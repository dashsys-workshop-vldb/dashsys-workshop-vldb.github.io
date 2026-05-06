from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .endpoint_catalog import Endpoint
from .query_tokens import QueryTokens
from .relevance_scorer import RelevanceItem, split_identifier


ENDPOINT_FAMILY_BY_ID = {
    "journey_list": "journey_list",
    "ups_audiences": "segment_definitions",
    "segment_definitions": "segment_definitions",
    "flowservice_flows": "flow_definitions",
    "flowservice_runs": "flow_runs",
    "catalog_datasets": "dataset_list",
    "schema_registry_schema": "schema_detail",
    "schema_registry_schemas": "schema_list",
    "schemas_short": "schema_list",
    "audit_events": "audit_events",
    "audit_events_short": "audit_events",
    "unified_tags": "tag_list",
    "unified_tag_categories": "tag_category",
    "unified_tag_detail": "tag_detail",
    "merge_policies": "merge_policies",
    "segment_jobs": "segment_jobs",
    "catalog_batches": "batch_list",
    "catalog_batch_detail": "batch_details",
    "export_batch_files": "batch_files",
    "export_batch_failed": "batch_failed_files",
    "observability_metrics": "observability_metrics",
}

ENDPOINT_FAMILY_RULE_SOURCES = {
    "batch_files": "domain vocabulary + endpoint catalog path pattern",
    "batch_failed_files": "domain vocabulary + endpoint catalog path pattern",
    "batch_details": "endpoint catalog path pattern",
    "batch_list": "endpoint catalog metadata",
    "tag_list": "domain vocabulary + endpoint catalog metadata",
    "tag_detail": "domain vocabulary + endpoint catalog path pattern",
    "tag_category": "domain vocabulary + endpoint catalog path pattern",
    "schema_list": "domain vocabulary + endpoint catalog metadata",
    "schema_detail": "domain vocabulary + endpoint catalog path pattern",
    "dataset_list": "domain vocabulary + endpoint catalog metadata",
    "journey_list": "domain vocabulary + endpoint catalog metadata",
    "flow_runs": "domain vocabulary + endpoint catalog metadata",
    "flow_definitions": "domain vocabulary + endpoint catalog metadata",
    "segment_jobs": "domain vocabulary + endpoint catalog metadata",
    "segment_definitions": "domain vocabulary + endpoint catalog metadata",
    "merge_policies": "domain vocabulary + endpoint catalog metadata",
    "audit_events": "domain vocabulary + endpoint catalog metadata",
    "observability_metrics": "domain vocabulary + endpoint catalog metadata",
}

VALUE_BOOST_RULE_SOURCES = {
    "batch_id_to_batch_endpoint": "domain vocabulary + ID shape",
    "schema_value_to_schema_dataset_endpoint": "domain vocabulary + value retrieval match",
    "tag_value_to_tag_endpoint": "domain vocabulary + value retrieval match",
    "journey_value_to_journey_endpoint": "domain vocabulary + value retrieval match",
    "destination_value_to_flow_endpoint": "domain vocabulary + value retrieval match",
    "metric_value_to_observability_endpoint": "domain vocabulary + value retrieval match",
}


@dataclass(frozen=True)
class EndpointFamilyDecision:
    family: str | None
    confidence: float
    scores: dict[str, float]
    boost_reasons: list[str]
    value_match_used_for_api_ranking: bool = False
    value_match_confidence: float | None = None
    boosted_endpoint_family: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "endpoint_family": self.family,
            "endpoint_family_confidence": round(self.confidence, 4),
            "family_scores": {key: round(value, 4) for key, value in sorted(self.scores.items()) if value > 0},
            "endpoint_boost_reason": self.boost_reasons,
            "value_match_used_for_api_ranking": self.value_match_used_for_api_ranking,
            "value_match_confidence": self.value_match_confidence,
            "boosted_endpoint_family": self.boosted_endpoint_family,
            "boost_applied": bool(self.family and self.confidence > 0),
        }


def endpoint_family_for_endpoint(endpoint: Endpoint | dict[str, Any] | RelevanceItem | str) -> str:
    endpoint_id = _endpoint_id(endpoint)
    if endpoint_id in ENDPOINT_FAMILY_BY_ID:
        return ENDPOINT_FAMILY_BY_ID[endpoint_id]
    text = _endpoint_text(endpoint)
    if "failed" in text and "batch" in text:
        return "batch_failed_files"
    if "batch" in text and "files" in text:
        return "batch_files"
    if "tagcategory" in text or "tag category" in text:
        return "tag_category"
    if "tags/{" in text:
        return "tag_detail"
    if "tags" in text:
        return "tag_list"
    if "schemas/{" in text:
        return "schema_detail"
    if "schema" in text:
        return "schema_list"
    if "dataset" in text:
        return "dataset_list"
    if "journey" in text:
        return "journey_list"
    if "runs" in text:
        return "flow_runs"
    return "unknown"


