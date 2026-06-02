from __future__ import annotations

import json

from dashagent.answer_slots import extract_answer_slots
from dashagent.evidence_bus import EvidenceBus
from dashagent.final_answer_claim_extractor import extract_final_answer_claims
from dashagent.llm_final_answer_composer import (
    FINAL_ANSWER_MAX_TOKENS,
    build_llm_final_answer_card,
    check_final_answer_semantic_grounding,
    check_final_answer_syntax,
    parse_llm_final_answer_response,
    safe_llm_final_answer_fallback,
)
from dashagent.llm_unified_planner import LLMUnifiedAPIRequest, LLMUnifiedPass, LLMUnifiedPlan, LLMUnifiedSQLCandidate
from dashagent.planner import PlanStep
from dashagent.result_bundle import ResultBundle


def _sql_tool_result(rows: list[dict]) -> dict:
    return {
        "type": "sql",
        "step": {"action": "sql", "purpose": "test", "sql": "SELECT * FROM dim_campaign"},
        "payload": {"ok": True, "rows": rows, "row_count": len(rows)},
    }


def _api_tool_result(parsed_evidence: dict) -> dict:
    return {
        "type": "api",
        "step": {"action": "api", "method": "GET", "url": "/test", "params": {}, "family": "llm_owned_v2"},
        "payload": {"ok": True, "parsed_evidence": parsed_evidence},
    }


def _bus_and_slots(prompt: str, tool_results: list[dict]) -> tuple[EvidenceBus, object]:
    bus = EvidenceBus()
    for item in tool_results:
        step_payload = item.get("step") or {}
        step = PlanStep(action=step_payload.get("action", ""), purpose="test", sql=step_payload.get("sql"), method=step_payload.get("method"), url=step_payload.get("url"), params=step_payload.get("params") or {}, family=step_payload.get("family"))
        if item["type"] == "sql":
            bus.observe_sql(step, item["payload"])
        if item["type"] == "api":
            bus.observe_api(step, item["payload"])
    return bus, extract_answer_slots(prompt, tool_results)


def test_final_answer_token_budget_is_bounded_for_local_weak_model_smoke():
    assert FINAL_ANSWER_MAX_TOKENS <= 300


def test_syntax_gate_accepts_valid_wrapper_and_rejects_empty_or_malformed_answer():
    parsed = parse_llm_final_answer_response(
        json.dumps(
            {
                "final_answer": "There are 2 campaigns.",
                "used_pass_ids": ["sql_1"],
                "claimed_facts": [{"claim": "There are 2 campaigns.", "supporting_pass_ids": ["sql_1"]}],
                "caveats_included": [],
            }
        )
    )

    assert check_final_answer_syntax(parsed).passed is True
    assert check_final_answer_syntax(parse_llm_final_answer_response("{}")).passed is False
    assert check_final_answer_syntax(parse_llm_final_answer_response("not json")).passed is False


def test_semantic_gate_rejects_unsupported_count_claim():
    tool_results = [_sql_tool_result([{"count": 2}])]
    bus, slots = _bus_and_slots("How many campaigns are there?", tool_results)

    result = check_final_answer_semantic_grounding(
        "There are 3 campaigns.",
        question="How many campaigns are there?",
        runtime_passes=[{"pass_id": "sql_1", "source": "SQL", "status": "SUCCESS", "scope": "LOCAL_SNAPSHOT", "result": {"rows": [{"count": 2}]}}],
        evidence_bus=bus,
        slots=slots,
    )

    assert result.passed is False
    assert result.error_type == "unsupported_claim"
    assert result.unsupported_claims


def test_semantic_gate_rejects_status_contradiction():
    tool_results = [_sql_tool_result([{"name": "Birthday Message", "status": "draft"}])]
    bus, slots = _bus_and_slots("What is the status of Birthday Message?", tool_results)

    result = check_final_answer_semantic_grounding(
        "Birthday Message is published.",
        question="What is the status of Birthday Message?",
        runtime_passes=[{"pass_id": "sql_1", "source": "SQL", "status": "SUCCESS", "scope": "LOCAL_SNAPSHOT", "result": {"rows": [{"name": "Birthday Message", "status": "draft"}]}}],
        evidence_bus=bus,
        slots=slots,
    )

    assert result.passed is False
    assert result.error_type == "contradiction"


def test_semantic_gate_rejects_missing_required_count_when_evidence_contains_it():
    tool_results = [_sql_tool_result([{"count": 2}])]
    bus, slots = _bus_and_slots("How many campaigns are there?", tool_results)

    result = check_final_answer_semantic_grounding(
        "Campaign records were found.",
        question="How many campaigns are there?",
        runtime_passes=[{"pass_id": "sql_1", "source": "SQL", "status": "SUCCESS", "scope": "LOCAL_SNAPSHOT", "result": {"rows": [{"count": 2}]}}],
        evidence_bus=bus,
        slots=slots,
    )

    assert result.passed is False
    assert result.error_type == "missing_required_info"
    assert "count" in result.missing_required_fields


def test_semantic_gate_allows_published_date_answer_without_repeating_status_word():
    tool_results = [_sql_tool_result([{"NAME": "Birthday Message", "CREATEDTIME": "2026-03-31T06:07:32.838462639Z"}])]
    bus, slots = _bus_and_slots('When was the journey "Birthday Message" published?', tool_results)
    slots.statuses = ["published"]

    result = check_final_answer_semantic_grounding(
        "Local snapshot evidence shows Birthday Message date: 2026-03-31T06:07:32.838462639Z.",
        question='When was the journey "Birthday Message" published?',
        runtime_passes=[
            {
                "pass_id": "t1_lookup_journey",
                "source": "SQL",
                "path": "SQL",
                "status": "SUCCESS",
                "scope": "LOCAL_SNAPSHOT",
                "facts": ["NAME:Birthday Message", "CREATEDTIME:2026-03-31T06:07:32.838462639Z"],
                "source_results": [{"source": "SQL", "status": "SUCCESS", "scope": "LOCAL_SNAPSHOT", "result": {"rows": [{"NAME": "Birthday Message", "CREATEDTIME": "2026-03-31T06:07:32.838462639Z"}], "row_count": 1}}],
            }
        ],
        evidence_bus=bus,
        slots=slots,
    )

    assert result.passed is True


