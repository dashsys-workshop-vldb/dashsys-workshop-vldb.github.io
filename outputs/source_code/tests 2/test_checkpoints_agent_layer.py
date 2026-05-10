from __future__ import annotations

import json

from dashagent.agent_tools import run_data_answer_tool, verify_answer_tool
from dashagent.agents_sdk_adapter import export_checkpoints_to_spans
from dashagent.checkpoints import CheckpointLogger, REQUIRED_CHECKPOINT_IDS
from dashagent.executor import AgentExecutor
from dashagent.simple_prompt_gate import decide_simple_prompt
from scripts.generate_checkpoint_report import generate_checkpoint_report


def test_checkpoints_are_json_serializable_and_redact_secrets(monkeypatch):
    monkeypatch.setenv("ACCESS_TOKEN", "secret-access-token-12345")
    logger = CheckpointLogger()
    logger.add_checkpoint(
        "checkpoint_test",
        stage="test",
        technique="redaction",
        output={"Authorization": "Bearer secret-access-token-12345", "count": 1},
    )
    text = json.dumps(logger.to_list())
    assert "secret-access-token-12345" not in text
    assert "[REDACTED]" in text


def test_simple_prompt_gate_routes_data_questions_and_allows_concepts():
    data_decision = decide_simple_prompt("How many journeys are published?")
    assert data_decision.suggested_action == "USE_DATA_PIPELINE"
    assert not data_decision.is_simple

    concept_decision = decide_simple_prompt("Explain the project workflow")
    assert concept_decision.suggested_action == "LLM_DIRECT"
    assert concept_decision.is_simple


def test_trajectory_includes_required_checkpoints(tiny_project):
    result = AgentExecutor(tiny_project).run(
        'When was "Birthday Message" published?',
        strategy="SQL_FIRST_API_VERIFY",
        query_id="checkpoint_tiny",
    )
    checkpoints = result["trajectory"].get("checkpoints", [])
    ids = {checkpoint.get("checkpoint_id") for checkpoint in checkpoints}
    assert set(REQUIRED_CHECKPOINT_IDS).issubset(ids)
    assert "checkpoint_simple_prompt_gate" in ids
    assert result["trajectory"]["strategy"] == "SQL_FIRST_API_VERIFY"


def test_agent_tool_run_returns_answer_checkpoints_and_trajectory(tiny_project):
    result = run_data_answer_tool(
        'When was "Birthday Message" published?',
        config=tiny_project,
        query_id="agent_tool_checkpoint",
    )
    assert result["final_answer"]
    assert result["checkpoints"]
    assert result["trajectory"]["checkpoints"]
    assert result["diagnostics"]["tool_call_count"] >= 1


def test_verify_answer_tool_rewrites_unsupported_dry_run_confirmation():
    evidence = {
        "tool_results": [
            {
                "type": "api",
                "step": {"family": "tag_list"},
                "payload": {"ok": True, "dry_run": True, "result_preview": {"method": "GET"}},
            }
        ]
    }
    result = verify_answer_tool("List tags", "The API confirmed 5 tags.", evidence)
    assert not result["verifier_passed"]
    assert result["safer_rewritten_answer"]


def test_agents_sdk_adapter_noops_or_exports_without_required_dependency():
    result = export_checkpoints_to_spans(
        [{"checkpoint_id": "checkpoint_01_raw_query", "stage": "input", "output": {"query": "x"}}]
    )
    assert "sdk_available" in result
    assert "exported_spans" in result


def test_checkpoint_report_is_parseable(tiny_project):
    AgentExecutor(tiny_project).run(
        'When was "Birthday Message" published?',
        strategy="SQL_FIRST_API_VERIFY",
        query_id="checkpoint_report_tiny",
    )
    report = generate_checkpoint_report(tiny_project)
    assert report["trajectory_count"] >= 1
    assert report["coverage"]["checkpoint_01_raw_query"]["present_in"] >= 1
