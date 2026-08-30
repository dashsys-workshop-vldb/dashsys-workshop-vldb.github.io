from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from .query_normalizer import normalize_query


STATUS_WORDS = {
    "active",
    "completed",
    "deployed",
    "draft",
    "failed",
    "inactive",
    "live",
    "processing",
    "published",
    "queued",
    "redeployed",
    "success",
    "succeeded",
}

DOMAIN_TERMS = {
    "audit": ["audit", "created", "download"],
    "batch": ["batch", "file", "download"],
    "destination_dataflow": ["activation", "connector", "dataflow", "destination", "flow", "target"],
    "journey_campaign": ["campaign", "draft", "inactive", "journey", "live", "published"],
    "merge_policy": ["merge", "policy"],
    "observability": ["batchsuccess", "ingestion", "metric", "observability", "recordsuccess", "timeseries"],
    "property_field": ["attribute", "field", "property"],
    "schema_dataset": ["blueprint", "collection", "dataset", "schema"],
    "segment_audience": ["audience", "profile", "segment"],
    "tags": ["category", "tag", "uncategorized"],
}


@dataclass(frozen=True)
class QueryTokens:
    original: str
    normalized: str
    matching_text: str
    words: list[str] = field(default_factory=list)
    quoted_entities: list[str] = field(default_factory=list)
    named_entities: list[str] = field(default_factory=list)
    uuids: list[str] = field(default_factory=list)
    batch_ids: list[str] = field(default_factory=list)
    schema_ids: list[str] = field(default_factory=list)
    dates: list[str] = field(default_factory=list)
    date_ranges: list[tuple[str, str]] = field(default_factory=list)
    metric_names: list[str] = field(default_factory=list)
    field_paths: list[str] = field(default_factory=list)
    statuses: list[str] = field(default_factory=list)
    domain_tokens: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def compact(self) -> dict[str, Any]:
        payload = {
            "quoted_entities": self.quoted_entities[:3],
            "named_entities": self.named_entities[:3],
            "ids": len(set(self.uuids + self.batch_ids + self.schema_ids)),
            "dates": self.dates[:2],
            "metrics": self.metric_names[:2],
            "field_paths": self.field_paths[:2],
            "statuses": self.statuses[:4],
            "domains": self.domain_tokens[:5],
        }
        return {key: value for key, value in payload.items() if value not in ([], {}, "", 0, None)}


def extract_query_tokens(original: str, normalized: dict[str, Any] | str | None = None) -> QueryTokens:
    if isinstance(normalized, dict):
        norm_payload = normalized
    elif isinstance(normalized, str):
        norm_payload = {"normalized": normalized, "matching_text": normalized.lower()}
    else:
        norm_payload = normalize_query(original)
    normalized_text = str(norm_payload.get("normalized") or original)
    matching_text = str(norm_payload.get("matching_text") or normalized_text.lower())

    quoted = dedupe(
        value.strip()
        for pair in re.findall(r"'([^']+)'|\"([^\"]+)\"", normalized_text)
        for value in pair
        if value.strip()
    )
    named = extract_named_entities(normalized_text)
    uuids = dedupe(re.findall(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", normalized_text, flags=re.IGNORECASE))
    batch_ids = dedupe(re.findall(r"\b[0-9A-Z]{20,32}\b|\b[0-9a-f]{24}\b", normalized_text))
    schema_ids = dedupe(re.findall(r"\b[0-9a-f]{32,64}\b|https?://ns\.adobe\.com/[^\s'\",]+", normalized_text, flags=re.IGNORECASE))
    dates = dedupe(re.findall(r"\b20\d{2}-\d{2}-\d{2}\b", normalized_text))
    metrics = dedupe(re.findall(r"\btimeseries\.[a-z0-9_.]+\b", matching_text))
    field_paths = dedupe(
        value
        for value in re.findall(r"\b[a-zA-Z_][\w-]*(?:\.[a-zA-Z_][\w-]*){1,}\b", normalized_text)
        if not value.lower().startswith("timeseries.")
    )
    words = dedupe(re.findall(r"[a-z0-9_]+", matching_text))
    statuses = [word for word in words if word in STATUS_WORDS]
    domains = [
        family
        for family, terms in DOMAIN_TERMS.items()
        if any(term in words or term in matching_text for term in terms)
    ]
    date_ranges = [(dates[0], dates[1])] if len(dates) >= 2 else []
    return QueryTokens(
        original=original,
        normalized=normalized_text,
        matching_text=matching_text,
        words=words,
        quoted_entities=quoted,
        named_entities=dedupe(entity for entity in named if entity not in quoted),
        uuids=uuids,
        batch_ids=batch_ids,
        schema_ids=schema_ids,
        dates=dates,
        date_ranges=date_ranges,
        metric_names=metrics,
        field_paths=field_paths,
        statuses=dedupe(statuses),
        domain_tokens=domains,
    )


def extract_named_entities(text: str) -> list[str]:
    entities = []
    for match in re.finditer(r"\b(?:named|called|titled)\s+(.+?)(?:,|\s+showing\b|\s+with\b|\s+between\b|[?.!]|$)", text, flags=re.IGNORECASE):
        value = match.group(1).strip().strip("'\" ")
        if value:
            entities.append(value)
    return dedupe(entities)


def dedupe(values: Any) -> list[Any]:
    result = []
    seen = set()
    for value in values:
        key = str(value).lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result
