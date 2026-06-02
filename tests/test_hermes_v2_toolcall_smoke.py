from __future__ import annotations

from pathlib import Path

import scripts.run_hermes_v2_toolcall_smoke as smoke
from scripts.run_hermes_v2_toolcall_smoke import _build_smoke_row, _run_prompt_with_timeout, _summarize_rows, _timeout_row


def test_smoke_row_counts_successful_sql_rows_as_runtime_facts():
    result = {
        "final_answer": "There are 74 schema records in the local snapshot.",
        "output_dir": "/tmp/out",
        "trajectory": {
            "steps": [
                {
                    "kind": "llm_unified_planner",
                    "route": "EVIDENCE_PIPELINE",
                    "diagnostics": {
                        "sdk_toolcall_semantic_ir_used": True,
                        "semantic_ir_validation_passed": True,
                        "backend_formal_compilation_used": True,
                        "atomic_protocol_fallback_used": False,
                        "compiled_sql_count": 1,
                        "compiled_api_count": 0,
                    },
                },
                {
                    "kind": "sql_call",
                    "result": {
                        "ok": True,
                        "row_count": 1,
                        "rows": {"items": [{"count": 74}], "total_items": 1, "truncated_items": False},
                    },
                },
                {
                    "kind": "evidence_boundary",
                    "evidence_pipeline_bypassed": False,
                    "evidence_bus_built": True,
                    "post_evidence_answer_router_ran": False,
                },
                {
                    "kind": "answer_diagnostics",
                    "semantic_gate": {"passed": True, "unsupported_claims": []},
                    "answer_semantic_gate_passed": True,
                },
            ]
        },
        "checkpoints": [
            {"checkpoint_id": "checkpoint_llm_final_answer_semantic_gate", "output": {"passed": True}},
            {"checkpoint_id": "checkpoint_llm_owned_final_answer_boundary", "output": {"answer_semantic_gate_passed": True, "answer_repair_attempts": 0}},
        ],
    }

    row = _build_smoke_row({"id": "local_schema_count", "prompt": "How many schema records are in the local snapshot?", "expected": "EVIDENCE_SQL"}, result)

    assert row["runtime_fact_count"] == 1
    assert row["local_snapshot_fact_count"] == 1
    assert row["caveat_or_error_only_count"] == 0
    assert row["final_semantic_gate_initial_failures"] == 0
    assert row["final_semantic_gate_final_failures"] == 0
    assert row["final_answer_repair_attempts"] == 0
    assert row["repaired_success"] is False
    assert row["no_tool_fp"] is False
    assert row["pass"] is True


def test_smoke_row_counts_compacted_sql_success_with_answer_slots_as_runtime_facts():
    result = {
        "final_answer": "Based on the local snapshot, you have 74 schemas. Examples include Schema Alpha and Schema Beta.",
        "output_dir": "/tmp/out",
        "trajectory": {
            "steps": [
                {
                    "kind": "llm_unified_planner",
                    "route": "EVIDENCE_PIPELINE",
                    "diagnostics": {
                        "sdk_toolcall_semantic_ir_used": True,
                        "semantic_ir_validation_passed": True,
                        "backend_formal_compilation_used": True,
                        "atomic_protocol_fallback_used": False,
                        "compiled_sql_count": 1,
                        "compiled_api_count": 0,
                    },
                    "passes": [{"path": "SQL"}],
                },
                {
                    "kind": "sql_call",
                    "result": {
                        "preview": '{"ok":true,"rows":{"items":[{"NAME":"Schema Alpha"},{"NAME":"Schema Beta"}],"total_items":74',
                        "truncated": True,
                    },
                },
                {"kind": "evidence_boundary", "evidence_pipeline_bypassed": False, "evidence_bus_built": True},
                {"kind": "answer_diagnostics", "semantic_gate": {"passed": True, "unsupported_claims": []}},
            ]
        },
        "checkpoints": [
            {
                "checkpoint_id": "checkpoint_result_bundle",
                "output": {
                    "runtime_passes": {
                        "items": [{"pass_id": "fetch_local_schemas", "path": "SQL", "status": "SUCCESS"}],
                        "total_items": 1,
                        "truncated_items": False,
                    }
                },
            },
            {
                "checkpoint_id": "checkpoint_llm_final_answer_composer",
                "input_summary": {
                    "runtime_pass_count": 1,
                    "slot_counts": {
                        "sql_row_count": 74,
                        "counts": {"items": ["74"], "total_items": 1, "truncated_items": False},
                        "entity_names": {"items": ["Schema Alpha", "Schema Beta"], "total_items": 2, "truncated_items": False},
                    },
                },
            },
            {"checkpoint_id": "checkpoint_llm_final_answer_semantic_gate", "output": {"passed": True}},
            {"checkpoint_id": "checkpoint_llm_owned_final_answer_boundary", "output": {"answer_semantic_gate_passed": True}},
        ],
    }

    row = _build_smoke_row({"id": "ambiguous_user_schemas", "prompt": "What schemas do I have?", "expected": "EVIDENCE_LOCAL"}, result)

    assert row["runtime_fact_count"] > 0
    assert row["local_snapshot_fact_count"] > 0
    assert row["matches_expectation"] is True
    assert row["pass"] is True


