from __future__ import annotations

import json
import time
from typing import Any

from .trajectory import compact_preview, redact_secrets
from .v2_atomic_weak_protocol import run_atomic_weak_protocol
from .v2_semantic_ir import SemanticIRPlan, parse_semantic_ir_from_json_or_line_protocol, semantic_plan_to_dict
from .v2_semantic_ir_compiler import compile_semantic_ir_to_plan_payload
from .v2_semantic_ir_context import build_allowed_api_context_card, build_allowed_local_schema_card
from .v2_semantic_ir_validator import SemanticIRValidationResult, SemanticIRValidator
from .v2_weak_model_protocol import WeakProtocolResult, _elapsed_ms
from .v2_weak_model_protocol import _legacy_full_plan_payload


SEMANTIC_IR_TOOL_NAME = "submit_semantic_ir_plan"


def semantic_ir_tool_schema() -> dict[str, Any]:
    task_schema: dict[str, Any] = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "task_id": {"type": "string"},
            "kind": {"type": "string", "enum": ["CONCEPT", "LOCAL_QUERY", "LIVE_QUERY", "LOCAL_AND_LIVE", "AGGREGATE"]},
            "operation": {"type": "string", "enum": ["EXPLAIN", "LIST", "COUNT", "LOOKUP", "STATUS", "DATE", "COMPARE"]},
            "source": {"type": "string", "enum": ["NONE", "LOCAL_SNAPSHOT", "LIVE_API", "BOTH"]},
            "local_query": {
                "anyOf": [
                    {"type": "null"},
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "table": {"type": "string"},
                            "fields": {"type": "array", "items": {"type": "string"}},
                            "filters": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "properties": {
                                        "field": {"type": "string"},
                                        "op": {"type": "string", "enum": ["=", "!=", "contains", "in", ">=", "<=", ">", "<"]},
                                        "value": {},
                                    },
                                    "required": ["field", "op", "value"],
                                },
                            },
                            "limit": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
                            "count": {"type": "boolean"},
                        },
                        "required": ["table", "fields", "filters", "limit", "count"],
                    },
                ]
            },
            "api_query": {
                "anyOf": [
                    {"type": "null"},
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "endpoint_id": {"type": "string"},
                            "method": {"type": "string", "enum": ["GET"]},
                            "path_params": {"type": "object"},
                            "query_params": {"type": "object"},
                        },
                        "required": ["endpoint_id", "method", "path_params", "query_params"],
                    },
                ]
            },
            "depends_on": {"type": "array", "items": {"type": "string"}},
            "description": {"type": "string"},
            "required": {"type": "boolean"},
        },
        "required": ["task_id", "kind", "operation", "source", "local_query", "api_query", "depends_on", "description", "required"],
    }
    return {
        "type": "function",
        "function": {
            "name": SEMANTIC_IR_TOOL_NAME,
            "description": "Submit the DASHSys V2 Semantic IR plan. The backend validates and mechanically compiles this IR.",
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "route": {"type": "string", "enum": ["DIRECT", "EVIDENCE"]},
                    "direct_answer": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                    "tasks": {"type": "array", "items": task_schema},
                    "aggregation_instruction": {"type": "string"},
                },
                "required": ["route", "direct_answer", "tasks", "aggregation_instruction"],
            },
        },
    }


