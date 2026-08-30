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
from scripts.robustness_improvement_common import counter_dict, load_rows, now_iso, top_examples, write_report


REPORT_STEM = "route_mismatch_root_cause_analysis"


def main() -> int:
    config = Config.from_env(ROOT)
    report = run_route_mismatch_root_cause_analysis(config)
    print(json.dumps({"report": REPORT_STEM, "mismatch_count": report["mismatch_count"]}, indent=2))
    return 0


def run_route_mismatch_root_cause_analysis(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    rows = [row for row in load_rows(config) if row.get("route_matches_diagnostic") is False]
    enriched = [{**row, "likely_cause": _cause(row), "suggested_action": _action(row), "confidence": _confidence(row)} for row in rows]
    candidates = _candidate_fixes(enriched)
    payload: dict[str, Any] = {
        "report_type": REPORT_STEM,
        "generated_at": now_iso(),
        "classification": "diagnostic_only",
        "official_score_claim": False,
        "promotion_allowed": False,
        "runtime_change_applied": False,
        "mismatch_count": len(rows),
        "actual_route_distribution": counter_dict(row.get("actual_route") or row.get("route_type") for row in rows),
        "expected_route_distribution": counter_dict(row.get("expected_route_label") for row in rows),
        "likely_cause_counts": counter_dict(row.get("likely_cause") for row in enriched),
        "candidate_fix_trials": candidates,
        "representative_examples": top_examples(enriched),
        "rows": enriched,
        "recommendation": "No router/runtime fix applied. Generated route labels remain diagnostic; only low-risk deterministic candidates with paraphrase-stability evidence should be trialed.",
    }
    write_report(config, REPORT_STEM, payload, _render_md(payload))
    return payload


def _cause(row: dict[str, Any]) -> str:
    expected = str(row.get("expected_route_label") or "").upper()
    actual = str(row.get("actual_route") or row.get("route_type") or "").upper()
    prompt = str(row.get("prompt") or "").lower()
    if not expected:
        return "generated_label_weakness"
    if "api" in expected.lower() and int(row.get("api_calls") or 0) == 0:
        return "api_need_decision_gap"
    if "sql" in expected.lower() and "api" in actual.lower() and row.get("answer_used_sql_evidence"):
        return "unnecessary_api_call_noise"
    if any(token in prompt for token in ["dataset", "schema", "audience", "segment", "destination", "journey"]):
        return "ambiguous_domain_terms"
    if row.get("template_hit") is False:
        return "no_template_fallback_route_gap"
    return "generated_label_noise"


def _action(row: dict[str, Any]) -> str:
    cause = _cause(row)
    return {
        "api_need_decision_gap": "api_need_recalibration_candidate",
        "unnecessary_api_call_noise": "optional_api_suppression_when_sql_complete_candidate",
        "ambiguous_domain_terms": "domain_token_expansion_candidate",
        "no_template_fallback_route_gap": "confidence_margin_gate_candidate",
        "generated_label_noise": "no_code_change",
        "generated_label_weakness": "no_code_change",
    }.get(cause, "review")


def _confidence(row: dict[str, Any]) -> str:
    if _cause(row) in {"generated_label_noise", "generated_label_weakness"}:
        return "medium"
    if int(row.get("unsupported_claim_count") or 0) == 0 and not row.get("validation_failures"):
        return "low"
    return "medium"


def _candidate_fixes(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates = []
    for name in [
        "conservative_synonym_expansion",
        "confidence_margin_gate",
        "api_need_recalibration",
        "endpoint_family_priority_fix",
    ]:
        relevant = [row for row in rows if _candidate_matches(name, row)]
        candidates.append(
            {
                "variant": name,
                "affected_rows": len(relevant),
                "expected_route_mismatch_delta": -len(relevant),
                "public_dev_strict_delta": "requires_isolated_trial",
                "tool_count_runtime_delta": "unknown_until_trial",
                "paraphrase_consistency_delta": "must_be_non_negative_before_promotion",
                "recommendation": "trial_only" if relevant else "not_applicable",
                "representative_prompt_ids": [row.get("prompt_id") for row in relevant[:10]],
            }
        )
    return candidates


def _candidate_matches(name: str, row: dict[str, Any]) -> bool:
    cause = row.get("likely_cause")
    return {
        "conservative_synonym_expansion": cause == "ambiguous_domain_terms",
        "confidence_margin_gate": cause == "no_template_fallback_route_gap",
        "api_need_recalibration": cause == "api_need_decision_gap",
        "endpoint_family_priority_fix": cause in {"api_need_decision_gap", "ambiguous_domain_terms"},
    }.get(name, False)


def _render_md(report: dict[str, Any]) -> str:
    lines = [
        "# Route Mismatch Root-Cause Analysis",
        "",
        "Generated route labels are diagnostic-only. This report separates likely label noise from conservative deterministic candidates.",
        "",
        f"- Mismatch count: `{report.get('mismatch_count')}`",
        f"- Likely causes: `{report.get('likely_cause_counts')}`",
        "",
        "## Candidate Fix Trials",
        "",
    ]
    for candidate in report.get("candidate_fix_trials", []):
        lines.append(f"- `{candidate.get('variant')}`: affected rows `{candidate.get('affected_rows')}`, recommendation `{candidate.get('recommendation')}`")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
