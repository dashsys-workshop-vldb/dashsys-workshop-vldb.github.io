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
from dashagent.pure_llm_tool_agent import (
    API_ONLY_ONLY_WHEN_SQL_UNAVAILABLE_V1,
    STRUCTURED_SQL_PLAN_WITH_REPAIR_V1,
    STRUCTURED_SQL_PLAN_WITH_TOOL_CHOICE_GUARD_V1,
    SQL_FIRST_WHEN_VALIDATOR_HIGH_CONFIDENCE_V1,
)
from dashagent.trajectory import redact_secrets
from dashagent.validators import SQLValidator

REPORT_STEM = "pure_llm_bounded_sql_score_audit"
TOOL_CHOICE_STEM = "pure_llm_tool_choice_root_cause_audit"
SQL_TRACE_FIX_STEM = "pure_llm_example003_like_sql_trace_fix"
AUDITED_VARIANTS = {
    STRUCTURED_SQL_PLAN_WITH_REPAIR_V1,
    STRUCTURED_SQL_PLAN_WITH_TOOL_CHOICE_GUARD_V1,
    SQL_FIRST_WHEN_VALIDATOR_HIGH_CONFIDENCE_V1,
    API_ONLY_ONLY_WHEN_SQL_UNAVAILABLE_V1,
}


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
        if row.get("system") in AUDITED_VARIANTS and row.get("strict_scoring_status") == "available"
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
    _write_tool_choice_root_cause_report(reports_dir, payload)
    _write_sql_trace_fix_report(reports_dir, payload)
    try:
        harness.executor.close()
    except Exception:
        pass
    return payload


