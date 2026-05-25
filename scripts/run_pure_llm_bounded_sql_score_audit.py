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
from dashagent.eval_harness import EvalHarness, first_generated_sql, generated_api_calls, score_answer_strict, score_api_strict, score_sql_strict
from dashagent.trajectory import redact_secrets
from dashagent.validators import SQLValidator

REPORT_STEM = "pure_llm_bounded_sql_score_audit"
PURE_STRUCTURED_VARIANT = "structured_sql_plan_with_repair_v1"


def main() -> int:
    config = Config.from_env(ROOT)
    payload = run_pure_llm_bounded_sql_score_audit(config)
    print(
        json.dumps(
            {
                "json": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.json"),
                "markdown": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.md"),
                "root_cause": payload.get("summary", {}).get("root_cause"),
                "rows": len(payload.get("rows", [])),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def run_pure_llm_bounded_sql_score_audit(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    pure_eval = _load_json(reports_dir / "pure_llm_tool_agent_eval.json")
    harness = EvalHarness(config)
    examples = {example.query_id: example for example in harness.load_examples()}
    sql_validator = SQLValidator(harness.executor.schema_index)
    rows = [
        _audit_row(row, examples.get(str(row.get("query_id"))), harness, sql_validator, config)
        for row in pure_eval.get("rows", [])
        if row.get("system") == PURE_STRUCTURED_VARIANT and row.get("strict_scoring_status") == "available"
    ]
    payload = redact_secrets(
        {
            "report_type": REPORT_STEM,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "diagnostic_only": True,
            "promotion_allowed": False,
            "packaged_default_strategy": "SQL_FIRST_API_VERIFY",
            "packaged_runtime_changed": False,
            "source_report": "outputs/reports/pure_llm_tool_agent_eval.json",
            "summary": _summary(rows),
            "rows": rows,
        }
    )
    (reports_dir / f"{REPORT_STEM}.json").write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    (reports_dir / f"{REPORT_STEM}.md").write_text(_render_md(payload), encoding="utf-8")
    try:
        harness.executor.close()
    except Exception:
        pass
    return payload


def _audit_row(row: dict[str, Any], example: Any, harness: EvalHarness, sql_validator: SQLValidator, config: Config) -> dict[str, Any]:
    trajectory = row.get("trajectory") if isinstance(row.get("trajectory"), dict) else {}
    steps = trajectory.get("steps") if isinstance(trajectory.get("steps"), list) else []
    plan_step = next((step for step in steps if step.get("kind") == "llm_plan"), {})
    sql_step = next((step for step in steps if step.get("kind") == "sql_call"), {})
    api_step = next((step for step in steps if step.get("kind") == "api_call"), {})
    generated_sql = first_generated_sql(trajectory)
    generated_api = generated_api_calls(trajectory)
    gold_sql = example.gold_sql if example else None
    gold_api = example.gold_api if example else None
    gold_answer = example.gold_answer if example else None
    sql_score, sql_reason = score_sql_strict(harness.executor.db, generated_sql, gold_sql)
    api_score, _api_reason = score_api_strict(generated_api, gold_api)
    answer_score, _answer_reason = score_answer_strict(str(row.get("final_answer") or trajectory.get("final_answer") or ""), gold_answer)
    compiled_sql = _compiled_sql(sql_step) or generated_sql
    sql_validation = sql_step.get("validation") if isinstance(sql_step.get("validation"), dict) else {}
    sql_result = sql_step.get("result") if isinstance(sql_step.get("result"), dict) else {}
    deterministic = _deterministic_baseline(config, str(row.get("query_id") or ""), harness, sql_validator)
    generated_summary = _sql_summary(generated_sql, sql_validator) if generated_sql else {}
    gold_summary = _sql_summary(gold_sql, sql_validator) if gold_sql else {}
    comparison = _compare_to_deterministic(generated_summary, deterministic.get("sql_summary", {}), generated_sql)
    failure_category = _failure_category(
        row=row,
        sql_step=sql_step,
        api_step=api_step,
        generated_sql=generated_sql,
        gold_sql=gold_sql,
        sql_score=sql_score,
        sql_reason=sql_reason,
        sql_result=sql_result,
        generated_summary=generated_summary,
        gold_summary=gold_summary,
    )
    return redact_secrets(
        {
            "query_id": row.get("query_id"),
            "prompt": row.get("prompt"),
            "answer_intent": (plan_step.get("plan") or {}).get("answer_intent") if isinstance(plan_step.get("plan"), dict) else None,
            "expected_tool_type": _expected_tool_type(gold_sql, gold_api),
            "did_llm_call_sql": bool(sql_step),
            "did_llm_call_api": bool(api_step),
            "structured_sql_plan": _structured_plan(sql_step),
            "compiled_sql": compiled_sql,
            "generated_sql": generated_sql,
            "sql_validation_result": sql_validation,
            "sql_execution_result": _execution_summary(sql_result),
            "sql_row_count": sql_result.get("row_count") if isinstance(sql_result, dict) else None,
            "sql_result_preview": (sql_result.get("rows") or [])[:3] if isinstance(sql_result.get("rows"), list) else [],
            "api_endpoint_selected": api_step.get("endpoint_candidate") or api_step.get("url"),
            "final_answer": row.get("final_answer") or trajectory.get("final_answer"),
            "final_answer_used_sql_result": bool((row.get("trace_assertions") or {}).get("tool_result_used_in_answer")) if sql_step else False,
            "strict_sql_score": sql_score,
            "strict_sql_reason": sql_reason,
            "strict_api_score": api_score,
            "strict_answer_score": answer_score,
            "failure_category": failure_category,
            "deterministic_selected_sql": deterministic.get("sql"),
            "deterministic_selected_tables": deterministic.get("selected_tables", []),
            "pure_llm_selected_tables": generated_summary.get("selected_tables", []),
            "deterministic_sql_result": deterministic.get("result_summary"),
            "pure_llm_sql_result": _execution_summary(sql_result),
            "deterministic_final_answer": deterministic.get("final_answer"),
            "comparison_to_deterministic": comparison,
        }
    )


def _failure_category(
    *,
    row: dict[str, Any],
    sql_step: dict[str, Any],
    api_step: dict[str, Any],
    generated_sql: str | None,
    gold_sql: str | None,
    sql_score: float | None,
    sql_reason: str,
    sql_result: dict[str, Any],
    generated_summary: dict[str, Any],
    gold_summary: dict[str, Any],
) -> str:
    if not gold_sql:
        return "prompt_not_sql_answerable"
    if sql_step and not generated_sql:
        return "tool_trace_format_mismatch"
    if not generated_sql and api_step:
        return "api_used_when_sql_needed"
    if not generated_sql:
        return "no_sql_called_when_needed"
    if sql_score and sql_score > 0 and not (row.get("trace_assertions") or {}).get("tool_result_used_in_answer"):
        return "sql_result_not_used_in_answer"
    if sql_score and sql_score > 0:
        return "no_clear_sql_score_failure"
    generated_tables = set(generated_summary.get("selected_tables", []))
    gold_tables = set(gold_summary.get("selected_tables", []))
    if generated_tables != gold_tables:
        return "sql_valid_but_wrong_table"
    if _has_join(gold_sql) and not _has_join(generated_sql):
        return "sql_valid_but_wrong_join"
    if _has_count(gold_sql) != _has_count(generated_sql) or _has_distinct(gold_sql) != _has_distinct(generated_sql):
        return "sql_valid_but_wrong_aggregation"
    if " where " in gold_sql.lower() and " where " not in generated_sql.lower():
        return "sql_valid_but_wrong_filter"
    if sql_result.get("ok") and sql_result.get("rows") == []:
        return "sql_result_empty_unexpected"
    generated_columns = set(generated_summary.get("selected_columns", []))
    gold_columns = set(gold_summary.get("selected_columns", []))
    if generated_columns and gold_columns and generated_columns != gold_columns:
        return "sql_valid_but_wrong_columns"
    if sql_reason == "Strict SQL mismatch.":
        return "no_clear_sql_score_failure"
    return "no_clear_sql_score_failure"


def _deterministic_baseline(config: Config, query_id: str, harness: EvalHarness, sql_validator: SQLValidator) -> dict[str, Any]:
    trajectory_path = config.outputs_dir / "eval" / query_id / "sql_first_api_verify" / "trajectory.json"
    if not trajectory_path.exists():
        return {}
    trajectory = _load_json(trajectory_path)
    sql = first_generated_sql(trajectory)
    result = {}
    if sql:
        try:
            result = harness.executor.db.execute_sql(sql)
        except Exception as exc:
            result = {"ok": False, "error": type(exc).__name__}
    return {
        "sql": sql,
        "selected_tables": _sql_summary(sql, sql_validator).get("selected_tables", []) if sql else [],
        "sql_summary": _sql_summary(sql, sql_validator) if sql else {},
        "result_summary": _execution_summary(result),
        "final_answer": trajectory.get("final_answer"),
    }


def _compare_to_deterministic(pure_summary: dict[str, Any], deterministic_summary: dict[str, Any], generated_sql: str | None) -> str:
    if not generated_sql:
        return "answer_did_not_use_sql"
    pure_tables = set(pure_summary.get("selected_tables", []))
    deterministic_tables = set(deterministic_summary.get("selected_tables", []))
    if pure_tables != deterministic_tables:
        return "wrong_table"
    pure_columns = set(pure_summary.get("selected_columns", []))
    deterministic_columns = set(deterministic_summary.get("selected_columns", []))
    if pure_columns != deterministic_columns:
        return "same_table_different_filter"
    return "same_sql_shape"


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    categories: dict[str, int] = {}
    for row in rows:
        category = str(row.get("failure_category") or "no_clear_sql_score_failure")
        categories[category] = categories.get(category, 0) + 1
    sql_scores = [float(row.get("strict_sql_score")) for row in rows if isinstance(row.get("strict_sql_score"), (int, float))]
    sql_zero = bool(sql_scores) and all(score == 0.0 for score in sql_scores)
    missing_or_invalid = sum(categories.get(item, 0) for item in ["api_used_when_sql_needed", "no_sql_called_when_needed", "tool_trace_format_mismatch", "eval_harness_did_not_recognize_sql", "sql_valid_but_wrong_table", "sql_valid_but_wrong_filter", "sql_valid_but_wrong_columns", "sql_valid_but_wrong_join", "sql_valid_but_wrong_aggregation"])
    root_cause = (
        "bounded_sql_score_zero_due_to_missing_or_invalid_sql_calls"
        if sql_zero and missing_or_invalid
        else "bounded_sql_score_requires_row_level_review"
    )
    return {
        "rows": len(rows),
        "average_sql_score": round(sum(sql_scores) / len(sql_scores), 4) if sql_scores else None,
        "failure_categories": categories,
        "root_cause": root_cause,
        "why_sql_score_zero": _why_zero(categories) if sql_zero else "SQL score is not uniformly zero in the audited rows.",
    }


def _why_zero(categories: dict[str, int]) -> str:
    parts = []
    if categories.get("api_used_when_sql_needed"):
        parts.append(f"{categories['api_used_when_sql_needed']} row(s) used API while gold SQL existed")
    if categories.get("no_sql_called_when_needed"):
        parts.append(f"{categories['no_sql_called_when_needed']} row(s) emitted no SQL while gold SQL existed")
    if categories.get("tool_trace_format_mismatch") or categories.get("eval_harness_did_not_recognize_sql"):
        parts.append("at least one SQL trace was not visible to the evaluator")
    wrong_sql = sum(categories.get(item, 0) for item in ["sql_valid_but_wrong_table", "sql_valid_but_wrong_columns", "sql_valid_but_wrong_join", "sql_valid_but_wrong_filter", "sql_valid_but_wrong_aggregation", "no_clear_sql_score_failure"])
    if wrong_sql:
        parts.append(f"{wrong_sql} row(s) emitted SQL that did not match gold SQL semantics")
    return "; ".join(parts) + "."


def _render_md(payload: dict[str, Any]) -> str:
    summary = payload.get("summary", {})
    lines = [
        "# Pure LLM Bounded SQL Score Audit",
        "",
        "Diagnostic-only audit. Packaged `SQL_FIRST_API_VERIFY` runtime is unchanged.",
        "",
        "## Summary",
        f"- Rows audited: `{summary.get('rows')}`",
        f"- Average SQL score: `{summary.get('average_sql_score')}`",
        f"- Root cause: `{summary.get('root_cause')}`",
        f"- Explanation: {summary.get('why_sql_score_zero')}",
        "",
        "## Failure Categories",
    ]
    for key, value in sorted((summary.get("failure_categories") or {}).items()):
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Rows"])
    for row in payload.get("rows", []):
        lines.extend(
            [
                f"### {row.get('query_id')}",
                f"- Prompt: {row.get('prompt')}",
                f"- Failure category: `{row.get('failure_category')}`",
                f"- SQL called: `{row.get('did_llm_call_sql')}`; API called: `{row.get('did_llm_call_api')}`",
                f"- Strict SQL/API/answer: `{row.get('strict_sql_score')}` / `{row.get('strict_api_score')}` / `{row.get('strict_answer_score')}`",
                f"- SQL reason: {row.get('strict_sql_reason')}",
                f"- Compiled SQL: `{row.get('compiled_sql') or ''}`",
                f"- Deterministic comparison: `{row.get('comparison_to_deterministic')}`",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _expected_tool_type(gold_sql: str | None, gold_api: Any) -> str:
    if gold_sql and gold_api:
        return "sql_api"
    if gold_sql:
        return "sql"
    if gold_api:
        return "api"
    return "unknown"


def _structured_plan(sql_step: dict[str, Any]) -> dict[str, Any] | None:
    attempts = sql_step.get("attempts") if isinstance(sql_step.get("attempts"), list) else []
    for attempt in reversed(attempts):
        plan = attempt.get("structured_sql_plan")
        if isinstance(plan, dict):
            return plan
    return None


def _compiled_sql(sql_step: dict[str, Any]) -> str | None:
    attempts = sql_step.get("attempts") if isinstance(sql_step.get("attempts"), list) else []
    for attempt in reversed(attempts):
        compile_result = attempt.get("compile") if isinstance(attempt.get("compile"), dict) else {}
        if compile_result.get("sql"):
            return str(compile_result["sql"])
    return None


def _execution_summary(result: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(result, dict):
        return {}
    return {
        "ok": result.get("ok"),
        "row_count": result.get("row_count"),
        "error": result.get("error"),
        "rows_preview": (result.get("rows") or [])[:3] if isinstance(result.get("rows"), list) else [],
    }


def _sql_summary(sql: str | None, sql_validator: SQLValidator) -> dict[str, Any]:
    if not sql:
        return {}
    try:
        return sql_validator.ast_summary(sql)
    except Exception as exc:
        return {"parse_error": type(exc).__name__, "selected_tables": [], "selected_columns": []}


def _has_join(sql: str) -> bool:
    return " join " in sql.lower()


def _has_count(sql: str) -> bool:
    return "count(" in sql.lower()


def _has_distinct(sql: str) -> bool:
    return "distinct" in sql.lower()


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


if __name__ == "__main__":
    raise SystemExit(main())
