#!/usr/bin/env python
from __future__ import annotations

import json
import shutil
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.eval_harness import (
    EvalHarness,
    aggregate_strict_correctness,
    first_generated_sql,
    generated_api_calls,
    score_answer_strict,
    score_api_strict,
    score_sql_strict,
)
from dashagent.executor import AgentExecutor


def main() -> int:
    config = Config.from_env(ROOT)
    payload = run_compact_context_measured_eval(config)
    json_path = config.outputs_dir / "compact_context_measured_eval.json"
    md_path = config.outputs_dir / "compact_context_measured_eval.md"
    _assert_allowed_report(config.outputs_dir, json_path)
    _assert_allowed_report(config.outputs_dir, md_path)
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "rows": len(payload.get("rows", []))}, indent=2, sort_keys=True))
    return 0


def run_compact_context_measured_eval(config: Config) -> dict[str, Any]:
    shadow_gate = verify_shadow_safety_gate(config)
    if not shadow_gate["ok"]:
        raise RuntimeError("Shadow repair safety gate failed; compact-context measured eval is blocked: " + "; ".join(shadow_gate["failed_checks"]))

    candidate_report = _load_json(config.outputs_dir / "candidate_context_report.json")
    strict_rows = _strict_sql_first_rows(config.outputs_dir)
    examples = {example.query_id: example for example in EvalHarness(config).load_examples()}
    experiment_config = replace(config, enable_compact_context_when_schema_vote_safe=True)
    executor = AgentExecutor(experiment_config)
    experiment_root = config.outputs_dir / "compact_context_measured_eval"
    rows: list[dict[str, Any]] = []

    for candidate in candidate_report.get("rows", []) or []:
        eligibility = _compact_eligibility(candidate, config)
        if not eligibility["eligible"]:
            continue
        query_id = str(candidate.get("query_id") or "")
        example = examples.get(query_id)
        current = strict_rows.get(query_id, {})
        if not example or not current:
            continue
        current_trajectory = _load_trajectory(current.get("output_dir"))
        output_dir = experiment_root / query_id / "compact_sql_first"
        _assert_allowed_experiment_dir(config.outputs_dir, output_dir)
        if output_dir.exists():
            shutil.rmtree(output_dir)
        result = executor.run(
            example.query,
            strategy="SQL_FIRST_API_VERIFY",
            query_id=query_id,
            output_dir=output_dir,
        )
        compact_trajectory = result["trajectory"]
        compact_score = _score_compact_row(executor, compact_trajectory, result["final_answer"], example)
        current_sql = first_generated_sql(current_trajectory)
        compact_sql = first_generated_sql(compact_trajectory)
        current_api = generated_api_calls(current_trajectory)
        compact_api = generated_api_calls(compact_trajectory)
        current_answer = str(current_trajectory.get("final_answer") or "")
        compact_answer = str(result.get("final_answer") or "")
        current_score = _float(current.get("final_score"))
        score_delta = round(compact_score["final_score"] - current_score, 4)
        current_tokens = int(current.get("estimated_tokens") or 0)
        compact_tokens = int(compact_trajectory.get("estimated_tokens") or 0)
        current_runtime = _float(current.get("runtime"))
        compact_runtime = _float(compact_trajectory.get("runtime"))
        row = {
            "query_id": query_id,
            "query": example.query,
            "current_score": current_score,
            "compact_score": compact_score["final_score"],
            "score_delta": score_delta,
            "current_tokens": current_tokens,
            "compact_tokens": compact_tokens,
            "token_delta": compact_tokens - current_tokens,
            "current_runtime": current_runtime,
            "compact_runtime": round(compact_runtime, 4),
            "runtime_delta": round(compact_runtime - current_runtime, 4),
            "current_tool_calls": int(current.get("tool_call_count") or 0),
            "compact_tool_calls": int(compact_trajectory.get("tool_call_count") or 0),
            "tool_delta": int(compact_trajectory.get("tool_call_count") or 0) - int(current.get("tool_call_count") or 0),
            "final_answer_changed": current_answer != compact_answer,
            "sql_changed": (current_sql or "") != (compact_sql or ""),
            "api_changed": current_api != compact_api,
            "current_sql": current_sql,
            "compact_sql": compact_sql,
            "current_api_calls": current_api,
            "compact_api_calls": compact_api,
            "compact_context_safe": eligibility["compact_context_safe"],
            "schema_vote_agreement": eligibility["schema_vote_agreement"],
            "risk_level": eligibility["risk_level"],
            "table_top_agreement": eligibility["table_top_agreement"],
            "api_top_agreement": eligibility["api_top_agreement"],
            "compact_output_dir": str(output_dir),
            "packaged_execution_changed": False,
            "official_submission_metrics_updated": False,
            "preferred_strategy_changed": False,
            **compact_score,
        }
        row["experiment_safe_to_enable"] = _row_safe_to_enable(row)
        row["rejection_reasons"] = _row_rejection_reasons(row)
        rows.append(row)

    summary = _summary(rows)
    return {
        "mode": "compact_context_measured_eval",
        "shadow_safety_gate": shadow_gate,
        "feature_flag": "ENABLE_COMPACT_CONTEXT_WHEN_SCHEMA_VOTE_SAFE",
        "feature_flag_default": False,
        "feature_flag_enabled_for_experiment": True,
        "packaged_execution_changed": False,
        "official_submission_metrics_updated": False,
        "preferred_strategy_changed": False,
        "rows": rows,
        "summary": summary,
        "acceptance_criteria": {
            "all_score_delta_nonnegative": all(row.get("score_delta", 0) >= 0 for row in rows),
            "no_final_answer_changes": not any(row.get("final_answer_changed") for row in rows),
            "tool_delta_nonpositive": all(row.get("tool_delta", 0) <= 0 for row in rows),
            "avg_token_delta_negative": summary["avg_token_delta"] < 0 if rows else False,
            "avg_runtime_delta_nonpositive": summary["avg_runtime_delta"] <= 0 if rows else False,
            "no_live_api_evidence_fabricated": True,
        },
        "artifact_isolation": {
            "allowed_report_outputs": [
                "outputs/compact_context_measured_eval.json",
                "outputs/compact_context_measured_eval.md",
            ],
            "allowed_experiment_output_root": "outputs/compact_context_measured_eval/<query_id>/compact_sql_first/",
            "writes_eval_outputs": False,
            "writes_final_submission": False,
            "writes_packaged_query_outputs": False,
        },
        "notes": [
            "This is an isolated measured experiment; it does not update official eval results or submission metrics.",
            "Baseline rows are read from existing SQL_FIRST_API_VERIFY strict outputs.",
            "Compact-enabled runs write only under outputs/compact_context_measured_eval/<query_id>/compact_sql_first/.",
            "Measured efficiency improvement is experimental only and is not claimed for packaged SQL_FIRST_API_VERIFY.",
        ],
    }


