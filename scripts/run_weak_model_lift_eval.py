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
    score_answer_strict,
    score_api_strict,
    score_sql_strict,
)
from dashagent.llm_client import get_llm_client
from dashagent.llm_tool_agent import GUIDED_REAL_LLM_TWO_TOOLS_BASELINE, RAW_REAL_LLM_TWO_TOOLS_BASELINE
from dashagent.schema_index import SchemaIndex
from dashagent.semantic_slot_compiler import compile_semantic_slots
from dashagent.trajectory import estimate_tokens, redact_secrets
from dashagent.validators import SQLValidator
from dashagent.weak_model_answer_grounder import ground_weak_model_answer
from dashagent.weak_model_api_evidence_bridge import build_api_evidence
from dashagent.weak_model_semantic_slots import classify_balanced_evidence_need, weak_model_semantic_slots
from scripts.load_local_env import load_local_env

REPORT_STEM = "weak_model_lift_eval"
DEFINITION_STEM = "weak_model_lift_definition"
STABILIZATION_SET_PATH = ROOT / "data" / "pure_llm_stabilization_set.json"

WEAK_MODEL_VARIANTS = [
    "raw_weak_llm",
    "guided_weak_llm",
    "json_action_weak_llm",
    "semantic_slot_weak_llm",
    "weak_semantic_slots_only",
    "slot_to_sql_compiled_agent",
    "weak_slots_to_sql_compiler",
    "weak_slots_to_sql_api_compiler",
    "evidence_guarded_weak_agent",
    "weak_full_dashagent_scaffold",
    "weak_scaffold_balanced_sql_api_v1",
    "weak_scaffold_api_recovery_v1",
    "weak_scaffold_answer_grounded_v1",
    "weak_scaffold_balanced_full_v1",
    "weak_scaffold_sql_retrieval_v1",
    "weak_scaffold_sql_unit_tested_v1",
    "weak_scaffold_sql_retrieval_repair_v1",
    "weak_scaffold_balanced_sql_api_v2",
    "weak_scaffold_balanced_sql_api_answer_v3",
    "weak_scaffold_sql_lift_api_recovery_v3",
    "weak_scaffold_answer_fallback_v3",
    "weak_harness_slots_only_v1",
    "weak_harness_schema_retrieval_v1",
    "weak_harness_unit_tested_sql_v1",
    "weak_harness_repair_loop_v1",
    "weak_harness_balanced_sql_api_answer_v1",
    "weak_harness_full_v1",
    "weak_harness_answer_v1_style_preserve",
    "weak_harness_answer_evidence_bullets",
    "weak_harness_answer_slot_template",
    "weak_harness_answer_api_primary_when_api_scores_better",
    "weak_harness_compact_context_v1",
    "weak_harness_skip_repair_when_unit_pass_v1",
    "weak_harness_compact_trace_v1",
    "weak_harness_answer_grounding_compact_v1",
    "weak_harness_answer_and_efficiency_v2",
    "full_dashagent_current",
]

BALANCED_VARIANTS = {
    "weak_scaffold_balanced_sql_api_v1",
    "weak_scaffold_api_recovery_v1",
    "weak_scaffold_answer_grounded_v1",
    "weak_scaffold_balanced_full_v1",
    "weak_scaffold_balanced_sql_api_v2",
    "weak_scaffold_balanced_sql_api_answer_v3",
    "weak_scaffold_sql_lift_api_recovery_v3",
    "weak_scaffold_answer_fallback_v3",
    "weak_harness_schema_retrieval_v1",
    "weak_harness_unit_tested_sql_v1",
    "weak_harness_repair_loop_v1",
    "weak_harness_balanced_sql_api_answer_v1",
    "weak_harness_full_v1",
    "weak_harness_answer_v1_style_preserve",
    "weak_harness_answer_evidence_bullets",
    "weak_harness_answer_slot_template",
    "weak_harness_answer_api_primary_when_api_scores_better",
    "weak_harness_compact_context_v1",
    "weak_harness_skip_repair_when_unit_pass_v1",
    "weak_harness_compact_trace_v1",
    "weak_harness_answer_grounding_compact_v1",
    "weak_harness_answer_and_efficiency_v2",
}

