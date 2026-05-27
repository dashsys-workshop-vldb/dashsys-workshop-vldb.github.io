from __future__ import annotations

from dataclasses import replace

import pytest

from dashagent.checkpoints import CheckpointLogger
from dashagent.config import Config
from dashagent.eval_harness import config_for_applied_trial_strategy
from dashagent.executor import AgentExecutor
from dashagent.planner import ALL_STRATEGIES, PACKAGED_DEFAULT_STRATEGY, Plan, PlanStep, STRATEGIES, execution_base_strategy
from dashagent.prompt_semantic_ir import extract_objective_prompt_features


ROBUST = "ROBUST_GENERALIZED_HARNESS_CANDIDATE"


class CountingAPIClient:
    dry_run = False

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict]] = []

    def call_api(self, method, url, params=None, headers=None):
        self.calls.append((method, url, dict(params or {})))
        return {
            "ok": True,
            "dry_run": False,
            "status_code": 200,
            "parsed_evidence": {
                "evidence_state": "live_success",
                "live_evidence_available": True,
                "usable_evidence": True,
                "ids": ["tag-1"],
                "names": ["VIP"],
                "counts": {"items": 1},
            },
            "result_preview": {"items": [{"id": "tag-1", "name": "VIP"}]},
        }


def _sql_then_optional_api_plan(query, routing, metadata, strategy, analysis=None):
    return Plan(
        strategy=strategy,
        rationale="unit SQL direct answer plus optional API",
        steps=[
            PlanStep(
                action="sql",
                purpose="unit SQL direct answer",
                sql="SELECT campaign_id AS id, name FROM dim_campaign ORDER BY campaign_id",
            ),
            PlanStep(
                action="api",
                purpose="unit optional schema API",
                method="GET",
                url="/data/foundation/schemaregistry/tenant/schemas",
                params={},
            ),
        ],
    )


def test_robust_candidate_strategy_is_explicit_and_not_default(tiny_project: Config) -> None:
    assert PACKAGED_DEFAULT_STRATEGY == "SQL_FIRST_API_VERIFY"
    assert ROBUST in ALL_STRATEGIES
    assert ROBUST not in STRATEGIES
    assert execution_base_strategy(ROBUST) == "SQL_FIRST_API_VERIFY"

    cfg = config_for_applied_trial_strategy(tiny_project, ROBUST)
    assert cfg.enable_objective_prompt_features is True
    assert cfg.enable_semantic_intent_classifier is True
    assert cfg.enable_routing_anti_hallucination_gate is True
    assert cfg.enable_no_tool_safety_verifier is True
    assert cfg.enable_semantic_route_decision_ladder is True
    assert cfg.enable_safe_api_probe is True
    assert cfg.enable_staged_evidence_policy is True
    assert cfg.enable_post_sql_deterministic_policy is True
    assert cfg.enable_evidence_quality_classifier is True
    assert cfg.enable_answer_slot_renderer is True
    assert cfg.enable_evidence_grounded_answer_builder is True
    assert cfg.enable_score_provenance_guard is True
    assert cfg.enable_runtime_leakage_guard is True
    assert cfg.enable_hardcode_fake_score_guard is True
    assert cfg.post_sql_llm_advisor_enabled is False
    assert cfg.real_behavior_trial_mode == ROBUST


def test_objective_features_cover_candidate_required_cues() -> None:
    conceptual_schema = extract_objective_prompt_features("What is a schema?")
    assert "DEF" in conceptual_schema.cue
    assert "SCHEMA" in conceptual_schema.domain

    list_schema = extract_objective_prompt_features("List schemas")
    assert "LIST" in list_schema.retr
    assert "SCHEMA" in list_schema.domain

    registry = extract_objective_prompt_features("List schema registry schemas")
    assert "EXPLICIT_API_FAMILY" in registry.flags
    assert "SCHEMA_REGISTRY" in registry.cap
    assert "API" in registry.flags

    inactive = extract_objective_prompt_features("Show inactive journeys")
    assert "INACTIVE" in inactive.status
    assert "JOURNEY" in inactive.domain

    current_platform = extract_objective_prompt_features("Show current platform flow service runs")
    assert "CURRENT" in current_platform.flags
    assert "PLATFORM" in current_platform.flags
    assert "FLOW_SERVICE" in current_platform.cap

    mixed = extract_objective_prompt_features("Explain schemas and list current schema registry records")
    assert "EXPLAIN" in mixed.cue
    assert "LIST" in mixed.retr
    assert "MIXED_CONCEPT_AND_RETRIEVAL" in mixed.flags


def test_runtime_leakage_guard_rejects_gold_and_category() -> None:
    from dashagent.runtime_leakage_guard import assert_runtime_input_isolated

    assert_runtime_input_isolated({"query": "List schemas", "query_id": "unit", "strategy": ROBUST})
    with pytest.raises(ValueError):
        assert_runtime_input_isolated({"query": "List schemas", "gold_answer": "secret"})
    with pytest.raises(ValueError):
        assert_runtime_input_isolated({"query": "List schemas", "category": "api_only"})


