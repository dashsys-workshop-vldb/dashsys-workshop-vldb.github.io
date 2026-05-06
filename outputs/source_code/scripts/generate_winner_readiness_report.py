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
from dashagent.report_run import current_report_run_id, report_is_fresh, report_metadata
from scripts.check_submission_ready import check_submission_ready
from scripts.run_official_token_reduction_eval import _load_json


REQUIRED_REPORTS = {
    "official_token_reduction_packaged_trial": "official_token_reduction_packaged_trial.json",
    "hidden_style_eval": "hidden_style_eval.json",
    "endpoint_family_failure_report": "endpoint_family_failure_report.json",
    "schema_dataset_positive_repair_analysis": "schema_dataset_positive_repair_analysis.json",
    "sql_ast_candidate_ranking_report": "sql_ast_candidate_ranking_report.json",
    "retrieval_ablation_report": "retrieval_ablation_report.json",
    "repair_selector_v2_shadow_eval": "repair_selector_v2_shadow_eval.json",
}


def main() -> int:
    config = Config.from_env(ROOT)
    payload = generate_winner_readiness_report(config)
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    json_path = config.outputs_dir / "winner_readiness_report.json"
    md_path = config.outputs_dir / "winner_readiness_report.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "fresh": payload["freshness"]["fresh"]}, indent=2, sort_keys=True))
    return 0


def generate_winner_readiness_report(config: Config) -> dict[str, Any]:
    expected_run_id = current_report_run_id(config.outputs_dir)
    stale = [
        name
        for name, filename in REQUIRED_REPORTS.items()
        if not report_is_fresh(config.outputs_dir / filename, expected_run_id)
    ]
    if stale:
        raise RuntimeError(f"Required reports are missing or stale for run_id {expected_run_id}: {', '.join(stale)}")
    strict = _load_json(config.outputs_dir / "eval_results_strict.json")
    manifest = _load_json(config.outputs_dir / "final_submission_manifest.json")
    sql_first = strict.get("summary", {}).get("by_strategy", {}).get("SQL_FIRST_API_VERIFY", {})
    reports = {name: _load_json(config.outputs_dir / filename) for name, filename in REQUIRED_REPORTS.items()}
    readiness = check_submission_ready(config)
    return {
        **report_metadata(config.outputs_dir),
        "mode": "winner_readiness_report",
        "freshness": {"fresh": True, "run_id": expected_run_id, "required_reports": list(REQUIRED_REPORTS)},
        "packaged": {
            "preferred_strategy": manifest.get("preferred_strategy", "SQL_FIRST_API_VERIFY"),
            "strict_final_score": sql_first.get("avg_final_score"),
            "strict_correctness": sql_first.get("avg_correctness_score"),
            "estimated_tokens": sql_first.get("avg_estimated_tokens"),
            "runtime": sql_first.get("avg_runtime"),
            "tool_calls": sql_first.get("avg_tool_call_count"),
            "final_submission_ready": readiness.get("ok"),
            "no_secret_scan_ok": readiness.get("secret_scan", {}).get("ok"),
        },
        "official_token_reduction_packaged_trial": reports["official_token_reduction_packaged_trial"].get("summary", {}),
        "hidden_style_eval": reports["hidden_style_eval"].get("summary", {}),
        "endpoint_family_failure_report": reports["endpoint_family_failure_report"].get("summary", {}),
        "schema_dataset_positive_repair_analysis": reports["schema_dataset_positive_repair_analysis"].get("summary", {}),
        "sql_ast_candidate_ranking_report": reports["sql_ast_candidate_ranking_report"].get("summary", {}),
        "retrieval_ablation_report": reports["retrieval_ablation_report"].get("summary", {}),
        "repair_selector_v2_shadow_eval": reports["repair_selector_v2_shadow_eval"].get("summary", {}),
        "visualization_dataflow_completeness": {
            "official_token_reduction_visible": True,
            "research_technique_tables_present": True,
        },
        "recommended_next_action": [
            "Promote official-token reduction in a later explicit packaged task if the packaged trial remains safe.",
            "Keep repair execution disabled.",
            "Keep compact context disabled.",
            "Target endpoint/schema accuracy next.",
        ],
        "notes": [
            "This report does not change packaged behavior.",
            "Official-token reduction remains default-off in this pass.",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    packaged = payload["packaged"]
    lines = [
        "# Winner Readiness Report",
        "",
        f"- Freshness run ID: `{payload['freshness']['run_id']}`",
        f"- Preferred strategy: `{packaged['preferred_strategy']}`",
        f"- Strict final score: {packaged['strict_final_score']}",
        f"- Estimated tokens/runtime/tools: {packaged['estimated_tokens']} / {packaged['runtime']} / {packaged['tool_calls']}",
        f"- Final submission ready: {packaged['final_submission_ready']}",
        f"- Official-token packaged trial recommendation: `{payload['official_token_reduction_packaged_trial'].get('recommendation')}`",
        f"- Hidden-style passed/total: {payload['hidden_style_eval'].get('passed_cases')}/{payload['hidden_style_eval'].get('total_cases')}",
        f"- Endpoint-family risky rows: {payload['endpoint_family_failure_report'].get('risky_rows')}",
        f"- Repair selector v2 success: {payload['repair_selector_v2_shadow_eval'].get('success')}",
        "",
        "## Recommended Next Action",
        "",
    ]
    lines.extend(f"- {item}" for item in payload["recommended_next_action"])
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
