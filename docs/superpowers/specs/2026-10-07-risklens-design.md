# RiskLens AI implementation design for review

Target: `prabhsxx17/RiskLens-AI`, branch `feat/complete-risk-intelligence-system`.
Baseline: `2876612dab01dfdd2fb7de95b7eea7b2ff3c9922`.
PR title: `feat: complete RiskLens AI hybrid document risk intelligence system`.

## Intent and scope

Implement the uploaded 36-section brief as one cohesive PR, retaining FastAPI,
SQLite, PyMuPDF and vanilla HTML/CSS/JavaScript. Deliver a working explainable
document-analysis application and a reproducible, honest model/data pipeline.
Model training and evaluation will run only with legitimate, adequately labeled
data. No fabricated probabilities, provenance, dashboard totals or metrics.

## Audit evidence

- `main.py` is 1,647 lines and duplicates taxonomy, classification, scoring,
  database logic and rule analysis from services.
- A structured successful service result is discarded by `run_ai_analyzer`.
  A deterministic injected result reproduced this without model downloads.
- Existing fallback labels fixed interest as `high_interest` and "No foreclosure
  or prepayment penalty will apply" as `penalty_clause`; both return 0.91.
- The 2,857 card labels were created by regex rules. Distribution: no_risk 1,867;
  high_interest 400; hidden_charges 350; penalty_clause 179; unilateral_change 44;
  automatic_renewal 17. None have source_document_id or annotation_method.
- Two independent database implementations target risklens.db and fintel.db.
- HTML is 3,648 lines with inline assets alongside separate JS/CSS files.
- There is no executable test suite, root README or CI workflow.
- Git clone/read works. GitHub REST requests fail at the proxy CONNECT stage
  with 403; this has not established whether PR write permission is available.

## Approach and alternatives

Recommended: refactor into one pipeline while keeping the existing lightweight
stack and endpoint entry points. Canonical Pydantic results flow unchanged from
analysis to storage and rendering. Migrate useful service functions and remove
the disconnected duplicates.

An adapter-only repair would preserve duplicated scorers and false confidence.
A framework rewrite would add migration cost without improving evidence or
model correctness. Neither is selected.

## Canonical analysis contract

One versioned taxonomy defines all ten requested labels, aliases, display names,
severities, weights, rules, explanations and review actions. Training imports
this taxonomy instead of keeping a separate label list.

AnalysisResult contains document metadata and classification evidence, pages,
clauses, model status, scoring breakdown, category/severity distributions,
health indicators, executive summary and recommendations. Each clause retains
its page, identifier, text, source offsets when feasible, primary label, severity,
nullable model confidence, complete class probabilities, rule matches,
detection method, disagreement details, explanation and recommendation.

Support multiple category findings within a clause even though the ML task is
multiclass. A primary label supports table presentation; secondary rule evidence
is retained and included in scoring. Rules never produce ML confidence.
Low-confidence unresolved model predictions are visibly uncertain, not declared
safe. No detected evidence means only "no configured risk detected".

## Extraction and API

Stream uploads with a configurable 20 MiB default cap; check extension, allowed
MIME and PDF magic. Use generated local filenames, validate with PyMuPDF and
reject corrupt, encrypted or image-only PDFs with explicit messages. Clean up
temporary files on both success and failure. No public upload directory mount.
Preserve reading order, page numbers and clause boundaries for numbered/bullet
paragraphs and semicolon obligations. Bound page/text/clause work to prevent
unbounded inference. Run blocking analysis outside the asynchronous event loop.

One rule classifier returns document_type, classification_strength and matched
evidence for loan, credit_card, insurance, investment, lease, other_financial and
unknown. The strength is a heuristic, not a calibrated probability.

Retain `/api/analyze`, `/api/review`, `/api/health`, `/api/dashboard`, document
listing/detail/deletion and useful dashboard-detail alias routes. Declare
canonical response models. Add `/api/system/model`. Frontend assets use one
static path. Remove obsolete duplicate code and debug endpoints.

## Model boundary and hybrid evidence

Load once at startup using RISKLENS_MODEL_PATH or a configured Hugging Face
identifier; default to no deployed classifier. Validate exact taxonomy mappings,
architecture and deployment metadata identifying a RiskLens-trained classifier.
Reject vanilla positive/negative/neutral FinBERT as a risk model. Expose name,
version, base model, dataset version, device and sanitized load failure details.

Return real softmax distributions and nullable confidence. The model threshold
defaults to 0.65 and is documented as configurable, not empirically calibrated.
Negation/protection-aware rules retain their exact matched evidence. Matching
model/rule categories produce hybrid evidence; disagreement remains explicit.
Missing or unusable model yields rule_only mode and "AI classifier unavailable"
in the UI. No sentiment contributes to the core risk score.

## Scoring proposal

For each unique normalized clause/category pair, evidence strength is 0.70 for
rules alone, model probability for accepted model-only predictions, or
min(1, max(0.70, probability) + 0.10) when model and rule agree on that category.
These strengths are scoring heuristics, explicitly distinguished from confidence.
Use category severity weights from the taxonomy and retain the strongest
clause/category contribution, avoiding repetition inflation.

