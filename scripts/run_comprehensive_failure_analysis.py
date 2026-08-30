#!/usr/bin/env python
from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.trajectory import redact_secrets


REPORT_STEMS = [
    "comprehensive_failure_analysis_preflight",
    "official_row_failure_table",
    "generated_prompt_failure_table",
    "cross_dataset_failure_clusters",
    "general_deterministic_rule_candidates",
    "cross_dataset_counterfactual_answer_sketches",
    "general_rule_hardcoding_risk_audit",
    "comprehensive_failure_fix_decision",
]

PROTECTED_PATHS = [
    "outputs/final_submission/",
    "outputs/eval_results_strict.json",
    "outputs/hidden_style_eval.",
    "outputs/final_submission_manifest.json",
    "final_submission_manifest.json",
    "dashagent/endpoint_catalog.py",
    "dashagent/config.py",
]

GENERATED_ISSUE_TYPES = {
    "generated_label_noise",
    "live_api_required",
    "synonym_gap",
    "router_gap",
    "domain_detection_gap",
    "answer_intent_gap",
    "SQL_template_gap",
    "answer_template_gap",
    "zero_row_clarity_gap",
    "dry_run_wording_gap",
    "no_issue",
    "unclear",
}


def main() -> int:
    config = Config.from_env(ROOT)
    payload = run_comprehensive_failure_analysis(config)
    decision = payload.get("comprehensive_failure_fix_decision", {})
    print(
        json.dumps(
            {
                "decision": decision.get("decision"),
                "official_rows_analyzed": decision.get("total_official_rows_analyzed"),
                "generated_prompts_analyzed": decision.get("total_generated_prompts_analyzed"),
                "runtime_change_applied": decision.get("runtime_change_applied"),
                "report": str(config.outputs_dir / "reports" / "comprehensive_failure_fix_decision.json"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def run_comprehensive_failure_analysis(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    sources = _load_sources(config)
    preflight = _build_preflight(config, sources)
    _write_json_md(
        reports_dir,
        "comprehensive_failure_analysis_preflight",
        preflight,
        _render_preflight(preflight),
    )

    if preflight.get("blocker_required"):
        blocker = {
            "report_type": "comprehensive_failure_analysis_blocker",
            "created_at": _now(),
            "reason": "protected_or_runtime_source_changes_detected",
            "protected_changes": preflight.get("protected_changes", []),
            "runtime_source_changes": preflight.get("runtime_source_changes", []),
            "runtime_change_applied": False,
        }
        _write_json_md(reports_dir, "comprehensive_failure_analysis_blocker", blocker, _render_blocker(blocker))
        return {"preflight": preflight, "blocker": blocker}

    official = _build_official_row_failure_table(config, sources)
    generated = _build_generated_prompt_failure_table(config, sources)
    clusters = _build_cross_dataset_clusters(official, generated)
    candidates = _build_rule_candidates(clusters, sources)
    sketches = _build_counterfactual_sketches(official, generated, candidates)
    hardcoding = _build_hardcoding_risk_audit(candidates)
    decision = _build_fix_decision(official, generated, clusters, candidates, hardcoding, sources)

    outputs = {
        "official_row_failure_table": official,
        "generated_prompt_failure_table": generated,
        "cross_dataset_failure_clusters": clusters,
        "general_deterministic_rule_candidates": candidates,
        "cross_dataset_counterfactual_answer_sketches": sketches,
        "general_rule_hardcoding_risk_audit": hardcoding,
        "comprehensive_failure_fix_decision": decision,
    }
    renderers = {
        "official_row_failure_table": _render_official_rows,
        "generated_prompt_failure_table": _render_generated_rows,
        "cross_dataset_failure_clusters": _render_clusters,
        "general_deterministic_rule_candidates": _render_candidates,
        "cross_dataset_counterfactual_answer_sketches": _render_sketches,
        "general_rule_hardcoding_risk_audit": _render_hardcoding,
        "comprehensive_failure_fix_decision": _render_decision,
    }
    for stem, payload in outputs.items():
        _write_json_md(reports_dir, stem, payload, renderers[stem](payload))

    return {"preflight": preflight, **outputs}


def _load_sources(config: Config) -> dict[str, Any]:
    reports = config.outputs_dir / "reports"
    return {
        "strict": _load_json(config.outputs_dir / "eval_results_strict.json"),
        "workflow_decision_audit": _load_json(reports / "workflow_decision_audit.json"),
        "accuracy": _load_json(reports / "accuracy_and_bottleneck_summary.json"),
        "evidence_usage": _load_json(reports / "evidence_usage_audit.json"),
        "sql_evidence_usage": _load_json(reports / "sql_evidence_usage_audit.json"),
        "score_path_audit": _load_json(reports / "score_path_contribution_audit.json"),
        "score_trials": _load_json(reports / "score_focused_core_improvement_trials.json"),
        "score_fix_decision": _load_json(reports / "score_focused_core_fix_decision.json"),
        "generated_suite": _load_json_or_list(config.data_dir / "generated_prompt_suite.json"),
        "generated_local": _load_json(reports / "generated_prompt_suite_local_diagnostic.json"),
        "generated_gap_samples": _load_json(reports / "generated_prompt_local_gap_samples.json"),
        "local_candidates": _load_json(reports / "local_deterministic_improvement_candidates.json"),
        "local_gap_manual_review": _load_json(reports / "local_gap_manual_review.json"),
        "system_summary": _load_json(reports / "system_summary.json"),
        "report_index": _load_json(reports / "report_index.json"),
        "adobe_waiting": _load_json(reports / "adobe_access_waiting_status.json"),
        "live_blocker": _load_json(reports / "live_api_full_run_blocker.json"),
    }


def _build_preflight(config: Config, sources: dict[str, Any]) -> dict[str, Any]:
    git = _git_status(config.project_root)
    strict_rows = _sql_first_rows(sources.get("strict", {}))
    generated_rows = _generated_rows(sources)
    protected_changes = _protected_changes(git.get("short_lines", []))
    runtime_source_changes = _runtime_source_changes(git.get("short_lines", []))
    packaged = _packaged_strategy(sources)
    payload = {
        "report_type": "comprehensive_failure_analysis_preflight",
        "created_at": _now(),
        "git_status_summary": git,
        "packaged_strategy": packaged,
        "strict_score": _strict_score(sources),
        "hidden_style": _hidden_style(sources),
        "final_submission_ready": _final_submission_ready(sources),
        "live_success_count": _live_success_count(sources),
        "official_row_count": len(strict_rows),
        "generated_prompt_count": len(generated_rows),
        "generated_prompts_diagnostic_only": _generated_is_diagnostic_only(sources),
        "runtime_change_allowed": False,
        "protected_paths": PROTECTED_PATHS,
        "protected_changes": protected_changes,
        "runtime_source_changes": runtime_source_changes,
        "no_hardcoding_rule": True,
        "generated_prompt_usage": "generality_and_coverage_only",
        "official_rows_usage": "real_score_loss_diagnosis",
        "blocker_required": bool(protected_changes or runtime_source_changes),
    }
    return _redact_payload(payload)


def _build_official_row_failure_table(config: Config, sources: dict[str, Any]) -> dict[str, Any]:
    evidence_by_query = {
        row.get("query_id"): row
        for row in (sources.get("evidence_usage", {}).get("rows") or [])
        if isinstance(row, dict)
    }
    sql_audit_by_query = {
        row.get("query_id"): row
        for row in (sources.get("sql_evidence_usage", {}).get("rows") or [])
        if isinstance(row, dict)
    }
    rows = []
    for row in _sql_first_rows(sources.get("strict", {})):
        trajectory = _load_trajectory(config, row)
        metadata = _load_metadata(row)
        evidence_row = evidence_by_query.get(row.get("query_id"), {})
        sql_audit_row = sql_audit_by_query.get(row.get("query_id"), {})
        execution = _execution_summary(trajectory, row)
        failure_flags = _official_failure_flags(row, trajectory, execution, evidence_row, sql_audit_row)
        primary = _primary_official_cause(failure_flags, row)
        secondary = [key for key, value in failure_flags.items() if value and key != primary]
        requires_live = bool(failure_flags["live_api_blocked"] or failure_flags["api_required_but_dry_run"])
        locally_fixable = bool(
            not requires_live
            and (
                failure_flags["answer_missing_count"]
                or failure_flags["answer_missing_name_or_id"]
                or failure_flags["answer_missing_status"]
                or failure_flags["answer_missing_timestamp"]
                or failure_flags["zero_row_answer_unclear"]
                or failure_flags["sql_correct_but_answer_weak"]
            )
        )
        if requires_live and (
            failure_flags["answer_missing_count"]
            or failure_flags["answer_missing_name_or_id"]
            or failure_flags["zero_row_answer_unclear"]
            or failure_flags["dry_run_caveat_dominates_sql_answer"]
        ):
            locally_fixable = True
        general_rule = bool(
            failure_flags["answer_missing_count"]
            or failure_flags["answer_missing_name_or_id"]
            or failure_flags["answer_missing_status"]
            or failure_flags["answer_missing_timestamp"]
            or failure_flags["zero_row_answer_unclear"]
            or failure_flags["dry_run_caveat_dominates_sql_answer"]
        )
        strict_score = _num(row.get("final_score"))
        rows.append(
            _redact_payload(
                {
                    "row_id": row.get("query_id"),
                    "example_id": row.get("query_id"),
                    "prompt": row.get("query"),
                    "predicted_route": trajectory.get("route_type") or metadata.get("route_type") or _checkpoint_value(trajectory, "mode"),
                    "predicted_domain": trajectory.get("domain_type") or metadata.get("domain_type") or _checkpoint_value(trajectory, "domain_type"),
                    "answer_intent": trajectory.get("answer_intent") or metadata.get("answer_intent") or _checkpoint_value(trajectory, "answer_intent"),
                    "strategy": row.get("strategy"),
                    "bottleneck_label": primary,
                    "total_strict_score": strict_score,
                    "answer_score": _num(row.get("answer_score")),
                    "sql_score": _num(row.get("sql_score")),
                    "api_score": _num(row.get("api_score")),
                    "trajectory_tool_score": _num(row.get("trajectory_score") or row.get("tool_score")),
                    "format_compliance_score": _num(row.get("format_score") or row.get("compliance_score")),
                    "below_0_70": strict_score is not None and strict_score < 0.70,
                    "below_0_75": strict_score is not None and strict_score < 0.75,
                    "delta_to_0_70": _delta_to(strict_score, 0.70),
                    "delta_to_0_75": _delta_to(strict_score, 0.75),
                    "sql_calls": execution["sql_call_count"],
                    "sql_returned_row_count": execution["sql_row_count"],
                    "sql_evidence_fields": execution["sql_evidence_fields"],
                    "api_calls": execution["api_call_count"],
                    "api_state": execution["api_state"],
                    "evidencebus_items": execution["evidencebus_items"],
                    "answer_slots": execution["answer_slots"],
                    "final_answer": execution["final_answer"],
                    "verifier_notes": _verifier_notes(trajectory, row),
                    "failure_classification": failure_flags,
                    "likely_primary_cause": primary,
                    "secondary_causes": secondary,
                    "evidence_supporting_cause": _supporting_evidence(primary, execution, row),
                    "locally_fixable_now": locally_fixable,
                    "requires_live_api": requires_live,
                    "general_rule_possible": general_rule,
                    "hardcoding_risk": "low" if general_rule else "medium",
                    "confidence": _confidence(primary, row, execution),
                }
            )
        )
    summary = {
        "total_rows": len(rows),
        "below_0_70": sum(1 for row in rows if row["below_0_70"]),
        "below_0_75": sum(1 for row in rows if row["below_0_75"]),
        "requires_live_api_rows": sum(1 for row in rows if row["requires_live_api"]),
        "locally_fixable_now_rows": sum(1 for row in rows if row["locally_fixable_now"]),
        "primary_cause_distribution": dict(Counter(row["likely_primary_cause"] for row in rows)),
    }
    return {
        "report_type": "official_row_failure_table",
        "generated_at": _now(),
        "diagnostic_only": True,
        "official_score_claim": False,
        "runtime_change_applied": False,
        "source": "outputs/eval_results_strict.json",
        "strategy": "SQL_FIRST_API_VERIFY",
        "summary": summary,
        "rows": rows,
    }


def _build_generated_prompt_failure_table(config: Config, sources: dict[str, Any]) -> dict[str, Any]:
    suite_by_id = {
        item.get("prompt_id"): item
        for item in (sources.get("generated_suite") if isinstance(sources.get("generated_suite"), list) else [])
        if isinstance(item, dict)
    }
    rows = []
    for row in _generated_rows(sources):
        prompt_id = row.get("prompt_id")
        suite = suite_by_id.get(prompt_id, {})
        issue = _generated_issue_type(row)
        rows.append(
            _redact_payload(
                {
                    "prompt_id": prompt_id,
                    "prompt": row.get("prompt") or suite.get("prompt"),
                    "generation_type": row.get("generation_type") or suite.get("generation_type"),
                    "expected_label": row.get("expected_route_label") or suite.get("expected_route_diagnostic"),
                    "expected_domain": suite.get("domain_family") or row.get("domain_family"),
                    "expected_intent": suite.get("expected_answer_intent_diagnostic") or row.get("answer_intent"),
                    "actual_route": row.get("actual_route"),
                    "actual_domain": row.get("domain_type"),
                    "actual_answer_intent": row.get("actual_answer_intent"),
                    "answer_family": row.get("answer_family"),
                    "strategy": row.get("strategy", "SQL_FIRST_API_VERIFY"),
                    "sql_calls": row.get("sql_calls", 0),
                    "sql_row_count": _generated_sql_row_count(config, row),
                    "sql_result_shape": _generated_sql_shape(config, row),
                    "dry_run_api_calls": row.get("dry_run_api_calls", row.get("dry_run_count", 0)),
                    "api_state": row.get("evidence_state"),
                    "final_answer": row.get("final_answer"),
                    "validation_failures": row.get("validation_failures", 0),
                    "runtime_errors": 1 if row.get("status") == "failed" else 0,
                    "zero_row_sql": bool(row.get("zero_row_sql")),
                    "requires_live_api": _generated_requires_live_api(row),
                    "raw_requires_live_api_flag": bool(row.get("requires_live_api")),
                    "missing_count_or_name_advisory": bool(row.get("missing_count_or_name_advisory")),
                    "answer_too_vague_heuristic": bool(row.get("answer_too_vague_advisory") or row.get("vague_or_evidence_unused")),
                    "route_mismatch": not bool(row.get("route_matches_diagnostic", True)),
                    "domain_mismatch": not bool(row.get("domain_matches_diagnostic", True)),
                    "answer_intent_mismatch": not bool(row.get("answer_intent_matches_diagnostic", True)),
                    "likely_issue_type": issue,
                    "evidence_supporting_classification": _generated_evidence(row, issue),
                    "supports_general_rule": issue in {"answer_template_gap", "zero_row_clarity_gap", "dry_run_wording_gap", "answer_intent_gap"},
                    "only_live_api_limitation": issue == "live_api_required",
                    "hardcoding_risk": "high" if issue in {"generated_label_noise", "unclear"} else "medium",
                    "confidence": _generated_confidence(row, issue),
                    "diagnostic_only": True,
                    "generated_labels_are_advisory_only": True,
                    "official_score_claim": False,
                    "hardcoding_warning": "prompt text is diagnostic-only and must never become an exact runtime trigger",
                }
            )
        )
    summary = {
        "total_prompts": len(rows),
        "runtime_failures": sum(1 for row in rows if row["runtime_errors"]),
        "validation_failures": sum(int(row["validation_failures"] or 0) for row in rows),
        "requires_live_api_prompts": sum(1 for row in rows if row["requires_live_api"]),
        "issue_distribution": dict(Counter(row["likely_issue_type"] for row in rows)),
        "generated_prompts_diagnostic_only": True,
    }
    return {
        "report_type": "generated_prompt_failure_table",
        "generated_at": _now(),
        "diagnostic_only": True,
        "official_score_claim": False,
        "promotion_allowed": False,
        "generated_labels_are_ground_truth": False,
        "source": "outputs/reports/generated_prompt_suite_local_diagnostic.json",
        "summary": summary,
        "rows": rows,
    }


def _build_cross_dataset_clusters(official: dict[str, Any], generated: dict[str, Any]) -> dict[str, Any]:
    official_rows = official.get("rows", [])
    generated_rows = generated.get("rows", [])

    definitions = [
        {
            "cluster_id": "live_api_blocked",
            "cluster_name": "Live API blocked / requires live Adobe access",
            "official_predicate": lambda row: row.get("requires_live_api"),
            "generated_predicate": lambda row: row.get("requires_live_api"),
            "root_cause": "Adobe sandbox or product permission access prevents usable live API payload evidence.",
            "fix_now": False,
            "requires_adobe": True,
            "action": "wait_for_adobe_access",
        },
        {
            "cluster_id": "sql_evidence_answer_omission",
            "cluster_name": "SQL evidence exists but answer omits count/name/status/timestamp",
            "official_predicate": lambda row: any(
                row.get("failure_classification", {}).get(flag)
                for flag in [
                    "answer_missing_count",
                    "answer_missing_name_or_id",
                    "answer_missing_status",
                    "answer_missing_timestamp",
                    "sql_correct_but_answer_weak",
                ]
            ),
            "generated_predicate": lambda row: row.get("likely_issue_type") == "answer_template_gap",
            "root_cause": "Answer wording may fail to surface already-executed SQL facts.",
            "fix_now": True,
            "requires_adobe": False,
            "action": "keep_analysis_only",
        },
        {
            "cluster_id": "zero_row_local_sql_unclear",
            "cluster_name": "Zero-row local SQL answer unclear",
            "official_predicate": lambda row: row.get("failure_classification", {}).get("zero_row_answer_unclear"),
            "generated_predicate": lambda row: row.get("likely_issue_type") == "zero_row_clarity_gap",
            "root_cause": "Zero local rows can be phrased like a global absence instead of an available-local-evidence result.",
            "fix_now": True,
            "requires_adobe": False,
            "action": "keep_analysis_only",
        },
        {
            "cluster_id": "dry_run_caveat_dominates_sql_answer",
            "cluster_name": "Dry-run API caveat dominates SQL-supported answer",
            "official_predicate": lambda row: row.get("failure_classification", {}).get("dry_run_caveat_dominates_sql_answer"),
            "generated_predicate": lambda row: row.get("likely_issue_type") == "dry_run_wording_gap",
            "root_cause": "API caveats can obscure the SQL-supported portion of the answer.",
            "fix_now": True,
            "requires_adobe": False,
            "action": "keep_analysis_only",
        },
        {
            "cluster_id": "route_domain_synonym_mismatch",
            "cluster_name": "Route/domain mismatch caused by possible synonyms",
            "official_predicate": lambda row: row.get("failure_classification", {}).get("route_domain_wrong"),
            "generated_predicate": lambda row: row.get("likely_issue_type") in {"synonym_gap", "router_gap", "domain_detection_gap"},
            "root_cause": "Some prompt shapes may use wording not covered by deterministic routing.",
            "fix_now": False,
            "requires_adobe": False,
            "action": "manual_review_before_router_change",
        },
        {
            "cluster_id": "answer_intent_mismatch",
            "cluster_name": "Answer intent mismatch for count/list/status/date prompts",
            "official_predicate": lambda row: row.get("failure_classification", {}).get("intent_wrong"),
            "generated_predicate": lambda row: row.get("likely_issue_type") == "answer_intent_gap",
            "root_cause": "Generated intent labels and runtime intent can diverge; generated labels are not ground truth.",
            "fix_now": False,
            "requires_adobe": False,
            "action": "manual_review_generated_label_noise",
        },
        {
            "cluster_id": "generated_label_noise",
            "cluster_name": "Generated label noise",
            "official_predicate": lambda row: False,
            "generated_predicate": lambda row: row.get("likely_issue_type") == "generated_label_noise",
            "root_cause": "Diagnostic expected labels disagree with reasonable runtime behavior.",
            "fix_now": False,
            "requires_adobe": False,
            "action": "no_code_change",
        },
        {
            "cluster_id": "unsupported_claim_risk",
            "cluster_name": "Unsupported claim risk",
            "official_predicate": lambda row: row.get("failure_classification", {}).get("unsupported_claim"),
            "generated_predicate": lambda row: "unsupported" in str(row.get("final_answer", "")).lower(),
            "root_cause": "Answers must not infer unavailable live state or fabricate missing payload values.",
            "fix_now": True,
            "requires_adobe": False,
            "action": "guard_in_future_trial_only",
        },
        {
            "cluster_id": "evaluator_sensitive_wording",
            "cluster_name": "Evaluator-sensitive wording",
            "official_predicate": lambda row: row.get("failure_classification", {}).get("evaluator_sensitive_wording"),
            "generated_predicate": lambda row: False,
            "root_cause": "Small wording changes can hurt strict answer similarity, as prior broad rewrite trials showed.",
            "fix_now": False,
            "requires_adobe": False,
            "action": "avoid_broad_rewrite",
        },
        {
            "cluster_id": "no_local_fix_before_adobe_access",
            "cluster_name": "No clear local fix before Adobe access",
            "official_predicate": lambda row: row.get("likely_primary_cause") == "no_clear_local_fix",
            "generated_predicate": lambda row: row.get("likely_issue_type") in {"live_api_required", "unclear"},
            "root_cause": "Evidence is insufficient for a safe local deterministic change.",
            "fix_now": False,
            "requires_adobe": True,
            "action": "wait_or_keep_analysis_only",
        },
    ]
    clusters = []
    for definition in definitions:
        official_hits = [row for row in official_rows if definition["official_predicate"](row)]
        generated_hits = [row for row in generated_rows if definition["generated_predicate"](row)]
        official_scores = [row.get("total_strict_score") for row in official_hits if isinstance(row.get("total_strict_score"), (int, float))]
        clusters.append(
            {
                "cluster_id": definition["cluster_id"],
                "cluster_name": definition["cluster_name"],
                "official_rows_affected": [row.get("row_id") for row in official_hits],
                "generated_prompts_affected": [row.get("prompt_id") for row in generated_hits],
                "official_count": len(official_hits),
                "generated_count": len(generated_hits),
                "average_official_strict_score": round(mean(official_scores), 4) if official_scores else None,
                "common_trigger_signals": _common_trigger_signals(definition["cluster_id"]),
                "common_evidence_signals": _common_evidence_signals(definition["cluster_id"]),
                "root_cause": definition["root_cause"],
                "local_deterministic_fix_possible_now": definition["fix_now"],
                "requires_adobe_access": definition["requires_adobe"],
                "regression_risk": _cluster_risk(definition["cluster_id"]),
                "generalness_confidence": _cluster_confidence(official_hits, generated_hits),
                "recommended_action": definition["action"],
            }
        )
    return {
        "report_type": "cross_dataset_failure_clusters",
        "generated_at": _now(),
        "diagnostic_only": True,
        "official_score_claim": False,
        "generated_prompt_usage": "generality_and_coverage_only",
        "clusters": clusters,
    }


def _build_rule_candidates(clusters: dict[str, Any], sources: dict[str, Any]) -> dict[str, Any]:
    cluster_by_id = {cluster["cluster_id"]: cluster for cluster in clusters.get("clusters", [])}
    trial_summary = (sources.get("score_trials", {}).get("summary") or {})
    best_delta = trial_summary.get("best_strict_score_delta")
    trial_recommendation = trial_summary.get("recommendation") or sources.get("score_fix_decision", {}).get("recommendation")

    templates = [
        {
            "candidate_id": "rule_sql_required_values_in_answer",
            "rule_name": "Surface required SQL count/name/status/timestamp facts in final answers",
            "cluster_id": "sql_evidence_answer_omission",
            "triggering_conditions": [
                "query intent asks for count/list/status/date",
                "SQL result shape exposes the requested value fields",
                "answer slot type expects the same value family",
            ],
            "required_evidence_signals": ["SQL result fields", "answer intent", "EvidenceBus or answer-slot value family"],
            "proposed_behavior": "Prefer concise SQL-supported facts before any API caveat, without inventing missing values.",
            "tests_needed": [
                "count field appears for count intent",
                "names or IDs appear for list intent",
                "status and timestamp fields are not fabricated",
            ],
        },
        {
            "candidate_id": "rule_zero_row_local_evidence_wording",
            "rule_name": "Use local-evidence-specific zero-row wording",
            "cluster_id": "zero_row_local_sql_unclear",
            "triggering_conditions": [
                "SQL executed successfully",
                "SQL row count is zero",
                "no live API payload contradicts the local empty result",
            ],
            "required_evidence_signals": ["SQL ok=true", "SQL row_count=0", "API state separated from SQL result"],
            "proposed_behavior": "Say no matching local records were found in available local evidence instead of claiming global absence.",
            "tests_needed": [
                "zero-row answer does not say global no data",
                "API unavailable caveat remains separate",
            ],
        },
        {
            "candidate_id": "rule_sql_answer_before_dry_run_caveat",
            "rule_name": "Place SQL-supported answer before dry-run API caveat",
            "cluster_id": "dry_run_caveat_dominates_sql_answer",
            "triggering_conditions": [
                "SQL evidence contains a partial or complete answer",
                "API state is dry_run_unavailable or api_error",
                "query route is SQL_THEN_API or SQL_PLUS_API",
            ],
            "required_evidence_signals": ["SQL result summary", "API evidence state", "route/domain class"],
            "proposed_behavior": "Answer the SQL-supported part first, then append a short API caveat.",
            "tests_needed": [
                "SQL-supported answer precedes caveat",
                "caveat does not erase SQL evidence",
            ],
        },
        {
            "candidate_id": "rule_wait_for_live_api_payload",
            "rule_name": "Wait for live Adobe API access for API-required losses",
            "cluster_id": "live_api_blocked",
            "triggering_conditions": [
                "route or endpoint family requires live API payload",
                "safe GET smoke has live_success_count=0",
                "API evidence state is dry-run or external blocker",
            ],
            "required_evidence_signals": ["API_REQUIRED or SQL_PLUS_API route", "live_success guard", "endpoint outcome classifier"],
            "proposed_behavior": "Do not optimize away API-required behavior; rerun post-permission verification after access is granted.",
            "tests_needed": ["live guard stays blocked with zero live_success", "API-required answers do not fabricate live data"],
        },
        {
            "candidate_id": "rule_router_synonym_candidate_review",
            "rule_name": "Review router/domain synonyms only with official plus generated evidence",
            "cluster_id": "route_domain_synonym_mismatch",
            "triggering_conditions": [
                "multiple prompts share a domain phrase not covered by deterministic routing",
                "official row evidence shows a real route or domain score loss",
                "generated labels are manually confirmed as behavior gaps",
            ],
            "required_evidence_signals": ["route/domain class", "query token family", "strict row failure cause"],
            "proposed_behavior": "Consider a small synonym rule in a future prompt only after manual confirmation.",
            "tests_needed": ["synonym maps to intended domain", "unrelated domains do not move"],
        },
    ]

    candidates = []
    for template in templates:
        cluster = cluster_by_id.get(template["cluster_id"], {})
        official_ids = cluster.get("official_rows_affected", [])
        generated_ids = cluster.get("generated_prompts_affected", [])
        recommendation = _candidate_recommendation(template["candidate_id"], cluster, best_delta, trial_recommendation)
        implementable_now = bool(
            cluster.get("local_deterministic_fix_possible_now")
            and not cluster.get("requires_adobe_access")
            and recommendation == "implement_next"
        )
        candidates.append(
            {
                **template,
                "official_rows_supported": official_ids,
                "generated_prompts_supported": generated_ids,
                "examples_helped": {
                    "official_rows": official_ids[:5],
                    "generated_prompts": generated_ids[:5],
                },
                "possible_hurt_cases": _possible_hurt_cases(template["candidate_id"]),
                "generated_label_noise_risk": "medium" if generated_ids and not official_ids else "low",
                "hardcoding_risk": "low" if official_ids else "medium",
                "generalness_score": _generalness_score(cluster),
                "robustness_risk": _robustness_risk(template["candidate_id"], best_delta),
                "expected_official_score_impact": _expected_score_impact(template["candidate_id"], official_ids, best_delta),
                "implementable_before_adobe_access": implementable_now,
                "requires_adobe_access": bool(cluster.get("requires_adobe_access")),
                "recommendation": recommendation,
                "reason": _candidate_reason(template["candidate_id"], cluster, best_delta, trial_recommendation),
            }
        )

    return {
        "report_type": "general_deterministic_rule_candidates",
        "generated_at": _now(),
        "diagnostic_only": True,
        "official_score_claim": False,
        "runtime_change_applied": False,
        "selection_rules": [
            "Official strict rows explain real score loss.",
            "Generated prompts provide only generality and coverage evidence.",
            "Rules must use general evidence signals, never IDs or exact prompt text.",
        ],
        "candidates": candidates,
    }


def _build_counterfactual_sketches(
    official: dict[str, Any],
    generated: dict[str, Any],
    candidates: dict[str, Any],
) -> dict[str, Any]:
    candidate_ids = {candidate["candidate_id"] for candidate in candidates.get("candidates", [])}
    official_sketches = []
    for row in official.get("rows", []):
        if not row.get("locally_fixable_now"):
            continue
        rule = _rule_for_primary_cause(row.get("likely_primary_cause"))
        if rule not in candidate_ids:
            continue
        official_sketches.append(
            {
                "row_id": row.get("row_id"),
                "candidate_rule": rule,
                "counterfactual_answer_sketch": _counterfactual_for_official(row),
                "supporting_evidence": row.get("evidence_supporting_cause"),
                "forbidden_unsupported_statements": [
                    "Do not claim live API success.",
                    "Do not claim global absence from a local zero-row result.",
                    "Do not invent missing IDs, names, statuses, or timestamps.",
                ],
                "estimated_likely_effect": "unknown" if row.get("requires_live_api") else "help",
            }
        )
    generated_sketches = []
    for row in generated.get("rows", []):
        if row.get("likely_issue_type") not in {"answer_template_gap", "zero_row_clarity_gap", "dry_run_wording_gap"}:
            continue
        generated_sketches.append(
            {
                "prompt_id": row.get("prompt_id"),
                "diagnostic_only": True,
                "candidate_rule": _rule_for_generated_issue(row.get("likely_issue_type")),
                "short_sketch": _counterfactual_for_generated(row),
                "not_official_score_evidence": True,
            }
        )
        if len(generated_sketches) >= 12:
            break
    return {
        "report_type": "cross_dataset_counterfactual_answer_sketches",
        "generated_at": _now(),
        "diagnostic_only": True,
        "official_score_claim": False,
        "report_only": True,
        "writes_runtime": False,
        "writes_final_submission": False,
        "official_sketches": _redact_payload(official_sketches),
        "generated_prompt_sketches": _redact_payload(generated_sketches),
    }


def _build_hardcoding_risk_audit(candidates: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for candidate in candidates.get("candidates", []):
        trigger_text = json.dumps(candidate.get("triggering_conditions", []), sort_keys=True).lower()
        failed = (
            "query_id" in trigger_text
            or "prompt_id" in trigger_text
            or "exact prompt" in trigger_text
            or "gold answer" in trigger_text
        )
        rows.append(
            {
                "candidate_id": candidate.get("candidate_id"),
                "uses_query_id_trigger": "query_id" in trigger_text,
                "uses_prompt_id_trigger": "prompt_id" in trigger_text,
                "uses_exact_prompt_text_trigger": "exact prompt" in trigger_text,
                "uses_gold_answer_text": "gold answer" in trigger_text,
                "uses_public_dev_specific_constants": False,
                "uses_generated_prompt_specific_constants": False,
                "uses_hidden_eval_assumptions": False,
                "allowed_signal_types": [
                    "query intent signals",
                    "route/domain class",
                    "SQL result shape",
                    "EvidenceBus fields",
                    "API state",
                    "answer slot type",
                    "general field names",
                ],
                "hardcoding_audit_passed": not failed,
                "recommendation": "reject" if failed else candidate.get("recommendation"),
            }
        )
    return {
        "report_type": "general_rule_hardcoding_risk_audit",
        "generated_at": _now(),
        "diagnostic_only": True,
        "official_score_claim": False,
        "candidates": rows,
        "all_candidates_pass_hardcoding_audit": all(row["hardcoding_audit_passed"] for row in rows),
    }


def _build_fix_decision(
    official: dict[str, Any],
    generated: dict[str, Any],
    clusters: dict[str, Any],
    candidates: dict[str, Any],
    hardcoding: dict[str, Any],
    sources: dict[str, Any],
) -> dict[str, Any]:
    official_rows = official.get("rows", [])
    generated_rows = generated.get("rows", [])
    implement_next = [
        candidate for candidate in candidates.get("candidates", [])
        if candidate.get("recommendation") == "implement_next" and candidate.get("implementable_before_adobe_access")
    ]
    live_cluster = next((cluster for cluster in clusters.get("clusters", []) if cluster.get("cluster_id") == "live_api_blocked"), {})
    live_rows = int(live_cluster.get("official_count") or 0)
    local_fixable_rows = sum(1 for row in official_rows if row.get("locally_fixable_now"))
    if len(implement_next) == 1:
        decision = "one_general_rule_ready_for_next_prompt"
    elif len(implement_next) > 1:
        decision = "multiple_candidates_need_manual_choice"
    elif live_rows >= max(1, local_fixable_rows):
        decision = "wait_for_adobe_access"
    else:
        decision = "no_runtime_change"
    strongest = _strongest_candidate(candidates.get("candidates", []))
    next_prompt = (
        f"Implement only `{implement_next[0]['candidate_id']}` with focused tests and strict/hidden validation."
        if len(implement_next) == 1
        else "No implementation prompt is recommended from this analysis pass; keep the findings report-only."
    )
    payload = {
        "report_type": "comprehensive_failure_fix_decision",
        "generated_at": _now(),
        "diagnostic_only": True,
        "official_score_claim": False,
        "runtime_change_applied": False,
        "final_submission_changed": False,
        "decision": decision,
        "total_official_rows_analyzed": len(official_rows),
        "total_generated_prompts_analyzed": len(generated_rows),
        "rows_requiring_adobe_access": sum(1 for row in official_rows if row.get("requires_live_api")),
        "prompts_requiring_live_api": sum(1 for row in generated_rows if row.get("requires_live_api")),
        "locally_fixable_official_rows": local_fixable_rows,
        "generated_prompts_supporting_generality": sum(1 for row in generated_rows if row.get("supports_general_rule")),
        "strongest_candidate_rule": strongest,
        "why_no_hardcoding": "Candidate triggers use intent, route/domain, SQL shape, EvidenceBus/API state, and answer-slot signals, never IDs or exact prompt strings.",
        "ranked_candidates": _rank_candidates(candidates.get("candidates", [])),
        "exact_recommended_next_prompt": next_prompt,
        "previous_score_focused_trial_recommendation": (sources.get("score_trials", {}).get("summary") or {}).get("recommendation"),
        "previous_best_strict_delta": (sources.get("score_trials", {}).get("summary") or {}).get("best_strict_score_delta"),
        "hardcoding_audit_passed": hardcoding.get("all_candidates_pass_hardcoding_audit", False),
    }
    return _redact_payload(payload)


def _sql_first_rows(strict: dict[str, Any]) -> list[dict[str, Any]]:
    rows = strict.get("rows") or []
    if not isinstance(rows, list):
        return []
    selected = [row for row in rows if isinstance(row, dict) and row.get("strategy") == "SQL_FIRST_API_VERIFY"]
    return selected or [row for row in rows if isinstance(row, dict)]


def _generated_rows(sources: dict[str, Any]) -> list[dict[str, Any]]:
    rows = sources.get("generated_local", {}).get("rows") or []
    return rows if isinstance(rows, list) else []


def _load_trajectory(config: Config, row: dict[str, Any]) -> dict[str, Any]:
    candidates = []
    if row.get("output_dir"):
        candidates.append(Path(str(row["output_dir"])) / "trajectory.json")
    if row.get("query_id"):
        candidates.append(config.outputs_dir / "eval" / str(row["query_id"]) / "sql_first_api_verify" / "trajectory.json")
    for path in candidates:
        payload = _load_json(path)
        if payload:
            return payload
    return {}


def _load_metadata(row: dict[str, Any]) -> dict[str, Any]:
    if row.get("output_dir"):
        return _load_json(Path(str(row["output_dir"])) / "metadata.json")
    return {}


def _execution_summary(trajectory: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    steps = trajectory.get("steps") if isinstance(trajectory.get("steps"), list) else []
    sql_steps = [step for step in steps if _is_sql_step(step)]
    api_steps = [step for step in steps if _is_api_step(step)]
    fields: set[str] = set()
    row_count = 0
    sql_values: list[Any] = []
    for step in sql_steps:
        result = step.get("result") if isinstance(step, dict) else {}
        count = _result_row_count(result)
        row_count += count
        for item in _result_items(result):
            if isinstance(item, dict):
                fields.update(str(key) for key in item)
                sql_values.extend(item.values())
    api_states = [_api_state(step.get("result", {})) for step in api_steps if isinstance(step, dict)]
    final_answer = str(trajectory.get("final_answer") or row.get("answer") or "")
    return {
        "sql_call_count": len(sql_steps) or int(row.get("sql_call_count") or row.get("sql_calls") or 0),
        "sql_row_count": row_count,
        "sql_evidence_fields": sorted(fields),
        "sql_values": sql_values[:20],
        "api_call_count": len(api_steps) or int(row.get("api_call_count") or row.get("api_calls") or 0),
        "api_state": _merge_api_states(api_states),
        "evidencebus_items": _extract_named_payload(trajectory, "EvidenceBus") or _extract_named_payload(trajectory, "evidence_bus") or [],
        "answer_slots": trajectory.get("answer_slots") or _extract_named_payload(trajectory, "answer_slots") or {},
        "final_answer": final_answer,
    }


def _official_failure_flags(
    row: dict[str, Any],
    trajectory: dict[str, Any],
    execution: dict[str, Any],
    evidence_row: dict[str, Any],
    sql_audit_row: dict[str, Any],
) -> dict[str, bool]:
    answer = execution["final_answer"]
    answer_l = answer.lower()
    answer_reason = " ".join(str(row.get(key, "")) for key in ["answer_reason", "sql_reason", "api_reason"]).lower()
    fields = {field.lower() for field in execution["sql_evidence_fields"]}
    values = [str(value) for value in execution.get("sql_values", []) if value not in (None, "")]
    api_state = str(execution.get("api_state") or "").lower()
    sql_score = _num(row.get("sql_score"))
    answer_score = _num(row.get("answer_score"))
    api_score = _num(row.get("api_score"))
    count_fields = any("count" in field or "total" in field for field in fields)
    name_fields = any("name" in field or field.endswith("id") or "_id" in field for field in fields)
    status_fields = any("status" in field or "state" in field for field in fields)
    time_fields = any("time" in field or "date" in field or "timestamp" in field for field in fields)
    flags = {
        "live_api_blocked": "dry_run" in api_state or "unavailable" in api_state or bool(evidence_row.get("dry_run_caveat_presence")),
        "api_required_but_dry_run": "dry_run" in api_state or "dry-run" in answer_l or "credentials" in answer_l,
        "answer_missing_count": bool(count_fields and not _answer_contains_any_number(answer) or "missed count" in answer_reason or sql_audit_row.get("answer_missed_count")),
        "answer_missing_name_or_id": bool(name_fields and not _answer_contains_any_value(answer, values) or sql_audit_row.get("answer_missed_names") or sql_audit_row.get("answer_missed_ids")),
        "answer_missing_status": bool(status_fields and sql_audit_row.get("answer_missed_status")),
        "answer_missing_timestamp": bool(time_fields and sql_audit_row.get("answer_missed_timestamp")),
        "answer_too_vague": "vague" in answer_reason or len(answer.split()) < 8,
        "zero_row_answer_unclear": bool(execution["sql_call_count"] and execution["sql_row_count"] == 0 and "local" not in answer_l),
        "sql_wrong_table_or_filter": bool(sql_score is not None and sql_score < 0.8),
        "sql_correct_but_answer_weak": bool((sql_score or 0) >= 0.8 and answer_score is not None and answer_score < 0.5),
        "api_optional_noise": bool(execution["api_call_count"] > 0 and api_score is None and (sql_score or 0) >= 0.8),
        "route_domain_wrong": "route" in answer_reason or "domain" in answer_reason,
        "intent_wrong": "intent" in answer_reason,
        "unsupported_claim": bool(evidence_row.get("primary_issue_category") == "unsupported_claim" or "unsupported" in answer_reason),
        "format_or_trajectory_issue": bool(row.get("error_count") or "format" in answer_reason or "trajectory" in answer_reason),
        "evaluator_sensitive_wording": bool(answer_score is not None and answer_score < 0.5 and not count_fields and not name_fields),
        "dry_run_caveat_dominates_sql_answer": bool(
            execution["sql_call_count"]
            and ("dry_run" in api_state or "unavailable" in api_state)
            and answer_l.find("api") != -1
            and (answer_l.find("sql") == -1 or answer_l.find("api") < answer_l.find("sql"))
        ),
        "no_clear_local_fix": False,
    }
    flags["no_clear_local_fix"] = not any(flags.values())
    return flags


def _primary_official_cause(flags: dict[str, bool], row: dict[str, Any]) -> str:
    order = [
        "live_api_blocked",
        "api_required_but_dry_run",
        "sql_wrong_table_or_filter",
        "answer_missing_count",
        "answer_missing_name_or_id",
        "answer_missing_status",
        "answer_missing_timestamp",
        "zero_row_answer_unclear",
        "dry_run_caveat_dominates_sql_answer",
        "sql_correct_but_answer_weak",
        "answer_too_vague",
        "unsupported_claim",
        "route_domain_wrong",
        "intent_wrong",
        "format_or_trajectory_issue",
        "evaluator_sensitive_wording",
    ]
    for key in order:
        if flags.get(key):
            return key
    return "no_clear_local_fix"


def _generated_issue_type(row: dict[str, Any]) -> str:
    if _generated_requires_live_api(row):
        return "live_api_required"
    if row.get("zero_row_sql") and (row.get("answer_too_vague_advisory") or "no data" in str(row.get("final_answer", "")).lower()):
        return "zero_row_clarity_gap"
    if row.get("missing_count_or_name_advisory"):
        return "answer_template_gap"
    if row.get("answer_too_vague_advisory") or row.get("vague_or_evidence_unused"):
        if "dry_run" in str(row.get("evidence_state", "")).lower():
            return "dry_run_wording_gap"
        return "answer_template_gap"
    if not bool(row.get("route_matches_diagnostic", True)):
        return "router_gap"
    if not bool(row.get("domain_matches_diagnostic", True)):
        return "domain_detection_gap"
    if not bool(row.get("answer_intent_matches_diagnostic", True)):
        expected = str(row.get("answer_intent", "")).upper()
        actual = str(row.get("actual_answer_intent", "")).upper()
        if {expected, actual} <= {"DATE", "WHEN", "TIMESTAMP"}:
            return "generated_label_noise"
        return "answer_intent_gap"
    if row.get("validation_failures") or row.get("status") == "failed":
        return "SQL_template_gap"
    if row.get("failure_category") in GENERATED_ISSUE_TYPES:
        return str(row.get("failure_category"))
    return "no_issue"


def _candidate_recommendation(candidate_id: str, cluster: dict[str, Any], best_delta: Any, trial_recommendation: Any) -> str:
    if candidate_id == "rule_wait_for_live_api_payload":
        return "wait_for_adobe_access"
    if candidate_id == "rule_router_synonym_candidate_review":
        return "keep_analysis_only"
    if trial_recommendation == "keep_trial_only":
        return "keep_analysis_only"
    if isinstance(best_delta, (int, float)) and best_delta > 0 and cluster.get("official_count", 0) > 0:
        return "implement_next"
    return "keep_analysis_only"


def _candidate_reason(candidate_id: str, cluster: dict[str, Any], best_delta: Any, trial_recommendation: Any) -> str:
    if candidate_id == "rule_wait_for_live_api_payload":
        return "Most API-required evidence remains externally blocked; no local rule can fabricate live payloads."
    if trial_recommendation == "keep_trial_only":
        return "Prior isolated score-focused trials did not improve strict score safely, so this remains analysis-only."
    if not cluster.get("official_count"):
        return "Generated-prompt coverage alone is not sufficient for runtime promotion."
    if not cluster.get("generated_count"):
        return "Official evidence exists, but generated coverage is weak; manual review is needed before implementation."
    return "Candidate has cross-dataset evidence but still requires a future implementation prompt and validation."


def _strongest_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not candidates:
        return None
    ranked = _rank_candidates(candidates)
    return ranked[0] if ranked else None


def _rank_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def score(candidate: dict[str, Any]) -> tuple[int, int, int]:
        return (
            1 if candidate.get("recommendation") == "implement_next" else 0,
            len(candidate.get("official_rows_supported") or []),
            len(candidate.get("generated_prompts_supported") or []),
        )

    ranked = sorted(candidates, key=score, reverse=True)
    return [
        {
            "candidate_id": candidate.get("candidate_id"),
            "rule_name": candidate.get("rule_name"),
            "recommendation": candidate.get("recommendation"),
            "official_count": len(candidate.get("official_rows_supported") or []),
            "generated_count": len(candidate.get("generated_prompts_supported") or []),
            "expected_official_score_impact": candidate.get("expected_official_score_impact"),
            "reason": candidate.get("reason"),
        }
        for candidate in ranked
    ]


def _render_preflight(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Comprehensive Failure Analysis Preflight",
            "",
            f"- Packaged strategy: `{payload.get('packaged_strategy')}`",
            f"- Strict score: `{payload.get('strict_score')}`",
            f"- Hidden-style: `{payload.get('hidden_style')}`",
            f"- Final submission ready: `{payload.get('final_submission_ready')}`",
            f"- Live success count: `{payload.get('live_success_count')}`",
            f"- Official rows: `{payload.get('official_row_count')}`",
            f"- Generated prompts: `{payload.get('generated_prompt_count')}`",
            f"- Generated prompts diagnostic-only: `{payload.get('generated_prompts_diagnostic_only')}`",
            f"- Runtime change allowed: `{payload.get('runtime_change_allowed')}`",
            f"- No-hardcoding rule: `{payload.get('no_hardcoding_rule')}`",
            "",
            "Protected paths:",
            *(f"- `{path}`" for path in payload.get("protected_paths", [])),
        ]
    ) + "\n"


def _render_blocker(payload: dict[str, Any]) -> str:
    return "# Comprehensive Failure Analysis Blocker\n\nProtected or runtime source changes were detected; analysis stopped.\n"


def _render_official_rows(payload: dict[str, Any]) -> str:
    lines = ["# Official Row Failure Table", "", "Official strict rows are the score-loss source of truth.", ""]
    summary = payload.get("summary", {})
    lines.append(f"- Total rows: `{summary.get('total_rows')}`")
    lines.append(f"- Requires live API: `{summary.get('requires_live_api_rows')}`")
    lines.append(f"- Locally fixable now: `{summary.get('locally_fixable_now_rows')}`")
    lines.extend(["", "| Row | Score | Primary Cause | Local Fix? | Live API? |", "| --- | ---: | --- | --- | --- |"])
    for row in payload.get("rows", []):
        lines.append(
            f"| `{row.get('row_id')}` | `{row.get('total_strict_score')}` | `{row.get('likely_primary_cause')}` | "
            f"`{row.get('locally_fixable_now')}` | `{row.get('requires_live_api')}` |"
        )
    return "\n".join(lines) + "\n"


def _render_generated_rows(payload: dict[str, Any]) -> str:
    lines = ["# Generated Prompt Failure Table", "", "Generated prompts are diagnostic-only and never official score evidence.", ""]
    summary = payload.get("summary", {})
    lines.append(f"- Total prompts: `{summary.get('total_prompts')}`")
    lines.append(f"- Requires live API: `{summary.get('requires_live_api_prompts')}`")
    lines.append(f"- Issue distribution: `{summary.get('issue_distribution')}`")
    lines.extend(["", "| Prompt | Issue Type | Supports General Rule? |", "| --- | --- | --- |"])
    for row in payload.get("rows", [])[:50]:
        lines.append(f"| `{row.get('prompt_id')}` | `{row.get('likely_issue_type')}` | `{row.get('supports_general_rule')}` |")
    if len(payload.get("rows", [])) > 50:
        lines.append(f"| ... | `{len(payload.get('rows', [])) - 50} more rows omitted from markdown table` | ... |")
    return "\n".join(lines) + "\n"


def _render_clusters(payload: dict[str, Any]) -> str:
    lines = ["# Cross-Dataset Failure Clusters", "", "Clusters combine official score-loss rows with generated prompt generality evidence.", ""]
    lines.extend(["| Cluster | Official | Generated | Action |", "| --- | ---: | ---: | --- |"])
    for cluster in payload.get("clusters", []):
        lines.append(
            f"| `{cluster.get('cluster_id')}` | `{cluster.get('official_count')}` | "
            f"`{cluster.get('generated_count')}` | `{cluster.get('recommended_action')}` |"
        )
    return "\n".join(lines) + "\n"


def _render_candidates(payload: dict[str, Any]) -> str:
    lines = ["# General Deterministic Rule Candidates", "", "Candidate rules are proposals only; no runtime change is made in this pass.", ""]
    lines.extend(["| Candidate | Official | Generated | Recommendation |", "| --- | ---: | ---: | --- |"])
    for candidate in payload.get("candidates", []):
        lines.append(
            f"| `{candidate.get('candidate_id')}` | `{len(candidate.get('official_rows_supported') or [])}` | "
            f"`{len(candidate.get('generated_prompts_supported') or [])}` | `{candidate.get('recommendation')}` |"
        )
    return "\n".join(lines) + "\n"


def _render_sketches(payload: dict[str, Any]) -> str:
    lines = ["# Cross-Dataset Counterfactual Answer Sketches", "", "These sketches are report-only and are not written into runtime or final submission.", ""]
    lines.append(f"- Official sketches: `{len(payload.get('official_sketches', []))}`")
    lines.append(f"- Generated prompt sketches: `{len(payload.get('generated_prompt_sketches', []))}`")
    return "\n".join(lines) + "\n"


def _render_hardcoding(payload: dict[str, Any]) -> str:
    lines = ["# General Rule Hardcoding Risk Audit", "", f"- All candidates pass: `{payload.get('all_candidates_pass_hardcoding_audit')}`", ""]
    lines.extend(["| Candidate | Pass | Recommendation |", "| --- | --- | --- |"])
    for row in payload.get("candidates", []):
        lines.append(f"| `{row.get('candidate_id')}` | `{row.get('hardcoding_audit_passed')}` | `{row.get('recommendation')}` |")
    return "\n".join(lines) + "\n"


def _render_decision(payload: dict[str, Any]) -> str:
    lines = [
        "# Comprehensive Failure Fix Decision",
        "",
        f"- Decision: `{payload.get('decision')}`",
        f"- Runtime change applied: `{payload.get('runtime_change_applied')}`",
        f"- Official rows analyzed: `{payload.get('total_official_rows_analyzed')}`",
        f"- Generated prompts analyzed: `{payload.get('total_generated_prompts_analyzed')}`",
        f"- Rows requiring Adobe access: `{payload.get('rows_requiring_adobe_access')}`",
        f"- Prompts requiring live API: `{payload.get('prompts_requiring_live_api')}`",
        f"- Previous score-focused trial recommendation: `{payload.get('previous_score_focused_trial_recommendation')}`",
        "",
        "## Recommended Next Prompt",
        "",
        payload.get("exact_recommended_next_prompt", ""),
    ]
    return "\n".join(lines) + "\n"


def _write_json_md(reports_dir: Path, stem: str, payload: dict[str, Any], markdown: str) -> None:
    _write_json(reports_dir / f"{stem}.json", payload)
    (reports_dir / f"{stem}.md").write_text(redact_secrets(markdown), encoding="utf-8")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(redact_secrets(json.dumps(payload, indent=2, sort_keys=True)), encoding="utf-8")


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_json_or_list(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _redact_payload(payload: Any) -> Any:
    try:
        return json.loads(redact_secrets(json.dumps(payload)))
    except Exception:
        if isinstance(payload, str):
            return redact_secrets(payload)
        return payload


def _git_status(root: Path) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            ["git", "status", "--short"],
            cwd=root,
            check=False,
            text=True,
            capture_output=True,
            timeout=10,
        )
    except Exception as exc:
        return {"available": False, "error": str(exc), "short_lines": [], "clean": None}
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    return {"available": proc.returncode == 0, "returncode": proc.returncode, "short_lines": lines, "clean": not lines}


def _protected_changes(lines: list[str]) -> list[str]:
    hits = []
    for line in lines:
        path = line[3:] if len(line) > 3 else line
        if any(path.startswith(prefix) or path == prefix for prefix in PROTECTED_PATHS):
            hits.append(line)
    return hits


def _runtime_source_changes(lines: list[str]) -> list[str]:
    hits = []
    for line in lines:
        path = line[3:] if len(line) > 3 else line
        if path.startswith("dashagent/") and path.endswith(".py") and not any(path.startswith(prefix) for prefix in PROTECTED_PATHS):
            hits.append(line)
    return hits


def _packaged_strategy(sources: dict[str, Any]) -> str:
    system = sources.get("system_summary", {})
    return system.get("packaged_strategy") or system.get("preferred_strategy") or "SQL_FIRST_API_VERIFY"


def _strict_score(sources: dict[str, Any]) -> float | None:
    system = sources.get("system_summary", {})
    if isinstance(system.get("strict_final_score"), (int, float)):
        return round(float(system["strict_final_score"]), 4)
    metrics = sources.get("strict", {}).get("summary", {}).get("by_strategy", {}).get("SQL_FIRST_API_VERIFY", {})
    if isinstance(metrics.get("avg_final_score"), (int, float)):
        return round(float(metrics["avg_final_score"]), 4)
    rows = _sql_first_rows(sources.get("strict", {}))
    scores = [_num(row.get("final_score")) for row in rows]
    scores = [score for score in scores if score is not None]
    return round(mean(scores), 4) if scores else None


def _hidden_style(sources: dict[str, Any]) -> str | None:
    hidden = sources.get("system_summary", {}).get("hidden_style")
    if isinstance(hidden, dict):
        return hidden.get("label") or (f"{hidden.get('passed')}/{hidden.get('total')}" if hidden.get("passed") is not None else None)
    return hidden


def _final_submission_ready(sources: dict[str, Any]) -> bool | None:
    value = sources.get("system_summary", {}).get("final_submission_ready")
    return value if isinstance(value, bool) else None


def _live_success_count(sources: dict[str, Any]) -> int:
    for key in ["live_blocker", "adobe_waiting"]:
        payload = sources.get(key, {})
        if isinstance(payload.get("live_success_count"), int):
            return int(payload["live_success_count"])
        guard = payload.get("live_api_guard") if isinstance(payload.get("live_api_guard"), dict) else {}
        if isinstance(guard.get("live_success_count"), int):
            return int(guard["live_success_count"])
    return 0


def _generated_is_diagnostic_only(sources: dict[str, Any]) -> bool:
    generated = sources.get("generated_local", {})
    rows = _generated_rows(sources)
    return bool(generated.get("diagnostic_only", True) and generated.get("official_score_claim", False) is False and all(row.get("diagnostic_only", True) for row in rows))


def _num(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def _delta_to(value: float | None, target: float) -> float | None:
    return round(max(0.0, target - value), 4) if value is not None else None


def _is_sql_step(step: Any) -> bool:
    if not isinstance(step, dict):
        return False
    text = " ".join(str(step.get(key, "")) for key in ["kind", "tool_name", "name", "tool"]).lower()
    return "sql" in text or bool(step.get("sql"))


def _is_api_step(step: Any) -> bool:
    if not isinstance(step, dict):
        return False
    text = " ".join(str(step.get(key, "")) for key in ["kind", "tool_name", "name", "tool"]).lower()
    return "api" in text or bool(step.get("url") or step.get("endpoint"))


def _result_row_count(result: Any) -> int:
    if not isinstance(result, dict):
        return 0
    if isinstance(result.get("row_count"), int):
        return int(result["row_count"])
    items = _result_items(result)
    return len(items)


def _result_items(result: Any) -> list[Any]:
    if not isinstance(result, dict):
        return []
    rows = result.get("rows")
    if isinstance(rows, dict):
        items = rows.get("items")
        return items if isinstance(items, list) else []
    if isinstance(rows, list):
        return rows
    items = result.get("items")
    return items if isinstance(items, list) else []


def _api_state(result: Any) -> str:
    if not isinstance(result, dict):
        return "unknown"
    if result.get("evidence_state"):
        return str(result["evidence_state"])
    if result.get("dry_run"):
        return "dry_run_unavailable"
    if result.get("ok") is False:
        return str(result.get("error_category") or "api_error")
    if result.get("ok") is True:
        return "live_success"
    return "unknown"


def _merge_api_states(states: list[str]) -> str:
    if not states:
        return "none"
    if any("dry_run" in state for state in states):
        return "dry_run_unavailable"
    if any(state in {"api_error", "auth_error", "sandbox_scope_issue", "endpoint_path_issue"} for state in states):
        return "api_error"
    if any(state == "live_success" for state in states):
        return "live_success"
    return states[0]


def _extract_named_payload(payload: Any, name: str) -> Any:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if name.lower() in str(key).lower():
                return value
            found = _extract_named_payload(value, name)
            if found not in (None, [], {}):
                return found
    elif isinstance(payload, list):
        for item in payload:
            found = _extract_named_payload(item, name)
            if found not in (None, [], {}):
                return found
    return None


def _checkpoint_value(trajectory: dict[str, Any], key: str) -> Any:
    for checkpoint in trajectory.get("checkpoints", []) or []:
        output = checkpoint.get("output") if isinstance(checkpoint, dict) else {}
        if isinstance(output, dict) and output.get(key) is not None:
            return output.get(key)
    return None


def _verifier_notes(trajectory: dict[str, Any], row: dict[str, Any]) -> list[str]:
    notes = []
    for checkpoint in trajectory.get("checkpoints", []) or []:
        if "verif" in str(checkpoint.get("checkpoint_id", "")).lower():
            notes.append(str(checkpoint.get("output", ""))[:300])
    for key in ["answer_reason", "sql_reason", "api_reason"]:
        if row.get(key):
            notes.append(str(row[key])[:300])
    return notes


def _answer_contains_any_number(answer: str) -> bool:
    return bool(re.search(r"\b\d+(?:\.\d+)?\b", answer or ""))


def _answer_contains_any_value(answer: str, values: list[str]) -> bool:
    answer_l = (answer or "").lower()
    useful = [value.lower() for value in values if len(value) >= 2 and not value.lower() in {"none", "null", "true", "false"}]
    return any(value in answer_l for value in useful[:10])


def _supporting_evidence(primary: str, execution: dict[str, Any], row: dict[str, Any]) -> list[str]:
    evidence = [
        f"answer_score={row.get('answer_score')}",
        f"sql_score={row.get('sql_score')}",
        f"api_state={execution.get('api_state')}",
    ]
    if execution.get("sql_evidence_fields"):
        evidence.append(f"sql_evidence_fields={execution.get('sql_evidence_fields')}")
    if primary in {"live_api_blocked", "api_required_but_dry_run"}:
        evidence.append("live API evidence was unavailable or dry-run.")
    return evidence


def _confidence(primary: str, row: dict[str, Any], execution: dict[str, Any]) -> str:
    if primary in {"live_api_blocked", "api_required_but_dry_run"} and execution.get("api_state") != "none":
        return "high"
    if primary.startswith("answer_missing") and execution.get("sql_evidence_fields"):
        return "medium"
    if primary == "no_clear_local_fix":
        return "low"
    return "medium"


def _generated_sql_row_count(config: Config, row: dict[str, Any]) -> int | None:
    trajectory = _load_generated_trajectory(config, row)
    counts = [_result_row_count(step.get("result")) for step in trajectory.get("steps", []) or [] if _is_sql_step(step)]
    return sum(counts) if counts else None


def _generated_sql_shape(config: Config, row: dict[str, Any]) -> dict[str, Any]:
    trajectory = _load_generated_trajectory(config, row)
    fields: set[str] = set()
    for step in trajectory.get("steps", []) or []:
        if not _is_sql_step(step):
            continue
        for item in _result_items(step.get("result")):
            if isinstance(item, dict):
                fields.update(item)
    return {"fields": sorted(fields), "zero_row": bool(row.get("zero_row_sql"))}


def _load_generated_trajectory(config: Config, row: dict[str, Any]) -> dict[str, Any]:
    out = row.get("output_dir")
    candidates = []
    if out:
        candidates.append(config.project_root / str(out))
        candidates.append(Path(str(out)))
    if row.get("prompt_id"):
        candidates.append(config.outputs_dir / "generated_prompt_suite_local_diagnostic" / str(row["prompt_id"]))
    for candidate in candidates:
        payload = _load_json(candidate / "trajectory.json")
        if payload:
            return payload
    return {}


def _generated_evidence(row: dict[str, Any], issue: str) -> list[str]:
    evidence = [f"failure_category={row.get('failure_category')}", f"evidence_state={row.get('evidence_state')}"]
    if _generated_requires_live_api(row):
        evidence.append("requires_live_api=true")
    if row.get("missing_count_or_name_advisory"):
        evidence.append("missing_count_or_name_advisory=true")
    if row.get("zero_row_sql"):
        evidence.append("zero_row_sql=true")
    evidence.append(f"classified_as={issue}")
    return evidence


def _generated_requires_live_api(row: dict[str, Any]) -> bool:
    return row.get("failure_category") == "requires_live_api"


def _generated_confidence(row: dict[str, Any], issue: str) -> str:
    if issue in {"live_api_required", "zero_row_clarity_gap"}:
        return "high"
    if issue in {"answer_template_gap", "dry_run_wording_gap"}:
        return "medium"
    if issue in {"generated_label_noise", "unclear"}:
        return "low"
    return "medium"


def _common_trigger_signals(cluster_id: str) -> list[str]:
    mapping = {
        "live_api_blocked": ["API_REQUIRED or SQL_PLUS_API", "dry-run/API unavailable state"],
        "sql_evidence_answer_omission": ["COUNT/LIST/STATUS/DATE intent", "SQL fields present"],
        "zero_row_local_sql_unclear": ["SQL ok", "row_count=0"],
        "dry_run_caveat_dominates_sql_answer": ["SQL result exists", "API dry-run caveat"],
        "route_domain_synonym_mismatch": ["domain synonym wording", "route/domain mismatch"],
        "answer_intent_mismatch": ["intent label mismatch", "count/list/status/date wording"],
    }
    return mapping.get(cluster_id, ["general evidence mismatch"])


def _common_evidence_signals(cluster_id: str) -> list[str]:
    mapping = {
        "live_api_blocked": ["api_state=dry_run_unavailable", "live_success_count=0"],
        "sql_evidence_answer_omission": ["SQL result fields", "answer omits value"],
        "zero_row_local_sql_unclear": ["empty SQL result", "answer lacks local-evidence qualifier"],
        "dry_run_caveat_dominates_sql_answer": ["API caveat appears before SQL-supported fact"],
    }
    return mapping.get(cluster_id, ["strict row metadata", "generated diagnostic flags"])


def _cluster_risk(cluster_id: str) -> str:
    if cluster_id in {"sql_evidence_answer_omission", "zero_row_local_sql_unclear", "dry_run_caveat_dominates_sql_answer"}:
        return "medium"
    if cluster_id == "live_api_blocked":
        return "low"
    return "high"


def _cluster_confidence(official_hits: list[dict[str, Any]], generated_hits: list[dict[str, Any]]) -> str:
    if official_hits and generated_hits:
        return "medium"
    if official_hits:
        return "medium"
    if generated_hits:
        return "low"
    return "low"


def _possible_hurt_cases(candidate_id: str) -> list[str]:
    mapping = {
        "rule_sql_required_values_in_answer": ["answers already close to gold can lose strict wording similarity"],
        "rule_zero_row_local_evidence_wording": ["verbose zero-row wording can hurt concise expected answers"],
        "rule_sql_answer_before_dry_run_caveat": ["reordering caveats changed answer similarity in prior trials"],
        "rule_wait_for_live_api_payload": ["none locally; risk is only delaying speculative local rewrites"],
        "rule_router_synonym_candidate_review": ["over-broad synonym can route unrelated prompts incorrectly"],
    }
    return mapping.get(candidate_id, ["unknown"])


def _generalness_score(cluster: dict[str, Any]) -> int:
    score = 1
    if cluster.get("official_count", 0) > 0:
        score += 2
    if cluster.get("generated_count", 0) >= 3:
        score += 1
    if cluster.get("local_deterministic_fix_possible_now"):
        score += 1
    return min(score, 5)


def _robustness_risk(candidate_id: str, best_delta: Any) -> int:
    if candidate_id == "rule_wait_for_live_api_payload":
        return 1
    if isinstance(best_delta, (int, float)) and best_delta <= 0:
        return 4
    return 3


def _expected_score_impact(candidate_id: str, official_ids: list[str], best_delta: Any) -> str:
    if candidate_id == "rule_wait_for_live_api_payload":
        return "unknown"
    if not official_ids:
        return "unknown"
    if isinstance(best_delta, (int, float)) and best_delta <= 0:
        return "neutral"
    return "likely_positive"


def _rule_for_primary_cause(cause: str) -> str:
    if cause in {"answer_missing_count", "answer_missing_name_or_id", "answer_missing_status", "answer_missing_timestamp", "sql_correct_but_answer_weak"}:
        return "rule_sql_required_values_in_answer"
    if cause == "zero_row_answer_unclear":
        return "rule_zero_row_local_evidence_wording"
    if cause in {"dry_run_caveat_dominates_sql_answer", "api_required_but_dry_run", "live_api_blocked"}:
        return "rule_sql_answer_before_dry_run_caveat"
    return "rule_sql_required_values_in_answer"


def _rule_for_generated_issue(issue: str) -> str:
    return {
        "answer_template_gap": "rule_sql_required_values_in_answer",
        "zero_row_clarity_gap": "rule_zero_row_local_evidence_wording",
        "dry_run_wording_gap": "rule_sql_answer_before_dry_run_caveat",
    }.get(issue, "rule_sql_required_values_in_answer")


def _counterfactual_for_official(row: dict[str, Any]) -> str:
    cause = row.get("likely_primary_cause")
    if cause == "zero_row_answer_unclear":
        return "No matching local records were found in the available local evidence; live API state remains reported separately if unavailable."
    if cause in {"live_api_blocked", "api_required_but_dry_run", "dry_run_caveat_dominates_sql_answer"}:
        return "State the SQL-supported fact first, then add a short live API unavailable caveat without claiming live verification."
    return "State the requested count/name/status/timestamp from SQL evidence directly, without adding unsupported live API claims."


def _counterfactual_for_generated(row: dict[str, Any]) -> str:
    if row.get("likely_issue_type") == "zero_row_clarity_gap":
        return "Use local-evidence-specific zero-row wording."
    if row.get("likely_issue_type") == "dry_run_wording_gap":
        return "Put SQL-supported answer text before the dry-run caveat."
    return "Include SQL-provided values when the prompt asks for them."


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
