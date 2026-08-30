#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config, ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2
from dashagent.trajectory import redact_secrets
from scripts.load_local_env import load_local_env
from scripts.run_hermes_v2_toolcall_smoke import REPORT_DIR as SMOKE_REPORT_DIR
from scripts.run_hermes_v2_toolcall_smoke import _flatten_diagnostics, run_hermes_v2_toolcall_smoke


REPORT_DIR = ROOT / "outputs" / "reports" / "v2_ir_coverage"


def run_v2_ir_coverage_audit(config: Config | None = None, *, report_dir: Path | None = None, reuse_smoke: bool = False) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    report_dir = report_dir or REPORT_DIR
    report_dir.mkdir(parents=True, exist_ok=True)
    load_local_env(config.project_root)

    smoke = _load_existing_smoke() if reuse_smoke else run_hermes_v2_toolcall_smoke(config=config)
    rows = [_coverage_row(row) for row in smoke.get("rows") or []]
    summary = _summarize(rows, smoke)
    payload = {
        "ok": bool(smoke.get("ok")) and summary["backend_generated_sql_count"] == 0,
        "skipped": bool(smoke.get("skipped")),
        "skip_reason": smoke.get("skip_reason"),
        "strategy": ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2,
        "classification": "diagnostic_only",
        "smoke_reused": reuse_smoke,
        "objective": "Audit Semantic IR compiler coverage and strictly gated LLM-owned raw SQL fallback.",
        "primary_path": "SDK toolcall Semantic IR",
        "raw_sql_fallback_policy": "Only after valid-but-unsupported local Semantic IR and one Semantic IR repair attempt.",
        "backend_semantic_planning_used": False,
        "backend_sql_generation_used": False,
        "smoke_report": {
            "ok": smoke.get("ok"),
            "json_path": smoke.get("json_path"),
            "md_path": smoke.get("md_path"),
            "quality_json_path": smoke.get("quality_json_path"),
            "quality_md_path": smoke.get("quality_md_path"),
        },
        "summary": summary,
        "rows": rows,
    }
    return _write_reports(report_dir, payload)


def _coverage_row(smoke_row: dict[str, Any]) -> dict[str, Any]:
    trajectory = _read_trajectory(smoke_row.get("output_dir"), prompt_id=smoke_row.get("prompt_id"))
    diagnostics = _flatten_diagnostics(trajectory)
    row = {
        "prompt_id": smoke_row.get("prompt_id"),
        "prompt": smoke_row.get("prompt"),
        "pass": smoke_row.get("pass"),
        "expected": smoke_row.get("expected"),
        "sdk_toolcall_semantic_ir_used": diagnostics.get("sdk_toolcall_semantic_ir_used"),
        "semantic_ir_validation_passed": diagnostics.get("semantic_ir_validation_passed"),
        "semantic_ir_repair_attempted": diagnostics.get("semantic_ir_repair_attempted"),
        "semantic_ir_repair_success": diagnostics.get("semantic_ir_repair_success"),
        "semantic_ir_support_checked": diagnostics.get("semantic_ir_support_checked"),
        "semantic_ir_supported": diagnostics.get("semantic_ir_supported"),
        "semantic_ir_unsupported_reason": diagnostics.get("semantic_ir_unsupported_reason"),
        "semantic_ir_unsupported_features": diagnostics.get("semantic_ir_unsupported_features"),
        "semantic_ir_unsupported_task_id": diagnostics.get("semantic_ir_unsupported_task_id"),
        "semantic_ir_support_repair_attempted": diagnostics.get("semantic_ir_support_repair_attempted"),
        "semantic_ir_support_repair_success": diagnostics.get("semantic_ir_support_repair_success"),
        "semantic_ir_support_recommended_action": diagnostics.get("semantic_ir_support_recommended_action"),
        "raw_sql_fallback_considered": diagnostics.get("raw_sql_fallback_considered"),
        "raw_sql_fallback_used": diagnostics.get("raw_sql_fallback_used"),
        "raw_sql_fallback_success": diagnostics.get("raw_sql_fallback_success"),
        "raw_sql_fallback_repair_attempted": diagnostics.get("raw_sql_fallback_repair_attempted"),
        "raw_sql_fallback_repair_success": diagnostics.get("raw_sql_fallback_repair_success"),
        "raw_sql_fallback_gate_error_type": diagnostics.get("raw_sql_fallback_gate_error_type"),
        "raw_sql_fallback_rejected_reason": diagnostics.get("raw_sql_fallback_rejected_reason"),
        "raw_sql_safety_gate_failures": int(diagnostics.get("raw_sql_safety_gate_failures") or 0),
        "backend_generated_sql": diagnostics.get("backend_generated_sql"),
        "backend_formal_compilation_used": diagnostics.get("backend_formal_compilation_used"),
        "backend_semantic_planning_used": diagnostics.get("backend_semantic_planning_used"),
        "atomic_protocol_fallback_used": diagnostics.get("atomic_protocol_fallback_used"),
        "compiled_sql_count": smoke_row.get("compiled_sql_count"),
        "compiled_api_count": smoke_row.get("compiled_api_count"),
        "sql_calls": smoke_row.get("sql_calls"),
        "api_calls": smoke_row.get("api_calls"),
        "runtime_fact_count": smoke_row.get("runtime_fact_count"),
        "unsupported_claims": smoke_row.get("unsupported_claims"),
        "no_tool_fp": smoke_row.get("no_tool_fp"),
        "final_semantic_gate_final_failures": smoke_row.get("final_semantic_gate_final_failures"),
        "output_dir": smoke_row.get("output_dir"),
    }
    row["ir_supported_without_fallback"] = row["semantic_ir_supported"] is True and not row["raw_sql_fallback_used"]
    row["valid_unsupported_ir"] = row["semantic_ir_validation_passed"] is True and row["semantic_ir_supported"] is False
    row["raw_sql_fallback_safe"] = not row["raw_sql_fallback_used"] or (
        row["raw_sql_fallback_success"] is True
        and not row["backend_generated_sql"]
        and row["raw_sql_safety_gate_failures"] == 0
    )
    return redact_secrets(row)


