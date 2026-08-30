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
from scripts.robustness_improvement_common import load_json, now_iso, strict_metrics, write_report


REPORT_STEM = "generated_unsupported_claim_fix_trial"
VARIANTS = [
    "answer_guard_only",
    "api_state_payload_separation",
    "evidence_linking_fix",
    "parser_field_fix",
    "verifier_false_positive_fix",
    "combined_safe_unsupported_claim_fix",
]


def main() -> int:
    config = Config.from_env(ROOT)
    report = run_generated_unsupported_claim_fix_trial(config)
    print(
        json.dumps(
            {
                "report": REPORT_STEM,
                "recommendation": report["recommendation"],
                "runtime_change_applied": report["runtime_change_applied"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def run_generated_unsupported_claim_fix_trial(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    audit = load_json(config.outputs_dir / "reports" / "generated_unsupported_claims_audit.json")
    generated = load_json(config.outputs_dir / "reports" / "full_generated_prompt_suite_diagnostic.json")
    rows = audit.get("rows") if isinstance(audit.get("rows"), list) else []
    previous_rows = audit.get("previous_gate_rows") if isinstance(audit.get("previous_gate_rows"), list) else []
    trial_rows = rows or previous_rows
    strict = strict_metrics(config)
    variants = [_variant_result(name, trial_rows, generated, strict, previous_rows) for name in VARIANTS]
    recommended = _recommend(variants, strict)
    payload: dict[str, Any] = {
        "report_type": REPORT_STEM,
        "generated_at": now_iso(),
        "diagnostic_only": True,
        "official_score_claim": False,
        "runtime_change_applied": bool(previous_rows and int(generated.get("unsupported_claim_count") or 0) == 0),
        "promotion_allowed": False,
        "baseline": {
            "unsupported_claim_count": generated.get("unsupported_claim_count"),
            "previous_gate_unsupported_claim_count": sum(int(row.get("unsupported_claim_count") or 0) for row in previous_rows),
            "generated_runtime_pass_count": generated.get("runtime_pass_count"),
            "generated_validation_fail_count": generated.get("validation_fail_count"),
            "strict_score": strict.get("avg_final_score"),
        },
        "variants": variants,
        "recommendation": recommended["recommendation"],
        "reason": recommended["reason"],
        "required_gate": {
            "generated_unsupported_claims_decrease": True,
            "strict_score_at_or_above_reference": 0.6553,
            "hidden_style_48_of_48": True,
            "check_submission_ready_ok": True,
            "endpoint_matrix_clean": True,
            "no_new_unsupported_claims": True,
            "final_submission_format_unchanged": True,
        },
    }
    write_report(config, REPORT_STEM, payload, _render_md(payload))
    return payload


def _variant_result(
    name: str,
    rows: list[dict[str, Any]],
    generated: dict[str, Any],
    strict: dict[str, Any],
    previous_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    categories = [row.get("claim_category") for row in rows]
    false_positive_count = categories.count("verifier_false_positive")
    generic_entity_count = categories.count("fabricated_name_or_id")
    baseline_unsupported = sum(int(row.get("unsupported_claim_count") or 0) for row in previous_rows) or int(generated.get("unsupported_claim_count") or 0)
    observed_after = int(generated.get("unsupported_claim_count") or 0)
    after = baseline_unsupported
    risk = "medium"
    applies_to: list[str] = []
    if name == "verifier_false_positive_fix":
        after = max(0, baseline_unsupported - false_positive_count)
        risk = "low"
        applies_to = ["status token extraction for Live inside evidence-backed title text"]
    elif name == "answer_guard_only":
        after = max(0, baseline_unsupported - generic_entity_count)
        risk = "low"
        applies_to = ["generic schema detail answer wording"]
    elif name == "combined_safe_unsupported_claim_fix":
        after = max(0, baseline_unsupported - false_positive_count - generic_entity_count)
        risk = "low"
        applies_to = [
            "status token extraction for Live inside evidence-backed title text",
            "generic schema detail answer wording",
        ]
    elif name == "api_state_payload_separation":
        after = baseline_unsupported
        risk = "low"
        applies_to = ["not indicated by this audit"]
    elif name == "evidence_linking_fix":
        after = baseline_unsupported
        risk = "medium"
        applies_to = ["no evidence-linking row isolated"]
    elif name == "parser_field_fix":
        after = baseline_unsupported
        risk = "medium"
        applies_to = ["no parser-missing-field row isolated"]
    return {
        "variant": name,
        "unsupported_claims_before": baseline_unsupported,
        "projected_unsupported_claims_after": after,
        "observed_unsupported_claims_after_current_patch": observed_after,
        "generated_runtime_pass_count": generated.get("runtime_pass_count"),
        "generated_validation_fail_count": generated.get("validation_fail_count"),
        "public_dev_strict_score_current": strict.get("avg_final_score"),
        "public_dev_strict_score_delta_projected": "requires_runtime_validation",
        "hidden_style_result": "not_run_in_trial_script",
        "endpoint_matrix_status": "not_run_in_trial_script",
        "answer_score_delta_projected": "requires_runtime_validation",
        "rows_helped": baseline_unsupported - after,
        "rows_hurt": 0 if name in {"verifier_false_positive_fix", "answer_guard_only", "combined_safe_unsupported_claim_fix"} else "unknown",
        "risk": risk,
        "applies_to": applies_to,
        "recommendation": "candidate_for_runtime_validation" if after < baseline_unsupported and risk == "low" else "do_not_promote",
    }


def _recommend(variants: list[dict[str, Any]], strict: dict[str, Any]) -> dict[str, str]:
    best = min(variants, key=lambda item: int(item.get("projected_unsupported_claims_after") or 9999))
    if best.get("recommendation") != "candidate_for_runtime_validation":
        return {"recommendation": "no_runtime_change", "reason": "No low-risk variant reduces unsupported claims."}
    if float(strict.get("avg_final_score") or 0.0) < 0.6553:
        return {
            "recommendation": "candidate_requires_full_gate_validation",
            "reason": "A low-risk unsupported-claim fix is available, but strict score is currently below the non-regression reference and must be revalidated after any patch.",
        }
    return {"recommendation": "candidate_requires_full_gate_validation", "reason": "Low-risk candidate exists but this script does not promote runtime behavior."}


def _render_md(report: dict[str, Any]) -> str:
    lines = [
        "# Generated Unsupported Claim Fix Trial",
        "",
        "This is an isolated diagnostic trial. It does not change runtime behavior or claim promotion.",
        "",
        f"- Baseline unsupported claims: `{report['baseline'].get('unsupported_claim_count')}`",
        f"- Current strict score: `{report['baseline'].get('strict_score')}`",
        f"- Recommendation: `{report.get('recommendation')}`",
        f"- Reason: {report.get('reason')}",
        "",
        "## Variants",
        "",
    ]
    for variant in report.get("variants", []):
        lines.extend(
            [
                f"### {variant.get('variant')}",
                "",
                f"- Projected unsupported claims after: `{variant.get('projected_unsupported_claims_after')}`",
                f"- Rows helped: `{variant.get('rows_helped')}`",
                f"- Risk: `{variant.get('risk')}`",
                f"- Recommendation: `{variant.get('recommendation')}`",
                "",
            ]
        )
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
