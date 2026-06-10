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
from scripts.run_official_token_reduction_eval import _avg, _load_json


OUTPUT_NAME = "targeted_accuracy_packaged_trial"
BASELINE_STRICT_SCORE = 0.6491
BASELINE_CORRECTNESS = 0.6743
BASELINE_TOKENS = 831.4571
BASELINE_RUNTIME = 0.0115
BASELINE_TOOL_CALLS = 1.4571


def main() -> int:
    config = Config.from_env(ROOT)
    payload = run_targeted_accuracy_packaged_trial(config)
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    json_path = config.outputs_dir / f"{OUTPUT_NAME}.json"
    md_path = config.outputs_dir / f"{OUTPUT_NAME}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "recommendation": payload["summary"]["recommendation"]}, indent=2, sort_keys=True))
    return 0


def run_targeted_accuracy_packaged_trial(config: Config) -> dict[str, Any]:
    search = _load_json(config.outputs_dir / "execution_candidate_search.json")
    strict = _load_json(config.outputs_dir / "eval_results_strict.json")
    hidden = _load_json(config.outputs_dir / "hidden_style_eval.json")
    before_hashes = protected_output_hash_snapshot(config)
    output_root = config.outputs_dir / OUTPUT_NAME
    _assert_isolated_output(config.outputs_dir, output_root)
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)

    safe_rows = [row for row in search.get("rows", []) if row.get("safe_for_packaged_trial") and row.get("best_candidate")]
    if not safe_rows:
        after_hashes = protected_output_hash_snapshot(config)
        payload = _skipped_payload(config, search, strict, hidden, before_hashes, after_hashes)
        return payload

    rows = []
    for row in safe_rows:
        best = row["best_candidate"]
        source_dir = Path(best.get("output_dir") or "")
        query_id = str(row.get("query_id"))
        target_dir = output_root / query_id / "sql_first_api_verify"
        _assert_isolated_output(config.outputs_dir, target_dir)
        if source_dir.exists():
            shutil.copytree(source_dir, target_dir, dirs_exist_ok=True)
        rows.append(_trial_row(row, best, target_dir))

    after_hashes = protected_output_hash_snapshot(config)
    summary = _summary(rows, search, strict, hidden, before_hashes, after_hashes, check_submission_ready(config))
    return {
        **report_metadata(config.outputs_dir),
        "mode": OUTPUT_NAME,
        "feature_flag": "ENABLE_TARGETED_ACCURACY_RULES",
        "feature_flag_default": Config.from_env(config.project_root).enable_targeted_accuracy_rules,
        "feature_flag_enabled_for_trial": True,
        "packaged_execution_changed": False,
        "official_eval_outputs_changed": before_hashes.get("outputs_eval") != after_hashes.get("outputs_eval"),
        "final_submission_outputs_changed": before_hashes.get("final_submission") != after_hashes.get("final_submission"),
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
            "This is an isolated packaged-style trial only.",
            "No targeted accuracy rule is promoted by this script.",
            "Pure ties are not enough; fallback success requires a safe strict-score improvement over the promoted baseline.",
        ],
    }


def _skipped_payload(
    config: Config,
    search: dict[str, Any],
    strict: dict[str, Any],
    hidden: dict[str, Any],
    before_hashes: dict[str, Any],
    after_hashes: dict[str, Any],
) -> dict[str, Any]:
    readiness = check_submission_ready(config)
    return {
        **report_metadata(config.outputs_dir),
        "mode": OUTPUT_NAME,
        "skipped": True,
        "skip_reason": "execution_candidate_search_found_no_safe_generalizable_improvements",
        "feature_flag": "ENABLE_TARGETED_ACCURACY_RULES",
        "feature_flag_default": Config.from_env(config.project_root).enable_targeted_accuracy_rules,
        "feature_flag_enabled_for_trial": False,
        "packaged_execution_changed": False,
        "rows": [],
        "summary": {
            "total_rows": 0,
            "safe_rows": 0,
            "unsafe_rows": 0,
            "strict_final_score": _baseline_score(strict),
            "strict_score_delta": 0.0,
            "correctness": _baseline_correctness(strict),
            "estimated_tokens": _baseline_tokens(strict),
            "runtime": _baseline_runtime(strict),
            "tool_calls": _baseline_tools(strict),
            "target_0_70_reached": False,
            "fallback_safe_improvement": False,
            "hidden_style_gate_passed": _hidden_gate(hidden),
            "protected_hashes_unchanged": before_hashes == after_hashes,
            "final_submission_ready": readiness.get("ok"),
            "no_secret_scan_ok": readiness.get("secret_scan", {}).get("ok"),
            "recommendation": "keep_shadow_only",
        },
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
        "notes": ["No safe candidate passed anti-overfitting, holdout, cost, and strict scoring gates."],
    }