def _load_existing_smoke() -> dict[str, Any]:
    path = SMOKE_REPORT_DIR / "hermes_v2_toolcall_smoke.json"
    if not path.exists():
        return {
            "ok": False,
            "skipped": True,
            "skip_reason": f"Existing smoke report not found: {path}",
            "rows": [],
            "json_path": str(path),
            "md_path": str(SMOKE_REPORT_DIR / "hermes_v2_toolcall_smoke.md"),
        }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "ok": False,
            "skipped": True,
            "skip_reason": f"Existing smoke report could not be parsed: {exc}",
            "rows": [],
            "json_path": str(path),
        }
    return data if isinstance(data, dict) else {"ok": False, "skipped": True, "skip_reason": "Existing smoke report is not a JSON object.", "rows": []}


def _read_trajectory(output_dir: Any, *, prompt_id: Any = None) -> dict[str, Any]:
    path = Path(str(output_dir)) / "trajectory.json" if output_dir else None
    if path is None or not path.exists():
        prompt = str(prompt_id or "").strip()
        fallback = ROOT / "outputs" / f"hermes_toolcall_{prompt}" / "robust_generalized_harness_candidate_v2" / "trajectory.json"
        path = fallback if fallback.exists() else path
    if path is None or not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _summarize(rows: list[dict[str, Any]], smoke: dict[str, Any]) -> dict[str, Any]:
    return {
        "row_count": len(rows),
        "smoke_ok": bool(smoke.get("ok")),
        "smoke_skipped": bool(smoke.get("skipped")),
        "semantic_ir_support_checked_count": sum(1 for row in rows if row.get("semantic_ir_support_checked") is True),
        "semantic_ir_supported_count": sum(1 for row in rows if row.get("semantic_ir_supported") is True),
        "valid_unsupported_ir_count": sum(1 for row in rows if row.get("valid_unsupported_ir") is True),
        "support_repair_attempted_count": sum(1 for row in rows if row.get("semantic_ir_support_repair_attempted") is True),
        "support_repair_success_count": sum(1 for row in rows if row.get("semantic_ir_support_repair_success") is True),
        "raw_sql_fallback_considered_count": sum(1 for row in rows if row.get("raw_sql_fallback_considered") is True),
        "raw_sql_fallback_used_count": sum(1 for row in rows if row.get("raw_sql_fallback_used") is True),
        "raw_sql_fallback_success_count": sum(1 for row in rows if row.get("raw_sql_fallback_success") is True),
        "raw_sql_fallback_repair_attempted_count": sum(1 for row in rows if row.get("raw_sql_fallback_repair_attempted") is True),
        "raw_sql_safety_gate_failures": sum(int(row.get("raw_sql_safety_gate_failures") or 0) for row in rows),
        "backend_generated_sql_count": sum(1 for row in rows if row.get("backend_generated_sql") is True),
        "atomic_protocol_fallback_count": sum(1 for row in rows if row.get("atomic_protocol_fallback_used") is True),
        "backend_semantic_planning_count": sum(1 for row in rows if row.get("backend_semantic_planning_used") is True),
        "unsupported_claims": sum(int(row.get("unsupported_claims") or 0) for row in rows),
        "no_tool_fp": sum(1 for row in rows if row.get("no_tool_fp")),
        "final_semantic_gate_final_failures": sum(int(row.get("final_semantic_gate_final_failures") or 0) for row in rows),
    }


