#!/usr/bin/env python
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.eval_harness import (  # noqa: E402
    EvalHarness,
    aggregate_strict_correctness,
    count_validation_failures,
    first_generated_sql,
    generated_api_calls,
    score_answer_strict,
    score_api_strict,
    score_sql_strict,
)
from dashagent.llm_tool_agent import (  # noqa: E402
    GUIDED_REAL_LLM_TWO_TOOLS_BASELINE,
    LLM_CONTROLLER_OPTIMIZED_AGENT,
    RAW_REAL_LLM_TWO_TOOLS_BASELINE,
    REAL_LLM_TWO_TOOLS_BASELINE,
)
from dashagent.trajectory import estimate_tokens, redact_secrets  # noqa: E402
from scripts.load_local_env import load_local_env  # noqa: E402


STRICT_STRATEGIES = [
    RAW_REAL_LLM_TWO_TOOLS_BASELINE,
    GUIDED_REAL_LLM_TWO_TOOLS_BASELINE,
    LLM_CONTROLLER_OPTIMIZED_AGENT,
    REAL_LLM_TWO_TOOLS_BASELINE,
]


def main() -> int:
    config = Config.from_env(ROOT)
    load_local_env(config.project_root)
    payload = run_llm_strict_baseline_eval(config)
    write_report(config, payload)
    refresh_llm_baseline_report(config)
    print(
        json.dumps(
            {
                "json": str(config.outputs_dir / "llm_strict_baseline_eval.json"),
                "markdown": str(config.outputs_dir / "llm_strict_baseline_eval.md"),
                "strict_scoring_status": payload.get("summary", {}).get("strict_scoring_status"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def refresh_llm_baseline_report(config: Config) -> None:
    baseline_path = config.outputs_dir / "llm_baseline_eval.json"
    if not baseline_path.exists():
        return
    try:
        from scripts.run_llm_baseline_eval import write_llm_baseline_report

        payload = json.loads(baseline_path.read_text(encoding="utf-8"))
        write_llm_baseline_report(config, payload)
    except Exception:
        return


def run_llm_strict_baseline_eval(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    baseline = _load_json(config.outputs_dir / "llm_baseline_eval.json")
    smoke = _load_json(config.outputs_dir / "llm_sdk_backend_check.json") or _load_json(config.outputs_dir / "openai_compatible_llm_check.json")
    if not baseline or baseline.get("skipped"):
        reason = baseline.get("reason") if baseline else "outputs/llm_baseline_eval.json is missing"
        payload = _unavailable_payload(config, reason, smoke=smoke)
        return redact_secrets(payload)

    harness = EvalHarness(config)
    examples = {example.query_id: example for example in harness.load_examples()}
    deterministic_rows = _deterministic_rows(config)
    rows: list[dict[str, Any]] = []
    for source_row in baseline.get("rows", []):
        system = source_row.get("system")
        row_systems = [system]
        if system == RAW_REAL_LLM_TWO_TOOLS_BASELINE:
            row_systems.append(REAL_LLM_TWO_TOOLS_BASELINE)
        for effective_system in row_systems:
            example = examples.get(str(source_row.get("query_id")))
            if example is None:
                rows.append(_failed_row(source_row, effective_system, "strict_scoring_unavailable", "Example missing from dev data."))
                continue
            scored = score_baseline_row(config, harness, example, source_row, effective_system, deterministic_rows)
            rows.append(scored)
            write_isolated_artifacts(config, scored)

    per_strategy = [_summarize_strategy(rows, strategy) for strategy in STRICT_STRATEGIES]
    best_delta = _best_delta(per_strategy)
    backend_name = smoke.get("backend_name") or os.getenv("OPENAI_MODEL") or os.getenv("ANTHROPIC_MODEL", "") or "unavailable"
    base_url = smoke.get("base_url") or os.getenv("OPENAI_BASE_URL") or os.getenv("ANTHROPIC_BASE_URL", "")
    payload = {
        "framework": "generic_sdk_llm_baseline",
        "provider_type": smoke.get("provider_type", "openai_compatible"),
        "backend_type": smoke.get("backend_type", "openai_sdk"),
        "sdk_client": "SDK-based LLM client",
        "base_url": base_url,
        "model": backend_name,
        "backend_name": backend_name,
        "source_baseline_eval_path": str(config.outputs_dir / "llm_baseline_eval.json"),
        "isolated_output_root": str(config.outputs_dir / "llm_strict_eval"),
        "smoke_test_passed": smoke.get("ok", "unavailable"),
        "tool_calling_supported": smoke.get("tool_calling_supported", "unavailable"),
        "summary": {
            "strict_scoring_status": "available" if any(row.get("strict_scoring_status") == "available" for row in rows) else "unavailable",
            "rows_attempted": len(rows),
            "valid_rows": sum(1 for row in rows if row.get("strict_scoring_status") == "available"),
            "failed_rows": sum(1 for row in rows if row.get("strict_scoring_status") != "available"),
            "best_delta_vs_deterministic": best_delta,
            "safety_flags": [],
            "all_gates_clean": False,
            "recommendation": _recommendation(best_delta, rows),
        },
        "per_strategy": per_strategy,
        "rows": rows,
        "failure_categories": _aggregate_categories(rows),
        "comparison_against_deterministic": _comparison_text(per_strategy),
        "promotion_status": "shadow_only",
        "notes": [
            "The LLM baseline framework is generic; the configured model/provider is backend metadata.",
            "Strict scoring uses existing scorer helpers and does not modify packaged SQL_FIRST_API_VERIFY outputs.",
            "LLM baseline results remain comparison/shadow-only.",
        ],
    }
    return _safe_report_payload(payload)


def score_baseline_row(
    config: Config,
    harness: EvalHarness,
    example: Any,
    source_row: dict[str, Any],
    effective_system: str,
    deterministic_rows: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    trajectory = canonical_trajectory_from_row(source_row, effective_system)
    generated_sql = first_generated_sql(trajectory)
    generated_api = generated_api_calls(trajectory)
    failure_categories = Counter(_failure_categories_for_row(source_row, trajectory, example, generated_sql, generated_api))
    strict_status = "available"
    unavailable_reason = ""
    try:
        sql_score, sql_reason = score_sql_strict(harness.executor.db, generated_sql, example.gold_sql)
        api_score, api_reason = score_api_strict(generated_api, example.gold_api)
        answer_score, answer_reason = score_answer_strict(str(source_row.get("final_answer") or ""), example.gold_answer)
        correctness_score, unscored_dimension_count = aggregate_strict_correctness(
            {"sql": sql_score, "api": api_score, "answer": answer_score}
        )
        efficiency_penalty = min(
            1.0,
            (float(trajectory.get("tool_call_count") or 0) / 8)
            + (float(trajectory.get("runtime") or source_row.get("runtime") or 0) / 30)
            + (float(_token_value(source_row, trajectory) or 0) / 12000),
        )
        final_score = correctness_score - 0.1 * efficiency_penalty
    except Exception as exc:
        strict_status = "unavailable"
        unavailable_reason = f"strict_scoring_unavailable: {type(exc).__name__}"
        failure_categories["strict_scoring_unavailable"] += 1
        sql_score = api_score = answer_score = None
        sql_reason = api_reason = answer_reason = unavailable_reason
        correctness_score = 0.0
        unscored_dimension_count = 3
        efficiency_penalty = 0.0
        final_score = None

    deterministic = deterministic_rows.get(example.query_id, {})
    row = {
        "query_id": example.query_id,
        "query": example.query,
        "system": effective_system,
        "alias_of": RAW_REAL_LLM_TWO_TOOLS_BASELINE if effective_system == REAL_LLM_TWO_TOOLS_BASELINE else None,
        "strict_scoring_status": strict_status,
        "strict_scoring_unavailable_reason": unavailable_reason or None,
        "strict_final_score": round(final_score, 4) if isinstance(final_score, (int, float)) else None,
        "strict_correctness": round(correctness_score, 4),
        "answer_score": round(answer_score, 4) if isinstance(answer_score, (int, float)) else None,
        "sql_score": round(sql_score, 4) if isinstance(sql_score, (int, float)) else None,
        "api_score": round(api_score, 4) if isinstance(api_score, (int, float)) else None,
        "estimated_tokens": _token_value(source_row, trajectory),
        "llm_total_tokens": source_row.get("llm_total_tokens", trajectory.get("llm_total_tokens")),
        "token_source": _token_source(source_row, trajectory),
        "runtime": round(float(source_row.get("runtime") or trajectory.get("runtime") or 0.0), 4),
        "tool_calls": int(source_row.get("tool_call_count") or trajectory.get("tool_call_count") or 0),
        "validation_failures": count_validation_failures(trajectory),
        "dry_run_live_evidence_status": _dry_run_status(source_row, trajectory),
        "failure_categories": dict(failure_categories),
        "sql_reason": sql_reason,
        "api_reason": api_reason,
        "answer_reason": answer_reason,
        "unscored_dimension_count": unscored_dimension_count,
        "delta_vs_sql_first_api_verify": _delta_fields(
            {
                "final_score": final_score,
                "correctness_score": correctness_score,
                "answer_score": answer_score,
                "sql_score": sql_score,
                "api_score": api_score,
                "estimated_tokens": _token_value(source_row, trajectory),
                "runtime": source_row.get("runtime") or trajectory.get("runtime"),
                "tool_call_count": source_row.get("tool_call_count") or trajectory.get("tool_call_count"),
            },
            deterministic,
        ),
        "output_dir": str(_strategy_dir(config, example.query_id, effective_system)),
        "trajectory": trajectory,
    }
    return redact_secrets(row)


def canonical_trajectory_from_row(row: dict[str, Any], system: str | None = None) -> dict[str, Any]:
    trajectory = dict(row.get("trajectory") or {})
    standard_steps = _standard_steps_from_tool_calls(row)
    existing_steps = trajectory.get("steps") if isinstance(trajectory.get("steps"), list) else []
    if standard_steps:
        trajectory["llm_transcript_steps"] = existing_steps
        trajectory["steps"] = standard_steps
    trajectory.setdefault("original_query", row.get("query"))
    trajectory["strategy"] = system or row.get("system")
    trajectory["final_answer"] = row.get("final_answer", trajectory.get("final_answer", ""))
    trajectory["tool_call_count"] = row.get("tool_call_count", trajectory.get("tool_call_count", len(standard_steps)))
    trajectory["runtime"] = row.get("runtime", trajectory.get("runtime", 0.0))
    trajectory["estimated_tokens"] = _token_value(row, trajectory)
    trajectory["llm_total_tokens"] = row.get("llm_total_tokens", trajectory.get("llm_total_tokens"))
    trajectory["token_source"] = _token_source(row, trajectory)
    return trajectory


def _standard_steps_from_tool_calls(row: dict[str, Any]) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    for index, call in enumerate(row.get("llm_tool_calls") or []):
        tool = call.get("tool") or call.get("tool_name")
        args = call.get("arguments") if isinstance(call.get("arguments"), dict) else {}
        validation = call.get("validation") if isinstance(call.get("validation"), dict) else {}
        preview = call.get("result_preview") if isinstance(call.get("result_preview"), dict) else {}
        if tool == "execute_sql":
            steps.append(
                {
                    "kind": "sql_call",
                    "index": index,
                    "sql": args.get("sql"),
                    "validation": validation,
                    "result": preview,
                }
            )
        elif tool == "call_api":
            steps.append(
                {
                    "kind": "api_call",
                    "index": index,
                    "method": args.get("method", "GET"),
                    "url": args.get("url", ""),
                    "params": args.get("params", {}),
                    "headers": {},
                    "validation": validation,
                    "result": preview,
                }
            )
    return steps


def write_isolated_artifacts(config: Config, row: dict[str, Any]) -> None:
    out_dir = _strategy_dir(config, str(row.get("query_id")), str(row.get("system")))
    out_dir.mkdir(parents=True, exist_ok=True)
    trajectory = row.get("trajectory") or {}
    (out_dir / "trajectory.json").write_text(json.dumps(redact_secrets(trajectory), indent=2, sort_keys=True, default=str), encoding="utf-8")
    (out_dir / "metadata.json").write_text(
        json.dumps(
            redact_secrets(
                {
                    "query_id": row.get("query_id"),
                    "strategy": row.get("system"),
                    "framework": "generic_sdk_llm_baseline",
                    "provider_type": os.getenv("LLM_PROVIDER", "openai_compatible"),
                    "backend_name": os.getenv("OPENAI_MODEL", "") or "unavailable",
                    "strict_scoring_status": row.get("strict_scoring_status"),
                }
            ),
            indent=2,
            sort_keys=True,
            default=str,
        ),
        encoding="utf-8",
    )
    (out_dir / "filled_system_prompt.txt").write_text(
        "Generic SDK LLM baseline strict-scoring artifact. Packaged SQL_FIRST_API_VERIFY behavior is unchanged.\n",
        encoding="utf-8",
    )


def write_report(config: Config, payload: dict[str, Any]) -> None:
    json_path = config.outputs_dir / "llm_strict_baseline_eval.json"
    md_path = config.outputs_dir / "llm_strict_baseline_eval.md"
    json_path.write_text(json.dumps(_safe_report_payload(payload), indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# SDK LLM Strict Baseline Evaluation",
        "",
        f"- Framework: `{payload.get('framework')}`",
        f"- Provider type: `{payload.get('provider_type')}`",
        f"- Backend type: `{payload.get('backend_type')}`",
        f"- Current LLM backend: `{payload.get('backend_name')}`",
        f"- Smoke test passed: `{payload.get('smoke_test_passed')}`",
        f"- Tool calling supported: `{payload.get('tool_calling_supported')}`",
        f"- Strict scoring status: `{payload.get('summary', {}).get('strict_scoring_status')}`",
        f"- Recommendation: `{payload.get('summary', {}).get('recommendation')}`",
        "",
        "The LLM baseline framework is generic; the configured model/provider is backend metadata.",
        "",
        "## Strategy Summary",
        "",
        "| Strategy | Rows | Valid | Failed | Strict score | Correctness | Answer | SQL | API | Tokens | Token source | Runtime | Tools | Avg delta |",
        "| --- | ---: | ---: | ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload.get("per_strategy", []):
        lines.append(
            f"| `{row.get('system')}` | {row.get('rows_attempted')} | {row.get('valid_rows')} | {row.get('failed_rows')} | "
            f"{_fmt(row.get('strict_final_score'))} | {_fmt(row.get('strict_correctness'))} | {_fmt(row.get('answer_score'))} | "
            f"{_fmt(row.get('sql_score'))} | {_fmt(row.get('api_score'))} | {_fmt(row.get('estimated_tokens'))} | "
            f"{row.get('token_source_counts')} | {_fmt(row.get('runtime'))} | {_fmt(row.get('tool_calls'))} | "
            f"{row.get('avg_delta_vs_deterministic', {}).get('final_score', 'unavailable')} |"
        )
    lines.extend(
        [
            "",
            "## Recommendation",
            "",
            "- Keep the SDK LLM baseline shadow-only unless a future explicit promotion runs strict, safety, hidden-style, package, and no-secret gates.",
            "- Deterministic `SQL_FIRST_API_VERIFY` remains the packaged strategy.",
            "",
        ]
    )
    return "\n".join(lines)


def _unavailable_payload(config: Config, reason: str, *, smoke: dict[str, Any]) -> dict[str, Any]:
    backend_name = smoke.get("backend_name") or os.getenv("OPENAI_MODEL") or os.getenv("ANTHROPIC_MODEL", "") or "unavailable"
    payload = {
        "framework": "generic_sdk_llm_baseline",
        "provider_type": smoke.get("provider_type", "openai_compatible"),
        "backend_type": smoke.get("backend_type", "openai_sdk"),
        "sdk_client": "SDK-based LLM client",
        "base_url": smoke.get("base_url") or os.getenv("OPENAI_BASE_URL") or os.getenv("ANTHROPIC_BASE_URL", ""),
        "model": backend_name,
        "backend_name": backend_name,
        "source_baseline_eval_path": str(config.outputs_dir / "llm_baseline_eval.json"),
        "isolated_output_root": str(config.outputs_dir / "llm_strict_eval"),
        "smoke_test_passed": smoke.get("ok", "unavailable"),
        "tool_calling_supported": smoke.get("tool_calling_supported", "unavailable"),
        "summary": {
            "strict_scoring_status": "unavailable",
            "strict_scoring_unavailable_reason": reason,
            "rows_attempted": 0,
            "valid_rows": 0,
            "failed_rows": 0,
            "best_delta_vs_deterministic": "unavailable",
            "all_gates_clean": False,
            "recommendation": "keep_shadow_only",
        },
        "per_strategy": [],
        "rows": [],
        "failure_categories": {"strict_scoring_unavailable": 1},
        "comparison_against_deterministic": "llm_strict_score_unavailable; deterministic SQL_FIRST_API_VERIFY remains preferred",
        "promotion_status": "shadow_only",
    }
    return _safe_report_payload(payload)


def _safe_report_payload(payload: dict[str, Any]) -> dict[str, Any]:
    safe = redact_secrets(payload)
    for key in ["framework", "provider_type", "backend_type", "sdk_client", "base_url", "model", "backend_name", "promotion_status"]:
        if key in payload:
            safe[key] = payload.get(key)
    return safe


def _strategy_dir(config: Config, query_id: str, strategy: str) -> Path:
    safe_strategy = re.sub(r"[^A-Za-z0-9_.-]+", "_", strategy).lower()
    return config.outputs_dir / "llm_strict_eval" / query_id / safe_strategy


def _failed_row(source_row: dict[str, Any], system: str, category: str, reason: str) -> dict[str, Any]:
    return {
        "query_id": source_row.get("query_id"),
        "query": source_row.get("query"),
        "system": system,
        "strict_scoring_status": "unavailable",
        "strict_scoring_unavailable_reason": reason,
        "strict_final_score": None,
        "strict_correctness": 0.0,
        "answer_score": None,
        "sql_score": None,
        "api_score": None,
        "estimated_tokens": source_row.get("estimated_tokens"),
        "runtime": source_row.get("runtime"),
        "tool_calls": source_row.get("tool_call_count"),
        "failure_categories": {category: 1},
    }


def _token_value(row: dict[str, Any], trajectory: dict[str, Any]) -> int | None:
    for key in ("llm_total_tokens", "estimated_tokens", "prompt_context_tokens"):
        value = row.get(key)
        if isinstance(value, (int, float)) and (value != 0 or row.get("token_source") == "measured_usage"):
            return int(value)
    value = trajectory.get("estimated_tokens")
    if isinstance(value, (int, float)):
        return int(value)
    try:
        return estimate_tokens({"query": row.get("query"), "answer": row.get("final_answer"), "tool_calls": row.get("llm_tool_calls")})
    except Exception:
        return None


def _token_source(row: dict[str, Any], trajectory: dict[str, Any]) -> str:
    source = row.get("token_source") or trajectory.get("token_source")
    if source in {"measured_usage", "estimated", "unavailable"}:
        return str(source)
    return "estimated" if _token_value(row, trajectory) is not None else "unavailable"


def _dry_run_status(row: dict[str, Any], trajectory: dict[str, Any]) -> str:
    dry_run_count = row.get("dry_run_only_api_count", trajectory.get("dry_run_only_api_count", 0))
    try:
        if int(dry_run_count) > 0:
            return "dry_run_api_evidence_present"
    except Exception:
        pass
    return "live_or_sql_only"


def _failure_categories_for_row(
    row: dict[str, Any],
    trajectory: dict[str, Any],
    example: Any,
    generated_sql: str | None,
    generated_api: list[dict[str, Any]],
) -> list[str]:
    categories: list[str] = []
    if row.get("skipped_or_failed") or not row.get("valid_agent_run", True):
        reason = str(row.get("failure_reason") or "provider_error")
        categories.append(_normalize_failure(reason))
    if int(row.get("invalid_tool_call_count") or trajectory.get("invalid_tool_call_count") or 0) > 0:
        categories.append("invalid_tool_call")
        categories.append("validation_failed")
    if "max_turn" in str(row.get("failure_reason", "")).lower():
        categories.append("tool_loop_exceeded")
    if example.gold_sql and not generated_sql:
        categories.append("missing_sql")
    if example.gold_api and not generated_api:
        categories.append("missing_api")
    for step in trajectory.get("steps", []):
        if step.get("kind") == "sql_call" and step.get("validation", {}).get("ok") is False:
            categories.append("malformed_sql")
        if step.get("validation", {}).get("ok") is False:
            categories.append("validation_failed")
    if row.get("answer_score") is not None:
        try:
            if float(row.get("answer_score")) < 0.2:
                categories.append("answer_unsupported")
        except Exception:
            pass
    return categories


def _normalize_failure(reason: str) -> str:
    lowered = reason.lower()
    if "tool" in lowered and "invalid" in lowered:
        return "invalid_tool_call"
    if "validation" in lowered:
        return "validation_failed"
    if "sql" in lowered and "malformed" in lowered:
        return "malformed_sql"
    if "provider" in lowered or "request" in lowered or "api_key" in lowered:
        return "provider_error"
    return "validation_failed"


def _delta_fields(row: dict[str, Any], deterministic: dict[str, Any]) -> dict[str, Any]:
    pairs = {
        "final_score": "final_score",
        "correctness_score": "correctness_score",
        "answer_score": "answer_score",
        "sql_score": "sql_score",
        "api_score": "api_score",
        "estimated_tokens": "estimated_tokens",
        "runtime": "runtime",
        "tool_call_count": "tool_call_count",
    }
    deltas: dict[str, Any] = {}
    for output_key, input_key in pairs.items():
        current = row.get(input_key)
        baseline = deterministic.get(output_key)
        if isinstance(current, (int, float)) and isinstance(baseline, (int, float)):
            deltas[output_key] = round(float(current) - float(baseline), 4)
        else:
            deltas[output_key] = "unavailable"
    return deltas


def _deterministic_rows(config: Config) -> dict[str, dict[str, Any]]:
    data = _load_json(config.outputs_dir / "eval_results_strict.json")
    rows = data.get("rows", []) if isinstance(data, dict) else []
    return {row.get("query_id"): row for row in rows if row.get("strategy") == "SQL_FIRST_API_VERIFY"}


def _summarize_strategy(rows: list[dict[str, Any]], strategy: str) -> dict[str, Any]:
    selected = [row for row in rows if row.get("system") == strategy]
    valid = [row for row in selected if row.get("strict_scoring_status") == "available"]
    return {
        "system": strategy,
        "rows_attempted": len(selected),
        "valid_rows": len(valid),
        "failed_rows": len(selected) - len(valid),
        "strict_scoring_status": "available" if valid else "unavailable",
        "strict_final_score": _avg(valid, "strict_final_score"),
        "strict_correctness": _avg(valid, "strict_correctness"),
        "answer_score": _avg(valid, "answer_score"),
        "sql_score": _avg(valid, "sql_score"),
        "api_score": _avg(valid, "api_score"),
        "estimated_tokens": _avg(valid, "estimated_tokens"),
        "runtime": _avg(valid, "runtime"),
        "tool_calls": _avg(valid, "tool_calls"),
        "token_source_counts": dict(Counter(str(row.get("token_source") or "unavailable") for row in selected)),
        "failure_categories": _aggregate_categories(selected),
        "avg_delta_vs_deterministic": _avg_deltas(valid),
    }


def _avg(rows: list[dict[str, Any]], key: str) -> float | str:
    values = [row.get(key) for row in rows if isinstance(row.get(key), (int, float))]
    if not values:
        return "unavailable"
    return round(sum(values) / len(values), 4)


def _avg_deltas(rows: list[dict[str, Any]]) -> dict[str, Any]:
    keys = ["final_score", "correctness_score", "answer_score", "sql_score", "api_score", "estimated_tokens", "runtime", "tool_call_count"]
    out: dict[str, Any] = {}
    for key in keys:
        values = [
            row.get("delta_vs_sql_first_api_verify", {}).get(key)
            for row in rows
            if isinstance(row.get("delta_vs_sql_first_api_verify", {}).get(key), (int, float))
        ]
        out[key] = round(sum(values) / len(values), 4) if values else "unavailable"
    return out


def _best_delta(per_strategy: list[dict[str, Any]]) -> float | str:
    values = [
        row.get("avg_delta_vs_deterministic", {}).get("final_score")
        for row in per_strategy
        if isinstance(row.get("avg_delta_vs_deterministic", {}).get("final_score"), (int, float))
    ]
    if not values:
        return "unavailable"
    return round(max(values), 4)


def _aggregate_categories(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        for key, value in (row.get("failure_categories") or {}).items():
            try:
                counts[str(key)] += int(value)
            except Exception:
                counts[str(key)] += 1
    return dict(counts)


def _comparison_text(per_strategy: list[dict[str, Any]]) -> str:
    scored = [
        row
        for row in per_strategy
        if isinstance(row.get("avg_delta_vs_deterministic", {}).get("final_score"), (int, float))
    ]
    if not scored:
        return "llm_strict_score_unavailable; deterministic SQL_FIRST_API_VERIFY remains preferred"
    best = max(scored, key=lambda row: row.get("avg_delta_vs_deterministic", {}).get("final_score", -999))
    delta = best.get("avg_delta_vs_deterministic", {}).get("final_score")
    if delta > 0:
        return f"{best.get('system')} improves strict score by {delta}; keep shadow-only until all gates pass"
    if delta == 0:
        return f"{best.get('system')} ties deterministic strict score; deterministic packaged path remains preferred"
    return f"{best.get('system')} is lower by {abs(delta)}; deterministic SQL_FIRST_API_VERIFY remains preferred"


def _recommendation(best_delta: float | str, rows: list[dict[str, Any]]) -> str:
    # Strict scoring alone is not enough for promotion: hidden-style, safety,
    # packaging, and no-secret gates are intentionally outside this diagnostic.
    return "keep_shadow_only"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _fmt(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


if __name__ == "__main__":
    raise SystemExit(main())
