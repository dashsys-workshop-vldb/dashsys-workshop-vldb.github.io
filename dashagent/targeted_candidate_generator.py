from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from .api_templates import find_api_templates
from .candidate_context_builder import build_candidate_context
from .endpoint_catalog import EndpointCatalog
from .eval_harness import generated_api_calls, first_generated_sql
from .query_tokens import extract_query_tokens
from .sql_templates import find_sql_template


@dataclass(frozen=True)
class TargetedCandidate:
    candidate_id: str
    generation_reason: str
    sql: str | None
    api_call: dict[str, Any] | None
    expected_answer_shape: str
    endpoint_family: str
    schema_family: str
    risk_flags: list[str] = field(default_factory=list)
    estimated_tool_calls: int = 0
    source_signals: list[str] = field(default_factory=list)
    rule_source: str = "deterministic_family_rule"
    trigger_features: list[str] = field(default_factory=list)
    leakage_check_passed: bool = True
    leakage_reasons: list[str] = field(default_factory=list)
    generalizable_family: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


BLOCKED_TRIGGER_FEATURES = {
    "query_id",
    "exact_full_query_string",
    "manual_expected_answer",
    "memorized_expected_answer",
    "manual_memorized_expected_answer",
    "manual_gold_sql",
    "manual_gold_api",
    "memorized_gold_sql",
    "memorized_gold_api",
    "gold_sql_path",
    "gold_api_path",
}


def generate_targeted_candidates(
    *,
    query_id: str,
    query: str,
    baseline_trajectory: dict[str, Any],
    schema_index: Any,
    endpoint_catalog: EndpointCatalog,
    failure_row: dict[str, Any] | None = None,
    max_candidates: int = 8,
) -> list[dict[str, Any]]:
    """Generate reusable, non-gold candidate plans for an isolated search.

    The generator intentionally avoids query-id branches and exact public-query
    triggers. Public labels may score candidates later, but they do not feed
    candidate construction.
    """

    context = build_candidate_context(query, schema_index, endpoint_catalog)
    tokens = extract_query_tokens(query)
    baseline_sql = first_generated_sql(baseline_trajectory)
    baseline_api = generated_api_calls(baseline_trajectory)
    family = _general_family(query, tokens, context, failure_row or {})
    candidates: list[TargetedCandidate] = []
    candidates.append(
        _candidate(
            "current_baseline",
            "Current SQL_FIRST_API_VERIFY plan.",
            baseline_sql,
            baseline_api[0] if baseline_api else None,
            family,
            ["baseline_plan"],
            ["domain_tokens", "current_plan"],
        )
    )

    sql_template = find_sql_template(query, schema_index)
    if sql_template and sql_template.sql and _normalize_sql(sql_template.sql) != _normalize_sql(baseline_sql):
        candidates.append(
            _candidate(
                "sql_template_clean",
                f"Reusable SQL template for {sql_template.family}.",
                sql_template.sql,
                baseline_api[0] if baseline_api else None,
                family,
                ["sql_template", sql_template.family],
                ["domain_vocabulary", "schema_metadata", "sql_template"],
            )
        )

    api_templates = find_api_templates(query)
    for index, template in enumerate(api_templates[:3], start=1):
        api_call = {"method": template.method, "path": template.path, "params": template.params}
        if not baseline_api or _canonical_api(api_call) != _canonical_api(baseline_api[0]):
            candidates.append(
                _candidate(
                    f"api_template_{index}",
                    f"Reusable endpoint template for {template.family}.",
                    baseline_sql,
                    api_call,
                    family,
                    ["api_template", template.family],
                    ["endpoint_catalog", "domain_vocabulary", "api_template"],
                )
            )

    top_context_api = _top_context_api(context)
    if top_context_api and (not baseline_api or _canonical_api(top_context_api) != _canonical_api(baseline_api[0])):
        candidates.append(
            _candidate(
                "endpoint_family_reranked",
                "Endpoint-family ranked catalog candidate.",
                baseline_sql,
                top_context_api,
                family,
                ["endpoint_family_ranking"],
                ["endpoint_catalog", "endpoint_family_confidence"],
            )
        )

    if baseline_sql and _looks_like_count_question(query) and "count(" not in baseline_sql.lower():
        count_sql = _count_wrapped_sql(baseline_sql)
        candidates.append(
            _candidate(
                "count_shape_normalized",
                "Count-vs-list normalized SQL candidate.",
                count_sql,
                baseline_api[0] if baseline_api else None,
                family,
                ["answer_shape_normalization"],
                ["query_answer_shape", "sql_ast"],
            )
        )

    deduped: list[TargetedCandidate] = []
    seen: set[tuple[str, str]] = set()
    for candidate in candidates:
        key = (_normalize_sql(candidate.sql), _canonical_api(candidate.api_call))
        if key in seen:
            continue
        seen.add(key)
        checked = apply_leakage_checks(candidate, query=query)
        deduped.append(checked)
        if len(deduped) >= max_candidates:
            break
    return [candidate.to_dict() for candidate in deduped]


