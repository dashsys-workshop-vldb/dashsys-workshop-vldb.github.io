from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .config import Config, DEFAULT_CONFIG
from .db import DuckDBDatabase


ID_SUFFIXES = ("id", "_id", "guid", "uuid", "key")
BRIDGE_PREFIXES = ("br_", "hkg_br_", "bridge_", "xref_", "map_")


@dataclass(frozen=True)
class JoinHint:
    left_table: str
    left_column: str
    right_table: str
    right_column: str
    confidence: float
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SchemaIndex:
    tables: dict[str, dict[str, Any]]
    join_hints: list[JoinHint] = field(default_factory=list)
    bridge_tables: list[str] = field(default_factory=list)

    @classmethod
    def build(cls, db: DuckDBDatabase) -> "SchemaIndex":
        tables: dict[str, dict[str, Any]] = {}
        for table in db.list_tables():
            described = db.describe_table(table)
            columns = [
                {
                    "name": row["column_name"],
                    "type": row["column_type"],
                    "is_id_like": is_id_column(row["column_name"]),
                    "is_name_like": is_name_column(row["column_name"]),
                }
                for row in described
            ]
            id_columns = [column["name"] for column in columns if column["is_id_like"]]
            tables[table] = {
                "columns": columns,
                "id_columns": id_columns,
                "primary_like_id": detect_primary_like_id(table, id_columns),
                "is_bridge": is_bridge_table(table, [column["name"] for column in columns]),
            }
        bridge_tables = [table for table, meta in tables.items() if meta["is_bridge"]]
        join_hints = build_join_hints(tables)
        join_hints.extend(curated_join_hints(tables))
        deduped = dedupe_join_hints(join_hints)
        return cls(tables=tables, join_hints=deduped, bridge_tables=bridge_tables)

    def compact_summary(self, max_columns_per_table: int = 24) -> dict[str, Any]:
        return {
            "table_count": len(self.tables),
            "bridge_tables": self.bridge_tables,
            "tables": {
                table: {
                    "columns": [column["name"] for column in meta["columns"][:max_columns_per_table]],
                    "id_columns": meta["id_columns"],
                    "primary_like_id": meta["primary_like_id"],
                    "is_bridge": meta["is_bridge"],
                }
                for table, meta in self.tables.items()
            },
            "join_hints": [hint.to_dict() for hint in self.join_hints],
        }

    def columns_for(self, table: str) -> list[str]:
        return [column["name"] for column in self.tables.get(table, {}).get("columns", [])]

    def table_exists(self, table: str) -> bool:
        return table in self.tables

    def column_exists(self, table: str, column: str) -> bool:
        return normalize_name(column) in {normalize_name(c) for c in self.columns_for(table)}

    def selected_join_hints(self, selected_tables: list[str]) -> list[dict[str, Any]]:
        selected = set(selected_tables)
        return [
            hint.to_dict()
            for hint in self.join_hints
            if hint.left_table in selected or hint.right_table in selected
        ]

    def save(self, config: Config | None = None) -> tuple[Path, Path]:
        cfg = config or DEFAULT_CONFIG
        cfg.outputs_dir.mkdir(parents=True, exist_ok=True)
        schema_path = cfg.outputs_dir / "schema_summary.json"
        graph_path = cfg.outputs_dir / "join_graph.json"
        schema_path.write_text(
            json.dumps(self.compact_summary(max_columns_per_table=200), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        graph_payload = {
            "nodes": list(self.tables),
            "edges": [hint.to_dict() for hint in self.join_hints],
        }
        graph_path.write_text(json.dumps(graph_payload, indent=2, sort_keys=True), encoding="utf-8")
        return schema_path, graph_path


def normalize_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def singularize(name: str) -> str:
    return name[:-1] if name.endswith("s") else name


def is_id_column(column: str) -> bool:
    lowered = column.lower()
    normalized = normalize_name(column)
    return (
        lowered == "id"
        or lowered.endswith(ID_SUFFIXES)
        or normalized.endswith("id")
        or normalized.endswith("guid")
    )


def is_name_column(column: str) -> bool:
    lowered = column.lower()
    return any(token in lowered for token in ["name", "title", "label", "display"])


def detect_primary_like_id(table: str, id_columns: list[str]) -> str | None:
    if not id_columns:
        return None
    table_root = normalize_name(table)
    for prefix in ["dim", "fact", "hkg", "br"]:
        if table_root.startswith(prefix):
            table_root = table_root[len(prefix) :]
    table_root = singularize(table_root)
    for column in id_columns:
        col = normalize_name(column)
        if col == "id" or col == f"{table_root}id" or table_root in col:
            return column
    return id_columns[0]


def is_bridge_table(table: str, columns: list[str]) -> bool:
    lowered = table.lower()
    if lowered.startswith(BRIDGE_PREFIXES) or "_br_" in lowered or lowered.startswith("br"):
        return True
    id_like_count = sum(1 for column in columns if is_id_column(column))
    return id_like_count >= 2 and len(columns) <= 12


def build_join_hints(tables: dict[str, dict[str, Any]]) -> list[JoinHint]:
    hints: list[JoinHint] = []
    table_columns = {
        table: {normalize_name(column["name"]): column["name"] for column in meta["columns"]}
        for table, meta in tables.items()
    }

    for left_table, left_meta in tables.items():
        left_primary = left_meta.get("primary_like_id")
        if not left_primary:
            continue
        left_primary_norm = normalize_name(left_primary)
        left_root = normalized_table_root(left_table)
        for right_table, right_columns in table_columns.items():
            if left_table == right_table:
                continue
            for right_norm, right_column in right_columns.items():
                if right_norm == left_primary_norm:
                    confidence = 0.9
                    reason = "Matching ID-like column name."
                elif right_norm == f"{left_root}id" or (left_root and right_norm.endswith(f"{left_root}id")):
                    confidence = 0.75
                    reason = "Foreign-key-looking column references table root."
                else:
                    continue
                hints.append(
                    JoinHint(
                        left_table=left_table,
                        left_column=left_primary,
                        right_table=right_table,
                        right_column=right_column,
                        confidence=confidence,
                        reason=reason,
                    )
                )
    return hints


def normalized_table_root(table: str) -> str:
    root = normalize_name(table)
    for prefix in ["dim", "fact", "hkg", "br"]:
        if root.startswith(prefix):
            root = root[len(prefix) :]
    return singularize(root)


def curated_join_hints(tables: dict[str, dict[str, Any]]) -> list[JoinHint]:
    """Curated patterns are schema-aware and only emitted when columns exist."""
    candidates = [
        ("dim_campaign", "campaign_id", "br_campaign_segment", "campaign_id", "Campaign to segment bridge."),
        ("dim_segment", "segment_id", "br_campaign_segment", "segment_id", "Campaign to segment bridge."),
        ("dim_segment", "segment_id", "hkg_br_segment_target", "segment_id", "Segment to target bridge."),
        ("dim_target", "target_id", "hkg_br_segment_target", "target_id", "Segment to target bridge."),
        ("dim_connector", "connector_id", "dim_target", "connector_id", "Target belongs to connector."),
        ("dim_collection", "collection_id", "dim_property", "collection_id", "Collection contains properties."),
        ("dim_blueprint", "blueprint_id", "dim_collection", "blueprint_id", "Collection belongs to blueprint."),
    ]
    hints: list[JoinHint] = []
    for left_table, left_column, right_table, right_column, reason in candidates:
        actual_left_column = find_actual_column(tables.get(left_table, {}), left_column)
        actual_right_column = find_actual_column(tables.get(right_table, {}), right_column)
        if (
            left_table in tables
            and right_table in tables
            and actual_left_column
            and actual_right_column
        ):
            hints.append(
                JoinHint(
                    left_table,
                    actual_left_column,
                    right_table,
                    actual_right_column,
                    0.98,
                    f"Curated: {reason}",
                )
            )
    return hints


def has_column(table_meta: dict[str, Any], column_name: str) -> bool:
    return find_actual_column(table_meta, column_name) is not None


def find_actual_column(table_meta: dict[str, Any], column_name: str) -> str | None:
    wanted = normalize_name(column_name)
    for column in table_meta.get("columns", []):
        if normalize_name(column["name"]) == wanted:
            return column["name"]
    return None


def dedupe_join_hints(hints: list[JoinHint]) -> list[JoinHint]:
    by_key: dict[tuple[str, str, str, str], JoinHint] = {}
    for hint in hints:
        key = (hint.left_table, hint.left_column, hint.right_table, hint.right_column)
        reverse = (hint.right_table, hint.right_column, hint.left_table, hint.left_column)
        existing = by_key.get(key) or by_key.get(reverse)
        if existing is None or hint.confidence > existing.confidence:
            by_key[key] = hint
    return sorted(by_key.values(), key=lambda h: (-h.confidence, h.left_table, h.right_table))
