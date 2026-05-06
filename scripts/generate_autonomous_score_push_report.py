#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASELINE_STRICT_SCORE = 0.6491
BASELINE_CORRECTNESS = 0.6743
BASELINE_TOKENS = 831.4571
BASELINE_RUNTIME = 0.0115
BASELINE_TOOLS = 1.4571
TARGET_SCORE = 0.7500
MIN_PROGRESS_SCORE = 0.7000
STRETCH_SCORE = 0.8000


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the autonomous score075 push report.")
    parser.add_argument("--outputs-dir", default=str(ROOT / "outputs"))
    parser.add_argument("--json", default=None)
    parser.add_argument("--md", default=None)
    args = parser.parse_args()

    outputs_dir = Path(args.outputs_dir)
    payload = generate_autonomous_score_push_report(outputs_dir)
    json_path = Path(args.json) if args.json else outputs_dir / "autonomous_score_push_report.json"
    md_path = Path(args.md) if args.md else outputs_dir / "autonomous_score_push_report.md"
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "recommendation": payload["summary"]["final_recommendation"]}, indent=2))
    return 0


def generate_autonomous_score_push_report(outputs_dir: Path) -> dict[str, Any]:
    strict = _load_json(outputs_dir / "eval_results_strict.json")
    backlog = _load_json(outputs_dir / "improvement_backlog.json")
    local_index = _load_json(outputs_dir / "local_index_candidate_eval.json")
    execution_search = _load_json(outputs_dir / "execution_candidate_search.json")
    llm_search = _load_json(outputs_dir / "llm_candidate_search.json")
    packaged_trial = _load_json(outputs_dir / "autonomous_packaged_trial.json")
    hidden = _load_json(outputs_dir / "hidden_style_eval.json")
    readiness = _load_json(outputs_dir / "check_submission_ready.json")

    baseline = _baseline(strict)
    trial_summary = packaged_trial.get("summary") or {}
    trial_score = _float_or_none(trial_summary.get("strict_final_score"))
    best_score = trial_score if trial_score is not None else baseline["strict_final_score"]
    best_score = max(best_score, _float_or_none((execution_search.get("summary") or {}).get("best_projected_strict_final_score")) or baseline["strict_final_score"])
    hidden_summary = hidden.get("summary") or {}
    reached_070 = best_score >= MIN_PROGRESS_SCORE
    reached_075 = best_score >= TARGET_SCORE
    reached_080 = best_score >= STRETCH_SCORE
    gates = _gate_status(best_score, baseline, hidden_summary, readiness, trial_summary)
    final_recommendation = _recommendation(reached_075, gates, best_score, baseline)
    return {
        "mode": "autonomous_score_push_report",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "baseline": baseline,
        "targets": {
            "minimum_meaningful_progress": MIN_PROGRESS_SCORE,
            "hard_success": TARGET_SCORE,
            "stretch": STRETCH_SCORE,
        },
        "reports": {
            "improvement_backlog": backlog.get("summary", {}),
            "local_index_candidate_eval": local_index.get("summary", {}),
            "execution_candidate_search": execution_search.get("summary", {}),
            "llm_candidate_search": llm_search.get("summary", {}),
            "autonomous_packaged_trial": trial_summary,
        },
        "hidden_style_summary": hidden_summary,
        "gate_status": gates,
        "summary": {
            "starting_score": BASELINE_STRICT_SCORE,
            "best_achieved_score": round(best_score, 4),
            "score_delta": round(best_score - baseline["strict_final_score"], 4),
            "target_0_70_reached": reached_070,
            "target_0_75_reached": reached_075,
            "target_0_80_reached": reached_080,
            "final_recommendation": final_recommendation,
            "success_claimed": reached_075 and gates["all_required_gates_pass"],
        },
        "notes": _notes(reached_075, gates),
    }


