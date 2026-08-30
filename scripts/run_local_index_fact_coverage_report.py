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
from dashagent.evidence_aware_answer_composer import compose_evidence_aware_answer
from dashagent.local_knowledge_index import build_local_knowledge_index, requested_fact_coverage
from dashagent.report_run import report_metadata
from scripts.run_official_token_reduction_eval import _load_json, _load_trajectory


def main() -> int:
    config = Config.from_env(ROOT)
    payload = run_local_index_fact_coverage_report(config)
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    json_path = config.outputs_dir / "local_index_fact_coverage_report.json"
    md_path = config.outputs_dir / "local_index_fact_coverage_report.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "covered_rows": payload["summary"]["requested_fact_covered_rows"]}, indent=2, sort_keys=True))
    return 0


def run_local_index_fact_coverage_report(config: Config) -> dict[str, Any]:
    strict = _load_json(config.outputs_dir / "eval_results_strict.json")
    evidence_eval = _load_json(config.outputs_dir / "evidence_answer_candidate_eval.json")
    evidence_rows = {str(row.get("query_id")): row for row in evidence_eval.get("rows", [])}
    index = build_local_knowledge_index(config)
    rows = []
    for row in strict.get("rows", []):
        if row.get("strategy") != "SQL_FIRST_API_VERIFY":
            continue
        query = str(row.get("query") or "")
        hits = index.lookup(query, max_results=8)
        coverage = requested_fact_coverage(query, hits)
        trajectory = _load_trajectory(row.get("output_dir"))
        candidate = compose_evidence_aware_answer(query, trajectory, local_evidence=hits)
        eval_row = evidence_rows.get(str(row.get("query_id")), {})
        local_used = bool(eval_row.get("local_evidence_used_in_final_answer", candidate.local_evidence_used_in_final_answer))
        rows.append(
            {
                "query_id": row.get("query_id"),
                "query": query,
                "current_score": row.get("final_score"),
                "answer_score": row.get("answer_score"),
                "local_evidence_available": bool(hits),
                "local_evidence_hit_count": len(hits),
                "local_evidence_used_in_final_answer": local_used,
                "requested_fact_covered": bool(coverage.get("requested_fact_covered")),
                "requested_fact_type": coverage.get("requested_fact_type"),
                "covered_hit_count": coverage.get("covered_hit_count"),
                "covered_hits": coverage.get("covered_hits", []),
                "score_delta_from_local_evidence": eval_row.get("score_delta_from_local_evidence", 0.0 if not local_used else eval_row.get("score_delta", 0.0)),
                "expected_score_improvement_potential": _potential(row, coverage, local_used),
                "packaged_execution_changed": False,
            }
        )
    summary = _summary(rows, index)
    return {
        **report_metadata(config.outputs_dir),
        "mode": "local_index_fact_coverage_report",
        "diagnostic_only": True,
        "packaged_execution_changed": False,
        "writes_eval_outputs": False,
        "writes_final_submission": False,
        "runtime_sources": {
            "parquet_only": True,
            "dbsnapshot_glob": "data/DBSnapshot/*.parquet",
            "data_json_used_for_runtime": False,
            "gold_sql_api_answers_used_for_runtime": False,
        },
        "rows": rows,
        "summary": summary,
        "notes": [
            "Local evidence counts only when it maps to requested query facts.",
            "Evidence objects are not final answers and must be consumed by a separate answer composer.",
        ],
    }


def _potential(row: dict[str, Any], coverage: dict[str, Any], local_used: bool) -> str:
    if local_used and coverage.get("requested_fact_covered") and float(row.get("answer_score") or 0.0) < 0.35:
        return "high"
    if coverage.get("requested_fact_covered"):
        return "medium"
    if coverage.get("covered_hit_count"):
        return "low"
    return "none"


def _summary(rows: list[dict[str, Any]], index: Any) -> dict[str, Any]:
    return {
        "total_rows": len(rows),
        "local_evidence_available_rows": sum(1 for row in rows if row["local_evidence_available"]),
        "local_evidence_used_in_final_answer_rows": sum(1 for row in rows if row["local_evidence_used_in_final_answer"]),
        "requested_fact_covered_rows": sum(1 for row in rows if row["requested_fact_covered"]),
        "score_delta_from_local_evidence_total": round(sum(float(row.get("score_delta_from_local_evidence") or 0.0) for row in rows), 4),
        "evidence_object_count": len(index.evidence_objects),
        "data_json_used_for_runtime": False,
        "local_index_returns_final_answers": False,
        "packaged_execution_changed": False,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Local Index Fact Coverage Report",
        "",
        f"- Total rows: {summary['total_rows']}",
        f"- Local evidence available rows: {summary['local_evidence_available_rows']}",
        f"- Local evidence used in final answer rows: {summary['local_evidence_used_in_final_answer_rows']}",
        f"- Requested fact covered rows: {summary['requested_fact_covered_rows']}",
        f"- Score delta from local evidence total: {summary['score_delta_from_local_evidence_total']}",
        f"- Data JSON used for runtime: {summary['data_json_used_for_runtime']}",
        f"- Packaged execution changed: {summary['packaged_execution_changed']}",
        "",
        "## Covered Rows",
        "",
    ]
    for row in payload["rows"]:
        if row["local_evidence_available"] or row["requested_fact_covered"]:
            lines.append(
                f"- `{row['query_id']}` hits={row['local_evidence_hit_count']} covered={row['requested_fact_covered']} "
                f"used={row['local_evidence_used_in_final_answer']} potential={row['expected_score_improvement_potential']}"
            )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
