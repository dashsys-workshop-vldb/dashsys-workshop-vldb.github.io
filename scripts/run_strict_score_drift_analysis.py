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
from dashagent.eval_harness import first_generated_sql, generated_api_calls
from scripts.robustness_improvement_common import excerpt, load_json, now_iso, write_report


REPORT_STEM = "strict_score_drift_analysis"
STRATEGY = "SQL_FIRST_API_VERIFY"
NON_REGRESSION_REFERENCE = 0.6553


def main() -> int:
    config = Config.from_env(ROOT)
    report = run_strict_score_drift_analysis(config)
    print(
        json.dumps(
            {
                "report": REPORT_STEM,
                "current_strict_score": report["score_states"]["current_fresh_strict"]["strict_score"],
                "likely_root_cause": report["root_cause_summary"]["primary_root_cause"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def run_strict_score_drift_analysis(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    current = load_json(config.outputs_dir / "eval_results_strict.json")
    pre_live = load_json(config.outputs_dir / "reports" / "baselines" / "pre_live_api_eval_results_strict.json")
    live_delta = load_json(config.outputs_dir / "reports" / "live_api_strict_eval_delta.json")
    arbitration = load_json(config.outputs_dir / "reports" / "live_api_evidence_arbitration_trial.json")

    current_rows = _strategy_rows(current)
    baseline_rows = _strategy_rows(pre_live)
    baseline_by_id = {row.get("query_id"): row for row in baseline_rows}
    rows = [_compare_row(config, baseline_by_id.get(row.get("query_id")) or {}, row) for row in current_rows]
    helped = [row for row in rows if _num(row.get("score_delta")) and _num(row.get("score_delta")) > 0]
    hurt = [row for row in rows if _num(row.get("score_delta")) and _num(row.get("score_delta")) < 0]
    unchanged = [row for row in rows if _num(row.get("score_delta")) == 0]
    current_metrics = _strategy_metrics(current)
    baseline_metrics = _strategy_metrics(pre_live)
    score_states = {
        "pre_live_previous_packaged_baseline": {
            "strict_score": baseline_metrics.get("avg_final_score"),
            "correctness_score": baseline_metrics.get("avg_correctness_score"),
            "answer_score": baseline_metrics.get("avg_answer_score"),
            "sql_score": baseline_metrics.get("avg_sql_score"),
            "api_score": baseline_metrics.get("avg_api_score"),
            "runtime": baseline_metrics.get("avg_runtime"),
            "estimated_tokens": baseline_metrics.get("avg_estimated_tokens"),
            "tool_call_count": baseline_metrics.get("avg_tool_call_count"),
        },
        "post_live_arbitration_recovered_reference": {
            "strict_score": _arbitration_reference(arbitration, live_delta),
            "source": _arbitration_source(arbitration, live_delta),
        },
        "current_fresh_strict": {
            "strict_score": current_metrics.get("avg_final_score"),
            "correctness_score": current_metrics.get("avg_correctness_score"),
            "answer_score": current_metrics.get("avg_answer_score"),
            "sql_score": current_metrics.get("avg_sql_score"),
            "api_score": current_metrics.get("avg_api_score"),
            "runtime": current_metrics.get("avg_runtime"),
            "estimated_tokens": current_metrics.get("avg_estimated_tokens"),
            "tool_call_count": current_metrics.get("avg_tool_call_count"),
        },
    }
    root_cause = _root_cause(score_states, rows)
    payload: dict[str, Any] = {
        "report_type": REPORT_STEM,
        "generated_at": now_iso(),
        "diagnostic_only": True,
        "official_score_claim": False,
        "runtime_change_applied": False,
        "promotion_allowed": False,
        "strategy": STRATEGY,
        "non_regression_reference": NON_REGRESSION_REFERENCE,
        "score_states": score_states,
        "summary": {
            "row_count": len(rows),
            "rows_helped": len(helped),
            "rows_hurt": len(hurt),
            "rows_unchanged": len(unchanged),
            "top_negative_deltas": sorted(hurt, key=lambda row: float(row.get("score_delta") or 0.0))[:10],
        },
        "root_cause_summary": root_cause,
        "rows": rows,
        "interpretation": (
            "The current strict score is below the non-regression reference. The row-level comparison separates "
            "correctness drift from efficiency drift so runtime changes are not made before the failure mode is known."
        ),
    }
    write_report(config, REPORT_STEM, payload, _render_md(payload))
    return payload


def _strategy_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
    return [row for row in rows if isinstance(row, dict) and row.get("strategy") == STRATEGY]


def _strategy_metrics(payload: dict[str, Any]) -> dict[str, Any]:
    return (
        payload.get("summary", {})
        .get("by_strategy", {})
        .get(STRATEGY, {})
    )


def _compare_row(config: Config, old: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    query_id = str(current.get("query_id") or old.get("query_id") or "")
    old_traj = _load_baseline_trajectory(config, query_id)
    current_traj = _load_current_trajectory(config, query_id, current)
    old_sql = first_generated_sql(old_traj)
    current_sql = first_generated_sql(current_traj)
    old_api = generated_api_calls(old_traj)
    current_api = generated_api_calls(current_traj)
    old_evidence = _evidence_summary(old_traj)
    current_evidence = _evidence_summary(current_traj)
    changed = {
        "routing_changed": (old_traj.get("route_type") != current_traj.get("route_type")) if old_traj and current_traj else "unavailable",
        "sql_changed": old_sql != current_sql,
        "api_endpoint_changed": _api_paths(old_api) != _api_paths(current_api),
        "evidencebus_changed": old_evidence != current_evidence,
        "answer_wording_changed": old_traj.get("final_answer") != current_traj.get("final_answer"),
        "arbitration_behavior_changed": _checkpoint_digest(old_traj, "answer selection") != _checkpoint_digest(current_traj, "answer selection"),
        "live_api_evidence_changed": _api_outcomes(old_traj) != _api_outcomes(current_traj),
        "token_or_runtime_changed": old.get("runtime") != current.get("runtime") or old.get("estimated_tokens") != current.get("estimated_tokens"),
    }
    score_delta = _delta(current.get("final_score"), old.get("final_score"))
    return {
        "query_id": query_id,
        "prompt": current.get("query") or old.get("query"),
        "old_final_answer": excerpt(old_traj.get("final_answer")),
        "current_final_answer": excerpt(current_traj.get("final_answer")),
        "old_sql_api_evidence_summary": old_evidence,
        "current_sql_api_evidence_summary": current_evidence,
        "old_answer_score": old.get("answer_score"),
        "current_answer_score": current.get("answer_score"),
        "old_sql_score": old.get("sql_score"),
        "current_sql_score": current.get("sql_score"),
        "old_api_score": old.get("api_score"),
        "current_api_score": current.get("api_score"),
        "old_final_score": old.get("final_score"),
        "current_final_score": current.get("final_score"),
        "old_correctness_score": old.get("correctness_score"),
        "current_correctness_score": current.get("correctness_score"),
        "old_runtime": old.get("runtime"),
        "current_runtime": current.get("runtime"),
        "old_estimated_tokens": old.get("estimated_tokens"),
        "current_estimated_tokens": current.get("estimated_tokens"),
        "score_delta": score_delta,
        "changed_fields": changed,
        "likely_drift_category": _drift_category(old, current, changed),
    }


def _load_baseline_trajectory(config: Config, query_id: str) -> dict[str, Any]:
    path = config.outputs_dir / "official_token_reduction_canary" / query_id / "sql_first_api_verify" / "trajectory.json"
    return load_json(path)


def _load_current_trajectory(config: Config, query_id: str, row: dict[str, Any]) -> dict[str, Any]:
    row_path = Path(str(row.get("output_dir") or ""))
    if row_path.is_absolute():
        path = row_path / "trajectory.json"
    else:
        path = config.project_root / row_path / "trajectory.json"
    if path.exists():
        return load_json(path)
    return load_json(config.outputs_dir / "eval" / query_id / "sql_first_api_verify" / "trajectory.json")


def _evidence_summary(trajectory: dict[str, Any]) -> dict[str, Any]:
    return {
        "route_type": trajectory.get("route_type"),
        "domain_type": trajectory.get("domain_type"),
        "sql": excerpt(first_generated_sql(trajectory), 180),
        "api_calls": generated_api_calls(trajectory),
        "api_outcomes": _api_outcomes(trajectory),
        "evidence_bus": _checkpoint_digest(trajectory, "evidence forwarding"),
        "answer_slots": _checkpoint_digest(trajectory, "answer synthesis"),
    }


def _checkpoint_digest(trajectory: dict[str, Any], stage: str) -> Any:
    for checkpoint in trajectory.get("checkpoints") or []:
        if checkpoint.get("stage") == stage:
            output = checkpoint.get("output")
            return output if isinstance(output, dict) else output
    return None


def _api_outcomes(trajectory: dict[str, Any]) -> list[str]:
    outcomes: list[str] = []
    for step in trajectory.get("steps") or []:
        if step.get("kind") != "api_call":
            continue
        result = step.get("result") or {}
        preview = result.get("preview")
        text = json.dumps(preview, sort_keys=True, default=str) if isinstance(preview, (dict, list)) else str(preview or "")
        lower = text.lower()
        if "live_success" in lower:
            outcomes.append("live_success")
        elif "live_empty" in lower:
            outcomes.append("live_empty")
        elif "api_error" in lower:
            outcomes.append("api_error")
        elif "dry_run" in lower:
            outcomes.append("dry_run")
        elif step.get("method"):
            outcomes.append("api_called")
    return outcomes


def _api_paths(calls: list[dict[str, Any]]) -> list[str]:
    return [str(call.get("path") or "") for call in calls]


def _drift_category(old: dict[str, Any], current: dict[str, Any], changed: dict[str, Any]) -> str:
    correctness_delta = _delta(current.get("correctness_score"), old.get("correctness_score")) or 0.0
    final_delta = _delta(current.get("final_score"), old.get("final_score")) or 0.0
    runtime_delta = _delta(current.get("runtime"), old.get("runtime")) or 0.0
    token_delta = _delta(current.get("estimated_tokens"), old.get("estimated_tokens")) or 0.0
    if changed.get("api_endpoint_changed"):
        return "api_endpoint_selection_drift"
    if changed.get("evidencebus_changed"):
        return "evidencebus_field_drift"
    if changed.get("answer_wording_changed") and abs(correctness_delta) > 0.001:
        return "answer_wording_drift"
    if final_delta < 0 and correctness_delta >= 0 and (runtime_delta > 0.05 or token_delta > 50):
        return "scoring_artifact_changed"
    if changed.get("live_api_evidence_changed"):
        return "live_api_result_drift"
    if runtime_delta > 0.05:
        return "nondeterministic_live_api_payload"
    return "no_clear_drift"


def _root_cause(score_states: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    current = score_states["current_fresh_strict"]
    baseline = score_states["pre_live_previous_packaged_baseline"]
    correctness_delta = _delta(current.get("correctness_score"), baseline.get("correctness_score")) or 0.0
    final_delta = _delta(current.get("strict_score"), baseline.get("strict_score")) or 0.0
    runtime_delta = _delta(current.get("runtime"), baseline.get("runtime")) or 0.0
    token_delta = _delta(current.get("estimated_tokens"), baseline.get("estimated_tokens")) or 0.0
    categories: dict[str, int] = {}
    for row in rows:
        category = str(row.get("likely_drift_category") or "unknown")
        categories[category] = categories.get(category, 0) + 1
    if final_delta < 0 and correctness_delta >= 0 and (runtime_delta > 0.05 or token_delta > 50):
        primary = "efficiency_penalty_from_live_runtime_and_token_growth"
        true_runtime_regression = False
    elif correctness_delta < 0:
        primary = "true_correctness_regression"
        true_runtime_regression = True
    else:
        primary = "no_clear_drift"
        true_runtime_regression = False
    return {
        "primary_root_cause": primary,
        "strict_score_delta_vs_pre_live": final_delta,
        "correctness_score_delta_vs_pre_live": correctness_delta,
        "runtime_delta_vs_pre_live": runtime_delta,
        "token_delta_vs_pre_live": token_delta,
        "drift_category_counts": categories,
        "is_true_runtime_correctness_regression": true_runtime_regression,
        "reason_current_score_is_below_reference": (
            "Correctness is slightly higher than the pre-live baseline, but live runtime and larger trajectory token estimates "
            "increase the strict efficiency penalty enough to reduce final score below the non-regression reference."
            if primary == "efficiency_penalty_from_live_runtime_and_token_growth"
            else "See row-level deltas."
        ),
    }


def _arbitration_reference(arbitration: dict[str, Any], live_delta: dict[str, Any]) -> Any:
    for key in ["final_live_strict_score", "strict_score", "current_live_baseline_score"]:
        if isinstance(arbitration.get(key), (int, float)):
            return arbitration.get(key)
    delta_score = (live_delta.get("summary_delta") or {}).get("final_score", {}).get("current")
    return delta_score


def _arbitration_source(arbitration: dict[str, Any], live_delta: dict[str, Any]) -> str:
    if arbitration:
        return "outputs/reports/live_api_evidence_arbitration_trial.json"
    if live_delta:
        return "outputs/reports/live_api_strict_eval_delta.json"
    return "unavailable"


def _delta(current: Any, old: Any) -> float | None:
    if not isinstance(current, (int, float)) or not isinstance(old, (int, float)):
        return None
    return round(float(current) - float(old), 4)


def _num(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def _render_md(report: dict[str, Any]) -> str:
    states = report["score_states"]
    root = report["root_cause_summary"]
    lines = [
        "# Strict Score Drift Analysis",
        "",
        "This diagnostic compares the archived pre-live strict baseline, the post-live arbitration reference, and the current fresh strict result.",
        "",
        f"- Strategy: `{report.get('strategy')}`",
        f"- Non-regression reference: `{report.get('non_regression_reference')}`",
        f"- Pre-live strict score: `{states['pre_live_previous_packaged_baseline'].get('strict_score')}`",
        f"- Post-live arbitration reference: `{states['post_live_arbitration_recovered_reference'].get('strict_score')}`",
        f"- Current fresh strict score: `{states['current_fresh_strict'].get('strict_score')}`",
        f"- Primary root cause: `{root.get('primary_root_cause')}`",
        f"- Reason: {root.get('reason_current_score_is_below_reference')}",
        "",
        "## Row Summary",
        "",
        f"- Rows helped: `{report['summary'].get('rows_helped')}`",
        f"- Rows hurt: `{report['summary'].get('rows_hurt')}`",
        f"- Rows unchanged: `{report['summary'].get('rows_unchanged')}`",
        "",
        "## Top Negative Deltas",
        "",
    ]
    for row in report["summary"].get("top_negative_deltas", [])[:10]:
        lines.append(
            f"- `{row.get('query_id')}` delta `{row.get('score_delta')}` category `{row.get('likely_drift_category')}`"
        )
    lines.extend(
        [
            "",
            "No runtime fix is applied by this script.",
        ]
    )
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
