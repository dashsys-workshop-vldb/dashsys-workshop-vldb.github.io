#!/usr/bin/env python
from __future__ import annotations

import copy
import json
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.eval_harness import EvalHarness
from dashagent.evidence_aware_answer_composer import answer_only_preserves_plan, compose_evidence_aware_answer
from dashagent.executor import AgentExecutor
from dashagent.local_knowledge_index import build_local_knowledge_index, requested_fact_coverage
from dashagent.report_run import report_metadata
from dashagent.token_reduction_policy import official_estimated_tokens
from scripts.package_query_outputs import required_trajectory_fields_present
from scripts.run_official_token_reduction_eval import (
    _canonical_api,
    _dry_run_labels,
    _live_api_evidence_available,
    _load_json,
    _load_trajectory,
    _preview,
    _score_result,
)


OUTPUT_NAME = "evidence_answer_candidate_eval"


def main() -> int:
    config = Config.from_env(ROOT)
    payload = run_evidence_answer_candidate_eval(config)
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    json_path = config.outputs_dir / f"{OUTPUT_NAME}.json"
    md_path = config.outputs_dir / f"{OUTPUT_NAME}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "safe_rows": payload["summary"]["safe_rows"]}, indent=2, sort_keys=True))
    return 0


def run_evidence_answer_candidate_eval(config: Config) -> dict[str, Any]:
    strict = _load_json(config.outputs_dir / "eval_results_strict.json")
    score_report = _load_json(config.outputs_dir / "score_component_error_report.json")
    if not score_report:
        try:
            from scripts.generate_score_component_error_report import generate_score_component_error_report

            score_report = generate_score_component_error_report(config)
        except Exception:
            score_report = {}
    output_root = config.outputs_dir / OUTPUT_NAME
    _assert_isolated(config.outputs_dir, output_root)
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)
    executor = AgentExecutor(config)
    examples = {example.query_id: example for example in EvalHarness(config).load_examples()}
    local_index = build_local_knowledge_index(config)
    strict_rows = {
        str(row.get("query_id")): row
        for row in strict.get("rows", [])
        if row.get("strategy") == "SQL_FIRST_API_VERIFY"
    }
    target_ids = _target_ids(score_report, strict_rows)
    rows = []
    for query_id in target_ids:
        row = strict_rows.get(str(query_id))
        example = examples.get(str(query_id))
        if not row or not example:
            rows.append({"query_id": query_id, "safe_for_packaged_trial": False, "rejection_reason": "missing_strict_row_or_example"})
            continue
        rows.append(_evaluate_row(config, executor, output_root, row, example, local_index.lookup(str(row.get("query") or example.query), max_results=8)))
    summary = _summary(rows, strict)
    return {
        **report_metadata(config.outputs_dir),
        "mode": OUTPUT_NAME,
        "answer_only_ablation": True,
        "packaged_execution_changed": False,
        "writes_eval_outputs": False,
        "writes_final_submission": False,
        "artifact_isolation": {
            "allowed_outputs": [f"outputs/{OUTPUT_NAME}.json", f"outputs/{OUTPUT_NAME}.md", f"outputs/{OUTPUT_NAME}/"],
            "candidate_output_root": f"outputs/{OUTPUT_NAME}/<query_id>/answer_only/",
        },
        "rows": rows,
        "summary": summary,
        "notes": [
            "Answer-only ablation must preserve selected SQL and selected API exactly.",
            "Dry-run answers must mark unsupported fields unavailable instead of inventing API payload values.",
            "Local Parquet evidence counts only when it maps to requested facts and is used in the answer evidence path.",
        ],
    }


