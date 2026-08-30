from __future__ import annotations

import json

from dashagent.no_tool_safety_verifier import verify_no_tool_safety
from dashagent.checkpoints import CheckpointLogger
from dashagent.config import Config
from dashagent.executor import AgentExecutor
from dashagent.prompt_semantic_ir import extract_objective_prompt_features
from dashagent.routing_anti_hallucination_gate import (
    build_routing_gate_feedback,
    run_routing_gate_with_revision,
    validate_routing_decision_support,
)
from dashagent.semantic_intent_classifier import classify_semantic_intent, parse_semantic_intent_decision
from dashagent.semantic_intent_context_builder import build_semantic_intent_context, estimate_context_tokens
from dashagent.semantic_route_codebook import (
    estimate_compact_payload_savings,
    render_codebook_report,
    runtime_payload_is_compact,
)
from dashagent.semantic_route_decision_ladder import (
    ALLOWED_SEMANTIC_ROUTE_ACTIONS,
    run_semantic_route_decision_ladder,
    validate_llm_safe_direct_answer,
)


FORBIDDEN_ROUTE_FIELDS = {
    "final_route",
    "should_use_sql",
    "should_use_api",
    "should_skip_tools",
    "true_user_intent",
    "subjective_risk",
    "reason",
    "explanation",
    "route_confidence",
}


class FakeSemanticIntentClient:
    def __init__(self, *responses: str) -> None:
        self.responses = list(responses)
        self.calls = 0

    def complete(self, messages: list[dict[str, str]]) -> str:
        self.calls += 1
        return self.responses.pop(0)


def test_objective_prompt_features_for_conceptual_schema_have_no_route() -> None:
    features = extract_objective_prompt_features("What is a schema?")
    payload = features.to_dict()

    assert payload["cue"] == ["DEF"]
    assert "SCHEMA" in payload["domain"]
    assert "DOMAIN_WITH_DEF_CUE" in payload["flags"]
    assert not (FORBIDDEN_ROUTE_FIELDS & payload.keys())


def test_objective_prompt_features_for_list_schema_have_retrieval_no_route() -> None:
    features = extract_objective_prompt_features("List schemas")
    payload = features.to_dict()

    assert payload["retr"] == ["LIST"]
    assert "SCHEMA" in payload["domain"]
    assert not (FORBIDDEN_ROUTE_FIELDS & payload.keys())


def test_objective_prompt_features_record_mixed_concept_and_retrieval() -> None:
    features = extract_objective_prompt_features("Explain merge policy and list current merge policies")
    payload = features.to_dict()

    assert "EXPLAIN" in payload["cue"]
    assert "LIST" in payload["retr"]
    assert "MERGE_POLICY" in payload["domain"]
    assert "MIXED_CONCEPT_AND_RETRIEVAL" in payload["flags"]
    assert not (FORBIDDEN_ROUTE_FIELDS & payload.keys())


def test_compact_context_respects_budget_and_top_k() -> None:
    features = extract_objective_prompt_features("Explain merge policy and list current merge policies")
    context = build_semantic_intent_context(features, tier=1, token_budget=140, top_k_capability_families=2)

    assert estimate_context_tokens(context) <= 140
    assert len(context["capabilities"]) <= 2
    assert set(context) <= {"task", "prompt", "features", "capabilities", "allowed_outputs", "constraints", "examples"}
    assert context["task"] == "SEMANTIC_INTENT_DECISION"
    assert context["constraints"]["do_not_generate_sql"] is True
    serialized = json.dumps(context).lower()
    assert "sample_rows" not in serialized
    assert "endpoint_catalog" not in serialized
    assert "full_schema" not in serialized
    assert "reason" not in serialized
    assert "explanation" not in serialized


def test_semantic_intent_classifier_accepts_valid_json() -> None:
    decision = parse_semantic_intent_decision(
        '{"intent":"CONCEPT","need":"NONE","no_tool":true,"sql":false,"api":false,"conf":0.91,"codes":[]}'
    )

    assert decision.to_dict() == {
        "intent": "CONCEPT",
        "need": "NONE",
        "no_tool": True,
        "sql": False,
        "api": False,
        "conf": 0.91,
        "codes": [],
    }


