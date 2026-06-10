#!/usr/bin/env python
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from scripts.check_submission_ready import check_submission_ready
from scripts.robustness_improvement_common import (
    endpoint_matrix,
    generated_summary,
    git_branch,
    git_status_short,
    hidden_summary,
    load_json,
    now_iso,
    reports_dir,
    robustness_metrics,
    strict_metrics,
    write_report,
)


REPORT_STEM = "next_robustness_improvement_preflight"


def main() -> int:
    config = Config.from_env(ROOT)
    report = run_next_robustness_improvement_preflight(config)
    print(json.dumps({"report": REPORT_STEM, "recommendation": report["integrated_robustness_gate_recommendation"]}, indent=2))
    return 0


def run_next_robustness_improvement_preflight(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports = reports_dir(config)
    strict = strict_metrics(config)
    robustness = robustness_metrics(config)
    hidden = hidden_summary(config)
    check = _safe_check(config)
    generated = generated_summary(config)
    endpoint = endpoint_matrix(config)
    controller = load_json(reports / "controller_rewrite_policy_trial.json")
    llm_trace = load_json(reports / "llm_agent_trace_decomposition.json")
    multi = load_json(reports / "multi_llm_backend_robustness.json")
    efficiency = load_json(reports / "live_tool_efficiency_audit.json")
    gate = load_json(reports / "integrated_robustness_gate.json")
    missing = [
        path
        for path in [
            "outputs/reports/full_generated_prompt_suite_diagnostic.json",
            "outputs/reports/nl_sql_robustness_audit.json",
            "outputs/reports/multi_llm_backend_robustness.json",
            "outputs/reports/live_tool_efficiency_audit.json",
            "outputs/reports/controller_rewrite_policy_trial.json",
        ]
        if not (config.project_root / path).exists()
    ]
    recommendation = _recommendation(strict, hidden, check, endpoint, generated, robustness)
    payload: dict[str, Any] = {
        "report_type": REPORT_STEM,
        "generated_at": now_iso(),
        "classification": "diagnostic_only",
        "runtime_change_applied": False,
        "packaged_strategy": "SQL_FIRST_API_VERIFY",
        "git_status_short": git_status_short(),
        "current_branch": git_branch(),
        "current_strict_score": strict.get("avg_final_score"),
        "current_live_strict_score": strict.get("avg_final_score"),
        "hidden_style_result": hidden,
        "check_submission_ready_result": {
            "ok": check.get("ok"),
            "query_output_count": check.get("query_output_count"),
            "default_strategy_is_sql_first_api_verify": check.get("default_strategy_is_sql_first_api_verify"),
        },
        "endpoint_matrix": endpoint,
        "generated_prompt_suite_summary": generated,
        "nl_to_sql_robustness_metrics": {
            "template_hit_rate": robustness.get("template_hit_rate"),
            "template_miss_rate": robustness.get("template_miss_rate"),
            "template_dependency_score": robustness.get("template_dependency_score"),
            "paraphrase_consistency_score": robustness.get("paraphrase_consistency_score"),
            "fallback_success_rate": robustness.get("fallback_success_rate"),
        },
        "llm_controller_status": {
            "llm_trace_available": bool(llm_trace),
            "controller_trial_available": bool(controller),
            "controller_promotion_allowed": controller.get("promotion_allowed"),
            "multi_llm_backends_recorded": len(multi.get("backends", [])) if isinstance(multi.get("backends"), list) else 0,
            "llm_calls_executed": multi.get("llm_calls_executed"),
        },
        "tool_efficiency_status": efficiency.get("live_mode") or efficiency.get("summary") or {},
        "integrated_robustness_gate_recommendation": recommendation,
        "previous_gate_recommendation": gate.get("recommendation"),
        "missing_source_reports": missing,
        "next_phase_focus": [
            "answer_shape_weak cluster analysis",
            "route mismatch root-cause analysis",
            "API endpoint selection gap analysis",
            "live API evidence/token compression trial",
            "no-template SQL robustness diagnostic",
        ],
    }
    write_report(config, REPORT_STEM, payload, _render_md(payload))
    return payload


def _safe_check(config: Config) -> dict[str, Any]:
    try:
        return check_submission_ready(config)
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def _recommendation(
    strict: dict[str, Any],
    hidden: dict[str, Any],
    check: dict[str, Any],
    endpoint: dict[str, Any],
    generated: dict[str, Any],
    robustness: dict[str, Any],
) -> str:
    if not check.get("ok"):
        return "blocked_by_submission_readiness"
    if hidden.get("passed_cases") != 48 or hidden.get("failed_cases") not in {0, None}:
        return "blocked_by_hidden_style"
    outcomes = endpoint.get("outcome_counts") or {}
    if int(outcomes.get("endpoint_path_issue") or 0) or int(outcomes.get("api_error") or 0):
        return "blocked_by_endpoint_matrix"
    if int(generated.get("unsupported_claim_count") or 0):
        return "blocked_by_generated_unsupported_claims"
    if not isinstance(strict.get("avg_final_score"), (int, float)):
        return "blocked_by_missing_strict_score"
    if robustness.get("template_dependency_score") is None:
        return "diagnostics_required_before_promotion"
    return "diagnose_before_runtime_change"


def _render_md(report: dict[str, Any]) -> str:
    lines = [
        "# Next Robustness Improvement Preflight",
        "",
        "This preflight snapshots the current correctness, efficiency, generalization, live API, and packaging status before any robustness-first change.",
        "",
        f"- Current branch: `{report.get('current_branch')}`",
        f"- Current strict score: `{report.get('current_strict_score')}`",
        f"- Hidden-style: `{report.get('hidden_style_result')}`",
        f"- check_submission_ready: `{report.get('check_submission_ready_result')}`",
        f"- Endpoint matrix: `{report.get('endpoint_matrix')}`",
        f"- Generated prompt suite: `{report.get('generated_prompt_suite_summary')}`",
        f"- Robustness gate recommendation: `{report.get('integrated_robustness_gate_recommendation')}`",
        "",
        "## Next Focus",
        "",
    ]
    lines.extend(f"- {item}" for item in report.get("next_phase_focus", []))
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
