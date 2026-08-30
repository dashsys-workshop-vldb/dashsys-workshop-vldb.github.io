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

from dashagent.api_discovery import plan_discovery_for_endpoint
from dashagent.config import Config
from dashagent.endpoint_catalog import Endpoint, EndpointCatalog
from dashagent.eval_harness import generated_api_calls
from dashagent.trajectory import redact_secrets


OUTPUT_STEM = "api_required_readiness_matrix"
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "adobe_api_responses"


def main() -> int:
    config = Config.from_env(ROOT)
    payload = generate_api_required_readiness_matrix(config)
    print(json.dumps({"report": str(config.outputs_dir / "reports" / f"{OUTPUT_STEM}.json"), "rows": len(payload["rows"])}, indent=2, sort_keys=True))
    return 0


def generate_api_required_readiness_matrix(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    catalog = EndpointCatalog(config)
    strict_rows = _strict_rows(config)
    rows = [_row_from_strict(row, catalog) for row in strict_rows if row.get("strategy") == "SQL_FIRST_API_VERIFY"]
    diagnostic_rows = _diagnostic_rows(config, catalog)
    summary = _summary(rows)
    payload = redact_secrets(
        {
            "report_type": OUTPUT_STEM,
            "infrastructure_validation_only": True,
            "official_score_claim": False,
            "public_dev_source": "outputs/eval_results_strict.json plus per-row trajectory outputs",
            "generated_diagnostic_prompts_scored": False,
            "total_rows": len(rows),
            "summary": summary,
            "highest_priority_endpoint_families": summary["endpoint_family_distribution"].most_common(8)
            if isinstance(summary["endpoint_family_distribution"], Counter)
            else summary["endpoint_family_distribution"],
            "rows": rows,
            "diagnostic_only_rows": diagnostic_rows,
        }
    )
    payload["summary"]["endpoint_family_distribution"] = dict(summary["endpoint_family_distribution"])
    payload["summary"]["api_mode_distribution"] = dict(summary["api_mode_distribution"])
    _write_json_md(reports_dir / OUTPUT_STEM, payload, _render(payload))
    return payload


def _strict_rows(config: Config) -> list[dict[str, Any]]:
    path = config.outputs_dir / "eval_results_strict.json"
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("rows", [])
    except Exception:
        return []


def _row_from_strict(row: dict[str, Any], catalog: EndpointCatalog) -> dict[str, Any]:
    trajectory = _load_json(Path(row.get("output_dir", "")) / "trajectory.json") if row.get("output_dir") else {}
    api_calls = generated_api_calls(trajectory)
    endpoints = [_endpoint_for_call(call, catalog) for call in api_calls]
    endpoints = [endpoint for endpoint in endpoints if endpoint is not None]
    api_mode = _api_mode(row, trajectory, endpoints)
    endpoint_rows = [_endpoint_readiness(endpoint) for endpoint in endpoints]
    readiness_status = _readiness_status(api_mode, endpoint_rows)
    route = _first_step(trajectory, "nlp").get("route", {})
    answer_diag = _first_step(trajectory, "answer_diagnostics")
    return {
        "query_id": row.get("query_id"),
        "prompt": row.get("query") or trajectory.get("original_query"),
        "route_type": trajectory.get("route_type") or route.get("route_type"),
        "domain_type": trajectory.get("domain_type") or route.get("domain_type"),
        "answer_family": answer_diag.get("answer_family"),
        "api_mode": api_mode,
        "required_endpoint_family": endpoint_rows[0]["endpoint_family"] if endpoint_rows else None,
        "candidate_endpoint_ids": [endpoint.id for endpoint in endpoints],
        "endpoints": endpoint_rows,
        "live_credential_dependency": api_mode in {"API_REQUIRED", "API_ONLY", "API_OPTIONAL"},
        "dry_run_fallback_behavior": _dry_run_behavior(trajectory),
        "readiness_status": readiness_status,
        "strict_components_reference": {
            "sql_score": row.get("sql_score"),
            "api_score": row.get("api_score"),
            "answer_score": row.get("answer_score"),
            "final_score": row.get("final_score"),
        },
    }


def _endpoint_readiness(endpoint: Endpoint) -> dict[str, Any]:
    discovery = plan_discovery_for_endpoint(endpoint).to_dict()
    fixture_dir = FIXTURE_ROOT / endpoint.id
    parser_support = "supported_with_fixtures" if fixture_dir.exists() else "parser_gap"
    evidencebus_support = "supported" if fixture_dir.exists() else "evidencebus_gap"
    answer_slot_support = "supported" if fixture_dir.exists() else "answer_slot_gap"
    smoke_safe = endpoint.method == "GET" and not endpoint.path_params and "{" not in endpoint.path
    return {
        "endpoint_id": endpoint.id,
        "endpoint_family": endpoint.id,
        "method": endpoint.method,
        "path": endpoint.path,
        "smoke_safe_get": smoke_safe,
        "needs_path_param_discovery": bool(endpoint.path_params or "{" in endpoint.path or "}" in endpoint.path),
        "required_params": list(endpoint.path_params),
        "required_headers": ["Authorization", "x-api-key", "x-gw-ims-org-id", "x-sandbox-name"],
        "parser_support_status": parser_support,
        "evidencebus_support_status": evidencebus_support,
        "answer_slot_support_status": answer_slot_support,
        "discovery": discovery,
    }


def _api_mode(row: dict[str, Any], trajectory: dict[str, Any], endpoints: list[Endpoint]) -> str:
    if not endpoints and not row.get("api_call_count"):
        return "SQL_ONLY"
    route_type = str(trajectory.get("route_type") or "")
    plan = _first_step(trajectory, "plan")
    rationale = str(plan.get("rationale") or "").lower()
    if route_type == "API_ONLY" or (row.get("sql_call_count") == 0 and row.get("api_call_count")):
        return "API_ONLY"
    if "required" in rationale or route_type in {"API_THEN_SQL", "SQL_AND_API_COMPARE"}:
        return "API_REQUIRED"
    return "API_OPTIONAL"


def _readiness_status(api_mode: str, endpoints: list[dict[str, Any]]) -> str:
    if api_mode == "SQL_ONLY":
        return "ready_sql_only"
    if not endpoints:
        return "live_api_readiness_gap"
    if any(endpoint["parser_support_status"] == "parser_gap" for endpoint in endpoints):
        return "parser_gap"
    if any(endpoint["evidencebus_support_status"] == "evidencebus_gap" for endpoint in endpoints):
        return "evidencebus_gap"
    if any(endpoint["answer_slot_support_status"] == "answer_slot_gap" for endpoint in endpoints):
        return "answer_slot_gap"
    if any(endpoint["needs_path_param_discovery"] for endpoint in endpoints):
        return "needs_discovery_chain"
    if api_mode in {"API_REQUIRED", "API_ONLY"}:
        return "needs_live_credentials"
    return "ready_for_live_get"


def _dry_run_behavior(trajectory: dict[str, Any]) -> str:
    api_steps = [step for step in trajectory.get("steps", []) if isinstance(step, dict) and step.get("kind") == "api_call"]
    if not api_steps:
        return "not_applicable"
    if any((step.get("result") or {}).get("dry_run") for step in api_steps):
        return "honest_dry_run_unavailable"
    return "live_or_mock_api_evidence"


def _endpoint_for_call(call: dict[str, Any], catalog: EndpointCatalog) -> Endpoint | None:
    method = str(call.get("method") or "GET")
    url = str(call.get("url") or call.get("path") or "")
    return catalog.match(method, url)


def _diagnostic_rows(config: Config, catalog: EndpointCatalog) -> list[dict[str, Any]]:
    path = config.data_dir / "generated_prompt_suite.json"
    if not path.exists():
        return []
    try:
        prompts = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    rows = []
    for item in prompts:
        if len(rows) >= 100:
            break
        route = str(item.get("expected_route_diagnostic") or "")
        hints = item.get("target_api_hint") or []
        if "API" not in route and not hints:
            continue
        endpoint_ids = []
        for hint in hints:
            text = str(hint)
            for endpoint in catalog.endpoints:
                if endpoint.id in text or endpoint.path in text:
                    endpoint_ids.append(endpoint.id)
        rows.append(
            {
                "prompt_id": item.get("prompt_id"),
                "prompt": item.get("prompt"),
                "diagnostic_only": True,
                "should_be_scored": False,
                "expected_route_diagnostic": route,
                "domain_family": item.get("domain_family"),
                "target_api_hint": hints,
                "candidate_endpoint_ids": sorted(set(endpoint_ids)),
                "readiness_note": "Coverage-only diagnostic prompt; not official strict score or promotion evidence.",
            }
        )
    return rows


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    api_modes = Counter(row["api_mode"] for row in rows)
    endpoint_families = Counter(endpoint["endpoint_family"] for row in rows for endpoint in row.get("endpoints", []))
    return {
        "total_api_required_or_api_only_queries": api_modes.get("API_REQUIRED", 0) + api_modes.get("API_ONLY", 0),
        "api_mode_distribution": api_modes,
        "endpoint_family_distribution": endpoint_families,
        "endpoints_needed": len(endpoint_families),
        "discovery_chains_needed": sum(
            1 for row in rows for endpoint in row.get("endpoints", []) if endpoint.get("needs_path_param_discovery")
        ),
        "parser_gaps": sum(1 for row in rows if row.get("readiness_status") == "parser_gap"),
        "evidencebus_gaps": sum(1 for row in rows if row.get("readiness_status") == "evidencebus_gap"),
        "answer_slot_gaps": sum(1 for row in rows if row.get("readiness_status") == "answer_slot_gap"),
        "live_credential_blockers": sum(1 for row in rows if row.get("live_credential_dependency")),
    }


def _first_step(trajectory: dict[str, Any], kind: str) -> dict[str, Any]:
    for step in trajectory.get("steps", []):
        if isinstance(step, dict) and step.get("kind") == kind:
            return step
    return {}


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _render(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# API Required Readiness Matrix",
        "",
        "Infrastructure validation only; this report is not official strict-score evidence.",
        "",
        f"- Public/dev SQL_FIRST_API_VERIFY rows: `{payload['total_rows']}`",
        f"- API_REQUIRED/API_ONLY rows: `{summary['total_api_required_or_api_only_queries']}`",
        f"- Endpoints needed: `{summary['endpoints_needed']}`",
        f"- Discovery chains needed: `{summary['discovery_chains_needed']}`",
        f"- Parser gaps: `{summary['parser_gaps']}`",
        f"- EvidenceBus gaps: `{summary['evidencebus_gaps']}`",
        f"- Answer-slot gaps: `{summary['answer_slot_gaps']}`",
        f"- Live credential blockers: `{summary['live_credential_blockers']}`",
        "",
        "## Highest-Priority Endpoint Families",
        "",
    ]
    for family, count in (payload.get("highest_priority_endpoint_families") or []):
        lines.append(f"- `{family}`: `{count}`")
    lines.extend(["", "## Rows", ""])
    for row in payload["rows"][:40]:
        lines.append(
            f"- `{row.get('query_id')}` mode=`{row.get('api_mode')}` status=`{row.get('readiness_status')}` "
            f"endpoints=`{', '.join(row.get('candidate_endpoint_ids') or []) or 'none'}`"
        )
    return "\n".join(lines) + "\n"


def _write_json_md(stem: Path, payload: dict[str, Any], markdown: str) -> None:
    stem.with_suffix(".json").write_text(json.dumps(redact_secrets(payload), indent=2, sort_keys=True, default=str), encoding="utf-8")
    stem.with_suffix(".md").write_text(markdown, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
