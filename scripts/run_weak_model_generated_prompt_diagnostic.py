#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
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
from dashagent.llm_client import get_llm_client
from dashagent.schema_index import SchemaIndex
from dashagent.trajectory import redact_secrets
from dashagent.validators import SQLValidator
from scripts.load_local_env import load_local_env
from scripts.run_weak_model_lift_eval import _run_scaffold_variant

REPORT_STEM = "weak_model_generated_prompt_diagnostic"
DEFAULT_VARIANT = "weak_scaffold_api_recovery_v1"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run weak-scaffold diagnostic on generated prompts.")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--variant", default=DEFAULT_VARIANT)
    args = parser.parse_args()
    config = Config.from_env(ROOT)
    load_local_env(config.project_root)
    payload = run_weak_model_generated_prompt_diagnostic(config, limit=args.limit, variant=args.variant)
    print(json.dumps({"json": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.json"), "summary": payload["summary"]}, indent=2, sort_keys=True))
    return 0


def run_weak_model_generated_prompt_diagnostic(config: Config | None = None, *, limit: int | None = 50, variant: str = DEFAULT_VARIANT) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    prompts = _load_generated_prompts(config, limit=limit)
    reports = config.outputs_dir / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    db = DuckDBDatabase(config)
    try:
        schema = SchemaIndex.build(db)
        catalog = EndpointCatalog(config)
        api_client = AdobeAPIClient(config)
        llm_client = get_llm_client()
        sql_validator = SQLValidator(schema)
        for item in prompts:
            rows.append(_run_prompt(item, variant, db, schema, catalog, api_client, llm_client, sql_validator))
    finally:
        db.close()
    summary = _summarize(rows, requested_limit=limit, available_prompt_count=len(_load_generated_prompts(config, limit=None)))
    payload = redact_secrets(
        {
            "report_type": REPORT_STEM,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "diagnostic_only": True,
            "official_score_claim": False,
            "promotion_allowed": False,
            "packaged_runtime_changed": False,
            "packaged_default_strategy": "SQL_FIRST_API_VERIFY",
            "variant": variant,
            "summary": summary,
            "rows": rows,
        }
    )
    (reports / f"{REPORT_STEM}.json").write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    (reports / f"{REPORT_STEM}.md").write_text(_render_md(payload), encoding="utf-8")
    return payload


def _load_generated_prompts(config: Config, *, limit: int | None) -> list[dict[str, Any]]:
    path = config.project_root / "data" / "generated_prompt_suite.json"
    prompts = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    prompts = [item for item in prompts if isinstance(item, dict)]
    return prompts[:limit] if limit else prompts


def _run_prompt(
    item: dict[str, Any],
    variant: str,
    db: DuckDBDatabase,
    schema: SchemaIndex,
    catalog: EndpointCatalog,
    api_client: AdobeAPIClient,
    llm_client: Any,
    sql_validator: SQLValidator,
) -> dict[str, Any]:
    prompt = str(item.get("prompt") or "")
    try:
        result = _run_scaffold_variant(prompt, variant, db, schema, catalog, api_client, llm_client)
        trajectory = result.get("trajectory", {})
        row = _row_from_trajectory(item, variant, trajectory, result)
        row["runtime_pass"] = True
    except Exception as exc:  # diagnostic runner must isolate one prompt failure
        row = {
            "prompt_id": item.get("prompt_id"),
            "prompt": prompt,
            "variant": variant,
            "runtime_pass": False,
            "runtime_error_type": type(exc).__name__,
            "failure_category": "no_clear_failure",
            "unsupported_claims": 0,
        }
    return redact_secrets(row)


def _row_from_trajectory(item: dict[str, Any], variant: str, trajectory: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    steps = trajectory.get("steps", []) if isinstance(trajectory.get("steps"), list) else []
    slot_step = next((step for step in steps if step.get("kind") == "semantic_slots"), {})
    compiler_step = next((step for step in steps if step.get("kind") == "slot_compiler"), {})
    sql_step = next((step for step in steps if step.get("kind") == "sql_call"), {})
    api_steps = [step for step in steps if step.get("kind") == "api_call"]
    final_step = next((step for step in steps if step.get("kind") == "final_answer"), {})
    slots = slot_step.get("slots") if isinstance(slot_step.get("slots"), dict) else {}
    compiled = compiler_step.get("compiled") if isinstance(compiler_step.get("compiled"), dict) else {}
    sql_candidate = (compiled.get("sql_candidates") or [{}])[0] if isinstance(compiled.get("sql_candidates"), list) else {}
    api_candidate = (compiled.get("api_candidates") or [{}])[0] if isinstance(compiled.get("api_candidates"), list) else {}
    grounding = final_step.get("grounding") if isinstance(final_step.get("grounding"), dict) else {}
    api_result = (api_steps[0].get("result") if api_steps else {}) or {}
    api_evidence = api_result.get("api_evidence") if isinstance(api_result.get("api_evidence"), dict) else {}
    selected_table = _selected_table(sql_candidate)
    selected_columns = _selected_columns(sql_candidate)
    validation_failures = _validation_failure_count(sql_step, sql_candidate, api_steps, api_candidate)
    row = {
        "prompt_id": item.get("prompt_id"),
        "prompt": item.get("prompt"),
        "source_group_id": _source_group_id(item),
        "source_prompt": item.get("source_prompt"),
        "generation_type": item.get("generation_type"),
        "domain_family": item.get("domain_family"),
        "expected_answer_intent_diagnostic": item.get("expected_answer_intent_diagnostic"),
        "semantic_slots": slots,
        "answer_intent": slots.get("intent"),
        "evidence_need": slots.get("evidence_need"),
        "sql_candidate": sql_step.get("sql") or sql_candidate.get("sql"),
        "selected_sql_table": selected_table,
        "selected_sql_columns": selected_columns,
        "sql_validation_ok": _validation_ok(sql_step.get("validation") or sql_candidate.get("validation")),
        "sql_execution_ok": isinstance(sql_step.get("result"), dict) and not bool((sql_step.get("result") or {}).get("error")),
        "sql_row_count": (sql_step.get("result") or {}).get("row_count") if isinstance(sql_step.get("result"), dict) else None,
        "api_candidate": api_candidate,
        "endpoint_selected": api_result.get("endpoint_id") or api_candidate.get("endpoint_id"),
        "api_validation_ok": _validation_ok((api_steps[0].get("validation") if api_steps else None) or api_candidate.get("validation")),
        "api_outcome": api_evidence.get("outcome") or api_result.get("status_code"),
        "answer_used_sql_evidence": bool(grounding.get("answer_used_sql")),
        "answer_used_api_evidence": bool(grounding.get("answer_used_api")),
        "unsupported_claims": int(result.get("unsupported_claim_count") or grounding.get("unsupported_claim_count") or 0),
        "validation_failure_count": validation_failures,
        "tool_call_count": trajectory.get("tool_call_count", 0),
        "estimated_tokens": trajectory.get("estimated_tokens", 0),
        "runtime": round(float(trajectory.get("runtime") or 0.0), 4),
        "final_answer": trajectory.get("final_answer"),
    }
    row["failure_category"] = classify_generated_failure(row, item)
    return row


def classify_generated_failure(row: dict[str, Any], prompt_item: dict[str, Any] | None = None) -> str:
    item = prompt_item or {}
    if int(row.get("unsupported_claims") or 0) > 0:
        return "unsupported_claim"
    if int(row.get("validation_failure_count") or 0) > 0:
        return "sql_compiler_gap" if row.get("sql_candidate") else "api_endpoint_selection_gap"
    if _expected_sql(item, row) and not row.get("sql_candidate"):
        return "sql_compiler_gap"
    if row.get("sql_candidate") and row.get("sql_validation_ok") is False:
        return "sql_compiler_gap"
    if _wrong_table(row, item):
        return "wrong_table"
    if _wrong_aggregation(row, item):
        return "wrong_aggregation"
    if _missing_filter(row):
        return "missing_filter"
    if _wrong_columns(row, item):
        return "wrong_columns"
    if _expected_api(item, row) and not row.get("endpoint_selected"):
        return "api_endpoint_selection_gap"
    if row.get("endpoint_selected") and not row.get("api_validation_ok"):
        return "api_endpoint_selection_gap"
    if row.get("endpoint_selected") and not row.get("answer_used_api_evidence") and _api_required(row):
        return "api_evidence_not_used"
    if row.get("sql_candidate") and not row.get("answer_used_sql_evidence") and str(row.get("evidence_need")) in {"sql_only", "sql_first"}:
        return "answer_grounding_gap"
    return "no_clear_failure"


def _summarize(rows: list[dict[str, Any]], *, requested_limit: int | None, available_prompt_count: int) -> dict[str, Any]:
    total = len(rows)
    runtime_pass = sum(1 for row in rows if row.get("runtime_pass"))
    validation_failures = sum(int(row.get("validation_failure_count") or 0) for row in rows)
    unsupported = sum(int(row.get("unsupported_claims") or 0) for row in rows)
    sql_selected = sum(1 for row in rows if row.get("sql_candidate"))
    sql_validation_pass = sum(1 for row in rows if row.get("sql_candidate") and row.get("sql_validation_ok"))
    api_selected = sum(1 for row in rows if row.get("endpoint_selected"))
    api_validation_pass = sum(1 for row in rows if row.get("endpoint_selected") and row.get("api_validation_ok"))
    failure_counts = Counter(str(row.get("failure_category") or "no_clear_failure") for row in rows)
    api_outcomes = Counter(str(row.get("api_outcome") or "none") for row in rows)
    stable = total > 0 and runtime_pass == total and validation_failures == 0 and unsupported == 0
    return {
        "requested_limit": requested_limit,
        "available_prompt_count": available_prompt_count,
        "executed_prompts": total,
        "runtime_pass_count": runtime_pass,
        "runtime_pass_rate": round(runtime_pass / total, 4) if total else 0.0,
        "validation_failures": validation_failures,
        "unsupported_claim_count": unsupported,
        "sql_selected_count": sql_selected,
        "sql_validation_pass_count": sql_validation_pass,
        "sql_validation_pass_rate": round(sql_validation_pass / sql_selected, 4) if sql_selected else None,
        "api_selected_count": api_selected,
        "api_validation_pass_count": api_validation_pass,
        "api_validation_pass_rate": round(api_validation_pass / api_selected, 4) if api_selected else None,
        "answer_used_sql_count": sum(1 for row in rows if row.get("answer_used_sql_evidence")),
        "answer_used_api_count": sum(1 for row in rows if row.get("answer_used_api_evidence")),
        "api_outcome_distribution": dict(api_outcomes),
        "failure_category_counts": dict(failure_counts),
        "top_failure_categories": failure_counts.most_common(8),
        "stable_subset": stable,
        "generalizes_beyond_public_dev": stable and failure_counts.get("unsupported_claim", 0) == 0,
    }


def _render_md(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    failures = "\n".join(f"- `{name}`: `{count}`" for name, count in summary.get("top_failure_categories", []))
    return (
        "# Weak Model Generated Prompt Diagnostic\n\n"
        "Diagnostic-only weak-scaffold run. Generated prompts are not official score evidence.\n\n"
        f"- Variant: `{payload.get('variant')}`\n"
        f"- Executed prompts: `{summary.get('executed_prompts')}`\n"
        f"- Runtime pass: `{summary.get('runtime_pass_count')}` / `{summary.get('executed_prompts')}`\n"
        f"- Validation failures: `{summary.get('validation_failures')}`\n"
        f"- Unsupported claims: `{summary.get('unsupported_claim_count')}`\n"
        f"- SQL selected: `{summary.get('sql_selected_count')}`\n"
        f"- API selected: `{summary.get('api_selected_count')}`\n"
        f"- Stable subset: `{summary.get('stable_subset')}`\n\n"
        "## Top Failure Categories\n\n"
        f"{failures}\n"
    )


def _source_group_id(item: dict[str, Any]) -> str:
    ids = item.get("source_query_ids")
    if isinstance(ids, list) and ids:
        return str(ids[0])
    return str(item.get("source_prompt") or item.get("domain_family") or item.get("prompt_id") or "unknown")


def _selected_table(sql_candidate: dict[str, Any]) -> str | None:
    plan = sql_candidate.get("structured_sql_plan") if isinstance(sql_candidate.get("structured_sql_plan"), dict) else {}
    table = plan.get("primary_table")
    if table:
        return str(table)
    compiled = sql_candidate.get("compiled") if isinstance(sql_candidate.get("compiled"), dict) else {}
    tables = compiled.get("selected_tables") if isinstance(compiled.get("selected_tables"), list) else []
    return str(tables[0]) if tables else None


def _selected_columns(sql_candidate: dict[str, Any]) -> list[str]:
    plan = sql_candidate.get("structured_sql_plan") if isinstance(sql_candidate.get("structured_sql_plan"), dict) else {}
    columns = plan.get("columns_needed") if isinstance(plan.get("columns_needed"), list) else []
    return [str(column) for column in columns]


def _validation_ok(validation: Any) -> bool | None:
    if not isinstance(validation, dict):
        return None
    if "ok" in validation:
        return bool(validation.get("ok"))
    if "valid" in validation:
        return bool(validation.get("valid"))
    return None


def _validation_failure_count(sql_step: dict[str, Any], sql_candidate: dict[str, Any], api_steps: list[dict[str, Any]], api_candidate: dict[str, Any]) -> int:
    validations = [sql_step.get("validation") or sql_candidate.get("validation")]
    validations.extend((step.get("validation") for step in api_steps))
    if not api_steps:
        validations.append(api_candidate.get("validation"))
    return sum(1 for validation in validations if _validation_ok(validation) is False)


def _expected_sql(item: dict[str, Any], row: dict[str, Any]) -> bool:
    route = str(item.get("expected_route_diagnostic") or "").upper()
    need = str(row.get("evidence_need") or "").lower()
    return "SQL" in route or need in {"sql_only", "sql_first", "sql_then_api", "sql_primary_api_verify"}


def _expected_api(item: dict[str, Any], row: dict[str, Any]) -> bool:
    route = str(item.get("expected_route_diagnostic") or "").upper()
    need = str(row.get("evidence_need") or "").lower()
    return "API" in route or need in {"api_only", "api_first", "api_then_sql", "sql_then_api", "sql_primary_api_verify", "api_primary_sql_context"}


def _wrong_table(row: dict[str, Any], item: dict[str, Any]) -> bool:
    hints = item.get("target_tables_hint")
    if not isinstance(hints, list) or not hints or not row.get("selected_sql_table"):
        return False
    return str(row["selected_sql_table"]) not in {str(hint) for hint in hints}


def _wrong_aggregation(row: dict[str, Any], item: dict[str, Any]) -> bool:
    expected = str(item.get("expected_answer_intent_diagnostic") or row.get("answer_intent") or "").upper()
    if expected != "COUNT" or not row.get("sql_candidate"):
        return False
    sql = str(row.get("sql_candidate") or "").lower()
    return "count(" not in sql


def _missing_filter(row: dict[str, Any]) -> bool:
    prompt = str(row.get("prompt") or "")
    if "'" not in prompt and '"' not in prompt:
        return False
    sql = str(row.get("sql_candidate") or "").lower()
    return bool(sql) and " where " not in sql


def _wrong_columns(row: dict[str, Any], item: dict[str, Any]) -> bool:
    expected = str(item.get("expected_answer_intent_diagnostic") or row.get("answer_intent") or "").upper()
    columns = " ".join(str(col).lower() for col in row.get("selected_sql_columns") or [])
    if expected in {"DATE", "WHEN"}:
        return not any(marker in columns for marker in ("time", "date", "created", "updated", "published", "deployed", "modified"))
    if expected == "STATUS":
        return not any(marker in columns for marker in ("status", "state"))
    if expected == "LIST":
        return not any(marker in columns for marker in ("id", "name", "title", "display"))
    return False


def _api_required(row: dict[str, Any]) -> bool:
    return str(row.get("evidence_need") or "").lower() in {"api_only", "api_first", "api_then_sql", "sql_then_api", "sql_primary_api_verify", "api_primary_sql_context"}


if __name__ == "__main__":
    raise SystemExit(main())
