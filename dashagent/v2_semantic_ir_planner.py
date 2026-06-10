from __future__ import annotations

import json
import os
import signal
import threading
import time
from typing import Any

from .trajectory import compact_preview, redact_secrets
from .raw_sql_safety_gate import RawSQLSafetyGate
from .v2_atomic_weak_protocol import run_atomic_weak_protocol
from .v2_answer_contract_planner import run_answer_contract_planner
from .v2_answer_contract_validator import AnswerContractValidator
from .v2_schema_binding_planner import run_schema_binding_planner
from .v2_schema_grounding import bind_semantic_ir_schema_aliases
from .v2_raw_sql_fallback import RawSQLFallbackResult, run_raw_sql_fallback_planner
from .v2_semantic_ir import SemanticIRPlan, parse_semantic_ir_from_json_or_line_protocol, semantic_plan_to_dict
from .v2_semantic_ir_compiler import compile_semantic_ir_to_plan_payload
from .v2_semantic_ir_context import build_allowed_api_context_card, build_allowed_local_schema_card
from .v2_semantic_ir_support import IRSupportResult, check_semantic_ir_support
from .v2_semantic_ir_validator import SemanticIRValidationResult, SemanticIRValidator
from .v2_weak_model_protocol import WeakProtocolResult, _elapsed_ms
from .v2_weak_model_protocol import _legacy_full_plan_payload


SEMANTIC_IR_TOOL_NAME = "submit_semantic_ir_plan"
SEMANTIC_IR_JSON_TOOL_NAME = "submit_semantic_ir_json"
MICRO_DIRECT_TOOL_NAME = "submit_direct_task"
MICRO_LOCAL_QUERY_TOOL_NAME = "submit_local_query_task"
MICRO_LOCAL_COUNT_TOOL_NAME = "submit_local_count_task"
MICRO_LOCAL_LOOKUP_TOOL_NAME = "submit_local_lookup_task"
MICRO_API_TOOL_NAME = "submit_api_task"
MICRO_MIXED_TOOL_NAME = "submit_mixed_evidence_plan"
PLANNER_PROFILE_CURRENT = "current"
PLANNER_PROFILE_DEEPSEEK_AUTO_TOOL = "deepseek_auto_tool"
PLANNER_PROFILE_DEEPSEEK_REQUIRED_TOOL = "deepseek_required_tool"
PLANNER_PROFILE_DEEPSEEK_MICRO_TOOLS = "deepseek_micro_tools"
PLANNER_PROFILE_DEEPSEEK_JSON_TOOL = "deepseek_json_tool"
SUPPORTED_PLANNER_PROFILES = {
    PLANNER_PROFILE_CURRENT,
    PLANNER_PROFILE_DEEPSEEK_AUTO_TOOL,
    PLANNER_PROFILE_DEEPSEEK_REQUIRED_TOOL,
    PLANNER_PROFILE_DEEPSEEK_MICRO_TOOLS,
    PLANNER_PROFILE_DEEPSEEK_JSON_TOOL,
}
DEEPSEEK_SWEEP_PROFILE_ORDER = [
    PLANNER_PROFILE_CURRENT,
    PLANNER_PROFILE_DEEPSEEK_AUTO_TOOL,
    PLANNER_PROFILE_DEEPSEEK_REQUIRED_TOOL,
    PLANNER_PROFILE_DEEPSEEK_MICRO_TOOLS,
    PLANNER_PROFILE_DEEPSEEK_JSON_TOOL,
]
MICRO_TOOL_NAMES = {
    MICRO_DIRECT_TOOL_NAME,
    MICRO_LOCAL_QUERY_TOOL_NAME,
    MICRO_LOCAL_COUNT_TOOL_NAME,
    MICRO_LOCAL_LOOKUP_TOOL_NAME,
    MICRO_API_TOOL_NAME,
    MICRO_MIXED_TOOL_NAME,
}
DEFAULT_SEMANTIC_IR_PLANNER_CHAR_BUDGET = 24000
_SCHEMA_CARD_TARGET_SHARE = 0.58
_API_CARD_TARGET_SHARE = 0.42
ANSWER_CONTRACT_VALIDATION_ERROR_TYPES = {
    "missing_answer_contract",
    "unknown_slot_task_reference",
    "slot_scope_task_mismatch",
    "missing_zero_rows_semantics",
    "missing_date_fields",
    "missing_relation_descriptor",
    "missing_if_missing_policy",
    "count_slot_task_operation_mismatch",
    "list_slot_task_operation_mismatch",
    "status_slot_task_operation_mismatch",
    "date_slot_task_operation_mismatch",
}
SCHEMA_BINDING_VALIDATION_ERROR_TYPES = {
    "missing_schema_binding",
    "missing_binding_id",
    "duplicate_binding_id",
    "missing_table",
    "unknown_table",
    "unknown_field",
    "invalid_relation_table",
    "invalid_slot_reference",
    "scope_mismatch",
    "binding_reference_mismatch",
    "invalid_binding_reference",
    "binding_table_conflict",
}


def _normalize_planner_profile(value: str | None) -> str:
    normalized = str(value or "").strip().lower().replace("-", "_")
    aliases = {
        "": "",
        "compact": PLANNER_PROFILE_CURRENT,
        "single_tool": PLANNER_PROFILE_CURRENT,
        "deepseek_current": PLANNER_PROFILE_CURRENT,
        "auto": PLANNER_PROFILE_DEEPSEEK_AUTO_TOOL,
        "auto_tool": PLANNER_PROFILE_DEEPSEEK_AUTO_TOOL,
        "required": PLANNER_PROFILE_DEEPSEEK_REQUIRED_TOOL,
        "required_tool": PLANNER_PROFILE_DEEPSEEK_REQUIRED_TOOL,
        "micro": PLANNER_PROFILE_DEEPSEEK_MICRO_TOOLS,
        "micro_tools": PLANNER_PROFILE_DEEPSEEK_MICRO_TOOLS,
        "json": PLANNER_PROFILE_DEEPSEEK_JSON_TOOL,
        "json_tool": PLANNER_PROFILE_DEEPSEEK_JSON_TOOL,
        "semantic_ir_json_string_tool": PLANNER_PROFILE_DEEPSEEK_JSON_TOOL,
    }
    normalized = aliases.get(normalized, normalized)
    return normalized if normalized in SUPPORTED_PLANNER_PROFILES else PLANNER_PROFILE_CURRENT


def _is_deepseek_v4_flash_local(client: Any | None = None) -> bool:
    try:
        provider = str(client.provider_name() or "").lower() if client is not None else str(os.getenv("DASHAGENT_LLM_PROVIDER") or "").lower()
    except Exception:
        provider = str(os.getenv("DASHAGENT_LLM_PROVIDER") or "").lower()
    try:
        model = str(client.model_name() or "").lower() if client is not None else str(os.getenv("OPENAI_MODEL") or "").lower()
    except Exception:
        model = str(os.getenv("OPENAI_MODEL") or "").lower()
    endpoint_label = str(os.getenv("LLM_ENDPOINT_LABEL") or "").lower()
    return provider in {"openai", "openai_compatible"} and ("deepseek-v4-flash-local" in model or "msi_deepseek" in endpoint_label)


def _planner_profile(client: Any | None = None, *, override: str | None = None) -> str:
    configured = str(override or os.getenv("HERMES_V2_PLANNER_PROFILE") or "").strip()
    if configured:
        return _normalize_planner_profile(configured)
    if _is_deepseek_v4_flash_local(client):
        selected = str(os.getenv("HERMES_V2_DEEPSEEK_DEFAULT_PLANNER_PROFILE") or "").strip()
        if selected:
            return _normalize_planner_profile(selected)
        return PLANNER_PROFILE_DEEPSEEK_MICRO_TOOLS
    return PLANNER_PROFILE_CURRENT


def _planner_tool_choice(planner_profile: str | None) -> str | dict[str, Any]:
    profile = _normalize_planner_profile(planner_profile)
    if profile == PLANNER_PROFILE_DEEPSEEK_AUTO_TOOL:
        return "auto"
    if profile in {PLANNER_PROFILE_DEEPSEEK_REQUIRED_TOOL, PLANNER_PROFILE_DEEPSEEK_MICRO_TOOLS}:
        return "required"
    if profile == PLANNER_PROFILE_DEEPSEEK_JSON_TOOL:
        return {"type": "function", "function": {"name": SEMANTIC_IR_JSON_TOOL_NAME}}
    return {"type": "function", "function": {"name": SEMANTIC_IR_TOOL_NAME}}


def _planner_tool_choice_label(tool_choice: str | dict[str, Any]) -> str:
    if isinstance(tool_choice, str):
        return tool_choice
    try:
        return str((tool_choice.get("function") or {}).get("name") or tool_choice)
    except Exception:
        return str(tool_choice)


def _planner_tools(schema_profile: str | None, planner_profile: str | None) -> list[dict[str, Any]]:
    profile = _normalize_planner_profile(planner_profile)
    if profile == PLANNER_PROFILE_DEEPSEEK_MICRO_TOOLS:
        return semantic_ir_micro_tool_schemas()
    if profile == PLANNER_PROFILE_DEEPSEEK_JSON_TOOL:
        return [semantic_ir_json_tool_schema()]
    return [semantic_ir_tool_schema(schema_profile)]


