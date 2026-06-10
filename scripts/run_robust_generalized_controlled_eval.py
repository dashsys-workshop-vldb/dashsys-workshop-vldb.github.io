#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import (
    DEFAULT_CONFIG,
    ROBUST_ABLATION_STRATEGIES,
    ROBUST_GENERALIZED_HARNESS_CANDIDATE,
    robust_generalized_candidate_config,
)
from dashagent.eval_harness import config_for_applied_trial_strategy, extract_api_calls
from dashagent.executor import AgentExecutor
from dashagent.planner import ALL_STRATEGIES, PACKAGED_DEFAULT_STRATEGY, execution_base_strategy


REPORTS_DIR = DEFAULT_CONFIG.outputs_dir / "reports"
FOCUSED_OUTPUT_DIR = DEFAULT_CONFIG.outputs_dir / "robust_generalized_focused_stress"

STRICT_STRATEGIES = [
    "SQL_FIRST_API_VERIFY",
    ROBUST_GENERALIZED_HARNESS_CANDIDATE,
    *ROBUST_ABLATION_STRATEGIES,
]

INTERNAL_500_MODES = [
    "packaged_baseline_real",
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
]

COMPONENTS_BY_STRATEGY = {
    "ROBUST_ABLATION_NO_SEMANTIC_ROUTING": ["staged_evidence", "post_sql_api_policy", "answer_grounding", "final_answer_verifier"],
    "ROBUST_ABLATION_SEMANTIC_ROUTING_ONLY": ["semantic_parse", "semantic_route_decision", "anti_hallucination_gate", "semantic_consistency_verifier", "safe_api_probe"],
    "ROBUST_ABLATION_STAGED_EVIDENCE_ONLY": ["staged_evidence", "post_sql_api_policy", "api_preservation_guard"],
    "ROBUST_ABLATION_ANSWER_GROUNDING_ONLY": ["answer_slot_renderer", "llm_answer_generator", "final_answer_verifier"],
    "ROBUST_ABLATION_LLM_ANSWER_NO_VERIFIER": ["llm_answer_generator"],
    "ROBUST_ABLATION_LLM_ANSWER_WITH_VERIFIER": ["llm_answer_generator", "final_answer_verifier", "rewrite_fallback"],
    "ROBUST_ABLATION_SEMANTIC_ROLE_PARSE_ONLY": ["semantic_parse", "semantic_consistency_verifier"],
    "ROBUST_ABLATION_NO_LLM_COMPONENTS": ["objective_features", "staged_evidence", "post_sql_api_policy", "answer_slot_renderer"],
    "ROBUST_ABLATION_FULL_CANDIDATE_NO_LLM_ANSWER": [
        "semantic_parse",
        "semantic_route_decision",
        "anti_hallucination_gate",
        "semantic_consistency_verifier",
        "safe_api_probe",
        "staged_evidence",
        "post_sql_api_policy",
        "answer_slot_renderer",
    ],
    "ROBUST_ABLATION_FULL_CANDIDATE_NO_SAFE_API_PROBE": [
        "semantic_parse",
        "semantic_route_decision",
        "anti_hallucination_gate",
        "semantic_consistency_verifier",
        "staged_evidence",
        "post_sql_api_policy",
        "llm_answer_generator",
        "final_answer_verifier",
    ],
    "ROBUST_ABLATION_FULL_CANDIDATE_NO_STAGED_POLICY": [
        "semantic_parse",
        "semantic_route_decision",
        "anti_hallucination_gate",
        "semantic_consistency_verifier",
        "safe_api_probe",
        "llm_answer_generator",
        "final_answer_verifier",
    ],
    "ROBUST_ABLATION_FULL_CANDIDATE_NO_SEMANTIC_PARSE": [
        "objective_features",
        "semantic_route_decision",
        "safe_api_probe",
        "staged_evidence",
        "post_sql_api_policy",
        "llm_answer_generator",
        "final_answer_verifier",
    ],
}

