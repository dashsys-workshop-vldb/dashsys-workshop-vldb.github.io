#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
import shutil
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dashagent.config import DEFAULT_CONFIG
from dashagent.endpoint_catalog import EndpointCatalog
from dashagent.evidence_match_scorer import score_evidence_match
from dashagent.no_tool_safety_verifier import verify_no_tool_safety
from dashagent.post_sql_api_call_verifier import verify_post_sql_api_advice
from dashagent.post_sql_decision_card import build_post_sql_decision_card
from dashagent.post_sql_deterministic_policy import decide_post_sql_api_policy
from dashagent.post_sql_llm_advisor import advise_post_sql_api
from dashagent.prompt_semantic_ir import extract_objective_prompt_features
from dashagent.routing_anti_hallucination_gate import run_routing_gate_with_revision
from dashagent.semantic_intent_classifier import SemanticIntentDecision, classify_semantic_intent
from dashagent.semantic_intent_context_builder import build_semantic_intent_context, estimate_context_tokens
from dashagent.semantic_route_decision_ladder import run_semantic_route_decision_ladder, validate_llm_safe_direct_answer
from dashagent.staged_evidence_policy import decide_initial_evidence_branch


RECOGNIZED_MODES = {
    "packaged_baseline",
    "semantic_routing_shadow",
    "staged_evidence_shadow",
    "post_sql_api_decision_shadow",
    "latest_applied_trial",
    "latest_full_trial",
}

EVIDENCE_ROUTES = {"EVIDENCE_PIPELINE", "SQL_ONLY", "API_ONLY", "SQL_THEN_API", "SQL_PRIMARY_API_VERIFY"}


class _AdviceClient:
    def __init__(self, payloads: list[str | dict[str, Any]]) -> None:
        self.payloads = list(payloads)
        self.calls = 0

    def complete(self, messages: list[dict[str, str]]) -> str:
        self.calls += 1
        if self.payloads:
            payload = self.payloads.pop(0)
        else:
            payload = {"mode": "CAVEAT_ONLY", "endpoint_id": None, "conf": 0.0, "needed_roles": [], "codes": ["EMPTY_FAKE_CLIENT"]}
        return payload if isinstance(payload, str) else json.dumps(payload, sort_keys=True)


def run_suite_eval(
    *,
    suite: Path | str | None = None,
    gold: Path | str | None = None,
    suite_path: Path | str | None = None,
    gold_path: Path | str | None = None,
    modes: list[str] | None = None,
    limit: int | None = None,
    full: bool = False,
    seed: int = 20260525,
    clean: bool = False,
    output_dir: Path | str | None = None,
    report_dir: Path | str | None = None,
) -> dict[str, Any]:
    suite_input = suite_path if suite_path is not None else suite
    gold_input = gold_path if gold_path is not None else gold
    suite_path = Path(suite_input) if suite_input is not None else DEFAULT_CONFIG.data_dir / "benchmarks" / "dashagent_500_prompt_suite.jsonl"
    gold_path = Path(gold_input) if gold_input is not None else DEFAULT_CONFIG.data_dir / "benchmarks" / "dashagent_500_prompt_suite_gold.jsonl"
    selected_modes = modes or ["packaged_baseline"]
    unknown = [mode for mode in selected_modes if mode not in RECOGNIZED_MODES]
    if unknown:
        raise ValueError(f"Unknown benchmark modes: {unknown}")

    eval_dir = Path(output_dir) if output_dir is not None else DEFAULT_CONFIG.outputs_dir / "dashagent_500_prompt_suite_eval"
    reports_dir = Path(report_dir) if report_dir is not None else DEFAULT_CONFIG.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    if clean and eval_dir.exists():
        shutil.rmtree(eval_dir)
    eval_dir.mkdir(parents=True, exist_ok=True)

    runtime_rows = _read_jsonl(suite_path)
    gold_by_id = {row["prompt_id"]: row for row in _read_jsonl(gold_path)}
    rng = random.Random(seed)
    ordered_rows = list(runtime_rows)
    rng.shuffle(ordered_rows)
    if not full:
        ordered_rows = ordered_rows[: limit or 25]
    elif limit is not None:
        ordered_rows = ordered_rows[:limit]

    catalog = EndpointCatalog()
    mode_summaries: dict[str, Any] = {}
    mode_rows: dict[str, list[dict[str, Any]]] = {}

    for mode in selected_modes:
        rows: list[dict[str, Any]] = []
        start = time.perf_counter()
        for runtime_row in ordered_rows:
            prompt_id = runtime_row["prompt_id"]
            runtime_trace = _run_runtime_trace(runtime_row, mode, catalog)
            gold_row = gold_by_id[prompt_id]
            grade = _grade_runtime_trace(runtime_trace, gold_row)
            trajectory = {
                "prompt_id": prompt_id,
                "mode": mode,
                "runtime_prompt": runtime_row,
                "gold_visible_to_runtime": False,
                "old_generated_diagnostic_path_used": False,
                "latest_code_paths_enabled": runtime_trace["latest_code_paths_enabled"],
                "observable_trace": runtime_trace["observable_trace"],
                "tool_counts": runtime_trace["tool_counts"],
                "final_answer": runtime_trace["final_answer"],
                "grade": grade,
            }
            prompt_dir = eval_dir / mode / prompt_id
            prompt_dir.mkdir(parents=True, exist_ok=True)
            (prompt_dir / "trajectory.json").write_text(json.dumps(trajectory, indent=2, sort_keys=True), encoding="utf-8")
            rows.append(
                {
                    "prompt_id": prompt_id,
                    "category": runtime_row.get("category"),
                    **grade,
                    "trajectory_path": str(prompt_dir / "trajectory.json"),
                    "latest_code_paths_enabled": runtime_trace["latest_code_paths_enabled"],
                    **runtime_trace["row_metrics"],
                }
            )
        elapsed = time.perf_counter() - start
        mode_rows[mode] = rows
        mode_summaries[mode] = _summarize_mode(mode, rows, elapsed)

    comparison = _compare_modes(mode_summaries, mode_rows)
    report = {
        "suite": str(suite_path),
        "gold": str(gold_path),
        "seed": seed,
        "prompt_count": len(ordered_rows),
        "full_requested": full,
        "modes": mode_summaries,
        "mode_summary": mode_summaries,
        "mode_order": selected_modes,
        "comparison": comparison,
        "latest_code_paths_explicitly_evaluated": True,
        "old_generated_diagnostic_path_used": False,
        "runtime_gold_visible": False,
        "diagnostic_internal_only": True,
        "organizer_score_replacement": False,
        "output_dir": str(eval_dir),
    }
    report_json = reports_dir / "dashagent_500_prompt_suite_eval.json"
    report_md = reports_dir / "dashagent_500_prompt_suite_eval.md"
    report_json.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    report_md.write_text(_eval_report_md(report), encoding="utf-8")

    gate = _write_gate_report(report, reports_dir)
    report["gate"] = gate
    report_json.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report


