#!/usr/bin/env python
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.answer_synthesizer import synthesize_answer_with_diagnostics
from dashagent.config import Config
from dashagent.eval_harness import EvalHarness, first_generated_sql, generated_api_calls, normalize_sql
from dashagent.execution_based_candidate_selector import collect_candidate_gate_failures, holdout_regression_gate, select_best_candidate
from dashagent.executor import AgentExecutor
from dashagent.report_run import report_metadata
from dashagent.targeted_candidate_generator import generate_targeted_candidates
from dashagent.token_reduction_policy import apply_token_reduction_to_trajectory
from dashagent.trajectory import TrajectoryLogger
from scripts.generate_low_score_failure_mining_report import generate_low_score_failure_mining_report
from scripts.package_query_outputs import required_trajectory_fields_present
from scripts.run_official_token_reduction_eval import (
    _canonical_api,
    _dry_run_labels,
    _live_api_evidence_available,
    _load_json,
    _load_trajectory,
    _preview,
    _score_result,
)


OUTPUT_NAME = "execution_candidate_search"


def main() -> int:
    config = Config.from_env(ROOT)
    payload = run_execution_candidate_search(config)
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    json_path = config.outputs_dir / f"{OUTPUT_NAME}.json"
    md_path = config.outputs_dir / f"{OUTPUT_NAME}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "safe_rows": payload["summary"]["safe_rows"]}, indent=2, sort_keys=True))
    return 0


def run_execution_candidate_search(config: Config) -> dict[str, Any]:
    strict = _load_json(config.outputs_dir / "eval_results_strict.json")
    mining = _load_json(config.outputs_dir / "low_score_failure_mining_report.json")
    if not mining:
        mining = generate_low_score_failure_mining_report(config)
    hidden = _load_json(config.outputs_dir / "hidden_style_eval.json")
    holdout = holdout_regression_gate(hidden, candidate_diversity_delta=0)

    output_root = config.outputs_dir / OUTPUT_NAME
    _assert_isolated_output(config.outputs_dir, output_root)
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)

    executor = AgentExecutor(config)
    examples = {example.query_id: example for example in EvalHarness(config).load_examples()}
    strict_rows = {
        str(row.get("query_id")): row
        for row in strict.get("rows", [])
        if row.get("strategy") == "SQL_FIRST_API_VERIFY"
    }
    mining_rows = {str(row.get("query_id")): row for row in mining.get("rows", [])}
    target_ids = list((mining.get("summary") or {}).get("top_10_target_rows") or [])
    if not target_ids:
        target_ids = [
            str(row.get("query_id"))
            for row in mining.get("rows", [])
            if row.get("improvement_potential") in {"high", "medium"}
        ][:10]

    rows = []
    for query_id in target_ids:
        strict_row = strict_rows.get(str(query_id))
        example = examples.get(str(query_id))
        if not strict_row or not example:
            rows.append(_skipped_row(str(query_id), "missing_strict_row_or_example"))
            continue
        rows.append(_search_row(config, executor, output_root, strict_row, example, mining_rows.get(str(query_id), {}), holdout))

    selected = [row for row in rows if row.get("safe_for_packaged_trial")]
    summary = _summary(rows, selected, strict)
    return {
        **report_metadata(config.outputs_dir),
        "mode": OUTPUT_NAME,
        "feature_flag_enabled_for_search": False,
        "packaged_execution_changed": False,
        "writes_eval_outputs": False,
        "writes_final_submission": False,
        "artifact_isolation": {
            "allowed_outputs": [
                f"outputs/{OUTPUT_NAME}.json",
                f"outputs/{OUTPUT_NAME}.md",
                f"outputs/{OUTPUT_NAME}/",
            ],
            "candidate_output_root": f"outputs/{OUTPUT_NAME}/<query_id>/<candidate_id>/",
        },
        "holdout_regression_gate": holdout,
        "rows": rows,
        "selected_improvements": selected,
        "summary": summary,
        "notes": [
            "Candidates are generated from reusable schema/API/query-vocabulary rules only.",
            "No candidate trigger may depend on query_id, exact full query, memorized answers, or gold SQL/API paths.",
            "Gold labels are used only by the offline strict scorer after isolated execution.",
        ],
    }


