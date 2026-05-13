#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.answer_slots import extract_answer_slots
from dashagent.adobe_env import adobe_env_readiness, format_adobe_readiness_for_report
from dashagent.api_client import AdobeAPIClient
from dashagent.api_outcome_classifier import classify_api_outcome, diagnose_api_outcome, outcome_counts
from dashagent.api_response_parser import normalize_api_response
from dashagent.config import Config
from dashagent.endpoint_catalog import Endpoint, EndpointCatalog
from dashagent.evidence_bus import EvidenceBus
from dashagent.trajectory import redact_secrets
from dashagent.validators import APIValidator
from scripts.load_local_env import load_local_env


OUTPUT_STEM = "live_api_readiness_smoke"
DEFAULT_SMOKE_ENDPOINT_ORDER = [
    "journey_list",
    "ups_audiences",
    "segment_definitions",
    "flowservice_flows",
    "flowservice_runs",
    "catalog_datasets",
    "schema_registry_schemas",
    "unified_tags",
    "merge_policies",
    "catalog_batches",
    "audit_events",
]
SENSITIVE_ENV_NAMES = [
    "ADOBE_ACCESS_TOKEN",
    "ACCESS_TOKEN",
    "ADOBE_API_KEY",
    "CLIENT_ID",
    "ADOBE_CLIENT_ID",
    "ADOBE_CLIENT_SECRET",
    "CLIENT_SECRET",
    "ADOBE_ORG_ID",
    "IMS_ORG",
    "ADOBE_SANDBOX_NAME",
    "SANDBOX",
]


def main() -> int:
    load_local_env(ROOT)
    parser = argparse.ArgumentParser(description="Run safe GET-only Adobe API readiness smoke checks.")
    parser.add_argument("--limit", default="12", help="Maximum catalog-approved GET endpoints, or all-safe-get.")
    parser.add_argument("--endpoint-id", default=None, help="Optional single catalog endpoint id to smoke.")
    parser.add_argument("--endpoint-family", default=None, help="Optional endpoint id/domain family filter.")
    args = parser.parse_args()
    config = Config.from_env(ROOT)
    payload = run_live_api_readiness_smoke(
        config,
        limit=args.limit,
        endpoint_id=args.endpoint_id,
        endpoint_family=args.endpoint_family,
    )
    print(json.dumps({"status": payload["status"], "report": str(config.outputs_dir / "reports" / f"{OUTPUT_STEM}.json")}, indent=2, sort_keys=True))
    return 0


