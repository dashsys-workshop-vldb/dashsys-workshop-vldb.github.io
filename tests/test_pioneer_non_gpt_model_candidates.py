from __future__ import annotations

from dashagent.pioneer_non_gpt_model_candidates import (
    apply_run_results_to_candidates,
    build_non_gpt_model_candidates,
    candidate_model_id_map,
    candidate_model_names,
)


def test_non_gpt_candidate_selection_excludes_gpt4_and_prioritizes_qwen() -> None:
    payload = build_non_gpt_model_candidates(
        [
            _record("Gpt 4o Mini", "gpt-4o-mini"),
            _record("Claude Haiku 4.5", "claude-haiku-4-5"),
            _record("Qwen3.6 Flash", "qwen3.6-flash"),
            _record("Qwen3 8B", "Qwen/Qwen3-8B"),
        ]
    )

    names = candidate_model_names(payload)

    assert set(names[:2]) == {"Qwen3 8B", "Qwen3.6 Flash"}
    assert "Claude Haiku 4.5" in names
    assert not any(name.startswith("Gpt 4") for name in names)
    assert any(row["display_name"] == "Gpt 4o Mini" for row in payload["excluded_models"])


def test_candidate_mapping_keeps_display_name_and_actual_model_id_separate() -> None:
    payload = build_non_gpt_model_candidates([_record("Qwen3.6 Flash", "qwen3.6-flash")])

    assert candidate_model_id_map(payload) == {"Qwen3.6 Flash": "qwen3.6-flash"}


def test_candidate_selection_skips_non_generative_models() -> None:
    payload = build_non_gpt_model_candidates(
        [
            _record("Qwen Embedding", "Qwen/Qwen3-Embedding", task_type="decoder"),
            _record("Llama 3.2 3B Instruct", "meta-llama/Llama-3.2-3B-Instruct"),
        ]
    )

    assert candidate_model_names(payload) == ["Llama 3.2 3B Instruct"]
    assert payload["skipped_models"][0]["reason"] == "non_generative_or_guardrail_model"


def test_candidate_report_records_availability_smoke_and_benchmark_status() -> None:
    payload = build_non_gpt_model_candidates([_record("Qwen3.6 Flash", "qwen3.6-flash")])

    updated = apply_run_results_to_candidates(
        payload,
        [
            {
                "pioneer_model": "Qwen3.6 Flash",
                "pioneer_model_id": "qwen3.6-flash",
                "availability": {"available": True},
                "metrics": {"focused_smoke_pass": True},
                "benchmark_status": "completed",
            }
        ],
    )

    candidate = updated["candidate_models"][0]
    assert candidate["callable"] is True
    assert candidate["smoke_status"] == "passed"
    assert candidate["benchmark_status"] == "completed"


def _record(display_name: str, model_id: str, *, task_type: str = "decoder") -> dict:
    return {
        "display_name": display_name,
        "model_id": model_id,
        "supports_inference": True,
        "task_type": task_type,
        "source": "native_decoder",
    }
