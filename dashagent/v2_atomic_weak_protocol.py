from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any

from .trajectory import compact_preview, redact_secrets
from .v2_weak_model_protocol import (
    ProtocolParseError,
    WeakProtocolResult,
    _call_text,
    _candidate_from_legacy_plan,
    _compact_endpoint_lines,
    _compact_schema_lines,
    _elapsed_ms,
    _legacy_full_plan_payload,
    _merge_repaired_pass_payload,
    _run_direct_route_challenge,
    parse_pass_candidate_card,
    parse_route_card,
    parse_task_ledger_card,
)


CHECKLIST_MAX_TOKENS = 80
DIRECT_ANSWER_MAX_TOKENS = 120
TASK_SLOTS_MAX_TOKENS = 300
CANDIDATE_MAX_TOKENS = 220
CANDIDATE_REPAIR_MAX_TOKENS = 220

CHECKLIST_KEYS = [
    "RECORDS",
    "LIST",
    "COUNT",
    "STATUS",
    "DATE",
    "LOCAL_SNAPSHOT",
    "LIVE_CURRENT",
    "SHOW_ITEMS",
    "MIXED_CONCEPT_DATA",
    "PURE_CONCEPT",
]
EVIDENCE_KEYS = [
    "RECORDS",
    "LIST",
    "COUNT",
    "STATUS",
    "DATE",
    "LOCAL_SNAPSHOT",
    "LIVE_CURRENT",
    "SHOW_ITEMS",
    "MIXED_CONCEPT_DATA",
]
SLOT_PATHS = {"NONE", "DIRECT", "SQL", "API", "SQL_AND_API", "AGGREGATE"}
PATH_ALIASES = {
    "A": "DIRECT",
    "B": "SQL",
    "C": "API",
    "D": "SQL_AND_API",
    "E": "AGGREGATE",
    "N": "NONE",
}


@dataclass
class AtomicEvidenceChecklist:
    bits: dict[str, int]
    direct_answer: str = ""
    route: str = "EVIDENCE_PIPELINE"
    parse_error: str | None = None
    legacy_route_card: Any | None = None
    legacy_plan_payload: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FixedTaskSlot:
    task_id: str
    path: str
    depends_on: list[str]
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FixedTaskSlots:
    slots: list[FixedTaskSlot] = field(default_factory=list)
    aggregation_instruction: str = ""
    shape_error: str | None = None
    shape_error_message: str | None = None
    legacy_plan_payload: dict[str, Any] | None = None

    @property
    def active_slots(self) -> list[FixedTaskSlot]:
        return [slot for slot in self.slots if slot.path != "NONE"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "slots": [slot.to_dict() for slot in self.slots],
            "active_slots": [slot.to_dict() for slot in self.active_slots],
            "aggregation_instruction": self.aggregation_instruction,
            "shape_error": self.shape_error,
            "shape_error_message": self.shape_error_message,
            "legacy_plan_payload": compact_preview(self.legacy_plan_payload, 1200) if self.legacy_plan_payload else None,
        }


