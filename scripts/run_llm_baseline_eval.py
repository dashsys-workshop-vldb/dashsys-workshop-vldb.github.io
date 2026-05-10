#!/usr/bin/env python
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.eval_harness import EvalHarness, score_answer
from dashagent.llm_client import get_llm_client
from dashagent.llm_tool_agent import (
    GUIDED_REAL_LLM_TWO_TOOLS_BASELINE,
    LLM_CONTROLLER_OPTIMIZED_AGENT,
    RAW_REAL_LLM_TWO_TOOLS_BASELINE,
    run_optimized_llm_controller_agent,
    run_real_llm_two_tools_baseline,
)
from dashagent.trajectory import redact_secrets
from scripts.load_local_env import load_local_env


def main() -> int:
    config = Config.from_env(ROOT)
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    load_local_env(config.project_root)
    harness = EvalHarness(config)
    examples = harness.load_examples()
    client = get_llm_client()
    systems = [
        RAW_REAL_LLM_TWO_TOOLS_BASELINE,
        GUIDED_REAL_LLM_TWO_TOOLS_BASELINE,
        LLM_CONTROLLER_OPTIMIZED_AGENT,
    ]
    if not client.available():
        skipped_probe = client.generate_messages([])
        reason = skipped_probe.get("reason", "LLM provider API key is not set")
        payload = {
            "skipped": True,
            "reason": reason,
            "provider": os.getenv("LLM_PROVIDER", "openai"),
            "rows": [],
            "systems": systems,
        }
        write_outputs(config, payload)
        write_llm_baseline_report(config, payload)
        print(json.dumps({"skipped": True, "reason": payload["reason"], "json": str(config.outputs_dir / "llm_baseline_eval.json")}, indent=2, sort_keys=True))
        return 0
    rows = []
    runners = [
        (RAW_REAL_LLM_TWO_TOOLS_BASELINE, lambda q, *, config: run_real_llm_two_tools_baseline(q, config=config, guided=False, system_name=RAW_REAL_LLM_TWO_TOOLS_BASELINE)),
        (GUIDED_REAL_LLM_TWO_TOOLS_BASELINE, lambda q, *, config: run_real_llm_two_tools_baseline(q, config=config, guided=True, system_name=GUIDED_REAL_LLM_TWO_TOOLS_BASELINE)),
        (LLM_CONTROLLER_OPTIMIZED_AGENT, run_optimized_llm_controller_agent),
    ]
    for example in examples:
        for system, runner in runners:
            start = time.perf_counter()
            result = runner(example.query, config=config)
            elapsed = time.perf_counter() - start
            valid_agent_run = bool(result.get("valid_agent_run", not result.get("skipped", False)))
            if system in {RAW_REAL_LLM_TWO_TOOLS_BASELINE, GUIDED_REAL_LLM_TWO_TOOLS_BASELINE} and not valid_agent_run:
                answer_score = None
                answer_reason = "Real LLM was called but the tool loop did not complete a valid agent run."
            else:
                answer_score, answer_reason = score_answer(result.get("final_answer", ""), example.gold_answer)
            rows.append(
                {
                    "query_id": example.query_id,
                    "query": example.query,
                    "system": system,
                    "baseline_variant": result.get("baseline_variant"),
                    "answer_score": round(answer_score, 4) if isinstance(answer_score, (int, float)) else None,
                    "answer_reason": answer_reason,
                    "tool_call_count": result.get("tool_call_count", result.get("trajectory", {}).get("tool_call_count", 0)),
                    "runtime": round(elapsed, 4),
                    "skipped": result.get("skipped", False),
                    "real_llm_called": result.get("real_llm_called", bool(result.get("real_llm_used"))),
                    "provider": result.get("llm_provider"),
                    "model": result.get("llm_model"),
                    "backend_type": result.get("backend_type", result.get("trajectory", {}).get("backend_type")),
                    "sdk_path_used": result.get("sdk_path_used", result.get("trajectory", {}).get("sdk_path_used")),
                    "tool_calls_executed": result.get("tool_calls_executed", result.get("tool_call_count", 0) > 0),
                    "valid_agent_run": valid_agent_run,
                    "skipped_or_failed": result.get("skipped_or_failed", result.get("skipped", False) or not valid_agent_run),
                    "failure_reason": result.get("failure_reason", result.get("skipped_reason", "")),
                    "llm_turn_count": result.get("trajectory", {}).get("llm_turn_count", len(result.get("llm_turns", []))),
                    "llm_tool_calls": result.get("llm_tool_calls", result.get("trajectory", {}).get("llm_tool_calls", [])),
                    "validation_results": result.get("validation_results", result.get("trajectory", {}).get("validation_results", [])),
                    "execution_previews": result.get("execution_previews", result.get("trajectory", {}).get("execution_previews", [])),
                    "successful_evidence_count": result.get("successful_evidence_count", 0),
                    "invalid_tool_call_count": result.get("invalid_tool_call_count", 0),
                    "duplicate_invalid_call_count": result.get("duplicate_invalid_call_count", 0),
                    "repaired_endpoint_count": result.get("repaired_endpoint_count", 0),
                    "schema_hint_injected": result.get("schema_hint_injected", 0),
                    "dry_run_only_api_count": result.get("dry_run_only_api_count", 0),
                    "unsupported_negative_answer_count": result.get("unsupported_negative_answer_count", 0),
                    "failure_categories": result.get("failure_categories", {}),
                    "prompt_context_tokens": result.get("prompt_context_tokens", result.get("trajectory", {}).get("prompt_context_tokens", 0)),
                    "estimated_tokens": result.get("estimated_tokens", result.get("trajectory", {}).get("estimated_tokens", 0)),
                    "llm_total_tokens": result.get("llm_total_tokens", result.get("trajectory", {}).get("llm_total_tokens")),
                    "token_source": result.get("token_source", result.get("trajectory", {}).get("token_source", "unavailable")),
                    "final_answer": result.get("final_answer", ""),
                    "trajectory": result.get("trajectory", {}),
                }
            )
    payload = {"skipped": False, "rows": rows, "systems": systems}
    write_outputs(config, payload)
    write_llm_baseline_report(config, payload)
    print(json.dumps({"skipped": False, "rows": len(rows), "json": str(config.outputs_dir / "llm_baseline_eval.json")}, indent=2, sort_keys=True))
    return 0


