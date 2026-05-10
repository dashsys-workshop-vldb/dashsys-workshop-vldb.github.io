from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .endpoint_catalog import Endpoint
from .endpoint_family_ranker import endpoint_family_for_endpoint


@dataclass(frozen=True)
class EndpointSchemaRuleCandidate:
    rule_id: str
    description: str
    targeted_failure_type: str
    target_family: str
    trigger_terms: tuple[str, ...]
    source: str
    trigger_features: tuple[str, ...]
    generalizable_family: str
    dependency_branches: tuple[str, ...] = ("codex/score075-robustness-leakage",)

    def matches(self, query: str, risk_cluster: str, failure_type: str) -> bool:
        text = query.lower()
        observed_failures = {_non_gold_failure_alias(risk_cluster), _non_gold_failure_alias(failure_type), "all"}
        if self.targeted_failure_type not in observed_failures:
            return False
        return any(term in text for term in self.trigger_terms)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "description": self.description,
            "targeted_failure_type": self.targeted_failure_type,
            "target_family": self.target_family,
            "trigger_terms": list(self.trigger_terms),
            "source": self.source,
            "rule_source": self.source,
            "trigger_features": list(self.trigger_features),
            "generalizable_family": self.generalizable_family,
            "dependency_branches": list(self.dependency_branches),
            "leakage_check_result": validate_rule_leakage(
                {
                    "rule_id": self.rule_id,
                    "description": self.description,
                    "trigger_terms": list(self.trigger_terms),
                    "source": self.source,
                    "trigger_features": list(self.trigger_features),
                    "generalizable_family": self.generalizable_family,
                }
            ),
        }


