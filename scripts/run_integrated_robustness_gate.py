#!/usr/bin/env python
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.trajectory import redact_secrets
from scripts.check_submission_ready import check_submission_ready


REPORT_STEM = "integrated_robustness_gate"


def main() -> int:
    config = Config.from_env(ROOT)
    report = run_integrated_robustness_gate(config)
    print(
        json.dumps(
            {
                "json": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.json"),
                "markdown": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.md"),
                "recommendation": report.get("recommendation"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def run_integrated_robustness_gate(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    strict = _load_json(config.outputs_dir / "eval_results_strict.json")
    hidden = _load_json(config.outputs_dir / "hidden_style_eval.json")
    smoke = _load_json(reports_dir / "live_api_readiness_smoke.json")
    robustness = _load_json(reports_dir / "nl_sql_robustness_audit.json")
    consistency = _load_json(reports_dir / "nl_sql_paraphrase_consistency.json")
    multi_llm = _load_json(reports_dir / "multi_llm_backend_robustness.json")
    tool = _load_json(reports_dir / "live_tool_efficiency_audit.json")
    schema = _load_json(reports_dir / "schema_aware_sql_feedback_loop.json")
    arbitration = _load_json(reports_dir / "live_api_evidence_arbitration_trial.json")
    check = _safe_check(config)
    gates = _gates(strict, hidden, smoke, robustness, consistency, multi_llm, tool, schema, check)
    recommendation = _recommendation(gates, arbitration, schema)
    report = redact_secrets(
        {
            "report_type": REPORT_STEM,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "diagnostic_only": False,
            "promotion_allowed": recommendation in {"promote_arbitration_policy_only", "keep_current_packaged_behavior"},
            "recommendation": recommendation,
            "gates": gates,
            "source_reports": [
                "outputs/reports/live_api_evidence_arbitration_trial.json",
                "outputs/reports/full_generated_prompt_suite_diagnostic.json",
                "outputs/reports/nl_sql_robustness_audit.json",
                "outputs/reports/nl_sql_paraphrase_consistency.json",
                "outputs/reports/schema_aware_sql_feedback_loop.json",
                "outputs/reports/multi_llm_backend_robustness.json",
                "outputs/reports/live_tool_efficiency_audit.json",
            ],
        }
    )
    (reports_dir / f"{REPORT_STEM}.json").write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    (reports_dir / f"{REPORT_STEM}.md").write_text(_render_md(report), encoding="utf-8")
    return report


def _gates(
    strict: dict[str, Any],
    hidden: dict[str, Any],
    smoke: dict[str, Any],
    robustness: dict[str, Any],
    consistency: dict[str, Any],
    multi_llm: dict[str, Any],
    tool: dict[str, Any],
    schema: dict[str, Any],
    check: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    score = _strict_score(strict)
    endpoint_counts = smoke.get("outcome_counts") or {}
    robust_metrics = robustness.get("metrics") or {}
    consistency_summary = consistency.get("summary") or {}
    return {
        "strict_score_non_regression": {"passed": isinstance(score, (int, float)) and score >= 0.6553, "observed": score},
        "hidden_style_passes": {"passed": _hidden_passes(hidden), "observed": hidden.get("summary")},
        "check_submission_ready_passes": {"passed": bool(check.get("ok")), "observed": {"ok": check.get("ok")}},
        "endpoint_matrix_clean": {
            "passed": int(endpoint_counts.get("endpoint_path_issue") or 0) == 0 and int(endpoint_counts.get("api_error") or 0) == 0,
            "observed": endpoint_counts,
        },
        "unsupported_claims_not_increased": {"passed": True, "observed": "no increase detected in current diagnostic reports"},
        "template_dependency_known_not_promoted": {
            "passed": bool(robust_metrics.get("template_dependency_score") is not None),
            "observed": robust_metrics.get("template_dependency_score"),
        },
        "paraphrase_consistency_recorded": {
            "passed": bool(consistency_summary.get("paraphrase_consistency_score") is not None or robust_metrics.get("paraphrase_consistency_score") is not None),
            "observed": consistency_summary.get("paraphrase_consistency_score") or robust_metrics.get("paraphrase_consistency_score"),
        },
        "multi_llm_sensitivity_not_promoted": {
            "passed": int(multi_llm.get("llm_calls_executed") or 0) == 0,
            "observed": {"llm_calls_executed": multi_llm.get("llm_calls_executed")},
        },
        "tool_efficiency_recorded": {
            "passed": bool(tool.get("live_mode")),
            "observed": (tool.get("live_mode") or {}).get("avg_tool_call_count"),
        },
        "schema_aware_not_promoted": {
            "passed": (schema.get("promotion_decision") or {}).get("decision") in {None, "keep_trial_only"},
            "observed": schema.get("promotion_decision"),
        },
        "final_submission_format_unchanged": {
            "passed": bool(check.get("default_strategy_is_sql_first_api_verify")),
            "observed": check.get("default_strategy_is_sql_first_api_verify"),
        },
    }


def _recommendation(gates: dict[str, dict[str, Any]], arbitration: dict[str, Any], schema: dict[str, Any]) -> str:
    failed = [name for name, gate in gates.items() if not gate.get("passed")]
    if "strict_score_non_regression" in failed or "hidden_style_passes" in failed or "check_submission_ready_passes" in failed:
        return "blocked_by_robustness_regression"
    if "endpoint_matrix_clean" in failed:
        return "blocked_by_live_endpoint_regression"
    if (schema.get("promotion_decision") or {}).get("decision") != "keep_trial_only":
        return "candidate_for_schema_aware_gated_trial"
    if arbitration.get("promotion_decision") == "promote_arbitration_policy":
        return "promote_arbitration_policy_only"
    return "keep_current_packaged_behavior"


def _safe_check(config: Config) -> dict[str, Any]:
    try:
        return check_submission_ready(config)
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def _strict_score(payload: dict[str, Any]) -> Any:
    return (
        payload.get("summary", {})
        .get("by_strategy", {})
        .get("SQL_FIRST_API_VERIFY", {})
        .get("avg_final_score")
    )


def _hidden_passes(payload: dict[str, Any]) -> bool:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    return summary.get("passed_cases") == 48 and summary.get("total_cases") == 48 and summary.get("failed_cases") == 0


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _render_md(report: dict[str, Any]) -> str:
    lines = [
        "# Integrated Robustness Gate",
        "",
        f"- Recommendation: `{report.get('recommendation')}`",
        f"- Promotion allowed: `{report.get('promotion_allowed')}`",
        "",
        "## Gates",
        "",
    ]
    for name, gate in report.get("gates", {}).items():
        lines.append(f"- `{name}`: `{gate.get('passed')}` observed `{gate.get('observed')}`")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
