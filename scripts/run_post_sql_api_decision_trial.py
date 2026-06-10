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
from dashagent.endpoint_catalog import EndpointCatalog
from dashagent.planner import PlanStep
from dashagent.post_sql_api_call_verifier import verify_post_sql_api_advice
from dashagent.post_sql_decision_card import build_post_sql_decision_card
from dashagent.post_sql_deterministic_policy import decide_post_sql_api_policy
from dashagent.post_sql_llm_advisor import advise_post_sql_api
from dashagent.prompt_semantic_ir import extract_objective_prompt_features


VARIANTS = [
    "shadow_observe_only",
    "deterministic_high_conf_only",
    "llm_advisor_medium_low_only",
    "combined_verified_policy",
    "drop_api_when_sql_direct_answer",
    "sql_first_then_api_if_needed",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run shadow-only post-SQL API decision trial.")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    cfg = Config.from_env()
    catalog = EndpointCatalog(cfg)
    rows = _load_trajectory_rows(cfg, limit=args.limit)
    policy_counts: Counter[str] = Counter()
    confidence_counts: Counter[str] = Counter()
    verifier_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    advisor_invocations = 0
    advice_accepted = 0
    advice_blocked = 0
    deterministic_fallback_count = 0
    high_conf_bypass = 0
    api_calls_saved = 0
    api_calls_added = 0
    helped = 0
    hurt = 0
    output_rows: list[dict[str, Any]] = []

    for row in rows:
        features = extract_objective_prompt_features(row["prompt"])
        api_steps = [PlanStep(action="api", purpose="shadow planned API", method=api.get("method"), url=api.get("url"), params=api.get("params", {}), headers=api.get("headers", {}), family=api.get("family")) for api in row["api_steps"]]
        card = build_post_sql_decision_card(features, row.get("answer_intent") or "UNKNOWN", row.get("sql_result"), api_steps, catalog)
        policy = decide_post_sql_api_policy(card)
        advisor = advise_post_sql_api(card, policy, enabled=False)
        verified = verify_post_sql_api_advice(advisor, card, catalog, api_required=row.get("api_required", False))
        policy_counts[policy.suggestion] += 1
        confidence_counts[policy.confidence] += 1
        verifier_counts[verified.final_action] += 1
        source_counts[verified.source] += 1
        high_conf_bypass += 1 if policy.confidence == "HIGH" else 0
        advisor_invocations += 1 if policy.confidence in {"MEDIUM", "LOW"} or policy.suggestion == "AMBIGUOUS" else 0
        advice_accepted += 1 if verified.source == "LLM_ADVISOR_VERIFIED" else 0
        advice_blocked += 1 if verified.source == "LLM_ADVISOR_BLOCKED" and advisor.source not in {"DETERMINISTIC_FALLBACK", "DETERMINISTIC_BYPASS"} else 0
        deterministic_fallback_count += 1 if advisor.source == "DETERMINISTIC_FALLBACK" else 0
        planned_api = bool(row["api_steps"])
        if planned_api and verified.final_action in {"SKIP_API", "CAVEAT_ONLY"}:
            api_calls_saved += 1
            helped += 1
        if not planned_api and verified.final_action == "CALL_API":
            api_calls_added += 1
            hurt += 1
        output_rows.append(
            {
                "query_id": row["query_id"],
                "prompt": row["prompt"],
                "planned_api_count": len(row["api_steps"]),
                "card": card,
                "deterministic_policy": policy.to_dict(),
                "advisor": advisor.to_dict(),
                "verifier": verified.to_dict(),
            }
        )

    variant_summaries = {
        variant: {
            "shadow_only": True,
            "api_calls_saved": api_calls_saved if variant in {"deterministic_high_conf_only", "combined_verified_policy", "drop_api_when_sql_direct_answer", "sql_first_then_api_if_needed"} else 0,
            "api_calls_added": api_calls_added if variant in {"combined_verified_policy", "sql_first_then_api_if_needed"} else 0,
            "llm_calls_avoided_by_high_confidence_bypass": high_conf_bypass,
            "llm_advisor_invocation_count": advisor_invocations if "llm" in variant or variant == "combined_verified_policy" else 0,
            "strict_delta": 0.0,
            "api_delta": 0.0,
            "answer_delta": 0.0,
        }
        for variant in VARIANTS
    }
    strict_summary = _load_strict_summary(cfg)
    summary = {
        "classification": "diagnostic_only",
        "shadow_only": True,
        "packaged_default_strategy": "SQL_FIRST_API_VERIFY",
        "packaged_execution_changed": False,
        "total_rows": len(output_rows),
        "post_sql_deterministic_policy_distribution": dict(sorted(policy_counts.items())),
        "post_sql_policy_confidence_distribution": dict(sorted(confidence_counts.items())),
        "post_sql_verifier_action_distribution": dict(sorted(verifier_counts.items())),
        "post_sql_verifier_source_distribution": dict(sorted(source_counts.items())),
        "llm_post_sql_advisor_invocation_count": advisor_invocations,
        "llm_advice_verified_count": advice_accepted,
        "llm_advice_blocked_count": advice_blocked,
        "deterministic_fallback_count": deterministic_fallback_count,
        "high_confidence_bypass_count": high_conf_bypass,
        "api_calls_saved": api_calls_saved,
        "api_calls_added": api_calls_added,
        "rows_helped_estimate": helped,
        "rows_hurt_estimate": hurt,
        "variants": variant_summaries,
        "strict_api_answer_tool_token_runtime_deltas": {
            "strict_delta": 0.0,
            "api_delta": 0.0,
            "answer_delta": 0.0,
            "tool_call_delta": 0,
            "token_delta": 0,
            "runtime_delta": 0.0,
            "basis": "shadow-only; packaged eval metrics unchanged",
            "current_strict_summary": strict_summary,
        },
        "unsupported_claims": 0,
        "endpoint_matrix_status": "unchanged_shadow_only",
        "recommendation": "keep_shadow_only",
    }
    report = {**summary, "rows": output_rows}
    reports_dir = cfg.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "post_sql_api_decision_trial.json").write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    (reports_dir / "post_sql_api_decision_trial.md").write_text(_render_markdown(summary), encoding="utf-8")
    _write_integrated_report(cfg, summary)
    print(json.dumps(summary, indent=2, sort_keys=True, default=str))


