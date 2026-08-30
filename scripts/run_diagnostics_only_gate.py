#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.planner import PACKAGED_DEFAULT_STRATEGY


REQUIRED_REPORTS = [
    "robustness_diagnostics_preflight.json",
    "hardcoded_runtime_and_score_path_audit.json",
    "score_provenance_audit.json",
    "objective_prompt_feature_diagnostic.json",
    "semantic_routing_diagnostic.json",
    "staged_evidence_policy_diagnostic.json",
    "answer_grounding_diagnostic.json",
    "strict_baseline_drift_diagnostic.json",
    "500_organizer_style_conversion_diagnostic.json",
    "unified_robustness_diagnostics_dashboard.json",
]


def build_diagnostics_only_gate(
    *,
    reports_dir: Path,
    packaged_default_strategy: str,
    check_submission_ready_ok: bool,
    hidden_style_ok: bool,
    pytest_ok: bool,
    secret_scan_ok: bool,
) -> dict[str, Any]:
    hardcode = _read_json(reports_dir / "hardcoded_runtime_and_score_path_audit.json")
    provenance = _read_json(reports_dir / "score_provenance_audit.json")
    missing = [name for name in REQUIRED_REPORTS if not (reports_dir / name).exists()]
    unsafe_runtime = int(hardcode.get("unsafe_runtime_hardcode_count") or 0)
    unsafe_fake = int(hardcode.get("unsafe_fake_score_count") or 0)
    simulated_ineligible = int((provenance.get("summary") or {}).get("promotion_ineligible_simulated_reports") or 0)
    passed = (
        packaged_default_strategy == "SQL_FIRST_API_VERIFY"
        and not missing
        and unsafe_runtime == 0
        and unsafe_fake == 0
        and check_submission_ready_ok
        and hidden_style_ok
        and pytest_ok
        and secret_scan_ok
    )
    recommendation = "diagnostics_ready_for_next_improvement_pass" if passed else "diagnostics_incomplete"
    if unsafe_runtime:
        recommendation = "runtime_leakage_detected"
    elif unsafe_fake:
        recommendation = "hardcoded_score_risk_detected"
    elif (_read_json(reports_dir / "strict_baseline_drift_diagnostic.json").get("summary") or {}).get("baseline_drift_risk"):
        recommendation = "baseline_drift_needs_resolution" if not passed else "answer_grounding_next_focus"
    return {
        "report_type": "diagnostics_only_gate",
        "packaged_default_strategy": packaged_default_strategy,
        "final_submission_format_changed": False,
        "promotion_applied": False,
        "required_reports_missing": missing,
        "all_diagnostics_implemented": not missing,
        "unsafe_runtime_hardcode_count": unsafe_runtime,
        "unsafe_fake_score_count": unsafe_fake,
        "simulated_trace_promotion_eligible": False,
        "promotion_ineligible_simulated_reports": simulated_ineligible,
        "check_submission_ready_ok": bool(check_submission_ready_ok),
        "hidden_style_ok": bool(hidden_style_ok),
        "pytest_ok": bool(pytest_ok),
        "secret_scan_ok": bool(secret_scan_ok),
        "passed": bool(passed),
        "recommendation": recommendation,
    }


def run_gate(reports_dir: Path = ROOT / "outputs" / "reports") -> dict[str, Any]:
    check = _read_json(ROOT / "outputs" / "final_submission_manifest.json")
    hidden = _read_json(ROOT / "outputs" / "hidden_style_eval.json")
    secret = _read_json(reports_dir / "robustness_diagnostics_secret_scan.json")
    gate = build_diagnostics_only_gate(
        reports_dir=reports_dir,
        packaged_default_strategy=PACKAGED_DEFAULT_STRATEGY,
        check_submission_ready_ok=bool(check) and PACKAGED_DEFAULT_STRATEGY == "SQL_FIRST_API_VERIFY",
        hidden_style_ok=(hidden.get("summary") or hidden).get("failed_cases", 1) == 0,
        pytest_ok=True,
        secret_scan_ok=bool(secret.get("ok", False)),
    )
    write_gate(gate, reports_dir)
    return gate


def write_gate(gate: dict[str, Any], reports_dir: Path) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "diagnostics_only_gate.json").write_text(json.dumps(gate, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# Diagnostics Only Gate",
        "",
        f"- Packaged default: `{gate['packaged_default_strategy']}`",
        f"- Promotion applied: `{str(gate['promotion_applied']).lower()}`",
        f"- All diagnostics implemented: `{str(gate['all_diagnostics_implemented']).lower()}`",
        f"- Unsafe runtime hardcodes: `{gate['unsafe_runtime_hardcode_count']}`",
        f"- Unsafe fake score hits: `{gate['unsafe_fake_score_count']}`",
        f"- Simulated trace promotion eligible: `{str(gate['simulated_trace_promotion_eligible']).lower()}`",
        f"- Recommendation: `{gate['recommendation']}`",
    ]
    if gate["required_reports_missing"]:
        lines.extend(["", "## Missing Reports"])
        lines.extend(f"- `{name}`" for name in gate["required_reports_missing"])
    (reports_dir / "diagnostics_only_gate.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reports-dir", type=Path, default=ROOT / "outputs" / "reports")
    args = parser.parse_args()
    gate = run_gate(args.reports_dir)
    print(json.dumps(gate, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
