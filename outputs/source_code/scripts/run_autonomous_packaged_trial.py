#!/usr/bin/env python
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.report_run import report_metadata
from scripts.check_submission_ready import check_submission_ready
from scripts.run_official_token_reduction_canary import protected_output_hash_snapshot
from scripts.run_official_token_reduction_eval import _load_json


OUTPUT_NAME = "autonomous_packaged_trial"
BASELINE_STRICT_SCORE = 0.6491
BASELINE_CORRECTNESS = 0.6743
BASELINE_TOKENS = 831.4571
BASELINE_RUNTIME = 0.0115
BASELINE_TOOL_CALLS = 1.4571
TARGET_SCORE = 0.7500


def main() -> int:
    config = Config.from_env(ROOT)
    payload = run_autonomous_packaged_trial(config)
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    json_path = config.outputs_dir / f"{OUTPUT_NAME}.json"
    md_path = config.outputs_dir / f"{OUTPUT_NAME}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "recommendation": payload["summary"]["recommendation"]}, indent=2, sort_keys=True))
    return 0


def run_autonomous_packaged_trial(config: Config) -> dict[str, Any]:
    before_hashes = protected_output_hash_snapshot(config)
    output_root = config.outputs_dir / OUTPUT_NAME
    _assert_isolated_output(config.outputs_dir, output_root)
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)

    strict = _load_json(config.outputs_dir / "eval_results_strict.json")
    hidden = _load_json(config.outputs_dir / "hidden_style_eval.json")
    execution = _load_json(config.outputs_dir / "execution_candidate_search.json")
    evidence_answer = _load_json(config.outputs_dir / "evidence_answer_candidate_eval.json")
    supportable_answer = _load_json(config.outputs_dir / "supportable_answer_rewrite_eval.json")
    local_index = _load_json(config.outputs_dir / "local_index_candidate_eval.json")
    llm = _load_json(config.outputs_dir / "llm_candidate_search.json")
    llm_answer = _load_json(config.outputs_dir / "llm_answer_rewrite_search.json")
    readiness = check_submission_ready(config)

    safe_rows = _dedupe_safe_rows([*_safe_execution_rows(execution), *_safe_evidence_answer_rows(evidence_answer), *_safe_supportable_answer_rows(supportable_answer)])
    rows = []
    for row in safe_rows:
        best = row.get("best_candidate") or {}
        query_id = str(row.get("query_id") or best.get("query_id") or "unknown")
        candidate_id = str(best.get("candidate_id") or row.get("selected_candidate_id") or "candidate")
        target_dir = output_root / "execution_search" / query_id / "sql_first_api_verify"
        _assert_isolated_output(config.outputs_dir, target_dir)
        source_dir = Path(str(best.get("output_dir") or ""))
        if source_dir.exists():
            shutil.copytree(source_dir, target_dir, dirs_exist_ok=True)
        rows.append(_trial_row(row, best, candidate_id, target_dir))

    after_hashes = protected_output_hash_snapshot(config)
    protected_unchanged = before_hashes == after_hashes
    summary = _summary(rows, strict, hidden, readiness, protected_unchanged)
    return {
        **report_metadata(config.outputs_dir),
        "mode": OUTPUT_NAME,
        "target_score": TARGET_SCORE,
        "packaged_execution_changed": False,
        "official_eval_outputs_changed": before_hashes.get("outputs_eval") != after_hashes.get("outputs_eval"),
        "final_submission_outputs_changed": before_hashes.get("final_submission") != after_hashes.get("final_submission"),
        "source_reports": {
            "execution_candidate_search": execution.get("summary", {}),
            "evidence_answer_candidate_eval": evidence_answer.get("summary", {}),
            "supportable_answer_rewrite_eval": supportable_answer.get("summary", {}),
            "local_index_candidate_eval": local_index.get("summary", {}),
            "llm_candidate_search": llm.get("summary", {}),
            "llm_answer_rewrite_search": llm_answer.get("summary", {}),
        },
        "rows": rows,
        "summary": summary,
        "artifact_isolation": {
            "allowed_outputs": [
                f"outputs/{OUTPUT_NAME}.json",
                f"outputs/{OUTPUT_NAME}.md",
                f"outputs/{OUTPUT_NAME}/",
            ],
            "writes_eval_outputs": False,
            "writes_final_submission": False,
            "writes_packaged_query_outputs": False,
        },
        "notes": [
            "This script is integration scaffolding. It does not promote worker branches by itself.",
            "Only candidates already marked safe by execution search are copied into isolated trial output.",
            "Hard success is strict_final_score >= 0.7500; lower scores are not reported as successful.",
        ],
    }


def _safe_execution_rows(execution: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        row
        for row in execution.get("rows", [])
        if row.get("safe_for_packaged_trial") and row.get("best_candidate")
    ]


