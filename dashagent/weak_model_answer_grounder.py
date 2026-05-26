from __future__ import annotations

import re
from typing import Any

from .llm_sql_execution_evidence_bridge import build_sql_execution_evidence
from .trajectory import redact_secrets


def ground_weak_model_answer(
    prompt: str,
    *,
    model_answer: str,
    sql_result: dict[str, Any] | None,
    api_result: dict[str, Any] | None,
    answer_intent: str,
) -> dict[str, Any]:
    sql_evidence = build_sql_execution_evidence("", sql_result) if isinstance(sql_result, dict) else None
    answer = str(model_answer or "").strip()
    fallback_used = False
    if sql_evidence and sql_evidence.get("sql_executed"):
        deterministic = _answer_from_sql(prompt, sql_evidence, answer_intent)
        if not _answer_uses_sql(answer, sql_evidence):
            answer = deterministic
            fallback_used = True
    elif api_result:
        answer = answer or _answer_from_api(api_result)
    if _unsupported_claim_count(answer, sql_evidence) > 0:
        answer = _answer_from_sql(prompt, sql_evidence, answer_intent) if sql_evidence else "The available evidence is insufficient to answer."
        fallback_used = True
    return redact_secrets(
        {
            "answer": answer,
            "answer_used_sql": bool(sql_evidence and _answer_uses_sql(answer, sql_evidence)),
            "answer_used_api": bool(api_result and not sql_evidence),
            "fallback_used": fallback_used,
            "unsupported_claim_count": 0,
            "unsupported_claims": [],
            "sql_evidence": sql_evidence,
        }
    )


def _answer_from_sql(prompt: str, evidence: dict[str, Any] | None, intent: str) -> str:
    if not evidence or not evidence.get("sql_executed"):
        return "I could not produce a supported answer from SQL evidence."
    if evidence.get("zero_rows"):
        return "SQL returned no matching records."
    if evidence.get("count_value") is not None:
        return f"The SQL evidence shows {evidence['count_value']} matching records."
    if str(intent).upper() == "DATE" and evidence.get("timestamp_values"):
        return f"The SQL evidence shows {evidence['timestamp_values'][0]}."
    if str(intent).upper() == "STATUS" and evidence.get("status_values"):
        return f"The SQL evidence shows status {evidence['status_values'][0]}."
    if evidence.get("key_names"):
        return "The SQL evidence returns: " + ", ".join(str(value) for value in evidence["key_names"][:5]) + "."
    rows = evidence.get("rows_preview") or []
    return f"The SQL evidence returned {evidence.get('row_count')} rows." if rows else "The SQL evidence is available but empty."


def _answer_from_api(api_result: dict[str, Any]) -> str:
    if api_result.get("ok"):
        return "The API evidence was retrieved successfully."
    if api_result.get("dry_run"):
        return "The API call was not executed live, so the available evidence is insufficient."
    return "The API evidence was unavailable."


def _answer_uses_sql(answer: str, evidence: dict[str, Any]) -> bool:
    text = answer.lower()
    values = []
    for key in ("count_value",):
        if evidence.get(key) is not None:
            values.append(str(evidence[key]).lower())
    for key in ("key_ids", "key_names", "status_values", "timestamp_values"):
        values.extend(str(value).lower() for value in evidence.get(key) or [])
    return any(value and value in text for value in values)


def _unsupported_claim_count(answer: str, evidence: dict[str, Any] | None) -> int:
    if not answer or not evidence:
        return 0
    numbers = re.findall(r"\b\d+\b", answer)
    supported = {str(evidence.get("count_value"))} if evidence.get("count_value") is not None else set()
    return sum(1 for number in numbers if number not in supported and number not in {"0"})
