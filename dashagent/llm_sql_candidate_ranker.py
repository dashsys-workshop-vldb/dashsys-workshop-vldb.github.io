from __future__ import annotations

import re
from typing import Any

from .db import DuckDBDatabase
from .llm_sql_plan_compiler import compile_structured_sql_plan
from .llm_sql_semantic_verifier import verify_sql_plan_semantics
from .schema_index import SchemaIndex, normalize_name
from .trajectory import redact_secrets
from .validators import SQLValidator


def rank_sql_plan_candidates(
    prompt: str,
    answer_intent: str | None,
    schema_context: dict[str, Any],
    candidate_plans: list[dict[str, Any]],
    schema_index: SchemaIndex,
    sql_validator: SQLValidator,
    *,
    db: DuckDBDatabase | None = None,
    execution_probe: bool = False,
    evidence_source_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ranking: list[dict[str, Any]] = []
    rejection_reasons: dict[str, list[str]] = {}
    for index, candidate in enumerate(candidate_plans):
        candidate_id = str(candidate.get("candidate_id") or f"c{index + 1}")
        compiled = compile_structured_sql_plan(candidate, schema_index, schema_context)
        sql = str(compiled.get("sql") or "")
        validation = sql_validator.validate(sql) if compiled.get("ok") and sql else None
        candidate_intent = str(candidate.get("answer_intent") or answer_intent or "")
        semantic = (
            verify_sql_plan_semantics(prompt, evidence_source_plan or {}, candidate, schema_context, candidate_intent)
            if compiled.get("ok")
            else {"ok": False, "errors": compiled.get("errors", []), "semantic_score": 0.0, "warnings": []}
        )
        probe = _execution_probe(db, sql) if execution_probe and compiled.get("ok") and validation and validation.ok and semantic.get("ok") else {}
        reasons = _rejection_reasons(compiled, validation, semantic, probe, execution_probe)
        features = _ranking_features(prompt, candidate_intent, candidate, compiled, semantic, validation, probe)
        score = _score(features, candidate)
        accepted = not reasons
        if not accepted:
            rejection_reasons[candidate_id] = reasons
            score -= 100.0
        ranking.append(
            redact_secrets(
                {
                    "candidate_id": candidate_id,
                    "accepted": accepted,
                    "score": round(score, 4),
                    "candidate": candidate,
                    "compiled": compiled,
                    "validation": validation.to_dict() if validation else {"ok": False, "errors": compiled.get("errors", [])},
                    "semantic_verification": semantic,
                    "probe": probe,
                    "ranking_features": features,
                    "rejection_reasons": reasons,
                }
            )
        )
    ranking.sort(key=lambda item: (bool(item.get("accepted")), float(item.get("score") or 0.0)), reverse=True)
    selected = next((item for item in ranking if item.get("accepted")), None)
    return redact_secrets(
        {
            "selected_candidate_id": selected.get("candidate_id") if selected else None,
            "selected_candidate": selected.get("candidate") if selected else None,
            "selected_sql": (selected.get("compiled") or {}).get("sql") if selected else "",
            "ranking": ranking,
            "ranking_features": selected.get("ranking_features") if selected else {},
            "rejection_reasons": rejection_reasons,
        }
    )


def normalize_multi_candidate_plans(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    raw = payload.get("candidates")
    if isinstance(raw, dict):
        raw = list(raw.values())
    if not isinstance(raw, list):
        raw = []
    candidates = []
    for index, item in enumerate(raw[:5]):
        if not isinstance(item, dict):
            continue
        candidate = dict(item)
        candidate.setdefault("candidate_id", f"c{index + 1}")
        candidates.append(candidate)
    return candidates[:3]


def _rejection_reasons(
    compiled: dict[str, Any],
    validation: Any,
    semantic: dict[str, Any],
    probe: dict[str, Any],
    execution_probe: bool,
) -> list[str]:
    reasons: list[str] = []
    if not compiled.get("ok"):
        reasons.extend(str(error) for error in compiled.get("errors", []))
    if validation is not None and not validation.ok:
        reasons.extend(str(error) for error in validation.errors)
    if not semantic.get("ok"):
        reasons.extend(str(error) for error in semantic.get("errors", []))
    if execution_probe and probe and not probe.get("probe_ok"):
        reasons.append(str(probe.get("error") or "execution probe failed"))
    return sorted(set(reason for reason in reasons if reason))


def _ranking_features(
    prompt: str,
    answer_intent: str | None,
    candidate: dict[str, Any],
    compiled: dict[str, Any],
    semantic: dict[str, Any],
    validation: Any,
    probe: dict[str, Any],
) -> dict[str, Any]:
    columns = [str(column) for column in candidate.get("columns_needed") or []]
    aggregation = _aggregation(candidate)
    intent = str(answer_intent or candidate.get("answer_intent") or "").upper()
    return {
        "compile_ok": bool(compiled.get("ok")),
        "sql_validation_ok": bool(validation and validation.ok),
        "semantic_ok": bool(semantic.get("ok")),
        "semantic_score": semantic.get("semantic_score"),
        "probe_ok": bool(probe.get("probe_ok")) if probe else None,
        "answer_intent_match": _intent_match(intent, aggregation, columns),
        "timestamp_semantic_match": _timestamp_semantic_match(prompt, columns),
        "entity_table_match": bool(semantic.get("expected_table") and semantic.get("expected_table") == semantic.get("selected_table")),
        "filter_coverage": _filter_coverage(prompt, candidate),
        "column_coverage": _column_coverage(prompt, columns),
    }


def _score(features: dict[str, Any], candidate: dict[str, Any]) -> float:
    score = 0.0
    score += 2.0 if features.get("compile_ok") else 0.0
    score += 2.0 if features.get("sql_validation_ok") else 0.0
    score += 3.0 if features.get("semantic_ok") else 0.0
    score += float(features.get("semantic_score") or 0.0)
    score += 1.0 if features.get("probe_ok") else 0.0
    score += 1.0 if features.get("answer_intent_match") else 0.0
    score += 1.0 if features.get("timestamp_semantic_match") else 0.0
    score += 0.5 if features.get("entity_table_match") else 0.0
    score += 0.5 if features.get("filter_coverage") else 0.0
    score += 0.5 if features.get("column_coverage") else 0.0
    try:
        score += min(max(float(candidate.get("confidence") or 0.0), 0.0), 1.0) * 0.2
    except Exception:
        pass
    return score


def _execution_probe(db: DuckDBDatabase | None, sql: str) -> dict[str, Any]:
    if db is None or not sql:
        return {}
    cleaned = str(sql).strip().rstrip(";")
    probe_sql = f"SELECT * FROM ({cleaned}) AS _pure_llm_probe LIMIT 1"
    result = db.execute_sql(probe_sql, max_rows=1)
    rows = result.get("rows") if isinstance(result.get("rows"), list) else []
    columns = list(rows[0].keys()) if rows and isinstance(rows[0], dict) else []
    return redact_secrets(
        {
            "probe_ok": bool(result.get("ok")),
            "row_count": result.get("row_count"),
            "columns_returned": columns,
            "error": result.get("error"),
        }
    )


def _intent_match(intent: str, aggregation: str, columns: list[str]) -> bool:
    if intent == "COUNT":
        return aggregation in {"count", "count_distinct"}
    if intent == "LIST":
        return any(_is_id_column(column) or _is_name_column(column) for column in columns)
    if intent == "STATUS":
        return any("status" in normalize_name(column) or "state" in normalize_name(column) for column in columns)
    if intent == "DATE":
        return any(_is_timestamp_column(column) for column in columns)
    return True


def _timestamp_semantic_match(prompt: str, columns: list[str]) -> bool:
    prompt_l = prompt.lower()
    normalized = [normalize_name(column) for column in columns]
    if any(term in prompt_l for term in ("published", "deployed", "launched", "released")):
        return any("published" in column or "deployed" in column for column in normalized)
    if any(term in prompt_l for term in ("updated", "modified", "recent")):
        return any("updated" in column or "modified" in column for column in normalized)
    if "created" in prompt_l:
        return any("created" in column for column in normalized)
    return True


def _filter_coverage(prompt: str, candidate: dict[str, Any]) -> bool:
    filters = [item for item in candidate.get("filters") or [] if isinstance(item, dict)]
    quoted = [match.group(1) or match.group(2) for match in re.finditer(r"'([^']+)'|\"([^\"]+)\"", prompt)]
    if quoted:
        return any(
            any(str(item.get("value") or "") == value for value in quoted)
            and any(marker in normalize_name(str(item.get("column") or "")) for marker in ("name", "title", "display"))
            for item in filters
        )
    prompt_l = prompt.lower()
    if any(term in prompt_l for term in ("active", "inactive", "failed", "succeeded", "published")):
        return any("status" in normalize_name(str(item.get("column") or "")) or "state" in normalize_name(str(item.get("column") or "")) for item in filters)
    return True


def _column_coverage(prompt: str, columns: list[str]) -> bool:
    prompt_l = prompt.lower()
    if re.search(r"\bids?\b", prompt_l):
        return any(_is_id_column(column) for column in columns)
    if any(term in prompt_l for term in ("name", "names", "list")):
        return any(_is_name_column(column) or _is_id_column(column) for column in columns)
    if any(term in prompt_l for term in ("when", "date", "published", "updated", "created")):
        return any(_is_timestamp_column(column) for column in columns)
    return True


def _aggregation(candidate: dict[str, Any]) -> str:
    raw = candidate.get("aggregation")
    if isinstance(raw, dict):
        return str(raw.get("type") or raw.get("function") or "none").lower()
    return "none"


def _is_timestamp_column(column: str) -> bool:
    normalized = normalize_name(column)
    return any(marker in normalized for marker in ("time", "date", "created", "updated", "deployed", "published"))


def _is_id_column(column: str) -> bool:
    normalized = normalize_name(column)
    return normalized == "id" or normalized.endswith("id")


def _is_name_column(column: str) -> bool:
    normalized = normalize_name(column)
    return normalized in {"name", "title", "displayname"} or normalized.endswith("name")
