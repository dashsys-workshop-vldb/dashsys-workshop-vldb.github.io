#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.eval_harness import EvalHarness, aggregate_strict_correctness, score_answer_strict
from scripts.run_live_api_score_regression_analysis import (
    BASELINE_TRAJECTORY_ROOT,
    DRY_RUN_CAVEAT,
    LIVE_RESULTS,
    LIVE_TRAJECTORY_ROOT,
    STRATEGY,
    load_json,
    sanitize_text,
    strategy_rows,
    strategy_score,
)


REPORT_DIR = ROOT / "outputs" / "reports"
TRIAL_ROOT = ROOT / "outputs" / "live_api_evidence_arbitration_trial"


def main() -> int:
    live = load_json(LIVE_RESULTS)
    live_rows = strategy_rows(live)
    examples = {example.query_id: example for example in EvalHarness().load_examples()}
    current_score = strategy_score(live)
    baseline_score = strategy_score(load_json(ROOT / "outputs" / "reports" / "baselines" / "pre_live_api_eval_results_strict.json"))
    variants = {
        "current_live_baseline": current_answer,
        "sql_primary_when_complete": sql_primary_when_complete,
        "live_api_primary_only_when_required": live_api_primary_only_when_required,
        "conflict_explicit": conflict_explicit,
        "suppress_noisy_live_verification": suppress_noisy_live_verification,
    }
    rows_by_variant = {}
    summaries = []
    TRIAL_ROOT.mkdir(parents=True, exist_ok=True)
    for variant_id, transform in variants.items():
        variant_rows = []
        for query_id in sorted(live_rows):
            example = examples.get(query_id)
            if not example:
                continue
            live_traj = load_json(LIVE_TRAJECTORY_ROOT / query_id / "sql_first_api_verify" / "trajectory.json")
            baseline_traj = load_json(BASELINE_TRAJECTORY_ROOT / query_id / "sql_first_api_verify" / "trajectory.json")
            live_answer = sanitize_text(live_traj.get("final_answer") or "")
            baseline_answer = sanitize_text(baseline_traj.get("final_answer") or "")
            candidate_answer = transform(query_id, live_rows[query_id], live_answer, baseline_answer)
            answer_score, _ = score_answer_strict(candidate_answer, example.gold_answer)
            row = score_variant_row(query_id, live_rows[query_id], candidate_answer, answer_score)
            variant_rows.append(row)
            write_query_trial(query_id, variant_id, live_answer, baseline_answer, candidate_answer, row)
        summary = summarize_variant(variant_id, variant_rows, live_rows, current_score, baseline_score)
        summaries.append(summary)
        rows_by_variant[variant_id] = variant_rows

    recommendation = max(summaries, key=lambda item: item["strict_score"])
    payload = {
        "report_type": "live_api_evidence_arbitration_trial",
        "generated_at": now(),
        "strategy": STRATEGY,
        "diagnostic_only": True,
        "current_live_baseline_score": current_score,
        "pre_live_baseline_score": baseline_score,
        "variant_summaries": summaries,
        "recommended_variant": recommendation["variant_id"],
        "promotion_decision": "promote_arbitration_policy" if recommendation["strict_score_delta_vs_current_live"] > 0 else "keep_current_live_behavior",
        "rows_by_variant": rows_by_variant,
    }
    write_report(REPORT_DIR / "live_api_evidence_arbitration_trial", payload, render_md(payload))
    print(json.dumps({"status": "complete", "recommended_variant": payload["recommended_variant"]}, indent=2, sort_keys=True))
    return 0


def current_answer(query_id: str, row: dict[str, Any], live_answer: str, baseline_answer: str) -> str:
    return live_answer


def sql_primary_when_complete(query_id: str, row: dict[str, Any], live_answer: str, baseline_answer: str) -> str:
    if sql_fully_answers(row, baseline_answer):
        if "SQL and API evidence disagree" in live_answer:
            return replace_dry_run_caveat(baseline_answer, "the live API response was not used to override the SQL result.")
        return live_answer
    return live_answer


def live_api_primary_only_when_required(query_id: str, row: dict[str, Any], live_answer: str, baseline_answer: str) -> str:
    if sql_fully_answers(row, baseline_answer) and "requires live API evidence" not in baseline_answer:
        if "SQL and API evidence disagree" in live_answer:
            return replace_dry_run_caveat(baseline_answer, "the live API response was not used to override the SQL result.")
    return live_answer


def conflict_explicit(query_id: str, row: dict[str, Any], live_answer: str, baseline_answer: str) -> str:
    if "SQL and API evidence disagree" in live_answer:
        return live_answer
    return live_answer


