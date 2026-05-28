from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from .endpoint_catalog import Endpoint, EndpointCatalog


@dataclass(frozen=True)
class DiscoveryRule:
    source_endpoint_id: str
    detail_endpoint_id: str
    discovered_id_field: str
    path_param: str


@dataclass
class DiscoveryDecision:
    discovery_required: bool
    discovery_source_endpoint: str | None
    discovered_id_field: str | None
    detail_endpoint: str | None
    discovery_status: str
    blocked_reason: str | None = None
    filled_path: str | None = None
    id_source: str | None = None
    source_endpoint: str | None = None
    source_field: str | None = None
    source_query_id_or_fixture: str | None = None
    discovered_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


DISCOVERY_RULES = {
    "unified_tag_detail": DiscoveryRule("unified_tags", "unified_tag_detail", "tag_id", "tag_id"),
    "catalog_batch_detail": DiscoveryRule("catalog_batches", "catalog_batch_detail", "batch_id", "batch_id"),
    "export_batch_files": DiscoveryRule("catalog_batches", "export_batch_files", "batch_id", "batch_id"),
    "export_batch_failed": DiscoveryRule("catalog_batches", "export_batch_failed", "batch_id", "batch_id"),
    "schema_registry_schema": DiscoveryRule("schema_registry_schemas", "schema_registry_schema", "schema_id", "schema_id"),
}


def discovery_required(endpoint: Endpoint) -> bool:
    return bool(endpoint.path_params or "{" in endpoint.path or "}" in endpoint.path)


def discovery_rule_for(endpoint: Endpoint) -> DiscoveryRule | None:
    return DISCOVERY_RULES.get(endpoint.id)


def plan_discovery_for_endpoint(endpoint: Endpoint, catalog: EndpointCatalog | None = None) -> DiscoveryDecision:
    catalog = catalog or EndpointCatalog()
    if endpoint.method != "GET":
        return DiscoveryDecision(
            discovery_required=discovery_required(endpoint),
            discovery_source_endpoint=None,
            discovered_id_field=None,
            detail_endpoint=endpoint.id,
            discovery_status="discovery_blocked_non_get",
            blocked_reason="Discovery chains are GET-only.",
        )
    if not discovery_required(endpoint):
        return DiscoveryDecision(
            discovery_required=False,
            discovery_source_endpoint=None,
            discovered_id_field=None,
            detail_endpoint=endpoint.id,
            discovery_status="not_required",
        )
    rule = discovery_rule_for(endpoint)
    if rule is None:
        return DiscoveryDecision(
            discovery_required=True,
            discovery_source_endpoint=None,
            discovered_id_field=None,
            detail_endpoint=endpoint.id,
            discovery_status="unsupported_or_unsafe",
            blocked_reason="No safe discovery rule exists for this endpoint.",
        )
    source = catalog.by_id(rule.source_endpoint_id)
    if source is None or source.method != "GET" or discovery_required(source):
        return DiscoveryDecision(
            discovery_required=True,
            discovery_source_endpoint=rule.source_endpoint_id,
            discovered_id_field=rule.discovered_id_field,
            detail_endpoint=endpoint.id,
            discovery_status="unsupported_or_unsafe",
            blocked_reason="Discovery source endpoint is missing or unsafe.",
        )
    return DiscoveryDecision(
        discovery_required=True,
        discovery_source_endpoint=rule.source_endpoint_id,
        discovered_id_field=rule.discovered_id_field,
        detail_endpoint=endpoint.id,
        discovery_status="needs_discovery_chain",
    )


