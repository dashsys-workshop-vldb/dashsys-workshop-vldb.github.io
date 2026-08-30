from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from typing import Any


SUPPORTED_LOCAL_OPERATIONS = {"LIST", "COUNT", "LOOKUP", "STATUS", "DATE"}
SUPPORTED_API_OPERATIONS = {"LIST", "COUNT", "LOOKUP", "STATUS", "DATE", "COMPARE"}
SUPPORTED_FILTER_OPS = {"=", "!=", "contains", "in", ">=", "<=", ">", "<"}
UNSUPPORTED_ADVANCED_FEATURES = {
    "JOIN",
    "GROUP_BY",
    "HAVING",
    "WINDOW",
    "UNION",
    "CTE",
    "WITH",
    "NESTED_SUBQUERY",
    "COMPUTED_COLUMN",
    "VENDOR_FUNCTION",
}
LOCAL_JOURNEY_REPAIR_FEATURE = "MISSING_LOCAL_JOURNEY_QUERY"
LOCAL_SCHEMA_REPAIR_FEATURE = "MISSING_LOCAL_SCHEMA_QUERY"
LOCAL_DATE_REPAIR_FEATURE = "MISSING_LOCAL_DATE_QUERY"


@dataclass
class IRSupportResult:
    supported: bool
    unsupported_reason: str | None = None
    unsupported_features: list[str] = field(default_factory=list)
    task_id: str | None = None
    operation: str | None = None
    recommended_action: str = "COMPILE"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def check_semantic_ir_support(
    plan: Any,
    allowed_schema: list[dict[str, Any]],
    allowed_api_context: list[dict[str, Any]],
    *,
    user_prompt: str | None = None,
) -> IRSupportResult:
    del allowed_api_context
    if str(getattr(plan, "route", "") or "").upper() == "DIRECT":
        return IRSupportResult(True, recommended_action="COMPILE")
    prompt_support = _check_prompt_source_support(plan, allowed_schema, user_prompt=user_prompt)
    if prompt_support is not None:
        return prompt_support
    for task in list(getattr(plan, "tasks", []) or []):
        if str(getattr(task, "kind", "") or "").upper() in {"CONCEPT", "AGGREGATE", "CACHE_ALIAS"}:
            continue
        result = check_local_query_support(task) if getattr(task, "local_query", None) is not None else None
        if result is not None and not result.supported:
            return result
        api_result = check_api_query_support(task) if getattr(task, "api_query", None) is not None else None
        if api_result is not None and not api_result.supported:
            return api_result
    return IRSupportResult(True, recommended_action="COMPILE")


def _check_prompt_source_support(plan: Any, allowed_schema: list[dict[str, Any]], *, user_prompt: str | None) -> IRSupportResult | None:
    if _prompt_requires_local_schema_evidence(user_prompt):
        if _has_local_schema_card(allowed_schema) and not _plan_has_local_schema_query(plan, allowed_schema):
            task = _first_executable_task(plan)
            return IRSupportResult(
                False,
                (
                    "Prompt asks for the user's schemas without an explicit live/API cue; the Semantic IR must include "
                    "an LLM-owned LOCAL_QUERY/LOCAL_SNAPSHOT task for local schema records. A LIVE_QUERY or DIRECT task "
                    "cannot replace the required local evidence."
                ),
                [LOCAL_SCHEMA_REPAIR_FEATURE],
                getattr(task, "task_id", None),
                getattr(task, "operation", None),
                "LLM_REPAIR_IR",
            )
    if _prompt_requires_local_date_evidence(user_prompt):
        if _has_local_date_schema_card(allowed_schema) and not _plan_has_local_date_query(plan, allowed_schema):
            task = _first_executable_task(plan)
            return IRSupportResult(
                False,
                (
                    "Prompt asks for a local journey/campaign date without an explicit live/API cue; the Semantic IR "
                    "must include an LLM-owned LOCAL_QUERY/LOCAL_SNAPSHOT task over a table with exact local date fields. "
                    "A LIVE_QUERY cannot replace the required local evidence."
                ),
                [LOCAL_DATE_REPAIR_FEATURE],
                getattr(task, "task_id", None),
                getattr(task, "operation", None),
                "LLM_REPAIR_IR",
            )
    if _prompt_requires_local_inactive_journey_evidence(user_prompt):
        if _has_local_journey_schema_card(allowed_schema) and not _plan_has_local_journey_query(plan, allowed_schema):
            task = _first_executable_task(plan)
            return IRSupportResult(
                False,
                (
                    "Prompt asks to show inactive journeys without an explicit live/API cue; the Semantic IR must include an "
                    "LLM-owned LOCAL_QUERY/LOCAL_SNAPSHOT task for local journey/campaign records. A LIVE_QUERY cannot replace "
                    "the required local evidence."
                ),
                [LOCAL_JOURNEY_REPAIR_FEATURE],
                getattr(task, "task_id", None),
                getattr(task, "operation", None),
                "LLM_REPAIR_IR",
            )
    return None


