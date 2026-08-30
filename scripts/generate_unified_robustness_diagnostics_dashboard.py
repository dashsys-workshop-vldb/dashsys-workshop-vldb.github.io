#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.planner import PACKAGED_DEFAULT_STRATEGY
from scripts.robustness_diagnostics_common import read_json, write_json_md


REPORTS = {
    "score_provenance": "score_provenance_audit.json",
    "hardcode": "hardcoded_runtime_and_score_path_audit.json",
    "objective_features": "objective_prompt_feature_diagnostic.json",
    "semantic_routing": "semantic_routing_diagnostic.json",
    "staged_evidence": "staged_evidence_policy_diagnostic.json",
    "answer_grounding": "answer_grounding_diagnostic.json",
    "baseline_drift": "strict_baseline_drift_diagnostic.json",
    "conversion_500": "500_organizer_style_conversion_diagnostic.json",
}


def build_dashboard(reports_dir: Path = ROOT / "outputs" / "reports") -> dict[str, Any]:
    loaded = {key: read_json(reports_dir / filename) for key, filename in REPORTS.items()}
    score_entries = loaded["score_provenance"].get("entries") or []
    hardcode = loaded["hardcode"]
    dashboard = {
        "report_type": "unified_robustness_diagnostics_dashboard",
        "packaged_default_strategy": PACKAGED_DEFAULT_STRATEGY,
        "promotion_applied": False,
        "score_provenance_summary": loaded["score_provenance"].get("summary", {}),
        "score_sources": score_entries,
        "hardcode_fake_score_audit_summary": {
            "unsafe_runtime_hardcode_count": hardcode.get("unsafe_runtime_hardcode_count"),
            "unsafe_fake_score_count": hardcode.get("unsafe_fake_score_count"),
            "legacy_simulated_diagnostic_count": hardcode.get("legacy_simulated_diagnostic_count"),
        },
        "runtime_leakage_audit_summary": {
            "runtime_leakage_detected": hardcode.get("runtime_leakage_detected"),
            "classification_counts": hardcode.get("classification_counts", {}),
        },
        "organizer_35_strict_summary": read_json(ROOT / "outputs" / "eval_results_strict.json").get("summary", {}),
        "internal_500_heuristic_summary": read_json(reports_dir / "dashagent_500_prompt_suite_eval_real.json").get("modes", {}),
        "internal_500_organizer_style_summary": read_json(reports_dir / "dashagent_500_organizer_style_strict_comparison.json").get("summary", {}),
        "semantic_routing_summary": {
            "action_distribution": loaded["semantic_routing"].get("action_distribution"),
            "concrete_data_prompt_wrong_no_tool_count": loaded["semantic_routing"].get("concrete_data_prompt_wrong_no_tool_count"),
            "false_no_tool_risk_count": loaded["semantic_routing"].get("false_no_tool_risk_count"),
        },
        "staged_evidence_summary": loaded["staged_evidence"].get("summary_counts", {}),
        "answer_grounding_bottleneck_summary": loaded["answer_grounding"].get("failure_class_counts", {}),
        "baseline_drift_summary": loaded["baseline_drift"].get("summary", {}),
        "api_validation_safety_summary": {
            "unresolved_placeholder_blocking_retained": True,
            "api_validator_hardening_effect": read_json(reports_dir / "final_gate_strict_drift_audit.json").get("api_validator_hardening", {}),
        },
        "promotion_eligibility_summary": {
            "simulated_trace_promotion_eligible": False,
            "internal_500_heuristic_organizer_equivalent": False,
            "internal_500_organizer_style_organizer_equivalent": False,
            "packaged_default_changed": PACKAGED_DEFAULT_STRATEGY != "SQL_FIRST_API_VERIFY",
            "next_recommended_focus": _next_focus(loaded),
        },
    }
    return dashboard


def _next_focus(loaded: dict[str, Any]) -> str:
    answer_counts = loaded["answer_grounding"].get("failure_class_counts", {})
    if answer_counts.get("missing_required_fact") or answer_counts.get("evidence_available_but_not_rendered"):
        return "answer_grounding_next_focus"
    drift = (loaded["baseline_drift"].get("summary") or {}).get("baseline_drift_risk")
    if drift:
        return "baseline_drift_needs_resolution"
    if (loaded["semantic_routing"].get("concrete_data_prompt_wrong_no_tool_count") or 0) > 0:
        return "semantic_routing_next_focus"
    return "staged_policy_next_focus"


def main() -> int:
    dashboard = build_dashboard()
    lines = [
        "# Unified Robustness Diagnostics Dashboard",
        "",
        f"- Packaged default strategy: `{dashboard['packaged_default_strategy']}`",
        f"- Promotion applied: `{str(dashboard['promotion_applied']).lower()}`",
        f"- Simulated trace promotion eligible: `{str(dashboard['promotion_eligibility_summary']['simulated_trace_promotion_eligible']).lower()}`",
        f"- Unsafe runtime hardcodes: `{dashboard['hardcode_fake_score_audit_summary'].get('unsafe_runtime_hardcode_count')}`",
        f"- Unsafe fake score hits: `{dashboard['hardcode_fake_score_audit_summary'].get('unsafe_fake_score_count')}`",
        f"- Semantic action distribution: `{dashboard['semantic_routing_summary'].get('action_distribution')}`",
        f"- Answer grounding classes: `{dashboard['answer_grounding_bottleneck_summary']}`",
        f"- Next focus: `{dashboard['promotion_eligibility_summary']['next_recommended_focus']}`",
        "",
        "The dashboard separates organizer-equivalent strict scores, internal heuristic scores, converted stress scores, trace observability, and simulated diagnostics.",
    ]
    write_json_md("unified_robustness_diagnostics_dashboard", dashboard, lines)
    print(json.dumps(dashboard["promotion_eligibility_summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
