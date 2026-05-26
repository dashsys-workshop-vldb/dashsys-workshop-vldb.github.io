from __future__ import annotations

from typing import Any

from .endpoint_catalog import EndpointCatalog
from .llm_sql_plan_compiler import compile_structured_sql_plan
from .nlp_generalization_layer import domain_to_table, timestamp_semantic_markers
from .schema_index import SchemaIndex, normalize_name
from .trajectory import redact_secrets
from .validators import APIValidator, SQLValidator
from .weak_model_api_selector import select_weak_model_api_candidates
from .weak_model_slot_verifier import verify_semantic_slots
from .weak_sql_schema_retriever import retrieve_weak_sql_schema_context
from .weak_sql_skeleton_retriever import retrieve_sql_skeletons
from .weak_sql_unit_tester import run_sql_semantic_unit_tests


def compile_semantic_slots(
    slots: dict[str, Any],
    schema_index: SchemaIndex,
    endpoint_catalog: EndpointCatalog,
    sql_validator: SQLValidator,
    *,
    prompt: str | None = None,
    enhanced_sql: bool = False,
    repair_rounds: int = 0,
) -> dict[str, Any]:
    prompt = prompt or _prompt_from_slots(slots)
    verification = verify_semantic_slots(prompt, slots)
    effective_slots = verification.get("corrected_slots") if isinstance(verification.get("corrected_slots"), dict) else slots
    warnings = list(verification.get("warnings") or [])
    errors: list[str] = []
    sql_candidates: list[dict[str, Any]] = []
    api_candidates: list[dict[str, Any]] = []
    schema_context: dict[str, Any] | None = None
    sql_skeletons: list[dict[str, Any]] = []
    evidence_need = str(effective_slots.get("evidence_need") or "").lower()
    if evidence_need in {"sql_first", "sql_then_api", "sql_only", "api_then_sql", "sql_primary_api_verify", "api_primary_sql_context"}:
        if enhanced_sql:
            schema_context = retrieve_weak_sql_schema_context(prompt, schema_index, effective_slots)
            sql_skeletons = retrieve_sql_skeletons(effective_slots)
            plan = _enhanced_slots_to_plan(effective_slots, schema_index, schema_context)
        else:
            plan = _slots_to_plan(effective_slots, schema_index)
        candidate = _compile_candidate(
            plan,
            effective_slots,
            schema_index,
            sql_validator,
            prompt=prompt,
            schema_context=schema_context,
            sql_skeletons=sql_skeletons,
            enhanced_sql=enhanced_sql,
        )
        if candidate.get("ok"):
            sql_candidates.append(candidate["candidate"])
        else:
            errors.extend(candidate.get("errors") or [])
            repaired = None
            if enhanced_sql and repair_rounds > 0:
                repaired_plan = _repair_plan_from_feedback(plan, effective_slots, schema_index, schema_context or {}, candidate.get("unit_tests") or {})
                repaired = _compile_candidate(
                    repaired_plan,
                    effective_slots,
                    schema_index,
                    sql_validator,
                    prompt=prompt,
                    schema_context=schema_context,
                    sql_skeletons=sql_skeletons,
                    enhanced_sql=True,
                    repair_attempts=1,
                )
            if repaired and repaired.get("ok"):
                sql_candidates.append(repaired["candidate"])
                warnings.append("enhanced_sql_repair_success")
            elif repaired:
                errors.extend(repaired.get("errors") or [])
    if evidence_need in {"api_first", "api_only", "sql_then_api", "api_then_sql", "sql_primary_api_verify", "api_primary_sql_context"}:
        api_candidates.extend(_api_candidates(effective_slots, endpoint_catalog, prompt=prompt))
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
            "enhanced_sql": enhanced_sql,
            "schema_context": schema_context,
            "sql_skeletons": sql_skeletons,
        }
    )


