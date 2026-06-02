from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from .trajectory import compact_preview
from .v2_answer_contract import V2AnswerContract, answer_contract_to_dict
from .v2_schema_binding import SchemaBindingPlan, parse_schema_binding_plan, schema_binding_plan_to_dict
from .v2_schema_binding_validator import SchemaBindingValidationResult, SchemaBindingValidator
from .v2_semantic_ir import SemanticIRPlan, semantic_plan_to_dict
from .v2_weak_model_protocol import _elapsed_ms


SCHEMA_BINDING_TOOL_NAME = "submit_schema_binding_plan"


@dataclass
class SchemaBindingPlannerResult:
    ok: bool
    binding_plan: SchemaBindingPlan | None = None
    error_type: str | None = None
    error_message: str | None = None
    repair_attempted: bool = False
    repair_success: bool = False
    latency_ms: int = 0
    raw_preview: Any = None
    diagnostics: dict[str, Any] = field(default_factory=dict)


def schema_binding_tool_schema() -> dict[str, Any]:
    binding_schema: dict[str, Any] = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "binding_id": {"type": "string"},
            "semantic_object": {"type": "string"},
            "object_type": {
                "type": "string",
                "enum": [
                    "schema",
                    "blueprint",
                    "segment",
                    "journey",
                    "campaign",
                    "batch",
                    "dataset",
                    "audience",
                    "destination",
                    "merge_policy",
                    "class",
                    "field",
                    "relationship",
                    "unknown",
                ],
            },
            "source_scope": {"type": "string", "enum": ["LOCAL_SNAPSHOT", "LIVE_API", "BOTH", "NONE"]},
            "table": {"anyOf": [{"type": "string"}, {"type": "null"}]},
            "primary_id_fields": {"type": "array", "items": {"type": "string"}},
            "name_fields": {"type": "array", "items": {"type": "string"}},
            "status_fields": {"type": "array", "items": {"type": "string"}},
            "date_fields": {"type": "array", "items": {"type": "string"}},
            "relation_tables": {"type": "array", "items": {"type": "string"}},
            "required_for_slots": {"type": "array", "items": {"type": "string"}},
            "confidence_note": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        },
        "required": [
            "binding_id",
            "semantic_object",
            "object_type",
            "source_scope",
            "table",
            "primary_id_fields",
            "name_fields",
            "status_fields",
            "date_fields",
            "relation_tables",
            "required_for_slots",
            "confidence_note",
        ],
    }
    return {
        "type": "function",
        "function": {
            "name": SCHEMA_BINDING_TOOL_NAME,
            "description": "Bind Semantic IR answer slots/tasks to exact allowed local schema table and field IDs.",
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "binding_version": {"type": "string", "enum": ["v1"]},
                    "bindings": {"type": "array", "items": binding_schema},
                },
                "required": ["bindings"],
            },
        },
    }


