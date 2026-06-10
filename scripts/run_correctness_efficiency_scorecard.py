#!/usr/bin/env python
from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.trajectory import redact_secrets


SCORECARD_STEM = "correctness_efficiency_scorecard"
FIX_DECISION_STEM = "correctness_efficiency_fix_decision"
BASELINE_STRATEGY = "SQL_FIRST_API_VERIFY"
EPSILON_RUNTIME = 0.001
EFFICIENCY_CAP = 1.25
REGRESSION_TOLERANCE = 1e-9
SPEED_PATCH_PRIORITY = [
    "compact_tool_schema",
    "compact_tool_result_evidence_summary",
    "no_rewrite_when_backend_complete",
    "disable_parallel_tool_calls",
    "allowed_tools_by_prompt_type",
    "combined_safe_tool_policy",
]


def main() -> int:
    config = Config.from_env(ROOT)
    payload = run_correctness_efficiency_scorecard(config)
    print(
        json.dumps(
            {
                "scorecard": str(config.outputs_dir / "reports" / f"{SCORECARD_STEM}.json"),
                "fix_decision": str(config.outputs_dir / "reports" / f"{FIX_DECISION_STEM}.json"),
                "decision": payload["fix_decision"].get("decision"),
                "runtime_change_applied": payload["fix_decision"].get("runtime_change_applied"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def run_correctness_efficiency_scorecard(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    sources = _load_sources(config)
    strict = sources["eval_results_strict"]
    baseline = _baseline_metrics(config, strict, sources)
    strategies = _strategy_rows(strict, baseline)
    variants = _variant_rows(sources, baseline)
    _rank_variants(variants)
    sdk_review = _sdk_speed_candidate_review(variants)
    fix_decision = _fix_decision(baseline, variants, sources)
    scorecard = {
        "report_type": SCORECARD_STEM,
        "generated_at": _now(),
        "purpose": "Sensitivity scorecard for workshop-style correctness plus efficiency evaluation.",
        "organizer_weights_known": False,
        "official_overall_score_claim": False,
        "diagnostic_only": True,
        "runtime_change_applied": False,
        "writes_official_eval_artifacts": False,
        "writes_final_submission": False,
        "baseline_strategy": BASELINE_STRATEGY,
        "baseline": baseline,
        "strategies": strategies,
        "variants": variants,
        "sdk_speed_candidate_review": sdk_review,
        "formulas": _formulas(),
        "composite_scenarios": _scenario_definitions(),
        "rankings": _scenario_rankings(variants),
        "fix_decision": fix_decision,
        "source_reports": [
            "outputs/eval_results_strict.json",
            "outputs/reports/sdk_tool_calling_optimization_trials.json",
            "outputs/reports/sdk_tool_calling_fix_decision.json",
            "outputs/reports/score_focused_core_improvement_trials.json",
            "outputs/reports/system_summary.json",
            "outputs/reports/accuracy_and_bottleneck_summary.json",
        ],
        "notes": [
            "Correctness-only strict score is not treated as the full evaluation picture.",
            "Efficiency dimensions are reported separately because organizer weights are not known.",
            "Composite scenarios are sensitivity analysis, not official rankings.",
            "Speed-only candidates require strict/hidden/submission validation before any runtime patch.",
        ],
    }
    scorecard = _safe(scorecard)
    fix_decision = _safe(fix_decision)
    _write_json(reports_dir / f"{SCORECARD_STEM}.json", scorecard)
    (reports_dir / f"{SCORECARD_STEM}.md").write_text(_render_scorecard(scorecard), encoding="utf-8")
    _write_json(reports_dir / f"{FIX_DECISION_STEM}.json", fix_decision)
    (reports_dir / f"{FIX_DECISION_STEM}.md").write_text(_render_fix_decision(fix_decision), encoding="utf-8")
    return {"scorecard": scorecard, "fix_decision": fix_decision}


def _baseline_metrics(config: Config, strict: dict[str, Any], sources: dict[str, Any]) -> dict[str, Any]:
    by_strategy = ((strict.get("summary") or {}).get("by_strategy") or {})
    metrics = by_strategy.get(BASELINE_STRATEGY) or _aggregate_strategy(strict, BASELINE_STRATEGY)
    system = sources.get("system_summary") or {}
    hidden = system.get("hidden_style") or {}
    avg_turns = _average_turns_from_trajectories(strict)
    runtime = _number(metrics.get("avg_runtime"))
    preprocessing = _number(metrics.get("avg_preprocessing_time"))
    planning = _number(metrics.get("avg_planning_time"))
    execution = _number(metrics.get("avg_execution_time"))
    answer = _number(metrics.get("avg_answer_time"))
    return {
        "strategy": BASELINE_STRATEGY,
        "correctness_score": _round(metrics.get("avg_correctness_score") or metrics.get("avg_final_score")),
        "strict_final_score": _round(metrics.get("avg_final_score") or system.get("packaged_strict_score")),
        "sql_score": _round(metrics.get("avg_sql_score")),
        "api_score": _round(metrics.get("avg_api_score")),
        "response_score": _round(metrics.get("avg_answer_score")),
        "turns": avg_turns,
        "turns_source": "trajectory_json" if avg_turns is not None else "unavailable_in_strict_artifacts",
        "tool_calls": _round(metrics.get("avg_tool_call_count")),
        "total_tokens": _round(metrics.get("avg_estimated_tokens")),
        "prompt_tokens": _round(metrics.get("avg_prompt_tokens")),
        "metadata_tokens": _round(metrics.get("avg_metadata_tokens")),
        "wall_time_seconds": _round(runtime),
        "preprocessing_time_seconds": _round(preprocessing),
        "planning_time_seconds": _round(planning),
        "execution_time_seconds": _round(execution),
        "answer_time_seconds": _round(answer),
        "end_to_end_time_seconds": _round(_sum_available([runtime, preprocessing, planning, execution, answer])),
        "hidden_style_status": hidden.get("label") or _hidden_label(hidden),
        "final_submission_ready": system.get("final_submission_ready"),
        "direct_http_hits": _direct_http_hits(sources),
        "unsupported_claim_delta": 0,
        "final_submission_format_changed": False,
    }


def _strategy_rows(strict: dict[str, Any], baseline: dict[str, Any]) -> list[dict[str, Any]]:
    strategies = []
    for strategy, metrics in (((strict.get("summary") or {}).get("by_strategy") or {}).items()):
        runtime = _number(metrics.get("avg_runtime"))
        preprocessing = _number(metrics.get("avg_preprocessing_time"))
        planning = _number(metrics.get("avg_planning_time"))
        execution = _number(metrics.get("avg_execution_time"))
        answer = _number(metrics.get("avg_answer_time"))
        row = {
            "strategy": strategy,
            "correctness_score": _round(metrics.get("avg_correctness_score") or metrics.get("avg_final_score")),
            "strict_final_score": _round(metrics.get("avg_final_score")),
            "sql_score": _round(metrics.get("avg_sql_score")),
            "api_score": _round(metrics.get("avg_api_score")),
            "response_score": _round(metrics.get("avg_answer_score")),
            "turns": None,
            "tool_calls": _round(metrics.get("avg_tool_call_count")),
            "total_tokens": _round(metrics.get("avg_estimated_tokens")),
            "wall_time_seconds": _round(runtime),
            "preprocessing_time_seconds": _round(preprocessing),
            "end_to_end_time_seconds": _round(_sum_available([runtime, preprocessing, planning, execution, answer])),
        }
        row["relative_efficiency"] = _efficiency_scores(baseline, row)
        strategies.append(row)
    return strategies


def _variant_rows(sources: dict[str, Any], baseline: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    sdk_trials = sources.get("sdk_tool_calling_optimization_trials") or {}
    for variant in sdk_trials.get("variants") or []:
        rows.append(_project_sdk_variant(variant, baseline))
    score_trials = sources.get("score_focused_core_improvement_trials") or {}
    for variant in score_trials.get("variant_reports") or []:
        rows.append(_project_score_focused_variant(variant, baseline))
    return rows


def _project_sdk_variant(variant: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    strict_delta = _number(variant.get("strict_score_delta")) or 0.0
    correctness_delta = _number(variant.get("correctness_score_delta"))
    if correctness_delta is None:
        correctness_delta = strict_delta
    token_delta = _number(variant.get("total_tokens_delta"))
    if token_delta is None:
        token_delta = _number(variant.get("token_input_estimate_delta")) or 0.0
    row = _project_variant_common(
        baseline,
        variant_id=str(variant.get("variant_id")),
        source="sdk_tool_calling_optimization_trials",
        correctness_delta=correctness_delta,
        strict_delta=strict_delta,
        sql_delta=_number(variant.get("sql_score_delta")) or 0.0,
        api_delta=_number(variant.get("api_score_delta")) or 0.0,
        response_delta=_number(variant.get("answer_score_delta")) or 0.0,
        turns_delta=_number(variant.get("turns_delta")),
        tool_delta=_number(variant.get("tool_call_count_delta")) or 0.0,
        token_delta=token_delta,
        runtime_delta=_number(variant.get("runtime_delta_seconds_estimate")) or 0.0,
        unsupported_claim_delta=int(variant.get("unsupported_claim_delta") or 0),
        high_scoring_rows_hurt=int(variant.get("high_scoring_rows_hurt") or 0),
        final_submission_format_changed=bool(variant.get("final_submission_format_changed", False)),
        direct_http_hits=int(variant.get("direct_http_hits") or 0),
        hardcoding_detected=bool(
            variant.get("hardcoded_query_id_trigger")
            or variant.get("hardcoded_prompt_id_trigger")
            or variant.get("hardcoded_exact_prompt_trigger")
        ),
        trial_mode=variant.get("trial_mode", "artifact_replay"),
    )
    row["token_output_delta"] = _number(variant.get("token_output_estimate_delta")) or 0.0
    return row


def _project_score_focused_variant(variant: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    strict_delta = _number(variant.get("strict_score_delta")) or 0.0
    return _project_variant_common(
        baseline,
        variant_id=str(variant.get("variant")),
        source="score_focused_core_improvement_trials",
        correctness_delta=strict_delta,
        strict_delta=strict_delta,
        sql_delta=0.0,
        api_delta=0.0,
        response_delta=_number(variant.get("answer_score_delta_avg")) or 0.0,
        turns_delta=None,
        tool_delta=_number(variant.get("tool_delta_avg")) or 0.0,
        token_delta=_number(variant.get("token_delta_avg")) or 0.0,
        runtime_delta=_number(variant.get("runtime_delta_avg")) or 0.0,
        unsupported_claim_delta=int(variant.get("unsupported_claim_delta") or 0),
        high_scoring_rows_hurt=int(variant.get("high_score_regressions") or 0),
        final_submission_format_changed=bool(variant.get("final_submission_would_change", False)),
        direct_http_hits=0,
        hardcoding_detected=False,
        trial_mode="artifact_replay",
    )


def _project_variant_common(
    baseline: dict[str, Any],
    *,
    variant_id: str,
    source: str,
    correctness_delta: float,
    strict_delta: float,
    sql_delta: float,
    api_delta: float,
    response_delta: float,
    turns_delta: float | None,
    tool_delta: float,
    token_delta: float,
    runtime_delta: float,
    unsupported_claim_delta: int,
    high_scoring_rows_hurt: int,
    final_submission_format_changed: bool,
    direct_http_hits: int,
    hardcoding_detected: bool,
    trial_mode: str,
) -> dict[str, Any]:
    projected = {
        "turns": _project_metric(baseline.get("turns"), turns_delta, minimum=1.0),
        "tool_calls": _project_metric(baseline.get("tool_calls"), tool_delta, minimum=1.0),
        "total_tokens": _project_metric(baseline.get("total_tokens"), token_delta, minimum=1.0),
        "wall_time_seconds": _project_metric(baseline.get("wall_time_seconds"), runtime_delta, minimum=EPSILON_RUNTIME),
        "end_to_end_time_seconds": _project_metric(
            baseline.get("end_to_end_time_seconds"), runtime_delta, minimum=EPSILON_RUNTIME
        ),
    }
    correctness_score = _round((_number(baseline.get("correctness_score")) or 0.0) + correctness_delta)
    row = {
        "variant_id": variant_id,
        "source": source,
        "trial_mode": trial_mode,
        "correctness_score": correctness_score,
        "correctness_delta": _round(correctness_delta),
        "strict_final_score_projected": _round((_number(baseline.get("strict_final_score")) or 0.0) + strict_delta),
        "strict_score_delta": _round(strict_delta),
        "sql_score": _round((_number(baseline.get("sql_score")) or 0.0) + sql_delta),
        "api_score": _round((_number(baseline.get("api_score")) or 0.0) + api_delta),
        "response_score": _round((_number(baseline.get("response_score")) or 0.0) + response_delta),
        "efficiency": {
            "turns_delta": _round(turns_delta),
            "tool_calls_delta": _round(tool_delta),
            "total_tokens_delta": _round(token_delta),
            "wall_time_delta": _round(runtime_delta),
            "end_to_end_time_delta": _round(runtime_delta),
            **projected,
        },
        "safety": {
            "hidden_style_required": True,
            "check_submission_ready_required": True,
            "direct_http_hits": direct_http_hits,
            "unsupported_claim_delta": unsupported_claim_delta,
            "high_scoring_rows_hurt": high_scoring_rows_hurt,
            "final_submission_format_changed": final_submission_format_changed,
            "hardcoding_detected": hardcoding_detected,
        },
    }
    row["efficiency_scores"] = _efficiency_scores(baseline, projected)
    row["composite_scores"] = _composite_scores(row)
    row["pareto_dominates_baseline"] = _pareto_dominates_baseline(row)
    row["promotion_candidate_status"] = _promotion_candidate_status(row)
    return row


def _efficiency_scores(baseline: dict[str, Any], metrics: dict[str, Any]) -> dict[str, Any]:
    turns_eff = _ratio(baseline.get("turns"), metrics.get("turns"), neutral_if_missing=True)
    tool_eff = _ratio(baseline.get("tool_calls"), metrics.get("tool_calls"))
    token_eff = _ratio(baseline.get("total_tokens"), metrics.get("total_tokens"))
    runtime_eff = _ratio(baseline.get("wall_time_seconds"), metrics.get("wall_time_seconds"), runtime=True)
    equal = _weighted_average([turns_eff, tool_eff, token_eff, runtime_eff], [0.25, 0.25, 0.25, 0.25])
    return {
        "turns_efficiency": _round(turns_eff),
        "tool_call_efficiency": _round(tool_eff),
        "token_efficiency": _round(token_eff),
        "runtime_efficiency": _round(runtime_eff),
        "efficiency_score_equal_weight": _round(equal),
        "efficiency_tool_heavy": _round(_weighted_average([turns_eff, tool_eff, token_eff, runtime_eff], [0.1, 0.5, 0.2, 0.2])),
        "efficiency_token_heavy": _round(_weighted_average([turns_eff, tool_eff, token_eff, runtime_eff], [0.1, 0.2, 0.5, 0.2])),
        "efficiency_runtime_heavy": _round(_weighted_average([turns_eff, tool_eff, token_eff, runtime_eff], [0.1, 0.2, 0.2, 0.5])),
        "efficiency_turn_heavy": _round(_weighted_average([turns_eff, tool_eff, token_eff, runtime_eff], [0.5, 0.2, 0.15, 0.15])),
        "turns_efficiency_source": "neutral_1_0_when_turns_unavailable" if baseline.get("turns") is None else "trajectory_json",
    }


def _composite_scores(row: dict[str, Any]) -> dict[str, Any]:
    correctness = _number(row.get("correctness_score")) or 0.0
    efficiency = row["efficiency_scores"]["efficiency_score_equal_weight"]
    return {
        "correctness_dominant": _round(0.80 * correctness + 0.20 * efficiency),
        "balanced": _round(0.60 * correctness + 0.40 * efficiency),
        "efficiency_sensitive": _round(0.50 * correctness + 0.50 * efficiency),
        "strict_no_regression_efficiency_rank_score": _round(efficiency if row.get("correctness_delta", -1) >= -REGRESSION_TOLERANCE else -1),
        "hidden_safe_efficiency_rank_score": _round(
            efficiency
            if row.get("correctness_delta", -1) >= -REGRESSION_TOLERANCE and _safety_gate_for_rank(row)
            else -1
        ),
    }


def _rank_variants(variants: list[dict[str, Any]]) -> None:
    scenarios = [
        "correctness_dominant",
        "balanced",
        "efficiency_sensitive",
        "strict_no_regression_efficiency_rank_score",
        "hidden_safe_efficiency_rank_score",
    ]
    rank_names = {
        "strict_no_regression_efficiency_rank_score": "strict_no_regression_efficiency_rank",
        "hidden_safe_efficiency_rank_score": "hidden_safe_efficiency_rank",
    }
    for scenario in scenarios:
        ordered = sorted(
            variants,
            key=lambda row: (row["composite_scores"].get(scenario, -1), row["efficiency_scores"]["efficiency_score_equal_weight"]),
            reverse=True,
        )
        for rank, row in enumerate(ordered, start=1):
            row.setdefault("scenario_ranks", {})[rank_names.get(scenario, scenario)] = rank


def _scenario_rankings(variants: list[dict[str, Any]]) -> dict[str, list[str]]:
    rankings: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for row in variants:
        for scenario, rank in row.get("scenario_ranks", {}).items():
            rankings[scenario].append((rank, row["variant_id"]))
    return {scenario: [variant for _, variant in sorted(items)] for scenario, items in rankings.items()}


def _pareto_dominates_baseline(row: dict[str, Any]) -> bool:
    if (_number(row.get("correctness_delta")) or 0.0) < -REGRESSION_TOLERANCE:
        return False
    efficiency = row["efficiency"]
    deltas = [
        efficiency.get("turns_delta"),
        efficiency.get("tool_calls_delta"),
        efficiency.get("total_tokens_delta"),
        efficiency.get("wall_time_delta"),
        efficiency.get("end_to_end_time_delta"),
    ]
    numeric = [float(delta) for delta in deltas if isinstance(delta, (int, float))]
    any_better = any(delta < -REGRESSION_TOLERANCE for delta in numeric)
    none_worse = all(delta <= REGRESSION_TOLERANCE for delta in numeric)
    return any_better and none_worse


def _promotion_candidate_status(row: dict[str, Any]) -> str:
    safety = row.get("safety") or {}
    if (_number(row.get("correctness_delta")) or 0.0) < -REGRESSION_TOLERANCE:
        return "reject"
    if int(safety.get("direct_http_hits") or 0) != 0:
        return "reject"
    if int(safety.get("unsupported_claim_delta") or 0) > 0:
        return "reject"
    if int(safety.get("high_scoring_rows_hurt") or 0) > 0:
        return "reject"
    if safety.get("final_submission_format_changed") or safety.get("hardcoding_detected"):
        return "reject"
    if row.get("pareto_dominates_baseline"):
        return "efficiency_candidate_needs_strict_validation"
    return "keep_shadow_only"


def _safety_gate_for_rank(row: dict[str, Any]) -> bool:
    safety = row.get("safety") or {}
    return (
        int(safety.get("direct_http_hits") or 0) == 0
        and int(safety.get("unsupported_claim_delta") or 0) <= 0
        and int(safety.get("high_scoring_rows_hurt") or 0) == 0
        and not safety.get("final_submission_format_changed")
        and not safety.get("hardcoding_detected")
    )


def _sdk_speed_candidate_review(variants: list[dict[str, Any]]) -> list[dict[str, Any]]:
    reviewed_ids = {
        "combined_safe_tool_policy",
        "allowed_tools_by_prompt_type",
        "compact_tool_schema",
        "compact_tool_result_evidence_summary",
        "tool_choice_policy",
        "no_rewrite_when_backend_complete",
    }
    review = []
    for row in variants:
        if row["variant_id"] not in reviewed_ids:
            continue
        review.append(
            {
                "variant_id": row["variant_id"],
                "correctness_delta": row["correctness_delta"],
                "token_delta": row["efficiency"].get("total_tokens_delta"),
                "tool_call_delta": row["efficiency"].get("tool_calls_delta"),
                "runtime_delta": row["efficiency"].get("wall_time_delta"),
                "composite_scenario_ranks": row.get("scenario_ranks", {}),
                "pareto_dominates_baseline": row.get("pareto_dominates_baseline"),
                "promotion_candidate_status": row.get("promotion_candidate_status"),
            }
        )
    return sorted(review, key=lambda item: SPEED_PATCH_PRIORITY.index(item["variant_id"]) if item["variant_id"] in SPEED_PATCH_PRIORITY else 99)


def _fix_decision(baseline: dict[str, Any], variants: list[dict[str, Any]], sources: dict[str, Any]) -> dict[str, Any]:
    eligible = [row for row in variants if row.get("promotion_candidate_status") == "efficiency_candidate_needs_strict_validation"]
    priority_map = {name: index for index, name in enumerate(SPEED_PATCH_PRIORITY)}
    ranked = sorted(
        eligible,
        key=lambda row: (
            priority_map.get(row["variant_id"], 99),
            -row["efficiency_scores"]["efficiency_score_equal_weight"],
        ),
    )
    if not ranked:
        decision = "keep_shadow_only"
        best = None
        reason = "No speed-only candidate preserved correctness and safety gates in the artifact replay."
    else:
        decision = "speed_only_patch_needs_validation"
        best = ranked[0]
        reason = "At least one speed-only candidate Pareto-dominates the baseline, but evidence is shadow-simulated and still needs strict/hidden/submission validation before implementation."
    return {
        "report_type": FIX_DECISION_STEM,
        "generated_at": _now(),
        "decision": decision,
        "best_candidate": best["variant_id"] if best else None,
        "best_candidate_source": best.get("source") if best else None,
        "recommended_speed_patch_priority": SPEED_PATCH_PRIORITY,
        "ranked_speed_candidates": [
            {
                "variant_id": row["variant_id"],
                "source": row["source"],
                "efficiency_score_equal_weight": row["efficiency_scores"]["efficiency_score_equal_weight"],
                "correctness_delta": row["correctness_delta"],
                "pareto_dominates_baseline": row["pareto_dominates_baseline"],
                "promotion_candidate_status": row["promotion_candidate_status"],
            }
            for row in ranked
        ],
        "promotion_requirements": {
            "correctness_no_regression_required": True,
            "hidden_style_48_48_required": True,
            "check_submission_ready_required": True,
            "direct_http_hits_must_remain_zero": True,
            "final_submission_format_unchanged_required": True,
            "unsupported_claim_increase_allowed": False,
            "high_scoring_official_row_regression_allowed": False,
            "generated_prompt_broad_breakage_allowed": False,
            "hardcoding_allowed": False,
            "patch_must_be_small_and_general": True,
        },
        "follow_up_validation_steps": [
            "Implement at most one selected speed-only patch in the shadow/controller path.",
            "Run python3 scripts/run_dev_eval.py --strict and verify correctness does not regress.",
            "Run python3 scripts/run_hidden_style_eval.py and verify 48/48.",
            "Run python3 scripts/run_generated_prompt_suite_local_diagnostic.py and inspect broad breakage.",
            "Run python3 scripts/check_submission_ready.py.",
            "Run python3 scripts/generate_sdk_usage_audit.py and verify runtime_llm_direct_http_hits=0.",
            "Run python3 -m pytest -q.",
        ],
        "reason": reason,
        "baseline_correctness_score": baseline.get("correctness_score"),
        "baseline_strict_final_score": baseline.get("strict_final_score"),
        "hidden_style_status": baseline.get("hidden_style_status"),
        "final_submission_ready": baseline.get("final_submission_ready"),
        "direct_http_hits": baseline.get("direct_http_hits"),
        "official_overall_score_claim": False,
        "organizer_weights_known": False,
        "runtime_change_applied": False,
        "final_submission_format_changed": False,
        "sdk_fix_decision_prior": (sources.get("sdk_tool_calling_fix_decision") or {}).get("decision"),
    }


def _formulas() -> list[str]:
    return [
        "tool_call_efficiency = baseline_tool_calls / max(variant_tool_calls, 1)",
        "token_efficiency = baseline_tokens / max(variant_tokens, 1)",
        "runtime_efficiency = baseline_runtime / max(variant_runtime, 0.001)",
        "turns_efficiency = baseline_turns / max(variant_turns, 1), or neutral 1.0 when turns are unavailable",
        "each efficiency ratio is capped to [0.0, 1.25]",
        "efficiency_score_equal_weight = average(turns_efficiency, tool_call_efficiency, token_efficiency, runtime_efficiency)",
        "correctness_dominant = 0.80 * correctness_score + 0.20 * efficiency_score_equal_weight",
        "balanced = 0.60 * correctness_score + 0.40 * efficiency_score_equal_weight",
        "efficiency_sensitive = 0.50 * correctness_score + 0.50 * efficiency_score_equal_weight",
    ]


def _scenario_definitions() -> dict[str, Any]:
    return {
        "correctness_dominant": {"formula": "0.80 correctness + 0.20 efficiency"},
        "balanced": {"formula": "0.60 correctness + 0.40 efficiency"},
        "efficiency_sensitive": {"formula": "0.50 correctness + 0.50 efficiency"},
        "strict_no_regression_efficiency_rank": {
            "requirement": "correctness_score >= baseline correctness_score",
            "rank_by": "efficiency_score_equal_weight",
        },
        "hidden_safe_efficiency_rank": {
            "requirement": "correctness_score >= baseline, hidden-style 48/48, check_submission_ready pass, no final-submission format change, direct HTTP hits 0",
            "rank_by": "efficiency_score_equal_weight",
        },
    }


def _aggregate_strategy(strict: dict[str, Any], strategy: str) -> dict[str, Any]:
    rows = [row for row in strict.get("rows") or [] if row.get("strategy") == strategy]
    if not rows:
        return {}
    fields = {
        "avg_correctness_score": "correctness_score",
        "avg_final_score": "final_score",
        "avg_sql_score": "sql_score",
        "avg_api_score": "api_score",
        "avg_answer_score": "answer_score",
        "avg_tool_call_count": "tool_call_count",
        "avg_estimated_tokens": "estimated_tokens",
        "avg_runtime": "runtime",
        "avg_preprocessing_time": "preprocessing_time",
        "avg_planning_time": "planning_time",
        "avg_execution_time": "execution_time",
        "avg_answer_time": "answer_time",
    }
    return {output: _avg(row.get(field) for row in rows) for output, field in fields.items()}


def _average_turns_from_trajectories(strict: dict[str, Any]) -> float | None:
    values = []
    for row in strict.get("rows") or []:
        if row.get("strategy") != BASELINE_STRATEGY:
            continue
        trajectory = row.get("trajectory") if isinstance(row.get("trajectory"), dict) else {}
        for key in ["agent_turn_count", "turn_count", "llm_turn_count"]:
            value = trajectory.get(key) or row.get(key)
            if isinstance(value, (int, float)):
                values.append(float(value))
                break
    return _round(sum(values) / len(values)) if values else None


def _load_sources(config: Config) -> dict[str, Any]:
    reports = config.outputs_dir / "reports"
    return {
        "eval_results_strict": _load_json(config.outputs_dir / "eval_results_strict.json"),
        "sdk_tool_calling_optimization_trials": _load_json(reports / "sdk_tool_calling_optimization_trials.json"),
        "sdk_tool_calling_fix_decision": _load_json(reports / "sdk_tool_calling_fix_decision.json"),
        "score_focused_core_improvement_trials": _load_json(reports / "score_focused_core_improvement_trials.json"),
        "system_summary": _load_json(reports / "system_summary.json"),
        "accuracy_and_bottleneck_summary": _load_json(reports / "accuracy_and_bottleneck_summary.json"),
        "sdk_usage_audit": _load_json(reports / "sdk_usage_audit.json"),
    }


def _direct_http_hits(sources: dict[str, Any]) -> int:
    sdk_usage = sources.get("sdk_usage_audit") or {}
    if isinstance((sdk_usage.get("summary") or {}).get("runtime_llm_direct_http_hits"), (int, float)):
        return int((sdk_usage.get("summary") or {}).get("runtime_llm_direct_http_hits"))
    fix = sources.get("sdk_tool_calling_fix_decision") or {}
    return int(fix.get("direct_http_hits") or 0)


def _project_metric(baseline: Any, delta: float | None, *, minimum: float) -> float | None:
    value = _number(baseline)
    if value is None:
        return None
    return _round(max(value + (delta or 0.0), minimum))


def _ratio(baseline: Any, variant: Any, *, runtime: bool = False, neutral_if_missing: bool = False) -> float:
    base = _number(baseline)
    value = _number(variant)
    if base is None or value is None:
        return 1.0 if neutral_if_missing else 1.0
    denominator = max(value, EPSILON_RUNTIME if runtime else 1.0)
    return max(0.0, min(EFFICIENCY_CAP, base / denominator))


def _weighted_average(values: list[float], weights: list[float]) -> float:
    total_weight = sum(weights) or 1.0
    return sum(value * weight for value, weight in zip(values, weights)) / total_weight


def _sum_available(values: list[float | None]) -> float | None:
    numbers = [value for value in values if isinstance(value, (int, float))]
    if not numbers:
        return None
    return sum(numbers)


def _avg(values: Any) -> float | None:
    numbers = [float(value) for value in values if isinstance(value, (int, float))]
    return sum(numbers) / len(numbers) if numbers else None


def _number(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def _round(value: Any, digits: int = 4) -> float | None:
    number = _number(value)
    if number is None:
        return None
    return round(number, digits)


def _hidden_label(hidden: dict[str, Any]) -> str | None:
    passed = hidden.get("passed") or hidden.get("passed_cases")
    total = hidden.get("total") or hidden.get("total_cases")
    if isinstance(passed, (int, float)) and isinstance(total, (int, float)):
        return f"{int(passed)}/{int(total)}"
    return None


def _load_json(path: Path) -> Any:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_safe(payload), indent=2, sort_keys=True, default=str), encoding="utf-8")


def _safe(payload: Any) -> Any:
    return redact_secrets(payload)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _render_scorecard(payload: dict[str, Any]) -> str:
    lines = [
        "# Correctness + Efficiency Scorecard",
        "",
        f"- Organizer weights known: `{payload.get('organizer_weights_known')}`",
        f"- Official overall score claim: `{payload.get('official_overall_score_claim')}`",
        f"- Baseline strategy: `{payload.get('baseline_strategy')}`",
        f"- Baseline correctness score: `{payload.get('baseline', {}).get('correctness_score')}`",
        f"- Baseline strict final score: `{payload.get('baseline', {}).get('strict_final_score')}`",
        "",
        "## Formulas",
        "",
        *[f"- {formula}" for formula in payload.get("formulas", [])],
        "",
        "## Variant Sensitivity",
        "",
        "| Variant | Correctness delta | Efficiency | Pareto dominates baseline | Promotion candidate status |",
        "| --- | ---: | ---: | --- | --- |",
    ]
    for row in payload.get("variants", []):
        lines.append(
            f"| `{row.get('variant_id')}` | {row.get('correctness_delta')} | "
            f"{row.get('efficiency_scores', {}).get('efficiency_score_equal_weight')} | "
            f"{row.get('pareto_dominates_baseline')} | `{row.get('promotion_candidate_status')}` |"
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            f"- Decision: `{payload.get('fix_decision', {}).get('decision')}`",
            f"- Best candidate: `{payload.get('fix_decision', {}).get('best_candidate')}`",
            "",
            "Composite scenarios are sensitivity analysis only; no official ranking improvement is claimed.",
        ]
    )
    return "\n".join(lines) + "\n"


def _render_fix_decision(payload: dict[str, Any]) -> str:
    lines = [
        "# Correctness + Efficiency Fix Decision",
        "",
        f"- Decision: `{payload.get('decision')}`",
        f"- Best candidate: `{payload.get('best_candidate')}`",
        f"- Runtime change applied: `{payload.get('runtime_change_applied')}`",
        f"- Official overall score claim: `{payload.get('official_overall_score_claim')}`",
        f"- Organizer weights known: `{payload.get('organizer_weights_known')}`",
        "",
        payload.get("reason", ""),
        "",
        "## Required Before Promotion",
        "",
        *[f"- `{key}`: `{value}`" for key, value in (payload.get("promotion_requirements") or {}).items()],
        "",
        "## Follow-Up Validation",
        "",
        *[f"- {step}" for step in payload.get("follow_up_validation_steps", [])],
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
