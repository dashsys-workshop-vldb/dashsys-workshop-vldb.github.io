from __future__ import annotations

import json
from pathlib import Path

from scripts.generate_dashagent_500_prompt_suite import CATEGORY_TARGETS, generate_suite
from scripts.run_dashagent_500_prompt_suite_eval import REAL_MODES, RECOGNIZED_MODES, SIMULATED_MODES, run_suite_eval
from scripts.validate_dashagent_500_prompt_suite import validate_suite


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_generate_suite_writes_500_runtime_and_gold_rows(tmp_path: Path) -> None:
    out = tmp_path / "benchmarks"
    report_dir = tmp_path / "reports"

    manifest = generate_suite(out_dir=out, report_dir=report_dir, seed=20260525)

    runtime_rows = _read_jsonl(out / "dashagent_500_prompt_suite.jsonl")
    gold_rows = _read_jsonl(out / "dashagent_500_prompt_suite_gold.jsonl")
    assert manifest["total_prompts"] == 500
    assert len(runtime_rows) == 500
    assert len(gold_rows) == 500
    assert manifest["category_distribution"] == CATEGORY_TARGETS
    assert {row["prompt_id"] for row in runtime_rows} == {row["prompt_id"] for row in gold_rows}
    assert not ({"gold_answer", "oracle_evidence", "expected_observable_trace"} & runtime_rows[0].keys())
    assert {"gold_answer", "oracle_evidence", "expected_observable_trace", "grading_rubric"} <= gold_rows[0].keys()


def test_validation_rejects_gold_leakage_and_accepts_generated_suite(tmp_path: Path) -> None:
    out = tmp_path / "benchmarks"
    report_dir = tmp_path / "reports"
    generate_suite(out_dir=out, report_dir=report_dir, seed=20260525)

    ok = validate_suite(suite_path=out / "dashagent_500_prompt_suite.jsonl", gold_path=out / "dashagent_500_prompt_suite_gold.jsonl", manifest_path=out / "dashagent_500_prompt_suite_manifest.json", report_dir=report_dir)
    assert ok["ok"] is True
    assert ok["total_prompts"] == 500
    assert ok["runtime_gold_field_leak_count"] == 0
    assert ok["private_chain_of_thought_count"] == 0
    assert ok["oracle_sql_reexecution_checked"] > 0
    assert ok["endpoint_catalog_validation_failures"] == []
    assert ok["synthetic_prompt_artifact_count"] > 0

    leaked = _read_jsonl(out / "dashagent_500_prompt_suite.jsonl")
    leaked[0]["gold_answer"] = "leak"
    (out / "dashagent_500_prompt_suite.jsonl").write_text("\n".join(json.dumps(row) for row in leaked) + "\n", encoding="utf-8")
    bad = validate_suite(suite_path=out / "dashagent_500_prompt_suite.jsonl", gold_path=out / "dashagent_500_prompt_suite_gold.jsonl", manifest_path=out / "dashagent_500_prompt_suite_manifest.json", report_dir=report_dir)
    assert bad["ok"] is False
    assert bad["runtime_gold_field_leak_count"] == 1


def test_suite_contains_required_semantic_and_post_sql_stress_cases(tmp_path: Path) -> None:
    out = tmp_path / "benchmarks"
    report_dir = tmp_path / "reports"
    generate_suite(out_dir=out, report_dir=report_dir, seed=20260525)
    gold = _read_jsonl(out / "dashagent_500_prompt_suite_gold.jsonl")
    tags = {tag for row in _read_jsonl(out / "dashagent_500_prompt_suite.jsonl") for tag in row.get("tags", [])}

    assert {"anti_hallucination_no_tool_conflict", "anti_hallucination_unknown_capability", "mixed_no_tool_block", "low_low_safe_direct", "low_low_safe_api_probe", "post_sql_advisor_accept", "post_sql_advisor_block", "invalid_json_fallback"} <= tags
    assert any(step["stage"] == "objective_features" for row in gold for step in row["expected_observable_trace"])
    assert any((row["oracle_evidence"] or {}).get("oracle_sql") for row in gold)
    assert any((row["oracle_evidence"] or {}).get("oracle_api_endpoint") for row in gold)


