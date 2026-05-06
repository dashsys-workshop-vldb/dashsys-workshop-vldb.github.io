#!/usr/bin/env python
from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from collections import defaultdict
from dataclasses import replace
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.candidate_context_builder import build_candidate_context
from dashagent.config import Config
from dashagent.endpoint_catalog import EndpointCatalog, normalize_api_path
from dashagent.endpoint_family_ranker import endpoint_family_for_endpoint
from dashagent.eval_harness import (
    EvalExample,
    EvalHarness,
    aggregate_strict_correctness,
    generated_api_calls,
    score_answer_strict,
    score_api_strict,
    score_sql_strict,
)
from dashagent.executor import AgentExecutor
from dashagent.query_normalizer import normalize_query
from dashagent.query_tokens import extract_query_tokens
from dashagent.repair_safety_verifier import verify_repair_safety


TARGET_CLUSTERS = [
    "zero_score_margin",
    "missing_gold_api_in_top_k",
    "batch_endpoint_confusion",
    "tag_api_confusion",
    "schema_vs_dataset_confusion",
    "broad_domain_api_confusion",
]

CLUSTER_FLAGS = {
    "batch_endpoint_confusion": "ENABLE_REPAIR_FOR_BATCH_ENDPOINT_CONFUSION",
    "tag_api_confusion": "ENABLE_REPAIR_FOR_TAG_API_CONFUSION",
    "schema_vs_dataset_confusion": "ENABLE_REPAIR_FOR_SCHEMA_DATASET_CONFUSION",
    "zero_score_margin": "ENABLE_REPAIR_FOR_ZERO_SCORE_MARGIN",
    "missing_gold_api_in_top_k": "ENABLE_REPAIR_FOR_MISSING_API_TOPK",
    "broad_domain_api_confusion": None,
}


def main() -> int:
    config = Config.from_env(ROOT)
    payload = run_shadow_repair_eval(config)
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    json_path = config.outputs_dir / "shadow_repair_eval.json"
    md_path = config.outputs_dir / "shadow_repair_eval.md"
    shadow_dir = config.outputs_dir / "shadow_repair_eval"
    shadow_dir.mkdir(parents=True, exist_ok=True)
    _assert_shadow_output_path(config.outputs_dir, json_path)
    _assert_shadow_output_path(config.outputs_dir, md_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    for row in payload.get("rows", []):
        query_dir = shadow_dir / str(row.get("query_id"))
        query_dir.mkdir(parents=True, exist_ok=True)
        row_path = query_dir / "shadow_decision.json"
        _assert_shadow_output_path(config.outputs_dir, row_path)
        row_path.write_text(json.dumps(row, indent=2, sort_keys=True, default=str), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "rows": len(payload.get("rows", []))}, indent=2, sort_keys=True))
    return 0


def run_shadow_repair_eval(config: Config) -> dict[str, Any]:
    if config.enable_gated_risk_cluster_repair_execution:
        raise RuntimeError("Shadow repair eval refuses to run with ENABLE_GATED_RISK_CLUSTER_REPAIR_EXECUTION=1.")
    executor_config = replace(config, outputs_dir=config.outputs_dir / "shadow_repair_eval" / "_internal")
    executor = AgentExecutor(executor_config)
    harness = EvalHarness(config, executor)
    examples = harness.load_examples()
    rows: list[dict[str, Any]] = []
    for example in examples:
        rows.append(_evaluate_example(config, executor, example))
    paired_summary = build_paired_summary(rows)
    cluster_recommendations = build_cluster_canary_recommendations(rows)
    return {
        "mode": "offline_shadow_repair_eval",
        "packaged_strategy_unchanged": True,
        "preferred_strategy": "SQL_FIRST_API_VERIFY",
        "repair_execution_enabled": config.enable_gated_risk_cluster_repair_execution,
        "canary_flags_default_zero": {
            flag: False
            for flag in CLUSTER_FLAGS.values()
            if flag
        },
        "artifact_isolation": {
            "allowed_outputs": [
                "outputs/shadow_repair_eval.json",
                "outputs/shadow_repair_eval.md",
                "outputs/shadow_repair_eval/",
            ],
            "writes_eval_outputs": False,
            "writes_final_submission": False,
            "writes_packaged_query_outputs": False,
        },
        "paired_shadow_eval_summary": paired_summary,
        "cluster_canary_recommendations": cluster_recommendations,
        "rows": rows,
        "notes": [
            "Gold labels are used only by the offline strict scorer, never to generate repaired plans.",
            "Shadow repaired plan scoring reuses existing deterministic answer text and verifier diagnostics; no LLM answer generation is introduced.",
            "Dry-run API calls are not counted as live API evidence.",
            "Execution repair remains disabled by default and this script does not alter packaged SQL_FIRST_API_VERIFY outputs.",
        ],
    }


