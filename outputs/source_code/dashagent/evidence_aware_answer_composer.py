from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .answer_shape import collect_shape_evidence
from .answer_templates import classify_answer_family, join_human
from .eval_harness import generated_api_calls, first_generated_sql, normalize_sql
from .local_knowledge_index import ensure_not_final_answer_payload, requested_fact_coverage


SECRET_PARAM_PARTS = {"token", "secret", "password", "authorization", "client_id", "client_secret", "key"}


@dataclass(frozen=True)
class EvidenceAwareAnswerCandidate:
    answer: str
    evidence_path: list[dict[str, Any]]
    unavailable_fields: list[str]
    supported_fields: list[str]
    local_evidence_used_in_final_answer: bool
    requested_fact_covered: bool
    no_fabrication_checks: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "answer": self.answer,
            "evidence_path": self.evidence_path,
            "unavailable_fields": self.unavailable_fields,
            "supported_fields": self.supported_fields,
            "local_evidence_used_in_final_answer": self.local_evidence_used_in_final_answer,
            "requested_fact_covered": self.requested_fact_covered,
            "no_fabrication_checks": self.no_fabrication_checks,
        }


def compose_evidence_aware_answer(
    query: str,
    trajectory: dict[str, Any],
    *,
    local_evidence: list[dict[str, Any]] | None = None,
) -> EvidenceAwareAnswerCandidate:
    """Compose an answer candidate from recorded evidence only.

    The composer is deliberately conservative for dry-run API calls: request
    params and query-visible IDs/names are evidence, but API payload values are
    unavailable unless a live/non-dry-run payload exists.
    """

    local_evidence = _safe_local_evidence(local_evidence or [])
    tool_results = _tool_results_from_trajectory(trajectory)
    shape_evidence = collect_shape_evidence(query, tool_results)
    local_coverage = requested_fact_coverage(query, local_evidence)
    endpoint_bits = _endpoint_bits(trajectory)
    query_values = _query_visible_values(query)
    local_bits = _local_evidence_bits(local_evidence, local_coverage)
    intent = _intent(query)
    noun = _noun(query)
    dry_run = _has_dry_run_api(trajectory)
    live = _has_live_api_payload(trajectory)

    evidence_path: list[dict[str, Any]] = []
    evidence_path.extend(endpoint_bits)
    evidence_path.extend({"source": "query_visible_entity_text", "value": value} for value in query_values)
    evidence_path.extend(local_bits)

    supported_fields = _supported_fields(shape_evidence, endpoint_bits, query_values, local_bits)
    unavailable = _unavailable_fields(intent, supported_fields, dry_run=dry_run, live=live)
    pieces = []
    subject = _subject(query_values, endpoint_bits, local_bits, noun)
    if unavailable:
        pieces.append(f"{subject} {noun} {intent} is unavailable in dry-run mode.")
    else:
        pieces.append(_supported_sentence(intent, noun, shape_evidence, subject))
    if endpoint_bits:
        pieces.append("Endpoint: " + "; ".join(bit["text"] for bit in endpoint_bits[:2]) + ".")
    if local_bits:
        pieces.append("Parquet evidence: " + "; ".join(bit["text"] for bit in local_bits[:2]) + ".")
    if dry_run:
        pieces.append("Live API unavailable.")
    answer = " ".join(part for part in pieces if part).strip()
    answer = _clip_answer(answer)
    allowed_values = _allowed_value_fragments(query_values, endpoint_bits, local_bits)
    no_fabrication = {
        "uses_only_recorded_evidence": True,
        "dry_run_payload_values_used": False,
        "unsupported_fields_reported_unavailable": bool(unavailable) if dry_run else True,
        "allowed_value_fragments": sorted(allowed_values)[:30],
    }
    local_used = any(_value_in_answer(bit.get("value"), answer) for bit in local_bits)
    return EvidenceAwareAnswerCandidate(
        answer=answer,
        evidence_path=evidence_path[:12],
        unavailable_fields=unavailable,
        supported_fields=supported_fields,
        local_evidence_used_in_final_answer=local_used,
        requested_fact_covered=bool(local_coverage.get("requested_fact_covered")),
        no_fabrication_checks=no_fabrication,
    )