def detect_endpoint_family(query_tokens: QueryTokens, value_matches: list[Any] | None = None) -> EndpointFamilyDecision:
    words = set(query_tokens.words)
    matching = query_tokens.matching_text
    scores: dict[str, float] = {}
    reasons: list[str] = []

    def add(family: str, amount: float, reason: str) -> None:
        scores[family] = scores.get(family, 0.0) + amount
        reasons.append(f"{family}: {reason}")

    has_batch_id = bool(query_tokens.batch_ids or re.search(r"\b[0-9a-f]{24}\b", matching, flags=re.IGNORECASE))
    if has_batch_id:
        add("batch_details", 0.55, "batch-shaped ID")
        if "file" in words or "files" in words or "download" in words:
            add("batch_files", 1.2, "batch ID with files/download terms")
        if "failed" in words and ("file" in words or "files" in words):
            add("batch_failed_files", 1.45, "failed files with batch ID")
    elif "batch" in words or "batches" in words:
        add("batch_list", 0.55, "batch list vocabulary")
        if "file" in words or "files" in words:
            add("batch_files", 0.65, "batch files vocabulary")

    if "tag" in words or "tags" in words:
        add("tag_list", 0.85, "tag vocabulary")
        if "named" in words or query_tokens.quoted_entities or query_tokens.named_entities:
            add("tag_detail", 0.55, "tag detail/name vocabulary")
    if "category" in words or "categories" in words or "uncategorized" in words:
        add("tag_category", 0.75, "tag category vocabulary")

    if "schema" in words or "schemas" in words or query_tokens.schema_ids:
        add("schema_list", 0.8, "schema vocabulary")
        if query_tokens.schema_ids or query_tokens.quoted_entities or "named" in words:
            add("schema_detail", 0.7, "schema ID/name vocabulary")
    if "dataset" in words or "datasets" in words or "collection" in words or "collections" in words:
        add("dataset_list", 0.85, "dataset/collection vocabulary")
        if "schema" in words or "schemas" in words:
            add("schema_detail", 0.25, "schema-dataset relation vocabulary")

    if "journey" in words or "journeys" in words or "campaign" in words:
        add("journey_list", 0.9, "journey/campaign vocabulary")
    if "dataflow" in words or "flow" in words or "flows" in words:
        add("flow_definitions", 0.75, "flow definition vocabulary")
        if "run" in words or "runs" in words or "failed" in words or "succeeded" in words:
            add("flow_runs", 1.05, "flow run/status vocabulary")
    if "segment" in words or "segments" in words or "audience" in words or "audiences" in words:
        add("segment_definitions", 0.85, "segment/audience vocabulary")
        if "job" in words or "jobs" in words or "evaluation" in words:
            add("segment_jobs", 1.0, "segment jobs vocabulary")
    if "merge" in words and ("policy" in words or "policies" in words):
        add("merge_policies", 1.1, "merge policy vocabulary")
    if "audit" in words or "created" in words or "download" in words:
        add("audit_events", 0.45, "audit/change vocabulary")
    if query_tokens.metric_names or "metric" in words or "metrics" in words or "observability" in words or "timeseries" in words:
        add("observability_metrics", 1.1, "observability metric vocabulary")

    value_boost = _value_match_family(value_matches or [])
    if value_boost:
        family, confidence, reason = value_boost
        add(family, 0.7, reason)

    if not scores:
        return EndpointFamilyDecision(None, 0.0, {}, [], False, None, None)
    ranked = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    top_family, top_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0.0
    confidence = min(1.0, 0.45 + min(top_score, 1.5) / 2.0 + min(max(top_score - second_score, 0.0), 1.0) * 0.15)
    value_used = bool(value_boost and value_boost[0] == top_family)
    return EndpointFamilyDecision(
        top_family,
        round(confidence, 4),
        scores,
        reasons[:10],
        value_match_used_for_api_ranking=value_used,
        value_match_confidence=value_boost[1] if value_used and value_boost else None,
        boosted_endpoint_family=top_family if value_used else None,
    )


