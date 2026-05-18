from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.generate_consolidated_reports import generate_consolidated_reports
from scripts.run_sdk_tool_calling_optimization_audit import (
    compact_tool_result_evidence_summary,
    compact_tool_schema,
    rewrite_gate_allows_rewrite,
    run_sdk_tool_calling_optimization_audit,
)
from scripts.run_sdk_tool_calling_optimization_trials import run_sdk_tool_calling_optimization_trials


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _seed_sdk_optimization_inputs(outputs: Path) -> None:
    reports = outputs / "reports"
    _write_json(
        reports / "llm_baseline_summary.json",
        {
            "report_type": "llm_baseline_summary",
            "best_llm_baseline": "GUIDED_REAL_LLM_TWO_TOOLS_BASELINE",
            "best_llm_baseline_score": 0.6328,
            "sql_first_api_verify_score": 0.6553,
            "provider_type": "openai_compatible",
            "backend_type": "openai_sdk",
            "current_backend_model": "unit-test-model",
            "tool_calling_supported": True,
            "recommendation": "keep_shadow_only",
        },
    )
    _write_json(
        reports / "llm_semantic_router_promotion_decision.json",
        {"report_type": "llm_semantic_router_promotion_decision", "decision": "do_not_promote"},
    )
    _write_json(
        reports / "controller_rewrite_ablation.json",
        {
            "report_type": "controller_rewrite_ablation",
            "diagnostic_only": True,
            "packaged_runtime_changed": False,
            "summary": {"recommendation": "controller_no_rewrite_better", "best_variant_by_final_delta": "backend_safe"},
        },
    )
    _write_json(
        reports / "sdk_usage_audit.json",
        {
            "report_type": "sdk_usage_audit",
            "all_llm_calls_sdk_based": True,
            "summary": {"runtime_llm_direct_http_hits": 0, "runtime_hits": 2},
        },
    )
    _write_json(
        reports / "system_summary.json",
        {
            "report_type": "system_summary",
            "preferred_strategy": "SQL_FIRST_API_VERIFY",
            "packaged_strict_score": 0.6553,
            "hidden_style": {"passed": 48, "total": 48},
            "final_submission_ready": True,
            "live_adobe_api_readiness": {"live_success_count": 0},
        },
    )
    _write_json(
        reports / "accuracy_and_bottleneck_summary.json",
        {
            "report_type": "accuracy_and_bottleneck_summary",
            "starting_score": 0.6553,
            "answer_quality_bottleneck": {
                "answer_uses_dry_run_poorly": 5,
                "answer_shape_weak": 1,
            },
        },
    )
    _write_json(
        outputs / "eval_results_strict.json",
        {
            "examples": 2,
            "rows": [
                {
                    "query_id": "official_count",
                    "query": "How many active audiences are there?",
                    "strategy": "SQL_FIRST_API_VERIFY",
                    "final_score": 0.54,
                    "answer_score": 0.2,
                    "sql_score": 1.0,
                    "api_score": 0.9,
                    "tool_call_count": 2,
                    "estimated_tokens": 700,
                    "runtime": 0.01,
                    "final_answer": "Local SQL found active audiences; live API verification was unavailable.",
                    "trajectory": {
                        "route_type": "SQL_THEN_API",
                        "domain_type": "SEGMENT_AUDIENCE",
                        "answer_intent": "COUNT",
                        "llm_tool_calls": [],
                    },
                },
                {
                    "query_id": "official_llm",
                    "query": "List active segment names.",
                    "strategy": "GUIDED_REAL_LLM_TWO_TOOLS_BASELINE",
                    "system": "GUIDED_REAL_LLM_TWO_TOOLS_BASELINE",
                    "final_score": 0.6,
                    "answer_score": 0.35,
                    "sql_score": 1.0,
                    "api_score": 0.8,
                    "tool_call_count": 3,
                    "estimated_tokens": 1800,
                    "runtime": 0.08,
                    "llm_tool_calls": [
                        {"tool_name": "execute_sql", "arguments": {"sql": "SELECT name FROM dim_segment"}},
                        {"tool_name": "call_api", "arguments": {"method": "GET", "url": "/segments"}},
                    ],
                    "failure_reason": "dry_run_api_caveat_dominated_answer",
                },
            ],
            "summary": {"by_strategy": {"SQL_FIRST_API_VERIFY": {"avg_final_score": 0.6553}}},
        },
    )
    _write_json(
        reports / "generated_prompt_suite_local_diagnostic.json",
        {
            "report_type": "generated_prompt_suite_local_diagnostic",
            "diagnostic_only": True,
            "official_score_claim": False,
            "promotion_allowed": False,
            "executed_prompts": 3,
            "rows": [
                {
                    "prompt_id": "gen_count",
                    "prompt": "How many active audiences exist?",
                    "actual_route": "SQL_THEN_API",
                    "domain_type": "SEGMENT_AUDIENCE",
                    "answer_intent": "COUNT",
                    "dry_run_api_calls": 1,
                    "requires_live_api": False,
                    "missing_count_or_name_advisory": True,
                    "validation_failures": 0,
                    "runtime": 0.01,
                    "tokens": 600,
                    "diagnostic_only": True,
                },
                {
                    "prompt_id": "gen_api",
                    "prompt": "Inspect latest Adobe endpoint state.",
                    "actual_route": "API_ONLY",
                    "domain_type": "DATASET_SCHEMA",
                    "answer_intent": "STATUS",
                    "dry_run_api_calls": 1,
                    "requires_live_api": True,
                    "validation_failures": 0,
                    "runtime": 0.02,
                    "tokens": 650,
                    "diagnostic_only": True,
                },
            ],
        },
    )
    _write_json(
        reports / "comprehensive_failure_fix_decision.json",
        {
            "report_type": "comprehensive_failure_fix_decision",
            "decision": "wait_for_adobe_access",
            "runtime_change_applied": False,
        },
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_sdk_tool_calling_audit_reports_and_helpers(tiny_project):
    _seed_sdk_optimization_inputs(tiny_project.outputs_dir)

    payload = run_sdk_tool_calling_optimization_audit(tiny_project)
    reports = tiny_project.outputs_dir / "reports"

    for stem in [
        "sdk_tool_calling_optimization_preflight",
        "sdk_tool_call_surface_audit",
        "sdk_tool_call_decision_analysis",
        "sdk_tool_call_optimization_variants",
    ]:
        assert (reports / f"{stem}.json").exists()
        assert (reports / f"{stem}.md").exists()

    preflight = payload["preflight"]
    assert preflight["runtime_change_allowed"] is False
    assert preflight["packaged_strategy"] == "SQL_FIRST_API_VERIFY"
    assert preflight["sdk_direct_http_hits"] == 0
    assert "outputs/eval_results_strict.json" in preflight["protected_artifacts"]
    assert preflight["no_hardcoding_rule"] is True

    surface = payload["surface_audit"]
    assert {"openai_compatible", "anthropic", "all_providers"} <= set(surface["audited_areas"])
    classifications = {item["classification"] for item in surface["issues"]}
    assert classifications <= set(surface["allowed_classifications"])
    assert "parallel_calls_uncontrolled" in classifications

    decision = payload["decision_analysis"]
    assert decision["official_rows_analyzed"] >= 1
    assert decision["generated_prompts_analyzed"] >= 1
    assert decision["generated_prompts_diagnostic_only"] is True
    assert any(row["classification"] in decision["allowed_classifications"] for row in decision["rows"])

    variants = payload["variants"]
    assert [variant["variant_id"] for variant in variants["variants"]] == [
        "compact_tool_schema",
        "allowed_tools_by_prompt_type",
        "tool_choice_policy",
        "disable_parallel_tool_calls",
        "compact_tool_result_evidence_summary",
        "rewrite_gate_strict",
        "no_rewrite_when_backend_complete",
        "combined_safe_tool_policy",
    ]
    assert all(variant["promotion_status"] == "trial_only" for variant in variants["variants"])

    tool = {
        "type": "function",
        "function": {
            "name": "execute_sql",
            "description": "x" * 500,
            "parameters": {
                "type": "object",
                "properties": {"sql": {"type": "string", "description": "Read-only SQL"}},
                "required": ["sql"],
                "additionalProperties": False,
            },
        },
    }
    compact = compact_tool_schema(tool)
    assert compact["function"]["parameters"]["required"] == ["sql"]
    assert "sql" in compact["function"]["parameters"]["properties"]
    assert len(compact["function"]["description"]) < 180

    summary = compact_tool_result_evidence_summary(
        {
            "evidence_type": "sql",
            "row_count": 1,
            "rows": [{"count": 2, "name": "High Value", "status": "active", "updated_at": "2026-01-01"}],
            "api_state": "dry_run_unavailable",
            "extra": "noise",
        }
    )
    assert summary["evidence_type"] == "sql"
    assert summary["row_count"] == 1
    assert {"count", "name", "status", "updated_at"} <= set(summary["key_fields"])
    assert summary["api_state"] == "dry_run_unavailable"

    assert rewrite_gate_allows_rewrite(
        backend_answer="The count is 2.",
        verifier={"backend_complete": True, "unsupported_claim_count": 0},
        evidence={"sql": [{"count": 2}]},
    ) is False
    assert rewrite_gate_allows_rewrite(
        backend_answer="I found local evidence.",
        verifier={"backend_complete": False, "unsupported_claim_count": 0},
        evidence={"sql": [{"count": 2}]},
    ) is True


def test_sdk_tool_calling_trials_are_isolated_and_shadow_only(tiny_project):
    _seed_sdk_optimization_inputs(tiny_project.outputs_dir)
    eval_path = tiny_project.outputs_dir / "eval_results_strict.json"
    before_eval_hash = _sha256(eval_path)

    run_sdk_tool_calling_optimization_audit(tiny_project)
    payload = run_sdk_tool_calling_optimization_trials(tiny_project)

    reports = tiny_project.outputs_dir / "reports"
    assert (reports / "sdk_tool_calling_optimization_trials.json").exists()
    assert (reports / "sdk_tool_calling_fix_decision.json").exists()
    assert (tiny_project.outputs_dir / "sdk_tool_calling_optimization_trials" / "compact_tool_schema" / "trial_summary.json").exists()

    assert _sha256(eval_path) == before_eval_hash
    assert not (tiny_project.outputs_dir / "final_submission").exists()
    assert payload["fix_decision"]["runtime_change_applied"] is False
    assert payload["fix_decision"]["promotion_safe"] is False
    assert payload["fix_decision"]["final_submission_format_changed"] is False
    assert payload["fix_decision"]["direct_http_hits"] == 0
    assert all(row["isolated_output_only"] for row in payload["trials"]["variants"])
    assert all(row["final_submission_format_changed"] is False for row in payload["trials"]["variants"])
    assert all(not row.get("hardcoded_query_id_trigger") for row in payload["trials"]["variants"])
    assert payload["trials"]["generated_prompts_diagnostic_only"] is True

    combined = "\n".join(path.read_text(encoding="utf-8") for path in reports.glob("sdk_tool_call*.json"))
    forbidden = ["Authorization", "Bearer ", "client_secret", "access_token", "x-api-key", "abc***"]
    assert not any(term in combined for term in forbidden)


def test_consolidated_reports_link_sdk_tool_calling_outputs(tiny_project):
    _seed_sdk_optimization_inputs(tiny_project.outputs_dir)
    run_sdk_tool_calling_optimization_audit(tiny_project)
    run_sdk_tool_calling_optimization_trials(tiny_project)

    generate_consolidated_reports(tiny_project)
    index = json.loads((tiny_project.outputs_dir / "reports" / "report_index.json").read_text(encoding="utf-8"))
    system = json.loads((tiny_project.outputs_dir / "reports" / "system_summary.json").read_text(encoding="utf-8"))
    llm = json.loads((tiny_project.outputs_dir / "reports" / "llm_baseline_summary.json").read_text(encoding="utf-8"))

    assert "sdk_tool_calling_optimization" in index
    assert index["sdk_tool_calling_optimization"]["fix_decision_path"] == "outputs/reports/sdk_tool_calling_fix_decision.md"
    assert system["sdk_tool_calling_optimization"]["runtime_change_applied"] is False
    assert llm["sdk_tool_calling_optimization"]["runtime_change_applied"] is False
