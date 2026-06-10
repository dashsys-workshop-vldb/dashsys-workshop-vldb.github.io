#!/usr/bin/env python
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.trajectory import estimate_tokens
from scripts.robustness_improvement_common import excerpt, load_json, now_iso, write_report


REPORT_STEM = "strict_efficiency_component_analysis"
STRATEGY = "SQL_FIRST_API_VERIFY"
NON_REGRESSION_REFERENCE = 0.6553


def main() -> int:
    report = run_strict_efficiency_component_analysis(Config.from_env(ROOT))
    print(
        json.dumps(
            {
                "report": REPORT_STEM,
                "current_strict_score": report["summary"]["current_strict_score"],
                "score_gap": report["summary"]["score_gap_vs_reference"],
                "primary_source": report["summary"]["primary_efficiency_source"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def run_strict_efficiency_component_analysis(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    strict = load_json(config.outputs_dir / "eval_results_strict.json")
    drift = load_json(config.outputs_dir / "reports" / "strict_score_drift_analysis.json")
    current_rows = [row for row in strict.get("rows", []) if row.get("strategy") == STRATEGY]
    drift_by_id = {row.get("query_id"): row for row in drift.get("rows", []) if isinstance(row, dict)}
    rows = [_analyze_row(config, row, drift_by_id.get(row.get("query_id")) or {}) for row in current_rows]
    metrics = (
        strict.get("summary", {})
        .get("by_strategy", {})
        .get(STRATEGY, {})
    )
    baseline = (drift.get("score_states", {}) or {}).get("pre_live_previous_packaged_baseline", {})
    score_gap = round(float(metrics.get("avg_final_score") or 0.0) - NON_REGRESSION_REFERENCE, 4)
    token_overhead = _delta(metrics.get("avg_estimated_tokens"), baseline.get("estimated_tokens"))
    runtime_overhead = _delta(metrics.get("avg_runtime"), baseline.get("runtime"))
    tool_overhead = _delta(metrics.get("avg_tool_call_count"), baseline.get("tool_call_count"))
    correctness_delta = _delta(metrics.get("avg_correctness_score"), baseline.get("correctness_score"))
    token_penalty = round(0.1 * max(0.0, token_overhead) / 12000, 4) if token_overhead is not None else None
    runtime_penalty = round(0.1 * max(0.0, runtime_overhead) / 30, 4) if runtime_overhead is not None else None
    tool_penalty = round(0.1 * max(0.0, tool_overhead) / 8, 4) if tool_overhead is not None else None
    source_counts: dict[str, int] = {}
    for row in rows:
        source = str(row.get("likely_efficiency_penalty_source") or "no_clear_efficiency_source")
        source_counts[source] = source_counts.get(source, 0) + 1
    primary_source = max(source_counts, key=source_counts.get) if source_counts else "no_clear_efficiency_source"
    report = {
        "report_type": REPORT_STEM,
        "generated_at": now_iso(),
        "diagnostic_only": True,
        "runtime_change_applied": False,
        "official_score_claim": False,
        "promotion_allowed": False,
        "strategy": STRATEGY,
        "non_regression_reference": NON_REGRESSION_REFERENCE,
        "summary": {
            "row_count": len(rows),
            "current_strict_score": metrics.get("avg_final_score"),
            "score_gap_vs_reference": score_gap,
            "current_correctness_score": metrics.get("avg_correctness_score"),
            "baseline_correctness_score": baseline.get("correctness_score"),
            "correctness_delta_vs_baseline": correctness_delta,
            "avg_token_overhead_vs_baseline": token_overhead,
            "avg_runtime_overhead_vs_baseline": runtime_overhead,
            "avg_tool_overhead_vs_baseline": tool_overhead,
            "score_gap_attributable_to_token_overhead": token_penalty,
            "score_gap_attributable_to_runtime_overhead": runtime_penalty,
            "score_gap_attributable_to_tool_count": tool_penalty,
            "score_gap_attributable_to_answer_or_correctness_drift": round(-0.1 * min(0.0, correctness_delta or 0.0), 4),
            "primary_efficiency_source": primary_source,
            "efficiency_source_counts": source_counts,
        },
        "top_10_rows_by_token_overhead": sorted(rows, key=lambda row: float(row.get("token_count_delta") or 0.0), reverse=True)[:10],
        "top_10_rows_by_runtime_overhead": sorted(rows, key=lambda row: float(row.get("runtime_delta") or 0.0), reverse=True)[:10],
        "safest_efficiency_recovery_candidates": _candidate_recommendations(rows, score_gap),
        "rows": rows,
    }
    write_report(config, REPORT_STEM, report, _render_md(report))
    return report


def _analyze_row(config: Config, current: dict[str, Any], old: dict[str, Any]) -> dict[str, Any]:
    query_id = str(current.get("query_id") or old.get("query_id") or "")
    trajectory = _load_trajectory(config, current)
    step_tokens = _step_token_breakdown(trajectory)
    timings = trajectory.get("timings") if isinstance(trajectory.get("timings"), dict) else {}
    runtime_stage = _runtime_stage(current, timings)
    endpoint_info = _endpoint_info(trajectory)
    token_delta = _delta(current.get("estimated_tokens"), old.get("old_estimated_tokens"))
    runtime_delta = _delta(current.get("runtime"), old.get("old_runtime"))
    tool_delta = _delta(current.get("tool_call_count"), old.get("old_tool_call_count"))
    source = _penalty_source(step_tokens, runtime_stage, token_delta, runtime_delta, endpoint_info)
    return {
        "query_id": query_id,
        "prompt": current.get("query") or old.get("prompt"),
        "strict_score_previous": old.get("old_final_score"),
        "strict_score_current": current.get("final_score"),
        "strict_score_delta": _delta(current.get("final_score"), old.get("old_final_score")),
        "correctness_previous": old.get("old_correctness_score"),
        "correctness_current": current.get("correctness_score"),
        "correctness_delta": _delta(current.get("correctness_score"), old.get("old_correctness_score")),
        "answer_score_previous": old.get("old_answer_score"),
        "answer_score_current": current.get("answer_score"),
        "answer_score_delta": _delta(current.get("answer_score"), old.get("old_answer_score")),
        "sql_score_previous": old.get("old_sql_score"),
        "sql_score_current": current.get("sql_score"),
        "sql_score_delta": _delta(current.get("sql_score"), old.get("old_sql_score")),
        "api_score_previous": old.get("old_api_score"),
        "api_score_current": current.get("api_score"),
        "api_score_delta": _delta(current.get("api_score"), old.get("old_api_score")),
        "tool_count_previous": old.get("old_tool_call_count"),
        "tool_count_current": current.get("tool_call_count"),
        "tool_count_delta": tool_delta,
        "token_count_previous": old.get("old_estimated_tokens"),
        "token_count_current": current.get("estimated_tokens"),
        "token_count_delta": token_delta,
        "runtime_previous": old.get("old_runtime"),
        "runtime_current": current.get("runtime"),
        "runtime_delta": runtime_delta,
        "endpoint_used": endpoint_info["endpoints"],
        "api_outcome": endpoint_info["outcomes"],
        "answer_changed": (old.get("old_final_answer") or "") != (trajectory.get("final_answer") or ""),
        "evidence_changed": (old.get("old_sql_api_evidence_summary") or {}) != (old.get("current_sql_api_evidence_summary") or {}),
        "token_heavy_fields": step_tokens[:5],
        "runtime_heavy_stage": runtime_stage,
        "likely_efficiency_penalty_source": source,
    }


def _load_trajectory(config: Config, row: dict[str, Any]) -> dict[str, Any]:
    output_dir = Path(str(row.get("output_dir") or ""))
    path = output_dir / "trajectory.json" if output_dir.is_absolute() else config.project_root / output_dir / "trajectory.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _step_token_breakdown(trajectory: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for index, step in enumerate(trajectory.get("steps") or []):
        if not isinstance(step, dict) or step.get("kind") == "answer_diagnostics":
            continue
        rows.append({"step_index": index, "kind": step.get("kind"), "estimated_tokens": estimate_tokens(step)})
    return sorted(rows, key=lambda row: int(row.get("estimated_tokens") or 0), reverse=True)


def _runtime_stage(row: dict[str, Any], timings: dict[str, Any]) -> str:
    candidates = {
        "preprocessing_time": row.get("preprocessing_time") or timings.get("preprocessing_time"),
        "planning_time": row.get("planning_time") or timings.get("planning_time"),
        "execution_time": row.get("execution_time") or timings.get("execution_time"),
        "answer_time": row.get("answer_time") or timings.get("answer_time"),
    }
    numeric = {key: float(value) for key, value in candidates.items() if isinstance(value, (int, float))}
    return max(numeric, key=numeric.get) if numeric else "unavailable"


def _endpoint_info(trajectory: dict[str, Any]) -> dict[str, Any]:
    endpoints = []
    outcomes = []
    for step in trajectory.get("steps") or []:
        if not isinstance(step, dict) or step.get("kind") != "api_call":
            continue
        endpoints.append(step.get("url"))
        result = step.get("result") or {}
        if result.get("dry_run"):
            outcomes.append("dry_run_unavailable")
        elif result.get("ok") is True and result.get("result_preview") in (None, "", [], {}):
            outcomes.append("live_empty")
        elif result.get("ok") is True:
            outcomes.append("live_success")
        elif result:
            outcomes.append("api_error")
    return {"endpoints": endpoints, "outcomes": outcomes}


def _penalty_source(
    step_tokens: list[dict[str, Any]],
    runtime_stage: str,
    token_delta: float | None,
    runtime_delta: float | None,
    endpoint_info: dict[str, Any],
) -> str:
    if runtime_stage == "execution_time" and endpoint_info.get("endpoints") and (runtime_delta or 0) > 0.05:
        return "live_api_network_latency"
    top_kind = str((step_tokens[0] if step_tokens else {}).get("kind") or "")
    if top_kind == "api_call":
        return "api_raw_preview_tokens"
    if top_kind == "sql_call":
        return "evidencebus_payload_tokens"
    if top_kind in {"route", "nlp", "plan", "optimizer", "metadata"} and (token_delta or 0) > 0:
        return "repeated_metadata_tokens"
    return "no_clear_efficiency_source"


def _candidate_recommendations(rows: list[dict[str, Any]], score_gap: float) -> list[dict[str, Any]]:
    sources: dict[str, int] = {}
    for row in rows:
        source = str(row.get("likely_efficiency_penalty_source") or "no_clear_efficiency_source")
        sources[source] = sources.get(source, 0) + 1
    candidates = []
    for source, count in sorted(sources.items(), key=lambda item: (-item[1], item[0])):
        if source == "api_raw_preview_tokens":
            fix = "compact_api_preview_strict"
        elif source == "repeated_metadata_tokens":
            fix = "compact_repeated_checkpoint_metadata"
        elif source == "live_api_network_latency":
            fix = "live_get_session_reuse"
        elif source == "evidencebus_payload_tokens":
            fix = "evidencebus_projection_for_answer_context"
        else:
            fix = "review_only"
        candidates.append({"source": source, "row_count": count, "candidate_fix": fix, "score_gap_context": score_gap})
    return candidates


def _render_md(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Strict Efficiency Component Analysis",
        "",
        "Diagnostic-only decomposition of the remaining strict non-regression gap.",
        "",
        f"- Current strict score: `{summary.get('current_strict_score')}`",
        f"- Non-regression reference: `{report.get('non_regression_reference')}`",
        f"- Score gap vs reference: `{summary.get('score_gap_vs_reference')}`",
        f"- Correctness delta vs baseline: `{summary.get('correctness_delta_vs_baseline')}`",
        f"- Avg token overhead vs baseline: `{summary.get('avg_token_overhead_vs_baseline')}`",
        f"- Avg runtime overhead vs baseline: `{summary.get('avg_runtime_overhead_vs_baseline')}`",
        f"- Primary efficiency source: `{summary.get('primary_efficiency_source')}`",
        "",
        "## Safest Candidates",
        "",
    ]
    for item in report.get("safest_efficiency_recovery_candidates", []):
        lines.append(f"- `{item['candidate_fix']}` for `{item['source']}` (`{item['row_count']}` rows)")
    lines.extend(["", "## Top Token Rows", ""])
    for row in report.get("top_10_rows_by_token_overhead", [])[:10]:
        lines.append(
            f"- `{row.get('query_id')}` tokens `{row.get('token_count_current')}` delta `{row.get('token_count_delta')}` source `{row.get('likely_efficiency_penalty_source')}`"
        )
    return "\n".join(lines) + "\n"


def _delta(current: Any, previous: Any) -> float | None:
    if not isinstance(current, (int, float)) or not isinstance(previous, (int, float)):
        return None
    return round(float(current) - float(previous), 4)


if __name__ == "__main__":
    raise SystemExit(main())
