from __future__ import annotations

import json
from pathlib import Path

from dashagent.config import Config
from scripts.run_api_endpoint_selection_gap_analysis import run_api_endpoint_selection_gap_analysis
from scripts.run_external_text_to_sql_tool_agent_research import run_external_text_to_sql_tool_agent_research
from scripts.run_generated_prompt_failure_cluster_analysis import run_generated_prompt_failure_cluster_analysis
from scripts.run_generated_unsupported_claim_fix_trial import run_generated_unsupported_claim_fix_trial
from scripts.run_generated_unsupported_claims_audit import run_generated_unsupported_claims_audit
from scripts.run_live_efficiency_recovery_trials import run_live_efficiency_recovery_trials
from scripts.run_live_api_efficiency_compression_trial import run_live_api_efficiency_compression_trial
from scripts.run_no_template_sql_mode_diagnostic import run_no_template_sql_mode_diagnostic
from scripts.run_route_mismatch_root_cause_analysis import run_route_mismatch_root_cause_analysis
from scripts.run_strict_efficiency_component_analysis import run_strict_efficiency_component_analysis
from scripts.run_strict_score_drift_analysis import run_strict_score_drift_analysis
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


def test_post_gate_blocker_reports_preserve_previous_unsupported_rows(tmp_path: Path) -> None:
    config = _config(tmp_path)
    reports = config.outputs_dir / "reports"
    _write_json(
        reports / "full_generated_prompt_suite_diagnostic.json",
        {
            "total_prompts": 1,
            "executed_prompts": 1,
            "runtime_pass_count": 1,
            "validation_fail_count": 0,
            "unsupported_claim_count": 0,
            "rows": [{"prompt_id": "gen_001", "unsupported_claim_count": 0}],
        },
    )
    _write_json(
        reports / "generated_prompt_failure_cluster_analysis.json",
        {
            "rows": [
                {
                    "prompt_id": "gen_001",
                    "prompt": "List schema blueprint IDs and names.",
                    "generation_type": "domain_coverage",
                    "domain_family": "schema_dataset",
                    "route_type": "SQL_ONLY",
                    "answer_intent": "LIST",
                    "endpoint_selected": ["/data/foundation/schemaregistry/tenant/schemas"],
                    "api_outcomes": ["api_error"],
                    "evidence_state": "sql_evidence",
                    "final_answer": "AJO Live Activities Feedback Event Dataset",
                    "unsupported_claim_count": 1,
                }
            ]
        },
    )
    _write_json(
        config.outputs_dir / "eval_results_strict.json",
        {"summary": {"by_strategy": {"SQL_FIRST_API_VERIFY": {"avg_final_score": 0.6543}}}, "rows": []},
    )

    audit = run_generated_unsupported_claims_audit(config)
    trial = run_generated_unsupported_claim_fix_trial(config)

    assert audit["summary"]["unsupported_claim_count"] == 0
    assert audit["summary"]["previous_gate_unsupported_claim_count"] == 1
    assert audit["previous_gate_rows"][0]["claim_category"] == "verifier_false_positive"
    assert trial["runtime_change_applied"] is True
    assert trial["baseline"]["previous_gate_unsupported_claim_count"] == 1


def test_strict_score_drift_analysis_identifies_efficiency_penalty(tmp_path: Path) -> None:
    config = _config(tmp_path)
    baseline = {
        "summary": {
            "by_strategy": {
                "SQL_FIRST_API_VERIFY": {
                    "avg_final_score": 0.6553,
                    "avg_correctness_score": 0.6805,
                    "avg_runtime": 0.01,
                    "avg_estimated_tokens": 800,
                }
            }
        },
        "rows": [
            {
                "query_id": "example_000",
                "strategy": "SQL_FIRST_API_VERIFY",
                "query": "How many schemas?",
                "final_score": 0.6553,
                "correctness_score": 0.6805,
                "runtime": 0.01,
                "estimated_tokens": 800,
            }
        ],
    }
    current = {
        "summary": {
            "by_strategy": {
                "SQL_FIRST_API_VERIFY": {
                    "avg_final_score": 0.6543,
                    "avg_correctness_score": 0.685,
                    "avg_runtime": 1.5,
                    "avg_estimated_tokens": 900,
                }
            }
        },
        "rows": [
            {
                "query_id": "example_000",
                "strategy": "SQL_FIRST_API_VERIFY",
                "query": "How many schemas?",
                "final_score": 0.6543,
                "correctness_score": 0.685,
                "runtime": 1.5,
                "estimated_tokens": 900,
            }
        ],
    }
    _write_json(config.outputs_dir / "eval_results_strict.json", current)
    _write_json(config.outputs_dir / "reports" / "baselines" / "pre_live_api_eval_results_strict.json", baseline)

    report = run_strict_score_drift_analysis(config)

    assert report["root_cause_summary"]["primary_root_cause"] == "efficiency_penalty_from_live_runtime_and_token_growth"


