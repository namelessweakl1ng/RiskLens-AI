"""Extract de-duplicated clauses from approved PDFs for human labelling only."""

import argparse
import hashlib
import json
import re
from pathlib import Path

import pymupdf


def clauses_from_text(text: str) -> list[str]:
    """Split extracted PDF text into candidate clauses."""
    text = re.sub(r"\s+", " ", text).strip()

    candidates = re.split(
        r"(?<=[.;!?])\s+(?=[A-Z0-9(])",
        text
    )

    return [
        clause.strip()
        for clause in candidates
        if 40 <= len(clause.strip()) <= 1600
    ]


def main():
    parser = argparse.ArgumentParser(
        description="Prepare insurance agreement clauses for human labelling."
    )

    parser.add_argument(
        "--input",
        required=True,
        help="Folder containing authorised PDFs"
    )

    parser.add_argument(
        "--output",
        required=True,
        help="Output JSONL file"
    )

    args = parser.parse_args()

    input_dir = Path(args.input)
    output_path = Path(args.output)

    # Check input directory
    if not input_dir.exists():
        raise SystemExit(
            f"Input folder not found: {input_dir}"
        )

    seen = set()
    rows = []

    pdf_files = list(input_dir.rglob("*.pdf"))

    if not pdf_files:
        raise SystemExit(
            f"No PDF files found in: {input_dir}"
        )

    print(f"Found {len(pdf_files)} PDF file(s).")
    print("-" * 60)

    for pdf_path in pdf_files:

        family = pdf_path.parent.name

        print(f"Processing: {pdf_path}")

        # Check if file exists and is not empty
        if pdf_path.stat().st_size == 0:
            print(
                f"WARNING: Skipping empty PDF: {pdf_path.name}"
            )
            continue

        try:
            # Open PDF using modern PyMuPDF API
            with pymupdf.open(pdf_path) as document:

                if document.page_count == 0:
                    print(
                        f"WARNING: Skipping PDF with 0 pages: "
                        f"{pdf_path.name}"
                    )
                    continue

                text = " ".join(
                    page.get_text()
                    for page in document
                )

        except Exception as e:
            print(
                f"WARNING: Could not read {pdf_path.name}"
            )
            print(f"Reason: {e}")
            print("Skipping this file...")
            continue

        # Check extracted text
        if not text.strip():
            print(
                f"WARNING: No text extracted from "
                f"{pdf_path.name}"
            )
            print(
                "This may be a scanned/image-only PDF."
            )
            continue

        clauses = clauses_from_text(text)

        print(
            f"  Extracted {len(clauses)} candidate clause(s)"
        )

        for clause in clauses:

            fingerprint = hashlib.sha256(
                clause.lower().encode("utf-8")
            ).hexdigest()

            if fingerprint in seen:
                continue

            seen.add(fingerprint)

            rows.append(
                {
                    "text": clause,
                    "label": "",
                    "agreement_family": family,
                    "source_file": pdf_path.name
                }
            )

    # Create output directory
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    # Write JSONL dataset
    output_path.write_text(
        "\n".join(
            json.dumps(
                row,
                ensure_ascii=False
            )
            for row in rows
        )
        + ("\n" if rows else ""),
        encoding="utf-8"
    )

    print("-" * 60)
    print(
        f"Prepared {len(rows)} unique clauses "
        f"for human review:"
    )
    print(output_path)


if __name__ == "__main__":
    main()