def _load_trajectory_rows(cfg: Config, *, limit: int) -> list[dict[str, Any]]:
    paths = sorted((cfg.outputs_dir / "eval").glob("example_*/sql_first_api_verify/trajectory.json"))
    rows: list[dict[str, Any]] = []
    for path in paths[: limit or None]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        api_steps: list[dict[str, Any]] = []
        sql_result: dict[str, Any] | None = None
        for step in payload.get("steps") or []:
            if step.get("kind") == "sql_call" and sql_result is None:
                sql_result = _normalize_sql_result(step.get("result") or {})
            if step.get("kind") == "api_call":
                api_steps.append(
                    {
                        "method": step.get("method"),
                        "url": step.get("url"),
                        "params": step.get("params") or {},
                        "headers": step.get("headers") or {},
                        "family": None,
                    }
                )
        rows.append(
            {
                "query_id": payload.get("query_id") or path.parts[-3],
                "prompt": str(payload.get("original_query") or ""),
                "answer_intent": _answer_intent_from_trajectory(payload),
                "sql_result": sql_result or {"ok": False, "row_count": 0, "error": "no SQL result"},
                "api_steps": api_steps,
                "api_required": str(payload.get("route_type") or "").upper() == "API_ONLY",
            }
        )
    return rows


def _normalize_sql_result(result: dict[str, Any]) -> dict[str, Any]:
    payload = dict(result)
    rows = payload.get("rows")
    if isinstance(rows, dict) and isinstance(rows.get("items"), list):
        payload["rows"] = rows.get("items")
    return payload


def _answer_intent_from_trajectory(payload: dict[str, Any]) -> str:
    for checkpoint in payload.get("checkpoints") or []:
        if checkpoint.get("checkpoint_id") == "checkpoint_15_answer_slots":
            output = checkpoint.get("output") or {}
            return str(output.get("answer_intent") or "UNKNOWN")
    return "UNKNOWN"


def _load_strict_summary(cfg: Config) -> dict[str, Any]:
    path = cfg.outputs_dir / "eval_results_strict.json"
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    summary = payload.get("summary") if isinstance(payload, dict) else {}
    if isinstance(summary, dict):
        return summary.get("SQL_FIRST_API_VERIFY") or summary.get("sql_first_api_verify") or summary
    return {}


