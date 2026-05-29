from __future__ import annotations

import json
from types import SimpleNamespace

from dashagent.llm_client import PioneerChatLLMClient
import dashagent.pioneer_model_sweep as sweep
from dashagent.pioneer_model_sweep import (
    DEFAULT_PIONEER_MODEL_GROUPS,
    DEFAULT_PIONEER_MODEL_SWEEP,
    EXCLUDED_DEFAULT_PIONEER_MODELS,
    PIONEER_SWEEP_PROMPTS,
    parse_pioneer_model_sweep,
    run_pioneer_model_sweep,
    safe_model_name,
    write_pioneer_model_sweep_reports,
)
from dashagent.pre_evidence_routing_boundary import should_bypass_evidence_for_llm_direct


def test_default_pioneer_model_sweep_is_exact_selected_set() -> None:
    assert DEFAULT_PIONEER_MODEL_SWEEP == [
        "Gpt 4o",
        "Claude Haiku 4.5",
        "DeepSeek V4 Flash",
        "Qwen3 4B Instruct 2507",
        "Llama 3.1 8B Instruct",
        "Mistral Nemo Instruct 2407",
        "Gemma 4 E4B It",
    ]
    assert DEFAULT_PIONEER_MODEL_GROUPS == {
        "Gpt 4o": "gpt_baseline",
        "Claude Haiku 4.5": "anthropic_fast_small",
        "DeepSeek V4 Flash": "deepseek_cheap_fast",
        "Qwen3 4B Instruct 2507": "qwen_small_instruct",
        "Llama 3.1 8B Instruct": "llama_small_instruct",
        "Mistral Nemo Instruct 2407": "mistral_compact_instruct",
        "Gemma 4 E4B It": "gemma_small_instruct",
    }


def test_default_pioneer_model_sweep_includes_only_one_gpt_model() -> None:
    gpt_models = [model for model in DEFAULT_PIONEER_MODEL_SWEEP if model.lower().startswith("gpt")]
    assert gpt_models == ["Gpt 4o"]


def test_excluded_gpt_and_frontier_models_are_not_in_default_sweep() -> None:
    assert not set(DEFAULT_PIONEER_MODEL_SWEEP) & EXCLUDED_DEFAULT_PIONEER_MODELS


def test_pioneer_model_sweep_env_override(monkeypatch) -> None:
    monkeypatch.setenv("PIONEER_MODEL_SWEEP", "Model A, Model B,,Model C")
    assert parse_pioneer_model_sweep() == ["Model A", "Model B", "Model C"]


def test_weak_model_malformed_json_falls_back_to_evidence_pipeline(monkeypatch) -> None:
    class FakeCompletion:
        def model_dump(self):
            return {
                "choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": "{bad json"}}],
                "usage": {"total_tokens": 3},
            }

    class FakeCompletions:
        def create(self, **payload):
            return FakeCompletion()

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.chat = type("Chat", (), {"completions": FakeCompletions()})()

    monkeypatch.setattr("dashagent.llm_client.OpenAI", FakeOpenAI)
    client = PioneerChatLLMClient(api_key="unit-test-pioneer-key", model="Qwen3 4B Instruct 2507")

    result = client.complete_json("Classify routing.", "What schemas do I have?")

    assert result["route"] == "EVIDENCE_PIPELINE"
    assert result["requires_evidence"] is True
    assert result["pure_no_evidence"] is False
    assert result["parse_error"] is True


def test_concrete_data_prompt_cannot_bypass_evidence_bus_under_weak_output() -> None:
    weak_payload = {
        "action": "LLM_SAFE_DIRECT",
        "confidence": 0.96,
        "semantic_intent_decision": {"conf": 0.96, "need": "NONE", "no_tool": True},
        "progressive_evidence_policy": {"confidence": "HIGH", "requires_evidence_pipeline": False},
        "semantic_parse": {
            "operation": "LIST",
            "target": {"grounding": "SUPPORTED_DATA_OBJECT", "instance_level": True},
            "evidence_need": "SQL",
            "no_tool_safe": False,
            "confidence": 0.9,
        },
    }

    assert not should_bypass_evidence_for_llm_direct(
        weak_payload,
        strategy="ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2",
        prompt="What schemas do I have?",
    )


