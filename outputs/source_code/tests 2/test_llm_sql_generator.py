from __future__ import annotations

from dashagent.llm_sql_generator import generate_sql_with_llm, repair_sql_with_llm, validate_sql_against_context


def test_llm_sql_generation_skips_without_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = generate_sql_with_llm("How many campaigns?", {"tables": {"dim_campaign": {"columns": ["name"]}}})
    assert result["skipped"] is True
    assert not result["ok"]


def test_llm_sql_repair_skips_without_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = repair_sql_with_llm("How many campaigns?", "SELECT bad FROM nope", ["Unknown table"], {"tables": {}})
    assert result["skipped"] is True


def test_context_validation_blocks_out_of_context_or_destructive_sql():
    context = {"tables": {"dim_campaign": {"columns": ["name"]}}}
    assert validate_sql_against_context("DROP TABLE dim_campaign", context)["ok"] is False
    assert validate_sql_against_context("SELECT * FROM dim_segment", context)["ok"] is False