class _FakeExecutor:
    def __init__(self, *, shadow: bool = False) -> None:
        self.shadow = shadow
        self.calls: list[dict] = []

    def run(self, query: str, *, strategy: str, query_id: str, output_dir: Path) -> dict:
        self.calls.append({"query": query, "strategy": strategy, "query_id": query_id, "output_dir": output_dir})
        checkpoints = [
            {
                "name": "checkpoint_objective_prompt_features",
                "output": {"cue": ["DEF"], "domain": ["SCHEMA"], "flags": ["DOMAIN_WITH_DEF_CUE"]},
            },
            {
                "name": "checkpoint_13_tool_execution",
                "output": {"tool_result_count": 0},
            },
            {
                "name": "checkpoint_15_answer_slots",
                "output": {"slots": {}},
            },
            {
                "name": "checkpoint_16_answer_verification",
                "output": {"unsupported_claims_count": 0, "verifier_passed": True},
            },
        ]
        if self.shadow:
            checkpoints.extend(
                [
                    {"name": "checkpoint_semantic_route_decision_ladder", "output": {"action": "LLM_SAFE_DIRECT", "shadow_only": True}},
                    {"name": "checkpoint_initial_evidence_branch_policy", "output": {"first_branch": "NO_TOOL", "shadow_only": True}},
                    {
                        "name": "checkpoint_post_sql_llm_advisor",
                        "output": {
                            "mode": "CAVEAT_ONLY",
                            "source": "DETERMINISTIC_FALLBACK",
                            "codes": ["POST_SQL_LLM_ADVISOR_DISABLED"],
                            "shadow_only": True,
                        },
                    },
                    {
                        "name": "checkpoint_post_sql_api_call_verifier",
                        "output": {
                            "final_action": "CAVEAT_ONLY",
                            "source": "DETERMINISTIC_FALLBACK",
                            "shadow_only": True,
                        },
                    },
                ]
            )
        trajectory = {
            "query_id": query_id,
            "steps": [{"name": "route", "output": {"route_type": "LLM_DIRECT"}}],
            "checkpoints": checkpoints,
        }
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        (Path(output_dir) / "trajectory.json").write_text(json.dumps(trajectory), encoding="utf-8")
        return {
            "query_id": query_id,
            "query": query,
            "strategy": strategy,
            "output_dir": str(output_dir),
            "metadata": {},
            "plan": {"steps": []},
            "tool_results": [],
            "final_answer": "A schema is a conceptual data structure.",
            "checkpoints": checkpoints,
            "trajectory": trajectory,
        }