def test_semantic_gate_allows_broad_schema_summary_with_count_and_sample():
    rows = [
        {"NAME": "Schema Alpha"},
        {"NAME": "Schema Beta"},
        {"NAME": "Schema Gamma"},
        {"NAME": "Schema Delta"},
    ]
    tool_results = [_sql_tool_result(rows)]
    bus, slots = _bus_and_slots("What schemas do I have?", tool_results)
    slots.sql_row_count = 74
    slots.counts = [74]
    slots.entity_names = ["Schema Alpha", "Schema Beta", "Schema Gamma", "Schema Delta", "Schema Epsilon"]

    result = check_final_answer_semantic_grounding(
        "Based on the local snapshot, there are 74 schemas. Sample schemas include Schema Alpha, Schema Beta, and Schema Gamma.",
        question="What schemas do I have?",
        runtime_passes=[
            {
                "pass_id": "schema_list",
                "source": "SQL",
                "path": "SQL",
                "status": "SUCCESS",
                "scope": "LOCAL_SNAPSHOT",
                "facts": ["NAME:Schema Alpha", "NAME:Schema Beta", "NAME:Schema Gamma"],
                "source_results": [{"source": "SQL", "status": "SUCCESS", "scope": "LOCAL_SNAPSHOT", "result": {"rows": rows, "row_count": 74}}],
            }
        ],
        evidence_bus=bus,
        slots=slots,
    )

    assert result.passed is True


def test_semantic_gate_allows_broad_schema_summary_with_including_word_and_long_names():
    rows = [
        {"NAME": "Adhoc XDM Schema for dataset JOJourneyVersionsDs_e0f2475b-1232-425e-869d-22e671494d5c"},
        {"NAME": "Adhoc XDM Schema for dataset JOJourneyVersionsDs_8e9d4f37-a8bf-4085-bfd5-3c893df100e7"},
        {"NAME": "Adhoc XDM Schema for dataset JOJourneyVersionsDs_f877134c-9ce5-4ca2-b326-881c75f8a355"},
        {"NAME": "Adhoc XDM Schema for dataset JOJourneyVersionsDs_961ddfca-2199-4783-b16c-9226938e0d93"},
    ]
    tool_results = [_sql_tool_result(rows)]
    bus, slots = _bus_and_slots("What schemas do I have?", tool_results)
    slots.sql_row_count = 50
    slots.counts = [50]
    slots.entity_names = [row["NAME"] for row in rows]

    result = check_final_answer_semantic_grounding(
        "The local snapshot contains 50 schemas, including "
        "Adhoc XDM Schema for dataset JOJourneyVersionsDs_e0f2475b-1232-425e-869d-22e671494d5c, "
        "Adhoc XDM Schema for dataset JOJourneyVersionsDs_8e9d4f37-a8bf-4085-bfd5-3c893df100e7, and "
        "Adhoc XDM Schema for dataset JOJourneyVersionsDs_f877134c-9ce5-4ca2-b326-881c75f8a355.",
        question="What schemas do I have?",
        runtime_passes=[
            {
                "pass_id": "schema_list",
                "source": "SQL",
                "path": "SQL",
                "status": "SUCCESS",
                "scope": "LOCAL_SNAPSHOT",
                "facts": [f"NAME:{row['NAME']}" for row in rows[:3]],
                "source_results": [{"source": "SQL", "status": "SUCCESS", "scope": "LOCAL_SNAPSHOT", "result": {"rows": rows, "row_count": 50}}],
            }
        ],
        evidence_bus=bus,
        slots=slots,
    )

    assert result.passed is True


def test_semantic_gate_rejects_local_live_scope_confusion():
    tool_results = [_sql_tool_result([{"count": 2}])]
    bus, slots = _bus_and_slots("How many current schemas are in Adobe Experience Platform?", tool_results)

    result = check_final_answer_semantic_grounding(
        "Adobe Experience Platform currently has 2 schemas.",
        question="How many current schemas are in Adobe Experience Platform?",
        runtime_passes=[{"pass_id": "sql_1", "source": "SQL", "status": "SUCCESS", "scope": "LOCAL_SNAPSHOT", "result": {"rows": [{"count": 2}]}}],
        evidence_bus=bus,
        slots=slots,
    )

    assert result.passed is False
    assert result.error_type == "scope_error"


def test_semantic_gate_rejects_api_error_as_no_data():
    tool_results = [
        {
            "type": "api",
            "step": {"action": "api", "method": "GET", "url": "/test", "params": {}, "family": "llm_owned_v2"},
            "payload": {"ok": False, "dry_run": False, "error": "API unavailable"},
        }
    ]
    bus, slots = _bus_and_slots("Show current schemas.", tool_results)

    result = check_final_answer_semantic_grounding(
        "No schemas were returned.",
        question="Show current schemas.",
        runtime_passes=[{"pass_id": "api_1", "source": "API", "status": "API_ERROR", "scope": "LIVE_API", "result": {}, "caveats": ["API unavailable"]}],
        evidence_bus=bus,
        slots=slots,
    )

    assert result.passed is False
    assert result.error_type == "caveat_error"


def test_semantic_gate_allows_scoped_no_match_for_empty_local_filtered_list():
    tool_results = [_sql_tool_result([])]
    bus, slots = _bus_and_slots("List all datasets that use the schema 'hkg_adls_profile_count_history'.", tool_results)
    slots.counts = [0]
    slots.sql_row_count = 0
    slots.entity_names = ["hkg_adls_profile_count_history"]

    result = check_final_answer_semantic_grounding(
        "No matching runtime evidence was available for this query/scope.",
        question="List all datasets that use the schema 'hkg_adls_profile_count_history'.",
        runtime_passes=[
            {
                "pass_id": "local_schema_dataset_lookup",
                "source": "SQL",
                "path": "SQL",
                "status": "EMPTY",
                "scope": "LOCAL_SNAPSHOT",
                "source_results": [{"source": "SQL", "status": "EMPTY", "scope": "LOCAL_SNAPSHOT", "result": {"rows": [], "row_count": 0}}],
            }
        ],
        evidence_bus=bus,
        slots=slots,
    )

    assert result.passed is True


