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
    SemanticRoutingResult,
    apply_semantic_routing_hint,
    build_semantic_routing_messages,
    compute_semantic_router_eligibility,
    normalize_answer_intent,
    normalize_helper_domain,
    normalize_route_suggestion,
    run_semantic_routing_helper,
    validate_semantic_routing_hint,
)
from scripts.run_llm_semantic_router_isolated_trial import run_llm_semantic_router_isolated_trial
from scripts.run_llm_semantic_router_shadow_eval import _build_report, _row_from_trajectory, run_llm_semantic_router_shadow_eval
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


def test_helper_prompt_has_strict_json_schema_examples(tiny_project: Config):
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
    text = "\n".join(message["content"] for message in messages)
    assert "Return one JSON object only. No markdown. No prose. No final answer." in text
    assert "synonym_mappings must always be an array" in text
    assert '"user_phrase": "data models"' in text
    assert '"mapped_to": "schemas"' in text
    assert '"candidate_tables": [\n    "dim_blueprint"\n  ]' in text
    assert '"synonym_mappings": []' in text


def test_route_and_intent_normalization():
    assert normalize_route_suggestion("SQL_PLUS_API") == "SQL_THEN_API"
    assert normalize_answer_intent("DATE") == "WHEN"
    assert normalize_answer_intent("BOOLEAN") == "YES_NO"


def test_audit_domain_aliases_normalize_to_observability():
    assert normalize_helper_domain("audit") == ("observability", None)
    assert normalize_helper_domain("audits") == ("observability", None)
    assert normalize_helper_domain("audit_events") == ("observability", None)
    assert normalize_helper_domain("not_a_domain") == ("not_a_domain", None)


def test_semantic_router_flags_accept_true_false_env(monkeypatch, tiny_project: Config):
    monkeypatch.setenv("ENABLE_LLM_SEMANTIC_ROUTER", "true")
    monkeypatch.setenv("LLM_SEMANTIC_ROUTER_SHADOW_ONLY", "false")
    config = Config.from_env(tiny_project.project_root)
    assert config.enable_llm_semantic_router is True
    assert config.llm_semantic_router_shadow_only is False


def test_semantic_router_trial_policy_env(monkeypatch, tiny_project: Config):
    monkeypatch.setenv("LLM_SEMANTIC_ROUTER_TRIAL_POLICY", "priority_only")
    config = Config.from_env(tiny_project.project_root)
    assert config.llm_semantic_router_trial_policy == "priority_only"


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


def test_synonym_mappings_safe_shape_normalization(tiny_project: Config):
    executor, *_ = _context(tiny_project)
    base = _valid_hint_base()

    missing = {key: value for key, value in base.items() if key != "synonym_mappings"}
    hint, reason = validate_semantic_routing_hint(
        missing,
        user_prompt="show me my data models",
        schema_index=executor.schema_index,
        endpoint_catalog=executor.endpoint_catalog,
    )
    assert hint is not None, reason
    assert hint.synonym_mappings == []
    assert "synonym_mappings_missing_to_empty" in hint.normalization_actions

    null_hint, reason = validate_semantic_routing_hint(
        {**base, "synonym_mappings": None},
        user_prompt="show me my data models",
        schema_index=executor.schema_index,
        endpoint_catalog=executor.endpoint_catalog,
    )
    assert null_hint is not None, reason
    assert null_hint.synonym_mappings == []
    assert "synonym_mappings_null_to_empty" in null_hint.normalization_actions

    object_hint, reason = validate_semantic_routing_hint(
        {**base, "synonym_mappings": {"user_phrase": "data models", "mapped_to": "schemas", "target_domain": "schema_dataset"}},
        user_prompt="show me my data models",
        schema_index=executor.schema_index,
        endpoint_catalog=executor.endpoint_catalog,
    )
    assert object_hint is not None, reason
    assert object_hint.synonym_mappings[0]["mapped_to"] == "schemas"
    assert "synonym_mappings_object_wrapped" in object_hint.normalization_actions

    simple_hint, reason = validate_semantic_routing_hint(
        {**base, "synonym_mappings": {"data models": "schemas"}},
        user_prompt="show me my data models",
        schema_index=executor.schema_index,
        endpoint_catalog=executor.endpoint_catalog,
    )
    assert simple_hint is not None, reason
    assert simple_hint.synonym_mappings == [
        {
            "user_phrase": "data models",
            "mapped_to": "schemas",
            "target_domain": "unknown",
            "reason": "Coerced from simple mapping object.",
        }
    ]
    assert "synonym_mappings_simple_object_coerced" in simple_hint.normalization_actions

    rejected, reason = validate_semantic_routing_hint(
        {**base, "synonym_mappings": "data models means schemas"},
        user_prompt="show me my data models",
        schema_index=executor.schema_index,
        endpoint_catalog=executor.endpoint_catalog,
    )
    assert rejected is None
    assert reason == "synonym_mappings_string_not_allowed"


