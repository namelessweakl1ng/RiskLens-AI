# Dataset methodology and current inventory

No production ground-truth RiskLens training/evaluation set exists in this PR.
No classifier has been trained and no model benchmark metrics are claimed.

| Data | Verified origin / provenance | Annotation | Count / use |
| --- | --- | --- | --- |
| Legacy credit-card clauses | 60 source filenames; source PDFs, observed URLs, dates and hashes are unavailable | 2,857 automatic regex weak labels | Quarantined; excluded from ground truth |
| Legacy reviewed clauses | Source documents and reviewer provenance missing; historical human_review claim preserved | Unverified historical claim | 2; excluded pending provenance restoration |
| Synthetic challenge cases | Created by this project's deterministic fixture generator; hashes of source text and a stable fixture timestamp | synthetic_curated | 21, including 12 hard negatives; testing/supplement only |
| CUAD v1 | The Atticus Project official GitHub, pinned revision and SHA256 manifest | Expert annotation for **CUAD's separate extraction categories**, not RiskLens labels | 510 source contracts; no automatic RiskLens training mapping |
| CFPB / insurance / SEC candidates | Explicit authoritative source manifests with observed URL, retrieval timestamp and document SHA256 | Unannotated until genuine review | No newly ingested PDF corpus in this environment; source access restricted |

Legacy weak-label distribution: no_risk 1,867; high_interest 400; hidden_charges
350; penalty_clause 179; unilateral_change 44; automatic_renewal 17. The other
four taxonomy classes have no weak examples here. Eligible real training clauses:
**0**. Synthetic fixtures are not sufficient to train the classifier.

## Authorized sources

Prefer the [CFPB Credit Card Agreement Database](https://www.consumerfinance.gov/credit-cards/agreements/),
[IRDAI](https://irdai.gov.in/) and published insurer policy wordings, and
[SEC EDGAR exhibits](https://www.sec.gov/edgar/search/). Specify exact source
organization/family/URL, not random blog text. SEC requests require a genuine
`SEC_USER_AGENT` organization/contact string. Add an insurer source ID,
organization and exact hostnames to the reviewed approved-source manifest before
ingestion. This tool only handles text PDFs;
HTML SEC exhibits require a separate reviewed conversion before PDF ingestion.

A `sources.json` manifest is an array of objects with an approved `source_id`,
`url` (observed actual PDF HTTPS URL), `source_type`, `source_organization`,
`agreement_family`, and optional `sha256`. Source IDs, organizations and exact
hostnames are governed by `training_pipeline/data/manifests/approved_sources.json`;
extend that reviewed manifest before using another public insurer or authority.
Do not paste an illustrative or guessed URL as though it were a retrieved source.
TLS verification, size limits, redirect-host restrictions and optional SHA256
verification remain enabled. Ingestion creates unlabelled candidate records and
an actual retrieval manifest; manual review supplies labels and annotation method.

## Required records

Every eligible row contains text, label, agreement_family, source_type,
annotation_method, source_document_id, source_organization, source_url,
retrieved_at (timezone-aware ISO8601), sha256 and is_hard_negative. For public
real sources, source_id is also required and the HTTPS URL hostname/organization must match the
approved-source manifest. For synthetic clauses, URL must be null,
source_type is synthetic, annotation_method is synthetic_curated and the document
hash is the hash of its generated source text. Hashes do not verify a human review;
retain your annotation audit records. Expert/human review must actually occur.

Valid annotations: expert_reviewed, human_reviewed, project_curated,
synthetic_curated, weak_label. Weak labels are retained separately and excluded
from supervised ground truth and evaluation. Automatically generated outputs are
never human_reviewed. Uncertain labels must be resolved or omitted before splitting.

## Cleaning, duplicates and splits

NFKC Unicode and whitespace normalization; standalone page-number and copyright
line removal. No broad deletion of contractual boilerplate. SHA256 detects
normalized duplicates. Character similarity >=0.90 (with >=0.80 relative length)
identifies near duplicates; token indexing narrows candidate pairs. Identical
clauses with conflicting labels fail validation.

Source-document groups connected by exact/near duplicates are unioned before
assignment, including transitive chains. Deterministic seed 42 seeks 70/15/15
train/validation/test proportions and class balance; indivisible source groups
may prevent exact proportions. All three splits must contain independent groups.
Validation fails on cross-split documents or near duplicates. Evaluation is never
oversampled. The report records all counts, distributions, duplicate removals,
near-duplicate groups and real/synthetic proportions. Synthetic examples must
constitute less than half of both validation and test.

Model training records each split file's SHA256 and hashes their canonical
train/validation/test mapping into dataset_version. Swapping or moving content
between splits therefore changes the model's dataset identity.

## CUAD reproducibility and mapping

`python -m training_pipeline.ingestion.cuad` downloads the pinned official archive.
Archive SHA256: `f8161d18bea4e9c05e78fa6dda61c19c846fb8087ea969c172753bc2f45b999a`.
All three JSON files were independently restored and verified byte-identical to
the previous tracked copies. Copies remain local/ignored; this PR removes them
from tracking without rewriting existing Git history.

Mapping policy: **no automatic CUAD-to-RiskLens label mapping**. Renewal,
termination, exclusivity, transfer, liability and change provisions can provide
review candidates or hard negatives, but their contractual meaning must be
reviewed in context and the mapping logged with the annotator's actual method.
CUAD expert annotations do not certify a RiskLens financial-risk label.
Citation: Hendrycks et al., *CUAD: An Expert-Annotated NLP Dataset for Legal
Contract Review* (2021), https://arxiv.org/abs/2103.06268.
