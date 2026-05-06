from __future__ import annotations

import json

from dashagent.executor import AgentExecutor
from dashagent.query_family_examples import few_shot_public_overlap_check
from dashagent.research_safety import build_research_safety_audit
from scripts.generate_research_inspired_report import generate_report, render_markdown


def test_query_family_overlap_audit_has_no_public_or_gold_overlap():
    audit = few_shot_public_overlap_check(
        [{"query": "List all journeys", "gold_sql": "SELECT * FROM dim_campaign", "answer": "Birthday Message"}]
    )
    assert audit["exact_query_overlap"] is False
    assert audit["exact_gold_sql_overlap"] is False
    assert audit["public_answer_overlap"] is False
    assert audit["public_entity_overlap"] is False


def test_research_safety_audit_records_sources(tiny_project):
    executor = AgentExecutor(tiny_project)
    audit = build_research_safety_audit(executor.schema_index, [])

    assert audit["public_query_overlap"] is False
    assert audit["gold_sql_overlap"] is False
    assert audit["used_gold_patterns"] is False
    assert audit["schema_alias_source"]
    assert isinstance(audit["join_hint_source"], dict)
    assert audit["endpoint_family_rule_source"]
    assert audit["value_boost_source"]
    assert all("public example" not in source.lower() for source in audit["endpoint_family_rule_source"].values())
    assert audit["family_example_source"]


def test_research_inspired_report_contains_flags_and_techniques(tiny_project):
    strict_path = tiny_project.outputs_dir / "eval_results_strict.json"
    tiny_project.outputs_dir.mkdir(parents=True, exist_ok=True)
    strict_path.write_text(
        json.dumps(
            {
                "summary": {
                    "by_strategy": {
                        "SQL_FIRST_API_VERIFY": {
                            "avg_final_score": 0.649,
                            "avg_correctness_score": 0.6743,
                            "avg_estimated_tokens": 851.7714,
                            "avg_runtime": 0.0102,
                            "avg_tool_call_count": 1.4571,
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    report = generate_report(tiny_project)
    md = render_markdown(report)

    assert "ENABLE_SQL_AST_VALIDATION" in report["feature_flags"]
    assert "ENABLE_HYBRID_CANDIDATE_SCORING" in report["feature_flags"]
    assert any(row["source_inspiration"] == "SQLGlot" for row in report["techniques"])
    assert any(row["implemented_module"] == "dashagent/candidate_ranker.py" for row in report["techniques"])
    assert report["summary"]["value_retrieval_budget_ms"] == tiny_project.value_retrieval_max_ms
    assert report["summary"]["ranking_only_no_score_claim"] is True
    assert report["summary"]["value_retrieval_cache_key_algorithm"] == "sha256"
    assert report["summary"]["value_retrieval_cache_reproducible"] is True
    assert report["summary"]["final_submission_format_unchanged"] is True
    assert "no measured strict-score improvement" in md
    assert "Value retrieval budget" in md
    assert "Value retrieval cache key algorithm" in md
    assert "Diagnostic Candidate Risk Clusters" in md
    assert "Ranking-only no score claim" in md
    assert "Visualization artifacts directory" in md
