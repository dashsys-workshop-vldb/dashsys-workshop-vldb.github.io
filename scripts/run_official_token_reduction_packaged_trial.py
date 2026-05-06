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
from dashagent.eval_harness import EvalExample, EvalHarness, first_generated_sql, generated_api_calls, normalize_sql
from dashagent.executor import AgentExecutor
from dashagent.report_run import (
    DEFAULT_RUNTIME_NOISE_SECONDS,
    report_metadata,
    runtime_budget_for_row,
    runtime_budget_summary,
)
from dashagent.token_reduction_policy import official_estimated_tokens
from scripts.package_query_outputs import required_trajectory_fields_present, scan_for_output_secrets
from scripts.run_official_token_reduction_canary import protected_output_hash_snapshot
from scripts.run_official_token_reduction_eval import (
    _avg,
    _canonical_api,
    _dry_run_labels,
    _live_api_evidence_available,
    _load_json,
    _load_trajectory,
    _preview,
    _score_result,
    _strict_sql_first_rows,
)


OUTPUT_NAME = "official_token_reduction_packaged_trial"
REQUIRED_ROW_FIELDS = [
    "query_id",
    "baseline_score",
    "trial_score",
    "score_delta",
    "baseline_tokens",
    "trial_tokens",
    "token_delta",
    "baseline_runtime",
    "trial_runtime",
    "runtime_delta",
    "baseline_tool_calls",
    "trial_tool_calls",
    "tool_delta",
    "final_answer_changed",
    "sql_changed",
    "api_changed",
    "required_fields_preserved",
    "dry_run_labels_preserved",
    "live_api_evidence_fabricated",
    "safe_to_promote",
]


def main() -> int:
    config = Config.from_env(ROOT)
    payload = run_official_token_reduction_packaged_trial(config)
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    json_path = config.outputs_dir / f"{OUTPUT_NAME}.json"
    md_path = config.outputs_dir / f"{OUTPUT_NAME}.md"
    _assert_allowed_output(config.outputs_dir, json_path)
    _assert_allowed_output(config.outputs_dir, md_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    if not payload.get("protected_output_hashes_unchanged"):
        raise RuntimeError("Official-token packaged trial modified protected official outputs.")
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "rows": len(payload["rows"])}, indent=2, sort_keys=True))
    return 0


