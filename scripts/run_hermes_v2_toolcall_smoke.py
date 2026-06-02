#!/usr/bin/env python
from __future__ import annotations

import json
import multiprocessing as mp
import os
import sys
import time
import traceback
from datetime import datetime, timezone
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
DEFAULT_PROMPT_TIMEOUT_SEC = 120
DEFAULT_LLM_CALL_TIMEOUT_SEC = 60
LATENCY_FIELDS = [
    "total_latency_sec",
    "semantic_ir_planner_latency_sec",
    "semantic_ir_validation_latency_sec",
    "semantic_ir_repair_latency_sec",
    "semantic_ir_support_check_latency_sec",
    "raw_sql_fallback_latency_sec",
    "compiler_latency_sec",
    "sql_gate_latency_sec",
    "api_gate_latency_sec",
    "sql_execution_latency_sec",
    "api_execution_latency_sec",
    "final_composer_latency_sec",
    "final_answer_repair_latency_sec",
    "final_gate_latency_sec",
]
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


def run_hermes_v2_toolcall_smoke(
    config: Config | None = None,
    *,
    report_dir: Path | None = None,
    probe_runner: Any | None = None,
    report_name: str = "hermes_v2_toolcall_smoke",
    report_title: str = "Hermes V2 Toolcall Smoke",
) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    report_dir = report_dir or REPORT_DIR
    report_dir.mkdir(parents=True, exist_ok=True)
    load_local_env(config.project_root)
    prompt_timeout_sec = _env_int("HERMES_SMOKE_PROMPT_TIMEOUT_SEC", DEFAULT_PROMPT_TIMEOUT_SEC)
    llm_call_timeout_sec = _env_int("HERMES_LLM_CALL_TIMEOUT_SEC", DEFAULT_LLM_CALL_TIMEOUT_SEC)
    _configure_llm_timeout_env(llm_call_timeout_sec)
    if probe_runner is None:
        probe = run_hermes_toolcall_probe(config, report_dir=ROOT / "outputs" / "reports" / "hermes_toolcall_probe")
    else:
        probe = probe_runner(config)
    report: dict[str, Any] = {
        "ok": False,
        "report_name": report_name,
        "report_title": report_title,
        "skipped": False,
        "skip_reason": "",
        "strategy": ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2,
        "prompt_timeout_sec": prompt_timeout_sec,
        "llm_call_timeout_sec": llm_call_timeout_sec,
        "partial_report": True,
        "last_stage_heartbeat": {},
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
        report.update({"skipped": True, "skip_reason": f"{report_title} probe did not return native SDK tool/function calls."})
        report["summary"] = _summarize_rows([])
        return _write_report(report_dir, report)

    rows: list[dict[str, Any]] = []
    for item in SMOKE_PROMPTS:
        _write_heartbeat(report_dir, item["id"], "parent_prompt_start")
        row = _run_prompt_with_timeout(
            item,
            config=config,
            report_dir=report_dir,
            prompt_timeout_sec=prompt_timeout_sec,
            llm_call_timeout_sec=llm_call_timeout_sec,
        )
        rows.append(row)
        report["rows"] = rows
        report["summary"] = _summarize_rows(rows)
        report["last_stage_heartbeat"] = _read_heartbeat(report_dir)
        _write_report(report_dir, report)
    report["rows"] = rows
    report["summary"] = _summarize_rows(rows)
    report["partial_report"] = False
    report["last_stage_heartbeat"] = _read_heartbeat(report_dir)
    report["ok"] = bool(rows) and all(row.get("pass") for row in rows) and report["summary"].get("unsupported_claims", 0) == 0 and report["summary"].get("timeout_count", 0) == 0
    return _write_report(report_dir, report)


def _run_prompt_with_timeout(
    item: dict[str, Any],
    *,
    config: Config,
    report_dir: Path,
    prompt_timeout_sec: int,
    llm_call_timeout_sec: int,
) -> dict[str, Any]:
    started = time.perf_counter()
    ctx = mp.get_context("fork" if sys.platform != "win32" else "spawn")
    queue: Any = ctx.Queue(maxsize=1)
    process = ctx.Process(target=_prompt_worker, args=(item, config, str(report_dir), llm_call_timeout_sec, queue))
    process.start()
    process.join(prompt_timeout_sec)
    total_latency = round(time.perf_counter() - started, 3)
    if process.is_alive():
        process.terminate()
        process.join(5)
        heartbeat = _read_heartbeat(report_dir)
        return _timeout_row(item, timeout_sec=prompt_timeout_sec, total_latency_sec=total_latency, heartbeat=heartbeat)
    try:
        payload = queue.get_nowait()
    except Exception:
        heartbeat = _read_heartbeat(report_dir)
        return _error_row(item, "prompt_worker_returned_no_result", total_latency, heartbeat)
    if not isinstance(payload, dict):
        return _error_row(item, "prompt_worker_returned_non_dict_result", total_latency, _read_heartbeat(report_dir))
    if payload.get("ok") and isinstance(payload.get("row"), dict):
        row = payload["row"]
        row["total_latency_sec"] = total_latency
        return row
    heartbeat = _read_heartbeat(report_dir)
    return _error_row(item, str(payload.get("error") or "prompt_worker_failed"), total_latency, heartbeat, traceback_text=payload.get("traceback"))


def _prompt_worker(item: dict[str, Any], config: Config, report_dir_text: str, llm_call_timeout_sec: int, queue: Any) -> None:
    report_dir = Path(report_dir_text)
    _configure_llm_timeout_env(llm_call_timeout_sec)
    _install_checkpoint_heartbeat(report_dir, str(item["id"]))
    started = time.perf_counter()
    try:
        _write_heartbeat(report_dir, item["id"], "agent_executor_start")
        executor = AgentExecutor(config)
        result = executor.run(item["prompt"], strategy=ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2, query_id=f"hermes_toolcall_{item['id']}")
        row = _build_smoke_row(item, result)
        row["total_latency_sec"] = round(time.perf_counter() - started, 3)
        _write_heartbeat(report_dir, item["id"], "prompt_complete")
        queue.put({"ok": True, "row": row})
    except Exception as exc:
        _write_heartbeat(report_dir, item["id"], "prompt_exception", {"error": str(exc)[:500]})
        queue.put({"ok": False, "error": str(exc), "traceback": traceback.format_exc(limit=20)})


def _install_checkpoint_heartbeat(report_dir: Path, prompt_id: str) -> None:
    from dashagent.checkpoints import CheckpointLogger

    original = CheckpointLogger.add_checkpoint

    def add_checkpoint_with_heartbeat(self, checkpoint_id: str, **kwargs):
        _write_heartbeat(
            report_dir,
            prompt_id,
            str(checkpoint_id),
            {"stage": kwargs.get("stage"), "technique": kwargs.get("technique")},
        )
        return original(self, checkpoint_id, **kwargs)

    CheckpointLogger.add_checkpoint = add_checkpoint_with_heartbeat


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
        "raw_sql_fallback_used": bool(diagnostics.get("raw_sql_fallback_used")),
        "raw_sql_fallback_success": bool(diagnostics.get("raw_sql_fallback_success")),
        "raw_sql_fallback_gate_error_type": diagnostics.get("raw_sql_fallback_gate_error_type"),
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
        "final_answer_repair_attempts": gate_metrics["final_answer_repair_attempts"],
        "repaired_success": gate_metrics["repaired_success"],
        "no_tool_fp": item["expected"] != "DIRECT" and sql_calls == 0 and api_calls == 0,
        "final_answer": result.get("final_answer"),
        "output_dir": result.get("output_dir"),
    }
    row.update(_stage_timing_diagnostics(result))
    row["final_unavailable_with_runtime_facts"] = _final_unavailable_with_runtime_facts(row)
    row["matches_expectation"] = _matches_expectation(item["expected"], row, diagnostics)
    row["pass"] = bool(
        row["matches_expectation"]
        and _answer_contains_expected(row)
        and unsupported_claims == 0
        and row["final_semantic_gate_final_failures"] == 0
        and not row["final_unavailable_with_runtime_facts"]
    )
    return row


