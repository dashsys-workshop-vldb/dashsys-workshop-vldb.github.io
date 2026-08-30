from __future__ import annotations

import json
from typing import Any

from .endpoint_catalog import EndpointCatalog
from .llm_client import LLMClient
from .llm_tool_agent_prompts import parse_json_object
from .llm_tool_choice_validator import infer_tool_choice_root_cause, validate_tool_choice_plan
from .trajectory import compact_preview, redact_secrets


REQUIRED_KEYS = {
    "question_type",
    "needs_local_sql",
    "needs_live_api",
    "sql_reason",
    "api_reason",
    "local_tables_that_may_answer",
    "api_endpoints_that_may_answer",
    "preferred_first_tool",
    "confidence",
}


def plan_evidence_source(
    prompt: str,
    schema_context: dict[str, Any],
    endpoint_catalog: EndpointCatalog,
    llm_client: LLMClient,
) -> dict[str, Any]:
    """Ask the Pure LLM for an evidence-source plan, then normalize its JSON shape."""

    system_prompt, user_prompt = _build_prompt(prompt, schema_context)
    response = llm_client.generate(system_prompt, user_prompt)
    parsed = parse_json_object(response.get("content", ""))
    if not parsed:
        correction = llm_client.generate(
            system_prompt + " Correct your previous output and return valid JSON only.",
            user_prompt,
        )
        parsed = parse_json_object(correction.get("content", ""))
        response = correction
    plan = _normalize_plan(parsed)
    return redact_secrets(
        {
            "ok": _has_required_shape(plan),
            "plan": plan,
            "missing_keys": sorted(REQUIRED_KEYS - set(plan)),
            "_usage": response.get("usage", {}),
        }
    )


def plan_validate_and_repair_evidence_source(
    prompt: str,
    schema_context: dict[str, Any],
    endpoint_catalog: EndpointCatalog,
    llm_client: LLMClient,
) -> dict[str, Any]:
    first = plan_evidence_source(prompt, schema_context, endpoint_catalog, llm_client)
    initial_validation = validate_tool_choice_plan(prompt, first.get("plan", {}), schema_context, endpoint_catalog)
    validation = initial_validation
    retry_used = False
    repaired = first
    if not validation.get("ok"):
        retry_used = True
        system_prompt, user_prompt = _build_repair_prompt(prompt, schema_context, first.get("plan", {}), validation)
        response = llm_client.generate(system_prompt, user_prompt)
        repaired_plan = _normalize_plan(parse_json_object(response.get("content", "")))
        repaired = {"ok": _has_required_shape(repaired_plan), "plan": repaired_plan, "_usage": response.get("usage", {})}
        validation = validate_tool_choice_plan(prompt, repaired_plan, schema_context, endpoint_catalog)
    root_cause = infer_tool_choice_root_cause(prompt, repaired.get("plan", {}), validation, schema_context)
    return redact_secrets(
        {
            "ok": bool(validation.get("ok")),
            "initial_plan": first.get("plan", {}),
            "initial_validation": initial_validation,
            "final_plan": repaired.get("plan", {}),
            "validation": validation,
            "retry_used": retry_used,
            "tool_choice_validation_ok": bool(validation.get("ok")),
            "rejection_reason": validation.get("rejection_reason"),
            "final_tool_choice": validation.get("final_tool_choice"),
            "root_cause": root_cause,
            "_usage": {
                "initial": first.get("_usage", {}),
                "final": repaired.get("_usage", {}),
            },
        }
    )


