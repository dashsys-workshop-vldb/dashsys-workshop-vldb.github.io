from __future__ import annotations

from contextlib import redirect_stdout
from pathlib import Path

import scripts.run_hermes_v2_toolcall_smoke as smoke
import scripts.diagnose_deepseek_v2_planner_only as planner_diag
from scripts.run_hermes_v2_toolcall_smoke import (
    _build_smoke_row,
    _finalize_row_timing,
    _run_prompt_with_timeout,
    _summarize_rows,
    _timeout_row,
    _write_heartbeat,
)


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


def test_planner_only_diagnostic_emits_seven_rows(monkeypatch, tiny_project):
    def fake_run_prompt(item, *, config, timeout_sec):
        return {
            "prompt_id": item["id"],
            "expected_class": item["expected"],
            "planner_timeout": False,
            "planner_elapsed_sec": 0.01,
            "tool_calls_count": 1,
            "finish_reason": "tool_calls",
            "semantic_ir_present": True,
            "semantic_ir_task_count": 1,
            "semantic_ir_task_types": ["DIRECT" if item["expected"] == "DIRECT" else "SQL"],
            "answer_contract_present": item["expected"] != "DIRECT",
            "evidence_contract_present": item["expected"] != "DIRECT",
            "raw_text_content_present": False,
            "response_error_type": None,
            "response_error_message": None,
            "tool_name": "submit_semantic_ir_plan",
            "planner_schema_profile": "deepseek_compact",
        }

    monkeypatch.setattr(planner_diag, "_run_prompt_with_timeout", fake_run_prompt)
    report = planner_diag.run_planner_only_diagnostics(config=tiny_project, report_dir=tiny_project.outputs_dir / "planner_only", timeout_sec=1)

    assert report["row_count"] == 7
    assert report["timeout_count"] == 0
    assert report["semantic_ir_present_count"] == 7
    assert Path(report["json_path"]).exists()
    assert Path(report["md_path"]).exists()


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


def test_smoke_accepts_scoped_zero_row_local_evidence_when_final_gate_passes():
    result = {
        "final_answer": "An inactive journey is a journey that is not currently active or running. No inactive journeys were found.",
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
                    "passes": [{"path": "DIRECT"}, {"path": "SQL"}],
                },
                {"kind": "sql_call", "result": {"ok": True, "row_count": 0, "rows": []}},
                {"kind": "evidence_boundary", "evidence_pipeline_bypassed": False, "evidence_bus_built": True},
            ]
        },
        "checkpoints": [
            {
                "checkpoint_result_bundle": "ignored",
                "checkpoint_id": "checkpoint_result_bundle",
                "output": {
                    "runtime_passes": {
                        "items": [
                            {"pass_id": "t1", "path": "DIRECT", "status": "SUCCESS", "facts": ["direct_answer:inactive journey concept"]},
                            {"pass_id": "t2", "path": "SQL", "status": "EMPTY", "facts": []},
                        ],
                        "total_items": 2,
                        "truncated_items": False,
                    }
                },
            },
            {"checkpoint_id": "checkpoint_llm_final_answer_semantic_gate", "output": {"passed": True}},
            {"checkpoint_id": "checkpoint_llm_owned_final_answer_boundary", "output": {"answer_semantic_gate_passed": True}},
        ],
    }

    row = _build_smoke_row(
        {
            "id": "mixed_inactive_journeys",
            "prompt": "Explain what inactive journey means and show inactive journeys.",
            "expected": "EVIDENCE_LOCAL",
        },
        result,
    )

    assert row["local_snapshot_fact_count"] == 0
    assert row["zero_row_local_evidence_count"] == 1
    assert row["matches_expectation"] is True
    assert row["pass"] is True


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


def test_smoke_timing_accounting_never_reports_negative_invisible_time():
    row = {
        "total_latency_sec": 1.0,
        "semantic_ir_planner_latency_sec": 0.8,
        "semantic_ir_repair_latency_sec": 0.7,
        "final_composer_latency_sec": 0.2,
    }

    _finalize_row_timing(row)

    assert row["instrumented_latency_sec"] == 1.7
    assert row["invisible_time_sec"] == 0.0
    assert row["timing_accounting_error"] is True


