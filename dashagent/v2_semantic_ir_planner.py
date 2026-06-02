from __future__ import annotations

import json
import os
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
DEFAULT_SEMANTIC_IR_PLANNER_CHAR_BUDGET = 24000
_SCHEMA_CARD_TARGET_SHARE = 0.58
_API_CARD_TARGET_SHARE = 0.42


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


def _configured_semantic_ir_planner_char_budget(default: int = DEFAULT_SEMANTIC_IR_PLANNER_CHAR_BUDGET) -> int:
    raw = os.getenv("DASHAGENT_SEMANTIC_IR_PLANNER_CHAR_BUDGET")
    if not raw:
        return int(default)
    try:
        value = int(raw)
    except Exception:
        return int(default)
    return value if value >= 12000 else int(default)


def semantic_ir_prompt_context_diagnostics(
    *,
    user_prompt: str,
    schema_context: dict[str, Any],
    endpoint_context: list[dict[str, Any]],
    repair_context: dict[str, Any] | None = None,
    max_total_chars: int | None = None,
) -> dict[str, Any]:
    """Return pre-call Semantic IR prompt-size diagnostics without invoking the LLM."""
    _, _, diagnostics = _build_semantic_ir_prompt_context(
        schema_context,
        endpoint_context,
        user_prompt=user_prompt,
        repair_context=repair_context,
        max_total_chars=max_total_chars,
    )
    return diagnostics


