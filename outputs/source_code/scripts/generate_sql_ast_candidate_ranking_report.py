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
from dashagent.eval_harness import EvalHarness, first_generated_sql
from dashagent.executor import AgentExecutor
from dashagent.report_run import report_metadata
from dashagent.sql_ast_candidate_ranker import rank_sql_candidate_ast
from scripts.run_official_token_reduction_eval import _load_json, _load_trajectory


def main() -> int:
    config = Config.from_env(ROOT)
    payload = generate_sql_ast_candidate_ranking_report(config)
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    json_path = config.outputs_dir / "sql_ast_candidate_ranking_report.json"
    md_path = config.outputs_dir / "sql_ast_candidate_ranking_report.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "rows": len(payload["rows"])}, indent=2, sort_keys=True))
    return 0


def generate_sql_ast_candidate_ranking_report(config: Config) -> dict[str, Any]:
    executor = AgentExecutor(config)
    strict_rows = {
        str(row.get("query_id")): row
        for row in (_load_json(config.outputs_dir / "eval_results_strict.json").get("rows") or [])
        if row.get("strategy") == "SQL_FIRST_API_VERIFY"
    }
    rows = []
    for example in EvalHarness(config).load_examples():
        strict = strict_rows.get(example.query_id, {})
        trajectory = _load_trajectory(strict.get("output_dir"))
        candidates = _sql_candidates_from_trajectory(trajectory)
        for candidate in candidates:
            ast = rank_sql_candidate_ast(
                candidate["sql"],
                executor.schema_index,
                query=example.query,
                expected_answer_shape=_answer_shape(trajectory),
            )
            rows.append(
                {
                    "query_id": example.query_id,
                    "query": example.query,
                    "candidate_name": candidate["candidate_name"],
                    "source": candidate["source"],
                    "sql": candidate["sql"],
                    **ast,
                    "selected_sql": candidate["selected_sql"],
                    "report_only": True,
                    "selection_changed": False,
                }
            )
    return {
        **report_metadata(config.outputs_dir),
        "mode": "sql_ast_candidate_ranking_report",
        "report_only": True,
        "summary": {
            "candidate_count": len(rows),
            "parsed_ok_count": sum(1 for row in rows if row["parsed_ok"]),
            "avg_ast_quality_score": _avg(row["ast_quality_score"] for row in rows),
            "unknown_schema_count": sum(1 for row in rows if row["unknown_tables"] or row["unknown_columns"]),
            "destructive_sql_count": sum(1 for row in rows if row["destructive_sql_detected"]),
        },
        "rows": rows,
        "notes": ["AST quality is diagnostic only and does not change selected SQL."],
    }


def _sql_candidates_from_trajectory(trajectory: dict[str, Any]) -> list[dict[str, Any]]:
    selected = first_generated_sql(trajectory)
    candidates = []
    if selected:
        candidates.append({"candidate_name": "executed_sql", "source": "trajectory_sql_call", "sql": selected, "selected_sql": True})
    for checkpoint in trajectory.get("checkpoints", []) or []:
        if checkpoint.get("checkpoint_id") != "checkpoint_gated_sql_candidate_selection":
            continue
        output = checkpoint.get("output") or {}
        for index, item in enumerate(output.get("validation_results") or []):
            sql = item.get("sql")
            if sql:
                candidates.append(
                    {
                        "candidate_name": item.get("name") or f"gated_candidate_{index}",
                        "source": item.get("source") or "gated_sql_candidate",
                        "sql": sql,
                        "selected_sql": bool((output.get("selected_candidate") or {}).get("sql") == sql),
                    }
                )
    seen = set()
    deduped = []
    for candidate in candidates:
        key = (candidate["candidate_name"], candidate["sql"])
        if key not in seen:
            deduped.append(candidate)
            seen.add(key)
    return deduped


def _answer_shape(trajectory: dict[str, Any]) -> str:
    for step in trajectory.get("steps", []) or []:
        if step.get("kind") == "answer_diagnostics":
            return str(step.get("answer_family") or step.get("selected_candidate_type") or "unknown")
    return "unknown"


def _avg(values: Any) -> float:
    values = [float(value) for value in values]
    return round(sum(values) / len(values), 4) if values else 0.0


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# SQL AST Candidate Ranking Report",
        "",
        f"- Candidate count: {payload['summary']['candidate_count']}",
        f"- Avg AST quality score: {payload['summary']['avg_ast_quality_score']}",
        f"- Unknown schema count: {payload['summary']['unknown_schema_count']}",
        "",
        "| Query ID | Candidate | Parsed | Tables | Unknowns | Joins | Aggs | Filters | Quality |",
        "| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for row in payload["rows"]:
        unknowns = [*row.get("unknown_tables", []), *row.get("unknown_columns", [])]
        lines.append(
            f"| `{row['query_id']}` | {row['candidate_name']} | {row['parsed_ok']} | "
            f"{', '.join(row.get('selected_tables') or [])} | {', '.join(unknowns)} | "
            f"{row['join_count']} | {row['aggregation_count']} | {row['filter_count']} | {row['ast_quality_score']} |"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