Document score = round(100 * (0.65 * strongest weighted evidence +
0.25 * mean of top three weighted category contributions, padded with zero +
0.10 * min(unique material categories / 5, 1))). All contributions are in [0,1].
Safe/no-evidence clauses contribute zero. Repeating a clause changes no score.
Below-threshold model-only predictions do not create material category findings.
Expose components and category contributions. Thresholds are Low <30,
Moderate <60, High <80, Critical otherwise. Describe this as an explainable
triage heuristic rather than a validated estimate of financial loss.

## Persistence and compatibility

Consolidate SQLite operations in backend/database.py, using the live risklens.db
as the default and RISKLENS_DB_PATH for tests/configuration. Use transactions,
foreign keys, versioned migration and parameterized queries. Preserve legacy
records, timestamps and identifiers. Mark historical results legacy_unverified,
discard fabricated legacy confidence, and leave unavailable page/model metadata
unknown. Do not silently reinterpret historical scores as current-model output.
Do not delete or overwrite unrelated fintel.db data; document its separate origin.

Persist the canonical versioned result and queryable document/clauses fields.
History and detail rendering use stored analysis-time model status, not whatever
classifier happens to be loaded later. Deletion removes its associated records.

## Dataset and training

Consolidate under training_pipeline with ingestion, annotation, preprocessing,
evaluation, scripts and config packages. One trainer and evaluator; remove
obsolete duplicate trainers and document migration commands.

Use source manifests and verified HTTPS downloader tools for official CFPB,
public insurer wording, SEC exhibits and CUAD. Record observed URL, retrieval
timestamp, document checksum and source organization; do not invent missing
fields in imported legacy data. Reproduce large existing corpora before removing
tracked copies, otherwise preserve them and report the unresolved provenance.

Quarantine existing automatic card labels as weak_label; exclude them from
evaluation and supervised ground truth by default. Preserve original annotation
claims as legacy metadata rather than upgrade them to expert_reviewed. Include
clearly tagged synthetic curated hard-negative fixtures for all requested
trigger words. Synthetic examples cannot dominate the evaluation set.

Normalize Unicode/whitespace, safely remove repeated page headers/footers and
detect exact/normalized/near duplicates. Require valid provenance and source IDs.
Cluster duplicate-related source documents before deterministic group assignment
to approximately 70/15/15 splits; fail validation on cross-split source overlap
or near duplicates. Do not oversample evaluation data.

Report per-class/source/family counts, real/synthetic ratio, weak-label counts,
hard negatives, duplicate removals and split composition. Default training guard:
100 eligible training examples and 15 validation/test examples per taxonomy class;
report every unmet requirement. Insufficient/unverified existing data will not
be relabeled or trained merely to demonstrate completion.

Fine-tune ProsusAI/finbert with a reinitialized ten-label head, deterministic seed,
class weights, early stopping, validation-selected checkpoint, configurable
learning rate/epochs/batch size and CPU/GPU selection. Record config, data hashes
and model metadata. Evaluation writes all five requested metrics/report/matrix/
error artifacts, including confusion_matrix.png, using real inference only.
Model weights/checkpoints remain ignored. Provide exact CLI commands and clearly
state when training/evaluation could not run.

## Dashboard and accessibility

One semantic HTML shell and linked CSS/JS modules. Dark navy enterprise terminal
layout, restrained cyan accents, strong typography and sharp borders; every
rectangular component has border-radius: 0. Circular gauges use SVG.

History shows actual counts, average score, severity/type distribution and recent
activity; empty database shows an honest empty state. Analysis detail shows
filename, classification, stored analysis mode/version, animated score gauge,
category/severity charts, risk cards, searchable/filterable expandable clause
evidence with pages, model distribution/disagreements, health, summary and actions.
No random/demo statistics. Render user-controlled strings safely as text.

Health calculations: clause coverage = clauses with complete analysis / extracted
clauses; model coverage = successfully inferred clauses / clauses; evidence
coverage = material findings with explicit rule/model support / material findings;
high-risk density = high/critical clauses / clauses; safe ratio = clauses with
no material finding / clauses; extraction quality = text-bearing pages / pages;
classification strength comes from the documented classifier heuristic.
Zero denominators produce unavailable where appropriate, not invented 100%.

Include visible informational-use disclaimer, keyboard controls/focus, labeled
fields, live loading/error status, responsive layouts and reduced-motion support.
Verify desktop (1920px), laptop, tablet and mobile behavior, not just CSS syntax.

## Verification and PR completion

Add pytest suites for taxonomy, schema, rules and hard negatives, scoring bounds
and invariance, model mapping/probabilities/cache/unavailable behavior, provenance,
group splits and leakage, PDF validation, live pipeline integration, persistence,
migration, retrieval and deletion. Use generated legal-to-distribute PDF fixtures.
Exercise model-present logic with deterministic test models, clearly separated
from evaluation of a genuine trained FinBERT artifact.

Verify clean dependency installation, pytest, API startup/status, a legitimate
public financial/insurance PDF and dashboard interactions. Model absence must
pass explicit rule_only tests. Add CI and reproducible CLI/Makefile commands.
README plus DATASET/MODEL/ARCHITECTURE/RISK_SCORING docs explain every limitation.

After approval, create a detailed implementation plan, execute it with meaningful
tests, review the final diff and run acceptance checks before pushing/opening the
PR. Use the requested title and all required PR sections. Report actual dataset
counts, training configuration and commands, exact checks and genuine metrics
only. GitHub REST access and eventual write permission remain to be verified.

## Review status

This is a proposed design, prepared outside the checkout for user review.
Application source has not been changed and no PR has been opened.
