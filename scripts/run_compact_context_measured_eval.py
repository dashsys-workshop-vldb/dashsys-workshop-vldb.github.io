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
    EvalExample,
    EvalHarness,
    aggregate_strict_correctness,
    first_generated_sql,
    generated_api_calls,
    normalize_sql,
    score_answer_strict,
    score_api_strict,
    score_sql_strict,
)
from dashagent.executor import AgentExecutor
from dashagent.trajectory import estimate_tokens


CANARY_CONFIG_FIELDS = [
    "enable_repair_for_batch_endpoint_confusion",
    "enable_repair_for_tag_api_confusion",
    "enable_repair_for_schema_dataset_confusion",
    "enable_repair_for_zero_score_margin",
    "enable_repair_for_missing_api_topk",
]

REQUIRED_ROW_FIELDS = [
    "query_id",
    "query",
    "eligible",
    "skip_reason",
    "current_score",
    "compact_score",
    "score_delta",
    "current_tokens",
    "compact_tokens",
    "token_delta",
    "current_total_estimated_tokens",
    "compact_total_estimated_tokens",
    "current_context_tokens",
    "compact_context_tokens",
    "fallback_context_tokens",
    "checkpoint_overhead_tokens",
    "checkpoint_overhead_in_total_tokens",
    "answer_generation_tokens",
    "token_delta_total",
    "token_delta_context_only",
    "token_delta_checkpoint_overhead",
    "token_measurement_classification",
    "current_runtime",
    "compact_runtime",
    "runtime_delta",
    "current_tool_calls",
    "compact_tool_calls",
    "tool_delta",
    "current_final_answer_preview",
    "compact_final_answer_preview",
    "final_answer_changed",
    "current_sql",
    "compact_sql",
    "sql_changed",
    "current_api",
    "compact_api",
    "api_changed",
    "schema_vote_agreement",
    "compact_context_safe",
    "experiment_safe_to_enable",
]


def main() -> int:
    config = Config.from_env(ROOT)
    payload = run_compact_context_measured_eval(config)
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    json_path = config.outputs_dir / "compact_context_measured_eval.json"
    md_path = config.outputs_dir / "compact_context_measured_eval.md"
    _assert_allowed_output(config.outputs_dir, json_path)
    _assert_allowed_output(config.outputs_dir, md_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "rows": len(payload.get("rows", []))}, indent=2, sort_keys=True))
    return 0


def run_compact_context_measured_eval(config: Config) -> dict[str, Any]:
    shadow_gate = verify_shadow_safety_gate(config)
    if not shadow_gate["ok"]:
        raise RuntimeError("Compact-context measured eval refused to run: " + "; ".join(shadow_gate["failed_checks"]))

    candidate_report = _load_json(config.outputs_dir / "candidate_context_report.json")
    strict_rows = _strict_sql_first_rows(config.outputs_dir)
    compact_root = config.outputs_dir / "compact_context_measured_eval"
    _assert_allowed_output(config.outputs_dir, compact_root)
    if compact_root.exists():
        shutil.rmtree(compact_root)
    compact_root.mkdir(parents=True, exist_ok=True)

    compact_config = replace(config, enable_compact_context_when_schema_vote_safe=True)
    compact_executor = AgentExecutor(compact_config)
    examples = {example.query_id: example for example in EvalHarness(config).load_examples()}
    rows: list[dict[str, Any]] = []
    for candidate in candidate_report.get("rows", []) or []:
        rows.append(
            _evaluate_candidate_row(
                config=config,
                compact_executor=compact_executor,
                compact_root=compact_root,
                candidate=candidate,
                strict_rows=strict_rows,
                examples=examples,
                shadow_gate=shadow_gate,
            )
        )
    summary = _summary(rows)
    token_accounting_analysis = _token_accounting_analysis(rows)
    payload = {
        "mode": "compact_context_measured_eval",
        "shadow_safety_gate": shadow_gate,
        "feature_flag_default": Config.from_env(config.project_root).enable_compact_context_when_schema_vote_safe,
        "feature_flag_enabled_for_experiment": True,
        "packaged_execution_changed": False,
        "official_submission_metrics_updated": False,
        "measured_efficiency_improvement_is_experimental_only": True,
        "measured_efficiency_improvement_claimed": summary["measured_efficiency_improvement_claimed"],
        "official_measured_efficiency_improvement_claimed": False,
        "behavior_changing_flags_enabled": False,
        "behavior_changing_flags_note": "No behavior-changing flags were enabled in this pass.",
        "rows": rows,
        "summary": summary,
        "token_accounting_analysis": token_accounting_analysis,
        "measurement_caveat": token_accounting_analysis["measurement_caveat"],
        "artifact_isolation": {
            "allowed_outputs": [
                "outputs/compact_context_measured_eval.json",
                "outputs/compact_context_measured_eval.md",
                "outputs/compact_context_measured_eval/",
            ],
            "experiment_output_root": "outputs/compact_context_measured_eval/<query_id>/compact_sql_first/",
            "writes_eval_outputs": False,
            "writes_final_submission": False,
            "writes_packaged_query_outputs": False,
        },
        "notes": [
            "Measured efficiency improvement is experimental only, not packaged-submission improvement.",
            "Baseline rows are read from current SQL_FIRST_API_VERIFY strict outputs.",
            "Compact-enabled runs write only under outputs/compact_context_measured_eval/<query_id>/compact_sql_first/.",
            "The packaged SQL_FIRST_API_VERIFY path and final submission artifacts are not modified by this script.",
            "Repair execution and all repair canaries remain disabled.",
            "Trajectory estimated_tokens remains the official efficiency metric, but it is not a full prompt-token measurement.",
        ],
    }
    return payload


