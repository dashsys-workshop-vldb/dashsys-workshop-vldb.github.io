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
    grounding_mode: str = "default",
) -> dict[str, Any]:
    sql_evidence = (
        build_sql_execution_evidence(str(sql_result.get("original_sql") or sql_result.get("sql") or ""), sql_result)
        if isinstance(sql_result, dict)
        else None
    )
    api_evidence = build_api_evidence(api_endpoint_id, api_result) if isinstance(api_result, dict) else None
    answer = str(model_answer or "").strip()
    fallback_used = False
    arbitration = _arbitration_mode(evidence_need, sql_evidence, api_evidence)
    v3_mode = str(grounding_mode or "").lower() in {
        "balanced_sql_api_answer_v3",
        "sql_lift_api_recovery_v3",
        "answer_fallback_v3",
    }
    if sql_evidence and sql_evidence.get("sql_executed"):
        deterministic = (
            _combined_answer_v3(prompt, sql_evidence, api_evidence, answer_intent, arbitration)
            if v3_mode
            else _combined_answer(prompt, sql_evidence, api_evidence, answer_intent, arbitration)
        )
        if not _answer_uses_sql(answer, sql_evidence) or (_api_required(evidence_need) and not _answer_uses_api(answer, api_evidence)):
            answer = deterministic
            fallback_used = True
    elif api_evidence:
        deterministic = _answer_from_api_evidence_v3(api_evidence) if v3_mode else _answer_from_api_evidence(api_evidence)
        if not answer or not _answer_uses_api(answer, api_evidence):
            answer = deterministic
            fallback_used = True
    if _unsupported_claim_count(answer, sql_evidence) > 0:
        answer = (
            _combined_answer_v3(prompt, sql_evidence, api_evidence, answer_intent, arbitration)
            if v3_mode and sql_evidence
            else _combined_answer(prompt, sql_evidence, api_evidence, answer_intent, arbitration)
            if sql_evidence
            else _answer_from_api_evidence_v3(api_evidence)
            if v3_mode
            else _answer_from_api_evidence(api_evidence)
        )
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
            "sql_evidence_object_available": bool(sql_evidence),
            "sql_evidence_used_in_answer": answer_used_sql,
            "fallback_to_sql_evidence_answer": bool(fallback_used and sql_evidence),
            "api_evidence_object_available": bool(api_evidence),
            "api_evidence_used_in_answer": answer_used_api,
            "fallback_to_api_evidence_answer": bool(fallback_used and api_evidence),
            "sql_api_arbitration_mode": arbitration,
            "grounding_mode": grounding_mode,
        }
    )


def _answer_from_sql(prompt: str, evidence: dict[str, Any] | None, intent: str) -> str:
    if not evidence or not evidence.get("sql_executed"):
        return "I could not produce a supported answer from SQL evidence."
    if evidence.get("zero_rows"):
        if any(marker in prompt.lower() for marker in ("connected", "linked", "associated", "mapped")):
            entity = _prompt_entity(prompt)
            suffix = f" for {entity}" if entity else " for this query context"
            return f"Based on the evidence provided, there is no data available to answer this question. The SQL query returned zero rows{suffix}."
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


def _combined_answer_v3(
    prompt: str,
    sql_evidence: dict[str, Any] | None,
    api_evidence: dict[str, Any] | None,
    intent: str,
    arbitration: str,
) -> str:
    effective_intent = _effective_intent(prompt, intent)
    sql_part = _answer_from_sql_v3(prompt, sql_evidence, effective_intent) if sql_evidence else ""
    api_part = _answer_from_api_evidence_v3(api_evidence) if api_evidence else ""
    sql_useful = bool(sql_evidence and _sql_evidence_directly_answers(prompt, sql_evidence, effective_intent))
    api_useful = bool(api_evidence and _api_evidence_useful(api_evidence))

    if arbitration == "api_primary_sql_context":
        parts = [api_part] if api_part else []
        if sql_useful and sql_part:
            parts.append(sql_part)
        return " ".join(parts).strip() or sql_part or "The available evidence is insufficient to answer."
    if arbitration in {"sql_primary_api_verify", "sql_only"}:
        parts = []
        if sql_part and (sql_useful or arbitration == "sql_only" or not api_useful):
            parts.append(sql_part)
        if api_part and (api_useful or not parts):
            parts.append(api_part)
        return " ".join(parts).strip() or "The available evidence is insufficient to answer."
    parts = []
    if sql_useful and sql_part:
        parts.append(sql_part)
    if api_part:
        parts.append(api_part)
    return " ".join(parts).strip() or sql_part or "The available evidence is insufficient to answer."


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


