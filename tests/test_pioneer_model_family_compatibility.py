from __future__ import annotations

from dashagent.pioneer_model_family_compatibility import (
    build_model_family_compatibility_matrix,
    select_full_benchmark_models_after_family_smoke,
)


def test_family_matrix_groups_available_models_and_records_capabilities() -> None:
    model_results = [
        {
            "model": "Qwen3 4B Instruct 2507",
            "pioneer_model_id": "Qwen/Qwen3-4B-Instruct-2507",
            "availability": {"available": True},
            "metrics": {
                "json_parse_failures": 2,
                "declared_pass_count": 0,
                "planner_usable_count": 0,
                "evidence_bus_non_empty_count": 0,
                "no_tool_fp": 0,
                "unsupported_claims": 0,
            },
        },
        {
            "model": "Mistral Nemo Instruct 2407",
            "pioneer_model_id": "mistralai/Mistral-Nemo-Instruct-2407",
            "availability": {"available": True},
            "metrics": {
                "json_parse_failures": 0,
                "declared_pass_count": 3,
                "planner_usable_count": 3,
                "evidence_bus_non_empty_count": 3,
                "no_tool_fp": 2,
                "unsupported_claims": 0,
                "latency_sec": 10.0,
            },
        },
    ]
    probes = [
        {
            "display_name": "Qwen3 4B Instruct 2507",
            "model_id": "Qwen/Qwen3-4B-Instruct-2507",
            "toolcall_probe": {"toolcall_supported": False},
            "json_content_probe": {"content_preview": "", "ok": True},
        },
        {
            "display_name": "Mistral Nemo Instruct 2407",
            "model_id": "mistralai/Mistral-Nemo-Instruct-2407",
            "toolcall_probe": {"toolcall_supported": False},
            "json_content_probe": {"content_preview": '{"route":"LLM_DIRECT"}', "ok": True},
        },
    ]

    matrix = build_model_family_compatibility_matrix(model_results=model_results, probe_results=probes)

    assert matrix["families"]["qwen"]["available_model_count"] == 1
    assert matrix["families"]["qwen"]["toolcall_supported"] is False
    assert matrix["families"]["mistral"]["json_content_fallback_works"] is True
    assert matrix["families"]["mistral"]["declared_pass_count"] == 3


def test_full_benchmark_models_require_three_smoke_passing_families() -> None:
    smoke_results = [
        {"model": "Qwen3 8B", "pioneer_model_id": "Qwen/Qwen3-8B", "metrics": {"focused_smoke_pass": True}},
        {"model": "Mistral Nemo Instruct 2407", "pioneer_model_id": "mistralai/Mistral-Nemo-Instruct-2407", "metrics": {"focused_smoke_pass": True}},
        {"model": "Claude Haiku 4.5", "pioneer_model_id": "claude-haiku-4-5", "metrics": {"focused_smoke_pass": False}},
    ]

    decision = select_full_benchmark_models_after_family_smoke(smoke_results, minimum_families=3)

    assert decision["run_full_benchmark"] is False
    assert decision["passing_family_count"] == 2
    assert decision["selected_models"] == []


def test_full_benchmark_models_selected_after_three_family_smoke_success() -> None:
    smoke_results = [
        {"model": "Qwen3 8B", "pioneer_model_id": "Qwen/Qwen3-8B", "metrics": {"focused_smoke_pass": True}},
        {"model": "Mistral Nemo Instruct 2407", "pioneer_model_id": "mistralai/Mistral-Nemo-Instruct-2407", "metrics": {"focused_smoke_pass": True}},
        {"model": "Claude Haiku 4.5", "pioneer_model_id": "claude-haiku-4-5", "metrics": {"focused_smoke_pass": True}},
    ]

    decision = select_full_benchmark_models_after_family_smoke(smoke_results, minimum_families=3)

    assert decision["run_full_benchmark"] is True
    assert decision["passing_families"] == ["claude", "mistral", "qwen"]
    assert decision["selected_models"] == ["Qwen3 8B", "Mistral Nemo Instruct 2407", "Claude Haiku 4.5"]