def run_live_api_readiness_smoke(
    config: Config | None = None,
    *,
    limit: int | str = 12,
    endpoint_id: str | None = None,
    endpoint_family: str | None = None,
) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    client = AdobeAPIClient(config)
    catalog = EndpointCatalog(config)
    validator = APIValidator(catalog)
    readiness = adobe_env_readiness()
    report_readiness = format_adobe_readiness_for_report(readiness)

    if client.dry_run:
        payload = skipped_live_report(config, client, readiness)
        _write_json_md(reports_dir / OUTPUT_STEM, payload, render_smoke(payload))
        return payload

    safe_endpoints = [endpoint for endpoint in catalog.endpoints if endpoint_is_safe_get_smoke(endpoint)]
    filtered_endpoints = filter_safe_smoke_endpoints(
        safe_endpoints,
        limit=limit,
        endpoint_id=endpoint_id,
        endpoint_family=endpoint_family,
    )
    endpoints = filtered_endpoints
    selected_ids = {endpoint.id for endpoint in endpoints}
    filtered_ids = {
        endpoint.id
        for endpoint in filter_safe_smoke_endpoints(
            safe_endpoints,
            limit="all-safe-get",
            endpoint_id=endpoint_id,
            endpoint_family=endpoint_family,
        )
    }
    skipped_endpoints = [
        skipped_endpoint_reason(
            endpoint,
            selected=endpoint.id in selected_ids,
            filter_matched=endpoint.id in filtered_ids,
        )
        for endpoint in catalog.endpoints
        if endpoint.id not in selected_ids
    ]
    rows = []
    for endpoint in endpoints:
        validation = validator.validate(endpoint.method, endpoint.path, endpoint.common_params, {})
        if not validation.ok:
            result = {
                "ok": False,
                "dry_run": False,
                "endpoint": endpoint.path,
                "status_code": None,
                "error_category": "endpoint_path_issue",
                "error": "validation_failed",
            }
            rows.append(
                smoke_endpoint_row(
                    endpoint=endpoint,
                    result=result,
                    validation=validation.to_dict(),
                    attempted=False,
                    evidence_status={
                        "response_parser_status": "not_available",
                        "evidencebus_forwarding_status": "no_live_items",
                        "answer_synthesis_status": "no_live_items",
                    },
                )
            )
            continue
        result = client.call_api(endpoint.method, endpoint.path, endpoint.common_params, {})
        evidence_status = evidence_pipeline_status(endpoint, result)
        rows.append(
            smoke_endpoint_row(
                endpoint=endpoint,
                result=result,
                validation=validation.to_dict(),
                attempted=True,
                evidence_status=evidence_status,
            )
        )
        time.sleep(0.2)

    payload = {
        "report_type": OUTPUT_STEM,
        "status": "complete",
        "infrastructure_validation_only": True,
        "official_score_claim": False,
        "credentials_present": True,
        "adobe_readiness": report_readiness,
        "credential_ready": report_readiness.get("credential_ready"),
        "sandbox_ready": report_readiness.get("sandbox_ready"),
        "ready_for_live_adobe_api_smoke": report_readiness.get("ready_for_live_adobe_api_smoke"),
        "ready_for_sandbox_endpoints": report_readiness.get("ready_for_sandbox_endpoints"),
        "selection_filters": {
            "limit": str(limit),
            "endpoint_id": endpoint_id,
            "endpoint_family": endpoint_family,
        },
        "live_mode_attempted": True,
        "dry_run_fallback_verified": False,
        "endpoints_tested": rows,
        "skipped_endpoints": skipped_endpoints,
        "outcome_counts": outcome_counts(rows),
        "endpoints_attempted": sum(1 for row in rows if row.get("attempted")),
        "endpoints_success": sum(1 for row in rows if row.get("outcome") == "live_success"),
        "endpoints_empty": sum(1 for row in rows if row.get("outcome") == "live_empty"),
        "endpoints_auth_error": sum(1 for row in rows if row.get("outcome") == "auth_error"),
        "endpoints_rate_limited": sum(1 for row in rows if row.get("outcome") == "rate_limited"),
        "endpoints_api_error": sum(1 for row in rows if row.get("outcome") in {"api_error", "external_api_unavailable", "endpoint_path_issue", "scope_or_permission_issue", "sandbox_scope_issue", "token_acquisition_failed"}),
        "parser_success": sum(1 for row in rows if row.get("response_parser_status") == "pass"),
        "parser_failure": sum(1 for row in rows if row.get("response_parser_status") not in {"pass", "dry_run_fallback"}),
        "discovery_success": 0,
        "discovery_blocked": sum(1 for row in skipped_endpoints if row.get("reason") == "requires_discovery_chain_or_path_param"),
        "success_count": sum(1 for row in rows if row.get("ok") is True),
        "failure_count": sum(1 for row in rows if row.get("ok") is False),
        "auth_failure_count": sum(1 for row in rows if row.get("status_code") in {401, 403}),
        "rate_limit_count": sum(1 for row in rows if row.get("status_code") == 429),
        "response_parser_status": _aggregate_status(rows, "response_parser_status"),
        "evidencebus_forwarding_status": _aggregate_status(rows, "evidencebus_forwarding_status"),
        "answer_synthesis_status": _aggregate_status(rows, "answer_synthesis_status"),
        "residual_risk": "GET smoke checks verify connectivity and parsing only; they do not claim official strict-score improvement.",
        "protected_outputs_not_written": protected_output_paths(),
    }
    payload = redact_secrets(payload)
    _write_json_md(reports_dir / OUTPUT_STEM, payload, render_smoke(payload))
    return payload


