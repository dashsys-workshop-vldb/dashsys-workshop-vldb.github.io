#!/usr/bin/env python
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.answer_slots import extract_answer_slots
from dashagent.config import Config
from dashagent.eval_harness import first_generated_sql
from dashagent.report_run import report_metadata
from dashagent.trajectory import redact_secrets
from scripts.run_evidence_aware_answer_rewrite_trial import tool_results_from_trajectory
from scripts.run_official_token_reduction_eval import _load_json, _load_trajectory


def main() -> int:
    config = Config.from_env(ROOT)
    payload = run_sql_evidence_usage_audit(config)
    print(json.dumps({"status": payload["status"], "rows": payload["total_rows"]}, indent=2, sort_keys=True))
    return 0


def run_sql_evidence_usage_audit(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    strict = _load_json(config.outputs_dir / "eval_results_strict.json")
    rows = [_audit_row(row) for row in strict.get("rows", []) if row.get("strategy") == "SQL_FIRST_API_VERIFY"]
    rows = [row for row in rows if row["sql_call_count"] > 0]
    payload = {
        **report_metadata(config.outputs_dir),
        "report_type": "sql_evidence_usage_audit",
        "status": "complete" if rows else "skipped",
        "official_score_claim": False,
        "total_rows": len(rows),
        "summary": {
            "zero_row_rows": sum(1 for row in rows if row["sql_result_row_count"] == 0),
            "answer_used_key_sql_value_rows": sum(1 for row in rows if row["answer_used_key_sql_value"]),
            "zero_row_unclear_rows": sum(1 for row in rows if row["zero_row_answer_unclear"]),
            "count_distinct_detected_rows": sum(1 for row in rows if row["count_distinct_used"]),
            "relationship_join_rows": sum(1 for row in rows if row["relationship_join_detected"]),
            "issue_distribution": dict(Counter(row["primary_sql_evidence_issue"] for row in rows)),
        },
        "rows": rows,
    }
    _write_report(reports_dir / "sql_evidence_usage_audit", payload, _render(payload))
    return payload


def _audit_row(row: dict[str, Any]) -> dict[str, Any]:
    trajectory = _load_trajectory(row.get("output_dir"))
    query = str(row.get("query") or trajectory.get("original_query") or "")
    answer = str(trajectory.get("final_answer") or "")
    tool_results = tool_results_from_trajectory(trajectory)
    slots = extract_answer_slots(query, tool_results)
    sql_results = [result for result in tool_results if result.get("type") == "sql"]
    rows = []
    for result in sql_results:
        payload = result.get("payload") or {}
        rows.extend(payload.get("rows") or [])
    columns = sorted({str(key) for sql_row in rows if isinstance(sql_row, dict) for key in sql_row})
    sql = first_generated_sql(trajectory) or ""
    key_values = _key_values(rows, slots)
    answer_used = any(str(value).lower() in answer.lower() for value in key_values[:10])
    zero_unclear = slots.sql_row_count == 0 and not any(token in answer.lower() for token in ["no matching", "no rows", "returned no"])
    issue = _issue(slots, answer, answer_used, zero_unclear)
    return redact_secrets(
        {
            "query_id": row.get("query_id"),
            "prompt": query,
            "route_type": trajectory.get("route_type"),
            "domain_type": trajectory.get("domain_type"),
            "sql_call_count": len(sql_results),
            "sql": sql,
            "sql_result_row_count": slots.sql_row_count,
            "selected_columns": columns,
            "count_evidence": slots.counts,
            "list_name_evidence": slots.entity_names,
            "status_evidence": slots.statuses,
            "timestamp_evidence": slots.timestamps,
            "answer_used_key_sql_value": answer_used,
            "answer_missed_ids": bool(slots.entity_ids and not any(str(value).lower() in answer.lower() for value in slots.entity_ids[:3])),
            "answer_missed_names": bool(slots.entity_names and not any(str(value).lower() in answer.lower() for value in slots.entity_names[:3])),
            "answer_missed_status": bool(slots.statuses and not any(str(value).lower() in answer.lower() for value in slots.statuses[:3])),
            "answer_missed_timestamp": bool(slots.timestamps and not any(str(value).lower()[:10] in answer.lower() for value in slots.timestamps[:3])),
            "zero_row_answer_unclear": zero_unclear,
            "count_distinct_used": "count(distinct" in sql.lower() or "count distinct" in sql.lower(),
            "relationship_join_detected": bool(re.search(r"\bjoin\b", sql, flags=re.I)),
            "primary_sql_evidence_issue": issue,
            "strict_sql_score": row.get("sql_score"),
            "strict_answer_score": row.get("answer_score"),
        }
    )


def _key_values(rows: list[Any], slots: Any) -> list[str]:
    values = [str(value) for value in slots.counts + slots.entity_names + slots.entity_ids + slots.statuses + slots.timestamps]
    for row in rows[:5]:
        if isinstance(row, dict):
            values.extend(str(value) for value in row.values() if value not in (None, "", [], {}))
    return list(dict.fromkeys(values))


def _issue(slots: Any, answer: str, answer_used: bool, zero_unclear: bool) -> str:
    if zero_unclear:
        return "zero_row_answer_unclear"
    if slots.counts and not any(str(value).lower() in answer.lower() for value in slots.counts[:3]):
        return "answer_missed_count"
    if slots.entity_names and not any(str(value).lower() in answer.lower() for value in slots.entity_names[:3]):
        return "answer_missed_names"
    if slots.statuses and not any(str(value).lower() in answer.lower() for value in slots.statuses[:3]):
        return "answer_missed_status"
    if slots.timestamps and not any(str(value).lower()[:10] in answer.lower() for value in slots.timestamps[:3]):
        return "answer_missed_timestamp"
    return "sql_evidence_used" if answer_used else "no_clear_sql_evidence_issue"


def _write_report(stem: Path, payload: dict[str, Any], markdown: str) -> None:
    stem.with_suffix(".json").write_text(json.dumps(redact_secrets(payload), indent=2, sort_keys=True, default=str), encoding="utf-8")
    stem.with_suffix(".md").write_text(markdown, encoding="utf-8")


def _render(payload: dict[str, Any]) -> str:
    lines = [
        "# SQL Evidence Usage Audit",
        "",
        "Report-only audit of SQL facts reaching the final answer. No SQL/API execution changed.",
        "",
        f"- Status: `{payload['status']}`",
        f"- SQL rows audited: `{payload['total_rows']}`",
        "",
        "## Summary",
        "",
    ]
    for key, value in payload["summary"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Examples", ""])
    for row in payload.get("rows", [])[:8]:
        lines.append(f"- `{row['query_id']}` {row['primary_sql_evidence_issue']}")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
