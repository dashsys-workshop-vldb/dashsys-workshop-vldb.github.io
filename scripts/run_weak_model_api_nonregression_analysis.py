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
from dashagent.eval_harness import EvalHarness, extract_api_calls
from dashagent.trajectory import redact_secrets

REPORT_STEM = "weak_model_api_nonregression_analysis"


def main() -> int:
    config = Config.from_env(ROOT)
    report = run_analysis(config)
    print(json.dumps({"json": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.json"), "root_causes": report["root_cause_counts"]}, indent=2, sort_keys=True))
    return 0


def run_analysis(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports = config.outputs_dir / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    lift = _load_json(reports / "weak_model_lift_eval_public_dev_limit_5.json") or _load_json(reports / "weak_model_lift_eval.json")
    baseline = _load_json(config.outputs_dir / "llm_strict_baseline_eval.json")
    strict = _load_json(config.outputs_dir / "eval_results_strict.json")
    examples = {example.query_id: example for example in EvalHarness(config).load_examples()[:5]}
    rows = []
    for query_id, example in examples.items():
        mode_rows = {row.get("mode"): row for row in lift.get("rows", []) if row.get("query_id") == query_id}
        raw = _baseline_row(baseline, query_id, "RAW_REAL_LLM_TWO_TOOLS_BASELINE")
        guided = _baseline_row(baseline, query_id, "GUIDED_REAL_LLM_TWO_TOOLS_BASELINE")
        scaffold = _best_scaffold_row(mode_rows)
        full = _strict_row(strict, query_id, "SQL_FIRST_API_VERIFY")
        root = _root_cause(example, raw, guided, scaffold, full)
        rows.append(
            redact_secrets(
                {
                    "query_id": query_id,
                    "prompt": example.query,
                    "expected_evidence_need": _expected_evidence_need(example),
                    "gold_api_calls": extract_api_calls(example.gold_api),
                    "raw_weak": _mode_summary(raw),
                    "guided_weak": _mode_summary(guided),
                    "best_scaffold": _mode_summary(scaffold),
                    "full_system_reference": _mode_summary(full),
                    "raw_weak_api_calls": _api_calls(raw),
                    "guided_weak_api_calls": _api_calls(guided),
                    "scaffold_api_calls": _api_calls(scaffold),
                    "full_system_api_calls": _api_calls(full),
                    "api_result_entered_evidence": _api_result_entered_evidence(scaffold),
                    "answer_used_api_result": _answer_used_api(scaffold),
                    "api_regression_root_cause": root,
                }
            )
        )
    root_counts: dict[str, int] = {}
    for row in rows:
        root_counts[row["api_regression_root_cause"]] = root_counts.get(row["api_regression_root_cause"], 0) + 1
    report = redact_secrets(
        {
            "report_type": REPORT_STEM,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "diagnostic_only": True,
            "promotion_allowed": False,
            "packaged_runtime_changed": False,
            "rows": rows,
            "root_cause_counts": root_counts,
            "summary": {
                "rows_where_raw_or_guided_had_api_credit_but_scaffold_lost_it": [
                    row["query_id"]
                    for row in rows
                    if _num(row["best_scaffold"].get("api_score")) < max(_num(row["raw_weak"].get("api_score")), _num(row["guided_weak"].get("api_score")))
                ],
                "dominant_loss_stage": max(root_counts, key=root_counts.get) if root_counts else "no_clear_api_regression",
                "safest_fix_candidate": "balanced_sql_api_evidence_need_plus_catalog_endpoint_selection",
            },
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


def _baseline_row(payload: dict[str, Any], query_id: str, system: str) -> dict[str, Any]:
    return next((row for row in payload.get("rows", []) if row.get("query_id") == query_id and row.get("system") == system), {})


def _strict_row(payload: dict[str, Any], query_id: str, strategy: str) -> dict[str, Any]:
    row = next((item for item in payload.get("rows", []) if item.get("query_id") == query_id and item.get("strategy") == strategy), {})
    if not row:
        return {}
    output_dir = Path(str(row.get("output_dir") or ""))
    trajectory = _load_json(output_dir / "trajectory.json") if output_dir else {}
    converted = {
        "query_id": row.get("query_id"),
        "mode": "full_dashagent_current",
        "api_score": row.get("api_score"),
        "sql_score": row.get("sql_score"),
        "answer_score": row.get("answer_score"),
        "tool_calls": row.get("tool_call_count"),
        "trajectory": trajectory,
    }
    return converted


def _best_scaffold_row(mode_rows: dict[str, dict[str, Any]]) -> dict[str, Any]:
    candidates = [
        row
        for mode, row in mode_rows.items()
        if mode not in {"raw_weak_llm", "guided_weak_llm", "full_dashagent_current"}
        and isinstance(row.get("strict_final_score"), (int, float))
    ]
    return max(candidates, key=lambda row: float(row.get("strict_final_score") or -999), default={})


def _mode_summary(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "mode": row.get("mode") or row.get("system") or row.get("strategy"),
        "api_score": row.get("api_score"),
        "sql_score": row.get("sql_score"),
        "answer_score": row.get("answer_score"),
        "tool_calls": row.get("tool_calls") or row.get("tool_call_count"),
    }


def _api_calls(row: dict[str, Any]) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    trajectory = row.get("trajectory") if isinstance(row.get("trajectory"), dict) else {}
    for step in trajectory.get("steps", []):
        if step.get("kind") == "api_call":
            calls.append({"method": step.get("method"), "path": step.get("url") or step.get("path"), "params": step.get("params", {})})
    for call in trajectory.get("llm_tool_calls", []):
        args = call.get("arguments") if isinstance(call.get("arguments"), dict) else {}
        if call.get("tool") == "call_api" or "url" in args:
            calls.append({"method": args.get("method", "GET"), "path": args.get("url"), "params": args.get("params", {})})
    return calls


def _api_result_entered_evidence(row: dict[str, Any]) -> bool:
    trajectory = row.get("trajectory") if isinstance(row.get("trajectory"), dict) else {}
    return any(step.get("kind") == "api_call" and step.get("result") for step in trajectory.get("steps", []))


def _answer_used_api(row: dict[str, Any]) -> bool:
    trajectory = row.get("trajectory") if isinstance(row.get("trajectory"), dict) else {}
    final = next((step for step in trajectory.get("steps", []) if step.get("kind") == "final_answer"), {})
    grounding = final.get("grounding") if isinstance(final.get("grounding"), dict) else {}
    return bool(grounding.get("answer_used_api") or grounding.get("api_evidence_used_in_answer"))


def _expected_evidence_need(example: Any) -> str:
    has_api = bool(extract_api_calls(example.gold_api))
    has_sql = bool(example.gold_sql)
    if has_sql and has_api:
        return "mixed_sql_api"
    if has_api:
        return "live_api_required"
    if has_sql:
        return "local_sql_required"
    return "unclear"


def _root_cause(example: Any, raw: dict[str, Any], guided: dict[str, Any], scaffold: dict[str, Any], full: dict[str, Any]) -> str:
    gold_api = extract_api_calls(example.gold_api)
    scaffold_calls = _api_calls(scaffold)
    if gold_api and not scaffold_calls:
        return "endpoint_not_selected"
    if gold_api and scaffold_calls and not _api_result_entered_evidence(scaffold):
        return "endpoint_selected_but_not_executed"
    if gold_api and _num(scaffold.get("api_score")) < _num(full.get("api_score")) and not _answer_used_api(scaffold):
        return "api_result_not_used_in_answer"
    if _num(scaffold.get("api_score")) < max(_num(raw.get("api_score")), _num(guided.get("api_score"))):
        return "scaffold_overcorrected_to_sql"
    return "no_clear_api_regression"


def _num(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def _render_md(report: dict[str, Any]) -> str:
    lines = [
        "# Weak Model API Non-Regression Analysis",
        "",
        "Diagnostic-only. Packaged `SQL_FIRST_API_VERIFY` remains unchanged.",
        "",
        "| Query | Root cause | Raw API | Guided API | Scaffold API | Full API | Scaffold calls |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in report["rows"]:
        lines.append(
            f"| `{row['query_id']}` | `{row['api_regression_root_cause']}` | {row['raw_weak'].get('api_score')} | {row['guided_weak'].get('api_score')} | {row['best_scaffold'].get('api_score')} | {row['full_system_reference'].get('api_score')} | {len(row['scaffold_api_calls'])} |"
        )
    lines.extend(
        [
            "",
            f"- Dominant loss stage: `{report['summary']['dominant_loss_stage']}`",
            f"- Safest fix candidate: `{report['summary']['safest_fix_candidate']}`",
        ]
    )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