def test_semantic_gate_allows_api_failed_wording_as_caveat_not_status_claim():
    tool_results = [
        _sql_tool_result([{"name": "Birthday Message", "status": "updated"}]),
        {
            "type": "api",
            "step": {"action": "api", "method": "GET", "url": "/ajo/journey", "params": {}, "family": "llm_owned_v2"},
            "payload": {"ok": False, "dry_run": True, "error": "Adobe credentials unavailable"},
        },
    ]
    bus, slots = _bus_and_slots("Compare local and live status of Birthday Message if both are available.", tool_results)

    result = check_final_answer_semantic_grounding(
        'From the local snapshot, Birthday Message has status "updated". The live API call failed because Adobe credentials were unavailable.',
        question="Compare local and live status of Birthday Message if both are available.",
        runtime_passes=[
            {
                "pass_id": "local_status",
                "source": "SQL",
                "status": "SUCCESS",
                "scope": "LOCAL_SNAPSHOT",
                "facts": ["status: updated", "name: Birthday Message"],
                "source_results": [{"source": "SQL", "status": "SUCCESS", "scope": "LOCAL_SNAPSHOT"}],
                "result": {"rows": [{"name": "Birthday Message", "status": "updated"}]},
            },
            {
                "pass_id": "live_status",
                "source": "API",
                "status": "API_ERROR",
                "scope": "LIVE_API",
                "facts": [],
                "caveats": ["Adobe credentials unavailable"],
                "source_results": [{"source": "API", "status": "ERROR", "scope": "LIVE_API"}],
                "result": {},
            },
        ],
        evidence_bus=bus,
        slots=slots,
    )

    assert result.passed is True


def test_claim_extractor_treats_sentence_final_number_as_count():
    claims = extract_final_answer_claims("The count of schema records in the local snapshot is 10.")

    assert any(claim.type == "COUNT" and claim.value == "10" for claim in claims)


def test_claim_extractor_treats_deployed_time_as_timestamp_wording_not_status():
    claims = extract_final_answer_claims(
        'The local snapshot found "Birthday Message" but did not provide a last deployed time. Live API verification failed because credentials were unavailable.'
    )

    assert not any(claim.type == "STATUS" and claim.value.lower() == "deployed" for claim in claims)
    assert not any(claim.type == "STATUS" and claim.value.lower() == "failed" for claim in claims)


def test_claim_extractor_ignores_numbered_list_markers_as_counts():
    claims = extract_final_answer_claims(
        "Based on the local snapshot, there are 74 schemas.\n\n"
        "1. Schema Alpha\n"
        "2. Schema Beta\n"
        "3. Schema Gamma"
    )

    count_values = [claim.value for claim in claims if claim.type == "COUNT"]
    assert "74" in count_values
    assert "1" not in count_values
    assert "2" not in count_values
    assert "3" not in count_values


def test_claim_extractor_ignores_unquoted_numeric_entity_suffixes_and_percent_names():
    claims = extract_final_answer_claims(
        "The retrieved segments include Person: Birthday Today 001 and Campaign: 25% Off Purchase Offer Reminder."
    )

    count_values = {claim.value for claim in claims if claim.type == "COUNT"}
    assert "001" not in count_values
    assert "25" not in count_values


def test_claim_extractor_ignores_prompt_time_window_and_interval_values_as_counts():
    claims = extract_final_answer_claims(
        "The local snapshot shows 0 ingestion records for the last 90 days. "
        "The destination operates on a daily frequency with an interval of 0."
    )

    count_values = [claim.value for claim in claims if claim.type == "COUNT"]
    assert "0" in count_values
    assert "90" not in count_values
    assert count_values.count("0") == 1


def test_semantic_gate_allows_draft_as_conceptual_example_when_data_statuses_differ():
    tool_results = [
        _sql_tool_result(
            [
                {"name": "Birthday Message", "status": "updated", "campaign_id": "9f4ebca4-2fdd-4873-95f5-8d66bab358c6"},
                {"name": "Gold Tier Welcome Email", "status": "created", "campaign_id": "3f277603-ac4d-4022-a993-8cbd3afc0d62"},
            ]
        )
    ]
    bus, slots = _bus_and_slots("Explain inactive journey and show inactive journeys.", tool_results)

    result = check_final_answer_semantic_grounding(
        'An inactive journey can include a journey in a draft state or one that is not running. Local snapshot journeys: Birthday Message has status "updated"; Gold Tier Welcome Email has status "created".',
        question="Explain inactive journey and show inactive journeys.",
        runtime_passes=[
            {
                "pass_id": "local_inactive",
                "source": "SQL",
                "status": "SUCCESS",
                "scope": "LOCAL_SNAPSHOT",
                "facts": ["name: Birthday Message", "status: updated", "name: Gold Tier Welcome Email", "status: created"],
                "source_results": [{"source": "SQL", "status": "SUCCESS", "scope": "LOCAL_SNAPSHOT"}],
                "result": {"rows": [{"name": "Birthday Message", "status": "updated"}, {"name": "Gold Tier Welcome Email", "status": "created"}]},
            }
        ],
        evidence_bus=bus,
        slots=slots,
    )

    assert result.passed is True


def test_semantic_gate_allows_active_as_conceptual_contrast_when_data_statuses_differ():
    tool_results = [_sql_tool_result([{"name": "Birthday Message", "status": "updated"}, {"name": "Gold Tier Welcome Email", "status": "created"}])]
    bus, slots = _bus_and_slots("Explain inactive journey and show inactive journeys.", tool_results)

    result = check_final_answer_semantic_grounding(
        'An inactive journey is not currently executing. Unlike active or live journeys, inactive journeys are paused. Local snapshot journeys: Birthday Message has status "updated"; Gold Tier Welcome Email has status "created".',
        question="Explain inactive journey and show inactive journeys.",
        runtime_passes=[
            {
                "pass_id": "local_inactive",
                "source": "SQL",
                "status": "SUCCESS",
                "scope": "LOCAL_SNAPSHOT",
                "facts": ["name: Birthday Message", "status: updated", "name: Gold Tier Welcome Email", "status: created"],
                "source_results": [{"source": "SQL", "status": "SUCCESS", "scope": "LOCAL_SNAPSHOT"}],
                "result": {"rows": [{"name": "Birthday Message", "status": "updated"}, {"name": "Gold Tier Welcome Email", "status": "created"}]},
            }
        ],
        evidence_bus=bus,
        slots=slots,
    )

    assert result.passed is True


