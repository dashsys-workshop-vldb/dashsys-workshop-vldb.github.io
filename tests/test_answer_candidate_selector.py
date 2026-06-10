from __future__ import annotations

from dashagent.answer_candidate_selector import select_answer_candidate
from dashagent.answer_slots import AnswerSlots


def _slots(query: str, **overrides) -> AnswerSlots:
    slots = AnswerSlots(query=query, answer_family=overrides.pop("answer_family", "unit"))
    for key, value in overrides.items():
        setattr(slots, key, value)
    return slots


def test_selector_prefers_legacy_when_llm_omits_available_count() -> None:
    slots = _slots(
        "How many failed flow runs are in the local snapshot?",
        counts=[2],
        statuses=["failed"],
        sql_row_count=2,
    )

    selected = select_answer_candidate(
        prompt=slots.query,
        slots=slots,
        evidence_bus={},
        llm_answer="The failed flow runs are available in the evidence.",
        llm_verification={"ok": True, "unsupported_claims": []},
        legacy_answer="The local snapshot has 2 failed flow runs.",
        grounded_answer="Results: failed flow runs.",
    )

    assert selected.selected_source == "LEGACY_SAFE_RENDERER"
    assert selected.selected_answer == "The local snapshot has 2 failed flow runs."
    assert "COUNT_COVERAGE_ADVANTAGE" in selected.selection_codes


def test_legacy_first_structured_selector_keeps_legacy_when_hybrid_loses_exact_number() -> None:
    slots = _slots("How many schemas do I have?", counts=[74], sql_row_count=1)

    selected = select_answer_candidate(
        prompt=slots.query,
        slots=slots,
        evidence_bus={},
        hybrid_answer="There are schemas.",
        hybrid_verification={"ok": True, "unsupported_claims": []},
        legacy_answer="You have 74 schemas.",
        grounded_answer="There are schemas.",
    )

    assert selected.selected_source == "LEGACY_SAFE_RENDERER"
    assert "REJECT_HYBRID_MISSING_EXACT_FACT" in selected.selection_codes
    assert "SELECT_LEGACY_STRUCTURED_DEFAULT" in selected.selection_codes


def test_legacy_first_structured_selector_keeps_legacy_when_hybrid_changes_object_label() -> None:
    slots = _slots("How many schemas do I have?", counts=[74], sql_row_count=1)

    selected = select_answer_candidate(
        prompt=slots.query,
        slots=slots,
        evidence_bus={},
        hybrid_answer="There are 74 records.",
        hybrid_verification={"ok": True, "unsupported_claims": []},
        legacy_answer="You have 74 schemas.",
        grounded_answer="There are 74 records.",
    )

    assert selected.selected_source == "LEGACY_SAFE_RENDERER"
    assert "REJECT_HYBRID_WRONG_OBJECT_LABEL" in selected.selection_codes


def test_legacy_first_structured_selector_keeps_legacy_when_hybrid_adds_unneeded_scope_caveat() -> None:
    slots = _slots("How many schemas do I have?", counts=[74], sql_row_count=1)

    selected = select_answer_candidate(
        prompt=slots.query,
        slots=slots,
        evidence_bus={},
        hybrid_answer="There are 74 schemas in the local snapshot. API unavailable/error; cannot verify live state.",
        hybrid_verification={"ok": True, "unsupported_claims": []},
        legacy_answer="You have 74 schemas.",
        grounded_answer="There are 74 schemas in the local snapshot.",
    )

    assert selected.selected_source == "LEGACY_SAFE_RENDERER"
    assert "REJECT_HYBRID_EXTRA_SCOPE_CAVEAT" in selected.selection_codes


def test_legacy_first_structured_selector_allows_hybrid_extra_runtime_coverage() -> None:
    slots = _slots(
        "List schemas with IDs.",
        entity_names=["Profile Schema"],
        entity_ids=["schema-1"],
    )

    selected = select_answer_candidate(
        prompt=slots.query,
        slots=slots,
        evidence_bus={},
        hybrid_answer="Profile Schema (schema-1).",
        hybrid_verification={"ok": True, "unsupported_claims": []},
        legacy_answer="Profile Schema.",
        grounded_answer="Profile Schema (schema-1).",
    )

    assert selected.selected_source == "HYBRID_ANSWER"
    assert "SELECT_HYBRID_EXTRA_RUNTIME_COVERAGE" in selected.selection_codes


