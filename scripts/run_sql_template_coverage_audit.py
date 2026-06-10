#!/usr/bin/env python
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.db import DuckDBDatabase
from dashagent.endpoint_catalog import EndpointCatalog
from dashagent.eval_harness import EvalHarness
from dashagent.metadata_selector import MetadataSelector
from dashagent.planner import StrategyPlanner
from dashagent.query_analysis import analyze_query
from dashagent.query_normalizer import normalize_query
from dashagent.query_tokens import extract_query_tokens
from dashagent.router import QueryRouter
from dashagent.schema_aware_sql_generator import generate_schema_aware_sql_candidates
from dashagent.schema_index import SchemaIndex
from dashagent.sql_ast_candidate_ranker import rank_sql_candidate_ast
from dashagent.sql_ast_tools import sql_ast_summary
from dashagent.trajectory import redact_secrets
from dashagent.validators import SQLValidator


REPORT_STEM = "sql_template_coverage_audit"
LIKELY_FAILURES = {
    "template_gap",
    "table_selection_gap",
    "join_reasoning_gap",
    "count_distinct_gap",
    "where_condition_gap",
    "column_selection_gap",
    "no_sql_gap",
    "none",
}


def main() -> int:
    config = Config.from_env(ROOT)
    payload = run_sql_template_coverage_audit(config)
    print(
        json.dumps(
            {
                "json": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.json"),
                "markdown": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.md"),
                "row_count": payload.get("row_count"),
                "template_hit_count": payload.get("template_hit_count"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def run_sql_template_coverage_audit(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    db = DuckDBDatabase(config)
    schema = SchemaIndex.build(db)
    endpoint_catalog = EndpointCatalog(config)
    router = QueryRouter(db.list_tables(), endpoint_catalog)
    metadata_selector = MetadataSelector(schema, endpoint_catalog, config)
    planner = StrategyPlanner(schema, replace(config, enable_schema_aware_sql_fallback=False))
    validator = SQLValidator(schema, enable_ast_validation=config.enable_sql_ast_validation)

    prompts = _load_public_prompts(config) + _load_generated_prompts(config)
    rows = [
        _audit_prompt(
            prompt=item["prompt"],
            prompt_id=item["prompt_id"],
            source=item["source"],
            config=config,
            db=db,
            schema=schema,
            router=router,
            metadata_selector=metadata_selector,
            planner=planner,
            validator=validator,
            endpoint_catalog=endpoint_catalog,
        )
        for item in prompts
    ]
    payload = redact_secrets(_build_report(config, rows))
    (reports_dir / f"{REPORT_STEM}.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    (reports_dir / f"{REPORT_STEM}.md").write_text(_render_markdown(payload), encoding="utf-8")
    return payload


def _audit_prompt(
    *,
    prompt: str,
    prompt_id: str,
    source: str,
    config: Config,
    db: DuckDBDatabase,
    schema: SchemaIndex,
    router: QueryRouter,
    metadata_selector: MetadataSelector,
    planner: StrategyPlanner,
    validator: SQLValidator,
    endpoint_catalog: EndpointCatalog,
) -> dict[str, Any]:
    normalization = normalize_query(prompt)
    tokens = extract_query_tokens(prompt, normalization)
    routing = router.route(prompt)
    analysis = analyze_query(
        prompt,
        routing,
        schema,
        strategy="SQL_FIRST_API_VERIFY",
        config=config,
        endpoint_catalog=endpoint_catalog,
        normalized=normalization,
        tokens=tokens,
    )
    metadata = metadata_selector.select(
        prompt,
        routing,
        strategy="SQL_FIRST_API_VERIFY",
        query_id=prompt_id,
        analysis=analysis,
    )
    plan = planner.create_plan(prompt, routing, metadata, "SQL_FIRST_API_VERIFY", analysis=analysis)
    sql_step = next((step for step in plan.steps if step.action == "sql" and step.sql), None)
    sql = sql_step.sql if sql_step else None
    validation = validator.validate(sql) if sql else None
    execution = db.execute_sql(sql, allow_full_result=bool(sql_step and sql_step.allow_full_result)) if sql and validation and validation.ok else None
    ast = sql_ast_summary(sql, schema) if sql else {}
    ast_rank = rank_sql_candidate_ast(sql, schema, query=prompt, expected_answer_shape=analysis.answer_family) if sql else {}
    schema_candidates = generate_schema_aware_sql_candidates(
        prompt,
        schema,
        analysis=analysis,
        selected_tables=metadata.get("selected_tables", []),
        max_candidates=3,
        db=db,
        execute_probe=True,
    )
    likely_failure = _likely_failure(prompt, analysis, sql, validation, execution, ast_rank)
    return redact_secrets(
        {
            "prompt_id": prompt_id,
            "source": source,
            "prompt": prompt,
            "route_type": routing.route_type,
            "domain_type": routing.domain_type,
            "answer_family": analysis.answer_family,
            "sql_template_family": analysis.sql_template.family if analysis.sql_template else None,
            "template_hit": analysis.sql_template is not None,
            "fallback_sql_used": bool(sql and analysis.sql_template is None),
            "schema_aware_candidate_available": schema_candidates.selected_candidate is not None,
            "schema_aware_candidate_id": schema_candidates.selected_candidate.candidate_id if schema_candidates.selected_candidate else None,
            "selected_table": (ast.get("selected_tables") or [None])[0],
            "selected_tables": ast.get("selected_tables", []),
            "selected_columns": ast.get("selected_columns", []),
            "joins_used": int(ast_rank.get("join_count") or max(0, len(ast.get("selected_tables", [])) - 1)),
            "sql_validation_result": validation.to_dict() if validation else {"ok": False, "errors": ["no SQL step"]},
            "sql_execution_result": _compact_execution(execution),
            "generated_sql": sql,
            "likely_failure": likely_failure,
        }
    )


def _build_report(config: Config, rows: list[dict[str, Any]]) -> dict[str, Any]:
    failures = Counter(row.get("likely_failure", "none") for row in rows)
    template_misses = [row for row in rows if not row.get("template_hit")]
    return {
        "report_type": REPORT_STEM,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "diagnostic_only": True,
        "official_score_claim": False,
        "promotion_allowed": False,
        "strategy": "SQL_FIRST_API_VERIFY",
        "schema_aware_fallback_packaged_default": False,
        "row_count": len(rows),
        "template_hit_count": sum(1 for row in rows if row.get("template_hit")),
        "template_miss_count": len(template_misses),
        "fallback_sql_used_count": sum(1 for row in rows if row.get("fallback_sql_used")),
        "schema_aware_candidate_available_on_template_miss": sum(
            1 for row in template_misses if row.get("schema_aware_candidate_available")
        ),
        "likely_failure_distribution": dict(failures),
        "required_likely_failure_enum": sorted(LIKELY_FAILURES),
        "rows": rows,
        "output_paths": {
            "json": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.json"),
            "markdown": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.md"),
        },
    }


def _likely_failure(
    prompt: str,
    analysis: Any,
    sql: str | None,
    validation: Any,
    execution: dict[str, Any] | None,
    ast_rank: dict[str, Any],
) -> str:
    if not sql:
        return "no_sql_gap"
    if validation is not None and not validation.ok:
        text = " ".join(validation.errors).lower()
        if "unknown table" in text:
            return "table_selection_gap"
        if "unknown column" in text:
            return "column_selection_gap"
        return "template_gap"
    lowered = prompt.lower()
    if _asks_unique_count(lowered) and "count(distinct" not in sql.lower():
        return "count_distinct_gap"
    if any(marker in lowered for marker in ["connected", "mapped", "related", "associated", "linked"]) and int(ast_rank.get("join_count") or 0) == 0:
        return "join_reasoning_gap"
    if re.search(r"'[^']+'|\"[^\"]+\"", prompt) and " where " not in sql.lower():
        return "where_condition_gap"
    if execution is not None and not execution.get("ok"):
        return "template_gap" if analysis.sql_template else "table_selection_gap"
    return "none"


def _asks_unique_count(lowered: str) -> bool:
    return any(marker in lowered for marker in ["unique", "distinct", "different"]) and any(
        marker in lowered for marker in ["how many", "count", "number of", "total"]
    )


def _compact_execution(execution: dict[str, Any] | None) -> dict[str, Any]:
    if execution is None:
        return {"ok": False, "row_count": 0, "error": "not executed"}
    return {
        "ok": bool(execution.get("ok")),
        "row_count": execution.get("row_count", 0),
        "limited": bool(execution.get("limited")),
        "error": execution.get("error"),
    }


def _load_public_prompts(config: Config) -> list[dict[str, str]]:
    harness = EvalHarness(config)
    return [
        {"source": "public_dev", "prompt_id": example.query_id, "prompt": example.query}
        for example in harness.load_examples()
    ]


def _load_generated_prompts(config: Config) -> list[dict[str, str]]:
    path = config.data_dir / "generated_prompt_suite.json"
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        return []
    rows = []
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            continue
        prompt = str(item.get("prompt") or "")
        if not prompt:
            continue
        rows.append(
            {
                "source": "generated_prompt_diagnostic",
                "prompt_id": str(item.get("prompt_id") or f"generated_{index + 1:03d}"),
                "prompt": prompt,
            }
        )
    return rows


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# SQL Template Coverage Audit",
        "",
        "Diagnostic-only audit of fixed SQL template coverage and schema-aware fallback opportunities.",
        "",
        f"- Rows: {report.get('row_count')}",
        f"- Template hits: {report.get('template_hit_count')}",
        f"- Template misses: {report.get('template_miss_count')}",
        f"- Existing fallback SQL used: {report.get('fallback_sql_used_count')}",
        f"- Schema-aware candidate available on template misses: {report.get('schema_aware_candidate_available_on_template_miss')}",
        "",
        "## Likely Failures",
        "",
    ]
    for name, count in sorted((report.get("likely_failure_distribution") or {}).items()):
        lines.append(f"- {name}: {count}")
    lines.extend(["", "## Template Miss Examples", ""])
    misses = [row for row in report.get("rows", []) if not row.get("template_hit")][:20]
    for row in misses:
        lines.append(
            f"- `{row.get('prompt_id')}` [{row.get('source')}]: {row.get('likely_failure')} "
            f"(candidate={row.get('schema_aware_candidate_id') or 'none'})"
        )
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