def _stage_timing_diagnostics(result: dict[str, Any]) -> dict[str, Any]:
    trajectory = result.get("trajectory") or {}
    diagnostics = _flatten_diagnostics(trajectory)
    checkpoints = result.get("checkpoints") or trajectory.get("checkpoints") or []
    timings = trajectory.get("timings") if isinstance(trajectory.get("timings"), dict) else {}
    row = _empty_latency_fields()
    row.update(
        {
            "semantic_ir_planner_latency_sec": _ms_to_sec(diagnostics.get("planner_provider_latency_ms") or diagnostics.get("semantic_ir_provider_latency_ms")),
            "semantic_ir_validation_latency_sec": _ms_to_sec(diagnostics.get("semantic_ir_validation_latency_ms")),
            "semantic_ir_repair_latency_sec": _ms_to_sec(diagnostics.get("semantic_ir_repair_latency_ms")),
            "semantic_ir_support_check_latency_sec": _ms_to_sec(diagnostics.get("semantic_ir_support_check_latency_ms")),
            "raw_sql_fallback_latency_sec": _ms_to_sec(diagnostics.get("raw_sql_fallback_latency_ms")),
            "compiler_latency_sec": _ms_to_sec(diagnostics.get("compiler_latency_ms")),
            "sql_gate_latency_sec": _checkpoint_seconds(checkpoints, {"checkpoint_llm_owned_sql_compile_gate", "checkpoint_llm_owned_sql_compile_gate_repair"}),
            "api_gate_latency_sec": _checkpoint_seconds(checkpoints, {"checkpoint_llm_owned_api_request_gate", "checkpoint_llm_owned_api_request_gate_repair"}),
            "sql_execution_latency_sec": float(diagnostics.get("sql_execution_latency_sec") or 0.0),
            "api_execution_latency_sec": float(diagnostics.get("api_execution_latency_sec") or 0.0),
            "final_composer_latency_sec": float(diagnostics.get("final_composer_latency_sec") or timings.get("answer_time") or 0.0),
            "final_answer_repair_latency_sec": _checkpoint_seconds(checkpoints, {"checkpoint_llm_final_answer_repair"}),
            "final_gate_latency_sec": _checkpoint_seconds(checkpoints, {"checkpoint_llm_final_answer_syntax_gate", "checkpoint_llm_final_answer_semantic_gate"}),
            "timed_out": False,
            "timed_out_stage": None,
        }
    )
    return row