def _answer_from_sql_v3(prompt: str, evidence: dict[str, Any] | None, intent: str) -> str:
    if not evidence or not evidence.get("sql_executed"):
        return "I could not produce a supported answer from SQL evidence."
    if evidence.get("zero_rows"):
        return "SQL returned no matching records."
    if evidence.get("count_value") is not None:
        return f"The SQL evidence shows {evidence['count_value']} matching records."

    key_names = _nonblank_values(evidence.get("key_names") or [])
    key_ids = _nonblank_values(evidence.get("key_ids") or [])
    statuses = _nonblank_values(evidence.get("status_values") or [])
    timestamps = _nonblank_values(evidence.get("timestamp_values") or [])
    effective_intent = _effective_intent(prompt, intent)
    if effective_intent == "DATE" and timestamps:
        prefix = f"{key_names[0]}: " if key_names else ""
        return f"The SQL evidence shows {prefix}{timestamps[0]}."
    if effective_intent == "STATUS" and statuses:
        prefix = f"{key_names[0]}: " if key_names else ""
        return f"The SQL evidence shows {prefix}status {statuses[0]}."
    if "field" in prompt.lower():
        field_values = _field_values(evidence.get("rows_preview") or [])
        if field_values:
            entity = _prompt_entity(prompt)
            field = str(field_values[0])
            human = _humanize_field(field)
            if entity and human:
                return f"The field for {entity} is {field}, the {human} property."
            if entity:
                return f"The field for {entity} is {field}."
            return f"The SQL evidence returns field value {field}."
        entity = _prompt_entity(prompt)
        target = f" for {entity}" if entity else ""
        return f"The SQL evidence returned rows, but it did not provide a grounded field value{target}."
    if key_names or key_ids:
        values = key_names[:5] or key_ids[:5]
        return "The SQL evidence returns: " + ", ".join(str(value) for value in values) + "."
    row_summary = _row_summary(evidence.get("rows_preview") or [])
    if row_summary:
        return "The SQL evidence returns: " + row_summary + "."
    entity = _prompt_entity(prompt)
    if "field" in prompt.lower():
        target = f" for {entity}" if entity else ""
        return f"The SQL evidence returned rows, but it did not provide a grounded field value{target}."
    rows = evidence.get("row_count")
    if rows:
        return f"The SQL evidence returned {rows} rows, but it did not expose a usable answer value."
    return "The SQL evidence is available but does not expose a usable answer value."


def _answer_from_api_evidence_v3(api_evidence: dict[str, Any] | None) -> str:
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
        details.append("names: " + ", ".join(str(value) for value in _nonblank_values(api_evidence["names"])[:5]))
    if api_evidence.get("ids"):
        details.append("ids: " + ", ".join(str(value) for value in _nonblank_values(api_evidence["ids"])[:5]))
    if api_evidence.get("statuses"):
        details.append("statuses: " + ", ".join(str(value) for value in _nonblank_values(api_evidence["statuses"])[:5]))
    if api_evidence.get("timestamps"):
        details.append("timestamps: " + ", ".join(str(value) for value in _nonblank_values(api_evidence["timestamps"])[:3]))
    if api_evidence.get("counts"):
        counts = [str(value) for value in _nonblank_values(api_evidence["counts"])[:3]]
        if counts:
            details.append("counts: " + ", ".join(counts))
    if details:
        return f"The API evidence from {endpoint} includes " + "; ".join(item for item in details if not item.endswith(": ")) + "."
    return f"The API evidence from {endpoint} was retrieved successfully."


def _answer_uses_sql(answer: str, evidence: dict[str, Any]) -> bool:
    text = answer.lower()
    if evidence.get("sql_executed") and "sql evidence" in text:
        return True
    if evidence.get("zero_rows") and "no matching" in text:
        return True
    values = []
    for key in ("count_value",):
        if evidence.get(key) is not None:
            values.append(str(evidence[key]).lower())
    for key in ("key_ids", "key_names", "status_values", "timestamp_values"):
        values.extend(str(value).lower() for value in _nonblank_values(evidence.get(key) or []))
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


