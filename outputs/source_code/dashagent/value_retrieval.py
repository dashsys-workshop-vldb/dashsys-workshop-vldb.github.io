from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from rapidfuzz import fuzz, process

from .db import DuckDBDatabase, quote_ident
from .query_tokens import QueryTokens
from .schema_index import SchemaIndex
from .trajectory import redact_secrets


HIGH_SIGNAL_COLUMN_PARTS = ("id", "name", "status", "state", "title", "label", "category", "metric", "schema", "batch")
_VALUE_INDEX_L1: dict[str, dict[str, Any]] = {}


@dataclass(frozen=True)
class EntityMention:
    text: str
    kind: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ValueMatch:
    mention: str
    kind: str
    matched_table: str
    matched_column: str
    matched_value: str
    confidence: float
    match_type: str
    retrieval_cost: dict[str, Any]
    used_for: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def extract_query_values(query: str, query_tokens: QueryTokens) -> list[EntityMention]:
    mentions: list[EntityMention] = []
    for value in query_tokens.quoted_entities:
        mentions.append(EntityMention(value, "quoted_entity"))
    for value in query_tokens.batch_ids:
        mentions.append(EntityMention(value, "batch_id"))
    for value in query_tokens.schema_ids:
        mentions.append(EntityMention(value, "schema_id"))
    for value in query_tokens.metric_names:
        mentions.append(EntityMention(value, "metric_name"))
    for value in query_tokens.dates:
        mentions.append(EntityMention(value, "date"))
    for value in query_tokens.statuses:
        mentions.append(EntityMention(value, "status"))
    for value in query_tokens.named_entities:
        mentions.append(EntityMention(value, "named_entity"))
    for value in re.findall(r"\b[A-Z0-9]{20,32}\b|\b[0-9a-f]{24}\b", query):
        mentions.append(EntityMention(value, "id"))
    return _dedupe_mentions(mentions)


def build_value_index(
    db: DuckDBDatabase,
    schema_index: SchemaIndex,
    cache_dir: Path,
    *,
    candidate_tables: list[str] | None = None,
    max_tables: int = 6,
    max_columns: int = 18,
    max_rows_per_column: int = 500,
    max_ms: int = 250,
) -> dict[str, Any]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    table_key = ",".join(candidate_tables or sorted(schema_index.tables)[:max_tables])
    key = f"{table_key}|{max_tables}|{max_columns}|{max_rows_per_column}|{max_ms}"
    if key in _VALUE_INDEX_L1:
        cached = dict(_VALUE_INDEX_L1[key])
        cached["cache_hit"] = True
        return cached
    disk_path = cache_dir / ("value_index_" + str(abs(hash(key))) + ".json")
    if disk_path.exists():
        payload = json.loads(disk_path.read_text(encoding="utf-8"))
        payload["cache_hit"] = True
        _VALUE_INDEX_L1[key] = payload
        return payload

    started = time.perf_counter()
    values: list[dict[str, Any]] = []
    scanned_tables = 0
    scanned_columns = 0
    budget_exceeded = False
    selected_tables = [table for table in (candidate_tables or sorted(schema_index.tables)) if table in schema_index.tables][:max_tables]
    for table in selected_tables:
        scanned_tables += 1
        for column in schema_index.columns_for(table):
            if scanned_columns >= max_columns:
                budget_exceeded = True
                break
            if not _is_high_signal_column(column):
                continue
            elapsed_ms = (time.perf_counter() - started) * 1000
            if elapsed_ms > max_ms:
                budget_exceeded = True
                break
            sql = (
                f"SELECT DISTINCT {quote_ident(column)} AS value FROM {quote_ident(table)} "
                f"WHERE {quote_ident(column)} IS NOT NULL LIMIT {int(max_rows_per_column)}"
            )
            result = db.execute_sql(sql, allow_full_result=True)
            scanned_columns += 1
            if not result.get("ok"):
                continue
            for row in result.get("rows", [])[:max_rows_per_column]:
                value = row.get("value")
                if value not in (None, ""):
                    values.append({"table": table, "column": column, "value": str(value)})
        if budget_exceeded:
            break
    elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
    payload = {
        "values": values,
        "cache_hit": False,
        "cache_path": str(disk_path),
        "scanned_tables": scanned_tables,
        "scanned_columns": scanned_columns,
        "retrieval_ms": elapsed_ms,
        "value_retrieval_budget_exceeded": budget_exceeded or elapsed_ms > max_ms,
        "budget": {
            "max_tables": max_tables,
            "max_columns": max_columns,
            "max_rows_per_column": max_rows_per_column,
            "max_ms": max_ms,
        },
    }
    disk_path.write_text(json.dumps(redact_secrets(payload), indent=2, sort_keys=True), encoding="utf-8")
    _VALUE_INDEX_L1[key] = payload
    return payload


