from __future__ import annotations

from dashagent.db import DuckDBDatabase
from dashagent.executor import AgentExecutor
from dashagent.sql_compile_gate import SQLCompileGate


def test_valid_sql_passes(tiny_project):
    db = DuckDBDatabase(tiny_project)
    gate = SQLCompileGate(db)

    result = gate.check("SELECT name, status FROM dim_campaign WHERE LOWER(name) = LOWER(?) LIMIT 1", ["Birthday Message"])

    assert result.passed is True
    assert result.error_type is None
    assert result.error_message is None
    assert result.sql == "SELECT name, status FROM dim_campaign WHERE LOWER(name) = LOWER(?) LIMIT 1"
    assert result.params == ["Birthday Message"]


def test_syntax_error_fails(tiny_project):
    gate = SQLCompileGate(DuckDBDatabase(tiny_project))

    result = gate.check("SELECT FROM dim_campaign")

    assert result.passed is False
    assert result.error_type == "syntax_error"
    assert "syntax" in result.error_message.lower() or "parser" in result.error_message.lower()


def test_unknown_table_fails_as_semantic_error(tiny_project):
    gate = SQLCompileGate(DuckDBDatabase(tiny_project))

    result = gate.check("SELECT name FROM missing_table")

    assert result.passed is False
    assert result.error_type == "semantic_error"
    assert "missing_table" in result.error_message


def test_unknown_column_fails_as_semantic_error(tiny_project):
    gate = SQLCompileGate(DuckDBDatabase(tiny_project))

    result = gate.check("SELECT campaign_name FROM dim_campaign WHERE name = ?", ["Birthday Message"])

    assert result.passed is False
    assert result.error_type == "semantic_error"
    assert "campaign_name" in result.error_message


def test_ambiguous_column_fails_if_database_reports_it(tiny_project):
    gate = SQLCompileGate(DuckDBDatabase(tiny_project))

    result = gate.check(
        "SELECT name FROM dim_campaign JOIN dim_segment ON dim_campaign.campaign_id = dim_segment.segment_id"
    )

    assert result.passed is False
    assert result.error_type == "semantic_error"
    assert "ambiguous" in result.error_message.lower()


def test_gate_returns_original_sql_unchanged_and_does_not_rewrite(tiny_project):
    gate = SQLCompileGate(DuckDBDatabase(tiny_project))
    sql = "SELECT campaign_name FROM dim_campaign WHERE name = ?"

    result = gate.check(sql, ["Birthday Message"])

    assert result.sql == sql
    assert result.params == ["Birthday Message"]
    assert "SELECT name" not in result.sql


def test_gate_does_not_select_tables_columns_or_filters(tiny_project):
    gate = SQLCompileGate(DuckDBDatabase(tiny_project))
    sql = "SELECT made_up_column FROM made_up_table WHERE made_up_filter = ?"

    result = gate.check(sql, ["value"])

    assert result.passed is False
    assert result.sql == sql
    assert "dim_campaign" not in result.sql
    assert "dim_segment" not in result.sql


def test_gate_result_contains_no_gold_query_or_oracle_fields(tiny_project):
    gate = SQLCompileGate(DuckDBDatabase(tiny_project))

    result = gate.check("SELECT campaign_name FROM dim_campaign")
    payload = result.to_dict()

    forbidden = {"gold_answer", "gold_sql", "organizer", "category", "query_id", "example_id", "expected_trace", "oracle"}
    assert forbidden.isdisjoint(payload)


def test_failed_sql_returns_sanitized_db_error_for_llm_repair(tiny_project):
    gate = SQLCompileGate(DuckDBDatabase(tiny_project))

    result = gate.check("SELECT campaign_name FROM dim_campaign")

    assert result.passed is False
    assert result.error_message
    assert "\n" not in result.error_message
    assert len(result.error_message) <= 500
    assert "campaign_name" in result.error_message


def test_llm_sql_path_runs_compile_gate_before_execution(tiny_project, monkeypatch):
    class FakeLLMClient:
        def available(self):
            return True

        def provider_name(self):
            return "fake_llm"

        def model_name(self):
            return "fake-model"

        def generate_messages(self, messages):
            return {"reason": "available"}

        def generate(self, system_prompt, user_prompt):
            return {
                "content": (
                    '{"sql":"SELECT name FROM dim_campaign JOIN dim_segment '
                    'ON dim_campaign.campaign_id = dim_segment.segment_id",'
                    '"reasoning_summary":"ambiguous column"}'
                )
            }

    monkeypatch.setattr("dashagent.llm_sql_generator.get_llm_client", lambda: FakeLLMClient())

    result = AgentExecutor(tiny_project).run(
        "Show campaigns.",
        strategy="CANDIDATE_GUIDED_LLM_SQL",
        query_id="compile_gate_llm_sql",
    )

    checkpoints = result["trajectory"].get("checkpoints", [])
    compile_checkpoints = [
        item for item in checkpoints if item.get("checkpoint_id") == "checkpoint_llm_sql_compile_gate"
    ]
    assert compile_checkpoints
    compile_output = compile_checkpoints[-1]["output"]
    assert compile_output["passed"] is False
    assert compile_output["error_type"] == "semantic_error"
    assert "ambiguous" in compile_output["error_message"].lower()
