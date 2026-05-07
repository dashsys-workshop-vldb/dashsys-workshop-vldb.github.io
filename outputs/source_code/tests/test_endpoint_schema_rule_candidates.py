from __future__ import annotations

from types import SimpleNamespace

from dashagent.endpoint_schema_rule_candidates import candidate_rules, leakage_safe_candidate_rules, validate_rule_leakage
from scripts.run_endpoint_schema_rule_candidate_eval import _gold_in_top_k, run_endpoint_schema_rule_candidate_eval


def test_endpoint_schema_rules_are_reusable_and_dependency_declared():
    rules = candidate_rules()

    assert len(rules) >= 16
    assert all(rule.dependency_branches == ("codex/score075-robustness-leakage",) for rule in rules)
    assert all(rule.trigger_features for rule in rules)
    assert all(rule.generalizable_family for rule in rules)
    assert {rule.rule_id for rule in leakage_safe_candidate_rules()} == {rule.rule_id for rule in rules}


def test_endpoint_schema_leakage_guard_rejects_overfit_triggers():
    safe = validate_rule_leakage(
        {
            "rule_id": "safe_schema_dataset_relation",
            "trigger_terms": ["datasets using schema", "collections built from schema"],
            "source": "domain vocabulary + endpoint catalog metadata",
        }
    )
    unsafe = validate_rule_leakage(
        {
            "rule_id": "example_007_fix",
            "trigger_terms": ["List all datasets that use the schema hkg_adls_profile_count_history"],
            "source": "query_id branch with gold API path and memorized answer",
        }
    )

    assert safe["passed"] is True
    assert unsafe["passed"] is False
    assert "public_eval_example_id" in unsafe["rejection_reasons"]
    assert "query_id_trigger" in unsafe["rejection_reasons"]
    assert "gold_api_trigger" in unsafe["rejection_reasons"]
    assert "memorized_answer_trigger" in unsafe["rejection_reasons"]


def test_gold_top_k_matcher_uses_catalog_paths_offline_only():
    endpoints = [
        SimpleNamespace(id="unified_tags", path="/unifiedtags/tags"),
        SimpleNamespace(id="unified_tag_detail", path="/unifiedtags/tags/{tag_id}"),
        SimpleNamespace(id="observability_metrics", path="/data/infrastructure/observability/insights/metrics"),
    ]

    assert _gold_in_top_k(["GET /unifiedtags/tags/51175a7f"], ["unified_tag_detail"], endpoints) is True
    assert _gold_in_top_k(["GET /unifiedtags/tags/51175a7f"], ["unified_tags"], endpoints) is False
    assert _gold_in_top_k(["POST /data/infrastructure/observability/insights/metrics body={}"], ["observability_metrics"], endpoints) is True


def test_endpoint_schema_candidate_eval_reports_leakage_metadata(tiny_project):
    payload = run_endpoint_schema_rule_candidate_eval(tiny_project)

    assert payload["report_only"] is True
    assert payload["gold_used_for_generation"] is False
    assert payload["public_query_strings_used_for_generation"] is False
    assert payload["summary"]["candidate_rules"] >= 16
    for row in payload["rows"]:
        assert row["rule_source"]
        assert row["trigger_features"]
        assert row["generalizable_family"]
        assert row["declared_dependencies"] == ["codex/score075-robustness-leakage"]
        assert row["uses_query_id_trigger"] is False
        assert row["uses_exact_public_query_trigger"] is False
        assert row["uses_gold_api_or_sql_trigger"] is False
        assert row["uses_memorized_answer_trigger"] is False
        assert row["leakage_check_result"]["passed"] is True
