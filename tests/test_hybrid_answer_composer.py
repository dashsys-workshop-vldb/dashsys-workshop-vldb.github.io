from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from dashagent.answer_slots import AnswerSlots
from dashagent.config import SQL_FIRST_API_VERIFY_HYBRID_ANSWER
from dashagent.executor import AgentExecutor
from dashagent.hybrid_answer_composer import compose_hybrid_answer
from dashagent.planner import ALL_STRATEGIES, PACKAGED_DEFAULT_STRATEGY, Plan, PlanStep, STRATEGIES, execution_base_strategy
from dashagent.eval_harness import config_for_applied_trial_strategy


class CountingAPIClient:
    dry_run = False

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

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
                "ids": ["schema-1"],
                "names": ["Profile Schema"],
                "counts": {"items": 1},
            },
            "result_preview": {"items": [{"id": "schema-1", "name": "Profile Schema"}]},
        }


class FakeConceptClient:
    def __init__(self, answer: str) -> None:
        self.answer = answer

    def complete(self, messages):
        return self.answer


@dataclass
class FakeAnswerCard:
    answer: str

    def to_dict(self) -> dict[str, Any]:
        return {"answer": self.answer}


def _slots(query: str, **kwargs) -> AnswerSlots:
    defaults = {"query": query, "answer_family": "journey_campaign"}
    defaults.update(kwargs)
    return AnswerSlots(**defaults)


def _sql_then_api_plan(query, routing, metadata, strategy, analysis=None):
    return Plan(
        strategy=strategy,
        rationale="unit SQL_FIRST evidence path",
        steps=[
            PlanStep(
                action="sql",
                purpose="unit SQL list",
                sql="SELECT campaign_id AS id, name, status FROM dim_campaign ORDER BY campaign_id",
            ),
            PlanStep(
                action="api",
                purpose="unit SQL_FIRST API verification",
                method="GET",
                url="/data/foundation/schemaregistry/tenant/schemas",
                params={},
            ),
        ],
    )


@dataclass
class VerificationStub:
    ok: bool
    unsupported_claims_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "unsupported_claims_count": self.unsupported_claims_count}


def test_mixed_prompt_includes_concept_and_canonical_data() -> None:
    prompt = "Explain what inactive journey means and show inactive journeys."
    slots = _slots(
        prompt,
        entity_names=["Birthday Message", "Gold Tier Welcome Email"],
        statuses=["draft", "inactive"],
        first_rows=[
            {"name": "Birthday Message", "status": "draft"},
            {"name": "Gold Tier Welcome Email", "status": "inactive"},
        ],
    )

    result = compose_hybrid_answer(
        prompt,
        slots=slots,
        legacy_answer="Legacy answer.",
        llm_client=FakeConceptClient("An inactive journey is not currently active or running."),
    )

    assert result.selected_source == "HYBRID_MIXED"
    assert result.intent.answer_intent == "MIXED"
    assert result.final_answer.startswith("An inactive journey is not currently active or running.")
    assert "Birthday Message" in result.final_answer
    assert "Gold Tier Welcome Email" in result.final_answer


def test_unsupported_concept_claim_falls_back_to_legacy() -> None:
    prompt = "What is a schema?"
    slots = _slots(prompt)

    result = compose_hybrid_answer(
        prompt,
        slots=slots,
        legacy_answer="A schema defines the structure of data.",
        llm_client=FakeConceptClient("There are 999 schemas in Adobe Experience Platform."),
    )

    assert result.selected_source == "LEGACY_SAFE_RENDERER"
    assert result.fallback_used is True
    assert result.final_answer == "A schema defines the structure of data."


def test_unsupported_legacy_fallback_prefers_verified_grounded_answer() -> None:
    prompt = "What is a schema?"
    slots = _slots(prompt)

    result = compose_hybrid_answer(
        prompt,
        slots=slots,
        answer_card=FakeAnswerCard("A schema defines the structure of data."),
        legacy_answer="There are 75 schema records in the local snapshot.",
        llm_client=FakeConceptClient("There are 999 schemas in Adobe Experience Platform."),
    )

    assert result.selected_source == "DETERMINISTIC_FALLBACK"
    assert result.fallback_used is True
    assert result.verification.ok is True
    assert result.final_answer == "A schema defines the structure of data."


