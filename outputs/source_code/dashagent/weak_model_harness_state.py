from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class HarnessStateName(str, Enum):
    INPUT = "INPUT"
    NORMALIZED_PROMPT = "NORMALIZED_PROMPT"
    SEMANTIC_SLOTS = "SEMANTIC_SLOTS"
    SLOT_VALIDATED = "SLOT_VALIDATED"
    SCHEMA_CONTEXT_RETRIEVED = "SCHEMA_CONTEXT_RETRIEVED"
    SQL_CANDIDATES = "SQL_CANDIDATES"
    SQL_UNIT_TESTED = "SQL_UNIT_TESTED"
    SQL_VALIDATED = "SQL_VALIDATED"
    SQL_EXECUTED = "SQL_EXECUTED"
    API_CANDIDATES = "API_CANDIDATES"
    API_VALIDATED = "API_VALIDATED"
    API_EXECUTED = "API_EXECUTED"
    EVIDENCE_BUILT = "EVIDENCE_BUILT"
    ANSWER_DRAFTED = "ANSWER_DRAFTED"
    CLAIMS_VERIFIED = "CLAIMS_VERIFIED"
    FINAL_ANSWER = "FINAL_ANSWER"


@dataclass(frozen=True)
class HarnessStateSpec:
    name: HarnessStateName
    input_fields: list[str]
    output_fields: list[str]
    validation_assertions: list[str]
    failure_category: str
    retry_policy: str
    trace_event: str

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["name"] = self.name.value
        return data


def build_default_harness_state_machine() -> list[HarnessStateSpec]:
    return [
        HarnessStateSpec(HarnessStateName.INPUT, ["prompt"], ["prompt"], ["prompt_present"], "input_missing", "none", "weak_harness.input"),
        HarnessStateSpec(HarnessStateName.NORMALIZED_PROMPT, ["prompt"], ["nlp_context"], ["normalized_prompt_present"], "normalization_failed", "none", "weak_harness.normalized_prompt"),
        HarnessStateSpec(HarnessStateName.SEMANTIC_SLOTS, ["prompt", "nlp_context"], ["semantic_slots"], ["semantic_slots_schema_valid"], "slot_extraction_failed", "retry_once", "weak_harness.semantic_slots"),
        HarnessStateSpec(HarnessStateName.SLOT_VALIDATED, ["semantic_slots"], ["validated_slots"], ["intent_domain_consistent", "evidence_need_compatible"], "slot_validation_failed", "retry_once", "weak_harness.slot_validated"),
        HarnessStateSpec(HarnessStateName.SCHEMA_CONTEXT_RETRIEVED, ["validated_slots", "schema_index"], ["schema_context"], ["schema_context_compact", "known_tables_only"], "schema_retrieval_failed", "none", "weak_harness.schema_context"),
        HarnessStateSpec(HarnessStateName.SQL_CANDIDATES, ["validated_slots", "schema_context"], ["sql_candidates"], ["candidate_has_plan_or_reason"], "sql_candidate_failed", "repair_once", "weak_harness.sql_candidates"),
        HarnessStateSpec(HarnessStateName.SQL_UNIT_TESTED, ["sql_candidates", "schema_context"], ["unit_test_results"], ["critical_sql_unit_tests_pass"], "sql_unit_test_failed", "repair_once", "weak_harness.sql_unit_tested"),
        HarnessStateSpec(HarnessStateName.SQL_VALIDATED, ["sql_candidates", "unit_test_results"], ["validated_sql"], ["sql_validator_passed", "sqlglot_parse_passed"], "sql_validation_failed", "repair_once", "weak_harness.sql_validated"),
        HarnessStateSpec(HarnessStateName.SQL_EXECUTED, ["validated_sql"], ["sql_result"], ["sql_execution_ok_or_safe_empty"], "sql_execution_failed", "none", "weak_harness.sql_executed"),
        HarnessStateSpec(HarnessStateName.API_CANDIDATES, ["validated_slots", "endpoint_catalog"], ["api_candidates"], ["candidate_endpoint_known_or_reason"], "api_candidate_failed", "retry_once", "weak_harness.api_candidates"),
        HarnessStateSpec(HarnessStateName.API_VALIDATED, ["api_candidates"], ["validated_api_call"], ["endpoint_catalog_validation_passed"], "api_validation_failed", "retry_once", "weak_harness.api_validated"),
        HarnessStateSpec(HarnessStateName.API_EXECUTED, ["validated_api_call"], ["api_result"], ["api_outcome_not_payload_if_error"], "api_execution_failed", "none", "weak_harness.api_executed"),
        HarnessStateSpec(HarnessStateName.EVIDENCE_BUILT, ["sql_result", "api_result"], ["evidence_bus"], ["evidence_state_distinct"], "evidence_build_failed", "none", "weak_harness.evidence_built"),
        HarnessStateSpec(HarnessStateName.ANSWER_DRAFTED, ["evidence_bus", "validated_slots"], ["draft_answer"], ["draft_uses_required_evidence"], "answer_grounding_failed", "fallback_once", "weak_harness.answer_drafted"),
        HarnessStateSpec(HarnessStateName.CLAIMS_VERIFIED, ["draft_answer", "evidence_bus"], ["claim_records"], ["unsupported_claims_zero"], "claim_verification_failed", "fallback_once", "weak_harness.claims_verified"),
        HarnessStateSpec(HarnessStateName.FINAL_ANSWER, ["draft_answer", "claim_records"], ["final_answer"], ["final_answer_supported"], "final_answer_failed", "none", "weak_harness.final_answer"),
    ]


def state_machine_as_dicts() -> list[dict[str, Any]]:
    return [state.to_dict() for state in build_default_harness_state_machine()]
