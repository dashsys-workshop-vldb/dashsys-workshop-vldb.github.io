from __future__ import annotations

import json
import re
from typing import Any

from .db import is_read_only_sql
from .llm_client import LLMClient, get_llm_client
from .trajectory import compact_preview, redact_secrets


def generate_sql_with_llm(
    query: str,
    schema_context: dict[str, Any],
    llm_client: LLMClient | None = None,
    mode: str = "candidate_guided",
) -> dict[str, Any]:
    client = llm_client or get_llm_client()
    if not client.available():
        reason = client.generate_messages([]).get("reason", "LLM provider API key is not set")
        return {
            "ok": False,
            "sql": "",
            "reasoning_summary": "",
            "provider": client.provider_name(),
            "model": client.model_name(),
            "mode": mode,
            "skipped": True,
            "error": reason,
        }
    system_prompt = (
        "You generate read-only DuckDB SQL for DASHSys. Use only the provided schema. "
        "Do not invent table or column names. Do not use destructive SQL. "
        'Return strict JSON only: {"sql":"...","reasoning_summary":"..."}'
    )
    user_prompt = json.dumps(
        {
            "query": query,
            "mode": mode,
            "schema_context": compact_preview(schema_context, 9000),
        },
        indent=2,
        default=str,
    )
    response = client.generate(system_prompt, user_prompt)
    parsed = _parse_json_response(response.get("content", ""))
    sql = str(parsed.get("sql") or "").strip()
    reason = str(parsed.get("reasoning_summary") or parsed.get("reason") or "").strip()
    validation = validate_sql_against_context(sql, schema_context)
    return redact_secrets(
        {
            "ok": bool(sql) and validation["ok"],
            "sql": sql,
            "reasoning_summary": reason,
            "provider": client.provider_name(),
            "model": client.model_name(),
            "mode": mode,
            "skipped": False,
            "validation": validation,
            "error": None if validation["ok"] else "; ".join(validation["errors"]),
            "raw_preview": response.get("raw_preview"),
        }
    )


def repair_sql_with_llm(
    query: str,
    bad_sql: str,
    validation_errors: list[str],
    schema_context: dict[str, Any],
    llm_client: LLMClient | None = None,
) -> dict[str, Any]:
    client = llm_client or get_llm_client()
    if not client.available():
        reason = client.generate_messages([]).get("reason", "LLM provider API key is not set")
        return {
            "ok": False,
            "sql": "",
            "reasoning_summary": "",
            "provider": client.provider_name(),
            "model": client.model_name(),
            "mode": "repair",
            "skipped": True,
            "error": reason,
        }
    system_prompt = (
        "Repair invalid read-only DuckDB SQL for DASHSys using only the provided schema and validator errors. "
        'Return strict JSON only: {"sql":"...","reasoning_summary":"..."}'
    )
    user_prompt = json.dumps(
        {
            "query": query,
            "bad_sql": bad_sql,
            "validation_errors": validation_errors,
            "schema_context": compact_preview(schema_context, 9000),
        },
        indent=2,
        default=str,
    )
    response = client.generate(system_prompt, user_prompt)
    parsed = _parse_json_response(response.get("content", ""))
    sql = str(parsed.get("sql") or "").strip()
    reason = str(parsed.get("reasoning_summary") or parsed.get("reason") or "").strip()
    validation = validate_sql_against_context(sql, schema_context)
    return redact_secrets(
        {
            "ok": bool(sql) and validation["ok"],
            "sql": sql,
            "reasoning_summary": reason,
            "provider": client.provider_name(),
            "model": client.model_name(),
            "mode": "repair",
            "skipped": False,
            "validation": validation,
            "error": None if validation["ok"] else "; ".join(validation["errors"]),
            "raw_preview": response.get("raw_preview"),
        }
    )


def validate_sql_against_context(sql: str, schema_context: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    ok, error = is_read_only_sql(sql)
    if not ok:
        errors.append(error or "SQL is not read-only.")
        return {"ok": False, "errors": errors, "warnings": []}
    tables = _context_tables(schema_context)
    referenced_tables = _extract_referenced_tables(sql)
    for table in referenced_tables:
        if tables and table not in tables:
            errors.append(f"Unknown or out-of-context table: {table}")
    return {"ok": not errors, "errors": errors, "warnings": []}


def _parse_json_response(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            return {}
        try:
            parsed = json.loads(match.group(0))
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}


def _context_tables(schema_context: dict[str, Any]) -> set[str]:
    if "tables" in schema_context and isinstance(schema_context["tables"], dict):
        return set(schema_context["tables"])
    if "candidate_tables" in schema_context:
        return {str(table) for table in schema_context.get("candidate_tables", [])}
    return set()


def _extract_referenced_tables(sql: str) -> list[str]:
    matches = re.findall(r"\b(?:FROM|JOIN)\s+(?:\"([^\"]+)\"|([A-Za-z_][\w$]*))", sql, flags=re.IGNORECASE)
    return [quoted or bare for quoted, bare in matches]
