from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any


SCHEMA_TABLE_ALIAS_CATALOG: dict[str, str] = {
    "schema": "dim_blueprint",
    "schemas": "dim_blueprint",
    "schema record": "dim_blueprint",
    "schema records": "dim_blueprint",
    "xdm schema": "dim_blueprint",
    "xdm schemas": "dim_blueprint",
    "blueprint": "dim_blueprint",
    "blueprints": "dim_blueprint",
    "journey": "dim_campaign",
    "journeys": "dim_campaign",
    "campaign": "dim_campaign",
    "campaigns": "dim_campaign",
    "message": "dim_campaign",
    "messages": "dim_campaign",
    "campaign activity": "dim_campaign",
    "campaign activities": "dim_campaign",
    "segment": "dim_segment",
    "segments": "dim_segment",
    "audience": "dim_segment",
    "audiences": "dim_segment",
    "collection": "dim_collection",
    "collections": "dim_collection",
    "dataset": "dim_collection",
    "datasets": "dim_collection",
}


TABLE_ALIAS_GROUPS: dict[str, list[str]] = {
    "dim_blueprint": ["schemas", "schema records", "XDM schemas", "blueprints"],
    "dim_campaign": ["journeys", "campaigns", "messages", "campaign activities"],
    "dim_segment": ["segments", "audiences"],
    "dim_collection": ["collections", "datasets"],
}


@dataclass
class SchemaGroundingResult:
    bindings: list[dict[str, Any]] = field(default_factory=list)
    rejected_unknown_tables: list[str] = field(default_factory=list)
    rejected_unknown_fields: list[dict[str, str]] = field(default_factory=list)

    @property
    def used(self) -> bool:
        return bool(self.bindings)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def resolve_table_alias(table_name: str, allowed_tables: set[str] | list[str]) -> str | None:
    allowed = {str(item) for item in allowed_tables}
    by_norm = {_norm(item): item for item in allowed}
    raw = str(table_name or "").strip()
    if not raw:
        return None
    exact = by_norm.get(_norm(raw))
    if exact:
        return exact
    mapped = SCHEMA_TABLE_ALIAS_CATALOG.get(_norm_phrase(raw))
    if mapped and mapped in allowed:
        return mapped
    return None


def table_aliases_for(table_name: str) -> list[str]:
    return list(TABLE_ALIAS_GROUPS.get(str(table_name or ""), []))


def bind_semantic_ir_schema_aliases(plan: Any, allowed_schema_card: list[dict[str, Any]]) -> SchemaGroundingResult:
    allowed_tables = {str(row.get("table") or "") for row in allowed_schema_card if str(row.get("table") or "")}
    columns_by_table = {
        str(row.get("table") or ""): [str(column) for column in row.get("columns") or []]
        for row in allowed_schema_card
        if str(row.get("table") or "")
    }
    result = SchemaGroundingResult()
    for task in list(getattr(plan, "tasks", []) or []):
        local_query = getattr(task, "local_query", None)
        if local_query is None:
            continue
        original_table = str(getattr(local_query, "table", "") or "").strip()
        resolved_table = resolve_table_alias(original_table, allowed_tables)
        if resolved_table is None:
            if original_table and _norm(original_table) not in {_norm(table) for table in allowed_tables}:
                result.rejected_unknown_tables.append(original_table)
            continue
        if resolved_table != original_table:
            setattr(local_query, "table", resolved_table)
            result.bindings.append(
                {
                    "type": "table",
                    "task_id": getattr(task, "task_id", None),
                    "from_table": original_table,
                    "to_table": resolved_table,
                    "reason": "schema_alias_catalog",
                }
            )
        _bind_fields(local_query, resolved_table, columns_by_table.get(resolved_table, []), result, getattr(task, "task_id", None))
    try:
        setattr(plan, "schema_alias_bindings", list(result.bindings))
    except Exception:
        pass
    return result


def _bind_fields(local_query: Any, table: str, columns: list[str], result: SchemaGroundingResult, task_id: str | None) -> None:
    if not columns:
        return
    field_lookup = {_norm(column): column for column in columns}
    rebound_fields = []
    for field in list(getattr(local_query, "fields", []) or []):
        resolved = _resolve_field_alias(field, table, field_lookup)
        if resolved is None:
            result.rejected_unknown_fields.append({"task_id": str(task_id or ""), "table": table, "field": str(field)})
            rebound_fields.append(field)
            continue
        if resolved != field:
            result.bindings.append({"type": "field", "task_id": task_id, "table": table, "from_field": field, "to_field": resolved, "reason": "field_alias_catalog"})
        rebound_fields.append(resolved)
    try:
        setattr(local_query, "fields", rebound_fields)
    except Exception:
        pass
    for item in list(getattr(local_query, "filters", []) or []):
        field = str(getattr(item, "field", "") or "")
        resolved = _resolve_field_alias(field, table, field_lookup)
        if resolved is None:
            result.rejected_unknown_fields.append({"task_id": str(task_id or ""), "table": table, "field": field})
            continue
        if resolved != field:
            result.bindings.append({"type": "field", "task_id": task_id, "table": table, "from_field": field, "to_field": resolved, "reason": "field_alias_catalog"})
            try:
                setattr(item, "field", resolved)
            except Exception:
                pass


def _resolve_field_alias(field_name: str, table: str, field_lookup: dict[str, str]) -> str | None:
    raw = str(field_name or "").strip()
    if not raw:
        return None
    exact = field_lookup.get(_norm(raw))
    if exact:
        return exact
    candidates = _field_alias_candidates(raw, table)
    for candidate in candidates:
        resolved = field_lookup.get(_norm(candidate))
        if resolved:
            return resolved
    return None


def _field_alias_candidates(field_name: str, table: str) -> list[str]:
    key = _norm_phrase(field_name)
    common = {
        "id": ["ID"],
        "name": ["NAME"],
        "title": ["NAME"],
        "display name": ["NAME"],
        "status": ["STATUS", "STATE", "LIFECYCLESTATUS"],
        "state": ["STATE", "STATUS", "LIFECYCLESTATUS"],
        "created": ["CREATEDTIME", "STARTDATE"],
        "created at": ["CREATEDTIME", "STARTDATE"],
        "updated": ["UPDATEDTIME"],
        "updated at": ["UPDATEDTIME"],
        "published": ["LASTDEPLOYEDTIME", "UPDATEDTIME", "STARTDATE"],
        "published at": ["LASTDEPLOYEDTIME", "UPDATEDTIME", "STARTDATE"],
        "published date": ["LASTDEPLOYEDTIME", "UPDATEDTIME", "STARTDATE"],
        "date": ["LASTDEPLOYEDTIME", "UPDATEDTIME", "STARTDATE"],
        "row count": ["ROWCOUNT", "TOTALMEMBERS"],
        "count": ["ROWCOUNT", "TOTALMEMBERS"],
    }
    by_table = {
        "dim_blueprint": {
            "schema id": ["BLUEPRINTID"],
            "blueprint id": ["BLUEPRINTID"],
            "class": ["CLASS"],
        },
        "dim_campaign": {
            "campaign id": ["CAMPAIGNID"],
            "journey id": ["CAMPAIGNID"],
        },
        "dim_segment": {
            "segment id": ["SEGMENTID"],
            "members": ["TOTALMEMBERS"],
            "total members": ["TOTALMEMBERS"],
        },
        "dim_collection": {
            "collection id": ["COLLECTIONID"],
            "dataset id": ["COLLECTIONID"],
        },
    }
    return [*common.get(key, []), *by_table.get(table, {}).get(key, [])]


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def _norm_phrase(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()