def test_audit_domain_alias_validation_and_unsupported_domain(tiny_project: Config):
    executor, *_ = _context(tiny_project)
    for domain, action in [
        ("audit", "domain_alias:audit->observability"),
        ("audits", "domain_alias:audits->observability"),
        ("audit_events", "domain_alias:audit_events->observability"),
    ]:
        hint, reason = validate_semantic_routing_hint(
            {**_valid_hint_base(), "likely_domain": domain},
            user_prompt="show audit events",
            schema_index=executor.schema_index,
            endpoint_catalog=executor.endpoint_catalog,
        )
        assert hint is not None, reason
        assert hint.normalized_domain == "observability"
        assert hint.internal_domain_type is None
        assert action in hint.normalization_actions

    hint, reason = validate_semantic_routing_hint(
        {**_valid_hint_base(), "likely_domain": "unsupported"},
        user_prompt="show audit events",
        schema_index=executor.schema_index,
        endpoint_catalog=executor.endpoint_catalog,
    )
    assert hint is None
    assert reason == "unknown_domain:unsupported"


def test_validate_semantic_hint_rejects_unsafe_outputs(tiny_project: Config):
    executor, *_ = _context(tiny_project)
    base = _valid_hint_base()
    bad_table = {**base, "candidate_tables": ["missing_table"]}
    assert validate_semantic_routing_hint(bad_table, user_prompt="schemas count", schema_index=executor.schema_index, endpoint_catalog=executor.endpoint_catalog)[0] is None
    bad_api = {**base, "candidate_api_families": ["missing_api_family"]}
    assert validate_semantic_routing_hint(bad_api, user_prompt="schemas count", schema_index=executor.schema_index, endpoint_catalog=executor.endpoint_catalog)[0] is None
    final_answer_key = {**base, "final_answer": "You have 74 schemas."}
    assert validate_semantic_routing_hint(final_answer_key, user_prompt="schemas count", schema_index=executor.schema_index, endpoint_catalog=executor.endpoint_catalog)[0] is None
    query_id_ref = {**base, "reason": "This follows example_011."}
    assert validate_semantic_routing_hint(query_id_ref, user_prompt="schemas count", schema_index=executor.schema_index, endpoint_catalog=executor.endpoint_catalog)[0] is None
    invalid_confidence = {**base, "confidence": 1.2}
    assert validate_semantic_routing_hint(invalid_confidence, user_prompt="schemas count", schema_index=executor.schema_index, endpoint_catalog=executor.endpoint_catalog)[0] is None
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
    assert "normalization_actions" in checkpoint


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


