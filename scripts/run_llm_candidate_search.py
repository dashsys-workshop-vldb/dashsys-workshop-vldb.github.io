#!/usr/bin/env python
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.candidate_context_builder import build_candidate_context
from dashagent.config import Config
from dashagent.eval_harness import EvalHarness
from dashagent.executor import AgentExecutor
from dashagent.llm_candidate_generator import (
    build_llm_candidate_prompt,
    llm_candidate_search_status,
    normalize_llm_candidate,
    parse_llm_candidates,
)
from dashagent.llm_client import get_llm_client
from dashagent.report_run import report_metadata
from scripts.load_local_env import load_local_env
from scripts.run_official_token_reduction_eval import _load_json, _load_trajectory


MAX_TARGET_ROWS = 10
MAX_CANDIDATES_PER_ROW = 5
MAX_RETRIES_PER_ROW = 2


def main() -> int:
    config = Config.from_env(ROOT)
    payload = run_llm_candidate_search(config)
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    json_path = config.outputs_dir / "llm_candidate_search.json"
    md_path = config.outputs_dir / "llm_candidate_search.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "status": payload["summary"]["status"]}, indent=2, sort_keys=True))
    return 0


def run_llm_candidate_search(config: Config) -> dict[str, Any]:
    load_local_env(config.project_root)
    status = llm_candidate_search_status()
    mining = _load_json(config.outputs_dir / "score_component_error_report.json") or _load_json(config.outputs_dir / "low_score_failure_mining_report.json")
    if not status.available:
        return _skipped(config, status, "skipped_no_llm_key", status.reason)

    client = get_llm_client(status.provider)
    if not client.available():
        return _skipped(config, status, "skipped_no_llm_key", "configured client is unavailable")

    executor = AgentExecutor(config)
    examples = {example.query_id: example for example in EvalHarness(config).load_examples()}
    strict = _load_json(config.outputs_dir / "eval_results_strict.json")
    strict_rows = {
        str(row.get("query_id")): row
        for row in strict.get("rows", [])
        if row.get("strategy") == "SQL_FIRST_API_VERIFY"
    }
    target_ids = _target_ids(mining, strict_rows)[:MAX_TARGET_ROWS]
    rows = []
    for query_id in target_ids:
        row = strict_rows.get(query_id)
        if not row:
            rows.append({"query_id": query_id, "failure_category": "provider_error", "rejection_reason": "missing_strict_row"})
            continue
        rows.append(_run_row(config, executor, client, row, examples.get(query_id)))
    summary = _summary(rows, status)
    return {
        **report_metadata(config.outputs_dir),
        "mode": "llm_candidate_search",
        "skipped": False,
        "provider": status.provider,
        "model": client.model_name(),
        **_sdk_metadata(client, provider=status.provider),
        "budget": {
            "max_target_rows": MAX_TARGET_ROWS,
            "max_candidates_per_row": MAX_CANDIDATES_PER_ROW,
            "max_retries_per_row": MAX_RETRIES_PER_ROW,
        },
        "packaged_execution_changed": False,
        "writes_eval_outputs": False,
        "writes_final_submission": False,
        "rows": rows,
        "summary": summary,
        "notes": [
            "LLM candidates are diagnostic only and are never trusted directly.",
            "Provider keys are never printed or written; provider errors are redacted.",
            "Candidates must pass deterministic validators before any later isolated execution/scoring.",
        ],
    }