def _prompt_requires_local_schema_evidence(user_prompt: str | None) -> bool:
    text = f" {str(user_prompt or '').lower()} "
    if not text.strip():
        return False
    if not re.search(r"\bschemas?\b", text):
        return False
    if re.search(r"\b(what is|what does|phrase|mean|means|define|definition|why|reasons?)\b", text):
        return False
    if re.search(r"\b(live|current|platform|api|schema registry|adobe experience platform|real[- ]?time)\b", text):
        return False
    return bool(re.search(r"\b(my|do i have|have|show|list|give|count|how many|records?)\b", text))


def _prompt_requires_local_date_evidence(user_prompt: str | None) -> bool:
    text = f" {str(user_prompt or '').lower()} "
    if not text.strip():
        return False
    if not re.search(r"\b(journey|journeys|campaign|campaigns)\b", text):
        return False
    if not re.search(r"\b(when|date|published|created|updated|modified|deployed)\b", text):
        return False
    if re.search(r"\b(live|current|platform|api|adobe experience platform|real[- ]?time)\b", text):
        return False
    return True


def _prompt_requires_local_inactive_journey_evidence(user_prompt: str | None) -> bool:
    text = f" {str(user_prompt or '').lower()} "
    if not text.strip():
        return False
    if not re.search(r"\binactive\b", text):
        return False
    if not re.search(r"\b(journey|journeys|campaign|campaigns)\b", text):
        return False
    if not re.search(r"\b(show|list|give|display|find|which|what are)\b", text):
        return False
    if re.search(r"\b(live|current|platform|api|aep|adobe experience platform|real[- ]?time)\b", text):
        return False
    return True


def _has_local_journey_schema_card(allowed_schema: list[dict[str, Any]]) -> bool:
    return any(_schema_card_is_journey(row) for row in allowed_schema if isinstance(row, dict))


def _has_local_schema_card(allowed_schema: list[dict[str, Any]]) -> bool:
    return any(_schema_card_is_schema(row) for row in allowed_schema if isinstance(row, dict))


def _has_local_date_schema_card(allowed_schema: list[dict[str, Any]]) -> bool:
    return any(_schema_card_is_journey(row) and _schema_card_has_date_fields(row) for row in allowed_schema if isinstance(row, dict))


def _plan_has_local_schema_query(plan: Any, allowed_schema: list[dict[str, Any]]) -> bool:
    return _plan_has_local_query_matching(plan, allowed_schema, _schema_card_is_schema)


def _plan_has_local_journey_query(plan: Any, allowed_schema: list[dict[str, Any]]) -> bool:
    return _plan_has_local_query_matching(plan, allowed_schema, _schema_card_is_journey)


def _plan_has_local_date_query(plan: Any, allowed_schema: list[dict[str, Any]]) -> bool:
    return _plan_has_local_query_matching(plan, allowed_schema, lambda row: _schema_card_is_journey(row) and _schema_card_has_date_fields(row))


def _plan_has_local_query_matching(plan: Any, allowed_schema: list[dict[str, Any]], predicate: Any) -> bool:
    for task in list(getattr(plan, "tasks", []) or []):
        if getattr(task, "local_query", None) is None:
            continue
        source = str(getattr(task, "source", "") or "").upper()
        kind = str(getattr(task, "kind", "") or "").upper()
        if source not in {"LOCAL_SNAPSHOT", "BOTH"} and kind not in {"LOCAL_QUERY", "LOCAL_AND_LIVE"}:
            continue
        query = getattr(task, "local_query", None)
        table = str(getattr(query, "table", "") or "").lower()
        if any(str(row.get("table") or "").lower() == table and predicate(row) for row in allowed_schema if isinstance(row, dict)):
            return True
    return False


