#!/usr/bin/env python
from __future__ import annotations

import copy
import hashlib
import json
import shutil
import argparse
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.answer_faithfulness import evaluate_answer_faithfulness
from dashagent.answer_intent import classify_answer_intent
from dashagent.answer_slots import extract_answer_slots
from dashagent.config import Config
from dashagent.eval_harness import EvalHarness
from dashagent.evidence_aware_answer_templates import compose_evidence_aware_answer
from dashagent.executor import AgentExecutor
from dashagent.report_run import report_metadata
from dashagent.supportable_answer_rewriter import canonical_plan_hashes
from dashagent.token_reduction_policy import official_estimated_tokens
from dashagent.trajectory import redact_secrets
from scripts.package_query_outputs import required_trajectory_fields_present
from scripts.run_official_token_reduction_eval import _dry_run_labels, _load_json, _load_trajectory, _score_result


OUTPUT_NAME = "evidence_aware_answer_rewrite_trial"
PREFLIGHT_BLOCKER_NAME = "evidence_answer_synthesis_preflight_blocker"
VARIANTS = [
    "direct_first_templates",
    "dry_run_minimal_caveat",
    "intent_specific_templates",
    "evidence_source_aware_templates",
    "conservative_rewrite_only",
]
REPORT_VARIANT_NAMES = {
    1: "direct_first_templates",
    2: "dry_run_minimal_caveat",
    3: "intent_specific_templates",
    4: "evidence_source_aware_templates",
    5: "conservative_rewrite_only",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run isolated evidence-aware answer-only rewrite trials.")
    parser.add_argument("--limit", type=int, default=0, help="Limit public/dev rows considered per variant. 0 means all rows.")
    parser.add_argument("--full", action="store_true", help="Consider all available SQL_FIRST_API_VERIFY rows.")
    parser.add_argument("--clean", action="store_true", help="Remove only the isolated rewrite-trial output root before running.")
    args = parser.parse_args()
    config = Config.from_env(ROOT)
    payload = run_evidence_aware_answer_rewrite_trial(
        config,
        limit=0 if args.full else args.limit,
        clean=args.clean,
    )
    print(json.dumps({"status": payload["status"], "rows_rewritten": payload["summary"]["rows_rewritten"]}, indent=2, sort_keys=True))
    return 0


def run_evidence_aware_answer_rewrite_trial(
    config: Config | None = None,
    *,
    limit: int = 0,
    clean: bool = True,
) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    blocker = protected_deletion_preflight(config)
    if blocker.get("blocked"):
        _write_report(reports_dir / PREFLIGHT_BLOCKER_NAME, blocker, _render_preflight_blocker(blocker))
        return {
            **blocker,
            "report_type": OUTPUT_NAME,
            "status": "blocked",
            "summary": {"rows_rewritten": 0, "rows_considered": 0, "rows_rejected": 0},
        }

    output_root = config.outputs_dir / OUTPUT_NAME
    _assert_isolated(config.outputs_dir, output_root)
    if clean and output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)

    strict = _load_json(config.outputs_dir / "eval_results_strict.json")
    if not strict.get("rows"):
        payload = _skipped_trial_report(config, output_root, "missing outputs/eval_results_strict.json rows")
        _write_report(reports_dir / OUTPUT_NAME, payload, _render_trial(payload))
        return payload
    executor = AgentExecutor(config)
    examples = {example.query_id: example for example in EvalHarness(config).load_examples()}
    strict_rows = [row for row in strict.get("rows", []) if row.get("strategy") == "SQL_FIRST_API_VERIFY"]
    if limit and limit > 0:
        strict_rows = strict_rows[:limit]
    all_rows: list[dict[str, Any]] = []
    iteration_reports: list[dict[str, Any]] = []
    for index, variant in enumerate(VARIANTS, start=1):
        rows = [_evaluate_row(config, executor, output_root, strict_row, examples.get(str(strict_row.get("query_id"))), variant) for strict_row in strict_rows]
        all_rows.extend(rows)
        iteration = _iteration_report(index, variant, rows, strict)
        iteration_reports.append(iteration)
        _write_report(reports_dir / f"feedback_loop_answer_synthesis_iteration_{index}", iteration, _render_iteration(iteration))

    final = _final_report(iteration_reports)
    _write_report(reports_dir / "feedback_loop_answer_synthesis_final", final, _render_final(final))
    payload = _trial_report(all_rows, iteration_reports, final, strict, output_root)
    _write_report(reports_dir / OUTPUT_NAME, payload, _render_trial(payload))
    return payload