def write_outputs(config: Config, payload: dict) -> None:
    json_path = config.outputs_dir / "llm_baseline_eval.json"
    md_path = config.outputs_dir / "llm_baseline_comparison.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    lines = ["# LLM Baseline Comparison", ""]
    if payload.get("skipped"):
        lines.append(f"Real LLM baseline systems were skipped because {payload.get('reason')}.")
    else:
        lines.extend(["| System | Rows | Valid runs | Failed runs | Avg answer score on valid runs | Avg tool calls on valid runs |", "| --- | ---: | ---: | ---: | ---: | ---: |"])
        for system in payload.get("systems", []):
            rows = [row for row in payload.get("rows", []) if row.get("system") == system]
            valid_rows = [row for row in rows if row.get("valid_agent_run")]
            failed_rows = [row for row in rows if row.get("skipped_or_failed") and not row.get("valid_agent_run")]
            scored_rows = [row for row in valid_rows if isinstance(row.get("answer_score"), (int, float))]
            avg_answer = sum(row.get("answer_score", 0) for row in scored_rows) / len(scored_rows) if scored_rows else 0
            avg_tools = sum(row.get("tool_call_count", 0) for row in valid_rows) / len(valid_rows) if valid_rows else 0
            lines.append(f"| {system} | {len(rows)} | {len(valid_rows)} | {len(failed_rows)} | {avg_answer:.4f} | {avg_tools:.2f} |")
        failed_real = [
            row for row in payload.get("rows", [])
            if row.get("system") in {RAW_REAL_LLM_TWO_TOOLS_BASELINE, GUIDED_REAL_LLM_TWO_TOOLS_BASELINE}
            and row.get("real_llm_called")
            and not row.get("valid_agent_run")
        ]
        if failed_real:
            lines.extend(
                [
                    "",
                    "## Failed Real LLM Tool Loops",
                    "",
                    "These rows are real LLM calls, but they are not counted as successful real tool-using baseline runs.",
                    "",
                    "| Query ID | Tool calls executed? | Failure reason |",
                    "| --- | --- | --- |",
                ]
            )
            for row in failed_real[:20]:
                lines.append(f"| `{row.get('query_id')}` | {row.get('tool_calls_executed')} | {row.get('failure_reason')} |")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_llm_baseline_report(config: Config, payload: dict) -> None:
    report = build_llm_baseline_report(config, payload)
    json_path = config.outputs_dir / "llm_baseline_eval_report.json"
    md_path = config.outputs_dir / "llm_baseline_eval_report.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(render_llm_baseline_markdown(report), encoding="utf-8")


