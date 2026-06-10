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


def test_unsupported_claim_counter_handles_list_values() -> None:
    checkpoints = [
        {
            "checkpoint_id": "checkpoint_llm_final_answer_semantic_gate",
            "output": {"unsupported_claims": [{"claim": "unsupported"}]},
        }
    ]

    assert sweep._unsupported_claim_count(checkpoints) == 1


def test_prompt_result_splits_initial_and_final_answer_gate_failures() -> None:
    run_result = {
        "final_answer": "repaired ok",
        "tool_results": [{"type": "sql"}],
        "checkpoints": [
            {
                "checkpoint_id": "checkpoint_evidence_pipeline_boundary",
                "output": {"evidence_pipeline_bypassed": False, "evidence_bus_built": True},
            },
            {
                "checkpoint_id": "checkpoint_llm_owned_pass_graph_gate",
                "input_summary": {"llm_pass_count": 1},
                "output": {"pass_count": 1},
            },
            {"checkpoint_id": "checkpoint_result_bundle", "output": {"pass_results_count": 1}},
            {"checkpoint_id": "checkpoint_llm_final_answer_semantic_gate", "output": {"passed": False}},
            {
                "checkpoint_id": "checkpoint_llm_owned_final_answer_boundary",
                "output": {
                    "answer_syntax_gate_passed": True,
                    "answer_semantic_gate_passed": True,
                    "answer_repair_attempts": 1,
                },
            },
        ],
    }

    result = sweep._summarize_prompt_result(
        {"id": "data", "prompt": "What schemas do I have?", "expected_kind": "EVIDENCE"},
        run_result,
        0.1,
    )

    assert result["answer_semantic_gate_initial_failures"] == 1
    assert result["answer_semantic_gate_final_failures"] == 0
    assert result["answer_repair_attempts"] == 1
    assert result["answer_repaired_successes"] == 1
    assert result["pass"] is True


def test_prompt_result_splits_runtime_facts_from_caveat_only_evidence() -> None:
    success_result = {
        "final_answer": "There are 2 schemas.",
        "tool_results": [{"type": "sql"}],
        "checkpoints": [
            {
                "checkpoint_id": "checkpoint_evidence_pipeline_boundary",
                "output": {"evidence_pipeline_bypassed": False, "evidence_bus_built": True},
            },
            {
                "checkpoint_id": "checkpoint_llm_owned_pass_graph_gate",
                "input_summary": {"llm_pass_count": 1},
                "output": {"pass_count": 1},
            },
            {
                "checkpoint_id": "checkpoint_result_bundle",
                "output": {
                    "pass_results_count": 1,
                    "runtime_passes": [
                        {
                            "pass_id": "p1",
                            "status": "SUCCESS",
                            "facts": ["count: 2"],
                            "source_results": [{"status": "SUCCESS"}],
                        }
                    ],
                },
            },
        ],
    }
    caveat_result = {
        "final_answer": "Runtime evidence was unavailable; cannot provide a verified answer.",
        "tool_results": [],
        "checkpoints": [
            {
                "checkpoint_id": "checkpoint_evidence_pipeline_boundary",
                "output": {"evidence_pipeline_bypassed": False, "evidence_bus_built": True},
            },
            {
                "checkpoint_id": "checkpoint_llm_owned_pass_graph_gate",
                "input_summary": {"llm_pass_count": 1},
                "output": {"pass_count": 1},
            },
            {
                "checkpoint_id": "checkpoint_result_bundle",
                "output": {
                    "pass_results_count": 1,
                    "runtime_passes": [
                        {
                            "pass_id": "p1",
                            "status": "API_ERROR",
                            "facts": [],
                            "caveats": ["API_ERROR"],
                            "source_results": [{"status": "ERROR"}],
                        }
                    ],
                },
            },
        ],
    }

    success = sweep._summarize_prompt_result(
        {"id": "success", "prompt": "How many schemas?", "expected_kind": "EVIDENCE"},
        success_result,
        0.1,
    )
    caveat = sweep._summarize_prompt_result(
        {"id": "caveat", "prompt": "How many current schemas?", "expected_kind": "EVIDENCE"},
        caveat_result,
        0.1,
    )
    aggregate = sweep._aggregate_metrics([success, caveat], [], 0.0)

    assert success["evidence_bus_runtime_fact_count"] == 1
    assert success["evidence_bus_runtime_non_empty"] is True
    assert success["evidence_bus_error_or_caveat_only"] is False
    assert success["result_bundle_success_pass_count"] == 1
    assert caveat["evidence_bus_runtime_fact_count"] == 0
    assert caveat["evidence_bus_runtime_non_empty"] is False
    assert caveat["evidence_bus_error_or_caveat_only"] is True
    assert aggregate["evidence_bus_built_count"] == 2
    assert aggregate["evidence_bus_runtime_fact_count"] == 1
    assert aggregate["evidence_bus_runtime_non_empty_count"] == 1
    assert aggregate["evidence_bus_error_or_caveat_only_count"] == 1
    assert aggregate["result_bundle_success_pass_count"] == 1


