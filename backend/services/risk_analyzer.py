"""One authoritative page -> evidence -> score -> summary analysis path."""
import re
from collections import Counter
from backend.schemas import AnalysisResult, Finding, ModelStatus, RuleMatch
from backend.taxonomy import TAXONOMY
from backend.services.document_classifier import classify_document
from backend.services.pdf import segment_pages
from backend.services.scoring import score_clauses, severity_for_score

MODEL_THRESHOLD = .65
SEVERITIES = {'low': 0, 'medium': 1, 'high': 2, 'critical': 3}


def rule_matches(text: str) -> list[RuleMatch]:
    matches = []
    for label, policy in TAXONOMY.items():
        patterns = list(policy['rule_patterns'])
        if label == 'high_interest':
            patterns.append(r'\b(?:APR|interest rate)\s*(?:of|is|at|:)?\s*(?:2[5-9]|[3-9]\d|100)(?:\.\d+)?\s*(?:%|percent)')
        for number, pattern in enumerate(patterns):
            for match in re.finditer(pattern, text, re.I):
                before = re.split(r'[.;!?]|\b(?:but|however|yet)\b', text[:match.start()], flags=re.I)[-1][-90:]
                after = text[match.end():match.end()+60]
                # "not covered" is positive exclusion evidence, not a negated rule.
                negated = re.search(r'\b(?:no|not|never|without|waived?|zero)\b[^.;!?]{0,80}$', before, re.I)
                negated_after = re.match(r'\s*(?:shall |will |does |do |is |are )?(?:not (?:apply|payable|charged)|waived|does not apply)', after, re.I)
                if negated or negated_after:
                    continue
                if any(item.category == label and item.start_offset == match.start() for item in matches):
                    continue
                matches.append(RuleMatch(rule=f'{label}_{number+1}', category=label, pattern=pattern, matched_text=match.group(), start_offset=match.start(), end_offset=match.end()))
    return matches


def analyze_pages(pages, filename, model) -> AnalysisResult:
    clauses = segment_pages(pages)
    status = model.status()
    predictions = []
    if status.model_loaded:
        try:
            predictions = model.predict([c.text for c in clauses])
            if len(predictions) != len(clauses):
                raise ValueError('Incomplete inference results')
            # Validate all outputs before accepting any model evidence.
            for clause, probabilities in zip(clauses, predictions):
                clause.__class__.model_validate({**clause.model_dump(), 'class_probabilities': probabilities})
        except Exception:
            predictions = []
            status = ModelStatus(load_error='Model inference failed; this analysis used rules only.')
    for index, clause in enumerate(clauses):
        clause.rule_matches = rule_matches(clause.text)
        categories = set(m.category for m in clause.rule_matches)
        model_category = None
        if predictions:
            probabilities = predictions[index]
            clause.class_probabilities = probabilities
            clause.model_label = max(probabilities, key=probabilities.get)
            clause.model_confidence = probabilities[clause.model_label]
            if clause.model_confidence >= MODEL_THRESHOLD and clause.model_label != 'no_risk':
                model_category = clause.model_label
            clause.disagreement = bool(categories and (clause.model_label not in categories)) or bool(model_category and categories and categories != {model_category})
        for category in sorted(categories | ({model_category} if model_category else set())):
            policy = TAXONOMY[category]
            ruled = category in categories
            inferred = category == model_category
            method = 'hybrid' if ruled and inferred else 'rule' if ruled else 'model'
            strength = min(1, max(.70, clause.model_confidence)+.10) if method == 'hybrid' else .70 if ruled else clause.model_confidence
            clause.findings.append(Finding(category=category, severity=policy['default_severity'], evidence_strength=strength, detection_method=method, explanation=policy['explanation_template'], recommendation=policy['recommendation_template']))
        if clause.findings:
            primary = max(clause.findings, key=lambda f: (SEVERITIES[f.severity], f.evidence_strength))
            clause.predicted_label = primary.category
            clause.severity = primary.severity
            clause.detection_method = primary.detection_method
            clause.explanation = primary.explanation
            clause.recommendation = primary.recommendation
        else:
            clause.explanation = TAXONOMY['no_risk']['explanation_template']
            clause.recommendation = TAXONOMY['no_risk']['recommendation_template']
            if predictions and clause.model_label != 'no_risk':
                clause.explanation = 'No rule evidence; model prediction is below the configured threshold. Review this uncertain clause.'
    scoring = score_clauses(clauses)
    classification = classify_document('\n'.join(p.text for p in pages))
    counts = dict(Counter(c.severity for c in clauses))
    counts = {key: counts.get(key, 0) for key in SEVERITIES}
    categories = dict(Counter(f.category for c in clauses for f in c.findings))
    count = len(clauses)
    risky = sum(bool(c.findings) for c in clauses)
    findings = [f for c in clauses for f in c.findings]
    actions = list(dict.fromkeys(f.recommendation for f in sorted(findings, key=lambda f: SEVERITIES[f.severity], reverse=True)))
    main = sorted(scoring.category_contributions, key=scoring.category_contributions.get, reverse=True)[:3]
    names = ', '.join(TAXONOMY[label]['display_name'] for label in main) or 'no configured material risks'
    summary = f'{classification.document_type.replace("_", " ").title()}: {scoring.score}/100 ({severity_for_score(scoring.score)}). {count} clauses reviewed; {counts["high"]+counts["critical"]} high/critical and {counts["medium"]} medium-risk clauses. Main evidence: {names}. {count-risky} clauses have no material finding; this is not a guarantee of safety.'
    text_pages = sum(bool(p.text.strip()) for p in pages)
    return AnalysisResult(filename=filename, classification=classification, page_count=len(pages), text_page_count=text_pages, clause_count=count, clauses=clauses, model_status=status, mode=status.mode, risk_score=scoring.score, overall_risk=severity_for_score(scoring.score), scoring=scoring, severity_distribution=counts, category_distribution=categories, health={'clause_coverage': 1.0, 'model_coverage': 1.0 if predictions else 0.0, 'evidence_coverage': 1.0 if findings else None, 'high_risk_density': (counts['high']+counts['critical'])/count, 'safe_clause_ratio': (count-risky)/count, 'extraction_quality': text_pages/len(pages), 'classification_strength': classification.classification_strength}, executive_summary=summary, recommended_actions=actions)
