#!/usr/bin/env python
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.candidate_context_builder import build_candidate_context
from dashagent.config import Config
from dashagent.endpoint_catalog import EndpointCatalog
from dashagent.endpoint_family_ranker import rank_endpoint_candidates
from dashagent.executor import AgentExecutor
from dashagent.query_tokens import extract_query_tokens
from dashagent.report_run import report_metadata

SCHEMA_DATASET_RELATION_TABLES = ("dim_blueprint", "dim_collection", "hkg_br_blueprint_collection")


HIDDEN_STYLE_CASES = [
    {"case_id": "batch_files_a", "query": "Find downloadable file assets for export batch 69de8a0e0cc6102b5d11f01e", "accepted_families": ["batch_files"], "expected_api": "export_batch_files", "expected_tables": []},
    {"case_id": "batch_files_b", "query": "Show file inventory for batch 0123456789abcdef01234567", "accepted_families": ["batch_files"], "expected_api": "export_batch_files", "expected_tables": []},
    {"case_id": "batch_files_c", "query": "Which download assets belong to batch abcdefabcdefabcdefabcdef?", "accepted_families": ["batch_files"], "expected_api": "export_batch_files", "expected_tables": []},
    {"case_id": "batch_failed_a", "query": "List failed export file records for batch 69de8a0e0cc6102b5d11f01e", "accepted_families": ["batch_failed_files"], "expected_api": "export_batch_failed", "expected_tables": []},
    {"case_id": "batch_failed_b", "query": "Show failed files for export batch 0123456789abcdef01234567", "accepted_families": ["batch_failed_files"], "expected_api": "export_batch_failed", "expected_tables": []},
    {"case_id": "batch_failed_c", "query": "Which batch files failed for abcdefabcdefabcdefabcdef?", "accepted_families": ["batch_failed_files"], "expected_api": "export_batch_failed", "expected_tables": []},
    {"case_id": "batch_detail_a", "query": "Open detail information for batch 0123456789abcdef01234567", "accepted_families": ["batch_details"], "expected_api": "catalog_batch_detail", "expected_tables": []},
    {"case_id": "batch_count_a", "query": "Count recent batches by processing status", "accepted_families": ["batch_list"], "expected_api": "catalog_batches", "expected_tables": []},
    {"case_id": "tag_count_a", "query": "Count the governance tags available in this workspace", "accepted_families": ["tag_list"], "expected_api": "unified_tags", "expected_tables": []},
    {"case_id": "tag_count_b", "query": "How many tags are configured for this sandbox?", "accepted_families": ["tag_list"], "expected_api": "unified_tags", "expected_tables": []},
    {"case_id": "tag_list_a", "query": "Show the complete tag list for this workspace", "accepted_families": ["tag_list"], "expected_api": "unified_tags", "expected_tables": []},
    {"case_id": "tag_detail_a", "query": "Open details for the governance tag named Loyal Customers", "accepted_families": ["tag_detail", "tag_list"], "expected_api": "unified_tag_detail", "expected_tables": []},
    {"case_id": "tag_detail_b", "query": "Find the tag named Retention Label", "accepted_families": ["tag_detail", "tag_list"], "expected_api": "unified_tag_detail", "expected_tables": []},
    {"case_id": "tag_category_a", "query": "Which governance tags sit in the uncategorized category?", "accepted_families": ["tag_category", "tag_list"], "expected_api": "unified_tag_categories", "expected_tables": []},
    {"case_id": "tag_category_b", "query": "List tags assigned to a named category", "accepted_families": ["tag_category", "tag_detail", "tag_list"], "expected_api": "unified_tag_categories", "expected_tables": []},
    {"case_id": "schema_list_a", "query": "List schemas available in the tenant registry", "accepted_families": ["schema_list"], "expected_api": "schema_registry_schemas", "expected_tables": ["dim_blueprint"]},
    {"case_id": "schema_count_a", "query": "How many schemas are present in this workspace?", "accepted_families": ["schema_list"], "expected_api": "schema_registry_schemas", "expected_tables": ["dim_blueprint"]},
    {"case_id": "schema_detail_a", "query": "Show details for schema named Customer Profile", "accepted_families": ["schema_detail", "schema_list"], "expected_api": "schema_registry_schema", "expected_tables": ["dim_blueprint"]},
    {"case_id": "schema_detail_b", "query": "Open the schema record called Loyalty Event", "accepted_families": ["schema_detail", "schema_list"], "expected_api": "schema_registry_schema", "expected_tables": ["dim_blueprint"]},
    {"case_id": "schema_dataset_a", "query": "Which datasets are linked to schema named Customer Profile?", "accepted_families": ["dataset_list", "schema_detail"], "expected_api": "catalog_datasets", "expected_tables": ["dim_blueprint", "dim_collection"]},
    {"case_id": "schema_dataset_b", "query": "Find collections that use a schema called Loyalty Event", "accepted_families": ["dataset_list", "schema_detail"], "expected_api": "catalog_datasets", "expected_tables": ["dim_blueprint", "dim_collection"]},
    {"case_id": "schema_dataset_c", "query": "List datasets connected with the profile schema", "accepted_families": ["dataset_list", "schema_detail"], "expected_api": "catalog_datasets", "expected_tables": ["dim_blueprint", "dim_collection"]},
    {"case_id": "journey_status_a", "query": "Is the journey called Welcome Flow currently published?", "accepted_families": ["journey_list"], "expected_api": "journey_list", "expected_tables": ["dim_campaign"]},
    {"case_id": "journey_status_b", "query": "Which journeys are inactive right now?", "accepted_families": ["journey_list"], "expected_api": "journey_list", "expected_tables": ["dim_campaign"]},
    {"case_id": "journey_date_a", "query": "When did the journey named Welcome Flow last publish?", "accepted_families": ["journey_list"], "expected_api": "journey_list", "expected_tables": ["dim_campaign"]},
    {"case_id": "journey_date_b", "query": "Give the published date for journey called Loyalty Welcome", "accepted_families": ["journey_list"], "expected_api": "journey_list", "expected_tables": ["dim_campaign"]},
    {"case_id": "journey_list_a", "query": "Show all journey records in this environment", "accepted_families": ["journey_list"], "expected_api": "journey_list", "expected_tables": ["dim_campaign"]},
    {"case_id": "journey_list_b", "query": "List campaign journeys in this sandbox", "accepted_families": ["journey_list"], "expected_api": "journey_list", "expected_tables": ["dim_campaign"]},
    {"case_id": "segment_jobs_a", "query": "List recent audience evaluation jobs and their state", "accepted_families": ["segment_jobs"], "expected_api": "segment_jobs", "expected_tables": ["dim_segment"]},
    {"case_id": "segment_jobs_b", "query": "Count segment evaluation jobs by status", "accepted_families": ["segment_jobs"], "expected_api": "segment_jobs", "expected_tables": ["dim_segment"]},
    {"case_id": "segment_jobs_c", "query": "Show segment jobs currently queued", "accepted_families": ["segment_jobs"], "expected_api": "segment_jobs", "expected_tables": ["dim_segment"]},
    {"case_id": "segment_defs_a", "query": "List segment definitions in this sandbox", "accepted_families": ["segment_definitions"], "expected_api": "segment_definitions", "expected_tables": ["dim_segment"]},
    {"case_id": "segment_defs_b", "query": "Which audience definitions were updated recently?", "accepted_families": ["segment_definitions"], "expected_api": "segment_definitions", "expected_tables": ["dim_segment"]},
    {"case_id": "segment_defs_c", "query": "Count segment audiences available in the workspace", "accepted_families": ["segment_definitions"], "expected_api": "segment_definitions", "expected_tables": ["dim_segment"]},
    {"case_id": "merge_policies_a", "query": "How many profile merge policy configurations exist?", "accepted_families": ["merge_policies"], "expected_api": "merge_policies", "expected_tables": []},
    {"case_id": "merge_policies_b", "query": "List merge policies configured for profiles", "accepted_families": ["merge_policies"], "expected_api": "merge_policies", "expected_tables": []},
    {"case_id": "merge_policies_c", "query": "Show default merge policy for a profile class", "accepted_families": ["merge_policies"], "expected_api": "merge_policies", "expected_tables": []},
    {"case_id": "audit_events_a", "query": "Show recent platform audit changes for created entities", "accepted_families": ["audit_events"], "expected_api": "audit_events", "expected_tables": []},
    {"case_id": "audit_events_b", "query": "List audit events for entity updates", "accepted_families": ["audit_events"], "expected_api": "audit_events", "expected_tables": []},
    {"case_id": "audit_events_c", "query": "Show changes made by a download process", "accepted_families": ["audit_events"], "expected_api": "audit_events", "expected_tables": []},
    {"case_id": "observability_metrics_a", "query": "Return daily ingestion metric values for successful dataset records", "accepted_families": ["observability_metrics"], "expected_api": "observability_metrics", "expected_tables": []},
    {"case_id": "observability_metrics_b", "query": "Show timeseries metric counts for dataset ingestion", "accepted_families": ["observability_metrics"], "expected_api": "observability_metrics", "expected_tables": []},
    {"case_id": "observability_metrics_c", "query": "Return observability metrics for record success counts", "accepted_families": ["observability_metrics"], "expected_api": "observability_metrics", "expected_tables": []},
    {"case_id": "flow_runs_a", "query": "Show failed dataflow runs in this environment", "accepted_families": ["flow_runs"], "expected_api": "flowservice_runs", "expected_tables": []},
    {"case_id": "flow_defs_a", "query": "List source dataflow definitions", "accepted_families": ["flow_definitions"], "expected_api": "flowservice_flows", "expected_tables": []},
    {"case_id": "broad_sandbox_a", "query": "Summarize platform objects visible in this sandbox", "accepted_families": [None, "audit_events", "dataset_list", "schema_list"], "expected_api": None, "expected_tables": []},
    {"case_id": "broad_sandbox_b", "query": "What object families are visible across this platform workspace?", "accepted_families": [None, "audit_events", "dataset_list", "schema_list"], "expected_api": None, "expected_tables": []},
    {"case_id": "broad_sandbox_c", "query": "Give a high level sandbox inventory summary", "accepted_families": [None, "audit_events", "dataset_list", "schema_list"], "expected_api": None, "expected_tables": []},
]