def test_timeout_row_records_stage_and_keeps_summary_partial():
    item = {"id": "slow_prompt", "prompt": "Explain and show data.", "expected": "EVIDENCE_LOCAL"}
    heartbeat = {"current_stage": "checkpoint_llm_final_answer_composer", "prompt_id": "slow_prompt"}

    row = _timeout_row(item, timeout_sec=3, total_latency_sec=3.25, heartbeat=heartbeat)
    summary = _summarize_rows([row])

    assert row["prompt_id"] == "slow_prompt"
    assert row["timed_out"] is True
    assert row["timed_out_stage"] == "checkpoint_llm_final_answer_composer"
    assert row["total_latency_sec"] == 3.25
    assert row["invisible_time_sec"] == 3.25
    assert row["timing_accounting_error"] is False
    assert row["pass"] is False
    assert summary["timeout_count"] == 1
    assert summary["passed_count"] == 0


def test_write_heartbeat_emits_flushable_worker_log_line(tmp_path):
    log_path = tmp_path / "worker.log"

    with log_path.open("w", encoding="utf-8") as log_file, redirect_stdout(log_file):
        _write_heartbeat(
            tmp_path,
            "mixed_inactive_journeys",
            "checkpoint_llm_owned_pass_graph_gate",
            {"stage": "llm-owned pass graph validation"},
        )

    text = log_path.read_text(encoding="utf-8")
    assert "HEARTBEAT" in text
    assert "mixed_inactive_journeys" in text
    assert "checkpoint_llm_owned_pass_graph_gate" in text
    assert "llm-owned pass graph validation" in text


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


def test_prompt_worker_llm_timeout_is_bounded_below_prompt_timeout(monkeypatch, tiny_project):
    captured = {}

    class FakeQueue:
        def get(self, timeout=None):
            return {
                "ok": True,
                "row": {
                    "prompt_id": "bounded_prompt",
                    "prompt": "What schemas do I have?",
                    "expected": "EVIDENCE_LOCAL",
                    "pass": True,
                    "timed_out": False,
                },
            }

    class FakeProcess:
        exitcode = 0

        def __init__(self, *args, **kwargs):
            captured["process_args"] = kwargs.get("args") or (args[0] if args else ())

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
            return FakeProcess(*args, **kwargs)

    monkeypatch.setattr(smoke.mp, "get_context", lambda *_args, **_kwargs: FakeContext())

    row = _run_prompt_with_timeout(
        {"id": "bounded_prompt", "prompt": "What schemas do I have?", "expected": "EVIDENCE_LOCAL"},
        config=tiny_project,
        report_dir=tiny_project.outputs_dir / "smoke",
        prompt_timeout_sec=120,
        llm_call_timeout_sec=180,
    )

    assert row["pass"] is True
    assert captured["process_args"][3] <= 110


def test_smoke_worker_start_method_defaults_to_spawn_on_macos(monkeypatch):
    monkeypatch.delenv("HERMES_SMOKE_MP_START_METHOD", raising=False)
    monkeypatch.setattr(smoke.sys, "platform", "darwin")

    assert smoke._worker_start_method() == "spawn"


def test_smoke_worker_start_method_env_override(monkeypatch):
    monkeypatch.setenv("HERMES_SMOKE_MP_START_METHOD", "forkserver")
    monkeypatch.setattr(smoke.sys, "platform", "darwin")

    assert smoke._worker_start_method() == "forkserver"


def test_prompt_worker_crash_returns_exitcode_and_child_log_without_hanging(monkeypatch, tiny_project):
    item = {"id": "crashy_prompt", "prompt": "What schemas do I have?", "expected": "EVIDENCE_LOCAL"}
    report_dir = tiny_project.outputs_dir / "smoke"
    report_dir.mkdir(parents=True, exist_ok=True)
    child_log = smoke._child_log_path(report_dir, item["id"])
    child_log.write_text("objc crash details\n+[NSNumber initialize] fork safety\n", encoding="utf-8")

    class FakeQueue:
        def get(self, timeout=None):
            raise RuntimeError("empty queue")

    class FakeProcess:
        exitcode = -6

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
        item,
        config=tiny_project,
        report_dir=report_dir,
        prompt_timeout_sec=5,
        llm_call_timeout_sec=1,
    )

    assert row["pass"] is False
    assert row["timed_out"] is False
    assert row["child_exitcode"] == -6
    assert "+[NSNumber initialize]" in row["child_stderr_tail"]
    assert row["error"] == "prompt_worker_exited_nonzero_exitcode_-6"


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


