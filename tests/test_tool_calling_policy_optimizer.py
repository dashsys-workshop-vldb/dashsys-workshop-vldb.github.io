from __future__ import annotations

import json
import re
from pathlib import Path

from dashagent.llm_tool_agent import _allowed_tool_schemas_for_route, _baseline_tool_schemas
from dashagent.prompt_router import API_REQUIRED, API_SKIP, LOCAL_DB_ONLY, PromptRouteDecision, SQL_PLUS_API
from scripts.run_tool_calling_policy_optimizer import run_tool_calling_policy_optimizer


SECRET_VALUE_RE = re.compile(
    r"sk-[A-Za-z0-9_-]{12,}"
    r"|Bearer\s+[A-Za-z0-9._-]{12,}"
    r"|Authorization:\s*Bearer\s+[A-Za-z0-9._-]+"
    r"|[A-Za-z0-9]{3}\*\*\*",
    re.IGNORECASE,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _seed_optimizer_inputs(outputs: Path) -> None:
    reports = outputs / "reports"
    _write_json(
        outputs / "eval_results_strict.json",
        {
            "rows": [
                {
                    "query_id": "example_001",
                    "strategy": "SQL_FIRST_API_VERIFY",
                    "correctness_score": 0.68,
                    "final_score": 0.6553,
                    "tool_call_count": 1.5,
                    "estimated_tokens": 835,
                    "runtime": 0.012,
                }
            ],
            "summary": {
                "by_strategy": {
                    "SQL_FIRST_API_VERIFY": {
                        "avg_correctness_score": 0.6805,
                        "avg_final_score": 0.6553,
                        "avg_sql_score": 0.9333,
                        "avg_api_score": 0.9791,
                        "avg_answer_score": 0.3199,
                        "avg_tool_call_count": 1.4571,
                        "avg_estimated_tokens": 834.6,
                        "avg_runtime": 0.0123,
                        "avg_preprocessing_time": 0.003,
                    }
                }
            },
        },
    )
    _write_json(
        reports / "correctness_efficiency_scorecard.json",
        {
            "baseline": {
                "strategy": "SQL_FIRST_API_VERIFY",
                "correctness_score": 0.6805,
                "strict_final_score": 0.6553,
                "sql_score": 0.9333,
                "api_score": 0.9791,
                "response_score": 0.3199,
                "tool_calls": 1.4571,
                "total_tokens": 834.6,
                "wall_time_seconds": 0.0123,
                "end_to_end_time_seconds": 0.0174,
                "hidden_style_status": "48/48",
                "final_submission_ready": True,
                "direct_http_hits": 0,
            },
            "variants": [
                {
                    "variant_id": "combined_safe_tool_policy",
                    "correctness_delta": 0.0,
                    "strict_score_delta": 0.0,
                    "promotion_candidate_status": "efficiency_candidate_needs_strict_validation",
                    "pareto_dominates_baseline": True,
                    "efficiency": {
                        "tool_calls_delta": -2.0,
                        "total_tokens_delta": -120.0,
                        "wall_time_delta": -0.02,
                        "end_to_end_time_delta": -0.02,
                        "tool_calls": 1.0,
                        "total_tokens": 714.6,
                        "wall_time_seconds": 0.001,
                        "end_to_end_time_seconds": 0.001,
                    },
                    "safety": {
                        "direct_http_hits": 0,
                        "unsupported_claim_delta": 0,
                        "high_scoring_rows_hurt": 0,
                        "final_submission_format_changed": False,
                        "hardcoding_detected": False,
                    },
                }
            ],
        },
    )
    _write_json(
        reports / "generated_prompt_suite_local_diagnostic.json",
        {
            "diagnostic_only": True,
            "total_prompts": 250,
            "executed_prompts": 250,
            "runtime_pass_count": 250,
            "validation_fail_count": 0,
        },
    )
    _write_json(
        reports / "sdk_usage_audit.json",
        {"summary": {"runtime_llm_direct_http_hits": 0}},
    )
    _write_json(
        reports / "live_api_readiness_smoke.json",
        {"summary": {"live_success_count": 0}, "failure_counts": {"auth_error": 3}},
    )
    _write_json(
        reports / "system_summary.json",
        {
            "preferred_strategy": "SQL_FIRST_API_VERIFY",
            "packaged_strict_score": 0.6553,
            "hidden_style": {"label": "48/48", "passed": 48, "total": 48},
            "final_submission_ready": True,
        },
    )


def test_tool_calling_policy_optimizer_generates_search_reports(tiny_project):
    _seed_optimizer_inputs(tiny_project.outputs_dir)

    payload = run_tool_calling_policy_optimizer(tiny_project)
    reports = tiny_project.outputs_dir / "reports"
    for stem in [
        "tool_calling_policy_optimizer",
        "tool_calling_objective_functions",
        "tool_calling_policy_search_results",
        "tool_calling_compiled_policy_candidate",
        "tool_calling_policy_promotion_decision",
    ]:
        assert (reports / f"{stem}.json").exists(), stem
        assert (reports / f"{stem}.md").exists(), stem

    optimizer = payload["optimizer"]
    assert optimizer["diagnostic_only"] is True
    assert optimizer["official_overall_score_claim"] is False
    assert optimizer["baseline"]["packaged_strategy"] == "SQL_FIRST_API_VERIFY"
    assert optimizer["search_space"]["policy_count"] > 1000
    assert {"allowed_tools_policy", "tool_choice_policy", "parallel_tool_calls_policy"} <= set(
        optimizer["search_space"]["dimensions"]
    )
    assert optimizer["sample_policies"]
    assert all(row["policy_id"].startswith("tcp_") for row in optimizer["sample_policies"])
    assert all("query_id" not in row["trigger_conditions"] for row in optimizer["sample_policies"])

    objectives = payload["objectives"]
    assert objectives["organizer_weights_known"] is False
    assert objectives["official_overall_score_claim"] is False
    assert {"correctness_dominant", "balanced", "efficiency_sensitive", "no_regression_efficiency", "pareto_frontier"} <= set(
        objectives["composite_scenarios"]
    )

    search = payload["search_results"]
    assert search["total_policies_evaluated"] == optimizer["search_space"]["policy_count"]
    assert search["pareto_frontier_policies"]
    assert search["best_policy_per_objective"]["no_regression_efficiency"]["policy_id"].startswith("tcp_")
    assert search["best_speed_only_candidate"]["strict_score_delta"] == 0.0
    assert search["best_speed_only_candidate"]["efficiency"]["total_tokens_delta"] < 0
    assert search["generated_prompts_diagnostic_only"] is True

    candidate = payload["compiled_candidate"]
    assert candidate["recommendation"] == "promote_candidate"
    assert candidate["uses_query_ids"] is False
    assert candidate["uses_prompt_ids"] is False
    assert candidate["uses_exact_prompt_strings"] is False
    assert candidate["deterministic_rules"]
    assert any("live_success_count=0" in rule for rule in candidate["deterministic_rules"])

    decision = payload["promotion_decision"]
    assert decision["decision"] in {"promoted_existing_policy", "promote_candidate"}
    assert decision["runtime_change_applied"] in {False, True}
    assert decision["strict_score_before"] == decision["strict_score_after_projected"]
    assert decision["direct_http_hits"] == 0
    assert decision["final_submission_ready"] is True
    assert decision["official_overall_score_claim"] is False
    assert not (tiny_project.outputs_dir / "final_submission").exists()

    combined = "\n".join((reports / f"{stem}.json").read_text(encoding="utf-8") for stem in [
        "tool_calling_policy_optimizer",
        "tool_calling_objective_functions",
        "tool_calling_policy_search_results",
        "tool_calling_compiled_policy_candidate",
        "tool_calling_policy_promotion_decision",
    ])
    assert not SECRET_VALUE_RE.search(combined)


def test_compiled_policy_hides_optional_api_when_live_success_zero():
    tools = _baseline_tool_schemas()
    optional_api_route = PromptRouteDecision(
        mode=SQL_PLUS_API,
        reason="unit-test",
        confidence=0.9,
        requires_database=True,
        requires_api=True,
        api_policy="API_OPTIONAL",
    )
    api_required_route = PromptRouteDecision(
        mode=SQL_PLUS_API,
        reason="unit-test",
        confidence=0.9,
        requires_database=True,
        requires_api=True,
        api_policy=API_REQUIRED,
    )
    sql_only_route = PromptRouteDecision(
        mode=LOCAL_DB_ONLY,
        reason="unit-test",
        confidence=0.9,
        requires_database=True,
        requires_api=False,
        api_policy=API_SKIP,
    )

    assert [tool["function"]["name"] for tool in _allowed_tool_schemas_for_route(tools, sql_only_route)] == ["execute_sql"]
    assert [tool["function"]["name"] for tool in _allowed_tool_schemas_for_route(tools, optional_api_route, live_success_count=0)] == ["execute_sql"]
    assert [tool["function"]["name"] for tool in _allowed_tool_schemas_for_route(tools, optional_api_route, live_success_count=1)] == [
        "execute_sql",
        "call_api",
    ]
    assert [tool["function"]["name"] for tool in _allowed_tool_schemas_for_route(tools, api_required_route, live_success_count=0)] == [
        "execute_sql",
        "call_api",
    ]