def build_llm_baseline_report(config: Config, payload: dict) -> dict:
    rows = payload.get("rows") or []
    smoke = _load_json(config.outputs_dir / "llm_sdk_backend_check.json") or _load_json(config.outputs_dir / "openai_compatible_llm_check.json")
    strict = _load_json(config.outputs_dir / "llm_strict_baseline_eval.json")
    deterministic = _deterministic_sql_first_summary(config)
    strategies = []
    for system in payload.get("systems", []):
        system_rows = [row for row in rows if row.get("system") == system]
        valid_rows = [row for row in system_rows if row.get("valid_agent_run")]
        scored_rows = [row for row in valid_rows if isinstance(row.get("answer_score"), (int, float))]
        strict_summary = _strict_strategy_summary(strict, system)
        strategies.append(
            {
                "system": system,
                "rows": len(system_rows),
                "valid_runs": len(valid_rows),
                "failed_runs": sum(1 for row in system_rows if row.get("skipped_or_failed") and not row.get("valid_agent_run")),
                "avg_answer_score": _avg(scored_rows, "answer_score"),
                "strict_score": strict_summary.get("strict_final_score", "unavailable"),
                "strict_correctness": strict_summary.get("strict_correctness", "unavailable"),
                "strict_scoring_status": strict_summary.get("strict_scoring_status", "unavailable"),
                "avg_tool_calls": _avg(valid_rows, "tool_call_count"),
                "avg_tokens": _avg_token_rows(valid_rows),
                "token_source_counts": _token_source_counts(valid_rows),
                "avg_runtime": _avg(valid_rows, "runtime"),
                "failure_categories": _aggregate_failures(system_rows),
            }
        )
    skipped = []
    if payload.get("skipped"):
        skipped = [{"system": system, "reason": payload.get("reason", "LLM baseline skipped")} for system in payload.get("systems", [])]
    recommendation = _llm_baseline_recommendation(payload, strategies, smoke, strict)
    model = smoke.get("backend_name") or os.getenv("OPENAI_MODEL") or os.getenv("ANTHROPIC_MODEL", "")
    base_url = smoke.get("base_url") or os.getenv("OPENAI_BASE_URL") or os.getenv("ANTHROPIC_BASE_URL", "")
    report = {
        "framework": "generic_sdk_llm_baseline",
        "framework_note": "The LLM baseline framework is generic; the configured model/provider is backend metadata.",
        "provider_type": smoke.get("provider_type", "openai_compatible"),
        "provider": smoke.get("provider", "openai_compatible"),
        "backend_type": smoke.get("backend_type", "openai_sdk"),
        "transport": smoke.get("transport", smoke.get("backend_type", "openai_sdk")),
        "sdk_path_used": smoke.get("sdk_path_used", smoke.get("backend_type", "openai_sdk") in {"openai_sdk", "anthropic_sdk"}),
        "sdk_client": "SDK-based LLM client",
        "base_url": base_url,
        "model": model,
        "backend_name": model or "unavailable",
        "smoke_test_passed": smoke.get("ok", "unavailable"),
        "tool_calling_supported": smoke.get("tool_calling_supported", "unavailable"),
        "strict_scoring_status": strict.get("summary", {}).get("strict_scoring_status", "unavailable") if strict else "unavailable",
        "baseline_strategies_run": [row["system"] for row in strategies if row["rows"] > 0],
        "skipped_strategies": skipped,
        "per_strategy": strategies,
        "deterministic_sql_first_api_verify": deterministic,
        "comparison_against_deterministic": _compare_to_deterministic(strategies, deterministic),
        "failure_categories": _aggregate_failures(rows),
        "recommendation": recommendation,
        "promotion_status": "shadow_only",
        "safety_notes": [
            "Generic SDK LLM baseline results are comparison-only.",
            "The current model/backend is metadata; switch models by changing .env.local.",
            "Packaged SQL_FIRST_API_VERIFY behavior is unchanged.",
            "No LLM result is promoted automatically.",
        ],
    }
    safe_report = redact_secrets(report)
    safe_report["base_url"] = report.get("base_url")
    safe_report["model"] = report.get("model")
    safe_report["backend_name"] = report.get("backend_name")
    safe_report["provider"] = report.get("provider")
    safe_report["provider_type"] = report.get("provider_type")
    safe_report["backend_type"] = report.get("backend_type")
    safe_report["transport"] = report.get("transport")
    safe_report["sdk_path_used"] = report.get("sdk_path_used")
    return safe_report