@dataclass
class SQLSlotCandidate:
    sql: str
    params: list[Any] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class APISlotCandidate:
    method: str
    api_path: str
    params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def run_atomic_weak_protocol(
    *,
    client: Any,
    user_prompt: str,
    schema_context: dict[str, Any],
    endpoint_context: list[dict[str, Any]],
    repair_context: dict[str, Any] | None = None,
) -> WeakProtocolResult:
    started = time.perf_counter()
    diagnostics = _base_diagnostics(repair_context is None)
    if repair_context:
        return _run_repair_context_protocol(
            client=client,
            user_prompt=user_prompt,
            schema_context=schema_context,
            endpoint_context=endpoint_context,
            repair_context=repair_context,
            diagnostics=diagnostics,
            started=started,
        )

    raw_previews: dict[str, Any] = {}
    checklist, checklist_error = _call_and_parse_checklist(client, user_prompt, diagnostics, raw_previews)
    if checklist is None:
        checklist = AtomicEvidenceChecklist(
            bits={key: 0 for key in CHECKLIST_KEYS},
            direct_answer="",
            route="EVIDENCE_PIPELINE",
            parse_error=checklist_error,
        )
        diagnostics.update(
            {
                "checklist_parse_success": False,
                "checklist_route": "EVIDENCE_PIPELINE",
                "route_gate_route": "EVIDENCE_PIPELINE",
                "planner_success": False,
                "planner_timeout": "timeout" in str(checklist_error or "").lower(),
                "planner_provider_latency_ms": _elapsed_ms(started),
            }
        )
        if diagnostics.get("planner_timeout"):
            return WeakProtocolResult(
                plan_payload={
                    "route": "EVIDENCE_PIPELINE",
                    "evidence_order": "SQL_FIRST",
                    "direct_answer": None,
                    "passes": [],
                    "aggregation_instruction": "",
                    "reason": f"Atomic checklist LLM call failed: {checklist_error or 'unknown'}",
                },
                diagnostics=diagnostics,
                raw_preview=raw_previews,
                parse_error=True,
                backend_unavailable=True,
                error_message=checklist_error,
            )
    else:
        diagnostics.update(
            {
                "checklist_parse_success": True,
                "checklist_bits": checklist.bits,
                "checklist_route": checklist.route,
                "route_card_success": True,
                "route_card_route": "DIRECT" if checklist.route == "LLM_DIRECT" else "EVIDENCE",
                "route_gate_success": True,
                "route_gate_route": checklist.route,
            }
        )
    if checklist.legacy_plan_payload is not None:
        diagnostics.update(
            {
                "weak_protocol_legacy_monolithic_response_accepted": True,
                "planner_success": True,
                "planner_json_fallback_used": True,
                "planner_provider_latency_ms": _elapsed_ms(started),
            }
        )
        if checklist.route == "LLM_DIRECT" and checklist.legacy_route_card is not None:
            challenge, challenge_raw_preview = _run_direct_route_challenge(
                client=client,
                user_prompt=user_prompt,
                route_card=checklist.legacy_route_card,
                diagnostics=diagnostics,
            )
            raw_previews.update(challenge_raw_preview)
            if challenge.needs_evidence:
                checklist = AtomicEvidenceChecklist(
                    bits={**checklist.bits, "RECORDS": 1, "PURE_CONCEPT": 0},
                    direct_answer="",
                    route="EVIDENCE_PIPELINE",
                )
            else:
                return WeakProtocolResult(
                    plan_payload=checklist.legacy_plan_payload,
                    diagnostics=diagnostics,
                    raw_preview=raw_previews,
                )
        else:
            return WeakProtocolResult(
                plan_payload=checklist.legacy_plan_payload,
                diagnostics=diagnostics,
                raw_preview=raw_previews,
            )

    if checklist.route == "LLM_DIRECT":
        if checklist.legacy_route_card is not None:
            challenge, challenge_raw_preview = _run_direct_route_challenge(
                client=client,
                user_prompt=user_prompt,
                route_card=checklist.legacy_route_card,
                diagnostics=diagnostics,
            )
            raw_previews.update(challenge_raw_preview)
            if challenge.needs_evidence:
                checklist.route = "EVIDENCE_PIPELINE"
                checklist.direct_answer = ""
                diagnostics["checklist_route"] = "EVIDENCE_PIPELINE"
            else:
                diagnostics.update(
                    {
                        "atomic_direct_answer_used": True,
                        "evidence_planner_called": False,
                        "planner_success": True,
                        "planner_provider_latency_ms": _elapsed_ms(started),
                    }
                )
                return WeakProtocolResult(
                    plan_payload={
                        "route": "LLM_DIRECT",
                        "evidence_order": "NO_EVIDENCE",
                        "direct_answer": checklist.direct_answer,
                        "passes": [],
                        "aggregation_instruction": "",
                        "reason": "Legacy route-card direct answer accepted by direct challenge.",
                    },
                    diagnostics=diagnostics,
                    raw_preview=raw_previews,
                )

    if checklist.route == "LLM_DIRECT":
        direct_answer = checklist.direct_answer.strip()
        if not direct_answer:
            direct_answer, direct_error, direct_latency = _call_text(
                client,
                system_prompt=_direct_answer_system_prompt(),
                user_prompt=f"USER_PROMPT={user_prompt}",
                max_tokens=DIRECT_ANSWER_MAX_TOKENS,
            )
            diagnostics["atomic_direct_answer_latency_ms"] = direct_latency
            raw_previews["atomic_direct_answer"] = compact_preview(direct_answer or direct_error, 800)
            if direct_error:
                direct_answer = "This is a general conceptual question; no runtime evidence was used."
        diagnostics.update(
            {
                "atomic_direct_answer_used": True,
                "evidence_planner_called": False,
                "planner_success": True,
                "planner_provider_latency_ms": _elapsed_ms(started),
            }
        )
        return WeakProtocolResult(
            plan_payload={
                "route": "LLM_DIRECT",
                "evidence_order": "NO_EVIDENCE",
                "direct_answer": direct_answer,
                "passes": [],
                "aggregation_instruction": "",
                "reason": "Atomic checklist selected pure no-evidence direct answer.",
            },
            diagnostics=diagnostics,
            raw_preview=raw_previews,
        )

    slots, slots_error = _call_and_parse_task_slots(client, user_prompt, diagnostics, raw_previews)
    if slots is None or slots.shape_error:
        diagnostics.update(
            {
                "fixed_task_slot_error": slots_error or (slots.shape_error if slots else "unknown"),
                "planner_success": False,
                "planner_provider_latency_ms": _elapsed_ms(started),
            }
        )
        return WeakProtocolResult(
            plan_payload={
                "route": "EVIDENCE_PIPELINE",
                "evidence_order": "SQL_FIRST",
                "direct_answer": None,
                "passes": [],
                "aggregation_instruction": slots.aggregation_instruction if slots else "",
                "reason": f"Fixed task slots failed shape gate: {slots_error or (slots.shape_error if slots else 'unknown')}",
            },
            diagnostics=diagnostics,
            raw_preview=raw_previews,
            parse_error=True,
        )
    if slots.legacy_plan_payload is not None:
        diagnostics.update(
            {
                "fixed_task_slots_used": True,
                "task_ledger_success": True,
                "weak_protocol_legacy_monolithic_response_accepted": True,
                "planner_json_fallback_used": True,
                "planner_success": True,
                "planner_provider_latency_ms": _elapsed_ms(started),
            }
        )
        return WeakProtocolResult(plan_payload=slots.legacy_plan_payload, diagnostics=diagnostics, raw_preview=raw_previews)

    diagnostics.update(
        {
            "fixed_task_slots_used": True,
            "slot_count": 5,
            "active_task_count": len(slots.active_slots),
            "task_paths": [slot.path for slot in slots.active_slots],
            "task_ledger_success": True,
            "task_count": len(slots.active_slots),
            "task_paths": [slot.path for slot in slots.active_slots],
            "dependency_edges": [[dep, slot.task_id] for slot in slots.active_slots for dep in slot.depends_on],
        }
    )
    passes = [
        _pass_payload_for_slot(
            client=client,
            slot=slot,
            user_prompt=user_prompt,
            schema_context=schema_context,
            endpoint_context=endpoint_context,
            diagnostics=diagnostics,
            raw_previews=raw_previews,
        )
        for slot in slots.active_slots
    ]
    diagnostics.update({"planner_success": True, "planner_provider_latency_ms": _elapsed_ms(started)})
    return WeakProtocolResult(
        plan_payload={
            "route": "EVIDENCE_PIPELINE",
            "evidence_order": "MULTI_PASS" if len(passes) > 1 else _evidence_order_for_passes(passes),
            "direct_answer": None,
            "passes": passes,
            "aggregation_instruction": slots.aggregation_instruction,
            "reason": "Atomic checklist selected evidence; fixed task slots supplied LLM-owned tasks.",
        },
        diagnostics=diagnostics,
        raw_preview=raw_previews,
    )


