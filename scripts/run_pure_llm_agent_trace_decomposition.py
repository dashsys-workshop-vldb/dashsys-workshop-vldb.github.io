#!/usr/bin/env python
from __future__ import annotations

import json
import argparse
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

REPORT_STEM = "pure_llm_agent_trace_decomposition"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stabilization-set", action="store_true", help="Decompose the Pure LLM stabilization report.")
    args = parser.parse_args()
    config = Config.from_env(ROOT)
    payload = run_pure_llm_agent_trace_decomposition(config, stabilization_set=args.stabilization_set)
    print(json.dumps({"json": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.json"), "rows": payload["summary"]["rows"]}, indent=2))
    return 0


def run_pure_llm_agent_trace_decomposition(config: Config | None = None, *, stabilization_set: bool = False) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    source = "pure_llm_tool_agent_stabilization.json" if stabilization_set else "pure_llm_tool_agent_eval.json"
    eval_payload = _load_json(reports_dir / source)
    rows = [_decompose(row) for row in eval_payload.get("rows", [])]
    stages = Counter(row["failure_stage"] for row in rows)
    payload = redact_secrets(
        {
            "report_type": REPORT_STEM,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "diagnostic_only": True,
            "promotion_allowed": False,
            "stabilization_set": stabilization_set,
            "source_report": f"outputs/reports/{source}",
            "summary": {"rows": len(rows), "failure_distribution": dict(stages)},
            "rows": rows,
        }
    )
    (reports_dir / f"{REPORT_STEM}.json").write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    (reports_dir / f"{REPORT_STEM}.md").write_text(_render_md(payload), encoding="utf-8")
    return payload


def _decompose(row: dict[str, Any]) -> dict[str, Any]:
    trajectory = row.get("trajectory") if isinstance(row.get("trajectory"), dict) else {}
    steps = trajectory.get("steps") if isinstance(trajectory.get("steps"), list) else []
    sql_steps = [step for step in steps if step.get("kind") == "sql_call"]
    api_steps = [step for step in steps if step.get("kind") == "api_call"]
    trace = row.get("trace_assertions") if isinstance(row.get("trace_assertions"), dict) else trajectory.get("trace_assertions", {})
    return {
        "query_id": row.get("query_id"),
        "prompt_id": row.get("prompt_id"),
        "category": row.get("category"),
        "prompt": row.get("prompt"),
        "baseline_variant": row.get("variant") or row.get("system"),
        "llm_plan": next((step.get("plan") for step in steps if step.get("kind") == "llm_plan"), None),
        "did_llm_plan": trace.get("did_llm_plan"),
        "did_llm_choose_tool": trace.get("did_llm_choose_tool"),
        "selected_tool": trace.get("selected_tool"),
        "tool_calls_attempted": len(sql_steps) + len(api_steps),
        "execute_sql_call_content": sql_steps[0].get("sql") if sql_steps else None,
        "sql_candidate": trace.get("sql_candidate"),
        "sql_validation_ok": trace.get("sql_validation_ok"),
        "sql_repair_attempted": trace.get("sql_repair_attempted"),
        "sql_repair_success": trace.get("sql_repair_success"),
        "sql_validation_result": sql_steps[0].get("validation") if sql_steps else None,
        "sql_execution_result": sql_steps[0].get("result") if sql_steps else None,
        "call_api_endpoint_selected": api_steps[0].get("url") if api_steps else None,
        "api_endpoint_candidate": trace.get("api_endpoint_candidate"),
        "api_endpoint_validation_ok": trace.get("api_endpoint_validation_ok"),
        "api_validation_result": api_steps[0].get("validation") if api_steps else None,
        "api_execution_result": api_steps[0].get("result") if api_steps else None,
        "tool_execution_ok": trace.get("tool_execution_ok"),
        "tool_result_used_in_answer": trace.get("tool_result_used_in_answer"),
        "final_answer": row.get("trajectory", {}).get("final_answer") if isinstance(row.get("trajectory"), dict) else None,
        "strict_score_components": {
            "strict_final_score": row.get("strict_final_score"),
            "sql_score": row.get("sql_score"),
            "api_score": row.get("api_score"),
            "answer_score": row.get("answer_score"),
        },
        "unsupported_claims": row.get("unsupported_claim_count", 0),
        "failure_stage": row.get("failure_stage") or _infer_stage(row, sql_steps, api_steps),
    }


def _infer_stage(row: dict[str, Any], sql_steps: list[dict[str, Any]], api_steps: list[dict[str, Any]]) -> str:
    if not sql_steps and not api_steps:
        return "no_tool_called_when_needed"
    if sql_steps and not (sql_steps[0].get("validation") or {}).get("ok", False):
        return "invalid_sql"
    if row.get("unsupported_claim_count"):
        return "unsupported_claim_added"
    return "no_clear_failure"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"rows": []}
    return json.loads(path.read_text(encoding="utf-8"))


def _render_md(payload: dict[str, Any]) -> str:
    lines = ["# Pure LLM Agent Trace Decomposition", "", "Diagnostic-only trace-level failure report.", ""]
    for stage, count in sorted(payload.get("summary", {}).get("failure_distribution", {}).items()):
        lines.append(f"- `{stage}`: `{count}`")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