def _compile_candidate(
    plan: dict[str, Any],
    slots: dict[str, Any],
    schema_index: SchemaIndex,
    sql_validator: SQLValidator,
    *,
    prompt: str,
    schema_context: dict[str, Any] | None,
    sql_skeletons: list[dict[str, Any]],
    enhanced_sql: bool,
    repair_attempts: int = 0,
) -> dict[str, Any]:
    compile_context = {"business_term_aliases": {}}
    if enhanced_sql:
        primary = str(plan.get("primary_table") or "")
        compile_context["allowed_primary_tables"] = [primary]
    compiled = compile_structured_sql_plan(plan, schema_index, compile_context)
    validation = sql_validator.validate(str(compiled.get("sql") or "")) if compiled.get("ok") else None
    unit_tests = (
        run_sql_semantic_unit_tests(prompt, slots, plan, str(compiled.get("sql") or ""), schema_context or {})
        if enhanced_sql
        else {"passed": True, "failed_tests": [], "repair_hints": [], "semantic_score": 1.0}
    )
    errors = list(compiled.get("errors") or [])
    if validation and not validation.ok:
        errors.extend(validation.errors)
    if enhanced_sql and not unit_tests.get("passed"):
        errors.extend(str(item) for item in unit_tests.get("repair_hints") or [])
    if compiled.get("ok") and validation and validation.ok and (not enhanced_sql or unit_tests.get("passed")):
        return {
            "ok": True,
            "candidate": {
                "sql": compiled["sql"],
                "structured_sql_plan": plan,
                "validation": validation.to_dict(),
                "compiled": compiled,
                "sql_unit_tests": unit_tests,
                "sql_skeletons": sql_skeletons,
                "repair_attempts": repair_attempts,
                "repair_success": bool(repair_attempts),
            },
            "unit_tests": unit_tests,
            "errors": [],
        }
    return {"ok": False, "errors": errors, "unit_tests": unit_tests}


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


def _enhanced_slots_to_plan(slots: dict[str, Any], schema_index: SchemaIndex, schema_context: dict[str, Any]) -> dict[str, Any]:
    domain = str(slots.get("domain") or "UNKNOWN").upper()
    retrieved_tables = [table for table in schema_context.get("retrieved_tables") or [] if schema_index.table_exists(str(table))]
    table = (domain_to_table(domain) if domain_to_table(domain) in retrieved_tables else None) or (retrieved_tables[0] if retrieved_tables else domain_to_table(domain)) or _first_table(schema_index)
    intent = str(slots.get("intent") or "DETAIL").upper()
    tables_needed = _tables_needed_for_enhanced_plan(intent, table, slots, schema_context, schema_index)
    columns = _enhanced_columns_for_intent(intent, table, schema_index, slots, schema_context)
    aggregation = _enhanced_aggregation(slots, table, schema_context, schema_index)
    filters = _enhanced_filters(slots, table, schema_index, schema_context, tables_needed=tables_needed)
    order_by = _enhanced_order_by(intent, table, schema_context, slots)
    return {
        "answer_intent": intent,
        "primary_table": table,
        "tables_needed": tables_needed,
        "columns_needed": columns,
        "filters": filters,
        "aggregation": aggregation,
        "order_by": order_by,
        "limit": 50,
        "confidence": slots.get("confidence", 0.5),
    }


def _tables_needed_for_enhanced_plan(intent: str, table: str, slots: dict[str, Any], schema_context: dict[str, Any], schema_index: SchemaIndex) -> list[str]:
    tables = [table]
    if intent != "RELATIONSHIP":
        return tables
    nlp = slots.get("nlp_context") if isinstance(slots.get("nlp_context"), dict) else {}
    prompt_lower = str(nlp.get("original_prompt") or "").lower()
    lowered_entities = " ".join(str(item).lower() for item in slots.get("entity_terms") or []) + " " + prompt_lower
    join_candidates = schema_context.get("join_candidates") if isinstance(schema_context.get("join_candidates"), list) else []
    if table == "dim_segment" and ("destination" in lowered_entities or "target" in lowered_entities):
        for needed in ("hkg_br_segment_target", "dim_target"):
            if schema_index.table_exists(needed):
                tables.append(needed)
    elif table == "dim_campaign" and ("segment" in lowered_entities or "audience" in lowered_entities):
        for needed in ("br_campaign_segment", "dim_segment"):
            if schema_index.table_exists(needed):
                tables.append(needed)
    elif table == "dim_collection" and ("schema" in lowered_entities or "blueprint" in lowered_entities):
        for needed in ("dim_blueprint",):
            if schema_index.table_exists(needed):
                tables.append(needed)
    elif join_candidates:
        first = join_candidates[0]
        for needed in (first.get("left_table"), first.get("right_table")):
            if needed and schema_index.table_exists(str(needed)) and needed not in tables:
                tables.append(str(needed))
    return tables


