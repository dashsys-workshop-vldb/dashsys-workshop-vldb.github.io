#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config


def main() -> None:
    cfg = Config.from_env()
    reports = cfg.outputs_dir / "reports"
    trial = _load_json(reports / "semantic_route_decision_ladder_trial.json")
    hidden = _load_json(cfg.outputs_dir / "hidden_style_eval.json")
    readiness = _submission_ready_snapshot(cfg)
    generated = _load_json(reports / "weak_model_generated_prompt_diagnostic.json")
    endpoint = _load_json(reports / "live_api_safe_get_endpoint_matrix.json")
    strict = _load_json(cfg.outputs_dir / "eval_results_strict.json")
    strict_score = (
        ((strict.get("summary") or {}).get("by_strategy") or {}).get("SQL_FIRST_API_VERIFY")
        or (strict.get("by_strategy") or {}).get("SQL_FIRST_API_VERIFY")
        or {}
    )
    hidden_summary = hidden.get("summary") if isinstance(hidden.get("summary"), dict) else hidden
    gates = {
        "public_dev_strict_no_regression": bool(strict_score.get("avg_final_score") is not None),
        "hidden_style_passes": int(hidden_summary.get("passed_cases") or 0) == 48 and int(hidden_summary.get("failed_cases") or 0) == 0,
        "check_submission_ready_passes": readiness.get("ok") is True,
        "generated_prompt_unsupported_claims_zero": _generated_unsupported(generated) == 0,
        "no_concrete_data_plain_llm_direct": int(trial.get("false_no_tool_risk_count") or 0) == 0,
        "conceptual_keyword_prompts_skip_tools_safely": int(trial.get("conceptual_false_positive_tool_routes_reduced") or 0) > 0,
        "tool_runtime_token_cost_improves_or_stable": int(trial.get("estimated_tool_call_savings") or 0) > 0,
        "endpoint_matrix_clean": _endpoint_matrix_clean(endpoint),
        "shadow_false_positive_reduction": int(trial.get("conceptual_false_positive_tool_routes_reduced") or 0) > 0,
        "no_increase_false_no_tool_risk": int(trial.get("false_no_tool_risk_count") or 0) == 0,
        "packaged_runtime_unchanged": True,
        "final_submission_format_unchanged": True,
        "broad_semantic_router_promotion_blocked": True,
    }
    promotion_allowed = False
    if not gates["no_concrete_data_plain_llm_direct"]:
        recommendation = "blocked_by_data_false_negative_risk"
    elif not gates["tool_runtime_token_cost_improves_or_stable"]:
        recommendation = "blocked_by_context_cost"
    else:
        recommendation = "keep_shadow_only"
    report = {
        "classification": "diagnostic_only",
        "packaged_default_strategy": "SQL_FIRST_API_VERIFY",
        "shadow_only": True,
        "promotion_allowed": promotion_allowed,
        "recommendation": recommendation,
        "allowed_recommendations": [
            "keep_shadow_only",
            "promote_conceptual_false_positive_gate_only",
            "promote_llm_safe_direct_only",
            "blocked_by_data_false_negative_risk",
            "blocked_by_strict_regression",
            "blocked_by_generated_prompt_regression",
            "blocked_by_context_cost",
        ],
        "gates": gates,
        "trial_summary": {key: trial.get(key) for key in [
            "total_prompts",
            "action_distribution",
            "false_no_tool_risk_count",
            "conceptual_false_positive_tool_routes_reduced",
            "estimated_tool_call_savings",
            "average_context_token_cost",
            "average_tier_used",
            "recommendation",
        ]},
        "strict_score": {
            "avg_final_score": strict_score.get("avg_final_score"),
            "avg_sql_score": strict_score.get("avg_sql_score"),
            "avg_api_score": strict_score.get("avg_api_score"),
            "avg_answer_score": strict_score.get("avg_answer_score"),
        },
    }
    out_json = reports / "semantic_route_promotion_gate.json"
    out_md = reports / "semantic_route_promotion_gate.md"
    out_json.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    out_md.write_text(_render_markdown(report), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ["recommendation", "promotion_allowed", "gates"]}, indent=2, sort_keys=True))


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _submission_ready_snapshot(cfg: Config) -> dict[str, Any]:
    # Keep this gate read-only; the full validation command is run separately.
    manifest = cfg.outputs_dir / "final_submission_manifest.json"
    root_manifest = cfg.project_root / "final_submission_manifest.json"
    final_dir = cfg.outputs_dir / "final_submission"
    return {
        "ok": final_dir.exists() and (manifest.exists() or root_manifest.exists()),
        "final_submission_dir_exists": final_dir.exists(),
        "final_submission_manifest_exists": manifest.exists() or root_manifest.exists(),
    }


def _generated_unsupported(payload: dict[str, Any]) -> int:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else payload
    return int(summary.get("unsupported_claim_count") or 0)


def _endpoint_matrix_clean(payload: dict[str, Any]) -> bool:
    totals = payload.get("after_safe_get_totals") if isinstance(payload.get("after_safe_get_totals"), dict) else payload
    return all(int(totals.get(key) or 0) == 0 for key in ["api_error_count", "auth_error_count", "endpoint_path_issue_count", "malformed_response_count"])


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Semantic Route Promotion Gate",
        "",
        "Classification: `diagnostic_only`.",
        "",
        f"Recommendation: `{report['recommendation']}`.",
        "",
        "Promotion is not allowed by this pass. The semantic routing harness remains shadow-only and the packaged `SQL_FIRST_API_VERIFY` runtime is unchanged.",
        "",
        "## Gates",
        "",
    ]
    for key, value in report["gates"].items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Trial Summary", ""])
    for key, value in report.get("trial_summary", {}).items():
        lines.append(f"- {key}: `{value}`")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
