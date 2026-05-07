from __future__ import annotations

import json

from dashagent.config import Config
from dashagent.evidence_aware_answer_composer import compose_evidence_aware_answer
from dashagent.local_knowledge_index import requested_fact_coverage
from dashagent.report_run import report_metadata, start_report_run
from dashagent.targeted_candidate_generator import TargetedCandidate, apply_leakage_checks, generate_targeted_candidates
from scripts.generate_score_component_error_report import generate_score_component_error_report
from scripts.generate_0_7_score_push_report import generate_score_push_report
from scripts.generate_low_score_failure_mining_report import generate_low_score_failure_mining_report
from scripts.package_query_outputs import NON_SUBMISSION_OUTPUT_DIRS, discover_query_output_dirs
from scripts.run_evidence_answer_candidate_eval import run_evidence_answer_candidate_eval
from scripts.run_execution_candidate_search import run_execution_candidate_search
from scripts.run_local_index_fact_coverage_report import run_local_index_fact_coverage_report
from scripts.run_llm_candidate_search import run_llm_candidate_search
from scripts.run_targeted_accuracy_packaged_trial import run_targeted_accuracy_packaged_trial


def _write_score_push_inputs(config: Config) -> Path:
    start_report_run(config.outputs_dir)
    output_dir = config.outputs_dir / "eval" / "tiny_001" / "sql_first_api_verify"
    output_dir.mkdir(parents=True, exist_ok=True)
    trajectory = {
        "query_id": "tiny_001",
        "original_query": "How many campaigns are there?",
        "strategy": "SQL_FIRST_API_VERIFY",
        "route_type": "SQL",
        "domain_type": "campaign",
        "steps": [
            {
                "kind": "sql_call",
                "sql": "SELECT COUNT(*) AS count FROM dim_campaign",
                "validation": {"ok": True},
                "result": {"ok": True, "rows": [{"count": 2}], "row_count": 1, "limited": False},
            }
        ],
        "final_answer": "The database count is 2.",
        "runtime": 0.01,
        "tool_call_count": 1,
        "sql_call_count": 1,
        "api_call_count": 0,
        "estimated_tokens": 100,
        "errors": [],
    }
    (output_dir / "metadata.json").write_text(json.dumps({"query_id": "tiny_001"}), encoding="utf-8")
    (output_dir / "filled_system_prompt.txt").write_text("prompt", encoding="utf-8")
    (output_dir / "trajectory.json").write_text(json.dumps(trajectory), encoding="utf-8")
    strict = {
        "rows": [
            {
                "query_id": "tiny_001",
                "query": "How many campaigns are there?",
                "strategy": "SQL_FIRST_API_VERIFY",
                "output_dir": str(output_dir),
                "final_score": 0.5,
                "correctness_score": 0.55,
                "answer_score": 0.5,
                "sql_score": 0.5,
                "api_score": None,
                "tool_call_count": 1,
                "estimated_tokens": 100,
                "runtime": 0.01,
                "sql_call_count": 1,
                "api_call_count": 0,
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
    (config.outputs_dir / "eval_results_strict.json").write_text(json.dumps(strict), encoding="utf-8")
    hidden = {
        **report_metadata(config.outputs_dir),
        "summary": {
            "total_cases": 48,
            "passed_cases": 48,
            "failed_cases": 0,
            "family_stability_rate": 1.0,
            "schema_stability_rate": 1.0,
        },
        "rows": [],
    }
    (config.outputs_dir / "hidden_style_eval.json").write_text(json.dumps(hidden), encoding="utf-8")
    for name in [
        "candidate_context_report.json",
        "endpoint_family_failure_report.json",
        "sql_ast_candidate_ranking_report.json",
        "shadow_repair_eval.json",
    ]:
        (config.outputs_dir / name).write_text(json.dumps({"rows": [], "summary": {}}), encoding="utf-8")
    final_submission = config.outputs_dir / "final_submission"
    final_submission.mkdir(exist_ok=True)
    return output_dir


def test_targeted_accuracy_flag_defaults_and_env(monkeypatch, tiny_project):
    monkeypatch.delenv("ENABLE_TARGETED_ACCURACY_RULES", raising=False)
    assert Config.from_env(tiny_project.project_root).enable_targeted_accuracy_rules is False
    monkeypatch.setenv("ENABLE_TARGETED_ACCURACY_RULES", "1")
    assert Config.from_env(tiny_project.project_root).enable_targeted_accuracy_rules is True


def test_targeted_candidate_leakage_rejects_memorized_triggers():
    candidate = TargetedCandidate(
        candidate_id="bad",
        generation_reason="bad",
        sql="SELECT 1",
        api_call=None,
        expected_answer_shape="count",
        endpoint_family="test",
        schema_family="test",
        source_signals=["gold_api_path"],
        trigger_features=["query_id", "exact_full_query_string", "memorized_expected_answer", "exact_public_entity"],
    )

    checked = apply_leakage_checks(candidate, query="How many campaigns are there?")

    assert checked.leakage_check_passed is False
    assert any("query_id" in reason for reason in checked.leakage_reasons)
    assert "exact_public_entity_without_general_value_match" in checked.leakage_reasons


def test_candidate_generator_exposes_generalizable_fields(tiny_project):
    _write_score_push_inputs(tiny_project)
    from dashagent.executor import AgentExecutor

    executor = AgentExecutor(tiny_project)
    trajectory = json.loads((tiny_project.outputs_dir / "eval" / "tiny_001" / "sql_first_api_verify" / "trajectory.json").read_text())
    candidates = generate_targeted_candidates(
        query_id="tiny_001",
        query="How many campaigns are there?",
        baseline_trajectory=trajectory,
        schema_index=executor.schema_index,
        endpoint_catalog=executor.endpoint_catalog,
    )

    assert candidates
    for candidate in candidates:
        assert candidate["rule_source"]
        assert candidate["trigger_features"]
        assert "query_id" not in candidate["trigger_features"]
        assert candidate["leakage_check_passed"] is True
        assert candidate["generalizable_family"]


def test_low_score_failure_mining_report_fields_and_gap(tiny_project):
    _write_score_push_inputs(tiny_project)

    payload = generate_low_score_failure_mining_report(tiny_project)

    assert payload["rows"][0]["query_id"] == "tiny_001"
    assert payload["rows"][0]["likely_failure_type"]
    assert payload["summary"]["score_needed_to_reach_0_70_total"] == 0.2
    assert payload["summary"]["top_10_target_rows"] == ["tiny_001"]
    assert payload["packaged_execution_changed"] is False


def test_score_component_error_report_prioritizes_api_correct_answer_weak(tiny_project):
    _write_score_push_inputs(tiny_project)
    strict = json.loads((tiny_project.outputs_dir / "eval_results_strict.json").read_text())
    strict["rows"][0]["api_score"] = 1.0
    strict["rows"][0]["answer_score"] = 0.1
    (tiny_project.outputs_dir / "eval_results_strict.json").write_text(json.dumps(strict), encoding="utf-8")

    payload = generate_score_component_error_report(tiny_project)

    assert payload["rows"][0]["likely_bottleneck"] == "api_correct_answer_weak"
    assert payload["summary"]["api_correct_answer_weak_rows"] == 1
    assert payload["packaged_execution_changed"] is False


def test_evidence_aware_answer_does_not_fabricate_dry_run_payload_values():
    trajectory = {
        "steps": [
            {
                "kind": "api_call",
                "method": "GET",
                "url": "/data/foundation/catalog/batches/01ABCDEFABCDEFABCDEFABCDEF",
                "params": {},
                "result": {
                    "dry_run": True,
                    "result_preview": {"status": "FORGED_STATUS", "count": 999},
                },
            }
        ]
    }

    candidate = compose_evidence_aware_answer("Show the details of batch 01ABCDEFABCDEFABCDEFABCDEF.", trajectory)

    assert "FORGED_STATUS" not in candidate.answer
    assert "999" not in candidate.answer
    assert "unavailable in dry-run mode" in candidate.answer
    assert candidate.no_fabrication_checks["dry_run_payload_values_used"] is False


def test_evidence_answer_eval_preserves_sql_and_api(tiny_project):
    _write_score_push_inputs(tiny_project)
    strict = json.loads((tiny_project.outputs_dir / "eval_results_strict.json").read_text())
    strict["rows"][0]["api_score"] = 1.0
    strict["rows"][0]["answer_score"] = 0.1
    strict["rows"][0]["query"] = "How many campaigns are there?"
    (tiny_project.outputs_dir / "eval_results_strict.json").write_text(json.dumps(strict), encoding="utf-8")

    payload = run_evidence_answer_candidate_eval(tiny_project)

    assert payload["packaged_execution_changed"] is False
    assert payload["rows"][0]["selected_sql_unchanged"] is True
    assert payload["rows"][0]["selected_api_unchanged"] is True
    assert (tiny_project.outputs_dir / "evidence_answer_candidate_eval" / "tiny_001" / "answer_only").exists()


def test_local_fact_coverage_reports_requested_fact_and_used_fields(tiny_project):
    _write_score_push_inputs(tiny_project)

    payload = run_local_index_fact_coverage_report(tiny_project)
    row = payload["rows"][0]

    assert "local_evidence_available" in row
    assert "local_evidence_used_in_final_answer" in row
    assert "requested_fact_covered" in row
    assert "score_delta_from_local_evidence" in row
    assert payload["summary"]["data_json_used_for_runtime"] is False


def test_requested_fact_coverage_matches_status_column():
    hits = [
        {
            "evidence_id": "e1",
            "source_table": "dim_campaign",
            "source_column": "status",
            "columns": ["status"],
            "matched_value": "published",
            "values": {"status": "published"},
        }
    ]
    coverage = requested_fact_coverage("What is the status of Welcome Journey?", hits)

    assert coverage["requested_fact_type"] == "status"
    assert coverage["requested_fact_covered"] is True


def test_execution_candidate_search_isolated_and_shadow_only(tiny_project):
    _write_score_push_inputs(tiny_project)

    payload = run_execution_candidate_search(tiny_project)

    assert payload["packaged_execution_changed"] is False
    assert payload["summary"]["recommendation"] in {"keep_shadow_only", "safe_for_targeted_packaged_trial"}
    assert (tiny_project.outputs_dir / "execution_candidate_search" / "tiny_001").exists()
    assert "execution_candidate_search" in NON_SUBMISSION_OUTPUT_DIRS
    assert not discover_query_output_dirs(tiny_project.outputs_dir / "execution_candidate_search")


def test_targeted_accuracy_packaged_trial_skips_without_safe_candidates(tiny_project):
    _write_score_push_inputs(tiny_project)
    search = {
        **report_metadata(tiny_project.outputs_dir),
        "rows": [{"query_id": "tiny_001", "safe_for_packaged_trial": False}],
        "summary": {"recommendation": "keep_shadow_only"},
    }
    (tiny_project.outputs_dir / "execution_candidate_search.json").write_text(json.dumps(search), encoding="utf-8")

    payload = run_targeted_accuracy_packaged_trial(tiny_project)

    assert payload["summary"]["recommendation"] == "keep_shadow_only"
    assert payload["packaged_execution_changed"] is False
    assert not discover_query_output_dirs(tiny_project.outputs_dir / "targeted_accuracy_packaged_trial")


def test_llm_candidate_search_skips_without_keys(monkeypatch, tiny_project):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    payload = run_llm_candidate_search(tiny_project)

    assert payload["summary"]["status"] == "skipped_no_llm_key"
    assert payload["summary"]["recommendation"] == "keep_shadow_only"


def test_llm_candidate_search_categorizes_provider_errors(monkeypatch, tiny_project):
    _write_score_push_inputs(tiny_project)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")

    class FakeClient:
        def available(self):
            return True

        def model_name(self):
            return "fake/model"

        def generate_messages(self, messages):
            return {"ok": False, "error": "model unavailable"}

    monkeypatch.setattr("scripts.run_llm_candidate_search.get_llm_client", lambda provider=None: FakeClient())
    payload = run_llm_candidate_search(tiny_project)

    assert payload["summary"]["status"] == "completed"
    assert payload["summary"]["failure_category_counts"]["provider_error"] == 1


def test_score_push_report_prefers_current_when_no_safe_improvement(tiny_project):
    _write_score_push_inputs(tiny_project)
    for name, payload in {
        "low_score_failure_mining_report.json": {"summary": {"score_needed_to_reach_0_70_total": 0.2}},
        "execution_candidate_search.json": {"summary": {"safe_rows": 0, "recommendation": "keep_shadow_only"}},
        "llm_candidate_search.json": {"summary": {"status": "skipped_no_llm_key", "recommendation": "keep_shadow_only"}},
        "targeted_accuracy_packaged_trial.json": {"summary": {"strict_final_score": 0.5, "recommendation": "keep_shadow_only"}},
    }.items():
        (tiny_project.outputs_dir / name).write_text(json.dumps(payload), encoding="utf-8")

    payload = generate_score_push_report(tiny_project)

    assert payload["summary"]["target_0_70_reached"] is False
    assert payload["summary"]["final_recommendation"] == "submit_current_official_token_reduction_version"