def verify_shadow_safety_gate(config: Config) -> dict[str, Any]:
    shadow = _load_json(config.outputs_dir / "shadow_repair_eval.json")
    summary = shadow.get("paired_shadow_eval_summary") or {}
    failed: list[str] = []
    if not shadow:
        failed.append("shadow_repair_eval_missing")
    if int(summary.get("safe_repaired_worse_count") or 0) != 0:
        failed.append("safe_repaired_worse_count_nonzero")
    if float(summary.get("safe_avg_score_delta") or 0.0) < 0:
        failed.append("safe_avg_score_delta_negative")
    if any(row.get("decision") == "safe_shadow_tie_recommend_canary" for row in shadow.get("rows", []) or []):
        failed.append("safe_shadow_tie_recommend_canary_present")
    if shadow.get("repair_execution_enabled") is True or config.enable_gated_risk_cluster_repair_execution:
        failed.append("repair_execution_enabled")
    enabled_shadow_canaries = [
        name
        for name, recommendation in (shadow.get("cluster_canary_recommendations") or {}).items()
        if isinstance(recommendation, dict) and recommendation.get("safe_to_enable_canary")
    ]
    enabled_config_canaries = [field for field in CANARY_CONFIG_FIELDS if getattr(config, field)]
    if enabled_shadow_canaries:
        failed.append("shadow_canary_enabled")
    if enabled_config_canaries:
        failed.append("config_canary_enabled")
    return {
        "ok": not failed,
        "failed_checks": failed,
        "safe_repaired_worse_count": summary.get("safe_repaired_worse_count"),
        "safe_avg_score_delta": summary.get("safe_avg_score_delta"),
        "enabled_shadow_canaries": enabled_shadow_canaries,
        "enabled_config_canaries": enabled_config_canaries,
        "repair_execution_enabled": bool(shadow.get("repair_execution_enabled") or config.enable_gated_risk_cluster_repair_execution),
    }


