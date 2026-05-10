from __future__ import annotations

from typing import Any

from .candidate_ranker import rank_candidates
from .endpoint_family_ranker import endpoint_family_for_endpoint, rank_endpoint_candidates
from .endpoint_catalog import EndpointCatalog
from .query_normalizer import normalize_query
from .query_tokens import extract_query_tokens
from .relevance_scorer import RelevanceItem, score_relevance
from .schema_index import SchemaIndex
from .trajectory import estimate_tokens


IMPORTANT_COLUMN_TOKENS = ("id", "name", "status", "state", "time", "date", "count", "type")
SCHEMA_ALIASES = {
    "journey": {"tables": ["dim_campaign"], "source": "domain vocabulary alias"},
    "journeys": {"tables": ["dim_campaign"], "source": "domain vocabulary alias"},
    "campaign": {"tables": ["dim_campaign"], "source": "schema naming convention"},
    "destination": {"tables": ["dim_target"], "source": "domain vocabulary alias"},
    "destinations": {"tables": ["dim_target"], "source": "domain vocabulary alias"},
    "target": {"tables": ["dim_target"], "source": "schema naming convention"},
    "audience": {"tables": ["dim_segment"], "source": "domain vocabulary alias"},
    "audiences": {"tables": ["dim_segment"], "source": "domain vocabulary alias"},
    "segment": {"tables": ["dim_segment"], "source": "schema naming convention"},
    "schema": {"tables": ["dim_blueprint"], "source": "domain vocabulary alias"},
    "schemas": {"tables": ["dim_blueprint"], "source": "domain vocabulary alias"},
    "dataset": {"tables": ["dim_collection"], "source": "domain vocabulary alias"},
    "datasets": {"tables": ["dim_collection"], "source": "domain vocabulary alias"},
    "collection": {"tables": ["dim_collection"], "source": "domain vocabulary alias"},
    "collections": {"tables": ["dim_collection"], "source": "domain vocabulary alias"},
    "blueprint": {"tables": ["dim_blueprint"], "source": "schema registry vocabulary alias"},
    "blueprints": {"tables": ["dim_blueprint"], "source": "schema registry vocabulary alias"},
}


def build_full_schema_context(
    schema_index: SchemaIndex,
    endpoint_catalog: EndpointCatalog | None = None,
) -> dict[str, Any]:
    endpoints = endpoint_catalog.as_list() if endpoint_catalog else []
    return {
        "mode": "full_schema",
        "tables": {
            table: {
                "columns": [column["name"] for column in meta.get("columns", [])],
                "id_columns": meta.get("id_columns", []),
                "primary_like_id": meta.get("primary_like_id"),
                "is_bridge": meta.get("is_bridge", False),
            }
            for table, meta in schema_index.tables.items()
        },
        "join_hints": [hint.to_dict() for hint in schema_index.join_hints],
        "apis": [
            {
                "id": endpoint["id"],
                "method": endpoint["method"],
                "path": endpoint["path"],
                "use_when": endpoint.get("use_when", ""),
                "domains": endpoint.get("domains", []),
            }
            for endpoint in endpoints
        ],
        "used_gold_patterns": False,
    }


