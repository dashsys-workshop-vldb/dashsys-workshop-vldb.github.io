from __future__ import annotations

from dashagent.eval_harness import EvalHarness, config_for_applied_trial_strategy
from dashagent.planner import ALL_STRATEGIES, APPLIED_TRIAL_STRATEGIES, STRATEGIES, execution_base_strategy
from scripts.run_dashagent_500_prompt_suite_eval import REAL_MODES, _config_for_real_mode


def test_applied_trial_strategies_are_explicit_only() -> None:
    assert "SQL_FIRST_API_VERIFY" in STRATEGIES
    for strategy in APPLIED_TRIAL_STRATEGIES:
        assert strategy in ALL_STRATEGIES
        assert strategy not in STRATEGIES
        assert execution_base_strategy(strategy) == "SQL_FIRST_API_VERIFY"


def test_applied_trial_strategy_config_excludes_llm_advisor(tiny_project) -> None:
    cfg = config_for_applied_trial_strategy(tiny_project, "COMBINED_SAFE_APPLIED_TRIAL")

    assert cfg.enable_semantic_no_tool_applied_trial is True
    assert cfg.enable_staged_evidence_applied_trial is True
    assert cfg.enable_post_sql_deterministic_applied_trial is True
    assert cfg.post_sql_llm_advisor_enabled is False
    assert cfg.enable_post_sql_llm_advisor_applied_trial is False
    assert cfg.real_behavior_trial_mode == "COMBINED_SAFE_APPLIED_TRIAL"


def test_promotion_candidate_strategy_is_explicit_deterministic_only(tiny_project) -> None:
    strategy = "COMBINED_SAFE_DETERMINISTIC_PROMOTION_CANDIDATE"

    assert strategy in APPLIED_TRIAL_STRATEGIES
    assert strategy in ALL_STRATEGIES
    assert strategy not in STRATEGIES
    assert execution_base_strategy(strategy) == "SQL_FIRST_API_VERIFY"

    cfg = config_for_applied_trial_strategy(tiny_project, strategy)
    assert cfg.enable_staged_evidence_applied_trial is True
    assert cfg.enable_post_sql_deterministic_applied_trial is True
    assert cfg.enable_combined_safe_applied_trial is True
    assert cfg.enable_semantic_no_tool_applied_trial is False
    assert cfg.post_sql_llm_advisor_enabled is False
    assert cfg.enable_post_sql_llm_advisor_applied_trial is False
    assert cfg.real_behavior_trial_mode == strategy


def test_500_runner_promotion_candidate_mode_is_real_deterministic_only() -> None:
    mode = "combined_safe_deterministic_promotion_candidate_real"

    assert mode in REAL_MODES
    cfg = _config_for_real_mode(mode)
    assert cfg.enable_staged_evidence_applied_trial is True
    assert cfg.enable_post_sql_deterministic_applied_trial is True
    assert cfg.enable_combined_safe_applied_trial is True
    assert cfg.enable_semantic_no_tool_applied_trial is False
    assert cfg.post_sql_llm_advisor_enabled is False
    assert cfg.enable_post_sql_llm_advisor_applied_trial is False
    assert cfg.real_behavior_trial_mode == mode


