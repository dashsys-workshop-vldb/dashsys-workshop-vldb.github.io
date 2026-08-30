#!/usr/bin/env python3
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

from dashagent.eval_harness import EvalHarness, generated_api_calls


STRATEGY = "SQL_FIRST_API_VERIFY"
BASELINE_RESULTS = ROOT / "outputs" / "reports" / "baselines" / "pre_live_api_eval_results_strict.json"
LIVE_RESULTS = ROOT / "outputs" / "eval_results_strict.json"
BASELINE_TRAJECTORY_ROOT = ROOT / "outputs" / "official_token_reduction_canary"
LIVE_TRAJECTORY_ROOT = ROOT / "outputs" / "eval"
REPORT_DIR = ROOT / "outputs" / "reports"
DRY_RUN_CAVEAT = "Live API verification was not executed because Adobe credentials are unavailable."


def main() -> int:
    baseline = load_json(BASELINE_RESULTS)
    live = load_json(LIVE_RESULTS)
    examples = {example.query_id: example for example in EvalHarness().load_examples()}
    baseline_rows = strategy_rows(baseline)
    live_rows = strategy_rows(live)
    rows = []
    for query_id in sorted(live_rows):
        if query_id not in baseline_rows:
            continue
        baseline_traj = load_trajectory(BASELINE_TRAJECTORY_ROOT / query_id / "sql_first_api_verify" / "trajectory.json")
        live_traj = load_trajectory(LIVE_TRAJECTORY_ROOT / query_id / "sql_first_api_verify" / "trajectory.json")
        row = compare_row(query_id, baseline_rows[query_id], live_rows[query_id], baseline_traj, live_traj, examples.get(query_id))
        rows.append(row)

    baseline_score = strategy_score(baseline)
    live_score = strategy_score(live)
    baseline_report = {
        "report_type": "live_api_score_regression_baseline",
        "generated_at": now(),
        "strategy": STRATEGY,
        "baseline": {
            "strict_score": baseline_score,
            "adobe_api_mode": "pre_live_dry_run",
            "artifact_path": rel(BASELINE_RESULTS),
            "trajectory_root": rel(BASELINE_TRAJECTORY_ROOT),
        },
        "live": {
            "strict_score": live_score,
            "adobe_api_mode": "live_enabled",
            "artifact_path": rel(LIVE_RESULTS),
            "trajectory_root": rel(LIVE_TRAJECTORY_ROOT),
        },
        "delta": round(live_score - baseline_score, 4),
        "historical_baseline_overwritten": False,
    }
    write_report(
        REPORT_DIR / "live_api_score_regression_baseline",
        baseline_report,
        render_baseline_md(baseline_report),
    )

    helped = [row for row in rows if row["score_delta"] > 0.0001]
    hurt = [row for row in rows if row["score_delta"] < -0.0001]
    unchanged = [row for row in rows if abs(row["score_delta"]) <= 0.0001]
    categories = Counter(row["likely_regression_category"] for row in rows)
    analysis = {
        "report_type": "live_api_score_regression_analysis",
        "generated_at": now(),
        "strategy": STRATEGY,
        "baseline_strict_score": baseline_score,
        "live_strict_score": live_score,
        "score_delta": round(live_score - baseline_score, 4),
        "row_count": len(rows),
        "rows_helped": len(helped),
        "rows_hurt": len(hurt),
        "rows_unchanged": len(unchanged),
        "dominant_regression_categories": categories.most_common(),
        "biggest_negative_deltas": sorted((brief_delta(row) for row in hurt), key=lambda item: item["score_delta"])[:8],
        "biggest_positive_deltas": sorted((brief_delta(row) for row in helped), key=lambda item: item["score_delta"], reverse=True)[:8],
        "rows": rows,
    }
    write_report(
        REPORT_DIR / "live_api_score_regression_analysis",
        analysis,
        render_analysis_md(analysis),
    )

    audit_rows = [arbitration_audit_row(row) for row in rows if row["live_api_state"] not in {"skipped", "unavailable"}]
    audit = {
        "report_type": "live_api_evidence_arbitration_audit",
        "generated_at": now(),
        "strategy": STRATEGY,
        "row_count": len(audit_rows),
        "policy_recommendations": summarize_policy_recommendations(audit_rows),
        "rows": audit_rows,
    }
    write_report(
        REPORT_DIR / "live_api_evidence_arbitration_audit",
        audit,
        render_audit_md(audit),
    )
    print(json.dumps({"status": "complete", "baseline_delta": baseline_report["delta"], "rows": len(rows)}, indent=2, sort_keys=True))
    return 0