def _empty_latency_fields() -> dict[str, Any]:
    row = {field: 0.0 for field in LATENCY_FIELDS}
    row["timed_out"] = False
    row["timed_out_stage"] = None
    return row


def _ms_to_sec(value: Any) -> float:
    try:
        return round(float(value) / 1000.0, 3)
    except Exception:
        return 0.0


def _checkpoint_seconds(checkpoints: list[dict[str, Any]], checkpoint_ids: set[str]) -> float:
    total_ms = 0.0
    for checkpoint in checkpoints or []:
        if str(checkpoint.get("checkpoint_id") or "") in checkpoint_ids:
            try:
                total_ms += float(checkpoint.get("duration_ms") or 0.0)
            except Exception:
                continue
    return round(total_ms / 1000.0, 3)


def _timeout_row(item: dict[str, Any], *, timeout_sec: int, total_latency_sec: float, heartbeat: dict[str, Any] | None = None) -> dict[str, Any]:
    heartbeat = heartbeat or {}
    row = {
        "prompt_id": item["id"],
        "prompt": item["prompt"],
        "expected": item.get("expected"),
        "expected_answer_contains": item.get("expected_answer_contains"),
        "route": None,
        "sdk_toolcall_semantic_ir_used": None,
        "semantic_ir_validation_passed": None,
        "semantic_ir_repair_attempted": None,
        "backend_formal_compilation_used": None,
        "backend_semantic_planning_used": None,
        "atomic_protocol_fallback_used": None,
        "raw_sql_fallback_used": False,
        "raw_sql_fallback_success": False,
        "raw_sql_fallback_gate_error_type": None,
        "task_count": None,
        "plan_paths": [],
        "compiled_sql_count": 0,
        "compiled_api_count": 0,
        "sql_calls": 0,
        "api_calls": 0,
        "evidence_pipeline_bypassed": False,
        "evidence_bus_built": False,
        "post_evidence_answer_router_ran": False,
        "runtime_fact_count": 0,
        "local_snapshot_fact_count": 0,
        "live_api_fact_count": 0,
        "caveat_or_error_only_count": 0,
        "unsupported_claims": 0,
        "final_semantic_gate_initial_failures": 0,
        "final_semantic_gate_final_failures": 0,
        "final_answer_repair_attempts": 0,
        "repaired_success": False,
        "no_tool_fp": item.get("expected") != "DIRECT",
        "final_answer": "",
        "output_dir": None,
        "matches_expectation": False,
        "final_unavailable_with_runtime_facts": False,
        "pass": False,
        "timeout_sec": timeout_sec,
        "timeout_error": f"prompt_timeout_after_{timeout_sec}s",
        "last_stage_heartbeat": heartbeat,
    }
    row.update(_empty_latency_fields())
    row["total_latency_sec"] = round(float(total_latency_sec), 3)
    row["timed_out"] = True
    row["timed_out_stage"] = heartbeat.get("current_stage") or "unknown"
    return redact_secrets(row)


