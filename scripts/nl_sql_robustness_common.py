from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.db import DuckDBDatabase
from dashagent.endpoint_catalog import EndpointCatalog
from dashagent.eval_harness import EvalExample, EvalHarness
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


VARIANT_KINDS = [
    "original",
    "generated_paraphrase",
    "synonym_substitution",
    "reordered_wording",
    "vague_equivalent",
    "answer_intent_phrasing",
    "without_exact_template_keywords",
    "llm_backend_neutral",
]


@dataclass(frozen=True)
class PromptSource:
    group_id: str
    prompt_id: str
    prompt: str
    source: str
    gold_sql: str | None = None
    gold_answer: str | None = None


@dataclass(frozen=True)
class RobustnessContext:
    config: Config
    db: DuckDBDatabase
    schema: SchemaIndex
    endpoint_catalog: EndpointCatalog
    router: QueryRouter
    metadata_selector: MetadataSelector
    planner: StrategyPlanner
    validator: SQLValidator


def build_context(config: Config, *, enable_schema_aware: bool = False) -> RobustnessContext:
    db = DuckDBDatabase(config)
    schema = SchemaIndex.build(db)
    endpoint_catalog = EndpointCatalog(config)
    return RobustnessContext(
        config=config,
        db=db,
        schema=schema,
        endpoint_catalog=endpoint_catalog,
        router=QueryRouter(db.list_tables(), endpoint_catalog),
        metadata_selector=MetadataSelector(schema, endpoint_catalog, config),
        planner=StrategyPlanner(schema, replace(config, enable_schema_aware_sql_fallback=enable_schema_aware)),
        validator=SQLValidator(schema, enable_ast_validation=config.enable_sql_ast_validation),
    )


def load_prompt_sources(
    config: Config,
    *,
    include_public: bool = True,
    include_generated: bool = True,
    max_generated: int | None = None,
) -> list[PromptSource]:
    rows: list[PromptSource] = []
    if include_public:
        harness = EvalHarness(config)
        for example in harness.load_examples():
            rows.append(_prompt_source_from_example(example))
    if include_generated:
        path = config.data_dir / "generated_prompt_suite.json"
        if path.exists():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                payload = []
            if isinstance(payload, list):
                for index, item in enumerate(payload):
                    if max_generated is not None and index >= max_generated:
                        break
                    if not isinstance(item, dict):
                        continue
                    prompt = str(item.get("prompt") or "").strip()
                    if not prompt:
                        continue
                    prompt_id = str(item.get("prompt_id") or f"generated_{index + 1:03d}")
                    rows.append(
                        PromptSource(
                            group_id=f"generated::{prompt_id}",
                            prompt_id=prompt_id,
                            prompt=prompt,
                            source="generated_prompt_diagnostic",
                        )
                    )
    return rows


def deterministic_variants(prompt: str) -> list[dict[str, str]]:
    base = prompt.strip()
    variants = [
        {"variant_kind": "original", "prompt": base},
        {"variant_kind": "generated_paraphrase", "prompt": _clean_sentence(f"Could you answer this from the available snapshot: {base}")},
        {"variant_kind": "synonym_substitution", "prompt": _substitute_synonyms(base)},
        {"variant_kind": "reordered_wording", "prompt": _clean_sentence(f"In the local data, {base.rstrip('?')}?")},
        {"variant_kind": "vague_equivalent", "prompt": _clean_sentence(f"Using the records we have, answer the same request: {base}")},
        {"variant_kind": "answer_intent_phrasing", "prompt": _answer_intent_variant(base)},
        {"variant_kind": "without_exact_template_keywords", "prompt": _remove_template_keywords(base)},
        {"variant_kind": "llm_backend_neutral", "prompt": _clean_sentence(f"Answer deterministically using local evidence where possible: {base}")},
    ]
    deduped: list[dict[str, str]] = []
    seen: set[str] = set()
    for variant in variants:
        text = variant["prompt"].strip()
        key = text.lower()
        if text and key not in seen:
            seen.add(key)
            deduped.append({"variant_kind": variant["variant_kind"], "prompt": text})
    return deduped


