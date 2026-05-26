from __future__ import annotations

import json


def test_bounded_sql_score_audit_classifies_api_used_when_gold_sql_exists(tiny_project):
    from scripts.run_pure_llm_bounded_sql_score_audit import run_pure_llm_bounded_sql_score_audit

    reports_dir = tiny_project.outputs_dir / "reports"
    reports_dir.mkdir(parents=True)
    (reports_dir / "pure_llm_tool_agent_eval.json").write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "query_id": "tiny_001",
                        "prompt": "How many campaigns are there?",
                        "system": "structured_sql_plan_with_repair_v1",
                        "strict_scoring_status": "available",
                        "sql_score": 0.0,
                        "api_score": 0.5,
                        "answer_score": 0.1,
                        "trace_assertions": {
                            "selected_tool": "call_api",
                            "did_llm_choose_tool": True,
                            "sql_validation_ok": False,
                            "tool_result_used_in_answer": True,
                        },
                        "trajectory": {
                            "steps": [
                                {"kind": "llm_plan", "plan": {"answer_intent": "COUNT", "needs_sql": False, "needs_api": True}},
                                {
                                    "kind": "api_call",
                                    "endpoint_candidate": "journey_list",
                                    "method": "GET",
                                    "url": "/ajo/journey",
                                    "params": {"limit": 50},
                                    "validation": {"ok": True},
                                    "result": {"ok": True, "outcome": "live_empty"},
                                },
                            ]
                        },
                        "final_answer": "The API returned no campaigns.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    payload = run_pure_llm_bounded_sql_score_audit(tiny_project)

    assert payload["summary"]["root_cause"] == "bounded_sql_score_zero_due_to_missing_or_invalid_sql_calls"
    assert payload["rows"][0]["failure_category"] == "api_used_when_sql_needed"
    assert payload["rows"][0]["strict_sql_reason"] == "No generated SQL while gold SQL exists."
    assert payload["rows"][0]["evidence_source_that_should_have_been_considered"] == "local_sql_required"
    assert payload["rows"][0]["tool_choice_root_cause"] in {
        "api_bias_for_live_terms",
        "missed_local_table_affordance",
        "endpoint_catalog_overselected",
    }
    assert (reports_dir / "pure_llm_bounded_sql_score_audit.json").exists()
    assert (reports_dir / "pure_llm_bounded_sql_score_audit.md").exists()
    assert (reports_dir / "pure_llm_tool_choice_root_cause_audit.json").exists()
    assert (reports_dir / "pure_llm_tool_choice_root_cause_audit.md").exists()


def test_bounded_sql_score_audit_records_recognized_sql_trace(tiny_project):
    from scripts.run_pure_llm_bounded_sql_score_audit import run_pure_llm_bounded_sql_score_audit

    reports_dir = tiny_project.outputs_dir / "reports"
    reports_dir.mkdir(parents=True)
    (reports_dir / "pure_llm_tool_agent_eval.json").write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "query_id": "tiny_001",
                        "prompt": "How many campaigns are there?",
                        "system": "structured_sql_plan_with_repair_v1",
                        "strict_scoring_status": "available",
                        "sql_score": 1.0,
                        "api_score": None,
                        "answer_score": 0.9,
                        "trace_assertions": {
                            "selected_tool": "execute_sql",
                            "did_llm_choose_tool": True,
                            "sql_validation_ok": True,
                            "tool_result_used_in_answer": True,
                        },
                        "trajectory": {
                            "steps": [
                                {"kind": "llm_plan", "plan": {"answer_intent": "COUNT", "needs_sql": True, "needs_api": False}},
                                {
                                    "kind": "sql_call",
                                    "sql": "SELECT COUNT(*) AS count FROM dim_campaign",
                                    "validation": {"ok": True},
                                    "result": {"ok": True, "row_count": 1, "rows": [{"count": 2}]},
                                    "attempts": [
                                        {
                                            "structured_sql_plan": {"primary_table": "dim_campaign"},
                                            "compile": {"ok": True, "sql": "SELECT COUNT(*) AS count FROM dim_campaign"},
                                        }
                                    ],
                                },
                            ]
                        },
                        "final_answer": "There are 2 campaigns.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    payload = run_pure_llm_bounded_sql_score_audit(tiny_project)

    row = payload["rows"][0]
    assert row["did_llm_call_sql"] is True
    assert row["compiled_sql"] == "SELECT COUNT(*) AS count FROM dim_campaign"
    assert row["strict_sql_score"] == 1.0
    assert row["failure_category"] == "no_clear_sql_score_failure"


def test_bounded_sql_score_audit_writes_sql_trace_fix_report(tiny_project):
    from scripts.run_pure_llm_bounded_sql_score_audit import run_pure_llm_bounded_sql_score_audit

    reports_dir = tiny_project.outputs_dir / "reports"
    reports_dir.mkdir(parents=True)
    (reports_dir / "pure_llm_tool_agent_eval.json").write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "query_id": "tiny_001",
                        "prompt": "List all campaigns",
                        "system": "structured_sql_plan_with_tool_choice_guard_v1",
                        "strict_scoring_status": "available",
                        "sql_score": 0.0,
                        "api_score": None,
                        "answer_score": 0.1,
                        "trace_assertions": {
                            "selected_tool": "execute_sql",
                            "did_llm_choose_tool": True,
                            "sql_validation_ok": False,
                            "tool_result_used_in_answer": False,
                        },
                        "trajectory": {
                            "steps": [
                                {"kind": "llm_plan", "plan": {"answer_intent": "LIST", "needs_sql": True, "needs_api": False}},
                                {
                                    "kind": "sql_call",
                                    "sql": None,
                                    "validation": {"ok": False, "errors": ["unknown table"]},
                                    "result": {},
                                    "repair_rounds": 2,
                                    "attempts": [
                                        {
                                            "structured_sql_plan": {"primary_table": "journey"},
                                            "plan_validation": {"ok": False, "errors": ["unknown table: journey"]},
                                            "compile": {"ok": False, "errors": ["unknown table: journey"]},
                                        }
                                    ],
                                },
                            ]
                        },
                        "final_answer": "I could not produce a validated SQL query from the available schema.",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    payload = run_pure_llm_bounded_sql_score_audit(tiny_project)

    assert payload["rows"][0]["failure_category"] == "tool_trace_format_mismatch"
    sql_trace_report = json.loads((reports_dir / "pure_llm_example003_like_sql_trace_fix.json").read_text(encoding="utf-8"))
    assert sql_trace_report["summary"]["example003_like_row_count"] == 1
    assert sql_trace_report["rows"][0]["executable_sql_reached_evaluator"] is False
    assert sql_trace_report["rows"][0]["likely_issue"] in {"repair_loop_failed", "compiler_rejected_plan"}
