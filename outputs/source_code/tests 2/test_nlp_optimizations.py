from __future__ import annotations

import json
from dataclasses import replace

from dashagent.config import Config
from dashagent.db import DuckDBDatabase
from dashagent.endpoint_catalog import EndpointCatalog
from dashagent.executor import AgentExecutor
from dashagent.metadata_selector import MetadataSelector
from dashagent.plan_ensemble import select_plan_candidate
from dashagent.planner import Plan, PlanStep
from dashagent.query_analysis import analyze_query
from dashagent.query_normalizer import normalize_query
from dashagent.query_tokens import extract_query_tokens
from dashagent.relevance_scorer import score_relevance
from dashagent.router import QueryRouter
from dashagent.schema_index import SchemaIndex
from dashagent.validators import APIValidator, SQLValidator


def test_query_normalizer_preserves_original_and_rewrites_matching_text():
    query = "Show  data\u2011flows for \u201cBirthday Message\u201d and merge-policy record success"
    normalized = normalize_query(query)
    assert normalized["original"] == query
    assert '"Birthday Message"' in normalized["normalized"]
    assert "dataflow" in normalized["matching_text"]
    assert "merge policy" in normalized["matching_text"]
    assert "recordsuccess" in normalized["matching_text"]
    assert normalized["rewrites"]


def test_query_tokens_extract_entities_ids_dates_metrics_and_statuses():
    query = (
        "Show all segment jobs with status 'QUEUED' for schema https://ns.adobe.com/acme/schema "
        "between '2026-03-15' and '2026-03-31' using "
        "timeseries.ingestion.dataset.recordsuccess.count and _xdm.context.profile. "
        "Batch 01KP69BPA5ZKFB7HCDYPE4GN6F uses 51175a7f-aa60-4533-bef1-717b3cef7818."
    )
    tokens = extract_query_tokens(query)
    assert "QUEUED" in tokens.quoted_entities
    assert "51175a7f-aa60-4533-bef1-717b3cef7818" in tokens.uuids
    assert "01KP69BPA5ZKFB7HCDYPE4GN6F" in tokens.batch_ids
    assert "https://ns.adobe.com/acme/schema" in tokens.schema_ids
    assert ("2026-03-15", "2026-03-31") in tokens.date_ranges
    assert "timeseries.ingestion.dataset.recordsuccess.count" in tokens.metric_names
    assert "_xdm.context.profile" in tokens.field_paths
    assert "queued" in tokens.statuses


def test_relevance_scorer_ranks_expected_journey_table(tiny_project: Config):
    db = DuckDBDatabase(tiny_project)
    schema = SchemaIndex.build(db)
    relevance = score_relevance("List all journeys", schema, EndpointCatalog(tiny_project))
    assert relevance.tables[0].name == "dim_campaign"
    assert "journey_list" in [item.name for item in relevance.apis[:3]]


def test_metadata_selector_includes_compact_nlp_diagnostics(tiny_project: Config):
    db = DuckDBDatabase(tiny_project)
    schema = SchemaIndex.build(db)
    catalog = EndpointCatalog(tiny_project)
    router = QueryRouter(db.list_tables(), catalog)
    query = "When was the journey 'Birthday Message' published?"
    normalized = normalize_query(query)
    routing = router.route(normalized["matching_text"])
    analysis = analyze_query(query, routing, schema, strategy="SQL_FIRST_API_VERIFY", config=tiny_project, endpoint_catalog=catalog, normalized=normalized)
    metadata = MetadataSelector(schema, catalog, tiny_project).select(
        query,
        routing,
        strategy="SQL_FIRST_API_VERIFY",
        query_id="tiny",
        analysis=analysis,
    )
    assert metadata["query"] == query
    assert "nlp_diagnostics" in metadata
    assert metadata["nlp_diagnostics"]["relevance"]["lookup_paths"]


def test_plan_ensemble_selects_one_candidate_and_removes_unresolved_api(tiny_project: Config):
    db = DuckDBDatabase(tiny_project)
    schema = SchemaIndex.build(db)
    catalog = EndpointCatalog(tiny_project)
    router = QueryRouter(db.list_tables(), catalog)
    query = "List all journeys"
    normalized = normalize_query(query)
    routing = router.route(normalized["matching_text"])
    analysis = analyze_query(query, routing, schema, strategy="SQL_FIRST_API_VERIFY", config=tiny_project, endpoint_catalog=catalog, normalized=normalized)
    base_plan = Plan(
        "SQL_FIRST_API_VERIFY",
        "test",
        [
            PlanStep("sql", "count", sql='SELECT COUNT(*) AS count FROM "dim_campaign"'),
            PlanStep("api", "bad", method="GET", url="/data/foundation/schemaregistry/tenant/schemas/{schema_id}", params={}),
        ],
    )
    selected = select_plan_candidate(
        query=query,
        routing=routing,
        base_plan=base_plan,
        analysis=analysis,
        sql_validator=SQLValidator(schema),
        api_validator=APIValidator(catalog),
    )
    assert selected.selected
    assert all("{schema_id}" not in (step.url or "") for step in selected.plan.steps)


def test_sql_first_tool_call_budget_does_not_grow(tiny_project: Config):
    result = AgentExecutor(tiny_project).run("List all journeys", strategy="SQL_FIRST_API_VERIFY", query_id="budget")
    assert result["trajectory"]["tool_call_count"] <= 2


def test_tuning_and_robustness_report_writers_are_parseable(tiny_project: Config):
    from scripts.run_robustness_eval import write_outputs as write_robustness
    from scripts.tune_thresholds import write_outputs as write_tuning

    tuning_report = {
        "strategy": "SQL_FIRST_API_VERIFY",
        "grid_size": 1,
        "best_run_id": "run_01",
        "recommendation": "Keep current defaults.",
        "runs": [
            {
                "run_id": "run_01",
                "params": {"max_join_hints": 8},
                "summary": {
                    "avg_correctness_score": 1.0,
                    "avg_final_score": 1.0,
                    "avg_tool_call_count": 1.0,
                    "avg_estimated_tokens": 10,
                    "avg_runtime": 0.01,
                },
                "leave_one_family_out": {"journey_campaign": 1.0},
            }
        ],
    }
    robustness_report = {
        "strategy": "SQL_FIRST_API_VERIFY",
        "summary": {"high_risk_modes": [], "medium_risk_modes": []},
        "modes": [
            {
                "mode": "baseline",
                "summary": {
                    "avg_correctness_score": 1.0,
                    "avg_final_score": 1.0,
                    "avg_tool_call_count": 1.0,
                    "avg_estimated_tokens": 10,
                },
                "delta_vs_baseline": {"correctness": 0.0, "final": 0.0},
                "risk": "low",
            }
        ],
    }
    write_tuning(tiny_project, tuning_report)
    write_robustness(tiny_project, robustness_report)
    assert json.loads((tiny_project.outputs_dir / "threshold_tuning_report.json").read_text())["grid_size"] == 1
    assert json.loads((tiny_project.outputs_dir / "robustness_eval.json").read_text())["strategy"] == "SQL_FIRST_API_VERIFY"
