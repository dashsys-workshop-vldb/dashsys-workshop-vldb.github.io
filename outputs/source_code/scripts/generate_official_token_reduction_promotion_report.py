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
from dashagent.eval_harness import EvalHarness
from dashagent.planner import STRATEGIES
from dashagent.report_run import report_metadata
from scripts.check_submission_ready import check_submission_ready, required_trajectory_fields_present
from scripts.package_query_outputs import NON_SUBMISSION_OUTPUT_DIRS, REQUIRED_QUERY_FILES, package_query_outputs
from scripts.run_official_token_reduction_eval import _load_json


BASELINE = {
    "strict_final_score": 0.6486,
    "strict_correctness": 0.6743,
    "estimated_tokens": 899.2286,
    "runtime": 0.0112,
    "tool_calls": 1.4571,
}


def main() -> int:
    config = Config.from_env(ROOT)
    payload = generate_official_token_reduction_promotion_report(config)
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    json_path = config.outputs_dir / "official_token_reduction_promotion_report.json"
    md_path = config.outputs_dir / "official_token_reduction_promotion_report.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "recommendation": payload["summary"]["recommendation"]}, indent=2, sort_keys=True))
    return 0 if payload["summary"]["promotion_kept"] else 1


def generate_official_token_reduction_promotion_report(config: Config) -> dict[str, Any]:
    previous_manifest = _load_json(config.outputs_dir / "final_submission_manifest.json")
    result = EvalHarness(config).run(strategies=STRATEGIES, strict=True)
    strict_summary = result.get("summary", {}).get("by_strategy", {}).get("SQL_FIRST_API_VERIFY", {})
    package_query_outputs(config)
    readiness = check_submission_ready(config)
    final_submission_diff = compare_final_submission_structure(config, previous_manifest)
    repair_enabled = config.enable_gated_risk_cluster_repair_execution
    compact_enabled = config.enable_compact_context_when_schema_vote_safe
    promoted = {
        "strict_final_score": strict_summary.get("avg_final_score"),
        "strict_correctness": strict_summary.get("avg_correctness_score"),
        "estimated_tokens": strict_summary.get("avg_estimated_tokens"),
        "runtime": strict_summary.get("avg_runtime"),
        "tool_calls": strict_summary.get("avg_tool_call_count"),
    }
    gates = {
        "preferred_strategy_sql_first": readiness.get("default_strategy_is_sql_first_api_verify") is True,
        "strict_final_score_gate": float(promoted["strict_final_score"] or 0.0) >= BASELINE["strict_final_score"] - 0.0005,
        "strict_correctness_gate": float(promoted["strict_correctness"] or 0.0) >= BASELINE["strict_correctness"],
        "estimated_tokens_gate": float(promoted["estimated_tokens"] or 999999.0) < BASELINE["estimated_tokens"],
        "tool_calls_gate": float(promoted["tool_calls"] or 999999.0) <= BASELINE["tool_calls"],
        "final_submission_diff_gate": final_submission_diff.get("unchanged") is True,
        "readiness_gate": readiness.get("ok") is True,
        "no_secret_scan_gate": readiness.get("secret_scan", {}).get("ok") is True,
        "repair_execution_disabled_gate": not repair_enabled,
        "compact_context_disabled_gate": not compact_enabled,
        "official_token_reduction_default_on_gate": config.enable_official_token_reduction is True,
    }
    promotion_kept = all(gates.values())
    recommendation = "promoted_keep_enabled" if promotion_kept else "promotion_failed_reverted"
    return {
        **report_metadata(config.outputs_dir, reset=True),
        "mode": "official_token_reduction_promotion_report",
        "promotion_attempted": True,
        "promotion_kept": promotion_kept,
        "feature_flag_default": config.enable_official_token_reduction,
        "explicit_disable_env": "ENABLE_OFFICIAL_TOKEN_REDUCTION=0",
        "baseline": BASELINE,
        "promoted": promoted,
        "deltas": {
            "score_delta": round(float(promoted["strict_final_score"] or 0.0) - BASELINE["strict_final_score"], 4),
            "correctness_delta": round(float(promoted["strict_correctness"] or 0.0) - BASELINE["strict_correctness"], 4),
            "token_delta": round(float(promoted["estimated_tokens"] or 0.0) - BASELINE["estimated_tokens"], 4),
            "runtime_delta": round(float(promoted["runtime"] or 0.0) - BASELINE["runtime"], 4),
            "tool_delta": round(float(promoted["tool_calls"] or 0.0) - BASELINE["tool_calls"], 4),
        },
        "final_submission_diff": final_submission_diff,
        "readiness": {
            "ok": readiness.get("ok"),
            "preferred_strategy_sql_first": readiness.get("default_strategy_is_sql_first_api_verify"),
            "no_secret_scan_ok": readiness.get("secret_scan", {}).get("ok"),
            "query_output_count": readiness.get("query_output_count"),
        },
        "repair_execution_enabled": repair_enabled,
        "compact_context_enabled": compact_enabled,
        "gates": gates,
        "summary": {
            "promotion_attempted": True,
            "promotion_kept": promotion_kept,
            "baseline_strict_score": BASELINE["strict_final_score"],
            "promoted_strict_score": promoted["strict_final_score"],
            "score_delta": round(float(promoted["strict_final_score"] or 0.0) - BASELINE["strict_final_score"], 4),
            "baseline_correctness": BASELINE["strict_correctness"],
            "promoted_correctness": promoted["strict_correctness"],
            "baseline_estimated_tokens": BASELINE["estimated_tokens"],
            "promoted_estimated_tokens": promoted["estimated_tokens"],
            "token_delta": round(float(promoted["estimated_tokens"] or 0.0) - BASELINE["estimated_tokens"], 4),
            "baseline_runtime": BASELINE["runtime"],
            "promoted_runtime": promoted["runtime"],
            "runtime_delta": round(float(promoted["runtime"] or 0.0) - BASELINE["runtime"], 4),
            "baseline_tool_calls": BASELINE["tool_calls"],
            "promoted_tool_calls": promoted["tool_calls"],
            "tool_delta": round(float(promoted["tool_calls"] or 0.0) - BASELINE["tool_calls"], 4),
            "final_submission_format_unchanged": final_submission_diff.get("unchanged"),
            "no_secret_scan_ok": readiness.get("secret_scan", {}).get("ok"),
            "repair_execution_enabled": repair_enabled,
            "compact_context_enabled": compact_enabled,
            "recommendation": recommendation,
        },
        "notes": [
            "Official-token reduction is the only behavior-changing default promoted in this pass.",
            "If any gate fails, revert Config.from_env default back to disabled and regenerate this report.",
        ],
    }


