"""Single domain FinBERT trainer with provenance, leakage and minimum-data gates."""

import argparse
import hashlib
import inspect
import json
from collections import Counter
from pathlib import Path

from backend.taxonomy import LABELS
from training_pipeline.preprocessing.prepare import assert_no_leakage, read_jsonl, validate_rows

MINIMUM = {"train": 100, "validation": 15, "test": 15}


def dataset_identity(folder):
    """Return a split-aware version and the individual source-file hashes."""
    folder = Path(folder)
    split_hashes = {
        key: hashlib.sha256((folder / f"{key}.jsonl").read_bytes()).hexdigest() for key in MINIMUM
    }
    canonical = json.dumps(split_hashes, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canonical).hexdigest(), split_hashes


def validate_training_data(splits):
    for key in MINIMUM:
        splits[key] = validate_rows(splits[key])
        if any(row["annotation_method"] == "weak_label" for row in splits[key]):
            raise ValueError("Weak labels cannot be used as supervised ground truth")
    assert_no_leakage(splits)
    errors = []
    for key, minimum in MINIMUM.items():
        counts = Counter(r["label"] for r in splits[key])
        errors.extend(
            f"{key}/{label}: {counts[label]} < {minimum}"
            for label in LABELS
            if counts[label] < minimum
        )
        if (
            key != "train"
            and splits[key]
            and sum(r["source_type"] == "synthetic" for r in splits[key]) / len(splits[key]) >= 0.5
        ):
            errors.append(f"{key}: synthetic examples must not dominate evaluation")
    if errors:
        raise ValueError("Insufficient eligible data:\n" + "\n".join(errors))
    return splits


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--base-model", default="ProsusAI/finbert", choices=["ProsusAI/finbert"])
    parser.add_argument("--epochs", type=float, default=8)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    folder = Path(args.data_dir)
    splits = validate_training_data({key: read_jsonl(folder / f"{key}.jsonl") for key in MINIMUM})
    # Imports and downloads happen only after data validation succeeds.
    import numpy as np
    import torch
    from sklearn.metrics import accuracy_score, f1_score
    from torch.utils.data import Dataset
    from transformers import (
        AutoModelForSequenceClassification,
        AutoTokenizer,
        EarlyStoppingCallback,
        Trainer,
        TrainingArguments,
        set_seed,
    )

    set_seed(args.seed)
    label2id = {label: i for i, label in enumerate(LABELS)}
    tokenizer = AutoTokenizer.from_pretrained(args.base_model, trust_remote_code=False)
    model = AutoModelForSequenceClassification.from_pretrained(
        args.base_model,
        num_labels=len(LABELS),
        label2id=label2id,
        id2label={i: label for label, i in label2id.items()},
        ignore_mismatched_sizes=True,
        trust_remote_code=False,
    )
    counts = Counter(r["label"] for r in splits["train"])
    weights = torch.tensor(
        [len(splits["train"]) / (len(LABELS) * counts[label]) for label in LABELS],
        dtype=torch.float,
    )

    class Clauses(Dataset):
        def __init__(self, rows):
            self.rows = rows

        def __len__(self):
            return len(self.rows)

        def __getitem__(self, index):
            row = self.rows[index]
            tokens = tokenizer(row["text"], padding="max_length", truncation=True, max_length=512)
            return {
                **{key: torch.tensor(value) for key, value in tokens.items()},
                "labels": torch.tensor(label2id[row["label"]]),
            }

    class WeightedTrainer(Trainer):
        def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
            labels = inputs.pop("labels")
            outputs = model(**inputs)
            loss = torch.nn.functional.cross_entropy(
                outputs.logits, labels, weight=weights.to(outputs.logits.device)
            )
            return (loss, outputs) if return_outputs else loss

    def metrics(prediction):
        logits, labels = prediction
        predicted = np.argmax(logits, axis=1)
        return {
            "accuracy": accuracy_score(labels, predicted),
            "macro_f1": f1_score(
                labels, predicted, labels=list(range(len(LABELS))), average="macro", zero_division=0
            ),
        }

    output = Path(args.output)
    arguments = TrainingArguments(
        output_dir=str(output / "checkpoints"),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        weight_decay=0.01,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="macro_f1",
        greater_is_better=True,
        save_total_limit=2,
        logging_steps=10,
        report_to="none",
        seed=args.seed,
        data_seed=args.seed,
        lr_scheduler_type="linear",
    )
    tokenizer_key = (
        "processing_class"
        if "processing_class" in inspect.signature(Trainer.__init__).parameters
        else "tokenizer"
    )
    trainer = WeightedTrainer(
        model=model,
        args=arguments,
        train_dataset=Clauses(splits["train"]),
        eval_dataset=Clauses(splits["validation"]),
        compute_metrics=metrics,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=2)],
        **{tokenizer_key: tokenizer},
    )
    trainer.train()
    dataset_hash, split_hashes = dataset_identity(folder)
    metadata = {
        "task": "contract_risk",
        "base_model": args.base_model,
        "version": "risklens-" + dataset_hash[:12],
        "dataset_version": dataset_hash,
        "split_hashes": split_hashes,
        "labels": LABELS,
        "training_config": vars(args),
        "split_counts": {key: len(rows) for key, rows in splits.items()},
    }
    model.config.risklens_metadata = metadata
    output.mkdir(parents=True, exist_ok=True)
    trainer.save_model(str(output))
    tokenizer.save_pretrained(str(output))
    (output / "training_metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(f"Saved validation-selected classifier: {output}")


if __name__ == "__main__":
    main()