def test_smoke_partial_caveat_after_local_facts_is_not_global_unavailable():
    result = {
        "final_answer": "Local snapshot evidence shows count: 2; examples include Birthday Message. Some requested runtime evidence was unavailable for this query/scope.",
        "output_dir": "/tmp/out",
        "trajectory": {
            "steps": [
                {
                    "kind": "llm_unified_planner",
                    "route": "EVIDENCE_PIPELINE",
                    "diagnostics": {
                        "sdk_toolcall_semantic_ir_used": True,
                        "semantic_ir_validation_passed": True,
                        "backend_formal_compilation_used": True,
                        "atomic_protocol_fallback_used": False,
                        "compiled_sql_count": 1,
                        "compiled_api_count": 0,
                    },
                    "passes": [{"path": "SQL"}],
                },
                {"kind": "sql_call", "result": {"ok": True, "row_count": 2, "rows": [{"NAME": "Birthday Message"}, {"NAME": "Gold Tier Welcome Email"}]}},
                {"kind": "evidence_boundary", "evidence_pipeline_bypassed": False, "evidence_bus_built": True},
                {"kind": "answer_diagnostics", "semantic_gate": {"passed": True, "unsupported_claims": []}, "answer_semantic_gate_passed": True},
            ]
        },
        "checkpoints": [
            {"checkpoint_id": "checkpoint_llm_final_answer_semantic_gate", "output": {"passed": True}},
            {"checkpoint_id": "checkpoint_llm_owned_final_answer_boundary", "output": {"answer_semantic_gate_passed": True}},
        ],
    }

    row = _build_smoke_row({"id": "mixed_inactive_journeys", "prompt": "Explain what inactive journey means and show inactive journeys.", "expected": "EVIDENCE_LOCAL"}, result)

    assert row["runtime_fact_count"] > 0
    assert row["final_unavailable_with_runtime_facts"] is False


def test_smoke_row_fails_local_preference_when_data_prompt_uses_api_only():
    result = {
        "final_answer": "Runtime evidence was unavailable; cannot provide a verified answer.",
        "output_dir": "/tmp/out",
        "trajectory": {
            "steps": [
                {
                    "kind": "llm_unified_planner",
                    "route": "EVIDENCE_PIPELINE",
                    "diagnostics": {
                        "sdk_toolcall_semantic_ir_used": True,
                        "semantic_ir_validation_passed": True,
                        "backend_formal_compilation_used": True,
                        "atomic_protocol_fallback_used": False,
                        "compiled_sql_count": 0,
                        "compiled_api_count": 1,
                    },
                },
                {
                    "kind": "api_call",
                    "result": {
                        "ok": False,
                        "dry_run": True,
                        "error": "Adobe credentials unavailable",
                    },
                },
                {"kind": "evidence_boundary", "evidence_pipeline_bypassed": False, "evidence_bus_built": True},
                {
                    "kind": "answer_diagnostics",
                    "semantic_gate": {"passed": True, "unsupported_claims": []},
                    "answer_semantic_gate_passed": True,
                },
            ]
        },
        "checkpoints": [
            {"checkpoint_id": "checkpoint_llm_final_answer_semantic_gate", "output": {"passed": True}},
            {"checkpoint_id": "checkpoint_llm_owned_final_answer_boundary", "output": {"answer_semantic_gate_passed": True}},
        ],
    }

    row = _build_smoke_row({"id": "ambiguous_user_schemas", "prompt": "What schemas do I have?", "expected": "EVIDENCE_LOCAL"}, result)

    assert row["runtime_fact_count"] == 0
    assert row["caveat_or_error_only_count"] == 1
    assert row["no_tool_fp"] is False
    assert row["pass"] is False


