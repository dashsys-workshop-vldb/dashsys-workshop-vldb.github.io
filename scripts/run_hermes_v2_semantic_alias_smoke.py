#!/usr/bin/env python
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config, ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2
from dashagent.executor import AgentExecutor
from dashagent.trajectory import redact_secrets
from scripts.load_local_env import load_local_env
from scripts.probe_hermes_sdk_toolcall import run_hermes_toolcall_probe
from scripts.run_hermes_v2_toolcall_smoke import (
    _count_steps,
    _final_gate_metrics,
    _flatten_diagnostics,
    _plan_paths,
)


REPORT_DIR = ROOT / "outputs" / "reports" / "hermes_v2_toolcall_smoke"
ALIAS_PROMPTS = [
    {
        "id": "repeated_local_status",
        "prompt": "Show the local status of Birthday Message, then use the same local status again in the final summary.",
        "expected": "ALIAS_OPTIONAL_REPEATED_LOCAL",
    },
    {
        "id": "compare_with_repeated_local",
        "prompt": "Compare the local status of Birthday Message with its live status, and also include the local status separately.",
        "expected": "LOCAL_AND_LIVE_NOT_ALIASED",
    },
    {
        "id": "status_and_date_negative",
        "prompt": "Give the local status and published date of Birthday Message.",
        "expected": "NO_STATUS_DATE_ALIAS",
    },
    {
        "id": "count_and_list_negative",
        "prompt": "Count schema records and list schemas.",
        "expected": "NO_COUNT_LIST_ALIAS",
    },
]


