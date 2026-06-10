#!/usr/bin/env python
from __future__ import annotations

import json
import multiprocessing as mp
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.executor import AgentExecutor
from dashagent.llm_client import get_llm_client
from dashagent.trajectory import compact_preview, redact_secrets
from dashagent.v2_semantic_ir_planner import DEEPSEEK_SWEEP_PROFILE_ORDER, run_semantic_ir_toolcall_planner
from scripts.load_local_env import load_local_env
from scripts.run_hermes_v2_toolcall_smoke import SMOKE_PROMPTS


REPORT_DIR = ROOT / "outputs" / "reports" / "hermes_v2_toolcall_smoke"
JSON_PATH = REPORT_DIR / "deepseek_planner_profile_sweep.json"
MD_PATH = REPORT_DIR / "deepseek_planner_profile_sweep.md"
DEFAULT_TIMEOUT_SEC = 100


def run_deepseek_planner_profile_sweep(
    *,
    config: Config | None = None,
    report_dir: Path | None = None,
    timeout_sec: int | None = None,
    profiles: list[str] | None = None,
) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    load_local_env(config.project_root)
    report_dir = report_dir or REPORT_DIR
    report_dir.mkdir(parents=True, exist_ok=True)
    timeout = int(timeout_sec or os.getenv("HERMES_PLANNER_PROFILE_SWEEP_TIMEOUT_SEC") or DEFAULT_TIMEOUT_SEC)
    active_profiles = profiles or list(DEEPSEEK_SWEEP_PROFILE_ORDER)
    rows: list[dict[str, Any]] = []
    for profile in active_profiles:
        for item in SMOKE_PROMPTS:
            rows.append(_run_prompt_with_timeout(item, profile=profile, config=config, timeout_sec=timeout))
            _write_report(report_dir, rows, active_profiles, timeout)
    return _write_report(report_dir, rows, active_profiles, timeout)


def _run_prompt_with_timeout(item: dict[str, Any], *, profile: str, config: Config, timeout_sec: int) -> dict[str, Any]:
    started = time.perf_counter()
    ctx = mp.get_context("spawn" if sys.platform in {"darwin", "win32"} else "fork")
    queue: Any = ctx.Queue(maxsize=1)
    process = ctx.Process(target=_planner_worker, args=(item, profile, config, queue))
    process.start()
    process.join(timeout_sec)
    elapsed = round(time.perf_counter() - started, 3)
    if process.is_alive():
        process.terminate()
        process.join(3)
        if process.is_alive():
            process.kill()
            process.join(3)
        return _timeout_row(item, profile, elapsed, timeout_sec, getattr(process, "exitcode", None))
    exitcode = getattr(process, "exitcode", None)
    if exitcode not in (0, None):
        return _error_row(item, profile, elapsed, f"planner_worker_exitcode_{exitcode}", exitcode=exitcode)
    try:
        payload = queue.get(timeout=5)
    except Exception:
        return _error_row(item, profile, elapsed, "planner_worker_returned_no_result", exitcode=exitcode)
    if isinstance(payload, dict) and payload.get("ok") and isinstance(payload.get("row"), dict):
        row = payload["row"]
        row["elapsed_sec"] = elapsed
        return redact_secrets(row)
    return _error_row(
        item,
        profile,
        elapsed,
        str((payload or {}).get("error") if isinstance(payload, dict) else "planner_worker_failed"),
        traceback_text=(payload or {}).get("traceback") if isinstance(payload, dict) else None,
        exitcode=exitcode,
    )


def _planner_worker(item: dict[str, Any], profile: str, config: Config, queue: Any) -> None:
    try:
        os.environ["HERMES_V2_PLANNER_PROFILE"] = profile
        executor = AgentExecutor(config)
        planner_context = executor._llm_owned_planner_context()
        client = get_llm_client()
        started = time.perf_counter()
        result = run_semantic_ir_toolcall_planner(
            client=client,
            user_prompt=item["prompt"],
            schema_context=planner_context["schema_context"],
            endpoint_context=planner_context["endpoint_context"],
            fallback_to_atomic=False,
            planner_profile=profile,
        )
        row = _row_from_protocol_result(item, profile, result.plan_payload, result.diagnostics, round(time.perf_counter() - started, 3))
        queue.put({"ok": True, "row": row})
    except Exception as exc:
        queue.put({"ok": False, "error": str(exc), "traceback": traceback.format_exc(limit=20)})


