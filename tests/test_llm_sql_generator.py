from __future__ import annotations

from dashagent.llm_sql_generator import generate_sql_with_llm, repair_sql_with_llm, validate_sql_against_context


def clear_llm_env(monkeypatch):
    for key in [
        "LLM_PROVIDER",
        "DASHAGENT_LLM_PROVIDER",
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
        "OPENROUTER_API_KEY",
        "OPENROUTER_BASE_URL",
        "ANTHROPIC_API_KEY",
        "PIONEER_API_KEY",
    ]:
        monkeypatch.delenv(key, raising=False)


def test_llm_sql_generation_skips_without_key(monkeypatch):
    clear_llm_env(monkeypatch)
    result = generate_sql_with_llm("How many campaigns?", {"tables": {"dim_campaign": {"columns": ["name"]}}})
    assert result["skipped"] is True
    assert not result["ok"]


def test_llm_sql_repair_skips_without_key(monkeypatch):
    clear_llm_env(monkeypatch)
    result = repair_sql_with_llm("How many campaigns?", "SELECT bad FROM nope", ["Unknown table"], {"tables": {}})
    assert result["skipped"] is True


def test_context_validation_blocks_out_of_context_or_destructive_sql():
    context = {"tables": {"dim_campaign": {"columns": ["name"]}}}
    assert validate_sql_against_context("DROP TABLE dim_campaign", context)["ok"] is False
    assert validate_sql_against_context("SELECT * FROM dim_segment", context)["ok"] is False


def test_pioneer_chat_is_not_used_for_executable_sql_generation():
    class FakePioneerClient:
        def available(self):
            return True

        def provider_name(self):
            return "pioneer_chat"

        def model_name(self):
            return "Qwen3 4B Instruct 2507"

        def generate_messages(self, messages):
            return {"reason": "should not be called"}

        def generate(self, system_prompt, user_prompt):
            return {"content": '{"sql":"SELECT * FROM dim_campaign","reasoning_summary":"unsafe"}'}

    result = generate_sql_with_llm(
        "Show campaigns.",
        {"tables": {"dim_campaign": {"columns": ["name"]}}},
        llm_client=FakePioneerClient(),
    )

    assert result["skipped"] is True
    assert result["ok"] is False
    assert result["sql"] == ""
    assert "not allowed to generate executable SQL" in result["error"]


def test_pioneer_chat_is_not_used_for_executable_sql_repair():
    class FakePioneerClient:
        def available(self):
            return True

        def provider_name(self):
            return "pioneer_chat"

        def model_name(self):
            return "Llama 3.1 8B Instruct"

        def generate_messages(self, messages):
            return {"reason": "should not be called"}

        def generate(self, system_prompt, user_prompt):
            return {"content": '{"sql":"SELECT * FROM dim_campaign","reasoning_summary":"unsafe"}'}

    result = repair_sql_with_llm(
        "Show campaigns.",
        "SELECT bad FROM nope",
        ["Unknown table"],
        {"tables": {"dim_campaign": {"columns": ["name"]}}},
        llm_client=FakePioneerClient(),
    )

    assert result["skipped"] is True
    assert result["ok"] is False
    assert result["sql"] == ""
    assert "not allowed to generate executable SQL" in result["error"]
