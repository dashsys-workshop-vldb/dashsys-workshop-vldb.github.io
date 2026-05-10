from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from dashagent.config import Config
from dashagent.endpoint_catalog import EndpointCatalog
from dashagent.executor import AgentExecutor
from dashagent.query_analysis import analyze_query
from dashagent.query_normalizer import normalize_query
from dashagent.query_tokens import extract_query_tokens
from dashagent.router import RoutingDecision
from dashagent.schema_index import SchemaIndex
from dashagent.semantic_routing_helper import (
    apply_semantic_routing_hint,
    build_semantic_routing_messages,
    compute_semantic_router_eligibility,
    normalize_answer_intent,
    normalize_route_suggestion,
    run_semantic_routing_helper,
    validate_semantic_routing_hint,
)
from scripts.run_llm_semantic_router_shadow_eval import run_llm_semantic_router_shadow_eval
from scripts.package_query_outputs import NON_SUBMISSION_OUTPUT_DIRS


class FakeLLMClient:
    def __init__(self, content: str | None = None, *, available: bool = True) -> None:
        self.content = content or json.dumps(
            {
                "likely_domain": "schema_dataset",
                "answer_intent": "DATE",
                "route_suggestion": "SQL_PLUS_API",
                "synonym_mappings": [
                    {
                        "user_phrase": "data models",
                        "mapped_to": "dim_campaign",
                        "target_domain": "schema_dataset",
                        "reason": "safe synonym test",
                    }
                ],
                "candidate_tables": ["dim_campaign"],
                "candidate_api_families": ["journey_list"],
                "needs_api": True,
                "confidence": 0.72,
                "reason": "Maps the phrase to known metadata.",
            }
        )
        self._available = available

    def available(self) -> bool:
        return self._available

    def provider_name(self) -> str:
        return "openai"

    def model_name(self) -> str:
        return "unit-test-model"

    def generate_messages(self, messages, tools=None, tool_choice=None):
        if not self._available:
            return {
                "ok": False,
                "skipped": True,
                "reason": "unit test unavailable",
                "backend_type": "none",
                "transport": "none",
                "sdk_path_used": False,
                "content": "",
            }
        return {
            "ok": True,
            "provider": "openai",
            "model": "unit-test-model",
            "backend_type": "openai_sdk",
            "transport": "openai_sdk",
            "sdk_path_used": True,
            "content": self.content,
            "usage": {"total_tokens": 12},
        }


def _context(tiny_project: Config):
    executor = AgentExecutor(tiny_project)
    routing = RoutingDecision("SQL_ONLY", "UNKNOWN", 0.2, "unit", candidate_tables=[], candidate_apis=[])
    norm = normalize_query("show me my data models")
    tokens = extract_query_tokens("show me my data models", norm)
    analysis = analyze_query(
        "show me my data models",
        routing,
        executor.schema_index,
        strategy="SQL_FIRST_API_VERIFY",
        config=tiny_project,
        endpoint_catalog=executor.endpoint_catalog,
        normalized=norm,
        tokens=tokens,
    )
    return executor, routing, norm, tokens, analysis


def test_semantic_router_eligibility_high_confidence_skips(tiny_project: Config):
    executor, _, norm, tokens, _ = _context(tiny_project)
    routing = RoutingDecision("SQL_ONLY", "JOURNEY_CAMPAIGN", 0.9, "high confidence", candidate_tables=["dim_campaign"], candidate_apis=[])
    analysis = analyze_query(
        "How many campaigns are there?",
        routing,
        executor.schema_index,
        strategy="SQL_FIRST_API_VERIFY",
        config=tiny_project,
        endpoint_catalog=executor.endpoint_catalog,
        normalized=norm,
        tokens=tokens,
    )
    decision = compute_semantic_router_eligibility(query="How many campaigns are there?", routing=routing, analysis=analysis, config=tiny_project)
    assert decision["eligible"] is False


