from __future__ import annotations

from typing import Any

from .db import DuckDBDatabase
from .llm_client import LLMClient, get_llm_client
from .llm_tool_agent_prompts import build_sql_candidate_prompt, build_sql_repair_prompt, parse_json_object
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


def _call_json(client: LLMClient, system_prompt: str, user_prompt: str) -> dict[str, Any]:
    response = client.generate(system_prompt, user_prompt)
    parsed = parse_json_object(response.get("content", ""))
    parsed["_usage"] = response.get("usage", {})
    return parsed


def _compact_sql_result(result: dict[str, Any]) -> dict[str, Any]:
    rows = result.get("rows")
    return {
        "ok": bool(result.get("ok")),
        "row_count": result.get("row_count"),
        "rows": rows[:5] if isinstance(rows, list) else [],
        "limited": result.get("limited"),
        "error": result.get("error"),
    }