def test_legacy_first_structured_selector_keeps_zero_row_no_result_legacy() -> None:
    slots = _slots(
        "List all segment audiences connected to the destination named 'SMS Opt-In'.",
        sql_row_count=0,
        entity_names=["Activate segments to S3 Feed"],
        entity_ids=["139bece0-5266-46bd-8ed3-fc1dd5eb5dd4"],
        api_error=True,
    )

    selected = select_answer_candidate(
        prompt=slots.query,
        slots=slots,
        evidence_bus={},
        hybrid_answer="Audiences: Activate segments to S3 Feed id=139bece0-5266-46bd-8ed3-fc1dd5eb5dd4.",
        hybrid_verification={"ok": True, "unsupported_claims": []},
        legacy_answer="Based on the evidence provided, there is no data available to answer this question. The SQL query returned zero rows.",
        grounded_answer="Audiences: Activate segments to S3 Feed id=139bece0-5266-46bd-8ed3-fc1dd5eb5dd4.",
    )

    assert selected.selected_source == "LEGACY_SAFE_RENDERER"
    assert "REJECT_HYBRID_UNSUPPORTED" in selected.selection_codes


def test_selector_prefers_legacy_when_llm_omits_status() -> None:
    slots = _slots(
        "What is the status of Journey A?",
        entity_names=["Journey A"],
        statuses=["inactive"],
        first_rows=[{"name": "Journey A", "status": "inactive"}],
    )

    selected = select_answer_candidate(
        prompt=slots.query,
        slots=slots,
        evidence_bus={},
        llm_answer="Journey A appears in the available evidence.",
        llm_verification={"ok": True, "unsupported_claims": []},
        legacy_answer="Journey A has status inactive in the local snapshot.",
        grounded_answer="Results: Journey A.",
    )

    assert selected.selected_source == "LEGACY_SAFE_RENDERER"
    assert "STATUS_COVERAGE_ADVANTAGE" in selected.selection_codes


def test_selector_keeps_llm_when_facts_are_equivalent() -> None:
    slots = _slots(
        "List campaign names.",
        entity_names=["Birthday Message", "Welcome Journey"],
        first_rows=[{"name": "Birthday Message"}, {"name": "Welcome Journey"}],
    )

    selected = select_answer_candidate(
        prompt=slots.query,
        slots=slots,
        evidence_bus={},
        llm_answer="The matching campaigns are Birthday Message and Welcome Journey.",
        llm_verification={"ok": True, "unsupported_claims": []},
        legacy_answer="Based on the SQL evidence, the matching item(s) are: Birthday Message, Welcome Journey.",
        grounded_answer="Results: Birthday Message; Welcome Journey.",
    )

    assert selected.selected_source == "LLM_EVIDENCE_GROUNDED"
    assert selected.unsupported_claims == 0


def test_selector_prefers_legacy_over_generic_count_when_coverage_ties() -> None:
    slots = _slots(
        "How many schemas do I have?",
        counts=[74],
        sql_row_count=1,
        api_evidence_state="live_empty",
    )

    selected = select_answer_candidate(
        prompt=slots.query,
        slots=slots,
        evidence_bus={},
        llm_answer="Count: 74.",
        llm_verification={"ok": True, "unsupported_claims": []},
        legacy_answer="You have 74 schemas from the available SQL evidence.",
        grounded_answer="Count: 74.",
    )

    assert selected.selected_source == "LEGACY_SAFE_RENDERER"
    assert selected.selected_answer.startswith("You have 74")


def test_selector_prefers_legacy_over_generic_braced_results_when_coverage_ties() -> None:
    slots = _slots(
        "List all audiences mapped to destinations.",
        entity_names=["Gender: Male", "amazon-s3"],
        entity_ids=["aud-1"],
        first_rows=[{"id": "aud-1", "name": "Gender: Male", "target_name": "amazon-s3"}],
    )

    selected = select_answer_candidate(
        prompt=slots.query,
        slots=slots,
        evidence_bus={},
        llm_answer="Results: {id=aud-1, name=Gender: Male}.",
        llm_verification={"ok": True, "unsupported_claims": []},
        legacy_answer="Based on the SQL evidence, Gender: Male (ID aud-1) mapped to amazon-s3.",
        grounded_answer="Results: {id=aud-1, name=Gender: Male}.",
    )

    assert selected.selected_source == "LEGACY_SAFE_RENDERER"
    assert "mapped to amazon-s3" in selected.selected_answer