FOCUSED_CASES = [
    {
        "suite": "no_tool_semantic_decoy",
        "query_id": "stress_no_tool_001",
        "prompt": "List three reasons why schemas matter.",
        "expected_no_tool": True,
        "expected_evidence": False,
        "api_required": False,
    },
    {
        "suite": "no_tool_semantic_decoy",
        "query_id": "stress_no_tool_002",
        "prompt": "What does 'inactive journey' mean?",
        "expected_no_tool": True,
        "expected_evidence": False,
        "api_required": False,
    },
    {
        "suite": "no_tool_semantic_decoy",
        "query_id": "stress_no_tool_003",
        "prompt": "Explain why the word list appears in API docs.",
        "expected_no_tool": True,
        "expected_evidence": False,
        "api_required": False,
    },
    {
        "suite": "no_tool_semantic_decoy",
        "query_id": "stress_no_tool_004",
        "prompt": "Give examples of status fields; do not query the dataset.",
        "expected_no_tool": True,
        "expected_evidence": False,
        "api_required": False,
    },
    {
        "suite": "no_tool_semantic_decoy",
        "query_id": "stress_no_tool_005",
        "prompt": "In the phrase 'list schemas', what does list mean?",
        "expected_no_tool": True,
        "expected_evidence": False,
        "api_required": False,
    },
    {
        "suite": "data_retrieval",
        "query_id": "stress_data_001",
        "prompt": "List current schemas in the sandbox.",
        "expected_no_tool": False,
        "expected_evidence": True,
        "api_required": True,
    },
    {
        "suite": "data_retrieval",
        "query_id": "stress_data_002",
        "prompt": "Show inactive journeys.",
        "expected_no_tool": False,
        "expected_evidence": True,
        "api_required": False,
    },
    {
        "suite": "data_retrieval",
        "query_id": "stress_data_003",
        "prompt": "Count datasets.",
        "expected_no_tool": False,
        "expected_evidence": True,
        "api_required": False,
    },
    {
        "suite": "data_retrieval",
        "query_id": "stress_data_004",
        "prompt": "Show failed flow runs.",
        "expected_no_tool": False,
        "expected_evidence": True,
        "api_required": True,
    },
    {
        "suite": "live_api_required",
        "query_id": "stress_api_001",
        "prompt": "List current schema registry schemas.",
        "expected_no_tool": False,
        "expected_evidence": True,
        "api_required": True,
    },
    {
        "suite": "live_api_required",
        "query_id": "stress_api_002",
        "prompt": "Show merge policies in the platform.",
        "expected_no_tool": False,
        "expected_evidence": True,
        "api_required": True,
    },
    {
        "suite": "live_api_required",
        "query_id": "stress_api_003",
        "prompt": "List tags.",
        "expected_no_tool": False,
        "expected_evidence": True,
        "api_required": True,
    },
    {
        "suite": "live_api_required",
        "query_id": "stress_api_004",
        "prompt": "Show audit events.",
        "expected_no_tool": False,
        "expected_evidence": True,
        "api_required": True,
    },
    {
        "suite": "live_api_required",
        "query_id": "stress_api_005",
        "prompt": "Show flowservice runs.",
        "expected_no_tool": False,
        "expected_evidence": True,
        "api_required": True,
    },
    {
        "suite": "answer_grounding",
        "query_id": "stress_answer_001",
        "prompt": "How many datasets are in the local snapshot?",
        "expected_no_tool": False,
        "expected_evidence": True,
        "api_required": False,
    },
    {
        "suite": "answer_grounding",
        "query_id": "stress_answer_002",
        "prompt": "List campaign names and statuses.",
        "expected_no_tool": False,
        "expected_evidence": True,
        "api_required": False,
    },
    {
        "suite": "answer_grounding",
        "query_id": "stress_answer_003",
        "prompt": "When was the Journey dataset updated?",
        "expected_no_tool": False,
        "expected_evidence": True,
        "api_required": False,
    },
    {
        "suite": "answer_grounding",
        "query_id": "stress_answer_004",
        "prompt": "Show campaign records.",
        "expected_no_tool": False,
        "expected_evidence": True,
        "api_required": False,
    },
    {
        "suite": "answer_grounding",
        "query_id": "stress_answer_005",
        "prompt": "Which dataset is associated with journeys?",
        "expected_no_tool": False,
        "expected_evidence": True,
        "api_required": False,
    },
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run controlled evals for ROBUST_GENERALIZED_HARNESS_CANDIDATE.")
    parser.add_argument("--skip-organizer", action="store_true")
    parser.add_argument("--skip-internal-500", action="store_true")
    parser.add_argument("--skip-focused", action="store_true")
    parser.add_argument("--skip-validation", action="store_true")
    parser.add_argument("--internal-limit", type=int, help="Diagnostic override for quicker local runs.")
    args = parser.parse_args()

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    preflight = write_preflight()
    organizer = None if args.skip_organizer else run_organizer35()
    internal500 = None if args.skip_internal_500 else run_internal500(limit=args.internal_limit)
    focused = None if args.skip_focused else run_focused_stress()
    answer_verifier = write_answer_verifier_report(organizer, internal500, focused)
    contribution = write_component_contribution_report(organizer, internal500, focused)
    provenance = run_provenance_audits()
    validation = None if args.skip_validation else run_validation_suite()
    summary = write_controlled_summary(
        preflight=preflight,
        organizer=organizer,
        internal500=internal500,
        focused=focused,
        answer_verifier=answer_verifier,
        contribution=contribution,
        provenance=provenance,
        validation=validation,
    )
    print(json.dumps({"summary_report": summary["json_path"], "status": "completed"}, indent=2, sort_keys=True))
    return 0


def write_preflight() -> dict[str, Any]:
    candidate_config = robust_generalized_candidate_config(DEFAULT_CONFIG)
    components = {
        key: value
        for key, value in asdict(candidate_config).items()
        if key.startswith("enable_") or key in {"candidate_shadow_only", "real_behavior_trial_mode"}
    }
    payload = {
        "report_type": "robust_generalized_eval_preflight",
        "git_status": command_text(["git", "status", "--short"]),
        "packaged_default_strategy": PACKAGED_DEFAULT_STRATEGY,
        "candidate_strategy_available": ROBUST_GENERALIZED_HARNESS_CANDIDATE in ALL_STRATEGIES,
        "ablation_strategies": ROBUST_ABLATION_STRATEGIES,
        "candidate_components_enabled": components,
        "llm_backend_available": llm_backend_available(),
        "score_provenance_status": existing_report_status("score_provenance_audit"),
        "hardcode_fake_score_audit_status": existing_report_status("hardcoded_runtime_and_score_path_audit"),
        "check_submission_ready": run_command(["python3", "scripts/check_submission_ready.py"], timeout=180),
        "hidden_style_status": "deferred_to_validation",
        "runtime_gold_visible": False,
        "score_source": "preflight",
        "promotion_judgment": "not_run",
    }
    write_report_pair(
        "robust_generalized_eval_preflight",
        payload,
        "# Robust Generalized Eval Preflight\n\n" + bullet_lines(flatten_for_md(payload)),
    )
    return payload


def run_organizer35() -> dict[str, Any]:
    command = [
        "python3",
        "scripts/run_dev_eval.py",
        "--strict",
        "--strategies",
        ",".join(STRICT_STRATEGIES),
    ]
    result = run_command(command, timeout=3600)
    eval_path = DEFAULT_CONFIG.outputs_dir / "eval_results_strict.json"
    payload: dict[str, Any] = {
        "report_type": "robust_generalized_organizer35_ablation",
        "score_source": "organizer_strict",
        "real_agent_execution": True,
        "synthetic_trace": False,
        "organizer_equivalent": True,
        "runtime_gold_visible": False,
        "promotion_eligible": False,
        "promotion_judgment": "not_run",
        "command": result,
        "eval_results_path": str(eval_path),
    }
    if result["returncode"] == 0 and eval_path.exists():
        raw = load_json(eval_path)
        payload.update(summarize_organizer_results(raw))
    else:
        payload["status"] = "failed_or_blocked"
        payload["summary"] = {}
    write_report_pair("robust_generalized_organizer35_ablation", payload, organizer_md(payload))
    return payload


def run_internal500(*, limit: int | None = None) -> dict[str, Any]:
    command = [
        "python3",
        "scripts/run_dashagent_500_prompt_suite_eval.py",
        "--engine",
        "real_agent",
        "--suite",
        "data/benchmarks/dashagent_500_prompt_suite.jsonl",
        "--gold",
        "data/benchmarks/dashagent_500_prompt_suite_gold.jsonl",
    ]
    for mode in INTERNAL_500_MODES:
        command.extend(["--mode", mode])
    if limit:
        command.extend(["--limit", str(limit)])
    else:
        command.append("--full")
    command.extend([
        "--seed",
        "20260525",
        "--clean",
        "--output-dir",
        "outputs/robust_generalized_internal500_eval",
    ])
    result = run_command(command, timeout=14400)
    eval_path = REPORTS_DIR / "dashagent_500_prompt_suite_eval_real.json"
    payload: dict[str, Any] = {
        "report_type": "robust_generalized_internal500_ablation",
        "score_source": "internal_500_heuristic",
        "real_agent_execution": True,
        "synthetic_trace": False,
        "organizer_equivalent": False,
        "runtime_gold_visible": False,
        "promotion_eligible": False,
        "promotion_judgment": "not_run",
        "command": result,
        "eval_results_path": str(eval_path),
    }
    if result["returncode"] == 0 and eval_path.exists():
        raw = load_json(eval_path)
        payload.update(summarize_internal500_results(raw))
    else:
        payload["status"] = "failed_or_blocked"
        payload["summary"] = {}
    write_report_pair("robust_generalized_internal500_ablation", payload, internal500_md(payload))
    return payload


def run_focused_stress() -> dict[str, Any]:
    FOCUSED_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    base_executor = AgentExecutor(DEFAULT_CONFIG)
    executors: dict[str, AgentExecutor] = {"SQL_FIRST_API_VERIFY": base_executor}
    rows: list[dict[str, Any]] = []
    for strategy in STRICT_STRATEGIES:
        if strategy not in executors:
            cfg = config_for_applied_trial_strategy(DEFAULT_CONFIG, strategy)
            executors[strategy] = AgentExecutor(
                cfg,
                db=base_executor.db,
                schema_index=base_executor.schema_index,
                endpoint_catalog=base_executor.endpoint_catalog,
                api_client=base_executor.api_client,
            )
        executor = executors[strategy]
        for case in FOCUSED_CASES:
            out_dir = FOCUSED_OUTPUT_DIR / case["query_id"] / strategy.lower()
            start = time.perf_counter()
            try:
                result = executor.run(
                    case["prompt"],
                    strategy=strategy,
                    query_id=case["query_id"],
                    output_dir=out_dir,
                )
                row = focused_row(case, strategy, result, runtime=time.perf_counter() - start)
            except Exception as exc:  # Diagnostic report should preserve failures without aborting the suite.
                row = {
                    **case,
                    "strategy": strategy,
                    "error": type(exc).__name__,
                    "error_message": safe_text(str(exc)),
                    "runtime": round(time.perf_counter() - start, 4),
                    "tool_call_count": 0,
                    "sql_call_count": 0,
                    "api_call_count": 0,
                    "unsupported_claims": None,
                    "no_tool_false_positive": bool(case["expected_evidence"]),
                    "no_tool_false_negative": False,
                    "api_required_underuse": bool(case["api_required"]),
                }
            rows.append(row)
    payload = {
        "report_type": "robust_generalized_focused_stress_ablation",
        "score_source": "focused_stress_real_agent",
        "real_agent_execution": True,
        "synthetic_trace": False,
        "organizer_equivalent": False,
        "runtime_gold_visible": False,
        "promotion_eligible": False,
        "promotion_judgment": "not_run",
        "cases": len(FOCUSED_CASES),
        "strategies": STRICT_STRATEGIES,
        "rows": rows,
        "summary": summarize_focused_rows(rows),
    }
    write_report_pair("robust_generalized_focused_stress_ablation", payload, focused_md(payload))
    return payload


def focused_row(case: dict[str, Any], strategy: str, result: dict[str, Any], *, runtime: float) -> dict[str, Any]:
    trajectory = result.get("trajectory") if isinstance(result.get("trajectory"), dict) else {}
    checkpoints = result.get("checkpoints") if isinstance(result.get("checkpoints"), list) else trajectory.get("checkpoints", [])
    tool_results = result.get("tool_results") if isinstance(result.get("tool_results"), list) else []
    sql_calls = [item for item in tool_results if isinstance(item, dict) and item.get("type") == "sql"]
    api_calls = [item for item in tool_results if isinstance(item, dict) and item.get("type") == "api"]
    tool_call_count = len(sql_calls) + len(api_calls)
    unsupported = extract_unsupported_count(checkpoints)
    verifier = final_answer_verifier_metrics(checkpoints)
    answer = str(result.get("final_answer") or "")
    return {
        **case,
        "strategy": strategy,
        "final_answer": answer[:500],
        "runtime": round(runtime, 4),
        "estimated_tokens": trajectory.get("estimated_tokens", 0),
        "tool_call_count": tool_call_count,
        "sql_call_count": len(sql_calls),
        "api_call_count": len(api_calls),
        "unsupported_claims": unsupported,
        "no_tool_false_positive": bool(case["expected_evidence"] and tool_call_count == 0),
        "no_tool_false_negative": bool(case["expected_no_tool"] and tool_call_count > 0),
        "api_required_underuse": bool(case["api_required"] and not api_calls),
        "evidence_available_but_not_rendered": evidence_available_but_not_rendered(checkpoints, answer),
        "verifier_first_pass_ok": verifier.get("first_pass_ok"),
        "verifier_blocked_claims": verifier.get("blocked_claims", 0),
        "verifier_rewrite_attempted": verifier.get("rewrite_attempted"),
        "verifier_rewrite_success": verifier.get("rewrite_success"),
        "verifier_fallback_used": verifier.get("fallback_used"),
        "checkpoint_names": [
            str(item.get("name") or item.get("checkpoint") or "")
            for item in checkpoints
            if isinstance(item, dict)
        ],
    }


def summarize_organizer_results(raw: dict[str, Any]) -> dict[str, Any]:
    rows = raw.get("rows", [])
    by_strategy = raw.get("summary", {}).get("by_strategy", {})
    baseline_rows = {row["query_id"]: row for row in rows if row.get("strategy") == "SQL_FIRST_API_VERIFY"}
    strategy_rows = defaultdict(list)
    for row in rows:
        strategy_rows[row.get("strategy")].append(row)
    table = {}
    comparisons = {}
    for strategy, metrics in by_strategy.items():
        rows_for_strategy = strategy_rows.get(strategy, [])
        api_underuse = sum(1 for row in rows_for_strategy if "No generated API call while gold API exists" in str(row.get("api_reason")))
        no_tool_fp = sum(
            1
            for row in rows_for_strategy
            if int(row.get("tool_call_count") or 0) == 0
            and (zeroish(row.get("sql_score")) or zeroish(row.get("api_score")))
        )
        table[strategy] = {
            "final_score": metrics.get("avg_final_score"),
            "correctness": metrics.get("avg_correctness_score"),
            "sql_score": metrics.get("avg_sql_score"),
            "api_score": metrics.get("avg_api_score"),
            "answer_score": metrics.get("avg_answer_score"),
            "tool_calls": metrics.get("avg_tool_call_count"),
            "runtime": metrics.get("avg_runtime"),
            "tokens": metrics.get("avg_estimated_tokens"),
            "validation_failures": sum(int(row.get("validation_failures") or 0) for row in rows_for_strategy),
            "unsupported_claims": None,
            "api_required_underuse": api_underuse,
            "no_tool_false_positive": no_tool_fp,
            "sql_calls": sum(int(row.get("sql_call_count") or 0) for row in rows_for_strategy),
            "api_calls": sum(int(row.get("api_call_count") or 0) for row in rows_for_strategy),
        }
        comparisons[strategy] = compare_strict_rows(baseline_rows, {row["query_id"]: row for row in rows_for_strategy})
    return {
        "status": "completed",
        "examples": raw.get("examples"),
        "strategies": raw.get("strategies"),
        "summary": table,
        "comparisons_vs_baseline": comparisons,
        "severe_regression_rows": {
            strategy: [
                row
                for row in comparison.get("hurt_examples", [])
                if float(row.get("delta") or 0) <= -0.05
            ]
            for strategy, comparison in comparisons.items()
        },
    }


def summarize_internal500_results(raw: dict[str, Any]) -> dict[str, Any]:
    summaries = raw.get("mode_summary") or raw.get("modes") or {}
    comparisons = raw.get("mode_comparisons") or {}
    table = {}
    for mode, metrics in summaries.items():
        if metrics.get("excluded_from_comparison"):
            table[mode] = {"available": False, "blockers": metrics.get("blockers", [])}
            continue
        table[mode] = {
            "available": True,
            "behavior_score": metrics.get("behavior_score"),
            "final_answer_correctness": metrics.get("final_answer_correctness"),
            "required_facts_coverage": metrics.get("required_facts_coverage"),
            "answer_grounding_score": metrics.get("answer_grounding_score"),
            "trace_observability_score": metrics.get("trace_observability_score"),
            "combined_diagnostic_score": metrics.get("combined_diagnostic_score"),
            "sql_accuracy": metrics.get("sql_required_used_accuracy"),
            "api_accuracy": metrics.get("api_required_used_accuracy"),
            "unsupported_claims": metrics.get("unsupported_claims"),
            "no_tool_false_positive": metrics.get("no_tool_false_positive"),
            "no_tool_false_negative": metrics.get("no_tool_false_negative"),
            "api_required_underuse": metrics.get("api_required_underuse"),
            "sql_calls": metrics.get("sql_calls"),
            "api_calls": metrics.get("api_calls"),
            "api_calls_saved": metrics.get("api_calls_saved"),
            "api_calls_added": metrics.get("api_calls_added"),
            "runtime_ms": metrics.get("runtime_ms"),
            "tokens": metrics.get("estimated_total_tokens"),
            "per_category": metrics.get("per_category"),
            "comparison_vs_baseline": comparisons.get(mode, {}),
        }
    return {
        "status": "completed",
        "prompt_count": raw.get("prompt_count"),
        "full_requested": raw.get("full_requested"),
        "summary": table,
        "comparisons_vs_baseline": comparisons,
    }


def summarize_focused_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    by_strategy_suite: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    by_strategy: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_strategy_suite[(row["strategy"], row["suite"])].append(row)
        by_strategy[row["strategy"]].append(row)
    for strategy, strategy_rows in sorted(by_strategy.items()):
        summary[strategy] = aggregate_focused(strategy_rows)
        summary[strategy]["by_suite"] = {
            suite: aggregate_focused(items)
            for (item_strategy, suite), items in sorted(by_strategy_suite.items())
            if item_strategy == strategy
        }
    return summary


def aggregate_focused(rows: list[dict[str, Any]]) -> dict[str, Any]:
    count = len(rows) or 1
    return {
        "prompt_count": len(rows),
        "no_tool_false_positive": sum(1 for row in rows if row.get("no_tool_false_positive")),
        "no_tool_false_negative": sum(1 for row in rows if row.get("no_tool_false_negative")),
        "api_required_underuse": sum(1 for row in rows if row.get("api_required_underuse")),
        "evidence_available_but_not_rendered": sum(1 for row in rows if row.get("evidence_available_but_not_rendered")),
        "unsupported_claims": sum(int(row.get("unsupported_claims") or 0) for row in rows),
        "llm_answer_verifier_blocked_claims": sum(int(row.get("verifier_blocked_claims") or 0) for row in rows),
        "llm_answer_rewrite_attempted": sum(1 for row in rows if row.get("verifier_rewrite_attempted")),
        "llm_answer_rewrite_success": sum(1 for row in rows if row.get("verifier_rewrite_success")),
        "llm_answer_fallback_used": sum(1 for row in rows if row.get("verifier_fallback_used")),
        "sql_calls": sum(int(row.get("sql_call_count") or 0) for row in rows),
        "api_calls": sum(int(row.get("api_call_count") or 0) for row in rows),
        "runtime": round(sum(float(row.get("runtime") or 0.0) for row in rows) / count, 4),
        "tokens": round(sum(float(row.get("estimated_tokens") or 0.0) for row in rows) / count, 4),
        "errors": sum(1 for row in rows if row.get("error")),
    }


def write_answer_verifier_report(
    organizer: dict[str, Any] | None,
    internal500: dict[str, Any] | None,
    focused: dict[str, Any] | None,
) -> dict[str, Any]:
    strategies = [
        "SQL_FIRST_API_VERIFY",
        "ROBUST_ABLATION_LLM_ANSWER_NO_VERIFIER",
        "ROBUST_ABLATION_LLM_ANSWER_WITH_VERIFIER",
        "ROBUST_ABLATION_ANSWER_GROUNDING_ONLY",
        "ROBUST_ABLATION_FULL_CANDIDATE_NO_LLM_ANSWER",
        ROBUST_GENERALIZED_HARNESS_CANDIDATE,
    ]
    payload = {
        "report_type": "llm_answer_verifier_ablation",
        "promotion_judgment": "not_run",
        "strategies": strategies,
        "organizer_answer_scores": extract_metric_table(organizer, strategies, "answer_score"),
        "internal500_final_answer_correctness": extract_metric_table(internal500, strategy_to_internal_modes(strategies), "final_answer_correctness"),
        "focused_verifier_metrics": {
            strategy: (focused or {}).get("summary", {}).get(strategy, {})
            for strategy in strategies
        },
        "notes": [
            "LLM answer without verifier is diagnostic-only and promotion-ineligible.",
            "The verifier is measured by unsupported claims, blocked claims, rewrite success, fallback usage, and answer-score deltas when available.",
        ],
    }
    write_report_pair("llm_answer_verifier_ablation", payload, answer_verifier_md(payload))
    return payload


def write_component_contribution_report(
    organizer: dict[str, Any] | None,
    internal500: dict[str, Any] | None,
    focused: dict[str, Any] | None,
) -> dict[str, Any]:
    baseline_org = metric(organizer, "SQL_FIRST_API_VERIFY", "final_score")
    baseline_500 = metric(internal500, "packaged_baseline_real", "behavior_score")
    components: dict[str, dict[str, Any]] = {}
    for strategy in [ROBUST_GENERALIZED_HARNESS_CANDIDATE, *ROBUST_ABLATION_STRATEGIES]:
        internal_mode = strategy_to_internal_mode(strategy)
        org_delta = delta(metric(organizer, strategy, "final_score"), baseline_org)
        behavior_delta = delta(metric(internal500, internal_mode, "behavior_score"), baseline_500)
        safety_delta = focused_safety_delta(focused, strategy)
        components[strategy] = {
            "components": COMPONENTS_BY_STRATEGY.get(strategy, ["full_candidate"]),
            "organizer_final_delta": org_delta,
            "internal500_behavior_delta": behavior_delta,
            "focused_safety_delta": safety_delta,
            "api_call_delta_internal500": comparison_metric(internal500, internal_mode, "api_call_delta"),
            "token_delta_internal500": comparison_metric(internal500, internal_mode, "token_delta"),
            "runtime_delta_internal500": comparison_metric(internal500, internal_mode, "runtime_ms_delta"),
            "classification": classify_component(org_delta, behavior_delta, safety_delta),
        }
    payload = {
        "report_type": "robust_generalized_component_contribution",
        "promotion_judgment": "not_run",
        "components": components,
        "ranking": sorted(
            components,
            key=lambda item: (
                components[item].get("internal500_behavior_delta") or 0.0,
                components[item].get("organizer_final_delta") or 0.0,
                components[item].get("focused_safety_delta") or 0.0,
            ),
            reverse=True,
        ),
    }
    write_report_pair("robust_generalized_component_contribution", payload, contribution_md(payload))
    return payload


def run_provenance_audits() -> dict[str, Any]:
    commands = {
        "hardcoded_runtime_and_score_path_audit": ["python3", "scripts/audit_hardcoded_runtime_and_score_paths.py"],
        "score_provenance_audit": ["python3", "scripts/audit_score_provenance.py"],
    }
    return {name: run_command(command, timeout=900) for name, command in commands.items()}


def run_validation_suite() -> dict[str, Any]:
    commands = {
        "hidden_style": ["python3", "scripts/run_hidden_style_eval.py"],
        "check_submission_ready": ["python3", "scripts/check_submission_ready.py"],
        "workshop_audit": ["python3", "scripts/audit_workshop_requirements.py"],
        "sdk_usage_audit": ["python3", "scripts/generate_sdk_usage_audit.py"],
        "pytest": ["python3", "-m", "pytest", "-q"],
        "git_diff_check": ["git", "diff", "--check"],
    }
    validation = {name: run_command(command, timeout=2400) for name, command in commands.items()}
    validation["secret_scan"] = run_secret_scan()
    return validation


def run_secret_scan() -> dict[str, Any]:
    command = [
        "rg",
        "-n",
        "--glob",
        "!*.env",
        "--glob",
        "!*.env.*",
        "--glob",
        "!**/venv/**",
        "--glob",
        "!**/.venv/**",
        "--glob",
        "!**/*.zip",
        "--glob",
        "!**/archives/**",
        "(sk-[A-Za-z0-9_-]{20,}|xox[baprs]-[A-Za-z0-9-]{20,}|AKIA[0-9A-Z]{16}|ADOBE_ACCESS_TOKEN\\s*=\\s*[^\\s]+|CLIENT_SECRET\\s*=\\s*[^\\s]+)",
        "dashagent",
        "scripts",
        "tests",
        "outputs/reports",
        "outputs/eval_results_strict.json",
    ]
    result = run_command(command, timeout=600)
    # rg returns 1 when no matches are found.
    result["passed"] = result["returncode"] in {0, 1} and not result["stdout_tail"].strip()
    if result["returncode"] == 0:
        result["passed"] = False
        result["stdout_tail"] = "[redacted potential secret hits; inspect locally]"
    return result


def write_controlled_summary(**parts: Any) -> dict[str, Any]:
    payload = {
        "report_type": "robust_generalized_controlled_eval_summary",
        "promotion_judgment": "not_run",
        "packaged_default_strategy": PACKAGED_DEFAULT_STRATEGY,
        "packaged_default_unchanged": PACKAGED_DEFAULT_STRATEGY == "SQL_FIRST_API_VERIFY",
        "final_submission_format_changed": False,
        "score_source_summary": {
            "organizer35": "organizer_strict",
            "internal500": "internal_500_heuristic",
            "focused_stress": "focused_stress_real_agent",
        },
        **parts,
    }
    payload["high_level_tables"] = {
        "organizer35": (parts.get("organizer") or {}).get("summary", {}),
        "internal500": (parts.get("internal500") or {}).get("summary", {}),
        "focused_stress": (parts.get("focused") or {}).get("summary", {}),
    }
    md = controlled_summary_md(payload)
    paths = write_report_pair("robust_generalized_controlled_eval_summary", payload, md)
    payload.update(paths)
    return payload


def compare_strict_rows(baseline: dict[str, dict[str, Any]], candidate: dict[str, dict[str, Any]]) -> dict[str, Any]:
    helped = []
    hurt = []
    neutral = 0
    final_answer_changed = 0
    api_saved = 0
    api_added = 0
    for query_id, row in candidate.items():
        base = baseline.get(query_id)
        if not base:
            continue
        delta_score = round(float(row.get("final_score") or 0.0) - float(base.get("final_score") or 0.0), 4)
        api_delta = int(row.get("api_call_count") or 0) - int(base.get("api_call_count") or 0)
        if delta_score > 0.005:
            helped.append({"query_id": query_id, "delta": delta_score, "api_delta": api_delta})
        elif delta_score < -0.005:
            hurt.append({"query_id": query_id, "delta": delta_score, "api_delta": api_delta})
        else:
            neutral += 1
        api_saved += max(0, -api_delta)
        api_added += max(0, api_delta)
        final_answer_changed += int(str(row.get("answer_reason")) != str(base.get("answer_reason")))
    return {
        "helped": len(helped),
        "hurt": len(hurt),
        "neutral": neutral,
        "api_calls_saved": api_saved,
        "api_calls_added": api_added,
        "final_answer_changed_count_proxy": final_answer_changed,
        "helped_examples": sorted(helped, key=lambda item: item["delta"], reverse=True)[:20],
        "hurt_examples": sorted(hurt, key=lambda item: item["delta"])[:20],
    }


def strategy_to_internal_mode(strategy: str) -> str:
    if strategy == "SQL_FIRST_API_VERIFY":
        return "packaged_baseline_real"
    if strategy == ROBUST_GENERALIZED_HARNESS_CANDIDATE:
        return "robust_generalized_harness_candidate_real"
    return "ablation_" + strategy.removeprefix("ROBUST_ABLATION_").lower() + "_real"


def strategy_to_internal_modes(strategies: list[str]) -> list[str]:
    return [strategy_to_internal_mode(strategy) for strategy in strategies]


def metric(report: dict[str, Any] | None, strategy: str, key: str) -> Any:
    if not report:
        return None
    return (report.get("summary") or {}).get(strategy, {}).get(key)


def comparison_metric(report: dict[str, Any] | None, mode: str, key: str) -> Any:
    if not report:
        return None
    return (report.get("comparisons_vs_baseline") or {}).get(mode, {}).get(key)


def extract_metric_table(report: dict[str, Any] | None, strategies: list[str], key: str) -> dict[str, Any]:
    return {strategy: metric(report, strategy, key) for strategy in strategies}


def delta(candidate: Any, baseline: Any) -> float | None:
    if candidate is None or baseline is None:
        return None
    try:
        return round(float(candidate) - float(baseline), 4)
    except Exception:
        return None


def focused_safety_delta(focused: dict[str, Any] | None, strategy: str) -> int | None:
    if not focused:
        return None
    baseline = (focused.get("summary") or {}).get("SQL_FIRST_API_VERIFY", {})
    candidate = (focused.get("summary") or {}).get(strategy, {})
    if not candidate:
        return None
    base_issues = safety_issue_count(baseline)
    candidate_issues = safety_issue_count(candidate)
    return base_issues - candidate_issues


def safety_issue_count(summary: dict[str, Any]) -> int:
    return int(summary.get("no_tool_false_positive") or 0) + int(summary.get("api_required_underuse") or 0) + int(summary.get("unsupported_claims") or 0)


def classify_component(org_delta: float | None, behavior_delta: float | None, safety_delta: int | None) -> str:
    safety = safety_delta or 0
    behavior = behavior_delta or 0.0
    organizer = org_delta or 0.0
    if safety > 0 and behavior >= -0.005 and organizer >= -0.005:
        return "safety_positive"
    if behavior > 0.005 or organizer > 0.005:
        return "net_positive"
    if behavior < -0.005 or organizer < -0.005 or safety < 0:
        return "net_negative"
    return "neutral"


def extract_unsupported_count(checkpoints: list[dict[str, Any]]) -> int:
    for checkpoint in checkpoints:
        if not isinstance(checkpoint, dict):
            continue
        name = str(checkpoint.get("name") or checkpoint.get("checkpoint") or "")
        if name not in {"checkpoint_16_answer_verification", "checkpoint_evidence_grounded_final_answer_verifier"}:
            continue
        output = checkpoint_output(checkpoint)
        for key in ("unsupported_claims_count", "unsupported_claims"):
            value = output.get(key)
            if isinstance(value, list):
                return len(value)
            if isinstance(value, int):
                return value
    return 0


def final_answer_verifier_metrics(checkpoints: list[dict[str, Any]]) -> dict[str, Any]:
    metrics = {
        "first_pass_ok": None,
        "blocked_claims": 0,
        "rewrite_attempted": False,
        "rewrite_success": False,
        "fallback_used": False,
    }
    for checkpoint in checkpoints:
        if not isinstance(checkpoint, dict):
            continue
        name = str(checkpoint.get("name") or checkpoint.get("checkpoint") or "")
        if name == "checkpoint_evidence_grounded_final_answer_verifier":
            output = checkpoint_output(checkpoint)
            unsupported = output.get("unsupported_claims") or []
            over = output.get("over_specified_claims") or []
            needs = output.get("needs_caveat_claims") or []
            metrics["first_pass_ok"] = bool(output.get("ok")) if "ok" in output else None
            metrics["blocked_claims"] = len(unsupported) + len(over) + len(needs)
            metrics["fallback_used"] = output.get("action") == "FALLBACK_DETERMINISTIC"
        if name == "checkpoint_llm_answer_rewrite_feedback":
            output = checkpoint_output(checkpoint)
            metrics["rewrite_attempted"] = bool(output.get("rewrite_attempted", True))
            metrics["rewrite_success"] = bool(output.get("rewrite_success"))
            metrics["fallback_used"] = metrics["fallback_used"] or bool(output.get("fallback_used"))
    return metrics


def evidence_available_but_not_rendered(checkpoints: list[dict[str, Any]], answer: str) -> bool:
    values: list[str] = []
    for checkpoint in checkpoints:
        if not isinstance(checkpoint, dict):
            continue
        name = str(checkpoint.get("name") or checkpoint.get("checkpoint") or "")
        if name in {"checkpoint_15_answer_slots", "checkpoint_answer_slot_renderer", "checkpoint_evidence_grounded_answer_builder"}:
            values.extend(collect_scalar_values(checkpoint_output(checkpoint)))
    candidates = [value for value in values if len(value) >= 3 and not value.lower().startswith(("http", "select "))]
    if not candidates:
        return False
    answer_lower = answer.lower()
    return not any(value.lower() in answer_lower for value in candidates[:20])


def collect_scalar_values(payload: Any) -> list[str]:
    values: list[str] = []
    if isinstance(payload, dict):
        for value in payload.values():
            values.extend(collect_scalar_values(value))
    elif isinstance(payload, list):
        for value in payload:
            values.extend(collect_scalar_values(value))
    elif isinstance(payload, (str, int, float)) and payload not in ("", 0, 0.0):
        values.append(str(payload))
    return values


def checkpoint_output(checkpoint: dict[str, Any]) -> dict[str, Any]:
    output = checkpoint.get("output")
    return output if isinstance(output, dict) else {}


def zeroish(value: Any) -> bool:
    try:
        return float(value) == 0.0
    except Exception:
        return False


def llm_backend_available() -> bool:
    try:
        from dashagent.llm_client import get_llm_client

        return bool(get_llm_client().available())
    except Exception:
        return False


def existing_report_status(stem: str) -> dict[str, Any]:
    json_path = REPORTS_DIR / f"{stem}.json"
    md_path = REPORTS_DIR / f"{stem}.md"
    return {"json_exists": json_path.exists(), "md_exists": md_path.exists()}


def command_text(command: list[str]) -> str:
    result = run_command(command, timeout=120)
    return result.get("stdout_tail") or result.get("stderr_tail") or ""


def run_command(command: list[str], *, timeout: int) -> dict[str, Any]:
    start = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        return {
            "command": " ".join(command),
            "returncode": completed.returncode,
            "runtime_seconds": round(time.perf_counter() - start, 4),
            "stdout_tail": safe_tail(completed.stdout),
            "stderr_tail": safe_tail(completed.stderr),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": " ".join(command),
            "returncode": 124,
            "runtime_seconds": round(time.perf_counter() - start, 4),
            "stdout_tail": safe_tail(exc.stdout or ""),
            "stderr_tail": safe_tail(exc.stderr or "timeout"),
        }


def safe_tail(text: str | bytes, *, max_chars: int = 8000) -> str:
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="replace")
    return safe_text(text[-max_chars:])