def test_eval_runner_recognizes_latest_modes_and_isolates_real_agent_runtime(tmp_path: Path) -> None:
    out = tmp_path / "benchmarks"
    report_dir = tmp_path / "reports"
    eval_dir = tmp_path / "eval"
    generate_suite(out_dir=out, report_dir=report_dir, seed=20260525)

    assert {
        "packaged_baseline",
        "semantic_routing_shadow",
        "staged_evidence_shadow",
        "post_sql_api_decision_shadow",
        "latest_applied_trial",
        "latest_full_trial",
    } <= SIMULATED_MODES <= RECOGNIZED_MODES
    assert {"packaged_baseline_real", "latest_shadow_real", "latest_applied_real_trial"} <= REAL_MODES <= RECOGNIZED_MODES

    fake_executor = _FakeExecutor()

    result = run_suite_eval(
        suite_path=out / "dashagent_500_prompt_suite.jsonl",
        gold_path=out / "dashagent_500_prompt_suite_gold.jsonl",
        output_dir=eval_dir,
        report_dir=report_dir,
        modes=["packaged_baseline_real"],
        limit=3,
        seed=20260525,
        clean=True,
        engine="real_agent",
        executor_factory=lambda config=None: fake_executor,
    )

    assert result["eval_engine"] == "real_agent"
    assert result["real_agent_execution"] is True
    assert result["synthetic_sql_results_used"] is False
    assert result["runtime_used_category_tags_for_decision"] is False
    assert result["agent_executor_used"] is True
    assert result["prompt_count"] == 3
    assert set(result["modes"]) == {"packaged_baseline_real"}
    assert len(fake_executor.calls) == 3
    runtime_rows = {row["prompt_id"]: row for row in _read_jsonl(out / "dashagent_500_prompt_suite.jsonl")}
    for call in fake_executor.calls:
        original_row = runtime_rows[call["query_id"]]
        assert call["query"] == original_row["prompt"]
        assert call["strategy"] == "SQL_FIRST_API_VERIFY"
        assert "category" not in call
        assert "tags" not in call
        assert "oracle_sql" not in call
    assert (eval_dir / "packaged_baseline_real").is_dir()
    assert len(list((eval_dir / "packaged_baseline_real").glob("*/trajectory.json"))) == 3
    grade_record = json.loads(next((eval_dir / "packaged_baseline_real").glob("*/benchmark_grade.json")).read_text(encoding="utf-8"))
    assert set(grade_record["runtime_input"]) == {"prompt_id", "prompt"}
    assert grade_record["gold_visible_to_runtime"] is False
    assert grade_record["category_tags_domain_visible_to_runtime"] is False


def test_simulated_eval_is_explicitly_marked_and_separate(tmp_path: Path) -> None:
    out = tmp_path / "benchmarks"
    report_dir = tmp_path / "reports"
    eval_dir = tmp_path / "eval_sim"
    generate_suite(out_dir=out, report_dir=report_dir, seed=20260525)

    result = run_suite_eval(
        suite_path=out / "dashagent_500_prompt_suite.jsonl",
        gold_path=out / "dashagent_500_prompt_suite_gold.jsonl",
        output_dir=eval_dir,
        report_dir=report_dir,
        modes=["packaged_baseline", "latest_applied_trial"],
        limit=4,
        seed=20260525,
        clean=True,
        engine="simulated_trace",
    )

    assert result["eval_engine"] == "simulated_trace"
    assert result["simulated_trace_only"] is True
    assert result["real_agent_execution"] is False
    assert result["synthetic_sql_results_used"] is True
    assert result["runtime_used_category_tags_for_decision"] is True
    assert result["agent_executor_used"] is False
    assert (report_dir / "dashagent_500_prompt_suite_eval_simulated.json").is_file()


def test_unavailable_applied_real_trial_is_excluded_and_has_no_fake_zero_scores(tmp_path: Path) -> None:
    out = tmp_path / "benchmarks"
    report_dir = tmp_path / "reports"
    eval_dir = tmp_path / "eval"
    generate_suite(out_dir=out, report_dir=report_dir, seed=20260525)

    result = run_suite_eval(
        suite_path=out / "dashagent_500_prompt_suite.jsonl",
        gold_path=out / "dashagent_500_prompt_suite_gold.jsonl",
        output_dir=eval_dir,
        report_dir=report_dir,
        modes=["packaged_baseline_real", "latest_applied_real_trial"],
        limit=2,
        seed=20260525,
        clean=True,
        engine="real_agent",
        executor_factory=lambda config=None: _FakeExecutor(),
    )

    unavailable = result["mode_summary"]["latest_applied_real_trial"]
    assert unavailable["available"] is False
    assert unavailable["excluded_from_comparison"] is True
    assert unavailable["latest_applied_real_trial_unavailable"] is True
    for key in [
        "overall_score",
        "combined_diagnostic_score",
        "behavior_score",
        "trace_observability_score",
        "route_accuracy",
        "sql_required_used_accuracy",
        "api_required_used_accuracy",
        "expected_observable_trace_score",
        "runtime_ms",
    ]:
        assert unavailable.get(key) is None
    assert result["comparison"]["latest_unavailable"] is True
    assert result["comparison"]["excluded_from_comparison"] is True
    gate = result["gate"]
    assert gate["latest_trial_score"] is None
    assert gate["route_trace_accuracy"] is None
    assert gate["runtime_cost_acceptable"] is None
    assert gate["latest_applied_real_trial_available"] is False
    assert gate["applied_behavior_changed"] is False
    assert gate["recommendation"] in {"latest_applied_real_trial_unavailable_keep_shadow", "improve_post_sql_policy_before_promotion"}


