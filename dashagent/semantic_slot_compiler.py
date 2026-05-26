from __future__ import annotations

from typing import Any

from .endpoint_catalog import EndpointCatalog
from .llm_sql_plan_compiler import compile_structured_sql_plan
from .nlp_generalization_layer import domain_to_table, timestamp_semantic_markers
from .schema_index import SchemaIndex, normalize_name
from .trajectory import redact_secrets
from .validators import APIValidator, SQLValidator
from .weak_model_slot_verifier import verify_semantic_slots


def compile_semantic_slots(
    slots: dict[str, Any],
    schema_index: SchemaIndex,
    endpoint_catalog: EndpointCatalog,
    sql_validator: SQLValidator,
    *,
    prompt: str | None = None,
) -> dict[str, Any]:
    prompt = prompt or _prompt_from_slots(slots)
    verification = verify_semantic_slots(prompt, slots)
    effective_slots = verification.get("corrected_slots") if isinstance(verification.get("corrected_slots"), dict) else slots
    warnings = list(verification.get("warnings") or [])
    errors: list[str] = []
    sql_candidates: list[dict[str, Any]] = []
    api_candidates: list[dict[str, Any]] = []
    if str(effective_slots.get("evidence_need") or "").lower() in {"sql_first", "sql_then_api"}:
        plan = _slots_to_plan(effective_slots, schema_index)
        compiled = compile_structured_sql_plan(plan, schema_index, {"business_term_aliases": {}})
        validation = sql_validator.validate(str(compiled.get("sql") or "")) if compiled.get("ok") else None
        if compiled.get("ok") and validation and validation.ok:
            sql_candidates.append(
                {
                    "sql": compiled["sql"],
                    "structured_sql_plan": plan,
                    "validation": validation.to_dict(),
                    "compiled": compiled,
                }
            )
        else:
            errors.extend(compiled.get("errors", []))
            if validation and not validation.ok:
                errors.extend(validation.errors)
    if str(effective_slots.get("evidence_need") or "").lower() in {"api_first", "api_only", "sql_then_api"}:
        api_candidates.extend(_api_candidates(effective_slots, endpoint_catalog))
    return redact_secrets(
        {
            "ok": bool(sql_candidates or api_candidates) and not (verification.get("errors") and not sql_candidates),
            "slots": effective_slots,
            "slot_verification": verification,
            "sql_candidates": sql_candidates,
            "api_candidates": api_candidates,
            "evidence_policy": effective_slots.get("evidence_need"),
            "compiler_warnings": warnings,
            "compiler_errors": sorted(set(errors)),
        }
    )


def _slots_to_plan(slots: dict[str, Any], schema_index: SchemaIndex) -> dict[str, Any]:
    domain = str(slots.get("domain") or "UNKNOWN").upper()
    table = domain_to_table(domain) or _first_table(schema_index)
    intent = str(slots.get("intent") or "DETAIL").upper()
    columns = _columns_for_intent(intent, table, schema_index, slots)
    aggregation = _aggregation(slots, table, schema_index)
    filters = _filters(slots, table, schema_index)
    return {
        "answer_intent": intent,
        "primary_table": table,
        "tables_needed": [table],
        "columns_needed": columns,
        "filters": filters,
        "aggregation": aggregation,
        "order_by": [],
        "limit": 50,
        "confidence": slots.get("confidence", 0.5),
    }


def _columns_for_intent(intent: str, table: str, schema_index: SchemaIndex, slots: dict[str, Any]) -> list[str]:
    if intent == "COUNT":
        return [_id_column(table, schema_index) or "*"]
    if intent == "DATE":
        ts = _timestamp_column(table, schema_index, slots)
        name = _role_column(table, schema_index, ("name", "title", "display"))
        return [col for col in [name, ts] if col]
    if intent == "STATUS":
        name = _role_column(table, schema_index, ("name", "title", "display"))
        status = _role_column(table, schema_index, ("status", "state"))
        return [col for col in [name, status] if col]
    if intent == "LIST":
        return [col for col in [_id_column(table, schema_index), _role_column(table, schema_index, ("name", "title", "display"))] if col]
    return schema_index.columns_for(table)[:5]


