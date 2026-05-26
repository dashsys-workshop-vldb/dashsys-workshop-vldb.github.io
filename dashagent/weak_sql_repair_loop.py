from __future__ import annotations

from typing import Any

from .endpoint_catalog import EndpointCatalog
from .nlp_generalization_layer import normalize_prompt_semantics
from .schema_index import SchemaIndex
from .semantic_slot_compiler import compile_semantic_slots
from .trajectory import redact_secrets
from .validators import SQLValidator


def repair_slots_from_unit_feedback(slots: dict[str, Any], repair_hints: list[str], prompt: str) -> dict[str, Any]:
    repaired = dict(slots)
    hint_text = " ".join(str(item).lower() for item in repair_hints)
    nlp = repaired.get("nlp_context") if isinstance(repaired.get("nlp_context"), dict) else normalize_prompt_semantics(prompt)
    if "count" in hint_text and str(repaired.get("intent") or "").upper() == "COUNT":
        repaired["aggregation"] = "count_distinct"
    if "status" in hint_text and nlp.get("status_terms"):
        repaired.setdefault("filters", [])
        _append_filter_once(repaired["filters"], "status", "equals", str((nlp.get("status_terms") or [""])[0]))
    if "name" in hint_text or "quoted" in hint_text or "filter" in hint_text:
        for entity in nlp.get("quoted_entities") or []:
            repaired.setdefault("filters", [])
            _append_filter_once(repaired["filters"], "name", "equals", str(entity))
    repaired["nlp_context"] = nlp
    return redact_secrets(repaired)


def run_weak_sql_repair_loop(
    prompt: str,
    slots: dict[str, Any],
    schema_index: SchemaIndex,
    endpoint_catalog: EndpointCatalog,
    sql_validator: SQLValidator,
    *,
    max_repair_rounds: int = 1,
) -> dict[str, Any]:
    attempts = 0
    current = dict(slots)
    last_compile: dict[str, Any] = {}
    while attempts <= max_repair_rounds:
        compiled = compile_semantic_slots(
            current,
            schema_index,
            endpoint_catalog,
            sql_validator,
            prompt=prompt,
            enhanced_sql=True,
            repair_rounds=0,
        )
        last_compile = compiled
        if compiled.get("sql_candidates"):
            return redact_secrets({"final_state": "sql_candidate_ready", "repair_attempts": attempts, "slots": current, "compiled": compiled})
        if attempts >= max_repair_rounds:
            break
        hints = list(compiled.get("compiler_errors") or [])
        if not hints:
            hints = ["Use known tables and columns and match the prompt intent."]
        current = repair_slots_from_unit_feedback(current, hints, prompt)
        attempts += 1
    return redact_secrets({"final_state": "safe_no_sql", "repair_attempts": attempts, "slots": current, "compiled": last_compile})


def _append_filter_once(filters: list[dict[str, Any]], semantic_field: str, operator: str, value: str) -> None:
    if not value:
        return
    wanted = {"semantic_field": semantic_field, "operator": operator, "value": value}
    if not any(item.get("semantic_field") == semantic_field and str(item.get("value")) == value for item in filters if isinstance(item, dict)):
        filters.append(wanted)
