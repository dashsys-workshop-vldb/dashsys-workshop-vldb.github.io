#!/usr/bin/env python
from __future__ import annotations

import copy
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.trajectory import redact_secrets


PREFLIGHT_STEM = "sdk_tool_calling_optimization_preflight"
SURFACE_STEM = "sdk_tool_call_surface_audit"
DECISION_STEM = "sdk_tool_call_decision_analysis"
VARIANTS_STEM = "sdk_tool_call_optimization_variants"

PROTECTED_ARTIFACTS = [
    "outputs/final_submission/**",
    "outputs/eval_results_strict.json",
    "outputs/hidden_style_eval.*",
    "outputs/final_submission_manifest.json",
    "final_submission_manifest.json",
    ".env.local",
    "dashagent/endpoint_catalog.py",
    "packaged strategy/default config",
]

ALLOWED_SURFACE_CLASSIFICATIONS = [
    "aligned",
    "schema_too_large",
    "ambiguous_tool_description",
    "unnecessary_tool_available",
    "missing_tool_choice_control",
    "parallel_calls_uncontrolled",
    "tool_result_too_verbose",
    "provider_normalization_gap",
    "usage_metadata_gap",
    "no_action",
]

ALLOWED_DECISION_CLASSIFICATIONS = [
    "tool_call_helpful",
    "unnecessary_tool_call",
    "wrong_tool_selected",
    "tool_args_brittle",
    "tool_result_too_verbose",
    "no_tool_needed",
    "deterministic_better",
    "LLM_rewrite_hurt",
    "LLM_rewrite_helped",
    "blocked_by_live_api",
    "no_clear_signal",
]

VARIANT_IDS = [
    "compact_tool_schema",
    "allowed_tools_by_prompt_type",
    "tool_choice_policy",
    "disable_parallel_tool_calls",
    "compact_tool_result_evidence_summary",
    "rewrite_gate_strict",
    "no_rewrite_when_backend_complete",
    "combined_safe_tool_policy",
]

SOURCE_FILES_TO_AUDIT = [
    "dashagent/llm_client.py",
    "dashagent/llm_tool_agent.py",
    "dashagent/semantic_routing_helper.py",
    "dashagent/supportable_answer_rewriter.py",
    "dashagent/eval_harness.py",
    "scripts/run_llm_baseline_eval.py",
    "scripts/run_llm_strict_baseline_eval.py",
    "scripts/run_llm_semantic_router_shadow_eval.py",
    "scripts/run_evidence_aware_answer_rewrite_trial.py",
    "scripts/run_controller_rewrite_ablation.py",
    "tests/test_llm_client.py",
    "tests/test_real_llm_tool_loop.py",
    "tests/test_real_llm_tool_loop_feedback.py",
]


