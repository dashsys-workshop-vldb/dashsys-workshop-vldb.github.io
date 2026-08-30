from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from difflib import SequenceMatcher
from typing import Any

from .endpoint_catalog import EndpointCatalog
from .lookup_paths import LOOKUP_PATHS, LookupPath
from .query_tokens import QueryTokens, extract_query_tokens
from .schema_index import JoinHint, SchemaIndex, normalize_name


@dataclass(frozen=True)
class RelevanceItem:
    name: str
    score: float
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["score"] = round(self.score, 4)
        return payload


@dataclass(frozen=True)
class RelevanceResult:
    tables: list[RelevanceItem] = field(default_factory=list)
    columns: dict[str, list[RelevanceItem]] = field(default_factory=dict)
    join_hints: list[RelevanceItem] = field(default_factory=list)
    apis: list[RelevanceItem] = field(default_factory=list)
    lookup_paths: list[RelevanceItem] = field(default_factory=list)
    answer_families: list[RelevanceItem] = field(default_factory=list)

    def compact(self, *, table_k: int = 5, api_k: int = 4) -> dict[str, Any]:
        payload = {
            "tables": [item.name for item in self.tables[:table_k]],
            "apis": [item.name for item in self.apis[:api_k]],
            "lookup_paths": [item.name for item in self.lookup_paths[:3]],
            "answer_families": [item.name for item in self.answer_families[:3]],
        }
        return {key: value for key, value in payload.items() if value}


def score_relevance(
    query: str,
    schema_index: SchemaIndex,
    endpoint_catalog: EndpointCatalog | None = None,
    *,
    tokens: QueryTokens | None = None,
    lookup_path: LookupPath | None = None,
) -> RelevanceResult:
    token_obj = tokens or extract_query_tokens(query)
    endpoint_catalog = endpoint_catalog or EndpointCatalog()
    words = set(token_obj.words)
    matching = token_obj.matching_text
    lookup = lookup_path or best_lookup_path(token_obj)

    table_items = score_tables(schema_index, words, matching, lookup)
    top_tables = [item.name for item in table_items[:8]]
    column_items = {
        table: score_columns(table, schema_index.columns_for(table), words, matching)[:12]
        for table in top_tables
    }
    join_items = score_join_hints(schema_index.join_hints, top_tables, words, matching)
    api_items = score_apis(endpoint_catalog, words, matching, lookup)
    lookup_items = score_lookup_paths(words, matching, lookup)
    answer_items = score_answer_families(words, matching, token_obj)
    return RelevanceResult(
        tables=table_items,
        columns=column_items,
        join_hints=join_items,
        apis=api_items,
        lookup_paths=lookup_items,
        answer_families=answer_items,
    )


def score_tables(schema: SchemaIndex, words: set[str], matching: str, lookup: LookupPath) -> list[RelevanceItem]:
    items = []
    lookup_tables = set(lookup.tables)
    for table in schema.tables:
        table_words = split_identifier(table)
        overlap = len(words & table_words)
        score = 0.25 * overlap
        if table in lookup_tables:
            score += 2.0
        if any(word in matching for word in table_words):
            score += 0.3
        if "bridge" in matching and schema.tables[table].get("is_bridge"):
            score += 0.25
        if score > 0:
            items.append(RelevanceItem(table, score, "lookup/table-token overlap"))
    return sorted(items, key=lambda item: (-item.score, item.name))


def score_columns(table: str, columns: list[str], words: set[str], matching: str) -> list[RelevanceItem]:
    items = []
    for column in columns:
        column_words = split_identifier(column)
        overlap = len(words & column_words)
        score = 0.2 * overlap
        normalized_column = normalize_name(column)
        if any(normalize_name(word) in normalized_column for word in words):
            score += 0.1
        if normalized_column in {"id", "name"} or normalized_column.endswith(("id", "name", "time", "status", "state", "count")):
            score += 0.15
        if any(entity.lower() in matching for entity in column_words):
            score += 0.05
        if score > 0:
            items.append(RelevanceItem(column, score, f"{table} column relevance"))
    return sorted(items, key=lambda item: (-item.score, item.name))