def build_candidate_context(
    query: str,
    schema_index: SchemaIndex,
    endpoint_catalog: EndpointCatalog,
    top_k_tables: int = 5,
    top_k_columns: int = 16,
    top_k_joins: int = 8,
    top_k_apis: int = 5,
    value_matches: list[Any] | None = None,
    enable_hybrid_ranking: bool = True,
    enable_endpoint_family_ranking: bool = True,
    enable_structural_preservation: bool = True,
    enable_value_to_api_ranking: bool = True,
    enable_gated_risk_cluster_repair: bool = True,
) -> dict[str, Any]:
    normalization = normalize_query(query)
    tokens = extract_query_tokens(query, normalization)
    relevance = score_relevance(query, schema_index, endpoint_catalog, tokens=tokens)
    forward_links = forward_schema_link(tokens, schema_index)
    backward_links = backward_schema_link(tokens, schema_index)
    table_items = _with_fallback_tables(relevance.tables, schema_index, top_k_tables)
    baseline_tables = [item.name for item in table_items[:top_k_tables]]
    linked_tables = combine_schema_links(forward_links, backward_links, {"candidate_tables": [item.name for item in table_items]})
    candidate_tables = _dedupe(baseline_tables + linked_tables.get("tables", []))[:top_k_tables]
    structural = preserve_structural_joins(candidate_tables, schema_index.join_hints) if enable_structural_preservation else {"added_bridge_tables": [], "join_hints": [], "missing_bridge_warning": False}
    relation_structural = preserve_structural_relations(tokens, candidate_tables, schema_index) if enable_structural_preservation else {"added_tables": [], "join_hints": [], "reason": None}
    structural_added = _dedupe(structural.get("added_bridge_tables", []) + relation_structural.get("added_tables", []))
    structural_hints = list(structural.get("join_hints", [])) + list(relation_structural.get("join_hints", []))
    candidate_tables = _dedupe(candidate_tables + structural_added)[: max(top_k_tables, len(candidate_tables) + len(structural_added))]
    table_ranking = _rank_tables_for_context(
        tokens,
        schema_index,
        relevance.tables,
        forward_links,
        backward_links,
        structural_added,
        value_matches or [],
        enable_hybrid_ranking=enable_hybrid_ranking,
    )
    if enable_hybrid_ranking and table_ranking.get("ranked_candidates"):
        ranked_tables = [row["name"] for row in table_ranking["ranked_candidates"]]
        candidate_tables = _dedupe(ranked_tables[:top_k_tables] + structural_added)[: max(top_k_tables, len(structural_added) + top_k_tables)]
    candidate_columns = {
        table: _candidate_columns(table, relevance.columns.get(table, []), schema_index, top_k_columns)
        for table in candidate_tables
    }
    join_hints = _candidate_joins(relevance.join_hints, top_k_joins)
    baseline_apis = _candidate_apis(relevance.apis, endpoint_catalog, top_k_apis)
    endpoint_ranking = rank_endpoint_candidates(
        tokens,
        endpoint_catalog.endpoints,
        relevance_items=relevance.apis,
        value_matches=(value_matches or []) if enable_value_to_api_ranking else [],
    ) if enable_hybrid_ranking and enable_endpoint_family_ranking else {}
    apis = _candidate_apis_from_ranked(endpoint_ranking.get("ranked_endpoints", []), top_k_apis) if endpoint_ranking else baseline_apis
    scores = {
        "tables": {
            row["name"]: round(float(row.get("weighted_score_fusion") or row.get("final_score") or 0.0), 4)
            for row in table_ranking.get("ranked_candidates", [])[:top_k_tables]
        } if table_ranking else {item.name: round(item.score, 4) for item in table_items[:top_k_tables]},
        "apis": {api["id"]: round(float(api.get("final_score") or api.get("score") or 0.0), 4) for api in apis[:top_k_apis]},
        "joins": {item.name: round(item.score, 4) for item in relevance.join_hints[:top_k_joins]},
    }
    top_scores = [
        float(row.get("weighted_score_fusion") or row.get("final_score") or 0.0)
        for row in table_ranking.get("ranked_candidates", [])[:2]
    ] if table_ranking else [item.score for item in table_items[:2]]
    top_score = top_scores[0] if top_scores else 0.0
    margin = (top_scores[0] - top_scores[1]) if len(top_scores) > 1 else top_score
    endpoint_confidence = float((endpoint_ranking.get("detected_family") or {}).get("endpoint_family_confidence") or 0.0)
    confidence = max(0.0, min(1.0, (top_score / 3.0) + min(max(margin, 0.0), 1.0) * 0.2 + endpoint_confidence * 0.12))
    notes = ["Candidate context is retrieval-only and not a hard SQL constraint."]
    schema_risk = schema_link_risk_score(
        forward_links=forward_links,
        backward_links=backward_links,
        structural=structural,
        confidence=confidence,
        margin=margin,
    )
    if confidence < 0.45 or margin < 0.15:
        notes.append("Low confidence or small score margin; full-schema fallback is preferred.")
    payload = {
        "query": query,
        "normalized_query": normalization.get("normalized"),
        "tokens": tokens.compact(),
        "candidate_tables": candidate_tables,
        "candidate_columns": candidate_columns,
        "candidate_join_hints": join_hints,
        "candidate_apis": apis,
        "scores": scores,
        "confidence": round(confidence, 4),
        "score_margin": round(margin, 4),
        "schema_linking": {
            "forward_link_count": forward_links["link_count"],
            "backward_link_count": backward_links["link_count"],
            "forward_links": forward_links["links"][:12],
            "backward_links": backward_links["links"][:12],
            "structural_join_preserved": bool(structural_added or structural_hints),
            "structural_joins": structural_hints,
            "structural_tables_added": structural_added,
            "structural_reason": relation_structural.get("reason") or ("bridge-table heuristic" if structural.get("added_bridge_tables") else None),
            "bridge_preserved": bool(structural_added or structural_hints),
            "structural_confidence_delta": 0.1 if structural_added else 0.0,
            "schema_link_confidence": schema_risk["schema_link_confidence"],
            "schema_link_risk": schema_risk["schema_link_risk"],
            "missing_bridge_warning": structural.get("missing_bridge_warning", False),
            "reason_for_context_mode": schema_risk["reason_for_context_mode"],
            "used_robust_schema_linking": True,
        },
        "hybrid_candidate_scoring": {
            "active": enable_hybrid_ranking,
            "fusion_mode": table_ranking.get("fusion_mode", "weighted_score_fusion") if table_ranking else "disabled",
            "top_candidate_score": table_ranking.get("top_candidate_score") if table_ranking else None,
            "score_margin": table_ranking.get("score_margin") if table_ranking else None,
            "ranking_changed": table_ranking.get("ranking_changed", False) if table_ranking else False,
            "top_components": _top_score_components(table_ranking.get("ranked_candidates", []) if table_ranking else []),
            "rank_before": (table_ranking.get("rank_before", baseline_tables) if table_ranking else baseline_tables)[:8],
            "rank_after": (table_ranking.get("rank_after", candidate_tables) if table_ranking else candidate_tables)[:8],
            "reciprocal_rank_fusion_scores": {
                row["name"]: row.get("reciprocal_rank_fusion")
                for row in table_ranking.get("ranked_candidates", [])[:top_k_tables]
            } if table_ranking else {},
        },
        "endpoint_family_ranking": {
            "active": bool(endpoint_ranking),
            **(endpoint_ranking.get("detected_family") or {}),
            "endpoint_rank_before": endpoint_ranking.get("endpoint_rank_before", [api.get("id") for api in baseline_apis])[:8],
            "endpoint_rank_after": endpoint_ranking.get("endpoint_rank_after", [api.get("id") for api in apis])[:8],
            "ranking_changed": endpoint_ranking.get("ranking_changed", False),
            "top_ranked_apis": [
                {
                    "id": row.get("id"),
                    "endpoint_family": row.get("endpoint_family"),
                    "final_score": row.get("final_score"),
                    "score_explanation": row.get("score_explanation"),
                }
                for row in endpoint_ranking.get("ranked_endpoints", [])[:top_k_apis]
            ],
        },
        "value_to_api_ranking": {
            "active": bool(enable_value_to_api_ranking and value_matches),
            "value_match_used_for_api_ranking": bool((endpoint_ranking.get("detected_family") or {}).get("value_match_used_for_api_ranking")),
            "value_match_confidence": (endpoint_ranking.get("detected_family") or {}).get("value_match_confidence"),
            "boosted_endpoint_family": (endpoint_ranking.get("detected_family") or {}).get("boosted_endpoint_family"),
            "boost_applied": bool((endpoint_ranking.get("detected_family") or {}).get("boost_applied")),
        },
        "gated_risk_cluster_repair": build_gated_risk_cluster_repair_diagnostic(
            confidence=confidence,
            margin=margin,
            endpoint_ranking=endpoint_ranking,
            baseline_apis=baseline_apis,
            reranked_apis=apis,
        ) if enable_gated_risk_cluster_repair else {"active": False, "diagnostic_only": True, "execution_repair_enabled": False},
        "ranking_diagnostics": {
            "ranking_report_only": True,
            "execution_repair_enabled": False,
            "baseline_candidate_tables": baseline_tables,
            "baseline_candidate_apis": baseline_apis,
            "baseline_score_margin": _baseline_margin(table_items),
            "baseline_confidence": _baseline_confidence(table_items),
            "reranked_candidate_tables": candidate_tables,
            "reranked_candidate_apis": apis,
        },
        "used_gold_patterns": False,
        "notes": notes,
    }
    payload["context_mode"] = choose_context_mode(payload)
    payload["estimated_tokens"] = estimate_tokens(payload)
    return payload