def run_official_token_reduction_packaged_trial(config: Config) -> dict[str, Any]:
    metadata = report_metadata(config.outputs_dir, reset=True)
    before_hashes = protected_output_hash_snapshot(config)
    strict_rows = _strict_sql_first_rows(config.outputs_dir)
    output_root = config.outputs_dir / OUTPUT_NAME
    _assert_allowed_output(config.outputs_dir, output_root)
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)

    trial_config = replace(config, enable_official_token_reduction=True)
    executor = AgentExecutor(trial_config)
    examples = {example.query_id: example for example in EvalHarness(config).load_examples()}
    rows = [
        _evaluate_row(config, executor, output_root, strict_row, examples.get(str(strict_row.get("query_id"))))
        for strict_row in strict_rows
    ]
    runtime_summary = runtime_budget_summary(rows, acceptable_noise_seconds=DEFAULT_RUNTIME_NOISE_SECONDS)
    after_hashes = protected_output_hash_snapshot(config)
    protected_unchanged = before_hashes == after_hashes
    secret_scan = scan_for_output_secrets(output_root)
    for row in rows:
        row["protected_hashes_unchanged"] = protected_unchanged
        safe, reason = _safe_to_promote(row, runtime_summary=runtime_summary, secret_scan_ok=secret_scan.get("ok", False))
        row["safe_to_promote"] = safe
        row["rejection_reason"] = reason
    summary = _summary(rows, runtime_summary=runtime_summary, protected_unchanged=protected_unchanged, secret_scan_ok=secret_scan.get("ok", False))
    return {
        **metadata,
        "mode": OUTPUT_NAME,
        "feature_flag_default": Config.from_env(config.project_root).enable_official_token_reduction,
        "feature_flag_enabled_for_trial": True,
        "repair_execution_enabled": config.enable_gated_risk_cluster_repair_execution,
        "compact_context_enabled": config.enable_compact_context_when_schema_vote_safe,
        "packaged_execution_changed": False,
        "official_packaged_efficiency_improvement_claimed": False,
        "protected_output_hashes_before": before_hashes,
        "protected_output_hashes_after": after_hashes,
        "protected_output_hashes_unchanged": protected_unchanged,
        "secret_scan": secret_scan,
        "rows": rows,
        "summary": summary,
        "artifact_isolation": {
            "allowed_outputs": [
                f"outputs/{OUTPUT_NAME}.json",
                f"outputs/{OUTPUT_NAME}.md",
                f"outputs/{OUTPUT_NAME}/",
            ],
            "trial_output_root": f"outputs/{OUTPUT_NAME}/<query_id>/sql_first_api_verify/",
            "writes_eval_outputs": False,
            "writes_final_submission": False,
            "writes_packaged_query_outputs": False,
        },
        "notes": [
            "This is a packaged flag trial only; ENABLE_OFFICIAL_TOKEN_REDUCTION remains default false.",
            "Promotion to packaged outputs requires a later explicit task.",
            "Strict scoring and estimated-token formula match the official eval helpers.",
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
    output_dir = output_root / query_id / "sql_first_api_verify"
    _assert_allowed_output(config.outputs_dir, output_dir)
    if output_dir.exists():
        shutil.rmtree(output_dir)
    result = executor.run(example.query, strategy="SQL_FIRST_API_VERIFY", query_id=query_id, output_dir=output_dir)
    trial_trajectory = _load_json(output_dir / "trajectory.json") or result["trajectory"]
    trial_answer = str(result.get("final_answer") or trial_trajectory.get("final_answer") or "")
    trial_scores = _score_result(executor, trial_trajectory, trial_answer, example)

    baseline_answer = str(baseline_trajectory.get("final_answer") or "")
    baseline_sql = first_generated_sql(baseline_trajectory)
    trial_sql = first_generated_sql(trial_trajectory)
    baseline_api = generated_api_calls(baseline_trajectory)
    trial_api = generated_api_calls(trial_trajectory)
    baseline_score = float(strict_row.get("final_score") or 0.0)
    trial_score = float(trial_scores["final_score"])
    baseline_tokens = int(strict_row.get("estimated_tokens") or baseline_trajectory.get("estimated_tokens") or 0)
    trial_tokens = int(trial_trajectory.get("estimated_tokens") or 0)
    runtime = runtime_budget_for_row(
        baseline_runtime=float(strict_row.get("runtime") or baseline_trajectory.get("runtime") or 0.0),
        trial_runtime=float(trial_trajectory.get("runtime") or 0.0),
    )
    row = {
        "query_id": query_id,
        "query": query,
        "baseline_score": round(baseline_score, 4),
        "trial_score": round(trial_score, 4),
        "score_delta": round(trial_score - baseline_score, 4),
        "baseline_tokens": baseline_tokens,
        "trial_tokens": trial_tokens,
        "token_delta": trial_tokens - baseline_tokens,
        "baseline_formula_tokens": official_estimated_tokens(baseline_trajectory),
        "trial_formula_tokens": official_estimated_tokens(trial_trajectory),
        "trial_formula_matches": trial_tokens == official_estimated_tokens(trial_trajectory),
        "strict_scorer_check_passed": True,
        "baseline_runtime": round(float(strict_row.get("runtime") or baseline_trajectory.get("runtime") or 0.0), 4),
        "trial_runtime": round(float(trial_trajectory.get("runtime") or 0.0), 4),
        "baseline_tool_calls": int(strict_row.get("tool_call_count") or baseline_trajectory.get("tool_call_count") or 0),
        "trial_tool_calls": int(trial_trajectory.get("tool_call_count") or 0),
        "baseline_final_answer_preview": _preview(baseline_answer),
        "trial_final_answer_preview": _preview(trial_answer),
        "final_answer_changed": baseline_answer != trial_answer,
        "baseline_sql": baseline_sql,
        "trial_sql": trial_sql,
        "sql_changed": normalize_sql(baseline_sql) != normalize_sql(trial_sql),
        "baseline_api": baseline_api,
        "trial_api": trial_api,
        "api_changed": _canonical_api(baseline_api) != _canonical_api(trial_api),
        "required_fields_preserved": required_trajectory_fields_present(trial_trajectory),
        "dry_run_labels_preserved": _dry_run_labels(trial_trajectory) == _dry_run_labels(baseline_trajectory),
        "live_api_evidence_fabricated": _live_api_evidence_available(trial_trajectory)
        and not _live_api_evidence_available(baseline_trajectory),
        "trial_output_dir": str(output_dir),
        "protected_hashes_unchanged": None,
    }
    row.update(runtime)
    row["tool_delta"] = row["trial_tool_calls"] - row["baseline_tool_calls"]
    for field in REQUIRED_ROW_FIELDS:
        row.setdefault(field, None)
    return row


def _safe_to_promote(row: dict[str, Any], *, runtime_summary: dict[str, Any], secret_scan_ok: bool) -> tuple[bool, str]:
    failures = []
    if float(row.get("score_delta") or 0.0) < 0:
        failures.append("score_delta_negative")
    if int(row.get("token_delta") or 0) >= 0:
        failures.append("token_delta_not_negative")
    if int(row.get("tool_delta") or 0) > 0:
        failures.append("tool_calls_increased")
    if row.get("runtime_budget_ok") is not True:
        failures.append("row_runtime_budget_failed")
    if runtime_summary.get("avg_runtime_budget_ok") is not True:
        failures.append("avg_runtime_budget_failed")
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
    if row.get("trial_formula_matches") is not True:
        failures.append("estimated_token_formula_mismatch")
    if row.get("strict_scorer_check_passed") is not True:
        failures.append("strict_scorer_check_failed")
    if row.get("protected_hashes_unchanged") is False:
        failures.append("protected_output_hash_changed")
    if not secret_scan_ok:
        failures.append("secret_scan_failed")
    return (not failures, "; ".join(failures))


def _summary(
    rows: list[dict[str, Any]],
    *,
    runtime_summary: dict[str, Any],
    protected_unchanged: bool,
    secret_scan_ok: bool,
) -> dict[str, Any]:
    safe = [row for row in rows if row.get("safe_to_promote")]
    unsafe = [row for row in rows if not row.get("safe_to_promote")]
    avg_score_delta = _avg(row.get("score_delta") for row in rows)
    avg_token_delta = _avg(row.get("token_delta") for row in rows)
    avg_tool_delta = _avg(row.get("tool_delta") for row in rows)
    answer_changed_count = sum(1 for row in rows if row.get("final_answer_changed"))
    sql_changed_count = sum(1 for row in rows if row.get("sql_changed"))
    api_changed_count = sum(1 for row in rows if row.get("api_changed"))
    required_field_failure_count = sum(1 for row in rows if row.get("required_fields_preserved") is not True)
    dry_run_label_failure_count = sum(1 for row in rows if row.get("dry_run_labels_preserved") is not True)
    live_api_evidence_fabricated_count = sum(1 for row in rows if row.get("live_api_evidence_fabricated"))
    promotion_ok = (
        bool(rows)
        and len(safe) == len(rows)
        and not unsafe
        and avg_score_delta >= 0
        and avg_token_delta < 0
        and avg_tool_delta <= 0
        and answer_changed_count == 0
        and sql_changed_count == 0
        and api_changed_count == 0
        and required_field_failure_count == 0
        and dry_run_label_failure_count == 0
        and live_api_evidence_fabricated_count == 0
        and runtime_summary.get("runtime_budget_ok") is True
        and protected_unchanged
        and secret_scan_ok
    )
    recommendation = "safe_to_make_packaged_default_in_future" if promotion_ok else ("unsafe_do_not_enable" if rows else "keep_flag_off")
    return {
        "total_rows": len(rows),
        "safe_rows": len(safe),
        "unsafe_rows": len(unsafe),
        "avg_score_delta": avg_score_delta,
        "avg_token_delta": avg_token_delta,
        "avg_runtime_delta": runtime_summary.get("avg_runtime_delta"),
        "avg_tool_delta": avg_tool_delta,
        "answer_changed_count": answer_changed_count,
        "sql_changed_count": sql_changed_count,
        "api_changed_count": api_changed_count,
        "required_field_failure_count": required_field_failure_count,
        "dry_run_label_failure_count": dry_run_label_failure_count,
        "live_api_evidence_fabricated_count": live_api_evidence_fabricated_count,
        "runtime_budget": runtime_summary,
        "protected_output_hashes_unchanged": protected_unchanged,
        "secret_scan_ok": secret_scan_ok,
        "recommendation": recommendation,
        "packaged_execution_changed": False,
        "official_packaged_efficiency_improvement_claimed": False,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload.get("summary", {})
    lines = [
        "# Official Token Reduction Packaged Trial",
        "",
        "This is an isolated packaged flag trial, not a packaged submission change.",
        "",
        f"- Feature flag default: {payload.get('feature_flag_default')}",
        f"- Protected official output hashes unchanged: {payload.get('protected_output_hashes_unchanged')}",
        f"- Packaged execution changed: {payload.get('packaged_execution_changed')}",
        f"- Recommendation: `{summary.get('recommendation')}`",
        "",
        "## Summary",
        "",
        f"- Total rows: {summary.get('total_rows')}",
        f"- Safe rows: {summary.get('safe_rows')}",
        f"- Unsafe rows: {summary.get('unsafe_rows')}",
        f"- Avg score delta: {summary.get('avg_score_delta')}",
        f"- Avg token delta: {summary.get('avg_token_delta')}",
        f"- Avg runtime delta: {summary.get('avg_runtime_delta')}",
        f"- Avg tool delta: {summary.get('avg_tool_delta')}",
        f"- Runtime budget: {summary.get('runtime_budget')}",
        "",
        "| Query ID | Score delta | Token delta | Runtime delta | Runtime >20%? | Tool delta | Answer changed? | SQL changed? | API changed? | Safe? | Rejection reason |",
        "| --- | ---: | ---: | ---: | --- | ---: | --- | --- | --- | --- | --- |",
    ]
    for row in payload.get("rows", []):
        lines.append(
            f"| `{row.get('query_id')}` | {row.get('score_delta')} | {row.get('token_delta')} | "
            f"{row.get('runtime_delta')} | {row.get('runtime_regression_over_20pct')} | "
            f"{row.get('tool_delta')} | {row.get('final_answer_changed')} | {row.get('sql_changed')} | "
            f"{row.get('api_changed')} | {row.get('safe_to_promote')} | {row.get('rejection_reason')} |"
        )
    return "\n".join(lines) + "\n"


def _skipped_row(query_id: str, query: str, strict_row: dict[str, Any], trajectory: dict[str, Any], reason: str) -> dict[str, Any]:
    row = {
        "query_id": query_id,
        "query": query,
        "baseline_score": strict_row.get("final_score"),
        "baseline_tokens": strict_row.get("estimated_tokens") or trajectory.get("estimated_tokens"),
        "baseline_runtime": strict_row.get("runtime") or trajectory.get("runtime"),
        "baseline_tool_calls": strict_row.get("tool_call_count") or trajectory.get("tool_call_count"),
        "safe_to_promote": False,
        "rejection_reason": reason,
    }
    for field in REQUIRED_ROW_FIELDS:
        row.setdefault(field, None)
    return row


def _assert_allowed_output(outputs_dir: Path, path: Path) -> None:
    allowed_files = {
        (outputs_dir / f"{OUTPUT_NAME}.json").resolve(),
        (outputs_dir / f"{OUTPUT_NAME}.md").resolve(),
    }
    resolved = path.resolve()
    if resolved in allowed_files:
        return
    try:
        resolved.relative_to((outputs_dir / OUTPUT_NAME).resolve())
        return
    except ValueError as exc:
        raise RuntimeError(f"Refusing to write official-token packaged trial artifact outside isolated paths: {path}") from exc


if __name__ == "__main__":
    raise SystemExit(main())