def test_semantic_gate_allows_product_context_phrase_for_mixed_inactive_answer():
    tool_results = [
        _sql_tool_result(
            [
                {"name": "Birthday Message", "status": "updated", "campaign_id": "9f4ebca4-2fdd-4873-95f5-8d66bab358c6"},
                {"name": "Gold Tier Welcome Email", "status": "created", "campaign_id": "3f277603-ac4d-4022-a993-8cbd3afc0d62"},
            ]
        )
    ]
    bus, slots = _bus_and_slots("Explain inactive journey and show inactive journeys.", tool_results)

    result = check_final_answer_semantic_grounding(
        "An inactive journey in Journey Optimizer refers to a marketing automation workflow that is not currently executing or set to active. "
        "Based on the local snapshot, there are two such journeys: Birthday Message (ID 9f4ebca4-2fdd-4873-95f5-8d66bab358c6) and Gold Tier Welcome Email (ID 3f277603-ac4d-4022-a993-8cbd3afc0d62). "
        "Live API evidence was unavailable due to Adobe credentials being unavailable, so no comparison with live state could be performed.",
        question="Explain inactive journey and show inactive journeys.",
        runtime_passes=[
            {
                "pass_id": "local_inactive",
                "source": "SQL",
                "status": "SUCCESS",
                "scope": "LOCAL_SNAPSHOT",
                "facts": [
                    "name: Birthday Message",
                    "status: updated",
                    "name: Gold Tier Welcome Email",
                    "status: created",
                    "id: 9f4ebca4-2fdd-4873-95f5-8d66bab358c6",
                    "id: 3f277603-ac4d-4022-a993-8cbd3afc0d62",
                ],
                "source_results": [{"source": "SQL", "status": "SUCCESS", "scope": "LOCAL_SNAPSHOT"}],
                "result": {
                    "rows": [
                        {"name": "Birthday Message", "status": "updated", "campaign_id": "9f4ebca4-2fdd-4873-95f5-8d66bab358c6"},
                        {"name": "Gold Tier Welcome Email", "status": "created", "campaign_id": "3f277603-ac4d-4022-a993-8cbd3afc0d62"},
                    ]
                },
            },
            {"pass_id": "live_inactive", "source": "API", "status": "API_ERROR", "scope": "LIVE_API", "result": {}, "caveats": ["Adobe credentials unavailable"]},
        ],
        evidence_bus=bus,
        slots=slots,
    )

    assert result.passed is True


def test_semantic_gate_rejects_live_empty_as_global_absence():
    tool_results = [_api_tool_result({"evidence_state": "live_empty", "live_evidence_available": True, "counts": {"items": 0}, "names": []})]
    bus, slots = _bus_and_slots("Show current schemas.", tool_results)

    result = check_final_answer_semantic_grounding(
        "There are no schemas in Adobe Experience Platform.",
        question="Show current schemas.",
        runtime_passes=[{"pass_id": "api_1", "source": "API", "status": "LIVE_EMPTY", "scope": "LIVE_API", "result": {}, "caveats": []}],
        evidence_bus=bus,
        slots=slots,
    )

    assert result.passed is False
    assert result.error_type == "caveat_error"


def test_final_answer_card_requires_partial_local_evidence_before_api_caveat():
    plan = LLMUnifiedPlan(
        route="EVIDENCE_PIPELINE",
        evidence_order="MULTI_PASS",
        direct_answer=None,
        sql=LLMUnifiedSQLCandidate(query='SELECT "NAME", "STATUS" FROM "dim_campaign"', params=[]),
        api_request=LLMUnifiedAPIRequest(method="GET", path="/ajo/journey", params={}),
        passes=[
            LLMUnifiedPass(
                pass_id="local_status",
                subtask="Retrieve local status.",
                path="SQL",
                can_run_parallel=True,
                depends_on=[],
                evidence_order="SQL_FIRST",
                sql=LLMUnifiedSQLCandidate(query='SELECT "NAME", "STATUS" FROM "dim_campaign"', params=[]),
                api_request=None,
                expected_result="Local status.",
            ),
            LLMUnifiedPass(
                pass_id="live_status",
                subtask="Retrieve live status.",
                path="API",
                can_run_parallel=True,
                depends_on=[],
                evidence_order="API_FIRST",
                sql=None,
                api_request=LLMUnifiedAPIRequest(method="GET", path="/ajo/journey", params={}),
                expected_result="Live status.",
            ),
        ],
        aggregation_instruction="Use local evidence and include live API caveat if live fails.",
        reason="test",
        provider="openai",
        model="unit",
    )
    runtime_passes = [
        {
            "pass_id": "local_status",
            "source": "SQL",
            "status": "SUCCESS",
            "scope": "LOCAL_SNAPSHOT",
            "facts": ["name: Birthday Message", "status: updated"],
            "source_results": [{"source": "SQL", "status": "SUCCESS", "scope": "LOCAL_SNAPSHOT"}],
        },
        {
            "pass_id": "live_status",
            "source": "API",
            "status": "API_ERROR",
            "scope": "LIVE_API",
            "facts": [],
            "caveats": ["Adobe credentials unavailable"],
            "source_results": [{"source": "API", "status": "ERROR", "scope": "LIVE_API"}],
        },
    ]
    evidence_bus = EvidenceBus(run_id="unit")
    for item in runtime_passes:
        evidence_bus.observe_pass_result(item)
    slots = extract_answer_slots(
        "Compare local and live status of Birthday Message if both are available.",
        [
            _sql_tool_result([{"name": "Birthday Message", "status": "updated"}]),
            {
                "type": "api",
                "step": {"action": "api", "method": "GET", "url": "/ajo/journey", "params": {}, "family": "llm_owned_v2"},
                "payload": {"ok": False, "dry_run": True, "error": "Adobe credentials unavailable"},
            },
        ],
    )
    bundle = ResultBundle.from_pass_results(runtime_passes, [], run_id="unit")

    card = build_llm_final_answer_card(
        user_prompt="Compare local and live status of Birthday Message if both are available.",
        llm_plan=plan,
        runtime_passes=runtime_passes,
        evidence_bus=evidence_bus,
        answer_slots=slots,
        result_bundle=bundle,
        aggregation_instruction=plan.aggregation_instruction,
    )

    constraints = " ".join(card["constraints"])
    assert "If any required local evidence succeeded" in constraints
    assert "Only use the global runtime-unavailable answer if all required evidence failed" in constraints
    assert card["AVAILABLE_RUNTIME_FACTS"]
    assert card["AVAILABLE_RUNTIME_FACTS"][0]["task_id"] == "local_status"
    assert "Birthday Message" in json.dumps(card["AVAILABLE_RUNTIME_FACTS"])
    assert card["FAILED_OR_UNAVAILABLE_SOURCES"]
    assert card["FAILED_OR_UNAVAILABLE_SOURCES"][0]["task_id"] == "live_status"


