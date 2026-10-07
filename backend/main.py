from pathlib import Path
from datetime import datetime
import json
import re
import sqlite3
import traceback
import shutil

from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

FRONTEND_DIR = BASE_DIR / "frontend"
UPLOAD_DIR = BASE_DIR / "uploads"

DB_PATH = BASE_DIR / "risklens.db"

INDEX_FILE = FRONTEND_DIR / "index.html"
CSS_FILE = FRONTEND_DIR / "style.css"
JS_FILE = FRONTEND_DIR / "script.js"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
FRONTEND_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# FASTAPI
# ============================================================

app = FastAPI(
    title="RiskLens AI",
    description="AI-powered Financial Agreement Risk Intelligence",
    version="2.0.0",
)


# ============================================================
# STATIC FILES
# ============================================================

app.mount(
    "/static",
    StaticFiles(directory=str(FRONTEND_DIR)),
    name="static",
)


# ============================================================
# DATABASE
# ============================================================

def get_db():
    connection = sqlite3.connect(
        str(DB_PATH),
        check_same_thread=False
    )

    connection.row_factory = sqlite3.Row

    return connection


def init_db():

    db = get_db()

    cursor = db.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            document_type TEXT DEFAULT 'Financial Agreement',
            risk_score REAL DEFAULT 0,
            overall_risk TEXT DEFAULT 'Low',
            high_risk_count INTEGER DEFAULT 0,
            medium_risk_count INTEGER DEFAULT 0,
            low_risk_count INTEGER DEFAULT 0,
            clause_count INTEGER DEFAULT 0,
            summary TEXT DEFAULT '',
            created_at TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clauses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            clause_number INTEGER DEFAULT 0,
            clause_text TEXT DEFAULT '',
            risk_label TEXT DEFAULT 'no_risk',
            severity TEXT DEFAULT 'low',
            confidence REAL DEFAULT 0,
            model_name TEXT DEFAULT '',
            explanation TEXT DEFAULT '',
            FOREIGN KEY(document_id)
                REFERENCES documents(id)
                ON DELETE CASCADE
        )
    """)

    db.commit()
    db.close()


init_db()


# ============================================================
# FRONTEND
# ============================================================

@app.get("/")
async def home():

    if not INDEX_FILE.exists():
        return JSONResponse(
            status_code=404,
            content={
                "error": "index.html not found",
                "expected": str(INDEX_FILE)
            }
        )

    return FileResponse(
        str(INDEX_FILE),
        media_type="text/html"
    )


@app.get("/style.css")
async def css():

    if not CSS_FILE.exists():
        raise HTTPException(
            status_code=404,
            detail="style.css not found"
        )

    return FileResponse(
        str(CSS_FILE),
        media_type="text/css"
    )


@app.get("/script.js")
async def javascript():

    if not JS_FILE.exists():
        raise HTTPException(
            status_code=404,
            detail="script.js not found"
        )

    return FileResponse(
        str(JS_FILE),
        media_type="application/javascript"
    )


# ============================================================
# HEALTH
# ============================================================

@app.get("/api/health")
async def health():

    return {
        "status": "online",
        "application": "RiskLens AI",
        "database": DB_PATH.exists(),
        "frontend": INDEX_FILE.exists(),
        "css": CSS_FILE.exists(),
        "javascript": JS_FILE.exists()
    }


# ============================================================
# HELPERS
# ============================================================

def clean_text(value):

    if value is None:
        return ""

    return str(value).strip()


def normalize_risk_label(label):

    if not label:
        return "no_risk"

    label = str(label).strip().lower()

    mapping = {
        "high interest": "high_interest",
        "interest": "high_interest",
        "hidden charges": "hidden_charges",
        "hidden charge": "hidden_charges",
        "penalty": "penalty_clause",
        "penalty clause": "penalty_clause",
        "automatic renewal": "automatic_renewal",
        "auto renewal": "automatic_renewal",
        "unilateral change": "unilateral_change",
        "foreclosure": "foreclosure",
        "foreclosure risk": "foreclosure",
        "coverage exclusion": "coverage_exclusion",
        "exclusion": "coverage_exclusion",
        "waiting period": "waiting_period",
        "no risk": "no_risk",
        "safe": "no_risk"
    }

    return mapping.get(
        label,
        label.replace(" ", "_")
    )


def severity_for_label(label):

    label = normalize_risk_label(label)

    high = {
        "high_interest",
        "hidden_charges",
        "penalty_clause",
        "unilateral_change",
        "foreclosure",
        "coverage_exclusion"
    }

    medium = {
        "automatic_renewal",
        "waiting_period"
    }

    if label in high:
        return "high"

    if label in medium:
        return "medium"

    return "low"


def label_display(label):

    labels = {

        "high_interest":
            "High Interest",

        "hidden_charges":
            "Hidden Charges",

        "penalty_clause":
            "Penalty Clause",

        "automatic_renewal":
            "Automatic Renewal",

        "unilateral_change":
            "Unilateral Change",

        "foreclosure":
            "Foreclosure Risk",

        "coverage_exclusion":
            "Coverage Exclusion",

        "waiting_period":
            "Waiting Period",

        "no_risk":
            "No Risk"
    }

    label = normalize_risk_label(label)

    return labels.get(
        label,
        label.replace("_", " ").title()
    )


def extract_pdf_text(file_path):

    try:

        import fitz

        document = fitz.open(str(file_path))

        pages = []

        for page in document:

            text = page.get_text("text")

            if text:
                pages.append(text)

        document.close()

        return "\n".join(pages)

    except Exception:

        try:

            import pymupdf

            document = pymupdf.open(str(file_path))

            pages = []

            for page in document:

                text = page.get_text("text")

                if text:
                    pages.append(text)

            document.close()

            return "\n".join(pages)

        except Exception as exc:

            print("PDF extraction error:")
            print(exc)

            return ""


def split_clauses(text):

    if not text:
        return []

    text = re.sub(
        r"\s+",
        " ",
        text
    ).strip()

    parts = re.split(
        r"(?<=[.!?])\s+",
        text
    )

    clauses = []

    for part in parts:

        part = part.strip()

        if len(part) >= 35:

            clauses.append(part)

    if not clauses and text:

        chunks = [
            text[i:i + 500]
            for i in range(
                0,
                len(text),
                500
            )
        ]

        clauses = [
            x.strip()
            for x in chunks
            if x.strip()
        ]

    return clauses


# ============================================================
# RULE-BASED FALLBACK ANALYZER
# ============================================================

def fallback_analyze(text):

    clauses = split_clauses(text)

    findings = []

    rules = [

        (
            "high_interest",
            [
                "high interest",
                "interest rate",
                "annual percentage rate",
                "apr"
            ]
        ),

        (
            "hidden_charges",
            [
                "processing fee",
                "service charge",
                "additional charge",
                "administrative fee",
                "late fee"
            ]
        ),

        (
            "penalty_clause",
            [
                "penalty",
                "late payment",
                "default charge",
                "penal interest"
            ]
        ),

        (
            "automatic_renewal",
            [
                "automatically renew",
                "automatic renewal",
                "auto renewal"
            ]
        ),

        (
            "unilateral_change",
            [
                "may change",
                "sole discretion",
                "without notice",
                "modify the terms"
            ]
        ),

        (
            "foreclosure",
            [
                "foreclosure",
                "prepayment penalty",
                "early repayment"
            ]
        ),

        (
            "coverage_exclusion",
            [
                "exclusion",
                "not covered",
                "excluded from coverage"
            ]
        ),

        (
            "waiting_period",
            [
                "waiting period",
                "waiting time"
            ]
        )
    ]

    for index, clause_text in enumerate(
        clauses,
        start=1
    ):

        lower = clause_text.lower()

        detected_label = "no_risk"

        for label, keywords in rules:

            if any(
                keyword in lower
                for keyword in keywords
            ):

                detected_label = label
                break

        severity = severity_for_label(
            detected_label
        )

        confidence = (
            0.91
            if detected_label != "no_risk"
            else 0.72
        )

        findings.append({

            "clause_number": index,

            "clause_text": clause_text,

            "risk_label": detected_label,

            "severity": severity,

            "confidence": confidence,

            "model_name":
                "Rule-based Risk Analyzer",

            "explanation":
                (
                    "Potential risk-related term detected."
                    if detected_label != "no_risk"
                    else
                    "No configured high-risk pattern detected."
                )
        })

    return findings


# ============================================================
# AI ANALYZER
# ============================================================

def run_ai_analyzer(text):

    """
    Imports the existing RiskLens analyzer lazily.

    This is intentional:
    transformers/torch are NOT imported while FastAPI
    starts, preventing the entire server from crashing
    because of a PyTorch DLL problem.
    """

    try:

        from backend.services.risk_analyzer import analyze_document

        result = analyze_document(text)

        if result is None:
            return []

        if isinstance(result, list):
            return result

        if isinstance(result, dict):

            if isinstance(
                result.get("clauses"),
                list
            ):
                return result["clauses"]

            if isinstance(
                result.get("findings"),
                list
            ):
                return result["findings"]

            if isinstance(
                result.get("results"),
                list
            ):
                return result["results"]

        return []

    except Exception as exc:

        print()
        print("=" * 70)
        print("AI ANALYZER COULD NOT BE LOADED")
        print("=" * 70)
        print(str(exc))
        print("Using fallback risk analyzer.")
        print("=" * 70)
        print()

        return []


# ============================================================
# NORMALIZE AI RESULTS
# ============================================================

def normalize_findings(raw_findings, text):

    if not raw_findings:

        return fallback_analyze(text)

    normalized = []

    for index, item in enumerate(
        raw_findings,
        start=1
    ):

        if not isinstance(item, dict):

            continue

        clause_text = (
            item.get("clause_text")
            or item.get("text")
            or item.get("clause")
            or ""
        )

        predictions = item.get(
            "predictions"
        )

        prediction = {}

        if isinstance(
            predictions,
            list
        ) and predictions:

            if isinstance(
                predictions[0],
                dict
            ):
                prediction = predictions[0]

        label = (
            item.get("risk_label")
            or item.get("label")
            or prediction.get("risk_label")
            or prediction.get("label")
            or "no_risk"
        )

        confidence = (
            item.get("confidence")
            or prediction.get("confidence")
            or 0
        )

        try:
            confidence = float(confidence)
        except Exception:
            confidence = 0

        if confidence > 1:
            confidence = confidence / 100

        model_name = (
            item.get("model_name")
            or prediction.get("model_name")
            or "RiskLens AI"
        )

        label = normalize_risk_label(label)

        normalized.append({

            "clause_number":
                item.get(
                    "clause_number",
                    index
                ),

            "clause_text":
                clean_text(clause_text),

            "risk_label":
                label,

            "severity":
                severity_for_label(label),

            "confidence":
                confidence,

            "model_name":
                model_name,

            "explanation":
                item.get(
                    "explanation",
                    ""
                )
        })

    if not normalized:

        return fallback_analyze(text)

    return normalized


# ============================================================
# DOCUMENT TYPE
# ============================================================

def detect_document_type(
    filename,
    text
):

    combined = (
        filename + " " + text[:10000]
    ).lower()

    if any(
        x in combined
        for x in [
            "insurance",
            "policy holder",
            "premium",
            "coverage"
        ]
    ):
        return "Insurance Agreement"

    if any(
        x in combined
        for x in [
            "loan",
            "borrower",
            "principal amount",
            "interest rate",
            "repayment"
        ]
    ):
        return "Loan / Financial Agreement"

    if any(
        x in combined
        for x in [
            "credit card",
            "cardholder",
            "credit limit",
            "cash advance"
        ]
    ):
        return "Credit Card Agreement"

    if any(
        x in combined
        for x in [
            "lease",
            "tenant",
            "landlord",
            "monthly rent"
        ]
    ):
        return "Lease Agreement"

    if any(
        x in combined
        for x in [
            "investment",
            "shareholder",
            "equity",
            "shares"
        ]
    ):
        return "Investment / Equity Agreement"

    return "Financial Agreement"


# ============================================================
# RISK SCORE
# ============================================================

def calculate_risk_score(findings):

    score = 0

    for finding in findings:

        severity = finding.get(
            "severity",
            "low"
        )

        confidence = float(
            finding.get(
                "confidence",
                0
            ) or 0
        )

        if severity == "high":

            score += max(
                12,
                round(22 * confidence)
            )

        elif severity == "medium":

            score += max(
                7,
                round(12 * confidence)
            )

        else:

            if (
                finding.get(
                    "risk_label"
                ) != "no_risk"
            ):

                score += max(
                    2,
                    round(5 * confidence)
                )

    return min(
        100,
        max(0, score)
    )


def overall_risk_from_score(score):

    if score >= 60:
        return "High"

    if score >= 30:
        return "Medium"

    return "Low"


# ============================================================
# SAVE ANALYSIS
# ============================================================

def save_analysis(
    filename,
    document_type,
    findings,
    summary=""
):

    high = sum(
        1
        for x in findings
        if x.get("severity") == "high"
    )

    medium = sum(
        1
        for x in findings
        if x.get("severity") == "medium"
    )

    low = sum(
        1
        for x in findings
        if x.get("severity") == "low"
    )

    risk_score = calculate_risk_score(
        findings
    )

    overall_risk = overall_risk_from_score(
        risk_score
    )

    created_at = datetime.now().isoformat(
        timespec="seconds"
    )

    db = get_db()

    cursor = db.cursor()

    cursor.execute(
        """
        INSERT INTO documents (
            filename,
            document_type,
            risk_score,
            overall_risk,
            high_risk_count,
            medium_risk_count,
            low_risk_count,
            clause_count,
            summary,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            filename,
            document_type,
            risk_score,
            overall_risk,
            high,
            medium,
            low,
            len(findings),
            summary,
            created_at
        )
    )

    document_id = cursor.lastrowid

    for index, finding in enumerate(
        findings,
        start=1
    ):

        cursor.execute(
            """
            INSERT INTO clauses (
                document_id,
                clause_number,
                clause_text,
                risk_label,
                severity,
                confidence,
                model_name,
                explanation
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                document_id,

                finding.get(
                    "clause_number",
                    index
                ),

                finding.get(
                    "clause_text",
                    ""
                ),

                finding.get(
                    "risk_label",
                    "no_risk"
                ),

                finding.get(
                    "severity",
                    "low"
                ),

                finding.get(
                    "confidence",
                    0
                ),

                finding.get(
                    "model_name",
                    ""
                ),

                finding.get(
                    "explanation",
                    ""
                )
            )
        )

    db.commit()
    db.close()

    return document_id


# ============================================================
# GET DOCUMENT DETAILS
# ============================================================

def get_document_details(document_id):

    db = get_db()

    cursor = db.cursor()

    cursor.execute(
        """
        SELECT *
        FROM documents
        WHERE id = ?
        """,
        (document_id,)
    )

    document = cursor.fetchone()

    if not document:

        db.close()

        return None

    cursor.execute(
        """
        SELECT *
        FROM clauses
        WHERE document_id = ?
        ORDER BY clause_number ASC
        """,
        (document_id,)
    )

    clause_rows = cursor.fetchall()

    db.close()

    document_data = dict(document)

    clauses = []

    for row in clause_rows:

        clause = dict(row)

        prediction = {

            "risk_label":
                clause["risk_label"],

            "confidence":
                clause["confidence"],

            "model_name":
                clause["model_name"]
        }

        clauses.append({

            "id":
                clause["id"],

            "clause_number":
                clause["clause_number"],

            "clause_text":
                clause["clause_text"],

            "text":
                clause["clause_text"],

            "risk_label":
                clause["risk_label"],

            "severity":
                clause["severity"],

            "confidence":
                clause["confidence"],

            "model_name":
                clause["model_name"],

            "explanation":
                clause["explanation"],

            "predictions":
                [prediction]
        })

    report = {

        "risk_score":
            document_data["risk_score"],

        "overall_risk":
            document_data["overall_risk"],

        "high_risk_count":
            document_data["high_risk_count"],

        "medium_risk_count":
            document_data["medium_risk_count"],

        "low_risk_count":
            document_data["low_risk_count"],

        "clause_count":
            document_data["clause_count"],

        "summary":
            document_data["summary"]
    }

    return {

        "document":
            document_data,

        "report":
            report,

        "clauses":
            clauses
    }


# ============================================================
# ANALYZE PDF
# ============================================================

@app.post("/api/analyze")
async def analyze_pdf(
    file: UploadFile = File(...)
):

    if not file.filename:

        raise HTTPException(
            status_code=400,
            detail="No file selected"
        )

    if not file.filename.lower().endswith(
        ".pdf"
    ):

        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported"
        )

    safe_filename = Path(
        file.filename
    ).name

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    saved_name = (
        f"{timestamp}_{safe_filename}"
    )

    file_path = (
        UPLOAD_DIR / saved_name
    )

    try:

        with open(
            file_path,
            "wb"
        ) as buffer:

            shutil.copyfileobj(
                file.file,
                buffer
            )

        text = extract_pdf_text(
            file_path
        )

        if not text.strip():

            raise HTTPException(
                status_code=400,
                detail=(
                    "Could not extract text from the PDF. "
                    "Please upload a text-readable PDF."
                )
            )

        document_type = detect_document_type(
            safe_filename,
            text
        )

        # ----------------------------------------------------
        # Try the actual RiskLens AI analyzer first.
        # If transformers/torch cannot load, use fallback.
        # ----------------------------------------------------

        ai_findings = run_ai_analyzer(
            text
        )

        findings = normalize_findings(
            ai_findings,
            text
        )

        high = sum(
            1
            for x in findings
            if x["severity"] == "high"
        )

        medium = sum(
            1
            for x in findings
            if x["severity"] == "medium"
        )

        low = sum(
            1
            for x in findings
            if x["severity"] == "low"
        )

        risk_score = calculate_risk_score(
            findings
        )

        overall_risk = overall_risk_from_score(
            risk_score
        )

        summary = (
            f"{len(findings)} clauses analysed. "
            f"{high} high-risk, "
            f"{medium} medium-risk and "
            f"{low} low-risk findings detected."
        )

        document_id = save_analysis(
            filename=safe_filename,
            document_type=document_type,
            findings=findings,
            summary=summary
        )

        result = get_document_details(
            document_id
        )

        return {

            "success":
                True,

            "message":
                "Agreement analysed successfully",

            "document_id":
                document_id,

            **result
        }

    except HTTPException:
        raise

    except Exception as exc:

        print()
        print("=" * 70)
        print("ANALYSIS ERROR")
        print("=" * 70)
        print(traceback.format_exc())
        print("=" * 70)

        raise HTTPException(
            status_code=500,
            detail=str(exc)
        )


# ============================================================
# ALIAS FOR FRONTEND
# ============================================================

@app.post("/api/review")
async def review_pdf(
    file: UploadFile = File(...)
):

    return await analyze_pdf(file)


# ============================================================
# DASHBOARD
# ============================================================

@app.get("/api/dashboard")
async def dashboard():

    db = get_db()

    cursor = db.cursor()

    cursor.execute(
        """
        SELECT
            COUNT(*) AS total_documents,
            COALESCE(
                ROUND(AVG(risk_score), 1),
                0
            ) AS average_risk_score,
            COALESCE(
                SUM(high_risk_count),
                0
            ) AS total_high_risk,
            COALESCE(
                SUM(medium_risk_count),
                0
            ) AS total_medium_risk,
            COALESCE(
                SUM(low_risk_count),
                0
            ) AS total_low_risk
        FROM documents
        """
    )

    stats = dict(
        cursor.fetchone()
    )

    cursor.execute(
        """
        SELECT *
        FROM documents
        ORDER BY id DESC
        LIMIT 10
        """
    )

    recent = [
        dict(row)
        for row in cursor.fetchall()
    ]

    db.close()

    return {

        "total_documents":
            stats["total_documents"],

        "average_risk_score":
            stats["average_risk_score"],

        "total_high_risk":
            stats["total_high_risk"],

        "total_medium_risk":
            stats["total_medium_risk"],

        "total_low_risk":
            stats["total_low_risk"],

        "recent_documents":
            recent
    }


# ============================================================
# DOCUMENT LIST / HISTORY
# ============================================================

@app.get("/api/documents")
async def documents(

    search: str = Query(
        default=""
    ),

    risk: str = Query(
        default=""
    ),

    document_type: str = Query(
        default=""
    ),

    sort: str = Query(
        default="newest"
    )
):

    db = get_db()

    cursor = db.cursor()

    query = """
        SELECT *
        FROM documents
        WHERE 1 = 1
    """

    params = []

    if search:

        query += """
            AND filename LIKE ?
        """

        params.append(
            f"%{search}%"
        )

    if risk:

        query += """
            AND LOWER(overall_risk) = LOWER(?)
        """

        params.append(risk)

    if document_type:

        query += """
            AND document_type LIKE ?
        """

        params.append(
            f"%{document_type}%"
        )

    if sort == "oldest":

        query += """
            ORDER BY id ASC
        """

    elif sort == "risk_high":

        query += """
            ORDER BY risk_score DESC
        """

    elif sort == "risk_low":

        query += """
            ORDER BY risk_score ASC
        """

    else:

        query += """
            ORDER BY id DESC
        """

    cursor.execute(
        query,
        params
    )

    rows = cursor.fetchall()

    db.close()

    return {

        "documents":
            [
                dict(row)
                for row in rows
            ],

        "count":
            len(rows)
    }


# ============================================================
# SINGLE DOCUMENT
# ============================================================

@app.get("/api/documents/{document_id}")
async def document_details(
    document_id: int
):

    result = get_document_details(
        document_id
    )

    if result is None:

        raise HTTPException(
            status_code=404,
            detail="Document not found"
        )

    return result


# ============================================================
# DASHBOARD DOCUMENT DETAILS
# ============================================================

@app.get(
    "/api/dashboard/documents/{document_id}"
)
async def dashboard_document_details(
    document_id: int
):

    result = get_document_details(
        document_id
    )

    if result is None:

        raise HTTPException(
            status_code=404,
            detail="Document not found"
        )

    return result


# ============================================================
# DELETE DOCUMENT
# ============================================================

@app.delete("/api/documents/{document_id}")
async def delete_document(
    document_id: int
):

    db = get_db()

    cursor = db.cursor()

    cursor.execute(
        """
        SELECT id
        FROM documents
        WHERE id = ?
        """,
        (document_id,)
    )

    document = cursor.fetchone()

    if not document:

        db.close()

        raise HTTPException(
            status_code=404,
            detail="Document not found"
        )

    cursor.execute(
        """
        DELETE FROM clauses
        WHERE document_id = ?
        """,
        (document_id,)
    )

    cursor.execute(
        """
        DELETE FROM documents
        WHERE id = ?
        """,
        (document_id,)
    )

    db.commit()
    db.close()

    return {

        "success":
            True,

        "message":
            "Document deleted successfully"
    }


# ============================================================
# DEBUG FRONTEND
# ============================================================

@app.get("/api/debug/frontend")
async def debug_frontend():

    return {

        "base_dir":
            str(BASE_DIR),

        "frontend_dir":
            str(FRONTEND_DIR),

        "index":
            str(INDEX_FILE),

        "style":
            str(CSS_FILE),

        "script":
            str(JS_FILE),

        "index_exists":
            INDEX_FILE.exists(),

        "style_exists":
            CSS_FILE.exists(),

        "script_exists":
            JS_FILE.exists(),

        "database":
            str(DB_PATH),

        "database_exists":
            DB_PATH.exists()
    }


# ============================================================
# RUN DIRECTLY
# ============================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )