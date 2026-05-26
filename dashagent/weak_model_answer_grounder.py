from __future__ import annotations

import re
from typing import Any

from .llm_sql_execution_evidence_bridge import build_sql_execution_evidence
from .trajectory import redact_secrets
from .weak_model_api_evidence_bridge import build_api_evidence


def ground_weak_model_answer(
    prompt: str,
    *,
    model_answer: str,
    sql_result: dict[str, Any] | None,
    api_result: dict[str, Any] | None,
    answer_intent: str,
    evidence_need: str = "sql_first",
    api_endpoint_id: str = "",
) -> dict[str, Any]:
    sql_evidence = build_sql_execution_evidence("", sql_result) if isinstance(sql_result, dict) else None
    api_evidence = build_api_evidence(api_endpoint_id, api_result) if isinstance(api_result, dict) else None
    answer = str(model_answer or "").strip()
    fallback_used = False
    arbitration = _arbitration_mode(evidence_need, sql_evidence, api_evidence)
    if sql_evidence and sql_evidence.get("sql_executed"):
        deterministic = _combined_answer(prompt, sql_evidence, api_evidence, answer_intent, arbitration)
        if not _answer_uses_sql(answer, sql_evidence) or (_api_required(evidence_need) and not _answer_uses_api(answer, api_evidence)):
            answer = deterministic
            fallback_used = True
    elif api_evidence:
        deterministic = _answer_from_api_evidence(api_evidence)
        if not answer or not _answer_uses_api(answer, api_evidence):
            answer = deterministic
            fallback_used = True
    if _unsupported_claim_count(answer, sql_evidence) > 0:
        answer = _combined_answer(prompt, sql_evidence, api_evidence, answer_intent, arbitration) if sql_evidence else _answer_from_api_evidence(api_evidence)
        fallback_used = True
    answer_used_sql = bool(sql_evidence and _answer_uses_sql(answer, sql_evidence))
    answer_used_api = bool(api_evidence and _answer_uses_api(answer, api_evidence))
    return redact_secrets(
        {
            "answer": answer,
            "answer_used_sql": answer_used_sql,
            "answer_used_api": answer_used_api,
            "fallback_used": fallback_used,
            "unsupported_claim_count": 0,
            "unsupported_claims": [],
            "sql_evidence": sql_evidence,
            "api_evidence": api_evidence,
            "api_evidence_object_available": bool(api_evidence),
            "api_evidence_used_in_answer": answer_used_api,
            "fallback_to_api_evidence_answer": bool(fallback_used and api_evidence),
            "sql_api_arbitration_mode": arbitration,
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


def _combined_answer(
    prompt: str,
    sql_evidence: dict[str, Any] | None,
    api_evidence: dict[str, Any] | None,
    intent: str,
    arbitration: str,
) -> str:
    parts = []
    if arbitration == "api_primary_sql_context" and api_evidence:
        parts.append(_answer_from_api_evidence(api_evidence))
        if sql_evidence and sql_evidence.get("sql_executed"):
            parts.append(_answer_from_sql(prompt, sql_evidence, intent))
    else:
        if sql_evidence and sql_evidence.get("sql_executed"):
            parts.append(_answer_from_sql(prompt, sql_evidence, intent))
        if api_evidence:
            parts.append(_answer_from_api_evidence(api_evidence))
    return " ".join(part for part in parts if part).strip() or "The available evidence is insufficient to answer."


def _answer_from_api_evidence(api_evidence: dict[str, Any] | None) -> str:
    if not api_evidence:
        return "The API evidence is unavailable."
    endpoint = api_evidence.get("endpoint_id") or "selected endpoint"
    if api_evidence.get("live_empty"):
        return f"The API endpoint {endpoint} returned no matching records for this query context."
    if api_evidence.get("api_error"):
        return f"The API evidence from {endpoint} is unavailable due to an API error."
    if api_evidence.get("dry_run"):
        return f"The API call to {endpoint} was not executed live."
    details = []
    if api_evidence.get("names"):
        details.append("names: " + ", ".join(str(value) for value in api_evidence["names"][:5]))
    if api_evidence.get("ids"):
        details.append("ids: " + ", ".join(str(value) for value in api_evidence["ids"][:5]))
    if api_evidence.get("statuses"):
        details.append("statuses: " + ", ".join(str(value) for value in api_evidence["statuses"][:5]))
    if api_evidence.get("timestamps"):
        details.append("timestamps: " + ", ".join(str(value) for value in api_evidence["timestamps"][:3]))
    if details:
        return f"The API evidence from {endpoint} includes " + "; ".join(details) + "."
    return f"The API evidence from {endpoint} was retrieved successfully."


def _answer_uses_sql(answer: str, evidence: dict[str, Any]) -> bool:
    text = answer.lower()
    values = []
    for key in ("count_value",):
        if evidence.get(key) is not None:
            values.append(str(evidence[key]).lower())
    for key in ("key_ids", "key_names", "status_values", "timestamp_values"):
        values.extend(str(value).lower() for value in evidence.get(key) or [])
    return any(value and value in text for value in values)


def _answer_uses_api(answer: str, evidence: dict[str, Any] | None) -> bool:
    if not evidence:
        return False
    text = answer.lower()
    values: list[str] = []
    values.extend(str(value).lower() for value in evidence.get("ids") or [])
    values.extend(str(value).lower() for value in evidence.get("names") or [])
    values.extend(str(value).lower() for value in evidence.get("statuses") or [])
    values.extend(str(value).lower() for value in evidence.get("timestamps") or [])
    values.append(str(evidence.get("endpoint_id") or "").lower())
    if evidence.get("live_empty"):
        values.extend(["no matching records", "returned no matching"])
    if evidence.get("api_error"):
        values.extend(["api error", "unavailable"])
    if evidence.get("live_success"):
        values.extend(["api evidence", "retrieved successfully"])
    return any(value and value in text for value in values)


def _api_required(evidence_need: str) -> bool:
    return str(evidence_need).lower() in {
        "api_first",
        "api_only",
        "sql_then_api",
        "api_then_sql",
        "sql_primary_api_verify",
        "api_primary_sql_context",
    }


def _arbitration_mode(evidence_need: str, sql_evidence: dict[str, Any] | None, api_evidence: dict[str, Any] | None) -> str:
    need = str(evidence_need or "").lower()
    if need in {"api_primary_sql_context", "api_first", "api_only"}:
        return "api_primary_sql_context"
    if need in {"sql_primary_api_verify", "sql_then_api", "api_then_sql"}:
        return "sql_primary_api_verify"
    if sql_evidence:
        return "sql_only"
    if api_evidence:
        return "api_only"
    return "no_evidence"


def _unsupported_claim_count(answer: str, evidence: dict[str, Any] | None) -> int:
    if not answer or not evidence:
        return 0
    numbers = re.findall(r"\b\d+\b", answer)
    supported = {str(evidence.get("count_value"))} if evidence.get("count_value") is not None else set()
    return sum(1 for number in numbers if number not in supported and number not in {"0"})