def test_final_answer_card_repair_context_exposes_gate_errors_and_runtime_facts():
    plan = LLMUnifiedPlan(
        route="EVIDENCE_PIPELINE",
        evidence_order="SQL_FIRST",
        direct_answer=None,
        sql=LLMUnifiedSQLCandidate(query='SELECT COUNT(*) AS "count" FROM "dim_blueprint"', params=[]),
        api_request=None,
        passes=[
            LLMUnifiedPass(
                pass_id="local_count",
                subtask="Count schema records in the local snapshot.",
                path="SQL",
                can_run_parallel=True,
                depends_on=[],
                evidence_order="SQL_FIRST",
                sql=LLMUnifiedSQLCandidate(query='SELECT COUNT(*) AS "count" FROM "dim_blueprint"', params=[]),
                api_request=None,
                expected_result="Schema count.",
            )
        ],
        aggregation_instruction="Answer with the schema count.",
        reason="test",
        provider="openai",
        model="unit",
    )
    runtime_passes = [
        {
            "pass_id": "local_count",
            "source": "SQL",
            "path": "SQL",
            "status": "SUCCESS",
            "scope": "LOCAL_SNAPSHOT",
            "facts": ["count: 74"],
            "source_results": [
                {
                    "source": "SQL",
                    "status": "SUCCESS",
                    "scope": "LOCAL_SNAPSHOT",
                    "result": {"rows": [{"count": 74}], "row_count": 1},
                }
            ],
            "result": {"rows": [{"count": 74}], "row_count": 1},
        }
    ]
    evidence_bus = EvidenceBus(run_id="unit")
    evidence_bus.counts.append(74)
    evidence_bus.observe_pass_result(runtime_passes[0])
    slots = extract_answer_slots("How many schema records are in the local snapshot?", [_sql_tool_result([{"count": 74}])])
    bundle = ResultBundle.from_pass_results(runtime_passes, [], run_id="unit")

    card = build_llm_final_answer_card(
        user_prompt="How many schema records are in the local snapshot?",
        llm_plan=plan,
        runtime_passes=runtime_passes,
        evidence_bus=evidence_bus,
        answer_slots=slots,
        result_bundle=bundle,
        repair_context={
            "previous_answer": "Runtime evidence was unavailable; cannot provide a verified answer.",
            "semantic_gate": {
                "error_type": "missing_required_info",
                "missing_required_fields": ["count"],
                "scope_errors": [],
                "unsupported_claims": [],
            },
        },
    )

    serialized = json.dumps(card, sort_keys=True)
    assert '"AVAILABLE_RUNTIME_FACTS"' in serialized
    assert "count: 74" in serialized
    assert "missing_required_info" in serialized
    assert "previous_answer" in serialized
    assert "Runtime evidence was unavailable" in serialized


def test_final_answer_card_compacts_large_result_bundle_but_keeps_available_facts():
    plan = LLMUnifiedPlan(
        route="EVIDENCE_PIPELINE",
        evidence_order="SQL_FIRST",
        direct_answer=None,
        sql=LLMUnifiedSQLCandidate(query='SELECT "NAME", "STATUS" FROM "dim_campaign"', params=[]),
        api_request=None,
        passes=[
            LLMUnifiedPass(
                pass_id="local_inactive",
                subtask="List inactive journeys.",
                path="SQL",
                can_run_parallel=True,
                depends_on=[],
                evidence_order="SQL_FIRST",
                sql=LLMUnifiedSQLCandidate(query='SELECT "NAME", "STATUS" FROM "dim_campaign"', params=[]),
                api_request=None,
                expected_result="Inactive journeys.",
            )
        ],
        aggregation_instruction="Give a concise concept sentence and local inactive journey list.",
        reason="test",
        provider="openai",
        model="unit",
    )
    rows = [{"name": f"Journey {idx}", "status": "created", "notes": "x" * 200} for idx in range(40)]
    rows[0]["name"] = "Birthday Message"
    runtime_passes = [
        {
            "pass_id": "local_inactive",
            "source": "SQL",
            "path": "SQL",
            "status": "SUCCESS",
            "scope": "LOCAL_SNAPSHOT",
            "facts": ["name: Birthday Message", "status: created"],
            "source_results": [{"source": "SQL", "status": "SUCCESS", "scope": "LOCAL_SNAPSHOT", "result": {"rows": rows, "row_count": len(rows)}}],
            "result": {"rows": rows, "row_count": len(rows)},
        }
    ]
    evidence_bus = EvidenceBus(run_id="unit")
    evidence_bus.observe_pass_result(runtime_passes[0])
    slots = extract_answer_slots("Explain inactive journey and show inactive journeys.", [_sql_tool_result(rows[:2])])

    card = build_llm_final_answer_card(
        user_prompt="Explain inactive journey and show inactive journeys.",
        llm_plan=plan,
        runtime_passes=runtime_passes,
        evidence_bus=evidence_bus,
        answer_slots=slots,
        result_bundle=ResultBundle.from_pass_results(runtime_passes, [{"payload": {"rows": rows}}], run_id="unit"),
    )

    serialized = json.dumps(card, sort_keys=True)
    assert len(serialized) < 15000
    assert "Birthday Message" in json.dumps(card["AVAILABLE_RUNTIME_FACTS"], sort_keys=True)
    assert serialized.count("x" * 80) < 3


