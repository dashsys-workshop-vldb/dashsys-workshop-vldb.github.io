from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from .targeted_candidate_generator import TargetedCandidate, apply_leakage_checks
from .validators import APIValidator, SQLValidator


@dataclass(frozen=True)
class LLMCandidateSearchStatus:
    available: bool
    provider: str | None
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def llm_candidate_search_status() -> LLMCandidateSearchStatus:
    if os.getenv("OPENAI_API_KEY"):
        return LLMCandidateSearchStatus(True, "openai", "OPENAI_API_KEY present")
    if os.getenv("OPENROUTER_API_KEY"):
        return LLMCandidateSearchStatus(True, "openrouter", "OPENROUTER_API_KEY present")
    return LLMCandidateSearchStatus(False, None, "No OPENAI_API_KEY or OPENROUTER_API_KEY present")


BLOCKED_PROMPT_KEYS = {
    "answer",
    "answer_score",
    "expected_answer",
    "final_answer",
    "gold",
    "gold_api",
    "gold_api_path",
    "gold_answer",
    "gold_sql",
    "gold_sql_path",
    "offline_score_delta",
    "strict_score_after",
    "strict_score_before",
}


def sanitize_for_llm_prompt(value: Any, *, max_items: int = 8, max_string_chars: int = 500) -> Any:
    """Remove gold/scoring/final-answer fields before constructing an LLM prompt."""

    if isinstance(value, dict):
        clean: dict[str, Any] = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if lowered in BLOCKED_PROMPT_KEYS or lowered.startswith("gold_") or lowered.endswith("_gold"):
                continue
            clean[str(key)] = sanitize_for_llm_prompt(item, max_items=max_items, max_string_chars=max_string_chars)
            if len(clean) >= max_items:
                break
        return clean
    if isinstance(value, list):
        return [sanitize_for_llm_prompt(item, max_items=max_items, max_string_chars=max_string_chars) for item in value[:max_items]]
    if isinstance(value, str):
        return value[:max_string_chars]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)[:max_string_chars]


def build_llm_candidate_prompt(
    *,
    query: str,
    schema_context: dict[str, Any],
    endpoint_catalog_summary: list[dict[str, Any]],
    failed_trajectory_summary: dict[str, Any],
    answer_shape: str,
) -> str:
    """Build a constrained prompt for optional isolated LLM candidate search.

    This prompt intentionally omits gold SQL, gold APIs, gold answers, and
    public-example answer strings. The generated plans still require
    deterministic validation/execution/scoring before any trial eligibility.
    """

    safe_schema_context = sanitize_for_llm_prompt(schema_context)
    safe_endpoint_catalog = sanitize_for_llm_prompt(endpoint_catalog_summary, max_items=30)
    safe_trajectory_summary = sanitize_for_llm_prompt(failed_trajectory_summary)
    return (
        "Generate up to 3 candidate SQL/API plans for an isolated diagnostic search.\n"
        "Constraints: do not use gold labels, public-example answers, memorized API paths, or exact full-query triggers. "
        "Use only the provided schema context, endpoint catalog, query wording, and answer-shape requirement. "
        "The output will be rejected unless it is generalizable and passes deterministic SQL/API/leakage validators.\n"
        f"Query: {query}\n"
        f"Expected answer shape: {answer_shape}\n"
        f"Schema context: {safe_schema_context}\n"
        f"Endpoint catalog summary: {safe_endpoint_catalog}\n"
        f"Current trajectory summary: {safe_trajectory_summary}\n"
        "Return JSON with a top-level candidates array. Each candidate must contain candidate_id, sql, api_call, "
        "generation_reason, source_signals, trigger_features, generalizable_family, endpoint_family, schema_family, "
        "and expected_answer_shape."
    )


def parse_llm_candidate_response(content: str) -> list[dict[str, Any]]:
    """Parse a JSON candidate response without trusting prose around it."""

    if not content.strip():
        return []
    candidates = _loads_candidate_json(content)
    if isinstance(candidates, dict):
        candidates = candidates.get("candidates") or candidates.get("plans") or []
    if not isinstance(candidates, list):
        return []
    return [item for item in candidates if isinstance(item, dict)]