def analyze_prompt_variant(
    source: PromptSource,
    variant_kind: str,
    prompt: str,
    context: RobustnessContext,
    *,
    enable_schema_aware_shadow: bool = True,
) -> dict[str, Any]:
    normalization = normalize_query(prompt)
    tokens = extract_query_tokens(prompt, normalization)
    routing = context.router.route(prompt)
    analysis = analyze_query(
        prompt,
        routing,
        context.schema,
        strategy="SQL_FIRST_API_VERIFY",
        config=context.config,
        endpoint_catalog=context.endpoint_catalog,
        normalized=normalization,
        tokens=tokens,
    )
    metadata = context.metadata_selector.select(
        prompt,
        routing,
        strategy="SQL_FIRST_API_VERIFY",
        query_id=f"{source.prompt_id}::{variant_kind}",
        analysis=analysis,
    )
    plan = context.planner.create_plan(prompt, routing, metadata, "SQL_FIRST_API_VERIFY", analysis=analysis)
    sql_step = next((step for step in plan.steps if step.action == "sql" and step.sql), None)
    sql = sql_step.sql if sql_step else None
    validation = context.validator.validate(sql) if sql else None
    execution = None
    if sql and validation and validation.ok:
        execution = context.db.execute_sql(sql, allow_full_result=bool(sql_step and sql_step.allow_full_result))
    ast = sql_ast_summary(sql, context.schema) if sql else {}
    ast_rank = rank_sql_candidate_ast(sql, context.schema, query=prompt, expected_answer_shape=analysis.answer_family) if sql else {}
    schema_shadow = None
    if enable_schema_aware_shadow:
        schema_shadow = generate_schema_aware_sql_candidates(
            prompt,
            context.schema,
            analysis=analysis,
            selected_tables=metadata.get("selected_tables", []),
            max_candidates=3,
            db=context.db,
            execute_probe=True,
        )
    selected_tables = ast.get("selected_tables") or metadata.get("selected_tables", [])
    row = {
        "semantic_group_id": source.group_id,
        "prompt_id": source.prompt_id,
        "source": source.source,
        "variant_kind": variant_kind,
        "prompt": prompt,
        "route_type": routing.route_type,
        "domain_type": routing.domain_type,
        "answer_family": analysis.answer_family,
        "sql_template_family": analysis.sql_template.family if analysis.sql_template else None,
        "template_hit": analysis.sql_template is not None,
        "fallback_sql_used": bool(sql and analysis.sql_template is None),
        "schema_aware_shadow_candidate_available": bool(schema_shadow and schema_shadow.selected_candidate),
        "schema_aware_shadow_candidate_id": (
            schema_shadow.selected_candidate.candidate_id if schema_shadow and schema_shadow.selected_candidate else None
        ),
        "generated_sql": sql,
        "sql_shape": _sql_shape(sql, ast, ast_rank),
        "selected_tables": selected_tables,
        "selected_columns": ast.get("selected_columns", []),
        "join_count": int(ast_rank.get("join_count") or max(0, len(ast.get("selected_tables", [])) - 1)),
        "count_query": _is_count_sql(sql),
        "count_distinct": "count(distinct" in (sql or "").lower(),
        "sql_validation_ok": bool(validation and validation.ok),
        "sql_validation_errors": validation.errors if validation else ["no SQL step"],
        "sql_execution_ok": bool(execution and execution.get("ok")),
        "sql_execution_row_count": execution.get("row_count", 0) if execution else 0,
        "sql_execution_error": execution.get("error") if execution else None,
        "result_type": _result_type(sql, execution),
        "answer_slot_proxy": analysis.answer_family,
        "answer_correctness_proxy": _answer_correctness_proxy(validation, execution),
        "likely_failure": _likely_failure(prompt, analysis.sql_template is not None, sql, validation, execution, ast_rank),
    }
    return redact_secrets(row)