def test_shadow_real_separates_behavior_from_trace_observability(tmp_path: Path) -> None:
    out = tmp_path / "benchmarks"
    report_dir = tmp_path / "reports"
    eval_dir = tmp_path / "eval"
    generate_suite(out_dir=out, report_dir=report_dir, seed=20260525)

    def factory(config=None):
        return _FakeExecutor(shadow=bool(getattr(config, "enable_semantic_route_decision_ladder", False)))

    result = run_suite_eval(
        suite_path=out / "dashagent_500_prompt_suite.jsonl",
        gold_path=out / "dashagent_500_prompt_suite_gold.jsonl",
        output_dir=eval_dir,
        report_dir=report_dir,
        modes=["packaged_baseline_real", "latest_shadow_real"],
        limit=2,
        seed=20260525,
        clean=True,
        engine="real_agent",
        executor_factory=factory,
    )

    baseline = result["mode_summary"]["packaged_baseline_real"]
    shadow = result["mode_summary"]["latest_shadow_real"]
    comparison = result["shadow_comparison"]
    assert "behavior_score" in baseline
    assert "trace_observability_score" in baseline
    assert "combined_diagnostic_score" in baseline
    assert result["grading_type"] == "heuristic_internal_gold"
    assert result["organizer_equivalent"] is False
    assert shadow["behavior_changed"] is False
    assert comparison["tool_behavior_changed_count"] == 0
    assert comparison["final_answer_changed_count"] == 0
    assert comparison["behavior_score_delta"] == 0.0
    assert comparison["trace_observability_delta"] > 0
    assert comparison["trace_observability_improved"] is True


def test_shadow_real_advisor_checkpoint_does_not_count_as_llm_invocation(tmp_path: Path) -> None:
    out = tmp_path / "benchmarks"
    report_dir = tmp_path / "reports"
    eval_dir = tmp_path / "eval"
    generate_suite(out_dir=out, report_dir=report_dir, seed=20260525)

    result = run_suite_eval(
        suite_path=out / "dashagent_500_prompt_suite.jsonl",
        gold_path=out / "dashagent_500_prompt_suite_gold.jsonl",
        output_dir=eval_dir,
        report_dir=report_dir,
        modes=["latest_shadow_real"],
        limit=2,
        seed=20260525,
        clean=True,
        engine="real_agent",
        executor_factory=lambda config=None: _FakeExecutor(shadow=True),
    )

    shadow = result["mode_summary"]["latest_shadow_real"]
    assert shadow["post_sql_advisor_checkpoint_present_count"] == 2
    assert shadow["post_sql_llm_advisor_actual_call_count"] == 0
    assert shadow["post_sql_advisor_invoked"] == 0
    assert shadow["post_sql_llm_advice_blocked_count"] == 0
    assert shadow["post_sql_advisor_blocked"] == 0
    assert shadow["post_sql_deterministic_fallback_count"] == 2
    assert shadow["post_sql_advisor_disabled_or_fallback_count"] == 2
    assert shadow["post_sql_advisor_source_counts"]["DETERMINISTIC_FALLBACK"] == 2