def _evaluate_row(config: Config, executor: AgentExecutor, output_root: Path, strict_row: dict[str, Any], example: Any, local_hits: list[dict[str, Any]]) -> dict[str, Any]:
    query_id = str(strict_row.get("query_id"))
    query = str(strict_row.get("query") or example.query)
    baseline = _load_trajectory(strict_row.get("output_dir"))
    # The first ablation is answer-only from existing trajectory evidence. Local
    # Parquet evidence is evaluated separately by the fact-coverage report so it
    # cannot quietly turn this into a broader evidence-routing change.
    candidate_info = compose_evidence_aware_answer(query, baseline, local_evidence=[])
    candidate = copy.deepcopy(baseline)
    candidate["final_answer"] = candidate_info.answer
    candidate.setdefault("checkpoints", []).append(
        {
            "checkpoint_id": "checkpoint_evidence_answer_candidate",
            "answer_only": True,
            "local_evidence_used_in_final_answer": candidate_info.local_evidence_used_in_final_answer,
            "requested_fact_covered": candidate_info.requested_fact_covered,
            "packaged_execution_changed": False,
        }
    )
    candidate["estimated_tokens"] = official_estimated_tokens(candidate)
    output_dir = output_root / query_id / "answer_only"
    _assert_isolated(config.outputs_dir, output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "metadata.json").write_text(json.dumps({"query_id": query_id, "query": query, "answer_only_candidate": True}, indent=2, sort_keys=True), encoding="utf-8")
    (output_dir / "filled_system_prompt.txt").write_text("Evidence-aware answer-only candidate. SQL/API planning unchanged.\n", encoding="utf-8")
    (output_dir / "trajectory.json").write_text(json.dumps(candidate, indent=2, sort_keys=True, default=str), encoding="utf-8")
    scores = _score_result(executor, candidate, candidate_info.answer, example)
    baseline_score = float(strict_row.get("final_score") or 0.0)
    baseline_correctness = float(strict_row.get("correctness_score") or 0.0)
    plan_check = answer_only_preserves_plan(baseline, candidate)
    local_coverage = requested_fact_coverage(query, local_hits)
    row = {
        "query_id": query_id,
        "query": query,
        "baseline_score": round(baseline_score, 4),
        "candidate_score": scores["final_score"],
        "score_delta": round(float(scores["final_score"]) - baseline_score, 4),
        "baseline_correctness": round(baseline_correctness, 4),
        "candidate_correctness": scores["correctness_score"],
        "correctness_delta": round(float(scores["correctness_score"]) - baseline_correctness, 4),
        "baseline_answer_score": strict_row.get("answer_score"),
        "candidate_answer_score": scores.get("answer_score"),
        "answer_score_delta": round(float(scores.get("answer_score") or 0.0) - float(strict_row.get("answer_score") or 0.0), 4),
        "baseline_estimated_tokens": int(strict_row.get("estimated_tokens") or baseline.get("estimated_tokens") or 0),
        "candidate_estimated_tokens": int(candidate.get("estimated_tokens") or 0),
        "token_delta": int(candidate.get("estimated_tokens") or 0) - int(strict_row.get("estimated_tokens") or baseline.get("estimated_tokens") or 0),
        "baseline_runtime": float(strict_row.get("runtime") or baseline.get("runtime") or 0.0),
        "candidate_runtime": float(baseline.get("runtime") or 0.0),
        "runtime_delta": 0.0,
        "baseline_tool_calls": int(strict_row.get("tool_call_count") or baseline.get("tool_call_count") or 0),
        "candidate_tool_calls": int(candidate.get("tool_call_count") or 0),
        "tool_delta": int(candidate.get("tool_call_count") or 0) - int(strict_row.get("tool_call_count") or baseline.get("tool_call_count") or 0),
        "baseline_final_answer_preview": _preview(str(baseline.get("final_answer") or "")),
        "candidate_final_answer_preview": _preview(candidate_info.answer),
        **plan_check,
        "required_fields_preserved": required_trajectory_fields_present(candidate),
        "dry_run_labels_preserved": _dry_run_labels(candidate) == _dry_run_labels(baseline),
        "live_api_evidence_fabricated": _live_api_evidence_available(candidate) and not _live_api_evidence_available(baseline),
        "local_evidence_available": bool(local_hits),
        "local_evidence_used_in_final_answer": candidate_info.local_evidence_used_in_final_answer,
        "requested_fact_covered": bool(local_coverage.get("requested_fact_covered")),
        "score_delta_from_local_evidence": 0.0,
        "evidence_path": candidate_info.evidence_path,
        "unavailable_fields": candidate_info.unavailable_fields,
        "no_fabrication_checks": candidate_info.no_fabrication_checks,
        "output_dir": str(output_dir),
    }
    row["score_delta_from_local_evidence"] = row["score_delta"] if row["local_evidence_used_in_final_answer"] else 0.0
    safe, reason = _safe(row)
    row["safe_for_packaged_trial"] = safe
    row["rejection_reason"] = reason
    return row


def _target_ids(score_report: dict[str, Any], strict_rows: dict[str, dict[str, Any]]) -> list[str]:
    answer_targets = (score_report.get("summary") or {}).get("top_api_correct_answer_weak_rows") or []
    if answer_targets:
        return [str(item) for item in answer_targets[:12]]
    ranked = sorted(
        strict_rows.values(),
        key=lambda row: (
            0 if row.get("api_score") is not None and float(row.get("api_score") or 0.0) >= 0.95 else 1,
            float(row.get("answer_score") or 1.0),
            float(row.get("final_score") or 0.0),
        ),
    )
    return [str(row.get("query_id")) for row in ranked[:12]]


