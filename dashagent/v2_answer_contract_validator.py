from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .v2_answer_contract import V2AnswerContract, validate_answer_contract_shape
from .v2_semantic_ir import SemanticIRPlan, SemanticIRTask


@dataclass
class AnswerContractValidationResult:
    passed: bool
    error_type: str | None = None
    error_message: str | None = None
    slot_id: str | None = None
    task_id: str | None = None
    required_slot_count: int = 0
    warning_messages: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AnswerContractValidator:
    """Shape-only answer-contract validator.

    This checks contract/task references and scope compatibility. It does not infer
    slots from prompt text and does not choose replacement tasks.
    """

    def validate(self, plan: SemanticIRPlan) -> AnswerContractValidationResult:
        contract = plan.answer_contract
        task_ids = [task.task_id for task in plan.tasks]
        shape = validate_answer_contract_shape(contract, task_ids=task_ids, route=plan.route)
        if not shape.get("passed"):
            return AnswerContractValidationResult(
                passed=False,
                error_type=str(shape.get("error_type") or "invalid_answer_contract"),
                error_message=str(shape.get("error_message") or "Invalid answer contract."),
                slot_id=shape.get("slot_id"),
                task_id=shape.get("task_id"),
                required_slot_count=len(contract.required_slots) if contract is not None else 0,
            )
        if contract is None:
            return AnswerContractValidationResult(True, required_slot_count=0)
        task_lookup = {task.task_id: task for task in plan.tasks}
        for slot in contract.required_slots:
            result = self._validate_slot(slot, contract, task_lookup)
            if not result.passed:
                return result
        return AnswerContractValidationResult(True, required_slot_count=len(contract.required_slots))

    def _validate_slot(self, slot: Any, contract: V2AnswerContract, task_lookup: dict[str, SemanticIRTask]) -> AnswerContractValidationResult:
        tasks = [task_lookup[task_id] for task_id in slot.satisfied_by_tasks if task_id in task_lookup]
        if slot.type == "DATE" and not (slot.required_fields or slot.acceptable_fallback_fields):
            return self._fail("missing_date_fields", "DATE slot requires required_fields or acceptable_fallback_fields.", slot.slot_id)
        if slot.type == "RELATION":
            if not (slot.relation or (slot.subject and slot.object)):
                return self._fail("missing_relation_descriptor", "RELATION slot requires relation or subject/object.", slot.slot_id)
            if not slot.zero_rows_semantics or slot.zero_rows_semantics == "NOT_APPLICABLE":
                return self._fail("missing_zero_rows_semantics", "RELATION slot requires zero_rows_semantics.", slot.slot_id)
        if slot.type in {"LIST", "LOOKUP"} and (not slot.zero_rows_semantics or slot.zero_rows_semantics == "NOT_APPLICABLE"):
            return self._fail("missing_zero_rows_semantics", f"{slot.type} slot requires zero_rows_semantics.", slot.slot_id)
        if slot.required and not slot.if_missing:
            return self._fail("missing_if_missing_policy", "Required slots require if_missing policy.", slot.slot_id)
        if slot.source_scope == "LOCAL_SNAPSHOT" and not any(task.source in {"LOCAL_SNAPSHOT", "BOTH"} for task in tasks):
            return self._fail("slot_scope_task_mismatch", "LOCAL_SNAPSHOT slot must be backed by a LOCAL_SNAPSHOT/BOTH task.", slot.slot_id, tasks[0].task_id if tasks else None)
        if slot.source_scope == "LIVE_API" and not any(task.source in {"LIVE_API", "BOTH"} for task in tasks):
            return self._fail("slot_scope_task_mismatch", "LIVE_API slot must be backed by a LIVE_API/BOTH task.", slot.slot_id, tasks[0].task_id if tasks else None)
        if slot.source_scope == "BOTH":
            sources = {task.source for task in tasks}
            if not (("BOTH" in sources) or ({"LOCAL_SNAPSHOT", "LIVE_API"} <= sources)):
                return self._fail("slot_scope_task_mismatch", "BOTH slot must be backed by BOTH or local+live tasks.", slot.slot_id, tasks[0].task_id if tasks else None)
        if slot.type == "COUNT" and tasks and not any(task.operation == "COUNT" for task in tasks):
            return self._fail("count_slot_task_operation_mismatch", "COUNT slot should be backed by a COUNT task.", slot.slot_id, tasks[0].task_id)
        if slot.type == "LIST" and tasks and not any(task.operation in {"LIST", "LOOKUP"} for task in tasks):
            return self._fail("list_slot_task_operation_mismatch", "LIST slot should be backed by LIST/LOOKUP task.", slot.slot_id, tasks[0].task_id)
        if slot.type == "STATUS" and tasks and not any(task.operation in {"STATUS", "LOOKUP", "LIST"} for task in tasks):
            return self._fail("status_slot_task_operation_mismatch", "STATUS slot should be backed by STATUS/LOOKUP/LIST task.", slot.slot_id, tasks[0].task_id)
        if slot.type == "DATE" and tasks and not any(task.operation in {"DATE", "LOOKUP", "LIST"} for task in tasks):
            return self._fail("date_slot_task_operation_mismatch", "DATE slot should be backed by DATE/LOOKUP/LIST task.", slot.slot_id, tasks[0].task_id)
        return AnswerContractValidationResult(True, required_slot_count=len(contract.required_slots))

    def _fail(self, error_type: str, message: str, slot_id: str | None = None, task_id: str | None = None) -> AnswerContractValidationResult:
        return AnswerContractValidationResult(False, error_type, message, slot_id=slot_id, task_id=task_id)