def _row_from_protocol_result(
    item: dict[str, Any],
    profile: str,
    plan_payload: dict[str, Any],
    diagnostics: dict[str, Any],
    elapsed: float,
) -> dict[str, Any]:
    passes = plan_payload.get("passes") if isinstance(plan_payload.get("passes"), list) else []
    answer_contract = plan_payload.get("answer_contract")
    error_message = (
        plan_payload.get("reason")
        if plan_payload.get("parse_error") or not diagnostics.get("planner_success", True)
        else diagnostics.get("semantic_ir_validation_error_message")
    )
    return _safe_row(
        {
            "prompt_id": item["id"],
            "prompt": item["prompt"],
            "expected_class": item.get("expected"),
            "profile": profile,
            "timeout": False,
            "elapsed_sec": elapsed,
            "finish_reason": diagnostics.get("planner_finish_reason"),
            "tool_calls_count": int(diagnostics.get("planner_tool_calls_count") or 0),
            "selected_tool_name": diagnostics.get("planner_tool_name"),
            "semantic_ir_present": bool(diagnostics.get("sdk_toolcall_semantic_ir_used") or diagnostics.get("v2_semantic_ir_used")),
            "task_count": int(diagnostics.get("semantic_ir_task_count") or len(passes) or 0),
            "task_types": [str(pass_item.get("path") or "") for pass_item in passes if isinstance(pass_item, dict)],
            "answer_contract_present": bool(answer_contract),
            "evidence_contract_present": bool(answer_contract and plan_payload.get("route") == "EVIDENCE_PIPELINE"),
            "validation_ok": bool(diagnostics.get("semantic_ir_validation_passed")),
            "error_type": diagnostics.get("semantic_ir_validation_error_type") or ("planner_error" if error_message else None),
            "error_message": str(error_message)[:600] if error_message else None,
            "raw_text_content_present": bool(diagnostics.get("planner_raw_text_content_present")),
            "planner_profile": diagnostics.get("planner_profile"),
            "planner_schema_profile": diagnostics.get("planner_schema_profile"),
            "planner_tool_choice": diagnostics.get("planner_tool_choice"),
            "planner_tool_names": diagnostics.get("planner_tool_names"),
            "semantic_ir_tool_schema_chars": diagnostics.get("semantic_ir_tool_schema_chars"),
            "planner_retry_used": bool(diagnostics.get("planner_retry_used")),
            "planner_retry_reason": diagnostics.get("planner_retry_reason"),
            "planner_model_timeout_sec": diagnostics.get("planner_model_timeout_sec"),
            "planner_extra_body_keys": diagnostics.get("planner_extra_body_keys"),
            "route": plan_payload.get("route"),
            "evidence_order": plan_payload.get("evidence_order"),
            "compiled_sql_count": int(diagnostics.get("compiled_sql_count") or 0),
            "compiled_api_count": int(diagnostics.get("compiled_api_count") or 0),
            "parse_source": diagnostics.get("planner_parse_source"),
            "provider_latency_ms": diagnostics.get("planner_provider_latency_ms"),
            "raw_preview": compact_preview(plan_payload, 900),
        },
        profile=profile,
    )


def _timeout_row(item: dict[str, Any], profile: str, elapsed: float, timeout_sec: int, exitcode: int | None) -> dict[str, Any]:
    return _safe_row(
        {
            "prompt_id": item["id"],
            "prompt": item["prompt"],
            "expected_class": item.get("expected"),
            "profile": profile,
            "timeout": True,
            "elapsed_sec": elapsed,
            "finish_reason": None,
            "tool_calls_count": 0,
            "selected_tool_name": None,
            "semantic_ir_present": False,
            "task_count": 0,
            "task_types": [],
            "answer_contract_present": False,
            "evidence_contract_present": False,
            "validation_ok": False,
            "error_type": "planner_timeout",
            "error_message": f"planner_timeout_after_{timeout_sec}s",
            "raw_text_content_present": False,
            "child_exitcode": exitcode,
        },
        profile=profile,
    )