def main() -> int:
    config = Config.from_env(ROOT)
    payload = run_sdk_tool_calling_optimization_audit(config)
    print(
        json.dumps(
            {
                "preflight": str(config.outputs_dir / "reports" / f"{PREFLIGHT_STEM}.json"),
                "surface_audit": str(config.outputs_dir / "reports" / f"{SURFACE_STEM}.json"),
                "decision_analysis": str(config.outputs_dir / "reports" / f"{DECISION_STEM}.json"),
                "variants": str(config.outputs_dir / "reports" / f"{VARIANTS_STEM}.json"),
                "runtime_change_allowed": payload.get("preflight", {}).get("runtime_change_allowed"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def run_sdk_tool_calling_optimization_audit(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    sources = _load_sources(config)
    inspected_sources = _inspect_source_files()
    git_status = _git_status(config.project_root)
    protected_findings = _protected_change_findings(git_status)

    preflight = _build_preflight(config, sources, inspected_sources, git_status, protected_findings)
    surface = _build_surface_audit(sources, inspected_sources)
    decision = _build_decision_analysis(sources)
    variants = _build_variants(sources, surface, decision)

    payload = {
        "preflight": preflight,
        "surface_audit": surface,
        "decision_analysis": decision,
        "variants": variants,
    }
    _write_json(reports_dir / f"{PREFLIGHT_STEM}.json", preflight)
    (reports_dir / f"{PREFLIGHT_STEM}.md").write_text(_render_preflight(preflight), encoding="utf-8")
    _write_json(reports_dir / f"{SURFACE_STEM}.json", surface)
    (reports_dir / f"{SURFACE_STEM}.md").write_text(_render_surface(surface), encoding="utf-8")
    _write_json(reports_dir / f"{DECISION_STEM}.json", decision)
    (reports_dir / f"{DECISION_STEM}.md").write_text(_render_decision_analysis(decision), encoding="utf-8")
    _write_json(reports_dir / f"{VARIANTS_STEM}.json", variants)
    (reports_dir / f"{VARIANTS_STEM}.md").write_text(_render_variants(variants), encoding="utf-8")
    return payload


def compact_tool_schema(tool: dict[str, Any], *, max_description_chars: int = 140) -> dict[str, Any]:
    """Return a shorter tool schema while preserving names and required parameters."""
    compact = copy.deepcopy(tool)
    function = compact.get("function") if isinstance(compact.get("function"), dict) else compact
    if isinstance(function.get("description"), str):
        function["description"] = _shorten(function["description"], max_description_chars)
    parameters = function.get("parameters") or function.get("input_schema")
    if isinstance(parameters, dict):
        for prop in (parameters.get("properties") or {}).values():
            if isinstance(prop, dict) and isinstance(prop.get("description"), str):
                prop["description"] = _shorten(prop["description"], 80)
        if "required" in parameters and not isinstance(parameters["required"], list):
            parameters["required"] = list(parameters["required"])
    return compact


def compact_tool_result_evidence_summary(result: dict[str, Any]) -> dict[str, Any]:
    rows = _extract_rows(result)
    key_fields = _key_fields(rows)
    summary: dict[str, Any] = {
        "evidence_type": result.get("evidence_type") or result.get("tool_name") or result.get("type") or "unknown",
        "row_count": _row_count(result, rows),
        "key_fields": key_fields,
        "api_state": result.get("api_state") or result.get("evidence_state") or result.get("safe_error_category"),
        "caveat": result.get("caveat") or result.get("warning") or result.get("error_category"),
    }
    sample_values: dict[str, list[Any]] = {}
    for field in key_fields[:8]:
        values = []
        for row in rows[:5]:
            if field in row and row[field] is not None:
                values.append(row[field])
        if values:
            sample_values[field] = values[:3]
    if sample_values:
        summary["sample_values"] = sample_values
    return redact_secrets(summary)


def rewrite_gate_allows_rewrite(backend_answer: str, verifier: dict[str, Any], evidence: dict[str, Any]) -> bool:
    if verifier.get("backend_complete"):
        return False
    if int(verifier.get("unsupported_claim_count") or 0) > 0:
        return False
    if not _has_evidence(evidence):
        return False
    if not backend_answer and not evidence:
        return False
    return True


def _build_preflight(
    config: Config,
    sources: dict[str, Any],
    inspected_sources: dict[str, Any],
    git_status: dict[str, Any],
    protected_findings: list[dict[str, Any]],
) -> dict[str, Any]:
    system = sources.get("system_summary") or {}
    strict = sources.get("eval_results_strict") or {}
    llm_summary = sources.get("llm_baseline_summary") or {}
    sdk = sources.get("sdk_usage_audit") or {}
    preflight = {
        "report_type": PREFLIGHT_STEM,
        "generated_at": _now(),
        "git_status": git_status,
        "protected_change_findings": protected_findings,
        "blocker": bool(protected_findings),
        "packaged_strategy": system.get("preferred_strategy") or _best_overall_strategy(strict) or "SQL_FIRST_API_VERIFY",
        "strict_score": _strict_score(system, strict),
        "llm_baseline_score": llm_summary.get("best_llm_baseline_score") or _llm_score_from_sources(sources),
        "current_backend_provider": llm_summary.get("provider_type") or llm_summary.get("provider") or "unavailable",
        "current_backend_model": llm_summary.get("current_backend_model") or llm_summary.get("backend_name") or "unavailable",
        "backend_type": llm_summary.get("backend_type") or "unavailable",
        "sdk_direct_http_hits": int((sdk.get("summary") or {}).get("runtime_llm_direct_http_hits") or 0),
        "tool_calling_supported": llm_summary.get("tool_calling_supported", "unavailable"),
        "promotion_status": {
            "semantic_router": (sources.get("llm_semantic_router_promotion_decision") or {}).get("decision", "not_run"),
            "controller": ((sources.get("controller_rewrite_ablation") or {}).get("summary") or {}).get("recommendation", "not_run"),
            "answer_rewrite": ((sources.get("evidence_aware_answer_rewrite_trial") or {}).get("recommendation") or "trial_only"),
        },
        "runtime_change_allowed": False,
        "diagnostic_only": True,
        "official_score_claim": False,
        "protected_artifacts": PROTECTED_ARTIFACTS,
        "no_hardcoding_rule": True,
        "source_files_audited": inspected_sources.get("files", []),
        "source_inspection": inspected_sources.get("summary", {}),
    }
    return _safe(preflight)


def _build_surface_audit(sources: dict[str, Any], inspected_sources: dict[str, Any]) -> dict[str, Any]:
    llm_client = inspected_sources.get("contents", {}).get("dashagent/llm_client.py", "")
    llm_tool_agent = inspected_sources.get("contents", {}).get("dashagent/llm_tool_agent.py", "")
    issues: list[dict[str, Any]] = []

    issues.append(
        _issue(
            "openai_sdk_client",
            "openai_compatible",
            "aligned" if "OpenAI(" in llm_client and "chat.completions.create" in llm_client else "provider_normalization_gap",
            "OpenAI-compatible calls are routed through the OpenAI SDK client.",
            ["dashagent/llm_client.py"],
        )
    )
    issues.append(
        _issue(
            "openai_tool_choice",
            "openai_compatible",
            "aligned" if "tool_choice" in llm_client else "missing_tool_choice_control",
            "Tool choice is accepted by the shared generate_messages path.",
            ["dashagent/llm_client.py"],
        )
    )
    issues.append(
        _issue(
            "openai_parallel_tool_calls",
            "openai_compatible",
            "aligned" if "parallel_tool_calls" in llm_client or "parallel_tool_calls" in llm_tool_agent else "parallel_calls_uncontrolled",
            "No explicit parallel tool-call control was found in the SDK payload path.",
            ["dashagent/llm_client.py", "dashagent/llm_tool_agent.py"],
        )
    )
    issues.append(
        _issue(
            "openai_usage_metadata",
            "openai_compatible",
            "aligned" if "usage" in llm_client and "total_tokens" in llm_client else "usage_metadata_gap",
            "Usage metadata is read defensively when the SDK response contains it.",
            ["dashagent/llm_client.py"],
        )
    )
    issues.append(
        _issue(
            "anthropic_sdk_client",
            "anthropic",
            "aligned" if "Anthropic(" in llm_client and "messages.create" in llm_client else "provider_normalization_gap",
            "Anthropic calls are routed through the Anthropic SDK client.",
            ["dashagent/llm_client.py"],
        )
    )
    issues.append(
        _issue(
            "anthropic_tool_shape",
            "anthropic",
            "aligned" if "_anthropic_tools" in llm_client and "input_schema" in llm_client else "provider_normalization_gap",
            "OpenAI function tools are converted into Anthropic name/description/input_schema tools.",
            ["dashagent/llm_client.py"],
        )
    )
    issues.append(
        _issue(
            "anthropic_tool_use_normalization",
            "anthropic",
            "aligned" if "_normalize_anthropic_tool_calls" in llm_client and "tool_use" in llm_client else "provider_normalization_gap",
            "Anthropic tool_use blocks are normalized into the shared tool-call shape.",
            ["dashagent/llm_client.py"],
        )
    )
    schemas = _baseline_tool_schemas_from_source(llm_tool_agent)
    schema_chars = len(json.dumps(schemas, sort_keys=True, default=str))
    issues.append(
        _issue(
            "baseline_tool_schema_size",
            "all_providers",
            "schema_too_large" if schema_chars > 1800 else "aligned",
            f"Baseline tool schema estimate is {schema_chars} characters.",
            ["dashagent/llm_tool_agent.py"],
            {"schema_chars": schema_chars, "tool_count": len(schemas)},
        )
    )
    issues.append(
        _issue(
            "two_tools_always_available_baseline",
            "all_providers",
            "unnecessary_tool_available",
            "The two-tool LLM baseline exposes execute_sql and call_api together; prompt-type pruning is trial-only.",
            ["dashagent/llm_tool_agent.py"],
        )
    )
    issues.append(
        _issue(
            "tool_result_message_size",
            "all_providers",
            "tool_result_too_verbose" if "result_preview" in llm_tool_agent else "no_action",
            "Tool results expose preview/error state; compact EvidenceBus summaries may reduce token use in shadow trials.",
            ["dashagent/llm_tool_agent.py"],
        )
    )
    issues.append(
        _issue(
            "direct_http_guard",
            "all_providers",
            "aligned"
            if int(((sources.get("sdk_usage_audit") or {}).get("summary") or {}).get("runtime_llm_direct_http_hits") or 0) == 0
            else "provider_normalization_gap",
            "SDK usage audit reports runtime direct LLM HTTP hits.",
            ["outputs/reports/sdk_usage_audit.json"],
            {"runtime_llm_direct_http_hits": int(((sources.get("sdk_usage_audit") or {}).get("summary") or {}).get("runtime_llm_direct_http_hits") or 0)},
        )
    )

    classification_counts = Counter(issue["classification"] for issue in issues)
    surface = {
        "report_type": SURFACE_STEM,
        "generated_at": _now(),
        "diagnostic_only": True,
        "official_score_claim": False,
        "allowed_classifications": ALLOWED_SURFACE_CLASSIFICATIONS,
        "audited_areas": ["openai_compatible", "anthropic", "all_providers"],
        "issues": issues,
        "classification_counts": dict(sorted(classification_counts.items())),
        "summary": {
            "direct_http_hits": int(((sources.get("sdk_usage_audit") or {}).get("summary") or {}).get("runtime_llm_direct_http_hits") or 0),
            "tool_schema_chars": schema_chars,
            "tool_count": len(schemas),
            "runtime_change_recommended": False,
            "recommendation": "trial_only_shadow_optimization",
        },
    }
    return _safe(surface)


def _build_decision_analysis(sources: dict[str, Any]) -> dict[str, Any]:
    strict = sources.get("eval_results_strict") or {}
    generated = sources.get("generated_prompt_suite_local_diagnostic") or {}
    official_rows = _strict_rows(strict)
    generated_rows = generated.get("rows") or []

    rows: list[dict[str, Any]] = []
    for row in official_rows:
        rows.append(_official_decision_row(row))
    for row in generated_rows[:40]:
        rows.append(_generated_decision_row(row))

    counts = Counter(row["classification"] for row in rows)
    decision = {
        "report_type": DECISION_STEM,
        "generated_at": _now(),
        "diagnostic_only": True,
        "official_score_claim": False,
        "allowed_classifications": ALLOWED_DECISION_CLASSIFICATIONS,
        "official_rows_analyzed": len(official_rows),
        "generated_prompts_analyzed": len(generated_rows),
        "generated_prompts_diagnostic_only": bool(generated.get("diagnostic_only", True)),
        "rows": rows,
        "classification_counts": dict(sorted(counts.items())),
        "summary": {
            "deterministic_path_better_rows": counts.get("deterministic_better", 0),
            "blocked_by_live_api_rows": counts.get("blocked_by_live_api", 0),
            "unnecessary_tool_call_rows": counts.get("unnecessary_tool_call", 0),
            "llm_rewrite_hurt_rows": counts.get("LLM_rewrite_hurt", 0),
            "recommendation": "use_artifact_replay_for_shadow_variants_only",
        },
    }
    return _safe(decision)


def _build_variants(sources: dict[str, Any], surface: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any]:
    rows = decision.get("rows") or []
    counts = Counter(row.get("classification") for row in rows)
    issue_counts = Counter(issue.get("classification") for issue in surface.get("issues") or [])
    variants = [
        _variant(
            "compact_tool_schema",
            "Reduce tool descriptions/schema wording while preserving required parameters.",
            ["baseline_tool_schema_size"],
            "token input reduction",
            "low",
            "scripts/run_sdk_tool_calling_optimization_trials.py",
            ["tool schema compression preserves required parameters"],
            issue_counts.get("schema_too_large", 0),
        ),
        _variant(
            "allowed_tools_by_prompt_type",
            "Expose only tools needed by deterministic prompt type in shadow/controller trials.",
            ["no_tool_needed", "unnecessary_tool_available"],
            "tool-call reduction",
            "medium",
            "shadow controller policy only",
            ["SQL-only prompt exposes SQL/no API in simulation", "API_REQUIRED prompts keep API available"],
            counts.get("no_tool_needed", 0) + counts.get("unnecessary_tool_call", 0),
        ),
        _variant(
            "tool_choice_policy",
            "Select no-tools, allowed-tools, or forced-SQL policy by deterministic route evidence.",
            ["tool_choice", "route_type", "answer_intent"],
            "tool-call stability",
            "medium",
            "shadow tool policy",
            ["forced SQL only for SQL-answerable evidence", "no forced API while live_success_count=0"],
            counts.get("deterministic_better", 0),
        ),
        _variant(
            "disable_parallel_tool_calls",
            "Set or simulate parallel_tool_calls=false where supported.",
            ["parallel_calls_uncontrolled"],
            "stability",
            "low",
            "SDK payload guard",
            ["provider payload does not break when flag unsupported", "strict score no-regression if applied"],
            issue_counts.get("parallel_calls_uncontrolled", 0),
        ),
        _variant(
            "compact_tool_result_evidence_summary",
            "Summarize tool outputs as EvidenceBus fields instead of verbose raw previews.",
            ["tool_result_too_verbose"],
            "token output reduction",
            "low",
            "tool result formatter",
            ["count/name/status/timestamp fields preserved", "API state preserved"],
            issue_counts.get("tool_result_too_verbose", 0),
        ),
        _variant(
            "rewrite_gate_strict",
            "Allow rewrite only when backend answer is incomplete, evidence exists, and faithfulness passes.",
            ["LLM_rewrite_hurt", "backend_complete"],
            "unsupported claim reduction",
            "medium",
            "answer rewrite trial gate",
            ["complete backend answer skips rewrite", "unsupported facts block rewrite"],
            counts.get("LLM_rewrite_hurt", 0),
        ),
        _variant(
            "no_rewrite_when_backend_complete",
            "Skip LLM rewrite when backend answer already contains required evidence fields.",
            ["backend_complete", "required evidence present"],
            "runtime/token reduction",
            "low",
            "answer rewrite gate",
            ["backend_complete true skips rewrite", "incomplete answer may still be trialed"],
            counts.get("deterministic_better", 0),
        ),
        _variant(
            "combined_safe_tool_policy",
            "Combine safe schema compression, compact evidence summary, and strict rewrite gating in shadow replay.",
            ["compact_tool_schema", "compact_tool_result_evidence_summary", "rewrite_gate_strict"],
            "combined token/tool reduction",
            "medium",
            "shadow-only combined trial",
            ["isolated output root", "no official artifact overwrite", "no final submission write"],
            max(1, counts.get("deterministic_better", 0) + issue_counts.get("parallel_calls_uncontrolled", 0)),
        ),
    ]
    payload = {
        "report_type": VARIANTS_STEM,
        "generated_at": _now(),
        "diagnostic_only": True,
        "official_score_claim": False,
        "promotion_allowed": False,
        "variants": variants,
        "promotion_gate": [
            "strict score improves or speed/tool-call reduction has zero strict regression",
            "hidden-style remains 48/48 if runtime changes are made",
            "check_submission_ready passes",
            "SDK direct HTTP hits remain 0",
            "unsupported claims do not increase",
            "no high-scoring official rows regress",
            "no live API assumption while live_success_count=0",
            "no hardcoding",
            "final submission format unchanged",
        ],
        "default_decision": "trial_only_no_runtime_change",
    }
    return _safe(payload)


def _official_decision_row(row: dict[str, Any]) -> dict[str, Any]:
    strategy = str(row.get("strategy") or row.get("system") or "")
    route = str((row.get("trajectory") or {}).get("route_type") or row.get("route_type") or row.get("predicted_route") or "")
    tool_calls = int(row.get("tool_call_count") or 0)
    llm_calls = row.get("llm_tool_calls") or (row.get("trajectory") or {}).get("llm_tool_calls") or []
    score = row.get("final_score") if isinstance(row.get("final_score"), (int, float)) else row.get("total_strict_score")
    if "LLM" in strategy and (row.get("failure_reason") or "").lower().find("rewrite") >= 0:
        classification = "LLM_rewrite_hurt"
    elif "LLM" in strategy and tool_calls > 2:
        classification = "unnecessary_tool_call"
    elif route == "API_ONLY" or "api" in str(row.get("api_reason") or row.get("failure_reason") or "").lower():
        classification = "blocked_by_live_api"
    elif strategy == "SQL_FIRST_API_VERIFY" and not llm_calls:
        classification = "deterministic_better"
    elif tool_calls == 0:
        classification = "no_tool_needed"
    else:
        classification = "no_clear_signal"
    return {
        "row_source": "official_strict_eval",
        "row_id": row.get("query_id") or row.get("example_id"),
        "prompt_type": _prompt_type(str(row.get("query") or row.get("prompt") or "")),
        "current_deterministic_route": route or row.get("predicted_route"),
        "llm_controller_route": row.get("controller_route") or "unavailable",
        "tools_exposed": ["execute_sql", "call_api"] if "LLM" in strategy else [],
        "tools_actually_called": [call.get("tool_name") or call.get("tool") or call.get("name") for call in llm_calls],
        "tool_args_shape": _tool_arg_shape(llm_calls),
        "tool_output_size": _safe_int(row.get("estimated_tokens")),
        "score": score,
        "tool_call_was_necessary": classification not in {"unnecessary_tool_call", "no_tool_needed", "deterministic_better"},
        "deterministic_path_better": classification == "deterministic_better",
        "sql_tool_should_be_forced": route in {"LOCAL_DB_ONLY", "SQL_THEN_API"} and classification != "blocked_by_live_api",
        "api_tool_should_be_hidden": route != "API_ONLY" and classification in {"deterministic_better", "unnecessary_tool_call", "no_tool_needed"},
        "no_tool_answer_allowed": classification == "no_tool_needed",
        "answer_rewrite_should_be_skipped": classification in {"LLM_rewrite_hurt", "deterministic_better"},
        "classification": classification,
        "evidence": _classification_evidence(row, classification),
    }


def _generated_decision_row(row: dict[str, Any]) -> dict[str, Any]:
    route = str(row.get("actual_route") or row.get("route") or "")
    dry_run_calls = int(row.get("dry_run_api_calls") or row.get("api_calls") or 0)
    requires_live = bool(row.get("requires_live_api"))
    if requires_live:
        classification = "blocked_by_live_api"
    elif dry_run_calls and route != "API_ONLY":
        classification = "unnecessary_tool_call"
    elif route in {"LOCAL_DB_ONLY", "SQL_ONLY"}:
        classification = "deterministic_better"
    else:
        classification = "no_clear_signal"
    return {
        "row_source": "generated_prompt_local_diagnostic",
        "prompt_id": row.get("prompt_id"),
        "prompt_type": _prompt_type(str(row.get("prompt") or "")),
        "current_deterministic_route": route,
        "llm_controller_route": "not_run",
        "tools_exposed": "diagnostic_simulation_only",
        "tools_actually_called": [],
        "tool_args_shape": {},
        "tool_output_size": _safe_int(row.get("tokens")),
        "score": None,
        "diagnostic_only": True,
        "tool_call_was_necessary": classification == "blocked_by_live_api",
        "deterministic_path_better": classification == "deterministic_better",
        "sql_tool_should_be_forced": route in {"LOCAL_DB_ONLY", "SQL_THEN_API"} and not requires_live,
        "api_tool_should_be_hidden": dry_run_calls > 0 and not requires_live,
        "no_tool_answer_allowed": False,
        "answer_rewrite_should_be_skipped": True,
        "classification": classification,
        "evidence": {
            "requires_live_api": requires_live,
            "dry_run_api_calls": dry_run_calls,
            "validation_failures": row.get("validation_failures"),
        },
    }


def _load_sources(config: Config) -> dict[str, Any]:
    reports = config.outputs_dir / "reports"
    return {
        "llm_baseline_summary": _load_json(reports / "llm_baseline_summary.json"),
        "llm_semantic_router_promotion_decision": _load_json(reports / "llm_semantic_router_promotion_decision.json"),
        "controller_rewrite_ablation": _load_json(reports / "controller_rewrite_ablation.json"),
        "evidence_aware_answer_rewrite_trial": _load_json(reports / "evidence_aware_answer_rewrite_trial.json"),
        "sdk_usage_audit": _load_json(reports / "sdk_usage_audit.json"),
        "system_summary": _load_json(reports / "system_summary.json"),
        "accuracy_and_bottleneck_summary": _load_json(reports / "accuracy_and_bottleneck_summary.json"),
        "eval_results_strict": _load_json(config.outputs_dir / "eval_results_strict.json"),
        "generated_prompt_suite_local_diagnostic": _load_json(reports / "generated_prompt_suite_local_diagnostic.json"),
        "comprehensive_failure_fix_decision": _load_json(reports / "comprehensive_failure_fix_decision.json"),
        "llm_baseline_eval": _load_json(config.outputs_dir / "llm_baseline_eval.json"),
        "llm_strict_baseline_eval": _load_json(config.outputs_dir / "llm_strict_baseline_eval.json"),
    }


def _inspect_source_files() -> dict[str, Any]:
    contents: dict[str, str] = {}
    files: list[str] = []
    for rel in SOURCE_FILES_TO_AUDIT:
        path = ROOT / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        contents[rel] = text
        files.append(rel)
    combined = "\n".join(contents.values())
    requests_post_marker = "requests" + ".post("
    requests_request_marker = "requests" + ".request("
    chat_completions_marker = "/chat" + "/completions"
    return {
        "files": files,
        "contents": contents,
        "summary": {
            "openai_sdk_imported": "from openai import OpenAI" in combined,
            "anthropic_sdk_imported": "from anthropic import Anthropic" in combined,
            "generate_messages_interface": "generate_messages" in combined,
            "native_tool_call_normalization": "_normalize_openai_tool_calls" in combined and "_normalize_anthropic_tool_calls" in combined,
            "direct_requests_runtime_seen": requests_post_marker in combined
            or requests_request_marker in combined
            or chat_completions_marker in combined,
            "parallel_tool_calls_configured": "parallel_tool_calls" in combined,
        },
    }


def _git_status(project_root: Path) -> dict[str, Any]:
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=project_root,
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
        )
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        return {
            "command": "git status --short",
            "exit_code": result.returncode,
            "lines": lines,
            "summary": "clean" if not lines else f"{len(lines)} changed paths",
            "fallback_used": False,
        }
    except Exception as exc:
        return {
            "command": "git status --short",
            "exit_code": None,
            "lines": [],
            "summary": f"unavailable: {type(exc).__name__}",
            "fallback_used": True,
        }


def _protected_change_findings(git_status: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for line in git_status.get("lines") or []:
        path = line[3:].strip() if len(line) > 3 else line.strip()
        status = line[:2]
        if path.startswith("outputs/final_submission/") or path in {
            "outputs/eval_results_strict.json",
            "outputs/final_submission_manifest.json",
            "final_submission_manifest.json",
            ".env.local",
            "dashagent/endpoint_catalog.py",
        } or path.startswith("outputs/hidden_style_eval."):
            findings.append({"path": path, "status": status.strip(), "reason": "protected_artifact_changed"})
        if path.startswith("dashagent/") and path.endswith(".py") and path not in {"dashagent/endpoint_catalog.py"}:
            findings.append({"path": path, "status": status.strip(), "reason": "runtime_source_changed"})
    return findings


def _baseline_tool_schemas_from_source(text: str) -> list[dict[str, Any]]:
    if "execute_sql" not in text:
        return []
    return [
        {
            "type": "function",
            "function": {
                "name": "execute_sql",
                "description": "Execute a read-only SQL query against the local DuckDB snapshot.",
                "parameters": {
                    "type": "object",
                    "properties": {"sql": {"type": "string", "description": "Read-only DuckDB SQL query."}},
                    "required": ["sql"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "call_api",
                "description": "Call an Adobe API endpoint using method, URL/path, params, and headers.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "method": {"type": "string"},
                        "url": {"type": "string"},
                        "params": {"type": "object"},
                        "headers": {"type": "object"},
                    },
                    "required": ["method", "url"],
                    "additionalProperties": False,
                },
            },
        },
    ]


def _issue(
    issue_id: str,
    area: str,
    classification: str,
    finding: str,
    repo_files: list[str],
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "issue_id": issue_id,
        "area": area,
        "classification": classification if classification in ALLOWED_SURFACE_CLASSIFICATIONS else "needs_manual_review",
        "finding": finding,
        "repo_files": repo_files,
        "code_audit_needed": classification != "aligned",
        "runtime_change_recommended": False,
    }
    if extra:
        payload.update(extra)
    return payload


def _variant(
    variant_id: str,
    description: str,
    trigger_signals: list[str],
    expected_impact: str,
    risk: str,
    implementation_scope: str,
    test_requirements: list[str],
    affected_signal_count: int,
) -> dict[str, Any]:
    return {
        "variant_id": variant_id,
        "description": description,
        "trigger_signals": trigger_signals,
        "expected_impact": expected_impact,
        "affected_rows_or_signals": affected_signal_count,
        "risk": risk,
        "implementation_scope": implementation_scope,
        "test_requirements": test_requirements,
        "promotion_status": "trial_only",
        "runtime_change_applied": False,
    }


def _classification_evidence(row: dict[str, Any], classification: str) -> dict[str, Any]:
    return {
        "strategy": row.get("strategy") or row.get("system"),
        "tool_call_count": row.get("tool_call_count"),
        "failure_reason": row.get("failure_reason"),
        "api_reason_present": bool(row.get("api_reason")),
        "classification": classification,
    }


def _tool_arg_shape(calls: list[dict[str, Any]]) -> dict[str, Any]:
    shape: dict[str, Any] = {}
    for call in calls:
        name = call.get("tool_name") or call.get("tool") or call.get("name") or "unknown"
        args = call.get("arguments") if isinstance(call.get("arguments"), dict) else {}
        shape.setdefault(str(name), sorted(str(key) for key in args.keys()))
    return shape


def _strict_rows(strict: dict[str, Any]) -> list[dict[str, Any]]:
    rows = strict.get("rows")
    if isinstance(rows, list):
        return [row for row in rows if isinstance(row, dict)]
    examples = strict.get("examples")
    if isinstance(examples, list):
        return [row for row in examples if isinstance(row, dict)]
    return []


def _prompt_type(prompt: str) -> str:
    text = prompt.lower()
    if any(token in text for token in ["how many", "count", "number of"]):
        return "count"
    if any(token in text for token in ["list", "show", "names", "ids"]):
        return "list/name/id"
    if "status" in text or "state" in text:
        return "status"
    if any(token in text for token in ["when", "date", "time", "latest"]):
        return "timestamp/date/when"
    if text.startswith(("is ", "are ", "does ", "do ")):
        return "yes/no"
    return "unknown/ambiguous"


def _row_count(result: dict[str, Any], rows: list[dict[str, Any]]) -> int | None:
    for key in ["row_count", "total_items", "count"]:
        value = result.get(key)
        if isinstance(value, (int, float)):
            return int(value)
    return len(rows) if rows else 0


def _extract_rows(result: dict[str, Any]) -> list[dict[str, Any]]:
    raw = result.get("rows")
    if isinstance(raw, dict) and isinstance(raw.get("items"), list):
        return [row for row in raw["items"] if isinstance(row, dict)]
    if isinstance(raw, list):
        return [row for row in raw if isinstance(row, dict)]
    if isinstance(result.get("items"), list):
        return [row for row in result["items"] if isinstance(row, dict)]
    return []


def _key_fields(rows: list[dict[str, Any]]) -> list[str]:
    fields: list[str] = []
    for row in rows[:10]:
        for key in row.keys():
            lowered = str(key).lower()
            if any(token in lowered for token in ["id", "name", "status", "state", "count", "time", "date", "timestamp"]):
                if key not in fields:
                    fields.append(str(key))
    return fields


def _has_evidence(evidence: dict[str, Any]) -> bool:
    if not isinstance(evidence, dict):
        return False
    for value in evidence.values():
        if isinstance(value, list) and value:
            return True
        if isinstance(value, dict) and value:
            return True
        if value not in (None, "", [], {}):
            return True
    return False


def _best_overall_strategy(strict: dict[str, Any]) -> str | None:
    return ((strict.get("summary") or {}).get("best_overall") or None)


def _strict_score(system: dict[str, Any], strict: dict[str, Any]) -> float | None:
    value = system.get("packaged_strict_score")
    if isinstance(value, (int, float)):
        return round(float(value), 4)
    by_strategy = ((strict.get("summary") or {}).get("by_strategy") or {})
    sql_first = by_strategy.get("SQL_FIRST_API_VERIFY") or {}
    score = sql_first.get("avg_final_score")
    return round(float(score), 4) if isinstance(score, (int, float)) else None


def _llm_score_from_sources(sources: dict[str, Any]) -> float | None:
    llm = sources.get("llm_strict_baseline_eval") or {}
    for path in [("summary", "best_llm_score"), ("summary", "best_final_score")]:
        value = llm
        for key in path:
            value = value.get(key) if isinstance(value, dict) else None
        if isinstance(value, (int, float)):
            return round(float(value), 4)
    return None


def _safe_int(value: Any) -> int | None:
    return int(value) if isinstance(value, (int, float)) else None


def _shorten(text: str, limit: int) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: max(0, limit - 3)].rstrip() + "..."


def _load_json(path: Path) -> Any:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_safe(payload), indent=2, sort_keys=True, default=str), encoding="utf-8")


def _safe(payload: Any) -> Any:
    return redact_secrets(payload)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _render_preflight(payload: dict[str, Any]) -> str:
    lines = [
        "# SDK Tool Calling Optimization Preflight",
        "",
        f"- Packaged strategy: `{payload.get('packaged_strategy')}`",
        f"- Strict score: `{payload.get('strict_score')}`",
        f"- Best LLM baseline score: `{payload.get('llm_baseline_score')}`",
        f"- Backend/provider: `{payload.get('current_backend_provider')}` / `{payload.get('backend_type')}`",
        f"- SDK direct HTTP hits: `{payload.get('sdk_direct_http_hits')}`",
        f"- Tool calling supported: `{payload.get('tool_calling_supported')}`",
        f"- Runtime change allowed: `{payload.get('runtime_change_allowed')}`",
        f"- Blocker: `{payload.get('blocker')}`",
        "",
        "Protected artifacts remain outside this diagnostic pass.",
    ]
    return "\n".join(lines) + "\n"


def _render_surface(payload: dict[str, Any]) -> str:
    lines = [
        "# SDK Tool-Call Surface Audit",
        "",
        f"- Diagnostic only: `{payload.get('diagnostic_only')}`",
        f"- Direct HTTP hits: `{payload.get('summary', {}).get('direct_http_hits')}`",
        f"- Recommendation: `{payload.get('summary', {}).get('recommendation')}`",
        "",
        "| Issue | Area | Classification | Finding |",
        "| --- | --- | --- | --- |",
    ]
    for issue in payload.get("issues", []):
        lines.append(f"| `{issue.get('issue_id')}` | `{issue.get('area')}` | `{issue.get('classification')}` | {issue.get('finding')} |")
    return "\n".join(lines) + "\n"


def _render_decision_analysis(payload: dict[str, Any]) -> str:
    lines = [
        "# SDK Tool-Call Decision Analysis",
        "",
        f"- Official rows analyzed: `{payload.get('official_rows_analyzed')}`",
        f"- Generated prompts analyzed: `{payload.get('generated_prompts_analyzed')}`",
        f"- Generated prompts diagnostic-only: `{payload.get('generated_prompts_diagnostic_only')}`",
        "",
        "| Source | ID | Classification | Tool needed? | API hidden? | Rewrite skipped? |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in payload.get("rows", [])[:40]:
        row_id = row.get("row_id") or row.get("prompt_id")
        lines.append(
            f"| `{row.get('row_source')}` | `{row_id}` | `{row.get('classification')}` | "
            f"{row.get('tool_call_was_necessary')} | {row.get('api_tool_should_be_hidden')} | {row.get('answer_rewrite_should_be_skipped')} |"
        )
    return "\n".join(lines) + "\n"


def _render_variants(payload: dict[str, Any]) -> str:
    lines = [
        "# SDK Tool-Call Optimization Variants",
        "",
        "All variants are isolated and trial-only; no packaged runtime behavior changes are made by this audit.",
        "",
        "| Variant | Expected impact | Risk | Affected signals | Promotion status |",
        "| --- | --- | --- | ---: | --- |",
    ]
    for variant in payload.get("variants", []):
        lines.append(
            f"| `{variant.get('variant_id')}` | {variant.get('expected_impact')} | `{variant.get('risk')}` | "
            f"{variant.get('affected_rows_or_signals')} | `{variant.get('promotion_status')}` |"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