def forward_schema_link(query_tokens: Any, schema_index: SchemaIndex) -> dict[str, Any]:
    words = set(getattr(query_tokens, "words", []) or [])
    statuses = set(getattr(query_tokens, "statuses", []) or [])
    domains = set(getattr(query_tokens, "domain_tokens", []) or [])
    links: list[dict[str, Any]] = []
    for word in sorted(words | statuses | domains):
        alias = SCHEMA_ALIASES.get(word)
        if alias:
            for table in alias["tables"]:
                if table in schema_index.tables:
                    links.append({"query_term": word, "table": table, "score": 1.0, "source": alias["source"]})
        for table, meta in schema_index.tables.items():
            table_norm = table.lower()
            if word and word in table_norm:
                links.append({"query_term": word, "table": table, "score": 0.75, "source": "table lexical overlap"})
            for column in meta.get("columns", []):
                column_name = column["name"]
                column_norm = column_name.lower()
                if word and word in column_norm:
                    links.append({"query_term": word, "table": table, "column": column_name, "score": 0.55, "source": "column lexical overlap"})
                if word in {"status", "published", "failed", "queued", "active", "inactive"} and any(token in column_norm for token in ("status", "state")):
                    links.append({"query_term": word, "table": table, "column": column_name, "score": 0.8, "source": "status/state column hint"})
    return {"links": _dedupe_links(links), "link_count": len(_dedupe_links(links))}


