#!/usr/bin/env python
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.eval_harness import count_validation_failures, first_generated_sql, generated_api_calls, normalize_sql
from dashagent.trajectory import redact_secrets


BOTTLENECK_CATEGORIES = {
    "route_mismatch",
    "domain_mismatch",
    "wrong_sql_template",
    "wrong_api_template",
    "weak_relevance_selection",
    "unnecessary_dry_run_api",
    "answer_shape_weak",
    "unsupported_answer_claim",
    "token_cost_high",
    "tool_count_high",
    "semantic_router_no_effect",
    "confidence_miscalibrated",
    "no_clear_bottleneck",
}


DECISION_STAGES: list[dict[str, Any]] = [
    {
        "stage_id": 1,
        "name": "Prompt router",
        "decision_made": "LLM_DIRECT vs LOCAL_DB_ONLY vs SQL_PLUS_API vs API_ONLY.",
        "diagnostic_question": "Did this correctly decide whether the prompt needs SQL/API evidence?",
        "input_signals_used": ["query text", "live/status/API keywords", "data-object keywords"],
        "confidence_or_score": "checkpoint_00_prompt_router.confidence when present",
        "rejected_alternatives_if_available": "not usually logged beyond matched_rules",
        "downstream_effect": "can keep conceptual prompts out of the data pipeline or send data questions to tools",
        "known_failure_examples": ["synonyms such as data models or broken things can be under-specified"],
        "possible_improvement": "calibrate with deterministic route confidence and relevance margins",
        "safety_risk": "direct answers for evidence-needed prompts would be unsupported",
        "improvement_mode": "isolated_only",
        "extended_questions": [
            "Did router send data questions to evidence tools?",
            "Did it correctly avoid SQL/API for conceptual prompts?",
            "Did keyword routing miss synonyms?",
        ],
    },
    {
        "stage_id": 2,
        "name": "Simple prompt gate",
        "decision_made": "direct/simple handling vs USE_DATA_PIPELINE.",
        "diagnostic_question": "Did it avoid direct answers for evidence-needed data questions?",
        "input_signals_used": ["prompt-router mode", "confidence", "requires_database", "requires_api"],
        "confidence_or_score": "checkpoint_simple_prompt_gate.confidence",
        "rejected_alternatives_if_available": "direct response when suggested_action is USE_DATA_PIPELINE",
        "downstream_effect": "prevents unsupported answers for data questions",
        "known_failure_examples": ["ambiguous conceptual/data prompts"],
        "possible_improvement": "tighten conceptual prompt definitions without weakening evidence routing",
        "safety_risk": "unsupported claims if data prompts bypass tools",
        "improvement_mode": "isolated_only",
        "extended_questions": ["Does simple handling ever trigger for factual data questions?"],
    },
    {
        "stage_id": 3,
        "name": "Query normalization",
        "decision_made": "rewrite/no rewrite, singular/plural normalization, synonym normalization.",
        "diagnostic_question": "Did normalization preserve meaning while improving matchability?",
        "input_signals_used": ["raw query", "known plural/domain terms"],
        "confidence_or_score": "normalization rewrites list",
        "rejected_alternatives_if_available": "raw query is retained for answer wording",
        "downstream_effect": "feeds router, token extraction, and template matching",
        "known_failure_examples": ["over-normalization can erase user phrasing"],
        "possible_improvement": "record before/after tokens and preserve quoted entities",
        "safety_risk": "meaning drift",
        "improvement_mode": "promotable_if_hashes_safe",
        "extended_questions": ["Did singular/plural normalization help route matching without changing meaning?"],
    },
    {
        "stage_id": 4,
        "name": "Query token extraction",
        "decision_made": "domain/status/date/id/entity extraction.",
        "diagnostic_question": "Did it capture the important user intent signals?",
        "input_signals_used": ["normalized query", "quoted entities", "date/status patterns"],
        "confidence_or_score": "token presence and value-retrieval matches",
        "rejected_alternatives_if_available": "not usually logged",
        "downstream_effect": "drives answer families and SQL/API filters",
        "known_failure_examples": ["terse prompts and typos"],
        "possible_improvement": "add typo-tolerant synonyms only when generalizable",
        "safety_risk": "wrong entity/status filters",
        "improvement_mode": "isolated_only",
        "extended_questions": ["Were names, IDs, dates, status words, and entity words captured?"],
    },
    {
        "stage_id": 5,
        "name": "Deterministic QueryRouter",
        "decision_made": "domain_type, route_type, confidence, candidate tables/APIs.",
        "diagnostic_question": "Is router confidence calibrated against actual correctness?",
        "input_signals_used": ["matching text", "domain keywords", "candidate tables/APIs"],
        "confidence_or_score": "route step confidence",
        "rejected_alternatives_if_available": "implicit keyword scores in route reason",
        "downstream_effect": "seeds QueryAnalysis, context, and plan families",
        "known_failure_examples": ["low confidence may still be correct; high confidence can still have weak answer shape"],
        "possible_improvement": "combine route confidence with relevance margin and template support",
        "safety_risk": "misrouting can cause wrong tool path",
        "improvement_mode": "isolated_only",
        "extended_questions": [
            "Are low-confidence rows actually wrong, or just short prompts?",
            "Does confidence predict strict score?",
        ],
    },
    {
        "stage_id": 6,
        "name": "QueryAnalysis",
        "decision_made": "answer_family, SQL template, API templates, lookup path, API need decision.",
        "diagnostic_question": "Did analysis choose the correct answer family and tool family?",
        "input_signals_used": ["route decision", "tokens", "schema/API relevance"],
        "confidence_or_score": "analysis confidence when available",
        "rejected_alternatives_if_available": "not fully logged; plan ensemble captures some alternatives",
        "downstream_effect": "controls SQL/API template families and answer slots",
        "known_failure_examples": ["correct SQL with weak answer family"],
        "possible_improvement": "audit answer-family alignment before changing templates",
        "safety_risk": "wrong family can silently produce weak answers",
        "improvement_mode": "isolated_only",
        "extended_questions": ["Did the chosen answer family match COUNT/LIST/STATUS/DATE intent?"],
    },
    {
        "stage_id": 7,
        "name": "Relevance scoring",
        "decision_made": "top tables, top APIs, top answer families, join hints.",
        "diagnostic_question": "Did selected context include the true needed source?",
        "input_signals_used": ["tokens", "schema summaries", "endpoint labels"],
        "confidence_or_score": "relevance compact/table/API lists",
        "rejected_alternatives_if_available": "top-k lists in nlp step",
        "downstream_effect": "limits context and template candidates",
        "known_failure_examples": ["synonym gaps can push true source out of top-k"],
        "possible_improvement": "log top-2 margin and compare selected context to executed SQL/API",
        "safety_risk": "wrong table/API context",
        "improvement_mode": "isolated_only",
        "extended_questions": ["Were top-2 candidates close?", "Were wrong tables selected due to missing synonyms?"],
    },
    {
        "stage_id": 8,
        "name": "Metadata/context selection",
        "decision_made": "selected tables, selected columns, selected APIs, compact/full context.",
        "diagnostic_question": "Did context include enough evidence while avoiding token noise?",
        "input_signals_used": ["relevance", "route", "templates", "value retrieval"],
        "confidence_or_score": "metadata/prompt token counts",
        "rejected_alternatives_if_available": "not fully logged",
        "downstream_effect": "sets prompt and trajectory evidence surface",
        "known_failure_examples": ["irrelevant API context can add dry-run noise"],
        "possible_improvement": "require template-required columns in selected context",
        "safety_risk": "missing columns or too much noise",
        "improvement_mode": "isolated_only",
        "extended_questions": ["Did selected context include required columns?", "Did compact context hurt any query?"],
    },
    {
        "stage_id": 9,
        "name": "Plan generation",
        "decision_made": "SQL_FIRST_API_VERIFY plan, SQL/API order, fast path/template/generic plan.",
        "diagnostic_question": "Did the plan pick the right SQL/API path?",
        "input_signals_used": ["analysis", "metadata", "evidence policy"],
        "confidence_or_score": "plan rationale and step families",
        "rejected_alternatives_if_available": "plan ensemble when available",
        "downstream_effect": "determines executable tool calls",
        "known_failure_examples": ["optional dry-run API can hurt answer wording"],
        "possible_improvement": "compare plan family to strict component failures",
        "safety_risk": "invalid SQL/API if validators miss issues",
        "improvement_mode": "isolated_only",
        "extended_questions": ["Did losing candidates have better answer potential?"],
    },
    {
        "stage_id": 10,
        "name": "Plan ensemble selection",
        "decision_made": "selected candidate, rejected candidates, candidate scores.",
        "diagnostic_question": "Did the selected plan actually lead to better strict score?",
        "input_signals_used": ["candidate scores", "tool-call estimates", "validation signals"],
        "confidence_or_score": "optimizer.plan_ensemble.candidate_scores",
        "rejected_alternatives_if_available": "optimizer.plan_ensemble candidate scores/tool calls",
        "downstream_effect": "executes exactly one selected plan",
        "known_failure_examples": ["validator-safe plans may still be answer-weak"],
        "possible_improvement": "add answer-shape/evidence completeness scoring in isolated trials",
        "safety_risk": "executing multiple plans would violate cost assumptions",
        "improvement_mode": "isolated_only",
        "extended_questions": ["Are candidate scores aligned with strict score?"],
    },
    {
        "stage_id": 11,
        "name": "Evidence policy",
        "decision_made": "API_REQUIRED, API_OPTIONAL, API_SKIP.",
        "diagnostic_question": "Are optional dry-run API calls helping or hurting answer score?",
        "input_signals_used": ["route", "analysis", "credential/dry-run state"],
        "confidence_or_score": "plan rationale evidence policy label",
        "rejected_alternatives_if_available": "API optional vs skipped not always logged as alternative",
        "downstream_effect": "can add API calls and dry-run caveats",
        "known_failure_examples": ["SQL fully answers but answer emphasizes unavailable API"],
        "possible_improvement": "isolated dry-run skip/wording variants when SQL answer is complete",
        "safety_risk": "skipping truly required API would lose evidence",
        "improvement_mode": "isolated_only",
        "extended_questions": ["When SQL fully answers, does dry-run API hurt answer score?"],
    },
    {
        "stage_id": 12,
        "name": "Tool-call budget",
        "decision_made": "max SQL calls, max API calls, total tool limit.",
        "diagnostic_question": "Are tool calls being spent where they improve correctness?",
        "input_signals_used": ["plan steps", "call budget", "optimizer actions"],
        "confidence_or_score": "tool_call_count and budget settings",
        "rejected_alternatives_if_available": "deduped/optimized plan actions",
        "downstream_effect": "affects efficiency penalty and answer evidence",
        "known_failure_examples": ["dry-run calls add cost without evidence"],
        "possible_improvement": "penalize optional dry-run when SQL evidence is complete",
        "safety_risk": "over-pruning useful evidence",
        "improvement_mode": "isolated_only",
        "extended_questions": ["Are extra API calls improving correctness?"],
    },
    {
        "stage_id": 13,
        "name": "SQL validation / AST validation",
        "decision_made": "safe or blocked SQL, selected tables/columns, unknown table/column.",
        "diagnostic_question": "Are validators blocking unsafe SQL while preserving valid useful SQL?",
        "input_signals_used": ["generated SQL", "schema index", "read-only checks"],
        "confidence_or_score": "validation.ok/errors/warnings",
        "rejected_alternatives_if_available": "validation errors",
        "downstream_effect": "prevents unsafe SQL execution",
        "known_failure_examples": ["unknown columns or template drift"],
        "possible_improvement": "improve validators only by making valid/invalid separation clearer",
        "safety_risk": "weakening validators is prohibited",
        "improvement_mode": "isolated_or_validator_safe_only",
        "extended_questions": ["Are validators blocking unsafe SQL while preserving valid useful SQL?"],
    },
    {
        "stage_id": 14,
        "name": "API validation",
        "decision_made": "endpoint allowed or blocked, dry-run behavior.",
        "diagnostic_question": "Are API calls valid and useful under missing live credentials?",
        "input_signals_used": ["endpoint catalog", "method/url/params", "credential availability"],
        "confidence_or_score": "api validation ok/errors/warnings",
        "rejected_alternatives_if_available": "validation errors",
        "downstream_effect": "permits catalog-safe Adobe API calls or dry-run records",
        "known_failure_examples": ["unresolved path parameters and optional dry-run calls"],
        "possible_improvement": "endpoint-family trials only if strict and safety gates pass",
        "safety_risk": "unsafe or fabricated API evidence",
        "improvement_mode": "isolated_only",
        "extended_questions": ["Which queries truly need live API?"],
    },
    {
        "stage_id": 15,
        "name": "Execution",
        "decision_made": "SQL result and API result/dry-run result.",
        "diagnostic_question": "Did execution produce useful evidence or just cost?",
        "input_signals_used": ["validated plan", "local DB", "Adobe credentials"],
        "confidence_or_score": "result ok/row_count/dry_run",
        "rejected_alternatives_if_available": "not applicable because exactly one plan executes",
        "downstream_effect": "feeds EvidenceBus and final answer",
        "known_failure_examples": ["dry-run API unavailable under missing credentials"],
        "possible_improvement": "answer wording improvements for dry-run limitations",
        "safety_risk": "fabricated live API evidence is prohibited",
        "improvement_mode": "answer_only_or_isolated",
        "extended_questions": ["Did SQL/API results contain enough evidence to answer directly?"],
    },
    {
        "stage_id": 16,
        "name": "EvidenceBus",
        "decision_made": "forwarded SQL/API facts, IDs/names/counts/timestamps/statuses.",
        "diagnostic_question": "Did the right evidence reach answer synthesis?",
        "input_signals_used": ["tool results", "answer slots", "evidence extraction"],
        "confidence_or_score": "slots_present and unsupported_claims_count",
        "rejected_alternatives_if_available": "not usually logged",
        "downstream_effect": "controls grounded claims in final answer",
        "known_failure_examples": ["SQL fact present but answer omits it"],
        "possible_improvement": "answer-only rewrites with unchanged SQL/API/evidence hashes",
        "safety_risk": "unsupported claims",
        "improvement_mode": "answer_only_isolated",
        "extended_questions": ["Were IDs, names, counts, statuses, and dates forwarded?"],
    },
    {
        "stage_id": 17,
        "name": "Answer slots",
        "decision_made": "answer intent and count/list/status/date/yes-no shape.",
        "diagnostic_question": "Did slots correctly represent the user’s requested answer type?",
        "input_signals_used": ["answer diagnostics", "tool facts", "query intent"],
        "confidence_or_score": "answer_diagnostics slots_present",
        "rejected_alternatives_if_available": "selected_candidate_type when logged",
        "downstream_effect": "affects answer template and shape",
        "known_failure_examples": ["COUNT evidence answered with vague summary"],
        "possible_improvement": "COUNT/LIST/STATUS/WHEN template trials",
        "safety_risk": "shape fixes must preserve evidence hashes",
        "improvement_mode": "answer_only_isolated",
        "extended_questions": ["Does the slot shape match COUNT/LIST/STATUS/DATE intent?"],
    },
    {
        "stage_id": 18,
        "name": "Answer synthesis",
        "decision_made": "final answer wording and dry-run caveat.",
        "diagnostic_question": "Does the answer directly answer the prompt using evidence?",
        "input_signals_used": ["EvidenceBus facts", "answer slots", "dry-run label"],
        "confidence_or_score": "strict answer score",
        "rejected_alternatives_if_available": "answer candidate type if logged",
        "downstream_effect": "dominant current correctness bottleneck",
        "known_failure_examples": ["vague dry-run wording despite complete SQL evidence"],
        "possible_improvement": "answer-only rewrite variants preserving SQL/API/tool/evidence/dry-run hashes",
        "safety_risk": "unsupported answer claims",
        "improvement_mode": "answer_only_isolated",
        "extended_questions": ["Is the answer too vague?", "Does it mention dry-run unnecessarily?"],
    },
    {
        "stage_id": 19,
        "name": "Answer verification/reranking",
        "decision_made": "supported claims, unsupported claims, selected answer candidate.",
        "diagnostic_question": "Is verifier checking groundedness and answer shape, not just literal support?",
        "input_signals_used": ["answer diagnostics", "unsupported claim counts"],
        "confidence_or_score": "verifier_passed and unsupported_claims_count",
        "rejected_alternatives_if_available": "selected_candidate_type",
        "downstream_effect": "should prefer grounded and correctly shaped answers",
        "known_failure_examples": ["technically supported but weakly worded answers"],
        "possible_improvement": "shape-aware verifier scoring in isolated answer-only trials",
        "safety_risk": "rejecting good answers or accepting weak unsupported ones",
        "improvement_mode": "answer_only_isolated",
        "extended_questions": ["Are weak answers passing because claims are supported but badly worded?"],
    },
    {
        "stage_id": 20,
        "name": "Token reduction / packaging",
        "decision_made": "fields reduced, packaged trajectory unchanged enough for reproducibility.",
        "diagnostic_question": "Did token reduction preserve reproducibility and correctness?",
        "input_signals_used": ["packaging policy", "trajectory manifest", "readiness checks"],
        "confidence_or_score": "check_submission_ready and manifest checks",
        "rejected_alternatives_if_available": "full vs reduced trajectory in packaging policy",
        "downstream_effect": "submission size and reproducibility",
        "known_failure_examples": ["removing required trajectory fields would fail readiness/audit"],
        "possible_improvement": "report-only checks unless readiness proves safe",
        "safety_risk": "final submission contamination or irreproducible trajectories",
        "improvement_mode": "promotable_only_with_readiness_pass",
        "extended_questions": ["Did packaged trajectory still preserve original query, tools, answer, tokens, and runtime?"],
    },
]


