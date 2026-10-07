def classify_document(text):

    # Convert text to lowercase
    text = text.lower()

    # -----------------------------------------
    # FINANCIAL / LOAN KEYWORDS
    # -----------------------------------------

    financial_keywords = [

        "loan agreement",
        "borrower",
        "lender",
        "interest rate",
        "emi",
        "equated monthly installment",
        "repayment",
        "principal amount",
        "processing fee",
        "late payment",
        "default",
        "credit facility",
        "loan tenure"

    ]

    # -----------------------------------------
    # INSURANCE KEYWORDS
    # -----------------------------------------

    insurance_keywords = [

        "insurance policy",
        "policyholder",
        "insured",
        "premium",
        "sum insured",
        "coverage",
        "claim",
        "waiting period",
        "pre-existing disease",
        "exclusions",
        "policy term",
        "deductible"

    ]

    # -----------------------------------------
    # COUNT FINANCIAL KEYWORDS
    # -----------------------------------------

    financial_score = 0

    for keyword in financial_keywords:

        if keyword in text:
            financial_score += 1

    # -----------------------------------------
    # COUNT INSURANCE KEYWORDS
    # -----------------------------------------

    insurance_score = 0

    for keyword in insurance_keywords:

        if keyword in text:
            insurance_score += 1

    # -----------------------------------------
    # CLASSIFICATION
    # -----------------------------------------

    if financial_score == 0 and insurance_score == 0:

        document_type = "UNKNOWN"

    elif financial_score > insurance_score:

        document_type = "FINANCIAL_CONTRACT"

    elif insurance_score > financial_score:

        document_type = "INSURANCE_POLICY"

    else:

        document_type = "MIXED_DOCUMENT"

    # -----------------------------------------
    # CONFIDENCE CALCULATION
    # -----------------------------------------

    total_score = financial_score + insurance_score

    if total_score == 0:

        confidence = 0

    else:

        highest_score = max(
            financial_score,
            insurance_score
        )

        confidence = round(
            (highest_score / total_score) * 100,
            2
        )

    # -----------------------------------------
    # RETURN RESULT
    # -----------------------------------------

    return {

        "document_type": document_type,

        "confidence": confidence,

        "financial_keyword_score": financial_score,

        "insurance_keyword_score": insurance_score

    }