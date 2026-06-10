from __future__ import annotations

from typing import Any

from .db import DuckDBDatabase
from .endpoint_catalog import EndpointCatalog
from .llm_client import LLMClient, get_llm_client
from .llm_sql_candidate_ranker import normalize_multi_candidate_plans, rank_sql_plan_candidates
from .llm_sql_execution_evidence_bridge import build_sql_execution_evidence
from .llm_sql_plan_compiler import compile_structured_sql_plan
from .llm_sql_semantic_verifier import verify_sql_plan_semantics
from .llm_tool_agent_prompts import (
    build_retrieved_schema_sql_candidates_prompt,
    build_retrieved_sql_plan_repair_prompt,
    build_sql_review_prompt,
    parse_json_object,
)
from .pure_llm_schema_retriever import retrieve_schema_context
from .pure_llm_sql_example_retriever import retrieve_sql_examples
from .schema_index import SchemaIndex
from .trajectory import redact_secrets
from .validators import SQLValidator


def run_pure_llm_text_to_sql_pipeline(
    prompt: str,
    db: DuckDBDatabase,
    schema_index: SchemaIndex,
    endpoint_catalog: EndpointCatalog | None,
    sql_validator: SQLValidator,
    *,
    llm_client: LLMClient | None = None,
    plan: dict[str, Any] | None = None,
    review_repair: bool = False,
    execution_probe: bool = False,
    evidence_grounding: bool = False,
) -> dict[str, Any]:
    client = llm_client or get_llm_client()
    if not client.available():
        return {
            "ok": False,
            "skipped": True,
            "failure_stage": "llm_unavailable",
            "reason": "LLM provider unavailable",
            "attempts": [],
        }

    retrieval_context = retrieve_schema_context(prompt, schema_index, endpoint_catalog)
    examples = retrieve_sql_examples(prompt, retrieval_context, limit=4)
    candidates, usage, retry_used = _generate_candidates(client, prompt, retrieval_context, examples, plan)
    ranked = rank_sql_plan_candidates(
        prompt,
        str((plan or {}).get("answer_intent") or retrieval_context.get("answer_intent") or ""),
        retrieval_context,
        candidates,
        schema_index,
        sql_validator,
        db=db,
        execution_probe=execution_probe,
        evidence_source_plan=(plan or {}).get("evidence_source_plan") if isinstance(plan, dict) else None,
    )
    attempts = [_attempt_from_ranked_item(item, sql_validator) for item in ranked.get("ranking", [])]
    selected = _execute_selected(prompt, db, ranked)
    if selected.get("ok"):
        return _success_payload(
            selected,
            retrieval_context,
            examples,
            ranked,
            attempts,
            usage,
            retry_used,
            repair_attempts=[],
            evidence_grounding=evidence_grounding,
        )

    repair_attempts: list[dict[str, Any]] = []
    if review_repair and ranked.get("ranking"):
        repair_result = _review_and_repair(
            prompt,
            client,
            db,
            schema_index,
            sql_validator,
            retrieval_context,
            ranked,
            execution_probe=execution_probe,
        )
        repair_attempts = repair_result.get("repair_attempts", [])
        if repair_result.get("ok"):
            attempts.extend(repair_result.get("attempts", []))
            return _success_payload(
                repair_result,
                retrieval_context,
                examples,
                ranked,
                attempts,
                usage,
                retry_used,
                repair_attempts=repair_attempts,
                evidence_grounding=evidence_grounding,
            )
        attempts.extend(repair_result.get("attempts", []))

    return redact_secrets(
        {
            "ok": False,
            "selected_sql": "",
            "sql": "",
            "candidate_count": len(candidates),
            "retrieval_context": retrieval_context,
            "dynamic_examples": examples,
            "candidate_ranking": ranked,
            "attempts": attempts,
            "candidate_generation_retry_used": retry_used,
            "repair_attempts": repair_attempts,
            "repair_rounds": len(repair_attempts),
            "failure_stage": "sql_plan_unrepairable",
            "safe_answer": "I could not produce a validated SQL query from the available schema.",
            "_usage": usage,
        }
    )


def _generate_candidates(
    client: LLMClient,
    prompt: str,
    retrieval_context: dict[str, Any],
    examples: list[dict[str, Any]],
    plan: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any], bool]:
    bundle = build_retrieved_schema_sql_candidates_prompt(prompt, retrieval_context, examples, plan)
    response = client.generate(bundle.system_prompt, bundle.user_prompt)
    parsed = parse_json_object(response.get("content", ""))
    candidates = normalize_multi_candidate_plans(parsed)
    usage = dict(response.get("usage") or {})
    retry_used = False
    if not candidates:
        retry_used = True
        correction = client.generate(
            bundle.system_prompt + " Correct your previous output and return valid JSON with exactly three candidates.",
            bundle.user_prompt,
        )
        parsed = parse_json_object(correction.get("content", ""))
        candidates = normalize_multi_candidate_plans(parsed)
        for key, value in (correction.get("usage") or {}).items():
            if isinstance(value, (int, float)):
                usage[key] = int(usage.get(key) or 0) + int(value)
    return candidates, usage, retry_used


