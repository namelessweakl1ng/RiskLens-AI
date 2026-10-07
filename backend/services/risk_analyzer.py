import re
from functools import lru_cache

from transformers import pipeline
from backend.services.fine_tuned_risk_model import classify_risk_clause


# ==========================================================
# FINBERT MODEL
# ==========================================================

@lru_cache(maxsize=1)
def get_finbert():

    print("Loading FinBERT model...")

    return pipeline(
        "sentiment-analysis",
        model="ProsusAI/finbert",
        tokenizer="ProsusAI/finbert"
    )


# ==========================================================
# RISK RULES
# ==========================================================

RISK_RULES = {

    "Hidden Charges": {
        "severity": "High",
        "weight": 18,
        "patterns": [
            "processing fee",
            "documentation charge",
            "extra fee",
            "processing fees",
            "stamping charges"
        ],
        "explanation":
            "Additional charges can increase the total financial obligation beyond the expected amount."
    },

    "High Interest Risk": {
        "severity": "High",
        "weight": 20,
        "patterns": [
            "high interest",
            "interest rate may vary",
            "floating interest rate",
            "variable interest rate",
            "interest shall be revised",
            "interest rate revised",
            "rate subject to change"
        ],
        "explanation":
            "Variable or revisable interest terms may increase repayment costs."
    },

    "Penalty Clause": {
        "severity": "Medium",
        "weight": 12,
        "patterns": [
            "late payment penalty",
            "penalty shall apply",
            "penal interest",
            "late fee",
            "default interest",
            "penalty charge",
            "additional penalty"
        ],
        "explanation":
            "Missed or delayed payments may result in additional financial penalties."
    },

    "Foreclosure Risk": {
        "severity": "High",
        "weight": 22,
        "patterns": [
            "foreclosure",
            "property may be repossessed",
            "repossession",
            "seizure of property",
            "security may be enforced",
            "collateral may be sold"
        ],
        "explanation":
            "Default may result in enforcement against assets, collateral, or property."
    },

    "Automatic Renewal": {
        "severity": "Medium",
        "weight": 10,
        "patterns": [
            "automatically renewed",
            "automatic renewal",
            "renewal shall continue",
            "policy will renew automatically"
        ],
        "explanation":
            "Automatic renewal may create continued financial obligations unless cancelled."
    },

    "Coverage Exclusion": {
        "severity": "High",
        "weight": 18,
        "patterns": [
            "not covered",
            "excluded from coverage",
            "coverage shall not include",
            "claim will not be payable",
            "policy exclusion",
            "exclusions apply"
        ],
        "explanation":
            "Important exclusions may prevent the user from receiving expected insurance benefits."
    },

    "Waiting Period": {
        "severity": "Medium",
        "weight": 10,
        "patterns": [
            "waiting period",
            "claim not payable during",
            "benefits shall commence after",
            "coverage begins after"
        ],
        "explanation":
            "Benefits may not be available immediately after purchasing the policy."
    },

    "Unilateral Change": {
        "severity": "High",
        "weight": 16,
        "patterns": [
            "right to modify",
            "may modify the terms",
            "terms may be changed",
            "without prior notice",
            "at its sole discretion"
        ],
        "explanation":
            "One party may be able to change important terms, potentially creating uncertainty."
    }
}

# Labels expected from training/train_risk_classifier.py. The label names are
# intentionally separate from presentation labels so the training contract is
# stable even if the UI wording changes.
MODEL_LABEL_TO_RISK = {
    "hidden_charges": "Hidden Charges",
    "high_interest": "High Interest Risk",
    "penalty_clause": "Penalty Clause",
    "foreclosure": "Foreclosure Risk",
    "automatic_renewal": "Automatic Renewal",
    "coverage_exclusion": "Coverage Exclusion",
    "waiting_period": "Waiting Period",
    "unilateral_change": "Unilateral Change",
}

