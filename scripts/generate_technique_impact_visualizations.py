#!/usr/bin/env python
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from visualization_report_helpers import (  # noqa: E402
    UNAVAILABLE,
    VIS_DIR,
    load_json,
    score_delta,
    strict_strategy_summary,
    table,
    write_json,
    write_md,
)


def main() -> int:
    impact = build_impact_matrix()
    timeline = build_timeline()
    write_json(VIS_DIR / "technique_impact_matrix.json", {"rows": impact})
    write_md(VIS_DIR / "technique_impact_matrix.md", build_impact_markdown(impact))
    write_json(VIS_DIR / "score_improvement_timeline.json", {"milestones": timeline})
    write_md(VIS_DIR / "score_improvement_timeline.md", build_timeline_markdown(timeline, impact))
    print(
        {
            "impact_json": str(VIS_DIR / "technique_impact_matrix.json"),
            "timeline_json": str(VIS_DIR / "score_improvement_timeline.json"),
            "rows": len(impact),
            "milestones": len(timeline),
        }
    )
    return 0


def build_impact_matrix() -> list[dict[str, Any]]:
    current = strict_strategy_summary()
    official = load_json("outputs/official_token_reduction_promotion_report.json", {})
    endpoint_schema = load_json("outputs/endpoint_schema_rule_canary.json", {}).get("summary", {})
    ast = load_json("outputs/ast_guided_sql_candidate_canary.json", {}).get("summary", {})
    answer_shape = load_json("outputs/answer_shape_v2_ab_eval.json", {}).get("summary", {})
    supportable = load_json("outputs/supportable_answer_rewrite_eval.json", {}).get("summary", {})
    evidence_answer = load_json("outputs/evidence_answer_candidate_eval.json", {}).get("summary", {})
    llm_answer = load_json("outputs/llm_answer_rewrite_search.json", {}).get("summary", {})
    local_index = load_json("outputs/local_index_candidate_eval.json", {}).get("summary", {})
    endpoint_tie = load_json("outputs/endpoint_family_tiebreak_v2_shadow.json", {}).get("summary", {})
    live = load_json("outputs/live_mode_readiness_report.json", {}).get("summary", {})
    autonomous = load_json("outputs/autonomous_packaged_trial.json", {}).get("summary", {})

    rows = [
        impact_row(
            "SQL_FIRST_API_VERIFY packaged strategy",
            "promoted_default",
            True,
            0.0,
            0.0,
            current.get("avg_answer_score", UNAVAILABLE),
            current.get("avg_sql_score", UNAVAILABLE),
            current.get("avg_api_score", UNAVAILABLE),
            current.get("avg_estimated_tokens", UNAVAILABLE),
            current.get("avg_runtime", UNAVAILABLE),
            current.get("avg_tool_call_count", UNAVAILABLE),
            "48/48 hidden-style in current report",
            "current safe default",
        ),
        impact_row(
            "official-token reduction",
            "promoted_default",
            True,
            official.get("score_delta", UNAVAILABLE),
            score_delta(official.get("promoted_correctness"), official.get("baseline_correctness")),
            UNAVAILABLE,
            UNAVAILABLE,
            UNAVAILABLE,
            official.get("token_delta", UNAVAILABLE),
            official.get("runtime_delta", UNAVAILABLE),
            official.get("tool_delta", UNAVAILABLE),
            "48/48 maintained",
            official.get("recommendation", "promoted_keep_enabled"),
        ),
        impact_row(
            "supportable answer rewrite",
            "shadow_only",
            False,
            score_delta(supportable.get("best_projected_strict_final_score"), current.get("avg_final_score")),
            UNAVAILABLE,
            UNAVAILABLE,
            UNAVAILABLE,
            UNAVAILABLE,
            UNAVAILABLE,
            UNAVAILABLE,
            UNAVAILABLE,
            "no packaged effect",
            supportable.get("recommendation", "safe rows isolated only"),
        ),
        impact_row(
            "evidence-aware answer candidates",
            "shadow_only",
            False,
            score_delta(evidence_answer.get("best_projected_strict_final_score"), current.get("avg_final_score")),
            UNAVAILABLE,
            UNAVAILABLE,
            UNAVAILABLE,
            UNAVAILABLE,
            UNAVAILABLE,
            UNAVAILABLE,
            UNAVAILABLE,
            "no packaged effect",
            evidence_answer.get("recommendation", "isolated only"),
        ),
        impact_row(
            "autonomous packaged trial bundle",
            "shadow_only",
            False,
            autonomous.get("score_delta", UNAVAILABLE),
            autonomous.get("correctness_delta", UNAVAILABLE),
            UNAVAILABLE,
            UNAVAILABLE,
            UNAVAILABLE,
            autonomous.get("token_delta", UNAVAILABLE),
            autonomous.get("runtime_delta", UNAVAILABLE),
            autonomous.get("tool_delta", UNAVAILABLE),
            "hidden-style gate passed",
            autonomous.get("recommendation", UNAVAILABLE),
        ),
        impact_row(
            "answer-shape v2",
            "default_off",
            False,
            score_delta(answer_shape.get("projected_strict_final_score"), answer_shape.get("baseline_strict_final_score")),
            score_delta(answer_shape.get("projected_correctness"), answer_shape.get("baseline_correctness")),
            answer_shape.get("avg_answer_score_delta_changed", UNAVAILABLE),
            UNAVAILABLE,
            UNAVAILABLE,
            UNAVAILABLE,
            UNAVAILABLE,
            UNAVAILABLE,
            "hidden-style gate passed",
            answer_shape.get("recommendation", UNAVAILABLE),
        ),
        impact_row(
            "endpoint/schema rule canary",
            "shadow_only",
            False,
            endpoint_schema.get("avg_score_delta", UNAVAILABLE),
            endpoint_schema.get("avg_correctness_delta", UNAVAILABLE),
            UNAVAILABLE,
            UNAVAILABLE,
            endpoint_schema.get("api_top_k_hit_rate_delta", UNAVAILABLE),
            endpoint_schema.get("avg_token_delta", UNAVAILABLE),
            endpoint_schema.get("avg_runtime_delta", UNAVAILABLE),
            endpoint_schema.get("avg_tool_delta", UNAVAILABLE),
            "hidden-style gate passed",
            endpoint_schema.get("recommendation", UNAVAILABLE),
        ),
        impact_row(
            "endpoint-family tie-break v2",
            "shadow_only",
            False,
            0 if endpoint_tie.get("positive_projected_delta_rows") == 0 else UNAVAILABLE,
            UNAVAILABLE,
            UNAVAILABLE,
            UNAVAILABLE,
            UNAVAILABLE,
            UNAVAILABLE,
            UNAVAILABLE,
            UNAVAILABLE,
            "no packaged effect",
            endpoint_tie.get("recommendation", "keep_shadow_only"),
        ),
        impact_row(
            "AST-guided SQL candidate canary",
            "shadow_only",
            False,
            ast.get("avg_score_delta", UNAVAILABLE),
            ast.get("avg_correctness_delta", UNAVAILABLE),
            UNAVAILABLE,
            UNAVAILABLE,
            UNAVAILABLE,
            ast.get("avg_token_delta", UNAVAILABLE),
            ast.get("avg_runtime_delta", UNAVAILABLE),
            ast.get("avg_tool_delta", UNAVAILABLE),
            "no hidden-style effect reported",
            ast.get("recommendation", UNAVAILABLE),
        ),
        impact_row(
            "local knowledge index",
            "diagnostic_only",
            False,
            local_index.get("score_delta_from_local_evidence_total", UNAVAILABLE),
            UNAVAILABLE,
            UNAVAILABLE,
            UNAVAILABLE,
            UNAVAILABLE,
            UNAVAILABLE,
            UNAVAILABLE,
            UNAVAILABLE,
            "no packaged effect",
            local_index.get("recommendation", UNAVAILABLE),
        ),
        impact_row(
            "OpenRouter LLM answer rewrite search",
            "shadow_only",
            False,
            0 if llm_answer.get("safe_rows") == 0 else UNAVAILABLE,
            UNAVAILABLE,
            UNAVAILABLE,
            UNAVAILABLE,
            UNAVAILABLE,
            UNAVAILABLE,
            UNAVAILABLE,
            UNAVAILABLE,
            "no packaged effect",
            llm_answer.get("recommendation", UNAVAILABLE),
        ),
        impact_row(
            "live-mode readiness",
            "diagnostic_only",
            False,
            UNAVAILABLE,
            UNAVAILABLE,
            UNAVAILABLE,
            UNAVAILABLE,
            UNAVAILABLE,
            UNAVAILABLE,
            UNAVAILABLE,
            UNAVAILABLE,
            "does not change dry-run behavior",
            "diagnostic_only" if live.get("diagnostic_only") is True else UNAVAILABLE,
        ),
    ]
    return rows


