from __future__ import annotations

import re
import time
from typing import Any

from .api_client import AdobeAPIClient
from .api_outcome_classifier import classify_api_outcome
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
STRUCTURED_SQL_PLAN_AGENT_V1 = "structured_sql_plan_agent_v1"
STRUCTURED_SQL_PLAN_WITH_REPAIR_V1 = "structured_sql_plan_with_repair_v1"
STRUCTURED_SQL_PLAN_BACKEND_ANSWER_ONLY = "structured_sql_plan_backend_answer_only"

PURE_LLM_TOOL_AGENT_VARIANTS = [
    STRUCTURED_PLAN_THEN_TOOLS,
    SCHEMA_RETRIEVED_SQL_AGENT,
    VALIDATE_REPAIR_SQL_AGENT,
    EVIDENCE_LOCKED_ANSWER_AGENT,
    FULL_PURE_LLM_TOOL_AGENT_V1,
    STRUCTURED_SQL_PLAN_AGENT_V1,
    STRUCTURED_SQL_PLAN_WITH_REPAIR_V1,
    STRUCTURED_SQL_PLAN_BACKEND_ANSWER_ONLY,
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
    STRUCTURED_SQL_PLAN_AGENT_V1: {
        "structured_plan": True,
        "schema_context": True,
        "sql_repair": False,
        "structured_sql_plan": True,
        "api_guard": True,
        "evidence_locked_answer": True,
    },
    STRUCTURED_SQL_PLAN_WITH_REPAIR_V1: {
        "structured_plan": True,
        "schema_context": True,
        "sql_repair": True,
        "structured_sql_plan": True,
        "api_guard": True,
        "evidence_locked_answer": True,
    },
    STRUCTURED_SQL_PLAN_BACKEND_ANSWER_ONLY: {
        "structured_plan": True,
        "schema_context": True,
        "sql_repair": True,
        "structured_sql_plan": True,
        "api_guard": True,
        "evidence_locked_answer": True,
        "backend_answer_only": True,
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
        {
            "variant": STRUCTURED_SQL_PLAN_AGENT_V1,
            "description": "LLM emits structured SQL plan JSON; deterministic compiler emits validated SQL without repair.",
            "capabilities": VARIANT_CAPABILITIES[STRUCTURED_SQL_PLAN_AGENT_V1],
            "status": "shadow_diagnostic",
        },
        {
            "variant": STRUCTURED_SQL_PLAN_WITH_REPAIR_V1,
            "description": "Structured SQL plan JSON plus deterministic compiler and up to two plan repair rounds.",
            "capabilities": VARIANT_CAPABILITIES[STRUCTURED_SQL_PLAN_WITH_REPAIR_V1],
            "status": "shadow_diagnostic",
        },
        {
            "variant": STRUCTURED_SQL_PLAN_BACKEND_ANSWER_ONLY,
            "description": "Structured SQL plan with deterministic tool-evidence answer fallback only.",
            "capabilities": VARIANT_CAPABILITIES[STRUCTURED_SQL_PLAN_BACKEND_ANSWER_ONLY],
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
    raw_plan = _plan(prompt, context, client) if capabilities.get("structured_plan") else _default_plan(prompt, context)
    plan = _normalize_plan(prompt, context, raw_plan)
    answer_intent = str(plan.get("answer_intent") or context.get("answer_intent") or infer_answer_intent(prompt))
    observations: list[dict[str, Any]] = []
    steps: list[dict[str, Any]] = [
        {
            "kind": "llm_plan",
            "variant": variant,
            "plan": plan,
            "raw_plan": raw_plan,
            "context_summary": _context_summary(context),
        }
    ]
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
            structured_sql_plan=bool(capabilities.get("structured_sql_plan")),
        )
        sql_result = repair
        steps.append(
            {
                "kind": "sql_call",
                "sql": repair.get("sql"),
                "validation": repair.get("validation") or _last_validation(repair),
                "result": repair.get("execution_result"),
                "repair_rounds": repair.get("repair_rounds"),
                "attempts": repair.get("attempts", []),
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
    answer_client = _UnavailableLLMClient() if capabilities.get("backend_answer_only") else client
    if capabilities.get("evidence_locked_answer"):
        answer_payload = evidence_locked_answer(prompt, observations, llm_client=answer_client, answer_intent=answer_intent)
        final_answer = str(answer_payload.get("answer") or "")
    else:
        answer_payload = evidence_locked_answer(prompt, observations, llm_client=answer_client, answer_intent=answer_intent)
        final_answer = str(answer_payload.get("answer") or "")
    steps.append({"kind": "final_answer", "answer": final_answer, "answer_guard": answer_payload})
    runtime = time.perf_counter() - start
    trace_assertions = _trace_assertions(plan, steps, answer_payload)
    failure_stage = _failure_stage_from_assertions(trace_assertions)
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
        "rejected_unsupported_claim_count": answer_payload.get("rejected_unsupported_claim_count", 0),
        "trace_assertions": trace_assertions,
        "failure_stage": failure_stage,
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
            "rejected_unsupported_claim_count": answer_payload.get("rejected_unsupported_claim_count", 0),
            "trace_assertions": trace_assertions,
            "failure_stage": failure_stage,
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


def _normalize_plan(prompt: str, context: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(plan or {})
    actions: list[str] = []
    normalized.setdefault("answer_intent", context.get("answer_intent") or infer_answer_intent(prompt))
    endpoint_candidates = [item.get("endpoint_id") for item in context.get("endpoint_candidates", []) if item.get("endpoint_id")]
    normalized.setdefault("candidate_endpoints", endpoint_candidates[:3])
    normalized.setdefault("candidate_tables", [item.get("table") for item in context.get("top_tables", [])[:3]])
    if _explicit_api_request(prompt):
        if not normalized.get("needs_api"):
            actions.append("forced_api_for_explicit_api_prompt")
        normalized["needs_api"] = True
    if _data_question_needs_tool(prompt) and not normalized.get("needs_sql") and not normalized.get("needs_api"):
        normalized["needs_sql"] = True
        actions.append("forced_sql_for_data_question")
    if normalized.get("needs_api") and not normalized.get("candidate_endpoints") and endpoint_candidates:
        normalized["candidate_endpoints"] = endpoint_candidates[:3]
        actions.append("added_catalog_endpoint_candidates")
    normalized["_normalization_actions"] = actions
    return normalized


def _data_question_needs_tool(prompt: str) -> bool:
    lowered = prompt.lower()
    return any(
        marker in lowered
        for marker in (
            "how many",
            "count",
            "list",
            "show",
            "which",
            "when",
            "status",
            "state",
            "date",
            "dataset",
            "journey",
            "campaign",
            "audience",
            "segment",
            "destination",
            "schema",
            "batch",
            "api",
        )
    )


def _explicit_api_request(prompt: str) -> bool:
    lowered = prompt.lower()
    return bool(
        re.search(r"\bapi\b|\bendpoint\b|ups audiences|merge policies|journey api|batch details|adobe", lowered)
    )


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
    retry_attempted = False
    rejected_candidate = None
    if not guarded.get("ok") and guard:
        retry_attempted = True
        rejected_candidate = candidate
        retry_context = _context_without_unresolved_path_endpoints(context)
        retry_system = (
            bundle.system_prompt
            + " Your previous endpoint choice was rejected. Retry once. "
            "Choose only an endpoint_id from the supplied catalog candidates; do not invent endpoint IDs or URLs."
        )
        retry_response = client.generate(
            retry_system,
            build_api_candidate_prompt(prompt, retry_context, plan).user_prompt,
        )
        candidate = parse_json_object(retry_response.get("content", ""))
        guarded = validate_llm_api_candidate(candidate, endpoint_catalog, validator)
    if not guarded.get("ok"):
        return {
            "ok": False,
            "guard": guarded,
            "step": {
                "kind": "api_call",
                "endpoint_candidate": candidate.get("endpoint_id"),
                "rejected_candidate": rejected_candidate,
                "retry_attempted": retry_attempted,
                "validation": {"ok": False, "errors": [guarded.get("rejection_reason")]},
            },
        }
    call = guarded["validated_api_call"]
    result = api_client.call_api(call["method"], call["url"], call.get("params", {}), call.get("headers", {})) if api_client else {"ok": False, "dry_run": True, "status_code": None, "result_preview": None}
    outcome = classify_api_outcome(result, method=call["method"], path=call["url"])
    return redact_secrets(
        {
            "ok": bool(result.get("ok")),
            "guard": guarded,
            "observation": {
                "source": "api",
                "state": outcome,
                "status_code": result.get("status_code"),
                "endpoint": call["url"],
                "result_preview": result.get("result_preview"),
                "parsed_evidence": result.get("parsed_evidence"),
            },
            "step": {
                "kind": "api_call",
                "method": call["method"],
                "url": call["url"],
                "params": call.get("params", {}),
                "endpoint_candidate": candidate.get("endpoint_id"),
                "retry_attempted": retry_attempted,
                "rejected_candidate": rejected_candidate,
                "validation": guarded.get("validation"),
                "result": {"ok": result.get("ok"), "dry_run": result.get("dry_run"), "status_code": result.get("status_code"), "outcome": outcome},
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


def _context_without_unresolved_path_endpoints(context: dict[str, Any]) -> dict[str, Any]:
    cloned = dict(context)
    endpoints = []
    for endpoint in context.get("endpoint_candidates", []):
        path = str(endpoint.get("path") or "")
        if "{" in path or "}" in path:
            continue
        endpoints.append(endpoint)
    cloned["endpoint_candidates"] = endpoints
    return cloned


def _last_validation(repair: dict[str, Any]) -> dict[str, Any] | None:
    attempts = repair.get("attempts")
    if isinstance(attempts, list) and attempts:
        validation = attempts[-1].get("validation")
        return validation if isinstance(validation, dict) else None
    return None


def _sum_usage_tokens(items: list[dict[str, Any]]) -> int | None:
    total = 0
    seen = False
    for item in items:
        usage = item.get("_usage") if isinstance(item, dict) else None
        if isinstance(usage, dict) and isinstance(usage.get("total_tokens"), (int, float)):
            total += int(usage["total_tokens"])
            seen = True
    return total if seen else None


class _UnavailableLLMClient:
    def available(self) -> bool:
        return False

    def provider_name(self) -> str:
        return "deterministic_backend_answer"

    def model_name(self) -> str:
        return "none"


def _trace_assertions(plan: dict[str, Any], steps: list[dict[str, Any]], answer_payload: dict[str, Any]) -> dict[str, Any]:
    sql_step = next((step for step in steps if step.get("kind") == "sql_call"), {})
    api_step = next((step for step in steps if step.get("kind") == "api_call"), {})
    sql_validation = sql_step.get("validation") if isinstance(sql_step.get("validation"), dict) else {}
    api_validation = api_step.get("validation") if isinstance(api_step.get("validation"), dict) else {}
    sql_result = sql_step.get("result") if isinstance(sql_step.get("result"), dict) else {}
    api_result = api_step.get("result") if isinstance(api_step.get("result"), dict) else {}
    attempts = sql_step.get("attempts") if isinstance(sql_step.get("attempts"), list) else []
    final_attempt = attempts[-1] if attempts else {}
    compile_result = final_attempt.get("compile") if isinstance(final_attempt.get("compile"), dict) else {}
    plan_validation = final_attempt.get("plan_validation") if isinstance(final_attempt.get("plan_validation"), dict) else {}
    selected_tool = None
    if sql_step:
        selected_tool = "execute_sql"
    elif api_step:
        selected_tool = "call_api"
    return {
        "did_llm_plan": bool(plan),
        "did_llm_choose_tool": bool(sql_step or api_step),
        "selected_tool": selected_tool,
        "sql_candidate": sql_step.get("sql"),
        "sql_validation_ok": bool(sql_validation.get("ok")),
        "structured_plan_compile_ok": bool(compile_result.get("ok")) if compile_result else None,
        "structured_plan_validation_ok": bool(plan_validation.get("ok")) if plan_validation else None,
        "sql_repair_attempted": int(sql_step.get("repair_rounds") or 0) > 0,
        "sql_repair_success": bool(sql_validation.get("ok")) and int(sql_step.get("repair_rounds") or 0) > 0,
        "api_endpoint_candidate": api_step.get("endpoint_candidate"),
        "api_endpoint_repair_attempted": bool(api_step.get("retry_attempted")),
        "api_endpoint_validation_ok": bool(api_validation.get("ok")),
        "tool_execution_ok": bool(sql_result.get("ok") or api_result.get("ok")),
        "tool_result_used_in_answer": bool(answer_payload.get("tool_result_used")),
        "unsupported_claim_count": int(answer_payload.get("unsupported_claim_count") or 0),
        "rejected_unsupported_claim_count": int(answer_payload.get("rejected_unsupported_claim_count") or 0),
        "final_answer": answer_payload.get("answer"),
    }


def _failure_stage_from_assertions(trace: dict[str, Any]) -> str:
    if not trace.get("did_llm_plan"):
        return "planning_failed"
    if not trace.get("did_llm_choose_tool"):
        return "no_tool_called_when_needed"
    if trace.get("selected_tool") == "execute_sql" and not trace.get("sql_validation_ok"):
        return "invalid_sql" if not trace.get("sql_repair_attempted") else "sql_repair_failed"
    if trace.get("selected_tool") == "call_api" and not trace.get("api_endpoint_validation_ok"):
        return "api_validation_failed"
    if not trace.get("tool_execution_ok"):
        return "tool_execution_failed"
    if trace.get("unsupported_claim_count"):
        return "unsupported_claim_added"
    if not trace.get("tool_result_used_in_answer"):
        return "tool_result_ignored"
    return "no_clear_failure"