def _aggregation(slots: dict[str, Any], table: str, schema_index: SchemaIndex) -> dict[str, Any]:
    agg = str(slots.get("aggregation") or "none").lower()
    if str(slots.get("intent") or "").upper() == "COUNT" and agg == "none":
        agg = "count_distinct"
    column = _id_column(table, schema_index) if agg in {"count", "count_distinct"} else ""
    return {"type": agg, "table": table, "column": column or "*"}


def _filters(slots: dict[str, Any], table: str, schema_index: SchemaIndex) -> list[dict[str, Any]]:
    compiled = []
    for item in slots.get("filters") or []:
        if not isinstance(item, dict):
            continue
        semantic = str(item.get("semantic_field") or "").lower()
        column = _semantic_column(table, schema_index, semantic)
        if not column:
            continue
        operator = str(item.get("operator") or "equals").lower()
        if operator == "before":
            operator = "lte"
        elif operator == "after":
            operator = "gte"
        elif operator not in {"equals", "contains", "gte", "lte", "in"}:
            operator = "equals"
        compiled.append({"table": table, "column": column, "operator": operator, "value": item.get("value")})
    return compiled


def _api_candidates(slots: dict[str, Any], endpoint_catalog: EndpointCatalog) -> list[dict[str, Any]]:
    validator = APIValidator(endpoint_catalog)
    domain = str(slots.get("domain") or "").lower()
    candidates = []
    for endpoint in endpoint_catalog.endpoints:
        text = f"{endpoint.id} {endpoint.path} {endpoint.use_when} {' '.join(endpoint.domains)}".lower()
        if domain and domain != "unknown" and domain not in text:
            if not (domain == "segment" and "audience" in text):
                continue
        if "{" in endpoint.path or "}" in endpoint.path:
            continue
        validation = validator.validate(endpoint.method, endpoint.path, {}, {})
        if validation.ok:
            candidates.append({"endpoint_id": endpoint.id, "method": endpoint.method, "path": endpoint.path, "params": {}, "validation": validation.to_dict()})
    return candidates[:3]


def _semantic_column(table: str, schema_index: SchemaIndex, semantic: str) -> str | None:
    if semantic == "name":
        return _role_column(table, schema_index, ("name", "title", "display"))
    if semantic == "status":
        return _role_column(table, schema_index, ("status", "state"))
    if semantic == "id":
        return _id_column(table, schema_index)
    if semantic == "date":
        return _timestamp_column(table, schema_index, {})
    return _role_column(table, schema_index, (semantic,))


def _timestamp_column(table: str, schema_index: SchemaIndex, slots: dict[str, Any]) -> str | None:
    kind = ((slots.get("nlp_context") or {}).get("timestamp_semantics") if isinstance(slots.get("nlp_context"), dict) else None)
    markers = timestamp_semantic_markers(kind)
    for column in schema_index.columns_for(table):
        normalized = normalize_name(column)
        if any(marker in normalized for marker in markers):
            return column
    return _role_column(table, schema_index, ("time", "date", "created", "updated", "deployed", "published"))


def _role_column(table: str, schema_index: SchemaIndex, markers: tuple[str, ...]) -> str | None:
    for column in schema_index.columns_for(table):
        normalized = normalize_name(column)
        if any(marker in normalized for marker in markers):
            return column
    return None


def _id_column(table: str, schema_index: SchemaIndex) -> str | None:
    for column in schema_index.columns_for(table):
        normalized = normalize_name(column)
        if normalized == "id" or normalized.endswith("id"):
            return column
    return None


def _first_table(schema_index: SchemaIndex) -> str:
    return next(iter(schema_index.tables), "")


def _prompt_from_slots(slots: dict[str, Any]) -> str:
    values = slots.get("quoted_entities") if isinstance(slots.get("quoted_entities"), list) else []
    return " ".join([str(slots.get("intent") or ""), str(slots.get("domain") or ""), " ".join(str(v) for v in values)])
