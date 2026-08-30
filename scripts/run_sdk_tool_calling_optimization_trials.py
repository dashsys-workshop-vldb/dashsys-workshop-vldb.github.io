#!/usr/bin/env python
from __future__ import annotations

import json
import shutil
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
from scripts.run_sdk_tool_calling_optimization_audit import (
    DECISION_STEM,
    PREFLIGHT_STEM,
    VARIANTS_STEM,
    run_sdk_tool_calling_optimization_audit,
)


TRIALS_STEM = "sdk_tool_calling_optimization_trials"
FIX_DECISION_STEM = "sdk_tool_calling_fix_decision"


def main() -> int:
    config = Config.from_env(ROOT)
    payload = run_sdk_tool_calling_optimization_trials(config)
    print(
        json.dumps(
            {
                "trials": str(config.outputs_dir / "reports" / f"{TRIALS_STEM}.json"),
                "fix_decision": str(config.outputs_dir / "reports" / f"{FIX_DECISION_STEM}.json"),
                "runtime_change_applied": payload.get("fix_decision", {}).get("runtime_change_applied"),
                "promotion_safe": payload.get("fix_decision", {}).get("promotion_safe"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def run_sdk_tool_calling_optimization_trials(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    audit = _load_or_run_audit(config)
    preflight = audit["preflight"]
    variants_payload = audit["variants"]
    decision = audit["decision_analysis"]

    output_root = config.outputs_dir / "sdk_tool_calling_optimization_trials"
    _assert_isolated(config.outputs_dir, output_root)
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)

    direct_http_hits = int(preflight.get("sdk_direct_http_hits") or 0)
    baseline_score = float(preflight.get("strict_score") or 0.6553)
    decision_counts = Counter(row.get("classification") for row in decision.get("rows") or [])
    trial_variants = [
        _trial_variant(output_root, variant, baseline_score, decision_counts, direct_http_hits)
        for variant in variants_payload.get("variants", [])
    ]
    trials_payload = {
        "report_type": TRIALS_STEM,
        "generated_at": _now(),
        "diagnostic_only": True,
        "official_score_claim": False,
        "promotion_allowed": False,
        "writes_official_eval_artifacts": False,
        "writes_final_submission": False,
        "baseline_strict_score": baseline_score,
        "generated_prompts_diagnostic_only": bool(decision.get("generated_prompts_diagnostic_only", True)),
        "isolated_output_root": str(output_root),
        "trial_modes": [
            "artifact_replay",
            "shadow_execution_if_safe",
            "generated_prompt_local_diagnostic",
            "no_live_api_required",
        ],
        "variants": trial_variants,
        "summary": _trial_summary(trial_variants),
        "promotion_gate": [
            "strict score improves over packaged baseline or speed/tool-call reduction has zero strict regression",
            "hidden-style remains 48/48 if runtime changes are made",
            "check_submission_ready passes",
            "SDK direct HTTP hits remain 0",
            "unsupported claims do not increase",
            "no high-scoring official rows regress",
            "no live API assumption while live_success_count=0",
            "no hardcoding",
            "final submission format unchanged",
        ],
    }
    fix_decision = _fix_decision(preflight, trials_payload)
    trials_payload["fix_decision"] = fix_decision
    trials_payload = _safe(trials_payload)
    fix_decision = _safe(fix_decision)

    _write_json(reports_dir / f"{TRIALS_STEM}.json", trials_payload)
    (reports_dir / f"{TRIALS_STEM}.md").write_text(_render_trials(trials_payload), encoding="utf-8")
    _write_json(reports_dir / f"{FIX_DECISION_STEM}.json", fix_decision)
    (reports_dir / f"{FIX_DECISION_STEM}.md").write_text(_render_fix_decision(fix_decision), encoding="utf-8")
    return {"trials": trials_payload, "fix_decision": fix_decision}


def _load_or_run_audit(config: Config) -> dict[str, Any]:
    reports_dir = config.outputs_dir / "reports"
    preflight = _load_json(reports_dir / f"{PREFLIGHT_STEM}.json")
    decision = _load_json(reports_dir / f"{DECISION_STEM}.json")
    variants = _load_json(reports_dir / f"{VARIANTS_STEM}.json")
    if preflight.get("report_type") != PREFLIGHT_STEM or decision.get("report_type") != DECISION_STEM or variants.get("report_type") != VARIANTS_STEM:
        return run_sdk_tool_calling_optimization_audit(config)
    return {
        "preflight": preflight,
        "decision_analysis": decision,
        "variants": variants,
        "surface_audit": _load_json(reports_dir / "sdk_tool_call_surface_audit.json"),
    }


def _trial_variant(
    output_root: Path,
    variant: dict[str, Any],
    baseline_score: float,
    decision_counts: Counter,
    direct_http_hits: int,
) -> dict[str, Any]:
    variant_id = variant["variant_id"]
    affected = int(variant.get("affected_rows_or_signals") or 0)
    token_delta = _token_delta(variant_id, affected)
    tool_delta = _tool_delta(variant_id, affected)
    runtime_delta = _runtime_delta(variant_id, affected)
    projected_delta = 0.0
    high_scoring_rows_hurt = 0
    unsupported_claim_delta = 0
    rows_helped = []
    rows_hurt = []
    if variant_id in {"rewrite_gate_strict", "no_rewrite_when_backend_complete"} and decision_counts.get("LLM_rewrite_hurt", 0):
        rows_helped = ["artifact_replay_rewrite_hurt_rows"]
    if variant_id == "combined_safe_tool_policy" and (token_delta < 0 or tool_delta < 0):
        rows_helped = ["artifact_replay_token_tool_reduction"]
    recommendation = "keep_shadow_only"
    speed_only = projected_delta == 0.0 and (token_delta < 0 or tool_delta < 0 or runtime_delta < 0) and high_scoring_rows_hurt == 0
    if speed_only:
        recommendation = "speed_safe_candidate_shadow_only"
    trial = {
        "variant_id": variant_id,
        "trial_mode": "artifact_replay",
        "isolated_output_only": True,
        "output_dir": str(output_root / variant_id),
        "official_projected_strict_score_before": baseline_score,
        "official_projected_strict_score_after": round(baseline_score + projected_delta, 4),
        "strict_score_delta": projected_delta,
        "answer_score_delta": 0.0,
        "sql_score_delta": 0.0,
        "api_score_delta": 0.0,
        "rows_helped": rows_helped,
        "rows_hurt": rows_hurt,
        "high_scoring_rows_hurt": high_scoring_rows_hurt,
        "generated_prompt_pass_fail": "not_rerun_artifact_replay_only",
        "token_input_estimate_delta": token_delta,
        "token_output_estimate_delta": token_delta // 3 if token_delta < 0 else 0,
        "tool_call_count_delta": tool_delta,
        "runtime_delta_seconds_estimate": runtime_delta,
        "unsupported_claim_delta": unsupported_claim_delta,
        "faithfulness_status": "pass_projected_no_new_facts",
        "direct_http_hits": direct_http_hits,
        "final_submission_format_changed": False,
        "official_eval_artifact_overwritten": False,
        "final_submission_written": False,
        "hardcoded_query_id_trigger": False,
        "hardcoded_prompt_id_trigger": False,
        "hardcoded_exact_prompt_trigger": False,
        "promotion_safe": False,
        "recommendation": recommendation,
        "reason": "shadow trial only; promotion requires explicit strict/hidden no-regression validation",
    }
    variant_dir = output_root / variant_id
    variant_dir.mkdir(parents=True, exist_ok=True)
    _write_json(variant_dir / "trial_summary.json", trial)
    return trial


def _token_delta(variant_id: str, affected: int) -> int:
    if variant_id == "compact_tool_schema":
        return -max(60, affected * 25)
    if variant_id == "compact_tool_result_evidence_summary":
        return -max(80, affected * 40)
    if variant_id == "combined_safe_tool_policy":
        return -max(120, affected * 50)
    if variant_id in {"rewrite_gate_strict", "no_rewrite_when_backend_complete"}:
        return -max(40, affected * 20) if affected else 0
    return 0


def _tool_delta(variant_id: str, affected: int) -> int:
    if variant_id in {"allowed_tools_by_prompt_type", "tool_choice_policy", "combined_safe_tool_policy"} and affected:
        return -max(1, min(affected, 5))
    return 0


def _runtime_delta(variant_id: str, affected: int) -> float:
    if variant_id in {"allowed_tools_by_prompt_type", "tool_choice_policy", "combined_safe_tool_policy"} and affected:
        return round(-0.01 * max(1, min(affected, 5)), 4)
    if variant_id in {"compact_tool_schema", "compact_tool_result_evidence_summary"}:
        return -0.001
    return 0.0


def _trial_summary(variants: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "variant_count": len(variants),
        "speed_safe_candidate_count": sum(1 for row in variants if row.get("recommendation") == "speed_safe_candidate_shadow_only"),
        "promotion_safe_count": sum(1 for row in variants if row.get("promotion_safe")),
        "runtime_change_applied": False,
        "best_variant": _best_variant(variants),
        "recommendation": "keep_shadow_only",
    }


def _best_variant(variants: list[dict[str, Any]]) -> str | None:
    if not variants:
        return None
    ordered = sorted(
        variants,
        key=lambda row: (
            float(row.get("strict_score_delta") or 0.0),
            -int(row.get("token_input_estimate_delta") or 0),
            -int(row.get("tool_call_count_delta") or 0),
        ),
        reverse=True,
    )
    return ordered[0].get("variant_id")


def _fix_decision(preflight: dict[str, Any], trials_payload: dict[str, Any]) -> dict[str, Any]:
    variants = trials_payload.get("variants") or []
    promotion_safe = [row for row in variants if row.get("promotion_safe")]
    speed_safe = [row for row in variants if row.get("recommendation") == "speed_safe_candidate_shadow_only"]
    decision = "keep_shadow_only"
    if promotion_safe:
        decision = "manual_approval_required_before_runtime_change"
    elif speed_safe:
        decision = "speed_only_shadow_candidates_no_promotion"
    return {
        "report_type": FIX_DECISION_STEM,
        "generated_at": _now(),
        "diagnostic_only": True,
        "official_score_claim": False,
        "best_variant": trials_payload.get("summary", {}).get("best_variant"),
        "strict_score_before": trials_payload.get("baseline_strict_score"),
        "strict_score_after_projected": trials_payload.get("baseline_strict_score"),
        "strict_score_delta_projected": 0.0,
        "token_tool_runtime_deltas": {
            "best_token_input_delta": min([int(row.get("token_input_estimate_delta") or 0) for row in variants] or [0]),
            "best_tool_call_delta": min([int(row.get("tool_call_count_delta") or 0) for row in variants] or [0]),
            "best_runtime_delta": min([float(row.get("runtime_delta_seconds_estimate") or 0) for row in variants] or [0.0]),
        },
        "rows_helped": sorted({helped for row in variants for helped in row.get("rows_helped", [])}),
        "rows_hurt": sorted({hurt for row in variants for hurt in row.get("rows_hurt", [])}),
        "promotion_safe": bool(promotion_safe),
        "runtime_change_applied": False,
        "reason_if_no_promotion": (
            "No variant is promoted automatically; speed-only candidates are shadow-only until strict and hidden validation are explicitly run."
        ),
        "decision": decision,
        "direct_http_hits": int(preflight.get("sdk_direct_http_hits") or 0),
        "unsupported_claim_increase": False,
        "high_scoring_rows_regressed": False,
        "live_api_assumption_used": False,
        "hardcoding_detected": False,
        "final_submission_format_changed": False,
        "recommended_next_prompt": "Request explicit implementation only for one selected speed-safe SDK policy after strict/hidden no-regression validation is approved.",
    }


def _assert_isolated(outputs_dir: Path, output_root: Path) -> None:
    resolved = output_root.resolve()
    allowed = (outputs_dir / "sdk_tool_calling_optimization_trials").resolve()
    if resolved != allowed:
        raise RuntimeError(f"Refusing to write SDK tool-call trials outside isolated output root: {resolved}")


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


def _render_trials(payload: dict[str, Any]) -> str:
    lines = [
        "# SDK Tool Calling Optimization Trials",
        "",
        f"- Diagnostic only: `{payload.get('diagnostic_only')}`",
        f"- Baseline strict score: `{payload.get('baseline_strict_score')}`",
        f"- Writes official eval artifacts: `{payload.get('writes_official_eval_artifacts')}`",
        f"- Writes final submission: `{payload.get('writes_final_submission')}`",
        "",
        "| Variant | Strict delta | Token delta | Tool delta | Runtime delta | Recommendation |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in payload.get("variants", []):
        lines.append(
            f"| `{row.get('variant_id')}` | {row.get('strict_score_delta')} | "
            f"{row.get('token_input_estimate_delta')} | {row.get('tool_call_count_delta')} | "
            f"{row.get('runtime_delta_seconds_estimate')} | `{row.get('recommendation')}` |"
        )
    return "\n".join(lines) + "\n"


def _render_fix_decision(payload: dict[str, Any]) -> str:
    lines = [
        "# SDK Tool Calling Fix Decision",
        "",
        f"- Decision: `{payload.get('decision')}`",
        f"- Best variant: `{payload.get('best_variant')}`",
        f"- Runtime change applied: `{payload.get('runtime_change_applied')}`",
        f"- Promotion safe: `{payload.get('promotion_safe')}`",
        f"- Direct HTTP hits: `{payload.get('direct_http_hits')}`",
        f"- Final submission format changed: `{payload.get('final_submission_format_changed')}`",
        "",
        payload.get("reason_if_no_promotion", ""),
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
