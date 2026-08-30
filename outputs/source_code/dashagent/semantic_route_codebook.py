from __future__ import annotations

import json
from typing import Any


CODEBOOK = {
    "DEF": "definition cue",
    "EXPLAIN": "explanation cue",
    "WHY": "why cue",
    "HOW_WORKS": "how-it-works cue",
    "COMPARE": "comparison cue",
    "LIST": "retrieval list cue",
    "SHOW": "retrieval show cue",
    "FIND": "retrieval find cue",
    "EXPORT": "retrieval export cue",
    "RETURN": "retrieval return cue",
    "COUNT": "count cue",
    "HOW_MANY": "how-many cue",
    "TOTAL": "total cue",
    "SCHEMA": "schema domain term",
    "SEGMENT": "segment domain term",
    "AUDIENCE": "audience domain term",
    "DATASET": "dataset domain term",
    "JOURNEY": "journey domain term",
    "CAMPAIGN": "campaign domain term",
    "TAG": "tag domain term",
    "AUDIT": "audit domain term",
    "MERGE_POLICY": "merge policy domain term",
    "DOMAIN_WITH_DEF_CUE": "domain term appears with definition cue",
    "MIXED_CONCEPT_AND_RETRIEVAL": "concept cue appears with retrieval or count cue",
}

PROSE_KEYS = {"reason", "explanation", "safety_notes", "final_route", "api_policy", "human_readable_reason"}


def render_codebook_report(payload: dict[str, Any]) -> str:
    codes = sorted(_collect_codes(payload))
    lines = ["# Semantic Route Codebook", ""]
    for code in codes:
        if code in CODEBOOK:
            lines.append(f"- {code} = {CODEBOOK[code]}")
    return "\n".join(lines)


def runtime_payload_is_compact(payload: dict[str, Any]) -> bool:
    return _is_compact(payload)


def estimate_compact_payload_savings(payload: dict[str, Any]) -> dict[str, int]:
    compact = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    verbose_payload = _expand_codes(payload)
    verbose = json.dumps(verbose_payload, sort_keys=True)
    return {
        "compact_tokens": max(1, len(compact) // 4),
        "verbose_tokens": max(2, len(verbose) // 4),
        "estimated_token_savings": max(0, len(verbose) // 4 - len(compact) // 4),
    }


def _is_compact(value: Any) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key) in PROSE_KEYS:
                return False
            if not _is_compact(item):
                return False
        return True
    if isinstance(value, list):
        return all(_is_compact(item) for item in value)
    if isinstance(value, str):
        return len(value) <= 240
    return True


def _collect_codes(value: Any) -> set[str]:
    codes: set[str] = set()
    if isinstance(value, dict):
        for item in value.values():
            codes.update(_collect_codes(item))
    elif isinstance(value, list):
        for item in value:
            codes.update(_collect_codes(item))
    elif isinstance(value, str) and value in CODEBOOK:
        codes.add(value)
    return codes


def _expand_codes(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _expand_codes(item) for key, item in value.items()}
    if isinstance(value, list):
        return [{"code": item, "meaning": CODEBOOK.get(item, item)} if isinstance(item, str) else _expand_codes(item) for item in value]
    return value
