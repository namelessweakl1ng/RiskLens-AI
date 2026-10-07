"""Evaluate a deployed-format RiskLens classifier on untouched test data."""

import argparse
from pathlib import Path

from backend.services.fine_tuned_risk_model import RiskModel
from training_pipeline.evaluation.metrics import write_evaluation
from training_pipeline.preprocessing.prepare import assert_no_leakage, read_jsonl, validate_rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    splits = {
        key: validate_rows(read_jsonl(Path(args.data_dir) / f"{key}.jsonl"))
        for key in ["train", "validation", "test"]
    }
    assert_no_leakage(splits)
    rows = splits["test"]
    if (
        not rows
        or any(row["annotation_method"] == "weak_label" for row in rows)
        or sum(row["source_type"] == "synthetic" for row in rows) / len(rows) >= 0.5
    ):
        raise ValueError(
            "Evaluation requires eligible test data that is not dominated by synthetic records"
        )
    model = RiskModel(args.model)
    if not model.status().model_loaded:
        raise ValueError(model.status().load_error)
    print(write_evaluation(rows, model.predict([row["text"] for row in rows]), args.output))


if __name__ == "__main__":
    main()
