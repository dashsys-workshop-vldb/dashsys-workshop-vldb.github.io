#!/usr/bin/env python
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.trajectory import redact_secrets

REPORT_STEM = "pure_llm_sql_semantic_quality_audit"


def main() -> int:
    config = Config.from_env(ROOT)
    payload = run_pure_llm_sql_semantic_quality_audit(config)
    print(
        json.dumps(
            {
                "json": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.json"),
                "markdown": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.md"),
                "rows": payload.get("summary", {}).get("rows"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def run_pure_llm_sql_semantic_quality_audit(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    bounded = _load_json(reports_dir / "pure_llm_bounded_sql_score_audit.json")
    rows = [_semantic_row(row) for row in bounded.get("rows", [])]
    payload = redact_secrets(
        {
            "report_type": REPORT_STEM,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "diagnostic_only": True,
            "promotion_allowed": False,
            "packaged_default_strategy": "SQL_FIRST_API_VERIFY",
            "packaged_runtime_changed": False,
            "source_report": "outputs/reports/pure_llm_bounded_sql_score_audit.json",
            "summary": {
                "rows": len(rows),
                "failure_categories": _count_by(rows, "failure_category"),
                "selected_tools": _count_by(rows, "selected_tool"),
                "answer_used_sql_result": sum(1 for row in rows if row.get("answer_used_sql_result")),
            },
            "rows": rows,
        }
    )
    (reports_dir / f"{REPORT_STEM}.json").write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    (reports_dir / f"{REPORT_STEM}.md").write_text(_render_md(payload), encoding="utf-8")
    return payload


def _semantic_row(row: dict[str, Any]) -> dict[str, Any]:
    plan = row.get("structured_sql_plan") if isinstance(row.get("structured_sql_plan"), dict) else {}
    selected_filters = plan.get("filters") if isinstance(plan.get("filters"), list) else []
    failure = _semantic_failure_category(row)
    return {
        "query_id": row.get("query_id"),
        "prompt": row.get("prompt"),
        "intended_answer_type": row.get("answer_intent"),
        "selected_tool": row.get("llm_selected_evidence_source"),
        "structured_sql_plan": plan,
        "compiled_sql": row.get("compiled_sql"),
        "sql_validation_result": row.get("sql_validation_result"),
        "sql_execution_result": row.get("sql_execution_result"),
        "selected_table": plan.get("primary_table"),
        "selected_columns": plan.get("columns_needed") or [],
        "selected_aggregation": plan.get("aggregation"),
        "selected_filters": selected_filters,
        "selected_join_path": plan.get("join_path") or plan.get("join_path_reason"),
        "final_answer": row.get("final_answer"),
        "answer_used_sql_result": row.get("final_answer_used_sql_result"),
        "sql_score": row.get("strict_sql_score"),
        "answer_score": row.get("strict_answer_score"),
        "failure_category": failure,
        "root_cause": _root_cause(row, failure),
    }


def _semantic_failure_category(row: dict[str, Any]) -> str:
    category = str(row.get("failure_category") or "")
    if category == "sql_valid_but_wrong_table":
        return "wrong_table"
    if category == "sql_valid_but_wrong_columns":
        return "wrong_columns"
    if category == "sql_valid_but_wrong_aggregation":
        return "wrong_aggregation"
    if category == "sql_valid_but_wrong_join":
        return "missing_join"
    if category == "sql_valid_but_wrong_filter":
        return "missing_filter"
    if category == "tool_trace_format_mismatch":
        return "no_executable_sql"
    if category == "sql_result_not_used_in_answer":
        return "sql_result_not_used"
    if category == "api_used_when_sql_needed":
        return "api_overselected"
    if row.get("strict_answer_score") == 0:
        return "answer_shape_wrong"
    return "no_clear_failure"


def _root_cause(row: dict[str, Any], failure: str) -> str:
    prompt = str(row.get("prompt") or "").lower()
    columns = " ".join(str(col).lower() for col in ((row.get("structured_sql_plan") or {}).get("columns_needed") or []))
    if failure == "wrong_columns" and "published" in prompt and "updated" in columns:
        return "The SQL plan selected an updated timestamp instead of a published timestamp such as LASTDEPLOYEDTIME."
    if failure == "no_executable_sql":
        return "The structured SQL plan or repair output did not compile to executable SQL before strict scoring."
    if failure == "wrong_table":
        return "The SQL plan passed validation but selected a table or SQL shape that did not match the requested local entity."
    if failure == "sql_result_not_used":
        return "The SQL query produced useful rows, but final answer synthesis ignored or underused those rows."
    if failure == "api_overselected":
        return "The planner selected API evidence even though local SQL was expected to answer the requested facts."
    if failure == "wrong_aggregation":
        return "The SQL plan aggregation did not match the prompt answer intent."
    if failure == "missing_filter":
        return "The SQL plan did not include the entity/status filter required by the prompt."
    if failure == "missing_join":
        return "The SQL plan did not include the relationship join required by the prompt."
    return "No single semantic root cause was identified from the compact bounded audit row."


def _render_md(payload: dict[str, Any]) -> str:
    summary = payload.get("summary", {})
    lines = [
        "# Pure LLM SQL Semantic Quality Audit",
        "",
        "Diagnostic-only audit. Packaged `SQL_FIRST_API_VERIFY` runtime is unchanged.",
        "",
        f"- Rows audited: `{summary.get('rows')}`",
        f"- Answer used SQL result rows: `{summary.get('answer_used_sql_result')}`",
        "",
        "## Failure Categories",
    ]
    for key, value in sorted((summary.get("failure_categories") or {}).items()):
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Row Root Causes"])
    for row in payload.get("rows", []):
        lines.extend(
            [
                f"### {row.get('query_id')}",
                f"- Prompt: {row.get('prompt')}",
                f"- Failure category: `{row.get('failure_category')}`",
                f"- SQL score / answer score: `{row.get('sql_score')}` / `{row.get('answer_score')}`",
                f"- Root cause: {row.get('root_cause')}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return counts


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


if __name__ == "__main__":
    raise SystemExit(main())