def _review_and_repair(
    prompt: str,
    client: LLMClient,
    db: DuckDBDatabase,
    schema_index: SchemaIndex,
    sql_validator: SQLValidator,
    retrieval_context: dict[str, Any],
    ranked: dict[str, Any],
    *,
    execution_probe: bool,
) -> dict[str, Any]:
    repair_attempts: list[dict[str, Any]] = []
    attempts: list[dict[str, Any]] = []
    for item in (ranked.get("ranking") or [])[:3]:
        candidate = item.get("candidate") if isinstance(item.get("candidate"), dict) else {}
        compiled = item.get("compiled") if isinstance(item.get("compiled"), dict) else {}
        validation = item.get("validation") if isinstance(item.get("validation"), dict) else {}
        probe = item.get("probe") if isinstance(item.get("probe"), dict) else {}
        review_bundle = build_sql_review_prompt(
            prompt,
            candidate,
            str(compiled.get("sql") or ""),
            validation,
            probe,
            retrieval_context,
        )
        review_response = client.generate(review_bundle.system_prompt, review_bundle.user_prompt)
        review = parse_json_object(review_response.get("content", ""))
        errors = list(item.get("rejection_reasons") or [])
        suggestion = review.get("repair_suggestion")
        if suggestion:
            errors.append(str(suggestion))
        repair_bundle = build_retrieved_sql_plan_repair_prompt(prompt, retrieval_context, candidate, review, errors)
        repair_response = client.generate(repair_bundle.system_prompt, repair_bundle.user_prompt)
        repaired_plan = parse_json_object(repair_response.get("content", ""))
        repaired_result = _compile_validate_probe_execute(
            prompt,
            repaired_plan,
            retrieval_context,
            schema_index,
            sql_validator,
            db,
            execution_probe=execution_probe,
        )
        repair_attempt = {
            "candidate_id": item.get("candidate_id"),
            "review": review,
            "repaired_plan": repaired_plan,
            "result": {key: repaired_result.get(key) for key in ("ok", "sql", "failure_stage", "validation", "semantic_verification", "probe")},
            "_usage": _merge_usage(review_response.get("usage"), repair_response.get("usage")),
        }
        repair_attempts.append(redact_secrets(repair_attempt))
        attempts.append(repaired_result.get("attempt", {}))
        if repaired_result.get("ok"):
            return {
                **repaired_result,
                "repair_attempts": repair_attempts,
                "attempts": attempts,
                "repair_rounds": len(repair_attempts),
            }
    return {
        "ok": False,
        "repair_attempts": repair_attempts,
        "attempts": attempts,
        "failure_stage": "sql_plan_unrepairable",
    }


def _compile_validate_probe_execute(
    prompt: str,
    plan: dict[str, Any],
    retrieval_context: dict[str, Any],
    schema_index: SchemaIndex,
    sql_validator: SQLValidator,
    db: DuckDBDatabase,
    *,
    execution_probe: bool,
) -> dict[str, Any]:
    compiled = compile_structured_sql_plan(plan, schema_index, retrieval_context)
    sql = str(compiled.get("sql") or "")
    validation = sql_validator.validate(sql) if compiled.get("ok") and sql else None
    semantic = (
        verify_sql_plan_semantics(
            prompt,
            {},
            plan,
            retrieval_context,
            str(plan.get("answer_intent") or retrieval_context.get("answer_intent") or ""),
        )
        if compiled.get("ok")
        else {"ok": False, "errors": compiled.get("errors", []), "warnings": [], "semantic_score": 0.0}
    )
    probe = _probe(db, sql) if execution_probe and compiled.get("ok") and validation and validation.ok and semantic.get("ok") else {}
    attempt = {
        "round": 0,
        "structured_sql_plan": plan,
        "plan_validation": {"ok": bool(compiled.get("ok")), "errors": compiled.get("errors", []), "warnings": compiled.get("warnings", [])},
        "compile": compiled,
        "sql": sql,
        "validation": validation.to_dict() if validation else {"ok": False, "errors": compiled.get("errors", [])},
        "semantic_verification": semantic,
        "probe": probe,
        "executed": False,
    }
    if not (compiled.get("ok") and validation and validation.ok and semantic.get("ok")):
        return {
            "ok": False,
            "sql": sql,
            "compiled_sql": compiled,
            "validation": attempt["validation"],
            "semantic_verification": semantic,
            "probe": probe,
            "attempt": redact_secrets(attempt),
            "failure_stage": "sql_plan_unrepairable",
        }
    execution = db.execute_sql(sql)
    attempt["executed"] = True
    attempt["execution_ok"] = bool(execution.get("ok"))
    return redact_secrets(
        {
            "ok": bool(execution.get("ok")),
            "sql": sql,
            "selected_sql": sql,
            "structured_sql_plan": plan,
            "compiled_sql": compiled,
            "validation": attempt["validation"],
            "semantic_verification": semantic,
            "probe": probe,
            "execution_result": _compact_sql_result(execution),
            "attempt": attempt,
            "failure_stage": None if execution.get("ok") else "sql_execution_failed",
        }
    )


