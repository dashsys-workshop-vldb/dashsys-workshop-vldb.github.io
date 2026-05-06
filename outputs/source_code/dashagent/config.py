from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _path_from_env(name: str, default: Path) -> Path:
    value = os.getenv(name)
    return Path(value).expanduser() if value else default


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
    enable_official_token_reduction: bool = False
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
            enable_official_token_reduction=os.getenv("ENABLE_OFFICIAL_TOKEN_REDUCTION", "0") == "1",
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