def analyze_prompt_groups(
    config: Config,
    *,
    include_generated: bool = True,
    max_groups: int | None = None,
    max_generated: int | None = None,
    enable_schema_aware: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    context = build_context(config, enable_schema_aware=enable_schema_aware)
    sources = load_prompt_sources(config, include_generated=include_generated, max_generated=max_generated)
    if max_groups is not None:
        sources = sources[:max_groups]
    rows: list[dict[str, Any]] = []
    groups: list[dict[str, Any]] = []
    for source in sources:
        group_rows = [
            analyze_prompt_variant(source, item["variant_kind"], item["prompt"], context)
            for item in deterministic_variants(source.prompt)
        ]
        rows.extend(group_rows)
        groups.append(summarize_group(source, group_rows))
    metrics = summarize_robustness(rows, groups)
    return rows, groups, metrics


def summarize_group(source: PromptSource, rows: list[dict[str, Any]]) -> dict[str, Any]:
    original = next((row for row in rows if row.get("variant_kind") == "original"), rows[0] if rows else {})
    instabilities = {
        "route_changed": any(row.get("route_type") != original.get("route_type") for row in rows),
        "table_changed": any(row.get("selected_tables") != original.get("selected_tables") for row in rows),
        "join_changed": any(row.get("join_count") != original.get("join_count") for row in rows),
        "count_changed": any(row.get("count_query") != original.get("count_query") for row in rows),
        "answer_intent_changed": any(row.get("answer_family") != original.get("answer_family") for row in rows),
        "sql_shape_changed": any(row.get("sql_shape") != original.get("sql_shape") for row in rows),
    }
    consistency_dimensions = [
        "route_type",
        "selected_tables",
        "join_count",
        "count_query",
        "answer_family",
        "sql_shape",
    ]
    stable_scores = []
    for dimension in consistency_dimensions:
        stable_scores.append(sum(1 for row in rows if row.get(dimension) == original.get(dimension)) / max(1, len(rows)))
    return redact_secrets(
        {
            "semantic_group_id": source.group_id,
            "prompt_id": source.prompt_id,
            "source": source.source,
            "original_prompt": source.prompt,
            "variant_count": len(rows),
            "original_route_type": original.get("route_type"),
            "original_selected_tables": original.get("selected_tables", []),
            "original_answer_family": original.get("answer_family"),
            "template_hit_original": bool(original.get("template_hit")),
            "template_hit_variants": sum(1 for row in rows if row.get("template_hit")),
            "sql_validation_pass_variants": sum(1 for row in rows if row.get("sql_validation_ok")),
            "sql_execution_pass_variants": sum(1 for row in rows if row.get("sql_execution_ok")),
            "paraphrase_consistency_score": round(sum(stable_scores) / max(1, len(stable_scores)), 4),
            "instabilities": instabilities,
            "variant_rows": rows,
        }
    )


def summarize_robustness(rows: list[dict[str, Any]], groups: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    template_hit_count = sum(1 for row in rows if row.get("template_hit"))
    template_miss_count = total - template_hit_count
    fallback_rows = [row for row in rows if row.get("fallback_sql_used")]
    fallback_success_count = sum(1 for row in fallback_rows if row.get("sql_validation_ok") and row.get("sql_execution_ok"))
    validation_pass = sum(1 for row in rows if row.get("sql_validation_ok"))
    execution_pass = sum(1 for row in rows if row.get("sql_execution_ok"))
    consistency = _avg(group.get("paraphrase_consistency_score") for group in groups)
    template_miss_due_to_paraphrase = _template_miss_due_to_paraphrase(groups)
    fallback_success_rate = fallback_success_count / len(fallback_rows) if fallback_rows else 0.0
    template_dependency_score = (
        0.40 * (template_hit_count / total if total else 0.0)
        + 0.25 * (1.0 - fallback_success_rate)
        + 0.20 * template_miss_due_to_paraphrase
        + 0.15 * (1.0 - consistency)
    )
    return {
        "row_count": total,
        "semantic_group_count": len(groups),
        "template_hit_count": template_hit_count,
        "template_miss_count": template_miss_count,
        "template_hit_rate": round(template_hit_count / total, 4) if total else 0.0,
        "template_miss_rate": round(template_miss_count / total, 4) if total else 0.0,
        "fallback_sql_used_count": len(fallback_rows),
        "fallback_success_count": fallback_success_count,
        "fallback_success_rate": round(fallback_success_rate, 4),
        "sql_validation_pass_rate": round(validation_pass / total, 4) if total else 0.0,
        "sql_execution_pass_rate": round(execution_pass / total, 4) if total else 0.0,
        "answer_correctness_proxy": round(_avg(row.get("answer_correctness_proxy") for row in rows), 4),
        "route_stability": round(_stability(groups, "route_changed"), 4),
        "table_selection_stability": round(_stability(groups, "table_changed"), 4),
        "join_selection_stability": round(_stability(groups, "join_changed"), 4),
        "count_count_distinct_stability": round(_stability(groups, "count_changed"), 4),
        "answer_intent_stability": round(_stability(groups, "answer_intent_changed"), 4),
        "paraphrase_consistency_score": round(consistency, 4),
        "template_miss_due_to_paraphrase_rate": round(template_miss_due_to_paraphrase, 4),
        "template_dependency_score": round(template_dependency_score, 4),
        "route_distribution": dict(Counter(row.get("route_type") or "UNKNOWN" for row in rows)),
        "domain_distribution": dict(Counter(row.get("domain_type") or "UNKNOWN" for row in rows)),
        "answer_family_distribution": dict(Counter(row.get("answer_family") or "UNKNOWN" for row in rows)),
        "failure_distribution": dict(Counter(row.get("likely_failure") or "none" for row in rows)),
    }


def safe_report_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return redact_secrets(payload)


def _prompt_source_from_example(example: EvalExample) -> PromptSource:
    return PromptSource(
        group_id=f"public_dev::{example.query_id}",
        prompt_id=example.query_id,
        prompt=example.query,
        source="public_dev",
        gold_sql=example.gold_sql,
        gold_answer=example.gold_answer,
    )


def _substitute_synonyms(text: str) -> str:
    replacements = [
        (r"\bhow many\b", "what is the number of"),
        (r"\bcount\b", "total"),
        (r"\blist\b", "show"),
        (r"\bwhich\b", "identify which"),
        (r"\bstatus\b", "state"),
        (r"\bcreated\b", "made"),
        (r"\bupdated\b", "modified"),
    ]
    result = text
    for pattern, replacement in replacements:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    return _clean_sentence(result)


def _answer_intent_variant(text: str) -> str:
    lowered = text.lower()
    if any(marker in lowered for marker in ["how many", "count", "number of", "total"]):
        return _clean_sentence(f"Return the total count for this request: {text}")
    if any(marker in lowered for marker in ["when", "date", "recent", "latest"]):
        return _clean_sentence(f"Return the relevant date or most recent record for this request: {text}")
    if any(marker in lowered for marker in ["status", "state"]):
        return _clean_sentence(f"Return the status/state answer for this request: {text}")
    return _clean_sentence(f"Return the matching names or identifiers for this request: {text}")


def _remove_template_keywords(text: str) -> str:
    replacements = [
        (r"\bhow many\b", "give the total"),
        (r"\bnumber of\b", "total"),
        (r"\blist all\b", "show every"),
        (r"\blist\b", "show"),
        (r"\bwhat is\b", "tell me"),
        (r"\bwhich\b", "identify"),
        (r"\bfind\b", "locate"),
    ]
    result = text
    for pattern, replacement in replacements:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    return _clean_sentence(result)


def _clean_sentence(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _sql_shape(sql: str | None, ast: dict[str, Any], ast_rank: dict[str, Any]) -> str | None:
    if not sql:
        return None
    normalized = str(ast.get("normalized_sql") or sql)
    normalized = re.sub(r"'[^']*'", "'?'", normalized)
    normalized = re.sub(r"\b\d+(?:\.\d+)?\b", "?", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip().lower()
    join_count = int(ast_rank.get("join_count") or max(0, len(ast.get("selected_tables", [])) - 1))
    count = "count_distinct" if "count(distinct" in normalized else ("count" if "count(" in normalized else "non_count")
    return f"{count}|joins={join_count}|{normalized}"


def _is_count_sql(sql: str | None) -> bool:
    return bool(sql and re.search(r"\bcount\s*\(", sql, re.IGNORECASE))


def _result_type(sql: str | None, execution: dict[str, Any] | None) -> str:
    if not sql:
        return "no_sql"
    if execution is None:
        return "not_executed"
    if not execution.get("ok"):
        return "execution_error"
    if _is_count_sql(sql):
        return "count"
    if int(execution.get("row_count") or 0) == 0:
        return "zero_rows"
    return "rows"


def _answer_correctness_proxy(validation: Any, execution: dict[str, Any] | None) -> float:
    if not validation or not validation.ok:
        return 0.0
    if execution is None:
        return 0.5
    if execution.get("ok"):
        return 1.0
    return 0.0


def _likely_failure(
    prompt: str,
    template_hit: bool,
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
    if any(marker in lowered for marker in ["unique", "distinct", "different"]) and _is_count_sql(sql) and "count(distinct" not in sql.lower():
        return "count_distinct_gap"
    if any(marker in lowered for marker in ["connected", "mapped", "related", "associated", "linked"]) and int(ast_rank.get("join_count") or 0) == 0:
        return "join_reasoning_gap"
    if re.search(r"'[^']+'|\"[^\"]+\"", prompt) and " where " not in sql.lower():
        return "where_condition_gap"
    if execution is not None and not execution.get("ok"):
        return "template_gap" if template_hit else "table_selection_gap"
    return "none"


def _stability(groups: list[dict[str, Any]], instability_key: str) -> float:
    if not groups:
        return 0.0
    return 1.0 - (sum(1 for group in groups if group.get("instabilities", {}).get(instability_key)) / len(groups))


def _template_miss_due_to_paraphrase(groups: list[dict[str, Any]]) -> float:
    eligible = [group for group in groups if group.get("template_hit_original")]
    if not eligible:
        return 0.0
    changed = 0
    for group in eligible:
        variants = group.get("variant_rows") or []
        if any(row.get("variant_kind") != "original" and not row.get("template_hit") for row in variants):
            changed += 1
    return changed / len(eligible)


def _avg(values: Iterable[Any]) -> float:
    nums = [float(value) for value in values if isinstance(value, (int, float))]
    return sum(nums) / len(nums) if nums else 0.0