def backward_schema_link(query_tokens: Any, schema_index: SchemaIndex) -> dict[str, Any]:
    words = set(getattr(query_tokens, "words", []) or [])
    domain_text = " ".join(sorted(words | set(getattr(query_tokens, "domain_tokens", []) or [])))
    links: list[dict[str, Any]] = []
    for table, meta in schema_index.tables.items():
        root = table.lower().replace("dim_", "").replace("fact_", "").replace("hkg_", "").replace("br_", "")
        if root and root in domain_text:
            links.append({"table": table, "query_terms": sorted(words & set(root.split("_"))), "score": 0.75, "source": "table-name-to-query backward link"})
        for column in meta.get("columns", []):
            column_tokens = set(column["name"].lower().split("_"))
            overlap = sorted(column_tokens & words)
            if overlap:
                links.append({"table": table, "column": column["name"], "query_terms": overlap, "score": 0.55, "source": "column-name-to-query backward link"})
    return {"links": _dedupe_links(links), "link_count": len(_dedupe_links(links))}


def combine_schema_links(forward: dict[str, Any], backward: dict[str, Any], structural: dict[str, Any] | None = None) -> dict[str, Any]:
    tables = []
    columns: dict[str, list[str]] = {}
    for link in list(forward.get("links", [])) + list(backward.get("links", [])):
        table = link.get("table")
        if table:
            tables.append(table)
        column = link.get("column")
        if table and column:
            columns.setdefault(table, []).append(column)
    tables.extend((structural or {}).get("candidate_tables", []))
    return {"tables": _dedupe(tables), "columns": {table: _dedupe(values) for table, values in columns.items()}}


