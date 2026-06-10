#!/usr/bin/env python
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.trajectory import redact_secrets
from scripts.run_schema_aware_sql_trial import run_schema_aware_sql_trial


REPORT_STEM = "schema_aware_sql_failure_decomposition"


def main() -> int:
    config = Config.from_env(ROOT)
    report = run_schema_aware_sql_failure_decomposition(config)
    print(
        json.dumps(
            {
                "json": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.json"),
                "markdown": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.md"),
                "hurt_rows": report.get("summary", {}).get("hurt_rows"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def run_schema_aware_sql_failure_decomposition(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    trial_path = reports_dir / "schema_aware_sql_trial.json"
    trial = _load_json(trial_path)
    if not trial:
        trial = run_schema_aware_sql_trial(config)
    hurt = trial.get("rows_hurt") or []
    helped = trial.get("rows_helped") or []
    rows = [_decompose_row(row) for row in hurt]
    categories = Counter(row.get("failure_category") for row in rows)
    report = redact_secrets(
        {
            "report_type": REPORT_STEM,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "diagnostic_only": True,
            "promotion_allowed": False,
            "source_report": "outputs/reports/schema_aware_sql_trial.json",
            "summary": {
                "strict_score_delta": (trial.get("summary") or {}).get("strict_score_delta"),
                "sql_score_delta": (trial.get("summary") or {}).get("sql_score_delta"),
                "answer_score_delta": (trial.get("summary") or {}).get("answer_score_delta"),
                "hurt_rows": len(hurt),
                "helped_rows": len(helped),
                "failure_distribution": dict(categories),
            },
            "rows": rows,
            "recommendation": "schema_aware_needs_stricter_activation_gates" if hurt else "no_hurt_rows_detected",
            "candidate_gates": [
                "template_miss_only",
                "strong_grounding_signal_required",
                "join_intent_required",
                "bridge_table_cannot_be_primary_answer_table",
                "quoted_entity_requires_filter",
                "probe_filtered_execution_required",
                "paraphrase_stability_required",
            ],
        }
    )
    (reports_dir / f"{REPORT_STEM}.json").write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    (reports_dir / f"{REPORT_STEM}.md").write_text(_render_md(report), encoding="utf-8")
    return report


def _decompose_row(row: dict[str, Any]) -> dict[str, Any]:
    query = str(row.get("query") or "")
    candidate_family = str(row.get("candidate_sql_family") or "")
    failure = _classify(query, candidate_family, row)
    return {
        "query_id": row.get("query_id"),
        "query": query,
        "failure_category": failure,
        "baseline_sql_template_family": row.get("baseline_sql_template_family"),
        "candidate_sql_family": candidate_family,
        "final_score_delta": row.get("final_score_delta"),
        "sql_score_delta": row.get("sql_score_delta"),
        "answer_score_delta": row.get("answer_score_delta"),
        "tool_count_delta": row.get("tool_count_delta"),
        "activation_gate_that_should_have_blocked": _gate_for_failure(failure),
    }


def _classify(query: str, candidate_family: str, row: dict[str, Any]) -> str:
    lowered = query.lower()
    if row.get("baseline_sql_template_family") and candidate_family == "schema_aware_sql_fallback":
        return "template_should_have_won"
    if any(word in lowered for word in ["connected", "mapped", "related", "associated", "linked"]):
        return "wrong_join_path"
    if re.search(r"'[^']+'|\"[^\"]+\"", query):
        return "missing_filter"
    if any(word in lowered for word in ["how many", "count", "number of", "total"]):
        return "wrong_count_entity"
    if candidate_family == "schema_aware_sql_fallback":
        return "low_confidence_candidate_selected"
    return "no_clear_failure"


def _gate_for_failure(failure: str) -> str:
    return {
        "template_should_have_won": "template_miss_only",
        "wrong_join_path": "join_intent_required",
        "missing_filter": "quoted_entity_requires_filter",
        "wrong_count_entity": "count_distinct_requires_entity_id_column",
        "low_confidence_candidate_selected": "candidate_confidence_threshold",
    }.get(failure, "manual_review_required")


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _render_md(report: dict[str, Any]) -> str:
    summary = report.get("summary", {})
    lines = [
        "# Schema-Aware SQL Failure Decomposition",
        "",
        f"- Strict score delta: `{summary.get('strict_score_delta')}`",
        f"- SQL score delta: `{summary.get('sql_score_delta')}`",
        f"- Hurt rows: `{summary.get('hurt_rows')}`",
        f"- Helped rows: `{summary.get('helped_rows')}`",
        "",
        "## Failure Distribution",
        "",
    ]
    for key, value in sorted((summary.get("failure_distribution") or {}).items()):
        lines.append(f"- `{key}`: `{value}`")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
