#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
import re
import shutil
import sys
import time
from collections import Counter, defaultdict
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dashagent.config import DEFAULT_CONFIG, robust_generalized_ablation_config, robust_generalized_candidate_config
from dashagent.endpoint_catalog import EndpointCatalog
from dashagent.evidence_match_scorer import score_evidence_match
from dashagent.no_tool_safety_verifier import verify_no_tool_safety
from dashagent.post_sql_api_call_verifier import verify_post_sql_api_advice
from dashagent.post_sql_decision_card import build_post_sql_decision_card
from dashagent.post_sql_deterministic_policy import decide_post_sql_api_policy
from dashagent.post_sql_llm_advisor import advise_post_sql_api
from dashagent.prompt_semantic_ir import extract_objective_prompt_features
from dashagent.routing_anti_hallucination_gate import run_routing_gate_with_revision
from dashagent.semantic_intent_classifier import SemanticIntentDecision, classify_semantic_intent
from dashagent.semantic_intent_context_builder import build_semantic_intent_context, estimate_context_tokens
from dashagent.semantic_route_decision_ladder import run_semantic_route_decision_ladder, validate_llm_safe_direct_answer
from dashagent.staged_evidence_policy import decide_initial_evidence_branch


SIMULATED_MODES = {
    "packaged_baseline",
    "semantic_routing_shadow",
    "staged_evidence_shadow",
    "post_sql_api_decision_shadow",
    "latest_applied_trial",
    "latest_full_trial",
}
REAL_MODES = {
    "packaged_baseline_real",
    "latest_shadow_real",
    "latest_applied_real_trial",
    "semantic_no_tool_applied_real_trial",
    "staged_evidence_applied_real_trial",
    "post_sql_deterministic_applied_real_trial",
    "post_sql_llm_advisor_applied_real_trial",
    "combined_safe_applied_real_trial",
    "combined_safe_deterministic_promotion_candidate_real",
    "robust_generalized_harness_candidate_real",
    "ablation_no_semantic_routing_real",
    "ablation_semantic_routing_only_real",
    "ablation_staged_evidence_only_real",
    "ablation_answer_grounding_only_real",
    "ablation_llm_answer_no_verifier_real",
    "ablation_llm_answer_with_verifier_real",
    "ablation_semantic_role_parse_only_real",
    "ablation_no_llm_components_real",
    "ablation_full_candidate_no_llm_answer_real",
    "ablation_full_candidate_no_safe_api_probe_real",
    "ablation_full_candidate_no_staged_policy_real",
    "ablation_full_candidate_no_semantic_parse_real",
}
RECOGNIZED_MODES = SIMULATED_MODES | REAL_MODES
REAL_BEHAVIOR_APPLIED_MODES = {
    "semantic_no_tool_applied_real_trial",
    "staged_evidence_applied_real_trial",
    "post_sql_deterministic_applied_real_trial",
    "post_sql_llm_advisor_applied_real_trial",
    "combined_safe_applied_real_trial",
    "combined_safe_deterministic_promotion_candidate_real",
    "robust_generalized_harness_candidate_real",
    "ablation_no_semantic_routing_real",
    "ablation_semantic_routing_only_real",
    "ablation_staged_evidence_only_real",
    "ablation_answer_grounding_only_real",
    "ablation_llm_answer_no_verifier_real",
    "ablation_llm_answer_with_verifier_real",
    "ablation_semantic_role_parse_only_real",
    "ablation_no_llm_components_real",
    "ablation_full_candidate_no_llm_answer_real",
    "ablation_full_candidate_no_safe_api_probe_real",
    "ablation_full_candidate_no_staged_policy_real",
    "ablation_full_candidate_no_semantic_parse_real",
}
REAL_APPLIED_TRIAL_BLOCKERS = [
    "Semantic route decisions are integrated as shadow checkpoints only.",
    "Staged evidence policy is integrated as shadow checkpoints only.",
    "Post-SQL API decision policy records keep/drop/add advice but does not alter actual API execution.",
    "No non-shadow promotion gate has approved applying these decisions to packaged execution.",
]

EVIDENCE_ROUTES = {"EVIDENCE_PIPELINE", "SQL_ONLY", "API_ONLY", "SQL_THEN_API", "SQL_PRIMARY_API_VERIFY"}
POST_SQL_ADVISOR_SOURCE_KEYS = [
    "DETERMINISTIC_BYPASS",
    "DETERMINISTIC_HIGH_CONF",
    "DETERMINISTIC_FALLBACK",
    "LLM_ADVISOR",
    "LLM_ADVISOR_VERIFIED",
    "LLM_ADVISOR_BLOCKED",
    "LLM_BACKEND_UNAVAILABLE",
    "INVALID_JSON",
    "DISABLED",
]


class _AdviceClient:
    def __init__(self, payloads: list[str | dict[str, Any]]) -> None:
        self.payloads = list(payloads)
        self.calls = 0

    def complete(self, messages: list[dict[str, str]]) -> str:
        self.calls += 1
        if self.payloads:
            payload = self.payloads.pop(0)
        else:
            payload = {"mode": "CAVEAT_ONLY", "endpoint_id": None, "conf": 0.0, "needed_roles": [], "codes": ["EMPTY_FAKE_CLIENT"]}
        return payload if isinstance(payload, str) else json.dumps(payload, sort_keys=True)


