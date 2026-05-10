from __future__ import annotations

import json
import os
import re
from contextlib import contextmanager
from dataclasses import asdict, dataclass, replace
from typing import Any

from .answer_intent import AnswerIntent
from .config import Config, DEFAULT_CONFIG
from .endpoint_catalog import EndpointCatalog, normalize_api_path
from .llm_client import get_llm_client
from .query_analysis import QueryAnalysis
from .query_tokens import QueryTokens
from .router import DOMAIN_TYPES, ROUTE_TYPES, RoutingDecision
from .schema_index import SchemaIndex
from .trajectory import redact_secrets


HELPER_ROUTE_ALIASES = {
    "SQL_PLUS_API": "SQL_THEN_API",
    "SQL_THEN_API": "SQL_THEN_API",
    "SQL_ONLY": "SQL_ONLY",
    "API_ONLY": "API_ONLY",
    "API_THEN_SQL": "API_THEN_SQL",
    "SQL_AND_API_COMPARE": "SQL_AND_API_COMPARE",
    "UNKNOWN": "UNKNOWN",
}

HELPER_INTENT_ALIASES = {
    "COUNT": "COUNT",
    "LIST": "LIST",
    "STATUS": "STATUS",
    "DATE": "WHEN",
    "WHEN": "WHEN",
    "BOOLEAN": "YES_NO",
    "YES_NO": "YES_NO",
    "ID_LOOKUP": "DETAIL",
    "DETAIL": "DETAIL",
    "SUMMARY": "DETAIL",
    "COMPARISON": "COMPARISON",
    "UNKNOWN": "UNKNOWN",
}

HELPER_DOMAIN_ALIASES = {
    "audit": None,
    "audit_events": None,
    "audits": None,
    "schema_dataset": "DATASET_SCHEMA",
    "journey_campaign": "JOURNEY_CAMPAIGN",
    "segment_audience": "SEGMENT_AUDIENCE",
    "destination_dataflow": "DESTINATION_DATAFLOW",
    "property_field": "PROPERTY_FIELD",
    "unknown": "UNKNOWN",
}

ALLOWED_HELPER_DOMAINS = {
    "audit",
    "audit_events",
    "audits",
    "schema_dataset",
    "journey_campaign",
    "segment_audience",
    "destination_dataflow",
    "merge_policy",
    "tags",
    "batch",
    "observability",
    "property_field",
    "unknown",
}

HELPER_DOMAIN_VALUE_ALIASES = {
    "audit": "observability",
    "audits": "observability",
    "audit_events": "observability",
}

API_FAMILY_HINTS = {
    "journey_campaign": {"journey_list"},
    "schema_dataset": {"catalog_datasets", "schema_registry_schema", "schema_registry_schemas", "schemas_short"},
    "segment_audience": {"ups_audiences", "segment_definitions", "segment_jobs"},
    "destination_dataflow": {"flowservice_flows", "flowservice_runs", "audit_events", "audit_events_short"},
    "merge_policy": {"merge_policies"},
    "tags": {"unified_tags", "unified_tag_categories", "unified_tag_detail"},
    "batch": {"catalog_batches", "catalog_batch_detail", "export_batch_files", "export_batch_failed"},
    "observability": {"observability_metrics"},
}

AMBIGUOUS_PHRASES = [
    "data model",
    "data models",
    "broken things",
    "changed recently",
    "data objects",
    "connected",
    "anything inactive",
    "latest broken",
]

SECRET_RE = re.compile(r"sk-[A-Za-z0-9_-]{8,}|Authorization\s*:\s*Bearer|CLIENT_SECRET|ACCESS_TOKEN", re.I)
QUERY_ID_RE = re.compile(r"\b(example|query)_\d{3,}\b", re.I)
FINAL_ANSWER_LANGUAGE_RE = re.compile(r"\b(final answer|the answer is)\b", re.I)
ANSWER_NUMERIC_CLAIM_RE = re.compile(
    r"\b(you have\s+\d+|there (?:are|is)\s+\d+|the count is\s+\d+|result is\s+\d+)\b",
    re.I,
)
DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
UUID_RE = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)
MISSING = object()
SYNONYM_MAPPING_KEYS = {"user_phrase", "mapped_to", "target_domain", "reason"}
SAFE_SYNONYM_WORDS = {
    "api",
    "audience",
    "audiences",
    "audit",
    "audit_events",
    "audits",
    "blueprint",
    "blueprints",
    "count",
    "data_model",
    "data_models",
    "data_set",
    "data_sets",
    "dataset",
    "datasets",
    "date",
    "destination",
    "destinations",
    "failed",
    "latest",
    "list",
    "observability",
    "recent",
    "schema",
    "schemas",
    "segment",
    "segments",
    "sql",
    "status",
    "target",
    "targets",
    "when",
    "yes_no",
}


