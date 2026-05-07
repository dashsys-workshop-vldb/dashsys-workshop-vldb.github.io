from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from dashagent.answer_synthesizer import synthesize_answer
from dashagent.execution_based_candidate_selector import evaluate_candidate_safety, holdout_regression_gate
from dashagent.targeted_candidate_generator import TargetedCandidate, apply_leakage_checks, generate_targeted_candidates
from scripts.run_execution_candidate_search import run_execution_candidate_search
from scripts.run_hidden_style_eval import run_hidden_style_eval


FORBIDDEN_TRIGGER_FEATURES = {
    "query_id",
    "exact_full_query_string",
    "manual_expected_answer",
    "memorized_expected_answer",
    "manual_memorized_expected_answer",
    "manual_gold_sql",
    "manual_gold_api",
    "memorized_gold_sql",
    "memorized_gold_api",
    "gold_sql_path",
    "gold_api_path",
}


def test_score075_leakage_rejects_query_id_exact_query_gold_and_memorized_triggers():
    query = "How many campaigns are there?"
    candidate = TargetedCandidate(
        candidate_id="bad_memorized_candidate",
        generation_reason="bad",
        sql="SELECT 1",
        api_call={"method": "GET", "path": "/gold/path", "params": {}},
        expected_answer_shape="count",
        endpoint_family="campaign",
        schema_family="campaign",
        source_signals=["schema_metadata", "gold_api_path"],
        trigger_features=[
            "query_id",
            "exact_full_query_string",
            "manual_expected_answer",
            "manual_gold_api",
            "memorized_gold_sql",
            "exact_public_entity",
            query,
        ],
        generalizable_family="campaign",
    )

    checked = apply_leakage_checks(candidate, query=query)

    assert checked.leakage_check_passed is False
    assert "blocked_trigger:query_id" in checked.leakage_reasons
    assert "blocked_trigger:exact_full_query_string" in checked.leakage_reasons
    assert "blocked_trigger:manual_expected_answer" in checked.leakage_reasons
    assert "blocked_trigger:manual_gold_api" in checked.leakage_reasons
    assert "blocked_trigger:memorized_gold_sql" in checked.leakage_reasons
    assert "exact_full_query_string_trigger" in checked.leakage_reasons
    assert "exact_public_entity_without_general_value_match" in checked.leakage_reasons
    assert "gold_signal_used_for_generation" in checked.leakage_reasons


def test_score075_public_entity_trigger_requires_general_value_match():
    safe_candidate = TargetedCandidate(
        candidate_id="general_value_match_candidate",
        generation_reason="general value match",
        sql="SELECT name FROM dim_campaign WHERE lower(name) = lower(?)",
        api_call=None,
        expected_answer_shape="detail",
        endpoint_family="campaign",
        schema_family="campaign",
        source_signals=["schema_metadata", "value_retrieval"],
        trigger_features=["exact_public_entity", "general_value_match"],
        generalizable_family="campaign",
    )

    checked = apply_leakage_checks(safe_candidate, query="Find campaign named Birthday Message")

    assert checked.leakage_check_passed is True
    assert checked.leakage_reasons == []


def test_score075_generated_candidates_have_generalizable_non_gold_triggers(tiny_project):
    from dashagent.executor import AgentExecutor

    executor = AgentExecutor(tiny_project)
    baseline_trajectory = {
        "steps": [
            {
                "kind": "sql_call",
                "sql": "SELECT COUNT(*) AS count FROM dim_campaign",
            }
        ]
    }

    candidates = generate_targeted_candidates(
        query_id="tiny_001",
        query="How many campaigns are there?",
        baseline_trajectory=baseline_trajectory,
        schema_index=executor.schema_index,
        endpoint_catalog=executor.endpoint_catalog,
    )

    assert candidates
    for candidate in candidates:
        features = set(candidate["trigger_features"])
        assert not (features & FORBIDDEN_TRIGGER_FEATURES)
        assert "How many campaigns are there?" not in candidate["trigger_features"]
        assert candidate["rule_source"]
        assert candidate["generalizable_family"]
        assert candidate["leakage_check_passed"] is True
        assert not candidate["leakage_reasons"]


def test_score075_local_index_returns_evidence_objects_only_when_available(tiny_project):
    if importlib.util.find_spec("dashagent.local_knowledge_index") is None:
        pytest.skip("local knowledge index worker branch not merged yet")

    from dashagent.local_knowledge_index import build_local_knowledge_index, classify_evidence_hit, ensure_not_final_answer_payload

    tiny_project.data_json_path.write_text(
        json.dumps(
            {
                "answer": "FORBIDDEN_GOLD_ANSWER",
                "gold_sql": "SELECT secret_answer",
                "gold_api": [{"path": "/secret/gold/path"}],
            }
        ),
        encoding="utf-8",
    )

    index = build_local_knowledge_index(tiny_project)
    payload = index.to_dict()
    rendered = json.dumps(payload, sort_keys=True)

    assert payload["runtime_sources"]["parquet_only"] is True
    assert payload["runtime_sources"]["data_json_used_for_runtime"] is False
    assert payload["local_index_returns_final_answers"] is False
    assert "FORBIDDEN_GOLD_ANSWER" not in rendered
    assert "secret_answer" not in rendered
    assert "/secret/gold/path" not in rendered

    hits = index.lookup("What is the status of Welcome Journey?")
    assert hits
    for hit in hits:
        assert hit["is_final_answer"] is False
        assert hit["answer_cache"] is False
        assert "final_answer" not in hit
        assert "answer" not in hit
        assert hit["provenance"]["data_json_used"] is False
        assert hit["provenance"]["derived_from_gold"] is False
        assert classify_evidence_hit(hit) != "rejected_exact_query_or_gold_like_lookup"

    with pytest.raises(ValueError):
        ensure_not_final_answer_payload({"evidence": {"final_answer": "2"}})