def compare_final_submission_structure(config: Config, previous_manifest: dict[str, Any]) -> dict[str, Any]:
    final_dir = config.outputs_dir / "final_submission"
    current_manifest = _load_json(config.outputs_dir / "final_submission_manifest.json")
    query_dirs = sorted(path for path in final_dir.iterdir() if path.is_dir() and path.name.startswith("query_")) if final_dir.exists() else []
    query_checks = []
    experimental_hits = []
    valid = True
    for query_dir in query_dirs:
        files = {name: (query_dir / name).exists() for name in REQUIRED_QUERY_FILES}
        trajectory_valid = False
        required_fields = False
        if files.get("trajectory.json"):
            try:
                trajectory = json.loads((query_dir / "trajectory.json").read_text(encoding="utf-8"))
                trajectory_valid = True
                required_fields = required_trajectory_fields_present(trajectory)
            except Exception:
                trajectory_valid = False
        valid = valid and all(files.values()) and trajectory_valid and required_fields
        query_checks.append(
            {
                "query_id": query_dir.name,
                "files": files,
                "trajectory_json_valid": trajectory_valid,
                "required_trajectory_fields": required_fields,
            }
        )
    for root in NON_SUBMISSION_OUTPUT_DIRS:
        if root in {"final_submission", "source_code"}:
            continue
        if any(root in part for path in final_dir.rglob("*") for part in path.parts):
            experimental_hits.append(root)
    previous_count = int(previous_manifest.get("total_number_of_queries") or len(previous_manifest.get("queries") or []))
    current_count = int(current_manifest.get("total_number_of_queries") or len(query_dirs))
    same_required_files = all(all(item["files"].values()) for item in query_checks)
    preferred_sql_first = current_manifest.get("preferred_strategy") == "SQL_FIRST_API_VERIFY"
    unchanged = (
        bool(previous_manifest)
        and previous_count == current_count
        and same_required_files
        and valid
        and not experimental_hits
        and preferred_sql_first
    )
    return {
        "unchanged": unchanged,
        "previous_query_count": previous_count,
        "current_query_count": current_count,
        "same_required_files": same_required_files,
        "all_trajectories_valid": all(item["trajectory_json_valid"] for item in query_checks),
        "required_fields_preserved": all(item["required_trajectory_fields"] for item in query_checks),
        "experimental_output_roots_included": sorted(set(experimental_hits)),
        "preferred_strategy": current_manifest.get("preferred_strategy"),
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Official Token Reduction Promotion Report",
        "",
        f"- Promotion attempted: {summary['promotion_attempted']}",
        f"- Promotion kept: {summary['promotion_kept']}",
        f"- Recommendation: `{summary['recommendation']}`",
        f"- Feature flag default: {payload['feature_flag_default']}",
        f"- Explicit disable: `{payload['explicit_disable_env']}`",
        "",
        "## Metrics",
        "",
        f"- Strict score: {summary['baseline_strict_score']} -> {summary['promoted_strict_score']} ({summary['score_delta']})",
        f"- Correctness: {summary['baseline_correctness']} -> {summary['promoted_correctness']}",
        f"- Estimated tokens: {summary['baseline_estimated_tokens']} -> {summary['promoted_estimated_tokens']} ({summary['token_delta']})",
        f"- Runtime: {summary['baseline_runtime']} -> {summary['promoted_runtime']} ({summary['runtime_delta']})",
        f"- Tool calls: {summary['baseline_tool_calls']} -> {summary['promoted_tool_calls']} ({summary['tool_delta']})",
        "",
        "## Gates",
        "",
    ]
    lines.extend(f"- {key}: {value}" for key, value in payload["gates"].items())
    lines.extend(
        [
            "",
            "## Final Submission Diff",
            "",
            f"- Format unchanged: {summary['final_submission_format_unchanged']}",
            f"- Preferred strategy: `{payload['final_submission_diff'].get('preferred_strategy')}`",
            f"- Experimental roots included: {payload['final_submission_diff'].get('experimental_output_roots_included')}",
            "",
            "This is now an official packaged improvement only when `recommendation=promoted_keep_enabled`.",
        ]
    )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
