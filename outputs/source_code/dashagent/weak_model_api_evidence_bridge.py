from __future__ import annotations

from typing import Any

from .trajectory import redact_secrets


def build_api_evidence(endpoint_id: str, api_result: dict[str, Any] | None) -> dict[str, Any]:
    result = api_result if isinstance(api_result, dict) else {}
    parsed = result.get("parsed_evidence") if isinstance(result.get("parsed_evidence"), dict) else {}
    state = str(parsed.get("evidence_state") or result.get("evidence_state") or "").lower()
    ok = bool(result.get("ok"))
    live_empty = state == "live_empty" or bool(parsed.get("live_empty"))
    api_error = bool(result and not ok and not result.get("dry_run")) or state == "api_error"
    live_success = ok and not live_empty and not api_error
    evidence = {
        "endpoint_id": endpoint_id,
        "endpoint": result.get("endpoint") or result.get("url"),
        "outcome": state or ("live_success" if live_success else "live_empty" if live_empty else "api_error" if api_error else "dry_run_unavailable" if result.get("dry_run") else "unknown"),
        "live_success": live_success,
        "live_empty": live_empty,
        "api_error": api_error,
        "dry_run": bool(result.get("dry_run")),
        "ids": _values(parsed, result, ("ids", "id_values", "key_ids")),
        "names": _values(parsed, result, ("names", "name_values", "key_names")),
        "statuses": _values(parsed, result, ("statuses", "status_values")),
        "timestamps": _values(parsed, result, ("timestamps", "timestamp_values")),
        "counts": _values(parsed, result, ("counts", "count_values")),
        "error": result.get("error") if api_error or result.get("dry_run") else None,
    }
    return redact_secrets(evidence)


def _values(parsed: dict[str, Any], result: dict[str, Any], keys: tuple[str, ...]) -> list[Any]:
    collected: list[Any] = []
    for source in (parsed, result):
        for key in keys:
            value = source.get(key)
            if isinstance(value, list):
                collected.extend(item for item in value if item is not None)
            elif value is not None:
                collected.append(value)
    return _dedupe(collected)


def _dedupe(values: list[Any]) -> list[Any]:
    seen = set()
    deduped = []
    for value in values:
        text = str(value)
        if text not in seen:
            seen.add(text)
            deduped.append(value)
    return deduped[:10]
