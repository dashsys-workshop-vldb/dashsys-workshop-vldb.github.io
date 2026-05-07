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
from dashagent.local_knowledge_index import build_local_knowledge_index, classify_evidence_hit, requested_fact_coverage
from dashagent.report_run import report_metadata


def main() -> int:
    config = Config.from_env(ROOT)
    payload = run_local_index_candidate_eval(config)
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    json_path = config.outputs_dir / "local_index_candidate_eval.json"
    md_path = config.outputs_dir / "local_index_candidate_eval.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    print(
        json.dumps(
            {
                "json": str(json_path),
                "markdown": str(md_path),
                "rows": payload["summary"]["total_rows"],
                "rows_with_hits": payload["summary"]["rows_with_hits"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def run_local_index_candidate_eval(config: Config) -> dict[str, Any]:
    strict_rows = _strict_sql_first_rows(config.outputs_dir / "eval_results_strict.json")
    index = build_local_knowledge_index(config)
    rows = []
    for row in strict_rows:
        query = str(row.get("query") or "")
        hits = index.lookup(query, max_results=8)
        classifications = [classify_evidence_hit(hit) for hit in hits]
        rejected_like = [classification for classification in classifications if classification == "rejected_exact_query_or_gold_like_lookup"]
        coverage = requested_fact_coverage(query, hits)
        trajectory = _load_trajectory(row.get("output_dir"))
        answer_candidate = compose_evidence_aware_answer(query, trajectory, local_evidence=hits) if trajectory else None
        rows.append(
            {
                "query_id": row.get("query_id"),
                "query": query,
                "current_score": row.get("final_score"),
                "correctness_score": row.get("correctness_score"),
                "answer_score": row.get("answer_score"),
                "local_index_hit_count": len(hits),
                "local_index_hits": hits,
                "hit_classifications": classifications,
                "leakage_check_passed": not rejected_like,
                "local_index_returns_final_answers": False,
                "local_evidence_available": bool(hits),
                "local_evidence_used_in_final_answer": bool(answer_candidate and answer_candidate.local_evidence_used_in_final_answer),
                "requested_fact_covered": bool(coverage.get("requested_fact_covered")),
                "requested_fact_type": coverage.get("requested_fact_type"),
                "score_delta_from_local_evidence": 0.0,
                "candidate_kind": "parquet_evidence_object_grounding",
                "safe_for_packaged_trial": False,
                "packaged_execution_changed": False,
                "rejection_reason": "Worker 3 provides evidence-object candidates only; integration must evaluate packaged behavior.",
            }
        )
    summary = _summary(rows, index)
    return {
        **report_metadata(config.outputs_dir),
        "mode": "local_index_candidate_eval",
        "diagnostic_only": True,
        "packaged_execution_changed": False,
        "writes_eval_outputs": False,
        "writes_final_submission": False,
        "runtime_sources": {
            "parquet_only": True,
            "data_json_used_for_runtime": False,
            "gold_sql_api_answers_used_for_runtime": False,
        },
        "summary": summary,
        "rows": rows,
        "notes": [
            "Rows are evidence-object candidates only and are not promoted by this worker.",
            "Gold/public eval rows are used only as offline queries for diagnostic matching.",
            "Local index hits must be consumed as evidence, never as final answers.",
        ],
    }


def _strict_sql_first_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    return [
        row
        for row in payload.get("rows", [])
        if str(row.get("strategy") or "") == "SQL_FIRST_API_VERIFY"
    ]


def _load_trajectory(path_value: Any) -> dict[str, Any]:
    if not path_value:
        return {}
    path = Path(str(path_value)) / "trajectory.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _summary(rows: list[dict[str, Any]], index: Any) -> dict[str, Any]:
    rows_with_hits = [row for row in rows if row["local_index_hit_count"]]
    leakage_failures = [row for row in rows if not row["leakage_check_passed"]]
    classification_counts: dict[str, int] = {}
    for row in rows:
        for classification in row["hit_classifications"]:
            classification_counts[classification] = classification_counts.get(classification, 0) + 1
    return {
        "total_rows": len(rows),
        "rows_with_hits": len(rows_with_hits),
        "total_hit_count": sum(int(row["local_index_hit_count"]) for row in rows),
        "leakage_failure_count": len(leakage_failures),
        "hit_classification_counts": dict(sorted(classification_counts.items())),
        "evidence_object_count": len(index.evidence_objects),
        "safe_for_packaged_trial_rows": 0,
        "local_evidence_available_rows": len(rows_with_hits),
        "local_evidence_used_in_final_answer_rows": sum(1 for row in rows if row.get("local_evidence_used_in_final_answer")),
        "requested_fact_covered_rows": sum(1 for row in rows if row.get("requested_fact_covered")),
        "score_delta_from_local_evidence_total": round(sum(float(row.get("score_delta_from_local_evidence") or 0.0) for row in rows), 4),
        "recommendation": "handoff_to_integration_for_candidate_selection" if rows_with_hits else "no_local_index_hits",
        "packaged_execution_changed": False,
        "data_json_used_for_runtime": False,
        "local_index_returns_final_answers": False,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Local Index Candidate Eval",
        "",
        "This is an isolated diagnostic eval. It does not change packaged execution.",
        "",
        f"- Total rows: {summary['total_rows']}",
        f"- Rows with local-index hits: {summary['rows_with_hits']}",
        f"- Total hit count: {summary['total_hit_count']}",
        f"- Leakage failures: {summary['leakage_failure_count']}",
        f"- Safe for packaged trial rows: {summary['safe_for_packaged_trial_rows']}",
        f"- Local evidence used in final answer rows: {summary['local_evidence_used_in_final_answer_rows']}",
        f"- Requested fact covered rows: {summary['requested_fact_covered_rows']}",
        f"- Recommendation: {summary['recommendation']}",
        f"- Data JSON used for runtime: {summary['data_json_used_for_runtime']}",
        f"- Local index returns final answers: {summary['local_index_returns_final_answers']}",
        f"- Packaged execution changed: {summary['packaged_execution_changed']}",
        "",
        "## Hit Classifications",
        "",
    ]
    for classification, count in summary.get("hit_classification_counts", {}).items():
        lines.append(f"- {classification}: {count}")
    lines.extend(["", "## Rows", ""])
    for row in payload["rows"][:30]:
        lines.append(
            f"- `{row['query_id']}`: hits={row['local_index_hit_count']} "
            f"covered={row.get('requested_fact_covered')} used={row.get('local_evidence_used_in_final_answer')} "
            f"leakage_ok={row['leakage_check_passed']} score={row.get('current_score')}"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
