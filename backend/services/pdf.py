"""Bounded page extraction and traceable legal clause segmentation."""

import re

import pymupdf

from backend.schemas import Clause, Page

MAX_PAGES = 500
MAX_TEXT = 1_000_000
MAX_CLAUSES = 5000


class PDFError(ValueError):
    pass


def extract_pages(data: bytes) -> list[Page]:
    if not data.startswith(b"%PDF-"):
        raise PDFError("The file does not have a PDF signature.")
    try:
        with pymupdf.open(stream=data, filetype="pdf") as pdf:
            if pdf.needs_pass:
                raise PDFError("Password-protected PDFs are not supported.")
            if not 0 < len(pdf) <= MAX_PAGES:
                raise PDFError(f"PDF must contain between 1 and {MAX_PAGES} pages.")
            pages = []
            characters = 0
            for i, page in enumerate(pdf):
                text = page.get_text("text", sort=True)
                characters += len(text)
                if characters > MAX_TEXT:
                    raise PDFError("Extracted text exceeds the analysis limit.")
                pages.append(Page(page_number=i + 1, text=text))
    except PDFError:
        raise
    except Exception as exc:
        raise PDFError("The PDF is corrupt or unreadable.") from exc
    if not any(p.text.strip() for p in pages):
        raise PDFError(
            "No readable text was found. This may be a scanned PDF; OCR is not available."
        )
    return pages


def segment_pages(pages: list[Page]) -> list[Clause]:
    clauses = []
    boundary = re.compile(r";\s*|(?<=[.!?])\s+(?=[A-Z])|\n\s*\n|\n(?=\s*(?:\d+[.)]|[•●\-])\s)")
    for page in pages:
        start = 0
        for match in [*boundary.finditer(page.text), None]:
            end = match.start() if match else len(page.text)
            raw = page.text[start:end]
            text = re.sub(r"\s+", " ", raw).strip()
            if len(text) >= 8 and not re.fullmatch(r"[\d\s.()\-]+", text):
                if len(text) > 4000:
                    raise PDFError(
                        "A clause exceeds 4,000 characters; divide the document into shorter sections."
                    )
                clauses.append(
                    Clause(
                        clause_id=len(clauses) + 1,
                        page_number=page.page_number,
                        text=text,
                        start_offset=start,
                        end_offset=end,
                    )
                )
                if len(clauses) > MAX_CLAUSES:
                    raise PDFError("The document contains too many clauses.")
            start = match.end() if match else end
    if not clauses:
        raise PDFError("No analyzable clauses were found in the extracted text.")
    return clauses
