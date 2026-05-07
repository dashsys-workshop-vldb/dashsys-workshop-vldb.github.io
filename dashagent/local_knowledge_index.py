from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from .config import Config, DEFAULT_CONFIG
from .db import sanitize_table_name
from .query_tokens import extract_query_tokens
from .trajectory import redact_secrets


HIGH_SIGNAL_COLUMN_PARTS = (
    "id",
    "name",
    "status",
    "state",
    "title",
    "label",
    "category",
    "metric",
    "schema",
    "blueprint",
    "collection",
    "batch",
    "file",
    "date",
    "time",
    "class",
    "type",
    "policy",
)

RELATION_TABLE_PARTS = ("br_", "bridge", "relation", "used_by")
SCHEMA_RELATION_TERMS = {"schema", "blueprint", "dataset", "collection", "using", "based", "associated", "built"}


@dataclass(frozen=True)
class EvidenceObject:
    evidence_id: str
    evidence_type: str
    table: str
    source_path: str
    columns: list[str]
    values: dict[str, str]
    row_excerpt: dict[str, str]
    provenance: dict[str, Any]
    confidence: float
    match_type: str = "indexed"
    query_visible_text: str | None = None
    source_signals: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["is_final_answer"] = False
        payload["answer_cache"] = False
        return redact_secrets(payload)


@dataclass(frozen=True)
class LocalKnowledgeIndex:
    evidence_objects: list[EvidenceObject]
    table_summaries: list[dict[str, Any]]
    rejected_objects: list[dict[str, Any]]
    build_summary: dict[str, Any]

    def to_dict(self, *, include_objects: bool = True, max_objects: int | None = None) -> dict[str, Any]:
        objects = self.evidence_objects if max_objects is None else self.evidence_objects[:max_objects]
        return redact_secrets(
            {
                "index_version": "parquet_evidence_v1",
                "runtime_sources": {
                    "parquet_only": True,
                    "dbsnapshot_glob": "data/DBSnapshot/*.parquet",
                    "data_json_used_for_runtime": False,
                    "gold_sql_api_answers_used_for_runtime": False,
                },
                "local_index_returns_final_answers": False,
                "evidence_objects": [obj.to_dict() for obj in objects] if include_objects else [],
                "evidence_object_count": len(self.evidence_objects),
                "table_summaries": self.table_summaries,
                "rejected_objects": self.rejected_objects,
                "build_summary": self.build_summary,
            }
        )

    def lookup(self, query: str, *, max_results: int = 12) -> list[dict[str, Any]]:
        query_tokens = extract_query_tokens(query)
        query_text = query_tokens.matching_text
        query_words = set(query_tokens.words)
        scored: list[tuple[float, EvidenceObject, str, list[str]]] = []
        for evidence in self.evidence_objects:
            score, match_type, signals = _score_evidence(evidence, query_text, query_words)
            if score <= 0:
                continue
            scored.append((score, evidence, match_type, signals))
        scored.sort(key=lambda item: (-item[0], item[1].evidence_id))
        results = []
        for score, evidence, match_type, signals in scored[:max_results]:
            payload = evidence.to_dict()
            payload.update(
                {
                    "confidence": round(min(1.0, score), 4),
                    "match_type": match_type,
                    "query_visible_text": query[:160],
                    "source_signals": sorted(set([*payload.get("source_signals", []), *signals])),
                }
            )
            results.append(payload)
        return results


def build_local_knowledge_index(
    config: Config | None = None,
    *,
    max_distinct_values_per_column: int = 200,
    max_relation_rows_per_table: int = 300,
    max_cell_chars: int = 240,
) -> LocalKnowledgeIndex:
    cfg = config or DEFAULT_CONFIG
    evidence_objects: list[EvidenceObject] = []
    table_summaries: list[dict[str, Any]] = []
    rejected_objects: list[dict[str, Any]] = []
    parquet_paths = sorted(cfg.dbsnapshot_dir.rglob("*.parquet")) if cfg.dbsnapshot_dir.exists() else []

    for parquet_path in parquet_paths:
        table = sanitize_table_name(parquet_path)
        source_path = _relative_path(parquet_path, cfg.project_root)
        try:
            frame = pd.read_parquet(parquet_path)
        except Exception as exc:
            rejected_objects.append(
                {
                    "source_path": source_path,
                    "classification": "rejected_unreadable_parquet",
                    "reason": str(exc).splitlines()[0][:300],
                }
            )
            continue
        columns = [str(column) for column in frame.columns]
        high_signal_columns = [column for column in columns if _is_high_signal_column(column)]
        relation_columns = _relation_columns(columns)
        row_count = int(len(frame))
        table_summaries.append(
            {
                "table": table,
                "source_path": source_path,
                "row_count": row_count,
                "column_count": len(columns),
                "high_signal_columns": high_signal_columns,
                "relation_columns": relation_columns,
                "likely_domains": _likely_domains(table, columns),
            }
        )
        if row_count == 0 or not columns:
            continue
        evidence_objects.extend(
            _value_evidence_for_table(
                frame,
                table=table,
                source_path=source_path,
                high_signal_columns=high_signal_columns,
                max_distinct=max_distinct_values_per_column,
                max_cell_chars=max_cell_chars,
            )
        )
        evidence_objects.extend(
            _relation_evidence_for_table(
                frame,
                table=table,
                source_path=source_path,
                relation_columns=relation_columns,
                max_rows=max_relation_rows_per_table,
                max_cell_chars=max_cell_chars,
            )
        )

    evidence_objects = _dedupe_evidence(evidence_objects)
    build_summary = {
        "parquet_files_scanned": len(parquet_paths),
        "tables_indexed": len(table_summaries),
        "evidence_object_count": len(evidence_objects),
        "rejected_object_count": len(rejected_objects),
        "evidence_type_counts": _count_by(evidence_objects, "evidence_type"),
        "parquet_only": True,
        "data_json_used_for_runtime": False,
        "local_index_returns_final_answers": False,
    }
    return LocalKnowledgeIndex(
        evidence_objects=evidence_objects,
        table_summaries=table_summaries,
        rejected_objects=rejected_objects,
        build_summary=build_summary,
    )


