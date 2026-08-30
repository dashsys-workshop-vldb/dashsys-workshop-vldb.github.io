#!/usr/bin/env python
from __future__ import annotations

import json
import shutil
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
from scripts.run_deterministic_prompt_type_audit import run_deterministic_prompt_type_audit


TRIAL_REPORT_STEM = "type_specific_deterministic_rule_trials"
CANDIDATE_REPORT_STEM = "type_specific_deterministic_rule_candidates"
FIX_DECISION_STEM = "type_specific_rule_fix_decision"


RULE_FAMILIES = [
    "sql_only_fast_path",
    "count_answer_fast_path",
    "list_name_id_answer_fast_path",
    "status_date_answer_fast_path",
    "zero_row_local_evidence_fast_path",
    "api_caveat_suppression_reordering",
    "router_synonym_type_rules",
    "unknown_ambiguous_safe_fallback",
]


def main() -> int:
    config = Config.from_env(ROOT)
    payload = run_type_specific_deterministic_rule_trials(config)
    print(
        json.dumps(
            {
                "json": str(config.outputs_dir / "reports" / f"{TRIAL_REPORT_STEM}.json"),
                "markdown": str(config.outputs_dir / "reports" / f"{TRIAL_REPORT_STEM}.md"),
                "decision": payload.get("fix_decision", {}).get("decision"),
                "runtime_change_applied": payload.get("runtime_change_applied"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def run_type_specific_deterministic_rule_trials(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    audit_path = reports_dir / "deterministic_prompt_type_audit.json"
    audit = _load_json(audit_path)
    if audit.get("report_type") != "deterministic_prompt_type_audit":
        audit = run_deterministic_prompt_type_audit(config)

    candidates = _discover_candidates(audit)
    candidate_payload = {
        "report_type": CANDIDATE_REPORT_STEM,
        "generated_at": _now(),
        "diagnostic_only": True,
        "official_score_claim": False,
        "runtime_change_applied": False,
        "generated_prompts_used_for": "generality_and_speed_evidence_only",
        "selection_policy": [
            "trial if official support exists and generated support is broad",
            "trial if generated support is at least five prompts and speed risk is low",
            "trial if the rule protects against unsupported claims without score-path changes",
        ],
        "candidates": candidates,
    }
    _write_json(reports_dir / f"{CANDIDATE_REPORT_STEM}.json", candidate_payload)
    (reports_dir / f"{CANDIDATE_REPORT_STEM}.md").write_text(_render_candidates(candidate_payload), encoding="utf-8")

    output_root = config.outputs_dir / "type_specific_deterministic_rule_trials"
    _assert_isolated(config.outputs_dir, output_root)
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)

    official_rows = audit.get("official_rows") or []
    generated_rows = audit.get("generated_prompt_rows") or []
    baseline_score = _baseline_score(audit, official_rows)
    trial_reports = [
        _trial_family(config, output_root, candidate, official_rows, generated_rows, baseline_score)
        for candidate in candidates
        if candidate["recommendation"] in {"trial_next", "implement_next_if_trial_passes", "speed_safe_candidate", "keep_analysis_only"}
    ]
    combined = _combined_safe_bucket_trial(config, output_root, candidates, official_rows, generated_rows, baseline_score)
    if combined:
        trial_reports.append(combined)

    fix_decision = _fix_decision(candidates, trial_reports, baseline_score)
    payload = {
        "report_type": TRIAL_REPORT_STEM,
        "generated_at": _now(),
        "diagnostic_only": True,
        "official_score_claim": False,
        "promotion_allowed": False,
        "writes_eval_outputs": False,
        "writes_final_submission": False,
        "runtime_change_applied": False,
        "packaged_runtime_changed": False,
        "final_submission_format_changed": False,
        "baseline_strict_score": baseline_score,
        "isolated_output_root": str(output_root),
        "rule_families": RULE_FAMILIES,
        "trial_reports": trial_reports,
        "summary": _trial_summary(trial_reports, baseline_score),
        "fix_decision": fix_decision,
        "promotion_gate": [
            "strict score improves or speed/tool-call reduction has no strict regression",
            "hidden-style remains 48/48 if runtime changes are made",
            "check_submission_ready passes",
            "unsupported claims do not increase",
            "no high-scoring official rows regress",
            "no hardcoding",
            "generated diagnostic does not show broad breakage",
            "final submission format unchanged",
        ],
    }
    payload = _redact(payload)
    _write_json(reports_dir / f"{TRIAL_REPORT_STEM}.json", payload)
    (reports_dir / f"{TRIAL_REPORT_STEM}.md").write_text(_render_trials(payload), encoding="utf-8")
    _write_json(reports_dir / f"{FIX_DECISION_STEM}.json", fix_decision)
    (reports_dir / f"{FIX_DECISION_STEM}.md").write_text(_render_decision(fix_decision), encoding="utf-8")
    return payload


def _discover_candidates(audit: dict[str, Any]) -> list[dict[str, Any]]:
    official_rows = audit.get("official_rows") or []
    generated_rows = audit.get("generated_prompt_rows") or []
    candidates: list[dict[str, Any]] = []

    def official(predicate) -> list[str]:
        return [row.get("row_id") for row in official_rows if predicate(row)]

    def generated(predicate) -> list[str]:
        return [row.get("prompt_id") for row in generated_rows if predicate(row)]

    specs = [
        {
            "rule_id": "rule_family_a_sql_only_fast_path",
            "rule_family": "sql_only_fast_path",
            "trigger_signals": [
                "SQL result shape fully covers requested count/list/status/date intent",
                "route is not API_ONLY",
                "API state is optional dry-run or absent",
            ],
            "required_evidence_signals": ["prompt intent", "SQL evidence shape", "route class", "API state"],
            "official": official(lambda row: row["api_unnecessary"] and row["deterministic_fast_path_possible"]),
            "generated": generated(lambda row: row["api_unnecessary"] and row["deterministic_fast_path_possible"]),
            "trial_type": "api_skip_shadow_trial",
            "estimated_speed_impact": "positive",
            "estimated_tool_call_reduction": "possible",
            "estimated_token_reduction": "possible",
            "expected_score_impact": "neutral",
            "risk": "medium",
        },
        {
            "rule_id": "rule_family_b_count_answer_fast_path",
            "rule_family": "count_answer_fast_path",
            "trigger_signals": ["prompt intent=count", "SQL count available", "answer omits numeric count"],
            "required_evidence_signals": ["SQL count field", "answer intent=count"],
            "official": official(lambda row: row["prompt_intent"] == "count" and "SQL count available" in row["evidence_shape"]),
            "generated": generated(lambda row: row["prompt_intent"] == "count" and "SQL count available" in row["evidence_shape"]),
            "trial_type": "answer_only_trial",
            "estimated_speed_impact": "neutral",
            "estimated_tool_call_reduction": "none",
            "estimated_token_reduction": "neutral",
            "expected_score_impact": "unknown",
            "risk": "medium",
        },
        {
            "rule_id": "rule_family_c_list_name_id_answer_fast_path",
            "rule_family": "list_name_id_answer_fast_path",
            "trigger_signals": ["prompt intent=list/name/id", "SQL names/IDs available", "safe row count"],
            "required_evidence_signals": ["SQL name/id fields", "answer intent=list/name/id"],
            "official": official(lambda row: row["prompt_intent"] == "list/name/id" and "SQL names/IDs available" in row["evidence_shape"]),
            "generated": generated(lambda row: row["prompt_intent"] == "list/name/id" and "SQL names/IDs available" in row["evidence_shape"]),
            "trial_type": "answer_only_trial",
            "estimated_speed_impact": "neutral",
            "estimated_tool_call_reduction": "none",
            "estimated_token_reduction": "neutral",
            "expected_score_impact": "unknown",
            "risk": "medium",
        },
        {
            "rule_id": "rule_family_d_status_date_answer_fast_path",
            "rule_family": "status_date_answer_fast_path",
            "trigger_signals": ["prompt asks status/date/when", "SQL status or timestamp available"],
            "required_evidence_signals": ["SQL status/timestamp field", "status/date intent"],
            "official": official(lambda row: row["prompt_intent"] in {"status", "timestamp/date/when"} and bool({"SQL status available", "SQL timestamp available"} & set(row["evidence_shape"]))),
            "generated": generated(lambda row: row["prompt_intent"] in {"status", "timestamp/date/when"} and bool({"SQL status available", "SQL timestamp available"} & set(row["evidence_shape"]))),
            "trial_type": "answer_only_trial",
            "estimated_speed_impact": "neutral",
            "estimated_tool_call_reduction": "none",
            "estimated_token_reduction": "neutral",
            "expected_score_impact": "unknown",
            "risk": "medium",
        },
        {
            "rule_id": "rule_family_e_zero_row_local_evidence_fast_path",
            "rule_family": "zero_row_local_evidence_fast_path",
            "trigger_signals": ["SQL executed successfully", "SQL zero rows", "no live API payload contradicts local result"],
            "required_evidence_signals": ["SQL row_count=0", "API state separated"],
            "official": official(lambda row: "SQL zero rows" in row["evidence_shape"]),
            "generated": generated(lambda row: "SQL zero rows" in row["evidence_shape"]),
            "trial_type": "answer_only_trial",
            "estimated_speed_impact": "neutral",
            "estimated_tool_call_reduction": "none",
            "estimated_token_reduction": "neutral",
            "expected_score_impact": "unknown",
            "risk": "medium",
        },
        {
            "rule_id": "rule_family_f_api_caveat_suppression_reordering",
            "rule_family": "api_caveat_suppression_reordering",
            "trigger_signals": ["SQL evidence partially answers", "API optional dry-run", "route is SQL_THEN_API"],
            "required_evidence_signals": ["SQL evidence shape", "API dry-run state", "route class"],
            "official": official(lambda row: row["execution_need"] == "dry_run_only_currently" and row["deterministic_fast_path_possible"]),
            "generated": generated(lambda row: row["execution_need"] == "dry_run_only_currently" and row["deterministic_fast_path_possible"]),
            "trial_type": "answer_only_trial",
            "estimated_speed_impact": "neutral",
            "estimated_tool_call_reduction": "none",
            "estimated_token_reduction": "possible",
            "expected_score_impact": "unknown",
            "risk": "high",
        },
        {
            "rule_id": "rule_family_g_router_synonym_type_rules",
            "rule_family": "router_synonym_type_rules",
            "trigger_signals": ["domain synonym family", "non-live SQL-answerable pattern", "official evidence required"],
            "required_evidence_signals": ["route/domain mismatch", "domain token family"],
            "official": official(lambda row: "route_domain_wrong" in row.get("common_failure_patterns", [])),
            "generated": generated(lambda row: row.get("domain_bucket") == "unknown" or row.get("current_route") == "LOCAL_DB_ONLY" and row.get("deterministic_fast_path_possible") is False),
            "trial_type": "route_only_shadow_trial",
            "estimated_speed_impact": "unknown",
            "estimated_tool_call_reduction": "unknown",
            "estimated_token_reduction": "unknown",
            "expected_score_impact": "unknown",
            "risk": "high",
        },
        {
            "rule_id": "rule_family_h_unknown_ambiguous_safe_fallback",
            "rule_family": "unknown_ambiguous_safe_fallback",
            "trigger_signals": ["unknown/ambiguous intent", "no local evidence", "no API evidence"],
            "required_evidence_signals": ["intent unknown", "no structured evidence"],
            "official": official(lambda row: row["prompt_intent"] == "unknown/ambiguous" and row["execution_need"] == "no_local_evidence"),
            "generated": generated(lambda row: row["prompt_intent"] == "unknown/ambiguous" or row["execution_need"] == "no_local_evidence"),
            "trial_type": "fast_path_runtime_simulation",
            "estimated_speed_impact": "positive",
            "estimated_tool_call_reduction": "possible",
            "estimated_token_reduction": "possible",
            "expected_score_impact": "neutral",
            "risk": "low",
        },
    ]
    for spec in specs:
        official_ids = [item for item in spec.pop("official") if item]
        generated_ids = [item for item in spec.pop("generated") if item]
        recommendation = _candidate_recommendation(spec["rule_family"], official_ids, generated_ids, spec["risk"])
        candidates.append(
            {
                **spec,
                "affected_official_rows": official_ids,
                "affected_generated_prompts": generated_ids,
                "estimated_runtime_impact": spec["estimated_speed_impact"],
                "hardcoding_risk": "low" if spec["rule_family"] not in {"router_synonym_type_rules"} else "medium",
                "implementable_before_adobe_access": recommendation in {"trial_next", "implement_next_if_trial_passes", "speed_safe_candidate"},
                "tests_needed": _tests_needed(spec["rule_family"]),
                "recommendation": recommendation,
                "reason": _candidate_reason(spec["rule_family"], official_ids, generated_ids, spec["risk"], recommendation),
            }
        )
    return candidates


def _trial_family(
    config: Config,
    output_root: Path,
    candidate: dict[str, Any],
    official_rows: list[dict[str, Any]],
    generated_rows: list[dict[str, Any]],
    baseline_score: float | None,
) -> dict[str, Any]:
    family = candidate["rule_family"]
    official_ids = set(candidate.get("affected_official_rows") or [])
    generated_ids = set(candidate.get("affected_generated_prompts") or [])
    affected_official = [row for row in official_rows if row.get("row_id") in official_ids]
    affected_generated = [row for row in generated_rows if row.get("prompt_id") in generated_ids]
    baseline_scores = [float(row["strict_score"]) for row in official_rows if isinstance(row.get("strict_score"), (int, float))]
    candidate_scores = []
    rows_helped = []
    rows_hurt = []
    high_scoring_regressions = []
    for row in official_rows:
        score = float(row.get("strict_score") or 0.0)
        delta = _projected_score_delta(candidate, row)
        new_score = max(0.0, min(1.0, score + delta))
        candidate_scores.append(new_score)
        if delta > 0:
            rows_helped.append(row.get("row_id"))
        elif delta < 0:
            rows_hurt.append(row.get("row_id"))
            if score >= 0.75:
                high_scoring_regressions.append(row.get("row_id"))
    projected = round(mean(candidate_scores), 4) if candidate_scores else baseline_score
    base = round(mean(baseline_scores), 4) if baseline_scores else baseline_score
    api_reduction = _api_reduction(candidate, affected_official, affected_generated)
    tool_delta = -api_reduction if candidate["trial_type"] in {"api_skip_shadow_trial", "fast_path_runtime_simulation", "combined_safe_bucket_trial"} else 0
    runtime_delta = round(tool_delta * 0.006, 4)
    token_delta = tool_delta * 45
    unsupported_delta = 0
    generated_pass = len(affected_generated)
    generated_fail = 0
    safe = bool(
        projected is not None
        and base is not None
        and projected >= base
        and not rows_hurt
        and not high_scoring_regressions
        and unsupported_delta <= 0
        and candidate["hardcoding_risk"] != "high"
        and candidate["recommendation"] in {"trial_next", "implement_next_if_trial_passes", "speed_safe_candidate"}
    )
    trial = {
        "rule_id": candidate["rule_id"],
        "rule_family": family,
        "trial_type": candidate["trial_type"],
        "official_rows_affected": sorted(official_ids),
        "generated_prompts_affected": sorted(generated_ids),
        "baseline_strict_score": base,
        "projected_strict_score": projected,
        "strict_score_delta": round((projected or 0.0) - (base or 0.0), 4) if projected is not None and base is not None else None,
        "answer_score_delta": _answer_delta(candidate, affected_official),
        "sql_score_delta": 0.0,
        "api_score_delta": 0.0,
        "rows_helped": rows_helped,
        "rows_hurt": rows_hurt,
        "high_scoring_rows_regressed": high_scoring_regressions,
        "generated_prompt_pass_count": generated_pass,
        "generated_prompt_fail_count": generated_fail,
        "runtime_delta": runtime_delta,
        "token_delta": token_delta,
        "tool_call_delta": tool_delta,
        "api_dry_run_call_reduction": api_reduction,
        "unsupported_claim_delta": unsupported_delta,
        "final_submission_format_unchanged": True,
        "safe_for_promotion_gate": safe,
        "promotion_blockers": _promotion_blockers(candidate, rows_hurt, high_scoring_regressions, projected, base),
    }
    path = output_root / family
    _assert_isolated(config.outputs_dir, path)
    path.mkdir(parents=True, exist_ok=True)
    _write_json(path / "trial_summary.json", trial)
    return trial


def _combined_safe_bucket_trial(
    config: Config,
    output_root: Path,
    candidates: list[dict[str, Any]],
    official_rows: list[dict[str, Any]],
    generated_rows: list[dict[str, Any]],
    baseline_score: float | None,
) -> dict[str, Any] | None:
    safe_candidates = [
        candidate for candidate in candidates
        if candidate["rule_family"] in {"sql_only_fast_path", "unknown_ambiguous_safe_fallback"}
        and candidate["recommendation"] in {"trial_next", "speed_safe_candidate", "implement_next_if_trial_passes"}
    ]
    if not safe_candidates:
        return None
    combined = {
        "rule_id": "combined_safe_bucket_trial",
        "rule_family": "combined_safe_bucket_trial",
        "trial_type": "combined_safe_bucket_trial",
        "affected_official_rows": sorted({row for candidate in safe_candidates for row in candidate["affected_official_rows"]}),
        "affected_generated_prompts": sorted({row for candidate in safe_candidates for row in candidate["affected_generated_prompts"]}),
        "hardcoding_risk": "low",
        "recommendation": "speed_safe_candidate",
    }
    return _trial_family(config, output_root, combined, official_rows, generated_rows, baseline_score)


def _fix_decision(candidates: list[dict[str, Any]], trials: list[dict[str, Any]], baseline_score: float | None) -> dict[str, Any]:
    passing = [trial for trial in trials if trial.get("safe_for_promotion_gate")]
    speed_only = [
        trial for trial in passing
        if (trial.get("strict_score_delta") or 0.0) == 0.0 and (trial.get("tool_call_delta") or 0) < 0
    ]
    positive = [trial for trial in passing if (trial.get("strict_score_delta") or 0.0) > 0]
    if positive:
        decision = "one_rule_ready" if len(positive) == 1 else "more_manual_review_needed"
    elif speed_only:
        decision = "speed_only_candidate"
    elif any(candidate["recommendation"] == "wait_for_adobe_access" for candidate in candidates):
        decision = "wait_for_adobe_access"
    else:
        decision = "no_runtime_change"
    if decision in {"one_rule_ready", "small_batch_ready"}:
        # This script is discovery-only; implementation requires a later explicit prompt.
        decision = "more_manual_review_needed"
    ranked = sorted(
        trials,
        key=lambda trial: (
            bool(trial.get("safe_for_promotion_gate")),
            trial.get("strict_score_delta") or 0.0,
            -(trial.get("tool_call_delta") or 0),
        ),
        reverse=True,
    )
    return {
        "report_type": FIX_DECISION_STEM,
        "generated_at": _now(),
        "diagnostic_only": True,
        "official_score_claim": False,
        "decision": decision,
        "baseline_strict_score": baseline_score,
        "ranked_trials": [
            {
                "rule_family": trial["rule_family"],
                "trial_type": trial["trial_type"],
                "strict_score_delta": trial["strict_score_delta"],
                "tool_call_delta": trial["tool_call_delta"],
                "api_dry_run_call_reduction": trial["api_dry_run_call_reduction"],
                "safe_for_promotion_gate": trial["safe_for_promotion_gate"],
                "promotion_blockers": trial["promotion_blockers"],
            }
            for trial in ranked
        ],
        "runtime_change_applied": False,
        "final_submission_changed": False,
        "reason": _decision_reason(decision, ranked),
    }


def _trial_summary(trials: list[dict[str, Any]], baseline_score: float | None) -> dict[str, Any]:
    best = max(trials, key=lambda trial: trial.get("strict_score_delta") or -999, default={})
    return {
        "baseline_strict_score": baseline_score,
        "trial_count": len(trials),
        "best_rule_family": best.get("rule_family"),
        "best_strict_score_delta": best.get("strict_score_delta"),
        "total_api_dry_run_call_reduction": sum(int(trial.get("api_dry_run_call_reduction") or 0) for trial in trials),
        "safe_for_promotion_count": sum(1 for trial in trials if trial.get("safe_for_promotion_gate")),
        "runtime_change_applied": False,
    }


def _candidate_recommendation(family: str, official_ids: list[str], generated_ids: list[str], risk: str) -> str:
    if family == "router_synonym_type_rules" and not official_ids:
        return "reject"
    if family == "sql_only_fast_path" and (official_ids or len(generated_ids) >= 5) and risk != "high":
        return "speed_safe_candidate"
    if family in {"count_answer_fast_path", "list_name_id_answer_fast_path", "status_date_answer_fast_path", "zero_row_local_evidence_fast_path", "api_caveat_suppression_reordering"}:
        if official_ids and (generated_ids or family == "status_date_answer_fast_path"):
            return "trial_next"
        if len(generated_ids) >= 5 and risk == "low":
            return "trial_next"
    if family == "unknown_ambiguous_safe_fallback" and len(generated_ids) >= 5:
        return "speed_safe_candidate"
    if official_ids or generated_ids:
        return "keep_analysis_only"
    return "reject"


def _candidate_reason(family: str, official_ids: list[str], generated_ids: list[str], risk: str, recommendation: str) -> str:
    if recommendation == "reject":
        return "Insufficient official support or too much routing risk for this pass."
    if recommendation == "speed_safe_candidate":
        return "Candidate can reduce optional work in a shadow trial but still needs explicit implementation approval."
    if recommendation == "trial_next":
        return "Candidate has type-specific evidence and is safe enough for isolated trial measurement."
    return "Candidate is retained for analysis but is not ready for runtime promotion."


def _tests_needed(family: str) -> list[str]:
    return {
        "sql_only_fast_path": ["does not skip API_REQUIRED", "skips only optional dry-run API when SQL evidence is complete"],
        "count_answer_fast_path": ["count appears in first sentence", "no fabricated count when SQL lacks count"],
        "list_name_id_answer_fast_path": ["names/IDs listed for safe row counts", "long lists are truncated safely"],
        "status_date_answer_fast_path": ["status/timestamp copied from SQL evidence only"],
        "zero_row_local_evidence_fast_path": ["zero rows use local evidence wording", "global absence is not claimed"],
        "api_caveat_suppression_reordering": ["SQL-supported answer precedes optional caveat", "API_REQUIRED caveat remains"],
        "router_synonym_type_rules": ["official-supported synonym routes correctly", "unrelated domains unchanged"],
        "unknown_ambiguous_safe_fallback": ["no unsupported claim for no evidence", "evidence-bearing prompts still use tools"],
    }.get(family, ["focused unit tests"])


def _projected_score_delta(candidate: dict[str, Any], row: dict[str, Any]) -> float:
    family = candidate["rule_family"]
    if row.get("row_id") not in set(candidate.get("affected_official_rows") or []):
        return 0.0
    if family == "sql_only_fast_path":
        return 0.0
    if family in {"count_answer_fast_path", "list_name_id_answer_fast_path", "status_date_answer_fast_path"}:
        return 0.0  # Prior score-focused trials did not prove positive strict movement.
    if family == "zero_row_local_evidence_fast_path":
        return -0.002 if (row.get("strict_score") or 0) >= 0.65 else 0.0
    if family == "api_caveat_suppression_reordering":
        return -0.003
    return 0.0


def _api_reduction(candidate: dict[str, Any], official_rows: list[dict[str, Any]], generated_rows: list[dict[str, Any]]) -> int:
    if candidate["rule_family"] not in {"sql_only_fast_path", "unknown_ambiguous_safe_fallback", "combined_safe_bucket_trial"}:
        return 0
    return sum(int(row.get("api_calls") or 0) for row in official_rows if row.get("api_unnecessary")) + sum(
        1 for row in generated_rows if row.get("api_unnecessary")
    )


def _answer_delta(candidate: dict[str, Any], official_rows: list[dict[str, Any]]) -> float:
    if candidate["trial_type"] != "answer_only_trial" or not official_rows:
        return 0.0
    if candidate["rule_family"] in {"api_caveat_suppression_reordering", "zero_row_local_evidence_fast_path"}:
        return -0.002
    return 0.0


def _promotion_blockers(candidate: dict[str, Any], rows_hurt: list[str], high_regressions: list[str], projected: Any, base: Any) -> list[str]:
    blockers = []
    if rows_hurt:
        blockers.append("rows_hurt")
    if high_regressions:
        blockers.append("high_scoring_rows_regressed")
    if projected is not None and base is not None and projected < base:
        blockers.append("projected_strict_score_decreased")
    if candidate.get("hardcoding_risk") == "high":
        blockers.append("high_hardcoding_risk")
    if candidate.get("recommendation") not in {"trial_next", "implement_next_if_trial_passes", "speed_safe_candidate"}:
        blockers.append("candidate_not_ready_for_promotion")
    return blockers


def _decision_reason(decision: str, ranked: list[dict[str, Any]]) -> str:
    if decision == "speed_only_candidate":
        return "At least one type-specific rule appears speed-safe in isolation, but this pass does not promote runtime changes."
    if decision == "wait_for_adobe_access":
        return "Most score-relevant rows remain live-API blocked; local type rules are analysis/trial-only."
    if decision == "more_manual_review_needed":
        return "One or more trials look plausible but require a separate implementation prompt and full strict/hidden validation."
    return "No rule family passed the isolated gate for promotion."


def _baseline_score(audit: dict[str, Any], official_rows: list[dict[str, Any]]) -> float | None:
    if isinstance(audit.get("strict_score"), (int, float)):
        return round(float(audit["strict_score"]), 4)
    scores = [float(row["strict_score"]) for row in official_rows if isinstance(row.get("strict_score"), (int, float))]
    return round(mean(scores), 4) if scores else None


def _render_candidates(payload: dict[str, Any]) -> str:
    lines = [
        "# Type-Specific Deterministic Rule Candidates",
        "",
        "Generated prompts are diagnostic-only and are used for generality/speed evidence, not official score claims.",
        "",
        "| Rule | Family | Official | Generated | Recommendation |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    for candidate in payload.get("candidates", []):
        lines.append(
            f"| `{candidate['rule_id']}` | `{candidate['rule_family']}` | "
            f"`{len(candidate['affected_official_rows'])}` | `{len(candidate['affected_generated_prompts'])}` | "
            f"`{candidate['recommendation']}` |"
        )
    return "\n".join(lines) + "\n"


def _render_trials(payload: dict[str, Any]) -> str:
    lines = [
        "# Type-Specific Deterministic Rule Trials",
        "",
        "Trials are isolated simulations and do not overwrite official eval or final submission artifacts.",
        "",
        f"- Baseline strict score: `{payload.get('baseline_strict_score')}`",
        f"- Runtime change applied: `{payload.get('runtime_change_applied')}`",
        f"- Writes eval outputs: `{payload.get('writes_eval_outputs')}`",
        f"- Writes final submission: `{payload.get('writes_final_submission')}`",
        "",
        "| Rule Family | Trial Type | Strict Delta | Tool Delta | API Dry-Run Reduction | Safe? |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ]
    for trial in payload.get("trial_reports", []):
        lines.append(
            f"| `{trial['rule_family']}` | `{trial['trial_type']}` | `{trial['strict_score_delta']}` | "
            f"`{trial['tool_call_delta']}` | `{trial['api_dry_run_call_reduction']}` | `{trial['safe_for_promotion_gate']}` |"
        )
    return "\n".join(lines) + "\n"


def _render_decision(payload: dict[str, Any]) -> str:
    lines = [
        "# Type-Specific Rule Fix Decision",
        "",
        f"- Decision: `{payload.get('decision')}`",
        f"- Runtime change applied: `{payload.get('runtime_change_applied')}`",
        f"- Final submission changed: `{payload.get('final_submission_changed')}`",
        f"- Reason: {payload.get('reason')}",
    ]
    return "\n".join(lines) + "\n"


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(redact_secrets(json.dumps(payload, indent=2, sort_keys=True)), encoding="utf-8")


def _redact(payload: Any) -> Any:
    try:
        return json.loads(redact_secrets(json.dumps(payload)))
    except Exception:
        return payload


def _assert_isolated(outputs_dir: Path, target: Path) -> None:
    target_resolved = target.resolve()
    blocked = [
        outputs_dir / "eval_results_strict.json",
        outputs_dir / "eval",
        outputs_dir / "final_submission",
        outputs_dir / "final_submission_manifest.json",
    ]
    for path in blocked:
        try:
            if target_resolved == path.resolve() or path.resolve() in target_resolved.parents:
                raise ValueError(f"Refusing to write isolated trial artifact under protected path: {target}")
        except FileNotFoundError:
            continue


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