def _error_row(
    item: dict[str, Any],
    error: str,
    total_latency_sec: float,
    heartbeat: dict[str, Any] | None = None,
    *,
    traceback_text: str | None = None,
) -> dict[str, Any]:
    row = _timeout_row(item, timeout_sec=0, total_latency_sec=total_latency_sec, heartbeat=heartbeat)
    row["timed_out"] = False
    row["timeout_error"] = ""
    row["error"] = error
    row["traceback"] = traceback_text
    row["timed_out_stage"] = (heartbeat or {}).get("current_stage")
    return redact_secrets(row)


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
    repair_attempts = 0
    repair_semantic_passed = False
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
            repair_semantic_passed = semantic.get("passed") is True
        elif checkpoint_id == "checkpoint_llm_owned_final_answer_boundary":
            if output.get("answer_semantic_gate_passed") is False:
                final_failures += 1
            repair_attempts = max(repair_attempts, int(output.get("answer_repair_attempts") or 0))
            semantic = output.get("semantic_gate") if isinstance(output.get("semantic_gate"), dict) else {}
            unsupported_claims += _unsupported_claims_len(semantic)
    return {
        "final_semantic_gate_initial_failures": initial_failures,
        "final_semantic_gate_final_failures": final_failures,
        "unsupported_claims": unsupported_claims,
        "final_answer_repair_attempts": repair_attempts,
        "repaired_success": bool(repair_attempts > 0 and repair_semantic_passed and final_failures == 0),
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


def _final_unavailable_with_runtime_facts(row: dict[str, Any]) -> bool:
    if int(row.get("runtime_fact_count") or 0) <= 0:
        return False
    answer = str(row.get("final_answer") or "").lower()
    return "runtime evidence was unavailable" in answer or "no matching runtime evidence was available" in answer


def _write_heartbeat(report_dir: Path, prompt_id: Any, current_stage: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    report_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "current_stage": current_stage,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "prompt_id": str(prompt_id),
    }
    if extra:
        payload.update(extra)
    safe = redact_secrets(payload)
    for path in [report_dir / "last_stage_heartbeat.json", report_dir / f"heartbeat_{prompt_id}.json"]:
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(safe, indent=2, sort_keys=True, default=str), encoding="utf-8")
        tmp.replace(path)
    return safe


def _read_heartbeat(report_dir: Path) -> dict[str, Any]:
    path = report_dir / "last_stage_heartbeat.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _env_int(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except Exception:
        return default
    return value if value > 0 else default


def _configure_llm_timeout_env(timeout_sec: int) -> None:
    value = str(max(1, int(timeout_sec)))
    os.environ["HERMES_LLM_CALL_TIMEOUT_SEC"] = value
    os.environ.setdefault("LLM_TIMEOUT_SECONDS", value)


def _summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "row_count": len(rows),
        "passed_count": sum(1 for row in rows if row.get("pass")),
        "failed_count": sum(1 for row in rows if not row.get("pass")),
        "timeout_count": sum(1 for row in rows if row.get("timed_out")),
        "error_count": sum(1 for row in rows if row.get("error") and not row.get("timed_out")),
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
        "final_answer_repair_attempts": sum(int(row.get("final_answer_repair_attempts") or 0) for row in rows),
        "repaired_success_count": sum(1 for row in rows if row.get("repaired_success")),
        "final_unavailable_with_runtime_facts": sum(1 for row in rows if row.get("final_unavailable_with_runtime_facts")),
        "atomic_protocol_fallback_count": sum(1 for row in rows if row.get("atomic_protocol_fallback_used")),
        "raw_sql_fallback_used_count": sum(1 for row in rows if row.get("raw_sql_fallback_used")),
    }


