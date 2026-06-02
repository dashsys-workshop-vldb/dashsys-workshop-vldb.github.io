from __future__ import annotations

import json
import time
from typing import Any

from .trajectory import compact_preview, redact_secrets
from .raw_sql_safety_gate import RawSQLSafetyGate
from .v2_atomic_weak_protocol import run_atomic_weak_protocol
from .v2_raw_sql_fallback import RawSQLFallbackResult, run_raw_sql_fallback_planner
from .v2_semantic_ir import SemanticIRPlan, parse_semantic_ir_from_json_or_line_protocol, semantic_plan_to_dict
from .v2_semantic_ir_compiler import compile_semantic_ir_to_plan_payload
from .v2_semantic_ir_context import build_allowed_api_context_card, build_allowed_local_schema_card
from .v2_semantic_ir_support import IRSupportResult, check_semantic_ir_support
from .v2_semantic_ir_validator import SemanticIRValidationResult, SemanticIRValidator
from .v2_weak_model_protocol import WeakProtocolResult, _elapsed_ms
from .v2_weak_model_protocol import _legacy_full_plan_payload


SEMANTIC_IR_TOOL_NAME = "submit_semantic_ir_plan"


def semantic_ir_tool_schema() -> dict[str, Any]:
    result_contract_schema: dict[str, Any] = {
        "anyOf": [
            {"type": "null"},
            {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "source": {"type": "string", "enum": ["NONE", "LOCAL_SNAPSHOT", "LIVE_API", "BOTH"]},
                    "object": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                    "entity": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                    "operation": {"type": "string", "enum": ["EXPLAIN", "LIST", "COUNT", "LOOKUP", "STATUS", "DATE", "COMPARE"]},
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
                    "scope": {"type": "string", "enum": ["concept", "local", "live", "both"]},
                    "freshness": {"type": "string", "enum": ["same_run"]},
                },
                "required": ["source", "object", "entity", "operation", "fields", "filters", "scope", "freshness"],
            },
        ]
    }
    task_schema: dict[str, Any] = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "task_id": {"type": "string"},
            "kind": {"type": "string", "enum": ["CONCEPT", "LOCAL_QUERY", "LIVE_QUERY", "LOCAL_AND_LIVE", "AGGREGATE", "CACHE_ALIAS"]},
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
            "reuse_result_from": {"anyOf": [{"type": "string"}, {"type": "null"}]},
            "semantic_cache_key": {"anyOf": [{"type": "string"}, {"type": "null"}]},
            "result_contract": result_contract_schema,
            "requires_raw_sql_fallback": {"type": "boolean"},
            "raw_sql_reason": {"anyOf": [{"type": "string"}, {"type": "null"}]},
            "unsupported_features": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": ["JOIN", "GROUP_BY", "HAVING", "WINDOW", "UNION", "CTE", "WITH", "NESTED_SUBQUERY", "COMPUTED_COLUMN", "VENDOR_FUNCTION"],
                },
            },
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

    validation_started = time.perf_counter()
    parsed_plan, validation = _parse_validate(tool_args, validator)
    diagnostics["semantic_ir_validation_latency_ms"] = _elapsed_ms(validation_started)
    diagnostics.update(
        {
            "semantic_ir_toolcall_supported": True,
            "sdk_toolcall_semantic_ir_used": True,
            "semantic_ir_validation_passed": validation.passed,
            "semantic_ir_validation_error_type": validation.error_type,
            "semantic_ir_validation_error_message": validation.error_message,
            "semantic_ir_task_count": len(parsed_plan.tasks) if parsed_plan else 0,
            "semantic_alias_validation_used": validation.semantic_alias_validation_used,
            "semantic_alias_validation_passed": validation.semantic_alias_validation_passed,
            "semantic_alias_count": validation.semantic_alias_count,
            "semantic_alias_error_type": validation.error_type if validation.error_type == "invalid_semantic_alias" else None,
        }
    )
    if parsed_plan is None or not validation.passed:
        diagnostics["semantic_ir_repair_attempted"] = True
        if validation.error_type == "invalid_semantic_alias":
            diagnostics["semantic_alias_repair_attempted"] = True
        repair_started = time.perf_counter()
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
        diagnostics["semantic_ir_repair_latency_ms"] = _elapsed_ms(repair_started)
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
        validation_started = time.perf_counter()
        parsed_plan, validation = _parse_validate(repair_args, validator)
        diagnostics["semantic_ir_validation_latency_ms"] = diagnostics.get("semantic_ir_validation_latency_ms", 0) + _elapsed_ms(validation_started)
        diagnostics.update(
            {
                "semantic_ir_validation_passed": validation.passed,
                "semantic_ir_repair_success": bool(parsed_plan is not None and validation.passed),
                "semantic_ir_task_count": len(parsed_plan.tasks) if parsed_plan else 0,
                "semantic_alias_validation_used": validation.semantic_alias_validation_used,
                "semantic_alias_validation_passed": validation.semantic_alias_validation_passed,
                "semantic_alias_count": validation.semantic_alias_count,
                "semantic_alias_error_type": validation.error_type if validation.error_type == "invalid_semantic_alias" else diagnostics.get("semantic_alias_error_type"),
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

    support_started = time.perf_counter()
    support_result = check_semantic_ir_support(parsed_plan, schema_card, api_card)
    diagnostics["semantic_ir_support_check_latency_ms"] = _elapsed_ms(support_started)
    _record_support_result(diagnostics, support_result)
    if not support_result.supported:
        diagnostics["semantic_ir_support_repair_attempted"] = True
        support_repair_started = time.perf_counter()
        support_repair_result, support_repair_error = _call_semantic_ir_tool(
            client,
            system_prompt=_semantic_ir_support_repair_system_prompt(),
            user_prompt=_semantic_ir_support_repair_user_prompt(
                user_prompt=user_prompt,
                previous_args=semantic_plan_to_dict(parsed_plan),
                support_result=support_result,
                allowed_schema_card=schema_card,
                allowed_api_card=api_card,
            ),
        )
        diagnostics["semantic_ir_provider_latency_ms"] = _elapsed_ms(started)
        diagnostics["semantic_ir_support_repair_latency_ms"] = _elapsed_ms(support_repair_started)
        raw_previews["semantic_ir_support_repair"] = compact_preview(support_repair_result or support_repair_error, 1200)
        if support_repair_error:
            diagnostics["semantic_ir_support_repair_success"] = False
            diagnostics["semantic_ir_support_repair_error_message"] = support_repair_error
            return _failed_semantic_ir_result(diagnostics, raw_previews, reason=support_repair_error, started=started)
        support_repair_args = _extract_semantic_ir_tool_arguments(support_repair_result)
        if support_repair_args is None:
            diagnostics["semantic_ir_support_repair_success"] = False
            diagnostics["semantic_ir_support_repair_error_type"] = "missing_tool_call"
            return _failed_semantic_ir_result(
                diagnostics,
                raw_previews,
                reason="Semantic IR support repair did not return submit_semantic_ir_plan tool call.",
                started=started,
            )
        validation_started = time.perf_counter()
        repaired_plan, repaired_validation = _parse_validate(support_repair_args, validator)
        diagnostics["semantic_ir_validation_latency_ms"] = diagnostics.get("semantic_ir_validation_latency_ms", 0) + _elapsed_ms(validation_started)
        diagnostics.update(
            {
                "semantic_ir_validation_passed": repaired_validation.passed,
                "semantic_ir_validation_error_type": repaired_validation.error_type,
                "semantic_ir_validation_error_message": repaired_validation.error_message,
                "semantic_ir_task_count": len(repaired_plan.tasks) if repaired_plan else 0,
            }
        )
        if repaired_plan is None or not repaired_validation.passed:
            diagnostics["semantic_ir_support_repair_success"] = False
            diagnostics["semantic_ir_support_repair_error_type"] = repaired_validation.error_type
            diagnostics["semantic_ir_support_repair_error_message"] = repaired_validation.error_message
            return _failed_semantic_ir_result(
                diagnostics,
                raw_previews,
                reason=repaired_validation.error_message or "Semantic IR support repair failed validation.",
                started=started,
            )
        support_started = time.perf_counter()
        repaired_support = check_semantic_ir_support(repaired_plan, schema_card, api_card)
        diagnostics["semantic_ir_support_check_latency_ms"] = diagnostics.get("semantic_ir_support_check_latency_ms", 0) + _elapsed_ms(support_started)
        if repaired_support.supported:
            parsed_plan = repaired_plan
            support_result = repaired_support
            diagnostics["semantic_ir_support_repair_success"] = True
            _record_support_result(diagnostics, repaired_support)
        else:
            diagnostics["semantic_ir_support_repair_success"] = False
            _record_support_result(diagnostics, repaired_support)
            if repaired_support.recommended_action != "RAW_SQL_FALLBACK":
                return _failed_semantic_ir_result(
                    diagnostics,
                    raw_previews,
                    reason=repaired_support.unsupported_reason or "Semantic IR remains unsupported after repair.",
                    started=started,
                )
            raw_fallback = run_raw_sql_fallback_planner(
                client=client,
                user_prompt=user_prompt,
                semantic_plan=semantic_plan_to_dict(repaired_plan),
                support_result=repaired_support,
                allowed_schema_card=schema_card,
                safety_gate=RawSQLSafetyGate(),
            )
            diagnostics["raw_sql_fallback_latency_ms"] = raw_fallback.latency_ms
            raw_previews["raw_sql_fallback"] = compact_preview(raw_fallback.raw_preview, 1200)
            _record_raw_sql_fallback_result(diagnostics, raw_fallback)
            if not raw_fallback.ok or not raw_fallback.sql:
                return _failed_semantic_ir_result(
                    diagnostics,
                    raw_previews,
                    reason=raw_fallback.rejected_reason or "Raw SQL fallback was rejected.",
                    started=started,
                )
            compiler_started = time.perf_counter()
            plan_payload = _raw_sql_fallback_plan_payload(repaired_plan, raw_fallback)
            diagnostics["compiler_latency_ms"] = _elapsed_ms(compiler_started)
            diagnostics.update(
                {
                    "planner_success": True,
                    "backend_formal_compilation_used": True,
                    "backend_semantic_planning_used": False,
                    "backend_sql_api_generation_used": False,
                    "backend_semantic_decomposition_used": False,
                    "atomic_protocol_fallback_used": False,
                    "compiled_sql_count": 1,
                    "compiled_api_count": 0,
                    "planner_parse_source": "sdk_toolcall_semantic_ir_raw_sql_fallback",
                    "planner_provider_latency_ms": _elapsed_ms(started),
                    "semantic_ir_plan_preview": compact_preview(semantic_plan_to_dict(repaired_plan), 1200),
                }
            )
            return WeakProtocolResult(plan_payload=plan_payload, diagnostics=diagnostics, raw_preview=redact_secrets(raw_previews))

    compiler_started = time.perf_counter()
    plan_payload = compile_semantic_ir_to_plan_payload(parsed_plan, schema_card, api_card)
    diagnostics["compiler_latency_ms"] = _elapsed_ms(compiler_started)
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
            "compiled_alias_count": sum(1 for item in plan_payload.get("passes", []) if str(item.get("path") or "").upper() == "CACHE_ALIAS"),
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
        "semantic_ir_validation_latency_ms": 0,
        "semantic_ir_repair_latency_ms": 0,
        "semantic_ir_support_check_latency_ms": 0,
        "semantic_ir_support_repair_latency_ms": 0,
        "raw_sql_fallback_latency_ms": 0,
        "compiler_latency_ms": 0,
        "semantic_ir_support_checked": False,
        "semantic_ir_supported": None,
        "semantic_ir_unsupported_reason": None,
        "semantic_ir_unsupported_features": [],
        "semantic_ir_support_repair_attempted": False,
        "semantic_ir_support_repair_success": False,
        "semantic_ir_support_repair_error_type": None,
        "semantic_ir_support_repair_error_message": None,
        "raw_sql_fallback_considered": False,
        "raw_sql_fallback_used": False,
        "raw_sql_fallback_success": False,
        "raw_sql_fallback_repair_attempted": False,
        "raw_sql_fallback_repair_success": False,
        "raw_sql_fallback_gate_error_type": None,
        "raw_sql_fallback_rejected_reason": None,
        "raw_sql_fallback_task_id": None,
        "raw_sql_fallback_reason": None,
        "backend_generated_sql": False,
        "semantic_alias_validation_used": False,
        "semantic_alias_validation_passed": None,
        "semantic_alias_count": 0,
        "semantic_alias_repair_attempted": False,
        "semantic_alias_error_type": None,
        "compiled_alias_count": 0,
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


def _record_support_result(diagnostics: dict[str, Any], support_result: IRSupportResult) -> None:
    diagnostics.update(
        {
            "semantic_ir_support_checked": True,
            "semantic_ir_supported": support_result.supported,
            "semantic_ir_unsupported_reason": support_result.unsupported_reason,
            "semantic_ir_unsupported_features": list(support_result.unsupported_features),
            "semantic_ir_unsupported_task_id": support_result.task_id,
            "semantic_ir_unsupported_operation": support_result.operation,
            "semantic_ir_support_recommended_action": support_result.recommended_action,
        }
    )


def _record_raw_sql_fallback_result(diagnostics: dict[str, Any], raw_fallback: RawSQLFallbackResult) -> None:
    gate = raw_fallback.safety_gate
    diagnostics.update(
        {
            "raw_sql_fallback_considered": True,
            "raw_sql_fallback_used": bool(raw_fallback.ok),
            "raw_sql_fallback_success": bool(raw_fallback.ok),
            "raw_sql_fallback_repair_attempted": raw_fallback.repair_attempted,
            "raw_sql_fallback_repair_success": raw_fallback.repair_success,
            "raw_sql_fallback_gate_error_type": gate.error_type if gate else None,
            "raw_sql_fallback_rejected_reason": raw_fallback.rejected_reason,
            "raw_sql_fallback_task_id": raw_fallback.task_id,
            "raw_sql_fallback_reason": raw_fallback.reason,
            "backend_generated_sql": raw_fallback.backend_generated_sql,
        }
    )


def _raw_sql_fallback_plan_payload(plan: SemanticIRPlan, raw_fallback: RawSQLFallbackResult) -> dict[str, Any]:
    task = _semantic_task_by_id(plan, raw_fallback.task_id)
    pass_id = raw_fallback.task_id or (task.task_id if task else "raw_sql_fallback")
    description = task.description if task and task.description else (raw_fallback.reason or "LLM-owned raw SQL fallback.")
    return {
        "route": "EVIDENCE_PIPELINE",
        "evidence_order": "SQL_FIRST",
        "direct_answer": None,
        "passes": [
            {
                "pass_id": pass_id,
                "subtask": description,
                "path": "SQL",
                "can_run_parallel": not bool(task.depends_on) if task else True,
                "depends_on": list(task.depends_on) if task else [],
                "evidence_order": "SQL_FIRST",
                "sql": {"query": raw_fallback.sql, "params": list(raw_fallback.params or [])},
                "api_request": None,
                "expected_result": description,
                "optional": not bool(task.required) if task else False,
                "fallback": False,
                "raw_sql_fallback_used": True,
                "raw_sql_fallback_reason": raw_fallback.reason,
                "raw_sql_fallback_task_id": raw_fallback.task_id,
            }
        ],
        "aggregation_instruction": plan.aggregation_instruction,
        "reason": "LLM-owned raw SQL fallback for valid-but-unsupported Semantic IR.",
    }


def _semantic_task_by_id(plan: SemanticIRPlan, task_id: str | None):
    for task in plan.tasks or []:
        if task.task_id == str(task_id or ""):
            return task
    return None


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
            "Prefer supported Semantic IR operations whenever they can express the requested evidence.",
            "Use LIST/COUNT/LOOKUP/STATUS/DATE LocalQueryIR operations for simple local snapshot data requests.",
            "raw SQL fallback is an escape hatch only when a required LOCAL_SNAPSHOT task cannot be represented by supported Semantic IR.",
            "Do not ask the backend to write SQL, infer SQL, choose SQL tables, choose SQL fields, or repair SQL for you.",
            "Do not request unsupported JOIN/GROUP/window SQL in Semantic IR unless the user request truly requires it and supported IR cannot represent it.",
            "If unsupported local SQL structure is truly required, set requires_raw_sql_fallback=true, raw_sql_reason, and unsupported_features on that LOCAL_SNAPSHOT task.",
            "Prefer LOCAL_QUERY for user-specific local or ambiguous data-like prompts unless the prompt explicitly asks for live/current/platform/API evidence.",
            "Hard source contract: if the prompt has no live/current/platform/API cue and asks what records exist, what records the user has, a count, date, status, or list, LIVE_QUERY is the wrong source; choose LOCAL_QUERY.",
            "Phrases like 'do I have', 'my', 'show/list/give me records', and bare entity lookups without live/current/platform/API cues are LOCAL_SNAPSHOT requests.",
            "Do not choose LIVE_QUERY merely because a live endpoint exists for the object family.",
            "Use LIVE_QUERY only when the prompt explicitly asks for live/current/platform/API state or when comparing local/live evidence.",
            "For mixed concept plus data prompts without live/current/platform/API cues, include a CONCEPT task and a LOCAL_QUERY data task; do not use API as the primary data source.",
            "For any how many/count/number of/total prompt, use operation COUNT and local_query.count=true; do not list rows and count the displayed limit.",
            "For local snapshot counts, use LOCAL_QUERY with operation COUNT.",
            "Do not represent a requested COUNT as an AGGREGATE task over a sampled LIST task; sampled rows are not a count.",
            "If a COUNT answer is requested for LOCAL_SNAPSHOT, the required evidence task itself must be kind LOCAL_QUERY, source LOCAL_SNAPSHOT, operation COUNT, and local_query.count=true.",
            "For date or published/created/updated lookup prompts without live/current/platform/API cues, use LOCAL_QUERY with DATE or LOOKUP when an allowed local table has a relevant date/timestamp field; do not make API a prerequisite.",
            "For published/date prompts, select all relevant local timestamp candidates available in the allowed table, such as CREATEDTIME, UPDATEDTIME, STARTDATE, LASTDEPLOYEDTIME, STOPPEDTIME, or FINISHEDTIME, instead of selecting only one nullable timestamp.",
            "Do not make a local lookup depend on a live API task unless the local filter literally needs an ID returned by the live task.",
            "For lifecycle words such as active/inactive/status/state, choose filters only on allowed local fields and values you can justify from schema context; if exact enum values are unknown, prefer a broader LOCAL_QUERY over an invented literal enum like INACTIVE.",
            "For compare local/live prompts, include both LOCAL_QUERY and LIVE_QUERY tasks when both are available, then aggregate.",
            "If two tasks require exactly the same runtime evidence, you may declare a CACHE_ALIAS task instead of repeating SQL/API.",
            "LLM owns semantic equivalence; the backend will not infer aliases from natural language, task descriptions, SQL, or API similarity.",
            "A CACHE_ALIAS must set reuse_result_from to the producer task ID, include depends_on for that producer, contain no local_query/api_query, and include an identical result_contract.",
            "Only alias when source, scope, operation, object, entity, fields, filters, freshness, and answer contract are identical.",
            "If uncertain, do not alias.",
            "Do not alias local and live evidence.",
            "Do not alias status and date evidence.",
            "Do not alias count and list evidence.",
            "Do not alias concept explanations to runtime evidence.",
            "Do not alias different entities, different sources, different scopes, different fields, or different filters.",
            "Alias reuse is same-run only.",
        ],
        "semantic_alias_examples": [
            {
                "case": "repeated_local_status",
                "shape": "t1 LOCAL_QUERY gets local Birthday Message status; t2 CACHE_ALIAS reuses t1 with identical result_contract.",
            },
            {
                "case": "local_live_compare_negative",
                "shape": "A local status task and a live status task must not be aliased because source/scope differ.",
            },
            {
                "case": "status_date_negative",
                "shape": "A local status task and a published-date task must not be aliased because operation/fields differ.",
            },
            {
                "case": "count_list_negative",
                "shape": "A schema count task and schema list task must not be aliased because COUNT and LIST contracts differ.",
            },
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


def _semantic_ir_support_repair_system_prompt() -> str:
    return (
        "Your previous Semantic IR was valid but used structures the backend compiler does not support. "
        "Submit exactly one corrected submit_semantic_ir_plan tool call. "
        "Keep the same user intent. Prefer supported LIST/COUNT/LOOKUP/STATUS/DATE LocalQueryIR/APIQueryIR if it can express the evidence. "
        "Only keep requires_raw_sql_fallback=true when the local snapshot task truly requires unsupported SQL structure. "
        "Do not ask the backend to write SQL, choose fields, add filters, or repair your plan."
    )


def _semantic_ir_support_repair_user_prompt(
    *,
    user_prompt: str,
    previous_args: dict[str, Any],
    support_result: IRSupportResult,
    allowed_schema_card: list[dict[str, Any]],
    allowed_api_card: list[dict[str, Any]],
) -> str:
    payload = {
        "task": "REPAIR_UNSUPPORTED_DASHSYS_V2_SEMANTIC_IR",
        "user_prompt": user_prompt,
        "previous_tool_arguments": compact_preview(previous_args, 1600),
        "unsupported_ir": support_result.to_dict(),
        "allowed_schema_card": allowed_schema_card,
        "allowed_api_card": allowed_api_card,
        "rules": [
            "First try to express the same evidence request using supported Semantic IR.",
            "Supported local operations are LIST, COUNT, LOOKUP, STATUS, and DATE with simple filters.",
            "Do not choose a different user intent.",
            "Do not choose replacement tables, fields, filters, or endpoints unless they are your LLM-owned corrected plan and appear in the allowed cards.",
            "If supported Semantic IR cannot represent the required local structure, keep the unsupported local task and explicitly set requires_raw_sql_fallback=true, raw_sql_reason, and unsupported_features.",
            "Never use raw SQL fallback for LIVE_API or API tasks.",
        ],
    }
    return json.dumps(redact_secrets(payload), ensure_ascii=False, sort_keys=True)
