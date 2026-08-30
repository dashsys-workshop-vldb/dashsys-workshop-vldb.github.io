#!/usr/bin/env python
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from visualization_report_helpers import VIS_DIR, load_json, mermaid_block, table, write_json, write_md  # noqa: E402


def main() -> int:
    state = build_state()
    write_json(VIS_DIR / "current_system_state.json", state)
    write_md(VIS_DIR / "current_system_state.md", build_markdown(state))
    views = build_technique_dataflow_views()
    write_json(VIS_DIR / "technique_dataflow_views.json", {"techniques": views})
    write_md(VIS_DIR / "technique_dataflow_views.md", build_technique_views_markdown(views))
    print(
        {
            "json": str(VIS_DIR / "current_system_state.json"),
            "markdown": str(VIS_DIR / "current_system_state.md"),
            "technique_dataflow_views_json": str(VIS_DIR / "technique_dataflow_views.json"),
            "technique_dataflow_views_markdown": str(VIS_DIR / "technique_dataflow_views.md"),
        }
    )
    return 0


def build_state() -> dict[str, Any]:
    winner = load_json("outputs/winner_readiness_report.json", {})
    packaged = winner.get("packaged", {})
    hidden = winner.get("hidden_style_eval", {})
    auto_trial = winner.get("autonomous_packaged_trial", {})
    llm = winner.get("llm_answer_rewrite_search", load_json("outputs/llm_answer_rewrite_search.json", {}).get("summary", {}))
    llm_baseline = winner.get("llm_baseline_framework", load_json("outputs/llm_baseline_eval_report.json", {}))
    llm_strict = load_json("outputs/llm_strict_baseline_eval.json", {})
    live = winner.get("live_mode_readiness_report", load_json("outputs/live_mode_readiness_report.json", {}).get("summary", {}))
    answer_shape = winner.get("answer_shape_v2_ab_eval", load_json("outputs/answer_shape_v2_ab_eval.json", {}).get("summary", {}))
    endpoint_tie = winner.get("endpoint_family_tiebreak_v2_shadow", load_json("outputs/endpoint_family_tiebreak_v2_shadow.json", {}).get("summary", {}))
    accuracy = load_json("outputs/accuracy_promotion_decision_report.json", {})
    return {
        "preferred_strategy": packaged.get("preferred_strategy", "SQL_FIRST_API_VERIFY"),
        "packaged_strict_final_score": packaged.get("strict_final_score"),
        "best_isolated_score": auto_trial.get("strict_final_score"),
        "correctness": packaged.get("strict_correctness"),
        "estimated_tokens": packaged.get("estimated_tokens"),
        "runtime": packaged.get("runtime"),
        "tool_calls": packaged.get("tool_calls"),
        "hidden_style": {
            "passed_cases": hidden.get("passed_cases"),
            "total_cases": hidden.get("total_cases"),
            "family_stability_rate": hidden.get("family_stability_rate"),
            "schema_stability_rate": hidden.get("schema_stability_rate"),
        },
        "final_submission_ready": packaged.get("final_submission_ready"),
        "no_secret_scan_ok": packaged.get("no_secret_scan_ok"),
        "final_recommendation": winner.get("final_recommendation"),
        "llm_status": {
            "provider": llm.get("provider"),
            "model": llm.get("model"),
            "key_visible": llm.get("key_visible"),
            "candidate_count": llm.get("candidate_count", llm.get("candidate_rows")),
            "accepted_candidate_count": llm.get("accepted_candidate_count", llm.get("safe_rows")),
            "recommendation": llm.get("recommendation"),
        },
        "llm_baseline_framework_status": {
            "framework": llm_baseline.get("framework", "generic_sdk_llm_baseline"),
            "backend_name": llm_baseline.get("backend_name"),
            "backend_type": llm_baseline.get("backend_type"),
            "tool_calling_supported": llm_baseline.get("tool_calling_supported"),
            "strict_scoring_status": llm_strict.get("summary", {}).get("strict_scoring_status", llm_baseline.get("strict_scoring_status")),
            "recommendation": llm_strict.get("summary", {}).get("recommendation", llm_baseline.get("recommendation", "keep_shadow_only")),
            "state": "shadow_only",
        },
        "live_mode_readiness_status": {
            "diagnostic_only": live.get("diagnostic_only"),
            "all_adobe_credentials_visible": live.get("all_adobe_credentials_visible"),
            "dry_run_dependent_rows": live.get("dry_run_dependent_rows"),
            "final_answers_changed": live.get("final_answers_changed"),
        },
        "answer_shape_v2_status": {
            "state": "default_off",
            "recommendation": answer_shape.get("recommendation"),
            "projected_strict_final_score": answer_shape.get("projected_strict_final_score"),
            "safe_rows": answer_shape.get("safe_rows"),
        },
        "endpoint_family_tiebreak_v2_status": {
            "state": "shadow_only",
            "recommendation": endpoint_tie.get("recommendation"),
            "trial_eligible_rows": endpoint_tie.get("trial_eligible_rows"),
        },
        "sql_only_api_skip_status": {
            "state": "default_off",
            "sql_only_skip_guard_rows": live.get("sql_only_skip_guard_rows"),
        },
        "compact_context_status": {
            "enabled": accuracy.get("compact_context_enabled"),
            "state": "disabled",
        },
        "repair_status": {
            "enabled": accuracy.get("repair_execution_enabled"),
            "state": "disabled",
        },
        "official_token_reduction_status": {
            "enabled": accuracy.get("official_token_reduction_enabled"),
            "state": "promoted_default",
        },
        "promoted_techniques": [
            "SQL_FIRST_API_VERIFY",
            "query normalization/tokens/relevance",
            "metadata selector",
            "SQL/API templates",
            "endpoint catalog validation",
            "evidence policy",
            "answer synthesis/verifier/reranker",
            "official-token reduction",
            "trajectory checkpoints",
        ],
        "shadow_only_techniques": [
            "supportable answer rewrite",
            "endpoint/schema rule candidates",
            "endpoint-family tie-break v2",
            "AST-guided SQL candidate canary",
            "OpenRouter LLM answer rewrite search",
            "SDK LLM baseline framework",
            "autonomous packaged trials",
        ],
        "diagnostic_only_techniques": [
            "hidden-style eval",
            "live-mode readiness",
            "local knowledge index coverage",
            "secret scan",
            "package readiness checks",
        ],
        "blocked_or_not_yet_promoted": [
            "answer-shape v2",
            "SQL-only API-skip guard",
            "compact context",
            "repair execution",
        ],
    }


