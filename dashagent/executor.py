from __future__ import annotations

import json
import re
import time
import copy
from pathlib import Path
from typing import Any

from .answer_claims import extract_claims
from .answer_intent import classify_answer_intent
from .answer_candidate_selector import select_answer_candidate
from .answer_slots import extract_answer_slots
from .api_request_gate import APIRequestGate, APIRequestGateResult
from .api_templates import find_api_templates
from .answer_shape import propose_answer_shape_candidate
from .answer_synthesizer import AnswerResult, synthesize_answer_with_diagnostics
from .answer_verifier import verify_answer
from .api_client import AdobeAPIClient
from .broad_question_classifier import classify_broad_question
from .cache import (
    api_response_cache_key,
    current_fingerprint,
    get_api_response_cache,
    get_query_analysis_cache,
    get_sql_result_cache,
    load_schema_index_from_cache,
    query_analysis_cache_key,
    set_api_response_cache,
    set_query_analysis_cache,
    set_sql_result_cache,
    sql_result_cache_key,
    write_cache_manifest,
)
from .candidate_context_builder import build_adaptive_context, build_candidate_context, build_full_schema_context
from .call_budget import budget_for_strategy
from .checkpoints import CheckpointLogger
from .concise_llm_answer_rewriter import rewrite_concise_answer
from .concise_rewrite_card import build_concise_rewrite_card
from .concise_rewrite_eligibility import decide_concise_rewrite_eligibility
from .concise_rewrite_selector import select_concise_rewrite
from .config import (
    Config,
    DEFAULT_CONFIG,
    ROBUST_GENERALIZED_HARNESS_CANDIDATE,
    ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2,
    SQL_FIRST_API_VERIFY_CONCISE_LLM_REWRITE,
    SQL_FIRST_API_VERIFY_HYBRID_ANSWER,
    SQL_FIRST_API_VERIFY_LLM_ANSWER_VERIFIER,
    robust_generalized_candidate_config,
    robust_generalized_v2_config,
    sql_first_concise_llm_rewrite_config,
    sql_first_hybrid_answer_config,
    sql_first_llm_answer_verifier_config,
)
from .core_tool_policy import compact_api_outcome
from .db import DuckDBDatabase
from .endpoint_catalog import EndpointCatalog
from .evidence_match_scorer import score_evidence_match
from .evidence_bus import EvidenceBus
from .evidence_grounded_answer_builder import build_evidence_grounded_answer
from .evidence_grounded_llm_answer_generator import generate_evidence_grounded_llm_answer
from .evidence_policy import API_SKIP
from .evidence_quality_classifier import classify_evidence_quality
from .gated_sql_candidates import hard_case_triggers, select_gated_sql_candidate
from .hybrid_answer_composer import compose_hybrid_answer
from .metadata_selector import MetadataSelector
from .pass_graph_gate import PassGraphGate, PassGraphGateResult
from .plan_ensemble import select_plan_candidate
from .planner import (
    ALL_STRATEGIES,
    LLM_SQL_STRATEGIES,
    PACKAGED_DEFAULT_STRATEGY,
    Plan,
    PlanStep,
    STRATEGIES,
    StrategyPlanner,
    execution_base_strategy,
)
from .pre_evidence_routing_boundary import should_bypass_evidence_for_llm_direct
from .query_normalizer import normalize_query
from .query_tokens import extract_query_tokens
from .llm_sql_generator import generate_sql_with_llm, repair_sql_with_llm
from .llm_final_answer_composer import (
    build_llm_final_answer_card,
    check_final_answer_semantic_grounding,
    check_final_answer_syntax,
    compose_llm_final_answer,
    safe_llm_final_answer_fallback,
)
from .llm_unified_planner import LLMUnifiedAPIRequest, LLMUnifiedPass, LLMUnifiedPlan, LLMUnifiedSQLCandidate, run_llm_unified_planner
from .query_decomposer import decompose_query
from .query_family_examples import examples_for_family, few_shot_public_overlap_check
from .query_analysis import analyze_query
from .risk_efficiency_controller import classify_candidate_risk
from .result_bundle import ResultBundle
from .router import QueryRouter
from .runtime_leakage_guard import runtime_guard_checkpoint, score_provenance_runtime_checkpoint
from .schema_context_voter import vote_schema_contexts
from .schema_index import SchemaIndex
from .semantic_routing_helper import apply_semantic_routing_hint, run_semantic_routing_helper
from .prompt_semantic_ir import extract_objective_prompt_features
from .routing_anti_hallucination_gate import run_routing_gate_with_revision
from .semantic_intent_classifier import classify_semantic_intent
from .semantic_intent_context_builder import build_semantic_intent_context, estimate_context_tokens
from .semantic_route_decision_ladder import run_semantic_route_decision_ladder, validate_llm_safe_direct_answer
from .semantic_parser import parse_prompt_semantics
from .no_tool_safety_verifier import verify_no_tool_safety
from .post_sql_api_call_verifier import verify_post_sql_api_advice
from .post_sql_decision_card import build_post_sql_decision_card
from .post_sql_deterministic_policy import decide_post_sql_api_policy
from .post_sql_llm_advisor import advise_post_sql_api
from .post_sql_llm_decision import run_post_sql_llm_first_decision
from .post_sql_semantic_decision_card import build_post_sql_semantic_decision_card
from .simple_prompt_gate import decide_simple_prompt
from .staged_evidence_policy import decide_initial_evidence_branch
from .sql_compile_gate import SQLCompileGate, SQLCompileGateResult
from .sql_only_api_skip_guard import should_skip_api_with_sql_evidence
from .prompt_router import LLM_DIRECT, route_prompt
from .trajectory import TrajectoryLogger, compact_preview, estimate_tokens
from .token_reduction_policy import apply_token_reduction_to_trajectory
from .validators import APIValidator, SQLValidator, ValidationResult
from .v2_execution_optimizer import BudgetLimits, V2ExecutionOptimizer
from .v2_pipeline_scheduler import V2PipelineScheduler
from .v2_run_context import RunBudget, RunContext, create_run_context
from .value_retrieval import build_value_index, extract_query_values, retrieve_value_matches, value_retrieval_summary


def _normalize_probe_path(value: str) -> str:
    text = str(value or "")
    match = re.search(r"https?://[^/]+(?P<path>/.*)", text)
    if match:
        text = match.group("path")
    if "?" in text:
        text = text.split("?", 1)[0]
    return text.rstrip("/")


def _can_skip_llm_answer_generation(selection: Any) -> bool:
    if selection is None or int(getattr(selection, "unsupported_claims", 1) or 0) != 0:
        return False
    selected_source = str(getattr(selection, "selected_source", ""))
    if selected_source not in {"LEGACY_SAFE_RENDERER", "DETERMINISTIC_FALLBACK"}:
        return False
    for candidate in getattr(selection, "candidates", []) or []:
        if str(candidate.get("source")) == selected_source:
            if selected_source == "LEGACY_SAFE_RENDERER":
                return float(candidate.get("coverage_score", 0.0) or 0.0) >= 0.0
            return not candidate.get("missing_roles") and float(candidate.get("coverage_score", 0.0) or 0.0) >= 1.0
    return False


def _skipped_llm_answer_payload(skipped: bool) -> dict[str, Any] | None:
    if not skipped:
        return None
    return {
        "llm_backend_used": False,
        "llm_skipped": True,
        "skip_reason": "PREVERIFIED_LEGACY_OR_DETERMINISTIC_ANSWER_SELECTED",
        "first_pass_ok": True,
        "rewrite_attempted": False,
        "rewrite_success": False,
        "fallback_used": False,
        "feedback": {},
        "verification": {
            "ok": True,
            "action": "ACCEPT_PREVERIFIED_NON_LLM_ANSWER",
            "unsupported_claims": [],
            "over_specified_claims": [],
            "needs_caveat_claims": [],
            "claim_extractor": {},
            "claim_matcher": {},
            "allowed_fact_index": {},
        },
    }


