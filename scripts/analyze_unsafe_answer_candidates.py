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
from dashagent.report_run import report_metadata
from scripts.run_official_token_reduction_eval import _load_json


OUTPUT_NAME = "unsafe_answer_candidate_analysis"


def main() -> int:
    config = Config.from_env(ROOT)
    payload = analyze_unsafe_answer_candidates(config)
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    json_path = config.outputs_dir / f"{OUTPUT_NAME}.json"
    md_path = config.outputs_dir / f"{OUTPUT_NAME}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "rows": payload["summary"]["total_rows"]}, indent=2, sort_keys=True))
    return 0


def analyze_unsafe_answer_candidates(config: Config) -> dict[str, Any]:
    evidence = _load_json(config.outputs_dir / "evidence_answer_candidate_eval.json")
    execution = _load_json(config.outputs_dir / "execution_candidate_search.json")
    rows: list[dict[str, Any]] = []
    for row in evidence.get("rows", []):
        if row.get("safe_for_packaged_trial"):
            continue
        rows.append(_evidence_row(row))
    for row in execution.get("rows", []):
        for candidate in row.get("candidates", []):
            if candidate.get("safe_for_packaged_trial"):
                continue
            candidate_id = str(candidate.get("candidate_id") or "")
            if "answer" not in candidate_id and candidate_id not in {"dry_run_evidence_answer"}:
                continue
            rows.append(_execution_candidate_row(row, candidate))
    rows.sort(key=lambda item: float(item.get("supportable_answer_delta") or 0.0), reverse=True)
    summary = _summary(rows)
    return {
        **report_metadata(config.outputs_dir),
        "mode": OUTPUT_NAME,
        "packaged_execution_changed": False,
        "writes_eval_outputs": False,
        "writes_final_submission": False,
        "rows": rows,
        "summary": summary,
        "notes": [
            "Unsafe reasons are recomputed from current reports; no query-id conclusions are hard-coded.",
            "supportable_answer_delta penalizes token growth, unsupported/evidence risks, and answer drift.",
        ],
    }


def _evidence_row(row: dict[str, Any]) -> dict[str, Any]:
    reason = str(row.get("rejection_reason") or "")
    categories = _classify(reason, row)
    answer_delta = float(row.get("answer_score_delta") or 0.0)
    token_delta = float(row.get("token_delta") or 0.0)
    return {
        "source_report": "evidence_answer_candidate_eval",
        "query_id": row.get("query_id"),
        "query": row.get("query"),
        "candidate_id": "answer_only",
        "score_delta": row.get("score_delta"),
        "answer_score_delta": row.get("answer_score_delta"),
        "correctness_delta": row.get("correctness_delta"),
        "token_delta": row.get("token_delta"),
        "runtime_delta": row.get("runtime_delta"),
        "tool_delta": row.get("tool_delta"),
        "unsafe_reason": reason,
        "unsafe_categories": categories,
        "supportable_answer_delta": _supportable_delta(answer_delta, token_delta, categories),
        "baseline_answer_preview": row.get("baseline_final_answer_preview"),
        "candidate_answer_preview": row.get("candidate_final_answer_preview"),
    }


def _execution_candidate_row(row: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    reason = str(candidate.get("rejection_reasons") or candidate.get("gate_failures") or candidate.get("rejection_reason") or "")
    categories = _classify(reason, candidate)
    answer_delta = float(candidate.get("answer_score_delta") or candidate.get("correctness_delta") or candidate.get("score_delta") or 0.0)
    token_delta = float(candidate.get("token_delta") or 0.0)
    return {
        "source_report": "execution_candidate_search",
        "query_id": row.get("query_id"),
        "query": row.get("query"),
        "candidate_id": candidate.get("candidate_id"),
        "score_delta": candidate.get("score_delta"),
        "answer_score_delta": candidate.get("answer_score_delta"),
        "correctness_delta": candidate.get("correctness_delta"),
        "token_delta": candidate.get("token_delta"),
        "runtime_delta": candidate.get("runtime_delta"),
        "tool_delta": candidate.get("tool_delta"),
        "unsafe_reason": reason,
        "unsafe_categories": categories,
        "supportable_answer_delta": _supportable_delta(answer_delta, token_delta, categories),
    }


def _classify(reason: str, row: dict[str, Any]) -> list[str]:
    text = " ".join([reason, json.dumps(row, sort_keys=True, default=str)[:1000]]).lower()
    categories: list[str] = []
    if "fabrication" in text or "unsupported" in text or "payload_value" in text:
        categories.append("evidence_fabrication")
    if "final_answer_unsafe_drift" in text or "correctness_regressed" in text or "answer drift" in text:
        categories.append("answer_drift")
    if "unsupported_value" in text or "missing_or_unknown_evidence_id" in text:
        categories.append("unsupported_value")
    if "dry_run_labels" in text or "evidence_label_loss" in text:
        categories.append("dry_run_label_loss")
    if "token_gate" in text or "answer_token_budget" in text:
        categories.append("token_gate_failed")
    if "runtime_gate" in text or "tool" in text:
        categories.append("runtime_or_tool_gate")
    if "hidden" in text or "holdout" in text:
        categories.append("hidden_style_risk")
    if not categories:
        categories.append("no_score_or_answer_improvement")
    return sorted(set(categories))


def _supportable_delta(answer_delta: float, token_delta: float, categories: list[str]) -> float:
    penalty = max(0.0, token_delta) * 0.001
    if "evidence_fabrication" in categories or "unsupported_value" in categories:
        penalty += 0.08
    if "answer_drift" in categories:
        penalty += 0.05
    if "dry_run_label_loss" in categories:
        penalty += 0.04
    return round(answer_delta - penalty, 4)


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for row in rows:
        for category in row.get("unsafe_categories", []):
            counts[category] = counts.get(category, 0) + 1
    return {
        "total_rows": len(rows),
        "category_counts": dict(sorted(counts.items())),
        "top_supportable_rows": [row.get("query_id") for row in rows[:10]],
        "positive_supportable_rows": sum(1 for row in rows if float(row.get("supportable_answer_delta") or 0.0) > 0),
        "packaged_execution_changed": False,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Unsafe Answer Candidate Analysis",
        "",
        f"- Rows: {summary['total_rows']}",
        f"- Positive supportable rows: {summary['positive_supportable_rows']}",
        f"- Top supportable rows: {summary['top_supportable_rows']}",
        f"- Packaged execution changed: {summary['packaged_execution_changed']}",
        "",
        "## Category Counts",
        "",
    ]
    for category, count in summary.get("category_counts", {}).items():
        lines.append(f"- `{category}`: {count}")
    lines.extend(["", "## Top Rows", ""])
    for row in payload["rows"][:15]:
        lines.append(
            f"- `{row.get('query_id')}` `{row.get('candidate_id')}` supportable_delta={row.get('supportable_answer_delta')} "
            f"categories={row.get('unsafe_categories')} reason={row.get('unsafe_reason')}"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
