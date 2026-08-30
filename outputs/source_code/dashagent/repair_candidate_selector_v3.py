from __future__ import annotations

from typing import Any


def select_repair_candidate_v3(
    current_plan: dict[str, Any],
    repaired_plan: dict[str, Any],
    ast_guided_plan: dict[str, Any] | None,
    safety: dict[str, Any],
    *,
    ast_current: dict[str, Any] | None = None,
    ast_repaired: dict[str, Any] | None = None,
    ast_guided: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Shadow-only CHASE-style pairwise selector.

    The selector is intentionally conservative: current wins unless an
    alternative has positive offline score delta and passes every deterministic
    SQL/API/evidence/cost gate.
    """

    alternatives = [
        ("repaired", repaired_plan, ast_repaired or {}),
    ]
    if ast_guided_plan:
        alternatives.append(("ast_guided", ast_guided_plan, ast_guided or {}))

    current_ast_score = float((ast_current or {}).get("ast_quality_score") or 0.0)
    decisions = [_evaluate_alternative(name, plan, ast, current_plan, current_ast_score, safety) for name, plan, ast in alternatives]
    selected = next((item for item in sorted(decisions, key=lambda row: (-row["score_delta"], row["name"])) if item["safe_to_select"]), None)
    if selected:
        return {
            "selected_plan": selected["name"],
            "decision_label": f"strictly_better_{selected['name']}_shadow_candidate",
            "safe_to_select_alternative": True,
            "failed_checks": [],
            "reasons": selected["reasons"],
            "alternative_decisions": decisions,
            "diagnostic_only": True,
            "behavior_changed": False,
            "packaged_execution_changed": False,
        }
    no_op = any(item["decision_label"] == "no_op_tie_keep_current" for item in decisions)
    tie = any(item["decision_label"] == "score_tie_keep_current" for item in decisions)
    return {
        "selected_plan": "current",
        "decision_label": "no_op_tie_keep_current" if no_op else "score_tie_keep_current" if tie else "keep_current_failed_gates",
        "safe_to_select_alternative": False,
        "failed_checks": sorted({failure for item in decisions for failure in item["failed_checks"]}),
        "reasons": [reason for item in decisions for reason in item["reasons"]],
        "alternative_decisions": decisions,
        "diagnostic_only": True,
        "behavior_changed": False,
        "packaged_execution_changed": False,
    }


def _evaluate_alternative(
    name: str,
    plan: dict[str, Any],
    ast: dict[str, Any],
    current_plan: dict[str, Any],
    current_ast_score: float,
    safety: dict[str, Any],
) -> dict[str, Any]:
    failed: list[str] = []
    reasons: list[str] = []
    score_delta_present = "offline_score_delta" in plan
    score_delta = float(plan.get("offline_score_delta") or 0.0) if score_delta_present else 0.0
    if _plans_equal(current_plan, plan):
        return _decision(name, "no_op_tie_keep_current", False, [], ["Alternative is identical to current plan."], score_delta)
    if score_delta_present and score_delta == 0:
        return _decision(name, "score_tie_keep_current", False, [], ["Offline strict score tied; keep current."], score_delta)
    if score_delta_present and score_delta < 0:
        failed.append("score_regression")
        reasons.append("Offline strict score regressed.")
    if score_delta_present and score_delta <= 0:
        failed.append("no_positive_score_delta")
        reasons.append("Alternative does not strictly improve offline score.")
    if safety.get("safe") is not True:
        failed.append("safety_verifier")
        reasons.append("Safety verifier did not pass.")
    if plan.get("fusion_agreement") is not True:
        failed.append("fusion_agreement")
        reasons.append("Weighted and RRF/family signals do not agree.")
    endpoint_confidence = float(plan.get("endpoint_family_confidence") or 0.0)
    if plan.get("api_calls") and endpoint_confidence < 0.90:
        failed.append("endpoint_family_confidence")
        reasons.append("Endpoint family confidence is below 0.90.")
    schema_confidence = float(plan.get("schema_family_confidence") or 1.0)
    if schema_confidence < 0.75:
        failed.append("schema_family_confidence")
        reasons.append("Schema family confidence is below 0.75.")
    if ast.get("parsed_ok") is False:
        failed.append("sql_ast_parse")
        reasons.append("SQL AST parse failed.")
    if ast.get("unknown_tables"):
        failed.append("unknown_tables")
        reasons.append("Alternative SQL contains unknown tables.")
    if ast.get("unknown_columns"):
        failed.append("unknown_columns")
        reasons.append("Alternative SQL contains unknown columns.")
    if ast.get("destructive_sql_detected"):
        failed.append("destructive_sql")
        reasons.append("Alternative SQL is destructive.")
    if float(ast.get("ast_quality_score") or 0.0) < current_ast_score:
        failed.append("ast_quality_regression")
        reasons.append("AST quality regressed.")
    current_shape = current_plan.get("expected_answer_shape")
    repaired_shape = plan.get("expected_answer_shape")
    if current_shape and repaired_shape and current_shape != repaired_shape:
        failed.append("answer_shape")
        reasons.append("Answer shape changed.")
    if int(plan.get("tool_call_count") or 0) > int(current_plan.get("tool_call_count") or 0):
        failed.append("tool_call_increase")
        reasons.append("Tool calls increased.")
    if plan.get("dry_run_labels_preserved") is False:
        failed.append("dry_run_labels")
        reasons.append("Dry-run/live evidence labels changed.")
    if plan.get("live_api_evidence_fabricated"):
        failed.append("live_api_evidence_fabricated")
        reasons.append("Live API evidence would be fabricated.")
    safe = not failed
    return _decision(
        name,
        f"strictly_better_{name}_shadow_candidate" if safe else "keep_current_failed_gates",
        safe,
        sorted(set(failed)),
        reasons or [f"{name} alternative passed selector v3 gates."],
        score_delta,
    )


def _decision(
    name: str,
    label: str,
    safe: bool,
    failed: list[str],
    reasons: list[str],
    score_delta: float,
) -> dict[str, Any]:
    return {
        "name": name,
        "decision_label": label,
        "safe_to_select": safe,
        "failed_checks": failed,
        "reasons": reasons,
        "score_delta": score_delta,
    }


def _plans_equal(current_plan: dict[str, Any], alternative: dict[str, Any]) -> bool:
    current = {
        "sql": current_plan.get("sql") or [],
        "api_calls": current_plan.get("api_calls") or [],
        "final_answer": current_plan.get("final_answer"),
    }
    other = {
        "sql": alternative.get("sql") or [],
        "api_calls": alternative.get("api_calls") or [],
        "final_answer": alternative.get("final_answer"),
    }
    return current == other