def protected_deletion_preflight(config: Config) -> dict[str, Any]:
    deleted = _tracked_deletions(config.project_root, ["outputs/final_submission", "outputs/source_code"])
    final_deletions = [path for path in deleted if path.startswith("outputs/final_submission/")]
    source_deletions = [path for path in deleted if path.startswith("outputs/source_code/")]
    blocked = bool(final_deletions or source_deletions)
    return {
        "report_type": PREFLIGHT_BLOCKER_NAME,
        "status": "blocked" if blocked else "pass",
        "blocked": blocked,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "implementation_started": not blocked,
        "source_files_modified_by_this_pass": False if blocked else None,
        "protected_deletions": {
            "outputs/final_submission": final_deletions,
            "outputs/source_code": source_deletions,
        },
        "protected_deletion_counts": {
            "outputs/final_submission": len(final_deletions),
            "outputs/source_code": len(source_deletions),
        },
        "recommended_fix": "Restore protected tracked artifacts from HEAD before running evidence-aware answer synthesis."
        if blocked
        else "No protected tracked deletions detected.",
    }


def _tracked_deletions(project_root: Path, paths: list[str]) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "status", "--short", "--", *paths],
            cwd=project_root,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except Exception:
        return []
    deleted: list[str] = []
    for line in result.stdout.splitlines():
        status = line[:2]
        path = line[3:].strip()
        if "D" in status and path:
            deleted.append(path)
    return deleted