def compare_row(
    query_id: str,
    baseline_row: dict[str, Any],
    live_row: dict[str, Any],
    baseline_traj: dict[str, Any],
    live_traj: dict[str, Any],
    example: Any,
) -> dict[str, Any]:
    baseline_answer = sanitize_text(baseline_traj.get("final_answer") or "")
    live_answer = sanitize_text(live_traj.get("final_answer") or "")
    baseline_api_state = classify_api_state(baseline_traj)
    live_api_state = classify_api_state(live_traj)
    live_api_calls = generated_api_calls(live_traj)
    sql_delta = delta(live_row.get("sql_score"), baseline_row.get("sql_score"))
    api_delta = delta(live_row.get("api_score"), baseline_row.get("api_score"))
    answer_delta = delta(live_row.get("answer_score"), baseline_row.get("answer_score"))
    score_delta = delta(live_row.get("final_score"), baseline_row.get("final_score")) or 0.0
    sql_fully_answered = bool((live_row.get("sql_score") or 0) >= 0.85 and baseline_answer and "requires live api evidence" not in baseline_answer.lower())
    live_changed_answer = normalize_space(baseline_answer) != normalize_space(live_answer)
    evidence_priority_changed = any(
        phrase in live_answer.lower()
        for phrase in ["api evidence reports", "api returned", "live api evidence", "sql and api evidence disagree"]
    )
    contradicted = "sql and api evidence disagree" in live_answer.lower()
    necessary = bool((live_row.get("sql_score") is None or (live_row.get("sql_score") or 0) < 0.5) or "requires live api evidence" in baseline_answer.lower())
    category = classify_regression(
        score_delta=score_delta,
        answer_delta=answer_delta,
        api_delta=api_delta,
        live_api_state=live_api_state,
        sql_fully_answered=sql_fully_answered,
        live_changed_answer=live_changed_answer,
        evidence_priority_changed=evidence_priority_changed,
        contradicted=contradicted,
        live_answer=live_answer,
    )
    return {
        "query_id": query_id,
        "prompt": sanitize_text(example.query if example else baseline_row.get("query", "")),
        "baseline_score": baseline_row.get("final_score"),
        "live_score": live_row.get("final_score"),
        "score_delta": round(score_delta, 4),
        "sql_score_delta": round(sql_delta, 4) if sql_delta is not None else None,
        "api_score_delta": round(api_delta, 4) if api_delta is not None else None,
        "answer_score_delta": round(answer_delta, 4) if answer_delta is not None else None,
        "baseline_final_answer": baseline_answer,
        "live_final_answer": live_answer,
        "baseline_sql_result_summary": sql_summary(baseline_traj),
        "live_sql_result_summary": sql_summary(live_traj),
        "baseline_api_state": baseline_api_state,
        "live_api_state": live_api_state,
        "endpoint_used": [call.get("path") for call in live_api_calls],
        "whether_live_api_changed_the_answer": live_changed_answer,
        "whether_live_api_changed_evidence_priority": evidence_priority_changed,
        "whether_live_api_contradicted_sql": contradicted,
        "whether_live_api_was_necessary": necessary,
        "whether_sql_already_fully_answered": sql_fully_answered,
        "whether_answer_added_unnecessary_live_api_details": bool(sql_fully_answered and evidence_priority_changed and not necessary),
        "whether_answer_lost_useful_sql_detail": bool(score_delta < 0 and answer_delta is not None and answer_delta < 0 and sql_fully_answered),
        "likely_regression_category": category,
    }


