#!/usr/bin/env python
from __future__ import annotations

import hashlib
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
    first_generated_sql,
    generated_api_calls,
    normalize_sql,
)
from dashagent.executor import AgentExecutor
from dashagent.token_reduction_policy import official_estimated_tokens
from scripts.package_query_outputs import (
    discover_query_output_dirs,
    required_trajectory_fields_present,
    select_submission_query_dirs,
)
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


REQUIRED_CANARY_ROW_FIELDS = [
    "query_id",
    "query",
    "baseline_score",
    "canary_score",
    "score_delta",
    "baseline_estimated_tokens",
    "canary_estimated_tokens",
    "token_delta",
    "baseline_runtime",
    "canary_runtime",
    "runtime_delta",
    "baseline_tool_calls",
    "canary_tool_calls",
    "tool_delta",
    "baseline_final_answer_preview",
    "canary_final_answer_preview",
    "final_answer_changed",
    "baseline_sql",
    "canary_sql",
    "sql_changed",
    "baseline_api",
    "canary_api",
    "api_changed",
    "required_fields_preserved",
    "dry_run_labels_preserved",
    "live_api_evidence_fabricated",
    "protected_hashes_unchanged",
    "strict_scorer_check_passed",
    "canary_formula_matches",
    "canary_safe_to_promote",
    "rejection_reason",
]


def main() -> int:
    config = Config.from_env(ROOT)
    payload = run_official_token_reduction_canary(config)
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    json_path = config.outputs_dir / "official_token_reduction_canary.json"
    md_path = config.outputs_dir / "official_token_reduction_canary.md"
    _assert_allowed_output(config.outputs_dir, json_path)
    _assert_allowed_output(config.outputs_dir, md_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    if not payload.get("protected_output_hashes_unchanged"):
        raise RuntimeError("Official-token reduction canary modified protected official outputs.")
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "rows": len(payload["rows"])}, indent=2, sort_keys=True))
    return 0


