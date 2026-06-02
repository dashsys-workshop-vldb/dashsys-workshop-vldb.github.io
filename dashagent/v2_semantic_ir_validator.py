from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .v2_semantic_ir import (
    ALLOWED_SEMANTIC_IR_FILTER_OPS,
    APIQueryIR,
    LocalQueryIR,
    SemanticIRPlan,
    SemanticIRTask,
)
from .v2_semantic_alias import validate_semantic_ir_aliases


@dataclass
class SemanticIRValidationResult:
    passed: bool
    error_type: str | None = None
    error_message: str | None = None
    task_id: str | None = None
    allowed_tables: list[str] = field(default_factory=list)
    allowed_fields_for_table: list[str] = field(default_factory=list)
    allowed_endpoints: list[str] = field(default_factory=list)
    semantic_alias_validation_used: bool = False
    semantic_alias_validation_passed: bool | None = None
    semantic_alias_count: int = 0
    reuse_result_from: str | None = None
    alias_contract: dict[str, Any] | None = None
    producer_contract: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SemanticIRValidator:
    def __init__(self, allowed_schema_card: list[dict[str, Any]], allowed_api_card: list[dict[str, Any]]) -> None:
        self.allowed_schema_card = allowed_schema_card
        self.allowed_api_card = allowed_api_card
        self._tables = {str(row.get("table") or ""): [str(col) for col in row.get("columns") or []] for row in allowed_schema_card}
        self._table_key = {name.lower(): name for name in self._tables}
        self._endpoints = {str(row.get("endpoint_id") or ""): row for row in allowed_api_card}
        self._endpoint_key = {name.lower(): name for name in self._endpoints}

    def validate(self, plan: SemanticIRPlan) -> SemanticIRValidationResult:
        base = self._ok_context()
        if plan.route == "DIRECT":
            executable = [task for task in plan.tasks if task.kind in {"LOCAL_QUERY", "LIVE_QUERY", "LOCAL_AND_LIVE"}]
            if executable:
                return self._fail("direct_route_with_evidence_tasks", "DIRECT route cannot include evidence tasks.", executable[0].task_id)
            return base
        if plan.route != "EVIDENCE":
            return self._fail("invalid_route", f"Invalid route: {plan.route}")

        seen: set[str] = set()
        for task in plan.tasks:
            if not task.task_id:
                return self._fail("missing_task_id", "Task is missing task_id.")
            if task.task_id in seen:
                return self._fail("duplicate_task_id", f"Duplicate task_id: {task.task_id}", task.task_id)
            seen.add(task.task_id)
        for task in plan.tasks:
            for dep in task.depends_on:
                if dep not in seen:
                    return self._fail("unknown_dependency", f"Task {task.task_id} depends on unknown task {dep}.", task.task_id)
        if self._has_cycle(plan.tasks):
            return self._fail("dependency_cycle", "Task dependencies contain a cycle.")

        for task in plan.tasks:
            result = self._validate_task(task)
            if not result.passed:
                return result
        alias_result = validate_semantic_ir_aliases(plan)
        if not alias_result.passed:
            return self._fail(
                "invalid_semantic_alias",
                alias_result.message,
                alias_result.task_id,
                semantic_alias_validation_used=True,
                semantic_alias_validation_passed=False,
                semantic_alias_count=alias_result.semantic_alias_count,
                reuse_result_from=alias_result.reuse_result_from,
                alias_contract=alias_result.alias_contract,
                producer_contract=alias_result.producer_contract,
            )
        base.semantic_alias_validation_used = True
        base.semantic_alias_validation_passed = True
        base.semantic_alias_count = alias_result.semantic_alias_count
        return base

    def _validate_task(self, task: SemanticIRTask) -> SemanticIRValidationResult:
        if task.kind == "CACHE_ALIAS":
            if task.local_query is not None or task.api_query is not None:
                return self._fail("invalid_semantic_alias", "CACHE_ALIAS task must not contain local_query or api_query.", task.task_id)
            if not task.reuse_result_from:
                return self._fail("invalid_semantic_alias", "CACHE_ALIAS task requires reuse_result_from.", task.task_id)
            if task.result_contract is None:
                return self._fail("invalid_semantic_alias", "CACHE_ALIAS task requires result_contract.", task.task_id)
            return self._ok_context()
        count_shape = self._validate_count_task_shape(task)
        if not count_shape.passed:
            return count_shape
        if task.kind == "CONCEPT":
            return self._ok_context()
        if task.kind == "AGGREGATE":
            if not task.depends_on:
                return self._fail("aggregate_missing_dependencies", "AGGREGATE task must depend on prior tasks.", task.task_id)
            return self._ok_context()
        if task.kind == "LOCAL_QUERY":
            if task.local_query is None:
                return self._fail("missing_local_query", "LOCAL_QUERY task requires local_query.", task.task_id)
            return self._validate_local(task.task_id, task.local_query)
        if task.kind == "LIVE_QUERY":
            if task.api_query is None:
                return self._fail("missing_api_query", "LIVE_QUERY task requires api_query.", task.task_id)
            return self._validate_api(task.task_id, task.api_query)
        if task.kind == "LOCAL_AND_LIVE":
            if task.local_query is None:
                return self._fail("missing_local_query", "LOCAL_AND_LIVE task requires local_query.", task.task_id)
            if task.api_query is None:
                return self._fail("missing_api_query", "LOCAL_AND_LIVE task requires api_query.", task.task_id)
            local_result = self._validate_local(task.task_id, task.local_query)
            if not local_result.passed:
                return local_result
            return self._validate_api(task.task_id, task.api_query)
        return self._fail("invalid_kind", f"Invalid task kind: {task.kind}", task.task_id)

    def _validate_count_task_shape(self, task: SemanticIRTask) -> SemanticIRValidationResult:
        if task.operation != "COUNT":
            return self._ok_context()
        if task.source == "LOCAL_SNAPSHOT":
            if task.kind not in {"LOCAL_QUERY", "LOCAL_AND_LIVE"} or task.local_query is None or not task.local_query.count:
                return self._fail(
                    "local_count_requires_count_query",
                    "COUNT tasks over LOCAL_SNAPSHOT must include a LOCAL_QUERY local_query with count=true.",
                    task.task_id,
                )
        if task.source == "BOTH":
            if task.kind != "LOCAL_AND_LIVE" or task.local_query is None or not task.local_query.count or task.api_query is None:
                return self._fail(
                    "both_count_requires_local_and_live_queries",
                    "COUNT tasks over BOTH must include LOCAL_AND_LIVE with local_query.count=true and an api_query.",
                    task.task_id,
                )
        if task.source == "LIVE_API":
            if task.kind not in {"LIVE_QUERY", "LOCAL_AND_LIVE"} or task.api_query is None:
                return self._fail("live_count_requires_api_query", "COUNT tasks over LIVE_API must include an api_query.", task.task_id)
        return self._ok_context()

    def _validate_local(self, task_id: str, query: LocalQueryIR) -> SemanticIRValidationResult:
        table = self._table_key.get(query.table.lower())
        if not table:
            return self._fail("unknown_table", f"Unknown table: {query.table}", task_id)
        allowed_fields = self._tables.get(table, [])
        field_lookup = {field.lower(): field for field in allowed_fields}
        for field in query.fields:
            if field.lower() not in field_lookup:
                return self._fail("unknown_field", f"Unknown field {field} for table {query.table}.", task_id, allowed_fields)
        for item in query.filters:
            if item.field.lower() not in field_lookup:
                return self._fail("unknown_filter_field", f"Unknown filter field {item.field} for table {query.table}.", task_id, allowed_fields)
            if item.op not in ALLOWED_SEMANTIC_IR_FILTER_OPS:
                return self._fail("invalid_filter_op", f"Invalid filter op: {item.op}", task_id, allowed_fields)
        return self._ok_context(allowed_fields)

    def _validate_api(self, task_id: str, query: APIQueryIR) -> SemanticIRValidationResult:
        endpoint = self._endpoint_key.get(query.endpoint_id.lower())
        if not endpoint:
            return self._fail("unknown_endpoint", f"Unknown endpoint_id: {query.endpoint_id}", task_id)
        if query.method.upper() != "GET":
            return self._fail("non_get_api_method", f"Only GET is allowed, got {query.method}.", task_id)
        if not isinstance(query.path_params, dict) or not isinstance(query.query_params, dict):
            return self._fail("invalid_api_params", "API path_params and query_params must be objects.", task_id)
        return self._ok_context()

    def _has_cycle(self, tasks: list[SemanticIRTask]) -> bool:
        graph = {task.task_id: list(task.depends_on) for task in tasks}
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> bool:
            if node in visiting:
                return True
            if node in visited:
                return False
            visiting.add(node)
            for dep in graph.get(node, []):
                if visit(dep):
                    return True
            visiting.remove(node)
            visited.add(node)
            return False

        return any(visit(node) for node in graph)

    def _ok_context(self, allowed_fields: list[str] | None = None) -> SemanticIRValidationResult:
        return SemanticIRValidationResult(
            passed=True,
            allowed_tables=list(self._tables.keys()),
            allowed_fields_for_table=list(allowed_fields or []),
            allowed_endpoints=list(self._endpoints.keys()),
        )

    def _fail(
        self,
        error_type: str,
        error_message: str,
        task_id: str | None = None,
        allowed_fields: list[str] | None = None,
        semantic_alias_validation_used: bool = False,
        semantic_alias_validation_passed: bool | None = None,
        semantic_alias_count: int = 0,
        reuse_result_from: str | None = None,
        alias_contract: dict[str, Any] | None = None,
        producer_contract: dict[str, Any] | None = None,
    ) -> SemanticIRValidationResult:
        return SemanticIRValidationResult(
            passed=False,
            error_type=error_type,
            error_message=error_message,
            task_id=task_id,
            allowed_tables=list(self._tables.keys()),
            allowed_fields_for_table=list(allowed_fields or []),
            allowed_endpoints=list(self._endpoints.keys()),
            semantic_alias_validation_used=semantic_alias_validation_used,
            semantic_alias_validation_passed=semantic_alias_validation_passed,
            semantic_alias_count=semantic_alias_count,
            reuse_result_from=reuse_result_from,
            alias_contract=alias_contract,
            producer_contract=producer_contract,
        )
