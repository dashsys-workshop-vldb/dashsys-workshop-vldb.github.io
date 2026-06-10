from __future__ import annotations

from dashagent.prompt_router import API_ONLY, LLM_DIRECT, LOCAL_DB_ONLY, SQL_PLUS_API, route_prompt


def test_prompt_router_conceptual_direct():
    decision = route_prompt("Explain how checkpoints work")
    assert decision.mode == LLM_DIRECT
    assert not decision.requires_database


def test_prompt_router_data_prompt_not_direct():
    decision = route_prompt("How many schemas do I have?")
    assert decision.mode == LOCAL_DB_ONLY
    assert decision.api_policy == "API_SKIP"


def test_prompt_router_status_prompt_sql_plus_api():
    decision = route_prompt("Is the 'Birthday Message' journey published?")
    assert decision.mode == SQL_PLUS_API
    assert decision.requires_database


def test_prompt_router_api_only_families():
    assert route_prompt("How many merge policies are configured?").mode == API_ONLY
    assert route_prompt("List tags").mode == API_ONLY
    assert route_prompt("Show observability metrics").mode == API_ONLY


def test_prompt_router_ambiguous_uses_pipeline():
    decision = route_prompt("What overall pattern do you see?")
    assert decision.mode != LLM_DIRECT
    assert decision.risk == "high"