def _evaluate_example(config: Config, executor: AgentExecutor, example: EvalExample) -> dict[str, Any]:
    start = time.perf_counter()
    current = _load_or_run_current(config, executor, example)
    trajectory = current["trajectory"]
    current_sql = _sql_from_trajectory(trajectory)
    current_api = generated_api_calls(trajectory)
    context = build_candidate_context(
        example.query,
        executor.schema_index,
        executor.endpoint_catalog,
        enable_hybrid_ranking=config.enable_hybrid_candidate_scoring,
        enable_endpoint_family_ranking=config.enable_endpoint_family_ranking,
        enable_structural_preservation=config.enable_structural_schema_preservation,
        enable_value_to_api_ranking=config.enable_value_to_api_ranking,
        enable_gated_risk_cluster_repair=config.enable_gated_risk_cluster_repair,
    )
    risk_cluster = infer_risk_cluster(example.query, context)
    current_plan = _plan_payload(
        sql=current_sql,
        api_calls=current_api,
        trajectory=trajectory,
        context=context,
        answer_shape=_answer_shape(trajectory),
    )
    repaired_api, repair_decision = _build_repaired_api_calls(example.query, current_api, context, executor.endpoint_catalog)
    repaired_plan = _plan_payload(
        sql=current_sql,
        api_calls=repaired_api,
        trajectory=trajectory,
        context=context,
        answer_shape=_answer_shape(trajectory),
    )
    repaired_plan.update(
        {
            "fusion_agreement": _fusion_agreement(context),
            "endpoint_family_confidence": (context.get("endpoint_family_ranking") or {}).get("endpoint_family_confidence", 0.0),
            "expected_answer_shape": current_plan.get("expected_answer_shape"),
            "answer_shape_more_specific": True,
            "live_api_evidence_available": False if repaired_api else current_plan.get("live_api_evidence_available"),
            "dry_run_only": bool(repaired_api and executor.api_client.dry_run),
        }
    )
    safety = verify_repair_safety(current_plan, repaired_plan, trajectory, executor.schema_index, executor.endpoint_catalog)
    current_scores = _score_plan(executor, trajectory, current_sql, current_api, example)
    repaired_scores = _score_plan(executor, trajectory, current_sql, repaired_api, example)
    elapsed = time.perf_counter() - start
    score_delta = round(float(repaired_scores["final_score"]) - float(current_scores["final_score"]), 4)
    tool_delta = int(repaired_scores["tool_call_count"]) - int(current_scores["tool_call_count"])
    token_delta = int(repaired_scores["estimated_tokens"]) - int(current_scores["estimated_tokens"])
    runtime_delta = round(float(repaired_scores["runtime"]) - float(current_scores["runtime"]), 4)
    safe_to_enable = bool(
        safety.get("safe")
        and score_delta >= 0
        and tool_delta <= 0
        and token_delta <= max(1, int(current_scores["estimated_tokens"] * 0.10))
        and runtime_delta <= max(0.001, float(current_scores["runtime"]) * 0.20)
    )
    decision = _decision_label(score_delta, safety, tool_delta, token_delta, runtime_delta, safe_to_enable)
    row = {
        "query_id": example.query_id,
        "query": example.query,
        "risk_cluster": risk_cluster,
        "current_plan_sql": current_sql,
        "current_plan_api": current_api,
        "repaired_plan_sql": current_sql,
        "repaired_plan_api": repaired_api,
        "repair_decision": repair_decision,
        "current_strict_score": current_scores["final_score"],
        "repaired_strict_score": repaired_scores["final_score"],
        "score_delta": score_delta,
        "current_tool_calls": current_scores["tool_call_count"],
        "repaired_tool_calls": repaired_scores["tool_call_count"],
        "tool_delta": tool_delta,
        "current_tokens": current_scores["estimated_tokens"],
        "repaired_tokens": repaired_scores["estimated_tokens"],
        "token_delta": token_delta,
        "current_runtime": current_scores["runtime"],
        "repaired_runtime": repaired_scores["runtime"],
        "runtime_delta": runtime_delta,
        "evidence_available": current_plan.get("evidence_available"),
        "live_api_evidence_available": repaired_plan.get("live_api_evidence_available"),
        "dry_run_only": repaired_plan.get("dry_run_only"),
        "repair_safe_to_enable": safe_to_enable,
        "safety_verdict": safety,
        "rejection_reason": "" if safe_to_enable else "; ".join(safety.get("reasons", []) or [decision]),
        "decision": decision,
        "shadow_runtime": round(elapsed, 4),
        "execution_changed": False,
        "why_execution_not_changed": "offline shadow evaluation only; packaged SQL_FIRST_API_VERIFY repair execution remains disabled",
    }
    row["decision_hash"] = decision_hash(row)
    return row


