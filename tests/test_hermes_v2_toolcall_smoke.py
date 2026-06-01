from __future__ import annotations

from scripts.run_hermes_v2_toolcall_smoke import _build_smoke_row


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
            {"checkpoint_id": "checkpoint_llm_owned_final_answer_boundary", "output": {"answer_semantic_gate_passed": True}},
        ],
    }

    row = _build_smoke_row({"id": "local_schema_count", "prompt": "How many schema records are in the local snapshot?", "expected": "EVIDENCE_SQL"}, result)

    assert row["runtime_fact_count"] == 1
    assert row["local_snapshot_fact_count"] == 1
    assert row["caveat_or_error_only_count"] == 0
    assert row["final_semantic_gate_initial_failures"] == 0
    assert row["final_semantic_gate_final_failures"] == 0
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