def _enhanced_columns_for_intent(intent: str, table: str, schema_index: SchemaIndex, slots: dict[str, Any], schema_context: dict[str, Any]) -> list[str]:
    roles = ((schema_context.get("column_roles") or {}).get(table) or {}) if isinstance(schema_context.get("column_roles"), dict) else {}
    if intent == "COUNT":
        return [_first_role(roles, "id") or _id_column(table, schema_index) or "*"]
    if intent == "DATE":
        ts = _timestamp_from_context(table, schema_context, slots) or _timestamp_column(table, schema_index, slots)
        name = _first_role(roles, "name") or _role_column(table, schema_index, ("name", "title", "display"))
        return [col for col in [name, ts] if col]
    if intent == "STATUS":
        name = _first_role(roles, "name") or _role_column(table, schema_index, ("name", "title", "display"))
        status = _first_role(roles, "status") or _role_column(table, schema_index, ("status", "state"))
        return [col for col in [name, status] if col]
    if intent == "LIST":
        return [col for col in [_first_role(roles, "id") or _id_column(table, schema_index), _first_role(roles, "name") or _role_column(table, schema_index, ("name", "title", "display"))] if col]
    if intent == "RELATIONSHIP":
        return [col for col in [_first_role(roles, "id") or _id_column(table, schema_index), _first_role(roles, "name") or _role_column(table, schema_index, ("name", "title", "display"))] if col]
    return _compact_non_metadata_columns(table, schema_index)[:5]


def _enhanced_aggregation(slots: dict[str, Any], table: str, schema_context: dict[str, Any], schema_index: SchemaIndex) -> dict[str, Any]:
    intent = str(slots.get("intent") or "").upper()
    if intent == "COUNT":
        candidates = schema_context.get("aggregation_candidates") if isinstance(schema_context.get("aggregation_candidates"), list) else []
        for item in candidates:
            if item.get("table") == table:
                return dict(item)
        column = _first_role(((schema_context.get("column_roles") or {}).get(table) or {}), "id") or _id_column(table, schema_index) or "*"
        return {"type": "count_distinct" if column != "*" else "count", "table": table, "column": column}
    return {"type": "none", "table": table, "column": "*"}


def _enhanced_filters(slots: dict[str, Any], table: str, schema_index: SchemaIndex, schema_context: dict[str, Any], *, tables_needed: list[str] | None = None) -> list[dict[str, Any]]:
    nlp = slots.get("nlp_context") if isinstance(slots.get("nlp_context"), dict) else {}
    intent = str(slots.get("intent") or "").upper()
    prompt_lower = str(nlp.get("original_prompt") or "").lower()
    tables_needed = tables_needed or [table]
    date_terms = {str(item).lower() for item in nlp.get("date_terms") or []}
    compiled = []
    for item in slots.get("filters") or []:
        if not isinstance(item, dict):
            continue
        semantic = str(item.get("semantic_field") or "").lower()
        value = item.get("value")
        if intent == "DATE" and semantic == "status" and str(value).lower() in date_terms:
            continue
        filter_table = _filter_table_for_value(table, tables_needed, prompt_lower, semantic, str(value or ""))
        column = _enhanced_semantic_column(filter_table, schema_index, semantic, schema_context, slots)
        if not column:
            continue
        operator = str(item.get("operator") or "equals").lower()
        if operator == "before":
            operator = "lte"
        elif operator == "after":
            operator = "gte"
        elif operator not in {"equals", "contains", "gte", "lte", "in"}:
            operator = "equals"
        compiled.append({"table": filter_table, "column": column, "operator": operator, "value": value})
    return compiled


def _enhanced_order_by(intent: str, table: str, schema_context: dict[str, Any], slots: dict[str, Any]) -> list[dict[str, Any]]:
    nlp = slots.get("nlp_context") if isinstance(slots.get("nlp_context"), dict) else {}
    if intent == "DATE" and "recent" in {str(item).lower() for item in nlp.get("date_terms") or []}:
        column = _timestamp_from_context(table, schema_context, slots)
        if column:
            return [{"table": table, "column": column, "direction": "desc"}]
    return []


