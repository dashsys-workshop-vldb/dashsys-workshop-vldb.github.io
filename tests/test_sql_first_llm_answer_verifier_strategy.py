from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from dashagent.config import SQL_FIRST_API_VERIFY_LLM_ANSWER_VERIFIER
from dashagent.eval_harness import config_for_applied_trial_strategy
from dashagent.evidence_grounded_llm_answer_generator import EvidenceGroundedLLMAnswerResult
from dashagent.executor import AgentExecutor
from dashagent.planner import ALL_STRATEGIES, PACKAGED_DEFAULT_STRATEGY, Plan, PlanStep, STRATEGIES, execution_base_strategy


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


@dataclass
class VerificationStub:
    ok: bool
    unsupported_claims_count: int = 0
    unsupported_claims: list[dict[str, Any]] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "unsupported_claims_count": self.unsupported_claims_count,
            "unsupported_claims": self.unsupported_claims or [],
        }


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


def _sql_count_plan(query, routing, metadata, strategy, analysis=None):
    return Plan(
        strategy=strategy,
        rationale="unit SQL count",
        steps=[
            PlanStep(
                action="sql",
                purpose="unit SQL count",
                sql="SELECT COUNT(*) AS count FROM dim_campaign",
            )
        ],
    )


def _answer_diagnostics(result: dict[str, Any]) -> dict[str, Any]:
    return next(step for step in result["trajectory"]["steps"] if step.get("kind") == "answer_diagnostics")


def test_strategy_is_explicit_answer_layer_only(tiny_project) -> None:
    assert PACKAGED_DEFAULT_STRATEGY == "SQL_FIRST_API_VERIFY"
    assert SQL_FIRST_API_VERIFY_LLM_ANSWER_VERIFIER in ALL_STRATEGIES
    assert SQL_FIRST_API_VERIFY_LLM_ANSWER_VERIFIER not in STRATEGIES
    assert execution_base_strategy(SQL_FIRST_API_VERIFY_LLM_ANSWER_VERIFIER) == "SQL_FIRST_API_VERIFY"

    cfg = config_for_applied_trial_strategy(tiny_project, SQL_FIRST_API_VERIFY_LLM_ANSWER_VERIFIER)
    assert cfg.enable_evidence_grounded_answer_builder is True
    assert cfg.enable_evidence_grounded_llm_answer_generator is True
    assert cfg.enable_evidence_grounded_final_answer_verifier is True
    assert cfg.force_evidence_grounded_llm_answer_generation is True
    assert cfg.enable_score_provenance_guard is True
    assert cfg.enable_runtime_leakage_guard is True

    assert cfg.enable_semantic_route_decision_ladder is False
    assert cfg.enable_safe_api_probe is False
    assert cfg.enable_staged_evidence_policy is False
    assert cfg.enable_post_sql_api_decision is False
    assert cfg.enable_post_sql_deterministic_policy is False
    assert cfg.enable_post_sql_llm_semantic_decision is False
    assert cfg.post_sql_llm_advisor_enabled is False
    assert cfg.real_behavior_trial_mode == SQL_FIRST_API_VERIFY_LLM_ANSWER_VERIFIER


def test_strategy_preserves_sql_first_tool_decisions(tiny_project, monkeypatch) -> None:
    def supported_answer(*args, **kwargs):
        return EvidenceGroundedLLMAnswerResult(
            final_answer="Birthday Message is draft; Welcome Journey is published.",
            verification=VerificationStub(ok=True),
            first_pass_ok=True,
            rewrite_attempted=False,
            rewrite_success=False,
            fallback_used=False,
            llm_backend_used=True,
        )

    monkeypatch.setattr("dashagent.executor.generate_evidence_grounded_llm_answer", supported_answer)

    baseline_client = CountingAPIClient()
    baseline = AgentExecutor(tiny_project, api_client=baseline_client)
    baseline.planner.create_plan = _sql_then_api_plan
    baseline_result = baseline.run("List campaigns", strategy="SQL_FIRST_API_VERIFY", query_id="sql_first_path_baseline")

    candidate_client = CountingAPIClient()
    candidate = AgentExecutor(tiny_project, api_client=candidate_client)
    candidate.planner.create_plan = _sql_then_api_plan
    candidate_result = candidate.run(
        "List campaigns",
        strategy=SQL_FIRST_API_VERIFY_LLM_ANSWER_VERIFIER,
        query_id="sql_first_path_llm_answer",
    )

    assert [row["type"] for row in candidate_result["tool_results"]] == [row["type"] for row in baseline_result["tool_results"]]
    assert candidate_client.calls == baseline_client.calls
    assert candidate_result["plan"]["steps"] == baseline_result["plan"]["steps"]

    checkpoints = {checkpoint["checkpoint_id"] for checkpoint in candidate_result["checkpoints"]}
    assert "checkpoint_evidence_grounded_answer_builder" in checkpoints
    assert "checkpoint_answer_candidate_selector" in checkpoints
    assert "checkpoint_semantic_route_decision_ladder" not in checkpoints
    assert "checkpoint_post_sql_deterministic_policy" not in checkpoints
    diagnostics = _answer_diagnostics(candidate_result)
    assert diagnostics["llm_answer_attempted"] is True
    assert diagnostics["llm_answer_generation_skipped"] is False


