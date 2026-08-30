#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dashagent.config import DEFAULT_CONFIG
from dashagent.db import DuckDBDatabase, quote_ident
from dashagent.endpoint_catalog import EndpointCatalog
from dashagent.prompt_semantic_ir import extract_objective_prompt_features, normalize_prompt_text


CATEGORY_TARGETS: dict[str, int] = {
    "conceptual_no_tool": 60,
    "sql_only_local_snapshot": 120,
    "api_only_live_platform": 90,
    "sql_then_api_verification": 90,
    "mixed_conceptual_data": 40,
    "ambiguous_low_confidence": 40,
    "hard_stress": 60,
}

MAJOR_CATEGORY_LABELS = {
    "conceptual_no_tool": "A. Conceptual/no-tool prompts",
    "sql_only_local_snapshot": "B. SQL-only local snapshot prompts",
    "api_only_live_platform": "C. API-only live/platform prompts",
    "sql_then_api_verification": "D. SQL then API / API verification prompts",
    "mixed_conceptual_data": "E. Mixed conceptual + data prompts",
    "ambiguous_low_confidence": "F. Ambiguous / low-confidence prompts",
    "hard_stress": "G. Hard/stress prompts",
}

RUNTIME_GOLD_FORBIDDEN = {
    "gold_answer",
    "gold_answer_type",
    "acceptable_answer_variants",
    "required_facts",
    "forbidden_claims",
    "expected_route",
    "expected_evidence_need",
    "expected_tool_calls",
    "expected_observable_trace",
    "oracle_evidence",
    "grading_rubric",
    "oracle_sql",
    "oracle_api_endpoint",
}

DOMAIN_TEXT = {
    "SCHEMA": "schema",
    "SEGMENT": "segment",
    "AUDIENCE": "audience",
    "DATASET": "dataset",
    "JOURNEY": "journey",
    "CAMPAIGN": "campaign",
    "TAG": "tag",
    "AUDIT": "audit event",
    "MERGE_POLICY": "merge policy",
    "FLOW": "dataflow",
    "BATCH": "batch",
    "DESTINATION": "destination",
    "CONNECTOR": "connector",
    "FIELD": "field",
}

CONCEPT_DOMAINS = [
    "SCHEMA",
    "SEGMENT",
    "AUDIENCE",
    "DATASET",
    "JOURNEY",
    "TAG",
    "MERGE_POLICY",
    "FLOW",
    "BATCH",
    "DESTINATION",
    "CONNECTOR",
    "FIELD",
]

API_ENDPOINT_BY_DOMAIN = {
    "SCHEMA": "schema_registry_schemas",
    "AUDIENCE": "ups_audiences",
    "SEGMENT": "segment_definitions",
    "MERGE_POLICY": "merge_policies",
    "FLOW": "flowservice_flows",
    "BATCH": "catalog_batches",
    "DATASET": "catalog_datasets",
    "TAG": "unified_tags",
    "AUDIT": "audit_events",
}

SQL_TABLE_BY_DOMAIN = {
    "SCHEMA": "dim_blueprint",
    "DATASET": "dim_collection",
    "SEGMENT": "dim_segment",
    "AUDIENCE": "dim_segment",
    "JOURNEY": "dim_campaign",
    "CAMPAIGN": "dim_campaign",
    "FLOW": "dim_connector",
    "DESTINATION": "dim_target",
    "CONNECTOR": "dim_connector",
    "FIELD": "dim_property",
}

RELATIONSHIP_TABLES = [
    ("hkg_br_collection_segment", "datasets and segments", "COLLECTIONID", "SEGMENTID"),
    ("hkg_br_segment_target", "segments and destinations", "SEGMENTID", "TARGETID"),
    ("hkg_br_blueprint_collection", "schemas and datasets", "BLUEPRINTID", "COLLECTIONID"),
    ("hkg_br_source_collection", "connectors and datasets", "SOURCEID", "COLLECTIONID"),
    ("br_campaign_segment", "journeys and segments", "CAMPAIGNID", "SEGMENTID"),
]


@dataclass(frozen=True)
class SQLProfile:
    table: str
    domain: str
    columns: list[str]
    count: int
    sample: dict[str, Any]


