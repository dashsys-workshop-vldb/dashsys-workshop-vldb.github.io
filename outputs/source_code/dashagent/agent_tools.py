from __future__ import annotations

from typing import Any

from .answer_intent import classify_answer_intent
from .answer_slots import extract_answer_slots
from .answer_verifier import safe_rewrite, verify_answer
from .call_budget import budget_for_strategy
from .checkpoints import CheckpointLogger
from .config import Config
from .executor import AgentExecutor, render_system_prompt, slugify
from .plan_ensemble import select_plan_candidate
from .query_analysis import analyze_query
from .query_normalizer import normalize_query
from .query_tokens import extract_query_tokens
from .simple_prompt_gate import decide_simple_prompt
from .trajectory import compact_preview, estimate_tokens


DEFAULT_AGENT_STRATEGY = "SQL_FIRST_API_VERIFY"


def analyze_query_tool(query: str, *, config: Config | None = None) -> dict[str, Any]:
    executor = AgentExecutor(config)
    checkpoints = CheckpointLogger(max_preview_chars=executor.config.max_preview_chars)
    checkpoints.add_checkpoint(
        "checkpoint_01_raw_query",
        stage="input",
        technique="raw user query capture",
        output={"query": query, "strategy": DEFAULT_AGENT_STRATEGY},
    )
    gate = decide_simple_prompt(query)
    checkpoints.add_checkpoint(
        "checkpoint_simple_prompt_gate",
        stage="input routing",
        technique="simple prompt gate",
        output=gate.to_dict(),
        correctness_role="routes data questions to the evidence pipeline",
        efficiency_role="allows safe conceptual prompts to avoid data tools",
    )
    normalization = normalize_query(query)
    tokens = extract_query_tokens(query, normalization)
    routing = executor.router.route(normalization["matching_text"])
    analysis = analyze_query(
        query,
        routing,
        executor.schema_index,
        strategy=DEFAULT_AGENT_STRATEGY,
        config=executor.config,
        endpoint_catalog=executor.endpoint_catalog,
        normalized=normalization,
        tokens=tokens,
    )
    checkpoints.add_checkpoint(
        "checkpoint_02_query_normalization",
        stage="normalization",
        technique="data cleaning / query normalization",
        output={
            "normalized_query": normalization.get("normalized"),
            "matching_text": normalization.get("matching_text"),
            "rewrites": normalization.get("rewrites", []),
        },
    )
    checkpoints.add_checkpoint(
        "checkpoint_03_query_tokens",
        stage="tokenization",
        technique="domain-aware tokenization/entity extraction",
        output=tokens.compact(),
    )
    checkpoints.add_checkpoint(
        "checkpoint_05_query_analysis",
        stage="routing",
        technique="branch prediction / QueryAnalysis",
        output={
            "route_type": analysis.route_type,
            "domain_type": analysis.domain_type,
            "answer_family": analysis.answer_family,
            "likely_strategy": DEFAULT_AGENT_STRATEGY,
            "confidence": round(float(analysis.confidence), 4),
            "fast_path": analysis.fast_path.family if analysis.fast_path else None,
        },
    )
    return {
        "normalized_query": normalization,
        "tokens": tokens.compact(),
        "route_type": analysis.route_type,
        "domain_type": analysis.domain_type,
        "answer_family": analysis.answer_family,
        "likely_strategy": DEFAULT_AGENT_STRATEGY,
        "database_api_pipeline_needed": gate.suggested_action == "USE_DATA_PIPELINE",
        "simple_prompt_gate": gate.to_dict(),
        "checkpoints": checkpoints.to_list(),
    }


