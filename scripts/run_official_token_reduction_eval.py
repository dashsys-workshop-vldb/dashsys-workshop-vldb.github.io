#!/usr/bin/env python
from __future__ import annotations

import json
import shutil
import sys
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
    first_generated_sql,
    generated_api_calls,
    normalize_sql,
    score_answer_strict,
    score_api_strict,
    score_sql_strict,
)
from dashagent.executor import AgentExecutor
from dashagent.token_reduction_policy import official_estimated_tokens
from scripts.package_query_outputs import required_trajectory_fields_present


REQUIRED_ROW_FIELDS = [
    "query_id",
    "query",
    "baseline_score",
    "reduced_score",
    "score_delta",
    "baseline_estimated_tokens",
    "reduced_estimated_tokens",
    "token_delta",
    "baseline_runtime",
    "reduced_runtime",
    "runtime_delta",
    "baseline_tool_calls",
    "reduced_tool_calls",
    "tool_delta",
    "final_answer_changed",
    "sql_changed",
    "api_changed",
    "required_fields_preserved",
    "dry_run_labels_preserved",
    "live_api_evidence_fabricated",
    "reduction_safe_to_enable",
    "reduction_rejection_reason",
]


def main() -> int:
    config = Config.from_env(ROOT)
    payload = run_official_token_reduction_eval(config)
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    json_path = config.outputs_dir / "official_token_reduction_eval.json"
    md_path = config.outputs_dir / "official_token_reduction_eval.md"
    _assert_allowed_output(config.outputs_dir, json_path)
    _assert_allowed_output(config.outputs_dir, md_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "rows": len(payload["rows"])}, indent=2, sort_keys=True))
    return 0


def run_official_token_reduction_eval(config: Config) -> dict[str, Any]:
    strict_rows = _strict_sql_first_rows(config.outputs_dir)
    output_root = config.outputs_dir / "official_token_reduction_eval"
    _assert_allowed_output(config.outputs_dir, output_root)
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)

    reduced_config = replace(config, enable_official_token_reduction=True)
    executor = AgentExecutor(reduced_config)
    examples = {example.query_id: example for example in EvalHarness(config).load_examples()}
    rows = [
        _evaluate_row(config, executor, output_root, strict_row, examples.get(str(strict_row.get("query_id"))))
        for strict_row in strict_rows
    ]
    summary = _summary(rows)
    return {
        "mode": "official_token_reduction_eval",
        "feature_flag_default": Config.from_env(config.project_root).enable_official_token_reduction,
        "feature_flag_enabled_for_experiment": True,
        "packaged_execution_changed": False,
        "official_measured_efficiency_improvement_claimed": False,
        "measured_efficiency_improvement_claimed": summary["recommendation"] == "safe_for_future_canary",
        "behavior_changing_flags_enabled": False,
        "rows": rows,
        "summary": summary,
        "artifact_isolation": {
            "allowed_outputs": [
                "outputs/official_token_reduction_eval.json",
                "outputs/official_token_reduction_eval.md",
                "outputs/official_token_reduction_eval/",
            ],
            "experiment_output_root": "outputs/official_token_reduction_eval/<query_id>/reduced_sql_first/",
            "writes_eval_outputs": False,
            "writes_final_submission": False,
            "writes_packaged_query_outputs": False,
        },
        "notes": [
            "Official token reduction is experimental only and does not change packaged SQL_FIRST_API_VERIFY outputs by default.",
            "Baseline and reduced trajectories use the same official estimated_tokens formula.",
            "No live API evidence is fabricated; dry-run labels must be preserved.",
        ],
    }


