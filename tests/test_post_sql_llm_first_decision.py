from __future__ import annotations

from dataclasses import replace

from dashagent.config import DEFAULT_CONFIG
from dashagent.minimal_correction_feedback import build_minimal_correction_feedback
from dashagent.planner import PACKAGED_DEFAULT_STRATEGY
from dashagent.post_sql_llm_decision import (
    PostSQLLLMDecision,
    parse_post_sql_llm_decision,
    reset_post_sql_llm_backend_circuit_for_tests,
    run_post_sql_llm_first_decision,
)
from dashagent.post_sql_semantic_decision_card import build_post_sql_semantic_decision_card
from dashagent.post_sql_semantic_decision_gate import (
    gate_post_sql_semantic_decision,
    risk_minimizing_post_sql_fallback,
    verify_post_sql_execution_contract,
)
from dashagent.semantic_parse import SemanticParse


class SequenceLLMClient:
    def __init__(self, responses: list[dict]) -> None:
        self.responses = list(responses)
        self.messages_seen: list[list[dict[str, str]]] = []

    def generate_messages(self, messages):
        self.messages_seen.append(messages)
        payload = self.responses.pop(0)
        return {"ok": True, "content": __import__("json").dumps(payload)}


class UnavailableLLMClient:
    def __init__(self) -> None:
        self.calls = 0

    def available(self) -> bool:
        return True

    def generate_messages(self, messages):
        self.calls += 1
        return {
            "ok": False,
            "skipped": False,
            "content": "",
            "error": "backend unavailable",
        }


def _semantic_parse(evidence_need: str = "SQL_API") -> SemanticParse:
    return SemanticParse.from_dict(
        {
            "operation": "COUNT",
            "target": {
                "text": "schemas",
                "grounding": "SUPPORTED_DATA_OBJECT",
                "object_family": "SCHEMA",
                "instance_level": True,
            },
            "filters": {},
            "requested_fields": ["COUNT"],
            "capability": {"sql_match": True, "api_match": True, "api_families": ["schema_registry_schemas"]},
            "evidence_need": evidence_need,
            "no_tool_safe": False,
            "confidence": 0.9,
            "supporting_spans": [],
            "risk_codes": [],
        }
    )


def _card(**overrides):
    payload = {
        "task": "POST_SQL_SEMANTIC_DECISION",
        "user_prompt": "How many current schemas are in the sandbox?",
        "semantic_parse": _semantic_parse().to_dict(),
        "user_requested_scope": "LIVE_PLATFORM",
        "sql_result_scope": "LOCAL_SNAPSHOT",
        "sql_state": {
            "execution": "SUCCESS",
            "row_count_bucket": "ONE",
            "returned_roles": ["count"],
            "missing_roles": [],
            "direct_answer": True,
            "partial_answer": False,
            "zero_rows": False,
        },
        "sql_facts_summary": {"row_count_bucket": "ONE", "returned_roles": ["count"]},
        "api_candidates": [
            {
                "endpoint_id": "schema_registry_schemas",
                "family": "schema_registry_schemas",
                "method": "GET",
                "safe_get": True,
                "requires_path_param": False,
                "can_answer_roles": ["count"],
                "can_fill_roles": ["count"],
            }
        ],
        "api_need_prior": "API_REQUIRED",
        "explicit_cues": ["CURRENT", "PLATFORM", "API", "SCHEMA_REGISTRY"],
        "constraints": {"api_required_cannot_skip": True},
    }
    payload.update(overrides)
    return payload


def test_minimal_feedback_excludes_raw_rows_catalog_and_gold() -> None:
    feedback = build_minimal_correction_feedback(
        task="REVISE_POST_SQL_API_DECISION",
        previous_decision={"mode": "SKIP_API", "endpoint_id": None},
        conflicts=[
            {
                "code": "SQL_SCOPE_MISMATCH",
                "given": "sql_scope=LOCAL_SNAPSHOT",
                "required": "user_scope=LIVE_PLATFORM",
                "raw_sql_rows": [{"secret": "do-not-include"}],
                "full_api_catalog": [{"endpoint_id": "a"}, {"endpoint_id": "b"}],
                "gold_answer": "secret",
            }
        ],
        must_reconsider=["scope_match"],
        allowed_outputs=["CALL_API", "CAVEAT_ONLY"],
        forbidden_outputs=["SKIP_API"],
        output_schema={"mode": "CALL_API|CAVEAT_ONLY"},
    ).to_dict()

    assert feedback["task"] == "REVISE_POST_SQL_API_DECISION"
    assert feedback["allowed_outputs"] == ["CALL_API", "CAVEAT_ONLY"]
    assert feedback["forbidden_outputs"] == ["SKIP_API"]
    assert "raw_sql_rows" not in str(feedback)
    assert "full_api_catalog" not in str(feedback)
    assert "gold_answer" not in str(feedback)