def impact_row(
    technique: str,
    status: str,
    promoted: bool,
    strict_delta: Any,
    correctness_delta: Any,
    answer_delta: Any,
    sql_delta: Any,
    api_delta: Any,
    token_delta: Any,
    runtime_delta: Any,
    tool_delta: Any,
    hidden_style_impact: Any,
    recommendation: Any,
) -> dict[str, Any]:
    return {
        "technique": technique,
        "status": status,
        "promoted": promoted,
        "strict_delta": strict_delta,
        "correctness_delta": correctness_delta,
        "answer_delta": answer_delta,
        "sql_delta": sql_delta,
        "api_delta": api_delta,
        "token_delta": token_delta,
        "runtime_delta": runtime_delta,
        "tool_delta": tool_delta,
        "hidden_style_impact": hidden_style_impact,
        "recommendation": recommendation,
    }


def build_timeline() -> list[dict[str, Any]]:
    eval_summary = load_json("outputs/eval_results_strict.json", {}).get("summary", {}).get("by_strategy", {})
    official = load_json("outputs/official_token_reduction_promotion_report.json", {})
    supportable = load_json("outputs/supportable_answer_rewrite_eval.json", {}).get("summary", {})
    llm_answer = load_json("outputs/llm_answer_rewrite_search.json", {}).get("summary", {})
    answer_shape = load_json("outputs/answer_shape_v2_ab_eval.json", {}).get("summary", {})
    endpoint_tie = load_json("outputs/endpoint_family_tiebreak_v2_shadow.json", {}).get("summary", {})
    live = load_json("outputs/live_mode_readiness_report.json", {}).get("summary", {})
    autonomous = load_json("outputs/autonomous_packaged_trial.json", {}).get("summary", {})
    score_push = load_json("outputs/autonomous_score_push_report.json", {}).get("summary", {})
    return [
        milestone("initial baseline", UNAVAILABLE, eval_summary.get("LLM_FREE_AGENT_BASELINE", {}).get("avg_final_score", UNAVAILABLE), "LLM-free baseline comparison", False, "Baseline only; not packaged."),
        milestone("SQL/API template improvements", UNAVAILABLE, eval_summary.get("TEMPLATE_FIRST", {}).get("avg_final_score", UNAVAILABLE), "Reusable SQL/API templates and deterministic metadata path", False, "Competitive but not preferred due to cost/risk tradeoff."),
        milestone("SQL_FIRST_API_VERIFY selection", UNAVAILABLE, eval_summary.get("SQL_FIRST_API_VERIFY", {}).get("avg_final_score", UNAVAILABLE), "SQL-first grounding with API verification", True, "Current preferred packaged strategy."),
        milestone("official-token reduction promotion", official.get("baseline_strict_score", UNAVAILABLE), official.get("promoted_strict_score", UNAVAILABLE), "Official token reduction enabled", True, official.get("recommendation", UNAVAILABLE)),
        milestone("supportable answer rewrite", eval_summary.get("SQL_FIRST_API_VERIFY", {}).get("avg_final_score", UNAVAILABLE), supportable.get("best_projected_strict_final_score", UNAVAILABLE), "Evidence-cited answer-only rewrite candidates", False, supportable.get("recommendation", UNAVAILABLE)),
        milestone("LLM rewrite search", eval_summary.get("SQL_FIRST_API_VERIFY", {}).get("avg_final_score", UNAVAILABLE), UNAVAILABLE, "OpenRouter rewrite proposals with local validation", False, llm_answer.get("recommendation", llm_answer.get("status", UNAVAILABLE))),
        milestone("answer-shape v2", answer_shape.get("baseline_strict_final_score", UNAVAILABLE), answer_shape.get("projected_strict_final_score", UNAVAILABLE), "Row-level answer-shape A/B", False, answer_shape.get("recommendation", UNAVAILABLE)),
        milestone("endpoint-family tie-break v2", eval_summary.get("SQL_FIRST_API_VERIFY", {}).get("avg_final_score", UNAVAILABLE), eval_summary.get("SQL_FIRST_API_VERIFY", {}).get("avg_final_score", UNAVAILABLE), "Shadow endpoint divergence analysis", False, endpoint_tie.get("recommendation", "keep_shadow_only")),
        milestone("live-mode readiness", UNAVAILABLE, UNAVAILABLE, "Credential/live API readiness diagnostic", False, "diagnostic_only" if live.get("diagnostic_only") else UNAVAILABLE),
        milestone("autonomous packaged trials", autonomous.get("baseline_strict_final_score", UNAVAILABLE), autonomous.get("strict_final_score", score_push.get("best_safe_score", UNAVAILABLE)), "Isolated packaged-style bundle trial", False, autonomous.get("recommendation", UNAVAILABLE)),
    ]


