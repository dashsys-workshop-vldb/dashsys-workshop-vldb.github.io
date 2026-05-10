#!/usr/bin/env python
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.trajectory import redact_secrets


REPORTS_DIRNAME = "reports"

POST_CHANGE_VALIDATION_COMMANDS = [
    "python3 -m pytest -q",
    "python3 scripts/run_dev_eval.py --strict",
    "python3 scripts/run_hidden_style_eval.py",
    "python3 scripts/check_llm_sdk_backend.py",
    "python3 scripts/run_llm_baseline_eval.py",
    "python3 scripts/run_llm_strict_baseline_eval.py",
    "python3 scripts/run_llm_hidden_style_diagnostic.py",
    "python3 scripts/generate_winner_readiness_report.py",
    "python3 scripts/generate_research_inspired_report.py",
    "python3 scripts/generate_system_status_dashboard.py",
    "python3 scripts/generate_technique_visual_cards.py",
    "python3 scripts/generate_visualization_index.py",
    "python3 scripts/package_submission.py",
    "python3 scripts/package_query_outputs.py",
    "python3 scripts/check_submission_ready.py",
]

REPORT_REGENERATION_TARGETS = [
    "outputs/reports/report_index.md/json",
    "outputs/reports/system_summary.md/json",
    "outputs/reports/llm_baseline_summary.md/json",
    "outputs/reports/accuracy_and_bottleneck_summary.md/json",
    "outputs/reports/visualization_summary.md/json",
    "outputs/reports/cleanup_audit.md/json",
    "outputs/reports/cleanup_final_report.md/json",
    "outputs/winner_readiness_report.md/json",
    "outputs/final_research_inspired_improvement_report.md/json",
    "outputs/visualizations/index.md/json",
    "outputs/visualizations/system_status_dashboard.md/json",
    "outputs/visualizations/technique_visual_cards.md/json",
]


def main() -> int:
    config = Config.from_env(ROOT)
    payload = generate_consolidated_reports(config)
    print(json.dumps({"reports_dir": str(config.outputs_dir / REPORTS_DIRNAME), "files": payload["written_files"]}, indent=2, sort_keys=True))
    return 0


