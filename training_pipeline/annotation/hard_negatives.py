"""Small explicitly synthetic challenge fixtures, never an evaluation benchmark."""

import hashlib
import json
from pathlib import Path

EXAMPLES = [
    ("The interest rate is fixed for the entire term.", "no_risk", True),
    ("No foreclosure or prepayment penalty will apply.", "no_risk", True),
    ("No processing fee or administrative charge is payable.", "no_risk", True),
    ("The APR remains fixed at eight percent for this term.", "no_risk", True),
    ("The agreement will not automatically renew.", "no_risk", True),
    ("Coverage has no waiting period for the listed benefits.", "no_risk", True),
    ("Hospital treatment is covered without exclusion for the stated illness.", "no_risk", True),
    ("The lender shall not modify the terms without your written consent.", "no_risk", True),
    ("No default penalty shall apply during the agreed grace period.", "no_risk", True),
    (
        "The insurer has no discretion to increase the premium during the policy term.",
        "no_risk",
        True,
    ),
    ("Service charges are waived for the full duration of this agreement.", "no_risk", True),
    ("The borrower may repay early without any additional fee.", "no_risk", True),
    ("A non-refundable processing fee is charged on disbursement.", "hidden_charges", False),
    ("The floating interest rate may rise following a benchmark reset.", "high_interest", False),
    ("A late payment penalty of five hundred rupees is payable.", "penalty_clause", False),
    ("The lender may repossess the collateral after default.", "foreclosure", False),
    (
        "The agreement automatically renews for twelve months unless cancelled.",
        "automatic_renewal",
        False,
    ),
    ("Hospital treatment for the listed condition is not covered.", "coverage_exclusion", False),
    ("A waiting period of ninety days applies before benefits commence.", "waiting_period", False),
    ("The insurer may modify the premium at its sole discretion.", "unilateral_change", False),
    ("The customer accepts unlimited liability for all consequential losses.", "other_risk", False),
]
FIXTURE_TIMESTAMP = "2026-01-01T00:00:00+00:00"


def build_rows():
    rows = []
    for text, label, negative in EXAMPLES:
        digest = hashlib.sha256(text.encode()).hexdigest()
        rows.append(
            dict(
                text=text,
                label=label,
                agreement_family="synthetic_challenge",
                source_type="synthetic",
                annotation_method="synthetic_curated",
                source_document_id="synthetic-" + digest,
                source_organization="RiskLens project synthetic fixture generator",
                source_url=None,
                retrieved_at=FIXTURE_TIMESTAMP,
                sha256=digest,
                is_hard_negative=negative,
            )
        )
    return rows


def write_fixtures(output):
    rows = build_rows()
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(json.dumps(row) + "\n" for row in rows))
    return rows


def main():
    rows = write_fixtures("training_pipeline/data/fixtures/hard_negatives.jsonl")
    print(
        f"Wrote {len(rows)} synthetic fixtures ({sum(r['is_hard_negative'] for r in rows)} hard negatives); not enough data for training."
    )


if __name__ == "__main__":
    main()