def milestone(name: str, before: Any, after: Any, changed: str, promoted: bool, why: Any) -> dict[str, Any]:
    return {
        "milestone": name,
        "score_before": before,
        "score_after": after,
        "score_delta": score_delta(after, before),
        "what_changed": changed,
        "promoted": promoted,
        "why_it_mattered": why,
    }


def build_impact_markdown(rows: list[dict[str, Any]]) -> str:
    return "\n".join(
        [
            "# Technique Impact Matrix",
            "",
            "Metrics below are copied from current reports. Missing values are `unavailable`.",
            "",
            table(
                [
                    "Technique",
                    "Status",
                    "Promoted?",
                    "Strict Δ",
                    "Correctness Δ",
                    "Answer Δ",
                    "SQL Δ",
                    "API Δ",
                    "Token Δ",
                    "Runtime Δ",
                    "Tool Δ",
                    "Hidden-style impact",
                    "Recommendation",
                ],
                [
                    [
                        row["technique"],
                        row["status"],
                        row["promoted"],
                        row["strict_delta"],
                        row["correctness_delta"],
                        row["answer_delta"],
                        row["sql_delta"],
                        row["api_delta"],
                        row["token_delta"],
                        row["runtime_delta"],
                        row["tool_delta"],
                        row["hidden_style_impact"],
                        row["recommendation"],
                    ]
                    for row in rows
                ],
            ),
            "",
        ]
    )