def _evaluate_candidate_row(
    *,
    config: Config,
    compact_executor: AgentExecutor,
    compact_root: Path,
    candidate: dict[str, Any],
    strict_rows: dict[str, dict[str, Any]],
    examples: dict[str, EvalExample],
    shadow_gate: dict[str, Any],
) -> dict[str, Any]:
    query_id = str(candidate.get("query_id") or "")
    strict = strict_rows.get(query_id, {})
    example = examples.get(query_id)
    current_trajectory = _load_trajectory(strict.get("output_dir"))
    current_answer = str(current_trajectory.get("final_answer") or "")
    current_sql = first_generated_sql(current_trajectory)
    current_api = generated_api_calls(current_trajectory)
    base = _base_row(candidate, strict, current_trajectory, current_sql, current_api, current_answer)
    eligible, skip_reason = _eligibility(candidate, strict, example, config, shadow_gate)
    if not eligible or example is None:
        return {**base, "eligible": False, "skip_reason": skip_reason, "experiment_safe_to_enable": False}

    output_dir = compact_root / query_id / "compact_sql_first"
    _assert_allowed_output(config.outputs_dir, output_dir)
    if output_dir.exists():
        shutil.rmtree(output_dir)
    result = compact_executor.run(
        example.query,
        strategy="SQL_FIRST_API_VERIFY",
        query_id=query_id,
        output_dir=output_dir,
    )
    compact_trajectory = result["trajectory"]
    compact_sql = first_generated_sql(compact_trajectory)
    compact_api = generated_api_calls(compact_trajectory)
    compact_answer = str(result.get("final_answer") or compact_trajectory.get("final_answer") or "")
    compact_scores = _score_compact_result(compact_executor, compact_trajectory, compact_answer, example)
    current_score = float(strict.get("final_score") or 0.0)
    compact_score = float(compact_scores["final_score"])
    current_tokens = int(strict.get("estimated_tokens") or current_trajectory.get("estimated_tokens") or 0)
    compact_tokens = int(compact_scores["estimated_tokens"])
    current_runtime = float(strict.get("runtime") or current_trajectory.get("runtime") or 0.0)
    compact_runtime = float(compact_scores["runtime"])
    current_tool_calls = int(strict.get("tool_call_count") or current_trajectory.get("tool_call_count") or 0)
    compact_tool_calls = int(compact_scores["tool_call_count"])
    sql_changed = normalize_sql(current_sql) != normalize_sql(compact_sql)
    api_changed = _canonical_api(current_api) != _canonical_api(compact_api)
    final_answer_changed = current_answer != compact_answer
    runtime_delta = round(compact_runtime - current_runtime, 4)
    runtime_noise_acceptable = 0 < runtime_delta <= max(0.002, current_runtime * 0.20)
    token_accounting = _token_accounting(
        current_trajectory=current_trajectory,
        compact_trajectory=compact_trajectory,
        current_total_estimated_tokens=current_tokens,
        compact_total_estimated_tokens=compact_tokens,
        current_answer=current_answer,
        compact_answer=compact_answer,
        vote=candidate.get("schema_context_vote") or {},
    )
    row = {
        **base,
        "eligible": True,
        "skip_reason": "",
        "compact_score": round(compact_score, 4),
        "score_delta": round(compact_score - current_score, 4),
        "compact_tokens": compact_tokens,
        "token_delta": compact_tokens - current_tokens,
        **token_accounting,
        "compact_runtime": round(compact_runtime, 4),
        "runtime_delta": runtime_delta,
        "runtime_delta_explanation": "positive delta within local timing-noise bound" if runtime_noise_acceptable else "",
        "compact_tool_calls": compact_tool_calls,
        "tool_delta": compact_tool_calls - current_tool_calls,
        "compact_final_answer_preview": _preview(compact_answer),
        "final_answer_changed": final_answer_changed,
        "compact_sql": compact_sql,
        "sql_changed": sql_changed,
        "sql_semantically_equivalent": _sql_semantically_equivalent(compact_executor, current_sql, compact_sql),
        "compact_api": compact_api,
        "api_changed": api_changed,
        "api_semantically_equivalent": not api_changed,
        "live_api_evidence_available": _live_api_evidence_available(compact_trajectory),
        "dry_run_only": _dry_run_only(compact_trajectory),
        "no_live_api_evidence_fabricated": True,
        "compact_output_dir": str(output_dir),
    }
    row["experiment_safe_to_enable"] = _experiment_safe(row, runtime_noise_acceptable)
    return row


