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
            self._model, loading = AutoModelForSequenceClassification.from_pretrained(
                self.source, trust_remote_code=False, output_loading_info=True
            )
            if (
                loading.get("missing_keys")
                or loading.get("mismatched_keys")
                or loading.get("error_msgs")
            ):
                raise ValueError("Checkpoint has missing or incompatible model weights")
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
        configured = getattr(self._model.config, "max_position_embeddings", 512)
        tokenizer_limit = getattr(self._tokenizer, "model_max_length", configured)
        window = min(configured, tokenizer_limit if tokenizer_limit < 100_000 else configured, 512)
        with self._lock, torch.inference_mode():
            for text in texts:
                inputs = self._tokenizer(
                    text,
                    truncation=True,
                    max_length=window,
                    stride=min(96, window // 4),
                    return_overflowing_tokens=True,
                    padding=True,
                    return_tensors="pt",
                ).to(self._status.device)
                inputs.pop("overflow_to_sample_mapping", None)
                rows = []
                for start in range(0, inputs["input_ids"].shape[0], 16):
                    batch = {key: value[start : start + 16] for key, value in inputs.items()}
                    rows.extend(self._model(**batch).logits.softmax(dim=-1).cpu().tolist())
                material = [i for i, label in enumerate(self._status.labels) if label != "no_risk"]
                # Preserve the complete distribution from the window with the
                # strongest material signal; ties choose the earliest window.
                strongest = max(rows, key=lambda row: max(row[i] for i in material))
                output.append(dict(zip(self._status.labels, strongest)))
        return output
