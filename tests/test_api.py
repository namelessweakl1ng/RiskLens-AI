import sqlite3

import pymupdf
import pytest
from fastapi.testclient import TestClient


def pdf_bytes(text="Loan agreement. A processing fee is payable by the borrower.", pages=1):
    with pymupdf.open() as pdf:
        for i in range(pages):
            page = pdf.new_page()
            if text:
                page.insert_text((72, 72), text + f" Page {i + 1}.")
        return pdf.tobytes()


@pytest.fixture
def client(tmp_path):
    from backend.main import create_app
    from backend.services.fine_tuned_risk_model import RiskModel

    with TestClient(create_app(tmp_path / "test.db", RiskModel(""))) as value:
        yield value


def upload(client, content=None, filename="loan.pdf", mime="application/pdf"):
    return client.post(
        "/api/analyze",
        files={"file": (filename, pdf_bytes() if content is None else content, mime)},
    )


def test_health_and_model_status(client):
    assert client.get("/api/health").json()["status"] == "online"
    status = client.get("/api/system/model").json()
    assert status["mode"] == "rule_only" and not status["model_loaded"]
    assert len(status["labels"]) == 10


def test_pdf_analysis_is_canonical_and_reloadable(client):
    response = upload(client, pdf_bytes(pages=2))
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["mode"] == "rule_only"
    assert result["classification"]["document_type"] == "loan"
    assert result["page_count"] == 2
    assert {c["page_number"] for c in result["clauses"]} == {1, 2}
    assert result["risk_score"] == result["scoring"]["score"]
    assert any(c["rule_matches"] for c in result["clauses"])
    assert all(c["model_confidence"] is None for c in result["clauses"])
    id_ = result["document_id"]
    assert client.get(f"/api/documents/{id_}").json() == result
    dashboard = client.get("/api/dashboard").json()
    assert dashboard["total_documents"] == 1
    assert dashboard["average_risk"] == result["risk_score"]
    assert client.delete(f"/api/documents/{id_}").status_code == 200
    assert client.get(f"/api/documents/{id_}").status_code == 404
    assert client.get("/api/dashboard").json()["total_documents"] == 0


@pytest.mark.parametrize(
    "content,name,mime,message",
    [
        (b"not a pdf", "bad.pdf", "application/pdf", "signature"),
        (b"%PDF-1.7\ngarbage", "bad.pdf", "application/pdf", "corrupt"),
        (b"", "empty.pdf", "application/pdf", "signature"),
        (None, "bad.exe", "application/pdf", "PDF"),
        (None, "bad.pdf", "text/plain", "MIME"),
        (pdf_bytes(""), "scan.pdf", "application/pdf", "OCR"),
    ],
)
def test_invalid_uploads(client, content, name, mime, message):
    response = upload(client, content, name, mime)
    assert response.status_code in (400, 415), response.text
    assert message.lower() in response.json()["detail"].lower()
    assert client.get("/api/dashboard").json()["total_documents"] == 0


def test_upload_limit(tmp_path):
    from backend.main import create_app

    with TestClient(create_app(tmp_path / "limit.db", max_upload_bytes=100)) as client:
        assert upload(client).status_code == 413


def test_filename_is_sanitized(client):
    result = upload(client, filename="../../private\\loan.pdf").json()
    assert result["filename"] == "loan.pdf"


def test_live_model_results_are_not_discarded(tmp_path):
    from backend.main import create_app
    from backend.schemas import ModelStatus
    from backend.taxonomy import LABELS

    class Model:
        def status(self):
            return ModelStatus(
                mode="hybrid", model_loaded=True, version="test-fixture", load_error=None
            )

        def predict(self, texts):
            return [
                {label: 0.91 if label == "hidden_charges" else 0.01 for label in LABELS}
                for _ in texts
            ]

    with TestClient(create_app(tmp_path / "hybrid.db", Model())) as client:
        result = upload(client).json()
        assert result["mode"] == "hybrid"
        assert result["model_status"]["version"] == "test-fixture"
        assert any(c["detection_method"] == "hybrid" for c in result["clauses"])
        assert all(c["model_confidence"] == pytest.approx(0.91) for c in result["clauses"])


def test_legacy_migration_preserves_record_and_removes_fake_confidence(tmp_path):
    from backend.main import create_app

    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as db:
        db.executescript("""CREATE TABLE documents(id INTEGER PRIMARY KEY, filename TEXT NOT NULL, risk_score REAL, overall_risk TEXT, created_at TEXT NOT NULL);
        CREATE TABLE clauses(id INTEGER PRIMARY KEY,document_id INTEGER,clause_number INTEGER,clause_text TEXT,risk_label TEXT,severity TEXT,confidence REAL);
        INSERT INTO documents VALUES(42,'old.pdf',40,'Medium','2026-01-01');
        INSERT INTO clauses VALUES(1,42,1,'A processing fee applies.','hidden_charges','high',0.91);""")
    with TestClient(create_app(path)) as client:
        result = client.get("/api/documents/42").json()
        assert result["document_id"] == 42 and result["filename"] == "old.pdf"
        assert result["mode"] == "legacy_unverified"
        assert result["clauses"][0]["model_confidence"] is None
        assert result["clauses"][0]["page_number"] is None
        assert upload(client).status_code == 200
    with sqlite3.connect(path) as db:
        assert db.execute("select count(*) from documents").fetchone()[0] == 2
        assert db.execute("select confidence from clauses where id=1").fetchone()[0] == 0.91


def test_empty_dashboard(client):
    data = client.get("/api/dashboard").json()
    assert data["total_documents"] == 0
    assert data["average_risk"] == 0
    assert data["recent_documents"] == []


def test_store_connection_closes_after_transaction(tmp_path):
    from backend.database import Store

    store = Store(tmp_path / "closed.db")
    with store.connect() as db:
        assert db.execute("select 1").fetchone()[0] == 1
    with pytest.raises(sqlite3.ProgrammingError):
        db.execute("select 1")


def test_oversized_request_rejected_before_multipart_parse(client):
    response = client.post(
        "/api/analyze",
        content=b"not multipart",
        headers={
            "Content-Type": "multipart/form-data; boundary=x",
            "Content-Length": str(100 * 1024 * 1024),
        },
    )
    assert response.status_code == 413


def test_taxonomy_endpoint_uses_authoritative_policy(client):
    from backend.taxonomy import TAXONOMY

    assert client.get("/api/system/taxonomy").json() == TAXONOMY


def test_streamed_oversize_body_is_bounded_before_spooling(client):
    # No Content-Length: the ASGI receive limit must still apply.
    response = client.post(
        "/api/analyze",
        content=iter([b"x" * (21 * 1024 * 1024)]),
        headers={"Content-Type": "multipart/form-data; boundary=x"},
    )
    assert response.status_code == 413


def test_future_database_schema_is_not_downgraded(tmp_path):
    from backend.database import Store

    path = tmp_path / "future.db"
    with sqlite3.connect(path) as db:
        db.execute("PRAGMA user_version=2")
    with pytest.raises(ValueError):
        Store(path)
    with sqlite3.connect(path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 2
