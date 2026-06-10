from __future__ import annotations

import json

from dashagent.eval_harness import EvalHarness
from dashagent.eval_harness import _build_timeout_eval_row


def test_eval_harness_runs_on_tiny_example(tiny_project):
    harness = EvalHarness(tiny_project)
    result = harness.run(strategies=["SQL_ONLY_BASELINE"])
    assert result["examples"] == 1
    assert result["rows"]
    assert (tiny_project.outputs_dir / "eval_results.json").exists()
    assert (tiny_project.outputs_dir / "strategy_comparison.md").exists()


def test_eval_harness_can_report_live_api_metrics(tiny_project):
    harness = EvalHarness(tiny_project)
    result = harness.run(strategies=["SQL_ONLY_BASELINE"], include_live_api_metrics=True)
    assert "live_api_metrics" in result
    assert "planned_api_score" in result["live_api_metrics"]


def test_timeout_eval_row_records_failed_query_and_heartbeat(tiny_project):
    harness = EvalHarness(tiny_project)
    example = harness.load_examples()[0]

    row = _build_timeout_eval_row(
        db=harness.executor.db,
        example=example,
        strategy="ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2",
        timeout_sec=3.0,
        elapsed=3.25,
        heartbeat={"current_stage": "checkpoint_llm_unified_planner", "prompt_id": example.query_id},
        output_dir=tiny_project.outputs_dir / "eval" / example.query_id / "robust_generalized_harness_candidate_v2",
        strict=True,
    )

    assert row["query_id"] == example.query_id
    assert row["timed_out"] is True
    assert row["timed_out_stage"] == "checkpoint_llm_unified_planner"
    assert row["error_count"] == 1
    assert row["final_score"] == 0.0
    assert row["last_stage_heartbeat"]["prompt_id"] == example.query_id


def test_eval_harness_timeout_partial_outputs_are_written(tiny_project, monkeypatch):
    harness = EvalHarness(tiny_project)

    def fake_timeout_runner(*args, **kwargs):
        example = kwargs["example"]
        strategy = kwargs["strategy"]
        return _build_timeout_eval_row(
            db=harness.executor.db,
            example=example,
            strategy=strategy,
            timeout_sec=1.0,
            elapsed=1.01,
            heartbeat={"current_stage": "unit_timeout_stage", "prompt_id": example.query_id},
            output_dir=tiny_project.outputs_dir / "eval" / example.query_id / strategy.lower(),
            strict=True,
        )

    monkeypatch.setattr("dashagent.eval_harness._run_eval_row_with_timeout", fake_timeout_runner)

    partial_dir = tiny_project.outputs_dir / "reports" / "partial_eval"
    result = harness.run(
        strategies=["ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2"],
        strict=True,
        per_query_timeout_sec=1.0,
        partial_report_dir=partial_dir,
    )

    assert result["timeout_query_ids"] == ["tiny_001"]
    assert result["summary"]["timeout_count"] == 1
    partial = json.loads((partial_dir / "eval_results_partial.json").read_text(encoding="utf-8"))
    assert partial["timeout_query_ids"] == ["tiny_001"]
    assert partial["last_stage_heartbeat"]["current_stage"] == "unit_timeout_stage"


def test_eval_harness_csv_writer_allows_timeout_row_extra_fields(tiny_project):
    harness = EvalHarness(tiny_project)
    normal = {
        "query_id": "ok",
        "strategy": "SQL_ONLY_BASELINE",
        "query": "How many campaigns are there?",
        "sql_score": 1.0,
        "api_score": None,
        "answer_score": 1.0,
        "correctness_score": 1.0,
        "efficiency_penalty": 0.0,
        "final_score": 1.0,
        "tool_call_count": 1,
        "sql_call_count": 1,
        "api_call_count": 0,
        "runtime": 0.1,
        "estimated_tokens": 0,
        "metadata_tokens": 0,
        "prompt_tokens": 0,
        "preprocessing_time": 0.0,
        "planning_time": 0.0,
        "execution_time": 0.0,
        "answer_time": 0.0,
        "error_count": 0,
        "validation_failures": 0,
        "sql_reason": "ok",
        "api_reason": "unscored",
        "answer_reason": "ok",
        "unscored_dimension_count": 1,
        "output_dir": "/tmp/ok",
        "timed_out": False,
        "timed_out_stage": None,
        "last_stage_heartbeat": {},
        "worker_error": None,
    }
    timeout = dict(normal, query_id="timeout", timed_out=True, timeout_sec=1.0)

    harness._write_outputs(
        {
            "examples": 2,
            "strategies": ["SQL_ONLY_BASELINE"],
            "rows": [normal, timeout],
            "summary": {"by_strategy": {}, "message": "unit"},
        },
        strict=True,
    )

    csv_text = (tiny_project.outputs_dir / "eval_results_strict.csv").read_text(encoding="utf-8")
    assert "timeout_sec" in csv_text.splitlines()[0]
