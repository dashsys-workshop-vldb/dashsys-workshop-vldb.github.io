#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.prompt_semantic_ir import extract_objective_prompt_features
from scripts.robustness_diagnostics_common import counter_dict, load_500_gold_by_id, load_500_runtime_prompts, load_organizer_prompts, write_json_md


def run_diagnostic() -> dict[str, Any]:
    prompts = load_organizer_prompts() + load_500_runtime_prompts()
    gold_by_id = load_500_gold_by_id()
    cue_counts: Counter[str] = Counter()
    dataset_counts: Counter[str] = Counter()
    api_required_coverage = {"total": 0, "with_api_capability": 0, "with_live_or_explicit_family": 0}
    false_no_tool_risk: list[dict[str, Any]] = []
    ambiguous: list[dict[str, Any]] = []
    weak_api_family: list[dict[str, Any]] = []
    examples: list[dict[str, Any]] = []
    for row in prompts:
        features = extract_objective_prompt_features(str(row.get("prompt") or ""))
        payload = features.to_dict()
        dataset = str(row.get("dataset") or "unknown")
        dataset_counts[dataset] += 1
        for key in ("cue", "retr", "count", "status", "date", "rel", "domain", "entity", "cap", "flags"):
            for value in payload.get(key) or []:
                cue_counts[f"{key}:{value}"] += 1
        prompt_id = str(row.get("prompt_id") or "")
        gold = gold_by_id.get(prompt_id, {})
        expected_tools = gold.get("expected_tool_calls") or {}
        if expected_tools.get("api_required"):
            api_required_coverage["total"] += 1
            if any(str(code).startswith("API_") for code in payload.get("cap") or []):
                api_required_coverage["with_api_capability"] += 1
            if "LIVE_OR_CURRENT" in payload.get("flags", []) or "EXPLICIT_API_FAMILY" in payload.get("flags", []):
                api_required_coverage["with_live_or_explicit_family"] += 1
            elif not any(str(code).startswith("API_") for code in payload.get("cap") or []):
                weak_api_family.append({"prompt_id": prompt_id, "prompt": row.get("prompt"), "features": payload})
        has_data_signal = any(payload.get(key) for key in ("retr", "count", "status", "date", "fields", "rel", "entity"))
        has_concept = bool(payload.get("cue"))
        if has_concept and has_data_signal:
            ambiguous.append({"prompt_id": prompt_id, "dataset": dataset, "prompt": row.get("prompt"), "features": payload})
        if "MIXED_CONCEPT_AND_RETRIEVAL" in payload.get("flags", []) or (payload.get("cue") and has_data_signal):
            false_no_tool_risk.append({"prompt_id": prompt_id, "dataset": dataset, "prompt": row.get("prompt"), "features": payload})
        if len(examples) < 12:
            examples.append({"prompt_id": prompt_id, "dataset": dataset, "prompt": row.get("prompt"), "features": payload})
    total_api = max(1, api_required_coverage["total"])
    report = {
        "report_type": "objective_prompt_feature_diagnostic",
        "diagnostic_only": True,
        "runtime_behavior_changed": False,
        "prompt_count": len(prompts),
        "dataset_counts": dict(dataset_counts),
        "cue_distribution": dict(cue_counts.most_common(80)),
        "api_required_cue_coverage": {
            **api_required_coverage,
            "api_capability_rate": round(api_required_coverage["with_api_capability"] / total_api, 4),
            "live_or_explicit_family_rate": round(api_required_coverage["with_live_or_explicit_family"] / total_api, 4),
        },
        "false_no_tool_risk_count": len(false_no_tool_risk),
        "ambiguous_prompt_count": len(ambiguous),
        "explicit_api_family_detection_count": cue_counts.get("flags:EXPLICIT_API_FAMILY", 0),
        "weak_api_family_examples": weak_api_family[:20],
        "false_no_tool_risk_examples": false_no_tool_risk[:20],
        "examples": examples,
    }
    return report


def main() -> int:
    report = run_diagnostic()
    lines = [
        "# Objective Prompt Feature Diagnostic",
        "",
        f"- Prompt count: `{report['prompt_count']}`",
        f"- False no-tool risk prompts: `{report['false_no_tool_risk_count']}`",
        f"- Ambiguous prompts: `{report['ambiguous_prompt_count']}`",
        f"- API-required capability coverage: `{report['api_required_cue_coverage']['api_capability_rate']}`",
        f"- Explicit API-family detections: `{report['explicit_api_family_detection_count']}`",
        "",
        "Diagnostics are report-only and do not alter packaged routing.",
    ]
    write_json_md("objective_prompt_feature_diagnostic", report, lines)
    print(json.dumps({k: report[k] for k in ["prompt_count", "false_no_tool_risk_count", "ambiguous_prompt_count"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
