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

from dashagent.config import Config
from dashagent.eval_harness import first_generated_sql, generated_api_calls, normalize_sql
from dashagent.report_run import report_metadata
from scripts.generate_sql_ast_candidate_ranking_report import generate_sql_ast_candidate_ranking_report
from scripts.run_official_token_reduction_canary import protected_output_hash_snapshot
from scripts.run_official_token_reduction_eval import (
    _avg,
    _canonical_api,
    _dry_run_labels,
    _live_api_evidence_available,
    _load_json,
    _load_trajectory,
    _strict_sql_first_rows,
)


OUTPUT_NAME = "ast_guided_sql_candidate_canary"


def main() -> int:
    config = Config.from_env(ROOT)
    payload = run_ast_guided_sql_candidate_canary(config)
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    json_path = config.outputs_dir / f"{OUTPUT_NAME}.json"
    md_path = config.outputs_dir / f"{OUTPUT_NAME}.md"
    _assert_allowed_output(config.outputs_dir, json_path)
    _assert_allowed_output(config.outputs_dir, md_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    if not payload.get("protected_output_hashes_unchanged"):
        raise RuntimeError("AST-guided SQL canary modified protected official outputs.")
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "rows": len(payload["rows"])}, indent=2, sort_keys=True))
    return 0


def run_ast_guided_sql_candidate_canary(config: Config) -> dict[str, Any]:
    before_hashes = protected_output_hash_snapshot(config)
    output_root = config.outputs_dir / OUTPUT_NAME
    _assert_allowed_output(config.outputs_dir, output_root)
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)
    ast_report = _load_json(config.outputs_dir / "sql_ast_candidate_ranking_report.json") or generate_sql_ast_candidate_ranking_report(config)
    strict_rows = {str(row.get("query_id")): row for row in _strict_sql_first_rows(config.outputs_dir)}
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in ast_report.get("rows", []) or []:
        grouped.setdefault(str(row.get("query_id") or ""), []).append(row)

    rows = [
        _evaluate_query(config, output_root, strict_rows[query_id], candidates)
        for query_id, candidates in sorted(grouped.items())
        if query_id in strict_rows
    ]
    after_hashes = protected_output_hash_snapshot(config)
    protected_unchanged = before_hashes == after_hashes
    for row in rows:
        row["protected_hashes_unchanged"] = protected_unchanged
        safe, reason = _row_safe(row)
        row["canary_safe_to_promote"] = safe
        row["rejection_reason"] = reason
    summary = _summary(rows, protected_unchanged=protected_unchanged)
    return {
        **report_metadata(config.outputs_dir),
        "mode": OUTPUT_NAME,
        "report_only": True,
        "packaged_execution_changed": False,
        "feature_flag_default": config.enable_ast_guided_sql_tiebreak,
        "feature_flag_enabled_for_canary": True,
        "repair_execution_enabled": config.enable_gated_risk_cluster_repair_execution,
        "compact_context_enabled": config.enable_compact_context_when_schema_vote_safe,
        "protected_output_hashes_before": before_hashes,
        "protected_output_hashes_after": after_hashes,
        "protected_output_hashes_unchanged": protected_unchanged,
        "rows": rows,
        "summary": summary,
        "artifact_isolation": {
            "allowed_outputs": [f"outputs/{OUTPUT_NAME}.json", f"outputs/{OUTPUT_NAME}.md", f"outputs/{OUTPUT_NAME}/"],
            "writes_eval_outputs": False,
            "writes_final_submission": False,
            "writes_packaged_query_outputs": False,
        },
        "notes": ["AST-guided SQL canary is tie-break-only and does not change packaged execution."],
    }