def graph(state: dict[str, Any]) -> str:
    return f"""
flowchart LR
  A["Packaged default"] --> B["{state['preferred_strategy']}"]
  B --> C["Strict {state['packaged_strict_final_score']}"]
  C --> D["Ready: {state['final_submission_ready']}"]
  B --> E["Official token reduction: {state['official_token_reduction_status']['state']}"]
  B --> F["Hidden-style {state['hidden_style']['passed_cases']}/{state['hidden_style']['total_cases']}"]
  G["Shadow only"] --> H["Best isolated {state['best_isolated_score']}"]
  G --> I["Answer rewrites / candidates"]
  J["Diagnostic only"] --> K["Live readiness"]
  J --> L["Secret/readiness checks"]
  M["Disabled"] --> N["Compact context"]
  M --> O["Repair execution"]
"""


def build_markdown(state: dict[str, Any]) -> str:
    status_rows = [
        ["preferred strategy", state["preferred_strategy"]],
        ["packaged strict final score", state["packaged_strict_final_score"]],
        ["best isolated score", state["best_isolated_score"]],
        ["correctness", state["correctness"]],
        ["tokens / runtime / tool calls", f"{state['estimated_tokens']} / {state['runtime']} / {state['tool_calls']}"],
        ["hidden-style pass rate", f"{state['hidden_style']['passed_cases']}/{state['hidden_style']['total_cases']}"],
        ["family/schema stability", f"{state['hidden_style']['family_stability_rate']} / {state['hidden_style']['schema_stability_rate']}"],
        ["final submission ready", state["final_submission_ready"]],
        ["no secret scan ok", state["no_secret_scan_ok"]],
        ["final recommendation", state["final_recommendation"]],
        ["LLM status", state["llm_status"]],
        ["LLM baseline framework", state["llm_baseline_framework_status"]],
        ["live-mode readiness", state["live_mode_readiness_status"]],
        ["answer-shape v2", state["answer_shape_v2_status"]],
        ["endpoint-family tie-break v2", state["endpoint_family_tiebreak_v2_status"]],
        ["SQL-only API-skip", state["sql_only_api_skip_status"]],
        ["compact context", state["compact_context_status"]],
        ["repair", state["repair_status"]],
        ["official-token reduction", state["official_token_reduction_status"]],
    ]
    group_rows = [
        ["promoted_default", ", ".join(state["promoted_techniques"])],
        ["shadow_only", ", ".join(state["shadow_only_techniques"])],
        ["diagnostic_only", ", ".join(state["diagnostic_only_techniques"])],
        ["blocked / not promoted", ", ".join(state["blocked_or_not_yet_promoted"])],
    ]
    return "\n".join(
        [
            "# Current DASHSys System State",
            "",
            "## At a Glance",
            "",
            mermaid_block(graph(state)),
            "",
            "## Summary Table",
            "",
            table(["Field", "Value"], status_rows),
            "",
            "## Promotion State",
            "",
            table(["State", "Techniques"], group_rows),
            "",
        ]
    )


