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
    candidate_family: str = "custom"
    local_index_hits: list[dict[str, Any]] = field(default_factory=list)
    dependency_requirements: list[str] = field(default_factory=list)
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
    "exact_public_query_string",
    "exact_public_example_query",
    "exact_query_string",
    "public_example_query",
    "public_query_string",
}

RUNTIME_GOLD_SIGNAL_PATTERNS = (
    "gold",
    "expected answer",
    "memorized answer",
    "public query",
    "public example",
    "query_id",
)

DEPENDENCY_NAMES = {
    "local_index": "codex/score075-local-index",
    "endpoint_routing": "codex/score075-endpoint-routing",
    "answer_shape": "codex/score075-answer-shape",
}


def generate_targeted_candidates(
    *,
    query_id: str,
    query: str,
    baseline_trajectory: dict[str, Any],
    schema_index: Any,
    endpoint_catalog: EndpointCatalog,
    failure_row: dict[str, Any] | None = None,
    local_index_evidence: list[dict[str, Any]] | None = None,
    endpoint_rule_candidates: list[dict[str, Any]] | None = None,
    answer_shape_hints: dict[str, Any] | None = None,
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
    local_index_evidence = local_index_evidence or []
    endpoint_rule_candidates = endpoint_rule_candidates or []
    answer_shape_hints = answer_shape_hints or {}
    candidates: list[TargetedCandidate] = []
    candidates.append(
        _candidate(
            "current_baseline",
            "baseline",
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
        family_id = "schema_relation" if _is_schema_relation_query(query) else "sql_first"
        candidates.append(
            _candidate(
                "schema_relation_preserving" if family_id == "schema_relation" else "sql_first_template",
                family_id,
                f"Reusable SQL template for {sql_template.family}.",
                sql_template.sql,
                baseline_api[0] if baseline_api else None,
                family,
                ["schema_relation_preservation" if family_id == "schema_relation" else "sql_template", sql_template.family],
                ["domain_vocabulary", "schema_metadata", "sql_template", family_id],
            )
        )
        candidates.append(
            _candidate(
                "ast_clean_sql_template",
                "ast_clean",
                f"AST-clean SQL template for {sql_template.family}.",
                sql_template.sql,
                None,
                family,
                ["ast_clean_sql", sql_template.family],
                ["schema_metadata", "sql_ast_validation", "sql_template"],
            )
        )

    api_templates = find_api_templates(query)
    for index, template in enumerate(api_templates[:3], start=1):
        if "gold" in str(template.family).lower():
            continue
        api_call = {"method": template.method, "path": template.path, "params": template.params}
        if not baseline_api or _canonical_api(api_call) != _canonical_api(baseline_api[0]):
            candidates.append(
                _candidate(
                    f"api_template_{index}",
                    "api_first",
                    f"Reusable endpoint template for {template.family}.",
                    None if _looks_api_first(query, family, failure_row or {}) else baseline_sql,
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
                "endpoint_rerank",
                "Endpoint-family ranked catalog candidate.",
                baseline_sql,
                top_context_api,
                family,
                ["endpoint_family_ranking"],
                ["endpoint_catalog", "endpoint_family_confidence"],
            )
        )

    for rule in endpoint_rule_candidates[:2]:
        api_call = _endpoint_rule_api_call(rule, endpoint_catalog)
        if api_call and (not baseline_api or _canonical_api(api_call) != _canonical_api(baseline_api[0])):
            candidates.append(
                _candidate(
                    f"endpoint_rule_{_safe_id(str(rule.get('rule_id') or 'candidate'))}",
                    "endpoint_rerank",
                    f"Endpoint/schema rule candidate {rule.get('rule_id')}.",
                    baseline_sql,
                    api_call,
                    family,
                    ["endpoint_schema_rule_candidate"],
                    ["endpoint_catalog", "domain_vocabulary", "endpoint_schema_rule"],
                    dependency_requirements=[DEPENDENCY_NAMES["endpoint_routing"]],
                )
            )

    if baseline_sql and _looks_like_count_question(query) and "count(" not in baseline_sql.lower():
        count_sql = _count_wrapped_sql(baseline_sql)
        candidates.append(
            _candidate(
                "count_shape_normalized",
                "count_list",
                "Count-vs-list normalized SQL candidate.",
                count_sql,
                baseline_api[0] if baseline_api else None,
                family,
                ["answer_shape_normalization"],
                ["query_answer_shape", "sql_ast"],
            )
        )

    if baseline_sql and _looks_like_date_or_status_question(query):
        normalized_sql = _date_status_normalized_sql(baseline_sql, query)
        if normalized_sql and _normalize_sql(normalized_sql) != _normalize_sql(baseline_sql):
            candidates.append(
                _candidate(
                    "date_status_normalized",
                    "date_status",
                    "Date/status normalized SQL candidate derived from reusable query vocabulary.",
                    normalized_sql,
                    baseline_api[0] if baseline_api else None,
                    family,
                    ["date_status_normalization"],
                    ["query_status_terms", "query_date_terms", "sql_ast"],
                )
            )

    if local_index_evidence:
        candidates.append(
            _candidate(
                "local_index_grounded_plan",
                "local_index_grounded",
                "Local Parquet-index evidence grounding candidate.",
                baseline_sql,
                baseline_api[0] if baseline_api else None,
                family,
                ["local_index_evidence_grounding"],
                ["local_parquet_index", "reusable_entity_lookup", "general_value_match"],
                local_index_hits=_safe_local_index_hits(local_index_evidence),
                dependency_requirements=[DEPENDENCY_NAMES["local_index"]],
            )
        )

    if _has_dry_run_api(baseline_trajectory) or (failure_row or {}).get("likely_failure_type") == "answer_format_issue":
        candidates.append(
            _candidate(
                "dry_run_evidence_answer",
                "answer_evidence",
                "Dry-run evidence-aware answer composition candidate with unchanged SQL/API plan.",
                baseline_sql,
                baseline_api[0] if baseline_api else None,
                family,
                ["answer_only_ablation", "dry_run_evidence_composition"],
                ["recorded_evidence_only", "selected_endpoint_params", "query_visible_text"],
                expected_answer_shape=_answer_shape_for_query(query, answer_shape_hints),
                local_index_hits=_safe_local_index_hits(local_index_evidence),
                dependency_requirements=[DEPENDENCY_NAMES["answer_shape"]],
            )
        )

    answer_shape = _answer_shape_for_query(query, answer_shape_hints)
    if answer_shape != "list_or_detail":
        candidates.append(
            _candidate(
                f"answer_shape_{answer_shape}",
                "answer_shape",
                f"Answer-shape normalization candidate for {answer_shape} responses.",
                baseline_sql,
                baseline_api[0] if baseline_api else None,
                family,
                ["answer_shape_normalization"],
                ["query_answer_shape", "recorded_evidence_only"],
                expected_answer_shape=answer_shape,
                dependency_requirements=[DEPENDENCY_NAMES["answer_shape"]],
            )
        )

    deduped: list[TargetedCandidate] = []
    seen: set[tuple[str, str, str]] = set()
    for candidate in candidates:
        key = (candidate.candidate_family, _normalize_sql(candidate.sql), _canonical_api(candidate.api_call))
        if key in seen:
            continue
        seen.add(key)
        checked = apply_leakage_checks(candidate, query=query)
        deduped.append(checked)
        if len(deduped) >= max_candidates:
            break
    return [candidate.to_dict() for candidate in deduped]


def _has_dry_run_api(trajectory: dict[str, Any]) -> bool:
    return any(
        step.get("kind") == "api_call" and (step.get("result") or {}).get("dry_run")
        for step in trajectory.get("steps", [])
    )


def apply_leakage_checks(candidate: TargetedCandidate, *, query: str = "") -> TargetedCandidate:
    reasons: list[str] = []
    features = set(candidate.trigger_features)
    blocked = sorted(features & BLOCKED_TRIGGER_FEATURES)
    if blocked:
        reasons.extend(f"blocked_trigger:{item}" for item in blocked)
    signal_text = " ".join(
        [
            candidate.generation_reason,
            candidate.rule_source,
            *candidate.source_signals,
            *candidate.trigger_features,
        ]
    ).lower()
    for pattern in RUNTIME_GOLD_SIGNAL_PATTERNS:
        if pattern in signal_text:
            reasons.append(f"blocked_runtime_signal:{pattern.replace(' ', '_')}")
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
    candidate_family: str,
    reason: str,
    sql: str | None,
    api_call: dict[str, Any] | None,
    family: str,
    risk_flags: list[str],
    source_signals: list[str],
    *,
    expected_answer_shape: str | None = None,
    local_index_hits: list[dict[str, Any]] | None = None,
    dependency_requirements: list[str] | None = None,
) -> TargetedCandidate:
    return TargetedCandidate(
        candidate_id=candidate_id,
        candidate_family=candidate_family,
        generation_reason=reason,
        sql=sql,
        api_call=api_call,
        expected_answer_shape=expected_answer_shape or ("count" if "count" in candidate_id else "list_or_detail"),
        endpoint_family=family,
        schema_family=family,
        local_index_hits=local_index_hits or [],
        dependency_requirements=dependency_requirements or [],
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


def _endpoint_rule_api_call(rule: dict[str, Any], endpoint_catalog: EndpointCatalog) -> dict[str, Any] | None:
    family = str(rule.get("target_family") or "")
    if not family or family == "unknown":
        return None
    endpoints = [
        endpoint
        for endpoint in endpoint_catalog.endpoints
        if endpoint.id == family or family in endpoint.id or family in "_".join(endpoint.domains).lower()
    ]
    if not endpoints:
        return None
    endpoint = endpoints[0]
    if endpoint.path_params:
        return None
    return {"method": endpoint.method, "path": endpoint.path, "params": dict(endpoint.common_params)}


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


def _looks_like_date_or_status_question(query: str) -> bool:
    lowered = query.lower()
    return bool(
        re.search(r"\b20\d{2}-\d{2}-\d{2}\b", lowered)
        or any(term in lowered for term in ["status", "state", "failed", "success", "published", "inactive", "recent", "last ", "date"])
    )


def _looks_api_first(query: str, family: str, failure_row: dict[str, Any]) -> bool:
    lowered = query.lower()
    if failure_row.get("likely_failure_type") in {"wrong_endpoint_family", "missing_api_candidate", "dry_run_api_only_issue"}:
        return True
    return bool(
        any(term in lowered for term in ["api", "endpoint", "batch files", "failed files", "merge polic", "segment job", "tags", "audit events", "observability"])
        or family in {"batch_files", "batch_failed_files", "merge_policies", "segment_jobs", "observability_metrics"}
    )


def _is_schema_relation_query(query: str) -> bool:
    lowered = query.lower()
    has_schema = any(term in lowered for term in ["schema", "schemas", "blueprint", "blueprints"])
    has_dataset = any(term in lowered for term in ["dataset", "datasets", "collection", "collections"])
    relation = any(term in lowered for term in ["using", "based on", "associated", "built from", "used by", "same schema", "connected"])
    return has_schema and has_dataset and relation


def _count_wrapped_sql(sql: str) -> str:
    stripped = sql.strip().rstrip(";")
    return f"SELECT COUNT(*) AS count FROM ({stripped}) AS candidate_rows"


def _date_status_normalized_sql(sql: str, query: str) -> str | None:
    stripped = sql.strip().rstrip(";")
    lowered_sql = stripped.lower()
    lowered_query = query.lower()
    if "order by" in lowered_sql or "limit" in lowered_sql:
        return None
    if any(term in lowered_query for term in ["recent", "latest", "last "]):
        for column in ["updated_time", "updatedtime", "created_time", "createdtime", "published_time", "lastdeployedtime"]:
            if column in lowered_sql:
                return f"{stripped} ORDER BY {column} DESC LIMIT 50"
    if any(term in lowered_query for term in ["failed", "success", "inactive", "published"]) and " where " not in lowered_sql:
        # Do not invent status values; expose this as a low-confidence shape
        # candidate only when the selected SQL already projected a state/status.
        if "status" in lowered_sql or "state" in lowered_sql:
            return f"{stripped} LIMIT 50"
    return None


def _answer_shape_for_query(query: str, hints: dict[str, Any]) -> str:
    hinted = str(hints.get("expected_answer_shape") or "")
    if hinted and hinted != "unknown":
        return _safe_id(hinted)
    lowered = query.lower()
    if _looks_like_count_question(query):
        return "count"
    if any(term in lowered for term in ["when", "date", "published", "created", "updated"]):
        return "date"
    if any(term in lowered for term in ["status", "state", "failed", "success", "inactive"]):
        return "status"
    if any(term in lowered for term in ["list", "show", "give me", "which"]):
        return "list"
    return "list_or_detail"


def _safe_local_index_hits(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    safe_hits = []
    for hit in hits[:5]:
        source = str(hit.get("source") or hit.get("provenance") or "")
        classification = str(hit.get("classification") or "")
        if "gold" in source.lower() or "gold" in classification.lower():
            continue
        payload = {
            "classification": classification or "reusable_value_grounding",
            "source": source or "local_parquet_index",
            "table": hit.get("table") or hit.get("source_table"),
            "column": hit.get("column") or hit.get("source_column"),
            "value_preview": str(hit.get("value") or hit.get("matched_value") or "")[:80],
        }
        for key in ["evidence_id", "source_table", "source_column", "matched_value", "values", "columns"]:
            value = hit.get(key)
            if value not in (None, "", [], {}):
                payload[key] = value
        safe_hits.append(payload)
    return safe_hits


def _normalize_sql(sql: str | None) -> str:
    return re.sub(r"\s+", " ", str(sql or "").strip().lower())


def _canonical_api(api_call: dict[str, Any] | None) -> str:
    if not api_call:
        return ""
    return f"{str(api_call.get('method') or '').upper()} {api_call.get('path') or api_call.get('url') or ''} {api_call.get('params') or {}}"


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _safe_id(text: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", text.strip().lower()).strip("_") or "candidate"