def _trial_row(row: dict[str, Any], best: dict[str, Any], target_dir: Path) -> dict[str, Any]:
    return {
        "query_id": row.get("query_id"),
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
        "final_answer_unsafe_drift": best.get("final_answer_unsafe_drift"),
        "sql_unsafe_drift": best.get("sql_unsafe_drift"),
        "api_unsafe_drift": best.get("api_unsafe_drift"),
        "dry_run_labels_preserved": best.get("dry_run_labels_preserved"),
        "live_api_evidence_fabricated": best.get("live_api_evidence_fabricated"),
        "required_fields_preserved": best.get("required_fields_preserved"),
        "leakage_check_passed": best.get("leakage_check_passed"),
        "holdout_regression_passed": best.get("holdout_regression_passed"),
        "safe_to_promote": best.get("safe_for_packaged_trial"),
        "trial_output_dir": str(target_dir),
    }


def _summary(
    rows: list[dict[str, Any]],
    search: dict[str, Any],
    strict: dict[str, Any],
    hidden: dict[str, Any],
    before_hashes: dict[str, Any],
    after_hashes: dict[str, Any],
    readiness: dict[str, Any],
) -> dict[str, Any]:
    baseline_score = _baseline_score(strict)
    baseline_correctness = _baseline_correctness(strict)
    baseline_tokens = _baseline_tokens(strict)
    baseline_runtime = _baseline_runtime(strict)
    baseline_tools = _baseline_tools(strict)
    strict_rows = [
        row for row in strict.get("rows", [])
        if row.get("strategy") == "SQL_FIRST_API_VERIFY"
    ]
    total_examples = len(strict_rows) or 35
    total_score_delta = sum(float(row.get("score_delta") or 0.0) for row in rows)
    total_correctness_delta = sum(float(row.get("correctness_delta") or 0.0) for row in rows)
    projected_score = round(baseline_score + total_score_delta / total_examples, 4)
    projected_correctness = round(baseline_correctness + total_correctness_delta / total_examples, 4)
    projected_tokens = round(baseline_tokens + sum(float(row.get("token_delta") or 0.0) for row in rows) / total_examples, 4)
    projected_runtime = round(baseline_runtime + sum(float(row.get("runtime_delta") or 0.0) for row in rows) / total_examples, 4)
    projected_tools = round(baseline_tools + sum(float(row.get("tool_delta") or 0.0) for row in rows) / total_examples, 4)
    gates = {
        "strict_score_improved_over_baseline": projected_score > BASELINE_STRICT_SCORE,
        "strict_score_target_0_70": projected_score >= 0.7000,
        "correctness_not_regressed": projected_correctness >= BASELINE_CORRECTNESS,
        "tokens_within_2pct": projected_tokens <= BASELINE_TOKENS * 1.02,
        "runtime_within_10pct": projected_runtime <= BASELINE_RUNTIME * 1.10,
        "tool_calls_not_increased": projected_tools <= BASELINE_TOOL_CALLS,
        "hidden_style_gate_passed": _hidden_gate(hidden),
        "protected_hashes_unchanged": before_hashes == after_hashes,
        "final_submission_ready": readiness.get("ok") is True,
        "no_secret_scan_ok": readiness.get("secret_scan", {}).get("ok") is True,
        "all_rows_safe": all(row.get("safe_to_promote") for row in rows),
    }
    promote = all(gates.values())
    return {
        "total_rows": len(rows),
        "safe_rows": sum(1 for row in rows if row.get("safe_to_promote")),
        "unsafe_rows": sum(1 for row in rows if not row.get("safe_to_promote")),
        "strict_final_score": projected_score,
        "strict_score_delta": round(projected_score - baseline_score, 4),
        "correctness": projected_correctness,
        "correctness_delta": round(projected_correctness - baseline_correctness, 4),
        "estimated_tokens": projected_tokens,
        "token_delta": round(projected_tokens - baseline_tokens, 4),
        "runtime": projected_runtime,
        "runtime_delta": round(projected_runtime - baseline_runtime, 4),
        "tool_calls": projected_tools,
        "tool_delta": round(projected_tools - baseline_tools, 4),
        "target_0_70_reached": projected_score >= 0.7000,
        "fallback_safe_improvement": projected_score > baseline_score and all(gates.values()),
        "gates": gates,
        "search_recommendation": (search.get("summary") or {}).get("recommendation"),
        "recommendation": "promote_targeted_accuracy_changes" if promote else "keep_shadow_only",
    }