def test_post_sql_llm_skip_local_sql_count_passes_gate() -> None:
    card = _card(
        user_prompt="How many schemas are in the local snapshot?",
        user_requested_scope="LOCAL_SNAPSHOT",
        sql_result_scope="LOCAL_SNAPSHOT",
        api_need_prior="API_SKIP",
        explicit_cues=[],
        constraints={"api_required_cannot_skip": False},
    )
    decision = PostSQLLLMDecision("SKIP_API", None, 0.91, ["SQL_LOCAL_COUNT"])

    gate = gate_post_sql_semantic_decision(decision, card)

    assert gate.ok is True
    assert gate.revision_required is False
    assert gate.feedback is None


def test_post_sql_live_platform_skip_generates_minimal_feedback() -> None:
    decision = PostSQLLLMDecision("SKIP_API", None, 0.8, ["SQL_HAS_COUNT"])

    gate = gate_post_sql_semantic_decision(decision, _card())

    assert gate.ok is False
    assert gate.revision_required is True
    assert set(gate.conflict_codes) >= {"API_REQUIRED_CANNOT_SKIP", "SQL_SCOPE_MISMATCH"}
    assert gate.feedback is not None
    feedback = gate.feedback.to_dict()
    assert feedback["task"] == "REVISE_POST_SQL_API_DECISION"
    assert feedback["allowed_outputs"] == ["CALL_API", "CAVEAT_ONLY"]
    assert feedback["forbidden_outputs"] == ["SKIP_API"]
    assert "raw_sql_rows" not in str(feedback)


def test_post_sql_revision_to_call_api_is_accepted() -> None:
    client = SequenceLLMClient(
        [
            {"mode": "SKIP_API", "endpoint_id": None, "confidence": 0.8, "codes": ["SQL_HAS_COUNT"]},
            {"mode": "CALL_API", "endpoint_id": "schema_registry_schemas", "confidence": 0.88, "codes": ["SCOPE_FIX"]},
        ]
    )

    result = run_post_sql_llm_first_decision(_card(), llm_client=client)

    assert result["first_pass_ok"] is False
    assert result["revision_attempted"] is True
    assert result["revision_success"] is True
    assert result["execution_verifier"]["final_action"] == "CALL_API"
    assert result["execution_verifier"]["source"] == "LLM_DECISION_VERIFIED"
    assert result["feedback"]["task"] == "REVISE_POST_SQL_API_DECISION"
    assert result["metrics"]["post_sql_first_pass_fail_count"] == 1
    assert result["metrics"]["post_sql_revision_attempt_count"] == 1
    assert result["metrics"]["post_sql_revision_success_count"] == 1
    assert result["metrics"]["post_sql_risk_fallback_count"] == 0


def test_default_backend_unavailable_circuit_skips_repeated_runtime_attempts(monkeypatch) -> None:
    reset_post_sql_llm_backend_circuit_for_tests()
    client = UnavailableLLMClient()
    monkeypatch.setattr("dashagent.post_sql_llm_decision.get_llm_client", lambda: client)

    first = run_post_sql_llm_first_decision(_card())
    second = run_post_sql_llm_first_decision(_card())

    assert client.calls == 1
    assert first["llm_backend_available"] is False
    assert second["llm_backend_available"] is False
    assert first["execution_verifier"]["final_action"] == "CALL_API"
    assert second["execution_verifier"]["final_action"] == "CALL_API"
    reset_post_sql_llm_backend_circuit_for_tests()


def test_post_sql_partial_sql_revision_to_call_api_is_accepted() -> None:
    partial_card = _card(
        user_prompt="Show Journey A status.",
        api_need_prior="API_OPTIONAL",
        constraints={"api_required_cannot_skip": False},
        explicit_cues=[],
        sql_state={
            "execution": "SUCCESS",
            "row_count_bucket": "ONE",
            "returned_roles": ["name"],
            "missing_roles": ["status"],
            "direct_answer": False,
            "partial_answer": True,
            "zero_rows": False,
        },
        api_candidates=[{**_card()["api_candidates"][0], "can_answer_roles": ["status"], "can_fill_roles": ["status"]}],
    )
    client = SequenceLLMClient(
        [
            {"mode": "SKIP_API", "endpoint_id": None, "confidence": 0.8, "codes": ["SQL_HAS_NAME"]},
            {"mode": "CALL_API", "endpoint_id": "schema_registry_schemas", "confidence": 0.86, "codes": ["FILL_STATUS"]},
        ]
    )

    result = run_post_sql_llm_first_decision(partial_card, llm_client=client)

    assert result["revision_attempted"] is True
    assert result["revision_success"] is True
    assert result["execution_verifier"]["final_action"] == "CALL_API"
    assert "MISSING_ROLES_CAN_BE_FILLED_BY_API" in result["first_gate"]["conflict_codes"]


def test_post_sql_repeated_invalid_skip_uses_risk_minimizing_fallback() -> None:
    client = SequenceLLMClient(
        [
            {"mode": "SKIP_API", "endpoint_id": None, "confidence": 0.8, "codes": ["SQL_HAS_COUNT"]},
            {"mode": "SKIP_API", "endpoint_id": None, "confidence": 0.8, "codes": ["REPEATED"]},
        ]
    )

    result = run_post_sql_llm_first_decision(_card(), llm_client=client)

    assert result["revision_attempted"] is True
    assert result["revision_success"] is False
    assert result["fallback"]["fallback_source"] == "RISK_MINIMIZING_FALLBACK"
    assert result["fallback"]["semantic_certainty_claimed"] is False
    assert result["execution_verifier"]["final_action"] == "CALL_API"
    assert result["execution_verifier"]["source"] == "RISK_MINIMIZING_FALLBACK"