def test_report_generation_works_with_fake_metrics(tmp_path) -> None:
    model_result = {
        "model": "Qwen3 4B Instruct 2507",
        "safe_model_name": safe_model_name("Qwen3 4B Instruct 2507"),
        "group": "qwen_small_instruct",
        "availability": {"available": True, "error_category": None},
        "metrics": {
            "json_parse_failures": 1,
            "semantic_fallback_count": 1,
            "llm_direct_count": 2,
            "evidence_pipeline_count": 4,
            "evidence_pipeline_bypassed_count": 2,
            "evidence_bus_built_count": 4,
            "no_tool_fp": 0,
            "api_required_underuse": 0,
            "unsupported_claims": 0,
            "focused_smoke_pass": True,
            "latency_sec": 1.23,
        },
        "prompt_results": [
            {
                "prompt": PIONEER_SWEEP_PROMPTS[0]["prompt"],
                "expected_kind": PIONEER_SWEEP_PROMPTS[0]["expected_kind"],
                "pass": True,
            }
        ],
    }

    paths = write_pioneer_model_sweep_reports(tmp_path, [model_result])

    assert paths["summary_md"].exists()
    assert paths["summary_json"].exists()
    assert (tmp_path / "per_model_qwen3_4b_instruct_2507.json").exists()
    assert (tmp_path / "per_model_qwen3_4b_instruct_2507.log").exists()
    payload = json.loads(paths["summary_json"].read_text(encoding="utf-8"))
    assert payload["model_count"] == 1
    assert payload["models"][0]["model"] == "Qwen3 4B Instruct 2507"


def test_pioneer_model_sweep_is_model_major_not_prompt_major(monkeypatch, tmp_path) -> None:
    prompts = [
        {"id": "prompt1", "prompt": "prompt1", "expected_kind": "EVIDENCE"},
        {"id": "prompt2", "prompt": "prompt2", "expected_kind": "EVIDENCE"},
        {"id": "prompt3", "prompt": "prompt3", "expected_kind": "EVIDENCE"},
    ]
    call_order: list[tuple[str, str]] = []

    class FakeExecutor:
        def __init__(self, config):
            self.model_at_init = sweep.os.getenv("PIONEER_MODEL")

        def run(self, prompt, *, strategy, query_id, output_dir):
            call_order.append((sweep.os.getenv("PIONEER_MODEL") or "", prompt))
            assert sweep.os.getenv("PIONEER_MODEL") == self.model_at_init
            return _fake_evidence_result(output_dir)

    monkeypatch.setattr(sweep, "PIONEER_SWEEP_PROMPTS", prompts)
    monkeypatch.setattr(sweep, "AgentExecutor", FakeExecutor)
    monkeypatch.setattr(sweep, "_availability_probe", lambda model: {"available": True, "model": model})
    monkeypatch.setattr(
        sweep,
        "_semantic_json_probe",
        lambda model, prompt: {
            "model": model,
            "pioneer_model": model,
            "model_sweep_run_id": safe_model_name(model),
            "prompt": prompt,
            "parse_error": False,
            "route": "EVIDENCE_PIPELINE",
            "requires_evidence": True,
        },
    )

    result = run_pioneer_model_sweep(
        SimpleNamespace(outputs_dir=tmp_path),
        models=["ModelA", "ModelB"],
        report_dir=tmp_path,
    )

    assert call_order == [
        ("ModelA", "prompt1"),
        ("ModelA", "prompt2"),
        ("ModelA", "prompt3"),
        ("ModelB", "prompt1"),
        ("ModelB", "prompt2"),
        ("ModelB", "prompt3"),
    ]
    for model_result in result["models"]:
        assert model_result["pioneer_model"] == model_result["model"]
        assert model_result["model_sweep_run_id"] == safe_model_name(model_result["model"])
        assert {row["pioneer_model"] for row in model_result["prompt_results"]} == {model_result["model"]}


