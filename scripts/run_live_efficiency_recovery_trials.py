#!/usr/bin/env python
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.token_reduction_policy import (
    TokenReductionPolicy,
    apply_token_reduction_to_trajectory,
    official_estimated_tokens,
)
from scripts.robustness_improvement_common import generated_summary, load_json, now_iso, write_report


REPORT_STEM = "live_efficiency_recovery_trials"
STRATEGY = "SQL_FIRST_API_VERIFY"
NON_REGRESSION_REFERENCE = 0.6553


def main() -> int:
    report = run_live_efficiency_recovery_trials(Config.from_env(ROOT))
    print(
        json.dumps(
            {
                "report": REPORT_STEM,
                "best_variant": report["summary"]["best_variant"],
                "best_projected_score": report["summary"]["best_projected_strict_score"],
                "recommendation": report["summary"]["recommendation"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def run_live_efficiency_recovery_trials(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    strict = load_json(config.outputs_dir / "eval_results_strict.json")
    rows = [row for row in strict.get("rows", []) if row.get("strategy") == STRATEGY]
    current_score = _current_strict_score(strict)
    variants = [
        ("compact_api_preview_strict", _variant_compact_api_preview_strict),
        ("evidencebus_projection_for_answer_context", _variant_evidencebus_projection),
        ("compact_repeated_checkpoint_metadata", _variant_compact_repeated_metadata),
        ("api_response_summary_only_for_live_success", _variant_api_summary_only),
        ("live_get_session_reuse", _variant_session_reuse_projection),
        ("identical_get_memoization_trial", _variant_identical_get_memoization),
        ("optional_api_suppression_when_sql_complete_trial", _variant_optional_api_suppression),
    ]
    variant_reports = [_evaluate_variant(config, rows, name, func, current_score=current_score) for name, func in variants]
    for index, variant in enumerate(variant_reports, start=1):
        write_report(config, f"live_efficiency_recovery_trial_iteration_{index}", variant, _render_variant_md(variant))
    best = max(variant_reports, key=lambda item: float(item["summary"].get("projected_strict_score") or 0.0), default={})
    safe_best = [
        item for item in variant_reports
        if item["summary"].get("projected_strict_score", 0.0) >= NON_REGRESSION_REFERENCE
        and item["summary"].get("final_answer_changes") == 0
        and item["summary"].get("sql_changes") == 0
        and item["summary"].get("api_changes") == 0
        and item["summary"].get("evidence_changes") == 0
    ]
    recommendation = "promote_efficiency_recovery_fix" if safe_best else "keep_current_behavior_blocked_by_efficiency"
    report = {
        "report_type": REPORT_STEM,
        "generated_at": now_iso(),
        "diagnostic_only": True,
        "official_score_claim": False,
        "runtime_change_applied": False,
        "promotion_allowed": bool(safe_best),
        "baseline_strict_score": current_score,
        "non_regression_reference": NON_REGRESSION_REFERENCE,
        "generated_prompt_diagnostic": generated_summary(config),
        "summary": {
            "variant_count": len(variant_reports),
            "best_variant": best.get("variant"),
            "best_projected_strict_score": (best.get("summary") or {}).get("projected_strict_score"),
            "best_delta_vs_current": (best.get("summary") or {}).get("delta_vs_current"),
            "best_delta_vs_reference": (best.get("summary") or {}).get("delta_vs_reference"),
            "recommendation": recommendation,
            "safe_variants": [item["variant"] for item in safe_best],
        },
        "variants": [
            {
                "variant": item["variant"],
                **item["summary"],
            }
            for item in variant_reports
        ],
    }
    write_report(config, REPORT_STEM, report, _render_md(report))
    return report


def _evaluate_variant(
    config: Config,
    rows: list[dict[str, Any]],
    name: str,
    transform: Callable[[dict[str, Any]], tuple[dict[str, Any], dict[str, Any]]],
    *,
    current_score: float,
) -> dict[str, Any]:
    evaluated = []
    for row in rows:
        trajectory = _load_trajectory(config, row)
        if not trajectory:
            continue
        candidate, metadata = transform(trajectory)
        baseline_tokens = int(row.get("estimated_tokens") or trajectory.get("estimated_tokens") or 0)
        candidate_tokens = int(candidate.get("estimated_tokens") or official_estimated_tokens(candidate))
        baseline_runtime = float(row.get("runtime") or trajectory.get("runtime") or 0.0)
        candidate_runtime = float(metadata.get("projected_runtime", baseline_runtime))
        correctness = float(row.get("correctness_score") or 0.0)
        tool_calls = int(row.get("tool_call_count") or trajectory.get("tool_call_count") or 0)
        candidate_tool_calls = int(metadata.get("projected_tool_calls", tool_calls))
        projected_score = _score(correctness, candidate_tool_calls, candidate_runtime, candidate_tokens)
        baseline_api = _api_fingerprint(trajectory)
        candidate_api = _api_fingerprint(candidate)
        baseline_sql = _sql_fingerprint(trajectory)
        candidate_sql = _sql_fingerprint(candidate)
        evaluated.append(
            {
                "query_id": row.get("query_id"),
                "baseline_score": row.get("final_score"),
                "projected_score": projected_score,
                "score_delta": round(projected_score - float(row.get("final_score") or 0.0), 4),
                "baseline_tokens": baseline_tokens,
                "candidate_tokens": candidate_tokens,
                "token_delta": candidate_tokens - baseline_tokens,
                "baseline_runtime": round(baseline_runtime, 4),
                "candidate_runtime": round(candidate_runtime, 4),
                "runtime_delta": round(candidate_runtime - baseline_runtime, 4),
                "baseline_tool_calls": tool_calls,
                "candidate_tool_calls": candidate_tool_calls,
                "tool_delta": candidate_tool_calls - tool_calls,
                "final_answer_changed": trajectory.get("final_answer") != candidate.get("final_answer"),
                "sql_changed": baseline_sql != candidate_sql,
                "api_changed": baseline_api != candidate_api,
                "evidence_changed": _evidence_fingerprint(trajectory) != _evidence_fingerprint(candidate),
                "unsupported_claims": metadata.get("unsupported_claims", 0),
                "notes": metadata.get("notes", []),
            }
        )
    avg_score = _avg(item.get("projected_score") for item in evaluated)
    avg_tokens = _avg(item.get("candidate_tokens") for item in evaluated)
    avg_runtime = _avg(item.get("candidate_runtime") for item in evaluated)
    avg_tools = _avg(item.get("candidate_tool_calls") for item in evaluated)
    summary = {
        "row_count": len(evaluated),
        "strict_score": avg_score,
        "projected_strict_score": avg_score,
        "delta_vs_current": round(avg_score - current_score, 4) if avg_score is not None else None,
        "delta_vs_reference": round(avg_score - NON_REGRESSION_REFERENCE, 4) if avg_score is not None else None,
        "avg_token_delta": round(avg_tokens - _avg(item.get("baseline_tokens") for item in evaluated), 4) if evaluated else None,
        "avg_runtime_delta": round(avg_runtime - _avg(item.get("baseline_runtime") for item in evaluated), 4) if evaluated else None,
        "avg_tool_delta": round(avg_tools - _avg(item.get("baseline_tool_calls") for item in evaluated), 4) if evaluated else None,
        "final_answer_changes": sum(1 for item in evaluated if item.get("final_answer_changed")),
        "sql_changes": sum(1 for item in evaluated if item.get("sql_changed")),
        "api_changes": sum(1 for item in evaluated if item.get("api_changed")),
        "evidence_changes": sum(1 for item in evaluated if item.get("evidence_changed")),
        "unsupported_claims": sum(int(item.get("unsupported_claims") or 0) for item in evaluated),
        "examples_helped": sorted(evaluated, key=lambda item: float(item.get("score_delta") or 0.0), reverse=True)[:10],
        "examples_hurt": sorted(evaluated, key=lambda item: float(item.get("score_delta") or 0.0))[:10],
    }
    summary["recommendation"] = _variant_recommendation(name, summary)
    return {
        "report_type": "live_efficiency_recovery_trial_iteration",
        "generated_at": now_iso(),
        "variant": name,
        "diagnostic_only": True,
        "runtime_change_applied": False,
        "summary": summary,
        "rows": evaluated,
    }


def _variant_compact_api_preview_strict(trajectory: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    policy = TokenReductionPolicy(max_preview_rows=1, max_cell_chars=64, max_text_chars=96, max_list_items=2, max_reason_chars=64)
    reduced, summary = apply_token_reduction_to_trajectory(trajectory, policy)
    return reduced, {"notes": ["strict preview and text compaction"], "summary": summary}


def _variant_compact_repeated_metadata(trajectory: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    reduced = copy.deepcopy(trajectory)
    for step in reduced.get("steps") or []:
        if not isinstance(step, dict):
            continue
        if step.get("kind") == "route":
            step.pop("reason", None)
            step["candidate_apis"] = (step.get("candidate_apis") or [])[:1]
            step["candidate_tables"] = (step.get("candidate_tables") or [])[:2]
        elif step.get("kind") == "nlp":
            step["decomposition"] = {"expected_answer_shape": (step.get("decomposition") or {}).get("expected_answer_shape")}
            step["value_retrieval"] = {"match_count": (step.get("value_retrieval") or {}).get("match_count")}
        elif step.get("kind") == "plan":
            for plan_step in step.get("steps") or []:
                if isinstance(plan_step, dict):
                    plan_step.pop("purpose", None)
                    plan_step.pop("sql", None)
            step.pop("rationale", None)
    reduced["estimated_tokens"] = official_estimated_tokens(reduced)
    return reduced, {"notes": ["route/nlp/plan metadata compaction only"]}


def _variant_evidencebus_projection(trajectory: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    return copy.deepcopy(trajectory), {"notes": ["answer-context projection is not represented in saved strict trajectory; no projected score change"]}


def _variant_api_summary_only(trajectory: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    reduced = copy.deepcopy(trajectory)
    for step in reduced.get("steps") or []:
        if not isinstance(step, dict) or step.get("kind") != "api_call":
            continue
        result = step.get("result")
        if not isinstance(result, dict) or result.get("ok") is not True:
            continue
        preview = result.get("result_preview")
        if isinstance(preview, dict):
            result["result_preview"] = {
                key: preview.get(key)
                for key in ["id", "name", "status", "state", "count", "total", "pagination", "page", "pageSize", "totalCount"]
                if preview.get(key) not in (None, "", [], {})
            }
        elif isinstance(preview, list):
            result["result_preview"] = {"item_count": len(preview), "items_previewed": min(len(preview), 1)}
    reduced["estimated_tokens"] = official_estimated_tokens(reduced)
    return reduced, {"notes": ["live success API preview summarized to typed fields"]}


def _variant_session_reuse_projection(trajectory: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    reduced = copy.deepcopy(trajectory)
    runtime = float(reduced.get("runtime") or 0.0)
    return reduced, {"projected_runtime": round(runtime * 0.94, 4), "notes": ["projected only; no request-shape change"]}


def _variant_identical_get_memoization(trajectory: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    reduced = copy.deepcopy(trajectory)
    return reduced, {"notes": ["trial-only; no projected safe tool-count change without per-run duplicate proof"]}


def _variant_optional_api_suppression(trajectory: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    reduced = copy.deepcopy(trajectory)
    return reduced, {"notes": ["high risk; no projected promotion without API score proof"]}


def _score(correctness: float, tools: int, runtime: float, tokens: int) -> float:
    penalty = min(1.0, (tools / 8) + (runtime / 30) + (tokens / 12000))
    return round(correctness - 0.1 * penalty, 4)


def _load_trajectory(config: Config, row: dict[str, Any]) -> dict[str, Any]:
    output_dir = Path(str(row.get("output_dir") or ""))
    path = output_dir / "trajectory.json" if output_dir.is_absolute() else config.project_root / output_dir / "trajectory.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _api_fingerprint(trajectory: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"method": step.get("method"), "url": step.get("url"), "params": step.get("params")}
        for step in trajectory.get("steps") or []
        if isinstance(step, dict) and step.get("kind") == "api_call"
    ]


def _sql_fingerprint(trajectory: dict[str, Any]) -> list[str]:
    return [
        str(step.get("sql") or "")
        for step in trajectory.get("steps") or []
        if isinstance(step, dict) and step.get("kind") == "sql_call"
    ]


def _evidence_fingerprint(trajectory: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for step in trajectory.get("steps") or []:
        if isinstance(step, dict) and step.get("kind") in {"sql_call", "api_call"}:
            result = step.get("result") or {}
            out.append(
                {
                    "kind": step.get("kind"),
                    "ok": result.get("ok"),
                    "row_count": result.get("row_count"),
                    "dry_run": result.get("dry_run"),
                    "endpoint": result.get("endpoint"),
                    "method": result.get("method"),
                    "url": result.get("url"),
                    "params": result.get("params"),
                }
            )
    return out


def _variant_recommendation(name: str, summary: dict[str, Any]) -> str:
    if name in {"identical_get_memoization_trial", "optional_api_suppression_when_sql_complete_trial"}:
        return "do_not_promote_without_stronger_evidence"
    if summary.get("projected_strict_score", 0.0) >= NON_REGRESSION_REFERENCE and not any(
        summary.get(key) for key in ["final_answer_changes", "sql_changes", "api_changes", "evidence_changes", "unsupported_claims"]
    ):
        return "candidate_for_runtime_validation"
    return "diagnostic_only"


def _avg(values: Any) -> float:
    nums = [float(value) for value in values if isinstance(value, (int, float))]
    return round(sum(nums) / len(nums), 4) if nums else 0.0


def _current_strict_score(strict: dict[str, Any]) -> float:
    value = (
        strict.get("summary", {})
        .get("by_strategy", {})
        .get(STRATEGY, {})
        .get("avg_final_score")
    )
    return float(value) if isinstance(value, (int, float)) else 0.0


def _render_variant_md(report: dict[str, Any]) -> str:
    summary = report["summary"]
    return "\n".join(
        [
            f"# Live Efficiency Recovery Trial: {report['variant']}",
            "",
            f"- Projected strict score: `{summary.get('projected_strict_score')}`",
            f"- Delta vs current: `{summary.get('delta_vs_current')}`",
            f"- Delta vs reference: `{summary.get('delta_vs_reference')}`",
            f"- Avg token delta: `{summary.get('avg_token_delta')}`",
            f"- Avg runtime delta: `{summary.get('avg_runtime_delta')}`",
            f"- Final answer changes: `{summary.get('final_answer_changes')}`",
            f"- SQL/API/evidence changes: `{summary.get('sql_changes')}` / `{summary.get('api_changes')}` / `{summary.get('evidence_changes')}`",
            f"- Recommendation: `{summary.get('recommendation')}`",
            "",
        ]
    )


def _render_md(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Live Efficiency Recovery Trials",
        "",
        "Diagnostic-only projected variants. No SQL/API evidence or final answers are changed by this report.",
        "",
        f"- Baseline strict score: `{report.get('baseline_strict_score')}`",
        f"- Non-regression reference: `{report.get('non_regression_reference')}`",
        f"- Best variant: `{summary.get('best_variant')}`",
        f"- Best projected strict score: `{summary.get('best_projected_strict_score')}`",
        f"- Recommendation: `{summary.get('recommendation')}`",
        "",
        "## Variants",
        "",
    ]
    for variant in report.get("variants", []):
        lines.append(
            f"- `{variant['variant']}`: projected `{variant.get('projected_strict_score')}`, token delta `{variant.get('avg_token_delta')}`, recommendation `{variant.get('recommendation')}`"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