def plan_data_answer_tool(query: str, *, config: Config | None = None) -> dict[str, Any]:
    executor = AgentExecutor(config)
    qid = slugify(query)
    normalization = normalize_query(query)
    tokens = extract_query_tokens(query, normalization)
    routing = executor.router.route(normalization["matching_text"])
    analysis = analyze_query(
        query,
        routing,
        executor.schema_index,
        strategy=DEFAULT_AGENT_STRATEGY,
        config=executor.config,
        endpoint_catalog=executor.endpoint_catalog,
        normalized=normalization,
        tokens=tokens,
    )
    metadata = executor.metadata_selector.select(
        query,
        routing,
        strategy=DEFAULT_AGENT_STRATEGY,
        query_id=qid,
        analysis=analysis,
    )
    plan = executor.planner.create_plan(query, routing, metadata, DEFAULT_AGENT_STRATEGY, analysis=analysis)
    selection = select_plan_candidate(
        query=query,
        routing=routing,
        base_plan=plan,
        analysis=analysis,
        sql_validator=executor.sql_validator,
        api_validator=executor.api_validator,
        strategy=DEFAULT_AGENT_STRATEGY,
    )
    optimized_plan = selection.plan
    api_families = [step.family for step in optimized_plan.steps if step.action == "api" and step.family]
    budget = budget_for_strategy(DEFAULT_AGENT_STRATEGY, api_families, analysis.api_need_decision.max_api_calls)
    checkpoints = CheckpointLogger(max_preview_chars=executor.config.max_preview_chars)
    checkpoints.add_checkpoint(
        "checkpoint_07_context_card",
        stage="metadata packing",
        technique="huge-page-style compact context card",
        output={
            "selected_tables": metadata.get("selected_tables", []),
            "selected_apis": [api.get("id") or api.get("path") for api in metadata.get("selected_apis", [])],
            "estimated_metadata_tokens": estimate_tokens(metadata),
            "prompt_tokens": estimate_tokens(render_system_prompt(executor.config, metadata)),
        },
    )
    checkpoints.add_checkpoint(
        "checkpoint_08_candidate_plans",
        stage="planning",
        technique="pre-execution plan ensemble",
        output=selection.compact(),
        effect="executes only the selected plan",
    )
    checkpoints.add_checkpoint(
        "checkpoint_10_evidence_policy",
        stage="evidence policy",
        technique="API_REQUIRED/API_OPTIONAL/API_SKIP policy",
        output=analysis.api_need_decision.to_dict(),
    )
    checkpoints.add_checkpoint(
        "checkpoint_11_call_budget",
        stage="efficiency control",
        technique="tool-call budgeting",
        output={
            "max_sql_calls": budget.max_sql_calls,
            "max_api_calls": budget.max_api_calls,
            "max_total_tool_calls": budget.max_total_tool_calls,
            "final_planned_calls": len(optimized_plan.steps),
        },
    )
    return {
        "selected_metadata": compact_preview(metadata),
        "candidate_plan": selection.compact(),
        "optimized_plan": optimized_plan.to_dict(),
        "evidence_policy": analysis.api_need_decision.to_dict(),
        "call_budget": {
            "max_sql_calls": budget.max_sql_calls,
            "max_api_calls": budget.max_api_calls,
            "max_total_tool_calls": budget.max_total_tool_calls,
        },
        "checkpoints": checkpoints.to_list(),
    }


def run_data_answer_tool(query: str, *, config: Config | None = None, query_id: str | None = None) -> dict[str, Any]:
    result = AgentExecutor(config).run(query, strategy=DEFAULT_AGENT_STRATEGY, query_id=query_id)
    return {
        "final_answer": result["final_answer"],
        "trajectory": result["trajectory"],
        "checkpoints": result.get("checkpoints") or result["trajectory"].get("checkpoints", []),
        "tool_results_summary": compact_preview(result.get("tool_results", [])),
        "diagnostics": {
            "tool_call_count": result["trajectory"].get("tool_call_count"),
            "estimated_tokens": result["trajectory"].get("estimated_tokens"),
            "runtime": result["trajectory"].get("runtime"),
        },
    }


def verify_answer_tool(query: str, answer: str, evidence: dict[str, Any] | list[dict[str, Any]]) -> dict[str, Any]:
    if isinstance(evidence, dict):
        tool_results = evidence.get("tool_results") or evidence.get("results") or []
    else:
        tool_results = evidence
    slots = extract_answer_slots(query, tool_results if isinstance(tool_results, list) else [])
    intent = classify_answer_intent(query, slots)
    verification = verify_answer(answer, slots)
    safer = None
    if not verification.ok:
        safer = safe_rewrite(query, slots, intent, slots.answer_family)
    return {
        "verifier_passed": verification.ok,
        "supported_claims_count": max(0, len(answer.split(".")) - verification.unsupported_count),
        "unsupported_claims": [
            {"type": claim.claim_type, "value": claim.value}
            for claim in verification.unsupported_claims
        ],
        "errors": verification.errors,
        "warnings": verification.warnings,
        "missing_evidence": verification.errors,
        "safer_rewritten_answer": safer,
    }