def test_evidence_card_excludes_benchmark_metadata(tiny_project, monkeypatch) -> None:
    monkeypatch.setattr(
        "dashagent.executor.generate_evidence_grounded_llm_answer",
        lambda *args, **kwargs: EvidenceGroundedLLMAnswerResult(
            final_answer="The database count is 2.",
            verification=VerificationStub(ok=True),
            first_pass_ok=True,
            rewrite_attempted=False,
            rewrite_success=False,
            fallback_used=False,
            llm_backend_used=True,
        ),
    )
    executor = AgentExecutor(tiny_project)
    executor.planner.create_plan = _sql_count_plan

    result = executor.run(
        "How many campaigns are there?",
        strategy=SQL_FIRST_API_VERIFY_LLM_ANSWER_VERIFIER,
        query_id="sql_first_answer_card_leakage",
    )

    diagnostics = _answer_diagnostics(result)
    card_text = str(diagnostics.get("evidence_grounded_answer_builder") or {})
    forbidden = ("gold", "category", "tags", "oracle", "expected_trace")
    assert not any(token in card_text.lower() for token in forbidden)


def test_unsupported_llm_answer_falls_back_to_better_coverage(tiny_project, monkeypatch) -> None:
    def unsupported_answer(*args, **kwargs):
        return EvidenceGroundedLLMAnswerResult(
            final_answer="There are 999 matching campaigns.",
            verification=VerificationStub(
                ok=False,
                unsupported_claims_count=1,
                unsupported_claims=[{"type": "COUNT", "value": "999"}],
            ),
            first_pass_ok=False,
            rewrite_attempted=True,
            rewrite_success=False,
            fallback_used=True,
            llm_backend_used=True,
        )

    monkeypatch.setattr("dashagent.executor.generate_evidence_grounded_llm_answer", unsupported_answer)
    executor = AgentExecutor(tiny_project)
    executor.planner.create_plan = _sql_count_plan

    result = executor.run(
        "How many campaigns are there?",
        strategy=SQL_FIRST_API_VERIFY_LLM_ANSWER_VERIFIER,
        query_id="sql_first_answer_unsupported_fallback",
    )

    diagnostics = _answer_diagnostics(result)
    selector = diagnostics["answer_candidate_selector"]
    assert selector["selected_source"] != "LLM_EVIDENCE_GROUNDED"
    assert selector["unsupported_claims"] == 0
    assert "999" not in result["final_answer"]
    assert "2" in result["final_answer"]


def test_sql_first_tool_results_build_non_empty_answer_card(tiny_project) -> None:
    executor = AgentExecutor(tiny_project)
    executor.planner.create_plan = _sql_count_plan

    result = executor.run(
        "How many campaigns are there?",
        strategy=SQL_FIRST_API_VERIFY_LLM_ANSWER_VERIFIER,
        query_id="sql_first_answer_card_non_empty",
    )

    diagnostics = _answer_diagnostics(result)
    card = diagnostics["evidence_grounded_answer_builder"]
    renderer = card["renderer"]
    assert card["answer"]
    assert renderer["rendered_fields"]
    assert diagnostics["answer_candidate_selector"]["candidates"]
