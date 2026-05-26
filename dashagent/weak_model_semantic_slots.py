from __future__ import annotations

import json
from typing import Any

from .llm_client import LLMClient
from .llm_tool_agent_prompts import parse_json_object
from .nlp_generalization_layer import normalize_prompt_semantics
from .trajectory import redact_secrets


VALID_INTENTS = {"COUNT", "LIST", "STATUS", "DATE", "DETAIL", "RELATIONSHIP", "YES_NO", "UNKNOWN"}
VALID_DOMAINS = {"JOURNEY", "SEGMENT", "DATASET", "SCHEMA", "DESTINATION", "CONNECTOR", "FIELD", "TAG", "AUDIT", "UNKNOWN"}
VALID_EVIDENCE_NEEDS = {
    "sql_first",
    "api_first",
    "sql_then_api",
    "api_only",
    "sql_only",
    "api_then_sql",
    "sql_primary_api_verify",
    "api_primary_sql_context",
    "no_tool_needed",
    "unknown",
}
VALID_AGGREGATIONS = {"none", "count", "count_distinct", "max", "min"}


def build_semantic_slot_prompt(prompt: str, nlp_context: dict[str, Any]) -> tuple[str, str]:
    system = (
        "You are a weak-model semantic slot filler for DASHSys. Return JSON only. "
        "Do not write SQL. Do not choose URLs. Fill intent, domain, entity_terms, quoted_entities, "
        "filters, aggregation, relationship, evidence_need, confidence."
    )
    user = json.dumps({"prompt": prompt, "deterministic_nlp_context": nlp_context}, indent=2, default=str)
    return system, user


def weak_model_semantic_slots(prompt: str, llm_client: LLMClient | None = None) -> dict[str, Any]:
    nlp = normalize_prompt_semantics(prompt)
    parsed: dict[str, Any] = {}
    usage: dict[str, Any] = {}
    if llm_client is not None and llm_client.available():
        system, user = build_semantic_slot_prompt(prompt, nlp)
        response = llm_client.generate(system, user)
        parsed = parse_json_object(response.get("content", ""))
        usage = response.get("usage", {}) if isinstance(response.get("usage"), dict) else {}
    slots = normalize_semantic_slots(parsed, prompt=prompt)
    slots["_usage"] = usage
    slots["_source"] = "weak_llm_with_deterministic_normalization" if parsed else "deterministic_nlp_fallback"
    return redact_secrets(slots)


def normalize_semantic_slots(raw: dict[str, Any] | None, *, prompt: str) -> dict[str, Any]:
    nlp = normalize_prompt_semantics(prompt)
    raw = raw if isinstance(raw, dict) else {}
    intent = str(raw.get("intent") or nlp["canonical_intent"] or "UNKNOWN").upper()
    domain = str(raw.get("domain") or nlp["canonical_domain"] or "UNKNOWN").upper()
    evidence_need = str(raw.get("evidence_need") or _default_evidence_need(prompt, domain) or "unknown").lower()
    aggregation = str(raw.get("aggregation") or ("count" if intent == "COUNT" else "none")).lower()
    if intent not in VALID_INTENTS:
        intent = nlp["canonical_intent"]
    if domain not in VALID_DOMAINS:
        domain = nlp["canonical_domain"]
    if evidence_need not in VALID_EVIDENCE_NEEDS:
        evidence_need = _default_evidence_need(prompt, domain)
    if aggregation not in VALID_AGGREGATIONS:
        aggregation = "none"
    filters = _normalize_filters(raw.get("filters"), nlp["canonical_filters"])
    quoted = _string_list(raw.get("quoted_entities")) or list(nlp.get("quoted_entities") or [])
    entity_terms = _string_list(raw.get("entity_terms")) or quoted
    relationship = raw.get("relationship") if isinstance(raw.get("relationship"), dict) else {}
    return redact_secrets(
        {
            "intent": intent,
            "domain": domain,
            "entity_terms": entity_terms,
            "quoted_entities": quoted,
            "filters": filters,
            "aggregation": aggregation,
            "relationship": {
                "needed": bool(relationship.get("needed")) if relationship else intent == "RELATIONSHIP",
                "left_entity": str(relationship.get("left_entity") or "") if relationship else "",
                "right_entity": str(relationship.get("right_entity") or "") if relationship else "",
            },
            "evidence_need": evidence_need,
            "confidence": _confidence(raw.get("confidence")),
            "nlp_context": nlp,
        }
    )


def _default_evidence_need(prompt: str, domain: str) -> str:
    lowered = prompt.lower()
    if "api" in lowered or "live" in lowered or "platform" in lowered:
        return "api_first"
    if domain != "UNKNOWN":
        return "sql_first"
    return "unknown"


def classify_balanced_evidence_need(prompt: str, slots: dict[str, Any]) -> str:
    """Classify evidence need for shadow weak-model scaffolds.

    This is intentionally coarse and domain-family based. It is not a packaged
    router and does not use query IDs or gold labels.
    """
    lowered = str(prompt or "").lower()
    domain = str(slots.get("domain") or "").upper()
    intent = str(slots.get("intent") or "").upper()
    explicit_api = any(term in lowered for term in (" api", "live ", "platform", "current adobe", "adobe api"))
    explicit_local = any(term in lowered for term in ("local", "snapshot", "database", "db "))
    relationship = intent == "RELATIONSHIP" or any(term in lowered for term in ("connected", "linked", "mapped", "associated", "related"))
    if intent == "UNKNOWN" and domain == "UNKNOWN":
        return "unknown"
    if explicit_api:
        return "api_primary_sql_context" if domain != "UNKNOWN" else "api_only"
    if relationship:
        return "sql_then_api"
    if explicit_local:
        return "sql_only"
    if _domain_has_safe_api_family(domain, lowered):
        return "sql_primary_api_verify"
    if domain != "UNKNOWN":
        return "sql_only"
    return "unknown"


def _domain_has_safe_api_family(domain: str, lowered_prompt: str) -> bool:
    if domain in {"JOURNEY", "SEGMENT", "DATASET", "SCHEMA", "DESTINATION", "CONNECTOR", "TAG", "AUDIT"}:
        return True
    if "merge polic" in lowered_prompt or "batch" in lowered_prompt:
        return True
    return False


def _normalize_filters(raw_filters: Any, fallback: list[dict[str, Any]]) -> list[dict[str, Any]]:
    filters = raw_filters if isinstance(raw_filters, list) else fallback
    normalized = []
    for item in filters:
        if not isinstance(item, dict):
            continue
        semantic_field = str(item.get("semantic_field") or "name").lower()
        operator = str(item.get("operator") or "equals").lower()
        value = item.get("value")
        if semantic_field not in {"name", "status", "date", "id", "type"}:
            semantic_field = "name"
        if operator not in {"equals", "contains", "before", "after", "in"}:
            operator = "equals"
        if value is None or value == "":
            continue
        normalized.append({"semantic_field": semantic_field, "operator": operator, "value": str(value)})
    return normalized[:8]


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _confidence(value: Any) -> float:
    try:
        return round(min(1.0, max(0.0, float(value))), 4)
    except Exception:
        return 0.5
