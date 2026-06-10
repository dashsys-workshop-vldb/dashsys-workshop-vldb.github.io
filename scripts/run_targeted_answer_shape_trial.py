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
from scripts.robustness_improvement_common import load_rows, now_iso, strict_metrics, top_examples, write_report


REPORT_STEM = "targeted_answer_shape_trial"


VARIANTS = [
    "count_direct_first",
    "list_compact_with_ids_when_present",
    "status_direct_first",
    "live_empty_clear_no_results",
    "api_error_clear_but_not_no_data",
    "sql_api_conflict_explicit",
    "evidence_source_suffix_minimal",
]


def main() -> int:
    config = Config.from_env(ROOT)
    report = run_targeted_answer_shape_trial(config)
    print(json.dumps({"report": REPORT_STEM, "recommendation": report["recommendation"]}, indent=2))
    return 0


def run_targeted_answer_shape_trial(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    rows = [row for row in load_rows(config) if _eligible(row)]
    variant_results = [_variant_result(variant, rows) for variant in VARIANTS]
    best = max(variant_results, key=lambda item: (item["estimated_helped_rows"], -item["risk_rank"]), default=None)
    strict = strict_metrics(config)
    implementation_ready = bool(best and best["estimated_helped_rows"] >= 3 and best["risk_level"] == "low")
    payload: dict[str, Any] = {
        "report_type": REPORT_STEM,
        "generated_at": now_iso(),
        "classification": "diagnostic_only",
        "official_score_claim": False,
        "promotion_allowed": False,
        "runtime_change_applied": False,
        "invariant": "SQL/API tool calls and evidence are unchanged; variants are simulated answer-slot/template candidates only.",
        "strict_score_reference": strict.get("avg_final_score"),
        "eligible_rows": len(rows),
        "variants": variant_results,
        "best_variant": best,
        "implementation_ready": implementation_ready,
        "recommendation": (
            "No runtime answer-shape fix applied in this pass; variants remain isolated diagnostics until strict/hidden/generated robustness gates are rerun."
        ),
        "representative_examples": top_examples(rows),
    }
    write_report(config, REPORT_STEM, payload, _render_md(payload))
    return payload


def _eligible(row: dict[str, Any]) -> bool:
    if int(row.get("unsupported_claim_count") or 0) != 0:
        return False
    if str(row.get("failure_category") or "") == "answer_shape_weak":
        return True
    if row.get("answer_intent_matches_diagnostic") is False:
        return True
    return bool(row.get("vague_or_evidence_unused")) and (row.get("answer_used_sql_evidence") or row.get("answer_used_live_api_evidence"))


def _variant_result(variant: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    matched = [row for row in rows if _variant_matches(variant, row)]
    risk = _risk(variant)
    return {
        "variant": variant,
        "estimated_helped_rows": len(matched),
        "estimated_hurt_rows": 0 if risk == "low" else "unknown_without_strict_trial",
        "unsupported_claim_delta": 0,
        "tool_call_delta": 0,
        "token_delta": "small_positive_or_neutral" if variant != "evidence_source_suffix_minimal" else "small_negative",
        "risk_level": risk,
        "risk_rank": {"low": 0, "medium": 1, "high": 2}[risk],
        "strict_trial_required": True,
        "representative_prompt_ids": [row.get("prompt_id") for row in matched[:10]],
    }


def _variant_matches(variant: str, row: dict[str, Any]) -> bool:
    intent = str(row.get("actual_answer_intent") or row.get("answer_intent") or "").upper()
    answer = str(row.get("final_answer") or "").lower()
    if variant == "count_direct_first":
        return intent == "COUNT" or "count" in answer or "how many" in str(row.get("prompt") or "").lower()
    if variant == "list_compact_with_ids_when_present":
        return intent == "LIST" or "list" in str(row.get("prompt") or "").lower()
    if variant == "status_direct_first":
        return intent == "STATUS" or "status" in str(row.get("prompt") or "").lower() or "state" in answer
    if variant == "live_empty_clear_no_results":
        return int(row.get("live_empty_count") or 0) > 0
    if variant == "api_error_clear_but_not_no_data":
        return int(row.get("api_error_count") or 0) > 0
    if variant == "sql_api_conflict_explicit":
        return "conflict" in str(row.get("evidence_state") or "").lower()
    if variant == "evidence_source_suffix_minimal":
        return bool(row.get("answer_used_sql_evidence") or row.get("answer_used_live_api_evidence"))
    return False


def _risk(variant: str) -> str:
    return "medium" if variant in {"evidence_source_suffix_minimal", "api_error_clear_but_not_no_data"} else "low"


def _render_md(report: dict[str, Any]) -> str:
    lines = [
        "# Targeted Answer Shape Trial",
        "",
        "This is an isolated diagnostic. It does not enable broad answer rewriting and does not change SQL/API evidence.",
        "",
        f"- Eligible rows: `{report.get('eligible_rows')}`",
        f"- Best variant: `{(report.get('best_variant') or {}).get('variant')}`",
        f"- Recommendation: {report.get('recommendation')}",
        "",
        "## Variants",
        "",
    ]
    for variant in report.get("variants", []):
        lines.append(
            f"- `{variant.get('variant')}` helped `{variant.get('estimated_helped_rows')}`, risk `{variant.get('risk_level')}`, tool delta `{variant.get('tool_call_delta')}`"
        )
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