def classify_evidence_hit(hit: dict[str, Any]) -> str:
    evidence_type = str(hit.get("evidence_type") or "")
    if evidence_type in {
        "reusable_entity_lookup",
        "reusable_value_grounding",
        "reusable_schema_relation_lookup",
        "reusable_endpoint_family_lookup",
        "reusable_materialized_view_lookup",
    }:
        return evidence_type
    return "rejected_exact_query_or_gold_like_lookup"


def ensure_not_final_answer_payload(payload: dict[str, Any]) -> None:
    forbidden_keys = {"final_answer", "answer", "gold_answer", "gold_sql", "gold_api"}
    found = _find_forbidden_keys(payload, forbidden_keys)
    if found:
        raise ValueError(f"Local knowledge index evidence cannot contain final/gold answer keys: {sorted(found)}")


def _value_evidence_for_table(
    frame: pd.DataFrame,
    *,
    table: str,
    source_path: str,
    high_signal_columns: list[str],
    max_distinct: int,
    max_cell_chars: int,
) -> list[EvidenceObject]:
    evidence: list[EvidenceObject] = []
    for column in high_signal_columns:
        if column not in frame.columns:
            continue
        values = [value for value in frame[column].dropna().astype(str).unique().tolist() if value.strip()]
        for value in sorted(values)[:max_distinct]:
            normalized_value = _normalize(value)
            if not normalized_value or len(normalized_value) < 2:
                continue
            evidence_type = _evidence_type_for_column(table, column)
            row = frame[frame[column].astype(str) == value].head(1)
            row_excerpt = _row_excerpt(row.iloc[0].to_dict() if not row.empty else {column: value}, max_cell_chars)
            evidence.append(
                _make_evidence(
                    evidence_type=evidence_type,
                    table=table,
                    source_path=source_path,
                    columns=[column],
                    values={column: _clip(value, max_cell_chars)},
                    row_excerpt=row_excerpt,
                    confidence=0.86 if evidence_type == "reusable_value_grounding" else 0.9,
                    source_signals=["parquet_distinct_value", f"column:{column}"],
                )
            )
    return evidence


def _relation_evidence_for_table(
    frame: pd.DataFrame,
    *,
    table: str,
    source_path: str,
    relation_columns: list[str],
    max_rows: int,
    max_cell_chars: int,
) -> list[EvidenceObject]:
    if not relation_columns and not _is_relation_table(table):
        return []
    evidence: list[EvidenceObject] = []
    selected_columns = relation_columns or [str(column) for column in frame.columns if _is_high_signal_column(str(column))]
    if len(selected_columns) < 2:
        return []
    for _, row in frame[selected_columns].dropna(how="all").head(max_rows).iterrows():
        values = {
            column: _clip(value, max_cell_chars)
            for column, value in row.to_dict().items()
            if value not in (None, "") and str(value).strip()
        }
        if len(values) < 2:
            continue
        evidence.append(
            _make_evidence(
                evidence_type="reusable_schema_relation_lookup",
                table=table,
                source_path=source_path,
                columns=list(values),
                values=values,
                row_excerpt=values,
                confidence=0.92,
                source_signals=["parquet_relation_row", f"table:{table}"],
            )
        )
    return evidence


def _make_evidence(
    *,
    evidence_type: str,
    table: str,
    source_path: str,
    columns: list[str],
    values: dict[str, Any],
    row_excerpt: dict[str, Any],
    confidence: float,
    source_signals: list[str],
) -> EvidenceObject:
    clean_values = {str(key): _clip(value, 240) for key, value in values.items()}
    clean_excerpt = {str(key): _clip(value, 240) for key, value in row_excerpt.items()}
    payload_for_id = {
        "type": evidence_type,
        "table": table,
        "source_path": source_path,
        "columns": columns,
        "values": clean_values,
    }
    evidence_id = hashlib.sha256(json.dumps(payload_for_id, sort_keys=True).encode("utf-8")).hexdigest()[:20]
    return EvidenceObject(
        evidence_id=evidence_id,
        evidence_type=evidence_type,
        table=table,
        source_path=source_path,
        columns=columns,
        values=clean_values,
        row_excerpt=clean_excerpt,
        provenance={
            "source": "data/DBSnapshot parquet",
            "source_path": source_path,
            "derived_from_gold": False,
            "data_json_used": False,
            "query_id_used": False,
            "exact_public_query_used": False,
            "runtime_safe": True,
        },
        confidence=confidence,
        source_signals=source_signals,
    )