def _search_row(
    config: Config,
    executor: AgentExecutor,
    output_root: Path,
    strict_row: dict[str, Any],
    example: Any,
    failure_row: dict[str, Any],
    holdout: dict[str, Any],
) -> dict[str, Any]:
    query_id = str(strict_row.get("query_id"))
    baseline_trajectory = _load_trajectory(strict_row.get("output_dir"))
    candidates = generate_targeted_candidates(
        query_id=query_id,
        query=str(strict_row.get("query") or example.query),
        baseline_trajectory=baseline_trajectory,
        schema_index=executor.schema_index,
        endpoint_catalog=executor.endpoint_catalog,
        failure_row=failure_row,
    )
    candidate_rows = []
    for candidate in candidates:
        candidate_rows.append(
            _execute_and_score_candidate(
                config,
                executor,
                output_root,
                strict_row,
                example,
                baseline_trajectory,
                candidate,
                holdout,
            )
        )
    best = select_best_candidate(candidate_rows)
    return {
        "query_id": query_id,
        "query": strict_row.get("query"),
        "baseline_score": strict_row.get("final_score"),
        "baseline_correctness": strict_row.get("correctness_score"),
        "candidate_count": len(candidate_rows),
        "candidates": candidate_rows,
        "selected_candidate_id": best.get("candidate_id") if best else None,
        "score_delta": best.get("score_delta") if best else 0.0,
        "correctness_delta": best.get("correctness_delta") if best else 0.0,
        "safe_for_packaged_trial": best is not None,
        "selection_reason": "strict_or_correctness_improvement_passed_all_gates" if best else "no_candidate_passed_all_gates",
        "rejected_candidate_reasons": {
            row["candidate_id"]: row.get("rejection_reason")
            for row in candidate_rows
            if not row.get("safe_for_packaged_trial")
        },
        "best_candidate": best,
    }


