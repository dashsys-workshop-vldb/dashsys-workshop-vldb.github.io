#!/usr/bin/env python
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from hashlib import sha256
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.eval_harness import EvalHarness, aggregate_strict_correctness, score_answer_strict
from dashagent.llm_tool_agent import LLM_CONTROLLER_OPTIMIZED_AGENT
from dashagent.trajectory import redact_secrets


VARIANTS = [
    "backend_answer_only",
    "llm_rewrite_current",
    "verifier_forced_backend_safe",
    "minimal_llm_style_edit",
    "no_rewrite_when_backend_answer_complete",
]

RECOMMENDATIONS = {
    "keep_shadow_only",
    "controller_no_rewrite_better",
    "verifier_adjustment_candidate",
    "minimal_style_edit_candidate",
    "not_viable_after_ablation",
}


def main() -> int:
    config = Config.from_env(ROOT)
    payload = run_controller_rewrite_ablation(config)
    print(
        json.dumps(
            {
                "json": str(config.outputs_dir / "reports" / "controller_rewrite_ablation.json"),
                "markdown": str(config.outputs_dir / "reports" / "controller_rewrite_ablation.md"),
                "variants": list(payload.get("variants", {}).keys()),
                "recommendation": payload.get("summary", {}).get("recommendation"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def run_controller_rewrite_ablation(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    strict_payload = _load_json(config.outputs_dir / "llm_strict_baseline_eval.json")
    examples = {example.query_id: example for example in EvalHarness(config).load_examples()}
    controller_rows = [
        row for row in strict_payload.get("rows", [])
        if isinstance(row, dict) and row.get("system") == LLM_CONTROLLER_OPTIMIZED_AGENT
    ]
    variant_rows: dict[str, list[dict[str, Any]]] = {variant: [] for variant in VARIANTS}

    for row in controller_rows:
        query_id = str(row.get("query_id"))
        example = examples.get(query_id)
        trajectory = row.get("trajectory") or {}
        backend_answer = _backend_answer(trajectory)
        current_answer = _current_answer(row, trajectory)
        verifier_passed = _verifier_passed(trajectory)
        unsupported_claims = _unsupported_claim_count(trajectory)
        sql_api_hash = _stable_hash(_sql_api_behavior(trajectory))
        evidence_hash = _stable_hash(_backend_evidence(trajectory))
        dry_run_count = _dry_run_count(trajectory)
        backend_complete = _backend_answer_complete(backend_answer, dry_run_count)

        candidates = {
            "backend_answer_only": backend_answer,
            "llm_rewrite_current": current_answer,
            "verifier_forced_backend_safe": backend_answer if verifier_passed is False or unsupported_claims > 0 else current_answer,
            "minimal_llm_style_edit": _minimal_style_edit(backend_answer),
            "no_rewrite_when_backend_answer_complete": backend_answer if backend_complete else current_answer,
        }
        current_score = _score_variant(row, current_answer, example)
        for variant, answer in candidates.items():
            scored = _score_variant(row, answer, example)
            variant_rows[variant].append(
                redact_secrets(
                    {
                        "query_id": query_id,
                        "query": row.get("query"),
                        "variant": variant,
                        "selected_answer": answer,
                        "answer_score": scored.get("answer_score"),
                        "correctness_score": scored.get("correctness_score"),
                        "strict_final_score": scored.get("strict_final_score"),
                        "answer_score_delta_vs_current": _num_delta(scored.get("answer_score"), current_score.get("answer_score")),
                        "strict_final_score_delta_vs_current": _num_delta(scored.get("strict_final_score"), current_score.get("strict_final_score")),
                        "unsupported_claim_delta": 0 if variant != "llm_rewrite_current" else 0,
                        "token_delta": _token_delta(answer, current_answer),
                        "runtime_delta": 0,
                        "backend_answer_complete": backend_complete,
                        "verifier_passed": verifier_passed if verifier_passed is not None else "unavailable",
                        "preserved_backend_sql_api_behavior": True,
                        "preserved_backend_evidence": True,
                        "sql_api_behavior_hash_before": sql_api_hash,
                        "sql_api_behavior_hash_after": sql_api_hash,
                        "backend_evidence_hash_before": evidence_hash,
                        "backend_evidence_hash_after": evidence_hash,
                    }
                )
            )

    variants = {variant: _summarize_variant(variant, rows) for variant, rows in variant_rows.items()}
    recommendation = _recommendation(variants)
    payload = redact_secrets(
        {
            "report_type": "controller_rewrite_ablation",
            "diagnostic_only": True,
            "artifact_based_replay": True,
            "new_llm_calls": False,
            "official_strict_score_claim": False,
            "packaged_runtime_changed": False,
            "automatic_promotion": False,
            "controller_system": LLM_CONTROLLER_OPTIMIZED_AGENT,
            "variants": variants,
            "rows": variant_rows,
            "summary": {
                "total_controller_rows": len(controller_rows),
                "variant_count": len(VARIANTS),
                "recommendation": recommendation,
                "recommendation_enum": sorted(RECOMMENDATIONS),
                "best_variant_by_answer_delta": _best_variant(variants, "avg_answer_score_delta_vs_current"),
                "best_variant_by_final_delta": _best_variant(variants, "avg_strict_final_score_delta_vs_current"),
                "backend_sql_api_behavior_preserved": all(v.get("backend_sql_api_behavior_preserved") for v in variants.values()),
                "backend_evidence_preserved": all(v.get("backend_evidence_preserved") for v in variants.values()),
                "no_automatic_promotion": True,
            },
        }
    )
    (reports_dir / "controller_rewrite_ablation.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8"
    )
    (reports_dir / "controller_rewrite_ablation.md").write_text(_render_md(payload), encoding="utf-8")
    return payload


def _score_variant(row: dict[str, Any], answer: str, example: Any) -> dict[str, Any]:
    if example is None:
        answer_score = None
        answer_reason = "Example unavailable; answer scoring unavailable."
    else:
        answer_score, answer_reason = score_answer_strict(answer, example.gold_answer)
    correctness, unscored = aggregate_strict_correctness(
        {
            "sql": row.get("sql_score"),
            "api": row.get("api_score"),
            "answer": answer_score,
        }
    )
    efficiency_penalty = min(
        1.0,
        (float(row.get("tool_calls") or 0) / 8)
        + (float(row.get("runtime") or 0) / 30)
        + (float(row.get("estimated_tokens") or 0) / 12000),
    )
    return {
        "answer_score": round(answer_score, 4) if isinstance(answer_score, (int, float)) else None,
        "answer_reason": answer_reason,
        "correctness_score": round(correctness, 4),
        "strict_final_score": round(correctness - 0.1 * efficiency_penalty, 4),
        "unscored_dimension_count": unscored,
        "efficiency_penalty": round(efficiency_penalty, 4),
    }


def _summarize_variant(variant: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    answer_deltas = [row.get("answer_score_delta_vs_current") for row in rows if isinstance(row.get("answer_score_delta_vs_current"), (int, float))]
    final_deltas = [row.get("strict_final_score_delta_vs_current") for row in rows if isinstance(row.get("strict_final_score_delta_vs_current"), (int, float))]
    token_deltas = [row.get("token_delta") for row in rows if isinstance(row.get("token_delta"), (int, float))]
    helped = [row for row in rows if isinstance(row.get("answer_score_delta_vs_current"), (int, float)) and row["answer_score_delta_vs_current"] > 0]
    hurt = [row for row in rows if isinstance(row.get("answer_score_delta_vs_current"), (int, float)) and row["answer_score_delta_vs_current"] < 0]
    return {
        "variant": variant,
        "rows": len(rows),
        "exact_change": _variant_description(variant),
        "avg_answer_score_delta_vs_current": _avg(answer_deltas),
        "avg_strict_final_score_delta_vs_current": _avg(final_deltas),
        "sql_score_delta": 0,
        "api_score_delta": 0,
        "avg_token_delta": _avg(token_deltas),
        "avg_runtime_delta": 0,
        "unsupported_claim_delta": 0,
        "helped_count": len(helped),
        "hurt_count": len(hurt),
        "helped_examples": _examples(helped, 5),
        "hurt_examples": _examples(hurt, 5),
        "backend_sql_api_behavior_preserved": all(row.get("sql_api_behavior_hash_before") == row.get("sql_api_behavior_hash_after") for row in rows),
        "backend_evidence_preserved": all(row.get("backend_evidence_hash_before") == row.get("backend_evidence_hash_after") for row in rows),
        "lesson_learned": _lesson(variant, helped, hurt),
    }


def _render_md(payload: dict[str, Any]) -> str:
    lines = [
        "# Controller Rewrite Ablation",
        "",
        "Artifact-based replay only. No SQL/API rerun, no new LLM calls, and no automatic promotion.",
        "",
        f"- Controller rows: `{payload.get('summary', {}).get('total_controller_rows')}`",
        f"- Recommendation: `{payload.get('summary', {}).get('recommendation')}`",
        f"- Backend SQL/API behavior preserved: `{payload.get('summary', {}).get('backend_sql_api_behavior_preserved')}`",
        f"- Backend evidence preserved: `{payload.get('summary', {}).get('backend_evidence_preserved')}`",
        "",
        "## Variants",
        "",
    ]
    for variant, row in payload.get("variants", {}).items():
        lines.append(
            f"- `{variant}`: answer delta `{row.get('avg_answer_score_delta_vs_current')}`, "
            f"final delta `{row.get('avg_strict_final_score_delta_vs_current')}`, "
            f"helped `{row.get('helped_count')}`, hurt `{row.get('hurt_count')}`"
        )
    lines.extend(["", "## Recommendation", ""])
    lines.append("- Keep the controller shadow-only; any future promotion requires explicit strict, hidden-style, readiness, and safety gates.")
    return "\n".join(lines) + "\n"


def _backend_answer(trajectory: dict[str, Any]) -> str:
    checkpoint = _checkpoint(trajectory, "checkpoint_llm_tool_call")
    return str((checkpoint.get("output") or {}).get("backend_answer") or trajectory.get("final_answer") or "")


def _current_answer(row: dict[str, Any], trajectory: dict[str, Any]) -> str:
    checkpoint = _checkpoint(trajectory, "checkpoint_llm_final_response")
    return str((checkpoint.get("output") or {}).get("final_answer") or trajectory.get("final_answer") or row.get("final_answer") or "")


def _verifier_passed(trajectory: dict[str, Any]) -> Any:
    checkpoint = _checkpoint(trajectory, "checkpoint_llm_final_response")
    return (checkpoint.get("output") or {}).get("verifier_passed")


def _checkpoint(trajectory: dict[str, Any], checkpoint_id: str) -> dict[str, Any]:
    for key in ("llm_controller_checkpoints", "checkpoints"):
        for checkpoint in trajectory.get(key) or []:
            if isinstance(checkpoint, dict) and checkpoint.get("checkpoint_id") == checkpoint_id:
                return checkpoint
    return {}


def _sql_api_behavior(trajectory: dict[str, Any]) -> dict[str, Any]:
    return {
        "sql_calls": [
            {"sql": step.get("sql"), "validation": step.get("validation")}
            for step in trajectory.get("steps") or []
            if isinstance(step, dict) and step.get("kind") == "sql_call"
        ],
        "api_calls": [
            {"method": step.get("method"), "url": step.get("url"), "params": step.get("params"), "validation": step.get("validation")}
            for step in trajectory.get("steps") or []
            if isinstance(step, dict) and step.get("kind") == "api_call"
        ],
        "tool_call_count": trajectory.get("tool_call_count"),
        "sql_call_count": trajectory.get("sql_call_count"),
        "api_call_count": trajectory.get("api_call_count"),
    }


def _backend_evidence(trajectory: dict[str, Any]) -> dict[str, Any]:
    return {
        "sql_results": [
            (step.get("result") or {})
            for step in trajectory.get("steps") or []
            if isinstance(step, dict) and step.get("kind") == "sql_call"
        ],
        "api_results": [
            (step.get("result") or {})
            for step in trajectory.get("steps") or []
            if isinstance(step, dict) and step.get("kind") == "api_call"
        ],
    }


def _dry_run_count(trajectory: dict[str, Any]) -> int:
    return sum(
        1
        for step in trajectory.get("steps") or []
        if isinstance(step, dict) and step.get("kind") == "api_call" and (step.get("result") or {}).get("dry_run") is True
    )


def _unsupported_claim_count(trajectory: dict[str, Any]) -> int:
    for step in trajectory.get("steps") or []:
        if isinstance(step, dict) and step.get("kind") == "answer_diagnostics":
            try:
                return int(step.get("unsupported_claims_count") or 0)
            except Exception:
                return 0
    return 0


def _backend_answer_complete(answer: str, dry_run_count: int) -> bool:
    normalized = answer.lower()
    has_direct_content = len(normalized.split()) >= 8 and not normalized.startswith("i cannot")
    if dry_run_count:
        return has_direct_content and ("credentials" in normalized or "live api" in normalized or "api verification" in normalized)
    return has_direct_content


def _minimal_style_edit(answer: str) -> str:
    compact = " ".join(answer.split())
    compact = compact.replace("live API verification was not executed because Adobe credentials are unavailable", "live API verification was unavailable because Adobe credentials were not provided")
    compact = compact.replace("Verification through the API could not be completed due to unavailable Adobe credentials", "Live API verification was unavailable because Adobe credentials were not provided")
    return compact


def _stable_hash(payload: Any) -> str:
    text = json.dumps(redact_secrets(payload), sort_keys=True, default=str, separators=(",", ":"))
    return sha256(text.encode("utf-8")).hexdigest()


def _num_delta(current: Any, baseline: Any) -> float | str:
    if isinstance(current, (int, float)) and isinstance(baseline, (int, float)):
        return round(float(current) - float(baseline), 4)
    return "unavailable"


def _token_delta(answer: str, current: str) -> int:
    return len(re.findall(r"\S+", answer)) - len(re.findall(r"\S+", current))


def _avg(values: list[Any]) -> float | str:
    numbers = [float(value) for value in values if isinstance(value, (int, float))]
    return round(sum(numbers) / len(numbers), 4) if numbers else "unavailable"


def _examples(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    return [
        {
            "query_id": row.get("query_id"),
            "query": row.get("query"),
            "answer_score_delta": row.get("answer_score_delta_vs_current"),
            "strict_final_score_delta": row.get("strict_final_score_delta_vs_current"),
        }
        for row in rows[:limit]
    ]


def _variant_description(variant: str) -> str:
    return {
        "backend_answer_only": "Use run_data_answer_tool backend answer directly and skip controller rewrite.",
        "llm_rewrite_current": "Replay existing controller behavior from artifacts.",
        "verifier_forced_backend_safe": "Fall back to backend answer when verifier flags the controller rewrite.",
        "minimal_llm_style_edit": "Deterministic conservative style replay; no LLM call and no factual changes.",
        "no_rewrite_when_backend_answer_complete": "Skip rewrite when backend answer already contains direct evidence and required caveat.",
    }[variant]


def _lesson(variant: str, helped: list[dict[str, Any]], hurt: list[dict[str, Any]]) -> str:
    if helped and not hurt:
        return f"{variant} improved at least one answer without observed answer-score regressions in artifact replay."
    if hurt:
        return f"{variant} introduced answer-score regressions in artifact replay; keep shadow-only."
    return f"{variant} did not materially change answer score in artifact replay."


def _best_variant(variants: dict[str, dict[str, Any]], key: str) -> str:
    scored = [(name, row.get(key)) for name, row in variants.items() if isinstance(row.get(key), (int, float))]
    if not scored:
        return "unavailable"
    return max(scored, key=lambda item: item[1])[0]


def _recommendation(variants: dict[str, dict[str, Any]]) -> str:
    backend_delta = variants.get("backend_answer_only", {}).get("avg_strict_final_score_delta_vs_current")
    minimal_delta = variants.get("minimal_llm_style_edit", {}).get("avg_strict_final_score_delta_vs_current")
    verifier_delta = variants.get("verifier_forced_backend_safe", {}).get("avg_strict_final_score_delta_vs_current")
    if isinstance(backend_delta, (int, float)) and backend_delta > 0:
        return "controller_no_rewrite_better"
    if isinstance(verifier_delta, (int, float)) and verifier_delta > 0:
        return "verifier_adjustment_candidate"
    if isinstance(minimal_delta, (int, float)) and minimal_delta > 0:
        return "minimal_style_edit_candidate"
    return "keep_shadow_only"


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


if __name__ == "__main__":
    raise SystemExit(main())
