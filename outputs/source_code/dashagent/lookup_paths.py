from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class LookupPath:
    family: str
    tables: list[str]
    join_path: list[str] = field(default_factory=list)
    api_families: list[str] = field(default_factory=list)
    required_ids: list[str] = field(default_factory=list)
    api_mode: str = "optional"

    def to_dict(self) -> dict[str, Any]:
        return {
            "family": self.family,
            "tables": self.tables,
            "join_path": self.join_path,
            "api_families": self.api_families,
            "required_ids": self.required_ids,
            "api_mode": self.api_mode,
        }


LOOKUP_PATHS: dict[str, LookupPath] = {
    "journey_campaign": LookupPath(
        family="journey_campaign",
        tables=["dim_campaign"],
        api_families=["journey_by_name", "journey_inactive", "journey_list"],
        required_ids=["campaign_id", "journey_name"],
        api_mode="optional",
    ),
    "segment_destination": LookupPath(
        family="segment_destination",
        tables=["dim_segment", "hkg_br_segment_target", "dim_target"],
        join_path=[
            "dim_segment.segmentid = hkg_br_segment_target.segmentid",
            "hkg_br_segment_target.targetid = dim_target.targetid",
        ],
        api_families=["audience_by_destination_id", "destination_flows"],
        required_ids=["segment_id", "destination_id", "target_id"],
        api_mode="optional",
    ),
    "destination_dataflow": LookupPath(
        family="destination_dataflow",
        tables=["dim_target", "dim_connector"],
        api_families=["destination_flows", "recent_destination_flows", "failed_dataflow_flows"],
        required_ids=["target_id", "dataflow_id"],
        api_mode="optional",
    ),
    "schema_dataset": LookupPath(
        family="schema_dataset",
        tables=["dim_blueprint", "hkg_br_blueprint_collection", "dim_collection"],
        join_path=[
            "dim_blueprint.blueprintid = hkg_br_blueprint_collection.blueprintid",
            "hkg_br_blueprint_collection.collectionid = dim_collection.collectionid",
        ],
        api_families=["datasets_by_schema", "schema_registry_by_id", "schema_by_name", "schema_list"],
        required_ids=["schema_id", "blueprint_id", "collection_id"],
        api_mode="required",
    ),
    "property_field": LookupPath(
        family="property_field",
        tables=["dim_segment", "hkg_br_segment_property", "dim_collection", "hkg_br_collection_property"],
        join_path=[
            "dim_segment.segmentid = hkg_br_segment_property.segmentid",
            "dim_collection.collectionid = hkg_br_collection_property.collectionid",
        ],
        api_families=[],
        required_ids=["segment_id", "collection_id", "property"],
        api_mode="skip",
    ),
    "tags": LookupPath(
        family="tags",
        tables=[],
        api_families=["tag_count", "tag_list", "tag_details_by_id", "tag_categories", "tags_by_uncategorized_category"],
        required_ids=["tag_id", "tag_category_id"],
        api_mode="required",
    ),
    "merge_policy": LookupPath(
        family="merge_policy",
        tables=[],
        api_families=["merge_policies"],
        required_ids=["merge_policy_id"],
        api_mode="required",
    ),
    "observability": LookupPath(
        family="observability",
        tables=[],
        api_families=["observability_metrics"],
        required_ids=[],
        api_mode="required",
    ),
    "batch": LookupPath(
        family="batch",
        tables=[],
        api_families=["batch_list", "recent_batches", "batch_details", "batch_export_files", "successful_batch_count"],
        required_ids=["batch_id"],
        api_mode="required",
    ),
    "audit": LookupPath(
        family="audit",
        tables=["dim_collection", "dim_segment", "hkg_br_segment_target", "dim_target"],
        api_families=["audit_create_events", "audit_events", "dataset_audit_changes", "destination_audit_events"],
        required_ids=["collection_id", "segment_id", "target_id"],
        api_mode="required",
    ),
}


def predict_lookup_path(query: str, answer_family: str, domain_type: str = "") -> LookupPath:
    lowered = query.lower()
    if answer_family in {"journey_published", "inactive_journeys", "list_journeys"}:
        return LOOKUP_PATHS["journey_campaign"]
    if answer_family in {"segment_destination"}:
        return LOOKUP_PATHS["segment_destination"]
    if answer_family in {"destination_export", "failed_dataflow_runs"}:
        return LOOKUP_PATHS["destination_dataflow"]
    if answer_family in {"schema_dataset"}:
        return LOOKUP_PATHS["schema_dataset"]
    if answer_family == "property_field":
        return LOOKUP_PATHS["property_field"]
    if answer_family == "tags":
        return LOOKUP_PATHS["tags"]
    if answer_family == "merge_policy":
        return LOOKUP_PATHS["merge_policy"]
    if answer_family == "observability_metrics":
        return LOOKUP_PATHS["observability"]
    if answer_family == "batch":
        return LOOKUP_PATHS["batch"]
    if "audit" in answer_family or "created by" in lowered:
        return LOOKUP_PATHS["audit"]
    if "DATASET_SCHEMA" in domain_type:
        return LOOKUP_PATHS["schema_dataset"]
    if "DESTINATION_DATAFLOW" in domain_type:
        return LOOKUP_PATHS["destination_dataflow"]
    if "SEGMENT_AUDIENCE" in domain_type:
        return LOOKUP_PATHS["segment_destination"]
    if "JOURNEY_CAMPAIGN" in domain_type:
        return LOOKUP_PATHS["journey_campaign"]
    return LookupPath(family="unknown", tables=[], api_mode="optional")
