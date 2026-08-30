from __future__ import annotations

import json
from types import SimpleNamespace

from dashagent.candidate_context_builder import preserve_structural_relations
from dashagent.config import Config
from dashagent.query_tokens import extract_query_tokens
from dashagent.repair_candidate_selector_v3 import select_repair_candidate_v3
from dashagent.report_run import start_report_run
from scripts.run_ast_guided_sql_candidate_canary import _eligible_candidates, _row_safe as _ast_row_safe
from scripts.run_endpoint_schema_rule_canary import _summary as _endpoint_canary_summary
from scripts.generate_accuracy_promotion_decision_report import generate_accuracy_promotion_decision_report
from scripts.run_hidden_style_eval import HIDDEN_STYLE_CASES, run_hidden_style_eval


def test_accuracy_flags_default_off(monkeypatch, tiny_project):
    monkeypatch.delenv("ENABLE_ENDPOINT_SCHEMA_RULE_CANDIDATES", raising=False)
    monkeypatch.delenv("ENABLE_AST_GUIDED_SQL_TIEBREAK", raising=False)
    config = Config.from_env(tiny_project.project_root)

    assert config.enable_official_token_reduction is True
    assert config.enable_endpoint_schema_rule_candidates is False
    assert config.enable_ast_guided_sql_tiebreak is False
    assert config.enable_gated_risk_cluster_repair_execution is False
    assert config.enable_compact_context_when_schema_vote_safe is False


def test_accuracy_flags_env_enable(monkeypatch, tiny_project):
    monkeypatch.setenv("ENABLE_ENDPOINT_SCHEMA_RULE_CANDIDATES", "1")
    monkeypatch.setenv("ENABLE_AST_GUIDED_SQL_TIEBREAK", "1")

    config = Config.from_env(tiny_project.project_root)

    assert config.enable_endpoint_schema_rule_candidates is True
    assert config.enable_ast_guided_sql_tiebreak is True


def test_schema_dataset_hidden_case_expectations_not_weakened():
    case = next(case for case in HIDDEN_STYLE_CASES if case["case_id"] == "schema_dataset_b")

    assert "dim_blueprint" in case["expected_tables"]
    assert "dim_collection" in case["expected_tables"]


def test_schema_dataset_b_hidden_eval_reports_before_after_diagnostics(tiny_project):
    payload = run_hidden_style_eval(tiny_project)
    row = next(row for row in payload["rows"] if row["case_id"] == "schema_dataset_b")

    assert row["expected_schema_tables"] == row["expected_tables_checked"]
    assert "observed_schema_tables_before" in row
    assert "observed_schema_tables_after" in row
    assert "pass_fail_reason" in row
    assert set(row["expected_schema_tables"]).issubset(set(row["observed_schema_tables_after"]))
    assert row["passed"] is True


def test_schema_dataset_relation_preserves_full_relation_set():
    schema_index = SimpleNamespace(
        tables={
            "dim_blueprint": {},
            "dim_collection": {},
            "hkg_br_blueprint_collection": {},
        },
        join_hints=[],
    )
    tokens = extract_query_tokens("Find collections that use a schema called Loyalty Event")

    structural = preserve_structural_relations(tokens, ["dim_collection"], schema_index)

    assert {"dim_blueprint", "dim_collection", "hkg_br_blueprint_collection"}.issubset(set(structural["added_tables"]))


def test_endpoint_schema_canary_requires_measurable_improvement():
    tied_rows = [
        {
            "score_delta": 0.0,
            "correctness_delta": 0.0,
            "token_delta": 0,
            "runtime_delta": 0.0,
            "tool_delta": 0,
            "api_top_k_hit_before": True,
            "api_top_k_hit_after": True,
            "canary_safe_to_promote": True,
        }
    ]
    improved_rows = [{**tied_rows[0], "api_top_k_hit_before": False, "api_top_k_hit_after": True, "api_top_k_hit_delta": 1}]

    tied = _endpoint_canary_summary(tied_rows, hidden_gate_passed=True, leakage_ok=True, protected_unchanged=True)
    improved = _endpoint_canary_summary(improved_rows, hidden_gate_passed=True, leakage_ok=True, protected_unchanged=True)

    assert tied["recommendation"] == "keep_shadow_only"
    assert improved["recommendation"] == "safe_for_packaged_accuracy_trial"