def render_llm_baseline_markdown(report: dict) -> str:
    lines = [
        "# SDK LLM Baseline Evaluation Report",
        "",
        f"- Framework: `{report.get('framework')}`",
        f"- Provider type: `{report.get('provider_type')}`",
        f"- Backend type: `{report.get('backend_type')}`",
        f"- Transport: `{report.get('transport')}`",
        f"- SDK path used: `{report.get('sdk_path_used')}`",
        f"- SDK client: `{report.get('sdk_client')}`",
        f"- Base URL: `{report.get('base_url') or 'unavailable'}`",
        f"- Current LLM backend: `{report.get('backend_name') or 'unavailable'}`",
        f"- Smoke test passed: `{report.get('smoke_test_passed')}`",
        f"- Tool calling supported: `{report.get('tool_calling_supported')}`",
        f"- Strict scoring status: `{report.get('strict_scoring_status')}`",
        f"- Recommendation: `{report.get('recommendation')}`",
        f"- Promotion status: `{report.get('promotion_status')}`",
        "",
        report.get("framework_note", "The LLM baseline framework is generic; the configured model is backend metadata."),
        "",
        "## Strategy Summary",
        "",
        "| Strategy | Rows | Valid runs | Failed runs | Avg answer score | Strict score | Strict status | Avg tools | Avg tokens | Token source | Avg runtime |",
        "| --- | ---: | ---: | ---: | ---: | --- | --- | ---: | ---: | --- | ---: |",
    ]
    for row in report.get("per_strategy", []):
        lines.append(
            f"| `{row.get('system')}` | {row.get('rows')} | {row.get('valid_runs')} | {row.get('failed_runs')} | "
            f"{_fmt(row.get('avg_answer_score'))} | {row.get('strict_score')} | {row.get('strict_scoring_status')} | "
            f"{_fmt(row.get('avg_tool_calls'))} | {_fmt(row.get('avg_tokens'))} | {row.get('token_source_counts')} | {_fmt(row.get('avg_runtime'))} |"
        )
    lines.extend(
        [
            "",
            "## Deterministic Comparison",
            "",
            f"- SQL_FIRST_API_VERIFY strict score: `{report.get('deterministic_sql_first_api_verify', {}).get('avg_final_score', 'unavailable')}`",
            f"- Comparison: `{report.get('comparison_against_deterministic')}`",
            "",
            "The SDK LLM baseline remains shadow-only unless a later explicit promotion passes strict scoring, safety, hidden-style, and packaging gates.",
        ]
    )
    return "\n".join(lines) + "\n"


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _deterministic_sql_first_summary(config: Config) -> dict:
    data = _load_json(config.outputs_dir / "eval_results_strict.json")
    rows = [row for row in data.get("rows", []) if row.get("strategy") == "SQL_FIRST_API_VERIFY"]
    return {
        "rows": len(rows),
        "avg_final_score": _avg(rows, "final_score"),
        "avg_correctness_score": _avg(rows, "correctness_score"),
        "avg_answer_score": _avg(rows, "answer_score"),
        "avg_tool_calls": _avg(rows, "tool_call_count"),
        "avg_tokens": _avg(rows, "estimated_tokens"),
        "avg_runtime": _avg(rows, "runtime"),
    }