def score_join_hints(hints: list[JoinHint], top_tables: list[str], words: set[str], matching: str) -> list[RelevanceItem]:
    table_set = set(top_tables)
    items = []
    for hint in hints:
        score = 0.0
        if hint.left_table in table_set:
            score += 0.7
        if hint.right_table in table_set:
            score += 0.7
        joined_text = " ".join([hint.left_table, hint.left_column, hint.right_table, hint.right_column, hint.reason]).lower()
        score += 0.1 * len(words & set(re.findall(r"[a-z0-9]+", joined_text)))
        if any(token in matching for token in ["connected", "mapped", "related", "uses", "linked"]):
            score += 0.2
        if score > 0:
            name = f"{hint.left_table}.{hint.left_column}->{hint.right_table}.{hint.right_column}"
            items.append(RelevanceItem(name, score, hint.reason))
    return sorted(items, key=lambda item: (-item.score, item.name))


def score_apis(catalog: EndpointCatalog, words: set[str], matching: str, lookup: LookupPath) -> list[RelevanceItem]:
    lookup_families = set(lookup.api_families)
    items = []
    for endpoint in catalog.endpoints:
        endpoint_text = " ".join([endpoint.id, endpoint.path, endpoint.use_when, " ".join(endpoint.domains)]).lower()
        endpoint_words = set(re.findall(r"[a-z0-9]+", endpoint_text))
        overlap = len(words & endpoint_words)
        score = 0.18 * overlap
        if endpoint.id in lookup_families or any(family in endpoint.id for family in lookup_families):
            score += 1.0
        if endpoint.path in matching:
            score += 0.8
        if fuzzy_contains(endpoint.id, matching):
            score += 0.2
        if score > 0:
            items.append(RelevanceItem(endpoint.id, score, endpoint.path))
    return sorted(items, key=lambda item: (-item.score, item.name))


def score_lookup_paths(words: set[str], matching: str, predicted: LookupPath) -> list[RelevanceItem]:
    items = []
    for name, path in LOOKUP_PATHS.items():
        path_words = set(split_identifier(name))
        path_words.update(word for table in path.tables for word in split_identifier(table))
        path_words.update(word for family in path.api_families for word in split_identifier(family))
        score = 0.2 * len(words & path_words)
        if name == predicted.family:
            score += 2.0
        if name.replace("_", " ") in matching:
            score += 0.4
        if score > 0:
            items.append(RelevanceItem(name, score, path.api_mode))
    return sorted(items, key=lambda item: (-item.score, item.name))


def score_answer_families(words: set[str], matching: str, tokens: QueryTokens) -> list[RelevanceItem]:
    families = {
        "journey_published": {"journey", "campaign", "published", "publish"},
        "inactive_journeys": {"inactive", "journey", "campaign"},
        "segment_destination": {"segment", "audience", "destination", "connected", "mapped"},
        "schema_dataset": {"schema", "dataset", "collection", "blueprint"},
        "tags": {"tag", "category"},
        "merge_policy": {"merge", "policy"},
        "observability_metrics": {"metric", "timeseries", "recordsuccess", "batchsuccess"},
        "batch": {"batch", "file"},
        "property_field": {"field", "property", "attribute"},
    }
    items = []
    for family, family_words in families.items():
        score = 0.25 * len(words & family_words)
        if family == "observability_metrics" and tokens.metric_names:
            score += 1.0
        if family.replace("_", " ") in matching:
            score += 0.4
        if score > 0:
            items.append(RelevanceItem(family, score, "answer family token overlap"))
    return sorted(items, key=lambda item: (-item.score, item.name))


def best_lookup_path(tokens: QueryTokens) -> LookupPath:
    domain_to_path = {
        "audit": "audit",
        "batch": "batch",
        "destination_dataflow": "destination_dataflow",
        "journey_campaign": "journey_campaign",
        "merge_policy": "merge_policy",
        "observability": "observability",
        "property_field": "property_field",
        "schema_dataset": "schema_dataset",
        "segment_audience": "segment_destination",
        "tags": "tags",
    }
    for domain in tokens.domain_tokens:
        if domain in domain_to_path:
            return LOOKUP_PATHS[domain_to_path[domain]]
    return LOOKUP_PATHS.get("journey_campaign") if "journey" in tokens.words else LookupPath("unknown", [])


def split_identifier(value: str) -> set[str]:
    normalized = re.sub(r"([a-z])([A-Z])", r"\1 \2", value)
    return {
        token
        for token in re.findall(r"[a-z0-9]+", normalized.lower().replace("_", " "))
        if token not in {"br", "dim", "hkg", "the", "and", "for"}
    }


def fuzzy_contains(needle: str, haystack: str) -> bool:
    compact = needle.replace("_", " ").lower()
    if compact in haystack:
        return True
    try:
        from rapidfuzz.fuzz import partial_ratio  # type: ignore

        return partial_ratio(compact, haystack) >= 85
    except Exception:
        return SequenceMatcher(None, compact, haystack).ratio() >= 0.75
