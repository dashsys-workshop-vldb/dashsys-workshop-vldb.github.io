#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_NAME = "improvement_backlog"
BASELINE_STRICT_SCORE = 0.6491
BASELINE_CORRECTNESS = 0.6743
BASELINE_TOKENS = 831.4571
BASELINE_RUNTIME = 0.0115
BASELINE_TOOLS = 1.4571
TARGET_SCORE = 0.7500


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the score075 improvement backlog.")
    parser.add_argument("--outputs-dir", default=str(ROOT / "outputs"))
    parser.add_argument("--json", default=None)
    parser.add_argument("--md", default=None)
    args = parser.parse_args()

    outputs_dir = Path(args.outputs_dir)
    payload = generate_improvement_backlog(outputs_dir)
    json_path = Path(args.json) if args.json else outputs_dir / f"{OUTPUT_NAME}.json"
    md_path = Path(args.md) if args.md else outputs_dir / f"{OUTPUT_NAME}.md"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "targets": len(payload["top_targets"])}, indent=2))
    return 0


def generate_improvement_backlog(outputs_dir: Path) -> dict[str, Any]:
    strict = _load_json(outputs_dir / "eval_results_strict.json")
    endpoint_report = _load_json(outputs_dir / "endpoint_family_failure_report.json")
    ast_report = _load_json(outputs_dir / "sql_ast_candidate_ranking_report.json")
    execution_search = _load_json(outputs_dir / "execution_candidate_search.json")
    hidden = _load_json(outputs_dir / "hidden_style_eval.json")

    strict_rows = [
        row
        for row in strict.get("rows", [])
        if row.get("strategy") == "SQL_FIRST_API_VERIFY"
    ]
    endpoint_by_query = {
        str(row.get("query_id")): row
        for row in endpoint_report.get("rows", [])
        if row.get("query_id")
    }
    ast_by_query = {
        str(row.get("query_id")): row
        for row in ast_report.get("rows", [])
        if row.get("query_id")
    }
    execution_selected = {
        str(row.get("query_id")): row
        for row in execution_search.get("selected_improvements", [])
        if row.get("query_id")
    }

    opportunities = [
        _classify_row(row, endpoint_by_query.get(str(row.get("query_id")), {}), ast_by_query.get(str(row.get("query_id")), {}), execution_selected)
        for row in strict_rows
    ]
    ranked = sorted(
        opportunities,
        key=lambda row: (
            {"high": 0, "medium": 1, "low": 2}.get(row["improvement_potential"], 3),
            -row["opportunity_score"],
            row["query_id"],
        ),
    )
    high_medium = [row for row in ranked if row["improvement_potential"] in {"high", "medium"}]
    failure_counts = Counter(row["likely_failure_type"] for row in ranked)
    cluster_counts = Counter(row["failure_cluster"] for row in ranked)
    baseline = _baseline_summary(strict)
    score_gap = max(0.0, TARGET_SCORE - baseline["strict_final_score"])
    total_score_needed = round(score_gap * max(1, len(strict_rows)), 4)
    return {
        "mode": OUTPUT_NAME,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "baseline": baseline,
        "target_score": TARGET_SCORE,
        "score_gap_to_target": round(score_gap, 4),
        "total_score_needed_to_reach_0_75": total_score_needed,
        "hidden_style_summary": hidden.get("summary", {}),
        "existing_execution_search_summary": execution_search.get("summary", {}),
        "summary": {
            "total_rows": len(strict_rows),
            "rows_below_0_7": sum(1 for row in ranked if row["current_score"] < 0.7),
            "high_potential_rows": sum(1 for row in ranked if row["improvement_potential"] == "high"),
            "medium_potential_rows": sum(1 for row in ranked if row["improvement_potential"] == "medium"),
            "low_potential_rows": sum(1 for row in ranked if row["improvement_potential"] == "low"),
            "likely_failure_type_counts": dict(sorted(failure_counts.items())),
            "failure_cluster_counts": dict(sorted(cluster_counts.items())),
            "minimum_average_gain_needed": round(score_gap, 4),
            "minimum_total_gain_needed": total_score_needed,
            "safe_backlog_items": len(high_medium),
            "recommended_first_workers": [
                "score075-robustness-leakage",
                "score075-local-index",
                "score075-dryrun-answer",
                "score075-answer-shape",
                "score075-candidate-generation",
            ],
        },
        "top_targets": high_medium[:15],
        "rows": ranked,
        "safety_notes": [
            "This report is offline diagnostic only and may read strict eval scores.",
            "Gold labels may not be used by runtime candidate generation.",
            "Promotable rules must not depend on query_id, exact full public query strings, gold SQL/API paths, or memorized answers.",
        ],
    }