def _base_row(
    candidate: dict[str, Any],
    strict: dict[str, Any],
    trajectory: dict[str, Any],
    current_sql: str | None,
    current_api: list[dict[str, Any]],
    current_answer: str,
) -> dict[str, Any]:
    vote = candidate.get("schema_context_vote") or {}
    current_total_estimated_tokens = _int_or_none(strict.get("estimated_tokens") or trajectory.get("estimated_tokens"))
    current_context_tokens = _metadata_prompt_tokens(trajectory)
    answer_generation_tokens = _answer_generation_tokens(current_answer)
    row = {
        "query_id": candidate.get("query_id"),
        "query": candidate.get("query") or strict.get("query") or trajectory.get("original_query"),
        "eligible": False,
        "skip_reason": "",
        "current_score": strict.get("final_score"),
        "compact_score": None,
        "score_delta": None,
        "current_tokens": current_total_estimated_tokens,
        "compact_tokens": None,
        "token_delta": None,
        "current_total_estimated_tokens": current_total_estimated_tokens,
        "compact_total_estimated_tokens": None,
        "current_context_tokens": current_context_tokens,
        "compact_context_tokens": None,
        "fallback_context_tokens": vote.get("fallback_context_tokens"),
        "checkpoint_overhead_tokens": None,
        "checkpoint_overhead_in_total_tokens": False,
        "answer_generation_tokens": answer_generation_tokens,
        "token_delta_total": None,
        "token_delta_context_only": None,
        "token_delta_checkpoint_overhead": None,
        "token_measurement_classification": "context_metric_unavailable_or_unreliable",
        "token_measurement_note": "compact run was not executed, so compact context tokens are unavailable",
        "current_runtime": strict.get("runtime") or trajectory.get("runtime"),
        "compact_runtime": None,
        "runtime_delta": None,
        "current_tool_calls": strict.get("tool_call_count") or trajectory.get("tool_call_count"),
        "compact_tool_calls": None,
        "tool_delta": None,
        "current_final_answer_preview": _preview(current_answer),
        "compact_final_answer_preview": None,
        "final_answer_changed": None,
        "current_sql": current_sql,
        "compact_sql": None,
        "sql_changed": None,
        "current_api": current_api,
        "compact_api": None,
        "api_changed": None,
        "schema_vote_agreement": vote.get("schema_vote_agreement"),
        "compact_context_safe": vote.get("compact_context_safe"),
        "compact_tables": vote.get("compact_candidate_tables") or [],
        "compact_apis": vote.get("compact_candidate_apis") or [],
        "fallback_tables": vote.get("fallback_candidate_tables") or [],
        "fallback_apis": vote.get("fallback_candidate_apis") or [],
        "schema_vote_compact_context_tokens": vote.get("compact_context_tokens"),
        "expected_token_savings": vote.get("token_delta"),
        "risk_level": candidate.get("risk_level"),
        "experiment_safe_to_enable": False,
        "packaged_execution_changed": False,
        "diagnostic_only": True,
    }
    for field in REQUIRED_ROW_FIELDS:
        row.setdefault(field, None)
    return row


def _eligibility(
    candidate: dict[str, Any],
    strict: dict[str, Any],
    example: EvalExample | None,
    config: Config,
    shadow_gate: dict[str, Any],
) -> tuple[bool, str]:
    reasons: list[str] = []
    vote = candidate.get("schema_context_vote") or {}
    if not shadow_gate.get("ok"):
        reasons.append("shadow safety gate failed")
    if not strict:
        reasons.append("missing SQL_FIRST strict baseline row")
    if strict and strict.get("strategy") != "SQL_FIRST_API_VERIFY":
        reasons.append("strategy is not SQL_FIRST_API_VERIFY")
    if example is None:
        reasons.append("missing public eval example")
    if candidate.get("risk_level") != "high":
        reasons.append("risk_level is not high")
    if vote.get("schema_vote_agreement") is not True:
        reasons.append("schema_vote_agreement is not true")
    if vote.get("compact_context_safe") is not True:
        reasons.append("compact_context_safe is not true")
    if not _top_items_agree(vote.get("compact_candidate_tables") or [], vote.get("fallback_candidate_tables") or []):
        reasons.append("compact and fallback top tables do not agree")
    compact_apis = vote.get("compact_candidate_apis") or []
    fallback_apis = vote.get("fallback_candidate_apis") or []
    if compact_apis or fallback_apis:
        if not _top_items_agree(compact_apis, fallback_apis):
            reasons.append("compact and fallback top APIs do not agree")
    if config.enable_gated_risk_cluster_repair_execution:
        reasons.append("repair execution is enabled")
    if any(getattr(config, field) for field in CANARY_CONFIG_FIELDS):
        reasons.append("repair canary flag is enabled")
    return (not reasons, "; ".join(reasons))


