# Real-data training sources

Use only documents that are public, licensed for your use, or supplied with the owner's permission. Remove personal data before annotation. Every clause needs a human-reviewed label before it enters the training file.

| Agreement family | Suitable public source | Use in this project |
| --- | --- | --- |
| Credit-card agreements | CFPB Credit Card Agreement Database | Collect public agreements, extract clauses, and have a reviewer label fees, APR changes, default, and no-risk clauses. |
| Investment and equity agreements | SEC EDGAR filings and exhibits | Select public contract exhibits, then label provisions such as dilution, transfer limits, termination, and no-risk clauses. |
| Loans, insurance, leasing | Publicly available issuer templates or documents provided with permission | Use only versions that are legally shareable; label the clause meaning, not the company name. |

## Dataset contract

The trainer reads JSON Lines records with the following shape:

```json
{"text":"The lender may revise the interest rate at its discretion.","label":"high_interest","source":"human_review"}
```

Required labels: `hidden_charges`, `high_interest`, `penalty_clause`, `foreclosure`, `automatic_renewal`, `coverage_exclusion`, `waiting_period`, `unilateral_change`, and `no_risk`.

Keep a separate test set that is never used for training. Include documents from every agreement family you intend to support. Do not train from the application's own predictions without reviewer confirmation; that causes error reinforcement.
