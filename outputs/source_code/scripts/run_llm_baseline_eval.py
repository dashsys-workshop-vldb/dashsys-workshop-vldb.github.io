#!/usr/bin/env python
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.eval_harness import EvalHarness, score_answer
from dashagent.llm_client import get_llm_client
from dashagent.llm_tool_agent import (
    GUIDED_REAL_LLM_TWO_TOOLS_BASELINE,
    LLM_CONTROLLER_OPTIMIZED_AGENT,
    RAW_REAL_LLM_TWO_TOOLS_BASELINE,
    run_optimized_llm_controller_agent,
    run_real_llm_two_tools_baseline,
)


def main() -> int:
    config = Config.from_env(ROOT)
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    harness = EvalHarness(config)
    examples = harness.load_examples()
    client = get_llm_client()
    systems = [
        RAW_REAL_LLM_TWO_TOOLS_BASELINE,
        GUIDED_REAL_LLM_TWO_TOOLS_BASELINE,
        LLM_CONTROLLER_OPTIMIZED_AGENT,
    ]
    if not client.available():
        skipped_probe = client.generate_messages([])
        reason = skipped_probe.get("reason", "LLM provider API key is not set")
        payload = {
            "skipped": True,
            "reason": reason,
            "provider": os.getenv("LLM_PROVIDER", "openai"),
            "rows": [],
            "systems": systems,
        }
        write_outputs(config, payload)
        print(json.dumps({"skipped": True, "reason": payload["reason"], "json": str(config.outputs_dir / "llm_baseline_eval.json")}, indent=2, sort_keys=True))
        return 0
    rows = []
    runners = [
        (RAW_REAL_LLM_TWO_TOOLS_BASELINE, lambda q, *, config: run_real_llm_two_tools_baseline(q, config=config, guided=False, system_name=RAW_REAL_LLM_TWO_TOOLS_BASELINE)),
        (GUIDED_REAL_LLM_TWO_TOOLS_BASELINE, lambda q, *, config: run_real_llm_two_tools_baseline(q, config=config, guided=True, system_name=GUIDED_REAL_LLM_TWO_TOOLS_BASELINE)),
        (LLM_CONTROLLER_OPTIMIZED_AGENT, run_optimized_llm_controller_agent),
    ]
    for example in examples:
        for system, runner in runners:
            start = time.perf_counter()
            result = runner(example.query, config=config)
            elapsed = time.perf_counter() - start
            valid_agent_run = bool(result.get("valid_agent_run", not result.get("skipped", False)))
            if system in {RAW_REAL_LLM_TWO_TOOLS_BASELINE, GUIDED_REAL_LLM_TWO_TOOLS_BASELINE} and not valid_agent_run:
                answer_score = None
                answer_reason = "Real LLM was called but the tool loop did not complete a valid agent run."
            else:
                answer_score, answer_reason = score_answer(result.get("final_answer", ""), example.gold_answer)
            rows.append(
                {
                    "query_id": example.query_id,
                    "query": example.query,
                    "system": system,
                    "baseline_variant": result.get("baseline_variant"),
                    "answer_score": round(answer_score, 4) if isinstance(answer_score, (int, float)) else None,
                    "answer_reason": answer_reason,
                    "tool_call_count": result.get("tool_call_count", result.get("trajectory", {}).get("tool_call_count", 0)),
                    "runtime": round(elapsed, 4),
                    "skipped": result.get("skipped", False),
                    "real_llm_called": result.get("real_llm_called", bool(result.get("real_llm_used"))),
                    "provider": result.get("llm_provider"),
                    "model": result.get("llm_model"),
                    "tool_calls_executed": result.get("tool_calls_executed", result.get("tool_call_count", 0) > 0),
                    "valid_agent_run": valid_agent_run,
                    "skipped_or_failed": result.get("skipped_or_failed", result.get("skipped", False) or not valid_agent_run),
                    "failure_reason": result.get("failure_reason", result.get("skipped_reason", "")),
                    "llm_turn_count": result.get("trajectory", {}).get("llm_turn_count", len(result.get("llm_turns", []))),
                    "llm_tool_calls": result.get("llm_tool_calls", result.get("trajectory", {}).get("llm_tool_calls", [])),
                    "validation_results": result.get("validation_results", result.get("trajectory", {}).get("validation_results", [])),
                    "execution_previews": result.get("execution_previews", result.get("trajectory", {}).get("execution_previews", [])),
                    "successful_evidence_count": result.get("successful_evidence_count", 0),
                    "invalid_tool_call_count": result.get("invalid_tool_call_count", 0),
                    "duplicate_invalid_call_count": result.get("duplicate_invalid_call_count", 0),
                    "repaired_endpoint_count": result.get("repaired_endpoint_count", 0),
                    "schema_hint_injected": result.get("schema_hint_injected", 0),
                    "dry_run_only_api_count": result.get("dry_run_only_api_count", 0),
                    "unsupported_negative_answer_count": result.get("unsupported_negative_answer_count", 0),
                    "failure_categories": result.get("failure_categories", {}),
                    "prompt_context_tokens": result.get("prompt_context_tokens", result.get("trajectory", {}).get("prompt_context_tokens", 0)),
                    "final_answer": result.get("final_answer", ""),
                }
            )
    payload = {"skipped": False, "rows": rows, "systems": systems}
    write_outputs(config, payload)
    print(json.dumps({"skipped": False, "rows": len(rows), "json": str(config.outputs_dir / "llm_baseline_eval.json")}, indent=2, sort_keys=True))
    return 0