def _load_or_run_current(config: Config, executor: AgentExecutor, example: EvalExample) -> dict[str, Any]:
    trajectory_path = config.outputs_dir / "eval" / example.query_id / "sql_first_api_verify" / "trajectory.json"
    if trajectory_path.exists():
        trajectory = json.loads(trajectory_path.read_text(encoding="utf-8"))
        return {
            "trajectory": trajectory,
            "final_answer": trajectory.get("final_answer", ""),
            "output_dir": str(trajectory_path.parent),
        }
    shadow_current = config.outputs_dir / "shadow_repair_eval" / example.query_id / "current_sql_first_api_verify"
    return executor.run(example.query, strategy="SQL_FIRST_API_VERIFY", query_id=example.query_id, output_dir=shadow_current)


def _sql_from_trajectory(trajectory: dict[str, Any]) -> list[str]:
    return [
        str(step.get("sql") or "")
        for step in trajectory.get("steps", []) or []
        if step.get("kind") == "sql_call" and step.get("sql")
    ]


def _plan_payload(
    *,
    sql: list[str],
    api_calls: list[dict[str, Any]],
    trajectory: dict[str, Any],
    context: dict[str, Any],
    answer_shape: str | None,
) -> dict[str, Any]:
    dry_run = any(((step.get("result") or {}).get("dry_run") is True) for step in trajectory.get("steps", []) or [] if step.get("kind") == "api_call")
    sql_evidence = any(((step.get("result") or {}).get("row_count") or 0) > 0 for step in trajectory.get("steps", []) or [] if step.get("kind") == "sql_call")
    return {
        "sql": sql,
        "api_calls": api_calls,
        "tool_call_count": len(sql) + len(api_calls),
        "expected_answer_shape": answer_shape,
        "endpoint_family": (context.get("endpoint_family_ranking") or {}).get("endpoint_family"),
        "endpoint_family_confidence": (context.get("endpoint_family_ranking") or {}).get("endpoint_family_confidence", 0.0),
        "fusion_agreement": _fusion_agreement(context),
        "dry_run_only": dry_run,
        "live_api_evidence_available": False,
        "evidence_available": bool(sql_evidence),
    }