def _score_evidence(evidence: EvidenceObject, query_text: str, query_words: set[str]) -> tuple[float, str, list[str]]:
    signals: list[str] = []
    score = 0.0
    combined_values = " ".join(str(value) for value in evidence.values.values())
    normalized_value = _normalize(combined_values)
    normalized_query = _normalize(query_text)
    if normalized_value and len(normalized_value) >= 4 and normalized_value in normalized_query:
        score += 0.75
        signals.append("value_visible_in_query")
    value_words = set(re.findall(r"[a-z0-9_]+", combined_values.lower()))
    overlap = sorted(word for word in value_words & query_words if len(word) > 2)
    if overlap:
        score += min(0.35, 0.08 * len(overlap))
        signals.append("value_word_overlap")
    table_words = set(re.findall(r"[a-z0-9_]+", evidence.table.lower()))
    if table_words & query_words:
        score += 0.18
        signals.append("table_word_overlap")
    column_words = set(word for column in evidence.columns for word in re.findall(r"[a-z0-9_]+", column.lower()))
    if column_words & query_words:
        score += 0.12
        signals.append("column_word_overlap")
    if evidence.evidence_type == "reusable_schema_relation_lookup" and SCHEMA_RELATION_TERMS & query_words:
        score += 0.25
        signals.append("schema_relation_language")
    if score <= 0:
        return 0.0, "no_match", []
    return round(min(1.0, score), 4), "parquet_evidence_match", signals


def _dedupe_evidence(objects: list[EvidenceObject]) -> list[EvidenceObject]:
    by_id: dict[str, EvidenceObject] = {}
    for obj in objects:
        by_id.setdefault(obj.evidence_id, obj)
    return [by_id[key] for key in sorted(by_id)]


def _is_high_signal_column(column: str) -> bool:
    lowered = column.lower()
    return any(part in lowered for part in HIGH_SIGNAL_COLUMN_PARTS)


def _is_relation_table(table: str) -> bool:
    lowered = table.lower()
    return any(part in lowered for part in RELATION_TABLE_PARTS) or lowered.startswith(("br_", "hkg_br_"))


def _relation_columns(columns: list[str]) -> list[str]:
    selected = []
    for column in columns:
        lowered = column.lower()
        if any(part in lowered for part in ("id", "schema", "blueprint", "collection", "dataset", "segment", "property")):
            selected.append(column)
    return selected


def _evidence_type_for_column(table: str, column: str) -> str:
    lowered = f"{table}.{column}".lower()
    if "endpoint" in lowered or "api" in lowered:
        return "reusable_endpoint_family_lookup"
    if "metric" in lowered:
        return "reusable_materialized_view_lookup"
    if any(part in lowered for part in ("status", "state", "category", "type", "class", "date", "time", "file")):
        return "reusable_value_grounding"
    return "reusable_entity_lookup"


def _likely_domains(table: str, columns: list[str]) -> list[str]:
    text = " ".join([table, *columns]).lower()
    domains = []
    for domain, terms in {
        "batch": ["batch", "file"],
        "schema_dataset": ["schema", "blueprint", "collection", "dataset"],
        "journey_campaign": ["campaign", "journey"],
        "segment_audience": ["segment", "audience"],
        "merge_policy": ["merge", "policy"],
        "observability": ["metric", "timeseries", "observability"],
        "tags": ["tag", "category"],
        "destination_dataflow": ["target", "connector", "destination", "dataflow"],
    }.items():
        if any(term in text for term in terms):
            domains.append(domain)
    return domains or ["general"]


def _row_excerpt(row: dict[str, Any], max_cell_chars: int) -> dict[str, str]:
    excerpt = {}
    for key, value in row.items():
        if value in (None, ""):
            continue
        if not _is_high_signal_column(str(key)) and len(excerpt) >= 8:
            continue
        excerpt[str(key)] = _clip(value, max_cell_chars)
        if len(excerpt) >= 12:
            break
    return excerpt


def _clip(value: Any, max_chars: int) -> str:
    text = str(value)
    return text if len(text) <= max_chars else text[: max_chars - 3] + "..."


def _normalize(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def _count_by(objects: list[EvidenceObject], attr: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for obj in objects:
        key = str(getattr(obj, attr))
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def _relative_path(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return path.name


def _find_forbidden_keys(payload: Any, forbidden: set[str]) -> set[str]:
    found: set[str] = set()
    if isinstance(payload, dict):
        for key, value in payload.items():
            if str(key).lower() in forbidden:
                found.add(str(key))
            found.update(_find_forbidden_keys(value, forbidden))
    elif isinstance(payload, list):
        for item in payload:
            found.update(_find_forbidden_keys(item, forbidden))
    return found
