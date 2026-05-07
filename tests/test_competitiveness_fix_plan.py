from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from dashagent.config import Config
from dashagent.sql_only_api_skip_guard import should_skip_api_with_sql_evidence
from scripts.run_answer_shape_v2_ab_eval import run_answer_shape_v2_ab_eval
from scripts.run_endpoint_family_tiebreak_v2_shadow import run_endpoint_family_tiebreak_v2_shadow
from scripts.run_live_mode_readiness_check import run_live_mode_readiness_check


def _write_baseline_eval(config: Config) -> Path:
    output_dir = config.outputs_dir / "eval" / "tiny_001" / "sql_first_api_verify"
    output_dir.mkdir(parents=True, exist_ok=True)
    trajectory = {
        "query_id": "tiny_001",
        "original_query": "How many campaigns are there?",
        "strategy": "SQL_FIRST_API_VERIFY",
        "route_type": "SQL_ONLY",
        "domain_type": "JOURNEY_CAMPAIGN",
        "steps": [
            {
                "kind": "sql_call",
                "sql": "SELECT COUNT(*) AS count FROM dim_campaign",
                "validation": {"ok": True, "warnings": [], "errors": []},
                "result": {"ok": True, "rows": [{"count": 2}], "row_count": 1},
            }
        ],
        "final_answer": "The database returned a result.",
        "tool_call_count": 1,
        "sql_call_count": 1,
        "api_call_count": 0,
        "runtime": 0.001,
        "estimated_tokens": 100,
        "checkpoints": [],
        "timings": {},
    }
    (output_dir / "trajectory.json").write_text(json.dumps(trajectory), encoding="utf-8")
    (output_dir / "metadata.json").write_text(json.dumps({"query_id": "tiny_001"}), encoding="utf-8")
    (output_dir / "filled_system_prompt.txt").write_text("test", encoding="utf-8")
    (config.outputs_dir / "eval_results_strict.json").write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "query_id": "tiny_001",
                        "strategy": "SQL_FIRST_API_VERIFY",
                        "query": "How many campaigns are there?",
                        "sql_score": 1.0,
                        "api_score": None,
                        "answer_score": 0.0,
                        "correctness_score": 0.5,
                        "final_score": 0.49,
                        "tool_call_count": 1,
                        "api_call_count": 0,
                        "runtime": 0.001,
                        "estimated_tokens": 100,
                        "output_dir": str(output_dir),
                    }
                ],
                "summary": {
                    "by_strategy": {
                        "SQL_FIRST_API_VERIFY": {
                            "count": 1,
                            "avg_final_score": 0.49,
                            "avg_correctness_score": 0.5,
                            "avg_estimated_tokens": 100,
                            "avg_runtime": 0.001,
                            "avg_tool_call_count": 1,
                        }
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    (config.outputs_dir / "hidden_style_eval.json").write_text(
        json.dumps({"summary": {"passed_cases": 48, "total_cases": 48, "family_stability_rate": 1.0, "schema_stability_rate": 1.0}}),
        encoding="utf-8",
    )
    return output_dir


def test_answer_shape_v2_ab_eval_reports_row_level_deltas(tiny_project: Config):
    _write_baseline_eval(tiny_project)

    payload = run_answer_shape_v2_ab_eval(tiny_project)

    row = payload["rows"][0]
    assert row["query_id"] == "tiny_001"
    assert row["baseline_answer"]
    assert row["answer_shape_v2_answer"]
    assert "evidence_used" in row
    assert row["sql_api_tool_changed"] is False
    assert row["baseline_sql_hash"] == row["candidate_sql_hash"]
    assert row["baseline_api_hash"] == row["candidate_api_hash"]
    assert "strict_score_delta" in row
    assert "answer_score_delta" in row
    assert (tiny_project.outputs_dir / "answer_shape_v2_ab_eval" / "tiny_001" / "sql_first_api_verify" / "trajectory.json").exists()


def test_sql_only_api_skip_guard_refuses_when_api_may_matter():
    tool_results = [{"type": "sql", "payload": {"ok": True, "rows": [{"count": 2}], "row_count": 1}}]
    decision = should_skip_api_with_sql_evidence(
        query="How many batches succeeded in the current sandbox?",
        prompt_route=SimpleNamespace(requires_api=True),
        routing=SimpleNamespace(route_type="SQL_THEN_API"),
        analysis=SimpleNamespace(api_need_decision=SimpleNamespace(mode="API_REQUIRED", allowed_api_families=["successful_batch_count"])),
        api_step=SimpleNamespace(family="successful_batch_count"),
        tool_results=tool_results,
    )

    assert decision.skip is False
    assert decision.api_score_may_be_required is True


def test_sql_only_api_skip_guard_allows_sql_only_noop_when_proven():
    tool_results = [{"type": "sql", "payload": {"ok": True, "rows": [{"count": 2}], "row_count": 1}}]
    decision = should_skip_api_with_sql_evidence(
        query="How many campaigns are there?",
        prompt_route=SimpleNamespace(requires_api=False),
        routing=SimpleNamespace(route_type="SQL_ONLY"),
        analysis=SimpleNamespace(api_need_decision=SimpleNamespace(mode="API_SKIP", allowed_api_families=[])),
        api_step=SimpleNamespace(family="journey_default"),
        tool_results=tool_results,
        prior_strict_row={"api_call_count": 0, "api_reason": "No gold API supplied; unscored."},
    )

    assert decision.skip is True
    assert decision.sql_satisfies_answer_shape is True


def test_endpoint_tiebreak_shadow_never_enters_trial_without_positive_delta(tiny_project: Config):
    output_dir = _write_baseline_eval(tiny_project)
    trajectory = json.loads((output_dir / "trajectory.json").read_text(encoding="utf-8"))
    trajectory["steps"].append(
        {
            "kind": "api_call",
            "method": "GET",
            "url": "/unifiedtags/tags",
            "params": {},
            "validation": {"ok": True},
            "result": {"ok": False, "dry_run": True},
        }
    )
    trajectory["tool_call_count"] = 2
    trajectory["api_call_count"] = 1
    (output_dir / "trajectory.json").write_text(json.dumps(trajectory), encoding="utf-8")
    (tiny_project.outputs_dir / "candidate_context_report.json").write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "query_id": "tiny_001",
                        "query": "How many campaigns are there?",
                        "endpoint_family_ranking": {
                            "endpoint_family": "batch",
                            "endpoint_family_confidence": 0.99,
                            "top_ranked_apis": [{"endpoint_family": "batch", "id": "catalog_batches"}],
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    payload = run_endpoint_family_tiebreak_v2_shadow(tiny_project)

    assert payload["summary"]["trial_eligible_rows"] == 0
    assert payload["summary"]["recommendation"] == "keep_shadow_only"
    assert payload["rows"][0]["shadow_only"] is True


def test_live_mode_readiness_is_diagnostic_and_does_not_leak_credentials(tiny_project: Config, monkeypatch):
    _write_baseline_eval(tiny_project)
    for name in ["CLIENT_ID", "CLIENT_SECRET", "IMS_ORG", "SANDBOX", "ACCESS_TOKEN", "ADOBE_BASE_URL"]:
        monkeypatch.delenv(name, raising=False)

    payload = run_live_mode_readiness_check(tiny_project)

    assert payload["summary"]["diagnostic_only"] is True
    assert payload["packaged_execution_changed"] is False
    assert payload["final_answers_changed"] is False
    assert set(payload["credential_visibility"].values()) == {False}
    assert "CLIENT_SECRET" in payload["credential_visibility"]
