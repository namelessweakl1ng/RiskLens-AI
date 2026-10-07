"""Validate reviewer labels and create deterministic train/validation/test files."""

import argparse
import hashlib
import json
import random
from collections import Counter, defaultdict
from pathlib import Path


def load_labels(path: Path) -> set[str]:
    return set(json.loads(path.read_text(encoding="utf-8"))) - {"needs_expert_review"}


def load_rows(path: Path, valid_labels: set[str]) -> list[dict]:
    rows, fingerprints = [], set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        text, label = str(row.get("text", "")).strip(), str(row.get("label", "")).strip().lower()
        if not text or label not in valid_labels:
            raise ValueError(f"Line {line_number}: a valid text and label are required.")
        fingerprint = hashlib.sha256(text.lower().encode("utf-8")).hexdigest()
        if fingerprint in fingerprints:
            continue
        fingerprints.add(fingerprint)
        rows.append({"text": text, "label": label, "agreement_family": row.get("agreement_family", "unknown")})
    return rows


def write_jsonl(path: Path, rows: list[dict]):
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--labels", default=str(Path(__file__).with_name("labels.json")))
    args = parser.parse_args()

    rows = load_rows(Path(args.input), load_labels(Path(args.labels)))
    counts = Counter(row["label"] for row in rows)
    missing = [label for label, count in counts.items() if count < 10]
    if missing:
        raise SystemExit(f"Need at least 10 reviewed examples per represented label before splitting: {', '.join(missing)}")
    if counts["no_risk"] < max(counts.values()):
        raise SystemExit("Add more no_risk examples; it should be at least as common as the largest risk class.")

    grouped = defaultdict(list)
    for row in rows:
        grouped[row["label"]].append(row)
    train, validation, test = [], [], []
    random.seed(42)
    for label_rows in grouped.values():
        random.shuffle(label_rows)
        total = len(label_rows)
        test_end, validation_end = max(1, round(total * .15)), max(2, round(total * .25))
        test.extend(label_rows[:test_end])
        validation.extend(label_rows[test_end:validation_end])
        train.extend(label_rows[validation_end:])

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    write_jsonl(output / "train.jsonl", train)
    write_jsonl(output / "validation.jsonl", validation)
    write_jsonl(output / "test.jsonl", test)
    (output / "dataset_report.json").write_text(json.dumps({"counts": counts, "train": len(train), "validation": len(validation), "test": len(test)}, indent=2, default=dict), encoding="utf-8")
    print(f"Validated {len(rows)} clauses. Train={len(train)} Validation={len(validation)} Test={len(test)}")


if __name__ == "__main__":
    main()
