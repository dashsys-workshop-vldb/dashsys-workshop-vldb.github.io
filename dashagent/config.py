from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path


def _path_from_env(name: str, default: Path) -> Path:
    value = os.getenv(name)
    return Path(value).expanduser() if value else default


def _bool_from_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def find_project_root(start: Path | None = None) -> Path:
    """Find the project root without relying on machine-local absolute paths."""
    explicit = os.getenv("DASHAGENT_ROOT")
    if explicit:
        return Path(explicit).expanduser().resolve()

    current = (start or Path.cwd()).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "dashagent").is_dir() and (candidate / "scripts").is_dir():
            return candidate
    return current


@dataclass(frozen=True)
class Config:
    project_root: Path
    data_dir: Path
    dbsnapshot_dir: Path
    data_json_path: Path
    outputs_dir: Path
    prompts_dir: Path
    max_preview_chars: int = 1000
    max_result_rows: int = 50
    api_timeout_seconds: int = 15
    allow_unknown_api_endpoints: bool = False
    max_join_hints: int = 8
    max_gold_patterns: int = 2
    compact_metadata: bool = True
    relevance_top_k_tables: int = 8
    relevance_top_k_apis: int = 4
    fast_path_confidence_threshold: float = 0.0
    api_skip_confidence_threshold: float = 0.0
    disable_fast_paths: bool = False
    disable_gold_patterns: bool = False
    disable_context_cards: bool = False
    disable_api_fallback_templates: bool = False
    drop_one_join_hint: bool = False
    enable_sql_ast_validation: bool = True
    enable_schema_linking: bool = True
    enable_value_retrieval: bool = True
    enable_gated_sql_candidates: bool = True
    enable_query_decomposition: bool = True
    enable_query_family_examples: bool = False
    enable_research_span_export: bool = True
    enable_hybrid_candidate_scoring: bool = True
    enable_endpoint_family_ranking: bool = True
    enable_structural_schema_preservation: bool = True
    enable_value_to_api_ranking: bool = True
    enable_gated_risk_cluster_repair: bool = True
    enable_gated_risk_cluster_repair_execution: bool = False
    enable_repair_for_batch_endpoint_confusion: bool = False
    enable_repair_for_tag_api_confusion: bool = False
    enable_repair_for_schema_dataset_confusion: bool = False
    enable_repair_for_zero_score_margin: bool = False
    enable_repair_for_missing_api_topk: bool = False
    enable_compact_context_when_schema_vote_safe: bool = False
    enable_official_token_reduction: bool = True
    enable_endpoint_schema_rule_candidates: bool = False
    enable_ast_guided_sql_tiebreak: bool = False
    enable_targeted_accuracy_rules: bool = False
    enable_answer_shape_v2: bool = False
    enable_sql_only_api_skip_guard: bool = False
    enable_endpoint_family_tiebreak_v2: bool = False
    enable_schema_aware_sql_fallback: bool = False
    enable_llm_semantic_router: bool = False
    llm_semantic_router_shadow_only: bool = True
    llm_semantic_router_confidence_threshold: float = 0.55
    llm_semantic_router_ambiguity_margin: float = 0.10
    llm_semantic_router_max_tokens: int = 512
    llm_semantic_router_trial_policy: str = "broad"
    enable_objective_prompt_features: bool = True
    enable_semantic_intent_classifier: bool = False
    enable_routing_anti_hallucination_gate: bool = True
    enable_no_tool_safety_verifier: bool = True
    enable_semantic_route_decision_ladder: bool = False
    enable_safe_api_probe: bool = False
    semantic_route_shadow_only: bool = True
    semantic_route_tier2_diagnostic: bool = False
    semantic_route_verbose_reports: bool = False
    enable_staged_evidence_policy: bool = False
    staged_evidence_policy_shadow_only: bool = True
    enable_post_sql_api_decision: bool = False
    enable_post_sql_deterministic_policy: bool = False
    post_sql_api_decision_shadow_only: bool = True
    post_sql_llm_advisor_enabled: bool = False
    enable_evidence_quality_classifier: bool = False
    enable_answer_slot_renderer: bool = False
    enable_evidence_grounded_answer_builder: bool = False
    enable_score_provenance_guard: bool = False
    enable_runtime_leakage_guard: bool = False
    enable_hardcode_fake_score_guard: bool = False
    enable_broad_semantic_no_tool: bool = False
    enable_robust_generalized_candidate: bool = False
    candidate_shadow_only: bool = True
    real_behavior_trial_mode: str = ""
    enable_semantic_no_tool_applied_trial: bool = False
    enable_staged_evidence_applied_trial: bool = False
    enable_post_sql_deterministic_applied_trial: bool = False
    enable_post_sql_llm_advisor_applied_trial: bool = False
    enable_combined_safe_applied_trial: bool = False
    value_retrieval_max_tables: int = 6
    value_retrieval_max_columns: int = 18
    value_retrieval_max_rows_per_column: int = 500
    value_retrieval_max_ms: int = 250

    @classmethod
    def from_env(cls, root: Path | None = None) -> "Config":
        project_root = find_project_root(root)
        data_dir = _path_from_env("DASHAGENT_DATA_DIR", project_root / "data")
        outputs_dir = _path_from_env("DASHAGENT_OUTPUTS_DIR", project_root / "outputs")
        prompts_dir = _path_from_env("DASHAGENT_PROMPTS_DIR", project_root / "prompts")
        return cls(
            project_root=project_root,
            data_dir=data_dir,
            dbsnapshot_dir=_path_from_env("DASHAGENT_DBSNAPSHOT_DIR", data_dir / "DBSnapshot"),
            data_json_path=_path_from_env("DASHAGENT_DATA_JSON", data_dir / "data.json"),
            outputs_dir=outputs_dir,
            prompts_dir=prompts_dir,
            max_preview_chars=int(os.getenv("DASHAGENT_MAX_PREVIEW_CHARS", "1000")),
            max_result_rows=int(os.getenv("DASHAGENT_MAX_RESULT_ROWS", "50")),
            api_timeout_seconds=int(os.getenv("DASHAGENT_API_TIMEOUT_SECONDS", "15")),
            allow_unknown_api_endpoints=os.getenv("DASHAGENT_ALLOW_UNKNOWN_API", "0") == "1",
            max_join_hints=int(os.getenv("DASHAGENT_MAX_JOIN_HINTS", "8")),
            max_gold_patterns=int(os.getenv("DASHAGENT_MAX_GOLD_PATTERNS", "2")),
            compact_metadata=os.getenv("DASHAGENT_COMPACT_METADATA", "1") != "0",
            relevance_top_k_tables=int(os.getenv("DASHAGENT_RELEVANCE_TOP_K_TABLES", "8")),
            relevance_top_k_apis=int(os.getenv("DASHAGENT_RELEVANCE_TOP_K_APIS", "4")),
            fast_path_confidence_threshold=float(os.getenv("DASHAGENT_FAST_PATH_CONFIDENCE_THRESHOLD", "0.0")),
            api_skip_confidence_threshold=float(os.getenv("DASHAGENT_API_SKIP_CONFIDENCE_THRESHOLD", "0.0")),
            disable_fast_paths=os.getenv("DASHAGENT_DISABLE_FAST_PATHS", "0") == "1",
            disable_gold_patterns=os.getenv("DASHAGENT_DISABLE_GOLD_PATTERNS", "0") == "1",
            disable_context_cards=os.getenv("DASHAGENT_DISABLE_CONTEXT_CARDS", "0") == "1",
            disable_api_fallback_templates=os.getenv("DASHAGENT_DISABLE_API_FALLBACK_TEMPLATES", "0") == "1",
            drop_one_join_hint=os.getenv("DASHAGENT_DROP_ONE_JOIN_HINT", "0") == "1",
            enable_sql_ast_validation=os.getenv("ENABLE_SQL_AST_VALIDATION", "1") != "0",
            enable_schema_linking=os.getenv("ENABLE_SCHEMA_LINKING", "1") != "0",
            enable_value_retrieval=os.getenv("ENABLE_VALUE_RETRIEVAL", "1") != "0",
            enable_gated_sql_candidates=os.getenv("ENABLE_GATED_SQL_CANDIDATES", "1") != "0",
            enable_query_decomposition=os.getenv("ENABLE_QUERY_DECOMPOSITION", "1") != "0",
            enable_query_family_examples=os.getenv("ENABLE_QUERY_FAMILY_EXAMPLES", "0") == "1",
            enable_research_span_export=os.getenv("ENABLE_RESEARCH_SPAN_EXPORT", "1") != "0",
            enable_hybrid_candidate_scoring=os.getenv("ENABLE_HYBRID_CANDIDATE_SCORING", "1") != "0",
            enable_endpoint_family_ranking=os.getenv("ENABLE_ENDPOINT_FAMILY_RANKING", "1") != "0",
            enable_structural_schema_preservation=os.getenv("ENABLE_STRUCTURAL_SCHEMA_PRESERVATION", "1") != "0",
            enable_value_to_api_ranking=os.getenv("ENABLE_VALUE_TO_API_RANKING", "1") != "0",
            enable_gated_risk_cluster_repair=os.getenv("ENABLE_GATED_RISK_CLUSTER_REPAIR", "1") != "0",
            enable_gated_risk_cluster_repair_execution=os.getenv("ENABLE_GATED_RISK_CLUSTER_REPAIR_EXECUTION", "0") == "1",
            enable_repair_for_batch_endpoint_confusion=os.getenv("ENABLE_REPAIR_FOR_BATCH_ENDPOINT_CONFUSION", "0") == "1",
            enable_repair_for_tag_api_confusion=os.getenv("ENABLE_REPAIR_FOR_TAG_API_CONFUSION", "0") == "1",
            enable_repair_for_schema_dataset_confusion=os.getenv("ENABLE_REPAIR_FOR_SCHEMA_DATASET_CONFUSION", "0") == "1",
            enable_repair_for_zero_score_margin=os.getenv("ENABLE_REPAIR_FOR_ZERO_SCORE_MARGIN", "0") == "1",
            enable_repair_for_missing_api_topk=os.getenv("ENABLE_REPAIR_FOR_MISSING_API_TOPK", "0") == "1",
            enable_compact_context_when_schema_vote_safe=os.getenv("ENABLE_COMPACT_CONTEXT_WHEN_SCHEMA_VOTE_SAFE", "0") == "1",
            enable_official_token_reduction=os.getenv("ENABLE_OFFICIAL_TOKEN_REDUCTION", "1") != "0",
            enable_endpoint_schema_rule_candidates=os.getenv("ENABLE_ENDPOINT_SCHEMA_RULE_CANDIDATES", "0") == "1",
            enable_ast_guided_sql_tiebreak=os.getenv("ENABLE_AST_GUIDED_SQL_TIEBREAK", "0") == "1",
            enable_targeted_accuracy_rules=os.getenv("ENABLE_TARGETED_ACCURACY_RULES", "0") == "1",
            enable_answer_shape_v2=os.getenv("ENABLE_ANSWER_SHAPE_V2", "0") == "1",
            enable_sql_only_api_skip_guard=os.getenv("ENABLE_SQL_ONLY_API_SKIP_GUARD", "0") == "1",
            enable_endpoint_family_tiebreak_v2=os.getenv("ENABLE_ENDPOINT_FAMILY_TIEBREAK_V2", "0") == "1",
            enable_schema_aware_sql_fallback=_bool_from_env("ENABLE_SCHEMA_AWARE_SQL_FALLBACK", False),
            enable_llm_semantic_router=_bool_from_env("ENABLE_LLM_SEMANTIC_ROUTER", False),
            llm_semantic_router_shadow_only=_bool_from_env("LLM_SEMANTIC_ROUTER_SHADOW_ONLY", True),
            llm_semantic_router_confidence_threshold=float(os.getenv("LLM_SEMANTIC_ROUTER_CONFIDENCE_THRESHOLD", "0.55")),
            llm_semantic_router_ambiguity_margin=float(os.getenv("LLM_SEMANTIC_ROUTER_AMBIGUITY_MARGIN", "0.10")),
            llm_semantic_router_max_tokens=int(os.getenv("LLM_SEMANTIC_ROUTER_MAX_TOKENS", "512")),
            llm_semantic_router_trial_policy=os.getenv("LLM_SEMANTIC_ROUTER_TRIAL_POLICY", "broad"),
            enable_objective_prompt_features=_bool_from_env("ENABLE_OBJECTIVE_PROMPT_FEATURES", True),
            enable_semantic_intent_classifier=_bool_from_env("ENABLE_SEMANTIC_INTENT_CLASSIFIER", False),
            enable_routing_anti_hallucination_gate=_bool_from_env("ENABLE_ROUTING_ANTI_HALLUCINATION_GATE", True),
            enable_no_tool_safety_verifier=_bool_from_env("ENABLE_NO_TOOL_SAFETY_VERIFIER", True),
            enable_semantic_route_decision_ladder=_bool_from_env("ENABLE_SEMANTIC_ROUTE_DECISION_LADDER", False),
            enable_safe_api_probe=_bool_from_env("ENABLE_SAFE_API_PROBE", False),
            semantic_route_shadow_only=_bool_from_env("SEMANTIC_ROUTE_SHADOW_ONLY", True),
            semantic_route_tier2_diagnostic=_bool_from_env("SEMANTIC_ROUTE_TIER2_DIAGNOSTIC", False),
            semantic_route_verbose_reports=_bool_from_env("SEMANTIC_ROUTE_VERBOSE_REPORTS", False),
            enable_staged_evidence_policy=_bool_from_env("ENABLE_STAGED_EVIDENCE_POLICY", False),
            staged_evidence_policy_shadow_only=_bool_from_env("STAGED_EVIDENCE_POLICY_SHADOW_ONLY", True),
            enable_post_sql_api_decision=_bool_from_env("ENABLE_POST_SQL_API_DECISION", False),
            enable_post_sql_deterministic_policy=_bool_from_env("ENABLE_POST_SQL_DETERMINISTIC_POLICY", False),
            post_sql_api_decision_shadow_only=_bool_from_env("POST_SQL_API_DECISION_SHADOW_ONLY", True),
            post_sql_llm_advisor_enabled=_bool_from_env("POST_SQL_LLM_ADVISOR_ENABLED", False),
            enable_evidence_quality_classifier=_bool_from_env("ENABLE_EVIDENCE_QUALITY_CLASSIFIER", False),
            enable_answer_slot_renderer=_bool_from_env("ENABLE_ANSWER_SLOT_RENDERER", False),
            enable_evidence_grounded_answer_builder=_bool_from_env("ENABLE_EVIDENCE_GROUNDED_ANSWER_BUILDER", False),
            enable_score_provenance_guard=_bool_from_env("ENABLE_SCORE_PROVENANCE_GUARD", False),
            enable_runtime_leakage_guard=_bool_from_env("ENABLE_RUNTIME_LEAKAGE_GUARD", False),
            enable_hardcode_fake_score_guard=_bool_from_env("ENABLE_HARDCODE_FAKE_SCORE_GUARD", False),
            enable_broad_semantic_no_tool=_bool_from_env("ENABLE_BROAD_SEMANTIC_NO_TOOL", False),
            enable_robust_generalized_candidate=_bool_from_env("ENABLE_ROBUST_GENERALIZED_CANDIDATE", False),
            candidate_shadow_only=_bool_from_env("CANDIDATE_SHADOW_ONLY", True),
            real_behavior_trial_mode=os.getenv("REAL_BEHAVIOR_TRIAL_MODE", ""),
            enable_semantic_no_tool_applied_trial=_bool_from_env("ENABLE_SEMANTIC_NO_TOOL_APPLIED_TRIAL", False),
            enable_staged_evidence_applied_trial=_bool_from_env("ENABLE_STAGED_EVIDENCE_APPLIED_TRIAL", False),
            enable_post_sql_deterministic_applied_trial=_bool_from_env("ENABLE_POST_SQL_DETERMINISTIC_APPLIED_TRIAL", False),
            enable_post_sql_llm_advisor_applied_trial=_bool_from_env("ENABLE_POST_SQL_LLM_ADVISOR_APPLIED_TRIAL", False),
            enable_combined_safe_applied_trial=_bool_from_env("ENABLE_COMBINED_SAFE_APPLIED_TRIAL", False),
            value_retrieval_max_tables=int(os.getenv("VALUE_RETRIEVAL_MAX_TABLES", "6")),
            value_retrieval_max_columns=int(os.getenv("VALUE_RETRIEVAL_MAX_COLUMNS", "18")),
            value_retrieval_max_rows_per_column=int(os.getenv("VALUE_RETRIEVAL_MAX_ROWS_PER_COLUMN", "500")),
            value_retrieval_max_ms=int(os.getenv("VALUE_RETRIEVAL_MAX_MS", "250")),
        )

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.dbsnapshot_dir.mkdir(parents=True, exist_ok=True)
        self.outputs_dir.mkdir(parents=True, exist_ok=True)
        self.prompts_dir.mkdir(parents=True, exist_ok=True)


