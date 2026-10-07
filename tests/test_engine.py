import pytest


def engine(text, probabilities=None):
    from backend.schemas import Page, ModelStatus
    from backend.services.risk_analyzer import analyze_pages
    class Predictor:
        def status(self):
            return ModelStatus(model_loaded=probabilities is not None, mode='hybrid' if probabilities else 'rule_only', labels=list(probabilities or {}))
        def predict(self, texts):
            return [probabilities for _ in texts] if probabilities else []
    return analyze_pages([Page(page_number=1, text=text)], 'agreement.pdf', Predictor())


def test_taxonomy_and_aliases():
    from backend.taxonomy import TAXONOMY, canonical_label
    assert set(TAXONOMY) == {'hidden_charges','high_interest','penalty_clause','foreclosure','automatic_renewal','coverage_exclusion','waiting_period','unilateral_change','other_risk','no_risk'}
    assert canonical_label('High Interest Risk') == 'high_interest'
    assert canonical_label('safe') == 'no_risk'


@pytest.mark.parametrize('text', [
    'The interest rate is fixed for the entire term.',
    'No foreclosure or prepayment penalty will apply.',
    'No processing fee or service charge is payable.',
    'The agreement will not automatically renew.',
    'There is no waiting period for coverage.',
    'The lender shall not modify the terms without consent.',
    'No default penalty shall apply to this account.',
    'The APR is fixed at 8 percent for this term.',
    'The insurer does not exclude hospital coverage.',
])
def test_hard_negatives(text):
    result = engine(text)
    assert result.risk_score == 0
    assert all(c.model_confidence is None for c in result.clauses)
    assert all(c.predicted_label == 'no_risk' for c in result.clauses)


def test_rule_evidence_has_no_ml_confidence():
    result = engine('A processing fee of 100 rupees is payable on disbursement.')
    assert result.mode == 'rule_only'
    clause = result.clauses[0]
    assert clause.predicted_label == 'hidden_charges'
    assert clause.rule_matches and clause.rule_matches[0].matched_text
    assert clause.model_confidence is None
    assert clause.detection_method == 'rule'
    assert result.risk_score > 0


def test_duplicate_risks_do_not_inflate_score():
    text = 'The lender may repossess the collateral after default.'
    assert engine(text).risk_score == engine((text+' ')*20).risk_score


def test_model_rule_agreement_strength_and_probabilities():
    from backend.taxonomy import TAXONOMY
    probs = {label: .01 for label in TAXONOMY}
    probs['hidden_charges'] = .91
    result = engine('A processing fee of 100 rupees is payable.', probs)
    clause = result.clauses[0]
    assert clause.detection_method == 'hybrid'
    assert clause.model_confidence == pytest.approx(.91)
    assert sum(clause.class_probabilities.values()) == pytest.approx(1)
    assert result.risk_score > engine(clause.text).risk_score


def test_model_disagreement_is_explicit():
    from backend.taxonomy import TAXONOMY
    probs = {label: .001 for label in TAXONOMY}
    probs['no_risk'] = .991
    clause = engine('A processing fee of 100 rupees is payable.', probs).clauses[0]
    assert clause.disagreement
    assert clause.predicted_label == 'hidden_charges'
    assert clause.model_label == 'no_risk'


def test_weak_prediction_does_not_dominate():
    from backend.taxonomy import TAXONOMY
    probs = {label: .08 for label in TAXONOMY}
    probs['no_risk'] = .08
    probs['high_interest'] = .28
    assert engine('The parties acknowledge the signed agreement.', probs).risk_score == 0


def test_score_thresholds():
    from backend.services.scoring import severity_for_score
    assert [severity_for_score(x) for x in [0,29,30,59,60,79,80,100]] == ['Low','Low','Moderate','Moderate','High','High','Critical','Critical']


def test_unavailable_model_is_cached_and_honest():
    from backend.services.fine_tuned_risk_model import RiskModel
    model = RiskModel(None)
    assert model.status().mode == 'rule_only'
    assert not model.status().model_loaded
    assert model.predict(['A processing fee applies.']) == []
    assert model.status().model_loaded is False


def test_pages_and_semicolon_segmentation():
    from backend.services.pdf import segment_pages
    from backend.schemas import Page
    clauses = segment_pages([Page(page_number=2, text='1. Payment terms\nA processing fee is payable; the agreement automatically renews each year.')])
    assert len(clauses) >= 2
    assert all(c.page_number == 2 for c in clauses)
    assert all(c.start_offset is not None for c in clauses)


def test_negation_stops_at_contrasting_conjunction():
    result = engine('No processing fee applies, but an administrative fee is payable.')
    assert result.clauses[0].predicted_label == 'hidden_charges'
    assert [m.matched_text.lower() for m in result.clauses[0].rule_matches] == ['administrative fee']


def test_invalid_probability_distribution_falls_back_explicitly():
    result = engine('A processing fee is payable.', {'hidden_charges': .9})
    assert result.mode == 'rule_only'
    assert result.model_status.load_error.startswith('Model inference failed')
    assert result.clauses[0].model_confidence is None