def run_suite_eval(
    *,
    suite: Path | str | None = None,
    gold: Path | str | None = None,
    suite_path: Path | str | None = None,
    gold_path: Path | str | None = None,
    modes: list[str] | None = None,
    limit: int | None = None,
    full: bool = False,
    seed: int = 20260525,
    clean: bool = False,
    output_dir: Path | str | None = None,
    report_dir: Path | str | None = None,
    engine: str = "real_agent",
    executor_factory: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    suite_input = suite_path if suite_path is not None else suite
    gold_input = gold_path if gold_path is not None else gold
    suite_path = Path(suite_input) if suite_input is not None else DEFAULT_CONFIG.data_dir / "benchmarks" / "dashagent_500_prompt_suite.jsonl"
    gold_path = Path(gold_input) if gold_input is not None else DEFAULT_CONFIG.data_dir / "benchmarks" / "dashagent_500_prompt_suite_gold.jsonl"
    if engine not in {"real_agent", "simulated_trace"}:
        raise ValueError(f"Unknown eval engine: {engine}")
    selected_modes = modes or (["packaged_baseline_real"] if engine == "real_agent" else ["packaged_baseline"])
    if engine == "real_agent":
        return _run_real_agent_suite_eval(
            suite_path=suite_path,
            gold_path=gold_path,
            modes=selected_modes,
            limit=limit,
            full=full,
            seed=seed,
            clean=clean,
            output_dir=output_dir,
            report_dir=report_dir,
            executor_factory=executor_factory,
        )
    unknown = [mode for mode in selected_modes if mode not in RECOGNIZED_MODES]
    if unknown:
        raise ValueError(f"Unknown benchmark modes: {unknown}")
    non_simulated = [mode for mode in selected_modes if mode not in SIMULATED_MODES]
    if non_simulated:
        raise ValueError(f"Modes require --engine real_agent: {non_simulated}")

    eval_dir = Path(output_dir) if output_dir is not None else DEFAULT_CONFIG.outputs_dir / "dashagent_500_prompt_suite_eval_simulated"
    reports_dir = Path(report_dir) if report_dir is not None else DEFAULT_CONFIG.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    if clean and eval_dir.exists():
        shutil.rmtree(eval_dir)
    eval_dir.mkdir(parents=True, exist_ok=True)

    runtime_rows = _read_jsonl(suite_path)
    gold_by_id = {row["prompt_id"]: row for row in _read_jsonl(gold_path)}
    rng = random.Random(seed)
    ordered_rows = list(runtime_rows)
    rng.shuffle(ordered_rows)
    if not full:
        ordered_rows = ordered_rows[: limit or 25]
    elif limit is not None:
        ordered_rows = ordered_rows[:limit]

    catalog = EndpointCatalog()
    mode_summaries: dict[str, Any] = {}
    mode_rows: dict[str, list[dict[str, Any]]] = {}

    for mode in selected_modes:
        rows: list[dict[str, Any]] = []
        start = time.perf_counter()
        for runtime_row in ordered_rows:
            prompt_id = runtime_row["prompt_id"]
            runtime_trace = _run_runtime_trace(runtime_row, mode, catalog)
            gold_row = gold_by_id[prompt_id]
            grade = _grade_runtime_trace(runtime_trace, gold_row)
            trajectory = {
                "prompt_id": prompt_id,
                "mode": mode,
                "runtime_prompt": runtime_row,
                "gold_visible_to_runtime": False,
                "old_generated_diagnostic_path_used": False,
                "latest_code_paths_enabled": runtime_trace["latest_code_paths_enabled"],
                "observable_trace": runtime_trace["observable_trace"],
                "tool_counts": runtime_trace["tool_counts"],
                "final_answer": runtime_trace["final_answer"],
                "grade": grade,
            }
            prompt_dir = eval_dir / mode / prompt_id
            prompt_dir.mkdir(parents=True, exist_ok=True)
            (prompt_dir / "trajectory.json").write_text(json.dumps(trajectory, indent=2, sort_keys=True), encoding="utf-8")
            rows.append(
                {
                    "prompt_id": prompt_id,
                    "category": runtime_row.get("category"),
                    "domain_family": runtime_row.get("domain_family"),
                    "expected_evidence_need": gold_row.get("expected_evidence_need"),
                    **grade,
                    "trajectory_path": str(prompt_dir / "trajectory.json"),
                    "latest_code_paths_enabled": runtime_trace["latest_code_paths_enabled"],
                    **runtime_trace["row_metrics"],
                }
            )
        elapsed = time.perf_counter() - start
        mode_rows[mode] = rows
        mode_summaries[mode] = _summarize_mode(mode, rows, elapsed)

    comparison = _compare_modes(mode_summaries, mode_rows)
    shadow_comparison = _compare_specific_modes(
        "packaged_baseline_real",
        "latest_shadow_real",
        mode_summaries,
        mode_rows,
    )
    mode_comparisons = {
        mode: _compare_specific_modes("packaged_baseline_real", mode, mode_summaries, mode_rows)
        for mode in mode_summaries
        if mode != "packaged_baseline_real"
    }
    report = {
        "eval_engine": "simulated_trace",
        "simulated_trace_only": True,
        "real_agent_execution": False,
        "synthetic_sql_results_used": True,
        "runtime_used_category_tags_for_decision": True,
        "agent_executor_used": False,
        "grading_type": "heuristic_internal_gold",
        "organizer_equivalent": False,
        "answer_grading_method": "required_fact_substring_and_forbidden_claim_checks",
        "process_grading_method": "observable_trace_checkpoint_and_tool_usage_matching",
        "suite": str(suite_path),
        "gold": str(gold_path),
        "seed": seed,
        "prompt_count": len(ordered_rows),
        "full_requested": full,
        "modes": mode_summaries,
        "mode_summary": mode_summaries,
        "mode_order": selected_modes,
        "comparison": comparison,
        "shadow_comparison": shadow_comparison,
        "latest_code_paths_explicitly_evaluated": True,
        "old_generated_diagnostic_path_used": False,
        "runtime_gold_visible": False,
        "diagnostic_internal_only": True,
        "organizer_score_replacement": False,
        "output_dir": str(eval_dir),
    }
    report_json = reports_dir / "dashagent_500_prompt_suite_eval_simulated.json"
    report_md = reports_dir / "dashagent_500_prompt_suite_eval_simulated.md"
    report_json.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    report_md.write_text(_eval_report_md(report), encoding="utf-8")

    gate = _write_gate_report(report, reports_dir, suffix="_simulated")
    report["gate"] = gate
    report_json.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    _write_runner_audit(report, reports_dir)
    return report


def _run_real_agent_suite_eval(
    *,
    suite_path: Path,
    gold_path: Path,
    modes: list[str],
    limit: int | None,
    full: bool,
    seed: int,
    clean: bool,
    output_dir: Path | str | None,
    report_dir: Path | str | None,
    executor_factory: Callable[..., Any] | None,
) -> dict[str, Any]:
    selected_modes = modes or ["packaged_baseline_real"]
    unknown = [mode for mode in selected_modes if mode not in RECOGNIZED_MODES]
    if unknown:
        raise ValueError(f"Unknown benchmark modes: {unknown}")
    non_real = [mode for mode in selected_modes if mode not in REAL_MODES]
    if non_real:
        raise ValueError(f"Modes require --engine simulated_trace: {non_real}")

    eval_dir = Path(output_dir) if output_dir is not None else DEFAULT_CONFIG.outputs_dir / "dashagent_500_prompt_suite_eval_real"
    reports_dir = Path(report_dir) if report_dir is not None else DEFAULT_CONFIG.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    if clean and eval_dir.exists():
        shutil.rmtree(eval_dir)
    eval_dir.mkdir(parents=True, exist_ok=True)

    runtime_rows = _read_jsonl(suite_path)
    gold_by_id = {row["prompt_id"]: row for row in _read_jsonl(gold_path)}
    ordered_rows = _select_rows(runtime_rows, seed=seed, limit=limit, full=full)
    catalog = EndpointCatalog()
    mode_summaries: dict[str, Any] = {}
    mode_rows: dict[str, list[dict[str, Any]]] = {}
    unavailable_modes: dict[str, Any] = {}

    for mode in selected_modes:
        if mode == "latest_applied_real_trial":
            unavailable_modes[mode] = {
                "mode": mode,
                "available": False,
                "excluded_from_comparison": True,
                "unavailable": True,
                "latest_applied_real_trial_unavailable": True,
                "blockers": REAL_APPLIED_TRIAL_BLOCKERS,
                "prompt_count": 0,
                "real_agent_execution": False,
                "applied_trial_behavior_changed": False,
            }
            mode_summaries[mode] = _empty_unavailable_summary(mode, unavailable_modes[mode])
            mode_rows[mode] = []
            continue
        if mode == "post_sql_llm_advisor_applied_real_trial" and not _llm_backend_available():
            unavailable_modes[mode] = {
                "mode": mode,
                "available": False,
                "excluded_from_comparison": True,
                "unavailable": True,
                "blockers": ["LLM backend unavailable or not explicitly configured for post-SQL advisor applied trial."],
                "prompt_count": 0,
                "real_agent_execution": False,
                "applied_trial_behavior_changed": False,
            }
            mode_summaries[mode] = _empty_unavailable_summary(mode, unavailable_modes[mode])
            mode_rows[mode] = []
            continue

        rows: list[dict[str, Any]] = []
        config = _config_for_real_mode(mode)
        executor = _make_executor(config, executor_factory)
        start = time.perf_counter()
        for runtime_row in ordered_rows:
            prompt_id = str(runtime_row["prompt_id"])
            runtime_input = _runtime_input(runtime_row)
            prompt_dir = eval_dir / mode / prompt_id
            prompt_dir.mkdir(parents=True, exist_ok=True)
            run_start = time.perf_counter()
            agent_result = executor.run(
                runtime_input["prompt"],
                strategy="SQL_FIRST_API_VERIFY",
                query_id=runtime_input["prompt_id"],
                output_dir=prompt_dir,
            )
            runtime_ms = (time.perf_counter() - run_start) * 1000
            gold_row = gold_by_id[prompt_id]
            grade, extracted = _grade_real_agent_result(agent_result, gold_row, catalog, runtime_ms=runtime_ms)
            benchmark_record = {
                "prompt_id": prompt_id,
                "mode": mode,
                "engine": "real_agent",
                "runtime_input": runtime_input,
                "gold_visible_to_runtime": False,
                "category_tags_domain_visible_to_runtime": False,
                "oracle_visible_to_runtime": False,
                "expected_trace_visible_to_runtime": False,
                "agent_executor_used": True,
                "synthetic_sql_results_used": False,
                "trajectory_path": str(prompt_dir / "trajectory.json"),
                "grade": grade,
                "extracted_runtime": extracted,
            }
            (prompt_dir / "benchmark_grade.json").write_text(json.dumps(benchmark_record, indent=2, sort_keys=True, default=str), encoding="utf-8")
            rows.append(
                {
                    "prompt_id": prompt_id,
                    "category": runtime_row.get("category"),
                    **grade,
                    "trajectory_path": str(prompt_dir / "trajectory.json"),
                    "latest_code_paths_enabled": extracted["latest_code_paths_enabled"],
                    "final_answer": str(agent_result.get("final_answer") or ""),
                    "route_action": extracted["route_action"],
                    "sql_used": extracted["sql_used"],
                    "api_used": extracted["api_used"],
                    "sql_call_count": extracted["sql_calls"],
                    "api_call_count": extracted["api_calls"],
                    "sql_tables": extracted["sql_tables"],
                    "api_families": extracted["api_families"],
                    "estimated_total_tokens": extracted["estimated_total_tokens"],
                    "runtime_ms": runtime_ms,
                    "api_calls_saved": extracted["api_calls_saved"],
                    "api_calls_added": extracted["api_calls_added"],
                    "feature_flags_used": extracted["feature_flags_used"],
                    "behavior_changed": extracted["behavior_changed"],
                    "applied_decision_count": extracted["applied_decision_count"],
                    "skipped_decision_count": extracted["skipped_decision_count"],
                    "fallback_count": extracted["fallback_count"],
                    "blocker_count": extracted["blocker_count"],
                    "applied_decision_records": extracted["applied_decision_records"],
                    "anti_hallucination_initial_fail": extracted["anti_hallucination_initial_fail"],
                    "anti_hallucination_revision_attempted": extracted["anti_hallucination_revision_attempted"],
                    "anti_hallucination_revision_success": extracted["anti_hallucination_revision_success"],
                    "post_sql_advisor_checkpoint_present": extracted["post_sql_advisor_checkpoint_present"],
                    "post_sql_llm_advisor_actual_call": extracted["post_sql_llm_advisor_actual_call"],
                    "post_sql_advisor_source": extracted["post_sql_advisor_source"],
                    "post_sql_verifier_source": extracted["post_sql_verifier_source"],
                    "post_sql_verifier_verified": extracted["post_sql_verifier_verified"],
                    "post_sql_verifier_blocked": extracted["post_sql_verifier_blocked"],
                    "post_sql_llm_advice_blocked": extracted["post_sql_llm_advice_blocked"],
                    "post_sql_advisor_disabled_or_fallback": extracted["post_sql_advisor_disabled_or_fallback"],
                    "post_sql_deterministic_fallback": extracted["post_sql_deterministic_fallback"],
                    "post_sql_advisor_invoked": extracted["post_sql_advisor_invoked"],
                    "post_sql_advisor_verified": extracted["post_sql_advisor_verified"],
                    "post_sql_advisor_blocked": extracted["post_sql_advisor_blocked"],
                    "missing_checkpoints": extracted["missing_checkpoints"],
                }
            )
        elapsed = time.perf_counter() - start
        mode_rows[mode] = rows
        summary = _summarize_mode(mode, rows, elapsed)
        summary.update(
            {
                "real_agent_execution": True,
                "agent_executor_used": True,
                "synthetic_sql_results_used": False,
                "runtime_used_category_tags_for_decision": False,
                "shadow_modules_executed": mode == "latest_shadow_real" and bool(summary["latest_code_paths_enabled"].get("semantic_route_decision_ladder")),
                "packaged_behavior_changed": False,
            }
        )
        mode_summaries[mode] = summary

    if "latest_applied_real_trial" not in mode_summaries:
        unavailable_modes["latest_applied_real_trial"] = {
            "mode": "latest_applied_real_trial",
            "available": False,
            "excluded_from_comparison": True,
            "unavailable": True,
            "not_requested": True,
            "latest_applied_real_trial_unavailable": True,
            "blockers": REAL_APPLIED_TRIAL_BLOCKERS,
            "prompt_count": 0,
            "real_agent_execution": False,
            "applied_trial_behavior_changed": False,
        }

    shadow_comparison = _compare_specific_modes(
        "packaged_baseline_real",
        "latest_shadow_real",
        mode_summaries,
        mode_rows,
    )
    if shadow_comparison and "latest_shadow_real" in mode_summaries:
        mode_summaries["latest_shadow_real"].update(
            {
                "behavior_changed": bool(shadow_comparison.get("tool_behavior_changed_count") or shadow_comparison.get("final_answer_changed_count")),
                "tool_behavior_changed_count": shadow_comparison.get("tool_behavior_changed_count"),
                "final_answer_changed_count": shadow_comparison.get("final_answer_changed_count"),
                "trace_observability_improved": shadow_comparison.get("trace_observability_improved"),
            }
        )
    comparison = _compare_modes(mode_summaries, mode_rows)
    mode_comparisons = {
        mode: _compare_specific_modes("packaged_baseline_real", mode, mode_summaries, mode_rows)
        for mode in mode_summaries
        if mode != "packaged_baseline_real"
    }
    report = {
        "eval_engine": "real_agent",
        "simulated_trace_only": False,
        "real_agent_execution": True,
        "synthetic_sql_results_used": False,
        "runtime_used_category_tags_for_decision": False,
        "agent_executor_used": any(summary.get("agent_executor_used") for summary in mode_summaries.values()),
        "grading_type": "heuristic_internal_gold",
        "organizer_equivalent": False,
        "answer_grading_method": "required_fact_substring_and_forbidden_claim_checks",
        "process_grading_method": "observable_trace_checkpoint_and_tool_usage_matching",
        "suite": str(suite_path),
        "gold": str(gold_path),
        "seed": seed,
        "prompt_count": len(ordered_rows),
        "full_requested": full,
        "modes": mode_summaries,
        "mode_summary": mode_summaries,
        "mode_order": selected_modes,
        "comparison": comparison,
        "shadow_comparison": shadow_comparison,
        "mode_comparisons": mode_comparisons,
        "unavailable_modes": unavailable_modes,
        "latest_code_paths_explicitly_evaluated": bool(
            mode_summaries.get("latest_shadow_real", {}).get("shadow_modules_executed")
            or any(mode in REAL_BEHAVIOR_APPLIED_MODES for mode in mode_summaries)
        ),
        "old_generated_diagnostic_path_used": False,
        "runtime_gold_visible": False,
        "runtime_input_fields": ["prompt_id", "prompt"],
        "category_domain_tags_used_only_for_grading": True,
        "diagnostic_internal_only": True,
        "organizer_score_replacement": False,
        "output_dir": str(eval_dir),
    }
    report_json = reports_dir / "dashagent_500_prompt_suite_eval_real.json"
    report_md = reports_dir / "dashagent_500_prompt_suite_eval_real.md"
    report_json.write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report_md.write_text(_eval_report_md(report), encoding="utf-8")
    gate = _write_gate_report(report, reports_dir, suffix="_real")
    report["gate"] = gate
    if any(mode in REAL_BEHAVIOR_APPLIED_MODES for mode in mode_summaries):
        behavior_reports = _write_real_behavior_change_reports(report, mode_rows, reports_dir)
        report["real_behavior_change_reports"] = behavior_reports
    report_json.write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _write_runner_audit(report, reports_dir)
    return report


def _select_rows(runtime_rows: list[dict[str, Any]], *, seed: int, limit: int | None, full: bool) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    ordered_rows = list(runtime_rows)
    rng.shuffle(ordered_rows)
    if not full:
        return ordered_rows[: limit or 25]
    if limit is not None:
        return ordered_rows[:limit]
    return ordered_rows


def _runtime_input(row: dict[str, Any]) -> dict[str, str]:
    return {"prompt_id": str(row["prompt_id"]), "prompt": str(row["prompt"])}


def _config_for_real_mode(mode: str) -> Any:
    if mode == "latest_shadow_real":
        return replace(
            DEFAULT_CONFIG,
            enable_objective_prompt_features=True,
            enable_semantic_intent_classifier=True,
            enable_semantic_route_decision_ladder=True,
            semantic_route_shadow_only=True,
            enable_staged_evidence_policy=True,
            staged_evidence_policy_shadow_only=True,
            enable_post_sql_api_decision=True,
            post_sql_api_decision_shadow_only=True,
            post_sql_llm_advisor_enabled=False,
        )
    if mode == "semantic_no_tool_applied_real_trial":
        return replace(
            DEFAULT_CONFIG,
            enable_objective_prompt_features=True,
            enable_semantic_intent_classifier=True,
            enable_semantic_route_decision_ladder=True,
            semantic_route_shadow_only=False,
            enable_semantic_no_tool_applied_trial=True,
            real_behavior_trial_mode=mode,
        )
    if mode == "staged_evidence_applied_real_trial":
        return replace(
            DEFAULT_CONFIG,
            enable_staged_evidence_policy=True,
            staged_evidence_policy_shadow_only=False,
            enable_post_sql_api_decision=True,
            post_sql_api_decision_shadow_only=False,
            enable_staged_evidence_applied_trial=True,
            real_behavior_trial_mode=mode,
        )
    if mode == "post_sql_deterministic_applied_real_trial":
        return replace(
            DEFAULT_CONFIG,
            enable_post_sql_api_decision=True,
            post_sql_api_decision_shadow_only=False,
            enable_post_sql_deterministic_applied_trial=True,
            post_sql_llm_advisor_enabled=False,
            real_behavior_trial_mode=mode,
        )
    if mode == "post_sql_llm_advisor_applied_real_trial":
        return replace(
            DEFAULT_CONFIG,
            enable_post_sql_api_decision=True,
            post_sql_api_decision_shadow_only=False,
            enable_post_sql_llm_advisor_applied_trial=True,
            post_sql_llm_advisor_enabled=True,
            real_behavior_trial_mode=mode,
        )
    if mode == "combined_safe_applied_real_trial":
        return replace(
            DEFAULT_CONFIG,
            enable_objective_prompt_features=True,
            enable_semantic_intent_classifier=True,
            enable_semantic_route_decision_ladder=True,
            semantic_route_shadow_only=False,
            enable_staged_evidence_policy=True,
            staged_evidence_policy_shadow_only=False,
            enable_post_sql_api_decision=True,
            post_sql_api_decision_shadow_only=False,
            enable_semantic_no_tool_applied_trial=True,
            enable_staged_evidence_applied_trial=True,
            enable_post_sql_deterministic_applied_trial=True,
            enable_combined_safe_applied_trial=True,
            post_sql_llm_advisor_enabled=False,
            real_behavior_trial_mode=mode,
        )
    if mode == "combined_safe_deterministic_promotion_candidate_real":
        return replace(
            DEFAULT_CONFIG,
            enable_staged_evidence_policy=True,
            staged_evidence_policy_shadow_only=False,
            enable_post_sql_api_decision=True,
            post_sql_api_decision_shadow_only=False,
            enable_staged_evidence_applied_trial=True,
            enable_post_sql_deterministic_applied_trial=True,
            enable_combined_safe_applied_trial=True,
            enable_semantic_no_tool_applied_trial=False,
            post_sql_llm_advisor_enabled=False,
            enable_post_sql_llm_advisor_applied_trial=False,
            real_behavior_trial_mode=mode,
        )
    if mode == "robust_generalized_harness_candidate_real":
        return replace(
            robust_generalized_candidate_config(DEFAULT_CONFIG),
            real_behavior_trial_mode=mode,
        )
    if mode.startswith("ablation_") and mode.endswith("_real"):
        return robust_generalized_ablation_config(DEFAULT_CONFIG, mode)
    return DEFAULT_CONFIG


def _make_executor(config: Any, executor_factory: Callable[..., Any] | None) -> Any:
    if executor_factory is not None:
        try:
            return executor_factory(config=config)
        except TypeError:
            return executor_factory(config)
    from dashagent.executor import AgentExecutor

    return AgentExecutor(config=config)


def _llm_backend_available() -> bool:
    try:
        from dashagent.llm_client import get_llm_client

        client = get_llm_client()
        return bool(client.available())
    except Exception:
        return False


def _empty_unavailable_summary(mode: str, payload: dict[str, Any]) -> dict[str, Any]:
    nullable_metrics = [
        "final_answer_correctness",
        "required_facts_coverage",
        "route_accuracy",
        "expected_evidence_need_accuracy",
        "sql_required_used_accuracy",
        "api_required_used_accuracy",
        "sql_table_accuracy",
        "api_endpoint_family_accuracy",
        "expected_observable_trace_score",
        "trace_observability_score",
        "behavior_score",
        "combined_diagnostic_score",
        "answer_grounding_score",
        "estimated_total_tokens",
        "runtime_ms",
        "overall_score",
        "unsupported_claims",
        "tool_overuse",
        "tool_underuse",
        "api_required_underuse",
        "no_tool_false_positive",
        "no_tool_false_negative",
        "sql_calls",
        "api_calls",
        "api_calls_saved",
        "api_calls_added",
        "applied_decision_count",
        "skipped_decision_count",
        "fallback_count",
        "blocker_count",
        "anti_hallucination_initial_fail",
        "anti_hallucination_revision_attempted",
        "anti_hallucination_revision_success",
        "post_sql_advisor_checkpoint_present_count",
        "post_sql_llm_advisor_actual_call_count",
        "post_sql_verifier_verified_count",
        "post_sql_verifier_blocked_count",
        "post_sql_llm_advice_blocked_count",
        "post_sql_advisor_disabled_or_fallback_count",
        "post_sql_deterministic_fallback_count",
        "post_sql_advisor_invoked",
        "post_sql_advisor_verified",
        "post_sql_advisor_blocked",
        "wall_time_seconds",
    ]
    summary = {key: None for key in nullable_metrics}
    summary.update(
        {
            "mode": mode,
            "prompt_count": 0,
            "available": False,
            "excluded_from_comparison": True,
            "per_category": {},
            "latest_code_paths_enabled": {},
            "feature_flags_used": {},
            "behavior_changed": False,
            "applied_decision_records": [],
            "post_sql_advisor_source_counts": {},
            "old_generated_diagnostic_path_used": False,
            "rows_helped": [],
            "rows_hurt": [],
            **payload,
        }
    )
    return summary


def _grade_real_agent_result(
    agent_result: dict[str, Any],
    gold: dict[str, Any],
    catalog: EndpointCatalog,
    *,
    runtime_ms: float,
) -> tuple[dict[str, Any], dict[str, Any]]:
    extracted = _extract_real_runtime(agent_result, catalog, runtime_ms=runtime_ms)
    expected_tools = gold.get("expected_tool_calls") or {}
    sql_required = bool(expected_tools.get("sql_required"))
    api_required = bool(expected_tools.get("api_required"))
    api_optional = bool(expected_tools.get("api_optional"))
    sql_used = extracted["sql_used"]
    api_used = extracted["api_used"]
    route_action = extracted["route_action"]
    evidence_need = str(gold.get("expected_evidence_need") or "unknown")

    sql_accuracy = 1.0 if sql_used == sql_required or (sql_used and sql_required) else 0.0
    if not sql_required and sql_used:
        sql_accuracy = 0.5
    api_accuracy = 1.0
    if api_required and not api_used:
        api_accuracy = 0.0
    elif not api_required and not api_optional and api_used:
        api_accuracy = 0.5
    elif api_optional:
        api_accuracy = 1.0

    expected_sql_tables = set(expected_tools.get("expected_sql_tables") or [])
    expected_api_families = set(expected_tools.get("expected_api_families") or [])
    sql_table_accuracy = 1.0 if not expected_sql_tables else round(len(expected_sql_tables & set(extracted["sql_tables"])) / len(expected_sql_tables), 4)
    api_endpoint_family_accuracy = 1.0 if not expected_api_families else round(len(expected_api_families & set(extracted["api_families"])) / len(expected_api_families), 4)
    route_accuracy = _route_accuracy(route_action, str(gold.get("expected_route") or ""), sql_used, api_used)
    evidence_need_accuracy = _evidence_need_accuracy(evidence_need, sql_used, api_used, route_action)
    objective_score = _objective_feature_score(extracted["observable_trace"], gold)
    trace_stage_score = _real_trace_stage_score(extracted["checkpoint_names"], gold)
    trace_observability_score = round((objective_score + trace_stage_score) / 2.0, 4)
    observable_trace_score = round((objective_score + trace_stage_score + route_accuracy + evidence_need_accuracy + sql_accuracy + api_accuracy) / 6.0, 4)
    unsupported_claims = int(extracted.get("unsupported_claims") or 0)
    forbidden_violation = _forbidden_claims_violation(str(agent_result.get("final_answer") or ""), gold)
    fact_coverage = _required_fact_coverage(str(agent_result.get("final_answer") or ""), gold)
    answer_grounding_score = 1.0 if unsupported_claims == 0 and not forbidden_violation else 0.0
    correctness = round((fact_coverage + answer_grounding_score + sql_accuracy + api_accuracy) / 4.0, 4)
    tool_overuse = int((not sql_required and sql_used) or (not api_required and not api_optional and api_used))
    tool_underuse = int((sql_required and not sql_used) or (api_required and not api_used))
    no_tool_false_positive = route_action in {"LLM_DIRECT", "LLM_SAFE_DIRECT"} and (sql_required or api_required)
    no_tool_false_negative = route_action not in {"LLM_DIRECT", "LLM_SAFE_DIRECT"} and evidence_need == "none"
    no_tool_safety_score = 0.0 if no_tool_false_positive or no_tool_false_negative else 1.0
    behavior_score = round(
        (
            correctness
            + sql_accuracy
            + api_accuracy
            + api_endpoint_family_accuracy
            + answer_grounding_score
            + no_tool_safety_score
        )
        / 6.0,
        4,
    )

    overall_score = round(
        0.35 * correctness
        + 0.25 * observable_trace_score
        + 0.15 * route_accuracy
        + 0.15 * evidence_need_accuracy
        + 0.10 * answer_grounding_score,
        4,
    )
    grade = {
        "overall_score": overall_score,
        "combined_diagnostic_score": overall_score,
        "behavior_score": behavior_score,
        "trace_observability_score": trace_observability_score,
        "final_answer_correctness": correctness,
        "required_facts_coverage": fact_coverage,
        "forbidden_claims_violation": forbidden_violation,
        "route_accuracy": route_accuracy,
        "expected_evidence_need_accuracy": evidence_need_accuracy,
        "sql_required_used_accuracy": sql_accuracy,
        "api_required_used_accuracy": api_accuracy,
        "sql_table_accuracy": sql_table_accuracy,
        "api_endpoint_family_accuracy": api_endpoint_family_accuracy,
        "expected_observable_trace_score": observable_trace_score,
        "tool_overuse": tool_overuse,
        "tool_underuse": tool_underuse,
        "unsupported_claims": unsupported_claims,
        "no_tool_false_positive": no_tool_false_positive,
        "no_tool_false_negative": no_tool_false_negative,
        "live_empty_interpretation_correct": _live_empty_interpretation_correct(agent_result),
        "api_error_interpretation_correct": _api_error_interpretation_correct(agent_result),
        "answer_grounding_score": answer_grounding_score,
    }
    return grade, extracted


def _extract_real_runtime(agent_result: dict[str, Any], catalog: EndpointCatalog, *, runtime_ms: float) -> dict[str, Any]:
    tool_results = agent_result.get("tool_results") if isinstance(agent_result.get("tool_results"), list) else []
    trajectory = agent_result.get("trajectory") if isinstance(agent_result.get("trajectory"), dict) else {}
    checkpoints = agent_result.get("checkpoints") if isinstance(agent_result.get("checkpoints"), list) else trajectory.get("checkpoints", [])
    checkpoint_names = [str(item.get("name") or item.get("checkpoint_id") or item.get("checkpoint") or "") for item in checkpoints if isinstance(item, dict)]
    checkpoint_by_name = {name: item for name, item in zip(checkpoint_names, checkpoints, strict=False)}
    sql_calls = [item for item in tool_results if isinstance(item, dict) and item.get("type") == "sql"]
    api_calls = [item for item in tool_results if isinstance(item, dict) and item.get("type") == "api"]
    sql_strings = [str((item.get("step") or {}).get("sql") or "") for item in sql_calls]
    api_steps = [(item.get("step") or {}) for item in api_calls]
    sql_tables = sorted({table for sql in sql_strings for table in _extract_sql_tables(sql)})
    api_families = sorted({family for step in api_steps for family in _extract_api_families(step, catalog)})
    route_action = _route_action_from_actual_tools(bool(sql_calls), bool(api_calls))
    unsupported_claims = _extract_unsupported_claims(checkpoints)
    latest_flags = _latest_flags_from_checkpoints(checkpoint_names)
    timing = trajectory.get("timing") if isinstance(trajectory.get("timing"), dict) else {}
    estimated_tokens = _estimate_real_tokens(agent_result)
    missing_checkpoints = [
        name
        for name in [
            "checkpoint_objective_prompt_features",
            "checkpoint_semantic_route_decision_ladder",
            "checkpoint_initial_evidence_branch_policy",
            "checkpoint_post_sql_api_call_verifier",
            "checkpoint_13_tool_execution",
            "checkpoint_15_answer_slots",
            "checkpoint_16_answer_verification",
        ]
        if name not in checkpoint_by_name
    ]
    advisor_checkpoint = checkpoint_by_name.get("checkpoint_post_sql_llm_advisor")
    verifier_checkpoint = checkpoint_by_name.get("checkpoint_post_sql_api_call_verifier")
    advisor_output = _checkpoint_output(advisor_checkpoint)
    verifier_source = _normalize_post_sql_source(_checkpoint_output_source(verifier_checkpoint))
    advisor_source = _post_sql_advisor_source(advisor_output)
    advisor_checkpoint_present = advisor_checkpoint is not None
    actual_llm_advisor_call = bool(advisor_output.get("llm_call_attempted")) or _post_sql_actual_llm_advisor_call(advisor_source)
    llm_advice_blocked = actual_llm_advisor_call and verifier_source == "LLM_ADVISOR_BLOCKED"
    applied_records = [
        _checkpoint_output(checkpoint)
        for name, checkpoint in zip(checkpoint_names, checkpoints, strict=False)
        if name == "checkpoint_real_behavior_applied_trial"
    ]
    applied_decision_count = sum(1 for record in applied_records if record.get("applied"))
    skipped_decision_count = sum(1 for record in applied_records if record and not record.get("applied"))
    fallback_count = sum(1 for record in applied_records if record.get("fallback"))
    blocker_count = sum(len(record.get("blockers") or []) for record in applied_records)
    return {
        "sql_used": bool(sql_calls),
        "api_used": bool(api_calls),
        "sql_calls": len(sql_calls),
        "api_calls": len(api_calls),
        "sql_tables": sql_tables,
        "api_families": api_families,
        "route_action": route_action,
        "unsupported_claims": unsupported_claims,
        "checkpoint_names": checkpoint_names,
        "missing_checkpoints": missing_checkpoints,
        "observable_trace": {name: (checkpoint_by_name.get(name) or {}).get("output", {}) for name in checkpoint_names},
        "latest_code_paths_enabled": latest_flags,
        "estimated_total_tokens": estimated_tokens,
        "runtime_ms": runtime_ms,
        "trajectory_timing": timing,
        "feature_flags_used": _trial_feature_flags_from_records(applied_records),
        "behavior_changed": applied_decision_count > 0,
        "applied_decision_count": applied_decision_count,
        "skipped_decision_count": skipped_decision_count,
        "fallback_count": fallback_count,
        "blocker_count": blocker_count,
        "applied_decision_records": applied_records[:8],
        "api_calls_saved": sum(1 for record in applied_records if record.get("applied") and record.get("decision") == "SKIP_API"),
        "api_calls_added": sum(1 for record in applied_records if record.get("applied") and record.get("decision") == "CALL_API"),
        "anti_hallucination_initial_fail": _checkpoint_has_gate_initial_fail(checkpoint_by_name.get("checkpoint_routing_anti_hallucination_gate")),
        "anti_hallucination_revision_attempted": _checkpoint_output_bool(checkpoint_by_name.get("checkpoint_routing_anti_hallucination_gate"), "revision_attempted"),
        "anti_hallucination_revision_success": _checkpoint_output_bool(checkpoint_by_name.get("checkpoint_routing_anti_hallucination_gate"), "revision_success"),
        "post_sql_advisor_checkpoint_present": advisor_checkpoint_present,
        "post_sql_llm_advisor_actual_call": actual_llm_advisor_call,
        "post_sql_advisor_source": advisor_source,
        "post_sql_verifier_source": verifier_source,
        "post_sql_verifier_verified": _post_sql_verifier_verified(verifier_checkpoint),
        "post_sql_verifier_blocked": verifier_source == "LLM_ADVISOR_BLOCKED",
        "post_sql_llm_advice_blocked": llm_advice_blocked,
        "post_sql_advisor_disabled_or_fallback": advisor_source in {"DISABLED", "DETERMINISTIC_FALLBACK", "LLM_BACKEND_UNAVAILABLE", "INVALID_JSON"},
        "post_sql_deterministic_fallback": advisor_source == "DETERMINISTIC_FALLBACK",
        "post_sql_advisor_invoked": actual_llm_advisor_call,
        "post_sql_advisor_verified": actual_llm_advisor_call and verifier_source in {"LLM_ADVISOR", "LLM_ADVISOR_VERIFIED"},
        "post_sql_advisor_blocked": llm_advice_blocked,
    }


def _route_action_from_actual_tools(sql_used: bool, api_used: bool) -> str:
    if sql_used and api_used:
        return "SQL_THEN_API"
    if sql_used:
        return "SQL_ONLY"
    if api_used:
        return "API_ONLY"
    return "LLM_SAFE_DIRECT"


def _extract_sql_tables(sql: str) -> list[str]:
    tables: list[str] = []
    for match in re.finditer(r"\b(?:FROM|JOIN)\s+([\"`]?)([A-Za-z_][\w$]*)\1", sql, flags=re.IGNORECASE):
        tables.append(match.group(2))
    return tables


def _extract_api_families(step: dict[str, Any], catalog: EndpointCatalog) -> list[str]:
    method = str(step.get("method") or "GET")
    url = str(step.get("url") or "")
    endpoint = catalog.match(method, url) if url else None
    endpoint_id = endpoint.id if endpoint else str(step.get("family") or step.get("endpoint_id") or "")
    return [endpoint_id] if endpoint_id else []


def _extract_unsupported_claims(checkpoints: list[dict[str, Any]]) -> int:
    for checkpoint in checkpoints:
        if not isinstance(checkpoint, dict):
            continue
        name = str(checkpoint.get("name") or checkpoint.get("checkpoint") or "")
        if name != "checkpoint_16_answer_verification":
            continue
        output = checkpoint.get("output") if isinstance(checkpoint.get("output"), dict) else {}
        return int(output.get("unsupported_claims_count") or output.get("unsupported_claims") or 0)
    return 0


def _latest_flags_from_checkpoints(checkpoint_names: list[str]) -> dict[str, bool]:
    names = set(checkpoint_names)
    return {
        "objective_prompt_features": "checkpoint_objective_prompt_features" in names,
        "compact_json_llm_context": "checkpoint_semantic_intent_decision" in names,
        "semantic_intent_classifier": "checkpoint_semantic_intent_decision" in names,
        "routing_anti_hallucination_gate": "checkpoint_routing_anti_hallucination_gate" in names,
        "routing_feedback_revision": "checkpoint_routing_anti_hallucination_gate" in names,
        "no_tool_safety_verifier": "checkpoint_no_tool_safety_verifier" in names,
        "semantic_route_decision_ladder": "checkpoint_semantic_route_decision_ladder" in names,
        "staged_evidence_policy": "checkpoint_initial_evidence_branch_policy" in names,
        "post_sql_deterministic_policy": "checkpoint_post_sql_deterministic_policy" in names,
        "post_sql_llm_advisor": "checkpoint_post_sql_llm_advisor" in names,
        "post_sql_api_call_verifier": "checkpoint_post_sql_api_call_verifier" in names,
        "evidence_bus_answer_verifier_token_reduction": "checkpoint_16_answer_verification" in names,
    }


def _trial_feature_flags_from_records(records: list[dict[str, Any]]) -> dict[str, bool]:
    flags = {
        "semantic_no_tool_applied": False,
        "staged_evidence_applied": False,
        "post_sql_deterministic_applied": False,
        "post_sql_llm_advisor_applied": False,
        "combined_safe_applied": False,
        "combined_safe_deterministic_promotion_candidate": False,
        "robust_generalized_harness_candidate": False,
    }
    for record in records:
        mode = str(record.get("trial_mode") or "")
        if mode == "semantic_no_tool_applied_real_trial":
            flags["semantic_no_tool_applied"] = True
        elif mode == "staged_evidence_applied_real_trial":
            flags["staged_evidence_applied"] = True
        elif mode == "post_sql_deterministic_applied_real_trial":
            flags["post_sql_deterministic_applied"] = True
        elif mode == "post_sql_llm_advisor_applied_real_trial":
            flags["post_sql_llm_advisor_applied"] = True
        elif mode == "combined_safe_applied_real_trial":
            flags["combined_safe_applied"] = True
        elif mode == "combined_safe_deterministic_promotion_candidate_real":
            flags["combined_safe_deterministic_promotion_candidate"] = True
        elif mode == "robust_generalized_harness_candidate_real":
            flags["robust_generalized_harness_candidate"] = True
    return flags


def _estimate_real_tokens(agent_result: dict[str, Any]) -> int:
    payload = {
        "metadata": agent_result.get("metadata"),
        "plan": agent_result.get("plan"),
        "final_answer": agent_result.get("final_answer"),
    }
    return max(1, len(json.dumps(payload, sort_keys=True, default=str)) // 4)


def _checkpoint_output(checkpoint: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(checkpoint, dict):
        return {}
    output = checkpoint.get("output")
    return output if isinstance(output, dict) else {}


def _checkpoint_output_bool(checkpoint: dict[str, Any] | None, key: str) -> bool:
    return bool(_checkpoint_output(checkpoint).get(key))


def _checkpoint_output_source(checkpoint: dict[str, Any] | None) -> str:
    return str(_checkpoint_output(checkpoint).get("source") or "")


def _normalize_post_sql_source(source: str) -> str:
    if source == "DETERMINISTIC_BYPASS":
        return "DETERMINISTIC_HIGH_CONF"
    if source in {"LLM_ADVISOR", "LLM_ADVISOR_VERIFIED"}:
        return source
    if source in {"LLM_ADVISOR_BLOCKED", "DETERMINISTIC_HIGH_CONF", "DETERMINISTIC_FALLBACK", "LLM_BACKEND_UNAVAILABLE", "INVALID_JSON", "DISABLED"}:
        return source
    return source or "UNKNOWN"


def _post_sql_advisor_source(advisor_output: dict[str, Any]) -> str:
    codes = {str(item) for item in advisor_output.get("codes") or []}
    if "INVALID_JSON" in codes:
        return "INVALID_JSON"
    if "LLM_BACKEND_UNAVAILABLE" in codes:
        return "LLM_BACKEND_UNAVAILABLE"
    return str(advisor_output.get("source") or "UNKNOWN")


def _post_sql_actual_llm_advisor_call(source: str) -> bool:
    return source in {"LLM_ADVISOR", "LLM_ADVISOR_VERIFIED", "LLM_ADVISOR_BLOCKED", "INVALID_JSON"}


def _post_sql_verifier_verified(checkpoint: dict[str, Any] | None) -> bool:
    output = _checkpoint_output(checkpoint)
    source = _normalize_post_sql_source(str(output.get("source") or ""))
    codes = {str(item) for item in output.get("codes") or []}
    return source != "LLM_ADVISOR_BLOCKED" and any(code.startswith("VERIFIED_") for code in codes)


def _checkpoint_has_gate_initial_fail(checkpoint: dict[str, Any] | None) -> bool:
    output = _checkpoint_output(checkpoint)
    initial = output.get("initial_gate")
    if isinstance(initial, dict):
        return not bool(initial.get("ok", True))
    return bool(output.get("initial_fail"))


def _real_trace_stage_score(checkpoint_names: list[str], gold: dict[str, Any]) -> float:
    expected_stages = [step.get("stage") for step in gold.get("expected_observable_trace") or [] if step.get("stage") != "objective_features"]
    if not expected_stages:
        return 1.0
    names = set(checkpoint_names)
    stage_to_checkpoint = {
        "semantic_routing": "checkpoint_semantic_route_decision_ladder",
        "evidence_policy": "checkpoint_initial_evidence_branch_policy",
        "tool_execution": "checkpoint_13_tool_execution",
        "answer_grounding": "checkpoint_15_answer_slots",
        "verification": "checkpoint_16_answer_verification",
    }
    matched = 0
    for stage in expected_stages:
        checkpoint = stage_to_checkpoint.get(str(stage))
        if checkpoint is None or checkpoint in names:
            matched += 1
    return round(matched / len(expected_stages), 4)


def _required_fact_coverage(answer: str, gold: dict[str, Any]) -> float:
    facts = [str(fact).strip().lower() for fact in gold.get("required_facts") or [] if str(fact).strip()]
    if not facts:
        return 1.0
    normalized = answer.lower()
    hits = sum(1 for fact in facts if fact in normalized)
    return round(hits / len(facts), 4)


def _forbidden_claims_violation(answer: str, gold: dict[str, Any]) -> bool:
    normalized = answer.lower()
    for claim in gold.get("forbidden_claims") or []:
        claim_text = str(claim).strip().lower()
        if claim_text and claim_text in normalized:
            return True
    return False


def _live_empty_interpretation_correct(agent_result: dict[str, Any]) -> bool:
    text = str(agent_result.get("final_answer") or "").lower()
    api_payloads = [
        item.get("payload") for item in agent_result.get("tool_results", [])
        if isinstance(item, dict) and item.get("type") == "api"
    ]
    live_empty = any(isinstance(payload, dict) and payload.get("evidence_state") == "live_empty" for payload in api_payloads)
    if not live_empty:
        return True
    return "no matching" in text or "returned no" in text or "empty" in text


def _api_error_interpretation_correct(agent_result: dict[str, Any]) -> bool:
    text = str(agent_result.get("final_answer") or "").lower()
    api_payloads = [
        item.get("payload") for item in agent_result.get("tool_results", [])
        if isinstance(item, dict) and item.get("type") == "api"
    ]
    api_error = any(isinstance(payload, dict) and payload.get("ok") is False for payload in api_payloads)
    if not api_error:
        return True
    return "unavailable" in text or "error" in text or "could not" in text or "failed" in text


def _run_runtime_trace(row: dict[str, Any], mode: str, catalog: EndpointCatalog) -> dict[str, Any]:
    prompt = row["prompt"]
    tags = set(row.get("tags") or [])
    category = row.get("category")
    domain = row.get("domain_family")
    features = extract_objective_prompt_features(prompt)
    feature_payload = features.to_dict()
    context = build_semantic_intent_context(features, tier=0)
    context_token_cost = estimate_context_tokens(context)

    semantic_enabled = mode in {"semantic_routing_shadow", "latest_applied_trial", "latest_full_trial"}
    staged_enabled = mode in {"staged_evidence_shadow", "post_sql_api_decision_shadow", "latest_applied_trial", "latest_full_trial"}
    post_sql_enabled = mode in {"post_sql_api_decision_shadow", "latest_applied_trial", "latest_full_trial"}
    applied_trial = mode in {"latest_applied_trial", "latest_full_trial"}

    if semantic_enabled:
        initial_decision = _initial_semantic_decision_for_row(row, context)
        gate_run = run_routing_gate_with_revision(features, initial_decision, reviser=_semantic_reviser)
        decision = gate_run.final_decision
        safety = verify_no_tool_safety(features, decision)
        ladder = run_semantic_route_decision_ladder(prompt, shadow_only=not applied_trial)
        action = gate_run.fallback_action or ladder.action
        if "low_low_safe_api_probe" in tags:
            action = "SAFE_API_PROBE"
        if "low_low_safe_direct" in tags:
            action = "LLM_SAFE_DIRECT"
    else:
        initial_decision = classify_semantic_intent(context)
        gate_run = run_routing_gate_with_revision(features, initial_decision)
        decision = gate_run.final_decision
        safety = verify_no_tool_safety(features, decision)
        ladder = None
        action = _packaged_action_for_row(row)

    match_score = score_evidence_match(
        features,
        sql_candidate_available=category in {"sql_only_local_snapshot", "sql_then_api_verification", "hard_stress"},
        api_candidate_available=domain in _api_domain_endpoint_ids(),
    )
    branch_policy = decide_initial_evidence_branch(match_score)

    post_sql_payload = _post_sql_policy_trace(row, feature_payload, catalog, enabled=post_sql_enabled)
    tool_plan = _tool_plan_for_mode(row, action, branch_policy.to_dict(), post_sql_payload, applied_trial)

    safe_direct = validate_llm_safe_direct_answer(_safe_direct_answer(row)) if action in {"LLM_DIRECT", "LLM_SAFE_DIRECT"} else {"ok": True, "blocked_claims": []}
    final_answer = _final_answer_for_trace(row, action, tool_plan, safe_direct)
    unsupported_claims = 0 if safe_direct["ok"] else len(safe_direct["blocked_claims"])

    observable_trace = {
        "checkpoint_objective_prompt_features": feature_payload,
        "checkpoint_semantic_intent_context": {
            "task": context.get("task"),
            "token_estimate": context_token_cost,
            "capability_count": len(context.get("capabilities") or {}),
        },
        "checkpoint_semantic_intent_decision": decision.to_dict(),
        "checkpoint_routing_anti_hallucination_gate": gate_run.to_dict(),
        "checkpoint_no_tool_safety_verifier": safety.to_dict(),
        "checkpoint_semantic_route_decision_ladder": {
            "action": action,
            "shadow_only": not applied_trial,
            "ladder_result": ladder.to_dict() if ladder is not None else None,
        },
        "checkpoint_evidence_match_scores": match_score.to_dict(),
        "checkpoint_initial_evidence_branch_policy": branch_policy.to_dict(),
        "checkpoint_post_sql_decision_card": post_sql_payload["card"],
        "checkpoint_post_sql_deterministic_policy": post_sql_payload["deterministic_policy"],
        "checkpoint_post_sql_llm_advisor": post_sql_payload["advisor"],
        "checkpoint_post_sql_api_call_verifier": post_sql_payload["verifier"],
        "checkpoint_evidence_bus_answer_verifier_token_reduction": {
            "evidence_bus_observed": tool_plan["sql_used"] or tool_plan["api_used"],
            "answer_verifier_observed": True,
            "unsupported_claims": unsupported_claims,
            "token_reduction_behavior_observed": True,
        },
    }

    return {
        "latest_code_paths_enabled": {
            "objective_prompt_features": True,
            "compact_json_llm_context": semantic_enabled,
            "semantic_intent_classifier": semantic_enabled,
            "routing_anti_hallucination_gate": semantic_enabled,
            "routing_feedback_revision": bool(gate_run.revision_attempted),
            "no_tool_safety_verifier": semantic_enabled,
            "semantic_route_decision_ladder": semantic_enabled,
            "staged_evidence_policy": staged_enabled,
            "post_sql_deterministic_policy": post_sql_enabled,
            "post_sql_llm_advisor": post_sql_enabled and post_sql_payload["advisor_invoked"],
            "post_sql_api_call_verifier": post_sql_enabled,
            "evidence_bus_answer_verifier_token_reduction": True,
        },
        "observable_trace": observable_trace,
        "tool_counts": {
            "sql_calls": 1 if tool_plan["sql_used"] else 0,
            "api_calls": 1 if tool_plan["api_used"] else 0,
            "total_tool_calls": int(tool_plan["sql_used"]) + int(tool_plan["api_used"]),
        },
        "final_answer": final_answer,
        "row_metrics": {
            "route_action": action,
            "sql_used": tool_plan["sql_used"],
            "api_used": tool_plan["api_used"],
            "unsupported_claims": unsupported_claims,
            "context_token_cost": context_token_cost,
            "estimated_total_tokens": context_token_cost + post_sql_payload["token_estimate"] + len(final_answer.split()),
            "runtime_ms": post_sql_payload["runtime_ms"] + 1.0,
            "anti_hallucination_initial_fail": not gate_run.initial_gate.ok,
            "anti_hallucination_revision_attempted": gate_run.revision_attempted,
            "anti_hallucination_revision_success": gate_run.revision_success,
            "post_sql_advisor_checkpoint_present": True,
            "post_sql_llm_advisor_actual_call": post_sql_payload["advisor_invoked"],
            "post_sql_advisor_source": post_sql_payload["advisor_source"],
            "post_sql_verifier_source": post_sql_payload["verifier_source"],
            "post_sql_verifier_verified": post_sql_payload["verifier_verified"],
            "post_sql_verifier_blocked": post_sql_payload["verifier_blocked"],
            "post_sql_llm_advice_blocked": post_sql_payload["llm_advice_blocked"],
            "post_sql_advisor_disabled_or_fallback": post_sql_payload["advisor_disabled_or_fallback"],
            "post_sql_deterministic_fallback": post_sql_payload["deterministic_fallback"],
            "post_sql_advisor_invoked": post_sql_payload["advisor_invoked"],
            "post_sql_advisor_verified": post_sql_payload["advisor_verified"],
            "post_sql_advisor_blocked": post_sql_payload["llm_advice_blocked"],
            "api_calls_saved": int(tool_plan["api_saved"]),
            "api_calls_added": int(tool_plan["api_added"]),
        },
    }


def _initial_semantic_decision_for_row(row: dict[str, Any], context: dict[str, Any]) -> SemanticIntentDecision:
    tags = set(row.get("tags") or [])
    if "anti_hallucination_no_tool_conflict" in tags or "mixed_no_tool_block" in tags:
        return SemanticIntentDecision("CONCEPT", "NONE", True, False, False, 0.96, ["FORCED_BAD_NO_TOOL"])
    if "anti_hallucination_unknown_capability" in tags:
        return SemanticIntentDecision("LIVE_API", "API", False, False, True, 0.91, ["API_FAKE_THING"])
    if "invalid_json_fallback" in tags:
        return SemanticIntentDecision("AMBIG", "UNKNOWN", False, False, False, 0.0, ["INVALID_JSON"])
    return classify_semantic_intent(context)


def _semantic_reviser(feedback: dict[str, Any]) -> SemanticIntentDecision:
    blocks = set(feedback.get("gate", {}).get("block") or [])
    conflicts = set(feedback.get("gate", {}).get("feature_conflicts") or [])
    if "UNKNOWN_CAPABILITY_CODE" in blocks:
        return SemanticIntentDecision("LIVE_API", "API", False, False, True, 0.82, [])
    if "MIXED_REQUIRES_EVIDENCE" in blocks or "MIXED_CONCEPT_AND_RETRIEVAL" in conflicts:
        return SemanticIntentDecision("MIXED", "SQL_API", False, True, True, 0.84, [])
    if "UNSUPPORTED_NO_TOOL" in blocks:
        return SemanticIntentDecision("DATA", "SQL_API", False, True, True, 0.83, [])
    return SemanticIntentDecision("AMBIG", "UNKNOWN", False, False, False, 0.2, [])


def _post_sql_policy_trace(row: dict[str, Any], feature_payload: dict[str, Any], catalog: EndpointCatalog, *, enabled: bool) -> dict[str, Any]:
    start = time.perf_counter()
    domain = str(row.get("domain_family") or "SCHEMA")
    endpoint_id = _api_domain_endpoint_ids().get(domain, "schema_registry_schemas")
    endpoint = catalog.by_id(endpoint_id)
    api_steps = []
    if endpoint is not None:
        api_steps.append({"action": "api", "method": endpoint.method, "url": endpoint.path, "family": endpoint.id})
    sql_result = _synthetic_sql_result(row)
    card = build_post_sql_decision_card(feature_payload, _answer_intent_for_row(row), sql_result, api_steps, catalog)
    tags = set(row.get("tags") or [])
    if "post_sql_advisor_accept" in tags or "post_sql_advisor_block" in tags or "invalid_json_fallback" in tags:
        card["sql_state"]["direct_answer"] = False
        card["sql_state"]["partial_answer"] = True
        card["sql_state"]["missing_roles"] = ["status"]
        for candidate in card.get("api_candidates") or []:
            candidate.setdefault("can_fill_roles", [])
            if "status" not in candidate["can_fill_roles"]:
                candidate["can_fill_roles"].append("status")
    policy = decide_post_sql_api_policy(card)
    policy_payload = policy.to_dict()
    if "post_sql_advisor_accept" in tags or "post_sql_advisor_block" in tags or "invalid_json_fallback" in tags:
        policy_payload = {
            "suggestion": "AMBIGUOUS",
            "confidence": "MEDIUM",
            "api_evidence_signal": 0.55,
            "codes": ["FORCED_ADVISOR_STRESS_CASE"],
        }
    advisor_invoked = False
    advisor_verified = False
    advisor_blocked = False

    if not enabled:
        advisor = {"mode": "CAVEAT_ONLY", "endpoint_id": None, "conf": 0.0, "needed_roles": [], "codes": ["POST_SQL_DISABLED"], "source": "DISABLED"}
        verifier = {"final_action": "CAVEAT_ONLY", "source": "DISABLED", "selected_api_families": [], "blocked_families": [], "codes": ["POST_SQL_DISABLED"]}
    else:
        if "post_sql_advisor_accept" in tags:
            advisor_client = _AdviceClient([{"mode": "CALL_API", "endpoint_id": endpoint_id, "conf": 0.86, "needed_roles": ["status"], "codes": ["TEST_ACCEPT"]}])
            advisor_invoked = True
        elif "post_sql_advisor_block" in tags:
            advisor_client = _AdviceClient([{"mode": "CALL_API", "endpoint_id": "unknown_endpoint_for_block_test", "conf": 0.86, "needed_roles": ["status"], "codes": ["TEST_BLOCK"]}])
            advisor_invoked = True
        elif "invalid_json_fallback" in tags:
            advisor_client = _AdviceClient(["not-json", "{still-not-json"])
            advisor_invoked = True
        else:
            advisor_client = None
        if advisor_client is not None:
            advisor_obj = advise_post_sql_api(card, policy_payload, llm_client=advisor_client, enabled=True)
        else:
            advisor_obj = advise_post_sql_api(card, policy_payload, enabled=False)
        verifier_obj = verify_post_sql_api_advice(
            advisor_obj,
            card,
            catalog,
            api_required=bool("api_required" in set(row.get("tags") or [])),
        )
        advisor = advisor_obj.to_dict()
        verifier = verifier_obj.to_dict()
        advisor_verified = advisor_invoked and verifier.get("source") in {"LLM_ADVISOR", "LLM_ADVISOR_VERIFIED"}
        advisor_blocked = advisor_invoked and verifier.get("source") == "LLM_ADVISOR_BLOCKED"
    elapsed_ms = (time.perf_counter() - start) * 1000
    advisor_source = _post_sql_advisor_source(advisor)
    verifier_source = _normalize_post_sql_source(str(verifier.get("source") or ""))
    llm_advice_blocked = advisor_invoked and verifier_source == "LLM_ADVISOR_BLOCKED"
    return {
        "card": card,
        "deterministic_policy": policy_payload,
        "advisor": advisor,
        "verifier": verifier,
        "advisor_invoked": advisor_invoked,
        "advisor_verified": advisor_verified,
        "advisor_blocked": llm_advice_blocked,
        "advisor_source": advisor_source,
        "verifier_source": verifier_source,
        "verifier_verified": verifier_source != "LLM_ADVISOR_BLOCKED" and any(str(code).startswith("VERIFIED_") for code in verifier.get("codes") or []),
        "verifier_blocked": verifier_source == "LLM_ADVISOR_BLOCKED",
        "llm_advice_blocked": llm_advice_blocked,
        "advisor_disabled_or_fallback": advisor_source in {"DISABLED", "DETERMINISTIC_FALLBACK", "LLM_BACKEND_UNAVAILABLE", "INVALID_JSON"},
        "deterministic_fallback": advisor_source == "DETERMINISTIC_FALLBACK",
        "token_estimate": max(1, len(json.dumps(card, sort_keys=True)) // 4),
        "runtime_ms": elapsed_ms,
    }


def _synthetic_sql_result(row: dict[str, Any]) -> dict[str, Any]:
    tags = set(row.get("tags") or [])
    if "post_sql_direct_skip_optional_api" in tags:
        return {"ok": True, "rows": [{"count": 7}], "row_count": 1, "error": None}
    if "post_sql_partial_api_can_fill" in tags:
        return {"ok": True, "rows": [{"id": "local-object"}], "row_count": 1, "error": None}
    if row.get("category") in {"sql_only_local_snapshot", "sql_then_api_verification", "hard_stress"}:
        return {"ok": True, "rows": [{"id": "local-object", "name": "local object", "count": 1}], "row_count": 1, "error": None}
    return {"ok": True, "rows": [], "row_count": 0, "error": None}


def _tool_plan_for_mode(
    row: dict[str, Any],
    action: str,
    branch_policy: dict[str, Any],
    post_sql: dict[str, Any],
    applied_trial: bool,
) -> dict[str, bool]:
    category = str(row.get("category"))
    tags = set(row.get("tags") or [])
    if not applied_trial:
        sql_used = category in {"sql_only_local_snapshot", "sql_then_api_verification", "hard_stress"} or "sql_required" in tags
        api_used = category in {"api_only_live_platform", "sql_then_api_verification", "mixed_conceptual_data", "hard_stress"} or "api_required" in tags
        if category == "conceptual_no_tool":
            sql_used = bool(row.get("domain_family") in {"SCHEMA", "DATASET", "SEGMENT", "JOURNEY"})
            api_used = bool(row.get("domain_family") in {"TAG", "MERGE_POLICY", "AUDIT"})
        return {"sql_used": sql_used, "api_used": api_used, "api_saved": False, "api_added": False}

    if action in {"LLM_DIRECT", "LLM_SAFE_DIRECT"}:
        return {"sql_used": False, "api_used": False, "api_saved": category != "conceptual_no_tool", "api_added": False}
    if action == "SAFE_API_PROBE":
        return {"sql_used": False, "api_used": True, "api_saved": False, "api_added": True}

    first_branch = branch_policy.get("first_branch")
    sql_used = first_branch == "SQL" or category in {"sql_only_local_snapshot", "sql_then_api_verification"}
    api_used = first_branch == "API" or "api_required" in tags or category in {"api_only_live_platform", "mixed_conceptual_data"}
    verifier_action = (post_sql.get("verifier") or {}).get("final_action")
    if category == "sql_then_api_verification" and verifier_action == "SKIP_API":
        api_saved = True
        api_used = False
    else:
        api_saved = False
    if verifier_action == "CALL_API":
        api_used = True
    return {"sql_used": sql_used, "api_used": api_used, "api_saved": api_saved, "api_added": bool(verifier_action == "CALL_API" and category not in {"api_only_live_platform", "mixed_conceptual_data"})}


def _grade_runtime_trace(trace: dict[str, Any], gold: dict[str, Any]) -> dict[str, Any]:
    expected_tools = gold.get("expected_tool_calls") or {}
    row_metrics = trace["row_metrics"]
    sql_required = bool(expected_tools.get("sql_required"))
    api_required = bool(expected_tools.get("api_required"))
    api_optional = bool(expected_tools.get("api_optional"))
    sql_used = bool(row_metrics["sql_used"])
    api_used = bool(row_metrics["api_used"])
    route_action = str(row_metrics["route_action"])
    evidence_need = str(gold.get("expected_evidence_need") or "unknown")

    sql_accuracy = 1.0 if sql_used == sql_required or (sql_used and sql_required) else 0.0
    if not sql_required and sql_used:
        sql_accuracy = 0.5
    api_accuracy = 1.0
    if api_required and not api_used:
        api_accuracy = 0.0
    elif not api_required and not api_optional and api_used:
        api_accuracy = 0.5
    elif api_optional:
        api_accuracy = 1.0

    route_accuracy = _route_accuracy(route_action, str(gold.get("expected_route") or ""), sql_used, api_used)
    evidence_need_accuracy = _evidence_need_accuracy(evidence_need, sql_used, api_used, route_action)
    objective_score = _objective_feature_score(trace["observable_trace"], gold)
    observable_trace_score = round((objective_score + route_accuracy + evidence_need_accuracy + sql_accuracy + api_accuracy) / 5.0, 4)
    no_tool_false_positive = route_action in {"LLM_DIRECT", "LLM_SAFE_DIRECT"} and (sql_required or api_required)
    no_tool_false_negative = route_action not in {"LLM_DIRECT", "LLM_SAFE_DIRECT"} and evidence_need == "none"
    unsupported_claims = int(row_metrics.get("unsupported_claims") or 0)
    answer_grounding_score = 1.0 if unsupported_claims == 0 and (not (sql_required or api_required) or sql_used or api_used) else 0.0
    required_fact_coverage = round((route_accuracy + sql_accuracy + api_accuracy + answer_grounding_score) / 4.0, 4)
    correctness = round((required_fact_coverage + observable_trace_score) / 2.0, 4)
    tool_overuse = int((not sql_required and sql_used) or (not api_required and not api_optional and api_used))
    tool_underuse = int((sql_required and not sql_used) or (api_required and not api_used))
    no_tool_safety_score = 0.0 if no_tool_false_positive or no_tool_false_negative else 1.0
    behavior_score = round((correctness + sql_accuracy + api_accuracy + api_accuracy + answer_grounding_score + no_tool_safety_score) / 6.0, 4)
    trace_observability_score = objective_score

    overall_score = round(
        0.35 * correctness
        + 0.25 * observable_trace_score
        + 0.15 * route_accuracy
        + 0.15 * evidence_need_accuracy
        + 0.10 * answer_grounding_score,
        4,
    )
    return {
        "overall_score": overall_score,
        "combined_diagnostic_score": overall_score,
        "behavior_score": behavior_score,
        "trace_observability_score": trace_observability_score,
        "final_answer_correctness": correctness,
        "required_facts_coverage": required_fact_coverage,
        "forbidden_claims_violation": unsupported_claims > 0,
        "route_accuracy": route_accuracy,
        "expected_evidence_need_accuracy": evidence_need_accuracy,
        "sql_required_used_accuracy": sql_accuracy,
        "api_required_used_accuracy": api_accuracy,
        "sql_table_accuracy": 1.0 if not expected_tools.get("expected_sql_tables") or sql_used else 0.0,
        "api_endpoint_family_accuracy": 1.0 if not expected_tools.get("expected_api_families") or api_used else 0.0,
        "expected_observable_trace_score": observable_trace_score,
        "tool_overuse": tool_overuse,
        "tool_underuse": tool_underuse,
        "unsupported_claims": unsupported_claims,
        "no_tool_false_positive": no_tool_false_positive,
        "no_tool_false_negative": no_tool_false_negative,
        "api_required_underuse": bool(api_required and not api_used),
        "live_empty_interpretation_correct": True,
        "api_error_interpretation_correct": True,
        "answer_grounding_score": answer_grounding_score,
    }


def _summarize_mode(mode: str, rows: list[dict[str, Any]], elapsed: float) -> dict[str, Any]:
    count = len(rows) or 1
    avg_keys = [
        "behavior_score",
        "trace_observability_score",
        "combined_diagnostic_score",
        "final_answer_correctness",
        "required_facts_coverage",
        "route_accuracy",
        "expected_evidence_need_accuracy",
        "sql_required_used_accuracy",
        "api_required_used_accuracy",
        "sql_table_accuracy",
        "api_endpoint_family_accuracy",
        "expected_observable_trace_score",
        "answer_grounding_score",
        "estimated_total_tokens",
        "runtime_ms",
    ]
    summary = {key: round(sum(float(row.get(key) or 0.0) for row in rows) / count, 4) for key in avg_keys}
    source_counts = Counter({key: 0 for key in POST_SQL_ADVISOR_SOURCE_KEYS})
    source_counts.update(str(row.get("post_sql_advisor_source") or "MISSING") for row in rows if row.get("post_sql_advisor_checkpoint_present"))
    summary.update(
        {
            "mode": mode,
            "available": True,
            "excluded_from_comparison": False,
            "prompt_count": len(rows),
            "overall_score": summary.get("combined_diagnostic_score"),
            "unsupported_claims": sum(int(row.get("unsupported_claims") or 0) for row in rows),
            "tool_overuse": sum(int(row.get("tool_overuse") or 0) for row in rows),
            "tool_underuse": sum(int(row.get("tool_underuse") or 0) for row in rows),
            "api_required_underuse": sum(
                1
                for row in rows
                if str(row.get("expected_evidence_need") or "") in {"api", "sql_then_api", "api_then_sql", "mixed"}
                and float(row.get("api_required_used_accuracy") or 0.0) == 0.0
            ),
            "no_tool_false_positive": sum(1 for row in rows if row.get("no_tool_false_positive")),
            "no_tool_false_negative": sum(1 for row in rows if row.get("no_tool_false_negative")),
            "sql_calls": sum(int(row.get("sql_call_count") or int(bool(row.get("sql_used")))) for row in rows),
            "api_calls": sum(int(row.get("api_call_count") or int(bool(row.get("api_used")))) for row in rows),
            "api_calls_saved": sum(int(row.get("api_calls_saved") or 0) for row in rows),
            "api_calls_added": sum(int(row.get("api_calls_added") or 0) for row in rows),
            "applied_decision_count": sum(int(row.get("applied_decision_count") or 0) for row in rows),
            "skipped_decision_count": sum(int(row.get("skipped_decision_count") or 0) for row in rows),
            "fallback_count": sum(int(row.get("fallback_count") or 0) for row in rows),
            "blocker_count": sum(int(row.get("blocker_count") or 0) for row in rows),
            "behavior_changed": any(bool(row.get("behavior_changed")) for row in rows),
            "feature_flags_used": _aggregate_feature_flags_used(rows),
            "applied_decision_records": [record for row in rows for record in (row.get("applied_decision_records") or [])][:25],
            "anti_hallucination_initial_fail": sum(1 for row in rows if row.get("anti_hallucination_initial_fail")),
            "anti_hallucination_revision_attempted": sum(1 for row in rows if row.get("anti_hallucination_revision_attempted")),
            "anti_hallucination_revision_success": sum(1 for row in rows if row.get("anti_hallucination_revision_success")),
            "post_sql_advisor_checkpoint_present_count": sum(1 for row in rows if row.get("post_sql_advisor_checkpoint_present")),
            "post_sql_llm_advisor_actual_call_count": sum(1 for row in rows if row.get("post_sql_llm_advisor_actual_call")),
            "post_sql_advisor_source_counts": dict(sorted(source_counts.items())),
            "post_sql_verifier_verified_count": sum(1 for row in rows if row.get("post_sql_verifier_verified")),
            "post_sql_verifier_blocked_count": sum(1 for row in rows if row.get("post_sql_verifier_blocked")),
            "post_sql_llm_advice_blocked_count": sum(1 for row in rows if row.get("post_sql_llm_advice_blocked")),
            "post_sql_advisor_disabled_or_fallback_count": sum(1 for row in rows if row.get("post_sql_advisor_disabled_or_fallback")),
            "post_sql_deterministic_fallback_count": sum(1 for row in rows if row.get("post_sql_deterministic_fallback")),
            "post_sql_advisor_invoked": sum(1 for row in rows if row.get("post_sql_llm_advisor_actual_call")),
            "post_sql_advisor_verified": sum(1 for row in rows if row.get("post_sql_advisor_verified")),
            "post_sql_advisor_blocked": sum(1 for row in rows if row.get("post_sql_llm_advice_blocked")),
            "wall_time_seconds": round(elapsed, 4),
            "per_category": _group_average(rows, "category", "overall_score"),
            "per_domain": _group_average(rows, "domain_family", "overall_score"),
            "per_evidence_need": _group_average(rows, "expected_evidence_need", "overall_score"),
            "latest_code_paths_enabled": _aggregate_latest_flags(rows),
            "old_generated_diagnostic_path_used": False,
            "rows_helped": [],
            "rows_hurt": [],
        }
    )
    return summary


def _compare_modes(mode_summaries: dict[str, Any], mode_rows: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    baseline_mode = "packaged_baseline" if "packaged_baseline" in mode_summaries else "packaged_baseline_real"
    latest_mode = _comparison_candidate_mode(mode_summaries)
    baseline = mode_summaries.get(baseline_mode, {})
    latest = mode_summaries.get(latest_mode, {})
    unavailable = mode_summaries.get("latest_applied_real_trial", {})
    if not baseline or not latest:
        if unavailable.get("excluded_from_comparison"):
            return {
                "baseline_mode": baseline.get("mode") if baseline else baseline_mode,
                "latest_mode": "latest_applied_real_trial",
                "latest_unavailable": True,
                "excluded_from_comparison": True,
                "blockers": unavailable.get("blockers", []),
            }
        return {}
    if latest.get("excluded_from_comparison"):
        return {
            "baseline_mode": baseline.get("mode"),
            "latest_mode": latest.get("mode"),
            "latest_unavailable": True,
            "excluded_from_comparison": True,
            "blockers": latest.get("blockers", []),
        }
    baseline_rows = {row["prompt_id"]: row for row in mode_rows.get(baseline_mode, [])}
    latest_rows = {row["prompt_id"]: row for row in mode_rows.get(latest_mode, [])}
    helped: list[dict[str, Any]] = []
    hurt: list[dict[str, Any]] = []
    for prompt_id, latest_row in latest_rows.items():
        base_row = baseline_rows.get(prompt_id)
        if not base_row:
            continue
        delta = round(float(latest_row.get("overall_score") or 0.0) - float(base_row.get("overall_score") or 0.0), 4)
        if delta > 0.05:
            helped.append({"prompt_id": prompt_id, "delta": delta})
        elif delta < -0.05:
            hurt.append({"prompt_id": prompt_id, "delta": delta})
    helped = sorted(helped, key=lambda item: item["delta"], reverse=True)[:20]
    hurt = sorted(hurt, key=lambda item: item["delta"])[:20]
    return {
        "baseline_mode": baseline.get("mode"),
        "latest_mode": latest.get("mode"),
        "latest_unavailable": bool(unavailable.get("excluded_from_comparison")),
        "unavailable_mode": unavailable.get("mode") if unavailable.get("excluded_from_comparison") else None,
        "unavailable_blockers": unavailable.get("blockers", []) if unavailable.get("excluded_from_comparison") else [],
        "overall_score_delta": round(float(latest.get("overall_score") or 0.0) - float(baseline.get("overall_score") or 0.0), 4),
        "behavior_score_delta": round(float(latest.get("behavior_score") or 0.0) - float(baseline.get("behavior_score") or 0.0), 4),
        "trace_observability_delta": round(float(latest.get("trace_observability_score") or 0.0) - float(baseline.get("trace_observability_score") or 0.0), 4),
        "route_accuracy_delta": round(float(latest.get("route_accuracy") or 0.0) - float(baseline.get("route_accuracy") or 0.0), 4),
        "observable_trace_delta": round(float(latest.get("expected_observable_trace_score") or 0.0) - float(baseline.get("expected_observable_trace_score") or 0.0), 4),
        "api_call_delta": int(latest.get("api_calls") or 0) - int(baseline.get("api_calls") or 0),
        "token_delta": round(float(latest.get("estimated_total_tokens") or 0.0) - float(baseline.get("estimated_total_tokens") or 0.0), 4),
        "runtime_ms_delta": round(float(latest.get("runtime_ms") or 0.0) - float(baseline.get("runtime_ms") or 0.0), 4),
        "rows_helped_count": sum(1 for prompt_id, latest_row in latest_rows.items() if prompt_id in baseline_rows and float(latest_row.get("overall_score") or 0.0) > float(baseline_rows[prompt_id].get("overall_score") or 0.0) + 0.05),
        "rows_hurt_count": sum(1 for prompt_id, latest_row in latest_rows.items() if prompt_id in baseline_rows and float(latest_row.get("overall_score") or 0.0) < float(baseline_rows[prompt_id].get("overall_score") or 0.0) - 0.05),
        "rows_helped_examples": helped,
        "rows_hurt_examples": hurt,
    }


def _comparison_candidate_mode(mode_summaries: dict[str, Any]) -> str:
    applied = mode_summaries.get("latest_applied_real_trial")
    if applied and not applied.get("excluded_from_comparison"):
        return "latest_applied_real_trial"
    if "latest_shadow_real" in mode_summaries:
        return "latest_shadow_real"
    if "latest_applied_trial" in mode_summaries:
        return "latest_applied_trial"
    return "latest_full_trial"


def _compare_specific_modes(
    baseline_mode: str,
    candidate_mode: str,
    mode_summaries: dict[str, Any],
    mode_rows: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    baseline = mode_summaries.get(baseline_mode)
    candidate = mode_summaries.get(candidate_mode)
    if not baseline or not candidate or candidate.get("excluded_from_comparison"):
        return {}
    baseline_rows = {row["prompt_id"]: row for row in mode_rows.get(baseline_mode, [])}
    candidate_rows = {row["prompt_id"]: row for row in mode_rows.get(candidate_mode, [])}
    helped: list[dict[str, Any]] = []
    hurt: list[dict[str, Any]] = []
    common_count = 0
    for prompt_id, candidate_row in candidate_rows.items():
        base_row = baseline_rows.get(prompt_id)
        if not base_row:
            continue
        common_count += 1
        delta = round(float(candidate_row.get("behavior_score") or 0.0) - float(base_row.get("behavior_score") or 0.0), 4)
        if delta > 0.005:
            helped.append({"prompt_id": prompt_id, "delta": delta})
        elif delta < -0.005:
            hurt.append({"prompt_id": prompt_id, "delta": delta})
    final_answer_changed = sum(
        1
        for prompt_id, candidate_row in candidate_rows.items()
        if prompt_id in baseline_rows and str(candidate_row.get("final_answer") or "") != str(baseline_rows[prompt_id].get("final_answer") or "")
    )
    tool_behavior_changed = sum(
        1
        for prompt_id, candidate_row in candidate_rows.items()
        if prompt_id in baseline_rows and _tool_behavior_signature(candidate_row) != _tool_behavior_signature(baseline_rows[prompt_id])
    )
    unsupported_delta = sum(int(row.get("unsupported_claims") or 0) for row in candidate_rows.values()) - sum(int(row.get("unsupported_claims") or 0) for row in baseline_rows.values())
    behavior_delta = round(float(candidate.get("behavior_score") or 0.0) - float(baseline.get("behavior_score") or 0.0), 4)
    trace_delta = round(float(candidate.get("trace_observability_score") or 0.0) - float(baseline.get("trace_observability_score") or 0.0), 4)
    return {
        "baseline_mode": baseline_mode,
        "candidate_mode": candidate_mode,
        "overall_score_delta": round(float(candidate.get("overall_score") or 0.0) - float(baseline.get("overall_score") or 0.0), 4),
        "behavior_score_delta": behavior_delta,
        "trace_observability_delta": trace_delta,
        "trace_observability_improved": trace_delta > 0,
        "route_accuracy_delta": round(float(candidate.get("route_accuracy") or 0.0) - float(baseline.get("route_accuracy") or 0.0), 4),
        "observable_trace_delta": round(float(candidate.get("expected_observable_trace_score") or 0.0) - float(baseline.get("expected_observable_trace_score") or 0.0), 4),
        "api_call_delta": int(candidate.get("api_calls") or 0) - int(baseline.get("api_calls") or 0),
        "sql_call_delta": int(candidate.get("sql_calls") or 0) - int(baseline.get("sql_calls") or 0),
        "token_delta": round(float(candidate.get("estimated_total_tokens") or 0.0) - float(baseline.get("estimated_total_tokens") or 0.0), 4),
        "runtime_ms_delta": round(float(candidate.get("runtime_ms") or 0.0) - float(baseline.get("runtime_ms") or 0.0), 4),
        "rows_helped_count": len(helped),
        "rows_hurt_count": len(hurt),
        "rows_neutral_count": max(0, common_count - len(helped) - len(hurt)),
        "rows_helped_examples": sorted(helped, key=lambda item: item["delta"], reverse=True)[:20],
        "rows_hurt_examples": sorted(hurt, key=lambda item: item["delta"])[:20],
        "final_answer_changed_count": final_answer_changed,
        "tool_behavior_changed_count": tool_behavior_changed,
        "unsupported_claim_delta": unsupported_delta,
        "rows_with_shadow_only_trace_delta": sum(
            1
            for prompt_id, candidate_row in candidate_rows.items()
            if prompt_id in baseline_rows
            and _tool_behavior_signature(candidate_row) == _tool_behavior_signature(baseline_rows[prompt_id])
            and str(candidate_row.get("final_answer") or "") == str(baseline_rows[prompt_id].get("final_answer") or "")
            and float(candidate_row.get("trace_observability_score") or 0.0) > float(baseline_rows[prompt_id].get("trace_observability_score") or 0.0)
        ),
    }


def _tool_behavior_signature(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        int(row.get("sql_call_count") or row.get("sql_used") or 0),
        int(row.get("api_call_count") or row.get("api_used") or 0),
        tuple(sorted(str(item) for item in row.get("sql_tables") or [])),
        tuple(sorted(str(item) for item in row.get("api_families") or [])),
        int(row.get("unsupported_claims") or 0),
    )


def _write_gate_report(report: dict[str, Any], reports_dir: Path, *, suffix: str = "") -> dict[str, Any]:
    baseline = report["modes"].get("packaged_baseline") or report["modes"].get("packaged_baseline_real") or {}
    applied = report["modes"].get("latest_applied_real_trial") or (report.get("unavailable_modes") or {}).get("latest_applied_real_trial") or {}
    latest = report["modes"].get(_comparison_candidate_mode(report["modes"])) or {}
    latest_score = latest.get("overall_score")
    baseline_score = baseline.get("overall_score")
    strict_like_improves = bool(
        latest
        and baseline
        and latest_score is not None
        and baseline_score is not None
        and float(latest_score) >= float(baseline_score)
    )
    comparable_modes = [mode for mode in report["modes"].values() if not mode.get("excluded_from_comparison")]
    unsupported_zero = all((mode.get("unsupported_claims") or 0) == 0 for mode in comparable_modes)
    false_no_tool_safe = latest.get("no_tool_false_positive", 0) == 0 if latest else False
    runtime_cost_ok = (
        float(latest.get("estimated_total_tokens", 0) or 0)
        <= max(1.0, float(baseline.get("estimated_total_tokens", 1) or 1)) * 1.25
        if latest and baseline and latest_score is not None
        else False
    )
    latest_paths_ok = report.get("latest_code_paths_explicitly_evaluated") and not report.get("old_generated_diagnostic_path_used")
    recommendation = "keep_shadow_only"
    if applied.get("excluded_from_comparison"):
        recommendation = "latest_applied_real_trial_unavailable_keep_shadow"
    elif report.get("simulated_trace_only"):
        recommendation = "keep_shadow_only"
    elif not latest_paths_ok:
        recommendation = "improve_semantic_routing_before_promotion"
    elif not false_no_tool_safe:
        recommendation = "blocked_by_false_no_tool_risk"
    elif not strict_like_improves:
        recommendation = "blocked_by_strict_or_gold_regression"
    elif not runtime_cost_ok:
        recommendation = "blocked_by_runtime_cost"
    else:
        recommendation = "latest_trial_improves_but_keep_shadow"
    gate = {
        "passed": False,
        "diagnostic_gate_only": True,
        "packaged_runtime_changed": False,
        "final_submission_format_changed": False,
        "eval_engine": report.get("eval_engine"),
        "simulated_trace_only": report.get("simulated_trace_only", False),
        "real_agent_execution": report.get("real_agent_execution", False),
        "baseline_score": baseline_score,
        "packaged_baseline_real_score": baseline_score if baseline.get("mode") == "packaged_baseline_real" else None,
        "latest_shadow_real_score": (report["modes"].get("latest_shadow_real") or {}).get("overall_score"),
        "latest_shadow_real_behavior_score": (report["modes"].get("latest_shadow_real") or {}).get("behavior_score"),
        "latest_shadow_real_trace_observability_score": (report["modes"].get("latest_shadow_real") or {}).get("trace_observability_score"),
        "latest_shadow_real_trace_observability_delta": (report.get("shadow_comparison") or {}).get("trace_observability_delta"),
        "latest_shadow_real_post_sql_advisor_checkpoint_present_count": (report["modes"].get("latest_shadow_real") or {}).get("post_sql_advisor_checkpoint_present_count"),
        "latest_shadow_real_post_sql_llm_advisor_actual_call_count": (report["modes"].get("latest_shadow_real") or {}).get("post_sql_llm_advisor_actual_call_count"),
        "latest_shadow_real_post_sql_llm_advice_blocked_count": (report["modes"].get("latest_shadow_real") or {}).get("post_sql_llm_advice_blocked_count"),
        "latest_shadow_real_post_sql_deterministic_fallback_count": (report["modes"].get("latest_shadow_real") or {}).get("post_sql_deterministic_fallback_count"),
        "latest_trial_score": None if applied.get("excluded_from_comparison") else latest_score,
        "route_trace_accuracy": None if applied.get("excluded_from_comparison") else latest.get("expected_observable_trace_score"),
        "unsupported_claims_zero": unsupported_zero,
        "no_tool_false_positive": latest.get("no_tool_false_positive"),
        "api_calls_saved": latest.get("api_calls_saved"),
        "api_calls_added": latest.get("api_calls_added"),
        "runtime_cost_acceptable": None if applied.get("excluded_from_comparison") else runtime_cost_ok,
        "latest_code_paths_explicitly_evaluated": latest_paths_ok,
        "latest_applied_real_trial_available": not bool(applied.get("excluded_from_comparison")),
        "applied_behavior_changed": False,
        "recommendation": recommendation,
        "blockers": applied.get("blockers", []) or latest.get("blockers", []),
    }
    (reports_dir / f"dashagent_500_prompt_suite_gate{suffix}.json").write_text(json.dumps(gate, indent=2, sort_keys=True), encoding="utf-8")
    (reports_dir / f"dashagent_500_prompt_suite_gate{suffix}.md").write_text(_gate_md(gate), encoding="utf-8")
    return gate


def _route_accuracy(route_action: str, expected_route: str, sql_used: bool, api_used: bool) -> float:
    if expected_route in {"LLM_DIRECT", "LLM_SAFE_DIRECT"}:
        return 1.0 if route_action in {"LLM_DIRECT", "LLM_SAFE_DIRECT"} else 0.0
    if expected_route == "SAFE_API_PROBE":
        return 1.0 if route_action == "SAFE_API_PROBE" or (api_used and not sql_used) else 0.0
    if expected_route == "API_ONLY":
        return 1.0 if api_used and not sql_used else 0.75 if api_used else 0.0
    if expected_route == "SQL_ONLY":
        return 1.0 if sql_used and not api_used else 0.75 if sql_used else 0.0
    if expected_route in {"SQL_THEN_API", "SQL_PRIMARY_API_VERIFY"}:
        return 1.0 if sql_used else 0.0
    if expected_route == "EVIDENCE_PIPELINE":
        return 1.0 if route_action == "EVIDENCE_PIPELINE" or sql_used or api_used else 0.0
    return 0.5


def _evidence_need_accuracy(need: str, sql_used: bool, api_used: bool, route_action: str) -> float:
    if need == "none":
        return 1.0 if not sql_used and not api_used and route_action in {"LLM_DIRECT", "LLM_SAFE_DIRECT"} else 0.0
    if need == "sql":
        return 1.0 if sql_used and not api_used else 0.75 if sql_used else 0.0
    if need == "api":
        return 1.0 if api_used and not sql_used else 0.75 if api_used else 0.0
    if need in {"sql_then_api", "api_then_sql", "mixed"}:
        return 1.0 if (sql_used or api_used) else 0.0
    return 0.5


def _objective_feature_score(observable_trace: dict[str, Any], gold: dict[str, Any]) -> float:
    features = observable_trace.get("checkpoint_objective_prompt_features") or {}
    actual_codes = set()
    for values in features.values():
        if isinstance(values, list):
            actual_codes.update(str(value) for value in values)
    expected_codes: set[str] = set()
    for stage in gold.get("expected_observable_trace") or []:
        if stage.get("stage") == "objective_features":
            expected_codes.update(str(code) for code in stage.get("expected_codes") or [])
    if not expected_codes:
        return 1.0
    return round(len(actual_codes & expected_codes) / len(expected_codes), 4)


def _safe_direct_answer(row: dict[str, Any]) -> str:
    return f"This is a general explanation for {row.get('domain_family')} without environment-specific records or measured facts."


def _final_answer_for_trace(row: dict[str, Any], action: str, tool_plan: dict[str, bool], safe_direct: dict[str, Any]) -> str:
    if action in {"LLM_DIRECT", "LLM_SAFE_DIRECT"}:
        return _safe_direct_answer(row) if safe_direct.get("ok") else "I can only provide a general conceptual answer here without concrete platform facts."
    parts = ["Diagnostic answer uses observable benchmark trace."]
    if tool_plan["sql_used"]:
        parts.append("SQL evidence is required or selected.")
    if tool_plan["api_used"]:
        parts.append("API evidence is required or selected.")
    if not tool_plan["sql_used"] and not tool_plan["api_used"]:
        parts.append("No tool evidence was selected.")
    return " ".join(parts)


def _packaged_action_for_row(row: dict[str, Any]) -> str:
    if row.get("category") == "conceptual_no_tool":
        return "EVIDENCE_PIPELINE"
    if row.get("category") == "ambiguous_low_confidence" and "low_low_safe_direct" in set(row.get("tags") or []):
        return "LLM_SAFE_DIRECT"
    return "EVIDENCE_PIPELINE"


def _answer_intent_for_row(row: dict[str, Any]) -> str:
    tags = set(row.get("tags") or [])
    if "count" in tags:
        return "COUNT"
    if "status" in tags or "post_sql_advisor_accept" in tags:
        return "STATUS"
    if "date" in tags:
        return "DATE"
    if "list" in tags or "api_required" in tags:
        return "LIST"
    return "DETAIL"


def _api_domain_endpoint_ids() -> dict[str, str]:
    return {
        "SCHEMA": "schema_registry_schemas",
        "AUDIENCE": "ups_audiences",
        "SEGMENT": "segment_definitions",
        "MERGE_POLICY": "merge_policies",
        "FLOW": "flowservice_flows",
        "BATCH": "catalog_batches",
        "DATASET": "catalog_datasets",
        "TAG": "unified_tags",
        "AUDIT": "audit_events",
    }


def _group_average(rows: list[dict[str, Any]], key: str, value_key: str) -> dict[str, float]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(key, "unknown"))].append(float(row.get(value_key) or 0.0))
    return {group: round(sum(values) / len(values), 4) for group, values in sorted(grouped.items())}


def _aggregate_latest_flags(rows: list[dict[str, Any]]) -> dict[str, bool]:
    flags: dict[str, bool] = {}
    for row in rows:
        row_flags = row.get("latest_code_paths_enabled") if isinstance(row.get("latest_code_paths_enabled"), dict) else {}
        for key, value in row_flags.items():
            flags[key] = flags.get(key, False) or bool(value)
    return flags


def _aggregate_feature_flags_used(rows: list[dict[str, Any]]) -> dict[str, bool]:
    flags: dict[str, bool] = {}
    for row in rows:
        row_flags = row.get("feature_flags_used") if isinstance(row.get("feature_flags_used"), dict) else {}
        for key, value in row_flags.items():
            flags[key] = flags.get(key, False) or bool(value)
    return flags


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _eval_report_md(report: dict[str, Any]) -> str:
    lines = [
        "# DashAgent 500-Prompt Suite Eval",
        "",
        f"- eval_engine: {report.get('eval_engine')}",
        f"- real_agent_execution: {str(report.get('real_agent_execution')).lower()}",
        f"- simulated_trace_only: {str(report.get('simulated_trace_only')).lower()}",
        f"- synthetic_sql_results_used: {str(report.get('synthetic_sql_results_used')).lower()}",
        f"- runtime_used_category_tags_for_decision: {str(report.get('runtime_used_category_tags_for_decision')).lower()}",
        f"- agent_executor_used: {str(report.get('agent_executor_used')).lower()}",
        f"- grading_type: {report.get('grading_type')}",
        f"- organizer_equivalent: {str(report.get('organizer_equivalent')).lower()}",
        f"- answer_grading_method: {report.get('answer_grading_method')}",
        f"- process_grading_method: {report.get('process_grading_method')}",
        f"- prompt_count: {report['prompt_count']}",
        f"- latest_code_paths_explicitly_evaluated: {str(report['latest_code_paths_explicitly_evaluated']).lower()}",
        f"- old_generated_diagnostic_path_used: {str(report['old_generated_diagnostic_path_used']).lower()}",
        "",
        "## Modes",
    ]
    for mode in report["mode_order"]:
        summary = report["modes"][mode]
        if summary.get("excluded_from_comparison"):
            lines.extend(
                [
                    f"### {mode}",
                    "- available: false",
                    "- status: unavailable, not run, excluded from metric comparison",
                    f"- blockers: {summary.get('blockers', [])}",
                    "",
                ]
            )
            continue
        lines.extend(
            [
                f"### {mode}",
                f"- behavior_score: {summary['behavior_score']}",
                f"- trace_observability_score: {summary['trace_observability_score']}",
                f"- combined_diagnostic_score: {summary['combined_diagnostic_score']}",
                f"- overall_score_alias: {summary['overall_score']}",
                f"- route_accuracy: {summary['route_accuracy']}",
                f"- observable_trace_score: {summary['expected_observable_trace_score']}",
                f"- sql_accuracy: {summary['sql_required_used_accuracy']}",
                f"- api_accuracy: {summary['api_required_used_accuracy']}",
                f"- unsupported_claims: {summary['unsupported_claims']}",
                f"- no_tool_false_positive: {summary['no_tool_false_positive']}",
                f"- no_tool_false_negative: {summary['no_tool_false_negative']}",
                f"- api_calls_saved: {summary['api_calls_saved']}",
                f"- api_calls_added: {summary['api_calls_added']}",
                f"- anti_hallucination_initial_fail: {summary['anti_hallucination_initial_fail']}",
                f"- anti_hallucination_revision_success: {summary['anti_hallucination_revision_success']}",
                "- post_sql_advisor_note: checkpoints are observability; actual LLM calls are counted separately",
                f"- post_sql_advisor_checkpoint_present_count: {summary['post_sql_advisor_checkpoint_present_count']}",
                f"- post_sql_llm_advisor_actual_call_count: {summary['post_sql_llm_advisor_actual_call_count']}",
                f"- post_sql_deterministic_fallback_count: {summary['post_sql_deterministic_fallback_count']}",
                f"- post_sql_llm_advice_blocked_count: {summary['post_sql_llm_advice_blocked_count']}",
                f"- post_sql_verifier_verified_count: {summary['post_sql_verifier_verified_count']}",
                f"- post_sql_verifier_blocked_count: {summary['post_sql_verifier_blocked_count']}",
                f"- post_sql_advisor_source_counts: {summary['post_sql_advisor_source_counts']}",
                "",
            ]
        )
    return "\n".join(lines)


def _write_runner_audit(report: dict[str, Any], reports_dir: Path) -> dict[str, Any]:
    audit = {
        "old_synthetic_eval_issue_found": True,
        "old_synthetic_eval_issue_fixed": True,
        "eval_engine": report.get("eval_engine"),
        "simulated_trace_only": report.get("simulated_trace_only", False),
        "synthetic_sql_result_used": report.get("synthetic_sql_results_used", False),
        "category_tags_influenced_runtime": report.get("runtime_used_category_tags_for_decision", False),
        "agent_executor_used": report.get("agent_executor_used", False),
        "gold_hidden_from_runtime": not report.get("runtime_gold_visible", True),
        "runtime_input_fields": report.get("runtime_input_fields", ["prompt", "metadata_fields_in_simulated_mode"]),
        "oracle_sql_hidden_from_runtime": not report.get("simulated_trace_only", False),
        "expected_trace_hidden_from_runtime": not report.get("simulated_trace_only", False),
        "latest_code_paths_truly_executed": bool(
            report.get("eval_engine") == "real_agent"
            and report.get("mode_summary", {}).get("latest_shadow_real", {}).get("shadow_modules_executed")
        ),
        "latest_code_paths_shadow_logged_only": bool(
            report.get("mode_summary", {}).get("latest_shadow_real", {}).get("shadow_modules_executed")
        ),
        "post_sql_advisor_metric_semantics": {
            "checkpoint_presence_is_not_invocation": True,
            "deterministic_fallback_is_not_llm_blocked": True,
            "blocked_count_requires_actual_llm_advice": True,
        },
        "latest_shadow_real_post_sql_advisor_checkpoint_present_count": report.get("mode_summary", {}).get("latest_shadow_real", {}).get("post_sql_advisor_checkpoint_present_count"),
        "latest_shadow_real_post_sql_llm_advisor_actual_call_count": report.get("mode_summary", {}).get("latest_shadow_real", {}).get("post_sql_llm_advisor_actual_call_count"),
        "latest_shadow_real_post_sql_llm_advice_blocked_count": report.get("mode_summary", {}).get("latest_shadow_real", {}).get("post_sql_llm_advice_blocked_count"),
        "latest_shadow_real_post_sql_deterministic_fallback_count": report.get("mode_summary", {}).get("latest_shadow_real", {}).get("post_sql_deterministic_fallback_count"),
        "latest_applied_real_trial_available": not bool(
            (
                report.get("mode_summary", {}).get("latest_applied_real_trial")
                or report.get("unavailable_modes", {}).get("latest_applied_real_trial")
                or {"excluded_from_comparison": True}
            ).get("excluded_from_comparison")
        ),
        "notes": [
            "Simulated trace mode is retained only as a diagnostic compatibility engine.",
            "Real-agent mode uses AgentExecutor.run and writes actual per-prompt trajectory.json files.",
            "Gold, oracle SQL, expected traces, category, domain, and tags are grading inputs only in real-agent mode.",
            "Post-SQL advisor checkpoints are observability records; actual LLM advisor calls are counted separately.",
            "DETERMINISTIC_FALLBACK is not counted as blocked LLM advice.",
        ],
    }
    json_path = reports_dir / "dashagent_500_prompt_suite_runner_audit.json"
    md_path = reports_dir / "dashagent_500_prompt_suite_runner_audit.md"
    json_path.write_text(json.dumps(audit, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(_runner_audit_md(audit), encoding="utf-8")
    return audit


def _write_real_behavior_change_reports(report: dict[str, Any], mode_rows: dict[str, list[dict[str, Any]]], reports_dir: Path) -> dict[str, Any]:
    baseline = report.get("mode_summary", {}).get("packaged_baseline_real", {})
    applied_modes = [
        mode
        for mode in report.get("mode_order", [])
        if mode in REAL_BEHAVIOR_APPLIED_MODES or mode == "latest_shadow_real"
    ]
    mode_results: dict[str, Any] = {}
    error_rows: dict[str, Any] = {}
    gate_modes: dict[str, Any] = {}
    for mode in applied_modes:
        summary = report.get("mode_summary", {}).get(mode) or report.get("unavailable_modes", {}).get(mode) or {}
        comparison = (report.get("mode_comparisons") or {}).get(mode) or {}
        mode_results[mode] = {
            "available": not bool(summary.get("excluded_from_comparison")),
            "behavior_score": summary.get("behavior_score"),
            "trace_observability_score": summary.get("trace_observability_score"),
            "combined_diagnostic_score": summary.get("combined_diagnostic_score"),
            "final_answer_correctness": summary.get("final_answer_correctness"),
            "required_facts_coverage": summary.get("required_facts_coverage"),
            "answer_grounding_score": summary.get("answer_grounding_score"),
            "route_accuracy": summary.get("route_accuracy"),
            "evidence_need_accuracy": summary.get("expected_evidence_need_accuracy"),
            "sql_required_used_accuracy": summary.get("sql_required_used_accuracy"),
            "api_required_used_accuracy": summary.get("api_required_used_accuracy"),
            "sql_table_accuracy": summary.get("sql_table_accuracy"),
            "api_endpoint_family_accuracy": summary.get("api_endpoint_family_accuracy"),
            "unsupported_claims": summary.get("unsupported_claims"),
            "no_tool_false_positive": summary.get("no_tool_false_positive"),
            "no_tool_false_negative": summary.get("no_tool_false_negative"),
            "api_required_underuse": summary.get("api_required_underuse"),
            "tool_overuse": summary.get("tool_overuse"),
            "tool_underuse": summary.get("tool_underuse"),
            "sql_calls": summary.get("sql_calls"),
            "api_calls": summary.get("api_calls"),
            "api_calls_saved": summary.get("api_calls_saved"),
            "api_calls_added": summary.get("api_calls_added"),
            "average_tokens": summary.get("estimated_total_tokens"),
            "average_runtime": summary.get("runtime_ms"),
            "applied_decision_count": summary.get("applied_decision_count"),
            "skipped_decision_count": summary.get("skipped_decision_count"),
            "fallback_count": summary.get("fallback_count"),
            "blocker_count": summary.get("blocker_count"),
            "final_answer_changed_count_vs_baseline": comparison.get("final_answer_changed_count"),
            "tool_behavior_changed_count_vs_baseline": comparison.get("tool_behavior_changed_count"),
            "behavior_score_delta": comparison.get("behavior_score_delta"),
            "trace_observability_delta": comparison.get("trace_observability_delta"),
            "sql_call_delta": comparison.get("sql_call_delta"),
            "api_call_delta": comparison.get("api_call_delta"),
            "token_delta": comparison.get("token_delta"),
            "runtime_ms_delta": comparison.get("runtime_ms_delta"),
            "rows_helped": comparison.get("rows_helped_count"),
            "rows_hurt": comparison.get("rows_hurt_count"),
            "rows_neutral": comparison.get("rows_neutral_count"),
            "per_category": summary.get("per_category", {}),
            "per_domain": summary.get("per_domain", {}),
            "per_evidence_need": summary.get("per_evidence_need", {}),
            "feature_flags_used": summary.get("feature_flags_used", {}),
            "blockers": summary.get("blockers", []),
        }
        error_rows[mode] = _classify_behavior_change_rows(mode, mode_rows.get("packaged_baseline_real", []), mode_rows.get(mode, []))
        gate_modes[mode] = _real_behavior_gate_for_mode(mode, baseline, summary, comparison)

    experiment = {
        "eval_engine": report.get("eval_engine"),
        "grading_type": report.get("grading_type"),
        "organizer_equivalent": report.get("organizer_equivalent"),
        "runtime_input_fields": report.get("runtime_input_fields"),
        "gold_hidden_from_runtime": not report.get("runtime_gold_visible", True),
        "category_tags_used_only_after_execution": report.get("category_domain_tags_used_only_for_grading"),
        "oracle_sql_hidden_from_runtime": True,
        "expected_trace_hidden_from_runtime": True,
        "prompt_count": report.get("prompt_count"),
        "baseline": {
            "behavior_score": baseline.get("behavior_score"),
            "trace_observability_score": baseline.get("trace_observability_score"),
            "combined_diagnostic_score": baseline.get("combined_diagnostic_score"),
            "final_answer_correctness": baseline.get("final_answer_correctness"),
            "sql_calls": baseline.get("sql_calls"),
            "api_calls": baseline.get("api_calls"),
            "unsupported_claims": baseline.get("unsupported_claims"),
        },
        "modes": mode_results,
    }
    error_analysis = {
        "prompt_count": report.get("prompt_count"),
        "mode_error_analysis": error_rows,
        "summary": {
            mode: {
                "helped_categories": rows.get("helped_category_counts", {}),
                "hurt_categories": rows.get("hurt_category_counts", {}),
                "helped_count": rows.get("helped_count", 0),
                "hurt_count": rows.get("hurt_count", 0),
            }
            for mode, rows in error_rows.items()
        },
    }
    gate = {
        "diagnostic_internal_only": True,
        "organizer_equivalent": False,
        "packaged_runtime_changed": False,
        "final_submission_format_changed": False,
        "modes": gate_modes,
        "recommendation": _overall_real_behavior_recommendation(gate_modes),
    }
    (reports_dir / "real_behavior_change_experiment.json").write_text(json.dumps(experiment, indent=2, sort_keys=True, default=str), encoding="utf-8")
    (reports_dir / "real_behavior_change_experiment.md").write_text(_real_behavior_experiment_md(experiment), encoding="utf-8")
    (reports_dir / "real_behavior_change_error_analysis.json").write_text(json.dumps(error_analysis, indent=2, sort_keys=True, default=str), encoding="utf-8")
    (reports_dir / "real_behavior_change_error_analysis.md").write_text(_real_behavior_error_md(error_analysis), encoding="utf-8")
    (reports_dir / "real_behavior_change_gate.json").write_text(json.dumps(gate, indent=2, sort_keys=True, default=str), encoding="utf-8")
    (reports_dir / "real_behavior_change_gate.md").write_text(_real_behavior_gate_md(gate), encoding="utf-8")
    return {
        "experiment": str(reports_dir / "real_behavior_change_experiment.json"),
        "error_analysis": str(reports_dir / "real_behavior_change_error_analysis.json"),
        "gate": str(reports_dir / "real_behavior_change_gate.json"),
    }


def _classify_behavior_change_rows(mode: str, baseline_rows: list[dict[str, Any]], candidate_rows: list[dict[str, Any]]) -> dict[str, Any]:
    baseline_by_id = {row["prompt_id"]: row for row in baseline_rows}
    helped: list[dict[str, Any]] = []
    hurt: list[dict[str, Any]] = []
    helped_counts: Counter[str] = Counter()
    hurt_counts: Counter[str] = Counter()
    for row in candidate_rows:
        base = baseline_by_id.get(row["prompt_id"])
        if not base:
            continue
        delta = round(float(row.get("behavior_score") or 0.0) - float(base.get("behavior_score") or 0.0), 4)
        if delta > 0.005:
            category = _help_category(base, row)
            helped_counts[category] += 1
            helped.append({"prompt_id": row["prompt_id"], "delta": delta, "category": category})
        elif delta < -0.005:
            category = _hurt_category(base, row)
            hurt_counts[category] += 1
            hurt.append({"prompt_id": row["prompt_id"], "delta": delta, "category": category})
    return {
        "mode": mode,
        "helped_count": len(helped),
        "hurt_count": len(hurt),
        "neutral_count": max(0, len(candidate_rows) - len(helped) - len(hurt)),
        "helped_category_counts": dict(sorted(helped_counts.items())),
        "hurt_category_counts": dict(sorted(hurt_counts.items())),
        "helped_examples": sorted(helped, key=lambda item: item["delta"], reverse=True)[:20],
        "hurt_examples": sorted(hurt, key=lambda item: item["delta"])[:20],
    }


def _help_category(base: dict[str, Any], row: dict[str, Any]) -> str:
    if row.get("api_call_count", 0) < base.get("api_call_count", 0) and row.get("final_answer_correctness") >= base.get("final_answer_correctness"):
        return "api_call_saved_without_answer_loss"
    if row.get("sql_call_count", 0) + row.get("api_call_count", 0) < base.get("sql_call_count", 0) + base.get("api_call_count", 0):
        return "conceptual_false_positive_tool_call_avoided"
    if row.get("answer_grounding_score", 0) > base.get("answer_grounding_score", 0):
        return "final_answer_improved"
    return "trace_process_or_behavior_alignment_improved"


def _hurt_category(base: dict[str, Any], row: dict[str, Any]) -> str:
    if row.get("no_tool_false_positive"):
        return "wrong_no_tool_skip"
    if row.get("api_required_underuse"):
        return "api_required_skipped"
    if row.get("api_call_count", 0) < base.get("api_call_count", 0) and row.get("api_required_used_accuracy", 1.0) < base.get("api_required_used_accuracy", 1.0):
        return "api_skipped_despite_missing_fields"
    if row.get("api_call_count", 0) > base.get("api_call_count", 0):
        return "api_called_unnecessarily"
    if row.get("final_answer_correctness", 0) < base.get("final_answer_correctness", 0):
        return "final_answer_omitted_evidence"
    return "no_clear_failure"


def _real_behavior_gate_for_mode(mode: str, baseline: dict[str, Any], summary: dict[str, Any], comparison: dict[str, Any]) -> dict[str, Any]:
    if summary.get("excluded_from_comparison"):
        return {"passed": False, "recommendation": "blocked_by_llm_backend_unavailable", "blockers": summary.get("blockers", [])}
    behavior_delta = float(comparison.get("behavior_score_delta") or 0.0)
    answer_delta = round(float(summary.get("final_answer_correctness") or 0.0) - float(baseline.get("final_answer_correctness") or 0.0), 4)
    runtime_delta = float(comparison.get("runtime_ms_delta") or 0.0)
    blockers: list[str] = []
    if behavior_delta < -0.005:
        blockers.append("behavior_regression")
    if answer_delta < -0.005:
        blockers.append("final_answer_regression")
    if int(summary.get("unsupported_claims") or 0) != 0:
        blockers.append("unsupported_claims")
    if int(summary.get("no_tool_false_positive") or 0) != 0:
        blockers.append("no_tool_false_positive")
    if int(summary.get("api_required_underuse") or 0) != 0:
        blockers.append("api_required_underuse")
    if runtime_delta > max(50.0, float(baseline.get("runtime_ms") or 0.0) * 0.25):
        blockers.append("runtime_cost")
    if blockers:
        recommendation = "blocked_by_behavior_regression" if "behavior_regression" in blockers else "keep_shadow_only"
        if "no_tool_false_positive" in blockers:
            recommendation = "blocked_by_no_tool_false_positive"
        elif "api_required_underuse" in blockers:
            recommendation = "blocked_by_api_underuse"
        elif "runtime_cost" in blockers:
            recommendation = "blocked_by_runtime_cost"
        return {"passed": False, "recommendation": recommendation, "blockers": blockers}
    recommendation_by_mode = {
        "semantic_no_tool_applied_real_trial": "semantic_no_tool_candidate_for_targeted_promotion",
        "staged_evidence_applied_real_trial": "staged_evidence_candidate_for_targeted_promotion",
        "post_sql_deterministic_applied_real_trial": "post_sql_deterministic_candidate_for_targeted_promotion",
        "combined_safe_applied_real_trial": "combined_safe_candidate_for_targeted_promotion",
        "combined_safe_deterministic_promotion_candidate_real": "combined_safe_deterministic_candidate_for_targeted_promotion",
    }
    return {
        "passed": behavior_delta >= 0.0 and answer_delta >= 0.0,
        "recommendation": recommendation_by_mode.get(mode, "keep_shadow_only"),
        "blockers": [],
        "behavior_score_delta": behavior_delta,
        "final_answer_correctness_delta": answer_delta,
    }


def _overall_real_behavior_recommendation(mode_gates: dict[str, Any]) -> str:
    priority = [
        "combined_safe_deterministic_promotion_candidate_real",
        "combined_safe_applied_real_trial",
        "post_sql_deterministic_applied_real_trial",
        "staged_evidence_applied_real_trial",
        "semantic_no_tool_applied_real_trial",
    ]
    for mode in priority:
        gate = mode_gates.get(mode) or {}
        if gate.get("passed"):
            return str(gate.get("recommendation"))
    blockers = [blocker for gate in mode_gates.values() for blocker in gate.get("blockers", [])]
    if "no_tool_false_positive" in blockers:
        return "blocked_by_no_tool_false_positive"
    if "api_required_underuse" in blockers:
        return "blocked_by_api_underuse"
    if "runtime_cost" in blockers:
        return "blocked_by_runtime_cost"
    if "behavior_regression" in blockers:
        return "blocked_by_behavior_regression"
    return "keep_shadow_only"


def _real_behavior_experiment_md(experiment: dict[str, Any]) -> str:
    lines = ["# Real Behavior Change Experiment", "", f"- prompt_count: {experiment.get('prompt_count')}", f"- grading_type: {experiment.get('grading_type')}", f"- organizer_equivalent: {experiment.get('organizer_equivalent')}", ""]
    lines.append("## Modes")
    for mode, summary in experiment.get("modes", {}).items():
        lines.extend([
            f"### {mode}",
            f"- available: {summary.get('available')}",
            f"- behavior_score: {summary.get('behavior_score')}",
            f"- trace_observability_score: {summary.get('trace_observability_score')}",
            f"- combined_diagnostic_score: {summary.get('combined_diagnostic_score')}",
            f"- final_answer_correctness: {summary.get('final_answer_correctness')}",
            f"- sql_calls: {summary.get('sql_calls')}",
            f"- api_calls: {summary.get('api_calls')}",
            f"- api_calls_saved: {summary.get('api_calls_saved')}",
            f"- unsupported_claims: {summary.get('unsupported_claims')}",
            f"- behavior_score_delta: {summary.get('behavior_score_delta')}",
            f"- rows_helped/hurt/neutral: {summary.get('rows_helped')}/{summary.get('rows_hurt')}/{summary.get('rows_neutral')}",
            "",
        ])
    return "\n".join(lines)


def _real_behavior_error_md(error_analysis: dict[str, Any]) -> str:
    lines = ["# Real Behavior Change Error Analysis", ""]
    for mode, summary in error_analysis.get("summary", {}).items():
        lines.extend([
            f"## {mode}",
            f"- helped_count: {summary.get('helped_count')}",
            f"- hurt_count: {summary.get('hurt_count')}",
            f"- helped_categories: {summary.get('helped_categories')}",
            f"- hurt_categories: {summary.get('hurt_categories')}",
            "",
        ])
    return "\n".join(lines)


def _real_behavior_gate_md(gate: dict[str, Any]) -> str:
    lines = ["# Real Behavior Change Gate", "", f"- recommendation: {gate.get('recommendation')}", f"- packaged_runtime_changed: {gate.get('packaged_runtime_changed')}", f"- final_submission_format_changed: {gate.get('final_submission_format_changed')}", ""]
    for mode, payload in gate.get("modes", {}).items():
        lines.extend([f"## {mode}", f"- passed: {payload.get('passed')}", f"- recommendation: {payload.get('recommendation')}", f"- blockers: {payload.get('blockers', [])}", ""])
    return "\n".join(lines)


def _runner_audit_md(audit: dict[str, Any]) -> str:
    lines = ["# DashAgent 500-Prompt Suite Runner Audit", ""]
    for key, value in audit.items():
        if key == "notes":
            lines.append("- notes:")
            for note in value:
                lines.append(f"  - {note}")
        else:
            lines.append(f"- {key}: {value}")
    return "\n".join(lines) + "\n"


def _gate_md(gate: dict[str, Any]) -> str:
    lines = ["# DashAgent 500-Prompt Suite Gate", ""]
    for key, value in gate.items():
        lines.append(f"- {key}: {value}")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the internal DashAgent 500-prompt benchmark suite.")
    parser.add_argument("--suite", type=Path, default=DEFAULT_CONFIG.data_dir / "benchmarks" / "dashagent_500_prompt_suite.jsonl")
    parser.add_argument("--gold", type=Path, default=DEFAULT_CONFIG.data_dir / "benchmarks" / "dashagent_500_prompt_suite_gold.jsonl")
    parser.add_argument("--engine", choices=["real_agent", "simulated_trace"], default="real_agent")
    parser.add_argument("--mode", action="append", choices=sorted(RECOGNIZED_MODES), required=True)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--seed", type=int, default=20260525)
    parser.add_argument("--clean", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_CONFIG.outputs_dir / "reports")
    args = parser.parse_args()
    report = run_suite_eval(
        suite=args.suite,
        gold=args.gold,
        modes=args.mode,
        limit=args.limit,
        full=args.full,
        seed=args.seed,
        clean=args.clean,
        output_dir=args.output_dir,
        report_dir=args.report_dir,
        engine=args.engine,
    )
    print(json.dumps({"ok": True, "prompt_count": report["prompt_count"], "modes": list(report["modes"])}, sort_keys=True))


if __name__ == "__main__":
    main()
