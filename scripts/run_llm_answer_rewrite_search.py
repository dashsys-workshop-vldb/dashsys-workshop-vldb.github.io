#!/usr/bin/env python
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.eval_harness import EvalHarness
from dashagent.executor import AgentExecutor
from dashagent.llm_candidate_generator import llm_candidate_search_status
from dashagent.llm_client import get_llm_client
from dashagent.report_run import report_metadata
from dashagent.supportable_answer_rewriter import (
    build_evidence_registry,
    compare_plan_hashes,
    parse_llm_rewrite_payload,
    validate_supportable_claims,
)
from dashagent.token_reduction_policy import official_estimated_tokens
from dashagent.trajectory import estimate_tokens
from scripts.package_query_outputs import required_trajectory_fields_present
from scripts.run_official_token_reduction_eval import _dry_run_labels, _live_api_evidence_available, _load_json, _load_trajectory, _score_result


MAX_TARGET_ROWS = 10
MAX_REWRITES_PER_ROW = 5
MAX_RETRIES_PER_ROW = 2
OUTPUT_NAME = "llm_answer_rewrite_search"


def main() -> int:
    config = Config.from_env(ROOT)
    payload = run_llm_answer_rewrite_search(config)
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    json_path = config.outputs_dir / f"{OUTPUT_NAME}.json"
    md_path = config.outputs_dir / f"{OUTPUT_NAME}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "status": payload["summary"]["status"]}, indent=2, sort_keys=True))
    return 0


def run_llm_answer_rewrite_search(config: Config) -> dict[str, Any]:
    status = llm_candidate_search_status()
    if not status.available:
        return _skipped(config, status, "skipped_no_llm_key", status.reason)
    client = get_llm_client(status.provider)
    if not client.available():
        return _skipped(config, status, "skipped_no_llm_key", "configured client is unavailable")

    strict = _load_json(config.outputs_dir / "eval_results_strict.json")
    unsafe = _load_json(config.outputs_dir / "unsafe_answer_candidate_analysis.json")
    executor = AgentExecutor(config)
    examples = {example.query_id: example for example in EvalHarness(config).load_examples()}
    strict_rows = {
        str(row.get("query_id")): row
        for row in strict.get("rows", [])
        if row.get("strategy") == "SQL_FIRST_API_VERIFY"
    }
    rows = []
    for query_id in _target_ids(unsafe, strict_rows)[:MAX_TARGET_ROWS]:
        strict_row = strict_rows.get(query_id)
        example = examples.get(query_id)
        if not strict_row or not example:
            rows.append({"query_id": query_id, "failure_category": "provider_error", "rejection_reason": "missing_strict_row"})
            continue
        rows.append(_run_row(executor, client, strict_row, example))
    return {
        **report_metadata(config.outputs_dir),
        "mode": OUTPUT_NAME,
        "skipped": False,
        "provider": status.provider,
        "model": client.model_name(),
        "budget": {
            "max_target_rows": MAX_TARGET_ROWS,
            "max_rewrites_per_row": MAX_REWRITES_PER_ROW,
            "max_retries_per_row": MAX_RETRIES_PER_ROW,
        },
        "packaged_execution_changed": False,
        "writes_eval_outputs": False,
        "writes_final_submission": False,
        "rows": rows,
        "summary": _summary(rows, status="completed", provider=status.provider),
        "notes": [
            "LLM rewrites are proposal-only and must cite local evidence IDs for every claim.",
            "No provider key values are printed or written.",
            "No LLM rewrite is promoted directly.",
        ],
    }