def _baseline_strategy_summary(strict: dict[str, Any]) -> dict[str, Any]:
    return (strict.get("summary") or {}).get("by_strategy", {}).get("SQL_FIRST_API_VERIFY", {})


def _baseline_score(strict: dict[str, Any]) -> float:
    return float(_baseline_strategy_summary(strict).get("avg_final_score") or BASELINE_STRICT_SCORE)


def _baseline_correctness(strict: dict[str, Any]) -> float:
    return float(_baseline_strategy_summary(strict).get("avg_correctness_score") or BASELINE_CORRECTNESS)


def _baseline_tokens(strict: dict[str, Any]) -> float:
    return float(_baseline_strategy_summary(strict).get("avg_estimated_tokens") or BASELINE_TOKENS)


def _baseline_runtime(strict: dict[str, Any]) -> float:
    return float(_baseline_strategy_summary(strict).get("avg_runtime") or BASELINE_RUNTIME)


def _baseline_tools(strict: dict[str, Any]) -> float:
    return float(_baseline_strategy_summary(strict).get("avg_tool_call_count") or BASELINE_TOOL_CALLS)


def _hidden_gate(hidden: dict[str, Any]) -> bool:
    summary = hidden.get("summary") or {}
    total = int(summary.get("total_cases") or 0)
    passed = int(summary.get("passed_cases") or 0)
    return (
        total >= 48
        and passed == total
        and float(summary.get("family_stability_rate") or 0.0) >= 1.0
        and float(summary.get("schema_stability_rate") or 0.0) >= 1.0
    )


def _assert_isolated_output(outputs_dir: Path, path: Path) -> None:
    resolved = path.resolve()
    allowed_root = (outputs_dir / OUTPUT_NAME).resolve()
    if resolved in {(outputs_dir / f"{OUTPUT_NAME}.json").resolve(), (outputs_dir / f"{OUTPUT_NAME}.md").resolve()}:
        return
    try:
        resolved.relative_to(allowed_root)
    except ValueError as exc:
        raise RuntimeError(f"Targeted accuracy trial attempted to write outside isolated output root: {path}") from exc


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Targeted Accuracy Packaged Trial",
        "",
        f"- Skipped: {payload.get('skipped', False)}",
        f"- Strict final score: {summary['strict_final_score']}",
        f"- Strict score delta: {summary['strict_score_delta']}",
        f"- Correctness: {summary['correctness']}",
        f"- Estimated tokens/runtime/tools: {summary['estimated_tokens']} / {summary['runtime']} / {summary['tool_calls']}",
        f"- 0.70 reached: {summary['target_0_70_reached']}",
        f"- Fallback safe improvement: {summary['fallback_safe_improvement']}",
        f"- Recommendation: `{summary['recommendation']}`",
        "",
        "This trial is isolated and does not overwrite official eval, final submission, or packaged query outputs.",
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