@dataclass(frozen=True)
class SemanticRoutingHint:
    likely_domain: str
    normalized_domain: str
    internal_domain_type: str | None
    answer_intent: str
    normalized_answer_intent: str
    route_suggestion: str
    internal_route_suggestion: str
    synonym_mappings: list[dict[str, str]]
    candidate_tables: list[str]
    candidate_api_families: list[str]
    candidate_api_ids: list[str]
    needs_api: bool
    confidence: float
    reason: str
    normalization_actions: list[str]
    raw: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SemanticRoutingResult:
    enabled: bool
    shadow_only: bool
    eligibility_reason: list[str]
    deterministic_route_type: str
    deterministic_domain_type: str
    deterministic_confidence_before: float
    final_runtime_confidence: float
    helper_called: bool = False
    helper_valid: bool = False
    helper_rejected_reason: str | None = None
    hint: SemanticRoutingHint | None = None
    would_change_route: bool = False
    would_change_domain: bool = False
    would_change_intent: bool = False
    hint_applied: bool = False
    hint_application_mode: str = "disabled"
    applied_to_runtime: bool = False
    provider: str | None = None
    model: str | None = None
    backend_type: str | None = None
    transport: str | None = None
    sdk_path_used: bool = False
    llm_client_path_used: bool = True

    @property
    def helper_confidence(self) -> float | None:
        return self.hint.confidence if self.hint else None

    def with_application(self, *, applied: bool, final_runtime_confidence: float) -> "SemanticRoutingResult":
        mode = "isolated_non_shadow" if applied else ("shadow_only" if self.shadow_only else "disabled")
        return replace(
            self,
            hint_applied=applied,
            applied_to_runtime=applied,
            final_runtime_confidence=final_runtime_confidence,
            hint_application_mode=mode,
        )

    def to_checkpoint(self) -> dict[str, Any]:
        payload = {
            "enabled": self.enabled,
            "shadow_only": self.shadow_only,
            "eligibility_reason": self.eligibility_reason,
            "deterministic_route_type": self.deterministic_route_type,
            "deterministic_domain_type": self.deterministic_domain_type,
            "deterministic_confidence_before": round(self.deterministic_confidence_before, 4),
            "helper_called": self.helper_called,
            "helper_valid": self.helper_valid,
            "helper_rejected_reason": self.helper_rejected_reason,
            "helper_likely_domain": self.hint.normalized_domain if self.hint else None,
            "helper_answer_intent": self.hint.normalized_answer_intent if self.hint else None,
            "helper_raw_answer_intent": self.hint.answer_intent if self.hint else None,
            "helper_route_suggestion": self.hint.internal_route_suggestion if self.hint else None,
            "helper_raw_route_suggestion": self.hint.route_suggestion if self.hint else None,
            "helper_confidence": round(self.hint.confidence, 4) if self.hint else None,
            "would_change_route": self.would_change_route,
            "would_change_domain": self.would_change_domain,
            "would_change_intent": self.would_change_intent,
            "hint_applied": self.hint_applied,
            "hint_application_mode": self.hint_application_mode,
            "applied_to_runtime": self.applied_to_runtime,
            "final_runtime_confidence": round(self.final_runtime_confidence, 4),
            "sdk_path_used": self.sdk_path_used,
            "llm_client_path_used": self.llm_client_path_used,
            "provider": self.provider,
            "model": self.model,
            "backend_type": self.backend_type,
            "transport": self.transport,
        }
        if self.hint:
            payload["candidate_tables"] = self.hint.candidate_tables
            payload["candidate_api_families"] = self.hint.candidate_api_families
            payload["candidate_api_ids"] = self.hint.candidate_api_ids
            payload["synonym_mappings"] = self.hint.synonym_mappings[:5]
            payload["normalization_actions"] = self.hint.normalization_actions
        safe = redact_secrets(payload)
        return safe if isinstance(safe, dict) else payload


