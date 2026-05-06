from __future__ import annotations

from types import SimpleNamespace

from dashagent.cache import get_sql_result_cache, set_sql_result_cache, sql_result_cache_key
from dashagent.context_cards import context_card_for
from dashagent.evidence_bus import EvidenceBus
from dashagent.plan_optimizer import optimize_plan_steps
from dashagent.query_analysis import analyze_query
from dashagent.router import QueryRouter
from dashagent.schema_index import SchemaIndex
from dashagent.db import DuckDBDatabase
from dashagent.lookup_paths import predict_lookup_path


def test_evidence_bus_forwards_target_id_to_destination_param():
    bus = EvidenceBus()
    bus.observe_sql(
        SimpleNamespace(family="destination_export_recent"),
        {"ok": True, "rows": [{"target_id": "target-123", "dataflow_name": "SMS Opt-In"}]},
    )
    step = SimpleNamespace(
        action="api",
        family="audience_by_destination_id",
        url="/data/core/ups/audiences",
        params={"property": "destinationId==<destination_id>", "limit": "5"},
    )
    actions = bus.forward_to_step(step)
    assert step.params["property"] == "destinationId==target-123"
    assert actions


def test_plan_optimizer_keeps_json_params_but_dedupes_api():
    step = SimpleNamespace(
        action="api",
        family="journey_by_name",
        method="GET",
        url="/ajo/journey",
        params={"filter": "name==Birthday Message"},
        warnings=[],
    )
    result = optimize_plan_steps([step, step], strategy="SQL_FIRST_API_VERIFY", route_type="SQL_THEN_API")
    assert len(result.steps) == 1
    assert "duplicate API" in " ".join(result.actions)


def test_query_analysis_predicts_lookup_path(tiny_project):
    db = DuckDBDatabase(tiny_project)
    schema = SchemaIndex.build(db)
    router = QueryRouter(db.list_tables(), None)
    query = "When was the journey 'Birthday Message' published?"
    routing = router.route(query)
    analysis = analyze_query(query, routing, schema, strategy="SQL_FIRST_API_VERIFY", config=tiny_project)
    assert analysis.answer_family == "journey_published"
    assert analysis.lookup_path.family == "journey_campaign"


def test_context_card_and_sql_cache(tiny_project):
    path = predict_lookup_path("List all tags in this sandbox.", "tags")
    card = context_card_for(path)
    assert card and card["family"] == "tags"
    key = sql_result_cache_key("SELECT 1", tiny_project, {"test": 1})
    set_sql_result_cache(key, {"ok": True, "rows": [{"one": 1}]})
    assert get_sql_result_cache(key)["rows"][0]["one"] == 1