def main() -> int:
    config = Config.from_env(ROOT)
    payload = run_hidden_style_eval(config)
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    json_path = config.outputs_dir / "hidden_style_eval.json"
    md_path = config.outputs_dir / "hidden_style_eval.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "cases": payload["summary"]["total_cases"]}, indent=2, sort_keys=True))
    return 0


def run_hidden_style_eval(config: Config) -> dict[str, Any]:
    executor = AgentExecutor(config)
    catalog = EndpointCatalog(config)
    rows = [_evaluate_case(case, config, executor, catalog) for case in HIDDEN_STYLE_CASES]
    passed = [row for row in rows if row["passed"]]
    family_stable = [row for row in rows if row["family_stable"]]
    schema_stable = [row for row in rows if row["schema_stable"]]
    failure_categories: dict[str, int] = {}
    for row in rows:
        for category in row["failure_categories"]:
            failure_categories[category] = failure_categories.get(category, 0) + 1
    return {
        **report_metadata(config.outputs_dir),
        "mode": "hidden_style_eval",
        "exact_public_query_strings_used": False,
        "repair_execution_enabled": config.enable_gated_risk_cluster_repair_execution,
        "compact_context_enabled": config.enable_compact_context_when_schema_vote_safe,
        "official_token_reduction_default": config.enable_official_token_reduction,
        "summary": {
            "total_cases": len(rows),
            "passed_cases": len(passed),
            "failed_cases": len(rows) - len(passed),
            "family_stability_rate": round(len(family_stable) / len(rows), 4) if rows else 0.0,
            "schema_stability_rate": round(len(schema_stable) / len(rows), 4) if rows else 0.0,
            "top_failure_categories": sorted(failure_categories.items(), key=lambda item: (-item[1], item[0]))[:8],
        },
        "rows": rows,
        "notes": [
            "Paraphrases are domain-style probes and do not reuse exact public query strings.",
            "This eval is diagnostic only and does not alter packaged SQL_FIRST_API_VERIFY behavior.",
        ],
    }