def _run_row(executor: AgentExecutor, client: Any, strict_row: dict[str, Any], example: Any) -> dict[str, Any]:
    query_id = str(strict_row.get("query_id"))
    query = str(strict_row.get("query") or example.query)
    baseline = _load_trajectory(strict_row.get("output_dir"))
    registry = build_evidence_registry(query, baseline)
    prompt = _prompt(query, baseline, registry)
    attempts: list[dict[str, Any]] = []
    raw_rewrites: list[dict[str, Any]] = []
    failure_category = "no_score_improvement"
    for attempt in range(1, MAX_RETRIES_PER_ROW + 1):
        result = client.generate_messages(
            [
                {"role": "system", "content": "Return strict JSON only. Rewrite dry-run answers with cited evidence claims. Do not use gold labels or final answers."},
                {"role": "user", "content": prompt},
            ]
        )
        if not result.get("ok"):
            failure_category = "provider_error"
            attempts.append({"attempt": attempt, "ok": False, "failure_category": failure_category, "error": _redacted_error(result.get("error") or result.get("reason"))})
            continue
        parsed, error = parse_llm_rewrite_payload(str(result.get("content") or ""))
        if error:
            failure_category = "invalid_json"
            attempts.append({"attempt": attempt, "ok": False, "failure_category": failure_category, "error": error})
            continue
        raw_rewrites = parsed[:MAX_REWRITES_PER_ROW]
        attempts.append({"attempt": attempt, "ok": True, "rewrite_count": len(raw_rewrites), "usage": result.get("usage", {})})
        break
    candidates = [_validate_and_score_rewrite(executor, strict_row, example, baseline, registry, raw, idx) for idx, raw in enumerate(raw_rewrites)]
    if candidates:
        failure_category = _row_failure_category(candidates)
    return {
        "query_id": query_id,
        "query": query,
        "attempts": attempts,
        "rewrite_count": len(candidates),
        "candidates": candidates,
        "failure_category": failure_category,
        "safe_for_packaged_trial": False,
        "rejection_reason": "LLM answer rewrites remain diagnostic until a deterministic isolated trial selects a score-improving candidate.",
    }


def _validate_and_score_rewrite(
    executor: AgentExecutor,
    strict_row: dict[str, Any],
    example: Any,
    baseline: dict[str, Any],
    registry: dict[str, dict[str, Any]],
    raw: dict[str, Any],
    idx: int,
) -> dict[str, Any]:
    claims = raw.get("claims") if isinstance(raw.get("claims"), list) else []
    answer = " ".join(str(claim.get("claim_text") or "") for claim in claims).strip()
    max_answer_tokens = estimate_tokens(str(baseline.get("final_answer") or "")) + 20
    validation = validate_supportable_claims(answer, claims, registry, trajectory=baseline, max_answer_tokens=max_answer_tokens)
    candidate = copy.deepcopy(baseline)
    candidate["final_answer"] = answer
    candidate["estimated_tokens"] = official_estimated_tokens(candidate)
    scores = _score_result(executor, candidate, answer, example) if validation.get("ok") else {}
    baseline_score = float(strict_row.get("final_score") or 0.0)
    baseline_correctness = float(strict_row.get("correctness_score") or 0.0)
    row = {
        "candidate_id": str(raw.get("candidate_id") or f"llm_rewrite_{idx}"),
        "claim_validation": validation,
        "score_delta": round(float(scores.get("final_score") or baseline_score) - baseline_score, 4) if scores else 0.0,
        "correctness_delta": round(float(scores.get("correctness_score") or baseline_correctness) - baseline_correctness, 4) if scores else 0.0,
        "answer_score_delta": round(float(scores.get("answer_score") or 0.0) - float(strict_row.get("answer_score") or 0.0), 4) if scores else 0.0,
        "token_delta": int(candidate.get("estimated_tokens") or 0) - int(strict_row.get("estimated_tokens") or baseline.get("estimated_tokens") or 0),
        **compare_plan_hashes(baseline, candidate),
        "required_fields_preserved": required_trajectory_fields_present(candidate),
        "dry_run_labels_preserved": _dry_run_labels(candidate) == _dry_run_labels(baseline),
        "live_api_evidence_fabricated": _live_api_evidence_available(candidate) and not _live_api_evidence_available(baseline),
        "claims": claims,
    }
    row["failure_categories"] = _failure_categories(row)
    row["safe_for_packaged_trial"] = False
    return row


