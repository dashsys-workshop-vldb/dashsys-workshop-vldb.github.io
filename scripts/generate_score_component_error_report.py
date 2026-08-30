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
from dashagent.report_run import report_metadata
from scripts.run_official_token_reduction_eval import _load_json, _load_trajectory


TARGET_SCORE = 0.7500


def main() -> int:
    config = Config.from_env(ROOT)
    payload = generate_score_component_error_report(config)
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    json_path = config.outputs_dir / "score_component_error_report.json"
    md_path = config.outputs_dir / "score_component_error_report.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "rows": len(payload["rows"])}, indent=2, sort_keys=True))
    return 0


def generate_score_component_error_report(config: Config) -> dict[str, Any]:
    strict = _load_json(config.outputs_dir / "eval_results_strict.json")
    local_eval = _load_json(config.outputs_dir / "local_index_candidate_eval.json")
    endpoint = _load_json(config.outputs_dir / "endpoint_family_failure_report.json")
    ast = _load_json(config.outputs_dir / "sql_ast_candidate_ranking_report.json")
    local_by_id = {str(row.get("query_id")): row for row in local_eval.get("rows", [])}
    endpoint_by_id = {str(row.get("query_id")): row for row in endpoint.get("rows", [])}
    ast_by_id = {str(row.get("query_id")): row for row in ast.get("rows", [])}
    rows = [
        _component_row(row, local_by_id.get(str(row.get("query_id")), {}), endpoint_by_id.get(str(row.get("query_id")), {}), ast_by_id.get(str(row.get("query_id")), {}))
        for row in strict.get("rows", [])
        if row.get("strategy") == "SQL_FIRST_API_VERIFY"
    ]
    rows.sort(key=_rank_key)
    summary = _summary(rows)
    return {
        **report_metadata(config.outputs_dir),
        "mode": "score_component_error_report",
        "target_score": TARGET_SCORE,
        "packaged_execution_changed": False,
        "writes_eval_outputs": False,
        "writes_final_submission": False,
        "rows": rows,
        "summary": summary,
        "notes": [
            "Gold labels are used only because this is an offline score-decomposition report.",
            "Runtime candidate generation must not use gold SQL/API/answers or data/data.json.",
            "Rows with API-correct but answer-weak scores are prioritized for answer-only ablation.",
        ],
    }


def _component_row(strict_row: dict[str, Any], local_row: dict[str, Any], endpoint_row: dict[str, Any], ast_row: dict[str, Any]) -> dict[str, Any]:
    trajectory = _load_trajectory(strict_row.get("output_dir"))
    answer_score = _score_value(strict_row.get("answer_score"))
    sql_score = strict_row.get("sql_score")
    api_score = strict_row.get("api_score")
    evidence_status = _evidence_status(trajectory)
    bottleneck = _likely_bottleneck(strict_row, evidence_status)
    improvement = _improvement_opportunity(strict_row, bottleneck, local_row, endpoint_row)
    return {
        "query_id": strict_row.get("query_id"),
        "query": strict_row.get("query"),
        "final_score": strict_row.get("final_score"),
        "correctness_score": strict_row.get("correctness_score"),
        "answer_score": answer_score,
        "sql_score": sql_score,
        "api_score": api_score,
        "estimated_tokens": strict_row.get("estimated_tokens"),
        "runtime": strict_row.get("runtime"),
        "tool_calls": strict_row.get("tool_call_count"),
        "selected_sql": first_generated_sql(trajectory),
        "selected_api": generated_api_calls(trajectory),
        "final_answer": trajectory.get("final_answer"),
        "evidence_status": evidence_status,
        "dry_run_live_evidence_status": evidence_status.get("dry_run_live_evidence_status"),
        "answer_shape_category": _answer_shape_category(str(strict_row.get("query") or "")),
        "likely_bottleneck": bottleneck,
        "improvement_opportunity": improvement,
        "local_index_could_help": bool(local_row.get("local_index_hit_count") or local_row.get("local_evidence_available")),
        "llm_candidate_search_could_help": bottleneck in {"wrong_endpoint_family", "wrong_sql_or_api_candidate", "answer_shape_issue"},
        "answer_only_improvement_may_help": _api_correct_answer_weak(strict_row),
        "sql_api_candidate_improvement_may_help": bottleneck in {"wrong_endpoint_family", "wrong_sql_or_api_candidate", "sql_bottleneck", "api_bottleneck"},
        "score_gap_to_0_75": round(max(0.0, TARGET_SCORE - float(strict_row.get("final_score") or 0.0)), 4),
        "endpoint_failure_type": endpoint_row.get("failure_type"),
        "endpoint_risk_cluster": endpoint_row.get("risk_cluster"),
        "ast_quality_score": ast_row.get("ast_quality_score") or ast_row.get("avg_ast_quality_score"),
        "low_leakage_risk": True,
    }


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    target_rows = [row for row in rows if row.get("improvement_opportunity") in {"high", "medium"}]
    api_answer_weak = [row for row in rows if row.get("answer_only_improvement_may_help")]
    return {
        "total_rows": len(rows),
        "target_score": TARGET_SCORE,
        "current_avg_final_score": round(sum(float(row.get("final_score") or 0.0) for row in rows) / len(rows), 4) if rows else 0.0,
        "total_score_gap_to_0_75": round(sum(float(row.get("score_gap_to_0_75") or 0.0) for row in rows), 4),
        "api_correct_answer_weak_rows": len(api_answer_weak),
        "top_api_correct_answer_weak_rows": [row.get("query_id") for row in api_answer_weak[:10]],
        "top_target_rows": [row.get("query_id") for row in target_rows[:10]],
        "likely_bottleneck_counts": _counts(row.get("likely_bottleneck") for row in rows),
        "packaged_execution_changed": False,
    }


