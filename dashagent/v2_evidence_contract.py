from __future__ import annotations

import re
from typing import Any

from .v2_answer_contract import EvidenceSlotState, RequiredAnswerSlot, V2AnswerContract


def evaluate_evidence_contract(
    answer_contract: V2AnswerContract | None,
    runtime_passes: list[dict[str, Any]],
) -> list[EvidenceSlotState]:
    if answer_contract is None:
        return []
    pass_lookup = {str(item.get("pass_id") or ""): item for item in runtime_passes if isinstance(item, dict)}
    states: list[EvidenceSlotState] = []
    for slot in answer_contract.required_slots + answer_contract.optional_slots:
        states.append(_evaluate_slot(slot, pass_lookup))
    return states


def evidence_contract_summary(states: list[EvidenceSlotState]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for state in states:
        counts[state.status] = counts.get(state.status, 0) + 1
    return {
        "evidence_contract_used": bool(states),
        "evidence_slot_states": [state.to_dict() for state in states],
        "evidence_contract_satisfied_count": counts.get("SATISFIED", 0),
        "evidence_contract_partial_count": counts.get("PARTIAL", 0),
        "evidence_contract_zero_row_count": counts.get("ZERO_ROWS", 0),
        "evidence_contract_api_unavailable_count": counts.get("API_UNAVAILABLE", 0),
        "evidence_contract_no_evidence_count": counts.get("NO_EVIDENCE", 0),
        "evidence_contract_error_count": counts.get("ERROR", 0) + counts.get("DEPENDENCY_FAILED", 0),
    }


def _evaluate_slot(slot: RequiredAnswerSlot, pass_lookup: dict[str, dict[str, Any]]) -> EvidenceSlotState:
    supporting = [pass_lookup[task_id] for task_id in slot.satisfied_by_tasks if task_id in pass_lookup]
    if not supporting:
        return EvidenceSlotState(
            slot_id=slot.slot_id,
            status="NO_EVIDENCE",
            source_scope=slot.source_scope,
            supporting_task_ids=[],
            caveats=[_missing_caveat(slot)],
            missing_fields=list(slot.required_fields),
            positive_assertion_allowed=False,
        )

    if slot.type == "CONCEPT" and _has_direct_concept_pass(supporting):
        answers = _direct_answers_from_passes(supporting)
        return EvidenceSlotState(
            slot_id=slot.slot_id,
            status="SATISFIED",
            source_scope=slot.source_scope,
            supporting_task_ids=[str(item.get("pass_id") or "") for item in supporting],
            facts=[{"answer": answer} for answer in answers[:3]],
            positive_assertion_allowed=True,
        )

    statuses = {_status(item) for item in supporting}
    if statuses & {"DEPENDENCY_FAILED", "DEPENDENCY_BLOCKED", "BUDGET_EXCEEDED"}:
        return _state(slot, "DEPENDENCY_FAILED", supporting, caveats=["Required dependency failed."], positive=False)
    if statuses & {"API_ERROR"} or any(_has_api_error(item) for item in supporting):
        rows = _rows_from_passes(supporting)
        if rows:
            return _state_from_rows(slot, supporting, rows, extra_caveats=["Live API evidence was unavailable for part of this slot."])
        return _state(slot, "API_UNAVAILABLE", supporting, caveats=["Live API evidence was unavailable for this slot."], positive=False)
    if statuses & {"ERROR", "COMPILE_ERROR", "REQUEST_ERROR"}:
        rows = _rows_from_passes(supporting)
        if rows:
            return _state_from_rows(slot, supporting, rows, extra_caveats=["Some requested runtime evidence errored for this slot."])
        return _state(slot, "ERROR", supporting, caveats=["Runtime evidence errored for this slot."], positive=False)

    rows = _rows_from_passes(supporting)
    zero_rows = _has_zero_rows(supporting)
    if not rows and zero_rows:
        status = "SATISFIED" if slot.type == "COUNT" and slot.zero_rows_semantics == "EMPTY_RESULT_IS_ANSWER" else "ZERO_ROWS"
        count_values = [0] if slot.type == "COUNT" else []
        return EvidenceSlotState(
            slot_id=slot.slot_id,
            status=status,
            source_scope=slot.source_scope,
            supporting_task_ids=[str(item.get("pass_id") or "") for item in supporting],
            count_values=count_values,
            caveats=[_zero_row_caveat(slot)] if status == "ZERO_ROWS" else [],
            missing_fields=[] if status == "SATISFIED" else list(slot.required_fields),
            positive_assertion_allowed=status == "SATISFIED" and not slot.must_not_assert_positive_if_zero_rows,
        )
    if rows:
        return _state_from_rows(slot, supporting, rows)
    return _state(slot, "NO_EVIDENCE", supporting, caveats=[_missing_caveat(slot)], missing=list(slot.required_fields), positive=False)


def _state_from_rows(
    slot: RequiredAnswerSlot,
    supporting: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    *,
    extra_caveats: list[str] | None = None,
) -> EvidenceSlotState:
    required = list(slot.required_fields)
    fallback = list(slot.acceptable_fallback_fields)
    count_values = _count_values(rows)
    date_values = _date_values(rows, required + fallback)
    status_values = _status_values(rows)
    missing = _missing_required_fields(rows, required)
    list_rows = rows[:25] if slot.type in {"LIST", "LOOKUP", "STATUS", "DATE", "SUMMARY", "BOOLEAN"} else []
    relation_rows = rows[:25] if slot.type in {"RELATION", "COMPARISON"} or _rows_look_like_relationship(rows) else []
    facts = [_compact_row(row) for row in rows[:25]]
    status = "SATISFIED"
    positive = True
    if slot.type == "COUNT":
        if not count_values:
            status = "NO_EVIDENCE"
            missing = required or ["count"]
            positive = False
    elif slot.type == "DATE":
        if date_values and _has_any_date_field(rows, required):
            status = "SATISFIED"
        elif date_values and fallback and _has_any_date_field(rows, fallback):
            status = "PARTIAL"
        else:
            status = "PARTIAL"
            missing = required
            positive = False
    elif slot.type == "STATUS":
        if not status_values:
            status = "PARTIAL"
            missing = required or ["status"]
            positive = False
        elif slot.expected_status_filter and not any(_norm(slot.expected_status_filter) == _norm(value) for value in status_values):
            status = "ZERO_ROWS"
            positive = False
    elif slot.type == "RELATION":
        if not relation_rows:
            status = "ZERO_ROWS"
            positive = False
    elif slot.type in {"LIST", "LOOKUP"}:
        if not rows:
            status = "ZERO_ROWS"
            positive = False
    return EvidenceSlotState(
        slot_id=slot.slot_id,
        status=status,
        source_scope=slot.source_scope,
        supporting_task_ids=[str(item.get("pass_id") or "") for item in supporting],
        facts=facts,
        count_values=count_values,
        date_values=date_values,
        status_values=status_values,
        relation_rows=relation_rows,
        list_rows=list_rows,
        caveats=list(extra_caveats or []),
        missing_fields=missing,
        positive_assertion_allowed=positive,
    )


def _state(
    slot: RequiredAnswerSlot,
    status: str,
    supporting: list[dict[str, Any]],
    *,
    caveats: list[str] | None = None,
    missing: list[str] | None = None,
    positive: bool = True,
) -> EvidenceSlotState:
    return EvidenceSlotState(
        slot_id=slot.slot_id,
        status=status,
        source_scope=slot.source_scope,
        supporting_task_ids=[str(item.get("pass_id") or "") for item in supporting],
        caveats=list(caveats or []),
        missing_fields=list(missing or []),
        positive_assertion_allowed=positive,
    )


def _rows_from_passes(passes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in passes:
        for source in item.get("source_results", []) if isinstance(item.get("source_results"), list) else []:
            if not isinstance(source, dict):
                continue
            result = source.get("result") if isinstance(source.get("result"), dict) else {}
            rows.extend(_rows_from_result(result))
        result = item.get("result") if isinstance(item.get("result"), dict) else {}
        rows.extend(_rows_from_result(result))
    return [_compact_row(row) for row in rows if isinstance(row, dict)]


def _rows_from_result(result: dict[str, Any]) -> list[dict[str, Any]]:
    rows = result.get("rows")
    if isinstance(rows, dict) and isinstance(rows.get("items"), list):
        rows = rows.get("items")
    if isinstance(rows, list):
        return [row for row in rows if isinstance(row, dict)]
    parsed = result.get("parsed_evidence") if isinstance(result.get("parsed_evidence"), dict) else {}
    items = parsed.get("items")
    if isinstance(items, list):
        return [row for row in items if isinstance(row, dict)]
    return []


def _direct_answers_from_passes(passes: list[dict[str, Any]]) -> list[str]:
    answers: list[str] = []
    for item in passes:
        for source in item.get("source_results", []) if isinstance(item.get("source_results"), list) else []:
            if not isinstance(source, dict):
                continue
            if str(source.get("source") or item.get("path") or "").upper() != "DIRECT":
                continue
            if str(source.get("status") or "").upper() != "SUCCESS":
                continue
            result = source.get("result") if isinstance(source.get("result"), dict) else {}
            answer = str(result.get("answer") or "").strip()
            if answer:
                answers.append(answer)
        result = item.get("result") if isinstance(item.get("result"), dict) else {}
        if str(item.get("path") or item.get("source") or "").upper() == "DIRECT" and str(item.get("status") or "").upper() == "SUCCESS":
            answer = str(result.get("answer") or "").strip()
            if answer:
                answers.append(answer)
    return _dedupe(answers)


def _has_direct_concept_pass(passes: list[dict[str, Any]]) -> bool:
    for item in passes:
        if str(item.get("path") or item.get("source") or "").upper() in {"DIRECT", "CONCEPT", "NO_EVIDENCE_CONCEPT", "NONE"}:
            return True
        for source in item.get("source_results", []) if isinstance(item.get("source_results"), list) else []:
            if isinstance(source, dict) and str(source.get("source") or source.get("scope") or "").upper() in {
                "DIRECT",
                "CONCEPT",
                "NO_EVIDENCE_CONCEPT",
                "NONE",
            }:
                return True
    return False


def _has_zero_rows(passes: list[dict[str, Any]]) -> bool:
    for item in passes:
        if _status(item) in {"EMPTY", "LIVE_EMPTY"}:
            return True
        for source in item.get("source_results", []) if isinstance(item.get("source_results"), list) else []:
            result = source.get("result") if isinstance(source.get("result"), dict) else {}
            if str(source.get("status") or "").upper() in {"EMPTY", "LIVE_EMPTY"}:
                return True
            if result.get("row_count") == 0:
                return True
    return False


def _has_api_error(item: dict[str, Any]) -> bool:
    for source in item.get("source_results", []) if isinstance(item.get("source_results"), list) else []:
        if str(source.get("source") or "").upper() in {"API", "LIVE_API"} and str(source.get("status") or "").upper() in {"ERROR", "API_ERROR", "REQUEST_ERROR"}:
            return True
    return False


def _status(item: dict[str, Any]) -> str:
    return str(item.get("status") or "").upper()


def _count_values(rows: list[dict[str, Any]]) -> list[Any]:
    values: list[Any] = []
    for row in rows:
        for key, value in row.items():
            norm = _norm_key(key)
            if norm in {"count", "total", "totalcount"} or norm.endswith("count"):
                values.append(value)
    return _dedupe(values)


def _date_values(rows: list[dict[str, Any]], field_names: list[str]) -> list[str]:
    wanted = {_norm_key(name) for name in field_names if name}
    values: list[str] = []
    for row in rows:
        for key, value in row.items():
            norm = _norm_key(key)
            if value in (None, ""):
                continue
            if _is_date_like_field(norm) or (norm in wanted and _looks_like_date_value(value)):
                values.append(str(value))
    return _dedupe(values)


def _status_values(rows: list[dict[str, Any]]) -> list[str]:
    values: list[str] = []
    for row in rows:
        for key, value in row.items():
            if _norm_key(key) in {"status", "state", "lifecyclestatus"} and value not in (None, ""):
                values.append(str(value))
    return _dedupe(values)


def _missing_required_fields(rows: list[dict[str, Any]], required_fields: list[str]) -> list[str]:
    missing: list[str] = []
    for field in required_fields:
        if not _has_any_field(rows, [field]):
            missing.append(field)
    return missing


def _has_any_field(rows: list[dict[str, Any]], fields: list[str]) -> bool:
    wanted = {_norm_key(field) for field in fields if field}
    if not wanted:
        return False
    for row in rows:
        for key, value in row.items():
            if _norm_key(key) in wanted and value not in (None, ""):
                return True
    return False


def _has_any_date_field(rows: list[dict[str, Any]], fields: list[str]) -> bool:
    wanted = {_norm_key(field) for field in fields if field}
    if not wanted:
        return False
    for row in rows:
        for key, value in row.items():
            norm = _norm_key(key)
            if norm not in wanted or value in (None, ""):
                continue
            if _is_date_like_field(norm) or _looks_like_date_value(value):
                return True
    return False


def _is_date_like_field(norm_key: str) -> bool:
    return any(token in norm_key for token in ["date", "time", "created", "updated", "modified", "deployed", "published", "start", "end"])


def _looks_like_date_value(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    return bool(
        re.search(r"\b20\d{2}-\d{2}-\d{2}(?:[T ][0-9:.+-]+Z?)?\b", text)
        or re.search(r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2},?\s+20\d{2}\b", text, flags=re.I)
    )


def _rows_look_like_relationship(rows: list[dict[str, Any]]) -> bool:
    for row in rows:
        id_like = [key for key in row if _norm_key(key).endswith("id")]
        if len(id_like) >= 2:
            return True
    return False


def _compact_row(row: dict[str, Any]) -> dict[str, Any]:
    return {str(key): value for key, value in list(row.items())[:24]}


def _zero_row_caveat(slot: RequiredAnswerSlot) -> str:
    return f"No matching {slot.source_scope.lower()} evidence was available for slot {slot.slot_id}."


def _missing_caveat(slot: RequiredAnswerSlot) -> str:
    return f"No runtime evidence was available for required slot {slot.slot_id}."


def _norm_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _dedupe(values: list[Any]) -> list[Any]:
    out: list[Any] = []
    seen: set[str] = set()
    for value in values:
        key = repr(value)
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out