def _error_row(
    item: dict[str, Any],
    profile: str,
    elapsed: float,
    error: str,
    *,
    traceback_text: str | None = None,
    exitcode: int | None = None,
) -> dict[str, Any]:
    row = _timeout_row(item, profile, elapsed, 0, exitcode)
    row.update(
        {
            "timeout": False,
            "error_type": "planner_error",
            "error_message": error,
            "traceback": traceback_text,
        }
    )
    return redact_secrets(row)


def _write_report(report_dir: Path, rows: list[dict[str, Any]], profiles: list[str], timeout_sec: int) -> dict[str, Any]:
    summary = _profile_summaries(rows, profiles)
    selected = select_best_profile(summary)
    payload = _safe_payload(
        {
            "objective": "DeepSeek V4 Flash V2 planner profile sweep; planner-only, no SQL/API execution.",
            "profiles": profiles,
            "prompt_count": len(SMOKE_PROMPTS),
            "row_count": len(rows),
            "timeout_sec": timeout_sec,
            "selected_profile": selected.get("profile"),
            "selection_reason": selected.get("reason"),
            "profile_summaries": summary,
            "rows": rows,
        },
        profiles=profiles,
        rows=rows,
        summaries=summary,
    )
    json_path = report_dir / "deepseek_planner_profile_sweep.json"
    md_path = report_dir / "deepseek_planner_profile_sweep.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    return {**payload, "json_path": str(json_path), "md_path": str(md_path)}