def apply_leakage_checks(candidate: TargetedCandidate, *, query: str = "") -> TargetedCandidate:
    reasons: list[str] = []
    features = set(candidate.trigger_features)
    blocked = sorted(features & BLOCKED_TRIGGER_FEATURES)
    if blocked:
        reasons.extend(f"blocked_trigger:{item}" for item in blocked)
    if any("gold" in signal.lower() for signal in candidate.source_signals):
        reasons.append("gold_signal_used_for_generation")
    if "exact_public_entity" in features and "general_value_match" not in features:
        reasons.append("exact_public_entity_without_general_value_match")
    if query and _normalize_text(query) in {_normalize_text(feature) for feature in candidate.trigger_features}:
        reasons.append("exact_full_query_string_trigger")
    return TargetedCandidate(
        **{
            **candidate.to_dict(),
            "leakage_check_passed": not reasons,
            "leakage_reasons": sorted(set(reasons)),
        }
    )


def _candidate(
    candidate_id: str,
    reason: str,
    sql: str | None,
    api_call: dict[str, Any] | None,
    family: str,
    risk_flags: list[str],
    source_signals: list[str],
) -> TargetedCandidate:
    return TargetedCandidate(
        candidate_id=candidate_id,
        generation_reason=reason,
        sql=sql,
        api_call=api_call,
        expected_answer_shape="count" if "count" in candidate_id else "list_or_detail",
        endpoint_family=family,
        schema_family=family,
        risk_flags=risk_flags,
        estimated_tool_calls=int(bool(sql)) + int(bool(api_call)),
        source_signals=source_signals,
        rule_source="reusable_domain_schema_endpoint_rule",
        trigger_features=source_signals,
        generalizable_family=family,
    )


def _top_context_api(context: dict[str, Any]) -> dict[str, Any] | None:
    apis = context.get("candidate_apis") or []
    if not apis:
        return None
    api = apis[0]
    return {"method": api.get("method", "GET"), "path": api.get("path") or api.get("url"), "params": api.get("params", {})}


def _general_family(query: str, tokens: Any, context: dict[str, Any], failure_row: dict[str, Any]) -> str:
    detected = ((context.get("endpoint_family_ranking") or {}).get("endpoint_family") or failure_row.get("predicted_endpoint_family"))
    if detected:
        return str(detected)
    words = set(getattr(tokens, "words", []) or [])
    if words & {"tag", "tags"}:
        return "tag"
    if words & {"batch", "batches", "file", "files"}:
        return "batch"
    if words & {"schema", "schemas", "dataset", "datasets", "collection", "collections"}:
        return "schema_dataset"
    if words & {"segment", "audience", "audiences"}:
        return "segment"
    if words & {"journey", "journeys"}:
        return "journey"
    return "unknown"


def _looks_like_count_question(query: str) -> bool:
    lowered = query.lower()
    return "how many" in lowered or "count" in lowered or lowered.startswith("number of ")


def _count_wrapped_sql(sql: str) -> str:
    stripped = sql.strip().rstrip(";")
    return f"SELECT COUNT(*) AS count FROM ({stripped}) AS candidate_rows"


def _normalize_sql(sql: str | None) -> str:
    return re.sub(r"\s+", " ", str(sql or "").strip().lower())


def _canonical_api(api_call: dict[str, Any] | None) -> str:
    if not api_call:
        return ""
    return f"{str(api_call.get('method') or '').upper()} {api_call.get('path') or api_call.get('url') or ''} {api_call.get('params') or {}}"


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())
