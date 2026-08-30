#!/usr/bin/env python
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.eval_harness import first_generated_sql, generated_api_calls
from dashagent.report_run import report_metadata
from scripts.run_official_token_reduction_eval import _load_json, _load_trajectory


TARGET_STRICT_SCORE = 0.7000
BASELINE_STRICT_SCORE = 0.6491


def main() -> int:
    config = Config.from_env(ROOT)
    payload = generate_low_score_failure_mining_report(config)
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    json_path = config.outputs_dir / "low_score_failure_mining_report.json"
    md_path = config.outputs_dir / "low_score_failure_mining_report.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "target_rows": len(payload["summary"]["top_10_target_rows"])}, indent=2, sort_keys=True))
    return 0


def generate_low_score_failure_mining_report(config: Config) -> dict[str, Any]:
    strict = _load_json(config.outputs_dir / "eval_results_strict.json")
    context = _load_json(config.outputs_dir / "candidate_context_report.json")
    endpoint_failures = _load_json(config.outputs_dir / "endpoint_family_failure_report.json")
    ast_report = _load_json(config.outputs_dir / "sql_ast_candidate_ranking_report.json")
    shadow = _load_json(config.outputs_dir / "shadow_repair_eval.json")
    strict_rows = [
        row for row in strict.get("rows", [])
        if row.get("strategy") == "SQL_FIRST_API_VERIFY"
    ]
    context_by_id = {str(row.get("query_id")): row for row in context.get("rows", [])}
    endpoint_by_id = {str(row.get("query_id")): row for row in endpoint_failures.get("rows", [])}
    ast_by_id = {str(row.get("query_id")): row for row in ast_report.get("rows", [])}
    shadow_by_id = {str(row.get("query_id")): row for row in shadow.get("rows", [])}

    rows = [
        _mine_row(
            row,
            context_by_id.get(str(row.get("query_id")), {}),
            endpoint_by_id.get(str(row.get("query_id")), {}),
            ast_by_id.get(str(row.get("query_id")), {}),
            shadow_by_id.get(str(row.get("query_id")), {}),
        )
        for row in strict_rows
    ]
    summary = _summary(rows, strict_rows)
    return {
        **report_metadata(config.outputs_dir),
        "mode": "low_score_failure_mining_report",
        "target_strict_score": TARGET_STRICT_SCORE,
        "baseline_strict_score": _avg([float(row.get("final_score") or 0.0) for row in strict_rows]) or BASELINE_STRICT_SCORE,
        "packaged_execution_changed": False,
        "writes_eval_outputs": False,
        "writes_final_submission": False,
        "rows": rows,
        "summary": summary,
        "notes": [
            "Gold labels and public examples are used only for offline scoring/reporting.",
            "Candidate generation must use reusable schema/API/query-vocabulary rules, not query-id branches.",
            "This report does not execute or promote any behavior.",
        ],
    }


def _mine_row(
    strict_row: dict[str, Any],
    context_row: dict[str, Any],
    endpoint_row: dict[str, Any],
    ast_row: dict[str, Any],
    shadow_row: dict[str, Any],
) -> dict[str, Any]:
    trajectory = _load_trajectory(strict_row.get("output_dir"))
    selected_sql = first_generated_sql(trajectory)
    selected_api = generated_api_calls(trajectory)
    likely_failure_type = _likely_failure_type(strict_row, context_row, endpoint_row, selected_sql)
    failure_cluster = (
        endpoint_row.get("risk_cluster")
        or context_row.get("schema_link_risk")
        or context_row.get("risk_level")
        or "uncategorized"
    )
    potential = _improvement_potential(strict_row, context_row, endpoint_row, likely_failure_type)
    return {
        "query_id": strict_row.get("query_id"),
        "query": strict_row.get("query"),
        "current_score": strict_row.get("final_score"),
        "correctness_score": strict_row.get("correctness_score"),
        "answer_score": strict_row.get("answer_score"),
        "sql_score": strict_row.get("sql_score"),
        "api_score": strict_row.get("api_score"),
        "selected_sql": selected_sql,
        "selected_api": selected_api,
        "endpoint_family": (context_row.get("endpoint_family_ranking") or {}).get("endpoint_family")
        or endpoint_row.get("predicted_endpoint_family"),
        "candidate_tables": context_row.get("candidate_tables", []),
        "candidate_apis": context_row.get("candidate_apis", []),
        "tool_calls": strict_row.get("tool_call_count"),
        "estimated_tokens": strict_row.get("estimated_tokens"),
        "failure_cluster": failure_cluster,
        "likely_failure_type": likely_failure_type,
        "improvement_potential": potential,
        "score_gap_to_0_70": round(max(0.0, TARGET_STRICT_SCORE - float(strict_row.get("final_score") or 0.0)), 4),
        "no_extra_tool_needed_likely": int(strict_row.get("tool_call_count") or 0) <= 2,
        "leakage_risk": "low" if not endpoint_row.get("gold_api") else "offline_gold_report_only",
        "ast_diagnostics": {
            "candidate_count": ast_row.get("candidate_count"),
            "unknown_schema_count": ast_row.get("unknown_schema_count"),
            "avg_ast_quality_score": ast_row.get("avg_ast_quality_score"),
        },
        "shadow_repair_delta": shadow_row.get("score_delta"),
    }


