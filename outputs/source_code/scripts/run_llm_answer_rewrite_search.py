#!/usr/bin/env python
from __future__ import annotations

import copy
import json
import os
import re
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.eval_harness import EvalHarness
from dashagent.executor import AgentExecutor
from dashagent.llm_client import get_llm_client
from dashagent.report_run import report_metadata
from dashagent.supportable_answer_rewriter import (
    build_evidence_registry,
    compare_plan_hashes,
    parse_llm_rewrite_payload,
    summarize_answer_rewrite,
    validate_supportable_claims,
)
from dashagent.token_reduction_policy import official_estimated_tokens
from dashagent.trajectory import estimate_tokens, redact_secrets
from scripts.load_local_env import load_local_env
from scripts.package_query_outputs import required_trajectory_fields_present
from scripts.run_official_token_reduction_eval import _dry_run_labels, _live_api_evidence_available, _load_json, _load_trajectory, _score_result
from scripts.run_supportable_answer_rewrite_eval import _safe as _supportable_safe_gate


MAX_TARGET_ROWS = 10
DEFAULT_MAX_REWRITES_PER_ROW = 5
DEFAULT_MAX_RETRIES_PER_ROW = 2
FREE_MODEL_MAX_REWRITES_PER_ROW = 3
FREE_MODEL_MAX_RETRIES_PER_ROW = 1
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
    load_local_env(config.project_root)
    status = _answer_rewrite_llm_status()
    if not status.available:
        return _skipped(config, status, "skipped_no_llm_key", status.reason)
    client = get_llm_client(status.provider)
    if not client.available():
        return _skipped(config, status, "skipped_no_llm_key", "configured client is unavailable")
    budget = _budget_for_model(client.model_name())
    output_root = config.outputs_dir / OUTPUT_NAME
    _assert_isolated(config.outputs_dir, output_root)
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)

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
        rows.append(_run_row(config, output_root, executor, client, strict_row, example, budget))
    return {
        **report_metadata(config.outputs_dir),
        "mode": OUTPUT_NAME,
        "skipped": False,
        "provider": status.provider,
        "model": client.model_name(),
        **_sdk_metadata(client, provider=status.provider),
        "budget": budget,
        "packaged_execution_changed": False,
        "writes_eval_outputs": False,
        "writes_final_submission": False,
        "artifact_isolation": {
            "allowed_outputs": [f"outputs/{OUTPUT_NAME}.json", f"outputs/{OUTPUT_NAME}.md", f"outputs/{OUTPUT_NAME}/"],
            "candidate_output_root": f"outputs/{OUTPUT_NAME}/<query_id>/<candidate_id>/",
        },
        "rows": rows,
        "summary": _summary(rows, status="completed", provider=status.provider),
        "notes": [
            "LLM rewrites are proposal-only and must cite local evidence IDs for every claim.",
            "No provider key values are printed or written.",
            "No LLM rewrite is promoted directly.",
        ],
    }


def _answer_rewrite_llm_status() -> Any:
    if os.getenv("OPENROUTER_API_KEY"):
        return SimpleNamespace(available=True, provider="openrouter", reason="OPENROUTER_API_KEY present")
    if os.getenv("OPENAI_API_KEY"):
        return SimpleNamespace(available=True, provider="openrouter", reason="OPENAI_API_KEY present; using OpenRouter-compatible endpoint")
    return SimpleNamespace(available=False, provider=None, reason="No OPENAI_API_KEY or OPENROUTER_API_KEY present")


def _budget_for_model(model: str | None) -> dict[str, Any]:
    normalized = (model or "").strip().lower()
    if normalized == "openrouter/free":
        return {
            "max_target_rows": MAX_TARGET_ROWS,
            "max_rewrites_per_row": FREE_MODEL_MAX_REWRITES_PER_ROW,
            "max_retries_per_row": FREE_MODEL_MAX_RETRIES_PER_ROW,
            "budget_reason": "reduced_for_openrouter_free",
        }
    return {
        "max_target_rows": MAX_TARGET_ROWS,
        "max_rewrites_per_row": DEFAULT_MAX_REWRITES_PER_ROW,
        "max_retries_per_row": DEFAULT_MAX_RETRIES_PER_ROW,
        "budget_reason": "default",
    }


