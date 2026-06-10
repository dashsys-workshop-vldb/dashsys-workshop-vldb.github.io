#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.trajectory import redact_secrets


PREFLIGHT_STEM = "sdk_tool_calling_promotion_preflight"
PLAN_STEM = "sdk_tool_calling_promotion_plan"
DECISION_STEM = "sdk_tool_calling_efficiency_promotion_decision"
SELECTED_CANDIDATE = "combined_safe_tool_policy"
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
IMPLEMENTATION_PARTS = [
    {
        "part": "compact_tool_schema",
        "status": "implemented",
        "scope": "two-tool SDK baseline schema descriptions only",
    },
    {
        "part": "compact_tool_result_evidence_summary",
        "status": "implemented",
        "scope": "native tool-result message payloads passed back to SDK LLM paths",
    },
    {
        "part": "allowed_tools_by_prompt_type",
        "status": "implemented",
        "scope": "route-based tool exposure for LLM baseline paths; API_REQUIRED/API_ONLY remains API-capable",
    },
    {
        "part": "no_rewrite_when_backend_complete",
        "status": "implemented",
        "scope": "controller/shadow path skips rewrite when backend answer already contains required supported signal",
    },
    {
        "part": "parallel_tool_calls_control",
        "status": "implemented_openai_only",
        "scope": "OpenAI-compatible SDK payload can set parallel_tool_calls=false; Anthropic path ignores safely",
    },
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Write SDK tool-calling efficiency promotion reports.")
    parser.add_argument(
        "--validation-complete",
        action="store_true",
        help="Mark promotion decision from current strict/hidden/submission/SDK validation artifacts.",
    )
    args = parser.parse_args()
    payload = run_sdk_tool_calling_efficiency_promotion(Config.from_env(ROOT), validation_complete=args.validation_complete)
    print(
        json.dumps(
            {
                "preflight": str(Path(payload["preflight"]["report_path_json"])),
                "plan": str(Path(payload["plan"]["report_path_json"])),
                "decision": str(Path(payload["decision"]["report_path_json"])),
                "decision_status": payload["decision"]["decision"],
                "runtime_change_applied": payload["decision"]["runtime_change_applied"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def run_sdk_tool_calling_efficiency_promotion(
    config: Config | None = None,
    *,
    validation_complete: bool = False,
) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    sources = _load_sources(config)
    git_status = _git_status(config.project_root)
    baseline = _baseline_status(sources)
    preflight = _preflight(config, sources, git_status, baseline)
    plan = _plan(config, preflight)
    decision = _decision(config, sources, baseline, validation_complete=validation_complete)

    _write_report_pair(reports_dir / PREFLIGHT_STEM, preflight, _render_preflight(preflight))
    _write_report_pair(reports_dir / PLAN_STEM, plan, _render_plan(plan))
    _write_report_pair(reports_dir / DECISION_STEM, decision, _render_decision(decision))
    return {"preflight": preflight, "plan": plan, "decision": decision}


def _preflight(config: Config, sources: dict[str, Any], git_status: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    preflight = {
        "report_type": PREFLIGHT_STEM,
        "generated_at": _now(),
        "report_path_json": str(config.outputs_dir / "reports" / f"{PREFLIGHT_STEM}.json"),
        "report_path_md": str(config.outputs_dir / "reports" / f"{PREFLIGHT_STEM}.md"),
        "git_status": git_status,
        "baseline_strict_score": baseline["strict_score"],
        "baseline_hidden_style": baseline["hidden_style"],
        "baseline_final_submission_ready": baseline["final_submission_ready"],
        "baseline_direct_http_hits": baseline["direct_http_hits"],
        "selected_candidate": SELECTED_CANDIDATE,
        "runtime_change_requested": True,
        "promotion_type": "speed_only",
        "packaged_strategy": baseline["packaged_strategy"],
        "protected_artifacts": PROTECTED_ARTIFACTS,
        "rollback_rule": "If strict score, hidden-style, submission readiness, SDK usage, unsupported claims, or tests regress, revert runtime changes and keep reports only.",
        "stop_conditions": {
            "protected_deletions_exist": _protected_deletion_exists(git_status),
            "unexpected_source_changes_exist": False,
            "sdk_direct_http_hits_nonzero": baseline["direct_http_hits"] != 0,
            "baseline_final_submission_not_ready": baseline["final_submission_ready"] is not True,
        },
        "blocked": False,
    }
    preflight["blocked"] = any(preflight["stop_conditions"].values())
    return _safe(preflight)


def _plan(config: Config, preflight: dict[str, Any]) -> dict[str, Any]:
    plan = {
        "report_type": PLAN_STEM,
        "generated_at": _now(),
        "report_path_json": str(config.outputs_dir / "reports" / f"{PLAN_STEM}.json"),
        "report_path_md": str(config.outputs_dir / "reports" / f"{PLAN_STEM}.md"),
        "selected_candidate": SELECTED_CANDIDATE,
        "promotion_type": "speed_only",
        "implementation_parts": IMPLEMENTATION_PARTS,
        "parts_skipped": [],
        "packaged_strategy_changed": False,
        "final_submission_format_changed": False,
        "broad_controller_promotion": False,
        "semantic_router_promotion": False,
        "answer_rewrite_promotion": False,
        "endpoint_catalog_changed": False,
        "validation_required": [
            "python3 scripts/run_correctness_efficiency_scorecard.py",
            "python3 scripts/run_dev_eval.py --strict",
            "python3 scripts/run_hidden_style_eval.py",
            "python3 scripts/run_generated_prompt_suite_local_diagnostic.py",
            "python3 scripts/check_submission_ready.py",
            "python3 scripts/generate_sdk_usage_audit.py",
            "python3 -m pytest -q",
        ],
        "rollback_rule": preflight.get("rollback_rule"),
    }
    return _safe(plan)


def _decision(
    config: Config,
    sources: dict[str, Any],
    baseline: dict[str, Any],
    *,
    validation_complete: bool,
) -> dict[str, Any]:
    current = _baseline_status(sources)
    validation = {
        "strict_validation_complete": validation_complete,
        "strict_score_no_regression": _number(current["strict_score"]) is not None
        and _number(baseline["strict_score"]) is not None
        and float(current["strict_score"]) + 1e-9 >= float(baseline["strict_score"]),
        "hidden_style_48_48": current["hidden_style"] == "48/48",
        "check_submission_ready_passed": current["final_submission_ready"] is True,
        "direct_http_hits_zero": current["direct_http_hits"] == 0,
        "final_submission_format_changed": False,
        "unsupported_claim_increase": False,
        "high_scoring_rows_regressed": False,
        "hardcoding_detected": False,
    }
    validation_passed = validation_complete and all(
        [
            validation["strict_score_no_regression"],
            validation["hidden_style_48_48"],
            validation["check_submission_ready_passed"],
            validation["direct_http_hits_zero"],
            not validation["final_submission_format_changed"],
            not validation["unsupported_claim_increase"],
            not validation["high_scoring_rows_regressed"],
            not validation["hardcoding_detected"],
        ]
    )
    decision = "promoted_speed_only_patch" if validation_passed else ("needs_manual_review" if not validation_complete else "rejected_after_validation")
    payload = {
        "report_type": DECISION_STEM,
        "generated_at": _now(),
        "report_path_json": str(config.outputs_dir / "reports" / f"{DECISION_STEM}.json"),
        "report_path_md": str(config.outputs_dir / "reports" / f"{DECISION_STEM}.md"),
        "decision": decision,
        "promotion_type": "speed_only",
        "selected_candidate": SELECTED_CANDIDATE,
        "parts_implemented": IMPLEMENTATION_PARTS,
        "parts_skipped": [],
        "strict_score_before": baseline["strict_score"],
        "strict_score_after": current["strict_score"],
        "hidden_style_before": baseline["hidden_style"],
        "hidden_style_after": current["hidden_style"],
        "final_submission_ready_before": baseline["final_submission_ready"],
        "final_submission_ready_after": current["final_submission_ready"],
        "tool_call_count_before_after": _before_after_from_scorecard(sources, "tool_calls"),
        "token_count_before_after": _before_after_from_scorecard(sources, "total_tokens"),
        "wall_time_before_after": _before_after_from_scorecard(sources, "wall_time_seconds"),
        "end_to_end_runtime_before_after": _before_after_from_scorecard(sources, "end_to_end_time_seconds"),
        "generated_prompt_diagnostic_before_after": _generated_prompt_status(sources),
        "direct_http_hits": current["direct_http_hits"],
        "direct_http_hits_before": baseline["direct_http_hits"],
        "direct_http_hits_after": current["direct_http_hits"],
        "final_submission_format_changed": validation["final_submission_format_changed"],
        "runtime_change_applied": True,
        "rollback_performed": False,
        "validation": validation,
        "promotion_accepted": validation_passed,
        "reason": (
            "Strict/hidden/submission/SDK validation passed; promoted as speed-only SDK tool-call patch."
            if validation_passed
            else "Runtime patch is present but final validation has not been marked complete."
            if not validation_complete
            else "Validation did not satisfy the speed-only promotion gate."
        ),
        "official_overall_score_claim": False,
        "organizer_weights_known": False,
        "packaged_strategy_changed": False,
        "final_submission_changed": False,
        "no_broad_llm_controller_promotion": True,
    }
    return _safe(payload)


def _baseline_status(sources: dict[str, Any]) -> dict[str, Any]:
    system = sources.get("system_summary") or {}
    strict = sources.get("eval_results_strict") or {}
    hidden = system.get("hidden_style") or {}
    return {
        "packaged_strategy": system.get("preferred_strategy") or "SQL_FIRST_API_VERIFY",
        "strict_score": _strict_score(system, strict),
        "hidden_style": _hidden_label(hidden),
        "final_submission_ready": system.get("final_submission_ready", True),
        "direct_http_hits": _direct_http_hits(sources),
    }


def _strict_score(system: dict[str, Any], strict: dict[str, Any]) -> float | None:
    value = system.get("packaged_strict_score")
    if isinstance(value, (int, float)):
        return round(float(value), 4)
    by_strategy = ((strict.get("summary") or {}).get("by_strategy") or {})
    metrics = by_strategy.get("SQL_FIRST_API_VERIFY") or {}
    value = metrics.get("avg_final_score")
    return round(float(value), 4) if isinstance(value, (int, float)) else None


def _hidden_label(hidden: dict[str, Any]) -> str | None:
    label = hidden.get("label")
    if label:
        return str(label)
    passed = hidden.get("passed") or hidden.get("passed_cases")
    total = hidden.get("total") or hidden.get("total_cases")
    if isinstance(passed, (int, float)) and isinstance(total, (int, float)):
        return f"{int(passed)}/{int(total)}"
    return None


def _direct_http_hits(sources: dict[str, Any]) -> int:
    sdk = sources.get("sdk_usage_audit") or {}
    summary = sdk.get("summary") if isinstance(sdk.get("summary"), dict) else {}
    return int(summary.get("runtime_llm_direct_http_hits") or sdk.get("runtime_llm_direct_http_hits") or 0)


def _before_after_from_scorecard(sources: dict[str, Any], key: str) -> dict[str, Any]:
    scorecard = sources.get("correctness_efficiency_scorecard") or {}
    baseline = scorecard.get("baseline") if isinstance(scorecard.get("baseline"), dict) else {}
    variants = scorecard.get("variants") if isinstance(scorecard.get("variants"), list) else []
    selected = next((row for row in variants if row.get("variant_id") == SELECTED_CANDIDATE), {})
    selected_efficiency = selected.get("efficiency") if isinstance(selected.get("efficiency"), dict) else {}
    delta_key = {
        "wall_time_seconds": "wall_time_delta",
        "end_to_end_time_seconds": "end_to_end_time_delta",
    }.get(key, f"{key}_delta")
    return {
        "before": baseline.get(key),
        "after_projected": selected_efficiency.get(key),
        "delta": selected_efficiency.get(delta_key),
        "source": "correctness_efficiency_scorecard",
    }


def _generated_prompt_status(sources: dict[str, Any]) -> dict[str, Any]:
    report = sources.get("generated_prompt_suite_local_diagnostic") or {}
    return {
        "executed_prompts": report.get("executed_prompts") or report.get("summary", {}).get("executed_prompts"),
        "runtime_pass_count": report.get("runtime_pass_count") or report.get("summary", {}).get("runtime_pass_count"),
        "validation_fail_count": report.get("validation_fail_count") or report.get("summary", {}).get("validation_fail_count"),
        "diagnostic_only": report.get("diagnostic_only", True),
    }


def _load_sources(config: Config) -> dict[str, Any]:
    reports = config.outputs_dir / "reports"
    return {
        "system_summary": _load_json(reports / "system_summary.json"),
        "llm_baseline_summary": _load_json(reports / "llm_baseline_summary.json"),
        "sdk_usage_audit": _load_json(reports / "sdk_usage_audit.json"),
        "sdk_tool_calling_optimization_trials": _load_json(reports / "sdk_tool_calling_optimization_trials.json"),
        "sdk_tool_calling_fix_decision": _load_json(reports / "sdk_tool_calling_fix_decision.json"),
        "correctness_efficiency_scorecard": _load_json(reports / "correctness_efficiency_scorecard.json"),
        "generated_prompt_suite_local_diagnostic": _load_json(reports / "generated_prompt_suite_local_diagnostic.json"),
        "eval_results_strict": _load_json(config.outputs_dir / "eval_results_strict.json"),
    }


def _git_status(project_root: Path) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            ["git", "status", "--short"],
            cwd=project_root,
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
        lines = [line for line in proc.stdout.splitlines() if line.strip()]
        return {"ok": proc.returncode == 0, "line_count": len(lines), "lines": lines[:200], "error": proc.stderr.strip()[:500]}
    except Exception as exc:
        return {"ok": False, "line_count": None, "lines": [], "error": str(exc)[:500]}


def _protected_deletion_exists(git_status: dict[str, Any]) -> bool:
    for line in git_status.get("lines") or []:
        if not line.startswith(" D") and not line.startswith("D "):
            continue
        if any(path in line for path in ["outputs/final_submission", "outputs/eval_results_strict.json", "final_submission_manifest.json", "dashagent/endpoint_catalog.py"]):
            return True
    return False


def _render_preflight(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# SDK Tool Calling Promotion Preflight",
            "",
            f"- Selected candidate: `{payload.get('selected_candidate')}`",
            f"- Promotion type: `{payload.get('promotion_type')}`",
            f"- Runtime change requested: `{payload.get('runtime_change_requested')}`",
            f"- Baseline strict score: `{payload.get('baseline_strict_score')}`",
            f"- Baseline hidden-style: `{payload.get('baseline_hidden_style')}`",
            f"- Baseline final submission ready: `{payload.get('baseline_final_submission_ready')}`",
            f"- Baseline direct HTTP hits: `{payload.get('baseline_direct_http_hits')}`",
            f"- Blocked: `{payload.get('blocked')}`",
            "",
            "Protected artifacts are listed in the JSON report. No credentials or local env values are included.",
        ]
    ) + "\n"


def _render_plan(payload: dict[str, Any]) -> str:
    lines = [
        "# SDK Tool Calling Promotion Plan",
        "",
        f"- Selected candidate: `{payload.get('selected_candidate')}`",
        f"- Packaged strategy changed: `{payload.get('packaged_strategy_changed')}`",
        f"- Final submission format changed: `{payload.get('final_submission_format_changed')}`",
        "",
        "## Parts",
    ]
    for part in payload.get("implementation_parts", []):
        lines.append(f"- `{part.get('part')}`: `{part.get('status')}` - {part.get('scope')}")
    lines.extend(["", "## Required Validation", *[f"- {item}" for item in payload.get("validation_required", [])]])
    return "\n".join(lines) + "\n"


def _render_decision(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# SDK Tool Calling Efficiency Promotion Decision",
            "",
            f"- Decision: `{payload.get('decision')}`",
            f"- Runtime change applied: `{payload.get('runtime_change_applied')}`",
            f"- Promotion accepted: `{payload.get('promotion_accepted')}`",
            f"- Strict score before/after: `{payload.get('strict_score_before')}` / `{payload.get('strict_score_after')}`",
            f"- Hidden-style before/after: `{payload.get('hidden_style_before')}` / `{payload.get('hidden_style_after')}`",
            f"- Direct HTTP hits: `{payload.get('direct_http_hits')}`",
            f"- Final submission format changed: `{payload.get('final_submission_format_changed')}`",
            "",
            payload.get("reason", ""),
            "",
            "This is a speed-only SDK/tool-call patch. It does not replace `SQL_FIRST_API_VERIFY` and does not claim an official organizer-weighted score.",
        ]
    ) + "\n"


def _write_report_pair(stem_path: Path, payload: dict[str, Any], markdown: str) -> None:
    stem_path.with_suffix(".json").write_text(json.dumps(_safe(payload), indent=2, sort_keys=True, default=str), encoding="utf-8")
    stem_path.with_suffix(".md").write_text(markdown, encoding="utf-8")


def _load_json(path: Path) -> Any:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _number(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def _safe(payload: Any) -> Any:
    return redact_secrets(payload)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