REVIEW_ACTIONS = {
    "Hidden Charges": "Ask for the complete fee schedule and the final amount payable.",
    "High Interest Risk": "Confirm the current rate, how often it can change, and the maximum rate allowed.",
    "Penalty Clause": "Check the grace period and the exact cost of a late or missed payment.",
    "Foreclosure Risk": "Understand what asset is at risk and the steps required before enforcement.",
    "Automatic Renewal": "Check the cancellation deadline and whether you will receive a renewal notice.",
    "Coverage Exclusion": "Confirm whether this exclusion affects the protection you are buying.",
    "Waiting Period": "Check when benefits begin and what is excluded before that date.",
    "Unilateral Change": "Ask which terms can change, when, and how you will be notified.",
}

PROTECTION_SIGNALS = {
    "fixed interest rate": "The agreement refers to a fixed interest rate.",
    "prepayment without penalty": "The agreement allows prepayment without a stated penalty.",
    "no foreclosure charges": "The agreement states that foreclosure charges do not apply.",
    "grace period": "The agreement refers to a payment grace period.",
    "free look period": "The agreement refers to a free-look period.",
    "right to cancel": "The agreement refers to a cancellation right.",
    "renewal notice": "The agreement refers to a renewal notice.",
}


# ==========================================================
# TEXT CLEANING
# ==========================================================

def clean_text(text):

    text = re.sub(r"\s+", " ", text)

    return text.strip()


# ==========================================================
# SENTENCE / CLAUSE EXTRACTION
# ==========================================================

def split_into_clauses(text):

    clauses = re.split(
        r"(?<=[.!?])\s+|\n+",
        text
    )

    cleaned = []

    for clause in clauses:

        clause = clean_text(clause)

        if len(clause) >= 15:
            cleaned.append(clause)

    return cleaned


# ==========================================================
# FINBERT ANALYSIS
# ==========================================================

def analyze_with_finbert(text):

    finbert = get_finbert()

    # FinBERT works better with manageable chunks
    max_length = 450

    chunks = []

    for i in range(0, len(text), max_length):
        chunk = text[i:i + max_length].strip()

        if len(chunk) > 20:
            chunks.append(chunk)

    if not chunks:

        return {
            "label": "neutral",
            "confidence": 0.0,
            "distribution": {
                "positive": 0.0,
                "negative": 0.0,
                "neutral": 1.0
            },
            "negative_ratio": 0.0,
            "analyzed_chunks": 0
        }

    # Limit chunks to prevent very long documents
    chunks = chunks[:30]

    results = finbert(chunks)

    counts = {
        "positive": 0,
        "negative": 0,
        "neutral": 0
    }

    confidence_totals = {
        "positive": 0.0,
        "negative": 0.0,
        "neutral": 0.0
    }

    for result in results:

        label = result["label"].lower()
        score = float(result["score"])

        if label in counts:
            counts[label] += 1
            confidence_totals[label] += score

    total = len(results)

    distribution = {}

    for label in counts:

        distribution[label] = round(
            counts[label] / total,
            3
        )

    dominant_label = max(
        counts,
        key=counts.get
    )

    dominant_confidence = 0.0

    if counts[dominant_label] > 0:

        dominant_confidence = (
            confidence_totals[dominant_label]
            /
            counts[dominant_label]
        )

    return {
        "label": dominant_label,
        "confidence": round(
            dominant_confidence,
            3
        ),
        "distribution": distribution,
        "negative_ratio": round(
            distribution["negative"],
            3
        ),
        "analyzed_chunks": total
    }


# ==========================================================
# ANALYZE INDIVIDUAL CLAUSE WITH FINBERT
# ==========================================================

def analyze_clause_with_finbert(clause):

    try:

        finbert = get_finbert()

        result = finbert(
            clause[:500]
        )[0]

        return {
            "label": result["label"].lower(),
            "confidence": round(
                float(result["score"]),
                3
            )
        }

    except Exception:

        return {
            "label": "neutral",
            "confidence": 0.0
        }


# ==========================================================
# RULE-BASED RISK DETECTION
# ==========================================================