def test_smoke_row_fails_when_global_unavailable_answer_has_runtime_facts():
    result = {
        "final_answer": "Runtime evidence was unavailable; cannot provide a verified answer.",
        "output_dir": "/tmp/out",
        "trajectory": {
            "steps": [
                {
                    "kind": "llm_unified_planner",
                    "route": "EVIDENCE_PIPELINE",
                    "diagnostics": {
                        "sdk_toolcall_semantic_ir_used": True,
                        "semantic_ir_validation_passed": True,
                        "backend_formal_compilation_used": True,
                        "atomic_protocol_fallback_used": False,
                        "compiled_sql_count": 1,
                        "compiled_api_count": 0,
                    },
                },
                {
                    "kind": "sql_call",
                    "result": {
                        "ok": True,
                        "row_count": 1,
                        "rows": [{"count": 74}],
                    },
                },
                {"kind": "evidence_boundary", "evidence_pipeline_bypassed": False, "evidence_bus_built": True},
            ]
        },
        "checkpoints": [
            {"checkpoint_id": "checkpoint_llm_final_answer_semantic_gate", "output": {"passed": False}},
            {"checkpoint_id": "checkpoint_llm_owned_final_answer_boundary", "output": {"answer_semantic_gate_passed": False, "answer_repair_attempts": 1}},
        ],
    }

    row = _build_smoke_row({"id": "local_schema_count", "prompt": "How many schema records are in the local snapshot?", "expected": "EVIDENCE_SQL"}, result)

    assert row["runtime_fact_count"] == 1
    assert row["final_answer_repair_attempts"] == 1
    assert row["pass"] is False


def test_smoke_row_records_repaired_success():
    result = {
        "final_answer": "There are 74 schema records in the local snapshot.",
        "output_dir": "/tmp/out",
        "trajectory": {
            "steps": [
                {
                    "kind": "llm_unified_planner",
                    "route": "EVIDENCE_PIPELINE",
                    "diagnostics": {
                        "sdk_toolcall_semantic_ir_used": True,
                        "semantic_ir_validation_passed": True,
                        "backend_formal_compilation_used": True,
                        "atomic_protocol_fallback_used": False,
                        "compiled_sql_count": 1,
                        "compiled_api_count": 0,
                    },
                },
                {"kind": "sql_call", "result": {"ok": True, "row_count": 1, "rows": [{"count": 74}]}},
                {"kind": "evidence_boundary", "evidence_pipeline_bypassed": False, "evidence_bus_built": True},
            ]
        },
        "checkpoints": [
            {"checkpoint_id": "checkpoint_llm_final_answer_semantic_gate", "output": {"passed": False}},
            {"checkpoint_id": "checkpoint_llm_final_answer_repair", "output": {"semantic_gate": {"passed": True, "unsupported_claims": []}}},
            {"checkpoint_id": "checkpoint_llm_owned_final_answer_boundary", "output": {"answer_semantic_gate_passed": True, "answer_repair_attempts": 1}},
        ],
    }

    row = _build_smoke_row({"id": "local_schema_count", "prompt": "How many schema records are in the local snapshot?", "expected": "EVIDENCE_SQL", "expected_answer_contains": "74"}, result)

    assert row["final_answer_repair_attempts"] == 1
    assert row["repaired_success"] is True
    assert row["pass"] is True


