#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.prompt_router import route_prompt
from dashagent.semantic_route_decision_ladder import run_semantic_route_decision_ladder
from dashagent.simple_prompt_gate import decide_simple_prompt


CONCEPTUAL_PROMPTS = [
    "What is a schema?",
    "Explain a merge policy.",
    "How does a segment work?",
    "Describe Adobe tags.",
    "What is a journey?",
    "What is a dataset?",
]

CONCRETE_DATA_PROMPTS = [
    "List schemas.",
    "Show segment definitions.",
    "How many datasets use schema X?",
    "Give me audience IDs.",
    "Show failed dataflow runs.",
]

MIXED_PROMPTS = [
    "Explain what a merge policy is and list current merge policies.",
    "Describe schemas and show current schemas.",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run shadow-only semantic route decision ladder trial.")
    parser.add_argument("--generated-limit", type=int, default=50)
    parser.add_argument("--tier2", action="store_true", help="Enable tier-2 generic examples for diagnostic mode.")
    args = parser.parse_args()
    cfg = Config.from_env()
    rows = _load_rows(cfg, generated_limit=args.generated_limit)
    action_counts: Counter[str] = Counter()
    no_tool_allowed = 0
    no_tool_blocked = 0
    false_no_tool_risk = 0
    conceptual_false_positive_tool_routes_reduced = 0
    estimated_tool_call_savings = 0
    context_tokens = 0
    tier_total = 0
    low_low_count = 0
    gate_initial_pass = 0
    gate_initial_fail = 0
    gate_revision_attempts = 0
    gate_revision_success = 0
    gate_revision_fail = 0
    gate_fallback_counts: Counter[str] = Counter()
    gate_extra_tokens = 0
    results: list[dict[str, Any]] = []

    for row in rows:
        prompt = row["prompt"]
        route = route_prompt(prompt)
        simple = decide_simple_prompt(prompt)
        decision = run_semantic_route_decision_ladder(prompt, tier2_diagnostic=args.tier2, shadow_only=True)
        payload = decision.to_dict()
        action = payload["action"]
        action_counts[action] += 1
        safety = payload["no_tool_safety"]
        if safety.get("allow_no_tool"):
            no_tool_allowed += 1
        else:
            no_tool_blocked += 1
        concrete = bool(safety.get("has_concrete_data_signal")) or row["label"] in {"data", "mixed"}
        direct_action = action in {"LLM_DIRECT", "LLM_SAFE_DIRECT"}
        if concrete and direct_action:
            false_no_tool_risk += 1
        if row["label"] == "conceptual" and simple.suggested_action == "USE_DATA_PIPELINE" and direct_action:
            conceptual_false_positive_tool_routes_reduced += 1
        if simple.suggested_action == "USE_DATA_PIPELINE" and direct_action:
            estimated_tool_call_savings += 1
        if route.mode != "LLM_DIRECT" and action == "SAFE_API_PROBE":
            estimated_tool_call_savings += 1
        context_tokens += int(payload.get("context_token_cost") or 0)
        tier_total += int(payload.get("tier_used") or 0)
        low_low_count += 1 if payload.get("low_low_case") else 0
        gate = payload.get("routing_anti_hallucination_gate") or {}
        initial_gate = gate.get("initial_gate") or {}
        if initial_gate.get("ok"):
            gate_initial_pass += 1
        else:
            gate_initial_fail += 1
        if gate.get("revision_attempted"):
            gate_revision_attempts += 1
            if gate.get("revision_success"):
                gate_revision_success += 1
            else:
                gate_revision_fail += 1
        if gate.get("fallback_action"):
            gate_fallback_counts[str(gate.get("fallback_action"))] += 1
        gate_extra_tokens += int(gate.get("revision_token_estimate") or 0)
        results.append(
            {
                "prompt_id": row["prompt_id"],
                "prompt": prompt,
                "source": row["source"],
                "label": row["label"],
                "current_route_mode": route.mode,
                "current_simple_action": simple.suggested_action,
                "shadow_action": action,
                "tier_used": payload.get("tier_used"),
                "context_token_cost": payload.get("context_token_cost"),
                "no_tool_allowed": safety.get("allow_no_tool"),
                "no_tool_blocked": not safety.get("allow_no_tool"),
                "false_no_tool_risk": bool(concrete and direct_action),
                "features": payload.get("features"),
                "semantic_intent_decision": payload.get("semantic_intent_decision"),
                "routing_anti_hallucination_gate": gate,
                "no_tool_safety": safety,
                "safe_api_probe": payload.get("safe_api_probe"),
            }
        )

    total = len(results)
    summary = {
        "classification": "diagnostic_only",
        "packaged_default_strategy": "SQL_FIRST_API_VERIFY",
        "shadow_only": True,
        "promotion_allowed": False,
        "classifier_mode": "deterministic_fallback",
        "llm_backend_unavailable": False,
        "llm_backend_note": "LLM classifier was not invoked; default semantic classifier flags remain off.",
        "total_prompts": total,
        "public_dev_prompt_count": sum(1 for row in results if row["source"] == "public_dev"),
        "generated_prompt_count": sum(1 for row in results if row["source"] == "generated"),
        "conceptual_prompt_count": sum(1 for row in results if row["source"] == "conceptual_keyword"),
        "concrete_data_prompt_count": sum(1 for row in results if row["source"] == "concrete_data"),
        "mixed_prompt_count": sum(1 for row in results if row["source"] == "mixed"),
        "action_distribution": dict(sorted(action_counts.items())),
        "llm_direct_candidates": action_counts.get("LLM_DIRECT", 0),
        "llm_safe_direct_candidates": action_counts.get("LLM_SAFE_DIRECT", 0),
        "safe_api_probe_candidates": action_counts.get("SAFE_API_PROBE", 0),
        "evidence_pipeline_candidates": action_counts.get("EVIDENCE_PIPELINE", 0),
        "no_tool_allowed_count": no_tool_allowed,
        "no_tool_blocked_count": no_tool_blocked,
        "false_no_tool_risk_count": false_no_tool_risk,
        "conceptual_false_positive_tool_routes_reduced": conceptual_false_positive_tool_routes_reduced,
        "estimated_tool_call_savings": estimated_tool_call_savings,
        "total_context_token_cost": context_tokens,
        "average_context_token_cost": round(context_tokens / total, 2) if total else 0.0,
        "average_tier_used": round(tier_total / total, 3) if total else 0.0,
        "low_low_case_count": low_low_count,
        "routing_gate_initial_pass_count": gate_initial_pass,
        "routing_gate_initial_fail_count": gate_initial_fail,
        "routing_gate_revision_attempt_count": gate_revision_attempts,
        "routing_gate_revision_success_count": gate_revision_success,
        "routing_gate_revision_fail_count": gate_revision_fail,
        "routing_gate_fallback_counts": dict(sorted(gate_fallback_counts.items())),
        "routing_gate_extra_token_estimate": gate_extra_tokens,
        "strict_public_dev_shadow_impact_estimate": "no packaged score impact; shadow-only diagnostics",
        "recommendation": "keep_shadow_only",
    }
    report = {
        **summary,
        "rows": results,
    }
    out_json = cfg.outputs_dir / "reports" / "semantic_route_decision_ladder_trial.json"
    out_md = cfg.outputs_dir / "reports" / "semantic_route_decision_ladder_trial.md"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    out_md.write_text(_render_markdown(summary, results), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


def _load_rows(cfg: Config, *, generated_limit: int) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    data_path = cfg.data_json_path
    if data_path.exists():
        public_rows = json.loads(data_path.read_text(encoding="utf-8"))
        for idx, row in enumerate(public_rows, start=1):
            prompt = str(row.get("query") or "")
            rows.append({"prompt_id": f"public_{idx:03d}", "prompt": prompt, "source": "public_dev", "label": "data"})
    generated_path = cfg.data_dir / "generated_prompt_suite.json"
    if generated_path.exists() and generated_limit:
        generated_rows = json.loads(generated_path.read_text(encoding="utf-8"))[:generated_limit]
        for idx, row in enumerate(generated_rows, start=1):
            prompt = str(row.get("prompt") or "")
            label = "data" if str(row.get("expected_route_diagnostic") or "").upper() != "LLM_DIRECT" else "conceptual"
            rows.append({"prompt_id": str(row.get("prompt_id") or f"generated_{idx:03d}"), "prompt": prompt, "source": "generated", "label": label})
    for idx, prompt in enumerate(CONCEPTUAL_PROMPTS, start=1):
        rows.append({"prompt_id": f"conceptual_{idx:03d}", "prompt": prompt, "source": "conceptual_keyword", "label": "conceptual"})
    for idx, prompt in enumerate(CONCRETE_DATA_PROMPTS, start=1):
        rows.append({"prompt_id": f"data_{idx:03d}", "prompt": prompt, "source": "concrete_data", "label": "data"})
    for idx, prompt in enumerate(MIXED_PROMPTS, start=1):
        rows.append({"prompt_id": f"mixed_{idx:03d}", "prompt": prompt, "source": "mixed", "label": "mixed"})
    return rows


def _render_markdown(summary: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Semantic Route Decision Ladder Trial",
        "",
        "Classification: `diagnostic_only`.",
        "",
        "The semantic routing harness ran in shadow-only deterministic fallback mode. It did not change packaged routing, planning, SQL/API execution, answer synthesis, final submission artifacts, or Adobe API behavior.",
        "",
        "## Summary",
        "",
    ]
    for key in [
        "total_prompts",
        "llm_direct_candidates",
        "llm_safe_direct_candidates",
        "safe_api_probe_candidates",
        "evidence_pipeline_candidates",
        "no_tool_allowed_count",
        "no_tool_blocked_count",
        "false_no_tool_risk_count",
        "conceptual_false_positive_tool_routes_reduced",
        "estimated_tool_call_savings",
        "average_context_token_cost",
        "average_tier_used",
        "low_low_case_count",
        "routing_gate_initial_pass_count",
        "routing_gate_initial_fail_count",
        "routing_gate_revision_attempt_count",
        "routing_gate_revision_success_count",
        "routing_gate_revision_fail_count",
        "routing_gate_extra_token_estimate",
        "recommendation",
    ]:
        lines.append(f"- {key}: `{summary.get(key)}`")
    lines.extend(["", "## Action Distribution", ""])
    for action, count in (summary.get("action_distribution") or {}).items():
        lines.append(f"- `{action}`: `{count}`")
    lines.extend(["", "## Prompt Rows", "", "| prompt_id | source | current route | shadow action | no-tool allowed | false no-tool risk |", "|---|---|---:|---:|---:|---:|"])
    for row in rows[:120]:
        lines.append(
            f"| `{row['prompt_id']}` | `{row['source']}` | `{row['current_route_mode']}` | `{row['shadow_action']}` | `{row['no_tool_allowed']}` | `{row['false_no_tool_risk']}` |"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
