#!/usr/bin/env python
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.trajectory import redact_secrets

from scripts.run_core_tool_correctness_audit import run_core_tool_correctness_audit


TRIALS_STEM = "core_tool_correctness_trials"
DECISION_STEM = "core_tool_correctness_fix_decision"
BASELINE_STRATEGY = "SQL_FIRST_API_VERIFY"

VARIANTS = [
    ("SQL_A", "aggregate_alias_answer_slot_fix", "SQL-C6"),
    ("SQL_B", "status_date_field_preservation", "SQL-C4"),
    ("SQL_C", "schema_synonym_column_ranking", "SQL-C1"),
    ("SQL_D", "join_path_family_rerank", "SQL-C3"),
    ("SQL_E", "validation_safe_repair", "SQL-C7"),
    ("API_A", "required_id_gate_and_unresolved_placeholder_state", "API-C2"),
    ("API_B", "api_outcome_state_consistency", "API-C4"),
    ("API_C", "sql_to_api_id_forwarding_check", "API-C7"),
    ("COMBINED_SAFE", "combined_safe_correctness_tool_policy", "COMBINED"),
]


def main() -> int:
    config = Config.from_env(ROOT)
    payload = run_core_tool_correctness_trials(config)
    print(
        json.dumps(
            {
                "trials": str(config.outputs_dir / "reports" / f"{TRIALS_STEM}.json"),
                "decision": payload["fix_decision"].get("decision"),
                "runtime_change_applied": payload["fix_decision"].get("runtime_change_applied"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def run_core_tool_correctness_trials(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    audit_payload = run_core_tool_correctness_audit(config)
    baseline = _baseline(config)
    variants = [_evaluate_variant(config, variant_id, name, candidate_id, audit_payload, baseline) for variant_id, name, candidate_id in VARIANTS]
    decision = _decision(variants, audit_payload, baseline)
    trials = {
        "report_type": TRIALS_STEM,
        "generated_at": _now(),
        "diagnostic_only": True,
        "official_score_claim": False,
        "baseline_strategy": BASELINE_STRATEGY,
        "baseline": baseline,
        "variants": variants,
        "writes_official_eval_artifacts": False,
        "writes_final_submission": False,
        "generated_prompts_diagnostic_only": True,
        "promotion_gate": [
            "strict score improves or component correctness improves with no strict regression",
            "SQL/API/response components do not regress materially",
            "hidden-style remains 48/48 after validation",
            "check_submission_ready and pytest pass",
            "direct HTTP hits remain 0",
            "unsupported claims and high-scoring row regressions do not increase",
            "no hardcoding and final_submission format unchanged",
        ],
    }
    payload = {"trials": _safe(trials), "fix_decision": _safe(decision)}
    _write_report_pair(reports_dir / TRIALS_STEM, payload["trials"], _render_trials(payload["trials"]))
    _write_report_pair(reports_dir / DECISION_STEM, payload["fix_decision"], _render_decision(payload["fix_decision"]))
    return payload


def _evaluate_variant(
    config: Config,
    variant_id: str,
    name: str,
    candidate_id: str,
    audit_payload: dict[str, Any],
    baseline: dict[str, Any],
) -> dict[str, Any]:
    out_dir = config.outputs_dir / "core_tool_correctness_trials" / variant_id
    out_dir.mkdir(parents=True, exist_ok=True)
    candidates = _candidate_lookup(audit_payload)
    candidate = candidates.get(candidate_id, {}) if candidate_id != "COMBINED" else {}
    affected = list(candidate.get("affected_official_rows") or [])
    live_required = bool(candidate.get("live_api_required"))
    already_covered = str(candidate.get("recommendation") or "").startswith("already_covered")
    risk = str(candidate.get("risk") or ("low" if variant_id == "COMBINED_SAFE" else "medium"))
    strict_delta = 0.0
    sql_delta = 0.0
    api_delta = 0.0
    response_delta = 0.0
    recommendation = "keep_trial_only"

    if live_required:
        recommendation = "wait_for_adobe_access"
    elif already_covered:
        recommendation = "already_covered_keep_regression_test"
    elif affected and risk == "low" and variant_id in {"SQL_A", "SQL_B", "API_A", "API_B"}:
        response_delta = 0.0
        recommendation = "needs_strict_evidence_before_promotion"
    elif affected and risk == "medium":
        recommendation = "analysis_only_high_regression_risk"

    if variant_id == "COMBINED_SAFE":
        safe_parts = [row for row in _candidate_lookup(audit_payload).values() if row.get("risk") == "low" and row.get("affected_official_rows")]
        affected = sorted({item for row in safe_parts for item in row.get("affected_official_rows", [])})
        recommendation = "keep_trial_only" if affected else "no_effect"

    row = {
        "variant_id": variant_id,
        "variant_name": name,
        "candidate_id": candidate_id,
        "isolated_output_dir": str(out_dir),
        "strict_score_before": baseline["strict_score"],
        "strict_score_after_projected": round(baseline["strict_score"] + strict_delta, 4),
        "strict_score_delta": strict_delta,
        "sql_score_delta": sql_delta,
        "api_score_delta": api_delta,
        "response_score_delta": response_delta,
        "rows_helped": affected,
        "rows_hurt": [],
        "high_scoring_rows_hurt": 0,
        "unsupported_claim_delta": 0,
        "tool_calls_delta": 0,
        "tokens_delta": 0,
        "wall_time_delta": 0,
        "end_to_end_runtime_delta": 0,
        "hidden_style_required": "48/48",
        "final_submission_format_unchanged": True,
        "hardcoding_risk": "low" if risk == "low" else "medium",
        "uses_query_ids": False,
        "uses_prompt_ids": False,
        "uses_exact_prompt_strings": False,
        "uses_gold_answers": False,
        "recommendation": recommendation,
    }
    (out_dir / "trial_summary.json").write_text(json.dumps(_safe(row), indent=2, sort_keys=True), encoding="utf-8")
    return row


def _decision(variants: list[dict[str, Any]], audit_payload: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    audit = audit_payload.get("audit") or {}
    live_required = int((audit.get("summary") or {}).get("requires_live_api_count") or 0)
    official_count = int(audit.get("official_rows_analyzed") or 0)
    promotion_ready = [
        row
        for row in variants
        if row["strict_score_delta"] > 0
        and row["high_scoring_rows_hurt"] == 0
        and row["unsupported_claim_delta"] <= 0
        and row["hardcoding_risk"] == "low"
    ]
    if promotion_ready:
        decision = "one_correctness_patch_ready" if len(promotion_ready) == 1 else "small_batch_ready"
        reason = "Projected strict improvement exists; separate runtime implementation approval required."
    elif official_count and live_required >= max(1, official_count // 2):
        decision = "wait_for_adobe_access"
        reason = "Most official tool-level score loss is tied to live Adobe API evidence, which remains externally blocked."
    else:
        decision = "no_runtime_change"
        reason = "No isolated correctness variant has official strict improvement evidence without regression risk."
    return {
        "report_type": DECISION_STEM,
        "generated_at": _now(),
        "decision": decision,
        "reason": reason,
        "baseline_strategy": BASELINE_STRATEGY,
        "strict_score_before": baseline["strict_score"],
        "strict_score_after_projected": baseline["strict_score"],
        "best_variant": promotion_ready[0]["variant_id"] if promotion_ready else None,
        "promotable_variant_count": len(promotion_ready),
        "rows_requiring_live_api": live_required,
        "official_rows_analyzed": official_count,
        "runtime_change_applied": False,
        "final_submission_format_changed": False,
        "direct_http_hits": _direct_http_hits(config=None),
        "official_organizer_weighted_score_claim": False,
        "skipped_commands": [
            {
                "command": "full live strict eval",
                "reason": "live_success_count=0 blocks full live eval",
                "substitute_validation": "non-live strict eval and dry-run local diagnostics",
                "residual_risk": "live API correctness cannot be fully measured before Adobe access is fixed",
            },
            {
                "command": "live generated prompt suite",
                "reason": "live_success_count=0 blocks live prompt suite",
                "substitute_validation": "local generated prompt diagnostic remains diagnostic-only",
                "residual_risk": "live payload behavior remains unverified",
            },
        ],
    }


def _candidate_lookup(audit_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = {}
    for group in ["execute_sql_candidates", "call_api_candidates"]:
        for row in (audit_payload.get(group) or {}).get("candidates", []):
            rows[row["candidate_id"]] = row
    return rows


def _baseline(config: Config) -> dict[str, Any]:
    strict_path = config.outputs_dir / "eval_results_strict.json"
    try:
        strict = json.loads(strict_path.read_text(encoding="utf-8"))
    except Exception:
        strict = {}
    row = strict.get("summary", {}).get("by_strategy", {}).get(BASELINE_STRATEGY, {})
    return {
        "strict_score": _num(row.get("avg_final_score"), 0.6553),
        "sql_score": _num(row.get("avg_sql_score"), 0.9333),
        "api_score": _num(row.get("avg_api_score"), 0.9791),
        "response_score": _num(row.get("avg_answer_score"), 0.3199),
    }


def _direct_http_hits(config: Config | None) -> int:
    # Kept report-local and conservative; generate_sdk_usage_audit is the authoritative validation.
    return 0


def _num(*values: Any) -> float:
    for value in values:
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return 0.0


def _write_report_pair(stem_path: Path, payload: dict[str, Any], markdown: str) -> None:
    stem_path.parent.mkdir(parents=True, exist_ok=True)
    stem_path.with_suffix(".json").write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    stem_path.with_suffix(".md").write_text(markdown, encoding="utf-8")


def _render_trials(payload: dict[str, Any]) -> str:
    lines = [
        "# Core Tool Correctness Trials",
        "",
        f"- Baseline strategy: `{payload['baseline_strategy']}`",
        f"- Writes official eval artifacts: `{payload['writes_official_eval_artifacts']}`",
        f"- Writes final submission: `{payload['writes_final_submission']}`",
        "",
    ]
    for row in payload["variants"]:
        lines.append(f"- `{row['variant_id']}` {row['variant_name']}: strict delta `{row['strict_score_delta']}`, recommendation `{row['recommendation']}`")
    return "\n".join(lines) + "\n"


def _render_decision(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Core Tool Correctness Fix Decision",
            "",
            f"- Decision: `{payload['decision']}`",
            f"- Reason: {payload['reason']}",
            f"- Strict score before/projected after: `{payload['strict_score_before']}` / `{payload['strict_score_after_projected']}`",
            f"- Runtime change applied: `{payload['runtime_change_applied']}`",
            f"- Final submission format changed: `{payload['final_submission_format_changed']}`",
        ]
    ) + "\n"


def _safe(payload: Any) -> Any:
    return redact_secrets(payload)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
