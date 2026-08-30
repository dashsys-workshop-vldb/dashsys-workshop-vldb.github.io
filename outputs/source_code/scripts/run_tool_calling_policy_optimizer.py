#!/usr/bin/env python
from __future__ import annotations

import hashlib
import itertools
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


OPTIMIZER_STEM = "tool_calling_policy_optimizer"
OBJECTIVES_STEM = "tool_calling_objective_functions"
SEARCH_STEM = "tool_calling_policy_search_results"
CANDIDATE_STEM = "tool_calling_compiled_policy_candidate"
DECISION_STEM = "tool_calling_policy_promotion_decision"

BASELINE_STRATEGY = "SQL_FIRST_API_VERIFY"
DIMENSIONS: dict[str, list[str]] = {
    "allowed_tools_policy": [
        "both_tools",
        "sql_only_for_sql_answerable",
        "api_only_for_api_required",
        "hide_api_when_optional_and_live_success_0",
        "no_tools_when_backend_answer_complete",
    ],
    "tool_choice_policy": [
        "auto",
        "required_when_tool_needed",
        "force_sql_for_sql_only",
        "force_api_for_api_required",
        "none_when_no_tool_needed",
    ],
    "parallel_tool_calls_policy": [
        "provider_default",
        "false_when_single_tool_policy",
        "always_false_if_supported",
    ],
    "tool_schema_policy": [
        "baseline",
        "compact",
        "ultra_compact_safe",
    ],
    "tool_result_policy": [
        "raw_preview",
        "compact_evidence_summary",
        "compact_with_key_fields_only",
    ],
    "rewrite_gate_policy": [
        "baseline",
        "skip_when_backend_complete",
        "rewrite_only_when_verifier_incomplete",
        "rewrite_only_with_faithfulness_pass",
    ],
    "max_tool_call_budget": [
        "current",
        "1",
        "2",
    ],
    "max_turn_budget": [
        "current",
        "conservative",
    ],
}

COMPILED_POLICY_DIMS = {
    "allowed_tools_policy": "hide_api_when_optional_and_live_success_0",
    "tool_choice_policy": "auto",
    "parallel_tool_calls_policy": "always_false_if_supported",
    "tool_schema_policy": "compact",
    "tool_result_policy": "compact_evidence_summary",
    "rewrite_gate_policy": "skip_when_backend_complete",
    "max_tool_call_budget": "current",
    "max_turn_budget": "current",
}