def _build_prompt(prompt: str, schema_context: dict[str, Any]) -> tuple[str, str]:
    system_prompt = (
        "Choose which evidence source a DASHSys pure LLM tool agent should use. Return JSON only with keys: "
        '"question_type", "needs_local_sql", "needs_live_api", "sql_reason", "api_reason", '
        '"local_tables_that_may_answer", "api_endpoints_that_may_answer", "preferred_first_tool", "confidence". '
        "Prefer execute_sql for local snapshot entities such as journeys/campaigns, datasets/collections, "
        "schemas/blueprints, segments/audiences, destinations/targets, connectors/flows, fields/properties. "
        "Use call_api first only for explicit live Adobe/API/platform state or when no local table can answer. "
        "Do not answer the user; choose evidence only."
    )
    user_prompt = json.dumps(
        {
            "prompt": prompt,
            "schema_context": compact_preview(schema_context, 9000),
        },
        indent=2,
        default=str,
    )
    return system_prompt, user_prompt


def _build_repair_prompt(
    prompt: str,
    schema_context: dict[str, Any],
    bad_plan: dict[str, Any],
    validation: dict[str, Any],
) -> tuple[str, str]:
    system_prompt = (
        "Repair the evidence-source plan JSON only. Keep the same required keys. "
        "If validation says sql_likely_required_api_chosen, choose execute_sql first unless the prompt explicitly asks for live API state. "
        "If validation says unresolved_api_path_param, choose a safe catalog endpoint without path placeholders or choose SQL if local schema can answer."
    )
    user_prompt = json.dumps(
        {
            "prompt": prompt,
            "bad_plan": bad_plan,
            "validation": validation,
            "schema_context": compact_preview(schema_context, 9000),
        },
        indent=2,
        default=str,
    )
    return system_prompt, user_prompt


def _normalize_plan(plan: dict[str, Any]) -> dict[str, Any]:
    normalized = _unwrap_plan_object(dict(plan or {}))
    normalized.setdefault("question_type", "unknown")
    normalized["question_type"] = str(normalized.get("question_type") or "unknown").lower()
    normalized["needs_local_sql"] = bool(normalized.get("needs_local_sql"))
    normalized["needs_live_api"] = bool(normalized.get("needs_live_api"))
    normalized.setdefault("sql_reason", "")
    normalized.setdefault("api_reason", "")
    normalized["local_tables_that_may_answer"] = _string_list(normalized.get("local_tables_that_may_answer"))
    normalized["api_endpoints_that_may_answer"] = _string_list(normalized.get("api_endpoints_that_may_answer"))
    preferred = str(normalized.get("preferred_first_tool") or "").strip().lower()
    if preferred in {"sql", "execute sql"}:
        preferred = "execute_sql"
    elif preferred in {"api", "call api"}:
        preferred = "call_api"
    elif preferred not in {"execute_sql", "call_api", "none", "both"}:
        preferred = "execute_sql" if normalized["needs_local_sql"] else ("call_api" if normalized["needs_live_api"] else "none")
    normalized["preferred_first_tool"] = preferred
    try:
        normalized["confidence"] = float(normalized.get("confidence") or 0.0)
    except Exception:
        normalized["confidence"] = 0.0
    normalized["confidence"] = max(0.0, min(1.0, normalized["confidence"]))
    return normalized


def _unwrap_plan_object(plan: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(plan, dict):
        return {}
    if REQUIRED_KEYS.intersection(plan.keys()):
        return dict(plan)
    for key in ("plan", "evidence_source_plan", "tool_choice_plan"):
        nested = plan.get(key)
        if isinstance(nested, dict):
            unwrapped = dict(nested)
            if "_usage" not in unwrapped and "_usage" in plan:
                unwrapped["_usage"] = plan["_usage"]
            return unwrapped
    return dict(plan)


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for item in value:
        if isinstance(item, dict):
            text = item.get("table") or item.get("table_name") or item.get("endpoint_id") or item.get("id")
        else:
            text = item
        if text:
            items.append(str(text))
    return items


def _has_required_shape(plan: dict[str, Any]) -> bool:
    return REQUIRED_KEYS.issubset(set(plan)) and plan.get("preferred_first_tool") in {"execute_sql", "call_api", "both", "none"}