def write_outputs(config: Config, payload: dict) -> None:
    json_path = config.outputs_dir / "llm_baseline_eval.json"
    md_path = config.outputs_dir / "llm_baseline_comparison.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    lines = ["# LLM Baseline Comparison", ""]
    if payload.get("skipped"):
        lines.append(f"Real LLM baseline systems were skipped because {payload.get('reason')}.")
    else:
        lines.extend(["| System | Rows | Valid runs | Failed runs | Avg answer score on valid runs | Avg tool calls on valid runs |", "| --- | ---: | ---: | ---: | ---: | ---: |"])
        for system in payload.get("systems", []):
            rows = [row for row in payload.get("rows", []) if row.get("system") == system]
            valid_rows = [row for row in rows if row.get("valid_agent_run")]
            failed_rows = [row for row in rows if row.get("skipped_or_failed") and not row.get("valid_agent_run")]
            scored_rows = [row for row in valid_rows if isinstance(row.get("answer_score"), (int, float))]
            avg_answer = sum(row.get("answer_score", 0) for row in scored_rows) / len(scored_rows) if scored_rows else 0
            avg_tools = sum(row.get("tool_call_count", 0) for row in valid_rows) / len(valid_rows) if valid_rows else 0
            lines.append(f"| {system} | {len(rows)} | {len(valid_rows)} | {len(failed_rows)} | {avg_answer:.4f} | {avg_tools:.2f} |")
        failed_real = [
            row for row in payload.get("rows", [])
            if row.get("system") in {RAW_REAL_LLM_TWO_TOOLS_BASELINE, GUIDED_REAL_LLM_TWO_TOOLS_BASELINE}
            and row.get("real_llm_called")
            and not row.get("valid_agent_run")
        ]
        if failed_real:
            lines.extend(
                [
                    "",
                    "## Failed Real LLM Tool Loops",
                    "",
                    "These rows are real LLM calls, but they are not counted as successful real tool-using baseline runs.",
                    "",
                    "| Query ID | Tool calls executed? | Failure reason |",
                    "| --- | --- | --- |",
                ]
            )
            for row in failed_real[:20]:
                lines.append(f"| `{row.get('query_id')}` | {row.get('tool_calls_executed')} | {row.get('failure_reason')} |")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