def _planner_tools_schema_chars(schema_profile: str | None, planner_profile: str | None) -> int:
    return len(json.dumps(_planner_tools(schema_profile, planner_profile), ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def _planner_schema_profile(client: Any | None = None, *, override: str | None = None) -> str:
    configured = str(override or os.getenv("HERMES_V2_PLANNER_SCHEMA_PROFILE") or "").strip().lower()
    if configured:
        return configured
    provider = ""
    model = ""
    try:
        provider = str(client.provider_name() or "").lower() if client is not None else str(os.getenv("DASHAGENT_LLM_PROVIDER") or "").lower()
    except Exception:
        provider = str(os.getenv("DASHAGENT_LLM_PROVIDER") or "").lower()
    try:
        model = str(client.model_name() or "").lower() if client is not None else str(os.getenv("OPENAI_MODEL") or "").lower()
    except Exception:
        model = str(os.getenv("OPENAI_MODEL") or "").lower()
    endpoint_label = str(os.getenv("LLM_ENDPOINT_LABEL") or "").lower()
    if provider in {"openai", "openai_compatible"} and ("deepseek-v4-flash-local" in model or "msi_deepseek" in endpoint_label):
        return "deepseek_compact"
    return "default"


def _is_compact_schema_profile(profile: str | None) -> bool:
    return str(profile or "").strip().lower() in {"deepseek_compact", "deepseek_ultra_compact"}


def semantic_ir_tool_schema(profile: str | None = None) -> dict[str, Any]:
    answer_slot_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "slot_id": {"type": "string"},
            "type": {
                "type": "string",
                "enum": [
                    "COUNT",
                    "LIST",
                    "STATUS",
                    "DATE",
                    "LOOKUP",
                    "RELATION",
                    "COMPARISON",
                    "CONCEPT",
                    "CAVEAT",
                ],
            },
            "required": {"type": "boolean"},
            "subject": {"anyOf": [{"type": "string"}, {"type": "null"}]},
            "object": {"anyOf": [{"type": "string"}, {"type": "null"}]},
            "relation": {"anyOf": [{"type": "string"}, {"type": "null"}]},
            "source_scope": {"type": "string", "enum": ["LOCAL_SNAPSHOT", "LIVE_API", "BOTH", "NONE"]},
            "satisfied_by_tasks": {"type": "array", "items": {"type": "string"}},
            "required_fields": {"type": "array", "items": {"type": "string"}},
            "acceptable_fallback_fields": {"type": "array", "items": {"type": "string"}},
            "expected_status_filter": {"anyOf": [{"type": "string"}, {"type": "null"}]},
            "zero_rows_semantics": {
                "type": "string",
                "enum": ["NO_MATCH", "EMPTY_RESULT_IS_ANSWER", "UNKNOWN", "NOT_APPLICABLE"],
            },
            "if_missing": {
                "type": "string",
                "enum": ["FAIL_REQUIRED", "SCOPED_UNAVAILABLE_CAVEAT", "ALLOW_PARTIAL"],
            },
            "must_not_assert_positive_if_zero_rows": {"type": "boolean"},
            "notes": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        },
        "required": [
            "slot_id",
            "type",
            "required",
            "subject",
            "object",
            "relation",
            "source_scope",
            "satisfied_by_tasks",
            "required_fields",
            "acceptable_fallback_fields",
            "expected_status_filter",
            "zero_rows_semantics",
            "if_missing",
            "must_not_assert_positive_if_zero_rows",
            "notes",
        ],
    }
    compact_profile = _is_compact_schema_profile(profile)
    answer_contract_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "required_slots": {"type": "array", "items": answer_slot_schema},
            "optional_slots": {"type": "array", "items": {"type": "object"}},
            "answer_style": {"type": "string", "enum": ["CONCISE", "EXPLANATORY", "LIST", "TABLE", "COMPARISON", "COUNT_ONLY", "CAVEATED"]},
            "global_scope": {"type": "string", "enum": ["LOCAL_SNAPSHOT", "LIVE_API", "BOTH", "NONE"]},
            "contract_version": {"type": "string", "enum": ["v1"]},
        },
        "required": ["required_slots", "optional_slots", "answer_style", "global_scope", "contract_version"],
    }
    answer_contract_schema = {
        "type": "object",
        "description": "Optional LLM-owned v1 answer contract; backend validator enforces required slot shape.",
        "additionalProperties": True,
    }
    result_contract_schema: dict[str, Any] = (
        {"anyOf": [{"type": "null"}, {"type": "object", "additionalProperties": True}]}
        if compact_profile
        else {
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
    )
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
                            "binding_id": {"anyOf": [{"type": "string"}, {"type": "null"}]},
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
    if not compact_profile:
        task_schema["properties"].update(
            {
                "binding_id": {"anyOf": [{"type": "string"}, {"type": "null"}]},
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
            }
        )
    return {
        "type": "function",
        "function": {
            "name": SEMANTIC_IR_TOOL_NAME,
            "description": "Submit exactly one DASHSys V2 Semantic IR plan. Backend validates and compiles only.",
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "route": {"type": "string", "enum": ["DIRECT", "EVIDENCE"]},
                    "direct_answer": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                    "tasks": {"type": "array", "items": task_schema},
                    "answer_contract": answer_contract_schema,
                    "aggregation_instruction": {"type": "string"},
                },
                "required": ["route", "direct_answer", "tasks", "aggregation_instruction"],
            },
        },
    }


def semantic_ir_json_tool_schema() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": SEMANTIC_IR_JSON_TOOL_NAME,
            "description": "Submit one DASHSys V2 Semantic IR plan encoded as a compact JSON string. Backend validates and compiles only.",
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "semantic_ir_json": {
                        "type": "string",
                        "description": "A valid JSON object matching the submit_semantic_ir_plan payload shape.",
                    }
                },
                "required": ["semantic_ir_json"],
            },
        },
    }


def semantic_ir_micro_tool_schemas() -> list[dict[str, Any]]:
    filter_schema = _micro_filter_schema()
    local_query_schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "table": {"type": "string"},
            "fields": {"type": "array", "items": {"type": "string"}},
            "filters": {"type": "array", "items": filter_schema},
            "limit": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
            "count": {"type": "boolean"},
        },
        "required": ["table", "fields", "filters", "limit", "count"],
    }
    api_query_schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "endpoint_id": {"type": "string"},
            "method": {"type": "string", "enum": ["GET"]},
            "path_params": {"type": "object"},
            "query_params": {"type": "object"},
        },
        "required": ["endpoint_id", "method", "path_params", "query_params"],
    }
    contract_schema = {"anyOf": [{"type": "null"}, {"type": "object", "additionalProperties": True}]}
    direct_task_props = {
        "description": {"type": "string"},
    }
    single_evidence_task_props = {
        "description": {"type": "string"},
        "answer_contract": contract_schema,
    }
    mixed_task_schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "task_id": {"type": "string"},
            "kind": {"type": "string", "enum": ["CONCEPT", "LOCAL_QUERY", "LIVE_QUERY", "LOCAL_AND_LIVE", "AGGREGATE"]},
            "operation": {"type": "string", "enum": ["EXPLAIN", "LIST", "COUNT", "LOOKUP", "STATUS", "DATE", "COMPARE"]},
            "source": {"type": "string", "enum": ["NONE", "LOCAL_SNAPSHOT", "LIVE_API", "BOTH"]},
            "local_query": {"anyOf": [{"type": "null"}, local_query_schema]},
            "api_query": {"anyOf": [{"type": "null"}, api_query_schema]},
            "depends_on": {"type": "array", "items": {"type": "string"}},
            "description": {"type": "string"},
            "required": {"type": "boolean"},
        },
        "required": ["task_id", "kind", "operation", "source", "local_query", "api_query", "depends_on", "description", "required"],
    }
    return [
        {
            "type": "function",
            "function": {
                "name": MICRO_DIRECT_TOOL_NAME,
                "description": "DIRECT concept/meta.",
                "parameters": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        **direct_task_props,
                        "direct_answer": {"type": "string"},
                    },
                    "required": ["direct_answer", "description"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": MICRO_LOCAL_COUNT_TOOL_NAME,
                "description": "LOCAL_SNAPSHOT COUNT.",
                "parameters": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        **single_evidence_task_props,
                        "table": {"type": "string"},
                        "filters": {"type": "array", "items": filter_schema},
                        "subject": {"type": "string"},
                    },
                    "required": ["table", "filters", "description"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": MICRO_LOCAL_QUERY_TOOL_NAME,
                "description": "LOCAL_SNAPSHOT LIST/STATUS/DATE/LOOKUP.",
                "parameters": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        **single_evidence_task_props,
                        "operation": {"type": "string", "enum": ["LIST", "STATUS", "DATE", "LOOKUP", "COMPARE"]},
                        "local_query": local_query_schema,
                    },
                    "required": ["operation", "local_query", "description"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": MICRO_LOCAL_LOOKUP_TOOL_NAME,
                "description": "LOCAL_SNAPSHOT entity lookup/date/status.",
                "parameters": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        **single_evidence_task_props,
                        "operation": {"type": "string", "enum": ["LOOKUP", "STATUS", "DATE", "LIST"]},
                        "table": {"type": "string"},
                        "fields": {"type": "array", "items": {"type": "string"}},
                        "filters": {"type": "array", "items": filter_schema},
                        "limit": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
                    },
                    "required": ["operation", "table", "fields", "filters", "description"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": MICRO_API_TOOL_NAME,
                "description": "LIVE_API GET with exact endpoint_id.",
                "parameters": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        **single_evidence_task_props,
                        "operation": {"type": "string", "enum": ["LIST", "COUNT", "LOOKUP", "STATUS", "DATE", "COMPARE"]},
                        "api_query": api_query_schema,
                    },
                    "required": ["operation", "api_query", "description"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": MICRO_MIXED_TOOL_NAME,
                "description": "Mixed/multi-evidence plan; inactive journey without live/API needs CONCEPT plus LOCAL_QUERY.",
                "parameters": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "direct_answer": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                        "tasks": {"type": "array", "items": mixed_task_schema},
                        "answer_contract": contract_schema,
                        "aggregation_instruction": {"type": "string"},
                    },
                    "required": ["tasks", "aggregation_instruction"],
                },
            },
        },
    ]


def _micro_filter_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "field": {"type": "string"},
            "op": {"type": "string", "enum": ["=", "!=", "contains", "in", ">=", "<=", ">", "<"]},
            "value": {},
        },
        "required": ["field", "op", "value"],
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


def _schema_binding_toolcall_enabled() -> bool:
    raw = os.getenv("V2_ENABLE_SCHEMA_BINDING", "0")
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def semantic_ir_prompt_context_diagnostics(
    *,
    user_prompt: str,
    schema_context: dict[str, Any],
    endpoint_context: list[dict[str, Any]],
    repair_context: dict[str, Any] | None = None,
    max_total_chars: int | None = None,
    schema_profile: str | None = None,
) -> dict[str, Any]:
    """Return pre-call Semantic IR prompt-size diagnostics without invoking the LLM."""
    _, _, diagnostics = _build_semantic_ir_prompt_context(
        schema_context,
        endpoint_context,
        user_prompt=user_prompt,
        repair_context=repair_context,
        max_total_chars=max_total_chars,
        schema_profile=schema_profile,
    )
    return diagnostics


