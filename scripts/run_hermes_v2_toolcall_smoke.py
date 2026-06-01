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


REPORT_DIR = ROOT / "outputs" / "reports" / "hermes_v2_toolcall_smoke"
SMOKE_PROMPTS = [
    {"id": "pure_concept_schema", "prompt": "What is a schema?", "expected": "DIRECT"},
    {"id": "pure_meta_list_schemas", "prompt": 'In the phrase "list schemas", what does "list" mean?', "expected": "DIRECT"},
    {"id": "ambiguous_user_schemas", "prompt": "What schemas do I have?", "expected": "EVIDENCE"},
    {"id": "local_schema_count", "prompt": "How many schema records are in the local snapshot?", "expected": "EVIDENCE_SQL"},
    {"id": "birthday_message_published", "prompt": 'When was the journey "Birthday Message" published?', "expected": "EVIDENCE"},
    {"id": "mixed_inactive_journeys", "prompt": "Explain what inactive journey means and show inactive journeys.", "expected": "EVIDENCE"},
    {
        "id": "compare_local_live_birthday_status",
        "prompt": "Compare local and live status of Birthday Message if both are available.",
        "expected": "EVIDENCE_LIVE_IF_AVAILABLE",
    },
]


def run_hermes_v2_toolcall_smoke(config: Config | None = None, *, report_dir: Path | None = None) -> dict[str, Any]:
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
    for item in SMOKE_PROMPTS:
        result = executor.run(item["prompt"], strategy=ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2, query_id=f"hermes_toolcall_{item['id']}")
        trajectory = result.get("trajectory") or {}
        diagnostics = _flatten_diagnostics(trajectory)
        sql_calls = _count_steps(trajectory, {"sql_query", "sql_call", "sql"})
        api_calls = _count_steps(trajectory, {"api_call", "api"})
        row = {
            "prompt_id": item["id"],
            "prompt": item["prompt"],
            "expected": item["expected"],
            "route": diagnostics.get("route") or diagnostics.get("route_gate_route") or diagnostics.get("checklist_route"),
            "sdk_toolcall_semantic_ir_used": diagnostics.get("sdk_toolcall_semantic_ir_used"),
            "semantic_ir_validation_passed": diagnostics.get("semantic_ir_validation_passed"),
            "semantic_ir_repair_attempted": diagnostics.get("semantic_ir_repair_attempted"),
            "backend_formal_compilation_used": diagnostics.get("backend_formal_compilation_used"),
            "atomic_protocol_fallback_used": diagnostics.get("atomic_protocol_fallback_used"),
            "task_count": diagnostics.get("semantic_ir_task_count"),
            "compiled_sql_count": int(diagnostics.get("compiled_sql_count") or 0),
            "compiled_api_count": int(diagnostics.get("compiled_api_count") or 0),
            "sql_calls": sql_calls,
            "api_calls": api_calls,
            "runtime_fact_count": int(diagnostics.get("runtime_fact_count") or diagnostics.get("evidence_bus_fact_count") or 0),
            "unsupported_claims": int(diagnostics.get("unsupported_claims") or 0),
            "final_answer": result.get("final_answer"),
            "output_dir": result.get("output_dir"),
            "matches_expectation": _matches_expectation(item["expected"], sql_calls, api_calls, diagnostics),
        }
        rows.append(row)
    report["rows"] = rows
    report["summary"] = _summarize_rows(rows)
    report["ok"] = bool(rows) and all(row.get("matches_expectation") for row in rows) and report["summary"].get("unsupported_claims", 0) == 0
    return _write_report(report_dir, report)


def _flatten_diagnostics(trajectory: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key not in merged and isinstance(item, (str, int, float, bool, type(None))):
                    merged[key] = item
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(trajectory)
    return merged


def _count_steps(trajectory: dict[str, Any], kinds: set[str]) -> int:
    count = 0
    for step in trajectory.get("steps", []) or []:
        kind = str(step.get("kind") or step.get("action") or "").lower()
        if kind in kinds:
            count += 1
    return count


def _matches_expectation(expected: str, sql_calls: int, api_calls: int, diagnostics: dict[str, Any]) -> bool:
    if expected == "DIRECT":
        return sql_calls == 0 and api_calls == 0 and diagnostics.get("sdk_toolcall_semantic_ir_used") is True and not diagnostics.get("atomic_protocol_fallback_used")
    if expected == "EVIDENCE_SQL":
        return sql_calls > 0 and diagnostics.get("sdk_toolcall_semantic_ir_used") is True and not diagnostics.get("atomic_protocol_fallback_used")
    return (sql_calls + api_calls) > 0 and diagnostics.get("sdk_toolcall_semantic_ir_used") is True and not diagnostics.get("atomic_protocol_fallback_used")


def _summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "row_count": len(rows),
        "passed_count": sum(1 for row in rows if row.get("matches_expectation")),
        "failed_count": sum(1 for row in rows if not row.get("matches_expectation")),
        "sql_calls": sum(int(row.get("sql_calls") or 0) for row in rows),
        "api_calls": sum(int(row.get("api_calls") or 0) for row in rows),
        "compiled_sql_count": sum(int(row.get("compiled_sql_count") or 0) for row in rows),
        "compiled_api_count": sum(int(row.get("compiled_api_count") or 0) for row in rows),
        "unsupported_claims": sum(int(row.get("unsupported_claims") or 0) for row in rows),
        "atomic_protocol_fallback_count": sum(1 for row in rows if row.get("atomic_protocol_fallback_used")),
    }


def _write_report(report_dir: Path, report: dict[str, Any]) -> dict[str, Any]:
    safe_report = redact_secrets(report)
    json_path = report_dir / "hermes_v2_toolcall_smoke.json"
    md_path = report_dir / "hermes_v2_toolcall_smoke.md"
    json_path.write_text(json.dumps(safe_report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_markdown(safe_report), encoding="utf-8")
    safe_report["json_path"] = str(json_path)
    safe_report["md_path"] = str(md_path)
    return safe_report


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Hermes V2 Toolcall Smoke",
        "",
        f"- ok: `{report.get('ok')}`",
        f"- skipped: `{report.get('skipped')}`",
        f"- skip_reason: `{report.get('skip_reason')}`",
        f"- strategy: `{report.get('strategy')}`",
        f"- provider: `{(report.get('probe') or {}).get('provider')}`",
        f"- model: `{(report.get('probe') or {}).get('model')}`",
        f"- sdk_path_used: `{(report.get('probe') or {}).get('sdk_path_used')}`",
        f"- toolcall_supported: `{(report.get('probe') or {}).get('toolcall_supported')}`",
        "",
        "## Rows",
        "",
        "| Prompt | SQL | API | Semantic IR | Atomic Fallback | Compiled SQL | Compiled API | Expected | Pass |",
        "|---|---:|---:|---|---|---:|---:|---|---|",
    ]
    for row in report.get("rows") or []:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row.get("prompt_id")),
                    str(row.get("sql_calls")),
                    str(row.get("api_calls")),
                    str(row.get("sdk_toolcall_semantic_ir_used")),
                    str(row.get("atomic_protocol_fallback_used")),
                    str(row.get("compiled_sql_count")),
                    str(row.get("compiled_api_count")),
                    str(row.get("expected")),
                    str(row.get("matches_expectation")),
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    report = run_hermes_v2_toolcall_smoke()
    print(json.dumps({"ok": report.get("ok"), "skipped": report.get("skipped"), "json": report.get("json_path"), "md": report.get("md_path")}, indent=2))
    return 0 if report.get("ok") or report.get("skipped") else 1


if __name__ == "__main__":
    raise SystemExit(main())