def _effective_intent(prompt: str, intent: str) -> str:
    text = prompt.lower()
    current = str(intent or "").upper()
    if any(marker in text for marker in ("how many", "number of", "count", "total ")):
        return "COUNT"
    if any(marker in text for marker in ("when", "published", "deployed", "created", "updated", "modified")):
        return "DATE"
    if any(marker in text for marker in ("status", "state", "active", "inactive", "failed", "succeeded")):
        return "STATUS"
    if any(marker in text for marker in ("list", "show", "give me", "export")):
        return "LIST" if current not in {"DATE", "STATUS"} else current
    return current or "DETAIL"


def _sql_evidence_directly_answers(prompt: str, evidence: dict[str, Any], intent: str) -> bool:
    if not evidence.get("sql_executed"):
        return False
    if evidence.get("zero_rows"):
        return True
    effective_intent = _effective_intent(prompt, intent)
    if evidence.get("count_value") is not None:
        return effective_intent == "COUNT"
    if effective_intent == "DATE":
        return bool(_nonblank_values(evidence.get("timestamp_values") or [])) or (
            bool(_nonblank_values(evidence.get("key_names") or [])) and _sql_mentions_prompt_entity(prompt, evidence)
        )
    if effective_intent == "STATUS":
        return bool(_nonblank_values(evidence.get("status_values") or []))
    if _prompt_entity(prompt) and not _sql_mentions_prompt_entity(prompt, evidence):
        return False
    return bool(
        _nonblank_values(evidence.get("key_names") or [])
        or _nonblank_values(evidence.get("key_ids") or [])
        or _row_summary(evidence.get("rows_preview") or [])
    )


def _api_evidence_useful(api_evidence: dict[str, Any]) -> bool:
    return bool(
        api_evidence.get("live_success")
        or api_evidence.get("live_empty")
        or api_evidence.get("api_error")
        or api_evidence.get("dry_run")
    )


def _sql_mentions_prompt_entity(prompt: str, evidence: dict[str, Any]) -> bool:
    entity = _prompt_entity(prompt)
    if not entity:
        return True
    needle = entity.lower()
    sql = str(evidence.get("sql") or "").lower()
    if needle in sql:
        return True
    for row in evidence.get("rows_preview") or []:
        if any(needle in str(value).lower() for value in row.values() if value is not None):
            return True
    return False


def _prompt_entity(prompt: str) -> str:
    quoted = re.findall(r"'([^']+)'|\"([^\"]+)\"", prompt)
    if quoted:
        return next((left or right for left, right in quoted if (left or right)), "")
    match = re.search(r"\bfor\s+(.+?)(?:[?.]|$)", prompt, flags=re.IGNORECASE)
    return match.group(1).strip() if match else ""


def _row_summary(rows: list[dict[str, Any]]) -> str:
    fragments = []
    for row in rows[:3]:
        pairs = []
        for key, value in row.items():
            if _is_blank(value):
                continue
            pairs.append(f"{key}: {value}")
            if len(pairs) >= 3:
                break
        if pairs:
            fragments.append("; ".join(pairs))
    return " | ".join(fragments)


def _field_value_summary(rows: list[dict[str, Any]]) -> str:
    values = []
    for row in rows[:3]:
        for key, value in row.items():
            normalized = key.lower().replace("_", "")
            if normalized.endswith("id") or _is_blank(value):
                continue
            if any(marker in normalized for marker in ("property", "field", "display", "desc", "name", "title")):
                values.append(f"{key}: {value}")
                break
    return " | ".join(values)


def _field_values(rows: list[dict[str, Any]]) -> list[Any]:
    values = []
    for row in rows[:5]:
        for key, value in row.items():
            normalized = key.lower().replace("_", "")
            if _is_blank(value):
                continue
            if normalized == "propertyid" or (normalized.endswith("id") and normalized != "property"):
                continue
            if any(marker in normalized for marker in ("property", "field", "display", "desc", "name", "title")):
                values.append(value)
                break
    return values


def _humanize_field(value: str) -> str:
    leaf = str(value).split(".")[-1].split(":")[-1]
    words = re.sub(r"([a-z])([A-Z])", r"\1 \2", leaf).replace("_", " ").replace("-", " ")
    words = " ".join(part.lower() for part in words.split() if part)
    return words


def _nonblank_values(values: list[Any]) -> list[Any]:
    return [value for value in values if not _is_blank(value)]


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, dict):
        return not any(not _is_blank(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return not any(not _is_blank(item) for item in value)
    return str(value).strip() == ""


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
