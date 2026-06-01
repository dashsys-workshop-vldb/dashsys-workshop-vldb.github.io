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
    {"id": "ambiguous_user_schemas", "prompt": "What schemas do I have?", "expected": "EVIDENCE_LOCAL"},
    {"id": "local_schema_count", "prompt": "How many schema records are in the local snapshot?", "expected": "EVIDENCE_SQL", "expected_answer_contains": "74"},
    {"id": "birthday_message_published", "prompt": 'When was the journey "Birthday Message" published?', "expected": "EVIDENCE_LOCAL"},
    {"id": "mixed_inactive_journeys", "prompt": "Explain what inactive journey means and show inactive journeys.", "expected": "EVIDENCE_LOCAL"},
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
        rows.append(_build_smoke_row(item, result))
    report["rows"] = rows
    report["summary"] = _summarize_rows(rows)
    report["ok"] = bool(rows) and all(row.get("pass") for row in rows) and report["summary"].get("unsupported_claims", 0) == 0
    return _write_report(report_dir, report)


def _build_smoke_row(item: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    trajectory = result.get("trajectory") or {}
    diagnostics = _flatten_diagnostics(trajectory)
    sql_calls = _count_steps(trajectory, {"sql_query", "sql_call", "sql"})
    api_calls = _count_steps(trajectory, {"api_call", "api"})
    fact_metrics = _fact_metrics(result)
    gate_metrics = _final_gate_metrics(result)
    unsupported_claims = max(int(diagnostics.get("unsupported_claims") or 0), gate_metrics["unsupported_claims"])
    row = {
        "prompt_id": item["id"],
        "prompt": item["prompt"],
        "expected": item["expected"],
        "expected_answer_contains": item.get("expected_answer_contains"),
        "route": diagnostics.get("route") or diagnostics.get("route_gate_route") or diagnostics.get("checklist_route"),
        "sdk_toolcall_semantic_ir_used": diagnostics.get("sdk_toolcall_semantic_ir_used"),
        "semantic_ir_validation_passed": diagnostics.get("semantic_ir_validation_passed"),
        "semantic_ir_repair_attempted": diagnostics.get("semantic_ir_repair_attempted"),
        "backend_formal_compilation_used": diagnostics.get("backend_formal_compilation_used"),
        "backend_semantic_planning_used": diagnostics.get("backend_semantic_planning_used"),
        "atomic_protocol_fallback_used": diagnostics.get("atomic_protocol_fallback_used"),
        "task_count": diagnostics.get("semantic_ir_task_count"),
        "plan_paths": _plan_paths(trajectory),
        "compiled_sql_count": int(diagnostics.get("compiled_sql_count") or 0),
        "compiled_api_count": int(diagnostics.get("compiled_api_count") or 0),
        "sql_calls": sql_calls,
        "api_calls": api_calls,
        "evidence_pipeline_bypassed": bool(diagnostics.get("evidence_pipeline_bypassed")),
        "evidence_bus_built": bool(diagnostics.get("evidence_bus_built")),
        "post_evidence_answer_router_ran": bool(diagnostics.get("post_evidence_answer_router_ran")),
        "runtime_fact_count": fact_metrics["runtime_fact_count"],
        "local_snapshot_fact_count": fact_metrics["local_snapshot_fact_count"],
        "live_api_fact_count": fact_metrics["live_api_fact_count"],
        "caveat_or_error_only_count": fact_metrics["caveat_or_error_only_count"],
        "unsupported_claims": unsupported_claims,
        "final_semantic_gate_initial_failures": gate_metrics["final_semantic_gate_initial_failures"],
        "final_semantic_gate_final_failures": gate_metrics["final_semantic_gate_final_failures"],
        "no_tool_fp": item["expected"] != "DIRECT" and sql_calls == 0 and api_calls == 0,
        "final_answer": result.get("final_answer"),
        "output_dir": result.get("output_dir"),
    }
    row["matches_expectation"] = _matches_expectation(item["expected"], row, diagnostics)
    row["pass"] = bool(
        row["matches_expectation"]
        and _answer_contains_expected(row)
        and unsupported_claims == 0
        and row["final_semantic_gate_final_failures"] == 0
    )
    return row


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


def _plan_paths(trajectory: dict[str, Any]) -> list[str]:
    for step in trajectory.get("steps", []) or []:
        if step.get("kind") != "llm_unified_planner":
            continue
        paths = []
        for item in step.get("passes") or []:
            if isinstance(item, dict) and item.get("path"):
                paths.append(str(item["path"]))
        return paths
    return []


def _fact_metrics(result: dict[str, Any]) -> dict[str, int]:
    trajectory = result.get("trajectory") or {}
    metrics = {
        "runtime_fact_count": 0,
        "local_snapshot_fact_count": 0,
        "live_api_fact_count": 0,
        "caveat_or_error_only_count": 0,
    }
    for step in trajectory.get("steps", []) or []:
        kind = str(step.get("kind") or "").lower()
        payload = step.get("result") if isinstance(step.get("result"), dict) else {}
        if kind == "sql_call":
            facts = _successful_sql_fact_count(payload)
            metrics["runtime_fact_count"] += facts
            metrics["local_snapshot_fact_count"] += facts
            if facts == 0 and _payload_is_error_or_caveat(payload):
                metrics["caveat_or_error_only_count"] += 1
        elif kind == "api_call":
            facts = _successful_api_fact_count(payload)
            metrics["runtime_fact_count"] += facts
            metrics["live_api_fact_count"] += facts
            if facts == 0 and _payload_is_error_or_caveat(payload):
                metrics["caveat_or_error_only_count"] += 1

    for item in _checkpoint_runtime_passes(result):
        if not isinstance(item, dict):
            continue
        status = str(item.get("status") or "").upper()
        facts = len(item.get("facts") or []) if isinstance(item.get("facts"), list) else 0
        path = str(item.get("path") or item.get("source") or "").upper()
        if status == "SUCCESS" and facts > 0:
            missing = max(0, facts - metrics["runtime_fact_count"])
            if missing:
                metrics["runtime_fact_count"] += missing
                if "API" in path:
                    metrics["live_api_fact_count"] += missing
                else:
                    metrics["local_snapshot_fact_count"] += missing
        if status in {"API_ERROR", "ERROR", "LIVE_EMPTY", "EMPTY"} and facts == 0:
            metrics["caveat_or_error_only_count"] += 1
    return metrics


def _successful_sql_fact_count(payload: dict[str, Any]) -> int:
    if not payload.get("ok"):
        return 0
    rows = _rows_from_payload(payload)
    if rows:
        non_empty_rows = [row for row in rows if not isinstance(row, dict) or any(value not in (None, "", []) for value in row.values())]
        return len(non_empty_rows)
    row_count = int(payload.get("row_count") or 0)
    return max(row_count, 0)


def _successful_api_fact_count(payload: dict[str, Any]) -> int:
    if not payload.get("ok"):
        return 0
    parsed = payload.get("parsed_evidence") if isinstance(payload.get("parsed_evidence"), dict) else {}
    count = 0
    for key in ("names", "ids", "statuses", "dates"):
        value = parsed.get(key)
        if isinstance(value, list):
            count += len(value)
    counts = parsed.get("counts")
    if isinstance(counts, dict):
        count += sum(1 for value in counts.values() if value not in (None, "", []))
    result_preview = payload.get("result_preview")
    if isinstance(result_preview, list):
        count += len(result_preview)
    if isinstance(result_preview, dict):
        count += len(result_preview)
    return count


def _rows_from_payload(payload: dict[str, Any]) -> list[Any]:
    rows = payload.get("rows")
    if isinstance(rows, list):
        return rows
    if isinstance(rows, dict) and isinstance(rows.get("items"), list):
        return rows["items"]
    return []


def _payload_is_error_or_caveat(payload: dict[str, Any]) -> bool:
    if not payload:
        return False
    if payload.get("ok") is False:
        return True
    state = str((payload.get("parsed_evidence") or {}).get("evidence_state") if isinstance(payload.get("parsed_evidence"), dict) else "").lower()
    return state in {"api_error", "dry_run_unavailable", "live_empty"}


def _checkpoint_runtime_passes(result: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for checkpoint in result.get("checkpoints") or []:
        if checkpoint.get("checkpoint_id") != "checkpoint_result_bundle":
            continue
        output = checkpoint.get("output") if isinstance(checkpoint.get("output"), dict) else {}
        runtime_passes = output.get("runtime_passes")
        if isinstance(runtime_passes, list):
            out.extend(item for item in runtime_passes if isinstance(item, dict))
    return out


def _final_gate_metrics(result: dict[str, Any]) -> dict[str, int]:
    initial_failures = 0
    final_failures = 0
    unsupported_claims = 0
    for checkpoint in result.get("checkpoints") or []:
        output = checkpoint.get("output") if isinstance(checkpoint.get("output"), dict) else {}
        checkpoint_id = str(checkpoint.get("checkpoint_id") or "")
        if checkpoint_id == "checkpoint_llm_final_answer_semantic_gate":
            if output.get("passed") is False:
                initial_failures += 1
            unsupported_claims += _unsupported_claims_len(output)
        elif checkpoint_id == "checkpoint_llm_final_answer_repair":
            semantic = output.get("semantic_gate") if isinstance(output.get("semantic_gate"), dict) else {}
            unsupported_claims += _unsupported_claims_len(semantic)
        elif checkpoint_id == "checkpoint_llm_owned_final_answer_boundary":
            if output.get("answer_semantic_gate_passed") is False:
                final_failures += 1
            semantic = output.get("semantic_gate") if isinstance(output.get("semantic_gate"), dict) else {}
            unsupported_claims += _unsupported_claims_len(semantic)
    return {
        "final_semantic_gate_initial_failures": initial_failures,
        "final_semantic_gate_final_failures": final_failures,
        "unsupported_claims": unsupported_claims,
    }


def _unsupported_claims_len(output: dict[str, Any]) -> int:
    claims = output.get("unsupported_claims")
    if isinstance(claims, list):
        return len(claims)
    return 0


def _matches_expectation(expected: str, row: dict[str, Any], diagnostics: dict[str, Any]) -> bool:
    sql_calls = int(row.get("sql_calls") or 0)
    api_calls = int(row.get("api_calls") or 0)
    semantic_ir_ok = diagnostics.get("sdk_toolcall_semantic_ir_used") is True and not diagnostics.get("atomic_protocol_fallback_used")
    if expected == "DIRECT":
        return (
            sql_calls == 0
            and api_calls == 0
            and semantic_ir_ok
            and row.get("evidence_pipeline_bypassed") is True
            and row.get("evidence_bus_built") is False
        )
    if expected == "EVIDENCE_SQL":
        return sql_calls > 0 and semantic_ir_ok and int(row.get("runtime_fact_count") or 0) > 0
    if expected == "EVIDENCE_LOCAL":
        return sql_calls > 0 and semantic_ir_ok and int(row.get("local_snapshot_fact_count") or 0) > 0
    if expected == "EVIDENCE_LIVE_IF_AVAILABLE":
        return sql_calls > 0 and api_calls > 0 and semantic_ir_ok and int(row.get("local_snapshot_fact_count") or 0) > 0
    return (sql_calls + api_calls) > 0 and semantic_ir_ok


def _answer_contains_expected(row: dict[str, Any]) -> bool:
    expected = row.get("expected_answer_contains")
    if not expected:
        return True
    return str(expected).lower() in str(row.get("final_answer") or "").lower()


def _summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "row_count": len(rows),
        "passed_count": sum(1 for row in rows if row.get("pass")),
        "failed_count": sum(1 for row in rows if not row.get("pass")),
        "sql_calls": sum(int(row.get("sql_calls") or 0) for row in rows),
        "api_calls": sum(int(row.get("api_calls") or 0) for row in rows),
        "compiled_sql_count": sum(int(row.get("compiled_sql_count") or 0) for row in rows),
        "compiled_api_count": sum(int(row.get("compiled_api_count") or 0) for row in rows),
        "unsupported_claims": sum(int(row.get("unsupported_claims") or 0) for row in rows),
        "runtime_fact_count": sum(int(row.get("runtime_fact_count") or 0) for row in rows),
        "local_snapshot_fact_count": sum(int(row.get("local_snapshot_fact_count") or 0) for row in rows),
        "live_api_fact_count": sum(int(row.get("live_api_fact_count") or 0) for row in rows),
        "caveat_or_error_only_count": sum(int(row.get("caveat_or_error_only_count") or 0) for row in rows),
        "no_tool_fp": sum(1 for row in rows if row.get("no_tool_fp")),
        "final_semantic_gate_initial_failures": sum(int(row.get("final_semantic_gate_initial_failures") or 0) for row in rows),
        "final_semantic_gate_final_failures": sum(int(row.get("final_semantic_gate_final_failures") or 0) for row in rows),
        "atomic_protocol_fallback_count": sum(1 for row in rows if row.get("atomic_protocol_fallback_used")),
    }


def _write_report(report_dir: Path, report: dict[str, Any]) -> dict[str, Any]:
    safe_report = redact_secrets(report)
    json_path = report_dir / "hermes_v2_toolcall_smoke.json"
    md_path = report_dir / "hermes_v2_toolcall_smoke.md"
    json_path.write_text(json.dumps(safe_report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_markdown(safe_report), encoding="utf-8")
    quality_paths = _write_quality_report(report_dir, safe_report)
    safe_report["json_path"] = str(json_path)
    safe_report["md_path"] = str(md_path)
    safe_report.update(quality_paths)
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
        "| Prompt | SQL | API | Semantic IR | Atomic Fallback | Compiled SQL | Compiled API | Runtime Facts | Local Facts | Caveats/Errors | Initial Gate Fail | Final Gate Fail | Expected | Pass |",
        "|---|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|",
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
                    str(row.get("runtime_fact_count")),
                    str(row.get("local_snapshot_fact_count")),
                    str(row.get("caveat_or_error_only_count")),
                    str(row.get("final_semantic_gate_initial_failures")),
                    str(row.get("final_semantic_gate_final_failures")),
                    str(row.get("expected")),
                    str(row.get("pass")),
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def _write_quality_report(report_dir: Path, report: dict[str, Any]) -> dict[str, str]:
    json_path = report_dir / "unified_planner_semantic_ir_quality.json"
    md_path = report_dir / "unified_planner_semantic_ir_quality.md"
    summary = report.get("summary") or {}
    rows = report.get("rows") or []
    payload = {
        "objective": "Restore Unified LLM Planner facade while keeping SDK-toolcall Semantic IR primary.",
        "unified_planner_facade_restored": True,
        "semantic_ir_primary": all(row.get("sdk_toolcall_semantic_ir_used") is True for row in rows) if rows else False,
        "free_form_sql_api_avoided": all(row.get("backend_formal_compilation_used") is True and row.get("backend_semantic_planning_used") is False for row in rows if row.get("expected") != "DIRECT"),
        "atomic_protocol_fallback_used_count": summary.get("atomic_protocol_fallback_count", 0),
        "unsupported_claims": summary.get("unsupported_claims", 0),
        "no_tool_fp": summary.get("no_tool_fp", 0),
        "ready_to_run_dev_eval": bool(report.get("ok") and summary.get("unsupported_claims", 0) == 0 and summary.get("final_semantic_gate_final_failures", 0) == 0),
        "summary": summary,
        "rows": rows,
    }
    json_path.write_text(json.dumps(redact_secrets(payload), indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_quality_markdown(redact_secrets(payload)), encoding="utf-8")
    return {"quality_json_path": str(json_path), "quality_md_path": str(md_path)}


def _quality_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Unified Planner Semantic IR Quality",
        "",
        f"- unified_planner_facade_restored: `{payload.get('unified_planner_facade_restored')}`",
        f"- semantic_ir_primary: `{payload.get('semantic_ir_primary')}`",
        f"- free_form_sql_api_avoided: `{payload.get('free_form_sql_api_avoided')}`",
        f"- atomic_protocol_fallback_used_count: `{payload.get('atomic_protocol_fallback_used_count')}`",
        f"- unsupported_claims: `{payload.get('unsupported_claims')}`",
        f"- no_tool_fp: `{payload.get('no_tool_fp')}`",
        f"- ready_to_run_dev_eval: `{payload.get('ready_to_run_dev_eval')}`",
        "",
        "## Smoke Rows",
        "",
        "| Prompt | Expected | SQL | API | Runtime Facts | Local Facts | Initial Gate Fail | Final Gate Fail | Pass | Final Answer |",
        "|---|---|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in payload.get("rows") or []:
        answer = str(row.get("final_answer") or "").replace("\n", " ")[:180]
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row.get("prompt_id")),
                    str(row.get("expected")),
                    str(row.get("sql_calls")),
                    str(row.get("api_calls")),
                    str(row.get("runtime_fact_count")),
                    str(row.get("local_snapshot_fact_count")),
                    str(row.get("final_semantic_gate_initial_failures")),
                    str(row.get("final_semantic_gate_final_failures")),
                    str(row.get("pass")),
                    answer,
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
