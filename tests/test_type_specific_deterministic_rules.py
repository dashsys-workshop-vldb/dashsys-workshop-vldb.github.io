from __future__ import annotations

import json
from pathlib import Path

from scripts.generate_consolidated_reports import generate_consolidated_reports
from scripts.run_deterministic_prompt_type_audit import run_deterministic_prompt_type_audit
from scripts.run_type_specific_deterministic_rule_trials import run_type_specific_deterministic_rule_trials


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _write_md(path: Path, text: str = "# report\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _seed_type_specific_inputs(outputs: Path) -> None:
    reports = outputs / "reports"
    official_rows = [
        {
            "row_id": "example_count",
            "example_id": "example_count",
            "prompt": "How many active audiences are there?",
            "predicted_route": "SQL_THEN_API",
            "predicted_domain": "SEGMENT_AUDIENCE",
            "answer_intent": "COUNT",
            "strategy": "SQL_FIRST_API_VERIFY",
            "total_strict_score": 0.54,
            "answer_score": 0.2,
            "sql_score": 1.0,
            "api_score": 1.0,
            "sql_calls": 1,
            "sql_returned_row_count": 1,
            "sql_evidence_fields": ["count"],
            "api_calls": 1,
            "api_state": "dry_run_unavailable",
            "final_answer": "Active audiences were found locally; live API verification was unavailable.",
            "failure_classification": {
                "answer_missing_count": True,
                "api_required_but_dry_run": True,
                "live_api_blocked": True,
                "dry_run_caveat_dominates_sql_answer": True,
            },
            "likely_primary_cause": "live_api_blocked",
            "requires_live_api": True,
            "locally_fixable_now": True,
            "general_rule_possible": True,
        },
        {
            "row_id": "example_list",
            "example_id": "example_list",
            "prompt": "List active segment names.",
            "predicted_route": "LOCAL_DB_ONLY",
            "predicted_domain": "SEGMENT_AUDIENCE",
            "answer_intent": "LIST",
            "strategy": "SQL_FIRST_API_VERIFY",
            "total_strict_score": 0.76,
            "answer_score": 0.45,
            "sql_score": 1.0,
            "api_score": None,
            "sql_calls": 1,
            "sql_returned_row_count": 2,
            "sql_evidence_fields": ["name", "segment_id"],
            "api_calls": 0,
            "api_state": "none",
            "final_answer": "Matching segments exist locally.",
            "failure_classification": {
                "answer_missing_name_or_id": True,
                "sql_correct_but_answer_weak": True,
            },
            "likely_primary_cause": "answer_missing_name_or_id",
            "requires_live_api": False,
            "locally_fixable_now": True,
            "general_rule_possible": True,
        },
        {
            "row_id": "example_zero",
            "example_id": "example_zero",
            "prompt": "Show missing flow runs.",
            "predicted_route": "LOCAL_DB_ONLY",
            "predicted_domain": "DATAFLOW_RUN",
            "answer_intent": "LIST",
            "strategy": "SQL_FIRST_API_VERIFY",
            "total_strict_score": 0.66,
            "answer_score": 0.3,
            "sql_score": 1.0,
            "api_score": None,
            "sql_calls": 1,
            "sql_returned_row_count": 0,
            "sql_evidence_fields": [],
            "api_calls": 0,
            "api_state": "none",
            "final_answer": "There is no data.",
            "failure_classification": {"zero_row_answer_unclear": True},
            "likely_primary_cause": "zero_row_answer_unclear",
            "requires_live_api": False,
            "locally_fixable_now": True,
            "general_rule_possible": True,
        },
    ]
    generated_rows = [
        {
            "prompt_id": "gen_count_1",
            "prompt": "How many active audiences exist?",
            "generation_type": "paraphrase",
            "expected_label": "SQL_PLUS_API",
            "expected_domain": "segment_audience",
            "expected_intent": "COUNT",
            "actual_route": "SQL_THEN_API",
            "actual_domain": "SEGMENT_AUDIENCE",
            "actual_answer_intent": "COUNT",
            "answer_family": "segment_count",
            "strategy": "SQL_FIRST_API_VERIFY",
            "sql_calls": 1,
            "sql_row_count": 1,
            "sql_result_shape": {"fields": ["count"], "zero_row": False},
            "dry_run_api_calls": 1,
            "api_state": "dry_run_unavailable",
            "final_answer": "Active audiences exist locally; live API unavailable.",
            "zero_row_sql": False,
            "requires_live_api": False,
            "missing_count_or_name_advisory": True,
            "answer_too_vague_heuristic": False,
            "route_mismatch": False,
            "domain_mismatch": False,
            "answer_intent_mismatch": False,
            "likely_issue_type": "answer_template_gap",
            "supports_general_rule": True,
            "diagnostic_only": True,
        },
        {
            "prompt_id": "gen_list_1",
            "prompt": "Show active segment names.",
            "generation_type": "paraphrase",
            "expected_label": "SQL_PLUS_API",
            "expected_domain": "segment_audience",
            "expected_intent": "LIST",
            "actual_route": "SQL_THEN_API",
            "actual_domain": "SEGMENT_AUDIENCE",
            "actual_answer_intent": "LIST",
            "answer_family": "segment_list",
            "strategy": "SQL_FIRST_API_VERIFY",
            "sql_calls": 1,
            "sql_row_count": 2,
            "sql_result_shape": {"fields": ["name", "segment_id"], "zero_row": False},
            "dry_run_api_calls": 1,
            "api_state": "dry_run_unavailable",
            "final_answer": "Segments exist locally; live API unavailable.",
            "zero_row_sql": False,
            "requires_live_api": False,
            "missing_count_or_name_advisory": True,
            "answer_too_vague_heuristic": True,
            "route_mismatch": False,
            "domain_mismatch": False,
            "answer_intent_mismatch": False,
            "likely_issue_type": "answer_template_gap",
            "supports_general_rule": True,
            "diagnostic_only": True,
        },
        {
            "prompt_id": "gen_zero_1",
            "prompt": "Show missing flow runs.",
            "generation_type": "edge_case",
            "expected_label": "SQL_PLUS_API",
            "expected_domain": "dataflow_run",
            "expected_intent": "LIST",
            "actual_route": "SQL_THEN_API",
            "actual_domain": "DATAFLOW_RUN",
            "actual_answer_intent": "LIST",
            "answer_family": "dataflow_list",
            "strategy": "SQL_FIRST_API_VERIFY",
            "sql_calls": 1,
            "sql_row_count": 0,
            "sql_result_shape": {"fields": [], "zero_row": True},
            "dry_run_api_calls": 0,
            "api_state": "none",
            "final_answer": "There is no data.",
            "zero_row_sql": True,
            "requires_live_api": False,
            "missing_count_or_name_advisory": False,
            "answer_too_vague_heuristic": True,
            "route_mismatch": False,
            "domain_mismatch": False,
            "answer_intent_mismatch": False,
            "likely_issue_type": "zero_row_clarity_gap",
            "supports_general_rule": True,
            "diagnostic_only": True,
        },
        {
            "prompt_id": "gen_route_1",
            "prompt": "Audience membership overview.",
            "generation_type": "synonym",
            "expected_label": "SQL_PLUS_API",
            "expected_domain": "segment_audience",
            "expected_intent": "LIST",
            "actual_route": "LOCAL_DB_ONLY",
            "actual_domain": "UNKNOWN",
            "actual_answer_intent": "UNKNOWN",
            "answer_family": "unknown",
            "strategy": "SQL_FIRST_API_VERIFY",
            "sql_calls": 0,
            "sql_row_count": None,
            "sql_result_shape": {"fields": [], "zero_row": False},
            "dry_run_api_calls": 0,
            "api_state": "none",
            "final_answer": "I do not have enough local evidence.",
            "zero_row_sql": False,
            "requires_live_api": False,
            "missing_count_or_name_advisory": False,
            "answer_too_vague_heuristic": True,
            "route_mismatch": True,
            "domain_mismatch": True,
            "answer_intent_mismatch": True,
            "likely_issue_type": "router_gap",
            "supports_general_rule": False,
            "diagnostic_only": True,
        },
    ]
    _write_json(
        reports / "official_row_failure_table.json",
        {"report_type": "official_row_failure_table", "summary": {"total_rows": 3}, "rows": official_rows},
    )
    _write_md(reports / "official_row_failure_table.md")
    _write_json(
        reports / "generated_prompt_failure_table.json",
        {
            "report_type": "generated_prompt_failure_table",
            "diagnostic_only": True,
            "official_score_claim": False,
            "summary": {"total_prompts": 4},
            "rows": generated_rows,
        },
    )
    _write_md(reports / "generated_prompt_failure_table.md")
    _write_json(
        reports / "cross_dataset_failure_clusters.json",
        {"report_type": "cross_dataset_failure_clusters", "clusters": []},
    )
    _write_json(
        reports / "general_deterministic_rule_candidates.json",
        {"report_type": "general_deterministic_rule_candidates", "candidates": []},
    )
    _write_json(
        reports / "generated_prompt_suite_local_diagnostic.json",
        {"report_type": "generated_prompt_suite_local_diagnostic", "diagnostic_only": True, "rows": generated_rows},
    )
    _write_json(
        outputs / "eval_results_strict.json",
        {
            "rows": [
                {
                    "query_id": row["row_id"],
                    "strategy": "SQL_FIRST_API_VERIFY",
                    "final_score": row["total_strict_score"],
                    "answer_score": row["answer_score"],
                    "sql_score": row["sql_score"],
                    "api_score": row["api_score"],
                    "runtime": 0.02,
                    "estimated_tokens": 800,
                    "tool_call_count": row["sql_calls"] + row["api_calls"],
                }
                for row in official_rows
            ],
            "summary": {"by_strategy": {"SQL_FIRST_API_VERIFY": {"avg_final_score": 0.6533}}},
        },
    )
    for name in [
        "system_summary",
        "accuracy_and_bottleneck_summary",
        "report_index",
        "adobe_access_waiting_status",
        "live_api_full_run_blocker",
    ]:
        _write_json(reports / f"{name}.json", {"report_type": name})
        _write_md(reports / f"{name}.md")


def test_prompt_type_audit_assigns_taxonomy_buckets(tiny_project):
    _seed_type_specific_inputs(tiny_project.outputs_dir)

    payload = run_deterministic_prompt_type_audit(tiny_project)

    reports = tiny_project.outputs_dir / "reports"
    assert (reports / "deterministic_prompt_type_audit.json").exists()
    assert (reports / "deterministic_prompt_type_audit.md").exists()
    assert payload["diagnostic_only"] is True
    assert payload["official_row_count"] == 3
    assert payload["generated_prompt_count"] == 4
    for row in payload["official_rows"]:
        assert row["prompt_intent"] in {"count", "list/name/id", "status", "timestamp/date/when", "yes/no", "compare", "explain", "unknown/ambiguous"}
        assert row["domain_bucket"]
        assert row["execution_need"]
        assert row["evidence_shape"]
    for row in payload["generated_prompt_rows"]:
        assert row["diagnostic_only"] is True
        assert row["generated_prompt_usage"] == "generality_and_speed_evidence_only"
    assert payload["buckets"]
    assert any(bucket["deterministic_fast_path_possible"] for bucket in payload["buckets"])


def test_type_specific_candidates_are_general_and_multi_family(tiny_project):
    _seed_type_specific_inputs(tiny_project.outputs_dir)
    run_deterministic_prompt_type_audit(tiny_project)

    trials = run_type_specific_deterministic_rule_trials(tiny_project)

    candidate_report = json.loads(
        (tiny_project.outputs_dir / "reports" / "type_specific_deterministic_rule_candidates.json").read_text(encoding="utf-8")
    )
    families = {candidate["rule_family"] for candidate in candidate_report["candidates"]}
    assert {"sql_only_fast_path", "count_answer_fast_path", "list_name_id_answer_fast_path", "zero_row_local_evidence_fast_path"}.issubset(families)
    for candidate in candidate_report["candidates"]:
        trigger_text = json.dumps(candidate["trigger_signals"]).lower()
        assert "query_id" not in trigger_text
        assert "prompt_id" not in trigger_text
        assert "exact prompt" not in trigger_text
        assert candidate["hardcoding_risk"] in {"low", "medium", "high"}
        assert candidate["recommendation"] in {
            "trial_next",
            "implement_next_if_trial_passes",
            "wait_for_adobe_access",
            "reject",
            "speed_safe_candidate",
            "keep_analysis_only",
        }
    assert trials["diagnostic_only"] is True


def test_type_specific_trials_are_isolated_and_record_metrics(tiny_project):
    _seed_type_specific_inputs(tiny_project.outputs_dir)
    before_eval = (tiny_project.outputs_dir / "eval_results_strict.json").read_text(encoding="utf-8")
    run_deterministic_prompt_type_audit(tiny_project)

    payload = run_type_specific_deterministic_rule_trials(tiny_project)

    after_eval = (tiny_project.outputs_dir / "eval_results_strict.json").read_text(encoding="utf-8")
    assert after_eval == before_eval
    assert payload["writes_eval_outputs"] is False
    assert payload["writes_final_submission"] is False
    assert payload["runtime_change_applied"] is False
    assert payload["trial_reports"]
    for trial in payload["trial_reports"]:
        assert trial["trial_type"] in {
            "answer_only_trial",
            "route_only_shadow_trial",
            "api_skip_shadow_trial",
            "fast_path_runtime_simulation",
            "combined_safe_bucket_trial",
        }
        assert "projected_strict_score" in trial
        assert "runtime_delta" in trial
        assert "token_delta" in trial
        assert "tool_call_delta" in trial
        assert "api_dry_run_call_reduction" in trial
        assert (tiny_project.outputs_dir / "type_specific_deterministic_rule_trials" / trial["rule_family"]).exists()
    decision = json.loads(
        (tiny_project.outputs_dir / "reports" / "type_specific_rule_fix_decision.json").read_text(encoding="utf-8")
    )
    assert decision["decision"] in {
        "no_runtime_change",
        "one_rule_ready",
        "small_batch_ready",
        "speed_only_candidate",
        "wait_for_adobe_access",
        "more_manual_review_needed",
    }
    assert decision["runtime_change_applied"] is False


def test_consolidated_reports_link_type_specific_rule_reports(tiny_project):
    _seed_type_specific_inputs(tiny_project.outputs_dir)
    run_deterministic_prompt_type_audit(tiny_project)
    run_type_specific_deterministic_rule_trials(tiny_project)

    generate_consolidated_reports(tiny_project)

    index = json.loads((tiny_project.outputs_dir / "reports" / "report_index.json").read_text(encoding="utf-8"))
    assert "type_specific_deterministic_rules" in index
    section = index["type_specific_deterministic_rules"]
    assert section["prompt_type_audit_path"] == "outputs/reports/deterministic_prompt_type_audit.md"
    assert section["rule_candidates_path"] == "outputs/reports/type_specific_deterministic_rule_candidates.md"
    assert section["rule_trials_path"] == "outputs/reports/type_specific_deterministic_rule_trials.md"
    assert section["fix_decision_path"] == "outputs/reports/type_specific_rule_fix_decision.md"
    assert section["runtime_change_applied"] is False