def test_smoke_row_extracts_stage_latency_fields():
    result = {
        "final_answer": "There are 74 schema records in the local snapshot.",
        "output_dir": "/tmp/out",
        "trajectory": {
            "steps": [
                {
                    "kind": "llm_unified_planner",
                    "diagnostics": {
                        "sdk_toolcall_semantic_ir_used": True,
                        "semantic_ir_validation_passed": True,
                        "backend_formal_compilation_used": True,
                        "atomic_protocol_fallback_used": False,
                        "compiled_sql_count": 1,
                        "compiled_api_count": 0,
                        "semantic_ir_provider_latency_ms": 1234,
                        "semantic_ir_validation_latency_ms": 20,
                        "semantic_ir_repair_latency_ms": 0,
                        "semantic_ir_support_check_latency_ms": 7,
                        "raw_sql_fallback_latency_ms": 0,
                        "compiler_latency_ms": 9,
                    },
                },
                {"kind": "sql_call", "result": {"ok": True, "row_count": 1, "rows": [{"count": 74}]}},
                {"kind": "evidence_boundary", "evidence_pipeline_bypassed": False, "evidence_bus_built": True},
            ],
            "timings": {"answer_time": 0.25},
        },
        "checkpoints": [
            {"checkpoint_id": "checkpoint_llm_owned_sql_compile_gate", "duration_ms": 11, "output": {"passed": True}},
            {"checkpoint_id": "checkpoint_llm_owned_api_request_gate", "duration_ms": 13, "output": {"passed": True}},
            {"checkpoint_id": "checkpoint_llm_final_answer_semantic_gate", "duration_ms": 17, "output": {"passed": True}},
            {"checkpoint_id": "checkpoint_llm_owned_final_answer_boundary", "duration_ms": 19, "output": {"answer_semantic_gate_passed": True, "answer_repair_attempts": 0}},
        ],
    }

    row = _build_smoke_row({"id": "local_schema_count", "prompt": "How many schema records are in the local snapshot?", "expected": "EVIDENCE_SQL"}, result)

    assert row["semantic_ir_planner_latency_sec"] == 1.234
    assert row["semantic_ir_validation_latency_sec"] == 0.02
    assert row["semantic_ir_support_check_latency_sec"] == 0.007
    assert row["compiler_latency_sec"] == 0.009
    assert row["sql_gate_latency_sec"] == 0.011
    assert row["api_gate_latency_sec"] == 0.013
    assert row["final_composer_latency_sec"] == 0.25
    assert row["final_gate_latency_sec"] == 0.017
    assert row["timed_out_stage"] is None


def test_timeout_row_records_stage_and_keeps_summary_partial():
    item = {"id": "slow_prompt", "prompt": "Explain and show data.", "expected": "EVIDENCE_LOCAL"}
    heartbeat = {"current_stage": "checkpoint_llm_final_answer_composer", "prompt_id": "slow_prompt"}

    row = _timeout_row(item, timeout_sec=3, total_latency_sec=3.25, heartbeat=heartbeat)
    summary = _summarize_rows([row])

    assert row["prompt_id"] == "slow_prompt"
    assert row["timed_out"] is True
    assert row["timed_out_stage"] == "checkpoint_llm_final_answer_composer"
    assert row["total_latency_sec"] == 3.25
    assert row["pass"] is False
    assert summary["timeout_count"] == 1
    assert summary["passed_count"] == 0


def test_prompt_timeout_escalates_to_kill_when_terminate_does_not_stop_worker(monkeypatch, tiny_project):
    class FakeQueue:
        pass

    class FakeProcess:
        def __init__(self, *args, **kwargs):
            self.terminate_called = False
            self.kill_called = False
            self._alive = True

        def start(self):
            return None

        def join(self, timeout=None):
            return None

        def is_alive(self):
            return self._alive

        def terminate(self):
            self.terminate_called = True

        def kill(self):
            self.kill_called = True
            self._alive = False

    fake_process = FakeProcess()

    class FakeContext:
        def Queue(self, maxsize=0):
            return FakeQueue()

        def Process(self, *args, **kwargs):
            return fake_process

    monkeypatch.setattr(smoke.mp, "get_context", lambda *_args, **_kwargs: FakeContext())

    row = _run_prompt_with_timeout(
        {"id": "slow_prompt", "prompt": "Explain and show data.", "expected": "EVIDENCE_LOCAL"},
        config=tiny_project,
        report_dir=tiny_project.outputs_dir / "smoke",
        prompt_timeout_sec=1,
        llm_call_timeout_sec=1,
    )

    assert fake_process.terminate_called is True
    assert fake_process.kill_called is True
    assert row["timed_out"] is True