def test_semantic_router_eligibility_low_confidence_unknown(tiny_project: Config):
    _, routing, _, _, analysis = _context(tiny_project)
    decision = compute_semantic_router_eligibility(query="show me my data models", routing=routing, analysis=analysis, config=tiny_project)
    assert decision["eligible"] is True
    assert "low_confidence" in decision["reasons"]
    assert "unknown_domain" in decision["reasons"]


def test_helper_prompt_excludes_gold_runtime_payloads(tiny_project: Config):
    executor, routing, norm, tokens, analysis = _context(tiny_project)
    messages = build_semantic_routing_messages(
        user_prompt="show me my data models",
        normalized_query=norm["normalized"],
        matching_text=norm["matching_text"],
        routing=routing,
        analysis=analysis,
        tokens=tokens,
        schema_index=executor.schema_index,
        endpoint_catalog=executor.endpoint_catalog,
    )
    text = json.dumps(messages)
    assert "gold_sql" not in text
    assert "gold_api" not in text
    assert "tiny_001" not in text
    assert "final_answer" not in text


def test_route_and_intent_normalization():
    assert normalize_route_suggestion("SQL_PLUS_API") == "SQL_THEN_API"
    assert normalize_answer_intent("DATE") == "WHEN"
    assert normalize_answer_intent("BOOLEAN") == "YES_NO"


def test_semantic_router_flags_accept_true_false_env(monkeypatch, tiny_project: Config):
    monkeypatch.setenv("ENABLE_LLM_SEMANTIC_ROUTER", "true")
    monkeypatch.setenv("LLM_SEMANTIC_ROUTER_SHADOW_ONLY", "false")
    config = Config.from_env(tiny_project.project_root)
    assert config.enable_llm_semantic_router is True
    assert config.llm_semantic_router_shadow_only is False


def test_validate_semantic_hint_accepts_normalized_valid_hint(tiny_project: Config):
    executor, *_ = _context(tiny_project)
    hint, reason = validate_semantic_routing_hint(
        {
            "likely_domain": "schema_dataset",
            "answer_intent": "DATE",
            "route_suggestion": "SQL_PLUS_API",
            "synonym_mappings": [{"user_phrase": "models", "mapped_to": "dim_campaign", "target_domain": "schema_dataset"}],
            "candidate_tables": ["dim_campaign"],
            "candidate_api_families": ["journey_list"],
            "needs_api": True,
            "confidence": 0.8,
            "reason": "safe",
        },
        user_prompt="show me my data models",
        schema_index=executor.schema_index,
        endpoint_catalog=executor.endpoint_catalog,
    )
    assert reason is None
    assert hint is not None
    assert hint.internal_route_suggestion == "SQL_THEN_API"
    assert hint.normalized_answer_intent == "WHEN"


def test_validate_semantic_hint_rejects_unsafe_outputs(tiny_project: Config):
    executor, *_ = _context(tiny_project)
    base = {
        "likely_domain": "schema_dataset",
        "answer_intent": "COUNT",
        "route_suggestion": "SQL_ONLY",
        "synonym_mappings": [],
        "candidate_tables": [],
        "candidate_api_families": [],
        "needs_api": False,
        "confidence": 0.5,
        "reason": "safe",
    }
    bad_table = {**base, "candidate_tables": ["missing_table"]}
    assert validate_semantic_routing_hint(bad_table, user_prompt="schemas count", schema_index=executor.schema_index, endpoint_catalog=executor.endpoint_catalog)[0] is None
    answer_like = {**base, "reason": "there are 74 schemas"}
    assert validate_semantic_routing_hint(answer_like, user_prompt="schemas count", schema_index=executor.schema_index, endpoint_catalog=executor.endpoint_catalog)[0] is None
    secret_like = {**base, "reason": "ACCESS_TOKEN_PLACEHOLDER"}
    assert validate_semantic_routing_hint(secret_like, user_prompt="schemas count", schema_index=executor.schema_index, endpoint_catalog=executor.endpoint_catalog)[0] is None
    safe_numbers = {**base, "reason": "Use last 7 days, top 10, date 2026-03-31, and id 123e4567-e89b-12d3-a456-426614174000 as constraints."}
    hint, reason = validate_semantic_routing_hint(
        safe_numbers,
        user_prompt="show top 10 failures in last 7 days before 2026-03-31 for 123e4567-e89b-12d3-a456-426614174000",
        schema_index=executor.schema_index,
        endpoint_catalog=executor.endpoint_catalog,
    )
    assert hint is not None, reason


