from __future__ import annotations

import json


def test_sql_semantic_quality_audit_writes_row_root_causes(tiny_project):
    from scripts.run_pure_llm_sql_semantic_quality_audit import run_pure_llm_sql_semantic_quality_audit

    reports_dir = tiny_project.outputs_dir / "reports"
    reports_dir.mkdir(parents=True)
    (reports_dir / "pure_llm_bounded_sql_score_audit.json").write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "query_id": "tiny_001",
                        "prompt": "When was the journey 'Birthday Message' published?",
                        "answer_intent": "DATE",
                        "llm_selected_evidence_source": "execute_sql",
                        "structured_sql_plan": {
                            "primary_table": "dim_campaign",
                            "tables_needed": ["dim_campaign"],
                            "columns_needed": ["updatedtime"],
                            "filters": [{"table": "dim_campaign", "column": "name", "operator": "equals", "value": "Birthday Message"}],
                            "aggregation": {"type": "none", "table": "dim_campaign", "column": ""},
                        },
                        "compiled_sql": "SELECT updatedtime FROM dim_campaign",
                        "sql_validation_result": {"ok": True},
                        "sql_execution_result": {"ok": True, "row_count": 1, "rows_preview": [{"updatedtime": "2026-01-01"}]},
                        "final_answer": "2026-01-01",
                        "final_answer_used_sql_result": True,
                        "strict_sql_score": 0.0,
                        "strict_answer_score": 0.1,
                        "failure_category": "sql_valid_but_wrong_columns",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    payload = run_pure_llm_sql_semantic_quality_audit(tiny_project)

    assert payload["summary"]["rows"] == 1
    assert payload["rows"][0]["failure_category"] == "wrong_columns"
    assert "published timestamp" in payload["rows"][0]["root_cause"].lower()
    assert (reports_dir / "pure_llm_sql_semantic_quality_audit.json").exists()
    assert (reports_dir / "pure_llm_sql_semantic_quality_audit.md").exists()
