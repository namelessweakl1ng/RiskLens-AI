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


def test_upload_accepts_exact_limit_and_rejects_one_byte_over(tmp_path):
    from backend.main import create_app

    content = pdf_bytes()
    with TestClient(create_app(tmp_path / "exact.db", max_upload_bytes=len(content))) as exact:
        assert upload(exact, content).status_code == 200
    with TestClient(create_app(tmp_path / "over.db", max_upload_bytes=len(content) - 1)) as over:
        assert upload(over, content).status_code == 413


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


def test_legacy_detail_and_history_preserve_known_metadata(tmp_path):
    import sqlite3

    from backend.database import Store

    path = tmp_path / "historical.db"
    store = Store(path)
    with sqlite3.connect(path) as db:
        db.execute(
            "INSERT INTO documents(id,filename,created_at,document_type,risk_score,overall_risk) VALUES(1,'old.pdf','2026-01-01','loan',90,'High')"
        )
        db.execute(
            "INSERT INTO clauses(document_id,clause_text,risk_label,severity) VALUES(1,'A penalty applies.','penalty_clause','high')"
        )
    result = store.get(1)
    assert result.overall_risk == "High"
    assert result.classification.document_type == "loan"
    assert result.clauses[0].detection_method == "legacy_unverified"
    assert store.list()[0]["overall_risk"] == "High"
    dashboard = store.dashboard()
    assert dashboard["risk_distribution"] == {}
    assert dashboard["verified_documents"] == 0
    assert dashboard["legacy_unverified_documents"] == 1


def test_dashboard_excludes_legacy_from_canonical_aggregates(tmp_path):
    from backend.main import create_app
    from backend.services.fine_tuned_risk_model import RiskModel

    path = tmp_path / "mixed.db"
    with TestClient(create_app(path, RiskModel(""))) as mixed:
        canonical = upload(mixed).json()
        with sqlite3.connect(path) as db:
            db.execute(
                "INSERT INTO documents(filename,created_at,document_type,risk_score,overall_risk) VALUES('legacy.pdf','2020-01-01','loan',100,'High')"
            )
        dashboard = mixed.get("/api/dashboard").json()
        assert dashboard["total_documents"] == 2
        assert dashboard["verified_documents"] == 1
        assert dashboard["legacy_unverified_documents"] == 1
        assert dashboard["average_risk"] == canonical["risk_score"]
        assert dashboard["high_risk_documents"] == int(canonical["risk_score"] >= 60)
        assert sum(dashboard["risk_distribution"].values()) == 1
        assert len(mixed.get("/api/documents").json()["documents"]) == 2


def test_segmentation_stops_at_clause_limit_without_materializing_all_boundaries():
    from backend.schemas import Page
    from backend.services import pdf

    text = ";".join(f"clause number {index}" for index in range(pdf.MAX_CLAUSES + 1000))
    with pytest.raises(pdf.PDFError, match="too many clauses"):
        pdf.segment_pages([Page(page_number=1, text=text)])


def test_pdf_text_budget_stops_extraction_early(monkeypatch):
    from backend.services import pdf

    extracted = []

    class FakePage:
        def get_text(self, *args, **kwargs):
            extracted.append(1)
            return "a" * 600_000

    class FakePDF:
        needs_pass = False

        def __len__(self):
            return 3

        def __iter__(self):
            return iter([FakePage(), FakePage(), FakePage()])

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    monkeypatch.setattr(pdf.pymupdf, "open", lambda **kwargs: FakePDF())
    with pytest.raises(pdf.PDFError, match="text exceeds"):
        pdf.extract_pages(b"%PDF-test")
    assert len(extracted) == 2