DEFAULT_CONFIG = Config.from_env()


ROBUST_GENERALIZED_HARNESS_CANDIDATE = "ROBUST_GENERALIZED_HARNESS_CANDIDATE"


def robust_generalized_candidate_config(config: Config) -> Config:
    return replace(
        config,
        enable_objective_prompt_features=True,
        enable_semantic_intent_classifier=True,
        enable_routing_anti_hallucination_gate=True,
        enable_no_tool_safety_verifier=True,
        enable_semantic_route_decision_ladder=True,
        enable_safe_api_probe=True,
        semantic_route_shadow_only=False,
        enable_staged_evidence_policy=True,
        staged_evidence_policy_shadow_only=False,
        enable_post_sql_api_decision=True,
        enable_post_sql_deterministic_policy=True,
        post_sql_api_decision_shadow_only=False,
        enable_evidence_quality_classifier=True,
        enable_answer_slot_renderer=True,
        enable_evidence_grounded_answer_builder=True,
        enable_score_provenance_guard=True,
        enable_runtime_leakage_guard=True,
        enable_hardcode_fake_score_guard=True,
        enable_broad_semantic_no_tool=True,
        enable_robust_generalized_candidate=True,
        candidate_shadow_only=False,
        enable_semantic_no_tool_applied_trial=True,
        enable_staged_evidence_applied_trial=True,
        enable_post_sql_deterministic_applied_trial=True,
        enable_post_sql_llm_advisor_applied_trial=False,
        enable_combined_safe_applied_trial=True,
        post_sql_llm_advisor_enabled=False,
        real_behavior_trial_mode=ROBUST_GENERALIZED_HARNESS_CANDIDATE,
    )