def answer_only_preserves_plan(baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    baseline_sql = first_generated_sql(baseline)
    candidate_sql = first_generated_sql(candidate)
    baseline_api = generated_api_calls(baseline)
    candidate_api = generated_api_calls(candidate)
    sql_unchanged = normalize_sql(baseline_sql) == normalize_sql(candidate_sql)
    api_unchanged = _canonical_api(baseline_api) == _canonical_api(candidate_api)
    return {
        "selected_sql_unchanged": sql_unchanged,
        "selected_api_unchanged": api_unchanged,
        "baseline_sql": baseline_sql,
        "candidate_sql": candidate_sql,
        "baseline_api": baseline_api,
        "candidate_api": candidate_api,
        "answer_only_plan_preserved": sql_unchanged and api_unchanged,
    }


def _tool_results_from_trajectory(trajectory: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for step in trajectory.get("steps", []):
        if step.get("kind") == "sql_call":
            results.append({"type": "sql", "step": step, "payload": step.get("result") or {}})
        elif step.get("kind") == "api_call":
            results.append({"type": "api", "step": step, "payload": step.get("result") or {}})
    return results


def _safe_local_evidence(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    safe = []
    for hit in hits[:8]:
        ensure_not_final_answer_payload(hit)
        provenance = hit.get("provenance") if isinstance(hit.get("provenance"), dict) else {}
        source_text = " ".join(str(hit.get(key) or "") for key in ["source", "classification", "rule_source"]).lower()
        if provenance.get("derived_from_gold") is True or "gold" in source_text:
            continue
        safe.append(hit)
    return safe


def _endpoint_bits(trajectory: dict[str, Any]) -> list[dict[str, Any]]:
    bits = []
    for call in generated_api_calls(trajectory):
        method = str(call.get("method") or "GET").upper()
        path = str(call.get("path") or "")
        params = _safe_params(call.get("params") or {})
        text = f"{method} {path}"
        if params:
            text += " params " + ", ".join(f"{key}={value}" for key, value in list(params.items())[:5])
        bits.append({"source": "selected_endpoint_params", "method": method, "path": path, "params": params, "text": text, "value": text})
    return bits


def _query_visible_values(query: str) -> list[str]:
    values = [(single or double).strip() for single, double in re.findall(r"'([^']+)'|\"([^\"]+)\"", query)]
    values.extend(re.findall(r"\b01[A-Z0-9]{20,}\b", query))
    values.extend(re.findall(r"\b[0-9a-f]{12,}(?:-[0-9a-f]{4,})*\b", query, flags=re.I))
    values.extend(re.findall(r"\b20\d{2}-\d{2}-\d{2}\b", query))
    for status in ["success", "failed", "queued", "processing", "inactive", "published"]:
        if re.search(rf"\b{status}\b", query, re.I):
            values.append(status)
    return list(dict.fromkeys(value for value in values if value))


def _local_evidence_bits(hits: list[dict[str, Any]], coverage: dict[str, Any]) -> list[dict[str, Any]]:
    covered_ids = {item.get("evidence_id") for item in coverage.get("covered_hits", [])}
    bits = []
    for hit in hits:
        if covered_ids and hit.get("evidence_id") not in covered_ids:
            continue
        value = hit.get("matched_value")
        if value in (None, ""):
            values = hit.get("values") if isinstance(hit.get("values"), dict) else {}
            value = next(iter(values.values()), None) if values else None
        if value in (None, ""):
            value = hit.get("value_preview")
        if value in (None, ""):
            continue
        table = hit.get("source_table") or hit.get("table")
        column = hit.get("source_column") or (hit.get("columns") or [None])[0]
        text = f"{table}.{column}={value}"
        bits.append({"source": "local_parquet_evidence", "table": table, "column": column, "value": str(value), "text": text})
    return bits[:5]


def _safe_params(params: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    if not isinstance(params, dict):
        return safe
    for key, value in params.items():
        key_norm = re.sub(r"[^a-z0-9]", "", str(key).lower())
        if any(part in key_norm for part in SECRET_PARAM_PARTS):
            continue
        if isinstance(value, (list, dict)) or value in (None, ""):
            continue
        safe[str(key)] = str(value)
    return safe


def _supported_fields(evidence: dict[str, Any], endpoint_bits: list[dict[str, Any]], query_values: list[str], local_bits: list[dict[str, Any]]) -> list[str]:
    fields = []
    for key, field in [("counts", "count"), ("names", "name"), ("ids", "id"), ("statuses", "status"), ("timestamps", "timestamp")]:
        if evidence.get(key):
            fields.append(field)
    if endpoint_bits:
        fields.append("selected_endpoint")
    if query_values:
        fields.append("query_visible_entity")
    if local_bits:
        fields.append("local_parquet_evidence")
    return sorted(set(fields))


def _unavailable_fields(intent: str, supported: list[str], *, dry_run: bool, live: bool) -> list[str]:
    if live:
        return []
    required = {
        "count": ["count"],
        "list": ["items"],
        "status": ["status"],
        "date": ["timestamp"],
        "detail": ["details"],
    }.get(intent, ["details"])
    if dry_run:
        return [field for field in required if field not in supported]
    return []


def _supported_sentence(intent: str, noun: str, evidence: dict[str, Any], subject: str) -> str:
    if intent == "count" and evidence.get("counts"):
        return f"The recorded evidence reports {evidence['counts'][0]} {noun} item(s)."
    if intent == "status" and evidence.get("statuses"):
        return f"{subject} has status/state {evidence['statuses'][0]} in the recorded evidence."
    if intent == "date" and evidence.get("timestamps"):
        return f"{subject} has recorded timestamp {evidence['timestamps'][0]}."
    names = evidence.get("names") or evidence.get("ids") or []
    if names:
        return f"The recorded evidence identifies {join_human([str(item) for item in names[:5]])}."
    return f"The requested {noun} detail is supported by recorded evidence."


def _intent(query: str) -> str:
    lowered = query.lower()
    if any(term in lowered for term in ["how many", "count", "number of", "total"]):
        return "count"
    if any(term in lowered for term in ["status", "state"]):
        return "status"
    if any(term in lowered for term in ["when", "date", "recent", "updated", "created", "published"]):
        return "date"
    if any(term in lowered for term in ["list", "which files", "which segment", "which tag"]):
        return "list"
    return "detail"


def _noun(query: str) -> str:
    family = classify_answer_family(query)
    return {
        "batch": "batch",
        "tags": "tag",
        "merge_policy": "merge policy",
        "segment_definitions": "segment definition",
        "segment_jobs": "segment job",
        "schema_dataset": "schema/dataset",
        "observability_metrics": "observability metric",
    }.get(family, family.replace("_", " "))


def _subject(query_values: list[str], endpoint_bits: list[dict[str, Any]], local_bits: list[dict[str, Any]], noun: str) -> str:
    if query_values:
        return query_values[0]
    if local_bits:
        return str(local_bits[0].get("value"))
    if endpoint_bits:
        return str(endpoint_bits[0].get("path"))
    return f"the requested {noun}"


def _has_dry_run_api(trajectory: dict[str, Any]) -> bool:
    return any(step.get("kind") == "api_call" and (step.get("result") or {}).get("dry_run") for step in trajectory.get("steps", []))


def _has_live_api_payload(trajectory: dict[str, Any]) -> bool:
    return any(
        step.get("kind") == "api_call"
        and (step.get("result") or {}).get("ok")
        and not (step.get("result") or {}).get("dry_run")
        for step in trajectory.get("steps", [])
    )


def _allowed_value_fragments(query_values: list[str], endpoint_bits: list[dict[str, Any]], local_bits: list[dict[str, Any]]) -> set[str]:
    fragments = set(query_values)
    for bit in [*endpoint_bits, *local_bits]:
        fragments.add(str(bit.get("value") or ""))
        fragments.add(str(bit.get("text") or ""))
    return {fragment for fragment in fragments if fragment}


def _value_in_answer(value: Any, answer: str) -> bool:
    text = str(value or "").strip()
    return bool(text) and text.lower() in answer.lower()


def _canonical_api(calls: list[dict[str, Any]]) -> str:
    return "|".join(f"{call.get('method')} {call.get('path')} {call.get('params')}" for call in calls)


def _clip_answer(answer: str, max_chars: int = 420) -> str:
    return answer if len(answer) <= max_chars else answer[: max_chars - 15].rstrip() + " [truncated]"
