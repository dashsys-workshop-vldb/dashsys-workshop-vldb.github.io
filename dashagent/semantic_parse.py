from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


OPERATIONS = {
    "DEFINE",
    "EXPLAIN",
    "LIST",
    "COUNT",
    "LOOKUP",
    "STATUS",
    "DATE",
    "RELATIONSHIP",
    "COMPARE",
    "FORMAT_REQUEST",
    "META_LANGUAGE",
    "UNKNOWN",
}
TARGET_GROUNDINGS = {"SUPPORTED_DATA_OBJECT", "CONCEPTUAL_OBJECT", "META_LANGUAGE", "OUT_OF_DOMAIN", "UNKNOWN"}
OBJECT_FAMILIES = {"SCHEMA", "DATASET", "JOURNEY", "SEGMENT", "AUDIENCE", "TAG", "AUDIT", "MERGE_POLICY", "FLOW", "BATCH"}
EVIDENCE_NEEDS = {"NONE", "SQL", "API", "SQL_API", "UNKNOWN"}


@dataclass(frozen=True)
class SemanticTarget:
    text: str = ""
    grounding: str = "UNKNOWN"
    object_family: str | None = None
    instance_level: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "grounding", _coerce(self.grounding, TARGET_GROUNDINGS, "UNKNOWN"))
        family = str(self.object_family).upper() if self.object_family is not None else None
        object.__setattr__(self, "object_family", family if family in OBJECT_FAMILIES else None)


@dataclass(frozen=True)
class SemanticFilters:
    status: str | None = None
    date: str | None = None
    entity: str | None = None
    relationship: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("status", "date", "entity", "relationship"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, str(value).upper())


@dataclass(frozen=True)
class SemanticCapability:
    sql_match: bool = False
    api_match: bool = False
    api_families: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        object.__setattr__(self, "api_families", _dedupe([str(value).upper() for value in self.api_families]))


@dataclass(frozen=True)
class SemanticParse:
    operation: str = "UNKNOWN"
    target: SemanticTarget = field(default_factory=SemanticTarget)
    filters: SemanticFilters = field(default_factory=SemanticFilters)
    requested_fields: list[str] = field(default_factory=list)
    capability: SemanticCapability = field(default_factory=SemanticCapability)
    evidence_need: str = "UNKNOWN"
    no_tool_safe: bool = False
    confidence: float = 0.0
    supporting_spans: list[str] = field(default_factory=list)
    risk_codes: list[str] = field(default_factory=list)
    source: str = "UNKNOWN"

    def __post_init__(self) -> None:
        object.__setattr__(self, "operation", _coerce(self.operation, OPERATIONS, "UNKNOWN"))
        target = self.target if isinstance(self.target, SemanticTarget) else SemanticTarget(**dict(self.target))
        filters = self.filters if isinstance(self.filters, SemanticFilters) else SemanticFilters(**dict(self.filters))
        capability = self.capability if isinstance(self.capability, SemanticCapability) else SemanticCapability(**dict(self.capability))
        object.__setattr__(self, "target", target)
        object.__setattr__(self, "filters", filters)
        object.__setattr__(self, "capability", capability)
        object.__setattr__(self, "evidence_need", _coerce(self.evidence_need, EVIDENCE_NEEDS, "UNKNOWN"))
        object.__setattr__(self, "requested_fields", _dedupe([str(value).upper() for value in self.requested_fields]))
        object.__setattr__(self, "confidence", max(0.0, min(1.0, float(self.confidence or 0.0))))
        object.__setattr__(self, "supporting_spans", [str(value) for value in self.supporting_spans][:12])
        object.__setattr__(self, "risk_codes", _dedupe([str(value).upper() for value in self.risk_codes])[:12])
        object.__setattr__(self, "source", str(self.source or "UNKNOWN").upper())

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["confidence"] = round(float(self.confidence), 4)
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SemanticParse":
        return cls(
            operation=str(payload.get("operation") or "UNKNOWN"),
            target=SemanticTarget(**_dict(payload.get("target"))),
            filters=SemanticFilters(**_dict(payload.get("filters"))),
            requested_fields=_list(payload.get("requested_fields")),
            capability=SemanticCapability(**_dict(payload.get("capability"))),
            evidence_need=str(payload.get("evidence_need") or "UNKNOWN"),
            no_tool_safe=bool(payload.get("no_tool_safe")),
            confidence=float(payload.get("confidence") or 0.0),
            supporting_spans=_list(payload.get("supporting_spans")),
            risk_codes=_list(payload.get("risk_codes")),
            source=str(payload.get("source") or "UNKNOWN"),
        )


def _coerce(value: str, allowed: set[str], default: str) -> str:
    normalized = str(value or default).upper()
    return normalized if normalized in allowed else default


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _list(value: Any) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return out