def run_semantic_ir_toolcall_planner(
    *,
    client: Any,
    user_prompt: str,
    schema_context: dict[str, Any],
    endpoint_context: list[dict[str, Any]],
    repair_context: dict[str, Any] | None = None,
    fallback_to_atomic: bool = True,
) -> WeakProtocolResult:
    started = time.perf_counter()
    schema_card = build_allowed_local_schema_card(schema_context)
    api_card = build_allowed_api_context_card(endpoint_context)
    validator = SemanticIRValidator(schema_card, api_card)
    diagnostics: dict[str, Any] = _base_diagnostics()
    raw_previews: dict[str, Any] = {}

    result, call_error = _call_semantic_ir_tool(
        client,
        system_prompt=_semantic_ir_system_prompt(),
        user_prompt=_semantic_ir_user_prompt(
            user_prompt=user_prompt,
            allowed_schema_card=schema_card,
            allowed_api_card=api_card,
            repair_context=repair_context,
        ),
    )
    diagnostics["semantic_ir_provider_latency_ms"] = _elapsed_ms(started)
    raw_previews["semantic_ir_initial"] = compact_preview(result or call_error, 1200)
    if call_error:
        diagnostics["semantic_ir_toolcall_error"] = call_error
        return _fallback_or_failed(
            client=client,
            user_prompt=user_prompt,
            schema_context=schema_context,
            endpoint_context=endpoint_context,
            repair_context=repair_context,
            fallback_to_atomic=fallback_to_atomic,
            diagnostics=diagnostics,
            raw_previews=raw_previews,
            reason=call_error,
            started=started,
        )

    tool_args = _extract_semantic_ir_tool_arguments(result)
    if tool_args is None:
        legacy_payload = _extract_legacy_planner_payload(result)
        if legacy_payload is not None:
            diagnostics.update(
                {
                    "semantic_ir_toolcall_supported": bool(result.get("tool_calls")),
                    "sdk_toolcall_semantic_ir_used": False,
                    "semantic_ir_validation_passed": False,
                    "semantic_ir_validation_error_type": "legacy_content_or_tool_fallback",
                    "planner_success": True,
                    "planner_json_fallback_used": True,
                    "planner_parse_source": "legacy_planner_payload_fallback",
                    "atomic_protocol_fallback_used": False,
                    "backend_formal_compilation_used": False,
                    "backend_semantic_planning_used": False,
                    "backend_sql_api_generation_used": True,
                    "planner_provider_latency_ms": _elapsed_ms(started),
                }
            )
            return WeakProtocolResult(plan_payload=legacy_payload, diagnostics=diagnostics, raw_preview=redact_secrets(raw_previews))
        diagnostics.update(
            {
                "semantic_ir_toolcall_supported": False,
                "sdk_toolcall_semantic_ir_used": False,
                "semantic_ir_validation_passed": False,
                "semantic_ir_validation_error_type": "missing_tool_call",
            }
        )
        return _fallback_or_failed(
            client=client,
            user_prompt=user_prompt,
            schema_context=schema_context,
            endpoint_context=endpoint_context,
            repair_context=repair_context,
            fallback_to_atomic=fallback_to_atomic,
            diagnostics=diagnostics,
            raw_previews=raw_previews,
            reason="SDK model response did not include submit_semantic_ir_plan tool call.",
            started=started,
        )

    parsed_plan, validation = _parse_validate(tool_args, validator)
    diagnostics.update(
        {
            "semantic_ir_toolcall_supported": True,
            "sdk_toolcall_semantic_ir_used": True,
            "semantic_ir_validation_passed": validation.passed,
            "semantic_ir_validation_error_type": validation.error_type,
            "semantic_ir_validation_error_message": validation.error_message,
            "semantic_ir_task_count": len(parsed_plan.tasks) if parsed_plan else 0,
        }
    )
    if parsed_plan is None or not validation.passed:
        diagnostics["semantic_ir_repair_attempted"] = True
        repair_result, repair_error = _call_semantic_ir_tool(
            client,
            system_prompt=_semantic_ir_repair_system_prompt(),
            user_prompt=_semantic_ir_repair_user_prompt(
                user_prompt=user_prompt,
                previous_args=tool_args,
                validation=validation,
                allowed_schema_card=schema_card,
                allowed_api_card=api_card,
            ),
        )
        diagnostics["semantic_ir_provider_latency_ms"] = _elapsed_ms(started)
        raw_previews["semantic_ir_repair"] = compact_preview(repair_result or repair_error, 1200)
        if repair_error:
            diagnostics["semantic_ir_repair_success"] = False
            return _failed_semantic_ir_result(diagnostics, raw_previews, reason=repair_error, started=started)
        repair_args = _extract_semantic_ir_tool_arguments(repair_result)
        if repair_args is None:
            diagnostics["semantic_ir_repair_success"] = False
            return _failed_semantic_ir_result(
                diagnostics,
                raw_previews,
                reason="Semantic IR repair did not return submit_semantic_ir_plan tool call.",
                started=started,
            )
        parsed_plan, validation = _parse_validate(repair_args, validator)
        diagnostics.update(
            {
                "semantic_ir_validation_passed": validation.passed,
                "semantic_ir_repair_success": bool(parsed_plan is not None and validation.passed),
                "semantic_ir_task_count": len(parsed_plan.tasks) if parsed_plan else 0,
            }
        )
        if not parsed_plan or not validation.passed:
            diagnostics.update(
                {
                    "semantic_ir_validation_error_type": validation.error_type,
                    "semantic_ir_validation_error_message": validation.error_message,
                }
            )
            return _failed_semantic_ir_result(
                diagnostics,
                raw_previews,
                reason=validation.error_message or "Semantic IR validation failed after repair.",
                started=started,
            )

    plan_payload = compile_semantic_ir_to_plan_payload(parsed_plan, schema_card, api_card)
    diagnostics.update(
        {
            "planner_success": True,
            "semantic_ir_validation_passed": True,
            "semantic_ir_repair_success": diagnostics.get("semantic_ir_repair_success", False),
            "backend_formal_compilation_used": True,
            "backend_semantic_planning_used": False,
            "backend_sql_api_generation_used": False,
            "backend_semantic_decomposition_used": False,
            "atomic_protocol_fallback_used": False,
            "compiled_sql_count": sum(1 for item in plan_payload.get("passes", []) if item.get("sql")),
            "compiled_api_count": sum(1 for item in plan_payload.get("passes", []) if item.get("api_request")),
            "planner_parse_source": "sdk_toolcall_semantic_ir",
            "planner_provider_latency_ms": _elapsed_ms(started),
            "semantic_ir_plan_preview": compact_preview(semantic_plan_to_dict(parsed_plan), 1200),
        }
    )
    return WeakProtocolResult(plan_payload=plan_payload, diagnostics=diagnostics, raw_preview=redact_secrets(raw_previews))