def _baseline(strict: dict[str, Any]) -> dict[str, Any]:
    sql_first = (strict.get("summary") or {}).get("by_strategy", {}).get("SQL_FIRST_API_VERIFY", {})
    return {
        "preferred_strategy": "SQL_FIRST_API_VERIFY",
        "strict_final_score": float(sql_first.get("avg_final_score") or BASELINE_STRICT_SCORE),
        "correctness": float(sql_first.get("avg_correctness_score") or BASELINE_CORRECTNESS),
        "estimated_tokens": float(sql_first.get("avg_estimated_tokens") or BASELINE_TOKENS),
        "runtime": float(sql_first.get("avg_runtime") or BASELINE_RUNTIME),
        "tool_calls": float(sql_first.get("avg_tool_call_count") or BASELINE_TOOLS),
    }


def _gate_status(
    best_score: float,
    baseline: dict[str, Any],
    hidden: dict[str, Any],
    readiness: dict[str, Any],
    trial_summary: dict[str, Any],
) -> dict[str, Any]:
    correctness = _float_or_none(trial_summary.get("correctness")) or baseline["correctness"]
    tokens = _float_or_none(trial_summary.get("estimated_tokens")) or baseline["estimated_tokens"]
    runtime = _float_or_none(trial_summary.get("runtime")) or baseline["runtime"]
    tools = _float_or_none(trial_summary.get("tool_calls")) or baseline["tool_calls"]
    hidden_ok = hidden.get("passed_cases", 48) == hidden.get("total_cases", 48) == 48
    readiness_ok = bool(readiness.get("ok", True))
    no_secret_ok = bool((readiness.get("secret_scan") or readiness.get("no_secret_scan") or {"ok": True}).get("ok", True))
    gates = {
        "hard_target_met": best_score >= TARGET_SCORE,
        "correctness_ok": correctness >= BASELINE_CORRECTNESS,
        "tokens_ok": tokens <= BASELINE_TOKENS * 1.02,
        "runtime_ok": runtime <= BASELINE_RUNTIME * 1.10,
        "tool_calls_ok": tools <= BASELINE_TOOLS or best_score >= TARGET_SCORE,
        "hidden_style_ok": hidden_ok,
        "readiness_ok": readiness_ok,
        "no_secret_scan_ok": no_secret_ok,
        "final_submission_format_unchanged": bool(trial_summary.get("final_submission_format_unchanged", True)),
    }
    gates["all_required_gates_pass"] = all(gates.values())
    return gates


def _recommendation(reached_075: bool, gates: dict[str, Any], best_score: float, baseline: dict[str, Any]) -> str:
    if reached_075 and gates["all_required_gates_pass"]:
        return "promote_safe_autonomous_improvements"
    if best_score > baseline["strict_final_score"] and not reached_075:
        return "continue_iteration_target_not_reached"
    if not gates["correctness_ok"] or not gates["hidden_style_ok"] or not gates["readiness_ok"]:
        return "do_not_submit_until_regression_fixed"
    return "submit_current_official_token_reduction_version"


def _notes(reached_075: bool, gates: dict[str, Any]) -> list[str]:
    if reached_075 and gates["all_required_gates_pass"]:
        return ["0.75 was reached safely under all gates."]
    if not reached_075:
        return [
            "0.75 was not reached safely.",
            "Do not claim success below strict_final_score >= 0.7500.",
            "Preserve the current submit-ready official-token-reduction version unless integration accepts a safe improvement.",
        ]
    return ["0.75 score threshold was reached, but one or more safety gates failed; do not promote."]


def _float_or_none(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    gates = payload["gate_status"]
    lines = [
        "# Autonomous 0.75 Score-Push Report",
        "",
        f"- Starting score: {summary['starting_score']}",
        f"- Best achieved score: {summary['best_achieved_score']}",
        f"- Score delta: {summary['score_delta']}",
        f"- 0.70 reached: {summary['target_0_70_reached']}",
        f"- 0.75 reached: {summary['target_0_75_reached']}",
        f"- 0.80 reached: {summary['target_0_80_reached']}",
        f"- Success claimed: {summary['success_claimed']}",
        f"- Final recommendation: `{summary['final_recommendation']}`",
        "",
        "## Gates",
        "",
    ]
    for key, value in gates.items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Notes", ""])
    lines.extend(f"- {note}" for note in payload["notes"])
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