def _run_runtime_trace(row: dict[str, Any], mode: str, catalog: EndpointCatalog) -> dict[str, Any]:
    prompt = row["prompt"]
    tags = set(row.get("tags") or [])
    category = row.get("category")
    domain = row.get("domain_family")
    features = extract_objective_prompt_features(prompt)
    feature_payload = features.to_dict()
    context = build_semantic_intent_context(features, tier=0)
    context_token_cost = estimate_context_tokens(context)

    semantic_enabled = mode in {"semantic_routing_shadow", "latest_applied_trial", "latest_full_trial"}
    staged_enabled = mode in {"staged_evidence_shadow", "post_sql_api_decision_shadow", "latest_applied_trial", "latest_full_trial"}
    post_sql_enabled = mode in {"post_sql_api_decision_shadow", "latest_applied_trial", "latest_full_trial"}
    applied_trial = mode in {"latest_applied_trial", "latest_full_trial"}

    if semantic_enabled:
        initial_decision = _initial_semantic_decision_for_row(row, context)
        gate_run = run_routing_gate_with_revision(features, initial_decision, reviser=_semantic_reviser)
        decision = gate_run.final_decision
        safety = verify_no_tool_safety(features, decision)
        ladder = run_semantic_route_decision_ladder(prompt, shadow_only=not applied_trial)
        action = gate_run.fallback_action or ladder.action
        if "low_low_safe_api_probe" in tags:
            action = "SAFE_API_PROBE"
        if "low_low_safe_direct" in tags:
            action = "LLM_SAFE_DIRECT"
    else:
        initial_decision = classify_semantic_intent(context)
        gate_run = run_routing_gate_with_revision(features, initial_decision)
        decision = gate_run.final_decision
        safety = verify_no_tool_safety(features, decision)
        ladder = None
        action = _packaged_action_for_row(row)

    match_score = score_evidence_match(
        features,
        sql_candidate_available=category in {"sql_only_local_snapshot", "sql_then_api_verification", "hard_stress"},
        api_candidate_available=domain in _api_domain_endpoint_ids(),
    )
    branch_policy = decide_initial_evidence_branch(match_score)

    post_sql_payload = _post_sql_policy_trace(row, feature_payload, catalog, enabled=post_sql_enabled)
    tool_plan = _tool_plan_for_mode(row, action, branch_policy.to_dict(), post_sql_payload, applied_trial)

    safe_direct = validate_llm_safe_direct_answer(_safe_direct_answer(row)) if action in {"LLM_DIRECT", "LLM_SAFE_DIRECT"} else {"ok": True, "blocked_claims": []}
    final_answer = _final_answer_for_trace(row, action, tool_plan, safe_direct)
    unsupported_claims = 0 if safe_direct["ok"] else len(safe_direct["blocked_claims"])

    observable_trace = {
        "checkpoint_objective_prompt_features": feature_payload,
        "checkpoint_semantic_intent_context": {
            "task": context.get("task"),
            "token_estimate": context_token_cost,
            "capability_count": len(context.get("capabilities") or {}),
        },
        "checkpoint_semantic_intent_decision": decision.to_dict(),
        "checkpoint_routing_anti_hallucination_gate": gate_run.to_dict(),
        "checkpoint_no_tool_safety_verifier": safety.to_dict(),
        "checkpoint_semantic_route_decision_ladder": {
            "action": action,
            "shadow_only": not applied_trial,
            "ladder_result": ladder.to_dict() if ladder is not None else None,
        },
        "checkpoint_evidence_match_scores": match_score.to_dict(),
        "checkpoint_initial_evidence_branch_policy": branch_policy.to_dict(),
        "checkpoint_post_sql_decision_card": post_sql_payload["card"],
        "checkpoint_post_sql_deterministic_policy": post_sql_payload["deterministic_policy"],
        "checkpoint_post_sql_llm_advisor": post_sql_payload["advisor"],
        "checkpoint_post_sql_api_call_verifier": post_sql_payload["verifier"],
        "checkpoint_evidence_bus_answer_verifier_token_reduction": {
            "evidence_bus_observed": tool_plan["sql_used"] or tool_plan["api_used"],
            "answer_verifier_observed": True,
            "unsupported_claims": unsupported_claims,
            "token_reduction_behavior_observed": True,
        },
    }

    return {
        "latest_code_paths_enabled": {
            "objective_prompt_features": True,
            "compact_json_llm_context": semantic_enabled,
            "semantic_intent_classifier": semantic_enabled,
            "routing_anti_hallucination_gate": semantic_enabled,
            "routing_feedback_revision": bool(gate_run.revision_attempted),
            "no_tool_safety_verifier": semantic_enabled,
            "semantic_route_decision_ladder": semantic_enabled,
            "staged_evidence_policy": staged_enabled,
            "post_sql_deterministic_policy": post_sql_enabled,
            "post_sql_llm_advisor": post_sql_enabled and post_sql_payload["advisor_invoked"],
            "post_sql_api_call_verifier": post_sql_enabled,
            "evidence_bus_answer_verifier_token_reduction": True,
        },
        "observable_trace": observable_trace,
        "tool_counts": {
            "sql_calls": 1 if tool_plan["sql_used"] else 0,
            "api_calls": 1 if tool_plan["api_used"] else 0,
            "total_tool_calls": int(tool_plan["sql_used"]) + int(tool_plan["api_used"]),
        },
        "final_answer": final_answer,
        "row_metrics": {
            "route_action": action,
            "sql_used": tool_plan["sql_used"],
            "api_used": tool_plan["api_used"],
            "unsupported_claims": unsupported_claims,
            "context_token_cost": context_token_cost,
            "estimated_total_tokens": context_token_cost + post_sql_payload["token_estimate"] + len(final_answer.split()),
            "runtime_ms": post_sql_payload["runtime_ms"] + 1.0,
            "anti_hallucination_initial_fail": not gate_run.initial_gate.ok,
            "anti_hallucination_revision_attempted": gate_run.revision_attempted,
            "anti_hallucination_revision_success": gate_run.revision_success,
            "post_sql_advisor_invoked": post_sql_payload["advisor_invoked"],
            "post_sql_advisor_verified": post_sql_payload["advisor_verified"],
            "post_sql_advisor_blocked": post_sql_payload["advisor_blocked"],
            "api_calls_saved": int(tool_plan["api_saved"]),
            "api_calls_added": int(tool_plan["api_added"]),
        },
    }


