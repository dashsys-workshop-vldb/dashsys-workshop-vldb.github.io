#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.api_client import AdobeAPIClient
from dashagent.config import Config
from dashagent.db import DuckDBDatabase
from dashagent.endpoint_catalog import EndpointCatalog
from dashagent.eval_harness import (
    EvalHarness,
    aggregate_strict_correctness,
    first_generated_sql,
    generated_api_calls,
    score_answer_strict,
    score_api_strict,
    score_sql_strict,
)
from dashagent.llm_client import get_llm_client
from dashagent.llm_tool_agent import (
    GUIDED_REAL_LLM_TWO_TOOLS_BASELINE,
    LLM_CONTROLLER_OPTIMIZED_AGENT,
    RAW_REAL_LLM_TWO_TOOLS_BASELINE,
)
from dashagent.pure_llm_tool_agent import (
    FULL_PURE_LLM_TOOL_AGENT_V1,
    PURE_LLM_TOOL_AGENT_VARIANTS,
    pure_llm_baseline_definitions,
    run_pure_llm_tool_agent_variant,
)
from dashagent.schema_index import SchemaIndex
from dashagent.trajectory import estimate_tokens, redact_secrets
from scripts.load_local_env import load_local_env

REPORT_STEM = "pure_llm_tool_agent_eval"
DEFINITION_STEM = "pure_llm_baseline_definition"
STABILIZATION_STEM = "pure_llm_tool_agent_stabilization"
STRUCTURED_SQL_PLAN_STEM = "pure_llm_structured_sql_plan_trial"
SQL_FAILURE_STEM = "pure_llm_sql_generation_failure_analysis"
STABILIZATION_SET_PATH = ROOT / "data" / "pure_llm_stabilization_set.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-only", action="store_true", help="Do not execute new hosted LLM calls; score existing artifacts only.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--variant", action="append", choices=PURE_LLM_TOOL_AGENT_VARIANTS)
    parser.add_argument("--stabilization-set", action="store_true", help="Run the small diagnostic Pure LLM stabilization set instead of public/dev strict rows.")
    args = parser.parse_args()
    config = Config.from_env(ROOT)
    load_local_env(config.project_root)
    payload = run_pure_llm_tool_agent_eval(
        config,
        execute_real=not args.artifact_only,
        max_examples=args.limit,
        variants=args.variant,
        stabilization_set=args.stabilization_set,
    )
    print(
        json.dumps(
            {
                "json": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.json"),
                "markdown": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.md"),
                "executed_new_llm_rows": payload.get("summary", {}).get("executed_new_llm_rows"),
                "best_variant": payload.get("summary", {}).get("best_variant"),
                "promotion_allowed": payload.get("promotion_allowed"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def run_pure_llm_tool_agent_eval(
    config: Config | None = None,
    *,
    execute_real: bool = True,
    max_examples: int | None = None,
    variants: list[str] | None = None,
    stabilization_set: bool = False,
) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    _write_definition_report(config)
    existing_rows = [] if stabilization_set else _existing_baseline_rows(config)
    rows: list[dict[str, Any]] = list(existing_rows)
    variants_to_run = variants or [FULL_PURE_LLM_TOOL_AGENT_V1]
    client = get_llm_client()
    backend_probe = _backend_probe(client) if execute_real else {"ok": False, "reason": "artifact_only_requested"}
    execute_new = bool(execute_real and backend_probe.get("ok"))
    skipped_reason = None if execute_new else str(backend_probe.get("reason") or "llm_backend_unavailable")
    if execute_new:
        if stabilization_set:
            rows.extend(_run_stabilization_rows(config, variants_to_run, max_examples=max_examples, client=client))
        else:
            rows.extend(_run_new_variant_rows(config, variants_to_run, max_examples=max_examples, client=client))
    else:
        if stabilization_set:
            rows.extend(_skipped_stabilization_rows(variants_to_run, max_examples=max_examples, reason=skipped_reason))
        else:
            for variant in variants_to_run:
                rows.append(
                    {
                        "system": variant,
                        "variant": variant,
                        "strict_scoring_status": "unavailable",
                        "skipped": True,
                        "reason": skipped_reason,
                        "strict_final_score": None,
                    }
                )
    summary = _stabilization_summary(rows) if stabilization_set else _summary(rows)
    payload = redact_secrets(
        {
            "report_type": REPORT_STEM,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "diagnostic_only": True,
            "official_score_claim": False,
            "promotion_allowed": False,
            "packaged_runtime_changed": False,
            "packaged_default_strategy": "SQL_FIRST_API_VERIFY",
            "stabilization_set": stabilization_set,
            "execute_real_requested": execute_real,
            "new_llm_calls_executed": execute_new,
            "backend_probe": backend_probe,
            "skipped_reason": skipped_reason,
            "variants_defined": pure_llm_baseline_definitions(),
            "summary": summary,
            "rows": rows,
        }
    )
    (reports_dir / f"{REPORT_STEM}.json").write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    (reports_dir / f"{REPORT_STEM}.md").write_text(_render_eval_md(payload), encoding="utf-8")
    if stabilization_set:
        (reports_dir / f"{STABILIZATION_STEM}.json").write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
        (reports_dir / f"{STABILIZATION_STEM}.md").write_text(_render_stabilization_md(payload), encoding="utf-8")
    if _has_structured_sql_plan_rows(rows):
        (reports_dir / f"{STRUCTURED_SQL_PLAN_STEM}.json").write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
        (reports_dir / f"{STRUCTURED_SQL_PLAN_STEM}.md").write_text(_render_structured_trial_md(payload), encoding="utf-8")
    _write_sql_failure_analysis(config, payload)
    return payload


def _write_definition_report(config: Config) -> dict[str, Any]:
    reports_dir = config.outputs_dir / "reports"
    report = {
        "report_type": DEFINITION_STEM,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "diagnostic_only": True,
        "promotion_allowed": False,
        "packaged_default_strategy": "SQL_FIRST_API_VERIFY",
        "variants": pure_llm_baseline_definitions(),
    }
    (reports_dir / f"{DEFINITION_STEM}.json").write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    lines = ["# Pure LLM Baseline Definition", "", "All variants are diagnostic/shadow-only."]
    for item in report["variants"]:
        lines.append(f"- `{item['variant']}`: {item['description']}")
    (reports_dir / f"{DEFINITION_STEM}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def _backend_probe(client: Any) -> dict[str, Any]:
    if not client.available():
        return {"ok": False, "reason": "llm_backend_unavailable", "provider": client.provider_name(), "model": client.model_name()}
    response = client.generate("Return JSON only.", '{"ok": true}')
    if not response.get("ok"):
        return redact_secrets(
            {
                "ok": False,
                "reason": "llm_backend_request_failed",
                "provider": client.provider_name(),
                "model": client.model_name(),
                "error": response.get("error") or response.get("reason"),
            }
        )
    return {"ok": True, "provider": client.provider_name(), "model": client.model_name()}


def _existing_baseline_rows(config: Config) -> list[dict[str, Any]]:
    path = config.outputs_dir / "llm_strict_baseline_eval.json"
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    allowed = {RAW_REAL_LLM_TWO_TOOLS_BASELINE, GUIDED_REAL_LLM_TWO_TOOLS_BASELINE, LLM_CONTROLLER_OPTIMIZED_AGENT}
    if isinstance(payload.get("rows"), list):
        rows = []
        for item in payload["rows"]:
            if item.get("system") not in allowed:
                continue
            failures = item.get("failure_categories") if isinstance(item.get("failure_categories"), dict) else {}
            rows.append(
                redact_secrets(
                    {
                        "query_id": item.get("query_id"),
                        "prompt": item.get("query"),
                        "system": item.get("system"),
                        "variant": item.get("system"),
                        "strict_scoring_status": item.get("strict_scoring_status"),
                        "strict_final_score": item.get("strict_final_score"),
                        "strict_correctness": item.get("strict_correctness"),
                        "answer_score": item.get("answer_score"),
                        "sql_score": item.get("sql_score"),
                        "api_score": item.get("api_score"),
                        "tool_calls": item.get("tool_calls"),
                        "estimated_tokens": item.get("estimated_tokens"),
                        "runtime": item.get("runtime"),
                        "unsupported_claim_count": int(failures.get("answer_unsupported") or 0),
                        "failure_stage": _existing_failure_stage(item),
                        "failure_categories": failures,
                        "trajectory": item.get("trajectory", {}),
                        "source": "existing_llm_strict_baseline_eval_rows",
                    }
                )
            )
        if rows:
            return rows
    rows = []
    for item in payload.get("per_strategy", []):
        if item.get("system") not in allowed:
            continue
        rows.append(
            {
                "system": item.get("system"),
                "variant": item.get("system"),
                "strict_scoring_status": item.get("strict_scoring_status"),
                "strict_final_score": item.get("strict_final_score"),
                "strict_correctness": item.get("strict_correctness"),
                "answer_score": item.get("answer_score"),
                "sql_score": item.get("sql_score"),
                "api_score": item.get("api_score"),
                "tool_calls": item.get("tool_calls"),
                "estimated_tokens": item.get("estimated_tokens"),
                "runtime": item.get("runtime"),
                "rows_attempted": item.get("rows_attempted"),
                "failure_categories": item.get("failure_categories", {}),
                "source": "existing_llm_strict_baseline_eval",
            }
        )
    return rows


def _existing_failure_stage(row: dict[str, Any]) -> str:
    failures = row.get("failure_categories") if isinstance(row.get("failure_categories"), dict) else {}
    if failures.get("invalid_tool_call") or failures.get("validation_failed"):
        return "invalid_sql"
    if failures.get("missing_sql"):
        return "no_tool_called_when_needed"
    if failures.get("missing_api"):
        return "api_endpoint_selection_wrong"
    if failures.get("answer_unsupported"):
        return "unsupported_claim_added"
    return "no_clear_failure"


def _run_new_variant_rows(config: Config, variants: list[str], *, max_examples: int | None, client: Any) -> list[dict[str, Any]]:
    harness = EvalHarness(config)
    examples = harness.load_examples()
    if max_examples:
        examples = examples[:max_examples]
    db = DuckDBDatabase(config)
    schema = SchemaIndex.build(db)
    catalog = EndpointCatalog(config)
    api_client = AdobeAPIClient(config)
    rows = []
    for example in examples:
        for variant in variants:
            result = run_pure_llm_tool_agent_variant(
                example.query,
                variant=variant,
                db=db,
                schema_index=schema,
                endpoint_catalog=catalog,
                api_client=api_client,
                llm_client=client,
            )
            rows.append(_score_variant_result(harness, example, variant, result))
    db.close()
    return rows


def _run_stabilization_rows(config: Config, variants: list[str], *, max_examples: int | None, client: Any) -> list[dict[str, Any]]:
    prompts = _load_stabilization_set()
    if max_examples:
        prompts = prompts[:max_examples]
    db = DuckDBDatabase(config)
    schema = SchemaIndex.build(db)
    catalog = EndpointCatalog(config)
    api_client = AdobeAPIClient(config)
    rows = []
    for item in prompts:
        for variant in variants:
            result = run_pure_llm_tool_agent_variant(
                item["prompt"],
                variant=variant,
                db=db,
                schema_index=schema,
                endpoint_catalog=catalog,
                api_client=api_client,
                llm_client=client,
            )
            rows.append(_stabilization_row(item, variant, result))
    db.close()
    return rows


def _skipped_stabilization_rows(variants: list[str], *, max_examples: int | None, reason: str | None) -> list[dict[str, Any]]:
    prompts = _load_stabilization_set()
    if max_examples:
        prompts = prompts[:max_examples]
    rows = []
    for item in prompts:
        for variant in variants:
            rows.append(
                {
                    "prompt_id": item.get("prompt_id"),
                    "prompt": item.get("prompt"),
                    "category": item.get("category"),
                    "expected_tool_family": item.get("expected_tool_family"),
                    "system": variant,
                    "variant": variant,
                    "strict_scoring_status": "not_applicable_stabilization",
                    "stabilization_row": True,
                    "skipped": True,
                    "reason": reason,
                    "failure_stage": "llm_unavailable",
                    "trace_assertions": {
                        "did_llm_plan": False,
                        "did_llm_choose_tool": False,
                        "selected_tool": None,
                        "sql_validation_ok": False,
                        "sql_repair_attempted": False,
                        "sql_repair_success": False,
                        "api_endpoint_validation_ok": False,
                        "tool_execution_ok": False,
                        "tool_result_used_in_answer": False,
                        "unsupported_claim_count": 0,
                    },
                }
            )
    return rows


def _load_stabilization_set() -> list[dict[str, Any]]:
    if not STABILIZATION_SET_PATH.exists():
        return []
    payload = json.loads(STABILIZATION_SET_PATH.read_text(encoding="utf-8"))
    return payload if isinstance(payload, list) else []


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _stabilization_row(item: dict[str, Any], variant: str, result: dict[str, Any]) -> dict[str, Any]:
    trajectory = result.get("trajectory") if isinstance(result.get("trajectory"), dict) else {}
    trace = result.get("trace_assertions") if isinstance(result.get("trace_assertions"), dict) else trajectory.get("trace_assertions", {})
    return redact_secrets(
        {
            "prompt_id": item.get("prompt_id"),
            "prompt": item.get("prompt"),
            "category": item.get("category"),
            "expected_tool_family": item.get("expected_tool_family"),
            "system": variant,
            "variant": variant,
            "strict_scoring_status": "not_applicable_stabilization",
            "stabilization_row": True,
            "final_answer": result.get("final_answer"),
            "unsupported_claim_count": result.get("unsupported_claim_count", 0),
            "rejected_unsupported_claim_count": result.get("rejected_unsupported_claim_count", 0),
            "tool_calls": trajectory.get("tool_call_count", 0),
            "estimated_tokens": trajectory.get("estimated_tokens", estimate_tokens(trajectory)),
            "runtime": round(float(trajectory.get("runtime") or 0.0), 4),
            "failure_stage": result.get("failure_stage") or trajectory.get("failure_stage") or "no_clear_failure",
            "trace_assertions": trace,
            "trajectory": trajectory,
        }
    )


def _score_variant_result(harness: EvalHarness, example: Any, variant: str, result: dict[str, Any]) -> dict[str, Any]:
    trajectory = result.get("trajectory") if isinstance(result.get("trajectory"), dict) else {}
    generated_sql = first_generated_sql(trajectory)
    generated_api = generated_api_calls(trajectory)
    try:
        sql_score, sql_reason = score_sql_strict(harness.executor.db, generated_sql, example.gold_sql)
        api_score, api_reason = score_api_strict(generated_api, example.gold_api)
        answer_score, answer_reason = score_answer_strict(str(result.get("final_answer") or ""), example.gold_answer)
        correctness, unscored = aggregate_strict_correctness({"sql": sql_score, "api": api_score, "answer": answer_score})
        efficiency_penalty = min(
            1.0,
            (float(trajectory.get("tool_call_count") or 0) / 8)
            + (float(trajectory.get("runtime") or 0) / 30)
            + (float(trajectory.get("estimated_tokens") or 0) / 12000),
        )
        final = correctness - 0.1 * efficiency_penalty
        status = "available"
    except Exception as exc:
        sql_score = api_score = answer_score = None
        sql_reason = api_reason = answer_reason = f"strict_scoring_failed: {type(exc).__name__}"
        correctness = 0.0
        unscored = 3
        final = None
        status = "unavailable"
    return redact_secrets(
        {
            "query_id": example.query_id,
            "prompt": example.query,
            "system": variant,
            "variant": variant,
            "strict_scoring_status": status,
            "strict_final_score": round(final, 4) if isinstance(final, (int, float)) else None,
            "strict_correctness": round(correctness, 4),
            "answer_score": round(answer_score, 4) if isinstance(answer_score, (int, float)) else None,
            "sql_score": round(sql_score, 4) if isinstance(sql_score, (int, float)) else None,
            "api_score": round(api_score, 4) if isinstance(api_score, (int, float)) else None,
            "sql_reason": sql_reason,
            "api_reason": api_reason,
            "answer_reason": answer_reason,
            "unscored_dimension_count": unscored,
            "tool_calls": trajectory.get("tool_call_count", 0),
            "estimated_tokens": trajectory.get("estimated_tokens", estimate_tokens(trajectory)),
            "runtime": round(float(trajectory.get("runtime") or 0.0), 4),
            "unsupported_claim_count": result.get("unsupported_claim_count", 0),
            "failure_stage": _failure_stage(result, generated_sql, generated_api),
            "trace_assertions": result.get("trace_assertions", {}),
            "trajectory": trajectory,
        }
    )


def _failure_stage(result: dict[str, Any], generated_sql: str | None, generated_api: list[dict[str, Any]]) -> str:
    if result.get("skipped"):
        return "llm_unavailable"
    if result.get("failure_stage"):
        return str(result["failure_stage"])
    if result.get("unsupported_claim_count"):
        return "unsupported_claim_added"
    sql_result = result.get("sql_result") if isinstance(result.get("sql_result"), dict) else {}
    if not generated_sql and sql_result.get("failure_stage"):
        return str(sql_result["failure_stage"])
    if not generated_sql and not generated_api:
        return "no_tool_called_when_needed"
    if sql_result.get("failure_stage"):
        return str(sql_result["failure_stage"])
    return "no_clear_failure"


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    systems = sorted({str(row.get("system")) for row in rows if row.get("system")})
    per_system = []
    for system in systems:
        system_rows = [row for row in rows if row.get("system") == system and row.get("strict_scoring_status") == "available"]
        if not system_rows:
            per_system.append({"system": system, "strict_scoring_status": "unavailable", "rows": 0})
            continue
        row_count = sum(int(row.get("rows_attempted") or 1) for row in system_rows)
        per_system.append(
            {
                "system": system,
                "strict_scoring_status": "available",
                "rows": row_count,
                "strict_final_score": _avg(system_rows, "strict_final_score"),
                "strict_correctness": _avg(system_rows, "strict_correctness"),
                "answer_score": _avg(system_rows, "answer_score"),
                "sql_score": _avg(system_rows, "sql_score"),
                "api_score": _avg(system_rows, "api_score"),
                "tool_calls": _avg(system_rows, "tool_calls"),
                "estimated_tokens": _avg(system_rows, "estimated_tokens"),
                "runtime": _avg(system_rows, "runtime"),
                "unsupported_claims": sum(int(row.get("unsupported_claim_count") or 0) for row in system_rows),
                "compile_success_rate": _trace_rate(system_rows, "structured_plan_compile_ok"),
                "sql_validation_pass_rate": _trace_rate(system_rows, "sql_validation_ok"),
            }
        )
    scored = [item for item in per_system if item.get("strict_scoring_status") == "available"]
    best = max(scored, key=lambda item: float(item.get("strict_final_score") or 0.0), default={})
    raw = next((item for item in per_system if item.get("system") == "RAW_REAL_LLM_TWO_TOOLS_BASELINE"), {})
    guided = next((item for item in per_system if item.get("system") == "GUIDED_REAL_LLM_TWO_TOOLS_BASELINE"), {})
    structured = [
        item
        for item in per_system
        if item.get("system") in PURE_LLM_TOOL_AGENT_VARIANTS
    ]
    best_structured = max(structured, key=lambda item: float(item.get("strict_final_score") or -999), default={})
    baseline_score = max(float(raw.get("strict_final_score") or 0.0), float(guided.get("strict_final_score") or 0.0))
    baseline_sql = max(float(raw.get("sql_score") or 0.0), float(guided.get("sql_score") or 0.0))
    if best_structured and (
        float(best_structured.get("strict_final_score") or 0.0) <= baseline_score
        or float(best_structured.get("sql_score") or 0.0) <= baseline_sql
    ):
        recommendation = "pure_llm_still_blocked_by_sql_generation"
    elif best_structured:
        recommendation = "pure_llm_sql_grounding_improved_keep_shadow"
    else:
        recommendation = "pure_llm_still_too_weak"
    return {
        "systems": per_system,
        "best_variant": best.get("system"),
        "best_strict_score": best.get("strict_final_score"),
        "executed_new_llm_rows": sum(1 for row in rows if row.get("query_id") and row.get("variant") in PURE_LLM_TOOL_AGENT_VARIANTS),
        "recommendation": recommendation,
    }


def _stabilization_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    attempted = [row for row in rows if row.get("stabilization_row")]
    tool_needed = [
        row for row in attempted if row.get("expected_tool_family") in {"sql", "api", "sql_api"}
    ]
    traces = [row.get("trace_assertions") if isinstance(row.get("trace_assertions"), dict) else {} for row in attempted]
    sql_rows = [trace for trace in traces if trace.get("selected_tool") == "execute_sql" or trace.get("sql_candidate")]
    api_rows = [trace for trace in traces if trace.get("selected_tool") == "call_api" or trace.get("api_endpoint_candidate")]
    repair_attempts = [trace for trace in traces if trace.get("sql_repair_attempted")]
    failure_counts: dict[str, int] = {}
    for row in attempted:
        stage = str(row.get("failure_stage") or "no_clear_failure")
        failure_counts[stage] = failure_counts.get(stage, 0) + 1
    return {
        "prompts_attempted": len(attempted),
        "tool_needed_count": len(tool_needed),
        "tool_called_when_needed_rate": _rate([bool((row.get("trace_assertions") or {}).get("did_llm_choose_tool")) for row in tool_needed]),
        "sql_validation_pass_rate": _rate([bool(trace.get("sql_validation_ok")) for trace in sql_rows]),
        "compile_success_rate": _rate([bool(trace.get("structured_plan_compile_ok")) for trace in traces if trace.get("structured_plan_compile_ok") is not None]),
        "sql_repair_success_rate": _rate([bool(trace.get("sql_repair_success")) for trace in repair_attempts]),
        "api_endpoint_validation_pass_rate": _rate([bool(trace.get("api_endpoint_validation_ok")) for trace in api_rows]),
        "tool_result_used_rate": _rate([bool(trace.get("tool_result_used_in_answer")) for trace in traces if trace.get("did_llm_choose_tool")]),
        "unsupported_claim_count": sum(int(row.get("unsupported_claim_count") or 0) for row in attempted),
        "rejected_unsupported_claim_count": sum(int(row.get("rejected_unsupported_claim_count") or 0) for row in attempted),
        "failure_stage_distribution": failure_counts,
        "examples_still_failing": [
            {
                "prompt_id": row.get("prompt_id"),
                "category": row.get("category"),
                "failure_stage": row.get("failure_stage"),
            }
            for row in attempted
            if row.get("failure_stage") not in {"no_clear_failure"}
        ][:20],
    }


def _rate(values: list[bool]) -> float | None:
    if not values:
        return None
    return round(sum(1 for value in values if value) / len(values), 4)


def _avg(rows: list[dict[str, Any]], key: str) -> float:
    values = [float(row[key]) for row in rows if isinstance(row.get(key), (int, float))]
    return round(sum(values) / len(values), 4) if values else 0.0


def _trace_rate(rows: list[dict[str, Any]], key: str) -> float | None:
    values = []
    for row in rows:
        trace = row.get("trace_assertions")
        if not isinstance(trace, dict) and isinstance(row.get("trajectory"), dict):
            trace = row["trajectory"].get("trace_assertions")
        if isinstance(trace, dict) and trace.get(key) is not None:
            values.append(bool(trace.get(key)))
    return _rate(values)


def _render_eval_md(payload: dict[str, Any]) -> str:
    lines = [
        "# Pure LLM Tool Agent Eval",
        "",
        "Diagnostic-only report. Packaged `SQL_FIRST_API_VERIFY` runtime is unchanged.",
        "",
        f"- New LLM calls executed: `{payload.get('new_llm_calls_executed')}`",
        f"- Promotion allowed: `{payload.get('promotion_allowed')}`",
        f"- Best variant: `{payload.get('summary', {}).get('best_variant')}`",
        "",
        "## Systems",
        "",
        "| System | Rows | Strict | SQL | API | Answer | Unsupported claims |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for item in payload.get("summary", {}).get("systems", []):
        lines.append(
            f"| `{item.get('system')}` | {item.get('rows', 0)} | {item.get('strict_final_score', 'n/a')} | {item.get('sql_score', 'n/a')} | {item.get('api_score', 'n/a')} | {item.get('answer_score', 'n/a')} | {item.get('unsupported_claims', 'n/a')} |"
        )
    lines.append("")
    return "\n".join(lines)


def _render_stabilization_md(payload: dict[str, Any]) -> str:
    summary = payload.get("summary", {})
    lines = [
        "# Pure LLM Tool Agent Stabilization",
        "",
        "Diagnostic-only stabilization report. Packaged `SQL_FIRST_API_VERIFY` runtime is unchanged.",
        "",
        f"- Prompts attempted: `{summary.get('prompts_attempted')}`",
        f"- Tool-needed count: `{summary.get('tool_needed_count')}`",
        f"- Tool called when needed rate: `{summary.get('tool_called_when_needed_rate')}`",
        f"- SQL validation pass rate: `{summary.get('sql_validation_pass_rate')}`",
        f"- Compiler success rate: `{summary.get('compile_success_rate')}`",
        f"- SQL repair success rate: `{summary.get('sql_repair_success_rate')}`",
        f"- API endpoint validation pass rate: `{summary.get('api_endpoint_validation_pass_rate')}`",
        f"- Tool result used rate: `{summary.get('tool_result_used_rate')}`",
        f"- Unsupported claim count: `{summary.get('unsupported_claim_count')}`",
        "",
        "## Failure Stages",
        "",
    ]
    for stage, count in sorted((summary.get("failure_stage_distribution") or {}).items()):
        lines.append(f"- `{stage}`: `{count}`")
    lines.append("")
    return "\n".join(lines)


def _render_structured_trial_md(payload: dict[str, Any]) -> str:
    lines = [
        "# Pure LLM Structured SQL Plan Trial",
        "",
        "Diagnostic-only report. Structured SQL plan variants remain shadow-only.",
        "",
        "## Summary",
        "",
    ]
    summary = payload.get("summary", {})
    if payload.get("stabilization_set"):
        for key in [
            "prompts_attempted",
            "tool_called_when_needed_rate",
            "compile_success_rate",
            "sql_validation_pass_rate",
            "sql_repair_success_rate",
            "unsupported_claim_count",
        ]:
            lines.append(f"- {key}: `{summary.get(key)}`")
    else:
        for item in summary.get("systems", []):
            system = str(item.get("system"))
            if (
                "structured_sql_plan" in system
                or "multi_candidate_sql" in system
                or "retrieved_schema_sql" in system
                or "reviewed_sql_repair" in system
                or "execution_guided_sql" in system
                or "evidence_grounded_sql" in system
                or "full_retrieval_repair_grounded" in system
            ):
                lines.append(
                    f"- `{item.get('system')}` rows `{item.get('rows')}` strict `{item.get('strict_final_score')}` SQL `{item.get('sql_score')}` compile `{item.get('compile_success_rate')}` unsupported `{item.get('unsupported_claims')}`"
                )
    lines.append("")
    return "\n".join(lines)


def _has_structured_sql_plan_rows(rows: list[dict[str, Any]]) -> bool:
    return any(
        "structured_sql_plan" in str(row.get("variant") or row.get("system") or "")
        or "multi_candidate_sql" in str(row.get("variant") or row.get("system") or "")
        or "retrieved_schema_sql" in str(row.get("variant") or row.get("system") or "")
        or "reviewed_sql_repair" in str(row.get("variant") or row.get("system") or "")
        or "execution_guided_sql" in str(row.get("variant") or row.get("system") or "")
        or "evidence_grounded_sql" in str(row.get("variant") or row.get("system") or "")
        or "full_retrieval_repair_grounded" in str(row.get("variant") or row.get("system") or "")
        for row in rows
    )


def _write_sql_failure_analysis(config: Config, payload: dict[str, Any]) -> dict[str, Any]:
    reports_dir = config.outputs_dir / "reports"
    rows: list[dict[str, Any]] = []
    stabilization = _load_json(reports_dir / f"{STABILIZATION_STEM}.json")
    rows.extend(stabilization.get("rows", []) if isinstance(stabilization.get("rows"), list) else [])
    rows.extend(payload.get("rows", []) if isinstance(payload.get("rows"), list) else [])
    failures = []
    for row in rows:
        failure_stage = str(row.get("failure_stage") or "")
        trajectory = row.get("trajectory") if isinstance(row.get("trajectory"), dict) else {}
        sql_step = next((step for step in trajectory.get("steps", []) if step.get("kind") == "sql_call"), {})
        if not sql_step and "sql" not in failure_stage:
            continue
        attempts = sql_step.get("attempts") if isinstance(sql_step.get("attempts"), list) else []
        last_attempt = attempts[-1] if attempts else {}
        compiled = last_attempt.get("compile") if isinstance(last_attempt.get("compile"), dict) else {}
        validation = sql_step.get("validation") if isinstance(sql_step.get("validation"), dict) else {}
        category = _sql_failure_category(last_attempt, validation, failure_stage)
        if category == "no_clear_sql_failure" and failure_stage == "no_clear_failure":
            continue
        failures.append(
            redact_secrets(
                {
                    "prompt_id": row.get("prompt_id"),
                    "query_id": row.get("query_id"),
                    "prompt": row.get("prompt"),
                    "variant": row.get("variant") or row.get("system"),
                    "expected_answer_intent": (trajectory.get("steps") or [{}])[0].get("plan", {}).get("answer_intent") if trajectory.get("steps") else None,
                    "llm_sql_plan": last_attempt.get("structured_sql_plan") or last_attempt.get("candidate"),
                    "raw_sql_candidate": sql_step.get("sql"),
                    "selected_tables": compiled.get("selected_tables") or [],
                    "selected_columns": compiled.get("selected_columns") or [],
                    "selected_joins": compiled.get("join_path") or [],
                    "filters": compiled.get("filters") or [],
                    "aggregation": compiled.get("aggregation"),
                    "sql_validator_result": validation,
                    "sqlglot_result": last_attempt.get("ast_summary"),
                    "execution_result": sql_step.get("result"),
                    "repair_attempt_count": int(sql_step.get("repair_rounds") or 0),
                    "repair_result": "success" if validation.get("ok") else "failed",
                    "failure_stage": failure_stage,
                    "failure_reason": category,
                }
            )
        )
    summary = {
        "sql_failure_count": len(failures),
        "failure_categories": _count_by(failures, "failure_reason"),
        "hallucinated_journey_table_issue": _hallucinated_journey_summary(failures),
    }
    report = {
        "report_type": SQL_FAILURE_STEM,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "diagnostic_only": True,
        "promotion_allowed": False,
        "summary": summary,
        "failures": failures,
    }
    (reports_dir / f"{SQL_FAILURE_STEM}.json").write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    (reports_dir / f"{SQL_FAILURE_STEM}.md").write_text(_render_sql_failure_md(report), encoding="utf-8")
    return report


def _sql_failure_category(attempt: dict[str, Any], validation: dict[str, Any], failure_stage: str) -> str:
    text = " ".join(str(value) for value in [attempt, validation, failure_stage]).lower()
    if "unknown table" in text:
        return "hallucinated_table"
    if "unknown column" in text:
        return "hallucinated_column"
    if "unsupported join" in text:
        return "wrong_join_path"
    if "parse" in text or "syntax" in text:
        return "invalid_sql_syntax"
    if "sql_plan_unrepairable" in text or "repair_failed" in text:
        return "repair_failed"
    if "no_sql" in text or "empty_sql" in text:
        return "no_sql_generated"
    return "no_clear_sql_failure"


def _count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return counts


def _hallucinated_journey_summary(failures: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [row for row in failures if "journey" in json.dumps(row).lower() and row.get("failure_reason") == "hallucinated_table"]
    return {
        "found": bool(rows),
        "count": len(rows),
        "prompt_ids": [row.get("prompt_id") or row.get("query_id") for row in rows],
        "likely_cause": "business term used as table name instead of alias-map table dim_campaign" if rows else "not_observed_in_current_report",
    }


def _render_sql_failure_md(report: dict[str, Any]) -> str:
    summary = report.get("summary", {})
    lines = [
        "# Pure LLM SQL Generation Failure Analysis",
        "",
        "Diagnostic-only analysis for the shadow Pure LLM tool-agent SQL path.",
        "",
        f"- SQL failure count: `{summary.get('sql_failure_count')}`",
        f"- Hallucinated journey table issue: `{summary.get('hallucinated_journey_table_issue', {}).get('found')}`",
        "",
        "## Failure Categories",
        "",
    ]
    for key, value in sorted((summary.get("failure_categories") or {}).items()):
        lines.append(f"- `{key}`: `{value}`")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