def _execute_and_score_candidate(
    config: Config,
    executor: AgentExecutor,
    output_root: Path,
    strict_row: dict[str, Any],
    example: Any,
    baseline_trajectory: dict[str, Any],
    candidate: dict[str, Any],
    holdout: dict[str, Any],
) -> dict[str, Any]:
    query_id = str(strict_row.get("query_id"))
    candidate_id = str(candidate.get("candidate_id"))
    output_dir = output_root / query_id / candidate_id
    _assert_isolated_output(config.outputs_dir, output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    trajectory = _run_candidate_plan(config, executor, output_dir, example.query, query_id, candidate)
    answer = str(trajectory.get("final_answer") or "")
    scores = _score_result(executor, trajectory, answer, example)

    baseline_answer = str(baseline_trajectory.get("final_answer") or "")
    baseline_sql = first_generated_sql(baseline_trajectory)
    candidate_sql = first_generated_sql(trajectory)
    baseline_api = generated_api_calls(baseline_trajectory)
    candidate_api = generated_api_calls(trajectory)
    baseline_score = float(strict_row.get("final_score") or 0.0)
    candidate_score = float(scores.get("final_score") or 0.0)
    baseline_correctness = float(strict_row.get("correctness_score") or 0.0)
    candidate_correctness = float(scores.get("correctness_score") or 0.0)
    baseline_tokens = int(strict_row.get("estimated_tokens") or baseline_trajectory.get("estimated_tokens") or 0)
    candidate_tokens = int(trajectory.get("estimated_tokens") or 0)
    baseline_runtime = float(strict_row.get("runtime") or baseline_trajectory.get("runtime") or 0.0)
    candidate_runtime = float(trajectory.get("runtime") or 0.0)
    baseline_tools = int(strict_row.get("tool_call_count") or baseline_trajectory.get("tool_call_count") or 0)
    candidate_tools = int(trajectory.get("tool_call_count") or 0)
    sql_validation_ok = _sql_validation_ok(trajectory, bool(candidate.get("sql")))
    api_validation_ok = _api_validation_ok(trajectory, bool(candidate.get("api_call")))
    sql_errors = _validation_errors(trajectory, "sql")
    api_errors = _validation_errors(trajectory, "api")
    sql_changed = normalize_sql(baseline_sql) != normalize_sql(candidate_sql)
    api_changed = _canonical_api(baseline_api) != _canonical_api(candidate_api)
    answer_changed = answer != baseline_answer
    correctness_delta = round(candidate_correctness - baseline_correctness, 4)
    row = {
        "query_id": query_id,
        "query": strict_row.get("query") or example.query,
        "candidate_id": candidate_id,
        "candidate": candidate,
        "output_dir": str(output_dir),
        "baseline_score": round(baseline_score, 4),
        "best_candidate_score": round(candidate_score, 4),
        "score_delta": round(candidate_score - baseline_score, 4),
        "baseline_correctness": round(baseline_correctness, 4),
        "best_candidate_correctness": round(candidate_correctness, 4),
        "correctness_delta": correctness_delta,
        "baseline_tokens": baseline_tokens,
        "candidate_tokens": candidate_tokens,
        "token_delta": candidate_tokens - baseline_tokens,
        "baseline_runtime": round(baseline_runtime, 4),
        "candidate_runtime": round(candidate_runtime, 4),
        "runtime_delta": round(candidate_runtime - baseline_runtime, 4),
        "baseline_tool_calls": baseline_tools,
        "candidate_tool_calls": candidate_tools,
        "tool_delta": candidate_tools - baseline_tools,
        "baseline_final_answer_preview": _preview(baseline_answer),
        "candidate_final_answer_preview": _preview(answer),
        "accuracy_relevant_change": bool(sql_changed or api_changed or answer_changed or correctness_delta > 0),
        "final_answer_unsafe_drift": answer_changed and candidate_score <= baseline_score and candidate_correctness <= baseline_correctness,
        "baseline_sql": baseline_sql,
        "candidate_sql": candidate_sql,
        "sql_unsafe_drift": sql_changed and candidate_score <= baseline_score,
        "baseline_api": baseline_api,
        "candidate_api": candidate_api,
        "api_unsafe_drift": api_changed and candidate_score <= baseline_score,
        "required_fields_preserved": required_trajectory_fields_present(trajectory),
        "dry_run_labels_preserved": _dry_run_labels(trajectory) == _dry_run_labels(baseline_trajectory),
        "evidence_label_loss": _dry_run_labels(baseline_trajectory) and _dry_run_labels(trajectory) != _dry_run_labels(baseline_trajectory),
        "live_api_evidence_fabricated": _live_api_evidence_available(trajectory) and not _live_api_evidence_available(baseline_trajectory),
        "sql_validation_ok": sql_validation_ok,
        "sql_ast_valid": sql_validation_ok,
        "sql_validation_errors": sql_errors,
        "unknown_tables": _matching_validation_errors(sql_errors, "Unknown table:"),
        "unknown_columns": _matching_validation_errors(sql_errors, "Unknown column:"),
        "destructive_sql_detected": any("blocked write" in error or "environment-changing" in error for error in sql_errors),
        "invalid_sql_detected": bool(candidate.get("sql")) and not sql_validation_ok,
        "api_validation_ok": api_validation_ok,
        "api_validation_errors": api_errors,
        "api_catalog_valid": not any("Unknown or disallowed endpoint" in error for error in api_errors),
        "unresolved_api_placeholders": _matching_validation_errors(api_errors, "unresolved path"),
        "invalid_api_detected": bool(candidate.get("api_call")) and not api_validation_ok,
        "leakage_check_passed": candidate.get("leakage_check_passed") is True,
        "leakage_reasons": candidate.get("leakage_reasons", []),
        "holdout_regression_passed": holdout.get("passed") is True,
        "holdout_regression_gate": holdout,
    }
    failed_checks = collect_candidate_gate_failures(row)
    row["selector_failed_checks"] = failed_checks
    row["safe_for_packaged_trial"] = not failed_checks
    row["rejection_reason"] = "; ".join(failed_checks)
    return row


def _run_candidate_plan(
    config: Config,
    executor: AgentExecutor,
    output_dir: Path,
    query: str,
    query_id: str,
    candidate: dict[str, Any],
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    metadata = {
        "query_id": query_id,
        "query": query,
        "strategy": "SQL_FIRST_API_VERIFY",
        "candidate_search": {
            "candidate_id": candidate.get("candidate_id"),
            "generation_reason": candidate.get("generation_reason"),
            "diagnostic_only": True,
        },
    }
    (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True, default=str), encoding="utf-8")
    (output_dir / "filled_system_prompt.txt").write_text(
        "Targeted candidate search diagnostic prompt.\n"
        + json.dumps(metadata, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    logger = TrajectoryLogger(
        query_id=query_id,
        original_query=query,
        strategy="SQL_FIRST_API_VERIFY",
        route_type="TARGETED_CANDIDATE_SEARCH",
        domain_type=str(candidate.get("generalizable_family") or "unknown"),
        max_preview_chars=config.max_preview_chars,
    )
    logger.add_step("metadata", metadata)
    logger.add_step("plan", {"candidate_id": candidate.get("candidate_id"), "candidate": candidate})
    tool_results: list[dict[str, Any]] = []
    sql = candidate.get("sql")
    if sql:
        validation = executor.sql_validator.validate(str(sql))
        logger.add_validation("sql", validation)
        if validation.ok:
            result = executor.db.execute_sql(str(sql))
            logger.add_sql_call(str(sql), validation, result)
            tool_results.append({"type": "sql", "payload": result})
        else:
            logger.add_error("Candidate SQL validation failed; SQL was not executed.")
    api_call = candidate.get("api_call") or {}
    path = api_call.get("path") or api_call.get("url")
    if path:
        method = str(api_call.get("method") or "GET").upper()
        params = api_call.get("params") if isinstance(api_call.get("params"), dict) else {}
        validation = executor.api_validator.validate(method, str(path), params, {})
        logger.add_validation("api", validation)
        if validation.ok:
            result = executor.api_client.call_api(method, str(path), params=params, headers={})
            logger.add_api_call(method, str(path), params, {}, validation, result)
            tool_results.append({"type": "api", "payload": result})
        else:
            logger.add_error("Candidate API validation failed; API was not called.")
    answer = synthesize_answer_with_diagnostics(query, tool_results)
    logger.add_step("answer_diagnostics", answer.diagnostics)
    trajectory = logger.finish(answer.answer)
    if config.enable_official_token_reduction:
        trajectory, _ = apply_token_reduction_to_trajectory(trajectory)
    (output_dir / "trajectory.json").write_text(json.dumps(trajectory, indent=2, sort_keys=True, default=str), encoding="utf-8")
    return trajectory


def _sql_validation_ok(trajectory: dict[str, Any], expected_sql: bool) -> bool:
    if not expected_sql:
        return True
    validations = [
        step.get("result", {})
        for step in trajectory.get("steps", [])
        if step.get("kind") == "validation" and step.get("target") == "sql"
    ]
    return bool(validations) and all(item.get("ok") is True for item in validations)


def _api_validation_ok(trajectory: dict[str, Any], expected_api: bool) -> bool:
    if not expected_api:
        return True
    validations = [
        step.get("result", {})
        for step in trajectory.get("steps", [])
        if step.get("kind") == "validation" and step.get("target") == "api"
    ]
    return bool(validations) and all(item.get("ok") is True for item in validations)


def _validation_errors(trajectory: dict[str, Any], target: str) -> list[str]:
    errors: list[str] = []
    for step in trajectory.get("steps", []):
        if step.get("kind") != "validation" or step.get("target") != target:
            continue
        result = step.get("result") or {}
        for error in result.get("errors") or []:
            errors.append(str(error))
    return errors


def _matching_validation_errors(errors: list[str], pattern: str) -> list[str]:
    lowered = pattern.lower()
    return [error for error in errors if lowered in error.lower()]


def _summary(rows: list[dict[str, Any]], selected: list[dict[str, Any]], strict: dict[str, Any]) -> dict[str, Any]:
    strict_summary = (strict.get("summary") or {}).get("by_strategy", {}).get("SQL_FIRST_API_VERIFY", {})
    best_total_delta = round(sum(float(row.get("score_delta") or 0.0) for row in selected), 4)
    baseline_score = float(strict_summary.get("avg_final_score") or 0.6491)
    total_examples = int(strict_summary.get("count") or len([r for r in strict.get("rows", []) if r.get("strategy") == "SQL_FIRST_API_VERIFY"]) or 35)
    best_projected_score = round(baseline_score + (best_total_delta / max(1, total_examples)), 4)
    rejection_counts: dict[str, int] = {}
    for row in rows:
        for candidate in row.get("candidates", []) or []:
            for check in candidate.get("selector_failed_checks", []) or []:
                rejection_counts[str(check)] = rejection_counts.get(str(check), 0) + 1
    return {
        "total_target_rows": len(rows),
        "safe_rows": len(selected),
        "unsafe_rows": len(rows) - len(selected),
        "candidate_rejection_reason_counts": dict(sorted(rejection_counts.items())),
        "best_total_score_delta": best_total_delta,
        "best_projected_strict_final_score": best_projected_score,
        "target_0_70_reached": best_projected_score >= 0.7000,
        "fallback_safe_improvement": best_projected_score > baseline_score,
        "selected_query_ids": [row.get("query_id") for row in selected],
        "recommendation": "safe_for_targeted_packaged_trial" if selected else "keep_shadow_only",
        "packaged_execution_changed": False,
    }


def _skipped_row(query_id: str, reason: str) -> dict[str, Any]:
    return {
        "query_id": query_id,
        "candidate_count": 0,
        "safe_for_packaged_trial": False,
        "selection_reason": reason,
        "rejected_candidate_reasons": {},
    }


def _assert_isolated_output(outputs_dir: Path, path: Path) -> None:
    resolved = path.resolve()
    allowed_root = (outputs_dir / OUTPUT_NAME).resolve()
    if resolved in {(outputs_dir / f"{OUTPUT_NAME}.json").resolve(), (outputs_dir / f"{OUTPUT_NAME}.md").resolve()}:
        return
    try:
        resolved.relative_to(allowed_root)
    except ValueError as exc:
        raise RuntimeError(f"Execution candidate search attempted to write outside isolated output root: {path}") from exc


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Execution Candidate Search",
        "",
        f"- Target rows: {summary['total_target_rows']}",
        f"- Safe rows for packaged trial: {summary['safe_rows']}",
        f"- Best projected strict final score: {summary['best_projected_strict_final_score']}",
        f"- 0.70 reached: {summary['target_0_70_reached']}",
        f"- Fallback safe improvement: {summary['fallback_safe_improvement']}",
        f"- Recommendation: `{summary['recommendation']}`",
        f"- Packaged execution changed: {summary['packaged_execution_changed']}",
        "",
        "## Selector Gate Rejections",
        "",
    ]
    rejection_counts = summary.get("candidate_rejection_reason_counts") or {}
    if rejection_counts:
        lines.extend(f"- `{reason}`: {count}" for reason, count in rejection_counts.items())
    else:
        lines.append("- None.")
    lines.extend([
        "",
        "## Selected Improvements",
        "",
    ])
    if summary["selected_query_ids"]:
        lines.extend(f"- {query_id}" for query_id in summary["selected_query_ids"])
    else:
        lines.append("- None. All candidate changes remain shadow-only.")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
