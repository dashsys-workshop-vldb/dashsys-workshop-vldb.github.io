from __future__ import annotations

import json
from dataclasses import replace

import pytest

from dashagent.checkpoints import CheckpointLogger
from dashagent.config import Config, ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2
from dashagent.eval_harness import config_for_applied_trial_strategy
from dashagent.executor import AgentExecutor
from dashagent.planner import ALL_STRATEGIES, PACKAGED_DEFAULT_STRATEGY, Plan, PlanStep, STRATEGIES, execution_base_strategy
from dashagent.pre_evidence_routing_boundary import should_bypass_evidence_for_llm_direct
from dashagent.prompt_semantic_ir import extract_objective_prompt_features
from tests.test_llm_owned_v2_workflow import _legacy_unified_fixture_to_semantic_ir, _tool_response


ROBUST = "ROBUST_GENERALIZED_HARNESS_CANDIDATE"
ROBUST_V2 = ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2


def _checkpoint_names(result: dict) -> set[str]:
    return {checkpoint["checkpoint_id"] for checkpoint in result["checkpoints"]}


def _checkpoint_output(result: dict, checkpoint_id: str) -> dict:
    return next(
        checkpoint["output"]
        for checkpoint in result["checkpoints"]
        if checkpoint["checkpoint_id"] == checkpoint_id
    )


def _assert_post_evidence_answer_router_not_run(result: dict) -> None:
    checkpoint_names = _checkpoint_names(result)
    assert "checkpoint_14_evidence_bus" not in checkpoint_names
    assert "checkpoint_broad_question_classifier" not in checkpoint_names
    assert "checkpoint_answer_intent_router" not in checkpoint_names
    assert "checkpoint_hybrid_answer_composer" not in checkpoint_names


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


class SequencedLLMClient:
    def __init__(self, responses: list[dict]) -> None:
        self.responses = list(responses)
        self.last_final_answer: str | None = None

    def available(self):
        return True

    def provider_name(self):
        return "fake_llm"

    def model_name(self):
        return "fake-model"

    def generate(self, system_prompt, user_prompt, tools=None):
        if "Direct Route Challenge" in str(system_prompt):
            return {"ok": True, "provider": self.provider_name(), "model": self.model_name(), "content": "NEEDS_EVIDENCE=NO\nREASON=pure concept"}
        if "final-answer writer" in str(system_prompt):
            try:
                payload = json.loads(user_prompt)
            except Exception:
                payload = {}
            if payload.get("task_checklist") == []:
                prompt = str(payload.get("user_prompt") or "")
                if "list schemas" in prompt.lower():
                    answer = "Here, list means to present items in a sequence."
                else:
                    answer = "A schema defines the structure and meaning of data fields."
                return {"ok": True, "provider": self.provider_name(), "model": self.model_name(), "content": answer}
            if self.last_final_answer:
                return {"ok": True, "provider": self.provider_name(), "model": self.model_name(), "content": self.last_final_answer}
            return {"ok": True, "provider": self.provider_name(), "model": self.model_name(), "content": "Runtime evidence was collected."}
        if not self.responses:
            raise AssertionError("Fake LLM called more times than expected")
        payload = self.responses.pop(0)
        if isinstance(payload, dict) and payload.get("final_answer"):
            self.last_final_answer = str(payload.get("final_answer") or "")
        return {"ok": True, "provider": self.provider_name(), "model": self.model_name(), "content": json.dumps(payload)}

    def generate_messages(self, messages, tools=None, tool_choice=None, parallel_tool_calls=None, **kwargs):
        tool_names = {
            str(((tool.get("function") or {}).get("name")) or "")
            for tool in (tools or [])
            if isinstance(tool, dict)
        }
        if "submit_final_answer" in tool_names:
            if not self.responses:
                raise AssertionError("Fake LLM called more times than expected")
            payload = self.responses.pop(0)
            self.last_final_answer = str(payload.get("final_answer") or "")
            return _tool_response("submit_final_answer", payload)
        if "submit_semantic_ir_plan" in tool_names:
            if not self.responses:
                raise AssertionError("Fake LLM called more times than expected")
            payload = _legacy_unified_fixture_to_semantic_ir(self.responses.pop(0))
            return _tool_response("submit_semantic_ir_plan", payload)
        return self.generate(messages[0]["content"], messages[-1]["content"], tools=tools)


