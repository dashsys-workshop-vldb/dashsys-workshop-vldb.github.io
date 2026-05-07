from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

from .answer_templates import classify_answer_family
from .eval_harness import first_generated_sql, generated_api_calls, normalize_sql
from .local_knowledge_index import ensure_not_final_answer_payload, requested_fact_coverage
from .trajectory import estimate_tokens


ALLOWED_EVIDENCE_SOURCES = {
    "query_text",
    "endpoint_params",
    "sql_row",
    "parquet_evidence",
    "dry_run_label",
}
SECRET_LIKE_RE = re.compile(r"(bearer\s+[a-z0-9._-]+|sk-[a-z0-9_-]+|client_secret|access_token|api[_-]?key)", re.I)


@dataclass(frozen=True)
class SupportableAnswerRewrite:
    candidate_id: str
    answer: str
    claims: list[dict[str, Any]]
    evidence_registry: dict[str, dict[str, Any]]
    validation: dict[str, Any]
    baseline_answer_tokens: int
    candidate_answer_tokens: int
    target_answer_tokens: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "answer": self.answer,
            "claims": self.claims,
            "evidence_registry": self.evidence_registry,
            "validation": self.validation,
            "baseline_answer_tokens": self.baseline_answer_tokens,
            "candidate_answer_tokens": self.candidate_answer_tokens,
            "target_answer_tokens": self.target_answer_tokens,
        }


def canonical_plan_hashes(trajectory: dict[str, Any]) -> dict[str, Any]:
    sql = normalize_sql(first_generated_sql(trajectory))
    api = generated_api_calls(trajectory)
    return {
        "sql_hash": _sha256_json({"sql": sql}),
        "api_hash": _sha256_json({"api": api}),
        "tool_call_count": int(trajectory.get("tool_call_count") or 0),
        "canonical_sql": sql,
        "canonical_api": api,
    }