def test_robust_generalized_ablation_strategies_are_explicit_only(tiny_project) -> None:
    strategies = [
        "ROBUST_ABLATION_NO_SEMANTIC_ROUTING",
        "ROBUST_ABLATION_SEMANTIC_ROUTING_ONLY",
        "ROBUST_ABLATION_STAGED_EVIDENCE_ONLY",
        "ROBUST_ABLATION_ANSWER_GROUNDING_ONLY",
        "ROBUST_ABLATION_LLM_ANSWER_NO_VERIFIER",
        "ROBUST_ABLATION_LLM_ANSWER_WITH_VERIFIER",
        "ROBUST_ABLATION_SEMANTIC_ROLE_PARSE_ONLY",
        "ROBUST_ABLATION_NO_LLM_COMPONENTS",
        "ROBUST_ABLATION_FULL_CANDIDATE_NO_LLM_ANSWER",
        "ROBUST_ABLATION_FULL_CANDIDATE_NO_SAFE_API_PROBE",
        "ROBUST_ABLATION_FULL_CANDIDATE_NO_STAGED_POLICY",
        "ROBUST_ABLATION_FULL_CANDIDATE_NO_SEMANTIC_PARSE",
    ]

    for strategy in strategies:
        assert strategy in ALL_STRATEGIES
        assert strategy in APPLIED_TRIAL_STRATEGIES
        assert strategy not in STRATEGIES
        assert execution_base_strategy(strategy) == "SQL_FIRST_API_VERIFY"

    no_semantic = config_for_applied_trial_strategy(tiny_project, "ROBUST_ABLATION_NO_SEMANTIC_ROUTING")
    assert no_semantic.enable_semantic_route_decision_ladder is False
    assert no_semantic.enable_staged_evidence_policy is True
    assert no_semantic.enable_evidence_grounded_llm_answer_generator is True

    no_verifier = config_for_applied_trial_strategy(tiny_project, "ROBUST_ABLATION_LLM_ANSWER_NO_VERIFIER")
    assert no_verifier.enable_evidence_grounded_llm_answer_generator is True
    assert no_verifier.enable_evidence_grounded_final_answer_verifier is False

    with_verifier = config_for_applied_trial_strategy(tiny_project, "ROBUST_ABLATION_LLM_ANSWER_WITH_VERIFIER")
    assert with_verifier.enable_evidence_grounded_final_answer_verifier is True


def test_500_runner_robust_ablation_modes_are_real_modes() -> None:
    modes = {
        "ablation_no_semantic_routing_real",
        "ablation_semantic_routing_only_real",
        "ablation_staged_evidence_only_real",
        "ablation_answer_grounding_only_real",
        "ablation_llm_answer_no_verifier_real",
        "ablation_llm_answer_with_verifier_real",
        "ablation_semantic_role_parse_only_real",
        "ablation_no_llm_components_real",
        "ablation_full_candidate_no_llm_answer_real",
        "ablation_full_candidate_no_safe_api_probe_real",
        "ablation_full_candidate_no_staged_policy_real",
        "ablation_full_candidate_no_semantic_parse_real",
    }

    assert modes <= REAL_MODES
    no_parse = _config_for_real_mode("ablation_full_candidate_no_semantic_parse_real")
    assert no_parse.enable_semantic_parse is False
    no_answer = _config_for_real_mode("ablation_full_candidate_no_llm_answer_real")
    assert no_answer.enable_evidence_grounded_llm_answer_generator is False


def test_eval_harness_runs_applied_trial_alias_without_changing_default(tiny_project) -> None:
    harness = EvalHarness(tiny_project)

    payload = harness.run(
        strategies=[
            "SQL_FIRST_API_VERIFY",
            "COMBINED_SAFE_APPLIED_TRIAL",
            "COMBINED_SAFE_DETERMINISTIC_PROMOTION_CANDIDATE",
        ],
        strict=True,
    )

    assert "COMBINED_SAFE_APPLIED_TRIAL" in payload["strategies"]
    assert "COMBINED_SAFE_DETERMINISTIC_PROMOTION_CANDIDATE" in payload["strategies"]
    assert "COMBINED_SAFE_APPLIED_TRIAL" not in STRATEGIES
    assert "COMBINED_SAFE_DETERMINISTIC_PROMOTION_CANDIDATE" not in STRATEGIES
    assert set(payload["summary"]["by_strategy"]) == {
        "SQL_FIRST_API_VERIFY",
        "COMBINED_SAFE_APPLIED_TRIAL",
        "COMBINED_SAFE_DETERMINISTIC_PROMOTION_CANDIDATE",
    }
    rows = {(row["query_id"], row["strategy"]): row for row in payload["rows"]}
    assert ("tiny_001", "COMBINED_SAFE_APPLIED_TRIAL") in rows
    assert ("tiny_001", "COMBINED_SAFE_DETERMINISTIC_PROMOTION_CANDIDATE") in rows
