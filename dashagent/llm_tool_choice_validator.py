from __future__ import annotations

import re
from typing import Any

from .endpoint_catalog import EndpointCatalog
from .trajectory import redact_secrets


DATA_TERMS = (
    "how many",
    "count",
    "list",
    "show",
    "which",
    "when",
    "status",
    "state",
    "date",
    "id",
    "ids",
)

SCHEMA_ENTITY_TERMS = (
    "journey",
    "journeys",
    "campaign",
    "campaigns",
    "dataset",
    "datasets",
    "collection",
    "collections",
    "schema",
    "schemas",
    "blueprint",
    "blueprints",
    "segment",
    "segments",
    "audience",
    "audiences",
    "destination",
    "destinations",
    "target",
    "targets",
    "connector",
    "connectors",
    "flow",
    "flows",
    "dataflow",
    "dataflows",
    "field",
    "fields",
    "property",
    "properties",
)

LIVE_API_TERMS = (
    "live api",
    "live endpoint",
    "adobe api",
    "api endpoint",
    "call api",
    "platform api",
    "ups audiences api",
)


def validate_tool_choice_plan(
    prompt: str,
    plan: dict[str, Any],
    schema_context: dict[str, Any],
    endpoint_catalog: EndpointCatalog,
) -> dict[str, Any]:
    """Validate a Pure LLM evidence-source plan against schema/API affordances."""

    plan = plan if isinstance(plan, dict) else {}
    preferred = _preferred_tool(plan)
    needs_sql = bool(plan.get("needs_local_sql"))
    needs_api = bool(plan.get("needs_live_api"))
    local_tables = _local_tables(schema_context)
    api_ids = _api_ids(plan)
    schema_grounded = _schema_grounded_prompt(prompt, schema_context)
    live_requested = _explicit_live_api_request(prompt)
    data_question = _data_question(prompt)
    endpoint_path_issue = _unresolved_endpoint(api_ids, endpoint_catalog)
    ignored_schema = bool(schema_grounded and local_tables and not plan.get("local_tables_that_may_answer"))

    if data_question and preferred == "none" and not needs_sql and not needs_api:
        return _result(
            ok=False,
            prompt=prompt,
            plan=plan,
            schema_context=schema_context,
            preferred=preferred,
            reason="tool_required",
            evidence_source="local_sql_required" if schema_grounded else "unclear",
            ignored_schema=ignored_schema,
        )

    if endpoint_path_issue:
        return _result(
            ok=False,
            prompt=prompt,
            plan=plan,
            schema_context=schema_context,
            preferred=preferred,
            reason="unresolved_api_path_param",
            evidence_source="unclear",
            ignored_schema=ignored_schema,
        )

    if preferred == "call_api" and schema_grounded and local_tables and not live_requested and not needs_sql:
        return _result(
            ok=False,
            prompt=prompt,
            plan=plan,
            schema_context=schema_context,
            preferred=preferred,
            reason="sql_likely_required_api_chosen",
            evidence_source="local_sql_required",
            ignored_schema=ignored_schema,
            high_confidence_sql_required=True,
        )

    if preferred == "execute_sql" and not local_tables:
        return _result(
            ok=False,
            prompt=prompt,
            plan=plan,
            schema_context=schema_context,
            preferred=preferred,
            reason="sql_no_schema_grounding",
            evidence_source="unclear",
            ignored_schema=False,
        )

    if preferred == "both" and not str(plan.get("sql_reason") or "").strip() and not str(plan.get("api_reason") or "").strip():
        return _result(
            ok=False,
            prompt=prompt,
            plan=plan,
            schema_context=schema_context,
            preferred=preferred,
            reason="both_tools_missing_reason",
            evidence_source="mixed_sql_api",
            ignored_schema=ignored_schema,
        )

    evidence_source = _evidence_source(preferred, schema_grounded=schema_grounded, live_requested=live_requested)
    return _result(
        ok=True,
        prompt=prompt,
        plan=plan,
        schema_context=schema_context,
        preferred=preferred,
        reason=None,
        evidence_source=evidence_source,
        ignored_schema=ignored_schema,
        high_confidence_sql_required=bool(schema_grounded and local_tables and not live_requested),
    )