def classify_regression(
    *,
    score_delta: float,
    answer_delta: float | None,
    api_delta: float | None,
    live_api_state: str,
    sql_fully_answered: bool,
    live_changed_answer: bool,
    evidence_priority_changed: bool,
    contradicted: bool,
    live_answer: str,
) -> str:
    if score_delta > 0.0001:
        return "live_api_helped"
    if abs(score_delta) <= 0.0001:
        return "no_live_change_but_score_drift" if live_changed_answer else "no_clear_regression"
    if contradicted:
        return "sql_api_conflict_unresolved"
    if live_api_state == "live_empty":
        return "live_empty_overinterpreted"
    if api_delta is not None and api_delta < -0.01:
        return "endpoint_payload_shape_mismatch"
    if "observability metrics were returned" in live_answer.lower():
        return "endpoint_payload_shape_mismatch"
    if sql_fully_answered and evidence_priority_changed:
        return "unnecessary_api_call_added_noise"
    if answer_delta is not None and answer_delta < -0.01:
        return "answer_wording_regression"
    return "no_clear_regression"


def arbitration_audit_row(row: dict[str, Any]) -> dict[str, Any]:
    if row["whether_live_api_contradicted_sql"]:
        should = "conflict requiring explicit explanation"
    elif row["whether_sql_already_fully_answered"] and not row["whether_live_api_was_necessary"]:
        should = "verification evidence only"
    elif row["live_api_state"] == "live_empty" and row["whether_sql_already_fully_answered"]:
        should = "caveat only"
    elif row["whether_live_api_was_necessary"]:
        should = "primary evidence"
    else:
        should = "verification evidence only"
    return {
        "query_id": row["query_id"],
        "sql_already_fully_answered": row["whether_sql_already_fully_answered"],
        "api_need": "API_REQUIRED" if row["whether_live_api_was_necessary"] else "API_OPTIONAL",
        "live_api_provided_new_facts": row["live_api_state"] == "live_success" and not row["whether_sql_already_fully_answered"],
        "live_empty_conflicted_with_sql": row["live_api_state"] == "live_empty" and row["whether_sql_already_fully_answered"],
        "final_answer_prioritized_correct_source": not row["whether_answer_added_unnecessary_live_api_details"],
        "recommended_api_evidence_role": should,
        "category": row["likely_regression_category"],
    }


def summarize_policy_recommendations(rows: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(row["recommended_api_evidence_role"] for row in rows))


def classify_api_state(trajectory: dict[str, Any]) -> str:
    states = []
    for step in trajectory.get("steps", []):
        if step.get("kind") != "api_call":
            continue
        result = unpreview(step.get("result", {}))
        if result.get("dry_run"):
            states.append("dry_run")
        elif result.get("ok") is True:
            preview = result.get("result_preview")
            states.append("live_success" if preview not in (None, "", [], {}) else "live_empty")
        elif result:
            states.append("api_error")
    if not states:
        return "skipped"
    for preferred in ["api_error", "live_success", "live_empty", "dry_run"]:
        if preferred in states:
            return preferred
    return states[0]


def sql_summary(trajectory: dict[str, Any]) -> dict[str, Any]:
    for step in trajectory.get("steps", []):
        if step.get("kind") != "sql_call":
            continue
        result = unpreview(step.get("result", {}))
        rows = result.get("rows")
        return {
            "ok": result.get("ok"),
            "row_count": result.get("row_count"),
            "has_rows": bool(rows),
            "limited": result.get("limited"),
        }
    return {"ok": None, "row_count": None, "has_rows": False, "limited": None}


