#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.semantic_route_decision_ladder import run_semantic_route_decision_ladder
from scripts.robustness_diagnostics_common import load_500_gold_by_id, load_500_runtime_prompts, load_organizer_prompts, write_json_md


def run_diagnostic() -> dict[str, Any]:
    rows = load_organizer_prompts() + load_500_runtime_prompts()
    gold = load_500_gold_by_id()
    action_counts: Counter[str] = Counter()
    gate_fails = 0
    revision_attempts = 0
    revision_successes = 0
    no_tool_allowed = 0
    no_tool_blocked = 0
    false_no_tool_risk: list[dict[str, Any]] = []
    concrete_wrong_no_tool: list[dict[str, Any]] = []
    context_token_cost = 0
    top_failure_cases: list[dict[str, Any]] = []
    for row in rows:
        prompt = str(row.get("prompt") or "")
        decision = run_semantic_route_decision_ladder(prompt, tier2_diagnostic=True, shadow_only=True)
        payload = decision.to_dict()
        action_counts[payload["action"]] += 1
        context_token_cost += int(payload.get("context_token_cost") or 0)
        gate = payload.get("routing_anti_hallucination_gate") or {}
        initial_gate = gate.get("initial_gate") or {}
        final_gate = gate.get("final_gate") or {}
        if not initial_gate.get("ok", True):
            gate_fails += 1
            top_failure_cases.append({"prompt_id": row.get("prompt_id"), "prompt": prompt, "gate": gate, "action": payload["action"]})
        if gate.get("revision_attempted"):
            revision_attempts += 1
        if gate.get("revision_success"):
            revision_successes += 1
        safety = payload.get("no_tool_safety") or {}
        if safety.get("allow_no_tool"):
            no_tool_allowed += 1
        else:
            no_tool_blocked += 1
        prompt_id = str(row.get("prompt_id") or "")
        expected = gold.get(prompt_id, {})
        tools = expected.get("expected_tool_calls") or {}
        if payload["action"] in {"LLM_DIRECT", "LLM_SAFE_DIRECT"} and (tools.get("sql_required") or tools.get("api_required")):
            concrete_wrong_no_tool.append({"prompt_id": prompt_id, "prompt": prompt, "action": payload["action"], "features": payload.get("features")})
        if safety.get("block"):
            false_no_tool_risk.append({"prompt_id": prompt_id, "prompt": prompt, "block": safety.get("block"), "action": payload["action"]})
    report = {
        "report_type": "semantic_routing_diagnostic",
        "diagnostic_only": True,
        "shadow_only": True,
        "runtime_behavior_changed": False,
        "prompt_count": len(rows),
        "action_distribution": dict(sorted(action_counts.items())),
        "llm_direct_candidates": action_counts.get("LLM_DIRECT", 0),
        "llm_safe_direct_candidates": action_counts.get("LLM_SAFE_DIRECT", 0),
        "safe_api_probe_candidates": action_counts.get("SAFE_API_PROBE", 0),
        "evidence_pipeline_candidates": action_counts.get("EVIDENCE_PIPELINE", 0),
        "anti_hallucination_gate_fails": gate_fails,
        "revision_attempts": revision_attempts,
        "revision_successes": revision_successes,
        "no_tool_allowed": no_tool_allowed,
        "no_tool_blocked": no_tool_blocked,
        "false_no_tool_risk_count": len(false_no_tool_risk),
        "concrete_data_prompt_wrong_no_tool_count": len(concrete_wrong_no_tool),
        "context_token_cost_total": context_token_cost,
        "context_token_cost_avg": round(context_token_cost / max(1, len(rows)), 2),
        "top_failure_cases": top_failure_cases[:25],
        "false_no_tool_risk_examples": false_no_tool_risk[:25],
        "concrete_data_prompt_wrong_no_tool_examples": concrete_wrong_no_tool[:25],
    }
    return report


def main() -> int:
    report = run_diagnostic()
    lines = [
        "# Semantic Routing Diagnostic",
        "",
        f"- Prompt count: `{report['prompt_count']}`",
        f"- Action distribution: `{report['action_distribution']}`",
        f"- Anti-hallucination gate fails: `{report['anti_hallucination_gate_fails']}`",
        f"- Revision attempts: `{report['revision_attempts']}`",
        f"- Concrete data wrongly no-tool: `{report['concrete_data_prompt_wrong_no_tool_count']}`",
        f"- Average context token estimate: `{report['context_token_cost_avg']}`",
        "",
        "All semantic decisions are shadow/diagnostic only.",
    ]
    write_json_md("semantic_routing_diagnostic", report, lines)
    print(json.dumps({k: report[k] for k in ["prompt_count", "action_distribution", "concrete_data_prompt_wrong_no_tool_count"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