def safe_text(text: str) -> str:
    patterns = [
        r"(?i)(ADOBE_ACCESS_TOKEN|ACCESS_TOKEN|CLIENT_SECRET|ADOBE_CLIENT_SECRET|API_KEY|ADOBE_API_KEY)\s*[:=]\s*[^\s,}]+",
        r"sk-[A-Za-z0-9_-]{20,}",
        r"xox[baprs]-[A-Za-z0-9-]{20,}",
        r"AKIA[0-9A-Z]{16}",
    ]
    redacted = text
    for pattern in patterns:
        redacted = re.sub(pattern, "[REDACTED]", redacted)
    return redacted


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_report_pair(stem: str, payload: dict[str, Any], md: str) -> dict[str, str]:
    json_path = REPORTS_DIR / f"{stem}.json"
    md_path = REPORTS_DIR / f"{stem}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(md, encoding="utf-8")
    return {"json_path": str(json_path), "md_path": str(md_path)}


def flatten_for_md(payload: dict[str, Any]) -> dict[str, Any]:
    flat = {}
    for key, value in payload.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            flat[key] = value
        elif isinstance(value, list):
            flat[key] = f"{len(value)} items"
        elif isinstance(value, dict):
            flat[key] = json.dumps(value, sort_keys=True, default=str)[:500]
    return flat