def _build_repaired_api_calls(
    query: str,
    current_api: list[dict[str, Any]],
    context: dict[str, Any],
    endpoint_catalog: EndpointCatalog,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    endpoint_ranking = context.get("endpoint_family_ranking") or {}
    top_ranked = endpoint_ranking.get("top_ranked_apis") or []
    if not top_ranked:
        return list(current_api), {"changed": False, "reason": "no ranked endpoint recommendation"}
    top_id = str(top_ranked[0].get("id") or "")
    endpoint = endpoint_catalog.by_id(top_id)
    if not endpoint:
        return list(current_api), {"changed": False, "reason": f"ranked endpoint {top_id} was not in catalog"}
    repaired = {
        "method": endpoint.method,
        "path": _materialize_endpoint_path(query, endpoint.path),
        "params": dict(endpoint.common_params),
        "endpoint_id": endpoint.id,
        "endpoint_family": endpoint_family_for_endpoint(endpoint),
    }
    if current_api:
        current_first = current_api[0]
        current_key = (str(current_first.get("method") or "").upper(), normalize_api_path(str(current_first.get("path") or "")))
        repaired_key = (repaired["method"], normalize_api_path(repaired["path"]))
        if current_key == repaired_key:
            return list(current_api), {"changed": False, "reason": "top ranked endpoint already matches current API"}
        updated = [repaired, *current_api[1:]]
        return updated, {"changed": True, "kind": "replace_first_api", "endpoint_id": endpoint.id, "reason": "candidate-derived endpoint family rerank"}
    return [repaired], {"changed": True, "kind": "diagnostic_add_api", "endpoint_id": endpoint.id, "reason": "no current API call; diagnostic only and unsafe if tool calls increase"}


def _materialize_endpoint_path(query: str, path: str) -> str:
    tokens = extract_query_tokens(query, normalize_query(query))
    replacements = {
        "batch_id": (tokens.batch_ids[0] if tokens.batch_ids else _first_regex(query, r"\b[0-9a-f]{24}\b")),
        "schema_id": (tokens.schema_ids[0] if tokens.schema_ids else None),
        "tag_id": None,
    }
    result = path
    for key, value in replacements.items():
        if value:
            result = result.replace("{" + key + "}", str(value))
    return result


def _score_plan(
    executor: AgentExecutor,
    trajectory: dict[str, Any],
    sql_values: list[str],
    api_calls: list[dict[str, Any]],
    example: EvalExample,
) -> dict[str, Any]:
    sql_score, sql_reason = score_sql_strict(executor.db, sql_values[0] if sql_values else None, example.gold_sql)
    api_score, api_reason = score_api_strict(api_calls, example.gold_api)
    answer_score, answer_reason = score_answer_strict(str(trajectory.get("final_answer") or ""), example.gold_answer)
    correctness, unscored = aggregate_strict_correctness({"sql": sql_score, "api": api_score, "answer": answer_score})
    tool_calls = len(sql_values) + len(api_calls)
    runtime = float(trajectory.get("runtime") or 0.0)
    estimated_tokens = int(trajectory.get("estimated_tokens") or 0)
    efficiency_penalty = min(1.0, (tool_calls / 8) + (runtime / 30) + (estimated_tokens / 12000))
    final_score = correctness - 0.1 * efficiency_penalty
    return {
        "sql_score": round(sql_score, 4) if sql_score is not None else None,
        "api_score": round(api_score, 4) if api_score is not None else None,
        "answer_score": round(answer_score, 4) if answer_score is not None else None,
        "correctness_score": round(correctness, 4),
        "efficiency_penalty": round(efficiency_penalty, 4),
        "final_score": round(final_score, 4),
        "tool_call_count": tool_calls,
        "runtime": round(runtime, 4),
        "estimated_tokens": estimated_tokens,
        "unscored_dimension_count": unscored,
        "sql_reason": sql_reason,
        "api_reason": api_reason,
        "answer_reason": answer_reason,
    }


def infer_risk_cluster(query: str, context: dict[str, Any]) -> str:
    gated = context.get("gated_risk_cluster_repair") or {}
    if gated.get("risk_cluster"):
        return str(gated["risk_cluster"])
    text = query.lower()
    missing_api_like = bool((context.get("endpoint_family_ranking") or {}).get("ranking_changed"))
    if (context.get("score_margin") or 0) == 0:
        return "zero_score_margin"
    if "batch" in text and ("file" in text or "download" in text):
        return "batch_endpoint_confusion"
    if "tag" in text or "category" in text:
        return "tag_api_confusion"
    if "schema" in text and ("dataset" in text or "datasets" in text):
        return "schema_vs_dataset_confusion"
    if missing_api_like:
        return "missing_gold_api_in_top_k"
    if any(word in text for word in ("sandbox", "platform", "current", "live", "status", "observability")):
        return "broad_domain_api_confusion"
    return "not_targeted"


def _fusion_agreement(context: dict[str, Any]) -> bool:
    hybrid = context.get("hybrid_candidate_scoring") or {}
    endpoint = context.get("endpoint_family_ranking") or {}
    weighted_top = (hybrid.get("top_components") or {}).get("name")
    rrf_scores = hybrid.get("reciprocal_rank_fusion_scores") or {}
    if rrf_scores:
        rrf_top = sorted(rrf_scores.items(), key=lambda item: (-float(item[1] or 0.0), item[0]))[0][0]
        table_agrees = not weighted_top or weighted_top == rrf_top
    else:
        table_agrees = True
    top_apis = endpoint.get("top_ranked_apis") or []
    if top_apis and endpoint.get("endpoint_family"):
        endpoint_agrees = top_apis[0].get("endpoint_family") == endpoint.get("endpoint_family")
    else:
        endpoint_agrees = True
    return bool(table_agrees and endpoint_agrees)


def _answer_shape(trajectory: dict[str, Any]) -> str | None:
    for step in trajectory.get("steps", []) or []:
        if step.get("kind") == "answer_diagnostics":
            return step.get("answer_family") or step.get("selected_candidate_type")
    return None


def _decision_label(
    score_delta: float,
    safety: dict[str, Any],
    tool_delta: int,
    token_delta: int,
    runtime_delta: float,
    safe_to_enable: bool,
) -> str:
    if safe_to_enable:
        if score_delta > 0:
            return "safe_shadow_improvement_recommend_canary"
        return "safe_shadow_tie_recommend_canary"
    if not safety.get("safe"):
        return "reject_unsafe_repair"
    if tool_delta > 0:
        return "reject_tool_call_increase"
    if token_delta > 0 or runtime_delta > 0:
        return "reject_efficiency_regression"
    if score_delta < 0:
        return "reject_score_regression"
    return "diagnostic_only_no_enablement"


def decision_hash(row: dict[str, Any]) -> str:
    material = {
        "query_id": row.get("query_id"),
        "current_plan": {"sql": row.get("current_plan_sql"), "api": row.get("current_plan_api")},
        "repaired_plan": {"sql": row.get("repaired_plan_sql"), "api": row.get("repaired_plan_api")},
        "safety_verdict": bool((row.get("safety_verdict") or {}).get("safe")),
        "selected_cluster": row.get("risk_cluster"),
    }
    return hashlib.sha256(json.dumps(material, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()[:16]


def build_paired_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    better = [row for row in rows if float(row.get("score_delta") or 0.0) > 0]
    equal = [row for row in rows if float(row.get("score_delta") or 0.0) == 0]
    worse = [row for row in rows if float(row.get("score_delta") or 0.0) < 0]
    unsafe = [row for row in rows if not row.get("repair_safe_to_enable")]
    return {
        "repaired_better_count": len(better),
        "repaired_equal_count": len(equal),
        "repaired_worse_count": len(worse),
        "unsafe_repair_count": len(unsafe),
        "avg_score_delta": _avg(row.get("score_delta") for row in rows),
        "avg_tool_delta": _avg(row.get("tool_delta") for row in rows),
        "avg_runtime_delta": _avg(row.get("runtime_delta") for row in rows),
        "avg_token_delta": _avg(row.get("token_delta") for row in rows),
        "decision_hashes": [row.get("decision_hash") for row in rows],
    }


def build_cluster_canary_recommendations(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        cluster = str(row.get("risk_cluster") or "unknown")
        if cluster in TARGET_CLUSTERS:
            grouped[cluster].append(row)
    recommendations: dict[str, Any] = {}
    for cluster in TARGET_CLUSTERS:
        cluster_rows = grouped.get(cluster, [])
        better = [row for row in cluster_rows if float(row.get("score_delta") or 0.0) > 0]
        equal = [row for row in cluster_rows if float(row.get("score_delta") or 0.0) == 0]
        worse = [row for row in cluster_rows if float(row.get("score_delta") or 0.0) < 0]
        avg_score = _avg(row.get("score_delta") for row in cluster_rows)
        avg_tool = _avg(row.get("tool_delta") for row in cluster_rows)
        avg_token = _avg(row.get("token_delta") for row in cluster_rows)
        avg_runtime = _avg(row.get("runtime_delta") for row in cluster_rows)
        all_safe = bool(cluster_rows) and all(row.get("repair_safe_to_enable") for row in cluster_rows)
        recommended_flag = CLUSTER_FLAGS.get(cluster)
        gates_pass = bool(recommended_flag) and len(worse) == 0 and avg_score >= 0 and avg_tool <= 0 and avg_token <= 0 and avg_runtime <= 0 and all_safe
        recommendations[cluster] = {
            "shadow_eval_rows": len(cluster_rows),
            "repaired_better_count": len(better),
            "repaired_equal_count": len(equal),
            "repaired_worse_count": len(worse),
            "avg_score_delta": avg_score,
            "avg_tool_call_delta": avg_tool,
            "avg_token_delta": avg_token,
            "avg_runtime_delta": avg_runtime,
            "safe_to_enable_canary": gates_pass,
            "recommended_flag": recommended_flag,
            "recommendation": "recommend_canary_enablement" if gates_pass else "keep_disabled",
            "rejection_reason": "" if gates_pass else _cluster_rejection_reason(cluster, cluster_rows, worse, avg_score, avg_tool, avg_token, avg_runtime, all_safe),
        }
    return recommendations


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload.get("paired_shadow_eval_summary", {})
    lines = [
        "# DASHSys Offline Shadow Repair Evaluation",
        "",
        "Shadow repair execution is **disabled by default**. This report compares current SQL_FIRST_API_VERIFY plans with candidate-derived repaired plans without changing packaged outputs.",
        "",
        "## Paired Shadow Eval Summary",
        "",
        f"- repaired_better_count: {summary.get('repaired_better_count')}",
        f"- repaired_equal_count: {summary.get('repaired_equal_count')}",
        f"- repaired_worse_count: {summary.get('repaired_worse_count')}",
        f"- unsafe_repair_count: {summary.get('unsafe_repair_count')}",
        f"- avg_score_delta: {summary.get('avg_score_delta')}",
        f"- avg_tool_delta: {summary.get('avg_tool_delta')}",
        f"- avg_runtime_delta: {summary.get('avg_runtime_delta')}",
        "",
        "| Query ID | Cluster | Current score | Repaired score | Delta | Safe? | Decision |",
        "| --- | --- | ---: | ---: | ---: | --- | --- |",
    ]
    for row in payload.get("rows", []):
        lines.append(
            f"| `{row.get('query_id')}` | `{row.get('risk_cluster')}` | {row.get('current_strict_score')} | "
            f"{row.get('repaired_strict_score')} | {row.get('score_delta')} | {row.get('repair_safe_to_enable')} | {row.get('decision')} |"
        )
    lines.extend(
        [
            "",
            "## Cluster Canary Recommendation",
            "",
            "| Cluster | Rows | Better | Equal | Worse | Avg score delta | Avg tool delta | Avg token delta | Avg runtime delta | Safe to enable? | Recommended flag | Decision |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |",
        ]
    )
    for cluster, row in payload.get("cluster_canary_recommendations", {}).items():
        lines.append(
            f"| `{cluster}` | {row.get('shadow_eval_rows')} | {row.get('repaired_better_count')} | {row.get('repaired_equal_count')} | "
            f"{row.get('repaired_worse_count')} | {row.get('avg_score_delta')} | {row.get('avg_tool_call_delta')} | "
            f"{row.get('avg_token_delta')} | {row.get('avg_runtime_delta')} | {row.get('safe_to_enable_canary')} | "
            f"`{row.get('recommended_flag')}` | {row.get('recommendation')} |"
        )
    lines.extend(
        [
            "",
            "## Safety Notes",
            "",
            f"- Packaged strategy unchanged: {payload.get('packaged_strategy_unchanged')}",
            f"- Repair execution enabled: {payload.get('repair_execution_enabled')}",
            "- No live API evidence is fabricated; dry-run API remains dry-run.",
            "- Canary flags are recommendations only and remain off by default.",
            "",
        ]
    )
    return "\n".join(lines)


def _cluster_rejection_reason(
    cluster: str,
    rows: list[dict[str, Any]],
    worse: list[dict[str, Any]],
    avg_score: float,
    avg_tool: float,
    avg_token: float,
    avg_runtime: float,
    all_safe: bool,
) -> str:
    if not rows:
        return "No shadow rows for this cluster."
    if not CLUSTER_FLAGS.get(cluster):
        return "No canary flag is defined for this broad diagnostic cluster."
    if worse:
        return "At least one repaired row scored worse."
    if avg_score < 0:
        return "Average score delta is negative."
    if avg_tool > 0:
        return "Average tool-call delta is positive."
    if avg_token > 0:
        return "Average token delta is positive."
    if avg_runtime > 0:
        return "Average runtime delta is positive."
    if not all_safe:
        return "One or more rows failed the repair safety verifier."
    return "Cluster canary gates did not pass."


def _avg(values: Any) -> float:
    numbers = [float(value or 0.0) for value in values]
    return round(sum(numbers) / len(numbers), 4) if numbers else 0.0


def _first_regex(text: str, pattern: str) -> str | None:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return match.group(0) if match else None


def _assert_shadow_output_path(outputs_dir: Path, path: Path) -> None:
    resolved = path.resolve()
    allowed_files = {
        (outputs_dir / "shadow_repair_eval.json").resolve(),
        (outputs_dir / "shadow_repair_eval.md").resolve(),
    }
    allowed_dir = (outputs_dir / "shadow_repair_eval").resolve()
    if resolved in allowed_files:
        return
    if allowed_dir in resolved.parents or resolved == allowed_dir:
        return
    raise RuntimeError(f"Refusing to write shadow repair artifact outside isolated paths: {path}")


if __name__ == "__main__":
    raise SystemExit(main())