def _profile_summaries(rows: list[dict[str, Any]], profiles: list[str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for profile in profiles:
        profile_rows = [row for row in rows if row.get("profile") == profile]
        if not profile_rows:
            out.append({"profile": profile, "row_count": 0})
            continue
        latencies = [float(row.get("elapsed_sec") or 0) for row in profile_rows if not row.get("timeout")]
        schema_chars = [int(row.get("semantic_ir_tool_schema_chars") or 0) for row in profile_rows if row.get("semantic_ir_tool_schema_chars")]
        out.append(
            {
                "profile": profile,
                "row_count": len(profile_rows),
                "timeout_count": sum(1 for row in profile_rows if row.get("timeout")),
                "semantic_ir_present_count": sum(1 for row in profile_rows if row.get("semantic_ir_present")),
                "validation_ok_count": sum(1 for row in profile_rows if row.get("validation_ok")),
                "answer_contract_present_count": sum(1 for row in profile_rows if row.get("answer_contract_present")),
                "evidence_contract_present_count": sum(1 for row in profile_rows if row.get("evidence_contract_present")),
                "raw_text_content_present_count": sum(1 for row in profile_rows if row.get("raw_text_content_present")),
                "avg_elapsed_sec": round(sum(latencies) / len(latencies), 3) if latencies else None,
                "max_elapsed_sec": round(max(latencies), 3) if latencies else None,
                "tool_schema_chars": min(schema_chars) if schema_chars else None,
                "error_types": _count_by(profile_rows, "error_type"),
                "selected_tool_names": _count_by(profile_rows, "selected_tool_name"),
            }
        )
    return out


def select_best_profile(profile_summaries: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = [item for item in profile_summaries if item.get("row_count")]
    if not candidates:
        return {"profile": None, "reason": "no_profile_rows"}

    def sort_key(item: dict[str, Any]) -> tuple[Any, ...]:
        return (
            int(item.get("validation_ok_count") or 0),
            int(item.get("semantic_ir_present_count") or 0),
            int(item.get("answer_contract_present_count") or 0),
            int(item.get("evidence_contract_present_count") or 0),
            -int(item.get("timeout_count") or 0),
            -int(item.get("raw_text_content_present_count") or 0),
            -(float(item.get("avg_elapsed_sec") or 999999)),
            -(int(item.get("tool_schema_chars") or 999999)),
        )

    selected = sorted(candidates, key=sort_key, reverse=True)[0]
    return {
        "profile": selected.get("profile"),
        "reason": (
            "selected by max validation_ok_count, max semantic_ir_present_count, valid contracts, "
            "min timeout_count, no text fallback, lower latency, and smaller schema."
        ),
        "metrics": selected,
    }


def _count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = row.get(key)
        label = str(value) if value not in (None, "") else "none"
        counts[label] = counts.get(label, 0) + 1
    return counts


def _safe_row(row: dict[str, Any], *, profile: str) -> dict[str, Any]:
    safe = redact_secrets(row)
    if not isinstance(safe, dict):
        safe = dict(row)
    safe["profile"] = profile
    if row.get("planner_profile"):
        safe["planner_profile"] = row.get("planner_profile")
    return safe


def _safe_payload(
    payload: dict[str, Any],
    *,
    profiles: list[str],
    rows: list[dict[str, Any]],
    summaries: list[dict[str, Any]],
) -> dict[str, Any]:
    safe = redact_secrets(payload)
    if not isinstance(safe, dict):
        safe = dict(payload)
    safe["profiles"] = list(profiles)
    safe["selected_profile"] = payload.get("selected_profile")
    safe_rows = safe.get("rows") if isinstance(safe.get("rows"), list) else []
    for index, source in enumerate(rows):
        if index < len(safe_rows) and isinstance(safe_rows[index], dict):
            safe_rows[index]["profile"] = source.get("profile")
            safe_rows[index]["planner_profile"] = source.get("planner_profile")
    safe_summaries = safe.get("profile_summaries") if isinstance(safe.get("profile_summaries"), list) else []
    for index, source in enumerate(summaries):
        if index < len(safe_summaries) and isinstance(safe_summaries[index], dict):
            safe_summaries[index]["profile"] = source.get("profile")
    return safe


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# DeepSeek V2 Planner Profile Sweep",
        "",
        "- Scope: planner-only, no SQL/API execution.",
        f"- row_count: `{report.get('row_count')}`",
        f"- selected_profile: `{report.get('selected_profile')}`",
        f"- selection_reason: `{report.get('selection_reason')}`",
        "",
        "## Profile Summary",
        "",
        "| Profile | Rows | Semantic IR | Timeouts | Validation OK | Answer Contract | Raw Text | Avg Sec | Tool Schema Chars | Errors |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for item in report.get("profile_summaries") or []:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(item.get("profile")),
                    str(item.get("row_count")),
                    str(item.get("semantic_ir_present_count")),
                    str(item.get("timeout_count")),
                    str(item.get("validation_ok_count")),
                    str(item.get("answer_contract_present_count")),
                    str(item.get("raw_text_content_present_count")),
                    str(item.get("avg_elapsed_sec")),
                    str(item.get("tool_schema_chars")),
                    str(compact_preview(item.get("error_types"), 180)).replace("|", "/"),
                ]
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Rows",
            "",
            "| Profile | Prompt | Timeout | Sec | Tool Calls | Tool | Finish | Semantic IR | Tasks | Contract | Valid | Error |",
            "|---|---|---|---:|---:|---|---|---|---:|---|---|---|",
        ]
    )
    for row in report.get("rows") or []:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row.get("profile")),
                    str(row.get("prompt_id")),
                    str(row.get("timeout")),
                    str(row.get("elapsed_sec")),
                    str(row.get("tool_calls_count")),
                    str(row.get("selected_tool_name")),
                    str(row.get("finish_reason")),
                    str(row.get("semantic_ir_present")),
                    str(row.get("task_count")),
                    str(row.get("answer_contract_present")),
                    str(row.get("validation_ok")),
                    str(row.get("error_type")),
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    report = run_deepseek_planner_profile_sweep()
    print(
        json.dumps(
            {
                "json": report.get("json_path"),
                "md": report.get("md_path"),
                "selected_profile": report.get("selected_profile"),
                "profile_summaries": report.get("profile_summaries"),
            },
            indent=2,
            sort_keys=True,
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
