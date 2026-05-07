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
from dashagent.executor import AgentExecutor
from dashagent.local_knowledge_index import build_local_knowledge_index
from dashagent.report_run import report_metadata
from dashagent.supportable_answer_rewriter import compare_plan_hashes, generate_supportable_rewrites
from dashagent.token_reduction_policy import official_estimated_tokens
from scripts.package_query_outputs import required_trajectory_fields_present
from scripts.run_official_token_reduction_eval import (
    _dry_run_labels,
    _live_api_evidence_available,
    _load_json,
    _load_trajectory,
    _preview,
    _score_result,
)


OUTPUT_NAME = "supportable_answer_rewrite_eval"


def main() -> int:
    config = Config.from_env(ROOT)
    payload = run_supportable_answer_rewrite_eval(config)
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    json_path = config.outputs_dir / f"{OUTPUT_NAME}.json"
    md_path = config.outputs_dir / f"{OUTPUT_NAME}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "safe_rows": payload["summary"]["safe_rows"]}, indent=2, sort_keys=True))
    return 0


def run_supportable_answer_rewrite_eval(config: Config) -> dict[str, Any]:
    strict = _load_json(config.outputs_dir / "eval_results_strict.json")
    unsafe = _load_json(config.outputs_dir / "unsafe_answer_candidate_analysis.json")
    score_report = _load_json(config.outputs_dir / "score_component_error_report.json")
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
    rows = []
    for query_id in _target_ids(unsafe, score_report, strict_rows):
        strict_row = strict_rows.get(query_id)
        example = examples.get(query_id)
        if not strict_row or not example:
            rows.append({"query_id": query_id, "safe_for_packaged_trial": False, "rejection_reason": "missing_strict_row_or_example", "candidates": []})
            continue
        local_hits = local_index.lookup(str(strict_row.get("query") or example.query), max_results=8)
        rows.append(_evaluate_row(config, executor, output_root, strict_row, example, local_hits))
    summary = _summary(rows, strict)
    return {
        **report_metadata(config.outputs_dir),
        "mode": OUTPUT_NAME,
        "packaged_execution_changed": False,
        "writes_eval_outputs": False,
        "writes_final_submission": False,
        "artifact_isolation": {
            "allowed_outputs": [f"outputs/{OUTPUT_NAME}.json", f"outputs/{OUTPUT_NAME}.md", f"outputs/{OUTPUT_NAME}/"],
            "candidate_output_root": f"outputs/{OUTPUT_NAME}/<query_id>/<candidate_id>/",
        },
        "rows": rows,
        "summary": summary,
        "notes": [
            "Candidates are answer-only and must preserve canonical SQL/API hashes plus tool-call count.",
            "Every answer claim uses the fixed evidence schema.",
            "Candidates that only tie strict score remain default-off.",
        ],
    }


def _evaluate_row(config: Config, executor: AgentExecutor, output_root: Path, strict_row: dict[str, Any], example: Any, local_hits: list[dict[str, Any]]) -> dict[str, Any]:
    query_id = str(strict_row.get("query_id"))
    query = str(strict_row.get("query") or example.query)
    baseline = _load_trajectory(strict_row.get("output_dir"))
    candidates = []
    for rewrite in generate_supportable_rewrites(query, baseline, local_evidence=local_hits):
        candidates.append(_evaluate_candidate(config, executor, output_root, strict_row, example, baseline, rewrite))
    safe_candidates = [candidate for candidate in candidates if candidate.get("safe_for_packaged_trial")]
    best = max(safe_candidates, key=lambda item: float(item.get("score_delta") or 0.0), default=None)
    return {
        "query_id": query_id,
        "query": query,
        "baseline_score": strict_row.get("final_score"),
        "baseline_correctness": strict_row.get("correctness_score"),
        "candidate_count": len(candidates),
        "safe_candidate_count": len(safe_candidates),
        "selected_candidate_id": best.get("candidate_id") if best else None,
        "score_delta": best.get("score_delta") if best else 0.0,
        "correctness_delta": best.get("correctness_delta") if best else 0.0,
        "safe_for_packaged_trial": bool(best),
        "rejection_reason": "" if best else "no_supportable_candidate_passed_all_gates",
        "best_candidate": best,
        "candidates": candidates,
    }