def _run_row(config: Config, executor: AgentExecutor, client: Any, row: dict[str, Any], example: Any | None) -> dict[str, Any]:
    query_id = str(row.get("query_id"))
    query = str(row.get("query") or (example.query if example else ""))
    trajectory = _load_trajectory(row.get("output_dir"))
    context = build_candidate_context(query, executor.schema_index, executor.endpoint_catalog)
    endpoint_summary = [
        {"id": endpoint.id, "method": endpoint.method, "path": endpoint.path, "domains": endpoint.domains}
        for endpoint in executor.endpoint_catalog.endpoints[:20]
    ]
    prompt = build_llm_candidate_prompt(
        query=query,
        schema_context=_compact_context(context),
        endpoint_catalog_summary=endpoint_summary,
        failed_trajectory_summary=_trajectory_summary(trajectory),
        answer_shape=str((row.get("answer_shape_category") or "unknown")),
    )
    attempts = []
    raw_candidates: list[dict[str, Any]] = []
    failure_category = None
    for attempt in range(1, MAX_RETRIES_PER_ROW + 1):
        result = client.generate_messages(
            [
                {"role": "system", "content": "You propose diagnostic SQL/API candidates as strict JSON only. Do not use gold labels or final answers."},
                {"role": "user", "content": prompt},
            ]
        )
        if not result.get("ok"):
            failure_category = "provider_error"
            attempts.append({"attempt": attempt, "ok": False, "failure_category": failure_category, "error": _redacted_error(result.get("error") or result.get("reason"))})
            continue
        parsed, error = parse_llm_candidates(str(result.get("content") or ""))
        if error:
            failure_category = "invalid_json"
            attempts.append({"attempt": attempt, "ok": False, "failure_category": failure_category, "error": error})
            continue
        raw_candidates = parsed[:MAX_CANDIDATES_PER_ROW]
        attempts.append({"attempt": attempt, "ok": True, "candidate_count": len(raw_candidates), "usage": result.get("usage", {})})
        break
    candidates = [_validate_candidate(executor, raw, query=query) for raw in raw_candidates]
    if candidates:
        failure_category = _row_failure_category(candidates)
    return {
        "query_id": query_id,
        "query": query,
        "attempts": attempts,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "failure_category": failure_category or "no_score_improvement",
        "safe_for_packaged_trial": False,
        "rejection_reason": "LLM candidates remain diagnostic until deterministic isolated execution search selects a score-improving candidate.",
    }


def _validate_candidate(executor: AgentExecutor, raw: dict[str, Any], *, query: str) -> dict[str, Any]:
    candidate = normalize_llm_candidate(raw)
    failures = []
    if not candidate.get("leakage_check_passed"):
        failures.append("failed_leakage_check")
    sql = candidate.get("sql")
    if sql:
        validation = executor.sql_validator.validate(str(sql))
        candidate["sql_validation"] = validation.to_dict()
        if not validation.ok:
            failures.append("failed_sql_validation")
    api = candidate.get("api_call") if isinstance(candidate.get("api_call"), dict) else {}
    path = api.get("path") or api.get("url")
    if path:
        validation = executor.api_validator.validate(str(api.get("method") or "GET").upper(), str(path), api.get("params") if isinstance(api.get("params"), dict) else {}, {})
        candidate["api_validation"] = validation.to_dict()
        if not validation.ok:
            failures.append("failed_api_validation")
    if not failures:
        failures.append("failed_strict_score_gate")
    candidate["failure_categories"] = failures
    candidate["safe_for_packaged_trial"] = False
    return candidate


def _row_failure_category(candidates: list[dict[str, Any]]) -> str:
    priority = [
        "failed_leakage_check",
        "failed_sql_validation",
        "failed_api_validation",
        "failed_strict_score_gate",
        "no_score_improvement",
    ]
    seen = {failure for candidate in candidates for failure in candidate.get("failure_categories", [])}
    for item in priority:
        if item in seen:
            return item
    return "no_score_improvement"


def _target_ids(report: dict[str, Any], strict_rows: dict[str, dict[str, Any]]) -> list[str]:
    summary = report.get("summary") or {}
    ids = summary.get("top_api_correct_answer_weak_rows") or summary.get("top_10_target_rows") or summary.get("top_target_rows") or []
    if ids:
        return [str(item) for item in ids]
    ranked = sorted(strict_rows.values(), key=lambda row: (float(row.get("final_score") or 1.0), float(row.get("answer_score") or 1.0)))
    return [str(row.get("query_id")) for row in ranked]


