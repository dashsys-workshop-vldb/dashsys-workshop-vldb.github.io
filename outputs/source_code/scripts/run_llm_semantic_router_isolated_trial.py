#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.eval_harness import (
    EvalExample,
    EvalHarness,
    aggregate_strict_correctness,
    count_validation_failures,
    first_generated_sql,
    generated_api_calls,
    metadata_prompt_tokens,
    normalize_sql,
    score_answer_strict,
    score_api_strict,
    score_sql_strict,
)
from dashagent.executor import AgentExecutor
from dashagent.llm_client import get_llm_client
from dashagent.trajectory import redact_secrets
from scripts.load_local_env import load_local_env
from scripts.run_llm_semantic_router_shadow_eval import _backend_metadata


DEFAULT_LIMIT = 50
PACKAGED_STRICT_BASELINE = 0.6553
ISOLATED_OUTPUT_DIR = "llm_semantic_router_isolated_trial"
REPORT_STEM = "llm_semantic_router_isolated_trial"
PROMOTION_STEM = "llm_semantic_router_promotion_decision"


def main() -> int:
    args = parse_args()
    config = Config.from_env(ROOT)
    load_local_env(config.project_root)
    report = run_llm_semantic_router_isolated_trial(
        config,
        limit=args.limit,
        full=args.full,
        public_only=args.public_only,
        generated_only=args.generated_only,
        clean=args.clean,
        strict_public_set=args.strict_public_set,
    )
    print(
        json.dumps(
            {
                "status": report.get("status"),
                "total_prompts": report.get("total_prompts"),
                "strict_scoring_status": report.get("strict_scoring_status"),
                "recommendation": report.get("recommendation"),
                "json": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.json"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run an isolated non-shadow trial of the LLM semantic routing helper.")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help=f"Prompt limit. Defaults to {DEFAULT_LIMIT}.")
    parser.add_argument("--full", action="store_true", help="Run all selected prompts.")
    parser.add_argument("--public-only", action="store_true", help="Run only public/dev examples from data/data.json.")
    parser.add_argument("--generated-only", action="store_true", help="Run only generated diagnostic prompts.")
    parser.add_argument("--clean", action="store_true", help=f"Remove only outputs/{ISOLATED_OUTPUT_DIR}/ before running.")
    parser.add_argument("--strict-public-set", action="store_true", help="Run the complete public/dev strict set only.")
    return parser.parse_args()


def run_llm_semantic_router_isolated_trial(
    config: Config | None = None,
    *,
    limit: int = DEFAULT_LIMIT,
    full: bool = False,
    public_only: bool = False,
    generated_only: bool = False,
    clean: bool = False,
    strict_public_set: bool = False,
) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    output_root = config.outputs_dir / ISOLATED_OUTPUT_DIR
    if clean and output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    client = get_llm_client()
    backend = _backend_metadata(client)
    prompts, examples_by_id = _select_prompts(
        config,
        limit=limit,
        full=full,
        public_only=public_only,
        generated_only=generated_only,
        strict_public_set=strict_public_set,
    )
    if not client.available():
        reason = client.generate_messages([]).get("reason", "LLM provider API key is not set")
        report = _skipped_report(config, prompts, backend, str(reason))
        _write_reports(config, report)
        return report

    trial_config = replace(
        config,
        enable_llm_semantic_router=True,
        llm_semantic_router_shadow_only=False,
    )
    executor = AgentExecutor(trial_config)
    harness = EvalHarness(config)
    baseline = _load_baseline(config)
    rows: list[dict[str, Any]] = []
    for item in prompts:
        prompt_id = str(item["prompt_id"])
        prompt = str(item["prompt"])
        out_dir = output_root / prompt_id
        start = time.perf_counter()
        try:
            result = executor.run(prompt, strategy="SQL_FIRST_API_VERIFY", query_id=prompt_id, output_dir=out_dir)
            elapsed = time.perf_counter() - start
            trajectory = result.get("trajectory") or _load_json(out_dir / "trajectory.json")
            example = examples_by_id.get(prompt_id)
            rows.append(_build_row(config, harness, item, trajectory, elapsed, out_dir, example, baseline.get(prompt_id)))
        except Exception as exc:
            rows.append(
                redact_secrets(
                    {
                        "prompt_id": prompt_id,
                        "prompt": prompt,
                        "source": item.get("source"),
                        "status": "failed",
                        "failure_category": "runtime_error",
                        "error": f"{type(exc).__name__}: {exc}",
                        "runtime": round(time.perf_counter() - start, 4),
                        "output_dir": _rel(config, out_dir),
                    }
                )
            )

    report = _build_report(config, prompts, rows, backend)
    _write_reports(config, report)
    return report


def _select_prompts(
    config: Config,
    *,
    limit: int,
    full: bool,
    public_only: bool,
    generated_only: bool,
    strict_public_set: bool,
) -> tuple[list[dict[str, Any]], dict[str, EvalExample]]:
    if public_only and generated_only:
        raise ValueError("--public-only and --generated-only are mutually exclusive")
    if strict_public_set:
        public_only = True
        generated_only = False
        full = True

    harness = EvalHarness(config)
    examples = harness.load_examples()
    examples_by_id = {example.query_id: example for example in examples}
    prompts: list[dict[str, Any]] = []
    if not generated_only:
        prompts.extend(
            {
                "prompt_id": example.query_id,
                "prompt": example.query,
                "source": "data/data.json",
                "strict_scoring_available": True,
            }
            for example in examples
        )
    if generated_only and not public_only:
        prompts.extend(_load_generated_prompts(config.data_dir / "generated_prompt_suite.json"))

    if full:
        return prompts, examples_by_id
    return prompts[: max(0, min(limit, len(prompts)))], examples_by_id


def _load_generated_prompts(path: Path) -> list[dict[str, Any]]:
    payload = _load_json(path)
    if not isinstance(payload, list):
        return []
    prompts: list[dict[str, Any]] = []
    for index, item in enumerate(payload, start=1):
        if not isinstance(item, dict) or not item.get("prompt"):
            continue
        prompts.append(
            {
                "prompt_id": str(item.get("prompt_id") or f"generated_{index:04d}"),
                "prompt": str(item["prompt"]),
                "source": str(path),
                "strict_scoring_available": False,
                "diagnostic_only": True,
            }
        )
    return prompts


def _load_baseline(config: Config) -> dict[str, dict[str, Any]]:
    strict = _load_json(config.outputs_dir / "eval_results_strict.json")
    rows = {
        str(row.get("query_id")): {"row": row}
        for row in strict.get("rows", [])
        if isinstance(row, dict) and row.get("strategy") == "SQL_FIRST_API_VERIFY"
    }
    for query_id, payload in rows.items():
        output_dir = payload["row"].get("output_dir")
        trajectory_path = Path(output_dir) / "trajectory.json" if output_dir else None
        if trajectory_path and trajectory_path.exists():
            payload["trajectory"] = _load_json(trajectory_path)
    return rows


def _build_row(
    config: Config,
    harness: EvalHarness,
    item: dict[str, Any],
    trajectory: dict[str, Any],
    elapsed: float,
    out_dir: Path,
    example: EvalExample | None,
    baseline: dict[str, Any] | None,
) -> dict[str, Any]:
    prompt_id = str(item.get("prompt_id") or trajectory.get("query_id"))
    checkpoint = _semantic_checkpoint(trajectory)
    baseline_row = (baseline or {}).get("row") or {}
    baseline_trajectory = (baseline or {}).get("trajectory") or {}
    trial_scoring = _score_trial_row(harness, example, trajectory) if example is not None else _no_strict_score("generated_diagnostic_prompt")
    baseline_scores = _baseline_scores(baseline_row)
    generated_sql = first_generated_sql(trajectory)
    baseline_sql = first_generated_sql(baseline_trajectory)
    generated_api = generated_api_calls(trajectory)
    baseline_api = generated_api_calls(baseline_trajectory)
    trial_answer = str(trajectory.get("final_answer") or "")
    baseline_answer = str(baseline_trajectory.get("final_answer") or "")
    tool_count = int(trajectory.get("tool_call_count") or 0)
    baseline_tool_count = int(baseline_row.get("tool_call_count") or baseline_trajectory.get("tool_call_count") or 0)
    runtime = float(trajectory.get("runtime") or elapsed)
    baseline_runtime = _as_float(baseline_row.get("runtime") or baseline_trajectory.get("runtime"))
    tokens = int(trajectory.get("estimated_tokens") or 0)
    baseline_tokens = _as_int(baseline_row.get("estimated_tokens") or baseline_trajectory.get("estimated_tokens"))
    validation_failures = count_validation_failures(trajectory)
    baseline_validation_failures = int(baseline_row.get("validation_failures") or count_validation_failures(baseline_trajectory))
    row = {
        "prompt_id": prompt_id,
        "query_id": prompt_id,
        "prompt": item.get("prompt") or trajectory.get("original_query"),
        "source": item.get("source"),
        "status": "passed",
        "diagnostic_only": bool(item.get("diagnostic_only", False)),
        "output_dir": _rel(config, out_dir),
        "strict_scoring_status": trial_scoring["strict_scoring_status"],
        "strict_scoring_unavailable_reason": trial_scoring.get("strict_scoring_unavailable_reason"),
        "trial_strict_final_score": trial_scoring.get("final_score"),
        "baseline_strict_final_score": baseline_scores.get("final_score"),
        "strict_final_score_delta": _delta(trial_scoring.get("final_score"), baseline_scores.get("final_score")),
        "trial_correctness_score": trial_scoring.get("correctness_score"),
        "baseline_correctness_score": baseline_scores.get("correctness_score"),
        "correctness_delta": _delta(trial_scoring.get("correctness_score"), baseline_scores.get("correctness_score")),
        "trial_answer_score": trial_scoring.get("answer_score"),
        "baseline_answer_score": baseline_scores.get("answer_score"),
        "answer_score_delta": _delta(trial_scoring.get("answer_score"), baseline_scores.get("answer_score")),
        "trial_sql_score": trial_scoring.get("sql_score"),
        "baseline_sql_score": baseline_scores.get("sql_score"),
        "sql_score_delta": _delta(trial_scoring.get("sql_score"), baseline_scores.get("sql_score")),
        "trial_api_score": trial_scoring.get("api_score"),
        "baseline_api_score": baseline_scores.get("api_score"),
        "api_score_delta": _delta(trial_scoring.get("api_score"), baseline_scores.get("api_score")),
        "sql_reason": trial_scoring.get("sql_reason"),
        "api_reason": trial_scoring.get("api_reason"),
        "answer_reason": trial_scoring.get("answer_reason"),
        "deterministic_route_before": checkpoint.get("deterministic_route_type"),
        "helper_route_suggestion": checkpoint.get("helper_route_suggestion"),
        "applied_route": trajectory.get("route_type"),
        "deterministic_domain_before": checkpoint.get("deterministic_domain_type"),
        "helper_domain_suggestion": checkpoint.get("helper_likely_domain"),
        "applied_domain": trajectory.get("domain_type"),
        "deterministic_intent_before": checkpoint.get("deterministic_answer_family"),
        "helper_intent_suggestion": checkpoint.get("helper_answer_intent"),
        "applied_intent": checkpoint.get("final_runtime_answer_family"),
        "hint_applied": checkpoint.get("hint_applied", False),
        "hint_application_mode": checkpoint.get("hint_application_mode"),
        "hint_application_reason": checkpoint.get("hint_application_reason"),
        "hint_application_skipped_reason": checkpoint.get("hint_application_skipped_reason"),
        "eligibility_reason": checkpoint.get("eligibility_reason", []),
        "helper_valid": checkpoint.get("helper_valid", False),
        "helper_rejected_reason": checkpoint.get("helper_rejected_reason"),
        "deterministic_confidence_before": checkpoint.get("deterministic_confidence_before"),
        "helper_confidence": checkpoint.get("helper_confidence"),
        "final_runtime_confidence": checkpoint.get("final_runtime_confidence"),
        "route_changed": bool(checkpoint.get("hint_applied")) and checkpoint.get("deterministic_route_type") != trajectory.get("route_type"),
        "domain_changed": bool(checkpoint.get("hint_applied")) and checkpoint.get("deterministic_domain_type") != trajectory.get("domain_type"),
        "intent_changed": bool(checkpoint.get("would_change_intent")),
        "sql_changed": normalize_sql(generated_sql) != normalize_sql(baseline_sql),
        "api_changed": _normalize_api_calls(generated_api) != _normalize_api_calls(baseline_api),
        "answer_changed": bool(baseline_answer) and trial_answer.strip() != baseline_answer.strip(),
        "tool_count": tool_count,
        "baseline_tool_count": baseline_tool_count,
        "tool_count_delta": tool_count - baseline_tool_count,
        "estimated_tokens": tokens,
        "baseline_estimated_tokens": baseline_tokens,
        "estimated_token_delta": _delta(tokens, baseline_tokens),
        "runtime": round(runtime, 4),
        "baseline_runtime": baseline_runtime,
        "runtime_delta": _delta(runtime, baseline_runtime),
        "validation_failures": validation_failures,
        "baseline_validation_failures": baseline_validation_failures,
        "validation_failure_delta": validation_failures - baseline_validation_failures,
        "sql_call_count": int(trajectory.get("sql_call_count") or 0),
        "api_call_count": int(trajectory.get("api_call_count") or 0),
        "baseline_sql_call_count": int(baseline_row.get("sql_call_count") or baseline_trajectory.get("sql_call_count") or 0),
        "baseline_api_call_count": int(baseline_row.get("api_call_count") or baseline_trajectory.get("api_call_count") or 0),
        "baseline_sql": baseline_sql,
        "trial_sql": generated_sql,
        "baseline_api_calls": baseline_api,
        "trial_api_calls": generated_api,
        "baseline_plan": _plan_signature(baseline_trajectory),
        "trial_plan": _plan_signature(trajectory),
        "baseline_answer": baseline_answer,
        "trial_answer": trial_answer,
        "failures_introduced": _failures_introduced(trial_scoring, baseline_scores, validation_failures, baseline_validation_failures),
        "failures_fixed": _failures_fixed(trial_scoring, baseline_scores, validation_failures, baseline_validation_failures),
    }
    return redact_secrets(row)


def _score_trial_row(harness: EvalHarness, example: EvalExample | None, trajectory: dict[str, Any]) -> dict[str, Any]:
    if example is None:
        return _no_strict_score("missing_public_example")
    try:
        generated_sql = first_generated_sql(trajectory)
        generated_api = generated_api_calls(trajectory)
        final_answer = str(trajectory.get("final_answer") or "")
        sql_score, sql_reason = score_sql_strict(harness.executor.db, generated_sql, example.gold_sql)
        api_score, api_reason = score_api_strict(generated_api, example.gold_api)
        answer_score, answer_reason = score_answer_strict(final_answer, example.gold_answer)
        correctness_score, unscored_dimension_count = aggregate_strict_correctness(
            {"sql": sql_score, "api": api_score, "answer": answer_score}
        )
        metadata_tokens, prompt_tokens = metadata_prompt_tokens(trajectory)
        efficiency_penalty = min(
            1.0,
            (float(trajectory.get("tool_call_count") or 0) / 8)
            + (float(trajectory.get("runtime") or 0.0) / 30)
            + (float(trajectory.get("estimated_tokens") or 0) / 12000),
        )
        final_score = correctness_score - 0.1 * efficiency_penalty
        return {
            "strict_scoring_status": "available",
            "sql_score": _round_or_none(sql_score),
            "api_score": _round_or_none(api_score),
            "answer_score": _round_or_none(answer_score),
            "correctness_score": round(correctness_score, 4),
            "efficiency_penalty": round(efficiency_penalty, 4),
            "final_score": round(final_score, 4),
            "metadata_tokens": metadata_tokens,
            "prompt_tokens": prompt_tokens,
            "sql_reason": sql_reason,
            "api_reason": api_reason,
            "answer_reason": answer_reason,
            "unscored_dimension_count": unscored_dimension_count,
        }
    except Exception as exc:
        return _no_strict_score(f"strict_scoring_unavailable:{type(exc).__name__}")


def _no_strict_score(reason: str) -> dict[str, Any]:
    return {
        "strict_scoring_status": "unavailable",
        "strict_scoring_unavailable_reason": reason,
        "sql_score": None,
        "api_score": None,
        "answer_score": None,
        "correctness_score": None,
        "efficiency_penalty": None,
        "final_score": None,
        "sql_reason": reason,
        "api_reason": reason,
        "answer_reason": reason,
        "unscored_dimension_count": 3,
    }


def _baseline_scores(row: dict[str, Any]) -> dict[str, Any]:
    if not row:
        return {}
    return {
        "sql_score": row.get("sql_score"),
        "api_score": row.get("api_score"),
        "answer_score": row.get("answer_score"),
        "correctness_score": row.get("correctness_score"),
        "final_score": row.get("final_score"),
    }


def _build_report(config: Config, prompts: list[dict[str, Any]], rows: list[dict[str, Any]], backend: dict[str, Any]) -> dict[str, Any]:
    passed = [row for row in rows if row.get("status") == "passed"]
    scored = [row for row in passed if row.get("strict_scoring_status") == "available"]
    failures = [row for row in rows if row.get("status") != "passed"]
    strict_delta = _delta(_avg(row.get("trial_strict_final_score") for row in scored), _avg(row.get("baseline_strict_final_score") for row in scored))
    safety_failures = _safety_failures(rows)
    recommendation = _recommendation(config, strict_delta, safety_failures, rows)
    helped = _helped_examples(passed)
    risky = _risky_examples(passed)
    report = {
        "report_type": REPORT_STEM,
        "diagnostic_only": True,
        "isolated_non_shadow": True,
        "official_promotion_performed": False,
        "packaged_runtime_affected": False,
        "status": "complete",
        "output_root": _rel(config, config.outputs_dir / ISOLATED_OUTPUT_DIR),
        "total_prompts": len(prompts),
        "passed_runtime_count": len(passed),
        "failed_runtime_count": len(failures),
        "strict_scoring_status": "available" if scored else "unavailable",
        "strict_score_delta": strict_delta,
        "baseline_avg_strict_final_score": _avg(row.get("baseline_strict_final_score") for row in scored),
        "trial_avg_strict_final_score": _avg(row.get("trial_strict_final_score") for row in scored),
        "baseline_avg_correctness": _avg(row.get("baseline_correctness_score") for row in scored),
        "trial_avg_correctness": _avg(row.get("trial_correctness_score") for row in scored),
        "answer_score_delta": _delta(_avg(row.get("trial_answer_score") for row in scored), _avg(row.get("baseline_answer_score") for row in scored)),
        "sql_score_delta": _delta(_avg(row.get("trial_sql_score") for row in scored), _avg(row.get("baseline_sql_score") for row in scored)),
        "api_score_delta": _delta(_avg(row.get("trial_api_score") for row in scored), _avg(row.get("baseline_api_score") for row in scored)),
        "route_changed_count": sum(1 for row in passed if row.get("route_changed")),
        "domain_changed_count": sum(1 for row in passed if row.get("domain_changed")),
        "intent_changed_count": sum(1 for row in passed if row.get("intent_changed")),
        "sql_changed_count": sum(1 for row in passed if row.get("sql_changed")),
        "api_changed_count": sum(1 for row in passed if row.get("api_changed")),
        "answer_changed_count": sum(1 for row in passed if row.get("answer_changed")),
        "tool_count_delta_avg": _avg(row.get("tool_count_delta") for row in passed),
        "estimated_token_delta_avg": _avg(row.get("estimated_token_delta") for row in passed),
        "runtime_delta_avg": _avg(row.get("runtime_delta") for row in passed),
        "failures_introduced_count": sum(len(row.get("failures_introduced") or []) for row in passed),
        "failures_fixed_count": sum(len(row.get("failures_fixed") or []) for row in passed),
        "failure_categories": dict(Counter(reason for row in rows for reason in _row_failure_categories(row))),
        "safety_failures": safety_failures,
        "where_semantic_routing_helped": helped,
        "where_semantic_routing_hurt_or_was_risky": risky,
        "recommendation": recommendation,
        "recommendation_reason": _recommendation_reason(recommendation, strict_delta, safety_failures),
        **backend,
        "rows": rows,
    }
    return redact_secrets(report)


def _skipped_report(config: Config, prompts: list[dict[str, Any]], backend: dict[str, Any], reason: str) -> dict[str, Any]:
    report = redact_secrets(
        {
            "report_type": REPORT_STEM,
            "diagnostic_only": True,
            "isolated_non_shadow": True,
            "official_promotion_performed": False,
            "packaged_runtime_affected": False,
            "status": "skipped",
            "skipped_reason": reason,
            "total_prompts": len(prompts),
            "strict_scoring_status": "unavailable",
            "strict_score_delta": None,
            "safety_failures": [],
            "where_semantic_routing_helped": [],
            "where_semantic_routing_hurt_or_was_risky": [],
            "recommendation": "keep_shadow_only",
            "recommendation_reason": "No configured SDK backend/key was available for isolated non-shadow trial.",
            **backend,
            "rows": [],
        }
    )
    return report if isinstance(report, dict) else {}


def _write_reports(config: Config, report: dict[str, Any]) -> None:
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    trial_json = reports_dir / f"{REPORT_STEM}.json"
    trial_md = reports_dir / f"{REPORT_STEM}.md"
    trial_json.write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    trial_md.write_text(_render_trial_markdown(report), encoding="utf-8")
    decision = _promotion_decision_report(config, report)
    (reports_dir / f"{PROMOTION_STEM}.json").write_text(json.dumps(decision, indent=2, sort_keys=True, default=str), encoding="utf-8")
    (reports_dir / f"{PROMOTION_STEM}.md").write_text(_render_promotion_markdown(decision), encoding="utf-8")


def _promotion_decision_report(config: Config, report: dict[str, Any]) -> dict[str, Any]:
    hidden = _hidden_status(config)
    readiness = _readiness_status(config)
    sdk = _sdk_status(config)
    strict_delta = report.get("strict_score_delta")
    safety_failures = list(report.get("safety_failures") or [])
    meaningful_regression = _meaningful_regression(report)
    gates = {
        "strict_score_improves_over_0_6553": bool(
            isinstance(report.get("trial_avg_strict_final_score"), (int, float))
            and float(report["trial_avg_strict_final_score"]) > PACKAGED_STRICT_BASELINE
        ),
        "strict_delta_positive": bool(isinstance(strict_delta, (int, float)) and strict_delta > 0),
        "hidden_style_48_48": hidden.get("ok"),
        "check_submission_ready_passed": readiness.get("ok"),
        "no_safety_failures": not safety_failures,
        "runtime_direct_llm_http_hits_zero": sdk.get("runtime_llm_direct_http_hits") in {0, "0"},
        "final_submission_format_unchanged": True,
        "no_automatic_promotion": True,
        "no_meaningful_token_tool_runtime_regression": not meaningful_regression,
    }
    if safety_failures or (isinstance(strict_delta, (int, float)) and strict_delta < 0):
        decision = "do_not_promote"
    elif all(gates.values()):
        decision = "candidate_for_limited_promotion"
    else:
        decision = "keep_shadow_only"
    return redact_secrets(
        {
            "report_type": PROMOTION_STEM,
            "decision": decision,
            "official_promotion_performed": False,
            "packaged_runtime_affected": False,
            "source_report": f"outputs/reports/{REPORT_STEM}.md",
            "gates": gates,
            "strict_score_delta": strict_delta,
            "packaged_strict_baseline": PACKAGED_STRICT_BASELINE,
            "trial_avg_strict_final_score": report.get("trial_avg_strict_final_score"),
            "safety_failures": safety_failures,
            "hidden_style_status": hidden,
            "readiness_status": readiness,
            "sdk_usage_status": sdk,
            "meaningful_regression": meaningful_regression,
            "recommendation_reason": _promotion_reason(decision, gates, safety_failures, strict_delta),
        }
    )


def _render_trial_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# LLM Semantic Router Isolated Trial",
        "",
        "Diagnostic isolated non-shadow trial only. This report does not promote packaged runtime behavior.",
        "",
        f"- Status: `{report.get('status')}`",
        f"- Packaged runtime affected: `{report.get('packaged_runtime_affected')}`",
        f"- Backend/model: `{report.get('model')}`",
        f"- SDK path used: `{report.get('sdk_path_used')}`",
        f"- Total prompts: `{report.get('total_prompts')}`",
        f"- Strict scoring status: `{report.get('strict_scoring_status')}`",
        f"- Baseline avg strict score: `{report.get('baseline_avg_strict_final_score')}`",
        f"- Trial avg strict score: `{report.get('trial_avg_strict_final_score')}`",
        f"- Strict score delta: `{report.get('strict_score_delta')}`",
        f"- Route/domain/intent changes: `{report.get('route_changed_count')}` / `{report.get('domain_changed_count')}` / `{report.get('intent_changed_count')}`",
        f"- SQL/API/answer changes: `{report.get('sql_changed_count')}` / `{report.get('api_changed_count')}` / `{report.get('answer_changed_count')}`",
        f"- Recommendation: `{report.get('recommendation')}`",
        "",
    ]
    if report.get("skipped_reason"):
        lines.extend([f"Skipped reason: {report.get('skipped_reason')}", ""])
    lines.extend(["## Where Semantic Routing Helped", ""])
    helped = report.get("where_semantic_routing_helped") or []
    if helped:
        for row in helped[:5]:
            lines.append(_example_line(row))
    else:
        lines.append("- No helped examples identified in this run.")
    lines.extend(["", "## Where Semantic Routing Hurt Or Was Risky", ""])
    risky = report.get("where_semantic_routing_hurt_or_was_risky") or []
    if risky:
        for row in risky[:5]:
            lines.append(_example_line(row))
    else:
        lines.append("- No risky examples identified in this run.")
    lines.extend(["", "## Safety", ""])
    failures = report.get("safety_failures") or []
    lines.append(f"- Safety failures: `{len(failures)}`")
    for failure in failures[:10]:
        lines.append(f"- `{failure}`")
    lines.append("")
    return "\n".join(lines)


