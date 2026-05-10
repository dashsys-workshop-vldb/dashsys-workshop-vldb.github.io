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

from dashagent.answer_shape import propose_answer_shape_candidate
from dashagent.config import Config
from dashagent.eval_harness import EvalHarness
from dashagent.executor import AgentExecutor
from dashagent.report_run import report_metadata
from dashagent.supportable_answer_rewriter import compare_plan_hashes, summarize_answer_rewrite
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


OUTPUT_NAME = "answer_shape_v2_ab_eval"
BASELINE_STRICT_SCORE = 0.6491
BASELINE_CORRECTNESS = 0.6743


def main() -> int:
    config = Config.from_env(ROOT)
    payload = run_answer_shape_v2_ab_eval(config)
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    json_path = config.outputs_dir / f"{OUTPUT_NAME}.json"
    md_path = config.outputs_dir / f"{OUTPUT_NAME}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    print(
        json.dumps(
            {
                "json": str(json_path),
                "markdown": str(md_path),
                "changed_rows": payload["summary"]["changed_rows"],
                "safe_rows": payload["summary"]["safe_rows"],
                "recommendation": payload["summary"]["recommendation"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def run_answer_shape_v2_ab_eval(config: Config) -> dict[str, Any]:
    strict = _load_json(config.outputs_dir / "eval_results_strict.json")
    hidden = _load_json(config.outputs_dir / "hidden_style_eval.json")
    output_root = config.outputs_dir / OUTPUT_NAME
    _assert_isolated(config.outputs_dir, output_root)
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)

    executor = AgentExecutor(config)
    examples = {example.query_id: example for example in EvalHarness(config).load_examples()}
    rows = []
    for strict_row in strict.get("rows", []):
        if strict_row.get("strategy") != "SQL_FIRST_API_VERIFY":
            continue
        rows.append(_evaluate_row(config, executor, output_root, strict_row, examples.get(str(strict_row.get("query_id")))))
    summary = _summary(rows, strict, hidden)
    return {
        **report_metadata(config.outputs_dir),
        "mode": OUTPUT_NAME,
        "feature_flag": "ENABLE_ANSWER_SHAPE_V2",
        "feature_flag_default": Config.from_env(config.project_root).enable_answer_shape_v2,
        "feature_flag_enabled_for_experiment": True,
        "packaged_execution_changed": False,
        "writes_eval_outputs": False,
        "writes_final_submission": False,
        "artifact_isolation": {
            "allowed_outputs": [f"outputs/{OUTPUT_NAME}.json", f"outputs/{OUTPUT_NAME}.md", f"outputs/{OUTPUT_NAME}/"],
            "candidate_output_root": f"outputs/{OUTPUT_NAME}/<query_id>/sql_first_api_verify/",
        },
        "rows": rows,
        "summary": summary,
        "notes": [
            "Answer-shape v2 is answer-only in this A/B eval: selected SQL/API and tool calls must be unchanged.",
            "Gold labels are used only for offline row-level scoring.",
            "Behavior-changing ties remain default-off.",
        ],
    }


def _evaluate_row(
    config: Config,
    executor: AgentExecutor,
    output_root: Path,
    strict_row: dict[str, Any],
    example: Any | None,
) -> dict[str, Any]:
    query_id = str(strict_row.get("query_id") or "")
    query = str(strict_row.get("query") or "")
    baseline = _load_trajectory(strict_row.get("output_dir"))
    baseline_answer = str(baseline.get("final_answer") or "")
    tool_results = _tool_results_from_trajectory(baseline)
    shape = propose_answer_shape_candidate(query, tool_results)
    candidate_answer = shape.text if shape.text else baseline_answer
    changed = candidate_answer != baseline_answer
    candidate = copy.deepcopy(baseline)
    if changed:
        candidate["final_answer"] = candidate_answer
        candidate.setdefault("steps", []).append(
            {
                "kind": "answer_diagnostics",
                "candidate_family": "answer_shape_v2",
                "answer_shape_v2": shape.as_dict(),
                "answer_only": True,
            }
        )
        candidate["estimated_tokens"] = official_estimated_tokens(candidate)

    output_dir = output_root / query_id / "sql_first_api_verify"
    _assert_isolated(config.outputs_dir, output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_candidate_artifacts(output_dir, query_id, query, candidate)

    if example is not None:
        scores = _score_result(executor, candidate, candidate_answer, example)
    else:
        scores = {"final_score": strict_row.get("final_score"), "correctness_score": strict_row.get("correctness_score"), "answer_score": strict_row.get("answer_score")}
    plan_hash = compare_plan_hashes(baseline, candidate)
    baseline_score = float(strict_row.get("final_score") or 0.0)
    baseline_correctness = float(strict_row.get("correctness_score") or 0.0)
    baseline_tokens = int(strict_row.get("estimated_tokens") or baseline.get("estimated_tokens") or 0)
    candidate_tokens = int(candidate.get("estimated_tokens") or baseline_tokens)
    baseline_runtime = float(strict_row.get("runtime") or baseline.get("runtime") or 0.0)
    candidate_runtime = float(candidate.get("runtime") or baseline_runtime)
    baseline_tools = int(strict_row.get("tool_call_count") or baseline.get("tool_call_count") or 0)
    candidate_tools = int(candidate.get("tool_call_count") or baseline_tools)
    row = {
        "query_id": query_id,
        "query": query,
        "candidate_family": shape.answer_shape,
        "changed_answer": changed,
        "baseline_answer": baseline_answer,
        "answer_shape_v2_answer": candidate_answer,
        "baseline_answer_preview": _preview(baseline_answer),
        "answer_shape_v2_answer_preview": _preview(candidate_answer),
        "evidence_used": list(shape.source_evidence),
        "supported": shape.supported,
        "unavailable_fields": list(shape.unavailable_fields),
        "answer_score_before": strict_row.get("answer_score"),
        "answer_score_after": scores.get("answer_score"),
        "answer_score_delta": round(float(scores.get("answer_score") or 0.0) - float(strict_row.get("answer_score") or 0.0), 4),
        "strict_score_before": round(baseline_score, 4),
        "strict_score_after": scores.get("final_score"),
        "strict_score_delta": round(float(scores.get("final_score") or 0.0) - baseline_score, 4),
        "correctness_before": round(baseline_correctness, 4),
        "correctness_after": scores.get("correctness_score"),
        "correctness_delta": round(float(scores.get("correctness_score") or 0.0) - baseline_correctness, 4),
        "baseline_tokens": baseline_tokens,
        "candidate_tokens": candidate_tokens,
        "token_delta": candidate_tokens - baseline_tokens,
        "baseline_runtime": baseline_runtime,
        "candidate_runtime": candidate_runtime,
        "runtime_delta": round(candidate_runtime - baseline_runtime, 4),
        "baseline_tool_calls": baseline_tools,
        "candidate_tool_calls": candidate_tools,
        "tool_delta": candidate_tools - baseline_tools,
        **plan_hash,
        "sql_changed": plan_hash.get("sql_hash_unchanged") is not True,
        "api_changed": plan_hash.get("api_hash_unchanged") is not True,
        "tool_calls_changed": plan_hash.get("tool_call_count_unchanged") is not True,
        "sql_api_tool_changed": not (
            plan_hash.get("sql_hash_unchanged")
            and plan_hash.get("api_hash_unchanged")
            and plan_hash.get("tool_call_count_unchanged")
        ),
        "required_fields_preserved": required_trajectory_fields_present(candidate),
        "dry_run_labels_preserved": _dry_run_labels(candidate) == _dry_run_labels(baseline),
        "live_api_evidence_fabricated": _live_api_evidence_available(candidate) and not _live_api_evidence_available(baseline),
        "candidate_output_dir": str(output_dir),
        **summarize_answer_rewrite(baseline_answer, candidate_answer, []),
    }
    safe, reason = _safe(row)
    row["safe_for_promotion_candidate"] = safe
    row["rejection_reason"] = reason
    return row


def _tool_results_from_trajectory(trajectory: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for step in trajectory.get("steps", []):
        if step.get("kind") == "sql_call":
            results.append(
                {
                    "type": "sql",
                    "step": {"sql": step.get("sql")},
                    "validation": step.get("validation") or {},
                    "payload": step.get("result") or {},
                }
            )
        elif step.get("kind") == "api_call":
            results.append(
                {
                    "type": "api",
                    "step": {
                        "method": step.get("method"),
                        "url": step.get("url"),
                        "params": step.get("params") or {},
                        "headers": step.get("headers") or {},
                        "family": _family_from_api_path(str(step.get("url") or "")),
                    },
                    "validation": step.get("validation") or {},
                    "payload": step.get("result") or {},
                }
            )
    return results


def _family_from_api_path(path: str) -> str:
    lowered = path.lower()
    if "batch" in lowered:
        return "batch"
    if "tag" in lowered:
        return "tag"
    if "mergepolic" in lowered:
        return "merge_policy"
    if "observability" in lowered:
        return "observability_metrics"
    if "segment" in lowered and "job" in lowered:
        return "segment_jobs"
    if "schema" in lowered:
        return "schema_dataset"
    if "journey" in lowered or "campaign" in lowered:
        return "journey"
    return ""


def _write_candidate_artifacts(output_dir: Path, query_id: str, query: str, trajectory: dict[str, Any]) -> None:
    (output_dir / "metadata.json").write_text(
        json.dumps({"query_id": query_id, "query": query, "answer_shape_v2_ab_eval": True}, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (output_dir / "filled_system_prompt.txt").write_text(
        "Answer-shape v2 A/B candidate. SQL/API planning unchanged.\n",
        encoding="utf-8",
    )
    (output_dir / "trajectory.json").write_text(json.dumps(trajectory, indent=2, sort_keys=True, default=str), encoding="utf-8")


def _safe(row: dict[str, Any]) -> tuple[bool, str]:
    failures: list[str] = []
    if row.get("changed_answer") is not True:
        failures.append("answer_unchanged")
    if float(row.get("strict_score_delta") or 0.0) <= 0:
        failures.append("no_strict_score_improvement")
    if float(row.get("answer_score_delta") or 0.0) <= 0:
        failures.append("no_answer_score_improvement")
    if float(row.get("correctness_delta") or 0.0) < 0:
        failures.append("correctness_regressed")
    if row.get("sql_api_tool_changed"):
        failures.append("sql_api_or_tool_changed")
    if int(row.get("token_delta") or 0) > max(1, int(row.get("baseline_tokens") or 1) * 0.02):
        failures.append("token_gate_failed")
    if float(row.get("runtime_delta") or 0.0) > max(0.001, float(row.get("baseline_runtime") or 0.0) * 0.10):
        failures.append("runtime_gate_failed")
    if row.get("required_fields_preserved") is not True:
        failures.append("required_fields_missing")
    if row.get("dry_run_labels_preserved") is not True:
        failures.append("dry_run_labels_changed")
    if row.get("live_api_evidence_fabricated"):
        failures.append("live_api_evidence_fabricated")
    return (not failures, "; ".join(failures))


def _summary(rows: list[dict[str, Any]], strict: dict[str, Any], hidden: dict[str, Any]) -> dict[str, Any]:
    changed = [row for row in rows if row.get("changed_answer")]
    safe = [row for row in rows if row.get("safe_for_promotion_candidate")]
    strict_summary = (strict.get("summary") or {}).get("by_strategy", {}).get("SQL_FIRST_API_VERIFY", {})
    baseline = float(strict_summary.get("avg_final_score") or BASELINE_STRICT_SCORE)
    baseline_correctness = float(strict_summary.get("avg_correctness_score") or BASELINE_CORRECTNESS)
    total = int(strict_summary.get("count") or len(rows) or 35)
    projected = round(baseline + sum(float(row.get("strict_score_delta") or 0.0) for row in safe) / max(1, total), 4)
    projected_correctness = round(baseline_correctness + sum(float(row.get("correctness_delta") or 0.0) for row in safe) / max(1, total), 4)
    hidden_gate = _hidden_gate_passed(hidden)
    all_safe = bool(safe) and projected > baseline and projected_correctness >= baseline_correctness and hidden_gate
    return {
        "total_rows": len(rows),
        "changed_rows": len(changed),
        "safe_rows": len(safe),
        "selected_query_ids": [row.get("query_id") for row in safe],
        "avg_answer_score_delta_changed": _avg(row.get("answer_score_delta") for row in changed),
        "avg_strict_score_delta_changed": _avg(row.get("strict_score_delta") for row in changed),
        "baseline_strict_final_score": round(baseline, 4),
        "projected_strict_final_score": projected,
        "baseline_correctness": round(baseline_correctness, 4),
        "projected_correctness": projected_correctness,
        "hidden_style_gate_passed": hidden_gate,
        "packaged_execution_changed": False,
        "recommendation": "safe_for_answer_shape_v2_trial" if all_safe else "keep_default_off",
    }


def _hidden_gate_passed(hidden: dict[str, Any]) -> bool:
    summary = hidden.get("summary") or {}
    return (
        int(summary.get("passed_cases") or 0) == int(summary.get("total_cases") or 0) >= 48
        and float(summary.get("family_stability_rate") or 0.0) >= 0.98
        and float(summary.get("schema_stability_rate") or 0.0) >= 0.98
    )


def _avg(values: Any) -> float:
    nums = [float(value or 0.0) for value in values]
    return round(sum(nums) / len(nums), 4) if nums else 0.0


def _assert_isolated(outputs_dir: Path, path: Path) -> None:
    resolved = path.resolve()
    allowed = (outputs_dir / OUTPUT_NAME).resolve()
    if resolved == allowed or allowed in resolved.parents:
        return
    raise RuntimeError(f"Answer-shape v2 A/B eval attempted to write outside isolated root: {path}")


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Answer-Shape v2 A/B Eval",
        "",
        f"- Rows: {summary['total_rows']}",
        f"- Changed rows: {summary['changed_rows']}",
        f"- Safe rows: {summary['safe_rows']}",
        f"- Projected strict final score: {summary['projected_strict_final_score']}",
        f"- Hidden-style gate passed: {summary['hidden_style_gate_passed']}",
        f"- Recommendation: `{summary['recommendation']}`",
        "",
        "## Changed Rows",
        "",
        "| Query ID | Shape | Answer Δ | Strict Δ | Token Δ | SQL/API/Tool Changed | Safe | Reason |",
        "| --- | --- | ---: | ---: | ---: | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        if not row.get("changed_answer"):
            continue
        lines.append(
            f"| `{row.get('query_id')}` | {row.get('candidate_family')} | {row.get('answer_score_delta')} | "
            f"{row.get('strict_score_delta')} | {row.get('token_delta')} | {row.get('sql_api_tool_changed')} | "
            f"{row.get('safe_for_promotion_candidate')} | {row.get('rejection_reason')} |"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