def _evaluate_row(
    config: Config,
    executor: AgentExecutor,
    output_root: Path,
    strict_row: dict[str, Any],
    example: Any,
    variant: str,
) -> dict[str, Any]:
    query_id = str(strict_row.get("query_id") or "")
    query = str(strict_row.get("query") or "")
    baseline = _load_trajectory(strict_row.get("output_dir"))
    tool_results = tool_results_from_trajectory(baseline)
    slots = extract_answer_slots(query, tool_results)
    api_required = _api_required(baseline)
    baseline_faith = evaluate_answer_faithfulness(str(baseline.get("final_answer") or ""), slots)
    template = compose_evidence_aware_answer(
        query,
        tool_results,
        variant=variant,
        baseline_answer=str(baseline.get("final_answer") or ""),
        api_required=api_required,
    )
    candidate = copy.deepcopy(baseline)
    candidate["final_answer"] = template.answer
    candidate["estimated_tokens"] = official_estimated_tokens(candidate)
    candidate_faith = evaluate_answer_faithfulness(template.answer, slots)

    baseline_hashes = _invariant_hashes(baseline, query)
    candidate_hashes = _invariant_hashes(candidate, query)
    invariant_checks = {key: baseline_hashes[key] == candidate_hashes[key] for key in baseline_hashes}
    plan_hash = _plan_hash_check(baseline, candidate)
    scores = _score_result(executor, candidate, template.answer, example) if example else _no_scores()
    baseline_score = float(strict_row.get("final_score") or 0.0)
    baseline_answer_score = float(strict_row.get("answer_score") or 0.0)
    rejection_reasons = _rejection_reasons(
        invariant_checks,
        plan_hash,
        baseline_faith,
        candidate_faith,
        api_required=api_required,
        slots=slots,
        template=template,
    )
    output_dir = output_root / variant / query_id
    _assert_isolated(config.outputs_dir, output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "metadata.json").write_text(json.dumps({"query_id": query_id, "query": query, "variant": variant, "answer_only": True}, indent=2, sort_keys=True), encoding="utf-8")
    (output_dir / "filled_system_prompt.txt").write_text("Evidence-aware answer rewrite trial. SQL/API/tool execution unchanged.\n", encoding="utf-8")
    (output_dir / "trajectory.json").write_text(json.dumps(candidate, indent=2, sort_keys=True, default=str), encoding="utf-8")
    row = {
        "query_id": query_id,
        "query": query,
        "variant": variant,
        "answer_intent": str(classify_answer_intent(query, slots)),
        "baseline_final_answer": baseline.get("final_answer"),
        "candidate_final_answer": template.answer,
        "template": template.to_dict(),
        "baseline_score": round(baseline_score, 4),
        "candidate_score": scores["final_score"],
        "score_delta": round(float(scores["final_score"]) - baseline_score, 4),
        "baseline_answer_score": strict_row.get("answer_score"),
        "candidate_answer_score": scores["answer_score"],
        "answer_score_delta": round(float(scores["answer_score"] or 0.0) - baseline_answer_score, 4),
        "sql_score_delta": 0.0 if plan_hash["sql_hash_unchanged"] else None,
        "api_score_delta": 0.0 if plan_hash["api_hash_unchanged"] else None,
        "baseline_tokens": int(strict_row.get("estimated_tokens") or baseline.get("estimated_tokens") or 0),
        "candidate_tokens": int(candidate.get("estimated_tokens") or 0),
        "token_delta": int(candidate.get("estimated_tokens") or 0) - int(strict_row.get("estimated_tokens") or baseline.get("estimated_tokens") or 0),
        "runtime_delta": 0.0,
        "baseline_tool_calls": int(strict_row.get("tool_call_count") or baseline.get("tool_call_count") or 0),
        "candidate_tool_calls": int(candidate.get("tool_call_count") or 0),
        "tool_delta": int(candidate.get("tool_call_count") or 0) - int(strict_row.get("tool_call_count") or baseline.get("tool_call_count") or 0),
        "baseline_faithfulness_score": baseline_faith.faithfulness_score,
        "candidate_faithfulness_score": candidate_faith.faithfulness_score,
        "faithfulness_delta": round(candidate_faith.faithfulness_score - baseline_faith.faithfulness_score, 4),
        "baseline_unsupported_claim_count": len(baseline_faith.unsupported_claims),
        "candidate_unsupported_claim_count": len(candidate_faith.unsupported_claims),
        "unsupported_claim_delta": len(candidate_faith.unsupported_claims) - len(baseline_faith.unsupported_claims),
        "baseline_directness_score": _directness_score(str(baseline.get("final_answer") or ""), slots),
        "candidate_directness_score": _directness_score(template.answer, slots),
        "directness_delta": round(_directness_score(template.answer, slots) - _directness_score(str(baseline.get("final_answer") or ""), slots), 4),
        "required_fields_preserved": required_trajectory_fields_present(candidate),
        "invariant_checks": invariant_checks,
        "plan_hashes": plan_hash,
        "baseline_hashes": baseline_hashes,
        "candidate_hashes": candidate_hashes,
        "baseline_faithfulness": baseline_faith.to_dict(),
        "candidate_faithfulness": candidate_faith.to_dict(),
        "safe_for_limited_promotion_trial": not rejection_reasons,
        "rejected": bool(rejection_reasons),
        "rejection_reasons": rejection_reasons,
        "output_dir": str(output_dir),
    }
    return redact_secrets(row)


