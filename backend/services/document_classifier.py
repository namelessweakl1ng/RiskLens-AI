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
    top = max(map(len, evidence.values()))
    if not top:
        return DocumentClassification()
    candidates = [kind for kind, matches in evidence.items() if len(matches) == top]
    total = sum(len(v) for v in evidence.values())
    if len(candidates) > 1:
        return DocumentClassification(
            classification_strength=round(top / total, 3),
            evidence=sorted({word for kind in candidates for word in evidence[kind]}),
            candidate_types=candidates,
        )
    kind = candidates[0]
    matches = evidence[kind]
    return DocumentClassification(
        document_type=kind,
        classification_strength=round(len(matches) / total, 3),
        evidence=matches,
        candidate_types=[kind],
    )