def test_executor_default_does_not_add_semantic_checkpoint(tiny_project: Config):
    result = AgentExecutor(tiny_project).run("show me my data models", query_id="semantic_default", output_dir=tiny_project.outputs_dir / "semantic_default")
    checkpoint_ids = [item.get("checkpoint_id") for item in result["trajectory"].get("checkpoints", [])]
    assert "checkpoint_llm_semantic_routing_helper" not in checkpoint_ids


def test_executor_shadow_mode_records_without_applying(monkeypatch, tiny_project: Config):
    monkeypatch.setattr("dashagent.semantic_routing_helper.get_llm_client", lambda: FakeLLMClient())
    config = replace(tiny_project, enable_llm_semantic_router=True, llm_semantic_router_shadow_only=True)
    result = AgentExecutor(config).run("show me my data models", query_id="semantic_shadow", output_dir=tiny_project.outputs_dir / "semantic_shadow")
    checkpoint = _checkpoint(result["trajectory"], "checkpoint_llm_semantic_routing_helper")
    assert checkpoint["helper_called"] is True
    assert checkpoint["helper_valid"] is True
    assert checkpoint["hint_applied"] is False
    assert checkpoint["hint_application_mode"] == "shadow_only"
    assert checkpoint["sdk_path_used"] is True


def test_non_shadow_isolated_uses_runtime_copy(monkeypatch, tiny_project: Config):
    monkeypatch.setattr("dashagent.semantic_routing_helper.get_llm_client", lambda: FakeLLMClient())
    executor, routing, norm, tokens, analysis = _context(tiny_project)
    config = replace(tiny_project, enable_llm_semantic_router=True, llm_semantic_router_shadow_only=False)
    result = run_semantic_routing_helper(
        user_prompt="show me my data models",
        normalization=norm,
        tokens=tokens,
        routing=routing,
        analysis=analysis,
        schema_index=executor.schema_index,
        endpoint_catalog=executor.endpoint_catalog,
        config=config,
    )
    effective_routing, effective_analysis, applied = apply_semantic_routing_hint(
        routing=routing,
        analysis=analysis,
        result=result,
        config=config,
        endpoint_catalog=executor.endpoint_catalog,
    )
    assert applied.hint_applied is True
    assert effective_routing is not routing
    assert effective_analysis is not analysis
    assert analysis.route_type == "SQL_ONLY"
    assert effective_routing.route_type == "SQL_THEN_API"


def test_semantic_shadow_report_and_packaging_exclusion(monkeypatch, tiny_project: Config):
    monkeypatch.setattr("scripts.run_llm_semantic_router_shadow_eval.get_llm_client", lambda: FakeLLMClient(available=False))
    report = run_llm_semantic_router_shadow_eval(tiny_project, limit=1, include_generated=False)
    assert report["status"] == "skipped"
    assert report["shadow_only"] is True
    assert (tiny_project.outputs_dir / "reports" / "llm_semantic_router_shadow_eval.json").exists()
    assert "llm_semantic_router_shadow_eval" in NON_SUBMISSION_OUTPUT_DIRS


def _checkpoint(trajectory: dict, checkpoint_id: str) -> dict:
    for item in trajectory.get("checkpoints", []):
        if item.get("checkpoint_id") == checkpoint_id:
            return item.get("output") or {}
    raise AssertionError(f"missing checkpoint {checkpoint_id}")
