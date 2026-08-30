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
from scripts.robustness_improvement_common import (
    counter_dict,
    group_by,
    load_rows,
    now_iso,
    top_examples,
    write_report,
)


REPORT_STEM = "generated_prompt_failure_cluster_analysis"


CLUSTERS = [
    "route_mismatch",
    "answer_shape_weak",
    "api_endpoint_selection_gap",
    "no_template_fallback_weak",
    "live_empty_mishandled",
    "sql_api_conflict_unresolved",
    "unnecessary_api_call_noise",
    "no_clear_failure",
]


def main() -> int:
    config = Config.from_env(ROOT)
    report = run_generated_prompt_failure_cluster_analysis(config)
    print(json.dumps({"report": REPORT_STEM, "clusters": report["cluster_counts"]}, indent=2, sort_keys=True))
    return 0


def run_generated_prompt_failure_cluster_analysis(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    rows = load_rows(config)
    enriched = [{**row, "cluster": classify_cluster(row)} for row in rows]
    grouped = group_by(enriched, "cluster")
    clusters = [_cluster_summary(name, grouped.get(name, [])) for name in CLUSTERS if grouped.get(name)]
    payload: dict[str, Any] = {
        "report_type": REPORT_STEM,
        "generated_at": now_iso(),
        "classification": "diagnostic_only",
        "official_score_claim": False,
        "promotion_allowed": False,
        "runtime_change_applied": False,
        "total_rows": len(rows),
        "cluster_counts": counter_dict(row["cluster"] for row in enriched),
        "failure_category_counts": counter_dict(row.get("failure_category") for row in rows),
        "route_distribution": counter_dict(row.get("route_type") for row in rows),
        "domain_distribution": counter_dict(row.get("domain_family") for row in rows),
        "clusters": clusters,
        "rows": enriched,
        "recommendation": "Use this as diagnostic evidence only. Candidate fixes require strict, hidden-style, endpoint, robustness, and secret-scan gates before runtime promotion.",
    }
    write_report(config, REPORT_STEM, payload, _render_md(payload))
    return payload


def classify_cluster(row: dict[str, Any]) -> str:
    failure = str(row.get("failure_category") or "").strip()
    if failure in CLUSTERS:
        return failure
    if row.get("route_matches_diagnostic") is False:
        return "route_mismatch"
    if row.get("answer_intent_matches_diagnostic") is False or row.get("vague_or_evidence_unused"):
        return "answer_shape_weak"
    if int(row.get("api_error_count") or 0) > 0:
        return "api_endpoint_selection_gap"
    if not row.get("template_hit") and int(row.get("sql_calls") or 0) > 0 and row.get("zero_row_sql"):
        return "no_template_fallback_weak"
    if int(row.get("live_empty_count") or 0) > 0 and "no " not in str(row.get("final_answer") or "").lower():
        return "live_empty_mishandled"
    if "conflict" in str(row.get("evidence_state") or "").lower():
        return "sql_api_conflict_unresolved"
    if int(row.get("api_calls") or 0) > 0 and not row.get("requires_live_api") and row.get("answer_used_sql_evidence"):
        return "unnecessary_api_call_noise"
    return "no_clear_failure"


def _cluster_summary(name: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "cluster": name,
        "count": len(rows),
        "top_domain_families": counter_dict(row.get("domain_family") for row in rows),
        "top_routes": counter_dict(row.get("route_type") for row in rows),
        "root_cause": _root_cause(name),
        "code_fixable": name not in {"no_clear_failure"} and name != "route_mismatch",
        "safest_fix_type": _fix_type(name),
        "expected_correctness_impact": _correctness_impact(name),
        "expected_efficiency_impact": _efficiency_impact(name),
        "generalization_risk": _risk(name),
        "robustness_risk": _risk(name),
        "representative_examples": top_examples(rows),
    }


def _root_cause(name: str) -> str:
    return {
        "answer_shape_weak": "Evidence is available and unsupported claims are zero, but deterministic answer wording does not always expose the count/list/status/date shape expected by the prompt.",
        "route_mismatch": "Generated diagnostic labels often disagree with deterministic route decisions; some are likely label noise and require manual review before router edits.",
        "api_endpoint_selection_gap": "The runtime sometimes calls a less useful API family or carries unresolved/low-yield optional API calls when SQL evidence already answers the question.",
        "no_template_fallback_weak": "Template misses rely on heuristic fallback that can validate and execute but may select weak filters or produce zero-row evidence.",
        "live_empty_mishandled": "A real 2xx empty response must be worded as live empty evidence, not generic API failure.",
        "sql_api_conflict_unresolved": "SQL and API evidence disagree or answer different slices and the answer should surface that conflict explicitly.",
        "unnecessary_api_call_noise": "Optional live API calls add tokens/runtime when SQL already provides sufficient evidence.",
        "no_clear_failure": "No high-risk failure signature is present in available diagnostic fields.",
    }.get(name, "unknown")


def _fix_type(name: str) -> str:
    return {
        "answer_shape_weak": "targeted deterministic answer template trial",
        "route_mismatch": "manual label-noise review before conservative synonym/calibration rule",
        "api_endpoint_selection_gap": "endpoint-family ranking and optional API suppression trial",
        "no_template_fallback_weak": "schema-aware SQL gating diagnostic only",
        "live_empty_mishandled": "live_empty answer wording guard",
        "sql_api_conflict_unresolved": "SQL/API conflict answer template",
        "unnecessary_api_call_noise": "SQL-complete optional API skip guard",
        "no_clear_failure": "no_code_change",
    }.get(name, "review")


def _correctness_impact(name: str) -> str:
    return "potential_positive" if name in {"answer_shape_weak", "live_empty_mishandled", "sql_api_conflict_unresolved"} else "uncertain"


def _efficiency_impact(name: str) -> str:
    return "positive" if name in {"unnecessary_api_call_noise", "api_endpoint_selection_gap"} else "neutral"


def _risk(name: str) -> str:
    return "medium" if name in {"route_mismatch", "api_endpoint_selection_gap", "no_template_fallback_weak"} else "low"


def _render_md(report: dict[str, Any]) -> str:
    lines = [
        "# Generated Prompt Failure Cluster Analysis",
        "",
        "Generated prompts remain diagnostic-only. This report clusters failure signatures to decide which isolated trials are worth running.",
        "",
        f"- Total rows: `{report.get('total_rows')}`",
        f"- Cluster counts: `{report.get('cluster_counts')}`",
        "",
    ]
    for cluster in report.get("clusters", []):
        lines.extend(
            [
                f"## {cluster.get('cluster')}",
                "",
                f"- Count: `{cluster.get('count')}`",
                f"- Root cause: {cluster.get('root_cause')}",
                f"- Safest fix type: `{cluster.get('safest_fix_type')}`",
                f"- Generalization risk: `{cluster.get('generalization_risk')}`",
                "",
            ]
        )
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