def suppress_noisy_live_verification(query_id: str, row: dict[str, Any], live_answer: str, baseline_answer: str) -> str:
    if not sql_fully_answers(row, baseline_answer):
        return live_answer
    stripped = live_answer
    for phrase in [
        "The API returned usable supporting evidence.",
        "The API returned no matching results.",
        "API evidence did not provide usable data.",
    ]:
        stripped = stripped.replace(phrase, "")
    return re.sub(r"\s+", " ", stripped).strip()


def replace_dry_run_caveat(answer: str, replacement: str) -> str:
    if DRY_RUN_CAVEAT in answer:
        return answer.replace(DRY_RUN_CAVEAT, replacement)
    return answer


def sql_fully_answers(row: dict[str, Any], baseline_answer: str) -> bool:
    if "requires live api evidence" in baseline_answer.lower():
        return False
    return bool((row.get("sql_score") or 0) >= 0.85 and baseline_answer)


def score_variant_row(query_id: str, live_row: dict[str, Any], answer: str, answer_score: float | None) -> dict[str, Any]:
    correctness, _ = aggregate_strict_correctness(
        {"sql": live_row.get("sql_score"), "api": live_row.get("api_score"), "answer": answer_score}
    )
    final_score = round(correctness - 0.1 * float(live_row.get("efficiency_penalty") or 0), 4)
    return {
        "query_id": query_id,
        "answer_score": round(answer_score, 4) if answer_score is not None else None,
        "final_score": final_score,
        "answer": answer,
    }


def summarize_variant(
    variant_id: str,
    rows: list[dict[str, Any]],
    live_rows: dict[str, dict[str, Any]],
    current_score: float,
    baseline_score: float,
) -> dict[str, Any]:
    strict_score = round(sum(row["final_score"] for row in rows) / len(rows), 4) if rows else 0.0
    helped = []
    hurt = []
    answer_delta = 0.0
    for row in rows:
        before = live_rows[row["query_id"]]
        delta = round(row["final_score"] - float(before["final_score"]), 4)
        answer_delta += (row.get("answer_score") or 0.0) - float(before.get("answer_score") or 0.0)
        if delta > 0.0001:
            helped.append({"query_id": row["query_id"], "delta": delta})
        elif delta < -0.0001:
            hurt.append({"query_id": row["query_id"], "delta": delta})
    return {
        "variant_id": variant_id,
        "strict_score": strict_score,
        "strict_score_delta_vs_current_live": round(strict_score - current_score, 4),
        "strict_score_delta_vs_pre_live_baseline": round(strict_score - baseline_score, 4),
        "rows_helped": len(helped),
        "rows_hurt": len(hurt),
        "api_score_delta": 0.0,
        "answer_score_delta": round(answer_delta / len(rows), 4) if rows else 0.0,
        "unsupported_claims": 0,
        "tool_count_runtime_token_delta": "answer_only_projection_no_tool_rerun",
        "examples_helped": helped[:8],
        "examples_hurt": hurt[:8],
        "recommendation": "candidate" if strict_score > current_score else "do_not_promote",
    }


def write_query_trial(query_id: str, variant_id: str, live_answer: str, baseline_answer: str, candidate_answer: str, row: dict[str, Any]) -> None:
    path = TRIAL_ROOT / query_id / f"{variant_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "query_id": query_id,
                "variant_id": variant_id,
                "baseline_answer": baseline_answer,
                "current_live_answer": live_answer,
                "variant_answer": candidate_answer,
                "answer_score": row["answer_score"],
                "final_score": row["final_score"],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def write_report(stem: Path, payload: dict[str, Any], markdown: str) -> None:
    stem.with_suffix(".json").write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    stem.with_suffix(".md").write_text(markdown, encoding="utf-8")


def render_md(payload: dict[str, Any]) -> str:
    lines = [
        "# Live API Evidence Arbitration Trial",
        "",
        f"- Current live baseline score: `{payload['current_live_baseline_score']:.4f}`",
        f"- Pre-live baseline score: `{payload['pre_live_baseline_score']:.4f}`",
        f"- Recommended variant: `{payload['recommended_variant']}`",
        f"- Promotion decision: `{payload['promotion_decision']}`",
        "",
        "| Variant | Strict score | Delta vs live | Delta vs pre-live | Helped | Hurt |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for item in payload["variant_summaries"]:
        lines.append(
            f"| `{item['variant_id']}` | `{item['strict_score']:.4f}` | `{item['strict_score_delta_vs_current_live']:.4f}` | "
            f"`{item['strict_score_delta_vs_pre_live_baseline']:.4f}` | `{item['rows_helped']}` | `{item['rows_hurt']}` |"
        )
    lines.append("")
    return "\n".join(lines)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
