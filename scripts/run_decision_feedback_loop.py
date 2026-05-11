#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.trajectory import redact_secrets
from scripts.load_local_env import load_local_env
from scripts.run_llm_semantic_router_isolated_trial import run_llm_semantic_router_isolated_trial


BASELINE_STRICT_SCORE = 0.6553
BEST_ISOLATED_SCORE = 0.6558
SEMANTIC_ROUTER_VARIANTS = [
    {
        "variant": "narrow_eligibility",
        "iteration": 1,
        "hypothesis": "The first broad non-shadow semantic-router variant regressed; narrower eligibility may preserve useful fallback behavior while avoiding high-confidence perturbations.",
        "exact_isolated_change": "Apply hints only for UNKNOWN, confidence < 0.35, or explicit ambiguous phrase plus weak schema relevance.",
    },
    {
        "variant": "no_intent_application",
        "iteration": 2,
        "hypothesis": "The first trial changed intent metadata without improving SQL/API/answer; recording intent but not applying it may remove noise.",
        "exact_isolated_change": "Allow route/domain/candidate priority changes but keep helper intent as metadata only.",
    },
    {
        "variant": "priority_only",
        "iteration": 3,
        "hypothesis": "Validated semantic hints may be useful as table/API priority signals without changing route, domain, or intent.",
        "exact_isolated_change": "Only prepend validated candidate tables/APIs. Do not change route_type, domain_type, or answer intent.",
    },
    {
        "variant": "unknown_only",
        "iteration": 4,
        "hypothesis": "The helper may be safest as a true fallback only when deterministic routing cannot identify a domain.",
        "exact_isolated_change": "Apply validated hints only when deterministic domain_type is UNKNOWN.",
    },
    {
        "variant": "no_api_forcing",
        "iteration": 5,
        "hypothesis": "Dry-run API behavior may hurt answers; semantic hints should not force API routes unless the existing route already expects API evidence.",
        "exact_isolated_change": "Do not allow helper route changes into API_ONLY or SQL_THEN_API when the deterministic route is SQL_ONLY.",
    },
]


