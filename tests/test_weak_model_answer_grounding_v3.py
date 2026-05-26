from __future__ import annotations

from dashagent.weak_model_answer_grounder import ground_weak_model_answer


def test_v3_renders_direct_sql_count_evidence():
    grounded = ground_weak_model_answer(
        "How many journeys are active?",
        model_answer="",
        sql_result={"ok": True, "rows": [{"count": 3}], "row_count": 1, "error": None},
        api_result=None,
        answer_intent="COUNT",
        evidence_need="sql_only",
        grounding_mode="balanced_sql_api_answer_v3",
    )

    assert "3" in grounded["answer"]
    assert grounded["answer_used_sql"] is True
    assert grounded["unsupported_claim_count"] == 0


def test_v3_combines_sql_and_required_api_evidence_without_suppression():
    grounded = ground_weak_model_answer(
        "List live audiences for the Gold segment and verify in the platform.",
        model_answer="",
        sql_result={"ok": True, "rows": [{"SEGMENTID": "seg-1", "NAME": "Gold"}], "row_count": 1, "error": None},
        api_result={
            "ok": True,
            "parsed_evidence": {
                "evidence_state": "live_evidence",
                "ids": ["aud-1"],
                "names": ["Gold Audience"],
                "statuses": ["published"],
            },
        },
        answer_intent="LIST",
        evidence_need="sql_then_api",
        api_endpoint_id="ups_audiences",
        grounding_mode="balanced_sql_api_answer_v3",
    )

    assert "Gold" in grounded["answer"]
    assert "Gold Audience" in grounded["answer"]
    assert grounded["answer_used_sql"] is True
    assert grounded["answer_used_api"] is True


def test_v3_does_not_render_blank_sql_values_as_answer():
    grounded = ground_weak_model_answer(
        "show me the field for Person: Birthday Today 001",
        model_answer="",
        sql_result={"ok": True, "rows": [{"PROPERTYID": "p1", "ALTDISPLAYDESC": ""}], "row_count": 1, "error": None},
        api_result=None,
        answer_intent="DETAIL",
        evidence_need="sql_only",
        grounding_mode="balanced_sql_api_answer_v3",
    )

    assert "returns: ." not in grounded["answer"]
    assert "did not provide a grounded field value" in grounded["answer"]
    assert grounded["unsupported_claim_count"] == 0


def test_v3_renders_field_property_with_prompt_entity():
    grounded = ground_weak_model_answer(
        "show me the field for Person: Birthday Today 001",
        model_answer="",
        sql_result={"ok": True, "rows": [{"PROPERTY": "person.birthDate"}], "row_count": 1, "error": None},
        api_result=None,
        answer_intent="DETAIL",
        evidence_need="sql_only",
        grounding_mode="balanced_sql_api_answer_v3",
    )

    assert "Person: Birthday Today 001" in grounded["answer"]
    assert "person.birthDate" in grounded["answer"]
    assert "birth date property" in grounded["answer"]


def test_v3_api_primary_keeps_api_first_but_retains_sql_context():
    grounded = ground_weak_model_answer(
        "Show the live platform state for the dataset.",
        model_answer="",
        sql_result={"ok": True, "rows": [{"COLLECTIONID": "ds-1", "NAME": "Dataset One"}], "row_count": 1, "error": None},
        api_result={
            "ok": True,
            "parsed_evidence": {
                "evidence_state": "live_evidence",
                "ids": ["ds-live"],
                "names": ["Dataset One"],
            },
        },
        answer_intent="DETAIL",
        evidence_need="api_primary_sql_context",
        api_endpoint_id="catalog_datasets",
        grounding_mode="balanced_sql_api_answer_v3",
    )

    assert grounded["answer"].startswith("The API evidence")
    assert "Dataset One" in grounded["answer"]
    assert grounded["answer_used_sql"] is True
    assert grounded["answer_used_api"] is True


def test_v3_keeps_named_sql_context_when_date_column_is_empty():
    grounded = ground_weak_model_answer(
        "When was the journey 'Birthday Message' published?",
        model_answer="",
        sql_result={"ok": True, "rows": [{"NAME": "Birthday Message", "LASTDEPLOYEDTIME": None}], "row_count": 1, "error": None},
        api_result={"ok": True, "parsed_evidence": {"evidence_state": "live_empty", "live_empty": True}},
        answer_intent="DATE",
        evidence_need="sql_primary_api_verify",
        api_endpoint_id="journey_list",
        grounding_mode="balanced_sql_api_answer_v3",
    )

    assert "Birthday Message" in grounded["answer"]
    assert "no matching records" in grounded["answer"]
    assert grounded["answer_used_sql"] is True
    assert grounded["answer_used_api"] is True


def test_harness_answer_evidence_bullets_render_sql_and_api_without_suppression():
    grounded = ground_weak_model_answer(
        "List live audiences for the Gold segment and verify in the platform.",
        model_answer="",
        sql_result={"ok": True, "rows": [{"SEGMENTID": "seg-1", "NAME": "Gold"}], "row_count": 1, "error": None},
        api_result={
            "ok": True,
            "parsed_evidence": {
                "evidence_state": "live_evidence",
                "ids": ["aud-1"],
                "names": ["Gold Audience"],
                "statuses": ["published"],
            },
        },
        answer_intent="LIST",
        evidence_need="sql_then_api",
        api_endpoint_id="ups_audiences",
        grounding_mode="harness_answer_evidence_bullets",
    )

    assert "- Direct answer:" in grounded["answer"]
    assert "- SQL evidence:" in grounded["answer"]
    assert "- API evidence:" in grounded["answer"]
    assert "Gold" in grounded["answer"]
    assert "Gold Audience" in grounded["answer"]
    assert grounded["answer_used_sql"] is True
    assert grounded["answer_used_api"] is True
    assert grounded["unsupported_claim_count"] == 0


def test_harness_answer_slot_template_is_richer_than_sparse_fallback():
    grounded = ground_weak_model_answer(
        "When was the journey 'Birthday Message' published?",
        model_answer="",
        sql_result={"ok": True, "rows": [{"NAME": "Birthday Message", "LASTDEPLOYEDTIME": "2026-01-03"}], "row_count": 1, "error": None},
        api_result={"ok": True, "parsed_evidence": {"evidence_state": "live_empty", "live_empty": True}},
        answer_intent="DATE",
        evidence_need="sql_primary_api_verify",
        api_endpoint_id="journey_list",
        grounding_mode="harness_answer_slot_template",
    )

    assert "Birthday Message" in grounded["answer"]
    assert "2026-01-03" in grounded["answer"]
    assert "API endpoint journey_list returned no matching records" in grounded["answer"]
    assert "SQL returned no matching records." not in grounded["answer"]
    assert grounded["answer_used_sql"] is True
    assert grounded["answer_used_api"] is True