def test_unrepaired_final_answer_failure_blocks_smoke_prompt() -> None:
    run_result = {
        "final_answer": "fallback",
        "tool_results": [{"type": "sql"}],
        "checkpoints": [
            {
                "checkpoint_id": "checkpoint_evidence_pipeline_boundary",
                "output": {"evidence_pipeline_bypassed": False, "evidence_bus_built": True},
            },
            {
                "checkpoint_id": "checkpoint_llm_owned_pass_graph_gate",
                "input_summary": {"llm_pass_count": 1},
                "output": {"pass_count": 1},
            },
            {"checkpoint_id": "checkpoint_result_bundle", "output": {"pass_results_count": 1}},
            {"checkpoint_id": "checkpoint_llm_final_answer_semantic_gate", "output": {"passed": False}},
            {
                "checkpoint_id": "checkpoint_llm_owned_final_answer_boundary",
                "output": {
                    "answer_syntax_gate_passed": True,
                    "answer_semantic_gate_passed": False,
                    "answer_repair_attempts": 1,
                },
            },
        ],
    }

    result = sweep._summarize_prompt_result(
        {"id": "data", "prompt": "What schemas do I have?", "expected_kind": "EVIDENCE"},
        run_result,
        0.1,
    )

    assert result["answer_semantic_gate_initial_failures"] == 1
    assert result["answer_semantic_gate_final_failures"] == 1
    assert result["pass"] is False


