#!/usr/bin/env python
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.executor import AgentExecutor
from dashagent.llm_candidate_generator import (
    build_llm_candidate_prompt,
    llm_candidate_search_status,
    normalize_llm_candidate,
    parse_llm_candidate_response,
    sanitize_for_llm_prompt,
    validate_llm_candidate,
)
from dashagent.llm_client import get_llm_client
from dashagent.report_run import report_metadata
from scripts.run_official_token_reduction_eval import _load_json, _load_trajectory


OUTPUT_NAME = "llm_candidate_search"
MAX_TARGET_ROWS = 3


def main() -> int:
    config = Config.from_env(ROOT)
    payload = run_llm_candidate_search(config)
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    json_path = config.outputs_dir / f"{OUTPUT_NAME}.json"
    md_path = config.outputs_dir / f"{OUTPUT_NAME}.md"
    handoff_path = config.outputs_dir / "score075_llm_search_handoff.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    handoff_path.write_text(render_handoff(payload), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "status": payload["summary"]["status"]}, indent=2, sort_keys=True))
    return 0


def run_llm_candidate_search(config: Config) -> dict[str, Any]:
    status = llm_candidate_search_status()
    mining = _load_json(config.outputs_dir / "low_score_failure_mining_report.json")
    if not status.available:
        return _skipped_payload(config, status.provider, status.reason, "skipped_no_llm_key", mining)
    return _run_available_llm_search(config, status.provider, mining)


def _skipped_payload(
    config: Config,
    provider: str | None,
    reason: str,
    status_name: str,
    mining: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
            **report_metadata(config.outputs_dir),
            "mode": OUTPUT_NAME,
            "skipped": True,
        "skip_reason": reason,
        "provider": provider,
        "dependencies": ["codex/score075-candidate-generation", "codex/score075-execution-selector"],
            "packaged_execution_changed": False,
            "writes_eval_outputs": False,
            "writes_final_submission": False,
        "artifact_isolation": _artifact_isolation(),
            "rows": [],
            "summary": {
            "status": status_name,
                "safe_rows": 0,
                "unsafe_rows": 0,
            "candidate_rows": 0,
            "target_rows": 0,
                "recommendation": "keep_shadow_only",
            },
        "target_rows_available": ((mining or {}).get("summary") or {}).get("top_10_target_rows", []),
            "notes": [
                "No LLM key is available, so optional LLM candidate search was skipped.",
                "Validation passes because LLM search is optional and isolated.",
            ],
        }


def _run_available_llm_search(config: Config, provider: str | None, mining: dict[str, Any]) -> dict[str, Any]:
    strict = _load_json(config.outputs_dir / "eval_results_strict.json")
    context = _load_json(config.outputs_dir / "candidate_context_report.json")
    hidden = _load_json(config.outputs_dir / "hidden_style_eval.json")
    strict_rows = {
        str(row.get("query_id")): row
        for row in strict.get("rows", [])
        if row.get("strategy") == "SQL_FIRST_API_VERIFY"
    }
    context_by_id = {str(row.get("query_id")): row for row in context.get("rows", [])}
    target_ids = _target_ids(mining, strict_rows)
    output_root = config.outputs_dir / OUTPUT_NAME
    _assert_isolated_output(config.outputs_dir, output_root)
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)

    executor = AgentExecutor(config)
    client = get_llm_client(provider)
    if not client.available():
        return _skipped_payload(config, provider, "Configured LLM client is unavailable", "skipped_client_unavailable", mining)

    rows: list[dict[str, Any]] = []
    for query_id in target_ids:
        strict_row = strict_rows.get(str(query_id))
        if not strict_row:
            rows.append(_skipped_row(str(query_id), "missing_strict_row"))
            continue
        rows.append(_search_row(config, output_root, executor, client, strict_row, context_by_id.get(str(query_id), {})))

    safe_count = sum(1 for row in rows for candidate in row.get("candidates", []) if candidate.get("safe_for_execution_search"))
    candidate_count = sum(len(row.get("candidates", [])) for row in rows)
    return {
        **report_metadata(config.outputs_dir),
        "mode": OUTPUT_NAME,
        "skipped": False,
        "provider": client.provider_name(),
        "model": client.model_name(),
        "dependencies": ["codex/score075-candidate-generation", "codex/score075-execution-selector"],
        "packaged_execution_changed": False,
        "writes_eval_outputs": False,
        "writes_final_submission": False,
        "artifact_isolation": _artifact_isolation(),
        "candidate_prompt_constraints": [
            "no gold SQL/API/answers",
            "no public-query answers",
            "no query-id or exact full-query triggers",
            "all outputs require deterministic validators before execution search",
        ],
        "hidden_style_gate": _hidden_summary(hidden),
        "rows": rows,
        "summary": {
            "status": "completed",
            "target_rows": len(rows),
            "candidate_rows": candidate_count,
            "safe_rows": safe_count,
            "unsafe_rows": candidate_count - safe_count,
            "recommendation": "candidates_ready_for_execution_selector" if safe_count else "keep_shadow_only",
        },
        "notes": [
            "LLM candidates are diagnostic only and are not executed or packaged by this worker.",
            "Execution/scoring remains the responsibility of the execution-selector and integration workers.",
        ],
    }


