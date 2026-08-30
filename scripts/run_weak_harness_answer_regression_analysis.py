#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
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

REPORT_STEM = "weak_harness_answer_regression_analysis"
BASELINE_VARIANT = "weak_scaffold_api_recovery_v1"
FALLBACK_VARIANT = "weak_scaffold_answer_fallback_v3"
HARNESS_VARIANT = "weak_harness_full_v1"


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze weak harness answer non-regression failures.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--full-public-dev", action="store_true")
    args = parser.parse_args()
    config = Config.from_env(ROOT)
    load_local_env(config.project_root)
    payload = run_weak_harness_answer_regression_analysis(
        config,
        max_examples=None if args.full_public_dev else args.limit,
    )
    print(json.dumps({"json": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.json"), "summary": payload["summary"]}, indent=2, sort_keys=True))
    return 0


def run_weak_harness_answer_regression_analysis(
    config: Config | None = None,
    *,
    max_examples: int | None = None,
) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports = config.outputs_dir / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    variants = [BASELINE_VARIANT, FALLBACK_VARIANT, HARNESS_VARIANT]
    lift = run_weak_model_lift_eval(config, max_examples=max_examples, variants=variants, execute_real=True)
    rows = _comparison_rows(lift.get("rows", []))
    summary = _summary(rows, lift)
    report = redact_secrets(
        {
            "report_type": REPORT_STEM,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "diagnostic_only": True,
            "promotion_allowed": False,
            "packaged_runtime_changed": False,
            "packaged_default_strategy": "SQL_FIRST_API_VERIFY",
            "run_label": lift.get("run_label"),
            "compared_variants": variants,
            "summary": summary,
            "rows": rows,
        }
    )
    (reports / f"{REPORT_STEM}.json").write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    (reports / f"{REPORT_STEM}.md").write_text(_render_md(report), encoding="utf-8")
    return report


def _comparison_rows(eval_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_query: dict[str, dict[str, dict[str, Any]]] = {}
    for row in eval_rows:
        mode = str(row.get("mode") or "")
        if mode in {BASELINE_VARIANT, FALLBACK_VARIANT, HARNESS_VARIANT}:
            by_query.setdefault(str(row.get("query_id")), {})[mode] = row
    comparisons = []
    for query_id, modes in sorted(by_query.items()):
        baseline = modes.get(BASELINE_VARIANT)
        fallback = modes.get(FALLBACK_VARIANT)
        harness = modes.get(HARNESS_VARIANT)
        if not baseline or not fallback or not harness:
            continue
        baseline_details = _row_details(baseline)
        fallback_details = _row_details(fallback)
        harness_details = _row_details(harness)
        comparisons.append(
            {
                "query_id": query_id,
                "prompt": harness.get("prompt") or baseline.get("prompt"),
                "v1": baseline_details,
                "v3": fallback_details,
                "harness": harness_details,
                "answer_score_delta_harness_minus_v1": _delta(harness.get("answer_score"), baseline.get("answer_score")),
                "answer_score_delta_harness_minus_v3": _delta(harness.get("answer_score"), fallback.get("answer_score")),
                "strict_delta_harness_minus_v1": _delta(harness.get("strict_final_score"), baseline.get("strict_final_score")),
                "sql_delta_harness_minus_v1": _delta(harness.get("sql_score"), baseline.get("sql_score")),
                "api_delta_harness_minus_v1": _delta(harness.get("api_score"), baseline.get("api_score")),
                "regression_category": _classify_regression(baseline_details, fallback_details, harness_details, baseline, fallback, harness),
            }
        )
    return comparisons


def _row_details(row: dict[str, Any]) -> dict[str, Any]:
    trajectory = row.get("trajectory") if isinstance(row.get("trajectory"), dict) else {}
    steps = trajectory.get("steps") if isinstance(trajectory.get("steps"), list) else []
    grounding = next((step.get("grounding") for step in steps if step.get("kind") == "final_answer"), {})
    sql_step = next((step for step in steps if step.get("kind") == "sql_call"), {})
    api_step = next((step for step in steps if step.get("kind") == "api_call"), {})
    answer = str(trajectory.get("final_answer") or "")
    return {
        "strict_final_score": row.get("strict_final_score"),
        "sql_score": row.get("sql_score"),
        "api_score": row.get("api_score"),
        "answer_score": row.get("answer_score"),
        "final_answer": answer,
        "sql_evidence_available": bool(sql_step),
        "api_evidence_available": bool(api_step),
        "answer_used_sql": bool(grounding.get("answer_used_sql") or grounding.get("sql_evidence_used_in_answer")),
        "answer_used_api": bool(grounding.get("answer_used_api") or grounding.get("api_evidence_used_in_answer")),
        "grounding_mode": grounding.get("grounding_mode"),
        "assertions_failed": _failed_assertions(row),
        "too_terse": _too_terse(answer),
        "contains_bullet_shape": "- " in answer,
        "contains_evidence_labels": "sql evidence" in answer.lower() or "api evidence" in answer.lower(),
    }


def _failed_assertions(row: dict[str, Any]) -> list[str]:
    trajectory = row.get("trajectory") if isinstance(row.get("trajectory"), dict) else {}
    steps = trajectory.get("steps") if isinstance(trajectory.get("steps"), list) else []
    final = next((step.get("grounding") for step in steps if step.get("kind") == "final_answer"), {})
    assertions = final.get("harness_assertions") if isinstance(final, dict) else None
    if not isinstance(assertions, dict):
        assertions = row.get("harness_assertions") if isinstance(row.get("harness_assertions"), dict) else {}
    return list(assertions.get("failed_assertions") or [])


def _classify_regression(
    baseline: dict[str, Any],
    fallback: dict[str, Any],
    harness: dict[str, Any],
    baseline_row: dict[str, Any],
    fallback_row: dict[str, Any],
    harness_row: dict[str, Any],
) -> str:
    if _num(harness_row.get("answer_score")) >= _num(baseline_row.get("answer_score")):
        return "no_clear_regression"
    if harness.get("api_evidence_available") and not harness.get("answer_used_api"):
        return "omitted_api_evidence"
    if harness.get("sql_evidence_available") and not harness.get("answer_used_sql"):
        return "omitted_sql_evidence"
    if baseline.get("api_evidence_available") and not harness.get("api_evidence_available"):
        return "api_evidence_lost_after_sql_lift"
    answer = str(harness.get("final_answer") or "").lower()
    if harness.get("too_terse"):
        return "over_terse_answer"
    if "returned rows, but" in answer or "does not expose a usable answer" in answer:
        return "deterministic_fallback_too_sparse"
    if any(marker in str(harness_row.get("prompt") or "").lower() for marker in ("how many", "list", "show")) and not any(ch.isdigit() for ch in answer):
        return "missing_count_or_list_values"
    if any(marker in str(harness_row.get("prompt") or "").lower() for marker in ("status", "state", "when", "published", "updated")) and not any(
        marker in answer for marker in ("status", "state", "time", "date", "20")
    ):
        return "missing_status_or_timestamp"
    if "api evidence" not in answer and fallback.get("answer_used_api"):
        return "evidence_renderer_lost_context"
    if harness.get("sql_evidence_available") and harness.get("api_evidence_available") and _num(harness_row.get("api_score")) < _num(baseline_row.get("api_score")):
        return "sql_api_arbitration_wrong"
    return "wrong_answer_shape"


def _too_terse(answer: str) -> bool:
    words = [part for part in str(answer or "").split() if part]
    return 0 < len(words) < 8


def _summary(rows: list[dict[str, Any]], lift: dict[str, Any]) -> dict[str, Any]:
    categories = Counter(str(row.get("regression_category") or "no_clear_regression") for row in rows)
    regressed = [row.get("query_id") for row in rows if _num(row.get("answer_score_delta_harness_minus_v1")) < 0]
    modes = (lift.get("summary") or {}).get("modes") or []
    mode_summaries = [mode for mode in modes if mode.get("mode") in {BASELINE_VARIANT, FALLBACK_VARIANT, HARNESS_VARIANT}]
    dominant = categories.most_common(1)[0][0] if categories else "no_clear_regression"
    return {
        "run_label": lift.get("run_label"),
        "row_count": len(rows),
        "rows_where_harness_answer_regressed_vs_v1": regressed,
        "category_counts": dict(categories),
        "dominant_answer_regression_category": dominant,
        "mode_summaries": mode_summaries,
        "safest_targeted_fix": _safest_fix(dominant),
    }


def _safest_fix(category: str) -> str:
    return {
        "omitted_api_evidence": "api_primary_or_combined_answer_renderer",
        "omitted_sql_evidence": "slot_template_renderer_with_sql_fields",
        "over_terse_answer": "richer_deterministic_slot_template",
        "wrong_answer_shape": "style_preserve_answer_renderer",
        "deterministic_fallback_too_sparse": "slot_template_renderer_with_field_values",
        "evidence_renderer_lost_context": "preserve_api_recovery_v1_evidence_phrasing",
    }.get(category, "balanced_sql_api_style_preserve_renderer")


def _render_md(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Weak Harness Answer Regression Analysis",
        "",
        "Diagnostic-only comparison of api-recovery v1, answer-fallback v3, and `weak_harness_full_v1`.",
        "",
        f"- Run label: `{summary.get('run_label')}`",
        f"- Rows compared: `{summary.get('row_count')}`",
        f"- Dominant category: `{summary.get('dominant_answer_regression_category')}`",
        f"- Safest targeted fix: `{summary.get('safest_targeted_fix')}`",
        f"- Regressed rows vs v1: `{summary.get('rows_where_harness_answer_regressed_vs_v1')}`",
        "",
        "## Category Counts",
        "",
    ]
    for category, count in sorted((summary.get("category_counts") or {}).items()):
        lines.append(f"- `{category}`: `{count}`")
    lines.extend(["", "## Mode Summaries", "", "| Mode | Strict | SQL | API | Answer | Tokens | Runtime | Unsupported |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"])
    for mode in summary.get("mode_summaries") or []:
        lines.append(
            f"| `{mode.get('mode')}` | {mode.get('strict_final_score', 'n/a')} | {mode.get('sql_score', 'n/a')} | {mode.get('api_score', 'n/a')} | {mode.get('answer_score', 'n/a')} | {mode.get('estimated_tokens', 'n/a')} | {mode.get('runtime', 'n/a')} | {mode.get('unsupported_claims', 'n/a')} |"
        )
    lines.extend(["", "## Row Categories", "", "| Query | Category | Answer delta vs v1 | SQL delta vs v1 | API delta vs v1 |", "| --- | --- | ---: | ---: | ---: |"])
    for row in report.get("rows") or []:
        lines.append(
            f"| `{row.get('query_id')}` | `{row.get('regression_category')}` | {row.get('answer_score_delta_harness_minus_v1')} | {row.get('sql_delta_harness_minus_v1')} | {row.get('api_delta_harness_minus_v1')} |"
        )
    return "\n".join(lines) + "\n"


def _delta(after: Any, before: Any) -> float:
    return round(_num(after) - _num(before), 4)


def _num(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


if __name__ == "__main__":
    raise SystemExit(main())
