from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


API_REQUIRED = "API_REQUIRED"
API_OPTIONAL = "API_OPTIONAL"
API_SKIP = "API_SKIP"

API_ONLY_FAMILIES = {
    "audit_create_events",
    "batch_details",
    "batch_export_files",
    "batch_list",
    "dataset_audit_changes",
    "datasets_by_schema",
    "destination_audit_events",
    "merge_policies",
    "observability_metrics",
    "profile_enabled_experience_event_schemas",
    "recent_batches",
    "recent_segment_definitions",
    "segment_definition_count",
    "segment_definition_list",
    "segment_jobs",
    "schema_by_name",
    "schema_list",
    "successful_batch_count",
    "tag_categories",
    "tag_count",
    "tag_details_by_id",
    "tag_list",
    "tags_by_uncategorized_category",
}

MULTI_CALL_FAMILIES = {
    "audience_by_destination_id",
    "destination_flows",
    "datasets_by_schema",
    "schema_registry_by_id",
    "tag_categories",
    "tags_by_uncategorized_category",
}


@dataclass(frozen=True)
class ApiNeedDecision:
    mode: str
    reason: str
    max_api_calls: int = 0
    allowed_api_families: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "reason": self.reason,
            "max_api_calls": self.max_api_calls,
            "allowed_api_families": self.allowed_api_families,
        }


def decide_api_need(
    query: str,
    routing: Any,
    sql_template: Any,
    api_templates: list[Any],
    strategy: str,
) -> ApiNeedDecision:
    lowered = query.lower()
    families = [template.family for template in api_templates]

    if not api_templates:
        return ApiNeedDecision(API_SKIP, "No API template matched and SQL/local evidence is preferred.")

    if strategy == "LLM_FREE_AGENT_BASELINE":
        return ApiNeedDecision(API_OPTIONAL, "Baseline strategy keeps broad API probes.", 2, families)

    if "merge_policies" in families:
        return ApiNeedDecision(API_REQUIRED, "Merge policies are Adobe API objects.", 1, ["merge_policies"])

    if getattr(routing, "route_type", "") == "API_ONLY":
        return ApiNeedDecision(API_REQUIRED, "Route is API-only.", max_calls_for_families(families), families)

    if any(family in API_ONLY_FAMILIES for family in families):
        allowed = allowed_required_families(families)
        return ApiNeedDecision(API_REQUIRED, "Query family requires Adobe API evidence.", max_calls_for_families(allowed), allowed)

    if sql_template is not None and not explicitly_live(lowered) and safe_sql_only_family(sql_template.family):
        return ApiNeedDecision(API_SKIP, f"SQL template {sql_template.family} fully answers this local query.")

    if "gold_pattern_fallback" in families and len(families) == 1:
        if sql_template is not None and not explicitly_live(lowered):
            return ApiNeedDecision(API_SKIP, "Only a weak gold-pattern fallback matched; SQL evidence is sufficient.")
        return ApiNeedDecision(API_OPTIONAL, "Weak gold-pattern fallback is allowed as one verification call.", 1, families)

    if asks_count(lowered) and set(families).issubset({"journey_default", "journey_list"}) and not explicitly_live(lowered):
        return ApiNeedDecision(API_SKIP, "Local SQL count is sufficient for this non-live campaign/journey count.")

    if any(family in MULTI_CALL_FAMILIES for family in families):
        return ApiNeedDecision(API_OPTIONAL, "Known multi-call verification family.", 2, families)

    if explicitly_live(lowered) or any(token in lowered for token in ["journey", "campaign", "destination", "dataflow"]):
        return ApiNeedDecision(API_OPTIONAL, "Live/platform verification may improve the answer.", 1, families)

    return ApiNeedDecision(API_SKIP, "No strong evidence that API verification improves this SQL-grounded answer.")


def explicitly_live(lowered_query: str) -> bool:
    return any(
        token in lowered_query
        for token in [
            "api",
            "current",
            "failed",
            "inactive",
            "live",
            "platform",
            "published",
            "sandbox",
            "status",
            "succeeded",
        ]
    )


def asks_count(lowered_query: str) -> bool:
    return any(token in lowered_query for token in ["how many", "count", "number of", "total"])


def safe_sql_only_family(family: str) -> bool:
    return family in {
        "blueprint_collection_count",
        "blueprint_collection_list",
        "blueprint_collection_same_schema_count",
        "collection_property_fields",
        "destination_export_recent",
        "recent_dataset_changes",
        "schema_count",
        "segment_property_fields",
    }


def allowed_required_families(families: list[str]) -> list[str]:
    if "tag_categories" in families or "tags_by_uncategorized_category" in families:
        return [family for family in families if family in {"tag_categories", "tags_by_uncategorized_category"}]
    if "datasets_by_schema" in families or "schema_registry_by_id" in families:
        return [family for family in families if family in {"datasets_by_schema", "schema_registry_by_id"}]
    if "audience_by_destination_id" in families or "destination_flows" in families:
        return [family for family in families if family in {"audience_by_destination_id", "destination_flows"}]
    return [family for family in families if family in API_ONLY_FAMILIES] or families[:1]


def max_calls_for_families(families: list[str]) -> int:
    if any(family in MULTI_CALL_FAMILIES for family in families):
        return 2
    return 1 if families else 0
