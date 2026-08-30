from __future__ import annotations

import json
import time
from dataclasses import dataclass, replace
from typing import Any

from .trajectory import compact_preview, redact_secrets
from .v2_answer_contract import V2AnswerContract, answer_contract_to_dict, parse_answer_contract
from .v2_answer_contract_validator import AnswerContractValidator
from .v2_semantic_ir import SemanticIRPlan, semantic_plan_to_dict
from .v2_semantic_ir_validator import SemanticIRValidationResult
from .v2_weak_model_protocol import _elapsed_ms


ANSWER_CONTRACT_TOOL_NAME = "submit_answer_contract"


@dataclass
class AnswerContractPlannerResult:
    ok: bool
    answer_contract: V2AnswerContract | None = None
    error_type: str | None = None
    error_message: str | None = None
    diagnostics: dict[str, Any] | None = None
    raw_preview: Any | None = None
    latency_ms: int = 0


def answer_contract_tool_schema() -> dict[str, Any]:
    slot_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "slot_id": {"type": "string"},
            "type": {"type": "string", "enum": ["COUNT", "LIST", "DATE", "STATUS", "RELATION", "COMPARISON", "CONCEPT", "LOOKUP", "SUMMARY"]},
            "required": {"type": "boolean"},
            "subject": {"type": "string"},
            "object": {"type": "string"},
            "relation": {"type": "string"},
            "source_scope": {"type": "string", "enum": ["LOCAL_SNAPSHOT", "LIVE_API", "BOTH", "NONE"]},
            "satisfied_by_tasks": {"type": "array", "items": {"type": "string"}},
            "required_fields": {"type": "array", "items": {"type": "string"}},
            "acceptable_fallback_fields": {"type": "array", "items": {"type": "string"}},
            "expected_status_filter": {"type": "string"},
            "zero_rows_semantics": {"type": "string", "enum": ["NO_MATCH", "UNKNOWN", "EMPTY_RESULT_IS_ANSWER", "NOT_APPLICABLE"]},
            "if_missing": {"type": "string", "enum": ["SCOPED_UNAVAILABLE_CAVEAT", "FAIL_REQUIRED", "ALLOW_PARTIAL"]},
            "must_not_assert_positive_if_zero_rows": {"type": "boolean"},
            "notes": {"type": "string"},
        },
        "required": ["slot_id", "type", "required", "source_scope", "satisfied_by_tasks", "zero_rows_semantics", "if_missing"],
    }
    return {
        "type": "function",
        "function": {
            "name": ANSWER_CONTRACT_TOOL_NAME,
            "description": "Submit only the V2 final-answer contract for an already accepted Semantic IR task list.",
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "answer_contract": {
                        "type": "object",
                        "properties": {
                            "required_slots": {"type": "array", "items": slot_schema},
                            "optional_slots": {"type": "array", "items": {"type": "object"}},
                            "answer_style": {"type": "string", "enum": ["CONCISE", "EXPLANATORY", "LIST", "TABLE", "COMPARISON", "COUNT_ONLY", "CAVEATED"]},
                            "global_scope": {"type": "string", "enum": ["LOCAL_SNAPSHOT", "LIVE_API", "BOTH", "NONE"]},
                            "contract_version": {"type": "string", "enum": ["v1"]},
                        },
                        "required": ["required_slots"],
                    }
                },
                "required": ["answer_contract"],
            },
        },
    }


def run_answer_contract_planner(
    *,
    client: Any,
    user_prompt: str,
    semantic_plan: SemanticIRPlan,
    allowed_schema_card: list[dict[str, Any]],
    allowed_api_card: list[dict[str, Any]],
    validation_error: SemanticIRValidationResult | None = None,
) -> AnswerContractPlannerResult:
    started = time.perf_counter()
    result, call_error = _call_answer_contract_tool(
        client,
        system_prompt=_answer_contract_system_prompt(),
        user_prompt=_answer_contract_user_prompt(
            user_prompt=user_prompt,
            semantic_plan=semantic_plan,
            allowed_schema_card=allowed_schema_card,
            allowed_api_card=allowed_api_card,
            validation_error=validation_error,
        ),
    )
    latency_ms = _elapsed_ms(started)
    raw_preview = compact_preview(result or call_error, 1200)
    if call_error:
        return AnswerContractPlannerResult(
            ok=False,
            error_type="contract_tool_call_error",
            error_message=call_error,
            diagnostics=_diagnostics(False, "contract_tool_call_error", call_error),
            raw_preview=raw_preview,
            latency_ms=latency_ms,
        )
    args = _extract_answer_contract_tool_arguments(result)
    if args is None:
        return AnswerContractPlannerResult(
            ok=False,
            error_type="missing_answer_contract_tool_call",
            error_message="Answer contract planner did not return submit_answer_contract tool call.",
            diagnostics=_diagnostics(False, "missing_answer_contract_tool_call", "Missing submit_answer_contract tool call."),
            raw_preview=raw_preview,
            latency_ms=latency_ms,
        )
    try:
        contract = parse_answer_contract(args.get("answer_contract") if isinstance(args.get("answer_contract"), dict) else args)
    except Exception as exc:
        return AnswerContractPlannerResult(
            ok=False,
            error_type="answer_contract_parse_error",
            error_message=str(exc),
            diagnostics=_diagnostics(False, "answer_contract_parse_error", str(exc)),
            raw_preview=raw_preview,
            latency_ms=latency_ms,
        )
    plan_with_contract = replace(semantic_plan, answer_contract=contract)
    validation = AnswerContractValidator().validate(plan_with_contract)
    if not validation.passed:
        return AnswerContractPlannerResult(
            ok=False,
            answer_contract=contract,
            error_type=validation.error_type or "invalid_answer_contract",
            error_message=validation.error_message or "Invalid answer contract.",
            diagnostics=_diagnostics(False, validation.error_type or "invalid_answer_contract", validation.error_message),
            raw_preview=raw_preview,
            latency_ms=latency_ms,
        )
    return AnswerContractPlannerResult(
        ok=True,
        answer_contract=contract,
        diagnostics=_diagnostics(True, None, None, required_slot_count=len(contract.required_slots)),
        raw_preview=raw_preview,
        latency_ms=latency_ms,
    )