def main() -> int:
    config = Config.from_env(ROOT)
    payload = run_workflow_decision_audit(config)
    print(
        json.dumps(
            {
                "status": payload["audit"]["status"],
                "query_count": payload["audit"]["total_queries"],
                "map": str(config.outputs_dir / "reports" / "workflow_decision_map.json"),
                "audit": str(config.outputs_dir / "reports" / "workflow_decision_audit.json"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def run_workflow_decision_audit(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    decision_map = build_workflow_decision_map()
    audit = build_workflow_decision_audit(config)
    _write_json_md(reports_dir / "workflow_decision_map", decision_map, render_workflow_decision_map(decision_map))
    _write_json_md(reports_dir / "workflow_decision_audit", audit, render_workflow_decision_audit(audit))
    return {"decision_map": decision_map, "audit": audit}


def build_workflow_decision_map() -> dict[str, Any]:
    return {
        "report_type": "workflow_decision_map",
        "status": "complete",
        "stage_count": len(DECISION_STAGES),
        "methodology": "Diagnose decision stage first, run isolated variants, analyze helped/hurt examples, then decide without automatic promotion.",
        "scope_controls": [
            "Generated diagnostic prompts are coverage-only and cannot claim official strict-score improvement.",
            "Behavior-changing candidates remain isolated behind trial paths until later explicit promotion.",
            "Answer-only variants must preserve SQL/API/tool/evidence/dry-run hashes.",
        ],
        "decision_stages": DECISION_STAGES,
    }


def build_workflow_decision_audit(config: Config) -> dict[str, Any]:
    strict = _load_json(config.outputs_dir / "eval_results_strict.json")
    rows = [
        row
        for row in strict.get("rows", [])
        if isinstance(row, dict) and row.get("strategy") == "SQL_FIRST_API_VERIFY"
    ]
    audit_rows = [_row_from_strict_result(config, row) for row in rows]
    bottlenecks = Counter(row["likely_decision_stage_bottleneck"] for row in audit_rows)
    return redact_secrets(
        {
            "report_type": "workflow_decision_audit",
            "status": "complete" if rows else "missing_strict_eval",
            "source_report": "outputs/eval_results_strict.json",
            "total_queries": len(audit_rows),
            "bottleneck_categories_allowed": sorted(BOTTLENECK_CATEGORIES),
            "bottleneck_distribution": dict(sorted(bottlenecks.items())),
            "highest_priority_candidates": _priority_candidates(audit_rows),
            "methodology_rule": "Do not reject serious candidates after one failed trial; run 3-5 controlled variants before final evidence-backed decisions.",
            "rows": audit_rows,
        }
    )


def _row_from_strict_result(config: Config, row: dict[str, Any]) -> dict[str, Any]:
    trajectory_path = Path(str(row.get("output_dir") or "")) / "trajectory.json"
    trajectory = _load_json(trajectory_path)
    route = _first_step(trajectory, "route")
    nlp = _first_step(trajectory, "nlp")
    plan = _first_step(trajectory, "plan")
    optimizer = _first_step(trajectory, "optimizer")
    answer_diag = _first_step(trajectory, "answer_diagnostics")
    sql_calls = [step for step in trajectory.get("steps", []) if isinstance(step, dict) and step.get("kind") == "sql_call"]
    api_calls = [step for step in trajectory.get("steps", []) if isinstance(step, dict) and step.get("kind") == "api_call"]
    dry_run = any(bool((step.get("result") or {}).get("dry_run")) for step in api_calls)
    selected_tables = _selected_tables(nlp, route, sql_calls)
    selected_apis = _selected_apis(nlp, route, api_calls)
    bottleneck = _classify_bottleneck(row, trajectory, route, answer_diag, dry_run)
    return {
        "query_id": row.get("query_id"),
        "prompt": row.get("query") or trajectory.get("original_query"),
        "route_type": trajectory.get("route_type") or route.get("route_type"),
        "domain_type": trajectory.get("domain_type") or route.get("domain_type"),
        "router_confidence": _round(route.get("confidence")),
        "answer_family": answer_diag.get("answer_family"),
        "answer_intent": answer_diag.get("answer_intent"),
        "selected_tables": selected_tables,
        "selected_apis": selected_apis,
        "selected_plan": {
            "strategy": plan.get("strategy"),
            "rationale": plan.get("rationale"),
            "step_families": [step.get("family") for step in plan.get("steps", []) if isinstance(step, dict)],
        },
        "rejected_plan_candidates": (optimizer.get("plan_ensemble") or {}).get("candidate_scores", {}),
        "sql_calls": [step.get("sql") for step in sql_calls],
        "api_calls": [
            {"method": step.get("method"), "url": step.get("url"), "params": step.get("params")}
            for step in api_calls
        ],
        "dry_run_status": "dry_run" if dry_run else ("no_api_calls" if not api_calls else "live_or_mock_api"),
        "tool_count": row.get("tool_call_count", trajectory.get("tool_call_count")),
        "tokens": row.get("estimated_tokens", trajectory.get("estimated_tokens")),
        "runtime": row.get("runtime", trajectory.get("runtime")),
        "final_answer": trajectory.get("final_answer"),
        "strict_score_components": {
            "sql_score": row.get("sql_score"),
            "api_score": row.get("api_score"),
            "answer_score": row.get("answer_score"),
            "correctness_score": row.get("correctness_score"),
            "final_score": row.get("final_score"),
            "validation_failures": row.get("validation_failures", count_validation_failures(trajectory)),
        },
        "likely_decision_stage_bottleneck": bottleneck,
        "likely_improvement_candidate": _improvement_candidate(bottleneck),
        "baseline_sql_hash": _stable_text_hash(normalize_sql(first_generated_sql(trajectory))),
        "baseline_api_hash": _stable_text_hash(json.dumps(generated_api_calls(trajectory), sort_keys=True, default=str)),
        "selected_evidence_hash": _stable_text_hash(json.dumps({"tables": selected_tables, "apis": selected_apis}, sort_keys=True)),
        "dry_run_label": "dry_run" if dry_run else "not_dry_run",
    }


def _classify_bottleneck(row: dict[str, Any], trajectory: dict[str, Any], route: dict[str, Any], answer_diag: dict[str, Any], dry_run: bool) -> str:
    sql_score = row.get("sql_score")
    api_score = row.get("api_score")
    answer_score = row.get("answer_score")
    confidence = route.get("confidence")
    validation_failures = row.get("validation_failures", count_validation_failures(trajectory))
    if validation_failures:
        return "unsupported_answer_claim"
    if isinstance(confidence, (int, float)) and confidence >= 0.8 and isinstance(row.get("final_score"), (int, float)) and row["final_score"] < 0.55:
        return "confidence_miscalibrated"
    if _low(sql_score):
        return "wrong_sql_template"
    if _low(api_score):
        return "wrong_api_template"
    if dry_run and isinstance(answer_score, (int, float)) and answer_score < 0.55:
        return "unnecessary_dry_run_api"
    if isinstance(answer_score, (int, float)) and answer_score < 0.55:
        return "answer_shape_weak"
    if int(row.get("tool_call_count") or trajectory.get("tool_call_count") or 0) > 3:
        return "tool_count_high"
    if int(row.get("estimated_tokens") or trajectory.get("estimated_tokens") or 0) > 1800:
        return "token_cost_high"
    return "no_clear_bottleneck"


def _priority_candidates(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts = Counter(row["likely_decision_stage_bottleneck"] for row in rows)
    mapping = {
        "answer_shape_weak": "Answer-only rewrite with invariant hashes",
        "unnecessary_dry_run_api": "Dry-run wording/API optional skip isolated trial",
        "confidence_miscalibrated": "Router confidence calibration audit",
        "wrong_sql_template": "Plan/template family isolated trial",
        "wrong_api_template": "API endpoint-family isolated trial",
        "tool_count_high": "Tool-call budget isolated trial",
    }
    candidates = [
        {"candidate": mapping.get(category, "No clear candidate"), "bottleneck": category, "affected_rows": count}
        for category, count in counts.most_common()
        if category in mapping
    ]
    return candidates[:5]


def _improvement_candidate(category: str) -> str:
    return {
        "answer_shape_weak": "answer_only_rewrite_trial",
        "unnecessary_dry_run_api": "dry_run_wording_or_optional_api_skip_trial",
        "confidence_miscalibrated": "confidence_calibration_trial",
        "wrong_sql_template": "plan_template_trial",
        "wrong_api_template": "api_template_trial",
        "tool_count_high": "tool_budget_trial",
        "token_cost_high": "context_or_token_reduction_audit",
        "semantic_router_no_effect": "semantic_router_narrowing_trial",
    }.get(category, "monitor_only")


def render_workflow_decision_map(payload: dict[str, Any]) -> str:
    lines = [
        "# Workflow Decision Map",
        "",
        payload["methodology"],
        "",
        "## Scope Controls",
        "",
        *[f"- {item}" for item in payload["scope_controls"]],
        "",
        "## Decision Stages",
        "",
    ]
    for stage in payload["decision_stages"]:
        lines.extend(
            [
                f"### {stage['stage_id']}. {stage['name']}",
                "",
                f"- Decision made: {stage['decision_made']}",
                f"- Diagnostic question: {stage['diagnostic_question']}",
                f"- Input signals: {', '.join(stage['input_signals_used'])}",
                f"- Confidence/score: {stage['confidence_or_score']}",
                f"- Downstream effect: {stage['downstream_effect']}",
                f"- Possible improvement: {stage['possible_improvement']}",
                f"- Safety risk: {stage['safety_risk']}",
                f"- Improvement mode: `{stage['improvement_mode']}`",
                "",
                "Extended questions:",
                *[f"- {question}" for question in stage["extended_questions"]],
                "",
            ]
        )
    return "\n".join(lines)


def render_workflow_decision_audit(payload: dict[str, Any]) -> str:
    lines = [
        "# Workflow Decision Audit",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Total SQL_FIRST_API_VERIFY public/dev rows: `{payload.get('total_queries')}`",
        f"- Methodology rule: {payload.get('methodology_rule')}",
        "",
        "## Bottleneck Distribution",
        "",
    ]
    for key, value in (payload.get("bottleneck_distribution") or {}).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Highest-Priority Candidates", ""])
    for item in payload.get("highest_priority_candidates") or []:
        lines.append(f"- `{item['candidate']}` from `{item['bottleneck']}` affecting `{item['affected_rows']}` rows")
    lines.extend(["", "## Per-Query Audit", ""])
    for row in (payload.get("rows") or [])[:40]:
        score = row.get("strict_score_components", {})
        lines.append(
            f"- `{row.get('query_id')}`: route=`{row.get('route_type')}/{row.get('domain_type')}` "
            f"answer=`{score.get('answer_score')}` final=`{score.get('final_score')}` "
            f"bottleneck=`{row.get('likely_decision_stage_bottleneck')}`"
        )
    return "\n".join(lines) + "\n"


def _write_json_md(stem: Path, payload: dict[str, Any], markdown: str) -> None:
    safe = redact_secrets(payload)
    stem.with_suffix(".json").write_text(json.dumps(safe, indent=2, sort_keys=True, default=str), encoding="utf-8")
    stem.with_suffix(".md").write_text(markdown, encoding="utf-8")


def _first_step(trajectory: dict[str, Any], kind: str) -> dict[str, Any]:
    for step in trajectory.get("steps", []):
        if isinstance(step, dict) and step.get("kind") == kind:
            return step
    return {}


def _selected_tables(nlp: dict[str, Any], route: dict[str, Any], sql_calls: list[dict[str, Any]]) -> list[str]:
    tables = list((nlp.get("relevance") or {}).get("tables") or [])
    tables.extend(route.get("candidate_tables") or [])
    for call in sql_calls:
        sql = str(call.get("sql") or "")
        for token in sql.replace('"', " ").replace(".", " ").split():
            if token.startswith("dim_") or token.startswith("br_") or token.startswith("fact_"):
                tables.append(token)
    return _dedupe(tables)


def _selected_apis(nlp: dict[str, Any], route: dict[str, Any], api_calls: list[dict[str, Any]]) -> list[str]:
    apis = list((nlp.get("relevance") or {}).get("apis") or [])
    for item in route.get("candidate_apis") or []:
        if isinstance(item, dict):
            apis.append(str(item.get("id") or item.get("path") or ""))
    for call in api_calls:
        apis.append(str(call.get("url") or ""))
    return _dedupe([api for api in apis if api])


def _dedupe(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        text = str(value)
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def _low(value: Any) -> bool:
    return isinstance(value, (int, float)) and float(value) < 0.6


def _round(value: Any) -> float | None:
    return round(float(value), 4) if isinstance(value, (int, float)) else None


def _stable_text_hash(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


if __name__ == "__main__":
    raise SystemExit(main())
