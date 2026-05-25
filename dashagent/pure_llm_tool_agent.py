from __future__ import annotations

import time
from typing import Any

from .api_client import AdobeAPIClient
from .db import DuckDBDatabase
from .endpoint_catalog import EndpointCatalog
from .llm_api_tool_guard import validate_llm_api_candidate
from .llm_client import LLMClient, get_llm_client
from .llm_evidence_locked_answer import evidence_locked_answer
from .llm_sql_context_builder import build_llm_sql_context, infer_answer_intent
from .llm_sql_repair_loop import run_sql_repair_loop
from .llm_tool_agent_prompts import build_api_candidate_prompt, build_planning_prompt, parse_json_object
from .schema_index import SchemaIndex
from .trajectory import estimate_tokens, redact_secrets
from .validators import APIValidator, SQLValidator


STRUCTURED_PLAN_THEN_TOOLS = "structured_plan_then_tools"
SCHEMA_RETRIEVED_SQL_AGENT = "schema_retrieved_sql_agent"
VALIDATE_REPAIR_SQL_AGENT = "validate_repair_sql_agent"
EVIDENCE_LOCKED_ANSWER_AGENT = "evidence_locked_answer_agent"
FULL_PURE_LLM_TOOL_AGENT_V1 = "full_pure_llm_tool_agent_v1"

PURE_LLM_TOOL_AGENT_VARIANTS = [
    STRUCTURED_PLAN_THEN_TOOLS,
    SCHEMA_RETRIEVED_SQL_AGENT,
    VALIDATE_REPAIR_SQL_AGENT,
    EVIDENCE_LOCKED_ANSWER_AGENT,
    FULL_PURE_LLM_TOOL_AGENT_V1,
]


VARIANT_CAPABILITIES = {
    STRUCTURED_PLAN_THEN_TOOLS: {
        "structured_plan": True,
        "schema_context": False,
        "sql_repair": False,
        "api_guard": False,
        "evidence_locked_answer": False,
    },
    SCHEMA_RETRIEVED_SQL_AGENT: {
        "structured_plan": True,
        "schema_context": True,
        "sql_repair": False,
        "api_guard": False,
        "evidence_locked_answer": False,
    },
    VALIDATE_REPAIR_SQL_AGENT: {
        "structured_plan": True,
        "schema_context": True,
        "sql_repair": True,
        "api_guard": False,
        "evidence_locked_answer": False,
    },
    EVIDENCE_LOCKED_ANSWER_AGENT: {
        "structured_plan": True,
        "schema_context": True,
        "sql_repair": True,
        "api_guard": False,
        "evidence_locked_answer": True,
    },
    FULL_PURE_LLM_TOOL_AGENT_V1: {
        "structured_plan": True,
        "schema_context": True,
        "sql_repair": True,
        "api_guard": True,
        "evidence_locked_answer": True,
    },
}


def pure_llm_baseline_definitions() -> list[dict[str, Any]]:
    return [
        {
            "variant": "raw_two_tools_current",
            "description": "Current raw LLM with execute_sql and call_api, no extra scaffolding.",
            "status": "existing_baseline",
        },
        {
            "variant": "guided_two_tools_current",
            "description": "Current guided prompt baseline with schema/API affordances.",
            "status": "existing_baseline",
        },
        {
            "variant": STRUCTURED_PLAN_THEN_TOOLS,
            "description": "LLM outputs a structured plan before tool use.",
            "capabilities": VARIANT_CAPABILITIES[STRUCTURED_PLAN_THEN_TOOLS],
            "status": "shadow_diagnostic",
        },
        {
            "variant": SCHEMA_RETRIEVED_SQL_AGENT,
            "description": "Adds compact schema and endpoint retrieval context for LLM SQL planning.",
            "capabilities": VARIANT_CAPABILITIES[SCHEMA_RETRIEVED_SQL_AGENT],
            "status": "shadow_diagnostic",
        },
        {
            "variant": VALIDATE_REPAIR_SQL_AGENT,
            "description": "Adds SQLValidator/SQLGlot validation and up to two repair rounds.",
            "capabilities": VARIANT_CAPABILITIES[VALIDATE_REPAIR_SQL_AGENT],
            "status": "shadow_diagnostic",
        },
        {
            "variant": EVIDENCE_LOCKED_ANSWER_AGENT,
            "description": "Locks final answer claims to structured tool observations.",
            "capabilities": VARIANT_CAPABILITIES[EVIDENCE_LOCKED_ANSWER_AGENT],
            "status": "shadow_diagnostic",
        },
        {
            "variant": FULL_PURE_LLM_TOOL_AGENT_V1,
            "description": "Combines planning, schema retrieval, SQL repair, API validation, and evidence-locked answer.",
            "capabilities": VARIANT_CAPABILITIES[FULL_PURE_LLM_TOOL_AGENT_V1],
            "status": "shadow_diagnostic",
        },
    ]