def _score_compact_result(
    executor: AgentExecutor,
    trajectory: dict[str, Any],
    final_answer: str,
    example: EvalExample,
) -> dict[str, Any]:
    generated_sql = first_generated_sql(trajectory)
    generated_api = generated_api_calls(trajectory)
    sql_score, sql_reason = score_sql_strict(executor.db, generated_sql, example.gold_sql)
    api_score, api_reason = score_api_strict(generated_api, example.gold_api)
    answer_score, answer_reason = score_answer_strict(final_answer, example.gold_answer)
    correctness_score, unscored_dimension_count = aggregate_strict_correctness(
        {"sql": sql_score, "api": api_score, "answer": answer_score}
    )
    tool_calls = int(trajectory.get("tool_call_count", 0))
    runtime = float(trajectory.get("runtime", 0.0))
    estimated_tokens = int(trajectory.get("estimated_tokens", 0))
    efficiency_penalty = min(1.0, (tool_calls / 8) + (runtime / 30) + (estimated_tokens / 12000))
    return {
        "sql_score": round(sql_score, 4) if sql_score is not None else None,
        "api_score": round(api_score, 4) if api_score is not None else None,
        "answer_score": round(answer_score, 4) if answer_score is not None else None,
        "correctness_score": round(correctness_score, 4),
        "efficiency_penalty": round(efficiency_penalty, 4),
        "final_score": round(correctness_score - 0.1 * efficiency_penalty, 4),
        "tool_call_count": tool_calls,
        "runtime": round(runtime, 4),
        "estimated_tokens": estimated_tokens,
        "unscored_dimension_count": unscored_dimension_count,
        "sql_reason": sql_reason,
        "api_reason": api_reason,
        "answer_reason": answer_reason,
    }


def _token_accounting(
    *,
    current_trajectory: dict[str, Any],
    compact_trajectory: dict[str, Any],
    current_total_estimated_tokens: int,
    compact_total_estimated_tokens: int,
    current_answer: str,
    compact_answer: str,
    vote: dict[str, Any],
) -> dict[str, Any]:
    current_context_tokens = _metadata_prompt_tokens(current_trajectory)
    compact_context_tokens = _metadata_prompt_tokens(compact_trajectory)
    current_checkpoint_overhead = _compact_checkpoint_overhead_tokens(current_trajectory)
    compact_checkpoint_overhead = _compact_checkpoint_overhead_tokens(compact_trajectory)
    token_delta_total = compact_total_estimated_tokens - current_total_estimated_tokens
    token_delta_context_only = (
        compact_context_tokens - current_context_tokens
        if current_context_tokens is not None and compact_context_tokens is not None
        else None
    )
    token_delta_checkpoint_overhead = compact_checkpoint_overhead - current_checkpoint_overhead
    fields = {
        "current_total_estimated_tokens": current_total_estimated_tokens,
        "compact_total_estimated_tokens": compact_total_estimated_tokens,
        "current_context_tokens": current_context_tokens,
        "compact_context_tokens": compact_context_tokens,
        "fallback_context_tokens": vote.get("fallback_context_tokens"),
        "checkpoint_overhead_tokens": compact_checkpoint_overhead,
        "checkpoint_overhead_in_total_tokens": False,
        "answer_generation_tokens": {
            "current": _answer_generation_tokens(current_answer),
            "compact": _answer_generation_tokens(compact_answer),
        },
        "token_delta_total": token_delta_total,
        "token_delta_context_only": token_delta_context_only,
        "token_delta_checkpoint_overhead": token_delta_checkpoint_overhead,
        "schema_vote_compact_context_tokens": vote.get("compact_context_tokens"),
        "expected_token_savings": vote.get("token_delta"),
    }
    fields["token_measurement_classification"] = _classify_token_measurement(fields)
    fields["token_measurement_note"] = _token_measurement_note(fields)
    return fields


def _metadata_prompt_tokens(trajectory: dict[str, Any]) -> int | None:
    for step in trajectory.get("steps", []) or []:
        if step.get("kind") == "metadata":
            return _int_or_none(step.get("prompt_tokens"))
    return None


def _compact_checkpoint_overhead_tokens(trajectory: dict[str, Any]) -> int:
    for checkpoint in trajectory.get("checkpoints", []) or []:
        if checkpoint.get("checkpoint_id") == "checkpoint_compact_context_experiment":
            return estimate_tokens(checkpoint)
    return 0


def _answer_generation_tokens(answer: Any) -> int:
    return estimate_tokens(str(answer or ""))


