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
from dashagent.llm_unified_planner import run_llm_unified_planner
from dashagent.trajectory import redact_secrets
from scripts.load_local_env import load_local_env
from scripts.run_hermes_v2_toolcall_smoke import SMOKE_PROMPTS


REPORT_DIR = ROOT / "outputs" / "reports" / "hermes_v2_toolcall_smoke"
JSON_PATH = REPORT_DIR / "deepseek_planner_only_diagnostics.json"
MD_PATH = REPORT_DIR / "deepseek_planner_only_diagnostics.md"
DEFAULT_TIMEOUT_SEC = 75


def run_planner_only_diagnostics(
    *,
    config: Config | None = None,
    report_dir: Path | None = None,
    timeout_sec: int | None = None,
) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    load_local_env(config.project_root)
    report_dir = report_dir or REPORT_DIR
    report_dir.mkdir(parents=True, exist_ok=True)
    timeout = int(timeout_sec or os.getenv("HERMES_PLANNER_ONLY_TIMEOUT_SEC") or DEFAULT_TIMEOUT_SEC)
    rows: list[dict[str, Any]] = []
    for item in SMOKE_PROMPTS:
        rows.append(_run_prompt_with_timeout(item, config=config, timeout_sec=timeout))
        _write_report(report_dir, rows, timeout)
    return _write_report(report_dir, rows, timeout)


def _run_prompt_with_timeout(item: dict[str, Any], *, config: Config, timeout_sec: int) -> dict[str, Any]:
    started = time.perf_counter()
    ctx = mp.get_context("spawn" if sys.platform in {"darwin", "win32"} else "fork")
    queue: Any = ctx.Queue(maxsize=1)
    process = ctx.Process(target=_planner_worker, args=(item, config, queue))
    process.start()
    process.join(timeout_sec)
    elapsed = round(time.perf_counter() - started, 3)
    if process.is_alive():
        process.terminate()
        process.join(3)
        if process.is_alive():
            process.kill()
            process.join(3)
        return _timeout_row(item, elapsed, timeout_sec, getattr(process, "exitcode", None))
    exitcode = getattr(process, "exitcode", None)
    if exitcode not in (0, None):
        return _error_row(item, elapsed, f"planner_worker_exitcode_{exitcode}", exitcode=exitcode)
    try:
        payload = queue.get(timeout=5)
    except Exception:
        return _error_row(item, elapsed, "planner_worker_returned_no_result", exitcode=exitcode)
    if isinstance(payload, dict) and payload.get("ok") and isinstance(payload.get("row"), dict):
        row = payload["row"]
        row["planner_elapsed_sec"] = elapsed
        return redact_secrets(row)
    return _error_row(
        item,
        elapsed,
        str((payload or {}).get("error") if isinstance(payload, dict) else "planner_worker_failed"),
        traceback_text=(payload or {}).get("traceback") if isinstance(payload, dict) else None,
        exitcode=exitcode,
    )


def _planner_worker(item: dict[str, Any], config: Config, queue: Any) -> None:
    try:
        executor = AgentExecutor(config)
        planner_context = executor._llm_owned_planner_context()
        started = time.perf_counter()
        plan = run_llm_unified_planner(
            user_prompt=item["prompt"],
            schema_context=planner_context["schema_context"],
            endpoint_context=planner_context["endpoint_context"],
        )
        row = _row_from_plan(item, plan.to_dict(), round(time.perf_counter() - started, 3))
        queue.put({"ok": True, "row": row})
    except Exception as exc:
        queue.put({"ok": False, "error": str(exc), "traceback": traceback.format_exc(limit=20)})


def _row_from_plan(item: dict[str, Any], plan: dict[str, Any], elapsed: float) -> dict[str, Any]:
    diagnostics = plan.get("diagnostics") if isinstance(plan.get("diagnostics"), dict) else {}
    passes = plan.get("passes") if isinstance(plan.get("passes"), list) else []
    task_types = [str(pass_item.get("path") or "") for pass_item in passes if isinstance(pass_item, dict)]
    semantic_ir_present = bool(diagnostics.get("sdk_toolcall_semantic_ir_used") or diagnostics.get("v2_semantic_ir_used"))
    answer_contract = plan.get("answer_contract")
    response_error_message = (
        plan.get("reason")
        if plan.get("parse_error") or plan.get("backend_unavailable") or not diagnostics.get("planner_success", True)
        else diagnostics.get("semantic_ir_validation_error_message")
    )
    return redact_secrets(
        {
            "prompt_id": item["id"],
            "prompt": item["prompt"],
            "expected_class": item.get("expected"),
            "planner_timeout": False,
            "planner_elapsed_sec": elapsed,
            "tool_calls_count": int(diagnostics.get("planner_tool_calls_count") or 0),
            "finish_reason": diagnostics.get("planner_finish_reason"),
            "semantic_ir_present": semantic_ir_present,
            "semantic_ir_task_count": int(diagnostics.get("semantic_ir_task_count") or len(passes) or 0),
            "semantic_ir_task_types": task_types,
            "answer_contract_present": bool(answer_contract),
            "evidence_contract_present": bool(answer_contract and plan.get("route") == "EVIDENCE_PIPELINE"),
            "raw_text_content_present": bool(diagnostics.get("planner_raw_text_content_present")),
            "response_error_type": diagnostics.get("semantic_ir_validation_error_type") or ("planner_error" if response_error_message else None),
            "response_error_message": response_error_message,
            "tool_name": diagnostics.get("planner_tool_name"),
            "planner_schema_profile": diagnostics.get("planner_schema_profile"),
            "planner_retry_used": bool(diagnostics.get("planner_retry_used")),
            "planner_retry_reason": diagnostics.get("planner_retry_reason"),
            "planner_model_timeout_sec": diagnostics.get("planner_model_timeout_sec"),
            "planner_extra_body_keys": diagnostics.get("planner_extra_body_keys"),
            "planner_tool_choice": diagnostics.get("planner_tool_choice"),
            "semantic_ir_prompt_total_chars": diagnostics.get("semantic_ir_prompt_total_chars"),
            "semantic_ir_prompt_user_chars": diagnostics.get("semantic_ir_prompt_user_chars"),
            "semantic_ir_prompt_system_chars": diagnostics.get("semantic_ir_prompt_system_chars"),
            "semantic_ir_tool_schema_chars": diagnostics.get("semantic_ir_tool_schema_chars"),
            "semantic_ir_planner_char_budget": diagnostics.get("semantic_ir_planner_char_budget"),
            "semantic_ir_context_truncated": diagnostics.get("semantic_ir_context_truncated"),
            "semantic_ir_context_truncated_sections": diagnostics.get("semantic_ir_context_truncated_sections"),
            "schema_card_original_row_count": diagnostics.get("schema_card_original_row_count"),
            "schema_card_row_count": diagnostics.get("schema_card_row_count"),
            "schema_card_original_char_count": diagnostics.get("schema_card_original_char_count"),
            "schema_card_final_char_count": diagnostics.get("schema_card_final_char_count"),
            "schema_card_columns_truncated": diagnostics.get("schema_card_columns_truncated"),
            "api_card_original_row_count": diagnostics.get("api_card_original_row_count"),
            "api_card_row_count": diagnostics.get("api_card_row_count"),
            "api_card_original_char_count": diagnostics.get("api_card_original_char_count"),
            "api_card_final_char_count": diagnostics.get("api_card_final_char_count"),
            "api_card_detail_truncated": diagnostics.get("api_card_detail_truncated"),
            "provider": plan.get("provider"),
            "model": plan.get("model"),
            "route": plan.get("route"),
            "evidence_order": plan.get("evidence_order"),
        }
    )