def test_priority_only_changes_candidate_priority_only(tiny_project: Config):
    executor, routing, _, _, analysis = _context(tiny_project)
    hint, reason = validate_semantic_routing_hint(
        {**_valid_hint_base(), "route_suggestion": "SQL_PLUS_API", "candidate_tables": ["dim_campaign"]},
        user_prompt="show me my data models",
        schema_index=executor.schema_index,
        endpoint_catalog=executor.endpoint_catalog,
    )
    assert hint is not None, reason
    result = SemanticRoutingResult(
        enabled=True,
        shadow_only=False,
        eligibility_reason=["low_confidence", "unknown_domain"],
        deterministic_route_type=routing.route_type,
        deterministic_domain_type=routing.domain_type,
        deterministic_answer_family=analysis.answer_family,
        deterministic_confidence_before=routing.confidence,
        final_runtime_confidence=analysis.confidence,
        final_runtime_answer_family=analysis.answer_family,
        helper_called=True,
        helper_valid=True,
        hint=hint,
    )
    effective_routing, effective_analysis, applied = apply_semantic_routing_hint(
        routing=routing,
        analysis=analysis,
        result=result,
        config=replace(
            tiny_project,
            enable_llm_semantic_router=True,
            llm_semantic_router_shadow_only=False,
            llm_semantic_router_trial_policy="priority_only",
        ),
        endpoint_catalog=executor.endpoint_catalog,
    )
    assert applied.hint_applied is True
    assert effective_routing.route_type == routing.route_type
    assert effective_analysis.route_type == analysis.route_type
    assert effective_routing.domain_type == routing.domain_type
    assert effective_routing.candidate_tables[0] == "dim_campaign"
    assert "priority_only:candidate_tables_prepended" in (applied.hint_application_reason or "")


def test_unknown_only_allows_unknown_domain_hint(tiny_project: Config):
    executor, routing, _, _, analysis = _context(tiny_project)
    hint, reason = validate_semantic_routing_hint(
        {**_valid_hint_base(), "likely_domain": "journey_campaign", "candidate_tables": ["dim_campaign"]},
        user_prompt="show me my data models",
        schema_index=executor.schema_index,
        endpoint_catalog=executor.endpoint_catalog,
    )
    assert hint is not None, reason
    result = SemanticRoutingResult(
        enabled=True,
        shadow_only=False,
        eligibility_reason=["unknown_domain"],
        deterministic_route_type=routing.route_type,
        deterministic_domain_type=routing.domain_type,
        deterministic_answer_family=analysis.answer_family,
        deterministic_confidence_before=routing.confidence,
        final_runtime_confidence=analysis.confidence,
        final_runtime_answer_family=analysis.answer_family,
        helper_called=True,
        helper_valid=True,
        hint=hint,
    )
    effective_routing, _, applied = apply_semantic_routing_hint(
        routing=routing,
        analysis=analysis,
        result=result,
        config=replace(
            tiny_project,
            enable_llm_semantic_router=True,
            llm_semantic_router_shadow_only=False,
            llm_semantic_router_trial_policy="unknown_only",
        ),
        endpoint_catalog=executor.endpoint_catalog,
    )
    assert applied.hint_applied is True
    assert effective_routing.domain_type == "JOURNEY_CAMPAIGN"


def test_no_api_forcing_does_not_force_sql_only_to_api_route(tiny_project: Config):
    executor, _, norm, tokens, _ = _context(tiny_project)
    routing = RoutingDecision("SQL_ONLY", "UNKNOWN", 0.2, "low confidence", candidate_tables=[], candidate_apis=[])
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
    hint, reason = validate_semantic_routing_hint(
        {**_valid_hint_base(), "route_suggestion": "SQL_PLUS_API", "candidate_tables": ["dim_campaign"]},
        user_prompt="show me my data models",
        schema_index=executor.schema_index,
        endpoint_catalog=executor.endpoint_catalog,
    )
    assert hint is not None, reason
    result = SemanticRoutingResult(
        enabled=True,
        shadow_only=False,
        eligibility_reason=["low_confidence", "unknown_domain"],
        deterministic_route_type=routing.route_type,
        deterministic_domain_type=routing.domain_type,
        deterministic_answer_family=analysis.answer_family,
        deterministic_confidence_before=routing.confidence,
        final_runtime_confidence=analysis.confidence,
        final_runtime_answer_family=analysis.answer_family,
        helper_called=True,
        helper_valid=True,
        hint=hint,
    )
    effective_routing, _, applied = apply_semantic_routing_hint(
        routing=routing,
        analysis=analysis,
        result=result,
        config=replace(
            tiny_project,
            enable_llm_semantic_router=True,
            llm_semantic_router_shadow_only=False,
            llm_semantic_router_trial_policy="no_api_forcing",
        ),
        endpoint_catalog=executor.endpoint_catalog,
    )
    assert applied.hint_applied is True
    assert effective_routing.route_type == "SQL_ONLY"
    assert "route_changed" not in (applied.hint_application_reason or "")