def test_prompt_worker_waits_for_queue_payload_after_process_exit(monkeypatch, tiny_project):
    captured = {}

    class FakeQueue:
        def get(self, timeout=None):
            captured["queue_timeout"] = timeout
            return {
                "ok": True,
                "row": {
                    "prompt_id": "quick_prompt",
                    "prompt": "What schemas do I have?",
                    "expected": "EVIDENCE_LOCAL",
                    "pass": True,
                    "timed_out": False,
                },
            }

    class FakeProcess:
        exitcode = 0

        def start(self):
            return None

        def join(self, timeout=None):
            return None

        def is_alive(self):
            return False

    class FakeContext:
        def Queue(self, maxsize=0):
            return FakeQueue()

        def Process(self, *args, **kwargs):
            return FakeProcess()

    monkeypatch.setattr(smoke.mp, "get_context", lambda *_args, **_kwargs: FakeContext())

    row = _run_prompt_with_timeout(
        {"id": "quick_prompt", "prompt": "What schemas do I have?", "expected": "EVIDENCE_LOCAL"},
        config=tiny_project,
        report_dir=tiny_project.outputs_dir / "smoke",
        prompt_timeout_sec=5,
        llm_call_timeout_sec=1,
    )

    assert captured["queue_timeout"] == 5
    assert row["prompt_id"] == "quick_prompt"
    assert row["pass"] is True


def test_smoke_uses_gemini_openai_compat_probe_and_report_name(monkeypatch, tiny_project, tmp_path):
    monkeypatch.setenv("DASHAGENT_LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
    monkeypatch.setenv("OPENAI_API_KEY", "unit-gemini-key")
    monkeypatch.setenv("OPENAI_MODEL", "gemini-3.5-flash")
    monkeypatch.setattr(smoke, "load_local_env", lambda *args, **kwargs: {"keys_loaded": []})

    captured = {}

    def legacy_probe(*args, **kwargs):
        raise AssertionError("legacy Hermes probe should not be used for Gemini OpenAI-compatible smoke")

    def gemini_probe(config=None, *, report_dir=None):
        captured["probe_report_dir"] = Path(report_dir)
        return {
            "ok": True,
            "provider": "openai",
            "openai_compat_provider": "gemini",
            "model": "gemini-3.5-flash",
            "sdk_path_used": True,
            "toolcall_supported": True,
            "tool_calls_count": 1,
            "tool_name": "submit_probe_result",
            "finish_reason": "tool_calls",
            "error": "",
        }

    def fake_prompt(item, **kwargs):
        return {
            "prompt_id": item["id"],
            "prompt": item["prompt"],
            "expected": item["expected"],
            "pass": True,
            "unsupported_claims": 0,
            "final_semantic_gate_final_failures": 0,
            "no_tool_fp": False,
            "runtime_fact_count": 1,
            "compiled_sql_count": 1,
            "compiled_api_count": 0,
            "sql_calls": 1,
            "api_calls": 0,
            "sdk_toolcall_semantic_ir_used": True,
            "atomic_protocol_fallback_used": False,
        }

    monkeypatch.setattr(smoke, "run_hermes_toolcall_probe", legacy_probe)
    monkeypatch.setattr(smoke, "run_gemini_openai_toolcall_probe", gemini_probe, raising=False)
    monkeypatch.setattr(smoke, "_run_prompt_with_timeout", fake_prompt)

    report = smoke.run_hermes_v2_toolcall_smoke(config=tiny_project, report_dir=tmp_path)

    assert report["ok"] is True
    assert report["report_name"] == "gemini_openai_compat_smoke"
    assert report["report_title"] == "Gemini OpenAI-Compatible V2 Toolcall Smoke"
    assert Path(report["json_path"]).name == "gemini_openai_compat_smoke.json"
    assert captured["probe_report_dir"].name == "gemini_toolcall_probe"