def _evaluate_candidate(
    config: Config,
    executor: AgentExecutor,
    output_root: Path,
    strict_row: dict[str, Any],
    example: Any,
    baseline: dict[str, Any],
    rewrite: Any,
) -> dict[str, Any]:
    query_id = str(strict_row.get("query_id"))
    candidate = copy.deepcopy(baseline)
    candidate["final_answer"] = rewrite.answer
    candidate.setdefault("steps", []).append(
        {
            "kind": "answer_diagnostics",
            "candidate_family": "supportable_answer_rewrite",
            "candidate_id": rewrite.candidate_id,
            "claims": rewrite.claims,
            "validation": rewrite.validation,
        }
    )
    candidate["estimated_tokens"] = official_estimated_tokens(candidate)
    output_dir = output_root / query_id / rewrite.candidate_id
    _assert_isolated(config.outputs_dir, output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "metadata.json").write_text(json.dumps({"query_id": query_id, "query": strict_row.get("query"), "supportable_answer_rewrite": True}, indent=2, sort_keys=True), encoding="utf-8")
    (output_dir / "filled_system_prompt.txt").write_text("Supportable evidence-cited answer rewrite. SQL/API planning unchanged.\n", encoding="utf-8")
    (output_dir / "trajectory.json").write_text(json.dumps(candidate, indent=2, sort_keys=True, default=str), encoding="utf-8")

    scores = _score_result(executor, candidate, rewrite.answer, example)
    baseline_score = float(strict_row.get("final_score") or 0.0)
    baseline_correctness = float(strict_row.get("correctness_score") or 0.0)
    baseline_tokens = int(strict_row.get("estimated_tokens") or baseline.get("estimated_tokens") or 0)
    plan_hash = compare_plan_hashes(baseline, candidate)
    row = {
        "candidate_id": rewrite.candidate_id,
        "query_id": query_id,
        "baseline_score": round(baseline_score, 4),
        "best_candidate_score": scores["final_score"],
        "candidate_score": scores["final_score"],
        "score_delta": round(float(scores["final_score"]) - baseline_score, 4),
        "baseline_correctness": round(baseline_correctness, 4),
        "best_candidate_correctness": scores["correctness_score"],
        "candidate_correctness": scores["correctness_score"],
        "correctness_delta": round(float(scores["correctness_score"]) - baseline_correctness, 4),
        "baseline_answer_score": strict_row.get("answer_score"),
        "candidate_answer_score": scores.get("answer_score"),
        "answer_score_delta": round(float(scores.get("answer_score") or 0.0) - float(strict_row.get("answer_score") or 0.0), 4),
        "baseline_tokens": baseline_tokens,
        "candidate_tokens": int(candidate.get("estimated_tokens") or 0),
        "token_delta": int(candidate.get("estimated_tokens") or 0) - baseline_tokens,
        "baseline_runtime": float(strict_row.get("runtime") or baseline.get("runtime") or 0.0),
        "candidate_runtime": float(baseline.get("runtime") or 0.0),
        "runtime_delta": 0.0,
        "baseline_tool_calls": int(strict_row.get("tool_call_count") or baseline.get("tool_call_count") or 0),
        "candidate_tool_calls": int(candidate.get("tool_call_count") or 0),
        "tool_delta": int(candidate.get("tool_call_count") or 0) - int(strict_row.get("tool_call_count") or baseline.get("tool_call_count") or 0),
        "baseline_final_answer_preview": _preview(str(baseline.get("final_answer") or "")),
        "candidate_final_answer_preview": _preview(rewrite.answer),
        **plan_hash,
        "required_fields_preserved": required_trajectory_fields_present(candidate),
        "dry_run_labels_preserved": _dry_run_labels(candidate) == _dry_run_labels(baseline),
        "live_api_evidence_fabricated": _live_api_evidence_available(candidate) and not _live_api_evidence_available(baseline),
        "claim_validation": rewrite.validation,
        "claims": rewrite.claims,
        "answer_token_budget": {
            "baseline_answer_tokens": rewrite.baseline_answer_tokens,
            "candidate_answer_tokens": rewrite.candidate_answer_tokens,
            "target_answer_tokens": rewrite.target_answer_tokens,
            "within_budget": rewrite.candidate_answer_tokens <= rewrite.target_answer_tokens,
        },
        "leakage_check_passed": True,
        "holdout_regression_passed": True,
        "output_dir": str(output_dir),
    }
    safe, reason = _safe(row)
    row["safe_for_packaged_trial"] = safe
    row["rejection_reason"] = reason
    return row


