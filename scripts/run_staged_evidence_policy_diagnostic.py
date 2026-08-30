#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.robustness_diagnostics_common import load_500_gold_by_id, read_json, trajectory_files, write_json_md


def run_diagnostic() -> dict[str, Any]:
    organizer = _scan_organizer_eval()
    internal_500 = _scan_500_benchmark()
    converted_500 = _scan_converted_500()
    total = Counter()
    for section in (organizer, internal_500, converted_500):
        total.update(section.get("counts", {}))
    report = {
        "report_type": "staged_evidence_policy_diagnostic",
        "diagnostic_only": True,
        "packaged_runtime_changed": False,
        "llm_advisor_included": False,
        "organizer_35": organizer,
        "internal_500_heuristic": internal_500,
        "internal_500_organizer_style": converted_500,
        "summary_counts": dict(sorted(total.items())),
    }
    return report


def _scan_organizer_eval() -> dict[str, Any]:
    counts: Counter[str] = Counter()
    potential_underuse: list[dict[str, Any]] = []
    for path in trajectory_files("example_", strategy="sql_first_api_verify"):
        traj = read_json(path)
        qid = str(traj.get("query_id") or path.parts[-3])
        if traj.get("sql_call_count", 0):
            counts["sql_used"] += 1
        if traj.get("api_call_count", 0):
            counts["api_used"] += 1
        text = json.dumps(traj)
        if "API params contain unresolved parameter placeholders" in text:
            counts["unsafe_unresolved_api_blocked"] += 1
        if "checkpoint_post_sql_decision_card" in text:
            counts["post_sql_cards_present"] += 1
        if "checkpoint_real_behavior_applied_trial" in text:
            counts["applied_trial_records"] += 1
        if traj.get("api_call_count", 0) == 0 and "api" in str(traj.get("original_query", "")).lower():
            potential_underuse.append({"query_id": qid, "prompt": traj.get("original_query")})
    strict = read_json(ROOT / "outputs" / "eval_results_strict.json")
    for row in strict.get("rows", []):
        if row.get("strategy") != "SQL_FIRST_API_VERIFY":
            continue
        if row.get("api_score") is not None:
            counts["api_scored_rows"] += 1
        if row.get("api_score") == 0 and row.get("api_call_count") == 0:
            counts["api_required_underuse"] += 1
            potential_underuse.append({"query_id": row.get("query_id"), "prompt": row.get("query"), "api_score": row.get("api_score")})
    return {"counts": dict(sorted(counts.items())), "potential_api_underuse_cases": potential_underuse[:20]}


def _scan_500_benchmark() -> dict[str, Any]:
    report = read_json(ROOT / "outputs" / "reports" / "dashagent_500_prompt_suite_eval_real.json")
    modes = report.get("modes") or {}
    gold = load_500_gold_by_id()
    counts: Counter[str] = Counter()
    if modes:
        for mode, summary in modes.items():
            if not isinstance(summary, dict):
                continue
            counts[f"{mode}:api_calls"] += int(summary.get("api_calls") or 0)
            counts[f"{mode}:sql_calls"] += int(summary.get("sql_calls") or 0)
            counts[f"{mode}:api_calls_saved"] += int(summary.get("api_calls_saved") or 0)
            counts[f"{mode}:api_required_underuse"] += int(summary.get("api_required_underuse") or 0)
            counts[f"{mode}:unsupported_claims"] += int(summary.get("unsupported_claims") or 0)
    expected = Counter()
    for row in gold.values():
        tools = row.get("expected_tool_calls") or {}
        if tools.get("api_required"):
            expected["API_REQUIRED"] += 1
        elif tools.get("api_optional"):
            expected["API_OPTIONAL"] += 1
        else:
            expected["API_SKIP"] += 1
        need = str(row.get("expected_evidence_need") or "unknown")
        expected[f"need:{need}"] += 1
    counts.update(expected)
    return {"counts": dict(sorted(counts.items())), "report_available": bool(report), "expected_evidence_distribution": dict(expected)}


def _scan_converted_500() -> dict[str, Any]:
    report = read_json(ROOT / "outputs" / "reports" / "dashagent_500_organizer_style_strict_comparison.json")
    rows = report.get("rows") or []
    counts: Counter[str] = Counter()
    for row in rows:
        if row.get("api_saved"):
            counts["api_calls_saved"] += int(row.get("api_saved") or 0)
        if row.get("api_added"):
            counts["api_calls_added"] += int(row.get("api_added") or 0)
        if row.get("baseline_api_score") == 0 and row.get("combined_api_calls") == 0:
            counts["potential_api_underuse"] += 1
        if row.get("delta", 0) > 0:
            counts["rows_helped"] += 1
        elif row.get("delta", 0) < 0:
            counts["rows_hurt"] += 1
        else:
            counts["rows_neutral"] += 1
    return {"counts": dict(sorted(counts.items())), "row_count": len(rows), "organizer_equivalent": False}


def main() -> int:
    report = run_diagnostic()
    lines = [
        "# Staged Evidence Policy Diagnostic",
        "",
        f"- Packaged runtime changed: `{str(report['packaged_runtime_changed']).lower()}`",
        f"- LLM advisor included: `{str(report['llm_advisor_included']).lower()}`",
        f"- Summary counts: `{report['summary_counts']}`",
        "",
        "This report inspects actual trajectories and benchmark outputs after execution; it does not change packaged routing.",
    ]
    write_json_md("staged_evidence_policy_diagnostic", report, lines)
    print(json.dumps(report["summary_counts"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
