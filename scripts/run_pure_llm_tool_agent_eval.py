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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-only", action="store_true", help="Do not execute new hosted LLM calls; score existing artifacts only.")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--variant", action="append", choices=PURE_LLM_TOOL_AGENT_VARIANTS)
    args = parser.parse_args()
    config = Config.from_env(ROOT)
    load_local_env(config.project_root)
    payload = run_pure_llm_tool_agent_eval(
        config,
        execute_real=not args.artifact_only,
        max_examples=args.limit,
        variants=args.variant,
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
) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    _write_definition_report(config)
    existing_rows = _existing_baseline_rows(config)
    rows: list[dict[str, Any]] = list(existing_rows)
    variants_to_run = variants or [FULL_PURE_LLM_TOOL_AGENT_V1]
    client = get_llm_client()
    backend_probe = _backend_probe(client) if execute_real else {"ok": False, "reason": "artifact_only_requested"}
    execute_new = bool(execute_real and backend_probe.get("ok"))
    skipped_reason = None if execute_new else str(backend_probe.get("reason") or "llm_backend_unavailable")
    if execute_new:
        rows.extend(_run_new_variant_rows(config, variants_to_run, max_examples=max_examples, client=client))
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
    summary = _summary(rows)
    payload = redact_secrets(
        {
            "report_type": REPORT_STEM,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "diagnostic_only": True,
            "official_score_claim": False,
            "promotion_allowed": False,
            "packaged_runtime_changed": False,
            "packaged_default_strategy": "SQL_FIRST_API_VERIFY",
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
            "trajectory": trajectory,
        }
    )


def _failure_stage(result: dict[str, Any], generated_sql: str | None, generated_api: list[dict[str, Any]]) -> str:
    if result.get("skipped"):
        return "llm_unavailable"
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
            }
        )
    scored = [item for item in per_system if item.get("strict_scoring_status") == "available"]
    best = max(scored, key=lambda item: float(item.get("strict_final_score") or 0.0), default={})
    return {
        "systems": per_system,
        "best_variant": best.get("system"),
        "best_strict_score": best.get("strict_final_score"),
        "executed_new_llm_rows": sum(1 for row in rows if row.get("query_id") and row.get("variant") in PURE_LLM_TOOL_AGENT_VARIANTS),
        "recommendation": "pure_llm_baseline_improved_keep_shadow",
    }


def _avg(rows: list[dict[str, Any]], key: str) -> float:
    values = [float(row[key]) for row in rows if isinstance(row.get(key), (int, float))]
    return round(sum(values) / len(values), 4) if values else 0.0


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


if __name__ == "__main__":
    raise SystemExit(main())