def tool_results_from_trajectory(trajectory: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for step in trajectory.get("steps", []):
        if step.get("kind") == "sql_call":
            results.append({"type": "sql", "step": step, "payload": step.get("result") or {}})
        elif step.get("kind") == "api_call":
            results.append({"type": "api", "step": step, "payload": step.get("result") or {}})
    return results


def selected_evidence_hash(trajectory: dict[str, Any], query: str = "") -> str:
    tool_results = tool_results_from_trajectory(trajectory)
    slots = extract_answer_slots(query or str(trajectory.get("original_query") or ""), tool_results)
    evidence_bus = None
    checkpoint_slots = None
    for checkpoint in trajectory.get("checkpoints", []):
        if checkpoint.get("checkpoint_id") == "checkpoint_14_evidence_bus":
            evidence_bus = _decompact(checkpoint.get("output", {}).get("evidence"))
        elif checkpoint.get("checkpoint_id") == "checkpoint_15_answer_slots":
            checkpoint_slots = _decompact(checkpoint.get("output", {}).get("slots"))
    payload = {
        "sql_result_facts": [_sql_fact(result.get("payload") or {}) for result in tool_results if result.get("type") == "sql"],
        "api_result_facts": [_api_fact(result.get("payload") or {}) for result in tool_results if result.get("type") == "api"],
        "evidence_bus": evidence_bus,
        "answer_slots": slots.compact(),
        "checkpoint_answer_slots": checkpoint_slots,
        "dry_run_labels": _dry_run_labels(trajectory),
    }
    return _sha(payload)


def _invariant_hashes(trajectory: dict[str, Any], query: str) -> dict[str, Any]:
    plan = canonical_plan_hashes(trajectory)
    return {
        "sql_hash": plan["sql_hash"],
        "api_hash": plan["api_hash"],
        "tool_count": int(trajectory.get("tool_call_count") or 0),
        "route": trajectory.get("route_type"),
        "plan_hash": _sha([_stable(step) for step in trajectory.get("steps", []) if step.get("kind") in {"plan", "optimizer"}]),
        "selected_evidence_hash": selected_evidence_hash(trajectory, query),
        "dry_run_label_hash": _sha(_dry_run_labels(trajectory)),
    }


def _plan_hash_check(baseline: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    base = canonical_plan_hashes(baseline)
    cand = canonical_plan_hashes(candidate)
    return {
        "baseline_sql_hash": base["sql_hash"],
        "candidate_sql_hash": cand["sql_hash"],
        "baseline_api_hash": base["api_hash"],
        "candidate_api_hash": cand["api_hash"],
        "sql_hash_unchanged": base["sql_hash"] == cand["sql_hash"],
        "api_hash_unchanged": base["api_hash"] == cand["api_hash"],
        "tool_call_count_unchanged": int(baseline.get("tool_call_count") or 0) == int(candidate.get("tool_call_count") or 0),
    }


def _rejection_reasons(
    invariant_checks: dict[str, bool],
    plan_hash: dict[str, Any],
    baseline_faith: Any,
    candidate_faith: Any,
    *,
    api_required: bool,
    slots: Any,
    template: Any,
) -> list[str]:
    failures: list[str] = []
    for key, ok in invariant_checks.items():
        if not ok:
            failures.append(f"{key}_changed")
    for key in ["sql_hash_unchanged", "api_hash_unchanged", "tool_call_count_unchanged"]:
        if plan_hash.get(key) is not True:
            failures.append(key.replace("_unchanged", "_changed"))
    if len(candidate_faith.unsupported_claims) > len(baseline_faith.unsupported_claims):
        failures.append("unsupported_claims_increased")
    if api_required and slots.dry_run and not template.required_caveat_present:
        failures.append("api_required_dry_run_caveat_removed")
    return list(dict.fromkeys(failures))


def _iteration_report(index: int, variant: str, rows: list[dict[str, Any]], strict: dict[str, Any]) -> dict[str, Any]:
    safe = [row for row in rows if row.get("safe_for_limited_promotion_trial")]
    helped = [row for row in rows if float(row.get("answer_score_delta") or 0.0) > 0 and not row.get("rejected")]
    hurt = [row for row in rows if float(row.get("answer_score_delta") or 0.0) < 0 or row.get("rejection_reasons")]
    baseline = _baseline_score(strict)
    projected = round(baseline + sum(float(row.get("score_delta") or 0.0) for row in safe) / max(1, _strict_count(strict)), 4)
    outcome = _outcome(projected - baseline, helped, hurt)
    return {
        "report_type": "feedback_loop_answer_synthesis_iteration",
        "iteration": index,
        "variant": variant,
        "exact_change": _variant_change(variant),
        "rows_considered": len(rows),
        "rows_rewritten": len(safe),
        "rows_rejected": len(rows) - len(safe),
        "baseline_strict_score": baseline,
        "projected_strict_score": projected,
        "strict_score_delta": round(projected - baseline, 4),
        "answer_score_delta": _avg(row.get("answer_score_delta") for row in safe),
        "sql_score_delta": 0.0,
        "api_score_delta": 0.0,
        "faithfulness_delta": _avg(row.get("faithfulness_delta") for row in safe),
        "unsupported_claim_delta": sum(int(row.get("unsupported_claim_delta") or 0) for row in safe),
        "token_delta": _avg(row.get("token_delta") for row in safe),
        "runtime_delta": 0.0,
        "helped_examples": _examples(helped),
        "hurt_examples": _examples(hurt),
        "rejected_rewrite_reasons": dict(Counter(reason for row in rows for reason in row.get("rejection_reasons", []))),
        "lesson_learned": _lesson(variant, helped, hurt),
        "next_action": "continue_to_next_variant" if index < len(VARIANTS) else "write_final_decision",
        "outcome_classification": outcome,
        "no_automatic_promotion": True,
    }


def _final_report(iterations: list[dict[str, Any]]) -> dict[str, Any]:
    best = max(iterations, key=lambda item: float(item.get("strict_score_delta") or 0.0), default={})
    strict_improved = float(best.get("strict_score_delta") or 0.0) > 0
    promotion_gates = {
        "strict_score_improved": strict_improved,
        "hidden_style_48_48": "not_evaluated_by_this_trial",
        "check_submission_ready_passed": "not_evaluated_by_this_trial",
        "unsupported_claim_increase": sum(int(item.get("unsupported_claim_delta") or 0) for item in iterations),
        "invariant_sql_api_tool_evidence_hashes": True,
    }
    partial_useful = any(item.get("outcome_classification") == "candidate_partially_useful" for item in iterations)
    recommendation = "keep_trial_only" if strict_improved else ("locally_useful_but_not_promotable" if partial_useful else "keep_trial_only")
    if not any(item.get("rows_rewritten") for item in iterations):
        recommendation = "do_not_promote"
    return {
        "report_type": "feedback_loop_answer_synthesis_final",
        "candidate_name": "Evidence-Aware Answer Synthesis",
        "iteration_count": len(iterations),
        "best_variant": best.get("variant"),
        "best_strict_score_delta": best.get("strict_score_delta"),
        "worst_strict_score_delta": min((float(item.get("strict_score_delta") or 0.0) for item in iterations), default=0.0),
        "iterations": iterations,
        "final_recommendation": recommendation,
        "promotion_performed": False,
        "packaged_runtime_changed": False,
        "promotion_gate_status": promotion_gates,
        "promotion_requirements": [
            "strict score improvement",
            "hidden-style 48/48",
            "check_submission_ready pass",
            "no unsupported claim increase",
            "invariant SQL/API/tool/evidence hashes",
        ],
    }


def _trial_report(rows: list[dict[str, Any]], iterations: list[dict[str, Any]], final: dict[str, Any], strict: dict[str, Any], output_root: Path) -> dict[str, Any]:
    safe = [row for row in rows if row.get("safe_for_limited_promotion_trial")]
    return {
        **report_metadata(output_root.parents[0]),
        "report_type": OUTPUT_NAME,
        "status": "complete",
        "answer_only_trial": True,
        "isolated_output_root": str(output_root),
        "writes_eval_outputs": False,
        "writes_final_submission": False,
        "official_score_claim": False,
        "baseline_strict_score": _baseline_score(strict),
        "total_rows_considered": len(rows),
        "rows_rewritten": len(safe),
        "rows_rejected": len(rows) - len(safe),
        "iteration_reports": [f"outputs/reports/feedback_loop_answer_synthesis_iteration_{idx}.md" for idx in range(1, len(iterations) + 1)],
        "final_feedback_loop_report": "outputs/reports/feedback_loop_answer_synthesis_final.md",
        "summary": {
            "rows_considered": len(rows),
            "rows_rewritten": len(safe),
            "rows_rejected": len(rows) - len(safe),
            "best_variant": final.get("best_variant"),
            "best_strict_score_delta": final.get("best_strict_score_delta"),
            "recommendation": final.get("final_recommendation"),
            "sql_api_score_delta": 0.0,
            "unsupported_claim_delta": sum(int(row.get("unsupported_claim_delta") or 0) for row in safe),
        },
        "rows": rows,
        "final_decision": final,
    }


def _skipped_trial_report(config: Config, output_root: Path, reason: str) -> dict[str, Any]:
    return {
        **report_metadata(config.outputs_dir),
        "report_type": OUTPUT_NAME,
        "status": "skipped",
        "skip_reason": reason,
        "answer_only_trial": True,
        "isolated_output_root": str(output_root),
        "writes_eval_outputs": False,
        "writes_final_submission": False,
        "official_score_claim": False,
        "summary": {
            "rows_considered": 0,
            "rows_rewritten": 0,
            "rows_rejected": 0,
            "best_variant": None,
            "best_strict_score_delta": None,
            "recommendation": "keep_trial_only",
            "sql_api_score_delta": 0.0,
            "unsupported_claim_delta": 0,
        },
        "rows": [],
    }


def _api_required(trajectory: dict[str, Any]) -> bool:
    for checkpoint in trajectory.get("checkpoints", []):
        if checkpoint.get("checkpoint_id") == "checkpoint_10_evidence_policy":
            return checkpoint.get("output", {}).get("mode") == "API_REQUIRED"
    return False


def _sql_fact(payload: dict[str, Any]) -> dict[str, Any]:
    return {"ok": payload.get("ok"), "row_count": payload.get("row_count"), "rows": _stable(payload.get("rows") or [])}


def _api_fact(payload: dict[str, Any]) -> dict[str, Any]:
    parsed = payload.get("parsed_evidence") if isinstance(payload, dict) else None
    return {
        "ok": payload.get("ok"),
        "dry_run": payload.get("dry_run"),
        "endpoint": payload.get("endpoint"),
        "error": payload.get("error"),
        "parsed_evidence": _stable(parsed or {}),
        "evidence_state": parsed.get("evidence_state") if isinstance(parsed, dict) else None,
    }


def _stable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _stable(val) for key, val in sorted(value.items()) if str(key) not in {"timestamp", "runtime", "duration_ms", "answer_time", "execution_time", "planning_time", "preprocessing_time"}}
    if isinstance(value, list):
        return [_stable(item) for item in value]
    return value


def _decompact(value: Any) -> Any:
    if isinstance(value, dict) and set(value) >= {"items", "total_items"}:
        return _decompact(value.get("items"))
    if isinstance(value, dict):
        return {key: _decompact(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_decompact(item) for item in value]
    return value


def _sha(value: Any) -> str:
    return hashlib.sha256(json.dumps(_stable(value), sort_keys=True, default=str).encode("utf-8")).hexdigest()


def _no_scores() -> dict[str, Any]:
    return {"sql_score": None, "api_score": None, "answer_score": None, "correctness_score": 0.0, "final_score": 0.0}


def _directness_score(answer: str, slots: Any) -> float:
    first = answer.split(".")[0].lower()
    if slots.counts and any(str(value).lower() in first for value in slots.counts):
        return 1.0
    if slots.entity_names and any(str(value).lower() in first for value in slots.entity_names[:3]):
        return 1.0
    if slots.statuses and any(str(value).lower() in first for value in slots.statuses[:3]):
        return 1.0
    if slots.timestamps and any(str(value).lower()[:10] in first for value in slots.timestamps[:3]):
        return 1.0
    if first.startswith(("you have", "matching", "yes", "no", "live api returned", "the sql query returned")):
        return 0.8
    return 0.4


def _baseline_score(strict: dict[str, Any]) -> float:
    return float(((strict.get("summary") or {}).get("by_strategy") or {}).get("SQL_FIRST_API_VERIFY", {}).get("avg_final_score") or 0.0)


def _strict_count(strict: dict[str, Any]) -> int:
    return len([row for row in strict.get("rows", []) if row.get("strategy") == "SQL_FIRST_API_VERIFY"]) or 1


def _avg(values: Any) -> float:
    nums = [float(value) for value in values if isinstance(value, (int, float))]
    return round(sum(nums) / len(nums), 4) if nums else 0.0


def _examples(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "query_id": row.get("query_id"),
            "query": row.get("query"),
            "baseline_answer": row.get("baseline_final_answer"),
            "candidate_answer": row.get("candidate_final_answer"),
            "answer_score_delta": row.get("answer_score_delta"),
            "rejection_reasons": row.get("rejection_reasons"),
        }
        for row in rows[:5]
    ]


def _outcome(strict_delta: float, helped: list[dict[str, Any]], hurt: list[dict[str, Any]]) -> str:
    if strict_delta > 0:
        return "candidate_eligible_for_future_limited_promotion"
    if helped and len(helped) >= len(hurt):
        return "candidate_partially_useful"
    return "variant_failed"


def _variant_change(variant: str) -> str:
    return {
        "direct_first_templates": "Put direct SQL/API-supported answer first; caveat second.",
        "dry_run_minimal_caveat": "Keep required dry-run caveat but shorten it.",
        "intent_specific_templates": "Use separate COUNT/LIST/STATUS/WHEN/YES_NO wording.",
        "evidence_source_aware_templates": "Choose wording based on SQL/live API/dry-run/api-error/live-empty state.",
        "conservative_rewrite_only": "Rewrite only when evidence is clearly complete; otherwise retain baseline wording.",
    }[variant]


def _lesson(variant: str, helped: list[dict[str, Any]], hurt: list[dict[str, Any]]) -> str:
    if helped and not hurt:
        return f"{variant} produced safe local improvements without recorded harms."
    if helped:
        return f"{variant} found some useful rewrites but still has rejected or risky rows."
    return f"{variant} did not produce safe score-positive answer-only rewrites under the current gates."


def _write_report(stem: Path, payload: dict[str, Any], markdown: str) -> None:
    stem.with_suffix(".json").write_text(json.dumps(redact_secrets(payload), indent=2, sort_keys=True, default=str), encoding="utf-8")
    stem.with_suffix(".md").write_text(markdown, encoding="utf-8")


def _render_iteration(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# Answer Synthesis Feedback Loop Iteration {payload['iteration']}",
            "",
            f"- Variant: `{payload['variant']}`",
            f"- Rows considered: `{payload['rows_considered']}`",
            f"- Rows rewritten: `{payload['rows_rewritten']}`",
            f"- Rows rejected: `{payload['rows_rejected']}`",
            f"- Strict delta: `{payload['strict_score_delta']}`",
            f"- Answer delta: `{payload['answer_score_delta']}`",
            f"- Outcome: `{payload['outcome_classification']}`",
            f"- No automatic promotion: `{payload['no_automatic_promotion']}`",
            "",
            "## Lesson",
            "",
            payload["lesson_learned"],
            "",
        ]
    )