def smoke_endpoint_row(
    *,
    endpoint: Endpoint,
    result: dict[str, Any],
    validation: dict[str, Any],
    attempted: bool,
    evidence_status: dict[str, str],
) -> dict[str, Any]:
    outcome = classify_api_outcome(result, method=endpoint.method, path=endpoint.path)
    diagnosis = diagnose_api_outcome(result, method=endpoint.method, path=endpoint.path, outcome=outcome)
    return {
        "endpoint_id": endpoint.id,
        "method": endpoint.method,
        "path": endpoint.path,
        "attempted": attempted,
        "validation": validation,
        "status_code": result.get("status_code"),
        "ok": result.get("ok"),
        "dry_run": result.get("dry_run"),
        "outcome": outcome,
        "safe_error_category": result.get("error_category") or outcome,
        "likely_failure_area": diagnosis["likely_failure_area"],
        "next_action": diagnosis["next_action"],
        "confidence": diagnosis["confidence"],
        "response_parser_status": evidence_status["response_parser_status"],
        "evidencebus_forwarding_status": evidence_status["evidencebus_forwarding_status"],
        "answer_synthesis_status": evidence_status["answer_synthesis_status"],
        "safe_error_excerpt": safe_error_excerpt(result),
    }


def skipped_live_report(config: Config, client: AdobeAPIClient, readiness: dict[str, Any] | None = None) -> dict[str, Any]:
    readiness = readiness or adobe_env_readiness()
    report_readiness = format_adobe_readiness_for_report(readiness)
    dry_run_result = client.call_api("GET", "/ajo/journey", {"limit": 1}, {})
    parsed_sample = normalize_api_response(
        {"items": [{"id": "journey-1", "name": "Sample Journey", "status": "live"}], "total": 1},
        ok=True,
        dry_run=False,
        status_code=200,
        endpoint="/ajo/journey",
        endpoint_id="journey_list",
        endpoint_family="journey_list",
        method="GET",
        path="/ajo/journey",
    )
    pipeline = evidence_pipeline_status(
        Endpoint(id="journey_list", method="GET", path="/ajo/journey", use_when="sample"),
        {"ok": True, "dry_run": False, "parsed_evidence": parsed_sample, "result_preview": parsed_sample},
    )
    return redact_secrets(
        {
            "report_type": OUTPUT_STEM,
            "status": "skipped_live_credentials_missing",
            "infrastructure_validation_only": True,
            "official_score_claim": False,
            "credentials_present": False,
            "adobe_readiness": report_readiness,
            "credential_ready": report_readiness.get("credential_ready"),
            "sandbox_ready": report_readiness.get("sandbox_ready"),
            "ready_for_live_adobe_api_smoke": report_readiness.get("ready_for_live_adobe_api_smoke"),
            "ready_for_sandbox_endpoints": report_readiness.get("ready_for_sandbox_endpoints"),
            "selection_filters": {"limit": "not_run", "endpoint_id": None, "endpoint_family": None},
            "live_mode_attempted": False,
            "dry_run_fallback_verified": bool(dry_run_result.get("dry_run")),
            "missing_env_var_groups": [
                "ADOBE_ACCESS_TOKEN or ACCESS_TOKEN",
                "ADOBE_API_KEY or CLIENT_ID",
                "ADOBE_ORG_ID or IMS_ORG",
                "ADOBE_SANDBOX_NAME or SANDBOX",
            ],
            "endpoints_tested": [],
            "skipped_endpoints": [],
            "success_count": 0,
            "failure_count": 0,
            "auth_failure_count": 0,
            "rate_limit_count": 0,
            "outcome_counts": {},
            "endpoints_attempted": 0,
            "endpoints_success": 0,
            "endpoints_empty": 0,
            "endpoints_auth_error": 0,
            "endpoints_rate_limited": 0,
            "endpoints_api_error": 0,
            "parser_success": 0,
            "parser_failure": 0,
            "discovery_success": 0,
            "discovery_blocked": 0,
            "response_parser_status": pipeline["response_parser_status"],
            "evidencebus_forwarding_status": pipeline["evidencebus_forwarding_status"],
            "answer_synthesis_status": pipeline["answer_synthesis_status"],
            "dry_run_result": dry_run_result,
            "residual_risk": "Live connectivity, rate limits, and real payload shapes remain unverified until Adobe credentials are available.",
            "protected_outputs_not_written": protected_output_paths(),
        }
    )