def generate_consolidated_reports(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports_dir = config.outputs_dir / REPORTS_DIRNAME
    reports_dir.mkdir(parents=True, exist_ok=True)

    sources = _load_sources(config)
    system = build_system_summary(config, sources)
    llm = build_llm_baseline_summary(config, sources)
    accuracy = build_accuracy_and_bottleneck_summary(config, sources)
    visualization = build_visualization_summary(config, sources)
    index = build_report_index(config, system, llm, accuracy, visualization)

    written = []
    for stem, payload, markdown in [
        ("system_summary", system, render_system_summary(system)),
        ("llm_baseline_summary", llm, render_llm_summary(llm)),
        ("accuracy_and_bottleneck_summary", accuracy, render_accuracy_summary(accuracy)),
        ("visualization_summary", visualization, render_visualization_summary(visualization)),
        ("report_index", index, render_report_index(index)),
    ]:
        json_path = reports_dir / f"{stem}.json"
        md_path = reports_dir / f"{stem}.md"
        safe_payload = _safe_payload(payload)
        json_path.write_text(json.dumps(safe_payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
        md_path.write_text(markdown, encoding="utf-8")
        written.extend([_rel(config, json_path), _rel(config, md_path)])
    return {"written_files": written, "reports_dir": _rel(config, reports_dir)}


def _load_sources(config: Config) -> dict[str, Any]:
    outputs = config.outputs_dir
    visualizations = outputs / "visualizations"
    return {
        "eval_results_strict": _load_json(outputs / "eval_results_strict.json"),
        "winner_readiness": _load_json(outputs / "winner_readiness_report.json"),
        "hidden_style": _load_json(outputs / "hidden_style_eval.json"),
        "official_token_reduction": _load_json(outputs / "official_token_reduction_promotion_report.json"),
        "autonomous_trial": _load_json(outputs / "autonomous_packaged_trial.json"),
        "autonomous_score_push": _load_json(outputs / "autonomous_score_push_report.json"),
        "score075_blocker": _load_json(outputs / "score075_blocker_analysis.json"),
        "answer_shape_v2": _load_json(outputs / "answer_shape_v2_ab_eval.json"),
        "supportable_rewrite": _load_json(outputs / "supportable_answer_rewrite_eval.json"),
        "llm_answer_rewrite": _load_json(outputs / "llm_answer_rewrite_search.json"),
        "endpoint_tiebreak": _load_json(outputs / "endpoint_family_tiebreak_v2_shadow.json"),
        "endpoint_schema_canary": _load_json(outputs / "endpoint_schema_rule_canary.json"),
        "ast_canary": _load_json(outputs / "ast_guided_sql_candidate_canary.json"),
        "live_readiness": _load_json(outputs / "live_mode_readiness_report.json"),
        "llm_backend": _load_json(outputs / "llm_sdk_backend_check.json"),
        "llm_baseline": _load_json(outputs / "llm_baseline_eval_report.json"),
        "llm_strict": _load_json(outputs / "llm_strict_baseline_eval.json"),
        "llm_hidden": _load_json(outputs / "llm_hidden_style_diagnostic.json"),
        "generated_prompt_suite": _load_json(outputs / "reports" / "generated_prompt_suite_summary.json"),
        "diagnostic_prompt_suite_run": _load_json(outputs / "reports" / "diagnostic_prompt_suite_run.json"),
        "sdk_usage_audit": _load_json(outputs / "reports" / "sdk_usage_audit.json"),
        "sql_storyboard": _load_json(visualizations / "sql_prompt_storyboard_primary.json"),
        "visualization_index": _load_json(visualizations / "index.json"),
    }


def build_system_summary(config: Config, sources: dict[str, Any]) -> dict[str, Any]:
    strict = _sql_first_metrics(sources)
    packaged = sources["winner_readiness"].get("packaged", {})
    hidden = sources["hidden_style"].get("summary", {})
    official = sources["official_token_reduction"].get("summary", {})
    best_isolated = _best_isolated_score(sources)
    return {
        "report_type": "system_summary",
        "purpose": "One-glance supervisor/submission summary of the current deterministic packaged system.",
        "preferred_strategy": packaged.get("preferred_strategy") or "SQL_FIRST_API_VERIFY",
        "packaged_strict_score": _first_number(packaged.get("strict_final_score"), strict.get("avg_final_score")),
        "best_isolated_score": best_isolated,
        "strict_correctness": _first_number(packaged.get("strict_correctness"), strict.get("avg_correctness_score")),
        "hidden_style": {
            "passed": hidden.get("passed_cases"),
            "total": hidden.get("total_cases"),
            "label": _hidden_label(hidden),
        },
        "final_submission_ready": packaged.get("final_submission_ready"),
        "official_token_reduction_enabled": official.get("promotion_kept", True),
        "repair_execution_enabled": sources["hidden_style"].get("repair_execution_enabled", False),
        "compact_context_enabled": sources["hidden_style"].get("compact_context_enabled", False),
        "runtime": _first_number(packaged.get("runtime"), strict.get("avg_runtime")),
        "tool_calls": _first_number(packaged.get("tool_calls"), strict.get("avg_tool_call_count")),
        "estimated_tokens": _first_number(packaged.get("estimated_tokens"), strict.get("avg_estimated_tokens")),
        "architecture": [
            "Deterministic-first natural-language QA agent",
            "DuckDB SQL over local parquet snapshots",
            "Adobe API verification in dry-run mode when credentials are unavailable",
            "Evidence-driven answer synthesis and trajectory logging",
        ],
        "workflow": [
            "Prompt normalization and query analysis",
            "Metadata/context selection",
            "SQL_FIRST_API_VERIFY planning",
            "Validated SQL/API execution",
            "Evidence extraction, answer synthesis, verification, and packaging",
        ],
        "final_recommendation": sources["winner_readiness"].get("final_recommendation", "ready_to_submit_with_official_token_reduction"),
        "source_reports": [
            "outputs/eval_results_strict.json",
            "outputs/winner_readiness_report.json",
            "outputs/hidden_style_eval.json",
            "outputs/official_token_reduction_promotion_report.json",
        ],
    }


def build_llm_baseline_summary(config: Config, sources: dict[str, Any]) -> dict[str, Any]:
    baseline = sources["llm_baseline"]
    strict = sources["llm_strict"]
    per_strategy = baseline.get("per_strategy") or strict.get("per_strategy") or []
    best = _best_llm_strategy(per_strategy)
    deterministic = baseline.get("deterministic_sql_first_api_verify", {})
    return {
        "report_type": "llm_baseline_summary",
        "framework": baseline.get("framework") or strict.get("framework") or "generic_sdk_llm_baseline",
        "framework_note": "The LLM baseline framework is generic; Qwen is only the current configured backend/model metadata.",
        "current_backend_model": baseline.get("backend_name") or strict.get("backend_name") or sources["llm_backend"].get("backend_name"),
        "provider_type": baseline.get("provider_type") or strict.get("provider_type") or sources["llm_backend"].get("provider_type"),
        "backend_type": baseline.get("backend_type") or strict.get("backend_type") or sources["llm_backend"].get("backend_type"),
        "anthropic_sdk_support": "available_in_client; configure LLM_PROVIDER=anthropic with ANTHROPIC_API_KEY",
        "tool_calling_supported": baseline.get("tool_calling_supported", sources["llm_backend"].get("tool_calling_supported")),
        "smoke_test_passed": baseline.get("smoke_test_passed", sources["llm_backend"].get("ok")),
        "strict_scoring_status": baseline.get("strict_scoring_status", strict.get("summary", {}).get("strict_scoring_status")),
        "best_llm_baseline": best,
        "best_llm_baseline_score": best.get("strict_score") or best.get("strict_final_score"),
        "sql_first_api_verify_score": deterministic.get("avg_final_score") or _sql_first_metrics(sources).get("avg_final_score"),
        "comparison_against_deterministic": strict.get("comparison_against_deterministic") or baseline.get("comparison_against_deterministic"),
        "recommendation": baseline.get("recommendation") or strict.get("summary", {}).get("recommendation") or "keep_shadow_only",
        "reason": "Deterministic SQL_FIRST_API_VERIFY remains higher under strict scoring.",
        "source_reports": [
            "outputs/llm_sdk_backend_check.json",
            "outputs/llm_baseline_eval_report.json",
            "outputs/llm_strict_baseline_eval.json",
            "outputs/llm_hidden_style_diagnostic.json",
        ],
    }


def build_accuracy_and_bottleneck_summary(config: Config, sources: dict[str, Any]) -> dict[str, Any]:
    autonomous = sources["autonomous_score_push"].get("summary", {})
    trial = sources["autonomous_trial"].get("summary", {})
    best_isolated = _best_isolated_score(sources)
    return {
        "report_type": "accuracy_and_bottleneck_summary",
        "starting_score": autonomous.get("starting_score", 0.6491),
        "best_isolated_score": best_isolated,
        "target_0_70_reached": bool(autonomous.get("target_0_70_reached", False) or trial.get("target_0_70_reached", False)),
        "target_0_75_reached": bool(autonomous.get("target_0_75_reached", False) or trial.get("target_0_75_reached", False)),
        "answer_quality_bottleneck": True,
        "dry_run_api_limitation": True,
        "answer_shape_v2_status": _status_from_report(sources["answer_shape_v2"], "shadow_only"),
        "supportable_rewrite_status": _status_from_report(sources["supportable_rewrite"], "safe_for_autonomous_packaged_trial"),
        "llm_answer_rewrite_status": _status_from_report(sources["llm_answer_rewrite"], "keep_shadow_only"),
        "endpoint_tiebreak_status": _status_from_report(sources["endpoint_tiebreak"], "keep_shadow_only"),
        "endpoint_schema_canary_status": _status_from_report(sources["endpoint_schema_canary"], "keep_shadow_only"),
        "ast_canary_status": _status_from_report(sources["ast_canary"], "keep_shadow_only"),
        "why_shadow_only": [
            "The 0.70 and 0.75 targets were not reached safely.",
            "High-potential answer rewrites remain constrained by dry-run API payload unavailability.",
            "Endpoint/schema and AST changes are report-only or shadow-only unless strict gates improve.",
        ],
        "source_reports": [
            "outputs/autonomous_score_push_report.json",
            "outputs/autonomous_packaged_trial.json",
            "outputs/score075_blocker_analysis.json",
            "outputs/supportable_answer_rewrite_eval.json",
            "outputs/endpoint_family_tiebreak_v2_shadow.json",
            "outputs/ast_guided_sql_candidate_canary.json",
        ],
    }


def build_visualization_summary(config: Config, sources: dict[str, Any]) -> dict[str, Any]:
    story = sources["sql_storyboard"]
    return {
        "report_type": "visualization_summary",
        "primary_example": story.get("query_id", "example_011"),
        "raw_prompt": story.get("raw_prompt", "How many schemas do I have?"),
        "prompt_to_sql_mapping": {
            "schemas": story.get("selected_table", "dim_blueprint"),
            "how_many": story.get("aggregation", "COUNT DISTINCT"),
            "identifier_column": story.get("selected_column", "BLUEPRINTID"),
            "result": story.get("sql_result_summary", "blueprint_count = 74"),
        },
        "main_storyboard": "outputs/visualizations/sql_prompt_storyboard_primary.md",
        "supervisor_visualizations": [
            "outputs/visualizations/executive_dashboard.md",
            "outputs/visualizations/sql_prompt_storyboard_primary.md",
            "outputs/visualizations/system_status_dashboard.md",
            "outputs/visualizations/score_bottleneck_dashboard.md",
        ],
        "secondary_reference": "example_031 remains a secondary API/dry-run bottleneck reference only.",
        "source_reports": [
            "outputs/visualizations/sql_prompt_storyboard_primary.json",
            "outputs/visualizations/index.json",
        ],
    }


def build_report_index(
    config: Config,
    system: dict[str, Any],
    llm: dict[str, Any],
    accuracy: dict[str, Any],
    visualization: dict[str, Any],
) -> dict[str, Any]:
    return {
        "report_type": "report_index",
        "message": "Start here. Most older generated reports were consolidated or removed.",
        "canonical_reports": [
            "outputs/reports/system_summary.md",
            "outputs/reports/llm_baseline_summary.md",
            "outputs/reports/accuracy_and_bottleneck_summary.md",
            "outputs/reports/visualization_summary.md",
            "outputs/reports/overnight_autonomous_improvement_report.md",
            "outputs/reports/report_index.md",
        ],
        "key_source_of_truth_reports": [
            "outputs/eval_results_strict.json",
            "outputs/winner_readiness_report.md",
            "outputs/final_research_inspired_improvement_report.md",
            "outputs/hidden_style_eval.md",
            "outputs/llm_strict_baseline_eval.md",
        ],
        "key_visualizations": visualization["supervisor_visualizations"],
        "diagnostic_prompt_coverage": [
            {
                "path": "outputs/reports/generated_prompt_suite_summary.md",
                "label": "Diagnostic prompt coverage only; not official strict score.",
            },
            {
                "path": "outputs/reports/diagnostic_prompt_suite_run.md",
                "label": "Diagnostic prompt runtime coverage only; not official strict score.",
            },
        ],
        "sdk_usage_audit": {
            "path": "outputs/reports/sdk_usage_audit.md",
            "runtime_llm_direct_http_hits": _load_json(config.outputs_dir / "reports" / "sdk_usage_audit.json")
            .get("summary", {})
            .get("runtime_llm_direct_http_hits", "unavailable"),
        },
        "cleanup_reports": [
            "outputs/reports/cleanup_audit.md",
            "outputs/reports/cleanup_final_report.md",
        ],
        "post_change_validation": {
            "required_commands": list(POST_CHANGE_VALIDATION_COMMANDS),
            "report_regeneration_targets": list(REPORT_REGENERATION_TARGETS),
            "skip_policy": "Skipped commands must record command, reason, substitute validation, and residual risk.",
            "final_response_must_include": [
                "files changed",
                "reports generated",
                "files deleted",
                "validation commands run and results",
                "skipped commands and reasons",
                "check_submission_ready status",
                "secret scan status",
                "SQL_FIRST_API_VERIFY unchanged confirmation",
                "final submission format unchanged confirmation",
            ],
        },
        "current_status": {
            "preferred_strategy": system["preferred_strategy"],
            "packaged_strict_score": system["packaged_strict_score"],
            "best_isolated_score": system["best_isolated_score"],
            "hidden_style": system["hidden_style"]["label"],
            "final_submission_ready": system["final_submission_ready"],
            "llm_recommendation": llm["recommendation"],
            "target_0_75_reached": accuracy["target_0_75_reached"],
        },
    }


def render_system_summary(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# System Summary",
            "",
            f"- Preferred strategy: `{payload['preferred_strategy']}`",
            f"- Packaged strict score: `{payload['packaged_strict_score']}`",
            f"- Best isolated score: `{payload['best_isolated_score']}`",
            f"- Hidden-style: `{payload['hidden_style']['label']}`",
            f"- Final submission ready: `{payload['final_submission_ready']}`",
            f"- Official-token reduction enabled: `{payload['official_token_reduction_enabled']}`",
            f"- Repair execution enabled: `{payload['repair_execution_enabled']}`",
            f"- Compact context enabled: `{payload['compact_context_enabled']}`",
            f"- Final recommendation: `{payload['final_recommendation']}`",
            "",
            "## Workflow",
            "",
            *[f"- {item}" for item in payload["workflow"]],
            "",
            "## Source Reports",
            "",
            *[f"- `{path}`" for path in payload["source_reports"]],
            "",
        ]
    )


def render_llm_summary(payload: dict[str, Any]) -> str:
    best = payload.get("best_llm_baseline") or {}
    return "\n".join(
        [
            "# LLM Baseline Summary",
            "",
            f"- Framework: `{payload['framework']}`",
            f"- Current backend/model: `{payload.get('current_backend_model')}`",
            f"- Provider/backend type: `{payload.get('provider_type')}` / `{payload.get('backend_type')}`",
            f"- Anthropic SDK support: {payload.get('anthropic_sdk_support')}",
            f"- Tool calling supported: `{payload.get('tool_calling_supported')}`",
            f"- Best LLM baseline: `{best.get('system', 'unavailable')}`",
            f"- Best LLM baseline score: `{payload.get('best_llm_baseline_score')}`",
            f"- SQL_FIRST_API_VERIFY score: `{payload.get('sql_first_api_verify_score')}`",
            f"- Recommendation: `{payload.get('recommendation')}`",
            f"- Reason: {payload.get('reason')}",
            "",
            payload["framework_note"],
            "",
        ]
    )


def render_accuracy_summary(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Accuracy And Bottleneck Summary",
            "",
            f"- Starting score: `{payload.get('starting_score')}`",
            f"- Best isolated score: `{payload.get('best_isolated_score')}`",
            f"- 0.70 target reached: `{payload.get('target_0_70_reached')}`",
            f"- 0.75 target reached: `{payload.get('target_0_75_reached')}`",
            f"- Answer-quality bottleneck: `{payload.get('answer_quality_bottleneck')}`",
            f"- Dry-run API limitation: `{payload.get('dry_run_api_limitation')}`",
            f"- Supportable rewrite status: `{payload.get('supportable_rewrite_status')}`",
            f"- Endpoint tie-break status: `{payload.get('endpoint_tiebreak_status')}`",
            f"- AST canary status: `{payload.get('ast_canary_status')}`",
            "",
            "## Why Changes Remain Shadow-Only",
            "",
            *[f"- {item}" for item in payload["why_shadow_only"]],
            "",
        ]
    )


def render_visualization_summary(payload: dict[str, Any]) -> str:
    mapping = payload["prompt_to_sql_mapping"]
    return "\n".join(
        [
            "# Visualization Summary",
            "",
            f"- Primary example: `{payload['primary_example']}`",
            f"- Raw prompt: {payload['raw_prompt']}",
            f"- Main storyboard: `{payload['main_storyboard']}`",
            f"- Secondary reference: {payload['secondary_reference']}",
            "",
            "## Prompt To SQL Mapping",
            "",
            f"- `schemas` → `{mapping['schemas']}`",
            f"- `how many` → `{mapping['how_many']}`",
            f"- `{mapping['identifier_column']}` → `{mapping['result']}`",
            "",
        ]
    )


def render_report_index(payload: dict[str, Any]) -> str:
    lines = [
        "# Consolidated Report Index",
        "",
        payload["message"],
        "",
        "## Canonical Reports",
        "",
    ]
    lines.extend(f"- [{Path(path).name}]({Path(path).name})" for path in payload["canonical_reports"])
    lines.extend(["", "## Key Source-Of-Truth Reports", ""])
    lines.extend(f"- `{path}`" for path in payload["key_source_of_truth_reports"])
    lines.extend(["", "## Key Visualizations", ""])
    lines.extend(f"- `{path}`" for path in payload["key_visualizations"])
    lines.extend(["", "## Diagnostic Prompt Coverage", ""])
    for item in payload.get("diagnostic_prompt_coverage", []):
        lines.append(f"- `{item['path']}` - {item['label']}")
    lines.extend(["", "## System-Wide SDK LLM Audit", ""])
    audit = payload.get("sdk_usage_audit", {})
    lines.append(f"- `{audit.get('path')}`")
    lines.append(f"- Runtime LLM direct HTTP hits: `{audit.get('runtime_llm_direct_http_hits')}`")
    lines.extend(["", "## Cleanup Reports", ""])
    lines.extend(f"- `{path}`" for path in payload.get("cleanup_reports", []))
    lines.extend(["", "## Post-Change Validation Contract", ""])
    lines.append(payload["post_change_validation"]["skip_policy"])
    lines.extend(["", "Required commands:"])
    lines.extend(f"- `{command}`" for command in payload["post_change_validation"]["required_commands"])
    lines.extend(["", "Regenerated report surfaces:"])
    lines.extend(f"- `{path}`" for path in payload["post_change_validation"]["report_regeneration_targets"])
    lines.extend(["", "## Current Status", ""])
    for key, value in payload["current_status"].items():
        lines.append(f"- {key}: `{value}`")
    return "\n".join(lines) + "\n"


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _sql_first_metrics(sources: dict[str, Any]) -> dict[str, Any]:
    return (
        sources.get("eval_results_strict", {})
        .get("summary", {})
        .get("by_strategy", {})
        .get("SQL_FIRST_API_VERIFY", {})
    )


def _best_isolated_score(sources: dict[str, Any]) -> float | str:
    candidates = [
        sources["autonomous_trial"].get("summary", {}).get("strict_final_score"),
        sources["autonomous_score_push"].get("summary", {}).get("best_achieved_score"),
        sources["score075_blocker"].get("best_achieved_score"),
    ]
    numbers = [float(value) for value in candidates if isinstance(value, (int, float))]
    return round(max(numbers), 4) if numbers else "unavailable"


def _hidden_label(summary: dict[str, Any]) -> str:
    passed = summary.get("passed_cases")
    total = summary.get("total_cases")
    if passed is None or total is None:
        return "unavailable"
    return f"{passed}/{total}"


def _best_llm_strategy(rows: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [
        row for row in rows
        if isinstance(row.get("strict_score", row.get("strict_final_score")), (int, float))
    ]
    if not scored:
        return {"system": "unavailable", "strict_score": "unavailable"}
    best = max(scored, key=lambda row: float(row.get("strict_score", row.get("strict_final_score"))))
    return {
        "system": best.get("system"),
        "strict_score": best.get("strict_score", best.get("strict_final_score")),
        "strict_correctness": best.get("strict_correctness"),
    }


def _status_from_report(report: dict[str, Any], default: str) -> str:
    summary = report.get("summary", {})
    return (
        summary.get("recommendation")
        or report.get("recommendation")
        or ("shadow_only" if report.get("shadow_only") else None)
        or default
    )


def _first_number(*values: Any) -> float | str:
    for value in values:
        if isinstance(value, (int, float)):
            return round(float(value), 4)
    return "unavailable"


def _safe_payload(payload: dict[str, Any]) -> dict[str, Any]:
    safe = redact_secrets(payload)
    return safe if isinstance(safe, dict) else payload


def _rel(config: Config, path: Path) -> str:
    return path.resolve().relative_to(config.project_root.resolve()).as_posix()


if __name__ == "__main__":
    raise SystemExit(main())
