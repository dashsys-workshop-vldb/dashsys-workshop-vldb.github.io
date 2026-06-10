from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


ANSWER_SLOT_TYPES = {"CONCEPT", "COUNT", "LIST", "LOOKUP", "STATUS", "DATE", "RELATION", "COMPARISON", "BOOLEAN", "SUMMARY"}
ANSWER_STYLES = {"CONCISE", "EXPLANATORY", "LIST", "TABLE", "COMPARISON", "COUNT_ONLY", "CAVEATED"}
ANSWER_SCOPES = {"LOCAL_SNAPSHOT", "LIVE_API", "BOTH", "NONE"}
ZERO_ROWS_SEMANTICS = {"NO_MATCH", "UNKNOWN", "EMPTY_RESULT_IS_ANSWER", "NOT_APPLICABLE"}
IF_MISSING_POLICIES = {"SCOPED_UNAVAILABLE_CAVEAT", "FAIL_REQUIRED", "ALLOW_PARTIAL"}
EVIDENCE_SLOT_STATUSES = {"SATISFIED", "PARTIAL", "ZERO_ROWS", "API_UNAVAILABLE", "NO_EVIDENCE", "ERROR", "DEPENDENCY_FAILED"}


@dataclass
class RequiredAnswerSlot:
    slot_id: str
    type: str
    required: bool = True
    subject: str | None = None
    object: str | None = None
    relation: str | None = None
    source_scope: str = "LOCAL_SNAPSHOT"
    satisfied_by_tasks: list[str] = field(default_factory=list)
    required_fields: list[str] = field(default_factory=list)
    acceptable_fallback_fields: list[str] = field(default_factory=list)
    expected_status_filter: str | None = None
    zero_rows_semantics: str = "NOT_APPLICABLE"
    if_missing: str = "SCOPED_UNAVAILABLE_CAVEAT"
    must_not_assert_positive_if_zero_rows: bool = False
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class V2AnswerContract:
    required_slots: list[RequiredAnswerSlot] = field(default_factory=list)
    optional_slots: list[RequiredAnswerSlot] = field(default_factory=list)
    answer_style: str = "CONCISE"
    global_scope: str = "NONE"
    contract_version: str = "v1"

    def to_dict(self) -> dict[str, Any]:
        return answer_contract_to_dict(self)


@dataclass
class EvidenceSlotState:
    slot_id: str
    status: str
    source_scope: str = "NONE"
    supporting_task_ids: list[str] = field(default_factory=list)
    facts: list[dict[str, Any]] = field(default_factory=list)
    count_values: list[Any] = field(default_factory=list)
    date_values: list[str] = field(default_factory=list)
    status_values: list[str] = field(default_factory=list)
    relation_rows: list[dict[str, Any]] = field(default_factory=list)
    list_rows: list[dict[str, Any]] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)
    positive_assertion_allowed: bool = True

    def to_dict(self) -> dict[str, Any]:
        return evidence_slot_state_to_dict(self)


def answer_contract_to_dict(contract: V2AnswerContract | None) -> dict[str, Any] | None:
    if contract is None:
        return None
    return {
        "required_slots": [slot.to_dict() for slot in contract.required_slots],
        "optional_slots": [slot.to_dict() for slot in contract.optional_slots],
        "answer_style": contract.answer_style,
        "global_scope": contract.global_scope,
        "contract_version": contract.contract_version,
    }


def evidence_slot_state_to_dict(state: EvidenceSlotState) -> dict[str, Any]:
    return asdict(state)


def parse_answer_contract(raw: Any) -> V2AnswerContract:
    if not isinstance(raw, dict):
        raise ValueError("answer_contract must be an object or null.")
    required_slots = [_parse_slot(item, required_default=True, label="required_slots") for item in _list(raw.get("required_slots"))]
    optional_slots = [_parse_slot(item, required_default=False, label="optional_slots") for item in _list(raw.get("optional_slots"))]
    answer_style = _enum(raw.get("answer_style") or _default_answer_style(required_slots), ANSWER_STYLES, "answer_style")
    global_scope = _enum(raw.get("global_scope") or "NONE", ANSWER_SCOPES, "global_scope")
    version = str(raw.get("contract_version") or "v1").strip() or "v1"
    return V2AnswerContract(
        required_slots=required_slots,
        optional_slots=optional_slots,
        answer_style=answer_style,
        global_scope=global_scope,
        contract_version=version,
    )