SQL_ENHANCED_VARIANTS = {
    "weak_scaffold_sql_retrieval_v1",
    "weak_scaffold_sql_unit_tested_v1",
    "weak_scaffold_sql_retrieval_repair_v1",
    "weak_scaffold_balanced_sql_api_v2",
    "weak_scaffold_balanced_sql_api_answer_v3",
    "weak_scaffold_sql_lift_api_recovery_v3",
    "weak_scaffold_answer_fallback_v3",
    "weak_harness_schema_retrieval_v1",
    "weak_harness_unit_tested_sql_v1",
    "weak_harness_repair_loop_v1",
    "weak_harness_balanced_sql_api_answer_v1",
    "weak_harness_full_v1",
    "weak_harness_answer_v1_style_preserve",
    "weak_harness_answer_evidence_bullets",
    "weak_harness_answer_slot_template",
    "weak_harness_answer_api_primary_when_api_scores_better",
    "weak_harness_compact_context_v1",
    "weak_harness_skip_repair_when_unit_pass_v1",
    "weak_harness_compact_trace_v1",
    "weak_harness_answer_grounding_compact_v1",
    "weak_harness_answer_and_efficiency_v2",
}

SQL_REPAIR_VARIANTS = {
    "weak_scaffold_sql_retrieval_repair_v1",
    "weak_scaffold_balanced_sql_api_v2",
    "weak_scaffold_balanced_sql_api_answer_v3",
    "weak_scaffold_sql_lift_api_recovery_v3",
    "weak_scaffold_answer_fallback_v3",
    "weak_harness_repair_loop_v1",
    "weak_harness_balanced_sql_api_answer_v1",
    "weak_harness_full_v1",
    "weak_harness_answer_v1_style_preserve",
    "weak_harness_answer_evidence_bullets",
    "weak_harness_answer_slot_template",
    "weak_harness_answer_api_primary_when_api_scores_better",
    "weak_harness_compact_context_v1",
    "weak_harness_skip_repair_when_unit_pass_v1",
    "weak_harness_compact_trace_v1",
    "weak_harness_answer_grounding_compact_v1",
    "weak_harness_answer_and_efficiency_v2",
}