def test_smoke_records_row_failure_and_continues_all_prompts(monkeypatch, tiny_project, tmp_path):
    monkeypatch.setenv("DASHAGENT_LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:8000/v1")
    monkeypatch.setattr(smoke, "load_local_env", lambda *args, **kwargs: {"keys_loaded": []})
    monkeypatch.setattr(
        smoke,
        "run_hermes_toolcall_probe",
        lambda *args, **kwargs: {
            "ok": True,
            "provider": "openai",
            "model": "unit-model",
            "sdk_path_used": True,
            "toolcall_supported": True,
            "tool_calls_count": 1,
            "tool_name": "submit_probe_result",
            "finish_reason": "tool_calls",
            "error": "",
        },
    )
    seen: list[str] = []

    def fake_prompt(item, **kwargs):
        seen.append(item["id"])
        if item["id"] == "ambiguous_user_schemas":
            raise RuntimeError("missing_answer_contract")
        return {
            "prompt_id": item["id"],
            "prompt": item["prompt"],
            "expected": item["expected"],
            "pass": True,
            "unsupported_claims": 0,
            "final_semantic_gate_final_failures": 0,
            "no_tool_fp": False,
            "runtime_fact_count": 1,
            "compiled_sql_count": 1 if item["expected"] != "DIRECT" else 0,
            "compiled_api_count": 0,
            "sql_calls": 1 if item["expected"] != "DIRECT" else 0,
            "api_calls": 0,
            "sdk_toolcall_semantic_ir_used": True,
            "atomic_protocol_fallback_used": False,
            "timed_out": False,
        }

    monkeypatch.setattr(smoke, "_run_prompt_with_timeout", fake_prompt)

    report = smoke.run_hermes_v2_toolcall_smoke(config=tiny_project, report_dir=tmp_path)

    assert len(seen) == len(smoke.SMOKE_PROMPTS)
    assert len(report["rows"]) == len(smoke.SMOKE_PROMPTS)
    failed = next(row for row in report["rows"] if row["prompt_id"] == "ambiguous_user_schemas")
    assert failed["pass"] is False
    assert failed["error_type"] == "missing_answer_contract"
    assert report["summary"]["row_count"] == len(smoke.SMOKE_PROMPTS)
    assert report["summary"]["failed_count"] == 1


def test_smoke_row_and_summary_record_schema_binding_diagnostics():
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
                        "schema_binding_enabled": True,
                        "schema_binding_mode": "experimental_toolcall",
                        "schema_binding_used": True,
                        "schema_binding_count": 1,
                        "schema_binding_validation_passed": True,
                        "schema_binding_repair_attempted": True,
                        "schema_binding_repair_success": True,
                        "schema_binding_error_type": None,
                        "schema_binding_ids": ["b_schema"],
                    },
                },
                {"kind": "sql_call", "result": {"ok": True, "row_count": 1, "rows": [{"count": 74}]}},
                {"kind": "evidence_boundary", "evidence_pipeline_bypassed": False, "evidence_bus_built": True},
            ]
        },
        "checkpoints": [
            {"checkpoint_id": "checkpoint_llm_final_answer_semantic_gate", "output": {"passed": True}},
            {"checkpoint_id": "checkpoint_llm_owned_final_answer_boundary", "output": {"answer_semantic_gate_passed": True, "answer_repair_attempts": 0}},
        ],
    }

    row = _build_smoke_row({"id": "local_schema_count", "prompt": "How many schema records are in the local snapshot?", "expected": "EVIDENCE_SQL"}, result)
    summary = _summarize_rows([row, {**row, "schema_binding_validation_passed": False, "schema_binding_error_type": "unknown_field"}])

    assert row["schema_binding_used"] is True
    assert row["schema_binding_enabled"] is True
    assert row["schema_binding_mode"] == "experimental_toolcall"
    assert row["schema_binding_validation_passed"] is True
    assert row["schema_binding_repair_attempted"] is True
    assert row["schema_binding_repair_success"] is True
    assert row["schema_binding_ids"] == ["b_schema"]
    assert summary["schema_binding_used_count"] == 2
    assert summary["schema_binding_enabled_count"] == 2
    assert summary["schema_binding_mode_counts"] == {"experimental_toolcall": 2}
    assert summary["schema_binding_validation_failure_count"] == 1