def test_non_shadow_high_confidence_close_candidates_only_not_applied(tiny_project: Config):
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
    hint, reason = validate_semantic_routing_hint(
        {
            **_valid_hint_base(),
            "likely_domain": "schema_dataset",
            "route_suggestion": "SQL_PLUS_API",
            "candidate_tables": ["dim_segment"],
        },
        user_prompt="How many campaigns are there?",
        schema_index=executor.schema_index,
        endpoint_catalog=executor.endpoint_catalog,
    )
    assert hint is not None, reason
    result = SemanticRoutingResult(
        enabled=True,
        shadow_only=False,
        eligibility_reason=["close_table_candidates"],
        deterministic_route_type=routing.route_type,
        deterministic_domain_type=routing.domain_type,
        deterministic_answer_family=analysis.answer_family,
        deterministic_confidence_before=routing.confidence,
        final_runtime_confidence=analysis.confidence,
        final_runtime_answer_family=analysis.answer_family,
        helper_called=True,
        helper_valid=True,
        hint=hint,
    )
    effective_routing, effective_analysis, applied = apply_semantic_routing_hint(
        routing=routing,
        analysis=analysis,
        result=result,
        config=replace(tiny_project, enable_llm_semantic_router=True, llm_semantic_router_shadow_only=False),
        endpoint_catalog=executor.endpoint_catalog,
    )
    assert applied.hint_applied is False
    assert applied.hint_application_skipped_reason == "deterministic_route_high_confidence_or_close_candidates_only"
    assert effective_routing is routing
    assert effective_analysis is analysis


def test_semantic_shadow_report_and_packaging_exclusion(monkeypatch, tiny_project: Config):
    monkeypatch.setattr("scripts.run_llm_semantic_router_shadow_eval.get_llm_client", lambda: FakeLLMClient(available=False))
    report = run_llm_semantic_router_shadow_eval(tiny_project, limit=1, include_generated=False)
    assert report["status"] == "skipped"
    assert report["shadow_only"] is True
    assert (tiny_project.outputs_dir / "reports" / "llm_semantic_router_shadow_eval.json").exists()
    assert "llm_semantic_router_shadow_eval" in NON_SUBMISSION_OUTPUT_DIRS


def test_semantic_isolated_trial_report_and_packaging_exclusion(monkeypatch, tiny_project: Config):
    monkeypatch.setattr("scripts.run_llm_semantic_router_isolated_trial.get_llm_client", lambda: FakeLLMClient())
    monkeypatch.setattr("dashagent.semantic_routing_helper.get_llm_client", lambda: FakeLLMClient())
    report = run_llm_semantic_router_isolated_trial(tiny_project, limit=1, clean=True)
    assert report["status"] == "complete"
    assert report["isolated_non_shadow"] is True
    assert report["official_promotion_performed"] is False
    assert report["packaged_runtime_affected"] is False
    assert (tiny_project.outputs_dir / "llm_semantic_router_isolated_trial" / "tiny_001" / "trajectory.json").exists()
    assert (tiny_project.outputs_dir / "reports" / "llm_semantic_router_isolated_trial.json").exists()
    assert (tiny_project.outputs_dir / "reports" / "llm_semantic_router_promotion_decision.json").exists()
    assert not (tiny_project.outputs_dir / "final_submission").exists()
    assert not (tiny_project.outputs_dir / "eval").exists()
    assert "llm_semantic_router_isolated_trial" in NON_SUBMISSION_OUTPUT_DIRS
    assert "llm_semantic_router_feedback_loop" in NON_SUBMISSION_OUTPUT_DIRS