def normalize_answer_contract_enums(contract: V2AnswerContract) -> V2AnswerContract:
    return parse_answer_contract(answer_contract_to_dict(contract))


def answer_contract_from_plan_dict(plan: dict[str, Any]) -> V2AnswerContract | None:
    raw = plan.get("answer_contract") if isinstance(plan, dict) else None
    if raw is None:
        return None
    return parse_answer_contract(raw)


def validate_answer_contract_shape(
    contract: V2AnswerContract | None,
    *,
    task_ids: list[str],
    route: str,
) -> dict[str, Any]:
    normalized_route = str(route or "").strip().upper()
    if contract is None:
        if normalized_route == "DIRECT":
            return {"passed": True, "error_type": None, "error_message": None}
        return {"passed": False, "error_type": "missing_answer_contract", "error_message": "EVIDENCE route requires answer_contract.required_slots."}
    seen: set[str] = set()
    known_tasks = set(task_ids)
    for slot in list(contract.required_slots) + list(contract.optional_slots):
        if not slot.slot_id:
            return {"passed": False, "error_type": "missing_slot_id", "error_message": "Answer contract slot is missing slot_id."}
        if slot.slot_id in seen:
            return {"passed": False, "error_type": "duplicate_slot_id", "error_message": f"Duplicate answer slot id: {slot.slot_id}."}
        seen.add(slot.slot_id)
        if slot.type not in ANSWER_SLOT_TYPES:
            return {"passed": False, "error_type": "invalid_slot_type", "error_message": f"Invalid slot type: {slot.type}."}
        if slot.source_scope not in ANSWER_SCOPES:
            return {"passed": False, "error_type": "invalid_source_scope", "error_message": f"Invalid source scope: {slot.source_scope}."}
        if slot.zero_rows_semantics not in ZERO_ROWS_SEMANTICS:
            return {"passed": False, "error_type": "invalid_zero_rows_semantics", "error_message": f"Invalid zero rows semantics: {slot.zero_rows_semantics}."}
        if slot.if_missing not in IF_MISSING_POLICIES:
            return {"passed": False, "error_type": "invalid_if_missing", "error_message": f"Invalid if_missing policy: {slot.if_missing}."}
        if normalized_route == "DIRECT" and slot.type == "CONCEPT" and not slot.satisfied_by_tasks:
            continue
        if slot.required and not slot.satisfied_by_tasks:
            return {"passed": False, "error_type": "missing_slot_task_reference", "error_message": f"Required slot {slot.slot_id} must reference at least one task."}
        for task_id in slot.satisfied_by_tasks:
            if task_id not in known_tasks:
                return {
                    "passed": False,
                    "error_type": "unknown_slot_task_reference",
                    "error_message": f"Slot {slot.slot_id} references unknown task {task_id}.",
                    "slot_id": slot.slot_id,
                    "task_id": task_id,
                }
    return {"passed": True, "error_type": None, "error_message": None}


def _parse_slot(raw: Any, *, required_default: bool, label: str) -> RequiredAnswerSlot:
    if not isinstance(raw, dict):
        raise ValueError(f"{label} entries must be objects.")
    slot_id = str(raw.get("slot_id") or "").strip()
    if not slot_id:
        raise ValueError("slot_id is required.")
    slot_type = _enum(raw.get("type"), ANSWER_SLOT_TYPES, "type")
    if not (raw.get("source_scope") or raw.get("scope")):
        raise ValueError("source_scope is required.")
    source_scope = _enum(raw.get("source_scope") or raw.get("scope"), ANSWER_SCOPES, "source_scope")
    zero_rows = _enum(raw.get("zero_rows_semantics") or "NOT_APPLICABLE", ZERO_ROWS_SEMANTICS, "zero_rows_semantics")
    if_missing = _enum(raw.get("if_missing") or "SCOPED_UNAVAILABLE_CAVEAT", IF_MISSING_POLICIES, "if_missing")
    must_not_assert = raw.get("must_not_assert_positive_if_zero_rows")
    if must_not_assert is None:
        must_not_assert = slot_type in {"RELATION", "LIST", "LOOKUP", "STATUS"}
    return RequiredAnswerSlot(
        slot_id=slot_id,
        type=slot_type,
        required=bool(raw.get("required", required_default)),
        subject=_text_or_none(raw.get("subject")),
        object=_text_or_none(raw.get("object")),
        relation=_text_or_none(raw.get("relation")),
        source_scope=source_scope,
        satisfied_by_tasks=[str(item).strip() for item in _list(raw.get("satisfied_by_tasks")) if str(item).strip()],
        required_fields=[str(item).strip() for item in _list(raw.get("required_fields")) if str(item).strip()],
        acceptable_fallback_fields=[str(item).strip() for item in _list(raw.get("acceptable_fallback_fields")) if str(item).strip()],
        expected_status_filter=_text_or_none(raw.get("expected_status_filter")),
        zero_rows_semantics=zero_rows,
        if_missing=if_missing,
        must_not_assert_positive_if_zero_rows=bool(must_not_assert),
        notes=_text_or_none(raw.get("notes")),
    )