def preserve_structural_joins(candidate_tables: list[str], join_graph: list[Any]) -> dict[str, Any]:
    selected = set(candidate_tables)
    added: list[str] = []
    hints: list[dict[str, Any]] = []
    for hint in join_graph:
        left = getattr(hint, "left_table", None) or hint.get("left_table")
        right = getattr(hint, "right_table", None) or hint.get("right_table")
        reason = getattr(hint, "reason", None) or hint.get("reason", "")
        left_bridge = _looks_like_bridge(left)
        right_bridge = _looks_like_bridge(right)
        if left_bridge and right in selected:
            added.append(left)
            hints.append(_hint_to_dict(hint))
        elif right_bridge and left in selected:
            added.append(right)
            hints.append(_hint_to_dict(hint))
        elif left_bridge and right_bridge:
            continue
        elif "bridge" in str(reason).lower() and (left in selected or right in selected):
            hints.append(_hint_to_dict(hint))
    return {
        "added_bridge_tables": _dedupe([item for item in added if item]),
        "join_hints": hints[:12],
        "missing_bridge_warning": bool(selected) and not hints and len(selected) > 1,
    }


def schema_link_risk_score(
    *,
    forward_links: dict[str, Any],
    backward_links: dict[str, Any],
    structural: dict[str, Any],
    confidence: float,
    margin: float,
) -> dict[str, Any]:
    link_count = int(forward_links.get("link_count", 0)) + int(backward_links.get("link_count", 0))
    structural_bonus = 0.1 if structural.get("added_bridge_tables") else 0.0
    schema_confidence = max(0.0, min(1.0, confidence + min(link_count, 8) * 0.035 + structural_bonus))
    risk = "low" if schema_confidence >= 0.75 and margin > 0 else "medium" if schema_confidence >= 0.45 else "high"
    reason = "strong bidirectional links" if risk == "low" else "weak schema links or small score margin"
    if structural.get("added_bridge_tables"):
        reason += "; structural bridge preserved"
    return {
        "schema_link_confidence": round(schema_confidence, 4),
        "schema_link_risk": risk,
        "reason_for_context_mode": reason,
    }


def choose_context_mode(candidate_context: dict[str, Any]) -> str:
    confidence = float(candidate_context.get("confidence") or 0.0)
    margin = float(candidate_context.get("score_margin") or 0.0)
    has_candidates = bool(candidate_context.get("candidate_tables") or candidate_context.get("candidate_apis"))
    if not has_candidates:
        return "full_schema"
    if confidence >= 0.75 and margin > 0:
        return "candidate"
    if 0.4 <= confidence < 0.75 and margin > 0:
        return "expanded_candidate"
    return "hybrid"


