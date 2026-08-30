from __future__ import annotations

import json

from dashagent.targeted_candidate_generator import TargetedCandidate, apply_leakage_checks, generate_targeted_candidates
from scripts.run_score075_candidate_generation_eval import run_score075_candidate_generation_eval


def _baseline_trajectory(sql: str = "SELECT campaign_id, name FROM dim_campaign") -> dict:
    return {
        "query_id": "tiny_001",
        "original_query": "How many campaigns are there?",
        "strategy": "SQL_FIRST_API_VERIFY",
        "steps": [{"kind": "sql_call", "sql": sql, "result": {"ok": True, "rows": []}}],
        "final_answer": "The result is unavailable in dry-run mode.",
        "tool_call_count": 1,
        "estimated_tokens": 100,
        "runtime": 0.01,
    }


def _write_eval_inputs(config) -> None:
    output_dir = config.outputs_dir / "eval" / "tiny_001" / "sql_first_api_verify"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "trajectory.json").write_text(json.dumps(_baseline_trajectory()), encoding="utf-8")
    (output_dir / "metadata.json").write_text(json.dumps({"query_id": "tiny_001"}), encoding="utf-8")
    (output_dir / "filled_system_prompt.txt").write_text("prompt", encoding="utf-8")
    strict = {
        "rows": [
            {
                "query_id": "tiny_001",
                "query": "How many campaigns are there?",
                "strategy": "SQL_FIRST_API_VERIFY",
                "output_dir": str(output_dir),
                "final_score": 0.5,
                "correctness_score": 0.55,
                "estimated_tokens": 100,
                "runtime": 0.01,
                "tool_call_count": 1,
            }
        ],
        "summary": {
            "by_strategy": {
                "SQL_FIRST_API_VERIFY": {
                    "count": 1,
                    "avg_final_score": 0.5,
                    "avg_correctness_score": 0.55,
                    "avg_estimated_tokens": 100,
                    "avg_runtime": 0.01,
                    "avg_tool_call_count": 1,
                }
            }
        },
    }
    mining = {
        "rows": [
            {
                "query_id": "tiny_001",
                "likely_failure_type": "wrong_count_vs_list",
                "improvement_potential": "high",
            }
        ],
        "summary": {"top_10_target_rows": ["tiny_001"]},
    }
    (config.outputs_dir / "eval_results_strict.json").write_text(json.dumps(strict), encoding="utf-8")
    (config.outputs_dir / "low_score_failure_mining_report.json").write_text(json.dumps(mining), encoding="utf-8")


def test_candidate_generation_adds_family_metadata_and_count_candidate(tiny_project):
    from dashagent.executor import AgentExecutor

    executor = AgentExecutor(tiny_project)
    candidates = generate_targeted_candidates(
        query_id="tiny_001",
        query="How many campaigns are there?",
        baseline_trajectory=_baseline_trajectory(),
        schema_index=executor.schema_index,
        endpoint_catalog=executor.endpoint_catalog,
        failure_row={"likely_failure_type": "wrong_count_vs_list"},
        max_candidates=12,
    )

    families = {candidate["candidate_family"] for candidate in candidates}
    assert "baseline" in families
    assert "count_list" in families
    for candidate in candidates:
        assert candidate["candidate_id"]
        assert candidate["rule_source"]
        assert candidate["trigger_features"]
        assert candidate["leakage_check_passed"] is True
        assert "query_id" not in candidate["trigger_features"]


def test_candidate_generation_local_index_evidence_is_evidence_not_answer(tiny_project):
    from dashagent.executor import AgentExecutor

    executor = AgentExecutor(tiny_project)
    candidates = generate_targeted_candidates(
        query_id="tiny_001",
        query="List campaigns named Welcome Journey",
        baseline_trajectory=_baseline_trajectory(),
        schema_index=executor.schema_index,
        endpoint_catalog=executor.endpoint_catalog,
        local_index_evidence=[
            {
                "classification": "reusable_entity_lookup",
                "source": "local_parquet_index",
                "table": "dim_campaign",
                "column": "name",
                "value": "Welcome Journey",
            },
            {
                "classification": "rejected_exact_query_or_gold_like_lookup",
                "source": "gold_answer_cache",
                "value": "memorized answer",
            },
        ],
        max_candidates=12,
    )

    local = [candidate for candidate in candidates if candidate["candidate_family"] == "local_index_grounded"]
    assert local
    assert local[0]["local_index_hits"] == [
        {
            "classification": "reusable_entity_lookup",
            "source": "local_parquet_index",
            "table": "dim_campaign",
            "column": "name",
            "value_preview": "Welcome Journey",
        }
    ]
    assert "final_answer" not in json.dumps(local[0]["local_index_hits"]).lower()


def test_candidate_generation_leakage_rejects_full_query_and_gold_signals():
    candidate = TargetedCandidate(
        candidate_id="bad",
        candidate_family="endpoint_rerank",
        generation_reason="Use gold API path",
        sql=None,
        api_call={"method": "GET", "path": "/x", "params": {}},
        expected_answer_shape="list",
        endpoint_family="bad",
        schema_family="bad",
        source_signals=["endpoint_catalog"],
        trigger_features=["How many campaigns are there?", "exact_public_entity"],
    )

    checked = apply_leakage_checks(candidate, query="How many campaigns are there?")

    assert checked.leakage_check_passed is False
    assert "exact_full_query_string_trigger" in checked.leakage_reasons
    assert "exact_public_entity_without_general_value_match" in checked.leakage_reasons
    assert any("gold" in reason for reason in checked.leakage_reasons)


def test_score075_candidate_generation_eval_writes_isolated_report(tiny_project):
    _write_eval_inputs(tiny_project)

    payload = run_score075_candidate_generation_eval(tiny_project)

    assert payload["summary"]["branch"] == "codex/score075-candidate-generation"
    assert payload["summary"]["packaged_execution_changed"] is False
    assert payload["summary"]["writes_eval_outputs"] is False
    assert payload["summary"]["writes_final_submission"] is False
    assert payload["summary"]["total_candidates"] >= 1
    assert "dashagent/targeted_candidate_generator.py" in payload["allowed_files"]
    assert payload["summary"]["dependency_status"]["local_index"]["status"] in {
        "api_missing_blocked",
        "api_available_declared_dependency",
    }
