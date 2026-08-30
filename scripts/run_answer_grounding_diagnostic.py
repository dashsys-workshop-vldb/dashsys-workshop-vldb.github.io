#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.robustness_diagnostics_common import forbidden_claim_hits, load_500_gold_by_id, read_json, required_fact_coverage, trajectory_files, write_json_md


def run_diagnostic() -> dict[str, Any]:
    organizer = _organizer_answer_rows()
    internal = _internal_500_answer_rows()
    rows = organizer + internal
    classes: Counter[str] = Counter()
    for row in rows:
        classes.update(row["failure_classes"])
    report = {
        "report_type": "answer_grounding_diagnostic",
        "diagnostic_only": True,
        "runtime_gold_visible": False,
        "row_count": len(rows),
        "organizer_35_row_count": len(organizer),
        "internal_500_row_count": len(internal),
        "failure_class_counts": dict(sorted(classes.items())),
        "unsupported_claim_rows": [row for row in rows if row.get("unsupported_claims", 0)][:50],
        "evidence_available_but_not_rendered": [row for row in rows if "evidence_available_but_not_rendered" in row["failure_classes"]][:50],
        "missing_required_fact_rows": [row for row in rows if "missing_required_fact" in row["failure_classes"]][:50],
        "rows": rows[:250],
    }
    return report


def _organizer_answer_rows() -> list[dict[str, Any]]:
    strict = read_json(ROOT / "outputs" / "eval_results_strict.json")
    by_qid = {
        row.get("query_id"): row
        for row in strict.get("rows", [])
        if row.get("strategy") == "SQL_FIRST_API_VERIFY"
    }
    rows: list[dict[str, Any]] = []
    for path in trajectory_files("example_", strategy="sql_first_api_verify"):
        traj = read_json(path)
        qid = str(traj.get("query_id") or path.parts[-3])
        score_row = by_qid.get(qid, {})
        answer = str(traj.get("final_answer") or "")
        classes = _classes_from_answer(answer, score_row, traj)
        rows.append(
            {
                "dataset": "organizer_35",
                "prompt_id": qid,
                "prompt": traj.get("original_query") or score_row.get("query"),
                "answer_score": score_row.get("answer_score"),
                "final_score": score_row.get("final_score"),
                "sql_calls": traj.get("sql_call_count"),
                "api_calls": traj.get("api_call_count"),
                "unsupported_claims": _unsupported_claims(traj),
                "failure_classes": classes,
                "final_answer_preview": answer[:240],
            }
        )
    return rows


def _internal_500_answer_rows() -> list[dict[str, Any]]:
    gold = load_500_gold_by_id()
    rows: list[dict[str, Any]] = []
    root = ROOT / "outputs" / "dashagent_500_prompt_suite_eval_real" / "packaged_baseline_real"
    if not root.exists():
        return rows
    for grade_path in sorted(root.glob("*/benchmark_grade.json")):
        payload = read_json(grade_path)
        prompt_id = str(payload.get("prompt_id") or grade_path.parent.name)
        grade = payload.get("grade") or {}
        extracted = payload.get("extracted_runtime") or {}
        answer = str(payload.get("final_answer") or "")
        if not answer:
            traj = read_json(grade_path.parent / "trajectory.json")
            answer = str(traj.get("final_answer") or "")
        gold_row = gold.get(prompt_id, {})
        coverage, missing = required_fact_coverage(answer, gold_row.get("required_facts") or [])
        forbidden = forbidden_claim_hits(answer, gold_row.get("forbidden_claims") or [])
        classes: list[str] = []
        if missing:
            classes.append("missing_required_fact")
        if forbidden:
            classes.append("forbidden_claim")
        if grade.get("answer_grounding_score", 1.0) < 1.0:
            classes.append("answer_grounding_gap")
        if grade.get("required_facts_coverage", coverage) < 0.75:
            classes.append("evidence_available_but_not_rendered")
        if not classes:
            classes.append("no_clear_failure" if grade.get("final_answer_correctness", 1.0) < 0.5 else "ok")
        rows.append(
            {
                "dataset": "internal_500_heuristic",
                "prompt_id": prompt_id,
                "prompt": gold_row.get("prompt") or "",
                "answer_score": grade.get("final_answer_correctness"),
                "required_fact_coverage": coverage,
                "missing_facts": missing[:8],
                "forbidden_claim_hits": forbidden[:8],
                "sql_calls": extracted.get("sql_calls"),
                "api_calls": extracted.get("api_calls"),
                "unsupported_claims": grade.get("unsupported_claims", 0),
                "failure_classes": classes,
                "final_answer_preview": answer[:240],
            }
        )
    return rows


def _classes_from_answer(answer: str, score_row: dict[str, Any], trajectory: dict[str, Any]) -> list[str]:
    classes: list[str] = []
    answer_score = score_row.get("answer_score")
    if answer_score is not None and answer_score < 0.4:
        classes.append("missing_required_fact")
    if "no data available" in answer.lower() and trajectory.get("api_call_count", 0):
        classes.append("over_caveated_answer")
    if "api error" in answer.lower() or "unavailable" in answer.lower():
        classes.append("api_error_misworded" if trajectory.get("api_call_count", 0) else "under_caveated_answer")
    if _unsupported_claims(trajectory):
        classes.append("unsupported_claim")
    if not classes:
        classes.append("ok")
    return classes


def _unsupported_claims(trajectory: dict[str, Any]) -> int:
    text = json.dumps(trajectory)
    if '"unsupported_claims_count":' not in text and '"unsupported_claims":' not in text:
        return 0
    # Keep this conservative: existing verifier reports usually expose count in checkpoints.
    for key in ("unsupported_claims_count", "unsupported_claims"):
        marker = f'"{key}":'
        if marker in text:
            try:
                return int(text.split(marker, 1)[1].split(",", 1)[0].split("}", 1)[0].strip())
            except Exception:
                return 0
    return 0


def main() -> int:
    report = run_diagnostic()
    lines = [
        "# Answer Grounding Diagnostic",
        "",
        f"- Rows inspected: `{report['row_count']}`",
        f"- Organizer rows: `{report['organizer_35_row_count']}`",
        f"- Internal 500 rows: `{report['internal_500_row_count']}`",
        f"- Failure classes: `{report['failure_class_counts']}`",
        "",
        "Gold/rubric fields are used only after execution for analysis.",
    ]
    write_json_md("answer_grounding_diagnostic", report, lines)
    print(json.dumps(report["failure_class_counts"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
