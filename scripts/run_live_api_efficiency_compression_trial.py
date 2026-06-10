#!/usr/bin/env python
from __future__ import annotations

import json
import sys
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from scripts.robustness_improvement_common import load_rows, mean_number, now_iso, strict_metrics, write_report


REPORT_STEM = "live_api_efficiency_compression_trial"


VARIANTS = [
    "compact_api_raw_preview",
    "evidencebus_field_projection",
    "endpoint_family_summary_schema",
    "remove_unused_live_payload_fields_from_answer_context",
    "compact_pagination_metadata",
    "keep_full_raw_only_in_diagnostic_reports",
]


def main() -> int:
    config = Config.from_env(ROOT)
    report = run_live_api_efficiency_compression_trial(config)
    print(json.dumps({"report": REPORT_STEM, "recommendation": report["recommendation"]}, indent=2))
    return 0


def run_live_api_efficiency_compression_trial(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    rows = [row for row in load_rows(config) if int(row.get("api_calls") or 0) > 0]
    token_values = [int(row.get("tokens") or 0) for row in rows if isinstance(row.get("tokens"), int)]
    high_token_rows = [row for row in sorted(rows, key=lambda item: int(item.get("tokens") or 0), reverse=True)[:25]]
    variants = [_variant_result(name, rows, high_token_rows) for name in VARIANTS]
    payload: dict[str, Any] = {
        "report_type": REPORT_STEM,
        "generated_at": now_iso(),
        "classification": "diagnostic_only",
        "official_score_claim": False,
        "promotion_allowed": False,
        "runtime_change_applied": False,
        "strict_score_reference": strict_metrics(config).get("avg_final_score"),
        "api_prompt_rows": len(rows),
        "average_tokens_with_api": round(mean(token_values), 4) if token_values else None,
        "average_runtime_with_api": mean_number(rows, "runtime"),
        "average_tool_count_with_api": mean_number(rows, "tool_count"),
        "largest_token_rows": [
            {
                "prompt_id": row.get("prompt_id"),
                "tokens": row.get("tokens"),
                "api_calls": row.get("api_calls"),
                "api_outcomes": row.get("api_outcomes"),
                "endpoint_selected": row.get("endpoint_selected"),
            }
            for row in high_token_rows[:10]
        ],
        "variants": variants,
        "safe_fields_to_consider_compacting": [
            "raw response preview beyond parsed IDs/names/statuses/counts/timestamps",
            "repeated pagination metadata when not referenced by answer slots",
            "diagnostic-only API item fields not selected by EvidenceBus",
        ],
        "fields_not_safe_to_remove": [
            "endpoint path/method/params",
            "outcome/evidence_state/parser_status",
            "IDs, names, statuses, counts, timestamps used by answer slots",
            "redacted API error category and safe excerpt",
        ],
        "recommendation": "Keep trial-only. The safest next implementation candidate is compact_api_raw_preview, but it still needs strict/hidden/submission validation before promotion.",
    }
    write_report(config, REPORT_STEM, payload, _render_md(payload))
    return payload


def _variant_result(name: str, rows: list[dict[str, Any]], high_token_rows: list[dict[str, Any]]) -> dict[str, Any]:
    affected = _affected(name, rows, high_token_rows)
    return {
        "variant": name,
        "affected_rows": len(affected),
        "estimated_token_delta": _token_delta(name, affected),
        "estimated_runtime_delta": "small_positive" if affected else "none",
        "strict_score_delta": "requires_isolated_trial",
        "answer_score_delta": "requires_isolated_trial",
        "unsupported_claim_delta": 0,
        "final_submission_format_risk": "low" if name in {"compact_api_raw_preview", "compact_pagination_metadata"} else "medium",
        "recommendation": "implementation_candidate" if name == "compact_api_raw_preview" and affected else "trial_only",
        "representative_prompt_ids": [row.get("prompt_id") for row in affected[:10]],
    }


def _affected(name: str, rows: list[dict[str, Any]], high_token_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if name in {"compact_api_raw_preview", "keep_full_raw_only_in_diagnostic_reports"}:
        return high_token_rows
    if name == "evidencebus_field_projection":
        return [row for row in rows if row.get("answer_used_live_api_evidence")]
    if name == "endpoint_family_summary_schema":
        return [row for row in rows if int(row.get("live_success_count") or 0) > 0]
    if name == "remove_unused_live_payload_fields_from_answer_context":
        return [row for row in rows if not row.get("answer_used_live_api_evidence")]
    if name == "compact_pagination_metadata":
        return [row for row in rows if int(row.get("api_calls") or 0) > 0]
    return []


def _token_delta(name: str, rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "none"
    if name in {"compact_api_raw_preview", "keep_full_raw_only_in_diagnostic_reports"}:
        return "medium_positive"
    if name in {"evidencebus_field_projection", "endpoint_family_summary_schema"}:
        return "small_to_medium_positive"
    return "small_positive"


def _render_md(report: dict[str, Any]) -> str:
    lines = [
        "# Live API Efficiency Compression Trial",
        "",
        "This diagnostic estimates safe live API token/runtime compression opportunities without changing runtime payload handling.",
        "",
        f"- API prompt rows: `{report.get('api_prompt_rows')}`",
        f"- Average tokens with API: `{report.get('average_tokens_with_api')}`",
        f"- Average runtime with API: `{report.get('average_runtime_with_api')}`",
        f"- Recommendation: {report.get('recommendation')}",
        "",
        "## Variants",
        "",
    ]
    for variant in report.get("variants", []):
        lines.append(f"- `{variant.get('variant')}`: affected `{variant.get('affected_rows')}`, token delta `{variant.get('estimated_token_delta')}`, recommendation `{variant.get('recommendation')}`")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