def _schema_card_is_schema(row: dict[str, Any]) -> bool:
    text = " ".join(
        [
            str(row.get("table") or ""),
            " ".join(str(item) for item in row.get("columns") or []),
            " ".join(str(item) for item in row.get("table_role_hints") or []),
        ]
    ).lower()
    return "schema" in text or "blueprint" in text or "xdm_schema" in text


def _schema_card_is_journey(row: dict[str, Any]) -> bool:
    text = " ".join(
        [
            str(row.get("table") or ""),
            " ".join(str(item) for item in row.get("columns") or []),
            " ".join(str(item) for item in row.get("table_role_hints") or []),
        ]
    ).lower()
    return "journey" in text or "campaign" in text


def _schema_card_has_date_fields(row: dict[str, Any]) -> bool:
    hints = row.get("field_hints") if isinstance(row.get("field_hints"), dict) else {}
    if hints.get("date_fields"):
        return True
    return any(re.search(r"(published|created|updated|modified|deployed|date|time)", str(field), flags=re.I) for field in row.get("columns") or [])


def _first_executable_task(plan: Any) -> Any | None:
    for task in list(getattr(plan, "tasks", []) or []):
        if getattr(task, "local_query", None) is not None or getattr(task, "api_query", None) is not None:
            return task
    return None


def check_local_query_support(task: Any) -> IRSupportResult:
    task_id = str(getattr(task, "task_id", "") or "")
    operation = str(getattr(task, "operation", "") or "").upper()
    features = _declared_unsupported_features(task)
    if operation not in SUPPORTED_LOCAL_OPERATIONS:
        return IRSupportResult(False, "Operation is outside supported LocalQueryIR v1.", ["UNKNOWN_OPERATION"], task_id, operation, "LLM_REPAIR_IR")
    if features:
        action = "RAW_SQL_FALLBACK" if str(getattr(task, "source", "") or "").upper() == "LOCAL_SNAPSHOT" else "FAIL_SAFE"
        return IRSupportResult(False, str(getattr(task, "raw_sql_reason", "") or "Semantic IR task declares unsupported local query features."), features, task_id, operation, action)
    query = getattr(task, "local_query", None)
    for item in list(getattr(query, "filters", []) or []):
        op = str(getattr(item, "op", "") or "")
        if op not in SUPPORTED_FILTER_OPS:
            return IRSupportResult(False, f"Filter operator {op} is outside supported LocalQueryIR v1.", ["UNSUPPORTED_FILTER_OP"], task_id, operation, "LLM_REPAIR_IR")
    return IRSupportResult(True, task_id=task_id, operation=operation, recommended_action="COMPILE")


def check_api_query_support(task: Any) -> IRSupportResult:
    task_id = str(getattr(task, "task_id", "") or "")
    operation = str(getattr(task, "operation", "") or "").upper()
    query = getattr(task, "api_query", None)
    method = str(getattr(query, "method", "") or "").upper()
    if operation not in SUPPORTED_API_OPERATIONS:
        return IRSupportResult(False, "Operation is outside supported APIQueryIR v1.", ["UNKNOWN_OPERATION"], task_id, operation, "LLM_REPAIR_IR")
    if method != "GET":
        return IRSupportResult(False, "APIQueryIR v1 supports GET only.", ["NON_GET_API_METHOD"], task_id, operation, "FAIL_SAFE")
    return IRSupportResult(True, task_id=task_id, operation=operation, recommended_action="COMPILE")


def _declared_unsupported_features(task: Any) -> list[str]:
    features: list[str] = []
    raw = getattr(task, "unsupported_features", None)
    if isinstance(raw, list):
        features.extend(str(item).strip().upper() for item in raw if str(item).strip())
    if bool(getattr(task, "requires_raw_sql_fallback", False)) and not features:
        features.append("RAW_SQL_REQUIRED")
    return [item for item in features if item in UNSUPPORTED_ADVANCED_FEATURES or item == "RAW_SQL_REQUIRED"]
