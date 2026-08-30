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

REPORT_STEM = "weak_model_answer_grounding_regression_analysis"
BASELINE_VARIANT = "weak_scaffold_api_recovery_v1"
SQL_LIFT_VARIANT = "weak_scaffold_balanced_sql_api_v2"
V3_VARIANTS = [
    "weak_scaffold_balanced_sql_api_answer_v3",
    "weak_scaffold_sql_lift_api_recovery_v3",
    "weak_scaffold_answer_fallback_v3",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze weak scaffold answer grounding regression after SQL lift.")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--full-public-dev", action="store_true")
    args = parser.parse_args()
    config = Config.from_env(ROOT)
    load_local_env(config.project_root)
    payload = run_weak_model_answer_grounding_regression_analysis(
        config,
        max_examples=None if args.full_public_dev else args.limit,
    )
    print(json.dumps({"json": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.json"), "summary": payload["summary"]}, indent=2, sort_keys=True))
    return 0


def run_weak_model_answer_grounding_regression_analysis(
    config: Config | None = None,
    *,
    max_examples: int | None = 10,
) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports = config.outputs_dir / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    variants = [BASELINE_VARIANT, SQL_LIFT_VARIANT, *V3_VARIANTS]
    lift = run_weak_model_lift_eval(config, max_examples=max_examples, variants=variants, execute_real=True)
    rows = _comparison_rows(lift.get("rows", []), variants)
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


def _comparison_rows(eval_rows: list[dict[str, Any]], variants: list[str]) -> list[dict[str, Any]]:
    by_query: dict[str, dict[str, dict[str, Any]]] = {}
    for row in eval_rows:
        if row.get("mode") not in variants:
            continue
        by_query.setdefault(str(row.get("query_id")), {})[str(row.get("mode"))] = row
    comparisons: list[dict[str, Any]] = []
    for query_id, variant_rows in sorted(by_query.items()):
        baseline = variant_rows.get(BASELINE_VARIANT)
        lifted = variant_rows.get(SQL_LIFT_VARIANT)
        if not baseline or not lifted:
            continue
        base_details = _row_details(baseline)
        lifted_details = _row_details(lifted)
        v3_details = {variant: _row_details(variant_rows[variant]) for variant in V3_VARIANTS if variant in variant_rows}
        comparisons.append(
            {
                "query_id": query_id,
                "prompt": lifted.get("prompt") or baseline.get("prompt"),
                "v1": base_details,
                "v2": lifted_details,
                "v3": v3_details,
                "answer_score_delta_v2_minus_v1": _delta(lifted.get("answer_score"), baseline.get("answer_score")),
                "strict_delta_v2_minus_v1": _delta(lifted.get("strict_final_score"), baseline.get("strict_final_score")),
                "sql_delta_v2_minus_v1": _delta(lifted.get("sql_score"), baseline.get("sql_score")),
                "api_delta_v2_minus_v1": _delta(lifted.get("api_score"), baseline.get("api_score")),
                "regression_category": _classify_regression(base_details, lifted_details, baseline, lifted),
                "v3_best_answer_variant": _best_variant(v3_details, "answer_score"),
                "v3_best_strict_variant": _best_variant(v3_details, "strict_final_score"),
            }
        )
    return comparisons


def _row_details(row: dict[str, Any]) -> dict[str, Any]:
    trajectory = row.get("trajectory") if isinstance(row.get("trajectory"), dict) else {}
    steps = trajectory.get("steps") if isinstance(trajectory.get("steps"), list) else []
    grounding = next((step.get("grounding") for step in steps if step.get("kind") == "final_answer"), {})
    sql_step = next((step for step in steps if step.get("kind") == "sql_call"), {})
    api_step = next((step for step in steps if step.get("kind") == "api_call"), {})
    return {
        "strict_final_score": row.get("strict_final_score"),
        "sql_score": row.get("sql_score"),
        "api_score": row.get("api_score"),
        "answer_score": row.get("answer_score"),
        "unsupported_claim_count": row.get("unsupported_claim_count"),
        "final_answer": trajectory.get("final_answer"),
        "sql_result_available": bool(sql_step),
        "api_result_available": bool(api_step),
        "answer_used_sql": bool(grounding.get("answer_used_sql") or grounding.get("sql_evidence_used_in_answer")),
        "answer_used_api": bool(grounding.get("answer_used_api") or grounding.get("api_evidence_used_in_answer")),
        "sql_evidence": grounding.get("sql_evidence"),
        "api_evidence": grounding.get("api_evidence") or ((api_step.get("result") or {}).get("api_evidence") if isinstance(api_step.get("result"), dict) else None),
        "grounding_mode": grounding.get("grounding_mode"),
        "arbitration_mode": grounding.get("sql_api_arbitration_mode"),
    }


def _classify_regression(base: dict[str, Any], lifted: dict[str, Any], base_row: dict[str, Any], lifted_row: dict[str, Any]) -> str:
    if _num(lifted_row.get("answer_score")) >= _num(base_row.get("answer_score")):
        return "no_clear_answer_regression"
    if lifted.get("sql_result_available") and not lifted.get("answer_used_sql"):
        return "sql_evidence_not_rendered"
    if lifted.get("api_result_available") and not lifted.get("answer_used_api"):
        return "api_evidence_not_rendered"
    if base.get("api_result_available") and not lifted.get("api_result_available"):
        return "api_evidence_lost_after_sql_lift"
    answer = str(lifted.get("final_answer") or "").lower()
    if "sql evidence" in answer and lifted.get("api_result_available") and not lifted.get("answer_used_api"):
        return "sql_overrode_better_api_answer"
    if any(marker in answer for marker in ("returns: .", "returned rows, but")):
        return "missing_count_or_list_values"
    if any(marker in str(lifted_row.get("prompt") or "").lower() for marker in ("when", "status", "state")) and not any(
        marker in answer for marker in ("time", "date", "status", "state", "matching records")
    ):
        return "missing_status_or_timestamp"
    if "no matching records" in answer and not (lifted.get("api_evidence") or {}).get("live_empty"):
        return "live_empty_misworded"
    if lifted.get("arbitration_mode") != base.get("arbitration_mode"):
        return "sql_api_arbitration_wrong"
    return "answer_shape_weaker"


def _summary(rows: list[dict[str, Any]], lift: dict[str, Any]) -> dict[str, Any]:
    categories: dict[str, int] = {}
    sql_improved_answer_regressed = []
    for row in rows:
        category = str(row.get("regression_category") or "no_clear_answer_regression")
        categories[category] = categories.get(category, 0) + 1
        if _num(row.get("sql_delta_v2_minus_v1")) > 0 and _num(row.get("answer_score_delta_v2_minus_v1")) < 0:
            sql_improved_answer_regressed.append(row.get("query_id"))
    modes = (lift.get("summary") or {}).get("modes") or []
    return {
        "row_count": len(rows),
        "run_label": lift.get("run_label"),
        "category_counts": categories,
        "rows_where_v2_sql_improved_but_answer_regressed": sql_improved_answer_regressed,
        "mode_summaries": [mode for mode in modes if mode.get("mode") in [BASELINE_VARIANT, SQL_LIFT_VARIANT, *V3_VARIANTS]],
        "safest_fix_candidate": "balanced_sql_api_answer_v3_with_deterministic_evidence_fallback",
    }


def _render_md(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Weak Model Answer Grounding Regression Analysis",
        "",
        "Diagnostic-only comparison of `weak_scaffold_api_recovery_v1`, SQL-lift v2, and v3 answer-grounding variants.",
        "",
        f"- Run label: `{summary.get('run_label')}`",
        f"- Rows compared: `{summary.get('row_count')}`",
        f"- Rows where v2 SQL improved but answer regressed: `{summary.get('rows_where_v2_sql_improved_but_answer_regressed')}`",
        f"- Safest fix candidate: `{summary.get('safest_fix_candidate')}`",
        "",
        "## Category Counts",
        "",
    ]
    for category, count in sorted((summary.get("category_counts") or {}).items()):
        lines.append(f"- `{category}`: `{count}`")
    lines.extend(["", "## Mode Summaries", "", "| Mode | Strict | SQL | API | Answer | Unsupported |", "| --- | ---: | ---: | ---: | ---: | ---: |"])
    for mode in summary.get("mode_summaries") or []:
        lines.append(
            f"| `{mode.get('mode')}` | {mode.get('strict_final_score', 'n/a')} | {mode.get('sql_score', 'n/a')} | {mode.get('api_score', 'n/a')} | {mode.get('answer_score', 'n/a')} | {mode.get('unsupported_claims', 'n/a')} |"
        )
    lines.extend(["", "## Row Categories", "", "| Query | Category | SQL delta | Answer delta | Strict delta |", "| --- | --- | ---: | ---: | ---: |"])
    for row in report.get("rows") or []:
        lines.append(
            f"| `{row.get('query_id')}` | `{row.get('regression_category')}` | {row.get('sql_delta_v2_minus_v1')} | {row.get('answer_score_delta_v2_minus_v1')} | {row.get('strict_delta_v2_minus_v1')} |"
        )
    return "\n".join(lines) + "\n"


def _best_variant(details: dict[str, dict[str, Any]], metric: str) -> str | None:
    if not details:
        return None
    return max(details, key=lambda variant: _num(details[variant].get(metric)))


def _delta(after: Any, before: Any) -> float:
    return round(_num(after) - _num(before), 4)


def _num(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


if __name__ == "__main__":
    raise SystemExit(main())
