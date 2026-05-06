from __future__ import annotations

from typing import Any


def select_repair_candidate(
    current_plan: dict[str, Any],
    repaired_plan: dict[str, Any],
    safety: dict[str, Any],
    context: dict[str, Any] | None = None,
    schema_vote: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Select current vs repaired plan for shadow diagnostics.

    The selector is deliberately conservative and report-only.  It never
    mutates packaged execution; it only explains whether a repaired candidate
    would be strong enough to consider in a future canary.
    """

    context = context or {}
    schema_vote = schema_vote or {}
    failed: list[str] = []
    reasons: list[str] = []
    no_op = _plans_equal(current_plan, repaired_plan)

    if no_op:
        failed.append("no_op_repair")
        reasons.append("Current and repaired plans are identical; keep the current plan.")

    if safety.get("safe") is not True:
        failed.append("safety_verifier")
        reasons.append("Repair safety verifier did not pass.")

    if repaired_plan.get("fusion_agreement") is not True:
        failed.append("fusion_agreement")
        reasons.append("Weighted score fusion and RRF/family signals did not agree.")

    endpoint_confidence = float(repaired_plan.get("endpoint_family_confidence") or 0.0)
    if repaired_plan.get("api_calls") and endpoint_confidence < 0.85:
        failed.append("endpoint_family_confidence")
        reasons.append(f"Endpoint family confidence {endpoint_confidence:.4f} is below 0.85.")

    if schema_vote.get("schema_vote_agreement") is not True:
        failed.append("schema_vote_agreement")
        reasons.append("Compact-vs-broader schema context vote did not agree.")

    if not _sql_ast_valid(safety):
        failed.append("sql_ast_validation")
        reasons.append("SQLGlot AST validation did not pass for the repaired SQL.")

    current_shape = current_plan.get("expected_answer_shape")
    repaired_shape = repaired_plan.get("expected_answer_shape")
    if current_shape and repaired_shape and current_shape != repaired_shape:
        failed.append("answer_shape")
        reasons.append("Expected answer shape changed.")

    if int(repaired_plan.get("tool_call_count") or 0) > int(current_plan.get("tool_call_count") or 0):
        failed.append("tool_call_increase")
        reasons.append("Repaired plan would increase tool calls.")

    if repaired_plan.get("dry_run_only") and repaired_plan.get("live_api_evidence_available"):
        failed.append("dry_run_live_evidence")
        reasons.append("Dry-run API was marked as live evidence.")

    if "offline_score_delta" in repaired_plan:
        offline_score_delta = float(repaired_plan.get("offline_score_delta") or 0.0)
        if offline_score_delta < 0:
            failed.append("score_regression")
            reasons.append(
                f"Offline shadow strict score regressed by {offline_score_delta:.4f}; keep the current plan."
            )

    safe_to_select = not failed
    if safe_to_select:
        reasons.append("Repaired plan passed strict report-only selector gates.")
    return {
        "selected_plan": "repaired" if safe_to_select else "current",
        "safe_to_select_repaired": safe_to_select,
        "recommendation": "select_repaired_shadow_candidate" if safe_to_select else "keep_current",
        "no_op": no_op,
        "reasons": reasons,
        "failed_checks": sorted(set(failed)),
        "diagnostic_only": True,
        "behavior_changed": False,
        "packaged_execution_changed": False,
        "correctness_role": "prefers current plan unless repaired candidate strictly improves all safety signals",
        "efficiency_role": "rejects repaired candidates with any tool-call increase",
    }


def _plans_equal(current_plan: dict[str, Any], repaired_plan: dict[str, Any]) -> bool:
    return _tool_signature(current_plan) == _tool_signature(repaired_plan)


def _tool_signature(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "sql": plan.get("sql") or [],
        "api_calls": [
            {
                "method": str(call.get("method") or "GET").upper(),
                "path": call.get("path") or call.get("url"),
                "params": call.get("params") or {},
            }
            for call in plan.get("api_calls") or []
        ],
    }


def _sql_ast_valid(safety: dict[str, Any]) -> bool:
    sql_validation = safety.get("sql_validation") or {}
    if sql_validation.get("ok") is not True:
        return False
    for summary in sql_validation.get("ast_summaries") or []:
        if summary.get("parsed_ok") is False:
            return False
        if summary.get("parse_error"):
            return False
        if summary.get("unknown_tables") or summary.get("unknown_columns"):
            return False
        if summary.get("destructive_sql_detected"):
            return False
    return True
