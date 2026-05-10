from __future__ import annotations

from typing import Any

from .endpoint_catalog import EndpointCatalog
from .schema_index import SchemaIndex
from .trajectory import estimate_tokens


def vote_schema_contexts(
    *,
    query: str,
    compact_context: dict[str, Any],
    schema_index: SchemaIndex,
    endpoint_catalog: EndpointCatalog,
    risk_level: str,
) -> dict[str, Any]:
    """Compare compact candidate context with a broader context for diagnostics.

    The result is display/report guidance only. It must not change the SQL/API
    plan selected by SQL_FIRST_API_VERIFY.
    """

    if risk_level != "high":
        return {
            "active": False,
            "diagnostic_only": True,
            "behavior_changed": False,
            "reason": "schema voting is reserved for high-risk diagnostics",
            "schema_vote_agreement": None,
            "compact_context_safe": None,
        }
    fallback_context = _fallback_context(query, schema_index, endpoint_catalog, compact_context)
    compact_tables = _names(compact_context.get("candidate_tables"))
    compact_apis = _api_ids(compact_context.get("candidate_apis"))
    fallback_tables = _names(fallback_context.get("candidate_tables") or fallback_context.get("tables"))
    fallback_apis = _api_ids(fallback_context.get("candidate_apis") or fallback_context.get("apis"))
    table_agreement = _top_agreement(compact_tables, fallback_tables)
    api_agreement = _top_agreement(compact_apis, fallback_apis) or (not compact_apis and not fallback_apis)
    agreement = bool(table_agreement and api_agreement)
    compact_tokens = int(compact_context.get("estimated_tokens") or estimate_tokens(compact_context))
    fallback_tokens = int(fallback_context.get("estimated_tokens") or estimate_tokens(fallback_context))
    return {
        "active": True,
        "diagnostic_only": True,
        "behavior_changed": False,
        "schema_vote_agreement": agreement,
        "compact_context_safe": agreement,
        "fallback_reason": "compact and fallback top candidates agree" if agreement else "compact candidate context disagrees with broader schema/API context",
        "compact_candidate_tables": compact_tables[:8],
        "fallback_candidate_tables": fallback_tables[:8],
        "compact_candidate_apis": compact_apis[:8],
        "fallback_candidate_apis": fallback_apis[:8],
        "compact_context_tokens": compact_tokens,
        "fallback_context_tokens": fallback_tokens,
        "token_delta": fallback_tokens - compact_tokens,
        "query": query,
    }


def _fallback_context(
    query: str,
    schema_index: SchemaIndex,
    endpoint_catalog: EndpointCatalog,
    compact_context: dict[str, Any],
) -> dict[str, Any]:
    from .candidate_context_builder import build_candidate_context

    table_count = max(8, len(compact_context.get("candidate_tables") or []))
    api_count = max(8, len(compact_context.get("candidate_apis") or []))
    context = build_candidate_context(
        query,
        schema_index,
        endpoint_catalog,
        top_k_tables=table_count,
        top_k_columns=16,
        top_k_joins=12,
        top_k_apis=api_count,
        enable_hybrid_ranking=True,
        enable_endpoint_family_ranking=True,
        enable_structural_preservation=True,
        enable_value_to_api_ranking=True,
        enable_gated_risk_cluster_repair=True,
    )
    context["mode"] = "hybrid_full_context_diagnostic"
    return context


def _top_agreement(left: list[str], right: list[str]) -> bool:
    if not left or not right:
        return False
    left_top = _norm(left[0])
    right_top = _norm(right[0])
    if left_top == right_top:
        return True
    return bool({_norm(item) for item in left[:3]} & {_norm(item) for item in right[:3]})


def _names(value: Any) -> list[str]:
    if value in (None, "", {}, []):
        return []
    if isinstance(value, dict):
        if "items" in value:
            return _names(value.get("items"))
        if all(isinstance(item, dict) for item in value.values()):
            return list(value.keys())
        names: list[str] = []
        for item in value.values():
            names.extend(_names(item))
        return _dedupe(names)
    if isinstance(value, list):
        names: list[str] = []
        for item in value:
            names.extend(_names(item))
        return _dedupe(names)
    return [str(value)]


def _api_ids(value: Any) -> list[str]:
    if value in (None, "", {}, []):
        return []
    if isinstance(value, dict):
        if "items" in value:
            return _api_ids(value.get("items"))
        for key in ("id", "endpoint_id", "name", "path"):
            if value.get(key):
                return [str(value[key])]
        names: list[str] = []
        for item in value.values():
            names.extend(_api_ids(item))
        return _dedupe(names)
    if isinstance(value, list):
        names: list[str] = []
        for item in value:
            names.extend(_api_ids(item))
        return _dedupe(names)
    return [str(value)]


def _norm(value: str) -> str:
    return str(value or "").strip().lower()


def _dedupe(values: list[str]) -> list[str]:
    seen = set()
    output: list[str] = []
    for value in values:
        key = str(value)
        if key and key not in seen:
            seen.add(key)
            output.append(key)
    return output
