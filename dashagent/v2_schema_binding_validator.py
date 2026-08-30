from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .v2_answer_contract import V2AnswerContract
from .v2_schema_binding import SchemaBindingPlan
from .v2_semantic_ir import SemanticIRPlan


@dataclass
class SchemaBindingValidationResult:
    passed: bool
    error_type: str | None = None
    error_message: str | None = None
    binding_id: str | None = None
    task_id: str | None = None
    bad_value: str | None = None
    allowed_tables: list[str] = field(default_factory=list)
    allowed_fields_for_table: list[str] = field(default_factory=list)
    table_role_cards: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SchemaBindingValidator:
    def __init__(self, allowed_schema_card: list[dict[str, Any]], answer_contract: V2AnswerContract | None) -> None:
        self.allowed_schema_card = allowed_schema_card
        self.answer_contract = answer_contract
        self._tables = {str(row.get("table") or ""): [str(col) for col in row.get("columns") or []] for row in allowed_schema_card}
        self._table_key = {name.lower(): name for name in self._tables if name}

    def validate(self, plan: SchemaBindingPlan | None, *, semantic_plan: SemanticIRPlan | None = None) -> SchemaBindingValidationResult:
        if plan is None:
            return self._fail("missing_schema_binding", "Schema binding plan is missing.")
        seen: set[str] = set()
        slot_scopes = self._slot_scopes()
        for binding in plan.bindings:
            if not binding.binding_id:
                return self._fail("missing_binding_id", "Binding is missing binding_id.")
            if binding.binding_id in seen:
                return self._fail("duplicate_binding_id", f"Duplicate binding_id: {binding.binding_id}", binding.binding_id)
            seen.add(binding.binding_id)
            if binding.source_scope in {"LOCAL_SNAPSHOT", "BOTH"}:
                if not binding.table:
                    return self._fail("missing_table", "LOCAL_SNAPSHOT binding requires table.", binding.binding_id)
                table = self._table_key.get(binding.table.lower())
                if not table:
                    return self._fail("unknown_table", f"Unknown table: {binding.table}", binding.binding_id, bad_value=binding.table)
                allowed_fields = self._tables.get(table, [])
                field_lookup = {field.lower(): field for field in allowed_fields}
                for field in [
                    *binding.primary_id_fields,
                    *binding.name_fields,
                    *binding.status_fields,
                    *binding.date_fields,
                ]:
                    if field.lower() not in field_lookup:
                        return self._fail(
                            "unknown_field",
                            f"Unknown field {field} for table {binding.table}.",
                            binding.binding_id,
                            bad_value=field,
                            allowed_fields=allowed_fields,
                        )
            for relation_table in binding.relation_tables:
                if relation_table.lower() not in self._table_key:
                    return self._fail(
                        "invalid_relation_table",
                        f"Unknown relation table: {relation_table}",
                        binding.binding_id,
                        bad_value=relation_table,
                    )
            for slot_id in binding.required_for_slots:
                if slot_id not in slot_scopes:
                    return self._fail("invalid_slot_reference", f"Binding references unknown answer slot {slot_id}.", binding.binding_id, bad_value=slot_id)
                if not _scope_compatible(binding.source_scope, slot_scopes[slot_id]):
                    return self._fail(
                        "scope_mismatch",
                        f"Binding scope {binding.source_scope} is incompatible with slot {slot_id} scope {slot_scopes[slot_id]}.",
                        binding.binding_id,
                        bad_value=slot_id,
                    )
        if semantic_plan is not None:
            result = self._validate_semantic_plan_references(plan, semantic_plan)
            if not result.passed:
                return result
        return self._ok()

    def _validate_semantic_plan_references(self, binding_plan: SchemaBindingPlan, semantic_plan: SemanticIRPlan) -> SchemaBindingValidationResult:
        bindings = {binding.binding_id: binding for binding in binding_plan.bindings}
        for task in semantic_plan.tasks:
            task_binding_id = getattr(task, "binding_id", None)
            query = getattr(task, "local_query", None)
            query_binding_id = getattr(query, "binding_id", None) if query is not None else None
            binding_id = query_binding_id or task_binding_id
            if task_binding_id and query_binding_id and task_binding_id != query_binding_id:
                return self._fail("binding_reference_mismatch", "Task binding_id and local_query binding_id differ.", task_binding_id, task_id=task.task_id, bad_value=query_binding_id)
            if not binding_id:
                continue
            binding = bindings.get(binding_id)
            if binding is None:
                return self._fail("invalid_binding_reference", f"Task references unknown binding_id {binding_id}.", binding_id, task_id=task.task_id, bad_value=binding_id)
            if query is not None and query.table and binding.table and query.table.lower() != binding.table.lower():
                return self._fail(
                    "binding_table_conflict",
                    f"Task {task.task_id} local_query table {query.table} conflicts with binding {binding.binding_id} table {binding.table}.",
                    binding.binding_id,
                    task_id=task.task_id,
                    bad_value=query.table,
                    allowed_fields=self._tables.get(self._table_key.get(binding.table.lower(), ""), []),
                )
        return self._ok()

    def _slot_scopes(self) -> dict[str, str]:
        if self.answer_contract is None:
            return {}
        slots = [*self.answer_contract.required_slots, *self.answer_contract.optional_slots]
        return {slot.slot_id: slot.source_scope for slot in slots if getattr(slot, "slot_id", None)}

    def _ok(self) -> SchemaBindingValidationResult:
        return SchemaBindingValidationResult(
            passed=True,
            allowed_tables=list(self._tables.keys()),
            table_role_cards=self._table_role_cards(),
        )

    def _fail(
        self,
        error_type: str,
        error_message: str,
        binding_id: str | None = None,
        *,
        task_id: str | None = None,
        bad_value: str | None = None,
        allowed_fields: list[str] | None = None,
    ) -> SchemaBindingValidationResult:
        return SchemaBindingValidationResult(
            passed=False,
            error_type=error_type,
            error_message=error_message,
            binding_id=binding_id,
            task_id=task_id,
            bad_value=bad_value,
            allowed_tables=list(self._tables.keys()),
            allowed_fields_for_table=list(allowed_fields or []),
            table_role_cards=self._table_role_cards(),
        )

    def _table_role_cards(self) -> list[dict[str, Any]]:
        cards: list[dict[str, Any]] = []
        for row in self.allowed_schema_card:
            table = str(row.get("table") or "")
            if not table:
                continue
            cards.append(
                {
                    "table": table,
                    "table_role_hints": list(row.get("table_role_hints") or []),
                    "field_hints": row.get("field_hints") if isinstance(row.get("field_hints"), dict) else {},
                    "columns": list(row.get("columns") or [])[:24],
                }
            )
        return cards


def _scope_compatible(binding_scope: str, slot_scope: str) -> bool:
    if slot_scope == "NONE":
        return binding_scope == "NONE"
    if slot_scope == "LOCAL_SNAPSHOT":
        return binding_scope in {"LOCAL_SNAPSHOT", "BOTH"}
    if slot_scope == "LIVE_API":
        return binding_scope in {"LIVE_API", "BOTH"}
    if slot_scope == "BOTH":
        return binding_scope == "BOTH"
    return False