def test_semantic_isolated_trial_variant_writes_feedback_loop_root(monkeypatch, tiny_project: Config):
    monkeypatch.setattr("scripts.run_llm_semantic_router_isolated_trial.get_llm_client", lambda: FakeLLMClient())
    monkeypatch.setattr("dashagent.semantic_routing_helper.get_llm_client", lambda: FakeLLMClient())
    report = run_llm_semantic_router_isolated_trial(
        tiny_project,
        limit=1,
        clean=True,
        trial_policy="priority_only",
        output_root_name="llm_semantic_router_feedback_loop/priority_only",
        write_reports=False,
    )
    assert report["status"] == "complete"
    assert report["trial_policy"] == "priority_only"
    assert "llm_semantic_router_feedback_loop/priority_only" in report["output_root"]
    assert (tiny_project.outputs_dir / "llm_semantic_router_feedback_loop" / "priority_only" / "tiny_001" / "trajectory.json").exists()
    assert not (tiny_project.outputs_dir / "final_submission").exists()


def test_semantic_shadow_report_includes_normalization_metrics(tiny_project: Config):
    report = _build_report(
        tiny_project,
        [{"prompt_id": "p1"}, {"prompt_id": "p2"}],
        [
            {
                "prompt_id": "p1",
                "status": "passed",
                "eligible": True,
                "helper_called": True,
                "helper_valid": True,
                "normalization_actions": [
                    "synonym_mappings_object_wrapped",
                    "domain_alias:audit->observability",
                ],
            },
            {
                "prompt_id": "p2",
                "status": "passed",
                "eligible": True,
                "helper_called": True,
                "helper_valid": False,
                "helper_rejected_reason": "unknown_table_in_candidate_tables",
                "normalization_actions": [],
            },
        ],
        {"model": "unit-test-model", "backend_type": "openai_sdk", "sdk_path_used": True},
    )
    assert report["valid_helper_outputs"] == 1
    assert report["rejected_helper_outputs"] == 1
    assert report["normalization_actions"]["synonym_mappings_object_wrapped"] == 1
    assert report["normalization_actions_count"] == 2
    assert report["synonym_mappings_coerced_count"] == 1
    assert report["domain_aliases_applied_count"] == 1
    assert len(report["valid_hint_examples"]) == 1
    assert len(report["rejected_hint_examples"]) == 1
    assert report["recommendation"] == "keep_shadow_only"


def test_shadow_report_row_prefers_full_nlp_helper_over_truncated_checkpoint(tmp_path: Path):
    trajectory = {
        "query_id": "example_003",
        "original_query": "List journeys",
        "runtime": 0.01,
        "checkpoints": [
            {
                "checkpoint_id": "checkpoint_llm_semantic_routing_helper",
                "output": {
                    "helper_called": True,
                    "helper_valid": True,
                    "helper_likely_domain": None,
                    "helper_route_suggestion": None,
                    "helper_answer_intent": None,
                    "truncated_fields": 16,
                },
            }
        ],
        "steps": [
            {
                "kind": "nlp",
                "llm_semantic_routing_helper": {
                    "helper_called": True,
                    "helper_valid": True,
                    "helper_likely_domain": "journey_campaign",
                    "helper_route_suggestion": "SQL_ONLY",
                    "helper_answer_intent": "LIST",
                    "normalization_actions": [],
                },
            }
        ],
    }
    row = _row_from_trajectory({"prompt_id": "example_003", "prompt": "List journeys"}, trajectory, 0.01, tmp_path)
    assert row["helper_likely_domain"] == "journey_campaign"
    assert row["helper_route_suggestion"] == "SQL_ONLY"
    assert row["helper_answer_intent"] == "LIST"


def _checkpoint(trajectory: dict, checkpoint_id: str) -> dict:
    for item in trajectory.get("checkpoints", []):
        if item.get("checkpoint_id") == checkpoint_id:
            return item.get("output") or {}
    raise AssertionError(f"missing checkpoint {checkpoint_id}")


def _valid_hint_base() -> dict:
    return {
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
