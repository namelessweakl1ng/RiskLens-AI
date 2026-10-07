"""Provenance validation, duplicate clustering and source-grouped splits."""

import argparse
import hashlib
import json
import random
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urlparse

from backend.taxonomy import canonical_label

ANNOTATIONS = {
    "expert_reviewed",
    "human_reviewed",
    "project_curated",
    "synthetic_curated",
    "weak_label",
}
SOURCES = {"public_real", "licensed_real", "owner_provided", "synthetic"}
SPLITS = ("train", "validation", "test")


def normalize_text(text):
    text = unicodedata.normalize("NFKC", text)
    lines = [
        line
        for line in text.splitlines()
        if not re.fullmatch(r"\s*(?:page\s+)?\d+(?:\s+of\s+\d+)?\s*", line, re.I)
        and not line.strip().startswith("©")
    ]
    return re.sub(r"\s+", " ", " ".join(lines)).strip()


def validate_rows(rows):
    validated = []
    source_hashes = {}
    for index, original in enumerate(rows, 1):
        item = dict(original)
        item["text"] = normalize_text(str(item.get("text", "")))
        item["label"] = canonical_label(item.get("label", ""))
        if (
            not item["text"]
            or item.get("annotation_method") not in ANNOTATIONS
            or item.get("source_type") not in SOURCES
        ):
            raise ValueError(f"Row {index}: invalid text, annotation method or source type")
        if (
            not item.get("source_document_id")
            or not item.get("agreement_family")
            or not item.get("source_organization")
        ):
            raise ValueError(f"Row {index}: document, family and organization provenance required")
        if not re.fullmatch(r"[0-9a-f]{64}", item.get("sha256", "")):
            raise ValueError(f"Row {index}: source document SHA256 required")
        document = item["source_document_id"]
        if document in source_hashes and source_hashes[document] != item["sha256"]:
            raise ValueError(f"Row {index}: one source document ID cannot have conflicting hashes")
        source_hashes[document] = item["sha256"]
        try:
            timestamp = datetime.fromisoformat(item["retrieved_at"].replace("Z", "+00:00"))
            if timestamp.tzinfo is None:
                raise ValueError("Timestamp must include timezone")
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Row {index}: valid retrieval timestamp required") from exc
        if item["source_type"] == "synthetic":
            if item["annotation_method"] != "synthetic_curated" or item.get("source_url"):
                raise ValueError(
                    "Synthetic records must be synthetic_curated, with no invented source URL"
                )
        elif item["source_type"] == "public_real":
            url = urlparse(item.get("source_url") or "")
            if url.scheme != "https" or not url.hostname or url.username or url.password:
                raise ValueError(f"Row {index}: public source requires an HTTPS URL")
        if not isinstance(item.get("is_hard_negative"), bool):
            raise ValueError(f"Row {index}: is_hard_negative must be boolean")
        item["text_sha256"] = hashlib.sha256(item["text"].lower().encode()).hexdigest()
        validated.append(item)
    return validated


def near_duplicate(a, b):
    a, b = normalize_text(a).lower(), normalize_text(b).lower()
    if a == b:
        return True
    if min(len(a), len(b)) / max(len(a), len(b), 1) < 0.8:
        return False
    return SequenceMatcher(None, a, b, autojunk=False).ratio() >= 0.90


def duplicate_pairs(rows):
    # Token index avoids comparing every unrelated legal clause pair.
    index = defaultdict(set)
    for i, row in enumerate(rows):
        tokens = set(re.findall(r"\w+", row["text"].lower()))
        candidates = set().union(*(index[token] for token in tokens)) if tokens else set()
        for j in sorted(candidates):
            if near_duplicate(row["text"], rows[j]["text"]):
                yield j, i
        for token in tokens:
            index[token].add(i)


def assert_no_leakage(splits):
    seen = {}
    seen_hashes = {}
    all_rows = []
    owners = []
    for split in SPLITS:
        for row in splits[split]:
            document = row["source_document_id"]
            if document in seen and seen[document] != split:
                raise ValueError(f"Source document leaks across splits: {document}")
            seen[document] = split
            digest = row["sha256"]
            if digest in seen_hashes and seen_hashes[digest] != split:
                raise ValueError("Source document SHA256 leaks across splits")
            seen_hashes[digest] = split
            all_rows.append(row)
            owners.append(split)
    for a, b in duplicate_pairs(all_rows):
        if owners[a] != owners[b]:
            raise ValueError("Near-duplicate clauses leak across splits")