def retrieve_value_matches(query_values: list[EntityMention], value_index: dict[str, Any]) -> list[ValueMatch]:
    rows = value_index.get("values", [])
    normalized_to_rows: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        normalized_to_rows.setdefault(_normalize_value(row.get("value")), []).append(row)
    matches: list[ValueMatch] = []
    cost = {
        "cache_hit": value_index.get("cache_hit", False),
        "retrieval_ms": value_index.get("retrieval_ms", 0.0),
        "budget_exceeded": value_index.get("value_retrieval_budget_exceeded", False),
    }
    choices = [str(row.get("value")) for row in rows]
    for mention in query_values:
        normalized = _normalize_value(mention.text)
        exact_rows = [row for row in rows if str(row.get("value")) == mention.text]
        normalized_rows = normalized_to_rows.get(normalized, []) if not exact_rows else []
        if exact_rows:
            source_rows = exact_rows[:3]
            match_type = "exact"
            confidence = 1.0
        elif normalized_rows:
            source_rows = normalized_rows[:3]
            match_type = "normalized"
            confidence = 0.94
        else:
            fuzzy = process.extractOne(mention.text, choices, scorer=fuzz.WRatio) if choices else None
            if not fuzzy or fuzzy[1] < 92:
                continue
            source_rows = [row for row in rows if str(row.get("value")) == fuzzy[0]][:1]
            match_type = "fuzzy"
            confidence = round(float(fuzzy[1]) / 100.0, 4)
        for row in source_rows:
            matches.append(
                ValueMatch(
                    mention=mention.text,
                    kind=mention.kind,
                    matched_table=str(row.get("table")),
                    matched_column=str(row.get("column")),
                    matched_value=str(row.get("value")),
                    confidence=confidence,
                    match_type=match_type,
                    retrieval_cost=cost,
                    used_for=_used_for(mention.kind, str(row.get("column"))),
                )
            )
    return matches


def value_retrieval_summary(query_values: list[EntityMention], value_index: dict[str, Any], matches: list[ValueMatch]) -> dict[str, Any]:
    return redact_secrets(
        {
            "active": True,
            "query_value_count": len(query_values),
            "matches": [match.to_dict() for match in matches[:12]],
            "match_count": len(matches),
            "cache_hit": value_index.get("cache_hit", False),
            "cache_path": value_index.get("cache_path"),
            "scanned_tables": value_index.get("scanned_tables", 0),
            "scanned_columns": value_index.get("scanned_columns", 0),
            "retrieval_ms": value_index.get("retrieval_ms", 0.0),
            "value_retrieval_budget_exceeded": value_index.get("value_retrieval_budget_exceeded", False),
            "budget": value_index.get("budget", {}),
        }
    )


def _is_high_signal_column(column: str) -> bool:
    lowered = column.lower()
    return any(part in lowered for part in HIGH_SIGNAL_COLUMN_PARTS)


def _normalize_value(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def _used_for(kind: str, column: str) -> str:
    lowered = column.lower()
    if kind in {"batch_id", "schema_id", "id"} or lowered.endswith("id"):
        return "api_param"
    if "name" in lowered or "status" in lowered or "state" in lowered:
        return "sql_filter"
    return "answer_grounding"


def _dedupe_mentions(mentions: list[EntityMention]) -> list[EntityMention]:
    result = []
    seen: set[tuple[str, str]] = set()
    for mention in mentions:
        key = (mention.text.lower(), mention.kind)
        if mention.text and key not in seen:
            result.append(mention)
            seen.add(key)
    return result
