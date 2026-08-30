from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .config import Config, DEFAULT_CONFIG


@dataclass(frozen=True)
class Endpoint:
    id: str
    method: str
    path: str
    use_when: str
    common_params: dict[str, Any] = field(default_factory=dict)
    path_params: list[str] = field(default_factory=list)
    examples: list[dict[str, Any]] = field(default_factory=list)
    risk_notes: list[str] = field(default_factory=list)
    domains: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_api_path(url_or_path: str) -> str:
    parsed = urlparse(url_or_path)
    path = parsed.path if (parsed.scheme and parsed.netloc) or parsed.query else url_or_path
    path = "/" + path.lstrip("/")
    path = re.sub(r"/+", "/", path)
    return path.rstrip("/") or "/"


class EndpointCatalog:
    def __init__(self, config: Config | None = None) -> None:
        self.config = config or DEFAULT_CONFIG
        self.endpoints = self._default_endpoints()

    def _default_endpoints(self) -> list[Endpoint]:
        return [
            Endpoint(
                id="journey_list",
                method="GET",
                path="/ajo/journey",
                use_when="List or inspect Journey Optimizer journeys/campaigns, statuses, published/live/inactive/draft state.",
                common_params={"limit": 50, "start": 0},
                examples=[{"query": "published journeys", "params": {"limit": 50}}],
                risk_notes=["Journey status names can differ between database snapshots and live API state."],
                domains=["JOURNEY_CAMPAIGN", "STATUS_MONITORING"],
            ),
            Endpoint(
                id="ups_audiences",
                method="GET",
                path="/data/core/ups/audiences",
                use_when="List or look up Real-Time CDP audiences and audience metadata/counts.",
                common_params={"limit": 50, "start": 0},
                examples=[{"query": "audiences with profile counts", "params": {"limit": 50}}],
                risk_notes=["Audience APIs can be paginated; avoid assuming first page is exhaustive."],
                domains=["SEGMENT_AUDIENCE"],
            ),
            Endpoint(
                id="segment_definitions",
                method="GET",
                path="/data/core/ups/segment/definitions",
                use_when="Look up segment definitions, names, statuses, and segment metadata.",
                common_params={"limit": 50, "start": 0},
                examples=[{"query": "segment definition by name", "params": {"limit": 50}}],
                risk_notes=["Definition IDs and audience IDs are related but not always identical."],
                domains=["SEGMENT_AUDIENCE"],
            ),
            Endpoint(
                id="flowservice_flows",
                method="GET",
                path="/data/foundation/flowservice/flows",
                use_when="List destination/dataflow/activation flows and flow metadata.",
                common_params={"limit": 50},
                examples=[{"query": "destination flows", "params": {"limit": 50}}],
                risk_notes=["Flow lists are paginated and may need property filters for production use."],
                domains=["DESTINATION_DATAFLOW"],
            ),
            Endpoint(
                id="flowservice_runs",
                method="GET",
                path="/data/foundation/flowservice/runs",
                use_when="Inspect dataflow run status, failed/succeeded runs, and recent execution state.",
                common_params={"limit": 50},
                examples=[{"query": "failed flow runs", "params": {"limit": 50}}],
                risk_notes=["Run windows and sorting must be explicit for time-sensitive questions."],
                domains=["DESTINATION_DATAFLOW", "STATUS_MONITORING"],
            ),
            Endpoint(
                id="catalog_datasets",
                method="GET",
                path="/data/foundation/catalog/dataSets",
                use_when="List datasets and dataset metadata.",
                common_params={"limit": 50},
                examples=[{"query": "dataset metadata", "params": {"limit": 50}}],
                risk_notes=["Catalog responses can be large; request only needed fields when supported."],
                domains=["DATASET_SCHEMA"],
            ),
            Endpoint(
                id="schema_registry_schema",
                method="GET",
                path="/data/foundation/schemaregistry/tenant/schemas/{schema_id}",
                use_when="Fetch schema details when a concrete schema ID is known.",
                common_params={},
                path_params=["schema_id"],
                examples=[{"query": "schema by id", "path_params": {"schema_id": "..."}}],
                risk_notes=["Requires a schema ID; do not call with an unresolved placeholder."],
                domains=["DATASET_SCHEMA", "PROPERTY_FIELD"],
            ),
            Endpoint(
                id="schema_registry_schemas",
                method="GET",
                path="/data/foundation/schemaregistry/tenant/schemas",
                use_when="List tenant schemas or filter schema registry metadata.",
                common_params={"limit": 25},
                examples=[{"query": "profile-enabled ExperienceEvent schemas"}],
                risk_notes=["Schema-registry filters vary by endpoint version."],
                domains=["DATASET_SCHEMA"],
            ),
            Endpoint(
                id="schemas_short",
                method="GET",
                path="/schemas",
                use_when="Gold-example shorthand for schema list/name lookup.",
                common_params={"limit": 25},
                examples=[{"query": "schema named weRetail: Customer Actions"}],
                risk_notes=["Shorthand path is retained for benchmark compatibility."],
                domains=["DATASET_SCHEMA"],
            ),
            Endpoint(
                id="audit_events",
                method="GET",
                path="/data/foundation/audit/events",
                use_when="Audit events for destination/dataset/entity changes.",
                common_params={"limit": 20},
                examples=[{"query": "new destinations in last 3 months"}],
                domains=["DESTINATION_DATAFLOW", "DATASET_SCHEMA", "STATUS_MONITORING"],
            ),
            Endpoint(
                id="audit_events_short",
                method="GET",
                path="/audit/events",
                use_when="Gold-example shorthand for audit events.",
                common_params={"limit": 50},
                examples=[{"query": "recent dataset changes"}],
                domains=["DATASET_SCHEMA", "STATUS_MONITORING"],
            ),
            Endpoint(
                id="unified_tags",
                method="GET",
                path="/unifiedtags/tags",
                use_when="List or count tags.",
                common_params={"limit": 25},
                domains=["UNKNOWN"],
            ),
            Endpoint(
                id="unified_tag_categories",
                method="GET",
                path="/unifiedtags/tagCategory",
                use_when="List tag categories.",
                common_params={"limit": 100},
                domains=["UNKNOWN"],
            ),
            Endpoint(
                id="unified_tag_detail",
                method="GET",
                path="/unifiedtags/tags/{tag_id}",
                use_when="Fetch tag details when a tag ID is known.",
                path_params=["tag_id"],
                domains=["UNKNOWN"],
            ),
            Endpoint(
                id="merge_policies",
                method="GET",
                path="/data/core/ups/config/mergePolicies",
                use_when="List/count Real-Time Customer Profile merge policies.",
                common_params={"limit": 10},
                domains=["SEGMENT_AUDIENCE", "UNKNOWN"],
            ),
            Endpoint(
                id="segment_jobs",
                method="GET",
                path="/data/core/ups/segment/jobs",
                use_when="List segment evaluation jobs and statuses.",
                common_params={"limit": 10},
                domains=["SEGMENT_AUDIENCE", "STATUS_MONITORING"],
            ),
            Endpoint(
                id="catalog_batches",
                method="GET",
                path="/data/foundation/catalog/batches",
                use_when="List/count catalog batches.",
                common_params={"limit": 10},
                domains=["DATASET_SCHEMA", "STATUS_MONITORING", "UNKNOWN"],
            ),
            Endpoint(
                id="catalog_batch_detail",
                method="GET",
                path="/data/foundation/catalog/batches/{batch_id}",
                use_when="Fetch batch details by ID.",
                path_params=["batch_id"],
                domains=["DATASET_SCHEMA", "UNKNOWN"],
            ),
            Endpoint(
                id="export_batch_files",
                method="GET",
                path="/data/foundation/export/batches/{batch_id}/files",
                use_when="List files available for download in an export batch.",
                path_params=["batch_id"],
                domains=["DATASET_SCHEMA", "UNKNOWN"],
            ),
            Endpoint(
                id="export_batch_failed",
                method="GET",
                path="/data/foundation/export/batches/{batch_id}/failed",
                use_when="List failed files for an export batch.",
                path_params=["batch_id"],
                domains=["DATASET_SCHEMA", "STATUS_MONITORING", "UNKNOWN"],
            ),
            Endpoint(
                id="observability_metrics",
                method="POST",
                path="/data/infrastructure/observability/insights/metrics",
                use_when="Query observability metric time series.",
                common_params={},
                domains=["STATUS_MONITORING", "UNKNOWN"],
            ),
        ]

    def as_list(self) -> list[dict[str, Any]]:
        return [endpoint.to_dict() for endpoint in self.endpoints]

    def by_id(self, endpoint_id: str) -> Endpoint | None:
        return next((endpoint for endpoint in self.endpoints if endpoint.id == endpoint_id), None)

    def candidates_for_domain(self, domain_type: str) -> list[Endpoint]:
        return [
            endpoint
            for endpoint in self.endpoints
            if domain_type in endpoint.domains or domain_type == "UNKNOWN"
        ]

    def match(self, method: str, url_or_path: str) -> Endpoint | None:
        method = method.upper()
        path = normalize_api_path(url_or_path)
        for endpoint in self.endpoints:
            if endpoint.method != method:
                continue
            pattern = "^" + re.sub(r"\\\{[^/]+\\\}", r"[^/]+", re.escape(endpoint.path)) + "$"
            if re.match(pattern, path, flags=re.IGNORECASE):
                return endpoint
        return None

    def save(self, path: Path | None = None) -> Path:
        out = path or (self.config.outputs_dir / "endpoint_catalog.json")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(self.as_list(), indent=2, sort_keys=True), encoding="utf-8")
        return out

    def extract_gold_api_patterns(self, data_json_path: Path | None = None) -> list[dict[str, Any]]:
        path = data_json_path or self.config.data_json_path
        if not path.exists():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []

        counter: Counter[tuple[str, str]] = Counter()
        examples: dict[tuple[str, str], list[dict[str, Any]]] = {}

        def walk(obj: Any, parent_question: str | None = None) -> None:
            if isinstance(obj, dict):
                question = (
                    obj.get("question")
                    or obj.get("query")
                    or obj.get("input")
                    or parent_question
                )
                method = obj.get("method") or obj.get("http_method")
                url = obj.get("url") or obj.get("path") or obj.get("endpoint")
                if method and url:
                    key = (str(method).upper(), normalize_api_path(str(url)))
                    counter[key] += 1
                    examples.setdefault(key, [])
                    if len(examples[key]) < 3:
                        examples[key].append({"question": question, "params": obj.get("params", {})})
                for value in obj.values():
                    walk(value, question)
            elif isinstance(obj, list):
                for item in obj:
                    walk(item, parent_question)

        walk(payload)
        patterns = [
            {
                "method": method,
                "path": path,
                "count": count,
                "examples": examples.get((method, path), []),
            }
            for (method, path), count in counter.most_common()
        ]
        out = self.config.outputs_dir / "gold_api_patterns.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(patterns, indent=2, sort_keys=True), encoding="utf-8")
        return patterns
