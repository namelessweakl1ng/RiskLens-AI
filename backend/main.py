"""FastAPI transport: one canonical analysis service and one SQLite store."""

import hashlib
import os
import re
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from backend.database import Store
from backend.schemas import AnalysisResult, ModelStatus
from backend.services.fine_tuned_risk_model import RiskModel
from backend.services.pdf import PDFError, extract_pages
from backend.services.risk_analyzer import analyze_pages
from backend.taxonomy import TAXONOMY

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
DEFAULT_UPLOAD_LIMIT = 20 * 1024 * 1024


class RequestSizeLimit:
    """Bound multipart reception before Starlette spools the upload to disk."""

    def __init__(self, app, limit):
        self.app = app
        self.limit = limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("method") != "POST":
            return await self.app(scope, receive, send)
        length = dict(scope.get("headers", [])).get(b"content-length")
        try:
            if length is not None and int(length) > self.limit:
                return await JSONResponse(
                    {"detail": "PDF request exceeds the upload limit."}, status_code=413
                )(scope, receive, send)
        except ValueError:
            return await JSONResponse({"detail": "Invalid Content-Length."}, status_code=400)(
                scope, receive, send
            )
        total = 0

        async def limited_receive():
            nonlocal total
            message = await receive()
            total += len(message.get("body", b""))
            if total > self.limit:
                raise HTTPException(413, "PDF request exceeds the upload limit.")
            return message

        return await self.app(scope, limited_receive, send)


def create_app(db_path=None, model=None, max_upload_bytes=DEFAULT_UPLOAD_LIMIT) -> FastAPI:
    app = FastAPI(
        title="RiskLens AI",
        description="Explainable financial and insurance document triage",
        version="3.0.0",
    )
    app.add_middleware(RequestSizeLimit, limit=max_upload_bytes + 65536)
    app.state.store = Store(db_path or os.getenv("RISKLENS_DB_PATH", str(BASE_DIR / "risklens.db")))
    app.state.risk_model = model if model is not None else RiskModel()
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/")
    def home():
        return FileResponse(FRONTEND_DIR / "index.html")

    @app.get("/style.css", include_in_schema=False)
    def stylesheet():
        return FileResponse(FRONTEND_DIR / "style.css")

    @app.get("/api/health")
    def health():
        return {
            "status": "online",
            "application": "RiskLens AI",
            "database": app.state.store.path.exists(),
            "frontend": (FRONTEND_DIR / "index.html").exists(),
            "mode": app.state.risk_model.status().mode,
        }

    @app.get("/api/system/model", response_model=ModelStatus)
    def model_status():
        return app.state.risk_model.status()

    @app.get("/api/system/taxonomy")
    def taxonomy():
        return TAXONOMY

    @app.post("/api/analyze", response_model=AnalysisResult)
    @app.post("/api/review", response_model=AnalysisResult, include_in_schema=False)
    async def analyze(file: UploadFile = File(...)):
        try:
            filename = re.split(r"[/\\]", file.filename or "")[-1]
            filename = "".join(char for char in filename if char.isprintable())[:200]
            if not filename.lower().endswith(".pdf"):
                raise HTTPException(415, "Only PDF uploads are supported.")
            if (file.content_type or "").lower() not in {"application/pdf", "application/x-pdf"}:
                raise HTTPException(415, "The upload MIME type must be application/pdf.")
            chunks = []
            length = 0
            while chunk := await file.read(1024 * 1024):
                length += len(chunk)
                if length > max_upload_bytes:
                    raise HTTPException(
                        413, f"PDF exceeds the {max_upload_bytes} byte upload limit."
                    )
                chunks.append(chunk)
            data = b"".join(chunks)

            def process():
                pages = extract_pages(data)
                result = analyze_pages(pages, filename, app.state.risk_model)
                result.sha256 = hashlib.sha256(data).hexdigest()
                return app.state.store.save(result)

            try:
                return await run_in_threadpool(process)
            except PDFError as exc:
                raise HTTPException(400, str(exc)) from exc
        finally:
            await file.close()

    @app.get("/api/dashboard")
    def dashboard():
        return app.state.store.dashboard()

    @app.get("/api/documents")
    def documents(limit: int = Query(100, ge=1, le=100), offset: int = Query(0, ge=0)):
        return {
            "documents": app.state.store.list(limit, offset),
            "total": app.state.store.dashboard()["total_documents"],
        }

    @app.get("/api/documents/{document_id}", response_model=AnalysisResult)
    @app.get(
        "/api/dashboard/documents/{document_id}",
        response_model=AnalysisResult,
        include_in_schema=False,
    )
    def document(document_id: int):
        result = app.state.store.get(document_id)
        if result is None:
            raise HTTPException(404, "Document not found.")
        return result

    @app.delete("/api/documents/{document_id}")
    def delete(document_id: int):
        if not app.state.store.delete(document_id):
            raise HTTPException(404, "Document not found.")
        return {"success": True, "message": "Document deleted."}

    return app


app = create_app()
