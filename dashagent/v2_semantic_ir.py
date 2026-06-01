from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any


ALLOWED_SEMANTIC_IR_ROUTES = {"DIRECT", "EVIDENCE"}
ALLOWED_SEMANTIC_IR_KINDS = {"CONCEPT", "LOCAL_QUERY", "LIVE_QUERY", "LOCAL_AND_LIVE", "AGGREGATE"}
ALLOWED_SEMANTIC_IR_OPERATIONS = {"EXPLAIN", "LIST", "COUNT", "LOOKUP", "STATUS", "DATE", "COMPARE"}
ALLOWED_SEMANTIC_IR_SOURCES = {"NONE", "LOCAL_SNAPSHOT", "LIVE_API", "BOTH"}
ALLOWED_SEMANTIC_IR_FILTER_OPS = {"=", "!=", "contains", "in", ">=", "<=", ">", "<"}


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