def build_timeline_markdown(milestones: list[dict[str, Any]], impact: list[dict[str, Any]]) -> str:
    promoted = [row["technique"] for row in impact if row["status"] == "promoted_default"]
    shadow = [row["technique"] for row in impact if row["status"] == "shadow_only"]
    diagnostic = [row["technique"] for row in impact if row["status"] == "diagnostic_only"]
    default_off = [row["technique"] for row in impact if row["status"] == "default_off"]
    return "\n".join(
        [
            "# Score Improvement Timeline",
            "",
            table(
                ["Milestone", "Score before", "Score after", "Score Δ", "Changed", "Promoted?", "Why it mattered"],
                [
                    [
                        row["milestone"],
                        row["score_before"],
                        row["score_after"],
                        row["score_delta"],
                        row["what_changed"],
                        row["promoted"],
                        row["why_it_mattered"],
                    ]
                    for row in milestones
                ],
            ),
            "",
            "## Promoted vs Shadow vs Diagnostic",
            "",
            table(
                ["State", "Techniques"],
                [
                    ["promoted_default", ", ".join(promoted) or UNAVAILABLE],
                    ["shadow_only", ", ".join(shadow) or UNAVAILABLE],
                    ["default_off", ", ".join(default_off) or UNAVAILABLE],
                    ["diagnostic_only", ", ".join(diagnostic) or UNAVAILABLE],
                ],
            ),
            "",
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())