def prepare_splits(rows, seed=42):
    rows = validate_rows(rows)
    weak = sum(r["annotation_method"] == "weak_label" for r in rows)
    eligible = [r for r in rows if r["annotation_method"] != "weak_label"]
    parent = {r["source_document_id"]: r["source_document_id"] for r in eligible}

    def find(document):
        while parent[document] != document:
            parent[document] = parent[parent[document]]
            document = parent[document]
        return document

    def union(a, b):
        a, b = find(a), find(b)
        if a != b:
            parent[max(a, b)] = min(a, b)

    hash_owners = {}
    for row in eligible:
        digest = row["sha256"]
        if digest in hash_owners:
            union(row["source_document_id"], hash_owners[digest])
        hash_owners[digest] = row["source_document_id"]
    duplicates = set()
    near_count = 0
    for a, b in duplicate_pairs(eligible):
        union(eligible[a]["source_document_id"], eligible[b]["source_document_id"])
        if eligible[a]["text_sha256"] == eligible[b]["text_sha256"]:
            if eligible[a]["label"] != eligible[b]["label"]:
                raise ValueError(
                    "Conflicting labels for an identical clause; resolve annotation before splitting"
                )
            duplicates.add(b)
        else:
            near_count += 1
    unique = [row for i, row in enumerate(eligible) if i not in duplicates]
    groups = defaultdict(list)
    for row in unique:
        groups[find(row["source_document_id"])].append(row)
    if len(groups) < 3:
        raise ValueError("At least three independent source-document groups are required")
    grouped = list(groups.values())
    rng = random.Random(seed)
    rng.shuffle(grouped)
    grouped.sort(key=len, reverse=True)
    splits = {key: [] for key in SPLITS}
    targets = {"train": 0.70, "validation": 0.15, "test": 0.15}
    totals = Counter(row["label"] for row in unique)
    class_counts = {key: Counter() for key in SPLITS}
    for position, group in enumerate(grouped):
        remaining = len(grouped) - position
        empty = [key for key in SPLITS if not splits[key]]
        candidates = empty if remaining == len(empty) else list(SPLITS)
        additions = Counter(row["label"] for row in group)
        # Minimize normalized target deficits, including class balance.
        split = min(
            candidates,
            key=lambda key: (
                (len(splits[key]) + len(group)) / (len(unique) * targets[key])
                + sum(
                    (class_counts[key][label] + count) / (totals[label] * targets[key])
                    for label, count in additions.items()
                )
                / len(additions)
            ),
        )
        splits[split].extend(group)
        class_counts[split].update(additions)
    assert_no_leakage(splits)
    report = {
        "seed": seed,
        "input_clauses": len(rows),
        "total_clauses": len(unique),
        "examples_per_class": dict(totals),
        "examples_by_source_type": dict(Counter(r["source_type"] for r in unique)),
        "examples_by_document_family": dict(Counter(r["agreement_family"] for r in unique)),
        "hard_negative_count": sum(r["is_hard_negative"] for r in unique),
        "weak_label_count": weak,
        "duplicates_removed": len(duplicates),
        "near_duplicate_pairs_grouped": near_count,
        "document_groups": len(groups),
        "synthetic_ratio": sum(r["source_type"] == "synthetic" for r in unique) / len(unique),
        "split_counts": {key: len(splits[key]) for key in SPLITS},
        "split_class_distribution": {key: dict(class_counts[key]) for key in SPLITS},
    }
    return {**splits, "report": report}


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    result = prepare_splits(read_jsonl(args.input), args.seed)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    for key in SPLITS:
        (output / f"{key}.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in result[key])
        )
    (output / "dataset_report.json").write_text(json.dumps(result["report"], indent=2) + "\n")
    print(json.dumps(result["report"], indent=2))


if __name__ == "__main__":
    main()