def parse_atomic_evidence_checklist(raw_content: str) -> AtomicEvidenceChecklist:
    legacy_payload = _legacy_full_plan_payload(raw_content)
    if legacy_payload is not None:
        route_card = parse_route_card(raw_content)
        bits = {key: 0 for key in CHECKLIST_KEYS}
        if route_card.route == "DIRECT":
            bits["PURE_CONCEPT"] = 1
            route = "LLM_DIRECT"
        else:
            bits["RECORDS"] = 1
            route = "EVIDENCE_PIPELINE"
        return AtomicEvidenceChecklist(
            bits=bits,
            direct_answer=str(route_card.direct_answer or "") if route == "LLM_DIRECT" else "",
            route=route,
            legacy_route_card=route_card,
            legacy_plan_payload=legacy_payload,
        )
    fields = _parse_fields(raw_content)
    if not all(key in fields for key in CHECKLIST_KEYS):
        try:
            route_card = parse_route_card(raw_content)
        except Exception:
            route_card = None
        if route_card is not None:
            bits = {key: 0 for key in CHECKLIST_KEYS}
            if route_card.route == "DIRECT":
                bits["PURE_CONCEPT"] = 1
                route = "LLM_DIRECT"
            else:
                bits["RECORDS"] = 1
                route = "EVIDENCE_PIPELINE"
            return AtomicEvidenceChecklist(
                bits=bits,
                direct_answer=str(route_card.direct_answer or "") if route == "LLM_DIRECT" else "",
                route=route,
                legacy_route_card=route_card,
            )
    bits: dict[str, int] = {}
    for key in CHECKLIST_KEYS:
        if key not in fields:
            raise ProtocolParseError(f"{key} is required.")
        bits[key] = _parse_bit(fields[key])
    direct_answer = str(fields.get("DIRECT_ANSWER") or "").strip()
    route = "EVIDENCE_PIPELINE"
    if any(bits[key] for key in EVIDENCE_KEYS):
        route = "EVIDENCE_PIPELINE"
    elif bits.get("PURE_CONCEPT") == 1:
        route = "LLM_DIRECT"
    return AtomicEvidenceChecklist(bits=bits, direct_answer=direct_answer if route == "LLM_DIRECT" else "", route=route)


def parse_fixed_task_slots(raw_content: str) -> FixedTaskSlots:
    legacy_payload = _legacy_full_plan_payload(raw_content)
    if legacy_payload is not None:
        return FixedTaskSlots(legacy_plan_payload=legacy_payload)
    fields = _parse_fields(raw_content)
    if not any(key.startswith("T1_") for key in fields):
        try:
            ledger = parse_task_ledger_card(raw_content)
        except Exception:
            ledger = None
        if ledger is not None:
            if ledger.legacy_plan_payload is not None:
                return FixedTaskSlots(legacy_plan_payload=ledger.legacy_plan_payload)
            slots = [
                FixedTaskSlot(
                    task_id=str(task.task_id),
                    path=str(task.path),
                    depends_on=[str(dep) for dep in task.depends_on],
                    description=str(task.description or ""),
                )
                for task in ledger.tasks
            ]
            result = FixedTaskSlots(slots=slots, aggregation_instruction=str(ledger.aggregation_instruction or ""))
            error = _slot_shape_error(result.active_slots)
            if error:
                result.shape_error, result.shape_error_message = error
            return result
    slots: list[FixedTaskSlot] = []
    for index in range(1, 6):
        task_id = f"T{index}"
        path = _parse_slot_path(fields.get(f"{task_id}_PATH") or "NONE")
        deps = _parse_deps(fields.get(f"{task_id}_DEPS") or "[]")
        desc = str(fields.get(f"{task_id}_DESC") or "").strip()
        slots.append(FixedTaskSlot(task_id=task_id, path=path, depends_on=deps, description=desc))
    ledger = FixedTaskSlots(slots=slots, aggregation_instruction=str(fields.get("AGGREGATE") or "").strip())
    error = _slot_shape_error(ledger.active_slots)
    if error:
        ledger.shape_error, ledger.shape_error_message = error
    return ledger


def parse_slot_sql_candidate(raw_content: str) -> SQLSlotCandidate:
    fields = _parse_fields(raw_content)
    sql = str(fields.get("SQL_QUERY") or fields.get("SQL") or fields.get("QUERY") or "").strip()
    if not sql:
        legacy = parse_pass_candidate_card(raw_content)
        if legacy.path == "SQL" and legacy.sql:
            return SQLSlotCandidate(sql=str(legacy.sql), params=legacy.params if isinstance(legacy.params, list) else [])
        raise ProtocolParseError("SQL_QUERY is required.")
    params = _parse_json_value(fields.get("PARAMS_JSON") or fields.get("PARAMS"), default=[])
    return SQLSlotCandidate(sql=sql, params=params if isinstance(params, list) else [])


def parse_slot_api_candidate(raw_content: str) -> APISlotCandidate:
    fields = _parse_fields(raw_content)
    method = str(fields.get("METHOD") or "GET").strip().upper()
    api_path = str(fields.get("API_PATH") or fields.get("PATH") or "").strip()
    if not api_path:
        legacy = parse_pass_candidate_card(raw_content)
        if legacy.path == "API" and legacy.api_path:
            return APISlotCandidate(
                method=str(legacy.method or "GET").upper(),
                api_path=str(legacy.api_path),
                params=legacy.params if isinstance(legacy.params, dict) else {},
            )
        raise ProtocolParseError("API_PATH is required.")
    params = _parse_json_value(fields.get("PARAMS_JSON") or fields.get("PARAMS"), default={})
    return APISlotCandidate(method=method, api_path=api_path, params=params if isinstance(params, dict) else {})


def _base_diagnostics(initial: bool) -> dict[str, Any]:
    return {
        "weak_model_stable_protocol_used": True,
        "weak_protocol_route_card_used": initial,
        "weak_protocol_task_ledger_used": False,
        "llm_route_gate_used": initial,
        "atomic_weak_protocol_used": True,
        "atomic_checklist_used": initial,
        "checklist_bits": {},
        "checklist_parse_success": False,
        "checklist_repair_attempted": False,
        "checklist_route": None,
        "backend_semantic_routing_used": False,
        "backend_route_inference_used": False,
        "backend_semantic_planning_used": False,
        "backend_semantic_decomposition_used": False,
        "fixed_task_slots_used": False,
        "slot_count": 5,
        "active_task_count": 0,
        "task_slot_repair_attempted": False,
        "atomic_candidate_slots_used": False,
        "sql_candidate_success_count": 0,
        "api_candidate_success_count": 0,
        "candidate_repair_attempts": 0,
        "candidate_card_success": 0,
        "pass_candidate_cards": 0,
        "sql_candidate_cards": 0,
        "api_candidate_cards": 0,
        "route_card_success": False,
        "route_card_route": None,
        "route_card_repair_attempted": False,
        "route_gate_success": False,
        "route_gate_route": None,
        "route_gate_repair_attempted": False,
        "direct_route_challenge_used": False,
        "direct_route_challenge_needs_evidence": None,
        "direct_route_challenge_repair_attempted": False,
        "task_ledger_success": False,
        "task_ledger_repair_attempted": False,
        "route_card_max_tokens": CHECKLIST_MAX_TOKENS,
        "task_ledger_max_tokens": TASK_SLOTS_MAX_TOKENS,
        "candidate_card_max_tokens": CANDIDATE_MAX_TOKENS,
        "candidate_repair_max_tokens": CANDIDATE_REPAIR_MAX_TOKENS,
        "final_answer_max_tokens": 500,
    }