def run_pure_llm_tool_agent_variant(
    prompt: str,
    *,
    variant: str = FULL_PURE_LLM_TOOL_AGENT_V1,
    db: DuckDBDatabase,
    schema_index: SchemaIndex,
    endpoint_catalog: EndpointCatalog,
    api_client: AdobeAPIClient | None = None,
    llm_client: LLMClient | None = None,
) -> dict[str, Any]:
    client = llm_client or get_llm_client()
    if not client.available():
        return {
            "skipped": True,
            "reason": "LLM provider unavailable",
            "variant": variant,
            "final_answer": "",
            "trajectory": {"steps": [], "strategy": variant, "final_answer": "", "tool_call_count": 0},
        }
    start = time.perf_counter()
    capabilities = VARIANT_CAPABILITIES.get(variant, VARIANT_CAPABILITIES[FULL_PURE_LLM_TOOL_AGENT_V1])
    context = build_llm_sql_context(prompt, schema_index, endpoint_catalog if capabilities.get("schema_context") else None)
    plan = _plan(prompt, context, client) if capabilities.get("structured_plan") else _default_plan(prompt, context)
    answer_intent = str(plan.get("answer_intent") or context.get("answer_intent") or infer_answer_intent(prompt))
    observations: list[dict[str, Any]] = []
    steps: list[dict[str, Any]] = [{"kind": "llm_plan", "variant": variant, "plan": plan, "context_summary": _context_summary(context)}]
    sql_result: dict[str, Any] | None = None
    if bool(plan.get("needs_sql", True)):
        repair = run_sql_repair_loop(
            prompt,
            context,
            db,
            SQLValidator(schema_index),
            llm_client=client,
            plan=plan,
            max_repair_rounds=2 if capabilities.get("sql_repair") else 0,
        )
        sql_result = repair
        if repair.get("sql"):
            steps.append(
                {
                    "kind": "sql_call",
                    "sql": repair.get("sql"),
                    "validation": repair.get("validation"),
                    "result": repair.get("execution_result"),
                    "repair_rounds": repair.get("repair_rounds"),
                }
            )
        if repair.get("ok"):
            observations.append({"source": "sql", "rows": repair.get("execution_result", {}).get("rows", []), "row_count": repair.get("execution_result", {}).get("row_count")})
    api_result: dict[str, Any] | None = None
    if bool(plan.get("needs_api", False)):
        api_result = _run_api_step(prompt, context, plan, endpoint_catalog, api_client, client, guard=bool(capabilities.get("api_guard")))
        steps.append(api_result.get("step", {"kind": "api_call", "validation": {"ok": False}}))
        if api_result.get("observation"):
            observations.append(api_result["observation"])
    if capabilities.get("evidence_locked_answer"):
        answer_payload = evidence_locked_answer(prompt, observations, llm_client=client, answer_intent=answer_intent)
        final_answer = str(answer_payload.get("answer") or "")
    else:
        answer_payload = evidence_locked_answer(prompt, observations, llm_client=client, answer_intent=answer_intent)
        final_answer = str(answer_payload.get("answer") or "")
    steps.append({"kind": "final_answer", "answer": final_answer, "answer_guard": answer_payload})
    runtime = time.perf_counter() - start
    trajectory = {
        "original_query": prompt,
        "strategy": variant,
        "baseline_variant": variant,
        "pure_llm_tool_agent": True,
        "steps": steps,
        "final_answer": final_answer,
        "tool_call_count": sum(1 for step in steps if step.get("kind") in {"sql_call", "api_call"}),
        "runtime": runtime,
        "estimated_tokens": estimate_tokens({"prompt": prompt, "steps": steps, "answer": final_answer}),
        "llm_total_tokens": _sum_usage_tokens([plan, sql_result or {}, api_result or {}, answer_payload]),
        "token_source": "measured_usage_or_estimated",
        "unsupported_claim_count": answer_payload.get("unsupported_claim_count", 0),
    }
    return redact_secrets(
        {
            "skipped": False,
            "variant": variant,
            "final_answer": final_answer,
            "plan": plan,
            "sql_result": sql_result,
            "api_result": api_result,
            "answer_result": answer_payload,
            "trajectory": trajectory,
            "tool_call_count": trajectory["tool_call_count"],
            "runtime": runtime,
            "estimated_tokens": trajectory["estimated_tokens"],
            "unsupported_claim_count": answer_payload.get("unsupported_claim_count", 0),
        }
    )