def bullet_lines(payload: dict[str, Any]) -> str:
    return "\n".join(f"- {key}: `{value}`" for key, value in payload.items()) + "\n"


def organizer_md(payload: dict[str, Any]) -> str:
    lines = ["# Robust Generalized Organizer 35 Ablation", "", f"- status: `{payload.get('status')}`", ""]
    lines.extend(table_md(payload.get("summary", {}), ["final_score", "correctness", "sql_score", "api_score", "answer_score", "api_required_underuse", "sql_calls", "api_calls"]))
    lines.append("")
    lines.append("No promotion judgment is made in this diagnostic report.")
    return "\n".join(lines)


def internal500_md(payload: dict[str, Any]) -> str:
    lines = ["# Robust Generalized Internal 500 Ablation", "", f"- status: `{payload.get('status')}`", f"- prompt_count: `{payload.get('prompt_count')}`", ""]
    lines.extend(table_md(payload.get("summary", {}), ["behavior_score", "final_answer_correctness", "trace_observability_score", "combined_diagnostic_score", "unsupported_claims", "no_tool_false_positive", "api_required_underuse", "sql_calls", "api_calls"]))
    lines.append("")
    lines.append("This is internal heuristic gold, not organizer-equivalent.")
    return "\n".join(lines)


def focused_md(payload: dict[str, Any]) -> str:
    lines = ["# Robust Generalized Focused Stress Ablation", "", f"- cases: `{payload.get('cases')}`", ""]
    lines.extend(table_md(payload.get("summary", {}), ["no_tool_false_positive", "no_tool_false_negative", "api_required_underuse", "unsupported_claims", "llm_answer_verifier_blocked_claims", "llm_answer_rewrite_success", "llm_answer_fallback_used", "sql_calls", "api_calls"]))
    return "\n".join(lines)