def test_selector_prefers_no_result_legacy_over_count_zero_caveat() -> None:
    slots = _slots(
        "Show me all entities created by download",
        answer_family="audit_entity_created",
        counts=[0],
        sql_row_count=0,
        api_evidence_state="live_empty",
    )

    selected = select_answer_candidate(
        prompt=slots.query,
        slots=slots,
        evidence_bus={},
        llm_answer="The local snapshot has no matching rows. API returned no matching records for this query/scope.",
        llm_verification={"ok": True, "unsupported_claims": []},
        legacy_answer="Based on the evidence provided, no entities were created by download. The SQL query returned zero rows, and the API returned usable supporting evidence.",
        grounded_answer="The local snapshot has no matching rows. API returned no matching records for this query/scope.",
    )

    assert selected.selected_source == "LEGACY_SAFE_RENDERER"
    assert "no entities were created by download" in selected.selected_answer


def test_selector_prefers_default_detail_legacy_over_braced_duplicate_items() -> None:
    slots = _slots(
        "Show the default merge policy for schema class '_xdm.context.profile'.",
        answer_family="merge_policy",
        entity_names=["Default Timebased"],
        entity_ids=["policy-1", "policy-2"],
        api_items=[
            {"id": "policy-1", "name": "Default Timebased"},
            {"id": "policy-2", "name": "Default Timebased"},
        ],
    )

    selected = select_answer_candidate(
        prompt=slots.query,
        slots=slots,
        evidence_bus={},
        llm_answer="Results: {id=policy-1, name=Default Timebased}; {id=policy-2, name=Default Timebased}.",
        llm_verification={"ok": True, "unsupported_claims": []},
        legacy_answer="The default merge policy is Default Timebased. This is based on live merge-policy API evidence.",
        grounded_answer="Results: {id=policy-1, name=Default Timebased}; {id=policy-2, name=Default Timebased}.",
    )

    assert selected.selected_source == "LEGACY_SAFE_RENDERER"
    assert selected.selected_answer.startswith("The default merge policy")


def test_selector_prefers_legacy_over_raw_epoch_date_fallback() -> None:
    slots = _slots(
        "List the most recently created batches.",
        answer_family="batch",
        entity_ids=["01KSN0EJVFZF57PH3FVPPHX9TH"],
        statuses=["success"],
        timestamps=["1779895323686", "1779895999276"],
        api_items=[{"id": "01KSN0EJVFZF57PH3FVPPHX9TH", "status": "success"}],
        evidence_strings={"01ksn0ejvfzf57ph3fvpphx9th", "success"},
    )

    selected = select_answer_candidate(
        prompt=slots.query,
        slots=slots,
        evidence_bus={},
        llm_answer="Date/time: 1779895323686, 1779895999276.",
        llm_verification={"ok": False, "unsupported_claims": [{"text": "1779895323686"}]},
        legacy_answer="The API evidence reports batch 01KSN0EJVFZF57PH3FVPPHX9TH with status/state success.",
        grounded_answer="Date/time: 1779895323686, 1779895999276.",
    )

    assert selected.selected_source == "LEGACY_SAFE_RENDERER"
    assert "status/state success" in selected.selected_answer


def test_selector_rejects_unsupported_llm_claim() -> None:
    slots = _slots(
        "How many schema records are in the local snapshot?",
        counts=[3],
        sql_row_count=3,
    )

    selected = select_answer_candidate(
        prompt=slots.query,
        slots=slots,
        evidence_bus={},
        llm_answer="There are 9 schema records.",
        llm_verification={"ok": False, "unsupported_claims": [{"text": "9"}]},
        legacy_answer="The local snapshot has 3 schema records.",
        grounded_answer="Count: 3.",
    )

    assert selected.selected_source == "LEGACY_SAFE_RENDERER"
    assert selected.unsupported_claims == 0
    assert "SELECT_LEGACY_LLM_UNSUPPORTED" in selected.selection_codes


def test_selector_selects_llm_when_it_has_better_runtime_coverage() -> None:
    slots = _slots(
        "How many schema records are in the local snapshot?",
        counts=[74],
        sql_row_count=74,
    )

    selected = select_answer_candidate(
        prompt=slots.query,
        slots=slots,
        evidence_bus={},
        llm_answer="The local snapshot contains 74 schema records.",
        llm_verification={"ok": True, "unsupported_claims": []},
        legacy_answer="Schema records are available in the local snapshot.",
        grounded_answer="Count: 74.",
    )

    assert selected.selected_source == "LLM_EVIDENCE_GROUNDED"
    assert "SELECT_LLM_BETTER_COVERAGE" in selected.selection_codes