def generate_suite(
    *,
    out_dir: Path | str | None = None,
    report_dir: Path | str | None = None,
    seed: int = 20260525,
) -> dict[str, Any]:
    rng = random.Random(seed)
    config = DEFAULT_CONFIG
    bench_dir = Path(out_dir) if out_dir is not None else config.data_dir / "benchmarks"
    reports_dir = Path(report_dir) if report_dir is not None else config.outputs_dir / "reports"
    bench_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    db = DuckDBDatabase(config=config)
    catalog = EndpointCatalog(config=config)
    sql_profiles = _load_sql_profiles(db)
    endpoint_profiles = _load_endpoint_profiles(catalog)

    runtime_rows: list[dict[str, Any]] = []
    gold_rows: list[dict[str, Any]] = []
    rejected_duplicates: list[dict[str, Any]] = []
    normalized_seen: set[str] = set()
    signature_seen: set[str] = set()

    def add_case(case: dict[str, Any], gold: dict[str, Any]) -> None:
        prompt = case["prompt"]
        norm = normalize_prompt_text(prompt)
        signature = json.dumps(gold["semantic_signature"], sort_keys=True)
        duplicate_reason = None
        if norm in normalized_seen:
            duplicate_reason = "normalized_duplicate"
        elif signature in signature_seen:
            duplicate_reason = "semantic_signature_duplicate"
        if duplicate_reason:
            rejected_duplicates.append(
                {
                    "prompt_id": case["prompt_id"],
                    "reason": duplicate_reason,
                    "prompt": prompt,
                    "normalized_prompt": norm,
                    "semantic_signature": gold["semantic_signature"],
                }
            )
            return
        normalized_seen.add(norm)
        signature_seen.add(signature)
        runtime_rows.append(case)
        gold_rows.append(gold)

    generators = [
        ("conceptual_no_tool", _conceptual_cases),
        ("sql_only_local_snapshot", _sql_cases),
        ("api_only_live_platform", _api_cases),
        ("sql_then_api_verification", _sql_api_cases),
        ("mixed_conceptual_data", _mixed_cases),
        ("ambiguous_low_confidence", _ambiguous_cases),
        ("hard_stress", _stress_cases),
    ]

    next_id = 1
    for category, factory in generators:
        cases = factory(
            count=CATEGORY_TARGETS[category],
            start_id=next_id,
            rng=rng,
            sql_profiles=sql_profiles,
            endpoint_profiles=endpoint_profiles,
            db=db,
        )
        for case, gold in cases:
            add_case(case, gold)
        next_id += CATEGORY_TARGETS[category]

    if len(runtime_rows) != 500:
        raise RuntimeError(f"Expected 500 accepted prompts, got {len(runtime_rows)} with {len(rejected_duplicates)} duplicates")

    suite_path = bench_dir / "dashagent_500_prompt_suite.jsonl"
    gold_path = bench_dir / "dashagent_500_prompt_suite_gold.jsonl"
    manifest_path = bench_dir / "dashagent_500_prompt_suite_manifest.json"
    rejected_path = reports_dir / "dashagent_500_prompt_rejected_duplicates.json"

    _write_jsonl(suite_path, runtime_rows)
    _write_jsonl(gold_path, gold_rows)

    category_counts = Counter(row["category"] for row in runtime_rows)
    split_counts = Counter(row["split"] for row in runtime_rows)
    domain_counts = Counter(row["domain_family"] for row in runtime_rows)
    tags = Counter(tag for row in runtime_rows for tag in row.get("tags", []))
    semantic_signatures = {gold["prompt_id"]: gold["semantic_signature"] for gold in gold_rows}
    manifest = {
        "suite_id": "dashagent_500_prompt_suite",
        "version": "2026-05-25-shadow-semantic-staged-v1",
        "seed": seed,
        "total_prompts": len(runtime_rows),
        "runtime_jsonl": str(suite_path),
        "gold_jsonl": str(gold_path),
        "diagnostic_internal_only": True,
        "organizer_score_replacement": False,
        "runtime_gold_separated": True,
        "uses_gold_at_runtime": False,
        "category_targets": CATEGORY_TARGETS,
        "category_distribution": dict(category_counts),
        "category_counts": dict(category_counts),
        "split_counts": dict(split_counts),
        "domain_counts": dict(domain_counts),
        "tag_counts": dict(tags),
        "semantic_signatures": semantic_signatures,
        "dedup": {
            "accepted": len(runtime_rows),
            "rejected": len(rejected_duplicates),
            "normalized_unique": len(normalized_seen),
            "semantic_signature_unique": len(signature_seen),
            "rejected_report": str(rejected_path),
        },
        "latest_code_paths_required": [
            "objective_prompt_features",
            "compact_json_llm_context",
            "semantic_intent_classifier",
            "routing_anti_hallucination_gate_feedback_revision",
            "no_tool_safety_verifier",
            "semantic_route_decision_ladder",
            "staged_evidence_policy",
            "post_sql_deterministic_policy",
            "post_sql_llm_advisor",
            "post_sql_api_call_verifier",
            "evidence_bus_answer_verifier_token_reduction_observation",
        ],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    rejected_path.write_text(json.dumps(rejected_duplicates, indent=2, sort_keys=True), encoding="utf-8")

    report = _suite_report(manifest, runtime_rows, gold_rows)
    report_json_path = reports_dir / "dashagent_500_prompt_suite_report.json"
    report_md_path = reports_dir / "dashagent_500_prompt_suite_report.md"
    report_json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    report_md_path.write_text(_suite_report_md(report), encoding="utf-8")

    db.close()
    return {
        **manifest,
        "suite_path": suite_path,
        "gold_path": gold_path,
        "manifest_path": manifest_path,
        "report_path": report_md_path,
        "report_json_path": report_json_path,
        "rejected_duplicates_path": rejected_path,
        "manifest": manifest,
    }


def _load_sql_profiles(db: DuckDBDatabase) -> dict[str, SQLProfile]:
    profiles: dict[str, SQLProfile] = {}
    for domain, table in SQL_TABLE_BY_DOMAIN.items():
        if not db.table_exists(table):
            continue
        columns = db.get_table_columns(table)
        count_sql = f"SELECT COUNT(*) AS count FROM {quote_ident(table)}"
        count_result = db.execute_sql(count_sql, allow_full_result=True)
        count = _first_int(count_result, "count")
        sample_cols = _sample_columns(columns)
        sample_sql = f"SELECT {', '.join(quote_ident(col) for col in sample_cols)} FROM {quote_ident(table)} LIMIT 1"
        sample_result = db.execute_sql(sample_sql, allow_full_result=True)
        sample = sample_result.get("rows", [{}])[0] if sample_result.get("rows") else {}
        profiles[domain] = SQLProfile(table=table, domain=domain, columns=columns, count=count, sample=sample)
    return profiles


def _load_endpoint_profiles(catalog: EndpointCatalog) -> dict[str, dict[str, Any]]:
    profiles: dict[str, dict[str, Any]] = {}
    for domain, endpoint_id in API_ENDPOINT_BY_DOMAIN.items():
        endpoint = catalog.by_id(endpoint_id)
        if endpoint is None:
            continue
        profiles[domain] = {
            "endpoint_id": endpoint.id,
            "path": endpoint.path,
            "method": endpoint.method,
            "family": domain,
            "safe_get": endpoint.method == "GET" and not endpoint.path_params,
        }
    return profiles


def _conceptual_cases(**kwargs: Any) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    count = kwargs["count"]
    start_id = kwargs["start_id"]
    cases: list[tuple[dict[str, Any], dict[str, Any]]] = []
    templates = [
        "What is a {term} in Adobe Experience Platform?",
        "Explain how a {term} works conceptually without listing current objects.",
        "Describe the role of a {term} for a data team.",
        "Why would an organization use a {term}?",
        "Compare the idea of a {term} with a related Adobe data object, conceptually only.",
    ]
    for i in range(count):
        domain = CONCEPT_DOMAINS[i % len(CONCEPT_DOMAINS)]
        prompt = templates[i % len(templates)].format(term=DOMAIN_TEXT[domain])
        prompt = f"{prompt} Use general terms for concept case {i + 1}."
        case = _runtime_row(start_id + i, prompt, "conceptual_no_tool", _difficulty(i), domain, "dev_generated", ["conceptual", "no_tool_expected"])
        if i in {0, 1, 2, 3}:
            case["tags"].append("domain_keyword_conceptual")
        gold = _gold_row(
            case,
            answer=f"A {DOMAIN_TEXT[domain]} is an Adobe data-platform concept. A correct answer explains the concept without asserting concrete counts, IDs, statuses, timestamps, or live platform state.",
            answer_type="conceptual_rubric",
            expected_route="LLM_SAFE_DIRECT",
            evidence_need="none",
            sql_required=False,
            api_required=False,
            api_optional=False,
            expected_sql_tables=[],
            expected_api_families=[],
            oracle_source="static_conceptual_rubric",
            semantic_signature=_signature("CONCEPT", domain, "none", [], [], "conceptual", i),
            required_facts=[f"general explanation of {DOMAIN_TEXT[domain]}", "no concrete platform facts"],
            forbidden_claims=["specific count", "specific ID", "live status", "timestamp claim"],
        )
        cases.append((case, gold))
    return cases


def _sql_cases(**kwargs: Any) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    count = kwargs["count"]
    start_id = kwargs["start_id"]
    sql_profiles: dict[str, SQLProfile] = kwargs["sql_profiles"]
    db: DuckDBDatabase = kwargs["db"]
    domains = [domain for domain in SQL_TABLE_BY_DOMAIN if domain in sql_profiles]
    operations = ["count", "list", "lookup", "status", "date", "relationship"]
    cases: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for i in range(count):
        operation = operations[i % len(operations)]
        if operation == "relationship":
            table, relation_text, left_col, right_col = RELATIONSHIP_TABLES[i % len(RELATIONSHIP_TABLES)]
            sql = f"SELECT COUNT(*) AS count FROM {quote_ident(table)}"
            result = db.execute_sql(sql, allow_full_result=True)
            answer = f"The local snapshot relationship table for {relation_text} contains {_first_int(result, 'count')} rows."
            prompt = f"How many local snapshot relationships connect {relation_text}? Return only evidence from the local database for SQL case {i + 1}."
            domain = "FIELD" if "property" in relation_text else "SEGMENT"
            expected_tables = [table]
            required_fields = [left_col, right_col]
        else:
            domain = domains[i % len(domains)]
            profile = sql_profiles[domain]
            sql, answer, required_fields = _sql_oracle_for_operation(profile, operation, db)
            prompt = _sql_prompt_for_operation(domain, operation, i, profile)
            expected_tables = [profile.table]
        case = _runtime_row(start_id + i, prompt, "sql_only_local_snapshot", _difficulty(i), domain, "dev_generated", ["sql_required", operation])
        gold = _gold_row(
            case,
            answer=answer,
            answer_type=_answer_type_for_operation(operation),
            expected_route="SQL_ONLY",
            evidence_need="sql",
            sql_required=True,
            api_required=False,
            api_optional=False,
            expected_sql_tables=expected_tables,
            expected_api_families=[],
            oracle_source="local_db",
            oracle_sql=sql,
            semantic_signature=_signature("DATA", domain, "sql", required_fields, [], operation, i),
            required_facts=[answer],
            forbidden_claims=["live API state", "Adobe API returned no data"],
        )
        cases.append((case, gold))
    return cases


def _api_cases(**kwargs: Any) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    count = kwargs["count"]
    start_id = kwargs["start_id"]
    endpoint_profiles: dict[str, dict[str, Any]] = kwargs["endpoint_profiles"]
    domains = list(endpoint_profiles)
    templates = [
        "List current Adobe {term} using the platform API.",
        "Check the live API for {term} metadata.",
        "Show current {term} records from the Adobe endpoint.",
        "Return live platform state for {term}.",
        "Use a safe GET call to inspect {term}.",
    ]
    cases: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for i in range(count):
        domain = domains[i % len(domains)]
        endpoint = endpoint_profiles[domain]
        prompt = f"{templates[i % len(templates)].format(term=DOMAIN_TEXT[domain])} API case {i + 1}."
        case = _runtime_row(start_id + i, prompt, "api_only_live_platform", _difficulty(i), domain, "stress_generated", ["api_required", "safe_get"])
        gold = _api_gold(case, domain, endpoint, i, expected_route="API_ONLY", evidence_need="api", sql_required=False, api_required=True, api_optional=False)
        cases.append((case, gold))
    return cases


def _sql_api_cases(**kwargs: Any) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    count = kwargs["count"]
    start_id = kwargs["start_id"]
    sql_profiles: dict[str, SQLProfile] = kwargs["sql_profiles"]
    endpoint_profiles: dict[str, dict[str, Any]] = kwargs["endpoint_profiles"]
    db: DuckDBDatabase = kwargs["db"]
    domains = [domain for domain in SQL_TABLE_BY_DOMAIN if domain in sql_profiles and domain in endpoint_profiles]
    templates = [
        "Use the local snapshot for {term}, then call the live API only if the SQL answer is incomplete.",
        "Count local {term} rows and verify with a safe API probe if needed.",
        "Find local {term} names, then use the current endpoint only when it adds requested evidence.",
        "Answer from SQL first for {term}; do not let optional API suppress direct SQL evidence.",
        "If SQL returns zero rows for {term}, check whether the live endpoint has scoped evidence.",
    ]
    cases: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for i in range(count):
        domain = domains[i % len(domains)]
        profile = sql_profiles[domain]
        endpoint = endpoint_profiles[domain]
        sql, sql_answer, required_fields = _sql_oracle_for_operation(profile, "count" if i % 2 == 0 else "list", db)
        prompt = f"{templates[i % len(templates)].format(term=DOMAIN_TEXT[domain])} SQL/API policy case {i + 1}."
        tags = ["sql_first", "api_optional_verify"]
        if i % 5 == 0:
            tags.append("post_sql_direct_skip_optional_api")
        if i % 7 == 0:
            tags.append("post_sql_partial_api_can_fill")
        case = _runtime_row(start_id + i, prompt, "sql_then_api_verification", _difficulty(i), domain, "robustness_generated", tags)
        answer = f"{sql_answer} API evidence is optional unless SQL is incomplete or live platform state is explicitly requested."
        gold = _gold_row(
            case,
            answer=answer,
            answer_type="caveat",
            expected_route="SQL_PRIMARY_API_VERIFY",
            evidence_need="sql_then_api",
            sql_required=True,
            api_required=False,
            api_optional=True,
            expected_sql_tables=[profile.table],
            expected_api_families=[endpoint["endpoint_id"]],
            oracle_source="mixed",
            oracle_sql=sql,
            oracle_api_endpoint=endpoint["endpoint_id"],
            semantic_signature=_signature("DATA", domain, "sql_then_api", required_fields, [endpoint["endpoint_id"]], "verify", i),
            required_facts=[sql_answer, "API optional unless SQL is partial or live state is requested"],
            forbidden_claims=["API no data without API evidence", "SQL unavailable without validation failure"],
        )
        cases.append((case, gold))
    return cases


def _mixed_cases(**kwargs: Any) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    count = kwargs["count"]
    start_id = kwargs["start_id"]
    endpoint_profiles: dict[str, dict[str, Any]] = kwargs["endpoint_profiles"]
    domains = ["MERGE_POLICY", "SCHEMA", "TAG", "SEGMENT", "DATASET", "FLOW", "AUDIT", "AUDIENCE"]
    cases: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for i in range(count):
        domain = domains[i % len(domains)]
        endpoint = endpoint_profiles.get(domain) or endpoint_profiles["SCHEMA"]
        prompt = f"Explain what a {DOMAIN_TEXT[domain]} is and list current {DOMAIN_TEXT[domain]} objects if the live endpoint supports it. Mixed case {i + 1}."
        case = _runtime_row(start_id + i, prompt, "mixed_conceptual_data", _difficulty(i), domain, "robustness_generated", ["mixed_conceptual_data", "mixed_no_tool_block"])
        gold = _gold_row(
            case,
            answer=f"A correct answer includes a general concept explanation for {DOMAIN_TEXT[domain]} and uses evidence for the requested current object list or reports API evidence unavailable.",
            answer_type="caveat",
            expected_route="EVIDENCE_PIPELINE",
            evidence_need="mixed",
            sql_required=False,
            api_required=True,
            api_optional=False,
            expected_sql_tables=[],
            expected_api_families=[endpoint["endpoint_id"]],
            oracle_source="mixed",
            oracle_api_endpoint=endpoint["endpoint_id"],
            semantic_signature=_signature("MIXED", domain, "mixed", ["concept"], [endpoint["endpoint_id"]], "mixed", i),
            required_facts=["conceptual explanation", "evidence-backed current object handling"],
            forbidden_claims=["pure no-tool concrete list", "fabricated live object"],
        )
        cases.append((case, gold))
    return cases


def _ambiguous_cases(**kwargs: Any) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    count = kwargs["count"]
    start_id = kwargs["start_id"]
    endpoint_profiles: dict[str, dict[str, Any]] = kwargs["endpoint_profiles"]
    sql_profiles: dict[str, SQLProfile] = kwargs["sql_profiles"]
    db: DuckDBDatabase = kwargs["db"]
    patterns = [
        ("Schemas, in plain language.", "SCHEMA", "LLM_SAFE_DIRECT", "none", False, False, ["low_low_safe_direct"]),
        ("Current tags, quick check.", "TAG", "SAFE_API_PROBE", "api", False, True, ["low_low_safe_api_probe"]),
        ("Those failed dataflow runs: show what is available.", "FLOW", "EVIDENCE_PIPELINE", "api", False, True, ["low_low_concrete_data"]),
        ("Dataset details, but keep it concise.", "DATASET", "EVIDENCE_PIPELINE", "sql", True, False, ["low_low_concrete_data"]),
    ]
    cases: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for i in range(count):
        text, domain, route, need, sql_required, api_required, tags = patterns[i % len(patterns)]
        endpoint = endpoint_profiles.get(domain) or endpoint_profiles["SCHEMA"]
        oracle_sql = None
        expected_sql_tables = [SQL_TABLE_BY_DOMAIN.get(domain, "")] if sql_required and domain in SQL_TABLE_BY_DOMAIN else []
        if sql_required:
            profile = sql_profiles.get(domain)
            if profile is not None:
                oracle_sql, _, _ = _sql_oracle_for_operation(profile, "count", db)
                expected_sql_tables = [profile.table]
        prompt = f"{text} Ambiguous case {i + 1}."
        case = _runtime_row(start_id + i, prompt, "ambiguous_low_confidence", _difficulty(i), domain, "stress_generated", ["low_confidence_ladder", *tags])
        gold = _gold_row(
            case,
            answer=_ambiguous_answer(domain, route, need),
            answer_type="caveat" if need != "none" else "conceptual_rubric",
            expected_route=route,
            evidence_need=need,
            sql_required=sql_required,
            api_required=api_required,
            api_optional=False,
            expected_sql_tables=expected_sql_tables,
            expected_api_families=[endpoint["endpoint_id"]] if api_required else [],
            oracle_source="mixed" if need != "none" else "static_conceptual_rubric",
            oracle_sql=oracle_sql,
            oracle_api_endpoint=endpoint["endpoint_id"] if api_required else None,
            semantic_signature=_signature("AMBIG", domain, need, [], [endpoint["endpoint_id"]] if api_required else [], "ambiguous", i),
            required_facts=[f"route resolves to {route}", f"evidence need {need}"],
            forbidden_claims=["fabricated data", "clarification request"],
        )
        cases.append((case, gold))
    return cases


def _stress_cases(**kwargs: Any) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    count = kwargs["count"]
    start_id = kwargs["start_id"]
    sql_profiles: dict[str, SQLProfile] = kwargs["sql_profiles"]
    endpoint_profiles: dict[str, dict[str, Any]] = kwargs["endpoint_profiles"]
    db: DuckDBDatabase = kwargs["db"]
    stress_specs = [
        ("List schemas even though I first ask: what is a schema?", "SCHEMA", ["anti_hallucination_no_tool_conflict"], "SQL_THEN_API", "mixed"),
        ("Use capability API_FAKE_THING? No, list current tags from the valid tag endpoint.", "TAG", ["anti_hallucination_unknown_capability"], "API_ONLY", "api"),
        ("Explain merge policy and list current merge policies.", "MERGE_POLICY", ["mixed_no_tool_block"], "EVIDENCE_PIPELINE", "mixed"),
        ("Segment status after SQL: call the API if SQL lacks status.", "SEGMENT", ["post_sql_advisor_accept"], "SQL_PRIMARY_API_VERIFY", "sql_then_api"),
        ("Dataset count from SQL; block any advisor that invents an unknown endpoint.", "DATASET", ["post_sql_advisor_block"], "SQL_PRIMARY_API_VERIFY", "sql_then_api"),
        ("Schema registry maybe maybe maybe.", "SCHEMA", ["invalid_json_fallback"], "EVIDENCE_PIPELINE", "api"),
    ]
    generic = [
        ("Without using the word list, return available {term} records from evidence.", "sql"),
        ("In one answer, define {term} and provide current evidence where available.", "mixed"),
        ("Which {term} objects have status information? Use observable evidence.", "sql"),
        ("For {term}, prefer local snapshot facts before live verification.", "sql_then_api"),
        ("Give IDs and names for {term}; avoid unsupported live claims.", "sql"),
    ]
    cases: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for i in range(count):
        if i < len(stress_specs):
            prompt, domain, special_tags, route, need = stress_specs[i]
            prompt = f"{prompt} Stress trigger {i + 1}."
        else:
            domain = CONCEPT_DOMAINS[i % len(CONCEPT_DOMAINS)]
            template, need = generic[i % len(generic)]
            prompt = f"{template.format(term=DOMAIN_TEXT[domain])} Stress case {i + 1}."
            route = "EVIDENCE_PIPELINE" if need != "none" else "LLM_SAFE_DIRECT"
            special_tags = ["adversarial_wording", f"stress_need_{need}"]
        endpoint = endpoint_profiles.get(domain) or endpoint_profiles.get("SCHEMA")
        profile = sql_profiles.get(domain) or sql_profiles.get("SCHEMA")
        sql = None
        answer = "The correct behavior is to use observable evidence only and avoid unsupported claims."
        expected_tables: list[str] = []
        if need in {"sql", "sql_then_api", "mixed"} and profile is not None:
            sql, sql_answer, _fields = _sql_oracle_for_operation(profile, "count", db)
            answer = sql_answer
            expected_tables = [profile.table]
        expected_apis = [endpoint["endpoint_id"]] if endpoint and need in {"api", "sql_then_api", "mixed"} else []
        case = _runtime_row(start_id + i, prompt, "hard_stress", _difficulty(i), domain, "stress_generated", ["hard_stress", *special_tags])
        gold = _gold_row(
            case,
            answer=answer,
            answer_type="caveat",
            expected_route=route,
            evidence_need=need,
            sql_required=bool(expected_tables),
            api_required=need == "api",
            api_optional=need in {"sql_then_api", "mixed"},
            expected_sql_tables=expected_tables,
            expected_api_families=expected_apis,
            oracle_source="mixed" if expected_apis and expected_tables else ("live_api" if expected_apis else "local_db"),
            oracle_sql=sql,
            oracle_api_endpoint=expected_apis[0] if expected_apis else None,
            semantic_signature=_signature("STRESS", domain, need, expected_tables, expected_apis, "stress", i),
            required_facts=["latest harness path exercised", f"expected route {route}"],
            forbidden_claims=["unsupported concrete fact", "reasoning transcript"],
        )
        cases.append((case, gold))
    return cases


def _runtime_row(
    numeric_id: int,
    prompt: str,
    category: str,
    difficulty: str,
    domain: str,
    split: str,
    tags: list[str],
) -> dict[str, Any]:
    return {
        "prompt_id": f"da500_{numeric_id:04d}",
        "prompt": prompt,
        "category": category,
        "difficulty": difficulty,
        "domain_family": domain,
        "split": split,
        "tags": _dedupe(tags),
    }


def _gold_row(
    case: dict[str, Any],
    *,
    answer: str,
    answer_type: str,
    expected_route: str,
    evidence_need: str,
    sql_required: bool,
    api_required: bool,
    api_optional: bool,
    expected_sql_tables: list[str],
    expected_api_families: list[str],
    oracle_source: str,
    semantic_signature: dict[str, Any],
    required_facts: list[str],
    forbidden_claims: list[str],
    oracle_sql: str | None = None,
    oracle_api_endpoint: str | None = None,
) -> dict[str, Any]:
    features = extract_objective_prompt_features(case["prompt"]).to_dict()
    expected_codes = _expected_feature_codes(features)
    return {
        "prompt_id": case["prompt_id"],
        "gold_answer": answer,
        "gold_answer_type": answer_type,
        "acceptable_answer_variants": _variants_for_answer(answer),
        "required_facts": required_facts,
        "forbidden_claims": forbidden_claims,
        "expected_route": expected_route,
        "expected_evidence_need": evidence_need,
        "expected_tool_calls": {
            "sql_required": sql_required,
            "api_required": api_required,
            "api_optional": api_optional,
            "expected_api_families": expected_api_families,
            "expected_sql_tables": [table for table in expected_sql_tables if table],
        },
        "expected_observable_trace": [
            {"stage": "objective_features", "expected_codes": expected_codes},
            {"stage": "semantic_routing", "expected_behavior": expected_route},
            {"stage": "evidence_policy", "expected_behavior": evidence_need},
            {"stage": "tool_execution", "expected_behavior": _tool_behavior(sql_required, api_required, api_optional)},
            {"stage": "answer_grounding", "expected_behavior": "use EvidenceBus facts and keep unsupported claims at zero"},
        ],
        "oracle_evidence": {
            "oracle_sql": oracle_sql,
            "oracle_api_endpoint": oracle_api_endpoint,
            "oracle_source": oracle_source,
        },
        "grading_rubric": {
            "correctness_points": required_facts,
            "evidence_points": [f"expected evidence need: {evidence_need}", f"expected route: {expected_route}"],
            "format_points": ["compact answer", "no reasoning transcript"],
            "partial_credit_rules": [
                "credit objective feature extraction separately from final correctness",
                "credit live_empty/api_error distinction when API is unavailable",
                "do not award evidence credit for unsupported concrete claims",
            ],
        },
        "semantic_signature": semantic_signature,
    }


def _api_gold(
    case: dict[str, Any],
    domain: str,
    endpoint: dict[str, Any],
    index: int,
    *,
    expected_route: str,
    evidence_need: str,
    sql_required: bool,
    api_required: bool,
    api_optional: bool,
) -> dict[str, Any]:
    answer = (
        f"The correct behavior is to use safe GET evidence from {endpoint['endpoint_id']} for {DOMAIN_TEXT[domain]}. "
        "If live API evidence is unavailable or errors, report that API evidence is unavailable rather than saying no data."
    )
    return _gold_row(
        case,
        answer=answer,
        answer_type="caveat",
        expected_route=expected_route,
        evidence_need=evidence_need,
        sql_required=sql_required,
        api_required=api_required,
        api_optional=api_optional,
        expected_sql_tables=[],
        expected_api_families=[endpoint["endpoint_id"]],
        oracle_source="live_api",
        oracle_api_endpoint=endpoint["endpoint_id"],
        semantic_signature=_signature("LIVE_API", domain, evidence_need, [], [endpoint["endpoint_id"]], "api", index),
        required_facts=[endpoint["endpoint_id"], "safe GET evidence", "do not treat API error as no data"],
        forbidden_claims=["global no data without live_empty", "mutating API call", "unresolved path parameter"],
    )


def _sql_oracle_for_operation(profile: SQLProfile, operation: str, db: DuckDBDatabase) -> tuple[str, str, list[str]]:
    cols = profile.columns
    table = profile.table
    id_col = _first_col(cols, ("ID",)) or cols[0]
    name_col = _first_col(cols, ("NAME", "LABELS")) or id_col
    status_col = _first_col(cols, ("STATUS", "STATE", "LIFECYCLESTATUS"))
    timestamp_col = _first_col(cols, ("UPDATEDTIME", "CREATEDTIME", "LASTDEPLOYEDTIME", "EVALUATIONCOMPLETEDTIME"))
    if operation == "count":
        sql = f"SELECT COUNT(*) AS count FROM {quote_ident(table)}"
        result = db.execute_sql(sql, allow_full_result=True)
        return sql, f"The local snapshot table {table} contains {_first_int(result, 'count')} rows.", ["count"]
    if operation == "list":
        selected = _dedupe([id_col, name_col, status_col or "", timestamp_col or ""])[:4]
        sql = f"SELECT {', '.join(quote_ident(col) for col in selected)} FROM {quote_ident(table)} LIMIT 5"
        result = db.execute_sql(sql, allow_full_result=True)
        row_count = len(result.get("rows") or [])
        return sql, f"The local snapshot lists {row_count} {profile.domain.lower()} rows from {table}.", selected
    if operation == "lookup":
        value = profile.sample.get(name_col) or profile.sample.get(id_col)
        where = f" WHERE {quote_ident(name_col)} = {_sql_literal(value)}" if value not in (None, "") else ""
        selected = _dedupe([id_col, name_col, status_col or "", timestamp_col or ""])[:4]
        sql = f"SELECT {', '.join(quote_ident(col) for col in selected)} FROM {quote_ident(table)}{where} LIMIT 5"
        result = db.execute_sql(sql, allow_full_result=True)
        row_count = len(result.get("rows") or [])
        return sql, f"The local snapshot lookup in {table} returned {row_count} matching rows.", selected
    if operation == "status" and status_col:
        sql = f"SELECT {quote_ident(status_col)} AS status, COUNT(*) AS count FROM {quote_ident(table)} GROUP BY {quote_ident(status_col)} ORDER BY count DESC LIMIT 5"
        result = db.execute_sql(sql, allow_full_result=True)
        row_count = len(result.get("rows") or [])
        return sql, f"The local snapshot returned {row_count} status buckets from {table}.", [status_col, "count"]
    if operation == "date" and timestamp_col:
        sql = f"SELECT {quote_ident(id_col)} AS id, {quote_ident(timestamp_col)} AS timestamp FROM {quote_ident(table)} ORDER BY {quote_ident(timestamp_col)} DESC NULLS LAST LIMIT 5"
        result = db.execute_sql(sql, allow_full_result=True)
        row_count = len(result.get("rows") or [])
        return sql, f"The local snapshot returned {row_count} timestamp rows from {table}.", [id_col, timestamp_col]
    return _sql_oracle_for_operation(profile, "count", db)


def _sql_prompt_for_operation(domain: str, operation: str, index: int, profile: SQLProfile) -> str:
    term = DOMAIN_TEXT[domain]
    if operation == "count":
        return f"How many {term} records are in the local snapshot? SQL case {index + 1}."
    if operation == "list":
        return f"List local {term} IDs and names from the snapshot. SQL case {index + 1}."
    if operation == "lookup":
        name = profile.sample.get("NAME") or profile.sample.get("LABELSSEGMENT") or profile.sample.get("LABELSCAMPAIGN") or profile.sample.get("COLLECTIONID") or "the sampled object"
        return f"Find local snapshot details for {term} named {json.dumps(str(name))}. SQL case {index + 1}."
    if operation == "status":
        return f"Show local status/state distribution for {term} records. SQL case {index + 1}."
    if operation == "date":
        return f"When were the most recent local {term} records updated or created? SQL case {index + 1}."
    return f"Use local SQL evidence for {term}. SQL case {index + 1}."


def _sample_columns(columns: list[str]) -> list[str]:
    preferred = []
    for needles in [("ID",), ("NAME", "LABELS"), ("STATUS", "STATE"), ("UPDATEDTIME", "CREATEDTIME", "LASTDEPLOYEDTIME"), ("ROWCOUNT", "TOTALMEMBERS")]:
        col = _first_col(columns, needles)
        if col:
            preferred.append(col)
    return _dedupe(preferred or columns[:4])[:5]


def _first_col(columns: list[str], needles: tuple[str, ...]) -> str | None:
    for col in columns:
        upper = col.upper()
        if any(needle in upper for needle in needles):
            return col
    return None


def _first_int(result: dict[str, Any], key: str) -> int:
    rows = result.get("rows") if isinstance(result, dict) else []
    if rows and isinstance(rows[0], dict):
        try:
            return int(rows[0].get(key) or rows[0].get(key.upper()) or 0)
        except Exception:
            return 0
    return 0


def _sql_literal(value: Any) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _signature(
    intent: str,
    domain: str,
    evidence_need: str,
    requested_fields: list[str],
    entities: list[str],
    operation: str,
    index: int,
) -> dict[str, Any]:
    return {
        "intent": intent,
        "domain_family": domain,
        "evidence_need": evidence_need,
        "requested_fields": requested_fields,
        "entities": entities,
        "operation": operation,
        "case_axis": f"{operation}_{index:03d}",
    }


def _expected_feature_codes(features: dict[str, Any]) -> list[str]:
    codes: list[str] = []
    for key in ("cue", "retr", "count", "status", "date", "fields", "rel", "domain", "entity", "cap", "flags"):
        values = features.get(key) or []
        if isinstance(values, list):
            codes.extend(str(value) for value in values)
    return _dedupe(codes)[:16]


def _tool_behavior(sql_required: bool, api_required: bool, api_optional: bool) -> str:
    if sql_required and api_required:
        return "execute validated SQL and call validated safe GET API"
    if sql_required and api_optional:
        return "execute validated SQL; call safe GET API only if evidence policy needs it"
    if sql_required:
        return "execute validated SQL only"
    if api_required:
        return "call validated safe GET API only"
    return "no SQL/API tool required"


def _answer_type_for_operation(operation: str) -> str:
    return {
        "count": "count",
        "list": "list",
        "lookup": "exact",
        "status": "status",
        "date": "date",
        "relationship": "count",
    }.get(operation, "exact")


def _variants_for_answer(answer: str) -> list[str]:
    return [answer[:300]]


def _difficulty(index: int) -> str:
    return ["easy", "medium", "hard"][index % 3]


def _ambiguous_answer(domain: str, route: str, need: str) -> str:
    if need == "none":
        return f"The prompt can be answered as a general {DOMAIN_TEXT[domain]} concept without concrete platform facts."
    return f"The prompt should resolve without clarification to {route} with evidence need {need}."


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return out


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _suite_report(manifest: dict[str, Any], runtime_rows: list[dict[str, Any]], gold_rows: list[dict[str, Any]]) -> dict[str, Any]:
    examples: dict[str, dict[str, Any]] = {}
    gold_by_id = {row["prompt_id"]: row for row in gold_rows}
    for category in CATEGORY_TARGETS:
        row = next(item for item in runtime_rows if item["category"] == category)
        examples[category] = {
            "runtime_prompt": row,
            "gold": gold_by_id[row["prompt_id"]],
        }
    return {
        "suite_id": manifest["suite_id"],
        "total_prompts": manifest["total_prompts"],
        "category_counts": manifest["category_counts"],
        "split_counts": manifest["split_counts"],
        "dedup": manifest["dedup"],
        "stress_tags_present": {
            tag: manifest["tag_counts"].get(tag, 0)
            for tag in [
                "anti_hallucination_no_tool_conflict",
                "anti_hallucination_unknown_capability",
                "mixed_no_tool_block",
                "low_low_safe_direct",
                "low_low_safe_api_probe",
                "post_sql_advisor_accept",
                "post_sql_advisor_block",
                "invalid_json_fallback",
            ]
        },
        "runtime_gold_separated": True,
        "examples": examples,
    }


def _suite_report_md(report: dict[str, Any]) -> str:
    lines = [
        "# DashAgent 500-Prompt Suite",
        "",
        f"- total_prompts: {report['total_prompts']}",
        f"- runtime_gold_separated: {report['runtime_gold_separated']}",
        "- diagnostic_internal_only: true",
        "",
        "## Category Counts",
    ]
    for category, count in report["category_counts"].items():
        lines.append(f"- {category}: {count}")
    lines.extend(["", "## Stress Tags"])
    for tag, count in report["stress_tags_present"].items():
        lines.append(f"- {tag}: {count}")
    lines.extend(["", "## Example Runtime Prompts"])
    for category, payload in report["examples"].items():
        row = payload["runtime_prompt"]
        lines.append(f"- {category}: `{row['prompt_id']}` {row['prompt']}")
    lines.extend(["", "Gold rows are stored only in the gold JSONL and are not present in runtime prompt rows."])
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the internal DashAgent 500-prompt benchmark suite.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_CONFIG.data_dir / "benchmarks")
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_CONFIG.outputs_dir / "reports")
    parser.add_argument("--seed", type=int, default=20260525)
    args = parser.parse_args()
    result = generate_suite(out_dir=args.out_dir, report_dir=args.report_dir, seed=args.seed)
    print(json.dumps({"ok": True, "suite": str(result["suite_path"]), "gold": str(result["gold_path"]), "manifest": str(result["manifest_path"])}, sort_keys=True))


if __name__ == "__main__":
    main()