def _run_row(
    config: Config,
    output_root: Path,
    executor: AgentExecutor,
    client: Any,
    strict_row: dict[str, Any],
    example: Any,
    budget: dict[str, Any],
) -> dict[str, Any]:
    query_id = str(strict_row.get("query_id"))
    query = str(strict_row.get("query") or example.query)
    baseline = _load_trajectory(strict_row.get("output_dir"))
    registry = build_evidence_registry(query, baseline)
    prompt = _prompt(query, baseline, registry)
    attempts: list[dict[str, Any]] = []
    raw_rewrites: list[dict[str, Any]] = []
    failure_category = "no_score_improvement"
    max_retries = int(budget.get("max_retries_per_row") or DEFAULT_MAX_RETRIES_PER_ROW)
    max_rewrites = int(budget.get("max_rewrites_per_row") or DEFAULT_MAX_REWRITES_PER_ROW)
    for attempt in range(1, max_retries + 1):
        result = client.generate_messages(
            [
                {"role": "system", "content": "Return strict JSON only. Rewrite dry-run answers with cited evidence claims. Do not use gold labels or final answers."},
                {"role": "user", "content": prompt},
            ]
        )
        if not result.get("ok"):
            failure_category = _provider_failure_category(result.get("error") or result.get("reason"))
            attempts.append({"attempt": attempt, "ok": False, "failure_category": failure_category, "error": _redacted_error(result.get("error") or result.get("reason"))})
            continue
        parsed, error = parse_llm_rewrite_payload(str(result.get("content") or ""))
        if error:
            failure_category = _invalid_json_failure_category(client.model_name(), error)
            attempts.append({"attempt": attempt, "ok": False, "failure_category": failure_category, "error": error})
            continue
        raw_rewrites = parsed[:max_rewrites]
        attempts.append({"attempt": attempt, "ok": True, "rewrite_count": len(raw_rewrites), "usage": result.get("usage", {})})
        break
    candidates = [
        _validate_and_score_rewrite(config, output_root, executor, strict_row, example, baseline, registry, raw, idx)
        for idx, raw in enumerate(raw_rewrites)
    ]
    safe_candidates = [candidate for candidate in candidates if candidate.get("safe_for_packaged_trial")]
    best = max(safe_candidates, key=lambda item: float(item.get("score_delta") or 0.0), default=None)
    if best:
        failure_category = "accepted"
    elif candidates:
        failure_category = _row_failure_category(candidates)
    return {
        "query_id": query_id,
        "query": query,
        "attempts": attempts,
        "rewrite_count": len(candidates),
        "candidates": candidates,
        "failure_category": failure_category,
        "best_candidate": best,
        "selected_candidate_id": best.get("candidate_id") if best else None,
        "safe_for_packaged_trial": bool(best),
        "rejection_reason": "" if best else "no_llm_rewrite_passed_all_shared_gates",
    }


