#!/usr/bin/env python
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.eval_harness import EvalHarness, aggregate_strict_correctness, score_answer_strict
from dashagent.llm_tool_agent import LLM_CONTROLLER_OPTIMIZED_AGENT
from dashagent.trajectory import redact_secrets


LOSS_CATEGORIES = {
    "router_loss",
    "backend_evidence_loss",
    "llm_rewrite_loss",
    "verifier_loss",
    "answer_scorer_mismatch",
    "dry_run_caveat_loss",
    "no_clear_loss",
    "controller_helped",
}


def main() -> int:
    config = Config.from_env(ROOT)
    payload = run_llm_controller_failure_decomposition(config)
    print(
        json.dumps(
            {
                "json": str(config.outputs_dir / "reports" / "llm_controller_failure_decomposition.json"),
                "markdown": str(config.outputs_dir / "reports" / "llm_controller_failure_decomposition.md"),
                "controller_rows": payload.get("summary", {}).get("total_controller_rows"),
                "recommendation": payload.get("summary", {}).get("safest_next_controller_improvement"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def run_llm_controller_failure_decomposition(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    strict_payload = _load_json(config.outputs_dir / "llm_strict_baseline_eval.json")
    baseline_payload = _load_json(config.outputs_dir / "llm_baseline_eval.json")
    deterministic_rows = _deterministic_rows(config)
    examples = {example.query_id: example for example in EvalHarness(config).load_examples()}
    baseline_rows = {
        (str(row.get("query_id")), str(row.get("system"))): row
        for row in baseline_payload.get("rows", [])
        if isinstance(row, dict)
    }

    rows: list[dict[str, Any]] = []
    for strict_row in strict_payload.get("rows", []):
        if strict_row.get("system") != LLM_CONTROLLER_OPTIMIZED_AGENT:
            continue
        query_id = str(strict_row.get("query_id"))
        source_row = baseline_rows.get((query_id, LLM_CONTROLLER_OPTIMIZED_AGENT), {})
        rows.append(_decompose_row(config, strict_row, source_row, deterministic_rows.get(query_id, {}), examples.get(query_id)))

    summary = _summary(rows, strict_payload)
    payload = redact_secrets(
        {
            "report_type": "llm_controller_failure_decomposition",
            "diagnostic_only": True,
            "official_strict_score_computed": False,
            "promotion_status": "shadow_only",
            "automatic_promotion": False,
            "controller_system": LLM_CONTROLLER_OPTIMIZED_AGENT,
            "source_files": [
                "outputs/llm_baseline_eval.json",
                "outputs/llm_strict_baseline_eval.json",
                "outputs/eval_results_strict.json",
            ],
            "loss_category_enum": sorted(LOSS_CATEGORIES),
            "summary": summary,
            "rows": rows,
        }
    )
    (reports_dir / "llm_controller_failure_decomposition.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8"
    )
    (reports_dir / "llm_controller_failure_decomposition.md").write_text(_render_md(payload), encoding="utf-8")
    return payload


def _decompose_row(
    config: Config,
    strict_row: dict[str, Any],
    source_row: dict[str, Any],
    deterministic: dict[str, Any],
    example: Any,
) -> dict[str, Any]:
    trajectory = strict_row.get("trajectory") or source_row.get("trajectory") or {}
    controller_decision = _checkpoint(trajectory, "checkpoint_llm_controller_decision")
    tool_call = _checkpoint(trajectory, "checkpoint_llm_tool_call")
    final_response = _checkpoint(trajectory, "checkpoint_llm_final_response")

    decision_output = controller_decision.get("output") or {}
    tool_output = tool_call.get("output") or {}
    final_output = final_response.get("output") or {}

    backend_answer = str(tool_output.get("backend_answer") or "")
    final_answer = str(final_output.get("final_answer") or strict_row.get("trajectory", {}).get("final_answer") or source_row.get("final_answer") or "")
    backend_answer_score, backend_answer_reason = _score_answer(backend_answer, example)
    final_answer_score = strict_row.get("answer_score")
    rewrite_delta = _num_delta(final_answer_score, backend_answer_score)
    sql_steps = _steps(trajectory, "sql_call")
    api_steps = _steps(trajectory, "api_call")
    dry_run_count = sum(1 for step in api_steps if (step.get("result") or {}).get("dry_run") is True)
    route_mode = str(decision_output.get("mode") or trajectory.get("route_type") or "UNKNOWN")
    deterministic_route = deterministic.get("route_type") or _deterministic_route_from_output_dir(config, deterministic)
    deterministic_delta = strict_row.get("delta_vs_sql_first_api_verify") or {}
    verifier_passed = final_output.get("verifier_passed")
    loss_category = _classify_loss(
        strict_row,
        deterministic_delta,
        route_mode,
        deterministic_route,
        rewrite_delta,
        verifier_passed,
        dry_run_count,
    )
    instrumentation_gap = "proposed_llm_final_answer" not in final_output

    return redact_secrets(
        {
            "query_id": strict_row.get("query_id"),
            "query": strict_row.get("query"),
            "loss_category": loss_category,
            "instrumentation_gap": instrumentation_gap,
            "router_decision": {
                "route_mode": route_mode,
                "requires_database": bool(decision_output.get("requires_database")),
                "requires_api": bool(decision_output.get("requires_api")),
                "llm_direct_used": route_mode == "LLM_DIRECT",
                "confidence": decision_output.get("confidence"),
                "reason": decision_output.get("reason"),
                "deterministic_sql_first_route": deterministic_route or "unavailable",
                "matches_deterministic_route": _matches_route(route_mode, deterministic_route),
            },
            "backend_tool_result": {
                "backend_used": bool(backend_answer),
                "backend_final_answer": backend_answer or "unavailable",
                "sql_calls": len(sql_steps),
                "api_calls": len(api_steps),
                "tool_call_count": tool_output.get("tool_call_count", strict_row.get("tool_calls")),
                "sql_score": strict_row.get("sql_score"),
                "api_score": strict_row.get("api_score"),
                "backend_answer_score": backend_answer_score,
                "backend_answer_reason": backend_answer_reason,
                "evidence_available": bool(sql_steps or api_steps),
                "dry_run_count": dry_run_count,
                "dry_run_state": "dry_run_unavailable" if dry_run_count else strict_row.get("dry_run_live_evidence_status", "live_or_sql_only"),
            },
            "llm_rewrite_result": {
                "proposed_llm_final_answer": "unavailable_from_existing_artifact",
                "final_controller_answer": final_answer or "unavailable",
                "llm_changed_backend_answer": _normalize_answer(final_answer) != _normalize_answer(backend_answer),
                "rewrite_answer_score_delta_vs_backend": rewrite_delta,
                "rewrite_improved_answer_score": isinstance(rewrite_delta, (int, float)) and rewrite_delta > 0,
                "rewrite_hurt_answer_score": isinstance(rewrite_delta, (int, float)) and rewrite_delta < 0,
                "unsupported_claims": _unsupported_claim_count(trajectory),
                "removed_useful_evidence_heuristic": _removed_useful_evidence(backend_answer, final_answer),
            },
            "verifier_behavior": {
                "verifier_passed": verifier_passed if verifier_passed is not None else "unavailable",
                "safer_rewritten_answer_used": "unavailable_from_existing_artifact",
                "prevented_hallucination": False,
                "over_corrected": verifier_passed is False and _score_is_low(final_answer_score),
                "under_corrected": verifier_passed is True and _score_is_low(final_answer_score),
            },
            "score_breakdown": {
                "strict_final_score": strict_row.get("strict_final_score"),
                "strict_correctness": strict_row.get("strict_correctness"),
                "answer_score": strict_row.get("answer_score"),
                "sql_score": strict_row.get("sql_score"),
                "api_score": strict_row.get("api_score"),
                "delta_vs_sql_first_api_verify": deterministic_delta,
                "estimated_tokens": strict_row.get("estimated_tokens"),
                "runtime": strict_row.get("runtime"),
                "tool_calls": strict_row.get("tool_calls"),
            },
        }
    )


def _summary(rows: list[dict[str, Any]], strict_payload: dict[str, Any]) -> dict[str, Any]:
    counts = Counter(row.get("loss_category", "no_clear_loss") for row in rows)
    rewrite_hurt = [row for row in rows if row.get("llm_rewrite_result", {}).get("rewrite_hurt_answer_score")]
    verifier_helped = [row for row in rows if row.get("verifier_behavior", {}).get("prevented_hallucination")]
    verifier_hurt = [row for row in rows if row.get("verifier_behavior", {}).get("over_corrected")]
    answer_bottleneck = [
        row for row in rows
        if _score_is_low(row.get("score_breakdown", {}).get("answer_score"))
        and not _score_is_low(row.get("score_breakdown", {}).get("sql_score"))
    ]
    backend_matches = [
        row for row in rows
        if row.get("router_decision", {}).get("matches_deterministic_route") is True
        and row.get("score_breakdown", {}).get("delta_vs_sql_first_api_verify", {}).get("sql_score") in {0, 0.0}
    ]
    helped = [row for row in rows if row.get("loss_category") == "controller_helped"]
    hurt = [row for row in rows if row.get("loss_category") != "controller_helped"][:8]
    return {
        "total_controller_rows": len(rows),
        "controller_strict_score": _controller_score(strict_payload),
        "deterministic_preferred": True,
        "loss_category_distribution": dict(counts),
        "rows_where_backend_evidence_matched_deterministic": len(backend_matches),
        "rows_where_llm_rewrite_hurt_answer": len(rewrite_hurt),
        "rows_where_verifier_helped": len(verifier_helped),
        "rows_where_verifier_hurt": len(verifier_hurt),
        "rows_where_answer_score_is_main_bottleneck": len(answer_bottleneck),
        "instrumentation_gap_count": sum(1 for row in rows if row.get("instrumentation_gap")),
        "examples_helped": _example_slice(helped, 5),
        "examples_hurt": _example_slice(hurt, 8),
        "safest_next_controller_improvement": _next_improvement(counts, rewrite_hurt, answer_bottleneck),
        "automatic_promotion": False,
    }


def _render_md(payload: dict[str, Any]) -> str:
    summary = payload.get("summary", {})
    lines = [
        "# LLM Controller Failure Decomposition",
        "",
        "Diagnostic-only decomposition. The controller remains shadow-only and is not promoted automatically.",
        "",
        f"- Controller rows: `{summary.get('total_controller_rows')}`",
        f"- Controller strict score: `{summary.get('controller_strict_score')}`",
        f"- Instrumentation gap count: `{summary.get('instrumentation_gap_count')}`",
        f"- Safest next controller improvement: `{summary.get('safest_next_controller_improvement')}`",
        "",
        "## Loss Category Distribution",
        "",
    ]
    for key, value in sorted((summary.get("loss_category_distribution") or {}).items()):
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Examples Hurt", ""])
    for row in summary.get("examples_hurt", []):
        lines.append(f"- `{row.get('query_id')}` `{row.get('loss_category')}`: {row.get('query')}")
    lines.extend(["", "## Instrumentation Note", ""])
    lines.append("- Raw pre-verifier proposed LLM answers are unavailable in existing artifacts; no runtime was rerun for this report.")
    return "\n".join(lines) + "\n"


def _checkpoint(trajectory: dict[str, Any], checkpoint_id: str) -> dict[str, Any]:
    for key in ("llm_controller_checkpoints", "checkpoints"):
        for checkpoint in trajectory.get(key) or []:
            if isinstance(checkpoint, dict) and checkpoint.get("checkpoint_id") == checkpoint_id:
                return checkpoint
    return {}


def _steps(trajectory: dict[str, Any], kind: str) -> list[dict[str, Any]]:
    return [step for step in trajectory.get("steps") or [] if isinstance(step, dict) and step.get("kind") == kind]


def _score_answer(answer: str, example: Any) -> tuple[float | None, str]:
    if example is None:
        return None, "Example unavailable; answer scoring unavailable."
    try:
        return score_answer_strict(answer, example.gold_answer)
    except Exception as exc:
        return None, f"Answer scoring unavailable: {type(exc).__name__}"


def _classify_loss(
    row: dict[str, Any],
    delta: dict[str, Any],
    route_mode: str,
    deterministic_route: str | None,
    rewrite_delta: Any,
    verifier_passed: Any,
    dry_run_count: int,
) -> str:
    final_delta = delta.get("final_score")
    if isinstance(final_delta, (int, float)) and final_delta > 0:
        return "controller_helped"
    if route_mode == "LLM_DIRECT" or _matches_route(route_mode, deterministic_route) is False:
        return "router_loss"
    sql_score = row.get("sql_score")
    api_score = row.get("api_score")
    if _score_is_low(sql_score) or (api_score is not None and _score_is_low(api_score)) or int(row.get("validation_failures") or 0) > 0:
        return "backend_evidence_loss"
    if isinstance(rewrite_delta, (int, float)) and rewrite_delta < -0.001:
        return "llm_rewrite_loss"
    if verifier_passed is False and _score_is_low(row.get("answer_score")):
        return "verifier_loss"
    if dry_run_count and _score_is_low(row.get("answer_score")):
        return "dry_run_caveat_loss"
    if _score_is_low(row.get("answer_score")):
        return "answer_scorer_mismatch"
    return "no_clear_loss"


def _deterministic_rows(config: Config) -> dict[str, dict[str, Any]]:
    data = _load_json(config.outputs_dir / "eval_results_strict.json")
    rows = data.get("rows", []) if isinstance(data, dict) else []
    return {str(row.get("query_id")): row for row in rows if row.get("strategy") == "SQL_FIRST_API_VERIFY"}


def _deterministic_route_from_output_dir(config: Config, row: dict[str, Any]) -> str | None:
    out_dir = row.get("output_dir")
    if not out_dir:
        return None
    path = Path(out_dir)
    if not path.is_absolute():
        path = config.project_root / path
    try:
        trajectory = json.loads((path / "trajectory.json").read_text(encoding="utf-8"))
        return trajectory.get("route_type")
    except Exception:
        return None


def _matches_route(route: str | None, deterministic_route: str | None) -> bool | str:
    if not route or not deterministic_route:
        return "unavailable"
    return str(route).upper() == str(deterministic_route).upper()


def _num_delta(current: Any, baseline: Any) -> float | str:
    if isinstance(current, (int, float)) and isinstance(baseline, (int, float)):
        return round(float(current) - float(baseline), 4)
    return "unavailable"


def _score_is_low(value: Any) -> bool:
    return isinstance(value, (int, float)) and float(value) < 0.5


def _normalize_answer(answer: str) -> str:
    return " ".join(answer.lower().split())


def _unsupported_claim_count(trajectory: dict[str, Any]) -> int:
    for step in trajectory.get("steps") or []:
        if isinstance(step, dict) and step.get("kind") == "answer_diagnostics":
            try:
                return int(step.get("unsupported_claims_count") or 0)
            except Exception:
                return 0
    return 0


def _removed_useful_evidence(backend_answer: str, final_answer: str) -> bool:
    backend_tokens = set(_evidence_tokens(backend_answer))
    final_tokens = set(_evidence_tokens(final_answer))
    return bool(backend_tokens - final_tokens)


def _evidence_tokens(answer: str) -> list[str]:
    import re

    return re.findall(r"\b(?:[A-Z][A-Za-z0-9_-]{2,}|[0-9]{2,}|20\d{2}-\d{2}-\d{2}|published|draft|active|failed|succeeded|null)\b", answer)


def _controller_score(strict_payload: dict[str, Any]) -> Any:
    for row in strict_payload.get("per_strategy") or []:
        if row.get("system") == LLM_CONTROLLER_OPTIMIZED_AGENT:
            return row.get("strict_final_score")
    return "unavailable"


def _example_slice(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    return [
        {
            "query_id": row.get("query_id"),
            "query": row.get("query"),
            "loss_category": row.get("loss_category"),
            "answer_score": row.get("score_breakdown", {}).get("answer_score"),
            "final_delta": row.get("score_breakdown", {}).get("delta_vs_sql_first_api_verify", {}).get("final_score"),
        }
        for row in rows[:limit]
    ]


def _next_improvement(counts: Counter[str], rewrite_hurt: list[dict[str, Any]], answer_bottleneck: list[dict[str, Any]]) -> str:
    if rewrite_hurt:
        return "Run backend-vs-LLM rewrite ablation; test no-rewrite and minimal style-edit controller variants."
    if answer_bottleneck:
        return "Focus on answer evidence usage and verifier calibration before any controller promotion."
    if counts.get("router_loss"):
        return "Keep routing deterministic-first; controller routing remains shadow-only."
    return "Keep controller shadow-only; no safe promotion candidate from current artifacts."


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


if __name__ == "__main__":
    raise SystemExit(main())
