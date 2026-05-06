from __future__ import annotations

from dashagent.repair_candidate_selector import select_repair_candidate


def _current_plan() -> dict:
    return {
        "sql": ["SELECT COUNT(*) AS count FROM dim_campaign"],
        "api_calls": [{"method": "GET", "path": "/ajo/journey", "params": {}}],
        "tool_call_count": 2,
        "expected_answer_shape": "count",
    }


def _repaired_plan(**overrides) -> dict:
    plan = {
        "sql": ["SELECT COUNT(*) AS count FROM dim_campaign"],
        "api_calls": [{"method": "GET", "path": "/ajo/journey", "params": {"limit": 50}}],
        "tool_call_count": 2,
        "expected_answer_shape": "count",
        "fusion_agreement": True,
        "endpoint_family_confidence": 0.9,
        "dry_run_only": True,
        "live_api_evidence_available": False,
    }
    plan.update(overrides)
    return plan


def _safety(**overrides) -> dict:
    value = {
        "safe": True,
        "sql_validation": {
            "ok": True,
            "ast_summaries": [
                {
                    "parsed_ok": True,
                    "parse_error": None,
                    "unknown_tables": [],
                    "unknown_columns": [],
                    "destructive_sql_detected": False,
                }
            ],
        },
    }
    value.update(overrides)
    return value


def _schema_vote(**overrides) -> dict:
    value = {"schema_vote_agreement": True}
    value.update(overrides)
    return value


def test_selector_accepts_strictly_safe_report_only_repair():
    result = select_repair_candidate(_current_plan(), _repaired_plan(), _safety(), {}, _schema_vote())

    assert result["selected_plan"] == "repaired"
    assert result["safe_to_select_repaired"] is True
    assert result["packaged_execution_changed"] is False
    assert result["diagnostic_only"] is True


def test_selector_rejects_no_op_and_keeps_current():
    current = _current_plan()
    repaired = {**current, "fusion_agreement": True, "endpoint_family_confidence": 0.9, "dry_run_only": True, "live_api_evidence_available": False}

    result = select_repair_candidate(current, repaired, _safety(), {}, _schema_vote())

    assert result["selected_plan"] == "current"
    assert result["no_op"] is True
    assert "no_op_repair" in result["failed_checks"]


def test_selector_rejects_low_confidence_fusion_schema_sql_and_cost_failures():
    result = select_repair_candidate(
        _current_plan(),
        _repaired_plan(
            fusion_agreement=False,
            endpoint_family_confidence=0.84,
            tool_call_count=3,
            expected_answer_shape="list",
        ),
        _safety(
            sql_validation={
                "ok": True,
                "ast_summaries": [{"parsed_ok": False, "parse_error": "bad sql"}],
            }
        ),
        {},
        _schema_vote(schema_vote_agreement=False),
    )

    for check in [
        "fusion_agreement",
        "endpoint_family_confidence",
        "schema_vote_agreement",
        "sql_ast_validation",
        "answer_shape",
        "tool_call_increase",
    ]:
        assert check in result["failed_checks"]
    assert result["safe_to_select_repaired"] is False


def test_selector_rejects_failed_safety_and_dry_run_live_evidence():
    result = select_repair_candidate(
        _current_plan(),
        _repaired_plan(dry_run_only=True, live_api_evidence_available=True),
        _safety(safe=False),
        {},
        _schema_vote(),
    )

    assert "safety_verifier" in result["failed_checks"]
    assert "dry_run_live_evidence" in result["failed_checks"]
