"""Length-resistant triage heuristic; never a calibrated loss probability."""

from backend.schemas import ScoreBreakdown
from backend.taxonomy import TAXONOMY


def severity_for_score(score: float) -> str:
    return (
        "Low" if score < 30 else "Moderate" if score < 60 else "High" if score < 80 else "Critical"
    )


def score_clauses(clauses) -> ScoreBreakdown:
    categories = {}
    for clause in clauses:
        for finding in clause.findings:
            contribution = TAXONOMY[finding.category]["scoring_weight"] * finding.evidence_strength
            categories[finding.category] = max(categories.get(finding.category, 0), contribution)
    top = sorted(categories.values(), reverse=True)[:3]
    strongest = top[0] if top else 0
    mean = sum(top) / 3
    diversity = min(len(categories) / 5, 1)
    score = round(100 * (0.65 * strongest + 0.25 * mean + 0.10 * diversity), 1)
    return ScoreBreakdown(
        strongest_evidence=strongest,
        top_three_mean=mean,
        category_diversity=diversity,
        category_contributions=categories,
        score=score,
    )
