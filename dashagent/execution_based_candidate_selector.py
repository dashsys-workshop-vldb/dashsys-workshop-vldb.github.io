from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CandidateGateThresholds:
    token_delta_pct_max: float = 0.02
    runtime_delta_pct_max: float = 0.10
    substantial_score_gain_for_tool_increase: float = 0.05


def evaluate_candidate_safety(
    row: dict[str, Any],
    *,
    thresholds: CandidateGateThresholds | None = None,
) -> tuple[bool, str]:
    thresholds = thresholds or CandidateGateThresholds()
    failures: list[str] = []
    score_delta = float(row.get("score_delta") or 0.0)
    correctness_delta = float(row.get("correctness_delta") or 0.0)
    baseline_tokens = max(1, int(row.get("baseline_tokens") or 0))
    token_delta = int(row.get("token_delta") or 0)
    baseline_runtime = max(0.0001, float(row.get("baseline_runtime") or 0.0))
    runtime_delta = float(row.get("runtime_delta") or 0.0)
    tool_delta = int(row.get("tool_delta") or 0)

    if score_delta <= 0 and correctness_delta <= 0:
        failures.append("no_score_or_correctness_improvement")
    if row.get("candidate_id") == "current_baseline" or row.get("accuracy_relevant_change") is False:
        failures.append("no_accuracy_relevant_candidate_change")
    if token_delta > baseline_tokens * thresholds.token_delta_pct_max:
        failures.append("token_gate_failed")
    if runtime_delta > baseline_runtime * thresholds.runtime_delta_pct_max:
        failures.append("runtime_gate_failed")
    if tool_delta > 0 and score_delta < thresholds.substantial_score_gain_for_tool_increase:
        failures.append("tool_increase_without_substantial_score_gain")
    for key, failure in [
        ("final_answer_unsafe_drift", "final_answer_unsafe_drift"),
        ("sql_unsafe_drift", "sql_unsafe_drift"),
        ("api_unsafe_drift", "api_unsafe_drift"),
        ("evidence_label_loss", "evidence_label_loss"),
        ("live_api_evidence_fabricated", "live_api_evidence_fabricated"),
        ("required_fields_preserved", "required_fields_missing"),
        ("sql_validation_ok", "sql_validation_failed"),
        ("sql_ast_valid", "sql_ast_invalid"),
        ("api_validation_ok", "api_validation_failed"),
        ("leakage_check_passed", "leakage_check_failed"),
        ("holdout_regression_passed", "holdout_regression_failed"),
    ]:
        value = row.get(key)
        if key in {"required_fields_preserved", "sql_validation_ok", "sql_ast_valid", "api_validation_ok", "leakage_check_passed", "holdout_regression_passed"}:
            if value is not True:
                failures.append(failure)
        elif value:
            failures.append(failure)
    return not failures, "; ".join(sorted(set(failures)))


def select_best_candidate(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    safe_rows = [row for row in rows if row.get("safe_for_packaged_trial")]
    if not safe_rows:
        return None
    return sorted(
        safe_rows,
        key=lambda row: (
            -float(row.get("score_delta") or 0.0),
            -float(row.get("correctness_delta") or 0.0),
            int(row.get("tool_delta") or 0),
            int(row.get("token_delta") or 0),
            str(row.get("candidate_id") or ""),
        ),
    )[0]


def holdout_regression_gate(hidden_report: dict[str, Any], *, candidate_diversity_delta: int = 0) -> dict[str, Any]:
    summary = hidden_report.get("summary") or {}
    total = int(summary.get("total_cases") or 0)
    passed = int(summary.get("passed_cases") or 0)
    family_rate = float(summary.get("family_stability_rate") or 0.0)
    schema_rate = float(summary.get("schema_stability_rate") or 0.0)
    failures = []
    if total < 48 or passed != total:
        failures.append("hidden_style_not_48_48")
    if family_rate < 1.0:
        failures.append("endpoint_family_instability")
    if schema_rate < 1.0:
        failures.append("schema_family_instability")
    if candidate_diversity_delta < 0:
        failures.append("candidate_diversity_reduced")
    return {
        "passed": not failures,
        "failed_checks": failures,
        "hidden_style_total_cases": total,
        "hidden_style_passed_cases": passed,
        "family_stability_rate": family_rate,
        "schema_stability_rate": schema_rate,
        "candidate_diversity_delta": candidate_diversity_delta,
    }