def run_hermes_v2_semantic_alias_smoke(config: Config | None = None, *, report_dir: Path | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    report_dir = report_dir or REPORT_DIR
    report_dir.mkdir(parents=True, exist_ok=True)
    load_local_env(config.project_root)
    probe = run_hermes_toolcall_probe(config, report_dir=ROOT / "outputs" / "reports" / "hermes_toolcall_probe")
    report: dict[str, Any] = {
        "ok": False,
        "skipped": False,
        "skip_reason": "",
        "strategy": ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2,
        "probe": {
            "ok": probe.get("ok"),
            "provider": probe.get("provider"),
            "model": probe.get("model"),
            "sdk_path_used": probe.get("sdk_path_used"),
            "toolcall_supported": probe.get("toolcall_supported"),
            "tool_calls_count": probe.get("tool_calls_count"),
            "tool_name": probe.get("tool_name"),
            "finish_reason": probe.get("finish_reason"),
            "error": probe.get("error"),
        },
        "rows": [],
        "summary": {},
    }
    if not probe.get("toolcall_supported"):
        report.update({"skipped": True, "skip_reason": "Hermes/OpenAI-compatible model did not return native SDK tool_calls in probe."})
        report["summary"] = _summarize_rows([])
        return _write_report(report_dir, report)

    executor = AgentExecutor(config)
    rows: list[dict[str, Any]] = []
    for item in ALIAS_PROMPTS:
        result = executor.run(item["prompt"], strategy=ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2, query_id=f"hermes_semantic_alias_{item['id']}")
        rows.append(_build_alias_row(item, result))
    report["rows"] = rows
    report["summary"] = _summarize_rows(rows)
    report["ok"] = bool(rows) and all(row.get("pass") for row in rows)
    return _write_report(report_dir, report)


def _build_alias_row(item: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    trajectory = result.get("trajectory") or {}
    diagnostics = _flatten_diagnostics(trajectory)
    gate = _final_gate_metrics(result)
    alias_events = _alias_events(result)
    row = {
        "prompt_id": item["id"],
        "prompt": item["prompt"],
        "expected": item["expected"],
        "route": diagnostics.get("route") or diagnostics.get("llm_route"),
        "sdk_toolcall_semantic_ir_used": diagnostics.get("sdk_toolcall_semantic_ir_used"),
        "semantic_ir_validation_passed": diagnostics.get("semantic_ir_validation_passed"),
        "semantic_alias_validation_used": diagnostics.get("semantic_alias_validation_used"),
        "semantic_alias_validation_passed": diagnostics.get("semantic_alias_validation_passed"),
        "semantic_alias_count": int(diagnostics.get("semantic_alias_count") or 0),
        "alias_materialized_count": int(diagnostics.get("alias_materialized_count") or diagnostics.get("semantic_alias_materialized_count") or 0),
        "alias_validation_failures": int(diagnostics.get("semantic_alias_validation_failures") or 0),
        "compiled_sql_count": int(diagnostics.get("compiled_sql_count") or 0),
        "compiled_api_count": int(diagnostics.get("compiled_api_count") or 0),
        "compiled_alias_count": int(diagnostics.get("compiled_alias_count") or 0),
        "sql_calls": _count_steps(trajectory, {"sql_query", "sql_call", "sql"}),
        "api_calls": _count_steps(trajectory, {"api_call", "api"}),
        "exact_cache_hits": int(diagnostics.get("exact_pass_cache_hits") or diagnostics.get("cache_hits") or 0),
        "plan_paths": _plan_paths(trajectory),
        "alias_events": alias_events,
        "unsupported_claims": int(gate["unsupported_claims"]),
        "final_semantic_gate_initial_failures": gate["final_semantic_gate_initial_failures"],
        "final_semantic_gate_final_failures": gate["final_semantic_gate_final_failures"],
        "no_tool_fp": item["expected"] != "DIRECT" and _count_steps(trajectory, {"sql_query", "sql_call", "sql"}) == 0 and _count_steps(trajectory, {"api_call", "api"}) == 0,
        "final_answer": result.get("final_answer"),
        "output_dir": result.get("output_dir"),
    }
    row["matches_expectation"] = _matches_alias_expectation(row)
    row["pass"] = bool(
        row["matches_expectation"]
        and row["unsupported_claims"] == 0
        and row["final_semantic_gate_final_failures"] == 0
        and not row["no_tool_fp"]
    )
    return redact_secrets(row)


def _alias_events(result: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for checkpoint in result.get("checkpoints", []) or []:
        if checkpoint.get("checkpoint_id") != "checkpoint_semantic_alias_materialized":
            continue
        output = checkpoint.get("output")
        if isinstance(output, dict):
            events.append(dict(output))
    return events


def _matches_alias_expectation(row: dict[str, Any]) -> bool:
    alias_count = int(row.get("semantic_alias_count") or 0)
    materialized = int(row.get("alias_materialized_count") or 0)
    if row.get("alias_validation_failures"):
        return False
    if alias_count and materialized != alias_count:
        return False
    expected = str(row.get("expected") or "")
    paths = [str(path).upper() for path in row.get("plan_paths") or []]
    if expected in {"NO_STATUS_DATE_ALIAS", "NO_COUNT_LIST_ALIAS"} and alias_count:
        return False
    if expected == "LOCAL_AND_LIVE_NOT_ALIASED":
        if alias_count and any(event.get("alias_source_status") not in {"SUCCESS", "SKIPPED"} for event in row.get("alias_events") or []):
            return False
        return "API" in " ".join(paths) or int(row.get("compiled_api_count") or 0) > 0 or int(row.get("api_calls") or 0) > 0
    return True


def _summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "row_count": len(rows),
        "passed_count": sum(1 for row in rows if row.get("pass")),
        "failed_count": sum(1 for row in rows if not row.get("pass")),
        "semantic_alias_count": sum(int(row.get("semantic_alias_count") or 0) for row in rows),
        "alias_materialized_count": sum(int(row.get("alias_materialized_count") or 0) for row in rows),
        "alias_validation_failures": sum(int(row.get("alias_validation_failures") or 0) for row in rows),
        "compiled_sql_count": sum(int(row.get("compiled_sql_count") or 0) for row in rows),
        "compiled_api_count": sum(int(row.get("compiled_api_count") or 0) for row in rows),
        "compiled_alias_count": sum(int(row.get("compiled_alias_count") or 0) for row in rows),
        "sql_calls": sum(int(row.get("sql_calls") or 0) for row in rows),
        "api_calls": sum(int(row.get("api_calls") or 0) for row in rows),
        "exact_cache_hits": sum(int(row.get("exact_cache_hits") or 0) for row in rows),
        "unsupported_claims": sum(int(row.get("unsupported_claims") or 0) for row in rows),
        "no_tool_fp": sum(1 for row in rows if row.get("no_tool_fp")),
        "final_semantic_gate_final_failures": sum(int(row.get("final_semantic_gate_final_failures") or 0) for row in rows),
    }


def _write_report(report_dir: Path, report: dict[str, Any]) -> dict[str, Any]:
    json_path = report_dir / "semantic_alias_cache.json"
    md_path = report_dir / "semantic_alias_cache.md"
    json_path.write_text(json.dumps(redact_secrets(report), indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_markdown(report), encoding="utf-8")
    return report


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Hermes V2 Semantic Alias Cache Smoke",
        "",
        f"ok: `{report.get('ok')}`",
        f"skipped: `{report.get('skipped')}`",
        f"strategy: `{report.get('strategy')}`",
        "",
        "## Summary",
        "",
    ]
    summary = report.get("summary") or {}
    for key in [
        "row_count",
        "passed_count",
        "failed_count",
        "semantic_alias_count",
        "alias_materialized_count",
        "alias_validation_failures",
        "compiled_sql_count",
        "compiled_api_count",
        "sql_calls",
        "api_calls",
        "exact_cache_hits",
        "unsupported_claims",
        "no_tool_fp",
        "final_semantic_gate_final_failures",
    ]:
        lines.append(f"- {key}: `{summary.get(key)}`")
    lines.extend(["", "## Rows", "", "| Prompt | Pass | Alias | Materialized | SQL | API | Final Gate Failures |", "|---|---:|---:|---:|---:|---:|---:|"])
    for row in report.get("rows") or []:
        lines.append(
            "| {prompt_id} | {pass_} | {alias} | {mat} | {sql} | {api} | {gate} |".format(
                prompt_id=row.get("prompt_id"),
                pass_=row.get("pass"),
                alias=row.get("semantic_alias_count"),
                mat=row.get("alias_materialized_count"),
                sql=row.get("sql_calls"),
                api=row.get("api_calls"),
                gate=row.get("final_semantic_gate_final_failures"),
            )
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    report = run_hermes_v2_semantic_alias_smoke()
    print(json.dumps(redact_secrets(report.get("summary") or {}), indent=2, sort_keys=True, default=str))
    return 0 if report.get("ok") or report.get("skipped") else 1


if __name__ == "__main__":
    raise SystemExit(main())
