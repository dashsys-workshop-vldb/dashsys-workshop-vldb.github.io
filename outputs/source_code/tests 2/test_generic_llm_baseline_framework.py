from __future__ import annotations

import json
from pathlib import Path

from dashagent.llm_tool_agent import _llm_token_accounting
from scripts.run_llm_strict_baseline_eval import canonical_trajectory_from_row


def test_generic_llm_scripts_exist():
    for path in [
        Path("scripts/check_llm_sdk_backend.py"),
        Path("scripts/run_llm_baseline_eval.py"),
        Path("scripts/run_llm_strict_baseline_eval.py"),
        Path("scripts/run_llm_hidden_style_diagnostic.py"),
    ]:
        assert path.exists()


def test_token_accounting_prefers_measured_usage():
    result = _llm_token_accounting(
        [{"usage": {"total_tokens": 12}, "usage_total_tokens": 12}],
        fallback_payload={"large": "fallback text"},
    )

    assert result == {"llm_total_tokens": 12, "token_source": "measured_usage"}


def test_token_accounting_estimates_when_usage_missing():
    result = _llm_token_accounting(
        [{"usage": {}, "usage_total_tokens": None}],
        fallback_payload={"query": "How many schemas do I have?", "answer": "You have 74 schemas."},
    )

    assert result["token_source"] == "estimated"
    assert isinstance(result["llm_total_tokens"], int)
    assert result["llm_total_tokens"] > 0


def test_strict_baseline_canonical_trajectory_preserves_tool_calls_and_token_source():
    row = {
        "query_id": "example_011",
        "query": "How many schemas do I have?",
        "system": "RAW_REAL_LLM_TWO_TOOLS_BASELINE",
        "final_answer": "You have 74 schemas.",
        "tool_call_count": 1,
        "llm_total_tokens": 42,
        "token_source": "measured_usage",
        "llm_tool_calls": [
            {
                "tool": "execute_sql",
                "arguments": {"sql": 'SELECT COUNT(DISTINCT B."BLUEPRINTID") AS blueprint_count FROM "dim_blueprint" AS B'},
                "validation": {"ok": True},
                "result_preview": {"ok": True, "rows_preview": [{"blueprint_count": 74}]},
            }
        ],
    }

    trajectory = canonical_trajectory_from_row(row, row["system"])

    assert trajectory["steps"][0]["kind"] == "sql_call"
    assert trajectory["steps"][0]["sql"].startswith("SELECT COUNT")
    assert trajectory["llm_total_tokens"] == 42
    assert trajectory["token_source"] == "measured_usage"
    assert "qwen baseline" not in json.dumps(trajectory).lower()