def _default_answer_style(required_slots: list[RequiredAnswerSlot]) -> str:
    slot_types = {slot.type for slot in required_slots}
    if slot_types == {"COUNT"}:
        return "COUNT_ONLY"
    if slot_types and slot_types <= {"LIST", "LOOKUP", "STATUS"}:
        return "LIST"
    if "COMPARISON" in slot_types:
        return "COMPARISON"
    if slot_types & {"RELATION", "DATE", "CAVEAT"}:
        return "CAVEATED"
    return "CONCISE"


def _enum(value: Any, allowed: set[str], field_name: str) -> str:
    text = str(value or "").strip().upper()
    if field_name == "zero_rows_semantics":
        text = _normalize_zero_rows_semantics(text)
    elif field_name == "if_missing":
        text = _normalize_if_missing_policy(text)
    if text not in allowed:
        raise ValueError(f"{field_name} must be one of {sorted(allowed)}.")
    return text


def _normalize_zero_rows_semantics(text: str) -> str:
    normalized = text.replace("-", "_").replace(" ", "_")
    aliases = {
        "NO_DATA": "NO_MATCH",
        "NO_RESULTS": "NO_MATCH",
        "NO_RESULT": "NO_MATCH",
        "EMPTY": "NO_MATCH",
        "EMPTY_RESULT": "NO_MATCH",
        "NO_MATCHES": "NO_MATCH",
        "ZERO_ROWS": "NO_MATCH",
        "ZERO_ROWS_IS_ANSWER": "EMPTY_RESULT_IS_ANSWER",
        "ZERO_IS_ANSWER": "EMPTY_RESULT_IS_ANSWER",
        "EMPTY_IS_ANSWER": "EMPTY_RESULT_IS_ANSWER",
        "COUNT_ZERO_IS_ANSWER": "EMPTY_RESULT_IS_ANSWER",
        "N_A": "NOT_APPLICABLE",
        "NA": "NOT_APPLICABLE",
        "NONE": "NOT_APPLICABLE",
    }
    if normalized in aliases:
        return aliases[normalized]
    if normalized in ZERO_ROWS_SEMANTICS:
        return normalized
    return "UNKNOWN"


def _normalize_if_missing_policy(text: str) -> str:
    normalized = text.replace("-", "_").replace(" ", "_")
    aliases = {
        "CAVEAT": "SCOPED_UNAVAILABLE_CAVEAT",
        "SCOPED_CAVEAT": "SCOPED_UNAVAILABLE_CAVEAT",
        "UNAVAILABLE_CAVEAT": "SCOPED_UNAVAILABLE_CAVEAT",
        "SCOPED_UNAVAILABLE": "SCOPED_UNAVAILABLE_CAVEAT",
        "ERROR_CAVEAT": "SCOPED_UNAVAILABLE_CAVEAT",
        "FAIL": "FAIL_REQUIRED",
        "REQUIRED": "FAIL_REQUIRED",
        "FAIL_IF_MISSING": "FAIL_REQUIRED",
        "PARTIAL": "ALLOW_PARTIAL",
        "ALLOW_PARTIAL_CAVEAT": "ALLOW_PARTIAL",
    }
    if normalized in aliases:
        return aliases[normalized]
    if normalized in IF_MISSING_POLICIES:
        return normalized
    return "SCOPED_UNAVAILABLE_CAVEAT"


def _list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _text_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