def _install_v2_llm_plans(monkeypatch: pytest.MonkeyPatch, responses: list[dict]) -> SequencedLLMClient:
    client = SequencedLLMClient(responses)
    monkeypatch.setattr("dashagent.llm_unified_planner.get_llm_client", lambda: client)
    monkeypatch.setattr("dashagent.llm_final_answer_composer.get_llm_client", lambda: client)
    return client


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


def _sql_count_then_optional_schema_api_plan(query, routing, metadata, strategy, analysis=None):
    return Plan(
        strategy=strategy,
        rationale="unit local count plus optional schema API",
        steps=[
            PlanStep(
                action="sql",
                purpose="unit SQL count",
                sql="SELECT COUNT(*) AS count FROM dim_campaign",
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
    assert cfg.enable_post_sql_llm_semantic_decision is True
    assert cfg.enable_evidence_quality_classifier is True
    assert cfg.enable_answer_slot_renderer is True
    assert cfg.enable_evidence_grounded_answer_builder is True
    assert cfg.enable_evidence_grounded_llm_answer_generator is True
    assert cfg.enable_evidence_grounded_final_answer_verifier is True
    assert cfg.enable_score_provenance_guard is True
    assert cfg.enable_runtime_leakage_guard is True
    assert cfg.enable_hardcode_fake_score_guard is True
    assert cfg.post_sql_llm_advisor_enabled is False
    assert cfg.real_behavior_trial_mode == ROBUST


def test_robust_v2_strategy_is_explicit_research_planner_not_sql_first(tiny_project: Config) -> None:
    assert PACKAGED_DEFAULT_STRATEGY == "SQL_FIRST_API_VERIFY"
    assert ROBUST_V2 in ALL_STRATEGIES
    assert ROBUST_V2 not in STRATEGIES
    assert execution_base_strategy(ROBUST_V2) == ROBUST_V2

    cfg = config_for_applied_trial_strategy(tiny_project, ROBUST_V2)
    assert cfg.enable_research_generalized_planner is True
    assert cfg.enable_objective_prompt_features is True
    assert cfg.enable_semantic_parse is True
    assert cfg.enable_llm_first_semantic_decision is True
    assert cfg.enable_minimal_correction_feedback is True
    assert cfg.enable_progressive_evidence_policy is True
    assert cfg.enable_semantic_route_decision_ladder is True
    assert cfg.enable_safe_api_probe is True
    assert cfg.enable_staged_evidence_policy is True
    assert cfg.enable_post_sql_llm_first_decision is True
    assert cfg.enable_post_sql_llm_semantic_decision is True
    assert cfg.enable_risk_minimizing_fallback is True
    assert cfg.enable_broad_question_classifier is True
    assert cfg.enable_hybrid_answer_composer is True
    assert cfg.enable_gold_style_canonical_renderer is True
    assert cfg.enable_llm_concept_answer is True
    assert cfg.enable_legacy_first_answer_override is True
    assert cfg.enable_evidence_grounded_final_answer_verifier is True
    assert cfg.enable_runtime_leakage_guard is True
    assert cfg.enable_score_provenance_guard is True
    assert cfg.real_behavior_trial_mode == ROBUST_V2


def test_robust_v2_runs_llm_owned_planner_and_evidence_checkpoints(tiny_project: Config, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_v2_llm_plans(
        monkeypatch,
        [
            {
                "route": "EVIDENCE_PIPELINE",
                "evidence_order": "SQL_FIRST",
                "direct_answer": None,
                "sql": {"query": "SELECT name, status FROM dim_campaign ORDER BY campaign_id", "params": []},
                "api_request": None,
                "reason": "LLM-owned data evidence",
            },
            {
                "final_answer": "Inactive journeys: Birthday Message (draft); Welcome Journey (published).",
                "used_pass_ids": ["sql_1"],
                "claimed_facts": [{"claim": "Birthday Message and Welcome Journey were returned.", "supporting_pass_ids": ["sql_1"]}],
                "caveats_included": [],
            },
        ],
    )
    result = AgentExecutor(tiny_project).run(
        "Show inactive journeys.",
        strategy=ROBUST_V2,
        query_id="robust_v2_inactive_journeys",
    )

    assert result["plan"]["strategy"] == ROBUST_V2
    assert any(row["type"] in {"sql", "api"} for row in result["tool_results"])
    checkpoint_names = {checkpoint["checkpoint_id"] for checkpoint in result["checkpoints"]}
    assert "checkpoint_llm_unified_planner" in checkpoint_names
    assert "checkpoint_llm_owned_generation_boundary" in checkpoint_names
    assert "checkpoint_00_prompt_router" not in checkpoint_names
    assert "checkpoint_progressive_evidence_policy" not in checkpoint_names
    assert "checkpoint_broad_question_classifier" not in checkpoint_names
    assert "checkpoint_answer_intent_router" not in checkpoint_names
    assert "checkpoint_hybrid_answer_composer" not in checkpoint_names
    assert "checkpoint_llm_final_answer_composer" in checkpoint_names
    boundary = _checkpoint_output(result, "checkpoint_llm_owned_generation_boundary")
    assert boundary["llm_owned_generation"] is True
    assert "sql_gate_passed" in boundary
    assert "api_gate_passed" in boundary
    assert boundary["backend_semantic_planning_used"] is False


def test_robust_v2_safe_conceptual_and_meta_prompts_can_no_tool(tiny_project: Config, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_v2_llm_plans(
        monkeypatch,
        [
            {
                "route": "LLM_DIRECT",
                "evidence_order": "NO_EVIDENCE",
                "direct_answer": "Schemas define data structure and field meaning.",
                "sql": None,
                "api_request": None,
                "reason": "concept",
            },
            {
                "route": "LLM_DIRECT",
                "evidence_order": "NO_EVIDENCE",
                "direct_answer": "Here, list means to present items in a sequence.",
                "sql": None,
                "api_request": None,
                "reason": "meta-language",
            },
        ],
    )
    conceptual = AgentExecutor(tiny_project).run(
        "List three reasons why schemas matter.",
        strategy=ROBUST_V2,
        query_id="robust_v2_conceptual_list",
    )
    assert conceptual["tool_results"] == []
    conceptual_boundary = _checkpoint_output(conceptual, "checkpoint_evidence_pipeline_bypass")
    assert conceptual_boundary["evidence_pipeline_bypassed"] is True
    assert conceptual_boundary["bypass_reason"] == "llm_owned_direct_no_evidence_required"
    assert conceptual_boundary["pre_evidence_route"] == "LLM_DIRECT"
    assert conceptual_boundary["post_evidence_answer_router_ran"] is False
    assert conceptual_boundary["evidence_bus_built"] is False
    _assert_post_evidence_answer_router_not_run(conceptual)

    meta = AgentExecutor(tiny_project).run(
        "In the phrase 'list schemas', what does 'list' mean?",
        strategy=ROBUST_V2,
        query_id="robust_v2_meta_list",
    )
    assert meta["tool_results"] == []
    meta_boundary = _checkpoint_output(meta, "checkpoint_evidence_pipeline_bypass")
    assert meta_boundary["evidence_pipeline_bypassed"] is True
    assert meta_boundary["pre_evidence_route"] in {"LLM_DIRECT", "LLM_SAFE_DIRECT"}
    assert meta_boundary["post_evidence_answer_router_ran"] is False
    assert meta_boundary["evidence_bus_built"] is False
    _assert_post_evidence_answer_router_not_run(meta)
    assert "you have" not in meta["final_answer"].lower()
    assert "current schemas" not in meta["final_answer"].lower()


def test_robust_v2_pure_schema_concept_bypasses_evidence_bus(tiny_project: Config, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_v2_llm_plans(
        monkeypatch,
        [
            {
                "route": "LLM_DIRECT",
                "evidence_order": "NO_EVIDENCE",
                "direct_answer": "A schema defines the structure and meaning of data fields.",
                "sql": None,
                "api_request": None,
                "reason": "concept",
            }
        ],
    )
    result = AgentExecutor(tiny_project).run(
        "What is a schema?",
        strategy=ROBUST_V2,
        query_id="robust_v2_schema_concept_bypass",
    )

    assert result["tool_results"] == []
    boundary = _checkpoint_output(result, "checkpoint_evidence_pipeline_bypass")
    assert boundary["evidence_pipeline_bypassed"] is True
    assert boundary["pre_evidence_route"] == "LLM_DIRECT"
    assert boundary["post_evidence_answer_router_ran"] is False
    assert boundary["evidence_bus_built"] is False
    _assert_post_evidence_answer_router_not_run(result)
    assert "you have" not in result["final_answer"].lower()
    assert "current schemas" not in result["final_answer"].lower()


def test_pre_evidence_bypass_requires_pure_no_evidence_semantic_parse() -> None:
    base_payload = {
        "action": "LLM_SAFE_DIRECT",
        "confidence": 0.95,
        "semantic_intent_decision": {"conf": 0.95, "need": "NONE", "no_tool": True},
        "progressive_evidence_policy": {"confidence": "HIGH", "requires_evidence_pipeline": False},
    }
    assert not should_bypass_evidence_for_llm_direct(base_payload, strategy=ROBUST_V2, prompt="What is a schema?")

    pure_concept_payload = {
        **base_payload,
        "semantic_parse": {
            "operation": "DEFINE",
            "target": {"grounding": "CONCEPTUAL_OBJECT", "instance_level": False},
            "evidence_need": "NONE",
            "no_tool_safe": True,
            "confidence": 0.9,
        },
    }
    assert should_bypass_evidence_for_llm_direct(
        pure_concept_payload,
        strategy=ROBUST_V2,
        prompt="What is a schema?",
    )

    data_payload = {
        **base_payload,
        "semantic_parse": {
            "operation": "LOOKUP",
            "target": {"grounding": "SUPPORTED_DATA_OBJECT", "instance_level": True},
            "evidence_need": "SQL_API",
            "no_tool_safe": False,
            "confidence": 0.9,
        },
    }
    assert not should_bypass_evidence_for_llm_direct(
        data_payload,
        strategy=ROBUST_V2,
        prompt="What schemas do I have?",
    )


def test_robust_v2_mixed_prompt_still_uses_evidence_bus(tiny_project: Config, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_v2_llm_plans(
        monkeypatch,
        [
            {
                "route": "EVIDENCE_PIPELINE",
                "evidence_order": "SQL_FIRST",
                "direct_answer": None,
                "sql": {"query": "SELECT name, status FROM dim_campaign ORDER BY campaign_id", "params": []},
                "api_request": None,
                "reason": "mixed prompt needs data evidence",
            },
            {
                "final_answer": "An inactive journey is not currently running. Journeys: Birthday Message (draft); Welcome Journey (published).",
                "used_pass_ids": ["sql_1"],
                "claimed_facts": [{"claim": "Birthday Message and Welcome Journey were returned.", "supporting_pass_ids": ["sql_1"]}],
                "caveats_included": [],
            },
        ],
    )
    result = AgentExecutor(tiny_project).run(
        "Explain what inactive journey means and show inactive journeys.",
        strategy=ROBUST_V2,
        query_id="robust_v2_mixed_evidence_boundary",
    )

    assert any(row["type"] in {"sql", "api"} for row in result["tool_results"])
    boundary = _checkpoint_output(result, "checkpoint_evidence_pipeline_boundary")
    assert boundary["evidence_pipeline_bypassed"] is False
    assert boundary["evidence_bus_built"] is True
    assert boundary["post_evidence_answer_router_ran"] is False
    assert "checkpoint_14_evidence_bus" in _checkpoint_names(result)
    assert "checkpoint_broad_question_classifier" not in _checkpoint_names(result)
    assert "checkpoint_hybrid_answer_composer" not in _checkpoint_names(result)
    assert "checkpoint_llm_final_answer_composer" in _checkpoint_names(result)


def test_robust_v2_ambiguous_data_like_prompt_still_uses_evidence_bus(tiny_project: Config, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_v2_llm_plans(
        monkeypatch,
        [
            {
                "route": "EVIDENCE_PIPELINE",
                "evidence_order": "SQL_FIRST",
                "direct_answer": None,
                "sql": {"query": "SELECT name FROM dim_campaign ORDER BY campaign_id", "params": []},
                "api_request": None,
                "reason": "ambiguous user-specific data",
            },
            {
                "final_answer": "Schemas returned by the local evidence: Birthday Message; Welcome Journey.",
                "used_pass_ids": ["sql_1"],
                "claimed_facts": [{"claim": "Birthday Message and Welcome Journey were returned.", "supporting_pass_ids": ["sql_1"]}],
                "caveats_included": [],
            },
        ],
    )
    result = AgentExecutor(tiny_project).run(
        "What schemas do I have?",
        strategy=ROBUST_V2,
        query_id="robust_v2_ambiguous_schema_evidence_boundary",
    )

    assert any(row["type"] in {"sql", "api"} for row in result["tool_results"])
    boundary = _checkpoint_output(result, "checkpoint_evidence_pipeline_boundary")
    assert boundary["evidence_pipeline_bypassed"] is False
    assert boundary["evidence_bus_built"] is True
    assert boundary["post_evidence_answer_router_ran"] is False
    assert "checkpoint_14_evidence_bus" in _checkpoint_names(result)
    assert "checkpoint_llm_final_answer_composer" in _checkpoint_names(result)


def test_sql_first_strategy_does_not_use_research_evidence_bypass(tiny_project: Config) -> None:
    result = AgentExecutor(tiny_project).run(
        "What is a schema?",
        strategy="SQL_FIRST_API_VERIFY",
        query_id="sql_first_schema_concept_boundary_unchanged",
    )

    assert "checkpoint_evidence_pipeline_bypass" not in _checkpoint_names(result)
    assert result["strategy"] == "SQL_FIRST_API_VERIFY"


def test_robust_v2_evidence_bypass_trace_has_no_gold_or_oracle_fields(tiny_project: Config, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_v2_llm_plans(
        monkeypatch,
        [
            {
                "route": "LLM_DIRECT",
                "evidence_order": "NO_EVIDENCE",
                "direct_answer": "A schema defines data structure.",
                "sql": None,
                "api_request": None,
                "reason": "concept",
            }
        ],
    )
    result = AgentExecutor(tiny_project).run(
        "What is a schema?",
        strategy=ROBUST_V2,
        query_id="robust_v2_schema_concept_no_leakage",
    )

    boundary = _checkpoint_output(result, "checkpoint_evidence_pipeline_bypass")
    serialized = repr(boundary).lower()
    assert "gold" not in serialized
    assert "oracle" not in serialized
    assert "expected_trace" not in serialized
    assert "category" not in serialized


def test_robust_v2_post_sql_local_snapshot_count_skips_optional_api(tiny_project: Config, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_v2_llm_plans(
        monkeypatch,
        [
            {
                "route": "EVIDENCE_PIPELINE",
                "evidence_order": "SQL_FIRST",
                "direct_answer": None,
                "sql": {"query": "SELECT COUNT(*) AS count FROM dim_campaign", "params": []},
                "api_request": None,
                "reason": "local SQL count only",
            },
            {
                "final_answer": "There are 2 schema records in the local snapshot.",
                "used_pass_ids": ["sql_1"],
                "claimed_facts": [{"claim": "There are 2 schema records in the local snapshot.", "supporting_pass_ids": ["sql_1"]}],
                "caveats_included": [],
            },
        ],
    )
    client = CountingAPIClient()
    executor = AgentExecutor(tiny_project, api_client=client)

    result = executor.run(
        "How many schema records are in the local snapshot?",
        strategy=ROBUST_V2,
        query_id="robust_v2_local_count",
    )

    assert result["plan"]["strategy"] == ROBUST_V2
    assert [row["type"] for row in result["tool_results"]] == ["sql"]
    assert client.calls == []
    assert "local snapshot" in result["final_answer"].lower()


def test_robust_v2_live_platform_count_preserves_api_or_caveats(tiny_project: Config, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_v2_llm_plans(
        monkeypatch,
        [
            {
                "route": "EVIDENCE_PIPELINE",
                "evidence_order": "API_FIRST",
                "direct_answer": None,
                "sql": None,
                "api_request": {"method": "GET", "path": "/data/foundation/schemaregistry/tenant/schemas", "params": {}},
                "reason": "live platform count requires API evidence",
            },
            {
                "final_answer": "The live API returned 1 schema.",
                "used_pass_ids": ["api_1"],
                "claimed_facts": [{"claim": "The live API returned 1 schema.", "supporting_pass_ids": ["api_1"]}],
                "caveats_included": [],
            },
        ],
    )
    client = CountingAPIClient()
    executor = AgentExecutor(tiny_project, api_client=client)

    result = executor.run(
        "How many current schemas are in Adobe Experience Platform?",
        strategy=ROBUST_V2,
        query_id="robust_v2_live_count",
    )

    assert result["plan"]["strategy"] == ROBUST_V2
    assert any(row["type"] == "api" for row in result["tool_results"])
    assert client.calls
    api_gate = _checkpoint_output(result, "checkpoint_llm_owned_api_request_gate")
    assert api_gate["passed"] is True
    boundary = _checkpoint_output(result, "checkpoint_llm_owned_generation_boundary")
    assert boundary["backend_semantic_planning_used"] is False


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
    assert "checkpoint_final_answer_claim_extractor" in {
        checkpoint["checkpoint_id"] for checkpoint in result["checkpoints"]
    }
    assert "checkpoint_evidence_grounded_final_answer_verifier" in {
        checkpoint["checkpoint_id"] for checkpoint in result["checkpoints"]
    }
    assert "checkpoint_minimal_correction_feedback_semantic" in {
        checkpoint["checkpoint_id"] for checkpoint in result["checkpoints"]
    }
    assert "checkpoint_semantic_revision_result" in {
        checkpoint["checkpoint_id"] for checkpoint in result["checkpoints"]
    }
    progressive = next(
        checkpoint["output"]
        for checkpoint in result["checkpoints"]
        if checkpoint["checkpoint_id"] == "checkpoint_progressive_evidence_policy"
    )
    assert progressive["entry_action"] == "EVIDENCE_PIPELINE"
    assert progressive["requires_evidence_pipeline"] is True


def test_robust_candidate_progressive_pipeline_blocks_no_tool_for_status_lookup(tiny_project: Config) -> None:
    result = AgentExecutor(tiny_project).run(
        "Show inactive journeys.",
        strategy=ROBUST,
        query_id="robust_progressive_status_lookup",
    )

    assert any(row["type"] in {"sql", "api"} for row in result["tool_results"])
    progressive = next(
        checkpoint["output"]
        for checkpoint in result["checkpoints"]
        if checkpoint["checkpoint_id"] == "checkpoint_progressive_evidence_policy"
    )
    assert progressive["entry_action"] == "EVIDENCE_PIPELINE"
    assert progressive["allowed_early_exit"] is False
    risk_codes = progressive["risk_codes"]
    if isinstance(risk_codes, dict):
        risk_codes = risk_codes.get("items", [])
    assert "STATUS_OR_FILTER_REQUIRES_EVIDENCE" in risk_codes


def test_robust_candidate_does_not_no_tool_mixed_prompt(tiny_project: Config) -> None:
    result = AgentExecutor(tiny_project).run(
        "Explain schemas and list schema records",
        strategy=ROBUST,
        query_id="robust_mixed",
    )

    assert any(row["type"] in {"sql", "api"} for row in result["tool_results"])


def test_robust_candidate_does_not_no_tool_current_evidence_decoy(tiny_project: Config) -> None:
    result = AgentExecutor(tiny_project).run(
        "In one answer, define dataset and provide current evidence where available. Keep the answer evidence-bound.",
        strategy=ROBUST,
        query_id="robust_current_evidence_decoy",
    )

    progressive = next(
        checkpoint["output"]
        for checkpoint in result["checkpoints"]
        if checkpoint["checkpoint_id"] == "checkpoint_progressive_evidence_policy"
    )
    assert progressive["entry_action"] == "EVIDENCE_PIPELINE"
    assert progressive["allowed_early_exit"] is False
    assert any(row["type"] in {"sql", "api"} for row in result["tool_results"])


def test_robust_candidate_does_not_no_tool_meta_phrase_with_data_return(tiny_project: Config) -> None:
    result = AgentExecutor(tiny_project).run(
        "Without using the word list, return available destination records from evidence.",
        strategy=ROBUST,
        query_id="robust_meta_phrase_data_return",
    )

    progressive = next(
        checkpoint["output"]
        for checkpoint in result["checkpoints"]
        if checkpoint["checkpoint_id"] == "checkpoint_progressive_evidence_policy"
    )
    assert progressive["entry_action"] == "EVIDENCE_PIPELINE"
    assert progressive["allowed_early_exit"] is False


def test_robust_candidate_safe_api_probe_runs_one_safe_get(tiny_project: Config) -> None:
    client = CountingAPIClient()
    result = AgentExecutor(tiny_project, api_client=client).run("Tags", strategy=ROBUST, query_id="robust_safe_probe")

    assert len(client.calls) == 1
    assert client.calls[0][0] == "GET"
    assert "{ " not in client.calls[0][1]
    assert [row["type"] for row in result["tool_results"]] == ["api"]
    assert any(checkpoint["checkpoint_id"] == "checkpoint_safe_api_probe" for checkpoint in result["checkpoints"])
    progressive = next(
        checkpoint["output"]
        for checkpoint in result["checkpoints"]
        if checkpoint["checkpoint_id"] == "checkpoint_progressive_evidence_policy"
    )
    assert progressive["entry_action"] == "SAFE_API_PROBE"
    assert progressive["allowed_early_exit"] is True


def test_robust_candidate_safe_api_probe_uses_template_params_and_legacy_answer(tiny_project: Config) -> None:
    client = CountingAPIClient()
    result = AgentExecutor(tiny_project, api_client=client).run(
        "How many tags exist in this sandbox?",
        strategy=ROBUST,
        query_id="robust_safe_probe_tags_count",
    )

    assert len(client.calls) == 1
    assert client.calls[0][2] == {"limit": "20"}
    assert "api" in result["final_answer"].lower()
    assert "tag" in result["final_answer"].lower()
    assert result["final_answer"] != "Count: 1."


def test_robust_candidate_ambiguous_api_family_enters_evidence_pipeline(tiny_project: Config) -> None:
    result = AgentExecutor(tiny_project).run(
        "List current schemas and datasets in the sandbox.",
        strategy=ROBUST,
        query_id="robust_progressive_ambiguous_family",
    )

    progressive = next(
        checkpoint["output"]
        for checkpoint in result["checkpoints"]
        if checkpoint["checkpoint_id"] == "checkpoint_progressive_evidence_policy"
    )
    assert progressive["entry_action"] == "EVIDENCE_PIPELINE"
    assert progressive["allowed_early_exit"] is False


def test_robust_candidate_post_sql_policy_skips_optional_api_after_direct_sql(tiny_project: Config) -> None:
    client = CountingAPIClient()
    executor = AgentExecutor(tiny_project, api_client=client)
    executor.planner.create_plan = _sql_then_optional_api_plan

    result = executor.run("List campaigns", strategy=ROBUST, query_id="robust_post_sql_skip")

    assert [row["type"] for row in result["tool_results"]] == ["sql"]
    assert client.calls == []
    assert any(checkpoint["checkpoint_id"] == "checkpoint_post_sql_deterministic_policy" for checkpoint in result["checkpoints"])
    assert any(checkpoint["checkpoint_id"] == "checkpoint_post_sql_semantic_decision_card" for checkpoint in result["checkpoints"])
    assert any(checkpoint["checkpoint_id"] == "checkpoint_post_sql_execution_verifier" for checkpoint in result["checkpoints"])


def test_robust_candidate_local_snapshot_count_skips_optional_schema_api(tiny_project: Config) -> None:
    client = CountingAPIClient()
    executor = AgentExecutor(tiny_project, api_client=client)
    executor.planner.create_plan = _sql_count_then_optional_schema_api_plan

    result = executor.run(
        "How many schema records are in the local snapshot?",
        strategy=ROBUST,
        query_id="robust_local_snapshot_count",
    )

    assert [row["type"] for row in result["tool_results"]] == ["sql"]
    assert client.calls == []
    assert "local snapshot" in result["final_answer"].lower()
    execution_verifier = next(
        checkpoint["output"]
        for checkpoint in result["checkpoints"]
        if checkpoint["checkpoint_id"] == "checkpoint_post_sql_execution_verifier"
    )
    assert execution_verifier["final_action"] == "SKIP_API"


def test_robust_candidate_skips_llm_answer_when_legacy_answer_is_already_best(
    tiny_project: Config,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = CountingAPIClient()
    executor = AgentExecutor(tiny_project, api_client=client)
    executor.planner.create_plan = _sql_count_then_optional_schema_api_plan

    def fail_if_called(*args, **kwargs):
        raise AssertionError("LLM answer generation should be skipped for complete local SQL answer")

    monkeypatch.setattr("dashagent.executor.generate_evidence_grounded_llm_answer", fail_if_called)

    result = executor.run(
        "How many schema records are in the local snapshot?",
        strategy=ROBUST,
        query_id="robust_local_snapshot_count_no_llm_answer",
    )

    assert "local snapshot" in result["final_answer"].lower()
    answer_diagnostics = next(
        step
        for step in result["trajectory"]["steps"]
        if step.get("kind") == "answer_diagnostics"
    )
    assert answer_diagnostics["llm_answer_generation_skipped"] is True
    assert answer_diagnostics["selected_candidate_type"] in {"LEGACY_SAFE_RENDERER", "DETERMINISTIC_FALLBACK"}


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


def test_answer_slots_use_aggregate_count_value_not_sql_row_count() -> None:
    from dashagent.answer_slot_renderer import render_answer_slots
    from dashagent.answer_slots import extract_answer_slots

    slots = extract_answer_slots(
        "How many schemas do I have?",
        [
            {
                "type": "sql",
                "payload": {
                    "ok": True,
                    "row_count": 1,
                    "rows": [{"count": 74}],
                },
            }
        ],
    )

    rendered = render_answer_slots("How many schemas do I have?", slots)

    assert slots.sql_row_count == 1
    assert slots.counts == [74]
    assert "74" in rendered.answer
    assert "Count: 1" not in rendered.answer


def test_answer_slot_renderer_suppresses_live_empty_caveat_for_direct_sql_count() -> None:
    from dashagent.answer_slot_renderer import render_answer_slots
    from dashagent.answer_slots import extract_answer_slots

    slots = extract_answer_slots(
        "How many schemas do I have?",
        [
            {
                "type": "sql",
                "payload": {
                    "ok": True,
                    "row_count": 1,
                    "rows": [{"count": 74}],
                },
            },
            {
                "type": "api",
                "step": {"family": "schema_list"},
                "payload": {
                    "ok": True,
                    "dry_run": False,
                    "parsed_evidence": {"evidence_state": "live_empty"},
                    "result_preview": {"items": []},
                },
            },
        ],
    )

    rendered = render_answer_slots(
        "How many schemas do I have?",
        slots,
        {"sql": ["SQL_DIRECT_ANSWER"], "api": ["API_LIVE_EMPTY"]},
    )

    assert "74" in rendered.answer
    assert "no matching records" not in rendered.answer.lower()