def build_adaptive_context(
    query: str,
    schema_index: SchemaIndex,
    endpoint_catalog: EndpointCatalog,
) -> dict[str, Any]:
    initial = build_candidate_context(query, schema_index, endpoint_catalog)
    mode = choose_context_mode(initial)
    if mode == "candidate":
        initial["context_mode"] = mode
        return initial
    if mode == "expanded_candidate":
        expanded = build_candidate_context(
            query,
            schema_index,
            endpoint_catalog,
            top_k_tables=8,
            top_k_columns=20,
            top_k_joins=12,
            top_k_apis=8,
        )
        expanded["context_mode"] = mode
        expanded["notes"] = list(expanded.get("notes", [])) + ["Expanded candidate context selected by adaptive policy."]
        expanded["estimated_tokens"] = estimate_tokens(expanded)
        return expanded
    if mode == "hybrid":
        hybrid = dict(initial)
        hybrid["context_mode"] = "hybrid"
        hybrid["all_table_names"] = sorted(schema_index.tables)
        hybrid["endpoint_summaries"] = [
            {
                "id": endpoint.id,
                "method": endpoint.method,
                "path": endpoint.path,
                "use_when": endpoint.use_when,
            }
            for endpoint in endpoint_catalog.endpoints
        ]
        hybrid["notes"] = list(hybrid.get("notes", [])) + [
            "Hybrid context keeps candidates first but exposes all table names and endpoint summaries."
        ]
        hybrid["estimated_tokens"] = estimate_tokens(hybrid)
        return hybrid
    full = build_full_schema_context(schema_index, endpoint_catalog)
    full["context_mode"] = "full_schema"
    full["query"] = query
    full["estimated_tokens"] = estimate_tokens(full)
    return full


def preserve_structural_relations(query_tokens: Any, candidate_tables: list[str], schema_index: SchemaIndex) -> dict[str, Any]:
    words = set(getattr(query_tokens, "words", []) or [])
    domains = set(getattr(query_tokens, "domain_tokens", []) or [])
    selected = set(candidate_tables)
    relation_rules = [
        {
            "name": "segment_destination",
            "terms": {"segment", "segments", "audience", "audiences", "destination", "destinations", "target", "targets"},
            "required_any": [{"segment", "segments", "audience", "audiences"}, {"destination", "destinations", "target", "targets"}],
            "domains": {"segment_audience", "destination_dataflow"},
            "tables": ["dim_segment", "hkg_br_segment_target", "dim_target"],
            "source": "schema-level segment-target bridge rule",
        },
        {
            "name": "campaign_segment",
            "terms": {"campaign", "campaigns", "journey", "journeys", "segment", "segments", "audience", "audiences"},
            "required_any": [{"campaign", "campaigns", "journey", "journeys"}, {"segment", "segments", "audience", "audiences"}],
            "domains": {"journey_campaign", "segment_audience"},
            "tables": ["dim_campaign", "br_campaign_segment", "dim_segment"],
            "source": "schema-level campaign-segment bridge rule",
        },
        {
            "name": "schema_dataset",
            "terms": {
                "schema",
                "schemas",
                "dataset",
                "datasets",
                "collection",
                "collections",
                "blueprint",
                "blueprints",
                "using",
                "based",
                "associated",
                "connected",
                "linked",
                "built",
                "use",
                "uses",
            },
            "required_any": [{"schema", "schemas", "blueprint", "blueprints"}, {"dataset", "datasets", "collection", "collections"}],
            "domains": {"schema_dataset"},
            "tables": ["dim_blueprint", "dim_collection", "hkg_br_blueprint_collection"],
            "source": "schema-level blueprint-collection bridge rule",
        },
        {
            "name": "source_destination_collection",
            "terms": {"source", "sources", "destination", "destinations", "connector", "connectors", "collection", "collections"},
            "required_any": [{"source", "sources", "destination", "destinations", "connector", "connectors"}, {"collection", "collections"}],
            "domains": {"destination_dataflow", "schema_dataset"},
            "tables": ["dim_connector", "hkg_br_source_collection", "dim_collection"],
            "source": "schema-level connector-collection bridge rule",
        },
    ]
    added: list[str] = []
    reasons: list[str] = []
    hints: list[dict[str, Any]] = []
    for rule in relation_rules:
        if not (words & rule["terms"] or domains & rule["domains"]):
            continue
        required_any = rule.get("required_any") or []
        if required_any and not all(words & group for group in required_any):
            continue
        available = [table for table in rule["tables"] if table in schema_index.tables]
        if not available:
            continue
        if selected and not (selected & set(available)) and len(words & rule["terms"]) < 2:
            continue
        for table in available:
            if rule["name"] == "schema_dataset":
                # Schema/dataset routing needs the whole blueprint-collection
                # relation preserved through the later hybrid rerank.
                added.append(table)
            elif table not in selected:
                added.append(table)
        reasons.append(f"{rule['name']}: {rule['source']}")
        hints.extend(_join_hints_for_tables(schema_index, available))
    return {
        "added_tables": _dedupe(added),
        "reason": "; ".join(reasons[:4]) if reasons else None,
        "join_hints": hints[:12],
        "rule_sources": reasons,
    }