def test_direct_concept_pass_is_not_required_as_runtime_evidence():
    plan = LLMUnifiedPlan(
        route="EVIDENCE_PIPELINE",
        evidence_order="MULTI_PASS",
        direct_answer=None,
        sql=LLMUnifiedSQLCandidate(query='SELECT "NAME" FROM "dim_campaign"', params=[]),
        api_request=None,
        passes=[
            LLMUnifiedPass(
                pass_id="concept",
                subtask="Explain inactive journey.",
                path="DIRECT",
                can_run_parallel=True,
                depends_on=[],
                evidence_order="NO_EVIDENCE",
                sql=None,
                api_request=None,
                expected_result="Concept explanation.",
            ),
            LLMUnifiedPass(
                pass_id="local_rows",
                subtask="Show inactive journeys.",
                path="SQL",
                can_run_parallel=True,
                depends_on=[],
                evidence_order="SQL_FIRST",
                sql=LLMUnifiedSQLCandidate(query='SELECT "NAME" FROM "dim_campaign"', params=[]),
                api_request=None,
                expected_result="Local rows.",
            ),
        ],
        aggregation_instruction="Answer concept plus local rows.",
        reason="test",
        provider="openai",
        model="unit",
    )
    card = build_llm_final_answer_card(
        user_prompt="Explain inactive journey means and show inactive journeys.",
        llm_plan=plan,
        runtime_passes=[
            {"pass_id": "concept", "source": "DIRECT", "path": "DIRECT", "status": "SUCCESS", "scope": "NO_EVIDENCE", "facts": ["concept: not currently active"], "source_results": []},
            {
                "pass_id": "local_rows",
                "source": "SQL",
                "path": "SQL",
                "status": "SUCCESS",
                "scope": "LOCAL_SNAPSHOT",
                "facts": ["name: Birthday Message"],
                "source_results": [{"source": "SQL", "status": "SUCCESS", "scope": "LOCAL_SNAPSHOT"}],
            },
        ],
        evidence_bus=EvidenceBus(run_id="unit"),
        answer_slots=extract_answer_slots("Explain inactive journey means and show inactive journeys.", [_sql_tool_result([{"name": "Birthday Message"}])]),
    )

    assert "concept" not in card["required_task_ids"]
    assert "local_rows" in card["required_task_ids"]


def test_semantic_alias_pass_is_satisfied_by_same_reused_fact_once():
    plan = LLMUnifiedPlan(
        route="EVIDENCE_PIPELINE",
        evidence_order="MULTI_PASS",
        direct_answer=None,
        sql=LLMUnifiedSQLCandidate(query='SELECT "NAME", "STATUS" FROM "dim_campaign"', params=[]),
        api_request=None,
        passes=[
            LLMUnifiedPass(
                pass_id="local_status",
                subtask="Retrieve local status.",
                path="SQL",
                can_run_parallel=True,
                depends_on=[],
                evidence_order="SQL_FIRST",
                sql=LLMUnifiedSQLCandidate(query='SELECT "NAME", "STATUS" FROM "dim_campaign"', params=[]),
                api_request=None,
                expected_result="Local status.",
                semantic_cache_key="local_status:Birthday Message",
                result_contract={
                    "source": "LOCAL_SNAPSHOT",
                    "object": "journey",
                    "entity": "Birthday Message",
                    "operation": "STATUS",
                    "fields": ["NAME", "STATUS"],
                    "filters": [{"field": "NAME", "op": "=", "value": "Birthday Message"}],
                    "scope": "local",
                    "freshness": "same_run",
                },
            ),
            LLMUnifiedPass(
                pass_id="local_status_again",
                subtask="Reuse local status.",
                path="CACHE_ALIAS",
                can_run_parallel=False,
                depends_on=["local_status"],
                evidence_order="NO_EVIDENCE",
                sql=None,
                api_request=None,
                expected_result="Same local status.",
                reuse_result_from="local_status",
                semantic_cache_key="local_status:Birthday Message",
                result_contract={
                    "source": "LOCAL_SNAPSHOT",
                    "object": "journey",
                    "entity": "Birthday Message",
                    "operation": "STATUS",
                    "fields": ["NAME", "STATUS"],
                    "filters": [{"field": "NAME", "op": "=", "value": "Birthday Message"}],
                    "scope": "local",
                    "freshness": "same_run",
                },
            ),
        ],
        aggregation_instruction="Use the local status once; the second task is a same-run alias.",
        reason="test",
        provider="openai",
        model="unit",
    )
    runtime_passes = [
        {
            "pass_id": "local_status",
            "source": "SQL",
            "path": "SQL",
            "status": "SUCCESS",
            "scope": "LOCAL_SNAPSHOT",
            "facts": ["name: Birthday Message", "status: active"],
            "source_results": [{"source": "SQL", "status": "SUCCESS", "scope": "LOCAL_SNAPSHOT", "result": {"rows": [{"NAME": "Birthday Message", "STATUS": "active"}]}}],
        },
        {
            "pass_id": "local_status_again",
            "source": "SEMANTIC_CACHE_ALIAS",
            "path": "CACHE_ALIAS",
            "status": "SUCCESS",
            "scope": "LOCAL_SNAPSHOT",
            "facts": ["name: Birthday Message", "status: active"],
            "depends_on": ["local_status"],
            "reuse_result_from": "local_status",
            "semantic_cache_key": "local_status:Birthday Message",
            "alias_materialized": True,
            "shared_execution_id": "unit:local_status",
            "source_results": [
                {
                    "source": "SEMANTIC_CACHE_ALIAS",
                    "status": "SUCCESS",
                    "scope": "LOCAL_SNAPSHOT",
                    "result": {"producer_pass_id": "local_status"},
                }
            ],
        },
    ]
    bus = EvidenceBus(run_id="unit")
    for item in runtime_passes:
        bus.observe_pass_result(item)
    slots = extract_answer_slots("Show the local status of Birthday Message, then use the same local status again.", [_sql_tool_result([{"NAME": "Birthday Message", "STATUS": "active"}])])

    card = build_llm_final_answer_card(
        user_prompt="Show the local status of Birthday Message, then use the same local status again.",
        llm_plan=plan,
        runtime_passes=runtime_passes,
        evidence_bus=bus,
        answer_slots=slots,
        result_bundle=ResultBundle.from_pass_results(runtime_passes, [], run_id="unit"),
    )
    gate = check_final_answer_semantic_grounding(
        "Birthday Message has local status active.",
        question="Show the local status of Birthday Message, then use the same local status again.",
        runtime_passes=runtime_passes,
        evidence_bus=bus,
        slots=slots,
    )

    assert card["pass_result_checklist"][1]["alias_materialized"] is True
    assert card["pass_result_checklist"][1]["reuse_result_from"] == "local_status"
    assert card["AVAILABLE_RUNTIME_FACTS"][1]["source"] == "CACHE_ALIAS"
    assert gate.passed is True