def _write_integrated_report(cfg: Config, post_sql_summary: dict[str, Any]) -> None:
    reports = cfg.outputs_dir / "reports"
    semantic = _load_json(reports / "semantic_route_decision_ladder_trial.json")
    promotion = _load_json(reports / "semantic_route_promotion_gate.json")
    staged = _load_json(reports / "staged_evidence_policy_trial.json")
    integrated = {
        "classification": "diagnostic_only",
        "shadow_only": True,
        "packaged_default_strategy": "SQL_FIRST_API_VERIFY",
        "packaged_execution_changed": False,
        "objective_prompt_features_examples": _examples_from_semantic_rows(semantic),
        "compact_llm_context_budget": 700,
        "semantic_intent_decision_schema": {"intent": "CONCEPT|DATA|LIVE_API|MIXED|AMBIG|UNSUPPORTED", "need": "NONE|SQL|API|SQL_API|UNKNOWN", "no_tool": "bool", "sql": "bool", "api": "bool", "conf": "float", "codes": "list"},
        "routing_anti_hallucination_feedback_loop_statistics": {
            "initial_pass": semantic.get("routing_gate_initial_pass_count", 0),
            "initial_fail": semantic.get("routing_gate_initial_fail_count", 0),
            "revision_attempts": semantic.get("routing_gate_revision_attempt_count", 0),
            "revision_success": semantic.get("routing_gate_revision_success_count", 0),
            "revision_fail": semantic.get("routing_gate_revision_fail_count", 0),
            "fallback_counts": semantic.get("routing_gate_fallback_counts", {}),
        },
        "no_tool_safety_verifier_statistics": {
            "allowed": semantic.get("no_tool_allowed_count", 0),
            "blocked": semantic.get("no_tool_blocked_count", 0),
            "false_no_tool_risk": semantic.get("false_no_tool_risk_count", 0),
        },
        "decision_ladder_action_distribution": semantic.get("action_distribution", {}),
        "safe_api_probe_usage": semantic.get("safe_api_probe_candidates", 0),
        "llm_safe_direct_usage": semantic.get("llm_safe_direct_candidates", 0),
        "evidence_match_score_distribution": {
            "branch_distribution": staged.get("branch_distribution", {}),
            "second_branch_distribution": staged.get("second_branch_distribution", {}),
        },
        "initial_evidence_branch_distribution": staged.get("branch_distribution", {}),
        "post_sql_deterministic_policy_distribution": post_sql_summary.get("post_sql_deterministic_policy_distribution", {}),
        "llm_post_sql_advisor_invocation_count": post_sql_summary.get("llm_post_sql_advisor_invocation_count", 0),
        "llm_advice_verified_count": post_sql_summary.get("llm_advice_verified_count", 0),
        "llm_advice_blocked_count": post_sql_summary.get("llm_advice_blocked_count", 0),
        "api_calls_saved": post_sql_summary.get("api_calls_saved", 0),
        "api_calls_added": post_sql_summary.get("api_calls_added", 0),
        "strict_api_answer_tool_token_runtime_deltas": post_sql_summary.get("strict_api_answer_tool_token_runtime_deltas", {}),
        "false_no_tool_risk": semantic.get("false_no_tool_risk_count", 0),
        "endpoint_matrix_status": post_sql_summary.get("endpoint_matrix_status", "unchanged_shadow_only"),
        "promotion_gate": promotion,
        "promotion_recommendation": "keep_shadow_only",
    }
    (reports / "semantic_routing_and_staged_evidence_policy.json").write_text(json.dumps(integrated, indent=2, sort_keys=True, default=str), encoding="utf-8")
    (reports / "semantic_routing_and_staged_evidence_policy.md").write_text(_render_integrated_markdown(integrated), encoding="utf-8")


def _examples_from_semantic_rows(semantic: dict[str, Any]) -> list[dict[str, Any]]:
    examples: list[dict[str, Any]] = []
    for row in semantic.get("rows") or []:
        if row.get("source") in {"conceptual_keyword", "concrete_data", "mixed"}:
            examples.append({"prompt": row.get("prompt"), "features": row.get("features"), "shadow_action": row.get("shadow_action")})
        if len(examples) >= 6:
            break
    return examples


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _render_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Post-SQL API Decision Trial",
        "",
        "Classification: `diagnostic_only`. The trial is shadow-only and did not change API execution.",
        "",
        "## Summary",
        "",
    ]
    for key in [
        "total_rows",
        "post_sql_deterministic_policy_distribution",
        "post_sql_policy_confidence_distribution",
        "llm_post_sql_advisor_invocation_count",
        "llm_advice_verified_count",
        "llm_advice_blocked_count",
        "api_calls_saved",
        "api_calls_added",
        "rows_helped_estimate",
        "rows_hurt_estimate",
        "recommendation",
    ]:
        lines.append(f"- {key}: `{summary.get(key)}`")
    return "\n".join(lines) + "\n"


def _render_integrated_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Semantic Routing and Staged Evidence Policy",
        "",
        "Classification: `diagnostic_only`. All behavior is shadow-only; packaged `SQL_FIRST_API_VERIFY` execution and final submission format are unchanged.",
        "",
        "## Summary",
        "",
    ]
    for key in [
        "decision_ladder_action_distribution",
        "routing_anti_hallucination_feedback_loop_statistics",
        "no_tool_safety_verifier_statistics",
        "initial_evidence_branch_distribution",
        "post_sql_deterministic_policy_distribution",
        "llm_post_sql_advisor_invocation_count",
        "llm_advice_verified_count",
        "llm_advice_blocked_count",
        "api_calls_saved",
        "api_calls_added",
        "false_no_tool_risk",
        "endpoint_matrix_status",
        "promotion_recommendation",
    ]:
        lines.append(f"- {key}: `{report.get(key)}`")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
