#!/usr/bin/env python
from __future__ import annotations

import copy
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.answer_faithfulness import evaluate_answer_faithfulness
from dashagent.answer_intent import AnswerIntent, classify_answer_intent
from dashagent.answer_slots import extract_answer_slots
from dashagent.config import Config
from dashagent.eval_harness import EvalExample, EvalHarness
from dashagent.executor import AgentExecutor
from dashagent.token_reduction_policy import official_estimated_tokens
from dashagent.trajectory import redact_secrets
from scripts.package_query_outputs import required_trajectory_fields_present
from scripts.run_evidence_aware_answer_rewrite_trial import (
    _dry_run_labels,
    _invariant_hashes,
    _plan_hash_check,
    _sha,
    tool_results_from_trajectory,
)
from scripts.run_official_token_reduction_eval import _score_result


VARIANTS = [
    "sql_required_value_answer_slots",
    "zero_row_local_evidence_clarity",
    "dry_run_caveat_after_sql_answer",
    "answer_intent_count_list_status_guard",
    "combined_minimal",
]

REPORT_STEM = "score_focused_core_improvement_trials"
FIX_DECISION_STEM = "score_focused_core_fix_decision"


def main() -> int:
    config = Config.from_env(ROOT)
    payload = run_score_focused_core_improvement_trials(config)
    print(
        json.dumps(
            {
                "json": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.json"),
                "markdown": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.md"),
                "best_variant": payload["summary"].get("best_variant"),
                "recommendation": payload["fix_decision"].get("recommendation"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def run_score_focused_core_improvement_trials(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    output_root = config.outputs_dir / "score_focused_core_improvement_trials"
    _assert_isolated(config.outputs_dir, output_root)
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)

    strict = _load_json(config.outputs_dir / "eval_results_strict.json")
    strict_rows = [
        row
        for row in strict.get("rows", []) or []
        if row.get("strategy") == "SQL_FIRST_API_VERIFY"
    ]
    executor = AgentExecutor(config)
    examples = {example.query_id: example for example in EvalHarness(config).load_examples()}
    variant_reports: list[dict[str, Any]] = []
    all_rows: list[dict[str, Any]] = []
    for variant in VARIANTS:
        rows = [
            _evaluate_row(config, executor, output_root, strict_row, examples.get(str(strict_row.get("query_id"))), variant)
            for strict_row in strict_rows
        ]
        variant_reports.append(_variant_summary(variant, rows, strict))
        all_rows.extend(rows)

    summary = _overall_summary(variant_reports, strict)
    fix_decision = _fix_decision(summary, variant_reports)
    payload = {
        "report_type": REPORT_STEM,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "diagnostic_only": True,
        "official_score_claim": False,
        "promotion_allowed": False,
        "packaged_runtime_changed": False,
        "writes_eval_outputs": False,
        "writes_final_submission": False,
        "isolated_output_root": str(output_root),
        "baseline_strict_score": _baseline_score(strict),
        "variants": VARIANTS,
        "variant_reports": variant_reports,
        "rows": all_rows,
        "summary": summary,
        "fix_decision": fix_decision,
        "artifact_isolation": {
            "writes_official_eval_results_strict": False,
            "writes_outputs_eval": False,
            "writes_final_submission": False,
            "answer_only_trials": True,
        },
        "promotion_gate": [
            "strict score improves",
            "hidden-style remains 48/48",
            "check_submission_ready passes",
            "unsupported claims do not increase",
            "no hardcoding",
            "final submission format unchanged",
            "no regression on high-scoring rows",
        ],
        "runtime_behavior_changed": False,
        "credentials_accessed": False,
        "env_local_accessed": False,
    }
    payload = redact_secrets(payload)
    _write_json(reports_dir / f"{REPORT_STEM}.json", payload)
    (reports_dir / f"{REPORT_STEM}.md").write_text(_render_trials(payload), encoding="utf-8")
    _write_json(reports_dir / f"{FIX_DECISION_STEM}.json", fix_decision)
    (reports_dir / f"{FIX_DECISION_STEM}.md").write_text(_render_fix_decision(fix_decision), encoding="utf-8")
    return payload


def apply_score_focused_variant(trajectory: dict[str, Any], variant: str) -> dict[str, Any]:
    if variant not in VARIANTS:
        raise ValueError(f"Unknown score-focused variant: {variant}")
    candidate = copy.deepcopy(trajectory)
    query = str(candidate.get("original_query") or "")
    baseline = str(candidate.get("final_answer") or "")
    facts = extract_sql_answer_facts(candidate)
    dry_run = _has_dry_run_api(candidate)

    if variant == "sql_required_value_answer_slots":
        answer = _append_missing_sql_facts(baseline, facts)
    elif variant == "zero_row_local_evidence_clarity":
        answer = _zero_row_answer(facts, dry_run) if facts["zero_row_sql"] else baseline
    elif variant == "dry_run_caveat_after_sql_answer":
        answer = _sql_first_answer(query, facts, dry_run) if dry_run and _has_usable_sql_fact(facts) else baseline
    elif variant == "answer_intent_count_list_status_guard":
        answer = _intent_guard_answer(query, facts, dry_run) or baseline
    else:
        if facts["zero_row_sql"]:
            answer = _zero_row_answer(facts, dry_run)
        else:
            answer = _intent_guard_answer(query, facts, dry_run) or (
                _sql_first_answer(query, facts, dry_run) if dry_run and _has_usable_sql_fact(facts) else _append_missing_sql_facts(baseline, facts)
            )

    candidate["final_answer"] = answer
    candidate["estimated_tokens"] = official_estimated_tokens(candidate)
    return candidate


def extract_sql_answer_facts(trajectory: dict[str, Any]) -> dict[str, Any]:
    tool_results = tool_results_from_trajectory(trajectory)
    query = str(trajectory.get("original_query") or "")
    slots = extract_answer_slots(query, tool_results)
    rows = _sql_rows(trajectory)
    count_value = _explicit_count_value(rows)
    if count_value is None and slots.sql_row_count is not None:
        count_value = slots.sql_row_count
    names = _row_values(rows, ["name", "campaign_name", "campaignname", "segment_name", "audience_name", "dataset_name", "collection_name", "target_name", "dataflow_name"])
    ids = _row_values(rows, ["id", "_id", "campaign_id", "campaignid", "segment_id", "segmentid", "audience_id", "destination_id", "dataflow_id", "run_id", "batch_id"])
    statuses = _row_values(rows, ["status", "state", "campaign_state", "processing_status", "processingstatus"])
    timestamps = _row_values(rows, ["timestamp", "date", "time", "created", "created_time", "createdtime", "updated", "updated_time", "updatedtime", "published_time", "lastdeployedtime", "modified"])
    zero_row = any(_sql_payload_row_count(step.get("result") or {}) == 0 for step in trajectory.get("steps", []) if step.get("kind") == "sql_call" and (step.get("result") or {}).get("ok"))
    return {
        "query": query,
        "answer_intent": str(classify_answer_intent(query, slots)),
        "count": count_value,
        "names": _dedupe(names),
        "ids": _dedupe(ids),
        "statuses": _dedupe(statuses),
        "timestamps": _dedupe(timestamps),
        "sql_row_count": slots.sql_row_count,
        "zero_row_sql": zero_row,
        "rows": rows[:5],
    }


def _evaluate_row(
    config: Config,
    executor: AgentExecutor,
    output_root: Path,
    strict_row: dict[str, Any],
    example: EvalExample | None,
    variant: str,
) -> dict[str, Any]:
    query_id = str(strict_row.get("query_id") or "")
    query = str(strict_row.get("query") or "")
    baseline = _load_trajectory(strict_row.get("output_dir"))
    if not baseline:
        return _skipped_row(output_root, variant, query_id, query, strict_row, "missing baseline trajectory")
    candidate = apply_score_focused_variant(baseline, variant)
    candidate_answer = str(candidate.get("final_answer") or "")
    baseline_answer = str(baseline.get("final_answer") or "")
    scores = _score_result(executor, candidate, candidate_answer, example) if example else _no_scores()
    baseline_score = float(strict_row.get("final_score") or 0.0)
    baseline_answer_score = float(strict_row.get("answer_score") or 0.0)
    baseline_faith = evaluate_answer_faithfulness(baseline_answer, extract_answer_slots(query, tool_results_from_trajectory(baseline)))
    candidate_faith = evaluate_answer_faithfulness(candidate_answer, extract_answer_slots(query, tool_results_from_trajectory(candidate)))
    plan_hash = _plan_hash_check(baseline, candidate)
    invariant_checks = _invariant_checks(baseline, candidate, query)

    output_dir = output_root / variant / query_id
    _assert_isolated(config.outputs_dir, output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "metadata.json").write_text(
        json.dumps({"query_id": query_id, "query": query, "variant": variant, "answer_only": True}, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (output_dir / "filled_system_prompt.txt").write_text("Score-focused core improvement trial. SQL/API/tool execution unchanged.\n", encoding="utf-8")
    (output_dir / "trajectory.json").write_text(json.dumps(candidate, indent=2, sort_keys=True, default=str), encoding="utf-8")
    score_delta = round(float(scores["final_score"] or 0.0) - baseline_score, 4)
    answer_delta = round(float(scores["answer_score"] or 0.0) - baseline_answer_score, 4)
    row = {
        "query_id": query_id,
        "query": query,
        "variant": variant,
        "baseline_final_answer": baseline_answer,
        "candidate_final_answer": candidate_answer,
        "final_answer_changed": baseline_answer != candidate_answer,
        "baseline_score": round(baseline_score, 4),
        "candidate_score": scores["final_score"],
        "score_delta": score_delta,
        "baseline_answer_score": strict_row.get("answer_score"),
        "candidate_answer_score": scores["answer_score"],
        "answer_score_delta": answer_delta,
        "sql_score_delta": 0.0 if plan_hash["sql_hash_unchanged"] else None,
        "api_score_delta": 0.0 if plan_hash["api_hash_unchanged"] else None,
        "baseline_tokens": int(strict_row.get("estimated_tokens") or baseline.get("estimated_tokens") or 0),
        "candidate_tokens": int(candidate.get("estimated_tokens") or 0),
        "token_delta": int(candidate.get("estimated_tokens") or 0) - int(strict_row.get("estimated_tokens") or baseline.get("estimated_tokens") or 0),
        "runtime_delta": 0.0,
        "baseline_tool_calls": int(strict_row.get("tool_call_count") or baseline.get("tool_call_count") or 0),
        "candidate_tool_calls": int(candidate.get("tool_call_count") or 0),
        "tool_delta": int(candidate.get("tool_call_count") or 0) - int(strict_row.get("tool_call_count") or baseline.get("tool_call_count") or 0),
        "baseline_unsupported_claim_count": len(baseline_faith.unsupported_claims),
        "candidate_unsupported_claim_count": len(candidate_faith.unsupported_claims),
        "unsupported_claim_delta": len(candidate_faith.unsupported_claims) - len(baseline_faith.unsupported_claims),
        "required_fields_preserved": required_trajectory_fields_present(candidate),
        "dry_run_labels_preserved": _dry_run_labels(candidate) == _dry_run_labels(baseline),
        "invariant_checks": invariant_checks,
        "plan_hashes": plan_hash,
        "answer_only": True,
        "high_score_baseline": baseline_score >= 0.75,
        "high_score_regression": baseline_score >= 0.75 and score_delta < 0,
        "safe_for_promotion_gate": False,
        "promotion_rejection_reasons": [],
        "output_dir": str(output_dir),
    }
    row["promotion_rejection_reasons"] = _row_rejection_reasons(row)
    row["safe_for_promotion_gate"] = not row["promotion_rejection_reasons"]
    return redact_secrets(row)


def _variant_summary(variant: str, rows: list[dict[str, Any]], strict: dict[str, Any]) -> dict[str, Any]:
    baseline = _baseline_score(strict)
    safe = [row for row in rows if row.get("safe_for_promotion_gate")]
    helped = [row for row in rows if float(row.get("score_delta") or 0.0) > 0]
    hurt = [row for row in rows if float(row.get("score_delta") or 0.0) < 0]
    projected = round(baseline + sum(float(row.get("score_delta") or 0.0) for row in rows) / max(1, len(rows)), 4) if rows else baseline
    unsupported_delta = sum(int(row.get("unsupported_claim_delta") or 0) for row in rows)
    high_regressions = [row for row in rows if row.get("high_score_regression")]
    promotion_safe = bool(rows) and projected > baseline and unsupported_delta <= 0 and not hurt and not high_regressions and len(safe) == len(rows)
    return {
        "variant": variant,
        "baseline_strict_score": baseline,
        "projected_strict_score": projected,
        "strict_score_delta": round(projected - baseline, 4),
        "rows_evaluated": len(rows),
        "rows_changed": sum(1 for row in rows if row.get("final_answer_changed")),
        "rows_helped": len(helped),
        "rows_hurt": len(hurt),
        "high_score_regressions": len(high_regressions),
        "answer_score_delta_avg": _avg(row.get("answer_score_delta") for row in rows),
        "unsupported_claim_delta": unsupported_delta,
        "token_delta_avg": _avg(row.get("token_delta") for row in rows),
        "runtime_delta_avg": 0.0,
        "tool_delta_avg": _avg(row.get("tool_delta") for row in rows),
        "final_submission_would_change": any(row.get("final_answer_changed") for row in rows),
        "promotion_safe": promotion_safe,
        "promotion_rejection_reasons": _variant_rejection_reasons(projected, baseline, rows, unsupported_delta, hurt, high_regressions),
        "helped_examples": _examples(helped),
        "hurt_examples": _examples(hurt),
    }


def _overall_summary(variant_reports: list[dict[str, Any]], strict: dict[str, Any]) -> dict[str, Any]:
    best = max(variant_reports, key=lambda item: float(item.get("strict_score_delta") or 0.0), default={})
    safe = [item for item in variant_reports if item.get("promotion_safe")]
    return {
        "baseline_strict_score": _baseline_score(strict),
        "best_variant": best.get("variant"),
        "best_projected_strict_score": best.get("projected_strict_score"),
        "best_strict_score_delta": best.get("strict_score_delta"),
        "promotion_safe_variant_count": len(safe),
        "promotion_safe_variants": [item.get("variant") for item in safe],
        "recommendation": "promote_single_winner_after_validation" if len(safe) == 1 else "keep_trial_only",
        "reason": (
            "Exactly one variant passed isolated gates; runtime implementation still requires strict/hidden/submission validation."
            if len(safe) == 1
            else "No variant passed all isolated promotion gates; keep trial-only and make no runtime change."
        ),
    }


def _fix_decision(summary: dict[str, Any], variant_reports: list[dict[str, Any]]) -> dict[str, Any]:
    safe = [item for item in variant_reports if item.get("promotion_safe")]
    decision = {
        "report_type": FIX_DECISION_STEM,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "diagnostic_only": True,
        "official_score_claim": False,
        "baseline_strict_score": summary.get("baseline_strict_score"),
        "best_variant": summary.get("best_variant"),
        "best_projected_strict_score": summary.get("best_projected_strict_score"),
        "best_strict_score_delta": summary.get("best_strict_score_delta"),
        "promotion_safe": len(safe) == 1,
        "variant_promoted": None,
        "runtime_change_applied": False,
        "final_submission_changed": False,
        "hidden_style_validation_required_before_promotion": bool(safe),
        "check_submission_ready_required_before_promotion": bool(safe),
        "recommendation": summary.get("recommendation"),
        "reason": summary.get("reason"),
        "rows_helped": next((item.get("rows_helped") for item in variant_reports if item.get("variant") == summary.get("best_variant")), 0),
        "rows_hurt": next((item.get("rows_hurt") for item in variant_reports if item.get("variant") == summary.get("best_variant")), 0),
        "ranked_variants": sorted(
            [
                {
                    "variant": item.get("variant"),
                    "strict_score_delta": item.get("strict_score_delta"),
                    "promotion_safe": item.get("promotion_safe"),
                    "rejection_reasons": item.get("promotion_rejection_reasons"),
                }
                for item in variant_reports
            ],
            key=lambda item: float(item.get("strict_score_delta") or 0.0),
            reverse=True,
        ),
    }
    if len(safe) > 1:
        decision["recommendation"] = "multiple_candidates_require_separate_approval"
        decision["reason"] = "Multiple isolated candidates passed; no runtime change is applied in this pass."
        decision["promotion_safe"] = False
    return redact_secrets(decision)


def _invariant_checks(baseline: dict[str, Any], candidate: dict[str, Any], query: str) -> dict[str, bool]:
    base = _invariant_hashes(baseline, query)
    cand = _invariant_hashes(candidate, query)
    return {key: base.get(key) == cand.get(key) for key in base}


def _row_rejection_reasons(row: dict[str, Any]) -> list[str]:
    reasons = []
    if row.get("required_fields_preserved") is not True:
        reasons.append("required_fields_missing")
    if row.get("dry_run_labels_preserved") is not True:
        reasons.append("dry_run_labels_changed")
    if int(row.get("tool_delta") or 0) != 0:
        reasons.append("tool_count_changed")
    if row.get("sql_score_delta") not in (0, 0.0):
        reasons.append("sql_score_changed")
    if row.get("api_score_delta") not in (0, 0.0):
        reasons.append("api_score_changed")
    if int(row.get("unsupported_claim_delta") or 0) > 0:
        reasons.append("unsupported_claims_increased")
    if row.get("high_score_regression"):
        reasons.append("high_score_row_regressed")
    for key, ok in (row.get("invariant_checks") or {}).items():
        if ok is not True:
            reasons.append(f"{key}_changed")
    return list(dict.fromkeys(reasons))


def _variant_rejection_reasons(
    projected: float,
    baseline: float,
    rows: list[dict[str, Any]],
    unsupported_delta: int,
    hurt: list[dict[str, Any]],
    high_regressions: list[dict[str, Any]],
) -> list[str]:
    reasons = []
    if projected <= baseline:
        reasons.append("strict_score_not_improved")
    if unsupported_delta > 0:
        reasons.append("unsupported_claims_increased")
    if hurt:
        reasons.append("rows_hurt")
    if high_regressions:
        reasons.append("high_scoring_rows_regressed")
    if any(row.get("promotion_rejection_reasons") for row in rows):
        reasons.append("row_level_gate_failed")
    return reasons


def _append_missing_sql_facts(baseline: str, facts: dict[str, Any]) -> str:
    additions = _missing_fact_phrases(baseline, facts)
    if not additions:
        return baseline
    suffix = " SQL evidence also includes: " + "; ".join(additions) + "."
    return _join_sentences(baseline, suffix)


def _missing_fact_phrases(baseline: str, facts: dict[str, Any]) -> list[str]:
    lowered = baseline.lower()
    phrases: list[str] = []
    count = facts.get("count")
    if count is not None and str(count).lower() not in lowered:
        phrases.append(f"count {count}")
    names = [value for value in facts.get("names", []) if str(value).lower() not in lowered]
    if names:
        phrases.append("names " + _join_human(names[:5]))
    statuses = [value for value in facts.get("statuses", []) if str(value).lower() not in lowered]
    if statuses:
        phrases.append("statuses " + _join_human(statuses[:5]))
    timestamps = [value for value in facts.get("timestamps", []) if str(value)[:10].lower() not in lowered]
    if timestamps:
        phrases.append("timestamps " + _join_human([str(value)[:10] for value in timestamps[:5]]))
    return phrases


def _zero_row_answer(facts: dict[str, Any], dry_run: bool) -> str:
    answer = "No matching local records were found in the available local evidence."
    if dry_run:
        answer += " Live API verification was not executed because Adobe credentials are unavailable."
    return answer


def _sql_first_answer(query: str, facts: dict[str, Any], dry_run: bool) -> str:
    answer = _intent_guard_answer(query, facts, dry_run=False) or _generic_sql_fact_answer(facts)
    if dry_run:
        answer = _join_sentences(answer, "Live API verification was not executed because Adobe credentials are unavailable.")
    return answer


def _intent_guard_answer(query: str, facts: dict[str, Any], dry_run: bool) -> str | None:
    intent = AnswerIntent(facts.get("answer_intent") or str(classify_answer_intent(query)))
    if facts.get("zero_row_sql"):
        return _zero_row_answer(facts, dry_run)
    answer: str | None = None
    if intent == AnswerIntent.COUNT and facts.get("count") is not None:
        answer = f"Based on the SQL evidence, the count is {facts['count']}."
    elif intent == AnswerIntent.LIST:
        values = facts.get("names") or facts.get("ids")
        if values:
            answer = f"Based on the SQL evidence, matching values are: {_join_human(values[:8])}."
    elif intent == AnswerIntent.STATUS and facts.get("statuses"):
        answer = f"Based on the SQL evidence, the status/state value is {_join_human(facts['statuses'][:5])}."
    elif intent == AnswerIntent.WHEN and facts.get("timestamps"):
        timestamps = _join_human([str(value)[:10] for value in facts["timestamps"][:5]])
        answer = f"Based on the SQL evidence, the timestamp is {timestamps}."
    if answer and dry_run:
        answer = _join_sentences(answer, "Live API verification was not executed because Adobe credentials are unavailable.")
    return answer


def _generic_sql_fact_answer(facts: dict[str, Any]) -> str:
    pieces = _missing_fact_phrases("", facts)
    if pieces:
        return "Based on the SQL evidence, " + "; ".join(pieces) + "."
    return "Based on the SQL evidence, matching local records were found."


def _has_usable_sql_fact(facts: dict[str, Any]) -> bool:
    return any(
        facts.get(key)
        for key in ["count", "names", "ids", "statuses", "timestamps", "zero_row_sql"]
    )


def _has_dry_run_api(trajectory: dict[str, Any]) -> bool:
    for step in trajectory.get("steps", []):
        if step.get("kind") == "api_call" and (step.get("result") or {}).get("dry_run"):
            return True
    return False


def _sql_rows(trajectory: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for step in trajectory.get("steps", []):
        if step.get("kind") != "sql_call":
            continue
        payload = step.get("result") or {}
        raw = payload.get("rows")
        if isinstance(raw, dict) and isinstance(raw.get("items"), list):
            rows.extend(item for item in raw["items"] if isinstance(item, dict))
        elif isinstance(raw, list):
            rows.extend(item for item in raw if isinstance(item, dict))
    return rows


def _sql_payload_row_count(payload: dict[str, Any]) -> int | None:
    if payload.get("row_count") is not None:
        try:
            return int(payload.get("row_count") or 0)
        except Exception:
            return None
    raw = payload.get("rows")
    if isinstance(raw, dict) and raw.get("total_items") is not None:
        try:
            return int(raw.get("total_items") or 0)
        except Exception:
            return None
    if isinstance(raw, list):
        return len(raw)
    return None


def _explicit_count_value(rows: list[dict[str, Any]]) -> Any:
    for row in rows:
        for key, value in row.items():
            key_norm = _norm(key)
            if key_norm in {"count", "total", "totalcount", "rowcount", "num", "number"} or "count" in key_norm:
                if value not in (None, ""):
                    return value
        if len(row) == 1:
            value = next(iter(row.values()))
            if isinstance(value, (int, float)) or str(value).isdigit():
                return value
    return None


def _row_values(rows: list[dict[str, Any]], keys: list[str]) -> list[str]:
    normalized = {_norm(key) for key in keys}
    values: list[str] = []
    for row in rows:
        for key, value in row.items():
            if value in (None, "", [], {}):
                continue
            key_norm = _norm(key)
            if key_norm in normalized:
                values.append(str(value))
    return values


def _norm(value: Any) -> str:
    return "".join(ch for ch in str(value).lower() if ch.isalnum())


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        key = str(value).strip().lower()
        if key and key not in seen:
            seen.add(key)
            output.append(str(value))
    return output


def _join_human(values: list[Any]) -> str:
    parts = [str(value) for value in values if value not in (None, "")]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    return ", ".join(parts[:-1]) + " and " + parts[-1]


def _join_sentences(first: str, second: str) -> str:
    first = str(first or "").strip()
    second = str(second or "").strip()
    if not first:
        return second
    if not second:
        return first
    if not first.endswith((".", "!", "?")):
        first += "."
    return first + " " + second


def _strict_rows(config: Config) -> list[dict[str, Any]]:
    payload = _load_json(config.outputs_dir / "eval_results_strict.json")
    return [row for row in payload.get("rows", []) if row.get("strategy") == "SQL_FIRST_API_VERIFY"]


def _load_trajectory(output_dir: Any) -> dict[str, Any]:
    if not output_dir:
        return {}
    path = Path(str(output_dir)) / "trajectory.json"
    return _load_json(path)


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")


def _no_scores() -> dict[str, Any]:
    return {"sql_score": None, "api_score": None, "answer_score": None, "correctness_score": 0.0, "final_score": 0.0}


def _baseline_score(strict: dict[str, Any]) -> float:
    try:
        return round(float(((strict.get("summary") or {}).get("by_strategy") or {}).get("SQL_FIRST_API_VERIFY", {}).get("avg_final_score") or 0.0), 4)
    except Exception:
        rows = [row for row in strict.get("rows", []) if row.get("strategy") == "SQL_FIRST_API_VERIFY"]
        return round(sum(float(row.get("final_score") or 0.0) for row in rows) / len(rows), 4) if rows else 0.0


def _avg(values: Any) -> float:
    numbers = [float(value) for value in values if value is not None]
    return round(sum(numbers) / len(numbers), 4) if numbers else 0.0


def _examples(rows: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    return [
        {
            "query_id": row.get("query_id"),
            "score_delta": row.get("score_delta"),
            "answer_score_delta": row.get("answer_score_delta"),
            "baseline_answer": str(row.get("baseline_final_answer") or "")[:180],
            "candidate_answer": str(row.get("candidate_final_answer") or "")[:180],
        }
        for row in rows[:limit]
    ]


def _skipped_row(output_root: Path, variant: str, query_id: str, query: str, strict_row: dict[str, Any], reason: str) -> dict[str, Any]:
    output_dir = output_root / variant / (query_id or "unknown")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "metadata.json").write_text(json.dumps({"query_id": query_id, "query": query, "variant": variant, "skipped": True, "reason": reason}, indent=2), encoding="utf-8")
    (output_dir / "filled_system_prompt.txt").write_text("Score-focused core improvement trial skipped.\n", encoding="utf-8")
    (output_dir / "trajectory.json").write_text(json.dumps({"query_id": query_id, "final_answer": "", "steps": [], "skipped": True, "reason": reason}, indent=2), encoding="utf-8")
    return {
        "query_id": query_id,
        "query": query,
        "variant": variant,
        "baseline_score": strict_row.get("final_score"),
        "candidate_score": None,
        "score_delta": 0.0,
        "baseline_answer_score": strict_row.get("answer_score"),
        "candidate_answer_score": None,
        "answer_score_delta": 0.0,
        "skipped": True,
        "skip_reason": reason,
        "safe_for_promotion_gate": False,
        "promotion_rejection_reasons": [reason],
        "output_dir": str(output_dir),
    }


def _assert_isolated(outputs_dir: Path, path: Path) -> None:
    resolved = path.resolve()
    allowed = (outputs_dir / "score_focused_core_improvement_trials").resolve()
    if resolved == allowed:
        return
    try:
        resolved.relative_to(allowed)
    except ValueError as exc:
        raise RuntimeError(f"Refusing to write score-focused trial artifact outside isolated path: {path}") from exc


def _render_trials(payload: dict[str, Any]) -> str:
    lines = [
        "# Score-Focused Core Improvement Trials",
        "",
        "Diagnostic-only answer/SQL-evidence trials over the direct score-producing path. No packaged runtime, official eval artifact, or final submission output is changed.",
        "",
        f"- Baseline strict score: `{payload.get('baseline_strict_score')}`",
        f"- Official score claim: `{payload.get('official_score_claim')}`",
        f"- Writes eval outputs: `{payload.get('writes_eval_outputs')}`",
        f"- Writes final submission: `{payload.get('writes_final_submission')}`",
        f"- Recommendation: `{payload.get('fix_decision', {}).get('recommendation')}`",
        "",
        "| Variant | Projected strict | Delta | Rows helped | Rows hurt | Unsupported delta | Promotion safe? |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for item in payload.get("variant_reports", []):
        lines.append(
            f"| `{item.get('variant')}` | {item.get('projected_strict_score')} | {item.get('strict_score_delta')} | "
            f"{item.get('rows_helped')} | {item.get('rows_hurt')} | {item.get('unsupported_claim_delta')} | {item.get('promotion_safe')} |"
        )
    lines.extend(["", "## Fix Decision", "", payload.get("fix_decision", {}).get("reason", "")])
    return "\n".join(lines) + "\n"


def _render_fix_decision(payload: dict[str, Any]) -> str:
    lines = [
        "# Score-Focused Core Fix Decision",
        "",
        f"- Diagnostic-only: `{payload.get('diagnostic_only')}`",
        f"- Baseline strict score: `{payload.get('baseline_strict_score')}`",
        f"- Best variant: `{payload.get('best_variant')}`",
        f"- Best projected strict score: `{payload.get('best_projected_strict_score')}`",
        f"- Best strict score delta: `{payload.get('best_strict_score_delta')}`",
        f"- Promotion safe: `{payload.get('promotion_safe')}`",
        f"- Runtime change applied: `{payload.get('runtime_change_applied')}`",
        f"- Final submission changed: `{payload.get('final_submission_changed')}`",
        f"- Recommendation: `{payload.get('recommendation')}`",
        "",
        payload.get("reason", ""),
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
