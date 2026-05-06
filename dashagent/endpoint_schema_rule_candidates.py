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

    def matches(self, query: str, risk_cluster: str, failure_type: str) -> bool:
        text = query.lower()
        if self.targeted_failure_type not in {risk_cluster, failure_type, "all"}:
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
        ),
        EndpointSchemaRuleCandidate(
            "failed_batch_file_family",
            "Failed-file wording with batch vocabulary should prefer failed batch file endpoints.",
            "batch_endpoint_confusion",
            "batch_failed_files",
            ("failed file", "failed files", "batch failed"),
            "domain vocabulary + endpoint catalog path shape",
        ),
        EndpointSchemaRuleCandidate(
            "tag_category_detail_list_family",
            "Tag wording should separate list, detail, and category endpoint families by reusable vocabulary.",
            "tag_api_confusion",
            "tag_list",
            ("tag", "tags", "category", "categories", "named"),
            "domain vocabulary + endpoint catalog metadata",
        ),
        EndpointSchemaRuleCandidate(
            "schema_dataset_relation_family",
            "Schema plus dataset/collection relation language should keep schema and dataset families in top-k.",
            "schema_vs_dataset_confusion",
            "dataset_list",
            ("schema", "dataset", "datasets", "collection", "collections"),
            "domain vocabulary + schema-dataset relation language",
        ),
        EndpointSchemaRuleCandidate(
            "journey_status_date_family",
            "Journey status/date/list wording should prefer journey-list family.",
            "broad_domain_api_confusion",
            "journey_list",
            ("journey", "journeys", "published", "inactive", "campaign"),
            "domain vocabulary + endpoint catalog metadata",
        ),
        EndpointSchemaRuleCandidate(
            "segment_job_status_family",
            "Segment job/status wording should prefer segment job endpoints over broad segment definitions.",
            "broad_domain_api_confusion",
            "segment_jobs",
            ("segment job", "segment jobs", "evaluation job", "queued"),
            "domain vocabulary + endpoint catalog metadata",
        ),
        EndpointSchemaRuleCandidate(
            "merge_policy_default_class_family",
            "Merge policy/default/class wording should prefer merge policy endpoints.",
            "broad_domain_api_confusion",
            "merge_policies",
            ("merge policy", "merge policies", "default merge", "schema class"),
            "domain vocabulary + endpoint catalog metadata",
        ),
        EndpointSchemaRuleCandidate(
            "observability_timeseries_metric_family",
            "Metric/timeseries wording should prefer observability metrics endpoints.",
            "broad_domain_api_confusion",
            "observability_metrics",
            ("metric", "metrics", "timeseries", "observability"),
            "domain vocabulary + endpoint catalog metadata",
        ),
        EndpointSchemaRuleCandidate(
            "zero_margin_endpoint_family_tiebreak",
            "Zero-margin rows should use endpoint-family confidence as a future tie-break candidate.",
            "zero_score_margin",
            "unknown",
            ("",),
            "diagnostic ranking signal, not gold-derived",
        ),
        EndpointSchemaRuleCandidate(
            "missing_api_topk_family_coverage",
            "Missing top-k API rows should add catalog-backed family coverage diagnostics before runtime changes.",
            "missing_gold_api_in_top_k",
            "unknown",
            ("",),
            "endpoint catalog coverage diagnostic",
        ),
    ]


def rerank_api_ids_for_family(api_ids: list[str], endpoints: list[Endpoint], family: str) -> list[str]:
    if family == "unknown":
        return list(api_ids)
    known = {endpoint.id: endpoint for endpoint in endpoints}
    matching = sorted(endpoint.id for endpoint in endpoints if endpoint_family_for_endpoint(endpoint) == family)
    remaining = [api_id for api_id in api_ids if api_id not in matching]
    injected = [api_id for api_id in matching if api_id in known]
    return list(dict.fromkeys([*injected, *remaining]))
