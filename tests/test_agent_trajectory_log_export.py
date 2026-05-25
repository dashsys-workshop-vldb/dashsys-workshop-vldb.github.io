from __future__ import annotations

import json

from scripts.generate_agent_trajectory_log_export import build_export, write_export


def test_agent_trajectory_log_export_includes_sql_and_live_api_examples(tiny_project):
    _write_sql_trajectory(tiny_project)
    _write_live_api_trajectory(tiny_project)

    payload = build_export(tiny_project)
    write_export(tiny_project, payload)

    labels = {example["label"] for example in payload["examples"]}
    assert "sql_only_path" in labels
    assert "sql_plus_live_api_path" in labels
    assert payload["redaction_applied"] is True
    assert payload["examples"][0]["tool_calls"]
    assert payload["examples"][0]["evidence_bus"]["evidence_sources"]

    markdown = (tiny_project.outputs_dir / "reports" / "agent_trajectory_log_export.md").read_text(encoding="utf-8")
    rendered = json.dumps(payload, sort_keys=True) + markdown
    assert "Agent Trajectory Log" in markdown
    assert "execute_sql" in markdown
    assert "call_api" in markdown
    assert "Authorization: Bearer secret-token-value" not in rendered
    assert "secret-token-value" not in rendered
    assert ".env.local" not in rendered


def test_agent_trajectory_log_export_keeps_token_count_metric(tiny_project):
    _write_sql_trajectory(tiny_project, estimated_tokens=123)
    payload = build_export(tiny_project)

    assert payload["examples"][0]["metrics"]["estimated_tokens"] == 123


def _write_sql_trajectory(config, *, estimated_tokens=50):
    root = config.outputs_dir / "final_submission" / "query_001"
    root.mkdir(parents=True, exist_ok=True)
    (root / "metadata.json").write_text(
        json.dumps(
            {
                "query_id": "query_001",
                "query": "How many schemas do I have?",
                "route_type": "SQL_ONLY",
                "selected_tables": ["dim_schema"],
                "selected_apis": [],
            }
        ),
        encoding="utf-8",
    )
    (root / "trajectory.json").write_text(
        json.dumps(
            {
                "query_id": "query_001",
                "original_query": "How many schemas do I have?",
                "strategy": "SQL_FIRST_API_VERIFY",
                "route_type": "SQL_ONLY",
                "domain_type": "SCHEMA_DATASET",
                "sql_call_count": 1,
                "api_call_count": 0,
                "tool_call_count": 1,
                "estimated_tokens": estimated_tokens,
                "runtime": 0.1,
                "steps": [
                    {
                        "kind": "route",
                        "confidence": 0.9,
                        "route_type": "SQL_ONLY",
                        "domain_type": "SCHEMA_DATASET",
                    },
                    {
                        "kind": "plan",
                        "strategy": "SQL_FIRST_API_VERIFY",
                        "rationale": "SQL-first evidence policy: API_SKIP.",
                        "steps": [
                            {
                                "action": "sql",
                                "purpose": "Count local schema rows.",
                                "sql": "SELECT COUNT(*) AS schema_count FROM dim_schema",
                            }
                        ],
                    },
                    {
                        "kind": "sql_call",
                        "sql": "SELECT COUNT(*) AS schema_count FROM dim_schema",
                        "validation": {"ok": True, "errors": [], "warnings": []},
                        "result": {"ok": True, "row_count": 1, "rows": [{"schema_count": 3}]},
                    },
                    {
                        "kind": "answer_diagnostics",
                        "answer_intent": "COUNT",
                        "answer_family": "schema_count",
                        "slots_present": ["counts", "sql_row_count"],
                        "unsupported_claims_count": 0,
                        "verifier_passed": True,
                    },
                ],
                "final_answer": "There are 3 schemas.",
            }
        ),
        encoding="utf-8",
    )


def _write_live_api_trajectory(config):
    root = config.outputs_dir / "live_api_evidence_pipeline_trial" / "example_000"
    root.mkdir(parents=True, exist_ok=True)
    (root / "metadata.json").write_text(
        json.dumps({"query_id": "example_000", "query": "List all journeys", "selected_apis": [{"path": "/ajo/journey"}]}),
        encoding="utf-8",
    )
    (root / "trajectory.json").write_text(
        json.dumps(
            {
                "query_id": "example_000",
                "original_query": "List all journeys",
                "strategy": "SQL_FIRST_API_VERIFY",
                "route_type": "SQL_THEN_API",
                "domain_type": "JOURNEY_CAMPAIGN",
                "sql_call_count": 1,
                "api_call_count": 1,
                "tool_call_count": 2,
                "estimated_tokens": 75,
                "runtime": 0.2,
                "steps": [
                    {"kind": "route", "confidence": 0.8, "route_type": "SQL_THEN_API"},
                    {
                        "kind": "plan",
                        "strategy": "SQL_FIRST_API_VERIFY",
                        "rationale": "SQL-first evidence policy: API_OPTIONAL.",
                        "steps": [
                            {"action": "sql", "purpose": "List local journeys.", "sql": "SELECT name FROM dim_campaign"},
                            {"action": "api", "purpose": "Verify live journeys.", "method": "GET", "url": "/ajo/journey", "params": {"pageSize": "10"}},
                        ],
                    },
                    {
                        "kind": "sql_call",
                        "sql": "SELECT name FROM dim_campaign",
                        "validation": {"ok": True},
                        "result": {"ok": True, "row_count": 1, "rows": [{"name": "Birthday Message"}]},
                    },
                    {
                        "kind": "api_call",
                        "method": "GET",
                        "url": "/ajo/journey",
                        "params": {"pageSize": "10"},
                        "headers": {"Authorization": "Bearer secret-token-value"},
                        "validation": {"ok": True},
                        "result": {
                            "ok": True,
                            "dry_run": False,
                            "endpoint": "/ajo/journey",
                            "params": {"pageSize": "10"},
                            "result_preview": {"pagination": {"totalCount": 0}},
                        },
                    },
                    {
                        "kind": "answer_diagnostics",
                        "answer_intent": "LIST",
                        "answer_family": "list_journeys",
                        "slots_present": ["entity_names", "api_evidence_state"],
                        "unsupported_claims_count": 0,
                        "verifier_passed": True,
                    },
                ],
                "final_answer": "Birthday Message is present locally; live API returned an empty list.",
            }
        ),
        encoding="utf-8",
    )
