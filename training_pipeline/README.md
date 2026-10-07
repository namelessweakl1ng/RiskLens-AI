# RiskLens model-training workspace

This folder is separate from the live website and backend. Nothing here changes the model used by the running application. It prepares and evaluates a candidate model only.

## Step 1 — collect authorised documents

Use only documents that are public, licensed for your use, or provided with the owner's explicit permission. Never add documents containing account numbers, Aadhaar/PAN numbers, signatures, addresses, phone numbers, email addresses, or other personal information.

Create these folders and place your approved PDFs in the matching family folder:

```text
training_pipeline/data/raw/loan/
training_pipeline/data/raw/insurance/
training_pipeline/data/raw/investment_equity/
training_pipeline/data/raw/lease_asset/
training_pipeline/data/raw/cards/
```

Suggested sources: public agreement templates, publicly posted insurance wording, public SEC/EDGAR contract exhibits for equity/investment clauses, and the CFPB credit-card agreement database. Keep the source URL and date in your tracking notes.

## Step 2 — extract candidate clauses

From the project folder, run:

```powershell
python training_pipeline\prepare_dataset.py --input training_pipeline\data\raw --output training_pipeline\data\candidates.jsonl
```

This produces clause candidates only. It does **not** label them and it does not use them for model training.

## Step 3 — label every clause manually

Open `training_pipeline/data/candidates.jsonl` in VS Code. Add a `label` to every retained record using one value from `labels.json`.

Important rules:

- Label the meaning of the whole clause, not just one word.
- Use `no_risk` for ordinary terms. It must be at least as common as any individual risk label.
- Mark uncertain clauses as `needs_expert_review` and exclude them from training.
- Have a finance, insurance, or legal-domain reviewer check a sample from each label.

Copy the reviewed records into `training_pipeline/data/reviewed.jsonl`.

## Step 4 — validate and split

```powershell
python training_pipeline\validate_and_split.py --input training_pipeline\data\reviewed.jsonl --output training_pipeline\data\processed
```

The command rejects invalid labels, duplicate clauses, empty text, and under-represented labels. It creates independent `train.jsonl`, `validation.jsonl`, and `test.jsonl` files.

## Step 5 — train a candidate model

```powershell
python training_pipeline\train_optimized.py --train training_pipeline\data\processed\train.jsonl --validation training_pipeline\data\processed\validation.jsonl --output training_pipeline\artifacts\candidate_v1
```

Training uses FinBERT as a starting point, class-weighted loss to reduce ignored minority risks, early stopping, and validation-based model selection. It does not overwrite the live model.

## Step 6 — evaluate before deployment

```powershell
python training_pipeline\evaluate_candidate.py --model training_pipeline\artifacts\candidate_v1 --test training_pipeline\data\processed\test.jsonl
```

Read `metrics.json` and `error_review.jsonl`. Do not deploy based on accuracy alone; inspect precision and recall for every risk label, especially false positives for `hidden_charges` and `penalty_clause`.

## Minimum data target

Start with at least 100 reviewer-approved clauses per risk label and 300+ `no_risk` clauses. Use documents from every agreement family you expect the model to support. A model trained only on loan agreements must not be presented as an insurance or investment expert.

## Deployment boundary

Only after test results are accepted should you decide whether to connect a candidate model to the application. That is intentionally a separate step and is not performed by this workspace.