def _safe(row: dict[str, Any]) -> tuple[bool, str]:
    failures = []
    if float(row.get("score_delta") or 0.0) <= 0 and float(row.get("answer_score_delta") or 0.0) <= 0:
        failures.append("no_score_or_answer_improvement")
    if float(row.get("correctness_delta") or 0.0) < 0:
        failures.append("correctness_regressed")
    if row.get("selected_sql_unchanged") is not True:
        failures.append("selected_sql_changed")
    if row.get("selected_api_unchanged") is not True:
        failures.append("selected_api_changed")
    if row.get("required_fields_preserved") is not True:
        failures.append("required_fields_missing")
    if row.get("dry_run_labels_preserved") is not True:
        failures.append("dry_run_labels_changed")
    if row.get("live_api_evidence_fabricated"):
        failures.append("live_api_evidence_fabricated")
    if int(row.get("tool_delta") or 0) > 0:
        failures.append("tool_calls_increased")
    if int(row.get("token_delta") or 0) > max(1, int(row.get("baseline_estimated_tokens") or 1) * 0.02):
        failures.append("token_gate_failed")
    checks = row.get("no_fabrication_checks") or {}
    if checks.get("uses_only_recorded_evidence") is not True or checks.get("dry_run_payload_values_used"):
        failures.append("evidence_fabrication_risk")
    return (not failures, "; ".join(failures))


def _summary(rows: list[dict[str, Any]], strict: dict[str, Any]) -> dict[str, Any]:
    safe = [row for row in rows if row.get("safe_for_packaged_trial")]
    strict_summary = (strict.get("summary") or {}).get("by_strategy", {}).get("SQL_FIRST_API_VERIFY", {})
    baseline = float(strict_summary.get("avg_final_score") or 0.6491)
    total = int(strict_summary.get("count") or len([r for r in strict.get("rows", []) if r.get("strategy") == "SQL_FIRST_API_VERIFY"]) or 35)
    projected = round(baseline + sum(float(row.get("score_delta") or 0.0) for row in safe) / max(1, total), 4)
    return {
        "total_rows": len(rows),
        "safe_rows": len(safe),
        "unsafe_rows": len(rows) - len(safe),
        "answer_only_sql_api_unchanged_rows": sum(1 for row in rows if row.get("answer_only_plan_preserved")),
        "local_evidence_available_rows": sum(1 for row in rows if row.get("local_evidence_available")),
        "local_evidence_used_rows": sum(1 for row in rows if row.get("local_evidence_used_in_final_answer")),
        "requested_fact_covered_rows": sum(1 for row in rows if row.get("requested_fact_covered")),
        "best_projected_strict_final_score": projected,
        "target_0_75_reached": projected >= 0.7500,
        "selected_query_ids": [row.get("query_id") for row in safe],
        "recommendation": "safe_for_autonomous_packaged_trial" if safe else "keep_shadow_only",
        "packaged_execution_changed": False,
    }


def _assert_isolated(outputs_dir: Path, path: Path) -> None:
    resolved = path.resolve()
    allowed = (outputs_dir / OUTPUT_NAME).resolve()
    if resolved == allowed or allowed in resolved.parents:
        return
    raise RuntimeError(f"Evidence answer eval attempted to write outside isolated root: {path}")


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Evidence-Aware Answer Candidate Eval",
        "",
        f"- Rows: {summary['total_rows']}",
        f"- Safe rows: {summary['safe_rows']}",
        f"- Answer-only SQL/API unchanged rows: {summary['answer_only_sql_api_unchanged_rows']}",
        f"- Local evidence available/used/requested-covered rows: {summary['local_evidence_available_rows']} / {summary['local_evidence_used_rows']} / {summary['requested_fact_covered_rows']}",
        f"- Best projected strict final score: {summary['best_projected_strict_final_score']}",
        f"- Recommendation: `{summary['recommendation']}`",
        f"- Packaged execution changed: {summary['packaged_execution_changed']}",
        "",
        "## Rows",
        "",
    ]
    for row in payload["rows"][:20]:
        lines.append(
            f"- `{row.get('query_id')}` score_delta={row.get('score_delta')} answer_delta={row.get('answer_score_delta')} "
            f"sql_api_same={row.get('answer_only_plan_preserved')} local_used={row.get('local_evidence_used_in_final_answer')} safe={row.get('safe_for_packaged_trial')}"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
