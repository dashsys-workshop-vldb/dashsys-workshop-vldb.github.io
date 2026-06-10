#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.executor import AgentExecutor
from dashagent.trajectory import redact_secrets


DEFAULT_LIMIT = 50


def main() -> int:
    args = parse_args()
    config = Config.from_env(ROOT)
    report = run_diagnostic_prompt_suite(
        config,
        suite_path=Path(args.suite) if args.suite else config.data_dir / "generated_prompt_suite.json",
        limit=args.limit,
        full=args.full,
        clean=args.clean,
        with_llm_semantic_router_shadow=args.with_llm_semantic_router_shadow,
    )
    print(
        json.dumps(
            {
                "total_prompts": report["total_prompts"],
                "executed_prompts": report["executed_prompts"],
                "passed_runtime_count": report["passed_runtime_count"],
                "failed_runtime_count": report["failed_runtime_count"],
                "json": str(config.outputs_dir / "reports" / "diagnostic_prompt_suite_run.json"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run diagnostic-only generated prompts through SQL_FIRST_API_VERIFY.")
    parser.add_argument("--suite", help="Path to generated_prompt_suite.json. Defaults to data/generated_prompt_suite.json.")
    parser.add_argument("--limit", type=int, default=None, help=f"Number of prompts to run. Defaults to {DEFAULT_LIMIT}.")
    parser.add_argument("--full", action="store_true", help="Run all generated prompts.")
    parser.add_argument("--clean", action="store_true", help="Remove only outputs/diagnostic_prompt_suite before running.")
    parser.add_argument(
        "--with-llm-semantic-router-shadow",
        action="store_true",
        help="Enable the LLM semantic routing helper in shadow mode for diagnostic stats only.",
    )
    return parser.parse_args()


def run_diagnostic_prompt_suite(
    config: Config | None = None,
    *,
    suite_path: Path | None = None,
    limit: int | None = None,
    full: bool = False,
    clean: bool = False,
    with_llm_semantic_router_shadow: bool = False,
) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    runtime_config = (
        replace(config, enable_llm_semantic_router=True, llm_semantic_router_shadow_only=True)
        if with_llm_semantic_router_shadow
        else config
    )
    suite_path = suite_path or (config.data_dir / "generated_prompt_suite.json")
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    if not isinstance(suite, list):
        raise ValueError(f"Diagnostic prompt suite must be a JSON list: {suite_path}")

    output_root = config.outputs_dir / "diagnostic_prompt_suite"
    if clean:
        _clean_diagnostic_output(config, output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    run_limit = len(suite) if full else (limit if limit is not None else DEFAULT_LIMIT)
    selected = suite[: max(0, min(run_limit, len(suite)))]
    executor = AgentExecutor(runtime_config)

    rows: list[dict[str, Any]] = []
    for item in selected:
        prompt_id = str(item.get("prompt_id") or f"diagnostic_{len(rows) + 1:04d}")
        prompt = str(item.get("prompt") or "")
        out_dir = output_root / prompt_id
        start = time.perf_counter()
        try:
            result = executor.run(prompt, strategy="SQL_FIRST_API_VERIFY", query_id=prompt_id, output_dir=out_dir)
            elapsed = time.perf_counter() - start
            trajectory = result.get("trajectory") or _load_json(out_dir / "trajectory.json")
            row = _row_from_result(item, result, trajectory, elapsed)
        except Exception as exc:
            elapsed = time.perf_counter() - start
            row = {
                "prompt_id": prompt_id,
                "prompt": prompt,
                "status": "failed",
                "error": f"{type(exc).__name__}: {exc}",
                "runtime": round(elapsed, 4),
                "expected_route_diagnostic": item.get("expected_route_diagnostic", "UNKNOWN"),
                "expected_answer_intent_diagnostic": item.get("expected_answer_intent_diagnostic", "UNKNOWN"),
                "domain_family": item.get("domain_family", "unknown"),
                "generation_type": item.get("generation_type"),
                "output_dir": str(out_dir),
            }
        rows.append(redact_secrets(row))

    report = _build_report(
        config,
        suite,
        selected,
        rows,
        suite_path=suite_path,
        full=full,
        limit=run_limit,
        with_llm_semantic_router_shadow=with_llm_semantic_router_shadow,
    )
    report = redact_secrets(report)
    json_path = reports_dir / "diagnostic_prompt_suite_run.json"
    md_path = reports_dir / "diagnostic_prompt_suite_run.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_render_markdown(report), encoding="utf-8")
    return report


def _row_from_result(item: dict[str, Any], result: dict[str, Any], trajectory: dict[str, Any], elapsed: float) -> dict[str, Any]:
    sql_calls = int(trajectory.get("sql_call_count") or 0)
    api_calls = int(trajectory.get("api_call_count") or 0)
    route_type = str(trajectory.get("route_type") or "UNKNOWN")
    expected_route = str(item.get("expected_route_diagnostic") or "UNKNOWN")
    expected_intent = str(item.get("expected_answer_intent_diagnostic") or "UNKNOWN")
    final_answer = str(result.get("final_answer") or trajectory.get("final_answer") or "")
    actual_answer_family = _extract_answer_family(trajectory, final_answer)
    semantic_checkpoint = _semantic_checkpoint(trajectory)
    return {
        "prompt_id": item.get("prompt_id"),
        "prompt": item.get("prompt"),
        "status": "passed",
        "generation_type": item.get("generation_type"),
        "domain_family": item.get("domain_family"),
        "expected_route_diagnostic": expected_route,
        "actual_route_type": route_type,
        "route_matches_diagnostic": _route_matches(route_type, expected_route),
        "expected_answer_intent_diagnostic": expected_intent,
        "actual_answer_family": actual_answer_family,
        "answer_intent_matches_diagnostic": _intent_matches(actual_answer_family, expected_intent),
        "sql_call_count": sql_calls,
        "api_call_count": api_calls,
        "tool_count": int(trajectory.get("tool_call_count") or sql_calls + api_calls),
        "estimated_tokens": trajectory.get("estimated_tokens", "unavailable"),
        "runtime": round(float(trajectory.get("runtime", elapsed) or elapsed), 4),
        "dry_run_api_status": _dry_run_status(trajectory),
        "evidence_available": bool(sql_calls or api_calls),
        "validation_failures": _validation_failure_count(trajectory),
        "final_answer": final_answer,
        "weak_answer_flag": _weak_answer(final_answer),
        "llm_semantic_router_shadow": semantic_checkpoint,
        "errors": trajectory.get("errors", []),
        "output_dir": result.get("output_dir"),
    }


def _build_report(
    config: Config,
    suite: list[dict[str, Any]],
    selected: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    *,
    suite_path: Path,
    full: bool,
    limit: int,
    with_llm_semantic_router_shadow: bool,
) -> dict[str, Any]:
    passed = [row for row in rows if row.get("status") == "passed"]
    failed = [row for row in rows if row.get("status") != "passed"]
    route_mismatches = [row for row in passed if row.get("route_matches_diagnostic") is False]
    weak_answers = [row for row in passed if row.get("weak_answer_flag")]
    report = {
        "report_type": "diagnostic_prompt_suite_run",
        "diagnostic_only": True,
        "official_strict_score_computed": False,
        "not_official_score": True,
        "strategy": "SQL_FIRST_API_VERIFY",
        "llm_runtime_used": with_llm_semantic_router_shadow,
        "llm_runtime_note": (
            "LLM semantic routing helper ran in shadow mode only; no official strict score is computed."
            if with_llm_semantic_router_shadow
            else "The diagnostic suite runner uses the deterministic AgentExecutor path; no LLM/model call is made."
        ),
        "llm_semantic_router_shadow_enabled": with_llm_semantic_router_shadow,
        "llm_semantic_router_shadow_stats": _semantic_shadow_stats(rows),
        "suite_path": _rel(config, suite_path),
        "output_root": "outputs/diagnostic_prompt_suite",
        "default_limit": DEFAULT_LIMIT,
        "full": full,
        "limit": limit,
        "total_prompts": len(suite),
        "executed_prompts": len(selected),
        "passed_runtime_count": len(passed),
        "failed_runtime_count": len(failed),
        "validation_failure_count": sum(int(row.get("validation_failures", 0) or 0) for row in rows),
        "route_distribution": dict(Counter(row.get("actual_route_type", "UNKNOWN") for row in passed)),
        "domain_family_distribution": dict(Counter(item.get("domain_family", "unknown") for item in selected)),
        "answer_intent_distribution": dict(Counter(item.get("expected_answer_intent_diagnostic", "UNKNOWN") for item in selected)),
        "sql_api_call_distribution": dict(Counter(f"sql={row.get('sql_call_count', 0)},api={row.get('api_call_count', 0)}" for row in passed)),
        "dry_run_api_count": sum(1 for row in passed if row.get("dry_run_api_status") == "dry_run"),
        "top_failure_categories": dict(Counter(_failure_category(row) for row in rows if row.get("status") != "passed" or row.get("validation_failures"))),
        "weak_answer_examples": weak_answers[:10],
        "routing_mismatch_examples": route_mismatches[:10],
        "recommended_future_improvement_areas": _recommendations(rows, route_mismatches, weak_answers),
        "rows": rows,
    }
    return report


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Diagnostic Prompt Suite Run",
        "",
        "Diagnostic prompt coverage only; not official strict score.",
        "",
        f"- Strategy: `{report.get('strategy')}`",
        f"- LLM runtime used: `{report.get('llm_runtime_used')}`",
        f"- LLM semantic router shadow enabled: `{report.get('llm_semantic_router_shadow_enabled')}`",
        f"- Total prompts in suite: `{report.get('total_prompts')}`",
        f"- Executed prompts: `{report.get('executed_prompts')}`",
        f"- Passed runtime count: `{report.get('passed_runtime_count')}`",
        f"- Failed runtime count: `{report.get('failed_runtime_count')}`",
        f"- Validation failure count: `{report.get('validation_failure_count')}`",
        f"- Dry-run API count: `{report.get('dry_run_api_count')}`",
        "",
        "## Route Distribution",
        "",
    ]
    for key, value in sorted((report.get("route_distribution") or {}).items()):
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Top Failure Categories", ""])
    if report.get("top_failure_categories"):
        for key, value in sorted(report["top_failure_categories"].items()):
            lines.append(f"- `{key}`: `{value}`")
    else:
        lines.append("- `none`: `0`")
    lines.extend(["", "## Recommended Future Improvement Areas", ""])
    lines.extend(f"- {item}" for item in report.get("recommended_future_improvement_areas", []))
    lines.extend(["", "Generated prompts are not packaged into final submission and are not used by official strict eval.", ""])
    return "\n".join(lines)


def _clean_diagnostic_output(config: Config, output_root: Path) -> None:
    resolved = output_root.resolve()
    expected = (config.outputs_dir / "diagnostic_prompt_suite").resolve()
    if resolved != expected:
        raise ValueError(f"--clean may only remove {expected}, not {resolved}")
    if output_root.exists():
        shutil.rmtree(output_root)


def _route_matches(actual: str, expected: str) -> bool | str:
    if expected == "UNKNOWN" or not expected:
        return "unavailable"
    actual_upper = actual.upper()
    if expected == "SQL_PLUS_API":
        return "SQL" in actual_upper and "API" in actual_upper
    if expected == "SQL_ONLY":
        return "SQL" in actual_upper and "API" not in actual_upper
    if expected == "LOCAL_DB_ONLY":
        return actual_upper in {"LOCAL_DB_ONLY", "SQL_ONLY"} or ("SQL" in actual_upper and "API" not in actual_upper)
    return expected in actual_upper


def _extract_answer_family(trajectory: dict[str, Any], final_answer: str) -> str:
    for checkpoint in trajectory.get("checkpoints") or []:
        if not isinstance(checkpoint, dict):
            continue
        payload = checkpoint.get("output") or {}
        if isinstance(payload, dict):
            for key in ["answer_family", "answer_intent", "intent"]:
                if payload.get(key):
                    return str(payload[key])
    lowered = final_answer.lower()
    if any(word in lowered for word in ["you have", "there are", "count"]):
        return "COUNT"
    if any(word in lowered for word in ["not available", "unavailable", "dry-run"]):
        return "SUMMARY"
    return "UNKNOWN"


def _intent_matches(actual: str, expected: str) -> bool | str:
    if expected == "UNKNOWN" or not expected or actual == "UNKNOWN":
        return "unavailable"
    if expected == "LIST" and actual in {"SUMMARY", "LIST"}:
        return True
    if expected == "COUNT" and actual in {"COUNT", "SUMMARY"}:
        return True
    return actual == expected


def _dry_run_status(trajectory: dict[str, Any]) -> str:
    text = json.dumps(trajectory, default=str).lower()
    if "dry_run" in text or "dry-run" in text or "credentials are unavailable" in text:
        return "dry_run"
    return "none"


def _validation_failure_count(trajectory: dict[str, Any]) -> int:
    count = len(trajectory.get("errors") or [])
    for item in trajectory.get("validation_results") or []:
        if isinstance(item, dict) and not item.get("valid", True):
            count += 1
    return count


def _semantic_checkpoint(trajectory: dict[str, Any]) -> dict[str, Any]:
    for checkpoint in trajectory.get("checkpoints") or []:
        if isinstance(checkpoint, dict) and checkpoint.get("checkpoint_id") == "checkpoint_llm_semantic_routing_helper":
            output = checkpoint.get("output")
            return output if isinstance(output, dict) else {}
    return {}


def _semantic_shadow_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    checkpoints = [row.get("llm_semantic_router_shadow") for row in rows if isinstance(row.get("llm_semantic_router_shadow"), dict)]
    return {
        "checkpoint_count": len(checkpoints),
        "helper_called": sum(1 for item in checkpoints if item.get("helper_called")),
        "helper_valid": sum(1 for item in checkpoints if item.get("helper_valid")),
        "helper_rejected": sum(1 for item in checkpoints if item.get("helper_called") and not item.get("helper_valid")),
        "hint_applied": sum(1 for item in checkpoints if item.get("hint_applied")),
        "application_modes": dict(Counter(item.get("hint_application_mode", "unavailable") for item in checkpoints)),
    }


def _weak_answer(answer: str) -> bool:
    text = answer.strip().lower()
    if not text:
        return True
    if len(text) < 20:
        return True
    return "insufficient evidence" in text or "cannot answer" in text


def _failure_category(row: dict[str, Any]) -> str:
    if row.get("status") != "passed":
        return "runtime_error"
    if row.get("validation_failures"):
        return "validation_failure"
    return "ok"


def _recommendations(rows: list[dict[str, Any]], route_mismatches: list[dict[str, Any]], weak_answers: list[dict[str, Any]]) -> list[str]:
    recommendations = []
    if route_mismatches:
        recommendations.append("Review diagnostic route mismatches for prompt-router and query-analysis coverage.")
    if weak_answers:
        recommendations.append("Inspect weak answer examples for evidence-to-answer template gaps.")
    if any(row.get("dry_run_api_status") == "dry_run" for row in rows):
        recommendations.append("Keep dry-run wording concise and avoid fabricated live API payloads.")
    if not recommendations:
        recommendations.append("Use the full suite periodically for broader non-scored coverage checks.")
    return recommendations


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _rel(config: Config, path: Path) -> str:
    try:
        return path.resolve().relative_to(config.project_root.resolve()).as_posix()
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