def detect_rule_based_risks(text):

    text_lower = text.lower()

    detected_risks = {}

    all_risk_items = []

    clauses = split_into_clauses(text)

    for risk_type, rule in RISK_RULES.items():

        matches = []

        for pattern in rule["patterns"]:

            if pattern in text_lower:

                # Find the most relevant clause
                matched_clause = None

                for clause in clauses:

                    if pattern in clause.lower():

                        matched_clause = clause
                        break

                if matched_clause is None:

                    matched_clause = (
                        f"Detected pattern: {pattern}"
                    )

                # Avoid duplicate clauses
                duplicate = any(
                    item["clause"].lower()
                    ==
                    matched_clause.lower()
                    for item in matches
                )

                if duplicate:
                    continue

                # FinBERT context analysis
                ai_analysis = analyze_clause_with_finbert(
                    matched_clause
                )

                # Hybrid severity score
                hybrid_score = rule["weight"]

                if ai_analysis["label"] == "negative":

                    hybrid_score += (
                        ai_analysis["confidence"]
                        * 10
                    )

                elif ai_analysis["label"] == "neutral":

                    hybrid_score += 2

                # Cap per-risk contribution
                hybrid_score = min(
                    round(hybrid_score, 2),
                    30
                )

                risk_item = {

                    "risk_type": risk_type,

                    "severity": rule["severity"],

                    "clause": matched_clause,

                    "matched_pattern": pattern,

                    "explanation": rule["explanation"],

                    "review_action": REVIEW_ACTIONS[risk_type],

                    "rule_weight": rule["weight"],

                    "hybrid_score": hybrid_score,

                    "ai_analysis": ai_analysis
                }

                matches.append(
                    risk_item
                )

                all_risk_items.append(
                    risk_item
                )

        if matches:

            detected_risks[
                risk_type
            ] = matches

    # A reviewer-trained classifier can surface clauses beyond the explicit
    # keyword list. It is optional: until a model artifact is deployed this
    # call returns None and the transparent rule-only behaviour is unchanged.
    detected_model_clauses = set()
    for clause in clauses:
        prediction = classify_risk_clause(clause)
        if not prediction or prediction["confidence"] < 0.70:
            continue

        risk_type = MODEL_LABEL_TO_RISK.get(prediction["label"])
        if not risk_type or clause.lower() in detected_model_clauses:
            continue

        already_found = any(
            item["risk_type"] == risk_type and item["clause"].lower() == clause.lower()
            for item in all_risk_items
        )
        if already_found:
            continue

        rule = RISK_RULES[risk_type]
        risk_item = {
            "risk_type": risk_type,
            "severity": rule["severity"],
            "clause": clause,
            "matched_pattern": "fine_tuned_classifier",
            "explanation": rule["explanation"],
            "review_action": REVIEW_ACTIONS[risk_type],
            "rule_weight": rule["weight"],
            "hybrid_score": min(round(rule["weight"] + prediction["confidence"] * 10, 2), 30),
            "ai_analysis": {"label": "domain_risk", "confidence": prediction["confidence"]},
            "detection_method": "fine_tuned_clause_classifier",
        }
        detected_risks.setdefault(risk_type, []).append(risk_item)
        all_risk_items.append(risk_item)
        detected_model_clauses.add(clause.lower())

    return (
        detected_risks,
        all_risk_items
    )


# ==========================================================
# HYBRID RISK SCORING
# ==========================================================

def calculate_hybrid_risk_score(
    all_risks,
    finbert_analysis
):

    if not all_risks:

        # Even with no explicit rules, negative
        # financial language can indicate some caution.
        base_score = (
            finbert_analysis["negative_ratio"]
            * 15
        )

        return round(
            min(base_score, 20),
            1
        )

    # ------------------------------------------
    # 1. RULE-BASED COMPONENT
    # ------------------------------------------

    rule_score = sum(
        risk["hybrid_score"]
        for risk in all_risks
    )

    # Prevent many repeated clauses from
    # instantly producing 100.
    rule_score = min(
        rule_score,
        70
    )

    # ------------------------------------------
    # 2. SEVERITY DISTRIBUTION
    # ------------------------------------------

    high_count = sum(
        1
        for risk in all_risks
        if risk["severity"] == "High"
    )

    medium_count = sum(
        1
        for risk in all_risks
        if risk["severity"] == "Medium"
    )

    low_count = sum(
        1
        for risk in all_risks
        if risk["severity"] == "Low"
    )

    severity_bonus = (
        high_count * 4
        +
        medium_count * 2
        +
        low_count * 1
    )

    severity_bonus = min(
        severity_bonus,
        15
    )

    # ------------------------------------------
    # 3. FINBERT DOCUMENT CONTEXT
    # ------------------------------------------

    finbert_component = (
        finbert_analysis["negative_ratio"]
        * 15
    )

    if (
        finbert_analysis["label"]
        ==
        "negative"
    ):

        finbert_component += (
            finbert_analysis["confidence"]
            * 5
        )

    finbert_component = min(
        finbert_component,
        15
    )

    # ------------------------------------------
    # FINAL SCORE
    # ------------------------------------------

    final_score = (
        rule_score
        +
        severity_bonus
        +
        finbert_component
    )

    final_score = min(
        round(final_score, 1),
        100
    )

    return final_score