def answer_verifier_md(payload: dict[str, Any]) -> str:
    lines = ["# LLM Answer Verifier Ablation", ""]
    lines.append("The no-verifier mode is diagnostic-only and promotion-ineligible.")
    lines.append("")
    lines.append("## Organizer Answer Scores")
    lines.extend(simple_metric_table(payload.get("organizer_answer_scores", {})))
    lines.append("")
    lines.append("## Internal 500 Final Answer Correctness")
    lines.extend(simple_metric_table(payload.get("internal500_final_answer_correctness", {})))
    return "\n".join(lines)


def contribution_md(payload: dict[str, Any]) -> str:
    rows = payload.get("components", {})
    lines = ["# Robust Generalized Component Contribution", "", "| Strategy | Organizer delta | Internal 500 delta | Safety delta | Classification |", "|---|---:|---:|---:|---|"]
    for strategy, metrics in rows.items():
        lines.append(
            f"| {strategy} | {metrics.get('organizer_final_delta')} | {metrics.get('internal500_behavior_delta')} | {metrics.get('focused_safety_delta')} | {metrics.get('classification')} |"
        )
    lines.append("")
    lines.append("No promotion recommendation is made.")
    return "\n".join(lines)


def controlled_summary_md(payload: dict[str, Any]) -> str:
    lines = ["# Robust Generalized Controlled Eval Summary", ""]
    lines.append(f"- packaged_default_strategy: `{payload.get('packaged_default_strategy')}`")
    lines.append(f"- packaged_default_unchanged: `{payload.get('packaged_default_unchanged')}`")
    lines.append("- promotion_judgment: `not_run`")
    lines.append("")
    lines.append("## Organizer 35")
    lines.extend(table_md((payload.get("organizer") or {}).get("summary", {}), ["final_score", "correctness", "sql_score", "api_score", "answer_score", "api_required_underuse"]))
    lines.append("")
    lines.append("## Internal 500")
    lines.extend(table_md((payload.get("internal500") or {}).get("summary", {}), ["behavior_score", "final_answer_correctness", "combined_diagnostic_score", "unsupported_claims", "api_required_underuse"]))
    lines.append("")
    lines.append("## Focused Stress")
    lines.extend(table_md((payload.get("focused") or {}).get("summary", {}), ["no_tool_false_positive", "no_tool_false_negative", "api_required_underuse", "unsupported_claims"]))
    lines.append("")
    lines.append("This report is diagnostic-only and intentionally does not recommend promotion.")
    return "\n".join(lines)


def table_md(rows: dict[str, Any], keys: list[str]) -> list[str]:
    if not rows:
        return ["No rows available."]
    lines = ["| Mode | " + " | ".join(keys) + " |", "|---|" + "|".join("---:" for _ in keys) + "|"]
    for name, values in rows.items():
        if not isinstance(values, dict):
            continue
        lines.append("| " + str(name) + " | " + " | ".join(str(values.get(key)) for key in keys) + " |")
    return lines


def simple_metric_table(metrics: dict[str, Any]) -> list[str]:
    lines = ["| Strategy | Value |", "|---|---:|"]
    for strategy, value in metrics.items():
        lines.append(f"| {strategy} | {value} |")
    return lines


if __name__ == "__main__":
    raise SystemExit(main())
