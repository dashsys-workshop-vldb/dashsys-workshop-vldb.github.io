from __future__ import annotations

import json

from dashagent.executor import AgentExecutor
from dashagent.llm_candidate_generator import (
    build_llm_candidate_prompt,
    normalize_llm_candidate,
    parse_llm_candidate_response,
    validate_llm_candidate,
)
from scripts.run_llm_candidate_search import run_llm_candidate_search


def _write_tiny_llm_inputs(config):
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
                "sql": "SELECT * FROM dim_campaign",
                "validation": {"ok": True},
                "result": {"ok": True, "rows": [{"name": "Birthday Message"}]},
            }
        ],
        "final_answer": "There are campaigns in the sandbox.",
        "runtime": 0.01,
        "tool_call_count": 1,
        "estimated_tokens": 100,
        "errors": [],
    }
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
                "answer_score": 0.4,
                "tool_call_count": 1,
                "estimated_tokens": 100,
                "runtime": 0.01,
            }
        ],
        "summary": {"by_strategy": {"SQL_FIRST_API_VERIFY": {"count": 1}}},
    }
    (config.outputs_dir / "eval_results_strict.json").write_text(json.dumps(strict), encoding="utf-8")
    (config.outputs_dir / "low_score_failure_mining_report.json").write_text(
        json.dumps({"summary": {"top_10_target_rows": ["tiny_001"]}, "rows": []}),
        encoding="utf-8",
    )
    (config.outputs_dir / "candidate_context_report.json").write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "query_id": "tiny_001",
                        "candidate_tables": [{"table": "dim_campaign", "columns": ["campaign_id", "name", "status"]}],
                        "candidate_apis": [],
                        "endpoint_family_ranking": {"endpoint_family": "campaign"},
                        "gold_api": "/should/not/appear",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (config.outputs_dir / "hidden_style_eval.json").write_text(
        json.dumps(
            {
                "summary": {
                    "total_cases": 48,
                    "passed_cases": 48,
                    "family_stability_rate": 1.0,
                    "schema_stability_rate": 1.0,
                }
            }
        ),
        encoding="utf-8",
    )


def test_prompt_sanitizes_gold_answer_fields():
    prompt = build_llm_candidate_prompt(
        query="How many campaigns are there?",
        schema_context={
            "candidate_tables": ["dim_campaign"],
            "gold_api": "/gold/path",
            "final_answer": "memorized answer",
            "nested": {"gold_sql": "SELECT gold"},
        },
        endpoint_catalog_summary=[{"path": "/safe", "gold_answer": "secret"}],
        failed_trajectory_summary={"generated_sql": "SELECT * FROM dim_campaign", "final_answer": "bad"},
        answer_shape="count",
    )

    assert "/gold/path" not in prompt
    assert "memorized answer" not in prompt
    assert "SELECT gold" not in prompt
    assert "gold_answer" not in prompt
    assert "SELECT * FROM dim_campaign" in prompt


def test_parse_llm_candidate_response_accepts_fenced_json():
    content = """```json
    {"candidates": [{"candidate_id": "c1", "sql": "SELECT 1"}]}
    ```"""

    parsed = parse_llm_candidate_response(content)

    assert parsed == [{"candidate_id": "c1", "sql": "SELECT 1"}]


def test_validate_llm_candidate_rejects_gold_trigger_and_bad_sql(tiny_project):
    executor = AgentExecutor(tiny_project)
    candidate = normalize_llm_candidate(
        {
            "candidate_id": "bad",
            "sql": "SELECT answer FROM unknown_table",
            "trigger_features": ["query_id", "schema_context"],
            "source_signals": ["gold_api_path"],
        },
        query="How many campaigns are there?",
    )

    validation = validate_llm_candidate(
        candidate,
        sql_validator=executor.sql_validator,
        api_validator=executor.api_validator,
    )

    assert validation["deterministic_validators_passed"] is False
    assert "leakage_check_failed" in validation["failed_checks"]
    assert "sql_validation_failed" in validation["failed_checks"]


def test_run_llm_candidate_search_with_mock_key_writes_only_isolated_outputs(monkeypatch, tiny_project):
    _write_tiny_llm_inputs(tiny_project)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    class FakeClient:
        def available(self):
            return True

        def provider_name(self):
            return "openai"

        def model_name(self):
            return "fake-model"

        def generate(self, system_prompt, user_prompt, tools=None):
            assert "gold_api" not in user_prompt
            return {
                "ok": True,
                "provider": "openai",
                "model": "fake-model",
                "content": json.dumps(
                    {
                        "candidates": [
                            {
                                "candidate_id": "count_campaigns",
                                "generation_reason": "General count shape candidate.",
                                "sql": "SELECT COUNT(*) AS count FROM dim_campaign",
                                "api_call": None,
                                "source_signals": ["schema_context", "query_vocabulary"],
                                "trigger_features": ["schema_context", "query_vocabulary"],
                                "generalizable_family": "campaign_count",
                            }
                        ]
                    }
                ),
                "error": None,
            }

    monkeypatch.setattr("scripts.run_llm_candidate_search.get_llm_client", lambda provider=None: FakeClient())

    payload = run_llm_candidate_search(tiny_project)

    assert payload["summary"]["status"] == "completed"
    assert payload["summary"]["safe_rows"] == 1
    assert payload["summary"]["recommendation"] == "candidates_ready_for_execution_selector"
    candidate_path = tiny_project.outputs_dir / "llm_candidate_search" / "tiny_001" / "count_campaigns" / "candidate.json"
    assert candidate_path.exists()
    assert not (tiny_project.outputs_dir / "final_submission").exists()