def _plan(prompt: str, context: dict[str, Any], client: LLMClient) -> dict[str, Any]:
    bundle = build_planning_prompt(prompt, context)
    response = client.generate(bundle.system_prompt, bundle.user_prompt)
    parsed = parse_json_object(response.get("content", ""))
    if not parsed:
        correction = client.generate(bundle.system_prompt + " Correct your previous output and return valid JSON only.", bundle.user_prompt)
        parsed = parse_json_object(correction.get("content", ""))
    parsed.setdefault("answer_intent", context.get("answer_intent") or infer_answer_intent(prompt))
    parsed.setdefault("needs_sql", True)
    parsed.setdefault("needs_api", False)
    parsed["_usage"] = response.get("usage", {})
    return parsed


def _default_plan(prompt: str, context: dict[str, Any]) -> dict[str, Any]:
    return {
        "answer_intent": context.get("answer_intent") or infer_answer_intent(prompt),
        "needs_sql": True,
        "needs_api": False,
        "reason": "default pure LLM baseline plan",
        "candidate_tables": [item.get("table") for item in context.get("top_tables", [])[:3]],
        "candidate_endpoints": [item.get("endpoint_id") for item in context.get("endpoint_candidates", [])[:3]],
    }


def _run_api_step(
    prompt: str,
    context: dict[str, Any],
    plan: dict[str, Any],
    endpoint_catalog: EndpointCatalog,
    api_client: AdobeAPIClient | None,
    client: LLMClient,
    *,
    guard: bool,
) -> dict[str, Any]:
    bundle = build_api_candidate_prompt(prompt, context, plan)
    response = client.generate(bundle.system_prompt, bundle.user_prompt)
    candidate = parse_json_object(response.get("content", ""))
    validator = APIValidator(endpoint_catalog)
    guarded = validate_llm_api_candidate(candidate, endpoint_catalog, validator) if guard else _unguarded_api_candidate(candidate, endpoint_catalog, validator)
    if not guarded.get("ok"):
        return {"ok": False, "guard": guarded, "step": {"kind": "api_call", "validation": {"ok": False, "errors": [guarded.get("rejection_reason")]}}}
    call = guarded["validated_api_call"]
    result = api_client.call_api(call["method"], call["url"], call.get("params", {}), call.get("headers", {})) if api_client else {"ok": False, "dry_run": True, "status_code": None, "result_preview": None}
    return redact_secrets(
        {
            "ok": bool(result.get("ok")),
            "guard": guarded,
            "observation": {"source": "api", "state": "live_success" if result.get("ok") and not result.get("dry_run") else "api_unavailable", "result_preview": result.get("result_preview")},
            "step": {
                "kind": "api_call",
                "method": call["method"],
                "url": call["url"],
                "params": call.get("params", {}),
                "validation": guarded.get("validation"),
                "result": {"ok": result.get("ok"), "dry_run": result.get("dry_run"), "status_code": result.get("status_code")},
            },
        }
    )


def _unguarded_api_candidate(candidate: dict[str, Any], endpoint_catalog: EndpointCatalog, validator: APIValidator) -> dict[str, Any]:
    endpoint_id = str(candidate.get("endpoint_id") or "").strip()
    endpoint = endpoint_catalog.by_id(endpoint_id) if endpoint_id else None
    if endpoint is None:
        return {"ok": False, "rejection_reason": "no catalog endpoint selected", "candidate": candidate}
    return validate_llm_api_candidate({"endpoint_id": endpoint.id, "method": endpoint.method, "params": candidate.get("params", {})}, endpoint_catalog, validator)


def _context_summary(context: dict[str, Any]) -> dict[str, Any]:
    return {
        "top_tables": [item.get("table") for item in context.get("top_tables", [])],
        "endpoint_candidates": [item.get("endpoint_id") for item in context.get("endpoint_candidates", [])],
        "answer_intent": context.get("answer_intent"),
    }


def _sum_usage_tokens(items: list[dict[str, Any]]) -> int | None:
    total = 0
    seen = False
    for item in items:
        usage = item.get("_usage") if isinstance(item, dict) else None
        if isinstance(usage, dict) and isinstance(usage.get("total_tokens"), (int, float)):
            total += int(usage["total_tokens"])
            seen = True
    return total if seen else None
