#!/usr/bin/env python
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.trajectory import redact_secrets
from scripts.run_llm_controller_failure_decomposition import run_llm_controller_failure_decomposition


REPORT_STEM = "llm_agent_trace_decomposition"


def main() -> int:
    config = Config.from_env(ROOT)
    report = run_llm_agent_trace_decomposition(config)
    print(
        json.dumps(
            {
                "json": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.json"),
                "markdown": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.md"),
                "rows": report.get("summary", {}).get("rows"),
                "instrumentation_gap_count": report.get("summary", {}).get("instrumentation_gap_count"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def run_llm_agent_trace_decomposition(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    controller = run_llm_controller_failure_decomposition(config)
    rows = [_row_from_controller(row) for row in controller.get("rows", [])]
    stages = Counter(row.get("failure_stage") for row in rows)
    report = redact_secrets(
        {
            "report_type": REPORT_STEM,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "diagnostic_only": True,
            "promotion_allowed": False,
            "new_llm_calls": False,
            "sdk_only_policy": True,
            "source_report": "outputs/reports/llm_controller_failure_decomposition.json",
            "summary": {
                "rows": len(rows),
                "failure_stage_distribution": dict(stages),
                "instrumentation_gap_count": sum(1 for row in rows if row.get("instrumentation_gap")),
                "controller_remains_unpromoted": True,
            },
            "rows": rows,
        }
    )
    (reports_dir / f"{REPORT_STEM}.json").write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    (reports_dir / f"{REPORT_STEM}.md").write_text(_render_md(report), encoding="utf-8")
    return report


def _row_from_controller(row: dict[str, Any]) -> dict[str, Any]:
    rewrite = row.get("llm_rewrite_result") or {}
    router = row.get("router_decision") or {}
    backend = row.get("backend_tool_result") or {}
    verifier = row.get("verifier_behavior") or {}
    stage = _failure_stage(row)
    return {
        "query_id": row.get("query_id"),
        "prompt": row.get("query"),
        "model_backend": "artifact_replay_no_new_llm_call",
        "tool_schema_given": "unavailable_from_existing_artifact",
        "router_decision": router,
        "backend_tool_result": backend,
        "llm_rewrite_result": rewrite,
        "verifier_decision": verifier,
        "final_answer": rewrite.get("final_controller_answer"),
        "failure_stage": stage,
        "instrumentation_gap": bool(row.get("instrumentation_gap")),
        "pre_verifier_proposed_answer_captured": rewrite.get("proposed_llm_final_answer") != "unavailable_from_existing_artifact",
    }


def _failure_stage(row: dict[str, Any]) -> str:
    category = row.get("loss_category")
    rewrite = row.get("llm_rewrite_result") or {}
    verifier = row.get("verifier_behavior") or {}
    backend = row.get("backend_tool_result") or {}
    if category == "controller_helped":
        return "no_clear_failure"
    if rewrite.get("rewrite_hurt_answer_score"):
        return "answer_shape_wrong"
    if verifier.get("over_corrected"):
        return "verifier_overcorrected"
    if verifier.get("under_corrected"):
        return "verifier_undercorrected"
    if not backend.get("evidence_available"):
        return "no_tool_called_when_needed"
    if backend.get("sql_score") not in (None, 0) and float(backend.get("sql_score") or 0) < 0.5:
        return "wrong_sql_table"
    if backend.get("api_score") not in (None, 0) and float(backend.get("api_score") or 0) < 0.5:
        return "wrong_api_endpoint"
    return "no_clear_failure"


def _render_md(report: dict[str, Any]) -> str:
    summary = report.get("summary", {})
    lines = [
        "# LLM Agent Trace Decomposition",
        "",
        "Artifact replay only. No new hosted LLM calls are made and the controller is not promoted.",
        "",
        f"- Rows: `{summary.get('rows')}`",
        f"- Instrumentation gaps: `{summary.get('instrumentation_gap_count')}`",
        "",
        "## Failure Stage Distribution",
        "",
    ]
    for key, value in sorted((summary.get("failure_stage_distribution") or {}).items()):
        lines.append(f"- `{key}`: `{value}`")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