def _build_semantic_ir_prompt_context(
    schema_context: dict[str, Any],
    endpoint_context: list[dict[str, Any]],
    *,
    user_prompt: str = "",
    repair_context: dict[str, Any] | None = None,
    max_total_chars: int | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Build compact prompt cards mechanically; does not choose route, source, tables, fields, or endpoints."""
    budget = int(max_total_chars or _configured_semantic_ir_planner_char_budget())
    original_schema_card = build_allowed_local_schema_card(schema_context)
    original_api_card = build_allowed_api_context_card(endpoint_context)
    original_schema_chars = _json_char_count(original_schema_card)
    original_api_chars = _json_char_count(original_api_card)

    schema_budget, api_budget = _card_budgets_for_total(budget)
    schema_card, schema_diag = _compact_schema_card(original_schema_card, schema_budget)
    api_card, api_diag = _compact_api_card(original_api_card, api_budget)

    total_chars = _semantic_ir_total_prompt_chars(
        user_prompt=user_prompt,
        allowed_schema_card=schema_card,
        allowed_api_card=api_card,
        repair_context=repair_context,
    )
    if total_chars > budget:
        schema_card, schema_diag = _compact_schema_card(original_schema_card, max(5000, int(schema_budget * 0.76)))
        api_card, api_diag = _compact_api_card(original_api_card, max(3500, int(api_budget * 0.72)))
        total_chars = _semantic_ir_total_prompt_chars(
            user_prompt=user_prompt,
            allowed_schema_card=schema_card,
            allowed_api_card=api_card,
            repair_context=repair_context,
        )
    if total_chars > budget:
        schema_card, schema_diag = _compact_schema_card(original_schema_card, max(3800, int(schema_budget * 0.58)), aggressive=True)
        api_card, api_diag = _compact_api_card(original_api_card, max(2600, int(api_budget * 0.52)), aggressive=True)
        total_chars = _semantic_ir_total_prompt_chars(
            user_prompt=user_prompt,
            allowed_schema_card=schema_card,
            allowed_api_card=api_card,
            repair_context=repair_context,
        )
    if total_chars > budget:
        schema_card, schema_diag = _ultra_compact_schema_card(original_schema_card)
        api_card, api_diag = _ultra_compact_api_card(original_api_card)
        total_chars = _semantic_ir_total_prompt_chars(
            user_prompt=user_prompt,
            allowed_schema_card=schema_card,
            allowed_api_card=api_card,
            repair_context=repair_context,
        )

    final_schema_chars = _json_char_count(schema_card)
    final_api_chars = _json_char_count(api_card)
    diagnostics = {
        "semantic_ir_planner_char_budget": budget,
        "semantic_ir_context_truncated": bool(
            schema_diag.get("truncated")
            or api_diag.get("truncated")
            or final_schema_chars < original_schema_chars
            or final_api_chars < original_api_chars
        ),
        "semantic_ir_prompt_total_chars": total_chars,
        "semantic_ir_prompt_user_chars": len(
            _semantic_ir_user_prompt(
                user_prompt=user_prompt,
                allowed_schema_card=schema_card,
                allowed_api_card=api_card,
                repair_context=repair_context,
            )
        ),
        "semantic_ir_prompt_system_chars": len(_semantic_ir_system_prompt()),
        "semantic_ir_tool_schema_chars": len(json.dumps(semantic_ir_tool_schema(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))),
        "schema_card_original_row_count": len(original_schema_card),
        "schema_card_row_count": len(schema_card),
        "api_card_original_row_count": len(original_api_card),
        "api_card_row_count": len(api_card),
        "schema_card_original_char_count": original_schema_chars,
        "schema_card_final_char_count": final_schema_chars,
        "api_card_original_char_count": original_api_chars,
        "api_card_final_char_count": final_api_chars,
        "schema_card_columns_truncated": bool(schema_diag.get("columns_truncated")),
        "api_card_detail_truncated": bool(api_diag.get("detail_truncated")),
        "semantic_ir_context_truncated_sections": [
            section
            for section, flag in [
                ("schema_card", bool(schema_diag.get("truncated"))),
                ("api_card", bool(api_diag.get("truncated"))),
            ]
            if flag
        ],
    }
    return schema_card, api_card, diagnostics


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
    schema_card, api_card, context_diagnostics = _build_semantic_ir_prompt_context(
        schema_context,
        endpoint_context,
        user_prompt=user_prompt,
        repair_context=repair_context,
    )
    validator = SemanticIRValidator(schema_card, api_card)
    diagnostics: dict[str, Any] = _base_diagnostics()
    diagnostics.update(context_diagnostics)
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
        diagnostics["semantic_ir_repair_attempted"] = True
        repair_started = time.perf_counter()
        repair_result, repair_error = _call_semantic_ir_tool(
            client,
            system_prompt=_semantic_ir_repair_system_prompt(),
            user_prompt=_semantic_ir_missing_toolcall_retry_user_prompt(
                user_prompt=user_prompt,
                previous_result=result,
                allowed_schema_card=schema_card,
                allowed_api_card=api_card,
            ),
        )
        diagnostics["semantic_ir_provider_latency_ms"] = _elapsed_ms(started)
        diagnostics["semantic_ir_repair_latency_ms"] = _elapsed_ms(repair_started)
        raw_previews["semantic_ir_missing_toolcall_retry"] = compact_preview(repair_result or repair_error, 1200)
        if repair_error:
            diagnostics.update(
                {
                    "semantic_ir_toolcall_supported": False,
                    "sdk_toolcall_semantic_ir_used": False,
                    "semantic_ir_validation_passed": False,
                    "semantic_ir_validation_error_type": "missing_tool_call",
                    "semantic_ir_repair_success": False,
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
                reason=repair_error,
                started=started,
            )
        retry_args = _extract_semantic_ir_tool_arguments(repair_result)
        if retry_args is None:
            diagnostics.update(
                {
                    "semantic_ir_toolcall_supported": False,
                    "sdk_toolcall_semantic_ir_used": False,
                    "semantic_ir_validation_passed": False,
                    "semantic_ir_validation_error_type": "missing_tool_call",
                    "semantic_ir_repair_success": False,
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
                reason="Semantic IR retry did not return submit_semantic_ir_plan tool call.",
                started=started,
            )
        tool_args = retry_args

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
    if diagnostics.get("semantic_ir_repair_attempted") and validation.passed:
        diagnostics["semantic_ir_repair_success"] = True
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


def _card_budgets_for_total(total_budget: int) -> tuple[int, int]:
    tool_chars = len(json.dumps(semantic_ir_tool_schema(), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    fixed_payload_chars = _semantic_ir_total_prompt_chars(user_prompt="", allowed_schema_card=[], allowed_api_card=[], repair_context=None)
    remaining = max(7000, int(total_budget) - tool_chars - fixed_payload_chars)
    return max(3800, int(remaining * _SCHEMA_CARD_TARGET_SHARE)), max(2600, int(remaining * _API_CARD_TARGET_SHARE))


def _compact_schema_card(rows: list[dict[str, Any]], target_chars: int, *, aggressive: bool = False) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    max_columns_steps = [64, 48, 36, 28, 20, 14] if not aggressive else [32, 24, 18, 12, 8, 5]
    max_hint_items = 10 if not aggressive else 4
    best = [_compact_schema_row(row, max_columns=max_columns_steps[0], max_hint_items=max_hint_items) for row in rows]
    columns_truncated = any(len(best_row.get("columns", [])) < len((row.get("columns") or [])) for row, best_row in zip(rows, best))
    for max_columns in max_columns_steps:
        candidate = [_compact_schema_row(row, max_columns=max_columns, max_hint_items=max_hint_items) for row in rows]
        best = candidate
        columns_truncated = columns_truncated or any(
            len(candidate_row.get("columns", [])) < len((row.get("columns") or [])) for row, candidate_row in zip(rows, candidate)
        )
        if _json_char_count(candidate) <= target_chars:
            break
    final_chars = _json_char_count(best)
    return best, {"truncated": final_chars < _json_char_count(rows), "columns_truncated": columns_truncated, "char_count": final_chars}


def _compact_schema_row(row: dict[str, Any], *, max_columns: int, max_hint_items: int) -> dict[str, Any]:
    columns = [str(item) for item in row.get("columns", []) if str(item)]
    field_hints = row.get("field_hints") if isinstance(row.get("field_hints"), dict) else {}
    priority_columns = _schema_priority_columns(columns, field_hints)
    if len(columns) > max_columns:
        kept: list[str] = []
        for column in [*priority_columns, *columns]:
            if column in kept:
                continue
            kept.append(column)
            if len(kept) >= max_columns:
                break
        columns = kept
    compact_hints: dict[str, list[str]] = {}
    for key in ["id_fields", "primary_name_fields", "label_fields", "entity_lookup_fields", "status_fields", "date_fields", "count_fields"]:
        values = field_hints.get(key)
        if not isinstance(values, list):
            continue
        compact_values = [str(value) for value in values[:max_hint_items] if str(value)]
        if compact_values:
            compact_hints[str(key)] = compact_values
    return {
        "table": row.get("table"),
        "columns": columns,
        "table_role_hints": [str(value) for value in (row.get("table_role_hints") or [])[: min(max_hint_items, 3)]],
        "field_hints": compact_hints,
    }


def _schema_priority_columns(columns: list[str], field_hints: dict[str, Any]) -> list[str]:
    priority: list[str] = []
    for key in ["id_fields", "primary_name_fields", "entity_lookup_fields", "status_fields", "date_fields", "count_fields", "label_fields"]:
        values = field_hints.get(key) if isinstance(field_hints, dict) else []
        if isinstance(values, list):
            priority.extend(str(value) for value in values)
    priority.extend(column for column in columns if any(token in column.lower() for token in ("id", "name", "status", "state", "date", "time", "published", "created", "updated")))
    out: list[str] = []
    seen: set[str] = set()
    for column in priority:
        if column not in columns or column in seen:
            continue
        seen.add(column)
        out.append(column)
    return out


def _compact_api_card(rows: list[dict[str, Any]], target_chars: int, *, aggressive: bool = False) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    description_steps = [180, 120, 80, 40, 0] if not aggressive else [80, 40, 0]
    param_steps = [16, 12, 8, 5] if not aggressive else [8, 5, 3, 1]
    best = [_compact_api_row(row, description_limit=description_steps[0], param_limit=param_steps[0], keep_examples=not aggressive) for row in rows]
    for description_limit in description_steps:
        for param_limit in param_steps:
            candidate = [_compact_api_row(row, description_limit=description_limit, param_limit=param_limit, keep_examples=False) for row in rows]
            best = candidate
            if _json_char_count(candidate) <= target_chars:
                final_chars = _json_char_count(candidate)
                return candidate, {"truncated": final_chars < _json_char_count(rows), "detail_truncated": True, "char_count": final_chars}
    final_chars = _json_char_count(best)
    return best, {"truncated": final_chars < _json_char_count(rows), "detail_truncated": True, "char_count": final_chars}


def _compact_api_row(row: dict[str, Any], *, description_limit: int, param_limit: int, keep_examples: bool) -> dict[str, Any]:
    description = str(row.get("description") or "")
    if description_limit <= 0:
        description = ""
    elif len(description) > description_limit:
        description = description[:description_limit].rstrip()
    return {
        "endpoint_id": row.get("endpoint_id"),
        "method": row.get("method"),
        "path": row.get("path"),
        "path_params": [str(value) for value in (row.get("path_params") or [])[:param_limit]],
        "query_params": [str(value) for value in (row.get("query_params") or [])[:param_limit]],
        "common_params": {},
        "domains": [],
        "examples": row.get("examples", [])[:1] if keep_examples else [],
        "endpoint_role_hints": [str(value) for value in (row.get("endpoint_role_hints") or [])[:param_limit]],
        "description": description,
    }


def _ultra_compact_schema_card(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for row in rows:
        columns = [str(item) for item in row.get("columns", []) if str(item)]
        field_hints = row.get("field_hints") if isinstance(row.get("field_hints"), dict) else {}
        priority = _schema_priority_columns(columns, field_hints)
        compact.append(
            {
                "table": row.get("table"),
                "columns": (priority or columns)[:1],
                "table_role_hints": [],
                "field_hints": {},
            }
        )
    return compact, {"truncated": True, "columns_truncated": True, "char_count": _json_char_count(compact)}


def _ultra_compact_api_card(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for row in rows:
        compact.append(
            {
                "endpoint_id": row.get("endpoint_id"),
                "method": row.get("method"),
                "path": row.get("path"),
                "path_params": [str(value) for value in (row.get("path_params") or [])[:1]],
                "query_params": [str(value) for value in (row.get("query_params") or [])[:1]],
                "common_params": {},
                "domains": [],
                "examples": [],
                "endpoint_role_hints": [],
                "description": "",
            }
        )
    return compact, {"truncated": True, "detail_truncated": True, "char_count": _json_char_count(compact)}


def _semantic_ir_total_prompt_chars(
    *,
    user_prompt: str,
    allowed_schema_card: list[dict[str, Any]],
    allowed_api_card: list[dict[str, Any]],
    repair_context: dict[str, Any] | None,
) -> int:
    return (
        len(_semantic_ir_system_prompt())
        + len(
            _semantic_ir_user_prompt(
                user_prompt=user_prompt,
                allowed_schema_card=allowed_schema_card,
                allowed_api_card=allowed_api_card,
                repair_context=repair_context,
            )
        )
        + len(json.dumps(semantic_ir_tool_schema(), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    )


def _json_char_count(value: Any) -> int:
    return len(json.dumps(redact_secrets(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")))


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
            "Return one submit_semantic_ir_plan tool call.",
            "No plan in message content.",
            "LLM owns route, task semantics, source, table, fields, filters, endpoint, dependencies, and aggregation.",
            "Do not invent tables, columns, endpoint IDs, filters, or fields.",
            "DIRECT route: tasks empty, concise direct_answer, pure no-evidence concept/meta only.",
            "EVIDENCE route: tasks contain the LLM-owned evidence tasks.",
            "Prefer supported Semantic IR operations whenever they can express the requested evidence.",
            "Use LIST/COUNT/LOOKUP/STATUS/DATE LocalQueryIR operations for simple local snapshot requests.",
            "raw SQL fallback is an escape hatch only when required LOCAL_SNAPSHOT evidence cannot be represented by supported Semantic IR.",
            "Do not ask the backend to write SQL, infer SQL, choose SQL tables, choose SQL fields, or repair SQL for you.",
            "If unsupported JOIN/GROUP/window local SQL is truly required, set requires_raw_sql_fallback=true, raw_sql_reason, and unsupported_features.",
            *_semantic_ir_source_selection_rules(),
            "For how many/count/number/total prompts, use operation COUNT and local_query.count=true; sampled LIST rows are not a count.",
            "For LOCAL_SNAPSHOT COUNT, required evidence task must be LOCAL_QUERY, source LOCAL_SNAPSHOT, operation COUNT, local_query.count=true.",
            "For date/published/created/updated without live/current/platform/API, use LOCAL_QUERY DATE/LOOKUP when local timestamp fields exist.",
            "For published/date prompts, select all relevant local timestamp candidates available, e.g. CREATEDTIME, UPDATEDTIME, STARTDATE, LASTDEPLOYEDTIME, STOPPEDTIME, FINISHEDTIME.",
            "Do not make local lookup depend on live API unless the local filter literally needs an ID returned by live task.",
            "For lifecycle active/inactive/status/state, use allowed fields/known values; if enum unknown, prefer broader LOCAL_QUERY over invented literal INACTIVE enum.",
            "For compare local/live prompts, include LOCAL_QUERY and LIVE_QUERY tasks when both are available, then aggregate.",
            "If two tasks require exactly the same runtime evidence, you may declare a CACHE_ALIAS task instead of repeating SQL/API.",
            "LLM owns semantic equivalence; the backend will not infer aliases from natural language, task descriptions, SQL, or API similarity.",
            "A CACHE_ALIAS must set reuse_result_from, depends_on producer, no local_query/api_query, and identical result_contract.",
            "Only alias when source, scope, operation, object, entity, fields, filters, freshness, and answer contract are identical.",
            "If uncertain, do not alias. Do not alias local and live. Do not alias status and date, count/list, concepts/evidence, or different entities/sources/scopes/fields/filters.",
        ],
        "semantic_ir_examples": [
            {
                "user_prompt": "Explain what inactive journey means and show inactive journeys.",
                "shape": "CONCEPT plus LOCAL_QUERY for inactive journeys.",
            }
        ],
        "semantic_alias_examples": [],
        "repair_context": redact_secrets(repair_context) if repair_context else None,
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _semantic_ir_source_selection_rules() -> list[str]:
    return [
        "Prefer LOCAL_QUERY for user-specific local or ambiguous data-like prompts unless the prompt explicitly asks for live/current/platform/API or names an API catalog resource.",
        "If no live/current/platform/API cue asks for records, count, date, status, or list, LIVE_QUERY is the wrong source; choose LOCAL_QUERY unless the prompt names an API catalog resource.",
        "'do I have', 'my', show/list/give me records, and bare entity lookups without live/current/platform/API cues are LOCAL_SNAPSHOT unless they name API catalog resources.",
        "Bare 'schema' or 'schemas' plus 'do I have' or 'my' is LOCAL_SNAPSHOT; do not treat schemas alone as a Schema Registry cue.",
        "Use schema registry/schema API only for Schema Registry, API, live, current, platform, Adobe Experience Platform, or compare local/live schemas.",
        "Do not choose LIVE_QUERY merely because a live endpoint exists for the object family.",
        "Use LIVE_QUERY for explicit live/current/platform/API state, compare local/live evidence, or a named API catalog resource with a matching AllowedAPIContextCard endpoint.",
        "Treat sandbox/sandbox-name prompts as live/API cues for API catalog resources unless prompt says local snapshot.",
        "Endpoint catalog resources such as tags, merge policies, segment definitions, segment jobs, catalog batches/files, audit events, dataflow runs/flows, and recent platform changes use LIVE_QUERY when matched.",
        "Do not invent local table names from endpoint IDs or API nouns; if no matching local table is listed, choose matching LIVE_QUERY instead of fabricating LOCAL_QUERY.",
        "For batch prompts, use catalog_batches, catalog_batch_detail, export_batch_files, or export_batch_failed when user supplies needed path params.",
        "For recent changes, new destinations, or audit-style history prompts, use audit_events or audit_events_short when available.",
        "For segment definitions as sandbox/platform API resources or bare segment-definition catalog requests, use segment_definitions unless prompt asks local snapshot.",
        "For segment jobs or evaluation jobs, use segment_jobs unless prompt asks local snapshot.",
        "For tags and merge policies in this sandbox, use unified_tags or merge_policies rather than LOCAL_QUERY.",
        "For show/list actual records without live/current/platform/API cues, prefer LOCAL_QUERY over LIVE_QUERY unless they name API catalog resources.",
        "For mixed concept plus data prompts without live/current/platform/API cues, include CONCEPT plus LOCAL_QUERY; API only if data part names an API catalog resource.",
        "For inactive journeys without live/current/platform/API cues, use local snapshot journey/campaign records when an allowed local table is available.",
        "For inactive journey/campaign local tasks, do not invent literal INACTIVE enum unless known; select NAME plus STATUS/STATE for safe non-active records.",
        "For quoted/named entity filters, prefer primary_name_fields or title/name fields over label_fields; use label_fields for labels/tags/semantic labels.",
        "For relationship-bearing fields, schema class, or merge policy prompts, select existing allowed local fields; do not ask backend to infer links.",
        ]


def _semantic_ir_missing_toolcall_retry_user_prompt(
    *,
    user_prompt: str,
    previous_result: dict[str, Any],
    allowed_schema_card: list[dict[str, Any]],
    allowed_api_card: list[dict[str, Any]],
) -> str:
    payload = {
        "task": "RETRY_MISSING_DASHSYS_V2_SEMANTIC_IR_TOOLCALL",
        "user_prompt": user_prompt,
        "previous_model_response": compact_preview(previous_result, 1200),
        "validation_error": {
            "error_type": "missing_tool_call",
            "error_message": "The previous response did not call submit_semantic_ir_plan. Plain text is not accepted for the V2 primary path.",
        },
        "allowed_schema_card": allowed_schema_card,
        "allowed_api_card": allowed_api_card,
        "rules": [
            "Submit exactly one submit_semantic_ir_plan SDK tool call now.",
            "Do not answer in message content.",
            "Use DIRECT with empty tasks only for pure no-evidence concept/meta prompts.",
            "Use EVIDENCE with tasks for data, mixed, local, live, count, list, status, date, lookup, or compare prompts.",
            *_semantic_ir_source_selection_rules(),
        ],
    }
    return json.dumps(redact_secrets(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


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
            *_semantic_ir_source_selection_rules(),
        ],
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


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
            *_semantic_ir_source_selection_rules(),
        ],
    }
    return json.dumps(redact_secrets(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
