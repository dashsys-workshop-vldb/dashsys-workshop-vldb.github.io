from __future__ import annotations

import json

from scripts.generate_baseline_comparison_report import generate_report, render_markdown


def test_baseline_comparison_report_from_minimal_inputs(tiny_project):
    tiny_project.outputs_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "summary": {
            "by_strategy": {
                "LLM_FREE_AGENT_BASELINE": {"avg_correctness_score": 0.5, "avg_final_score": 0.4, "avg_tool_call_count": 3, "avg_estimated_tokens": 1000, "avg_runtime": 1},
                "SQL_FIRST_API_VERIFY": {"avg_correctness_score": 0.8, "avg_final_score": 0.75, "avg_tool_call_count": 1, "avg_estimated_tokens": 800, "avg_runtime": 0.5},
            }
        },
        "rows": [],
    }
    (tiny_project.outputs_dir / "eval_results.json").write_text(json.dumps(payload), encoding="utf-8")
    report = generate_report(tiny_project)
    systems = {row["system"] for row in report["systems"]}
    assert "LLM_FREE_AGENT_BASELINE" in systems
    assert "SQL_FIRST_API_VERIFY" in systems
    assert report["improvement_vs_naive"]
    assert "flowchart" in report["mermaid"]


def test_failed_real_llm_baseline_is_not_marked_successful(tiny_project):
    tiny_project.outputs_dir.mkdir(parents=True, exist_ok=True)
    (tiny_project.outputs_dir / "eval_results.json").write_text(
        json.dumps({"summary": {"by_strategy": {}}, "rows": []}),
        encoding="utf-8",
    )
    (tiny_project.outputs_dir / "llm_baseline_eval.json").write_text(
        json.dumps(
            {
                "skipped": False,
                "rows": [
                    {
                        "query_id": "example_000",
                        "system": "REAL_LLM_TWO_TOOLS_BASELINE",
                        "real_llm_called": True,
                        "tool_calls_executed": False,
                        "valid_agent_run": False,
                        "skipped_or_failed": True,
                        "failure_reason": "invalid_tool_call_format_after_retry",
                        "tool_call_count": 0,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    report = generate_report(tiny_project)
    real_status = next(row for row in report["systems"] if row["system"] == "REAL_LLM_TWO_TOOLS_BASELINE")["llm_status"]
    assert real_status["status"] == "real_llm_called_but_tool_loop_failed"
    assert real_status["valid_rows"] == 0
    assert report["failed_real_llm_tool_loops"]
    assert report["real_llm_tool_loop_warning"] is True
    assert not report["successful_real_llm_tool_loops"]


def test_valid_real_llm_baseline_is_marked_successful(tiny_project):
    tiny_project.outputs_dir.mkdir(parents=True, exist_ok=True)
    (tiny_project.outputs_dir / "eval_results.json").write_text(
        json.dumps({"summary": {"by_strategy": {}}, "rows": []}),
        encoding="utf-8",
    )
    (tiny_project.outputs_dir / "llm_baseline_eval.json").write_text(
        json.dumps(
            {
                "skipped": False,
                "rows": [
                    {
                        "query_id": "example_000",
                        "system": "REAL_LLM_TWO_TOOLS_BASELINE",
                        "real_llm_called": True,
                        "tool_calls_executed": True,
                        "valid_agent_run": True,
                        "skipped_or_failed": False,
                        "tool_call_count": 1,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    report = generate_report(tiny_project)
    real_status = next(row for row in report["systems"] if row["system"] == "REAL_LLM_TWO_TOOLS_BASELINE")["llm_status"]
    assert real_status["status"] == "valid_tool_agent_run"
    assert real_status["valid_rows"] == 1
    assert report["successful_real_llm_tool_loops"]
    assert not report["failed_real_llm_tool_loops"]


def test_raw_and_guided_baseline_metrics_are_separate(tiny_project):
    tiny_project.outputs_dir.mkdir(parents=True, exist_ok=True)
    (tiny_project.outputs_dir / "eval_results.json").write_text(
        json.dumps({"summary": {"by_strategy": {}}, "rows": []}),
        encoding="utf-8",
    )
    (tiny_project.outputs_dir / "llm_baseline_eval.json").write_text(
        json.dumps(
            {
                "skipped": False,
                "rows": [
                    {
                        "query_id": "example_raw",
                        "system": "RAW_REAL_LLM_TWO_TOOLS_BASELINE",
                        "real_llm_called": True,
                        "tool_calls_executed": False,
                        "valid_agent_run": False,
                        "skipped_or_failed": True,
                        "invalid_tool_call_count": 2,
                        "failure_categories": {"unknown_table_count": 1},
                        "tool_call_count": 2,
                    },
                    {
                        "query_id": "example_guided",
                        "system": "GUIDED_REAL_LLM_TWO_TOOLS_BASELINE",
                        "real_llm_called": True,
                        "tool_calls_executed": True,
                        "valid_agent_run": True,
                        "skipped_or_failed": False,
                        "invalid_tool_call_count": 0,
                        "repaired_endpoint_count": 1,
                        "prompt_context_tokens": 1200,
                        "runtime": 0.2,
                        "tool_call_count": 1,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    report = generate_report(tiny_project)
    assert report["raw_real_llm_tool_loops"]["failed_count"] == 1
    assert report["guided_real_llm_tool_loops"]["successful_count"] == 1
    assert report["failure_category_summary"]["raw"]["unknown_table_count"] == 1
    assert report["guided_real_llm_tool_loops"]["avg_endpoint_repairs"] == 1
    assert report["efficiency_comparison"]["guided"]["avg_prompt_context_tokens"] == 1200


def test_baseline_markdown_has_diagnostic_cells_and_variant_columns(tiny_project):
    tiny_project.outputs_dir.mkdir(parents=True, exist_ok=True)
    (tiny_project.outputs_dir / "eval_results.json").write_text(
        json.dumps({"summary": {"by_strategy": {}}, "rows": []}),
        encoding="utf-8",
    )
    (tiny_project.outputs_dir / "llm_baseline_eval.json").write_text(
        json.dumps(
            {
                "skipped": False,
                "rows": [
                    {
                        "query_id": "example_000",
                        "system": "RAW_REAL_LLM_TWO_TOOLS_BASELINE",
                        "baseline_variant": "raw",
                        "real_llm_called": True,
                        "tool_calls_executed": True,
                        "valid_agent_run": True,
                        "skipped_or_failed": False,
                        "tool_call_count": 2,
                        "prompt_context_tokens": 100,
                        "runtime": 1.2,
                        "successful_evidence_count": 1,
                        "invalid_tool_call_count": 1,
                        "repaired_endpoint_count": 0,
                    },
                    {
                        "query_id": "example_001",
                        "system": "RAW_REAL_LLM_TWO_TOOLS_BASELINE",
                        "baseline_variant": "raw",
                        "real_llm_called": True,
                        "tool_calls_executed": False,
                        "valid_agent_run": False,
                        "skipped_or_failed": True,
                        "failure_reason": "llm_request_failed",
                        "tool_call_count": 0,
                    },
                    {
                        "query_id": "example_000",
                        "system": "GUIDED_REAL_LLM_TWO_TOOLS_BASELINE",
                        "baseline_variant": "guided",
                        "real_llm_called": True,
                        "tool_calls_executed": True,
                        "valid_agent_run": True,
                        "skipped_or_failed": False,
                        "tool_call_count": 1,
                        "prompt_context_tokens": 180,
                        "runtime": 1.4,
                        "successful_evidence_count": 2,
                        "dry_run_only_api_count": 1,
                        "invalid_tool_call_count": 0,
                        "repaired_endpoint_count": 1,
                    },
                    {
                        "query_id": "example_001",
                        "system": "GUIDED_REAL_LLM_TWO_TOOLS_BASELINE",
                        "baseline_variant": "guided",
                        "real_llm_called": True,
                        "tool_calls_executed": False,
                        "valid_agent_run": False,
                        "skipped_or_failed": True,
                        "failure_reason": "llm_request_failed",
                        "tool_call_count": 0,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    markdown = render_markdown(generate_report(tiny_project))
    assert "n/a - tool-loop diagnostic baseline" in markdown
    assert "| Variant | Query ID | Tool calls | Tool calls executed? | Valid run? | Evidence count | Dry-run only? | Invalid calls | Endpoint repairs |" in markdown
    assert "| Raw | `example_000` | 2 | True | True | 1 | False | 1 | 0 |" in markdown
    assert "| Guided | `example_000` | 1 | True | True | 2 | True | 0 | 1 |" in markdown
    assert "Dry-run API calls are not counted as successful live evidence" in markdown
    assert "## Provider Reliability Note" in markdown
    assert "| Raw | 1 |" in markdown
    assert "| Guided | 1 |" in markdown
    report = generate_report(tiny_project)
    assert report["provider_reliability"]["raw_llm_request_failed_count"] == 1
    assert report["provider_reliability"]["guided_llm_request_failed_count"] == 1