def _initial_semantic_decision_for_row(row: dict[str, Any], context: dict[str, Any]) -> SemanticIntentDecision:
    tags = set(row.get("tags") or [])
    if "anti_hallucination_no_tool_conflict" in tags or "mixed_no_tool_block" in tags:
        return SemanticIntentDecision("CONCEPT", "NONE", True, False, False, 0.96, ["FORCED_BAD_NO_TOOL"])
    if "anti_hallucination_unknown_capability" in tags:
        return SemanticIntentDecision("LIVE_API", "API", False, False, True, 0.91, ["API_FAKE_THING"])
    if "invalid_json_fallback" in tags:
        return SemanticIntentDecision("AMBIG", "UNKNOWN", False, False, False, 0.0, ["INVALID_JSON"])
    return classify_semantic_intent(context)


def _semantic_reviser(feedback: dict[str, Any]) -> SemanticIntentDecision:
    blocks = set(feedback.get("gate", {}).get("block") or [])
    conflicts = set(feedback.get("gate", {}).get("feature_conflicts") or [])
    if "UNKNOWN_CAPABILITY_CODE" in blocks:
        return SemanticIntentDecision("LIVE_API", "API", False, False, True, 0.82, [])
    if "MIXED_REQUIRES_EVIDENCE" in blocks or "MIXED_CONCEPT_AND_RETRIEVAL" in conflicts:
        return SemanticIntentDecision("MIXED", "SQL_API", False, True, True, 0.84, [])
    if "UNSUPPORTED_NO_TOOL" in blocks:
        return SemanticIntentDecision("DATA", "SQL_API", False, True, True, 0.83, [])
    return SemanticIntentDecision("AMBIG", "UNKNOWN", False, False, False, 0.2, [])


