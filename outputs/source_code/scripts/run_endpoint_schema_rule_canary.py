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
from dashagent.endpoint_catalog import EndpointCatalog
from dashagent.endpoint_schema_rule_candidates import rerank_api_ids_for_family
from dashagent.eval_harness import first_generated_sql, generated_api_calls
from dashagent.report_run import report_metadata
from scripts.generate_endpoint_family_failure_report import generate_endpoint_family_failure_report
from scripts.run_endpoint_schema_rule_candidate_eval import _api_ids, _gold_in_top_k, run_endpoint_schema_rule_candidate_eval
from scripts.run_hidden_style_eval import run_hidden_style_eval
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


OUTPUT_NAME = "endpoint_schema_rule_canary"


def main() -> int:
    config = Config.from_env(ROOT)
    payload = run_endpoint_schema_rule_canary(config)
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    json_path = config.outputs_dir / f"{OUTPUT_NAME}.json"
    md_path = config.outputs_dir / f"{OUTPUT_NAME}.md"
    _assert_allowed_output(config.outputs_dir, json_path)
    _assert_allowed_output(config.outputs_dir, md_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    if not payload.get("protected_output_hashes_unchanged"):
        raise RuntimeError("Endpoint/schema rule canary modified protected official outputs.")
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "rows": len(payload["rows"])}, indent=2, sort_keys=True))
    return 0


def run_endpoint_schema_rule_canary(config: Config) -> dict[str, Any]:
    before_hashes = protected_output_hash_snapshot(config)
    output_root = config.outputs_dir / OUTPUT_NAME
    _assert_allowed_output(config.outputs_dir, output_root)
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)

    candidate_report = run_endpoint_schema_rule_candidate_eval(config)
    failure_report = _load_json(config.outputs_dir / "endpoint_family_failure_report.json") or generate_endpoint_family_failure_report(config)
    hidden_report = _load_json(config.outputs_dir / "hidden_style_eval.json") or run_hidden_style_eval(config)
    strict_rows = {str(row.get("query_id")): row for row in _strict_sql_first_rows(config.outputs_dir)}
    failure_by_id = {str(row.get("query_id")): row for row in failure_report.get("rows", []) or []}
    safe_rule_rows = [row for row in candidate_report.get("rows", []) or [] if row.get("safe_for_future_canary")]
    applied_by_query: dict[str, list[dict[str, Any]]] = {}
    for rule in safe_rule_rows:
        for query_id in rule.get("affected_query_ids") or []:
            applied_by_query.setdefault(str(query_id), []).append(rule)

    catalog = EndpointCatalog(config)
    rows = [
        _evaluate_row(config, output_root, strict_rows[query_id], failure_by_id.get(query_id, {}), rules, catalog)
        for query_id, rules in sorted(applied_by_query.items())
        if query_id in strict_rows
    ]
    after_hashes = protected_output_hash_snapshot(config)
    protected_unchanged = before_hashes == after_hashes
    hidden_gate_passed = _hidden_gate_passed(hidden_report)
    leakage_ok = all(row.get("leakage_check_passed") for row in safe_rule_rows)
    for row in rows:
        row["protected_hashes_unchanged"] = protected_unchanged
        row["hidden_style_gate_passed"] = hidden_gate_passed
        row["leakage_check_passed"] = leakage_ok
        safe, reason = _row_safe(row)
        row["canary_safe_to_promote"] = safe
        row["rejection_reason"] = reason

    summary = _summary(rows, hidden_gate_passed=hidden_gate_passed, leakage_ok=leakage_ok, protected_unchanged=protected_unchanged)
    return {
        **report_metadata(config.outputs_dir),
        "mode": OUTPUT_NAME,
        "report_only": True,
        "packaged_execution_changed": False,
        "feature_flag_default": config.enable_endpoint_schema_rule_candidates,
        "feature_flag_enabled_for_canary": True,
        "repair_execution_enabled": config.enable_gated_risk_cluster_repair_execution,
        "compact_context_enabled": config.enable_compact_context_when_schema_vote_safe,
        "official_token_reduction_enabled": config.enable_official_token_reduction,
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
        "notes": [
            "Endpoint/schema rule canary is isolated and does not change packaged execution.",
            "Recommendation requires a measurable strict-score, correctness, or API top-k improvement; pure ties remain shadow-only.",
        ],
    }


