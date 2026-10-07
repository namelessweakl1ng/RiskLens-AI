"""Metrics from actual predictions; no generated benchmark numbers."""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

from backend.taxonomy import LABELS


def write_evaluation(rows, predictions, output):
    if not rows or len(rows) != len(predictions):
        raise ValueError("Evaluation rows and predictions must be nonempty and aligned")
    expected = [row["label"] for row in rows]
    predicted = [max(probs, key=probs.get) for probs in predictions]
    report = classification_report(
        expected, predicted, labels=list(LABELS), output_dict=True, zero_division=0
    )
    matrix = confusion_matrix(expected, predicted, labels=list(LABELS))
    metrics = {
        "accuracy": accuracy_score(expected, predicted),
        "precision": report["macro avg"]["precision"],
        "recall": report["macro avg"]["recall"],
        "macro_f1": report["macro avg"]["f1-score"],
        "weighted_f1": report["weighted avg"]["f1-score"],
        "examples": len(rows),
    }
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    for filename, value in [
        ("metrics.json", metrics),
        ("classification_report.json", report),
        ("confusion_matrix.json", {"labels": LABELS, "matrix": matrix.tolist()}),
    ]:
        (output / filename).write_text(json.dumps(value, indent=2) + "\n")
    figure, axis = plt.subplots(figsize=(12, 10))
    image = axis.imshow(matrix, cmap="Blues")
    axis.set_xticks(range(len(LABELS)), LABELS, rotation=60, ha="right")
    axis.set_yticks(range(len(LABELS)), LABELS)
    axis.set_xlabel("Predicted label")
    axis.set_ylabel("Expected label")
    figure.colorbar(image, ax=axis)
    figure.tight_layout()
    figure.savefig(output / "confusion_matrix.png", dpi=160)
    plt.close(figure)
    errors = []
    for row, label, probs in zip(rows, predicted, predictions):
        if label != row["label"]:
            errors.append(
                {
                    "clause": row["text"],
                    "expected_label": row["label"],
                    "predicted_label": label,
                    "confidence": probs[label],
                    "source_document_id": row["source_document_id"],
                    "document_family": row["agreement_family"],
                }
            )
    (output / "errors.jsonl").write_text("".join(json.dumps(error) + "\n" for error in errors))
    return metrics
