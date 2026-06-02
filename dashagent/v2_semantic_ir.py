from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any


ALLOWED_SEMANTIC_IR_ROUTES = {"DIRECT", "EVIDENCE"}
ALLOWED_SEMANTIC_IR_KINDS = {"CONCEPT", "LOCAL_QUERY", "LIVE_QUERY", "LOCAL_AND_LIVE", "AGGREGATE", "CACHE_ALIAS"}
ALLOWED_SEMANTIC_IR_OPERATIONS = {"EXPLAIN", "LIST", "COUNT", "LOOKUP", "STATUS", "DATE", "COMPARE"}
ALLOWED_SEMANTIC_IR_SOURCES = {"NONE", "LOCAL_SNAPSHOT", "LIVE_API", "BOTH"}
ALLOWED_SEMANTIC_IR_FILTER_OPS = {"=", "!=", "contains", "in", ">=", "<=", ">", "<"}
ALLOWED_RESULT_CONTRACT_SCOPES = {"concept", "local", "live", "both"}
ALLOWED_RESULT_CONTRACT_FRESHNESS = {"same_run"}


@dataclass
class SemanticIRFilter:
    field: str
    op: str
    value: Any

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LocalQueryIR:
    table: str
    fields: list[str] = field(default_factory=list)
    filters: list[SemanticIRFilter] = field(default_factory=list)
    limit: int | None = 50
    count: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "table": self.table,
            "fields": list(self.fields),
            "filters": [item.to_dict() for item in self.filters],
            "limit": self.limit,
            "count": self.count,
        }


@dataclass
class APIQueryIR:
    endpoint_id: str
    method: str = "GET"
    path_params: dict[str, Any] = field(default_factory=dict)
    query_params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ResultContractIR:
    source: str
    object: str | None
    entity: str | None
    operation: str
    fields: list[str] = field(default_factory=list)
    filters: list[SemanticIRFilter] = field(default_factory=list)
    scope: str = "local"
    freshness: str = "same_run"

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "object": self.object,
            "entity": self.entity,
            "operation": self.operation,
            "fields": list(self.fields),
            "filters": [item.to_dict() for item in self.filters],
            "scope": self.scope,
            "freshness": self.freshness,
        }


@dataclass
class SemanticIRTask:
    task_id: str
    kind: str
    operation: str
    source: str
    local_query: LocalQueryIR | None = None
    api_query: APIQueryIR | None = None
    depends_on: list[str] = field(default_factory=list)
    description: str = ""
    required: bool = True
    reuse_result_from: str | None = None
    semantic_cache_key: str | None = None
    result_contract: ResultContractIR | None = None
    requires_raw_sql_fallback: bool = False
    raw_sql_reason: str | None = None
    unsupported_features: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "kind": self.kind,
            "operation": self.operation,
            "source": self.source,
            "local_query": self.local_query.to_dict() if self.local_query else None,
            "api_query": self.api_query.to_dict() if self.api_query else None,
            "depends_on": list(self.depends_on),
            "description": self.description,
            "required": self.required,
            "reuse_result_from": self.reuse_result_from,
            "semantic_cache_key": self.semantic_cache_key,
            "result_contract": self.result_contract.to_dict() if self.result_contract else None,
            "requires_raw_sql_fallback": self.requires_raw_sql_fallback,
            "raw_sql_reason": self.raw_sql_reason,
            "unsupported_features": list(self.unsupported_features),
        }


@dataclass
class SemanticIRPlan:
    route: str
    direct_answer: str | None = None
    tasks: list[SemanticIRTask] = field(default_factory=list)
    aggregation_instruction: str = ""

    def to_dict(self) -> dict[str, Any]:
        return semantic_plan_to_dict(self)


def semantic_plan_to_dict(plan: SemanticIRPlan) -> dict[str, Any]:
    return {
        "route": plan.route,
        "direct_answer": plan.direct_answer,
        "tasks": [task.to_dict() for task in plan.tasks],
        "aggregation_instruction": plan.aggregation_instruction,
    }


def parse_semantic_ir_from_json_or_line_protocol(raw: str | dict[str, Any]) -> SemanticIRPlan:
    payload = raw if isinstance(raw, dict) else _extract_json_object(str(raw or ""))
    if not isinstance(payload, dict):
        raise ValueError("Semantic IR payload must be a JSON object.")
    route = _enum(payload.get("route"), ALLOWED_SEMANTIC_IR_ROUTES, "route")
    direct_answer = payload.get("direct_answer")
    if direct_answer is not None:
        direct_answer = str(direct_answer).strip() or None
    tasks_raw = payload.get("tasks")
    if tasks_raw is None:
        tasks_raw = []
    if not isinstance(tasks_raw, list):
        raise ValueError("tasks must be a list.")
    tasks = [_parse_task(item, index) for index, item in enumerate(tasks_raw, start=1)]
    return SemanticIRPlan(
        route=route,
        direct_answer=direct_answer,
        tasks=tasks,
        aggregation_instruction=str(payload.get("aggregation_instruction") or "").strip(),
    )


