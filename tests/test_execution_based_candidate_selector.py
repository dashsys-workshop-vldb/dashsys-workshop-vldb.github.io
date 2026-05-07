from __future__ import annotations

from dashagent.execution_based_candidate_selector import (
    collect_candidate_gate_failures,
    evaluate_candidate_safety,
    holdout_regression_gate,
)


def _safe_row() -> dict:
    return {
        "query_id": "example_safe",
        "query": "How many batches finished yesterday?",
        "candidate_id": "endpoint_family_reranked",
        "candidate": {
            "rule_source": "reusable_domain_schema_endpoint_rule",
            "generalizable_family": "batch",
            "trigger_features": ["domain_vocabulary", "endpoint_catalog", "general_value_match"],
            "source_signals": ["endpoint_catalog", "domain_vocabulary"],
            "leakage_check_passed": True,
            "leakage_reasons": [],
        },
        "score_delta": 0.02,
        "correctness_delta": 0.0,
        "accuracy_relevant_change": True,
        "baseline_tokens": 1000,
        "token_delta": 0,
        "baseline_runtime": 1.0,
        "runtime_delta": 0.0,
        "tool_delta": 0,
        "final_answer_unsafe_drift": False,
        "sql_unsafe_drift": False,
        "api_unsafe_drift": False,
        "required_fields_preserved": True,
        "dry_run_labels_preserved": True,
        "evidence_label_loss": False,
        "live_api_evidence_fabricated": False,
        "sql_validation_ok": True,
        "sql_ast_valid": True,
        "api_validation_ok": True,
        "api_catalog_valid": True,
        "leakage_check_passed": True,
        "holdout_regression_passed": True,
    }


def test_selector_accepts_only_improving_clean_candidate():
    safe, reason = evaluate_candidate_safety(_safe_row())

    assert safe is True
    assert reason == ""


def test_selector_rejects_query_id_and_exact_query_triggers():
    row = _safe_row()
    row["candidate"] = {
        **row["candidate"],
        "trigger_features": [
            "example_safe",
            "How many batches finished yesterday?",
            "exact_public_entity",
        ],
    }

    failures = collect_candidate_gate_failures(row)

    assert "query_id_trigger" in failures
    assert "exact_full_query_string_trigger" in failures
    assert "exact_public_entity_without_general_value_match" in failures


def test_selector_rejects_invalid_sql_api_and_evidence_regressions():
    row = _safe_row()
    row.update(
        {
            "sql_validation_ok": False,
            "sql_ast_valid": False,
            "unknown_tables": ["Unknown table: dim_fake"],
            "unknown_columns": ["Unknown column: fake_col"],
            "destructive_sql_detected": True,
            "invalid_sql_detected": True,
            "api_validation_ok": False,
            "api_catalog_valid": False,
            "unresolved_api_placeholders": ["Endpoint path contains unresolved path parameters."],
            "invalid_api_detected": True,
            "dry_run_labels_preserved": False,
            "evidence_label_loss": True,
            "live_api_evidence_fabricated": True,
        }
    )

    failures = collect_candidate_gate_failures(row)

    assert "sql_validation_failed" in failures
    assert "sql_ast_invalid" in failures
    assert "unknown_tables_detected" in failures
    assert "unknown_columns_detected" in failures
    assert "destructive_sql_detected" in failures
    assert "invalid_sql_detected" in failures
    assert "api_validation_failed" in failures
    assert "api_catalog_invalid" in failures
    assert "unresolved_api_placeholders" in failures
    assert "invalid_api_detected" in failures
    assert "dry_run_labels_not_preserved" in failures
    assert "evidence_label_loss" in failures
    assert "live_api_evidence_fabricated" in failures


def test_selector_rejects_cost_regressions():
    row = _safe_row()
    row.update(
        {
            "score_delta": 0.01,
            "baseline_tokens": 100,
            "token_delta": 3,
            "baseline_runtime": 1.0,
            "runtime_delta": 0.11,
            "tool_delta": 1,
        }
    )

    failures = collect_candidate_gate_failures(row)

    assert "token_gate_failed" in failures
    assert "runtime_gate_failed" in failures
    assert "tool_increase_without_substantial_score_gain" in failures


def test_selector_rejects_hidden_style_regression():
    hidden_report = {
        "summary": {
            "total_cases": 48,
            "passed_cases": 47,
            "family_stability_rate": 0.99,
            "schema_stability_rate": 1.0,
        }
    }
    holdout = holdout_regression_gate(hidden_report, candidate_diversity_delta=-1)

    row = _safe_row()
    row["holdout_regression_passed"] = holdout["passed"]

    failures = collect_candidate_gate_failures(row)

    assert holdout["passed"] is False
    assert "hidden_style_not_48_48" in holdout["failed_checks"]
    assert "candidate_diversity_reduced" in holdout["failed_checks"]
    assert "holdout_regression_failed" in failures
