#!/usr/bin/env python
from __future__ import annotations

import json
import shutil
import sys
from collections import Counter
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.eval_harness import EvalHarness
from dashagent.trajectory import redact_secrets
from scripts.run_sql_template_coverage_audit import run_sql_template_coverage_audit


REPORT_STEM = "schema_aware_sql_trial"
BASELINE_NAME = "baseline_sql_first_api_verify"
CANDIDATE_NAME = "schema_aware_sql_fallback"


def main() -> int:
    config = Config.from_env(ROOT)
    payload = run_schema_aware_sql_trial(config)
    print(
        json.dumps(
            {
                "json": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.json"),
                "markdown": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.md"),
                "decision": payload.get("decision", {}).get("decision"),
                "strict_score_delta": payload.get("summary", {}).get("strict_score_delta"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def run_schema_aware_sql_trial(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    output_root = config.outputs_dir / REPORT_STEM
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    baseline = _run_variant(config, output_root / "baseline", enable_schema_aware=False)
    candidate = _run_variant(config, output_root / "schema_aware", enable_schema_aware=True)
    comparison_rows = _compare_rows(baseline, candidate)
    coverage = run_sql_template_coverage_audit(config)
    payload = redact_secrets(
        {
            "report_type": REPORT_STEM,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "diagnostic_only": True,
            "official_score_claim": False,
            "promotion_allowed": False,
            "runtime_change_applied": False,
            "packaged_default_changed": False,
            "strategy": "SQL_FIRST_API_VERIFY",
            "variants": {
                BASELINE_NAME: _variant_summary(baseline),
                CANDIDATE_NAME: _variant_summary(candidate),
            },
            "summary": _summary(baseline, candidate, comparison_rows),
            "rows_helped": [row for row in comparison_rows if row["final_score_delta"] > 0],
            "rows_hurt": [row for row in comparison_rows if row["final_score_delta"] < 0],
            "rows_unchanged": [row for row in comparison_rows if row["final_score_delta"] == 0],
            "template_miss_rows_fixed": [
                row
                for row in comparison_rows
                if row.get("baseline_sql_template_family") is None
                and row.get("candidate_sql_family") == "schema_aware_sql_fallback"
                and row["sql_score_delta"] > 0
            ],
            "generated_prompt_coverage": {
                "source_report": "outputs/reports/sql_template_coverage_audit.json",
                "template_miss_count": coverage.get("template_miss_count"),
                "schema_aware_candidate_available_on_template_miss": coverage.get("schema_aware_candidate_available_on_template_miss"),
                "note": "Generated prompts are diagnostic-only and are not score evidence.",
            },
            "decision": _decision(baseline, candidate, comparison_rows),
            "isolated_output_root": str(output_root),
        }
    )
    (reports_dir / f"{REPORT_STEM}.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    (reports_dir / f"{REPORT_STEM}.md").write_text(_render_markdown(payload), encoding="utf-8")
    return payload


def _run_variant(config: Config, output_dir: Path, *, enable_schema_aware: bool) -> dict[str, Any]:
    variant_config = replace(
        config,
        outputs_dir=output_dir,
        enable_schema_aware_sql_fallback=enable_schema_aware,
    )
    harness = EvalHarness(variant_config)
    return harness.run(strategies=["SQL_FIRST_API_VERIFY"], strict=True)


def _compare_rows(baseline: dict[str, Any], candidate: dict[str, Any]) -> list[dict[str, Any]]:
    base_by_id = {row["query_id"]: row for row in baseline.get("rows", [])}
    cand_by_id = {row["query_id"]: row for row in candidate.get("rows", [])}
    rows = []
    for query_id, base in sorted(base_by_id.items()):
        cand = cand_by_id.get(query_id)
        if not cand:
            continue
        rows.append(
            {
                "query_id": query_id,
                "query": base.get("query"),
                "baseline_final_score": base.get("final_score"),
                "candidate_final_score": cand.get("final_score"),
                "final_score_delta": _delta(cand.get("final_score"), base.get("final_score")),
                "sql_score_delta": _delta(cand.get("sql_score"), base.get("sql_score")),
                "answer_score_delta": _delta(cand.get("answer_score"), base.get("answer_score")),
                "tool_count_delta": int(cand.get("tool_call_count") or 0) - int(base.get("tool_call_count") or 0),
                "token_delta": int(cand.get("estimated_tokens") or 0) - int(base.get("estimated_tokens") or 0),
                "runtime_delta": _delta(cand.get("runtime"), base.get("runtime")),
                "baseline_sql_template_family": _first_sql_family(base.get("output_dir")),
                "candidate_sql_family": _first_sql_family(cand.get("output_dir")),
            }
        )
    return rows


def _variant_summary(result: dict[str, Any]) -> dict[str, Any]:
    strategy = (result.get("summary", {}).get("by_strategy") or {}).get("SQL_FIRST_API_VERIFY", {})
    return {
        "examples": result.get("examples"),
        "avg_sql_score": strategy.get("avg_sql_score"),
        "avg_api_score": strategy.get("avg_api_score"),
        "avg_answer_score": strategy.get("avg_answer_score"),
        "avg_final_score": strategy.get("avg_final_score"),
        "avg_tool_call_count": strategy.get("avg_tool_call_count"),
        "avg_estimated_tokens": strategy.get("avg_estimated_tokens"),
        "avg_runtime": strategy.get("avg_runtime"),
    }


def _summary(baseline: dict[str, Any], candidate: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    base = _variant_summary(baseline)
    cand = _variant_summary(candidate)
    return {
        "strict_score_delta": _delta(cand.get("avg_final_score"), base.get("avg_final_score")),
        "sql_score_delta": _delta(cand.get("avg_sql_score"), base.get("avg_sql_score")),
        "answer_score_delta": _delta(cand.get("avg_answer_score"), base.get("avg_answer_score")),
        "tool_count_delta": _delta(cand.get("avg_tool_call_count"), base.get("avg_tool_call_count")),
        "token_delta": _delta(cand.get("avg_estimated_tokens"), base.get("avg_estimated_tokens")),
        "runtime_delta": _delta(cand.get("avg_runtime"), base.get("avg_runtime")),
        "rows_helped_count": sum(1 for row in rows if row["final_score_delta"] > 0),
        "rows_hurt_count": sum(1 for row in rows if row["final_score_delta"] < 0),
        "rows_unchanged_count": sum(1 for row in rows if row["final_score_delta"] == 0),
        "schema_aware_sql_rows": dict(Counter(str(row.get("candidate_sql_family") or "none") for row in rows)),
    }


def _decision(baseline: dict[str, Any], candidate: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    summary = _summary(baseline, candidate, rows)
    improves = float(summary.get("strict_score_delta") or 0.0) > 0.0
    hurts = int(summary.get("rows_hurt_count") or 0) > 0
    return {
        "decision": "keep_trial_only",
        "promotion_allowed": False,
        "reason": (
            "Schema-aware SQL fallback is diagnostic-only in this pass. "
            "A future promotion requires explicit approval plus strict/hidden/submission validation."
        ),
        "strict_score_improved_in_trial": improves,
        "regression_rows_present": hurts,
    }


def _delta(new: Any, old: Any) -> float:
    if new is None or old is None:
        return 0.0
    return round(float(new) - float(old), 4)


def _first_sql_family(output_dir: str | None) -> str | None:
    if not output_dir:
        return None
    path = Path(output_dir) / "trajectory.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    for step in payload.get("steps", []):
        if step.get("kind") != "plan":
            continue
        for planned in step.get("steps", []):
            if planned.get("action") == "sql":
                return planned.get("family")
    return None


def _render_markdown(report: dict[str, Any]) -> str:
    summary = report.get("summary", {})
    lines = [
        "# Schema-Aware SQL Trial",
        "",
        "Diagnostic-only comparison of baseline `SQL_FIRST_API_VERIFY` and a feature-flagged schema-aware SQL fallback.",
        "",
        f"- Strict score delta: {summary.get('strict_score_delta')}",
        f"- SQL score delta: {summary.get('sql_score_delta')}",
        f"- Answer score delta: {summary.get('answer_score_delta')}",
        f"- Rows helped: {summary.get('rows_helped_count')}",
        f"- Rows hurt: {summary.get('rows_hurt_count')}",
        f"- Decision: {report.get('decision', {}).get('decision')}",
        "",
        "No automatic promotion is made by this trial.",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
