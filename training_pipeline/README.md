# One RiskLens training pipeline

Run all commands from the repository root. Labels and rules come exclusively
from `backend/taxonomy.json`. The old independent trainers and clause-random
split scripts have been removed; their data is preserved under `data/legacy`.

1. Collect authorized public PDFs using an explicit source manifest:
   `python -m training_pipeline.ingestion.public_sources --manifest sources.json --output training_pipeline/data/raw/collection`.
2. Annotate `candidates.jsonl`: set a taxonomy label, truthful annotation_method,
   and is_hard_negative. Never upgrade a rule output to human_reviewed.
3. Prepare source-grouped splits:
   `python -m training_pipeline.preprocessing.prepare --input reviewed.jsonl --output training_pipeline/data/processed/v1`.
4. Train only after minimum data checks pass:
   `python -m training_pipeline.scripts.train --data-dir training_pipeline/data/processed/v1 --output training_pipeline/artifacts/v1 --epochs 8 --batch-size 8 --learning-rate 2e-5 --seed 42`.
5. Evaluate the untouched split:
   `python -m training_pipeline.scripts.evaluate --model training_pipeline/artifacts/v1 --data-dir training_pipeline/data/processed/v1 --output training_pipeline/artifacts/v1/evaluation`.
6. Deploy only after domain review: `RISKLENS_MODEL_PATH=training_pipeline/artifacts/v1 uvicorn backend.main:app --reload`.

Restore CUAD with `python -m training_pipeline.ingestion.cuad`. The pinned archive
and all three restored files were checksum-verified against the prototype copies.
No CUAD category is automatically treated as a RiskLens risk label.

Generate supplementary challenge cases with
`python -m training_pipeline.annotation.hard_negatives`. The committed 21 cases
are explicitly synthetic fixtures (12 hard negatives), not a production training
set or evaluation benchmark. See [DATASET](../docs/DATASET.md) and
[MODEL](../docs/MODEL.md) for provenance, constraints and honest status.
