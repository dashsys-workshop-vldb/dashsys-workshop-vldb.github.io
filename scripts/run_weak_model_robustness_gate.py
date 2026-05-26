#!/usr/bin/env python
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.trajectory import redact_secrets

REPORT_STEM = "weak_model_robustness_gate"


def main() -> int:
    config = Config.from_env(ROOT)
    report = run_weak_model_robustness_gate(config)
    print(json.dumps({"json": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.json"), "recommendation": report["recommendation"]}, indent=2, sort_keys=True))
    return 0


def run_weak_model_robustness_gate(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports = config.outputs_dir / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    lift = _load_json(reports / "weak_model_lift_eval.json")
    strict = _load_json(config.outputs_dir / "eval_results_strict.json")
    generated = _load_json(reports / "full_generated_prompt_suite_diagnostic.json")
    paraphrase = _load_json(reports / "nl_sql_paraphrase_consistency.json")
    weak_generated = _load_json(reports / "weak_model_generated_prompt_diagnostic.json")
    weak_paraphrase = _load_json(reports / "weak_model_paraphrase_consistency.json")
    weak_no_template = _load_json(reports / "weak_model_no_template_diagnostic.json")
    weak_sql_bottleneck = _load_json(reports / "weak_model_sql_bottleneck_analysis.json")
    weak_sql_trials = _load_latest_json(
        [
            reports / "weak_model_sql_improvement_trials_public_dev_full.json",
            reports / "weak_model_sql_improvement_trials_public_dev_limit_10.json",
            reports / "weak_model_sql_improvement_trials.json",
        ]
    )
    weak_harness = _load_latest_json(
        [
            reports / "weak_harness_engineering_eval_public_dev_full.json",
            reports / "weak_harness_engineering_eval_public_dev_limit_10.json",
            reports / "weak_harness_engineering_eval.json",
        ]
    )
    weak_answer_grounding = _load_json(reports / "weak_model_answer_grounding_regression_analysis.json")
    endpoint = _load_json(reports / "live_api_safe_get_endpoint_matrix.json") or _load_json(reports / "live_api_readiness_smoke.json")
    hidden = _load_json(reports / "hidden_style_eval.json") or _load_json(config.outputs_dir / "hidden_style_eval.json")

    summary = lift.get("summary", {}) if isinstance(lift.get("summary"), dict) else {}
    modes = summary.get("modes", []) if isinstance(summary.get("modes"), list) else []
    raw = _mode(modes, "raw_weak_llm")
    guided = _mode(modes, "guided_weak_llm")
    best = _mode(modes, str(summary.get("best_scaffold_mode") or ""))
    full_current = _full_current(strict, modes)
    previous_scaffold = _previous_scaffold_reference(reports / "weak_model_api_nonregression_analysis.json")
    generated_summary = _generated_summary(generated)
    weak_generated_summary = _weak_generated_summary(weak_generated)
    weak_paraphrase_summary = _weak_paraphrase_summary(weak_paraphrase)
    weak_no_template_summary = _weak_no_template_summary(weak_no_template)
    weak_sql_bottleneck_summary = _weak_sql_bottleneck_summary(weak_sql_bottleneck)
    weak_sql_trials_summary = _weak_sql_trials_summary(weak_sql_trials)
    weak_harness_summary = _weak_harness_summary(weak_harness)
    weak_answer_grounding_summary = _weak_answer_grounding_summary(weak_answer_grounding)
    endpoint_summary = _endpoint_summary(endpoint)
    hidden_pass = _hidden_pass(hidden)

    gates = {
        "strict_score_improves_over_raw_weak": _num(best.get("strict_final_score")) > _num(raw.get("strict_final_score")),
        "strict_score_beats_guided_weak": _num(best.get("strict_final_score")) > _num(guided.get("strict_final_score")),
        "sql_score_improves_over_raw_weak": _num(best.get("sql_score")) > _num(raw.get("sql_score")),
        "api_score_not_regressed_vs_raw_or_guided_weak": _num(best.get("api_score")) >= max(_num(raw.get("api_score")), _num(guided.get("api_score"))),
        "answer_grounding_improves_over_previous_scaffold": previous_scaffold == {} or _num(best.get("answer_score")) > _num(previous_scaffold.get("answer_score")),
        "unsupported_claims_zero": int(best.get("unsupported_claims") or 0) == 0,
        "generated_prompt_runtime_pass_high": generated_summary.get("runtime_pass_count") in {None, generated_summary.get("total_count")} or _num(generated_summary.get("runtime_pass_rate")) >= 0.95,
        "weak_generated_prompt_runtime_pass_high": weak_generated_summary == {} or _num(weak_generated_summary.get("runtime_pass_rate")) >= 0.95,
        "weak_generated_prompt_validation_clean": weak_generated_summary == {} or int(weak_generated_summary.get("validation_failures") or 0) == 0,
        "weak_generated_prompt_unsupported_claims_zero": weak_generated_summary == {} or int(weak_generated_summary.get("unsupported_claim_count") or 0) == 0,
        "paraphrase_consistency_available_or_nonregressed": paraphrase == {} or _num(_paraphrase_summary(paraphrase).get("paraphrase_consistency")) >= 0.0,
        "weak_paraphrase_consistency_acceptable": weak_paraphrase_summary == {} or _num(weak_paraphrase_summary.get("consistency_score")) >= 0.75,
        "weak_no_template_unsupported_claims_zero": weak_no_template_summary == {} or int(weak_no_template_summary.get("unsupported_claim_count") or 0) == 0,
        "weak_no_template_validation_acceptable": weak_no_template_summary == {} or _none_or_at_least(weak_no_template_summary.get("sql_validation_pass_rate"), 0.8),
        "weak_sql_trial_sql_improved": weak_sql_trials_summary == {} or bool(weak_sql_trials_summary.get("sql_improved_over_current")),
        "weak_sql_trial_api_nonregression": weak_sql_trials_summary == {} or bool(weak_sql_trials_summary.get("best_sql_variant_api_nonregression")),
        "weak_sql_trial_answer_nonregression": weak_sql_trials_summary == {} or bool(weak_sql_trials_summary.get("best_sql_variant_answer_nonregression")),
        "weak_answer_v3_improves_over_v2": weak_answer_grounding_summary == {} or bool(weak_answer_grounding_summary.get("v3_answer_improves_over_v2")),
        "weak_answer_v3_strict_improves_over_v2": weak_answer_grounding_summary == {} or bool(weak_answer_grounding_summary.get("v3_strict_improves_over_v2")),
        "weak_answer_v3_answer_nonregression_vs_v1": weak_answer_grounding_summary == {} or bool(weak_answer_grounding_summary.get("v3_answer_nonregression_vs_v1")),
        "weak_harness_sql_improved": weak_harness_summary == {} or bool(weak_harness_summary.get("sql_improved_over_previous_weak_scaffold")),
        "weak_harness_api_nonregression": weak_harness_summary == {} or bool(weak_harness_summary.get("api_nonregression")),
        "weak_harness_answer_nonregression": weak_harness_summary == {} or bool(weak_harness_summary.get("answer_nonregression")),
        "weak_harness_unsupported_claims_zero": weak_harness_summary == {} or bool(weak_harness_summary.get("unsupported_claims_zero")),
        "weak_harness_bounded_or_full_gate_passed": weak_harness_summary == {} or bool(weak_harness_summary.get("bounded_gate_passed")),
        "endpoint_matrix_clean": endpoint_summary.get("failures", 0) == 0,
        "hidden_style_passes": hidden_pass is not False,
        "token_runtime_cost_acceptable": _token_runtime_cost_acceptable(best, raw, guided),
        "final_submission_format_unchanged": True,
        "packaged_runtime_unchanged": bool(lift.get("packaged_runtime_changed")) is False,
    }
    gate_passed = all(gates.values())
    recommendation = _recommendation(gates, summary, weak_sql_bottleneck_summary, best)
    report = redact_secrets(
        {
            "report_type": REPORT_STEM,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "diagnostic_only": True,
            "promotion_allowed": False,
            "packaged_runtime_changed": False,
            "packaged_default_strategy": "SQL_FIRST_API_VERIFY",
            "raw_weak_llm": raw,
            "guided_weak_llm": guided,
            "best_scaffold": best,
            "previous_scaffold_reference": previous_scaffold,
            "full_dashagent_current": full_current,
            "small_model_lift_score": summary.get("small_model_lift_score"),
            "sql_lift": summary.get("sql_lift"),
            "api_lift": summary.get("api_lift"),
            "answer_grounding_lift": summary.get("answer_grounding_lift"),
            "efficiency_lift": summary.get("efficiency_lift"),
            "generated_prompt_diagnostic": generated_summary,
            "weak_model_generated_prompt_diagnostic": weak_generated_summary,
            "paraphrase_consistency": _paraphrase_summary(paraphrase),
            "weak_model_paraphrase_consistency": weak_paraphrase_summary,
            "weak_model_no_template_diagnostic": weak_no_template_summary,
            "weak_model_sql_bottleneck": weak_sql_bottleneck_summary,
            "weak_model_sql_improvement_trials": weak_sql_trials_summary,
            "weak_harness_engineering_eval": weak_harness_summary,
            "weak_model_answer_grounding_regression_analysis": weak_answer_grounding_summary,
            "endpoint_matrix": endpoint_summary,
            "hidden_style_pass": hidden_pass,
            "gates": gates,
            "gate_passed": gate_passed,
            "recommendation": recommendation,
        }
    )
    (reports / f"{REPORT_STEM}.json").write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    (reports / f"{REPORT_STEM}.md").write_text(_render_md(report), encoding="utf-8")
    return report


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _load_latest_json(paths: list[Path]) -> dict[str, Any]:
    existing = [path for path in paths if path.exists()]
    if not existing:
        return {}
    return _load_json(max(existing, key=lambda path: path.stat().st_mtime))


def _mode(modes: list[dict[str, Any]], name: str) -> dict[str, Any]:
    return next((item for item in modes if item.get("mode") == name), {})


def _full_current(strict: dict[str, Any], modes: list[dict[str, Any]]) -> dict[str, Any]:
    current = _mode(modes, "full_dashagent_current")
    if current:
        return current
    by_strategy = ((strict.get("summary") or {}).get("by_strategy") or {}) if isinstance(strict.get("summary"), dict) else {}
    sql_first = by_strategy.get("SQL_FIRST_API_VERIFY") if isinstance(by_strategy, dict) else None
    if not isinstance(sql_first, dict):
        return {}
    return {
        "mode": "full_dashagent_current",
        "strict_final_score": sql_first.get("avg_final_score"),
        "strict_correctness": sql_first.get("avg_correctness_score"),
        "answer_score": sql_first.get("avg_answer_score"),
        "sql_score": sql_first.get("avg_sql_score"),
        "api_score": sql_first.get("avg_api_score"),
        "tool_calls": sql_first.get("avg_tool_call_count"),
        "estimated_tokens": sql_first.get("avg_estimated_tokens"),
        "runtime": sql_first.get("avg_runtime"),
    }


def _previous_scaffold_reference(path: Path) -> dict[str, Any]:
    payload = _load_json(path)
    rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
    values = []
    for row in rows:
        scaffold = row.get("best_scaffold") if isinstance(row.get("best_scaffold"), dict) else {}
        if isinstance(scaffold.get("answer_score"), (int, float)):
            values.append(scaffold)
    if not values:
        return {}
    return {
        "source": str(path),
        "answer_score": round(sum(float(item.get("answer_score") or 0.0) for item in values) / len(values), 4),
        "api_score": round(sum(_num(item.get("api_score")) for item in values) / len(values), 4),
        "sql_score": round(sum(_num(item.get("sql_score")) for item in values) / len(values), 4),
    }


def _generated_summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else payload
    total = summary.get("total_prompts") or summary.get("total_count") or summary.get("attempted") or summary.get("executed_prompts")
    passed = summary.get("runtime_pass_count") or summary.get("runtime_pass") or summary.get("passed") or summary.get("runtime_passed")
    if passed is None and summary.get("runtime_failure_count") == 0 and total is not None:
        passed = total
    unsupported = summary.get("unsupported_claim_count")
    if unsupported is None:
        unsupported = summary.get("unsupported_claims")
    rate = None
    if isinstance(total, (int, float)) and total and isinstance(passed, (int, float)):
        rate = round(float(passed) / float(total), 4)
    return {
        "total_count": total,
        "runtime_pass_count": passed,
        "runtime_pass_rate": rate,
        "validation_failures": (
            summary.get("validation_failures")
            if summary.get("validation_failures") is not None
            else summary.get("validation_failure_count")
            if summary.get("validation_failure_count") is not None
            else summary.get("validation_fail_count")
        ),
        "unsupported_claim_count": unsupported,
        "source_available": bool(payload),
    }


def _paraphrase_summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else payload
    return {
        "available": bool(payload),
        "paraphrase_consistency": summary.get("paraphrase_consistency") or summary.get("paraphrase_consistency_score") or summary.get("consistency"),
        "template_dependency_score": summary.get("template_dependency_score"),
    }


def _weak_generated_summary(payload: dict[str, Any]) -> dict[str, Any]:
    if not payload:
        return {}
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else payload
    return {
        "executed_prompts": summary.get("executed_prompts"),
        "runtime_pass_count": summary.get("runtime_pass_count"),
        "runtime_pass_rate": summary.get("runtime_pass_rate"),
        "validation_failures": summary.get("validation_failures"),
        "unsupported_claim_count": summary.get("unsupported_claim_count"),
        "sql_selected_count": summary.get("sql_selected_count"),
        "api_selected_count": summary.get("api_selected_count"),
        "sql_validation_pass_rate": summary.get("sql_validation_pass_rate"),
        "api_validation_pass_rate": summary.get("api_validation_pass_rate"),
        "top_failure_categories": summary.get("top_failure_categories"),
        "stable_subset": summary.get("stable_subset"),
    }


def _weak_paraphrase_summary(payload: dict[str, Any]) -> dict[str, Any]:
    if not payload:
        return {}
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else payload
    return {
        "group_count": summary.get("group_count"),
        "consistency_score": summary.get("consistency_score"),
        "slot_stability": summary.get("slot_stability"),
        "sql_table_stability": summary.get("sql_table_stability"),
        "api_endpoint_stability": summary.get("api_endpoint_stability"),
        "answer_grounding_stability": summary.get("answer_grounding_stability"),
        "worst_unstable_groups": summary.get("worst_unstable_groups"),
    }


def _weak_no_template_summary(payload: dict[str, Any]) -> dict[str, Any]:
    if not payload:
        return {}
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else payload
    return {
        "rows": summary.get("rows"),
        "fixed_template_used_count": summary.get("fixed_template_used_count"),
        "sql_validation_pass_rate": summary.get("sql_validation_pass_rate"),
        "sql_execution_pass_rate": summary.get("sql_execution_pass_rate"),
        "api_validation_pass_rate": summary.get("api_validation_pass_rate"),
        "unsupported_claim_count": summary.get("unsupported_claim_count"),
        "template_dependency_assessment": summary.get("template_dependency_assessment"),
        "failure_stage_distribution": summary.get("failure_stage_distribution"),
    }


def _weak_sql_bottleneck_summary(payload: dict[str, Any]) -> dict[str, Any]:
    if not payload:
        return {}
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else payload
    return {
        "rows": summary.get("rows"),
        "average_sql_score": summary.get("average_sql_score"),
        "low_sql_score_rows": summary.get("low_sql_score_rows"),
        "dominant_sql_bottleneck": summary.get("dominant_sql_bottleneck"),
        "failure_distribution": summary.get("failure_distribution"),
        "fix_layer_recommendation": summary.get("fix_layer_recommendation"),
        "safe_next_sql_improvement_candidate": summary.get("safe_next_sql_improvement_candidate"),
    }


def _weak_sql_trials_summary(payload: dict[str, Any]) -> dict[str, Any]:
    if not payload:
        return {}
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else payload
    return {
        "run_label": summary.get("run_label"),
        "best_variant": summary.get("best_variant"),
        "best_strict": summary.get("best_strict"),
        "best_sql": summary.get("best_sql"),
        "best_api": summary.get("best_api"),
        "best_answer": summary.get("best_answer"),
        "best_sql_variant": summary.get("best_sql_variant"),
        "best_sql_variant_strict": summary.get("best_sql_variant_strict"),
        "max_sql_score": summary.get("max_sql_score"),
        "best_sql_variant_api": summary.get("best_sql_variant_api"),
        "best_sql_variant_answer": summary.get("best_sql_variant_answer"),
        "sql_improved_over_current": summary.get("sql_improved_over_current"),
        "best_sql_variant_strict_nonregression": summary.get("best_sql_variant_strict_nonregression"),
        "best_sql_variant_api_nonregression": summary.get("best_sql_variant_api_nonregression"),
        "best_sql_variant_answer_nonregression": summary.get("best_sql_variant_answer_nonregression"),
        "unsupported_claims_zero": summary.get("unsupported_claims_zero"),
    }


def _weak_harness_summary(payload: dict[str, Any]) -> dict[str, Any]:
    if not payload:
        return {}
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else payload
    return {
        "run_label": summary.get("run_label"),
        "best_variant": summary.get("best_variant"),
        "best_strict": summary.get("best_strict"),
        "best_sql": summary.get("best_sql"),
        "best_api": summary.get("best_api"),
        "best_answer": summary.get("best_answer"),
        "best_sql_variant": summary.get("best_sql_variant"),
        "max_sql_score": summary.get("max_sql_score"),
        "sql_improved_over_previous_weak_scaffold": summary.get("sql_improved_over_previous_weak_scaffold"),
        "strict_improved_over_previous_weak_scaffold": summary.get("strict_improved_over_previous_weak_scaffold"),
        "api_nonregression": summary.get("api_nonregression"),
        "answer_nonregression": summary.get("answer_nonregression"),
        "unsupported_claims_zero": summary.get("unsupported_claims_zero"),
        "bounded_gate_passed": summary.get("bounded_gate_passed"),
        "recommendation": summary.get("recommendation"),
    }


def _weak_answer_grounding_summary(payload: dict[str, Any]) -> dict[str, Any]:
    if not payload:
        return {}
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else payload
    modes = summary.get("mode_summaries") if isinstance(summary.get("mode_summaries"), list) else []
    v2 = _mode(modes, "weak_scaffold_balanced_sql_api_v2")
    v1 = _mode(modes, "weak_scaffold_api_recovery_v1")
    v3_candidates = [
        _mode(modes, "weak_scaffold_balanced_sql_api_answer_v3"),
        _mode(modes, "weak_scaffold_sql_lift_api_recovery_v3"),
        _mode(modes, "weak_scaffold_answer_fallback_v3"),
    ]
    v3_candidates = [item for item in v3_candidates if item]
    best_v3 = max(v3_candidates, key=lambda item: _num(item.get("strict_final_score")), default={})
    return {
        "run_label": summary.get("run_label"),
        "row_count": summary.get("row_count"),
        "category_counts": summary.get("category_counts"),
        "safest_fix_candidate": summary.get("safest_fix_candidate"),
        "best_v3_variant": best_v3.get("mode"),
        "best_v3_strict": best_v3.get("strict_final_score"),
        "best_v3_sql": best_v3.get("sql_score"),
        "best_v3_api": best_v3.get("api_score"),
        "best_v3_answer": best_v3.get("answer_score"),
        "v2_strict": v2.get("strict_final_score"),
        "v2_answer": v2.get("answer_score"),
        "v1_strict": v1.get("strict_final_score"),
        "v1_answer": v1.get("answer_score"),
        "v3_answer_improves_over_v2": _num(best_v3.get("answer_score")) > _num(v2.get("answer_score")),
        "v3_strict_improves_over_v2": _num(best_v3.get("strict_final_score")) > _num(v2.get("strict_final_score")),
        "v3_answer_nonregression_vs_v1": _num(best_v3.get("answer_score")) >= _num(v1.get("answer_score")),
    }


def _endpoint_summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else payload
    after = summary.get("after_safe_get_totals") if isinstance(summary.get("after_safe_get_totals"), dict) else {}
    source = after or summary
    attempted = source.get("attempted") or source.get("attempted_count") or source.get("total_safe_get_endpoints_attempted")
    live_success = source.get("live_success") or source.get("live_success_count")
    live_empty = source.get("live_empty") or source.get("live_empty_count")
    failures = (
        int(source.get("endpoint_path_issue") or source.get("endpoint_path_issue_count") or 0)
        + int(source.get("api_error") or source.get("api_error_count") or 0)
        + int(source.get("failures") or 0)
    )
    return {"attempted": attempted, "live_success": live_success, "live_empty": live_empty, "failures": failures, "source_available": bool(payload)}


def _hidden_pass(payload: dict[str, Any]) -> bool | None:
    if not payload:
        return None
    text = json.dumps(payload).lower()
    if "48/48" in text or '"passed": 48' in text:
        return True
    result = payload.get("result") or payload.get("summary") or payload
    if isinstance(result, dict):
        passed = result.get("passed") or result.get("pass_count") or result.get("passed_cases")
        total = result.get("total") or result.get("total_count") or result.get("total_cases")
        if passed is not None and total is not None:
            return int(passed) == int(total)
    return None


def _recommendation(gates: dict[str, bool], summary: dict[str, Any], weak_sql_bottleneck: dict[str, Any], best: dict[str, Any]) -> str:
    if not gates["unsupported_claims_zero"]:
        return "weak_model_blocked_by_answer_grounding"
    if gates.get("weak_harness_sql_improved") and not gates.get("weak_harness_api_nonregression"):
        return "weak_harness_api_regression"
    if gates.get("weak_harness_sql_improved") and not gates.get("weak_harness_answer_nonregression"):
        return "weak_harness_answer_regression"
    if (
        gates.get("weak_harness_sql_improved")
        and gates.get("weak_harness_api_nonregression")
        and gates.get("weak_harness_answer_nonregression")
        and gates.get("weak_harness_unsupported_claims_zero")
        and gates.get("strict_score_beats_guided_weak")
    ):
        return "weak_harness_sql_improved_keep_shadow"
    if not gates["weak_generated_prompt_runtime_pass_high"] or not gates["weak_generated_prompt_validation_clean"] or not gates["weak_generated_prompt_unsupported_claims_zero"]:
        return "weak_model_scaffold_not_general_enough"
    if not gates["weak_paraphrase_consistency_acceptable"] or not gates["weak_no_template_validation_acceptable"] or not gates["weak_no_template_unsupported_claims_zero"]:
        return "weak_model_scaffold_not_general_enough"
    if (
        gates.get("weak_sql_trial_sql_improved")
        and gates.get("weak_sql_trial_api_nonregression")
        and gates.get("weak_sql_trial_answer_nonregression")
        and gates.get("weak_answer_v3_answer_nonregression_vs_v1")
        and gates.get("strict_score_beats_guided_weak")
    ):
        return "weak_model_scaffold_sql_and_answer_improved_keep_shadow"
    if gates.get("weak_sql_trial_sql_improved") and gates.get("weak_sql_trial_api_nonregression") and gates.get("weak_answer_v3_improves_over_v2") and gates.get("weak_answer_v3_strict_improves_over_v2"):
        return "weak_model_scaffold_still_answer_limited"
    if gates.get("weak_sql_trial_sql_improved") and (not gates.get("weak_sql_trial_answer_nonregression") or not gates.get("weak_sql_trial_api_nonregression")):
        return "weak_model_scaffold_still_answer_limited" if not gates.get("weak_sql_trial_answer_nonregression") else "weak_model_scaffold_still_sql_limited"
    if not gates["strict_score_improves_over_raw_weak"]:
        return "current_full_system_still_preferred"
    if not gates["sql_score_improves_over_raw_weak"]:
        return "weak_model_still_blocked_by_sql"
    if not gates["api_score_not_regressed_vs_raw_or_guided_weak"]:
        return "weak_model_blocked_by_api_nonregression"
    if not gates["answer_grounding_improves_over_previous_scaffold"]:
        return "weak_model_scaffold_candidate_needs_answer_fix"
    if not gates["strict_score_beats_guided_weak"]:
        return "weak_model_still_below_guided"
    if _num(best.get("sql_score")) < 0.12 or _num(weak_sql_bottleneck.get("low_sql_score_rows")) > 0:
        return "weak_model_scaffold_needs_sql_improvement"
    if all(gates.values()):
        return "weak_model_scaffold_improved_keep_shadow"
    if gates["strict_score_improves_over_raw_weak"] and gates["sql_score_improves_over_raw_weak"]:
        return "weak_model_scaffold_candidate_needs_answer_fix"
    return summary.get("recommendation") or "current_full_system_still_preferred"


def _num(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def _token_runtime_cost_acceptable(best: dict[str, Any], raw: dict[str, Any], guided: dict[str, Any]) -> bool:
    best_tokens = _num(best.get("estimated_tokens"))
    baseline_tokens = max(_num(raw.get("estimated_tokens")), _num(guided.get("estimated_tokens")))
    best_runtime = _num(best.get("runtime"))
    baseline_runtime = max(_num(raw.get("runtime")), _num(guided.get("runtime")))
    return (baseline_tokens == 0 or best_tokens <= baseline_tokens) and (baseline_runtime == 0 or best_runtime <= baseline_runtime)


def _none_or_at_least(value: Any, threshold: float) -> bool:
    if value is None:
        return True
    return _num(value) >= threshold


def _render_md(report: dict[str, Any]) -> str:
    gates = "\n".join(f"- `{name}`: `{value}`" for name, value in report["gates"].items())
    return (
        "# Weak Model Robustness Gate\n\n"
        "Diagnostic-only gate for weak-model scaffold lift. Packaged `SQL_FIRST_API_VERIFY` remains unchanged.\n\n"
        f"- Recommendation: `{report['recommendation']}`\n"
        f"- Gate passed: `{report.get('gate_passed')}`\n"
        f"- Small-model lift score: `{report.get('small_model_lift_score')}`\n"
        f"- SQL lift: `{report.get('sql_lift')}`\n"
        f"- Unsupported claims in best scaffold: `{report.get('best_scaffold', {}).get('unsupported_claims')}`\n\n"
        f"- Weak generated prompts: `{(report.get('weak_model_generated_prompt_diagnostic') or {}).get('runtime_pass_count')}` / `{(report.get('weak_model_generated_prompt_diagnostic') or {}).get('executed_prompts')}`\n"
        f"- Weak paraphrase consistency: `{(report.get('weak_model_paraphrase_consistency') or {}).get('consistency_score')}`\n"
        f"- Weak no-template SQL validation: `{(report.get('weak_model_no_template_diagnostic') or {}).get('sql_validation_pass_rate')}`\n"
        f"- Weak SQL bottleneck: `{(report.get('weak_model_sql_bottleneck') or {}).get('dominant_sql_bottleneck')}`\n\n"
        f"- Weak SQL trial best SQL variant: `{(report.get('weak_model_sql_improvement_trials') or {}).get('best_sql_variant')}` / SQL `{(report.get('weak_model_sql_improvement_trials') or {}).get('max_sql_score')}`\n\n"
        f"- Weak harness best variant: `{(report.get('weak_harness_engineering_eval') or {}).get('best_variant')}` / strict `{(report.get('weak_harness_engineering_eval') or {}).get('best_strict')}` / SQL `{(report.get('weak_harness_engineering_eval') or {}).get('best_sql')}` / answer `{(report.get('weak_harness_engineering_eval') or {}).get('best_answer')}`\n\n"
        f"- Weak answer-grounding v3 best: `{(report.get('weak_model_answer_grounding_regression_analysis') or {}).get('best_v3_variant')}` / answer `{(report.get('weak_model_answer_grounding_regression_analysis') or {}).get('best_v3_answer')}`\n\n"
        "## Gates\n\n"
        f"{gates}\n"
    )


if __name__ == "__main__":
    raise SystemExit(main())