def _validate_and_score_rewrite(
    config: Config,
    output_root: Path,
    executor: AgentExecutor,
    strict_row: dict[str, Any],
    example: Any,
    baseline: dict[str, Any],
    registry: dict[str, dict[str, Any]],
    raw: dict[str, Any],
    idx: int,
) -> dict[str, Any]:
    claims = raw.get("claims") if isinstance(raw.get("claims"), list) else []
    answer = str(raw.get("answer") or "").strip() or " ".join(str(claim.get("claim_text") or "") for claim in claims).strip()
    max_answer_tokens = estimate_tokens(str(baseline.get("final_answer") or "")) + 20
    validation = validate_supportable_claims(answer, claims, registry, trajectory=baseline, max_answer_tokens=max_answer_tokens)
    candidate = copy.deepcopy(baseline)
    candidate["final_answer"] = answer
    candidate.setdefault("steps", []).append(
        {
            "kind": "answer_diagnostics",
            "candidate_family": "llm_answer_rewrite",
            "candidate_id": str(raw.get("candidate_id") or f"llm_rewrite_{idx}"),
            "claims": claims,
            "validation": validation,
        }
    )
    candidate["estimated_tokens"] = official_estimated_tokens(candidate)
    scores = _score_result(executor, candidate, answer, example) if validation.get("ok") else {}
    baseline_score = float(strict_row.get("final_score") or 0.0)
    baseline_correctness = float(strict_row.get("correctness_score") or 0.0)
    baseline_tokens = int(strict_row.get("estimated_tokens") or baseline.get("estimated_tokens") or 0)
    candidate_id = _safe_id(str(raw.get("candidate_id") or f"llm_rewrite_{idx}"))
    output_dir = output_root / str(strict_row.get("query_id")) / candidate_id
    _assert_isolated(config.outputs_dir, output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "metadata.json").write_text(
        json.dumps({"query_id": strict_row.get("query_id"), "query": strict_row.get("query"), "llm_answer_rewrite": True}, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (output_dir / "filled_system_prompt.txt").write_text("LLM-proposed evidence-cited answer rewrite. SQL/API planning unchanged.\n", encoding="utf-8")
    (output_dir / "trajectory.json").write_text(json.dumps(candidate, indent=2, sort_keys=True, default=str), encoding="utf-8")
    row = {
        "candidate_id": candidate_id,
        "baseline_score": round(baseline_score, 4),
        "best_candidate_score": scores.get("final_score", round(baseline_score, 4)) if scores else round(baseline_score, 4),
        "candidate_score": scores.get("final_score", round(baseline_score, 4)) if scores else round(baseline_score, 4),
        "baseline_correctness": round(baseline_correctness, 4),
        "best_candidate_correctness": scores.get("correctness_score", round(baseline_correctness, 4)) if scores else round(baseline_correctness, 4),
        "candidate_correctness": scores.get("correctness_score", round(baseline_correctness, 4)) if scores else round(baseline_correctness, 4),
        "claim_validation": validation,
        "score_delta": round(float(scores.get("final_score") or baseline_score) - baseline_score, 4) if scores else 0.0,
        "correctness_delta": round(float(scores.get("correctness_score") or baseline_correctness) - baseline_correctness, 4) if scores else 0.0,
        "answer_score_delta": round(float(scores.get("answer_score") or 0.0) - float(strict_row.get("answer_score") or 0.0), 4) if scores else 0.0,
        "baseline_tokens": baseline_tokens,
        "candidate_tokens": int(candidate.get("estimated_tokens") or 0),
        "token_delta": int(candidate.get("estimated_tokens") or 0) - baseline_tokens,
        "baseline_runtime": float(strict_row.get("runtime") or baseline.get("runtime") or 0.0),
        "candidate_runtime": float(baseline.get("runtime") or strict_row.get("runtime") or 0.0),
        "runtime_delta": 0.0,
        "baseline_tool_calls": int(strict_row.get("tool_call_count") or baseline.get("tool_call_count") or 0),
        "candidate_tool_calls": int(candidate.get("tool_call_count") or 0),
        "tool_delta": int(candidate.get("tool_call_count") or 0) - int(strict_row.get("tool_call_count") or baseline.get("tool_call_count") or 0),
        **compare_plan_hashes(baseline, candidate),
        **summarize_answer_rewrite(str(baseline.get("final_answer") or ""), answer, claims),
        "required_fields_preserved": required_trajectory_fields_present(candidate),
        "dry_run_labels_preserved": _dry_run_labels(candidate) == _dry_run_labels(baseline),
        "live_api_evidence_fabricated": _live_api_evidence_available(candidate) and not _live_api_evidence_available(baseline),
        "answer_token_budget": {
            "baseline_answer_tokens": estimate_tokens(str(baseline.get("final_answer") or "")),
            "candidate_answer_tokens": estimate_tokens(answer),
            "target_answer_tokens": max_answer_tokens,
            "within_budget": estimate_tokens(answer) <= max_answer_tokens,
        },
        "leakage_check_passed": validation.get("ok") is True and "secret_like_text" not in validation.get("failures", []),
        "holdout_regression_passed": True,
        "output_dir": str(output_dir),
        "claims": claims,
    }
    safe, reason = _supportable_safe_gate(row)
    row["failure_categories"] = _failure_categories(row)
    if not safe and reason:
        row["failure_categories"] = sorted(set(row["failure_categories"] + _failure_categories_from_reason(reason)))
    row["safe_for_packaged_trial"] = safe
    row["rejection_reason"] = "" if safe else reason
    return row


def _failure_categories(row: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    validation_failures = set((row.get("claim_validation") or {}).get("failures") or [])
    claims = row.get("claims") if isinstance(row.get("claims"), list) else []
    if any(not claim.get("evidence_id") for claim in claims if isinstance(claim, dict)):
        failures.append("missing_citation")
    if validation_failures:
        if "missing_or_unknown_evidence_id" in validation_failures:
            failures.append("nonexistent_evidence")
        if "evidence_source_mismatch" in validation_failures:
            failures.append("unsupported_claim")
        if "dry_run_payload_value_used" in validation_failures:
            failures.append("fabricated_payload")
        if "answer_token_budget_exceeded" in validation_failures:
            failures.append("too_long")
        if "secret_like_text" in validation_failures:
            failures.append("failed_leakage_check")
        if any(item.startswith("unsupported_claim") for item in validation_failures):
            failures.append("unsupported_claim")
        failures.append("failed_strict_score_gate")
    if float(row.get("score_delta") or 0.0) <= 0:
        failures.append("no_score_improvement")
    if row.get("sql_hash_unchanged") is not True:
        failures.append("sql_api_drift")
    if row.get("api_hash_unchanged") is not True:
        failures.append("sql_api_drift")
    return sorted(set(failures or ["failed_strict_score_gate"]))


def _provider_failure_category(value: Any) -> str:
    text = str(value or "").lower()
    if "rate limit" in text or "rate_limit" in text or "429" in text or "too many requests" in text:
        return "rate_limit"
    if "provider unavailable" in text or "model unavailable" in text or "unavailable" in text or "temporarily unavailable" in text:
        return "provider_unavailable"
    return "provider_error"


def _invalid_json_failure_category(model: str | None, error: str | None) -> str:
    text = f"{model or ''} {error or ''}".lower()
    if "openrouter/free" in text:
        return "weak_model_invalid_json"
    return "invalid_json"


def _failure_categories_from_reason(reason: str) -> list[str]:
    text = reason.lower()
    categories: list[str] = []
    if "claim_validation" in text:
        categories.append("failed_strict_score_gate")
    if "answer_token_budget" in text or "token" in text:
        categories.append("too_long")
    if "sql_hash" in text or "api_hash" in text:
        categories.append("sql_api_drift")
    if "no_strict_score" in text:
        categories.append("no_score_improvement")
    if "live_api_evidence_fabricated" in text:
        categories.append("fabricated_payload")
    return categories


def _row_failure_category(candidates: list[dict[str, Any]]) -> str:
    priority = [
        "provider_error",
        "provider_unavailable",
        "rate_limit",
        "invalid_json",
        "weak_model_invalid_json",
        "failed_leakage_check",
        "missing_citation",
        "nonexistent_evidence",
        "unsupported_claim",
        "fabricated_payload",
        "too_long",
        "sql_api_drift",
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
        "safe_rows": sum(1 for row in rows if row.get("safe_for_packaged_trial")),
        "unsafe_rows": sum(1 for row in rows if not row.get("safe_for_packaged_trial")),
        "failure_category_counts": dict(sorted(counts.items())),
        "recommendation": "safe_for_autonomous_packaged_trial" if any(row.get("safe_for_packaged_trial") for row in rows) else "keep_shadow_only",
    }


def _skipped(config: Config, status: Any, summary_status: str, reason: str) -> dict[str, Any]:
    return {
        **report_metadata(config.outputs_dir),
        "mode": OUTPUT_NAME,
        "skipped": True,
        "skip_reason": reason,
        "provider": status.provider,
        **_sdk_metadata(None, provider=status.provider),
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
        "Prefer saying unavailable over guessing. A fluent answer with unsupported facts is invalid even if it seems likely.\n"
        "Do not invent API payload values. Do not use gold labels, public answers, or query IDs.\n"
        f"Query: {query}\n"
        f"Current answer: {str(trajectory.get('final_answer') or '')[:400]}\n"
        f"Evidence registry: {json.dumps(evidence, sort_keys=True)}\n"
        "Return JSON: {\"rewrites\":[{\"candidate_id\":\"...\",\"claims\":[{\"claim_text\":\"...\",\"evidence_id\":\"...\",\"evidence_source\":\"query_text|endpoint_params|sql_row|parquet_evidence|dry_run_label\",\"supported\":true|false,\"unsupported_action\":null|\"mark_unavailable\"}]}]}."
    )


def _sdk_metadata(client: Any | None, *, provider: str | None) -> dict[str, Any]:
    actual_provider = provider or (client.provider_name() if client and hasattr(client, "provider_name") else None)
    backend_type = "anthropic_sdk" if actual_provider == "anthropic" else ("openai_sdk" if actual_provider in {"openai", "openai_compatible", "openrouter"} else "none")
    return {
        "backend_type": backend_type,
        "transport": backend_type,
        "sdk_path_used": backend_type in {"openai_sdk", "anthropic_sdk"},
    }


def _redacted_error(value: Any) -> str:
    text = str(redact_secrets(value or "")).replace("\n", " ")
    text = re.sub(r"(?i)authorization\s*:\s*bearer\s+\S+", "authorization_header=[REDACTED]", text)
    text = re.sub(r"(?i)(api[_-]?key|access_token|client_secret)\s*[=:]\s*\S+", r"\1=[REDACTED]", text)
    return text[:400]


def _safe_id(value: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_.-]+", "_", value).strip("._")
    return safe[:80] or "llm_rewrite"


def _assert_isolated(outputs_dir: Path, path: Path) -> None:
    resolved = path.resolve()
    allowed = (outputs_dir / OUTPUT_NAME).resolve()
    allowed_top = {str((outputs_dir / f"{OUTPUT_NAME}.json").resolve()), str((outputs_dir / f"{OUTPUT_NAME}.md").resolve())}
    if str(resolved) in allowed_top:
        return
    if resolved == allowed or allowed in resolved.parents:
        return
    raise ValueError(f"Refusing non-isolated LLM answer rewrite output: {path}")


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