def _evaluate_row(
    config: Config,
    executor: AgentExecutor,
    output_root: Path,
    strict_row: dict[str, Any],
    example: EvalExample | None,
) -> dict[str, Any]:
    query_id = str(strict_row.get("query_id") or "")
    baseline_trajectory = _load_trajectory(strict_row.get("output_dir"))
    query = str(strict_row.get("query") or baseline_trajectory.get("original_query") or (example.query if example else ""))
    if example is None:
        return _skipped_row(query_id, query, strict_row, baseline_trajectory, "missing public eval example")
    output_dir = output_root / query_id / "reduced_sql_first"
    _assert_allowed_output(config.outputs_dir, output_dir)
    if output_dir.exists():
        shutil.rmtree(output_dir)
    result = executor.run(example.query, strategy="SQL_FIRST_API_VERIFY", query_id=query_id, output_dir=output_dir)
    reduced_trajectory = _load_json(output_dir / "trajectory.json") or result["trajectory"]
    reduced_answer = str(result.get("final_answer") or reduced_trajectory.get("final_answer") or "")
    reduced_scores = _score_result(executor, reduced_trajectory, reduced_answer, example)

    baseline_answer = str(baseline_trajectory.get("final_answer") or "")
    baseline_sql = first_generated_sql(baseline_trajectory)
    reduced_sql = first_generated_sql(reduced_trajectory)
    baseline_api = generated_api_calls(baseline_trajectory)
    reduced_api = generated_api_calls(reduced_trajectory)
    baseline_score = float(strict_row.get("final_score") or 0.0)
    reduced_score = float(reduced_scores["final_score"])
    baseline_tokens = int(strict_row.get("estimated_tokens") or baseline_trajectory.get("estimated_tokens") or 0)
    reduced_tokens = int(reduced_trajectory.get("estimated_tokens") or 0)
    row = {
        "query_id": query_id,
        "query": query,
        "baseline_score": round(baseline_score, 4),
        "reduced_score": round(reduced_score, 4),
        "score_delta": round(reduced_score - baseline_score, 4),
        "baseline_estimated_tokens": baseline_tokens,
        "reduced_estimated_tokens": reduced_tokens,
        "token_delta": reduced_tokens - baseline_tokens,
        "baseline_formula_tokens": official_estimated_tokens(baseline_trajectory),
        "reduced_formula_tokens": official_estimated_tokens(reduced_trajectory),
        "baseline_formula_matches": baseline_tokens == official_estimated_tokens(baseline_trajectory),
        "reduced_formula_matches": reduced_tokens == official_estimated_tokens(reduced_trajectory),
        "baseline_runtime": round(float(strict_row.get("runtime") or baseline_trajectory.get("runtime") or 0.0), 4),
        "reduced_runtime": round(float(reduced_trajectory.get("runtime") or 0.0), 4),
        "baseline_tool_calls": int(strict_row.get("tool_call_count") or baseline_trajectory.get("tool_call_count") or 0),
        "reduced_tool_calls": int(reduced_trajectory.get("tool_call_count") or 0),
        "baseline_final_answer_preview": _preview(baseline_answer),
        "reduced_final_answer_preview": _preview(reduced_answer),
        "final_answer_changed": baseline_answer != reduced_answer,
        "baseline_sql": baseline_sql,
        "reduced_sql": reduced_sql,
        "sql_changed": normalize_sql(baseline_sql) != normalize_sql(reduced_sql),
        "baseline_api": baseline_api,
        "reduced_api": reduced_api,
        "api_changed": _canonical_api(baseline_api) != _canonical_api(reduced_api),
        "required_fields_preserved": required_trajectory_fields_present(reduced_trajectory),
        "dry_run_labels_preserved": _dry_run_labels(reduced_trajectory) == _dry_run_labels(baseline_trajectory),
        "live_api_evidence_fabricated": _live_api_evidence_available(reduced_trajectory) and not _live_api_evidence_available(baseline_trajectory),
        "reduced_output_dir": str(output_dir),
    }
    row["runtime_delta"] = round(row["reduced_runtime"] - row["baseline_runtime"], 4)
    row["tool_delta"] = row["reduced_tool_calls"] - row["baseline_tool_calls"]
    safe, reason = _reduction_safe(row)
    row["reduction_safe_to_enable"] = safe
    row["reduction_rejection_reason"] = reason
    for field in REQUIRED_ROW_FIELDS:
        row.setdefault(field, None)
    return row


