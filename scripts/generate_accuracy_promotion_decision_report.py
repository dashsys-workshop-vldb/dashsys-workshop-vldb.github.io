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


def main() -> int:
    config = Config.from_env(ROOT)
    payload = generate_accuracy_promotion_decision_report(config)
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    json_path = config.outputs_dir / "accuracy_promotion_decision_report.json"
    md_path = config.outputs_dir / "accuracy_promotion_decision_report.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "recommendation": payload["summary"]["recommendation"]}, indent=2, sort_keys=True))
    return 0


def generate_accuracy_promotion_decision_report(config: Config) -> dict[str, Any]:
    hidden = _load_json(config.outputs_dir / "hidden_style_eval.json")
    endpoint_canary = _load_json(config.outputs_dir / "endpoint_schema_rule_canary.json")
    endpoint_trial = _load_json(config.outputs_dir / "endpoint_schema_rule_packaged_trial.json")
    ast_canary = _load_json(config.outputs_dir / "ast_guided_sql_candidate_canary.json")
    repair_v3 = _load_json(config.outputs_dir / "repair_selector_v3_shadow_eval.json")
    strict = _load_json(config.outputs_dir / "eval_results_strict.json")
    sql_first = strict.get("summary", {}).get("by_strategy", {}).get("SQL_FIRST_API_VERIFY", {})
    recommendation = _recommendation(endpoint_trial, ast_canary)
    return {
        **report_metadata(config.outputs_dir),
        "mode": "accuracy_promotion_decision_report",
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
        ],
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
        f"- Hidden-style passed/total: {summary['hidden_style_passed_cases']}/{summary['hidden_style_total_cases']}",
        f"- Endpoint/schema canary recommendation: `{summary['endpoint_schema_canary_recommendation']}`",
        f"- Endpoint/schema packaged trial recommendation: `{summary['endpoint_schema_trial_recommendation']}`",
        f"- AST-guided SQL canary recommendation: `{summary['ast_guided_sql_canary_recommendation']}`",
        f"- Repair selector v3 success: {summary['repair_selector_v3_success']}",
        f"- Final accuracy recommendation: `{summary['recommendation']}`",
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