def _rank_key(row: dict[str, Any]) -> tuple[Any, ...]:
    answer_first = 0 if row.get("answer_only_improvement_may_help") else 1
    potential_rank = {"high": 0, "medium": 1, "low": 2}.get(str(row.get("improvement_opportunity")), 9)
    return (answer_first, potential_rank, float(row.get("final_score") or 0.0), str(row.get("query_id") or ""))


def _likely_bottleneck(row: dict[str, Any], evidence_status: dict[str, Any]) -> str:
    if _api_correct_answer_weak(row):
        return "api_correct_answer_weak"
    sql_score = row.get("sql_score")
    api_score = row.get("api_score")
    if sql_score is not None and float(sql_score or 0.0) < 0.8:
        return "sql_bottleneck"
    if api_score is not None and float(api_score or 0.0) < 0.8:
        return "api_bottleneck"
    if evidence_status.get("dry_run_api_calls") and _score_value(row.get("answer_score")) < 0.45:
        return "dry_run_evidence_limitation"
    if _score_value(row.get("answer_score")) < 0.45:
        return "answer_shape_issue"
    return "candidate_or_efficiency_limit"


def _improvement_opportunity(row: dict[str, Any], bottleneck: str, local_row: dict[str, Any], endpoint_row: dict[str, Any]) -> str:
    score = float(row.get("final_score") or 0.0)
    if bottleneck == "api_correct_answer_weak" and score < 0.62:
        return "high"
    if bottleneck in {"api_correct_answer_weak", "answer_shape_issue"} and (local_row.get("local_index_hit_count") or score < 0.7):
        return "medium"
    if bottleneck in {"sql_bottleneck", "api_bottleneck"} and endpoint_row:
        return "medium"
    return "low"


def _api_correct_answer_weak(row: dict[str, Any]) -> bool:
    api_score = row.get("api_score")
    if api_score is None:
        return False
    return float(api_score or 0.0) >= 0.95 and _score_value(row.get("answer_score")) < 0.35


def _evidence_status(trajectory: dict[str, Any]) -> dict[str, Any]:
    dry = 0
    live = 0
    sql_ok = 0
    api_calls = 0
    for step in trajectory.get("steps", []):
        if step.get("kind") == "sql_call" and (step.get("result") or {}).get("ok"):
            sql_ok += 1
        if step.get("kind") == "api_call":
            api_calls += 1
            result = step.get("result") or {}
            if result.get("dry_run"):
                dry += 1
            elif result.get("ok"):
                live += 1
    return {
        "sql_ok_calls": sql_ok,
        "api_calls": api_calls,
        "dry_run_api_calls": dry,
        "live_api_ok_calls": live,
        "dry_run_live_evidence_status": "dry_run_only" if dry and not live else "live_or_sql_evidence" if live or sql_ok else "no_tool_evidence",
    }


def _answer_shape_category(query: str) -> str:
    lowered = query.lower()
    if any(term in lowered for term in ["how many", "count", "number of"]):
        return "count"
    if any(term in lowered for term in ["status", "state"]):
        return "status"
    if any(term in lowered for term in ["when", "date", "recent", "updated", "created"]):
        return "date"
    if any(term in lowered for term in ["list", "show", "which"]):
        return "list_or_detail"
    return "detail"


def _score_value(value: Any) -> float:
    return float(value or 0.0)


def _counts(values: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        key = str(value)
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Score Component Error Report",
        "",
        f"- Total rows: {summary['total_rows']}",
        f"- Current average strict final score: {summary['current_avg_final_score']}",
        f"- Total score gap to 0.75: {summary['total_score_gap_to_0_75']}",
        f"- API-correct answer-weak rows: {summary['api_correct_answer_weak_rows']}",
        f"- Top answer-only targets: {', '.join(summary['top_api_correct_answer_weak_rows'])}",
        f"- Packaged execution changed: {summary['packaged_execution_changed']}",
        "",
        "## Bottlenecks",
        "",
    ]
    lines.extend(f"- {name}: {count}" for name, count in summary["likely_bottleneck_counts"].items())
    lines.extend(["", "## Top Rows", ""])
    for row in payload["rows"][:12]:
        lines.append(
            f"- `{row['query_id']}` score={row['final_score']} answer={row['answer_score']} "
            f"api={row['api_score']} bottleneck={row['likely_bottleneck']} opportunity={row['improvement_opportunity']}"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
