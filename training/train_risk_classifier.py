"""Fine-tune a clause classifier from human-reviewed JSONL examples.

Usage:
  python training/train_risk_classifier.py --data training/data/risk_clauses.jsonl
"""

import argparse
import json
from pathlib import Path

import torch
from torch.utils.data import Dataset
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    Trainer,
    TrainingArguments,
    set_seed,
)


DEFAULT_BASE_MODEL = "ProsusAI/finbert"
DEFAULT_OUTPUT = Path("backend/models/contract-risk-classifier")


class ClauseDataset(Dataset):
    def __init__(self, rows, tokenizer, label_to_id):
        self.rows = rows
        self.tokenizer = tokenizer
        self.label_to_id = label_to_id

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, index):
        row = self.rows[index]
        encoded = self.tokenizer(
            row["text"], truncation=True, max_length=512, padding="max_length"
        )
        encoded["labels"] = self.label_to_id[row["label"]]
        return {key: torch.tensor(value) for key, value in encoded.items()}


def load_rows(path: Path):
    rows = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row.get("text"), str) or not isinstance(row.get("label"), str):
            raise ValueError(f"Line {number} must contain string fields 'text' and 'label'.")
        rows.append({"text": row["text"].strip(), "label": row["label"].strip().lower()})
    if len(rows) < 20:
        raise ValueError("Use at least 20 reviewed clauses before training.")
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True, help="JSONL with text and label fields")
    parser.add_argument("--base-model", default=DEFAULT_BASE_MODEL)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--epochs", type=float, default=5)
    parser.add_argument("--batch-size", type=int, default=8)
    args = parser.parse_args()

    set_seed(42)
    rows = load_rows(Path(args.data))
    labels = sorted({row["label"] for row in rows})
    if "no_risk" not in labels:
        raise ValueError("Include representative 'no_risk' clauses to reduce false positives.")
    label_to_id = {label: index for index, label in enumerate(labels)}
    id_to_label = {index: label for label, index in label_to_id.items()}

    tokenizer = AutoTokenizer.from_pretrained(args.base_model)
    model = AutoModelForSequenceClassification.from_pretrained(
        args.base_model,
        num_labels=len(labels),
        label2id=label_to_id,
        id2label=id_to_label,
        ignore_mismatched_sizes=True,
    )
    dataset = ClauseDataset(rows, tokenizer, label_to_id)
    output_dir = Path(args.output_dir)
    training_args = TrainingArguments(
        output_dir=str(output_dir / "checkpoints"),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        learning_rate=2e-5,
        weight_decay=0.01,
        logging_steps=5,
        save_strategy="no",
        report_to="none",
    )
    Trainer(model=model, args=training_args, train_dataset=dataset).train()
    output_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)
    (output_dir / "training_metadata.json").write_text(
        json.dumps({"base_model": args.base_model, "labels": labels, "examples": len(rows)}, indent=2),
        encoding="utf-8",
    )
    print(f"Saved fine-tuned classifier to {output_dir}")


if __name__ == "__main__":
    main()
