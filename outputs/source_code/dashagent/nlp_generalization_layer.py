from __future__ import annotations

import re
from typing import Any


DOMAIN_TERMS = {
    "JOURNEY": ("journey", "journeys", "campaign", "campaigns"),
    "SEGMENT": ("audience", "audiences", "segment", "segments"),
    "DATASET": ("dataset", "datasets", "collection", "collections"),
    "SCHEMA": ("schema", "schemas", "blueprint", "blueprints"),
    "DESTINATION": ("destination", "destinations", "target", "targets"),
    "CONNECTOR": ("connector", "connectors", "source", "sources", "flow", "flows", "dataflow", "dataflows"),
    "FIELD": ("field", "fields", "property", "properties"),
    "TAG": ("tag", "tags", "category", "categories"),
    "AUDIT": ("audit", "event", "events", "log", "logs"),
}

INTENT_TERMS = {
    "COUNT": ("how many", "number of", "count", "total"),
    "LIST": ("list", "show", "give", "export", "which", "names", "ids"),
    "DATE": ("when", "date", "published", "deployed", "launched", "released", "created", "updated", "modified"),
    "STATUS": ("status", "state", "active", "inactive", "failed", "succeeded"),
    "RELATIONSHIP": ("connected", "linked", "mapped", "associated", "related", "relationship"),
}


def normalize_prompt_semantics(prompt: str) -> dict[str, Any]:
    text = str(prompt or "")
    lowered = text.lower()
    intent = _intent(lowered)
    domain = _domain(lowered)
    quoted = _quoted_values(text)
    status_terms = _status_terms(lowered)
    date_terms = _date_terms(lowered)
    filters: list[dict[str, Any]] = []
    for value in quoted:
        filters.append({"semantic_field": "name", "operator": "equals", "value": value, "value_source": "quoted_entity"})
    for status in status_terms:
        filters.append({"semantic_field": "status", "operator": "equals", "value": status, "value_source": "status_term"})
    return {
        "original_prompt": text,
        "canonical_intent": intent,
        "canonical_domain": domain,
        "canonical_entities": quoted,
        "quoted_entities": quoted,
        "canonical_filters": filters,
        "status_terms": status_terms,
        "date_terms": date_terms,
        "timestamp_semantics": _timestamp_semantics(lowered),
        "canonical_representation": {
            "intent": intent,
            "domain": domain,
            "entities": quoted,
            "filters": filters,
        },
    }


def domain_to_table(domain: str) -> str | None:
    return {
        "JOURNEY": "dim_campaign",
        "SEGMENT": "dim_segment",
        "DATASET": "dim_collection",
        "SCHEMA": "dim_blueprint",
        "DESTINATION": "dim_target",
        "CONNECTOR": "dim_connector",
    }.get(str(domain or "").upper())


def timestamp_semantic_markers(kind: str | None) -> tuple[str, ...]:
    if kind == "published":
        return ("deployed", "published", "launch", "release")
    if kind == "updated":
        return ("updated", "modified")
    if kind == "created":
        return ("created",)
    return ("time", "date", "created", "updated", "deployed", "published")


def _intent(lowered: str) -> str:
    for intent, terms in INTENT_TERMS.items():
        if any(term in lowered for term in terms):
            return intent
    if "?" in lowered:
        return "DETAIL"
    return "UNKNOWN"


def _domain(lowered: str) -> str:
    for domain, terms in DOMAIN_TERMS.items():
        if any(re.search(rf"\b{re.escape(term)}\b", lowered) for term in terms):
            return domain
    return "UNKNOWN"


def _timestamp_semantics(lowered: str) -> str | None:
    if any(term in lowered for term in ("published", "deployed", "launched", "released")):
        return "published"
    if any(term in lowered for term in ("updated", "modified", "recent")):
        return "updated"
    if any(term in lowered for term in ("created", "new")):
        return "created"
    return None


def _quoted_values(text: str) -> list[str]:
    return [match.group(1) or match.group(2) for match in re.finditer(r"'([^']+)'|\"([^\"]+)\"", text)]


def _status_terms(lowered: str) -> list[str]:
    return [term for term in ("active", "inactive", "failed", "succeeded", "published") if re.search(rf"\b{term}\b", lowered)]


def _date_terms(lowered: str) -> list[str]:
    return [term for term in ("published", "deployed", "launched", "released", "created", "updated", "modified", "recent") if term in lowered]
