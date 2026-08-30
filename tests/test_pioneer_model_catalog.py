from __future__ import annotations

import json

from dashagent.pioneer_model_catalog import (
    desired_pioneer_model_mapping_names,
    extract_catalog_records,
    suggest_pioneer_model_id_map,
    write_pioneer_model_catalog_reports,
)


def test_discover_pioneer_models_parses_native_base_models_response(tmp_path) -> None:
    payload = {
        "base_models": [
            {
                "id": "qwen3-4b-instruct-2507",
                "display_name": "Qwen3 4B Instruct 2507",
                "provider": "Qwen",
                "supports_inference": True,
                "task_type": "decoder",
                "context_window": 32768,
                "input_price": 0.1,
                "output_price": 0.2,
            }
        ]
    }

    records = extract_catalog_records(payload, source="base_models_decoder")

    assert records == [
        {
            "id": "qwen3-4b-instruct-2507",
            "model_id": "qwen3-4b-instruct-2507",
            "name": "",
            "display_name": "Qwen3 4B Instruct 2507",
            "slug": "",
            "provider": "Qwen",
            "supports_inference": True,
            "task_type": "decoder",
            "context_window": 32768,
            "input_price": 0.1,
            "output_price": 0.2,
            "source": "base_models_decoder",
            "raw": payload["base_models"][0],
        }
    ]


def test_discover_pioneer_models_parses_openai_models_response() -> None:
    payload = {
        "object": "list",
        "data": [
            {"id": "mistral-nemo-instruct-2407", "object": "model", "owned_by": "mistral"},
        ],
    }

    records = extract_catalog_records(payload, source="v1_models_x_api_key")

    assert records[0]["model_id"] == "mistral-nemo-instruct-2407"
    assert records[0]["provider"] == "mistral"
    assert records[0]["source"] == "v1_models_x_api_key"


def test_mapping_suggestion_keeps_display_name_separate_from_actual_model_id() -> None:
    records = [
        {
            "model_id": "anthropic/claude-haiku-4-5",
            "display_name": "Claude Haiku 4.5",
            "provider": "Anthropic",
            "source": "unit",
        }
    ]

    suggestion = suggest_pioneer_model_id_map(["Claude Haiku 4.5"], records)

    assert suggestion["mapping"] == {"Claude Haiku 4.5": "anthropic/claude-haiku-4-5"}
    match = suggestion["matches"]["Claude Haiku 4.5"]
    assert match["display_name"] == "Claude Haiku 4.5"
    assert match["model_id"] == "anthropic/claude-haiku-4-5"
    assert match["confidence"] >= 0.99


def test_discovery_desired_names_exclude_gpt4_family_and_prioritize_qwen() -> None:
    desired = desired_pioneer_model_mapping_names()

    assert desired[0] == "Qwen3 4B Instruct 2507"
    assert "Gpt 4o" not in desired
    assert "Gpt 4o Mini" not in desired
    assert "Gpt 4.1 Mini" not in desired
    assert not [name for name in desired if name.lower().startswith(("gpt 4", "gpt-4"))]


def test_low_confidence_mapping_is_not_silently_used() -> None:
    records = [
        {
            "model_id": "frontier-max-pro",
            "display_name": "Frontier Max Pro",
            "provider": "Other",
            "source": "unit",
        }
    ]

    suggestion = suggest_pioneer_model_id_map(["Gemma 4 E4B It"], records)

    assert suggestion["mapping"] == {}
    assert suggestion["unmapped"] == ["Gemma 4 E4B It"]
    assert suggestion["matches"]["Gemma 4 E4B It"]["model_id"] is None


def test_catalog_report_generation_writes_mapping_file(tmp_path) -> None:
    endpoint_results = [
        {
            "name": "native_decoder",
            "url": "https://api.pioneer.ai/base-models?supports_inference=true&task_type=decoder",
            "ok": True,
            "status": 200,
            "payload": {"base_models": [{"id": "gpt-4o", "display_name": "Gpt 4o", "supports_inference": True}]},
        }
    ]
    records = extract_catalog_records(endpoint_results[0]["payload"], source="native_decoder")
    suggestion = suggest_pioneer_model_id_map(["Gpt 4o"], records)

    paths = write_pioneer_model_catalog_reports(tmp_path, endpoint_results, records, suggestion)

    assert paths["catalog_json"].exists()
    assert paths["catalog_md"].exists()
    assert paths["mapping_json"].exists()
    mapping_payload = json.loads(paths["mapping_json"].read_text(encoding="utf-8"))
    assert mapping_payload["mapping"] == {"Gpt 4o": "gpt-4o"}