def test_selector_selects_llm_when_equal_coverage_has_better_shape() -> None:
    slots = _slots(
        "List campaign names.",
        entity_names=["Birthday Message", "Welcome Journey"],
        first_rows=[{"name": "Birthday Message"}, {"name": "Welcome Journey"}],
    )

    selected = select_answer_candidate(
        prompt=slots.query,
        slots=slots,
        evidence_bus={},
        llm_answer="The matching campaigns are Birthday Message and Welcome Journey.",
        llm_verification={"ok": True, "unsupported_claims": []},
        legacy_answer="Results: {name=Birthday Message}; {name=Welcome Journey}.",
        grounded_answer="Results: {name=Birthday Message}; {name=Welcome Journey}.",
    )

    assert selected.selected_source == "LLM_EVIDENCE_GROUNDED"
    assert "SELECT_LLM_EQUAL_COVERAGE_BETTER_SHAPE" in selected.selection_codes


def test_selector_marks_llm_omitted_runtime_role() -> None:
    slots = _slots(
        "What is the status of Journey A?",
        entity_names=["Journey A"],
        statuses=["inactive"],
    )

    selected = select_answer_candidate(
        prompt=slots.query,
        slots=slots,
        evidence_bus={},
        llm_answer="Journey A appears in the evidence.",
        llm_verification={"ok": True, "unsupported_claims": []},
        legacy_answer="Journey A has status inactive.",
        grounded_answer="Results: Journey A.",
    )

    assert selected.selected_source == "LEGACY_SAFE_RENDERER"
    assert "SELECT_LEGACY_LLM_OMITS_ROLE" in selected.selection_codes


def test_selector_marks_empty_llm_answer() -> None:
    slots = _slots(
        "List campaign names.",
        entity_names=["Birthday Message"],
    )

    selected = select_answer_candidate(
        prompt=slots.query,
        slots=slots,
        evidence_bus={},
        llm_answer=" ",
        llm_verification={"ok": True, "unsupported_claims": []},
        legacy_answer="Birthday Message.",
        grounded_answer="Results: Birthday Message.",
    )

    assert selected.selected_source == "LEGACY_SAFE_RENDERER"
    assert "SELECT_LEGACY_LLM_EMPTY" in selected.selection_codes


def test_selector_prefers_local_scope_caveat_for_live_count_when_api_unavailable() -> None:
    slots = _slots(
        "How many current schemas are in Adobe Experience Platform?",
        counts=[74],
        sql_row_count=74,
        dry_run=True,
    )

    selected = select_answer_candidate(
        prompt=slots.query,
        slots=slots,
        evidence_bus={},
        llm_answer="You have 74 schemas. Live API verification was not executed because Adobe credentials are unavailable.",
        llm_verification={"ok": True, "unsupported_claims": []},
        legacy_answer="You have 74 schemas. Live API verification was not executed because Adobe credentials are unavailable.",
        grounded_answer="Local snapshot count: 74. Live API verification was not executed because Adobe credentials are unavailable.",
    )

    assert selected.selected_source == "DETERMINISTIC_FALLBACK"
    assert "local snapshot" in selected.selected_answer.lower()
    assert "LIVE_SCOPE_CAVEAT_COVERED" in selected.selection_codes


def test_selector_prefers_actual_count_over_sql_row_count() -> None:
    slots = _slots(
        "How many schemas do I have?",
        counts=[74],
        sql_row_count=1,
    )

    selected = select_answer_candidate(
        prompt=slots.query,
        slots=slots,
        evidence_bus={},
        llm_answer="Count: 1.",
        llm_verification={"ok": True, "unsupported_claims": []},
        legacy_answer="You have 74 schemas.",
        grounded_answer="Count: 1.",
    )

    assert selected.selected_source == "LEGACY_SAFE_RENDERER"


def test_selector_does_not_reward_live_empty_zero_as_no_result_for_positive_count() -> None:
    slots = _slots(
        "How many schemas do I have?",
        counts=[74, 0],
        sql_row_count=1,
        api_evidence_state="live_empty",
    )

    selected = select_answer_candidate(
        prompt=slots.query,
        slots=slots,
        evidence_bus={},
        llm_answer="Count: 74. No matching records were returned for this query globally.",
        llm_verification={"ok": True, "unsupported_claims": []},
        legacy_answer="You have 74 schemas from the available SQL evidence.",
        grounded_answer="Count: 74.",
    )

    assert selected.selected_source == "LEGACY_SAFE_RENDERER"
    llm_candidate = next(candidate for candidate in selected.candidates if candidate["source"] == "LLM_EVIDENCE_GROUNDED")
    assert "no_result" not in llm_candidate["covered_roles"]
    assert "no_result" not in llm_candidate["missing_roles"]
    assert "74" in selected.selected_answer