def test_slow_model_route_probe_timeout_prevents_expensive_full_smoke(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(sweep, "SLOW_ROUTE_PROBE_MODELS", {"SlowModel"})
    monkeypatch.setattr(sweep, "_availability_probe", lambda model: {"available": True, "model": model})
    monkeypatch.setattr(
        sweep,
        "_route_gate_short_probe",
        lambda model: {"usable": False, "error_category": "route_gate_timeout", "prompt_results": []},
    )

    class FailingExecutor:
        def __init__(self, config):
            pass

        def run(self, *args, **kwargs):
            raise AssertionError("full smoke should not run when short route probe fails")

    monkeypatch.setattr(sweep, "AgentExecutor", FailingExecutor)

    result = run_pioneer_model_sweep(SimpleNamespace(outputs_dir=tmp_path), models=["SlowModel"], report_dir=tmp_path)

    model_result = result["models"][0]
    assert model_result["route_gate_probe"]["usable"] is False
    assert model_result["metrics"]["focused_smoke_pass"] is False
    assert model_result["model_connection_status"] == "route_timeout"
    assert model_result["prompt_results"] == []


def test_slow_model_route_probe_success_allows_full_smoke(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(sweep, "SLOW_ROUTE_PROBE_MODELS", {"SlowModel"})
    monkeypatch.setattr(sweep, "PIONEER_SWEEP_PROMPTS", [{"id": "prompt1", "prompt": "prompt1", "expected_kind": "EVIDENCE"}])
    monkeypatch.setattr(sweep, "_availability_probe", lambda model: {"available": True, "model": model})
    monkeypatch.setattr(
        sweep,
        "_route_gate_short_probe",
        lambda model: {"usable": True, "error_category": None, "prompt_results": [{"parse_error": False}]},
    )
    monkeypatch.setattr(sweep, "_semantic_json_probe", lambda model, prompt: {"parse_error": False, "route": "EVIDENCE_PIPELINE", "prompt": prompt})
    monkeypatch.setattr(sweep, "AgentExecutor", lambda config: _FakeExecutor())

    result = run_pioneer_model_sweep(SimpleNamespace(outputs_dir=tmp_path), models=["SlowModel"], report_dir=tmp_path)

    model_result = result["models"][0]
    assert model_result["route_gate_probe"]["usable"] is True
    assert len(model_result["prompt_results"]) == 1


def test_all_semantic_probe_parse_failures_do_not_fast_fail_closed_smoke(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        sweep,
        "PIONEER_SWEEP_PROMPTS",
        [{"id": "data", "prompt": "What schemas do I have?", "expected_kind": "EVIDENCE"}],
    )
    monkeypatch.setattr(sweep, "AgentExecutor", lambda config: _FakeExecutor())
    monkeypatch.setattr(sweep, "_availability_probe", lambda model: {"available": True, "model": model})
    monkeypatch.setattr(
        sweep,
        "_semantic_json_probe",
        lambda model, prompt: {
            "model": model,
            "prompt": prompt,
            "parse_error": True,
            "route": "EVIDENCE_PIPELINE",
            "requires_evidence": True,
            "pure_no_evidence": False,
        },
    )

    result = run_pioneer_model_sweep(SimpleNamespace(outputs_dir=tmp_path), models=["ModelA"], report_dir=tmp_path)

    model_result = result["models"][0]
    assert model_result.get("smoke_fast_failed") is not True
    assert model_result["prompt_results"][0]["pass"] is True
    assert model_result["metrics"]["semantic_fallback_count"] == 1


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


def test_report_generation_preserves_public_model_labels_when_model_is_in_env(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("PIONEER_MODEL", "Claude Haiku 4.5")
    model_result = {
        "model": "Claude Haiku 4.5",
        "pioneer_model": "Claude Haiku 4.5",
        "pioneer_model_id": "claude-haiku-4-5",
        "safe_model_name": safe_model_name("Claude Haiku 4.5"),
        "model_sweep_run_id": safe_model_name("Claude Haiku 4.5"),
        "group": "anthropic_fast_small",
        "availability": {"available": True},
        "metrics": {
            "json_parse_failures": 0,
            "semantic_fallback_count": 0,
            "llm_direct_count": 2,
            "evidence_pipeline_count": 5,
            "evidence_pipeline_bypassed_count": 2,
            "evidence_bus_built_count": 5,
            "no_tool_fp": 0,
            "unsupported_claims": 0,
            "focused_smoke_pass": False,
            "latency_sec": 1.0,
        },
        "prompt_results": [{"pioneer_model": "Claude Haiku 4.5", "pioneer_model_id": "claude-haiku-4-5"}],
    }

    write_pioneer_model_sweep_reports(tmp_path, [model_result])

    payload = json.loads((tmp_path / "per_model_claude_haiku_4_5.json").read_text(encoding="utf-8"))
    summary = json.loads((tmp_path / "pioneer_model_sweep_summary.json").read_text(encoding="utf-8"))
    assert payload["model"] == "Claude Haiku 4.5"
    assert payload["pioneer_model_id"] == "claude-haiku-4-5"
    assert payload["prompt_results"][0]["pioneer_model"] == "Claude Haiku 4.5"
    assert summary["models"][0]["model"] == "Claude Haiku 4.5"


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
    assert model_result["model_connection_status"] == "provider_unavailable"


def test_callable_route_parse_failure_is_protocol_parse_failure_not_not_connected(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(sweep, "SLOW_ROUTE_PROBE_MODELS", {"ParseFailModel"})
    monkeypatch.setattr(sweep, "_availability_probe", lambda model: {"available": True, "model": model})
    monkeypatch.setattr(
        sweep,
        "_route_gate_short_probe",
        lambda model: {
            "usable": False,
            "error_category": "route_gate_parse_failure",
            "prompt_results": [{"parse_error": True}],
        },
    )

    result = run_pioneer_model_sweep(SimpleNamespace(outputs_dir=tmp_path), models=["ParseFailModel"], report_dir=tmp_path)

    model_result = result["models"][0]
    assert model_result["availability_probe_callable"] is True
    assert model_result["route_atomic_call_completed"] is True
    assert model_result["route_atomic_parse_success"] is False
    assert model_result["route_atomic_failure_category"] == "protocol_parse_failure"
    assert model_result["model_connection_status"] == "protocol_parse_failure"


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
                    "llm_pass_count": 1,
                },
            },
            {
                "checkpoint_id": "checkpoint_llm_owned_pass_graph_gate",
                "input_summary": {"llm_pass_count": 1},
                "output": {"pass_count": 1},
            },
            {"checkpoint_id": "checkpoint_14_evidence_bus", "output": {}},
            {"checkpoint_id": "checkpoint_broad_question_classifier", "output": {}},
        ],
    }