def _call_and_parse_checklist(
    client: Any,
    user_prompt: str,
    diagnostics: dict[str, Any],
    raw_previews: dict[str, Any],
) -> tuple[AtomicEvidenceChecklist | None, str | None]:
    raw, error, latency = _call_text(
        client,
        system_prompt=_checklist_system_prompt(),
        user_prompt=_checklist_user_prompt(user_prompt),
        max_tokens=CHECKLIST_MAX_TOKENS,
    )
    diagnostics["checklist_latency_ms"] = latency
    raw_previews["atomic_checklist"] = compact_preview(raw or error, 900)
    parse_error = error
    if not error:
        try:
            return parse_atomic_evidence_checklist(raw), None
        except Exception as exc:
            parse_error = str(exc)
    diagnostics["checklist_repair_attempted"] = True
    diagnostics["route_card_repair_attempted"] = True
    diagnostics["route_gate_repair_attempted"] = True
    repair_raw, repair_error, repair_latency = _call_text(
        client,
        system_prompt=_checklist_repair_system_prompt(),
        user_prompt=_checklist_repair_user_prompt(user_prompt, raw, parse_error),
        max_tokens=CHECKLIST_MAX_TOKENS,
    )
    diagnostics["checklist_repair_latency_ms"] = repair_latency
    raw_previews["atomic_checklist_repair"] = compact_preview(repair_raw or repair_error, 900)
    if repair_error:
        return None, repair_error
    try:
        return parse_atomic_evidence_checklist(repair_raw), None
    except Exception as exc:
        return None, str(exc)


def _call_and_parse_task_slots(
    client: Any,
    user_prompt: str,
    diagnostics: dict[str, Any],
    raw_previews: dict[str, Any],
) -> tuple[FixedTaskSlots | None, str | None]:
    raw, error, latency = _call_text(
        client,
        system_prompt=_task_slots_system_prompt(),
        user_prompt=_task_slots_user_prompt(user_prompt),
        max_tokens=TASK_SLOTS_MAX_TOKENS,
    )
    diagnostics["task_ledger_latency_ms"] = latency
    diagnostics["evidence_planner_called"] = True
    diagnostics["weak_protocol_task_ledger_used"] = True
    raw_previews["fixed_task_slots"] = compact_preview(raw or error, 1400)
    parse_error = error
    slots: FixedTaskSlots | None = None
    if not error:
        try:
            slots = parse_fixed_task_slots(raw)
            parse_error = slots.shape_error
        except Exception as exc:
            parse_error = str(exc)
    if slots is not None and not slots.shape_error:
        return slots, None
    diagnostics["task_slot_repair_attempted"] = True
    diagnostics["task_ledger_repair_attempted"] = True
    diagnostics["planner_repair_attempted"] = True
    repair_raw, repair_error, repair_latency = _call_text(
        client,
        system_prompt=_task_slots_repair_system_prompt(),
        user_prompt=_task_slots_repair_user_prompt(user_prompt, raw, parse_error),
        max_tokens=TASK_SLOTS_MAX_TOKENS,
    )
    diagnostics["task_ledger_repair_latency_ms"] = repair_latency
    raw_previews["fixed_task_slots_repair"] = compact_preview(repair_raw or repair_error, 1400)
    if repair_error:
        return None, repair_error
    try:
        slots = parse_fixed_task_slots(repair_raw)
        return slots, slots.shape_error
    except Exception as exc:
        return None, str(exc)


def _pass_payload_for_slot(
    *,
    client: Any,
    slot: FixedTaskSlot,
    user_prompt: str,
    schema_context: dict[str, Any],
    endpoint_context: list[dict[str, Any]],
    diagnostics: dict[str, Any],
    raw_previews: dict[str, Any],
) -> dict[str, Any]:
    sql_payload = None
    api_payload = None
    if slot.path in {"SQL", "SQL_AND_API"}:
        candidate = _sql_candidate_for_slot(client, user_prompt, slot, schema_context, diagnostics, raw_previews)
        if candidate:
            sql_payload = {"query": candidate.sql, "params": candidate.params}
    if slot.path in {"API", "SQL_AND_API"}:
        candidate = _api_candidate_for_slot(client, user_prompt, slot, endpoint_context, diagnostics, raw_previews)
        if candidate:
            api_payload = {"method": candidate.method, "path": candidate.api_path, "params": candidate.params}
    path = "AGGREGATION_ONLY" if slot.path == "AGGREGATE" else slot.path
    return {
        "pass_id": slot.task_id,
        "subtask": slot.description,
        "path": path,
        "can_run_parallel": not bool(slot.depends_on),
        "depends_on": slot.depends_on,
        "evidence_order": _evidence_order_for_path(slot.path),
        "sql": sql_payload,
        "api_request": api_payload,
        "expected_result": slot.description,
    }