def _failure_categories(row: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    validation_failures = set((row.get("claim_validation") or {}).get("failures") or [])
    if validation_failures:
        if "missing_or_unknown_evidence_id" in validation_failures or "evidence_source_mismatch" in validation_failures:
            failures.append("unsupported_claim")
        if "dry_run_payload_value_used" in validation_failures:
            failures.append("failed_leakage_check")
        failures.append("failed_claim_validation")
    if float(row.get("score_delta") or 0.0) <= 0:
        failures.append("no_score_improvement")
    if row.get("sql_hash_unchanged") is not True:
        failures.append("sql_hash_changed")
    if row.get("api_hash_unchanged") is not True:
        failures.append("api_hash_changed")
    return sorted(set(failures or ["failed_strict_score_gate"]))


def _row_failure_category(candidates: list[dict[str, Any]]) -> str:
    priority = [
        "failed_leakage_check",
        "unsupported_claim",
        "failed_claim_validation",
        "sql_hash_changed",
        "api_hash_changed",
        "failed_strict_score_gate",
        "no_score_improvement",
    ]
    seen = {failure for candidate in candidates for failure in candidate.get("failure_categories", [])}
    for item in priority:
        if item in seen:
            return item
    return "no_score_improvement"


def _target_ids(unsafe: dict[str, Any], strict_rows: dict[str, dict[str, Any]]) -> list[str]:
    ids = [str(row.get("query_id")) for row in unsafe.get("rows", []) if float(row.get("supportable_answer_delta") or 0.0) > 0]
    if ids:
        return list(dict.fromkeys(ids))
    ranked = sorted(strict_rows.values(), key=lambda row: (float(row.get("answer_score") or 1.0), float(row.get("final_score") or 0.0)))
    return [str(row.get("query_id")) for row in ranked[:MAX_TARGET_ROWS]]


def _summary(rows: list[dict[str, Any]], *, status: str, provider: str | None) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for row in rows:
        category = str(row.get("failure_category") or "unknown")
        counts[category] = counts.get(category, 0) + 1
    return {
        "status": status,
        "provider": provider,
        "total_rows": len(rows),
        "candidate_rows": sum(1 for row in rows if row.get("rewrite_count")),
        "safe_rows": 0,
        "unsafe_rows": len(rows),
        "failure_category_counts": dict(sorted(counts.items())),
        "recommendation": "keep_shadow_only",
    }


def _skipped(config: Config, status: Any, summary_status: str, reason: str) -> dict[str, Any]:
    return {
        **report_metadata(config.outputs_dir),
        "mode": OUTPUT_NAME,
        "skipped": True,
        "skip_reason": reason,
        "provider": status.provider,
        "packaged_execution_changed": False,
        "writes_eval_outputs": False,
        "writes_final_submission": False,
        "rows": [],
        "summary": _summary([], status=summary_status, provider=status.provider),
    }


def _prompt(query: str, trajectory: dict[str, Any], registry: dict[str, dict[str, Any]]) -> str:
    evidence = [
        {"evidence_id": key, "evidence_source": value.get("evidence_source"), "text": value.get("text")}
        for key, value in list(registry.items())[:12]
    ]
    return (
        "Rewrite the answer only. Preserve SQL/API/tool behavior implicitly by only returning answer claims.\n"
        "Every claim must cite one listed evidence_id. If a live API value is unavailable, use supported=false, "
        "evidence_source=dry_run_label, unsupported_action=mark_unavailable.\n"
        "Do not invent API payload values. Do not use gold labels, public answers, or query IDs.\n"
        f"Query: {query}\n"
        f"Current answer: {str(trajectory.get('final_answer') or '')[:400]}\n"
        f"Evidence registry: {json.dumps(evidence, sort_keys=True)}\n"
        "Return JSON: {\"rewrites\":[{\"candidate_id\":\"...\",\"claims\":[{\"claim_text\":\"...\",\"evidence_id\":\"...\",\"evidence_source\":\"query_text|endpoint_params|sql_row|parquet_evidence|dry_run_label\",\"supported\":true|false,\"unsupported_action\":null|\"mark_unavailable\"}]}]}."
    )


def _redacted_error(value: Any) -> str:
    return str(value or "").replace("\n", " ")[:400]


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# LLM Answer Rewrite Search",
        "",
        f"- Status: `{summary['status']}`",
        f"- Provider: `{payload.get('provider')}`",
        f"- Skipped: {payload.get('skipped')}",
        f"- Rows: {summary.get('total_rows', 0)}",
        f"- Candidate rows: {summary.get('candidate_rows', 0)}",
        f"- Recommendation: `{summary['recommendation']}`",
        f"- Packaged execution changed: {payload.get('packaged_execution_changed')}",
        "",
    ]
    if payload.get("skipped"):
        lines.append(f"Skip reason: {payload.get('skip_reason')}")
    else:
        lines.append("## Failure Categories")
        for category, count in summary.get("failure_category_counts", {}).items():
            lines.append(f"- `{category}`: {count}")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
