from __future__ import annotations

import difflib
import json
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

from .pioneer_model_sweep import DEFAULT_PIONEER_MODEL_SWEEP, GPT_LIGHT_BASELINE_CANDIDATES
from .trajectory import redact_secrets


PIONEER_CATALOG_ENDPOINTS = [
    {
        "name": "native_decoder",
        "url": "https://api.pioneer.ai/base-models?supports_inference=true&task_type=decoder",
        "headers": "x_api_key",
    },
    {
        "name": "native_inference",
        "url": "https://api.pioneer.ai/base-models?supports_inference=true",
        "headers": "x_api_key",
    },
    {
        "name": "openai_models_x_api_key",
        "url": "https://api.pioneer.ai/v1/models",
        "headers": "x_api_key",
    },
    {
        "name": "openai_models_bearer",
        "url": "https://api.pioneer.ai/v1/models",
        "headers": "bearer",
    },
]

CATALOG_FIELDS = [
    "id",
    "model_id",
    "name",
    "display_name",
    "slug",
    "provider",
    "supports_inference",
    "task_type",
    "context_window",
    "input_price",
    "output_price",
]


def discover_pioneer_model_catalog(
    api_key: str | None,
    *,
    timeout: int = 20,
    http_get: Callable[[str, dict[str, str], int], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    getter = http_get or _http_get_json
    endpoint_results: list[dict[str, Any]] = []
    if not api_key:
        endpoint_results = [
            {
                "name": endpoint["name"],
                "url": endpoint["url"],
                "ok": False,
                "status": None,
                "error": "PIONEER_API_KEY is not set",
            }
            for endpoint in PIONEER_CATALOG_ENDPOINTS
        ]
    else:
        for endpoint in PIONEER_CATALOG_ENDPOINTS:
            headers = _headers_for(endpoint["headers"], api_key)
            try:
                payload = getter(endpoint["url"], headers, timeout)
                endpoint_results.append(
                    redact_secrets(
                        {
                            "name": endpoint["name"],
                            "url": endpoint["url"],
                            "ok": True,
                            "status": 200,
                            "payload": payload,
                        }
                    )
                )
            except Exception as exc:
                endpoint_results.append(
                    redact_secrets(
                        {
                            "name": endpoint["name"],
                            "url": endpoint["url"],
                            "ok": False,
                            "status": getattr(exc, "code", None),
                            "error": f"{type(exc).__name__}: {exc}",
                        }
                    )
                )
    records: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for result in endpoint_results:
        if result.get("ok"):
            for record in extract_catalog_records(result.get("payload"), source=str(result.get("name") or "")):
                key = (str(record.get("model_id") or ""), str(record.get("source") or ""))
                if key not in seen:
                    seen.add(key)
                    records.append(record)
    suggestion = suggest_pioneer_model_id_map(desired_pioneer_model_mapping_names(), records)
    return {
        "endpoint_results": endpoint_results,
        "records": records,
        "decoder_or_inference_model_count": len(records),
        "mapping_suggestion": suggestion,
    }


def desired_pioneer_model_mapping_names() -> list[str]:
    desired: list[str] = []
    for name in [*GPT_LIGHT_BASELINE_CANDIDATES, *DEFAULT_PIONEER_MODEL_SWEEP]:
        if name not in desired:
            desired.append(name)
    return desired


def extract_catalog_records(payload: Any, *, source: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for item in _walk_catalog_items(payload):
        if not isinstance(item, dict):
            continue
        model_id = str(item.get("model_id") or item.get("id") or item.get("slug") or "").strip()
        if not model_id:
            continue
        provider = str(item.get("provider") or item.get("owned_by") or item.get("family") or "").strip()
        record = {
            "id": str(item.get("id") or "").strip(),
            "model_id": model_id,
            "name": str(item.get("name") or "").strip(),
            "display_name": str(item.get("display_name") or item.get("displayName") or item.get("label") or "").strip(),
            "slug": str(item.get("slug") or "").strip(),
            "provider": provider,
            "supports_inference": item.get("supports_inference"),
            "task_type": item.get("task_type"),
            "context_window": item.get("context_window") or item.get("context_length") or item.get("max_context_tokens"),
            "input_price": item.get("input_price") or item.get("input_cost") or _nested_price(item, "input"),
            "output_price": item.get("output_price") or item.get("output_cost") or _nested_price(item, "output"),
            "source": source,
            "raw": {key: item.get(key) for key in sorted(item) if key in set(CATALOG_FIELDS) | {"owned_by", "label", "family"}},
        }
        records.append(redact_secrets(record))
    return records


def suggest_pioneer_model_id_map(
    desired_names: list[str],
    records: list[dict[str, Any]],
    *,
    min_confidence: float = 0.78,
) -> dict[str, Any]:
    mapping: dict[str, str] = {}
    matches: dict[str, Any] = {}
    unmapped: list[str] = []
    for desired in desired_names:
        best = _best_record_match(desired, records)
        if best and best["confidence"] >= min_confidence:
            mapping[desired] = str(best["model_id"])
            matches[desired] = best
        else:
            unmapped.append(desired)
            matches[desired] = {
                "display_name": desired,
                "model_id": None,
                "confidence": best["confidence"] if best else 0.0,
                "reason": "low_confidence_match" if best else "no_catalog_match",
                "record": best.get("record") if best else None,
            }
    return {
        "mapping": mapping,
        "matches": matches,
        "unmapped": unmapped,
        "min_confidence": min_confidence,
    }


def write_pioneer_model_catalog_reports(
    report_dir: Path,
    endpoint_results: list[dict[str, Any]],
    records: list[dict[str, Any]],
    mapping_suggestion: dict[str, Any],
) -> dict[str, Path]:
    report_dir.mkdir(parents=True, exist_ok=True)
    catalog_json = report_dir / "pioneer_model_catalog.json"
    catalog_md = report_dir / "pioneer_model_catalog.md"
    mapping_json = report_dir / "pioneer_model_id_map_suggested.json"
    catalog_payload = {
        "endpoint_results": endpoint_results,
        "records": records,
        "decoder_or_inference_model_count": len(records),
    }
    catalog_json.write_text(json.dumps(redact_secrets(catalog_payload), indent=2, sort_keys=True), encoding="utf-8")
    mapping_json.write_text(json.dumps(redact_secrets(mapping_suggestion), indent=2, sort_keys=True), encoding="utf-8")
    catalog_md.write_text(_catalog_markdown(endpoint_results, records, mapping_suggestion), encoding="utf-8")
    return {"catalog_json": catalog_json, "catalog_md": catalog_md, "mapping_json": mapping_json}


def _http_get_json(url: str, headers: dict[str, str], timeout: int) -> dict[str, Any]:
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec - diagnostic user-requested endpoint.
            text = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:1200]
        raise RuntimeError(f"HTTP {exc.code}: {body}") from exc
    if not text.strip():
        return {}
    return json.loads(text)


def _headers_for(header_mode: str, api_key: str) -> dict[str, str]:
    if header_mode == "bearer":
        return {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    return {"X-API-Key": api_key, "Accept": "application/json"}


def _walk_catalog_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for value in payload for item in _walk_catalog_items(value)]
    if not isinstance(payload, dict):
        return []
    direct_keys = ("base_models", "models", "data", "items", "results")
    for key in direct_keys:
        value = payload.get(key)
        if isinstance(value, list):
            return [item for nested in value for item in _walk_catalog_items(nested)]
    if any(key in payload for key in ("id", "model_id", "slug")):
        return [payload]
    return []


def _nested_price(item: dict[str, Any], direction: str) -> Any:
    pricing = item.get("pricing")
    if isinstance(pricing, dict):
        return pricing.get(direction) or pricing.get(f"{direction}_price")
    return None


def _best_record_match(desired: str, records: list[dict[str, Any]]) -> dict[str, Any] | None:
    desired_norm = _normalize(desired)
    desired_tokens = set(_tokens(desired))
    best: dict[str, Any] | None = None
    for record in records:
        fields = [
            record.get("display_name"),
            record.get("name"),
            record.get("model_id"),
            record.get("id"),
            record.get("slug"),
        ]
        field_norms = [_normalize(str(value or "")) for value in fields if value]
        exact = desired_norm in field_norms
        token_score = max((_token_score(desired_tokens, set(_tokens(value))) for value in fields if value), default=0.0)
        fuzzy = max((difflib.SequenceMatcher(None, desired_norm, norm).ratio() for norm in field_norms), default=0.0)
        family_bonus = _family_bonus(desired, record)
        confidence = 1.0 if exact else max(fuzzy, token_score) * 0.9 + family_bonus
        confidence = min(1.0, round(confidence, 4))
        candidate = {
            "display_name": desired,
            "model_id": record.get("model_id"),
            "confidence": confidence,
            "reason": "exact_normalized_match" if exact else "fuzzy_family_match",
            "record": record,
        }
        if best is None or candidate["confidence"] > best["confidence"]:
            best = candidate
    return best


def _normalize(value: str) -> str:
    normalized = value.lower()
    normalized = normalized.replace("gpt", "gpt")
    normalized = re.sub(r"[^a-z0-9]+", "", normalized)
    return normalized


def _tokens(value: Any) -> list[str]:
    return [token for token in re.split(r"[^a-z0-9]+", str(value or "").lower()) if token]


def _token_score(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _family_bonus(desired: str, record: dict[str, Any]) -> float:
    text = " ".join(str(record.get(key) or "") for key in ("model_id", "display_name", "name", "provider", "slug")).lower()
    desired_lower = desired.lower()
    families = ("gpt", "claude", "deepseek", "qwen", "llama", "mistral", "gemma")
    for family in families:
        if family in desired_lower and family in text:
            return 0.08
    return 0.0


def _catalog_markdown(
    endpoint_results: list[dict[str, Any]],
    records: list[dict[str, Any]],
    mapping_suggestion: dict[str, Any],
) -> str:
    lines = [
        "# Pioneer Model Catalog",
        "",
        "Secrets are redacted. Mapping suggestions are conservative and only high-confidence matches are used.",
        "",
        "## Endpoint Results",
        "",
        "| Endpoint | OK | Status | Error |",
        "|---|---:|---:|---|",
    ]
    for result in endpoint_results:
        lines.append(
            f"| {result.get('name')} | {bool(result.get('ok'))} | {result.get('status')} | {str(result.get('error') or '')[:180]} |"
        )
    lines.extend(
        [
            "",
            f"Decoder/inference-capable model records extracted: {len(records)}",
            "",
            "## Mapping Suggestion",
            "",
            "| Display Name | Model ID | Confidence | Reason |",
            "|---|---|---:|---|",
        ]
    )
    for display, match in (mapping_suggestion.get("matches") or {}).items():
        lines.append(
            f"| {display} | {match.get('model_id') or ''} | {match.get('confidence')} | {match.get('reason')} |"
        )
    return "\n".join(lines) + "\n"
