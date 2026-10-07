# Verification evidence

Verified in the cloud development environment on 2026-10-07. These are functional
and engineering checks, **not model benchmark metrics**. The app's current mode
is explicitly rule_only because no domain-trained artifact is available.

## Executed checks

| Command / check | Observed outcome |
| --- | --- |
| `python3 -m venv .venv` | Fresh isolated project environment created |
| `PIP_CACHE_DIR=/workspace/review/pip-cache .venv/bin/python -m pip install 'torch==2.14.1+cpu' --index-url https://download.pytorch.org/whl/cpu` | Exit 0, CPU PyTorch installed with normal TLS verification |
| `.venv/bin/python -m pip install -r requirements-dev.txt` | Exit 0; includes clean runtime requirements installation |
| `.venv/bin/python -m pip check` | No broken requirements |
| `.venv/bin/python -m pytest -q` | 56 passed, 0 failed; one upstream Starlette HTTPX deprecation warning |
| `.venv/bin/ruff check backend training_pipeline tests` | All checks passed |
| `.venv/bin/ruff format --check backend training_pipeline tests` | 33 files already formatted |
| `for file in frontend/js/*.js tests/browser.cjs; do node --check "$file" || exit 1; done` | All JavaScript syntax checks passed |
| `RISKLENS_DB_PATH=/workspace/review/browser-test.db python -m uvicorn backend.main:app --host 127.0.0.1 --port 8001` | Startup succeeded |
| `GET /api/health`, `/api/system/model`, `/api/system/taxonomy` | Online/database/frontend ready; explicit rule-only classifier status and ten-label taxonomy |
| `RISKLENS_URL=http://127.0.0.1:8001 PYTHON=.venv/bin/python BROWSER_ARTIFACTS=/workspace/review/browser-final node tests/browser.cjs` | Browser acceptance passed; real Chromium, four responsive widths |
| `python -m training_pipeline.ingestion.cuad --output /workspace/review/cuad-restored` | Pinned archive/checksum verified; three JSON files restored byte-identical to prototype copies |
| `python -m training_pipeline.annotation.legacy --output /workspace/review/legacy-quarantine` | 2,857 weak labels / 60 filenames; eligible ground truth zero |
| `python -m training_pipeline.preprocessing.prepare --input training_pipeline/data/fixtures/hard_negatives.jsonl --output /workspace/review/synthetic-split` | Deterministic synthetic challenge split/report generated for guard validation only |
| `python -m training_pipeline.scripts.train --data-dir /workspace/review/synthetic-split --output /workspace/review/untrained-artifact` | Intentionally rejected: insufficient per-class eligible data and synthetic-only evaluation; no model weights trained |
| Trainer/evaluator `--help` | CLI imports/arguments work |

## Browser coverage

The checked-in optional `tests/browser.cjs` uses synthetic text-readable PDF input
with actual server results, not mocked dashboard responses. It verifies empty
state, file selection/upload, honest missing-model UI, risk cards, clause search,
severity filter, expandable evidence, history reopen, deletion and unsafe filename
rendering without HTML execution. It checks all rectangular controls' computed
border-radius is 0px, no document horizontal overflow, and no page errors at
1920×1080, 1366×900, 768×1024 and 390×844. Tables intentionally scroll within their
own container on narrow screens.

Run against a **new empty throwaway SQLite database**, never your history DB:

```bash
# Optional tooling; no frontend framework/build requirement:
npm install --prefix /tmp/risklens-browser playwright
# If no system Chromium exists:
/tmp/risklens-browser/node_modules/.bin/playwright install chromium
RISKLENS_DB_PATH=/tmp/risklens-browser-test.db uvicorn backend.main:app --host 127.0.0.1 --port 8001
# In a second shell, with the Python venv active:
NODE_PATH=/tmp/risklens-browser/node_modules RISKLENS_URL=http://127.0.0.1:8001 PYTHON=python node tests/browser.cjs
```

Use BROWSER_EXECUTABLE to select an installed browser and BROWSER_ARTIFACTS for
screenshots/results. The cloud check used system `/usr/bin/chromium` rather than
bypassing TLS to download a blocked browser package.

## Public real document check

Exact excerpts from CUAD's public **Principal Life Insurance Company — Broker
Dealer Marketing and Servicing Agreement** were formatted as a two-page PDF.
Their upstream corpus was independently checksum-verified. A live HTTP upload
returned 10 page-linked clauses, insurance classification (heuristic strength
0.5), rule_only mode and a 0.0 score. No configured risk evidence occurred in those
excerpts, so the system correctly did **not invent findings**. SHA256 matched,
stored retrieval was exactly equal to the response, and deletion succeeded.
This is a real-public-language functional check, not a labeled accuracy example.
Separate synthetic challenge PDFs exercised actual risky/safe rule behavior.

## Model boundary

Four tests use a tiny, randomly initialized, local BERT artifact solely to verify
actual softmax distributions, all ten mappings, repeatable cached inference,
sentiment-head rejection, metadata-label mismatch rejection and missing-artifact
fallback. Its configuration/version identifies it as a test fixture. It is not
fine-tuned FinBERT, and no accuracy/F1 claim is derived from it. API tests also
inject deterministic probability fixtures to prove successful hybrid results are
preserved end-to-end. These unit fixtures are separate from production inference.

## Verified versions

Python 3.12.14, torch 2.14.1+cpu, transformers 5.19.0, accelerate 1.15.0,
FastAPI 0.142.2, Uvicorn 0.54.0, PyMuPDF 1.28.2, NumPy 2.5.3, scikit-learn 1.9.1,
matplotlib 3.11.2, pytest 9.1.1, HTTPX 0.28.1, Ruff 0.16.10; browser tooling
Playwright 1.62.1 with installed system Chromium. CI runs the same Python suite,
lint, formatting and JS syntax checks; remote CI results require a pushed PR.

## Limitations that remain

No eligible reviewed real training set, no trained/deployed domain classifier and
no genuine model evaluation metrics. The trainer deliberately refuses the current
weak/synthetic-only data. CFPB and huggingface.co requests returned proxy CONNECT
403; GitHub/public CUAD access worked. Data/model access and genuine annotations
are prerequisites for training, not reasons to invent numbers or request API keys.
Rule-only behavior is verified; production-trained hybrid accuracy is unverified.
The upstream Starlette TestClient HTTPX deprecation warning is non-failing; it is
reported rather than suppressed. On read-only HOME environments, set writable
MPLCONFIGDIR/XDG_CACHE_HOME for repeated plotting to avoid temporary-cache warnings.
