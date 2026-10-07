"""Evaluate a candidate against the untouched test set and export errors for review."""

import argparse
import json
from collections import defaultdict
from pathlib import Path

from transformers import pipeline


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--test", required=True)
    args = parser.parse_args()
    rows = read_jsonl(args.test)
    classifier = pipeline("text-classification", model=args.model, tokenizer=args.model, truncation=True, max_length=512)
    result = classifier([row["text"] for row in rows])
    per_label, errors = defaultdict(lambda: {"tp":0,"fp":0,"fn":0,"support":0}), []
    correct = 0
    for row, prediction in zip(rows, result):
        expected, actual = row["label"], prediction["label"].lower()
        per_label[expected]["support"] += 1
        if expected == actual:
            correct += 1; per_label[expected]["tp"] += 1
        else:
            per_label[actual]["fp"] += 1; per_label[expected]["fn"] += 1
            errors.append({**row, "predicted_label": actual, "confidence": round(float(prediction["score"]), 4)})
    report = {"accuracy": correct / max(len(rows),1), "by_label": {}}
    for label, values in per_label.items():
        precision = values["tp"] / max(values["tp"] + values["fp"],1); recall = values["tp"] / max(values["tp"] + values["fn"],1)
        report["by_label"][label] = {"precision": precision, "recall": recall, "f1": 2*precision*recall/max(precision+recall,1e-9), "support": values["support"]}
    output = Path(args.model)
    (output / "metrics.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (output / "error_review.jsonl").write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in errors) + ("\n" if errors else ""), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