def normalize_route_suggestion(value: Any) -> str:
    route = str(value or "UNKNOWN").strip().upper()
    return HELPER_ROUTE_ALIASES.get(route, "UNKNOWN")


def normalize_answer_intent(value: Any) -> str:
    intent = str(value or "UNKNOWN").strip().upper()
    return HELPER_INTENT_ALIASES.get(intent, "UNKNOWN")


def normalize_helper_domain(value: Any) -> tuple[str, str | None]:
    normalized, internal, _actions = _normalize_helper_domain_with_actions(value)
    return normalized, internal


def _normalize_helper_domain_with_actions(value: Any) -> tuple[str, str | None, list[str]]:
    domain = str(value or "unknown").strip().lower()
    actions: list[str] = []
    if domain in HELPER_DOMAIN_VALUE_ALIASES:
        original = domain
        domain = HELPER_DOMAIN_VALUE_ALIASES[domain]
        actions.append(f"domain_alias:{original}->observability")
    if domain not in ALLOWED_HELPER_DOMAINS:
        return domain, None, actions
    internal = HELPER_DOMAIN_ALIASES.get(domain)
    return domain, internal if internal in DOMAIN_TYPES else None, actions


def compute_semantic_router_eligibility(
    *,
    query: str,
    routing: RoutingDecision,
    analysis: QueryAnalysis,
    config: Config | None = None,
) -> dict[str, Any]:
    cfg = config or DEFAULT_CONFIG
    reasons: list[str] = []
    if float(routing.confidence) < cfg.llm_semantic_router_confidence_threshold:
        reasons.append("low_confidence")
    if routing.domain_type == "UNKNOWN":
        reasons.append("unknown_domain")
    lowered = query.lower()
    if any(phrase in lowered for phrase in AMBIGUOUS_PHRASES):
        reasons.append("ambiguous_phrase")
    if _close_scores([item.score for item in analysis.relevance.tables[:2]], cfg.llm_semantic_router_ambiguity_margin):
        reasons.append("close_table_candidates")
    if _close_scores([item.score for item in analysis.relevance.apis[:2]], cfg.llm_semantic_router_ambiguity_margin):
        reasons.append("close_api_candidates")
    if not analysis.relevance.tables and not routing.candidate_tables:
        reasons.append("weak_schema_relevance")
    return {"eligible": bool(reasons), "reasons": reasons}