def test_safe_error_fallback_uses_semantic_gate_safe_wording():
    answer = safe_llm_final_answer_fallback([{"status": "ERROR"}])
    bus, slots = _bus_and_slots("When was the journey Birthday Message published?", [])

    result = check_final_answer_semantic_grounding(
        answer,
        question="When was the journey Birthday Message published?",
        runtime_passes=[{"pass_id": "p1", "status": "ERROR", "source_results": []}],
        evidence_bus=bus,
        slots=slots,
    )

    assert answer == "Runtime evidence was unavailable; cannot provide a verified answer."
    assert result.passed is True


def test_safe_fallback_with_runtime_facts_summarizes_scoped_evidence_not_global_unavailable():
    answer = safe_llm_final_answer_fallback(
        [
            {
                "pass_id": "local_count",
                "path": "SQL",
                "source": "SQL",
                "status": "SUCCESS",
                "scope": "LOCAL_SNAPSHOT",
                "facts": ["count: 74"],
                "source_results": [{"source": "SQL", "status": "SUCCESS", "scope": "LOCAL_SNAPSHOT"}],
            }
        ]
    )

    assert answer.startswith("Local snapshot evidence shows")
    assert "count: 74" in answer
    assert "Runtime evidence was unavailable" not in answer
    assert "could not compose a verified final answer" not in answer


def test_safe_fallback_with_empty_local_count_and_api_error_keeps_zero_count_scope():
    runtime_passes = [
        {
            "pass_id": "local_daily_values",
            "path": "SQL",
            "source": "SQL",
            "status": "EMPTY",
            "scope": "LOCAL_SNAPSHOT",
            "facts": [],
            "source_results": [
                {
                    "source": "SQL",
                    "status": "EMPTY",
                    "scope": "LOCAL_SNAPSHOT",
                    "result": {"rows": [], "row_count": 0},
                }
            ],
        },
        {
            "pass_id": "live_daily_values",
            "path": "API",
            "source": "API",
            "status": "API_ERROR",
            "scope": "LIVE_API",
            "caveats": ["Adobe credentials unavailable; API call not executed."],
            "source_results": [
                {
                    "source": "API",
                    "status": "API_ERROR",
                    "scope": "LIVE_API",
                    "error": "Adobe credentials unavailable; API call not executed.",
                }
            ],
        },
    ]
    answer = safe_llm_final_answer_fallback(runtime_passes)

    lowered = answer.lower()
    assert "local snapshot evidence shows" in lowered
    assert "0" in lowered
    assert "live api evidence was unavailable" in lowered
    assert "runtime evidence was unavailable" not in lowered

    bus, slots = _bus_and_slots(
        "What are the daily record success count values between 2026-03-15 and 2026-03-31?",
        [_sql_tool_result([])],
    )
    slots.counts = [0]
    slots.sql_row_count = 0
    bus.api_errors.append("Adobe credentials unavailable; API call not executed.")
    gate = check_final_answer_semantic_grounding(
        answer,
        question="What are the daily record success count values between 2026-03-15 and 2026-03-31?",
        runtime_passes=runtime_passes,
        evidence_bus=bus,
        slots=slots,
    )

    assert gate.passed is True


def test_safe_fallback_prefers_structured_values_over_raw_json_like_facts():
    answer = safe_llm_final_answer_fallback(
        [
            {
                "pass_id": "segment_defs",
                "path": "SQL",
                "source": "SQL",
                "status": "SUCCESS",
                "scope": "LOCAL_SNAPSHOT",
                "facts": [
                    'DEFINITION: {"nodeType":"fnApply","params":[{"fieldName":"birthDate"}]}',
                    "NAME: Person: Birthday Today 001",
                    "LIFECYCLESTATUS: published",
                ],
                "source_results": [
                    {
                        "source": "SQL",
                        "status": "SUCCESS",
                        "scope": "LOCAL_SNAPSHOT",
                        "result": {
                            "row_count": 1,
                            "rows": [
                                {
                                    "NAME": "Person: Birthday Today 001",
                                    "LIFECYCLESTATUS": "published",
                                }
                            ],
                        },
                    }
                ],
            }
        ]
    )

    assert "Person: Birthday Today 001" in answer
    assert "status: published" in answer
    assert "nodeType" not in answer


def test_safe_fallback_broad_schema_list_uses_examples_include_and_passes_gate():
    rows = [
        {"NAME": "Schema Alpha", "SCHEMAID": "schema-alpha"},
        {"NAME": "Schema Beta", "SCHEMAID": "schema-beta"},
        {"NAME": "Schema Gamma", "SCHEMAID": "schema-gamma"},
    ]
    runtime_passes = [
        {
            "pass_id": "t1_local_schemas",
            "path": "SQL",
            "source": "SQL",
            "status": "SUCCESS",
            "scope": "LOCAL_SNAPSHOT",
            "facts": ["NAME: Schema Alpha", "NAME: Schema Beta", "NAME: Schema Gamma"],
            "source_results": [{"source": "SQL", "status": "SUCCESS", "scope": "LOCAL_SNAPSHOT", "result": {"rows": rows, "row_count": 50}}],
        }
    ]
    answer = safe_llm_final_answer_fallback(runtime_passes)
    bus, slots = _bus_and_slots("What schemas do I have?", [_sql_tool_result(rows)])
    slots.sql_row_count = 50
    slots.counts = [50]
    slots.entity_names = [row["NAME"] for row in rows]

    gate = check_final_answer_semantic_grounding(
        answer,
        question="What schemas do I have?",
        runtime_passes=runtime_passes,
        evidence_bus=bus,
        slots=slots,
    )

    assert "examples include" in answer
    assert gate.passed is True


