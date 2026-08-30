from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import Any

from .trajectory import redact_secrets
from .weak_model_semantic_slots import VALID_AGGREGATIONS, VALID_DOMAINS, VALID_EVIDENCE_NEEDS, VALID_INTENTS


@dataclass(frozen=True)
class SchemaValidationResult:
    ok: bool
    value: dict[str, Any]
    errors: list[str]
    repair_instructions: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SemanticSlots:
    intent: str
    domain: str
    entity_terms: list[str]
    quoted_entities: list[str]
    filters: list[dict[str, Any]]
    aggregation: str
    relationship: dict[str, Any]
    evidence_need: str
    confidence: float


@dataclass(frozen=True)
class EvidenceNeedPlan:
    evidence_need: str
    sql_reason: str
    api_reason: str
    preferred_first_tool: str
    confidence: float


@dataclass(frozen=True)
class SQLPlanCandidate:
    candidate_id: str
    answer_intent: str
    primary_table: str
    tables_needed: list[str]
    columns_needed: list[str]
    filters: list[dict[str, Any]]
    aggregation: dict[str, Any]
    order_by: list[dict[str, Any]]
    limit: int
    reason: str
    confidence: float


@dataclass(frozen=True)
class SQLRepairRequest:
    failed_tests: list[str]
    repair_hints: list[str]
    allowed_tables: list[str]
    allowed_columns: dict[str, list[str]]


@dataclass(frozen=True)
class APIPlanCandidate:
    endpoint_id: str
    method: str
    params: dict[str, Any]
    reason: str


@dataclass(frozen=True)
class ClaimSupportRecord:
    claim: str
    evidence_source: str
    evidence_field: str


@dataclass(frozen=True)
class EvidenceGroundedAnswer:
    answer: str
    claims: list[ClaimSupportRecord]
    uncertainties: list[str]


SCHEMAS: dict[str, dict[str, Any]] = {
    "SemanticSlots": {
        "required": ["intent", "domain", "entity_terms", "quoted_entities", "filters", "aggregation", "relationship", "evidence_need", "confidence"],
        "enums": {"intent": VALID_INTENTS, "domain": VALID_DOMAINS, "aggregation": VALID_AGGREGATIONS, "evidence_need": VALID_EVIDENCE_NEEDS},
        "lists": {"entity_terms", "quoted_entities", "filters"},
        "dicts": {"relationship"},
    },
    "EvidenceNeedPlan": {
        "required": ["evidence_need", "sql_reason", "api_reason", "preferred_first_tool", "confidence"],
        "enums": {"evidence_need": VALID_EVIDENCE_NEEDS, "preferred_first_tool": {"execute_sql", "call_api", "none"}},
    },
    "SQLPlanCandidate": {
        "required": ["candidate_id", "answer_intent", "primary_table", "tables_needed", "columns_needed", "filters", "aggregation", "order_by", "limit", "reason", "confidence"],
        "enums": {"answer_intent": VALID_INTENTS},
        "lists": {"tables_needed", "columns_needed", "filters", "order_by"},
        "dicts": {"aggregation"},
    },
    "SQLRepairRequest": {
        "required": ["failed_tests", "repair_hints", "allowed_tables", "allowed_columns"],
        "lists": {"failed_tests", "repair_hints", "allowed_tables"},
        "dicts": {"allowed_columns"},
    },
    "APIPlanCandidate": {
        "required": ["endpoint_id", "method", "params", "reason"],
        "enums": {"method": {"GET"}},
        "dicts": {"params"},
    },
    "EvidenceGroundedAnswer": {
        "required": ["answer", "claims", "uncertainties"],
        "lists": {"claims", "uncertainties"},
    },
    "ClaimSupportRecord": {
        "required": ["claim", "evidence_source", "evidence_field"],
        "enums": {"evidence_source": {"sql", "api", "none"}},
    },
}


def parse_json_strict(text: str) -> dict[str, Any]:
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("Expected a JSON object.")
    return redact_secrets(parsed)


def recover_json_once(text: str) -> dict[str, Any]:
    try:
        return parse_json_strict(text)
    except Exception:
        pass
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        return parse_json_strict(fenced.group(1))
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return parse_json_strict(text[start : end + 1])
    raise ValueError("Could not recover a JSON object.")


def validate_schema(schema_name: str, payload: dict[str, Any]) -> SchemaValidationResult:
    schema = SCHEMAS.get(schema_name)
    if schema is None:
        return SchemaValidationResult(False, {}, [f"Unknown schema: {schema_name}"], [f"Use one of: {', '.join(sorted(SCHEMAS))}."])
    value = dict(payload) if isinstance(payload, dict) else {}
    errors: list[str] = []
    for field in schema.get("required", []):
        if field not in value:
            errors.append(f"Missing required field: {field}")
    for field, allowed in schema.get("enums", {}).items():
        if field in value and str(value[field]) not in {str(item) for item in allowed}:
            errors.append(f"Invalid enum for {field}: {value[field]}")
    for field in schema.get("lists", set()):
        if field in value and not isinstance(value[field], list):
            errors.append(f"Field {field} must be a list.")
    for field in schema.get("dicts", set()):
        if field in value and not isinstance(value[field], dict):
            errors.append(f"Field {field} must be an object.")
    if "confidence" in value:
        try:
            value["confidence"] = max(0.0, min(1.0, float(value["confidence"])))
        except Exception:
            errors.append("Field confidence must be numeric.")
    instructions = [f"Return corrected {schema_name} JSON only.", *errors]
    return SchemaValidationResult(not errors, redact_secrets(value), errors, instructions if errors else [])


def structured_retry_prompt(schema_name: str, errors: list[str]) -> str:
    schema = SCHEMAS.get(schema_name, {})
    required = ", ".join(schema.get("required", []))
    return (
        f"Return corrected {schema_name} JSON only. Required fields: {required}. "
        f"Fix these validation errors: {'; '.join(errors)}."
    )
