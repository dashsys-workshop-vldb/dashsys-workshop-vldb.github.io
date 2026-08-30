from __future__ import annotations

import re
from typing import Any

from .v2_semantic_ir import APIQueryIR, LocalQueryIR, SemanticIRPlan, SemanticIRTask


def compile_semantic_ir_to_plan_payload(
    plan: SemanticIRPlan,
    allowed_schema_card: list[dict[str, Any]],
    allowed_api_card: list[dict[str, Any]],
) -> dict[str, Any]:
    if plan.route == "DIRECT":
        direct_passes = [_compile_task(task, allowed_schema_card, allowed_api_card) for task in plan.tasks if task.kind == "CONCEPT"]
        return {
            "route": "LLM_DIRECT",
            "evidence_order": "NO_EVIDENCE",
            "direct_answer": plan.direct_answer,
            "passes": direct_passes,
            "answer_contract": plan.answer_contract.to_dict() if plan.answer_contract else None,
            "aggregation_instruction": plan.aggregation_instruction,
            "reason": "Semantic IR DIRECT route.",
        }
    passes = [_compile_task(task, allowed_schema_card, allowed_api_card) for task in plan.tasks]
    return {
        "route": "EVIDENCE_PIPELINE",
        "evidence_order": _evidence_order_for_passes(passes),
        "direct_answer": None,
        "passes": passes,
        "answer_contract": plan.answer_contract.to_dict() if plan.answer_contract else None,
        "aggregation_instruction": plan.aggregation_instruction,
        "reason": "Compiled mechanically from SDK toolcall Semantic IR.",
    }


def compile_local_query_to_sql(query: LocalQueryIR) -> dict[str, Any]:
    table = _quote_identifier(query.table)
    params: list[Any] = []
    if query.count:
        select = "COUNT(*) AS count"
    elif query.fields:
        select = ", ".join(_quote_identifier(field) for field in query.fields)
    else:
        select = "*"
    sql = f"SELECT {select} FROM {table}"
    where_clauses = []
    for item in query.filters:
        clause, values = _compile_filter(item.field, item.op, item.value)
        where_clauses.append(clause)
        params.extend(values)
    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)
    if not query.count:
        limit = query.limit if query.limit is not None else 50
        if int(limit) > 0:
            sql += f" LIMIT {int(limit)}"
    return {"query": sql, "params": params}


def compile_api_query_to_request(query: APIQueryIR, allowed_api_card: list[dict[str, Any]]) -> dict[str, Any]:
    endpoint = _find_endpoint(query.endpoint_id, allowed_api_card)
    if endpoint is None:
        raise ValueError(f"Unknown endpoint_id: {query.endpoint_id}")
    path = str(endpoint.get("path") or "")
    path_params = query.path_params or {}
    for name in endpoint.get("path_params") or []:
        if name not in path_params:
            raise ValueError(f"Missing path parameter {name} for endpoint {query.endpoint_id}.")
        path = path.replace("{" + str(name) + "}", str(path_params[name]))
    unresolved = re.findall(r"\{([^}]+)\}", path)
    if unresolved:
        raise ValueError(f"Unresolved path parameters for endpoint {query.endpoint_id}: {', '.join(unresolved)}")
    return {"method": str(query.method or "GET").upper(), "path": path, "params": dict(query.query_params or {})}


def _compile_task(task: SemanticIRTask, allowed_schema_card: list[dict[str, Any]], allowed_api_card: list[dict[str, Any]]) -> dict[str, Any]:
    sql = None
    api_request = None
    if task.kind == "CACHE_ALIAS":
        return {
            "pass_id": task.task_id,
            "task_id": task.task_id,
            "kind": "CACHE_ALIAS",
            "binding_id": task.binding_id,
            "subtask": task.description,
            "path": "CACHE_ALIAS",
            "can_run_parallel": False,
            "depends_on": list(task.depends_on),
            "evidence_order": "NO_EVIDENCE",
            "sql": None,
            "api_request": None,
            "expected_result": task.description,
            "optional": not bool(task.required),
            "fallback": False,
            "reuse_result_from": task.reuse_result_from,
            "semantic_cache_key": task.semantic_cache_key,
            "result_contract": task.result_contract.to_dict() if task.result_contract else None,
        }
    if task.local_query is not None and task.kind in {"LOCAL_QUERY", "LOCAL_AND_LIVE"}:
        sql = compile_local_query_to_sql(task.local_query)
    if task.api_query is not None and task.kind in {"LIVE_QUERY", "LOCAL_AND_LIVE"}:
        api_request = compile_api_query_to_request(task.api_query, allowed_api_card)
    return {
        "pass_id": task.task_id,
        "binding_id": task.binding_id or (task.local_query.binding_id if task.local_query else None),
        "subtask": task.description,
        "path": _path_for_task(task, sql, api_request),
        "can_run_parallel": not bool(task.depends_on),
        "depends_on": list(task.depends_on),
        "evidence_order": _evidence_order_for_task(task, sql, api_request),
        "sql": sql,
        "api_request": api_request,
        "expected_result": task.description,
        "optional": not bool(task.required),
        "fallback": False,
        "reuse_result_from": task.reuse_result_from,
        "semantic_cache_key": task.semantic_cache_key,
        "result_contract": task.result_contract.to_dict() if task.result_contract else None,
    }


def _path_for_task(task: SemanticIRTask, sql: dict[str, Any] | None, api_request: dict[str, Any] | None) -> str:
    if task.kind == "CONCEPT":
        return "DIRECT"
    if task.kind == "AGGREGATE":
        return "AGGREGATION_ONLY"
    if sql and api_request:
        return "SQL_AND_API"
    if sql:
        return "SQL"
    if api_request:
        return "API"
    return "AGGREGATION_ONLY"


def _evidence_order_for_task(task: SemanticIRTask, sql: dict[str, Any] | None, api_request: dict[str, Any] | None) -> str:
    if task.kind == "CONCEPT":
        return "NO_EVIDENCE"
    if sql and api_request:
        return "PARALLEL"
    if sql:
        return "SQL_FIRST"
    if api_request:
        return "API_FIRST"
    return "NO_EVIDENCE"


def _evidence_order_for_passes(passes: list[dict[str, Any]]) -> str:
    if len(passes) > 1:
        return "MULTI_PASS"
    if not passes:
        return "SQL_FIRST"
    return str(passes[0].get("evidence_order") or "SQL_FIRST")


def _compile_filter(field: str, op: str, value: Any) -> tuple[str, list[Any]]:
    column = _quote_identifier(field)
    if op == "contains":
        return f"LOWER({column}) LIKE LOWER(?)", [f"%{value}%"]
    if op == "in":
        values = value if isinstance(value, list) else [value]
        if not values:
            return "1 = 0", []
        placeholders = ", ".join("?" for _ in values)
        return f"{column} IN ({placeholders})", list(values)
    if op in {"=", "!=", ">=", "<=", ">", "<"}:
        return f"{column} {op} ?", [value]
    raise ValueError(f"Unsupported filter op: {op}")


def _quote_identifier(value: str) -> str:
    text = str(value or "")
    return '"' + text.replace('"', '""') + '"'


def _find_endpoint(endpoint_id: str, allowed_api_card: list[dict[str, Any]]) -> dict[str, Any] | None:
    wanted = str(endpoint_id or "").lower()
    for endpoint in allowed_api_card:
        if str(endpoint.get("endpoint_id") or "").lower() == wanted:
            return endpoint
    return None
