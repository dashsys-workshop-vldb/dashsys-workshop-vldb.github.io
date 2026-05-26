from __future__ import annotations

import json

from dashagent.eval_harness import EvalHarness
from scripts.convert_500_prompt_suite_to_organizer_format import convert_suite


def test_500_organizer_conversion_keeps_runtime_prompt_only(tmp_path, tiny_project):
    suite = tmp_path / "suite.jsonl"
    gold = tmp_path / "gold.jsonl"
    suite.write_text(
        json.dumps(
            {
                "prompt_id": "da500_test_0001",
                "prompt": "List schemas",
                "category": "api_only_live_platform",
                "domain_family": "SCHEMA",
                "tags": ["api_required"],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    gold.write_text(
        json.dumps(
            {
                "prompt_id": "da500_test_0001",
                "gold_answer": "Schema Registry returned tenant schemas.",
                "gold_answer_type": "list",
                "expected_evidence_need": "api",
                "expected_tool_calls": {
                    "sql_required": False,
                    "api_required": True,
                    "api_optional": False,
                    "expected_api_families": ["schema_registry_schemas"],
                    "expected_sql_tables": [],
                },
                "expected_observable_trace": [{"stage": "tool_execution", "expected_behavior": "API GET"}],
                "oracle_evidence": {
                    "oracle_sql": None,
                    "oracle_api_endpoint": "schema_registry_schemas",
                    "oracle_source": "live_api",
                },
                "required_facts": ["tenant schemas"],
                "forbidden_claims": ["unsupported count"],
                "grading_rubric": {"correctness_points": ["tenant schemas"]},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    payload = convert_suite(suite, gold)
    example = payload["examples"][0]

    assert example["id"] == "da500_test_0001"
    assert example["query"] == "List schemas"
    assert "category" not in example
    assert "domain_family" not in example
    assert "tags" not in example
    assert "expected_observable_trace" not in example
    assert example["gold_api"][0]["path"] == "/data/foundation/schemaregistry/tenant/schemas"
    assert payload["manifest"]["agent_visible_fields"] == ["id", "query"]

    converted = tmp_path / "converted.json"
    converted.write_text(json.dumps({"examples": payload["examples"]}), encoding="utf-8")
    loaded = EvalHarness(tiny_project).load_examples(converted)
    assert loaded[0].query_id == "da500_test_0001"
    assert loaded[0].query == "List schemas"
    assert loaded[0].gold_api