def _avg(rows: list[dict], key: str) -> float | str:
    values = [row.get(key) for row in rows if isinstance(row.get(key), (int, float))]
    if not values:
        return "unavailable"
    return round(sum(values) / len(values), 4)


def _avg_token_rows(rows: list[dict]) -> float | str:
    values = []
    for row in rows:
        token_value = row.get("llm_total_tokens")
        if not isinstance(token_value, (int, float)):
            token_value = row.get("estimated_tokens")
        if not isinstance(token_value, (int, float)):
            token_value = row.get("prompt_context_tokens")
        if isinstance(token_value, (int, float)):
            values.append(token_value)
    if not values:
        return "unavailable"
    return round(sum(values) / len(values), 4)


def _token_source_counts(rows: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        source = str(row.get("token_source") or "unavailable")
        if source == "unavailable" and isinstance(row.get("estimated_tokens"), (int, float)) and row.get("estimated_tokens"):
            source = "estimated"
        counts[source] = counts.get(source, 0) + 1
    return counts


def _strict_strategy_summary(strict: dict, system: str) -> dict:
    if not isinstance(strict, dict):
        return {}
    for row in strict.get("per_strategy", []):
        if row.get("system") == system:
            return row
    return {}


def _aggregate_failures(rows: list[dict]) -> dict:
    counts: dict[str, int] = {}
    for row in rows:
        categories = row.get("failure_categories")
        if isinstance(categories, dict):
            for key, value in categories.items():
                counts[key] = counts.get(key, 0) + int(value or 0)
        reason = str(row.get("failure_reason") or "").strip()
        if reason:
            counts[reason] = counts.get(reason, 0) + 1
    return counts


def _compare_to_deterministic(strategies: list[dict], deterministic: dict) -> str:
    det_score = deterministic.get("avg_final_score")
    if not isinstance(det_score, (int, float)):
        return "deterministic_strict_score_unavailable"
    scored = [
        row
        for row in strategies
        if isinstance(row.get("strict_score"), (int, float))
    ]
    if not scored:
        return "llm_strict_score_unavailable; deterministic SQL_FIRST_API_VERIFY remains preferred"
    best = max(scored, key=lambda row: float(row.get("strict_score", 0.0)))
    delta = round(float(best["strict_score"]) - float(det_score), 4)
    if delta > 0:
        return f"best_llm_strategy={best.get('system')} strict_delta={delta}; keep shadow-only until safety gates pass"
    if delta == 0:
        return f"best_llm_strategy={best.get('system')} ties deterministic strict score; keep SQL_FIRST_API_VERIFY preferred"
    return f"best_llm_strategy={best.get('system')} strict_delta={delta}; deterministic SQL_FIRST_API_VERIFY remains preferred"


def _llm_baseline_recommendation(payload: dict, strategies: list[dict], smoke: dict, strict: dict) -> str:
    if payload.get("skipped"):
        return "comparison_only"
    if smoke and smoke.get("tool_calling_supported") is False:
        return "keep_shadow_only"
    if not strict or strict.get("summary", {}).get("strict_scoring_status") != "available":
        return "keep_shadow_only"
    if (
        strict.get("summary", {}).get("best_delta_vs_deterministic", 0) > 0
        and strict.get("summary", {}).get("all_gates_clean") is True
        and not strict.get("summary", {}).get("safety_flags")
    ):
        return "candidate_for_future_trial"
    return "keep_shadow_only"


def _fmt(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


if __name__ == "__main__":
    raise SystemExit(main())
