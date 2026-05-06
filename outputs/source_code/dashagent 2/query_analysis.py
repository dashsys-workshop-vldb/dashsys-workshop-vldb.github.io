from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .answer_templates import classify_answer_family
from .api_templates import APITemplate, find_api_templates
from .config import Config, DEFAULT_CONFIG
from .endpoint_catalog import EndpointCatalog
from .evidence_policy import ApiNeedDecision, decide_api_need
from .fast_paths import FastPath, find_fast_path
from .lookup_paths import LookupPath, predict_lookup_path
from .query_normalizer import normalize_query
from .query_tokens import QueryTokens, extract_query_tokens
from .relevance_scorer import RelevanceResult, score_relevance
from .router import RoutingDecision
from .schema_index import SchemaIndex
from .sql_templates import SQLTemplate, find_sql_template


@dataclass(frozen=True)
class QueryAnalysis:
    query: str
    normalized_query: str
    matching_text: str
    normalization_rewrites: list[str]
    tokens: QueryTokens
    route_type: str
    domain_type: str
    answer_family: str
    sql_template: SQLTemplate | None
    api_templates: list[APITemplate]
    api_need_decision: ApiNeedDecision
    fast_path: FastPath | None
    lookup_path: LookupPath
    relevance: RelevanceResult
    confidence: float

    def to_metadata(self) -> dict[str, Any]:
        return {
            "answer_family": self.answer_family,
            "lookup_path": self.lookup_path.family,
            "api_need": self.api_need_decision.mode,
            "confidence": round(self.confidence, 4),
            "sql_template_family": self.sql_template.family if self.sql_template else None,
            "api_template_families": [template.family for template in self.api_templates],
            "normalization_rewrites": self.normalization_rewrites[:5],
            "tokens": self.tokens.compact(),
            "relevance": self.relevance.compact(),
        }


def analyze_query(
    query: str,
    routing: RoutingDecision,
    schema_index: SchemaIndex,
    *,
    strategy: str,
    config: Config | None = None,
    endpoint_catalog: EndpointCatalog | None = None,
    normalized: dict[str, Any] | None = None,
    tokens: QueryTokens | None = None,
) -> QueryAnalysis:
    cfg = config or DEFAULT_CONFIG
    norm = normalized or normalize_query(query)
    normalized_query = str(norm.get("normalized") or query)
    matching_text = str(norm.get("matching_text") or normalized_query.lower())
    token_obj = tokens or extract_query_tokens(query, norm)
    answer_family = classify_answer_family(matching_text)
    fast_path = None if cfg.disable_fast_paths else find_fast_path(normalized_query, schema_index)
    sql_template = fast_path.sql_template if fast_path else find_sql_template(normalized_query, schema_index)
    api_templates = fast_path.api_templates if fast_path else find_api_templates(normalized_query, cfg)
    lookup_path = predict_lookup_path(matching_text, answer_family, routing.domain_type)
    relevance = score_relevance(
        normalized_query,
        schema_index,
        endpoint_catalog,
        tokens=token_obj,
        lookup_path=lookup_path,
    )
    api_need = decide_api_need(matching_text, routing, sql_template, api_templates, strategy)
    confidence = min(1.0, float(routing.confidence) + (0.1 if fast_path else 0.0) + (0.05 if sql_template else 0.0))
    if fast_path and confidence < cfg.fast_path_confidence_threshold:
        fast_path = None
    return QueryAnalysis(
        query=query,
        normalized_query=normalized_query,
        matching_text=matching_text,
        normalization_rewrites=list(norm.get("rewrites", [])),
        tokens=token_obj,
        route_type=routing.route_type,
        domain_type=routing.domain_type,
        answer_family=answer_family,
        sql_template=sql_template,
        api_templates=api_templates,
        api_need_decision=api_need,
        fast_path=fast_path,
        lookup_path=lookup_path,
        relevance=relevance,
        confidence=confidence,
    )