def filter_safe_smoke_endpoints(
    endpoints: list[Endpoint],
    *,
    limit: int | str,
    endpoint_id: str | None = None,
    endpoint_family: str | None = None,
) -> list[Endpoint]:
    filtered = [endpoint for endpoint in endpoints if _endpoint_matches_filters(endpoint, endpoint_id, endpoint_family)]
    order = {endpoint_id: index for index, endpoint_id in enumerate(DEFAULT_SMOKE_ENDPOINT_ORDER)}
    filtered.sort(key=lambda endpoint: (order.get(endpoint.id, len(order)), endpoints.index(endpoint)))
    if str(limit) == "all-safe-get":
        return filtered
    try:
        max_count = int(limit)
    except (TypeError, ValueError):
        max_count = 12
    return filtered[: max(0, max_count)]


def _endpoint_matches_filters(endpoint: Endpoint, endpoint_id: str | None, endpoint_family: str | None) -> bool:
    if endpoint_id and endpoint.id != endpoint_id:
        return False
    if endpoint_family:
        family = endpoint_family.lower()
        haystack = [endpoint.id.lower(), *(domain.lower() for domain in endpoint.domains)]
        if not any(family in item for item in haystack):
            return False
    return True


def endpoint_is_safe_get_smoke(endpoint: Endpoint) -> bool:
    return endpoint.method == "GET" and not endpoint.path_params and "{" not in endpoint.path and "}" not in endpoint.path


def skipped_endpoint_reason(endpoint: Endpoint, *, selected: bool = False, filter_matched: bool = True) -> dict[str, Any]:
    if endpoint.method != "GET":
        reason = "non_get_endpoint"
    elif endpoint.path_params or "{" in endpoint.path or "}" in endpoint.path:
        reason = "requires_discovery_chain_or_path_param"
    elif not filter_matched:
        reason = "not_matching_filter"
    elif not selected:
        reason = "not_selected_by_limit"
    else:
        reason = "selected"
    return {
        "endpoint_id": endpoint.id,
        "method": endpoint.method,
        "path": endpoint.path,
        "reason": reason,
    }


def likely_failure_area(outcome: str) -> str:
    mapping = {
        "live_success": "no_code_fix",
        "live_empty": "no_code_fix",
        "auth_error": "auth_token",
        "token_acquisition_failed": "auth_token",
        "scope_or_permission_issue": "product_permission",
        "sandbox_scope_issue": "sandbox_scope",
        "endpoint_path_issue": "endpoint_path",
        "unresolved_path_param": "endpoint_path",
        "discovery_blocked_missing_id": "endpoint_path",
        "rate_limited": "adobe_service",
        "malformed_response": "parser_gap",
        "external_api_unavailable": "adobe_service",
        "api_error": "no_code_fix",
    }
    return mapping.get(outcome, "no_code_fix")


def safe_error_excerpt(result: dict[str, Any], *, max_chars: int = 300) -> str:
    parsed = result.get("parsed_evidence") if isinstance(result.get("parsed_evidence"), dict) else {}
    parts = [
        result.get("error"),
        result.get("result_preview"),
        parsed.get("errors"),
        parsed.get("raw_preview"),
    ]
    text = " ".join(str(part) for part in parts if part not in (None, "", [], {}))
    text = _replace_sensitive_env_values(text)
    text = str(redact_secrets(text))
    text = re.sub(r"Authorization\s*[:=]\s*Bearer\s+[^\s,;]+", "Authorization: [REDACTED]", text, flags=re.I)
    text = re.sub(r"x-api-key\s*[:=]\s*[^\s,;]+", "x-api-key: [REDACTED]", text, flags=re.I)
    text = re.sub(r"x-gw-ims-org-id\s*[:=]\s*[^\s,;]+", "x-gw-ims-org-id: [REDACTED]", text, flags=re.I)
    text = re.sub(r"x-sandbox-name\s*[:=]\s*[^\s,;]+", "x-sandbox-name: [REDACTED]", text, flags=re.I)
    text = re.sub(r"\b[A-Za-z0-9_.@-]{1,12}\*\*\*", "[REDACTED]", text)
    return text[:max_chars]


def _replace_sensitive_env_values(text: str) -> str:
    for name in SENSITIVE_ENV_NAMES:
        value = os.environ.get(name)
        if value:
            text = text.replace(value, "[REDACTED]")
    return text


