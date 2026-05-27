from __future__ import annotations

from typing import Any

from .endpoint_catalog import EndpointCatalog
from .trajectory import redact_secrets
from .validators import APIValidator


def select_weak_model_api_candidates(
    slots: dict[str, Any],
    endpoint_catalog: EndpointCatalog,
    *,
    prompt: str | None = None,
    live_endpoint_matrix: dict[str, Any] | None = None,
) -> dict[str, Any]:
    prompt_text = (prompt or _prompt_from_slots(slots)).lower()
    wanted = _wanted_endpoint_ids(slots, prompt_text)
    validator = APIValidator(endpoint_catalog)
    candidates: list[dict[str, Any]] = []
    for endpoint_id in wanted:
        endpoint = next((item for item in endpoint_catalog.endpoints if item.id == endpoint_id), None)
        if endpoint is None or "{" in endpoint.path or "}" in endpoint.path:
            continue
        params = _params_for(endpoint.id, prompt_text, slots)
        validation = validator.validate(endpoint.method, endpoint.path, params, {})
        if not validation.ok:
            continue
        candidates.append(
            {
                "endpoint_id": endpoint.id,
                "method": endpoint.method,
                "path": endpoint.path,
                "params": params,
                "validation": validation.to_dict(),
                "selection_reason": _reason(endpoint.id, slots),
                "live_health_rank": _health_rank(endpoint.id, live_endpoint_matrix or {}),
            }
        )
    candidates.sort(key=lambda item: (-int(item.get("live_health_rank") or 0), wanted.index(item["endpoint_id"])))
    return redact_secrets(
        {
            "selected_endpoint": candidates[0] if candidates else None,
            "candidates": candidates,
            "selection_reason": candidates[0]["selection_reason"] if candidates else "api_not_needed_or_no_safe_catalog_endpoint",
        }
    )


def _wanted_endpoint_ids(slots: dict[str, Any], lowered_prompt: str) -> list[str]:
    domain = str(slots.get("domain") or "").upper()
    if "merge polic" in lowered_prompt:
        return ["merge_policies"]
    if "batch" in lowered_prompt:
        return ["catalog_batches"]
    if "tag categor" in lowered_prompt or "category" in lowered_prompt:
        return ["unified_tag_categories"]
    if "tag" in lowered_prompt:
        return ["unified_tags"]
    if domain == "JOURNEY":
        return ["journey_list"]
    if domain == "SEGMENT":
        if any(term in lowered_prompt for term in ("connected", "destination", "mapped", "associated")):
            return ["ups_audiences", "flowservice_flows", "segment_definitions"]
        return ["ups_audiences", "segment_definitions"]
    if domain == "CONNECTOR" or "flow" in lowered_prompt or "dataflow" in lowered_prompt:
        return ["flowservice_flows", "flowservice_runs"]
    if domain == "DESTINATION":
        return ["flowservice_flows"]
    if domain == "DATASET":
        return ["catalog_datasets"]
    if domain == "SCHEMA":
        return ["schema_registry_schemas", "schemas_short"]
    if domain == "AUDIT":
        return ["audit_events"]
    return []


def _params_for(endpoint_id: str, lowered_prompt: str, slots: dict[str, Any]) -> dict[str, Any]:
    if endpoint_id == "journey_list":
        if "inactive" in lowered_prompt:
            return {"filter": "status!=live"}
        if "list all" in lowered_prompt or "all journeys" in lowered_prompt:
            return {"pageSize": 10}
        quoted = (slots.get("quoted_entities") or [None])[0]
        if quoted:
            return {"filter": f"name=={quoted}"}
        return {}
    if endpoint_id == "ups_audiences":
        return {"limit": 5} if "connected" in lowered_prompt or "destination" in lowered_prompt else {"limit": 50}
    if endpoint_id == "flowservice_flows":
        if "failed" in lowered_prompt:
            return {"filter": "state eq 'failed'", "limit": 50}
        if "destination" in lowered_prompt:
            return {"property": "inheritedAttributes.properties.isDestinationFlow==true", "limit": 5}
        return {"limit": 50}
    if endpoint_id == "segment_definitions":
        return {"limit": 50}
    if endpoint_id in {"catalog_datasets", "catalog_batches", "schema_registry_schemas", "schemas_short", "unified_tags", "unified_tag_categories", "merge_policies", "segment_jobs"}:
        return {"limit": 50}
    return {}


def _health_rank(endpoint_id: str, matrix: dict[str, Any]) -> int:
    text = str(matrix)
    if endpoint_id in text and "live_success" in text:
        return 2
    if endpoint_id in text and "live_empty" in text:
        return 1
    return 0


def _reason(endpoint_id: str, slots: dict[str, Any]) -> str:
    return f"selected_{endpoint_id}_for_{str(slots.get('domain') or 'UNKNOWN').lower()}_{str(slots.get('intent') or 'UNKNOWN').lower()}"


def _prompt_from_slots(slots: dict[str, Any]) -> str:
    nlp = slots.get("nlp_context") if isinstance(slots.get("nlp_context"), dict) else {}
    if nlp.get("original_prompt"):
        return str(nlp["original_prompt"])
    terms = []
    terms.extend(str(value) for value in slots.get("entity_terms") or [])
    terms.extend(str(value) for value in slots.get("quoted_entities") or [])
    return " ".join([str(slots.get("intent") or ""), str(slots.get("domain") or ""), " ".join(terms)])