def run_schema_binding_planner(
    *,
    client: Any,
    user_prompt: str,
    semantic_plan: SemanticIRPlan,
    answer_contract: V2AnswerContract | None,
    allowed_schema_card: list[dict[str, Any]],
    validation_error: Any | None = None,
) -> SchemaBindingPlannerResult:
    started = time.perf_counter()
    validator = SchemaBindingValidator(allowed_schema_card, answer_contract)
    raw_previews: dict[str, Any] = {}

    result, call_error = _call_schema_binding_tool(
        client,
        system_prompt=_schema_binding_system_prompt(),
        user_prompt=_schema_binding_user_prompt(
            user_prompt=user_prompt,
            semantic_plan=semantic_plan,
            answer_contract=answer_contract,
            allowed_schema_card=allowed_schema_card,
            validation_error=validation_error,
        ),
    )
    raw_previews["schema_binding_initial"] = compact_preview(result or call_error, 1200)
    if call_error:
        return _result(False, None, "schema_binding_tool_error", call_error, started, raw_previews)

    plan, validation, parse_error = _parse_and_validate(result, validator, semantic_plan)
    if parse_error:
        return _result(False, None, "schema_binding_parse_error", parse_error, started, raw_previews)
    if validation.passed:
        return _result(True, plan, None, None, started, raw_previews, validation=validation)

    repair_result, repair_error = _call_schema_binding_tool(
        client,
        system_prompt=_schema_binding_system_prompt(),
        user_prompt=_schema_binding_user_prompt(
            user_prompt=user_prompt,
            semantic_plan=semantic_plan,
            answer_contract=answer_contract,
            allowed_schema_card=allowed_schema_card,
            validation_error=validation,
        ),
    )
    raw_previews["schema_binding_repair"] = compact_preview(repair_result or repair_error, 1200)
    if repair_error:
        return _result(
            False,
            plan,
            "schema_binding_repair_error",
            repair_error,
            started,
            raw_previews,
            validation=validation,
            repair_attempted=True,
        )
    repaired_plan, repaired_validation, repaired_parse_error = _parse_and_validate(repair_result, validator, semantic_plan)
    if repaired_parse_error:
        return _result(
            False,
            plan,
            "schema_binding_parse_error",
            repaired_parse_error,
            started,
            raw_previews,
            validation=validation,
            repair_attempted=True,
        )
    return _result(
        repaired_validation.passed,
        repaired_plan,
        repaired_validation.error_type,
        repaired_validation.error_message,
        started,
        raw_previews,
        validation=repaired_validation,
        repair_attempted=True,
        repair_success=repaired_validation.passed,
    )


def _parse_and_validate(
    llm_result: dict[str, Any],
    validator: SchemaBindingValidator,
    semantic_plan: SemanticIRPlan,
) -> tuple[SchemaBindingPlan | None, SchemaBindingValidationResult, str | None]:
    args = _extract_schema_binding_tool_arguments(llm_result)
    if args is None:
        return None, SchemaBindingValidationResult(False, "missing_schema_binding_tool_call", "Missing submit_schema_binding_plan tool call."), None
    try:
        plan = parse_schema_binding_plan(args)
    except Exception as exc:
        return None, SchemaBindingValidationResult(False, "schema_binding_parse_error", str(exc)), str(exc)
    validation = validator.validate(plan, semantic_plan=semantic_plan)
    return plan, validation, None


def _result(
    ok: bool,
    plan: SchemaBindingPlan | None,
    error_type: str | None,
    error_message: str | None,
    started: float,
    raw_preview: Any,
    *,
    validation: SchemaBindingValidationResult | None = None,
    repair_attempted: bool = False,
    repair_success: bool = False,
) -> SchemaBindingPlannerResult:
    diagnostics = {
        "schema_binding_used": True,
        "schema_binding_count": len(plan.bindings) if plan else 0,
        "schema_binding_ids": [binding.binding_id for binding in plan.bindings] if plan else [],
        "schema_binding_validation_passed": bool(ok),
        "schema_binding_error_type": error_type,
        "schema_binding_error_message": error_message,
        "schema_binding_repair_attempted": bool(repair_attempted),
        "schema_binding_repair_success": bool(repair_success),
        "backend_schema_binding_inference_used": False,
    }
    if validation is not None:
        diagnostics["schema_binding_validation"] = validation.to_dict()
        diagnostics["schema_binding_error_type"] = validation.error_type if not validation.passed else None
        diagnostics["schema_binding_error_message"] = validation.error_message if not validation.passed else None
    return SchemaBindingPlannerResult(
        ok=ok,
        binding_plan=plan,
        error_type=diagnostics.get("schema_binding_error_type"),
        error_message=diagnostics.get("schema_binding_error_message"),
        repair_attempted=repair_attempted,
        repair_success=repair_success,
        latency_ms=_elapsed_ms(started),
        raw_preview=raw_preview,
        diagnostics=diagnostics,
    )


def _call_schema_binding_tool(client: Any, *, system_prompt: str, user_prompt: str) -> tuple[dict[str, Any], str | None]:
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
    tool_choice = {"type": "function", "function": {"name": SCHEMA_BINDING_TOOL_NAME}}
    try:
        result = client.generate_messages(
            messages,
            tools=[schema_binding_tool_schema()],
            tool_choice=tool_choice,
            parallel_tool_calls=False,
        )
    except TypeError:
        result = client.generate_messages(messages, tools=[schema_binding_tool_schema()], tool_choice=tool_choice)
    except Exception as exc:
        return {}, str(exc)
    if not isinstance(result, dict):
        return {}, "LLM client returned non-dict response."
    if not result.get("ok", True):
        return result, str(result.get("error") or result.get("reason") or "LLM client returned failure.")
    return result, None