def test_accuracy_decision_rejects_stale_hidden_style_by_default(tiny_project):
    start_report_run(tiny_project.outputs_dir)
    hidden_path = tiny_project.outputs_dir / "hidden_style_eval.json"
    hidden_path.write_text(
        json.dumps(
            {
                "run_id": "old",
                "generated_at": "2026-01-01T00:00:00+00:00",
                "summary": {
                    "total_cases": 48,
                    "passed_cases": 48,
                    "failed_cases": 0,
                    "family_stability_rate": 1.0,
                    "schema_stability_rate": 1.0,
                },
                "rows": [
                    {
                        "case_id": "schema_dataset_b",
                        "expected_schema_tables": ["dim_blueprint", "dim_collection"],
                        "observed_schema_tables_before": ["dim_collection"],
                        "observed_schema_tables_after": ["dim_blueprint", "dim_collection"],
                        "pass_fail_reason": "ok",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    try:
        generate_accuracy_promotion_decision_report(tiny_project)
    except RuntimeError as exc:
        assert "hidden_style_eval.run_id_stale" in str(exc)
    else:
        raise AssertionError("accuracy decision should reject stale hidden_style_eval by default")


def test_accuracy_decision_allow_stale_is_non_promotional(tiny_project):
    start_report_run(tiny_project.outputs_dir)
    hidden_path = tiny_project.outputs_dir / "hidden_style_eval.json"
    hidden_path.write_text(json.dumps({"run_id": "old", "summary": {}, "rows": []}), encoding="utf-8")

    payload = generate_accuracy_promotion_decision_report(tiny_project, allow_stale=True)

    assert payload["freshness"]["fresh"] is False
    assert payload["freshness"]["stale_allowed"] is True
    assert payload["summary"]["recommendation"] == "do_not_submit_until_regression_fixed"


def test_ast_guided_candidates_reject_unknown_schema():
    candidates = [
        {"parsed_ok": True, "unknown_tables": [], "unknown_columns": [], "destructive_sql_detected": False, "answer_shape_match": True},
        {"parsed_ok": True, "unknown_tables": ["missing_table"], "unknown_columns": [], "destructive_sql_detected": False, "answer_shape_match": True},
    ]

    eligible = _eligible_candidates(candidates)

    assert candidates[0] in eligible
    assert candidates[1] not in eligible


def test_ast_row_safe_rejects_invalid_or_unknown_selection():
    row = {
        "score_delta": 0.0,
        "correctness_delta": 0.0,
        "token_delta": 0,
        "runtime_delta": 0.0,
        "tool_delta": 0,
        "answer_changed": False,
        "api_changed": False,
        "sql_changed": False,
        "invalid_sql_selected": False,
        "unknown_schema_selected": True,
        "destructive_sql_selected": False,
        "live_api_evidence_fabricated": False,
        "dry_run_labels_preserved": True,
        "protected_hashes_unchanged": True,
    }

    safe, reason = _ast_row_safe(row)

    assert safe is False
    assert "unknown_schema_selected" in reason


def test_repair_selector_v3_keeps_current_for_zero_delta_and_rejects_regression():
    safety = {"safe": True, "failed_checks": []}
    current = {"sql": ["SELECT 1"], "api_calls": [], "tool_call_count": 1, "final_answer": "one"}
    tied = {"sql": ["SELECT 2"], "api_calls": [], "tool_call_count": 1, "final_answer": "two", "offline_score_delta": 0.0, "fusion_agreement": True}
    worse = {**tied, "offline_score_delta": -0.1}

    tie_decision = select_repair_candidate_v3(current, tied, None, safety, ast_current={"ast_quality_score": 1}, ast_repaired={"parsed_ok": True, "ast_quality_score": 1})
    worse_decision = select_repair_candidate_v3(current, worse, None, safety, ast_current={"ast_quality_score": 1}, ast_repaired={"parsed_ok": True, "ast_quality_score": 1})

    assert tie_decision["selected_plan"] == "current"
    assert tie_decision["decision_label"] == "score_tie_keep_current"
    assert worse_decision["selected_plan"] == "current"
    assert "score_regression" in worse_decision["failed_checks"]