def test_per_model_report_contains_exactly_one_active_model(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        sweep,
        "PIONEER_SWEEP_PROMPTS",
        [
            {"id": "prompt1", "prompt": "prompt1", "expected_kind": "EVIDENCE"},
            {"id": "prompt2", "prompt": "prompt2", "expected_kind": "EVIDENCE"},
        ],
    )
    monkeypatch.setattr(sweep, "AgentExecutor", lambda config: _FakeExecutor())
    monkeypatch.setattr(sweep, "_availability_probe", lambda model: {"available": True, "model": model})
    monkeypatch.setattr(
        sweep,
        "_semantic_json_probe",
        lambda model, prompt: {
            "model": model,
            "pioneer_model": model,
            "model_sweep_run_id": safe_model_name(model),
            "prompt": prompt,
            "parse_error": False,
        },
    )

    run_pioneer_model_sweep(SimpleNamespace(outputs_dir=tmp_path), models=["ModelA", "ModelB"], report_dir=tmp_path)

    for model in ("ModelA", "ModelB"):
        payload = json.loads((tmp_path / f"per_model_{safe_model_name(model)}.json").read_text(encoding="utf-8"))
        model_names = {payload["pioneer_model"], payload["model"]}
        model_names.update(row["pioneer_model"] for row in payload["prompt_results"])
        model_names.update(row["pioneer_model"] for row in payload["semantic_probe_results"])
        assert model_names == {model}


def test_env_sweep_override_does_not_mix_models_inside_per_model_result(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PIONEER_MODEL_SWEEP", "ModelA,ModelB")
    monkeypatch.setattr(
        sweep,
        "PIONEER_SWEEP_PROMPTS",
        [
            {"id": "prompt1", "prompt": "prompt1", "expected_kind": "EVIDENCE"},
            {"id": "prompt2", "prompt": "prompt2", "expected_kind": "EVIDENCE"},
        ],
    )
    monkeypatch.setattr(sweep, "AgentExecutor", lambda config: _FakeExecutor())
    monkeypatch.setattr(sweep, "_availability_probe", lambda model: {"available": True, "model": model})
    monkeypatch.setattr(
        sweep,
        "_semantic_json_probe",
        lambda model, prompt: {
            "model": model,
            "pioneer_model": model,
            "model_sweep_run_id": safe_model_name(model),
            "prompt": prompt,
            "parse_error": False,
        },
    )

    result = run_pioneer_model_sweep(SimpleNamespace(outputs_dir=tmp_path), report_dir=tmp_path)

    assert [row["model"] for row in result["models"]] == ["ModelA", "ModelB"]
    for model_result in result["models"]:
        active_models = {row["pioneer_model"] for row in model_result["prompt_results"]}
        active_models.update(row["pioneer_model"] for row in model_result["semantic_probe_results"])
        assert active_models == {model_result["model"]}


class _FakeExecutor:
    def run(self, prompt, *, strategy, query_id, output_dir):
        return _fake_evidence_result(output_dir)


def _fake_evidence_result(output_dir):
    return {
        "final_answer": "ok",
        "output_dir": str(output_dir),
        "tool_results": [{"type": "sql"}],
        "checkpoints": [
            {
                "checkpoint_id": "checkpoint_evidence_pipeline_boundary",
                "output": {
                    "evidence_pipeline_bypassed": False,
                    "evidence_bus_built": True,
                    "post_evidence_answer_router_ran": True,
                },
            },
            {"checkpoint_id": "checkpoint_14_evidence_bus", "output": {}},
            {"checkpoint_id": "checkpoint_broad_question_classifier", "output": {}},
        ],
    }