def evidence_pipeline_status(endpoint: Endpoint, result: dict[str, Any]) -> dict[str, str]:
    bus = EvidenceBus()
    step = type("Step", (), {"family": endpoint.id})()
    bus.observe_api(step, result)
    slots = extract_answer_slots(
        "live API readiness smoke",
        [{"type": "api", "step": {"family": endpoint.id, "url": endpoint.path}, "payload": result}],
    )
    parsed = result.get("parsed_evidence") if isinstance(result, dict) else None
    parser_status = "pass" if isinstance(parsed, dict) and parsed.get("evidence_state") in {"live_evidence", "live_empty", "live_empty_result", "api_error", "malformed_response", "token_acquisition_failed"} else "not_available"
    if result.get("dry_run"):
        parser_status = "dry_run_fallback"
    return {
        "response_parser_status": parser_status,
        "evidencebus_forwarding_status": "pass" if bus.api_items or bus.api_ids or bus.api_errors or bus.names or bus.ids or bus.statuses or result.get("dry_run") else "no_live_items",
        "answer_synthesis_status": "pass" if slots.api_items or slots.answer_slot_source or slots.dry_run or slots.api_error or slots.api_item_count is not None else "no_live_items",
    }


def protected_output_paths() -> list[str]:
    return [
        "outputs/eval_results_strict.json",
        "outputs/eval/",
        "outputs/final_submission/",
        "outputs/final_submission_manifest.json",
    ]


def render_smoke(payload: dict[str, Any]) -> str:
    lines = [
        "# Live API Readiness Smoke",
        "",
        "Infrastructure validation only; this report is not official strict-score evidence.",
        "",
        f"- Status: `{payload['status']}`",
        f"- Credentials present: `{payload['credentials_present']}`",
        f"- Live mode attempted: `{payload['live_mode_attempted']}`",
        f"- Dry-run fallback verified: `{payload['dry_run_fallback_verified']}`",
        f"- Credential ready: `{payload.get('credential_ready')}`",
        f"- Sandbox ready: `{payload.get('sandbox_ready')}`",
        f"- Ready for live smoke: `{payload.get('ready_for_live_adobe_api_smoke')}`",
        f"- Ready for sandbox endpoints: `{payload.get('ready_for_sandbox_endpoints')}`",
        f"- Success count: `{payload['success_count']}`",
        f"- Failure count: `{payload['failure_count']}`",
        f"- Auth failures: `{payload['auth_failure_count']}`",
        f"- Rate limits: `{payload['rate_limit_count']}`",
        f"- Response parser status: `{payload['response_parser_status']}`",
        f"- EvidenceBus forwarding status: `{payload['evidencebus_forwarding_status']}`",
        f"- Answer synthesis status: `{payload['answer_synthesis_status']}`",
        f"- Residual risk: {payload['residual_risk']}",
        "",
        "## Endpoints Tested",
        "",
    ]
    for row in payload.get("endpoints_tested", []):
        lines.append(
            f"- `{row.get('endpoint_id')}` {row.get('method')} `{row.get('path')}` "
            f"outcome=`{row.get('outcome')}` ok=`{row.get('ok')}` status=`{row.get('status_code')}` parser=`{row.get('response_parser_status')}`"
        )
    lines.extend(["", "## Skipped Endpoints", ""])
    for row in payload.get("skipped_endpoints", [])[:30]:
        lines.append(
            f"- `{row.get('endpoint_id')}` {row.get('method')} `{row.get('path')}` reason=`{row.get('reason')}`"
        )
    return "\n".join(lines) + "\n"


def _aggregate_status(rows: list[dict[str, Any]], key: str) -> str:
    if not rows:
        return "not_run"
    if any(row.get(key) == "pass" for row in rows):
        return "pass"
    return rows[0].get(key) or "not_available"


def _write_json_md(stem: Path, payload: dict[str, Any], markdown: str) -> None:
    stem.with_suffix(".json").write_text(json.dumps(redact_secrets(payload), indent=2, sort_keys=True, default=str), encoding="utf-8")
    stem.with_suffix(".md").write_text(markdown, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
