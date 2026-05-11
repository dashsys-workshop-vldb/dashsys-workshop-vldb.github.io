from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .answer_templates import classify_answer_family
from .config import Config, DEFAULT_CONFIG


STYLE_FLAGS = [
    "count_first",
    "list_first",
    "evidence_caveat",
    "discrepancy_wording",
    "dry_run_unavailable_wording",
    "timestamp_format",
]


def mine_answer_style_patterns(config: Config | None = None) -> dict[str, Any]:
    cfg = config or DEFAULT_CONFIG
    patterns: dict[str, dict[str, Any]] = {}
    if not cfg.data_json_path.exists():
        return patterns
    try:
        examples = json.loads(cfg.data_json_path.read_text(encoding="utf-8"))
    except Exception:
        return patterns
    for example in examples if isinstance(examples, list) else []:
        query = str(example.get("query") or "")
        answer = str(example.get("answer") or "")
        if not query or not answer:
            continue
        family = classify_answer_family(query)
        bucket = patterns.setdefault(family, {flag: 0 for flag in STYLE_FLAGS} | {"examples": 0})
        bucket["examples"] += 1
        lowered = answer.lower()
        if lowered.startswith(("there are", "there is", "based on the api response provided, there")) or re.match(r"^based on .*?\b\d+\b", lowered):
            bucket["count_first"] += 1
        if lowered.startswith(("based on", "the matching", "the sandbox has", "there are")):
            bucket["list_first"] += 1
        if any(token in lowered for token in ["based on the evidence", "based on the api response", "available evidence", "response appears to be truncated"]):
            bucket["evidence_caveat"] += 1
        if any(token in lowered for token in ["discrepancy", "does not match", "rather than", "but the api response"]):
            bucket["discrepancy_wording"] += 1
        if any(token in lowered for token in ["requires live", "cannot be determined", "unavailable"]):
            bucket["dry_run_unavailable_wording"] += 1
        if re.search(r"\b(?:january|february|march|april|may|june|july|august|september|october|november|december)\b", lowered):
            bucket["timestamp_format"] += 1
    return compact_style_patterns(patterns)


def compact_style_patterns(raw: dict[str, dict[str, Any]]) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    for family, values in raw.items():
        examples = max(1, int(values.get("examples", 0)))
        flags = {flag: round(float(values.get(flag, 0)) / examples, 3) for flag in STYLE_FLAGS}
        compact[family] = {"examples": examples, "style_flags": flags}
    return compact


def write_answer_style_patterns(config: Config | None = None) -> Path:
    cfg = config or DEFAULT_CONFIG
    cfg.outputs_dir.mkdir(parents=True, exist_ok=True)
    path = cfg.outputs_dir / "gold_answer_style_patterns.json"
    path.write_text(json.dumps(mine_answer_style_patterns(cfg), indent=2, sort_keys=True), encoding="utf-8")
    return path


def load_answer_style_patterns(config: Config | None = None) -> dict[str, Any]:
    cfg = config or DEFAULT_CONFIG
    path = cfg.outputs_dir / "gold_answer_style_patterns.json"
    if not path.exists():
        return mine_answer_style_patterns(cfg)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