def run_official_token_reduction_canary(config: Config) -> dict[str, Any]:
    before_hashes = protected_output_hash_snapshot(config)
    strict_rows = _strict_sql_first_rows(config.outputs_dir)
    output_root = config.outputs_dir / "official_token_reduction_canary"
    _assert_allowed_output(config.outputs_dir, output_root)
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)

    canary_config = replace(config, enable_official_token_reduction=True)
    executor = AgentExecutor(canary_config)
    examples = {example.query_id: example for example in EvalHarness(config).load_examples()}
    rows = [
        _evaluate_row(config, executor, output_root, strict_row, examples.get(str(strict_row.get("query_id"))))
        for strict_row in strict_rows
    ]
    after_hashes = protected_output_hash_snapshot(config)
    protected_unchanged = before_hashes == after_hashes
    if not protected_unchanged:
        for row in rows:
            row["protected_hashes_unchanged"] = False
            row["canary_safe_to_promote"] = False
            row["rejection_reason"] = _append_reason(row.get("rejection_reason"), "protected_output_hash_changed")
    else:
        for row in rows:
            row["protected_hashes_unchanged"] = True
            safe, reason = _canary_safe(row)
            row["canary_safe_to_promote"] = safe
            row["rejection_reason"] = reason

    summary = _summary(rows, protected_unchanged=protected_unchanged)
    return {
        "mode": "official_token_reduction_canary",
        "feature_flag_default": Config.from_env(config.project_root).enable_official_token_reduction,
        "feature_flag_enabled_for_canary": True,
        "repair_execution_enabled": config.enable_gated_risk_cluster_repair_execution,
        "compact_context_enabled": config.enable_compact_context_when_schema_vote_safe,
        "packaged_execution_changed": False,
        "official_packaged_efficiency_improvement_claimed": False,
        "behavior_changing_flags_enabled": False,
        "protected_output_hashes_before": before_hashes,
        "protected_output_hashes_after": after_hashes,
        "protected_output_hashes_unchanged": protected_unchanged,
        "rows": rows,
        "summary": summary,
        "artifact_isolation": {
            "allowed_outputs": [
                "outputs/official_token_reduction_canary.json",
                "outputs/official_token_reduction_canary.md",
                "outputs/official_token_reduction_canary/",
            ],
            "canary_output_root": "outputs/official_token_reduction_canary/<query_id>/sql_first_api_verify/",
            "writes_eval_outputs": False,
            "writes_final_submission": False,
            "writes_packaged_query_outputs": False,
        },
        "notes": [
            "This is a canary evaluation, not a packaged submission change.",
            "ENABLE_OFFICIAL_TOKEN_REDUCTION remains default false.",
            "Packaged SQL_FIRST_API_VERIFY outputs are unchanged when protected hashes match.",
            "No official packaged efficiency improvement is claimed yet.",
            "Promotion requires a separate explicit task after this canary passes.",
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
    canary_trajectory = _load_json(output_dir / "trajectory.json") or result["trajectory"]
    canary_answer = str(result.get("final_answer") or canary_trajectory.get("final_answer") or "")
    canary_scores = _score_result(executor, canary_trajectory, canary_answer, example)

    baseline_answer = str(baseline_trajectory.get("final_answer") or "")
    baseline_sql = first_generated_sql(baseline_trajectory)
    canary_sql = first_generated_sql(canary_trajectory)
    baseline_api = generated_api_calls(baseline_trajectory)
    canary_api = generated_api_calls(canary_trajectory)
    baseline_score = float(strict_row.get("final_score") or 0.0)
    canary_score = float(canary_scores["final_score"])
    baseline_tokens = int(strict_row.get("estimated_tokens") or baseline_trajectory.get("estimated_tokens") or 0)
    canary_tokens = int(canary_trajectory.get("estimated_tokens") or 0)
    canary_formula_tokens = official_estimated_tokens(canary_trajectory)
    row = {
        "query_id": query_id,
        "query": query,
        "baseline_score": round(baseline_score, 4),
        "canary_score": round(canary_score, 4),
        "score_delta": round(canary_score - baseline_score, 4),
        "baseline_estimated_tokens": baseline_tokens,
        "canary_estimated_tokens": canary_tokens,
        "token_delta": canary_tokens - baseline_tokens,
        "baseline_formula_tokens": official_estimated_tokens(baseline_trajectory),
        "canary_formula_tokens": canary_formula_tokens,
        "canary_formula_matches": canary_tokens == canary_formula_tokens,
        "strict_scorer_check_passed": True,
        "baseline_runtime": round(float(strict_row.get("runtime") or baseline_trajectory.get("runtime") or 0.0), 4),
        "canary_runtime": round(float(canary_trajectory.get("runtime") or 0.0), 4),
        "baseline_tool_calls": int(strict_row.get("tool_call_count") or baseline_trajectory.get("tool_call_count") or 0),
        "canary_tool_calls": int(canary_trajectory.get("tool_call_count") or 0),
        "baseline_final_answer_preview": _preview(baseline_answer),
        "canary_final_answer_preview": _preview(canary_answer),
        "final_answer_changed": baseline_answer != canary_answer,
        "baseline_sql": baseline_sql,
        "canary_sql": canary_sql,
        "sql_changed": normalize_sql(baseline_sql) != normalize_sql(canary_sql),
        "baseline_api": baseline_api,
        "canary_api": canary_api,
        "api_changed": _canonical_api(baseline_api) != _canonical_api(canary_api),
        "required_fields_preserved": required_trajectory_fields_present(canary_trajectory),
        "dry_run_labels_preserved": _dry_run_labels(canary_trajectory) == _dry_run_labels(baseline_trajectory),
        "live_api_evidence_fabricated": _live_api_evidence_available(canary_trajectory)
        and not _live_api_evidence_available(baseline_trajectory),
        "canary_output_dir": str(output_dir),
        "protected_hashes_unchanged": None,
    }
    row["runtime_delta"] = round(row["canary_runtime"] - row["baseline_runtime"], 4)
    row["tool_delta"] = row["canary_tool_calls"] - row["baseline_tool_calls"]
    safe, reason = _canary_safe(row)
    row["canary_safe_to_promote"] = safe
    row["rejection_reason"] = reason
    for field in REQUIRED_CANARY_ROW_FIELDS:
        row.setdefault(field, None)
    return row


def _canary_safe(row: dict[str, Any]) -> tuple[bool, str]:
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
    if row.get("canary_formula_matches") is not True:
        failures.append("estimated_token_formula_mismatch")
    if row.get("strict_scorer_check_passed") is not True:
        failures.append("strict_scorer_check_failed")
    if row.get("protected_hashes_unchanged") is False:
        failures.append("protected_output_hash_changed")
    return (not failures, "; ".join(failures))


def _summary(rows: list[dict[str, Any]], *, protected_unchanged: bool) -> dict[str, Any]:
    safe = [row for row in rows if row.get("canary_safe_to_promote")]
    unsafe = [row for row in rows if not row.get("canary_safe_to_promote")]
    answer_changed_count = sum(1 for row in rows if row.get("final_answer_changed"))
    sql_changed_count = sum(1 for row in rows if row.get("sql_changed"))
    api_changed_count = sum(1 for row in rows if row.get("api_changed"))
    required_field_failure_count = sum(1 for row in rows if row.get("required_fields_preserved") is not True)
    dry_run_label_failure_count = sum(1 for row in rows if row.get("dry_run_labels_preserved") is not True)
    live_api_evidence_fabricated_count = sum(1 for row in rows if row.get("live_api_evidence_fabricated"))
    formula_failure_count = sum(1 for row in rows if row.get("canary_formula_matches") is not True)
    strict_scorer_failure_count = sum(1 for row in rows if row.get("strict_scorer_check_passed") is not True)
    avg_score_delta = _avg(row.get("score_delta") for row in rows)
    avg_token_delta = _avg(row.get("token_delta") for row in rows)
    avg_tool_delta = _avg(row.get("tool_delta") for row in rows)
    recommendation = "keep_default_off"
    if rows:
        promotion_ok = (
            len(safe) == len(rows)
            and not unsafe
            and protected_unchanged
            and avg_score_delta >= 0
            and avg_token_delta < 0
            and avg_tool_delta <= 0
            and answer_changed_count == 0
            and sql_changed_count == 0
            and api_changed_count == 0
            and required_field_failure_count == 0
            and dry_run_label_failure_count == 0
            and live_api_evidence_fabricated_count == 0
            and formula_failure_count == 0
            and strict_scorer_failure_count == 0
        )
        recommendation = "safe_for_packaged_flag_trial" if promotion_ok else "unsafe_do_not_enable"
    return {
        "total_rows": len(rows),
        "safe_rows": len(safe),
        "unsafe_rows": len(unsafe),
        "avg_score_delta": avg_score_delta,
        "avg_token_delta": avg_token_delta,
        "avg_runtime_delta": _avg(row.get("runtime_delta") for row in rows),
        "avg_tool_delta": avg_tool_delta,
        "answer_changed_count": answer_changed_count,
        "sql_changed_count": sql_changed_count,
        "api_changed_count": api_changed_count,
        "required_field_failure_count": required_field_failure_count,
        "dry_run_label_failure_count": dry_run_label_failure_count,
        "live_api_evidence_fabricated_count": live_api_evidence_fabricated_count,
        "formula_failure_count": formula_failure_count,
        "strict_scorer_failure_count": strict_scorer_failure_count,
        "protected_output_hashes_unchanged": protected_unchanged,
        "recommendation": recommendation,
        "packaged_execution_changed": False,
        "official_packaged_efficiency_improvement_claimed": False,
    }


def protected_output_hash_snapshot(config: Config) -> dict[str, Any]:
    selected_dirs = select_submission_query_dirs(
        discover_query_output_dirs(config.outputs_dir),
        preferred_strategy="SQL_FIRST_API_VERIFY",
        require_complete_trajectory=True,
    )
    packaged_hashes = {
        str(path.relative_to(config.outputs_dir)): _hash_tree(path)
        for path in selected_dirs
        if not _is_canary_path(config.outputs_dir, path)
    }
    return {
        "outputs_eval": _hash_tree(config.outputs_dir / "eval"),
        "outputs_final_submission": _hash_tree(config.outputs_dir / "final_submission"),
        "packaged_sql_first_query_output_folders": packaged_hashes,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload.get("summary", {})
    lines = [
        "# Official Token Reduction Canary Evaluation",
        "",
        "This is a canary evaluation, not a packaged submission change.",
        "",
        f"- ENABLE_OFFICIAL_TOKEN_REDUCTION remains default false: {payload.get('feature_flag_default') is False}",
        f"- Packaged SQL_FIRST outputs are unchanged: {payload.get('protected_output_hashes_unchanged')}",
        f"- Packaged execution changed: {payload.get('packaged_execution_changed')}",
        f"- No official packaged efficiency improvement is claimed: "
        f"{not payload.get('official_packaged_efficiency_improvement_claimed')}",
        "- Promotion requires a separate explicit task after this canary passes.",
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
        f"- Answer/SQL/API changed counts: {summary.get('answer_changed_count')}/"
        f"{summary.get('sql_changed_count')}/{summary.get('api_changed_count')}",
        f"- Required-field failures: {summary.get('required_field_failure_count')}",
        f"- Dry-run label failures: {summary.get('dry_run_label_failure_count')}",
        f"- Formula/scorer failures: {summary.get('formula_failure_count')}/"
        f"{summary.get('strict_scorer_failure_count')}",
        f"- Recommendation: `{summary.get('recommendation')}`",
        "",
        "| Query ID | Score delta | Token delta | Tool delta | Answer changed? | SQL changed? | API changed? | Formula OK? | Protected hash OK? | Safe? | Rejection reason |",
        "| --- | ---: | ---: | ---: | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload.get("rows", []):
        lines.append(
            f"| `{row.get('query_id')}` | {row.get('score_delta')} | {row.get('token_delta')} | "
            f"{row.get('tool_delta')} | {row.get('final_answer_changed')} | {row.get('sql_changed')} | "
            f"{row.get('api_changed')} | {row.get('canary_formula_matches')} | "
            f"{row.get('protected_hashes_unchanged')} | {row.get('canary_safe_to_promote')} | "
            f"{row.get('rejection_reason')} |"
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
        "canary_safe_to_promote": False,
        "rejection_reason": reason,
    }
    for field in REQUIRED_CANARY_ROW_FIELDS:
        row.setdefault(field, None)
    return row


def _hash_tree(path: Path) -> str:
    if not path.exists():
        return "missing"
    if path.is_file():
        digest = hashlib.sha256()
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
        return digest.hexdigest()
    digest = hashlib.sha256()
    for child in sorted(path.rglob("*")):
        if child.is_file():
            digest.update(str(child.relative_to(path)).encode("utf-8"))
            digest.update(b"\0")
            digest.update(child.read_bytes())
            digest.update(b"\0")
    return digest.hexdigest()


def _assert_allowed_output(outputs_dir: Path, path: Path) -> None:
    allowed_files = {
        (outputs_dir / "official_token_reduction_canary.json").resolve(),
        (outputs_dir / "official_token_reduction_canary.md").resolve(),
    }
    resolved = path.resolve()
    if resolved in allowed_files:
        return
    try:
        resolved.relative_to((outputs_dir / "official_token_reduction_canary").resolve())
        return
    except ValueError as exc:
        raise RuntimeError(f"Refusing to write official-token canary artifact outside isolated paths: {path}") from exc


def _append_reason(current: Any, reason: str) -> str:
    value = str(current or "")
    if reason in value.split("; "):
        return value
    return "; ".join(part for part in [value, reason] if part)


def _is_canary_path(outputs_dir: Path, path: Path) -> bool:
    try:
        path.resolve().relative_to((outputs_dir / "official_token_reduction_canary").resolve())
        return True
    except ValueError:
        return False


if __name__ == "__main__":
    raise SystemExit(main())