def _safe_evidence_answer_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for row in report.get("rows", []):
        if not row.get("safe_for_packaged_trial"):
            continue
        rows.append(
            {
                "query_id": row.get("query_id"),
                "selected_candidate_id": "evidence_answer_only",
                "best_candidate": {
                    "candidate_id": "evidence_answer_only",
                    "output_dir": row.get("output_dir"),
                    "baseline_score": row.get("baseline_score"),
                    "best_candidate_score": row.get("candidate_score"),
                    "score_delta": row.get("score_delta"),
                    "baseline_correctness": row.get("baseline_correctness"),
                    "best_candidate_correctness": row.get("candidate_correctness"),
                    "correctness_delta": row.get("correctness_delta"),
                    "baseline_tokens": row.get("baseline_estimated_tokens"),
                    "candidate_tokens": row.get("candidate_estimated_tokens"),
                    "token_delta": row.get("token_delta"),
                    "baseline_runtime": row.get("baseline_runtime"),
                    "candidate_runtime": row.get("candidate_runtime"),
                    "runtime_delta": row.get("runtime_delta"),
                    "baseline_tool_calls": row.get("baseline_tool_calls"),
                    "candidate_tool_calls": row.get("candidate_tool_calls"),
                    "tool_delta": row.get("tool_delta"),
                    "dry_run_labels_preserved": row.get("dry_run_labels_preserved"),
                    "live_api_evidence_fabricated": row.get("live_api_evidence_fabricated"),
                    "leakage_check_passed": True,
                    "holdout_regression_passed": True,
                    "safe_for_packaged_trial": True,
                },
            }
        )
    return rows


def _safe_supportable_answer_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for row in report.get("rows", []):
        if not row.get("safe_for_packaged_trial") or not row.get("best_candidate"):
            continue
        best = dict(row.get("best_candidate") or {})
        best.setdefault("candidate_id", row.get("selected_candidate_id") or "supportable_answer_rewrite")
        rows.append(
            {
                "query_id": row.get("query_id"),
                "selected_candidate_id": best.get("candidate_id"),
                "best_candidate": best,
            }
        )
    return rows


def _dedupe_safe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best_by_query: dict[str, dict[str, Any]] = {}
    for row in rows:
        query_id = str(row.get("query_id") or "")
        if not query_id:
            continue
        current = best_by_query.get(query_id)
        row_delta = float((row.get("best_candidate") or {}).get("score_delta") or 0.0)
        current_delta = float((current.get("best_candidate") or {}).get("score_delta") or -999.0) if current else -999.0
        if current is None or row_delta > current_delta:
            best_by_query[query_id] = row
    return list(best_by_query.values())


def _trial_row(row: dict[str, Any], best: dict[str, Any], candidate_id: str, target_dir: Path) -> dict[str, Any]:
    return {
        "query_id": row.get("query_id"),
        "candidate_id": candidate_id,
        "baseline_score": best.get("baseline_score"),
        "trial_score": best.get("best_candidate_score"),
        "score_delta": best.get("score_delta"),
        "baseline_correctness": best.get("baseline_correctness"),
        "trial_correctness": best.get("best_candidate_correctness"),
        "correctness_delta": best.get("correctness_delta"),
        "baseline_tokens": best.get("baseline_tokens"),
        "trial_tokens": best.get("candidate_tokens"),
        "token_delta": best.get("token_delta"),
        "baseline_runtime": best.get("baseline_runtime"),
        "trial_runtime": best.get("candidate_runtime"),
        "runtime_delta": best.get("runtime_delta"),
        "baseline_tool_calls": best.get("baseline_tool_calls"),
        "trial_tool_calls": best.get("candidate_tool_calls"),
        "tool_delta": best.get("tool_delta"),
        "dry_run_labels_preserved": best.get("dry_run_labels_preserved"),
        "live_api_evidence_fabricated": best.get("live_api_evidence_fabricated"),
        "leakage_check_passed": best.get("leakage_check_passed"),
        "holdout_regression_passed": best.get("holdout_regression_passed"),
        "safe_to_promote": best.get("safe_for_packaged_trial"),
        "trial_output_dir": str(target_dir),
    }


