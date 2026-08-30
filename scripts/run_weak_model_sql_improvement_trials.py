#!/usr/bin/env python
from __future__ import annotations

import argparse
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
from scripts.load_local_env import load_local_env
from scripts.run_weak_model_lift_eval import run_weak_model_lift_eval

REPORT_STEM = "weak_model_sql_improvement_trials"
TRIAL_VARIANTS = [
    "weak_scaffold_api_recovery_v1",
    "weak_scaffold_sql_retrieval_v1",
    "weak_scaffold_sql_unit_tested_v1",
    "weak_scaffold_sql_retrieval_repair_v1",
    "weak_scaffold_balanced_sql_api_v2",
    "weak_scaffold_balanced_sql_api_answer_v3",
    "weak_scaffold_sql_lift_api_recovery_v3",
    "weak_scaffold_answer_fallback_v3",
]
REFERENCE = {
    "raw_weak_strict": 0.1596,
    "guided_weak_strict": 0.2244,
    "current_weak_scaffold_strict": 0.2873,
    "current_weak_scaffold_sql": 0.0600,
    "current_weak_scaffold_api": 0.6241,
    "current_weak_scaffold_answer": 0.2201,
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run weak-model SQL improvement trial variants.")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--full-public-dev", action="store_true")
    parser.add_argument("--stabilization-set", action="store_true")
    args = parser.parse_args()
    config = Config.from_env(ROOT)
    load_local_env(config.project_root)
    payload = run_weak_model_sql_improvement_trials(
        config,
        max_examples=None if args.full_public_dev else args.limit,
        stabilization_set=args.stabilization_set,
    )
    print(json.dumps({"json": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.json"), "summary": payload["summary"]}, indent=2, sort_keys=True))
    return 0


def run_weak_model_sql_improvement_trials(
    config: Config | None = None,
    *,
    max_examples: int | None = 5,
    stabilization_set: bool = False,
) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports = config.outputs_dir / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    variants = ["raw_weak_llm", "guided_weak_llm", *TRIAL_VARIANTS, "full_dashagent_current"]
    lift_payload = run_weak_model_lift_eval(
        config,
        max_examples=max_examples,
        variants=variants,
        stabilization_set=stabilization_set,
        execute_real=True,
    )
    trial_rows = [_trial_row(row) for row in lift_payload.get("rows", []) if row.get("mode") in TRIAL_VARIANTS]
    modes = _mode_summaries(lift_payload, trial_rows)
    strict_best = max(
        (mode for mode in modes if mode.get("mode") in TRIAL_VARIANTS),
        key=lambda item: float(item.get("strict_final_score") or -999),
        default={},
    )
    sql_best = max(
        (mode for mode in modes if mode.get("mode") in TRIAL_VARIANTS),
        key=lambda item: float(item.get("sql_score") or -999),
        default={},
    )
    summary = {
        "run_label": lift_payload.get("run_label"),
        "stabilization_set": stabilization_set,
        "reference": REFERENCE,
        "best_variant": strict_best.get("mode"),
        "best_strict": strict_best.get("strict_final_score"),
        "best_sql": strict_best.get("sql_score"),
        "best_api": strict_best.get("api_score"),
        "best_answer": strict_best.get("answer_score"),
        "best_sql_variant": sql_best.get("mode"),
        "best_sql_variant_strict": sql_best.get("strict_final_score"),
        "max_sql_score": sql_best.get("sql_score"),
        "best_sql_variant_api": sql_best.get("api_score"),
        "best_sql_variant_answer": sql_best.get("answer_score"),
        "sql_improved_over_current": _num(sql_best.get("sql_score")) > REFERENCE["current_weak_scaffold_sql"],
        "strict_nonregression_vs_current_scaffold": _num(strict_best.get("strict_final_score")) >= REFERENCE["current_weak_scaffold_strict"],
        "api_nonregression_vs_current_scaffold": _num(strict_best.get("api_score")) >= REFERENCE["current_weak_scaffold_api"],
        "answer_nonregression_vs_current_scaffold": _num(strict_best.get("answer_score")) >= REFERENCE["current_weak_scaffold_answer"],
        "best_sql_variant_strict_nonregression": _num(sql_best.get("strict_final_score")) >= REFERENCE["current_weak_scaffold_strict"],
        "best_sql_variant_api_nonregression": _num(sql_best.get("api_score")) >= REFERENCE["current_weak_scaffold_api"],
        "best_sql_variant_answer_nonregression": _num(sql_best.get("answer_score")) >= REFERENCE["current_weak_scaffold_answer"],
        "unsupported_claims_zero": all(int(mode.get("unsupported_claims") or 0) == 0 for mode in modes if mode.get("mode") in TRIAL_VARIANTS),
        "bounded_gate_passed": _bounded_gate(strict_best) or _bounded_gate(sql_best),
        "modes": modes,
    }
    report = redact_secrets(
        {
            "report_type": REPORT_STEM,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "diagnostic_only": True,
            "promotion_allowed": False,
            "packaged_runtime_changed": False,
            "packaged_default_strategy": "SQL_FIRST_API_VERIFY",
            "trial_classification": "diagnostic_only",
            "variants": TRIAL_VARIANTS,
            "summary": summary,
            "rows": trial_rows,
        }
    )
    (reports / f"{REPORT_STEM}.json").write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    (reports / f"{REPORT_STEM}.md").write_text(_render_md(report), encoding="utf-8")
    run_label = str(lift_payload.get("run_label") or "run")
    (reports / f"{REPORT_STEM}_{run_label}.json").write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    (reports / f"{REPORT_STEM}_{run_label}.md").write_text(_render_md(report), encoding="utf-8")
    return report


def _trial_row(row: dict[str, Any]) -> dict[str, Any]:
    trajectory = row.get("trajectory") if isinstance(row.get("trajectory"), dict) else {}
    steps = trajectory.get("steps") if isinstance(trajectory.get("steps"), list) else []
    compiler = next((step.get("compiled") for step in steps if step.get("kind") == "slot_compiler"), {})
    sql_step = next((step for step in steps if step.get("kind") == "sql_call"), {})
    sql_candidate = (compiler.get("sql_candidates") or [{}])[0] if isinstance(compiler, dict) and isinstance(compiler.get("sql_candidates"), list) else {}
    unit = sql_candidate.get("sql_unit_tests") if isinstance(sql_candidate.get("sql_unit_tests"), dict) else {}
    return {
        "query_id": row.get("query_id"),
        "prompt": row.get("prompt"),
        "mode": row.get("mode"),
        "strict_final_score": row.get("strict_final_score"),
        "sql_score": row.get("sql_score"),
        "api_score": row.get("api_score"),
        "answer_score": row.get("answer_score"),
        "unsupported_claim_count": row.get("unsupported_claim_count"),
        "compiled_sql": sql_step.get("sql") or sql_candidate.get("sql"),
        "sql_validation_ok": _validation_ok(sql_step.get("validation") or sql_candidate.get("validation")),
        "sql_execution_ok": isinstance(sql_step.get("result"), dict) and bool((sql_step.get("result") or {}).get("ok")),
        "sql_unit_test_passed": unit.get("passed"),
        "sql_unit_failed_tests": unit.get("failed_tests"),
        "sql_unit_semantic_score": unit.get("semantic_score"),
        "repair_attempts": sql_candidate.get("repair_attempts"),
        "repair_success": sql_candidate.get("repair_success"),
        "api_call_count": sum(1 for step in steps if step.get("kind") == "api_call"),
        "tool_calls": row.get("tool_calls"),
        "estimated_tokens": row.get("estimated_tokens"),
        "runtime": row.get("runtime"),
    }


def _mode_summaries(lift_payload: dict[str, Any], trial_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    modes = list((lift_payload.get("summary") or {}).get("modes") or [])
    by_mode: dict[str, list[dict[str, Any]]] = {}
    for row in trial_rows:
        by_mode.setdefault(str(row.get("mode")), []).append(row)
    for mode in modes:
        rows = by_mode.get(str(mode.get("mode")), [])
        if not rows:
            continue
        mode["sql_validation_pass_rate"] = _rate(rows, lambda row: row.get("compiled_sql"), lambda row: row.get("sql_validation_ok") is not False)
        mode["sql_execution_pass_rate"] = _rate(rows, lambda row: row.get("compiled_sql"), lambda row: row.get("sql_execution_ok") is True)
        mode["sql_unit_test_pass_rate"] = _rate(rows, lambda row: row.get("sql_unit_test_passed") is not None, lambda row: row.get("sql_unit_test_passed") is True)
        repair_rows = [row for row in rows if int(row.get("repair_attempts") or 0) > 0]
        mode["repair_success_rate"] = round(sum(1 for row in repair_rows if row.get("repair_success")) / len(repair_rows), 4) if repair_rows else None
    return modes


def _bounded_gate(best: dict[str, Any]) -> bool:
    if not best:
        return False
    return (
        _num(best.get("sql_score")) > REFERENCE["current_weak_scaffold_sql"]
        and _num(best.get("api_score")) >= REFERENCE["current_weak_scaffold_api"]
        and _num(best.get("answer_score")) >= REFERENCE["current_weak_scaffold_answer"]
        and int(best.get("unsupported_claims") or 0) == 0
    )


def _render_md(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Weak Model SQL Improvement Trials",
        "",
        "Diagnostic-only SQL correctness trials for the weak-model scaffold. Packaged `SQL_FIRST_API_VERIFY` is unchanged.",
        "",
        f"- Run label: `{summary.get('run_label')}`",
        f"- Best strict variant: `{summary.get('best_variant')}`",
        f"- Best strict/API/SQL/answer: `{summary.get('best_strict')}` / `{summary.get('best_api')}` / `{summary.get('best_sql')}` / `{summary.get('best_answer')}`",
        f"- Best SQL variant: `{summary.get('best_sql_variant')}`",
        f"- Best SQL variant strict/API/SQL/answer: `{summary.get('best_sql_variant_strict')}` / `{summary.get('best_sql_variant_api')}` / `{summary.get('max_sql_score')}` / `{summary.get('best_sql_variant_answer')}`",
        f"- SQL improved over current weak scaffold: `{summary.get('sql_improved_over_current')}`",
        f"- API non-regression: `{summary.get('api_nonregression_vs_current_scaffold')}`",
        f"- Answer non-regression: `{summary.get('answer_nonregression_vs_current_scaffold')}`",
        f"- Unsupported claims zero: `{summary.get('unsupported_claims_zero')}`",
        f"- Bounded gate passed: `{summary.get('bounded_gate_passed')}`",
        "",
        "| Mode | Rows | Strict | SQL | API | Answer | SQL unit pass | Repair success | Unsupported |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for mode in summary.get("modes") or []:
        if mode.get("mode") not in TRIAL_VARIANTS:
            continue
        lines.append(
            f"| `{mode.get('mode')}` | {mode.get('rows', 0)} | {mode.get('strict_final_score', 'n/a')} | {mode.get('sql_score', 'n/a')} | {mode.get('api_score', 'n/a')} | {mode.get('answer_score', 'n/a')} | {mode.get('sql_unit_test_pass_rate', 'n/a')} | {mode.get('repair_success_rate', 'n/a')} | {mode.get('unsupported_claims', 'n/a')} |"
        )
    return "\n".join(lines) + "\n"


def _validation_ok(validation: Any) -> bool | None:
    if not isinstance(validation, dict):
        return None
    if "ok" in validation:
        return bool(validation.get("ok"))
    if "valid" in validation:
        return bool(validation.get("valid"))
    return None


def _rate(rows: list[dict[str, Any]], denominator_predicate: Any, numerator_predicate: Any) -> float | None:
    denominator = [row for row in rows if denominator_predicate(row)]
    if not denominator:
        return None
    return round(sum(1 for row in denominator if numerator_predicate(row)) / len(denominator), 4)


def _num(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


if __name__ == "__main__":
    raise SystemExit(main())