def test_robust_candidate_can_skip_tools_for_safe_conceptual_prompt(tiny_project: Config) -> None:
    result = AgentExecutor(tiny_project).run("What is a schema?", strategy=ROBUST, query_id="robust_concept")

    assert result["tool_results"] == []
    assert result["plan"]["steps"] == []
    checkpoint_names = {checkpoint["checkpoint_id"] for checkpoint in result["checkpoints"]}
    assert "checkpoint_objective_prompt_features" in checkpoint_names
    assert "checkpoint_semantic_route_decision_ladder" in checkpoint_names
    assert "checkpoint_score_provenance_guard" in checkpoint_names


def test_robust_candidate_semantic_role_parse_skips_list_format_prompt(tiny_project: Config) -> None:
    result = AgentExecutor(tiny_project).run(
        "List three reasons why schemas matter.",
        strategy=ROBUST,
        query_id="robust_list_format",
    )

    assert result["tool_results"] == []
    checkpoint_names = {checkpoint["checkpoint_id"] for checkpoint in result["checkpoints"]}
    assert "checkpoint_semantic_parse" in checkpoint_names
    assert "checkpoint_semantic_consistency_verifier" in checkpoint_names


def test_robust_candidate_semantic_role_parse_blocks_schema_retrieval_no_tool(tiny_project: Config) -> None:
    result = AgentExecutor(tiny_project).run(
        "List current schemas in the sandbox.",
        strategy=ROBUST,
        query_id="robust_schema_retrieval",
    )

    assert any(row["type"] in {"sql", "api"} for row in result["tool_results"])
    semantic_parse = next(
        checkpoint["output"]
        for checkpoint in result["checkpoints"]
        if checkpoint["checkpoint_id"] == "checkpoint_semantic_parse"
    )
    consistency = next(
        checkpoint["output"]
        for checkpoint in result["checkpoints"]
        if checkpoint["checkpoint_id"] == "checkpoint_semantic_consistency_verifier"
    )
    assert semantic_parse["target"]["grounding"] == "SUPPORTED_DATA_OBJECT"
    assert semantic_parse["target"]["instance_level"] is True
    assert consistency["allow_no_tool"] is False


def test_robust_candidate_does_not_no_tool_mixed_prompt(tiny_project: Config) -> None:
    result = AgentExecutor(tiny_project).run(
        "Explain schemas and list schema records",
        strategy=ROBUST,
        query_id="robust_mixed",
    )

    assert any(row["type"] in {"sql", "api"} for row in result["tool_results"])


def test_robust_candidate_safe_api_probe_runs_one_safe_get(tiny_project: Config) -> None:
    client = CountingAPIClient()
    result = AgentExecutor(tiny_project, api_client=client).run("Tags", strategy=ROBUST, query_id="robust_safe_probe")

    assert len(client.calls) == 1
    assert client.calls[0][0] == "GET"
    assert "{ " not in client.calls[0][1]
    assert [row["type"] for row in result["tool_results"]] == ["api"]
    assert any(checkpoint["checkpoint_id"] == "checkpoint_safe_api_probe" for checkpoint in result["checkpoints"])


def test_robust_candidate_post_sql_policy_skips_optional_api_after_direct_sql(tiny_project: Config) -> None:
    client = CountingAPIClient()
    executor = AgentExecutor(tiny_project, api_client=client)
    executor.planner.create_plan = _sql_then_optional_api_plan

    result = executor.run("List campaigns", strategy=ROBUST, query_id="robust_post_sql_skip")

    assert [row["type"] for row in result["tool_results"]] == ["sql"]
    assert client.calls == []
    assert any(checkpoint["checkpoint_id"] == "checkpoint_post_sql_deterministic_policy" for checkpoint in result["checkpoints"])


def test_evidence_quality_classifier_distinguishes_empty_and_error() -> None:
    from dashagent.evidence_quality_classifier import classify_evidence_quality

    quality = classify_evidence_quality(
        [
            {"type": "sql", "payload": {"ok": True, "rows": [{"id": "c1", "name": "Campaign"}], "row_count": 1}},
            {"type": "api", "payload": {"ok": True, "parsed_evidence": {"evidence_state": "live_empty"}}},
            {"type": "api", "payload": {"ok": False, "error": "unavailable"}},
        ],
        api_required=True,
    )

    assert "SQL_DIRECT_ANSWER" in quality["sql"]
    assert "API_LIVE_EMPTY" in quality["api"]
    assert "API_ERROR" in quality["api"]
    assert "api_error_is_unavailable_not_no_data" in quality["caveats"]


def test_answer_slot_renderer_renders_requested_evidence() -> None:
    from dashagent.answer_slot_renderer import render_answer_slots
    from dashagent.answer_slots import extract_answer_slots

    slots = extract_answer_slots(
        "List campaign names and statuses",
        [
            {
                "type": "sql",
                "payload": {
                    "ok": True,
                    "row_count": 2,
                    "rows": [
                        {"id": "c1", "name": "Birthday Message", "status": "draft"},
                        {"id": "c2", "name": "Welcome Journey", "status": "published"},
                    ],
                },
            }
        ],
    )

    rendered = render_answer_slots("List campaign names and statuses", slots)

    assert "Birthday Message" in rendered.answer
    assert "draft" in rendered.answer
    assert "Welcome Journey" in rendered.answer
    assert "published" in rendered.answer
    assert rendered.unsupported_claims_count == 0
