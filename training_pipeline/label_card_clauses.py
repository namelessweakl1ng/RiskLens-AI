import json
import re
from pathlib import Path


INPUT = Path("training_pipeline/data/processed/card_clauses.jsonl")
OUTPUT = Path("training_pipeline/data/processed/card_labeled.jsonl")


LABEL_RULES = {
    "high_interest": [
        r"\bapr\b",
        r"annual percentage rate",
        r"interest rate",
        r"variable rate",
        r"prime rate",
        r"finance charge",
        r"periodic rate",
        r"interest charge",
    ],

    "hidden_charges": [
        r"annual fee",
        r"late fee",
        r"fee",
        r"charge",
        r"cash advance fee",
        r"balance transfer fee",
        r"transaction fee",
        r"foreign transaction",
        r"overlimit fee",
        r"service fee",
    ],

    "penalty_clause": [
        r"late payment",
        r"late fee",
        r"default",
        r"delinquen",
        r"penalty",
        r"penalty apr",
        r"penalty rate",
        r"failure to pay",
        r"minimum payment",
    ],

    "automatic_renewal": [
        r"automatically renew",
        r"automatic renewal",
        r"automatically renewed",
        r"renewal",
        r"continue until cancelled",
        r"continues unless",
        r"renewed unless",
    ],

    "unilateral_change": [
        r"we may change",
        r"we reserve the right",
        r"may change the terms",
        r"change.*terms",
        r"change.*conditions",
        r"modify.*agreement",
        r"amend.*agreement",
        r"at our discretion",
    ],
}


def classify_clause(text):
    text_lower = text.lower()

    matches = []

    for label, patterns in LABEL_RULES.items():
        score = 0

        for pattern in patterns:
            if re.search(pattern, text_lower):
                score += 1

        if score > 0:
            matches.append((label, score))

    if not matches:
        return "no_risk"

    # Select strongest matching category
    matches.sort(key=lambda x: x[1], reverse=True)

    return matches[0][0]


def main():

    if not INPUT.exists():
        raise SystemExit(f"Input file not found: {INPUT}")

    rows = []

    with INPUT.open("r", encoding="utf-8") as f:

        for line in f:

            if not line.strip():
                continue

            row = json.loads(line)

            text = str(row.get("text", "")).strip()

            if not text:
                continue

            label = classify_clause(text)

            rows.append({
                "text": text,
                "label": label,
                "agreement_family": row.get(
                    "agreement_family",
                    "cards"
                ),
                "source_file": row.get(
                    "source_file",
                    ""
                )
            })

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with OUTPUT.open("w", encoding="utf-8") as f:

        for row in rows:
            f.write(
                json.dumps(
                    row,
                    ensure_ascii=False
                ) + "\n"
            )

    from collections import Counter

    counts = Counter(
        row["label"]
        for row in rows
    )

    print("\nCARD DATASET LABELING COMPLETE")
    print("-" * 50)
    print(f"Total clauses: {len(rows)}")
    print()

    for label, count in counts.most_common():
        print(f"{label:25} {count}")

    print()
    print(f"Saved to: {OUTPUT}")


if __name__ == "__main__":
    main()