def test_semantic_intent_classifier_retries_invalid_json_once() -> None:
    features = extract_objective_prompt_features("What is a schema?")
    context = build_semantic_intent_context(features)
    client = FakeSemanticIntentClient(
        "not json",
        '{"intent":"CONCEPT","need":"NONE","no_tool":true,"sql":false,"api":false,"conf":0.88,"codes":[]}',
    )

    decision = classify_semantic_intent(context, llm_client=client)

    assert client.calls == 2
    assert decision.intent == "CONCEPT"
    assert decision.no_tool is True


def test_semantic_intent_classifier_invalid_after_retry_is_safe_unknown() -> None:
    features = extract_objective_prompt_features("List schemas")
    context = build_semantic_intent_context(features)
    client = FakeSemanticIntentClient("not json", "{still bad")

    decision = classify_semantic_intent(context, llm_client=client)

    assert client.calls == 2
    assert decision.to_dict() == {
        "intent": "AMBIG",
        "need": "UNKNOWN",
        "no_tool": False,
        "sql": False,
        "api": False,
        "conf": 0.0,
        "codes": ["INVALID_JSON"],
    }


def test_semantic_intent_classifier_fallback_is_safe_when_llm_unavailable() -> None:
    context = build_semantic_intent_context(extract_objective_prompt_features("Show failed dataflow runs"))

    decision = classify_semantic_intent(context, llm_client=None)

    assert decision.intent in {"DATA", "LIVE_API", "MIXED", "AMBIG"}
    assert decision.no_tool is False
    assert decision.conf >= 0.0


def test_no_tool_safety_verifier_negative_guardrail_only() -> None:
    features = extract_objective_prompt_features("List schemas")
    decision = parse_semantic_intent_decision(
        '{"intent":"CONCEPT","need":"NONE","no_tool":true,"sql":false,"api":false,"conf":0.95,"codes":[]}'
    )

    result = verify_no_tool_safety(features, decision).to_dict()

    assert result["allow_no_tool"] is False
    assert result["action"] == "BLOCK_NO_TOOL"
    assert "RETR" in result["block"]
    assert "final_route" not in result
    assert "api_policy" not in result
    assert "sql_route" not in result


def test_no_tool_safety_verifier_allows_conceptual_domain_keyword() -> None:
    features = extract_objective_prompt_features("What is a schema?")
    decision = parse_semantic_intent_decision(
        '{"intent":"CONCEPT","need":"NONE","no_tool":true,"sql":false,"api":false,"conf":0.92,"codes":[]}'
    )

    result = verify_no_tool_safety(features, decision)

    assert result.allow_no_tool is True
    assert result.block == []
    assert result.action == "ALLOW_NO_TOOL"


def test_no_tool_safety_verifier_blocks_concrete_data_signals() -> None:
    features = extract_objective_prompt_features("How many datasets use schema 'X'?")
    decision = parse_semantic_intent_decision(
        '{"intent":"CONCEPT","need":"NONE","no_tool":true,"sql":false,"api":false,"conf":0.93,"codes":[]}'
    )

    result = verify_no_tool_safety(features, decision)

    assert result.allow_no_tool is False
    assert {"COUNT", "ENTITY_LOOKUP"} <= set(result.block)
    assert result.has_concrete_data_signal is True


def test_route_ladder_has_no_clarification_or_sql_api_direct_actions() -> None:
    assert ALLOWED_SEMANTIC_ROUTE_ACTIONS == {
        "LLM_DIRECT",
        "LLM_SAFE_DIRECT",
        "SAFE_API_PROBE",
        "EVIDENCE_PIPELINE",
    }
    assert "ASK_CLARIFICATION" not in ALLOWED_SEMANTIC_ROUTE_ACTIONS
    assert "SQL_ONLY" not in ALLOWED_SEMANTIC_ROUTE_ACTIONS
    assert "API_ONLY" not in ALLOWED_SEMANTIC_ROUTE_ACTIONS


def test_route_ladder_direct_for_high_confidence_safe_concept() -> None:
    result = run_semantic_route_decision_ladder("What is a schema?")

    assert result.action == "LLM_DIRECT"
    assert result.no_tool_safety["allow_no_tool"] is True
    assert result.shadow_only is True


def test_route_ladder_evidence_for_concrete_data_prompt() -> None:
    result = run_semantic_route_decision_ladder("Show failed dataflow runs")

    assert result.action == "EVIDENCE_PIPELINE"
    assert result.no_tool_safety["has_concrete_data_signal"] is True


