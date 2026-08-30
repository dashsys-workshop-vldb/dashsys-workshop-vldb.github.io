from __future__ import annotations

from typing import Any

from .endpoint_catalog import EndpointCatalog
from .trajectory import redact_secrets
from .validators import APIValidator


def validate_llm_api_candidate(
    candidate: dict[str, Any],
    endpoint_catalog: EndpointCatalog,
    api_validator: APIValidator,
) -> dict[str, Any]:
    endpoint_id = str(candidate.get("endpoint_id") or "").strip()
    if not endpoint_id:
        return _reject("LLM API candidate must use endpoint_id from EndpointCatalog; free-form URLs are blocked.", candidate, endpoint_catalog)
    endpoint = endpoint_catalog.by_id(endpoint_id)
    if endpoint is None:
        return _reject(f"Unknown endpoint_id: {endpoint_id}", candidate, endpoint_catalog)
    method = str(candidate.get("method") or endpoint.method).upper()
    if method != endpoint.method.upper():
        return _reject(f"Method mismatch for endpoint_id {endpoint_id}: expected {endpoint.method}.", candidate, endpoint_catalog)
    if method != "GET":
        return _reject("Pure LLM baseline guard allows GET endpoints only for Adobe data resources.", candidate, endpoint_catalog)
    url = endpoint.path
    if endpoint.path_params:
        return _reject("Endpoint has unresolved path parameters and needs discovered IDs before use.", candidate, endpoint_catalog)
    params = dict(endpoint.common_params)
    raw_params = candidate.get("params")
    if isinstance(raw_params, dict):
        params.update(raw_params)
    validation = api_validator.validate(method, url, params, {})
    if not validation.ok:
        return {
            "ok": False,
            "rejection_reason": "; ".join(validation.errors),
            "validation": validation.to_dict(),
            "suggested_catalog_endpoints": _suggestions(endpoint_catalog),
        }
    return redact_secrets(
        {
            "ok": True,
            "validated_api_call": {"method": method, "url": url, "params": params, "headers": {}},
            "endpoint_id": endpoint_id,
            "validation": validation.to_dict(),
            "rejection_reason": "",
            "suggested_catalog_endpoints": [],
        }
    )


def _reject(reason: str, candidate: dict[str, Any], endpoint_catalog: EndpointCatalog) -> dict[str, Any]:
    return redact_secrets(
        {
            "ok": False,
            "rejection_reason": reason,
            "candidate": candidate,
            "validated_api_call": None,
            "suggested_catalog_endpoints": _suggestions(endpoint_catalog),
        }
    )


def _suggestions(endpoint_catalog: EndpointCatalog) -> list[dict[str, Any]]:
    return [
        {"endpoint_id": endpoint.id, "method": endpoint.method, "path": endpoint.path}
        for endpoint in endpoint_catalog.endpoints
        if endpoint.method == "GET" and not endpoint.path_params
    ][:10]