def candidate_rules() -> list[EndpointSchemaRuleCandidate]:
    """Reusable domain/path-shape candidates for shadow evaluation only."""

    return [
        EndpointSchemaRuleCandidate(
            "batch_id_file_family",
            "Batch-shaped IDs combined with file/download wording should prefer batch file endpoints.",
            "batch_endpoint_confusion",
            "batch_files",
            ("batch", "file", "files", "download"),
            "domain vocabulary + endpoint catalog path shape",
            ("batch vocabulary", "file/download wording", "endpoint catalog export batch file path"),
            "batch_files",
        ),
        EndpointSchemaRuleCandidate(
            "failed_batch_file_family",
            "Failed-file wording with batch vocabulary should prefer failed batch file endpoints.",
            "batch_endpoint_confusion",
            "batch_failed_files",
            ("failed file", "failed files", "batch failed"),
            "domain vocabulary + endpoint catalog path shape",
            ("failed-file wording", "batch vocabulary", "endpoint catalog failed batch path"),
            "batch_failed_files",
        ),
        EndpointSchemaRuleCandidate(
            "tag_category_detail_list_family",
            "Tag wording should separate list, detail, and category endpoint families by reusable vocabulary.",
            "tag_api_confusion",
            "tag_list",
            ("tag", "tags", "category", "categories", "named"),
            "domain vocabulary + endpoint catalog metadata",
            ("tag vocabulary", "category/list/detail wording", "unified tags catalog families"),
            "tag_list",
        ),
        EndpointSchemaRuleCandidate(
            "tag_named_detail_family",
            "Tag name/detail wording should keep tag detail endpoint candidates visible.",
            "zero_score_margin",
            "tag_detail",
            ("tag named", "tag called", "tag detail", "details of the tag", "details for tag"),
            "domain vocabulary + endpoint catalog path shape",
            ("tag detail wording", "name/called phrase", "unified tag detail path shape"),
            "tag_detail",
        ),
        EndpointSchemaRuleCandidate(
            "schema_dataset_relation_family",
            "Schema plus dataset/collection relation language should keep schema and dataset families in top-k.",
            "schema_vs_dataset_confusion",
            "dataset_list",
            (
                "schema",
                "dataset",
                "datasets",
                "collection",
                "collections",
                "using schema",
                "based on schema",
                "associated with schema",
                "schema used by",
                "built from schema",
                "connected with the profile schema",
            ),
            "domain vocabulary + schema-dataset relation language",
            ("schema-dataset relation wording", "dataset/collection vocabulary", "schema registry + catalog dataset families"),
            "schema_dataset_relation",
        ),
        EndpointSchemaRuleCandidate(
            "schema_named_detail_family",
            "Schema name/detail wording should keep schema lookup families visible without using schema IDs.",
            "broad_domain_api_confusion",
            "schema_list",
            ("schema named", "schema called", "details for the schema", "more details for the schema", "schema record"),
            "domain vocabulary + endpoint catalog metadata",
            ("schema detail wording", "name/called phrase", "schema registry list/detail families"),
            "schema_detail",
        ),
        EndpointSchemaRuleCandidate(
            "journey_status_date_family",
            "Journey status/date/list wording should prefer journey-list family.",
            "broad_domain_api_confusion",
            "journey_list",
            ("journey", "journeys", "published", "inactive", "campaign"),
            "domain vocabulary + endpoint catalog metadata",
            ("journey/campaign vocabulary", "status/date/list wording", "journey endpoint family"),
            "journey_list",
        ),
        EndpointSchemaRuleCandidate(
            "destination_flow_listing_family",
            "Destination listing or recently modified destination wording should keep flowservice flow candidates visible.",
            "zero_score_margin",
            "flow_definitions",
            ("destination", "destinations", "destination flow", "modified", "sandbox", "sorted"),
            "domain vocabulary + endpoint catalog flowservice metadata",
            ("destination vocabulary", "modified/sorted list wording", "flowservice destination-flow path shape"),
            "destination_flow_list",
        ),
        EndpointSchemaRuleCandidate(
            "audience_destination_mapping_family",
            "Audience-to-destination mapping wording should keep audience, flow, and audit candidate families visible.",
            "missing_api_candidate",
            "audit_events",
            ("mapped to", "mapped to new destinations", "connected to the destination", "destination named", "audiences"),
            "domain vocabulary + endpoint catalog relationship metadata",
            ("audience/destination relation wording", "mapping/change wording", "audit and flowservice catalog families"),
            "audience_destination_mapping",
        ),
        EndpointSchemaRuleCandidate(
            "dataflow_run_status_family",
            "Dataflow run failure/status wording should keep flow run and flow definition candidates visible.",
            "zero_score_margin",
            "flow_definitions",
            ("dataflow runs", "flow runs", "failed dataflow", "failed runs", "run status"),
            "domain vocabulary + endpoint catalog flowservice metadata",
            ("dataflow run vocabulary", "failed/status wording", "flowservice run/flow families"),
            "dataflow_run_status",
        ),
        EndpointSchemaRuleCandidate(
            "segment_job_status_family",
            "Segment job/status wording should prefer segment job endpoints over broad segment definitions.",
            "broad_domain_api_confusion",
            "segment_jobs",
            ("segment job", "segment jobs", "evaluation job", "queued"),
            "domain vocabulary + endpoint catalog metadata",
            ("segment job vocabulary", "status/evaluation wording", "segment jobs endpoint family"),
            "segment_jobs",
        ),
        EndpointSchemaRuleCandidate(
            "merge_policy_default_class_family",
            "Merge policy/default/class wording should prefer merge policy endpoints.",
            "broad_domain_api_confusion",
            "merge_policies",
            ("merge policy", "merge policies", "default merge", "schema class"),
            "domain vocabulary + endpoint catalog metadata",
            ("merge policy vocabulary", "default/class wording", "merge policy endpoint family"),
            "merge_policies",
        ),
        EndpointSchemaRuleCandidate(
            "dataset_audit_change_family",
            "Dataset recent-change wording should keep audit event candidates visible.",
            "broad_domain_api_confusion",
            "audit_events",
            ("recent changes", "dataset changes", "changes in datasets", "recent dataset", "created datasets", "updated datasets"),
            "domain vocabulary + audit endpoint catalog metadata",
            ("dataset change wording", "recent/create/update wording", "audit events endpoint family"),
            "dataset_audit_changes",
        ),
        EndpointSchemaRuleCandidate(
            "audit_entity_creator_family",
            "Created-by or entity-change wording should prefer audit event endpoint candidates.",
            "broad_domain_api_confusion",
            "audit_events",
            ("created by", "entities created", "entity changes", "changed by", "audit events"),
            "domain vocabulary + audit endpoint catalog metadata",
            ("audit/change vocabulary", "created-by wording", "audit events endpoint family"),
            "audit_entity_changes",
        ),
        EndpointSchemaRuleCandidate(
            "observability_timeseries_metric_family",
            "Metric/timeseries wording should prefer observability metrics endpoints.",
            "broad_domain_api_confusion",
            "observability_metrics",
            ("metric", "metrics", "timeseries", "observability"),
            "domain vocabulary + endpoint catalog metadata",
            ("metric/timeseries vocabulary", "observability wording", "observability metric endpoint family"),
            "observability_metrics",
        ),
        EndpointSchemaRuleCandidate(
            "observability_ingestion_metric_family",
            "Ingestion record/batch count wording should keep observability metric candidates visible.",
            "zero_score_margin",
            "observability_metrics",
            ("ingestion record", "record counts", "batch success counts", "last 90 days", "daily counts"),
            "domain vocabulary + observability metric naming pattern",
            ("ingestion metric wording", "record/batch count terms", "observability metric endpoint family"),
            "observability_metrics",
        ),
        EndpointSchemaRuleCandidate(
            "zero_margin_endpoint_family_tiebreak",
            "Zero-margin rows should use endpoint-family confidence as a future tie-break candidate.",
            "zero_score_margin",
            "unknown",
            ("",),
            "diagnostic ranking signal, not gold-derived",
            ("zero-margin diagnostic", "endpoint-family confidence", "catalog-backed ranking signal"),
            "endpoint_family_tiebreak",
        ),
        EndpointSchemaRuleCandidate(
            "missing_api_topk_family_coverage",
            "Missing top-k API rows should add catalog-backed family coverage diagnostics before runtime changes.",
            "missing_api_candidate",
            "unknown",
            ("",),
            "endpoint catalog coverage diagnostic",
            ("missing-top-k diagnostic", "catalog-backed family coverage", "report-only coverage signal"),
            "endpoint_family_coverage",
        ),
    ]