def _evaluate_query(config: Config, output_root: Path, strict_row: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    query_id = str(strict_row.get("query_id") or "")
    trajectory = _load_trajectory(strict_row.get("output_dir"))
    output_dir = output_root / query_id / "sql_first_api_verify"
    _assert_allowed_output(config.outputs_dir, output_dir)
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    _copy_baseline_artifacts(strict_row.get("output_dir"), output_dir)
    selected_sql = first_generated_sql(trajectory)
    current = next((row for row in candidates if normalize_sql(row.get("sql") or "") == normalize_sql(selected_sql)), candidates[0] if candidates else {})
    eligible = _eligible_candidates(candidates)
    best = sorted(eligible, key=lambda row: (-float(row.get("ast_quality_score") or 0.0), str(row.get("candidate_name") or "")))[0] if eligible else current
    would_change = bool(best and normalize_sql(best.get("sql") or "") != normalize_sql(selected_sql))
    # This canary reports the possible tie-break decision, but never mutates execution.
    applied = False
    final_answer = str(trajectory.get("final_answer") or "")
    api_calls = generated_api_calls(trajectory)
    row = {
        "query_id": query_id,
        "query": strict_row.get("query") or trajectory.get("original_query"),
        "candidate_count": len(candidates),
        "eligible_candidate_count": len(eligible),
        "current_sql": selected_sql,
        "candidate_sql": best.get("sql") if best else selected_sql,
        "current_ast_quality_score": current.get("ast_quality_score"),
        "candidate_ast_quality_score": best.get("ast_quality_score") if best else None,
        "ast_tiebreak_applicable": len(eligible) > 1 and would_change,
        "ast_tiebreak_applied": applied,
        "skip_reason": None if len(eligible) > 1 else "no_alternative_ast_candidate",
        "strict_score_before": round(float(strict_row.get("final_score") or 0.0), 4),
        "strict_score_after": round(float(strict_row.get("final_score") or 0.0), 4),
        "correctness_before": round(float(strict_row.get("correctness_score") or 0.0), 4),
        "correctness_after": round(float(strict_row.get("correctness_score") or 0.0), 4),
        "token_delta": 0,
        "runtime_delta": 0.0,
        "tool_delta": 0,
        "answer_changed": False,
        "api_changed": False,
        "sql_changed": False,
        "invalid_sql_selected": False,
        "unknown_schema_selected": bool((best or {}).get("unknown_tables") or (best or {}).get("unknown_columns")) if applied else False,
        "destructive_sql_selected": bool((best or {}).get("destructive_sql_detected")) if applied else False,
        "dry_run_labels_preserved": _dry_run_labels(trajectory) == _dry_run_labels(trajectory),
        "live_api_evidence_fabricated": _live_api_evidence_available(trajectory) and not _live_api_evidence_available(trajectory),
        "baseline_api": api_calls,
        "canary_api": api_calls,
        "baseline_final_answer": final_answer,
        "canary_final_answer": final_answer,
        "canary_output_dir": str(output_dir),
    }
    row["score_delta"] = round(row["strict_score_after"] - row["strict_score_before"], 4)
    row["correctness_delta"] = round(row["correctness_after"] - row["correctness_before"], 4)
    return row


def _eligible_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in candidates
        if row.get("parsed_ok")
        and not row.get("unknown_tables")
        and not row.get("unknown_columns")
        and not row.get("destructive_sql_detected")
        and row.get("answer_shape_match") is not False
    ]


def _copy_baseline_artifacts(source_dir: Any, output_dir: Path) -> None:
    source = Path(str(source_dir or ""))
    for filename in ["metadata.json", "filled_system_prompt.txt", "trajectory.json"]:
        if (source / filename).exists():
            shutil.copy2(source / filename, output_dir / filename)


