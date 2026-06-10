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
from scripts.load_local_env import load_local_env

REPORT_STEM = "pure_llm_sql_zero_root_cause_analysis"


def main() -> int:
    config = Config.from_env(ROOT)
    load_local_env(config.project_root)
    report = run_analysis(config)
    print(json.dumps({"json": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.json"), "sql_failure_rows": report["summary"]["sql_failure_rows"]}, indent=2))
    return 0


def run_analysis(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    sources = [
        reports_dir / "pure_llm_tool_agent_eval.json",
        reports_dir / "pure_llm_structured_sql_plan_trial.json",
        reports_dir / "pure_llm_sql_generation_failure_analysis.json",
        reports_dir / "pure_llm_bounded_sql_score_audit.json",
        reports_dir / "pure_llm_sql_semantic_quality_audit.json",
    ]
    rows = _collect_rows(sources)
    failures = [_failure_record(row) for row in rows if _is_sql_scored_failure(row)]
    category_counts = Counter(record["failure_category"] for record in failures)
    dominant = category_counts.most_common(1)[0][0] if category_counts else "unavailable"
    report = redact_secrets(
        {
            "report_type": REPORT_STEM,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "diagnostic_only": True,
            "promotion_allowed": False,
            "source_files": [str(path) for path in sources if path.exists()],
            "summary": {
                "rows_considered": len(rows),
                "sql_failure_rows": len(failures),
                "failure_categories": dict(sorted(category_counts.items())),
                "dominant_failure_category": dominant,
                "sql_score_zero_cause": _cause_statement(category_counts),
                "most_promising_fixes": _promising_fixes(category_counts),
                "model_vs_scaffold_assessment": _model_vs_scaffold(category_counts),
            },
            "failures": failures,
        }
    )
    (reports_dir / f"{REPORT_STEM}.json").write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    (reports_dir / f"{REPORT_STEM}.md").write_text(_render_md(report), encoding="utf-8")
    return report


def _collect_rows(paths: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in paths:
        payload = _load_json(path)
        candidates = []
        if isinstance(payload.get("rows"), list):
            candidates.extend(payload["rows"])
        if isinstance(payload.get("failures"), list):
            candidates.extend(payload["failures"])
        for row in candidates:
            key = json.dumps(
                {
                    "source": path.name,
                    "query_id": row.get("query_id"),
                    "prompt_id": row.get("prompt_id"),
                    "variant": row.get("variant") or row.get("system"),
                    "failure": row.get("failure_stage") or row.get("failure_reason"),
                    "sql": row.get("raw_sql_candidate") or row.get("compiled_sql"),
                },
                sort_keys=True,
                default=str,
            )
            if key in seen:
                continue
            seen.add(key)
            cloned = dict(row)
            cloned["_source_file"] = str(path)
            rows.append(cloned)
    return rows


def _is_sql_scored_failure(row: dict[str, Any]) -> bool:
    if isinstance(row.get("sql_score"), (int, float)) and float(row["sql_score"]) <= 0.0:
        return True
    stage = str(row.get("failure_stage") or row.get("failure_reason") or "").lower()
    return "sql" in stage or stage in {"repair_failed", "no_sql_generated", "hallucinated_table", "hallucinated_column"}


def _failure_record(row: dict[str, Any]) -> dict[str, Any]:
    trajectory = row.get("trajectory") if isinstance(row.get("trajectory"), dict) else {}
    sql_step = next((step for step in trajectory.get("steps", []) if step.get("kind") == "sql_call"), {})
    attempts = sql_step.get("attempts") if isinstance(sql_step.get("attempts"), list) else []
    last_attempt = attempts[-1] if attempts else {}
    plan = last_attempt.get("structured_sql_plan") or row.get("llm_sql_plan") or {}
    compiled = last_attempt.get("compile") if isinstance(last_attempt.get("compile"), dict) else {}
    validation = sql_step.get("validation") if isinstance(sql_step.get("validation"), dict) else row.get("sql_validator_result", {})
    category = _category(row, sql_step, last_attempt, validation)
    return redact_secrets(
        {
            "query_id": row.get("query_id"),
            "prompt_id": row.get("prompt_id"),
            "prompt": row.get("prompt"),
            "variant": row.get("variant") or row.get("system"),
            "route_tool_choice": _selected_tool(sql_step, trajectory),
            "sql_called": bool(sql_step or row.get("raw_sql_candidate")),
            "structured_sql_plan": plan,
            "selected_table": (plan or {}).get("primary_table") if isinstance(plan, dict) else None,
            "selected_columns": (compiled.get("selected_columns") or row.get("selected_columns") or []),
            "selected_filters": (compiled.get("filters") or row.get("filters") or []),
            "selected_aggregation": (compiled.get("aggregation") or row.get("aggregation")),
            "selected_join_path": (compiled.get("join_path") or row.get("selected_joins") or []),
            "compiled_sql": sql_step.get("sql") or row.get("raw_sql_candidate"),
            "sql_validation_result": validation,
            "sql_execution_result": sql_step.get("result") or row.get("execution_result"),
            "evaluator_sql_score": row.get("sql_score"),
            "answer_used_sql_result": (row.get("trace_assertions") or {}).get("sql_evidence_used_in_answer")
            if isinstance(row.get("trace_assertions"), dict)
            else None,
            "failure_category": category,
            "failure_stage": row.get("failure_stage") or row.get("failure_reason"),
            "source_file": row.get("_source_file"),
        }
    )


def _category(row: dict[str, Any], sql_step: dict[str, Any], last_attempt: dict[str, Any], validation: dict[str, Any]) -> str:
    text = json.dumps({"row": row, "sql_step": sql_step, "attempt": last_attempt, "validation": validation}, default=str).lower()
    if not sql_step and not row.get("raw_sql_candidate"):
        return "no_sql_called_when_needed"
    if "tool_trace_format" in text or "evaluator_artifact" in text:
        return "tool_trace_format_not_recognized"
    if "unknown table" in text:
        return "hallucinated_table"
    if "unknown column" in text:
        return "hallucinated_column"
    if "sql_plan_unrepairable" in text or "no executable" in text or "empty_sql" in text:
        return "no_executable_sql_after_repair"
    if validation and not validation.get("ok"):
        return "sql_called_but_invalid"
    if "wrong_table" in text:
        return "wrong_primary_table"
    if "wrong_columns" in text:
        return "wrong_columns"
    if "wrong_filter" in text or "missing_filter" in text:
        return "wrong_filter"
    if "wrong_aggregation" in text:
        return "wrong_aggregation"
    if "wrong_join" in text:
        return "wrong_join"
    if "sql_result_not_used" in text:
        return "sql_result_not_used"
    if row.get("sql_score") == 0:
        return "wrong_sql_shape"
    return "no_clear_sql_failure"


def _selected_tool(sql_step: dict[str, Any], trajectory: dict[str, Any]) -> str | None:
    if sql_step:
        return "execute_sql"
    api_step = next((step for step in trajectory.get("steps", []) if step.get("kind") == "api_call"), {})
    if api_step:
        return "call_api"
    return None


def _cause_statement(counts: Counter[str]) -> str:
    if not counts:
        return "No current SQL-zero evidence was available in source reports."
    dominant = counts.most_common(1)[0][0]
    if dominant == "no_sql_called_when_needed":
        return "SQL score is primarily zero because the agent did not call execute_sql when SQL evidence was needed."
    if dominant == "no_executable_sql_after_repair":
        return "SQL score is primarily zero because structured plans did not survive compile/validation/repair into executable SQL."
    if dominant in {"wrong_primary_table", "wrong_columns", "wrong_filter", "wrong_aggregation", "wrong_sql_shape"}:
        return "SQL score is primarily zero because SQL validates but does not match the prompt semantics."
    if dominant == "tool_trace_format_not_recognized":
        return "SQL score is primarily zero because evaluator-recognized SQL artifacts were missing or malformed."
    return f"SQL score is primarily zero due to `{dominant}`."


def _promising_fixes(counts: Counter[str]) -> list[str]:
    fixes: list[str] = []
    if any(counts.get(key) for key in ("wrong_primary_table", "wrong_columns", "wrong_filter", "wrong_aggregation", "wrong_sql_shape")):
        fixes.append("retrieval-ranked structured SQL candidates with semantic verification")
    if counts.get("no_executable_sql_after_repair") or counts.get("sql_called_but_invalid"):
        fixes.append("SQL reviewer/repair loop using compiler, validator, and execution-probe feedback")
    if counts.get("sql_result_not_used") or counts.get("tool_trace_format_not_recognized"):
        fixes.append("executed-SQL evidence bridge and final-answer grounding fallback")
    if counts.get("no_sql_called_when_needed"):
        fixes.append("evidence-source planner and tool-choice validation")
    return fixes or ["continue row-level trace analysis before promotion"]


def _model_vs_scaffold(counts: Counter[str]) -> dict[str, Any]:
    scaffold = sum(counts.get(key, 0) for key in ("no_sql_called_when_needed", "tool_trace_format_not_recognized", "sql_result_not_used"))
    model = sum(counts.get(key, 0) for key in ("wrong_primary_table", "wrong_columns", "wrong_filter", "wrong_aggregation", "wrong_sql_shape"))
    repair = sum(counts.get(key, 0) for key in ("sql_called_but_invalid", "no_executable_sql_after_repair", "hallucinated_table", "hallucinated_column"))
    return {
        "scaffold_weakness_count": scaffold,
        "model_semantic_weakness_count": model,
        "repair_validation_bottleneck_count": repair,
        "assessment": "mixed_model_semantics_and_scaffold" if model and scaffold else ("model_semantics_dominant" if model else "scaffold_or_repair_dominant"),
    }


def _render_md(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Pure LLM SQL Zero Root Cause Analysis",
        "",
        "Diagnostic-only analysis. Packaged `SQL_FIRST_API_VERIFY` runtime is unchanged.",
        "",
        f"- Rows considered: `{summary.get('rows_considered')}`",
        f"- SQL failure rows: `{summary.get('sql_failure_rows')}`",
        f"- Dominant category: `{summary.get('dominant_failure_category')}`",
        f"- Cause: {summary.get('sql_score_zero_cause')}",
        "",
        "## Failure Categories",
        "",
    ]
    for category, count in (summary.get("failure_categories") or {}).items():
        lines.append(f"- `{category}`: `{count}`")
    lines.extend(["", "## Promising Fixes", ""])
    for fix in summary.get("most_promising_fixes") or []:
        lines.append(f"- {fix}")
    lines.append("")
    return "\n".join(lines)


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


if __name__ == "__main__":
    raise SystemExit(main())