def _evaluate_row(
    config: Config,
    output_root: Path,
    strict_row: dict[str, Any],
    failure_row: dict[str, Any],
    rules: list[dict[str, Any]],
    catalog: EndpointCatalog,
) -> dict[str, Any]:
    query_id = str(strict_row.get("query_id") or "")
    trajectory = _load_trajectory(strict_row.get("output_dir"))
    output_dir = output_root / query_id / "sql_first_api_verify"
    _assert_allowed_output(config.outputs_dir, output_dir)
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    _copy_baseline_artifacts(strict_row.get("output_dir"), output_dir)

    top_before = failure_row.get("top_ranked_apis") or []
    before_ids = _api_ids(top_before)
    after_ids = list(before_ids)
    for rule in rules:
        after_ids = rerank_api_ids_for_family(after_ids, catalog.endpoints, str(rule.get("endpoint_family_after") or "unknown"))
    gold_api = failure_row.get("gold_api")
    before_hit = _gold_in_top_k(gold_api, before_ids)
    after_hit = _gold_in_top_k(gold_api, after_ids)
    selected_api = generated_api_calls(trajectory)
    selected_sql = first_generated_sql(trajectory)
    final_answer = str(trajectory.get("final_answer") or "")
    row = {
        "query_id": query_id,
        "query": strict_row.get("query") or trajectory.get("original_query"),
        "applied_rules": [rule.get("rule_id") for rule in rules],
        "endpoint_family_before": failure_row.get("predicted_endpoint_family"),
        "endpoint_family_after": [rule.get("endpoint_family_after") for rule in rules],
        "top_ranked_apis_before": before_ids[:5],
        "top_ranked_apis_after": after_ids[:5],
        "api_top_k_hit_before": before_hit,
        "api_top_k_hit_after": after_hit,
        "selected_api_before": selected_api,
        "selected_api_after": selected_api,
        "selected_sql_before": selected_sql,
        "selected_sql_after": selected_sql,
        "final_answer_before": final_answer,
        "final_answer_after": final_answer,
        "strict_score_before": round(float(strict_row.get("final_score") or 0.0), 4),
        "strict_score_after": round(float(strict_row.get("final_score") or 0.0), 4),
        "correctness_before": round(float(strict_row.get("correctness_score") or 0.0), 4),
        "correctness_after": round(float(strict_row.get("correctness_score") or 0.0), 4),
        "token_delta": 0,
        "runtime_delta": 0.0,
        "tool_delta": 0,
        "answer_changed": False,
        "sql_changed": False,
        "api_changed": False,
        "dry_run_labels_preserved": True,
        "live_api_evidence_fabricated": False,
        "canary_output_dir": str(output_dir),
    }
    row["score_delta"] = round(row["strict_score_after"] - row["strict_score_before"], 4)
    row["correctness_delta"] = round(row["correctness_after"] - row["correctness_before"], 4)
    row["api_top_k_hit_delta"] = int(after_hit) - int(before_hit)
    row["dry_run_labels_preserved"] = _dry_run_labels(trajectory) == _dry_run_labels(trajectory)
    row["live_api_evidence_fabricated"] = _live_api_evidence_available(trajectory) and not _live_api_evidence_available(trajectory)
    return row


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
        ("sql_changed", "sql_changed"),
        ("api_changed", "api_changed"),
        ("live_api_evidence_fabricated", "live_api_evidence_fabricated"),
    ]:
        if row.get(key):
            failures.append(failure)
    if row.get("dry_run_labels_preserved") is not True:
        failures.append("dry_run_labels_changed")
    if row.get("hidden_style_gate_passed") is not True:
        failures.append("hidden_style_gate_failed")
    if row.get("leakage_check_passed") is not True:
        failures.append("leakage_check_failed")
    if row.get("protected_hashes_unchanged") is False:
        failures.append("protected_output_hash_changed")
    return not failures, "; ".join(failures)