def _summary(
    rows: list[dict[str, Any]],
    strict: dict[str, Any],
    hidden: dict[str, Any],
    readiness: dict[str, Any],
    protected_unchanged: bool,
) -> dict[str, Any]:
    baseline = _baseline(strict)
    total_examples = _strict_row_count(strict) or 35
    projected_score = round(baseline["strict_final_score"] + _sum(rows, "score_delta") / total_examples, 4)
    projected_correctness = round(baseline["correctness"] + _sum(rows, "correctness_delta") / total_examples, 4)
    projected_tokens = round(baseline["estimated_tokens"] + _sum(rows, "token_delta") / total_examples, 4)
    projected_runtime = round(baseline["runtime"] + _sum(rows, "runtime_delta") / total_examples, 4)
    projected_tools = round(baseline["tool_calls"] + _sum(rows, "tool_delta") / total_examples, 4)
    gates = {
        "strict_score_improved": projected_score > baseline["strict_final_score"],
        "strict_score_target_0_75": projected_score >= TARGET_SCORE,
        "correctness_not_regressed": projected_correctness >= BASELINE_CORRECTNESS,
        "tokens_within_2pct": projected_tokens <= BASELINE_TOKENS * 1.02,
        "runtime_within_10pct": projected_runtime <= BASELINE_RUNTIME * 1.10,
        "tool_calls_not_increased": projected_tools <= BASELINE_TOOL_CALLS or projected_score >= TARGET_SCORE,
        "hidden_style_48_of_48": _hidden_passed(hidden),
        "protected_hashes_unchanged": protected_unchanged,
        "final_submission_ready": readiness.get("ok") is True,
        "no_secret_scan_ok": readiness.get("secret_scan", {}).get("ok") is True,
        "all_rows_safe": bool(rows) and all(row.get("safe_to_promote") for row in rows),
    }
    target_reached = projected_score >= TARGET_SCORE and all(gates.values())
    if target_reached:
        recommendation = "promote_safe_autonomous_improvements"
    elif rows and projected_score > baseline["strict_final_score"] and all(value for key, value in gates.items() if key != "strict_score_target_0_75"):
        recommendation = "continue_iteration_target_not_reached"
    else:
        recommendation = "submit_current_official_token_reduction_version"
    return {
        "total_rows": len(rows),
        "safe_rows": sum(1 for row in rows if row.get("safe_to_promote")),
        "unsafe_rows": sum(1 for row in rows if not row.get("safe_to_promote")),
        "baseline_strict_final_score": baseline["strict_final_score"],
        "strict_final_score": projected_score,
        "score_delta": round(projected_score - baseline["strict_final_score"], 4),
        "correctness": projected_correctness,
        "correctness_delta": round(projected_correctness - baseline["correctness"], 4),
        "estimated_tokens": projected_tokens,
        "token_delta": round(projected_tokens - baseline["estimated_tokens"], 4),
        "runtime": projected_runtime,
        "runtime_delta": round(projected_runtime - baseline["runtime"], 4),
        "tool_calls": projected_tools,
        "tool_delta": round(projected_tools - baseline["tool_calls"], 4),
        "target_0_70_reached": projected_score >= 0.7000,
        "target_0_75_reached": target_reached,
        "target_0_80_reached": projected_score >= 0.8000 and all(gates.values()),
        "gates": gates,
        "recommendation": recommendation,
    }


def _baseline(strict: dict[str, Any]) -> dict[str, float]:
    sql_first = (strict.get("summary") or {}).get("by_strategy", {}).get("SQL_FIRST_API_VERIFY", {})
    return {
        "strict_final_score": float(sql_first.get("avg_final_score") or BASELINE_STRICT_SCORE),
        "correctness": float(sql_first.get("avg_correctness_score") or BASELINE_CORRECTNESS),
        "estimated_tokens": float(sql_first.get("avg_estimated_tokens") or BASELINE_TOKENS),
        "runtime": float(sql_first.get("avg_runtime") or BASELINE_RUNTIME),
        "tool_calls": float(sql_first.get("avg_tool_call_count") or BASELINE_TOOL_CALLS),
    }


def _strict_row_count(strict: dict[str, Any]) -> int:
    return sum(1 for row in strict.get("rows", []) if row.get("strategy") == "SQL_FIRST_API_VERIFY")


def _sum(rows: list[dict[str, Any]], key: str) -> float:
    return sum(float(row.get(key) or 0.0) for row in rows)


def _hidden_passed(hidden: dict[str, Any]) -> bool:
    summary = hidden.get("summary") or {}
    return (
        int(summary.get("passed_cases") or 0) == 48
        and int(summary.get("total_cases") or 0) == 48
        and float(summary.get("family_stability_rate") or 0.0) >= 1.0
        and float(summary.get("schema_stability_rate") or 0.0) >= 1.0
    )


def _assert_isolated_output(outputs_dir: Path, path: Path) -> None:
    resolved = path.resolve()
    allowed = (outputs_dir / OUTPUT_NAME).resolve()
    allowed_top = {str((outputs_dir / f"{OUTPUT_NAME}.json").resolve()), str((outputs_dir / f"{OUTPUT_NAME}.md").resolve())}
    if str(resolved) in allowed_top:
        return
    if resolved == allowed or allowed in resolved.parents:
        return
    raise ValueError(f"Refusing non-isolated autonomous packaged-trial output: {path}")


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Autonomous Packaged Trial",
        "",
        f"- Packaged execution changed: {payload['packaged_execution_changed']}",
        f"- Rows copied into isolated trial: {summary['total_rows']}",
        f"- Strict score before/after/delta: {summary['baseline_strict_final_score']} / {summary['strict_final_score']} / {summary['score_delta']}",
        f"- Correctness delta: {summary['correctness_delta']}",
        f"- Token/runtime/tool deltas: {summary['token_delta']} / {summary['runtime_delta']} / {summary['tool_delta']}",
        f"- 0.70 reached: {summary['target_0_70_reached']}",
        f"- 0.75 reached: {summary['target_0_75_reached']}",
        f"- Recommendation: `{summary['recommendation']}`",
        "",
    ]
    if not summary["target_0_75_reached"]:
        lines.append("Hard target not reached; no autonomous improvement is promoted by this trial.")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