def _audit_row(row: dict[str, Any], example: Any, harness: EvalHarness, sql_validator: SQLValidator, config: Config) -> dict[str, Any]:
    trajectory = row.get("trajectory") if isinstance(row.get("trajectory"), dict) else {}
    steps = trajectory.get("steps") if isinstance(trajectory.get("steps"), list) else []
    plan_step = next((step for step in steps if step.get("kind") == "llm_plan"), {})
    evidence_step = next((step for step in steps if step.get("kind") == "evidence_source_plan"), {})
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
    tool_choice = _tool_choice_analysis(
        row=row,
        plan_step=plan_step,
        evidence_step=evidence_step,
        sql_step=sql_step,
        api_step=api_step,
        gold_sql=gold_sql,
        gold_api=gold_api,
        failure_category=failure_category,
    )
    return redact_secrets(
        {
            "query_id": row.get("query_id"),
            "variant": row.get("system") or row.get("variant"),
            "prompt": row.get("prompt"),
            "answer_intent": (plan_step.get("plan") or {}).get("answer_intent") if isinstance(plan_step.get("plan"), dict) else None,
            "expected_tool_type": _expected_tool_type(gold_sql, gold_api),
            "did_llm_call_sql": bool(sql_step),
            "did_llm_call_api": bool(api_step),
            **tool_choice,
            "structured_sql_plan": _structured_plan(sql_step),
            "compiled_sql": compiled_sql,
            "generated_sql": generated_sql,
            "sql_validation_result": sql_validation,
            "sql_repair_rounds": sql_step.get("repair_rounds"),
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


def _tool_choice_analysis(
    *,
    row: dict[str, Any],
    plan_step: dict[str, Any],
    evidence_step: dict[str, Any],
    sql_step: dict[str, Any],
    api_step: dict[str, Any],
    gold_sql: str | None,
    gold_api: Any,
    failure_category: str,
) -> dict[str, Any]:
    plan = plan_step.get("plan") if isinstance(plan_step.get("plan"), dict) else {}
    context = plan_step.get("context_summary") if isinstance(plan_step.get("context_summary"), dict) else {}
    evidence_plan = evidence_step.get("initial_plan") if isinstance(evidence_step.get("initial_plan"), dict) else {}
    final_evidence_plan = evidence_step.get("final_plan") if isinstance(evidence_step.get("final_plan"), dict) else evidence_plan
    validation = evidence_step.get("validation") if isinstance(evidence_step.get("validation"), dict) else {}
    decision = evidence_plan or {
        "needs_local_sql": bool(plan.get("needs_sql")),
        "needs_live_api": bool(plan.get("needs_api")),
        "preferred_first_tool": _choice_from_plan(plan),
        "sql_reason": plan.get("sql_task") or plan.get("reason") or "",
        "api_reason": plan.get("api_task") or plan.get("reason") or "",
        "local_tables_that_may_answer": plan.get("candidate_tables") or context.get("top_tables") or [],
        "api_endpoints_that_may_answer": plan.get("candidate_endpoints") or context.get("endpoint_candidates") or [],
    }
    final_choice = validation.get("final_tool_choice") or final_evidence_plan.get("preferred_first_tool") or _choice_from_plan(plan)
    selected_source = _selected_source(sql_step, api_step, final_choice)
    local_tables = _safe_string_list(validation.get("top_relevant_sql_tables") or decision.get("local_tables_that_may_answer") or context.get("top_tables"))
    api_endpoints = _safe_string_list(validation.get("top_relevant_api_endpoints") or decision.get("api_endpoints_that_may_answer") or context.get("endpoint_candidates"))
    expected_source = _expected_evidence_source(gold_sql, gold_api, validation)
    ignored_schema = bool(validation.get("ignored_schema_context")) or (
        bool(gold_sql and local_tables)
        and selected_source == "call_api"
        and not decision.get("needs_local_sql")
    )
    endpoint_misled = bool(validation.get("endpoint_catalog_may_have_misled_model")) or (
        selected_source == "call_api" and bool(api_endpoints) and bool(gold_sql)
    )
    return {
        "llm_initial_evidence_source_decision": decision,
        "llm_final_evidence_source_decision": final_evidence_plan,
        "llm_selected_evidence_source": selected_source,
        "why_chose_api": decision.get("api_reason") or plan.get("api_task") or plan.get("reason"),
        "api_endpoint_could_actually_answer_prompt": bool(gold_api and api_step),
        "local_schema_has_relevant_tables": bool(validation.get("local_schema_has_relevant_tables")) or bool(local_tables and gold_sql),
        "top_relevant_sql_tables": local_tables[:5],
        "top_relevant_api_endpoints": api_endpoints[:5],
        "evidence_source_that_should_have_been_considered": expected_source,
        "llm_ignored_schema_context": ignored_schema,
        "endpoint_catalog_description_misled_model": endpoint_misled,
        "tool_choice_root_cause": _tool_choice_root_cause(
            failure_category=failure_category,
            selected_source=selected_source,
            ignored_schema=ignored_schema,
            endpoint_misled=endpoint_misled,
            evidence_step=evidence_step,
            sql_step=sql_step,
        ),
        "tool_choice_validation_ok": validation.get("ok"),
        "tool_choice_rejection_reason": validation.get("rejection_reason"),
        "tool_choice_retry_used": evidence_step.get("retry_used"),
    }


def _choice_from_plan(plan: dict[str, Any]) -> str:
    needs_sql = bool(plan.get("needs_sql"))
    needs_api = bool(plan.get("needs_api"))
    if needs_sql and needs_api:
        return "both"
    if needs_sql:
        return "execute_sql"
    if needs_api:
        return "call_api"
    return "none"


def _selected_source(sql_step: dict[str, Any], api_step: dict[str, Any], fallback: Any) -> str:
    if sql_step and api_step:
        return "both"
    if sql_step:
        return "execute_sql"
    if api_step:
        return "call_api"
    return str(fallback or "none")


def _safe_string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value] if value else []
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        if isinstance(item, dict):
            text = item.get("table") or item.get("endpoint_id") or item.get("id") or item.get("path")
        else:
            text = item
        if text:
            result.append(str(text))
    return result


def _expected_evidence_source(gold_sql: str | None, gold_api: Any, validation: dict[str, Any]) -> str:
    if validation.get("evidence_source_that_should_have_been_considered") and validation.get("evidence_source_that_should_have_been_considered") != "unclear":
        return str(validation["evidence_source_that_should_have_been_considered"])
    if gold_sql and gold_api:
        return "mixed_sql_api"
    if gold_sql:
        return "local_sql_required"
    if gold_api:
        return "live_api_required"
    return "unclear"


def _tool_choice_root_cause(
    *,
    failure_category: str,
    selected_source: str,
    ignored_schema: bool,
    endpoint_misled: bool,
    evidence_step: dict[str, Any],
    sql_step: dict[str, Any],
) -> str:
    if evidence_step.get("root_cause"):
        root = str(evidence_step["root_cause"])
        if root != "no_clear_tool_choice_failure":
            return root
    if failure_category == "api_used_when_sql_needed":
        if ignored_schema:
            return "missed_local_table_affordance"
        if endpoint_misled:
            return "endpoint_catalog_overselected"
        return "api_bias_for_live_terms"
    if failure_category == "no_sql_called_when_needed":
        return "prompt_intent_misread"
    if failure_category == "tool_trace_format_mismatch":
        repair_rounds = int(sql_step.get("repair_rounds") or 0) if isinstance(sql_step, dict) else 0
        return "repair_loop_failed" if repair_rounds else "sql_plan_failed_after_correct_tool"
    if failure_category.startswith("sql_valid_but_"):
        return "sql_plan_failed_after_correct_tool"
    if selected_source == "call_api":
        return "endpoint_catalog_overselected" if endpoint_misled else "api_bias_for_live_terms"
    return "no_clear_tool_choice_failure"


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


def _write_tool_choice_root_cause_report(reports_dir: Path, payload: dict[str, Any]) -> dict[str, Any]:
    rows = [
        {
            "query_id": row.get("query_id"),
            "variant": row.get("variant"),
            "prompt": row.get("prompt"),
            "llm_initial_evidence_source_decision": row.get("llm_initial_evidence_source_decision"),
            "llm_selected_evidence_source": row.get("llm_selected_evidence_source"),
            "why_chose_api": row.get("why_chose_api"),
            "api_endpoint_could_actually_answer_prompt": row.get("api_endpoint_could_actually_answer_prompt"),
            "local_schema_has_relevant_tables": row.get("local_schema_has_relevant_tables"),
            "top_relevant_sql_tables": row.get("top_relevant_sql_tables"),
            "top_relevant_api_endpoints": row.get("top_relevant_api_endpoints"),
            "evidence_source_that_should_have_been_considered": row.get("evidence_source_that_should_have_been_considered"),
            "llm_ignored_schema_context": row.get("llm_ignored_schema_context"),
            "endpoint_catalog_description_misled_model": row.get("endpoint_catalog_description_misled_model"),
            "tool_choice_root_cause": row.get("tool_choice_root_cause"),
            "failure_category": row.get("failure_category"),
        }
        for row in payload.get("rows", [])
    ]
    report = redact_secrets(
        {
            "report_type": TOOL_CHOICE_STEM,
            "generated_at": payload.get("generated_at"),
            "diagnostic_only": True,
            "promotion_allowed": False,
            "packaged_default_strategy": "SQL_FIRST_API_VERIFY",
            "packaged_runtime_changed": False,
            "summary": {
                "rows": len(rows),
                "root_causes": _count_by(rows, "tool_choice_root_cause"),
                "selected_evidence_sources": _count_by(rows, "llm_selected_evidence_source"),
                "expected_evidence_sources": _count_by(rows, "evidence_source_that_should_have_been_considered"),
            },
            "rows": rows,
        }
    )
    (reports_dir / f"{TOOL_CHOICE_STEM}.json").write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    (reports_dir / f"{TOOL_CHOICE_STEM}.md").write_text(_render_tool_choice_md(report), encoding="utf-8")
    return report


def _write_sql_trace_fix_report(reports_dir: Path, payload: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for row in payload.get("rows", []):
        if row.get("failure_category") != "tool_trace_format_mismatch":
            continue
        rows.append(
            {
                "query_id": row.get("query_id"),
                "variant": row.get("variant"),
                "prompt": row.get("prompt"),
                "structured_sql_plan": row.get("structured_sql_plan"),
                "compiled_sql": row.get("compiled_sql"),
                "generated_sql": row.get("generated_sql"),
                "sql_validation_result": row.get("sql_validation_result"),
                "repair_rounds": _repair_rounds_from_row(row),
                "executable_sql_reached_evaluator": bool(row.get("generated_sql")),
                "compiled_sql_available_but_not_in_trace": bool(row.get("compiled_sql") and not row.get("generated_sql")),
                "likely_issue": _sql_trace_likely_issue(row),
                "fix_status": _sql_trace_fix_status(row),
            }
        )
    report = redact_secrets(
        {
            "report_type": SQL_TRACE_FIX_STEM,
            "generated_at": payload.get("generated_at"),
            "diagnostic_only": True,
            "promotion_allowed": False,
            "packaged_default_strategy": "SQL_FIRST_API_VERIFY",
            "packaged_runtime_changed": False,
            "summary": {
                "example003_like_row_count": len(rows),
                "likely_issues": _count_by(rows, "likely_issue"),
                "format_mismatch_rows_with_compiled_sql": sum(1 for row in rows if row.get("compiled_sql_available_but_not_in_trace")),
            },
            "rows": rows,
        }
    )
    (reports_dir / f"{SQL_TRACE_FIX_STEM}.json").write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    (reports_dir / f"{SQL_TRACE_FIX_STEM}.md").write_text(_render_sql_trace_fix_md(report), encoding="utf-8")
    return report


def _repair_rounds_from_row(row: dict[str, Any]) -> int | None:
    if isinstance(row.get("sql_repair_rounds"), int):
        return row["sql_repair_rounds"]
    validation = row.get("sql_validation_result") if isinstance(row.get("sql_validation_result"), dict) else {}
    if isinstance(validation.get("repair_rounds"), int):
        return validation["repair_rounds"]
    return None


def _sql_trace_likely_issue(row: dict[str, Any]) -> str:
    validation_text = json.dumps(row.get("sql_validation_result") or {}, default=str).lower()
    plan_text = json.dumps(row.get("structured_sql_plan") or {}, default=str).lower()
    if row.get("compiled_sql") and not row.get("generated_sql"):
        return "tool_trace_format_mismatch"
    if "unknown table" in validation_text or "unknown table" in plan_text:
        return "compiler_rejected_plan"
    if row.get("tool_choice_root_cause") == "repair_loop_failed":
        return "repair_loop_failed"
    return "repair_loop_failed" if not row.get("generated_sql") else "no_clear_trace_issue"


def _sql_trace_fix_status(row: dict[str, Any]) -> str:
    if row.get("compiled_sql") and row.get("generated_sql"):
        return "executable_sql_emitted"
    if row.get("compiled_sql") and not row.get("generated_sql"):
        return "needs_trace_format_fix"
    return "no_executable_sql_due_to_plan_or_repair_failure"


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


def _render_tool_choice_md(report: dict[str, Any]) -> str:
    summary = report.get("summary", {})
    lines = [
        "# Pure LLM Tool-Choice Root Cause Audit",
        "",
        "Diagnostic-only audit for shadow Pure LLM evidence-source selection. Packaged `SQL_FIRST_API_VERIFY` runtime is unchanged.",
        "",
        f"- Rows audited: `{summary.get('rows')}`",
        "",
        "## Root Causes",
    ]
    for key, value in sorted((summary.get("root_causes") or {}).items()):
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Rows"])
    for row in report.get("rows", []):
        lines.extend(
            [
                f"### {row.get('query_id')} / `{row.get('variant')}`",
                f"- Prompt: {row.get('prompt')}",
                f"- Selected evidence source: `{row.get('llm_selected_evidence_source')}`",
                f"- Should have considered: `{row.get('evidence_source_that_should_have_been_considered')}`",
                f"- Root cause: `{row.get('tool_choice_root_cause')}`",
                f"- Relevant SQL tables: `{row.get('top_relevant_sql_tables')}`",
                f"- Relevant API endpoints: `{row.get('top_relevant_api_endpoints')}`",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _render_sql_trace_fix_md(report: dict[str, Any]) -> str:
    summary = report.get("summary", {})
    lines = [
        "# Pure LLM Example003-Like SQL Trace Fix Audit",
        "",
        "Diagnostic-only audit for bounded rows where SQL was expected but no executable SQL reached strict scoring.",
        "",
        f"- Example003-like row count: `{summary.get('example003_like_row_count')}`",
        f"- Rows with compiled SQL missing from trace: `{summary.get('format_mismatch_rows_with_compiled_sql')}`",
        "",
        "## Likely Issues",
    ]
    for key, value in sorted((summary.get("likely_issues") or {}).items()):
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Rows"])
    for row in report.get("rows", []):
        lines.extend(
            [
                f"### {row.get('query_id')} / `{row.get('variant')}`",
                f"- Executable SQL reached evaluator: `{row.get('executable_sql_reached_evaluator')}`",
                f"- Likely issue: `{row.get('likely_issue')}`",
                f"- Fix status: `{row.get('fix_status')}`",
                f"- Compiled SQL: `{row.get('compiled_sql') or ''}`",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


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


def _count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return counts


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
