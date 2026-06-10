from __future__ import annotations

from dashagent.config import Config
from dashagent.db import DuckDBDatabase
from dashagent.endpoint_catalog import EndpointCatalog
from dashagent.schema_index import SchemaIndex
from dashagent.validators import SQLValidator


def _schema(config: Config):
    db = DuckDBDatabase(config)
    schema = SchemaIndex.build(db)
    return db, schema


def test_nlp_generalization_normalizes_intent_domain_and_entities():
    from dashagent.nlp_generalization_layer import normalize_prompt_semantics

    semantics = normalize_prompt_semantics("When was the journey 'Welcome Journey' published?")

    assert semantics["canonical_intent"] == "DATE"
    assert semantics["canonical_domain"] == "JOURNEY"
    assert semantics["canonical_entities"] == ["Welcome Journey"]
    assert semantics["canonical_filters"][0]["semantic_field"] == "name"
    assert semantics["timestamp_semantics"] == "published"


def test_semantic_slot_schema_and_verifier_reject_api_only_for_local_snapshot():
    from dashagent.weak_model_semantic_slots import normalize_semantic_slots
    from dashagent.weak_model_slot_verifier import verify_semantic_slots

    slots = normalize_semantic_slots(
        {
            "intent": "DATE",
            "domain": "JOURNEY",
            "quoted_entities": ["Welcome Journey"],
            "filters": [{"semantic_field": "name", "operator": "equals", "value": "Welcome Journey"}],
            "aggregation": "none",
            "evidence_need": "api_only",
            "confidence": 0.7,
        },
        prompt="When was the journey 'Welcome Journey' published?",
    )
    result = verify_semantic_slots("When was the journey 'Welcome Journey' published?", slots)

    assert result["ok"] is False
    assert "sql_likely_required_api_only" in result["errors"]
    assert result["corrected_slots"]["evidence_need"] == "sql_first"


def test_slot_to_sql_compiler_maps_business_slots_to_valid_sql(tiny_project):
    from dashagent.semantic_slot_compiler import compile_semantic_slots
    from dashagent.weak_model_semantic_slots import normalize_semantic_slots

    db, schema = _schema(tiny_project)
    slots = normalize_semantic_slots(
        {
            "intent": "DATE",
            "domain": "JOURNEY",
            "quoted_entities": ["Welcome Journey"],
            "filters": [{"semantic_field": "name", "operator": "equals", "value": "Welcome Journey"}],
            "aggregation": "none",
            "evidence_need": "sql_first",
            "confidence": 0.8,
        },
        prompt="When was the journey 'Welcome Journey' published?",
    )
    compiled = compile_semantic_slots(slots, schema, EndpointCatalog(tiny_project), SQLValidator(schema))

    assert compiled["ok"] is True
    assert compiled["sql_candidates"]
    sql = compiled["sql_candidates"][0]["sql"]
    assert "dim_campaign" in sql
    assert "lastdeployedtime" in sql.lower()
    assert SQLValidator(schema).validate(sql).ok
    result = db.execute_sql(sql)
    assert result["ok"] is True
    assert result["rows"][0]["lastdeployedtime"] == "2026-01-01"
    db.close()


def test_answer_grounder_uses_sql_evidence_and_blocks_unsupported_claims():
    from dashagent.weak_model_answer_grounder import ground_weak_model_answer

    result = ground_weak_model_answer(
        "How many journeys are there?",
        model_answer="There are 99 journeys.",
        sql_result={"ok": True, "row_count": 1, "rows": [{"count": 2}]},
        api_result=None,
        answer_intent="COUNT",
    )

    assert result["unsupported_claim_count"] == 0
    assert result["fallback_used"] is True
    assert "2" in result["answer"]
    assert result["answer_used_sql"] is True


def test_weak_model_eval_definition_and_variants_are_shadow_only(tiny_project):
    from scripts.run_weak_model_lift_eval import WEAK_MODEL_VARIANTS, run_weak_model_lift_eval

    assert "weak_full_dashagent_scaffold" in WEAK_MODEL_VARIANTS
    payload = run_weak_model_lift_eval(tiny_project, max_examples=1, variants=["weak_semantic_slots_only"], execute_real=False)

    assert payload["diagnostic_only"] is True
    assert payload["promotion_allowed"] is False
    assert payload["packaged_runtime_changed"] is False
    assert payload["summary"]["modes"][0]["mode"] == "weak_semantic_slots_only"
