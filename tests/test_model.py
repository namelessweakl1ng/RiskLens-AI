"""Tiny randomly initialized models are loader fixtures, not trained RiskLens artifacts."""

import pytest


@pytest.fixture
def tiny_model(tmp_path):
    from transformers import BertConfig, BertForSequenceClassification, BertTokenizer

    from backend.taxonomy import LABELS

    folder = tmp_path / "tiny-fixture"
    folder.mkdir()
    (folder / "vocab.txt").write_text("[PAD]\n[UNK]\n[CLS]\n[SEP]\n[MASK]\na\nfee\napplies\n.\n")
    tokenizer = BertTokenizer(vocab_file=str(folder / "vocab.txt"))
    tokenizer.save_pretrained(folder)
    config = BertConfig(
        vocab_size=9,
        hidden_size=16,
        num_hidden_layers=1,
        num_attention_heads=2,
        intermediate_size=32,
        num_labels=len(LABELS),
        id2label={i: label for i, label in enumerate(LABELS)},
        label2id={label: i for i, label in enumerate(LABELS)},
    )
    config.risklens_metadata = {
        "task": "contract_risk",
        "base_model": "ProsusAI/finbert",
        "version": "randomized-test-fixture-not-trained",
        "dataset_version": "test-fixture",
        "labels": list(LABELS),
    }
    BertForSequenceClassification(config).save_pretrained(folder)
    return folder


def test_loader_softmax_and_cached_model(tiny_model):
    from backend.services.fine_tuned_risk_model import RiskModel
    from backend.taxonomy import LABELS

    model = RiskModel(str(tiny_model))
    assert model.status().model_loaded, model.status().load_error
    identity = id(model._model)
    results = model.predict(["A fee applies.", "A fee applies."])
    assert len(results) == 2
    assert set(results[0]) == set(LABELS)
    assert sum(results[0].values()) == pytest.approx(1, abs=1e-6)
    assert all(0 <= value <= 1 for value in results[0].values())
    assert results[0] == pytest.approx(results[1])
    model.predict(["A fee applies."])
    assert id(model._model) == identity


def test_inconsistent_deployment_labels_rejected(tiny_model):
    import json

    from backend.services.fine_tuned_risk_model import RiskModel

    path = tiny_model / "config.json"
    config = json.loads(path.read_text())
    config["risklens_metadata"]["labels"] = ["negative", "positive", "neutral"]
    path.write_text(json.dumps(config))
    assert not RiskModel(str(tiny_model)).status().model_loaded


def test_sentiment_head_is_rejected_without_download(tmp_path):
    from transformers import BertConfig

    from backend.services.fine_tuned_risk_model import RiskModel

    config = BertConfig(
        num_labels=3,
        id2label={0: "positive", 1: "negative", 2: "neutral"},
        label2id={"positive": 0, "negative": 1, "neutral": 2},
    )
    config.save_pretrained(tmp_path)
    model = RiskModel(str(tmp_path))
    assert not model.status().model_loaded
    assert model.status().mode == "rule_only"


def test_missing_model_directory_falls_back(tmp_path):
    from backend.services.fine_tuned_risk_model import RiskModel

    assert RiskModel(str(tmp_path / "missing")).status().mode == "rule_only"