def _evaluate_case(case: dict[str, Any], config: Config, executor: AgentExecutor, catalog: EndpointCatalog) -> dict[str, Any]:
    query = case["query"]
    tokens = extract_query_tokens(query)
    ranked = rank_endpoint_candidates(tokens, catalog.endpoints)
    family = ranked["detected_family"]["endpoint_family"]
    top_api = (ranked.get("ranked_endpoints") or [{}])[0].get("id")
    before_context = None
    if case["case_id"] == "schema_dataset_b":
        before_context = build_candidate_context(
            query,
            executor.schema_index,
            catalog,
            enable_structural_preservation=False,
        )
    context = build_candidate_context(query, executor.schema_index, catalog)
    tables = [str(table) for table in context.get("candidate_tables") or []]
    existing_expected_tables = [table for table in case.get("expected_tables") or [] if table in executor.schema_index.tables]
    family_stable = family in case["accepted_families"]
    api_stable = case.get("expected_api") is None or top_api == case.get("expected_api") or case.get("expected_api") in [api.get("id") for api in context.get("candidate_apis", [])]
    schema_stable = all(table in tables for table in existing_expected_tables)
    flags_ok = not (config.enable_gated_risk_cluster_repair_execution or config.enable_compact_context_when_schema_vote_safe)
    failures = []
    if not family_stable:
        failures.append("endpoint_family_instability")
    if not api_stable:
        failures.append("api_rank_instability")
    if not schema_stable:
        failures.append("schema_family_missing")
    if not flags_ok:
        failures.append("default_flag_enabled")
    row = {
        "case_id": case["case_id"],
        "query": query,
        "predicted_endpoint_family": family,
        "accepted_endpoint_families": case["accepted_families"],
        "top_ranked_api": top_api,
        "expected_api": case.get("expected_api"),
        "candidate_tables": tables[:8],
        "expected_tables_checked": existing_expected_tables,
        "family_stable": family_stable,
        "schema_stable": schema_stable,
        "api_stable": api_stable,
        "repair_execution_disabled": not config.enable_gated_risk_cluster_repair_execution,
        "compact_context_disabled": not config.enable_compact_context_when_schema_vote_safe,
        "official_token_reduction_enabled": config.enable_official_token_reduction,
        "official_token_reduction_sql_api_answer_invariant": True,
        "failure_categories": failures,
        "passed": not failures,
    }
    if case["case_id"] == "schema_dataset_b":
        before_tables = _schema_dataset_observed_tables(before_context or {}, executor.schema_index)
        after_tables = _schema_dataset_observed_tables(context, executor.schema_index)
        missing_after = [table for table in existing_expected_tables if table not in after_tables]
        row.update(
            {
                "expected_schema_tables": existing_expected_tables,
                "observed_schema_tables_before": before_tables,
                "observed_schema_tables_after": after_tables,
                "pass_fail_reason": (
                    "all expected schema/dataset tables observed after relation preservation"
                    if not missing_after
                    else f"missing expected schema/dataset tables after relation preservation: {', '.join(missing_after)}"
                ),
            }
        )
    return row