def _call_answer_contract_tool(client: Any, *, system_prompt: str, user_prompt: str) -> tuple[dict[str, Any], str | None]:
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
    tool_choice = {"type": "function", "function": {"name": ANSWER_CONTRACT_TOOL_NAME}}
    try:
        result = client.generate_messages(
            messages,
            tools=[answer_contract_tool_schema()],
            tool_choice=tool_choice,
            parallel_tool_calls=False,
        )
    except TypeError:
        result = client.generate_messages(messages, tools=[answer_contract_tool_schema()], tool_choice=tool_choice)
    except Exception as exc:
        return {}, str(exc)
    if not isinstance(result, dict):
        return {}, "LLM client returned non-dict response."
    if not result.get("ok", True):
        return result, str(result.get("error") or result.get("reason") or "LLM client returned failure.")
    return result, None


def _extract_answer_contract_tool_arguments(result: dict[str, Any]) -> dict[str, Any] | None:
    for call in result.get("tool_calls") or []:
        if not isinstance(call, dict):
            continue
        name = call.get("name") or call.get("tool") or (call.get("function") or {}).get("name")
        if name != ANSWER_CONTRACT_TOOL_NAME:
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


def _answer_contract_system_prompt() -> str:
    return (
        "You create only the V2 Answer Contract for an already accepted LLM-owned Semantic IR task list. "
        "Do not change tasks, table IDs, endpoint IDs, fields, filters, dependencies, or route. "
        "Do not answer the user. Do not add evidence. Submit exactly one submit_answer_contract tool call."
    )


def _answer_contract_user_prompt(
    *,
    user_prompt: str,
    semantic_plan: SemanticIRPlan,
    allowed_schema_card: list[dict[str, Any]],
    allowed_api_card: list[dict[str, Any]],
    validation_error: SemanticIRValidationResult | None,
) -> str:
    task_cards = [
        {
            "task_id": task.task_id,
            "kind": task.kind,
            "operation": task.operation,
            "source": task.source,
            "description": task.description,
            "local_query": task.local_query.to_dict() if task.local_query else None,
            "api_query": task.api_query.to_dict() if task.api_query else None,
        }
        for task in semantic_plan.tasks
    ]
    payload = {
        "task": "SUBMIT_V2_ANSWER_CONTRACT_ONLY",
        "user_prompt": user_prompt,
        "semantic_ir_tasks_do_not_change": task_cards,
        "allowed_schema_card": allowed_schema_card,
        "allowed_api_card": allowed_api_card,
        "validation_error": validation_error.to_dict() if validation_error else None,
        "rules": [
            "Do not change tasks. Only create an answer_contract that describes what the final answer must cover.",
            "Each required slot must reference existing task IDs in satisfied_by_tasks.",
            "Use source_scope matching the referenced task source: LOCAL_SNAPSHOT, LIVE_API, BOTH, or NONE.",
            "Use compact slots when possible. Defaults are allowed for contract_version, optional_slots, answer_style, acceptable_fallback_fields, and must_not_assert_positive_if_zero_rows.",
            "COUNT slots use required_fields ['count']; LIST/LOOKUP/STATUS/RELATION slots need scoped zero_rows_semantics and caveat policy.",
            "Never use gold answers, expected traces, query IDs, or hidden evaluation wording.",
        ],
    }
    return json.dumps(redact_secrets(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _diagnostics(
    success: bool,
    error_type: str | None,
    error_message: str | None,
    *,
    required_slot_count: int = 0,
) -> dict[str, Any]:
    return {
        "answer_contract_secondary_call_used": True,
        "answer_contract_secondary_call_success": bool(success),
        "answer_contract_secondary_error": error_message,
        "answer_contract_secondary_error_type": error_type,
        "required_slot_count": required_slot_count,
        "backend_answer_contract_inference_used": False,
    }


def answer_contract_payload_preview(contract: V2AnswerContract | None) -> dict[str, Any] | None:
    return answer_contract_to_dict(contract)