def test_safe_fallback_ignores_failed_direct_concept_task_when_local_data_succeeds():
    answer = safe_llm_final_answer_fallback(
        [
            {
                "pass_id": "t1_concept",
                "path": "DIRECT",
                "source": "DIRECT",
                "status": "ERROR",
                "scope": "CONCEPT",
                "caveats": ["unsafe direct task answer"],
                "source_results": [{"source": "DIRECT", "status": "ERROR", "scope": "CONCEPT"}],
            },
            {
                "pass_id": "t2_local",
                "path": "SQL",
                "source": "SQL",
                "status": "SUCCESS",
                "scope": "LOCAL_SNAPSHOT",
                "facts": ["NAME: Birthday Message", "NAME: Gold Tier Welcome Email", "STATUS: updated"],
                "source_results": [
                    {
                        "source": "SQL",
                        "status": "SUCCESS",
                        "scope": "LOCAL_SNAPSHOT",
                        "result": {
                            "row_count": 2,
                            "rows": [
                                {"NAME": "Birthday Message", "STATUS": "updated"},
                                {"NAME": "Gold Tier Welcome Email", "STATUS": "created"},
                            ],
                        },
                    }
                ],
            },
        ]
    )

    assert "Birthday Message" in answer
    assert "Gold Tier Welcome Email" in answer
    assert "Some requested runtime evidence was unavailable" not in answer


def test_safe_fallback_with_local_status_and_api_error_gives_scoped_evidence_state_answer():
    runtime_passes = [
            {
                "pass_id": "local_campaign_status",
                "path": "SQL",
                "source": "SQL",
                "status": "SUCCESS",
                "scope": "LOCAL_SNAPSHOT",
                "facts": ["name: Birthday Message", "status: updated"],
                "source_results": [
                    {
                        "source": "SQL",
                        "status": "SUCCESS",
                        "scope": "LOCAL_SNAPSHOT",
                        "result": {
                            "row_count": 1,
                            "rows": [
                                {
                                    "NAME": "Birthday Message",
                                    "STATUS": "updated",
                                    "STATE": "updated",
                                    "CAMPAIGNID": "9f4ebca4-2fdd-4873-95f5-8d66bab358c6",
                                }
                            ],
                        },
                    }
                ],
            },
            {
                "pass_id": "live_journey_status",
                "path": "API",
                "source": "API",
                "status": "API_ERROR",
                "scope": "LIVE_API",
                "caveats": ["Adobe credentials unavailable; API call not executed."],
                "source_results": [
                    {
                        "source": "API",
                        "status": "API_ERROR",
                        "scope": "LIVE_API",
                        "error": "Adobe credentials unavailable; API call not executed.",
                    }
                ],
            },
        ]
    answer = safe_llm_final_answer_fallback(runtime_passes)

    lowered = answer.lower()
    assert "local snapshot evidence shows" in lowered
    assert "birthday message" in lowered
    assert "updated" in lowered
    assert "live" in lowered
    assert "unavailable" in lowered or "api" in lowered
    assert "could not compose a verified final answer" not in lowered
    assert "runtime evidence was unavailable" not in lowered

    bus, slots = _bus_and_slots(
        "Compare local and live status of Birthday Message if both are available.",
        [
            _sql_tool_result(
                [
                    {
                        "NAME": "Birthday Message",
                        "STATUS": "updated",
                        "STATE": "updated",
                        "CAMPAIGNID": "9f4ebca4-2fdd-4873-95f5-8d66bab358c6",
                    }
                ]
            )
        ],
    )
    bus.api_errors.append("Adobe credentials unavailable; API call not executed.")

    fallback_gate = check_final_answer_semantic_grounding(
        answer,
        question="Compare local and live status of Birthday Message if both are available.",
        runtime_passes=runtime_passes,
        evidence_bus=bus,
        slots=slots,
    )
    fabricated_live_gate = check_final_answer_semantic_grounding(
        "Local status is updated, and the live status is active.",
        question="Compare local and live status of Birthday Message if both are available.",
        runtime_passes=runtime_passes,
        evidence_bus=bus,
        slots=slots,
    )

    assert fallback_gate.passed is True
    assert fabricated_live_gate.passed is False


def test_semantic_gate_allows_extra_correct_context_without_gold_wording():
    tool_results = [_sql_tool_result([{"count": 2}])]
    bus, slots = _bus_and_slots("How many campaigns are there?", tool_results)

    result = check_final_answer_semantic_grounding(
        "There are 2 campaigns. This count comes from the runtime SQL evidence.",
        question="How many campaigns are there?",
        runtime_passes=[{"pass_id": "sql_1", "source": "SQL", "status": "SUCCESS", "scope": "LOCAL_SNAPSHOT", "result": {"rows": [{"count": 2}]}}],
        evidence_bus=bus,
        slots=slots,
    )

    assert result.passed is True
    serialized = json.dumps(result.to_dict(), sort_keys=True).lower()
    assert "gold_answer" not in serialized
    assert "expected_trace" not in serialized


def test_semantic_gate_catches_ignored_necessary_pass_result():
    tool_results = [_sql_tool_result([{"count": 2}])]
    bus, slots = _bus_and_slots("Count campaigns locally and verify the live API result.", tool_results)
    bus.api_names.append("Birthday Message")

    result = check_final_answer_semantic_grounding(
        "There are 2 campaigns.",
        question="Count campaigns locally and verify the live API result.",
        runtime_passes=[
            {
                "pass_id": "local_count",
                "source_results": [{"source": "SQL", "status": "SUCCESS", "scope": "LOCAL_SNAPSHOT", "result": {"rows": [{"count": 2}]}}],
                "facts": ["count:2"],
                "caveats": [],
            },
            {
                "pass_id": "live_probe",
                "source_results": [{"source": "API", "status": "SUCCESS", "scope": "LIVE_API", "result": {"parsed_evidence": {"names": ["Birthday Message"]}}}],
                "facts": ["names:Birthday Message"],
                "caveats": [],
            },
        ],
        evidence_bus=bus,
        slots=slots,
    )

    assert result.passed is False
    assert result.error_type == "missing_required_info"
    assert "pass:live_probe" in result.missing_required_fields
