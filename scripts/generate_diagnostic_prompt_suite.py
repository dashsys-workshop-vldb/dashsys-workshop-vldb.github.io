#!/usr/bin/env python
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.eval_harness import find_example_list
from dashagent.trajectory import redact_secrets


GENERATION_TYPES = {"paraphrase", "domain_coverage", "edge_case", "hidden_style", "dry_run_api", "answer_quality"}
ROUTES = {"SQL_ONLY", "SQL_PLUS_API", "API_ONLY", "LOCAL_DB_ONLY", "UNKNOWN"}
INTENTS = {"COUNT", "LIST", "STATUS", "DATE", "BOOLEAN", "ID_LOOKUP", "SUMMARY", "COMPARISON", "UNKNOWN"}
DOMAINS = {
    "journey_campaign",
    "schema_dataset",
    "segment_audience",
    "destination_flow",
    "dataflow_run",
    "merge_policy",
    "tags",
    "batch",
    "observability",
    "unknown",
}


def main() -> int:
    config = Config.from_env(ROOT)
    payload = generate_prompt_suite(config)
    print(
        json.dumps(
            {
                "prompts": payload["summary"]["total_generated_prompts"],
                "json": str(config.data_dir / "generated_prompt_suite.json"),
                "summary": str(config.outputs_dir / "reports" / "generated_prompt_suite_summary.json"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def generate_prompt_suite(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    config.data_dir.mkdir(parents=True, exist_ok=True)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    source_examples = _load_source_examples(config)
    suite, diagnostics = _build_suite(source_examples)
    summary = _build_summary(source_examples, suite, diagnostics)

    suite_json = config.data_dir / "generated_prompt_suite.json"
    suite_md = config.data_dir / "generated_prompt_suite.md"
    summary_json = reports_dir / "generated_prompt_suite_summary.json"
    summary_md = reports_dir / "generated_prompt_suite_summary.md"

    suite_json.write_text(json.dumps(redact_secrets(suite), indent=2, sort_keys=True, default=str), encoding="utf-8")
    suite_md.write_text(_render_suite_markdown(suite, summary), encoding="utf-8")
    summary_json.write_text(json.dumps(redact_secrets(summary), indent=2, sort_keys=True, default=str), encoding="utf-8")
    summary_md.write_text(_render_summary_markdown(summary), encoding="utf-8")
    return {"suite": suite, "summary": summary}


def _load_source_examples(config: Config) -> list[dict[str, Any]]:
    payload = json.loads(config.data_json_path.read_text(encoding="utf-8"))
    raw_examples = find_example_list(payload)
    sources: list[dict[str, Any]] = []
    for index, item in enumerate(raw_examples, start=1):
        if not isinstance(item, dict):
            continue
        prompt = str(item.get("question") or item.get("query") or item.get("input") or item.get("nl_query") or "").strip()
        if not prompt:
            continue
        source_id = str(item.get("id") or item.get("query_id") or f"example_{index:03d}")
        gold_sql = item.get("gold_sql") or item.get("sql") or item.get("expected_sql") or ""
        gold_api = item.get("gold_api") or item.get("api") or item.get("api_calls") or item.get("tool_calls")
        tables = _extract_tables(gold_sql)
        api_hints = _extract_api_hints(gold_api)
        family = _infer_domain_family(prompt, tables, api_hints)
        intent = _infer_intent(prompt)
        sources.append(
            {
                "source_id": source_id,
                "source_index": index,
                "prompt": prompt,
                "answer": str(item.get("answer") or item.get("gold_answer") or item.get("expected_answer") or ""),
                "gold_sql": str(gold_sql or ""),
                "gold_api": gold_api,
                "tables": tables,
                "api_hints": api_hints,
                "domain_family": family,
                "intent": intent,
                "route": _infer_route(tables, api_hints),
                "answer_only_numbers": _answer_only_numbers(prompt, str(item.get("answer") or "")),
            }
        )
    return sources


def _build_suite(source_examples: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_prompt_norms = {_norm(src["prompt"]) for src in source_examples}
    source_by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for source in source_examples:
        source_by_family[source["domain_family"]].append(source)

    suite: list[dict[str, Any]] = []
    seen_norms: set[str] = set()
    rejected = Counter()

    def add(
        prompt: str,
        *,
        generation_type: str,
        source_ids: list[str] | None = None,
        source_prompt: str = "",
        route: str = "UNKNOWN",
        intent: str = "UNKNOWN",
        domain: str = "unknown",
        tables: list[str] | None = None,
        apis: list[str] | None = None,
        difficulty: str = "medium",
        notes: str = "Diagnostic label only; not used by runtime.",
    ) -> bool:
        normalized = _norm(prompt)
        if not prompt.strip() or normalized in seen_norms:
            rejected["duplicate"] += 1
            return False
        if normalized in source_prompt_norms:
            rejected["exact_source_copy"] += 1
            return False
        if _prompt_leaks_answer(prompt, source_examples, source_ids=source_ids or []):
            rejected["answer_leak_guard"] += 1
            return False
        if generation_type not in GENERATION_TYPES:
            raise ValueError(f"Unknown generation_type {generation_type}")
        if route not in ROUTES:
            route = "UNKNOWN"
        if intent not in INTENTS:
            intent = "UNKNOWN"
        if domain not in DOMAINS:
            domain = "unknown"
        seen_norms.add(normalized)
        suite.append(
            {
                "prompt_id": f"gen_{len(suite) + 1:04d}",
                "prompt": prompt.strip(),
                "generation_type": generation_type,
                "source_query_ids": list(source_ids or []),
                "source_prompt": source_prompt,
                "expected_route_diagnostic": route,
                "expected_answer_intent_diagnostic": intent,
                "domain_family": domain,
                "target_tables_hint": list(tables or []),
                "target_api_hint": list(apis or []),
                "difficulty": difficulty,
                "should_be_scored": False,
                "diagnostic_only": True,
                "notes": notes,
            }
        )
        return True

    for source in source_examples:
        for prompt in _paraphrases_for_source(source):
            add(
                prompt,
                generation_type="paraphrase",
                source_ids=[source["source_id"]],
                source_prompt=source["prompt"],
                route=source["route"],
                intent=source["intent"],
                domain=source["domain_family"],
                tables=source["tables"],
                apis=source["api_hints"],
                difficulty="easy",
                notes="Semantic paraphrase for diagnostic coverage only; not official scoring data.",
            )

    for item in _domain_coverage_prompts(source_by_family):
        add(**item)

    for item in _edge_case_prompts(source_by_family):
        add(**item)

    if len(suite) < 250:
        for item in _filler_prompts(source_by_family):
            add(**item)
            if len(suite) >= 250:
                break

    return suite, {"rejected": dict(rejected), "source_prompt_norms": len(source_prompt_norms)}


def _paraphrases_for_source(source: dict[str, Any]) -> list[str]:
    prompt = source["prompt"].strip().rstrip("?")
    lower = prompt[:1].lower() + prompt[1:]
    family = source["domain_family"]
    intent = source["intent"]
    prompts = [
        f"Can you please {lower}?",
        f"Using the available DASHSys evidence, {lower}.",
        f"I need a {intent.lower().replace('_', ' ')} answer for this {family.replace('_', ' ')} question: {prompt}.",
    ]
    if intent == "COUNT":
        prompts[2] = f"Give me the count for this {family.replace('_', ' ')} request: {prompt}."
    elif intent == "LIST":
        prompts[2] = f"Return the matching {family.replace('_', ' ')} records for: {prompt}."
    elif intent == "DATE":
        prompts[2] = f"Find the relevant date or timestamp for: {prompt}."
    elif intent == "STATUS":
        prompts[2] = f"Check the status evidence for: {prompt}."
    return prompts


def _domain_coverage_prompts(source_by_family: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    base: dict[str, list[tuple[str, str, str, list[str], list[str], str]]] = {
        "journey_campaign": [
            ("List journeys with their IDs and current state.", "LIST", "SQL_PLUS_API", ["dim_campaign"], ["GET /ajo/journey"], "easy"),
            ("Which journeys look inactive in the local snapshot?", "STATUS", "SQL_PLUS_API", ["dim_campaign"], ["GET /ajo/journey"], "medium"),
            ("Show journeys sorted by most recently updated time.", "LIST", "SQL_PLUS_API", ["dim_campaign"], ["GET /ajo/journey"], "medium"),
            ("Find a journey by name and show its campaign ID.", "ID_LOOKUP", "SQL_PLUS_API", ["dim_campaign"], ["GET /ajo/journey"], "medium"),
            ("Which journeys have a published timestamp available?", "DATE", "SQL_PLUS_API", ["dim_campaign"], ["GET /ajo/journey"], "medium"),
            ("Give me a journey status summary by state.", "SUMMARY", "SQL_PLUS_API", ["dim_campaign"], ["GET /ajo/journey"], "hard"),
            ("List journey names without applying a row limit.", "LIST", "SQL_ONLY", ["dim_campaign"], [], "medium"),
            ("Check whether any campaigns are live or stopped.", "STATUS", "SQL_PLUS_API", ["dim_campaign"], ["GET /ajo/journey"], "medium"),
            ("Show campaign records that were updated recently.", "DATE", "SQL_PLUS_API", ["dim_campaign"], ["GET /ajo/journey"], "medium"),
            ("Give journey names and campaign IDs for available campaigns.", "LIST", "SQL_ONLY", ["dim_campaign"], [], "easy"),
            ("Which campaign record matches a journey name?", "ID_LOOKUP", "SQL_ONLY", ["dim_campaign"], [], "medium"),
            ("Summarize journey publication evidence from SQL and API dry-run status.", "SUMMARY", "SQL_PLUS_API", ["dim_campaign"], ["GET /ajo/journey"], "hard"),
        ],
        "schema_dataset": [
            ("Count my schema blueprints.", "COUNT", "SQL_ONLY", ["dim_blueprint"], ["GET /data/foundation/schemaregistry/tenant/schemas"], "easy"),
            ("List schema blueprint IDs and names.", "LIST", "SQL_ONLY", ["dim_blueprint"], [], "easy"),
            ("Which datasets are linked to schema blueprints?", "RELATIONSHIP", "SQL_PLUS_API", ["dim_blueprint", "dim_collection"], ["GET /catalog/dataSets"], "hard"),
            ("Show collections associated with each blueprint.", "LIST", "SQL_ONLY", ["dim_blueprint", "dim_collection"], [], "medium"),
            ("How many distinct blueprint IDs are in the snapshot?", "COUNT", "SQL_ONLY", ["dim_blueprint"], [], "easy"),
            ("Find schema records that have related collection metadata.", "RELATIONSHIP", "SQL_ONLY", ["dim_blueprint", "dim_collection"], [], "medium"),
            ("List schema names with their primary identifier columns if available.", "LIST", "SQL_ONLY", ["dim_blueprint"], [], "medium"),
            ("Check whether a schema has a matching dataset entry.", "BOOLEAN", "SQL_PLUS_API", ["dim_blueprint", "dim_collection"], ["GET /catalog/dataSets"], "hard"),
            ("Give a schema count and show the table used for the count.", "COUNT", "SQL_ONLY", ["dim_blueprint"], [], "medium"),
            ("Show blueprint records without relying on live API payloads.", "LIST", "SQL_ONLY", ["dim_blueprint"], [], "easy"),
            ("Which collection records share a blueprint identifier?", "RELATIONSHIP", "SQL_ONLY", ["dim_collection", "dim_blueprint"], [], "hard"),
            ("Summarize schema and collection relationship coverage.", "SUMMARY", "SQL_ONLY", ["dim_blueprint", "dim_collection"], [], "hard"),
        ],
        "segment_audience": [
            ("List segment audiences with IDs and names.", "LIST", "SQL_PLUS_API", ["dim_segment"], ["GET /data/core/ups/audiences"], "easy"),
            ("Which audiences are connected to a destination?", "RELATIONSHIP", "SQL_PLUS_API", ["dim_segment", "dim_target"], ["GET /data/core/ups/audiences"], "hard"),
            ("Show audience total profile counts where available.", "COUNT", "SQL_PLUS_API", ["dim_segment"], ["GET /data/core/ups/audiences"], "medium"),
            ("Find an audience by segment name.", "ID_LOOKUP", "SQL_PLUS_API", ["dim_segment"], ["GET /data/core/ups/audiences"], "medium"),
            ("List segment definitions that map to audiences.", "LIST", "API_ONLY", ["dim_segment"], ["GET /data/core/ups/segment/definitions"], "hard"),
            ("Which audiences were created or updated recently?", "DATE", "SQL_PLUS_API", ["dim_segment"], ["GET /data/core/ups/audiences"], "medium"),
            ("Show audience and destination relationship details.", "RELATIONSHIP", "SQL_PLUS_API", ["dim_segment", "dim_target"], ["GET /data/foundation/flowservice/flows"], "hard"),
            ("Count distinct audiences in the local snapshot.", "COUNT", "SQL_ONLY", ["dim_segment"], [], "easy"),
            ("Give me audience IDs for matching segment records.", "ID_LOOKUP", "SQL_ONLY", ["dim_segment"], [], "medium"),
            ("Summarize segment audience evidence and API dry-run status.", "SUMMARY", "SQL_PLUS_API", ["dim_segment"], ["GET /data/core/ups/audiences"], "hard"),
        ],
        "destination_flow": [
            ("List destinations and their flow IDs.", "LIST", "SQL_PLUS_API", ["dim_target"], ["GET /data/foundation/flowservice/flows"], "medium"),
            ("Which destination flows are disabled or inactive?", "STATUS", "SQL_PLUS_API", ["dim_target"], ["GET /data/foundation/flowservice/flows"], "medium"),
            ("Show flows by state for destinations.", "SUMMARY", "SQL_PLUS_API", ["dim_target"], ["GET /data/foundation/flowservice/flows"], "hard"),
            ("Find destination metadata for a named target.", "ID_LOOKUP", "SQL_PLUS_API", ["dim_target"], ["GET /data/foundation/flowservice/flows"], "medium"),
            ("List recently modified destination flows.", "DATE", "SQL_PLUS_API", ["dim_target"], ["GET /data/foundation/flowservice/flows"], "medium"),
            ("Distinguish source flows from destination flows.", "COMPARISON", "SQL_PLUS_API", ["dim_target", "dim_connector"], ["GET /data/foundation/flowservice/flows"], "hard"),
            ("Count destination flow records in the local snapshot.", "COUNT", "SQL_ONLY", ["dim_target"], [], "easy"),
            ("Show destination IDs that have associated audience records.", "RELATIONSHIP", "SQL_PLUS_API", ["dim_target", "dim_segment"], ["GET /data/core/ups/audiences"], "hard"),
            ("Which targets have flowservice records available?", "BOOLEAN", "SQL_PLUS_API", ["dim_target"], ["GET /data/foundation/flowservice/flows"], "medium"),
            ("Summarize destination flow evidence from SQL and API checks.", "SUMMARY", "SQL_PLUS_API", ["dim_target"], ["GET /data/foundation/flowservice/flows"], "hard"),
        ],
        "dataflow_run": [
            ("Show failed dataflow runs.", "LIST", "SQL_PLUS_API", ["dim_connector"], ["GET /data/foundation/flowservice/runs"], "medium"),
            ("Count failed flow runs in the available evidence.", "COUNT", "SQL_PLUS_API", ["dim_connector"], ["GET /data/foundation/flowservice/runs"], "medium"),
            ("List flow run IDs sorted by update time.", "LIST", "SQL_PLUS_API", ["dim_connector"], ["GET /data/foundation/flowservice/runs"], "hard"),
            ("Which dataflow runs are currently in a failed state?", "STATUS", "SQL_PLUS_API", ["dim_connector"], ["GET /data/foundation/flowservice/runs"], "medium"),
            ("Find source flow runs connected to loyalty data.", "RELATIONSHIP", "SQL_PLUS_API", ["dim_connector"], ["GET /data/foundation/flowservice/runs"], "hard"),
            ("Show recent run failures if the local snapshot contains them.", "DATE", "SQL_PLUS_API", ["dim_connector"], ["GET /data/foundation/flowservice/runs"], "medium"),
            ("Report whether flow run API verification is dry-run only.", "SUMMARY", "API_ONLY", [], ["GET /data/foundation/flowservice/runs"], "medium"),
        ],
        "merge_policy": [
            ("List merge policies.", "LIST", "API_ONLY", [], ["GET /data/core/ups/config/mergePolicies"], "easy"),
            ("How many merge policies are configured?", "COUNT", "API_ONLY", [], ["GET /data/core/ups/config/mergePolicies"], "easy"),
            ("Which merge policy is marked as default?", "STATUS", "API_ONLY", [], ["GET /data/core/ups/config/mergePolicies"], "medium"),
            ("Show merge policy IDs and names.", "LIST", "API_ONLY", [], ["GET /data/core/ups/config/mergePolicies"], "medium"),
            ("Verify merge policy details using the platform API.", "SUMMARY", "API_ONLY", [], ["GET /data/core/ups/config/mergePolicies"], "medium"),
            ("Can the system answer merge policy status without live API credentials?", "BOOLEAN", "API_ONLY", [], ["GET /data/core/ups/config/mergePolicies"], "hard"),
            ("Summarize available merge policy evidence and dry-run limits.", "SUMMARY", "API_ONLY", [], ["GET /data/core/ups/config/mergePolicies"], "hard"),
        ],
        "tags": [
            ("List available tags.", "LIST", "API_ONLY", [], ["GET /tags"], "easy"),
            ("Count tagged resources if tag evidence is available.", "COUNT", "API_ONLY", [], ["GET /tags"], "medium"),
            ("Which objects are associated with a specific tag?", "RELATIONSHIP", "API_ONLY", [], ["GET /tags"], "hard"),
            ("Show tag names and identifiers.", "ID_LOOKUP", "API_ONLY", [], ["GET /tags"], "medium"),
            ("Check whether tag answers require live API evidence.", "BOOLEAN", "API_ONLY", [], ["GET /tags"], "medium"),
            ("Summarize tag evidence and dry-run API limitations.", "SUMMARY", "API_ONLY", [], ["GET /tags"], "hard"),
            ("Find resources that use a label-style tag.", "LIST", "API_ONLY", [], ["GET /tags"], "hard"),
        ],
        "batch": [
            ("Show recent batches and their statuses.", "STATUS", "API_ONLY", [], ["GET /catalog/batches"], "medium"),
            ("List failed batches.", "LIST", "API_ONLY", [], ["GET /catalog/batches"], "medium"),
            ("Count successful batch records if available.", "COUNT", "API_ONLY", [], ["GET /catalog/batches"], "medium"),
            ("Which batch files failed export?", "LIST", "API_ONLY", [], ["GET /export/batches/{batch_id}/failed"], "hard"),
            ("Show batch IDs sorted by recent activity.", "LIST", "API_ONLY", [], ["GET /catalog/batches"], "hard"),
            ("Verify batch status through the API when credentials are present.", "STATUS", "API_ONLY", [], ["GET /catalog/batches"], "medium"),
            ("Summarize batch evidence and dry-run status.", "SUMMARY", "API_ONLY", [], ["GET /catalog/batches"], "hard"),
        ],
        "observability": [
            ("Show observability metrics available for ingestion.", "SUMMARY", "API_ONLY", [], ["GET /observability/insights/metrics"], "hard"),
            ("Count ingestion records reported by observability evidence.", "COUNT", "API_ONLY", [], ["GET /observability/insights/metrics"], "hard"),
            ("Compare ingestion records and batch success counts.", "COMPARISON", "API_ONLY", [], ["GET /observability/insights/metrics"], "hard"),
            ("Which observability metrics are unavailable in dry-run mode?", "SUMMARY", "API_ONLY", [], ["GET /observability/insights/metrics"], "medium"),
            ("Show failed ingestion indicators if the API can verify them.", "STATUS", "API_ONLY", [], ["GET /observability/insights/metrics"], "hard"),
            ("Summarize dry-run limitations for observability questions.", "SUMMARY", "API_ONLY", [], ["GET /observability/insights/metrics"], "hard"),
            ("List metric names needed for ingestion health checks.", "LIST", "API_ONLY", [], ["GET /observability/insights/metrics"], "medium"),
        ],
    }
    target_counts = {
        "journey_campaign": 12,
        "schema_dataset": 12,
        "segment_audience": 10,
        "destination_flow": 10,
        "dataflow_run": 9,
        "merge_policy": 9,
        "tags": 8,
        "batch": 10,
        "observability": 10,
    }
    prompts: list[dict[str, Any]] = []
    for domain, count in target_counts.items():
        options = base[domain]
        for prompt, intent, route, tables, apis, difficulty in options[:count]:
            source = (source_by_family.get(domain) or [{}])[0]
            prompts.append(
                {
                    "prompt": prompt,
                    "generation_type": "domain_coverage",
                    "source_ids": [source.get("source_id")] if source.get("source_id") else [],
                    "source_prompt": source.get("prompt", ""),
                    "route": route,
                    "intent": intent if intent in INTENTS else "SUMMARY",
                    "domain": domain,
                    "tables": tables,
                    "apis": apis,
                    "difficulty": difficulty,
                    "notes": "Domain coverage prompt; diagnostic-only label derived from source schema/API families.",
                }
            )
    return prompts


def _edge_case_prompts(source_by_family: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    raw = [
        ("schemmas count", "edge_case", "SQL_ONLY", "COUNT", "schema_dataset", ["dim_blueprint"], [], "easy"),
        ("datsets linked to schema blueprints please", "edge_case", "SQL_PLUS_API", "RELATIONSHIP", "schema_dataset", ["dim_blueprint", "dim_collection"], ["GET /catalog/dataSets"], "medium"),
        ("destnations with broken flows", "edge_case", "SQL_PLUS_API", "STATUS", "destination_flow", ["dim_target"], ["GET /data/foundation/flowservice/flows"], "medium"),
        ("schemas?", "hidden_style", "SQL_ONLY", "COUNT", "schema_dataset", ["dim_blueprint"], [], "easy"),
        ("anything inactive?", "hidden_style", "SQL_PLUS_API", "STATUS", "journey_campaign", ["dim_campaign"], ["GET /ajo/journey"], "hard"),
        ("show latest broken things", "hidden_style", "UNKNOWN", "SUMMARY", "unknown", [], [], "hard"),
        ("count and list IDs for schema records", "edge_case", "SQL_ONLY", "COUNT", "schema_dataset", ["dim_blueprint"], [], "hard"),
        ("show destinations, no row cap", "edge_case", "SQL_PLUS_API", "LIST", "destination_flow", ["dim_target"], ["GET /data/foundation/flowservice/flows"], "medium"),
        ("verify live platform status for merge policies", "dry_run_api", "API_ONLY", "STATUS", "merge_policy", [], ["GET /data/core/ups/config/mergePolicies"], "medium"),
        ("check platform API for tags, but don't invent missing payloads", "dry_run_api", "API_ONLY", "SUMMARY", "tags", [], ["GET /tags"], "medium"),
        ("what changed recently across journeys?", "hidden_style", "SQL_PLUS_API", "DATE", "journey_campaign", ["dim_campaign"], ["GET /ajo/journey"], "hard"),
        ("which data objects are connected?", "hidden_style", "UNKNOWN", "RELATIONSHIP", "unknown", [], [], "hard"),
        ("audiences vs segments: list matching records", "edge_case", "SQL_PLUS_API", "LIST", "segment_audience", ["dim_segment"], ["GET /data/core/ups/audiences"], "medium"),
        ("targets with audiences attached", "edge_case", "SQL_PLUS_API", "RELATIONSHIP", "destination_flow", ["dim_target", "dim_segment"], ["GET /data/core/ups/audiences"], "hard"),
        ("blueprints aka schemas total", "edge_case", "SQL_ONLY", "COUNT", "schema_dataset", ["dim_blueprint"], [], "easy"),
        ("campaigns aka journeys by state", "edge_case", "SQL_PLUS_API", "STATUS", "journey_campaign", ["dim_campaign"], ["GET /ajo/journey"], "medium"),
        ("segments aka audiences with profile counts", "edge_case", "SQL_PLUS_API", "COUNT", "segment_audience", ["dim_segment"], ["GET /data/core/ups/audiences"], "medium"),
        ("targets aka destinations sorted by update time", "edge_case", "SQL_PLUS_API", "DATE", "destination_flow", ["dim_target"], ["GET /data/foundation/flowservice/flows"], "medium"),
        ("find zero-result failed batch cases if any", "edge_case", "API_ONLY", "LIST", "batch", [], ["GET /catalog/batches"], "hard"),
        ("show no-limit journey listing", "edge_case", "SQL_ONLY", "LIST", "journey_campaign", ["dim_campaign"], [], "medium"),
        ("status pls for flow runs", "hidden_style", "SQL_PLUS_API", "STATUS", "dataflow_run", ["dim_connector"], ["GET /data/foundation/flowservice/runs"], "medium"),
        ("how many labels do I have?", "edge_case", "API_ONLY", "COUNT", "tags", [], ["GET /tags"], "medium"),
        ("are there default merge policies?", "edge_case", "API_ONLY", "BOOLEAN", "merge_policy", [], ["GET /data/core/ups/config/mergePolicies"], "medium"),
        ("recent batch health summary", "answer_quality", "API_ONLY", "SUMMARY", "batch", [], ["GET /catalog/batches"], "hard"),
        ("observability: ingestion health without live creds", "dry_run_api", "API_ONLY", "SUMMARY", "observability", [], ["GET /observability/insights/metrics"], "hard"),
        ("give me ids and names, not prose, for journeys", "answer_quality", "SQL_ONLY", "LIST", "journey_campaign", ["dim_campaign"], [], "medium"),
        ("one sentence schema count answer", "answer_quality", "SQL_ONLY", "COUNT", "schema_dataset", ["dim_blueprint"], [], "easy"),
        ("show API dry-run caveat for live audience check", "dry_run_api", "SQL_PLUS_API", "SUMMARY", "segment_audience", ["dim_segment"], ["GET /data/core/ups/audiences"], "medium"),
        ("list collections with blueprint links", "edge_case", "SQL_ONLY", "RELATIONSHIP", "schema_dataset", ["dim_collection", "dim_blueprint"], [], "medium"),
        ("what destination is SMS Opt-In connected to?", "edge_case", "SQL_PLUS_API", "ID_LOOKUP", "destination_flow", ["dim_target"], ["GET /data/foundation/flowservice/flows"], "medium"),
        ("campaign id for Birthday Message", "edge_case", "SQL_PLUS_API", "ID_LOOKUP", "journey_campaign", ["dim_campaign"], ["GET /ajo/journey"], "easy"),
        ("published time for Gold Tier Welcome Email", "edge_case", "SQL_PLUS_API", "DATE", "journey_campaign", ["dim_campaign"], ["GET /ajo/journey"], "medium"),
        ("all datasets for hkg_adls_profile_count_history", "edge_case", "SQL_PLUS_API", "LIST", "schema_dataset", ["dim_collection"], ["GET /catalog/dataSets"], "medium"),
        ("audience details for Person: Birthday Today 001", "edge_case", "SQL_PLUS_API", "SUMMARY", "segment_audience", ["dim_segment"], ["GET /data/core/ups/audiences"], "medium"),
        ("does weRetail: Customer Actions have related flows?", "edge_case", "SQL_PLUS_API", "BOOLEAN", "destination_flow", ["dim_target"], ["GET /data/foundation/flowservice/flows"], "hard"),
        ("tag named cool: what objects use it?", "edge_case", "API_ONLY", "RELATIONSHIP", "tags", [], ["GET /tags"], "hard"),
        ("schema _xdm.context.profile details", "edge_case", "SQL_PLUS_API", "SUMMARY", "schema_dataset", ["dim_blueprint"], ["GET /data/foundation/schemaregistry/tenant/schemas"], "medium"),
        ("show failed export files for a batch if evidence exists", "dry_run_api", "API_ONLY", "LIST", "batch", [], ["GET /export/batches/{batch_id}/failed"], "hard"),
        ("count, then list IDs for audiences", "answer_quality", "SQL_PLUS_API", "COUNT", "segment_audience", ["dim_segment"], ["GET /data/core/ups/audiences"], "hard"),
        ("sort flows newest first", "edge_case", "SQL_PLUS_API", "LIST", "destination_flow", ["dim_target"], ["GET /data/foundation/flowservice/flows"], "medium"),
        ("inactive journeys please, concise", "answer_quality", "SQL_PLUS_API", "STATUS", "journey_campaign", ["dim_campaign"], ["GET /ajo/journey"], "easy"),
        ("failed runs, include IDs only if supported", "answer_quality", "SQL_PLUS_API", "LIST", "dataflow_run", ["dim_connector"], ["GET /data/foundation/flowservice/runs"], "medium"),
        ("merge policy default? use API evidence only", "dry_run_api", "API_ONLY", "BOOLEAN", "merge_policy", [], ["GET /data/core/ups/config/mergePolicies"], "medium"),
        ("show local schema evidence and skip live claims", "answer_quality", "SQL_ONLY", "SUMMARY", "schema_dataset", ["dim_blueprint"], [], "medium"),
        ("ambiguous object connections across schemas and destinations", "hidden_style", "UNKNOWN", "RELATIONSHIP", "unknown", [], [], "hard"),
        ("latest data objects changed", "hidden_style", "UNKNOWN", "DATE", "unknown", [], [], "hard"),
        ("journey list with no invented API payload", "dry_run_api", "SQL_PLUS_API", "LIST", "journey_campaign", ["dim_campaign"], ["GET /ajo/journey"], "medium"),
        ("schema count from local snapshot only", "answer_quality", "SQL_ONLY", "COUNT", "schema_dataset", ["dim_blueprint"], [], "easy"),
        ("are any destinations failed?", "edge_case", "SQL_PLUS_API", "BOOLEAN", "destination_flow", ["dim_target"], ["GET /data/foundation/flowservice/flows"], "medium"),
        ("batches failed lately?", "hidden_style", "API_ONLY", "STATUS", "batch", [], ["GET /catalog/batches"], "medium"),
        ("show profile audience names and totals", "edge_case", "SQL_PLUS_API", "LIST", "segment_audience", ["dim_segment"], ["GET /data/core/ups/audiences"], "medium"),
        ("datasets using blueprints, summarize relationships", "answer_quality", "SQL_PLUS_API", "SUMMARY", "schema_dataset", ["dim_blueprint", "dim_collection"], ["GET /catalog/dataSets"], "hard"),
        ("labels and tags summary", "hidden_style", "API_ONLY", "SUMMARY", "tags", [], ["GET /tags"], "medium"),
        ("observability metric names please", "edge_case", "API_ONLY", "LIST", "observability", [], ["GET /observability/insights/metrics"], "medium"),
        ("if API is dry-run, say what SQL can still prove", "dry_run_api", "SQL_PLUS_API", "SUMMARY", "unknown", [], [], "hard"),
    ]
    prompts: list[dict[str, Any]] = []
    for prompt, gen_type, route, intent, domain, tables, apis, difficulty in raw:
        source = (source_by_family.get(domain) or [{}])[0]
        prompts.append(
            {
                "prompt": prompt,
                "generation_type": gen_type,
                "source_ids": [source.get("source_id")] if source.get("source_id") else [],
                "source_prompt": source.get("prompt", ""),
                "route": route,
                "intent": intent if intent in INTENTS else "SUMMARY",
                "domain": domain,
                "tables": tables,
                "apis": apis,
                "difficulty": difficulty,
                "notes": "Robustness or answer-quality diagnostic; not official scoring data.",
            }
        )
    return prompts


def _filler_prompts(source_by_family: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    domains = [domain for domain in DOMAINS if domain != "unknown"]
    prompts: list[dict[str, Any]] = []
    for domain in sorted(domains):
        source = (source_by_family.get(domain) or [{}])[0]
        for suffix in ["summary", "IDs", "status", "dry-run note", "local evidence"]:
            prompts.append(
                {
                    "prompt": f"Diagnostic {domain.replace('_', ' ')} {suffix} check.",
                    "generation_type": "domain_coverage",
                    "source_ids": [source.get("source_id")] if source.get("source_id") else [],
                    "source_prompt": source.get("prompt", ""),
                    "route": source.get("route", "UNKNOWN"),
                    "intent": source.get("intent", "SUMMARY"),
                    "domain": domain,
                    "tables": source.get("tables", []),
                    "apis": source.get("api_hints", []),
                    "difficulty": "medium",
                    "notes": "Fallback deterministic coverage prompt; diagnostic-only.",
                }
            )
    return prompts


def _build_summary(source_examples: list[dict[str, Any]], suite: list[dict[str, Any]], diagnostics: dict[str, Any]) -> dict[str, Any]:
    source_norms = {_norm(src["prompt"]) for src in source_examples}
    prompt_norms = [_norm(item["prompt"]) for item in suite]
    exact_copies = sum(1 for norm in prompt_norms if norm in source_norms)
    duplicates = len(prompt_norms) - len(set(prompt_norms))
    summary = {
        "report_type": "generated_prompt_suite_summary",
        "diagnostic_only": True,
        "not_official_score": True,
        "suite_path": "data/generated_prompt_suite.json",
        "suite_markdown_path": "data/generated_prompt_suite.md",
        "total_generated_prompts": len(suite),
        "source_examples_count": len(source_examples),
        "source_id_policy": "If data/data.json entries lack IDs, stable IDs are assigned by order: example_001, example_002, ...",
        "source_id_mapping": [
            {"source_index": src["source_index"], "source_query_id": src["source_id"], "source_prompt": src["prompt"]}
            for src in source_examples
        ],
        "counts": {
            "generation_type": dict(Counter(item["generation_type"] for item in suite)),
            "domain_family": dict(Counter(item["domain_family"] for item in suite)),
            "answer_intent": dict(Counter(item["expected_answer_intent_diagnostic"] for item in suite)),
            "route": dict(Counter(item["expected_route_diagnostic"] for item in suite)),
            "difficulty": dict(Counter(item["difficulty"] for item in suite)),
        },
        "duplicate_count": duplicates,
        "exact_copy_count_against_original_examples": exact_copies,
        "rejected_generation_candidates": diagnostics.get("rejected", {}),
        "coverage_gaps_still_remaining": _coverage_gaps(suite),
        "safety_notes": [
            "Generated prompts are diagnostic coverage only and should_be_scored=false.",
            "Generated labels are not runtime hints and are not official gold labels.",
            "Prompts are generated from source query structure, schema/API hints, and intent/domain patterns without embedding gold answers.",
        ],
    }
    return summary


def _render_suite_markdown(suite: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    lines = [
        "# Generated Diagnostic Prompt Suite",
        "",
        "Diagnostic prompt coverage only; not official strict score.",
        "",
        f"- Total prompts: `{summary['total_generated_prompts']}`",
        f"- Source examples: `{summary['source_examples_count']}`",
        "- Runtime behavior: generated prompts are not used by the packaged system.",
        "",
        "## Sample Prompts",
        "",
    ]
    for item in suite[:40]:
        lines.append(
            f"- `{item['prompt_id']}` [{item['generation_type']}/{item['domain_family']}/{item['expected_answer_intent_diagnostic']}]: {item['prompt']}"
        )
    if len(suite) > 40:
        lines.append(f"- ... {len(suite) - 40} more prompts in `data/generated_prompt_suite.json`")
    return "\n".join(lines) + "\n"


def _render_summary_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Generated Prompt Suite Summary",
        "",
        "Diagnostic prompt coverage only; not official strict score.",
        "",
        f"- Total generated prompts: `{summary['total_generated_prompts']}`",
        f"- Source examples count: `{summary['source_examples_count']}`",
        f"- Duplicate count: `{summary['duplicate_count']}`",
        f"- Exact-copy count against original examples: `{summary['exact_copy_count_against_original_examples']}`",
        f"- Suite path: `{summary['suite_path']}`",
        "",
        "## Counts",
        "",
    ]
    for group, counts in summary["counts"].items():
        lines.append(f"### {group}")
        for key, value in sorted(counts.items()):
            lines.append(f"- `{key}`: `{value}`")
        lines.append("")
    lines.extend(["## Coverage Gaps", ""])
    lines.extend(f"- {gap}" for gap in summary["coverage_gaps_still_remaining"])
    lines.append("")
    return "\n".join(lines)


def _extract_tables(sql: Any) -> list[str]:
    if isinstance(sql, list):
        sql = " ".join(str(part) for part in sql)
    text = str(sql or "")
    tables = []
    for match in re.finditer(r'(?i)\b(?:from|join)\s+"?([A-Za-z_][A-Za-z0-9_]*)"?', text):
        table = match.group(1).lower()
        if table not in tables:
            tables.append(table)
    return tables


def _extract_api_hints(value: Any) -> list[str]:
    hints: list[str] = []

    def visit(item: Any) -> None:
        if isinstance(item, dict):
            method = str(item.get("method") or "GET").upper()
            url = item.get("url") or item.get("path") or item.get("endpoint")
            if url:
                hints.append(_api_hint(method, str(url)))
            for child in item.values():
                visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)
        elif isinstance(item, str):
            text = item.strip()
            match = re.match(r"^(GET|POST|PUT|PATCH|DELETE)\s+(.+)$", text, flags=re.I)
            if match:
                hints.append(_api_hint(match.group(1).upper(), match.group(2)))
            elif text.startswith("http"):
                hints.append(_api_hint("GET", text))

    visit(value)
    result = []
    for hint in hints:
        if hint not in result:
            result.append(hint)
    return result


def _api_hint(method: str, url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path if parsed.scheme else url.split("?", 1)[0]
    path = path or "/"
    return f"{method} {path}"


def _infer_domain_family(prompt: str, tables: list[str], apis: list[str]) -> str:
    text = " ".join([prompt, " ".join(tables), " ".join(apis)]).lower()
    if any(word in text for word in ["journey", "campaign", "ajo"]):
        return "journey_campaign"
    if any(word in text for word in ["schema", "schemas", "blueprint", "collection", "dataset", "catalog/datasets", "schemaregistry"]):
        return "schema_dataset"
    if any(word in text for word in ["segment", "audience", "totalprofile", "ups/audience"]):
        return "segment_audience"
    if any(word in text for word in ["dataflow run", "flow run", "/runs", "failed dataflow"]):
        return "dataflow_run"
    if any(word in text for word in ["destination", "target", "flowservice/flows", "dim_target"]):
        return "destination_flow"
    if "merge" in text:
        return "merge_policy"
    if "tag" in text or "label" in text:
        return "tags"
    if "batch" in text:
        return "batch"
    if "observability" in text or "metric" in text or "ingestion" in text:
        return "observability"
    return "unknown"


def _infer_intent(prompt: str) -> str:
    text = prompt.lower()
    if re.search(r"\b(how many|count|number of|total)\b", text):
        return "COUNT"
    if re.search(r"\b(when|date|created|updated|published|recent|latest)\b", text):
        return "DATE"
    if re.search(r"\b(status|state|inactive|active|failed|published|enabled|disabled|success)\b", text):
        return "STATUS"
    if re.search(r"\b(is|are|does|do|has|have|whether)\b", text):
        return "BOOLEAN"
    if re.search(r"\b(id|ids|identifier)\b", text):
        return "ID_LOOKUP"
    if re.search(r"\b(compare|vs|versus|difference)\b", text):
        return "COMPARISON"
    if re.search(r"\b(list|show|give|which|what)\b", text):
        return "LIST"
    if re.search(r"\b(summarize|summary|details)\b", text):
        return "SUMMARY"
    return "UNKNOWN"


def _infer_route(tables: list[str], apis: list[str]) -> str:
    if tables and apis:
        return "SQL_PLUS_API"
    if tables:
        return "SQL_ONLY"
    if apis:
        return "API_ONLY"
    return "UNKNOWN"


def _answer_only_numbers(prompt: str, answer: str) -> set[str]:
    prompt_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", prompt))
    answer_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", answer))
    return answer_numbers - prompt_numbers


def _prompt_leaks_answer(prompt: str, sources: list[dict[str, Any]], *, source_ids: list[str] | None = None) -> bool:
    normalized = _norm(prompt)
    source_id_set = set(source_ids or [])
    for source in sources:
        answer = _norm(source.get("answer", ""))
        if answer and len(answer) > 20 and answer in normalized:
            return True
        if not source_id_set or source.get("source_id") not in source_id_set:
            continue
        for number in source.get("answer_only_numbers", set()):
            if re.search(rf"\b{re.escape(number)}\b", prompt):
                return True
    return False


def _coverage_gaps(suite: list[dict[str, Any]]) -> list[str]:
    gaps = []
    domain_counts = Counter(item["domain_family"] for item in suite)
    intent_counts = Counter(item["expected_answer_intent_diagnostic"] for item in suite)
    for domain in sorted(DOMAINS - {"unknown"}):
        if domain_counts[domain] == 0:
            gaps.append(f"No generated prompts for domain family {domain}.")
    for intent in sorted(INTENTS - {"UNKNOWN"}):
        if intent_counts[intent] == 0:
            gaps.append(f"No generated prompts for answer intent {intent}.")
    if not gaps:
        gaps.append("No major enum-level coverage gaps detected; manual semantic review is still recommended.")
    return gaps


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text.lower())).strip()


if __name__ == "__main__":
    raise SystemExit(main())