def _classify_row(
    row: dict[str, Any],
    endpoint: dict[str, Any],
    ast: dict[str, Any],
    execution_selected: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    query_id = str(row.get("query_id"))
    query = str(row.get("query") or "")
    score = float(row.get("final_score") or 0.0)
    answer_score = float(row.get("answer_score") or 0.0)
    sql_score = float(row.get("sql_score") or 0.0)
    api_score = float(row.get("api_score") or 0.0)
    validation_failures = row.get("validation_failures") or []
    failure_type = _likely_failure_type(query, score, answer_score, sql_score, api_score, endpoint, ast, validation_failures)
    cluster = endpoint.get("risk_cluster") or failure_type
    leakage_risk = _leakage_risk(query, failure_type)
    generalizability = _generalizability(failure_type, query)
    likely_gain = max(0.0, 0.75 - score)
    existing_safe_candidate = query_id in execution_selected
    opportunity_score = round(likely_gain * generalizability - leakage_risk + (0.05 if existing_safe_candidate else 0.0), 4)
    if score < 0.6 and leakage_risk < 0.5 and generalizability >= 0.65:
        potential = "high"
    elif score < 0.7 and leakage_risk < 0.7:
        potential = "medium"
    else:
        potential = "low"
    return {
        "query_id": query_id,
        "query": query,
        "current_score": round(score, 4),
        "correctness_score": row.get("correctness_score"),
        "answer_score": row.get("answer_score"),
        "sql_score": row.get("sql_score"),
        "api_score": row.get("api_score"),
        "tool_calls": row.get("tool_call_count"),
        "estimated_tokens": row.get("estimated_tokens"),
        "failure_cluster": cluster,
        "likely_failure_type": failure_type,
        "improvement_potential": potential,
        "opportunity_score": opportunity_score,
        "leakage_risk": round(leakage_risk, 3),
        "generalizability": round(generalizability, 3),
        "candidate_worker": _candidate_worker(failure_type),
        "existing_safe_candidate_found": existing_safe_candidate,
        "anti_overfitting_requirements": [
            "no_query_id_trigger",
            "no_exact_full_query_trigger",
            "no_memorized_answer",
            "no_gold_sql_or_api_path",
        ],
    }


def _likely_failure_type(
    query: str,
    score: float,
    answer_score: float,
    sql_score: float,
    api_score: float,
    endpoint: dict[str, Any],
    ast: dict[str, Any],
    validation_failures: list[Any],
) -> str:
    q = query.lower()
    endpoint_failure = endpoint.get("failure_type")
    risk_cluster = str(endpoint.get("risk_cluster") or "")
    if endpoint_failure == "gold_api_missing_from_top_k":
        return "missing_api_candidate"
    if "endpoint_family_differs" in str(endpoint_failure):
        return "wrong_endpoint_family"
    if "schema_vs_dataset" in risk_cluster or ("schema" in q and ("dataset" in q or "collection" in q)):
        return "wrong_schema_dataset_relation"
    if "tag" in q and api_score < 0.9:
        return "wrong_api_selected"
    if "batch" in q and ("file" in q or "download" in q) and api_score < 0.9:
        return "wrong_endpoint_family"
    if any("unknown" in str(item).lower() for item in validation_failures) or ast.get("unknown_columns"):
        return "wrong_sql_join"
    if "how many" in q or "count" in q:
        if answer_score < 0.4:
            return "wrong_count_vs_list"
        return "wrong_aggregation"
    if any(term in q for term in ("date", "status", "recent", "published", "failed", "success")) and answer_score < 0.5:
        return "wrong_filter_date_status_normalization"
    if api_score >= 0.95 and answer_score < 0.4:
        return "dry_run_api_only_issue"
    if sql_score < 0.85:
        return "wrong_sql_join"
    if score < 0.7 and answer_score < 0.5:
        return "answer_format_issue"
    return "candidate_diversity_limitation"


def _candidate_worker(failure_type: str) -> str:
    mapping = {
        "dry_run_api_only_issue": "codex/score075-dryrun-answer",
        "answer_format_issue": "codex/score075-answer-shape",
        "wrong_count_vs_list": "codex/score075-answer-shape",
        "wrong_filter_date_status_normalization": "codex/score075-local-index",
        "wrong_endpoint_family": "codex/score075-endpoint-routing",
        "missing_api_candidate": "codex/score075-endpoint-routing",
        "wrong_api_selected": "codex/score075-endpoint-routing",
        "wrong_schema_dataset_relation": "codex/score075-endpoint-routing",
        "wrong_sql_join": "codex/score075-candidate-generation",
        "wrong_aggregation": "codex/score075-candidate-generation",
        "candidate_diversity_limitation": "codex/score075-candidate-generation",
    }
    return mapping.get(failure_type, "codex/score075-candidate-generation")


def _leakage_risk(query: str, failure_type: str) -> float:
    has_specific_id = any(ch.isdigit() for ch in query) and any(len(tok) >= 12 for tok in query.split())
    risk = 0.15
    if has_specific_id:
        risk += 0.25
    if failure_type in {"dry_run_api_only_issue", "answer_format_issue"}:
        risk += 0.05
    if failure_type in {"missing_api_candidate", "wrong_endpoint_family"}:
        risk += 0.15
    return min(risk, 1.0)


def _generalizability(failure_type: str, query: str) -> float:
    generalizable = {
        "dry_run_api_only_issue": 0.9,
        "answer_format_issue": 0.85,
        "wrong_count_vs_list": 0.85,
        "wrong_filter_date_status_normalization": 0.8,
        "wrong_schema_dataset_relation": 0.8,
        "wrong_endpoint_family": 0.7,
        "missing_api_candidate": 0.65,
        "wrong_api_selected": 0.65,
        "wrong_sql_join": 0.6,
        "wrong_aggregation": 0.65,
        "candidate_diversity_limitation": 0.55,
    }
    value = generalizable.get(failure_type, 0.5)
    if any(len(tok) >= 18 for tok in query.split()):
        value -= 0.1
    return max(0.1, value)


def _baseline_summary(strict: dict[str, Any]) -> dict[str, Any]:
    sql_first = (strict.get("summary") or {}).get("by_strategy", {}).get("SQL_FIRST_API_VERIFY", {})
    return {
        "preferred_strategy": "SQL_FIRST_API_VERIFY",
        "strict_final_score": float(sql_first.get("avg_final_score") or BASELINE_STRICT_SCORE),
        "correctness": float(sql_first.get("avg_correctness_score") or BASELINE_CORRECTNESS),
        "estimated_tokens": float(sql_first.get("avg_estimated_tokens") or BASELINE_TOKENS),
        "runtime": float(sql_first.get("avg_runtime") or BASELINE_RUNTIME),
        "tool_calls": float(sql_first.get("avg_tool_call_count") or BASELINE_TOOLS),
    }


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Score075 Improvement Backlog",
        "",
        f"- Baseline strict final score: {payload['baseline']['strict_final_score']}",
        f"- Target strict final score: {payload['target_score']}",
        f"- Total score needed to reach 0.75: {payload['total_score_needed_to_reach_0_75']}",
        f"- Rows below 0.7: {summary['rows_below_0_7']}",
        f"- High/medium safe backlog items: {summary['safe_backlog_items']}",
        "",
        "## Top Targets",
        "",
        "| query_id | score | likely failure | potential | worker |",
        "|---|---:|---|---|---|",
    ]
    for row in payload["top_targets"][:15]:
        lines.append(
            f"| {row['query_id']} | {row['current_score']} | {row['likely_failure_type']} | "
            f"{row['improvement_potential']} | {row['candidate_worker']} |"
        )
    lines.extend([
        "",
        "## Safety",
        "",
        "- Backlog generation is offline/report-only.",
        "- Runtime candidates must not use query IDs, exact public queries, gold paths, or memorized answers.",
        "- Hidden-style must remain 48/48 before any integration merge.",
    ])
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