def rank_endpoint_candidates(
    query_tokens: QueryTokens,
    endpoints: list[Endpoint],
    *,
    relevance_items: list[RelevanceItem] | None = None,
    value_matches: list[Any] | None = None,
) -> dict[str, Any]:
    base_scores = {item.name: item.score for item in relevance_items or []}
    before = [item.name for item in relevance_items or []] or [endpoint.id for endpoint in endpoints]
    decision = detect_endpoint_family(query_tokens, value_matches)
    rows: list[dict[str, Any]] = []
    for endpoint in endpoints:
        family = endpoint_family_for_endpoint(endpoint)
        base = float(base_scores.get(endpoint.id, 0.0))
        family_score = _endpoint_family_score(decision, family, endpoint)
        endpoint_words = set(split_identifier(endpoint.id)) | set(re.findall(r"[a-z0-9]+", endpoint.path.lower()))
        lexical = 0.12 * len(set(query_tokens.words) & endpoint_words)
        final = base + family_score + lexical
        rows.append(
            {
                "id": endpoint.id,
                "method": endpoint.method,
                "path": endpoint.path,
                "use_when": endpoint.use_when,
                "domains": endpoint.domains,
                "base_score": round(base, 4),
                "endpoint_family": family,
                "endpoint_family_score": round(family_score, 4),
                "lexical_score": round(lexical, 4),
                "final_score": round(final, 4),
                "score_explanation": _score_explanation(base, family_score, lexical, decision),
            }
        )
    ranked = sorted(rows, key=lambda row: (-row["final_score"], row["id"]))
    after = [row["id"] for row in ranked]
    return {
        "detected_family": decision.to_dict(),
        "ranked_endpoints": ranked,
        "endpoint_rank_before": before,
        "endpoint_rank_after": after,
        "ranking_changed": before[: len(after)] != after[: len(before)],
        "endpoint_boost_reason": decision.boost_reasons[:8],
    }


def _endpoint_family_score(decision: EndpointFamilyDecision, family: str, endpoint: Endpoint) -> float:
    if not decision.family:
        return 0.0
    score = 0.0
    if family == decision.family:
        score += 1.4 * decision.confidence
    if decision.family == "batch_failed_files" and family == "batch_files":
        score += 0.35
    if decision.family == "schema_detail" and family in {"schema_list", "dataset_list"}:
        score += 0.25
    if decision.family == "tag_detail" and family == "tag_list":
        score += 0.3
    if decision.family == "flow_runs" and family == "flow_definitions":
        score += 0.2
    return score


def _value_match_family(value_matches: list[Any]) -> tuple[str, float, str] | None:
    best: tuple[str, float, str] | None = None
    for match in value_matches:
        payload = match.to_dict() if hasattr(match, "to_dict") else dict(match)
        confidence = float(payload.get("confidence") or 0.0)
        if confidence < 0.94:
            continue
        text = " ".join(
            str(payload.get(key) or "").lower()
            for key in ("kind", "matched_table", "matched_column", "used_for", "mention")
        )
        family = None
        source = None
        if "batch" in text:
            family, source = "batch_files", "batch_id_to_batch_endpoint"
        elif "schema" in text or "blueprint" in text:
            family, source = "schema_detail", "schema_value_to_schema_dataset_endpoint"
        elif "tag" in text or "category" in text:
            family, source = "tag_detail", "tag_value_to_tag_endpoint"
        elif "campaign" in text or "journey" in text:
            family, source = "journey_list", "journey_value_to_journey_endpoint"
        elif "target" in text or "destination" in text or "flow" in text:
            family, source = "flow_definitions", "destination_value_to_flow_endpoint"
        elif "metric" in text or "timeseries" in text:
            family, source = "observability_metrics", "metric_value_to_observability_endpoint"
        if family and (best is None or confidence > best[1]):
            best = (family, confidence, f"value match {source} confidence={confidence}")
    return best


def _endpoint_id(endpoint: Endpoint | dict[str, Any] | RelevanceItem | str) -> str:
    if isinstance(endpoint, str):
        return endpoint
    if isinstance(endpoint, RelevanceItem):
        return endpoint.name
    if isinstance(endpoint, dict):
        return str(endpoint.get("id") or endpoint.get("name") or "")
    return endpoint.id


def _endpoint_text(endpoint: Endpoint | dict[str, Any] | RelevanceItem | str) -> str:
    if isinstance(endpoint, str):
        return endpoint.lower()
    if isinstance(endpoint, RelevanceItem):
        return f"{endpoint.name} {endpoint.reason}".lower()
    if isinstance(endpoint, dict):
        return " ".join(str(endpoint.get(key) or "") for key in ("id", "name", "path", "use_when")).lower()
    return f"{endpoint.id} {endpoint.path} {endpoint.use_when}".lower()


def _score_explanation(base: float, family: float, lexical: float, decision: EndpointFamilyDecision) -> str:
    parts = [f"base={base:.3f}", f"family={family:.3f}", f"lexical={lexical:.3f}"]
    if decision.family:
        parts.append(f"detected_family={decision.family}")
    return "; ".join(parts)