def _execute_selected(prompt: str, db: DuckDBDatabase, ranked: dict[str, Any]) -> dict[str, Any]:
    selected_id = ranked.get("selected_candidate_id")
    if not selected_id:
        return {"ok": False, "failure_stage": "no_selected_candidate"}
    selected = next((item for item in ranked.get("ranking", []) if item.get("candidate_id") == selected_id), None)
    if not selected:
        return {"ok": False, "failure_stage": "selected_candidate_missing"}
    sql = str((selected.get("compiled") or {}).get("sql") or "")
    execution = db.execute_sql(sql)
    return redact_secrets(
        {
            "ok": bool(execution.get("ok")),
            "sql": sql,
            "selected_sql": sql,
            "selected_candidate_id": selected_id,
            "structured_sql_plan": selected.get("candidate"),
            "compiled_sql": selected.get("compiled"),
            "validation": selected.get("validation"),
            "semantic_verification": selected.get("semantic_verification"),
            "probe": selected.get("probe"),
            "execution_result": _compact_sql_result(execution),
            "failure_stage": None if execution.get("ok") else "sql_execution_failed",
        }
    )


def _success_payload(
    selected: dict[str, Any],
    retrieval_context: dict[str, Any],
    examples: list[dict[str, Any]],
    ranked: dict[str, Any],
    attempts: list[dict[str, Any]],
    usage: dict[str, Any],
    retry_used: bool,
    *,
    repair_attempts: list[dict[str, Any]],
    evidence_grounding: bool,
) -> dict[str, Any]:
    execution_result = selected.get("execution_result") if isinstance(selected.get("execution_result"), dict) else {}
    sql = str(selected.get("selected_sql") or selected.get("sql") or "")
    sql_evidence = build_sql_execution_evidence(sql, execution_result) if evidence_grounding or execution_result else None
    return redact_secrets(
        {
            "ok": True,
            "sql": sql,
            "selected_sql": sql,
            "selected_candidate_id": selected.get("selected_candidate_id"),
            "structured_sql_plan": selected.get("structured_sql_plan"),
            "compiled_sql": selected.get("compiled_sql"),
            "validation": selected.get("validation"),
            "semantic_verification": selected.get("semantic_verification"),
            "probe": selected.get("probe"),
            "execution_result": execution_result,
            "sql_evidence": sql_evidence,
            "candidate_count": len((ranked.get("ranking") or [])),
            "candidate_ranking": ranked,
            "retrieval_context": retrieval_context,
            "dynamic_examples": examples,
            "attempts": attempts,
            "candidate_generation_retry_used": retry_used,
            "repair_attempts": repair_attempts,
            "repair_rounds": len(repair_attempts),
            "plan_validation_success": True,
            "compile_success": True,
            "sql_validation_success": True,
            "execution_success": True,
            "failure_stage": None,
            "_usage": usage,
        }
    )


def _attempt_from_ranked_item(item: dict[str, Any], sql_validator: SQLValidator) -> dict[str, Any]:
    compiled = item.get("compiled") if isinstance(item.get("compiled"), dict) else {}
    sql = str(compiled.get("sql") or "")
    return redact_secrets(
        {
            "round": 0,
            "candidate_id": item.get("candidate_id"),
            "structured_sql_plan": item.get("candidate"),
            "plan_validation": {"ok": bool(compiled.get("ok")), "errors": compiled.get("errors", []), "warnings": compiled.get("warnings", [])},
            "compile": compiled,
            "sql": sql,
            "validation": item.get("validation"),
            "semantic_verification": item.get("semantic_verification"),
            "probe": item.get("probe"),
            "ast_summary": sql_validator.ast_summary(sql) if sql else {"parse_error": "empty_sql"},
            "executed": False,
        }
    )


def _probe(db: DuckDBDatabase, sql: str) -> dict[str, Any]:
    if not sql:
        return {}
    cleaned = sql.strip().rstrip(";")
    result = db.execute_sql(f"SELECT * FROM ({cleaned}) AS _pure_llm_probe LIMIT 1", max_rows=1)
    rows = result.get("rows") if isinstance(result.get("rows"), list) else []
    return redact_secrets(
        {
            "probe_ok": bool(result.get("ok")),
            "row_count": result.get("row_count"),
            "columns_returned": list(rows[0].keys()) if rows and isinstance(rows[0], dict) else [],
            "error": result.get("error"),
        }
    )


def _compact_sql_result(result: dict[str, Any]) -> dict[str, Any]:
    rows = result.get("rows")
    return {
        "ok": bool(result.get("ok")),
        "row_count": result.get("row_count"),
        "rows": rows[:5] if isinstance(rows, list) else [],
        "limited": result.get("limited"),
        "error": result.get("error"),
    }


def _merge_usage(*items: Any) -> dict[str, int]:
    merged: dict[str, int] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        for key, value in item.items():
            if isinstance(value, (int, float)):
                merged[key] = int(merged.get(key, 0)) + int(value)
    return merged
