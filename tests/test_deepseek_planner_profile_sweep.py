from __future__ import annotations

from scripts.sweep_deepseek_v2_planner_profiles import _profile_summaries, select_best_profile


def test_profile_sweep_selects_profile_with_more_semantic_ir_and_fewer_timeouts() -> None:
    rows = [
        {"profile": "current", "semantic_ir_present": True, "timeout": False, "validation_ok": True, "answer_contract_present": True},
        {"profile": "current", "semantic_ir_present": False, "timeout": True, "validation_ok": False, "answer_contract_present": False},
        {"profile": "deepseek_required_tool", "semantic_ir_present": True, "timeout": False, "validation_ok": True, "answer_contract_present": True},
        {"profile": "deepseek_required_tool", "semantic_ir_present": True, "timeout": False, "validation_ok": True, "answer_contract_present": True},
    ]

    summary = _profile_summaries(rows, ["current", "deepseek_required_tool"])
    selected = select_best_profile(summary)

    assert selected["profile"] == "deepseek_required_tool"
    required = next(item for item in summary if item["profile"] == "deepseek_required_tool")
    assert required["semantic_ir_present_count"] == 2
    assert required["timeout_count"] == 0


def test_profile_sweep_penalizes_raw_text_fallback_when_semantic_ir_ties() -> None:
    rows = [
        {
            "profile": "deepseek_auto_tool",
            "semantic_ir_present": True,
            "timeout": False,
            "validation_ok": True,
            "answer_contract_present": True,
            "raw_text_content_present": True,
        },
        {
            "profile": "deepseek_json_tool",
            "semantic_ir_present": True,
            "timeout": False,
            "validation_ok": True,
            "answer_contract_present": True,
            "raw_text_content_present": False,
        },
    ]

    summary = _profile_summaries(rows, ["deepseek_auto_tool", "deepseek_json_tool"])
    selected = select_best_profile(summary)

    assert selected["profile"] == "deepseek_json_tool"


def test_profile_sweep_does_not_select_all_parse_error_profile() -> None:
    rows = [
        {
            "profile": "deepseek_micro_tools",
            "semantic_ir_present": True,
            "timeout": False,
            "validation_ok": True,
            "answer_contract_present": True,
            "raw_text_content_present": False,
        },
        {
            "profile": "deepseek_json_tool",
            "semantic_ir_present": True,
            "timeout": False,
            "validation_ok": False,
            "answer_contract_present": False,
            "raw_text_content_present": False,
        },
        {
            "profile": "deepseek_json_tool",
            "semantic_ir_present": True,
            "timeout": False,
            "validation_ok": False,
            "answer_contract_present": False,
            "raw_text_content_present": False,
        },
    ]

    summary = _profile_summaries(rows, ["deepseek_micro_tools", "deepseek_json_tool"])
    selected = select_best_profile(summary)

    assert selected["profile"] == "deepseek_micro_tools"