def _base_diagnostics() -> dict[str, Any]:
    return {
        "v2_semantic_ir_used": True,
        "sdk_toolcall_semantic_ir_used": False,
        "semantic_ir_toolcall_supported": None,
        "semantic_ir_validation_passed": False,
        "semantic_ir_validation_error_type": None,
        "semantic_ir_validation_error_message": None,
        "semantic_ir_repair_attempted": False,
        "semantic_ir_repair_success": False,
        "backend_formal_compilation_used": False,
        "backend_semantic_planning_used": False,
        "backend_sql_api_generation_used": False,
        "backend_semantic_decomposition_used": False,
        "atomic_protocol_fallback_used": False,
        "compiled_sql_count": 0,
        "compiled_api_count": 0,
        "sql_compile_gate_failures": 0,
        "api_request_gate_failures": 0,
    }


def _call_semantic_ir_tool(client: Any, *, system_prompt: str, user_prompt: str) -> tuple[dict[str, Any], str | None]:
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
    tool_choice = {"type": "function", "function": {"name": SEMANTIC_IR_TOOL_NAME}}
    try:
        result = client.generate_messages(
            messages,
            tools=[semantic_ir_tool_schema()],
            tool_choice=tool_choice,
            parallel_tool_calls=False,
        )
    except TypeError:
        result = client.generate_messages(messages, tools=[semantic_ir_tool_schema()], tool_choice=tool_choice)
    except Exception as exc:
        return {}, str(exc)
    if not isinstance(result, dict):
        return {}, "LLM client returned non-dict response."
    if not result.get("ok", True):
        return result, str(result.get("error") or result.get("reason") or "LLM client returned failure.")
    return result, None


def _extract_semantic_ir_tool_arguments(result: dict[str, Any]) -> dict[str, Any] | None:
    for call in result.get("tool_calls") or []:
        if not isinstance(call, dict):
            continue
        name = call.get("name") or call.get("tool") or (call.get("function") or {}).get("name")
        if name != SEMANTIC_IR_TOOL_NAME:
            continue
        args = call.get("arguments")
        if isinstance(args, dict):
            return args
        raw_args = call.get("raw_arguments")
        if isinstance(raw_args, str):
            try:
                parsed = json.loads(raw_args)
            except Exception:
                return {"_raw": raw_args}
            return parsed if isinstance(parsed, dict) else {"_raw": raw_args}
    return None


def _extract_legacy_planner_payload(result: dict[str, Any]) -> dict[str, Any] | None:
    for call in result.get("tool_calls") or []:
        if not isinstance(call, dict):
            continue
        name = call.get("name") or call.get("tool") or (call.get("function") or {}).get("name")
        if name != "submit_v2_plan":
            continue
        args = call.get("arguments")
        if isinstance(args, dict):
            return args
        raw_args = call.get("raw_arguments")
        if isinstance(raw_args, str):
            return _legacy_full_plan_payload(raw_args)
    content_payload = _legacy_full_plan_payload(str(result.get("content") or ""))
    if content_payload is not None:
        return content_payload
    return None