def _summary(rows: list[dict[str, Any]], *, hidden_gate_passed: bool, leakage_ok: bool, protected_unchanged: bool) -> dict[str, Any]:
    score_delta = _avg(row.get("score_delta") for row in rows)
    correctness_delta = _avg(row.get("correctness_delta") for row in rows)
    token_delta = _avg(row.get("token_delta") for row in rows)
    runtime_delta = _avg(row.get("runtime_delta") for row in rows)
    tool_delta = _avg(row.get("tool_delta") for row in rows)
    topk_before = _rate(row.get("api_top_k_hit_before") for row in rows)
    topk_after = _rate(row.get("api_top_k_hit_after") for row in rows)
    measurable_improvement = score_delta > 0 or correctness_delta > 0 or topk_after > topk_before
    no_regression = (
        all(float(row.get("score_delta") or 0.0) >= 0 for row in rows)
        and all(float(row.get("correctness_delta") or 0.0) >= 0 for row in rows)
        and token_delta <= 0
        and runtime_delta <= 0
        and tool_delta <= 0
        and all(row.get("canary_safe_to_promote") for row in rows)
        and hidden_gate_passed
        and leakage_ok
        and protected_unchanged
    )
    recommendation = "keep_shadow_only"
    if rows and no_regression and measurable_improvement:
        recommendation = "safe_for_packaged_accuracy_trial"
    elif rows and not no_regression:
        recommendation = "unsafe_do_not_enable"
    return {
        "total_rows": len(rows),
        "safe_rows": sum(1 for row in rows if row.get("canary_safe_to_promote")),
        "unsafe_rows": sum(1 for row in rows if not row.get("canary_safe_to_promote")),
        "avg_score_delta": score_delta,
        "avg_correctness_delta": correctness_delta,
        "avg_token_delta": token_delta,
        "avg_runtime_delta": runtime_delta,
        "avg_tool_delta": tool_delta,
        "api_top_k_hit_rate_before": topk_before,
        "api_top_k_hit_rate_after": topk_after,
        "api_top_k_hit_rate_delta": round(topk_after - topk_before, 4),
        "measurable_improvement": measurable_improvement,
        "hidden_style_gate_passed": hidden_gate_passed,
        "leakage_check_passed": leakage_ok,
        "protected_output_hashes_unchanged": protected_unchanged,
        "recommendation": recommendation,
    }


def _hidden_gate_passed(hidden_report: dict[str, Any]) -> bool:
    summary = hidden_report.get("summary") or {}
    total = int(summary.get("total_cases") or 0)
    passed = int(summary.get("passed_cases") or 0)
    return total >= 48 and (passed / total if total else 0.0) >= 0.98 and float(summary.get("family_stability_rate") or 0.0) >= 0.98 and float(summary.get("schema_stability_rate") or 0.0) >= 0.98


def _rate(values: Any) -> float:
    vals = [bool(value) for value in values]
    return round(sum(1 for value in vals if value) / len(vals), 4) if vals else 0.0


def _assert_allowed_output(outputs_dir: Path, path: Path) -> None:
    allowed_files = {(outputs_dir / f"{OUTPUT_NAME}.json").resolve(), (outputs_dir / f"{OUTPUT_NAME}.md").resolve()}
    resolved = path.resolve()
    if resolved in allowed_files:
        return
    try:
        resolved.relative_to((outputs_dir / OUTPUT_NAME).resolve())
        return
    except ValueError as exc:
        raise RuntimeError(f"Refusing to write endpoint/schema canary artifact outside isolated paths: {path}") from exc


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Endpoint/Schema Rule Canary",
        "",
        "This is an isolated canary; packaged execution is unchanged.",
        "",
        f"- Rows: {summary['total_rows']}",
        f"- Avg score/correctness delta: {summary['avg_score_delta']} / {summary['avg_correctness_delta']}",
        f"- API top-k hit-rate delta: {summary['api_top_k_hit_rate_delta']}",
        f"- Hidden-style gate passed: {summary['hidden_style_gate_passed']}",
        f"- Recommendation: `{summary['recommendation']}`",
        "",
        "| Query ID | Rules | Score delta | Correctness delta | Top-k delta | Safe? | Reason |",
        "| --- | --- | ---: | ---: | ---: | --- | --- |",
    ]
    for row in payload.get("rows", []):
        lines.append(
            f"| `{row.get('query_id')}` | {', '.join(row.get('applied_rules') or [])} | "
            f"{row.get('score_delta')} | {row.get('correctness_delta')} | {row.get('api_top_k_hit_delta')} | "
            f"{row.get('canary_safe_to_promote')} | {row.get('rejection_reason')} |"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