def _parse_task(item: Any, index: int) -> SemanticIRTask:
    if not isinstance(item, dict):
        raise ValueError(f"tasks[{index}] must be an object.")
    task_id = str(item.get("task_id") or item.get("id") or f"t{index}").strip()
    kind = _enum(item.get("kind"), ALLOWED_SEMANTIC_IR_KINDS, "kind")
    operation = _enum(item.get("operation"), ALLOWED_SEMANTIC_IR_OPERATIONS, "operation")
    source = _enum(item.get("source"), ALLOWED_SEMANTIC_IR_SOURCES, "source")
    depends_on_raw = item.get("depends_on") if isinstance(item.get("depends_on"), list) else []
    local_query = _parse_local_query(item.get("local_query"))
    api_query = _parse_api_query(item.get("api_query"))
    reuse_result_from = str(item.get("reuse_result_from") or "").strip() or None
    semantic_cache_key = str(item.get("semantic_cache_key") or "").strip() or None
    result_contract = _parse_result_contract(item.get("result_contract"))
    raw_sql_reason = str(item.get("raw_sql_reason") or "").strip() or None
    unsupported_raw = item.get("unsupported_features") if isinstance(item.get("unsupported_features"), list) else []
    return SemanticIRTask(
        task_id=task_id,
        kind=kind,
        operation=operation,
        source=source,
        local_query=local_query,
        api_query=api_query,
        depends_on=[str(dep).strip() for dep in depends_on_raw if str(dep).strip()],
        description=str(item.get("description") or "").strip(),
        required=bool(item.get("required", True)),
        reuse_result_from=reuse_result_from,
        semantic_cache_key=semantic_cache_key,
        result_contract=result_contract,
        requires_raw_sql_fallback=bool(item.get("requires_raw_sql_fallback", False)),
        raw_sql_reason=raw_sql_reason,
        unsupported_features=[str(feature).strip().upper() for feature in unsupported_raw if str(feature).strip()],
    )


def _parse_local_query(raw: Any) -> LocalQueryIR | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError("local_query must be an object or null.")
    fields_raw = raw.get("fields") if isinstance(raw.get("fields"), list) else []
    filters_raw = raw.get("filters") if isinstance(raw.get("filters"), list) else []
    limit = raw.get("limit", 50)
    if limit is not None:
        try:
            limit = int(limit)
        except Exception as exc:
            raise ValueError("local_query.limit must be an integer or null.") from exc
    return LocalQueryIR(
        table=str(raw.get("table") or "").strip(),
        fields=[str(field).strip() for field in fields_raw if str(field).strip()],
        filters=[_parse_filter(item) for item in filters_raw],
        limit=limit,
        count=bool(raw.get("count", False)),
    )


def _parse_filter(raw: Any) -> SemanticIRFilter:
    if not isinstance(raw, dict):
        raise ValueError("filter must be an object.")
    op = str(raw.get("op") or "").strip()
    if op not in ALLOWED_SEMANTIC_IR_FILTER_OPS:
        raise ValueError(f"filter op must be one of {sorted(ALLOWED_SEMANTIC_IR_FILTER_OPS)}.")
    return SemanticIRFilter(field=str(raw.get("field") or "").strip(), op=op, value=raw.get("value"))


def _parse_api_query(raw: Any) -> APIQueryIR | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError("api_query must be an object or null.")
    path_params = raw.get("path_params") if isinstance(raw.get("path_params"), dict) else {}
    query_params = raw.get("query_params") if isinstance(raw.get("query_params"), dict) else {}
    return APIQueryIR(
        endpoint_id=str(raw.get("endpoint_id") or "").strip(),
        method=str(raw.get("method") or "GET").strip().upper(),
        path_params=dict(path_params),
        query_params=dict(query_params),
    )


def _parse_result_contract(raw: Any) -> ResultContractIR | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError("result_contract must be an object or null.")
    fields_raw = raw.get("fields") if isinstance(raw.get("fields"), list) else []
    filters_raw = raw.get("filters") if isinstance(raw.get("filters"), list) else []
    scope = str(raw.get("scope") or "").strip().lower()
    if scope not in ALLOWED_RESULT_CONTRACT_SCOPES:
        raise ValueError(f"result_contract.scope must be one of {sorted(ALLOWED_RESULT_CONTRACT_SCOPES)}.")
    freshness = str(raw.get("freshness") or "").strip().lower()
    if freshness not in ALLOWED_RESULT_CONTRACT_FRESHNESS:
        raise ValueError(f"result_contract.freshness must be one of {sorted(ALLOWED_RESULT_CONTRACT_FRESHNESS)}.")
    obj = raw.get("object")
    entity = raw.get("entity")
    return ResultContractIR(
        source=_enum(raw.get("source"), ALLOWED_SEMANTIC_IR_SOURCES, "result_contract.source"),
        object=str(obj).strip() if obj is not None and str(obj).strip() else None,
        entity=str(entity).strip() if entity is not None and str(entity).strip() else None,
        operation=_enum(raw.get("operation"), ALLOWED_SEMANTIC_IR_OPERATIONS, "result_contract.operation"),
        fields=[str(field).strip() for field in fields_raw if str(field).strip()],
        filters=[_parse_filter(item) for item in filters_raw],
        scope=scope,
        freshness=freshness,
    )


def _enum(value: Any, allowed: set[str], field_name: str) -> str:
    normalized = str(value or "").strip().upper()
    if normalized not in allowed:
        raise ValueError(f"{field_name} must be one of {sorted(allowed)}.")
    return normalized


def _extract_json_object(raw: str) -> dict[str, Any]:
    text = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        text = fenced.group(1)
    if not text.startswith("{"):
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            text = text[start : end + 1]
    return json.loads(text)
