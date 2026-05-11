from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .endpoint_catalog import EndpointCatalog


ROUTE_TYPES = {
    "SQL_ONLY",
    "API_ONLY",
    "SQL_THEN_API",
    "API_THEN_SQL",
    "SQL_AND_API_COMPARE",
}

DOMAIN_TYPES = {
    "JOURNEY_CAMPAIGN",
    "SEGMENT_AUDIENCE",
    "DESTINATION_DATAFLOW",
    "DATASET_SCHEMA",
    "PROPERTY_FIELD",
    "RELATIONSHIP_TRAVERSAL",
    "COUNT_AGGREGATION",
    "STATUS_MONITORING",
    "UNKNOWN",
}


DOMAIN_KEYWORDS = {
    "JOURNEY_CAMPAIGN": ["journey", "campaign", "published", "inactive", "live", "draft"],
    "SEGMENT_AUDIENCE": ["segment", "audience", "profile", "customer group", "customer"],
    "DESTINATION_DATAFLOW": [
        "destination",
        "target",
        "dataflow",
        "data flow",
        "connector",
        "activation",
        "flow",
    ],
    "DATASET_SCHEMA": ["dataset", "collection", "schema", "blueprint"],
    "PROPERTY_FIELD": ["property", "field", "attribute"],
    "RELATIONSHIP_TRAVERSAL": [
        "connected to",
        "associated with",
        "related to",
        "uses",
        "linked",
        "relationship",
    ],
    "COUNT_AGGREGATION": ["count", "how many", "number of", "total"],
    "STATUS_MONITORING": ["status", "failed", "succeeded", "live", "inactive", "published", "draft"],
}

TABLE_HINTS = {
    "JOURNEY_CAMPAIGN": ["dim_campaign", "campaign", "journey"],
    "SEGMENT_AUDIENCE": ["dim_segment", "segment", "audience"],
    "DESTINATION_DATAFLOW": ["dim_target", "dim_connector", "target", "connector", "flow"],
    "DATASET_SCHEMA": ["dim_collection", "dim_blueprint", "dataset", "schema", "collection", "blueprint"],
    "PROPERTY_FIELD": ["dim_property", "property", "field"],
    "RELATIONSHIP_TRAVERSAL": ["br_", "hkg_br_", "bridge"],
    "COUNT_AGGREGATION": [],
    "STATUS_MONITORING": [],
    "UNKNOWN": [],
}


@dataclass
class RoutingDecision:
    route_type: str
    domain_type: str
    confidence: float
    reason: str
    candidate_tables: list[str] = field(default_factory=list)
    candidate_apis: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class QueryRouter:
    def __init__(
        self,
        table_names: list[str] | None = None,
        endpoint_catalog: EndpointCatalog | None = None,
    ) -> None:
        self.table_names = table_names or []
        self.endpoint_catalog = endpoint_catalog or EndpointCatalog()

    def _keyword_hits(self, query: str) -> dict[str, int]:
        lowered = query.lower()
        return {
            domain: sum(1 for keyword in keywords if keyword in lowered)
            for domain, keywords in DOMAIN_KEYWORDS.items()
        }

    def _candidate_tables(self, primary_domain: str, hits: dict[str, int]) -> list[str]:
        hints = set(TABLE_HINTS.get(primary_domain, []))
        for domain, count in hits.items():
            if count:
                hints.update(TABLE_HINTS.get(domain, []))
        candidates = []
        for table in self.table_names:
            lowered = table.lower()
            if any(hint and hint in lowered for hint in hints):
                candidates.append(table)
        if not candidates and self.table_names:
            candidates = self.table_names[:5]
        return candidates[:8]

    def route(self, query: str) -> RoutingDecision:
        hits = self._keyword_hits(query)
        primary_domains = [
            domain
            for domain, count in sorted(hits.items(), key=lambda item: item[1], reverse=True)
            if count > 0
        ]
        primary = next(
            (
                domain
                for domain in primary_domains
                if domain not in {"COUNT_AGGREGATION", "STATUS_MONITORING", "RELATIONSHIP_TRAVERSAL"}
            ),
            primary_domains[0] if primary_domains else "UNKNOWN",
        )

        is_count = hits.get("COUNT_AGGREGATION", 0) > 0
        is_status = hits.get("STATUS_MONITORING", 0) > 0
        is_relationship = hits.get("RELATIONSHIP_TRAVERSAL", 0) > 0
        lowered_query = query.lower()
        mentions_api_state = any(word in lowered_query for word in ["current", "live", "platform", "sandbox", "api"])
        api_only_resource = any(
            phrase in lowered_query
            for phrase in [
                "tag",
                "merge polic",
                "segment job",
                "segment definition",
                "segment evaluation job",
                "batch",
                "batches",
                "files available",
                "timeseries.",
                "ingestion record",
                "audit",
            ]
        )

        sql_needed = primary != "UNKNOWN" or is_count or is_relationship
        api_needed = api_only_resource or (
            primary in {"JOURNEY_CAMPAIGN", "SEGMENT_AUDIENCE", "DESTINATION_DATAFLOW", "DATASET_SCHEMA"}
            and (is_status or mentions_api_state)
        )
        if "compare" in query.lower() or "disagree" in query.lower():
            route_type = "SQL_AND_API_COMPARE"
        elif api_only_resource:
            route_type = "API_ONLY"
        elif api_needed and sql_needed:
            route_type = "SQL_THEN_API"
        elif api_needed:
            route_type = "API_ONLY"
        else:
            route_type = "SQL_ONLY"

        if is_count and primary == "UNKNOWN":
            primary = "COUNT_AGGREGATION"
        if is_relationship and primary == "UNKNOWN":
            primary = "RELATIONSHIP_TRAVERSAL"
        if is_status and primary == "UNKNOWN":
            primary = "STATUS_MONITORING"

        confidence = min(0.95, 0.35 + 0.15 * sum(1 for count in hits.values() if count > 0))
        if primary == "UNKNOWN":
            confidence = 0.2

        candidate_apis = [
            endpoint.to_dict() for endpoint in self.endpoint_catalog.candidates_for_domain(primary)
        ][:5]
        candidate_tables = self._candidate_tables(primary, hits)
        reason_bits = [f"{domain}:{count}" for domain, count in hits.items() if count]
        reason = "Keyword routing" + (f" using {', '.join(reason_bits)}." if reason_bits else " found no domain keyword.")

        return RoutingDecision(
            route_type=route_type,
            domain_type=primary,
            confidence=confidence,
            reason=reason,
            candidate_tables=candidate_tables,
            candidate_apis=candidate_apis,
        )
