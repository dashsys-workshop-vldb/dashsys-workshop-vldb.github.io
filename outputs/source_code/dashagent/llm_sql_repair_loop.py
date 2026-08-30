from __future__ import annotations

from typing import Any

from .db import DuckDBDatabase
from .llm_client import LLMClient, get_llm_client
from .llm_sql_plan_compiler import compile_structured_sql_plan
from .llm_sql_candidate_ranker import normalize_multi_candidate_plans, rank_sql_plan_candidates
from .llm_sql_semantic_verifier import verify_sql_plan_semantics
from .llm_tool_agent_prompts import (
    build_multi_candidate_structured_sql_plan_prompt,
    build_sql_candidate_prompt,
    build_sql_repair_prompt,
    build_structured_sql_plan_prompt,
    build_structured_sql_plan_repair_prompt,
    parse_json_object,
)
from .trajectory import redact_secrets
from .validators import SQLValidator


def run_sql_repair_loop(
    prompt: str,
    schema_context: dict[str, Any],
    db: DuckDBDatabase,
    sql_validator: SQLValidator,
    *,
    llm_client: LLMClient | None = None,
    plan: dict[str, Any] | None = None,
    max_repair_rounds: int = 2,
    structured_sql_plan: bool = False,
    semantic_verify: bool = False,
    multi_candidate_sql_plan: bool = False,
    execution_probe: bool = False,
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

    if structured_sql_plan:
        if multi_candidate_sql_plan:
            return _run_multi_candidate_structured_plan_loop(
                prompt,
                schema_context,
                db,
                sql_validator,
                client,
                plan=plan,
                semantic_verify=semantic_verify,
                execution_probe=execution_probe,
            )
        return _run_structured_plan_repair_loop(
            prompt,
            schema_context,
            db,
            sql_validator,
            client,
            plan=plan,
            max_repair_rounds=max_repair_rounds,
            semantic_verify=semantic_verify,
        )

    attempts: list[dict[str, Any]] = []
    bundle = build_sql_candidate_prompt(prompt, schema_context, plan)
    candidate = _call_json(client, bundle.system_prompt, bundle.user_prompt)
    for round_index in range(max_repair_rounds + 1):
        sql = str(candidate.get("sql") or "").strip()
        validation = sql_validator.validate(sql)
        ast = sql_validator.ast_summary(sql) if sql else {"parse_error": "empty_sql"}
        attempt = {
            "round": round_index,
            "sql": sql,
            "candidate": candidate,
            "validation": validation.to_dict(),
            "ast_summary": ast,
            "executed": False,
        }
        if validation.ok:
            execution = db.execute_sql(sql)
            attempt["executed"] = True
            attempt["execution_ok"] = bool(execution.get("ok"))
            attempts.append(redact_secrets(attempt))
            return redact_secrets(
                {
                    "ok": bool(execution.get("ok")),
                    "sql": sql,
                    "validation": validation.to_dict(),
                    "ast_summary": ast,
                    "execution_result": _compact_sql_result(execution),
                    "repair_rounds": round_index,
                    "attempts": attempts,
                    "failure_stage": None if execution.get("ok") else "sql_execution_failed",
                }
            )
        attempts.append(redact_secrets(attempt))
        if round_index >= max_repair_rounds:
            break
        repair = build_sql_repair_prompt(prompt, schema_context, sql, validation.errors)
        candidate = _call_json(client, repair.system_prompt, repair.user_prompt)
    return redact_secrets(
        {
            "ok": False,
            "sql": attempts[-1]["sql"] if attempts else "",
            "repair_rounds": max(0, len(attempts) - 1),
            "attempts": attempts,
            "failure_stage": "invalid_sql",
            "error": "; ".join(attempts[-1].get("validation", {}).get("errors", [])) if attempts else "no_sql_candidate",
        }
    )


def _run_structured_plan_repair_loop(
    prompt: str,
    schema_context: dict[str, Any],
    db: DuckDBDatabase,
    sql_validator: SQLValidator,
    client: LLMClient,
    *,
    plan: dict[str, Any] | None,
    max_repair_rounds: int,
    semantic_verify: bool,
) -> dict[str, Any]:
    attempts: list[dict[str, Any]] = []
    bundle = build_structured_sql_plan_prompt(prompt, schema_context, plan)
    candidate_plan = _normalize_structured_plan_candidate(_call_json(client, bundle.system_prompt, bundle.user_prompt))
    for round_index in range(max_repair_rounds + 1):
        compiled = compile_structured_sql_plan(candidate_plan, sql_validator.schema_index, schema_context)
        sql = str(compiled.get("sql") or "")
        validation = sql_validator.validate(sql) if compiled.get("ok") and sql else None
        ast = sql_validator.ast_summary(sql) if sql else {"parse_error": "empty_sql"}
        semantic = (
            verify_sql_plan_semantics(
                prompt,
                plan.get("evidence_source_plan") if isinstance(plan, dict) else {},
                candidate_plan,
                schema_context,
                str(candidate_plan.get("answer_intent") or (plan or {}).get("answer_intent") or schema_context.get("answer_intent") or ""),
            )
            if semantic_verify and compiled.get("ok")
            else {"ok": True, "errors": [], "warnings": [], "semantic_score": None, "repair_hint": ""}
        )
        attempt = {
            "round": round_index,
            "structured_sql_plan": candidate_plan,
            "plan_validation": {
                "ok": bool(compiled.get("ok")),
                "errors": compiled.get("errors", []),
                "warnings": compiled.get("warnings", []),
            },
            "semantic_verification": semantic,
            "compile": compiled,
            "sql": sql,
            "validation": validation.to_dict() if validation else {"ok": False, "errors": compiled.get("errors", [])},
            "ast_summary": ast,
            "executed": False,
        }
        if compiled.get("ok") and validation and validation.ok and semantic.get("ok"):
            execution = db.execute_sql(sql)
            attempt["executed"] = True
            attempt["execution_ok"] = bool(execution.get("ok"))
            attempts.append(redact_secrets(attempt))
            return redact_secrets(
                {
                    "ok": bool(execution.get("ok")),
                    "sql": sql,
                    "structured_sql_plan": candidate_plan,
                    "compiled_sql": compiled,
                    "validation": validation.to_dict(),
                    "ast_summary": ast,
                    "execution_result": _compact_sql_result(execution),
                    "repair_rounds": round_index,
                    "attempts": attempts,
                    "plan_validation_success": True,
                    "compile_success": True,
                    "sql_validation_success": True,
                    "semantic_repair_attempted": bool(semantic_verify and round_index > 0),
                    "semantic_repair_success": bool(semantic_verify and round_index > 0),
                    "final_semantic_score": semantic.get("semantic_score"),
                    "execution_success": bool(execution.get("ok")),
                    "failure_stage": None if execution.get("ok") else "sql_execution_failed",
                }
            )
        attempts.append(redact_secrets(attempt))
        if round_index >= max_repair_rounds:
            break
        errors = list(compiled.get("errors", []))
        if validation and not validation.ok:
            errors.extend(validation.errors)
        if semantic_verify and not semantic.get("ok"):
            errors.extend(semantic.get("errors", []))
            if semantic.get("repair_hint"):
                errors.append(f"Semantic repair hint: {semantic['repair_hint']}")
        repair = build_structured_sql_plan_repair_prompt(prompt, schema_context, candidate_plan, errors)
        candidate_plan = _normalize_structured_plan_candidate(_call_json(client, repair.system_prompt, repair.user_prompt))
    return redact_secrets(
        {
            "ok": False,
            "sql": attempts[-1]["sql"] if attempts else "",
            "structured_sql_plan": candidate_plan,
            "repair_rounds": max(0, len(attempts) - 1),
            "attempts": attempts,
            "plan_validation_success": False,
            "compile_success": False,
            "sql_validation_success": False,
            "semantic_repair_attempted": any(
                not (attempt.get("semantic_verification") or {}).get("ok", True) for attempt in attempts
            ),
            "semantic_repair_success": False,
            "final_semantic_score": (attempts[-1].get("semantic_verification") or {}).get("semantic_score") if attempts else None,
            "execution_success": False,
            "failure_stage": "sql_plan_unrepairable",
            "safe_answer": "I could not produce a validated SQL query from the available schema.",
            "error": "; ".join(attempts[-1].get("validation", {}).get("errors", [])) if attempts else "no_sql_plan_candidate",
        }
    )


def _run_multi_candidate_structured_plan_loop(
    prompt: str,
    schema_context: dict[str, Any],
    db: DuckDBDatabase,
    sql_validator: SQLValidator,
    client: LLMClient,
    *,
    plan: dict[str, Any] | None,
    semantic_verify: bool,
    execution_probe: bool,
) -> dict[str, Any]:
    bundle = build_multi_candidate_structured_sql_plan_prompt(prompt, schema_context, plan)
    raw = _call_json(client, bundle.system_prompt, bundle.user_prompt)
    candidates = normalize_multi_candidate_plans(raw)
    retry_used = False
    if not candidates:
        retry_used = True
        correction = client.generate(
            bundle.system_prompt + " Correct your previous output and return valid JSON with exactly three candidates.",
            bundle.user_prompt,
        )
        raw = parse_json_object(correction.get("content", ""))
        raw["_usage"] = correction.get("usage", {})
        candidates = normalize_multi_candidate_plans(raw)
    ranked = rank_sql_plan_candidates(
        prompt,
        str((plan or {}).get("answer_intent") or schema_context.get("answer_intent") or ""),
        schema_context,
        candidates,
        sql_validator.schema_index,
        sql_validator,
        db=db,
        execution_probe=execution_probe,
        evidence_source_plan=(plan or {}).get("evidence_source_plan") if isinstance(plan, dict) else None,
    )
    attempts: list[dict[str, Any]] = []
    for item in ranked.get("ranking", []):
        compiled = item.get("compiled") if isinstance(item.get("compiled"), dict) else {}
        sql = str(compiled.get("sql") or "")
        validation_dict = item.get("validation") if isinstance(item.get("validation"), dict) else {}
        attempt = {
            "round": 0,
            "candidate_id": item.get("candidate_id"),
            "structured_sql_plan": item.get("candidate"),
            "plan_validation": {"ok": bool(compiled.get("ok")), "errors": compiled.get("errors", []), "warnings": compiled.get("warnings", [])},
            "semantic_verification": item.get("semantic_verification"),
            "compile": compiled,
            "sql": sql,
            "validation": validation_dict,
            "ast_summary": sql_validator.ast_summary(sql) if sql else {"parse_error": "empty_sql"},
            "probe": item.get("probe"),
            "executed": False,
        }
        if not item.get("accepted") or not sql:
            attempts.append(redact_secrets(attempt))
            continue
        execution = db.execute_sql(sql)
        attempt["executed"] = True
        attempt["execution_ok"] = bool(execution.get("ok"))
        attempts.append(redact_secrets(attempt))
        if execution.get("ok"):
            return redact_secrets(
                {
                    "ok": True,
                    "sql": sql,
                    "structured_sql_plan": item.get("candidate"),
                    "compiled_sql": compiled,
                    "validation": validation_dict,
                    "ast_summary": attempt["ast_summary"],
                    "execution_result": _compact_sql_result(execution),
                    "repair_rounds": 0,
                    "attempts": attempts,
                    "candidate_count": len(candidates),
                    "selected_candidate_id": item.get("candidate_id"),
                    "candidate_ranking": ranked,
                    "multi_candidate_retry_used": retry_used,
                    "plan_validation_success": True,
                    "compile_success": True,
                    "sql_validation_success": bool(validation_dict.get("ok")),
                    "semantic_repair_attempted": False,
                    "semantic_repair_success": False,
                    "final_semantic_score": (item.get("semantic_verification") or {}).get("semantic_score"),
                    "execution_success": True,
                    "failure_stage": None,
                }
            )
    return redact_secrets(
        {
            "ok": False,
            "sql": attempts[0]["sql"] if attempts else "",
            "structured_sql_plan": attempts[0].get("structured_sql_plan") if attempts else {},
            "repair_rounds": 0,
            "attempts": attempts,
            "candidate_count": len(candidates),
            "selected_candidate_id": None,
            "candidate_ranking": ranked,
            "multi_candidate_retry_used": retry_used,
            "plan_validation_success": False,
            "compile_success": False,
            "sql_validation_success": False,
            "semantic_repair_attempted": False,
            "semantic_repair_success": False,
            "final_semantic_score": None,
            "execution_success": False,
            "failure_stage": "sql_plan_unrepairable",
            "safe_answer": "I could not produce a validated SQL query from the available schema.",
            "error": "no multi-candidate SQL plan compiled, validated, semantically matched, and executed",
        }
    )


def _semantic_repair_attempted(attempts: list[dict[str, Any]]) -> bool:
    return any(not (attempt.get("semantic_verification") or {}).get("ok", True) for attempt in attempts[:-1])


def _call_json(client: LLMClient, system_prompt: str, user_prompt: str) -> dict[str, Any]:
    response = client.generate(system_prompt, user_prompt)
    parsed = parse_json_object(response.get("content", ""))
    parsed["_usage"] = response.get("usage", {})
    return parsed


def _normalize_structured_plan_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(candidate, dict):
        return {}
    if candidate.get("primary_table") or candidate.get("tables_needed"):
        return candidate
    for key in ("structured_sql_plan", "sql_plan", "plan", "primary_plan"):
        nested = candidate.get(key)
        if isinstance(nested, dict) and (nested.get("primary_table") or nested.get("tables_needed")):
            normalized = dict(nested)
            if "_usage" not in normalized and "_usage" in candidate:
                normalized["_usage"] = candidate["_usage"]
            return normalized
    return candidate


def _compact_sql_result(result: dict[str, Any]) -> dict[str, Any]:
    rows = result.get("rows")
    return {
        "ok": bool(result.get("ok")),
        "row_count": result.get("row_count"),
        "rows": rows[:5] if isinstance(rows, list) else [],
        "limited": result.get("limited"),
        "error": result.get("error"),
    }