def _classify_token_measurement(row: dict[str, Any]) -> str:
    current_context = row.get("current_context_tokens")
    compact_context = row.get("compact_context_tokens")
    if current_context is None or compact_context is None:
        return "context_metric_unavailable_or_unreliable"
    total_delta = row.get("token_delta_total")
    context_delta = row.get("token_delta_context_only")
    if total_delta is not None and context_delta is not None and float(total_delta) < 0 and float(context_delta) < 0:
        return "context_and_total_improved"
    if total_delta is not None and context_delta is not None and float(context_delta) < 0 <= float(total_delta):
        return "context_only_improved_total_not_improved"
    return "total_tokens_not_improved"


def _token_measurement_note(row: dict[str, Any]) -> str:
    classification = row.get("token_measurement_classification")
    if classification == "context_metric_unavailable_or_unreliable":
        return "metadata prompt_tokens were unavailable for current or compact trajectory, so context-only savings are not reliable"
    if classification == "context_only_improved_total_not_improved":
        return "measured metadata prompt/context tokens decreased, but official trajectory estimated_tokens did not decrease"
    if classification == "context_and_total_improved":
        return "measured metadata prompt/context tokens and official trajectory estimated_tokens both decreased"
    return "official trajectory estimated_tokens did not decrease; compact context is diagnostic-only for this row"


def _experiment_safe(row: dict[str, Any], runtime_noise_acceptable: bool) -> bool:
    if row.get("current_context_tokens") is None or row.get("compact_context_tokens") is None:
        return False
    return bool(
        row.get("eligible")
        and float(row.get("score_delta") or 0.0) >= 0
        and row.get("final_answer_changed") is False
        and (row.get("sql_changed") is False or row.get("sql_semantically_equivalent") is True)
        and (row.get("api_changed") is False or row.get("api_semantically_equivalent") is True)
        and int(row.get("tool_delta") or 0) <= 0
        and int(row.get("token_delta_total") or 0) < 0
        and (float(row.get("runtime_delta") or 0.0) <= 0 or runtime_noise_acceptable)
        and row.get("no_live_api_evidence_fabricated") is True
    )


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    eligible = [row for row in rows if row.get("eligible")]
    safe = [row for row in eligible if row.get("experiment_safe_to_enable")]
    unsafe = [row for row in eligible if not row.get("experiment_safe_to_enable")]
    answer_changed = sum(1 for row in eligible if row.get("final_answer_changed"))
    sql_changed = sum(1 for row in eligible if row.get("sql_changed"))
    api_changed = sum(1 for row in eligible if row.get("api_changed"))
    recommendation = "keep_default_off"
    if eligible and len(safe) == len(eligible):
        recommendation = "safe_for_future_canary"
    elif unsafe:
        recommendation = "unsafe_do_not_enable"
    return {
        "total_rows": len(rows),
        "eligible_rows": len(eligible),
        "skipped_rows": len(rows) - len(eligible),
        "safe_to_enable_rows": len(safe),
        "unsafe_rows": len(unsafe),
        "avg_score_delta": _avg(row.get("score_delta") for row in eligible),
        "avg_token_delta": _avg(row.get("token_delta") for row in eligible),
        "avg_token_delta_total": _avg(row.get("token_delta_total") for row in eligible),
        "avg_token_delta_context_only": _avg(row.get("token_delta_context_only") for row in eligible),
        "avg_token_delta_checkpoint_overhead": _avg(row.get("token_delta_checkpoint_overhead") for row in eligible),
        "token_measurement_classification_counts": _classification_counts(eligible),
        "avg_runtime_delta": _avg(row.get("runtime_delta") for row in eligible),
        "avg_tool_delta": _avg(row.get("tool_delta") for row in eligible),
        "answer_changed_count": answer_changed,
        "sql_changed_count": sql_changed,
        "api_changed_count": api_changed,
        "measured_efficiency_improvement_claimed": recommendation == "safe_for_future_canary",
        "official_measured_efficiency_improvement_claimed": False,
        "packaged_execution_changed": False,
        "behavior_changing_flags_enabled": False,
        "recommendation": recommendation,
        "experimental_only_note": "Measured efficiency improvement is experimental only, not packaged-submission improvement.",
    }