def infer_tool_choice_root_cause(
    prompt: str,
    plan: dict[str, Any],
    validation: dict[str, Any],
    schema_context: dict[str, Any],
) -> str:
    reason = validation.get("rejection_reason")
    if reason == "sql_likely_required_api_chosen":
        if _schema_grounded_prompt(prompt, schema_context):
            return "api_bias_for_live_terms"
        return "missed_local_table_affordance"
    if reason == "unresolved_api_path_param":
        return "endpoint_catalog_overselected"
    if reason == "sql_no_schema_grounding":
        return "schema_context_too_weak"
    if reason == "tool_required":
        return "prompt_intent_misread"
    if validation.get("ignored_schema_context"):
        return "missed_local_table_affordance"
    if plan.get("preferred_first_tool") == "execute_sql" and not validation.get("ok"):
        return "sql_plan_failed_after_correct_tool"
    return "no_clear_tool_choice_failure"


def _result(
    *,
    ok: bool,
    prompt: str,
    plan: dict[str, Any],
    schema_context: dict[str, Any],
    preferred: str,
    reason: str | None,
    evidence_source: str,
    ignored_schema: bool,
    high_confidence_sql_required: bool = False,
) -> dict[str, Any]:
    local_tables = _local_tables(schema_context)
    return redact_secrets(
        {
            "ok": ok,
            "rejection_reason": reason,
            "final_tool_choice": preferred,
            "evidence_source_that_should_have_been_considered": evidence_source,
            "high_confidence_sql_required": high_confidence_sql_required,
            "local_schema_has_relevant_tables": bool(_schema_grounded_prompt(prompt, schema_context) and local_tables),
            "top_relevant_sql_tables": local_tables[:5],
            "top_relevant_api_endpoints": [item.get("endpoint_id") for item in schema_context.get("endpoint_candidates", [])[:5]],
            "ignored_schema_context": ignored_schema,
            "endpoint_catalog_may_have_misled_model": preferred == "call_api" and bool(schema_context.get("endpoint_candidates")),
            "plan": plan,
        }
    )


def _preferred_tool(plan: dict[str, Any]) -> str:
    value = str(plan.get("preferred_first_tool") or "").strip().lower()
    if value in {"execute_sql", "sql"}:
        return "execute_sql"
    if value in {"call_api", "api"}:
        return "call_api"
    if value in {"both", "sql_api", "mixed_sql_api"}:
        return "both"
    if bool(plan.get("needs_local_sql")) and bool(plan.get("needs_live_api")):
        return "both"
    if bool(plan.get("needs_local_sql")):
        return "execute_sql"
    if bool(plan.get("needs_live_api")):
        return "call_api"
    return "none"


def _api_ids(plan: dict[str, Any]) -> list[str]:
    values = plan.get("api_endpoints_that_may_answer") or []
    if isinstance(values, str):
        values = [values]
    ids: list[str] = []
    for item in values:
        if isinstance(item, dict):
            text = item.get("endpoint_id") or item.get("id")
        else:
            text = item
        if text:
            ids.append(str(text))
    return ids


def _unresolved_endpoint(endpoint_ids: list[str], endpoint_catalog: EndpointCatalog) -> bool:
    for endpoint_id in endpoint_ids:
        endpoint = endpoint_catalog.by_id(endpoint_id)
        if endpoint and (endpoint.path_params or "{" in endpoint.path or "}" in endpoint.path):
            return True
    return False


def _local_tables(schema_context: dict[str, Any]) -> list[str]:
    tables = []
    for item in schema_context.get("top_tables", []):
        table = item.get("table") if isinstance(item, dict) else item
        if table:
            tables.append(str(table))
    return tables


def _data_question(prompt: str) -> bool:
    lowered = prompt.lower()
    return any(term in lowered for term in DATA_TERMS) or _schema_grounded_text(lowered)


def _explicit_live_api_request(prompt: str) -> bool:
    lowered = prompt.lower()
    return any(term in lowered for term in LIVE_API_TERMS) or bool(re.search(r"\bapi\b|\bendpoint\b", lowered))


def _schema_grounded_prompt(prompt: str, schema_context: dict[str, Any]) -> bool:
    return bool(_local_tables(schema_context) and _schema_grounded_text(prompt.lower()))


def _schema_grounded_text(lowered: str) -> bool:
    return any(re.search(rf"\b{re.escape(term)}\b", lowered) for term in SCHEMA_ENTITY_TERMS)


def _evidence_source(preferred: str, *, schema_grounded: bool, live_requested: bool) -> str:
    if preferred == "both":
        return "mixed_sql_api"
    if preferred == "execute_sql":
        return "local_sql_required" if schema_grounded else "local_sql_preferred"
    if preferred == "call_api":
        return "live_api_required" if live_requested else "api_verification_optional"
    return "unclear"
