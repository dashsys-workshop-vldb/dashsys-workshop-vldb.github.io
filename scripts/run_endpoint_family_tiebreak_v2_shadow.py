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
from dashagent.endpoint_family_ranker import endpoint_family_for_endpoint
from dashagent.eval_harness import generated_api_calls
from dashagent.report_run import report_metadata
from scripts.generate_candidate_context_report import generate_candidate_context_report
from scripts.run_official_token_reduction_eval import _load_json, _load_trajectory


OUTPUT_NAME = "endpoint_family_tiebreak_v2_shadow"


def main() -> int:
    config = Config.from_env(ROOT)
    payload = run_endpoint_family_tiebreak_v2_shadow(config)
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    json_path = config.outputs_dir / f"{OUTPUT_NAME}.json"
    md_path = config.outputs_dir / f"{OUTPUT_NAME}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "trial_eligible_rows": payload["summary"]["trial_eligible_rows"]}, indent=2, sort_keys=True))
    return 0


def run_endpoint_family_tiebreak_v2_shadow(config: Config) -> dict[str, Any]:
    candidate_report = _load_json(config.outputs_dir / "candidate_context_report.json") or generate_candidate_context_report(config)
    strict = _load_json(config.outputs_dir / "eval_results_strict.json")
    strict_by_id = {
        str(row.get("query_id")): row
        for row in strict.get("rows", [])
        if row.get("strategy") == "SQL_FIRST_API_VERIFY"
    }
    rows = []
    for candidate_row in candidate_report.get("rows", []):
        query_id = str(candidate_row.get("query_id") or "")
        strict_row = strict_by_id.get(query_id, {})
        if not strict_row:
            continue
        rows.append(_shadow_row(candidate_row, strict_row))
    summary = _summary(rows)
    return {
        **report_metadata(config.outputs_dir),
        "mode": OUTPUT_NAME,
        "feature_flag": "ENABLE_ENDPOINT_FAMILY_TIEBREAK_V2",
        "feature_flag_default": Config.from_env(config.project_root).enable_endpoint_family_tiebreak_v2,
        "shadow_only": True,
        "packaged_execution_changed": False,
        "writes_eval_outputs": False,
        "writes_final_submission": False,
        "rows": rows,
        "summary": summary,
        "notes": [
            "Endpoint-family tie-break v2 is shadow-first only.",
            "Rows enter an isolated packaged trial only when a concrete non-gold candidate has positive projected strict/API delta.",
            "This report does not change planner selection.",
        ],
    }


def _shadow_row(candidate_row: dict[str, Any], strict_row: dict[str, Any]) -> dict[str, Any]:
    endpoint = candidate_row.get("endpoint_family_ranking") or {}
    top_ranked = endpoint.get("top_ranked_apis") or []
    ranked_family = endpoint.get("endpoint_family") or (top_ranked[0].get("endpoint_family") if top_ranked else None)
    trajectory = _load_trajectory(strict_row.get("output_dir"))
    selected_apis = generated_api_calls(trajectory)
    selected_family = endpoint_family_for_endpoint(selected_apis[0].get("path") if selected_apis else "") if selected_apis else None
    confidence = float(endpoint.get("endpoint_family_confidence") or 0.0)
    divergence = bool(ranked_family and selected_family and ranked_family != selected_family)
    projected_api_delta = 0.0
    projected_strict_delta = 0.0
    rejection_reason = "no_family_divergence"
    if divergence and confidence < 0.85:
        rejection_reason = "ranked_family_confidence_below_gate"
    elif divergence:
        rejection_reason = "no_validated_replacement_endpoint_candidate"
    if divergence and confidence >= 0.85 and _strict_api_weak(strict_row):
        # Still shadow-only: positive projection requires a validated candidate
        # endpoint, not just a family divergence.
        rejection_reason = "api_weak_but_missing_validated_candidate_endpoint"
    return {
        "query_id": strict_row.get("query_id"),
        "query": strict_row.get("query"),
        "ranked_endpoint_family": ranked_family,
        "selected_endpoint_family": selected_family,
        "endpoint_family_confidence": round(confidence, 4),
        "top_ranked_apis": top_ranked[:5],
        "selected_api": selected_apis[:3],
        "executed_endpoint_family_differs_from_ranked_family": divergence,
        "divergence_reason": _divergence_reason(divergence, ranked_family, selected_family, confidence),
        "current_api_score": strict_row.get("api_score"),
        "current_strict_score": strict_row.get("final_score"),
        "projected_api_delta": projected_api_delta,
        "projected_strict_delta": projected_strict_delta,
        "positive_projected_delta": projected_api_delta > 0 or projected_strict_delta > 0,
        "eligible_for_isolated_packaged_trial": False,
        "rejection_reason": rejection_reason,
        "shadow_only": True,
    }


def _strict_api_weak(strict_row: dict[str, Any]) -> bool:
    value = strict_row.get("api_score")
    return value is not None and float(value or 0.0) < 1.0


def _divergence_reason(divergence: bool, ranked_family: Any, selected_family: Any, confidence: float) -> str:
    if not ranked_family and not selected_family:
        return "no_ranked_or_selected_api_family"
    if not selected_family:
        return "no_api_executed"
    if not ranked_family:
        return "no_ranked_endpoint_family"
    if not divergence:
        return "selected_family_matches_ranked_family"
    if confidence < 0.85:
        return "divergence_observed_but_ranked_confidence_below_override_gate"
    return "divergence_observed_requires_validated_candidate_before_trial"


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    divergences = [row for row in rows if row.get("executed_endpoint_family_differs_from_ranked_family")]
    trial_eligible = [row for row in rows if row.get("eligible_for_isolated_packaged_trial")]
    return {
        "total_rows": len(rows),
        "divergence_rows": len(divergences),
        "trial_eligible_rows": len(trial_eligible),
        "positive_projected_delta_rows": sum(1 for row in rows if row.get("positive_projected_delta")),
        "shadow_only": True,
        "packaged_execution_changed": False,
        "recommendation": "run_isolated_packaged_trial" if trial_eligible else "keep_shadow_only",
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Endpoint-Family Tie-Break v2 Shadow Report",
        "",
        f"- Rows: {summary['total_rows']}",
        f"- Divergence rows: {summary['divergence_rows']}",
        f"- Trial-eligible rows: {summary['trial_eligible_rows']}",
        f"- Recommendation: `{summary['recommendation']}`",
        "",
        "| Query ID | Ranked family | Selected family | Confidence | Projected API Δ | Projected strict Δ | Rejection |",
        "| --- | --- | --- | ---: | ---: | ---: | --- |",
    ]
    for row in payload["rows"]:
        if not row.get("executed_endpoint_family_differs_from_ranked_family"):
            continue
        lines.append(
            f"| `{row.get('query_id')}` | {row.get('ranked_endpoint_family')} | {row.get('selected_endpoint_family')} | "
            f"{row.get('endpoint_family_confidence')} | {row.get('projected_api_delta')} | {row.get('projected_strict_delta')} | {row.get('rejection_reason')} |"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