def _score_result(
    executor: AgentExecutor,
    trajectory: dict[str, Any],
    final_answer: str,
    example: EvalExample,
) -> dict[str, Any]:
    generated_sql = first_generated_sql(trajectory)
    generated_api = generated_api_calls(trajectory)
    sql_score, _ = score_sql_strict(executor.db, generated_sql, example.gold_sql)
    api_score, _ = score_api_strict(generated_api, example.gold_api)
    answer_score, _ = score_answer_strict(final_answer, example.gold_answer)
    correctness_score, unscored_dimension_count = aggregate_strict_correctness(
        {"sql": sql_score, "api": api_score, "answer": answer_score}
    )
    tool_calls = int(trajectory.get("tool_call_count", 0))
    runtime = float(trajectory.get("runtime", 0.0))
    estimated_tokens = int(trajectory.get("estimated_tokens", 0))
    efficiency_penalty = min(1.0, (tool_calls / 8) + (runtime / 30) + (estimated_tokens / 12000))
    return {
        "correctness_score": round(correctness_score, 4),
        "final_score": round(correctness_score - 0.1 * efficiency_penalty, 4),
        "unscored_dimension_count": unscored_dimension_count,
    }


def _reduction_safe(row: dict[str, Any]) -> tuple[bool, str]:
    failures = []
    if float(row.get("score_delta") or 0.0) < 0:
        failures.append("score_delta_negative")
    if int(row.get("token_delta") or 0) >= 0:
        failures.append("token_delta_not_negative")
    if int(row.get("tool_delta") or 0) > 0:
        failures.append("tool_calls_increased")
    for key, failure in [
        ("final_answer_changed", "final_answer_changed"),
        ("sql_changed", "sql_changed"),
        ("api_changed", "api_changed"),
        ("live_api_evidence_fabricated", "live_api_evidence_fabricated"),
    ]:
        if row.get(key):
            failures.append(failure)
    if row.get("required_fields_preserved") is not True:
        failures.append("required_fields_missing")
    if row.get("dry_run_labels_preserved") is not True:
        failures.append("dry_run_labels_changed")
    if row.get("reduced_formula_matches") is not True:
        failures.append("estimated_token_formula_mismatch")
    return (not failures, "; ".join(failures))


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    safe = [row for row in rows if row.get("reduction_safe_to_enable")]
    unsafe = [row for row in rows if not row.get("reduction_safe_to_enable")]
    recommendation = "keep_default_off"
    if rows and len(safe) == len(rows):
        recommendation = "safe_for_future_canary"
    elif unsafe:
        recommendation = "unsafe_do_not_enable"
    return {
        "total_rows": len(rows),
        "safe_rows": len(safe),
        "unsafe_rows": len(unsafe),
        "avg_score_delta": _avg(row.get("score_delta") for row in rows),
        "avg_token_delta": _avg(row.get("token_delta") for row in rows),
        "avg_runtime_delta": _avg(row.get("runtime_delta") for row in rows),
        "avg_tool_delta": _avg(row.get("tool_delta") for row in rows),
        "answer_changed_count": sum(1 for row in rows if row.get("final_answer_changed")),
        "sql_changed_count": sum(1 for row in rows if row.get("sql_changed")),
        "api_changed_count": sum(1 for row in rows if row.get("api_changed")),
        "baseline_formula_match_count": sum(1 for row in rows if row.get("baseline_formula_matches")),
        "reduced_formula_match_count": sum(1 for row in rows if row.get("reduced_formula_matches")),
        "formula_match_count": sum(1 for row in rows if row.get("reduced_formula_matches")),
        "recommendation": recommendation,
        "packaged_execution_changed": False,
        "official_measured_efficiency_improvement_claimed": False,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload.get("summary", {})
    lines = [
        "# Official Token Reduction Evaluation",
        "",
        "Official token reduction is experimental only, not packaged-submission improvement.",
        "",
        f"- Packaged execution changed: {payload.get('packaged_execution_changed')}",
        f"- Feature flag default: {payload.get('feature_flag_default')}",
        f"- Total rows: {summary.get('total_rows')}",
        f"- Safe rows: {summary.get('safe_rows')}",
        f"- Unsafe rows: {summary.get('unsafe_rows')}",
        f"- Avg score delta: {summary.get('avg_score_delta')}",
        f"- Avg token delta: {summary.get('avg_token_delta')}",
        f"- Avg runtime delta: {summary.get('avg_runtime_delta')}",
        f"- Avg tool delta: {summary.get('avg_tool_delta')}",
        f"- Recommendation: `{summary.get('recommendation')}`",
        "",
        "| Query ID | Score delta | Token delta | Tool delta | Answer changed? | SQL changed? | API changed? | Reduced formula OK? | Safe? | Rejection reason |",
        "| --- | ---: | ---: | ---: | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload.get("rows", []):
        formula_ok = row.get("reduced_formula_matches")
        lines.append(
            f"| `{row.get('query_id')}` | {row.get('score_delta')} | {row.get('token_delta')} | "
            f"{row.get('tool_delta')} | {row.get('final_answer_changed')} | {row.get('sql_changed')} | "
            f"{row.get('api_changed')} | {formula_ok} | {row.get('reduction_safe_to_enable')} | "
            f"{row.get('reduction_rejection_reason')} |"
        )
    return "\n".join(lines) + "\n"


def _skipped_row(query_id: str, query: str, strict_row: dict[str, Any], trajectory: dict[str, Any], reason: str) -> dict[str, Any]:
    row = {
        "query_id": query_id,
        "query": query,
        "baseline_score": strict_row.get("final_score"),
        "baseline_estimated_tokens": strict_row.get("estimated_tokens") or trajectory.get("estimated_tokens"),
        "baseline_runtime": strict_row.get("runtime") or trajectory.get("runtime"),
        "baseline_tool_calls": strict_row.get("tool_call_count") or trajectory.get("tool_call_count"),
        "reduction_safe_to_enable": False,
        "reduction_rejection_reason": reason,
    }
    for field in REQUIRED_ROW_FIELDS:
        row.setdefault(field, None)
    return row


def _strict_sql_first_rows(outputs_dir: Path) -> list[dict[str, Any]]:
    payload = _load_json(outputs_dir / "eval_results_strict.json")
    return [
        row
        for row in payload.get("rows", []) or []
        if row.get("strategy") == "SQL_FIRST_API_VERIFY"
    ]


def _load_trajectory(output_dir: Any) -> dict[str, Any]:
    if not output_dir:
        return {}
    path = Path(str(output_dir)) / "trajectory.json"
    return _load_json(path)


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _assert_allowed_output(outputs_dir: Path, path: Path) -> None:
    allowed_files = {
        (outputs_dir / "official_token_reduction_eval.json").resolve(),
        (outputs_dir / "official_token_reduction_eval.md").resolve(),
    }
    resolved = path.resolve()
    if resolved in allowed_files:
        return
    try:
        resolved.relative_to((outputs_dir / "official_token_reduction_eval").resolve())
        return
    except ValueError as exc:
        raise RuntimeError(f"Refusing to write official-token reduction artifact outside isolated paths: {path}") from exc


def _canonical_api(calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "method": str(call.get("method") or "").upper(),
            "path": str(call.get("path") or ""),
            "params": call.get("params") or {},
        }
        for call in calls
    ]


def _dry_run_labels(trajectory: dict[str, Any]) -> list[Any]:
    return [
        (step.get("result") or {}).get("dry_run")
        for step in trajectory.get("steps", [])
        if step.get("kind") == "api_call"
    ]


def _live_api_evidence_available(trajectory: dict[str, Any]) -> bool:
    for step in trajectory.get("steps", []):
        if step.get("kind") != "api_call":
            continue
        result = step.get("result") or {}
        if result.get("ok") and not result.get("dry_run"):
            return True
    return False


def _preview(text: Any, limit: int = 160) -> str:
    value = str(text or "").replace("\n", " ")
    return value[:limit] + ("..." if len(value) > limit else "")


def _avg(values: Any) -> float:
    numbers = [float(value) for value in values if value is not None]
    return round(sum(numbers) / len(numbers), 4) if numbers else 0.0


if __name__ == "__main__":
    raise SystemExit(main())