def _sql_candidate_for_slot(
    client: Any,
    user_prompt: str,
    slot: FixedTaskSlot,
    schema_context: dict[str, Any],
    diagnostics: dict[str, Any],
    raw_previews: dict[str, Any],
    repair_context: dict[str, Any] | None = None,
) -> SQLSlotCandidate | None:
    diagnostics["atomic_candidate_slots_used"] = True
    diagnostics["pass_candidate_cards"] += 1
    diagnostics["sql_candidate_cards"] += 1
    raw, error, latency = _call_text(
        client,
        system_prompt=_sql_candidate_system_prompt(),
        user_prompt=_sql_candidate_user_prompt(user_prompt, slot, schema_context, repair_context),
        max_tokens=CANDIDATE_MAX_TOKENS,
    )
    diagnostics["candidate_card_latency_ms"] = int(diagnostics.get("candidate_card_latency_ms", 0) or 0) + latency
    raw_previews[f"atomic_sql_candidate_{slot.task_id}"] = compact_preview(raw or error, 1000)
    if not error:
        legacy_payload = _legacy_full_plan_payload(raw)
        legacy_candidate = _candidate_from_legacy_plan(legacy_payload, slot.task_id, "SQL") if legacy_payload else None
        if legacy_candidate and legacy_candidate.sql:
            diagnostics["sql_candidate_success_count"] += 1
            diagnostics["candidate_card_success"] += 1
            return SQLSlotCandidate(
                sql=str(legacy_candidate.sql),
                params=legacy_candidate.params if isinstance(legacy_candidate.params, list) else [],
            )
        try:
            candidate = parse_slot_sql_candidate(raw)
            diagnostics["sql_candidate_success_count"] += 1
            diagnostics["candidate_card_success"] += 1
            return candidate
        except Exception as exc:
            error = str(exc)
    diagnostics["candidate_repair_attempts"] += 1
    repair_raw, repair_error, repair_latency = _call_text(
        client,
        system_prompt=_sql_candidate_repair_system_prompt(),
        user_prompt=_sql_candidate_repair_user_prompt(user_prompt, slot, raw, error, schema_context, repair_context),
        max_tokens=CANDIDATE_REPAIR_MAX_TOKENS,
    )
    diagnostics["candidate_card_latency_ms"] = int(diagnostics.get("candidate_card_latency_ms", 0) or 0) + repair_latency
    raw_previews[f"atomic_sql_candidate_repair_{slot.task_id}"] = compact_preview(repair_raw or repair_error, 1000)
    if repair_error:
        return None
    legacy_payload = _legacy_full_plan_payload(repair_raw)
    legacy_candidate = _candidate_from_legacy_plan(legacy_payload, slot.task_id, "SQL") if legacy_payload else None
    if legacy_candidate and legacy_candidate.sql:
        diagnostics["sql_candidate_success_count"] += 1
        diagnostics["candidate_card_success"] += 1
        return SQLSlotCandidate(
            sql=str(legacy_candidate.sql),
            params=legacy_candidate.params if isinstance(legacy_candidate.params, list) else [],
        )
    try:
        candidate = parse_slot_sql_candidate(repair_raw)
        diagnostics["sql_candidate_success_count"] += 1
        diagnostics["candidate_card_success"] += 1
        return candidate
    except Exception:
        return None


def _api_candidate_for_slot(
    client: Any,
    user_prompt: str,
    slot: FixedTaskSlot,
    endpoint_context: list[dict[str, Any]],
    diagnostics: dict[str, Any],
    raw_previews: dict[str, Any],
    repair_context: dict[str, Any] | None = None,
) -> APISlotCandidate | None:
    diagnostics["atomic_candidate_slots_used"] = True
    diagnostics["pass_candidate_cards"] += 1
    diagnostics["api_candidate_cards"] += 1
    raw, error, latency = _call_text(
        client,
        system_prompt=_api_candidate_system_prompt(),
        user_prompt=_api_candidate_user_prompt(user_prompt, slot, endpoint_context, repair_context),
        max_tokens=CANDIDATE_MAX_TOKENS,
    )
    diagnostics["candidate_card_latency_ms"] = int(diagnostics.get("candidate_card_latency_ms", 0) or 0) + latency
    raw_previews[f"atomic_api_candidate_{slot.task_id}"] = compact_preview(raw or error, 1000)
    if not error:
        legacy_payload = _legacy_full_plan_payload(raw)
        legacy_candidate = _candidate_from_legacy_plan(legacy_payload, slot.task_id, "API") if legacy_payload else None
        if legacy_candidate and legacy_candidate.api_path:
            diagnostics["api_candidate_success_count"] += 1
            diagnostics["candidate_card_success"] += 1
            return APISlotCandidate(
                method=str(legacy_candidate.method or "GET").upper(),
                api_path=str(legacy_candidate.api_path),
                params=legacy_candidate.params if isinstance(legacy_candidate.params, dict) else {},
            )
        try:
            candidate = parse_slot_api_candidate(raw)
            diagnostics["api_candidate_success_count"] += 1
            diagnostics["candidate_card_success"] += 1
            return candidate
        except Exception as exc:
            error = str(exc)
    diagnostics["candidate_repair_attempts"] += 1
    repair_raw, repair_error, repair_latency = _call_text(
        client,
        system_prompt=_api_candidate_repair_system_prompt(),
        user_prompt=_api_candidate_repair_user_prompt(user_prompt, slot, raw, error, endpoint_context, repair_context),
        max_tokens=CANDIDATE_REPAIR_MAX_TOKENS,
    )
    diagnostics["candidate_card_latency_ms"] = int(diagnostics.get("candidate_card_latency_ms", 0) or 0) + repair_latency
    raw_previews[f"atomic_api_candidate_repair_{slot.task_id}"] = compact_preview(repair_raw or repair_error, 1000)
    if repair_error:
        return None
    legacy_payload = _legacy_full_plan_payload(repair_raw)
    legacy_candidate = _candidate_from_legacy_plan(legacy_payload, slot.task_id, "API") if legacy_payload else None
    if legacy_candidate and legacy_candidate.api_path:
        diagnostics["api_candidate_success_count"] += 1
        diagnostics["candidate_card_success"] += 1
        return APISlotCandidate(
            method=str(legacy_candidate.method or "GET").upper(),
            api_path=str(legacy_candidate.api_path),
            params=legacy_candidate.params if isinstance(legacy_candidate.params, dict) else {},
        )
    try:
        candidate = parse_slot_api_candidate(repair_raw)
        diagnostics["api_candidate_success_count"] += 1
        diagnostics["candidate_card_success"] += 1
        return candidate
    except Exception:
        return None