# ==========================================================
# RISK LEVEL
# ==========================================================

def get_risk_level(score):

    if score >= 70:
        return "High"

    if score >= 35:
        return "Medium"

    return "Low"


def build_decision_brief(text, all_risks, risk_score):
    """Create a plain-English decision aid, not an approval or legal opinion."""
    risk_types = list(dict.fromkeys(risk["risk_type"] for risk in all_risks))
    pros = [message for phrase, message in PROTECTION_SIGNALS.items() if phrase in text.lower()]
    if not pros:
        pros = ["No explicit customer protections were identified automatically; confirm the benefits in the original agreement."]

    cons = [
        next(risk["explanation"] for risk in all_risks if risk["risk_type"] == risk_type)
        for risk_type in risk_types
    ]
    recommendations = [REVIEW_ACTIONS[risk_type] for risk_type in risk_types]

    if risk_score >= 70:
        suitability = "Proceed only after clarification"
        summary = "Several material terms need to be confirmed in writing before you make a decision."
    elif risk_score >= 35:
        suitability = "Proceed after checking the flagged terms"
        summary = "The agreement may be workable, but the highlighted items could affect cost or coverage."
    else:
        suitability = "Potentially suitable based on detected terms"
        summary = "No major high-priority terms were detected automatically; still verify the commercial details."

    return {
        "suitability": suitability,
        "summary": summary,
        "pros": pros[:3],
        "cons": cons[:4],
        "recommendations": recommendations[:4],
        "disclaimer": "This is an informational review, not legal, investment, insurance, or lending advice.",
    }


# ==========================================================
# MAIN ANALYSIS FUNCTION
# ==========================================================

def analyze_document(text):

    text = clean_text(text)

    # ------------------------------------------
    # FINBERT DOCUMENT ANALYSIS
    # ------------------------------------------

    finbert_analysis = analyze_with_finbert(
        text
    )

    # ------------------------------------------
    # RULE-BASED ANALYSIS
    # ------------------------------------------

    (
        detected_risks,
        all_risks
    ) = detect_rule_based_risks(
        text
    )

    # ------------------------------------------
    # HYBRID SCORE
    # ------------------------------------------

    risk_score = calculate_hybrid_risk_score(
        all_risks,
        finbert_analysis
    )

    risk_level = get_risk_level(
        risk_score
    )

    decision_brief = build_decision_brief(text, all_risks, risk_score)

    # ------------------------------------------
    # RISK COUNTS
    # ------------------------------------------

    high_risks = sum(
        1
        for risk in all_risks
        if risk["severity"] == "High"
    )

    medium_risks = sum(
        1
        for risk in all_risks
        if risk["severity"] == "Medium"
    )

    low_risks = sum(
        1
        for risk in all_risks
        if risk["severity"] == "Low"
    )

    # ------------------------------------------
    # RETURN RESULT
    # ------------------------------------------

    return {

        "risk_score": risk_score,

        "risk_level": risk_level,

        "total_risks": len(
            all_risks
        ),

        "high_risks": high_risks,

        "medium_risks": medium_risks,

        "low_risks": low_risks,

        "risk_summary": {

            "risk_score": risk_score,

            "overall_risk_level": risk_level,

            "total_risks": len(
                all_risks
            ),

            "high_risks": high_risks,

            "medium_risks": medium_risks,

            "low_risks": low_risks
        },

        "finbert_document_analysis":
            finbert_analysis,

        "detected_risks":
            detected_risks,

        "decision_brief": decision_brief,

        "analysis_method": {
            "rule_based_detection": True,
            "finbert_financial_context": True,
            "hybrid_scoring": True
        }
    }
