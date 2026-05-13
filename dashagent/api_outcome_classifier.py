from __future__ import annotations

from collections import Counter
from typing import Any


OUTCOME_VALUES = {
    "live_success",
    "live_empty",
    "auth_error",
    "token_acquisition_failed",
    "scope_or_permission_issue",
    "sandbox_scope_issue",
    "endpoint_path_issue",
    "unresolved_path_param",
    "discovery_blocked_missing_id",
    "rate_limited",
    "malformed_response",
    "external_api_unavailable",
    "api_error",
}


def classify_api_outcome(
    result: dict[str, Any] | None = None,
    *,
    method: str | None = None,
    path: str | None = None,
    discovery_status: str | None = None,
) -> str:
    """Classify a live Adobe API attempt into one shared diagnostic outcome."""

    result = result or {}
    parsed = result.get("parsed_evidence") if isinstance(result.get("parsed_evidence"), dict) else {}
    candidate_path = str(path or result.get("endpoint") or parsed.get("path") or result.get("url") or "")
    if discovery_status == "discovery_blocked_missing_id":
        return "discovery_blocked_missing_id"
    if "{" in candidate_path or "}" in candidate_path:
        return "unresolved_path_param"

    error_category = str(result.get("error_category") or parsed.get("error_category") or parsed.get("evidence_state") or "")
    if error_category == "token_acquisition_failed":
        return "token_acquisition_failed"
    if error_category == "malformed_response":
        return "malformed_response"
    if error_category in {
        "endpoint_path_issue",
        "unresolved_path_param",
        "discovery_blocked_missing_id",
        "scope_or_permission_issue",
        "sandbox_scope_issue",
        "rate_limited",
        "external_api_unavailable",
    }:
        return error_category

    status_code = _status_code(result.get("status_code", parsed.get("status_code")))
    text = _combined_text(result, parsed)
    if status_code == 401:
        return "auth_error"
    if status_code == 403:
        return "sandbox_scope_issue" if _mentions_sandbox_scope(text) else "scope_or_permission_issue"
    if status_code == 404:
        return "endpoint_path_issue"
    if status_code == 429:
        return "rate_limited"
    if status_code is not None and status_code >= 500:
        if _mentions_endpoint_path_issue(text):
            return "endpoint_path_issue"
        if _mentions_sandbox_scope(text):
            return "sandbox_scope_issue"
        return "external_api_unavailable"
    if parsed.get("evidence_state") == "malformed_response":
        return "malformed_response"
    if parsed.get("evidence_state") == "live_empty":
        return "live_empty"
    if status_code is not None and 200 <= status_code < 300:
        return "live_success" if _has_usable_evidence(parsed) or result.get("ok") is True else "live_empty"
    if result.get("ok") is True:
        return "live_success"
    return "api_error"


def outcome_counts(rows: list[dict[str, Any]], key: str = "outcome") -> dict[str, int]:
    return dict(Counter(str(row.get(key) or "api_error") for row in rows))


def _status_code(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _combined_text(result: dict[str, Any], parsed: dict[str, Any]) -> str:
    parts = [
        result.get("error"),
        result.get("result_preview"),
        parsed.get("errors"),
        parsed.get("raw_preview"),
    ]
    return " ".join(str(part) for part in parts if part not in (None, "", [], {})).lower()


def _has_usable_evidence(parsed: dict[str, Any]) -> bool:
    if parsed.get("live_evidence_available") is True:
        return True
    for key in ("items", "ids", "names", "statuses", "timestamps"):
        if parsed.get(key):
            return True
    counts = parsed.get("counts")
    if isinstance(counts, dict):
        return any(_truthy_count(value) for value in counts.values())
    return False


def _truthy_count(value: Any) -> bool:
    try:
        return float(value) != 0
    except (TypeError, ValueError):
        return bool(value)


def _mentions_sandbox_scope(text: str) -> bool:
    return any(token in text for token in ("sandbox", "tenant", "ims", "org", "organization"))


def _mentions_endpoint_path_issue(text: str) -> bool:
    return any(
        token in text
        for token in (
            "not found",
            "not_found",
            "no route",
            "route",
            "path",
            "endpoint",
            "resource not found",
            "unknown resource",
            "uri",
            "url",
        )
    )
