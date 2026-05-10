from __future__ import annotations

import os
import json
from dataclasses import asdict, dataclass, field
from typing import Any

from .targeted_candidate_generator import TargetedCandidate, apply_leakage_checks


@dataclass(frozen=True)
class LLMCandidateSearchStatus:
    available: bool
    provider: str | None
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def llm_candidate_search_status() -> LLMCandidateSearchStatus:
    if os.getenv("OPENROUTER_API_KEY"):
        return LLMCandidateSearchStatus(True, "openrouter", "OPENROUTER_API_KEY present")
    if os.getenv("OPENAI_API_KEY"):
        if "openrouter.ai" in os.getenv("OPENAI_BASE_URL", ""):
            return LLMCandidateSearchStatus(True, "openrouter", "OPENAI_API_KEY present with OpenRouter base URL")
        return LLMCandidateSearchStatus(True, "openai", "OPENAI_API_KEY present")
    return LLMCandidateSearchStatus(False, None, "No OPENAI_API_KEY or OPENROUTER_API_KEY present")


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

    return (
        "Generate up to 3 candidate SQL/API plans for an isolated diagnostic search.\n"
        "Constraints: do not use gold labels, public-example answers, memorized API paths, or exact full-query triggers. "
        "Use only the provided schema context, endpoint catalog, query wording, and answer-shape requirement.\n"
        f"Query: {query}\n"
        f"Expected answer shape: {answer_shape}\n"
        f"Schema context: {schema_context}\n"
        f"Endpoint catalog summary: {endpoint_catalog_summary}\n"
        f"Failed trajectory summary: {failed_trajectory_summary}\n"
        "Return JSON with candidates containing candidate_id, sql, api_call, generation_reason, and source_signals."
    )


def normalize_llm_candidate(raw: dict[str, Any], *, generalizable_family: str = "llm_diagnostic") -> dict[str, Any]:
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
    return apply_leakage_checks(candidate).to_dict()


def parse_llm_candidates(content: str) -> tuple[list[dict[str, Any]], str | None]:
    text = (content or "").strip()
    if not text:
        return [], "empty_content"
    if text.startswith("```"):
        text = text.strip("`")
        text = text.removeprefix("json").strip()
    try:
        payload = json.loads(text)
    except Exception:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                payload = json.loads(text[start : end + 1])
            except Exception as exc:
                return [], f"invalid_json:{str(exc)[:120]}"
        else:
            return [], "invalid_json:no_json_object"
    raw = payload.get("candidates") if isinstance(payload, dict) else payload
    if not isinstance(raw, list):
        return [], "invalid_json:candidates_not_list"
    normalized = [item for item in raw if isinstance(item, dict)]
    return normalized[:5], None