def _run_repair_context_protocol(
    *,
    client: Any,
    user_prompt: str,
    schema_context: dict[str, Any],
    endpoint_context: list[dict[str, Any]],
    repair_context: dict[str, Any],
    diagnostics: dict[str, Any],
    started: float,
) -> WeakProtocolResult:
    previous = repair_context.get("previous_plan") if isinstance(repair_context.get("previous_plan"), dict) else {}
    failed_component = str(repair_context.get("failed_component") or "")
    pass_id = str(repair_context.get("pass_id") or "")
    if failed_component not in {"sql", "api_request"}:
        raw_previews: dict[str, Any] = {}
        raw, error, latency = _call_text(
            client,
            system_prompt=_full_plan_repair_system_prompt(),
            user_prompt=_full_plan_repair_user_prompt(user_prompt, schema_context, endpoint_context, repair_context),
            max_tokens=TASK_SLOTS_MAX_TOKENS,
        )
        diagnostics["planner_repair_attempted"] = True
        diagnostics["planner_repair_latency_ms"] = latency
        diagnostics["planner_provider_latency_ms"] = _elapsed_ms(started)
        raw_previews["atomic_full_plan_repair"] = compact_preview(raw or error, 1400)
        if error:
            diagnostics["planner_success"] = False
            return WeakProtocolResult(
                plan_payload=previous or {"route": "EVIDENCE_PIPELINE", "passes": []},
                diagnostics=diagnostics,
                raw_preview=raw_previews,
                parse_error=True,
                error_message=error,
            )
        legacy_payload = _legacy_full_plan_payload(raw)
        if legacy_payload is not None:
            diagnostics["planner_success"] = True
            diagnostics["planner_json_fallback_used"] = True
            return WeakProtocolResult(plan_payload=legacy_payload, diagnostics=diagnostics, raw_preview=raw_previews)
        try:
            slots = parse_fixed_task_slots(raw)
        except Exception as exc:
            diagnostics["planner_success"] = False
            return WeakProtocolResult(
                plan_payload=previous or {"route": "EVIDENCE_PIPELINE", "passes": []},
                diagnostics=diagnostics,
                raw_preview=raw_previews,
                parse_error=True,
                error_message=str(exc),
            )
        if slots.legacy_plan_payload is not None:
            diagnostics["planner_success"] = True
            diagnostics["planner_json_fallback_used"] = True
            return WeakProtocolResult(plan_payload=slots.legacy_plan_payload, diagnostics=diagnostics, raw_preview=raw_previews)
        diagnostics["planner_success"] = False
        return WeakProtocolResult(
            plan_payload=previous or {"route": "EVIDENCE_PIPELINE", "passes": []},
            diagnostics=diagnostics,
            raw_preview=raw_previews,
            parse_error=True,
            error_message=slots.shape_error or "full_plan_repair_missing_plan_payload",
        )
    passes = [dict(item) for item in previous.get("passes", []) if isinstance(item, dict)]
    target = next((item for item in passes if str(item.get("pass_id")) == pass_id), None)
    if target is None:
        return WeakProtocolResult(plan_payload=previous or {"route": "EVIDENCE_PIPELINE", "passes": []}, diagnostics=diagnostics, parse_error=True)
    slot = FixedTaskSlot(
        task_id=pass_id,
        path="SQL" if failed_component == "sql" else "API",
        depends_on=[str(dep) for dep in target.get("depends_on", [])] if isinstance(target.get("depends_on"), list) else [],
        description=str(repair_context.get("subtask") or target.get("subtask") or "Repair candidate"),
    )
    raw_previews: dict[str, Any] = {}
    if failed_component == "sql":
        candidate = _sql_candidate_for_slot(client, user_prompt, slot, schema_context, diagnostics, raw_previews, repair_context=repair_context)
        if candidate:
            target["sql"] = {"query": candidate.sql, "params": candidate.params}
    elif failed_component == "api_request":
        candidate = _api_candidate_for_slot(client, user_prompt, slot, endpoint_context, diagnostics, raw_previews, repair_context=repair_context)
        if candidate:
            target["api_request"] = {"method": candidate.method, "path": candidate.api_path, "params": candidate.params}
    else:
        diagnostics.update({"planner_success": False, "planner_provider_latency_ms": _elapsed_ms(started)})
        return WeakProtocolResult(plan_payload=previous, diagnostics=diagnostics, raw_preview={"repair_context": compact_preview(repair_context, 1000)}, parse_error=True)
    payload = {**previous, "passes": passes}
    diagnostics.update(
        {
            "weak_protocol_candidate_repair_card_used": True,
            "planner_success": True,
            "planner_provider_latency_ms": _elapsed_ms(started),
        }
    )
    return WeakProtocolResult(plan_payload=_merge_repaired_pass_payload(previous, payload, pass_id), diagnostics=diagnostics, raw_preview=raw_previews)


def _parse_fields(raw_content: str) -> dict[str, Any]:
    parsed = _try_json_object(raw_content)
    if parsed is not None:
        return {str(key).upper(): value for key, value in parsed.items()}
    fields: dict[str, str] = {}
    for raw_line in str(raw_content or "").splitlines():
        line = _strip_line(raw_line)
        if not line:
            continue
        equal_at = line.find("=")
        colon_at = line.find(":")
        split_at = -1
        if equal_at >= 0 and colon_at >= 0:
            split_at = min(equal_at, colon_at)
        elif equal_at >= 0:
            split_at = equal_at
        elif colon_at >= 0:
            split_at = colon_at
        if split_at < 0:
            continue
        key = line[:split_at].strip().upper()
        value = line[split_at + 1 :].strip()
        fields[key] = value
    return fields


def _try_json_object(raw_content: str) -> dict[str, Any] | None:
    text = str(raw_content or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json|text)?\s*", "", text, flags=re.I).strip()
        text = re.sub(r"\s*```$", "", text).strip()
    if not text.lstrip().startswith("{"):
        return None
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    text = re.sub(r",(\s*[}\]])", r"\1", text[start : end + 1])
    try:
        payload = json.loads(text)
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _strip_line(raw_line: Any) -> str:
    line = str(raw_line or "").strip()
    line = re.sub(r"^```(?:json|text)?\s*", "", line, flags=re.I).strip()
    line = re.sub(r"\s*```$", "", line).strip()
    line = re.sub(r"^\s*[-*]\s+", "", line)
    line = re.sub(r"^\s*\d+[\.)]\s+", "", line)
    return line.strip()


def _parse_bit(value: Any) -> int:
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, (int, float)) and value in (0, 1):
        return int(value)
    text = str(value).strip().upper()
    if text in {"1", "YES", "Y", "TRUE", "是"}:
        return 1
    if text in {"0", "NO", "N", "FALSE", "否"}:
        return 0
    raise ProtocolParseError(f"Invalid binary value: {value}")


def _parse_slot_path(value: Any) -> str:
    text = str(value or "NONE").strip().upper()
    text = PATH_ALIASES.get(text, text)
    if text not in SLOT_PATHS:
        raise ProtocolParseError(f"Invalid slot path: {text}")
    return text


