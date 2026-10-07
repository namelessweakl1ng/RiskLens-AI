"""Optional inference layer for the project-specific clause classifier.

The application deliberately falls back to the deterministic rules until a
reviewed model artifact has been trained and placed in backend/models.
"""

from functools import lru_cache
from pathlib import Path

from transformers import pipeline


MODEL_DIR = Path(__file__).resolve().parents[1] / "models" / "contract-risk-classifier"


@lru_cache(maxsize=1)
def get_clause_classifier():
    """Load the reviewed fine-tuned model only when its artifacts exist."""
    if not (MODEL_DIR / "config.json").exists():
        return None

    return pipeline(
        "text-classification",
        model=str(MODEL_DIR),
        tokenizer=str(MODEL_DIR),
        truncation=True,
        max_length=512,
    )


def classify_risk_clause(clause: str):
    """Return a high-confidence domain label, or None when no model is deployed."""
    classifier = get_clause_classifier()
    if classifier is None or not clause.strip():
        return None

    result = classifier(clause)[0]
    label = str(result["label"]).lower().replace(" ", "_")
    return {"label": label, "confidence": round(float(result["score"]), 3)}
