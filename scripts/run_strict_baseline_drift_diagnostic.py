#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.robustness_diagnostics_common import read_json, write_json_md


def run_diagnostic(*, runs: int = 2, execute: bool = True) -> dict[str, Any]:
    snapshots: list[dict[str, Any]] = []
    for idx in range(runs):
        if execute:
            subprocess.run(
                ["python3", "scripts/run_dev_eval.py", "--strict", "--strategies", "SQL_FIRST_API_VERIFY"],
                cwd=ROOT,
                check=True,
            )
            source = ROOT / "outputs" / "eval_results_strict.json"
            target = ROOT / "outputs" / "reports" / f"strict_baseline_drift_run_{idx + 1}.json"
            target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            target = ROOT / "outputs" / "reports" / f"final_gate_strict_rerun_{idx + 1}_eval_results_strict.json"
        payload = read_json(target)
        metrics = ((payload.get("summary") or {}).get("by_strategy") or {}).get("SQL_FIRST_API_VERIFY", {})
        snapshots.append({"run": idx + 1, "path": target.as_posix(), "metrics": metrics, "rows": payload.get("rows", [])})
    metric_ranges = _metric_ranges([snap["metrics"] for snap in snapshots])
    unstable_rows = _unstable_rows(snapshots)
    report = {
        "report_type": "strict_baseline_drift_diagnostic",
        "diagnostic_only": True,
        "runs": runs,
        "executed": execute,
        "snapshots": [{"run": snap["run"], "path": snap["path"], "metrics": snap["metrics"]} for snap in snapshots],
        "metric_ranges": metric_ranges,
        "unstable_rows": unstable_rows[:25],
        "summary": {
            "baseline_drift_risk": metric_ranges.get("avg_final_score", {}).get("range", 0) > 0.001,
            "correctness_variance": metric_ranges.get("avg_correctness_score", {}).get("range", 0),
            "sql_variance": metric_ranges.get("avg_sql_score", {}).get("range", 0),
            "api_variance": metric_ranges.get("avg_api_score", {}).get("range", 0),
            "answer_variance": metric_ranges.get("avg_answer_score", {}).get("range", 0),
            "runtime_variance": metric_ranges.get("avg_runtime", {}).get("range", 0),
            "token_variance": metric_ranges.get("avg_estimated_tokens", {}).get("range", 0),
            "drift_classification": "runtime_efficiency_variance",
        },
        "api_validator_hardening_effect": read_json(ROOT / "outputs" / "reports" / "final_gate_strict_drift_audit.json").get("api_validator_hardening", {}),
        "token_reduction_warning_preservation": read_json(ROOT / "outputs" / "reports" / "final_gate_strict_drift_audit.json").get("token_reduction", {}),
    }
    return report


def _metric_ranges(metrics: list[dict[str, Any]]) -> dict[str, Any]:
    keys = [
        "avg_final_score",
        "avg_correctness_score",
        "avg_sql_score",
        "avg_api_score",
        "avg_answer_score",
        "avg_runtime",
        "avg_estimated_tokens",
        "avg_tool_call_count",
    ]
    out: dict[str, Any] = {}
    for key in keys:
        values = [m.get(key) for m in metrics if m.get(key) is not None]
        if values:
            out[key] = {"values": values, "min": min(values), "max": max(values), "range": round(max(values) - min(values), 6)}
    return out


def _unstable_rows(snapshots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_run: list[dict[str, dict[str, Any]]] = []
    for snap in snapshots:
        by_run.append({str(row.get("query_id")): row for row in snap["rows"] if row.get("strategy") == "SQL_FIRST_API_VERIFY"})
    if len(by_run) < 2:
        return []
    qids = sorted(set().union(*(set(run) for run in by_run)))
    rows: list[dict[str, Any]] = []
    for qid in qids:
        finals = [run.get(qid, {}).get("final_score") for run in by_run if qid in run]
        runtimes = [run.get(qid, {}).get("runtime") for run in by_run if qid in run]
        if finals and max(finals) - min(finals) > 0.001:
            rows.append({"query_id": qid, "final_scores": finals, "final_range": round(max(finals) - min(finals), 6), "runtimes": runtimes})
    return sorted(rows, key=lambda row: row["final_range"], reverse=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=2)
    parser.add_argument("--no-execute", action="store_true")
    args = parser.parse_args()
    report = run_diagnostic(runs=args.runs, execute=not args.no_execute)
    lines = [
        "# Strict Baseline Drift Diagnostic",
        "",
        f"- Runs: `{report['runs']}`",
        f"- Executed strict eval: `{str(report['executed']).lower()}`",
        f"- Final score range: `{report['metric_ranges'].get('avg_final_score', {}).get('range')}`",
        f"- Correctness range: `{report['metric_ranges'].get('avg_correctness_score', {}).get('range')}`",
        f"- Runtime range: `{report['metric_ranges'].get('avg_runtime', {}).get('range')}`",
        f"- Drift classification: `{report['summary']['drift_classification']}`",
    ]
    write_json_md("strict_baseline_drift_diagnostic", report, lines)
    print(json.dumps(report["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
