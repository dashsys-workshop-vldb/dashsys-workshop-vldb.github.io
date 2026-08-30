from __future__ import annotations

from typing import Any


def select_repair_candidate_v2(
    current_plan: dict[str, Any],
    repaired_plan: dict[str, Any],
    safety: dict[str, Any],
    *,
    ast_current: dict[str, Any] | None = None,
    ast_repaired: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Stricter shadow-only pairwise selector.

    This is intentionally not wired into runtime execution.  It only explains
    whether a repaired plan is strong enough to consider in a future canary.
    """

    failed: list[str] = []
    reasons: list[str] = []
    no_op = _plans_equal(current_plan, repaired_plan)
    score_delta_present = "offline_score_delta" in repaired_plan
    score_delta = float(repaired_plan.get("offline_score_delta") or 0.0) if score_delta_present else None
    if no_op:
        return {
            "selected_plan": "current",
            "decision_label": "no_op_tie_keep_current",
            "safe_to_select_repaired": False,
            "failed_checks": [],
            "reasons": ["Current and repaired plans are identical; keep current."],
            "no_op": True,
            "score_tie": score_delta == 0 if score_delta_present else False,
            "diagnostic_only": True,
            "behavior_changed": False,
            "packaged_execution_changed": False,
            "correctness_role": "keeps current plan for no-op repair recommendations",
            "efficiency_role": "avoids selecting equivalent repairs",
        }
    if score_delta_present and score_delta == 0:
        return {
            "selected_plan": "current",
            "decision_label": "score_tie_keep_current",
            "safe_to_select_repaired": False,
            "failed_checks": [],
            "reasons": ["Offline strict score tied; keep current plan unless a future canary proves a benefit."],
            "no_op": False,
            "score_tie": True,
            "diagnostic_only": True,
            "behavior_changed": False,
            "packaged_execution_changed": False,
            "correctness_role": "keeps current plan for zero-delta repairs",
            "efficiency_role": "avoids selecting equivalent repairs",
        }
    if safety.get("safe") is not True:
        failed.append("safety_verifier")
        reasons.append("Safety verifier did not pass.")
    if repaired_plan.get("fusion_agreement") is not True:
        failed.append("fusion_agreement")
        reasons.append("Weighted and RRF/family signals do not agree.")
    endpoint_confidence = float(repaired_plan.get("endpoint_family_confidence") or 0.0)
    if repaired_plan.get("api_calls") and endpoint_confidence < 0.90:
        failed.append("endpoint_family_confidence")
        reasons.append(f"Endpoint family confidence {endpoint_confidence:.4f} is below 0.90.")
    current_ast_score = float((ast_current or {}).get("ast_quality_score") or 0.0)
    repaired_ast_score = float((ast_repaired or {}).get("ast_quality_score") or current_ast_score)
    if repaired_ast_score < current_ast_score:
        failed.append("ast_quality_regression")
        reasons.append("Repaired AST quality score regressed.")
    if (ast_repaired or {}).get("destructive_sql_detected"):
        failed.append("destructive_sql")
        reasons.append("Repaired SQL AST detected destructive SQL.")
    current_shape = current_plan.get("expected_answer_shape")
    repaired_shape = repaired_plan.get("expected_answer_shape")
    if current_shape and repaired_shape and current_shape != repaired_shape:
        failed.append("answer_shape")
        reasons.append("Expected answer shape changed.")
    if int(repaired_plan.get("tool_call_count") or 0) > int(current_plan.get("tool_call_count") or 0):
        failed.append("tool_call_increase")
        reasons.append("Repaired plan increases tool calls.")
    if score_delta_present and score_delta is not None and score_delta < 0:
        failed.append("score_regression")
        reasons.append("Offline strict score regressed.")
    safe = not failed
    if safe:
        reasons.append("Repaired candidate passed v2 shadow-only selector gates.")
    return {
        "selected_plan": "repaired" if safe else "current",
        "decision_label": "strictly_better_repaired_shadow_candidate" if safe else "keep_current_failed_gates",
        "safe_to_select_repaired": safe,
        "failed_checks": sorted(set(failed)),
        "reasons": reasons,
        "no_op": False,
        "score_tie": False,
        "diagnostic_only": True,
        "behavior_changed": False,
        "packaged_execution_changed": False,
        "correctness_role": "prefers current unless repaired strictly improves endpoint/schema/value/AST evidence",
        "efficiency_role": "rejects repairs with any tool-call increase",
    }


def _plans_equal(current_plan: dict[str, Any], repaired_plan: dict[str, Any]) -> bool:
    current = {
        "sql": current_plan.get("sql") or [],
        "api_calls": current_plan.get("api_calls") or [],
        "final_answer": current_plan.get("final_answer"),
    }
    repaired = {
        "sql": repaired_plan.get("sql") or [],
        "api_calls": repaired_plan.get("api_calls") or [],
        "final_answer": repaired_plan.get("final_answer"),
    }
    return current == repaired