def _search_row(
    config: Config,
    output_root: Path,
    executor: AgentExecutor,
    client: Any,
    strict_row: dict[str, Any],
    context_row: dict[str, Any],
) -> dict[str, Any]:
    query_id = str(strict_row.get("query_id"))
    query = str(strict_row.get("query") or "")
    trajectory = _load_trajectory(strict_row.get("output_dir"))
    prompt = build_llm_candidate_prompt(
        query=query,
        schema_context=_schema_context(context_row),
        endpoint_catalog_summary=_endpoint_catalog_summary(executor),
        failed_trajectory_summary=_trajectory_summary(trajectory),
        answer_shape=_answer_shape(query, strict_row),
    )
    result = client.generate(
        "You propose isolated diagnostic SQL/API candidates. Output strict JSON only.",
        prompt,
        tools=None,
    )
    raw_candidates = parse_llm_candidate_response(str(result.get("content") or ""))
    candidates: list[dict[str, Any]] = []
    row_dir = output_root / query_id
    _assert_isolated_output(config.outputs_dir, row_dir)
    row_dir.mkdir(parents=True, exist_ok=True)
    for index, raw in enumerate(raw_candidates[:3], start=1):
        candidate = normalize_llm_candidate(
            raw,
            generalizable_family=str(raw.get("generalizable_family") or _answer_shape(query, strict_row)),
            query=query,
        )
        if candidate.get("candidate_id") == "llm_candidate":
            candidate["candidate_id"] = f"llm_candidate_{index}"
        validation = validate_llm_candidate(
            candidate,
            sql_validator=executor.sql_validator,
            api_validator=executor.api_validator,
        )
        candidate_row = {
            **candidate,
            **validation,
            "diagnostic_only": True,
            "packaged_execution_changed": False,
        }
        candidate_dir = row_dir / str(candidate_row["candidate_id"])
        _assert_isolated_output(config.outputs_dir, candidate_dir)
        candidate_dir.mkdir(parents=True, exist_ok=True)
        (candidate_dir / "candidate.json").write_text(
            json.dumps(candidate_row, indent=2, sort_keys=True, default=str),
            encoding="utf-8",
        )
        candidates.append(candidate_row)
    return {
        "query_id": query_id,
        "query": query,
        "provider": result.get("provider"),
        "model": result.get("model"),
        "llm_response_ok": result.get("ok") is True,
        "llm_error": result.get("error"),
        "prompt_token_proxy_chars": len(prompt),
        "raw_candidate_count": len(raw_candidates),
        "candidates": candidates,
        "safe_candidate_count": sum(1 for candidate in candidates if candidate.get("safe_for_execution_search")),
        "row_output_dir": str(row_dir),
    }


