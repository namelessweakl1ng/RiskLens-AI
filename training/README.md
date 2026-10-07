# Fine-tuning the contract-risk classifier

The existing FinBERT sentiment model is not a contractual-risk classifier. Train this classifier on clauses reviewed by a qualified financial or insurance reviewer; do not train it from rule matches or unverified PDFs.

1. Create `training/data/risk_clauses.jsonl`. Each line must have `text` and `label`. Use the exact risk labels represented in `backend/services/risk_analyzer.py`, plus `no_risk`.
2. Keep a balanced hold-out test set outside this file. Include ordinary clauses that are not risks so the model learns to avoid false positives.
3. From the project root, run `venv\Scripts\python training\train_risk_classifier.py --data training\data\risk_clauses.jsonl`.
4. The saved model is automatically used by the API at `backend/models/contract-risk-classifier`. Remove or rename that folder to revert to the transparent rule-only fallback.

Recommended minimum: 100 reviewed examples per label, including `no_risk`. Before deployment, measure precision and recall on a separate, reviewer-labeled set and select a confidence threshold appropriate to the document type and risk appetite.

Example JSONL record:

```json
{"text":"The lender may revise the interest rate at its discretion.","label":"high_interest"}
```
