from __future__ import annotations

from dataclasses import replace

from dashagent.config import Config
from dashagent.endpoint_catalog import EndpointCatalog
from dashagent.evidence_match_scorer import score_evidence_match
from dashagent.planner import PlanStep
from dashagent.post_sql_api_call_verifier import verify_post_sql_api_advice
from dashagent.post_sql_decision_card import build_post_sql_decision_card
from dashagent.post_sql_deterministic_policy import decide_post_sql_api_policy
from dashagent.post_sql_llm_advisor import advise_post_sql_api
from dashagent.prompt_semantic_ir import extract_objective_prompt_features
from dashagent.semantic_intent_classifier import parse_semantic_intent_decision
from dashagent.staged_evidence_policy import decide_initial_evidence_branch


class FakeAdvisorClient:
    def __init__(self, *responses: str) -> None:
        self.responses = list(responses)
        self.calls = 0

    def complete(self, messages: list[dict[str, str]]) -> str:
        self.calls += 1
        return self.responses.pop(0)


def test_evidence_match_scores_sql_and_api_examples() -> None:
    local = score_evidence_match(extract_objective_prompt_features("List schemas"))
    live = score_evidence_match(extract_objective_prompt_features("List current Adobe tags"))
    both = score_evidence_match(extract_objective_prompt_features("Show failed dataflow runs"))

    assert local.sql_match > local.api_match
    assert live.api_match >= 0.7
    assert both.sql_match > 0.0 and both.api_match > 0.0


def test_initial_branch_distribution_rules() -> None:
    sql_only = decide_initial_evidence_branch({"sql_match": 0.9, "api_match": 0.1})
    sql_then_api = decide_initial_evidence_branch({"sql_match": 0.9, "api_match": 0.85})
    api_only = decide_initial_evidence_branch({"sql_match": 0.2, "api_match": 0.9})
    no_tool = decide_initial_evidence_branch({"sql_match": 0.1, "api_match": 0.1, "concrete_data_signal": False})

    assert sql_only.first_branch == "SQL"
    assert sql_only.second_branch_policy == "NONE"
    assert sql_then_api.first_branch == "SQL"
    assert sql_then_api.second_branch_policy == "API_AFTER_SQL_IF_NEEDED"
    assert api_only.first_branch == "API"
    assert no_tool.first_branch == "NO_TOOL"


def test_post_sql_card_is_compact_and_role_based() -> None:
    features = extract_objective_prompt_features("List schemas")
    sql_result = {"ok": True, "rows": [{"id": "s1", "name": "Profile"}], "row_count": 1}
    api_steps = [PlanStep(action="api", purpose="schema list", method="GET", url="/data/foundation/schemaregistry/tenant/schemas", family="schema_registry_schemas")]

    card = build_post_sql_decision_card(features, "LIST", sql_result, api_steps, EndpointCatalog())

    assert card["task"] == "POST_SQL_API_DECISION"
    assert card["sql_state"]["validation"] == "PASS"
    assert card["sql_state"]["direct_answer"] is True
    assert card["api_candidates"][0]["method"] == "GET"
    assert "Profile" not in str(card)
    assert "rows" not in card


def test_high_confidence_post_sql_policy_bypasses_llm() -> None:
    features = extract_objective_prompt_features("List schemas")
    card = build_post_sql_decision_card(
        features,
        "LIST",
        {"ok": True, "rows": [{"id": "s1", "name": "Profile"}], "row_count": 1},
        [PlanStep(action="api", purpose="schema list", method="GET", url="/data/foundation/schemaregistry/tenant/schemas", family="schema_registry_schemas")],
        EndpointCatalog(),
    )

    policy = decide_post_sql_api_policy(card)

    assert policy.suggestion == "SKIP_API"
    assert policy.confidence == "HIGH"


def test_high_call_api_policy_for_live_prompt_bypasses_llm() -> None:
    features = extract_objective_prompt_features("Show current Adobe tags")
    card = build_post_sql_decision_card(
        features,
        "LIST",
        {"ok": True, "rows": [], "row_count": 0},
        [PlanStep(action="api", purpose="tags", method="GET", url="https://experience.adobe.io/unifiedtags/tags", family="unified_tags")],
        EndpointCatalog(),
    )

    policy = decide_post_sql_api_policy(card)

    assert policy.suggestion == "CALL_API"
    assert policy.confidence == "HIGH"