def verify_shadow_safety_gate(config: Config) -> dict[str, Any]:
    shadow = _load_json(config.outputs_dir / "shadow_repair_eval.json")
    summary = shadow.get("paired_shadow_eval_summary", {})
    rows = shadow.get("rows", []) or []
    canaries = shadow.get("cluster_canary_recommendations", {}) or {}
    manifest = _load_json(config.outputs_dir / "final_submission_manifest.json")
    failed: list[str] = []
    if summary.get("safe_repaired_worse_count") != 0:
        failed.append("safe_repaired_worse_count")
    if _float(summary.get("safe_avg_score_delta")) < 0:
        failed.append("safe_avg_score_delta")
    if any("safe_shadow_tie_recommend_canary" in str(row.get("decision")) for row in rows):
        failed.append("safe_shadow_tie_recommend_canary")
    if any(bool(value.get("safe_to_enable_canary")) for value in canaries.values() if isinstance(value, dict)):
        failed.append("repair_canary_enabled")
    if config.enable_gated_risk_cluster_repair_execution:
        failed.append("repair_execution_enabled")
    if manifest.get("preferred_strategy") not in {None, "SQL_FIRST_API_VERIFY"}:
        failed.append("preferred_strategy")
    if _contains_text(config.outputs_dir / "final_submission", "offline_score_delta") or _contains_text(config.outputs_dir / "eval", "offline_score_delta"):
        failed.append("offline_score_delta_packaged_output")
    return {
        "ok": not failed,
        "failed_checks": failed,
        "safe_repaired_worse_count": summary.get("safe_repaired_worse_count"),
        "safe_avg_score_delta": summary.get("safe_avg_score_delta"),
        "enabled_canaries": [key for key, value in canaries.items() if isinstance(value, dict) and value.get("safe_to_enable_canary")],
        "repair_execution_enabled": config.enable_gated_risk_cluster_repair_execution,
        "preferred_strategy": manifest.get("preferred_strategy"),
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload.get("summary", {})
    lines = [
        "# Compact Context Measured Evaluation",
        "",
        "This report is experimental and isolated. It does not update official SQL_FIRST_API_VERIFY scores, preferred strategy, submission metrics, or final submission artifacts.",
        "",
        f"- Shadow safety gate passed: {payload.get('shadow_safety_gate', {}).get('ok')}",
        f"- Feature flag: `{payload.get('feature_flag')}` (default: {payload.get('feature_flag_default')}; enabled for experiment: {payload.get('feature_flag_enabled_for_experiment')})",
        f"- Packaged execution changed: {payload.get('packaged_execution_changed')}",
        f"- Official submission metrics updated: {payload.get('official_submission_metrics_updated')}",
        f"- Preferred strategy changed: {payload.get('preferred_strategy_changed')}",
        f"- Rows: {summary.get('row_count')}",
        f"- Avg score delta: {summary.get('avg_score_delta')}",
        f"- Avg token delta: {summary.get('avg_token_delta')}",
        f"- Avg runtime delta: {summary.get('avg_runtime_delta')}",
        f"- Avg tool delta: {summary.get('avg_tool_delta')}",
        f"- Experimental measured efficiency improvement claimed: {summary.get('experimental_measured_efficiency_improvement_claimed')}",
        f"- Official measured efficiency improvement claimed: {summary.get('official_measured_efficiency_improvement_claimed')}",
        "",
        "| Query ID | Current score | Compact score | Score delta | Token delta | Runtime delta | Tool delta | Answer changed? | Safe to enable? |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in payload.get("rows", []):
        lines.append(
            f"| `{row.get('query_id')}` | {row.get('current_score')} | {row.get('compact_score')} | "
            f"{row.get('score_delta')} | {row.get('token_delta')} | {row.get('runtime_delta')} | "
            f"{row.get('tool_delta')} | {row.get('final_answer_changed')} | {row.get('experiment_safe_to_enable')} |"
        )
    lines.extend(["", "## Notes", ""])
    lines.extend(f"- {note}" for note in payload.get("notes", []))
    return "\n".join(lines) + "\n"


def _compact_eligibility(candidate: dict[str, Any], config: Config) -> dict[str, Any]:
    vote = candidate.get("schema_context_vote") or {}
    compact_tables = vote.get("compact_candidate_tables") or []
    fallback_tables = vote.get("fallback_candidate_tables") or []
    compact_apis = vote.get("compact_candidate_apis") or []
    fallback_apis = vote.get("fallback_candidate_apis") or []
    table_top_agreement = _top_items_agree(compact_tables, fallback_tables)
    api_top_agreement = _top_items_agree(compact_apis, fallback_apis) or (not compact_apis and not fallback_apis)
    eligible = bool(
        candidate.get("risk_level") == "high"
        and vote.get("schema_vote_agreement") is True
        and vote.get("compact_context_safe") is True
        and table_top_agreement
        and api_top_agreement
        and not config.enable_gated_risk_cluster_repair_execution
    )
    return {
        "eligible": eligible,
        "risk_level": candidate.get("risk_level"),
        "schema_vote_agreement": vote.get("schema_vote_agreement"),
        "compact_context_safe": vote.get("compact_context_safe"),
        "table_top_agreement": table_top_agreement,
        "api_top_agreement": api_top_agreement,
    }


def _score_compact_row(executor: AgentExecutor, trajectory: dict[str, Any], final_answer: str, example: Any) -> dict[str, Any]:
    generated_sql = first_generated_sql(trajectory)
    generated_api = generated_api_calls(trajectory)
    sql_score, sql_reason = score_sql_strict(executor.db, generated_sql, example.gold_sql)
    api_score, api_reason = score_api_strict(generated_api, example.gold_api)
    answer_score, answer_reason = score_answer_strict(final_answer, example.gold_answer)
    correctness_score, unscored_dimension_count = aggregate_strict_correctness(
        {"sql": sql_score, "api": api_score, "answer": answer_score}
    )
    efficiency_penalty = min(
        1.0,
        (trajectory.get("tool_call_count", 0) / 8)
        + (trajectory.get("runtime", 0.0) / 30)
        + (trajectory.get("estimated_tokens", 0) / 12000),
    )
    final_score = correctness_score - 0.1 * efficiency_penalty
    return {
        "compact_sql_score": round(sql_score, 4) if sql_score is not None else None,
        "compact_api_score": round(api_score, 4) if api_score is not None else None,
        "compact_answer_score": round(answer_score, 4) if answer_score is not None else None,
        "compact_correctness_score": round(correctness_score, 4),
        "compact_efficiency_penalty": round(efficiency_penalty, 4),
        "final_score": round(final_score, 4),
        "compact_sql_reason": sql_reason,
        "compact_api_reason": api_reason,
        "compact_answer_reason": answer_reason,
        "compact_unscored_dimension_count": unscored_dimension_count,
    }


def _row_safe_to_enable(row: dict[str, Any]) -> bool:
    return bool(
        row.get("score_delta", 0) >= 0
        and row.get("tool_delta", 0) <= 0
        and row.get("token_delta", 0) < 0
        and row.get("final_answer_changed") is False
    )


def _row_rejection_reasons(row: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if row.get("score_delta", 0) < 0:
        reasons.append("score_delta_negative")
    if row.get("tool_delta", 0) > 0:
        reasons.append("tool_delta_positive")
    if row.get("token_delta", 0) >= 0:
        reasons.append("token_delta_not_negative")
    if row.get("final_answer_changed"):
        reasons.append("final_answer_changed")
    return reasons


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    avg_runtime_delta = _avg(row.get("runtime_delta") for row in rows)
    experimental_efficiency = bool(
        rows
        and all(row.get("experiment_safe_to_enable") for row in rows)
        and _avg(row.get("token_delta") for row in rows) < 0
        and avg_runtime_delta <= 0
    )
    experimental_accuracy = bool(rows and all(row.get("score_delta", 0) >= 0 for row in rows) and any(row.get("score_delta", 0) > 0 for row in rows))
    return {
        "row_count": len(rows),
        "avg_score_delta": _avg(row.get("score_delta") for row in rows),
        "avg_token_delta": _avg(row.get("token_delta") for row in rows),
        "avg_runtime_delta": avg_runtime_delta,
        "avg_tool_delta": _avg(row.get("tool_delta") for row in rows),
        "final_answer_changed_count": sum(1 for row in rows if row.get("final_answer_changed")),
        "sql_changed_count": sum(1 for row in rows if row.get("sql_changed")),
        "api_changed_count": sum(1 for row in rows if row.get("api_changed")),
        "experiment_safe_to_enable_count": sum(1 for row in rows if row.get("experiment_safe_to_enable")),
        "experimental_measured_accuracy_improvement_claimed": experimental_accuracy,
        "experimental_measured_efficiency_improvement_claimed": experimental_efficiency,
        "official_measured_accuracy_improvement_claimed": False,
        "official_measured_efficiency_improvement_claimed": False,
        "packaged_execution_changed": False,
        "official_submission_metrics_updated": False,
    }


def _strict_sql_first_rows(outputs_dir: Path) -> dict[str, dict[str, Any]]:
    payload = _load_json(outputs_dir / "eval_results_strict.json")
    return {
        str(row.get("query_id")): row
        for row in payload.get("rows", []) or []
        if row.get("strategy") == "SQL_FIRST_API_VERIFY"
    }


def _load_trajectory(output_dir: Any) -> dict[str, Any]:
    if not output_dir:
        return {}
    return _load_json(Path(str(output_dir)) / "trajectory.json")


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _contains_text(root: Path, needle: str) -> bool:
    if not root.exists():
        return False
    for path in root.rglob("*"):
        if path.is_file() and needle in path.read_text(encoding="utf-8", errors="ignore"):
            return True
    return False


def _assert_allowed_report(outputs_dir: Path, path: Path) -> None:
    allowed = {
        (outputs_dir / "compact_context_measured_eval.json").resolve(),
        (outputs_dir / "compact_context_measured_eval.md").resolve(),
    }
    if path.resolve() not in allowed:
        raise RuntimeError(f"Refusing to write compact measured report outside isolated paths: {path}")


def _assert_allowed_experiment_dir(outputs_dir: Path, path: Path) -> None:
    root = (outputs_dir / "compact_context_measured_eval").resolve()
    resolved = path.resolve()
    if root not in [resolved, *resolved.parents] or resolved.name != "compact_sql_first":
        raise RuntimeError(f"Refusing to write compact measured run outside isolated experiment root: {path}")


def _top_items_agree(left: list[Any], right: list[Any]) -> bool:
    if not left or not right:
        return False
    left_norm = {str(item).strip().lower() for item in left[:3] if str(item).strip()}
    right_norm = {str(item).strip().lower() for item in right[:3] if str(item).strip()}
    return bool(left_norm & right_norm)


def _float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _avg(values: Any) -> float:
    numbers = [float(value or 0.0) for value in values]
    return round(sum(numbers) / len(numbers), 4) if numbers else 0.0


if __name__ == "__main__":
    raise SystemExit(main())