ANSWER_GROUNDING_V3_VARIANTS = {
    "weak_scaffold_balanced_sql_api_answer_v3",
    "weak_scaffold_sql_lift_api_recovery_v3",
    "weak_scaffold_answer_fallback_v3",
    "weak_harness_balanced_sql_api_answer_v1",
    "weak_harness_full_v1",
    "weak_harness_answer_v1_style_preserve",
    "weak_harness_answer_evidence_bullets",
    "weak_harness_answer_slot_template",
    "weak_harness_answer_api_primary_when_api_scores_better",
    "weak_harness_answer_grounding_compact_v1",
    "weak_harness_answer_and_efficiency_v2",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--variant", action="append", choices=WEAK_MODEL_VARIANTS)
    parser.add_argument("--stabilization-set", action="store_true")
    parser.add_argument("--full-public-dev", action="store_true")
    parser.add_argument("--artifact-only", action="store_true")
    args = parser.parse_args()
    config = Config.from_env(ROOT)
    load_local_env(config.project_root)
    limit = None if args.full_public_dev else args.limit
    payload = run_weak_model_lift_eval(
        config,
        max_examples=limit,
        variants=args.variant,
        stabilization_set=args.stabilization_set,
        execute_real=not args.artifact_only,
    )
    print(json.dumps({"json": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.json"), "summary": payload["summary"]}, indent=2, sort_keys=True))
    return 0


def run_weak_model_lift_eval(
    config: Config | None = None,
    *,
    max_examples: int | None = None,
    variants: list[str] | None = None,
    stabilization_set: bool = False,
    execute_real: bool = True,
) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports = config.outputs_dir / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    _write_definition(config)
    variants = variants or [
        "raw_weak_llm",
        "guided_weak_llm",
        "weak_semantic_slots_only",
        "slot_to_sql_compiled_agent",
        "evidence_guarded_weak_agent",
        "weak_full_dashagent_scaffold",
        "weak_scaffold_api_recovery_v1",
        "weak_scaffold_balanced_sql_api_v2",
        "weak_scaffold_balanced_sql_api_answer_v3",
        "full_dashagent_current",
    ]
    rows = _stabilization_rows(config, variants, max_examples=max_examples, execute_real=execute_real) if stabilization_set else _public_rows(config, variants, max_examples=max_examples, execute_real=execute_real)
    summary = _summary(rows)
    run_label = "stabilization_set" if stabilization_set else (f"public_dev_limit_{max_examples}" if max_examples else "public_dev_full")
    payload = redact_secrets(
        {
            "report_type": REPORT_STEM,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "diagnostic_only": True,
            "promotion_allowed": False,
            "packaged_runtime_changed": False,
            "packaged_default_strategy": "SQL_FIRST_API_VERIFY",
            "stabilization_set": stabilization_set,
            "run_label": run_label,
            "execute_real_requested": execute_real,
            "summary": summary,
            "rows": rows,
        }
    )
    (reports / f"{REPORT_STEM}.json").write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    (reports / f"{REPORT_STEM}.md").write_text(_render_md(payload), encoding="utf-8")
    (reports / f"{REPORT_STEM}_{run_label}.json").write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    (reports / f"{REPORT_STEM}_{run_label}.md").write_text(_render_md(payload), encoding="utf-8")
    return payload


def _public_rows(config: Config, variants: list[str], *, max_examples: int | None, execute_real: bool) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    rows.extend(_baseline_rows(config, variants, max_examples=max_examples))
    harness = EvalHarness(config)
    examples = harness.load_examples()
    if max_examples:
        examples = examples[:max_examples]
    db = DuckDBDatabase(config)
    schema = SchemaIndex.build(db)
    catalog = EndpointCatalog(config)
    client = get_llm_client()
    api_client = AdobeAPIClient(config)
    full_current_rows = _full_system_rows(config, max_examples=max_examples) if "full_dashagent_current" in variants else {}
    for example in examples:
        for variant in variants:
            if variant in {"raw_weak_llm", "guided_weak_llm"}:
                continue
            if variant == "full_dashagent_current":
                row = full_current_rows.get(example.query_id)
                if row:
                    rows.append(row)
                continue
            result = _run_scaffold_variant(example.query, variant, db, schema, catalog, api_client, client if execute_real else None)
            rows.append(_score_row(harness, example, variant, result["trajectory"], result["final_answer"], unsupported=result.get("unsupported_claim_count", 0)))
    db.close()
    return rows


def _stabilization_rows(config: Config, variants: list[str], *, max_examples: int | None, execute_real: bool) -> list[dict[str, Any]]:
    prompts = json.loads(STABILIZATION_SET_PATH.read_text(encoding="utf-8")) if STABILIZATION_SET_PATH.exists() else []
    if max_examples:
        prompts = prompts[:max_examples]
    db = DuckDBDatabase(config)
    schema = SchemaIndex.build(db)
    catalog = EndpointCatalog(config)
    api_client = AdobeAPIClient(config)
    client = get_llm_client()
    rows = []
    for item in prompts:
        for variant in variants:
            if variant in {"raw_weak_llm", "guided_weak_llm", "full_dashagent_current"}:
                continue
            result = _run_scaffold_variant(item["prompt"], variant, db, schema, catalog, api_client, client if execute_real else None)
            rows.append(
                {
                    "prompt_id": item.get("prompt_id"),
                    "prompt": item.get("prompt"),
                    "mode": variant,
                    "strict_scoring_status": "not_applicable_stabilization",
                    "runtime_pass": not result.get("skipped", False),
                    "unsupported_claim_count": result.get("unsupported_claim_count", 0),
                    "tool_calls": result["trajectory"].get("tool_call_count", 0),
                    "estimated_tokens": result["trajectory"].get("estimated_tokens", 0),
                    "runtime": result["trajectory"].get("runtime", 0),
                    "failure_stage": result.get("failure_stage") or "no_clear_failure",
                }
            )
    db.close()
    return rows


def _run_scaffold_variant(prompt: str, variant: str, db: DuckDBDatabase, schema: SchemaIndex, catalog: EndpointCatalog, api_client: AdobeAPIClient, client: Any | None) -> dict[str, Any]:
    import time

    start = time.perf_counter()
    slots = weak_model_semantic_slots(prompt, client if variant not in {"weak_semantic_slots_only", "semantic_slot_weak_llm"} else None)
    if variant in {"weak_semantic_slots_only", "semantic_slot_weak_llm", "weak_harness_slots_only_v1"}:
        answer = f"Semantic slots: intent={slots['intent']}, domain={slots['domain']}, evidence_need={slots['evidence_need']}."
        trajectory = {"strategy": variant, "steps": [{"kind": "semantic_slots", "slots": slots}], "final_answer": answer, "tool_call_count": 0, "runtime": time.perf_counter() - start}
        trajectory["estimated_tokens"] = estimate_tokens(trajectory)
        return {"final_answer": answer, "trajectory": trajectory, "unsupported_claim_count": 0, "failure_stage": "slots_only_no_tool_execution"}
    if variant in BALANCED_VARIANTS:
        slots = dict(slots)
        slots["evidence_need"] = classify_balanced_evidence_need(prompt, slots)
    compiled = compile_semantic_slots(
        slots,
        schema,
        catalog,
        SQLValidator(schema),
        prompt=prompt,
        enhanced_sql=variant in SQL_ENHANCED_VARIANTS,
        repair_rounds=1 if variant in SQL_REPAIR_VARIANTS else 0,
        retrieval_limits=_retrieval_limits_for_variant(variant),
    )
    sql_result: dict[str, Any] | None = None
    sql = ""
    if compiled.get("sql_candidates"):
        sql = compiled["sql_candidates"][0]["sql"]
        sql_result = db.execute_sql(sql)
    api_results: list[tuple[dict[str, Any], dict[str, Any]]] = []
    should_run_api = bool(compiled.get("api_candidates")) and (variant in BALANCED_VARIANTS or not sql_result)
    max_api_calls = _max_api_calls_for_variant(variant)
    if should_run_api:
        for call in list(compiled.get("api_candidates") or [])[:max_api_calls]:
            result = api_client.call_api(call["method"], call["path"], call.get("params", {}), {})
            api_results.append((call, result))
    api_result = api_results[0][1] if api_results else None
    api_endpoint_id = api_results[0][0].get("endpoint_id", "") if api_results else ""
    model_answer = ""
    grounded = ground_weak_model_answer(
        prompt,
        model_answer=model_answer,
        sql_result=sql_result,
        api_result=api_result,
        answer_intent=slots.get("intent", "DETAIL"),
        evidence_need=str(slots.get("evidence_need") or "sql_first"),
        api_endpoint_id=api_endpoint_id,
        grounding_mode=_grounding_mode_for_variant(variant),
    )
    answer = grounded["answer"] if variant in {"evidence_guarded_weak_agent", "weak_full_dashagent_scaffold"} | BALANCED_VARIANTS else (grounded["answer"] if sql_result else "The scaffold could not produce executable evidence.")
    trajectory_compact = _compact_trace_enabled(variant)
    compiled_for_trace = _compact_compiled_trace(compiled) if trajectory_compact else compiled
    grounded_for_trace = _compact_grounding_trace(grounded) if trajectory_compact or variant == "weak_harness_answer_grounding_compact_v1" else grounded
    steps = [
        {"kind": "semantic_slots", "slots": slots},
        {"kind": "slot_compiler", "compiled": compiled_for_trace},
    ]
    if sql:
        steps.append({"kind": "sql_call", "sql": sql, "validation": compiled["sql_candidates"][0].get("validation"), "result": _compact_sql_result(sql_result) if trajectory_compact else sql_result})
    for call, result in api_results:
        steps.append(
            {
                "kind": "api_call",
                "method": call["method"],
                "url": call["path"],
                "path": call["path"],
                "params": call.get("params", {}),
                "validation": call.get("validation"),
                "result": _compact_api_result(call, result),
            }
        )
    steps.append({"kind": "final_answer", "answer": answer, "grounding": grounded_for_trace})
    trajectory = {"strategy": variant, "steps": steps, "final_answer": answer, "tool_call_count": sum(1 for step in steps if step["kind"] in {"sql_call", "api_call"}), "runtime": time.perf_counter() - start}
    trajectory["estimated_tokens"] = estimate_tokens(trajectory)
    return {"final_answer": answer, "trajectory": trajectory, "unsupported_claim_count": grounded.get("unsupported_claim_count", 0), "failure_stage": None if sql_result or api_results else "no_executable_tool_evidence"}


def _grounding_mode_for_variant(variant: str) -> str:
    if variant == "weak_scaffold_balanced_sql_api_answer_v3":
        return "balanced_sql_api_answer_v3"
    if variant == "weak_scaffold_sql_lift_api_recovery_v3":
        return "sql_lift_api_recovery_v3"
    if variant == "weak_scaffold_answer_fallback_v3":
        return "answer_fallback_v3"
    if variant in {"weak_harness_balanced_sql_api_answer_v1", "weak_harness_full_v1"}:
        return "answer_fallback_v3"
    if variant == "weak_harness_answer_v1_style_preserve":
        return "harness_answer_v1_style_preserve"
    if variant == "weak_harness_answer_evidence_bullets":
        return "harness_answer_evidence_bullets"
    if variant == "weak_harness_answer_slot_template":
        return "harness_answer_slot_template"
    if variant == "weak_harness_answer_api_primary_when_api_scores_better":
        return "harness_answer_api_primary_when_api_scores_better"
    if variant == "weak_harness_answer_grounding_compact_v1":
        return "harness_answer_grounding_compact"
    if variant == "weak_harness_answer_and_efficiency_v2":
        return "harness_answer_v1_style_preserve"
    return "default"


def _retrieval_limits_for_variant(variant: str) -> dict[str, int] | None:
    if variant in {
        "weak_harness_compact_context_v1",
    }:
        return {"max_tables": 4, "max_columns_per_table": 12, "max_join_hints": 4, "max_skeletons": 2}
    return None


def _max_api_calls_for_variant(variant: str) -> int:
    if variant in {
        "weak_harness_compact_context_v1",
        "weak_harness_compact_trace_v1",
        "weak_harness_answer_grounding_compact_v1",
    }:
        return 1
    return 2


def _compact_trace_enabled(variant: str) -> bool:
    return variant in {
        "weak_harness_compact_trace_v1",
        "weak_harness_answer_grounding_compact_v1",
        "weak_harness_answer_and_efficiency_v2",
    }


def _compact_compiled_trace(compiled: dict[str, Any]) -> dict[str, Any]:
    compact_candidates = []
    for candidate in list(compiled.get("sql_candidates") or [])[:1]:
        compact_candidates.append(
            {
                "sql": candidate.get("sql"),
                "validation": candidate.get("validation"),
                "sql_unit_tests": candidate.get("sql_unit_tests"),
                "repair_attempts": candidate.get("repair_attempts"),
                "repair_success": candidate.get("repair_success"),
            }
        )
    return {
        "ok": compiled.get("ok"),
        "slots": compiled.get("slots"),
        "sql_candidates": compact_candidates,
        "api_candidates": list(compiled.get("api_candidates") or [])[:1],
        "evidence_policy": compiled.get("evidence_policy"),
        "compiler_warnings": compiled.get("compiler_warnings"),
        "compiler_errors": compiled.get("compiler_errors"),
        "enhanced_sql": compiled.get("enhanced_sql"),
        "schema_context": _compact_schema_context(compiled.get("schema_context")),
        "sql_skeletons": [
            {
                "skeleton_id": item.get("skeleton_id"),
                "intent": item.get("intent"),
                "unit_tests": item.get("unit_tests"),
            }
            for item in list(compiled.get("sql_skeletons") or [])[:2]
            if isinstance(item, dict)
        ],
    }


def _compact_schema_context(schema_context: Any) -> dict[str, Any] | None:
    if not isinstance(schema_context, dict):
        return None
    return {
        "retrieved_tables": schema_context.get("retrieved_tables"),
        "column_roles": schema_context.get("column_roles"),
        "value_links": schema_context.get("value_links"),
        "join_candidate_count": len(schema_context.get("join_candidates") or []),
        "confidence": schema_context.get("confidence"),
    }


def _compact_sql_result(sql_result: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(sql_result, dict):
        return sql_result
    return {
        "ok": sql_result.get("ok"),
        "row_count": sql_result.get("row_count"),
        "rows": list(sql_result.get("rows") or [])[:2],
        "error": sql_result.get("error"),
    }


def _compact_grounding_trace(grounded: dict[str, Any]) -> dict[str, Any]:
    sql = grounded.get("sql_evidence") if isinstance(grounded.get("sql_evidence"), dict) else None
    api = grounded.get("api_evidence") if isinstance(grounded.get("api_evidence"), dict) else None
    return {
        "answer": grounded.get("answer"),
        "answer_used_sql": grounded.get("answer_used_sql"),
        "answer_used_api": grounded.get("answer_used_api"),
        "fallback_used": grounded.get("fallback_used"),
        "unsupported_claim_count": grounded.get("unsupported_claim_count"),
        "sql_evidence": _compact_sql_evidence(sql),
        "api_evidence": _compact_api_evidence(api),
        "sql_evidence_object_available": grounded.get("sql_evidence_object_available"),
        "api_evidence_object_available": grounded.get("api_evidence_object_available"),
        "sql_api_arbitration_mode": grounded.get("sql_api_arbitration_mode"),
        "grounding_mode": grounded.get("grounding_mode"),
    }


def _compact_sql_evidence(evidence: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(evidence, dict):
        return None
    return {
        "sql_executed": evidence.get("sql_executed"),
        "row_count": evidence.get("row_count"),
        "count_value": evidence.get("count_value"),
        "key_ids": list(evidence.get("key_ids") or [])[:3],
        "key_names": list(evidence.get("key_names") or [])[:3],
        "status_values": list(evidence.get("status_values") or [])[:3],
        "timestamp_values": list(evidence.get("timestamp_values") or [])[:3],
        "zero_rows": evidence.get("zero_rows"),
    }


def _compact_api_evidence(evidence: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(evidence, dict):
        return None
    return {
        "endpoint_id": evidence.get("endpoint_id"),
        "live_success": evidence.get("live_success"),
        "live_empty": evidence.get("live_empty"),
        "api_error": evidence.get("api_error"),
        "dry_run": evidence.get("dry_run"),
        "ids": list(evidence.get("ids") or [])[:3],
        "names": list(evidence.get("names") or [])[:3],
        "statuses": list(evidence.get("statuses") or [])[:3],
        "timestamps": list(evidence.get("timestamps") or [])[:3],
        "counts": list(evidence.get("counts") or [])[:3],
    }


def _compact_api_result(call: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    evidence = build_api_evidence(str(call.get("endpoint_id") or ""), result)
    return {
        "ok": bool(result.get("ok")),
        "dry_run": bool(result.get("dry_run")),
        "status_code": result.get("status_code"),
        "endpoint_id": call.get("endpoint_id"),
        "endpoint": result.get("endpoint") or call.get("path"),
        "api_evidence": evidence,
        "error": result.get("error") if result.get("error") else None,
    }


def _score_row(harness: EvalHarness, example: Any, mode: str, trajectory: dict[str, Any], answer: str, *, unsupported: int = 0) -> dict[str, Any]:
    sql = next((step.get("sql") for step in trajectory.get("steps", []) if step.get("kind") == "sql_call"), None)
    api_calls = [step for step in trajectory.get("steps", []) if step.get("kind") == "api_call"]
    sql_score, _ = score_sql_strict(harness.executor.db, sql, example.gold_sql)
    api_score, _ = score_api_strict(api_calls, example.gold_api)
    answer_score, _ = score_answer_strict(answer, example.gold_answer)
    correctness, unscored = aggregate_strict_correctness({"sql": sql_score, "api": api_score, "answer": answer_score})
    efficiency_penalty = min(1.0, (float(trajectory.get("tool_call_count") or 0) / 8) + (float(trajectory.get("runtime") or 0) / 30) + (float(trajectory.get("estimated_tokens") or 0) / 12000))
    final = correctness - 0.1 * efficiency_penalty
    return redact_secrets(
        {
            "query_id": example.query_id,
            "prompt": example.query,
            "mode": mode,
            "strict_scoring_status": "available",
            "strict_final_score": round(final, 4),
            "strict_correctness": round(correctness, 4),
            "answer_score": round(answer_score, 4),
            "sql_score": round(sql_score, 4) if isinstance(sql_score, (int, float)) else None,
            "api_score": round(api_score, 4) if isinstance(api_score, (int, float)) else None,
            "unscored_dimension_count": unscored,
            "tool_calls": trajectory.get("tool_call_count", 0),
            "estimated_tokens": trajectory.get("estimated_tokens", 0),
            "runtime": round(float(trajectory.get("runtime") or 0), 4),
            "unsupported_claim_count": unsupported,
            "trajectory": trajectory,
        }
    )


def _baseline_rows(config: Config, variants: list[str], *, max_examples: int | None = None) -> list[dict[str, Any]]:
    if not {"raw_weak_llm", "guided_weak_llm"} & set(variants):
        return []
    path = config.outputs_dir / "llm_strict_baseline_eval.json"
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    mapping = {RAW_REAL_LLM_TWO_TOOLS_BASELINE: "raw_weak_llm", GUIDED_REAL_LLM_TWO_TOOLS_BASELINE: "guided_weak_llm"}
    rows = []
    kept_by_mode: dict[str, int] = {}
    for item in payload.get("rows", []):
        mode = mapping.get(item.get("system"))
        if not mode or mode not in variants:
            continue
        if max_examples is not None and kept_by_mode.get(mode, 0) >= max_examples:
            continue
        kept_by_mode[mode] = kept_by_mode.get(mode, 0) + 1
        failures = item.get("failure_categories") if isinstance(item.get("failure_categories"), dict) else {}
        rows.append(
            {
                "query_id": item.get("query_id"),
                "prompt": item.get("query"),
                "mode": mode,
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
                "source": "existing_llm_strict_baseline_eval",
            }
        )
    return rows


def _full_system_rows(config: Config, *, max_examples: int | None = None) -> dict[str, dict[str, Any]]:
    path = config.outputs_dir / "eval_results_strict.json"
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows: dict[str, dict[str, Any]] = {}
    kept = 0
    for item in payload.get("rows", []):
        if item.get("strategy") != "SQL_FIRST_API_VERIFY":
            continue
        if max_examples is not None and kept >= max_examples:
            break
        kept += 1
        query_id = str(item.get("query_id") or "")
        rows[query_id] = {
            "query_id": query_id,
            "prompt": item.get("query"),
            "mode": "full_dashagent_current",
            "strict_scoring_status": "available",
            "strict_final_score": item.get("final_score"),
            "strict_correctness": item.get("correctness_score"),
            "answer_score": item.get("answer_score"),
            "sql_score": item.get("sql_score"),
            "api_score": item.get("api_score"),
            "tool_calls": item.get("tool_call_count"),
            "estimated_tokens": item.get("estimated_tokens"),
            "runtime": item.get("runtime"),
            "unsupported_claim_count": 0,
            "source": "existing_eval_results_strict_sql_first_api_verify",
        }
    return rows


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    modes = []
    for mode in sorted({str(row.get("mode")) for row in rows if row.get("mode")}):
        mode_rows = [row for row in rows if row.get("mode") == mode and row.get("strict_scoring_status") == "available"]
        if not mode_rows:
            other = [row for row in rows if row.get("mode") == mode]
            modes.append({"mode": mode, "rows": len(other), "strict_scoring_status": "unavailable_or_not_applicable", "unsupported_claims": sum(int(row.get("unsupported_claim_count") or 0) for row in other)})
            continue
        modes.append(
            {
                "mode": mode,
                "rows": len(mode_rows),
                "strict_final_score": _avg(mode_rows, "strict_final_score"),
                "strict_correctness": _avg(mode_rows, "strict_correctness"),
                "answer_score": _avg(mode_rows, "answer_score"),
                "sql_score": _avg(mode_rows, "sql_score"),
                "api_score": _avg(mode_rows, "api_score"),
                "tool_calls": _avg(mode_rows, "tool_calls"),
                "estimated_tokens": _avg(mode_rows, "estimated_tokens"),
                "runtime": _avg(mode_rows, "runtime"),
                "unsupported_claims": sum(int(row.get("unsupported_claim_count") or 0) for row in mode_rows),
            }
        )
    raw = next((item for item in modes if item.get("mode") == "raw_weak_llm"), {})
    best_scaffold = max((item for item in modes if item.get("mode") not in {"raw_weak_llm", "guided_weak_llm", "full_dashagent_current"} and isinstance(item.get("strict_final_score"), (int, float))), key=lambda item: item.get("strict_final_score", -999), default={})
    lift = _delta(best_scaffold.get("strict_final_score"), raw.get("strict_final_score"))
    return {
        "modes": modes,
        "best_scaffold_mode": best_scaffold.get("mode"),
        "small_model_lift_score": lift,
        "sql_lift": _delta(best_scaffold.get("sql_score"), raw.get("sql_score")),
        "api_lift": _delta(best_scaffold.get("api_score"), raw.get("api_score")),
        "answer_grounding_lift": _delta(best_scaffold.get("answer_score"), raw.get("answer_score")),
        "efficiency_lift": _delta(raw.get("estimated_tokens"), best_scaffold.get("estimated_tokens")),
        "unsupported_claim_delta": _delta(best_scaffold.get("unsupported_claims"), raw.get("unsupported_claims")),
        "recommendation": "weak_model_scaffold_improved_keep_shadow" if isinstance(lift, (int, float)) and lift > 0 else "current_deterministic_system_still_preferred",
    }


def _write_definition(config: Config) -> None:
    reports = config.outputs_dir / "reports"
    report = {
        "report_type": DEFINITION_STEM,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "diagnostic_only": True,
        "promotion_allowed": False,
        "objective": "Measure how much DashAgent scaffolding lifts weak-model correctness, tool validity, evidence grounding, robustness, and efficiency.",
        "modes": WEAK_MODEL_VARIANTS,
        "formula": "small_model_lift_score = DashAgent-assisted weak-model score - raw weak-model score",
        "metrics": ["strict_score", "correctness", "answer_score", "sql_score", "api_score", "unsupported_claims", "tool_count", "tokens", "runtime", "paraphrase_consistency", "generated_prompt_robustness", "endpoint_matrix_health", "hidden_style_stability"],
    }
    (reports / f"{DEFINITION_STEM}.json").write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    (reports / f"{DEFINITION_STEM}.md").write_text(_render_definition_md(report), encoding="utf-8")


def _render_definition_md(report: dict[str, Any]) -> str:
    return "\n".join(["# Weak Model Lift Definition", "", report["objective"], "", f"- Formula: `{report['formula']}`", "", "## Modes", "", *[f"- `{mode}`" for mode in report["modes"]], ""])


def _render_md(payload: dict[str, Any]) -> str:
    lines = ["# Weak Model Lift Eval", "", "Diagnostic-only. Packaged `SQL_FIRST_API_VERIFY` runtime is unchanged.", "", "| Mode | Rows | Strict | SQL | API | Answer | Unsupported |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for item in payload["summary"]["modes"]:
        lines.append(f"| `{item.get('mode')}` | {item.get('rows', 0)} | {item.get('strict_final_score', 'n/a')} | {item.get('sql_score', 'n/a')} | {item.get('api_score', 'n/a')} | {item.get('answer_score', 'n/a')} | {item.get('unsupported_claims', 'n/a')} |")
    lines.append("")
    lines.append(f"- Small-model lift score: `{payload['summary'].get('small_model_lift_score')}`")
    lines.append(f"- Recommendation: `{payload['summary'].get('recommendation')}`")
    return "\n".join(lines) + "\n"


def _avg(rows: list[dict[str, Any]], key: str) -> float:
    values = [float(row[key]) for row in rows if isinstance(row.get(key), (int, float))]
    return round(sum(values) / len(values), 4) if values else 0.0


def _delta(after: Any, before: Any) -> float | None:
    if not isinstance(after, (int, float)) or not isinstance(before, (int, float)):
        return None
    return round(float(after) - float(before), 4)


if __name__ == "__main__":
    raise SystemExit(main())
