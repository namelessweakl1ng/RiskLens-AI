"""Train an isolated, validation-selected FinBERT clause-classification candidate."""

import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.utils.data import Dataset
from transformers import AutoModelForSequenceClassification, AutoTokenizer, EarlyStoppingCallback, Trainer, TrainingArguments, set_seed


class ClauseDataset(Dataset):
    def __init__(self, rows, tokenizer, label_to_id):
        self.rows, self.tokenizer, self.label_to_id = rows, tokenizer, label_to_id
    def __len__(self): return len(self.rows)
    def __getitem__(self, index):
        row = self.rows[index]
        values = self.tokenizer(row["text"], truncation=True, max_length=512, padding="max_length")
        values["labels"] = self.label_to_id[row["label"]]
        return {key: torch.tensor(value) for key, value in values.items()}


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def weighted_metrics(prediction):
    logits, labels = prediction
    predicted = np.argmax(logits, axis=1)
    accuracy = float((predicted == labels).mean())
    f1_values = []
    for label in np.unique(labels):
        true_positive = np.sum((predicted == label) & (labels == label))
        false_positive = np.sum((predicted == label) & (labels != label))
        false_negative = np.sum((predicted != label) & (labels == label))
        precision = true_positive / max(true_positive + false_positive, 1)
        recall = true_positive / max(true_positive + false_negative, 1)
        f1_values.append(2 * precision * recall / max(precision + recall, 1e-9))
    return {"accuracy": accuracy, "macro_f1": float(np.mean(f1_values))}


class WeightedTrainer(Trainer):
    def __init__(self, class_weights, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.class_weights = class_weights
    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        labels = inputs.pop("labels")
        outputs = model(**inputs)
        weights = self.class_weights.to(outputs.logits.device)
        loss = nn.CrossEntropyLoss(weight=weights)(outputs.logits, labels)
        return (loss, outputs) if return_outputs else loss


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", required=True)
    parser.add_argument("--validation", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--base-model", default="ProsusAI/finbert")
    parser.add_argument("--epochs", type=float, default=8)
    parser.add_argument("--batch-size", type=int, default=8)
    args = parser.parse_args()

    set_seed(42)
    train_rows, validation_rows = read_jsonl(args.train), read_jsonl(args.validation)
    labels = sorted({row["label"] for row in train_rows + validation_rows})
    label_to_id, id_to_label = {name: index for index, name in enumerate(labels)}, {index: name for index, name in enumerate(labels)}
    counts = Counter(row["label"] for row in train_rows)
    weights = torch.tensor([len(train_rows) / (len(labels) * counts[label]) for label in labels], dtype=torch.float)
    tokenizer = AutoTokenizer.from_pretrained(args.base_model)
    model = AutoModelForSequenceClassification.from_pretrained(args.base_model, num_labels=len(labels), label2id=label_to_id, id2label=id_to_label, ignore_mismatched_sizes=True)
    output = Path(args.output)
    training_args = TrainingArguments(output_dir=str(output / "checkpoints"), num_train_epochs=args.epochs, per_device_train_batch_size=args.batch_size, per_device_eval_batch_size=args.batch_size, learning_rate=2e-5, weight_decay=.01, eval_strategy="epoch", save_strategy="epoch", load_best_model_at_end=True, metric_for_best_model="macro_f1", greater_is_better=True, save_total_limit=2, logging_steps=10, report_to="none")
    trainer = WeightedTrainer(class_weights=weights, model=model, args=training_args, train_dataset=ClauseDataset(train_rows, tokenizer, label_to_id), eval_dataset=ClauseDataset(validation_rows, tokenizer, label_to_id), compute_metrics=weighted_metrics, callbacks=[EarlyStoppingCallback(early_stopping_patience=2)])
    trainer.train()
    output.mkdir(parents=True, exist_ok=True)
    trainer.save_model(output)
    tokenizer.save_pretrained(output)
    metrics = trainer.evaluate()
    (output / "training_metadata.json").write_text(json.dumps({"base_model": args.base_model, "labels": labels, "training_examples": len(train_rows), "validation_examples": len(validation_rows), "class_counts": counts, "validation_metrics": metrics}, indent=2, default=dict), encoding="utf-8")
    print(f"Candidate model saved to {output}")


if __name__ == "__main__":
    main()
