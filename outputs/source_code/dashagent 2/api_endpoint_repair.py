from __future__ import annotations

import re
from typing import Any

from .endpoint_catalog import EndpointCatalog, normalize_api_path


def repair_api_call(
    method: str,
    url: str,
    params: dict[str, Any] | None,
    endpoint_catalog: EndpointCatalog,
    query: str | None = None,
) -> dict[str, Any]:
    """Repair common endpoint-family aliases to catalog-backed paths.

    This is intentionally conservative: a repair is returned only when the
    repaired method/path matches the EndpointCatalog. It does not fabricate
    evidence or execute anything.
    """

    method = (method or "GET").upper()
    original_url = url or ""
    path = normalize_api_path(original_url)
    text = f"{path} {query or ''}".lower()
    params = dict(params or {})

    candidate: str | None = None
    reason = ""
    confidence = 0.0

    batch_id = _extract_batch_id(path)
    if batch_id and "batch" in text:
        if "failed" in text:
            candidate = f"/data/foundation/export/batches/{batch_id}/failed"
            reason = "batch failed-files alias repaired to export failed endpoint"
            confidence = 0.88
        elif "file" in text or "download" in text:
            candidate = f"/data/foundation/export/batches/{batch_id}/files"
            reason = "batch file/download alias repaired to export files endpoint"
            confidence = 0.9
        else:
            candidate = f"/data/foundation/catalog/batches/{batch_id}"
            reason = "batch detail alias repaired to catalog batch detail endpoint"
            confidence = 0.82
    elif "merge" in text and "polic" in text:
        candidate = "/data/core/ups/config/mergePolicies"
        reason = "merge policy alias repaired to catalog endpoint"
        confidence = 0.85
    elif "tag" in text:
        candidate = "/unifiedtags/tags"
        reason = "tag alias repaired to unified tags endpoint"
        confidence = 0.82
    elif "journey" in text or "campaign" in text:
        candidate = "/ajo/journey"
        reason = "journey/campaign alias repaired to AJO journey endpoint"
        confidence = 0.8
    elif "segment" in text and "job" in text:
        candidate = "/data/core/ups/segment/jobs"
        reason = "segment job alias repaired to segment jobs endpoint"
        confidence = 0.83
    elif "segment" in text and ("definition" in text or "audience" in text):
        candidate = "/data/core/ups/segment/definitions"
        reason = "segment definition alias repaired to segment definitions endpoint"
        confidence = 0.8
    elif ("flow" in text or "dataflow" in text) and "run" in text:
        candidate = "/data/foundation/flowservice/runs"
        reason = "flow run alias repaired to flowservice runs endpoint"
        confidence = 0.82
    elif "flow" in text or "dataflow" in text:
        candidate = "/data/foundation/flowservice/flows"
        reason = "flow alias repaired to flowservice flows endpoint"
        confidence = 0.8

    if not candidate:
        return _no_repair(method, original_url, params, "no safe endpoint-family alias matched")

    matched = endpoint_catalog.match(method, candidate)
    if not matched:
        return _no_repair(method, original_url, params, "repaired candidate was not in endpoint catalog")
    return {
        "repaired": True,
        "method": method,
        "url": candidate,
        "params": params,
        "original_url": original_url,
        "repaired_url": candidate,
        "reason": reason,
        "confidence": round(confidence, 4),
        "endpoint_id": matched.id,
    }


def _extract_batch_id(path: str) -> str | None:
    match = re.search(r"/batch(?:es)?/([^/]+)", path, flags=re.IGNORECASE)
    if match:
        return match.group(1)
    match = re.search(r"/batches/([^/]+)", path, flags=re.IGNORECASE)
    return match.group(1) if match else None


def _no_repair(method: str, url: str, params: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "repaired": False,
        "method": (method or "GET").upper(),
        "url": url,
        "params": params,
        "original_url": url,
        "repaired_url": None,
        "reason": reason,
        "confidence": 0.0,
    }
