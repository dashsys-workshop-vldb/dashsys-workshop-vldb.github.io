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
from dashagent.weak_model_harness_assertions import evaluate_harness_assertions, write_assertion_catalog
from dashagent.weak_model_harness_state import state_machine_as_dicts
from scripts.load_local_env import load_local_env
from scripts.run_weak_model_lift_eval import run_weak_model_lift_eval

REPORT_STEM = "weak_harness_engineering_eval"
DESIGN_STEM = "harness_engineering_design_map"
ANSWER_GROUNDING_STEM = "weak_model_answer_grounding_harness"
HARNESS_VARIANTS = [
    "weak_harness_slots_only_v1",
    "weak_harness_schema_retrieval_v1",
    "weak_harness_unit_tested_sql_v1",
    "weak_harness_repair_loop_v1",
    "weak_harness_balanced_sql_api_answer_v1",
    "weak_harness_full_v1",
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
    parser = argparse.ArgumentParser(description="Run shadow-only weak harness engineering variants.")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--variant", action="append", choices=HARNESS_VARIANTS)
    parser.add_argument("--full-public-dev", action="store_true")
    parser.add_argument("--stabilization-set", action="store_true")
    args = parser.parse_args()
    config = Config.from_env(ROOT)
    load_local_env(config.project_root)
    payload = run_weak_harness_engineering_eval(
        config,
        max_examples=None if args.full_public_dev else args.limit,
        stabilization_set=args.stabilization_set,
        variants=args.variant,
    )
    print(json.dumps({"json": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.json"), "summary": payload["summary"]}, indent=2, sort_keys=True))
    return 0


def run_weak_harness_engineering_eval(
    config: Config | None = None,
    *,
    max_examples: int | None = 5,
    stabilization_set: bool = False,
    variants: list[str] | None = None,
) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports = config.outputs_dir / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    _write_design_map(reports)
    write_assertion_catalog(reports)
    selected_harness_variants = variants or HARNESS_VARIANTS
    eval_variants = ["raw_weak_llm", "guided_weak_llm", *selected_harness_variants, "full_dashagent_current"]
    lift = run_weak_model_lift_eval(
        config,
        max_examples=max_examples,
        variants=eval_variants,
        stabilization_set=stabilization_set,
        execute_real=True,
    )
    harness_rows = [_harness_row(row) for row in lift.get("rows", []) if row.get("mode") in HARNESS_VARIANTS]
    modes = _mode_summaries(lift, harness_rows)
    best = max((mode for mode in modes if mode.get("mode") in HARNESS_VARIANTS and isinstance(mode.get("strict_final_score"), (int, float))), key=lambda item: float(item.get("strict_final_score") or -999), default={})
    best_sql = max((mode for mode in modes if mode.get("mode") in HARNESS_VARIANTS and isinstance(mode.get("sql_score"), (int, float))), key=lambda item: float(item.get("sql_score") or -999), default={})
    summary = {
        "run_label": lift.get("run_label"),
        "reference": REFERENCE,
        "best_variant": best.get("mode"),
        "best_strict": best.get("strict_final_score"),
        "best_sql": best.get("sql_score"),
        "best_api": best.get("api_score"),
        "best_answer": best.get("answer_score"),
        "best_sql_variant": best_sql.get("mode"),
        "max_sql_score": best_sql.get("sql_score"),
        "best_sql_variant_strict": best_sql.get("strict_final_score"),
        "unsupported_claims_zero": all(int(mode.get("unsupported_claims") or 0) == 0 for mode in modes if mode.get("mode") in HARNESS_VARIANTS),
        "sql_improved_over_previous_weak_scaffold": _num(best_sql.get("sql_score")) > REFERENCE["current_weak_scaffold_sql"],
        "api_nonregression": _num(best.get("api_score")) >= REFERENCE["current_weak_scaffold_api"],
        "answer_nonregression": _num(best.get("answer_score")) >= REFERENCE["current_weak_scaffold_answer"],
        "strict_improved_over_previous_weak_scaffold": _num(best.get("strict_final_score")) > REFERENCE["current_weak_scaffold_strict"],
        "bounded_gate_passed": _bounded_gate(best) or _bounded_gate(best_sql),
        "recommendation": _recommendation(best, best_sql),
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
            "state_machine": state_machine_as_dicts(),
            "variants": selected_harness_variants,
            "summary": summary,
            "rows": harness_rows,
        }
    )
    run_label = str(lift.get("run_label") or "run")
    for stem in (REPORT_STEM, f"{REPORT_STEM}_{run_label}"):
        (reports / f"{stem}.json").write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
        (reports / f"{stem}.md").write_text(_render_md(report), encoding="utf-8")
    _write_answer_grounding_report(reports, report)
    return report


def _harness_row(row: dict[str, Any]) -> dict[str, Any]:
    trajectory = row.get("trajectory") if isinstance(row.get("trajectory"), dict) else {}
    steps = trajectory.get("steps") if isinstance(trajectory.get("steps"), list) else []
    compiler = next((step.get("compiled") for step in steps if step.get("kind") == "slot_compiler"), {})
    sql_step = next((step for step in steps if step.get("kind") == "sql_call"), {})
    final = next((step for step in steps if step.get("kind") == "final_answer"), {})
    grounding = final.get("grounding") if isinstance(final.get("grounding"), dict) else {}
    sql_candidate = (compiler.get("sql_candidates") or [{}])[0] if isinstance(compiler, dict) and isinstance(compiler.get("sql_candidates"), list) else {}
    unit = sql_candidate.get("sql_unit_tests") if isinstance(sql_candidate.get("sql_unit_tests"), dict) else {}
    assertion_trace = {
        "prompt": row.get("prompt"),
        "answer": row.get("trajectory", {}).get("final_answer"),
        "semantic_slots": (compiler.get("slots") if isinstance(compiler, dict) else {}),
        "tool_calls": [step for step in steps if step.get("kind") in {"sql_call", "api_call"}],
        "sql_candidate": sql_candidate,
        "schema_context": compiler.get("schema_context") if isinstance(compiler, dict) else {},
        "sql_unit_tests": unit,
        "sql_validation": sql_candidate.get("validation") if isinstance(sql_candidate, dict) else {},
        "sql_executed": bool(sql_step),
        "sql_evidence": grounding.get("sql_evidence") if isinstance(grounding, dict) else {},
        "api_evidence": grounding.get("api_evidence") if isinstance(grounding, dict) else {},
        "answer_used_sql": grounding.get("answer_used_sql") if isinstance(grounding, dict) else False,
        "answer_used_api": grounding.get("answer_used_api") if isinstance(grounding, dict) else False,
        "unsupported_claim_count": row.get("unsupported_claim_count"),
    }
    assertions = evaluate_harness_assertions(assertion_trace).to_dict()
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
        "sql_unit_test_passed": unit.get("passed"),
        "sql_unit_failed_tests": unit.get("failed_tests"),
        "sql_unit_critical_failures": unit.get("critical_failures"),
        "sql_unit_semantic_score": unit.get("semantic_score"),
        "sql_validation_ok": _validation_ok(sql_step.get("validation") or sql_candidate.get("validation")),
        "sql_execution_ok": isinstance(sql_step.get("result"), dict) and bool((sql_step.get("result") or {}).get("ok")),
        "repair_attempts": sql_candidate.get("repair_attempts"),
        "repair_success": sql_candidate.get("repair_success"),
        "answer_used_sql": grounding.get("answer_used_sql"),
        "answer_used_api": grounding.get("answer_used_api"),
        "fallback_used": grounding.get("fallback_used"),
        "harness_assertions": assertions,
        "tool_calls": row.get("tool_calls"),
        "estimated_tokens": row.get("estimated_tokens"),
        "runtime": row.get("runtime"),
    }


def _mode_summaries(lift: dict[str, Any], harness_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    modes = list((lift.get("summary") or {}).get("modes") or [])
    by_mode: dict[str, list[dict[str, Any]]] = {}
    for row in harness_rows:
        by_mode.setdefault(str(row.get("mode")), []).append(row)
    for mode in modes:
        rows = by_mode.get(str(mode.get("mode")), [])
        if not rows:
            continue
        mode["sql_unit_test_pass_rate"] = _rate(rows, lambda row: row.get("sql_unit_test_passed") is not None, lambda row: row.get("sql_unit_test_passed") is True)
        mode["sql_validation_pass_rate"] = _rate(rows, lambda row: row.get("compiled_sql"), lambda row: row.get("sql_validation_ok") is not False)
        mode["sql_execution_pass_rate"] = _rate(rows, lambda row: row.get("compiled_sql"), lambda row: row.get("sql_execution_ok") is True)
        repair_rows = [row for row in rows if int(row.get("repair_attempts") or 0) > 0]
        mode["repair_success_rate"] = round(sum(1 for row in repair_rows if row.get("repair_success")) / len(repair_rows), 4) if repair_rows else None
        mode["answer_grounding_rate"] = _rate(rows, lambda row: row.get("answer_used_sql") is not None or row.get("answer_used_api") is not None, lambda row: bool(row.get("answer_used_sql") or row.get("answer_used_api")))
        mode["harness_assertion_pass_rate"] = _rate(rows, lambda row: True, lambda row: not (row.get("harness_assertions") or {}).get("failed_assertions"))
    return modes


def _write_design_map(reports: Path) -> None:
    patterns = [
        ("Vanna-style retrieval", "Schema, column role, value-link, join retrieval and compact observability.", "dashagent/weak_sql_schema_retriever.py", "Improve ranking confidence and value sampling.", "medium", "low", "low", "low"),
        ("SQLCoder-style prompt structure", "Structured slots and SQL plans before compilation; no free-form SQL first.", "dashagent/weak_model_output_schemas.py", "Use schemas for hosted weak-model calls.", "medium", "neutral", "low", "low"),
        ("CHESS-style SQL unit testing", "Unit tests before SQL execution plus candidate ranking.", "dashagent/weak_sql_unit_tester.py", "Broaden unit tests for group-by and relationship cases.", "medium", "low", "low", "low"),
        ("DIN-SQL/DEA-SQL", "Decompose into slots, schema linking, skeleton selection, and repair.", "dashagent/semantic_slot_compiler.py", "Add stronger decomposition traces.", "medium", "neutral", "low", "low"),
        ("SQLFixAgent", "Repair slots from validator/unit-test feedback instead of raw SQL.", "dashagent/weak_sql_repair_loop.py", "Integrate hosted weak-model retry when available.", "medium", "low", "medium", "low"),
        ("Guardrails/Instructor/Outlines", "Typed JSON schema validation and retry prompts.", "dashagent/weak_model_output_schemas.py", "Use strict schemas in all weak-model calls.", "medium", "low", "low", "low"),
        ("TraceSafe/PROMPTEVALS", "Trajectory-level assertions for tools, evidence, and final claims.", "dashagent/weak_model_harness_assertions.py", "Feed assertion failures back into repair loops.", "medium", "low", "low", "low"),
    ]
    payload = {
        "report_type": DESIGN_STEM,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "diagnostic_only": True,
        "packaged_runtime_changed": False,
        "patterns": [
            {
                "source_pattern": name,
                "implemented_now": True,
                "current_module": module,
                "problem_solved": problem,
                "gap": gap,
                "proposed_fix": gap,
                "expected_correctness_impact": correctness,
                "expected_efficiency_impact": efficiency,
                "robustness_risk": robustness,
                "generalization_risk": generalization,
            }
            for name, problem, module, gap, correctness, efficiency, robustness, generalization in patterns
        ],
    }
    (reports / f"{DESIGN_STEM}.json").write_text(json.dumps(redact_secrets(payload), indent=2, sort_keys=True), encoding="utf-8")
    lines = ["# Harness Engineering Design Map", "", "Shadow-only mapping of external harness patterns to DashAgent weak-model modules.", "", "| Pattern | Module | Gap | Correctness | Efficiency | Risk |", "| --- | --- | --- | --- | --- | --- |"]
    for item in payload["patterns"]:
        lines.append(f"| {item['source_pattern']} | `{item['current_module']}` | {item['gap']} | {item['expected_correctness_impact']} | {item['expected_efficiency_impact']} | robustness `{item['robustness_risk']}`, generalization `{item['generalization_risk']}` |")
    (reports / f"{DESIGN_STEM}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_answer_grounding_report(reports: Path, eval_report: dict[str, Any]) -> None:
    summary = eval_report.get("summary", {})
    payload = {
        "report_type": ANSWER_GROUNDING_STEM,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "diagnostic_only": True,
        "packaged_runtime_changed": False,
        "rules": [
            "SQL evidence is rendered when it directly answers the prompt.",
            "API evidence is rendered when required by evidence_need.",
            "SQL and API evidence are combined only when both add useful evidence.",
            "Unsupported claims remain rejected.",
        ],
        "best_variant": summary.get("best_variant"),
        "best_answer": summary.get("best_answer"),
        "answer_nonregression": summary.get("answer_nonregression"),
    }
    (reports / f"{ANSWER_GROUNDING_STEM}.json").write_text(json.dumps(redact_secrets(payload), indent=2, sort_keys=True), encoding="utf-8")
    (reports / f"{ANSWER_GROUNDING_STEM}.md").write_text(
        "\n".join(["# Weak Model Answer Grounding Harness", "", f"- Best variant: `{payload['best_variant']}`", f"- Best answer score: `{payload['best_answer']}`", f"- Answer non-regression: `{payload['answer_nonregression']}`", "", *[f"- {rule}" for rule in payload["rules"]], ""]),
        encoding="utf-8",
    )


def _render_md(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Weak Harness Engineering Eval",
        "",
        "Diagnostic-only harness variants for weak-model scaffolding. Packaged `SQL_FIRST_API_VERIFY` is unchanged.",
        "",
        f"- Run label: `{summary.get('run_label')}`",
        f"- Best variant: `{summary.get('best_variant')}`",
        f"- Best strict/API/SQL/answer: `{summary.get('best_strict')}` / `{summary.get('best_api')}` / `{summary.get('best_sql')}` / `{summary.get('best_answer')}`",
        f"- SQL improved over previous weak scaffold: `{summary.get('sql_improved_over_previous_weak_scaffold')}`",
        f"- API non-regression: `{summary.get('api_nonregression')}`",
        f"- Answer non-regression: `{summary.get('answer_nonregression')}`",
        f"- Unsupported claims zero: `{summary.get('unsupported_claims_zero')}`",
        f"- Recommendation: `{summary.get('recommendation')}`",
        "",
        "| Mode | Rows | Strict | SQL | API | Answer | Unit pass | Repair | Grounding | Unsupported |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for mode in summary.get("modes") or []:
        if mode.get("mode") not in HARNESS_VARIANTS:
            continue
        lines.append(
            f"| `{mode.get('mode')}` | {mode.get('rows', 0)} | {mode.get('strict_final_score', 'n/a')} | {mode.get('sql_score', 'n/a')} | {mode.get('api_score', 'n/a')} | {mode.get('answer_score', 'n/a')} | {mode.get('sql_unit_test_pass_rate', 'n/a')} | {mode.get('repair_success_rate', 'n/a')} | {mode.get('answer_grounding_rate', 'n/a')} | {mode.get('unsupported_claims', 'n/a')} |"
        )
    return "\n".join(lines) + "\n"


def _bounded_gate(mode: dict[str, Any]) -> bool:
    if not mode:
        return False
    return (
        _num(mode.get("sql_score")) > REFERENCE["current_weak_scaffold_sql"]
        and _num(mode.get("api_score")) >= REFERENCE["current_weak_scaffold_api"]
        and _num(mode.get("answer_score")) >= REFERENCE["current_weak_scaffold_answer"]
        and int(mode.get("unsupported_claims") or 0) == 0
    )


def _recommendation(best: dict[str, Any], best_sql: dict[str, Any]) -> str:
    if _bounded_gate(best) and _num(best.get("strict_final_score")) > REFERENCE["current_weak_scaffold_strict"]:
        return "weak_harness_balanced_improved_keep_shadow"
    if _bounded_gate(best_sql):
        return "weak_harness_sql_improved_keep_shadow"
    if _num(best.get("answer_score")) < REFERENCE["current_weak_scaffold_answer"]:
        return "weak_harness_answer_regression"
    if _num(best.get("api_score")) < REFERENCE["current_weak_scaffold_api"]:
        return "weak_harness_api_regression"
    return "weak_harness_still_sql_limited"


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
