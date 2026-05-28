from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .answer_slots import AnswerSlots


@dataclass(frozen=True)
class RenderedAnswer:
    answer: str
    shape: str
    rendered_fields: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)
    caveats: list[str] = field(default_factory=list)
    unsupported_claims_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def render_answer_slots(query: str, slots: AnswerSlots, evidence_quality: dict[str, Any] | None = None) -> RenderedAnswer:
    quality = evidence_quality or {}
    lowered = str(query or "").lower()
    caveats = _quality_caveats(slots, quality)

    if _asks_count(lowered) and slots.counts:
        if "local snapshot" in lowered or ((_asks_live_scope(lowered) or _asks_platform_scope(lowered)) and (slots.dry_run or slots.api_error)):
            answer = f"Local snapshot count: {slots.counts[0]}."
        else:
            answer = f"Count: {slots.counts[0]}."
        if caveats:
            answer = f"{answer} {' '.join(caveats)}"
        rendered = ["count", "scope"] if "local snapshot" in lowered else ["count"]
        return RenderedAnswer(answer, "count", rendered, caveats=caveats)

    if _asks_status(lowered) and (slots.important_rows or slots.important_items or slots.statuses):
        rows = slots.important_items or slots.important_rows
        answer = _render_rows(rows, include_status=True) if rows else "; ".join(slots.statuses[:5])
        answer = f"Status: {answer}."
        if caveats:
            answer = f"{answer} {' '.join(caveats)}"
        return RenderedAnswer(answer, "status", ["status", "name", "id"], caveats=caveats)

    if _asks_date(lowered) and slots.timestamps:
        answer = f"Date/time: {', '.join(slots.timestamps[:5])}."
        if caveats:
            answer = f"{answer} {' '.join(caveats)}"
        return RenderedAnswer(answer, "date", ["timestamp"], caveats=caveats)

    rows = slots.important_items or slots.important_rows or slots.api_items or slots.first_rows
    if rows:
        answer = f"Results: {_render_rows(rows, include_status=True)}."
        if caveats:
            answer = f"{answer} {' '.join(caveats)}"
        return RenderedAnswer(answer, "list", ["id", "name", "status", "timestamp"], caveats=caveats)

    if slots.entity_names or slots.entity_ids or slots.statuses or slots.timestamps:
        pieces = []
        if slots.entity_names:
            pieces.append("names: " + ", ".join(slots.entity_names[:5]))
        if slots.entity_ids:
            pieces.append("ids: " + ", ".join(slots.entity_ids[:5]))
        if slots.statuses:
            pieces.append("statuses: " + ", ".join(slots.statuses[:5]))
        if slots.timestamps:
            pieces.append("dates: " + ", ".join(slots.timestamps[:5]))
        answer = "Evidence: " + "; ".join(pieces) + "."
        if caveats:
            answer = f"{answer} {' '.join(caveats)}"
        return RenderedAnswer(answer, "evidence", ["entity", "status", "timestamp"], caveats=caveats)

    if "SQL_ZERO_ROWS" in set(quality.get("sql") or []):
        answer = "The local snapshot has no matching rows."
        if caveats:
            answer = f"{answer} {' '.join(caveats)}"
        return RenderedAnswer(answer, "empty", [], ["requested_evidence"], caveats)

    if caveats:
        return RenderedAnswer(" ".join(caveats), "caveat", [], ["requested_evidence"], caveats)

    return RenderedAnswer("No matching evidence was available from the executed SQL/API tools.", "empty", [], ["requested_evidence"])


def _quality_caveats(slots: AnswerSlots, quality: dict[str, Any]) -> list[str]:
    caveats: list[str] = []
    api_codes = set(quality.get("api") or [])
    sql_codes = set(quality.get("sql") or [])
    direct_sql_count_answer = (
        "SQL_DIRECT_ANSWER" in sql_codes
        and bool(slots.counts)
        and slots.sql_row_count is not None
        and not _asks_live_scope(slots.query.lower())
        and not _asks_platform_scope(slots.query.lower())
    )
    if slots.api_error or "API_ERROR" in api_codes:
        caveats.append("API unavailable/error; cannot verify live state.")
    if "API_LIVE_EMPTY" in api_codes and not direct_sql_count_answer:
        caveats.append("API returned no matching records for this query/scope.")
    if slots.dry_run:
        caveats.append("Live API verification was not executed because Adobe credentials are unavailable.")
    return _dedupe(caveats)


def _render_rows(rows: list[dict[str, Any]], *, include_status: bool) -> str:
    rendered: list[str] = []
    for row in rows[:5]:
        if not isinstance(row, dict):
            continue
        pieces: list[str] = []
        for key in ("id", "campaign_id", "segment_id", "schema_id", "audienceId", "audience_id"):
            if key in row and row[key] not in (None, ""):
                pieces.append(f"id={row[key]}")
                break
        for key in ("name", "title", "campaign_name", "segment_name", "displayName"):
            if key in row and row[key] not in (None, ""):
                pieces.append(f"name={row[key]}")
                break
        if include_status:
            for key in ("status", "state", "lifecycleStatus", "lifecycle_status"):
                if key in row and row[key] not in (None, ""):
                    pieces.append(f"status={row[key]}")
                    break
        for key in ("updatedTime", "updated_time", "createdTime", "created_time", "lastdeployedtime"):
            if key in row and row[key] not in (None, ""):
                pieces.append(f"{key}={row[key]}")
                break
        if not pieces:
            for key, value in list(row.items())[:4]:
                if value not in (None, "", [], {}):
                    pieces.append(f"{key}={value}")
        if pieces:
            rendered.append("{" + ", ".join(pieces[:5]) + "}")
    return "; ".join(rendered)


def _asks_count(text: str) -> bool:
    return any(token in text for token in ("count", "how many", "total", "number of"))


def _asks_status(text: str) -> bool:
    return any(token in text for token in ("status", "state", "active", "inactive", "failed", "succeeded"))


def _asks_date(text: str) -> bool:
    return any(token in text for token in ("when", "created", "updated", "date", "time", "deployed", "published"))


def _asks_live_scope(text: str) -> bool:
    return any(token in text for token in ("current", "live"))


def _asks_platform_scope(text: str) -> bool:
    return "platform" in text or "adobe experience platform" in text


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out
