from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from typing import Any

from .db import strip_sql_comments
from .trajectory import redact_secrets


COUNT_FIELD_NAMES = {"count", "cnt", "total", "row_count", "record_count"}
ID_SUFFIXES = ("_id", "id")
NAME_FIELD_NAMES = {"name", "display_name", "title", "label"}
STATUS_FIELD_NAMES = {"status", "state", "phase", "health"}
TIME_FIELD_MARKERS = ("time", "date", "timestamp", "created", "updated", "modified")


@dataclass(frozen=True)
class OptionalAPISkipDecision:
    skip: bool
    reason: str
    api_policy: str
    live_success_count: int
    sql_answer_complete: bool
    route_mode: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_sql_for_validation_cache(sql: str) -> str:
    """Normalize exactly equivalent SQL text for per-validator cache lookup."""

    cleaned = strip_sql_comments(str(sql or "")).strip().rstrip(";")
    return re.sub(r"\s+", " ", cleaned)


def clone_validation_result(result: Any) -> Any:
    return type(result)(bool(result.ok), list(result.errors), list(result.warnings), bool(result.repaired))


def compact_sql_result_for_intent(intent: str | None, payload: dict[str, Any], *, max_rows: int = 10) -> dict[str, Any]:
    rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
    normalized_intent = str(intent or "").strip().lower()
    shape = "rows"
    rows_preview: list[dict[str, Any]] = []
    key_fields: dict[str, Any] = {}

    if normalized_intent in {"count", "count_aggregation"} and rows:
        first = rows[0] if isinstance(rows[0], dict) else {}
        key_fields = {key: value for key, value in first.items() if _is_count_field(key)}
        rows_preview = [key_fields] if key_fields else [first]
        shape = "count"
    elif normalized_intent in {"list", "name", "id", "list/name/id", "show"}:
        rows_preview = [_select_fields(row, include=("id", "name")) for row in rows[:max_rows] if isinstance(row, dict)]
        shape = "key_fields"
    elif normalized_intent in {"status", "state"}:
        rows_preview = [_select_fields(row, include=("id", "name", "status")) for row in rows[:max_rows] if isinstance(row, dict)]
        shape = "status"
    elif normalized_intent in {"timestamp", "date", "when", "time"}:
        rows_preview = [_select_fields(row, include=("id", "name", "time")) for row in rows[:max_rows] if isinstance(row, dict)]
        shape = "timestamp"
    else:
        rows_preview = [dict(row) for row in rows[:max_rows] if isinstance(row, dict)]

    if not key_fields and rows_preview and isinstance(rows_preview[0], dict):
        key_fields = {
            key: value
            for key, value in rows_preview[0].items()
            if _is_count_field(key) or _is_id_field(key) or _is_name_field(key) or _is_status_field(key) or _is_time_field(key)
        }

    return {
        "ok": bool(payload.get("ok")),
        "row_count": payload.get("row_count", len(rows)),
        "evidence_shape": shape,
        "key_fields": key_fields,
        "rows_preview": rows_preview,
        "limited": bool(payload.get("limited")),
    }


def api_tool_cache_key(method: str, url: str, params: dict[str, Any] | None = None) -> str:
    signature = json.dumps(
        {
            "method": str(method or "GET").upper(),
            "url": str(url or ""),
            "params": params or {},
        },
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return "api_" + hashlib.sha256(signature.encode("utf-8")).hexdigest()[:16]


def should_skip_optional_api_call(
    *,
    api_policy: str | None,
    sql_answer_complete: bool,
    live_success_count: int,
    route_mode: str | None,
) -> OptionalAPISkipDecision:
    policy = str(api_policy or "").upper()
    mode = str(route_mode or "")
    if mode == "API_ONLY" or policy == "API_REQUIRED":
        return OptionalAPISkipDecision(False, "API is required by route or policy.", policy, live_success_count, sql_answer_complete, mode)
    if policy == "API_OPTIONAL" and sql_answer_complete and int(live_success_count or 0) == 0:
        return OptionalAPISkipDecision(
            True,
            "Optional API skipped because SQL evidence already answers the prompt and live_success_count=0.",
            policy,
            int(live_success_count or 0),
            True,
            mode,
        )
    return OptionalAPISkipDecision(False, "Optional API skip conditions were not met.", policy, int(live_success_count or 0), sql_answer_complete, mode)


def compact_api_outcome(payload: dict[str, Any], *, max_caveat_chars: int = 160) -> dict[str, Any]:
    parsed = payload.get("parsed_evidence") if isinstance(payload.get("parsed_evidence"), dict) else {}
    evidence_state = parsed.get("evidence_state") or payload.get("evidence_state") or ("dry_run_unavailable" if payload.get("dry_run") else "api_error")
    error_category = parsed.get("error_category") or payload.get("error_category") or evidence_state
    endpoint_family = parsed.get("endpoint_family") or payload.get("endpoint_family") or payload.get("endpoint")
    caveat_source = payload.get("error") or payload.get("result_preview") or parsed.get("safe_error_excerpt") or parsed.get("raw_preview") or ""
    return {
        "ok": bool(payload.get("ok")),
        "dry_run": bool(payload.get("dry_run")),
        "live_success": evidence_state == "live_success" or bool(payload.get("live_success")),
        "status_code": payload.get("status_code") or payload.get("status"),
        "evidence_state": evidence_state,
        "error_category": error_category,
        "endpoint_family": endpoint_family,
        "usable_evidence": bool(parsed.get("usable_evidence") or parsed.get("live_evidence_available")) and evidence_state == "live_success",
        "caveat": _safe_excerpt(caveat_source, max_chars=max_caveat_chars),
    }


def _select_fields(row: dict[str, Any], *, include: tuple[str, ...]) -> dict[str, Any]:
    selected: dict[str, Any] = {}
    for key, value in row.items():
        if ("id" in include and _is_id_field(key)) or ("name" in include and _is_name_field(key)):
            selected[key] = value
        elif "status" in include and _is_status_field(key):
            selected[key] = value
        elif "time" in include and _is_time_field(key):
            selected[key] = value
    return selected or dict(row)


def _is_count_field(key: str) -> bool:
    lowered = str(key).lower()
    return lowered in COUNT_FIELD_NAMES or lowered.endswith("_count") or lowered.endswith("count")


def _is_id_field(key: str) -> bool:
    lowered = str(key).lower()
    return lowered == "id" or lowered.endswith(ID_SUFFIXES)


def _is_name_field(key: str) -> bool:
    return str(key).lower() in NAME_FIELD_NAMES or str(key).lower().endswith("_name")


def _is_status_field(key: str) -> bool:
    return str(key).lower() in STATUS_FIELD_NAMES or str(key).lower().endswith("_status")


def _is_time_field(key: str) -> bool:
    lowered = str(key).lower()
    return any(marker in lowered for marker in TIME_FIELD_MARKERS)


def _safe_excerpt(value: Any, *, max_chars: int) -> str:
    text = str(redact_secrets(value or ""))
    text = re.sub(r"Authorization:\s*Bearer\s+[A-Za-z0-9._-]+", "[REDACTED_AUTH_HEADER]", text, flags=re.IGNORECASE)
    text = re.sub(r"\bBearer\s+[A-Za-z0-9._-]+", "[REDACTED_BEARER]", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(request-id|registryRequestId|x-request-id)\s*[:=]\s*[^,\s]+", r"\1=[REDACTED_ID]", text, flags=re.IGNORECASE)
    text = re.sub(r"[A-Za-z0-9]{3}\*\*\*", "[REDACTED_PREFIX]", text)
    text = " ".join(text.split())
    return text[:max_chars]
