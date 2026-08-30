#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.planner import PACKAGED_DEFAULT_STRATEGY
from scripts.robustness_diagnostics_common import read_json, safe_summary_metrics, write_json_md


def main() -> int:
    reports = ROOT / "outputs" / "reports"
    strict = read_json(ROOT / "outputs" / "eval_results_strict.json")
    hidden = read_json(ROOT / "outputs" / "hidden_style_eval.json")
    check = read_json(ROOT / "outputs" / "final_submission_manifest.json")
    internal_500 = read_json(reports / "dashagent_500_prompt_suite_eval_real.json")
    converted_500 = read_json(reports / "dashagent_500_organizer_style_strict_comparison.json")
    live = read_json(reports / "live_api_readiness_smoke.json")
    status = subprocess.run(["git", "status", "--short"], cwd=ROOT, text=True, capture_output=True, check=False).stdout.splitlines()
    strict_sql_first = safe_summary_metrics(strict, "SQL_FIRST_API_VERIFY")
    preflight = {
        "report_type": "robustness_diagnostics_preflight",
        "git_status_short": status[:200],
        "packaged_default_strategy": PACKAGED_DEFAULT_STRATEGY,
        "final_submission_format_status": {
            "manifest_exists": (ROOT / "outputs" / "final_submission_manifest.json").exists(),
            "query_output_count": check.get("query_output_count"),
            "strategy": PACKAGED_DEFAULT_STRATEGY,
        },
        "organizer_35_strict_sql_first": strict_sql_first,
        "internal_500_heuristic": {
            "grading_type": internal_500.get("grading_type"),
            "organizer_equivalent": internal_500.get("organizer_equivalent"),
            "packaged_baseline_real": (internal_500.get("modes") or {}).get("packaged_baseline_real"),
            "combined_safe": (internal_500.get("modes") or {}).get("combined_safe_applied_real_trial"),
        },
        "internal_500_organizer_style_strict": {
            "organizer_equivalent": False,
            "summary": converted_500.get("summary"),
        },
        "hidden_style": hidden.get("summary") or hidden,
        "check_submission_ready_available": bool(check),
        "pytest_status": "not_run_in_preflight",
        "api_readiness_status": {
            "available": bool(live),
            "live_success_count": live.get("live_success_count") or live.get("summary", {}).get("live_success_count"),
            "live_empty_count": live.get("live_empty_count") or live.get("summary", {}).get("live_empty_count"),
        },
        "known_bottlenecks": [
            "answer_score",
            "API underuse risk",
            "answer grounding gaps",
            "routing hardcoding risk",
            "score source ambiguity",
            "baseline drift risk",
        ],
        "runtime_behavior_modified": False,
    }
    lines = [
        "# Robustness Diagnostics Preflight",
        "",
        f"- Packaged default strategy: `{PACKAGED_DEFAULT_STRATEGY}`",
        f"- Organizer 35 SQL_FIRST final: `{strict_sql_first.get('avg_final_score')}`",
        f"- Organizer 35 answer score: `{strict_sql_first.get('avg_answer_score')}`",
        f"- Hidden-style failed cases: `{(hidden.get('summary') or hidden).get('failed_cases')}`",
        f"- check_submission_ready manifest available: `{str(bool(check)).lower()}`",
        "",
        "No runtime behavior was modified during preflight.",
    ]
    write_json_md("robustness_diagnostics_preflight", preflight, lines, reports)
    print(json.dumps(preflight["organizer_35_strict_sql_first"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
