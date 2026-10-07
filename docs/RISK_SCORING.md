# Explainable triage score and document health

This is a **heuristic triage score**, not a probability of loss or a validated
legal opinion. It contains no vanilla FinBERT sentiment contribution.

Each unique material category receives its strongest clause contribution:

`category = taxonomy_weight × evidence_strength`

- Rule-only evidence strength: **0.70**, an explicit scoring policy.
- Accepted model-only evidence: genuine top-class softmax probability.
- Model/rule agreement on a category: `min(1, max(0.70, probability) + 0.10)`.
- No material finding / no_risk: zero contribution.
- Model-only predictions below **0.65** are visible as uncertain but do not score.
- High/critical weights are 1.00; medium 0.65; no_risk 0.00. All weights live in
  the authoritative taxonomy. These are policy weights, not learned coefficients.

A clause can have several category findings. Model/rule disagreement is exposed,
and evidence is retained rather than overwritten. One accepted classifier label
never erases other rule categories. Repeated matches or duplicate clauses do not
increase a category contribution.

Let S be the largest category contribution; T the mean of the top three category
contributions (pad missing entries with zero); D = min(material categories / 5, 1).

`score = round(100 × (0.65 × S + 0.25 × T + 0.10 × D), 1)`

All inputs are in [0,1], so score remains [0,100]. No category means zero. A weak
prediction does not dominate; independent supported categories increase breadth,
while repetition has no additive effect. Formula version is risklens-triage-v1
and every component is returned for inspection. This capped strongest/category
method deliberately favors material clauses rather than document length.

Score levels: 0–29 Low; 30–59 Moderate; 60–79 High; 80–100 Critical. Clause default
severity describes the category; document severity describes the aggregate score,
so one critical-category clause need not make the overall document Critical.

## Transparent health definitions

All indicators are ratios displayed as percentages, never random numbers.

| Indicator | Numerator / denominator |
| --- | --- |
| Clause coverage | Completed clause analyses / extracted clauses |
| Model coverage | Valid model-inferred clauses / analyzed clauses |
| Evidence coverage | Material findings with explicit rule/model support / material findings |
| High-risk density | High or critical primary clauses / analyzed clauses |
| No-finding ratio (safe-clause ratio) | Clauses without material findings / analyzed clauses |
| Extraction quality | Text-bearing pages / total pages |
| Classification strength | Winning-family matched signals / all matched signals |

This pipeline rejects zero analyzable clauses, so normal clause denominators are
nonzero. When no material finding exists, evidence coverage is unavailable rather
than fabricated 100%. Legacy health fields are unavailable because their original
inputs cannot be recovered. Model coverage is zero in rule-only mode. Clause and
evidence coverage may be 100% by construction in a completed analysis; neither
measures prediction accuracy. No-finding ratio does not certify safety; text-page
coverage does not measure extraction fidelity; classification strength is not ML
confidence. Model/rule agreement shown by the UI is descriptive, not accuracy.