class AgentExecutor:
    def __init__(
        self,
        config: Config | None = None,
        db: DuckDBDatabase | None = None,
        schema_index: SchemaIndex | None = None,
        endpoint_catalog: EndpointCatalog | None = None,
        api_client: AdobeAPIClient | None = None,
    ) -> None:
        self.config = config or DEFAULT_CONFIG
        self.config.ensure_dirs()
        self.db = db or DuckDBDatabase(self.config)
        if schema_index is not None:
            self.schema_index = schema_index
        else:
            cached_schema = load_schema_index_from_cache(self.config)
            self.schema_index = cached_schema or SchemaIndex.build(self.db)
            if cached_schema is None:
                self.schema_index.save(self.config)
                write_cache_manifest(self.config)
        self.endpoint_catalog = endpoint_catalog or EndpointCatalog(self.config)
        self.api_client = api_client or AdobeAPIClient(self.config)
        self.router = QueryRouter(self.db.list_tables(), self.endpoint_catalog)
        self.metadata_selector = MetadataSelector(self.schema_index, self.endpoint_catalog, self.config)
        self.planner = StrategyPlanner(self.schema_index, self.config)
        self.sql_validator = SQLValidator(self.schema_index, enable_ast_validation=self.config.enable_sql_ast_validation)
        self.sql_compile_gate = SQLCompileGate(self.db)
        self.pass_graph_gate = PassGraphGate()
        self.api_validator = APIValidator(
            self.endpoint_catalog,
            allow_unknown=self.config.allow_unknown_api_endpoints,
        )
        self.api_request_gate = APIRequestGate(self.api_validator)
        self.v2_execution_optimizer = V2ExecutionOptimizer()
        self.v2_pipeline_scheduler = V2PipelineScheduler()
        self.cache_fingerprint = current_fingerprint(self.config)

    def run(
        self,
        query: str,
        *,
        strategy: str = PACKAGED_DEFAULT_STRATEGY,
        query_id: str | None = None,
        output_dir: Path | None = None,
    ) -> dict[str, Any]:
        if strategy not in ALL_STRATEGIES:
            raise ValueError(f"Unknown strategy {strategy}. Expected one of {ALL_STRATEGIES}.")
        original_config = self.config
        if strategy == ROBUST_GENERALIZED_HARNESS_CANDIDATE and self.config.real_behavior_trial_mode != ROBUST_GENERALIZED_HARNESS_CANDIDATE:
            self.config = robust_generalized_candidate_config(self.config)
        if strategy == ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2 and self.config.real_behavior_trial_mode != ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2:
            self.config = robust_generalized_v2_config(self.config)
        if (
            strategy == SQL_FIRST_API_VERIFY_LLM_ANSWER_VERIFIER
            and self.config.real_behavior_trial_mode != SQL_FIRST_API_VERIFY_LLM_ANSWER_VERIFIER
        ):
            self.config = sql_first_llm_answer_verifier_config(self.config)
        if (
            strategy == SQL_FIRST_API_VERIFY_HYBRID_ANSWER
            and self.config.real_behavior_trial_mode != SQL_FIRST_API_VERIFY_HYBRID_ANSWER
        ):
            self.config = sql_first_hybrid_answer_config(self.config)
        if (
            strategy == SQL_FIRST_API_VERIFY_CONCISE_LLM_REWRITE
            and self.config.real_behavior_trial_mode != SQL_FIRST_API_VERIFY_CONCISE_LLM_REWRITE
        ):
            self.config = sql_first_concise_llm_rewrite_config(self.config)
        try:
            return self._run_with_active_config(query, strategy=strategy, query_id=query_id, output_dir=output_dir)
        finally:
            self.config = original_config

    def _run_with_active_config(
        self,
        query: str,
        *,
        strategy: str,
        query_id: str | None = None,
        output_dir: Path | None = None,
    ) -> dict[str, Any]:
        execution_strategy = execution_base_strategy(strategy)
        qid = query_id or slugify(query)
        out_dir = output_dir or (self.config.outputs_dir / qid / strategy.lower())
        out_dir.mkdir(parents=True, exist_ok=True)
        checkpoint_preview_chars = self.config.max_preview_chars
        if strategy == ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2:
            checkpoint_preview_chars = max(checkpoint_preview_chars, 4000)
        checkpoint_logger = CheckpointLogger(max_preview_chars=checkpoint_preview_chars)
        checkpoint_logger.add_checkpoint(
            "checkpoint_01_raw_query",
            stage="input",
            technique="raw user query capture",
            output={"query_id": qid, "query": query, "strategy": strategy},
            effect="preserves the original query for reproducibility",
            correctness_role="keeps later normalization from changing the user-facing question",
            efficiency_role="starts one trace without extra tool calls",
        )
        if self.config.enable_runtime_leakage_guard:
            checkpoint_logger.add_checkpoint(
                "checkpoint_runtime_leakage_guard",
                stage="runtime safety",
                technique="runtime input isolation guard",
                input_summary={"strategy": strategy},
                output=runtime_guard_checkpoint(strategy=strategy, query_id=qid, query=query),
                effect="asserts that candidate runtime receives only prompt/runtime fields, not evaluator metadata",
                correctness_role="prevents evaluator-only metadata leakage into runtime decisions",
                efficiency_role="adds no tool calls",
            )
        if self.config.enable_score_provenance_guard:
            checkpoint_logger.add_checkpoint(
                "checkpoint_score_provenance_guard",
                stage="runtime safety",
                technique="score provenance guard",
                input_summary={"strategy": strategy},
                output=score_provenance_runtime_checkpoint(strategy=strategy),
                effect="marks candidate runs as real-agent runtime executions without promotion judgment",
                correctness_role="prevents simulated or gold-visible scores from being treated as runtime evidence",
                efficiency_role="adds no tool calls",
            )
        if strategy == ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2:
            return self._run_llm_owned_v2(
                query=query,
                qid=qid,
                strategy=strategy,
                out_dir=out_dir,
                checkpoint_logger=checkpoint_logger,
            )
        prompt_route = route_prompt(query)
        checkpoint_logger.add_checkpoint(
            "checkpoint_00_prompt_router",
            stage="prompt routing",
            technique="LLM_DIRECT / LOCAL_DB_ONLY / SQL_PLUS_API / API_ONLY routing policy",
            input_summary={"query": query},
            output=prompt_route.to_dict(),
            effect="chooses whether the prompt can be answered directly or needs SQL/API evidence",
            correctness_role="routes data questions to evidence tools instead of unsupported direct answers",
            efficiency_role="allows clearly conceptual prompts to avoid unnecessary SQL/API calls",
        )
        simple_decision = decide_simple_prompt(query)
        checkpoint_logger.add_checkpoint(
            "checkpoint_simple_prompt_gate",
            stage="input routing",
            technique="simple prompt gate",
            input_summary={"query": query},
            output=simple_decision.to_dict(),
            effect="lets an LLM wrapper answer conceptual questions directly while sending evidence questions to the backend",
            correctness_role="prevents direct answers for data questions that need SQL/API evidence",
            efficiency_role="can skip the data pipeline only for safe conceptual prompts",
        )
        semantic_ladder = self._add_semantic_route_harness_checkpoints(query, checkpoint_logger)
        semantic_trial_decision = self._semantic_no_tool_applied_decision(
            semantic_ladder,
            query=query,
            strategy=self.config.real_behavior_trial_mode or strategy,
        )
        if semantic_trial_decision.get("record"):
            checkpoint_logger.add_checkpoint(
                "checkpoint_real_behavior_applied_trial",
                stage="isolated applied trial",
                technique="semantic no-tool applied trial",
                input_summary={"trial_mode": self.config.real_behavior_trial_mode},
                output=semantic_trial_decision,
                effect="applies a semantic no-tool shortcut only in explicit real benchmark trial modes",
                correctness_role="falls back to SQL_FIRST_API_VERIFY unless all no-tool safety checks pass",
                efficiency_role="measures real tool-call savings for conceptual false-positive routes",
            )
        if semantic_trial_decision.get("applied"):
            return self._return_semantic_no_tool_applied_result(
                query=query,
                qid=qid,
                strategy=strategy,
                out_dir=out_dir,
                prompt_route=prompt_route,
                checkpoint_logger=checkpoint_logger,
                trial_decision=semantic_trial_decision,
            )
        safe_probe_decision = self._semantic_safe_api_probe_applied_decision(semantic_ladder)
        if safe_probe_decision.get("record"):
            checkpoint_logger.add_checkpoint(
                "checkpoint_safe_api_probe",
                stage="semantic routing applied candidate",
                technique="safe one-endpoint API probe",
                input_summary={"trial_mode": self.config.real_behavior_trial_mode},
                output=safe_probe_decision,
                effect="applies SAFE_API_PROBE only for one catalog GET endpoint with no unresolved path params",
                correctness_role="keeps probe evidence constrained by endpoint catalog and API validator",
                efficiency_role="caps the probe at one API call",
            )
        if safe_probe_decision.get("applied"):
            return self._return_safe_api_probe_result(
                query=query,
                qid=qid,
                strategy=strategy,
                out_dir=out_dir,
                prompt_route=prompt_route,
                checkpoint_logger=checkpoint_logger,
                probe_decision=safe_probe_decision,
            )
        if prompt_route.mode == LLM_DIRECT:
            metadata = {
                "query_id": qid,
                "query": query,
                "strategy": strategy,
                "prompt_route": prompt_route.to_dict(),
                "note": "Conceptual prompt routed for direct LLM handling; deterministic backend did not execute SQL/API tools.",
            }
            self.metadata_selector.save(metadata, out_dir)
            filled_prompt = render_system_prompt(self.config, metadata)
            (out_dir / "filled_system_prompt.txt").write_text(filled_prompt, encoding="utf-8")
            final_answer = (
                "This is a conceptual prompt that does not require local SQL or Adobe API evidence. "
                "Use the optimized LLM controller mode for a real direct LLM response; the deterministic backend skipped SQL/API calls."
            )
            trajectory = TrajectoryLogger(
                query_id=qid,
                original_query=query,
                strategy=strategy,
                route_type="LLM_DIRECT",
                domain_type="CONCEPTUAL",
                max_preview_chars=self.config.max_preview_chars,
            )
            trajectory.add_step("prompt_router", prompt_route.to_dict())
            trajectory.add_step("metadata", {"estimated_tokens": estimate_tokens(metadata), "prompt_tokens": estimate_tokens(filled_prompt), "metadata_path": str(out_dir / "metadata.json")})
            checkpoint_logger.add_checkpoint(
                "checkpoint_18_final_answer",
                stage="final response",
                technique="deterministic no-key direct fallback",
                output={"final_answer": final_answer, "answer_length": len(final_answer), "final_token_estimate": estimate_tokens(final_answer)},
                effect="returns a safe no-tool fallback for conceptual prompts",
                correctness_role="does not invent local DB/API evidence",
                efficiency_role="uses zero SQL/API tool calls",
            )
            trajectory.set_checkpoints(checkpoint_logger.to_list())
            trajectory_payload = trajectory.save(out_dir / "trajectory.json", final_answer)
            return {
                "query_id": qid,
                "query": query,
                "strategy": strategy,
                "output_dir": str(out_dir),
                "metadata": metadata,
                "plan": {"strategy": strategy, "rationale": "LLM_DIRECT prompt; deterministic backend skipped data tools.", "steps": []},
                "tool_results": [],
                "final_answer": final_answer,
                "checkpoints": checkpoint_logger.to_list(),
                "trajectory": trajectory_payload,
            }

        preprocessing_start = time.perf_counter()
        normalization = normalize_query(query)
        checkpoint_logger.add_checkpoint(
            "checkpoint_02_query_normalization",
            stage="normalization",
            technique="data cleaning / query normalization",
            input_summary={"query": query},
            output={
                "normalized_query": normalization.get("normalized"),
                "matching_text": normalization.get("matching_text"),
                "rewrites": normalization.get("rewrites", []),
            },
            effect="creates matching-friendly text while preserving the original query",
            correctness_role="improves template and route matching across wording variants",
            efficiency_role="reduces repeated fuzzy matching work downstream",
        )
        tokens = extract_query_tokens(query, normalization)
        checkpoint_logger.add_checkpoint(
            "checkpoint_03_query_tokens",
            stage="tokenization",
            technique="domain-aware tokenization/entity extraction",
            input_summary={"normalized_query": normalization.get("normalized")},
            output=tokens.compact(),
            effect="extracts reusable query fields for routing, planning, and answers",
            correctness_role="grounds names, IDs, dates, metrics, and statuses before planning",
            efficiency_role="avoids reparsing the query in later modules",
        )
        routing = self.router.route(normalization["matching_text"])
        analysis_key = query_analysis_cache_key(query, execution_strategy, self.config, self.cache_fingerprint)
        analysis = get_query_analysis_cache(analysis_key)
        if analysis is None:
            analysis = analyze_query(
                query,
                routing,
                self.schema_index,
                strategy=execution_strategy,
                config=self.config,
                endpoint_catalog=self.endpoint_catalog,
                normalized=normalization,
                tokens=tokens,
            )
            set_query_analysis_cache(analysis_key, analysis)
        semantic_routing_result = None
        if self.config.enable_llm_semantic_router:
            semantic_routing_result = run_semantic_routing_helper(
                user_prompt=query,
                normalization=normalization,
                tokens=tokens,
                routing=routing,
                analysis=analysis,
                schema_index=self.schema_index,
                endpoint_catalog=self.endpoint_catalog,
                config=self.config,
            )
            if not self.config.llm_semantic_router_shadow_only:
                routing, analysis, semantic_routing_result = apply_semantic_routing_hint(
                    routing=routing,
                    analysis=analysis,
                    result=semantic_routing_result,
                    config=self.config,
                    endpoint_catalog=self.endpoint_catalog,
                )
            checkpoint_logger.add_checkpoint(
                "checkpoint_llm_semantic_routing_helper",
                stage="routing",
                technique="feature-flagged SDK LLM semantic routing helper",
                input_summary={
                    "route_type": semantic_routing_result.deterministic_route_type,
                    "domain_type": semantic_routing_result.deterministic_domain_type,
                    "confidence": round(float(semantic_routing_result.deterministic_confidence_before), 4),
                },
                output=semantic_routing_result.to_checkpoint(),
                effect="optionally records validated semantic routing hints for low-confidence or ambiguous prompts",
                correctness_role="keeps deterministic routing first and never produces final answers or bypasses validators",
                efficiency_role="calls the LLM only behind an explicit feature flag and only when eligibility rules trigger",
            )
        relevance_compact = analysis.relevance.compact(table_k=3, api_k=3)
        checkpoint_logger.add_checkpoint(
            "checkpoint_04_relevance_scoring",
            stage="context selection",
            technique="attention-style relevance scoring",
            input_summary={"tokens": tokens.compact()},
            output={
                "top_tables": relevance_compact.get("tables", []),
                "top_apis": relevance_compact.get("apis", []),
                "top_join_hints": [item.name for item in analysis.relevance.join_hints[:3]],
                "top_answer_families": relevance_compact.get("answer_families", [analysis.answer_family]),
            },
            effect="selects a smaller, more relevant schema/API context",
            correctness_role="keeps high-signal tables and endpoints near the planner",
            efficiency_role="reduces metadata and prompt tokens when compact metadata is enabled",
        )
        value_retrieval = None
        if self.config.enable_value_retrieval:
            query_values = extract_query_values(query, tokens)
            if query_values:
                candidate_tables_for_values = [item.name for item in analysis.relevance.tables[: self.config.value_retrieval_max_tables]]
                value_index = build_value_index(
                    self.db,
                    self.schema_index,
                    self.config.outputs_dir / "cache",
                    candidate_tables=candidate_tables_for_values,
                    max_tables=self.config.value_retrieval_max_tables,
                    max_columns=self.config.value_retrieval_max_columns,
                    max_rows_per_column=self.config.value_retrieval_max_rows_per_column,
                    max_ms=self.config.value_retrieval_max_ms,
                )
                value_matches = retrieve_value_matches(query_values, value_index)
                value_retrieval = value_retrieval_summary(query_values, value_index, value_matches)
                checkpoint_logger.add_checkpoint(
                    "checkpoint_value_entity_retrieval",
                    stage="query understanding",
                    technique="CHESS-style value/entity retrieval",
                    input_summary={"query_values": [mention.to_dict() for mention in query_values]},
                    output=value_retrieval,
                    effect="grounds query entities against sampled local DB values before planning",
                    correctness_role="helps identify exact names, IDs, statuses, and metrics for SQL/API grounding",
                    efficiency_role="uses a cached bounded value index with per-query scan and wall-time budgets",
                    metrics={
                        "retrieval_ms": value_retrieval.get("retrieval_ms"),
                        "budget_exceeded": value_retrieval.get("value_retrieval_budget_exceeded"),
                        "match_count": value_retrieval.get("match_count"),
                    },
                )
        decomposition = None
        if self.config.enable_query_decomposition:
            decomposition = decompose_query(query, tokens)
            if decomposition.get("active"):
                checkpoint_logger.add_checkpoint(
                    "checkpoint_query_decomposition",
                    stage="query understanding",
                    technique="DIN-SQL-style deterministic query decomposition",
                    input_summary={"query": query, "tokens": tokens.compact()},
                    output=decomposition,
                    effect="breaks complex prompts into entities, filters, joins, and answer-shape constraints",
                    correctness_role="helps SQL/API planning preserve requested constraints",
                    efficiency_role="skips simple queries and uses no LLM/tool calls",
                )
        checkpoint_logger.add_checkpoint(
            "checkpoint_05_query_analysis",
            stage="routing",
            technique="branch prediction / QueryAnalysis",
            input_summary={"route_type": routing.route_type, "domain_type": routing.domain_type},
            output={
                "route_type": analysis.route_type,
                "domain_type": analysis.domain_type,
                "answer_family": analysis.answer_family,
                "strategy": strategy,
                "confidence": round(float(analysis.confidence), 4),
                "fast_path": analysis.fast_path.family if analysis.fast_path else None,
                "sql_template": analysis.sql_template.family if analysis.sql_template else None,
                "api_templates": [template.family for template in analysis.api_templates],
            },
            effect="computes shared query understanding once",
            correctness_role="aligns routing, metadata, planning, and reporting decisions",
            efficiency_role="avoids repeated template and routing analysis",
        )
        checkpoint_logger.add_checkpoint(
            "checkpoint_06_lookup_path",
            stage="path prediction",
            technique="TLB-style lookup path prediction",
            input_summary={"answer_family": analysis.answer_family, "domain_type": analysis.domain_type},
            output=analysis.lookup_path.to_dict(),
            effect="predicts the relevant table/join/API path",
            correctness_role="guides relationship-heavy SQL/API selection",
            efficiency_role="filters unrelated schema and endpoint candidates",
        )
        broad = strategy == "LLM_FREE_AGENT_BASELINE"
        compact_context_experiment = self._compact_context_experiment_candidate(
            query=query,
            strategy=strategy,
            output_dir=out_dir,
        )
        compact_context_override = (
            compact_context_experiment.get("compact_context")
            if compact_context_experiment.get("eligible")
            else None
        )
        metadata = self.metadata_selector.select(
            query,
            routing,
            strategy=strategy,
            query_id=qid,
            broad_context=broad,
            analysis=analysis,
            compact_context_override=compact_context_override,
        )
        self.metadata_selector.save(metadata, out_dir)

        filled_prompt = render_system_prompt(self.config, metadata)
        (out_dir / "filled_system_prompt.txt").write_text(filled_prompt, encoding="utf-8")
        context_card = metadata.get("context_card") if isinstance(metadata.get("context_card"), dict) else {}
        checkpoint_logger.add_checkpoint(
            "checkpoint_07_context_card",
            stage="metadata packing",
            technique="huge-page-style compact context card",
            input_summary={"lookup_path": analysis.lookup_path.family, "broad_context": broad},
            output={
                "selected_card_name": context_card.get("family") or context_card.get("name"),
                "selected_tables": metadata.get("selected_tables", []),
                "selected_columns": {
                    table: columns[:8] if isinstance(columns, list) else columns
                    for table, columns in metadata.get("selected_columns", {}).items()
                },
                "selected_apis": [api.get("id") or api.get("path") for api in metadata.get("selected_apis", [])],
                "estimated_metadata_tokens": estimate_tokens(metadata),
                "prompt_tokens": estimate_tokens(filled_prompt),
            },
            effect="packs family-relevant context into metadata.json and the filled prompt",
            correctness_role="keeps required tables, columns, joins, and API candidates visible",
            efficiency_role="limits context size for non-baseline strategies",
        )
        if compact_context_experiment.get("active"):
            checkpoint_logger.add_checkpoint(
                "checkpoint_compact_context_experiment",
                stage="metadata packing",
                technique="feature-flagged compact context measured experiment",
                input_summary={
                    "flag_enabled": self.config.enable_compact_context_when_schema_vote_safe,
                    "strategy": strategy,
                    "isolated_output_dir": _is_compact_experiment_output(out_dir, self.config.outputs_dir),
                },
                output={
                    key: value
                    for key, value in compact_context_experiment.items()
                    if key != "compact_context"
                },
                effect="uses compact candidate context only inside isolated measured experiment outputs when schema voting says it is safe",
                correctness_role="requires high-risk schema-vote agreement and disabled repair execution before experiment metadata changes",
                efficiency_role="measures prompt/context-token impact without changing packaged defaults",
            )
        preprocessing_time = time.perf_counter() - preprocessing_start

        planning_start = time.perf_counter()
        plan_strategy = "SQL_FIRST_API_VERIFY" if strategy in LLM_SQL_STRATEGIES else execution_strategy
        if strategy in LLM_SQL_STRATEGIES:
            plan = self._create_llm_sql_plan(query, routing, metadata, strategy, analysis, checkpoint_logger)
        else:
            plan = self.planner.create_plan(query, routing, metadata, plan_strategy, analysis=analysis)
        original_planned_step_count = len(plan.steps)
        ensemble_metadata = None
        if plan_strategy == "SQL_FIRST_API_VERIFY":
            selection = select_plan_candidate(
                query=query,
                routing=routing,
                base_plan=plan,
                analysis=analysis,
                sql_validator=self.sql_validator,
                api_validator=self.api_validator,
                strategy=strategy,
            )
            plan = selection.plan
            ensemble_metadata = selection.compact()
        candidate_output = ensemble_metadata or {
            "selected": "strategy_plan",
            "candidate_scores": {"strategy_plan": 1.0},
            "candidate_tool_calls": {"strategy_plan": len(plan.steps)},
        }
        checkpoint_logger.add_checkpoint(
            "checkpoint_08_candidate_plans",
            stage="planning",
            technique="pre-execution plan ensemble",
            input_summary={"strategy": strategy, "base_step_count": original_planned_step_count},
            output={
                "candidate_plan_names": list(candidate_output.get("candidate_scores", {}).keys()),
                "scores": candidate_output.get("candidate_scores", {}),
                "selected_plan": candidate_output.get("selected"),
                "reason_selected": "highest pre-execution validation/relevance/cost score"
                if ensemble_metadata
                else "strategy does not use ensemble selection",
            },
            effect="selects one plan before execution",
            correctness_role="prefers validated, family-matched plans",
            efficiency_role="does not execute losing candidate plans",
        )
        optimizer_actions = list(plan.optimizer_actions)
        checkpoint_logger.add_checkpoint(
            "checkpoint_09_plan_optimization",
            stage="optimization",
            technique="compiler-style plan optimization",
            input_summary={"original_step_count": original_planned_step_count},
            output={
                "original_step_count": original_planned_step_count,
                "optimized_step_count": len(plan.steps),
                "removed_duplicate_calls": count_actions(optimizer_actions, ["duplicate", "dedup"]),
                "removed_api_skip_calls": count_actions(optimizer_actions, ["api_skip", "skip"]),
                "unresolved_placeholders_removed": count_actions(optimizer_actions, ["placeholder", "unresolved"]),
                "call_budget_applied": any("budget" in action.lower() for action in optimizer_actions),
                "optimizer_actions": optimizer_actions[:8],
            },
            effect="removes duplicate, skippable, or unsafe calls before validation",
            correctness_role="drops unresolved placeholder calls unless explicitly warned",
            efficiency_role="enforces a bounded plan before execution",
        )
        checkpoint_logger.add_checkpoint(
            "checkpoint_10_evidence_policy",
            stage="evidence policy",
            technique="API_REQUIRED/API_OPTIONAL/API_SKIP policy",
            input_summary={"answer_family": analysis.answer_family, "route_type": routing.route_type},
            output=analysis.api_need_decision.to_dict(),
            effect="decides when API evidence is required, optional, or unnecessary",
            correctness_role="keeps API calls for API-only/live families",
            efficiency_role="skips or caps API calls when SQL evidence is enough",
        )
        api_families = [step.family for step in plan.steps if step.action == "api" and step.family]
        budget = budget_for_strategy(plan_strategy, api_families, analysis.api_need_decision.max_api_calls)
        checkpoint_logger.add_checkpoint(
            "checkpoint_11_call_budget",
            stage="efficiency control",
            technique="tool-call budgeting",
            input_summary={"planned_steps": [step.to_dict() for step in plan.steps]},
            output={
                "max_sql_calls": budget.max_sql_calls,
                "max_api_calls": budget.max_api_calls,
                "max_total_tool_calls": budget.max_total_tool_calls,
                "final_planned_calls": count_tool_plan_steps(plan.steps),
                "planned_sql_calls": sum(1 for step in plan.steps if step.action == "sql"),
                "planned_api_calls": sum(1 for step in plan.steps if step.action == "api"),
            },
            effect="keeps tool calls within per-family limits",
            correctness_role="preserves required grounding steps",
            efficiency_role="prevents accidental extra SQL/API calls",
        )
        self._add_staged_evidence_policy_checkpoints(query, analysis, plan, checkpoint_logger)
        if self.config.enable_gated_sql_candidates:
            pre_validation_failed = any(
                step.action == "sql" and step.sql and not self.sql_validator.validate(step.sql).ok
                for step in plan.steps
            )
            trigger_reasons = hard_case_triggers(
                validation_failed=pre_validation_failed,
                decomposition=decomposition,
                value_retrieval=value_retrieval,
            )
            gated_selection = select_gated_sql_candidate(
                query=query,
                plan=plan,
                sql_validator=self.sql_validator,
                expected_answer_shape=(decomposition or {}).get("expected_answer_shape", analysis.answer_family),
                trigger_reasons=trigger_reasons,
            )
            if gated_selection.get("active"):
                checkpoint_logger.add_checkpoint(
                    "checkpoint_gated_sql_candidate_selection",
                    stage="planning",
                    technique="hard-case gated SQL candidate validation",
                    input_summary={"trigger_reasons": trigger_reasons},
                    output=gated_selection,
                    effect="validates hard-case SQL candidates before execution without executing losing candidates",
                    correctness_role="selects only validator- and AST-passing SQL candidates",
                    efficiency_role="executes only one selected candidate in packaged SQL_FIRST_API_VERIFY mode",
                    metrics={
                        "candidate_count": gated_selection.get("candidate_count"),
                        "cost_estimate": gated_selection.get("cost_estimate"),
                    },
                )
        planning_time = time.perf_counter() - planning_start
        trajectory = TrajectoryLogger(
            query_id=qid,
            original_query=query,
            strategy=strategy,
            route_type=routing.route_type,
            domain_type=routing.domain_type,
            max_preview_chars=self.config.max_preview_chars,
        )
        trajectory.set_timing("preprocessing_time", preprocessing_time)
        trajectory.set_timing("planning_time", planning_time)
        trajectory.add_step("route", compact_routing_decision(routing.to_dict()))
        nlp_step = {
            "rewrites": analysis.normalization_rewrites[:3],
            "tokens": analysis.tokens.compact(),
            "relevance": {
                key: value[:2] if isinstance(value, list) else value
                for key, value in analysis.relevance.compact(table_k=2, api_k=2).items()
                if key in {"tables", "apis", "lookup_paths"}
            },
        }
        if value_retrieval:
            nlp_step["value_retrieval"] = {
                "match_count": value_retrieval.get("match_count"),
                "matches": value_retrieval.get("matches", [])[:5],
                "retrieval_ms": value_retrieval.get("retrieval_ms"),
                "budget_exceeded": value_retrieval.get("value_retrieval_budget_exceeded"),
            }
        if decomposition and decomposition.get("active"):
            nlp_step["decomposition"] = {
                "sub_questions": decomposition.get("sub_questions", [])[:5],
                "expected_answer_shape": decomposition.get("expected_answer_shape"),
            }
        if semantic_routing_result is not None:
            nlp_step["llm_semantic_routing_helper"] = semantic_routing_result.to_checkpoint()
        trajectory.add_step("nlp", {key: value for key, value in nlp_step.items() if value not in ([], {}, "", None)})
        trajectory.add_step(
            "metadata",
            {
                "estimated_tokens": estimate_tokens(metadata),
                "prompt_tokens": estimate_tokens(filled_prompt),
                "metadata_path": str(out_dir / "metadata.json"),
            },
        )
        trajectory.add_step("plan", plan.to_dict())
        if ensemble_metadata:
            trajectory.add_step("optimizer", {"plan_ensemble": ensemble_metadata})

        tool_results: list[dict[str, Any]] = []
        evidence_bus = EvidenceBus()
        validation_summaries: list[dict[str, Any]] = []
        sql_ast_summaries: list[dict[str, Any]] = []
        blocked_calls: list[dict[str, Any]] = []
        forwarding_actions_all: list[str] = []
        execution_start = time.perf_counter()
        per_query_api_response_cache: dict[str, dict[str, Any]] = {}
        for step in plan.steps:
            if step.action == "sql" and step.sql:
                validation = self.sql_validator.validate(step.sql)
                if not validation.ok:
                    repaired_sql = repair_sql(step.sql, validation, self.schema_index)
                    if repaired_sql and repaired_sql != step.sql:
                        repaired_validation = self.sql_validator.validate(repaired_sql)
                        trajectory.add_validation("sql_repair_attempt", repaired_validation)
                        if repaired_validation.ok:
                            step.sql = repaired_sql
                            validation = ValidationResult(True, warnings=["SQL repaired once."], repaired=True)
                if validation.ok:
                    cache_key = sql_result_cache_key(step.sql, self.config, self.cache_fingerprint)
                    result = get_sql_result_cache(cache_key)
                    if result is None:
                        result = self.db.execute_sql(step.sql, allow_full_result=step.allow_full_result)
                        set_sql_result_cache(cache_key, result)
                else:
                    result = {"ok": False, "rows": [], "row_count": 0, "error": "; ".join(validation.errors)}
                    blocked_calls.append({"type": "sql", "errors": validation.errors, "step": step.to_dict()})
                validation_summaries.append({"type": "sql", "ok": validation.ok, "warnings": validation.warnings, "errors": validation.errors})
                if self.config.enable_sql_ast_validation:
                    sql_ast_summaries.append(self.sql_validator.ast_summary(step.sql))
                trajectory.add_sql_call(step.sql, validation, result)
                tool_results.append({"type": "sql", "step": step.to_dict(), "validation": validation.to_dict(), "payload": result})
                evidence_bus.observe_sql(step, result)
            elif step.action == "api" and step.method and step.url:
                post_sql_decision = self._add_post_sql_api_decision_checkpoints(query, analysis, tool_results, step, checkpoint_logger)
                applied_api_decision = self._post_sql_api_applied_decision(post_sql_decision)
                if applied_api_decision.get("record"):
                    checkpoint_logger.add_checkpoint(
                        "checkpoint_real_behavior_applied_trial",
                        stage="isolated applied trial",
                        technique="post-SQL API decision applied trial",
                        input_summary={"trial_mode": self.config.real_behavior_trial_mode, "api_step": step.to_dict()},
                        output=applied_api_decision,
                        effect="applies deterministic post-SQL API keep/drop decisions only in explicit real benchmark trial modes",
                        correctness_role="preserves API-required and live/API prompts while testing optional API suppression",
                        efficiency_role="measures actual API call savings in trajectory tool results",
                    )
                if applied_api_decision.get("applied") and applied_api_decision.get("decision") == "SKIP_API":
                    validation_summaries.append(
                        {
                            "type": "api",
                            "ok": True,
                            "warnings": ["API skipped by isolated post-SQL applied trial."],
                            "errors": [],
                        }
                    )
                    continue
                if self.config.enable_sql_only_api_skip_guard:
                    skip_decision = should_skip_api_with_sql_evidence(
                        query=query,
                        prompt_route=prompt_route,
                        routing=routing,
                        analysis=analysis,
                        api_step=step,
                        tool_results=tool_results,
                    )
                    trajectory.add_step(
                        "api_skip_guard",
                        {
                            "checkpoint": "sql_only_api_skip_guard",
                            **skip_decision.to_dict(),
                            "feature_flag": "ENABLE_SQL_ONLY_API_SKIP_GUARD",
                        },
                    )
                    if skip_decision.skip:
                        validation_summaries.append(
                            {
                                "type": "api",
                                "ok": True,
                                "warnings": [skip_decision.reason],
                                "errors": [],
                            }
                        )
                        continue
                forwarding_actions = evidence_bus.forward_to_step(step)
                if forwarding_actions:
                    forwarding_actions_all.extend(forwarding_actions)
                    trajectory.add_step("optimizer", {"actions": forwarding_actions})
                validation = self.api_validator.validate(step.method, step.url, step.params, step.headers)
                if validation.ok:
                    api_cache_key = api_response_cache_key(step.method, step.url, step.params)
                    result = copy.deepcopy(per_query_api_response_cache.get(api_cache_key))
                    if result is None:
                        cached_result = get_api_response_cache(api_cache_key) if self.api_client.dry_run else None
                        result = copy.deepcopy(cached_result) if cached_result is not None else None
                    if result is None:
                        result = self.api_client.call_api(step.method, step.url, step.params, step.headers)
                        if result.get("dry_run"):
                            set_api_response_cache(api_cache_key, result)
                    per_query_api_response_cache[api_cache_key] = copy.deepcopy(result)
                else:
                    result = {"ok": False, "dry_run": False, "error": "; ".join(validation.errors)}
                    blocked_calls.append({"type": "api", "errors": validation.errors, "step": step.to_dict()})
                validation_summaries.append({"type": "api", "ok": validation.ok, "warnings": validation.warnings, "errors": validation.errors})
                trajectory.add_api_call(step.method, step.url, step.params, step.headers, validation, result)
                tool_results.append({"type": "api", "step": step.to_dict(), "validation": validation.to_dict(), "payload": result})
                evidence_bus.observe_api(step, result)
        trajectory.set_timing("execution_time", time.perf_counter() - execution_start)
        checkpoint_logger.add_checkpoint(
            "checkpoint_12_validation",
            stage="validation",
            technique="SQL/API safety validation",
            input_summary={"optimized_steps": [step.to_dict() for step in plan.steps]},
            output={
                "sql_validation_status": [
                    {"ok": item["ok"], "warnings": item["warnings"], "errors": item["errors"]}
                    for item in validation_summaries
                    if item["type"] == "sql"
                ],
                "api_validation_status": [
                    {"ok": item["ok"], "warnings": item["warnings"], "errors": item["errors"]}
                    for item in validation_summaries
                    if item["type"] == "api"
                ],
                "blocked_calls": blocked_calls,
                "warnings": [warning for item in validation_summaries for warning in item.get("warnings", [])],
            },
            effect="records whether planned SQL/API calls were safe to execute",
            correctness_role="blocks unsafe SQL and unknown/unresolved API calls",
            efficiency_role="prevents wasted execution on invalid calls",
        )
        if self.config.enable_sql_ast_validation and sql_ast_summaries:
            checkpoint_logger.add_checkpoint(
                "checkpoint_sql_ast_validation",
                stage="validation",
                technique="SQLGlot AST-based SQL validation and extraction",
                input_summary={"sql_call_count": len(sql_ast_summaries)},
                output={
                    "summaries": sql_ast_summaries,
                    "parsed_ok": all(item.get("parsed_ok") for item in sql_ast_summaries),
                    "selected_tables": sorted({table for item in sql_ast_summaries for table in item.get("selected_tables", [])}),
                    "selected_columns": sorted({column for item in sql_ast_summaries for column in item.get("selected_columns", [])}),
                    "unknown_tables": sorted({table for item in sql_ast_summaries for table in item.get("unknown_tables", [])}),
                    "unknown_columns": sorted({column for item in sql_ast_summaries for column in item.get("unknown_columns", [])}),
                    "destructive_sql_detected": any(item.get("destructive_sql_detected") for item in sql_ast_summaries),
                    "parse_errors": [item.get("parse_error") for item in sql_ast_summaries if item.get("parse_error")],
                    "closest_table_suggestions": {
                        key: value
                        for item in sql_ast_summaries
                        for key, value in (item.get("closest_table_suggestions") or {}).items()
                    },
                    "closest_column_suggestions": {
                        key: value
                        for item in sql_ast_summaries
                        for key, value in (item.get("closest_column_suggestions") or {}).items()
                    },
                },
                effect="adds AST-level table and column extraction after existing SQL validation",
                correctness_role="detects unsafe SQL and schema mismatches with parser-backed structure",
                efficiency_role="provides precise feedback without extra SQL tool calls",
            )
        checkpoint_logger.add_checkpoint(
            "checkpoint_13_tool_execution",
            stage="execution",
            technique="SQL/API tool execution",
            input_summary={"validated_step_count": len(plan.steps)},
            output=tool_results_execution_summary(tool_results),
            effect="captures the actual SQL/API evidence gathered by the backend",
            correctness_role="records row counts, dry-run state, and API status for final answer grounding",
            efficiency_role="makes tool-call count and result previews explicit",
        )
        evidence_boundary_payload = {
            "evidence_pipeline_bypassed": False,
            "evidence_bus_built": True,
            "post_evidence_answer_router_ran": bool(self.config.enable_hybrid_answer_composer),
        }
        checkpoint_logger.add_checkpoint(
            "checkpoint_evidence_pipeline_boundary",
            stage="evidence forwarding",
            technique="pre-evidence routing boundary",
            input_summary={"tool_result_count": len(tool_results), "strategy": strategy},
            output=evidence_boundary_payload,
            effect="records that the prompt continued into the evidence-backed answer path",
            correctness_role="separates data and mixed prompts from pure direct concept/meta bypasses",
            efficiency_role="makes EvidenceBus construction explicit in trajectories",
        )
        trajectory.add_step("evidence_boundary", evidence_boundary_payload)
        checkpoint_logger.add_checkpoint(
            "checkpoint_14_evidence_bus",
            stage="evidence forwarding",
            technique="operand forwarding / EvidenceBus",
            input_summary={"tool_result_count": len(tool_results)},
            output={
                "evidence": evidence_bus.compact(),
                "forwarding_actions": forwarding_actions_all,
            },
            effect="forwards structured facts to API params and answer slots",
            correctness_role="passes exact IDs, names, counts, timestamps, and statuses without text guessing",
            efficiency_role="avoids repeated lookup or reparsing work",
        )

        answer_start = time.perf_counter()
        api_need_decision = getattr(analysis, "api_need_decision", None)
        api_required_for_answer = str(getattr(api_need_decision, "mode", "") or "").upper() == "API_REQUIRED"
        evidence_quality = None
        if self.config.enable_evidence_quality_classifier:
            evidence_quality = classify_evidence_quality(tool_results, api_required=api_required_for_answer)
            checkpoint_logger.add_checkpoint(
                "checkpoint_evidence_quality_classifier",
                stage="answer synthesis",
                technique="SQL/API evidence quality classification",
                input_summary={"tool_result_count": len(tool_results), "api_required": api_required_for_answer},
                output=evidence_quality,
                effect="classifies SQL/API evidence quality before answer rendering",
                correctness_role="keeps SQL zero rows, live_empty, API errors, and required API missing distinct",
                efficiency_role="uses executed tool payloads without extra calls",
            )
        answer_result = synthesize_answer_with_diagnostics(query, tool_results)
        if self.config.enable_answer_shape_v2:
            shape_candidate = propose_answer_shape_candidate(query, tool_results)
            if shape_candidate.text and shape_candidate.text != answer_result.answer:
                answer_result = AnswerResult(
                    answer=shape_candidate.text,
                    diagnostics={
                        **answer_result.diagnostics,
                        "answer_shape_v2": shape_candidate.as_dict(),
                        "selected_candidate_type": "answer_shape_v2",
                        "selection_reason": "ENABLE_ANSWER_SHAPE_V2 selected a same-evidence answer-shape candidate.",
                    },
                )
        legacy_answer_result = answer_result
        slots = extract_answer_slots(query, tool_results)
        grounded = None
        generated = None
        pre_llm_selection = None
        hybrid_result = None
        broad_question_decision = None
        llm_answer_generation_skipped = False
        if self.config.enable_evidence_grounded_answer_builder:
            grounded = build_evidence_grounded_answer(
                query,
                tool_results,
                slots=slots,
                evidence_quality=evidence_quality,
                api_required=api_required_for_answer,
            )
            checkpoint_logger.add_checkpoint(
                "checkpoint_evidence_grounded_answer_builder",
                stage="answer synthesis",
                technique="EvidenceBus-centered grounded answer builder",
                input_summary={"tool_result_count": len(tool_results), "api_required": api_required_for_answer},
                output=grounded.to_dict(),
                effect="renders final answer from EvidenceBus-derived answer slots and evidence quality classes",
                correctness_role="uses exact available values and scoped caveats without inventing missing roles",
                efficiency_role="uses no extra SQL/API/LLM calls",
            )
            if self.config.enable_hybrid_answer_composer:
                if self.config.enable_broad_question_classifier:
                    broad_question_decision = classify_broad_question(
                        query,
                        slots=slots,
                        evidence_bus=evidence_bus,
                        evidence_quality=evidence_quality,
                    )
                hybrid_result = compose_hybrid_answer(
                    query,
                    slots=slots,
                    evidence_bus=evidence_bus,
                    evidence_quality=evidence_quality,
                    answer_card=grounded,
                    legacy_answer=legacy_answer_result.answer,
                )
            elif self.config.enable_evidence_grounded_llm_answer_generator:
                pre_llm_selection = select_answer_candidate(
                    prompt=query,
                    slots=slots,
                    evidence_bus=evidence_bus,
                    llm_answer=None,
                    llm_verification=None,
                    legacy_answer=legacy_answer_result.answer,
                    grounded_answer=grounded.answer,
                )
                llm_answer_generation_skipped = (
                    False
                    if self.config.force_evidence_grounded_llm_answer_generation
                    else _can_skip_llm_answer_generation(pre_llm_selection)
                )
                if not llm_answer_generation_skipped:
                    generated = generate_evidence_grounded_llm_answer(
                        query,
                        deterministic_answer=grounded.answer,
                        slots=slots,
                        answer_card=grounded,
                        evidence_bus=evidence_bus,
                        use_llm=self.config.enable_evidence_grounded_llm_answer_generator,
                        verify_final_answer=self.config.enable_evidence_grounded_final_answer_verifier,
                    )
        if self.config.enable_evidence_grounded_answer_builder and grounded is not None:
            if self.config.enable_hybrid_answer_composer and hybrid_result is not None:
                answer_result = AnswerResult(
                    answer=hybrid_result.final_answer,
                    diagnostics={
                        **legacy_answer_result.diagnostics,
                        "evidence_grounded_answer_builder": grounded.to_dict(),
                        "hybrid_answer_composer": hybrid_result.to_dict(),
                        "llm_answer_attempted": bool(
                            hybrid_result.concept is not None
                            and hybrid_result.concept.llm_backend_used
                        ),
                        "llm_answer_generation_skipped": False,
                        "candidate_count": 2,
                        "selected_candidate_type": hybrid_result.selected_source,
                        "selection_reason": (
                            "Selected intent-aware hybrid answer using runtime AnswerSlots/EvidenceBus only; "
                            "SQL/API execution path is unchanged by the answer composer."
                        ),
                    },
                )
                if broad_question_decision is not None:
                    checkpoint_logger.add_checkpoint(
                        "checkpoint_broad_question_classifier",
                        stage="answer selection",
                        technique="broad-question-aware answer routing",
                        input_summary={"slot_counts": slots.compact()},
                        output=broad_question_decision.to_dict(),
                        effect="distinguishes broad concept, broad data, mixed broad, and structured prompts before answer mode selection",
                        correctness_role="keeps broad data prompts evidence-first while allowing safe conceptual wording for concept prompts",
                        efficiency_role="avoids free-form LLM answer generation for structured data unless runtime evidence coverage improves",
                    )
                checkpoint_logger.add_checkpoint(
                    "checkpoint_answer_intent_router",
                    stage="answer selection",
                    technique="intent-aware answer router",
                    input_summary={"slot_counts": slots.compact()},
                    output=hybrid_result.intent.to_dict(),
                    effect="selects canonical data, LLM concept, mixed, caveat, or legacy answer mode from runtime evidence",
                    correctness_role="uses runtime prompt and evidence fields only",
                    efficiency_role="avoids unnecessary free-form LLM generation for structured data answers",
                )
                checkpoint_logger.add_checkpoint(
                    "checkpoint_hybrid_answer_composer",
                    stage="answer selection",
                    technique="intent-aware hybrid answer composition",
                    input_summary={"answer_intent": hybrid_result.intent.answer_intent, "answer_mode": hybrid_result.intent.answer_mode},
                    output=hybrid_result.to_dict(),
                    effect="uses canonical data rendering for structured answers and bounded LLM wording for concept sections",
                    correctness_role="preserves exact evidence facts and falls back to legacy rendering when verification fails",
                    efficiency_role="avoids all-row free-form LLM answer generation for structured data prompts",
                )
                checkpoint_logger.add_checkpoint(
                    "checkpoint_final_answer_verifier",
                    stage="answer verification",
                    technique="evidence-grounded final answer verifier",
                    input_summary={"selected_source": hybrid_result.selected_source},
                    output=hybrid_result.verification.to_dict(),
                    effect="accepts free wording only when hard factual claims are bounded by EvidenceBus and AnswerSlots",
                    correctness_role="blocks invented counts, IDs, statuses, timestamps, relationships, and unsafe no-data claims",
                    efficiency_role="runs on compact allowed facts and extracted claims without extra SQL/API calls",
                )
            else:
                if llm_answer_generation_skipped and pre_llm_selection is not None:
                    selection = pre_llm_selection
                else:
                    selection = select_answer_candidate(
                        prompt=query,
                        slots=slots,
                        evidence_bus=evidence_bus,
                        llm_answer=generated.final_answer if generated is not None else None,
                        llm_verification=generated.verification if generated is not None else None,
                        legacy_answer=legacy_answer_result.answer,
                        grounded_answer=grounded.answer,
                    )
                answer_result = AnswerResult(
                    answer=selection.selected_answer,
                    diagnostics={
                        **legacy_answer_result.diagnostics,
                        "evidence_grounded_answer_builder": grounded.to_dict(),
                        "evidence_grounded_llm_answer_generator": (
                            generated.to_dict()
                            if generated is not None
                            else _skipped_llm_answer_payload(llm_answer_generation_skipped)
                        ),
                        "llm_answer_attempted": bool(
                            self.config.enable_evidence_grounded_llm_answer_generator
                            and not llm_answer_generation_skipped
                        ),
                        "llm_answer_generation_skipped": llm_answer_generation_skipped,
                        "answer_candidate_selector": selection.to_dict(),
                        "candidate_count": len(selection.candidates),
                        "selected_candidate_type": selection.selected_source,
                        "selection_reason": (
                            "Selected the verifier-safe same-evidence answer with the best runtime role coverage; "
                            "no evaluator-only benchmark fields are used."
                        ),
                    },
                )
                checkpoint_logger.add_checkpoint(
                    "checkpoint_answer_candidate_selector",
                    stage="answer selection",
                    technique="runtime evidence coverage answer selection",
                    input_summary={"candidate_count": len(selection.candidates), "unsupported_claims": selection.unsupported_claims},
                    output=selection.to_dict(),
                    effect="restores strong same-evidence rendering when LLM wording omits requested roles",
                    correctness_role="selects only verifier-safe answers using AnswerSlots/EvidenceBus coverage, not gold labels",
                    efficiency_role="uses local scoring without extra SQL/API calls",
                )
        if self.config.enable_concise_llm_rewrite:
            rewrite_eligibility = decide_concise_rewrite_eligibility(
                prompt=query,
                legacy_answer=legacy_answer_result.answer,
                slots=slots,
                evidence_bus=evidence_bus,
                evidence_quality=evidence_quality,
            )
            checkpoint_logger.add_checkpoint(
                "checkpoint_concise_rewrite_eligibility",
                stage="answer selection",
                technique="selective concise rewrite eligibility",
                input_summary={"legacy_answer_length": len(legacy_answer_result.answer), "slots": slots.compact()},
                output=rewrite_eligibility.to_dict(),
                effect="allows LLM rewriting only for simple, exact-fact answer shapes",
                correctness_role="blocks rewrite for caveat-sensitive, incomplete, conflicted, or complex answers",
                efficiency_role="avoids all-row LLM answer rewriting",
            )
            rewrite_card = None
            rewrite_result = None
            rewrite_selection = None
            if rewrite_eligibility.eligible:
                rewrite_card = build_concise_rewrite_card(
                    prompt=query,
                    legacy_answer=legacy_answer_result.answer,
                    slots=slots,
                    eligibility=rewrite_eligibility,
                    evidence_bus=evidence_bus,
                    evidence_quality=evidence_quality,
                )
                checkpoint_logger.add_checkpoint(
                    "checkpoint_concise_rewrite_card",
                    stage="answer selection",
                    technique="compact runtime-evidence rewrite card",
                    input_summary={"answer_type": rewrite_eligibility.answer_type},
                    output=rewrite_card.to_dict(),
                    effect="passes only runtime exact facts and style constraints to the rewrite LLM",
                    correctness_role="excludes evaluator-only gold, tags, oracle, expected trace, and query-id decision fields",
                    efficiency_role="keeps rewrite prompt compact",
                )
                rewrite_result = rewrite_concise_answer(
                    rewrite_card,
                    max_tokens=self.config.concise_rewrite_max_tokens,
                )
                checkpoint_logger.add_checkpoint(
                    "checkpoint_concise_llm_rewrite",
                    stage="answer selection",
                    technique="one-shot concise gold-style LLM rewrite",
                    input_summary={"answer_type": rewrite_card.answer_type},
                    output=rewrite_result.to_dict(),
                    effect="rewrites the legacy answer only once when exact runtime evidence is available",
                    correctness_role="uses final-answer text only and leaves SQL/API evidence unchanged",
                    efficiency_role="limits rewrite to short outputs",
                )
            rewrite_selection = select_concise_rewrite(
                prompt=query,
                legacy_answer=legacy_answer_result.answer,
                rewrite_result=rewrite_result,
                card=rewrite_card,
                slots=slots,
                evidence_bus=evidence_bus,
            )
            checkpoint_logger.add_checkpoint(
                "checkpoint_concise_rewrite_verifier",
                stage="answer verification",
                technique="evidence-grounded concise rewrite verifier",
                input_summary={"rewrite_attempted": rewrite_result is not None},
                output=rewrite_selection.verifier,
                effect="keeps rewritten answers bounded by runtime EvidenceBus and AnswerSlots",
                correctness_role="rejects invented numbers, dates, statuses, names, IDs, scope, and caveats",
                efficiency_role="runs local verification without additional tool calls",
            )
            checkpoint_logger.add_checkpoint(
                "checkpoint_concise_rewrite_selector",
                stage="answer selection",
                technique="legacy-vs-concise-rewrite selector",
                input_summary={"rewrite_attempted": rewrite_result is not None},
                output=rewrite_selection.to_dict(),
                effect="selects the concise rewrite only when exact-fact coverage is preserved and style improves",
                correctness_role="falls back to legacy if uncertainty remains",
                efficiency_role="prevents unsafe or low-value rewrite selection",
            )
            answer_result = AnswerResult(
                answer=rewrite_selection.selected_answer,
                diagnostics={
                    **legacy_answer_result.diagnostics,
                    "concise_rewrite_eligibility": rewrite_eligibility.to_dict(),
                    "concise_rewrite_card": rewrite_card.to_dict() if rewrite_card is not None else None,
                    "concise_llm_rewrite": rewrite_result.to_dict() if rewrite_result is not None else None,
                    "concise_rewrite_selector": rewrite_selection.to_dict(),
                    "rewrite_eligible": rewrite_eligibility.eligible,
                    "rewrite_attempted": rewrite_result is not None,
                    "rewrite_selected": rewrite_selection.selected_source == "CONCISE_LLM_REWRITE",
                    "rewrite_backend_failed": bool(rewrite_result and rewrite_result.category == "backend_unavailable"),
                    "rewrite_empty": bool(rewrite_result and rewrite_result.category == "empty_rewrite"),
                    "selected_candidate_type": rewrite_selection.selected_source,
                    "selected_answer_source": rewrite_selection.selected_source,
                    "selection_reason": ";".join(rewrite_selection.selection_codes),
                    "candidate_count": 2 if rewrite_result is not None else 1,
                },
            )
        final_answer = answer_result.answer
        intent = classify_answer_intent(query, slots)
        claims = extract_claims(final_answer)
        verification = verify_answer(final_answer, slots)
        checkpoint_logger.add_checkpoint(
            "checkpoint_15_answer_slots",
            stage="answer synthesis",
            technique="structured answer slot extraction",
            input_summary={"tool_result_count": len(tool_results)},
            output={
                "answer_intent": str(intent),
                "slots": slots.compact(),
                "missing_slots": answer_result.diagnostics.get("completeness_missing_fields", []),
                "discrepancy_flags": {"sql_api_discrepancy": slots.discrepancy},
                "dry_run_flags": {"dry_run": slots.dry_run},
            },
            effect="turns raw tool results into typed evidence fields",
            correctness_role="makes final response generation evidence-grounded",
            efficiency_role="keeps answer context compact",
        )
        if self.config.enable_answer_slot_renderer:
            renderer_payload = (answer_result.diagnostics.get("evidence_grounded_answer_builder") or {}).get("renderer")
            if isinstance(renderer_payload, dict):
                checkpoint_logger.add_checkpoint(
                    "checkpoint_answer_slot_renderer",
                    stage="answer synthesis",
                    technique="deterministic answer-slot rendering",
                    input_summary={"slots": slots.compact()},
                    output=renderer_payload,
                    effect="records how requested fields were rendered from answer slots",
                    correctness_role="makes omitted or unavailable roles explicit",
                    efficiency_role="avoids LLM answer rewriting in the candidate path",
                )
        llm_answer_payload = answer_result.diagnostics.get("evidence_grounded_llm_answer_generator")
        if isinstance(llm_answer_payload, dict):
            verifier_payload = llm_answer_payload.get("verification") if isinstance(llm_answer_payload.get("verification"), dict) else {}
            checkpoint_logger.add_checkpoint(
                "checkpoint_final_answer_claim_extractor",
                stage="answer verification",
                technique="final-answer factual claim extraction",
                input_summary={"final_answer_length": len(final_answer)},
                output=verifier_payload.get("claim_extractor", {}),
                effect="extracts only hard factual claim candidates from free-form answer wording",
                correctness_role="keeps style flexible while making factual boundaries explicit",
                efficiency_role="uses deterministic text scanning with no tool calls",
            )
            checkpoint_logger.add_checkpoint(
                "checkpoint_final_answer_claim_matcher",
                stage="answer verification",
                technique="allowed-fact deterministic claim matching",
                input_summary={"allowed_fact_index_fields": list((verifier_payload.get("allowed_fact_index") or {}).keys())},
                output=verifier_payload.get("claim_matcher", {}),
                effect="matches hard claims against EvidenceBus and AnswerSlots allowed facts",
                correctness_role="blocks invented counts, IDs, statuses, dates, relationships, and over-broad no-data claims",
                efficiency_role="uses local normalized indexes without extra tools",
            )
            checkpoint_logger.add_checkpoint(
                "checkpoint_evidence_grounded_final_answer_verifier",
                stage="answer verification",
                technique="flexible wording bounded-fact final-answer verifier",
                input_summary={"llm_backend_used": llm_answer_payload.get("llm_backend_used")},
                output={
                    "ok": verifier_payload.get("ok"),
                    "action": verifier_payload.get("action"),
                    "unsupported_claims": verifier_payload.get("unsupported_claims", [])[:5],
                    "over_specified_claims": verifier_payload.get("over_specified_claims", [])[:5],
                    "needs_caveat_claims": verifier_payload.get("needs_caveat_claims", [])[:5],
                    "fallback_used": llm_answer_payload.get("fallback_used"),
                    "rewrite_attempted": llm_answer_payload.get("rewrite_attempted"),
                    "rewrite_success": llm_answer_payload.get("rewrite_success"),
                },
                effect="accepts natural wording only when factual claims stay inside allowed evidence",
                correctness_role="prevents factual overreach without enforcing deterministic template text",
                efficiency_role="falls back locally when no safe LLM answer is available",
            )
            checkpoint_logger.add_checkpoint(
                "checkpoint_llm_answer_rewrite_feedback",
                stage="answer verification",
                technique="compact rewrite feedback for failed grounded answer verification",
                input_summary={"rewrite_attempted": llm_answer_payload.get("rewrite_attempted")},
                output=llm_answer_payload.get("feedback", {}),
                effect="records blocked claims and allowed facts for one bounded rewrite attempt",
                correctness_role="keeps rewrite feedback fact-only and excludes evaluator-only metadata",
                efficiency_role="uses at most one rewrite attempt before deterministic fallback",
            )
            checkpoint_logger.add_checkpoint(
                "checkpoint_final_answer_minimal_correction_feedback",
                stage="answer verification",
                technique="minimal correction feedback for final-answer rewrite",
                input_summary={"rewrite_attempted": llm_answer_payload.get("rewrite_attempted")},
                output=llm_answer_payload.get("feedback", {}),
                effect="sends only blocked claims and relevant allowed facts to the rewrite LLM",
                correctness_role="keeps free wording while preventing factual overreach",
                efficiency_role="avoids resending full evidence cards on rewrite",
            )
            checkpoint_logger.add_checkpoint(
                "checkpoint_final_answer_rewrite_result",
                stage="answer verification",
                technique="single final-answer rewrite result",
                input_summary={"first_pass_ok": llm_answer_payload.get("first_pass_ok")},
                output={
                    "rewrite_attempted": llm_answer_payload.get("rewrite_attempted"),
                    "rewrite_success": llm_answer_payload.get("rewrite_success"),
                    "unsupported_after_revision": len(verifier_payload.get("unsupported_claims", []) or []),
                },
                effect="records whether one rewrite fixed verifier conflicts",
                correctness_role="does not keep unsupported rewritten answers",
                efficiency_role="limits correction to one rewrite",
            )
            checkpoint_logger.add_checkpoint(
                "checkpoint_final_answer_fallback_if_any",
                stage="answer verification",
                technique="deterministic final-answer fallback",
                input_summary={"fallback_used": llm_answer_payload.get("fallback_used")},
                output={
                    "fallback_used": llm_answer_payload.get("fallback_used"),
                    "fallback_reason": "verifier_failed_after_rewrite" if llm_answer_payload.get("fallback_used") else None,
                    "semantic_certainty_claimed": False,
                },
                effect="falls back to deterministic AnswerSlotRenderer when bounded LLM wording fails",
                correctness_role="preserves unsupported-claims target",
                efficiency_role="uses no extra tool calls",
            )
        checkpoint_logger.add_checkpoint(
            "checkpoint_16_answer_verification",
            stage="answer verification",
            technique="claim verification / groundedness checking",
            input_summary={"claim_count": len(claims), "slots_present": slots.slots_present()},
            output={
                "supported_claims_count": max(0, len(claims) - verification.unsupported_count),
                "unsupported_claims_count": verification.unsupported_count,
                "rewrite_applied": answer_result.diagnostics.get("rewrite_applied", False),
                "verifier_passed": verification.ok,
                "errors": verification.errors[:5],
                "warnings": verification.warnings[:5],
            },
            effect="checks final-answer claims against SQL/API evidence",
            correctness_role="blocks unsupported numbers, entities, timestamps, statuses, and dry-run API confirmation",
            efficiency_role="rewrites safely without extra tool calls",
        )
        checkpoint_logger.add_checkpoint(
            "checkpoint_17_answer_reranking",
            stage="answer selection",
            technique="deterministic answer reranking",
            input_summary={"answer_family": answer_result.diagnostics.get("answer_family")},
            output={
                "candidate_count": answer_result.diagnostics.get("candidate_count", 0),
                "selected_candidate_type": answer_result.diagnostics.get("selected_candidate_type"),
                "selection_reason": answer_result.diagnostics.get("selection_reason", "best verifier-passing answer"),
            },
            effect="selects the safest answer from same-evidence candidates",
            correctness_role="prefers verifier-passing and intent-matched answers",
            efficiency_role="uses no additional SQL/API/LLM calls",
        )
        checkpoint_logger.add_checkpoint(
            "checkpoint_18_final_answer",
            stage="final response",
            technique="concise grounded final response",
            input_summary={"verifier_passed": verification.ok},
            output={
                "final_answer": final_answer,
                "answer_length": len(final_answer),
                "final_token_estimate": estimate_tokens(final_answer),
            },
            effect="returns the final concise answer to the agent harness",
            correctness_role="final answer remains tied to evidence and caveats",
            efficiency_role="keeps response concise",
        )
        trajectory.add_step("answer_diagnostics", answer_result.diagnostics)
        trajectory.set_timing("answer_time", time.perf_counter() - answer_start)
        trajectory.set_checkpoints(checkpoint_logger.to_list())
        trajectory_payload = trajectory.finish(final_answer)
        if self.config.enable_official_token_reduction and plan_strategy == "SQL_FIRST_API_VERIFY":
            trajectory_payload, _ = apply_token_reduction_to_trajectory(trajectory_payload)
        trajectory_path = out_dir / "trajectory.json"
        trajectory_path.parent.mkdir(parents=True, exist_ok=True)
        trajectory_path.write_text(json.dumps(trajectory_payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
        return {
            "query_id": qid,
            "query": query,
            "strategy": strategy,
            "output_dir": str(out_dir),
            "metadata": metadata,
            "plan": plan.to_dict(),
            "tool_results": tool_results,
            "final_answer": final_answer,
            "checkpoints": checkpoint_logger.to_list(),
            "trajectory": trajectory_payload,
        }

    def _run_llm_owned_v2(
        self,
        *,
        query: str,
        qid: str,
        strategy: str,
        out_dir: Path,
        checkpoint_logger: CheckpointLogger,
    ) -> dict[str, Any]:
        run_context = create_run_context(
            query,
            prompt_id=qid,
            budget=RunBudget(
                max_passes=getattr(self.pass_graph_gate, "max_passes", 6),
                max_parallelism=self.v2_pipeline_scheduler.max_parallelism,
                max_sql_workers=self.v2_pipeline_scheduler.max_sql_workers,
                max_api_workers=self.v2_pipeline_scheduler.max_api_workers,
            ),
        )
        planner_context = self._llm_owned_planner_context()
        plan = run_llm_unified_planner(
            user_prompt=query,
            schema_context=planner_context["schema_context"],
            endpoint_context=planner_context["endpoint_context"],
        )
        checkpoint_logger.add_checkpoint(
            "checkpoint_llm_unified_planner",
            stage="llm-owned planning",
            technique="single unified LLM route/evidence/sql/api planner",
            input_summary={"query": query},
            output=plan.to_dict(),
            effect="lets the LLM own route, evidence order, and SQL/API candidate generation for V2",
            correctness_role="keeps backend deterministic logic limited to compile/request gates and execution",
            efficiency_role="uses one compact planner call before any SQL/API execution",
            metrics=plan.diagnostics,
        )

        metadata = {
            "query_id": qid,
            "query": query,
            "strategy": strategy,
            "run_context": run_context.to_dict(),
            "llm_owned_generation": True,
            "backend_semantic_planning_used": False,
            "llm_unified_plan": plan.to_dict(),
            "note": "ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2 uses LLM-owned route/evidence/SQL/API generation; packaged default remains unchanged.",
        }
        self.metadata_selector.save(metadata, out_dir)
        filled_prompt = render_system_prompt(self.config, metadata)
        (out_dir / "filled_system_prompt.txt").write_text(filled_prompt, encoding="utf-8")

        if plan.route == "LLM_DIRECT" and plan.evidence_order == "NO_EVIDENCE":
            return self._return_llm_owned_direct_result(
                query=query,
                qid=qid,
                strategy=strategy,
                out_dir=out_dir,
                metadata=metadata,
                filled_prompt=filled_prompt,
                plan=plan,
                run_context=run_context,
                checkpoint_logger=checkpoint_logger,
            )

        tool_results, runtime_passes, execution_summary = self._execute_llm_owned_evidence_plan(
            query=query,
            initial_plan=plan,
            run_context=run_context,
            planner_context=planner_context,
            checkpoint_logger=checkpoint_logger,
        )
        boundary_summary = {
            "llm_owned_generation": True,
            "llm_route": plan.route,
            "llm_evidence_order": plan.evidence_order,
            "backend_semantic_planning_used": False,
            **_llm_owned_generation_boundary_summary(execution_summary),
        }
        checkpoint_logger.add_checkpoint(
            "checkpoint_llm_owned_generation_boundary",
            stage="llm/backend boundary",
            technique="LLM-owned candidate generation with backend-only gates",
            input_summary={"route": plan.route, "evidence_order": plan.evidence_order},
            output=boundary_summary,
            effect="records that backend did not replace LLM semantic or SQL/API generation",
            correctness_role="separates LLM ownership from compile/request/runtime safety checks",
            efficiency_role="bounds repair attempts before execution",
        )

        evidence_bus = EvidenceBus(run_id=run_context.run_id)
        for item in tool_results:
            step_payload = item.get("step") if isinstance(item.get("step"), dict) else {}
            step = PlanStep(
                action=str(step_payload.get("action") or item.get("type") or ""),
                purpose=str(step_payload.get("purpose") or "LLM-owned V2 evidence."),
                sql=step_payload.get("sql"),
                method=step_payload.get("method"),
                url=step_payload.get("url"),
                params=step_payload.get("params") if isinstance(step_payload.get("params"), dict) else {},
                headers=step_payload.get("headers") if isinstance(step_payload.get("headers"), dict) else {},
                allow_full_result=bool(step_payload.get("allow_full_result", True)),
                family=step_payload.get("family"),
            )
            payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
            if item.get("type") == "sql":
                evidence_bus.observe_sql(step, payload)
            elif item.get("type") == "api":
                evidence_bus.observe_api(step, payload)
        for pass_result in runtime_passes:
            evidence_bus.observe_pass_result(pass_result)

        trajectory = TrajectoryLogger(
            query_id=qid,
            original_query=query,
            strategy=strategy,
            route_type=plan.route,
            domain_type="LLM_OWNED_V2",
            max_preview_chars=self.config.max_preview_chars,
        )
        trajectory.add_step("metadata", {"estimated_tokens": estimate_tokens(metadata), "prompt_tokens": estimate_tokens(filled_prompt), "metadata_path": str(out_dir / "metadata.json")})
        trajectory.add_step("llm_unified_planner", plan.to_dict())
        for item in tool_results:
            step_payload = item.get("step") if isinstance(item.get("step"), dict) else {}
            validation = _validation_result_from_payload(item.get("validation"))
            payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
            if item.get("type") == "sql":
                trajectory.add_sql_call(str(step_payload.get("sql") or ""), validation, payload)
            elif item.get("type") == "api":
                trajectory.add_api_call(
                    str(step_payload.get("method") or "GET"),
                    str(step_payload.get("url") or ""),
                    step_payload.get("params") if isinstance(step_payload.get("params"), dict) else {},
                    {},
                    validation,
                    payload,
                )

        checkpoint_logger.add_checkpoint(
            "checkpoint_13_tool_execution",
            stage="execution",
            technique="LLM-owned SQL/API tool execution",
            input_summary={"tool_result_count": len(tool_results)},
            output=tool_results_execution_summary(tool_results),
            effect="executes only LLM-proposed candidates that pass backend gates",
            correctness_role="records runtime evidence or compile/request failures without fabricating data",
            efficiency_role="does not execute alternative backend-generated candidates",
        )
        evidence_boundary_payload = {
            "evidence_pipeline_bypassed": False,
            "evidence_bus_built": True,
            "post_evidence_answer_router_ran": False,
            "llm_final_answer_composer_ran": True,
            "pass_results_count": len(runtime_passes),
            "llm_route": plan.route,
            "llm_evidence_order": plan.evidence_order,
        }
        checkpoint_logger.add_checkpoint(
            "checkpoint_evidence_pipeline_boundary",
            stage="evidence forwarding",
            technique="V2 evidence boundary",
            input_summary={"tool_result_count": len(tool_results), "strategy": strategy},
            output=evidence_boundary_payload,
            effect="records that data/mixed/ambiguous prompts continued into evidence-backed answer grounding",
            correctness_role="prevents pure direct answer routing from masking evidence-required prompts",
            efficiency_role="makes EvidenceBus construction explicit",
        )
        trajectory.add_step("evidence_boundary", evidence_boundary_payload)
        checkpoint_logger.add_checkpoint(
            "checkpoint_14_evidence_bus",
            stage="evidence forwarding",
            technique="EvidenceBus",
            input_summary={"tool_result_count": len(tool_results)},
            output={"evidence": evidence_bus.compact(), "forwarding_actions": []},
            effect="forwards executed SQL/API evidence into the existing grounded answer pipeline",
            correctness_role="keeps exact values and scoped caveats in existing EvidenceBus semantics",
            efficiency_role="uses collected evidence without extra tool calls",
        )

        answer_start = time.perf_counter()
        evidence_quality = classify_evidence_quality(tool_results, api_required=any(item.get("type") == "api" for item in tool_results))
        result_bundle = ResultBundle.from_pass_results(runtime_passes, tool_results, run_id=run_context.run_id)
        checkpoint_logger.add_checkpoint(
            "checkpoint_result_bundle",
            stage="evidence forwarding",
            technique="ResultBundle",
            input_summary={"pass_results_count": result_bundle.pass_results_count, "tool_result_count": len(tool_results)},
            output=_result_bundle_checkpoint_payload(result_bundle),
            effect="stores all LLM-declared pass results before final LLM aggregation",
            correctness_role="keeps pass-level runtime evidence separate from backend answer generation",
            efficiency_role="reuses executed pass results without extra tools",
        )
        checkpoint_logger.add_checkpoint(
            "checkpoint_evidence_quality_classifier",
            stage="answer synthesis",
            technique="SQL/API evidence quality classification",
            input_summary={"tool_result_count": len(tool_results)},
            output=evidence_quality,
            effect="keeps SQL errors, API errors, live empty, and direct evidence distinct",
            correctness_role="prevents API_ERROR as no-data and LIVE_EMPTY as global absence",
            efficiency_role="uses existing payloads only",
        )
        slots = extract_answer_slots(query, tool_results)
        answer_card = build_llm_final_answer_card(
            user_prompt=query,
            llm_plan=plan,
            runtime_passes=runtime_passes,
            evidence_bus=evidence_bus,
            answer_slots=slots,
            evidence_quality=evidence_quality,
            result_bundle=result_bundle,
            aggregation_instruction=plan.aggregation_instruction,
        )
        checkpoint_logger.add_checkpoint(
            "checkpoint_15_answer_slots",
            stage="answer synthesis",
            technique="structured answer slot extraction",
            input_summary={"tool_result_count": len(tool_results)},
            output={
                "slots": slots.compact(),
                "discrepancy_flags": {"sql_api_discrepancy": slots.discrepancy},
                "dry_run_flags": {"dry_run": slots.dry_run},
            },
            effect="turns runtime evidence into typed answer fields",
            correctness_role="provides runtime facts to the LLM-owned final answer composer",
            efficiency_role="uses existing slot extraction",
        )
        candidate = compose_llm_final_answer(card=answer_card)
        checkpoint_logger.add_checkpoint(
            "checkpoint_llm_final_answer_composer",
            stage="llm-owned answer synthesis",
            technique="LLMFinalAnswerComposer",
            input_summary={"runtime_pass_count": len(runtime_passes), "slot_counts": slots.compact()},
            output=candidate.to_dict(),
            effect="lets the LLM own final answer composition from runtime evidence",
            correctness_role="backend does not render deterministic templates or select competing answers",
            efficiency_role="uses one final-answer LLM call after evidence execution",
        )
        syntax_gate = check_final_answer_syntax(candidate)
        checkpoint_logger.add_checkpoint(
            "checkpoint_llm_final_answer_syntax_gate",
            stage="answer gate",
            technique="minimal final-answer syntax gate",
            input_summary={"composer": "LLMFinalAnswerComposer"},
            output=syntax_gate.to_dict(),
            effect="checks only answer existence and wrapper serialization",
            correctness_role="does not rewrite, shorten, or score the answer",
            efficiency_role="no SQL/API calls",
        )
        if syntax_gate.passed:
            semantic_gate = check_final_answer_semantic_grounding(
                syntax_gate.final_answer or "",
                question=query,
                runtime_passes=runtime_passes,
                evidence_bus=evidence_bus,
                slots=slots,
            )
        else:
            semantic_gate = None
        checkpoint_logger.add_checkpoint(
            "checkpoint_llm_final_answer_semantic_gate",
            stage="answer gate",
            technique="runtime-evidence semantic grounding gate",
            input_summary={"syntax_gate_passed": syntax_gate.passed},
            output=semantic_gate.to_dict() if semantic_gate is not None else {"passed": False, "error_type": "syntax_gate_failed"},
            effect="checks whether LLM final answer claims are supported by runtime evidence",
            correctness_role="blocks unsupported facts, missing requested facts, and scope/caveat errors without generating an answer",
            efficiency_role="no SQL/API calls",
        )
        answer_repair_attempts = 0
        final_candidate = candidate
        final_syntax_gate = syntax_gate
        final_semantic_gate = semantic_gate
        if not syntax_gate.passed or semantic_gate is None or not semantic_gate.passed:
            repair_context = {
                "syntax_gate": syntax_gate.to_dict(),
                "semantic_gate": semantic_gate.to_dict() if semantic_gate is not None else None,
                "previous_candidate": candidate.to_dict(),
            }
            repaired = compose_llm_final_answer(card=answer_card, repair_context=repair_context)
            answer_repair_attempts = 1
            repaired_syntax = check_final_answer_syntax(repaired)
            if repaired_syntax.passed:
                repaired_semantic = check_final_answer_semantic_grounding(
                    repaired_syntax.final_answer or "",
                    question=query,
                    runtime_passes=runtime_passes,
                    evidence_bus=evidence_bus,
                    slots=slots,
                )
            else:
                repaired_semantic = None
            checkpoint_logger.add_checkpoint(
                "checkpoint_llm_final_answer_repair",
                stage="llm-owned answer repair",
                technique="single LLM-owned final answer repair",
                input_summary={"failed_syntax": not syntax_gate.passed, "failed_semantic": semantic_gate is not None and not semantic_gate.passed},
                output={
                    "candidate": repaired.to_dict(),
                    "syntax_gate": repaired_syntax.to_dict(),
                    "semantic_gate": repaired_semantic.to_dict() if repaired_semantic is not None else {"passed": False, "error_type": "syntax_gate_failed"},
                },
                effect="returns gate errors to the LLM once; backend does not repair the answer itself",
                correctness_role="preserves LLM ownership while enforcing evidence boundaries",
                efficiency_role="caps answer repair to one LLM call",
            )
            if repaired_syntax.passed and repaired_semantic is not None and repaired_semantic.passed:
                final_candidate = repaired
                final_syntax_gate = repaired_syntax
                final_semantic_gate = repaired_semantic
        final_answer_supported = bool(final_syntax_gate.passed and final_semantic_gate is not None and final_semantic_gate.passed)
        final_answer = (
            final_syntax_gate.final_answer
            if final_answer_supported and final_syntax_gate.final_answer is not None
            else safe_llm_final_answer_fallback(runtime_passes, syntax_gate=final_syntax_gate, semantic_gate=final_semantic_gate)
        )
        answer_diagnostics = {
            "llm_owned_final_answer": True,
            "answer_composer_used": "LLMFinalAnswerComposer",
            "answer_syntax_gate_passed": bool(final_syntax_gate.passed),
            "answer_semantic_gate_passed": bool(final_semantic_gate.passed) if final_semantic_gate is not None else False,
            "answer_repair_attempts": answer_repair_attempts,
            "used_pass_ids": final_candidate.used_pass_ids,
            "final_answer_supported_by_evidence": final_answer_supported,
            "hidden_eval_gold_used": False,
            "deterministic_answer_template_used": False,
            "syntax_gate": final_syntax_gate.to_dict(),
            "semantic_gate": final_semantic_gate.to_dict() if final_semantic_gate is not None else None,
        }
        checkpoint_logger.add_checkpoint(
            "checkpoint_llm_owned_final_answer_boundary",
            stage="answer ownership boundary",
            technique="LLM-owned final answer with backend gates",
            input_summary={"runtime_pass_count": len(runtime_passes)},
            output=answer_diagnostics,
            effect="records that V2 did not use deterministic answer templates, renderers, or selectors as competing generators",
            correctness_role="keeps backend responsible only for syntax/semantic gates after LLM answer generation",
            efficiency_role="no extra tool calls",
        )
        checkpoint_logger.add_checkpoint(
            "checkpoint_18_final_answer",
            stage="final response",
            technique="LLM-owned final response",
            input_summary={"answer_semantic_gate_passed": final_answer_supported},
            output={
                "final_answer": final_answer,
                "answer_length": len(final_answer),
                "final_token_estimate": estimate_tokens(final_answer),
                "llm_owned_final_answer": True,
                "answer_composer_used": "LLMFinalAnswerComposer",
                "answer_syntax_gate_passed": bool(final_syntax_gate.passed),
                "answer_semantic_gate_passed": bool(final_semantic_gate.passed) if final_semantic_gate is not None else False,
                "answer_repair_attempts": answer_repair_attempts,
                "used_pass_ids": final_candidate.used_pass_ids,
                "final_answer_supported_by_evidence": final_answer_supported,
                "hidden_eval_gold_used": False,
                "deterministic_answer_template_used": False,
            },
            effect="returns the LLM-composed answer when gates pass, otherwise a safe evidence-state fallback",
            correctness_role="keeps final answer generation LLM-owned while preserving runtime evidence grounding",
            efficiency_role="no additional SQL/API calls",
        )
        trajectory.add_step("llm_final_answer_composer", final_candidate.to_dict())
        trajectory.add_step("answer_diagnostics", answer_diagnostics)
        trajectory.set_timing("answer_time", time.perf_counter() - answer_start)
        trajectory.set_checkpoints(checkpoint_logger.to_list())
        trajectory_payload = trajectory.finish(final_answer)
        trajectory_path = out_dir / "trajectory.json"
        trajectory_path.parent.mkdir(parents=True, exist_ok=True)
        trajectory_path.write_text(json.dumps(trajectory_payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
        return {
            "query_id": qid,
            "query": query,
            "strategy": strategy,
            "output_dir": str(out_dir),
            "metadata": metadata,
            "plan": self._llm_owned_plan_dict(strategy, plan, tool_results),
            "tool_results": tool_results,
            "final_answer": final_answer,
            "checkpoints": checkpoint_logger.to_list(),
            "trajectory": trajectory_payload,
        }

    def _return_llm_owned_direct_result(
        self,
        *,
        query: str,
        qid: str,
        strategy: str,
        out_dir: Path,
        metadata: dict[str, Any],
        filled_prompt: str,
        plan: LLMUnifiedPlan,
        run_context: RunContext,
        checkpoint_logger: CheckpointLogger,
    ) -> dict[str, Any]:
        final_answer = str(plan.direct_answer or "").strip()
        if not final_answer:
            final_answer = "This is a general conceptual question and no runtime evidence was used."
        safe_check = validate_llm_safe_direct_answer(final_answer)
        if not safe_check.get("ok"):
            final_answer = "This is a general conceptual question; no user-specific or live platform records were used."
            safe_check = validate_llm_safe_direct_answer(final_answer)
        boundary_payload = {
            "evidence_pipeline_bypassed": True,
            "bypass_reason": "llm_owned_direct_no_evidence_required",
            "pre_evidence_route": plan.route,
            "llm_route": plan.route,
            "llm_evidence_order": plan.evidence_order,
            "post_evidence_answer_router_ran": False,
            "evidence_bus_built": False,
        }
        generation_boundary = {
            "run_id": run_context.run_id,
            "llm_owned_generation": True,
            "multi_pass_enabled": False,
            "llm_pass_graph_used": False,
            "v2_execution_optimizer_used": False,
            "critical_path": [],
            "stage_pipeline_used": False,
            "cache_hits": 0,
            "deduped_passes": [],
            "early_stopped_passes": [],
            "budget_limits": run_context.budget.to_dict(),
            "budget_exceeded": False,
            "checkpoint_resume_used": False,
            "model_cascade_used": False,
            "v2_pipeline_scheduler_used": False,
            "pipeline_stage_count": 0,
            "max_parallelism": 0,
            "max_sql_workers": 0,
            "max_api_workers": 0,
            "llm_pass_count": 0,
            "parallel_pass_count": 0,
            "sequential_pass_count": 0,
            "pass_ids": [],
            "parallel_groups": [],
            "dependency_edges": [],
            "pass_graph_gate_passed": True,
            "stage_events": [],
            "pass_results_count": 0,
            "passes_executed": [],
            "passes_completed": [],
            "passes_failed": [],
            "passes_dependency_blocked": [],
            "llm_route": plan.route,
            "llm_evidence_order": plan.evidence_order,
            "sql_gate_passed": None,
            "api_gate_passed": None,
            "backend_semantic_planning_used": False,
            "backend_semantic_decomposition_used": False,
            "sql_compile_gate_passed": None,
            "api_request_gate_passed": None,
            "sql_repair_attempts": 0,
            "api_repair_attempts": 0,
            "evidence_pipeline_bypassed": True,
        }
        checkpoint_logger.add_checkpoint(
            "checkpoint_llm_owned_generation_boundary",
            stage="llm/backend boundary",
            technique="LLM-owned direct route",
            input_summary={"route": plan.route, "evidence_order": plan.evidence_order},
            output=generation_boundary,
            effect="records that no backend SQL/API/evidence planning ran for direct V2 answer",
            correctness_role="keeps direct conceptual answers separate from evidence-grounded data answers",
            efficiency_role="uses zero SQL/API calls",
        )
        checkpoint_logger.add_checkpoint(
            "checkpoint_evidence_pipeline_bypass",
            stage="pre-evidence routing",
            technique="LLM-owned high-confidence direct routing boundary",
            input_summary={"strategy": strategy},
            output=boundary_payload,
            effect="bypasses SQL/API, EvidenceBus, answer slots, and post-evidence answer routing",
            correctness_role="prevents empty EvidenceBus construction for no-evidence concept/meta answers",
            efficiency_role="uses no SQL/API calls",
        )
        checkpoint_logger.add_checkpoint(
            "checkpoint_safe_direct_answer_verifier",
            stage="answer verification",
            technique="safe-direct answer verifier",
            input_summary={"llm_route": plan.route},
            output=safe_check,
            effect="checks direct answer for unsupported concrete runtime claims",
            correctness_role="blocks counts, IDs, timestamps, statuses, and live platform claims",
            efficiency_role="uses no SQL/API calls",
        )
        checkpoint_logger.add_checkpoint(
            "checkpoint_18_final_answer",
            stage="final response",
            technique="LLM-owned direct concept answer",
            output={"final_answer": final_answer, "answer_length": len(final_answer), "final_token_estimate": estimate_tokens(final_answer)},
            effect="returns the safe direct answer without building evidence artifacts",
            correctness_role="does not invent SQL/API evidence",
            efficiency_role="zero tool calls",
        )
        trajectory = TrajectoryLogger(
            query_id=qid,
            original_query=query,
            strategy=strategy,
            route_type=plan.route,
            domain_type="CONCEPTUAL",
            max_preview_chars=self.config.max_preview_chars,
        )
        trajectory.add_step("metadata", {"estimated_tokens": estimate_tokens(metadata), "prompt_tokens": estimate_tokens(filled_prompt), "metadata_path": str(out_dir / "metadata.json")})
        trajectory.add_step("llm_unified_planner", plan.to_dict())
        trajectory.add_step("evidence_boundary", boundary_payload)
        trajectory.add_step("safe_direct_answer_verifier", safe_check)
        trajectory.set_checkpoints(checkpoint_logger.to_list())
        trajectory_payload = trajectory.save(out_dir / "trajectory.json", final_answer)
        return {
            "query_id": qid,
            "query": query,
            "strategy": strategy,
            "output_dir": str(out_dir),
            "metadata": metadata,
            "plan": self._llm_owned_plan_dict(strategy, plan, []),
            "tool_results": [],
            "final_answer": final_answer,
            "checkpoints": checkpoint_logger.to_list(),
            "trajectory": trajectory_payload,
        }

    def _execute_llm_owned_evidence_plan(
        self,
        *,
        query: str,
        initial_plan: LLMUnifiedPlan,
        run_context: RunContext,
        planner_context: dict[str, Any],
        checkpoint_logger: CheckpointLogger,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
        tool_results: list[dict[str, Any]] = []
        runtime_passes: list[dict[str, Any]] = []
        active_plan = initial_plan
        pass_specs = active_plan.passes or []
        graph_gate = self.pass_graph_gate.check(active_plan)
        pass_graph_repair_attempted = False
        pass_graph_repair_success = False
        initial_graph_gate_error_type = graph_gate.error_type
        checkpoint_logger.add_checkpoint(
            "checkpoint_llm_owned_pass_graph_gate",
            stage="llm-owned pass graph validation",
            technique="shape-only PassGraphGate",
            input_summary={"pass_ids": [item.pass_id for item in pass_specs], "evidence_order": active_plan.evidence_order},
            output=graph_gate.to_dict(),
            effect="validates only graph shape; does not choose subtasks, dependencies, SQL, or API paths",
            correctness_role="blocks malformed dependency graphs before execution",
            efficiency_role="bounds pass scheduling to LLM-declared valid graphs",
        )
        if not graph_gate.passed:
            pass_graph_repair_attempted = True
            repair_plan = run_llm_unified_planner(
                user_prompt=query,
                schema_context=planner_context["schema_context"],
                endpoint_context=planner_context["endpoint_context"],
                repair_context={
                    "failed_component": "pass_graph_gate",
                    "graph_gate_error_type": graph_gate.error_type,
                    "graph_gate_error_message": graph_gate.error_message,
                    "previous_plan": initial_plan.to_dict(),
                },
            )
            repaired_graph_gate = self.pass_graph_gate.check(repair_plan)
            pass_graph_repair_success = repaired_graph_gate.passed
            checkpoint_logger.add_checkpoint(
                "checkpoint_llm_owned_pass_graph_repair",
                stage="llm-owned pass graph repair",
                technique="single LLM-owned pass graph repair",
                input_summary={"error_type": graph_gate.error_type, "error_message": graph_gate.error_message},
                output={
                    "repair_plan": repair_plan.to_dict(),
                    "pass_graph_repair_attempted": True,
                    "pass_graph_repair_success": pass_graph_repair_success,
                    "pass_graph_gate_error_type": graph_gate.error_type,
                    "repaired_pass_count": len(repair_plan.passes or []),
                },
                effect="lets the LLM repair its own pass graph after shape-only feedback",
                correctness_role="backend supplies only graph-shape errors and no replacement subtasks or SQL/API",
                efficiency_role="caps pass graph repair to one attempt",
            )
            checkpoint_logger.add_checkpoint(
                "checkpoint_llm_owned_pass_graph_gate_repair",
                stage="llm-owned pass graph validation",
                technique="shape-only PassGraphGate on repaired plan",
                input_summary={"pass_ids": [item.pass_id for item in repair_plan.passes or []], "evidence_order": repair_plan.evidence_order},
                output=repaired_graph_gate.to_dict(),
                effect="executes repaired plan only if the LLM supplied a valid graph",
                correctness_role="does not add missing passes or choose SQL/API paths",
                efficiency_role="stops after one graph repair attempt",
            )
            if repaired_graph_gate.passed:
                active_plan = repair_plan
                graph_gate = repaired_graph_gate
                pass_specs = active_plan.passes or []
            else:
                graph_gate = repaired_graph_gate
                pass_specs = repair_plan.passes or []
        run_optimizer = V2ExecutionOptimizer(
            budget_limits=BudgetLimits(
                max_passes=run_context.budget.max_passes,
                max_parallelism=run_context.budget.max_parallelism,
                max_sql_workers=run_context.budget.max_sql_workers,
                max_api_workers=run_context.budget.max_api_workers,
                max_repair_attempts=run_context.budget.max_repair_attempts,
                timeout_seconds=run_context.budget.run_timeout_ms / 1000.0,
            ),
            run_id=run_context.run_id,
        )
        optimization_plan = run_optimizer.prepare(pass_specs, graph_gate)
        pipeline_schedule = self.v2_pipeline_scheduler.schedule(
            pass_specs,
            graph_gate,
            parallel_groups=optimization_plan.parallel_groups,
            run_context=run_context,
        )
        summary: dict[str, Any] = {
            "run_id": run_context.run_id,
            "result_bundle_id": run_context.result_bundle_id,
            "evidence_bus_id": run_context.evidence_bus_id,
            "plan_version": run_context.plan_version,
            "sql_gate_passed": None,
            "api_gate_passed": None,
            "sql_compile_gate_passed": None,
            "api_request_gate_passed": None,
            "sql_repair_attempts": 0,
            "api_repair_attempts": 0,
            "sql_executed": False,
            "api_executed": False,
            "multi_pass_enabled": bool(len(pass_specs) > 1 or active_plan.evidence_order == "MULTI_PASS"),
            "llm_pass_graph_used": bool(pass_specs),
            "llm_pass_count": len(pass_specs),
            "parallel_pass_count": sum(1 for item in pass_specs if item.can_run_parallel and not item.depends_on),
            "sequential_pass_count": sum(1 for item in pass_specs if not item.can_run_parallel or item.depends_on),
            "pass_ids": [item.pass_id for item in pass_specs],
            "parallel_groups": graph_gate.parallel_groups,
            "dependency_edges": graph_gate.dependency_edges,
            "pass_graph_gate_passed": graph_gate.passed,
            "pass_graph_repair_attempted": pass_graph_repair_attempted,
            "pass_graph_repair_success": pass_graph_repair_success,
            "pass_graph_gate_error_type": initial_graph_gate_error_type,
            "repaired_pass_count": len(pass_specs) if pass_graph_repair_success else 0,
            **optimization_plan.to_summary(),
            **pipeline_schedule.to_summary(),
            "pass_results_count": 0,
            "passes_executed": [],
            "dependency_resolution_errors": 0,
            "dependency_repair_attempts": 0,
            "backend_semantic_decomposition_used": False,
            "deterministic_answer_template_used": False,
            "hidden_eval_gold_used": False,
        }
        checkpoint_logger.add_checkpoint(
            "checkpoint_v2_execution_optimizer",
            stage="llm-owned execution optimization",
            technique="backend-only scheduling/cache/budget optimizer",
            input_summary={"pass_ids": summary["pass_ids"], "dependency_edges": graph_gate.dependency_edges},
            output=optimization_plan.to_dict(),
            effect="optimizes resource order, exact duplicate work, cache reuse, and budgets without changing LLM semantics",
            correctness_role="does not split prompts, choose SQL/API paths, rewrite SQL/API, or generate answers",
            efficiency_role="prioritizes critical path and enables exact pass-result reuse",
        )
        checkpoint_logger.add_checkpoint(
            "checkpoint_v2_pipeline_scheduler",
            stage="llm-owned pipeline scheduling",
            technique="resource-bounded stage scheduler for LLM-declared pass DAG",
            input_summary={"pass_ids": summary["pass_ids"], "parallel_groups": pipeline_schedule.parallel_groups},
            output=pipeline_schedule.to_dict(),
            effect="moves LLM-declared passes through fixed execution stages without changing pass semantics",
            correctness_role="keeps backend responsibility limited to scheduling, gates, execution, and result storage",
            efficiency_role="allows later passes to enter free stages before earlier passes finish all stages",
        )
        if not graph_gate.passed:
            runtime_passes.append(_pass_graph_error_runtime_pass(graph_gate, run_context=run_context))
            summary["pass_results_count"] = len(runtime_passes)
            return tool_results, runtime_passes, summary
        if optimization_plan.budget_exceeded:
            runtime_passes.append(_budget_error_runtime_pass(optimization_plan, run_context=run_context))
            summary["pass_results_count"] = len(runtime_passes)
            return tool_results, runtime_passes, summary
        checkpoint_logger.add_checkpoint(
            "checkpoint_llm_owned_pass_scheduler",
            stage="llm-owned pass scheduling",
            technique="dependency-aware scheduling of LLM-declared evidence passes",
            input_summary={"pass_ids": summary["pass_ids"], "multi_pass_enabled": summary["multi_pass_enabled"]},
            output=summary,
            effect="schedules only LLM-declared passes; does not split prompts or add semantic subtasks",
            correctness_role="keeps decomposition owned by the LLM and backend role limited to scheduling/gates/execution",
            efficiency_role="groups dependency-free passes without changing their semantics",
        )
        pass_by_id = {item.pass_id: item for item in pass_specs}
        for pass_group in [[pass_by_id[pass_id] for pass_id in group if pass_id in pass_by_id] for group in pipeline_schedule.parallel_groups]:
            for pass_spec in pass_group:
                early_stop = run_optimizer.early_stop_decision(pass_spec, runtime_passes)
                if early_stop.get("skip"):
                    runtime_passes.append(_early_stopped_runtime_pass(pass_spec, early_stop, run_context=run_context))
                    summary.setdefault("early_stopped_passes", []).append(early_stop)
                    continue
                resolved_pass, dependency_resolution = self._resolve_or_repair_llm_owned_pass(
                    query=query,
                    original_plan=active_plan,
                    pass_spec=pass_spec,
                    runtime_passes=runtime_passes,
                    planner_context=planner_context,
                    checkpoint_logger=checkpoint_logger,
                    summary=summary,
                    run_context=run_context,
                )
                if resolved_pass is None:
                    runtime_passes.append(_dependency_error_runtime_pass(pass_spec, dependency_resolution, run_context=run_context))
                    continue
                pass_tool_results: list[dict[str, Any]] = []
                for source in self._llm_owned_pass_execution_order(resolved_pass):
                    cached_result = run_optimizer.lookup_cached_result(
                        resolved_pass,
                        source,
                        target_pass_id=resolved_pass.pass_id,
                    )
                    if cached_result is not None:
                        pass_tool_results.append(cached_result)
                        summary["cache_hits"] = run_optimizer.trace.get("cache_hits", 0)
                        summary["checkpoint_resume_used"] = run_optimizer.trace.get("checkpoint_resume_used", False)
                        continue
                    if source == "sql" and resolved_pass.sql is not None:
                        result = self._run_llm_owned_sql_for_pass(
                            query=query,
                            original_plan=active_plan,
                            pass_spec=resolved_pass,
                            planner_context=planner_context,
                            checkpoint_logger=checkpoint_logger,
                            summary=summary,
                        )
                        if result is not None:
                            pass_tool_results.append(result)
                            tool_results.append(result)
                            run_optimizer.store_result(resolved_pass, source, result)
                    elif source == "api" and resolved_pass.api_request is not None:
                        result = self._run_llm_owned_api_for_pass(
                            query=query,
                            original_plan=active_plan,
                            pass_spec=resolved_pass,
                            planner_context=planner_context,
                            checkpoint_logger=checkpoint_logger,
                            summary=summary,
                        )
                        if result is not None:
                            pass_tool_results.append(result)
                            tool_results.append(result)
                            run_optimizer.store_result(resolved_pass, source, result)
                runtime_pass = _runtime_pass_from_pass_spec(
                    resolved_pass,
                    pass_tool_results,
                    dependency_resolution=dependency_resolution,
                    stage_history=pipeline_schedule.pass_stage_history.get(resolved_pass.pass_id, []),
                    run_context=run_context,
                )
                runtime_passes.append(runtime_pass)
                summary["passes_executed"].append(resolved_pass.pass_id)
        summary["pass_results_count"] = len(runtime_passes)
        summary["cache_hits"] = run_optimizer.trace.get("cache_hits", summary.get("cache_hits", 0))
        summary["checkpoint_resume_used"] = run_optimizer.trace.get("checkpoint_resume_used", summary.get("checkpoint_resume_used", False))
        return tool_results, runtime_passes, summary

    def _resolve_or_repair_llm_owned_pass(
        self,
        *,
        query: str,
        original_plan: LLMUnifiedPlan,
        pass_spec: LLMUnifiedPass,
        runtime_passes: list[dict[str, Any]],
        planner_context: dict[str, Any],
        checkpoint_logger: CheckpointLogger,
        summary: dict[str, Any],
        run_context: RunContext,
    ) -> tuple[LLMUnifiedPass | None, dict[str, Any]]:
        resolved_pass, resolution = _resolve_pass_placeholders(pass_spec, runtime_passes, run_id=run_context.run_id)
        checkpoint_logger.add_checkpoint(
            "checkpoint_llm_owned_dependency_resolution",
            stage="llm-owned pass dependency resolution",
            technique="placeholder resolution from completed LLM pass results",
            input_summary={"pass_id": pass_spec.pass_id, "depends_on": pass_spec.depends_on},
            output=resolution,
            effect="resolves only placeholders explicitly declared by the LLM pass graph",
            correctness_role="does not infer missing dependency values or add backend-selected subtasks",
            efficiency_role="prevents executing unresolved placeholder SQL/API calls",
        )
        if resolution.get("resolved"):
            return resolved_pass, resolution

        summary["dependency_resolution_errors"] = int(summary.get("dependency_resolution_errors", 0) or 0) + 1
        repair_plan = run_llm_unified_planner(
            user_prompt=query,
            schema_context=planner_context["schema_context"],
            endpoint_context=planner_context["endpoint_context"],
            repair_context={
                "failed_component": "dependency_resolution",
                "pass_id": pass_spec.pass_id,
                "subtask": pass_spec.subtask,
                "dependency_resolution": resolution,
                "previous_plan": original_plan.to_dict(),
                "completed_passes": compact_preview(runtime_passes, 1800),
            },
        )
        summary["dependency_repair_attempts"] = int(summary.get("dependency_repair_attempts", 0) or 0) + 1
        checkpoint_logger.add_checkpoint(
            "checkpoint_llm_owned_dependency_resolution_repair",
            stage="llm-owned pass dependency repair",
            technique="single LLM-owned dependency placeholder repair",
            input_summary={"pass_id": pass_spec.pass_id, "errors": resolution.get("errors", [])},
            output=repair_plan.to_dict(),
            effect="lets the LLM repair its pass placeholders after dependency-resolution feedback",
            correctness_role="backend supplies only resolution errors and no replacement SQL/API",
            efficiency_role="caps dependency repair to one attempt",
        )
        repaired_pass = _repaired_pass_for(repair_plan, pass_spec.pass_id, source=_primary_pass_source(pass_spec))
        if repaired_pass is None:
            return None, {**resolution, "repair_attempted": True, "repair_resolved": False}
        repaired_resolved_pass, repaired_resolution = _resolve_pass_placeholders(repaired_pass, runtime_passes, run_id=run_context.run_id)
        repaired_resolution = {**repaired_resolution, "repair_attempted": True}
        checkpoint_logger.add_checkpoint(
            "checkpoint_llm_owned_dependency_resolution_repair_check",
            stage="llm-owned pass dependency resolution",
            technique="placeholder resolution for repaired LLM pass",
            input_summary={"pass_id": repaired_pass.pass_id, "depends_on": repaired_pass.depends_on},
            output=repaired_resolution,
            effect="checks repaired placeholders without backend mutation",
            correctness_role="executes repaired pass only if placeholders resolve from prior pass evidence",
            efficiency_role="stops after one dependency repair",
        )
        if repaired_resolution.get("resolved"):
            return repaired_resolved_pass, repaired_resolution
        return None, repaired_resolution

    def _run_llm_owned_sql_for_pass(
        self,
        *,
        query: str,
        original_plan: LLMUnifiedPlan,
        pass_spec: LLMUnifiedPass,
        planner_context: dict[str, Any],
        checkpoint_logger: CheckpointLogger,
        summary: dict[str, Any],
    ) -> dict[str, Any] | None:
        candidate = pass_spec.sql
        if candidate is None:
            return None
        compile_result = self.sql_compile_gate.check(candidate.query, candidate.params)
        summary["sql_gate_passed"] = compile_result.passed
        summary["sql_compile_gate_passed"] = compile_result.passed
        checkpoint_logger.add_checkpoint(
            "checkpoint_llm_owned_sql_compile_gate",
            stage="llm sql compile gate",
            technique="DuckDB EXPLAIN compile check for LLM-owned SQL pass",
            input_summary={"pass_id": pass_spec.pass_id, "sql": candidate.query},
            output={"pass_id": pass_spec.pass_id, **compile_result.to_dict()},
            effect="checks syntax/database-semantic validity without rewriting SQL",
            correctness_role="returns compile errors for one LLM repair attempt",
            efficiency_role="prevents executing uncompilable SQL",
        )
        if not compile_result.passed:
            repair_plan = run_llm_unified_planner(
                user_prompt=query,
                schema_context=planner_context["schema_context"],
                endpoint_context=planner_context["endpoint_context"],
                repair_context={
                    "failed_component": "sql",
                    "pass_id": pass_spec.pass_id,
                    "subtask": pass_spec.subtask,
                    "compile_gate": compile_result.to_dict(),
                    "previous_plan": original_plan.to_dict(),
                },
            )
            summary["sql_repair_attempts"] = int(summary.get("sql_repair_attempts", 0) or 0) + 1
            checkpoint_logger.add_checkpoint(
                "checkpoint_llm_owned_sql_repair",
                stage="llm sql repair",
                technique="single LLM-owned SQL pass repair",
                input_summary={"pass_id": pass_spec.pass_id, "failed_sql": candidate.query, "error_type": compile_result.error_type},
                output=repair_plan.to_dict(),
                effect="lets the LLM repair its pass SQL after compile feedback",
                correctness_role="backend supplies only compile error feedback and no replacement SQL",
                efficiency_role="caps repair to one attempt",
            )
            repaired_pass = _repaired_pass_for(repair_plan, pass_spec.pass_id, source="sql")
            if repaired_pass is None or repaired_pass.sql is None:
                return _blocked_sql_tool_result(candidate.query, candidate.params, compile_result, pass_id=pass_spec.pass_id, subtask=pass_spec.subtask)
            repaired_compile = self.sql_compile_gate.check(repaired_pass.sql.query, repaired_pass.sql.params)
            summary["sql_gate_passed"] = repaired_compile.passed
            summary["sql_compile_gate_passed"] = repaired_compile.passed
            checkpoint_logger.add_checkpoint(
                "checkpoint_llm_owned_sql_compile_gate_repair",
                stage="llm sql compile gate",
                technique="DuckDB EXPLAIN compile check for repaired LLM-owned SQL pass",
                input_summary={"pass_id": pass_spec.pass_id, "sql": repaired_pass.sql.query},
                output={"pass_id": pass_spec.pass_id, **repaired_compile.to_dict()},
                effect="checks the LLM repair without backend mutation",
                correctness_role="executes repaired SQL only if it compiles",
                efficiency_role="stops after one repair",
            )
            if not repaired_compile.passed:
                return _blocked_sql_tool_result(repaired_pass.sql.query, repaired_pass.sql.params, repaired_compile, pass_id=pass_spec.pass_id, subtask=pass_spec.subtask)
            candidate = repaired_pass.sql
        payload = self.db.execute_sql(candidate.query, params=candidate.params, allow_full_result=True)
        summary["sql_executed"] = True
        validation = ValidationResult(True, warnings=["LLM SQL pass passed compile gate."], errors=[])
        step = PlanStep(
            action="sql",
            purpose=f"V2 LLM-owned SQL pass: {pass_spec.subtask}",
            sql=candidate.query,
            allow_full_result=True,
            family="llm_owned_v2",
        )
        return {
            "type": "sql",
            "pass_id": pass_spec.pass_id,
            "subtask": pass_spec.subtask,
            "expected_result": pass_spec.expected_result,
            "step": step.to_dict(),
            "validation": validation.to_dict(),
            "payload": payload,
        }

    def _run_llm_owned_api_for_pass(
        self,
        *,
        query: str,
        original_plan: LLMUnifiedPlan,
        pass_spec: LLMUnifiedPass,
        planner_context: dict[str, Any],
        checkpoint_logger: CheckpointLogger,
        summary: dict[str, Any],
    ) -> dict[str, Any] | None:
        request = pass_spec.api_request
        if request is None:
            return None
        gate_result = self.api_request_gate.check(request)
        summary["api_gate_passed"] = gate_result.passed
        summary["api_request_gate_passed"] = gate_result.passed
        checkpoint_logger.add_checkpoint(
            "checkpoint_llm_owned_api_request_gate",
            stage="llm api request gate",
            technique="safe GET request-shape/catalog gate for LLM-owned API pass",
            input_summary={"pass_id": pass_spec.pass_id, "method": request.method, "path": request.path},
            output={"pass_id": pass_spec.pass_id, **gate_result.to_dict()},
            effect="checks only executable API request shape before runtime execution",
            correctness_role="blocks unsafe method, unknown endpoint, unresolved path, or malformed params",
            efficiency_role="prevents invalid API calls without planning endpoints",
        )
        if not gate_result.passed:
            repair_plan = run_llm_unified_planner(
                user_prompt=query,
                schema_context=planner_context["schema_context"],
                endpoint_context=planner_context["endpoint_context"],
                repair_context={
                    "failed_component": "api_request",
                    "pass_id": pass_spec.pass_id,
                    "subtask": pass_spec.subtask,
                    "api_request_gate": gate_result.to_dict(),
                    "previous_plan": original_plan.to_dict(),
                },
            )
            summary["api_repair_attempts"] = int(summary.get("api_repair_attempts", 0) or 0) + 1
            checkpoint_logger.add_checkpoint(
                "checkpoint_llm_owned_api_request_repair",
                stage="llm api request repair",
                technique="single LLM-owned API pass repair",
                input_summary={"pass_id": pass_spec.pass_id, "failed_api_request": request.to_dict(), "error_type": gate_result.error_type},
                output=repair_plan.to_dict(),
                effect="lets the LLM repair request shape after gate feedback",
                correctness_role="backend supplies only request errors and no replacement endpoint",
                efficiency_role="caps repair to one attempt",
            )
            repaired_pass = _repaired_pass_for(repair_plan, pass_spec.pass_id, source="api")
            if repaired_pass is None or repaired_pass.api_request is None:
                return _blocked_api_tool_result(gate_result, pass_id=pass_spec.pass_id, subtask=pass_spec.subtask)
            repaired_gate = self.api_request_gate.check(repaired_pass.api_request)
            summary["api_gate_passed"] = repaired_gate.passed
            summary["api_request_gate_passed"] = repaired_gate.passed
            checkpoint_logger.add_checkpoint(
                "checkpoint_llm_owned_api_request_gate_repair",
                stage="llm api request gate",
                technique="request gate for repaired LLM-owned API pass",
                input_summary={"pass_id": pass_spec.pass_id, "method": repaired_pass.api_request.method, "path": repaired_pass.api_request.path},
                output={"pass_id": pass_spec.pass_id, **repaired_gate.to_dict()},
                effect="checks repaired request without backend endpoint replacement",
                correctness_role="executes repaired request only if it passes",
                efficiency_role="stops after one repair",
            )
            if not repaired_gate.passed:
                return _blocked_api_tool_result(repaired_gate, pass_id=pass_spec.pass_id, subtask=pass_spec.subtask)
            request = repaired_pass.api_request
            gate_result = repaired_gate
        method = str(gate_result.method or request.method)
        path = str(gate_result.path or request.path)
        params = dict(gate_result.params or request.params or {})
        payload = self.api_client.call_api(method, path, params, {})
        summary["api_executed"] = True
        validation = ValidationResult(True, warnings=["LLM API request pass passed request gate."], errors=[])
        step = PlanStep(
            action="api",
            purpose=f"V2 LLM-owned API pass: {pass_spec.subtask}",
            method=method,
            url=path,
            params=params,
            headers={},
            family="llm_owned_v2",
        )
        return {
            "type": "api",
            "pass_id": pass_spec.pass_id,
            "subtask": pass_spec.subtask,
            "expected_result": pass_spec.expected_result,
            "step": step.to_dict(),
            "validation": validation.to_dict(),
            "payload": payload,
        }

    def _run_llm_owned_sql_candidate(
        self,
        *,
        query: str,
        plan: LLMUnifiedPlan,
        planner_context: dict[str, Any],
        checkpoint_logger: CheckpointLogger,
        summary: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, LLMUnifiedPlan]:
        candidate = plan.sql
        if candidate is None:
            return None, plan
        compile_result = self.sql_compile_gate.check(candidate.query, candidate.params)
        summary["sql_gate_passed"] = compile_result.passed
        summary["sql_compile_gate_passed"] = compile_result.passed
        checkpoint_logger.add_checkpoint(
            "checkpoint_llm_owned_sql_compile_gate",
            stage="llm sql compile gate",
            technique="DuckDB EXPLAIN compile check for LLM-owned SQL",
            input_summary={"sql": candidate.query},
            output=compile_result.to_dict(),
            effect="checks syntax/database-semantic validity without rewriting SQL",
            correctness_role="returns compile errors for one LLM repair attempt",
            efficiency_role="prevents executing uncompilable SQL",
        )
        if not compile_result.passed:
            repair_plan = run_llm_unified_planner(
                user_prompt=query,
                schema_context=planner_context["schema_context"],
                endpoint_context=planner_context["endpoint_context"],
                repair_context={"failed_component": "sql", "compile_gate": compile_result.to_dict(), "previous_plan": plan.to_dict()},
            )
            summary["sql_repair_attempts"] = 1
            checkpoint_logger.add_checkpoint(
                "checkpoint_llm_owned_sql_repair",
                stage="llm sql repair",
                technique="single LLM-owned SQL repair",
                input_summary={"failed_sql": candidate.query, "error_type": compile_result.error_type},
                output=repair_plan.to_dict(),
                effect="lets the LLM repair its SQL after compile feedback",
                correctness_role="backend supplies only compile error feedback and no replacement SQL",
                efficiency_role="caps repair to one attempt",
            )
            if repair_plan.sql is None:
                return _blocked_sql_tool_result(candidate.query, candidate.params, compile_result), repair_plan
            repaired_compile = self.sql_compile_gate.check(repair_plan.sql.query, repair_plan.sql.params)
            summary["sql_gate_passed"] = repaired_compile.passed
            summary["sql_compile_gate_passed"] = repaired_compile.passed
            checkpoint_logger.add_checkpoint(
                "checkpoint_llm_owned_sql_compile_gate_repair",
                stage="llm sql compile gate",
                technique="DuckDB EXPLAIN compile check for repaired LLM-owned SQL",
                input_summary={"sql": repair_plan.sql.query},
                output=repaired_compile.to_dict(),
                effect="checks the LLM repair without backend mutation",
                correctness_role="executes repaired SQL only if it compiles",
                efficiency_role="stops after one repair",
            )
            if not repaired_compile.passed:
                return _blocked_sql_tool_result(repair_plan.sql.query, repair_plan.sql.params, repaired_compile), repair_plan
            candidate = repair_plan.sql
            plan = repair_plan
        payload = self.db.execute_sql(candidate.query, params=candidate.params, allow_full_result=True)
        summary["sql_executed"] = True
        validation = ValidationResult(True, warnings=["LLM SQL passed compile gate."], errors=[])
        step = PlanStep(
            action="sql",
            purpose="V2 LLM-owned SQL candidate.",
            sql=candidate.query,
            allow_full_result=True,
            family="llm_owned_v2",
        )
        return {"type": "sql", "step": step.to_dict(), "validation": validation.to_dict(), "payload": payload}, plan

    def _run_llm_owned_api_candidate(
        self,
        *,
        query: str,
        plan: LLMUnifiedPlan,
        planner_context: dict[str, Any],
        checkpoint_logger: CheckpointLogger,
        summary: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, LLMUnifiedPlan]:
        request = plan.api_request
        if request is None:
            return None, plan
        gate_result = self.api_request_gate.check(request)
        summary["api_gate_passed"] = gate_result.passed
        summary["api_request_gate_passed"] = gate_result.passed
        checkpoint_logger.add_checkpoint(
            "checkpoint_llm_owned_api_request_gate",
            stage="llm api request gate",
            technique="safe GET request-shape/catalog gate",
            input_summary={"method": request.method, "path": request.path},
            output=gate_result.to_dict(),
            effect="checks only executable API request shape before runtime execution",
            correctness_role="blocks unsafe method, unknown endpoint, unresolved path, or malformed params",
            efficiency_role="prevents invalid API calls without planning endpoints",
        )
        if not gate_result.passed:
            repair_plan = run_llm_unified_planner(
                user_prompt=query,
                schema_context=planner_context["schema_context"],
                endpoint_context=planner_context["endpoint_context"],
                repair_context={"failed_component": "api_request", "api_request_gate": gate_result.to_dict(), "previous_plan": plan.to_dict()},
            )
            summary["api_repair_attempts"] = 1
            checkpoint_logger.add_checkpoint(
                "checkpoint_llm_owned_api_request_repair",
                stage="llm api request repair",
                technique="single LLM-owned API request repair",
                input_summary={"failed_api_request": request.to_dict(), "error_type": gate_result.error_type},
                output=repair_plan.to_dict(),
                effect="lets the LLM repair request shape after gate feedback",
                correctness_role="backend supplies only request errors and no replacement endpoint",
                efficiency_role="caps repair to one attempt",
            )
            if repair_plan.api_request is None:
                return _blocked_api_tool_result(gate_result), repair_plan
            repaired_gate = self.api_request_gate.check(repair_plan.api_request)
            summary["api_gate_passed"] = repaired_gate.passed
            summary["api_request_gate_passed"] = repaired_gate.passed
            checkpoint_logger.add_checkpoint(
                "checkpoint_llm_owned_api_request_gate_repair",
                stage="llm api request gate",
                technique="request gate for repaired LLM-owned API request",
                input_summary={"method": repair_plan.api_request.method, "path": repair_plan.api_request.path},
                output=repaired_gate.to_dict(),
                effect="checks repaired request without backend endpoint replacement",
                correctness_role="executes repaired request only if it passes",
                efficiency_role="stops after one repair",
            )
            if not repaired_gate.passed:
                return _blocked_api_tool_result(repaired_gate), repair_plan
            request = repair_plan.api_request
            gate_result = repaired_gate
            plan = repair_plan
        method = str(gate_result.method or request.method)
        path = str(gate_result.path or request.path)
        params = dict(gate_result.params or request.params or {})
        payload = self.api_client.call_api(method, path, params, {})
        summary["api_executed"] = True
        validation = ValidationResult(True, warnings=["LLM API request passed request gate."], errors=[])
        step = PlanStep(
            action="api",
            purpose="V2 LLM-owned API request.",
            method=method,
            url=path,
            params=params,
            headers={},
            family="llm_owned_v2",
        )
        return {"type": "api", "step": step.to_dict(), "validation": validation.to_dict(), "payload": payload}, plan

    def _llm_owned_execution_order(self, plan: LLMUnifiedPlan) -> list[str]:
        if plan.evidence_order in {"API_FIRST", "API_THEN_SQL"}:
            return ["api", "sql"]
        if plan.evidence_order == "PARALLEL":
            return ["sql", "api"]
        return ["sql", "api"]

    def _llm_owned_pass_execution_order(self, pass_spec: LLMUnifiedPass) -> list[str]:
        if pass_spec.path == "SQL":
            return ["sql"]
        if pass_spec.path == "API":
            return ["api"]
        if pass_spec.path in {"DIRECT", "AGGREGATION_ONLY"}:
            return []
        if pass_spec.evidence_order in {"API_FIRST", "API_THEN_SQL"}:
            return ["api", "sql"]
        if pass_spec.evidence_order == "NO_EVIDENCE":
            return []
        return ["sql", "api"]

    def _schedule_llm_owned_passes(self, passes: list[LLMUnifiedPass]) -> list[LLMUnifiedPass]:
        pending = list(passes)
        complete: set[str] = set()
        ordered: list[LLMUnifiedPass] = []
        while pending:
            ready = [item for item in pending if all(dep in complete for dep in item.depends_on)]
            if not ready:
                ordered.extend(pending)
                break
            parallel_ready = [item for item in ready if item.can_run_parallel and not item.depends_on]
            sequential_ready = [item for item in ready if item not in parallel_ready]
            for item in [*parallel_ready, *sequential_ready]:
                ordered.append(item)
                complete.add(item.pass_id)
                pending.remove(item)
        return ordered

    def _llm_owned_planner_context(self) -> dict[str, Any]:
        return {
            "schema_context": self.db.get_schema_summary(),
            "endpoint_context": [
                {
                    "id": endpoint.get("id"),
                    "method": endpoint.get("method"),
                    "path": endpoint.get("path"),
                    "use_when": endpoint.get("use_when"),
                    "common_params": endpoint.get("common_params", {}),
                    "path_params": endpoint.get("path_params", []),
                    "domains": endpoint.get("domains", []),
                }
                for endpoint in self.endpoint_catalog.as_list()
            ],
        }

    def _llm_owned_plan_dict(self, strategy: str, plan: LLMUnifiedPlan, tool_results: list[dict[str, Any]]) -> dict[str, Any]:
        steps: list[dict[str, Any]] = []
        if plan.sql is not None:
            steps.append({"action": "sql", "sql": plan.sql.query, "params": plan.sql.params})
        if plan.api_request is not None:
            steps.append({"action": "api", **plan.api_request.to_dict()})
        return {
            "strategy": strategy,
            "rationale": plan.reason,
            "llm_owned_generation": True,
            "backend_semantic_planning_used": False,
            "route": plan.route,
            "evidence_order": plan.evidence_order,
            "passes": [item.to_dict() for item in plan.passes],
            "aggregation_instruction": plan.aggregation_instruction,
            "steps": steps,
            "executed_tool_count": len(tool_results),
        }

    def _compact_context_experiment_candidate(self, *, query: str, strategy: str, output_dir: Path) -> dict[str, Any]:
        if not self.config.enable_compact_context_when_schema_vote_safe:
            return {"active": False, "eligible": False, "reason": "ENABLE_COMPACT_CONTEXT_WHEN_SCHEMA_VOTE_SAFE is off"}
        if not _is_compact_experiment_output(output_dir, self.config.outputs_dir):
            return {
                "active": False,
                "eligible": False,
                "reason": "output_dir is not under outputs/compact_context_measured_eval",
                "packaged_default": False,
                "packaged_execution_changed": False,
            }
        reasons: list[str] = []
        if strategy != "SQL_FIRST_API_VERIFY":
            reasons.append("strategy is not SQL_FIRST_API_VERIFY")
        if self.config.enable_gated_risk_cluster_repair_execution:
            reasons.append("repair execution is enabled")
        compact_context = build_candidate_context(
            query,
            self.schema_index,
            self.endpoint_catalog,
            enable_hybrid_ranking=self.config.enable_hybrid_candidate_scoring,
            enable_endpoint_family_ranking=self.config.enable_endpoint_family_ranking,
            enable_structural_preservation=self.config.enable_structural_schema_preservation,
            enable_value_to_api_ranking=self.config.enable_value_to_api_ranking,
            enable_gated_risk_cluster_repair=self.config.enable_gated_risk_cluster_repair,
        )
        risk_policy = classify_candidate_risk(
            compact_context,
            risk_cluster=(compact_context.get("gated_risk_cluster_repair") or {}).get("risk_cluster"),
        )
        schema_vote = vote_schema_contexts(
            query=query,
            compact_context=compact_context,
            schema_index=self.schema_index,
            endpoint_catalog=self.endpoint_catalog,
            risk_level=risk_policy["risk_level"],
        )
        compact_tables = schema_vote.get("compact_candidate_tables") or []
        fallback_tables = schema_vote.get("fallback_candidate_tables") or []
        compact_apis = schema_vote.get("compact_candidate_apis") or []
        fallback_apis = schema_vote.get("fallback_candidate_apis") or []
        table_top_agreement = _top_items_agree(compact_tables, fallback_tables)
        api_top_agreement = _top_items_agree(compact_apis, fallback_apis) or (not compact_apis and not fallback_apis)
        if risk_policy.get("risk_level") != "high":
            reasons.append("risk_level is not high")
        if schema_vote.get("schema_vote_agreement") is not True:
            reasons.append("schema_vote_agreement is not true")
        if schema_vote.get("compact_context_safe") is not True:
            reasons.append("compact_context_safe is not true")
        if not table_top_agreement:
            reasons.append("compact/fallback top tables do not agree")
        if not api_top_agreement:
            reasons.append("compact/fallback top APIs do not agree")
        eligible = not reasons
        return {
            "active": True,
            "eligible": eligible,
            "reason": "compact context enabled for measured experiment" if eligible else "; ".join(reasons),
            "risk_level": risk_policy.get("risk_level"),
            "accuracy_risk": risk_policy.get("accuracy_risk"),
            "schema_vote_agreement": schema_vote.get("schema_vote_agreement"),
            "compact_context_safe": schema_vote.get("compact_context_safe"),
            "table_top_agreement": table_top_agreement,
            "api_top_agreement": api_top_agreement,
            "compact_tables": compact_tables[:8],
            "fallback_tables": fallback_tables[:8],
            "compact_apis": compact_apis[:8],
            "fallback_apis": fallback_apis[:8],
            "compact_context_tokens": schema_vote.get("compact_context_tokens"),
            "fallback_context_tokens": schema_vote.get("fallback_context_tokens"),
            "expected_token_savings": schema_vote.get("token_delta"),
            "diagnostic_only": True,
            "packaged_default": False,
            "packaged_execution_changed": False,
            "repair_execution_enabled": self.config.enable_gated_risk_cluster_repair_execution,
            "compact_context": compact_context,
            }

    def _add_semantic_route_harness_checkpoints(self, query: str, checkpoint_logger: CheckpointLogger) -> Any | None:
        if not self.config.enable_objective_prompt_features:
            return None
        try:
            features = extract_objective_prompt_features(query)
            checkpoint_logger.add_checkpoint(
                "checkpoint_objective_prompt_features",
                stage="semantic routing shadow",
                technique="objective prompt feature extraction",
                input_summary={"query": query},
                output=features.to_dict(),
                effect="records fact-only prompt cues for semantic routing diagnostics",
                correctness_role="keeps semantic pre-routing separate from SQL/API planning and answer generation",
                efficiency_role="uses compact symbolic features before any optional LLM classification",
            )
            if not (self.config.enable_semantic_intent_classifier or self.config.enable_semantic_route_decision_ladder):
                return None
            if self.config.enable_semantic_route_decision_ladder:
                ladder = run_semantic_route_decision_ladder(
                    query,
                    enable_semantic_parse=self.config.enable_semantic_parse,
                    tier2_diagnostic=self.config.semantic_route_tier2_diagnostic,
                    shadow_only=self.config.semantic_route_shadow_only,
                )
                checkpoint_logger.add_checkpoint(
                    "checkpoint_semantic_parse",
                    stage="semantic routing shadow",
                    technique="semantic role parse",
                    input_summary={"feature_codes": features.to_dict()},
                    output=ladder.semantic_parse,
                    effect="separates operation role, target grounding, instance level, and evidence need before route selection",
                    correctness_role="prevents keyword-only no-tool blocking or allowing decisions",
                    efficiency_role="adds compact parse metadata without executing tools",
                )
                checkpoint_logger.add_checkpoint(
                    "checkpoint_semantic_intent_decision",
                    stage="semantic routing shadow",
                    technique="compact SemanticIntentDecision classification",
                    input_summary={"feature_codes": features.to_dict()},
                    output=ladder.semantic_intent_decision,
                    effect="records semantic intent decision without generating SQL, API calls, or answers",
                    correctness_role="keeps no-tool candidates explicit for verifier review",
                    efficiency_role="measures whether conceptual false positives could avoid tools in a future gate",
                )
                checkpoint_logger.add_checkpoint(
                    "checkpoint_routing_anti_hallucination_gate",
                    stage="semantic routing shadow",
                    technique="objective support check for semantic intent",
                    input_summary={"semantic_intent": ladder.semantic_intent_decision},
                    output=ladder.routing_anti_hallucination_gate,
                    effect="blocks unsupported no-tool or capability claims and records one-revision fallback state",
                    correctness_role="prevents LLM semantic hints from overriding objective data cues",
                    efficiency_role="limits revision feedback to compact codes and keeps packaged execution unchanged",
                )
                checkpoint_logger.add_checkpoint(
                    "checkpoint_minimal_correction_feedback_semantic",
                    stage="semantic routing shadow",
                    technique="minimal semantic correction feedback",
                    input_summary={"semantic_intent": ladder.semantic_intent_decision},
                    output=ladder.checkpoints.get("checkpoint_minimal_correction_feedback_semantic", {}),
                    effect="records compact conflict deltas for one LLM semantic revision",
                    correctness_role="gate reports conflicts without replacing the LLM semantic decision",
                    efficiency_role="keeps revision payload compact",
                )
                checkpoint_logger.add_checkpoint(
                    "checkpoint_semantic_revision_result",
                    stage="semantic routing shadow",
                    technique="single semantic decision revision result",
                    input_summary={"gate_revision_attempted": ladder.routing_anti_hallucination_gate.get("revision_attempted")},
                    output=ladder.checkpoints.get("checkpoint_semantic_revision_result", {}),
                    effect="records whether LLM revision fixed semantic conflicts",
                    correctness_role="falls back only after conflict persists",
                    efficiency_role="limits semantic revision attempts to one",
                )
                checkpoint_logger.add_checkpoint(
                    "checkpoint_semantic_fallback_if_any",
                    stage="semantic routing shadow",
                    technique="risk-minimizing semantic fallback marker",
                    input_summary={"action": ladder.action},
                    output=ladder.checkpoints.get("checkpoint_semantic_fallback_if_any", {}),
                    effect="records fallback only when semantic conflicts remain after revision",
                    correctness_role="does not claim deterministic semantic certainty",
                    efficiency_role="uses no extra tools",
                )
                checkpoint_logger.add_checkpoint(
                    "checkpoint_semantic_consistency_verifier",
                    stage="semantic routing shadow",
                    technique="semantic parse and route consistency verifier",
                    input_summary={"semantic_parse": ladder.semantic_parse, "semantic_intent": ladder.semantic_intent_decision},
                    output=ladder.semantic_consistency,
                    effect="allows no-tool only when semantic roles are conceptual, meta-language, or out-of-domain",
                    correctness_role="blocks real instance-level data requests without treating every cue word as retrieval",
                    efficiency_role="keeps safe conceptual prompts from entering the evidence pipeline",
                )
                checkpoint_logger.add_checkpoint(
                    "checkpoint_progressive_evidence_policy",
                    stage="semantic routing candidate",
                    technique="progressive evidence early-exit policy",
                    input_summary={"semantic_action": ladder.action},
                    output=ladder.checkpoints.get("checkpoint_progressive_evidence_policy", {}),
                    effect="restricts early semantic routing to safe no-tool or single-endpoint API probe exits",
                    correctness_role="forces ambiguous and data-like prompts into evidence acquisition before post-evidence decisions",
                    efficiency_role="keeps low-risk conceptual/API-only exits available while avoiding high-risk branch decisions",
                )
                checkpoint_logger.add_checkpoint(
                    "checkpoint_no_tool_safety_verifier",
                    stage="semantic routing shadow",
                    technique="semantic consistency compatibility no-tool view",
                    input_summary={"semantic_intent": ladder.semantic_intent_decision},
                    output=ladder.no_tool_safety,
                    effect="records the semantic consistency result in the legacy no-tool safety checkpoint slot",
                    correctness_role="blocks concrete data prompts from direct LLM handling while allowing keyword decoys",
                    efficiency_role="estimates safe no-tool savings without changing packaged behavior",
                )
                checkpoint_logger.add_checkpoint(
                    "checkpoint_semantic_route_decision_ladder",
                    stage="semantic routing shadow",
                    technique="uncertainty escalation ladder",
                    input_summary={"shadow_only": self.config.semantic_route_shadow_only},
                    output={
                        "action": ladder.action,
                        "tier_used": ladder.tier_used,
                        "low_low_case": ladder.low_low_case,
                        "context_token_cost": ladder.context_token_cost,
                        "safe_api_probe": ladder.safe_api_probe,
                        "shadow_only": ladder.shadow_only,
                        "promotion_allowed": ladder.promotion_allowed,
                    },
                    effect="records the shadow action that would be considered by a future promotion gate",
                    correctness_role="never applies semantic routing to the packaged plan in shadow mode",
                    efficiency_role="estimates tool-call and context-token tradeoffs",
                )
                return ladder
            context = build_semantic_intent_context(features, tier=0)
            decision = classify_semantic_intent(context, use_llm=True)
            gate = run_routing_gate_with_revision(features, decision) if self.config.enable_routing_anti_hallucination_gate else None
            decision_for_safety = gate.final_decision if gate else decision
            safety = verify_no_tool_safety(features, decision)
            checkpoint_logger.add_checkpoint(
                "checkpoint_semantic_intent_decision",
                stage="semantic routing shadow",
                technique="compact SemanticIntentDecision classification",
                input_summary={"context_token_cost": estimate_context_tokens(context)},
                output=decision.to_dict(),
                effect="records semantic intent decision without generating SQL, API calls, or answers",
                correctness_role="keeps no-tool candidates explicit for verifier review",
                efficiency_role="measures classifier behavior without changing packaged routing",
            )
            if gate is not None:
                checkpoint_logger.add_checkpoint(
                    "checkpoint_routing_anti_hallucination_gate",
                    stage="semantic routing shadow",
                    technique="objective support check for semantic intent",
                    input_summary={"semantic_intent": decision.to_dict()},
                    output=gate.to_dict(),
                    effect="validates semantic intent support without choosing final SQL/API route",
                    correctness_role="blocks unsupported no-tool or capability claims before safety verification",
                    efficiency_role="records compact feedback/fallback only in shadow mode",
                )
                safety = verify_no_tool_safety(features, decision_for_safety)
            checkpoint_logger.add_checkpoint(
                "checkpoint_no_tool_safety_verifier",
                stage="semantic routing shadow",
                technique="negative no-tool safety guardrail",
                input_summary={"semantic_intent": decision_for_safety.to_dict()},
                output=safety.to_dict(),
                effect="allows or blocks only no-tool decisions and never chooses SQL/API routes",
                correctness_role="blocks concrete data prompts from direct LLM handling",
                efficiency_role="estimates safe no-tool savings without changing packaged behavior",
            )
        except Exception as exc:
            checkpoint_logger.add_error_checkpoint(
                "checkpoint_semantic_route_decision_ladder",
                stage="semantic routing shadow",
                technique="semantic routing harness failure capture",
                input_summary={"query": query},
                error=f"{type(exc).__name__}: {exc}",
                warnings=["semantic routing harness shadow checkpoint failed; packaged runtime path continued"],
            )
        return None

    def _semantic_no_tool_applied_decision(self, ladder: Any | None, *, query: str, strategy: str) -> dict[str, Any]:
        enabled = bool(
            self.config.enable_semantic_no_tool_applied_trial
            or self.config.enable_combined_safe_applied_trial
        )
        if not enabled:
            return {"record": False, "applied": False}
        payload = ladder.to_dict() if hasattr(ladder, "to_dict") else {}
        action = str(payload.get("action") or "")
        safety = payload.get("no_tool_safety") if isinstance(payload.get("no_tool_safety"), dict) else {}
        decision = payload.get("semantic_intent_decision") if isinstance(payload.get("semantic_intent_decision"), dict) else {}
        blocked = list(safety.get("block") or [])
        allowed = should_bypass_evidence_for_llm_direct(
            payload,
            strategy=strategy,
            prompt=query,
        )
        return {
            "record": True,
            "trial_mode": self.config.real_behavior_trial_mode or "semantic_no_tool_applied_real_trial",
            "decision_family": "SEMANTIC_NO_TOOL",
            "decision": action or "FALLBACK",
            "applied": allowed,
            "fallback": not allowed,
            "blockers": [] if allowed else blocked or ["PRE_EVIDENCE_LLM_DIRECT_BYPASS_NOT_ALLOWED"],
            "semantic_confidence": round(float(decision.get("conf") or 0.0), 4),
            "evidence_need_score": safety.get("evidence_need_score"),
            "evidence_pipeline_bypassed": bool(allowed),
            "bypass_reason": "high_confidence_llm_direct_no_evidence_required" if allowed else None,
            "shadow_only": False,
        }

    def _return_semantic_no_tool_applied_result(
        self,
        *,
        query: str,
        qid: str,
        strategy: str,
        out_dir: Path,
        prompt_route: Any,
        checkpoint_logger: CheckpointLogger,
        trial_decision: dict[str, Any],
    ) -> dict[str, Any]:
        final_answer = _conceptual_no_tool_answer(query)
        safe_check = validate_llm_safe_direct_answer(final_answer)
        if not safe_check.get("ok"):
            trial_decision["applied"] = False
            trial_decision["fallback"] = True
            trial_decision["blockers"] = list(safe_check.get("blocked_claims") or [])
            final_answer = "This is a conceptual question; no concrete runtime records were used."
            safe_check = validate_llm_safe_direct_answer(final_answer)
        boundary_payload = {
            "evidence_pipeline_bypassed": True,
            "bypass_reason": "high_confidence_llm_direct_no_evidence_required",
            "pre_evidence_route": trial_decision.get("decision") or "LLM_SAFE_DIRECT",
            "confidence": trial_decision.get("semantic_confidence"),
            "post_evidence_answer_router_ran": False,
            "evidence_bus_built": False,
        }
        metadata = {
            "query_id": qid,
            "query": query,
            "strategy": strategy,
            "prompt_route": prompt_route.to_dict(),
            "real_behavior_trial": trial_decision,
            "evidence_pipeline_bypassed": True,
            "bypass_reason": boundary_payload["bypass_reason"],
            "note": "Isolated semantic no-tool applied trial; packaged SQL_FIRST_API_VERIFY default is unchanged.",
        }
        self.metadata_selector.save(metadata, out_dir)
        filled_prompt = render_system_prompt(self.config, metadata)
        (out_dir / "filled_system_prompt.txt").write_text(filled_prompt, encoding="utf-8")
        checkpoint_logger.add_checkpoint(
            "checkpoint_evidence_pipeline_bypass",
            stage="pre-evidence routing",
            technique="high-confidence direct LLM routing boundary",
            input_summary={"trial_mode": self.config.real_behavior_trial_mode, "strategy": strategy},
            output=boundary_payload,
            effect="bypasses SQL/API, EvidenceBus, answer slots, and post-evidence answer routing for pure concept/meta prompts",
            correctness_role="keeps evidence-free answers separate from grounded SQL/API answer composition",
            efficiency_role="uses no SQL/API calls",
        )
        checkpoint_logger.add_checkpoint(
            "checkpoint_safe_direct_answer_verifier",
            stage="answer verification",
            technique="safe-direct answer verifier",
            input_summary={"pre_evidence_route": boundary_payload["pre_evidence_route"]},
            output=safe_check,
            effect="checks direct concept/meta answers without constructing grounded evidence artifacts",
            correctness_role="blocks invented counts, IDs, timestamps, statuses, or live platform claims",
            efficiency_role="uses no SQL/API calls",
        )
        checkpoint_logger.add_checkpoint(
            "checkpoint_18_final_answer",
            stage="final response",
            technique="semantic no-tool applied trial answer",
            output={"final_answer": final_answer, "answer_length": len(final_answer), "final_token_estimate": estimate_tokens(final_answer)},
            effect="returns a no-tool conceptual answer only after semantic safety gates pass",
            correctness_role="does not invent SQL/API evidence, counts, IDs, statuses, or timestamps",
            efficiency_role="uses zero SQL/API calls for the isolated trial row",
        )
        trajectory = TrajectoryLogger(
            query_id=qid,
            original_query=query,
            strategy=strategy,
            route_type="LLM_SAFE_DIRECT",
            domain_type="CONCEPTUAL",
            max_preview_chars=self.config.max_preview_chars,
        )
        trajectory.add_step("prompt_router", prompt_route.to_dict())
        trajectory.add_step("metadata", {"estimated_tokens": estimate_tokens(metadata), "prompt_tokens": estimate_tokens(filled_prompt), "metadata_path": str(out_dir / "metadata.json")})
        trajectory.add_step("real_behavior_applied_trial", trial_decision)
        trajectory.add_step("evidence_boundary", boundary_payload)
        trajectory.add_step("safe_direct_answer_verifier", safe_check)
        trajectory.set_checkpoints(checkpoint_logger.to_list())
        trajectory_payload = trajectory.save(out_dir / "trajectory.json", final_answer)
        return {
            "query_id": qid,
            "query": query,
            "strategy": strategy,
            "output_dir": str(out_dir),
            "metadata": metadata,
            "plan": {"strategy": strategy, "rationale": "semantic no-tool applied trial", "steps": []},
            "tool_results": [],
            "final_answer": final_answer,
            "checkpoints": checkpoint_logger.to_list(),
            "trajectory": trajectory_payload,
        }

    def _semantic_safe_api_probe_applied_decision(self, ladder: Any | None) -> dict[str, Any]:
        if not (self.config.enable_safe_api_probe and self.config.enable_robust_generalized_candidate):
            return {"record": False, "applied": False}
        payload = ladder.to_dict() if hasattr(ladder, "to_dict") else {}
        if payload.get("action") != "SAFE_API_PROBE":
            return {"record": False, "applied": False}
        probe = payload.get("safe_api_probe") if isinstance(payload.get("safe_api_probe"), dict) else {}
        endpoint_id = str(probe.get("endpoint_id") or "")
        endpoint = self.endpoint_catalog.by_id(endpoint_id) if endpoint_id else None
        blockers: list[str] = []
        if endpoint is None:
            blockers.append("UNKNOWN_ENDPOINT")
        elif endpoint.method != "GET":
            blockers.append("UNSAFE_METHOD")
        elif endpoint.path_params:
            blockers.append("UNRESOLVED_PATH_PARAM")
        url = endpoint.path if endpoint is not None else str(probe.get("path") or "")
        validation = self.api_validator.validate("GET", url, {}, {})
        if not validation.ok:
            blockers.extend(validation.errors or ["API_VALIDATION_FAILED"])
        applied = not blockers
        return {
            "record": True,
            "trial_mode": self.config.real_behavior_trial_mode or ROBUST_GENERALIZED_HARNESS_CANDIDATE,
            "decision_family": "SEMANTIC_SAFE_API_PROBE",
            "decision": "SAFE_API_PROBE" if applied else "EVIDENCE_PIPELINE",
            "applied": applied,
            "fallback": not applied,
            "blockers": blockers,
            "endpoint_id": endpoint_id or None,
            "method": "GET",
            "url": url,
            "max_endpoints": 1,
            "shadow_only": False,
        }

    def _return_safe_api_probe_result(
        self,
        *,
        query: str,
        qid: str,
        strategy: str,
        out_dir: Path,
        prompt_route: Any,
        checkpoint_logger: CheckpointLogger,
        probe_decision: dict[str, Any],
    ) -> dict[str, Any]:
        template = self._safe_api_probe_template(query, probe_decision)
        step = PlanStep(
            action="api",
            purpose="Robust generalized candidate SAFE_API_PROBE evidence.",
            method=(template.method if template is not None else "GET"),
            url=(template.path if template is not None else str(probe_decision.get("url") or "")),
            params=dict(template.params) if template is not None else {},
            family=(template.family if template is not None else str(probe_decision.get("endpoint_id") or "")),
            headers=dict(template.headers) if template is not None else {},
        )
        validation = self.api_validator.validate(step.method or "GET", step.url or "", step.params, step.headers)
        if validation.ok:
            payload = self.api_client.call_api(step.method or "GET", step.url or "", step.params, step.headers)
        else:
            payload = {"ok": False, "dry_run": False, "error": "; ".join(validation.errors)}
        tool_results = [{"type": "api", "step": step.to_dict(), "validation": validation.to_dict(), "payload": payload}]
        evidence_bus = EvidenceBus()
        evidence_bus.observe_api(step, payload)
        evidence_quality = classify_evidence_quality(tool_results, api_required=True)
        slots = extract_answer_slots(query, tool_results)
        grounded = build_evidence_grounded_answer(query, tool_results, slots=slots, evidence_quality=evidence_quality, api_required=True)
        legacy_answer_result = synthesize_answer_with_diagnostics(query, tool_results)
        hybrid_result = None
        selection = None
        broad_question_decision = None
        if self.config.enable_hybrid_answer_composer:
            if self.config.enable_broad_question_classifier:
                broad_question_decision = classify_broad_question(
                    query,
                    slots=slots,
                    evidence_bus=evidence_bus,
                    evidence_quality=evidence_quality,
                )
            hybrid_result = compose_hybrid_answer(
                query,
                slots=slots,
                evidence_bus=evidence_bus,
                evidence_quality=evidence_quality,
                answer_card=grounded,
                legacy_answer=legacy_answer_result.answer,
            )
            final_answer = hybrid_result.final_answer
        else:
            selection = select_answer_candidate(
                prompt=query,
                slots=slots,
                evidence_bus=evidence_bus,
                llm_answer=None,
                llm_verification=None,
                legacy_answer=legacy_answer_result.answer,
                grounded_answer=grounded.answer,
            )
            final_answer = selection.selected_answer
        metadata = {
            "query_id": qid,
            "query": query,
            "strategy": strategy,
            "prompt_route": prompt_route.to_dict(),
            "safe_api_probe": probe_decision,
            "note": "Research generalized candidate SAFE_API_PROBE; packaged SQL_FIRST_API_VERIFY default is unchanged.",
        }
        self.metadata_selector.save(metadata, out_dir)
        filled_prompt = render_system_prompt(self.config, metadata)
        (out_dir / "filled_system_prompt.txt").write_text(filled_prompt, encoding="utf-8")
        checkpoint_logger.add_checkpoint(
            "checkpoint_12_validation",
            stage="validation",
            technique="SAFE_API_PROBE API validation",
            input_summary={"api_step": step.to_dict()},
            output={"api_validation_status": [validation.to_dict()]},
            effect="validates the single safe API probe before execution",
            correctness_role="blocks unknown, mutating, or unresolved endpoint probes",
            efficiency_role="caps validation to one API step",
        )
        checkpoint_logger.add_checkpoint(
            "checkpoint_13_tool_execution",
            stage="execution",
            technique="SAFE_API_PROBE tool execution",
            input_summary={"validated": validation.ok},
            output=tool_results_execution_summary(tool_results),
            effect="executes at most one safe GET endpoint for low-confidence API-family prompts",
            correctness_role="uses real API client output, dry-run output, or validation error only",
            efficiency_role="avoids SQL and extra API calls for this candidate path",
        )
        checkpoint_logger.add_checkpoint(
            "checkpoint_14_evidence_bus",
            stage="evidence forwarding",
            technique="EvidenceBus",
            input_summary={"tool_result_count": len(tool_results)},
            output={"evidence": evidence_bus.compact(), "forwarding_actions": []},
            effect="extracts exact API evidence into answer slots",
            correctness_role="keeps IDs, names, statuses, counts, and timestamps evidence-grounded",
            efficiency_role="reuses compact evidence for answer rendering",
        )
        checkpoint_logger.add_checkpoint(
            "checkpoint_evidence_quality_classifier",
            stage="answer synthesis",
            technique="SQL/API evidence quality classification",
            input_summary={"tool_result_count": len(tool_results), "api_required": True},
            output=evidence_quality,
            effect="classifies live empty, API error, and direct API evidence distinctly",
            correctness_role="prevents live_empty and api_error from being treated as global no-data",
            efficiency_role="uses existing tool result payloads only",
        )
        checkpoint_logger.add_checkpoint(
            "checkpoint_answer_slot_renderer",
            stage="answer synthesis",
            technique="deterministic answer-slot rendering",
            input_summary={"slots": slots.compact()},
            output=grounded.renderer,
            effect="renders requested fields from structured answer slots",
            correctness_role="avoids unsupported concrete claims by using only extracted evidence",
            efficiency_role="uses no additional tools or LLM calls",
        )
        checkpoint_logger.add_checkpoint(
            "checkpoint_evidence_grounded_answer_builder",
            stage="answer synthesis",
            technique="EvidenceBus-centered grounded answer builder",
            input_summary={"evidence_quality": evidence_quality},
            output=grounded.to_dict(),
            effect="builds the final answer from evidence quality and answer slots",
            correctness_role="uses scoped caveats for live_empty/API errors and does not invent missing roles",
            efficiency_role="replaces free-form answer synthesis only in the explicit candidate strategy",
        )
        if hybrid_result is not None:
            if broad_question_decision is not None:
                checkpoint_logger.add_checkpoint(
                    "checkpoint_broad_question_classifier",
                    stage="answer selection",
                    technique="broad-question-aware answer routing",
                    input_summary={"slot_counts": slots.compact()},
                    output=broad_question_decision.to_dict(),
                    effect="distinguishes broad concept, broad data, mixed broad, and structured prompts before SAFE_API_PROBE answer mode selection",
                    correctness_role="keeps API probe answers evidence-grounded and avoids treating API errors as no-data",
                    efficiency_role="uses the single collected API result without extra SQL/API calls",
                )
            checkpoint_logger.add_checkpoint(
                "checkpoint_answer_intent_router",
                stage="answer selection",
                technique="intent-aware answer router",
                input_summary={"slot_counts": slots.compact()},
                output=hybrid_result.intent.to_dict(),
                effect="selects canonical data, LLM concept, mixed, caveat, or legacy answer mode from runtime evidence",
                correctness_role="uses runtime prompt and evidence fields only",
                efficiency_role="avoids unnecessary free-form LLM generation for structured data answers",
            )
            checkpoint_logger.add_checkpoint(
                "checkpoint_hybrid_answer_composer",
                stage="answer selection",
                technique="intent-aware hybrid answer composition",
                input_summary={"answer_intent": hybrid_result.intent.answer_intent, "answer_mode": hybrid_result.intent.answer_mode},
                output=hybrid_result.to_dict(),
                effect="uses canonical data rendering for structured answers and bounded LLM wording for concept sections",
                correctness_role="preserves exact evidence facts and falls back to legacy rendering when verification fails",
                efficiency_role="avoids all-row free-form LLM answer generation for structured data prompts",
            )
            checkpoint_logger.add_checkpoint(
                "checkpoint_final_answer_verifier",
                stage="answer verification",
                technique="evidence-grounded final answer verifier",
                input_summary={"selected_source": hybrid_result.selected_source},
                output=hybrid_result.verification.to_dict(),
                effect="accepts free wording only when hard factual claims are bounded by EvidenceBus and AnswerSlots",
                correctness_role="blocks invented counts, IDs, statuses, timestamps, relationships, and unsafe no-data claims",
                efficiency_role="runs on compact allowed facts and extracted claims without extra SQL/API calls",
            )
        elif selection is not None:
            checkpoint_logger.add_checkpoint(
                "checkpoint_answer_candidate_selector",
                stage="answer selection",
                technique="runtime evidence coverage answer selection",
                input_summary={"candidate_count": len(selection.candidates), "unsupported_claims": selection.unsupported_claims},
                output=selection.to_dict(),
                effect="uses the same legacy-safe evidence wording available to the full evidence pipeline",
                correctness_role="selects only verifier-safe answers using AnswerSlots/API evidence coverage, not gold labels",
                efficiency_role="uses local scoring without extra SQL/API calls",
            )
        checkpoint_logger.add_checkpoint(
            "checkpoint_18_final_answer",
            stage="final response",
            technique="candidate grounded final response",
            output={"final_answer": final_answer, "answer_length": len(final_answer), "final_token_estimate": estimate_tokens(final_answer)},
            effect="returns the final candidate answer",
            correctness_role="final answer remains tied to API probe evidence and caveats",
            efficiency_role="keeps response concise",
        )
        trajectory = TrajectoryLogger(
            query_id=qid,
            original_query=query,
            strategy=strategy,
            route_type="SAFE_API_PROBE",
            domain_type="API",
            max_preview_chars=self.config.max_preview_chars,
        )
        trajectory.add_step("prompt_router", prompt_route.to_dict())
        trajectory.add_step("metadata", {"estimated_tokens": estimate_tokens(metadata), "prompt_tokens": estimate_tokens(filled_prompt), "metadata_path": str(out_dir / "metadata.json")})
        trajectory.add_api_call(step.method or "GET", step.url or "", step.params, step.headers, validation, payload)
        trajectory.add_step(
            "answer_diagnostics",
            {
                **grounded.to_dict(),
                "legacy_answer": legacy_answer_result.answer,
                "answer_candidate_selector": selection.to_dict() if selection is not None else None,
                "hybrid_answer_composer": hybrid_result.to_dict() if hybrid_result is not None else None,
                "selected_candidate_type": (
                    hybrid_result.selected_source if hybrid_result is not None else selection.selected_source if selection is not None else "UNKNOWN"
                ),
            },
        )
        trajectory.set_checkpoints(checkpoint_logger.to_list())
        trajectory_payload = trajectory.save(out_dir / "trajectory.json", final_answer)
        return {
            "query_id": qid,
            "query": query,
            "strategy": strategy,
            "output_dir": str(out_dir),
            "metadata": metadata,
            "plan": {"strategy": strategy, "rationale": "robust generalized SAFE_API_PROBE", "steps": [step.to_dict()]},
            "tool_results": tool_results,
            "final_answer": final_answer,
            "checkpoints": checkpoint_logger.to_list(),
            "trajectory": trajectory_payload,
        }

    def _safe_api_probe_template(self, query: str, probe_decision: dict[str, Any]) -> Any | None:
        endpoint_id = str(probe_decision.get("endpoint_id") or "")
        url = str(probe_decision.get("url") or "")
        normalized_url = _normalize_probe_path(url)
        family_aliases = {
            "unified_tags": {"tag_count", "tag_list", "tags_by_uncategorized_category", "tag_categories"},
            "merge_policies": {"merge_policies"},
            "segment_jobs": {"segment_jobs"},
            "schema_registry_schemas": {"schema_count", "schema_list"},
        }
        for template in find_api_templates(query, self.config):
            if str(template.method).upper() != "GET":
                continue
            if _normalize_probe_path(template.path) == normalized_url:
                return template
            if template.family == endpoint_id or template.family in family_aliases.get(endpoint_id, set()):
                return template
        return None

    def _add_staged_evidence_policy_checkpoints(self, query: str, analysis: Any, plan: Plan, checkpoint_logger: CheckpointLogger) -> None:
        if not self.config.enable_staged_evidence_policy:
            return
        try:
            features = extract_objective_prompt_features(query)
            sql_available = any(step.action == "sql" and bool(step.sql) for step in plan.steps)
            api_available = any(step.action == "api" and bool(step.url) for step in plan.steps)
            scores = score_evidence_match(
                features,
                relevance_result=getattr(analysis, "relevance", None),
                sql_candidate_available=sql_available,
                api_candidate_available=api_available,
            )
            branch = decide_initial_evidence_branch(scores, analysis)
            checkpoint_logger.add_checkpoint(
                "checkpoint_evidence_match_scores",
                stage="staged evidence policy shadow",
                technique="objective SQL/API evidence match scorer",
                input_summary={"route_type": getattr(analysis, "route_type", None), "answer_family": getattr(analysis, "answer_family", None)},
                output=scores.to_dict(),
                effect="estimates whether SQL, API, both, or neither are plausible evidence sources",
                correctness_role="does not choose final answer or bypass SQL/API validators",
                efficiency_role="identifies potential staged acquisition savings without changing the plan",
            )
            checkpoint_logger.add_checkpoint(
                "checkpoint_initial_evidence_branch_policy",
                stage="staged evidence policy shadow",
                technique="SQL-first/API-first staged branch policy",
                input_summary={"score": scores.to_dict()},
                output={**branch.to_dict(), "shadow_only": self.config.staged_evidence_policy_shadow_only},
                effect="records the first evidence branch a future trial would acquire",
                correctness_role="keeps current SQL_FIRST_API_VERIFY execution unchanged in shadow mode",
                efficiency_role="measures where upfront SQL+API planning may be avoidable",
            )
            checkpoint_logger.add_checkpoint(
                "checkpoint_staged_evidence_acquisition",
                stage="evidence pipeline",
                technique="progressive staged evidence acquisition",
                input_summary={"planned_sql": sql_available, "planned_api": api_available},
                output={
                    "generalized_planner_executed": bool(self.config.enable_research_generalized_planner),
                    "scores": scores.to_dict(),
                    "initial_branch": branch.to_dict(),
                    "planned_sql_calls": sum(1 for step in plan.steps if step.action == "sql"),
                    "planned_api_calls": sum(1 for step in plan.steps if step.action == "api"),
                    "shadow_only": self.config.staged_evidence_policy_shadow_only,
                },
                effect="records the actual evidence pipeline entry and planned staged sources for research V2",
                correctness_role="keeps ambiguous/data-like prompts in evidence collection rather than early no-tool routing",
                efficiency_role="records first-source policy without executing extra candidate plans",
            )
        except Exception as exc:
            checkpoint_logger.add_error_checkpoint(
                "checkpoint_initial_evidence_branch_policy",
                stage="staged evidence policy shadow",
                technique="staged evidence policy failure capture",
                input_summary={"query": query},
                error=f"{type(exc).__name__}: {exc}",
                warnings=["staged evidence policy shadow checkpoint failed; packaged runtime path continued"],
            )

    def _add_post_sql_api_decision_checkpoints(
        self,
        query: str,
        analysis: Any,
        tool_results: list[dict[str, Any]],
        api_step: PlanStep,
        checkpoint_logger: CheckpointLogger,
    ) -> dict[str, Any] | None:
        if not (self.config.enable_post_sql_api_decision or self.config.enable_staged_evidence_policy):
            return None
        try:
            sql_result = _latest_sql_payload(tool_results)
            features = extract_objective_prompt_features(query)
            answer_intent = str(getattr(analysis, "answer_family", "") or "UNKNOWN").upper()
            card = build_post_sql_decision_card(features, answer_intent, sql_result, [api_step], self.endpoint_catalog)
            policy = decide_post_sql_api_policy(card)
            api_need_decision = getattr(analysis, "api_need_decision", None)
            api_required = (
                str(
                    getattr(api_need_decision, "mode", None)
                    or getattr(api_need_decision, "need", "")
                    or ""
                ).upper()
                == "API_REQUIRED"
            )
            if _local_snapshot_sql_complete_api_optional(query, features, card):
                api_required = False
            advisor = advise_post_sql_api(
                card,
                policy,
                enabled=self.config.post_sql_llm_advisor_enabled,
            )
            verified = verify_post_sql_api_advice(advisor, card, self.endpoint_catalog, api_required=api_required)
            semantic_decision: dict[str, Any] | None = None
            semantic_card: dict[str, Any] | None = None
            if self.config.enable_post_sql_llm_semantic_decision:
                semantic_parse = parse_prompt_semantics(query, features, use_llm=False)
                semantic_card = build_post_sql_semantic_decision_card(
                    user_prompt=query,
                    semantic_parse=semantic_parse,
                    features=features,
                    answer_intent=answer_intent,
                    sql_result=sql_result,
                    api_steps=[api_step],
                    endpoint_catalog=self.endpoint_catalog,
                    api_need_prior="API_REQUIRED" if api_required else "API_OPTIONAL",
                )
                semantic_decision = run_post_sql_llm_first_decision(
                    semantic_card,
                    enabled=self.config.enable_post_sql_llm_semantic_decision,
                )
                semantic_verified = semantic_decision.get("execution_verifier") if isinstance(semantic_decision.get("execution_verifier"), dict) else None
                if semantic_verified:
                    verified = type(verified)(
                        final_action=str(semantic_verified.get("final_action") or verified.final_action),
                        source=str(semantic_verified.get("source") or verified.source),
                        selected_api_families=list(semantic_verified.get("selected_api_families") or []),
                        blocked_families=list(semantic_verified.get("blocked_families") or []),
                        codes=list(semantic_verified.get("codes") or []),
                    )
            checkpoint_logger.add_checkpoint(
                "checkpoint_post_sql_decision_card",
                stage="post-SQL API decision shadow",
                technique="compact post-SQL decision card",
                input_summary={"api_step": api_step.to_dict(), "sql_result_seen": sql_result is not None},
                output=card,
                effect="summarizes SQL result quality and safe API candidates before API execution",
                correctness_role="uses role/bucket summaries rather than raw large result payloads",
                efficiency_role="provides compact input for deterministic or LLM API advice",
            )
            checkpoint_logger.add_checkpoint(
                "checkpoint_post_sql_deterministic_policy",
                stage="post-SQL API decision shadow",
                technique="confidence-banded deterministic post-SQL policy",
                input_summary={"card_task": card.get("task")},
                output=policy.to_dict(),
                effect="bypasses LLM advice for high-confidence call/skip decisions",
                correctness_role="does not execute or suppress API calls in shadow mode",
                efficiency_role="estimates where ambiguous-only LLM advice would save calls",
            )
            checkpoint_logger.add_checkpoint(
                "checkpoint_post_sql_llm_advisor",
                stage="post-SQL API decision shadow",
                technique="medium/low-confidence LLM API advisor",
                input_summary={"advisor_enabled": self.config.post_sql_llm_advisor_enabled, "policy_confidence": policy.confidence},
                output=advisor.to_dict(),
                effect="records advisory CALL_API/SKIP_API/CAVEAT_ONLY choice when enabled or deterministic fallback otherwise",
                correctness_role="never creates endpoints, params, user answers, or bypasses validators",
                efficiency_role="invokes LLM only for medium/low/ambiguous policy bands",
            )
            checkpoint_logger.add_checkpoint(
                "checkpoint_post_sql_api_call_verifier",
                stage="post-SQL API decision shadow",
                technique="thin verifier for post-SQL API advice",
                input_summary={"advisor_source": advisor.source},
                output={**verified.to_dict(), "shadow_only": self.config.post_sql_api_decision_shadow_only},
                effect="verifies endpoint legality and records what would be kept, dropped, or caveated",
                correctness_role="blocks unknown endpoints, unresolved path params, and API-required skips",
                efficiency_role="estimates API call savings/additions without changing execution",
            )
            if semantic_card is not None and semantic_decision is not None:
                checkpoint_logger.add_checkpoint(
                    "checkpoint_post_sql_semantic_decision_card",
                    stage="post-SQL API semantic decision",
                    technique="compact LLM-first post-SQL semantic decision card",
                    input_summary={"api_step": api_step.to_dict(), "sql_result_seen": sql_result is not None},
                    output=semantic_card,
                    effect="provides compact SQL state, scope, API candidate, and constraints to the LLM decision",
                    correctness_role="omits raw large SQL/API payloads and evaluator metadata",
                    efficiency_role="bounds the LLM decision payload",
                )
                checkpoint_logger.add_checkpoint(
                    "checkpoint_post_sql_llm_decision_v1",
                    stage="post-SQL API semantic decision",
                    technique="LLM-first post-SQL API decision",
                    input_summary={"llm_backend_available": semantic_decision.get("llm_backend_available")},
                    output=semantic_decision.get("first_decision") or {},
                    effect="records the initial LLM CALL_API/SKIP_API/CAVEAT_ONLY decision",
                    correctness_role="LLM decides semantics; gates only detect conflicts",
                    efficiency_role="can suppress optional API only after verifier acceptance",
                )
                checkpoint_logger.add_checkpoint(
                    "checkpoint_post_sql_minimal_correction_feedback",
                    stage="post-SQL API semantic decision",
                    technique="minimal compiler-style correction feedback",
                    input_summary={"first_pass_ok": semantic_decision.get("first_pass_ok")},
                    output=semantic_decision.get("feedback") or {},
                    effect="sends only conflict deltas and narrowed output choices for one revision",
                    correctness_role="does not replace the LLM semantic decision with deterministic policy",
                    efficiency_role="keeps revision payload compact",
                )
                checkpoint_logger.add_checkpoint(
                    "checkpoint_post_sql_llm_decision_v2",
                    stage="post-SQL API semantic decision",
                    technique="single LLM post-SQL revision",
                    input_summary={"revision_attempted": semantic_decision.get("revision_attempted")},
                    output=semantic_decision.get("second_decision") or {},
                    effect="records the one allowed LLM correction after gate feedback",
                    correctness_role="lets LLM revise before fallback",
                    efficiency_role="bounds post-SQL LLM calls to at most two",
                )
                checkpoint_logger.add_checkpoint(
                    "checkpoint_post_sql_risk_minimizing_fallback",
                    stage="post-SQL API semantic decision",
                    technique="risk-minimizing fallback after failed LLM revision",
                    input_summary={"revision_success": semantic_decision.get("revision_success")},
                    output=semantic_decision.get("fallback") or {},
                    effect="preserves evidence or caveats unsafe API only when LLM revision fails",
                    correctness_role="does not claim deterministic semantic certainty",
                    efficiency_role="uses local risk rules only after LLM failure",
                )
                checkpoint_logger.add_checkpoint(
                    "checkpoint_post_sql_execution_verifier",
                    stage="post-SQL API semantic decision",
                    technique="thin execution contract verifier",
                    input_summary={"decision_source": (semantic_decision.get("execution_verifier") or {}).get("source")},
                    output=semantic_decision.get("execution_verifier") or {},
                    effect="checks endpoint existence, safe GET, path params, role gain, and budget before execution",
                    correctness_role="blocks unsafe or unexecutable API calls without re-scoring semantic intent",
                    efficiency_role="prevents invalid API execution",
                )
            return {
                "card": card,
                "semantic_card": semantic_card or {},
                "policy": policy.to_dict(),
                "advisor": advisor.to_dict(),
                "verified": verified.to_dict(),
                "semantic_decision": semantic_decision or {},
                "api_required": api_required,
                "api_step": api_step.to_dict(),
            }
        except Exception as exc:
            checkpoint_logger.add_error_checkpoint(
                "checkpoint_post_sql_api_call_verifier",
                stage="post-SQL API decision shadow",
                technique="post-SQL decision failure capture",
                input_summary={"query": query, "api_step": api_step.to_dict()},
                error=f"{type(exc).__name__}: {exc}",
                warnings=["post-SQL API decision shadow checkpoint failed; packaged runtime path continued"],
            )
            return {"error": f"{type(exc).__name__}: {exc}", "api_step": api_step.to_dict()}

    def _post_sql_api_applied_decision(self, post_sql_decision: dict[str, Any] | None) -> dict[str, Any]:
        enabled = bool(
            self.config.enable_staged_evidence_applied_trial
            or self.config.enable_post_sql_deterministic_applied_trial
            or self.config.enable_post_sql_llm_advisor_applied_trial
            or self.config.enable_combined_safe_applied_trial
        )
        if not enabled:
            return {"record": False, "applied": False}
        if not post_sql_decision or post_sql_decision.get("error"):
            return {
                "record": True,
                "trial_mode": self.config.real_behavior_trial_mode,
                "decision_family": "POST_SQL_API",
                "decision": "FALLBACK",
                "applied": False,
                "fallback": True,
                "blockers": [post_sql_decision.get("error") if post_sql_decision else "NO_POST_SQL_DECISION"],
                "shadow_only": False,
            }
        policy = post_sql_decision.get("policy") if isinstance(post_sql_decision.get("policy"), dict) else {}
        advisor = post_sql_decision.get("advisor") if isinstance(post_sql_decision.get("advisor"), dict) else {}
        verified = post_sql_decision.get("verified") if isinstance(post_sql_decision.get("verified"), dict) else {}
        card = post_sql_decision.get("card") if isinstance(post_sql_decision.get("card"), dict) else {}
        sql_state = card.get("sql_state") if isinstance(card.get("sql_state"), dict) else {}
        api_required = bool(post_sql_decision.get("api_required"))
        advisor_source = str(advisor.get("source") or verified.get("source") or "")
        actual_llm_advice = advisor_source in {"LLM_ADVISOR", "LLM_ADVISOR_VERIFIED", "LLM_ADVISOR_BLOCKED"}
        llm_skip = (
            self.config.enable_post_sql_llm_advisor_applied_trial
            and actual_llm_advice
            and verified.get("source") == "LLM_ADVISOR_VERIFIED"
            and verified.get("final_action") == "SKIP_API"
            and not api_required
        )
        high_conf_skip = (
            policy.get("suggestion") == "SKIP_API"
            and policy.get("confidence") == "HIGH"
            and verified.get("final_action") == "SKIP_API"
            and not api_required
            and bool(sql_state.get("direct_answer"))
        )
        applied_skip = bool(high_conf_skip or llm_skip)
        blockers: list[str] = []
        if api_required:
            blockers.append("API_REQUIRED")
        if policy.get("confidence") != "HIGH" and not self.config.enable_post_sql_llm_advisor_applied_trial:
            blockers.append("NOT_HIGH_CONFIDENCE")
        if policy.get("suggestion") != "SKIP_API":
            blockers.append("POLICY_DID_NOT_SUGGEST_SKIP")
        if verified.get("final_action") != "SKIP_API":
            blockers.append("VERIFIER_DID_NOT_APPROVE_SKIP")
        if not sql_state.get("direct_answer") and not llm_skip:
            blockers.append("SQL_NOT_DIRECT_ANSWER")
        if self.config.enable_post_sql_llm_advisor_applied_trial and not actual_llm_advice:
            blockers.append("NO_ACTUAL_LLM_ADVICE")
        if self.config.enable_post_sql_llm_advisor_applied_trial and actual_llm_advice and verified.get("source") == "LLM_ADVISOR_BLOCKED":
            blockers.append("LLM_ADVICE_BLOCKED")
        return {
            "record": True,
            "trial_mode": self.config.real_behavior_trial_mode or "post_sql_deterministic_applied_real_trial",
            "decision_family": "POST_SQL_API",
            "decision": "SKIP_API" if applied_skip else "KEEP_BASELINE_API",
            "applied": applied_skip,
            "fallback": not applied_skip,
            "blockers": [] if applied_skip else blockers,
            "policy": policy,
            "advisor": advisor,
            "verified": verified,
            "api_required": api_required,
            "sql_direct_answer": bool(sql_state.get("direct_answer")),
            "actual_llm_advice": actual_llm_advice,
            "shadow_only": False,
        }

    def _create_llm_sql_plan(
        self,
        query: str,
        routing: Any,
        metadata: dict[str, Any],
        strategy: str,
        analysis: Any,
        checkpoint_logger: CheckpointLogger,
    ) -> Plan:
        fallback = self.planner.create_plan(query, routing, metadata, "SQL_FIRST_API_VERIFY", analysis=analysis)

        prefer_full_schema = strategy == "FULL_SCHEMA_LLM_SQL"
        candidate_context = None
        context_mode = "full_schema" if prefer_full_schema else "candidate"
        if not prefer_full_schema:
            candidate_context = build_adaptive_context(query, self.schema_index, self.endpoint_catalog)
            context_mode = candidate_context.get("context_mode", "candidate")
            prefer_full_schema = context_mode == "full_schema"
        schema_context = (
            build_full_schema_context(self.schema_index, self.endpoint_catalog)
            if prefer_full_schema
            else candidate_context
        )
        mode = "full_schema" if prefer_full_schema else "candidate_guided"
        if self.config.enable_query_family_examples:
            examples = examples_for_family(analysis.answer_family)
            checkpoint_logger.add_checkpoint(
                "checkpoint_query_family_examples",
                stage="llm sql prompting",
                technique="DAIL-SQL-style query-family examples",
                input_summary={"answer_family": analysis.answer_family},
                output={
                    "query_family": analysis.answer_family,
                    "example_count": len(examples),
                    "token_cost": estimate_tokens(examples),
                    "overlap_audit_result": few_shot_public_overlap_check(),
                },
                effect="adds short generic family hints to LLM SQL prompting only",
                correctness_role="helps LLM SQL follow family-specific schema patterns without public-answer examples",
                efficiency_role="disabled by default to avoid prompt-token overhead",
            )
            if isinstance(schema_context, dict):
                schema_context = {**schema_context, "query_family_examples": examples}
        generation = generate_sql_with_llm(query, schema_context or {}, mode=mode)
        checkpoint_logger.add_checkpoint(
            "checkpoint_llm_sql_generation",
            stage="llm nl-to-sql",
            technique=f"{mode} LLM SQL generation",
            input_summary={
                "strategy": strategy,
                "candidate_confidence": candidate_context.get("confidence") if candidate_context else None,
                "candidate_score_margin": candidate_context.get("score_margin") if candidate_context else None,
                "context_mode": context_mode,
            },
            output={
                "ok": generation.get("ok"),
                "skipped": generation.get("skipped"),
                "provider": generation.get("provider"),
                "model": generation.get("model"),
                "mode": generation.get("mode"),
                "context_mode": context_mode,
                "sql": generation.get("sql"),
                "error": generation.get("error"),
            },
            effect="uses a real LLM for NL-to-SQL when credentials are available",
            correctness_role="generates SQL from retrieved schema context and records fallback when unavailable",
            efficiency_role="uses candidate context first when confidence is sufficient",
        )
        sql = str(generation.get("sql") or "")
        validation = self.sql_validator.validate(sql) if sql else ValidationResult(False, errors=["No SQL generated."])
        checkpoint_logger.add_checkpoint(
            "checkpoint_llm_sql_validation",
            stage="llm sql validation",
            technique="SQL safety and schema validation for LLM SQL",
            input_summary={"sql": sql},
            output=validation.to_dict(),
            effect="validates LLM-generated SQL before execution",
            correctness_role="blocks destructive SQL and unknown tables/columns",
            efficiency_role="prevents wasted execution on invalid LLM output",
        )
        validation, compile_result = self._check_llm_sql_compiles(
            sql,
            validation,
            checkpoint_logger,
            "checkpoint_llm_sql_compile_gate",
        )
        if sql and not validation.ok and not generation.get("skipped"):
            repair_errors = list(validation.errors)
            if compile_result and compile_result.error_message and compile_result.error_message not in repair_errors:
                repair_errors.append(compile_result.error_message)
            repair = repair_sql_with_llm(query, sql, repair_errors, schema_context or {})
            checkpoint_logger.add_checkpoint(
                "checkpoint_llm_sql_repair",
                stage="llm sql repair",
                technique="one-shot LLM SQL repair",
                input_summary={"bad_sql": sql, "validation_errors": repair_errors},
                output={
                    "ok": repair.get("ok"),
                    "skipped": repair.get("skipped"),
                    "sql": repair.get("sql"),
                    "error": repair.get("error"),
                },
                effect="attempts one repair using validator feedback",
                correctness_role="repairs schema or safety mistakes without executing invalid SQL",
                efficiency_role="caps repair to one attempt",
            )
            if repair.get("ok") and repair.get("sql"):
                sql = str(repair["sql"])
                validation = self.sql_validator.validate(sql)
                validation, _ = self._check_llm_sql_compiles(
                    sql,
                    validation,
                    checkpoint_logger,
                    "checkpoint_llm_sql_compile_gate_repair",
                )

        if strategy == "CANDIDATE_GUIDED_LLM_SQL" and (not validation.ok or not sql) and not generation.get("skipped"):
            full_context = build_full_schema_context(self.schema_index, self.endpoint_catalog)
            full_generation = generate_sql_with_llm(query, full_context, mode="full_schema")
            checkpoint_logger.add_checkpoint(
                "checkpoint_llm_sql_fallback",
                stage="llm sql fallback",
                technique="candidate-context to full-schema fallback",
                input_summary={"candidate_validation": validation.to_dict()},
                output={
                    "fallback": "full_schema",
                    "ok": full_generation.get("ok"),
                    "skipped": full_generation.get("skipped"),
                    "sql": full_generation.get("sql"),
                    "error": full_generation.get("error"),
                },
                effect="uses full schema when candidate context is insufficient",
                correctness_role="prevents candidate retrieval from becoming a hard constraint",
                efficiency_role="only expands context after candidate failure/uncertainty",
            )
            if full_generation.get("ok") and full_generation.get("sql"):
                sql = str(full_generation["sql"])
                validation = self.sql_validator.validate(sql)
                validation, _ = self._check_llm_sql_compiles(
                    sql,
                    validation,
                    checkpoint_logger,
                    "checkpoint_llm_sql_compile_gate_fallback",
                )

        if not sql or not validation.ok:
            checkpoint_logger.add_checkpoint(
                "checkpoint_llm_sql_fallback",
                stage="llm sql fallback",
                technique="LLM SQL to deterministic backend fallback",
                input_summary={"strategy": strategy, "validation": validation.to_dict()},
                output={"fallback": "SQL_FIRST_API_VERIFY", "reason": generation.get("error") or validation.errors},
                effect="keeps deterministic backend fully functional when LLM SQL is unavailable or invalid",
                correctness_role="preserves validated SQL/API behavior",
                efficiency_role="avoids repeated LLM retries",
            )
            return Plan(strategy, f"LLM SQL unavailable/invalid; fell back to SQL_FIRST_API_VERIFY. {fallback.rationale}", fallback.steps, fallback.optimizer_actions)

        steps = [
            PlanStep(
                action="sql",
                purpose=f"{strategy} validated LLM-generated SQL grounding.",
                sql=sql,
                allow_full_result=True,
                family="llm_sql",
            )
        ]
        if strategy == "LLM_SQL_FIRST_API_VERIFY" and analysis.api_need_decision.mode != API_SKIP:
            steps.extend(
                self.planner._api_steps(
                    query,
                    routing,
                    metadata,
                    templates=analysis.api_templates,
                    allowed_families=analysis.api_need_decision.allowed_api_families,
                )
            )
        return Plan(
            strategy,
            f"{strategy} used validated {mode} LLM SQL with deterministic validation and fallback policy.",
            steps,
            optimizer_actions=[],
        )

    def _check_llm_sql_compiles(
        self,
        sql: str,
        validation: ValidationResult,
        checkpoint_logger: CheckpointLogger,
        checkpoint_name: str,
    ) -> tuple[ValidationResult, SQLCompileGateResult | None]:
        if not sql or not validation.ok:
            return validation, None
        result = self.sql_compile_gate.check(sql)
        checkpoint_logger.add_checkpoint(
            checkpoint_name,
            stage="llm sql compile gate",
            technique="DuckDB EXPLAIN compile check for LLM-generated SQL",
            input_summary={"sql": sql},
            output=result.to_dict(),
            effect="checks whether the LLM SQL compiles against the actual database schema without mutating it",
            correctness_role="returns syntax/database-semantic compile errors to the LLM repair loop or fallback path",
            efficiency_role="prevents execution of SQL that cannot compile",
        )
        if result.passed:
            return validation, result
        errors = list(validation.errors)
        message = result.error_message or "SQL failed database compile gate."
        if message not in errors:
            errors.append(message)
        return ValidationResult(False, errors=errors, warnings=list(validation.warnings)), result


def slugify(text: str, max_length: int = 48) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", text.lower()).strip("_")
    return (slug[:max_length] or "query").strip("_")


def _validation_result_from_payload(payload: Any) -> ValidationResult:
    if isinstance(payload, dict):
        return ValidationResult(
            ok=bool(payload.get("ok")),
            errors=list(payload.get("errors") or []),
            warnings=list(payload.get("warnings") or []),
            repaired=bool(payload.get("repaired", False)),
        )
    return ValidationResult(False, errors=["Missing validation payload."])


def _blocked_sql_tool_result(sql: str, params: list[Any] | None, compile_result: SQLCompileGateResult, *, pass_id: str | None = None, subtask: str | None = None) -> dict[str, Any]:
    validation = ValidationResult(
        False,
        errors=[compile_result.error_message or "SQL failed compile gate."],
        warnings=[],
    )
    step = PlanStep(
        action="sql",
        purpose="Blocked V2 LLM-owned SQL candidate.",
        sql=sql,
        allow_full_result=True,
        family="llm_owned_v2",
    )
    return {
        "type": "sql",
        "pass_id": pass_id,
        "subtask": subtask,
        "step": step.to_dict(),
        "validation": validation.to_dict(),
        "payload": {
            "ok": False,
            "sql": sql,
            "params": list(params) if params is not None else None,
            "rows": [],
            "row_count": 0,
            "limited": False,
            "error": compile_result.error_message,
            "compile_gate": compile_result.to_dict(),
        },
    }


def _blocked_api_tool_result(gate_result: APIRequestGateResult, *, pass_id: str | None = None, subtask: str | None = None) -> dict[str, Any]:
    validation = ValidationResult(
        False,
        errors=[gate_result.error_message or "API request failed gate."],
        warnings=[],
    )
    step = PlanStep(
        action="api",
        purpose="Blocked V2 LLM-owned API request.",
        method=gate_result.method or "GET",
        url=gate_result.path or "",
        params=dict(gate_result.params or {}),
        headers={},
        family="llm_owned_v2",
    )
    return {
        "type": "api",
        "pass_id": pass_id,
        "subtask": subtask,
        "step": step.to_dict(),
        "validation": validation.to_dict(),
        "payload": {
            "ok": False,
            "dry_run": False,
            "error": gate_result.error_message,
            "api_request_gate": gate_result.to_dict(),
        },
    }


def _repaired_pass_for(plan: LLMUnifiedPlan, pass_id: str, *, source: str) -> LLMUnifiedPass | None:
    for item in plan.passes:
        if item.pass_id == pass_id and (
            source == "any"
            or (source == "sql" and item.sql is not None)
            or (source == "api" and item.api_request is not None)
        ):
            return item
    for item in plan.passes:
        if source == "any" or (source == "sql" and item.sql is not None) or (source == "api" and item.api_request is not None):
            return item
    if source == "sql" and plan.sql is not None:
        return LLMUnifiedPass(pass_id=pass_id, subtask="Repaired SQL pass.", path="SQL", can_run_parallel=False, depends_on=[], evidence_order="SQL_FIRST", sql=plan.sql, api_request=None)
    if source == "api" and plan.api_request is not None:
        return LLMUnifiedPass(pass_id=pass_id, subtask="Repaired API pass.", path="API", can_run_parallel=False, depends_on=[], evidence_order="API_FIRST", sql=None, api_request=plan.api_request)
    return None


def _llm_owned_generation_boundary_summary(summary: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "run_id",
        "result_bundle_id",
        "evidence_bus_id",
        "plan_version",
        "multi_pass_enabled",
        "llm_pass_graph_used",
        "v2_execution_optimizer_used",
        "critical_path",
        "stage_pipeline_used",
        "cache_hits",
        "deduped_passes",
        "early_stopped_passes",
        "budget_limits",
        "budget_exceeded",
        "budget_error",
        "checkpoint_resume_used",
        "model_cascade_used",
        "v2_pipeline_scheduler_used",
        "pipeline_stage_count",
        "max_parallelism",
        "max_sql_workers",
        "max_api_workers",
        "llm_pass_count",
        "parallel_pass_count",
        "sequential_pass_count",
        "pass_ids",
        "parallel_groups",
        "dependency_edges",
        "pass_graph_gate_passed",
        "pass_graph_repair_attempted",
        "pass_graph_repair_success",
        "pass_graph_gate_error_type",
        "repaired_pass_count",
        "passes_executed",
        "stage_events",
        "passes_completed",
        "passes_failed",
        "passes_dependency_blocked",
        "pass_results_count",
        "sql_gate_passed",
        "api_gate_passed",
        "sql_repair_attempts",
        "api_repair_attempts",
        "dependency_resolution_errors",
        "dependency_repair_attempts",
        "backend_semantic_decomposition_used",
        "backend_semantic_planning_used",
        "deterministic_answer_template_used",
        "hidden_eval_gold_used",
    ]
    return {key: summary.get(key) for key in keys}


def _result_bundle_checkpoint_payload(result_bundle: ResultBundle) -> dict[str, Any]:
    return {
        "run_id": result_bundle.run_id,
        "pass_results_count": result_bundle.pass_results_count,
        "append_events": result_bundle.append_events,
        "runtime_passes": [
            {
                "run_id": item.get("run_id"),
                "pass_id": item.get("pass_id"),
                "global_pass_id": item.get("global_pass_id"),
                "attempt_id": item.get("attempt_id"),
                "plan_version": item.get("plan_version"),
                "path": item.get("path"),
                "status": item.get("status"),
                "cached_sources": item.get("cached_sources"),
                "depends_on": item.get("depends_on"),
                "started_at": item.get("started_at"),
                "completed_at": item.get("completed_at"),
                "stage_history": item.get("stage_history"),
                "dependency_resolution": item.get("dependency_resolution"),
                "facts": item.get("facts"),
                "source_result_count": len(item.get("source_results") or []),
            }
            for item in result_bundle.runtime_passes
        ],
    }


def _primary_pass_source(pass_spec: LLMUnifiedPass) -> str:
    if pass_spec.path == "SQL" or pass_spec.sql is not None:
        return "sql"
    if pass_spec.path == "API" or pass_spec.api_request is not None:
        return "api"
    return "any"


def _runtime_pass_from_pass_spec(
    pass_spec: LLMUnifiedPass,
    tool_results: list[dict[str, Any]],
    *,
    dependency_resolution: dict[str, Any] | None = None,
    stage_history: list[dict[str, Any]] | None = None,
    run_context: RunContext | None = None,
) -> dict[str, Any]:
    source_results = [_source_result_from_tool_result(item) for item in tool_results]
    caveats = [str(item.get("error")) for item in source_results if item.get("error")]
    status = _pass_status_from_source_results(source_results)
    started_at = stage_history[0]["timestamp"] if stage_history else None
    completed_at = stage_history[-1]["timestamp"] if stage_history else None
    cached_sources = [str(item.get("type") or "") for item in tool_results if item.get("cached")]
    run_id = run_context.run_id if run_context else None
    return {
        "run_id": run_id,
        "pass_id": pass_spec.pass_id,
        "global_pass_id": f"{run_id}:{pass_spec.pass_id}" if run_id else None,
        "attempt_id": 0,
        "plan_version": run_context.plan_version if run_context else 1,
        "subtask": pass_spec.subtask,
        "path": pass_spec.path,
        "status": status,
        "cached_sources": cached_sources,
        "can_run_parallel": pass_spec.can_run_parallel,
        "depends_on": pass_spec.depends_on,
        "expected_result": pass_spec.expected_result,
        "started_at": started_at,
        "completed_at": completed_at,
        "stage_history": list(stage_history or []),
        "dependency_resolution": dependency_resolution or {"required": False, "resolved": True, "errors": []},
        "source_results": source_results,
        "facts": _facts_from_source_results(source_results),
        "caveats": caveats,
    }


def _pass_graph_error_runtime_pass(graph_gate: PassGraphGateResult, *, run_context: RunContext | None = None) -> dict[str, Any]:
    run_id = run_context.run_id if run_context else None
    return {
        "run_id": run_id,
        "pass_id": "pass_graph_gate",
        "global_pass_id": f"{run_id}:pass_graph_gate" if run_id else None,
        "attempt_id": 0,
        "plan_version": run_context.plan_version if run_context else 1,
        "subtask": "Validate LLM-owned pass graph.",
        "path": "AGGREGATION_ONLY",
        "status": "ERROR",
        "can_run_parallel": False,
        "depends_on": [],
        "expected_result": "Valid pass graph.",
        "started_at": None,
        "completed_at": None,
        "stage_history": [],
        "dependency_resolution": {"required": False, "resolved": True, "errors": []},
        "source_results": [
            {
                "source": "PASS_GRAPH_GATE",
                "status": "ERROR",
                "scope": "RUNTIME",
                "result": graph_gate.to_dict(),
                "error": graph_gate.error_message,
                "gate_passed": False,
                "repair_attempts": 0,
            }
        ],
        "facts": [],
        "caveats": [str(graph_gate.error_message or "Pass graph gate failed.")],
    }


def _budget_error_runtime_pass(optimization_plan: Any, *, run_context: RunContext | None = None) -> dict[str, Any]:
    run_id = run_context.run_id if run_context else None
    return {
        "run_id": run_id,
        "pass_id": "execution_budget",
        "global_pass_id": f"{run_id}:execution_budget" if run_id else None,
        "attempt_id": 0,
        "plan_version": run_context.plan_version if run_context else 1,
        "subtask": "Enforce V2 execution budget.",
        "path": "AGGREGATION_ONLY",
        "status": "BUDGET_EXCEEDED",
        "can_run_parallel": False,
        "depends_on": [],
        "expected_result": "Budget-safe execution plan.",
        "started_at": None,
        "completed_at": None,
        "stage_history": [],
        "dependency_resolution": {"required": False, "resolved": True, "errors": []},
        "source_results": [
            {
                "source": "EXECUTION_OPTIMIZER",
                "status": "BUDGET_EXCEEDED",
                "scope": "RUNTIME",
                "result": optimization_plan.to_dict() if hasattr(optimization_plan, "to_dict") else optimization_plan,
                "error": getattr(optimization_plan, "budget_error", None) or "Execution budget exceeded.",
                "gate_passed": False,
                "repair_attempts": 0,
            }
        ],
        "facts": [],
        "caveats": [getattr(optimization_plan, "budget_error", None) or "Execution budget exceeded."],
    }


def _dependency_error_runtime_pass(pass_spec: LLMUnifiedPass, dependency_resolution: dict[str, Any], *, run_context: RunContext | None = None) -> dict[str, Any]:
    error_message = "; ".join(str(item) for item in dependency_resolution.get("errors", []) if item) or "Dependency placeholder could not be resolved."
    run_id = run_context.run_id if run_context else None
    return {
        "run_id": run_id,
        "pass_id": pass_spec.pass_id,
        "global_pass_id": f"{run_id}:{pass_spec.pass_id}" if run_id else None,
        "attempt_id": 0,
        "plan_version": run_context.plan_version if run_context else 1,
        "subtask": pass_spec.subtask,
        "path": pass_spec.path,
        "status": "DEPENDENCY_BLOCKED",
        "can_run_parallel": pass_spec.can_run_parallel,
        "depends_on": pass_spec.depends_on,
        "expected_result": pass_spec.expected_result,
        "started_at": None,
        "completed_at": None,
        "stage_history": [],
        "dependency_resolution": dependency_resolution,
        "source_results": [
            {
                "source": "DEPENDENCY_RESOLUTION",
                "status": "ERROR",
                "scope": "RUNTIME",
                "result": dependency_resolution,
                "error": error_message,
                "gate_passed": False,
                "repair_attempts": 1 if dependency_resolution.get("repair_attempted") else 0,
            }
        ],
        "facts": [],
        "caveats": [error_message],
    }


def _early_stopped_runtime_pass(pass_spec: LLMUnifiedPass, decision: dict[str, Any], *, run_context: RunContext | None = None) -> dict[str, Any]:
    reason = str(decision.get("reason") or "optional pass skipped")
    run_id = run_context.run_id if run_context else None
    return {
        "run_id": run_id,
        "pass_id": pass_spec.pass_id,
        "global_pass_id": f"{run_id}:{pass_spec.pass_id}" if run_id else None,
        "attempt_id": 0,
        "plan_version": run_context.plan_version if run_context else 1,
        "subtask": pass_spec.subtask,
        "path": pass_spec.path,
        "status": "SKIPPED",
        "can_run_parallel": pass_spec.can_run_parallel,
        "depends_on": pass_spec.depends_on,
        "expected_result": pass_spec.expected_result,
        "started_at": None,
        "completed_at": None,
        "stage_history": [],
        "dependency_resolution": {"required": bool(pass_spec.depends_on), "resolved": True, "errors": []},
        "source_results": [
            {
                "source": "EXECUTION_OPTIMIZER",
                "status": "SKIPPED",
                "scope": "RUNTIME",
                "result": decision,
                "error": None,
                "gate_passed": True,
                "repair_attempts": 0,
            }
        ],
        "facts": [],
        "caveats": [reason],
    }


def _pass_status_from_source_results(source_results: list[dict[str, Any]]) -> str:
    statuses = {str(item.get("status") or "").upper() for item in source_results if isinstance(item, dict)}
    if not statuses:
        return "SKIPPED"
    for status in ["COMPILE_ERROR", "REQUEST_ERROR", "API_ERROR", "ERROR", "LIVE_EMPTY", "EMPTY"]:
        if status in statuses:
            return status
    return "SUCCESS"


PLACEHOLDER_RE = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")


def _resolve_pass_placeholders(pass_spec: LLMUnifiedPass, runtime_passes: list[dict[str, Any]], *, run_id: str | None) -> tuple[LLMUnifiedPass, dict[str, Any]]:
    errors: list[str] = []
    replacements: list[dict[str, Any]] = []

    def resolve_value(value: Any) -> Any:
        if isinstance(value, str):
            matches = list(PLACEHOLDER_RE.finditer(value))
            if not matches:
                return value
            if len(matches) == 1 and matches[0].span() == (0, len(value)):
                resolved = _resolve_placeholder_token(matches[0].group(1), runtime_passes, run_id=run_id)
                if resolved.get("ok"):
                    replacements.append({"placeholder": matches[0].group(0), "value_preview": compact_preview(resolved.get("value"), 200)})
                    return resolved.get("value")
                errors.append(str(resolved.get("error")))
                return value
            out = value
            for match in matches:
                resolved = _resolve_placeholder_token(match.group(1), runtime_passes, run_id=run_id)
                if resolved.get("ok"):
                    replacements.append({"placeholder": match.group(0), "value_preview": compact_preview(resolved.get("value"), 200)})
                    out = out.replace(match.group(0), str(resolved.get("value")))
                else:
                    errors.append(str(resolved.get("error")))
            return out
        if isinstance(value, list):
            return [resolve_value(item) for item in value]
        if isinstance(value, dict):
            return {key: resolve_value(item) for key, item in value.items()}
        return value

    sql = pass_spec.sql
    if sql is not None:
        sql = LLMUnifiedSQLCandidate(query=resolve_value(sql.query), params=resolve_value(sql.params))
    api_request = pass_spec.api_request
    if api_request is not None:
        api_request = LLMUnifiedAPIRequest(
            method=api_request.method,
            path=resolve_value(api_request.path),
            params=resolve_value(api_request.params),
        )
    resolved_pass = LLMUnifiedPass(
        pass_id=pass_spec.pass_id,
        subtask=pass_spec.subtask,
        path=pass_spec.path,
        can_run_parallel=pass_spec.can_run_parallel,
        depends_on=pass_spec.depends_on,
        evidence_order=pass_spec.evidence_order,
        sql=sql,
        api_request=api_request,
        expected_result=pass_spec.expected_result,
        optional=pass_spec.optional,
        fallback=pass_spec.fallback,
    )
    required = bool(PLACEHOLDER_RE.search(json.dumps(pass_spec.to_dict(), default=str)))
    return resolved_pass, {
        "required": required,
        "resolved": not errors,
        "run_id": run_id,
        "errors": errors,
        "replacements": replacements,
    }


def _resolve_placeholder_token(token: str, runtime_passes: list[dict[str, Any]], *, run_id: str | None) -> dict[str, Any]:
    if not run_id:
        return {"ok": False, "error": "Placeholder resolution requires run_id."}
    text = str(token or "").strip()
    marker = ".result."
    if marker not in text:
        return {"ok": False, "error": f"Unsupported placeholder '{{{{{text}}}}}'."}
    pass_id, field_path = text.split(marker, 1)
    pass_id = pass_id.strip()
    field_path = field_path.strip()
    runtime_pass = next((item for item in runtime_passes if str(item.get("pass_id")) == pass_id and (not item.get("run_id") or item.get("run_id") == run_id)), None)
    if runtime_pass is None:
        return {"ok": False, "error": f"Dependency pass '{pass_id}' has no completed result."}
    found, value = _lookup_runtime_pass_value(runtime_pass, field_path)
    if not found:
        return {"ok": False, "error": f"Dependency placeholder '{text}' could not be resolved."}
    return {"ok": True, "value": value}


def _lookup_runtime_pass_value(runtime_pass: dict[str, Any], field_path: str) -> tuple[bool, Any]:
    source_results = runtime_pass.get("source_results") if isinstance(runtime_pass.get("source_results"), list) else []
    for source in source_results:
        if not isinstance(source, dict) or str(source.get("status") or "").upper() not in {"SUCCESS", "LIVE_EMPTY", "EMPTY"}:
            continue
        result = source.get("result") if isinstance(source.get("result"), dict) else {}
        found, value = _lookup_result_payload(result, field_path)
        if found:
            return True, value
    return False, None


def _lookup_result_payload(payload: dict[str, Any], field_path: str) -> tuple[bool, Any]:
    rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
    for row in rows:
        if isinstance(row, dict) and field_path in row and row[field_path] not in (None, ""):
            return True, row[field_path]
    parsed = payload.get("parsed_evidence") if isinstance(payload.get("parsed_evidence"), dict) else {}
    field_aliases = {
        "id": "ids",
        "name": "names",
        "status": "statuses",
        "count": "counts",
    }
    for key in [field_path, field_aliases.get(field_path, "")]:
        if not key:
            continue
        value = parsed.get(key)
        if isinstance(value, list) and value:
            return True, value[0]
        if isinstance(value, dict) and value:
            first = next((item for item in value.values() if item not in (None, "")), None)
            if first is not None:
                return True, first
        if value not in (None, "", [], {}):
            return True, value
    preview = payload.get("result_preview")
    if isinstance(preview, dict):
        items = preview.get("items") if isinstance(preview.get("items"), list) else []
        for item in items:
            if isinstance(item, dict) and field_path in item and item[field_path] not in (None, ""):
                return True, item[field_path]
    return _lookup_nested_value(payload, field_path.split("."))


def _lookup_nested_value(value: Any, parts: list[str]) -> tuple[bool, Any]:
    current = value
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            return False, None
    return (current not in (None, "", [], {})), current


def _source_result_from_tool_result(item: dict[str, Any]) -> dict[str, Any]:
    kind = str(item.get("type") or "").lower()
    payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
    if kind == "sql":
        rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
        compile_gate = payload.get("compile_gate") if isinstance(payload.get("compile_gate"), dict) else None
        if compile_gate and not compile_gate.get("passed"):
            status = "COMPILE_ERROR"
        else:
            status = "SUCCESS" if payload.get("ok") and rows else ("EMPTY" if payload.get("ok") else "ERROR")
        return {
            "source": "cached" if item.get("cached") else "SQL",
            "cached_source": "SQL" if item.get("cached") else None,
            "status": status,
            "scope": "LOCAL_SNAPSHOT",
            "result": {"rows": rows[:5], "row_count": payload.get("row_count", len(rows)), "sql": payload.get("sql")},
            "error": payload.get("error"),
            "gate_passed": None if compile_gate is None else bool(compile_gate.get("passed")),
            "repair_attempts": 0,
        }
    parsed = payload.get("parsed_evidence") if isinstance(payload.get("parsed_evidence"), dict) else {}
    gate = payload.get("api_request_gate") if isinstance(payload.get("api_request_gate"), dict) else None
    state = str(parsed.get("evidence_state") or "").lower()
    if gate and not gate.get("passed"):
        status = "REQUEST_ERROR"
    elif not payload.get("ok") or state in {"api_error", "malformed_response"}:
        status = "API_ERROR"
    elif "empty" in state:
        status = "LIVE_EMPTY"
    else:
        status = "SUCCESS"
    error = payload.get("error") or "; ".join(str(value) for value in parsed.get("errors", [])[:3]) if isinstance(parsed.get("errors"), list) else payload.get("error")
    return {
        "source": "cached" if item.get("cached") else "API",
        "cached_source": "API" if item.get("cached") else None,
        "status": status,
        "scope": "LIVE_API",
        "result": {"parsed_evidence": parsed, "result_preview": payload.get("result_preview")},
        "error": error,
        "gate_passed": None if gate is None else bool(gate.get("passed")),
        "repair_attempts": 0,
    }


def _facts_from_source_results(source_results: list[dict[str, Any]]) -> list[str]:
    facts: list[str] = []
    for result in source_results:
        payload = result.get("result") if isinstance(result.get("result"), dict) else {}
        rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
        for row in rows[:3]:
            if isinstance(row, dict):
                facts.extend(f"{key}:{value}" for key, value in row.items() if value not in (None, ""))
        parsed = payload.get("parsed_evidence") if isinstance(payload.get("parsed_evidence"), dict) else {}
        for key in ["names", "ids", "statuses"]:
            values = parsed.get(key)
            if isinstance(values, list):
                facts.extend(f"{key}:{value}" for value in values[:5])
        counts = parsed.get("counts")
        if isinstance(counts, dict):
            facts.extend(f"count:{value}" for value in counts.values() if value not in (None, ""))
    return facts[:20]


def _runtime_passes_from_tool_results(tool_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    passes: list[dict[str, Any]] = []
    counters = {"sql": 0, "api": 0}
    for item in tool_results:
        kind = str(item.get("type") or "").lower()
        if kind not in counters:
            continue
        counters[kind] += 1
        payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
        step = item.get("step") if isinstance(item.get("step"), dict) else {}
        if kind == "sql":
            rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
            status = "SUCCESS" if payload.get("ok") and rows else ("EMPTY" if payload.get("ok") else "ERROR")
            result = {
                "sql": step.get("sql") or payload.get("sql"),
                "row_count": payload.get("row_count", len(rows)),
                "rows": rows[:5],
                "compile_gate": payload.get("compile_gate"),
                "error": payload.get("error"),
            }
            caveats = [str(payload.get("error"))] if payload.get("error") else []
            passes.append(
                {
                    "pass_id": f"sql_{counters[kind]}",
                    "source": "SQL",
                    "status": status,
                    "scope": "LOCAL_SNAPSHOT",
                    "result": result,
                    "caveats": caveats,
                }
            )
        else:
            parsed = payload.get("parsed_evidence") if isinstance(payload.get("parsed_evidence"), dict) else {}
            evidence_state = str(parsed.get("evidence_state") or "").lower()
            if not payload.get("ok") or evidence_state in {"api_error", "malformed_response"}:
                status = "API_ERROR"
            elif "empty" in evidence_state:
                status = "LIVE_EMPTY"
            else:
                status = "SUCCESS"
            error = payload.get("error") or "; ".join(str(value) for value in parsed.get("errors", [])[:3]) if isinstance(parsed.get("errors"), list) else payload.get("error")
            result = {
                "method": step.get("method"),
                "url": step.get("url"),
                "params": step.get("params") if isinstance(step.get("params"), dict) else {},
                "parsed_evidence": parsed,
                "result_preview": payload.get("result_preview"),
                "api_request_gate": payload.get("api_request_gate"),
                "error": error,
            }
            caveats = [str(error)] if error else []
            passes.append(
                {
                    "pass_id": f"api_{counters[kind]}",
                    "source": "API",
                    "status": status,
                    "scope": "LIVE_API",
                    "result": result,
                    "caveats": caveats,
                }
            )
    return passes


def _is_compact_experiment_output(output_dir: Path, outputs_dir: Path) -> bool:
    try:
        output_dir.resolve().relative_to((outputs_dir / "compact_context_measured_eval").resolve())
        return True
    except ValueError:
        return False


def _top_items_agree(left: list[Any], right: list[Any]) -> bool:
    if not left or not right:
        return False
    left_norm = [str(item).strip().lower() for item in left[:3] if str(item).strip()]
    right_norm = [str(item).strip().lower() for item in right[:3] if str(item).strip()]
    return bool(left_norm and right_norm and set(left_norm) & set(right_norm))


def render_system_prompt(config: Config, metadata: dict[str, Any]) -> str:
    template_path = config.prompts_dir / "system_prompt_template.txt"
    if template_path.exists():
        template = template_path.read_text(encoding="utf-8")
    else:
        template = "You are a constrained DASHSys QA agent.\nMetadata:\n{metadata_json}\n"
    return template.replace("{metadata_json}", json.dumps(metadata, indent=2, sort_keys=True, default=str))


def repair_sql(sql: str, validation: ValidationResult, schema_index: SchemaIndex) -> str | None:
    if not validation.errors:
        return None
    fake_column_errors = [error for error in validation.errors if error.startswith("Unknown column:")]
    if not fake_column_errors:
        return None
    table_match = re.search(r"\bFROM\s+\"?([a-zA-Z_][\w$]*)\"?", sql, flags=re.IGNORECASE)
    if not table_match:
        return None
    table = table_match.group(1)
    if not schema_index.table_exists(table):
        return None
    columns = schema_index.columns_for(table)[:8]
    if not columns:
        return f"SELECT * FROM \"{table}\" LIMIT 50"
    projection = ", ".join(f'"{column}"' for column in columns)
    return f"SELECT {projection} FROM \"{table}\" LIMIT 50"


def compact_routing_decision(decision: dict[str, Any]) -> dict[str, Any]:
    compact = dict(decision)
    compact["candidate_apis"] = [
        {
            key: api[key]
            for key in ["id", "method", "path"]
            if key in api
        }
        for api in decision.get("candidate_apis", [])
    ]
    return compact


def count_actions(actions: list[str], needles: list[str]) -> int:
    lowered = [" ".join(action.lower().split()) for action in actions]
    return sum(1 for action in lowered if any(needle in action for needle in needles))


def count_tool_plan_steps(steps: list[Any]) -> int:
    return sum(1 for step in steps if getattr(step, "action", None) in {"sql", "api"})


def _conceptual_no_tool_answer(query: str) -> str:
    lowered = query.lower()
    if "list" in lowered and ("the word" in lowered or "the phrase" in lowered or "in the phrase" in lowered or "what does" in lowered):
        return "In that phrase, list means to return or enumerate matching items; this is a wording question, not a request to query schema records."
    definitions = {
        "schema": "A schema is a blueprint for how data is structured: it defines fields, types, and constraints so systems can interpret records consistently.",
        "merge polic": "A merge policy defines how profile fragments from multiple sources are combined when building a unified customer profile.",
        "segment": "A segment is a rule-defined audience group used to select profiles that meet specific traits, behaviors, or eligibility conditions.",
        "audience": "An audience is a group of profiles selected for activation, personalization, or analysis based on shared criteria.",
        "tag": "A tag is a label used to organize, categorize, and find platform objects without changing the underlying object data.",
        "dataset": "A dataset is a collection of records stored under a defined structure for ingestion, querying, or downstream activation.",
        "journey": "A journey is an orchestration that moves customers through messaging or activation steps based on events and conditions.",
        "campaign": "A campaign is a coordinated marketing effort that delivers messages or experiences to a selected audience.",
        "dataflow": "A dataflow describes how data moves between a source, processing step, and destination.",
        "flow": "A flow describes how data moves between a source, processing step, and destination.",
        "batch": "A batch is a grouped data ingestion or processing unit handled as one operation.",
        "audit": "An audit event is a record of an action or system event used for observability, governance, and troubleshooting.",
    }
    for needle, answer in definitions.items():
        if needle in lowered:
            return answer
    return "This is a conceptual question about the platform. It can be answered without concrete local records or live API state."


def _latest_sql_payload(tool_results: list[dict[str, Any]]) -> dict[str, Any] | None:
    for result in reversed(tool_results):
        if result.get("type") == "sql" and isinstance(result.get("payload"), dict):
            return result["payload"]
    return None


def _local_snapshot_sql_complete_api_optional(query: str, features: Any, card: dict[str, Any]) -> bool:
    feature_payload = features.to_dict() if hasattr(features, "to_dict") else dict(features or {})
    flags = set(str(value) for value in feature_payload.get("flags") or [])
    norm = str(feature_payload.get("norm") or query or "").lower()
    sql_state = card.get("sql_state") if isinstance(card.get("sql_state"), dict) else {}
    returned_roles = set(str(role) for role in sql_state.get("returned_roles") or [])
    missing_roles = set(str(role) for role in sql_state.get("missing_roles") or [])
    live_or_api_flags = {"LIVE", "CURRENT", "PLATFORM", "API", "LIVE_OR_CURRENT", "EXPLICIT_API_FAMILY"}
    return bool(
        "local snapshot" in norm
        and sql_state.get("direct_answer")
        and "count" in returned_roles
        and not missing_roles
        and not (flags & live_or_api_flags)
    )


def tool_results_execution_summary(tool_results: list[dict[str, Any]]) -> dict[str, Any]:
    sql_summaries = []
    api_summaries = []
    for result in tool_results:
        payload = result.get("payload", {})
        if result.get("type") == "sql":
            sql_summaries.append(
                {
                    "ok": bool(payload.get("ok")),
                    "row_count": payload.get("row_count", 0),
                    "result_preview": payload.get("rows", [])[:3] if isinstance(payload.get("rows"), list) else payload,
                }
            )
        elif result.get("type") == "api":
            step = result.get("step", {})
            compact_outcome = compact_api_outcome(payload)
            api_summaries.append(
                {
                    "ok": bool(payload.get("ok")),
                    "dry_run": bool(payload.get("dry_run")),
                    "method": step.get("method"),
                    "url": step.get("url"),
                    "status_code": payload.get("status_code") or payload.get("status"),
                    "result_preview": compact_outcome,
                }
            )
    return {
        "sql_calls_executed": len(sql_summaries),
        "api_calls_executed": len(api_summaries),
        "dry_run_status": any(item.get("dry_run") for item in api_summaries),
        "row_counts": [item.get("row_count", 0) for item in sql_summaries],
        "api_status_codes": [item.get("status_code") for item in api_summaries if item.get("status_code") is not None],
        "sql_results": sql_summaries,
        "api_results": api_summaries,
    }