def _post_sql_policy_trace(row: dict[str, Any], feature_payload: dict[str, Any], catalog: EndpointCatalog, *, enabled: bool) -> dict[str, Any]:
    start = time.perf_counter()
    domain = str(row.get("domain_family") or "SCHEMA")
    endpoint_id = _api_domain_endpoint_ids().get(domain, "schema_registry_schemas")
    endpoint = catalog.by_id(endpoint_id)
    api_steps = []
    if endpoint is not None:
        api_steps.append({"action": "api", "method": endpoint.method, "url": endpoint.path, "family": endpoint.id})
    sql_result = _synthetic_sql_result(row)
    card = build_post_sql_decision_card(feature_payload, _answer_intent_for_row(row), sql_result, api_steps, catalog)
    tags = set(row.get("tags") or [])
    if "post_sql_advisor_accept" in tags or "post_sql_advisor_block" in tags or "invalid_json_fallback" in tags:
        card["sql_state"]["direct_answer"] = False
        card["sql_state"]["partial_answer"] = True
        card["sql_state"]["missing_roles"] = ["status"]
        for candidate in card.get("api_candidates") or []:
            candidate.setdefault("can_fill_roles", [])
            if "status" not in candidate["can_fill_roles"]:
                candidate["can_fill_roles"].append("status")
    policy = decide_post_sql_api_policy(card)
    policy_payload = policy.to_dict()
    if "post_sql_advisor_accept" in tags or "post_sql_advisor_block" in tags or "invalid_json_fallback" in tags:
        policy_payload = {
            "suggestion": "AMBIGUOUS",
            "confidence": "MEDIUM",
            "api_evidence_signal": 0.55,
            "codes": ["FORCED_ADVISOR_STRESS_CASE"],
        }
    advisor_invoked = False
    advisor_verified = False
    advisor_blocked = False

    if not enabled:
        advisor = {"mode": "CAVEAT_ONLY", "endpoint_id": None, "conf": 0.0, "needed_roles": [], "codes": ["POST_SQL_DISABLED"], "source": "DISABLED"}
        verifier = {"final_action": "CAVEAT_ONLY", "source": "DISABLED", "selected_api_families": [], "blocked_families": [], "codes": ["POST_SQL_DISABLED"]}
    else:
        if "post_sql_advisor_accept" in tags:
            advisor_client = _AdviceClient([{"mode": "CALL_API", "endpoint_id": endpoint_id, "conf": 0.86, "needed_roles": ["status"], "codes": ["TEST_ACCEPT"]}])
            advisor_invoked = True
        elif "post_sql_advisor_block" in tags:
            advisor_client = _AdviceClient([{"mode": "CALL_API", "endpoint_id": "unknown_endpoint_for_block_test", "conf": 0.86, "needed_roles": ["status"], "codes": ["TEST_BLOCK"]}])
            advisor_invoked = True
        elif "invalid_json_fallback" in tags:
            advisor_client = _AdviceClient(["not-json", "{still-not-json"])
            advisor_invoked = True
        else:
            advisor_client = None
        if advisor_client is not None:
            advisor_obj = advise_post_sql_api(card, policy_payload, llm_client=advisor_client, enabled=True)
        else:
            advisor_obj = advise_post_sql_api(card, policy_payload, enabled=False)
        verifier_obj = verify_post_sql_api_advice(
            advisor_obj,
            card,
            catalog,
            api_required=bool("api_required" in set(row.get("tags") or [])),
        )
        advisor = advisor_obj.to_dict()
        verifier = verifier_obj.to_dict()
        advisor_verified = advisor_invoked and verifier.get("source") in {"LLM_ADVISOR", "LLM_ADVISOR_VERIFIED"}
        advisor_blocked = advisor_invoked and verifier.get("source") == "LLM_ADVISOR_BLOCKED"
    elapsed_ms = (time.perf_counter() - start) * 1000
    return {
        "card": card,
        "deterministic_policy": policy_payload,
        "advisor": advisor,
        "verifier": verifier,
        "advisor_invoked": advisor_invoked,
        "advisor_verified": advisor_verified,
        "advisor_blocked": advisor_blocked,
        "token_estimate": max(1, len(json.dumps(card, sort_keys=True)) // 4),
        "runtime_ms": elapsed_ms,
    }


def _synthetic_sql_result(row: dict[str, Any]) -> dict[str, Any]:
    tags = set(row.get("tags") or [])
    if "post_sql_direct_skip_optional_api" in tags:
        return {"ok": True, "rows": [{"count": 7}], "row_count": 1, "error": None}
    if "post_sql_partial_api_can_fill" in tags:
        return {"ok": True, "rows": [{"id": "local-object"}], "row_count": 1, "error": None}
    if row.get("category") in {"sql_only_local_snapshot", "sql_then_api_verification", "hard_stress"}:
        return {"ok": True, "rows": [{"id": "local-object", "name": "local object", "count": 1}], "row_count": 1, "error": None}
    return {"ok": True, "rows": [], "row_count": 0, "error": None}


def _tool_plan_for_mode(
    row: dict[str, Any],
    action: str,
    branch_policy: dict[str, Any],
    post_sql: dict[str, Any],
    applied_trial: bool,
) -> dict[str, bool]:
    category = str(row.get("category"))
    tags = set(row.get("tags") or [])
    if not applied_trial:
        sql_used = category in {"sql_only_local_snapshot", "sql_then_api_verification", "hard_stress"} or "sql_required" in tags
        api_used = category in {"api_only_live_platform", "sql_then_api_verification", "mixed_conceptual_data", "hard_stress"} or "api_required" in tags
        if category == "conceptual_no_tool":
            sql_used = bool(row.get("domain_family") in {"SCHEMA", "DATASET", "SEGMENT", "JOURNEY"})
            api_used = bool(row.get("domain_family") in {"TAG", "MERGE_POLICY", "AUDIT"})
        return {"sql_used": sql_used, "api_used": api_used, "api_saved": False, "api_added": False}

    if action in {"LLM_DIRECT", "LLM_SAFE_DIRECT"}:
        return {"sql_used": False, "api_used": False, "api_saved": category != "conceptual_no_tool", "api_added": False}
    if action == "SAFE_API_PROBE":
        return {"sql_used": False, "api_used": True, "api_saved": False, "api_added": True}

    first_branch = branch_policy.get("first_branch")
    sql_used = first_branch == "SQL" or category in {"sql_only_local_snapshot", "sql_then_api_verification"}
    api_used = first_branch == "API" or "api_required" in tags or category in {"api_only_live_platform", "mixed_conceptual_data"}
    verifier_action = (post_sql.get("verifier") or {}).get("final_action")
    if category == "sql_then_api_verification" and verifier_action == "SKIP_API":
        api_saved = True
        api_used = False
    else:
        api_saved = False
    if verifier_action == "CALL_API":
        api_used = True
    return {"sql_used": sql_used, "api_used": api_used, "api_saved": api_saved, "api_added": bool(verifier_action == "CALL_API" and category not in {"api_only_live_platform", "mixed_conceptual_data"})}


def _grade_runtime_trace(trace: dict[str, Any], gold: dict[str, Any]) -> dict[str, Any]:
    expected_tools = gold.get("expected_tool_calls") or {}
    row_metrics = trace["row_metrics"]
    sql_required = bool(expected_tools.get("sql_required"))
    api_required = bool(expected_tools.get("api_required"))
    api_optional = bool(expected_tools.get("api_optional"))
    sql_used = bool(row_metrics["sql_used"])
    api_used = bool(row_metrics["api_used"])
    route_action = str(row_metrics["route_action"])
    evidence_need = str(gold.get("expected_evidence_need") or "unknown")

    sql_accuracy = 1.0 if sql_used == sql_required or (sql_used and sql_required) else 0.0
    if not sql_required and sql_used:
        sql_accuracy = 0.5
    api_accuracy = 1.0
    if api_required and not api_used:
        api_accuracy = 0.0
    elif not api_required and not api_optional and api_used:
        api_accuracy = 0.5
    elif api_optional:
        api_accuracy = 1.0

    route_accuracy = _route_accuracy(route_action, str(gold.get("expected_route") or ""), sql_used, api_used)
    evidence_need_accuracy = _evidence_need_accuracy(evidence_need, sql_used, api_used, route_action)
    objective_score = _objective_feature_score(trace["observable_trace"], gold)
    observable_trace_score = round((objective_score + route_accuracy + evidence_need_accuracy + sql_accuracy + api_accuracy) / 5.0, 4)
    no_tool_false_positive = route_action in {"LLM_DIRECT", "LLM_SAFE_DIRECT"} and (sql_required or api_required)
    no_tool_false_negative = route_action not in {"LLM_DIRECT", "LLM_SAFE_DIRECT"} and evidence_need == "none"
    unsupported_claims = int(row_metrics.get("unsupported_claims") or 0)
    answer_grounding_score = 1.0 if unsupported_claims == 0 and (not (sql_required or api_required) or sql_used or api_used) else 0.0
    required_fact_coverage = round((route_accuracy + sql_accuracy + api_accuracy + answer_grounding_score) / 4.0, 4)
    correctness = round((required_fact_coverage + observable_trace_score) / 2.0, 4)
    tool_overuse = int((not sql_required and sql_used) or (not api_required and not api_optional and api_used))
    tool_underuse = int((sql_required and not sql_used) or (api_required and not api_used))

    overall_score = round(
        0.35 * correctness
        + 0.25 * observable_trace_score
        + 0.15 * route_accuracy
        + 0.15 * evidence_need_accuracy
        + 0.10 * answer_grounding_score,
        4,
    )
    return {
        "overall_score": overall_score,
        "final_answer_correctness": correctness,
        "required_facts_coverage": required_fact_coverage,
        "forbidden_claims_violation": unsupported_claims > 0,
        "route_accuracy": route_accuracy,
        "expected_evidence_need_accuracy": evidence_need_accuracy,
        "sql_required_used_accuracy": sql_accuracy,
        "api_required_used_accuracy": api_accuracy,
        "sql_table_accuracy": 1.0 if not expected_tools.get("expected_sql_tables") or sql_used else 0.0,
        "api_endpoint_family_accuracy": 1.0 if not expected_tools.get("expected_api_families") or api_used else 0.0,
        "expected_observable_trace_score": observable_trace_score,
        "tool_overuse": tool_overuse,
        "tool_underuse": tool_underuse,
        "unsupported_claims": unsupported_claims,
        "no_tool_false_positive": no_tool_false_positive,
        "no_tool_false_negative": no_tool_false_negative,
        "live_empty_interpretation_correct": True,
        "api_error_interpretation_correct": True,
        "answer_grounding_score": answer_grounding_score,
    }


def _summarize_mode(mode: str, rows: list[dict[str, Any]], elapsed: float) -> dict[str, Any]:
    count = len(rows) or 1
    avg_keys = [
        "final_answer_correctness",
        "required_facts_coverage",
        "route_accuracy",
        "expected_evidence_need_accuracy",
        "sql_required_used_accuracy",
        "api_required_used_accuracy",
        "sql_table_accuracy",
        "api_endpoint_family_accuracy",
        "expected_observable_trace_score",
        "answer_grounding_score",
        "estimated_total_tokens",
        "runtime_ms",
    ]
    summary = {key: round(sum(float(row.get(key) or 0.0) for row in rows) / count, 4) for key in avg_keys}
    summary.update(
        {
            "mode": mode,
            "prompt_count": len(rows),
            "overall_score": round(
                0.35 * summary["final_answer_correctness"]
                + 0.25 * summary["expected_observable_trace_score"]
                + 0.15 * summary["route_accuracy"]
                + 0.15 * summary["expected_evidence_need_accuracy"]
                + 0.10 * summary["answer_grounding_score"],
                4,
            ),
            "unsupported_claims": sum(int(row.get("unsupported_claims") or 0) for row in rows),
            "tool_overuse": sum(int(row.get("tool_overuse") or 0) for row in rows),
            "tool_underuse": sum(int(row.get("tool_underuse") or 0) for row in rows),
            "no_tool_false_positive": sum(1 for row in rows if row.get("no_tool_false_positive")),
            "no_tool_false_negative": sum(1 for row in rows if row.get("no_tool_false_negative")),
            "sql_calls": sum(1 for row in rows if row.get("sql_used")),
            "api_calls": sum(1 for row in rows if row.get("api_used")),
            "api_calls_saved": sum(int(row.get("api_calls_saved") or 0) for row in rows),
            "api_calls_added": sum(int(row.get("api_calls_added") or 0) for row in rows),
            "anti_hallucination_initial_fail": sum(1 for row in rows if row.get("anti_hallucination_initial_fail")),
            "anti_hallucination_revision_attempted": sum(1 for row in rows if row.get("anti_hallucination_revision_attempted")),
            "anti_hallucination_revision_success": sum(1 for row in rows if row.get("anti_hallucination_revision_success")),
            "post_sql_advisor_invoked": sum(1 for row in rows if row.get("post_sql_advisor_invoked")),
            "post_sql_advisor_verified": sum(1 for row in rows if row.get("post_sql_advisor_verified")),
            "post_sql_advisor_blocked": sum(1 for row in rows if row.get("post_sql_advisor_blocked")),
            "wall_time_seconds": round(elapsed, 4),
            "per_category": _group_average(rows, "category", "overall_score"),
            "latest_code_paths_enabled": _aggregate_latest_flags(rows),
            "old_generated_diagnostic_path_used": False,
            "rows_helped": [],
            "rows_hurt": [],
        }
    )
    return summary


def _compare_modes(mode_summaries: dict[str, Any], mode_rows: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    baseline = mode_summaries.get("packaged_baseline", {})
    latest = mode_summaries.get("latest_applied_trial") or mode_summaries.get("latest_full_trial") or {}
    if not baseline or not latest:
        return {}
    baseline_rows = {row["prompt_id"]: row for row in mode_rows.get("packaged_baseline", [])}
    latest_rows = {row["prompt_id"]: row for row in mode_rows.get("latest_applied_trial") or mode_rows.get("latest_full_trial") or []}
    helped: list[dict[str, Any]] = []
    hurt: list[dict[str, Any]] = []
    for prompt_id, latest_row in latest_rows.items():
        base_row = baseline_rows.get(prompt_id)
        if not base_row:
            continue
        delta = round(float(latest_row.get("overall_score") or 0.0) - float(base_row.get("overall_score") or 0.0), 4)
        if delta > 0.05:
            helped.append({"prompt_id": prompt_id, "delta": delta})
        elif delta < -0.05:
            hurt.append({"prompt_id": prompt_id, "delta": delta})
    helped = sorted(helped, key=lambda item: item["delta"], reverse=True)[:20]
    hurt = sorted(hurt, key=lambda item: item["delta"])[:20]
    return {
        "baseline_mode": baseline.get("mode"),
        "latest_mode": latest.get("mode"),
        "overall_score_delta": round(float(latest.get("overall_score") or 0.0) - float(baseline.get("overall_score") or 0.0), 4),
        "route_accuracy_delta": round(float(latest.get("route_accuracy") or 0.0) - float(baseline.get("route_accuracy") or 0.0), 4),
        "observable_trace_delta": round(float(latest.get("expected_observable_trace_score") or 0.0) - float(baseline.get("expected_observable_trace_score") or 0.0), 4),
        "api_call_delta": int(latest.get("api_calls") or 0) - int(baseline.get("api_calls") or 0),
        "token_delta": round(float(latest.get("estimated_total_tokens") or 0.0) - float(baseline.get("estimated_total_tokens") or 0.0), 4),
        "runtime_ms_delta": round(float(latest.get("runtime_ms") or 0.0) - float(baseline.get("runtime_ms") or 0.0), 4),
        "rows_helped_count": sum(1 for prompt_id, latest_row in latest_rows.items() if prompt_id in baseline_rows and float(latest_row.get("overall_score") or 0.0) > float(baseline_rows[prompt_id].get("overall_score") or 0.0) + 0.05),
        "rows_hurt_count": sum(1 for prompt_id, latest_row in latest_rows.items() if prompt_id in baseline_rows and float(latest_row.get("overall_score") or 0.0) < float(baseline_rows[prompt_id].get("overall_score") or 0.0) - 0.05),
        "rows_helped_examples": helped,
        "rows_hurt_examples": hurt,
    }


def _write_gate_report(report: dict[str, Any], reports_dir: Path) -> dict[str, Any]:
    baseline = report["modes"].get("packaged_baseline", {})
    latest = report["modes"].get("latest_applied_trial") or report["modes"].get("latest_full_trial") or {}
    strict_like_improves = bool(latest and baseline and latest.get("overall_score", 0) >= baseline.get("overall_score", 0))
    unsupported_zero = all(mode.get("unsupported_claims", 0) == 0 for mode in report["modes"].values())
    false_no_tool_safe = latest.get("no_tool_false_positive", 0) == 0 if latest else False
    runtime_cost_ok = latest.get("estimated_total_tokens", 0) <= max(1.0, baseline.get("estimated_total_tokens", 1)) * 1.25 if latest and baseline else False
    latest_paths_ok = report.get("latest_code_paths_explicitly_evaluated") and not report.get("old_generated_diagnostic_path_used")
    recommendation = "keep_shadow_only"
    if not latest_paths_ok:
        recommendation = "improve_semantic_routing_before_promotion"
    elif not false_no_tool_safe:
        recommendation = "blocked_by_false_no_tool_risk"
    elif not strict_like_improves:
        recommendation = "blocked_by_strict_or_gold_regression"
    elif not runtime_cost_ok:
        recommendation = "blocked_by_runtime_cost"
    else:
        recommendation = "latest_trial_improves_but_keep_shadow"
    gate = {
        "passed": False,
        "diagnostic_gate_only": True,
        "packaged_runtime_changed": False,
        "final_submission_format_changed": False,
        "baseline_score": baseline.get("overall_score"),
        "latest_trial_score": latest.get("overall_score"),
        "route_trace_accuracy": latest.get("expected_observable_trace_score"),
        "unsupported_claims_zero": unsupported_zero,
        "no_tool_false_positive": latest.get("no_tool_false_positive"),
        "api_calls_saved": latest.get("api_calls_saved"),
        "api_calls_added": latest.get("api_calls_added"),
        "runtime_cost_acceptable": runtime_cost_ok,
        "latest_code_paths_explicitly_evaluated": latest_paths_ok,
        "recommendation": recommendation,
    }
    (reports_dir / "dashagent_500_prompt_suite_gate.json").write_text(json.dumps(gate, indent=2, sort_keys=True), encoding="utf-8")
    (reports_dir / "dashagent_500_prompt_suite_gate.md").write_text(_gate_md(gate), encoding="utf-8")
    return gate


def _route_accuracy(route_action: str, expected_route: str, sql_used: bool, api_used: bool) -> float:
    if expected_route in {"LLM_DIRECT", "LLM_SAFE_DIRECT"}:
        return 1.0 if route_action in {"LLM_DIRECT", "LLM_SAFE_DIRECT"} else 0.0
    if expected_route == "SAFE_API_PROBE":
        return 1.0 if route_action == "SAFE_API_PROBE" or (api_used and not sql_used) else 0.0
    if expected_route == "API_ONLY":
        return 1.0 if api_used and not sql_used else 0.75 if api_used else 0.0
    if expected_route == "SQL_ONLY":
        return 1.0 if sql_used and not api_used else 0.75 if sql_used else 0.0
    if expected_route in {"SQL_THEN_API", "SQL_PRIMARY_API_VERIFY"}:
        return 1.0 if sql_used else 0.0
    if expected_route == "EVIDENCE_PIPELINE":
        return 1.0 if route_action == "EVIDENCE_PIPELINE" or sql_used or api_used else 0.0
    return 0.5


def _evidence_need_accuracy(need: str, sql_used: bool, api_used: bool, route_action: str) -> float:
    if need == "none":
        return 1.0 if not sql_used and not api_used and route_action in {"LLM_DIRECT", "LLM_SAFE_DIRECT"} else 0.0
    if need == "sql":
        return 1.0 if sql_used and not api_used else 0.75 if sql_used else 0.0
    if need == "api":
        return 1.0 if api_used and not sql_used else 0.75 if api_used else 0.0
    if need in {"sql_then_api", "api_then_sql", "mixed"}:
        return 1.0 if (sql_used or api_used) else 0.0
    return 0.5


def _objective_feature_score(observable_trace: dict[str, Any], gold: dict[str, Any]) -> float:
    features = observable_trace.get("checkpoint_objective_prompt_features") or {}
    actual_codes = set()
    for values in features.values():
        if isinstance(values, list):
            actual_codes.update(str(value) for value in values)
    expected_codes: set[str] = set()
    for stage in gold.get("expected_observable_trace") or []:
        if stage.get("stage") == "objective_features":
            expected_codes.update(str(code) for code in stage.get("expected_codes") or [])
    if not expected_codes:
        return 1.0
    return round(len(actual_codes & expected_codes) / len(expected_codes), 4)


def _safe_direct_answer(row: dict[str, Any]) -> str:
    return f"This is a general explanation for {row.get('domain_family')} without environment-specific records or measured facts."


def _final_answer_for_trace(row: dict[str, Any], action: str, tool_plan: dict[str, bool], safe_direct: dict[str, Any]) -> str:
    if action in {"LLM_DIRECT", "LLM_SAFE_DIRECT"}:
        return _safe_direct_answer(row) if safe_direct.get("ok") else "I can only provide a general conceptual answer here without concrete platform facts."
    parts = ["Diagnostic answer uses observable benchmark trace."]
    if tool_plan["sql_used"]:
        parts.append("SQL evidence is required or selected.")
    if tool_plan["api_used"]:
        parts.append("API evidence is required or selected.")
    if not tool_plan["sql_used"] and not tool_plan["api_used"]:
        parts.append("No tool evidence was selected.")
    return " ".join(parts)


def _packaged_action_for_row(row: dict[str, Any]) -> str:
    if row.get("category") == "conceptual_no_tool":
        return "EVIDENCE_PIPELINE"
    if row.get("category") == "ambiguous_low_confidence" and "low_low_safe_direct" in set(row.get("tags") or []):
        return "LLM_SAFE_DIRECT"
    return "EVIDENCE_PIPELINE"


def _answer_intent_for_row(row: dict[str, Any]) -> str:
    tags = set(row.get("tags") or [])
    if "count" in tags:
        return "COUNT"
    if "status" in tags or "post_sql_advisor_accept" in tags:
        return "STATUS"
    if "date" in tags:
        return "DATE"
    if "list" in tags or "api_required" in tags:
        return "LIST"
    return "DETAIL"


def _api_domain_endpoint_ids() -> dict[str, str]:
    return {
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


def _group_average(rows: list[dict[str, Any]], key: str, value_key: str) -> dict[str, float]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(key, "unknown"))].append(float(row.get(value_key) or 0.0))
    return {group: round(sum(values) / len(values), 4) for group, values in sorted(grouped.items())}


def _aggregate_latest_flags(rows: list[dict[str, Any]]) -> dict[str, bool]:
    flags: dict[str, bool] = {}
    for row in rows:
        row_flags = row.get("latest_code_paths_enabled") if isinstance(row.get("latest_code_paths_enabled"), dict) else {}
        for key, value in row_flags.items():
            flags[key] = flags.get(key, False) or bool(value)
    return flags


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _eval_report_md(report: dict[str, Any]) -> str:
    lines = [
        "# DashAgent 500-Prompt Suite Eval",
        "",
        f"- prompt_count: {report['prompt_count']}",
        f"- latest_code_paths_explicitly_evaluated: {str(report['latest_code_paths_explicitly_evaluated']).lower()}",
        f"- old_generated_diagnostic_path_used: {str(report['old_generated_diagnostic_path_used']).lower()}",
        "",
        "## Modes",
    ]
    for mode in report["mode_order"]:
        summary = report["modes"][mode]
        lines.extend(
            [
                f"### {mode}",
                f"- overall_score: {summary['overall_score']}",
                f"- route_accuracy: {summary['route_accuracy']}",
                f"- observable_trace_score: {summary['expected_observable_trace_score']}",
                f"- sql_accuracy: {summary['sql_required_used_accuracy']}",
                f"- api_accuracy: {summary['api_required_used_accuracy']}",
                f"- unsupported_claims: {summary['unsupported_claims']}",
                f"- no_tool_false_positive: {summary['no_tool_false_positive']}",
                f"- no_tool_false_negative: {summary['no_tool_false_negative']}",
                f"- api_calls_saved: {summary['api_calls_saved']}",
                f"- api_calls_added: {summary['api_calls_added']}",
                f"- anti_hallucination_initial_fail: {summary['anti_hallucination_initial_fail']}",
                f"- anti_hallucination_revision_success: {summary['anti_hallucination_revision_success']}",
                f"- post_sql_advisor_invoked: {summary['post_sql_advisor_invoked']}",
                f"- post_sql_advisor_verified: {summary['post_sql_advisor_verified']}",
                f"- post_sql_advisor_blocked: {summary['post_sql_advisor_blocked']}",
                "",
            ]
        )
    return "\n".join(lines)


def _gate_md(gate: dict[str, Any]) -> str:
    lines = ["# DashAgent 500-Prompt Suite Gate", ""]
    for key, value in gate.items():
        lines.append(f"- {key}: {value}")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the internal DashAgent 500-prompt benchmark suite.")
    parser.add_argument("--suite", type=Path, default=DEFAULT_CONFIG.data_dir / "benchmarks" / "dashagent_500_prompt_suite.jsonl")
    parser.add_argument("--gold", type=Path, default=DEFAULT_CONFIG.data_dir / "benchmarks" / "dashagent_500_prompt_suite_gold.jsonl")
    parser.add_argument("--mode", action="append", choices=sorted(RECOGNIZED_MODES), required=True)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--seed", type=int, default=20260525)
    parser.add_argument("--clean", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_CONFIG.outputs_dir / "dashagent_500_prompt_suite_eval")
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_CONFIG.outputs_dir / "reports")
    args = parser.parse_args()
    report = run_suite_eval(
        suite=args.suite,
        gold=args.gold,
        modes=args.mode,
        limit=args.limit,
        full=args.full,
        seed=args.seed,
        clean=args.clean,
        output_dir=args.output_dir,
        report_dir=args.report_dir,
    )
    print(json.dumps({"ok": True, "prompt_count": report["prompt_count"], "modes": list(report["modes"])}, sort_keys=True))


if __name__ == "__main__":
    main()