def test_efficiency_recovery_reports_identify_safe_token_projection(tmp_path: Path) -> None:
    config = _config(tmp_path)
    output_dir = config.outputs_dir / "eval" / "example_000" / "sql_first_api_verify"
    output_dir.mkdir(parents=True)
    trajectory = {
        "query_id": "example_000",
        "original_query": "Which schemas are active?",
        "strategy": "SQL_FIRST_API_VERIFY",
        "route_type": "SQL_THEN_API",
        "domain_type": "DATASET_SCHEMA",
        "steps": [
            {"kind": "route", "candidate_apis": [{"id": "schema_registry_schemas", "method": "GET", "path": "/schemas"}], "candidate_tables": ["dim_blueprint"], "reason": "r" * 400},
            {
                "kind": "nlp",
                "decomposition": {"expected_answer_shape": "list", "sub_questions": ["a", "b", "c"]},
                "relevance": {"tables": ["dim_blueprint"], "apis": ["schema_registry_schemas"]},
                "value_retrieval": {
                    "match_count": 1,
                    "matches": [
                        {
                            "kind": "quoted_entity",
                            "mention": "Profile",
                            "matched_table": "dim_blueprint",
                            "matched_column": "NAME",
                            "matched_value": "Profile" * 20,
                            "match_type": "exact",
                            "confidence": 1.0,
                            "used_for": "sql_filter",
                            "retrieval_cost": {"cache_key": "abc"},
                        }
                    ],
                },
            },
            {
                "kind": "plan",
                "strategy": "SQL_FIRST_API_VERIFY",
                "rationale": "r" * 400,
                "steps": [{"action": "sql", "family": "schema_list", "sql": "SELECT NAME FROM dim_blueprint", "purpose": "p" * 300}],
            },
            {
                "kind": "sql_call",
                "sql": "SELECT NAME FROM dim_blueprint",
                "validation": {"ok": True, "errors": [], "warnings": []},
                "result": {"ok": True, "row_count": 1, "rows": [{"NAME": "Profile"}]},
            },
            {
                "kind": "api_call",
                "method": "GET",
                "url": "/data/foundation/schemaregistry/tenant/schemas",
                "params": {},
                "validation": {"ok": True, "errors": [], "warnings": []},
                "result": {"ok": True, "dry_run": False, "endpoint": "/data/foundation/schemaregistry/tenant/schemas", "result_preview": {"name": "Profile"}},
            },
        ],
        "final_answer": "Profile is available.",
        "runtime": 0.5,
        "tool_call_count": 2,
        "sql_call_count": 1,
        "api_call_count": 1,
        "estimated_tokens": 1200,
        "timings": {"execution_time": 0.4},
        "errors": [],
    }
    _write_json(output_dir / "trajectory.json", trajectory)
    _write_json(
        config.outputs_dir / "eval_results_strict.json",
        {
            "summary": {
                "by_strategy": {
                    "SQL_FIRST_API_VERIFY": {
                        "avg_final_score": 0.6543,
                        "avg_correctness_score": 0.685,
                        "avg_estimated_tokens": 1200,
                        "avg_runtime": 0.5,
                        "avg_tool_call_count": 2,
                    }
                }
            },
            "rows": [
                {
                    "query_id": "example_000",
                    "strategy": "SQL_FIRST_API_VERIFY",
                    "query": "Which schemas are active?",
                    "final_score": 0.6543,
                    "correctness_score": 0.685,
                    "answer_score": 0.3,
                    "sql_score": 0.9,
                    "api_score": 1.0,
                    "estimated_tokens": 1200,
                    "runtime": 0.5,
                    "tool_call_count": 2,
                    "output_dir": str(output_dir),
                }
            ],
        },
    )
    _write_json(
        config.outputs_dir / "reports" / "strict_score_drift_analysis.json",
        {
            "score_states": {
                "pre_live_previous_packaged_baseline": {
                    "strict_score": 0.6553,
                    "correctness_score": 0.6805,
                    "estimated_tokens": 800,
                    "runtime": 0.01,
                    "tool_call_count": 2,
                }
            },
            "rows": [
                {
                    "query_id": "example_000",
                    "old_final_score": 0.6553,
                    "old_correctness_score": 0.6805,
                    "old_estimated_tokens": 800,
                    "old_runtime": 0.01,
                    "old_final_answer": "Profile is available.",
                }
            ],
        },
    )
    _write_json(
        config.outputs_dir / "reports" / "full_generated_prompt_suite_diagnostic.json",
        {"runtime_pass_count": 250, "validation_fail_count": 0, "unsupported_claim_count": 0},
    )

    component = run_strict_efficiency_component_analysis(config)
    trials = run_live_efficiency_recovery_trials(config)

    assert component["summary"]["avg_token_overhead_vs_baseline"] == 400.0
    assert trials["summary"]["best_variant"] in {item["variant"] for item in trials["variants"]}
    assert (config.outputs_dir / "reports" / "strict_efficiency_component_analysis.json").exists()
    assert (config.outputs_dir / "reports" / "live_efficiency_recovery_trials.json").exists()
