"""Single transactional SQLite store with additive legacy migration."""

import sqlite3
from collections import Counter
from contextlib import contextmanager
from pathlib import Path

from backend.schemas import (
    AnalysisResult,
    Clause,
    DocumentClassification,
    ModelStatus,
    ScoreBreakdown,
)
from backend.services.scoring import severity_for_score
from backend.taxonomy import canonical_label


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            if db.execute("PRAGMA user_version").fetchone()[0] > 1:
                raise ValueError(
                    "Database schema is newer than this application; use a compatible version"
                )
            db.execute("""CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT, filename TEXT NOT NULL,
                created_at TEXT NOT NULL, document_type TEXT, risk_score REAL,
                overall_risk TEXT, canonical_json TEXT)""")
            db.execute("""CREATE TABLE IF NOT EXISTS clauses (
                id INTEGER PRIMARY KEY AUTOINCREMENT, document_id INTEGER NOT NULL,
                clause_number INTEGER, clause_text TEXT, risk_label TEXT,
                severity TEXT, confidence REAL, canonical_json TEXT,
                FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE)""")
            for table, columns in {
                "documents": {
                    "document_type": "TEXT",
                    "risk_score": "REAL",
                    "overall_risk": "TEXT",
                    "canonical_json": "TEXT",
                },
                "clauses": {"canonical_json": "TEXT"},
            }.items():
                current = {row[1] for row in db.execute(f"PRAGMA table_info({table})")}
                for column, kind in columns.items():
                    if column not in current:
                        db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {kind}")
            db.execute("CREATE INDEX IF NOT EXISTS clauses_document_index ON clauses(document_id)")
            db.execute("PRAGMA user_version=1")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=20)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def save(self, result: AnalysisResult) -> AnalysisResult:
        with self.connect() as db:
            cursor = db.execute(
                """INSERT INTO documents(filename,created_at,document_type,risk_score,overall_risk)
                VALUES(?,?,?,?,?)""",
                (
                    result.filename,
                    result.created_at,
                    result.classification.document_type,
                    result.risk_score,
                    result.overall_risk,
                ),
            )
            saved = result.model_copy(update={"document_id": cursor.lastrowid})
            db.execute(
                "UPDATE documents SET canonical_json=? WHERE id=?",
                (saved.model_dump_json(), saved.document_id),
            )
            for clause in saved.clauses:
                db.execute(
                    """INSERT INTO clauses(document_id,clause_number,clause_text,risk_label,severity,confidence,canonical_json)
                    VALUES(?,?,?,?,?,?,?)""",
                    (
                        saved.document_id,
                        clause.clause_id,
                        clause.text,
                        clause.predicted_label,
                        clause.severity,
                        clause.model_confidence,
                        clause.model_dump_json(),
                    ),
                )
        return saved

    def get(self, identifier: int) -> AnalysisResult | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM documents WHERE id=?", (identifier,)).fetchone()
            if row is None:
                return None
            if row["canonical_json"]:
                return AnalysisResult.model_validate_json(row["canonical_json"])
            clauses = db.execute(
                "SELECT * FROM clauses WHERE document_id=? ORDER BY id", (identifier,)
            ).fetchall()
            return self._legacy(dict(row), [dict(c) for c in clauses])

    @staticmethod
    def _legacy(row, old_clauses):
        clauses = []
        for i, item in enumerate(old_clauses, 1):
            try:
                label = canonical_label(item.get("risk_label") or "no_risk")
            except ValueError:
                label = "other_risk"
            severity = (item.get("severity") or "low").lower()
            if severity not in {"low", "medium", "high", "critical"}:
                severity = "low"
            clauses.append(
                Clause(
                    clause_id=item.get("clause_number") or i,
                    page_number=None,
                    text=item.get("clause_text") or "",
                    predicted_label=label,
                    severity=severity,
                    detection_method="legacy_unverified",
                    explanation="Historical, unverified: "
                    + (
                        item.get("explanation")
                        or "Evidence and confidence have not been verified. Reanalyze the original PDF."
                    ),
                    recommendation="Reanalyze the original PDF with the current engine.",
                )
            )
        score = min(100, max(0, float(row.get("risk_score") or 0)))
        return AnalysisResult(
            document_id=row["id"],
            filename=row["filename"],
            created_at=row["created_at"],
            classification=DocumentClassification(
                document_type=Store._legacy_type(row.get("document_type")),
                method="legacy_unverified",
            ),
            page_count=0,
            text_page_count=0,
            clause_count=len(clauses),
            clauses=clauses,
            model_status=ModelStatus(
                mode="legacy_unverified", load_error="Historical model provenance is unknown."
            ),
            mode="legacy_unverified",
            risk_score=score,
            overall_risk=Store._legacy_level(row.get("overall_risk"), score),
            legacy_overall_risk=row.get("overall_risk"),
            scoring=ScoreBreakdown(formula_version="legacy_unverified", score=score),
            severity_distribution=dict(Counter(c.severity for c in clauses)),
            category_distribution=dict(
                Counter(c.predicted_label for c in clauses if c.predicted_label != "no_risk")
            ),
            health={
                key: None
                for key in [
                    "clause_coverage",
                    "model_coverage",
                    "evidence_coverage",
                    "high_risk_density",
                    "safe_clause_ratio",
                    "extraction_quality",
                    "classification_strength",
                ]
            },
            executive_summary="Historical analysis preserved. Its score, evidence and model provenance are unverified; reanalyze the original PDF.",
            recommended_actions=["Reanalyze the original PDF."],
            legacy_unverified=True,
        )

    @staticmethod
    def _legacy_type(value):
        value = (value or "unknown").lower().replace(" agreement", "").replace(" ", "_")
        return (
            value
            if value
            in {"loan", "credit_card", "insurance", "investment", "lease", "other_financial"}
            else "unknown"
        )

    @staticmethod
    def _legacy_level(value, score):
        normalized = {
            "low": "Low",
            "medium": "Moderate",
            "moderate": "Moderate",
            "high": "High",
            "critical": "Critical",
        }
        return normalized.get((value or "").lower(), severity_for_score(score))

    def list(self, limit=100, offset=0):
        with self.connect() as db:
            rows = db.execute(
                "SELECT id,filename,created_at,document_type,risk_score,overall_risk,canonical_json IS NULL AS legacy FROM documents ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
            return [
                dict(
                    document_id=r["id"],
                    filename=r["filename"],
                    created_at=r["created_at"],
                    document_type=r["document_type"] or "unknown",
                    risk_score=r["risk_score"] or 0,
                    overall_risk=self._legacy_level(r["overall_risk"], r["risk_score"] or 0)
                    if r["legacy"]
                    else severity_for_score(r["risk_score"] or 0),
                    legacy_unverified=bool(r["legacy"]),
                )
                for r in rows
            ]

    def dashboard(self):
        with self.connect() as db:
            rows = db.execute(
                "SELECT risk_score,document_type,overall_risk,canonical_json FROM documents"
            ).fetchall()
        scores = [float(r["risk_score"] or 0) for r in rows]
        return {
            "total_documents": len(rows),
            "average_risk": round(sum(scores) / len(scores), 1) if scores else 0,
            "high_risk_documents": sum(score >= 60 for score in scores),
            "risk_distribution": dict(
                Counter(
                    self._legacy_level(r["overall_risk"], r["risk_score"] or 0)
                    if not r["canonical_json"]
                    else severity_for_score(r["risk_score"] or 0)
                    for r in rows
                )
            ),
            "document_type_distribution": dict(
                Counter(r["document_type"] or "unknown" for r in rows)
            ),
            "recent_documents": self.list(limit=8),
        }

    def delete(self, identifier):
        with self.connect() as db:
            exists = db.execute("SELECT id FROM documents WHERE id=?", (identifier,)).fetchone()
            if exists is None:
                return False
            db.execute("DELETE FROM clauses WHERE document_id=?", (identifier,))
            db.execute("DELETE FROM documents WHERE id=?", (identifier,))
            return True
