from __future__ import annotations

from typing import Any

from visualization_report_helpers import (
    PRIMARY_QUERY_ID,
    UNAVAILABLE,
    get_path,
    load_json,
    mermaid_label,
    primary_example_context,
    primary_prompt_steps,
    runtime_badge,
    runtime_path_for_status,
    status_badge,
    visual_summary,
)


TECHNIQUE_GROUPS = {
    "Query understanding / routing": [
        "query_normalizer",
        "query_tokens",
        "relevance_scorer",
        "query_analysis",
        "metadata_selector",
        "prompt_router",
        "simple_prompt_gate",
    ],
    "Planning / execution": [
        "SQL_FIRST_API_VERIFY",
        "SQL templates",
        "API templates",
        "planner",
        "executor",
        "endpoint catalog",
        "endpoint family ranker",
        "answer-shape v2",
        "supportable answer rewriter",
        "SQL-only API-skip guard",
        "official-token reduction",
    ],
    "Evidence / context / optimization": [
        "evidence_bus",
        "context cards",
        "fast paths",
        "call budget",
        "evidence policy",
        "local knowledge index",
        "cache",
        "plan optimizer",
        "compact context experiment",
        "shadow repair",
        "AST-guided SQL candidate canary",
        "endpoint-family tie-break v2",
        "live-mode readiness diagnostics",
    ],
    "Safety / evaluation": [
        "answer verifier",
        "answer reranker",
        "hidden-style eval",
        "leakage / robustness checks",
        "secret scan",
        "package readiness checks",
        "OpenRouter LLM rewrite search",
        "SDK LLM baseline framework",
        "supportable dry-run rewrite validation",
        "autonomous packaged trials",
    ],
}


def build_primary_context() -> dict[str, Any]:
    context = primary_example_context(PRIMARY_QUERY_ID)
    context["steps"] = primary_prompt_steps(context)
    return context


def bottleneck_summary(context: dict[str, Any]) -> dict[str, Any]:
    return {
        "query_id": context["query_id"],
        "api_score": context["api_score"],
        "sql_score": context.get("sql_score"),
        "answer_score": context["answer_score"],
        "strict_score": context["strict_score"],
        "correctness_score": context["correctness_score"],
        "main_bottleneck": context["main_bottleneck"],
        "dry_run_status": context["api_status"],
        "sql_artifacts": context.get("sql_artifacts", {}),
    }


def current_state() -> dict[str, Any]:
    winner = load_json("outputs/winner_readiness_report.json", {})
    packaged = winner.get("packaged", {})
    hidden = winner.get("hidden_style_eval", {})
    auto_trial = winner.get("autonomous_packaged_trial", {})
    llm = winner.get("llm_answer_rewrite_search", load_json("outputs/llm_answer_rewrite_search.json", {}).get("summary", {}))
    llm_baseline = load_json("outputs/llm_baseline_eval_report.json", {})
    llm_strict = load_json("outputs/llm_strict_baseline_eval.json", {})
    llm_sdk = load_json("outputs/llm_sdk_backend_check.json", {})
    live = winner.get("live_mode_readiness_report", load_json("outputs/live_mode_readiness_report.json", {}).get("summary", {}))
    answer_shape = winner.get("answer_shape_v2_ab_eval", load_json("outputs/answer_shape_v2_ab_eval.json", {}).get("summary", {}))
    endpoint_tie = winner.get("endpoint_family_tiebreak_v2_shadow", load_json("outputs/endpoint_family_tiebreak_v2_shadow.json", {}).get("summary", {}))
    accuracy = load_json("outputs/accuracy_promotion_decision_report.json", {})
    return {
        "packaged_strict_score": packaged.get("strict_final_score", UNAVAILABLE),
        "best_isolated_score": auto_trial.get("strict_final_score", UNAVAILABLE),
        "target_score": 0.75,
        "correctness": packaged.get("strict_correctness", UNAVAILABLE),
        "tokens": packaged.get("estimated_tokens", UNAVAILABLE),
        "runtime": packaged.get("runtime", UNAVAILABLE),
        "tool_calls": packaged.get("tool_calls", UNAVAILABLE),
        "hidden_style": f"{hidden.get('passed_cases', UNAVAILABLE)}/{hidden.get('total_cases', UNAVAILABLE)}",
        "hidden_style_detail": hidden,
        "final_submission_ready": packaged.get("final_submission_ready", UNAVAILABLE),
        "no_secret_scan_ok": packaged.get("no_secret_scan_ok", UNAVAILABLE),
        "final_recommendation": winner.get("final_recommendation", UNAVAILABLE),
        "preferred_strategy": packaged.get("preferred_strategy", "SQL_FIRST_API_VERIFY"),
        "official_token_reduction": {
            "state": "promoted_default",
            "enabled": accuracy.get("official_token_reduction_enabled", UNAVAILABLE),
        },
        "llm": {
            "state": "shadow_only",
            "provider": llm.get("provider", UNAVAILABLE),
            "model": llm.get("model", UNAVAILABLE),
            "accepted": llm.get("accepted_candidate_count", llm.get("safe_rows", UNAVAILABLE)),
            "candidate_count": llm.get("candidate_count", llm.get("candidate_rows", UNAVAILABLE)),
        },
        "llm_baseline_framework": {
            "state": "shadow_only",
            "framework": llm_baseline.get("framework", "generic_sdk_llm_baseline"),
            "provider": llm_baseline.get("provider", llm_sdk.get("provider", UNAVAILABLE)),
            "provider_type": llm_baseline.get("provider_type", llm_sdk.get("provider_type", UNAVAILABLE)),
            "backend_type": llm_baseline.get("backend_type", llm_sdk.get("backend_type", UNAVAILABLE)),
            "backend_name": llm_baseline.get("backend_name", llm_sdk.get("backend_name", UNAVAILABLE)),
            "tool_calling_supported": llm_baseline.get("tool_calling_supported", llm_sdk.get("tool_calling_supported", UNAVAILABLE)),
            "strict_scoring_status": llm_strict.get("summary", {}).get("strict_scoring_status", llm_baseline.get("strict_scoring_status", UNAVAILABLE)),
            "recommendation": llm_strict.get("summary", {}).get("recommendation", llm_baseline.get("recommendation", UNAVAILABLE)),
        },
        "live": {
            "state": "diagnostic_only",
            "credentials_visible": live.get("all_adobe_credentials_visible", UNAVAILABLE),
            "dry_run_dependent_rows": live.get("dry_run_dependent_rows", UNAVAILABLE),
        },
        "answer_shape_v2": {
            "state": "default_off",
            "recommendation": answer_shape.get("recommendation", UNAVAILABLE),
            "safe_rows": answer_shape.get("safe_rows", UNAVAILABLE),
            "projected_score": answer_shape.get("projected_strict_final_score", UNAVAILABLE),
        },
        "sql_only_api_skip": {
            "state": "default_off",
            "rows": live.get("sql_only_skip_guard_rows", UNAVAILABLE),
        },
        "endpoint_tiebreak": {
            "state": "shadow_only",
            "recommendation": endpoint_tie.get("recommendation", UNAVAILABLE),
            "trial_eligible_rows": endpoint_tie.get("trial_eligible_rows", UNAVAILABLE),
        },
        "compact_context": {
            "state": "default_off",
            "enabled": accuracy.get("compact_context_enabled", UNAVAILABLE),
        },
        "repair": {
            "state": "default_off",
            "enabled": accuracy.get("repair_execution_enabled", UNAVAILABLE),
        },
    }


