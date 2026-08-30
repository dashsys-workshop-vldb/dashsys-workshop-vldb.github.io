#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.trajectory import estimate_tokens, redact_secrets
from scripts.load_local_env import load_local_env
from scripts.run_weak_model_lift_eval import run_weak_model_lift_eval

REPORT_STEM = "weak_harness_efficiency_analysis"
TARGET_VARIANT = "weak_harness_full_v1"
BASELINE_MAX_TOKENS = 7879.3429
BASELINE_MAX_RUNTIME = 3.8912


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze token/runtime overhead for weak harness variants.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--full-public-dev", action="store_true")
    parser.add_argument("--rerun", action="store_true")
    args = parser.parse_args()
    config = Config.from_env(ROOT)
    load_local_env(config.project_root)
    payload = run_weak_harness_efficiency_analysis(
        config,
        max_examples=None if args.full_public_dev else args.limit,
        rerun=args.rerun,
    )
    print(json.dumps({"json": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.json"), "summary": payload["summary"]}, indent=2, sort_keys=True))
    return 0


def run_weak_harness_efficiency_analysis(
    config: Config | None = None,
    *,
    max_examples: int | None = None,
    rerun: bool = False,
) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports = config.outputs_dir / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    source = None
    if not rerun and max_examples is None:
        source = _load_json(config.outputs_dir / "reports" / "weak_model_lift_eval_public_dev_full.json")
        if TARGET_VARIANT not in {str(row.get("mode")) for row in source.get("rows", []) if isinstance(row, dict)}:
            source = _load_json(reports / "weak_harness_engineering_eval_public_dev_full.json")
    if not source:
        source = run_weak_model_lift_eval(config, max_examples=max_examples, variants=[TARGET_VARIANT], execute_real=True)
    rows = _target_rows(source)
    analysis_rows = [_analyze_row(row) for row in rows]
    summary = _summary(source, analysis_rows)
    report = redact_secrets(
        {
            "report_type": REPORT_STEM,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "diagnostic_only": True,
            "promotion_allowed": False,
            "packaged_runtime_changed": False,
            "packaged_default_strategy": "SQL_FIRST_API_VERIFY",
            "target_variant": TARGET_VARIANT,
            "summary": summary,
            "rows": analysis_rows,
        }
    )
    (reports / f"{REPORT_STEM}.json").write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    (reports / f"{REPORT_STEM}.md").write_text(_render_md(report), encoding="utf-8")
    return report


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _target_rows(source: dict[str, Any]) -> list[dict[str, Any]]:
    rows = source.get("rows") if isinstance(source.get("rows"), list) else []
    return [row for row in rows if row.get("mode") == TARGET_VARIANT or source.get("report_type") == "weak_harness_engineering_eval"]


def _analyze_row(row: dict[str, Any]) -> dict[str, Any]:
    trajectory = row.get("trajectory") if isinstance(row.get("trajectory"), dict) else {}
    if not trajectory and isinstance(row.get("harness_assertions"), dict):
        return {
            "query_id": row.get("query_id"),
            "prompt": row.get("prompt"),
            "estimated_tokens": row.get("estimated_tokens"),
            "runtime": row.get("runtime"),
            "tool_calls": row.get("tool_calls"),
            "top_overhead_source": "report_row_without_full_trajectory",
        }
    steps = trajectory.get("steps") if isinstance(trajectory.get("steps"), list) else []
    step_tokens = {str(step.get("kind") or f"step_{idx}"): estimate_tokens(step) for idx, step in enumerate(steps)}
    compiler = next((step.get("compiled") for step in steps if step.get("kind") == "slot_compiler"), {})
    final = next((step.get("grounding") for step in steps if step.get("kind") == "final_answer"), {})
    schema_context = compiler.get("schema_context") if isinstance(compiler, dict) else {}
    overhead = _classify_overhead(trajectory, compiler, final, step_tokens)
    return {
        "query_id": row.get("query_id"),
        "prompt": row.get("prompt"),
        "estimated_tokens": row.get("estimated_tokens") or trajectory.get("estimated_tokens"),
        "runtime": row.get("runtime") or trajectory.get("runtime"),
        "tool_calls": row.get("tool_calls") or trajectory.get("tool_call_count"),
        "llm_call_count": _llm_call_count(compiler),
        "sql_calls": sum(1 for step in steps if step.get("kind") == "sql_call"),
        "api_calls": sum(1 for step in steps if step.get("kind") == "api_call"),
        "schema_retrieval_context_size": {
            "tables": len((schema_context or {}).get("retrieved_tables") or []),
            "columns": sum(len(cols or []) for cols in ((schema_context or {}).get("retrieved_columns") or {}).values()),
            "join_hints": len((schema_context or {}).get("join_candidates") or []),
        },
        "skeleton_examples_included": len(compiler.get("sql_skeletons") or []) if isinstance(compiler, dict) else 0,
        "assertion_trace_size": estimate_tokens(row.get("harness_assertions") or {}),
        "repair_loop_calls": _repair_attempts(compiler),
        "step_token_estimates": step_tokens,
        "top_overhead_source": overhead,
    }


def _classify_overhead(trajectory: dict[str, Any], compiler: Any, final: Any, step_tokens: dict[str, int]) -> str:
    if isinstance(compiler, dict):
        schema_context = compiler.get("schema_context") if isinstance(compiler.get("schema_context"), dict) else {}
        if sum(len(cols or []) for cols in (schema_context.get("retrieved_columns") or {}).values()) > 48:
            return "schema_context_too_large"
        if len(compiler.get("sql_skeletons") or []) > 2:
            return "skeleton_examples_too_many"
        if _repair_attempts(compiler) > 0:
            return "repair_loop_unnecessary"
    if step_tokens.get("final_answer", 0) > 1200:
        return "answer_grounding_prompt_too_large"
    if sum(step_tokens.values()) > 3500:
        return "repeated_metadata"
    if trajectory.get("tool_call_count", 0) > 2:
        return "api_calls"
    return "no_clear_overhead"


def _llm_call_count(compiler: Any) -> int:
    slots = compiler.get("slots") if isinstance(compiler, dict) else {}
    usage = slots.get("_usage") if isinstance(slots, dict) else {}
    return 1 if usage else 0


def _repair_attempts(compiler: Any) -> int:
    if not isinstance(compiler, dict):
        return 0
    attempts = 0
    for candidate in compiler.get("sql_candidates") or []:
        if isinstance(candidate, dict):
            attempts += int(candidate.get("repair_attempts") or 0)
    return attempts


def _summary(source: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    mode = _target_mode(source)
    categories = Counter(row.get("top_overhead_source") for row in rows)
    avg_stage_tokens: dict[str, float] = {}
    bucket: dict[str, list[int]] = defaultdict(list)
    for row in rows:
        for key, value in (row.get("step_token_estimates") or {}).items():
            bucket[key].append(int(value or 0))
    for key, values in bucket.items():
        avg_stage_tokens[key] = round(sum(values) / len(values), 2)
    return {
        "run_label": source.get("run_label") or (source.get("summary") or {}).get("run_label"),
        "rows": len(rows),
        "variant": TARGET_VARIANT,
        "strict": mode.get("strict_final_score"),
        "sql": mode.get("sql_score"),
        "api": mode.get("api_score"),
        "answer": mode.get("answer_score"),
        "estimated_tokens": mode.get("estimated_tokens"),
        "runtime": mode.get("runtime"),
        "tool_calls": mode.get("tool_calls"),
        "avg_llm_call_count": _avg(rows, "llm_call_count"),
        "avg_sql_calls": _avg(rows, "sql_calls"),
        "avg_api_calls": _avg(rows, "api_calls"),
        "avg_repair_loop_calls": _avg(rows, "repair_loop_calls"),
        "avg_stage_tokens": avg_stage_tokens,
        "top_overhead_sources": dict(categories),
        "dominant_overhead_source": categories.most_common(1)[0][0] if categories else "no_clear_overhead",
        "token_runtime_cost_acceptable": _num(mode.get("estimated_tokens")) <= BASELINE_MAX_TOKENS
        and _num(mode.get("runtime")) <= BASELINE_MAX_RUNTIME,
    }


def _target_mode(source: dict[str, Any]) -> dict[str, Any]:
    modes = ((source.get("summary") or {}).get("modes") or []) if isinstance(source.get("summary"), dict) else []
    return next((mode for mode in modes if mode.get("mode") == TARGET_VARIANT), {})


def _avg(rows: list[dict[str, Any]], key: str) -> float:
    values = [float(row.get(key) or 0.0) for row in rows]
    return round(sum(values) / len(values), 4) if values else 0.0


def _num(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def _render_md(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Weak Harness Efficiency Analysis",
        "",
        "Diagnostic-only token/runtime analysis for `weak_harness_full_v1`.",
        "",
        f"- Run label: `{summary.get('run_label')}`",
        f"- Rows: `{summary.get('rows')}`",
        f"- Strict/API/SQL/answer: `{summary.get('strict')}` / `{summary.get('api')}` / `{summary.get('sql')}` / `{summary.get('answer')}`",
        f"- Estimated tokens/runtime/tool calls: `{summary.get('estimated_tokens')}` / `{summary.get('runtime')}` / `{summary.get('tool_calls')}`",
        f"- Dominant overhead source: `{summary.get('dominant_overhead_source')}`",
        "",
        "## Overhead Sources",
        "",
    ]
    for source, count in sorted((summary.get("top_overhead_sources") or {}).items()):
        lines.append(f"- `{source}`: `{count}`")
    lines.extend(["", "## Average Stage Tokens", ""])
    for stage, value in sorted((summary.get("avg_stage_tokens") or {}).items()):
        lines.append(f"- `{stage}`: `{value}`")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