def _parse_deps(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip().upper() for item in value if str(item).strip()]
    text = str(value or "").strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [str(item).strip().upper() for item in parsed if str(item).strip()]
    except Exception:
        pass
    text = text.strip("[]")
    return [item.strip().upper() for item in text.split(",") if item.strip()]


def _parse_json_value(value: Any, *, default: Any) -> Any:
    if value is None or str(value).strip() == "":
        return default
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(str(value))
    except Exception:
        return default


def _slot_shape_error(slots: list[FixedTaskSlot]) -> tuple[str, str] | None:
    if not slots:
        return "empty_task_slots", "Evidence route requires at least one active slot."
    ids = {slot.task_id for slot in slots}
    for slot in slots:
        for dep in slot.depends_on:
            if dep not in ids:
                return "unknown_dependency", f"{slot.task_id} depends on unknown slot {dep}."
        if slot.path == "AGGREGATE" and not slot.depends_on:
            return "aggregation_without_dependencies", f"{slot.task_id} is AGGREGATE but has no dependencies."
    if not any(slot.path in {"SQL", "API", "SQL_AND_API"} for slot in slots):
        return "missing_executable_evidence_slot", "Evidence route requires at least one SQL/API/SQL_AND_API slot."
    if _has_cycle(slots):
        return "dependency_cycle", "Task slot dependencies contain a cycle."
    return None


def _has_cycle(slots: list[FixedTaskSlot]) -> bool:
    deps = {slot.task_id: set(slot.depends_on) for slot in slots}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(task_id: str) -> bool:
        if task_id in visiting:
            return True
        if task_id in visited:
            return False
        visiting.add(task_id)
        for dep in deps.get(task_id, set()):
            if dep in deps and visit(dep):
                return True
        visiting.remove(task_id)
        visited.add(task_id)
        return False

    return any(visit(slot.task_id) for slot in slots)


def _evidence_order_for_path(path: str) -> str:
    if path == "API":
        return "API_FIRST"
    if path == "SQL_AND_API":
        return "PARALLEL"
    if path in {"DIRECT", "AGGREGATE", "NONE"}:
        return "NO_EVIDENCE"
    return "SQL_FIRST"


def _evidence_order_for_passes(passes: list[dict[str, Any]]) -> str:
    if not passes:
        return "SQL_FIRST"
    orders = {str(item.get("evidence_order") or "") for item in passes}
    if "PARALLEL" in orders:
        return "PARALLEL"
    if "API_FIRST" in orders and "SQL_FIRST" not in orders:
        return "API_FIRST"
    return "SQL_FIRST"


def _checklist_system_prompt() -> str:
    return (
        "Fill the Atomic Evidence Need Checklist. Output only fixed fields. "
        "Use 1 or 0. Do not output SQL, API, tasks, JSON explanations, or markdown."
    )


def _checklist_user_prompt(user_prompt: str) -> str:
    fields = "\n".join([f"{key}=0|1" for key in CHECKLIST_KEYS])
    return "\n".join(
        [
            f"USER_PROMPT={user_prompt}",
            "Definitions: RECORDS actual records/entities/data the system has; LIST list actual items; COUNT count/number/total; STATUS state/active/inactive/published/draft; DATE when/date/created/updated/published/modified; LOCAL_SNAPSHOT local DB/stored records; LIVE_CURRENT current/live/platform/API state; SHOW_ITEMS show/list/give actual items; MIXED_CONCEPT_DATA both explanation and data request; PURE_CONCEPT purely concept/meta/general no runtime data.",
            "If any data flag is 1, PURE_CONCEPT must be 0 and DIRECT_ANSWER empty.",
            "DIRECT_ANSWER only for pure concept/meta/general prompts.",
            fields,
            "DIRECT_ANSWER=<short answer if pure concept, else empty>",
        ]
    )


def _checklist_repair_system_prompt() -> str:
    return "Repair the Atomic Evidence Need Checklist. Output every fixed field exactly once. Use 1 or 0. If uncertain set a data flag to 1."


def _checklist_repair_user_prompt(user_prompt: str, raw: str, error: str | None) -> str:
    return "\n".join([f"USER_PROMPT={user_prompt}", f"PREVIOUS_RESPONSE={compact_preview(raw, 700)}", f"PARSE_ERROR={error or 'unknown'}", _checklist_user_prompt(user_prompt)])


def _direct_answer_system_prompt() -> str:
    return "Answer the pure concept/meta/general prompt concisely. Plain text only. Do not claim user-specific records or live platform state."


def _task_slots_system_prompt() -> str:
    return "Fill exactly five fixed task slots. Do not output SQL or API requests."


def _task_slots_user_prompt(user_prompt: str) -> str:
    lines = [
        f"USER_PROMPT={user_prompt}",
        "Allowed paths: NONE, DIRECT, SQL, API, SQL_AND_API, AGGREGATE. Letter aliases: A=DIRECT, B=SQL, C=API, D=SQL_AND_API, E=AGGREGATE, N=NONE.",
        "DIRECT=concept only inside mixed prompt. SQL=local snapshot. API=live/current/platform/API. SQL_AND_API=both local and live. AGGREGATE=combine previous slots. NONE=unused.",
        "Use at least one SQL/API/SQL_AND_API slot for evidence prompts. For mixed concept+data include DIRECT plus SQL/API. For compare local/live include SQL_AND_API or SQL plus API.",
    ]
    for idx in range(1, 6):
        lines.extend([f"T{idx}_PATH=NONE", f"T{idx}_DEPS=[]", f"T{idx}_DESC="])
    lines.append("AGGREGATE=<how to combine results>")
    return "\n".join(lines)


def _task_slots_repair_system_prompt() -> str:
    return "Repair fixed task slots. Output T1_PATH/T1_DEPS/T1_DESC through T5 and AGGREGATE only. Do not output SQL/API."


def _task_slots_repair_user_prompt(user_prompt: str, raw: str, error: str | None) -> str:
    return "\n".join([f"USER_PROMPT={user_prompt}", f"PREVIOUS_RESPONSE={compact_preview(raw, 1000)}", f"SHAPE_ERROR={error or 'unknown'}", _task_slots_user_prompt(user_prompt)])


def _sql_candidate_system_prompt() -> str:
    return "Fill one SQL candidate slot. Output SQL_QUERY and PARAMS_JSON only. Use only schema context."


