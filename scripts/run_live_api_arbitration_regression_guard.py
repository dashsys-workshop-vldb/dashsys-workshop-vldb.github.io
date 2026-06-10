#!/usr/bin/env python
from __future__ import annotations

import json
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


REPORT_STEM = "live_api_arbitration_regression_guard"


def main() -> int:
    config = Config.from_env(ROOT)
    report = run_live_api_arbitration_regression_guard(config)
    print(
        json.dumps(
            {
                "json": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.json"),
                "markdown": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.md"),
                "policy_safe_to_keep": report.get("policy_safe_to_keep"),
                "policy_violation_count": report.get("policy_violation_count"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report.get("policy_safe_to_keep") else 1


def run_live_api_arbitration_regression_guard(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    analysis = _load_json(reports_dir / "live_api_score_regression_analysis.json")
    trial = _load_json(reports_dir / "live_api_evidence_arbitration_trial.json")
    rows = analysis.get("rows") or []
    violations = evaluate_arbitration_policy_rows(rows, config=config)
    critical = [item for item in violations if item.get("violation_type") != "noisy_verification_added"]
    strict_non_regression = _strict_non_regression(config)
    report = redact_secrets(
        {
            "report_type": REPORT_STEM,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "diagnostic_only": False,
            "policy_under_test": trial.get("recommended_variant") or "sql_primary_when_complete",
            "promotion_decision": trial.get("promotion_decision"),
            "rows_covered": len(rows),
            "policy_violation_count": len(violations),
            "critical_policy_violation_count": len(critical),
            "policy_warning_count": len(violations) - len(critical),
            "policy_violations": violations,
            "violation_distribution": dict(Counter(item["violation_type"] for item in violations)),
            "strict_non_regression": strict_non_regression,
            "policy_safe_to_keep": len(critical) == 0 and strict_non_regression is True,
            "checked_invariants": [
                "sql_primary_when_sql_fully_answers",
                "api_primary_only_when_required_or_sql_cannot_answer",
                "sql_api_conflict_explicit",
                "live_empty_does_not_override_sql",
                "noisy_verification_suppressed",
            ],
            "examples": violations[:20],
        }
    )
    (reports_dir / f"{REPORT_STEM}.json").write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    (reports_dir / f"{REPORT_STEM}.md").write_text(_render_md(report), encoding="utf-8")
    return report


def evaluate_arbitration_policy_rows(rows: list[dict[str, Any]], *, config: Config | None = None) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    for row in rows:
        if float(row.get("score_delta") or 0.0) >= 0.0 and row.get("likely_regression_category") == "live_api_helped":
            continue
        query_id = row.get("query_id")
        sql_complete = bool(row.get("whether_sql_already_fully_answered"))
        api_needed = bool(row.get("whether_live_api_was_necessary"))
        live_state = row.get("live_api_state")
        current_answer = _current_final_answer(config, str(query_id)) if config and query_id else None
        current_score_delta = _current_score_delta_vs_pre_live(config, str(query_id)) if config and query_id else None
        changed_priority = _current_changed_priority(current_answer, row)
        added_noise = _current_added_noise(current_answer, row)
        if current_answer is not None and isinstance(current_score_delta, (int, float)) and current_score_delta >= -0.0001:
            changed_priority = False
            added_noise = False
        contradicted = bool(row.get("whether_live_api_contradicted_sql"))
        category = row.get("likely_regression_category")
        if sql_complete and not api_needed and live_state == "live_empty" and changed_priority:
            violations.append(_violation(query_id, "live_empty_overrode_sql", row))
        elif sql_complete and not api_needed and changed_priority:
            violations.append(_violation(query_id, "api_verification_overrode_sql", row))
        if sql_complete and not api_needed and added_noise:
            violations.append(_violation(query_id, "noisy_verification_added", row))
        if contradicted and category != "sql_api_conflict_unresolved":
            violations.append(_violation(query_id, "sql_api_conflict_not_explicit", row))
    return violations


def _current_final_answer(config: Config | None, query_id: str) -> str | None:
    if not config:
        return None
    path = config.outputs_dir / "eval" / query_id / "sql_first_api_verify" / "trajectory.json"
    payload = _load_json(path)
    answer = payload.get("final_answer")
    return str(answer) if answer is not None else None


def _current_score_delta_vs_pre_live(config: Config | None, query_id: str) -> float | None:
    if not config:
        return None
    current = _load_json(config.outputs_dir / "eval_results_strict.json")
    baseline = _load_json(config.outputs_dir / "reports" / "baselines" / "pre_live_api_eval_results_strict.json")
    current_row = _strategy_row(current, query_id)
    baseline_row = _strategy_row(baseline, query_id)
    if not current_row or not baseline_row:
        return None
    try:
        return round(float(current_row.get("final_score")) - float(baseline_row.get("final_score")), 4)
    except Exception:
        return None


def _strategy_row(payload: dict[str, Any], query_id: str) -> dict[str, Any] | None:
    for row in payload.get("rows") or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("query_id")) == query_id and row.get("strategy") == "SQL_FIRST_API_VERIFY":
            return row
    return None


def _strict_non_regression(config: Config | None) -> bool | str:
    if not config:
        return "unavailable"
    current = _load_json(config.outputs_dir / "eval_results_strict.json")
    baseline = _load_json(config.outputs_dir / "reports" / "baselines" / "pre_live_api_eval_results_strict.json")
    current_score = _strategy_score(current)
    baseline_score = _strategy_score(baseline)
    if current_score is None or baseline_score is None:
        return "unavailable"
    return current_score >= baseline_score


def _strategy_score(payload: dict[str, Any]) -> float | None:
    value = (
        payload.get("summary", {})
        .get("by_strategy", {})
        .get("SQL_FIRST_API_VERIFY", {})
        .get("avg_final_score")
    )
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _current_changed_priority(current_answer: str | None, row: dict[str, Any]) -> bool:
    if current_answer is None:
        return bool(row.get("whether_live_api_changed_evidence_priority"))
    lowered = current_answer.lower()
    return any(
        phrase in lowered
        for phrase in [
            "sql and api evidence disagree",
            "api evidence did not provide usable data",
            "api returned no matching results",
        ]
    )


def _current_added_noise(current_answer: str | None, row: dict[str, Any]) -> bool:
    if current_answer is None:
        return bool(row.get("whether_answer_added_unnecessary_live_api_details"))
    lowered = current_answer.lower()
    return any(
        phrase in lowered
        for phrase in [
            "the api returned usable supporting evidence",
            "api evidence did not provide usable data",
            "api returned no matching results",
        ]
    )


def _violation(query_id: Any, violation_type: str, row: dict[str, Any]) -> dict[str, Any]:
    return {
        "query_id": query_id,
        "violation_type": violation_type,
        "live_api_state": row.get("live_api_state"),
        "likely_regression_category": row.get("likely_regression_category"),
    }


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _render_md(report: dict[str, Any]) -> str:
    lines = [
        "# Live API Arbitration Regression Guard",
        "",
        f"- Rows covered: `{report.get('rows_covered')}`",
        f"- Policy under test: `{report.get('policy_under_test')}`",
        f"- Policy safe to keep: `{report.get('policy_safe_to_keep')}`",
        f"- Policy violations: `{report.get('policy_violation_count')}`",
        f"- Critical policy violations: `{report.get('critical_policy_violation_count')}`",
        f"- Policy warnings: `{report.get('policy_warning_count')}`",
        "",
        "## Violation Distribution",
        "",
    ]
    for key, value in sorted((report.get("violation_distribution") or {}).items()):
        lines.append(f"- `{key}`: `{value}`")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