def _render_promotion_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# LLM Semantic Router Promotion Decision",
        "",
        "Report-only decision. No automatic promotion was performed.",
        "",
        f"- Decision: `{report.get('decision')}`",
        f"- Packaged runtime affected: `{report.get('packaged_runtime_affected')}`",
        f"- Strict score delta: `{report.get('strict_score_delta')}`",
        f"- Trial avg strict score: `{report.get('trial_avg_strict_final_score')}`",
        f"- Recommendation reason: {report.get('recommendation_reason')}",
        "",
        "## Gates",
        "",
    ]
    for key, value in (report.get("gates") or {}).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.append("")
    return "\n".join(lines)


def _example_line(row: dict[str, Any]) -> str:
    return (
        f"- `{row.get('query_id')}`: prompt={json.dumps(str(row.get('prompt') or '')[:120])}; "
        f"deterministic=`{row.get('deterministic_route_before')}/{row.get('deterministic_domain_before')}`; "
        f"helper=`{row.get('helper_route_suggestion')}/{row.get('helper_domain_suggestion')}/{row.get('helper_intent_suggestion')}`; "
        f"applied=`{row.get('hint_applied')}`; "
        f"delta=`{row.get('strict_final_score_delta')}`; "
        f"baseline_answer={json.dumps(str(row.get('baseline_answer') or '')[:120])}; "
        f"trial_answer={json.dumps(str(row.get('trial_answer') or '')[:120])}"
    )