def _render_final(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Answer Synthesis Feedback Loop Final",
            "",
            f"- Iterations: `{payload['iteration_count']}`",
            f"- Best variant: `{payload['best_variant']}`",
            f"- Best strict delta: `{payload['best_strict_score_delta']}`",
            f"- Recommendation: `{payload['final_recommendation']}`",
            f"- Promotion performed: `{payload['promotion_performed']}`",
            f"- Packaged runtime changed: `{payload['packaged_runtime_changed']}`",
            "",
        ]
    )


def _render_trial(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    return "\n".join(
        [
            "# Evidence-Aware Answer Rewrite Trial",
            "",
            f"- Rows considered: `{summary['rows_considered']}`",
            f"- Rows rewritten: `{summary['rows_rewritten']}`",
            f"- Rows rejected: `{summary['rows_rejected']}`",
            f"- Best variant: `{summary['best_variant']}`",
            f"- Best strict delta: `{summary['best_strict_score_delta']}`",
            f"- Recommendation: `{summary['recommendation']}`",
            f"- Writes eval outputs: `{payload['writes_eval_outputs']}`",
            f"- Writes final submission: `{payload['writes_final_submission']}`",
            f"- Official score claim: `{payload['official_score_claim']}`",
            "",
        ]
    )


def _render_preflight_blocker(payload: dict[str, Any]) -> str:
    counts = payload.get("protected_deletion_counts", {})
    protected = payload.get("protected_deletions", {})
    final_examples = protected.get("outputs/final_submission", [])[:10]
    source_examples = protected.get("outputs/source_code", [])[:10]
    lines = [
        "# Evidence-Aware Answer Synthesis Preflight Blocker",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Implementation started: `{payload.get('implementation_started')}`",
        f"- Source files modified by this pass: `{payload.get('source_files_modified_by_this_pass')}`",
        "",
        "Protected tracked deletions were detected, so the evidence-aware answer synthesis pass stopped before modifying source files.",
        "",
        "## Protected Deletions",
        "",
        f"- `outputs/final_submission/**`: `{counts.get('outputs/final_submission', 0)}` deleted files",
        f"- `outputs/source_code/**`: `{counts.get('outputs/source_code', 0)}` deleted files",
        "",
    ]
    if final_examples:
        lines.extend(["Final-submission deletion examples:", ""])
        lines.extend(f"- `{path}`" for path in final_examples)
        lines.append("")
    if source_examples:
        lines.extend(["Source-code deletion examples:", ""])
        lines.extend(f"- `{path}`" for path in source_examples)
        lines.append("")
    lines.extend(["## Action", "", str(payload.get("recommended_fix", "")), ""])
    return "\n".join(lines)


def _assert_isolated(outputs_dir: Path, path: Path) -> None:
    resolved = path.resolve()
    allowed = (outputs_dir / OUTPUT_NAME).resolve()
    if resolved == allowed or allowed in resolved.parents:
        return
    raise RuntimeError(f"Evidence-aware answer rewrite attempted to write outside isolated root: {path}")


if __name__ == "__main__":
    raise SystemExit(main())