def build_gated_risk_cluster_repair_diagnostic(
    *,
    confidence: float,
    margin: float,
    endpoint_ranking: dict[str, Any],
    baseline_apis: list[dict[str, Any]],
    reranked_apis: list[dict[str, Any]],
) -> dict[str, Any]:
    family_confidence = float((endpoint_ranking.get("detected_family") or {}).get("endpoint_family_confidence") or 0.0)
    risk_cluster = None
    reasons: list[str] = []
    if margin == 0:
        risk_cluster = "zero_score_margin"
        reasons.append("zero score margin remains after candidate scoring")
    if confidence < 0.4:
        risk_cluster = risk_cluster or "low_confidence"
        reasons.append("candidate confidence is low")
    if 0 < family_confidence < 0.55:
        risk_cluster = risk_cluster or "broad_domain_api_confusion"
        reasons.append("endpoint family confidence is low")
    if baseline_apis and reranked_apis and [api.get("id") for api in baseline_apis] != [api.get("id") for api in reranked_apis]:
        reasons.append("reranked endpoint candidate differs from baseline ordering")
    active = bool(reasons)
    return {
        "active": active,
        "diagnostic_only": True,
        "execution_repair_enabled": False,
        "hard_case_triggered": active,
        "risk_cluster": risk_cluster,
        "candidate_count": 2 if active else 1,
        "selected_candidate": (reranked_apis[0].get("id") if reranked_apis else None),
        "rejected_candidate_reason": "lower endpoint-family confidence or lower hybrid score" if active else None,
        "cost_delta": 0,
        "expected_correctness_gain": "retrieval-only candidate separation; no accuracy claim without execution change",
    }


def _rank_tables_for_context(
    tokens: Any,
    schema_index: SchemaIndex,
    relevance_items: list[RelevanceItem],
    forward_links: dict[str, Any],
    backward_links: dict[str, Any],
    structural_tables: list[str],
    value_matches: list[Any],
    *,
    enable_hybrid_ranking: bool,
) -> dict[str, Any]:
    if not enable_hybrid_ranking:
        return {}
    base_scores = {item.name: item.score for item in relevance_items}
    linked = combine_schema_links(forward_links, backward_links)
    aliases_by_table: dict[str, list[str]] = {}
    for alias, payload in SCHEMA_ALIASES.items():
        for table in payload.get("tables", []):
            aliases_by_table.setdefault(table, []).append(alias)
    candidates = [
        {
            "name": table,
            "kind": "table",
            "base_score": base_scores.get(table, 0.0),
            "text": " ".join(schema_index.columns_for(table)[:20]),
            "aliases": aliases_by_table.get(table, []),
            "structural": table in structural_tables,
        }
        for table in schema_index.tables
    ]
    schema_links = {"links": list(forward_links.get("links", [])) + list(backward_links.get("links", [])), **linked}
    return rank_candidates(tokens, candidates, value_matches=value_matches, schema_links=schema_links)


