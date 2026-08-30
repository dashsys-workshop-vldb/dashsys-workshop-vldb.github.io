from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


ALLOWED_SCHEMA_BINDING_OBJECT_TYPES = {
    "schema",
    "blueprint",
    "segment",
    "journey",
    "campaign",
    "batch",
    "dataset",
    "audience",
    "destination",
    "merge_policy",
    "class",
    "field",
    "relationship",
    "unknown",
}
ALLOWED_SCHEMA_BINDING_SCOPES = {"LOCAL_SNAPSHOT", "LIVE_API", "BOTH", "NONE"}


@dataclass
class SchemaBinding:
    binding_id: str
    semantic_object: str
    object_type: str
    source_scope: str
    table: str | None = None
    primary_id_fields: list[str] = field(default_factory=list)
    name_fields: list[str] = field(default_factory=list)
    status_fields: list[str] = field(default_factory=list)
    date_fields: list[str] = field(default_factory=list)
    relation_tables: list[str] = field(default_factory=list)
    required_for_slots: list[str] = field(default_factory=list)
    confidence_note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SchemaBindingPlan:
    bindings: list[SchemaBinding] = field(default_factory=list)
    binding_version: str = "v1"

    def to_dict(self) -> dict[str, Any]:
        return schema_binding_plan_to_dict(self)


def parse_schema_binding_plan(raw: dict[str, Any] | str | None) -> SchemaBindingPlan:
    if raw is None:
        return SchemaBindingPlan()
    payload = raw
    if isinstance(raw, str):
        import json

        payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("Schema binding plan must be an object.")
    version = str(payload.get("binding_version") or "v1").strip()
    if version != "v1":
        raise ValueError("binding_version must be v1.")
    bindings_raw = payload.get("bindings")
    if bindings_raw is None:
        bindings_raw = []
    if not isinstance(bindings_raw, list):
        raise ValueError("bindings must be a list.")
    return SchemaBindingPlan(bindings=[_parse_binding(item, index) for index, item in enumerate(bindings_raw, start=1)], binding_version=version)


def schema_binding_plan_to_dict(plan: SchemaBindingPlan | None) -> dict[str, Any] | None:
    if plan is None:
        return None
    return {
        "binding_version": plan.binding_version,
        "bindings": [binding.to_dict() for binding in plan.bindings],
    }


def _parse_binding(item: Any, index: int) -> SchemaBinding:
    if not isinstance(item, dict):
        raise ValueError(f"bindings[{index}] must be an object.")
    binding_id = str(item.get("binding_id") or f"b{index}").strip()
    if not binding_id:
        raise ValueError(f"bindings[{index}].binding_id is required.")
    object_type = str(item.get("object_type") or "unknown").strip().lower()
    if object_type not in ALLOWED_SCHEMA_BINDING_OBJECT_TYPES:
        raise ValueError(f"bindings[{index}].object_type must be one of {sorted(ALLOWED_SCHEMA_BINDING_OBJECT_TYPES)}.")
    source_scope = str(item.get("source_scope") or "NONE").strip().upper()
    if source_scope not in ALLOWED_SCHEMA_BINDING_SCOPES:
        raise ValueError(f"bindings[{index}].source_scope must be one of {sorted(ALLOWED_SCHEMA_BINDING_SCOPES)}.")
    table_raw = item.get("table")
    table = str(table_raw).strip() if table_raw is not None and str(table_raw).strip() else None
    confidence = item.get("confidence_note")
    return SchemaBinding(
        binding_id=binding_id,
        semantic_object=str(item.get("semantic_object") or "").strip(),
        object_type=object_type,
        source_scope=source_scope,
        table=table,
        primary_id_fields=_string_list(item.get("primary_id_fields")),
        name_fields=_string_list(item.get("name_fields")),
        status_fields=_string_list(item.get("status_fields")),
        date_fields=_string_list(item.get("date_fields")),
        relation_tables=_string_list(item.get("relation_tables")),
        required_for_slots=_string_list(item.get("required_for_slots")),
        confidence_note=str(confidence).strip() if confidence is not None and str(confidence).strip() else None,
    )


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]