def _extract_schema_binding_tool_arguments(result: dict[str, Any]) -> dict[str, Any] | None:
    for call in result.get("tool_calls") or []:
        if not isinstance(call, dict):
            continue
        name = call.get("name") or call.get("tool") or (call.get("function") or {}).get("name")
        if name != SCHEMA_BINDING_TOOL_NAME:
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


def _schema_binding_system_prompt() -> str:
    return (
        "You are the DASHSys V2 Schema Binding Planner. "
        "The LLM owns semantic object to schema binding. The backend will not infer bindings. "
        "Return exactly one submit_schema_binding_plan tool call."
    )


def _schema_binding_user_prompt(
    *,
    user_prompt: str,
    semantic_plan: SemanticIRPlan,
    answer_contract: V2AnswerContract | None,
    allowed_schema_card: list[dict[str, Any]],
    validation_error: Any | None,
) -> str:
    payload = {
        "task": "Bind each semantic object required by the tasks/answer slots to exact table and field IDs from the allowed cards. Do not invent table or field names. Do not write SQL.",
        "rules": [
            "The LLM owns the binding choice.",
            "The backend will not infer, replace, or repair semantic bindings.",
            "Use exact table and field IDs only from allowed cards.",
            "If LOCAL_SNAPSHOT is needed, table must be an allowed table ID.",
            "If a field category is unknown, leave that field list empty rather than inventing names.",
        ],
        "user_prompt": user_prompt,
        "semantic_ir_tasks_do_not_change": [
            {
                "task_id": task.task_id,
                "kind": task.kind,
                "operation": task.operation,
                "source": task.source,
                "binding_id": getattr(task, "binding_id", None),
                "local_query": task.local_query.to_dict() if task.local_query else None,
                "api_query": task.api_query.to_dict() if task.api_query else None,
                "description": task.description,
            }
            for task in semantic_plan.tasks
        ],
        "answer_contract": answer_contract_to_dict(answer_contract),
        "table_role_cards": _table_role_cards(allowed_schema_card),
        "relationship_cards": _relationship_cards(allowed_schema_card),
        "field_role_cards": _field_role_cards(allowed_schema_card),
        "validation_error": validation_error.to_dict() if hasattr(validation_error, "to_dict") else validation_error,
        "output_tool": SCHEMA_BINDING_TOOL_NAME,
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _table_role_cards(allowed_schema_card: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "table": row.get("table"),
            "table_role_hints": list(row.get("table_role_hints") or []),
            "columns": list(row.get("columns") or [])[:32],
        }
        for row in allowed_schema_card
    ]


def _relationship_cards(allowed_schema_card: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for row in allowed_schema_card:
        table = str(row.get("table") or "")
        hints = list(row.get("table_role_hints") or [])
        if "bridge_table" in hints or "relationship_table" in hints:
            cards.append({"table": table, "columns": list(row.get("columns") or [])[:32], "table_role_hints": hints})
    return cards


def _field_role_cards(allowed_schema_card: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for row in allowed_schema_card:
        hints = row.get("field_hints") if isinstance(row.get("field_hints"), dict) else {}
        cards.append(
            {
                "table": row.get("table"),
                "id_fields": list(hints.get("id_fields") or []),
                "name_fields": list(hints.get("name_fields") or []),
                "primary_name_fields": list(hints.get("primary_name_fields") or []),
                "status_fields": list(hints.get("status_fields") or []),
                "date_fields": list(hints.get("date_fields") or []),
                "count_fields": list(hints.get("count_fields") or []),
            }
        )
    return cards


def schema_binding_payload_preview(plan: SchemaBindingPlan | None) -> dict[str, Any] | None:
    return schema_binding_plan_to_dict(plan)