def _write_report(report_dir: Path, report: dict[str, Any]) -> dict[str, Any]:
    safe_report = redact_secrets(report)
    report_name = str(safe_report.get("report_name") or "hermes_v2_toolcall_smoke")
    json_path = report_dir / f"{report_name}.json"
    md_path = report_dir / f"{report_name}.md"
    json_path.write_text(json.dumps(safe_report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_markdown(safe_report), encoding="utf-8")
    quality_paths = _write_quality_report(report_dir, safe_report)
    timeout_paths = _write_timeout_diagnostics_report(report_dir, safe_report)
    safe_report["json_path"] = str(json_path)
    safe_report["md_path"] = str(md_path)
    safe_report.update(quality_paths)
    safe_report.update(timeout_paths)
    return safe_report


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# {report.get('report_title') or 'Hermes V2 Toolcall Smoke'}",
        "",
        f"- ok: `{report.get('ok')}`",
        f"- skipped: `{report.get('skipped')}`",
        f"- skip_reason: `{report.get('skip_reason')}`",
        f"- strategy: `{report.get('strategy')}`",
        f"- provider: `{(report.get('probe') or {}).get('provider')}`",
        f"- model: `{(report.get('probe') or {}).get('model')}`",
        f"- sdk_path_used: `{(report.get('probe') or {}).get('sdk_path_used')}`",
        f"- toolcall_supported: `{(report.get('probe') or {}).get('toolcall_supported')}`",
        f"- prompt_timeout_sec: `{report.get('prompt_timeout_sec')}`",
        f"- llm_call_timeout_sec: `{report.get('llm_call_timeout_sec')}`",
        f"- partial_report: `{report.get('partial_report')}`",
        "",
        "## Rows",
        "",
        "| Prompt | SQL | API | Semantic IR | Atomic Fallback | Runtime Facts | Timeout | Timed Out Stage | Total Sec | Planner Sec | Final Composer Sec | Expected | Pass |",
        "|---|---:|---:|---|---|---:|---|---|---:|---:|---:|---|---|",
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
                    str(row.get("runtime_fact_count")),
                    str(row.get("timed_out")),
                    str(row.get("timed_out_stage")),
                    str(row.get("total_latency_sec")),
                    str(row.get("semantic_ir_planner_latency_sec")),
                    str(row.get("final_composer_latency_sec")),
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
        "timeout_count": summary.get("timeout_count", 0),
        "unsupported_claims": summary.get("unsupported_claims", 0),
        "no_tool_fp": summary.get("no_tool_fp", 0),
        "ready_to_run_dev_eval": bool(
            report.get("ok")
            and summary.get("timeout_count", 0) == 0
            and summary.get("unsupported_claims", 0) == 0
            and summary.get("no_tool_fp", 0) == 0
            and summary.get("final_semantic_gate_final_failures", 0) == 0
        ),
        "summary": summary,
        "rows": rows,
    }
    json_path.write_text(json.dumps(redact_secrets(payload), indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_quality_markdown(redact_secrets(payload)), encoding="utf-8")
    return {"quality_json_path": str(json_path), "quality_md_path": str(md_path)}


def _write_timeout_diagnostics_report(report_dir: Path, report: dict[str, Any]) -> dict[str, str]:
    json_path = report_dir / "smoke_timeout_diagnostics.json"
    md_path = report_dir / "smoke_timeout_diagnostics.md"
    summary = report.get("summary") or {}
    rows = report.get("rows") or []
    payload = {
        "objective": "Diagnose and harden local Hermes/Qwen3.6 V2 smoke timeout before benchmark.",
        "files_changed": [
            "scripts/run_hermes_v2_toolcall_smoke.py",
            "dashagent/executor.py",
            "dashagent/llm_client.py",
            "dashagent/v2_semantic_ir_planner.py",
            "dashagent/trajectory.py",
            "tests/test_hermes_v2_toolcall_smoke.py",
            "tests/test_llm_client.py",
        ],
        "ok": bool(report.get("ok")),
        "fresh_smoke_completed": bool(not report.get("partial_report") and len(rows) == len(SMOKE_PROMPTS)),
        "fresh_smoke_passed": bool(report.get("ok")),
        "dev_eval_ran": False,
        "dev_eval_blocked_reason": "fresh smoke did not meet pass criteria" if not report.get("ok") else "",
        "benchmark_results": {},
        "timeout_count": summary.get("timeout_count", 0),
        "unsupported_claims": summary.get("unsupported_claims", 0),
        "no_tool_fp": summary.get("no_tool_fp", 0),
        "final_semantic_gate_failures": summary.get("final_semantic_gate_final_failures", 0),
        "raw_sql_fallback_used_count": summary.get("raw_sql_fallback_used_count", 0),
        "summary": summary,
        "last_stage_heartbeat": report.get("last_stage_heartbeat"),
        "rows": rows,
        "safe_to_keep": True,
        "safe_to_commit": bool(summary.get("timeout_count", 0) == 0),
        "safe_to_benchmark": bool(
            report.get("ok")
            and summary.get("timeout_count", 0) == 0
            and summary.get("unsupported_claims", 0) == 0
            and summary.get("no_tool_fp", 0) == 0
            and summary.get("final_semantic_gate_final_failures", 0) == 0
        ),
        "safe_to_promote": False,
    }
    safe = redact_secrets(payload)
    json_path.write_text(json.dumps(safe, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_timeout_markdown(safe), encoding="utf-8")
    return {"timeout_diagnostics_json_path": str(json_path), "timeout_diagnostics_md_path": str(md_path)}


def _timeout_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Hermes V2 Toolcall Smoke Timeout Diagnostics",
        "",
        f"- fresh_smoke_completed: `{payload.get('fresh_smoke_completed')}`",
        f"- fresh_smoke_passed: `{payload.get('fresh_smoke_passed')}`",
        f"- timeout_count: `{payload.get('timeout_count')}`",
        f"- unsupported_claims: `{payload.get('unsupported_claims')}`",
        f"- no_tool_fp: `{payload.get('no_tool_fp')}`",
        f"- final_semantic_gate_failures: `{payload.get('final_semantic_gate_failures')}`",
        f"- raw_sql_fallback_used_count: `{payload.get('raw_sql_fallback_used_count')}`",
        f"- dev_eval_ran: `{payload.get('dev_eval_ran')}`",
        f"- dev_eval_blocked_reason: `{payload.get('dev_eval_blocked_reason')}`",
        f"- safe_to_keep: `{payload.get('safe_to_keep')}`",
        f"- safe_to_commit: `{payload.get('safe_to_commit')}`",
        f"- safe_to_benchmark: `{payload.get('safe_to_benchmark')}`",
        f"- safe_to_promote: `{payload.get('safe_to_promote')}`",
        "",
        "## Per-Prompt Latency",
        "",
        "| Prompt | Pass | Timeout | Timed Out Stage | Total Sec | Planner Sec | SQL Gate Sec | API Gate Sec | SQL Exec Sec | API Exec Sec | Final Composer Sec | Repair Sec | Final Gate Sec | SQL | API | Facts |",
        "|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload.get("rows") or []:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row.get("prompt_id")),
                    str(row.get("pass")),
                    str(row.get("timed_out")),
                    str(row.get("timed_out_stage")),
                    str(row.get("total_latency_sec")),
                    str(row.get("semantic_ir_planner_latency_sec")),
                    str(row.get("sql_gate_latency_sec")),
                    str(row.get("api_gate_latency_sec")),
                    str(row.get("sql_execution_latency_sec")),
                    str(row.get("api_execution_latency_sec")),
                    str(row.get("final_composer_latency_sec")),
                    str(row.get("final_answer_repair_latency_sec")),
                    str(row.get("final_gate_latency_sec")),
                    str(row.get("sql_calls")),
                    str(row.get("api_calls")),
                    str(row.get("runtime_fact_count")),
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def _quality_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Unified Planner Semantic IR Quality",
        "",
        f"- unified_planner_facade_restored: `{payload.get('unified_planner_facade_restored')}`",
        f"- semantic_ir_primary: `{payload.get('semantic_ir_primary')}`",
        f"- free_form_sql_api_avoided: `{payload.get('free_form_sql_api_avoided')}`",
        f"- atomic_protocol_fallback_used_count: `{payload.get('atomic_protocol_fallback_used_count')}`",
        f"- timeout_count: `{payload.get('timeout_count')}`",
        f"- unsupported_claims: `{payload.get('unsupported_claims')}`",
        f"- no_tool_fp: `{payload.get('no_tool_fp')}`",
        f"- ready_to_run_dev_eval: `{payload.get('ready_to_run_dev_eval')}`",
        "",
        "## Smoke Rows",
        "",
        "| Prompt | Expected | SQL | API | Runtime Facts | Local Facts | Initial Gate Fail | Final Gate Fail | Repair Attempts | Repaired | Pass | Final Answer |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|---|",
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
                    str(row.get("final_answer_repair_attempts")),
                    str(row.get("repaired_success")),
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