def technique_cards() -> list[dict[str, Any]]:
    catalog = load_json("outputs/visualizations/technique_catalog.json", {})
    techniques = list(catalog.get("techniques", []))
    names = {item.get("technique_name") for item in techniques}
    if "simple_prompt_gate" not in names:
        techniques.append(
            {
                "technique_name": "simple_prompt_gate",
                "category": "Query understanding / routing",
                "purpose": "Checkpointed gate that sends evidence questions into the backend pipeline.",
                "stage_in_pipeline": "prompt routing",
                "input_data": "raw prompt",
                "output_data": "USE_DATA_PIPELINE or direct-answer decision",
                "decision_boundary": "Promoted checkpoint path; no scoring behavior is changed by this visualization.",
                "files_modules_involved": ["dashagent/prompt_router.py", "dashagent/executor.py"],
                "checkpoint_names_involved": ["checkpoint_simple_prompt_gate"],
                "default_state": "promoted_default",
                "measured_effect": {},
                "hidden_style_impact": "Covered through current hidden-style pass state.",
                "why_promoted_or_not": "Part of the packaged prompt routing path.",
                "source_reports": [{"path": f"outputs/eval/{PRIMARY_QUERY_ID}/sql_first_api_verify/trajectory.json"}],
            }
        )
    if "SDK LLM baseline framework" not in names:
        llm_baseline = load_json("outputs/llm_baseline_eval_report.json", {})
        llm_strict = load_json("outputs/llm_strict_baseline_eval.json", {})
        techniques.append(
            {
                "technique_name": "SDK LLM baseline framework",
                "category": "Safety / evaluation",
                "purpose": "Provider-agnostic SDK baseline for OpenAI-compatible and Anthropic LLM comparisons.",
                "stage_in_pipeline": "shadow LLM baseline evaluation",
                "input_data": "dev prompts plus configured SDK backend metadata",
                "output_data": "shadow baseline trajectories and strict comparison reports",
                "decision_boundary": "Comparison/shadow-only; never promoted without explicit strict, safety, hidden-style, package, and no-secret gates.",
                "files_modules_involved": [
                    "dashagent/llm_client.py",
                    "dashagent/llm_tool_agent.py",
                    "scripts/run_llm_baseline_eval.py",
                    "scripts/run_llm_strict_baseline_eval.py",
                    "scripts/run_llm_hidden_style_diagnostic.py",
                ],
                "checkpoint_names_involved": ["llm_sdk_backend_check", "llm_strict_eval"],
                "default_state": "shadow_only",
                "measured_effect": {
                    "strict_score": llm_strict.get("summary", {}).get("best_delta_vs_deterministic", UNAVAILABLE),
                    "recommendation": llm_strict.get("summary", {}).get("recommendation", llm_baseline.get("recommendation", UNAVAILABLE)),
                },
                "hidden_style_impact": "Diagnostic-only unless the generic hidden-style diagnostic has run.",
                "why_promoted_or_not": "Current SDK LLM baseline is a comparison framework; deterministic SQL_FIRST_API_VERIFY remains packaged.",
                "source_reports": [
                    {"path": "outputs/llm_baseline_eval_report.json"},
                    {"path": "outputs/llm_strict_baseline_eval.json"},
                    {"path": "outputs/llm_hidden_style_diagnostic.json"},
                ],
            }
        )

    cards: list[dict[str, Any]] = []
    for item in techniques:
        status = item.get("default_state", UNAVAILABLE)
        runtime_path = runtime_path_for_status(status)
        name = item.get("technique_name", UNAVAILABLE)
        cards.append(
            {
                "technique_name": name,
                "group": group_for(name, item.get("category")),
                "status": status,
                "status_badge": status_badge(status),
                "runtime_path": runtime_path,
                "runtime_badge": runtime_badge(runtime_path),
                "input": item.get("input_data", UNAVAILABLE),
                "changed_artifact": item.get("stage_in_pipeline", UNAVAILABLE),
                "output": item.get("output_data", UNAVAILABLE),
                "downstream_effect": item.get("purpose", UNAVAILABLE),
                "affects": infer_affects(name, item),
                "measured_effect": item.get("measured_effect", {}),
                "source_reports": item.get("source_reports", []),
                "why": item.get("why_promoted_or_not", UNAVAILABLE),
            }
        )
    return cards