def normalize_llm_candidate(
    raw: dict[str, Any],
    *,
    generalizable_family: str = "llm_diagnostic",
    query: str = "",
) -> dict[str, Any]:
    candidate = TargetedCandidate(
        candidate_id=str(raw.get("candidate_id") or "llm_candidate"),
        generation_reason=str(raw.get("generation_reason") or "LLM-proposed diagnostic candidate"),
        sql=raw.get("sql"),
        api_call=raw.get("api_call") if isinstance(raw.get("api_call"), dict) else None,
        expected_answer_shape=str(raw.get("expected_answer_shape") or "list_or_detail"),
        endpoint_family=str(raw.get("endpoint_family") or generalizable_family),
        schema_family=str(raw.get("schema_family") or generalizable_family),
        risk_flags=list(raw.get("risk_flags") or ["llm_generated_requires_validation"]),
        estimated_tool_calls=int(bool(raw.get("sql"))) + int(bool(raw.get("api_call"))),
        source_signals=list(raw.get("source_signals") or ["llm_diagnostic_prompt"]),
        rule_source="llm_isolated_candidate_search",
        trigger_features=list(raw.get("trigger_features") or ["schema_context", "endpoint_catalog", "query_vocabulary"]),
        generalizable_family=generalizable_family,
    )
    return apply_leakage_checks(candidate, query=query).to_dict()


def validate_llm_candidate(
    candidate: dict[str, Any],
    *,
    sql_validator: SQLValidator,
    api_validator: APIValidator,
) -> dict[str, Any]:
    """Run deterministic checks before any LLM candidate can reach execution search."""

    failed_checks: list[str] = []
    sql_validation: dict[str, Any] = {"ok": True, "errors": [], "warnings": [], "skipped": True}
    api_validation: dict[str, Any] = {"ok": True, "errors": [], "warnings": [], "skipped": True}
    sql = candidate.get("sql")
    api_call = candidate.get("api_call") if isinstance(candidate.get("api_call"), dict) else None
    if not sql and not api_call:
        failed_checks.append("candidate_missing_sql_and_api")
    if candidate.get("leakage_check_passed") is not True:
        failed_checks.append("leakage_check_failed")
    if not candidate.get("rule_source") or not candidate.get("trigger_features") or not candidate.get("generalizable_family"):
        failed_checks.append("missing_generalizable_rule_metadata")
    if sql:
        validation = sql_validator.validate(str(sql))
        sql_validation = validation.to_dict()
        if not validation.ok:
            failed_checks.append("sql_validation_failed")
    if api_call:
        method = str(api_call.get("method") or "GET").upper()
        path = str(api_call.get("path") or api_call.get("url") or "")
        params = api_call.get("params") if isinstance(api_call.get("params"), dict) else {}
        validation = api_validator.validate(method, path, params, {})
        api_validation = validation.to_dict()
        if not validation.ok:
            failed_checks.append("api_validation_failed")
    return {
        "deterministic_validators_passed": not failed_checks,
        "failed_checks": sorted(set(failed_checks)),
        "sql_validation": sql_validation,
        "api_validation": api_validation,
        "safe_for_execution_search": not failed_checks,
    }


def _loads_candidate_json(content: str) -> Any:
    try:
        return json.loads(content)
    except Exception:
        pass
    fenced = re.search(r"```(?:json)?\s*(.*?)```", content, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        try:
            return json.loads(fenced.group(1).strip())
        except Exception:
            pass
    start_candidates = [index for index in [content.find("{"), content.find("[")] if index >= 0]
    if not start_candidates:
        return []
    start = min(start_candidates)
    end = max(content.rfind("}"), content.rfind("]"))
    if end <= start:
        return []
    try:
        return json.loads(content[start : end + 1])
    except Exception:
        return []
