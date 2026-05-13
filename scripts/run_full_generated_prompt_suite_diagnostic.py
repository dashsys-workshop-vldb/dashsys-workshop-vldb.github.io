#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.executor import AgentExecutor
from dashagent.live_api_guard import evaluate_live_api_full_run_guard, guard_override_metadata
from dashagent.trajectory import redact_secrets
from scripts.run_diagnostic_prompt_suite import _intent_matches, _route_matches, _validation_failure_count, _weak_answer


OUTPUT_ROOT_NAME = "generated_prompt_suite_diagnostic"


def main() -> int:
    args = parse_args()
    config = Config.from_env(ROOT)
    report = run_full_generated_prompt_suite_diagnostic(
        config,
        suite_path=Path(args.suite) if args.suite else config.data_dir / "generated_prompt_suite.json",
        limit=args.limit,
        clean=args.clean,
        allow_live_diagnostic_without_success=args.allow_live_diagnostic_without_success,
    )
    print(
        json.dumps(
            {
                "status": report.get("status", "complete"),
                "total_prompts": report.get("total_prompts"),
                "executed_prompts": report.get("executed_prompts"),
                "runtime_pass_count": report.get("runtime_pass_count"),
                "runtime_fail_count": report.get("runtime_fail_count"),
                "json": str(config.outputs_dir / "reports" / "full_generated_prompt_suite_diagnostic.json"),
                "coverage_gap_json": str(config.outputs_dir / "reports" / "generated_prompt_coverage_gap_analysis.json"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run all generated diagnostic prompts through SQL_FIRST_API_VERIFY.")
    parser.add_argument("--suite", help="Path to generated_prompt_suite.json. Defaults to data/generated_prompt_suite.json.")
    parser.add_argument("--limit", type=int, default=None, help="Optional local debug limit. Default runs the full suite.")
    parser.add_argument("--clean", action="store_true", help=f"Remove only outputs/{OUTPUT_ROOT_NAME} before running.")
    parser.add_argument(
        "--allow-live-diagnostic-without-success",
        action="store_true",
        help="Explicitly allow a diagnostic-only live run when smoke has no live_success.",
    )
    return parser.parse_args()


def run_full_generated_prompt_suite_diagnostic(
    config: Config | None = None,
    *,
    suite_path: Path | None = None,
    limit: int | None = None,
    clean: bool = False,
    allow_live_diagnostic_without_success: bool = False,
) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    guard = evaluate_live_api_full_run_guard(
        config,
        override=allow_live_diagnostic_without_success,
        run_label="full_generated_prompt_suite_diagnostic",
    )
    if not guard.get("allowed"):
        return _blocked_report(config, guard)
    override_meta = guard_override_metadata(guard) if guard.get("override_used") else {}
    suite_path = suite_path or config.data_dir / "generated_prompt_suite.json"
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    if not isinstance(suite, list):
        raise ValueError(f"Generated prompt suite must be a JSON list: {suite_path}")

    output_root = config.outputs_dir / OUTPUT_ROOT_NAME
    if clean:
        _clean_output(config, output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    selected = suite[: len(suite) if limit is None else max(0, min(limit, len(suite)))]
    executor = AgentExecutor(config)
    rows: list[dict[str, Any]] = []
    for item in selected:
        prompt_id = str(item.get("prompt_id") or f"gen_{len(rows) + 1:04d}")
        prompt = str(item.get("prompt") or "")
        out_dir = output_root / prompt_id
        start = time.perf_counter()
        try:
            result = executor.run(prompt, strategy="SQL_FIRST_API_VERIFY", query_id=prompt_id, output_dir=out_dir)
            elapsed = time.perf_counter() - start
            trajectory = result.get("trajectory") or _load_json(out_dir / "trajectory.json")
            row = _row_from_result(config, item, result, trajectory, elapsed, out_dir)
        except Exception as exc:
            elapsed = time.perf_counter() - start
            row = {
                "prompt_id": prompt_id,
                "prompt": prompt,
                "diagnostic_only": True,
                "should_be_scored": False,
                "official_strict_score_computed": False,
                "generated_prompt_score_claim": False,
                "status": "failed",
                "failure_category": "runtime_error",
                "error": f"{type(exc).__name__}: {exc}",
                "runtime": round(elapsed, 4),
                "generation_type": item.get("generation_type"),
                "domain_family": item.get("domain_family", "unknown"),
                "answer_intent": item.get("expected_answer_intent_diagnostic", "UNKNOWN"),
                "expected_route_label": item.get("expected_route_diagnostic", "UNKNOWN"),
                "output_dir": _rel(config, out_dir),
            }
        rows.append(redact_secrets(row))

    report = redact_secrets({**_build_report(config, suite, selected, rows, suite_path), **override_meta})
    gap_report = redact_secrets(_build_gap_report(report))
    if override_meta:
        gap_report.update(override_meta)
    (reports_dir / "full_generated_prompt_suite_diagnostic.json").write_text(
        json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8"
    )
    (reports_dir / "full_generated_prompt_suite_diagnostic.md").write_text(_render_report_md(report), encoding="utf-8")
    (reports_dir / "generated_prompt_coverage_gap_analysis.json").write_text(
        json.dumps(gap_report, indent=2, sort_keys=True, default=str), encoding="utf-8"
    )
    (reports_dir / "generated_prompt_coverage_gap_analysis.md").write_text(_render_gap_md(gap_report), encoding="utf-8")
    return report


def _blocked_report(config: Config, guard: dict[str, Any]) -> dict[str, Any]:
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report = redact_secrets(
        {
            "report_type": "full_generated_prompt_suite_diagnostic",
            "status": "blocked_by_live_api_guard",
            "diagnostic_only": True,
            "official_strict_score_computed": False,
            "generated_prompt_score_claim": False,
            "official_score_claim": False,
            "promotion_allowed": False,
            "live_api_guard": guard,
            "total_prompts": None,
            "executed_prompts": 0,
            "runtime_pass_count": 0,
            "runtime_fail_count": 0,
            "rows": [],
        }
    )
    (reports_dir / "full_generated_prompt_suite_diagnostic.json").write_text(
        json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8"
    )
    (reports_dir / "full_generated_prompt_suite_diagnostic.md").write_text(
        "# Full Generated Prompt Suite Diagnostic\n\nBlocked by live API guard. See `live_api_full_run_blocker.md`.\n",
        encoding="utf-8",
    )
    return report


def _row_from_result(
    config: Config,
    item: dict[str, Any],
    result: dict[str, Any],
    trajectory: dict[str, Any],
    elapsed: float,
    out_dir: Path,
) -> dict[str, Any]:
    route = _first_step(trajectory, "route")
    plan = _first_step(trajectory, "plan")
    answer_diag = _first_step(trajectory, "answer_diagnostics")
    sql_steps = _steps(trajectory, "sql_call")
    api_steps = _steps(trajectory, "api_call")
    expected_route = str(item.get("expected_route_diagnostic") or "UNKNOWN")
    expected_intent = str(item.get("expected_answer_intent_diagnostic") or "UNKNOWN")
    actual_route = str(route.get("route_type") or trajectory.get("route_type") or "UNKNOWN")
    domain_type = str(route.get("domain_type") or trajectory.get("domain_type") or "UNKNOWN")
    answer_family = str(answer_diag.get("answer_family") or "UNKNOWN")
    answer_intent = str(answer_diag.get("answer_intent") or answer_family or "UNKNOWN")
    final_answer = str(result.get("final_answer") or trajectory.get("final_answer") or "")
    dry_run_count = sum(1 for step in api_steps if (step.get("result") or {}).get("dry_run") is True)
    zero_row_sql = any(int((step.get("result") or {}).get("row_count") or 0) == 0 for step in sql_steps)
    validation_failures = _validation_failure_count(trajectory) + sum(
        1 for step in [*sql_steps, *api_steps] if (step.get("validation") or {}).get("ok") is False
    )
    evidence_state = _evidence_state(sql_steps, api_steps, dry_run_count, zero_row_sql)
    vague = _weak_answer(final_answer)
    evidence_unused = bool(sql_steps or api_steps) and vague
    route_match = _route_matches(actual_route, expected_route)
    intent_match = _intent_matches(answer_intent, expected_intent)
    row = {
        "prompt_id": item.get("prompt_id"),
        "prompt": item.get("prompt"),
        "diagnostic_only": True,
        "should_be_scored": False,
        "official_strict_score_computed": False,
        "generated_prompt_score_claim": False,
        "status": "passed",
        "generation_type": item.get("generation_type"),
        "domain_family": item.get("domain_family"),
        "answer_intent": expected_intent,
        "expected_route_label": expected_route,
        "actual_route": actual_route,
        "route_matches_diagnostic": route_match,
        "domain_type": domain_type,
        "domain_matches_diagnostic": _domain_matches(domain_type, str(item.get("domain_family") or "")),
        "answer_family": answer_family,
        "actual_answer_intent": answer_intent,
        "answer_intent_matches_diagnostic": intent_match,
        "sql_template": _sql_template(plan),
        "api_mode": _api_mode(actual_route, len(sql_steps), len(api_steps)),
        "sql_calls": len(sql_steps),
        "api_calls": len(api_steps),
        "dry_run_count": dry_run_count,
        "validation_failures": validation_failures,
        "runtime": round(float(trajectory.get("runtime", elapsed) or elapsed), 4),
        "tokens": trajectory.get("estimated_tokens", "unavailable"),
        "final_answer": final_answer,
        "evidence_state": evidence_state,
        "zero_row_sql": zero_row_sql,
        "requires_live_api": dry_run_count > 0 or ("API" in actual_route.upper() and len(api_steps) > 0),
        "vague_or_evidence_unused": evidence_unused,
        "failure_category": _failure_category(validation_failures, route_match, intent_match, evidence_state, zero_row_sql, evidence_unused),
        "output_dir": _rel(config, out_dir),
    }
    return row


def _build_report(
    config: Config,
    suite: list[dict[str, Any]],
    selected: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    suite_path: Path,
) -> dict[str, Any]:
    passed = [row for row in rows if row.get("status") == "passed"]
    failed = [row for row in rows if row.get("status") != "passed"]
    route_mismatch = [row for row in passed if row.get("route_matches_diagnostic") is False]
    domain_mismatch = [row for row in passed if row.get("domain_matches_diagnostic") is False]
    zero_row = [row for row in passed if row.get("zero_row_sql")]
    live_api = [row for row in passed if row.get("requires_live_api")]
    vague = [row for row in passed if row.get("vague_or_evidence_unused")]
    return {
        "report_type": "full_generated_prompt_suite_diagnostic",
        "diagnostic_only": True,
        "official_strict_score_computed": False,
        "generated_prompt_score_claim": False,
        "strategy": "SQL_FIRST_API_VERIFY",
        "suite_path": _rel(config, suite_path),
        "output_root": f"outputs/{OUTPUT_ROOT_NAME}",
        "total_prompts": len(suite),
        "executed_prompts": len(selected),
        "runtime_pass_count": len(passed),
        "runtime_fail_count": len(failed),
        "validation_fail_count": sum(1 for row in rows if int(row.get("validation_failures") or 0) > 0),
        "route_distribution": dict(Counter(row.get("actual_route", "UNKNOWN") for row in passed)),
        "domain_distribution": dict(Counter(row.get("domain_type", "UNKNOWN") for row in passed)),
        "answer_intent_distribution": dict(Counter(row.get("actual_answer_intent", "UNKNOWN") for row in passed)),
        "dry_run_count": sum(int(row.get("dry_run_count") or 0) for row in passed),
        "sql_api_tool_count_distribution": dict(Counter(f"sql={row.get('sql_calls', 0)},api={row.get('api_calls', 0)}" for row in passed)),
        "top_failure_categories": dict(Counter(row.get("failure_category", "ok") for row in rows)),
        "top_route_mismatches": route_mismatch[:20],
        "top_domain_mismatches": domain_mismatch[:20],
        "zero_row_sql_prompts": zero_row[:20],
        "prompts_requiring_live_api": live_api[:20],
        "vague_or_evidence_unused_prompts": vague[:20],
        "rows": rows,
    }


def _build_gap_report(report: dict[str, Any]) -> dict[str, Any]:
    rows = report.get("rows") or []
    unknown = [row for row in rows if row.get("actual_route") == "UNKNOWN" or row.get("domain_type") == "UNKNOWN"]
    dry_run = [row for row in rows if int(row.get("dry_run_count") or 0) > 0]
    live_api = [row for row in rows if row.get("requires_live_api")]
    route_mismatch = [row for row in rows if row.get("route_matches_diagnostic") is False]
    answer_gaps = [row for row in rows if row.get("vague_or_evidence_unused")]
    return {
        "report_type": "generated_prompt_coverage_gap_analysis",
        "diagnostic_only": True,
        "official_strict_score_computed": False,
        "generated_prompt_score_claim": False,
        "source_report": "outputs/reports/full_generated_prompt_suite_diagnostic.json",
        "total_prompts": report.get("total_prompts"),
        "executed_prompts": report.get("executed_prompts"),
        "domain_gaps": dict(Counter(row.get("domain_family", "unknown") for row in route_mismatch)),
        "route_gaps": dict(Counter(row.get("actual_route", "UNKNOWN") for row in route_mismatch)),
        "answer_intent_gaps": dict(Counter(row.get("answer_intent", "UNKNOWN") for row in answer_gaps)),
        "dry_run_gaps": {"count": len(dry_run), "examples": dry_run[:10]},
        "live_api_gaps": {"count": len(live_api), "examples": live_api[:10]},
        "unknown_gaps": {"count": len(unknown), "examples": unknown[:10]},
        "schema_synonym_gaps": _gap_examples(rows, "domain_mismatch"),
        "sql_template_gaps": _gap_examples(rows, "zero_row_sql"),
        "answer_template_gaps": answer_gaps[:10],
        "recommendations": _gap_recommendations(route_mismatch, unknown, dry_run, live_api, answer_gaps),
    }


def _render_report_md(report: dict[str, Any]) -> str:
    lines = [
        "# Full Generated Prompt Suite Diagnostic",
        "",
        "Generated prompts are diagnostic coverage only; this report is not official strict-score evidence.",
        "",
        f"- Total prompts: `{report.get('total_prompts')}`",
        f"- Executed prompts: `{report.get('executed_prompts')}`",
        f"- Runtime pass count: `{report.get('runtime_pass_count')}`",
        f"- Runtime fail count: `{report.get('runtime_fail_count')}`",
        f"- Validation fail count: `{report.get('validation_fail_count')}`",
        f"- Dry-run count: `{report.get('dry_run_count')}`",
        f"- Official strict score computed: `{report.get('official_strict_score_computed')}`",
        "",
        "## Route Distribution",
        "",
    ]
    lines.extend(f"- `{key}`: `{value}`" for key, value in sorted((report.get("route_distribution") or {}).items()))
    lines.extend(["", "## Top Failure Categories", ""])
    lines.extend(f"- `{key}`: `{value}`" for key, value in sorted((report.get("top_failure_categories") or {}).items()))
    lines.extend(["", "## Coverage Notes", ""])
    lines.append("- Generated diagnostics do not enter final submission and do not affect packaged runtime.")
    return "\n".join(lines) + "\n"


def _render_gap_md(report: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Generated Prompt Coverage Gap Analysis",
            "",
            "Diagnostic coverage only; not official strict-score evidence.",
            "",
            f"- Total prompts: `{report.get('total_prompts')}`",
            f"- UNKNOWN gaps: `{report.get('unknown_gaps', {}).get('count')}`",
            f"- Dry-run gaps: `{report.get('dry_run_gaps', {}).get('count')}`",
            f"- Live API gaps: `{report.get('live_api_gaps', {}).get('count')}`",
            "",
            "## Recommendations",
            "",
            *[f"- {item}" for item in report.get("recommendations", [])],
            "",
        ]
    )


def _first_step(trajectory: dict[str, Any], kind: str) -> dict[str, Any]:
    for step in trajectory.get("steps") or []:
        if isinstance(step, dict) and step.get("kind") == kind:
            return step
    return {}


def _steps(trajectory: dict[str, Any], kind: str) -> list[dict[str, Any]]:
    return [step for step in trajectory.get("steps") or [] if isinstance(step, dict) and step.get("kind") == kind]


def _sql_template(plan: dict[str, Any]) -> str:
    for step in plan.get("steps") or []:
        if isinstance(step, dict) and step.get("action") == "sql":
            return str(step.get("family") or "generic_sql")
    return "unavailable"


def _api_mode(route: str, sql_calls: int, api_calls: int) -> str:
    upper = route.upper()
    if api_calls and sql_calls:
        return "SQL_PLUS_API"
    if api_calls:
        return "API_ONLY"
    if "API" in upper and sql_calls:
        return "API_PLANNED"
    return "SQL_ONLY"


def _evidence_state(sql_steps: list[dict[str, Any]], api_steps: list[dict[str, Any]], dry_run_count: int, zero_row_sql: bool) -> str:
    if dry_run_count:
        return "dry_run_unavailable"
    if any((step.get("result") or {}).get("ok") is True for step in api_steps):
        return "live_api_evidence"
    if zero_row_sql:
        return "sql_empty"
    if any((step.get("result") or {}).get("ok") is True for step in sql_steps):
        return "sql_evidence"
    return "no_evidence"


def _domain_matches(domain_type: str, domain_family: str) -> bool | str:
    if not domain_family:
        return "unavailable"
    domain_norm = domain_type.lower().replace("_", "")
    family_norm = domain_family.lower().replace("_", "")
    return family_norm in domain_norm or domain_norm in family_norm


def _failure_category(
    validation_failures: int,
    route_match: Any,
    intent_match: Any,
    evidence_state: str,
    zero_row_sql: bool,
    evidence_unused: bool,
) -> str:
    if validation_failures:
        return "validation_failure"
    if route_match is False:
        return "route_mismatch"
    if intent_match is False:
        return "answer_intent_mismatch"
    if evidence_state == "dry_run_unavailable":
        return "requires_live_api"
    if zero_row_sql:
        return "zero_row_sql"
    if evidence_unused:
        return "answer_vague_or_evidence_unused"
    return "ok"


def _gap_examples(rows: list[dict[str, Any]], category: str) -> list[dict[str, Any]]:
    if category == "domain_mismatch":
        selected = [row for row in rows if row.get("domain_matches_diagnostic") is False]
    else:
        selected = [row for row in rows if row.get("failure_category") == category or row.get(category)]
    return selected[:10]


def _gap_recommendations(
    route_mismatch: list[dict[str, Any]],
    unknown: list[dict[str, Any]],
    dry_run: list[dict[str, Any]],
    live_api: list[dict[str, Any]],
    answer_gaps: list[dict[str, Any]],
) -> list[str]:
    out = []
    if route_mismatch or unknown:
        out.append("Review route/domain stability and synonym coverage for generated paraphrases.")
    if dry_run or live_api:
        out.append("Keep live Adobe API readiness as the primary API-path target; dry-run remains fallback only.")
    if answer_gaps:
        out.append("Use answer-template diagnostics to improve evidence-to-answer directness without changing official score claims.")
    if not out:
        out.append("No high-priority generated prompt coverage gaps were detected in this diagnostic run.")
    return out


def _clean_output(config: Config, output_root: Path) -> None:
    expected = (config.outputs_dir / OUTPUT_ROOT_NAME).resolve()
    if output_root.resolve() != expected:
        raise ValueError(f"Refusing to clean unexpected path: {output_root}")
    if output_root.exists():
        shutil.rmtree(output_root)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _rel(config: Config, path: Path) -> str:
    try:
        return path.resolve().relative_to(config.project_root.resolve()).as_posix()
    except Exception:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
