from __future__ import annotations

import json
from pathlib import Path

from scripts.generate_consolidated_reports import generate_consolidated_reports
from scripts.run_comprehensive_failure_analysis import run_comprehensive_failure_analysis


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _write_md(path: Path, text: str = "# report\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _seed_official_outputs(outputs: Path) -> None:
    rows = [
        {
            "query_id": "example_001",
            "query": "How many audiences are active?",
            "strategy": "SQL_FIRST_API_VERIFY",
            "output_dir": str(outputs / "eval" / "example_001" / "sql_first_api_verify"),
            "final_score": 0.54,
            "answer_score": 0.2,
            "sql_score": 1.0,
            "api_score": 1.0,
            "tool_call_count": 2,
            "estimated_tokens": 700,
            "runtime": 0.01,
            "answer_reason": "Answer missed the required count.",
            "sql_reason": "Strict semantic result match.",
            "api_reason": "Dry-run API state accepted.",
        },
        {
            "query_id": "example_002",
            "query": "List the active segment names.",
            "strategy": "SQL_FIRST_API_VERIFY",
            "output_dir": str(outputs / "eval" / "example_002" / "sql_first_api_verify"),
            "final_score": 0.62,
            "answer_score": 0.35,
            "sql_score": 1.0,
            "api_score": 0.8,
            "tool_call_count": 2,
            "estimated_tokens": 740,
            "runtime": 0.01,
            "answer_reason": "Answer is vague.",
            "sql_reason": "Strict semantic result match.",
            "api_reason": "API required but dry-run unavailable.",
        },
    ]
    for row in rows:
        out = Path(row["output_dir"])
        out.mkdir(parents=True, exist_ok=True)
        if row["query_id"] == "example_001":
            trajectory = {
                "query_id": row["query_id"],
                "original_query": row["query"],
                "strategy": "SQL_FIRST_API_VERIFY",
                "route_type": "SQL_THEN_API",
                "domain_type": "SEGMENT_AUDIENCE",
                "answer_intent": "COUNT",
                "final_answer": "Active audiences were found in local evidence; live API verification was unavailable.",
                "steps": [
                    {
                        "kind": "sql_call",
                        "sql": "SELECT COUNT(*) AS count FROM dim_segment WHERE status = 'active'",
                        "result": {
                            "ok": True,
                            "row_count": 1,
                            "rows": {"items": [{"count": 2}], "total_items": 1, "truncated_items": False},
                        },
                    },
                    {
                        "kind": "api_call",
                        "method": "GET",
                        "url": "/audiences",
                        "result": {"ok": False, "dry_run": True, "evidence_state": "dry_run_unavailable"},
                    },
                ],
                "checkpoints": [],
            }
        else:
            trajectory = {
                "query_id": row["query_id"],
                "original_query": row["query"],
                "strategy": "SQL_FIRST_API_VERIFY",
                "route_type": "SQL_THEN_API",
                "domain_type": "SEGMENT_AUDIENCE",
                "answer_intent": "LIST",
                "final_answer": "The local SQL evidence has matching segments, but live API verification was unavailable.",
                "steps": [
                    {
                        "kind": "sql_call",
                        "sql": "SELECT name FROM dim_segment WHERE status = 'active'",
                        "result": {
                            "ok": True,
                            "row_count": 2,
                            "rows": {
                                "items": [{"name": "High Value"}, {"name": "Recent Buyers"}],
                                "total_items": 2,
                                "truncated_items": False,
                            },
                        },
                    },
                    {
                        "kind": "api_call",
                        "method": "GET",
                        "url": "/segments",
                        "result": {"ok": False, "dry_run": True, "evidence_state": "dry_run_unavailable"},
                    },
                ],
                "checkpoints": [],
            }
        _write_json(out / "trajectory.json", trajectory)
        _write_json(out / "metadata.json", {"query_id": row["query_id"]})
        (out / "filled_system_prompt.txt").write_text("Metadata:\n{}\n", encoding="utf-8")
    _write_json(
        outputs / "eval_results_strict.json",
        {
            "examples": 2,
            "rows": rows,
            "summary": {"by_strategy": {"SQL_FIRST_API_VERIFY": {"avg_final_score": 0.58}}},
        },
    )


def _seed_generated_diagnostic(project_root: Path, outputs: Path) -> None:
    prompts = [
        {
            "prompt_id": "gen_0001",
            "prompt": "How many active audiences are there?",
            "generation_type": "paraphrase",
            "domain_family": "segment_audience",
            "expected_route_diagnostic": "SQL_PLUS_API",
            "expected_answer_intent_diagnostic": "COUNT",
            "should_be_scored": False,
            "diagnostic_only": True,
        },
        {
            "prompt_id": "gen_0002",
            "prompt": "List active segment names.",
            "generation_type": "paraphrase",
            "domain_family": "segment_audience",
            "expected_route_diagnostic": "SQL_PLUS_API",
            "expected_answer_intent_diagnostic": "LIST",
            "should_be_scored": False,
            "diagnostic_only": True,
        },
        {
            "prompt_id": "gen_0003",
            "prompt": "Show flow runs that do not exist locally.",
            "generation_type": "edge_case",
            "domain_family": "dataflow_run",
            "expected_route_diagnostic": "SQL_PLUS_API",
            "expected_answer_intent_diagnostic": "LIST",
            "should_be_scored": False,
            "diagnostic_only": True,
        },
    ]
    _write_json(project_root / "data" / "generated_prompt_suite.json", prompts)
    rows = [
        {
            "prompt_id": "gen_0001",
            "prompt": prompts[0]["prompt"],
            "generation_type": "paraphrase",
            "domain_family": "segment_audience",
            "answer_intent": "COUNT",
            "actual_answer_intent": "COUNT",
            "expected_route_label": "SQL_PLUS_API",
            "actual_route": "SQL_THEN_API",
            "domain_type": "SEGMENT_AUDIENCE",
            "answer_family": "segment_count",
            "strategy": "SQL_FIRST_API_VERIFY",
            "sql_calls": 1,
            "sql_template": "segment_count",
            "dry_run_api_calls": 1,
            "api_calls": 1,
            "evidence_state": "dry_run_unavailable",
            "final_answer": "Local SQL found active audiences; live API verification was unavailable.",
            "zero_row_sql": False,
            "requires_live_api": True,
            "missing_count_or_name_advisory": True,
            "answer_too_vague_advisory": False,
            "route_matches_diagnostic": True,
            "domain_matches_diagnostic": True,
            "answer_intent_matches_diagnostic": True,
            "validation_failures": 0,
            "runtime": 0.01,
            "tokens": 500,
            "diagnostic_only": True,
            "official_score_claim": False,
            "promotion_allowed": False,
        },
        {
            "prompt_id": "gen_0002",
            "prompt": prompts[1]["prompt"],
            "generation_type": "paraphrase",
            "domain_family": "segment_audience",
            "answer_intent": "LIST",
            "actual_answer_intent": "LIST",
            "expected_route_label": "SQL_PLUS_API",
            "actual_route": "SQL_THEN_API",
            "domain_type": "SEGMENT_AUDIENCE",
            "answer_family": "segment_list",
            "strategy": "SQL_FIRST_API_VERIFY",
            "sql_calls": 1,
            "sql_template": "segment_list",
            "dry_run_api_calls": 1,
            "api_calls": 1,
            "evidence_state": "dry_run_unavailable",
            "final_answer": "Matching segments exist locally, but live API verification was unavailable.",
            "zero_row_sql": False,
            "requires_live_api": True,
            "missing_count_or_name_advisory": True,
            "answer_too_vague_advisory": True,
            "route_matches_diagnostic": True,
            "domain_matches_diagnostic": True,
            "answer_intent_matches_diagnostic": True,
            "validation_failures": 0,
            "runtime": 0.01,
            "tokens": 510,
            "diagnostic_only": True,
            "official_score_claim": False,
            "promotion_allowed": False,
        },
        {
            "prompt_id": "gen_0003",
            "prompt": prompts[2]["prompt"],
            "generation_type": "edge_case",
            "domain_family": "dataflow_run",
            "answer_intent": "LIST",
            "actual_answer_intent": "LIST",
            "expected_route_label": "SQL_PLUS_API",
            "actual_route": "SQL_THEN_API",
            "domain_type": "DATAFLOW_RUN",
            "answer_family": "dataflow_list",
            "strategy": "SQL_FIRST_API_VERIFY",
            "sql_calls": 1,
            "sql_template": "dataflow_run_list",
            "dry_run_api_calls": 1,
            "api_calls": 1,
            "evidence_state": "dry_run_unavailable",
            "final_answer": "There is no data.",
            "zero_row_sql": True,
            "requires_live_api": False,
            "missing_count_or_name_advisory": False,
            "answer_too_vague_advisory": True,
            "route_matches_diagnostic": True,
            "domain_matches_diagnostic": True,
            "answer_intent_matches_diagnostic": True,
            "validation_failures": 0,
            "runtime": 0.01,
            "tokens": 500,
            "diagnostic_only": True,
            "official_score_claim": False,
            "promotion_allowed": False,
        },
    ]
    for row in rows:
        out = outputs / "generated_prompt_suite_local_diagnostic" / row["prompt_id"]
        out.mkdir(parents=True, exist_ok=True)
        _write_json(out / "trajectory.json", {"query_id": row["prompt_id"], "final_answer": row["final_answer"], "steps": []})
        _write_json(out / "metadata.json", {"query_id": row["prompt_id"]})
        (out / "filled_system_prompt.txt").write_text("diagnostic prompt\n", encoding="utf-8")
    _write_json(
        outputs / "reports" / "generated_prompt_suite_local_diagnostic.json",
        {
            "report_type": "generated_prompt_suite_local_diagnostic",
            "diagnostic_only": True,
            "official_score_claim": False,
            "promotion_allowed": False,
            "total_prompts": 3,
            "executed_prompts": 3,
            "runtime_pass_count": 3,
            "runtime_fail_count": 0,
            "validation_fail_count": 0,
            "rows": rows,
        },
    )
    _write_md(outputs / "reports" / "generated_prompt_suite_local_diagnostic.md", "# Generated Diagnostic\n")
    for name in [
        "generated_prompt_local_gap_samples",
        "local_deterministic_improvement_candidates",
        "local_gap_manual_review",
    ]:
        _write_json(outputs / "reports" / f"{name}.json", {"report_type": name, "diagnostic_only": True, "official_score_claim": False})
        _write_md(outputs / "reports" / f"{name}.md", f"# {name}\n")


def _seed_status_reports(outputs: Path) -> None:
    reports = outputs / "reports"
    _write_json(reports / "workflow_decision_audit.json", {"report_type": "workflow_decision_audit"})
    _write_md(reports / "workflow_decision_audit.md")
    _write_json(reports / "accuracy_and_bottleneck_summary.json", {"report_type": "accuracy_and_bottleneck_summary"})
    _write_md(reports / "accuracy_and_bottleneck_summary.md")
    _write_json(reports / "evidence_usage_audit.json", {"report_type": "evidence_usage_audit", "rows": []})
    _write_md(reports / "evidence_usage_audit.md")
    _write_json(reports / "sql_evidence_usage_audit.json", {"report_type": "sql_evidence_usage_audit", "rows": []})
    _write_md(reports / "sql_evidence_usage_audit.md")
    _write_json(reports / "score_path_contribution_audit.json", {"report_type": "score_path_contribution_audit"})
    _write_md(reports / "score_path_contribution_audit.md")
    _write_json(
        reports / "score_focused_core_improvement_trials.json",
        {"report_type": "score_focused_core_improvement_trials", "summary": {"recommendation": "keep_trial_only"}},
    )
    _write_md(reports / "score_focused_core_improvement_trials.md")
    _write_json(reports / "score_focused_core_fix_decision.json", {"report_type": "score_focused_core_fix_decision"})
    _write_md(reports / "score_focused_core_fix_decision.md")
    _write_json(
        reports / "system_summary.json",
        {
            "report_type": "system_summary",
            "packaged_strategy": "SQL_FIRST_API_VERIFY",
            "strict_final_score": 0.6553,
            "hidden_style": {"passed": 48, "total": 48, "label": "48/48"},
            "final_submission_ready": True,
        },
    )
    _write_md(reports / "system_summary.md")
    _write_json(reports / "report_index.json", {"report_type": "report_index"})
    _write_md(reports / "report_index.md")
    _write_json(
        reports / "adobe_access_waiting_status.json",
        {"report_type": "adobe_access_waiting_status", "live_api_guard": {"live_success_count": 0}},
    )
    _write_md(reports / "adobe_access_waiting_status.md")
    _write_json(
        reports / "live_api_full_run_blocker.json",
        {"report_type": "live_api_full_run_blocker", "live_success_count": 0, "guard_decision": "blocked"},
    )
    _write_md(reports / "live_api_full_run_blocker.md")


def _seed_all(tiny_project) -> None:
    _seed_official_outputs(tiny_project.outputs_dir)
    _seed_generated_diagnostic(tiny_project.project_root, tiny_project.outputs_dir)
    _seed_status_reports(tiny_project.outputs_dir)


def test_comprehensive_failure_analysis_writes_all_reports(tiny_project):
    _seed_all(tiny_project)

    payload = run_comprehensive_failure_analysis(tiny_project)

    reports = tiny_project.outputs_dir / "reports"
    expected = [
        "comprehensive_failure_analysis_preflight",
        "official_row_failure_table",
        "generated_prompt_failure_table",
        "cross_dataset_failure_clusters",
        "general_deterministic_rule_candidates",
        "cross_dataset_counterfactual_answer_sketches",
        "general_rule_hardcoding_risk_audit",
        "comprehensive_failure_fix_decision",
    ]
    for stem in expected:
        assert (reports / f"{stem}.json").exists()
        assert (reports / f"{stem}.md").exists()

    preflight = payload["preflight"]
    assert preflight["packaged_strategy"] == "SQL_FIRST_API_VERIFY"
    assert preflight["generated_prompts_diagnostic_only"] is True
    assert preflight["runtime_change_allowed"] is False
    assert preflight["no_hardcoding_rule"] is True
    assert preflight["official_row_count"] == 2
    assert preflight["generated_prompt_count"] == 3


def test_official_and_generated_tables_have_required_classifications(tiny_project):
    _seed_all(tiny_project)

    payload = run_comprehensive_failure_analysis(tiny_project)

    official_rows = payload["official_row_failure_table"]["rows"]
    generated_rows = payload["generated_prompt_failure_table"]["rows"]
    assert len(official_rows) == 2
    assert len(generated_rows) == 3
    for row in official_rows:
        assert row["likely_primary_cause"]
        assert isinstance(row["locally_fixable_now"], bool)
        assert isinstance(row["requires_live_api"], bool)
        assert isinstance(row["general_rule_possible"], bool)
        assert row["hardcoding_risk"] in {"low", "medium", "high"}
        assert row["confidence"] in {"low", "medium", "high"}
    for row in generated_rows:
        assert row["diagnostic_only"] is True
        assert row["generated_labels_are_advisory_only"] is True
        assert row["likely_issue_type"] in {
            "generated_label_noise",
            "live_api_required",
            "synonym_gap",
            "router_gap",
            "domain_detection_gap",
            "answer_intent_gap",
            "SQL_template_gap",
            "answer_template_gap",
            "zero_row_clarity_gap",
            "dry_run_wording_gap",
            "no_issue",
            "unclear",
        }
        assert "prompt text is diagnostic-only" in row["hardcoding_warning"]


def test_clusters_candidates_and_hardcoding_audit_are_report_only(tiny_project):
    _seed_all(tiny_project)

    payload = run_comprehensive_failure_analysis(tiny_project)

    clusters = payload["cross_dataset_failure_clusters"]["clusters"]
    candidates = payload["general_deterministic_rule_candidates"]["candidates"]
    risk_rows = payload["general_rule_hardcoding_risk_audit"]["candidates"]
    decision = payload["comprehensive_failure_fix_decision"]

    assert clusters
    assert any(cluster["cluster_id"] == "sql_evidence_answer_omission" for cluster in clusters)
    assert candidates
    for candidate in candidates:
        assert "official_rows_supported" in candidate
        assert "generated_prompts_supported" in candidate
        assert candidate["hardcoding_risk"] in {"low", "medium", "high"}
        trigger_text = json.dumps(candidate["triggering_conditions"]).lower()
        assert "query_id" not in trigger_text
        assert "prompt_id" not in trigger_text
        assert "exact prompt" not in trigger_text
    for row in risk_rows:
        assert row["uses_query_id_trigger"] is False
        assert row["uses_prompt_id_trigger"] is False
        assert row["uses_exact_prompt_text_trigger"] is False
        assert row["uses_gold_answer_text"] is False
    assert payload["cross_dataset_counterfactual_answer_sketches"]["report_only"] is True
    assert decision["runtime_change_applied"] is False
    assert decision["decision"] in {
        "no_runtime_change",
        "one_general_rule_ready_for_next_prompt",
        "multiple_candidates_need_manual_choice",
        "wait_for_adobe_access",
    }


def test_consolidated_reports_link_comprehensive_failure_analysis(tiny_project):
    _seed_all(tiny_project)
    run_comprehensive_failure_analysis(tiny_project)

    generate_consolidated_reports(tiny_project)

    index = json.loads((tiny_project.outputs_dir / "reports" / "report_index.json").read_text(encoding="utf-8"))
    assert "comprehensive_failure_analysis" in index
    analysis = index["comprehensive_failure_analysis"]
    assert analysis["official_row_failure_table_path"] == "outputs/reports/official_row_failure_table.md"
    assert analysis["generated_prompt_failure_table_path"] == "outputs/reports/generated_prompt_failure_table.md"
    assert analysis["runtime_change_applied"] is False
    assert analysis["generated_prompts_used_for"] == "generality_and_coverage_only"
