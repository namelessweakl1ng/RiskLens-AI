"""Authoritative labels, presentation, rules and scoring policy."""

import json
from pathlib import Path

TAXONOMY = json.loads(Path(__file__).with_name("taxonomy.json").read_text())
LABELS = tuple(TAXONOMY)
ALIASES = {
    alias.lower().replace(" ", "_"): label
    for label, item in TAXONOMY.items()
    for alias in [label, *item["aliases"]]
}


def canonical_label(value: str) -> str:
    key = str(value).strip().lower().replace(" ", "_")
    if key not in ALIASES:
        raise ValueError(f"Unknown risk label: {value}")
    return ALIASES[key]