def test_medium_post_sql_policy_calls_llm_advisor() -> None:
    features = extract_objective_prompt_features("Show schema status")
    card = build_post_sql_decision_card(
        features,
        "STATUS",
        {"ok": True, "rows": [{"id": "s1"}], "row_count": 1},
        [PlanStep(action="api", purpose="schema list", method="GET", url="/data/foundation/schemaregistry/tenant/schemas", family="schema_registry_schemas")],
        EndpointCatalog(),
    )
    policy = decide_post_sql_api_policy(card)
    client = FakeAdvisorClient(
        '{"mode":"CALL_API","endpoint_id":"schema_registry_schemas","conf":0.71,"needed_roles":["status"],"codes":["FILL_MISSING_ROLE"]}'
    )

    advice = advise_post_sql_api(card, policy, llm_client=client)

    assert policy.confidence in {"MEDIUM", "LOW"}
    assert client.calls == 1
    assert advice.mode == "CALL_API"


def test_post_sql_advisor_skips_llm_for_high_confidence() -> None:
    features = extract_objective_prompt_features("List schemas")
    card = build_post_sql_decision_card(
        features,
        "LIST",
        {"ok": True, "rows": [{"id": "s1", "name": "Profile"}], "row_count": 1},
        [],
        EndpointCatalog(),
    )
    policy = decide_post_sql_api_policy(card)
    client = FakeAdvisorClient('{"mode":"CALL_API","endpoint_id":"x","conf":1.0,"needed_roles":[],"codes":[]}')

    advice = advise_post_sql_api(card, policy, llm_client=client)

    assert client.calls == 0
    assert advice.source == "DETERMINISTIC_BYPASS"


def test_post_sql_api_verifier_blocks_unknown_and_unresolved_endpoint() -> None:
    catalog = EndpointCatalog()
    card = {
        "api_candidates": [
            {
                "endpoint_id": "schema_registry_schema",
                "family": "schema_registry_schema",
                "method": "GET",
                "safe_get": True,
                "requires_path_param": True,
                "can_fill_roles": ["detail"],
            }
        ],
        "prompt_features": ["RETR"],
        "answer_intent": "DETAIL",
    }
    unknown = verify_post_sql_api_advice(
        {"mode": "CALL_API", "endpoint_id": "not_real", "needed_roles": ["detail"]},
        card,
        catalog,
        api_required=False,
    )
    unresolved = verify_post_sql_api_advice(
        {"mode": "CALL_API", "endpoint_id": "schema_registry_schema", "needed_roles": ["detail"]},
        card,
        catalog,
        api_required=False,
    )

    assert unknown.source == "LLM_ADVISOR_BLOCKED"
    assert "UNKNOWN_ENDPOINT" in unknown.codes
    assert unresolved.source == "LLM_ADVISOR_BLOCKED"
    assert "UNRESOLVED_PATH_PARAM" in unresolved.codes


def test_post_sql_api_required_cannot_be_skipped() -> None:
    card = {"api_candidates": [{"endpoint_id": "unified_tags", "family": "unified_tags", "method": "GET", "safe_get": True, "requires_path_param": False}], "prompt_features": ["TAG"], "answer_intent": "LIST"}

    result = verify_post_sql_api_advice({"mode": "SKIP_API", "endpoint_id": None, "needed_roles": []}, card, EndpointCatalog(), api_required=True)

    assert result.final_action == "CALL_API"
    assert result.source == "LLM_ADVISOR_BLOCKED"
    assert "API_REQUIRED_SKIP_BLOCKED" in result.codes


def test_invalid_llm_json_falls_back_to_deterministic_policy() -> None:
    features = extract_objective_prompt_features("Show schema status")
    card = build_post_sql_decision_card(
        features,
        "STATUS",
        {"ok": True, "rows": [{"id": "s1"}], "row_count": 1},
        [PlanStep(action="api", purpose="schema list", method="GET", url="/data/foundation/schemaregistry/tenant/schemas", family="schema_registry_schemas")],
        EndpointCatalog(),
    )
    policy = decide_post_sql_api_policy(card)
    client = FakeAdvisorClient("not json", "still not json")

    advice = advise_post_sql_api(card, policy, llm_client=client)

    assert client.calls == 2
    assert advice.source == "DETERMINISTIC_FALLBACK"


def test_staged_evidence_config_defaults_shadow_only(monkeypatch) -> None:
    for name in [
        "ENABLE_STAGED_EVIDENCE_POLICY",
        "STAGED_EVIDENCE_POLICY_SHADOW_ONLY",
        "ENABLE_POST_SQL_API_DECISION",
        "POST_SQL_API_DECISION_SHADOW_ONLY",
        "POST_SQL_LLM_ADVISOR_ENABLED",
    ]:
        monkeypatch.delenv(name, raising=False)

    cfg = Config.from_env()

    assert cfg.enable_staged_evidence_policy is False
    assert cfg.staged_evidence_policy_shadow_only is True
    assert cfg.enable_post_sql_api_decision is False
    assert cfg.post_sql_api_decision_shadow_only is True
    assert cfg.post_sql_llm_advisor_enabled is False
