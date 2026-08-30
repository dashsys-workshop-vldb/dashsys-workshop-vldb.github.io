from __future__ import annotations

import json
from typing import Any

from .prompt_semantic_ir import ObjectivePromptFeatures


CAPABILITY_REGISTRY: dict[str, dict[str, list[str]]] = {
    "SCHEMA": {"no_tool": ["definition", "concept"], "sql": ["local rows", "counts"], "api": ["schema registry"]},
    "SEGMENT": {"no_tool": ["definition", "concept"], "sql": ["local segment rows"], "api": ["segment definitions"]},
    "AUDIENCE": {"no_tool": ["definition", "concept"], "sql": ["local audience rows"], "api": ["ups audiences"]},
    "DATASET": {"no_tool": ["definition", "concept"], "sql": ["local dataset rows"], "api": ["catalog datasets"]},
    "JOURNEY": {"no_tool": ["definition", "concept"], "sql": ["local campaign rows"], "api": ["journey list"]},
    "CAMPAIGN": {"no_tool": ["definition", "concept"], "sql": ["local campaign rows"], "api": ["journey list"]},
    "TAG": {"no_tool": ["definition", "concept"], "sql": [], "api": ["unified tags"]},
    "AUDIT": {"no_tool": ["definition", "concept"], "sql": [], "api": ["audit events"]},
    "MERGE_POLICY": {"no_tool": ["definition", "concept"], "sql": [], "api": ["merge policies"]},
    "DATAFLOW": {"no_tool": ["definition", "concept"], "sql": ["local flow rows"], "api": ["flow service"]},
    "FLOW": {"no_tool": ["definition", "concept"], "sql": ["local flow rows"], "api": ["flow service"]},
    "BATCH": {"no_tool": ["definition", "concept"], "sql": [], "api": ["catalog batches"]},
    "DESTINATION": {"no_tool": ["definition", "concept"], "sql": ["local targets"], "api": ["flow service"]},
    "CONNECTOR": {"no_tool": ["definition", "concept"], "sql": ["local connectors"], "api": ["flow service"]},
    "FIELD": {"no_tool": ["definition", "concept"], "sql": ["local fields"], "api": []},
}

GENERIC_ROUTING_EXAMPLES = [
    {"p": "What is a schema?", "intent": "CONCEPT", "need": "NONE"},
    {"p": "List schemas", "intent": "DATA", "need": "SQL"},
    {"p": "Explain merge policy and list current merge policies", "intent": "MIXED", "need": "API"},
]


def build_semantic_intent_context(
    features: ObjectivePromptFeatures | dict[str, Any],
    *,
    tier: int = 0,
    token_budget: int = 700,
    top_k_capability_families: int = 3,
) -> dict[str, Any]:
    payload = features.to_dict() if isinstance(features, ObjectivePromptFeatures) else dict(features)
    selected_domains = _rank_domains(payload)[: max(0, top_k_capability_families)]
    caps = {domain: CAPABILITY_REGISTRY[domain] for domain in selected_domains if domain in CAPABILITY_REGISTRY}
    context: dict[str, Any] = {
        "task": "SEMANTIC_INTENT_DECISION",
        "prompt": {
            "raw": payload.get("p", ""),
            "normalized": payload.get("norm", ""),
        },
        "features": {
            "conceptual_cues": payload.get("cue", []),
            "retrieval_cues": payload.get("retr", []),
            "count_cues": payload.get("count", []),
            "field_cues": payload.get("fields", []),
            "status_cues": payload.get("status", []),
            "date_cues": payload.get("date", []),
            "relationship_cues": payload.get("rel", []),
            "domain_terms": payload.get("domain", []),
            "entities": payload.get("entity", []),
            "capability_matches": payload.get("cap", []),
            "flags": payload.get("flags", []),
        },
        "capabilities": caps,
        "allowed_outputs": {
            "intent": ["CONCEPT", "DATA", "LIVE_API", "MIXED", "AMBIG", "UNSUPPORTED"],
            "need": ["NONE", "SQL", "API", "SQL_API", "UNKNOWN"],
        },
        "constraints": {
            "do_not_generate_sql": True,
            "do_not_generate_api_params": True,
            "do_not_answer_user": True,
        },
    }
    if tier >= 2:
        context["examples"] = GENERIC_ROUTING_EXAMPLES[:3]
    _enforce_budget(context, token_budget)
    return context


def estimate_context_tokens(context: dict[str, Any]) -> int:
    return max(1, len(json.dumps(context, sort_keys=True, separators=(",", ":"))) // 4)


def _compact_features(payload: dict[str, Any]) -> dict[str, Any]:
    forbidden = {"reason", "explanation", "final_route", "should_use_sql", "should_use_api", "should_skip_tools"}
    return {
        key: value
        for key, value in payload.items()
        if key not in forbidden and (key in {"p", "norm"} or value)
    }


def _rank_domains(payload: dict[str, Any]) -> list[str]:
    domains = list(payload.get("domain") or [])
    if domains:
        return domains
    caps = set(payload.get("cap") or [])
    ranked = [domain for domain in CAPABILITY_REGISTRY if any(cap.startswith(domain) for cap in caps)]
    return ranked or ["SCHEMA"]


def _enforce_budget(context: dict[str, Any], token_budget: int) -> None:
    if token_budget <= 0:
        return
    if estimate_context_tokens(context) <= token_budget:
        return
    context.pop("examples", None)
    while estimate_context_tokens(context) > token_budget and context.get("capabilities"):
        context["capabilities"].pop(next(reversed(context["capabilities"])))
    feature_order = ["capability_matches", "flags", "entities", "field_cues", "date_cues", "status_cues", "relationship_cues", "count_cues"]
    for key in feature_order:
        if estimate_context_tokens(context) <= token_budget:
            return
        if isinstance(context.get("features"), dict):
            context["features"].pop(key, None)
