#!/usr/bin/env python
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.report_run import report_metadata
from scripts.run_official_token_reduction_eval import _load_json, _load_trajectory


OUTPUT_NAME = "live_mode_readiness_report"
ADOBE_CREDENTIAL_ENV = ["CLIENT_ID", "CLIENT_SECRET", "IMS_ORG", "SANDBOX", "ACCESS_TOKEN", "ADOBE_BASE_URL"]
DRY_RUN_PHRASES = [
    "dry-run",
    "dry run",
    "credentials unavailable",
    "live api verification was not executed",
    "requires live api evidence",
    "unavailable in dry-run mode",
]


def main() -> int:
    config = Config.from_env(ROOT)
    payload = run_live_mode_readiness_check(config)
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    json_path = config.outputs_dir / f"{OUTPUT_NAME}.json"
    md_path = config.outputs_dir / f"{OUTPUT_NAME}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "diagnostic_only": payload["summary"]["diagnostic_only"]}, indent=2, sort_keys=True))
    return 0


def run_live_mode_readiness_check(config: Config) -> dict[str, Any]:
    strict = _load_json(config.outputs_dir / "eval_results_strict.json")
    credential_visibility = {name: bool(os.getenv(name)) for name in ADOBE_CREDENTIAL_ENV}
    all_credentials_visible = all(credential_visibility.values())
    rows = []
    for strict_row in strict.get("rows", []):
        if strict_row.get("strategy") != "SQL_FIRST_API_VERIFY":
            continue
        trajectory = _load_trajectory(strict_row.get("output_dir"))
        rows.append(_row(strict_row, trajectory))
    summary = _summary(rows, credential_visibility, all_credentials_visible)
    return {
        **report_metadata(config.outputs_dir),
        "mode": OUTPUT_NAME,
        "diagnostic_only": not all_credentials_visible,
        "packaged_execution_changed": False,
        "dry_run_behavior_changed": False,
        "final_answers_changed": False,
        "credential_visibility": credential_visibility,
        "rows": rows,
        "summary": summary,
        "notes": [
            "This report is diagnostic unless real Adobe credentials are present.",
            "Credential values are never printed or written, only booleans.",
            "No live evidence is fabricated and dry-run answers are not changed by this report.",
        ],
    }


def _row(strict_row: dict[str, Any], trajectory: dict[str, Any]) -> dict[str, Any]:
    answer = str(trajectory.get("final_answer") or "")
    answer_lower = answer.lower()
    dry_api_calls = []
    live_api_calls = []
    skipped_api_guard = []
    schema_safe = True
    for step in trajectory.get("steps", []):
        if step.get("kind") == "api_call":
            result = step.get("result") or {}
            call = {"method": step.get("method"), "url": step.get("url"), "dry_run": bool(result.get("dry_run"))}
            if result.get("dry_run"):
                dry_api_calls.append(call)
            elif result.get("ok"):
                live_api_calls.append(call)
        if step.get("kind") == "api_skip_guard":
            skipped_api_guard.append(step)
    schema_safe = all(field in trajectory for field in ["final_answer", "tool_call_count", "runtime", "estimated_tokens", "steps"])
    dry_phrases = [phrase for phrase in DRY_RUN_PHRASES if phrase in answer_lower]
    return {
        "query_id": strict_row.get("query_id"),
        "query": strict_row.get("query"),
        "answer_family": _family_from_query(str(strict_row.get("query") or "")),
        "final_score": strict_row.get("final_score"),
        "api_score": strict_row.get("api_score"),
        "answer_score": strict_row.get("answer_score"),
        "dry_run_api_call_count": len(dry_api_calls),
        "live_api_ok_call_count": len(live_api_calls),
        "dry_run_phrases_in_answer": dry_phrases,
        "dry_run_dependent_answer": bool(dry_phrases or dry_api_calls),
        "sql_only_skip_guard_checkpoints": skipped_api_guard,
        "trajectory_schema_safe": schema_safe,
        "requires_live_api_payload": bool(dry_api_calls and dry_phrases),
    }


def _family_from_query(query: str) -> str:
    lowered = query.lower()
    if "batch" in lowered:
        return "batch"
    if "tag" in lowered:
        return "tags"
    if "merge polic" in lowered:
        return "merge_policy"
    if "segment job" in lowered:
        return "segment_jobs"
    if "segment definition" in lowered:
        return "segment_definitions"
    if "observability" in lowered or "timeseries" in lowered or "ingestion record" in lowered:
        return "observability_metrics"
    if "schema" in lowered or "dataset" in lowered:
        return "schema_dataset"
    if "journey" in lowered or "campaign" in lowered:
        return "journey"
    return "generic"


def _summary(rows: list[dict[str, Any]], credential_visibility: dict[str, bool], all_credentials_visible: bool) -> dict[str, Any]:
    dry_rows = [row for row in rows if row.get("dry_run_dependent_answer")]
    return {
        "credential_keys_visible": credential_visibility,
        "all_adobe_credentials_visible": all_credentials_visible,
        "diagnostic_only": not all_credentials_visible,
        "total_rows": len(rows),
        "dry_run_dependent_rows": len(dry_rows),
        "dry_run_dependent_families": dict(Counter(str(row.get("answer_family")) for row in dry_rows)),
        "sql_only_skip_guard_rows": sum(1 for row in rows if row.get("sql_only_skip_guard_checkpoints")),
        "trajectory_schema_safe_rows": sum(1 for row in rows if row.get("trajectory_schema_safe")),
        "live_mode_changes_enabled": False,
        "final_answers_changed": False,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Live-Mode Readiness Report",
        "",
        f"- All Adobe credentials visible: {summary['all_adobe_credentials_visible']}",
        f"- Diagnostic only: {summary['diagnostic_only']}",
        f"- Dry-run dependent rows: {summary['dry_run_dependent_rows']}",
        f"- Dry-run dependent families: {summary['dry_run_dependent_families']}",
        f"- Live-mode changes enabled: {summary['live_mode_changes_enabled']}",
        "",
        "## Dry-Run Dependent Rows",
        "",
    ]
    for row in payload["rows"]:
        if not row.get("dry_run_dependent_answer"):
            continue
        lines.append(
            f"- `{row.get('query_id')}` family={row.get('answer_family')} dry_api_calls={row.get('dry_run_api_call_count')} "
            f"phrases={row.get('dry_run_phrases_in_answer')}"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
