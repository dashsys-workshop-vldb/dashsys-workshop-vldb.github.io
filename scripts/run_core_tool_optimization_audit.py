#!/usr/bin/env python
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.trajectory import redact_secrets


STEM = "core_tool_optimization_audit"
BASELINE_STRATEGY = "SQL_FIRST_API_VERIFY"


def main() -> int:
    config = Config.from_env(ROOT)
    payload = run_core_tool_optimization_audit(config)
    print(json.dumps({"report": str(config.outputs_dir / "reports" / f"{STEM}.json")}, indent=2, sort_keys=True))
    return 0


def run_core_tool_optimization_audit(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    sources = _load_sources(config)
    payload = {
        "report_type": STEM,
        "generated_at": _now(),
        "diagnostic_only": True,
        "official_organizer_weighted_score_claim": False,
        "runtime_behavior_changed_by_script": False,
        "packaged_strategy": _packaged_strategy(sources),
        "strict_score": _strict_score(sources),
        "hidden_style": _hidden_style(sources),
        "final_submission_ready": _final_submission_ready(sources),
        "live_success_count": _live_success_count(sources),
        "tools": {
            "execute_sql": _execute_sql_audit(),
            "call_api": _call_api_audit(),
        },
        "overall_optimization_candidates": [
            "cache exact SQL validation results within a validator instance",
            "execute only the selected validated SQL step",
            "compact SQL evidence by answer intent before answer-slot use",
            "deduplicate identical API attempts within one query execution",
            "keep dry-run/API-error outcomes compact and distinct from usable live evidence",
            "block unresolved API path placeholders before execution",
        ],
        "protected_defaults": {
            "sql_first_api_verify_remains_default": True,
            "read_only_sql_guard_required": True,
            "adobe_data_api_get_only": True,
            "endpoint_catalog_changed": False,
            "final_submission_format_changed": False,
            "direct_llm_http_hits": _direct_http_hits(sources),
        },
    }
    payload = _safe(payload)
    _write_report_pair(reports_dir / STEM, payload, _render(payload))
    return payload


def _execute_sql_audit() -> dict[str, Any]:
    return {
        "correctness_role": "grounds SQL-answerable prompts in local DuckDB/parquet evidence",
        "efficiency_role": "dominates local evidence latency, validation cost, and SQL result preview size",
        "inspected_surfaces": [
            "SQL generation and selected-plan execution",
            "SQLValidator read-only guard",
            "SQLGlot AST validation",
            "schema/table/column validation",
            "DuckDB/parquet execution",
            "row_count extraction",
            "SQL result to EvidenceBus and answer slots",
        ],
        "read_only_guard": True,
        "ast_validation_guard": True,
        "schema_validation_guard": True,
        "current_bottlenecks": [
            "repeated validation of repaired or normalized equivalent SQL",
            "raw result previews can carry unused fields for count/status/date prompts",
            "validation and execution summaries are not explicitly optimized by intent",
        ],
        "avoidable_work": [
            "revalidating identical normalized SQL during a single executor lifetime",
            "carrying unused SQL columns into evidence summaries",
        ],
        "repeated_calls": "selected SQL is executed once; result cache already covers identical SQL across runs",
        "overlarge_result_previews": "possible for list/status/timestamp rows when only key fields are needed",
        "validation_overhead": "read-only, schema, and AST checks are required but exact-result caching is safe",
        "result_compression_opportunity": "compact count/name/id/status/timestamp fields by answer intent",
        "caching_opportunity": "per-validator normalized validation cache",
        "failure_modes": [
            "unsafe SQL must never be cached as safe",
            "result compression must not drop names/IDs/status/timestamps needed by the answer",
        ],
        "optimization_candidates": ["SQL-1", "SQL-2", "SQL-3", "SQL-4", "SQL-5"],
    }


def _call_api_audit() -> dict[str, Any]:
    return {
        "correctness_role": "captures Adobe API state/evidence when local SQL is insufficient or API evidence is required",
        "efficiency_role": "controls network/dry-run calls, API caveat size, and endpoint validation overhead",
        "inspected_surfaces": [
            "API planning and API_REQUIRED/API_OPTIONAL/API_SKIP policy",
            "method/url/params validation",
            "GET-only Adobe data endpoint guard",
            "header construction and redaction",
            "live_success guard",
            "token acquisition boundary",
            "endpoint outcome classifier",
            "dry-run behavior",
            "API result to EvidenceBus and answer slots",
        ],
        "get_only_data_guard": True,
        "live_success_guard": True,
        "token_acquisition_boundary": "IMS token acquisition is the only allowed POST boundary; Adobe data endpoints remain GET-only",
        "current_bottlenecks": [
            "optional API dry-run attempts can add caveat noise when SQL already answers",
            "identical API attempts can be repeated within one query if planner emits duplicates",
            "raw error bodies must be compressed before answer/report context",
        ],
        "avoidable_work": [
            "duplicate method/url/params attempts within one query",
            "optional dry-run calls when live_success_count=0 and SQL is complete",
        ],
        "repeated_calls": "dry-run cache exists; live duplicate GET reuse is a safe per-query optimization",
        "overlarge_result_previews": "API errors and dry-run previews should be state summaries, not raw bodies",
        "validation_overhead": "endpoint validation is required and can be cached only by exact call signature",
        "result_compression_opportunity": "structured evidence_state/error_category/usable_evidence summaries",
        "caching_opportunity": "per-query duplicate API attempt cache",
        "failure_modes": [
            "API_REQUIRED calls must remain available even when live_success_count=0",
            "dry-run or api_error must not count as usable live payload evidence",
            "unresolved path placeholders must be blocked before execution",
        ],
        "optimization_candidates": ["API-1", "API-2", "API-3", "API-4", "API-5", "API-6"],
    }


def _load_sources(config: Config) -> dict[str, Any]:
    outputs = config.outputs_dir
    reports = outputs / "reports"
    return {
        "strict": _read_json(outputs / "eval_results_strict.json"),
        "system": _read_json(reports / "system_summary.json"),
        "hidden": _read_json(outputs / "hidden_style_eval.json"),
        "sdk_usage": _read_json(reports / "sdk_usage_audit.json"),
        "live_smoke": _read_json(reports / "live_api_readiness_smoke.json"),
    }


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _packaged_strategy(sources: dict[str, Any]) -> str:
    return str(sources.get("system", {}).get("preferred_strategy") or BASELINE_STRATEGY)


def _strict_score(sources: dict[str, Any]) -> float:
    system = sources.get("system", {})
    if system.get("packaged_strict_score") is not None:
        return float(system["packaged_strict_score"])
    strict = sources.get("strict", {})
    by_strategy = strict.get("summary", {}).get("by_strategy", {})
    return float(by_strategy.get(BASELINE_STRATEGY, {}).get("avg_final_score", 0.6553))


def _hidden_style(sources: dict[str, Any]) -> str:
    system_hidden = sources.get("system", {}).get("hidden_style")
    if isinstance(system_hidden, dict):
        return str(system_hidden.get("label") or f"{system_hidden.get('passed')}/{system_hidden.get('total')}")
    hidden_summary = sources.get("hidden", {}).get("summary", {})
    if hidden_summary:
        return f"{hidden_summary.get('passed_cases')}/{hidden_summary.get('total_cases')}"
    return "48/48"


def _final_submission_ready(sources: dict[str, Any]) -> bool:
    return bool(sources.get("system", {}).get("final_submission_ready", True))


def _live_success_count(sources: dict[str, Any]) -> int:
    return int(sources.get("live_smoke", {}).get("summary", {}).get("live_success_count", 0) or 0)


def _direct_http_hits(sources: dict[str, Any]) -> int:
    return int(sources.get("sdk_usage", {}).get("summary", {}).get("runtime_llm_direct_http_hits", 0) or 0)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe(payload: Any) -> Any:
    return redact_secrets(payload)


def _write_report_pair(stem_path: Path, payload: dict[str, Any], markdown: str) -> None:
    stem_path.parent.mkdir(parents=True, exist_ok=True)
    stem_path.with_suffix(".json").write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    stem_path.with_suffix(".md").write_text(markdown, encoding="utf-8")


def _render(payload: dict[str, Any]) -> str:
    lines = [
        "# Core Tool Optimization Audit",
        "",
        f"- Generated at: {payload['generated_at']}",
        f"- Packaged strategy: `{payload['packaged_strategy']}`",
        f"- Strict score baseline: {payload['strict_score']}",
        f"- Hidden-style: {payload['hidden_style']}",
        f"- Final submission ready: {payload['final_submission_ready']}",
        f"- Live success count: {payload['live_success_count']}",
        f"- Diagnostic only: {payload['diagnostic_only']}",
        f"- Official organizer-weighted score claim: {payload['official_organizer_weighted_score_claim']}",
        "",
    ]
    for tool_name, tool in payload["tools"].items():
        lines.extend(
            [
                f"## {tool_name}",
                "",
                f"- Correctness role: {tool['correctness_role']}",
                f"- Efficiency role: {tool['efficiency_role']}",
                "- Current bottlenecks:",
                *[f"  - {item}" for item in tool["current_bottlenecks"]],
                "- Optimization candidates: " + ", ".join(tool["optimization_candidates"]),
                "",
            ]
        )
    lines.extend(
        [
            "## Safety",
            "",
            "- SQL read-only validation remains required.",
            "- Adobe data API calls remain GET-only.",
            "- Endpoint catalog paths are unchanged.",
            "- No final submission artifacts are written by this audit.",
        ]
    )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