def build_semantic_routing_messages(
    *,
    user_prompt: str,
    normalized_query: str,
    matching_text: str,
    routing: RoutingDecision,
    analysis: QueryAnalysis,
    tokens: QueryTokens,
    schema_index: SchemaIndex,
    endpoint_catalog: EndpointCatalog,
) -> list[dict[str, str]]:
    context = {
        "user_prompt": user_prompt,
        "normalized_query": normalized_query,
        "matching_text": matching_text,
        "deterministic_routing": {
            "route_type": routing.route_type,
            "domain_type": routing.domain_type,
            "confidence": round(float(routing.confidence), 4),
            "candidate_tables": routing.candidate_tables[:8],
            "candidate_api_ids": [api.get("id") for api in routing.candidate_apis[:5] if isinstance(api, dict)],
        },
        "query_analysis": {
            "route_type": analysis.route_type,
            "domain_type": analysis.domain_type,
            "answer_family": analysis.answer_family,
            "confidence": round(float(analysis.confidence), 4),
        },
        "tokens": tokens.compact(),
        "top_schema_candidates": [{"table": item.name, "score": round(item.score, 4)} for item in analysis.relevance.tables[:6]],
        "top_api_candidates": [{"api": item.name, "score": round(item.score, 4)} for item in analysis.relevance.apis[:6]],
        "known_domains": sorted(ALLOWED_HELPER_DOMAINS),
        "known_answer_intents": sorted(HELPER_INTENT_ALIASES),
        "allowed_route_types": sorted(HELPER_ROUTE_ALIASES),
        "known_tables": sorted(schema_index.tables)[:80],
        "known_api_ids": [endpoint.id for endpoint in endpoint_catalog.endpoints],
        "known_api_paths": [endpoint.path for endpoint in endpoint_catalog.endpoints],
        "known_synonyms": {
            "schemas": ["schema_dataset", "blueprint", "dim_blueprint"],
            "audiences": ["segment_audience", "segment"],
            "targets": ["destination_dataflow", "destination"],
            "broken": ["STATUS", "failed", "error"],
            "recent": ["WHEN", "updated", "latest"],
        },
    }
    populated_example = {
        "likely_domain": "schema_dataset",
        "answer_intent": "COUNT",
        "route_suggestion": "SQL_ONLY",
        "synonym_mappings": [
            {
                "user_phrase": "data models",
                "mapped_to": "schemas",
                "target_domain": "schema_dataset",
                "reason": "data models is semantically close to schemas/blueprints",
            }
        ],
        "candidate_tables": ["dim_blueprint"],
        "candidate_api_families": [],
        "needs_api": False,
        "confidence": 0.72,
        "reason": "The prompt asks for schema-like data objects.",
    }
    empty_example = {
        "likely_domain": "unknown",
        "answer_intent": "UNKNOWN",
        "route_suggestion": "UNKNOWN",
        "synonym_mappings": [],
        "candidate_tables": [],
        "candidate_api_families": [],
        "needs_api": False,
        "confidence": 0.0,
        "reason": "No safe routing hint.",
    }
    system = (
        "You are a semantic routing helper for a deterministic DASHSys agent. "
        "Return one JSON object only. No markdown. No prose. No final answer. "
        "Do not include SQL results, API results, final-answer text, gold labels, public example IDs, or actual data values. "
        "Only suggest routing/domain/intent/synonym hints that must still be validated."
    )
    user = (
        "Return one JSON object with exactly these keys: likely_domain, answer_intent, route_suggestion, "
        "synonym_mappings, candidate_tables, candidate_api_families, needs_api, confidence, reason.\n"
        "Schema rules:\n"
        "- synonym_mappings must always be an array. If there are no synonym mappings, output \"synonym_mappings\": [].\n"
        "- candidate_tables must always be an array.\n"
        "- candidate_api_families must always be an array.\n"
        "- confidence must be a number between 0 and 1.\n"
        "- Domain must be one of the allowed domains.\n"
        "- Route must be one of the allowed routes.\n"
        "- Answer intent must be one of the allowed intents.\n"
        "Populated example:\n"
        f"{json.dumps(populated_example, indent=2, sort_keys=True)}\n"
        "Empty synonym example:\n"
        f"{json.dumps(empty_example, indent=2, sort_keys=True)}\n"
        f"Safe routing context:\n{json.dumps(context, indent=2, sort_keys=True, default=str)}"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def run_semantic_routing_helper(
    *,
    user_prompt: str,
    normalization: dict[str, Any],
    tokens: QueryTokens,
    routing: RoutingDecision,
    analysis: QueryAnalysis,
    schema_index: SchemaIndex,
    endpoint_catalog: EndpointCatalog,
    config: Config | None = None,
) -> SemanticRoutingResult:
    cfg = config or DEFAULT_CONFIG
    eligibility = compute_semantic_router_eligibility(query=user_prompt, routing=routing, analysis=analysis, config=cfg)
    base = SemanticRoutingResult(
        enabled=cfg.enable_llm_semantic_router,
        shadow_only=cfg.llm_semantic_router_shadow_only,
        eligibility_reason=list(eligibility.get("reasons") or []),
        deterministic_route_type=routing.route_type,
        deterministic_domain_type=routing.domain_type,
        deterministic_confidence_before=float(routing.confidence),
        final_runtime_confidence=float(analysis.confidence),
        hint_application_mode="shadow_only" if cfg.enable_llm_semantic_router and cfg.llm_semantic_router_shadow_only else "disabled",
    )
    if not cfg.enable_llm_semantic_router or not eligibility.get("eligible"):
        return base

    client = get_llm_client()
    provider = client.provider_name()
    model = client.model_name()
    if not client.available():
        probe = client.generate_messages([])
        return replace(
            base,
            helper_called=False,
            helper_rejected_reason=str(probe.get("reason") or "LLM provider unavailable"),
            provider=provider,
            model=model,
            backend_type=probe.get("backend_type"),
            transport=probe.get("transport"),
            sdk_path_used=bool(probe.get("sdk_path_used")),
        )

    messages = build_semantic_routing_messages(
        user_prompt=user_prompt,
        normalized_query=str(normalization.get("normalized") or user_prompt),
        matching_text=str(normalization.get("matching_text") or ""),
        routing=routing,
        analysis=analysis,
        tokens=tokens,
        schema_index=schema_index,
        endpoint_catalog=endpoint_catalog,
    )
    with _temporary_llm_max_tokens(cfg.llm_semantic_router_max_tokens):
        response = client.generate_messages(messages, tools=None, tool_choice=None)
    provider = str(response.get("provider") or provider)
    model = str(response.get("model") or model)
    if not response.get("ok"):
        return replace(
            base,
            helper_called=True,
            helper_rejected_reason=str(response.get("error") or response.get("reason") or "LLM helper request failed")[:300],
            provider=provider,
            model=model,
            backend_type=response.get("backend_type"),
            transport=response.get("transport"),
            sdk_path_used=bool(response.get("sdk_path_used")),
        )

    raw_payload, parse_error = _parse_json_object(str(response.get("content") or ""))
    if parse_error or not isinstance(raw_payload, dict):
        return replace(
            base,
            helper_called=True,
            helper_rejected_reason=parse_error or "LLM helper did not return a JSON object",
            provider=provider,
            model=model,
            backend_type=response.get("backend_type"),
            transport=response.get("transport"),
            sdk_path_used=bool(response.get("sdk_path_used")),
        )

    hint, reject_reason = validate_semantic_routing_hint(
        raw_payload,
        user_prompt=user_prompt,
        schema_index=schema_index,
        endpoint_catalog=endpoint_catalog,
    )
    if not hint:
        return replace(
            base,
            helper_called=True,
            helper_rejected_reason=reject_reason,
            provider=provider,
            model=model,
            backend_type=response.get("backend_type"),
            transport=response.get("transport"),
            sdk_path_used=bool(response.get("sdk_path_used")),
        )

    would_change_route = hint.internal_route_suggestion != "UNKNOWN" and hint.internal_route_suggestion != routing.route_type
    would_change_domain = bool(hint.internal_domain_type and hint.internal_domain_type != routing.domain_type)
    would_change_intent = _intent_changed(analysis.answer_family, hint.normalized_answer_intent)
    return replace(
        base,
        helper_called=True,
        helper_valid=True,
        helper_rejected_reason=None,
        hint=hint,
        would_change_route=would_change_route,
        would_change_domain=would_change_domain,
        would_change_intent=would_change_intent,
        provider=provider,
        model=model,
        backend_type=response.get("backend_type"),
        transport=response.get("transport"),
        sdk_path_used=bool(response.get("sdk_path_used")),
    )


def validate_semantic_routing_hint(
    raw: dict[str, Any],
    *,
    user_prompt: str,
    schema_index: SchemaIndex,
    endpoint_catalog: EndpointCatalog,
) -> tuple[SemanticRoutingHint | None, str | None]:
    forbidden_keys = {"final_answer", "answer", "sql_result", "api_result", "result_rows", "gold_sql", "gold_api"}
    if any(key in raw for key in forbidden_keys):
        return None, "helper_output_contains_forbidden_answer_or_result_key"
    text = json.dumps(raw, sort_keys=True, default=str)
    if SECRET_RE.search(text):
        return None, "helper_output_contains_secret_like_string"
    if QUERY_ID_RE.search(text) or "gold label" in text.lower() or "public example" in text.lower():
        return None, "helper_output_mentions_query_id_or_gold_example"
    if FINAL_ANSWER_LANGUAGE_RE.search(text):
        return None, "helper_output_contains_final_answer_language"
    if _contains_unsafe_numeric_claim(text, user_prompt):
        return None, "helper_output_contains_unsafe_numeric_answer_claim"

    normalized_domain, internal_domain, domain_actions = _normalize_helper_domain_with_actions(raw.get("likely_domain"))
    if normalized_domain not in ALLOWED_HELPER_DOMAINS:
        return None, f"unknown_domain:{normalized_domain}"
    raw_route = str(raw.get("route_suggestion") or "UNKNOWN").strip().upper()
    internal_route = normalize_route_suggestion(raw_route)
    if internal_route not in ROUTE_TYPES and internal_route != "UNKNOWN":
        return None, f"unknown_route:{raw_route}"
    raw_intent = str(raw.get("answer_intent") or "UNKNOWN").strip().upper()
    normalized_intent = normalize_answer_intent(raw_intent)
    valid_intents = {intent.value for intent in AnswerIntent} | {"UNKNOWN"}
    if normalized_intent not in valid_intents:
        return None, f"unknown_answer_intent:{raw_intent}"

    candidate_tables = _normalize_candidate_tables(raw.get("candidate_tables"), schema_index)
    if candidate_tables is None:
        return None, "unknown_table_in_candidate_tables"
    api_labels = _known_api_labels(endpoint_catalog)
    candidate_api_families, candidate_api_ids, api_error = _normalize_candidate_apis(
        raw.get("candidate_api_families"),
        endpoint_catalog,
        api_labels,
    )
    if api_error:
        return None, api_error
    synonym_mappings, synonym_actions, synonym_error = _normalize_synonym_mappings(
        raw.get("synonym_mappings", MISSING),
        schema_index,
        api_labels,
    )
    if synonym_error:
        return None, synonym_error
    try:
        confidence = float(raw.get("confidence", 0.0))
    except (TypeError, ValueError):
        return None, "confidence_not_numeric"
    if confidence < 0.0 or confidence > 1.0:
        return None, "confidence_out_of_range"

    hint = SemanticRoutingHint(
        likely_domain=str(raw.get("likely_domain") or "unknown"),
        normalized_domain=normalized_domain,
        internal_domain_type=internal_domain,
        answer_intent=raw_intent,
        normalized_answer_intent=normalized_intent,
        route_suggestion=raw_route,
        internal_route_suggestion=internal_route,
        synonym_mappings=synonym_mappings,
        candidate_tables=candidate_tables,
        candidate_api_families=candidate_api_families,
        candidate_api_ids=candidate_api_ids,
        needs_api=bool(raw.get("needs_api", False)),
        confidence=confidence,
        reason=str(raw.get("reason") or "")[:240],
        normalization_actions=[*domain_actions, *synonym_actions],
        raw=redact_secrets(raw) if isinstance(redact_secrets(raw), dict) else {},
    )
    return hint, None


def apply_semantic_routing_hint(
    *,
    routing: RoutingDecision,
    analysis: QueryAnalysis,
    result: SemanticRoutingResult,
    config: Config | None = None,
    endpoint_catalog: EndpointCatalog | None = None,
) -> tuple[RoutingDecision, QueryAnalysis, SemanticRoutingResult]:
    cfg = config or DEFAULT_CONFIG
    hint = result.hint
    if cfg.llm_semantic_router_shadow_only or not hint or not result.helper_valid:
        return routing, analysis, result.with_application(applied=False, final_runtime_confidence=float(analysis.confidence))
    low_confidence = float(routing.confidence) < cfg.llm_semantic_router_confidence_threshold or routing.domain_type == "UNKNOWN"
    if not low_confidence:
        return routing, analysis, result.with_application(applied=False, final_runtime_confidence=float(analysis.confidence))

    route_type = routing.route_type
    if hint.internal_route_suggestion != "UNKNOWN":
        route_type = hint.internal_route_suggestion
    domain_type = routing.domain_type
    if hint.internal_domain_type:
        domain_type = hint.internal_domain_type
    candidate_tables = _dedupe([*hint.candidate_tables, *routing.candidate_tables])
    candidate_apis = list(routing.candidate_apis)
    if endpoint_catalog is not None and hint.candidate_api_ids:
        by_id = {api.get("id"): api for api in candidate_apis if isinstance(api, dict)}
        for api_id in hint.candidate_api_ids:
            endpoint = endpoint_catalog.by_id(api_id)
            if endpoint and endpoint.id not in by_id:
                candidate_apis.insert(0, endpoint.to_dict())
                by_id[endpoint.id] = endpoint.to_dict()
    confidence = max(float(routing.confidence), float(hint.confidence))
    effective_routing = RoutingDecision(
        route_type=route_type,
        domain_type=domain_type,
        confidence=confidence,
        reason=f"{routing.reason} LLM semantic hint applied in isolated non-shadow mode.",
        candidate_tables=candidate_tables,
        candidate_apis=candidate_apis,
    )
    effective_analysis = replace(
        analysis,
        route_type=route_type,
        domain_type=domain_type,
        confidence=max(float(analysis.confidence), confidence),
    )
    return effective_routing, effective_analysis, result.with_application(
        applied=True,
        final_runtime_confidence=float(effective_analysis.confidence),
    )


def _normalize_candidate_tables(raw: Any, schema_index: SchemaIndex) -> list[str] | None:
    if raw in (None, ""):
        return []
    if not isinstance(raw, list):
        return None
    by_lower = {table.lower(): table for table in schema_index.tables}
    normalized: list[str] = []
    for item in raw:
        table = str(item or "").strip()
        if not table:
            continue
        actual = by_lower.get(table.lower())
        if not actual:
            return None
        normalized.append(actual)
    return _dedupe(normalized)


def _normalize_candidate_apis(
    raw: Any,
    endpoint_catalog: EndpointCatalog,
    api_labels: dict[str, set[str]],
) -> tuple[list[str], list[str], str | None]:
    if raw in (None, ""):
        return [], [], None
    if not isinstance(raw, list):
        return [], [], "candidate_api_families_not_list"
    labels: list[str] = []
    ids: list[str] = []
    for item in raw:
        label = str(item or "").strip()
        if not label:
            continue
        key = _api_label_key(label)
        matched = api_labels.get(key)
        if not matched:
            return [], [], f"unknown_api_family:{label}"
        labels.append(label)
        ids.extend(sorted(matched))
    return _dedupe(labels), _dedupe(ids), None


def _normalize_synonym_mappings(
    raw: Any,
    schema_index: SchemaIndex,
    api_labels: dict[str, set[str]],
) -> tuple[list[dict[str, str]], list[str], str | None]:
    actions: list[str] = []
    if raw is MISSING:
        return [], ["synonym_mappings_missing_to_empty"], None
    if raw is None:
        return [], ["synonym_mappings_null_to_empty"], None
    if isinstance(raw, str):
        return [], actions, "synonym_mappings_string_not_allowed"
    if isinstance(raw, dict):
        if any(key in raw for key in SYNONYM_MAPPING_KEYS):
            raw = [raw]
            actions.append("synonym_mappings_object_wrapped")
        else:
            coerced: list[dict[str, str]] = []
            for phrase, mapped_to in raw.items():
                coerced.append(
                    {
                        "user_phrase": str(phrase),
                        "mapped_to": str(mapped_to),
                        "target_domain": "unknown",
                        "reason": "Coerced from simple mapping object.",
                    }
                )
            raw = coerced
            actions.append("synonym_mappings_simple_object_coerced")
    if not isinstance(raw, list):
        return [], actions, "synonym_mappings_not_list"
    known = set(ALLOWED_HELPER_DOMAINS)
    known.update(table.lower() for table in schema_index.tables)
    known.update(api_labels.keys())
    known.update(SAFE_SYNONYM_WORDS)
    normalized: list[dict[str, str]] = []
    for item in raw[:12]:
        if not isinstance(item, dict):
            return [], actions, "synonym_mapping_not_object"
        mapped_to = str(item.get("mapped_to") or "").strip()
        target_domain = str(item.get("target_domain") or "unknown").strip().lower()
        target_domain = HELPER_DOMAIN_VALUE_ALIASES.get(target_domain, target_domain)
        if target_domain and target_domain not in ALLOWED_HELPER_DOMAINS:
            return [], actions, f"unknown_synonym_target_domain:{target_domain}"
        if mapped_to and _api_label_key(mapped_to) not in known:
            return [], actions, f"unknown_synonym_mapping:{mapped_to}"
        normalized.append(
            {
                "user_phrase": str(item.get("user_phrase") or "")[:80],
                "mapped_to": mapped_to[:80],
                "target_domain": target_domain,
                "reason": str(item.get("reason") or "")[:160],
            }
        )
    return normalized, actions, None


def _known_api_labels(endpoint_catalog: EndpointCatalog) -> dict[str, set[str]]:
    labels: dict[str, set[str]] = {}
    for endpoint in endpoint_catalog.endpoints:
        values = {
            endpoint.id,
            endpoint.path,
            f"{endpoint.method.upper()} {endpoint.path}",
            normalize_api_path(endpoint.path),
        }
        values.update(domain.lower() for domain in endpoint.domains)
        for value in values:
            labels.setdefault(_api_label_key(value), set()).add(endpoint.id)
    for family, endpoint_ids in API_FAMILY_HINTS.items():
        labels.setdefault(_api_label_key(family), set()).update(endpoint_ids)
    return labels


def _api_label_key(value: str) -> str:
    value = value.strip()
    if "/" in value:
        parts = value.split(maxsplit=1)
        if len(parts) == 2 and parts[0].upper() in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
            return f"{parts[0].upper()} {normalize_api_path(parts[1])}".lower()
        return normalize_api_path(value).lower()
    return re.sub(r"[^a-z0-9_]+", "_", value.lower()).strip("_")


def _contains_unsafe_numeric_claim(text: str, user_prompt: str) -> bool:
    if not ANSWER_NUMERIC_CLAIM_RE.search(text):
        return False
    allowed_numbers = set(re.findall(r"\d+", user_prompt))
    for match in re.finditer(r"\b\d+(?:\.\d+)?\b", text):
        value = match.group(0)
        start = max(0, match.start() - 48)
        end = min(len(text), match.end() + 48)
        context = text[start:end]
        if value in allowed_numbers or DATE_RE.search(context) or UUID_RE.search(context):
            continue
        if re.search(r"(you have|there (?:are|is)|count is|answer is|result is|means)\D{0,20}" + re.escape(value), context, re.I):
            return True
    return False


def _parse_json_object(content: str) -> tuple[dict[str, Any] | None, str | None]:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```$", "", text)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            return None, f"json_parse_error:{exc.msg}"
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError as inner:
            return None, f"json_parse_error:{inner.msg}"
    if not isinstance(payload, dict):
        return None, "json_payload_not_object"
    return payload, None


def _close_scores(scores: list[float], margin: float) -> bool:
    if len(scores) < 2:
        return False
    top, second = float(scores[0]), float(scores[1])
    return top > 0 and second > 0 and abs(top - second) <= margin


def _intent_changed(answer_family: str, normalized_intent: str) -> bool:
    if normalized_intent == "UNKNOWN":
        return False
    family = answer_family.lower()
    if normalized_intent == "COUNT":
        return "count" not in family and family not in {"schema_dataset", "merge_policy", "batch", "tags"}
    if normalized_intent == "WHEN":
        return not any(token in family for token in ["date", "time", "audit", "recent"])
    if normalized_intent == "YES_NO":
        return not any(token in family for token in ["status", "published", "inactive"])
    if normalized_intent == "LIST":
        return not any(token in family for token in ["list", "destination", "journey", "segment", "tags"])
    return False


def _dedupe(values: list[str]) -> list[str]:
    seen = set()
    deduped = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


@contextmanager
def _temporary_llm_max_tokens(max_tokens: int):
    previous = os.environ.get("LLM_MAX_TOKENS")
    os.environ["LLM_MAX_TOKENS"] = str(max(1, int(max_tokens)))
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("LLM_MAX_TOKENS", None)
        else:
            os.environ["LLM_MAX_TOKENS"] = previous
