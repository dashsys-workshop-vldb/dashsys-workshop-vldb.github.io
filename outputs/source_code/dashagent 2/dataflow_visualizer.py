from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any

from .span_exporter import checkpoints_to_spans, research_technique_status
from .trajectory import compact_preview, redact_secrets


READABILITY_PATTERNS = ("{&quot;", "truncated_items", "preview")


def load_trajectory(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def attach_candidate_report_row(trajectory: dict[str, Any], outputs_dir: Path) -> dict[str, Any]:
    report_path = outputs_dir / "candidate_context_report.json"
    if not report_path.exists():
        return trajectory
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception:
        return trajectory
    query_id = str(trajectory.get("query_id") or "")
    query = str(trajectory.get("original_query") or trajectory.get("query") or "")
    for row in report.get("rows", []) or []:
        if str(row.get("query_id") or "") == query_id or (query and str(row.get("query") or "") == query):
            enriched = dict(trajectory)
            enriched["_candidate_context_report_row"] = row
            return enriched
    return trajectory


def attach_shadow_repair_row(trajectory: dict[str, Any], outputs_dir: Path) -> dict[str, Any]:
    report_path = outputs_dir / "shadow_repair_eval.json"
    if not report_path.exists():
        return trajectory
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception:
        return trajectory
    query_id = str(trajectory.get("query_id") or "")
    query = str(trajectory.get("original_query") or trajectory.get("query") or "")
    for row in report.get("rows", []) or []:
        if str(row.get("query_id") or "") == query_id or (query and str(row.get("query") or "") == query):
            enriched = dict(trajectory)
            enriched["_shadow_repair_eval_row"] = row
            return enriched
    return trajectory


def attach_compact_context_shadow_row(trajectory: dict[str, Any], outputs_dir: Path) -> dict[str, Any]:
    return _attach_report_row(
        trajectory,
        outputs_dir / "compact_context_shadow_eval.json",
        "_compact_context_shadow_eval_row",
    )


def attach_risk_efficiency_shadow_row(trajectory: dict[str, Any], outputs_dir: Path) -> dict[str, Any]:
    return _attach_report_row(
        trajectory,
        outputs_dir / "risk_efficiency_shadow_eval.json",
        "_risk_efficiency_shadow_eval_row",
    )


def _attach_report_row(trajectory: dict[str, Any], report_path: Path, key: str) -> dict[str, Any]:
    if not report_path.exists():
        return trajectory
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception:
        return trajectory
    query_id = str(trajectory.get("query_id") or "")
    query = str(trajectory.get("original_query") or trajectory.get("query") or "")
    for row in report.get("rows", []) or []:
        if str(row.get("query_id") or "") == query_id or (query and str(row.get("query") or "") == query):
            enriched = dict(trajectory)
            enriched[key] = row
            return enriched
    return trajectory


def extract_checkpoint_map(trajectory: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(checkpoint.get("checkpoint_id")): checkpoint
        for checkpoint in trajectory.get("checkpoints", []) or []
        if checkpoint.get("checkpoint_id")
    }


def extract_prompt_router_decision(trajectory: dict[str, Any]) -> dict[str, Any]:
    checkpoints = extract_checkpoint_map(trajectory)
    checkpoint = checkpoints.get("checkpoint_00_prompt_router") or {}
    output = checkpoint.get("output") or {}
    if isinstance(output, dict) and output:
        return output
    for step in trajectory.get("steps", []) or []:
        if step.get("kind") in {"prompt_router", "route"}:
            return step.get("decision") if isinstance(step.get("decision"), dict) else step
    route = {}
    if trajectory.get("route_type"):
        route["mode"] = trajectory.get("route_type")
    if trajectory.get("domain_type"):
        route["domain_type"] = trajectory.get("domain_type")
    return route


def extract_sql_api_steps(trajectory: dict[str, Any]) -> dict[str, Any]:
    steps = trajectory.get("steps", []) or []
    sql_calls = [step for step in steps if step.get("kind") == "sql_call"]
    api_calls = [step for step in steps if step.get("kind") == "api_call"]
    if not sql_calls and trajectory.get("llm_tool_calls"):
        sql_calls = [
            _llm_tool_call_to_step(call)
            for call in trajectory.get("llm_tool_calls", [])
            if call.get("tool_name") == "execute_sql" or call.get("tool") == "execute_sql"
        ]
        api_calls = [
            _llm_tool_call_to_step(call)
            for call in trajectory.get("llm_tool_calls", [])
            if call.get("tool_name") == "call_api" or call.get("tool") == "call_api"
        ]
    return {"sql_calls": sql_calls, "api_calls": api_calls}


def extract_prompt_to_sql_api_mapping(trajectory: dict[str, Any]) -> dict[str, Any]:
    summary = build_dataflow_summary(trajectory)
    return redact_secrets(
        {
            "prompt": summary["user_query"],
            "route": summary["route"],
            "normalization": summary["normalization"],
            "tokens": summary["tokens"],
            "context": summary["context"],
            "sql": summary["sql"],
            "api": summary["api"],
            "evidence": summary["evidence"],
            "answer": summary["answer"],
        }
    )


def build_dataflow_summary(trajectory: dict[str, Any]) -> dict[str, Any]:
    checkpoints = extract_checkpoint_map(trajectory)
    sql_api = extract_sql_api_steps(trajectory)
    sql_calls = sql_api["sql_calls"]
    api_calls = sql_api["api_calls"]
    nlp_step = _first_step(trajectory, "nlp")
    plan_step = _first_step(trajectory, "plan")
    optimizer_step = _first_step(trajectory, "optimizer")
    route = extract_prompt_router_decision(trajectory)
    first_sql = sql_calls[0] if sql_calls else {}
    first_api = api_calls[0] if api_calls else {}
    candidate_tables = _candidate_tables(checkpoints, nlp_step)
    candidate_apis = _candidate_apis(checkpoints, nlp_step)
    estimated_context_tokens = _estimated_context_tokens(trajectory)
    candidate_mode, context_mode_note = _find_context_mode(
        trajectory,
        checkpoints,
        candidate_tables,
        candidate_apis,
        estimated_context_tokens,
    )
    dry_run = _api_dry_run(api_calls)
    sql_evidence_available = _sql_evidence_available(sql_calls)
    live_api_evidence_available = _api_live_evidence(api_calls)
    evidence_available = _overall_evidence_available(trajectory, sql_calls, api_calls, sql_evidence_available, live_api_evidence_available)
    checkpoint_effect = _first_checkpoint_effect(trajectory)
    query_id = _value(trajectory.get("query_id") or trajectory.get("query"), "missing query_id")
    strategy = _value(trajectory.get("strategy") or trajectory.get("system"), "missing strategy")
    user_query = _value(trajectory.get("original_query") or trajectory.get("query"), "missing original query")
    return redact_secrets(
        {
            "query_id": query_id,
            "strategy": strategy,
            "variant": _variant_label(trajectory),
            "user_query": user_query,
            "route": {
                "mode": _value(route.get("mode") or route.get("route_type"), "no prompt router decision"),
                "confidence": _value(route.get("confidence"), "no route confidence recorded"),
                "risk": _value(route.get("risk"), "no route risk recorded"),
                "api_policy": _value(route.get("api_policy"), "no API policy recorded"),
            },
            "normalization": _normalization_summary(checkpoints),
            "tokens": _tokens_summary(checkpoints, nlp_step),
            "context": {
                "context_mode": candidate_mode,
                "context_mode_note": context_mode_note,
                "candidate_tables": _value(candidate_tables, "no candidate tables recorded"),
                "candidate_apis": _value(candidate_apis, "no candidate APIs recorded"),
                "confidence": _value(_find_nested(trajectory, "confidence"), "no candidate confidence recorded"),
                "score_margin": _value(_find_nested(trajectory, "score_margin"), "no candidate score margin recorded"),
                "estimated_context_tokens": _value(estimated_context_tokens, "no context token estimate recorded"),
            },
            "planning": {
                "selected_strategy": strategy,
                "rationale": _value(plan_step.get("rationale"), "no plan rationale recorded"),
                "optimizer_decision": _value(_brief(optimizer_step.get("plan_ensemble") or plan_step.get("optimizer_actions")), "no optimizer decision recorded"),
                "optimizer_selected": _value(_optimizer_selected(optimizer_step, plan_step), "no optimizer selection recorded"),
                "call_budget": _value(_checkpoint_output(checkpoints, "checkpoint_11_call_budget"), "no call budget checkpoint recorded"),
            },
            "sql": {
                "preview": _value(first_sql.get("sql"), "no SQL call in trajectory"),
                "validation": _validation_status(first_sql),
                "row_count": _value(_nested(first_sql, ["result", "row_count"]), "no SQL row count recorded"),
                "result_preview": _value(_brief(_nested(first_sql, ["result", "rows"])), "no SQL rows preview recorded"),
            },
            "api": {
                "endpoint": _api_endpoint(first_api),
                "validation": _validation_status(first_api),
                "dry_run": dry_run,
                "live_evidence_available": _api_live_evidence(api_calls),
                "endpoint_repair": _value(_endpoint_repair(api_calls), "no endpoint repair recorded"),
                "result_preview": _value(_brief(_nested(first_api, ["result", "result_preview"])), "no API result preview recorded"),
            },
            "execution": {
                "execute_sql_calls": len(sql_calls),
                "call_api_calls": len(api_calls),
                "tool_call_count": _value(trajectory.get("tool_call_count"), "tool_call_count missing"),
                "valid_agent_run": _value(trajectory.get("valid_agent_run"), "valid_agent_run not recorded"),
                "tool_calls_executed": _value(trajectory.get("tool_calls_executed"), "tool_calls_executed not recorded"),
                "valid_tool_calls": _valid_tool_calls(trajectory, sql_calls, api_calls),
                "invalid_tool_calls": _value(trajectory.get("invalid_tool_call_count"), "no invalid-call metric recorded"),
                "duplicate_invalid_calls": _value(trajectory.get("duplicate_invalid_call_count"), "no duplicate-invalid metric recorded"),
                "endpoint_repairs": _value(trajectory.get("repaired_endpoint_count"), "no endpoint-repair metric recorded"),
                "schema_hint_injections": _value(trajectory.get("schema_hint_injected"), "no schema-hint metric recorded"),
            },
            "evidence": {
                "sql_evidence_available": sql_evidence_available,
                "live_api_evidence_available": live_api_evidence_available,
                "overall_evidence_available": evidence_available,
                "evidence_available": evidence_available,
                "dry_run_only": dry_run,
                "zero_row_uncertain": _zero_row_uncertain(sql_calls),
                "successful_evidence_count": _successful_evidence_count(trajectory, sql_calls, api_calls),
                "explanation": _evidence_explanation(dry_run, sql_evidence_available, live_api_evidence_available, evidence_available),
            },
            "answer": {
                "final_answer_preview": _value(_preview(trajectory.get("final_answer")), "missing final answer"),
                "answer_verification": _value(_checkpoint_output(checkpoints, "checkpoint_16_answer_verification"), "no answer verification checkpoint recorded"),
                "empty_result_uncertainty": _value(_empty_result_uncertainty(trajectory), "no empty-result uncertainty wording detected"),
            },
            "metrics": {
                "runtime": _value(trajectory.get("runtime"), "runtime missing"),
                "estimated_tokens": _value(trajectory.get("estimated_tokens"), "estimated_tokens missing"),
                "prompt_context_tokens": _value(trajectory.get("prompt_context_tokens"), "prompt_context_tokens missing"),
                "preprocessing_time": _value(trajectory.get("preprocessing_time"), "preprocessing_time missing"),
                "planning_time": _value(trajectory.get("planning_time"), "planning_time missing"),
                "execution_time": _value(trajectory.get("execution_time"), "execution_time missing"),
                "answer_time": _value(trajectory.get("answer_time"), "answer_time missing"),
                "checkpoint_count": len(trajectory.get("checkpoints", []) or []),
            },
            "checkpoint_effect": checkpoint_effect,
            "checkpoint_count": len(trajectory.get("checkpoints", []) or []),
            "research_techniques": research_technique_status(trajectory),
            "sql_ast": _value(_checkpoint_output(checkpoints, "checkpoint_sql_ast_validation"), "SQL AST validation checkpoint inactive"),
            "value_retrieval_cache": _value(_checkpoint_output(checkpoints, "checkpoint_value_entity_retrieval"), "value retrieval checkpoint inactive"),
            "candidate_ranking": _candidate_ranking_summary(trajectory),
            "risk_efficiency_controller": _risk_efficiency_summary(trajectory),
            "schema_context_vote": _schema_context_vote_summary(trajectory),
            "shadow_repair": _shadow_repair_summary(trajectory),
            "compact_context_shadow": _compact_context_shadow_summary(trajectory),
            "risk_efficiency_shadow": _risk_efficiency_shadow_summary(trajectory),
            "official_token_reduction": _official_token_reduction_summary(trajectory),
        }
    )


def build_mermaid_graph(trajectory: dict[str, Any]) -> str:
    summary = build_dataflow_summary(trajectory)
    route = summary["route"]
    context = summary["context"]
    sql = summary["sql"]
    api = summary["api"]
    evidence = summary["evidence"]
    metrics = summary["metrics"]
    lines = [
        "flowchart TD",
        "  subgraph Input",
        f"    input_prompt[\"User Prompt<br/>{_m(summary['user_query'])}\"]",
        "  end",
        "  subgraph Routing",
        f"    router[\"Prompt Router<br/>mode={_m(route['mode'])}<br/>api={_m(route['api_policy'])}\"]",
        "    input_prompt -->|route_prompt| router",
        "  end",
        "  subgraph QueryUnderstanding[\"Query Understanding\"]",
        f"    normalizer[\"Query Normalizer<br/>{_m(_normalizer_label(summary['normalization']))}\"]",
        f"    tokens[\"Query Tokens<br/>{_m(_tokens_label(summary['tokens']))}\"]",
        "    router -->|clean + extract| normalizer --> tokens",
        "  end",
        "  subgraph ContextSelection[\"Context Selection\"]",
        f"    context[\"Context Mode<br/>{_m(context['context_mode'])}\"]",
        f"    candidates[\"Context<br/>{_m(_context_label(context))}\"]",
        "    tokens -->|score relevance| context --> candidates",
        "  end",
        "  subgraph Planning",
        f"    planner[\"Planner<br/>{_m(summary['planning']['selected_strategy'])}\"]",
        f"    optimizer[\"Plan Optimizer<br/>selected={_m(summary['planning']['optimizer_selected'])}\"]",
        "    candidates -->|metadata + policy| planner --> optimizer",
        "  end",
        "  subgraph SQLPath[\"SQL Path\"]",
        f"    sqlgen[\"SQL Generator<br/>{_m(_sql_label(sql))}\"]",
        f"    sqlval[\"SQL Validator<br/>{_m(sql['validation'])}\"]",
        "    optimizer -->|SQL step if needed| sqlgen --> sqlval",
        "  end",
        "  subgraph APIPath[\"API Path\"]",
        f"    apisel[\"API Selector<br/>{_m(_api_label(api))}\"]",
        f"    apival[\"API Validator<br/>{_m(api['validation'])}<br/>dry_run={_m(str(api['dry_run']))}\"]",
        "    optimizer -->|API policy| apisel --> apival",
        "  end",
        "  subgraph ToolExecution[\"Tool Execution\"]",
        f"    tools[\"Tool Calls<br/>sql={summary['execution']['execute_sql_calls']} api={summary['execution']['call_api_calls']}<br/>invalid={_m(str(summary['execution']['invalid_tool_calls']))}\"]",
        "    sqlval -->|execute_sql| tools",
        "    apival -->|call_api / dry-run| tools",
        "  end",
        "  subgraph EvidenceBus",
        f"    evidence[\"EvidenceBus<br/>{_m(_evidence_label(evidence))}\"]",
        "    tools -->|extract facts| evidence",
        "  end",
        "  subgraph AnswerVerification[\"Answer Verification\"]",
        f"    verifier[\"Verifier<br/>{_m(_verifier_label(summary['answer']['answer_verification']))}\"]",
        "    evidence -->|answer slots + claims| verifier",
        "  end",
        "  subgraph FinalAnswer[\"Final Answer\"]",
        f"    answer[\"Final Answer<br/>{_m(summary['answer']['final_answer_preview'])}\"]",
        "    verifier -->|safe answer| answer",
        "  end",
        "  subgraph Metrics",
        f"    metrics[\"Metrics<br/>tools={_m(str(metrics['tool_call_count'] if 'tool_call_count' in metrics else summary['execution']['tool_call_count']))}<br/>tokens={_m(str(metrics['estimated_tokens']))}<br/>runtime={_m(str(metrics['runtime']))}\"]",
        "    answer -->|record trajectory| metrics",
        "  end",
    ]
    return "\n".join(lines) + "\n"


def build_checkpoint_effect_table(trajectory: dict[str, Any]) -> str:
    lines = [
        "| Checkpoint | Stage | Technique | Input | Output | Effect on data flow | Correctness role | Efficiency role |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    checkpoints = trajectory.get("checkpoints", []) or []
    if not checkpoints:
        lines.append("| `n/a` | n/a | n/a | n/a | n/a | n/a - no checkpoints recorded | n/a | n/a |")
    for checkpoint in checkpoints:
        lines.append(
            "| `{}` | {} | {} | {} | {} | {} | {} | {} |".format(
                _md(checkpoint.get("checkpoint_id")),
                _md(checkpoint.get("stage")),
                _md(checkpoint.get("technique")),
                _md(_brief(checkpoint.get("input_summary"))),
                _md(_brief(checkpoint.get("output") or checkpoint.get("output_summary"))),
                _md(checkpoint.get("effect")),
                _md(checkpoint.get("correctness_role")),
                _md(checkpoint.get("efficiency_role")),
            )
        )
    return "\n".join(lines) + "\n"


def build_research_technique_table(summary: dict[str, Any]) -> str:
    lines = [
        "| Technique | Source inspiration | Active? | Effect on dataflow | Correctness impact | Efficiency impact | Visualization checkpoint |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in summary.get("research_techniques", []):
        lines.append(
            f"| {_md(row.get('technique'))} | {_md(row.get('source_inspiration'))} | {_md(row.get('active'))} | "
            f"{_md(row.get('effect_on_dataflow'))} | {_md(row.get('correctness_impact'))} | {_md(row.get('efficiency_impact'))} | {_md(row.get('visualization_checkpoint'))} |"
        )
    return "\n".join(lines) + "\n"


def build_value_retrieval_cache_table(summary: dict[str, Any]) -> str:
    value_cache = summary.get("value_retrieval_cache")
    lines = [
        "| Field | Value |",
        "| --- | --- |",
    ]
    if not isinstance(value_cache, dict):
        lines.append(f"| status | {_md(value_cache)} |")
        return "\n".join(lines) + "\n"
    for key in [
        "cache_hit",
        "cache_key_algorithm",
        "cache_reproducible",
        "retrieval_ms",
        "cold_cache_build_ms",
        "warm_cache_lookup_ms",
        "value_retrieval_budget_exceeded",
        "match_count",
    ]:
        lines.append(f"| {key} | {_md(value_cache.get(key, 'n/a'))} |")
    return "\n".join(lines) + "\n"


def build_sql_ast_summary_table(summary: dict[str, Any]) -> str:
    sql_ast = summary.get("sql_ast")
    lines = [
        "| Field | Value |",
        "| --- | --- |",
    ]
    if not isinstance(sql_ast, dict):
        lines.append(f"| status | {_md(sql_ast)} |")
        return "\n".join(lines) + "\n"
    for key in [
        "parsed_ok",
        "parse_errors",
        "selected_tables",
        "selected_columns",
        "unknown_tables",
        "unknown_columns",
        "destructive_sql_detected",
        "closest_table_suggestions",
        "closest_column_suggestions",
    ]:
        lines.append(f"| {key} | {_md(_brief(sql_ast.get(key), 800) or 'n/a')} |")
    return "\n".join(lines) + "\n"


def build_candidate_ranking_table(summary: dict[str, Any]) -> str:
    ranking = summary.get("candidate_ranking")
    lines = [
        "| Technique | Active | Output | Correctness role | Efficiency role |",
        "| --- | --- | --- | --- | --- |",
    ]
    if not isinstance(ranking, dict):
        lines.append(f"| status | false | {_md(ranking)} | n/a | n/a |")
        return "\n".join(lines) + "\n"
    for key, label in [
        ("hybrid_candidate_scoring", "Hybrid Candidate Scoring"),
        ("endpoint_family_ranking", "Endpoint Family Ranker"),
        ("structural_schema_preservation", "Structural Schema Preservation"),
        ("value_to_api_ranking", "Value-to-API Ranking"),
        ("gated_risk_cluster_repair", "Gated Risk Cluster Repair"),
    ]:
        row = ranking.get(key, {})
        lines.append(
            f"| {label} | {_md(row.get('active'))} | {_md(_brief(row.get('output'), 900) or 'n/a')} | "
            f"{_md(row.get('correctness_role'))} | {_md(row.get('efficiency_role'))} |"
        )
    return "\n".join(lines) + "\n"


def build_shadow_repair_table(summary: dict[str, Any]) -> str:
    shadow = summary.get("shadow_repair")
    lines = [
        "| Risk cluster | Current candidate | Repaired candidate | Safety verdict | Score delta | Tool/cost delta | Enable recommendation |",
        "| --- | --- | --- | --- | ---: | --- | --- |",
    ]
    if not isinstance(shadow, dict) or not shadow.get("available"):
        lines.append("| n/a | n/a | n/a | n/a | n/a | n/a | n/a - no shadow repair eval row recorded |")
        return "\n".join(lines) + "\n"
    lines.append(
        f"| {_md(shadow.get('risk_cluster'))} | {_md(_brief(shadow.get('current_candidate'), 500))} | "
        f"{_md(_brief(shadow.get('repaired_candidate'), 500))} | {_md(shadow.get('safety_verdict'))} | "
        f"{_md(shadow.get('score_delta'))} | {_md(shadow.get('tool_cost_delta'))} | {_md(shadow.get('enable_recommendation'))} |"
    )
    lines.append(
        f"| execution changed? | {_md(shadow.get('execution_changed'))} | reason | "
        f"{_md(shadow.get('why_execution_not_changed'))} | decision hash | {_md(shadow.get('decision_hash'))} | |"
    )
    return "\n".join(lines) + "\n"


def build_risk_efficiency_table(summary: dict[str, Any]) -> str:
    risk = summary.get("risk_efficiency_controller")
    lines = [
        "| Field | Value |",
        "| --- | --- |",
    ]
    if not isinstance(risk, dict) or not risk.get("available", True):
        lines.append(f"| status | {_md(risk)} |")
        return "\n".join(lines) + "\n"
    for key in [
        "risk_level",
        "accuracy_risk",
        "module_policy",
        "module_skipped_by_risk",
        "token_saved_estimate",
        "runtime_saved_estimate_ms",
        "savings_are_estimates",
        "measured_efficiency_improvement_claimed",
        "behavior_changed",
    ]:
        lines.append(f"| {key} | {_md(_brief(risk.get(key), 700) or 'n/a')} |")
    return "\n".join(lines) + "\n"


def build_schema_context_vote_table(summary: dict[str, Any]) -> str:
    vote = summary.get("schema_context_vote")
    lines = [
        "| Field | Value |",
        "| --- | --- |",
    ]
    if not isinstance(vote, dict) or not vote.get("available", True):
        lines.append(f"| status | {_md(vote)} |")
        return "\n".join(lines) + "\n"
    for key in [
        "active",
        "schema_vote_agreement",
        "compact_context_safe",
        "fallback_reason",
        "compact_candidate_tables",
        "fallback_candidate_tables",
        "compact_candidate_apis",
        "fallback_candidate_apis",
        "token_delta",
        "behavior_changed",
    ]:
        lines.append(f"| {key} | {_md(_brief(vote.get(key), 700) or 'n/a')} |")
    return "\n".join(lines) + "\n"


def build_compact_context_shadow_table(summary: dict[str, Any]) -> str:
    row = summary.get("compact_context_shadow")
    lines = ["| Field | Value |", "| --- | --- |"]
    if not isinstance(row, dict) or not row.get("available", True):
        lines.append(f"| status | {_md(row)} |")
        return "\n".join(lines) + "\n"
    for key in [
        "current_score",
        "compact_context_score",
        "score_delta",
        "token_delta",
        "runtime_delta",
        "tool_call_delta",
        "final_answer_difference",
        "packaged_execution_changed",
        "measured_accuracy_improvement_claimed",
        "measured_efficiency_improvement_claimed",
    ]:
        lines.append(f"| {key} | {_md(_brief(row.get(key), 500) or 'n/a')} |")
    return "\n".join(lines) + "\n"


def build_risk_efficiency_shadow_table(summary: dict[str, Any]) -> str:
    row = summary.get("risk_efficiency_shadow")
    lines = ["| Field | Value |", "| --- | --- |"]
    if not isinstance(row, dict) or not row.get("available", True):
        lines.append(f"| status | {_md(row)} |")
        return "\n".join(lines) + "\n"
    for key in [
        "risk_level",
        "module_skipped_by_risk",
        "current_score",
        "risk_skipping_score",
        "score_delta",
        "token_delta",
        "runtime_delta",
        "tool_call_delta",
        "final_answer_difference",
        "packaged_execution_changed",
        "measured_accuracy_improvement_claimed",
        "measured_efficiency_improvement_claimed",
    ]:
        lines.append(f"| {key} | {_md(_brief(row.get(key), 500) or 'n/a')} |")
    return "\n".join(lines) + "\n"


def build_official_token_reduction_table(summary: dict[str, Any]) -> str:
    row = summary.get("official_token_reduction")
    lines = ["| Field | Value |", "| --- | --- |"]
    if not isinstance(row, dict):
        lines.append(f"| status | {_md(row)} |")
        return "\n".join(lines) + "\n"
    for key in [
        "official_token_reduction_available",
        "official_token_reduction_active",
        "estimated_tokens_before",
        "estimated_tokens_after",
        "token_savings",
        "reduced_fields",
        "correctness_impact_expected",
        "packaged_execution_changed",
    ]:
        lines.append(f"| {key} | {_md(_brief(row.get(key), 700) or 'n/a')} |")
    return "\n".join(lines) + "\n"


def build_markdown_report(trajectory: dict[str, Any]) -> str:
    summary = build_dataflow_summary(trajectory)
    lines = [
        "# DASHSys Prompt-To-Answer Dataflow",
        "",
        "## Quality Gate Facts",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| Query ID | `{_md(summary['query_id'])}` |",
        f"| User query | {_md(summary['user_query'])} |",
        f"| Strategy | `{_md(summary['strategy'])}` |",
        f"| Variant | {_md(summary['variant'])} |",
        f"| Final answer preview | {_md(summary['answer']['final_answer_preview'])} |",
        f"| Tool call count | {_md(summary['execution']['tool_call_count'])} |",
        f"| Runtime | {_md(summary['metrics']['runtime'])} |",
        f"| Estimated tokens | {_md(summary['metrics']['estimated_tokens'])} |",
        f"| Checkpoint count | {_md(summary['checkpoint_count'])} |",
        f"| Candidate context mode | {_md(summary['context']['context_mode'])} |",
        f"| Context mode note | {_md(summary['context']['context_mode_note'])} |",
        "",
        "```mermaid",
        build_mermaid_graph(trajectory).strip(),
        "```",
        "",
        "## SQL And API Preview",
        "",
        "| Path | Preview | Validation | Result / Status |",
        "| --- | --- | --- | --- |",
        f"| SQL | {_md(summary['sql']['preview'])} | {_md(summary['sql']['validation'])} | row_count={_md(summary['sql']['row_count'])}; rows={_md(summary['sql']['result_preview'])} |",
        f"| API | {_md(summary['api']['endpoint'])} | {_md(summary['api']['validation'])} | dry_run={_md(summary['api']['dry_run'])}; live_api_evidence={_md(summary['api']['live_evidence_available'])}; overall_evidence={_md(summary['evidence']['evidence_available'])}; preview={_md(summary['api']['result_preview'])} |",
        "",
        "Context mode labels ending in `_inferred` are display-only summaries for the visualization; they are not recorded planner decisions.",
        "",
        "## Tool Execution vs Evidence Availability",
        "",
        summary["evidence"]["explanation"],
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| execute_sql calls | {_md(summary['execution']['execute_sql_calls'])} |",
        f"| call_api calls | {_md(summary['execution']['call_api_calls'])} |",
        f"| valid tool calls | {_md(summary['execution']['valid_tool_calls'])} |",
        f"| invalid tool calls | {_md(summary['execution']['invalid_tool_calls'])} |",
        f"| endpoint repairs | {_md(summary['execution']['endpoint_repairs'])} |",
        f"| schema hint injections | {_md(summary['execution']['schema_hint_injections'])} |",
        f"| SQL evidence available | {_md(summary['evidence']['sql_evidence_available'])} |",
        f"| live API evidence available | {_md(summary['evidence']['live_api_evidence_available'])} |",
        f"| overall evidence available | {_md(summary['evidence']['overall_evidence_available'])} |",
        f"| dry-run only | {_md(summary['evidence']['dry_run_only'])} |",
        f"| successful evidence count | {_md(summary['evidence']['successful_evidence_count'])} |",
        f"| zero-row uncertain | {_md(summary['evidence']['zero_row_uncertain'])} |",
        "",
        "## Research Technique Status",
        "",
        build_research_technique_table(summary).strip(),
        "",
        "## Candidate Ranking Diagnostics",
        "",
        build_candidate_ranking_table(summary).strip(),
        "",
        "## Shadow Repair / What-if Evaluation",
        "",
        build_shadow_repair_table(summary).strip(),
        "",
        "## Risk-Based Efficiency Controller",
        "",
        "Token/runtime savings in this section are estimates only unless packaged execution explicitly changes and validation confirms measured savings.",
        "",
        build_risk_efficiency_table(summary).strip(),
        "",
        "## Schema Context Voting",
        "",
        "Schema context voting is diagnostic guidance for high-risk rows and does not change executed SQL/API plans.",
        "",
        build_schema_context_vote_table(summary).strip(),
        "",
        "## Compact Context Shadow Evaluation",
        "",
        build_compact_context_shadow_table(summary).strip(),
        "",
        "## Risk-Efficiency Shadow Evaluation",
        "",
        build_risk_efficiency_shadow_table(summary).strip(),
        "",
        "## Official Token Reduction",
        "",
        build_official_token_reduction_table(summary).strip(),
        "",
        "## Value Retrieval Cache",
        "",
        build_value_retrieval_cache_table(summary).strip(),
        "",
        "## SQL AST Validation",
        "",
        build_sql_ast_summary_table(summary).strip(),
        "",
        "## Technique Impact Highlight",
        "",
        f"- Correctness: {_md(summary['checkpoint_effect']['correctness_role'])}",
        f"- Efficiency: {_md(summary['checkpoint_effect']['efficiency_role'])}",
        f"- Dataflow effect: {_md(summary['checkpoint_effect']['effect'])}",
        "",
        "## Prompt To SQL/API Mapping",
        "",
        "```json",
        json.dumps(redact_secrets(compact_preview(extract_prompt_to_sql_api_mapping(trajectory), 5000)), indent=2, sort_keys=True, default=str),
        "```",
        "",
        "## Checkpoint Effect Table",
        "",
        build_checkpoint_effect_table(trajectory).strip(),
        "",
    ]
    return "\n".join(lines)


def build_html_report(trajectory: dict[str, Any]) -> str:
    markdown = build_markdown_report(trajectory)
    graph = build_mermaid_graph(trajectory)
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>DASHSys Dataflow</title>
  <script type="module">import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs'; mermaid.initialize({{startOnLoad:true}});</script>
  <style>body{{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;margin:32px;line-height:1.45}} pre{{background:#f6f8fa;padding:12px;overflow:auto;white-space:pre-wrap}} table{{border-collapse:collapse;width:100%;margin:12px 0}} td,th{{border:1px solid #d0d7de;padding:6px;vertical-align:top}} code{{background:#f6f8fa;padding:1px 4px;border-radius:3px}}</style>
</head>
<body>
  <h1>DASHSys Prompt-To-Answer Dataflow</h1>
  <div class="mermaid">{html.escape(graph)}</div>
  <h2>Markdown Report</h2>
  <pre>{html.escape(markdown)}</pre>
</body>
</html>
"""


def write_dataflow_artifacts(trajectory: dict[str, Any], out_dir: Path, *, overwrite: bool = True) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "mmd": out_dir / "dataflow.mmd",
        "md": out_dir / "dataflow.md",
        "html": out_dir / "dataflow.html",
        "json": out_dir / "dataflow_summary.json",
        "spans": out_dir / "spans.json",
    }
    if not overwrite and all(path.exists() for path in files.values()):
        return {key: str(path) for key, path in files.items()}
    files["mmd"].write_text(build_mermaid_graph(trajectory), encoding="utf-8")
    files["md"].write_text(build_markdown_report(trajectory), encoding="utf-8")
    files["html"].write_text(build_html_report(trajectory), encoding="utf-8")
    files["json"].write_text(json.dumps(build_dataflow_summary(trajectory), indent=2, sort_keys=True, default=str), encoding="utf-8")
    files["spans"].write_text(json.dumps(checkpoints_to_spans(trajectory), indent=2, sort_keys=True, default=str), encoding="utf-8")
    return {key: str(path) for key, path in files.items()}


def default_visualization_dir(outputs_dir: Path, trajectory: dict[str, Any]) -> Path:
    query_id = _slug(str(trajectory.get("query_id") or trajectory.get("query") or "query"))
    strategy = _slug(str(trajectory.get("strategy") or trajectory.get("system") or "unknown_strategy"))
    return outputs_dir / "visualizations" / query_id / strategy


def trajectory_from_llm_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "query_id": row.get("query_id"),
        "original_query": row.get("query"),
        "strategy": row.get("system"),
        "system": row.get("system"),
        "baseline_variant": row.get("baseline_variant"),
        "final_answer": row.get("final_answer"),
        "tool_call_count": row.get("tool_call_count"),
        "runtime": row.get("runtime"),
        "prompt_context_tokens": row.get("prompt_context_tokens"),
        "invalid_tool_call_count": row.get("invalid_tool_call_count"),
        "duplicate_invalid_call_count": row.get("duplicate_invalid_call_count"),
        "repaired_endpoint_count": row.get("repaired_endpoint_count"),
        "schema_hint_injected": row.get("schema_hint_injected"),
        "successful_evidence_count": row.get("successful_evidence_count"),
        "valid_agent_run": row.get("valid_agent_run"),
        "tool_calls_executed": row.get("tool_calls_executed"),
        "dry_run_only_api_count": row.get("dry_run_only_api_count"),
        "llm_tool_calls": row.get("llm_tool_calls", []),
        "steps": [],
        "checkpoints": [],
    }


def _llm_tool_call_to_step(call: dict[str, Any]) -> dict[str, Any]:
    args = call.get("arguments") or {}
    if call.get("tool_name") == "execute_sql" or call.get("tool") == "execute_sql":
        result = call.get("result_preview") or {}
        return {
            "kind": "sql_call",
            "sql": args.get("sql"),
            "validation": call.get("validation"),
            "result": {
                "row_count": result.get("row_count"),
                "rows": result.get("rows") or result.get("rows_preview"),
                "ok": result.get("ok"),
            },
        }
    result = call.get("result_preview") or {}
    return {
        "kind": "api_call",
        "method": args.get("method"),
        "url": args.get("url"),
        "params": args.get("params"),
        "validation": call.get("validation"),
        "result": result,
        "endpoint_repair": call.get("endpoint_repair"),
    }


def _first_step(trajectory: dict[str, Any], kind: str) -> dict[str, Any]:
    for step in trajectory.get("steps", []) or []:
        if step.get("kind") == kind:
            return step
    return {}


def _normalization_summary(checkpoints: dict[str, dict[str, Any]]) -> dict[str, Any]:
    output = _checkpoint_output(checkpoints, "checkpoint_02_query_normalization")
    if isinstance(output, dict) and output:
        return output
    return {"normalized_query": _value(None, "no normalization checkpoint recorded")}


def _tokens_summary(checkpoints: dict[str, dict[str, Any]], nlp_step: dict[str, Any]) -> dict[str, Any]:
    output = _checkpoint_output(checkpoints, "checkpoint_03_query_tokens")
    if isinstance(output, dict) and output:
        return output
    if isinstance(nlp_step.get("tokens"), dict):
        return nlp_step["tokens"]
    return {"tokens": _value(None, "no tokens recorded")}


def _normalizer_label(normalization: dict[str, Any]) -> str:
    query = normalization.get("normalized_query") or normalization.get("matching_text")
    if isinstance(query, str) and query.startswith("n/a -"):
        return "status=not_recorded"
    return "normalized query" if query else "status=not_recorded"


def _tokens_label(tokens: Any) -> str:
    domains = _short_list(_extract_named_values(tokens, ("domains", "domain_tokens")), empty="none")
    entities = _short_list(
        _extract_named_values(tokens, ("quoted_entities", "entities", "entity_names", "ids")),
        empty="none",
    )
    statuses = _short_list(_extract_named_values(tokens, ("statuses", "status_tokens", "status_terms")), empty="none")
    parts = [f"domains={domains}", f"entities={entities}"]
    if statuses != "none":
        parts.append(f"status={statuses}")
    return "<br/>".join(parts)


def _context_label(context: dict[str, Any]) -> str:
    tables = _short_list(_extract_item_names(context.get("candidate_tables")), empty="none")
    apis = _short_list(_extract_item_names(context.get("candidate_apis")), empty="none")
    return f"tables={tables}<br/>apis={apis}"


def _sql_label(sql: dict[str, Any]) -> str:
    preview = str(sql.get("preview") or "")
    if preview.startswith("n/a -"):
        return "source=none"
    tables = _short_list(_extract_sql_tables(preview), empty="unknown")
    return f"tables={tables}<br/>rows={sql.get('row_count')}"


def _api_label(api: dict[str, Any]) -> str:
    endpoint = str(api.get("endpoint") or "")
    if endpoint.startswith("n/a -"):
        return "endpoint=none"
    endpoint = endpoint.replace("GET ", "").replace("POST ", "")
    return f"endpoint={_preview(endpoint, 54)}"


def _evidence_label(evidence: dict[str, Any]) -> str:
    return (
        f"SQL evidence: {_yes_no(evidence.get('sql_evidence_available'))}<br/>"
        f"Live API evidence: {_yes_no(evidence.get('live_api_evidence_available'))}<br/>"
        f"Dry-run API: {_yes_no(evidence.get('dry_run_only'))}"
    )


def _verifier_label(answer_verification: Any) -> str:
    if isinstance(answer_verification, dict):
        passed = answer_verification.get("verifier_passed")
        if passed is None:
            passed = answer_verification.get("passed")
        unsupported = answer_verification.get("unsupported_claims_count")
        return f"passed={_yes_no(passed)}<br/>unsupported={unsupported if unsupported is not None else 'n/a'}"
    text = str(answer_verification or "")
    if text.startswith("n/a -"):
        return "status=not_recorded"
    return "status=recorded"


def _optimizer_selected(optimizer_step: dict[str, Any], plan_step: dict[str, Any]) -> Any:
    selected = _nested(optimizer_step, ["plan_ensemble", "selected"])
    if selected:
        return selected
    actions = plan_step.get("optimizer_actions") or []
    if actions:
        match = re.search(r"selected\s+([A-Za-z0-9_/-]+)", " ".join(map(str, actions)))
        if match:
            return match.group(1)
        return _preview(", ".join(map(str, actions)), 70)
    return None


def _candidate_tables(checkpoints: dict[str, dict[str, Any]], nlp_step: dict[str, Any]) -> Any:
    output = _checkpoint_output(checkpoints, "checkpoint_04_relevance_scoring")
    if isinstance(output, dict):
        return output.get("top_tables") or output.get("tables")
    context_output = _checkpoint_output(checkpoints, "checkpoint_07_context_card")
    if isinstance(context_output, dict):
        return context_output.get("selected_tables") or context_output.get("tables")
    return (nlp_step.get("relevance") or {}).get("tables")


def _candidate_apis(checkpoints: dict[str, dict[str, Any]], nlp_step: dict[str, Any]) -> Any:
    output = _checkpoint_output(checkpoints, "checkpoint_04_relevance_scoring")
    if isinstance(output, dict):
        return output.get("top_apis") or output.get("apis")
    context_output = _checkpoint_output(checkpoints, "checkpoint_07_context_card")
    if isinstance(context_output, dict):
        return context_output.get("selected_apis") or context_output.get("apis")
    return (nlp_step.get("relevance") or {}).get("apis")


def _candidate_ranking_summary(trajectory: dict[str, Any]) -> Any:
    row = trajectory.get("_candidate_context_report_row")
    if not isinstance(row, dict):
        return _value(None, "no candidate context report row attached")
    hybrid = row.get("hybrid_candidate_scoring", {})
    endpoint = row.get("endpoint_family_ranking", {})
    schema_linking = row.get("schema_linking", {})
    value_api = row.get("value_to_api_ranking", {})
    repair = row.get("gated_risk_cluster_repair", {})
    return {
        "hybrid_candidate_scoring": {
            "active": bool(hybrid.get("active")),
            "output": {
                "top_candidate_score": hybrid.get("top_candidate_score"),
                "score_margin": hybrid.get("score_margin"),
                "ranking_changed": hybrid.get("ranking_changed"),
                "top_components": hybrid.get("top_components"),
            },
            "correctness_role": "separates candidate context without changing executed plan",
            "efficiency_role": "report-only scoring; no extra tools",
        },
        "endpoint_family_ranking": {
            "active": bool(endpoint.get("active")),
            "output": {
                "endpoint_family": endpoint.get("endpoint_family"),
                "endpoint_family_confidence": endpoint.get("endpoint_family_confidence"),
                "ranking_changed": endpoint.get("ranking_changed"),
                "boost_reason": endpoint.get("endpoint_boost_reason"),
            },
            "correctness_role": "reduces endpoint-family confusion in candidate context",
            "efficiency_role": "reranks metadata only",
        },
        "structural_schema_preservation": {
            "active": bool(schema_linking.get("bridge_preserved")),
            "output": {
                "structural_tables_added": row.get("structural_tables_added") or schema_linking.get("structural_tables_added"),
                "structural_reason": row.get("structural_reason") or schema_linking.get("structural_reason"),
                "structural_confidence_delta": row.get("structural_confidence_delta") or schema_linking.get("structural_confidence_delta"),
            },
            "correctness_role": "keeps relationship bridge tables visible",
            "efficiency_role": "adds only compact schema context",
        },
        "value_to_api_ranking": {
            "active": bool(value_api.get("active")),
            "output": value_api,
            "correctness_role": "uses only high-confidence retrieved values for endpoint family boosts",
            "efficiency_role": "reuses existing value retrieval diagnostics",
        },
        "gated_risk_cluster_repair": {
            "active": bool(repair.get("active")),
            "output": repair,
            "correctness_role": "compares a repaired candidate without executing losing plans",
            "efficiency_role": "diagnostic-only; zero tool-call delta",
        },
    }


def _shadow_repair_summary(trajectory: dict[str, Any]) -> dict[str, Any]:
    row = trajectory.get("_shadow_repair_eval_row")
    if not isinstance(row, dict):
        return {"available": False, "status": "n/a - no shadow repair eval row recorded"}
    safety = row.get("safety_verdict") or {}
    return {
        "available": True,
        "risk_cluster": row.get("risk_cluster"),
        "current_candidate": {
            "sql": row.get("current_plan_sql"),
            "api": row.get("current_plan_api"),
            "score": row.get("current_strict_score"),
        },
        "repaired_candidate": {
            "sql": row.get("repaired_plan_sql"),
            "api": row.get("repaired_plan_api"),
            "score": row.get("repaired_strict_score"),
        },
        "safety_verdict": "safe" if safety.get("safe") else "unsafe",
        "score_delta": row.get("score_delta"),
        "tool_cost_delta": {
            "tool_delta": row.get("tool_delta"),
            "token_delta": row.get("token_delta"),
            "runtime_delta": row.get("runtime_delta"),
        },
        "enable_recommendation": row.get("decision"),
        "execution_changed": row.get("execution_changed", False),
        "why_execution_not_changed": row.get("why_execution_not_changed"),
        "decision_hash": row.get("decision_hash"),
    }


def _risk_efficiency_summary(trajectory: dict[str, Any]) -> Any:
    row = trajectory.get("_shadow_repair_eval_row")
    if isinstance(row, dict) and isinstance(row.get("risk_efficiency_controller"), dict):
        return {"available": True, **row["risk_efficiency_controller"]}
    candidate = trajectory.get("_candidate_context_report_row")
    if isinstance(candidate, dict) and isinstance(candidate.get("risk_efficiency_controller"), dict):
        return {"available": True, **candidate["risk_efficiency_controller"]}
    return _value(None, "no risk-efficiency diagnostic row attached")


def _schema_context_vote_summary(trajectory: dict[str, Any]) -> Any:
    row = trajectory.get("_shadow_repair_eval_row")
    if isinstance(row, dict) and isinstance(row.get("schema_context_vote"), dict):
        return {"available": True, **row["schema_context_vote"]}
    candidate = trajectory.get("_candidate_context_report_row")
    if isinstance(candidate, dict) and isinstance(candidate.get("schema_context_vote"), dict):
        return {"available": True, **candidate["schema_context_vote"]}
    return _value(None, "no schema context voting diagnostic row attached")


def _compact_context_shadow_summary(trajectory: dict[str, Any]) -> Any:
    row = trajectory.get("_compact_context_shadow_eval_row")
    if isinstance(row, dict):
        return {"available": True, **row}
    return _value(None, "no compact-context shadow eval row attached")


def _risk_efficiency_shadow_summary(trajectory: dict[str, Any]) -> Any:
    row = trajectory.get("_risk_efficiency_shadow_eval_row")
    if isinstance(row, dict):
        return {"available": True, **row}
    return _value(None, "no risk-efficiency shadow eval row attached")


def _official_token_reduction_summary(trajectory: dict[str, Any]) -> dict[str, Any]:
    checkpoint = None
    for item in trajectory.get("checkpoints", []) or []:
        if item.get("checkpoint_id") == "checkpoint_official_token_reduction":
            checkpoint = item
            break
    if not checkpoint:
        return {
            "official_token_reduction_available": True,
            "official_token_reduction_active": False,
            "estimated_tokens_before": None,
            "estimated_tokens_after": trajectory.get("estimated_tokens"),
            "token_savings": 0,
            "reduced_fields": [],
            "correctness_impact_expected": False,
            "packaged_execution_changed": False,
        }
    before = checkpoint.get("estimated_tokens_before")
    after = checkpoint.get("estimated_tokens_after")
    return {
        "official_token_reduction_available": True,
        "official_token_reduction_active": bool(checkpoint.get("active")),
        "estimated_tokens_before": before,
        "estimated_tokens_after": after,
        "token_savings": checkpoint.get("expected_savings"),
        "reduced_fields": checkpoint.get("reduced_fields") or [],
        "correctness_impact_expected": checkpoint.get("correctness_impact_expected", False),
        "packaged_execution_changed": checkpoint.get("packaged_execution_changed", False),
    }


def _find_context_mode(
    trajectory: dict[str, Any],
    checkpoints: dict[str, dict[str, Any]],
    candidate_tables: Any,
    candidate_apis: Any,
    estimated_context_tokens: Any,
) -> tuple[str, str]:
    for checkpoint in checkpoints.values():
        for key in ("output", "input_summary", "metrics"):
            found = _find_nested(checkpoint.get(key), "context_mode")
            if found not in (None, "", [], {}):
                return str(found), "recorded in checkpoint/trajectory"
    found = _find_nested(trajectory, "context_mode")
    if found not in (None, "", [], {}):
        return str(found), "recorded in checkpoint/trajectory"
    if _checkpoint_output(checkpoints, "checkpoint_07_context_card") not in (None, "", [], {}):
        return "metadata_context_card", "display-only inferred from checkpoint_07_context_card"
    if _has_context_items(candidate_tables) or _has_context_items(candidate_apis):
        return "candidate_like_context_inferred", "display-only inferred from candidate tables/APIs"
    if estimated_context_tokens not in (None, "", [], {}):
        return "metadata_context_estimate_inferred", "display-only inferred from context token estimate"
    return "not_recorded", "no useful context-mode information recorded"


def _estimated_context_tokens(trajectory: dict[str, Any]) -> Any:
    for key in ("metadata_tokens", "prompt_context_tokens"):
        if trajectory.get(key) is not None:
            return trajectory.get(key)
    metadata_step = _first_step(trajectory, "metadata")
    return metadata_step.get("estimated_tokens")


def _api_endpoint(api_call: dict[str, Any]) -> str:
    if not api_call:
        return _value(None, "no API call in trajectory")
    method = api_call.get("method") or _nested(api_call, ["result", "method"]) or "GET"
    url = api_call.get("url") or _nested(api_call, ["result", "endpoint"]) or _nested(api_call, ["result", "url"])
    return f"{method} {url}" if url else _value(None, "API endpoint missing")


def _validation_status(step: dict[str, Any]) -> str:
    if not step:
        return _value(None, "no validation step recorded")
    validation = step.get("validation") or {}
    if validation.get("ok") is True:
        return "ok"
    if validation.get("ok") is False:
        return "failed: " + "; ".join(validation.get("errors") or [])
    return _value(None, "validation status missing")


def _api_dry_run(api_calls: list[dict[str, Any]]) -> Any:
    if not api_calls:
        return _value(None, "no API call in trajectory")
    return any(bool(_nested(call, ["result", "dry_run"]) or call.get("dry_run_only")) for call in api_calls)


def _api_live_evidence(api_calls: list[dict[str, Any]]) -> Any:
    if not api_calls:
        return _value(None, "no API call in trajectory")
    return any(bool(_nested(call, ["result", "ok"]) and not _nested(call, ["result", "dry_run"])) for call in api_calls)


def _sql_evidence_available(sql_calls: list[dict[str, Any]]) -> Any:
    if not sql_calls:
        return _value(None, "no SQL call in trajectory")
    return any((_nested(call, ["result", "row_count"]) or 0) > 0 for call in sql_calls)


def _endpoint_repair(api_calls: list[dict[str, Any]]) -> Any:
    repairs = []
    for call in api_calls:
        repair = call.get("endpoint_repair") or _nested(call, ["result", "endpoint_repair"])
        if repair:
            repairs.append(repair)
    return repairs


def _overall_evidence_available(
    trajectory: dict[str, Any],
    sql_calls: list[dict[str, Any]],
    api_calls: list[dict[str, Any]],
    sql_evidence_available: Any,
    live_api_evidence_available: Any,
) -> Any:
    if trajectory.get("successful_evidence_count") is not None:
        return trajectory.get("successful_evidence_count", 0) > 0
    if sql_evidence_available is True or live_api_evidence_available is True:
        return True
    if not sql_calls and not api_calls:
        return _value(None, "no tool calls in trajectory")
    return False


def _successful_evidence_count(trajectory: dict[str, Any], sql_calls: list[dict[str, Any]], api_calls: list[dict[str, Any]]) -> Any:
    if trajectory.get("successful_evidence_count") is not None:
        return trajectory.get("successful_evidence_count")
    count = 0
    count += sum(1 for call in sql_calls if (_nested(call, ["result", "row_count"]) or 0) > 0)
    count += sum(1 for call in api_calls if _nested(call, ["result", "ok"]) and not _nested(call, ["result", "dry_run"]))
    return count


def _valid_tool_calls(trajectory: dict[str, Any], sql_calls: list[dict[str, Any]], api_calls: list[dict[str, Any]]) -> Any:
    if trajectory.get("llm_tool_calls"):
        return sum(1 for call in trajectory.get("llm_tool_calls", []) if call.get("tool_validation_ok") or call.get("validation_ok"))
    return sum(1 for call in sql_calls + api_calls if (call.get("validation") or {}).get("ok") is True)


def _zero_row_uncertain(sql_calls: list[dict[str, Any]]) -> Any:
    if not sql_calls:
        return _value(None, "no SQL call in trajectory")
    return any((_nested(call, ["result", "row_count"]) == 0) for call in sql_calls)


def _empty_result_uncertainty(trajectory: dict[str, Any]) -> Any:
    answer = str(trajectory.get("final_answer") or "")
    if "executed query did not find evidence" in answer.lower():
        return "present"
    return None


def _evidence_explanation(
    dry_run: Any,
    sql_evidence_available: Any,
    live_api_evidence_available: Any,
    overall_evidence_available: Any,
) -> str:
    if dry_run is True:
        if sql_evidence_available is True:
            return "SQL evidence is available. API tool was invoked and validated, but live API evidence was unavailable because Adobe credentials were missing."
        return "API tool was invoked and validated, but live evidence was unavailable because Adobe credentials were missing."
    if overall_evidence_available is True:
        return "At least one SQL/API result provided evidence for answer construction."
    if overall_evidence_available is False:
        return "No successful evidence was available from executed tools."
    return str(overall_evidence_available)


def _first_checkpoint_effect(trajectory: dict[str, Any]) -> dict[str, str]:
    for checkpoint in trajectory.get("checkpoints", []) or []:
        correctness = checkpoint.get("correctness_role")
        efficiency = checkpoint.get("efficiency_role")
        effect = checkpoint.get("effect")
        if correctness or efficiency or effect:
            return {
                "checkpoint_id": str(checkpoint.get("checkpoint_id") or "n/a"),
                "correctness_role": _value(correctness, "no correctness role recorded"),
                "efficiency_role": _value(efficiency, "no efficiency role recorded"),
                "effect": _value(effect, "no dataflow effect recorded"),
            }
    return {
        "checkpoint_id": "n/a",
        "correctness_role": "n/a - no checkpoint correctness role recorded",
        "efficiency_role": "n/a - no checkpoint efficiency role recorded",
        "effect": "n/a - no checkpoint effect recorded",
    }


def _checkpoint_output(checkpoints: dict[str, dict[str, Any]], checkpoint_id: str) -> Any:
    checkpoint = checkpoints.get(checkpoint_id) or {}
    return checkpoint.get("output") or checkpoint.get("output_summary")


def _find_nested(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        if key in value:
            return value[key]
        for item in value.values():
            found = _find_nested(item, key)
            if found not in (None, "", [], {}):
                return found
    if isinstance(value, list):
        for item in value:
            found = _find_nested(item, key)
            if found not in (None, "", [], {}):
                return found
    return None


def _nested(value: Any, keys: list[str]) -> Any:
    current = value
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _value(value: Any, reason: str) -> Any:
    if value in (None, "", [], {}):
        return f"n/a - {reason}"
    return value


def _brief(value: Any, limit: int = 260) -> str:
    if value in (None, "", {}, []):
        return ""
    compact = compact_preview(value, limit)
    if isinstance(compact, (dict, list)):
        return json.dumps(compact, sort_keys=True, default=str)
    return str(compact)


def _preview(value: Any, limit: int = 220) -> str:
    if value in (None, ""):
        return ""
    text = str(value).replace("\n", " ")
    return text[:limit] + ("..." if len(text) > limit else "")


def _variant_label(trajectory: dict[str, Any]) -> str:
    variant = trajectory.get("baseline_variant")
    if variant == "raw":
        return "Raw"
    if variant == "guided":
        return "Guided"
    system = trajectory.get("system") or trajectory.get("strategy")
    if system == "LLM_CONTROLLER_OPTIMIZED_AGENT":
        return "Optimized Controller"
    return _value(variant, "not a baseline variant")


def count_mermaid_readability_issues(text: str) -> int:
    return sum(1 for line in text.splitlines() if any(pattern in line for pattern in READABILITY_PATTERNS))


def _extract_named_values(value: Any, names: tuple[str, ...]) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in names:
                found.extend(_extract_item_names(item))
            elif key not in {"total_items", "truncated_items", "truncated"}:
                found.extend(_extract_named_values(item, names))
    elif isinstance(value, list):
        for item in value:
            found.extend(_extract_named_values(item, names))
    return _dedupe(found)


def _extract_item_names(value: Any) -> list[str]:
    if value in (None, "", {}, []):
        return []
    if isinstance(value, str):
        if value.startswith("n/a -"):
            return []
        return [value]
    if isinstance(value, (int, float, bool)):
        return [str(value)]
    if isinstance(value, list):
        items: list[str] = []
        for item in value:
            items.extend(_extract_item_names(item))
        return _dedupe(items)
    if isinstance(value, dict):
        if "items" in value:
            return _extract_item_names(value.get("items"))
        for key in ("path", "endpoint", "endpoint_id", "name", "table", "id"):
            item = value.get(key)
            if isinstance(item, str) and item:
                return [item]
        items: list[str] = []
        for key, item in value.items():
            if key in {"total_items", "truncated_items", "truncated", "preview"}:
                continue
            items.extend(_extract_item_names(item))
        return _dedupe(items)
    return [str(value)]


def _short_list(items: list[str], *, empty: str = "n/a", max_items: int = 2, max_chars: int = 56) -> str:
    clean = [item for item in _dedupe(items) if item and not item.startswith("n/a -")]
    if not clean:
        return empty
    text = ",".join(_preview(item, 28) for item in clean[:max_items])
    if len(clean) > max_items:
        text += f"+{len(clean) - max_items}"
    return _preview(text, max_chars)


def _extract_sql_tables(sql: str) -> list[str]:
    identifier = r"(?:\"[^\"]+\"|`[^`]+`|[A-Za-z_][\w$]*)(?:\s*\.\s*(?:\"[^\"]+\"|`[^`]+`|[A-Za-z_][\w$]*))*"
    matches = re.findall(rf"\b(?:FROM|JOIN)\s+({identifier})", sql, flags=re.IGNORECASE)
    tables = []
    for match in matches:
        part = re.split(r"\s*\.\s*", match)[-1].strip().strip('"').strip("`")
        tables.append(part)
    return _dedupe(tables)


def _has_context_items(value: Any) -> bool:
    return bool(_extract_item_names(value))


def _yes_no(value: Any) -> str:
    if value is True:
        return "yes"
    if value is False:
        return "no"
    if isinstance(value, str) and value.startswith("n/a -"):
        return "n/a"
    return str(value)


def _dedupe(items: list[str]) -> list[str]:
    seen = set()
    output: list[str] = []
    for item in items:
        text = str(item)
        if text not in seen:
            seen.add(text)
            output.append(text)
    return output


def _m(text: str) -> str:
    return html.escape(str(text).replace("\n", " "))[:96]


def _md(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")[:800]


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", text.lower()).strip("_")
    return slug or "unknown"