def _parse_validate(tool_args: dict[str, Any], validator: SemanticIRValidator) -> tuple[SemanticIRPlan | None, SemanticIRValidationResult]:
    try:
        parsed_plan = parse_semantic_ir_from_json_or_line_protocol(tool_args)
    except Exception as exc:
        return None, SemanticIRValidationResult(passed=False, error_type="parse_error", error_message=str(exc))
    return parsed_plan, validator.validate(parsed_plan)


def _fallback_or_failed(
    *,
    client: Any,
    user_prompt: str,
    schema_context: dict[str, Any],
    endpoint_context: list[dict[str, Any]],
    repair_context: dict[str, Any] | None,
    fallback_to_atomic: bool,
    diagnostics: dict[str, Any],
    raw_previews: dict[str, Any],
    reason: str,
    started: float,
) -> WeakProtocolResult:
    if not fallback_to_atomic:
        return _failed_semantic_ir_result(diagnostics, raw_previews, reason=reason, started=started)
    atomic = run_atomic_weak_protocol(
        client=client,
        user_prompt=user_prompt,
        schema_context=schema_context,
        endpoint_context=endpoint_context,
        repair_context=repair_context,
    )
    merged = {
        **diagnostics,
        **atomic.diagnostics,
        "v2_semantic_ir_used": True,
        "sdk_toolcall_semantic_ir_used": False,
        "atomic_protocol_fallback_used": True,
        "semantic_ir_fallback_reason": reason,
        "backend_semantic_planning_used": False,
        "planner_parse_source": "atomic_protocol_fallback",
        "planner_provider_latency_ms": _elapsed_ms(started),
    }
    preview = {"semantic_ir": raw_previews, "atomic": atomic.raw_preview}
    return WeakProtocolResult(
        plan_payload=atomic.plan_payload,
        diagnostics=merged,
        raw_preview=redact_secrets(preview),
        parse_error=atomic.parse_error,
        backend_unavailable=atomic.backend_unavailable,
        error_message=atomic.error_message,
    )


def _failed_semantic_ir_result(
    diagnostics: dict[str, Any],
    raw_previews: dict[str, Any],
    *,
    reason: str,
    started: float,
) -> WeakProtocolResult:
    diagnostics.update(
        {
            "planner_success": False,
            "backend_formal_compilation_used": False,
            "atomic_protocol_fallback_used": False,
            "planner_parse_source": "semantic_ir_validation_error",
            "planner_provider_latency_ms": _elapsed_ms(started),
        }
    )
    return WeakProtocolResult(
        plan_payload={
            "route": "EVIDENCE_PIPELINE",
            "evidence_order": "SQL_FIRST",
            "direct_answer": None,
            "passes": [],
            "aggregation_instruction": "",
            "reason": f"semantic_ir_validation_error: {reason}",
        },
        diagnostics=diagnostics,
        raw_preview=redact_secrets(raw_previews),
        parse_error=True,
        backend_unavailable=False,
        error_message=reason,
    )


def _semantic_ir_system_prompt() -> str:
    return (
        "You are the single Unified LLM Planner facade for DASHSys V2, and SDK toolcall Semantic IR is the primary internal planning contract. "
        "Use the submit_semantic_ir_plan SDK tool. Do not answer in plain text unless tool calls are unavailable. "
        "You own DIRECT vs EVIDENCE routing, task semantics, source, operation, selected table/endpoint IDs, fields, filters, values, dependencies, and aggregation instruction. "
        "Use DIRECT only for pure concept, pure meta-language, or out-of-domain prompts needing no local or live evidence. "
        "Use EVIDENCE for user-specific, local snapshot, live/current/platform/API, list/count/status/date/lookup/compare, mixed concept plus data, or ambiguous data-like prompts. "
        "Choose table and field names only from AllowedLocalSchemaCard and endpoints only from AllowedAPIContextCard. "
        "The backend will only validate existence and mechanically compile the IR; it will not choose replacements."
    )