def compare_plan_hashes(baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    baseline_hashes = canonical_plan_hashes(baseline)
    candidate_hashes = canonical_plan_hashes(candidate)
    return {
        "baseline_sql_hash": baseline_hashes["sql_hash"],
        "candidate_sql_hash": candidate_hashes["sql_hash"],
        "baseline_api_hash": baseline_hashes["api_hash"],
        "candidate_api_hash": candidate_hashes["api_hash"],
        "baseline_tool_call_count": baseline_hashes["tool_call_count"],
        "candidate_tool_call_count": candidate_hashes["tool_call_count"],
        "sql_hash_unchanged": baseline_hashes["sql_hash"] == candidate_hashes["sql_hash"],
        "api_hash_unchanged": baseline_hashes["api_hash"] == candidate_hashes["api_hash"],
        "tool_call_count_unchanged": baseline_hashes["tool_call_count"] == candidate_hashes["tool_call_count"],
    }


def build_evidence_registry(
    query: str,
    trajectory: dict[str, Any],
    *,
    local_evidence: list[dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    registry: dict[str, dict[str, Any]] = {}
    for idx, value in enumerate(_query_visible_values(query)):
        evidence_id = f"query_text:{idx}"
        registry[evidence_id] = {
            "evidence_id": evidence_id,
            "evidence_source": "query_text",
            "text": value,
            "value": value,
        }
    for step_idx, step in enumerate(trajectory.get("steps", [])):
        if step.get("kind") == "sql_call":
            rows = ((step.get("result") or {}).get("rows") or []) if isinstance(step.get("result"), dict) else []
            for row_idx, row in enumerate(rows[:3]):
                evidence_id = f"sql_row:{step_idx}:{row_idx}"
                registry[evidence_id] = {
                    "evidence_id": evidence_id,
                    "evidence_source": "sql_row",
                    "text": _compact_row_text(row),
                    "value": row,
                }
        elif step.get("kind") == "api_call":
            method = str(step.get("method") or "GET").upper()
            path = str(step.get("url") or "")
            params = _safe_params(step.get("params") or {})
            evidence_id = f"endpoint_params:{step_idx}"
            text = f"{method} {path}"
            if params:
                text += " params " + ", ".join(f"{key}={value}" for key, value in list(params.items())[:4])
            registry[evidence_id] = {
                "evidence_id": evidence_id,
                "evidence_source": "endpoint_params",
                "text": text,
                "value": {"method": method, "path": path, "params": params},
            }
            if (step.get("result") or {}).get("dry_run"):
                dry_id = f"dry_run_label:{step_idx}"
                registry[dry_id] = {
                    "evidence_id": dry_id,
                    "evidence_source": "dry_run_label",
                    "text": "dry_run",
                    "value": True,
                }
    local_hits = _safe_local_evidence(local_evidence or [])
    coverage = requested_fact_coverage(query, local_hits)
    covered_ids = {item.get("evidence_id") for item in coverage.get("covered_hits", [])}
    for idx, hit in enumerate(local_hits[:6]):
        if covered_ids and hit.get("evidence_id") not in covered_ids:
            continue
        evidence_id = str(hit.get("evidence_id") or f"parquet_evidence:{idx}")
        registry[evidence_id] = {
            "evidence_id": evidence_id,
            "evidence_source": "parquet_evidence",
            "text": _local_hit_text(hit),
            "value": hit.get("matched_value") or hit.get("value_preview") or hit.get("values"),
        }
    return registry


def generate_supportable_rewrites(
    query: str,
    trajectory: dict[str, Any],
    *,
    local_evidence: list[dict[str, Any]] | None = None,
    max_extra_answer_tokens: int = 20,
) -> list[SupportableAnswerRewrite]:
    registry = build_evidence_registry(query, trajectory, local_evidence=local_evidence)
    baseline_answer = str(trajectory.get("final_answer") or "")
    baseline_answer_tokens = estimate_tokens(baseline_answer)
    target_answer_tokens = baseline_answer_tokens + max_extra_answer_tokens
    dry_id = _first_evidence_id(registry, "dry_run_label")
    endpoint_id = _first_evidence_id(registry, "endpoint_params")
    query_id = _first_evidence_id(registry, "query_text")
    parquet_id = _first_evidence_id(registry, "parquet_evidence")
    noun = _noun(query)
    intent = _intent(query)
    subject = _subject(query, registry, noun)

    candidates: list[tuple[str, list[dict[str, Any]]]] = []
    if dry_id and endpoint_id:
        endpoint_value = registry[endpoint_id].get("value") if isinstance(registry[endpoint_id].get("value"), dict) else {}
        compact_endpoint = f"{endpoint_value.get('method', 'GET')} {endpoint_value.get('path') or registry[endpoint_id]['text']}"
        endpoint_label = _endpoint_label(str(endpoint_value.get("path") or registry[endpoint_id]["text"]), noun, intent)
        candidates.append(
            (
                "family_endpoint_unavailable",
                [
                    _supported_claim(f"GET {endpoint_label} endpoint.", endpoint_id),
                    _unsupported_claim(f"Live {noun} {intent} unavailable in dry-run mode.", dry_id),
                ],
            )
        )
        candidates.append(
            (
                "compact_endpoint_unavailable",
                [
                    _supported_claim(f"{compact_endpoint}.", endpoint_id),
                    _unsupported_claim(f"Live {noun} {intent} unavailable in dry-run mode.", dry_id),
                ],
            )
        )
        candidates.append(
            (
                "minimal_endpoint_fact",
                [
                    _supported_claim(f"Selected endpoint: {registry[endpoint_id]['text']}.", endpoint_id),
                    _unsupported_claim(f"The requested live {noun} {intent} is unavailable in dry-run mode.", dry_id),
                ],
            )
        )
    if dry_id and endpoint_id:
        first_claim = _supported_claim(f"Requested {noun}: {subject}.", query_id) if query_id else _supported_claim(f"Selected endpoint: {registry[endpoint_id]['text']}.", endpoint_id)
        candidates.append(
            (
                "query_entity_plus_endpoint",
                [
                    first_claim,
                    _supported_claim(f"Endpoint: {registry[endpoint_id]['text']}.", endpoint_id),
                    _unsupported_claim(f"The requested live {intent} is unavailable in dry-run mode.", dry_id),
                ],
            )
        )
    if dry_id:
        if query_id:
            candidates.append(
                (
                    "query_subject_unavailable",
                    [
                        _supported_claim(f"{noun.title()}: {subject}.", query_id),
                        _unsupported_claim(f"Live {intent} unavailable in dry-run mode.", dry_id),
                    ],
                )
            )
        candidates.append(
            (
                "unavailable_requested_fact_only",
                [_unsupported_claim(f"The requested live {noun} {intent} is unavailable in dry-run mode.", dry_id)],
            )
        )
    if parquet_id and dry_id:
        candidates.append(
            (
                "parquet_hint_plus_unavailable",
                [
                    _supported_claim(f"Parquet evidence: {registry[parquet_id]['text']}.", parquet_id),
                    _unsupported_claim(f"The requested live {noun} {intent} is unavailable in dry-run mode.", dry_id),
                ],
            )
        )

    rewrites: list[SupportableAnswerRewrite] = []
    seen_answers: set[str] = set()
    for candidate_id, claims in candidates:
        answer = " ".join(claim["claim_text"] for claim in claims).strip()
        answer = _shorten_answer(answer, max_chars=360)
        if answer in seen_answers:
            continue
        seen_answers.add(answer)
        validation = validate_supportable_claims(
            answer,
            claims,
            registry,
            trajectory=trajectory,
            max_answer_tokens=target_answer_tokens,
        )
        rewrites.append(
            SupportableAnswerRewrite(
                candidate_id=candidate_id,
                answer=answer,
                claims=claims,
                evidence_registry=registry,
                validation=validation,
                baseline_answer_tokens=baseline_answer_tokens,
                candidate_answer_tokens=estimate_tokens(answer),
                target_answer_tokens=target_answer_tokens,
            )
        )
    return rewrites


def validate_supportable_claims(
    answer: str,
    claims: list[dict[str, Any]],
    evidence_registry: dict[str, dict[str, Any]],
    *,
    trajectory: dict[str, Any] | None = None,
    max_answer_tokens: int | None = None,
) -> dict[str, Any]:
    failures: list[str] = []
    if not claims:
        failures.append("missing_claims")
    reconstructed = " ".join(str(claim.get("claim_text") or "") for claim in claims).strip()
    if reconstructed and reconstructed != answer:
        failures.append("answer_claim_text_mismatch")
    if SECRET_LIKE_RE.search(answer):
        failures.append("secret_like_text")
    if max_answer_tokens is not None and estimate_tokens(answer) > max_answer_tokens:
        failures.append("answer_token_budget_exceeded")
    for claim in claims:
        failures.extend(_validate_claim_schema(claim, evidence_registry))
    if trajectory is not None and _uses_dry_run_payload_values(answer, trajectory):
        failures.append("dry_run_payload_value_used")
    return {
        "ok": not failures,
        "failures": sorted(set(failures)),
        "claim_count": len(claims),
        "answer_tokens": estimate_tokens(answer),
        "max_answer_tokens": max_answer_tokens,
    }


def parse_llm_rewrite_payload(content: str) -> tuple[list[dict[str, Any]], str | None]:
    text = (content or "").strip()
    if not text:
        return [], "invalid_json:empty_content"
    if text.startswith("```"):
        text = text.strip("`")
        text = text.removeprefix("json").strip()
    try:
        payload = json.loads(text)
    except Exception:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return [], "invalid_json:no_json_object"
        try:
            payload = json.loads(text[start : end + 1])
        except Exception as exc:
            return [], f"invalid_json:{str(exc)[:120]}"
    rewrites = payload.get("rewrites") if isinstance(payload, dict) else None
    if rewrites is None and isinstance(payload, dict):
        rewrites = payload.get("candidates")
    if not isinstance(rewrites, list):
        return [], "invalid_json:rewrites_not_list"
    return [item for item in rewrites if isinstance(item, dict)][:5], None


def _validate_claim_schema(claim: dict[str, Any], registry: dict[str, dict[str, Any]]) -> list[str]:
    failures: list[str] = []
    evidence_id = claim.get("evidence_id")
    source = claim.get("evidence_source")
    supported = claim.get("supported")
    unsupported_action = claim.get("unsupported_action")
    text = claim.get("claim_text")
    if not isinstance(text, str) or not text.strip():
        failures.append("missing_claim_text")
    if source not in ALLOWED_EVIDENCE_SOURCES:
        failures.append("invalid_evidence_source")
    if not isinstance(evidence_id, str) or evidence_id not in registry:
        failures.append("missing_or_unknown_evidence_id")
    elif registry[evidence_id].get("evidence_source") != source:
        failures.append("evidence_source_mismatch")
    if supported is True:
        if unsupported_action is not None:
            failures.append("supported_claim_has_unsupported_action")
    elif supported is False:
        if source != "dry_run_label":
            failures.append("unsupported_claim_without_dry_run_label")
        if unsupported_action != "mark_unavailable":
            failures.append("unsupported_claim_missing_mark_unavailable")
    else:
        failures.append("supported_not_boolean")
    return failures


def _supported_claim(text: str, evidence_id: str | None) -> dict[str, Any]:
    return {
        "claim_text": text,
        "evidence_id": evidence_id or "",
        "evidence_source": "query_text" if evidence_id and evidence_id.startswith("query_text:") else "endpoint_params" if evidence_id and evidence_id.startswith("endpoint_params:") else "parquet_evidence" if evidence_id and not evidence_id.startswith(("dry_run_label:", "sql_row:")) else "sql_row",
        "supported": True,
        "unsupported_action": None,
    }


def _unsupported_claim(text: str, evidence_id: str) -> dict[str, Any]:
    return {
        "claim_text": text,
        "evidence_id": evidence_id,
        "evidence_source": "dry_run_label",
        "supported": False,
        "unsupported_action": "mark_unavailable",
    }


def _first_evidence_id(registry: dict[str, dict[str, Any]], source: str) -> str | None:
    for evidence_id, evidence in registry.items():
        if evidence.get("evidence_source") == source:
            return evidence_id
    return None


def _uses_dry_run_payload_values(answer: str, trajectory: dict[str, Any]) -> bool:
    lowered = answer.lower()
    allowed = json.dumps({"api": generated_api_calls(trajectory)}, sort_keys=True).lower()
    for value in _dry_run_payload_scalars(trajectory):
        text = str(value).strip()
        if len(text) < 3:
            continue
        if text.lower() in allowed:
            continue
        if text.lower() in lowered:
            return True
    return False


def _dry_run_payload_scalars(trajectory: dict[str, Any]) -> list[Any]:
    values: list[Any] = []

    def walk(obj: Any) -> None:
        if isinstance(obj, dict):
            for key, value in obj.items():
                if key in {"dry_run", "ok", "method", "url", "params"}:
                    continue
                walk(value)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)
        elif isinstance(obj, (str, int, float)) and not isinstance(obj, bool):
            values.append(obj)

    for step in trajectory.get("steps", []):
        if step.get("kind") == "api_call" and (step.get("result") or {}).get("dry_run"):
            walk(step.get("result") or {})
    return values


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


def _safe_params(params: dict[str, Any]) -> dict[str, str]:
    safe: dict[str, str] = {}
    if not isinstance(params, dict):
        return safe
    for key, value in params.items():
        key_norm = re.sub(r"[^a-z0-9]", "", str(key).lower())
        if any(part in key_norm for part in ["token", "secret", "password", "authorization", "clientid", "clientsecret", "key"]):
            continue
        if isinstance(value, (dict, list)) or value in (None, ""):
            continue
        safe[str(key)] = str(value)
    return safe


def _query_visible_values(query: str) -> list[str]:
    values = [(single or double).strip() for single, double in re.findall(r"'([^']+)'|\"([^\"]+)\"", query)]
    values.extend(re.findall(r"\b01[A-Z0-9]{20,}\b", query))
    values.extend(re.findall(r"\b[0-9a-f]{12,}(?:-[0-9a-f]{4,})*\b", query, flags=re.I))
    values.extend(re.findall(r"\b20\d{2}-\d{2}-\d{2}\b", query))
    for status in ["success", "failed", "queued", "processing", "inactive", "published", "uncategorized"]:
        if re.search(rf"\b{status}\b", query, re.I):
            values.append(status)
    return list(dict.fromkeys(value for value in values if value))


def _compact_row_text(row: Any) -> str:
    if not isinstance(row, dict):
        return str(row)[:160]
    parts = []
    for key, value in list(row.items())[:4]:
        if value not in (None, "", [], {}):
            parts.append(f"{key}={value}")
    return ", ".join(parts)[:180]


def _local_hit_text(hit: dict[str, Any]) -> str:
    table = hit.get("source_table") or hit.get("table")
    column = hit.get("source_column") or hit.get("column")
    value = hit.get("matched_value") or hit.get("value_preview")
    if value in (None, "") and isinstance(hit.get("values"), dict):
        value = next(iter(hit["values"].values()), None)
    return f"{table}.{column}={value}"[:180]


def _intent(query: str) -> str:
    lowered = query.lower()
    if any(term in lowered for term in ["how many", "count", "number of", "total"]):
        return "count"
    if any(term in lowered for term in ["when", "date", "recent", "updated", "created", "published"]):
        return "date"
    if any(term in lowered for term in ["which", "list", "show all", "files"]):
        return "list"
    if "status" in lowered or "state" in lowered:
        return "status"
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


def _subject(query: str, registry: dict[str, dict[str, Any]], noun: str) -> str:
    query_id = _first_evidence_id(registry, "query_text")
    if query_id:
        return str(registry[query_id].get("text"))
    endpoint_id = _first_evidence_id(registry, "endpoint_params")
    if endpoint_id:
        return str(registry[endpoint_id].get("value", {}).get("path") or f"the requested {noun}")
    return f"the requested {noun}"


def _endpoint_label(path: str, noun: str, intent: str) -> str:
    lowered = path.lower()
    if "export/batches" in lowered and "files" in lowered:
        return "batch files"
    if "catalog/batches" in lowered:
        return "batch detail" if intent == "detail" else "batches"
    if "mergepolicies" in lowered:
        return "merge policies"
    if "segment/definitions" in lowered:
        return "segment definitions"
    if "segment/jobs" in lowered:
        return "segment jobs"
    if "unifiedtags" in lowered:
        return "tags"
    return noun


def _shorten_answer(answer: str, *, max_chars: int) -> str:
    answer = " ".join(answer.split())
    return answer if len(answer) <= max_chars else answer[: max_chars - 14].rstrip() + " [truncated]"


def _sha256_json(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()