def test_route_ladder_low_low_concept_becomes_safe_direct() -> None:
    calls = [
        parse_semantic_intent_decision(
            '{"intent":"AMBIG","need":"UNKNOWN","no_tool":true,"sql":false,"api":false,"conf":0.40,"codes":[]}'
        ),
        parse_semantic_intent_decision(
            '{"intent":"CONCEPT","need":"NONE","no_tool":true,"sql":false,"api":false,"conf":0.72,"codes":[]}'
        ),
    ]

    def classifier(_context: dict) -> object:
        return calls.pop(0)

    result = run_semantic_route_decision_ladder("Explain dashboards", classifier=classifier)

    assert result.action == "LLM_SAFE_DIRECT"
    assert result.tier_used == 1
    assert result.low_low_case is True


def test_route_ladder_low_low_clear_api_family_becomes_safe_api_probe() -> None:
    calls = [
        parse_semantic_intent_decision(
            '{"intent":"AMBIG","need":"UNKNOWN","no_tool":false,"sql":false,"api":false,"conf":0.30,"codes":[]}'
        ),
        parse_semantic_intent_decision(
            '{"intent":"LIVE_API","need":"API","no_tool":false,"sql":false,"api":true,"conf":0.65,"codes":[]}'
        ),
    ]

    def classifier(_context: dict) -> object:
        return calls.pop(0)

    result = run_semantic_route_decision_ladder("Check current Adobe tag service", classifier=classifier)

    assert result.action == "SAFE_API_PROBE"
    assert result.safe_api_probe["method"] == "GET"
    assert result.safe_api_probe["max_endpoints"] == 1
    assert "{" not in result.safe_api_probe.get("path", "")


def test_llm_safe_direct_blocks_concrete_factual_claims() -> None:
    assert validate_llm_safe_direct_answer("A schema describes the structure of data.")["ok"] is True
    bad = validate_llm_safe_direct_answer("There are 12 schemas in your sandbox.")
    assert bad["ok"] is False
    assert "CONCRETE_COUNT" in bad["blocked_claims"]


def test_codebook_keeps_runtime_compact_and_reports_explanations() -> None:
    payload = extract_objective_prompt_features("What is a schema?").to_dict()

    assert runtime_payload_is_compact(payload) is True
    rendered = render_codebook_report(payload)
    assert "DEF = definition cue" in rendered
    savings = estimate_compact_payload_savings(payload)
    assert savings["compact_tokens"] < savings["verbose_tokens"]


def test_config_defaults_keep_semantic_route_shadow_only(monkeypatch) -> None:
    for name in [
        "ENABLE_OBJECTIVE_PROMPT_FEATURES",
        "ENABLE_SEMANTIC_INTENT_CLASSIFIER",
        "ENABLE_ROUTING_ANTI_HALLUCINATION_GATE",
        "ENABLE_SEMANTIC_ROUTE_DECISION_LADDER",
        "SEMANTIC_ROUTE_SHADOW_ONLY",
        "SEMANTIC_ROUTE_TIER2_DIAGNOSTIC",
        "SEMANTIC_ROUTE_VERBOSE_REPORTS",
    ]:
        monkeypatch.delenv(name, raising=False)

    cfg = Config.from_env()

    assert cfg.enable_objective_prompt_features is True
    assert cfg.enable_semantic_intent_classifier is False
    assert cfg.enable_routing_anti_hallucination_gate is True
    assert cfg.enable_semantic_route_decision_ladder is False
    assert cfg.semantic_route_shadow_only is True
    assert cfg.semantic_route_tier2_diagnostic is False


def test_executor_shadow_checkpoint_integration_does_not_change_runtime_route() -> None:
    executor = AgentExecutor.__new__(AgentExecutor)
    executor.config = Config.from_env()
    logger = CheckpointLogger()

    executor._add_semantic_route_harness_checkpoints("What is a schema?", logger)

    checkpoint_ids = [checkpoint["checkpoint_id"] for checkpoint in logger.to_list()]
    assert checkpoint_ids == ["checkpoint_objective_prompt_features"]