def main() -> int:
    args = parse_args()
    config = Config.from_env(ROOT)
    load_local_env(config.project_root)
    report = run_decision_feedback_loop(config, limit=args.limit, full=args.full, variants=args.variants)
    print(
        json.dumps(
            {
                "status": report["final"].get("status"),
                "iterations": report["final"].get("iteration_count"),
                "final_recommendation": report["final"].get("final_recommendation"),
                "index": str(config.outputs_dir / "reports" / "improvement_feedback_loop_index.json"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run isolated decision-stage feedback loops.")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--full", action="store_true")
    parser.add_argument(
        "--variants",
        default=",".join(item["variant"] for item in SEMANTIC_ROUTER_VARIANTS),
        help="Comma-separated semantic-router trial variants to run.",
    )
    return parser.parse_args()


def run_decision_feedback_loop(
    config: Config | None = None,
    *,
    limit: int = 50,
    full: bool = False,
    variants: str | list[str] | None = None,
) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    selected = _selected_variants(variants)
    plan = _semantic_router_plan(selected)
    _write_report(reports_dir / "feedback_loop_semantic_router_plan", plan, _render_plan(plan))

    iteration_reports: list[dict[str, Any]] = []
    for variant_info in selected:
        trial = run_llm_semantic_router_isolated_trial(
            config,
            limit=limit,
            full=full,
            public_only=True,
            generated_only=False,
            clean=True,
            trial_policy=variant_info["variant"],
            output_root_name=f"llm_semantic_router_feedback_loop/{variant_info['variant']}",
            write_reports=False,
        )
        iteration = _build_iteration_report(variant_info, trial)
        iteration_reports.append(iteration)
        stem = reports_dir / f"feedback_loop_semantic_router_iteration_{variant_info['iteration']}"
        _write_report(stem, iteration, _render_iteration(iteration))

    final = _build_final_report(plan, iteration_reports)
    index = _build_feedback_loop_index(final, iteration_reports)
    summary = _build_decision_stage_improvement_summary(final, iteration_reports)
    decision_plan = _build_decision_improvement_plan(summary)
    decision_trial = _build_decision_improvement_trial(final)
    _write_report(reports_dir / "feedback_loop_semantic_router_final", final, _render_final(final))
    _write_report(reports_dir / "improvement_feedback_loop_index", index, _render_index(index))
    _write_report(reports_dir / "decision_stage_improvement_summary", summary, _render_summary(summary))
    _write_report(reports_dir / "decision_improvement_plan", decision_plan, _render_decision_plan(decision_plan))
    _write_report(reports_dir / "decision_improvement_trial", decision_trial, _render_decision_trial(decision_trial))
    return {
        "plan": plan,
        "iterations": iteration_reports,
        "final": final,
        "index": index,
        "summary": summary,
        "decision_plan": decision_plan,
        "decision_trial": decision_trial,
    }


def answer_only_invariants_preserved(baseline: dict[str, Any], trial: dict[str, Any]) -> dict[str, Any]:
    checks = {
        "sql_hash_unchanged": baseline.get("sql_hash") == trial.get("sql_hash"),
        "api_hash_unchanged": baseline.get("api_hash") == trial.get("api_hash"),
        "tool_count_unchanged": baseline.get("tool_count") == trial.get("tool_count"),
        "selected_evidence_hash_unchanged": baseline.get("selected_evidence_hash") == trial.get("selected_evidence_hash"),
        "dry_run_label_unchanged": baseline.get("dry_run_label") == trial.get("dry_run_label"),
    }
    return {"ok": all(checks.values()), "checks": checks}


def _selected_variants(variants: str | list[str] | None) -> list[dict[str, Any]]:
    wanted = variants
    if isinstance(wanted, str):
        wanted = [item.strip() for item in wanted.split(",") if item.strip()]
    wanted_set = set(wanted or [item["variant"] for item in SEMANTIC_ROUTER_VARIANTS])
    selected = [item for item in SEMANTIC_ROUTER_VARIANTS if item["variant"] in wanted_set]
    if not selected:
        raise ValueError("No recognized semantic-router feedback-loop variants selected.")
    return selected


def _semantic_router_plan(variants: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "report_type": "feedback_loop_semantic_router_plan",
        "candidate_name": "LLM Semantic Routing Helper",
        "target_decision_stage": "Deterministic QueryRouter / QueryAnalysis semantic fallback",
        "baseline_score": BASELINE_STRICT_SCORE,
        "best_isolated_score": BEST_ISOLATED_SCORE,
        "known_prior_result": {
            "variant": "broad_non_shadow",
            "strict_delta": -0.0031,
            "conclusion": "The first broad non-shadow semantic-router variant regressed; this does not disprove the entire semantic-router idea.",
        },
        "hypothesis": "Validated semantic hints may still be useful if applied more narrowly or only as candidate-priority metadata.",
        "variants": variants,
        "safety_controls": [
            "Default packaged ENABLE_LLM_SEMANTIC_ROUTER remains false.",
            "Default LLM_SEMANTIC_ROUTER_SHADOW_ONLY remains true.",
            "All variant runs write only isolated outputs under outputs/llm_semantic_router_feedback_loop/.",
            "No automatic promotion is performed.",
            "Generated diagnostic prompts are coverage-only and not promotion evidence.",
        ],
    }


def _build_iteration_report(variant_info: dict[str, Any], trial: dict[str, Any]) -> dict[str, Any]:
    strict_delta = trial.get("strict_score_delta")
    answer_delta = trial.get("answer_score_delta")
    sql_delta = trial.get("sql_score_delta")
    api_delta = trial.get("api_score_delta")
    tool_delta = trial.get("tool_count_delta_avg")
    token_delta = trial.get("estimated_token_delta_avg")
    runtime_delta = trial.get("runtime_delta_avg")
    classification, recommendation = _classify_iteration(trial)
    return redact_secrets(
        {
            "report_type": "feedback_loop_semantic_router_iteration",
            "candidate_name": "LLM Semantic Routing Helper",
            "iteration": variant_info["iteration"],
            "variant_name": variant_info["variant"],
            "target_decision_stage": "Query routing / domain detection / candidate table/API priority",
            "hypothesis": variant_info["hypothesis"],
            "exact_change_made": variant_info["exact_isolated_change"],
            "why_chosen_based_on_previous_failure": "The broad variant regressed or changed metadata too often; this variant restricts the application surface.",
            "isolated_output_root": trial.get("output_root"),
            "status": trial.get("status"),
            "strict_score_delta": strict_delta,
            "answer_score_delta": answer_delta,
            "sql_score_delta": sql_delta,
            "api_score_delta": api_delta,
            "tool_count_delta": tool_delta,
            "token_delta": token_delta,
            "runtime_delta": runtime_delta,
            "route_changed_count": trial.get("route_changed_count"),
            "domain_changed_count": trial.get("domain_changed_count"),
            "intent_changed_count": trial.get("intent_changed_count"),
            "sql_changed_count": trial.get("sql_changed_count"),
            "api_changed_count": trial.get("api_changed_count"),
            "answer_changed_count": trial.get("answer_changed_count"),
            "failures_introduced_count": trial.get("failures_introduced_count"),
            "failures_fixed_count": trial.get("failures_fixed_count"),
            "safety_failures": trial.get("safety_failures") or [],
            "examples_helped": _compact_examples(trial.get("where_semantic_routing_helped") or []),
            "examples_hurt": _compact_examples(trial.get("where_semantic_routing_hurt_or_was_risky") or []),
            "what_was_learned": _lesson_for_variant(variant_info["variant"], trial, classification),
            "next_iteration_recommendation": _next_iteration_recommendation(variant_info["iteration"], classification),
            "outcome_classification": classification,
            "recommendation": recommendation,
            "official_promotion_performed": False,
            "packaged_runtime_affected": False,
            "generated_prompt_score_claim": False,
            "source_trial_report_type": trial.get("report_type"),
        }
    )


def _classify_iteration(trial: dict[str, Any]) -> tuple[str, str]:
    strict_delta = trial.get("strict_score_delta")
    safety_failures = trial.get("safety_failures") or []
    if safety_failures or (isinstance(strict_delta, (int, float)) and strict_delta < 0):
        return "variant_failed", "do_not_promote"
    if isinstance(strict_delta, (int, float)) and strict_delta > 0:
        return "candidate_eligible_for_future_limited_promotion", "candidate_for_limited_promotion"
    subcategory_improved = any(
        isinstance(trial.get(key), (int, float)) and float(trial[key]) > 0
        for key in ["answer_score_delta", "sql_score_delta", "api_score_delta"]
    ) or int(trial.get("failures_fixed_count") or 0) > 0
    if subcategory_improved:
        return "candidate_partially_useful", "locally_useful_but_not_promotable"
    return "variant_failed", "do_not_promote"


def _build_final_report(plan: dict[str, Any], iterations: list[dict[str, Any]]) -> dict[str, Any]:
    best = _best_iteration(iterations)
    worst = _worst_iteration(iterations)
    classifications = Counter(item["outcome_classification"] for item in iterations)
    if iterations and all(item.get("status") == "skipped" for item in iterations):
        final_recommendation = "variant_failed"
    elif any(item["outcome_classification"] == "candidate_eligible_for_future_limited_promotion" for item in iterations):
        final_recommendation = "candidate_eligible_for_future_limited_promotion"
    elif any(item["outcome_classification"] == "candidate_partially_useful" for item in iterations):
        final_recommendation = "candidate_partially_useful"
    elif len(iterations) >= 4:
        final_recommendation = "candidate_not_viable_after_feedback_loops"
    else:
        final_recommendation = "variant_failed"
    return redact_secrets(
        {
            "report_type": "feedback_loop_semantic_router_final",
            "status": "complete",
            "candidate_name": plan["candidate_name"],
            "target_decision_stage": plan["target_decision_stage"],
            "iteration_count": len(iterations),
            "baseline_score": BASELINE_STRICT_SCORE,
            "best_isolated_score": BEST_ISOLATED_SCORE,
            "best_variant": best,
            "worst_regression": worst,
            "classification_counts": dict(classifications),
            "final_recommendation": final_recommendation,
            "final_recommendation_label": _recommendation_label(final_recommendation),
            "evidence_summary": _final_evidence_summary(iterations, final_recommendation),
            "promoted_changes": [],
            "shadow_or_isolated_only_changes": [item["variant_name"] for item in iterations],
            "reverted_changes": [],
            "packaged_runtime_affected": False,
            "no_automatic_promotion": True,
            "important_distinction": "The first broad non-shadow variant regressed; these reports evaluate controlled variants and do not claim the whole semantic-router idea is universally useless.",
            "iterations": iterations,
        }
    )


def _build_feedback_loop_index(final: dict[str, Any], iterations: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "report_type": "improvement_feedback_loop_index",
        "message": "Decision-stage improvements require hypothesis, isolated trial, failure analysis, 3-5 controlled variants, and evidence-backed decision.",
        "candidates": [
            {
                "candidate_name": "LLM Semantic Routing Helper",
                "target_decision_stage": final["target_decision_stage"],
                "baseline_score": final["baseline_score"],
                "iteration_count": final["iteration_count"],
                "attempted_variants": [item["variant_name"] for item in iterations],
                "best_isolated_score": _best_score(iterations),
                "worst_regression": final["worst_regression"],
                "final_recommendation": final["final_recommendation"],
                "source_report": "outputs/reports/feedback_loop_semantic_router_final.md",
            }
        ],
    }


def _build_decision_stage_improvement_summary(final: dict[str, Any], iterations: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "report_type": "decision_stage_improvement_summary",
        "decision_stages_audited": "20 stages in workflow_decision_map",
        "candidates_tested": ["LLM Semantic Routing Helper"],
        "iterations_by_candidate": {"LLM Semantic Routing Helper": len(iterations)},
        "best_score_reached": _best_score(iterations),
        "best_variant": final.get("best_variant"),
        "worst_regression": final.get("worst_regression"),
        "packaged_runtime_changed": False,
        "current_decision": final.get("final_recommendation"),
        "next_best_candidate": "Live Adobe API readiness / response parser / EvidenceBus API evidence pipeline, because future production behavior should preserve API_REQUIRED live evidence instead of optimizing mainly for missing-credential dry-run artifacts. Answer-only rewrite remains the secondary candidate.",
        "scope_control": "Do not implement another behavior-changing candidate family in this diff unless separately isolated and reported.",
    }


def _build_decision_improvement_plan(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "report_type": "decision_improvement_plan",
        "selected_decision_stage": "Live API execution / response parsing / EvidenceBus API evidence pipeline",
        "why_this_is_best_target": summary["next_best_candidate"],
        "affected_files": [],
        "expected_score_or_efficiency_impact": "Infrastructure readiness only; no strict-score claim until live Adobe credentials enable safe evaluation.",
        "safety_risk": "Live API trials must be GET-only by default, redact credentials, never fabricate evidence, and never overwrite official eval or final-submission artifacts.",
        "rollback_condition": "Any credential leak, mutation-capable live API call, official artifact overwrite, strict/readiness/security regression, or final-submission format change.",
        "validation_commands": [
            "python3 -m pytest -q",
            "python3 scripts/run_dev_eval.py --strict",
            "python3 scripts/run_hidden_style_eval.py",
            "python3 scripts/check_submission_ready.py",
        ],
        "implemented_in_this_diff": False,
        "reason_not_implemented_now": "Live-readiness implementation is tracked by the dedicated live Adobe API readiness pass and remains infrastructure validation only.",
    }


def _build_decision_improvement_trial(final: dict[str, Any]) -> dict[str, Any]:
    return {
        "report_type": "decision_improvement_trial",
        "candidate_tested_this_pass": "LLM Semantic Routing Helper feedback-loop variants",
        "baseline_strict_score": BASELINE_STRICT_SCORE,
        "trial_strict_score": _best_score(final.get("iterations") or []),
        "strict_delta": _best_delta(final.get("iterations") or []),
        "answer_score_delta": _best_delta(final.get("iterations") or [], "answer_score_delta"),
        "sql_score_delta": _best_delta(final.get("iterations") or [], "sql_score_delta"),
        "api_score_delta": _best_delta(final.get("iterations") or [], "api_score_delta"),
        "tool_count_delta": _best_delta(final.get("iterations") or [], "tool_count_delta"),
        "token_delta": _best_delta(final.get("iterations") or [], "token_delta"),
        "runtime_delta": _best_delta(final.get("iterations") or [], "runtime_delta"),
        "hidden_style_result": "validated separately by scripts/run_hidden_style_eval.py",
        "safety_failures": [failure for item in final.get("iterations") or [] for failure in item.get("safety_failures") or []],
        "examples_helped": [example for item in final.get("iterations") or [] for example in item.get("examples_helped") or []][:8],
        "examples_hurt": [example for item in final.get("iterations") or [] for example in item.get("examples_hurt") or []][:8],
        "recommendation": final.get("final_recommendation"),
        "promotion_performed": False,
        "generated_prompt_score_claim": False,
    }


def _compact_examples(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for row in rows[:6]:
        out.append(
            {
                "query_id": row.get("query_id"),
                "prompt": str(row.get("prompt") or "")[:180],
                "strict_delta": row.get("strict_final_score_delta"),
                "answer_delta": row.get("answer_score_delta"),
                "tool_delta": row.get("tool_count_delta"),
                "hint_application_reason": row.get("hint_application_reason"),
                "baseline_answer": str(row.get("baseline_answer") or "")[:220],
                "trial_answer": str(row.get("trial_answer") or "")[:220],
            }
        )
    return out


def _lesson_for_variant(variant: str, trial: dict[str, Any], classification: str) -> str:
    if trial.get("status") == "skipped":
        return "Live SDK backend was unavailable, so this iteration remains structurally prepared but not empirically scored."
    if classification == "candidate_eligible_for_future_limited_promotion":
        return f"{variant} improved strict score in isolation; promotion still requires separate human approval and gates."
    if classification == "candidate_partially_useful":
        return f"{variant} improved a subcategory without proving total strict-score improvement."
    if trial.get("route_changed_count") == trial.get("domain_changed_count") == trial.get("sql_changed_count") == 0:
        return f"{variant} mostly had no runtime effect, so LLM cost is hard to justify for packaged use."
    return f"{variant} did not beat the packaged baseline under isolated strict comparison."


def _next_iteration_recommendation(iteration: int, classification: str) -> str:
    if classification == "candidate_eligible_for_future_limited_promotion":
        return "Stop loop and prepare human-reviewed limited-promotion evidence; do not auto-promote."
    if iteration < len(SEMANTIC_ROUTER_VARIANTS):
        return f"Run controlled variant {iteration + 1}; one failed variant is not proof that the candidate is impossible."
    return "Summarize all variants and keep the helper disabled/shadow-only unless a later explicit promotion is approved."


def _best_iteration(iterations: list[dict[str, Any]]) -> dict[str, Any] | None:
    scored = [item for item in iterations if isinstance(item.get("strict_score_delta"), (int, float))]
    if not scored:
        return None
    best = max(scored, key=lambda item: float(item["strict_score_delta"]))
    return {"variant": best["variant_name"], "strict_delta": best["strict_score_delta"], "recommendation": best["recommendation"]}


def _worst_iteration(iterations: list[dict[str, Any]]) -> dict[str, Any] | None:
    scored = [item for item in iterations if isinstance(item.get("strict_score_delta"), (int, float))]
    if not scored:
        return None
    worst = min(scored, key=lambda item: float(item["strict_score_delta"]))
    return {"variant": worst["variant_name"], "strict_delta": worst["strict_score_delta"], "recommendation": worst["recommendation"]}


def _best_score(iterations: list[dict[str, Any]]) -> float | None:
    deltas = [item.get("strict_score_delta") for item in iterations if isinstance(item.get("strict_score_delta"), (int, float))]
    if not deltas:
        return None
    return round(BASELINE_STRICT_SCORE + max(float(delta) for delta in deltas), 4)


def _best_delta(iterations: list[dict[str, Any]], key: str = "strict_score_delta") -> float | None:
    values = [item.get(key) for item in iterations if isinstance(item.get(key), (int, float))]
    return round(max(float(value) for value in values), 4) if values else None


def _recommendation_label(final_recommendation: str) -> str:
    return {
        "variant_failed": "variant failed",
        "candidate_partially_useful": "candidate partially useful",
        "candidate_not_viable_after_feedback_loops": "candidate not viable after feedback loops",
        "candidate_eligible_for_future_limited_promotion": "candidate eligible for future limited promotion",
    }.get(final_recommendation, final_recommendation)


def _final_evidence_summary(iterations: list[dict[str, Any]], recommendation: str) -> str:
    if recommendation == "candidate_not_viable_after_feedback_loops":
        return "At least four controlled variants were tested without strict-score improvement or meaningful safe subcategory gains."
    if recommendation == "candidate_partially_useful":
        return "At least one variant improved a component or fixed examples, but total strict score did not justify promotion."
    if recommendation == "candidate_eligible_for_future_limited_promotion":
        return "A variant improved strict score in isolation, but this pass still performs no automatic promotion."
    return "Tested variants did not improve strict score enough for promotion."


def _write_report(stem: Path, payload: dict[str, Any], markdown: str) -> None:
    safe = redact_secrets(payload)
    stem.with_suffix(".json").write_text(json.dumps(safe, indent=2, sort_keys=True, default=str), encoding="utf-8")
    stem.with_suffix(".md").write_text(markdown, encoding="utf-8")


def _render_plan(payload: dict[str, Any]) -> str:
    lines = [
        "# Semantic Router Feedback Loop Plan",
        "",
        f"- Candidate: `{payload['candidate_name']}`",
        f"- Target stage: `{payload['target_decision_stage']}`",
        f"- Baseline score: `{payload['baseline_score']}`",
        f"- Prior broad variant strict delta: `{payload['known_prior_result']['strict_delta']}`",
        f"- Prior conclusion: {payload['known_prior_result']['conclusion']}",
        "",
        "## Variants",
        "",
    ]
    lines.extend(f"- Iteration {item['iteration']}: `{item['variant']}` - {item['hypothesis']}" for item in payload["variants"])
    return "\n".join(lines) + "\n"


def _render_iteration(payload: dict[str, Any]) -> str:
    lines = [
        f"# Semantic Router Feedback Loop Iteration {payload['iteration']}",
        "",
        f"- Variant: `{payload['variant_name']}`",
        f"- Status: `{payload['status']}`",
        f"- Outcome classification: `{payload['outcome_classification']}`",
        f"- Recommendation: `{payload['recommendation']}`",
        f"- Strict delta: `{payload['strict_score_delta']}`",
        f"- Answer/SQL/API deltas: `{payload['answer_score_delta']}` / `{payload['sql_score_delta']}` / `{payload['api_score_delta']}`",
        f"- Tool/token/runtime deltas: `{payload['tool_count_delta']}` / `{payload['token_delta']}` / `{payload['runtime_delta']}`",
        f"- Packaged runtime affected: `{payload['packaged_runtime_affected']}`",
        "",
        "## Lesson",
        "",
        payload["what_was_learned"],
        "",
        "## Helped Examples",
        "",
    ]
    lines.extend(_example_lines(payload.get("examples_helped") or []))
    lines.extend(["", "## Hurt Or Risky Examples", ""])
    lines.extend(_example_lines(payload.get("examples_hurt") or []))
    return "\n".join(lines) + "\n"


def _render_final(payload: dict[str, Any]) -> str:
    lines = [
        "# Semantic Router Feedback Loop Final",
        "",
        f"- Iterations: `{payload['iteration_count']}`",
        f"- Final recommendation: `{payload['final_recommendation']}`",
        f"- Recommendation label: `{payload['final_recommendation_label']}`",
        f"- Best variant: `{payload.get('best_variant')}`",
        f"- Worst regression: `{payload.get('worst_regression')}`",
        f"- Packaged runtime affected: `{payload['packaged_runtime_affected']}`",
        "",
        payload["important_distinction"],
        "",
        "## Evidence Summary",
        "",
        payload["evidence_summary"],
        "",
    ]
    return "\n".join(lines)


def _render_index(payload: dict[str, Any]) -> str:
    lines = ["# Improvement Feedback Loop Index", "", payload["message"], "", "## Candidates", ""]
    for item in payload["candidates"]:
        lines.append(
            f"- `{item['candidate_name']}`: variants={item['attempted_variants']}; "
            f"recommendation=`{item['final_recommendation']}`; report=`{item['source_report']}`"
        )
    return "\n".join(lines) + "\n"


def _render_summary(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Decision Stage Improvement Summary",
            "",
            f"- Decision stages audited: `{payload['decision_stages_audited']}`",
            f"- Candidates tested: `{payload['candidates_tested']}`",
            f"- Best score reached: `{payload['best_score_reached']}`",
            f"- Current decision: `{payload['current_decision']}`",
            f"- Packaged runtime changed: `{payload['packaged_runtime_changed']}`",
            f"- Next best candidate: {payload['next_best_candidate']}",
            "",
        ]
    )


def _render_decision_plan(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Decision Improvement Plan",
            "",
            f"- Selected decision stage: `{payload['selected_decision_stage']}`",
            f"- Implemented in this diff: `{payload['implemented_in_this_diff']}`",
            f"- Why: {payload['why_this_is_best_target']}",
            f"- Safety risk: {payload['safety_risk']}",
            f"- Rollback condition: {payload['rollback_condition']}",
            "",
        ]
    )


def _render_decision_trial(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Decision Improvement Trial",
            "",
            f"- Candidate tested this pass: `{payload['candidate_tested_this_pass']}`",
            f"- Baseline strict score: `{payload['baseline_strict_score']}`",
            f"- Best trial strict score: `{payload['trial_strict_score']}`",
            f"- Strict delta: `{payload['strict_delta']}`",
            f"- Recommendation: `{payload['recommendation']}`",
            f"- Promotion performed: `{payload['promotion_performed']}`",
            f"- Generated prompt score claim: `{payload['generated_prompt_score_claim']}`",
            "",
        ]
    )


def _example_lines(examples: list[dict[str, Any]]) -> list[str]:
    if not examples:
        return ["- None identified."]
    return [
        f"- `{item.get('query_id')}` delta=`{item.get('strict_delta')}` answer_delta=`{item.get('answer_delta')}` prompt={json.dumps(item.get('prompt', '')[:120])}"
        for item in examples[:6]
    ]


if __name__ == "__main__":
    raise SystemExit(main())