def leakage_safe_candidate_rules() -> list[EndpointSchemaRuleCandidate]:
    """Rules that pass the local non-gold/non-public-source check."""

    return [rule for rule in candidate_rules() if validate_rule_leakage(rule.to_dict())["passed"]]


def rerank_api_ids_for_family(api_ids: list[str], endpoints: list[Endpoint], family: str) -> list[str]:
    if family == "unknown":
        return list(api_ids)
    known = {endpoint.id: endpoint for endpoint in endpoints}
    matching = sorted(endpoint.id for endpoint in endpoints if endpoint_family_for_endpoint(endpoint) == family)
    remaining = [api_id for api_id in api_ids if api_id not in matching]
    injected = [api_id for api_id in matching if api_id in known]
    return list(dict.fromkeys([*injected, *remaining]))


def _leakage_check(rule: dict[str, Any]) -> bool:
    return validate_rule_leakage(rule)["passed"]


def validate_rule_leakage(rule: dict[str, Any]) -> dict[str, Any]:
    """Reject rule metadata that looks like public-example or gold-signal leakage.

    This checker is intentionally local and conservative. It does not inspect gold
    labels; it only validates that candidate rule definitions are phrased as
    reusable vocabulary/path-shape logic instead of query-specific branches.
    """

    forbidden = {
        "query_id": "query_id_trigger",
        "example_": "public_eval_example_id",
        "exact full query": "exact_query_trigger",
        "public answer": "public_answer_trigger",
        "memorized answer": "memorized_answer_trigger",
        "expected answer": "expected_answer_trigger",
        "gold_sql": "gold_sql_trigger",
        "gold sql": "gold_sql_trigger",
        "gold_api": "gold_api_trigger",
        "gold api": "gold_api_trigger",
        "gold path": "gold_api_trigger",
    }
    sanitized = {key: value for key, value in rule.items() if key not in {"leakage_check_result", "checked_constraints"}}
    text = str(sanitized).lower()
    reasons = sorted({reason for token, reason in forbidden.items() if token in text})
    trigger_terms = [str(term) for term in rule.get("trigger_terms", [])]
    for term in trigger_terms:
        normalized = " ".join(term.lower().split())
        if len(normalized.split()) > 8:
            reasons.append("overly_specific_trigger_phrase")
        if "?" in normalized and "=" in normalized:
            reasons.append("api_query_parameter_trigger")
    return {
        "passed": not reasons,
        "rejection_reasons": sorted(set(reasons)),
        "checked_constraints": [
            "no_query_id",
            "no_exact_full_public_query",
            "no_gold_sql_or_api_path",
            "no_memorized_answer",
            "no_overly_specific_trigger_phrase",
        ],
    }


def _non_gold_failure_alias(value: str) -> str:
    if value in {"missing_gold_api_in_top_k", "gold_api_missing_from_top_k"}:
        return "missing_api_candidate"
    return value
