"""Transparent document classification; heuristic strength is not ML confidence."""

import re

from backend.schemas import DocumentClassification

SIGNALS = {
    "credit_card": ["credit card", "cardholder", "cash advance", "credit limit"],
    "insurance": ["insurance", "policyholder", "sum insured", "coverage", "premium", "insurer"],
    "loan": ["loan agreement", "borrower", "lender", "repayment", "principal amount", "emi"],
    "investment": ["investment", "shareholder", "equity", "shares", "securities"],
    "lease": ["lease", "tenant", "landlord", "monthly rent"],
    "other_financial": ["financial agreement", "bank account", "deposit account"],
}


def classify_document(text: str) -> DocumentClassification:
    evidence = {
        kind: [word for word in words if re.search(r"\b" + re.escape(word) + r"\b", text, re.I)]
        for kind, words in SIGNALS.items()
    }
    kind = max(evidence, key=lambda key: len(evidence[key]))
    matches = evidence[kind]
    if not matches:
        return DocumentClassification()
    total = sum(len(v) for v in evidence.values())
    return DocumentClassification(
        document_type=kind, classification_strength=round(len(matches) / total, 3), evidence=matches
    )