def _candidate_apis_from_ranked(rows: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
    apis = []
    for row in rows[:top_k]:
        apis.append(
            {
                "id": row.get("id"),
                "method": row.get("method"),
                "path": row.get("path"),
                "use_when": row.get("use_when"),
                "score": row.get("final_score"),
                "endpoint_family": row.get("endpoint_family"),
                "score_explanation": row.get("score_explanation"),
            }
        )
    return apis


def _top_score_components(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {}
    top = rows[0]
    keys = [
        "name",
        "lexical_score",
        "alias_score",
        "value_match_score",
        "structural_score",
        "endpoint_family_score",
        "weighted_score_fusion",
        "reciprocal_rank_fusion",
        "score_explanation",
    ]
    return {key: top.get(key) for key in keys}


def _baseline_margin(table_items: list[RelevanceItem]) -> float:
    scores = [item.score for item in table_items[:2]]
    if not scores:
        return 0.0
    return round(max(0.0, scores[0] - (scores[1] if len(scores) > 1 else 0.0)), 4)


def _baseline_confidence(table_items: list[RelevanceItem]) -> float:
    scores = [item.score for item in table_items[:2]]
    if not scores:
        return 0.0
    top = scores[0]
    margin = top - scores[1] if len(scores) > 1 else top
    return round(max(0.0, min(1.0, (top / 3.0) + min(max(margin, 0.0), 1.0) * 0.2)), 4)


def _with_fallback_tables(items: list[RelevanceItem], schema_index: SchemaIndex, top_k: int) -> list[RelevanceItem]:
    if items:
        return items
    fallback = []
    for table, meta in schema_index.tables.items():
        score = 0.2
        if meta.get("is_bridge"):
            score += 0.05
        fallback.append(RelevanceItem(table, score, "fallback schema table"))
    return sorted(fallback, key=lambda item: (-item.score, item.name))[:top_k]


def _candidate_columns(
    table: str,
    scored_columns: list[RelevanceItem],
    schema_index: SchemaIndex,
    top_k: int,
) -> list[str]:
    selected = [item.name for item in scored_columns[:top_k]]
    for column in schema_index.columns_for(table):
        lowered = column.lower()
        if column not in selected and any(token in lowered for token in IMPORTANT_COLUMN_TOKENS):
            selected.append(column)
        if len(selected) >= top_k:
            break
    return selected[:top_k]


def _candidate_joins(items: list[RelevanceItem], top_k: int) -> list[dict[str, Any]]:
    joins = []
    for item in items[:top_k]:
        joins.append({"path": item.name, "score": round(item.score, 4), "reason": item.reason})
    return joins


def _candidate_apis(items: list[RelevanceItem], catalog: EndpointCatalog, top_k: int) -> list[dict[str, Any]]:
    apis = []
    for item in items[:top_k]:
        endpoint = catalog.by_id(item.name)
        if not endpoint:
            continue
        apis.append(
            {
                "id": endpoint.id,
                "method": endpoint.method,
                "path": endpoint.path,
                "use_when": endpoint.use_when,
                "score": round(item.score, 4),
            }
        )
    return apis


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "")
        key = text.lower()
        if text and key not in seen:
            result.append(text)
            seen.add(key)
    return result


def _dedupe_links(links: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for link in links:
        key = (link.get("query_term"), link.get("table"), link.get("column"), link.get("source"))
        if key in seen:
            continue
        seen.add(key)
        result.append(link)
    return result


def _looks_like_bridge(table: str | None) -> bool:
    lowered = str(table or "").lower()
    return lowered.startswith(("br_", "hkg_br_", "bridge_")) or "_br_" in lowered


def _hint_to_dict(hint: Any) -> dict[str, Any]:
    if hasattr(hint, "to_dict"):
        return hint.to_dict()
    if isinstance(hint, dict):
        return dict(hint)
    return {}


def _join_hints_for_tables(schema_index: SchemaIndex, tables: list[str]) -> list[dict[str, Any]]:
    table_set = set(tables)
    rows = []
    for hint in schema_index.join_hints:
        if hint.left_table in table_set and hint.right_table in table_set:
            rows.append(hint.to_dict())
    return rows