def _helped_examples(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    helped = [
        row
        for row in rows
        if row.get("hint_applied")
        and (
            _positive(row.get("strict_final_score_delta"))
            or _positive(row.get("answer_score_delta"))
            or row.get("failures_fixed")
        )
    ]
    return helped[:10]


def _risky_examples(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    risky = [
        row
        for row in rows
        if row.get("hint_applied")
        and (
            _negative(row.get("strict_final_score_delta"))
            or _negative(row.get("answer_score_delta"))
            or int(row.get("tool_count_delta") or 0) > 0
            or int(row.get("validation_failure_delta") or 0) > 0
            or row.get("failures_introduced")
        )
    ]
    return risky[:10]


def _safety_failures(rows: list[dict[str, Any]]) -> list[str]:
    failures: list[str] = []
    for row in rows:
        if row.get("status") != "passed":
            failures.append(f"{row.get('query_id')}:runtime_error")
        if int(row.get("validation_failure_delta") or 0) > 0:
            failures.append(f"{row.get('query_id')}:validation_failure_introduced")
        if row.get("helper_rejected_reason"):
            failures.append(f"{row.get('query_id')}:helper_rejected:{row.get('helper_rejected_reason')}")
    return failures


def _row_failure_categories(row: dict[str, Any]) -> list[str]:
    if row.get("status") != "passed":
        return [str(row.get("failure_category") or "runtime_error")]
    categories = []
    if row.get("strict_scoring_status") != "available" and not row.get("diagnostic_only"):
        categories.append("strict_scoring_unavailable")
    categories.extend(row.get("failures_introduced") or [])
    if int(row.get("validation_failure_delta") or 0) > 0:
        categories.append("validation_failure_introduced")
    return categories


def _failures_introduced(
    trial: dict[str, Any],
    baseline: dict[str, Any],
    validation_failures: int,
    baseline_validation_failures: int,
) -> list[str]:
    failures = []
    if _negative(_delta(trial.get("sql_score"), baseline.get("sql_score"))):
        failures.append("sql_score_regression")
    if _negative(_delta(trial.get("api_score"), baseline.get("api_score"))):
        failures.append("api_score_regression")
    if _negative(_delta(trial.get("answer_score"), baseline.get("answer_score"))):
        failures.append("answer_score_regression")
    if validation_failures > baseline_validation_failures:
        failures.append("validation_failure_introduced")
    return failures


def _failures_fixed(
    trial: dict[str, Any],
    baseline: dict[str, Any],
    validation_failures: int,
    baseline_validation_failures: int,
) -> list[str]:
    fixed = []
    if _positive(_delta(trial.get("sql_score"), baseline.get("sql_score"))):
        fixed.append("sql_score_improved")
    if _positive(_delta(trial.get("api_score"), baseline.get("api_score"))):
        fixed.append("api_score_improved")
    if _positive(_delta(trial.get("answer_score"), baseline.get("answer_score"))):
        fixed.append("answer_score_improved")
    if validation_failures < baseline_validation_failures:
        fixed.append("validation_failures_reduced")
    return fixed


def _recommendation(config: Config, strict_delta: float | None, safety_failures: list[str], rows: list[dict[str, Any]]) -> str:
    if safety_failures or _negative(strict_delta):
        return "do_not_promote"
    if _positive(strict_delta):
        route_changes_explainable = all(
            row.get("hint_application_reason")
            for row in rows
            if row.get("route_changed") or row.get("domain_changed")
        )
        if (
            _hidden_status(config).get("ok")
            and _readiness_status(config).get("ok")
            and _sdk_status(config).get("runtime_llm_direct_http_hits") in {0, "0"}
            and route_changes_explainable
        ):
            return "candidate_for_limited_promotion"
        return "keep_shadow_only"
    return "keep_shadow_only"


def _recommendation_reason(recommendation: str, strict_delta: float | None, safety_failures: list[str]) -> str:
    if recommendation == "do_not_promote":
        if safety_failures:
            return "Isolated trial introduced safety or validation failures."
        return "Isolated trial worsened strict score."
    if recommendation == "candidate_for_limited_promotion":
        return "Isolated trial improved strict score; promotion still requires separate human approval and all gates."
    if strict_delta is None:
        return "Strict scoring was unavailable; keep the helper shadow-only."
    return "No strict-score improvement was proven; keep the helper shadow-only."


def _promotion_reason(decision: str, gates: dict[str, bool], safety_failures: list[str], strict_delta: float | None) -> str:
    if decision == "do_not_promote":
        if safety_failures:
            return "Safety failures were detected in isolated trial."
        return "Strict score regressed in isolated trial."
    if decision == "candidate_for_limited_promotion":
        return "All report-visible gates passed, but no automatic promotion is performed."
    missing = [key for key, value in gates.items() if not value]
    return "Keep shadow-only because promotion gates are not all clean: " + ", ".join(missing[:6])


def _meaningful_regression(report: dict[str, Any]) -> bool:
    return bool(
        _positive(report.get("tool_count_delta_avg"))
        or _positive(report.get("estimated_token_delta_avg"), threshold=25)
        or _positive(report.get("runtime_delta_avg"), threshold=0.05)
    )


def _hidden_status(config: Config) -> dict[str, Any]:
    hidden = _load_json(config.outputs_dir / "hidden_style_eval.json")
    summary = hidden.get("summary", {})
    passed = summary.get("passed_cases")
    total = summary.get("total_cases")
    return {"passed": passed, "total": total, "ok": passed == total == 48}


def _readiness_status(config: Config) -> dict[str, Any]:
    readiness = _load_json(config.outputs_dir / "winner_readiness_report.json")
    packaged = readiness.get("packaged", {})
    ready = packaged.get("final_submission_ready")
    if ready is None:
        manifest = _load_json(config.outputs_dir / "final_submission_manifest.json")
        ready = bool(manifest.get("source_code_zip_exists") and manifest.get("system_prompt_template_exists"))
    return {"ok": bool(ready), "source": "outputs/winner_readiness_report.json"}


def _sdk_status(config: Config) -> dict[str, Any]:
    audit = _load_json(config.outputs_dir / "reports" / "sdk_usage_audit.json")
    summary = audit.get("summary", {})
    return {
        "runtime_llm_direct_http_hits": summary.get("runtime_llm_direct_http_hits", "unavailable"),
        "all_llm_calls_sdk_based": summary.get("runtime_llm_direct_http_hits") == 0,
    }


def _semantic_checkpoint(trajectory: dict[str, Any]) -> dict[str, Any]:
    step_payload = _semantic_step_payload(trajectory)
    checkpoint_payload: dict[str, Any] = {}
    for checkpoint in trajectory.get("checkpoints") or []:
        if isinstance(checkpoint, dict) and checkpoint.get("checkpoint_id") == "checkpoint_llm_semantic_routing_helper":
            output = checkpoint.get("output")
            checkpoint_payload = output if isinstance(output, dict) else {}
            break
    if step_payload:
        return {**checkpoint_payload, **step_payload}
    return checkpoint_payload


def _semantic_step_payload(trajectory: dict[str, Any]) -> dict[str, Any]:
    for step in trajectory.get("steps") or []:
        if not isinstance(step, dict) or step.get("kind") != "nlp":
            continue
        helper = step.get("llm_semantic_routing_helper")
        if isinstance(helper, dict):
            return helper
    return {}


def _plan_signature(trajectory: dict[str, Any]) -> dict[str, Any]:
    for step in trajectory.get("steps") or []:
        if isinstance(step, dict) and step.get("kind") == "plan":
            return {
                "strategy": step.get("strategy"),
                "rationale": step.get("rationale"),
                "steps": step.get("steps", [])[:5],
            }
    return {}


def _normalize_api_calls(calls: list[dict[str, Any]]) -> str:
    return json.dumps(calls, sort_keys=True, default=str)


def _delta(value: Any, baseline: Any) -> float | None:
    if not isinstance(value, (int, float)) or not isinstance(baseline, (int, float)):
        return None
    return round(float(value) - float(baseline), 4)


def _avg(values: Any) -> float | None:
    nums = [float(value) for value in values if isinstance(value, (int, float))]
    if not nums:
        return None
    return round(sum(nums) / len(nums), 4)


def _positive(value: Any, *, threshold: float = 0.0) -> bool:
    return isinstance(value, (int, float)) and float(value) > threshold


def _negative(value: Any) -> bool:
    return isinstance(value, (int, float)) and float(value) < 0


def _round_or_none(value: Any) -> float | None:
    return round(float(value), 4) if isinstance(value, (int, float)) else None


def _as_float(value: Any) -> float | None:
    try:
        return round(float(value), 4)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _rel(config: Config, path: Path) -> str:
    try:
        return path.resolve().relative_to(config.project_root.resolve()).as_posix()
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
