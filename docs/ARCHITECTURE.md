# Architecture and ownership

One AnalysisResult Pydantic schema is authoritative across API, SQLite and
frontend. The API never interprets a successful result as an unknown dict or
silently replaces it with a second analyzer.

- `backend/taxonomy.json`: labels, aliases, display, default severity, weights,
  evidence patterns, explanations and recommendations. Training and frontend
  taxonomy endpoint use this same source.
- `services/pdf.py`: signature/parser validation, bounded sorted page extraction,
  page-preserving clause segmentation and extracted-text offsets.
- `services/document_classifier.py`: one rule-based family classifier. Its
  classification_strength = winning-family signal count / all matched signals;
  exact top ties return unknown with candidate_types instead of silently selecting
  a family. Zero signals means unknown. Not an ML probability.
- `services/fine_tuned_risk_model.py`: one initialized domain-model loader per app,
  mapping/metadata validation, cached weights, bounded batches and locked genuine
  softmax inference. No remote custom Python code. Optional inference errors are
  visible in each stored result; the current configured model status is separate.
- `services/risk_analyzer.py`: one orchestration/rule engine, explicit negation and
  disagreement, multi-category clause findings, summaries and review actions.
- `services/scoring.py`: one scorer, independent of sentiment and document length.
- `database.py`: one transactional SQLite store, connection cleanup, parameterized
  queries and additive schema migration; canonical result JSON plus queryable
  document/clauses columns. No independent SQLAlchemy/fintel.db implementation.
- `main.py`: HTTP validation/transport, limits before multipart spooling, background
  thread for extraction/inference, no public mount for uploaded PDFs.
- `frontend/js`: safe DOM construction (textContent/text nodes), API, routing,
  analysis expansion, history and SVG charts. No competing frontend scoring.

PDF uploads are bounded by 20 MiB plus 64 KiB multipart overhead at the request
boundary, then by exact file-byte size. The framework upload spool is rolled to
disk, hashed incrementally and materialized once for PyMuPDF. Extensions/MIME/signature are checked,
filename path components and control characters are removed, encrypted/corrupt
PDFs rejected, image-only input explicitly reported. File resources close in a
finally block; no application upload copies remain. Work is capped at 500 pages,
one million extracted characters, 5,000 clauses and 4,000 characters per clause.
Inference uses overlapping windows at the model context limit, a bounded 96-token
stride and batches of 16 windows. For each original clause, the full distribution
from the window with the strongest material-class probability is retained; ties
select the earliest window. This prevents neutral windows from averaging away a
strong later risk signal while still returning one distribution per clause.

SQLite migration adds canonical_json and missing document metadata columns to
risklens.db while preserving original tables/IDs/data. Old entries are adapted
only on read and marked legacy_unverified. Their historical numeric score is
retained with scoring.formula_version=legacy_unverified, not represented as
current evidence. Legacy confidence is discarded from returned analysis; unknown
page/provenance remain null. Historical source rows are not rewritten. Fresh
analyses always store the canonical contract and analysis-time model status.
The unrelated prototype fintel.db, if present, is left intact.

Dashboard history includes canonical and legacy records, but average risk,
high-risk counts, risk distribution and document-family distribution use only
canonical analyses. The response reports verified and legacy counts separately.

The local app has no users/authentication/tenant boundary. Do not expose it as a
shared production service without a separate access-control and deployment task.