def group_for(name: str, fallback: Any) -> str:
    for group, names in TECHNIQUE_GROUPS.items():
        if name in names:
            return group
    return str(fallback or "Other")


def infer_affects(name: str, item: dict[str, Any]) -> list[str]:
    text = " ".join(
        [
            str(name),
            str(item.get("category", "")),
            str(item.get("purpose", "")),
            str(item.get("stage_in_pipeline", "")),
        ]
    ).lower()
    affects: list[str] = []
    if any(word in text for word in ["answer", "rank", "route", "sql", "api", "candidate", "schema", "planner"]):
        affects.append("accuracy")
    if any(word in text for word in ["token", "cache", "budget", "compact", "fast", "optimizer", "skip"]):
        affects.append("efficiency")
    if any(word in text for word in ["validation", "verifier", "leakage", "secret", "readiness", "safe", "repair", "dry-run"]):
        affects.append("safety")
    if any(word in text for word in ["checkpoint", "report", "diagnostic", "readiness", "trajectory", "eval"]):
        affects.append("observability")
    return affects or ["observability"]


def step_mermaid(steps: list[dict[str, Any]], limit: int | None = None) -> str:
    selected = steps if limit is None else steps[:limit]
    lines = ["flowchart LR"]
    for idx, step in enumerate(selected):
        node = f"S{idx}"
        label = mermaid_label(step["name"], 34)
        lines.append(f'  {node}["{label}"]')
        if idx:
            lines.append(f"  S{idx-1} --> {node}")
    return "\n".join(lines)


def stage_from_checkpoint_id(checkpoint_id: str) -> str:
    lowered = checkpoint_id.lower()
    if "router" in lowered or "gate" in lowered:
        return "routing"
    if "normal" in lowered or "token" in lowered:
        return "query understanding"
    if "analysis" in lowered or "lookup" in lowered:
        return "analysis"
    if "context" in lowered or "metadata" in lowered:
        return "context"
    if "plan" in lowered or "policy" in lowered or "budget" in lowered:
        return "planning"
    if "validation" in lowered or "execution" in lowered:
        return "execution"
    if "answer" in lowered or "verif" in lowered:
        return "answer"
    return "checkpoint"


def checkpoint_timeline(context: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for idx, checkpoint in enumerate(context["trajectory"].get("checkpoints", []) or [], start=1):
        checkpoint_id = checkpoint.get("checkpoint_id", f"checkpoint_{idx}")
        rows.append(
            {
                "order": idx,
                "checkpoint_id": checkpoint_id,
                "stage": checkpoint.get("stage") or stage_from_checkpoint_id(checkpoint_id),
                "technique": checkpoint.get("technique", UNAVAILABLE),
                "input": visual_summary(checkpoint.get("input_summary") or checkpoint.get("input"), 130),
                "output": visual_summary(checkpoint.get("output"), 130),
                "what_changed": checkpoint.get("effect") or "Recorded the stage output in trajectory.",
                "impact": checkpoint.get("correctness_role") or checkpoint.get("efficiency_role") or checkpoint.get("safety_role") or "observability",
            }
        )
    return rows


def source_value(report: dict[str, Any], *path: str) -> Any:
    return get_path(report, *path)
