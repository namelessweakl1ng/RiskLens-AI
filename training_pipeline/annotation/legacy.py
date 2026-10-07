"""Audit/quarantine legacy labels without inventing missing provenance."""

import argparse
import json
from collections import Counter
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="training_pipeline/data/legacy/card_labeled.jsonl")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    rows = [json.loads(line) for line in Path(args.input).read_text().splitlines() if line.strip()]
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    quarantine = [
        {
            **row,
            "annotation_method": "weak_label",
            "source_document_id": None,
            "sha256": None,
            "source_url": None,
            "retrieved_at": None,
            "provenance_status": "incomplete_legacy",
            "legacy_source_file": row.get("source_file"),
            "ground_truth_eligible": False,
        }
        for row in rows
    ]
    (output / "weak_labels.jsonl").write_text("".join(json.dumps(row) + "\n" for row in quarantine))
    report = {
        "clauses": len(rows),
        "annotation_method": "weak_label",
        "source_file_count": len({row.get("source_file") for row in rows}),
        "examples_per_class": dict(Counter(row.get("label") for row in rows)),
        "ground_truth_eligible": 0,
        "missing_provenance": "Original PDF hashes, observed source URLs and retrieval timestamps are unavailable; source_file alone is not verified provenance.",
    }
    (output / "legacy_report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
