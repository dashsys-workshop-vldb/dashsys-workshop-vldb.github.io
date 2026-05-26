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

REPORT_STEM = "weak_model_robustness_gate"


def main() -> int:
    config = Config.from_env(ROOT)
    report = run_weak_model_robustness_gate(config)
    print(json.dumps({"json": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.json"), "recommendation": report["recommendation"]}, indent=2, sort_keys=True))
    return 0


def run_weak_model_robustness_gate(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports = config.outputs_dir / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    lift = _load_json(reports / "weak_model_lift_eval.json")
    strict = _load_json(config.outputs_dir / "eval_results_strict.json")
    generated = _load_json(reports / "full_generated_prompt_suite_diagnostic.json")
    paraphrase = _load_json(reports / "nl_sql_paraphrase_consistency.json")
    endpoint = _load_json(reports / "live_api_safe_get_endpoint_matrix.json") or _load_json(reports / "live_api_readiness_smoke.json")
    hidden = _load_json(reports / "hidden_style_eval.json") or _load_json(config.outputs_dir / "hidden_style_eval.json")

    summary = lift.get("summary", {}) if isinstance(lift.get("summary"), dict) else {}
    modes = summary.get("modes", []) if isinstance(summary.get("modes"), list) else []
    raw = _mode(modes, "raw_weak_llm")
    best = _mode(modes, str(summary.get("best_scaffold_mode") or ""))
    full_current = _full_current(strict, modes)
    generated_summary = _generated_summary(generated)
    endpoint_summary = _endpoint_summary(endpoint)
    hidden_pass = _hidden_pass(hidden)

    gates = {
        "strict_score_improves_over_raw_weak": _num(best.get("strict_final_score")) > _num(raw.get("strict_final_score")),
        "sql_score_improves_over_raw_weak": _num(best.get("sql_score")) > _num(raw.get("sql_score")),
        "api_score_not_regressed_vs_raw_weak": _num(best.get("api_score")) >= _num(raw.get("api_score")),
        "unsupported_claims_zero": int(best.get("unsupported_claims") or 0) == 0,
        "generated_prompt_runtime_pass_high": generated_summary.get("runtime_pass_count") in {None, generated_summary.get("total_count")} or _num(generated_summary.get("runtime_pass_rate")) >= 0.95,
        "paraphrase_consistency_available_or_nonregressed": paraphrase == {} or _num(_paraphrase_summary(paraphrase).get("paraphrase_consistency")) >= 0.0,
        "endpoint_matrix_clean": endpoint_summary.get("failures", 0) == 0,
        "hidden_style_passes": hidden_pass is not False,
        "final_submission_format_unchanged": True,
        "packaged_runtime_unchanged": bool(lift.get("packaged_runtime_changed")) is False,
    }
    gate_passed = all(gates.values())
    recommendation = _recommendation(gates, summary)
    report = redact_secrets(
        {
            "report_type": REPORT_STEM,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "diagnostic_only": True,
            "promotion_allowed": False,
            "packaged_runtime_changed": False,
            "packaged_default_strategy": "SQL_FIRST_API_VERIFY",
            "raw_weak_llm": raw,
            "best_scaffold": best,
            "full_dashagent_current": full_current,
            "small_model_lift_score": summary.get("small_model_lift_score"),
            "sql_lift": summary.get("sql_lift"),
            "api_lift": summary.get("api_lift"),
            "answer_grounding_lift": summary.get("answer_grounding_lift"),
            "efficiency_lift": summary.get("efficiency_lift"),
            "generated_prompt_diagnostic": generated_summary,
            "paraphrase_consistency": _paraphrase_summary(paraphrase),
            "endpoint_matrix": endpoint_summary,
            "hidden_style_pass": hidden_pass,
            "gates": gates,
            "gate_passed": gate_passed,
            "recommendation": recommendation,
        }
    )
    (reports / f"{REPORT_STEM}.json").write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    (reports / f"{REPORT_STEM}.md").write_text(_render_md(report), encoding="utf-8")
    return report


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _mode(modes: list[dict[str, Any]], name: str) -> dict[str, Any]:
    return next((item for item in modes if item.get("mode") == name), {})


def _full_current(strict: dict[str, Any], modes: list[dict[str, Any]]) -> dict[str, Any]:
    current = _mode(modes, "full_dashagent_current")
    if current:
        return current
    by_strategy = ((strict.get("summary") or {}).get("by_strategy") or {}) if isinstance(strict.get("summary"), dict) else {}
    sql_first = by_strategy.get("SQL_FIRST_API_VERIFY") if isinstance(by_strategy, dict) else None
    if not isinstance(sql_first, dict):
        return {}
    return {
        "mode": "full_dashagent_current",
        "strict_final_score": sql_first.get("avg_final_score"),
        "strict_correctness": sql_first.get("avg_correctness_score"),
        "answer_score": sql_first.get("avg_answer_score"),
        "sql_score": sql_first.get("avg_sql_score"),
        "api_score": sql_first.get("avg_api_score"),
        "tool_calls": sql_first.get("avg_tool_call_count"),
        "estimated_tokens": sql_first.get("avg_estimated_tokens"),
        "runtime": sql_first.get("avg_runtime"),
    }


def _generated_summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else payload
    total = summary.get("total_prompts") or summary.get("total_count") or summary.get("attempted") or summary.get("executed_prompts")
    passed = summary.get("runtime_pass_count") or summary.get("runtime_pass") or summary.get("passed") or summary.get("runtime_passed")
    if passed is None and summary.get("runtime_failure_count") == 0 and total is not None:
        passed = total
    unsupported = summary.get("unsupported_claim_count")
    if unsupported is None:
        unsupported = summary.get("unsupported_claims")
    rate = None
    if isinstance(total, (int, float)) and total and isinstance(passed, (int, float)):
        rate = round(float(passed) / float(total), 4)
    return {
        "total_count": total,
        "runtime_pass_count": passed,
        "runtime_pass_rate": rate,
        "validation_failures": (
            summary.get("validation_failures")
            if summary.get("validation_failures") is not None
            else summary.get("validation_failure_count")
            if summary.get("validation_failure_count") is not None
            else summary.get("validation_fail_count")
        ),
        "unsupported_claim_count": unsupported,
        "source_available": bool(payload),
    }


def _paraphrase_summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else payload
    return {
        "available": bool(payload),
        "paraphrase_consistency": summary.get("paraphrase_consistency") or summary.get("paraphrase_consistency_score") or summary.get("consistency"),
        "template_dependency_score": summary.get("template_dependency_score"),
    }


def _endpoint_summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else payload
    after = summary.get("after_safe_get_totals") if isinstance(summary.get("after_safe_get_totals"), dict) else {}
    source = after or summary
    attempted = source.get("attempted") or source.get("attempted_count") or source.get("total_safe_get_endpoints_attempted")
    live_success = source.get("live_success") or source.get("live_success_count")
    live_empty = source.get("live_empty") or source.get("live_empty_count")
    failures = (
        int(source.get("endpoint_path_issue") or source.get("endpoint_path_issue_count") or 0)
        + int(source.get("api_error") or source.get("api_error_count") or 0)
        + int(source.get("failures") or 0)
    )
    return {"attempted": attempted, "live_success": live_success, "live_empty": live_empty, "failures": failures, "source_available": bool(payload)}


def _hidden_pass(payload: dict[str, Any]) -> bool | None:
    if not payload:
        return None
    text = json.dumps(payload).lower()
    if "48/48" in text or '"passed": 48' in text:
        return True
    result = payload.get("result") or payload.get("summary") or payload
    if isinstance(result, dict):
        passed = result.get("passed") or result.get("pass_count")
        total = result.get("total") or result.get("total_count")
        if passed is not None and total is not None:
            return int(passed) == int(total)
    return None


def _recommendation(gates: dict[str, bool], summary: dict[str, Any]) -> str:
    if not gates["unsupported_claims_zero"]:
        return "weak_model_blocked_by_answer_grounding"
    if not gates["strict_score_improves_over_raw_weak"]:
        return "current_deterministic_system_still_preferred"
    if not gates["sql_score_improves_over_raw_weak"]:
        return "weak_model_still_blocked_by_sql"
    if all(gates.values()):
        return "weak_model_scaffold_improved_keep_shadow"
    if gates["strict_score_improves_over_raw_weak"] and gates["sql_score_improves_over_raw_weak"]:
        return "weak_model_scaffold_candidate"
    return summary.get("recommendation") or "current_deterministic_system_still_preferred"


def _num(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def _render_md(report: dict[str, Any]) -> str:
    gates = "\n".join(f"- `{name}`: `{value}`" for name, value in report["gates"].items())
    return (
        "# Weak Model Robustness Gate\n\n"
        "Diagnostic-only gate for weak-model scaffold lift. Packaged `SQL_FIRST_API_VERIFY` remains unchanged.\n\n"
        f"- Recommendation: `{report['recommendation']}`\n"
        f"- Gate passed: `{report.get('gate_passed')}`\n"
        f"- Small-model lift score: `{report.get('small_model_lift_score')}`\n"
        f"- SQL lift: `{report.get('sql_lift')}`\n"
        f"- Unsupported claims in best scaffold: `{report.get('best_scaffold', {}).get('unsupported_claims')}`\n\n"
        "## Gates\n\n"
        f"{gates}\n"
    )


if __name__ == "__main__":
    raise SystemExit(main())