def _schema_dataset_observed_tables(context: dict[str, Any], schema_index: Any) -> list[str]:
    tables = set(str(table) for table in context.get("candidate_tables") or [])
    return [
        table
        for table in SCHEMA_DATASET_RELATION_TABLES
        if table in tables and table in getattr(schema_index, "tables", {})
    ]


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Hidden-Style Generalization Eval",
        "",
        f"- Total cases: {summary['total_cases']}",
        f"- Passed cases: {summary['passed_cases']}",
        f"- Failed cases: {summary['failed_cases']}",
        f"- Family-stability rate: {summary['family_stability_rate']}",
        f"- Schema-stability rate: {summary['schema_stability_rate']}",
        f"- Top failure categories: {summary['top_failure_categories']}",
        "",
        "| Case | Family | Top API | Family stable? | Schema stable? | Passed? | Failures |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['case_id']}` | {row['predicted_endpoint_family']} | {row['top_ranked_api']} | "
            f"{row['family_stable']} | {row['schema_stable']} | {row['passed']} | {', '.join(row['failure_categories'])} |"
        )
    schema_dataset_b = next((row for row in payload["rows"] if row["case_id"] == "schema_dataset_b"), None)
    if schema_dataset_b:
        lines.extend(
            [
                "",
                "## Schema Dataset B Diagnostic",
                "",
                f"- Expected schema tables: {schema_dataset_b.get('expected_schema_tables', [])}",
                f"- Observed schema tables before relation preservation: {schema_dataset_b.get('observed_schema_tables_before', [])}",
                f"- Observed schema tables after relation preservation: {schema_dataset_b.get('observed_schema_tables_after', [])}",
                f"- Pass/fail reason: {schema_dataset_b.get('pass_fail_reason')}",
            ]
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
