PYTHON ?= python
.PHONY: test lint run restore-cuad train evaluate

test:
	$(PYTHON) -m pytest
lint:
	$(PYTHON) -m ruff check backend training_pipeline tests
	$(PYTHON) -m ruff format --check backend training_pipeline tests
run:
	$(PYTHON) -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
restore-cuad:
	$(PYTHON) -m training_pipeline.ingestion.cuad
train:
	$(PYTHON) -m training_pipeline.scripts.train --data-dir training_pipeline/data/processed/v1 --output training_pipeline/artifacts/v1 --epochs 8 --batch-size 8 --learning-rate 2e-5 --seed 42
evaluate:
	$(PYTHON) -m training_pipeline.scripts.evaluate --model training_pipeline/artifacts/v1 --data-dir training_pipeline/data/processed/v1 --output training_pipeline/artifacts/v1/evaluation