def _build_semantic_ir_prompt_context(
    schema_context: dict[str, Any],
    endpoint_context: list[dict[str, Any]],
    *,
    user_prompt: str = "",
    repair_context: dict[str, Any] | None = None,
    max_total_chars: int | None = None,
    schema_profile: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Build compact prompt cards mechanically; does not choose route, source, tables, fields, or endpoints."""
    profile = _planner_schema_profile(override=schema_profile)
    default_budget = 10500 if profile == "deepseek_compact" else 7600 if profile == "deepseek_ultra_compact" else DEFAULT_SEMANTIC_IR_PLANNER_CHAR_BUDGET
    budget = int(max_total_chars or _configured_semantic_ir_planner_char_budget(default_budget))
    budget_user_prompt = user_prompt or ("x" * 512)
    original_schema_card = build_allowed_local_schema_card(schema_context)
    original_api_card = build_allowed_api_context_card(endpoint_context)
    original_schema_chars = _json_char_count(original_schema_card)
    original_api_chars = _json_char_count(original_api_card)

    if profile == "deepseek_compact":
        schema_card, schema_diag = _ultra_compact_schema_card(original_schema_card, max_columns=4, max_table_role_hints=2)
        api_card, api_diag = _ultra_compact_api_card(original_api_card, max_query_params=2, keep_role_hints=True, omit_empty=True)
    elif profile == "deepseek_ultra_compact":
        schema_card, schema_diag = _ultra_compact_schema_card(original_schema_card, max_columns=2, max_table_role_hints=1)
        api_card, api_diag = _ultra_compact_api_card(original_api_card, max_query_params=1, keep_role_hints=False, omit_empty=True)
    else:
        schema_budget, api_budget = _card_budgets_for_total(budget)
        schema_card, schema_diag = _compact_schema_card(original_schema_card, schema_budget)
        api_card, api_diag = _compact_api_card(original_api_card, api_budget)

    total_chars = _semantic_ir_total_prompt_chars(
        user_prompt=budget_user_prompt,
        allowed_schema_card=schema_card,
        allowed_api_card=api_card,
        repair_context=repair_context,
        schema_profile=profile,
    )
    if total_chars > budget and profile == "deepseek_compact":
        schema_card, schema_diag = _ultra_compact_schema_card(original_schema_card, max_columns=2, max_table_role_hints=1)
        api_card, api_diag = _ultra_compact_api_card(original_api_card, max_query_params=1, keep_role_hints=False, omit_empty=True)
        total_chars = _semantic_ir_total_prompt_chars(
            user_prompt=budget_user_prompt,
            allowed_schema_card=schema_card,
            allowed_api_card=api_card,
            repair_context=repair_context,
            schema_profile=profile,
        )
    elif total_chars > budget and profile == "deepseek_ultra_compact":
        schema_card, schema_diag = _ultra_compact_schema_card(original_schema_card, max_columns=1, max_table_role_hints=0)
        api_card, api_diag = _ultra_compact_api_card(original_api_card, max_query_params=0, keep_role_hints=False, omit_empty=True)
        total_chars = _semantic_ir_total_prompt_chars(
            user_prompt=budget_user_prompt,
            allowed_schema_card=schema_card,
            allowed_api_card=api_card,
            repair_context=repair_context,
            schema_profile=profile,
        )
    elif total_chars > budget:
        schema_budget, api_budget = _card_budgets_for_total(budget)
        schema_card, schema_diag = _compact_schema_card(original_schema_card, max(5000, int(schema_budget * 0.76)))
        api_card, api_diag = _compact_api_card(original_api_card, max(3500, int(api_budget * 0.72)))
        total_chars = _semantic_ir_total_prompt_chars(
            user_prompt=budget_user_prompt,
            allowed_schema_card=schema_card,
            allowed_api_card=api_card,
            repair_context=repair_context,
            schema_profile=profile,
        )
    if total_chars > budget and not _is_compact_schema_profile(profile):
        schema_card, schema_diag = _compact_schema_card(original_schema_card, max(3800, int(schema_budget * 0.58)), aggressive=True)
        api_card, api_diag = _compact_api_card(original_api_card, max(2600, int(api_budget * 0.52)), aggressive=True)
        total_chars = _semantic_ir_total_prompt_chars(
            user_prompt=budget_user_prompt,
            allowed_schema_card=schema_card,
            allowed_api_card=api_card,
            repair_context=repair_context,
            schema_profile=profile,
        )
    if total_chars > budget:
        schema_card, schema_diag = _ultra_compact_schema_card(original_schema_card)
        api_card, api_diag = _ultra_compact_api_card(original_api_card)
        total_chars = _semantic_ir_total_prompt_chars(
            user_prompt=budget_user_prompt,
            allowed_schema_card=schema_card,
            allowed_api_card=api_card,
            repair_context=repair_context,
            schema_profile=profile,
        )
    if total_chars > budget:
        schema_card, schema_diag = _ultra_compact_schema_card(original_schema_card, max_columns=2, max_table_role_hints=1)
        api_card, api_diag = _ultra_compact_api_card(original_api_card)
        total_chars = _semantic_ir_total_prompt_chars(
            user_prompt=budget_user_prompt,
            allowed_schema_card=schema_card,
            allowed_api_card=api_card,
            repair_context=repair_context,
            schema_profile=profile,
        )
    if total_chars > budget:
        schema_card, schema_diag = _ultra_compact_schema_card(original_schema_card, max_columns=1, max_table_role_hints=0)
        api_card, api_diag = _ultra_compact_api_card(
            original_api_card,
            max_query_params=0,
            keep_role_hints=False,
            omit_empty=_is_compact_schema_profile(profile),
        )
        total_chars = _semantic_ir_total_prompt_chars(
            user_prompt=budget_user_prompt,
            allowed_schema_card=schema_card,
            allowed_api_card=api_card,
            repair_context=repair_context,
            schema_profile=profile,
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
                schema_profile=profile,
            )
        ),
        "semantic_ir_prompt_system_chars": len(_semantic_ir_system_prompt(schema_profile=profile)),
        "semantic_ir_tool_schema_chars": len(json.dumps(semantic_ir_tool_schema(profile), ensure_ascii=False, sort_keys=True, separators=(",", ":"))),
        "planner_schema_profile": profile,
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
    planner_profile: str | None = None,
) -> WeakProtocolResult:
    started = time.perf_counter()
    schema_profile = _planner_schema_profile(client)
    active_planner_profile = _planner_profile(client, override=planner_profile)
    _force_planner_stage_client_timeout(client, _planner_model_timeout_sec(client))
    schema_card, api_card, context_diagnostics = _build_semantic_ir_prompt_context(
        schema_context,
        endpoint_context,
        user_prompt=user_prompt,
        repair_context=repair_context,
        schema_profile=schema_profile,
    )
    validator = SemanticIRValidator(schema_card, api_card)
    diagnostics: dict[str, Any] = _base_diagnostics()
    diagnostics.update(context_diagnostics)
    diagnostics.update(
        {
            "planner_schema_profile": schema_profile,
            "planner_profile": active_planner_profile,
            "planner_retry_used": False,
            "planner_retry_reason": None,
            "planner_tool_choice": _planner_tool_choice_label(_planner_tool_choice(active_planner_profile)),
            "planner_tool_names": [_tool_schema_name(tool) for tool in _planner_tools(schema_profile, active_planner_profile)],
            "planner_model_timeout_sec": _planner_model_timeout_sec(client),
            "planner_extra_body_keys": sorted(_planner_extra_body(schema_profile).keys()),
            "planner_finish_reason": None,
            "planner_tool_calls_count": 0,
            "semantic_ir_tool_schema_chars": _planner_tools_schema_chars(schema_profile, active_planner_profile),
        }
    )
    raw_previews: dict[str, Any] = {}

    result, call_error = _call_semantic_ir_tool(
        client,
        system_prompt=_semantic_ir_system_prompt(schema_profile=schema_profile, planner_profile=active_planner_profile),
        user_prompt=_semantic_ir_user_prompt(
            user_prompt=user_prompt,
            allowed_schema_card=schema_card,
            allowed_api_card=api_card,
            repair_context=repair_context,
            schema_profile=schema_profile,
            planner_profile=active_planner_profile,
        ),
        schema_profile=schema_profile,
        planner_profile=active_planner_profile,
    )
    diagnostics["semantic_ir_provider_latency_ms"] = _elapsed_ms(started)
    _record_planner_call_metadata(diagnostics, result)
    raw_previews["semantic_ir_initial"] = compact_preview(result or call_error, 1200)
    if call_error and _is_timeout_error(call_error):
        diagnostics.update(
            {
                "planner_retry_used": True,
                "planner_retry_reason": "initial_planner_timeout",
                "planner_timeout": True,
                "planner_schema_profile": "deepseek_ultra_compact",
            }
        )
        retry_schema_card, retry_api_card, retry_context_diag = _build_semantic_ir_prompt_context(
            schema_context,
            endpoint_context,
            user_prompt=user_prompt,
            repair_context=repair_context,
            schema_profile="deepseek_ultra_compact",
            max_total_chars=10500,
        )
        schema_card = retry_schema_card
        api_card = retry_api_card
        validator = SemanticIRValidator(schema_card, api_card)
        diagnostics.update(retry_context_diag)
        retry_started = time.perf_counter()
        result, call_error = _call_semantic_ir_tool(
            client,
            system_prompt=_semantic_ir_system_prompt(schema_profile="deepseek_ultra_compact", planner_profile=active_planner_profile),
            user_prompt=_semantic_ir_user_prompt(
                user_prompt=user_prompt,
                allowed_schema_card=schema_card,
                allowed_api_card=api_card,
                repair_context={
                    **(repair_context or {}),
                    "retry_reason": "initial_planner_timeout",
                    "instruction": "Submit exactly one compact Semantic IR tool call now.",
                },
                schema_profile="deepseek_ultra_compact",
                planner_profile=active_planner_profile,
            ),
            schema_profile="deepseek_ultra_compact",
            planner_profile=active_planner_profile,
        )
        diagnostics["semantic_ir_repair_latency_ms"] = diagnostics.get("semantic_ir_repair_latency_ms", 0) + _elapsed_ms(retry_started)
        diagnostics["semantic_ir_provider_latency_ms"] = _elapsed_ms(started)
        _record_planner_call_metadata(diagnostics, result)
        raw_previews["semantic_ir_initial_timeout_retry"] = compact_preview(result or call_error, 1200)
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

    tool_args = _extract_semantic_ir_tool_arguments(result, active_planner_profile)
    if tool_args is None:
        legacy_payload = _extract_legacy_planner_payload(result)
        if legacy_payload is not None and fallback_to_atomic:
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
        if active_planner_profile == PLANNER_PROFILE_DEEPSEEK_MICRO_TOOLS:
            diagnostics.update(
                {
                    "semantic_ir_repair_attempted": True,
                    "planner_retry_used": True,
                    "planner_retry_reason": "micro_missing_toolcall_json_tool_retry",
                }
            )
            json_retry_started = time.perf_counter()
            json_retry_result, json_retry_error = _call_semantic_ir_tool(
                client,
                system_prompt=_semantic_ir_repair_system_prompt(PLANNER_PROFILE_DEEPSEEK_JSON_TOOL),
                user_prompt=_semantic_ir_missing_toolcall_retry_user_prompt(
                    user_prompt=user_prompt,
                    previous_result=result,
                    allowed_schema_card=schema_card,
                    allowed_api_card=api_card,
                    planner_profile=PLANNER_PROFILE_DEEPSEEK_JSON_TOOL,
                ),
                schema_profile=str(diagnostics.get("planner_schema_profile") or schema_profile),
                planner_profile=PLANNER_PROFILE_DEEPSEEK_JSON_TOOL,
            )
            diagnostics["semantic_ir_provider_latency_ms"] = _elapsed_ms(started)
            diagnostics["semantic_ir_repair_latency_ms"] = _elapsed_ms(json_retry_started)
            raw_previews["semantic_ir_json_tool_retry"] = compact_preview(json_retry_result or json_retry_error, 1200)
            _record_planner_call_metadata(diagnostics, json_retry_result)
            json_retry_args = _extract_semantic_ir_tool_arguments(json_retry_result, PLANNER_PROFILE_DEEPSEEK_JSON_TOOL) if not json_retry_error else None
            if json_retry_args is not None:
                tool_args = json_retry_args
                active_planner_profile = PLANNER_PROFILE_DEEPSEEK_JSON_TOOL
        if tool_args is not None:
            pass
        else:
            diagnostics["semantic_ir_repair_attempted"] = True
            repair_started = time.perf_counter()
            repair_result, repair_error = _call_semantic_ir_tool(
                client,
                system_prompt=_semantic_ir_repair_system_prompt(active_planner_profile),
                user_prompt=_semantic_ir_missing_toolcall_retry_user_prompt(
                    user_prompt=user_prompt,
                    previous_result=result,
                    allowed_schema_card=schema_card,
                    allowed_api_card=api_card,
                    planner_profile=active_planner_profile,
                ),
                schema_profile=str(diagnostics.get("planner_schema_profile") or schema_profile),
                planner_profile=active_planner_profile,
            )
            diagnostics["semantic_ir_provider_latency_ms"] = _elapsed_ms(started)
            diagnostics["semantic_ir_repair_latency_ms"] = diagnostics.get("semantic_ir_repair_latency_ms", 0) + _elapsed_ms(repair_started)
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
            retry_args = _extract_semantic_ir_tool_arguments(repair_result, active_planner_profile)
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
    parsed_plan, validation = _parse_validate(tool_args, validator, require_answer_contract=False)
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
    diagnostics.update(_schema_alias_binding_diagnostics(parsed_plan))
    parsed_plan, validation = _ensure_answer_contract(
        client=client,
        user_prompt=user_prompt,
        parsed_plan=parsed_plan,
        validation=validation,
        diagnostics=diagnostics,
        raw_previews=raw_previews,
        schema_card=schema_card,
        api_card=api_card,
    )
    parsed_plan, validation = _ensure_schema_binding(
        client=client,
        user_prompt=user_prompt,
        parsed_plan=parsed_plan,
        validation=validation,
        diagnostics=diagnostics,
        raw_previews=raw_previews,
        schema_card=schema_card,
        validator=validator,
    )
    diagnostics.update(
        {
            "semantic_ir_validation_passed": validation.passed,
            "semantic_ir_validation_error_type": validation.error_type,
            "semantic_ir_validation_error_message": validation.error_message,
            "semantic_ir_task_count": len(parsed_plan.tasks) if parsed_plan else 0,
        }
    )
    if diagnostics.get("semantic_ir_repair_attempted") and validation.passed:
        diagnostics["semantic_ir_repair_success"] = True
    if parsed_plan is None or not validation.passed:
        diagnostics["semantic_ir_repair_attempted"] = True
        if validation.error_type == "invalid_semantic_alias":
            diagnostics["semantic_alias_repair_attempted"] = True
        if validation.error_type in ANSWER_CONTRACT_VALIDATION_ERROR_TYPES:
            diagnostics["semantic_ir_repair_attempted"] = False
            return _failed_semantic_ir_result(
                diagnostics,
                raw_previews,
                reason=validation.error_message or "Answer contract validation failed after secondary call.",
                started=started,
            )
        repair_started = time.perf_counter()
        repair_result, repair_error = _call_semantic_ir_tool(
            client,
            system_prompt=_semantic_ir_repair_system_prompt(active_planner_profile),
            user_prompt=_semantic_ir_repair_user_prompt(
                user_prompt=user_prompt,
                previous_args=tool_args,
                validation=validation,
                allowed_schema_card=schema_card,
                allowed_api_card=api_card,
                planner_profile=active_planner_profile,
            ),
            schema_profile=str(diagnostics.get("planner_schema_profile") or schema_profile),
            planner_profile=active_planner_profile,
        )
        diagnostics["semantic_ir_provider_latency_ms"] = _elapsed_ms(started)
        diagnostics["semantic_ir_repair_latency_ms"] = _elapsed_ms(repair_started)
        raw_previews["semantic_ir_repair"] = compact_preview(repair_result or repair_error, 1200)
        if repair_error:
            diagnostics["semantic_ir_repair_success"] = False
            return _failed_semantic_ir_result(diagnostics, raw_previews, reason=repair_error, started=started)
        repair_args = _extract_semantic_ir_tool_arguments(repair_result, active_planner_profile)
        if repair_args is None:
            diagnostics["semantic_ir_repair_success"] = False
            return _failed_semantic_ir_result(
                diagnostics,
                raw_previews,
                reason="Semantic IR repair did not return submit_semantic_ir_plan tool call.",
                started=started,
            )
        validation_started = time.perf_counter()
        parsed_plan, validation = _parse_validate(repair_args, validator, require_answer_contract=False)
        diagnostics["semantic_ir_validation_latency_ms"] = diagnostics.get("semantic_ir_validation_latency_ms", 0) + _elapsed_ms(validation_started)
        diagnostics.update(
            {
                "semantic_ir_validation_passed": validation.passed,
                "semantic_ir_task_count": len(parsed_plan.tasks) if parsed_plan else 0,
                "semantic_alias_validation_used": validation.semantic_alias_validation_used,
                "semantic_alias_validation_passed": validation.semantic_alias_validation_passed,
                "semantic_alias_count": validation.semantic_alias_count,
                "semantic_alias_error_type": validation.error_type if validation.error_type == "invalid_semantic_alias" else diagnostics.get("semantic_alias_error_type"),
            }
        )
        diagnostics.update(_schema_alias_binding_diagnostics(parsed_plan))
        parsed_plan, validation = _ensure_answer_contract(
            client=client,
            user_prompt=user_prompt,
            parsed_plan=parsed_plan,
            validation=validation,
            diagnostics=diagnostics,
            raw_previews=raw_previews,
            schema_card=schema_card,
            api_card=api_card,
        )
        parsed_plan, validation = _ensure_schema_binding(
            client=client,
            user_prompt=user_prompt,
            parsed_plan=parsed_plan,
            validation=validation,
            diagnostics=diagnostics,
            raw_previews=raw_previews,
            schema_card=schema_card,
            validator=validator,
        )
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

    support_started = time.perf_counter()
    support_result = check_semantic_ir_support(parsed_plan, schema_card, api_card, user_prompt=user_prompt)
    diagnostics["semantic_ir_support_check_latency_ms"] = _elapsed_ms(support_started)
    _record_support_result(diagnostics, support_result)
    if not support_result.supported:
        diagnostics["semantic_ir_support_repair_attempted"] = True
        support_repair_started = time.perf_counter()
        support_repair_result, support_repair_error = _call_semantic_ir_tool(
            client,
            system_prompt=_semantic_ir_support_repair_system_prompt(active_planner_profile),
            user_prompt=_semantic_ir_support_repair_user_prompt(
                user_prompt=user_prompt,
                previous_args=semantic_plan_to_dict(parsed_plan),
                support_result=support_result,
                allowed_schema_card=schema_card,
                allowed_api_card=api_card,
                planner_profile=active_planner_profile,
            ),
            schema_profile=str(diagnostics.get("planner_schema_profile") or schema_profile),
            planner_profile=active_planner_profile,
        )
        diagnostics["semantic_ir_provider_latency_ms"] = _elapsed_ms(started)
        diagnostics["semantic_ir_support_repair_latency_ms"] = _elapsed_ms(support_repair_started)
        raw_previews["semantic_ir_support_repair"] = compact_preview(support_repair_result or support_repair_error, 1200)
        if support_repair_error:
            diagnostics["semantic_ir_support_repair_success"] = False
            diagnostics["semantic_ir_support_repair_error_message"] = support_repair_error
            return _failed_semantic_ir_result(diagnostics, raw_previews, reason=support_repair_error, started=started)
        support_repair_args = _extract_semantic_ir_tool_arguments(support_repair_result, active_planner_profile)
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
        repaired_plan, repaired_validation = _parse_validate(support_repair_args, validator, require_answer_contract=False)
        diagnostics["semantic_ir_validation_latency_ms"] = diagnostics.get("semantic_ir_validation_latency_ms", 0) + _elapsed_ms(validation_started)
        diagnostics.update(
            {
                "semantic_ir_validation_passed": repaired_validation.passed,
                "semantic_ir_validation_error_type": repaired_validation.error_type,
                "semantic_ir_validation_error_message": repaired_validation.error_message,
                "semantic_ir_task_count": len(repaired_plan.tasks) if repaired_plan else 0,
                "semantic_alias_validation_used": repaired_validation.semantic_alias_validation_used,
                "semantic_alias_validation_passed": repaired_validation.semantic_alias_validation_passed,
                "semantic_alias_count": repaired_validation.semantic_alias_count,
                "semantic_alias_error_type": repaired_validation.error_type if repaired_validation.error_type == "invalid_semantic_alias" else diagnostics.get("semantic_alias_error_type"),
            }
        )
        diagnostics.update(_schema_alias_binding_diagnostics(repaired_plan))
        repaired_plan, repaired_validation = _ensure_answer_contract(
            client=client,
            user_prompt=user_prompt,
            parsed_plan=repaired_plan,
            validation=repaired_validation,
            diagnostics=diagnostics,
            raw_previews=raw_previews,
            schema_card=schema_card,
            api_card=api_card,
        )
        repaired_plan, repaired_validation = _ensure_schema_binding(
            client=client,
            user_prompt=user_prompt,
            parsed_plan=repaired_plan,
            validation=repaired_validation,
            diagnostics=diagnostics,
            raw_previews=raw_previews,
            schema_card=schema_card,
            validator=validator,
        )
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
        repaired_support = check_semantic_ir_support(repaired_plan, schema_card, api_card, user_prompt=user_prompt)
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
    schema_binding_toolcall_enabled = _schema_binding_toolcall_enabled()
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
        "answer_contract_validation_used": False,
        "answer_contract_validation_passed": None,
        "answer_contract_repair_attempted": False,
        "answer_contract_error_type": None,
        "answer_contract_missing_initially": False,
        "answer_contract_secondary_call_used": False,
        "answer_contract_secondary_call_success": False,
        "answer_contract_secondary_error": None,
        "answer_contract_secondary_error_type": None,
        "answer_contract_secondary_call_latency_ms": 0,
        "backend_answer_contract_inference_used": False,
        "required_slot_count": 0,
        "schema_binding_enabled": True,
        "schema_binding_toolcall_enabled": schema_binding_toolcall_enabled,
        "schema_binding_mode": "experimental_toolcall" if schema_binding_toolcall_enabled else "repair_hint_only",
        "schema_binding_used": False,
        "schema_binding_count": 0,
        "schema_binding_ids": [],
        "schema_binding_validation_passed": None,
        "schema_binding_error_type": None,
        "schema_binding_error_message": None,
        "schema_binding_repair_attempted": False,
        "schema_binding_repair_success": False,
        "schema_binding_call_latency_ms": 0,
        "backend_schema_binding_inference_used": False,
        "schema_alias_binding_used": False,
        "schema_alias_binding_count": 0,
        "schema_alias_bindings": [],
    }


def _schema_alias_binding_diagnostics(plan: SemanticIRPlan | None) -> dict[str, Any]:
    bindings = list(getattr(plan, "schema_alias_bindings", []) or []) if plan is not None else []
    return {
        "schema_alias_binding_used": bool(bindings),
        "schema_alias_binding_count": len(bindings),
        "schema_alias_bindings": bindings,
    }


def _planner_model_timeout_sec(client: Any | None = None) -> int:
    for name in ["HERMES_V2_PLANNER_MODEL_TIMEOUT_SEC", "HERMES_LLM_CALL_TIMEOUT_SEC", "LLM_TIMEOUT_SECONDS"]:
        raw = os.getenv(name)
        if not raw:
            continue
        try:
            value = int(raw)
        except Exception:
            continue
        if value > 0:
            return min(value, 60)
    profile = _planner_schema_profile(client)
    return 45 if _is_compact_schema_profile(profile) else 60


def _planner_max_tokens(schema_profile: str | None) -> int:
    raw = os.getenv("HERMES_V2_PLANNER_MAX_TOKENS") or os.getenv("LLM_MAX_TOKENS")
    if raw:
        try:
            value = int(raw)
            if value > 0:
                return value
        except Exception:
            pass
    profile = str(schema_profile or "").strip().lower()
    if profile == "deepseek_ultra_compact":
        return 384
    if _is_compact_schema_profile(profile):
        return 512
    return 1536


def _planner_extra_body(schema_profile: str | None) -> dict[str, Any]:
    raw = os.getenv("HERMES_V2_PLANNER_EXTRA_BODY_JSON") or os.getenv("OPENAI_EXTRA_BODY_JSON")
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
    if _is_compact_schema_profile(schema_profile):
        return {"chat_template_kwargs": {"enable_thinking": False}}
    return {}


def _force_planner_stage_client_timeout(client: Any, timeout_sec: int) -> None:
    if timeout_sec <= 0:
        return
    if hasattr(client, "timeout_seconds"):
        try:
            setattr(client, "timeout_seconds", timeout_sec)
        except Exception:
            pass
    if hasattr(client, "_sdk_client"):
        try:
            setattr(client, "_sdk_client", None)
        except Exception:
            pass


def _call_semantic_ir_tool(
    client: Any,
    *,
    system_prompt: str,
    user_prompt: str,
    schema_profile: str | None = None,
    planner_profile: str | None = None,
) -> tuple[dict[str, Any], str | None]:
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
    profile = _planner_profile(client, override=planner_profile)
    tool_choice = _planner_tool_choice(profile)
    tool_schemas = _planner_tools(schema_profile, profile)
    timeout_sec = _planner_model_timeout_sec(client)
    try:
        with _temporary_client_timeout(client, timeout_sec):
            result = _run_with_alarm(
                lambda: client.generate_messages(
                    messages,
                    tools=tool_schemas,
                    tool_choice=tool_choice,
                    parallel_tool_calls=False,
                    temperature=0,
                    max_tokens=_planner_max_tokens(schema_profile),
                    extra_body=_planner_extra_body(schema_profile),
                ),
                timeout_sec,
            )
    except TypeError:
        try:
            with _temporary_client_timeout(client, timeout_sec):
                result = _run_with_alarm(
                    lambda: client.generate_messages(
                        messages,
                        tools=tool_schemas,
                        tool_choice=tool_choice,
                        extra_body=_planner_extra_body(schema_profile),
                    ),
                    timeout_sec,
                )
        except Exception as exc:
            return {}, str(exc)
    except Exception as exc:
        return {}, str(exc)
    if not isinstance(result, dict):
        return {}, "LLM client returned non-dict response."
    if not result.get("ok", True):
        return result, str(result.get("error") or result.get("reason") or "LLM client returned failure.")
    return result, None


class _temporary_client_timeout:
    def __init__(self, client: Any, timeout_sec: int) -> None:
        self.client = client
        self.timeout_sec = timeout_sec
        self.old_timeout: Any = None
        self.had_timeout = False
        self.old_sdk_client: Any = None
        self.had_sdk_client = False

    def __enter__(self) -> None:
        if hasattr(self.client, "timeout_seconds"):
            self.had_timeout = True
            self.old_timeout = getattr(self.client, "timeout_seconds")
            try:
                setattr(self.client, "timeout_seconds", self.timeout_sec)
            except Exception:
                pass
        if hasattr(self.client, "_sdk_client"):
            self.had_sdk_client = True
            self.old_sdk_client = getattr(self.client, "_sdk_client")
            try:
                setattr(self.client, "_sdk_client", None)
            except Exception:
                pass

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.had_timeout:
            try:
                setattr(self.client, "timeout_seconds", self.old_timeout)
            except Exception:
                pass
        if self.had_sdk_client:
            try:
                setattr(self.client, "_sdk_client", self.old_sdk_client)
            except Exception:
                pass


def _run_with_alarm(callable_obj: Any, timeout_sec: int) -> Any:
    if timeout_sec <= 0 or threading.current_thread() is not threading.main_thread() or not hasattr(signal, "SIGALRM"):
        return callable_obj()
    previous_handler = signal.getsignal(signal.SIGALRM)

    def _handler(_signum, _frame):
        raise TimeoutError(f"semantic_ir_planner_timeout_after_{timeout_sec}s")

    try:
        signal.signal(signal.SIGALRM, _handler)
        signal.alarm(int(timeout_sec))
        return callable_obj()
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous_handler)


def _record_planner_call_metadata(diagnostics: dict[str, Any], result: dict[str, Any] | None) -> None:
    if not isinstance(result, dict):
        return
    tool_calls = result.get("tool_calls") or []
    first_tool = tool_calls[0] if tool_calls and isinstance(tool_calls[0], dict) else {}
    diagnostics["planner_finish_reason"] = result.get("finish_reason")
    diagnostics["planner_tool_calls_count"] = len(tool_calls)
    diagnostics["planner_tool_name"] = first_tool.get("name") or first_tool.get("tool") or (first_tool.get("function") or {}).get("name")
    diagnostics["planner_raw_text_content_present"] = bool(str(result.get("content") or "").strip())
    diagnostics["planner_model_timeout_sec"] = _planner_model_timeout_sec()


def _tool_schema_name(tool_schema: dict[str, Any]) -> str:
    try:
        return str((tool_schema.get("function") or {}).get("name") or "")
    except Exception:
        return ""


def _is_timeout_error(message: str | None) -> bool:
    text = str(message or "").lower()
    return "timeout" in text or "timed out" in text or "deadline" in text


def _extract_semantic_ir_tool_arguments(result: dict[str, Any], planner_profile: str | None = None) -> dict[str, Any] | None:
    profile = _normalize_planner_profile(planner_profile)
    for call in result.get("tool_calls") or []:
        if not isinstance(call, dict):
            continue
        name = call.get("name") or call.get("tool") or (call.get("function") or {}).get("name")
        if profile == PLANNER_PROFILE_DEEPSEEK_JSON_TOOL and name == SEMANTIC_IR_JSON_TOOL_NAME:
            args = _tool_call_arguments(call)
            return _normalize_json_tool_arguments(args)
        if profile == PLANNER_PROFILE_DEEPSEEK_MICRO_TOOLS and name in MICRO_TOOL_NAMES:
            args = _tool_call_arguments(call)
            return _normalize_micro_tool_arguments(name, args)
        if name != SEMANTIC_IR_TOOL_NAME:
            continue
        return _tool_call_arguments(call)
    return None


def _tool_call_arguments(call: dict[str, Any]) -> dict[str, Any]:
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
    return {}


def _normalize_json_tool_arguments(args: dict[str, Any]) -> dict[str, Any]:
    raw = args.get("semantic_ir_json")
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        return {"_raw": json.dumps(args, default=str)}
    try:
        parsed = json.loads(raw)
    except Exception:
        return {"_raw": raw}
    return parsed if isinstance(parsed, dict) else {"_raw": raw}


def _normalize_micro_tool_arguments(tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    task_id = str(args.get("task_id") or "t1").strip() or "t1"
    description = str(args.get("description") or "").strip() or "LLM-owned Semantic IR task."
    aggregation_instruction = str(args.get("aggregation_instruction") or "").strip() or "Answer from runtime evidence only."
    answer_contract = args.get("answer_contract") if isinstance(args.get("answer_contract"), dict) else None
    if tool_name == MICRO_DIRECT_TOOL_NAME:
        direct_answer = str(args.get("direct_answer") or "").strip() or None
        return {
            "route": "DIRECT",
            "direct_answer": direct_answer,
            "tasks": [
                {
                    "task_id": task_id,
                    "kind": "CONCEPT",
                    "operation": "EXPLAIN",
                    "source": "NONE",
                    "local_query": None,
                    "api_query": None,
                    "depends_on": [],
                    "description": description,
                    "required": bool(args.get("required", True)),
                }
            ],
            "aggregation_instruction": aggregation_instruction if aggregation_instruction != "Answer from runtime evidence only." else "Return the direct answer.",
        }
    if tool_name == MICRO_LOCAL_COUNT_TOOL_NAME:
        return _micro_evidence_payload(
            task={
                "task_id": task_id,
                "kind": "LOCAL_QUERY",
                "operation": "COUNT",
                "source": "LOCAL_SNAPSHOT",
                "local_query": {
                    "table": str(args.get("table") or "").strip(),
                    "fields": [],
                    "filters": _safe_list(args.get("filters")),
                    "limit": None,
                    "count": True,
                },
                "api_query": None,
                "depends_on": [],
                "description": description,
                "required": bool(args.get("required", True)),
            },
            aggregation_instruction=aggregation_instruction,
            answer_contract=answer_contract,
        )
    if tool_name in {MICRO_LOCAL_QUERY_TOOL_NAME, MICRO_LOCAL_LOOKUP_TOOL_NAME}:
        if isinstance(args.get("local_query"), dict):
            local_query = dict(args["local_query"])
        else:
            local_query = {
                "table": str(args.get("table") or "").strip(),
                "fields": _safe_str_list(args.get("fields")),
                "filters": _safe_list(args.get("filters")),
                "limit": args.get("limit", 50),
                "count": False,
            }
        operation = str(args.get("operation") or ("LOOKUP" if tool_name == MICRO_LOCAL_LOOKUP_TOOL_NAME else "LIST")).strip().upper()
        return _micro_evidence_payload(
            task={
                "task_id": task_id,
                "kind": "LOCAL_QUERY",
                "operation": operation,
                "source": "LOCAL_SNAPSHOT",
                "local_query": local_query,
                "api_query": None,
                "depends_on": [],
                "description": description,
                "required": bool(args.get("required", True)),
            },
            aggregation_instruction=aggregation_instruction,
            answer_contract=answer_contract,
        )
    if tool_name == MICRO_API_TOOL_NAME:
        api_query = dict(args.get("api_query") or {})
        operation = str(args.get("operation") or "LIST").strip().upper()
        return _micro_evidence_payload(
            task={
                "task_id": task_id,
                "kind": "LIVE_QUERY",
                "operation": operation,
                "source": "LIVE_API",
                "local_query": None,
                "api_query": api_query,
                "depends_on": [],
                "description": description,
                "required": bool(args.get("required", True)),
            },
            aggregation_instruction=aggregation_instruction,
            answer_contract=answer_contract,
        )
    if tool_name == MICRO_MIXED_TOOL_NAME:
        return {
            "route": "EVIDENCE",
            "direct_answer": args.get("direct_answer"),
            "tasks": _safe_list(args.get("tasks")),
            "answer_contract": answer_contract,
            "aggregation_instruction": aggregation_instruction,
        }
    return {"_raw": json.dumps(args, default=str)}


def _micro_evidence_payload(*, task: dict[str, Any], aggregation_instruction: str, answer_contract: dict[str, Any] | None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "route": "EVIDENCE",
        "direct_answer": None,
        "tasks": [task],
        "aggregation_instruction": aggregation_instruction,
    }
    if answer_contract is not None:
        payload["answer_contract"] = answer_contract
    return payload


def _safe_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _safe_str_list(value: Any) -> list[str]:
    return [str(item).strip() for item in _safe_list(value) if str(item).strip()]


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


def _parse_validate(
    tool_args: dict[str, Any],
    validator: SemanticIRValidator,
    *,
    require_answer_contract: bool = True,
) -> tuple[SemanticIRPlan | None, SemanticIRValidationResult]:
    try:
        parsed_plan = parse_semantic_ir_from_json_or_line_protocol(tool_args)
    except Exception as exc:
        return None, SemanticIRValidationResult(passed=False, error_type="parse_error", error_message=str(exc))
    bind_semantic_ir_schema_aliases(parsed_plan, validator.allowed_schema_card)
    return parsed_plan, validator.validate(parsed_plan, require_answer_contract=require_answer_contract)


def _answer_contract_validation(plan: SemanticIRPlan | None) -> SemanticIRValidationResult:
    if plan is None:
        return SemanticIRValidationResult(passed=False, error_type="parse_error", error_message="Semantic IR plan was not parsed.")
    result = AnswerContractValidator().validate(plan)
    if result.passed:
        return SemanticIRValidationResult(passed=True)
    return SemanticIRValidationResult(
        passed=False,
        error_type=result.error_type or "invalid_answer_contract",
        error_message=result.error_message or "Invalid answer contract.",
        task_id=result.task_id,
    )


def _record_contract_validation_diagnostics(
    diagnostics: dict[str, Any],
    *,
    plan: SemanticIRPlan | None,
    validation: SemanticIRValidationResult,
) -> None:
    diagnostics.update(
        {
            "answer_contract_validation_used": True,
            "answer_contract_validation_passed": validation.passed and validation.error_type not in ANSWER_CONTRACT_VALIDATION_ERROR_TYPES,
            "answer_contract_error_type": validation.error_type if validation.error_type in ANSWER_CONTRACT_VALIDATION_ERROR_TYPES else None,
            "required_slot_count": len(plan.answer_contract.required_slots) if plan and plan.answer_contract else 0,
        }
    )


def _ensure_answer_contract(
    *,
    client: Any,
    user_prompt: str,
    parsed_plan: SemanticIRPlan | None,
    validation: SemanticIRValidationResult,
    diagnostics: dict[str, Any],
    raw_previews: dict[str, Any],
    schema_card: list[dict[str, Any]],
    api_card: list[dict[str, Any]],
) -> tuple[SemanticIRPlan | None, SemanticIRValidationResult]:
    if parsed_plan is None or not validation.passed:
        return parsed_plan, validation
    if parsed_plan.route != "EVIDENCE":
        diagnostics["answer_contract_secondary_call_used"] = False
        diagnostics["answer_contract_missing_initially"] = False
        return parsed_plan, validation
    contract_validation = _answer_contract_validation(parsed_plan)
    _record_contract_validation_diagnostics(diagnostics, plan=parsed_plan, validation=contract_validation)
    if contract_validation.passed:
        diagnostics["answer_contract_secondary_call_used"] = False
        diagnostics["answer_contract_missing_initially"] = False
        return parsed_plan, validation

    diagnostics["answer_contract_missing_initially"] = parsed_plan.answer_contract is None
    diagnostics["answer_contract_repair_attempted"] = True
    contract_result = run_answer_contract_planner(
        client=client,
        user_prompt=user_prompt,
        semantic_plan=parsed_plan,
        allowed_schema_card=schema_card,
        allowed_api_card=api_card,
        validation_error=contract_validation,
    )
    diagnostics["answer_contract_secondary_call_latency_ms"] = contract_result.latency_ms
    if contract_result.diagnostics:
        diagnostics.update(contract_result.diagnostics)
    raw_previews["answer_contract_secondary"] = compact_preview(contract_result.raw_preview, 1200)
    if not contract_result.ok or contract_result.answer_contract is None:
        failed = SemanticIRValidationResult(
            passed=False,
            error_type=contract_result.error_type or "invalid_answer_contract",
            error_message=contract_result.error_message or "Answer contract secondary call failed.",
        )
        _record_contract_validation_diagnostics(diagnostics, plan=parsed_plan, validation=failed)
        return parsed_plan, failed

    parsed_plan.answer_contract = contract_result.answer_contract
    final_contract_validation = _answer_contract_validation(parsed_plan)
    _record_contract_validation_diagnostics(diagnostics, plan=parsed_plan, validation=final_contract_validation)
    if not final_contract_validation.passed:
        diagnostics["answer_contract_secondary_call_success"] = False
        return parsed_plan, final_contract_validation
    diagnostics["answer_contract_secondary_call_success"] = True
    return parsed_plan, validation


def _ensure_schema_binding(
    *,
    client: Any,
    user_prompt: str,
    parsed_plan: SemanticIRPlan | None,
    validation: SemanticIRValidationResult,
    diagnostics: dict[str, Any],
    raw_previews: dict[str, Any],
    schema_card: list[dict[str, Any]],
    validator: SemanticIRValidator,
) -> tuple[SemanticIRPlan | None, SemanticIRValidationResult]:
    if not _schema_binding_toolcall_enabled():
        needs_hint_binding = bool(parsed_plan is not None and _plan_needs_schema_binding(parsed_plan))
        diagnostics.update(
            {
                "schema_binding_enabled": True,
                "schema_binding_toolcall_enabled": False,
                "schema_binding_mode": "repair_hint_only",
                "schema_binding_used": needs_hint_binding,
                "schema_binding_validation_passed": None,
                "schema_binding_error_type": None,
                "schema_binding_error_message": None,
                "schema_binding_call_latency_ms": 0,
                "backend_schema_binding_inference_used": False,
            }
        )
        return parsed_plan, validation

    diagnostics.update({"schema_binding_enabled": True, "schema_binding_toolcall_enabled": True, "schema_binding_mode": "experimental_toolcall"})
    if parsed_plan is None or not validation.passed:
        return parsed_plan, validation
    if not _plan_needs_schema_binding(parsed_plan):
        diagnostics["schema_binding_used"] = False
        diagnostics["schema_binding_validation_passed"] = None
        return parsed_plan, validation

    if parsed_plan.schema_binding is not None:
        final_validation = validator.validate(parsed_plan, require_answer_contract=True)
        _record_schema_binding_validation_diagnostics(diagnostics, parsed_plan, final_validation)
        if final_validation.passed:
            return parsed_plan, final_validation

    binding_result = run_schema_binding_planner(
        client=client,
        user_prompt=user_prompt,
        semantic_plan=parsed_plan,
        answer_contract=parsed_plan.answer_contract,
        allowed_schema_card=schema_card,
        validation_error=validation,
    )
    diagnostics["schema_binding_call_latency_ms"] = binding_result.latency_ms
    if binding_result.diagnostics:
        diagnostics.update(binding_result.diagnostics)
    raw_previews["schema_binding"] = compact_preview(binding_result.raw_preview, 1200)
    if not binding_result.ok or binding_result.binding_plan is None:
        failed = SemanticIRValidationResult(
            passed=False,
            error_type=binding_result.error_type or "invalid_schema_binding",
            error_message=binding_result.error_message or "Schema binding planner failed.",
        )
        _record_schema_binding_validation_diagnostics(diagnostics, parsed_plan, failed)
        return parsed_plan, failed

    parsed_plan.schema_binding = binding_result.binding_plan
    final_validation = validator.validate(parsed_plan, require_answer_contract=True)
    _record_schema_binding_validation_diagnostics(diagnostics, parsed_plan, final_validation)
    return parsed_plan, final_validation


def _plan_needs_schema_binding(plan: SemanticIRPlan) -> bool:
    if plan.route != "EVIDENCE":
        return False
    for task in plan.tasks:
        if task.kind in {"LOCAL_QUERY", "LOCAL_AND_LIVE"} or task.local_query is not None:
            return True
    if plan.answer_contract is not None:
        for slot in [*plan.answer_contract.required_slots, *plan.answer_contract.optional_slots]:
            if slot.source_scope in {"LOCAL_SNAPSHOT", "BOTH"}:
                return True
    return False


def _record_schema_binding_validation_diagnostics(
    diagnostics: dict[str, Any],
    plan: SemanticIRPlan | None,
    validation: SemanticIRValidationResult,
) -> None:
    binding_plan = plan.schema_binding if plan is not None else None
    binding_error = validation.error_type if validation.error_type in SCHEMA_BINDING_VALIDATION_ERROR_TYPES else None
    diagnostics.update(
        {
            "schema_binding_used": bool(binding_plan),
            "schema_binding_count": len(binding_plan.bindings) if binding_plan else 0,
            "schema_binding_ids": [binding.binding_id for binding in binding_plan.bindings] if binding_plan else [],
            "schema_binding_validation_passed": validation.passed and binding_error is None,
            "schema_binding_error_type": binding_error,
            "schema_binding_error_message": validation.error_message if binding_error else None,
            "backend_schema_binding_inference_used": False,
        }
    )


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
    for key in ["primary_name_fields", "status_fields", "date_fields", "count_fields", "id_fields", "entity_lookup_fields", "label_fields"]:
        values = field_hints.get(key) if isinstance(field_hints, dict) else []
        if isinstance(values, list):
            prioritized = _prioritized_role_values(key, [str(value) for value in values])
            if key == "status_fields":
                prioritized = prioritized[:1]
            elif key == "date_fields":
                prioritized = prioritized[:2]
            priority.extend(prioritized)
    priority.extend(column for column in columns if any(token in column.lower() for token in ("id", "name", "status", "state", "date", "time", "published", "created", "updated")))
    out: list[str] = []
    seen: set[str] = set()
    for column in priority:
        if column not in columns or column in seen:
            continue
        seen.add(column)
        out.append(column)
    return out


def _prioritized_role_values(role: str, values: list[str]) -> list[str]:
    def score(value: str) -> tuple[int, str]:
        norm = value.lower().replace("_", "")
        if role == "primary_name_fields":
            if norm in {"name", "displayname", "title"}:
                return (0, norm)
            if "sandbox" in norm or "org" in norm:
                return (3, norm)
            return (1, norm)
        if role == "status_fields":
            if norm == "status":
                return (0, norm)
            if norm == "state":
                return (1, norm)
            return (2, norm)
        if role == "date_fields":
            if "updated" in norm:
                return (0, norm)
            if "deployed" in norm or "published" in norm:
                return (1, norm)
            if "created" in norm:
                return (2, norm)
            return (3, norm)
        if role == "id_fields":
            if norm in {"id", "blueprintid", "campaignid"}:
                return (0, norm)
            if "org" in norm or "client" in norm:
                return (3, norm)
            return (1, norm)
        return (0, norm)

    return sorted(values, key=score)


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


def _ultra_compact_schema_card(
    rows: list[dict[str, Any]],
    *,
    max_columns: int = 3,
    max_table_role_hints: int = 2,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for row in rows:
        columns = [str(item) for item in row.get("columns", []) if str(item)]
        field_hints = row.get("field_hints") if isinstance(row.get("field_hints"), dict) else {}
        priority = _schema_priority_columns(columns, field_hints)
        compact.append(
            {
                "table": row.get("table"),
                "columns": (priority or columns)[:max_columns],
                "table_role_hints": [str(value) for value in (row.get("table_role_hints") or [])[:max_table_role_hints]],
                "field_hints": {},
            }
        )
    return compact, {"truncated": True, "columns_truncated": True, "char_count": _json_char_count(compact)}


def _ultra_compact_api_card(
    rows: list[dict[str, Any]],
    *,
    max_query_params: int = 1,
    keep_role_hints: bool = False,
    omit_empty: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for row in rows:
        item: dict[str, Any] = {
            "endpoint_id": row.get("endpoint_id"),
            "method": row.get("method"),
            "path": row.get("path"),
        }
        path_params = [str(value) for value in (row.get("path_params") or [])[:1]]
        query_params = [str(value) for value in (row.get("query_params") or [])[:max_query_params]]
        role_hints = [str(value) for value in (row.get("endpoint_role_hints") or [])[:2]] if keep_role_hints else []
        if path_params or not omit_empty:
            item["path_params"] = path_params
        if query_params or not omit_empty:
            item["query_params"] = query_params
        if role_hints or not omit_empty:
            item["endpoint_role_hints"] = role_hints
        if not omit_empty:
            item.update({"common_params": {}, "domains": [], "examples": [], "description": ""})
        compact.append(item)
    return compact, {"truncated": True, "detail_truncated": True, "char_count": _json_char_count(compact)}


def _semantic_ir_total_prompt_chars(
    *,
    user_prompt: str,
    allowed_schema_card: list[dict[str, Any]],
    allowed_api_card: list[dict[str, Any]],
    repair_context: dict[str, Any] | None,
    schema_profile: str | None = None,
    planner_profile: str | None = None,
) -> int:
    return (
        len(_semantic_ir_system_prompt(schema_profile=schema_profile, planner_profile=planner_profile))
        + len(
            _semantic_ir_user_prompt(
                user_prompt=user_prompt,
                allowed_schema_card=allowed_schema_card,
                allowed_api_card=allowed_api_card,
                repair_context=repair_context,
                schema_profile=schema_profile,
                planner_profile=planner_profile,
            )
        )
        + _planner_tools_schema_chars(schema_profile, planner_profile)
    )


def _json_char_count(value: Any) -> int:
    return len(json.dumps(redact_secrets(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def _semantic_ir_system_prompt(*, schema_profile: str | None = None, planner_profile: str | None = None) -> str:
    compact = _is_compact_schema_profile(schema_profile)
    tool_instruction = _profile_tool_system_instruction(planner_profile)
    base = (
        "You are the single Unified LLM Planner facade for DASHSys V2. SDK toolcall Semantic IR is the primary internal planning contract. "
        f"{tool_instruction} Do not answer in text. "
        "You own DIRECT vs EVIDENCE routing, task semantics, source, operation, selected table/endpoint IDs, fields, filters, values, dependencies, and aggregation instruction. "
        "You also own the answer_contract for EVIDENCE: it declares required final-answer slots and which tasks satisfy each slot. "
        "Use DIRECT only for pure concept, pure meta-language, or out-of-domain prompts needing no local or live evidence. "
        "Use EVIDENCE for user-specific, local snapshot, live/current/platform/API, list/count/status/date/lookup/compare, mixed concept plus data, or ambiguous data-like prompts. "
        "Choose table and field names only from AllowedLocalSchemaCard and endpoints only from AllowedAPIContextCard. "
        "The backend validates existence and mechanically compiles the IR; it will not choose replacements."
    )
    if compact:
        return (
            base
            + " Keep arguments compact and include only required fields plus answer_contract when route is EVIDENCE. "
            "Do not reason in text. Do not think step by step. Emit the tool call immediately."
        )
    return base


def _profile_tool_system_instruction(planner_profile: str | None) -> str:
    profile = _normalize_planner_profile(planner_profile)
    if profile == PLANNER_PROFILE_DEEPSEEK_JSON_TOOL:
        return "You must call the submit_semantic_ir_json SDK tool exactly once with semantic_ir_json containing the Semantic IR JSON."
    if profile == PLANNER_PROFILE_DEEPSEEK_MICRO_TOOLS:
        return "You must call exactly one of the provided Semantic IR SDK tools; use submit_mixed_evidence_plan for mixed or multi-task prompts."
    return "You must call the submit_semantic_ir_plan SDK tool exactly once."


def _semantic_ir_user_prompt(
    *,
    user_prompt: str,
    allowed_schema_card: list[dict[str, Any]],
    allowed_api_card: list[dict[str, Any]],
    repair_context: dict[str, Any] | None,
    schema_profile: str | None = None,
    planner_profile: str | None = None,
) -> str:
    profile = _normalize_planner_profile(planner_profile)
    tool_rule = _profile_tool_user_rule(profile)
    binding_rules = []
    if _schema_binding_toolcall_enabled():
        binding_rules = [
            "Experimental schema binding is enabled: if you know a binding ID from repair context, put it on task.binding_id and local_query.binding_id.",
            "Backend may reject conflicts between binding_id and local_query table/fields, but it will not substitute a table or field for you.",
        ]
    if _is_compact_schema_profile(schema_profile):
        profile_rules = _profile_specific_user_rules(profile)
        payload = {
            "task": "SUBMIT_DASHSYS_V2_SEMANTIC_IR",
            "user_prompt": user_prompt,
            "AllowedLocalSchemaCard": allowed_schema_card,
            "AllowedAPIContextCard": allowed_api_card,
            "rules": [
                tool_rule,
                "DIRECT only for pure concept/meta/out-of-domain with no runtime data; include one CONCEPT task and direct_answer.",
                "Use EVIDENCE for user/local/live/list/count/status/date/lookup/compare/mixed/ambiguous-data prompts.",
                "Choose only listed table, field, and endpoint IDs; backend validates and compiles only.",
                "Local count: LOCAL_QUERY COUNT count=true over a snapshot_record_table, not bridge/relationship rows.",
                "Bare 'schemas do I have/my/show/list' without live/API: LOCAL_QUERY on schema/blueprint/xdm_schema table hints.",
                "Published/date without live/API: LOCAL_QUERY DATE/LOOKUP using listed date_fields/columns.",
                "Inactive/status without enum proof: do not invent INACTIVE; select NAME plus STATUS/STATE rows.",
                "Mixed concept+data: CONCEPT plus LOCAL_QUERY unless live/API is explicit.",
                "Compare local/live: include LOCAL_QUERY and LIVE_QUERY when both are needed.",
                "EVIDENCE requires answer_contract with required_slots, source_scope, satisfied_by_tasks, required_fields, zero_rows_semantics, if_missing.",
                *profile_rules,
                "Do not ask backend to write SQL, infer tables/fields/endpoints, or repair semantics.",
                *binding_rules,
            ],
            "repair_context": redact_secrets(repair_context) if repair_context else None,
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    payload = {
        "task": "SUBMIT_DASHSYS_V2_SEMANTIC_IR",
        "user_prompt": user_prompt,
        "AllowedLocalSchemaCard": allowed_schema_card,
        "AllowedAPIContextCard": allowed_api_card,
        "rules": [
            tool_rule,
            "No plan in message content.",
            "EVIDENCE tasks must be submitted through the SDK tool call, never as plain text or message content.",
            "DIRECT prompts must also be submitted through the SDK tool call.",
            "LLM owns route, task semantics, source, table, fields, filters, endpoint, dependencies, and aggregation.",
            *binding_rules,
            "Do not invent tables, columns, endpoint IDs, filters, or fields.",
            "DIRECT route: include one non-executable CONCEPT task with source NONE, null local_query/api_query, and a concise direct_answer; pure no-evidence concept/meta only.",
            "EVIDENCE route: tasks contain LLM-owned evidence tasks.",
            "Every EVIDENCE plan needs root answer_contract with v1, style/scope, required_slots, optional_slots.",
            "Required slots name slot_id, type, source_scope, satisfied_by_tasks, fields, zero_rows_semantics, if_missing.",
            "DIRECT route uses empty/NONE answer_contract or NONE-scope CONCEPT slot.",
            "answer_contract is a slot checklist, not evidence or final answer.",
            "Use DATE/RELATION/COUNT/LIST/COMPARISON slots for date, mapping, count, list, and local/live prompts; use zero_rows_semantics and if_missing to force scoped caveats.",
            "Never allow positive relation/list/status/date assertions from zero rows or missing fields.",
            "Prefer supported Semantic IR operations whenever they can express the requested evidence.",
            "Use LIST/COUNT/LOOKUP/STATUS/DATE LocalQueryIR operations for simple local snapshot requests.",
            "raw SQL fallback is an escape hatch only when required LOCAL_SNAPSHOT evidence cannot be represented by supported Semantic IR.",
            "Do not ask the backend to write SQL, infer SQL, choose SQL tables, choose SQL fields, or repair SQL for you.",
            "If unsupported JOIN/GROUP/window local SQL is truly required, set requires_raw_sql_fallback=true, raw_sql_reason, and unsupported_features.",
            *_semantic_ir_source_selection_rules(),
            *_profile_specific_user_rules(profile),
            "For how many/count/number/total prompts, use COUNT and local_query.count=true; sampled LIST rows are not a count.",
            "For LOCAL_SNAPSHOT COUNT, use LOCAL_QUERY/LOCAL_SNAPSHOT/COUNT with count=true.",
            "Do not count bridge_table or relationship_table rows for entity record counts; use a matching snapshot_record_table.",
            "For schema/schema-record counts or lists, use LOCAL_QUERY on schema/blueprint table_role_hints: schema, blueprint, or xdm_schema.",
            "For date/published/created/updated without live/current/platform/API, use LOCAL_QUERY DATE/LOOKUP when local timestamp fields exist.",
            "For published/date prompts, select only exact timestamp/date fields present in the selected table's field_hints.date_fields or columns.",
            "Do not make local lookup depend on live API unless the local filter literally needs an ID returned by live task.",
            "For lifecycle active/inactive/status/state, use allowed fields/known values; if enum unknown, prefer broader LOCAL_QUERY over invented literal INACTIVE enum.",
            "If no explicit enum_values in the schema card prove an INACTIVE value exists, do not filter STATUS/STATE to INACTIVE; select NAME plus STATUS/STATE rows instead.",
            "For compare local/live prompts, include LOCAL_QUERY and LIVE_QUERY tasks when both are available, then aggregate.",
            "CACHE_ALIAS may reuse exact same evidence; LLM owns semantic equivalence and backend will not infer aliases.",
            "CACHE_ALIAS needs reuse_result_from, producer depends_on, no local_query/api_query, identical result_contract.",
            "If uncertain, do not alias. Do not alias local and live. Do not alias status and date or different sources/scopes/fields/filters.",
        ],
        "semantic_ir_examples": [
            "Explain what inactive journey means and show inactive journeys -> CONCEPT plus LOCAL_QUERY; contract slots CONCEPT/NONE and LIST/LOCAL_SNAPSHOT.",
            "Local count -> LOCAL_QUERY COUNT; contract slot COUNT/LOCAL_SNAPSHOT with required_fields ['count'].",
            "What <objects> do I have? without live/API words -> LOCAL_QUERY LIST over a matching local snapshot table.",
            "When was <named local journey/campaign> published? -> LOCAL_QUERY DATE/LOOKUP using exact local date_fields.",
        ],
        "semantic_alias_examples": [],
        "repair_context": redact_secrets(repair_context) if repair_context else None,
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _profile_tool_user_rule(profile: str | None) -> str:
    normalized = _normalize_planner_profile(profile)
    if normalized == PLANNER_PROFILE_DEEPSEEK_JSON_TOOL:
        return "Call submit_semantic_ir_json exactly once; put the complete Semantic IR object in semantic_ir_json; no text plan."
    if normalized == PLANNER_PROFILE_DEEPSEEK_MICRO_TOOLS:
        return "Call exactly one provided micro Semantic IR tool; use submit_mixed_evidence_plan for mixed/multi-task prompts; no text plan."
    if normalized == PLANNER_PROFILE_DEEPSEEK_AUTO_TOOL:
        return "Call submit_semantic_ir_plan exactly once even though tool_choice is auto; no text plan."
    if normalized == PLANNER_PROFILE_DEEPSEEK_REQUIRED_TOOL:
        return "Call submit_semantic_ir_plan exactly once with required tool_choice; no text plan."
    return "Call submit_semantic_ir_plan exactly once; no text plan."


def _profile_specific_user_rules(profile: str | None) -> list[str]:
    normalized = _normalize_planner_profile(profile)
    if normalized != PLANNER_PROFILE_DEEPSEEK_MICRO_TOOLS:
        return []
    return [
        "Micro tool selection: pure concept/meta -> submit_direct_task.",
        "Micro tool selection: local count/how many -> submit_local_count_task with answer_contract.",
        "Micro tool selection: local show/list/what do I have -> submit_local_query_task with answer_contract.",
        "Micro tool selection: local date/status/quoted entity lookup -> submit_local_lookup_task with answer_contract; do not use submit_mixed_evidence_plan for a single local date lookup.",
        "Micro tool selection: live/API-only -> submit_api_task with answer_contract.",
        "Micro tool selection: mixed concept plus data or local/live compare -> submit_mixed_evidence_plan with compact tasks and answer_contract.",
        "For mixed inactive journey/campaign prompts without live/current/platform/API wording, submit_mixed_evidence_plan must include a CONCEPT task plus a LOCAL_QUERY task; LIVE_QUERY cannot replace the local task.",
        "Keep micro-tool arguments short; choose one exact table/endpoint and only required fields.",
    ]


def _semantic_ir_source_selection_rules() -> list[str]:
    return [
        "'What schemas do I have?' asks for actual records and is not a pure concept question; route EVIDENCE.",
        "Local snapshot schema counts are COUNT over LOCAL_SNAPSHOT; show/list actual records is EVIDENCE.",
        "Prefer LOCAL_QUERY for user-specific local or ambiguous data-like prompts unless the prompt explicitly asks for live/current/platform/API or names an API catalog resource.",
        "If no live/current/platform/API cue asks for records/count/date/status/list, LIVE_QUERY is the wrong source; choose LOCAL_QUERY unless the prompt names an API catalog resource.",
        "'do I have', 'my', show/list/give me records, and bare lookups are LOCAL_SNAPSHOT unless they name API catalog resources.",
        "Bare 'schema' or 'schemas' plus 'do I have' or 'my' is LOCAL_SNAPSHOT; do not treat schemas alone as a Schema Registry cue.",
        "Use schema registry/schema API only for explicit Schema Registry, API, live/current/platform/AEP cues, not for bare schemas.",
        "Do not choose LIVE_QUERY merely because a live endpoint exists for the object family.",
        "Use LIVE_QUERY for explicit live/current/platform/API state, compare local/live evidence, or a named API catalog resource with a matching endpoint.",
        "Treat sandbox/sandbox-name prompts as live/API cues for API catalog resources unless prompt says local snapshot.",
        "Endpoint catalog resources such as tags, merge policies, segment definitions, segment jobs, batches/files, audit events, dataflow runs/flows, and recent platform changes use LIVE_QUERY.",
        "Do not invent local table names from endpoint IDs/API nouns; if no local table is listed, choose matching LIVE_QUERY.",
        "For batch prompts, use catalog_batches/detail/files/failed when user supplies needed path params.",
        "For recent changes, new destinations, or audit-style history prompts, use audit_events or audit_events_short when available.",
        "For segment definitions as sandbox/platform API resources or bare catalog requests, use segment_definitions unless local snapshot.",
        "If local dimension table can satisfy local-scoped answer slot and prompt does not require live/current/API-only, include LOCAL_QUERY.",
        "For segment jobs or evaluation jobs, use segment_jobs unless prompt asks local snapshot.",
        "For tags and merge policies in this sandbox, use unified_tags or merge_policies rather than LOCAL_QUERY.",
        "For show/list actual records without live/current/platform/API cues, prefer LOCAL_QUERY unless they name API catalog resources.",
        "For mixed concept plus data without live/current/platform/API cues, include CONCEPT plus LOCAL_QUERY; API only for named API catalog data.",
        "For inactive journeys without live/current/platform/API cues, use local journey/campaign records when available.",
        "For mixed inactive journey/campaign prompts without live/current/platform/API wording, LIVE_QUERY cannot replace the local task.",
        "For inactive journey/campaign local tasks, do not invent INACTIVE enum unless known; select NAME plus STATUS/STATE.",
        "For quoted/named entity filters, prefer primary_name_fields or title/name fields over label_fields; use label_fields for labels/tags/semantic labels.",
        "For relationship-bearing fields, schema class, or merge policy prompts, select existing allowed local fields; backend will not infer links.",
        ]


def _semantic_ir_missing_toolcall_retry_user_prompt(
    *,
    user_prompt: str,
    previous_result: dict[str, Any],
    allowed_schema_card: list[dict[str, Any]],
    allowed_api_card: list[dict[str, Any]],
    planner_profile: str | None = None,
) -> str:
    tool_rule = _profile_tool_user_rule(planner_profile)
    payload = {
        "task": "RETRY_MISSING_DASHSYS_V2_SEMANTIC_IR_TOOLCALL",
        "user_prompt": user_prompt,
        "previous_model_response": compact_preview(previous_result, 1200),
        "validation_error": {
            "error_type": "missing_tool_call",
            "error_message": "The previous response did not call the required Semantic IR SDK tool. Plain text is not accepted for the V2 primary path.",
        },
        "allowed_schema_card": allowed_schema_card,
        "allowed_api_card": allowed_api_card,
        "rules": [
            tool_rule,
            "Do not answer in message content.",
            "Use DIRECT with one non-executable CONCEPT task only for pure no-evidence concept/meta prompts.",
            "Use EVIDENCE with tasks for data, mixed, local, live, count, list, status, date, lookup, or compare prompts.",
            *_semantic_ir_source_selection_rules(),
        ],
    }
    return json.dumps(redact_secrets(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _semantic_ir_repair_system_prompt(planner_profile: str | None = None) -> str:
    tool_instruction = _profile_tool_system_instruction(planner_profile)
    return (
        "Your previous Semantic IR tool call failed shape or existence validation. "
        f"{tool_instruction} "
        "Do not use message content for the plan. Do not let malformed output fail open into DIRECT. "
        "Do not ask the backend to choose replacements; choose valid IDs from the allowed cards yourself. "
        "If the validation error is about answer_contract, repair the root answer_contract yourself and keep all slot semantics LLM-owned. "
        "If the validation error is about schema_binding, keep binding semantics LLM-owned and correct the Semantic IR table/field/binding IDs yourself."
    )


def _semantic_ir_repair_user_prompt(
    *,
    user_prompt: str,
    previous_args: dict[str, Any],
    validation: SemanticIRValidationResult,
    allowed_schema_card: list[dict[str, Any]],
    allowed_api_card: list[dict[str, Any]],
    planner_profile: str | None = None,
) -> str:
    allowed_tables = [row.get("table") for row in allowed_schema_card]
    allowed_endpoints = [row.get("endpoint_id") for row in allowed_api_card]
    tool_rule = _profile_tool_user_rule(planner_profile)
    payload = {
        "task": "REPAIR_DASHSYS_V2_SEMANTIC_IR",
        "user_prompt": user_prompt,
        "previous_tool_arguments": compact_preview(previous_args, 1600),
        "validation_error": validation.to_dict(),
        "allowed_tables": allowed_tables,
        "allowed_fields_for_error_table": list(validation.allowed_fields_for_table or []),
        "table_role_cards": validation.table_role_cards or _table_role_cards_for_repair(allowed_schema_card),
        "field_role_cards": _field_role_cards_for_repair(allowed_schema_card, validation),
        "relationship_cards": _relationship_cards_for_repair(allowed_schema_card),
        "allowed_schema_card": allowed_schema_card,
        "allowed_endpoints": allowed_endpoints,
        "allowed_api_card": allowed_api_card,
        "rules": [
            tool_rule,
            "Use only exact table, field, and endpoint IDs from allowed cards.",
            "Choose exact table and field IDs from allowed cards. Do not invent semantic table names.",
            "Choose table only from allowed_tables. Do not invent semantic table names.",
            "If previous_tool_arguments include schema_binding, keep or correct binding_id references explicitly; backend will not apply binding fields automatically.",
            "If route is EVIDENCE, include root answer_contract; do not omit it.",
            "The root answer_contract must include contract_version='v1', answer_style, global_scope, required_slots, and optional_slots.",
            "If route is DIRECT, use answer_contract with empty slots and global_scope NONE unless a direct CONCEPT slot is useful.",
            "Each required slot must include slot_id, type, required, subject, object, relation, source_scope, satisfied_by_tasks, required_fields, acceptable_fallback_fields, expected_status_filter, zero_rows_semantics, if_missing, must_not_assert_positive_if_zero_rows, and notes.",
            "Each slot's satisfied_by_tasks must reference task IDs in this corrected tool call.",
            "For COUNT evidence use a COUNT slot with required_fields ['count']; for DATE evidence use DATE with required/fallback date fields; for LIST/LOOKUP/STATUS/RELATION evidence use scoped zero_rows_semantics and if_missing caveat policy.",
            "For unknown_field repairs, choose only from allowed_fields_for_error_table or change to another allowed table from table_role_cards.",
            "Do not retry generic timestamp names outside allowed_fields_for_error_table; for date repairs choose only from allowed_fields_for_error_table and field_role_cards.date_fields.",
            "If local COUNT used a bridge_table or relationship_table for an entity count, repair to a valid snapshot_record_table with matching table_role_hints.",
            "Do not output narrative text.",
            *_semantic_ir_source_selection_rules(),
        ],
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _table_role_cards_for_repair(allowed_schema_card: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for row in allowed_schema_card:
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


def _field_role_cards_for_repair(
    allowed_schema_card: list[dict[str, Any]],
    validation: SemanticIRValidationResult,
) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    preferred_fields = set(validation.allowed_fields_for_table or [])
    for row in allowed_schema_card:
        table = str(row.get("table") or "")
        if not table:
            continue
        columns = list(row.get("columns") or [])
        if preferred_fields and not any(column in preferred_fields for column in columns):
            continue
        cards.append(
            {
                "table": table,
                "allowed_fields": columns[:32],
                "field_hints": row.get("field_hints") if isinstance(row.get("field_hints"), dict) else {},
            }
        )
    return cards or [
        {
            "table": None,
            "allowed_fields": list(validation.allowed_fields_for_table or []),
            "field_hints": {},
        }
    ]


def _relationship_cards_for_repair(allowed_schema_card: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for row in allowed_schema_card:
        table = str(row.get("table") or "")
        if not table:
            continue
        hints = row.get("field_hints") if isinstance(row.get("field_hints"), dict) else {}
        id_fields = list(hints.get("id_fields") or [])
        relation_fields = [
            field
            for field in list(row.get("columns") or [])
            if "relationship" in str(field).lower() or str(field).lower().endswith("id") or "_id" in str(field).lower()
        ][:16]
        if not id_fields and not relation_fields:
            continue
        cards.append({"table": table, "id_fields": id_fields[:16], "relationship_like_fields": relation_fields})
    return cards


def _semantic_ir_support_repair_system_prompt(planner_profile: str | None = None) -> str:
    tool_instruction = _profile_tool_system_instruction(planner_profile)
    return (
        "Your previous Semantic IR was valid but used structures the backend compiler does not support. "
        f"{tool_instruction} "
        "Keep the same user intent. Prefer supported LIST/COUNT/LOOKUP/STATUS/DATE LocalQueryIR/APIQueryIR if it can express the evidence. "
        "Preserve and update the root answer_contract so required slots still reference the corrected task IDs. "
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
    planner_profile: str | None = None,
) -> str:
    tool_rule = _profile_tool_user_rule(planner_profile)
    payload = {
        "task": "REPAIR_UNSUPPORTED_DASHSYS_V2_SEMANTIC_IR",
        "user_prompt": user_prompt,
        "previous_tool_arguments": compact_preview(previous_args, 1600),
        "unsupported_ir": support_result.to_dict(),
        "allowed_schema_card": allowed_schema_card,
        "allowed_api_card": allowed_api_card,
        "rules": [
            tool_rule,
            "First try to express the same evidence request using supported Semantic IR.",
            "Supported local operations are LIST, COUNT, LOOKUP, STATUS, and DATE with simple filters.",
            "Preserve root answer_contract and update satisfied_by_tasks to the corrected task IDs.",
            "If route is EVIDENCE and answer_contract is missing, add it now with LLM-owned required slots.",
            "Do not choose a different user intent.",
            "Do not choose replacement tables, fields, filters, or endpoints unless they are your LLM-owned corrected plan and appear in the allowed cards.",
            "If supported Semantic IR cannot represent the required local structure, keep the unsupported local task and explicitly set requires_raw_sql_fallback=true, raw_sql_reason, and unsupported_features.",
            "Never use raw SQL fallback for LIVE_API or API tasks.",
            *_semantic_ir_source_selection_rules(),
            *_semantic_ir_support_specific_repair_rules(support_result),
        ],
    }
    return json.dumps(redact_secrets(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _semantic_ir_support_specific_repair_rules(support_result: IRSupportResult) -> list[str]:
    features = set(support_result.unsupported_features)
    rules: list[str] = []
    if "MISSING_LOCAL_SCHEMA_QUERY" in features:
        rules.extend(
            [
                "Repair MISSING_LOCAL_SCHEMA_QUERY by adding a required LOCAL_QUERY/LOCAL_SNAPSHOT task for local schema records.",
                "For schema record prompts without live/current/API cues, LIVE_QUERY and DIRECT cannot replace the required local task.",
                "Update answer_contract so the schema slot has source_scope LOCAL_SNAPSHOT and is satisfied by the local task.",
            ]
        )
    if "MISSING_LOCAL_DATE_QUERY" in features:
        rules.extend(
            [
                "Repair MISSING_LOCAL_DATE_QUERY by adding a required LOCAL_QUERY/LOCAL_SNAPSHOT DATE or LOOKUP task over a journey/campaign table with exact date fields.",
                "Choose only exact date/timestamp fields from AllowedLocalSchemaCard field_hints.date_fields or allowed table columns.",
                "Update answer_contract so the date slot has source_scope LOCAL_SNAPSHOT and is satisfied by the local task.",
            ]
        )
    if "MISSING_LOCAL_JOURNEY_QUERY" in features:
        rules.extend(
            [
                "Repair MISSING_LOCAL_JOURNEY_QUERY by preserving the concept task if useful and adding a required LOCAL_QUERY/LOCAL_SNAPSHOT task for local journey/campaign records.",
                "For that local task, choose exact table and fields from AllowedLocalSchemaCard; the backend will not choose replacements.",
                "API evidence may be optional only when the prompt explicitly asks for live/current/platform/API evidence; it cannot replace the required local slot.",
                "Update answer_contract so the inactive-journey LIST slot has source_scope LOCAL_SNAPSHOT and is satisfied by the local task.",
            ]
        )
    return rules