def _token_accounting_analysis(rows: list[dict[str, Any]]) -> dict[str, Any]:
    eligible = [row for row in rows if row.get("eligible")]
    classification_counts = _classification_counts(eligible)
    avg_total = _avg(row.get("token_delta_total") for row in eligible)
    avg_context = _avg(row.get("token_delta_context_only") for row in eligible)
    avg_checkpoint = _avg(row.get("token_delta_checkpoint_overhead") for row in eligible)
    current_compact_like = sum(
        1
        for row in eligible
        if row.get("current_context_tokens") is not None
        and row.get("fallback_context_tokens") is not None
        and int(row["current_context_tokens"]) <= int(row["fallback_context_tokens"])
    )
    measurement_caveat = (
        "Schema-vote fallback_context_tokens is a broader-context diagnostic estimate, not necessarily the official "
        "current prompt size. The official current path can already be compact-like, so replacing it with schema-vote "
        "compact metadata may not save prompt tokens. The official trajectory estimated_tokens metric is computed from "
        "query, compact step records, and final answer; it excludes checkpoints and the full filled prompt/context "
        "payload. Therefore large replay-estimated context savings can coexist with flat or positive measured total "
        "estimated_tokens."
    )
    mismatch_explanation = "total estimated tokens did not improve"
    if classification_counts.get("context_metric_unavailable_or_unreliable", 0):
        mismatch_explanation = "context proxy was missing or unreliable for at least one row"
    elif avg_context < 0 <= avg_total:
        mismatch_explanation = "average context proxy improved, but official total estimated tokens did not improve"
    elif classification_counts.get("context_only_improved_total_not_improved", 0):
        mismatch_explanation = "some rows had context-only savings, but average context proxy and total estimated tokens did not improve"
    elif avg_context >= 0 and avg_total >= 0:
        mismatch_explanation = "official current path already appears compact-like; measured context proxy and total estimated tokens did not improve"
    return {
        "eligible_rows": len(eligible),
        "avg_token_delta_total": avg_total,
        "avg_token_delta_context_only": avg_context,
        "avg_token_delta_checkpoint_overhead": avg_checkpoint,
        "classification_counts": classification_counts,
        "official_current_context_already_compact_like_rows": current_compact_like,
        "fallback_context_tokens_are_diagnostic_estimates": True,
        "estimated_tokens_source": "trajectory estimated_tokens = estimate_tokens({query, non-diagnostic steps, answer})",
        "checkpoint_overhead_in_total_tokens": False,
        "measurement_caveat": measurement_caveat,
        "metric_mismatch_explanation": mismatch_explanation,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload.get("summary", {})
    analysis = payload.get("token_accounting_analysis", {})
    lines = [
        "# Compact Context Measured Evaluation",
        "",
        "Measured efficiency improvement is experimental only, not packaged-submission improvement.",
        "",
        f"- Packaged execution changed: {payload.get('packaged_execution_changed')}",
        f"- Official measured efficiency improvement claimed: {payload.get('official_measured_efficiency_improvement_claimed')}",
        f"- Experiment measured efficiency improvement claimed: {summary.get('measured_efficiency_improvement_claimed')}",
        f"- No behavior-changing flags were enabled in this pass.",
        f"- Total rows: {summary.get('total_rows')}",
        f"- Eligible rows: {summary.get('eligible_rows')}",
        f"- Skipped rows: {summary.get('skipped_rows')}",
        f"- Safe-to-enable rows: {summary.get('safe_to_enable_rows')}",
        f"- Unsafe rows: {summary.get('unsafe_rows')}",
        f"- Avg score delta: {summary.get('avg_score_delta')}",
        f"- Avg token delta: {summary.get('avg_token_delta')}",
        f"- Avg total token delta: {summary.get('avg_token_delta_total')}",
        f"- Avg context-only token delta: {summary.get('avg_token_delta_context_only')}",
        f"- Avg checkpoint-overhead token delta: {summary.get('avg_token_delta_checkpoint_overhead')}",
        f"- Avg runtime delta: {summary.get('avg_runtime_delta')}",
        f"- Avg tool delta: {summary.get('avg_tool_delta')}",
        f"- Recommendation: `{summary.get('recommendation')}`",
        "",
        "## Token Accounting Analysis",
        "",
        f"- Avg total estimated-token delta: {analysis.get('avg_token_delta_total')}",
        f"- Avg context-only prompt-token delta: {analysis.get('avg_token_delta_context_only')}",
        f"- Avg compact checkpoint-overhead token delta: {analysis.get('avg_token_delta_checkpoint_overhead')}",
        f"- Classification counts: `{json.dumps(analysis.get('classification_counts', {}), sort_keys=True)}`",
        f"- Official current context already compact-like rows: {analysis.get('official_current_context_already_compact_like_rows')}",
        f"- Fallback context tokens are diagnostic estimates: {analysis.get('fallback_context_tokens_are_diagnostic_estimates')}",
        f"- Estimated token source: {analysis.get('estimated_tokens_source')}",
        f"- Checkpoint overhead included in total tokens: {analysis.get('checkpoint_overhead_in_total_tokens')}",
        f"- Metric mismatch explanation: {analysis.get('metric_mismatch_explanation')}",
        "",
        "## Measurement Caveat",
        "",
        str(payload.get("measurement_caveat") or analysis.get("measurement_caveat") or ""),
        "",
        "| Query ID | Eligible | Skip reason | Score delta | Total token delta | Context token delta | Runtime delta | Tool delta | Token classification | Safe? |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in payload.get("rows", []):
        lines.append(
            f"| `{row.get('query_id')}` | {row.get('eligible')} | {row.get('skip_reason') or ''} | "
            f"{row.get('score_delta')} | {row.get('token_delta_total')} | {row.get('token_delta_context_only')} | "
            f"{row.get('runtime_delta')} | {row.get('tool_delta')} | "
            f"{row.get('token_measurement_classification')} | {row.get('experiment_safe_to_enable')} |"
        )
    return "\n".join(lines) + "\n"


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
    path = Path(str(output_dir)) / "trajectory.json"
    if not path.exists():
        return {}
    return _load_json(path)


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _assert_allowed_output(outputs_dir: Path, path: Path) -> None:
    allowed_files = {
        (outputs_dir / "compact_context_measured_eval.json").resolve(),
        (outputs_dir / "compact_context_measured_eval.md").resolve(),
    }
    resolved = path.resolve()
    if resolved in allowed_files:
        return
    try:
        resolved.relative_to((outputs_dir / "compact_context_measured_eval").resolve())
        return
    except ValueError as exc:
        raise RuntimeError(f"Refusing to write compact-context measured artifact outside isolated paths: {path}") from exc


def _preview(text: Any, limit: int = 160) -> str:
    value = str(text or "").replace("\n", " ")
    return value[:limit] + ("..." if len(value) > limit else "")


def _avg(values: Any) -> float:
    numbers = [float(value) for value in values if value is not None]
    return round(sum(numbers) / len(numbers), 4) if numbers else 0.0


def _classification_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {
        "total_tokens_not_improved": 0,
        "context_only_improved_total_not_improved": 0,
        "context_and_total_improved": 0,
        "context_metric_unavailable_or_unreliable": 0,
    }
    for row in rows:
        key = str(row.get("token_measurement_classification") or "context_metric_unavailable_or_unreliable")
        counts[key] = counts.get(key, 0) + 1
    return counts


def _int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _top_items_agree(left: list[Any], right: list[Any]) -> bool:
    if not left or not right:
        return False
    left_norm = [str(item).strip().lower() for item in left[:3] if str(item).strip()]
    right_norm = [str(item).strip().lower() for item in right[:3] if str(item).strip()]
    return bool(left_norm and right_norm and set(left_norm) & set(right_norm))


def _canonical_api(calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "method": str(call.get("method") or "").upper(),
            "path": str(call.get("path") or ""),
            "params": call.get("params") or {},
        }
        for call in calls
    ]


def _sql_semantically_equivalent(executor: AgentExecutor, current_sql: str | None, compact_sql: str | None) -> bool:
    if normalize_sql(current_sql) == normalize_sql(compact_sql):
        return True
    if not current_sql or not compact_sql:
        return False
    current = executor.db.execute_sql(current_sql)
    compact = executor.db.execute_sql(compact_sql)
    return bool(current.get("ok") and compact.get("ok") and current.get("rows") == compact.get("rows"))


def _live_api_evidence_available(trajectory: dict[str, Any]) -> bool:
    for step in trajectory.get("steps", []):
        if step.get("kind") != "api_call":
            continue
        result = step.get("result") or {}
        if result.get("ok") and not result.get("dry_run"):
            return True
    return False


def _dry_run_only(trajectory: dict[str, Any]) -> bool:
    api_results = [
        step.get("result") or {}
        for step in trajectory.get("steps", [])
        if step.get("kind") == "api_call"
    ]
    return bool(api_results and all(result.get("dry_run") for result in api_results))


if __name__ == "__main__":
    raise SystemExit(main())
