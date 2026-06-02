from __future__ import annotations

from dataclasses import asdict, dataclass, field
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


def check_semantic_ir_support(plan: Any, allowed_schema: list[dict[str, Any]], allowed_api_context: list[dict[str, Any]]) -> IRSupportResult:
    del allowed_schema  # Existence is handled by SemanticIRValidator.
    del allowed_api_context
    if str(getattr(plan, "route", "") or "").upper() == "DIRECT":
        return IRSupportResult(True, recommended_action="COMPILE")
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
