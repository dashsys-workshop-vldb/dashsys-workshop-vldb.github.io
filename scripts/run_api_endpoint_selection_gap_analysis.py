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
from scripts.robustness_improvement_common import counter_dict, load_json, load_rows, now_iso, top_examples, write_report


REPORT_STEM = "api_endpoint_selection_gap_analysis"


def main() -> int:
    config = Config.from_env(ROOT)
    report = run_api_endpoint_selection_gap_analysis(config)
    print(json.dumps({"report": REPORT_STEM, "gap_count": report["gap_count"]}, indent=2))
    return 0


def run_api_endpoint_selection_gap_analysis(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    rows = [row for row in load_rows(config) if _is_gap(row)]
    live_matrix = (load_json(config.outputs_dir / "reports" / "live_api_readiness_smoke.json").get("outcome_counts") or {})
    enriched = [{**row, "gap_type": _gap_type(row), "recommended_fix_type": _fix_type(row)} for row in rows]
    trials = [_trial(name, enriched) for name in [
        "live_endpoint_health_ranking",
        "parser_supported_endpoint_boost",
        "optional_api_suppression_when_sql_complete",
        "api_family_answer_intent_alignment",
    ]]
    payload: dict[str, Any] = {
        "report_type": REPORT_STEM,
        "generated_at": now_iso(),
        "classification": "diagnostic_only",
        "official_score_claim": False,
        "promotion_allowed": False,
        "runtime_change_applied": False,
        "gap_count": len(rows),
        "live_endpoint_matrix_outcome_counts": live_matrix,
        "gap_type_counts": counter_dict(row.get("gap_type") for row in enriched),
        "selected_endpoint_counts": counter_dict(_endpoint_key(row.get("endpoint_selected")) for row in enriched),
        "api_outcome_counts": counter_dict(outcome for row in enriched for outcome in _as_list(row.get("api_outcomes") or row.get("api_outcome"))),
        "trial_variants": trials,
        "representative_examples": top_examples(enriched),
        "rows": enriched,
        "recommendation": "Endpoint selection changes remain trial-only. Do not suppress API calls or reorder families without strict non-regression and generated unsupported-claim checks.",
    }
    write_report(config, REPORT_STEM, payload, _render_md(payload))
    return payload


def _is_gap(row: dict[str, Any]) -> bool:
    if str(row.get("failure_category") or "") == "api_endpoint_selection_gap":
        return True
    if int(row.get("api_error_count") or 0) > 0:
        return True
    if int(row.get("api_calls") or 0) > 0 and row.get("answer_used_sql_evidence") and not row.get("requires_live_api"):
        return True
    return False


def _gap_type(row: dict[str, Any]) -> str:
    if int(row.get("api_error_count") or 0) > 0:
        return "less_useful_or_error_endpoint_selected"
    if int(row.get("api_calls") or 0) > 0 and row.get("answer_used_sql_evidence") and not row.get("requires_live_api"):
        return "optional_api_call_when_sql_complete"
    if int(row.get("live_empty_count") or 0) > 0:
        return "live_empty_needs_answer_shape"
    return "endpoint_family_alignment_gap"


def _fix_type(row: dict[str, Any]) -> str:
    return {
        "less_useful_or_error_endpoint_selected": "parser_supported_endpoint_boost",
        "optional_api_call_when_sql_complete": "optional_api_suppression_when_sql_complete",
        "live_empty_needs_answer_shape": "live_empty_answer_shape",
        "endpoint_family_alignment_gap": "api_family_answer_intent_alignment",
    }.get(_gap_type(row), "review")


def _trial(name: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    relevant = [row for row in rows if _trial_matches(name, row)]
    api_saved = sum(int(row.get("api_calls") or 0) for row in relevant if name == "optional_api_suppression_when_sql_complete")
    return {
        "variant": name,
        "affected_rows": len(relevant),
        "estimated_api_calls_saved": api_saved,
        "strict_score_delta": "requires_isolated_trial",
        "generated_endpoint_selection_delta": -len(relevant),
        "unsupported_claim_delta": 0,
        "live_evidence_usage_delta": "unknown_until_trial",
        "recommendation": "trial_only" if relevant else "not_applicable",
        "representative_prompt_ids": [row.get("prompt_id") for row in relevant[:10]],
    }


def _trial_matches(name: str, row: dict[str, Any]) -> bool:
    gap = row.get("gap_type")
    return {
        "live_endpoint_health_ranking": gap == "less_useful_or_error_endpoint_selected",
        "parser_supported_endpoint_boost": gap == "less_useful_or_error_endpoint_selected",
        "optional_api_suppression_when_sql_complete": gap == "optional_api_call_when_sql_complete",
        "api_family_answer_intent_alignment": gap in {"endpoint_family_alignment_gap", "less_useful_or_error_endpoint_selected"},
    }.get(name, False)


def _endpoint_key(value: Any) -> str:
    items = _as_list(value)
    return ",".join(str(item) for item in items) if items else "none"


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value in (None, "", {}):
        return []
    return [value]


def _render_md(report: dict[str, Any]) -> str:
    lines = [
        "# API Endpoint Selection Gap Analysis",
        "",
        "This diagnostic looks for endpoint-family selection issues and optional API noise without changing endpoint catalog paths or runtime ranking.",
        "",
        f"- Gap count: `{report.get('gap_count')}`",
        f"- Gap types: `{report.get('gap_type_counts')}`",
        f"- API outcomes: `{report.get('api_outcome_counts')}`",
        "",
        "## Trial Variants",
        "",
    ]
    for trial in report.get("trial_variants", []):
        lines.append(f"- `{trial.get('variant')}`: affected rows `{trial.get('affected_rows')}`, estimated API calls saved `{trial.get('estimated_api_calls_saved')}`")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