def _write_reports(report_dir: Path, payload: dict[str, Any]) -> dict[str, Any]:
    safe = redact_secrets(payload)
    audit_json = report_dir / "ir_coverage_audit.json"
    audit_md = report_dir / "ir_coverage_audit.md"
    final_json = report_dir / "semantic_ir_coverage_and_raw_sql_fallback.json"
    final_md = report_dir / "semantic_ir_coverage_and_raw_sql_fallback.md"
    text = _markdown(safe)
    audit_json.write_text(json.dumps(safe, indent=2, sort_keys=True, default=str), encoding="utf-8")
    final_json.write_text(json.dumps(safe, indent=2, sort_keys=True, default=str), encoding="utf-8")
    audit_md.write_text(text, encoding="utf-8")
    final_md.write_text(text, encoding="utf-8")
    safe["json_path"] = str(final_json)
    safe["md_path"] = str(final_md)
    safe["audit_json_path"] = str(audit_json)
    safe["audit_md_path"] = str(audit_md)
    return safe


def _markdown(payload: dict[str, Any]) -> str:
    summary = payload.get("summary") or {}
    lines = [
        "# Semantic IR Coverage And Raw SQL Fallback",
        "",
        f"- ok: `{payload.get('ok')}`",
        f"- skipped: `{payload.get('skipped')}`",
        f"- strategy: `{payload.get('strategy')}`",
        f"- classification: `{payload.get('classification')}`",
        f"- smoke_reused: `{payload.get('smoke_reused')}`",
        f"- primary_path: `{payload.get('primary_path')}`",
        f"- raw_sql_fallback_policy: `{payload.get('raw_sql_fallback_policy')}`",
        f"- backend_semantic_planning_used: `{payload.get('backend_semantic_planning_used')}`",
        f"- backend_sql_generation_used: `{payload.get('backend_sql_generation_used')}`",
        "",
        "## Summary",
        "",
    ]
    for key in sorted(summary):
        lines.append(f"- {key}: `{summary[key]}`")
    lines.extend(
        [
            "",
            "## Rows",
            "",
            "| Prompt | Support Checked | Supported | Support Repair | Raw Considered | Raw Used | Raw Safe | SQL | API | Facts | Pass |",
            "|---|---|---|---|---|---|---|---:|---:|---:|---|",
        ]
    )
    for row in payload.get("rows") or []:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row.get("prompt_id")),
                    str(row.get("semantic_ir_support_checked")),
                    str(row.get("semantic_ir_supported")),
                    f"{row.get('semantic_ir_support_repair_attempted')}/{row.get('semantic_ir_support_repair_success')}",
                    str(row.get("raw_sql_fallback_considered")),
                    str(row.get("raw_sql_fallback_used")),
                    str(row.get("raw_sql_fallback_safe")),
                    str(row.get("sql_calls")),
                    str(row.get("api_calls")),
                    str(row.get("runtime_fact_count")),
                    str(row.get("pass")),
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit V2 Semantic IR coverage and raw SQL fallback diagnostics.")
    parser.add_argument("--reuse-smoke", action="store_true", help="Reuse the latest Hermes V2 toolcall smoke JSON instead of rerunning smoke.")
    args = parser.parse_args()
    report = run_v2_ir_coverage_audit(reuse_smoke=args.reuse_smoke)
    print(json.dumps({"ok": report.get("ok"), "skipped": report.get("skipped"), "json": report.get("json_path"), "md": report.get("md_path")}, indent=2))
    return 0 if report.get("ok") or report.get("skipped") else 1


if __name__ == "__main__":
    raise SystemExit(main())