def _semantic_ir_user_prompt(
    *,
    user_prompt: str,
    allowed_schema_card: list[dict[str, Any]],
    allowed_api_card: list[dict[str, Any]],
    repair_context: dict[str, Any] | None,
) -> str:
    payload = {
        "task": "SUBMIT_DASHSYS_V2_SEMANTIC_IR",
        "user_prompt": user_prompt,
        "AllowedLocalSchemaCard": allowed_schema_card,
        "AllowedAPIContextCard": allowed_api_card,
        "rules": [
            "Return exactly one submit_semantic_ir_plan tool call.",
            "Do not put the plan in message content.",
            "Do not invent table names, column names, or endpoint IDs.",
            "Do not ask the backend to infer missing filters or fields.",
            "For DIRECT route, tasks must be empty and direct_answer must be concise.",
            "For EVIDENCE route, tasks must contain the LLM-owned evidence tasks.",
            "Prefer LOCAL_QUERY for user-specific local or ambiguous data-like prompts unless the prompt explicitly asks for live/current/platform/API evidence.",
            "Hard source contract: if the prompt has no live/current/platform/API cue and asks what records exist, what records the user has, a count, date, status, or list, LIVE_QUERY is the wrong source; choose LOCAL_QUERY.",
            "Phrases like 'do I have', 'my', 'show/list/give me records', and bare entity lookups without live/current/platform/API cues are LOCAL_SNAPSHOT requests.",
            "Do not choose LIVE_QUERY merely because a live endpoint exists for the object family.",
            "Use LIVE_QUERY only when the prompt explicitly asks for live/current/platform/API state or when comparing local/live evidence.",
            "For mixed concept plus data prompts without live/current/platform/API cues, include a CONCEPT task and a LOCAL_QUERY data task; do not use API as the primary data source.",
            "For any how many/count/number of/total prompt, use operation COUNT and local_query.count=true; do not list rows and count the displayed limit.",
            "For local snapshot counts, use LOCAL_QUERY with operation COUNT.",
            "For date or published/created/updated lookup prompts without live/current/platform/API cues, use LOCAL_QUERY with DATE or LOOKUP when an allowed local table has a relevant date/timestamp field; do not make API a prerequisite.",
            "For published/date prompts, select all relevant local timestamp candidates available in the allowed table, such as CREATEDTIME, UPDATEDTIME, STARTDATE, LASTDEPLOYEDTIME, STOPPEDTIME, or FINISHEDTIME, instead of selecting only one nullable timestamp.",
            "Do not make a local lookup depend on a live API task unless the local filter literally needs an ID returned by the live task.",
            "For lifecycle words such as active/inactive/status/state, choose filters only on allowed local fields and values you can justify from schema context; if exact enum values are unknown, prefer a broader LOCAL_QUERY over an invented literal enum like INACTIVE.",
            "For compare local/live prompts, include both LOCAL_QUERY and LIVE_QUERY tasks when both are available, then aggregate.",
        ],
        "repair_context": redact_secrets(repair_context) if repair_context else None,
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _semantic_ir_repair_system_prompt() -> str:
    return (
        "Your previous Semantic IR tool call failed shape or existence validation. "
        "Submit exactly one corrected submit_semantic_ir_plan tool call. "
        "Do not use message content for the plan. Do not let malformed output fail open into DIRECT. "
        "Do not ask the backend to choose replacements; choose valid IDs from the allowed cards yourself."
    )


def _semantic_ir_repair_user_prompt(
    *,
    user_prompt: str,
    previous_args: dict[str, Any],
    validation: SemanticIRValidationResult,
    allowed_schema_card: list[dict[str, Any]],
    allowed_api_card: list[dict[str, Any]],
) -> str:
    allowed_tables = [row.get("table") for row in allowed_schema_card]
    allowed_endpoints = [row.get("endpoint_id") for row in allowed_api_card]
    payload = {
        "task": "REPAIR_DASHSYS_V2_SEMANTIC_IR",
        "user_prompt": user_prompt,
        "previous_tool_arguments": compact_preview(previous_args, 1600),
        "validation_error": validation.to_dict(),
        "allowed_tables": allowed_tables,
        "allowed_schema_card": allowed_schema_card,
        "allowed_endpoints": allowed_endpoints,
        "allowed_api_card": allowed_api_card,
        "rules": [
            "Repair by submitting the SDK tool call again.",
            "Use only exact table, field, and endpoint IDs from allowed cards.",
            "Do not output narrative text.",
        ],
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)