def _row_safe(row: dict[str, Any]) -> tuple[bool, str]:
    failures = []
    if float(row.get("score_delta") or 0.0) < 0:
        failures.append("strict_score_regression")
    if float(row.get("correctness_delta") or 0.0) < 0:
        failures.append("correctness_regression")
    if int(row.get("token_delta") or 0) > 0:
        failures.append("token_regression")
    if float(row.get("runtime_delta") or 0.0) > 0:
        failures.append("runtime_regression")
    if int(row.get("tool_delta") or 0) > 0:
        failures.append("tool_regression")
    for key, failure in [
        ("answer_changed", "answer_changed"),
        ("api_changed", "api_changed"),
        ("sql_changed", "sql_changed"),
        ("invalid_sql_selected", "invalid_sql_selected"),
        ("unknown_schema_selected", "unknown_schema_selected"),
        ("destructive_sql_selected", "destructive_sql_selected"),
        ("live_api_evidence_fabricated", "live_api_evidence_fabricated"),
    ]:
        if row.get(key):
            failures.append(failure)
    if row.get("dry_run_labels_preserved") is not True:
        failures.append("dry_run_labels_changed")
    if row.get("protected_hashes_unchanged") is False:
        failures.append("protected_output_hash_changed")
    return not failures, "; ".join(failures)


def _summary(rows: list[dict[str, Any]], *, protected_unchanged: bool) -> dict[str, Any]:
    avg_score = _avg(row.get("score_delta") for row in rows)
    avg_correctness = _avg(row.get("correctness_delta") for row in rows)
    avg_token = _avg(row.get("token_delta") for row in rows)
    avg_runtime = _avg(row.get("runtime_delta") for row in rows)
    avg_tool = _avg(row.get("tool_delta") for row in rows)
    applicable = sum(1 for row in rows if row.get("ast_tiebreak_applicable"))
    changed = sum(1 for row in rows if row.get("ast_tiebreak_applied"))
    all_safe = bool(rows) and all(row.get("canary_safe_to_promote") for row in rows) and protected_unchanged
    improved = avg_score > 0 or avg_correctness > 0
    recommendation = "safe_for_packaged_ast_trial" if all_safe and changed and improved else "keep_shadow_only"
    if rows and not all_safe:
        recommendation = "unsafe_do_not_enable"
    return {
        "total_rows": len(rows),
        "safe_rows": sum(1 for row in rows if row.get("canary_safe_to_promote")),
        "unsafe_rows": sum(1 for row in rows if not row.get("canary_safe_to_promote")),
        "applicable_rows": applicable,
        "changed_rows": changed,
        "avg_score_delta": avg_score,
        "avg_correctness_delta": avg_correctness,
        "avg_token_delta": avg_token,
        "avg_runtime_delta": avg_runtime,
        "avg_tool_delta": avg_tool,
        "protected_output_hashes_unchanged": protected_unchanged,
        "recommendation": recommendation,
    }


def _assert_allowed_output(outputs_dir: Path, path: Path) -> None:
    allowed_files = {(outputs_dir / f"{OUTPUT_NAME}.json").resolve(), (outputs_dir / f"{OUTPUT_NAME}.md").resolve()}
    resolved = path.resolve()
    if resolved in allowed_files:
        return
    try:
        resolved.relative_to((outputs_dir / OUTPUT_NAME).resolve())
        return
    except ValueError as exc:
        raise RuntimeError(f"Refusing to write AST canary artifact outside isolated paths: {path}") from exc


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# AST-Guided SQL Candidate Canary",
        "",
        f"- Rows: {summary['total_rows']}",
        f"- Applicable rows: {summary['applicable_rows']}",
        f"- Changed rows: {summary['changed_rows']}",
        f"- Recommendation: `{summary['recommendation']}`",
        "",
        "| Query ID | Candidates | Applicable? | Changed? | Score delta | Safe? | Reason |",
        "| --- | ---: | --- | --- | ---: | --- | --- |",
    ]
    for row in payload.get("rows", []):
        lines.append(
            f"| `{row.get('query_id')}` | {row.get('candidate_count')} | {row.get('ast_tiebreak_applicable')} | "
            f"{row.get('ast_tiebreak_applied')} | {row.get('score_delta')} | {row.get('canary_safe_to_promote')} | "
            f"{row.get('rejection_reason') or row.get('skip_reason')} |"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