def _target_ids(mining: dict[str, Any], strict_rows: dict[str, dict[str, Any]]) -> list[str]:
    ids = [str(item) for item in ((mining.get("summary") or {}).get("top_10_target_rows") or [])]
    if not ids:
        ids = sorted(strict_rows)[:MAX_TARGET_ROWS]
    return ids[:MAX_TARGET_ROWS]


def _schema_context(context_row: dict[str, Any]) -> dict[str, Any]:
    return sanitize_for_llm_prompt(
        {
            "candidate_tables": context_row.get("candidate_tables", []),
            "candidate_apis": context_row.get("candidate_apis", []),
            "endpoint_family_ranking": context_row.get("endpoint_family_ranking", {}),
            "risk_level": context_row.get("risk_level"),
            "schema_vote_agreement": context_row.get("schema_vote_agreement"),
        },
        max_items=12,
    )


def _endpoint_catalog_summary(executor: AgentExecutor) -> list[dict[str, Any]]:
    rows = []
    for endpoint in executor.endpoint_catalog.endpoints:
        rows.append(
            {
                "id": endpoint.id,
                "method": endpoint.method,
                "path": endpoint.path,
                "use_when": endpoint.use_when,
                "common_params": endpoint.common_params,
                "path_params": endpoint.path_params,
                "domains": endpoint.domains,
            }
        )
    return rows


def _trajectory_summary(trajectory: dict[str, Any]) -> dict[str, Any]:
    return {
        "strategy": trajectory.get("strategy"),
        "route_type": trajectory.get("route_type"),
        "domain_type": trajectory.get("domain_type"),
        "tool_call_count": trajectory.get("tool_call_count"),
        "sql_call_count": trajectory.get("sql_call_count"),
        "api_call_count": trajectory.get("api_call_count"),
        "generated_sql": _first_sql(trajectory),
        "generated_api": _api_calls(trajectory),
        "validation_summaries": _validation_summaries(trajectory),
    }


def _first_sql(trajectory: dict[str, Any]) -> str | None:
    for step in trajectory.get("steps", []):
        if step.get("kind") == "sql_call" and step.get("sql"):
            return str(step.get("sql"))
    return None


def _api_calls(trajectory: dict[str, Any]) -> list[dict[str, Any]]:
    calls = []
    for step in trajectory.get("steps", []):
        if step.get("kind") == "api_call":
            calls.append(
                {
                    "method": step.get("method"),
                    "path": step.get("url") or step.get("path"),
                    "params": step.get("params", {}),
                    "dry_run": ((step.get("result") or {}).get("dry_run") is True),
                }
            )
    return calls[:3]


def _validation_summaries(trajectory: dict[str, Any]) -> list[dict[str, Any]]:
    summaries = []
    for step in trajectory.get("steps", []):
        if step.get("kind") == "validation":
            result = step.get("result") or {}
            summaries.append(
                {
                    "target": step.get("target"),
                    "ok": result.get("ok"),
                    "errors": result.get("errors", [])[:3],
                    "warnings": result.get("warnings", [])[:3],
                }
            )
    return summaries[:6]


def _answer_shape(query: str, strict_row: dict[str, Any]) -> str:
    lowered = query.lower()
    if "how many" in lowered or "count" in lowered:
        return "count"
    if lowered.startswith("list") or " all " in lowered:
        return "list"
    if any(word in lowered for word in ["status", "published", "date", "details", "detail"]):
        return "detail"
    if strict_row.get("answer_score") is not None and float(strict_row.get("answer_score") or 0) < 0.45:
        return "answer_format_repair"
    return "list_or_detail"


def _hidden_summary(hidden: dict[str, Any]) -> dict[str, Any]:
    summary = hidden.get("summary") or {}
    return {
        "total_cases": int(summary.get("total_cases") or 0),
        "passed_cases": int(summary.get("passed_cases") or 0),
        "family_stability_rate": float(summary.get("family_stability_rate") or 0.0),
        "schema_stability_rate": float(summary.get("schema_stability_rate") or 0.0),
    }