def test_hybrid_strategy_is_explicit_answer_layer_only(tiny_project) -> None:
    assert PACKAGED_DEFAULT_STRATEGY == "SQL_FIRST_API_VERIFY"
    assert SQL_FIRST_API_VERIFY_HYBRID_ANSWER in ALL_STRATEGIES
    assert SQL_FIRST_API_VERIFY_HYBRID_ANSWER not in STRATEGIES
    assert execution_base_strategy(SQL_FIRST_API_VERIFY_HYBRID_ANSWER) == "SQL_FIRST_API_VERIFY"

    cfg = config_for_applied_trial_strategy(tiny_project, SQL_FIRST_API_VERIFY_HYBRID_ANSWER)
    assert cfg.enable_hybrid_answer_composer is True
    assert cfg.enable_evidence_grounded_answer_builder is True
    assert cfg.enable_evidence_grounded_final_answer_verifier is True
    assert cfg.enable_evidence_grounded_llm_answer_generator is False
    assert cfg.force_evidence_grounded_llm_answer_generation is False
    assert cfg.enable_semantic_route_decision_ladder is False
    assert cfg.enable_safe_api_probe is False
    assert cfg.enable_staged_evidence_policy is False
    assert cfg.enable_post_sql_api_decision is False
    assert cfg.real_behavior_trial_mode == SQL_FIRST_API_VERIFY_HYBRID_ANSWER


def test_hybrid_strategy_preserves_sql_first_tool_decisions(tiny_project) -> None:
    baseline_client = CountingAPIClient()
    baseline = AgentExecutor(tiny_project, api_client=baseline_client)
    baseline.planner.create_plan = _sql_then_api_plan
    baseline_result = baseline.run("List campaigns", strategy="SQL_FIRST_API_VERIFY", query_id="hybrid_path_baseline")

    candidate_client = CountingAPIClient()
    candidate = AgentExecutor(tiny_project, api_client=candidate_client)
    candidate.planner.create_plan = _sql_then_api_plan
    candidate_result = candidate.run(
        "List campaigns",
        strategy=SQL_FIRST_API_VERIFY_HYBRID_ANSWER,
        query_id="hybrid_answer_path",
    )

    assert [row["type"] for row in candidate_result["tool_results"]] == [row["type"] for row in baseline_result["tool_results"]]
    assert candidate_client.calls == baseline_client.calls
    assert candidate_result["plan"]["steps"] == baseline_result["plan"]["steps"]
    diagnostics = next(step for step in candidate_result["trajectory"]["steps"] if step.get("kind") == "answer_diagnostics")
    assert diagnostics["hybrid_answer_composer"]["selected_source"] in {"HYBRID_CANONICAL_DATA", "LEGACY_SAFE_RENDERER"}


def test_hybrid_answer_context_excludes_benchmark_metadata(tiny_project) -> None:
    executor = AgentExecutor(tiny_project)
    executor.planner.create_plan = lambda query, routing, metadata, strategy, analysis=None: Plan(
        strategy=strategy,
        rationale="unit count",
        steps=[PlanStep(action="sql", purpose="unit SQL count", sql="SELECT COUNT(*) AS count FROM dim_campaign")],
    )

    result = executor.run(
        "How many campaigns are there?",
        strategy=SQL_FIRST_API_VERIFY_HYBRID_ANSWER,
        query_id="hybrid_answer_card_leakage",
    )

    diagnostics = next(step for step in result["trajectory"]["steps"] if step.get("kind") == "answer_diagnostics")
    payload = str(diagnostics.get("hybrid_answer_composer") or {})
    forbidden = ("gold", "category", "tags", "oracle", "expected_trace")
    assert not any(token in payload.lower() for token in forbidden)
