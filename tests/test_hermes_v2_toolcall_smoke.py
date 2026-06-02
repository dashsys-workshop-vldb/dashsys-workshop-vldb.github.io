from __future__ import annotations

from scripts.run_hermes_v2_toolcall_smoke import _build_smoke_row, _summarize_rows, _timeout_row


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