def _summary(rows: list[dict[str, Any]], status: Any) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for row in rows:
        key = str(row.get("failure_category") or "unknown")
        counts[key] = counts.get(key, 0) + 1
    return {
        "status": "completed",
        "provider": status.provider,
        "total_rows": len(rows),
        "candidate_rows": sum(1 for row in rows if row.get("candidate_count")),
        "safe_rows": 0,
        "unsafe_rows": len(rows),
        "failure_category_counts": dict(sorted(counts.items())),
        "recommendation": "keep_shadow_only",
    }


def _skipped(config: Config, status: Any, summary_status: str, reason: str) -> dict[str, Any]:
    return {
        **report_metadata(config.outputs_dir),
        "mode": "llm_candidate_search",
        "skipped": True,
        "skip_reason": reason,
        "provider": status.provider,
        **_sdk_metadata(None, provider=status.provider),
        "packaged_execution_changed": False,
        "writes_eval_outputs": False,
        "writes_final_submission": False,
        "rows": [],
        "summary": {
            "status": summary_status,
            "safe_rows": 0,
            "unsafe_rows": 0,
            "failure_category_counts": {},
            "recommendation": "keep_shadow_only",
        },
    }


def _compact_context(context: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_tables": context.get("candidate_tables", [])[:8],
        "candidate_apis": [
            {key: item.get(key) for key in ["id", "method", "path", "use_when"] if item.get(key)}
            for item in (context.get("candidate_apis") or [])[:8]
            if isinstance(item, dict)
        ],
        "endpoint_family_ranking": context.get("endpoint_family_ranking", {}),
    }


def _trajectory_summary(trajectory: dict[str, Any]) -> dict[str, Any]:
    return {
        "selected_sql": next((step.get("sql") for step in trajectory.get("steps", []) if step.get("kind") == "sql_call"), None),
        "selected_api": [
            {"method": step.get("method"), "path": step.get("url"), "params": step.get("params")}
            for step in trajectory.get("steps", [])
            if step.get("kind") == "api_call"
        ],
        "final_answer_preview": str(trajectory.get("final_answer") or "")[:300],
    }


def _redacted_error(value: Any) -> str:
    text = str(value or "").replace("\n", " ")
    text = re.sub(r"(?i)authorization\s*:\s*bearer\s+\S+", "authorization_header=[REDACTED]", text)
    text = re.sub(r"(?i)(api[_-]?key|access_token|client_secret)\s*[=:]\s*\S+", r"\1=[REDACTED]", text)
    return text[:400]


def _sdk_metadata(client: Any | None, *, provider: str | None) -> dict[str, Any]:
    actual_provider = provider or (client.provider_name() if client and hasattr(client, "provider_name") else None)
    backend_type = "anthropic_sdk" if actual_provider == "anthropic" else ("openai_sdk" if actual_provider in {"openai", "openai_compatible", "openrouter"} else "none")
    return {
        "backend_type": backend_type,
        "transport": backend_type,
        "sdk_path_used": backend_type in {"openai_sdk", "anthropic_sdk"},
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# LLM Candidate Search",
        "",
        f"- Status: `{summary['status']}`",
        f"- Provider: `{payload.get('provider')}`",
        f"- Skipped: {payload.get('skipped')}",
        f"- Rows: {summary.get('total_rows', 0)}",
        f"- Candidate rows: {summary.get('candidate_rows', 0)}",
        f"- Recommendation: `{summary['recommendation']}`",
        f"- Packaged execution changed: {payload.get('packaged_execution_changed')}",
        "",
        "## Failure Categories",
        "",
    ]
    counts = summary.get("failure_category_counts") or {}
    if counts:
        lines.extend(f"- `{key}`: {value}" for key, value in counts.items())
    else:
        lines.append("- None.")
    if payload.get("skip_reason"):
        lines.extend(["", f"Skip reason: {payload['skip_reason']}"])
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
