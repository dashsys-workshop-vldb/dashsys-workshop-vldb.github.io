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
    is_gpt4_family_model,
    parse_pioneer_model_sweep,
    run_pioneer_model_sweep,
    safe_model_name,
    write_pioneer_model_sweep_reports,
)
from dashagent.pre_evidence_routing_boundary import should_bypass_evidence_for_llm_direct


def test_default_pioneer_model_sweep_is_exact_selected_set() -> None:
    assert DEFAULT_PIONEER_MODEL_SWEEP == [
        "Qwen3 4B Instruct 2507",
        "Qwen3 8B",
        "Qwen3.5 9B",
        "Qwen3.6 27B",
        "Qwen3.6 Flash",
        "Qwen3.6 Plus",
        "Qwen3.6 35B A3B",
        "Qwen3.7 Max",
        "Claude Haiku 4.5",
        "DeepSeek V4 Flash",
        "DeepSeek V4 Pro",
        "Llama 3.1 8B Instruct",
        "Llama 3.2 3B Instruct",
        "Mistral Nemo Instruct 2407",
        "Gemma 4 E4B It",
        "Gemma 4 31B It",
        "MiniMax M2.7",
        "Kimi K2.6",
        "GLM 5.1",
        "GPT-OSS 20B",
        "GPT-OSS 120B",
    ]
    assert DEFAULT_PIONEER_MODEL_GROUPS["Qwen3 4B Instruct 2507"].startswith("qwen")
    assert DEFAULT_PIONEER_MODEL_GROUPS["Claude Haiku 4.5"] == "anthropic_fast_small"
    assert DEFAULT_PIONEER_MODEL_GROUPS["GPT-OSS 20B"] == "gpt_oss"


def test_default_pioneer_model_sweep_excludes_gpt4_family() -> None:
    assert not any(is_gpt4_family_model(model) for model in DEFAULT_PIONEER_MODEL_SWEEP)
    assert "Gpt 4o" not in DEFAULT_PIONEER_MODEL_SWEEP
    assert "Gpt 4o Mini" not in DEFAULT_PIONEER_MODEL_SWEEP
    assert "Gpt 4.1 Mini" not in DEFAULT_PIONEER_MODEL_SWEEP


def test_focused_sweep_contains_seven_requested_prompts() -> None:
    assert len(PIONEER_SWEEP_PROMPTS) == 7
    assert PIONEER_SWEEP_PROMPTS[-1]["id"] == "compare_local_live_birthday_status"


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


def test_semantic_probe_non_object_json_fails_closed(monkeypatch) -> None:
    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def available(self):
            return True

        def complete_json(self, *args, **kwargs):
            return 7

    monkeypatch.setattr(sweep, "PioneerChatLLMClient", FakeClient)

    result = sweep._semantic_json_probe("weak-model", "What schemas do I have?")

    assert result["parse_error"] is True
    assert result["route"] == "EVIDENCE_PIPELINE"
    assert result["requires_evidence"] is True


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


def test_sweep_uses_actual_model_id_when_mapping_exists(monkeypatch, tmp_path) -> None:
    call_order: list[tuple[str, str]] = []

    class FakeExecutor:
        def __init__(self, config):
            self.model_at_init = sweep.os.getenv("PIONEER_MODEL")
            self.model_id_at_init = sweep.os.getenv("PIONEER_MODEL_ID")

        def run(self, prompt, *, strategy, query_id, output_dir):
            call_order.append((sweep.os.getenv("PIONEER_MODEL") or "", sweep.os.getenv("PIONEER_MODEL_ID") or "", prompt))
            assert sweep.os.getenv("PIONEER_MODEL") == "ModelA"
            assert sweep.os.getenv("PIONEER_MODEL_ID") == "actual-model-a"
            return _fake_evidence_result(output_dir)

    monkeypatch.setenv("PIONEER_MODEL_ID_MAP_JSON", '{"ModelA":"actual-model-a"}')
    monkeypatch.setattr(sweep, "PIONEER_SWEEP_PROMPTS", [{"id": "prompt1", "prompt": "prompt1", "expected_kind": "EVIDENCE"}])
    monkeypatch.setattr(sweep, "AgentExecutor", FakeExecutor)
    monkeypatch.setattr(sweep, "_availability_probe", lambda model: {"available": True, "model": model})
    monkeypatch.setattr(
        sweep,
        "_semantic_json_probe",
        lambda model, prompt: {
            "model": model,
            "pioneer_model": "ModelA",
            "pioneer_model_id": model,
            "model_sweep_run_id": "modela",
            "prompt": prompt,
            "parse_error": False,
        },
    )

    result = run_pioneer_model_sweep(SimpleNamespace(outputs_dir=tmp_path), models=["ModelA"], report_dir=tmp_path)

    assert call_order == [("ModelA", "actual-model-a", "prompt1")]
    model_result = result["models"][0]
    assert model_result["model"] == "ModelA"
    assert model_result["pioneer_model"] == "ModelA"
    assert model_result["pioneer_model_id"] == "actual-model-a"
    assert model_result["prompt_results"][0]["pioneer_model_id"] == "actual-model-a"


def test_missing_mapping_marks_model_unavailable_without_crashing(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("PIONEER_MODEL_ID_MAP_JSON", raising=False)
    monkeypatch.setattr(sweep, "_availability_probe", lambda model: {"available": False, "model": model, "error_category": "model_not_found"})

    result = run_pioneer_model_sweep(SimpleNamespace(outputs_dir=tmp_path), models=["Unmapped Display"], report_dir=tmp_path)

    model_result = result["models"][0]
    assert model_result["model"] == "Unmapped Display"
    assert model_result["pioneer_model_id"] == "Unmapped Display"
    assert model_result["availability"]["available"] is False
    assert model_result["prompt_results"] == []


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
