# RiskLens domain classifier

**Current status: no trained RiskLens classifier or genuine benchmark metrics.**
The system runs explicitly in `rule_only` mode until an accepted artifact is
configured. ProsusAI/finbert is a three-label financial sentiment checkpoint,
not a contractual-risk classifier. Its sentiment outputs do not affect risk score.

One trainer reinitializes the ten-label head using canonical label2id/id2label.
It uses seed 42, class-weighted cross entropy, early stopping (patience 2),
validation-selected macro-F1 checkpoints, linear LR scheduling, weight decay
0.01, default learning rate 2e-5, eight epochs and batch size eight. CUDA is used
when available, otherwise CPU. Batch size/epochs/LR/seed are CLI options.

Before any downloads/training, the guard requires eligible provenance, no weak
labels, no source/near-duplicate leakage, at least 100 train and 15 validation/test
examples per each of ten classes, and synthetic share <50% in validation/test.
Do not lower these guards simply to claim a trained final-year demonstration.

```bash
python -m training_pipeline.preprocessing.prepare --input reviewed.jsonl --output training_pipeline/data/processed/v1
python -m training_pipeline.scripts.train --data-dir training_pipeline/data/processed/v1 --output training_pipeline/artifacts/v1 --epochs 8 --batch-size 8 --learning-rate 2e-5 --seed 42
python -m training_pipeline.scripts.evaluate --model training_pipeline/artifacts/v1 --data-dir training_pipeline/data/processed/v1 --output training_pipeline/artifacts/v1/evaluation
RISKLENS_MODEL_PATH=training_pipeline/artifacts/v1 uvicorn backend.main:app --reload
```

Evaluation writes accuracy, macro precision/recall/F1, weighted-F1 and per-class
precision/recall/F1/support to metrics.json and classification_report.json;
confusion_matrix.json includes ordered labels, confusion_matrix.png is plotted,
and errors.jsonl retains misclassified text, expected/predicted label, real model
confidence, source document and family. These are generated only from actual
predictions on the untouched test split. Test fixture metrics are not benchmarks.

Model deployment uses `RISKLENS_MODEL_PATH` or `RISKLENS_MODEL_ID`. The loader
validates all ten stable labels, inverse mappings and config.risklens_metadata
(task=contract_risk, base_model=ProsusAI/finbert, version). The trainer records
source split hashes, training arguments and counts in this metadata. Metadata
is a contract, not a guarantee of acceptable accuracy: inspect evaluation and
review errors before deploying. Remote custom Python code is never trusted.

`dataset_version` hashes a canonical mapping of the train, validation and test
file hashes; `split_hashes` retains each SHA256. Exchanging identical row bytes
between splits therefore produces a different artifact identity.

`GET /api/system/model` exposes actual availability, mode, name, base model,
version, dataset_version, labels and device. Load failures are visible. Loaded
classifiers return genuine softmax distributions; default accepted-label
threshold is 0.65 (a configurable policy in the analyzer, not calibrated accuracy).
Every analysis stores its own model status/version; historical views do not
substitute a later classifier. Inference failures downgrade that analysis to
explicit rule_only with an error. Below-threshold predictions remain visible as
uncertain and do not dominate score.

Long clauses are tokenized into overlapping windows at the model context limit
with up to 96 tokens of overlap. Windows run in bounded batches of 16. RiskLens
returns one distribution per original clause: the complete distribution from
the earliest window with the strongest material-class probability. This avoids
averaging away a strong risk signal near the end of a clause. It does not infer
relationships that span separate windows.

Training is blocked by the absence of eligible reviewed data. In this environment
CFPB and huggingface.co HTTPS requests also returned proxy CONNECT 403; no API
key would fix that network policy. Permit official data/model download domains
when actually collecting/training. Do not publish invented results or train on
the 2,857 legacy regex labels as though they were human ground truth.