def test_api_required_partial_sql_and_sql_error_cannot_skip() -> None:
    base_decision = PostSQLLLMDecision("SKIP_API", None, 0.8, [])

    assert "API_REQUIRED_CANNOT_SKIP" in gate_post_sql_semantic_decision(base_decision, _card()).conflict_codes

    partial = _card(
        api_need_prior="API_OPTIONAL",
        constraints={"api_required_cannot_skip": False},
        sql_state={
            "execution": "SUCCESS",
            "row_count_bucket": "ONE",
            "returned_roles": ["name"],
            "missing_roles": ["status"],
            "direct_answer": False,
            "partial_answer": True,
            "zero_rows": False,
        },
        explicit_cues=[],
        api_candidates=[{**_card()["api_candidates"][0], "can_fill_roles": ["status"]}],
    )
    assert "MISSING_ROLES_CAN_BE_FILLED_BY_API" in gate_post_sql_semantic_decision(base_decision, partial).conflict_codes

    sql_error = _card(
        api_need_prior="API_OPTIONAL",
        constraints={"api_required_cannot_skip": False},
        sql_state={"execution": "ERROR", "missing_roles": [], "direct_answer": False, "partial_answer": False, "zero_rows": False},
        explicit_cues=[],
    )
    assert "SQL_ERROR_API_CAN_ANSWER" in gate_post_sql_semantic_decision(base_decision, sql_error).conflict_codes


def test_low_risk_local_sql_fallback_can_skip() -> None:
    card = _card(
        user_requested_scope="LOCAL_SNAPSHOT",
        sql_result_scope="LOCAL_SNAPSHOT",
        api_need_prior="API_SKIP",
        explicit_cues=[],
        constraints={"api_required_cannot_skip": False},
        api_candidates=[],
    )

    fallback = risk_minimizing_post_sql_fallback(card).to_dict()

    assert fallback["mode"] == "SKIP_API"
    assert fallback["fallback_source"] == "LOW_RISK_LOCAL_SQL_FALLBACK"
    assert fallback["semantic_certainty_claimed"] is False


def test_call_api_unresolved_or_unsafe_endpoint_is_caveated_not_faked() -> None:
    unresolved_card = _card(api_candidates=[{**_card()["api_candidates"][0], "requires_path_param": True}])
    unresolved = verify_post_sql_execution_contract(
        PostSQLLLMDecision("CALL_API", "schema_registry_schemas", 0.8, []),
        unresolved_card,
    ).to_dict()
    assert unresolved["ok"] is False
    assert unresolved["final_action"] == "CAVEAT_ONLY"
    assert "UNRESOLVED_PATH_PARAM" in unresolved["codes"]

    unsafe_card = _card(api_candidates=[{**_card()["api_candidates"][0], "method": "POST", "safe_get": False}])
    unsafe = verify_post_sql_execution_contract(PostSQLLLMDecision("CALL_API", "schema_registry_schemas", 0.8, []), unsafe_card).to_dict()
    assert unsafe["final_action"] == "CAVEAT_ONLY"
    assert "UNSAFE_METHOD" in unsafe["codes"]


def test_post_sql_card_builder_keeps_payload_compact() -> None:
    card = build_post_sql_semantic_decision_card(
        user_prompt="How many current schemas are in the sandbox?",
        semantic_parse=_semantic_parse(),
        features={"flags": ["CURRENT", "PLATFORM", "API"], "cap": ["SCHEMA_REGISTRY"]},
        answer_intent="COUNT",
        sql_result={"ok": True, "rows": [{"count": 3, "large": "x" * 1000}], "row_count": 1},
        api_steps=[{"action": "api", "method": "GET", "url": "/data/foundation/schemaregistry/tenant/schemas"}],
        endpoint_catalog=None,
        api_need_prior="API_REQUIRED",
    )

    assert card["user_prompt"] == "How many current schemas are in the sandbox?"
    assert card["sql_state"]["returned_roles"] == ["count"]
    assert "x" * 100 not in str(card)
    assert card["constraints"]["api_required_cannot_skip"] is True


def test_parse_post_sql_llm_decision_accepts_confidence_alias() -> None:
    parsed = parse_post_sql_llm_decision({"mode": "CALL_API", "endpoint_id": "schema_registry_schemas", "confidence": 0.7})

    assert parsed.mode == "CALL_API"
    assert parsed.endpoint_id == "schema_registry_schemas"
    assert parsed.confidence == 0.7


def test_packaged_default_stays_sql_first() -> None:
    assert PACKAGED_DEFAULT_STRATEGY == "SQL_FIRST_API_VERIFY"
    assert DEFAULT_CONFIG.real_behavior_trial_mode == ""