def test_executor_ladder_checkpoint_integration_records_shadow_decision() -> None:
    executor = AgentExecutor.__new__(AgentExecutor)
    executor.config = Config.from_env()
    object.__setattr__(executor.config, "enable_semantic_route_decision_ladder", True)
    logger = CheckpointLogger()

    executor._add_semantic_route_harness_checkpoints("List schemas", logger)

    checkpoints = {checkpoint["checkpoint_id"]: checkpoint for checkpoint in logger.to_list()}
    assert "checkpoint_objective_prompt_features" in checkpoints
    assert "checkpoint_semantic_intent_decision" in checkpoints
    assert "checkpoint_routing_anti_hallucination_gate" in checkpoints
    assert "checkpoint_no_tool_safety_verifier" in checkpoints
    assert "checkpoint_semantic_route_decision_ladder" in checkpoints
    ladder_output = checkpoints["checkpoint_semantic_route_decision_ladder"]["output"]
    assert ladder_output["action"] == "EVIDENCE_PIPELINE"
    assert ladder_output["shadow_only"] is True


def test_routing_anti_hallucination_gate_blocks_wrong_no_tool_and_builds_feedback() -> None:
    features = extract_objective_prompt_features("List schemas")
    decision = parse_semantic_intent_decision(
        '{"intent":"CONCEPT","need":"NONE","no_tool":true,"sql":false,"api":false,"conf":0.96,"codes":["SQL_SCHEMA"]}'
    )

    result = validate_routing_decision_support(features, decision)
    feedback = build_routing_gate_feedback(decision, result, features)

    assert result.ok is False
    assert "UNSUPPORTED_NO_TOOL" in result.block
    assert result.to_dict()["support"] == {"intent": False, "need": False, "caps": True}
    assert "final_route" not in result.to_dict()
    assert feedback["task"] == "Return corrected SemanticIntentDecision JSON only."
    assert feedback["gate"]["allowed_fix"]


def test_routing_gate_unknown_capability_blocks() -> None:
    features = extract_objective_prompt_features("What is a schema?")
    decision = parse_semantic_intent_decision(
        '{"intent":"CONCEPT","need":"NONE","no_tool":true,"sql":false,"api":false,"conf":0.88,"codes":["API_UNKNOWN"]}'
    )

    result = validate_routing_decision_support(features, decision)

    assert result.ok is False
    assert result.unsupported_codes == ["API_UNKNOWN"]
    assert "UNKNOWN_CAPABILITY_CODE" in result.block


def test_routing_gate_feedback_revision_success() -> None:
    features = extract_objective_prompt_features("List schemas")
    bad = parse_semantic_intent_decision(
        '{"intent":"CONCEPT","need":"NONE","no_tool":true,"sql":false,"api":false,"conf":0.96,"codes":["SQL_SCHEMA"]}'
    )
    revised = parse_semantic_intent_decision(
        '{"intent":"DATA","need":"SQL","no_tool":false,"sql":true,"api":false,"conf":0.82,"codes":["SQL_SCHEMA"]}'
    )
    calls = []

    def reviser(_feedback: dict) -> object:
        calls.append("called")
        return revised

    result = run_routing_gate_with_revision(features, bad, reviser=reviser)

    assert result.final_decision.intent == "DATA"
    assert result.final_gate.ok is True
    assert result.revision_attempted is True
    assert result.revision_success is True
    assert len(calls) == 1


def test_routing_gate_failed_revision_fallbacks_by_data_signal() -> None:
    data_features = extract_objective_prompt_features("List schemas")
    concept_features = extract_objective_prompt_features("Explain schemas")
    bad = parse_semantic_intent_decision(
        '{"intent":"CONCEPT","need":"NONE","no_tool":true,"sql":false,"api":false,"conf":0.96,"codes":[]}'
    )
    concept_bad = parse_semantic_intent_decision(
        '{"intent":"CONCEPT","need":"NONE","no_tool":true,"sql":false,"api":false,"conf":0.96,"codes":["API_UNKNOWN"]}'
    )

    data_result = run_routing_gate_with_revision(data_features, bad, reviser=lambda _feedback: bad)
    concept_result = run_routing_gate_with_revision(concept_features, concept_bad, reviser=lambda _feedback: concept_bad)

    assert data_result.fallback_action == "EVIDENCE_PIPELINE"
    assert concept_result.fallback_action == "LLM_SAFE_DIRECT"
    assert data_result.revision_attempted is True
    assert data_result.revision_success is False