def _skipped_row(query_id: str, reason: str) -> dict[str, Any]:
    return {
        "query_id": query_id,
        "skipped": True,
        "skip_reason": reason,
        "candidates": [],
        "safe_candidate_count": 0,
    }


def _artifact_isolation() -> dict[str, Any]:
    return {
        "allowed_outputs": [
            f"outputs/{OUTPUT_NAME}.json",
            f"outputs/{OUTPUT_NAME}.md",
            "outputs/score075_llm_search_handoff.md",
            f"outputs/{OUTPUT_NAME}/<query_id>/<candidate_id>/candidate.json",
        ],
        "forbidden_outputs": [
            "outputs/eval/",
            "outputs/final_submission/",
            "packaged query output folders",
        ],
    }


def _assert_isolated_output(outputs_dir: Path, path: Path) -> None:
    resolved = path.resolve()
    allowed_root = (outputs_dir / OUTPUT_NAME).resolve()
    allowed_files = {
        (outputs_dir / f"{OUTPUT_NAME}.json").resolve(),
        (outputs_dir / f"{OUTPUT_NAME}.md").resolve(),
        (outputs_dir / "score075_llm_search_handoff.md").resolve(),
    }
    if resolved in allowed_files:
        return
    try:
        resolved.relative_to(allowed_root)
    except ValueError as exc:
        raise RuntimeError(f"LLM candidate search attempted to write outside isolated output root: {path}") from exc


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# LLM Candidate Search",
        "",
        f"- Status: `{summary['status']}`",
        f"- Provider: `{payload.get('provider')}`",
        f"- Skipped: {payload.get('skipped')}",
        f"- Target rows: {summary.get('target_rows', 0)}",
        f"- Candidate rows: {summary.get('candidate_rows', 0)}",
        f"- Safe for execution search: {summary.get('safe_rows', 0)}",
        f"- Recommendation: `{summary['recommendation']}`",
        f"- Packaged execution changed: {payload.get('packaged_execution_changed')}",
        f"- Writes official eval outputs: {payload.get('writes_eval_outputs')}",
        f"- Writes final submission: {payload.get('writes_final_submission')}",
    ]
    if payload.get("skip_reason"):
        lines.append(f"- Skip reason: {payload['skip_reason']}")
    if payload.get("rows"):
        lines.extend(["", "## Rows", ""])
        for row in payload["rows"]:
            lines.append(
                f"- `{row.get('query_id')}`: raw candidates {row.get('raw_candidate_count', 0)}, "
                f"safe {row.get('safe_candidate_count', 0)}"
            )
    return "\n".join(lines) + "\n"


def render_handoff(payload: dict[str, Any]) -> str:
    summary = payload.get("summary", {})
    return "\n".join(
        [
            "# Worker 7 LLM Search Handoff",
            "",
            "- Branch: `codex/score075-llm-search`",
            "- Dependencies: `codex/score075-candidate-generation`, `codex/score075-execution-selector`",
            "- Allowed files: `dashagent/llm_candidate_generator.py`, `scripts/run_llm_candidate_search.py`, LLM-search tests, `outputs/llm_candidate_search.*`, `outputs/score075_llm_search_handoff.md`",
            f"- Status: `{summary.get('status')}`",
            f"- Recommendation: `{summary.get('recommendation')}`",
            f"- Candidate rows: {summary.get('candidate_rows', 0)}",
            f"- Safe for execution search: {summary.get('safe_rows', 0)}",
            "- Packaged execution changed: false",
            "- Final submission touched: false",
            "",
            "## Notes",
            "",
            "- No candidate is packaged by this worker.",
            "- All keyed candidates must pass deterministic leakage, SQL, and API validators before handoff.",
            "- Gold labels, gold SQL/API, gold answers, query IDs, and exact public query strings are not prompt inputs or trigger features.",
        ]
    ) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