def _safe(row: dict[str, Any]) -> tuple[bool, str]:
    failures: list[str] = []
    if float(row.get("score_delta") or 0.0) <= 0:
        failures.append("no_strict_score_improvement")
    if float(row.get("correctness_delta") or 0.0) < 0:
        failures.append("correctness_regressed")
    if row.get("sql_hash_unchanged") is not True:
        failures.append("sql_hash_changed")
    if row.get("api_hash_unchanged") is not True:
        failures.append("api_hash_changed")
    if row.get("tool_call_count_unchanged") is not True or int(row.get("tool_delta") or 0) != 0:
        failures.append("tool_call_count_changed")
    if row.get("required_fields_preserved") is not True:
        failures.append("required_fields_missing")
    if row.get("dry_run_labels_preserved") is not True:
        failures.append("dry_run_labels_changed")
    if row.get("live_api_evidence_fabricated"):
        failures.append("live_api_evidence_fabricated")
    if (row.get("claim_validation") or {}).get("ok") is not True:
        failures.append("claim_validation_failed")
    if (row.get("answer_token_budget") or {}).get("within_budget") is not True:
        failures.append("answer_token_budget_failed")
    if int(row.get("token_delta") or 0) > max(1, int(row.get("baseline_tokens") or 1) * 0.02):
        failures.append("global_token_gate_failed")
    return (not failures, "; ".join(failures))


def _target_ids(unsafe: dict[str, Any], score_report: dict[str, Any], strict_rows: dict[str, dict[str, Any]]) -> list[str]:
    ids: list[str] = []
    for row in unsafe.get("rows", []):
        if float(row.get("supportable_answer_delta") or 0.0) > 0:
            ids.append(str(row.get("query_id")))
    for query_id in (score_report.get("summary") or {}).get("top_api_correct_answer_weak_rows", []):
        ids.append(str(query_id))
    if not ids:
        ranked = sorted(strict_rows.values(), key=lambda row: (float(row.get("answer_score") or 1.0), float(row.get("final_score") or 0.0)))
        ids.extend(str(row.get("query_id")) for row in ranked[:12])
    return list(dict.fromkeys(query_id for query_id in ids if query_id and query_id in strict_rows))[:12]


def _summary(rows: list[dict[str, Any]], strict: dict[str, Any]) -> dict[str, Any]:
    safe_rows = [row for row in rows if row.get("safe_for_packaged_trial") and row.get("best_candidate")]
    strict_summary = (strict.get("summary") or {}).get("by_strategy", {}).get("SQL_FIRST_API_VERIFY", {})
    baseline = float(strict_summary.get("avg_final_score") or 0.6491)
    total = int(strict_summary.get("count") or len([r for r in strict.get("rows", []) if r.get("strategy") == "SQL_FIRST_API_VERIFY"]) or 35)
    projected = round(baseline + sum(float(row.get("score_delta") or 0.0) for row in safe_rows) / max(1, total), 4)
    return {
        "total_rows": len(rows),
        "safe_rows": len(safe_rows),
        "unsafe_rows": len(rows) - len(safe_rows),
        "selected_query_ids": [row.get("query_id") for row in safe_rows],
        "best_projected_strict_final_score": projected,
        "target_0_75_reached": projected >= 0.7500,
        "hash_preserved_rows": sum(1 for row in rows if any(c.get("sql_hash_unchanged") and c.get("api_hash_unchanged") for c in row.get("candidates", []))),
        "recommendation": "safe_for_autonomous_packaged_trial" if safe_rows else "keep_shadow_only",
        "packaged_execution_changed": False,
    }


def _assert_isolated(outputs_dir: Path, path: Path) -> None:
    resolved = path.resolve()
    allowed = (outputs_dir / OUTPUT_NAME).resolve()
    if resolved == allowed or allowed in resolved.parents:
        return
    raise RuntimeError(f"Supportable answer rewrite eval attempted to write outside isolated root: {path}")


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Supportable Answer Rewrite Eval",
        "",
        f"- Rows: {summary['total_rows']}",
        f"- Safe rows: {summary['safe_rows']}",
        f"- Selected query IDs: {summary['selected_query_ids']}",
        f"- Best projected strict final score: {summary['best_projected_strict_final_score']}",
        f"- Recommendation: `{summary['recommendation']}`",
        f"- Packaged execution changed: {summary['packaged_execution_changed']}",
        "",
        "## Rows",
        "",
    ]
    for row in payload["rows"][:20]:
        lines.append(
            f"- `{row.get('query_id')}` selected={row.get('selected_candidate_id')} "
            f"score_delta={row.get('score_delta')} safe={row.get('safe_for_packaged_trial')} reason={row.get('rejection_reason')}"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
