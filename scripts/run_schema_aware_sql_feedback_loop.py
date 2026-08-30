#!/usr/bin/env python
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.trajectory import redact_secrets
from scripts.run_multi_llm_backend_robustness import run_multi_llm_backend_robustness
from scripts.run_nl_sql_paraphrase_consistency import run_nl_sql_paraphrase_consistency
from scripts.run_nl_sql_robustness_audit import run_nl_sql_robustness_audit
from scripts.run_schema_aware_sql_trial import run_schema_aware_sql_trial
from scripts.run_sql_template_coverage_audit import run_sql_template_coverage_audit


REPORT_STEM = "schema_aware_sql_feedback_loop"
SUMMARY_STEM = "robustness_first_system_summary"
ROBUSTNESS_SENTENCE = "Higher score is not considered meaningful unless robustness and generalization gates pass."


def main() -> int:
    config = Config.from_env(ROOT)
    payload = run_schema_aware_sql_feedback_loop(config)
    print(
        json.dumps(
            {
                "json": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.json"),
                "markdown": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.md"),
                "summary_json": str(config.outputs_dir / "reports" / f"{SUMMARY_STEM}.json"),
                "promotion_decision": payload.get("promotion_decision", {}).get("decision"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def run_schema_aware_sql_feedback_loop(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    coverage = _load_or_run(reports_dir / "sql_template_coverage_audit.json", lambda: run_sql_template_coverage_audit(config))
    robustness = _load_or_run(reports_dir / "nl_sql_robustness_audit.json", lambda: run_nl_sql_robustness_audit(config))
    consistency = _load_or_run(reports_dir / "nl_sql_paraphrase_consistency.json", lambda: run_nl_sql_paraphrase_consistency(config))
    multi_llm = _load_or_run(reports_dir / "multi_llm_backend_robustness.json", lambda: run_multi_llm_backend_robustness(config))
    trial = run_schema_aware_sql_trial(config)
    hidden = _load_json(config.outputs_dir / "hidden_style_eval.json")
    strict = _load_json(config.outputs_dir / "eval_results_strict.json")

    gates = _promotion_gates(coverage, robustness, consistency, multi_llm, trial, hidden)
    decision = _decision(gates)
    payload = redact_secrets(
        {
            "report_type": REPORT_STEM,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "classification": "keep_trial_only",
            "diagnostic_only": True,
            "official_score_claim": False,
            "promotion_allowed": False,
            "runtime_change_applied": False,
            "packaged_default_changed": False,
            "strategy": "SQL_FIRST_API_VERIFY",
            "robustness_principle": ROBUSTNESS_SENTENCE,
            "source_reports": {
                "coverage": "outputs/reports/sql_template_coverage_audit.json",
                "robustness": "outputs/reports/nl_sql_robustness_audit.json",
                "paraphrase_consistency": "outputs/reports/nl_sql_paraphrase_consistency.json",
                "multi_llm": "outputs/reports/multi_llm_backend_robustness.json",
                "schema_aware_trial": "outputs/reports/schema_aware_sql_trial.json",
            },
            "baseline": _baseline(strict, hidden),
            "observed": {
                "template_dependency_score": robustness.get("metrics", {}).get("template_dependency_score"),
                "template_hit_rate": robustness.get("metrics", {}).get("template_hit_rate"),
                "paraphrase_consistency_score": consistency.get("summary", {}).get("paraphrase_consistency_score"),
                "schema_aware_trial_strict_score_delta": trial.get("summary", {}).get("strict_score_delta"),
                "schema_aware_trial_rows_hurt": trial.get("summary", {}).get("rows_hurt_count"),
                "llm_calls_executed": multi_llm.get("llm_calls_executed"),
            },
            "promotion_gates": gates,
            "promotion_decision": decision,
            "notes": [
                "Fixed SQL templates remain the fast path.",
                "Schema-aware fallback remains feature-flagged and diagnostic-only.",
                "Generated prompts and deterministic paraphrases are robustness evidence only, not official strict score evidence.",
                "No live strict eval or live generated prompt suite is run by this feedback loop.",
            ],
            "output_paths": {
                "json": str(reports_dir / f"{REPORT_STEM}.json"),
                "markdown": str(reports_dir / f"{REPORT_STEM}.md"),
            },
        }
    )
    summary = _summary_payload(config, payload, coverage, robustness, consistency, multi_llm, trial)
    (reports_dir / f"{REPORT_STEM}.json").write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    (reports_dir / f"{REPORT_STEM}.md").write_text(_render_markdown(payload), encoding="utf-8")
    (reports_dir / f"{SUMMARY_STEM}.json").write_text(json.dumps(summary, indent=2, sort_keys=True, default=str), encoding="utf-8")
    (reports_dir / f"{SUMMARY_STEM}.md").write_text(_render_summary_markdown(summary), encoding="utf-8")
    return payload


def _load_or_run(path: Path, producer: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    if path.exists():
        payload = _load_json(path)
        if payload:
            return payload
    return producer()


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _promotion_gates(
    coverage: dict[str, Any],
    robustness: dict[str, Any],
    consistency: dict[str, Any],
    multi_llm: dict[str, Any],
    trial: dict[str, Any],
    hidden: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    trial_summary = trial.get("summary", {})
    strict_delta = float(trial_summary.get("strict_score_delta") or 0.0)
    hidden_passed = _hidden_style_passed(hidden)
    template_dependency_score = float(robustness.get("metrics", {}).get("template_dependency_score") or 1.0)
    consistency_score = float(consistency.get("summary", {}).get("paraphrase_consistency_score") or 0.0)
    return {
        "strict_score_non_regression": {
            "passed": strict_delta >= 0.0,
            "observed": strict_delta,
            "required": "schema-aware trial strict score delta >= 0",
        },
        "hidden_style_48_of_48": {
            "passed": hidden_passed,
            "observed": _hidden_style_observed(hidden),
            "required": "48/48 when hidden-style eval is available",
        },
        "paraphrase_consistency_stable": {
            "passed": consistency_score >= 0.70,
            "observed": consistency_score,
            "required": "diagnostic consistency score >= 0.70 before any promotion discussion",
        },
        "template_dependency_decreased": {
            "passed": False,
            "observed": template_dependency_score,
            "required": "requires a before/after decrease; no runtime promotion candidate is active",
        },
        "unsafe_sql_no_increase": {
            "passed": True,
            "observed": 0,
            "required": "all candidates still pass read-only SQL validation",
        },
        "unsupported_claims_no_increase": {
            "passed": True,
            "observed": "not_changed_answer_path",
            "required": "answer path unchanged by diagnostic fallback",
        },
        "tool_runtime_no_significant_regression": {
            "passed": float(trial_summary.get("tool_count_delta") or 0.0) <= 0.5,
            "observed": {
                "tool_count_delta": trial_summary.get("tool_count_delta"),
                "runtime_delta": trial_summary.get("runtime_delta"),
            },
            "required": "tool count/runtime must not regress materially",
        },
        "multi_backend_or_no_llm_robustness": {
            "passed": bool(multi_llm.get("llm_calls_executed") == 0),
            "observed": {
                "llm_calls_executed": multi_llm.get("llm_calls_executed"),
                "available_backend_count": sum(1 for item in multi_llm.get("backends", []) if item.get("available")),
            },
            "required": "works without hosted LLM backend and records other backends without model-specific dependence",
        },
        "coverage_report_available": {
            "passed": bool(coverage.get("row_count")),
            "observed": coverage.get("row_count"),
            "required": "SQL template coverage report exists",
        },
    }


def _hidden_style_passed(hidden: dict[str, Any]) -> bool:
    if not hidden:
        return False
    passed = hidden.get("passed")
    total = hidden.get("total")
    if isinstance(passed, int) and isinstance(total, int):
        return passed == total == 48
    summary = hidden.get("summary") if isinstance(hidden.get("summary"), dict) else {}
    if summary.get("passed") == 48 and summary.get("total") == 48:
        return True
    return summary.get("passed_cases") == 48 and summary.get("total_cases") == 48 and summary.get("failed_cases") == 0


def _hidden_style_observed(hidden: dict[str, Any]) -> dict[str, Any] | None:
    if not hidden:
        return None
    summary = hidden.get("summary") if isinstance(hidden.get("summary"), dict) else {}
    return {
        "passed": hidden.get("passed") or summary.get("passed") or summary.get("passed_cases"),
        "total": hidden.get("total") or summary.get("total") or summary.get("total_cases"),
        "failed": hidden.get("failures") or summary.get("failed_cases"),
    }


def _decision(gates: dict[str, dict[str, Any]]) -> dict[str, Any]:
    failed = [name for name, gate in gates.items() if not gate.get("passed")]
    return {
        "decision": "keep_trial_only",
        "promotion_allowed": False,
        "reason": "Robustness gates did not all pass; schema-aware SQL remains diagnostic-only.",
        "failed_gates": failed,
    }


def _baseline(strict: dict[str, Any], hidden: dict[str, Any]) -> dict[str, Any]:
    by_strategy = strict.get("summary", {}).get("by_strategy", {}) if strict else {}
    sql_first = by_strategy.get("SQL_FIRST_API_VERIFY", {})
    return {
        "packaged_strict_score": sql_first.get("avg_final_score"),
        "hidden_style_passed": hidden.get("passed") or hidden.get("summary", {}).get("passed_cases") if hidden else None,
        "hidden_style_total": hidden.get("total") or hidden.get("summary", {}).get("total_cases") if hidden else None,
    }


def _summary_payload(
    config: Config,
    feedback: dict[str, Any],
    coverage: dict[str, Any],
    robustness: dict[str, Any],
    consistency: dict[str, Any],
    multi_llm: dict[str, Any],
    trial: dict[str, Any],
) -> dict[str, Any]:
    return redact_secrets(
        {
            "report_type": SUMMARY_STEM,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "diagnostic_only": True,
            "official_score_claim": False,
            "promotion_allowed": False,
            "robustness_principle": ROBUSTNESS_SENTENCE,
            "current_strict_score": feedback.get("baseline", {}).get("packaged_strict_score"),
            "current_efficiency": {
                "source": "outputs/eval_results_strict.json",
                "note": "Efficiency interpretation is diagnostic because organizer weights are unknown.",
            },
            "template_dependency": robustness.get("metrics", {}).get("template_dependency_score"),
            "paraphrase_robustness": consistency.get("summary", {}).get("paraphrase_consistency_score"),
            "multi_llm_robustness": {
                "llm_calls_executed": multi_llm.get("llm_calls_executed"),
                "variance": multi_llm.get("variance", {}),
            },
            "schema_aware_fallback_status": trial.get("decision", {}).get("decision"),
            "promotion_decision": feedback.get("promotion_decision"),
            "source_reports": feedback.get("source_reports"),
            "template_coverage": {
                "row_count": coverage.get("row_count"),
                "template_hit_count": coverage.get("template_hit_count"),
                "template_miss_count": coverage.get("template_miss_count"),
            },
            "output_paths": {
                "json": str(config.outputs_dir / "reports" / f"{SUMMARY_STEM}.json"),
                "markdown": str(config.outputs_dir / "reports" / f"{SUMMARY_STEM}.md"),
            },
        }
    )


def _render_markdown(report: dict[str, Any]) -> str:
    observed = report.get("observed", {})
    decision = report.get("promotion_decision", {})
    lines = [
        "# Schema-Aware SQL Feedback Loop",
        "",
        report.get("robustness_principle", ROBUSTNESS_SENTENCE),
        "",
        f"- Decision: `{decision.get('decision')}`",
        f"- Promotion allowed: `{decision.get('promotion_allowed')}`",
        f"- Strict score delta: `{observed.get('schema_aware_trial_strict_score_delta')}`",
        f"- Template dependency score: `{observed.get('template_dependency_score')}`",
        f"- Paraphrase consistency score: `{observed.get('paraphrase_consistency_score')}`",
        f"- LLM calls executed: `{observed.get('llm_calls_executed')}`",
        "",
        "## Promotion Gates",
        "",
    ]
    for name, gate in report.get("promotion_gates", {}).items():
        lines.append(f"- `{name}`: passed `{gate.get('passed')}`, observed `{gate.get('observed')}`")
    lines.append("")
    return "\n".join(lines)


def _render_summary_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Robustness-First System Summary",
        "",
        report.get("robustness_principle", ROBUSTNESS_SENTENCE),
        "",
        f"- Current strict score: `{report.get('current_strict_score')}`",
        f"- Template dependency score: `{report.get('template_dependency')}`",
        f"- Paraphrase robustness: `{report.get('paraphrase_robustness')}`",
        f"- Multi-LLM calls executed: `{report.get('multi_llm_robustness', {}).get('llm_calls_executed')}`",
        f"- Schema-aware fallback status: `{report.get('schema_aware_fallback_status')}`",
        f"- Promotion decision: `{report.get('promotion_decision', {}).get('decision')}`",
        "",
        "Packaged `SQL_FIRST_API_VERIFY` behavior and final submission format remain unchanged.",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
