from __future__ import annotations

import json
from pathlib import Path

from dashagent.config import Config
from scripts.run_api_endpoint_selection_gap_analysis import run_api_endpoint_selection_gap_analysis
from scripts.run_external_text_to_sql_tool_agent_research import run_external_text_to_sql_tool_agent_research
from scripts.run_generated_prompt_failure_cluster_analysis import run_generated_prompt_failure_cluster_analysis
from scripts.run_live_api_efficiency_compression_trial import run_live_api_efficiency_compression_trial
from scripts.run_no_template_sql_mode_diagnostic import run_no_template_sql_mode_diagnostic
from scripts.run_route_mismatch_root_cause_analysis import run_route_mismatch_root_cause_analysis
from scripts.run_targeted_answer_shape_trial import run_targeted_answer_shape_trial


def _config(tmp_path: Path) -> Config:
    return Config(
        project_root=tmp_path,
        data_dir=tmp_path / "data",
        dbsnapshot_dir=tmp_path / "data" / "DBSnapshot",
        data_json_path=tmp_path / "data" / "data.json",
        outputs_dir=tmp_path / "outputs",
        prompts_dir=tmp_path / "prompts",
    )


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _seed_reports(config: Config) -> None:
    reports = config.outputs_dir / "reports"
    rows = [
        {
            "prompt_id": "gen_001",
            "prompt": "How many audiences are active?",
            "generation_type": "paraphrase",
            "domain_family": "segment_audience",
            "route_type": "SQL_THEN_API",
            "actual_route": "SQL_THEN_API",
            "expected_route_label": "SQL_PLUS_API",
            "route_matches_diagnostic": True,
            "answer_intent": "COUNT",
            "actual_answer_intent": "COUNT",
            "answer_intent_matches_diagnostic": True,
            "failure_category": "answer_shape_weak",
            "template_hit": True,
            "sql_calls": 1,
            "api_calls": 1,
            "endpoint_selected": ["/data/core/ups/audiences"],
            "api_outcomes": ["live_success"],
            "api_error_count": 0,
            "live_empty_count": 0,
            "unsupported_claim_count": 0,
            "answer_used_sql_evidence": True,
            "answer_used_live_api_evidence": True,
            "requires_live_api": True,
            "tokens": 1200,
            "runtime": 1.2,
            "tool_count": 2,
            "final_answer": "There are active audiences.",
        },
        {
            "prompt_id": "gen_002",
            "prompt": "List local schemas.",
            "generation_type": "synonym",
            "domain_family": "schema_dataset",
            "route_type": "SQL_ONLY",
            "actual_route": "SQL_ONLY",
            "expected_route_label": "SQL_PLUS_API",
            "route_matches_diagnostic": False,
            "failure_category": "route_mismatch",
            "template_hit": False,
            "sql_calls": 1,
            "api_calls": 0,
            "api_error_count": 0,
            "unsupported_claim_count": 0,
            "answer_used_sql_evidence": True,
            "requires_live_api": False,
            "tokens": 700,
            "runtime": 0.2,
            "tool_count": 1,
            "final_answer": "Two schemas are present.",
        },
        {
            "prompt_id": "gen_003",
            "prompt": "Check a destination flow.",
            "generation_type": "paraphrase",
            "domain_family": "destination_dataflow",
            "route_type": "SQL_THEN_API",
            "actual_route": "SQL_THEN_API",
            "expected_route_label": "SQL_PLUS_API",
            "route_matches_diagnostic": True,
            "failure_category": "api_endpoint_selection_gap",
            "template_hit": True,
            "sql_calls": 1,
            "api_calls": 1,
            "endpoint_selected": ["/data/foundation/flowservice/flows"],
            "api_outcomes": ["api_error"],
            "api_error_count": 1,
            "live_empty_count": 0,
            "unsupported_claim_count": 0,
            "answer_used_sql_evidence": True,
            "requires_live_api": False,
            "tokens": 1800,
            "runtime": 1.8,
            "tool_count": 2,
            "final_answer": "The SQL evidence has the flow.",
        },
    ]
    _write_json(
        reports / "full_generated_prompt_suite_diagnostic.json",
        {
            "total_prompts": 3,
            "executed_prompts": 3,
            "runtime_pass_count": 3,
            "validation_fail_count": 0,
            "unsupported_claim_count": 0,
            "rows": rows,
        },
    )
    _write_json(
        reports / "nl_sql_robustness_audit.json",
        {
            "metrics": {"template_dependency_score": 0.1, "paraphrase_consistency_score": 0.99},
            "rows": [
                {
                    "prompt_id": "robust_001",
                    "prompt": "List local schemas.",
                    "template_hit": False,
                    "generated_sql": "SELECT 1",
                    "sql_validation_ok": True,
                    "sql_execution_ok": True,
                    "likely_failure": "none",
                    "route_type": "SQL_ONLY",
                    "selected_tables": ["dim_blueprint"],
                    "join_count": 0,
                    "count_distinct": False,
                }
            ],
        },
    )


def test_robustness_improvement_report_scripts_generate_diagnostic_reports(tmp_path: Path) -> None:
    config = _config(tmp_path)
    _seed_reports(config)
    assert run_generated_prompt_failure_cluster_analysis(config)["cluster_counts"]["answer_shape_weak"] == 1
    assert run_targeted_answer_shape_trial(config)["runtime_change_applied"] is False
    assert run_route_mismatch_root_cause_analysis(config)["mismatch_count"] == 1
    assert run_api_endpoint_selection_gap_analysis(config)["gap_count"] == 1
    assert run_live_api_efficiency_compression_trial(config)["api_prompt_rows"] == 2
    assert run_no_template_sql_mode_diagnostic(config)["promotion_gate"]["promotable"] is False
    assert run_external_text_to_sql_tool_agent_research(config)["dependencies_added"] == []
    for stem in [
        "generated_prompt_failure_cluster_analysis",
        "targeted_answer_shape_trial",
        "route_mismatch_root_cause_analysis",
        "api_endpoint_selection_gap_analysis",
        "live_api_efficiency_compression_trial",
        "no_template_sql_mode_diagnostic",
        "external_text_to_sql_tool_agent_research",
    ]:
        assert (config.outputs_dir / "reports" / f"{stem}.json").exists()
        assert (config.outputs_dir / "reports" / f"{stem}.md").exists()
