from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from .answer_claims import extract_claims
from .answer_intent import classify_answer_intent
from .answer_slots import extract_answer_slots
from .answer_synthesizer import synthesize_answer_with_diagnostics
from .answer_verifier import verify_answer
from .api_client import AdobeAPIClient
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
from .config import Config, DEFAULT_CONFIG
from .db import DuckDBDatabase
from .endpoint_catalog import EndpointCatalog
from .evidence_bus import EvidenceBus
from .evidence_policy import API_SKIP
from .gated_sql_candidates import hard_case_triggers, select_gated_sql_candidate
from .metadata_selector import MetadataSelector
from .plan_ensemble import select_plan_candidate
from .planner import ALL_STRATEGIES, LLM_SQL_STRATEGIES, Plan, PlanStep, STRATEGIES, StrategyPlanner
from .query_normalizer import normalize_query
from .query_tokens import extract_query_tokens
from .llm_sql_generator import generate_sql_with_llm, repair_sql_with_llm
from .query_decomposer import decompose_query
from .query_family_examples import examples_for_family, few_shot_public_overlap_check
from .query_analysis import analyze_query
from .router import QueryRouter
from .schema_index import SchemaIndex
from .simple_prompt_gate import decide_simple_prompt
from .prompt_router import LLM_DIRECT, route_prompt
from .trajectory import TrajectoryLogger, estimate_tokens
from .validators import APIValidator, SQLValidator, ValidationResult
from .value_retrieval import build_value_index, extract_query_values, retrieve_value_matches, value_retrieval_summary


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
        self.planner = StrategyPlanner(self.schema_index)
        self.sql_validator = SQLValidator(self.schema_index, enable_ast_validation=self.config.enable_sql_ast_validation)
        self.api_validator = APIValidator(
            self.endpoint_catalog,
            allow_unknown=self.config.allow_unknown_api_endpoints,
        )
        self.cache_fingerprint = current_fingerprint(self.config)

    def run(
        self,
        query: str,
        *,
        strategy: str = "SQL_FIRST_API_VERIFY",
        query_id: str | None = None,
        output_dir: Path | None = None,
    ) -> dict[str, Any]:
        if strategy not in ALL_STRATEGIES:
            raise ValueError(f"Unknown strategy {strategy}. Expected one of {ALL_STRATEGIES}.")
        qid = query_id or slugify(query)
        out_dir = output_dir or (self.config.outputs_dir / qid / strategy.lower())
        out_dir.mkdir(parents=True, exist_ok=True)
        checkpoint_logger = CheckpointLogger(max_preview_chars=self.config.max_preview_chars)
        checkpoint_logger.add_checkpoint(
            "checkpoint_01_raw_query",
            stage="input",
            technique="raw user query capture",
            output={"query_id": qid, "query": query, "strategy": strategy},
            effect="preserves the original query for reproducibility",
            correctness_role="keeps later normalization from changing the user-facing question",
            efficiency_role="starts one trace without extra tool calls",
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
        analysis_key = query_analysis_cache_key(query, strategy, self.config, self.cache_fingerprint)
        analysis = get_query_analysis_cache(analysis_key)
        if analysis is None:
            analysis = analyze_query(
                query,
                routing,
                self.schema_index,
                strategy=strategy,
                config=self.config,
                endpoint_catalog=self.endpoint_catalog,
                normalized=normalization,
                tokens=tokens,
            )
            set_query_analysis_cache(analysis_key, analysis)
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
        metadata = self.metadata_selector.select(
            query,
            routing,
            strategy=strategy,
            query_id=qid,
            broad_context=broad,
            analysis=analysis,
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
        preprocessing_time = time.perf_counter() - preprocessing_start

        planning_start = time.perf_counter()
        plan_strategy = "SQL_FIRST_API_VERIFY" if strategy in LLM_SQL_STRATEGIES else strategy
        if strategy in LLM_SQL_STRATEGIES:
            plan = self._create_llm_sql_plan(query, routing, metadata, strategy, analysis, checkpoint_logger)
        else:
            plan = self.planner.create_plan(query, routing, metadata, plan_strategy, analysis=analysis)
        original_planned_step_count = len(plan.steps)
        ensemble_metadata = None
        if strategy == "SQL_FIRST_API_VERIFY":
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
        budget = budget_for_strategy(strategy, api_families, analysis.api_need_decision.max_api_calls)
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
                forwarding_actions = evidence_bus.forward_to_step(step)
                if forwarding_actions:
                    forwarding_actions_all.extend(forwarding_actions)
                    trajectory.add_step("optimizer", {"actions": forwarding_actions})
                validation = self.api_validator.validate(step.method, step.url, step.params, step.headers)
                if validation.ok:
                    api_cache_key = api_response_cache_key(step.method, step.url, step.params)
                    result = get_api_response_cache(api_cache_key) if self.api_client.dry_run else None
                    if result is None:
                        result = self.api_client.call_api(step.method, step.url, step.params, step.headers)
                        if result.get("dry_run"):
                            set_api_response_cache(api_cache_key, result)
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
        answer_result = synthesize_answer_with_diagnostics(query, tool_results)
        final_answer = answer_result.answer
        slots = extract_answer_slots(query, tool_results)
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
        trajectory_payload = trajectory.save(out_dir / "trajectory.json", final_answer)
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
        if sql and not validation.ok and not generation.get("skipped"):
            repair = repair_sql_with_llm(query, sql, validation.errors, schema_context or {})
            checkpoint_logger.add_checkpoint(
                "checkpoint_llm_sql_repair",
                stage="llm sql repair",
                technique="one-shot LLM SQL repair",
                input_summary={"bad_sql": sql, "validation_errors": validation.errors},
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


def slugify(text: str, max_length: int = 48) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", text.lower()).strip("_")
    return (slug[:max_length] or "query").strip("_")


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
            api_summaries.append(
                {
                    "ok": bool(payload.get("ok")),
                    "dry_run": bool(payload.get("dry_run")),
                    "method": step.get("method"),
                    "url": step.get("url"),
                    "status_code": payload.get("status_code") or payload.get("status"),
                    "result_preview": payload.get("result_preview") or payload.get("body") or payload,
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
