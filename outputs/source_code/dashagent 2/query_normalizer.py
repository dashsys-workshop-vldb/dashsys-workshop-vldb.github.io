from __future__ import annotations

import re
from typing import Any


SMART_QUOTES = {
    "\u2018": "'",
    "\u2019": "'",
    "\u201a": "'",
    "\u201b": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u201e": '"',
    "\u201f": '"',
}

HYPHEN_VARIANTS = {
    "\u2010": "-",
    "\u2011": "-",
    "\u2012": "-",
    "\u2013": "-",
    "\u2014": "-",
    "\u2212": "-",
}

SYNONYM_PATTERNS = [
    (re.compile(r"\bdata\s+flows?\b", re.IGNORECASE), "dataflow"),
    (re.compile(r"\bdata-flows?\b", re.IGNORECASE), "dataflow"),
    (re.compile(r"\bdata-sets?\b", re.IGNORECASE), "dataset"),
    (re.compile(r"\bmerge-policy\b", re.IGNORECASE), "merge policy"),
    (re.compile(r"\bsegment\s+evaluation\s+jobs?\b", re.IGNORECASE), "segment job"),
    (re.compile(r"\brecord\s+success\b", re.IGNORECASE), "recordsuccess"),
    (re.compile(r"\bbatch\s+success\b", re.IGNORECASE), "batchsuccess"),
    (re.compile(r"\bprofile-enabled\b", re.IGNORECASE), "profile enabled"),
    (re.compile(r"\bsegment\s+audiences?\b", re.IGNORECASE), "segments"),
    (re.compile(r"\baudiences?(\s+connected\s+to)\b", re.IGNORECASE), r"segments\1"),
]

PLURAL_NORMALIZATIONS = {
    "audiences": "audience",
    "batches": "batch",
    "campaigns": "campaign",
    "categories": "category",
    "collections": "collection",
    "connectors": "connector",
    "datasets": "dataset",
    "definitions": "definition",
    "destinations": "destination",
    "fields": "field",
    "files": "file",
    "flows": "flow",
    "jobs": "job",
    "journeys": "journey",
    "policies": "policy",
    "properties": "property",
    "schemas": "schema",
    "segments": "segment",
    "tags": "tag",
    "targets": "target",
}


def normalize_query(query: str) -> dict[str, Any]:
    original = str(query)
    rewrites: list[str] = []
    cleaned = original

    for source, target in SMART_QUOTES.items():
        if source in cleaned:
            cleaned = cleaned.replace(source, target)
            if "smart_quotes->ascii" not in rewrites:
                rewrites.append("smart_quotes->ascii")
    for source, target in HYPHEN_VARIANTS.items():
        if source in cleaned:
            cleaned = cleaned.replace(source, target)
            if "hyphen_variants->hyphen" not in rewrites:
                rewrites.append("hyphen_variants->hyphen")

    collapsed = re.sub(r"\s+", " ", cleaned).strip()
    if collapsed != cleaned:
        rewrites.append("whitespace_normalized")
    normalized = apply_outside_quotes(collapsed, lambda text: apply_synonyms(text, rewrites))
    matching_text = build_matching_text(normalized, rewrites)
    return {
        "original": original,
        "normalized": normalized,
        "matching_text": matching_text,
        "rewrites": list(dict.fromkeys(rewrites)),
    }


def apply_synonyms(text: str, rewrites: list[str]) -> str:
    result = text
    for pattern, replacement in SYNONYM_PATTERNS:
        new_result, count = pattern.subn(replacement, result)
        if count:
            rewrites.append(f"{pattern.pattern}->{replacement}")
            result = new_result
    return result


def build_matching_text(text: str, rewrites: list[str]) -> str:
    lowered = text.lower()

    def replace_plural(match: re.Match[str]) -> str:
        word = match.group(0)
        return PLURAL_NORMALIZATIONS.get(word, word)

    singular = re.sub(
        r"\b(" + "|".join(re.escape(word) for word in sorted(PLURAL_NORMALIZATIONS, key=len, reverse=True)) + r")\b",
        replace_plural,
        lowered,
    )
    if singular != lowered:
        rewrites.append("important_plurals->singular")
    return re.sub(r"\s+", " ", singular).strip()


def apply_outside_quotes(text: str, fn: Any) -> str:
    parts = re.split(r"('(?:''|[^'])*'|\"(?:\\\"|[^\"])*\")", text)
    transformed = []
    for index, part in enumerate(parts):
        transformed.append(part if index % 2 else fn(part))
    return "".join(transformed)