def _sql_candidate_user_prompt(user_prompt: str, slot: FixedTaskSlot, schema_context: dict[str, Any], repair_context: dict[str, Any] | None = None) -> str:
    if repair_context is not None:
        return json.dumps(
            redact_secrets(
                {
                    "user_prompt": user_prompt,
                    "task_id": slot.task_id,
                    "task_description": slot.description,
                    "repair_context": repair_context,
                    "SQLCompileGate sanitized error": _gate_error(repair_context, "SQL"),
                    "Schema context": _compact_schema_lines(schema_context, max_tables=12),
                    "output": ["SQL_QUERY=<one line SQL>", "PARAMS_JSON=[]"],
                }
            ),
            sort_keys=True,
        )
    return "\n".join(
        [
            f"USER_PROMPT={user_prompt}",
            f"TASK_ID={slot.task_id}",
            f"TASK_DESCRIPTION={slot.description}",
            "Schema context:",
            _compact_schema_lines(schema_context, max_tables=12),
            _repair_error_lines(repair_context, "SQL"),
            "Output exactly:",
            "SQL_QUERY=<one line SQL>",
            "PARAMS_JSON=[]",
        ]
    )


def _api_candidate_system_prompt() -> str:
    return "Fill one API candidate slot. Output METHOD, API_PATH, and PARAMS_JSON only. Use only endpoint context."


def _api_candidate_user_prompt(user_prompt: str, slot: FixedTaskSlot, endpoint_context: list[dict[str, Any]], repair_context: dict[str, Any] | None = None) -> str:
    if repair_context is not None:
        return json.dumps(
            redact_secrets(
                {
                    "user_prompt": user_prompt,
                    "task_id": slot.task_id,
                    "task_description": slot.description,
                    "repair_context": repair_context,
                    "APIRequestGate sanitized error": _gate_error(repair_context, "API"),
                    "Safe GET endpoint context": _compact_endpoint_lines(endpoint_context, max_endpoints=10),
                    "output": ["METHOD=GET", "API_PATH=/...", "PARAMS_JSON={}"],
                }
            ),
            sort_keys=True,
        )
    return "\n".join(
        [
            f"USER_PROMPT={user_prompt}",
            f"TASK_ID={slot.task_id}",
            f"TASK_DESCRIPTION={slot.description}",
            "Safe GET endpoint context:",
            _compact_endpoint_lines(endpoint_context, max_endpoints=10),
            _repair_error_lines(repair_context, "API"),
            "Output exactly:",
            "METHOD=GET",
            "API_PATH=/...",
            "PARAMS_JSON={}",
        ]
    )


def _sql_candidate_repair_system_prompt() -> str:
    return "Repair the SQL candidate slot. Output SQL_QUERY and PARAMS_JSON only. Backend will not rewrite SQL."


def _sql_candidate_repair_user_prompt(user_prompt: str, slot: FixedTaskSlot, raw: str, error: str | None, schema_context: dict[str, Any], repair_context: dict[str, Any] | None) -> str:
    return "\n".join(
        [
            f"USER_PROMPT={user_prompt}",
            f"TASK_ID={slot.task_id}",
            f"TASK_DESCRIPTION={slot.description}",
            f"PREVIOUS_CANDIDATE={compact_preview(raw, 900)}",
            f"SQLCompileGate sanitized error: {_gate_error(repair_context, 'SQL') or error or 'unknown'}",
            "Schema context:",
            _compact_schema_lines(schema_context, max_tables=12),
            "Use only schema context.",
        ]
    )


def _api_candidate_repair_system_prompt() -> str:
    return "Repair the API candidate slot. Output METHOD, API_PATH, and PARAMS_JSON only. Backend will not rewrite API."


def _api_candidate_repair_user_prompt(user_prompt: str, slot: FixedTaskSlot, raw: str, error: str | None, endpoint_context: list[dict[str, Any]], repair_context: dict[str, Any] | None) -> str:
    return "\n".join(
        [
            f"USER_PROMPT={user_prompt}",
            f"TASK_ID={slot.task_id}",
            f"TASK_DESCRIPTION={slot.description}",
            f"PREVIOUS_CANDIDATE={compact_preview(raw, 900)}",
            f"APIRequestGate sanitized error: {_gate_error(repair_context, 'API') or error or 'unknown'}",
            "Safe GET endpoint context:",
            _compact_endpoint_lines(endpoint_context, max_endpoints=10),
            "Use only endpoint context.",
        ]
    )


def _full_plan_repair_system_prompt() -> str:
    return (
        "Repair the LLM-owned V2 evidence plan. Return only a valid plan using your own task semantics. "
        "The backend will validate graph shape and will not add, remove, or rewrite semantic passes."
    )


def _full_plan_repair_user_prompt(
    user_prompt: str,
    schema_context: dict[str, Any],
    endpoint_context: list[dict[str, Any]],
    repair_context: dict[str, Any],
) -> str:
    payload = {
        "user_prompt": user_prompt,
        "repair_context": repair_context,
        "schema_context": _compact_schema_lines(schema_context, max_tables=12),
        "endpoint_context": _compact_endpoint_lines(endpoint_context, max_endpoints=10),
        "expected_shape": {
            "route": "EVIDENCE_PIPELINE",
            "evidence_order": "SQL_FIRST|API_FIRST|PARALLEL|MULTI_PASS",
            "passes": [
                {
                    "pass_id": "string",
                    "subtask": "short description",
                    "path": "SQL|API|SQL_AND_API|DIRECT|AGGREGATION_ONLY",
                    "depends_on": [],
                    "sql": {"query": "string", "params": []},
                    "api_request": {"method": "GET", "path": "/...", "params": {}},
                }
            ],
            "aggregation_instruction": "how to combine results",
        },
    }
    return json.dumps(redact_secrets(payload), sort_keys=True)


def _repair_error_lines(repair_context: dict[str, Any] | None, source: str) -> str:
    error = _gate_error(repair_context, source)
    return f"Gate error: {error}" if error else ""


def _gate_error(repair_context: dict[str, Any] | None, source: str) -> str:
    if not isinstance(repair_context, dict):
        return ""
    keys = ["sql_compile_gate", "compile_gate", "sql_gate"] if source == "SQL" else ["api_request_gate", "api_gate"]
    for key in keys:
        value = repair_context.get(key)
        if isinstance(value, dict):
            return str(redact_secrets(value.get("error_message") or value.get("message") or value.get("error") or ""))[:500]
    return str(redact_secrets(repair_context.get("error_message") or repair_context.get("gate_error") or ""))[:500]