def _repair_plan_from_feedback(plan: dict[str, Any], slots: dict[str, Any], schema_index: SchemaIndex, schema_context: dict[str, Any], unit_tests: dict[str, Any]) -> dict[str, Any]:
    repaired = {**plan}
    failed = set(unit_tests.get("failed_tests") or [])
    if "table_test" in failed:
        domain_table = domain_to_table(str(slots.get("domain") or ""))
        if domain_table and schema_index.table_exists(domain_table):
            repaired["primary_table"] = domain_table
            repaired["tables_needed"] = [domain_table]
    primary = str(repaired.get("primary_table") or "")
    if "timestamp_test" in failed or "column_role_test" in failed or "intent_test" in failed:
        repaired["columns_needed"] = _enhanced_columns_for_intent(str(slots.get("intent") or "DETAIL").upper(), primary, schema_index, slots, schema_context)
        repaired["aggregation"] = _enhanced_aggregation(slots, primary, schema_context, schema_index)
    if "filter_test" in failed or "overbroad_test" in failed:
        repaired["filters"] = _enhanced_filters(slots, primary, schema_index, schema_context, tables_needed=repaired.get("tables_needed") or [primary])
    return repaired


def _filter_table_for_value(primary_table: str, tables_needed: list[str], prompt_lower: str, semantic: str, value: str) -> str:
    if semantic != "name":
        return primary_table
    if "dim_target" in tables_needed and ("destination" in prompt_lower or "target" in prompt_lower):
        return "dim_target"
    if "dim_blueprint" in tables_needed and ("schema" in prompt_lower or "blueprint" in prompt_lower):
        return "dim_blueprint"
    return primary_table


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


def _api_candidates(slots: dict[str, Any], endpoint_catalog: EndpointCatalog, *, prompt: str | None = None) -> list[dict[str, Any]]:
    selected = select_weak_model_api_candidates(slots, endpoint_catalog, prompt=prompt)
    return list(selected.get("candidates") or [])[:3]


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


def _enhanced_semantic_column(table: str, schema_index: SchemaIndex, semantic: str, schema_context: dict[str, Any], slots: dict[str, Any]) -> str | None:
    roles = ((schema_context.get("column_roles") or {}).get(table) or {}) if isinstance(schema_context.get("column_roles"), dict) else {}
    if semantic == "name":
        return _first_role(roles, "name") or _semantic_column(table, schema_index, semantic)
    if semantic == "status":
        return _first_role(roles, "status") or _semantic_column(table, schema_index, semantic)
    if semantic == "id":
        return _first_role(roles, "id") or _semantic_column(table, schema_index, semantic)
    if semantic == "date":
        return _timestamp_from_context(table, schema_context, slots) or _semantic_column(table, schema_index, semantic)
    return _semantic_column(table, schema_index, semantic)


def _timestamp_from_context(table: str, schema_context: dict[str, Any], slots: dict[str, Any]) -> str | None:
    nlp = slots.get("nlp_context") if isinstance(slots.get("nlp_context"), dict) else {}
    kind = str(nlp.get("timestamp_semantics") or "requested")
    candidates_by_table = schema_context.get("timestamp_candidates") if isinstance(schema_context.get("timestamp_candidates"), dict) else {}
    candidates = (candidates_by_table.get(table) or {}) if isinstance(candidates_by_table.get(table), dict) else {}
    for key in (kind, "requested", "published", "updated", "created"):
        values = candidates.get(key) if isinstance(candidates.get(key), list) else []
        if values:
            return str(values[0])
    roles = ((schema_context.get("column_roles") or {}).get(table) or {}) if isinstance(schema_context.get("column_roles"), dict) else {}
    return _first_role(roles, "timestamp")


def _first_role(roles: dict[str, Any], role: str) -> str | None:
    values = roles.get(role) if isinstance(roles.get(role), list) else []
    return str(values[0]) if values else None


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
        if _metadata_column(normalized):
            continue
        if any(marker in normalized for marker in markers):
            return column
    return None


def _id_column(table: str, schema_index: SchemaIndex) -> str | None:
    for column in schema_index.columns_for(table):
        normalized = normalize_name(column)
        if _metadata_column(normalized):
            continue
        if normalized == "id" or normalized.endswith("id"):
            return column
    return None


def _compact_non_metadata_columns(table: str, schema_index: SchemaIndex) -> list[str]:
    return [column for column in schema_index.columns_for(table) if not _metadata_column(normalize_name(column))]


def _metadata_column(normalized: str) -> bool:
    return any(marker in normalized for marker in ("sandbox", "imsorg", "orgid", "acpsystemmetadata"))


def _first_table(schema_index: SchemaIndex) -> str:
    return next(iter(schema_index.tables), "")


def _prompt_from_slots(slots: dict[str, Any]) -> str:
    values = slots.get("quoted_entities") if isinstance(slots.get("quoted_entities"), list) else []
    return " ".join([str(slots.get("intent") or ""), str(slots.get("domain") or ""), " ".join(str(v) for v in values)])