def test_selector_prefers_status_filter_answer_over_unfiltered_ids() -> None:
    slots = _slots(
        "Show me the IDs of failed dataflow runs",
        entity_ids=["flow-1", "flow-2"],
        entity_names=["Flow 1", "Flow 2"],
        statuses=["enabled"],
        first_rows=[],
        api_items=[{"id": "flow-1", "name": "Flow 1", "status": "enabled"}],
    )

    selected = select_answer_candidate(
        prompt=slots.query,
        slots=slots,
        evidence_bus={},
        llm_answer="Status: {id=flow-1, name=Flow 1, status=enabled}.",
        llm_verification={"ok": True, "unsupported_claims": []},
        legacy_answer="There are no failed dataflow runs to report.",
        grounded_answer="Status: {id=flow-1, name=Flow 1, status=enabled}.",
    )

    assert selected.selected_source == "LEGACY_SAFE_RENDERER"
    assert "no failed" in selected.selected_answer.lower()


def test_selector_prefers_observability_metric_values_over_generic_count() -> None:
    slots = _slots(
        "Show ingestion record counts and batch success counts for the last 90 days.",
        answer_family="observability_metrics",
        counts=[1],
        metrics=[
            "timeseries.ingestion.dataset.recordsuccess.count",
            "timeseries.ingestion.dataset.batchsuccess.count",
        ],
        timestamps=["2026-03-29T00:00:00Z", "2026-03-30T00:00:00Z"],
        evidence_strings={
            "timeseries.ingestion.dataset.recordsuccess.count",
            "timeseries.ingestion.dataset.batchsuccess.count",
            "2026-03-29t00:00:00z",
            "152120.0",
            "24.0",
        },
        evidence_numbers={"1", "152120.0", "24.0"},
    )

    selected = select_answer_candidate(
        prompt=slots.query,
        slots=slots,
        evidence_bus={},
        llm_answer="Count: 1.",
        llm_verification={"ok": True, "unsupported_claims": []},
        legacy_answer=(
            "Based on live observability API evidence, "
            "timeseries.ingestion.dataset.recordsuccess.count and "
            "timeseries.ingestion.dataset.batchsuccess.count values include: "
            "2026-03-29 timeseries.ingestion.dataset.recordsuccess.count: 152120.0 "
            "and 2026-03-29 timeseries.ingestion.dataset.batchsuccess.count: 24.0."
        ),
        grounded_answer="Count: 1.",
    )

    assert selected.selected_source == "LEGACY_SAFE_RENDERER"
    assert "recordsuccess.count" in selected.selected_answer
    assert "152120.0" in selected.selected_answer


def test_selector_prefers_large_list_total_context_over_truncated_rows() -> None:
    slots = _slots(
        "List all segment evaluation jobs.",
        answer_family="segment_jobs",
        api_item_count=59,
        entity_ids=["job-1", "job-2", "job-3"],
        statuses=["SUCCEEDED"],
        api_items=[
            {"id": "job-1", "status": "SUCCEEDED"},
            {"id": "job-2", "status": "SUCCEEDED"},
            {"id": "job-3", "status": "SUCCEEDED"},
        ],
    )

    selected = select_answer_candidate(
        prompt=slots.query,
        slots=slots,
        evidence_bus={},
        llm_answer="Results: {id=job-1, status=SUCCEEDED}; {id=job-2, status=SUCCEEDED}; {id=job-3, status=SUCCEEDED}.",
        llm_verification={"ok": True, "unsupported_claims": []},
        legacy_answer="The API evidence reports 59 segment evaluation job(s) with status SUCCEEDED, ID job-1.",
        grounded_answer="Results: {id=job-1, status=SUCCEEDED}; {id=job-2, status=SUCCEEDED}; {id=job-3, status=SUCCEEDED}.",
    )

    assert selected.selected_source == "LEGACY_SAFE_RENDERER"
    assert "59" in selected.selected_answer


def test_selector_does_not_accept_gold_or_category_inputs() -> None:
    slots = _slots("List campaigns.", entity_names=["Birthday Message"])

    selected = select_answer_candidate(
        prompt=slots.query,
        slots=slots,
        evidence_bus={"names": ["Birthday Message"]},
        llm_answer="Birthday Message is available.",
        llm_verification={"ok": True, "unsupported_claims": []},
        legacy_answer="Birthday Message.",
        grounded_answer="Birthday Message.",
    )

    payload = selected.to_dict()
    assert "gold" not in str(payload).lower()
    assert "category" not in str(payload).lower()