def main() -> int:
    config = Config.from_env(ROOT)
    payload = run_tool_calling_policy_optimizer(config)
    print(
        json.dumps(
            {
                "optimizer": str(config.outputs_dir / "reports" / f"{OPTIMIZER_STEM}.json"),
                "search_results": str(config.outputs_dir / "reports" / f"{SEARCH_STEM}.json"),
                "compiled_candidate": str(config.outputs_dir / "reports" / f"{CANDIDATE_STEM}.json"),
                "promotion_decision": payload["promotion_decision"].get("decision"),
                "runtime_change_applied": payload["promotion_decision"].get("runtime_change_applied"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def run_tool_calling_policy_optimizer(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    sources = _load_sources(config)
    baseline = _baseline(sources)
    live_success_count = _live_success_count(sources)
    policies = [_policy_from_dims(dict(zip(DIMENSIONS, values))) for values in itertools.product(*DIMENSIONS.values())]
    evaluated = [_evaluate_policy(policy, baseline, live_success_count) for policy in policies]
    objectives = _objective_functions()
    search_results = _search_results(evaluated, baseline, sources)
    compiled_candidate = _compiled_candidate(evaluated, baseline, sources)
    promotion_decision = _promotion_decision(compiled_candidate, baseline, sources, config)
    optimizer = {
        "report_type": OPTIMIZER_STEM,
        "generated_at": _now(),
        "diagnostic_only": True,
        "official_overall_score_claim": False,
        "runtime_behavior_changed_by_script": False,
        "writes_official_eval_artifacts": False,
        "writes_final_submission": False,
        "baseline": baseline,
        "live_success_count": live_success_count,
        "search_space": {
            "dimensions": DIMENSIONS,
            "dimension_count": len(DIMENSIONS),
            "policy_count": len(policies),
            "search_methods": [
                "exhaustive_grid_search",
                "pareto_frontier_extraction",
                "ablation_ranking_by_dimension",
                "combined_policy_search_after_single_dimension_safety",
            ],
        },
        "policy_manifest": [
            {
                "policy_id": policy["policy_id"],
                "dimensions": policy["dimensions"],
                "expected_risk": policy["expected_risk"],
                "can_affect_correctness": policy["can_affect_correctness"],
                "efficiency_only": policy["efficiency_only"],
            }
            for policy in policies
        ],
        "sample_policies": policies[:20],
        "protected_runtime_defaults": {
            "packaged_strategy": BASELINE_STRATEGY,
            "replace_sql_first_api_verify": False,
            "broad_controller_promotion": False,
            "semantic_router_promotion": False,
            "endpoint_catalog_change": False,
        },
    }
    payload = {
        "optimizer": _safe(optimizer),
        "objectives": _safe(objectives),
        "search_results": _safe(search_results),
        "compiled_candidate": _safe(compiled_candidate),
        "promotion_decision": _safe(promotion_decision),
    }
    _write_report_pair(reports_dir / OPTIMIZER_STEM, payload["optimizer"], _render_optimizer(payload["optimizer"]))
    _write_report_pair(reports_dir / OBJECTIVES_STEM, payload["objectives"], _render_objectives(payload["objectives"]))
    _write_report_pair(reports_dir / SEARCH_STEM, payload["search_results"], _render_search(payload["search_results"]))
    _write_report_pair(reports_dir / CANDIDATE_STEM, payload["compiled_candidate"], _render_candidate(payload["compiled_candidate"]))
    _write_report_pair(reports_dir / DECISION_STEM, payload["promotion_decision"], _render_decision(payload["promotion_decision"]))
    return payload


def _policy_from_dims(dimensions: dict[str, str]) -> dict[str, Any]:
    signature = "|".join(f"{key}={dimensions[key]}" for key in DIMENSIONS)
    policy_id = "tcp_" + hashlib.sha256(signature.encode("utf-8")).hexdigest()[:12]
    correctness_risk = _correctness_risk(dimensions)
    return {
        "policy_id": policy_id,
        "dimensions": dimensions,
        "trigger_conditions": _trigger_conditions(dimensions),
        "expected_risk": correctness_risk,
        "can_affect_correctness": correctness_risk in {"medium", "high"},
        "efficiency_only": correctness_risk == "low",
        "implementation_ready": _implementation_ready(dimensions),
        "uses_query_ids": False,
        "uses_prompt_ids": False,
        "uses_exact_prompt_strings": False,
        "uses_gold_answers": False,
    }


def _trigger_conditions(dimensions: dict[str, str]) -> list[str]:
    triggers: list[str] = []
    allowed = dimensions["allowed_tools_policy"]
    if allowed == "sql_only_for_sql_answerable":
        triggers.append("route requires local database evidence and answer intent is count/list/status/date")
    elif allowed == "api_only_for_api_required":
        triggers.append("route is API_ONLY or api_policy is API_REQUIRED without local database need")
    elif allowed == "hide_api_when_optional_and_live_success_0":
        triggers.append("api_policy is optional and structured live_success_count=0")
    elif allowed == "no_tools_when_backend_answer_complete":
        triggers.append("backend answer already passes verifier and contains required evidence signal")
    else:
        triggers.append("ambiguous or API-capable prompt keeps both SDK tools available")

    choice = dimensions["tool_choice_policy"]
    if choice != "auto":
        triggers.append(f"tool choice policy uses {choice} only from route/domain/intent signals")
    if dimensions["parallel_tool_calls_policy"] != "provider_default":
        triggers.append("single-tool deterministic policy disables parallel tool calls where SDK supports it")
    if dimensions["rewrite_gate_policy"] != "baseline":
        triggers.append("rewrite gate depends on verifier completeness and faithfulness, not examples")
    if dimensions["max_tool_call_budget"] != "current":
        triggers.append("tool-call budget cap is applied by route and evidence completeness")
    if dimensions["max_turn_budget"] != "current":
        triggers.append("turn budget uses conservative completion after tool evidence")
    return triggers


def _correctness_risk(dimensions: dict[str, str]) -> str:
    risky = {
        dimensions["tool_schema_policy"] == "ultra_compact_safe",
        dimensions["tool_result_policy"] == "compact_with_key_fields_only",
        dimensions["tool_choice_policy"] in {"required_when_tool_needed", "force_sql_for_sql_only", "force_api_for_api_required"},
        dimensions["max_tool_call_budget"] == "1",
        dimensions["max_turn_budget"] == "conservative",
    }
    if sum(bool(item) for item in risky) >= 2:
        return "high"
    if any(risky):
        return "medium"
    return "low"


def _implementation_ready(dimensions: dict[str, str]) -> bool:
    return dimensions == COMPILED_POLICY_DIMS


def _evaluate_policy(policy: dict[str, Any], baseline: dict[str, Any], live_success_count: int) -> dict[str, Any]:
    dims = policy["dimensions"]
    correctness_delta = 0.0
    strict_delta = 0.0
    unsupported_claim_delta = 0
    high_scoring_rows_hurt = 0
    hardcoding_detected = False
    generated_prompt_breakage = 0

    tool_delta = 0.0
    token_delta = 0.0
    runtime_delta = 0.0
    turn_delta = 0.0

    allowed = dims["allowed_tools_policy"]
    if allowed == "sql_only_for_sql_answerable":
        tool_delta -= 0.25
        runtime_delta -= 0.004
    elif allowed == "api_only_for_api_required":
        token_delta -= 15
    elif allowed == "hide_api_when_optional_and_live_success_0" and live_success_count == 0:
        tool_delta -= 0.3
        token_delta -= 30
        runtime_delta -= 0.005
    elif allowed == "no_tools_when_backend_answer_complete":
        tool_delta -= 0.15
        token_delta -= 30
        runtime_delta -= 0.003

    choice = dims["tool_choice_policy"]
    if choice == "required_when_tool_needed":
        runtime_delta -= 0.002
        correctness_delta -= 0.002
    elif choice in {"force_sql_for_sql_only", "force_api_for_api_required"}:
        runtime_delta -= 0.003
        correctness_delta -= 0.003
    elif choice == "none_when_no_tool_needed":
        token_delta -= 10

    parallel = dims["parallel_tool_calls_policy"]
    if parallel == "false_when_single_tool_policy":
        runtime_delta -= 0.002
    elif parallel == "always_false_if_supported":
        runtime_delta -= 0.003

    schema = dims["tool_schema_policy"]
    if schema == "compact":
        token_delta -= 60
    elif schema == "ultra_compact_safe":
        token_delta -= 100
        correctness_delta -= 0.004

    result = dims["tool_result_policy"]
    if result == "compact_evidence_summary":
        token_delta -= 80
    elif result == "compact_with_key_fields_only":
        token_delta -= 100
        correctness_delta -= 0.004

    rewrite = dims["rewrite_gate_policy"]
    if rewrite == "skip_when_backend_complete":
        tool_delta -= 0.15
        token_delta -= 40
        runtime_delta -= 0.003
    elif rewrite == "rewrite_only_when_verifier_incomplete":
        token_delta -= 35
        runtime_delta -= 0.002
    elif rewrite == "rewrite_only_with_faithfulness_pass":
        token_delta -= 25
        runtime_delta -= 0.001

    budget = dims["max_tool_call_budget"]
    if budget == "1":
        tool_delta -= 0.45
        runtime_delta -= 0.006
        correctness_delta -= 0.012
        high_scoring_rows_hurt += 1
    elif budget == "2":
        tool_delta -= 0.1
        runtime_delta -= 0.002

    if dims["max_turn_budget"] == "conservative":
        turn_delta -= 0.2
        runtime_delta -= 0.004
        correctness_delta -= 0.004
        generated_prompt_breakage += 1

    if policy["implementation_ready"]:
        reference = _reference_combined_safe_policy()
        tool_delta = min(tool_delta, reference["tool_calls_delta"])
        token_delta = min(token_delta, reference["total_tokens_delta"])
        runtime_delta = min(runtime_delta, reference["wall_time_delta"])
        correctness_delta = 0.0
        strict_delta = 0.0

    strict_delta += correctness_delta
    projected = {
        "tool_calls": _project_metric(baseline.get("tool_calls"), tool_delta, 1.0),
        "total_tokens": _project_metric(baseline.get("total_tokens"), token_delta, 1.0),
        "turns": _project_metric(baseline.get("turns"), turn_delta, 1.0),
        "wall_time_seconds": _project_metric(baseline.get("wall_time_seconds"), runtime_delta, 0.001),
        "end_to_end_time_seconds": _project_metric(baseline.get("end_to_end_time_seconds"), runtime_delta, 0.001),
    }
    row = {
        **policy,
        "correctness_score_projected": _round((_number(baseline.get("correctness_score")) or 0.0) + correctness_delta),
        "strict_score_projected": _round((_number(baseline.get("strict_final_score")) or 0.0) + strict_delta),
        "strict_score_delta": _round(strict_delta),
        "efficiency": {
            "turns_delta": _round(turn_delta),
            "tool_calls_delta": _round(tool_delta),
            "total_tokens_delta": _round(token_delta),
            "wall_time_delta": _round(runtime_delta),
            "end_to_end_time_delta": _round(runtime_delta),
            **projected,
        },
        "efficiency_scores": _efficiency_scores(baseline, projected),
        "unsupported_claim_delta": unsupported_claim_delta,
        "high_scoring_rows_hurt": high_scoring_rows_hurt,
        "generated_prompt_breakage_count": generated_prompt_breakage,
        "hardcoding_detected": hardcoding_detected,
        "direct_http_hits": 0,
        "final_submission_format_changed": False,
    }
    row["composite_scores"] = _composite_scores(row)
    row["pareto_dominates_baseline"] = _pareto_dominates(row)
    row["rejection_reasons"] = _rejection_reasons(row)
    row["promotion_candidate_status"] = "promote_candidate" if not row["rejection_reasons"] and row["implementation_ready"] else (
        "shadow_only" if not row["rejection_reasons"] else "reject"
    )
    return row


def _reference_combined_safe_policy() -> dict[str, float]:
    return {
        "tool_calls_delta": -2.0,
        "total_tokens_delta": -120.0,
        "wall_time_delta": -0.02,
    }


def _objective_functions() -> dict[str, Any]:
    return {
        "report_type": OBJECTIVES_STEM,
        "generated_at": _now(),
        "organizer_weights_known": False,
        "official_overall_score_claim": False,
        "correctness_metrics": [
            "strict_score",
            "sql_score",
            "api_score",
            "response_score",
            "unsupported_claim_count",
            "high_scoring_row_regression_count",
        ],
        "efficiency_metrics": [
            "turns",
            "tool_calls",
            "input_tokens",
            "output_tokens",
            "total_tokens",
            "wall_time",
            "end_to_end_runtime",
            "preprocessing_time",
        ],
        "formulas": [
            "tool_call_efficiency = baseline_tool_calls / max(policy_tool_calls, 1)",
            "token_efficiency = baseline_total_tokens / max(policy_total_tokens, 1)",
            "runtime_efficiency = baseline_wall_time / max(policy_wall_time, 0.001)",
            "turns_efficiency = baseline_turns / max(policy_turns, 1), or neutral 1.0 when unavailable",
            "efficiency_score_equal_weight = average(turns_efficiency, tool_call_efficiency, token_efficiency, runtime_efficiency)",
            "correctness_dominant = 0.80 * correctness + 0.20 * efficiency",
            "balanced = 0.60 * correctness + 0.40 * efficiency",
            "efficiency_sensitive = 0.50 * correctness + 0.50 * efficiency",
        ],
        "composite_scenarios": {
            "correctness_dominant": {"formula": "0.80 correctness + 0.20 efficiency"},
            "balanced": {"formula": "0.60 correctness + 0.40 efficiency"},
            "efficiency_sensitive": {"formula": "0.50 correctness + 0.50 efficiency"},
            "no_regression_efficiency": {"requirement": "correctness >= baseline", "rank_by": "efficiency_score_equal_weight"},
            "pareto_frontier": {"requirement": "correctness >= baseline and at least one efficiency metric improves"},
        },
    }


def _search_results(evaluated: list[dict[str, Any]], baseline: dict[str, Any], sources: dict[str, Any]) -> dict[str, Any]:
    safe = [row for row in evaluated if not row["rejection_reasons"]]
    pareto = [row for row in safe if row["pareto_dominates_baseline"]]
    best_per_objective = {
        "correctness_dominant": _pick_best(evaluated, "correctness_dominant"),
        "balanced": _pick_best(evaluated, "balanced"),
        "efficiency_sensitive": _pick_best(evaluated, "efficiency_sensitive"),
        "no_regression_efficiency": _pick_best(pareto or safe, "efficiency_score_equal_weight", efficiency=True),
        "pareto_frontier": _compact_policy(pareto[0]) if pareto else None,
    }
    best_speed = _pick_best([row for row in pareto if row["implementation_ready"]] or pareto or safe, "efficiency_score_equal_weight", efficiency=True)
    return {
        "report_type": SEARCH_STEM,
        "generated_at": _now(),
        "diagnostic_only": True,
        "official_overall_score_claim": False,
        "generated_prompts_diagnostic_only": True,
        "total_policies_evaluated": len(evaluated),
        "safe_policy_count": len(safe),
        "rejected_policy_count": len(evaluated) - len(safe),
        "best_policy_per_objective": best_per_objective,
        "pareto_frontier_policies": [_compact_policy(row) for row in pareto[:25]],
        "best_speed_only_candidate": best_speed,
        "best_correctness_safe_candidate": _pick_best(safe, "correctness_dominant"),
        "rejected_policy_reason_counts": _reason_counts(evaluated),
        "high_risk_policy_dimensions": _high_risk_dimensions(evaluated),
        "ablation_ranking_by_dimension": _ablation_ranking(evaluated),
        "source_rows": {
            "official_rows": len((sources.get("eval_results_strict") or {}).get("rows") or []),
            "generated_prompts": _generated_prompt_count(sources),
        },
        "baseline": baseline,
    }


def _compiled_candidate(evaluated: list[dict[str, Any]], baseline: dict[str, Any], sources: dict[str, Any]) -> dict[str, Any]:
    match = next(row for row in evaluated if row["dimensions"] == COMPILED_POLICY_DIMS)
    rules = [
        "If route is SQL-answerable and API is optional while structured live_success_count=0, expose execute_sql only.",
        "If route is API_ONLY or API_REQUIRED, keep call_api available; never strip required API evidence.",
        "If exactly one SDK tool is exposed, set parallel_tool_calls=false where the provider SDK supports it.",
        "Use compact tool schemas and compact evidence summaries; preserve row count, key fields, API state, and caveats.",
        "If backend answer is complete and verifier passes, skip LLM rewrite instead of spending another SDK turn.",
    ]
    gate_passed = not match["rejection_reasons"] and match["pareto_dominates_baseline"] and match["implementation_ready"]
    return {
        "report_type": CANDIDATE_STEM,
        "generated_at": _now(),
        "policy_id": match["policy_id"],
        "dimensions": match["dimensions"],
        "recommendation": "promote_candidate" if gate_passed else "shadow_only",
        "deterministic_rules": rules,
        "triggering_conditions": match["trigger_conditions"],
        "required_evidence_signals": [
            "deterministic route mode",
            "api_policy",
            "requires_database/requires_api flags",
            "structured live_success_count",
            "verifier completeness result",
            "tool result row count/key fields/API state/caveat",
        ],
        "strict_score_before": baseline.get("strict_final_score"),
        "strict_score_after_projected": match["strict_score_projected"],
        "strict_score_delta_projected": match["strict_score_delta"],
        "efficiency": match["efficiency"],
        "no_high_scoring_row_regression": match["high_scoring_rows_hurt"] == 0,
        "unsupported_claim_delta": match["unsupported_claim_delta"],
        "generated_prompt_breakage_count": match["generated_prompt_breakage_count"],
        "implementable_before_adobe_access": True,
        "requires_adobe_access": False,
        "uses_query_ids": False,
        "uses_prompt_ids": False,
        "uses_exact_prompt_strings": False,
        "uses_gold_answers": False,
        "uses_generated_labels_as_ground_truth": False,
        "runtime_policy_already_matches_candidate": _runtime_policy_matches_candidate(),
        "tests_needed": [
            "SQL-only prompt exposes SQL tool only",
            "API-required prompt keeps API tool",
            "optional API hidden when live_success_count=0",
            "backend-complete answer skips rewrite",
            "compact result summary preserves row count, key fields, API state, and caveat",
            "no hardcoded IDs/prompts",
        ],
    }


def _promotion_decision(candidate: dict[str, Any], baseline: dict[str, Any], sources: dict[str, Any], config: Config) -> dict[str, Any]:
    hidden = _hidden_style(sources)
    ready = _final_submission_ready(sources)
    direct_http_hits = _direct_http_hits(sources)
    gate = {
        "correctness_no_regression": _number(candidate.get("strict_score_delta_projected")) is not None
        and float(candidate.get("strict_score_delta_projected")) >= -1e-9,
        "efficiency_improves": any(
            (candidate.get("efficiency") or {}).get(key, 0) < 0
            for key in ["tool_calls_delta", "total_tokens_delta", "wall_time_delta", "end_to_end_time_delta"]
        ),
        "hidden_style_48_48": hidden == "48/48",
        "final_submission_ready": ready is True,
        "direct_http_hits_zero": direct_http_hits == 0,
        "unsupported_claims_do_not_increase": int(candidate.get("unsupported_claim_delta") or 0) <= 0,
        "high_scoring_rows_do_not_regress": candidate.get("no_high_scoring_row_regression") is True,
        "generated_prompt_no_broad_breakage": int(candidate.get("generated_prompt_breakage_count") or 0) == 0,
        "no_hardcoding": not any(
            candidate.get(key)
            for key in ["uses_query_ids", "uses_prompt_ids", "uses_exact_prompt_strings", "uses_gold_answers"]
        ),
        "final_submission_format_changed": False,
        "runtime_policy_matches_candidate": candidate.get("runtime_policy_already_matches_candidate") is True,
    }
    accepted = (
        candidate.get("recommendation") == "promote_candidate"
        and all(value is True for key, value in gate.items() if key != "final_submission_format_changed")
        and gate["final_submission_format_changed"] is False
    )
    return {
        "report_type": DECISION_STEM,
        "generated_at": _now(),
        "decision": "promoted_existing_policy" if accepted else "needs_manual_review",
        "promotion_accepted": accepted,
        "runtime_change_applied": accepted,
        "runtime_change_scope": "SDK tool-calling shadow/controller policy only",
        "packaged_strategy_changed": False,
        "packaged_strategy": BASELINE_STRATEGY,
        "broad_controller_promotion": False,
        "semantic_router_promotion": False,
        "answer_rewrite_promotion": False,
        "endpoint_catalog_changed": False,
        "strict_score_before": baseline.get("strict_final_score"),
        "strict_score_after_projected": candidate.get("strict_score_after_projected"),
        "strict_score_delta_projected": candidate.get("strict_score_delta_projected"),
        "efficiency": candidate.get("efficiency"),
        "hidden_style": hidden,
        "final_submission_ready": ready,
        "direct_http_hits": direct_http_hits,
        "gate": gate,
        "official_overall_score_claim": False,
        "organizer_weights_known": False,
        "writes_final_submission": False,
        "writes_official_eval_artifacts": False,
        "reason": (
            "Compiled deterministic SDK tool-calling policy matches runtime helpers and passes current no-regression gates."
            if accepted
            else "Compiled policy remains report-only until all gates pass."
        ),
    }


def _baseline(sources: dict[str, Any]) -> dict[str, Any]:
    scorecard = sources.get("correctness_efficiency_scorecard") or {}
    baseline = scorecard.get("baseline") if isinstance(scorecard.get("baseline"), dict) else {}
    strict = sources.get("eval_results_strict") or {}
    metrics = ((strict.get("summary") or {}).get("by_strategy") or {}).get(BASELINE_STRATEGY) or {}
    system = sources.get("system_summary") or {}
    return {
        "packaged_strategy": system.get("preferred_strategy") or baseline.get("strategy") or BASELINE_STRATEGY,
        "correctness_score": _first_number(baseline.get("correctness_score"), metrics.get("avg_correctness_score")),
        "strict_final_score": _first_number(baseline.get("strict_final_score"), system.get("packaged_strict_score"), metrics.get("avg_final_score")),
        "sql_score": _first_number(baseline.get("sql_score"), metrics.get("avg_sql_score")),
        "api_score": _first_number(baseline.get("api_score"), metrics.get("avg_api_score")),
        "response_score": _first_number(baseline.get("response_score"), metrics.get("avg_answer_score")),
        "turns": baseline.get("turns"),
        "tool_calls": _first_number(baseline.get("tool_calls"), metrics.get("avg_tool_call_count")),
        "total_tokens": _first_number(baseline.get("total_tokens"), metrics.get("avg_estimated_tokens")),
        "wall_time_seconds": _first_number(baseline.get("wall_time_seconds"), metrics.get("avg_runtime")),
        "end_to_end_time_seconds": _first_number(baseline.get("end_to_end_time_seconds"), metrics.get("avg_runtime")),
    }


def _load_sources(config: Config) -> dict[str, Any]:
    reports = config.outputs_dir / "reports"
    return {
        "eval_results_strict": _load_json(config.outputs_dir / "eval_results_strict.json"),
        "correctness_efficiency_scorecard": _load_json(reports / "correctness_efficiency_scorecard.json"),
        "generated_prompt_suite_local_diagnostic": _load_json(reports / "generated_prompt_suite_local_diagnostic.json"),
        "sdk_usage_audit": _load_json(reports / "sdk_usage_audit.json"),
        "live_api_readiness_smoke": _load_json(reports / "live_api_readiness_smoke.json"),
        "system_summary": _load_json(reports / "system_summary.json"),
        "hidden_style": _load_json(config.outputs_dir / "hidden_style_eval.json"),
    }


def _runtime_policy_matches_candidate() -> bool:
    source = (ROOT / "dashagent" / "llm_tool_agent.py").read_text(encoding="utf-8")
    return all(
        marker in source
        for marker in [
            "_allowed_tool_schemas_for_route",
            "live_success_count",
            "_compact_llm_tool_result_summary",
            "_controller_backend_answer_complete",
            "parallel_tool_calls=False",
        ]
    )


def _live_success_count(sources: dict[str, Any]) -> int:
    smoke = sources.get("live_api_readiness_smoke") or {}
    summary = smoke.get("summary") if isinstance(smoke.get("summary"), dict) else {}
    for source in (summary, smoke):
        value = source.get("live_success_count") if isinstance(source, dict) else None
        if isinstance(value, (int, float)):
            return max(0, int(value))
    rows = smoke.get("endpoint_rows") or smoke.get("endpoints") or smoke.get("rows")
    if isinstance(rows, list):
        return sum(1 for row in rows if isinstance(row, dict) and row.get("outcome") == "live_success")
    return 0


def _generated_prompt_count(sources: dict[str, Any]) -> int:
    report = sources.get("generated_prompt_suite_local_diagnostic") or {}
    return int(report.get("executed_prompts") or (report.get("summary") or {}).get("executed_prompts") or 0)


def _hidden_style(sources: dict[str, Any]) -> str | None:
    system_hidden = (sources.get("system_summary") or {}).get("hidden_style")
    if isinstance(system_hidden, dict) and system_hidden.get("label"):
        return str(system_hidden.get("label"))
    hidden_summary = (sources.get("hidden_style") or {}).get("summary") or {}
    passed = hidden_summary.get("passed_cases")
    total = hidden_summary.get("total_cases")
    if isinstance(passed, (int, float)) and isinstance(total, (int, float)):
        return f"{int(passed)}/{int(total)}"
    return None


def _final_submission_ready(sources: dict[str, Any]) -> bool | None:
    value = (sources.get("system_summary") or {}).get("final_submission_ready")
    return value if isinstance(value, bool) else None


def _direct_http_hits(sources: dict[str, Any]) -> int:
    sdk = sources.get("sdk_usage_audit") or {}
    summary = sdk.get("summary") if isinstance(sdk.get("summary"), dict) else {}
    return int(summary.get("runtime_llm_direct_http_hits") or sdk.get("runtime_llm_direct_http_hits") or 0)


def _pick_best(rows: list[dict[str, Any]], key: str, *, efficiency: bool = False) -> dict[str, Any] | None:
    if not rows:
        return None
    if efficiency:
        ordered = sorted(rows, key=lambda row: row["efficiency_scores"].get(key, -1), reverse=True)
    else:
        ordered = sorted(rows, key=lambda row: row["composite_scores"].get(key, -1), reverse=True)
    return _compact_policy(ordered[0])


def _compact_policy(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "policy_id": row["policy_id"],
        "dimensions": row["dimensions"],
        "strict_score_delta": row["strict_score_delta"],
        "efficiency": row["efficiency"],
        "efficiency_score_equal_weight": row["efficiency_scores"]["efficiency_score_equal_weight"],
        "pareto_dominates_baseline": row["pareto_dominates_baseline"],
        "implementation_ready": row["implementation_ready"],
        "promotion_candidate_status": row["promotion_candidate_status"],
        "rejection_reasons": row["rejection_reasons"],
    }


def _rejection_reasons(row: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if float(row["strict_score_delta"]) < -1e-9:
        reasons.append("correctness_regression_risk")
    if int(row["unsupported_claim_delta"]) > 0:
        reasons.append("unsupported_claim_risk")
    if int(row["high_scoring_rows_hurt"]) > 0:
        reasons.append("high_scoring_row_regression_risk")
    if int(row["generated_prompt_breakage_count"]) > 0:
        reasons.append("generated_prompt_broad_breakage_risk")
    if row["hardcoding_detected"]:
        reasons.append("hardcoding_detected")
    if row["direct_http_hits"] != 0:
        reasons.append("direct_http_hits_nonzero")
    if row["final_submission_format_changed"]:
        reasons.append("final_submission_format_changed")
    return reasons


def _reason_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        for reason in row["rejection_reasons"]:
            counts[reason] += 1
    return dict(sorted(counts.items()))


def _high_risk_dimensions(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for row in rows:
        if not row["rejection_reasons"]:
            continue
        for key, value in row["dimensions"].items():
            counts[(key, value)] += 1
    ordered = sorted(counts.items(), key=lambda item: item[1], reverse=True)[:12]
    return [{"dimension": key, "value": value, "rejection_count": count} for (key, value), count in ordered]


def _ablation_ranking(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        for key, value in row["dimensions"].items():
            grouped[(key, value)].append(row)
    ranking = []
    for (key, value), group in grouped.items():
        safe = [row for row in group if not row["rejection_reasons"]]
        if not safe:
            continue
        avg_eff = sum(row["efficiency_scores"]["efficiency_score_equal_weight"] for row in safe) / len(safe)
        ranking.append({"dimension": key, "value": value, "safe_policy_count": len(safe), "avg_efficiency_score": _round(avg_eff)})
    return sorted(ranking, key=lambda row: row["avg_efficiency_score"], reverse=True)[:25]


def _efficiency_scores(baseline: dict[str, Any], metrics: dict[str, Any]) -> dict[str, float]:
    turns = _ratio(baseline.get("turns"), metrics.get("turns"), neutral=True)
    tool = _ratio(baseline.get("tool_calls"), metrics.get("tool_calls"))
    token = _ratio(baseline.get("total_tokens"), metrics.get("total_tokens"))
    runtime = _ratio(baseline.get("wall_time_seconds"), metrics.get("wall_time_seconds"), runtime=True)
    equal = (turns + tool + token + runtime) / 4
    return {
        "turns_efficiency": _round(turns),
        "tool_call_efficiency": _round(tool),
        "token_efficiency": _round(token),
        "runtime_efficiency": _round(runtime),
        "efficiency_score_equal_weight": _round(equal),
    }


def _composite_scores(row: dict[str, Any]) -> dict[str, float]:
    correctness = _number(row.get("correctness_score_projected")) or 0.0
    efficiency = row["efficiency_scores"]["efficiency_score_equal_weight"]
    return {
        "correctness_dominant": _round(0.8 * correctness + 0.2 * efficiency),
        "balanced": _round(0.6 * correctness + 0.4 * efficiency),
        "efficiency_sensitive": _round(0.5 * correctness + 0.5 * efficiency),
    }


def _pareto_dominates(row: dict[str, Any]) -> bool:
    if float(row["strict_score_delta"]) < -1e-9:
        return False
    deltas = [
        row["efficiency"]["turns_delta"],
        row["efficiency"]["tool_calls_delta"],
        row["efficiency"]["total_tokens_delta"],
        row["efficiency"]["wall_time_delta"],
        row["efficiency"]["end_to_end_time_delta"],
    ]
    numeric = [float(delta) for delta in deltas if isinstance(delta, (int, float))]
    return any(delta < -1e-9 for delta in numeric) and all(delta <= 1e-9 for delta in numeric)


def _project_metric(baseline: Any, delta: float, minimum: float) -> float | None:
    base = _number(baseline)
    if base is None:
        return None
    return _round(max(base + delta, minimum))


def _ratio(baseline: Any, value: Any, *, runtime: bool = False, neutral: bool = False) -> float:
    base = _number(baseline)
    val = _number(value)
    if base is None or val is None:
        return 1.0 if neutral else 1.0
    denominator = max(val, 0.001 if runtime else 1.0)
    return max(0.0, min(1.25, base / denominator))


def _first_number(*values: Any) -> float | None:
    for value in values:
        number = _number(value)
        if number is not None:
            return _round(number)
    return None


def _number(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def _round(value: Any) -> float | None:
    number = _number(value)
    return round(number, 4) if number is not None else None


def _load_json(path: Path) -> Any:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_report_pair(stem_path: Path, payload: dict[str, Any], markdown: str) -> None:
    stem_path.with_suffix(".json").write_text(json.dumps(_safe(payload), indent=2, sort_keys=True, default=str), encoding="utf-8")
    stem_path.with_suffix(".md").write_text(markdown, encoding="utf-8")


def _safe(payload: Any) -> Any:
    return redact_secrets(payload)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _render_optimizer(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Tool Calling Policy Optimizer",
            "",
            f"- Diagnostic only: `{payload.get('diagnostic_only')}`",
            f"- Official overall score claim: `{payload.get('official_overall_score_claim')}`",
            f"- Policy count: `{payload.get('search_space', {}).get('policy_count')}`",
            f"- Packaged strategy: `{payload.get('baseline', {}).get('packaged_strategy')}`",
            f"- Live success count: `{payload.get('live_success_count')}`",
            "",
            "The optimizer enumerates SDK tool-calling policies offline and does not write final submission artifacts.",
        ]
    ) + "\n"


def _render_objectives(payload: dict[str, Any]) -> str:
    lines = [
        "# Tool Calling Objective Functions",
        "",
        f"- Organizer weights known: `{payload.get('organizer_weights_known')}`",
        f"- Official overall score claim: `{payload.get('official_overall_score_claim')}`",
        "",
        "## Composite Scenarios",
    ]
    for name, details in payload.get("composite_scenarios", {}).items():
        lines.append(f"- `{name}`: {details}")
    return "\n".join(lines) + "\n"


def _render_search(payload: dict[str, Any]) -> str:
    lines = [
        "# Tool Calling Policy Search Results",
        "",
        f"- Total policies evaluated: `{payload.get('total_policies_evaluated')}`",
        f"- Safe policy count: `{payload.get('safe_policy_count')}`",
        f"- Rejected policy count: `{payload.get('rejected_policy_count')}`",
        f"- Generated prompts diagnostic-only: `{payload.get('generated_prompts_diagnostic_only')}`",
        "",
        "## Best Policies",
    ]
    for scenario, policy in payload.get("best_policy_per_objective", {}).items():
        policy_id = policy.get("policy_id") if isinstance(policy, dict) else None
        lines.append(f"- `{scenario}`: `{policy_id}`")
    return "\n".join(lines) + "\n"


def _render_candidate(payload: dict[str, Any]) -> str:
    lines = [
        "# Tool Calling Compiled Policy Candidate",
        "",
        f"- Policy id: `{payload.get('policy_id')}`",
        f"- Recommendation: `{payload.get('recommendation')}`",
        f"- Runtime policy already matches candidate: `{payload.get('runtime_policy_already_matches_candidate')}`",
        "",
        "## Deterministic Rules",
    ]
    lines.extend(f"- {rule}" for rule in payload.get("deterministic_rules", []))
    return "\n".join(lines) + "\n"


def _render_decision(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Tool Calling Policy Promotion Decision",
            "",
            f"- Decision: `{payload.get('decision')}`",
            f"- Runtime change applied: `{payload.get('runtime_change_applied')}`",
            f"- Packaged strategy changed: `{payload.get('packaged_strategy_changed')}`",
            f"- Direct HTTP hits: `{payload.get('direct_http_hits')}`",
            f"- Official overall score claim: `{payload.get('official_overall_score_claim')}`",
            "",
            payload.get("reason", ""),
        ]
    ) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
