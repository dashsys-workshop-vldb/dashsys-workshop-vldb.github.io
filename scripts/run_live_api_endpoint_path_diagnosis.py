#!/usr/bin/env python
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.adobe_env import adobe_env_readiness, format_adobe_readiness_for_report
from dashagent.api_client import AdobeAPIClient
from dashagent.api_outcome_classifier import classify_api_outcome, diagnose_api_outcome
from dashagent.config import Config
from dashagent.endpoint_catalog import Endpoint, EndpointCatalog, normalize_api_path
from dashagent.trajectory import redact_secrets
from scripts.load_local_env import load_local_env
from scripts.run_live_api_readiness_smoke import safe_error_excerpt


OUTPUT_STEM = "live_api_endpoint_path_diagnosis"
FOCUS_ENDPOINT_IDS = {"catalog_datasets", "unified_tags", "catalog_batches", "schemas_short"}
MAX_CANDIDATES_PER_ENDPOINT = 3

SAFE_CANDIDATE_PATHS: dict[str, list[str]] = {
    "catalog_datasets": [
        "/data/foundation/catalog/datasets",
        "/data/foundation/catalog/dataSets",
    ],
    "unified_tags": [
        "/data/foundation/unifiedtags/tags",
        "/data/core/unifiedtags/tags",
        "/unifiedtags/tags",
    ],
    "catalog_batches": [
        "/data/foundation/catalog/batch",
        "/data/foundation/catalog/batches",
    ],
    "schemas_short": [
        "/data/foundation/schemaregistry/tenant/schemas",
        "/schemas",
    ],
}


def main() -> int:
    load_local_env(ROOT)
    config = Config.from_env(ROOT)
    payload = run_live_api_endpoint_path_diagnosis(config)
    print(json.dumps({"report": str(config.outputs_dir / "reports" / f"{OUTPUT_STEM}.json"), "rows": len(payload.get("rows", []))}, indent=2, sort_keys=True))
    return 0