def resolve_discovery_chain(
    endpoint: Endpoint,
    *,
    parsed_evidence: dict[str, Any] | None = None,
    evidence_bus: Any | None = None,
    sql_evidence: dict[str, Any] | None = None,
    source_query_id_or_fixture: str | None = None,
    catalog: EndpointCatalog | None = None,
) -> DiscoveryDecision:
    catalog = catalog or EndpointCatalog()
    decision = plan_discovery_for_endpoint(endpoint, catalog)
    if not decision.discovery_required:
        return decision
    if decision.discovery_status != "needs_discovery_chain":
        return decision
    rule = discovery_rule_for(endpoint)
    if rule is None:
        decision.discovery_status = "unsupported_or_unsafe"
        decision.blocked_reason = "No safe discovery rule exists for this endpoint."
        return decision

    discovered = _find_discovered_id(
        rule.discovered_id_field,
        parsed_evidence=parsed_evidence,
        evidence_bus=evidence_bus,
        sql_evidence=sql_evidence,
    )
    if not discovered:
        decision.discovery_status = "discovery_blocked_missing_id"
        decision.blocked_reason = "No ID was available from live API, SQL, EvidenceBus, or fixture evidence."
        return decision

    value, source, source_field = discovered
    if "{" not in endpoint.path:
        decision.discovery_status = "not_required"
        return decision
    filled_path = endpoint.path.replace("{" + rule.path_param + "}", str(value))
    if "{" in filled_path or "}" in filled_path:
        decision.discovery_status = "discovery_blocked_unresolved_path"
        decision.blocked_reason = "Path remains unresolved after applying discovered ID."
        return decision

    decision.discovery_status = "ready_with_discovered_id"
    decision.filled_path = filled_path
    decision.discovered_id = str(value)
    decision.id_source = source
    decision.source_endpoint = (parsed_evidence or {}).get("endpoint_id") or rule.source_endpoint_id if source in {"live_api", "fixture"} else source
    decision.source_field = source_field
    decision.source_query_id_or_fixture = source_query_id_or_fixture
    return decision


def _find_discovered_id(
    field: str,
    *,
    parsed_evidence: dict[str, Any] | None,
    evidence_bus: Any | None,
    sql_evidence: dict[str, Any] | None,
) -> tuple[str, str, str] | None:
    aliases = _field_aliases(field)
    if isinstance(parsed_evidence, dict):
        for alias in aliases:
            value = _value_from_parsed(alias, parsed_evidence)
            if value:
                return value, "live_api" if parsed_evidence.get("dry_run") is False else "fixture", alias
        ids = parsed_evidence.get("ids")
        if isinstance(ids, list) and ids:
            return str(ids[0]), "live_api" if parsed_evidence.get("dry_run") is False else "fixture", "ids[0]"

    if evidence_bus is not None:
        ids = getattr(evidence_bus, "ids", {}) or {}
        for alias in aliases:
            if isinstance(ids, dict) and ids.get(alias):
                return str(ids[alias]), "evidence_bus", alias
        api_ids = getattr(evidence_bus, "api_ids", []) or []
        if api_ids:
            return str(api_ids[0]), "evidence_bus", "api_ids[0]"

    if isinstance(sql_evidence, dict):
        rows = sql_evidence.get("rows") if isinstance(sql_evidence.get("rows"), list) else []
        for row in rows:
            if not isinstance(row, dict):
                continue
            for alias in aliases:
                for key, value in row.items():
                    if _normalize(key) == _normalize(alias) and value not in (None, "", [], {}):
                        return str(value), "sql", key
    return None


def _value_from_parsed(alias: str, parsed: dict[str, Any]) -> str | None:
    for item in parsed.get("items", []) if isinstance(parsed.get("items"), list) else []:
        if not isinstance(item, dict):
            continue
        for key, value in item.items():
            if _normalize(key) == _normalize(alias) and value not in (None, "", [], {}):
                return str(value)
    important = parsed.get("important_fields")
    if isinstance(important, dict):
        for key, value in important.items():
            if _normalize(key) == _normalize(alias) and value not in (None, "", [], {}):
                if isinstance(value, list) and value:
                    return str(value[0])
                return str(value)
    return None


def _field_aliases(field: str) -> list[str]:
    mapping = {
        "tag_id": ["tag_id", "tagId", "id", "_id", "@id"],
        "batch_id": ["batch_id", "batchId", "id", "_id", "@id"],
        "schema_id": ["schema_id", "schemaId", "id", "_id", "@id"],
    }
    return mapping.get(field, [field, re.sub(r"_([a-z])", lambda m: m.group(1).upper(), field), "id", "_id"])


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())