def build_technique_dataflow_views() -> list[dict[str, Any]]:
    entries = [
        view("query_normalizer + query_tokens + relevance_scorer", "Raw query", "normalized tokens + relevance features", "metadata selector", True, True, True, True),
        view("metadata_selector", "ranked schema/API candidates", "compact metadata and context cards", "planner", True, True, True, True),
        view("SQL templates", "query analysis + schema metadata", "read-only SQL candidate", "SQL validator/executor", True, False, True, True),
        view("API templates", "endpoint intent + grounded params", "catalog-valid API call", "API validator/executor", True, False, True, True),
        view("evidence_policy", "SQL/API results + route policy", "evidence sufficiency decision", "answer synthesis", True, True, True, True),
        view("supportable_answer_rewriter", "recorded evidence + dry-run labels", "evidence-cited answer candidate", "isolated trial only", True, False, True, True, state="shadow_only"),
        view("answer-shape v2", "baseline answer + evidence", "short shape-normalized candidate answer", "isolated A/B report", True, True, True, True, state="default_off"),
        view("official-token reduction", "prompt/context metadata", "reduced token prompt context", "packaged execution", False, True, True, True),
        view("local_knowledge_index", "DBSnapshot parquet files", "provenance-safe evidence objects", "answer/candidate diagnostics", True, True, True, True, state="diagnostic_only"),
        view("endpoint_family_ranker", "query intent + endpoint catalog", "ranked endpoint family", "planner", True, False, True, True),
        view("endpoint-family tie-break v2", "ranked vs selected endpoint family", "shadow divergence report", "isolated trial gate", True, False, True, True, state="shadow_only"),
        view("hidden-style eval", "paraphrase/hidden-style cases", "family/schema stability report", "promotion gate", True, False, True, True, state="diagnostic_only"),
        view("live-mode readiness", "credential visibility + dry-run rows", "live-readiness report", "human review", False, False, True, True, state="diagnostic_only"),
        view("LLM answer rewrite search", "evidence registry + baseline answer", "validated/rejected LLM rewrite candidates", "supportable rewrite gates", True, False, True, True, state="shadow_only"),
        view("SDK LLM baseline framework", "configured SDK backend + dev prompts", "shadow baseline and strict diagnostic reports", "human comparison only", True, False, True, True, state="shadow_only"),
    ]
    return entries


def view(
    technique: str,
    input_data: str,
    output_data: str,
    downstream: str,
    accuracy: bool,
    efficiency: bool,
    safety: bool,
    observability: bool,
    *,
    state: str = "promoted_default",
) -> dict[str, Any]:
    graph = f"""
flowchart LR
  A["Before: {input_data}"] --> B["{technique}"]
  B --> C["After: {output_data}"]
  C --> D["Downstream: {downstream}"]
"""
    return {
        "technique": technique,
        "state": state,
        "enters_pipeline_at": input_data,
        "input_consumed": input_data,
        "intermediate_representation_changed": output_data,
        "output_produced": output_data,
        "downstream_stage_affected": downstream,
        "affects_accuracy": accuracy,
        "affects_efficiency": efficiency,
        "affects_safety": safety,
        "affects_observability": observability,
        "before_after_mermaid": graph,
        "before": f"Pipeline has {input_data}.",
        "after": f"Pipeline has {output_data}; downstream stage is {downstream}.",
    }


def build_technique_views_markdown(views: list[dict[str, Any]]) -> str:
    lines = [
        "# Technique Dataflow Views",
        "",
        "Each view shows where a technique enters the pipeline, what representation it changes, and what downstream stage is affected.",
        "",
    ]
    for item in views:
        lines.extend(
            [
                f"## {item['technique']}",
                "",
                mermaid_block(item["before_after_mermaid"]),
                "",
                table(
                    ["Field", "Value"],
                    [
                        ["State", item["state"]],
                        ["Input consumed", item["input_consumed"]],
                        ["Representation changed", item["intermediate_representation_changed"]],
                        ["Output produced", item["output_produced"]],
                        ["Downstream affected", item["downstream_stage_affected"]],
                        ["Accuracy / efficiency / safety / observability", f"{item['affects_accuracy']} / {item['affects_efficiency']} / {item['affects_safety']} / {item['affects_observability']}"],
                        ["Before", item["before"]],
                        ["After", item["after"]],
                    ],
                ),
                "",
            ]
        )
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