def test_score075_dry_run_answers_do_not_fabricate_from_result_preview():
    forged_answer = synthesize_answer(
        "Show details for the tag named Loyal Customers.",
        [
            {
                "type": "api",
                "step": {"family": "tag_detail"},
                "payload": {
                    "ok": False,
                    "dry_run": True,
                    "result_preview": {
                        "id": "FORGED_TAG_ID",
                        "name": "FORGED_TAG_NAME",
                        "category": "FORGED_CATEGORY",
                        "total": 999,
                    },
                },
            }
        ],
    )

    assert "FORGED_TAG_ID" not in forged_answer
    assert "FORGED_TAG_NAME" not in forged_answer
    assert "FORGED_CATEGORY" not in forged_answer
    assert "999" not in forged_answer
    assert "require live api evidence" in forged_answer.lower()
    assert "Live API verification was not executed" in forged_answer


def test_score075_selector_and_holdout_gates_reject_regressions_and_leakage():
    safe_row = {
        "candidate_id": "general_rule",
        "score_delta": 0.02,
        "correctness_delta": 0.0,
        "baseline_tokens": 100,
        "token_delta": 0,
        "baseline_runtime": 0.01,
        "runtime_delta": 0.0,
        "tool_delta": 0,
        "accuracy_relevant_change": True,
        "final_answer_unsafe_drift": False,
        "sql_unsafe_drift": False,
        "api_unsafe_drift": False,
        "evidence_label_loss": False,
        "live_api_evidence_fabricated": False,
        "required_fields_preserved": True,
        "sql_validation_ok": True,
        "sql_ast_valid": True,
        "api_validation_ok": True,
        "leakage_check_passed": True,
        "holdout_regression_passed": True,
    }
    assert evaluate_candidate_safety(safe_row)[0] is True

    bad_row = {
        **safe_row,
        "leakage_check_passed": False,
        "evidence_label_loss": True,
        "live_api_evidence_fabricated": True,
        "required_fields_preserved": False,
    }
    safe, reason = evaluate_candidate_safety(bad_row)

    assert safe is False
    assert "leakage_check_failed" in reason
    assert "evidence_label_loss" in reason
    assert "live_api_evidence_fabricated" in reason
    assert "required_fields_missing" in reason

    holdout = holdout_regression_gate(
        {
            "summary": {
                "total_cases": 48,
                "passed_cases": 47,
                "family_stability_rate": 1.0,
                "schema_stability_rate": 1.0,
            }
        },
        candidate_diversity_delta=-1,
    )
    assert holdout["passed"] is False
    assert "hidden_style_not_48_48" in holdout["failed_checks"]
    assert "candidate_diversity_reduced" in holdout["failed_checks"]


def test_score075_hidden_style_remains_48_of_48_with_safe_defaults(tiny_project):
    payload = run_hidden_style_eval(tiny_project)
    summary = payload["summary"]

    assert summary["total_cases"] == 48
    assert summary["passed_cases"] == 48
    assert summary["failed_cases"] == 0
    assert summary["family_stability_rate"] == 1.0
    assert summary["schema_stability_rate"] == 1.0
    assert payload["repair_execution_enabled"] is False
    assert payload["compact_context_enabled"] is False
    assert payload["official_token_reduction_default"] is True


def test_score075_diagnostic_search_does_not_write_final_submission(tiny_project):
    _write_minimal_strict_inputs(tiny_project)
    final_submission = tiny_project.outputs_dir / "final_submission"
    final_submission.mkdir(parents=True, exist_ok=True)
    (final_submission / "sentinel.txt").write_text("do-not-touch", encoding="utf-8")
    before_hash = _tree_hash(final_submission)

    run_hidden_style_eval(tiny_project)
    payload = run_execution_candidate_search(tiny_project)

    assert payload["writes_final_submission"] is False
    assert payload["packaged_execution_changed"] is False
    assert _tree_hash(final_submission) == before_hash


def _write_minimal_strict_inputs(config) -> None:
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
    hidden = {
        "summary": {
            "total_cases": 48,
            "passed_cases": 48,
            "failed_cases": 0,
            "family_stability_rate": 1.0,
            "schema_stability_rate": 1.0,
        },
        "rows": [],
    }
    (config.outputs_dir / "eval_results_strict.json").write_text(json.dumps(strict), encoding="utf-8")
    (config.outputs_dir / "hidden_style_eval.json").write_text(json.dumps(hidden), encoding="utf-8")


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    if not root.exists():
        return digest.hexdigest()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        digest.update(str(path.relative_to(root)).encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()