def _likely_failure_type(
    strict_row: dict[str, Any],
    context_row: dict[str, Any],
    endpoint_row: dict[str, Any],
    selected_sql: str | None,
) -> str:
    query = str(strict_row.get("query") or "").lower()
    sql_score = strict_row.get("sql_score")
    api_score = strict_row.get("api_score")
    answer_score = float(strict_row.get("answer_score") or 0.0)
    if endpoint_row.get("risk_cluster") == "missing_gold_api_in_top_k" or context_row.get("missing_gold_apis"):
        return "missing_api_candidate"
    if endpoint_row.get("predicted_endpoint_family") and endpoint_row.get("current_api"):
        if endpoint_row.get("predicted_endpoint_family") not in str(endpoint_row.get("current_api")):
            return "wrong_endpoint_family"
    if "schema" in query and ("dataset" in query or "collection" in query):
        return "wrong_schema_dataset_relation"
    if ("how many" in query or "count" in query) and selected_sql and "count(" not in selected_sql.lower():
        return "wrong_count_vs_list"
    if sql_score is not None and float(sql_score or 0.0) < 0.6:
        if "join" in str(selected_sql or "").lower() or any(word in query for word in ["using", "associated", "based on"]):
            return "wrong_sql_join"
        if any(word in query for word in ["status", "failed", "published", "recent", "date"]):
            return "wrong_filter"
        if any(word in query for word in ["average", "sum", "count", "total"]):
            return "wrong_aggregation"
        return "no_candidate_diversity"
    if api_score is not None and float(api_score or 0.0) < 0.6:
        return "wrong_endpoint_family"
    if answer_score < 0.45:
        return "answer_format_issue"
    if strict_row.get("api_call_count") and api_score is None:
        return "dry_run_api_only_issue"
    return "no_candidate_diversity"


def _improvement_potential(
    strict_row: dict[str, Any],
    context_row: dict[str, Any],
    endpoint_row: dict[str, Any],
    failure_type: str,
) -> str:
    score = float(strict_row.get("final_score") or 0.0)
    tool_calls = int(strict_row.get("tool_call_count") or 0)
    fixable = failure_type in {
        "wrong_endpoint_family",
        "missing_api_candidate",
        "wrong_sql_join",
        "wrong_count_vs_list",
        "wrong_schema_dataset_relation",
        "answer_format_issue",
        "no_candidate_diversity",
    }
    if score < 0.58 and fixable and tool_calls <= 2 and not endpoint_row.get("leakage_flag"):
        return "high"
    if score < 0.7 and fixable and tool_calls <= 2:
        return "medium"
    return "low"


def _summary(rows: list[dict[str, Any]], strict_rows: list[dict[str, Any]]) -> dict[str, Any]:
    avg_score = _avg([float(row.get("final_score") or 0.0) for row in strict_rows]) or 0.0
    total_gap = round(max(0.0, (TARGET_STRICT_SCORE - avg_score) * len(strict_rows)), 4)
    targets = [
        row for row in rows
        if float(row.get("current_score") or 0.0) < TARGET_STRICT_SCORE
        and row.get("improvement_potential") in {"high", "medium"}
    ]
    targets = sorted(
        targets,
        key=lambda row: (
            {"high": 0, "medium": 1, "low": 2}.get(str(row.get("improvement_potential")), 9),
            float(row.get("current_score") or 0.0),
            str(row.get("query_id")),
        ),
    )
    clusters = Counter(str(row.get("likely_failure_type")) for row in targets)
    return {
        "total_rows": len(strict_rows),
        "current_avg_final_score": round(avg_score, 4),
        "score_needed_to_reach_0_70_total": total_gap,
        "score_needed_to_reach_0_70_per_row": round(max(0.0, TARGET_STRICT_SCORE - avg_score), 4),
        "top_10_target_rows": [row.get("query_id") for row in targets[:10]],
        "estimated_minimum_rows_to_fix": _estimate_min_rows_to_fix(targets, total_gap),
        "safest_improvement_clusters": clusters.most_common(),
        "failure_type_counts": Counter(str(row.get("likely_failure_type")) for row in rows).most_common(),
        "packaged_execution_changed": False,
    }


def _estimate_min_rows_to_fix(targets: list[dict[str, Any]], total_gap: float) -> int:
    if total_gap <= 0:
        return 0
    gains = sorted([min(1.0 - float(row.get("current_score") or 0.0), 0.20) for row in targets], reverse=True)
    running = 0.0
    for index, gain in enumerate(gains, start=1):
        running += gain
        if running >= total_gap:
            return index
    return len(gains) if gains else 0


def _avg(values: list[float]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Low-Score Failure Mining Report",
        "",
        f"- Current average strict final score: {summary['current_avg_final_score']}",
        f"- Total score needed to reach 0.70: {summary['score_needed_to_reach_0_70_total']}",
        f"- Estimated minimum target rows to fix: {summary['estimated_minimum_rows_to_fix']}",
        f"- Top target rows: {', '.join(summary['top_10_target_rows'])}",
        f"- Packaged execution changed: {summary['packaged_execution_changed']}",
        "",
        "## Safest Improvement Clusters",
        "",
    ]
    lines.extend(f"- {name}: {count}" for name, count in summary["safest_improvement_clusters"])
    lines.extend(["", "## Top Rows", ""])
    for row in payload["rows"][:10]:
        lines.append(
            f"- {row['query_id']}: score={row['current_score']} type={row['likely_failure_type']} potential={row['improvement_potential']}"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
