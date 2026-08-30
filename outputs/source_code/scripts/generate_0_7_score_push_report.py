#!/usr/bin/env python
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.report_run import report_metadata
from scripts.run_official_token_reduction_eval import _load_json


BASELINE_STRICT_SCORE = 0.6491
TARGET_SCORE = 0.7000


def main() -> int:
    config = Config.from_env(ROOT)
    payload = generate_score_push_report(config)
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    json_path = config.outputs_dir / "score_0_7_push_report.json"
    md_path = config.outputs_dir / "score_0_7_push_report.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "recommendation": payload["summary"]["final_recommendation"]}, indent=2, sort_keys=True))
    return 0


def generate_score_push_report(config: Config) -> dict[str, Any]:
    strict = _load_json(config.outputs_dir / "eval_results_strict.json")
    mining = _load_json(config.outputs_dir / "low_score_failure_mining_report.json")
    execution = _load_json(config.outputs_dir / "execution_candidate_search.json")
    llm = _load_json(config.outputs_dir / "llm_candidate_search.json")
    trial = _load_json(config.outputs_dir / "targeted_accuracy_packaged_trial.json")
    baseline = _baseline_summary(strict)
    trial_summary = trial.get("summary") or {}
    best_safe_score = float(trial_summary.get("strict_final_score") or baseline["strict_final_score"])
    reached = best_safe_score >= TARGET_SCORE
    fallback = best_safe_score > baseline["strict_final_score"]
    recommendation = (
        "promote_targeted_accuracy_changes"
        if trial_summary.get("recommendation") == "promote_targeted_accuracy_changes" and fallback
        else "submit_current_official_token_reduction_version"
    )
    if trial_summary.get("recommendation") == "unsafe_do_not_enable":
        recommendation = "do_not_submit_until_regression_fixed"
    return {
        **report_metadata(config.outputs_dir),
        "mode": "score_0_7_push_report",
        "baseline": baseline,
        "target_score": TARGET_SCORE,
        "score_required_to_reach_0_7": round(max(0.0, TARGET_SCORE - baseline["strict_final_score"]), 4),
        "low_score_failure_mining": mining.get("summary", {}),
        "execution_candidate_search": execution.get("summary", {}),
        "llm_candidate_search": llm.get("summary", {}),
        "targeted_accuracy_packaged_trial": trial_summary,
        "packaged_execution_changed": False,
        "summary": {
            "strict_score_achieved": round(best_safe_score, 4),
            "target_0_70_reached": reached,
            "fallback_safe_improvement": fallback,
            "best_safe_score_delta": round(best_safe_score - baseline["strict_final_score"], 4),
            "final_recommendation": recommendation,
        },
        "notes": [
            "Primary target is strict_final_score >= 0.7000.",
            "Fallback success is any safe strict-score improvement over the promoted baseline with no regression.",
            "If no safe candidate passes gates, the submit-ready official-token-reduction version remains recommended.",
        ],
    }


def _baseline_summary(strict: dict[str, Any]) -> dict[str, Any]:
    sql_first = (strict.get("summary") or {}).get("by_strategy", {}).get("SQL_FIRST_API_VERIFY", {})
    return {
        "strict_final_score": float(sql_first.get("avg_final_score") or BASELINE_STRICT_SCORE),
        "correctness": sql_first.get("avg_correctness_score"),
        "estimated_tokens": sql_first.get("avg_estimated_tokens"),
        "runtime": sql_first.get("avg_runtime"),
        "tool_calls": sql_first.get("avg_tool_call_count"),
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    baseline = payload["baseline"]
    lines = [
        "# 0.70 Strict-Score Push Report",
        "",
        f"- Baseline strict final score: {baseline['strict_final_score']}",
        f"- Target strict final score: {payload['target_score']}",
        f"- Score required: {payload['score_required_to_reach_0_7']}",
        f"- Best safe strict score achieved: {summary['strict_score_achieved']}",
        f"- 0.70 reached safely: {summary['target_0_70_reached']}",
        f"- Fallback safe improvement: {summary['fallback_safe_improvement']}",
        f"- Final recommendation: `{summary['final_recommendation']}`",
        "",
    ]
    if not summary["target_0_70_reached"]:
        lines.append("0.7 was not reached safely; unsafe or merely tying changes remain shadow-only.")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
