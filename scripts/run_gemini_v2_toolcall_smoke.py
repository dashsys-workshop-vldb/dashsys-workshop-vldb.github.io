#!/usr/bin/env python
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.llm_client import DEFAULT_GEMINI_MODEL
from dashagent.trajectory import redact_secrets
from scripts.load_local_env import load_local_env
from scripts.probe_gemini_toolcall import run_gemini_toolcall_probe
from scripts.run_hermes_v2_toolcall_smoke import run_hermes_v2_toolcall_smoke


REPORT_DIR = ROOT / "outputs" / "reports" / "gemini_v2_toolcall_smoke"
QWEN_REPORT_PATHS = [
    ROOT / "outputs" / "reports" / "hermes_v2_toolcall_smoke" / "hermes_v2_toolcall_smoke.json",
    ROOT / "outputs" / "reports" / "hermes_v2_toolcall_smoke" / "final_two_rows_grounding_fix.json",
    ROOT / "outputs" / "reports" / "hermes_v2_toolcall_smoke" / "final_answer_evidence_use_fix.json",
    ROOT / "outputs" / "reports" / "hermes_v2_toolcall_smoke" / "smoke_timeout_diagnostics.json",
    ROOT / "outputs" / "reports" / "hermes_v2_toolcall_smoke" / "unified_planner_semantic_ir_quality.json",
]


def run_gemini_v2_toolcall_smoke(config: Config | None = None, *, report_dir: Path | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    report_dir = report_dir or REPORT_DIR
    report_dir.mkdir(parents=True, exist_ok=True)
    load_local_env(config.project_root)
    os.environ["DASHAGENT_LLM_PROVIDER"] = "gemini"
    os.environ.setdefault("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
    if os.getenv("GEMINI_TIMEOUT_SEC"):
        os.environ.setdefault("HERMES_LLM_CALL_TIMEOUT_SEC", os.getenv("GEMINI_TIMEOUT_SEC", "60"))

    def probe_runner(inner_config: Config) -> dict[str, Any]:
        return run_gemini_toolcall_probe(inner_config, report_dir=ROOT / "outputs" / "reports" / "gemini_toolcall_probe")

    report = run_hermes_v2_toolcall_smoke(
        config,
        report_dir=report_dir,
        probe_runner=probe_runner,
        report_name="gemini_v2_toolcall_smoke",
        report_title="Gemini V2 Toolcall Smoke",
    )
    write_gemini_vs_local_qwen_comparison(report, report_dir=report_dir)
    return report


def write_gemini_vs_local_qwen_comparison(
    gemini_report: dict[str, Any],
    *,
    report_dir: Path | None = None,
    qwen_report_paths: list[Path] | None = None,
) -> dict[str, Any]:
    report_dir = report_dir or REPORT_DIR
    report_dir.mkdir(parents=True, exist_ok=True)
    qwen_report_paths = qwen_report_paths or QWEN_REPORT_PATHS
    local_qwen_source, local_qwen = _load_first_qwen_metrics(qwen_report_paths)
    payload = {
        "report": "gemini_vs_local_qwen_comparison",
        "purpose": "Objective focused-smoke comparison only; no subjective ranking.",
        "gemini": _objective_metrics(gemini_report),
        "local_qwen": local_qwen,
        "local_qwen_source": str(local_qwen_source) if local_qwen_source else None,
    }
    safe_payload = redact_secrets(payload)
    json_path = report_dir / "gemini_vs_local_qwen_comparison.json"
    md_path = report_dir / "gemini_vs_local_qwen_comparison.md"
    json_path.write_text(json.dumps(safe_payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_comparison_markdown(safe_payload), encoding="utf-8")
    safe_payload["json_path"] = str(json_path)
    safe_payload["md_path"] = str(md_path)
    return safe_payload


def _load_first_qwen_metrics(paths: list[Path]) -> tuple[Path | None, dict[str, Any]]:
    for path in paths:
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        metrics = _qwen_metrics_from_report(data)
        if metrics:
            return path, metrics
    return None, {}


def _qwen_metrics_from_report(data: dict[str, Any]) -> dict[str, Any]:
    if isinstance(data.get("latest_smoke"), dict):
        return _objective_metrics({"summary": data["latest_smoke"], "probe": {"toolcall_supported": True}})
    if isinstance(data.get("summary"), dict):
        return _objective_metrics(data)
    return {}


def _objective_metrics(report: dict[str, Any]) -> dict[str, Any]:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else report
    probe = report.get("probe") if isinstance(report.get("probe"), dict) else {}
    return {
        "toolcall_supported": probe.get("toolcall_supported"),
        "passed_count": summary.get("passed_count"),
        "failed_count": summary.get("failed_count"),
        "runtime_fact_count": summary.get("runtime_fact_count"),
        "final_semantic_gate_final_failures": summary.get("final_semantic_gate_final_failures"),
        "final_answer_repair_attempts": summary.get("final_answer_repair_attempts"),
        "unsupported_claims": summary.get("unsupported_claims"),
        "no_tool_fp": summary.get("no_tool_fp"),
        "compiled_sql_count": summary.get("compiled_sql_count"),
        "compiled_api_count": summary.get("compiled_api_count"),
        "sql_calls": summary.get("sql_calls"),
        "api_calls": summary.get("api_calls"),
        "latency_sec": summary.get("total_latency_sec") or _sum_row_latency(report.get("rows") or []),
    }


def _sum_row_latency(rows: list[Any]) -> float | None:
    if not rows:
        return None
    total = 0.0
    found = False
    for row in rows:
        if isinstance(row, dict) and isinstance(row.get("total_latency_sec"), (int, float)):
            total += float(row["total_latency_sec"])
            found = True
    return round(total, 3) if found else None


def _comparison_markdown(payload: dict[str, Any]) -> str:
    gemini = payload.get("gemini") or {}
    qwen = payload.get("local_qwen") or {}
    metrics = [
        "toolcall_supported",
        "passed_count",
        "failed_count",
        "runtime_fact_count",
        "final_semantic_gate_final_failures",
        "final_answer_repair_attempts",
        "latency_sec",
        "unsupported_claims",
        "no_tool_fp",
        "compiled_sql_count",
        "compiled_api_count",
        "sql_calls",
        "api_calls",
    ]
    lines = [
        "# Gemini vs Local Qwen Focused Smoke Comparison",
        "",
        "Objective metrics only. This report does not produce subjective rankings.",
        "",
        f"- Local Qwen source: `{payload.get('local_qwen_source')}`",
        "",
        "| Metric | Gemini | Local Qwen |",
        "|---|---:|---:|",
    ]
    for metric in metrics:
        lines.append(f"| `{metric}` | `{gemini.get(metric)}` | `{qwen.get(metric)}` |")
    return "\n".join(lines) + "\n"


def main() -> int:
    report = run_gemini_v2_toolcall_smoke()
    print(
        json.dumps(
            {
                "ok": report.get("ok"),
                "skipped": report.get("skipped"),
                "summary": report.get("summary"),
                "json": report.get("json_path"),
                "md": report.get("md_path"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