def run_live_api_endpoint_path_diagnosis(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    smoke_payload = _load_json(config.outputs_dir / "reports" / "live_api_readiness_smoke.json")
    catalog = EndpointCatalog(config)
    client = AdobeAPIClient(config)
    rows: list[dict[str, Any]] = []

    for smoke_row in _endpoint_path_issue_rows(smoke_payload):
        endpoint = catalog.by_id(str(smoke_row.get("endpoint_id") or ""))
        if not endpoint:
            continue
        rows.append(_diagnose_endpoint(client, endpoint, smoke_row))

    payload = redact_secrets(
        {
            "report_type": OUTPUT_STEM,
            "diagnostic_only": True,
            "official_score_claim": False,
            "get_only": True,
            "mutating_calls_executed": False,
            "adobe_readiness": format_adobe_readiness_for_report(adobe_env_readiness()),
            "input_report": "outputs/reports/live_api_readiness_smoke.json",
            "focus_endpoint_ids": sorted(FOCUS_ENDPOINT_IDS),
            "rows": rows,
            "code_changes_recommended": [row for row in rows if row.get("code_change_recommended")],
            "recommendation": _overall_recommendation(rows),
        }
    )
    (reports_dir / f"{OUTPUT_STEM}.json").write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    (reports_dir / f"{OUTPUT_STEM}.md").write_text(_render_md(payload), encoding="utf-8")
    return payload


def _endpoint_path_issue_rows(smoke_payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for row in smoke_payload.get("endpoints_tested", []) or []:
        endpoint_id = str(row.get("endpoint_id") or "")
        if endpoint_id in FOCUS_ENDPOINT_IDS and row.get("outcome") == "endpoint_path_issue":
            rows.append(row)
    return rows


def _diagnose_endpoint(client: AdobeAPIClient, endpoint: Endpoint, smoke_row: dict[str, Any]) -> dict[str, Any]:
    current_outcome = str(smoke_row.get("outcome") or "api_error")
    current_diagnosis = diagnose_api_outcome(smoke_row, method=endpoint.method, path=endpoint.path, outcome=current_outcome)
    candidates = _candidate_paths(endpoint)
    attempted: list[dict[str, Any]] = []
    if not client.dry_run:
        for candidate_path in candidates[:MAX_CANDIDATES_PER_ENDPOINT]:
            attempted.append(_probe_candidate(client, endpoint, candidate_path))
            time.sleep(0.2)

    best = _best_candidate(attempted)
    recommended_action = current_diagnosis["next_action"]
    code_change_recommended = False
    evidence = "current endpoint still needs diagnosis"
    best_candidate_path = None
    if best:
        best_candidate_path = best.get("path")
        best_diagnosis = diagnose_api_outcome(
            {"status_code": best.get("status_code"), "ok": best.get("ok"), "error": best.get("safe_error_excerpt")},
            method="GET",
            path=str(best_candidate_path or ""),
            outcome=str(best.get("outcome") or "api_error"),
        )
        recommended_action = best_diagnosis["next_action"]
        if best.get("outcome") in {"live_success", "live_empty"} and normalize_api_path(str(best_candidate_path)) != normalize_api_path(endpoint.path):
            recommended_action = "fix_endpoint_path"
            code_change_recommended = True
            evidence = "candidate safe GET returned live data or a live empty response"
        else:
            if best.get("outcome") in {"scope_or_permission_issue", "auth_error"}:
                recommended_action = "verify_permission"
            elif best.get("outcome") == "sandbox_scope_issue":
                recommended_action = "verify_sandbox"
            else:
                recommended_action = "no_code_fix"
            evidence = f"best candidate outcome remained {best.get('outcome')}"

    return {
        "endpoint_id": endpoint.id,
        "current_method": endpoint.method,
        "current_path": endpoint.path,
        "current_status_code": smoke_row.get("status_code"),
        "current_outcome": current_outcome,
        "current_likely_failure_area": current_diagnosis["likely_failure_area"],
        "current_next_action": current_diagnosis["next_action"],
        "candidate_safe_get_paths_considered": candidates,
        "candidate_safe_get_paths_attempted": [row.get("path") for row in attempted],
        "candidate_status_codes": {str(row.get("path")): row.get("status_code") for row in attempted},
        "candidate_outcomes": {str(row.get("path")): row.get("outcome") for row in attempted},
        "best_candidate_path": best_candidate_path,
        "recommended_action": recommended_action,
        "code_change_recommended": code_change_recommended,
        "evidence": evidence,
        "candidate_probe_rows": attempted,
    }


def _candidate_paths(endpoint: Endpoint) -> list[str]:
    current = normalize_api_path(endpoint.path)
    candidates: list[str] = []
    for candidate in SAFE_CANDIDATE_PATHS.get(endpoint.id, []):
        normalized = normalize_api_path(candidate)
        if normalized == current:
            continue
        if "{" in normalized or "}" in normalized:
            continue
        if normalized not in candidates:
            candidates.append(normalized)
    return candidates[:MAX_CANDIDATES_PER_ENDPOINT]


def _probe_candidate(client: AdobeAPIClient, endpoint: Endpoint, candidate_path: str) -> dict[str, Any]:
    if endpoint.method != "GET" or "{" in candidate_path or "}" in candidate_path:
        result = {
            "ok": False,
            "dry_run": False,
            "status_code": None,
            "error_category": "unresolved_path_param",
            "error": "candidate_probe_blocked",
        }
    else:
        result = client.call_api("GET", candidate_path, endpoint.common_params, {})
    outcome = classify_api_outcome(result, method="GET", path=candidate_path)
    diagnosis = diagnose_api_outcome(result, method="GET", path=candidate_path, outcome=outcome)
    return {
        "method": "GET",
        "path": candidate_path,
        "attempted": endpoint.method == "GET" and "{" not in candidate_path and "}" not in candidate_path,
        "ok": result.get("ok"),
        "status_code": result.get("status_code"),
        "outcome": outcome,
        "likely_failure_area": diagnosis["likely_failure_area"],
        "next_action": diagnosis["next_action"],
        "confidence": diagnosis["confidence"],
        "safe_error_category": result.get("error_category") or outcome,
        "safe_error_excerpt": safe_error_excerpt(result),
    }


def _best_candidate(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not rows:
        return None
    rank = {
        "live_success": 0,
        "live_empty": 1,
        "scope_or_permission_issue": 2,
        "sandbox_scope_issue": 3,
        "auth_error": 4,
        "api_error": 5,
        "external_api_unavailable": 6,
        "endpoint_path_issue": 7,
    }
    return sorted(rows, key=lambda row: rank.get(str(row.get("outcome")), 99))[0]


def _overall_recommendation(rows: list[dict[str, Any]]) -> str:
    if any(row.get("code_change_recommended") for row in rows):
        return "review_successful_candidate_path_before_catalog_patch"
    if rows:
        return "no_endpoint_catalog_change_without_successful_safe_get_probe"
    return "no_endpoint_path_issue_rows_to_probe"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _render_md(payload: dict[str, Any]) -> str:
    lines = [
        "# Live API Endpoint Path Diagnosis",
        "",
        "Diagnostic-only safe GET endpoint path probe report. No mutating Adobe API calls are used.",
        "",
        f"- Rows: `{len(payload.get('rows', []))}`",
        f"- Recommendation: `{payload.get('recommendation')}`",
        "",
        "## Endpoint Rows",
        "",
    ]
    for row in payload.get("rows", []):
        lines.append(
            f"- `{row.get('endpoint_id')}` current=`{row.get('current_outcome')}` "
            f"best=`{row.get('best_candidate_path')}` action=`{row.get('recommended_action')}` "
            f"code_change=`{row.get('code_change_recommended')}`"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
