#!/usr/bin/env python
from __future__ import annotations

import json
import sys
import argparse
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.report_run import current_report_run_id, report_metadata
from scripts.run_official_token_reduction_eval import _load_json

REQUIRED_HIDDEN_SUMMARY_FIELDS = (
    "total_cases",
    "passed_cases",
    "failed_cases",
    "family_stability_rate",
    "schema_stability_rate",
)
REQUIRED_SCHEMA_DATASET_B_FIELDS = (
    "expected_schema_tables",
    "observed_schema_tables_before",
    "observed_schema_tables_after",
    "pass_fail_reason",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the accuracy promotion decision report.")
    parser.add_argument(
        "--allow-stale",
        action="store_true",
        help="Allow a missing/stale/incomplete hidden-style dependency and mark the decision non-promotional.",
    )
    args = parser.parse_args(argv)
    config = Config.from_env(ROOT)
    payload = generate_accuracy_promotion_decision_report(config, allow_stale=args.allow_stale)
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    json_path = config.outputs_dir / "accuracy_promotion_decision_report.json"
    md_path = config.outputs_dir / "accuracy_promotion_decision_report.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "recommendation": payload["summary"]["recommendation"]}, indent=2, sort_keys=True))
    return 0


def generate_accuracy_promotion_decision_report(config: Config, *, allow_stale: bool = False) -> dict[str, Any]:
    hidden, hidden_freshness = _load_hidden_style_dependency(config, allow_stale=allow_stale)
    endpoint_canary = _load_json(config.outputs_dir / "endpoint_schema_rule_canary.json")
    endpoint_trial = _load_json(config.outputs_dir / "endpoint_schema_rule_packaged_trial.json")
    ast_canary = _load_json(config.outputs_dir / "ast_guided_sql_candidate_canary.json")
    repair_v3 = _load_json(config.outputs_dir / "repair_selector_v3_shadow_eval.json")
    strict = _load_json(config.outputs_dir / "eval_results_strict.json")
    sql_first = strict.get("summary", {}).get("by_strategy", {}).get("SQL_FIRST_API_VERIFY", {})
    recommendation = (
        "do_not_submit_until_regression_fixed"
        if not hidden_freshness["fresh"]
        else _recommendation(endpoint_trial, ast_canary)
    )
    return {
        **report_metadata(config.outputs_dir),
        "mode": "accuracy_promotion_decision_report",
        "freshness": {
            "fresh": hidden_freshness["fresh"],
            "stale_allowed": hidden_freshness["stale_allowed"],
            "expected_run_id": hidden_freshness["expected_run_id"],
            "hidden_style_eval_run_id": hidden_freshness["hidden_style_eval_run_id"],
            "hidden_style_eval_generated_at": hidden_freshness["hidden_style_eval_generated_at"],
            "hidden_style_eval_problems": hidden_freshness["problems"],
        },
        "packaged_execution_changed": False,
        "repair_execution_enabled": config.enable_gated_risk_cluster_repair_execution,
        "compact_context_enabled": config.enable_compact_context_when_schema_vote_safe,
        "official_token_reduction_enabled": config.enable_official_token_reduction,
        "summary": {
            "hidden_style_passed_cases": (hidden.get("summary") or {}).get("passed_cases", 0),
            "hidden_style_total_cases": (hidden.get("summary") or {}).get("total_cases", 0),
            "hidden_style_family_stability_rate": (hidden.get("summary") or {}).get("family_stability_rate", 0.0),
            "hidden_style_schema_stability_rate": (hidden.get("summary") or {}).get("schema_stability_rate", 0.0),
            "endpoint_schema_canary_recommendation": (endpoint_canary.get("summary") or {}).get("recommendation", "not_run"),
            "endpoint_schema_trial_recommendation": (endpoint_trial.get("summary") or {}).get("recommendation", "not_run"),
            "endpoint_schema_api_top_k_hit_rate_delta": (endpoint_canary.get("summary") or {}).get("api_top_k_hit_rate_delta", 0.0),
            "ast_guided_sql_canary_recommendation": (ast_canary.get("summary") or {}).get("recommendation", "not_run"),
            "repair_selector_v3_success": (repair_v3.get("summary") or {}).get("success", False),
            "strict_final_score": sql_first.get("avg_final_score"),
            "strict_correctness": sql_first.get("avg_correctness_score"),
            "estimated_tokens": sql_first.get("avg_estimated_tokens"),
            "runtime": sql_first.get("avg_runtime"),
            "tool_calls": sql_first.get("avg_tool_call_count"),
            "recommendation": recommendation,
        },
        "hidden_style_eval": hidden.get("summary", {}),
        "endpoint_schema_rule_canary": endpoint_canary.get("summary", {}),
        "endpoint_schema_rule_packaged_trial": endpoint_trial.get("summary", {}),
        "ast_guided_sql_candidate_canary": ast_canary.get("summary", {}),
        "repair_selector_v3_shadow_eval": repair_v3.get("summary", {}),
        "notes": [
            "Accuracy changes remain shadow/canary/trial-only unless a later explicit task promotes them.",
            "Gold labels are used only for offline strict scoring and report comparison.",
            "Hidden-style freshness failures are non-promotional and fail by default unless --allow-stale is used.",
        ],
    }


def _load_hidden_style_dependency(config: Config, *, allow_stale: bool) -> tuple[dict[str, Any], dict[str, Any]]:
    path = config.outputs_dir / "hidden_style_eval.json"
    expected_run_id = current_report_run_id(config.outputs_dir)
    problems: list[str] = []
    hidden: dict[str, Any] = {}
    if not path.exists():
        problems.append("hidden_style_eval.json_missing")
    else:
        hidden = _load_json(path)
        if not hidden:
            problems.append("hidden_style_eval.json_unreadable_or_empty")
    summary = hidden.get("summary") if isinstance(hidden, dict) else None
    if not isinstance(summary, dict):
        problems.append("hidden_style_eval.summary_missing")
    else:
        for field in REQUIRED_HIDDEN_SUMMARY_FIELDS:
            if field not in summary:
                problems.append(f"hidden_style_eval.summary.{field}_missing")
    rows = hidden.get("rows") if isinstance(hidden, dict) else None
    if not isinstance(rows, list):
        problems.append("hidden_style_eval.rows_missing")
        schema_dataset_b = None
    else:
        schema_dataset_b = next((row for row in rows if row.get("case_id") == "schema_dataset_b"), None)
        if schema_dataset_b is None:
            problems.append("hidden_style_eval.schema_dataset_b_missing")
    if schema_dataset_b is not None:
        for field in REQUIRED_SCHEMA_DATASET_B_FIELDS:
            if field not in schema_dataset_b:
                problems.append(f"hidden_style_eval.schema_dataset_b.{field}_missing")
    hidden_run_id = hidden.get("run_id") if isinstance(hidden, dict) else None
    if hidden_run_id != expected_run_id:
        problems.append("hidden_style_eval.run_id_stale")
    fresh = not problems
    if problems and not allow_stale:
        raise RuntimeError("hidden_style_eval.json is stale or incomplete: " + ", ".join(problems))
    return hidden, {
        "fresh": fresh,
        "stale_allowed": bool(allow_stale and not fresh),
        "expected_run_id": expected_run_id,
        "hidden_style_eval_run_id": hidden_run_id,
        "hidden_style_eval_generated_at": hidden.get("generated_at") if isinstance(hidden, dict) else None,
        "problems": problems,
    }


def _recommendation(endpoint_trial: dict[str, Any], ast_canary: dict[str, Any]) -> str:
    endpoint_rec = (endpoint_trial.get("summary") or {}).get("recommendation")
    ast_rec = (ast_canary.get("summary") or {}).get("recommendation")
    if endpoint_rec == "safe_to_promote_endpoint_schema_rules":
        return "promote_endpoint_schema_rules"
    if ast_rec == "safe_for_packaged_ast_trial":
        return "promote_ast_guided_sql"
    if endpoint_rec == "unsafe_do_not_enable" or ast_rec == "unsafe_do_not_enable":
        return "do_not_submit_until_regression_fixed"
    return "keep_all_accuracy_changes_shadow_only"


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Accuracy Promotion Decision Report",
        "",
        f"- Hidden-style dependency fresh: {payload.get('freshness', {}).get('fresh')}",
        f"- Stale hidden-style allowed: {payload.get('freshness', {}).get('stale_allowed')}",
        f"- Hidden-style passed/total: {summary['hidden_style_passed_cases']}/{summary['hidden_style_total_cases']}",
        f"- Hidden-style family/schema stability: {summary['hidden_style_family_stability_rate']} / {summary['hidden_style_schema_stability_rate']}",
        f"- Endpoint/schema canary recommendation: `{summary['endpoint_schema_canary_recommendation']}`",
        f"- Endpoint/schema packaged trial recommendation: `{summary['endpoint_schema_trial_recommendation']}`",
        f"- AST-guided SQL canary recommendation: `{summary['ast_guided_sql_canary_recommendation']}`",
        f"- Repair selector v3 success: {summary['repair_selector_v3_success']}",
        f"- Final accuracy recommendation: `{summary['recommendation']}`",
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