def _timeout_row(item: dict[str, Any], elapsed: float, timeout_sec: int, exitcode: int | None) -> dict[str, Any]:
    return redact_secrets(
        {
            "prompt_id": item["id"],
            "prompt": item["prompt"],
            "expected_class": item.get("expected"),
            "planner_timeout": True,
            "planner_elapsed_sec": elapsed,
            "tool_calls_count": 0,
            "finish_reason": None,
            "semantic_ir_present": False,
            "semantic_ir_task_count": 0,
            "semantic_ir_task_types": [],
            "answer_contract_present": False,
            "evidence_contract_present": False,
            "raw_text_content_present": False,
            "response_error_type": "planner_timeout",
            "response_error_message": f"planner_timeout_after_{timeout_sec}s",
            "tool_name": None,
            "child_exitcode": exitcode,
        }
    )


def _error_row(item: dict[str, Any], elapsed: float, error: str, *, traceback_text: str | None = None, exitcode: int | None = None) -> dict[str, Any]:
    row = _timeout_row(item, elapsed, 0, exitcode)
    row.update(
        {
            "planner_timeout": False,
            "response_error_type": "planner_error",
            "response_error_message": error,
            "traceback": traceback_text,
        }
    )
    return redact_secrets(row)


def _write_report(report_dir: Path, rows: list[dict[str, Any]], timeout_sec: int) -> dict[str, Any]:
    json_path = report_dir / "deepseek_planner_only_diagnostics.json"
    md_path = report_dir / "deepseek_planner_only_diagnostics.md"
    payload = redact_secrets(
        {
            "objective": "DeepSeek V2 Unified Planner / SDK Semantic IR planner-only diagnostics.",
            "row_count": len(rows),
            "timeout_sec": timeout_sec,
            "timeout_count": sum(1 for row in rows if row.get("planner_timeout")),
            "semantic_ir_present_count": sum(1 for row in rows if row.get("semantic_ir_present")),
            "answer_contract_present_count": sum(1 for row in rows if row.get("answer_contract_present")),
            "raw_text_content_present_count": sum(1 for row in rows if row.get("raw_text_content_present")),
            "rows": rows,
        }
    )
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    return {**payload, "json_path": str(json_path), "md_path": str(md_path)}


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# DeepSeek V2 Planner-Only Diagnostics",
        "",
        f"- row_count: `{report.get('row_count')}`",
        f"- timeout_count: `{report.get('timeout_count')}`",
        f"- semantic_ir_present_count: `{report.get('semantic_ir_present_count')}`",
        f"- answer_contract_present_count: `{report.get('answer_contract_present_count')}`",
        f"- raw_text_content_present_count: `{report.get('raw_text_content_present_count')}`",
        "",
        "| Prompt | Expected | Timeout | Sec | Tool Calls | Tool | Finish | Semantic IR | Tasks | Profile | Retry | Error |",
        "|---|---|---|---:|---:|---|---|---|---:|---|---|---|",
    ]
    for row in report.get("rows") or []:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row.get("prompt_id")),
                    str(row.get("expected_class")),
                    str(row.get("planner_timeout")),
                    str(row.get("planner_elapsed_sec")),
                    str(row.get("tool_calls_count")),
                    str(row.get("tool_name")),
                    str(row.get("finish_reason")),
                    str(row.get("semantic_ir_present")),
                    str(row.get("semantic_ir_task_count")),
                    str(row.get("planner_schema_profile")),
                    str(row.get("planner_retry_used")),
                    str(row.get("response_error_type")),
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    report = run_planner_only_diagnostics()
    print(json.dumps({"json": report.get("json_path"), "md": report.get("md_path"), "timeout_count": report.get("timeout_count")}, indent=2))
    return 0 if report.get("timeout_count", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
