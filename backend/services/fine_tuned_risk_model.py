"""Optional validated RiskLens classifier. Vanilla FinBERT sentiment is rejected."""

import os
import threading
from pathlib import Path

from backend.schemas import ModelStatus
from backend.taxonomy import LABELS


class RiskModel:
    def __init__(self, source: str | None = None):
        self.source = (
            source
            if source is not None
            else os.getenv("RISKLENS_MODEL_PATH") or os.getenv("RISKLENS_MODEL_ID")
        )
        self._status = ModelStatus()
        self._model = None
        self._tokenizer = None
        self._lock = threading.Lock()
        if self.source:
            self._load()

    def _load(self):
        try:
            import torch
            from transformers import AutoConfig, AutoModelForSequenceClassification, AutoTokenizer

            config = AutoConfig.from_pretrained(self.source, trust_remote_code=False)
            labels = {int(k): v for k, v in config.id2label.items()}
            if set(labels) != set(range(len(LABELS))) or set(labels.values()) != set(LABELS):
                raise ValueError("Model must have all ten RiskLens labels")
            if config.label2id != {label: i for i, label in labels.items()}:
                raise ValueError("Inconsistent model label mapping")
            metadata = getattr(config, "risklens_metadata", {})
            if metadata.get("labels") != [labels[i] for i in range(len(LABELS))]:
                raise ValueError("Deployment metadata labels do not match the classifier head")
            if (
                metadata.get("task") != "contract_risk"
                or metadata.get("base_model") != "ProsusAI/finbert"
                or not metadata.get("version")
            ):
                raise ValueError("Missing RiskLens deployment metadata")
            self._tokenizer = AutoTokenizer.from_pretrained(self.source, trust_remote_code=False)
            self._model = AutoModelForSequenceClassification.from_pretrained(
                self.source, trust_remote_code=False
            )
            device = "cuda" if torch.cuda.is_available() else "cpu"
            self._model.to(device).eval()
            self._status = ModelStatus(
                mode="hybrid",
                model_loaded=True,
                model_name=Path(self.source).name,
                version=metadata["version"],
                dataset_version=metadata.get("dataset_version"),
                device=device,
                labels=[labels[i] for i in range(len(labels))],
                load_error=None,
            )
        except Exception as exc:
            self._model = None
            self._tokenizer = None
            self._status = ModelStatus(
                load_error=f"RiskLens classifier unavailable ({type(exc).__name__}); verify model path, label mappings and deployment metadata."
            )

    def status(self) -> ModelStatus:
        return self._status.model_copy(deep=True)

    def predict(self, texts: list[str]) -> list[dict[str, float]]:
        if self._model is None:
            return []
        import torch

        output = []
        with self._lock, torch.inference_mode():
            for start in range(0, len(texts), 16):
                inputs = self._tokenizer(
                    texts[start : start + 16],
                    truncation=True,
                    max_length=512,
                    padding=True,
                    return_tensors="pt",
                ).to(self._status.device)
                probabilities = self._model(**inputs).logits.softmax(dim=-1).cpu().tolist()
                output.extend(dict(zip(self._status.labels, row)) for row in probabilities)
        return output