def unpreview(value: Any) -> dict[str, Any]:
    if isinstance(value, dict) and isinstance(value.get("preview"), str):
        try:
            parsed = json.loads(value["preview"])
            return parsed if isinstance(parsed, dict) else value
        except json.JSONDecodeError:
            return value
    return value if isinstance(value, dict) else {}


def strategy_rows(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row["query_id"]: row for row in payload.get("rows", []) if row.get("strategy") == STRATEGY}


def strategy_score(payload: dict[str, Any]) -> float:
    return float(payload["summary"]["by_strategy"][STRATEGY]["avg_final_score"])


def load_trajectory(path: Path) -> dict[str, Any]:
    return load_json(path) if path.exists() else {}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def delta(after: Any, before: Any) -> float | None:
    if after is None or before is None:
        return None
    return float(after) - float(before)


def brief_delta(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "query_id": row["query_id"],
        "score_delta": row["score_delta"],
        "answer_score_delta": row["answer_score_delta"],
        "api_score_delta": row["api_score_delta"],
        "category": row["likely_regression_category"],
    }


def sanitize_text(text: Any) -> str:
    text = str(text or "")
    text = re.sub(r"[A-Z0-9._%+-]+@AdobeOrg", "[REDACTED_ORG]", text, flags=re.I)
    text = re.sub(r"[A-F0-9]{16,}@techacct\\.adobe\\.com", "[REDACTED_ACCOUNT]", text, flags=re.I)
    text = re.sub(r"Authorization:\\s*Bearer\\s+\\S+", "Authorization: [REDACTED]", text, flags=re.I)
    return text


def normalize_space(text: str) -> str:
    return " ".join(text.split())


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def write_report(stem: Path, payload: dict[str, Any], markdown: str) -> None:
    stem.parent.mkdir(parents=True, exist_ok=True)
    stem.with_suffix(".json").write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    stem.with_suffix(".md").write_text(markdown, encoding="utf-8")


def render_baseline_md(report: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Live API Score Regression Baseline",
            "",
            f"- Strategy: `{report['strategy']}`",
            f"- Pre-live strict score: `{report['baseline']['strict_score']:.4f}`",
            f"- Live strict score: `{report['live']['strict_score']:.4f}`",
            f"- Delta: `{report['delta']:.4f}`",
            f"- Baseline artifact: `{report['baseline']['artifact_path']}`",
            f"- Live artifact: `{report['live']['artifact_path']}`",
            "",
        ]
    )


def render_analysis_md(report: dict[str, Any]) -> str:
    lines = [
        "# Live API Score Regression Analysis",
        "",
        f"- Baseline strict score: `{report['baseline_strict_score']:.4f}`",
        f"- Live strict score: `{report['live_strict_score']:.4f}`",
        f"- Delta: `{report['score_delta']:.4f}`",
        f"- Rows helped/hurt/unchanged: `{report['rows_helped']}` / `{report['rows_hurt']}` / `{report['rows_unchanged']}`",
        "",
        "## Dominant Categories",
    ]
    for category, count in report["dominant_regression_categories"]:
        lines.append(f"- `{category}`: `{count}`")
    lines.extend(["", "## Biggest Negative Deltas", "| query_id | delta | category |", "|---|---:|---|"])
    for row in report["biggest_negative_deltas"]:
        lines.append(f"| `{row['query_id']}` | `{row['score_delta']:.4f}` | `{row['category']}` |")
    lines.append("")
    return "\n".join(lines)


def render_audit_md(report: dict[str, Any]) -> str:
    lines = [
        "# Live API Evidence Arbitration Audit",
        "",
        f"- Rows with live API involvement: `{report['row_count']}`",
        "",
        "## Recommended Evidence Roles",
    ]
    for role, count in report["policy_recommendations"].items():
        lines.append(f"- `{role}`: `{count}`")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
