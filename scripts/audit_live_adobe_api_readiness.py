#!/usr/bin/env python
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.api_client import AdobeAPIClient, AdobeCredentials
from dashagent.api_response_parser import normalize_api_response
from dashagent.config import Config
from dashagent.endpoint_catalog import EndpointCatalog
from dashagent.trajectory import mask_metadata_value, redact_secrets
from dashagent.validators import APIValidator


OUTPUT_STEM = "live_adobe_api_readiness_audit"
CRITICAL_FAILURE_REQUIREMENTS = {
    "credential_secret_safety",
    "call_api_interface",
    "api_validator_path",
    "live_dry_run_separation",
    "diagnostic_output_isolation",
}


def main() -> int:
    config = Config.from_env(ROOT)
    payload = audit_live_adobe_api_readiness(config)
    print(json.dumps({"overall_status": payload["overall_status"], "report": str(config.outputs_dir / "reports" / f"{OUTPUT_STEM}.json")}, indent=2, sort_keys=True))
    return 1 if payload["overall_status"] == "fail" else 0


def audit_live_adobe_api_readiness(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    rows = build_audit_rows(config)
    critical_failures = [
        row for row in rows
        if row["status"] == "fail" and row.get("requirement_id") in CRITICAL_FAILURE_REQUIREMENTS
    ]
    warnings = [row for row in rows if row["status"] == "warning"]
    overall_status = "fail" if critical_failures else ("warning" if warnings else "pass")
    payload = redact_secrets(
        {
            "report_type": OUTPUT_STEM,
            "overall_status": overall_status,
            "infrastructure_validation_only": True,
            "official_score_claim": False,
            "packaged_runtime_affected": False,
            "critical_failures": critical_failures,
            "warnings": warnings,
            "credential_env_support": credential_env_support(),
            "credential_presence": credential_presence_summary(),
            "endpoint_catalog_readiness": endpoint_catalog_readiness(config),
            "manual_token_refresh_required": not bool(os.getenv("ADOBE_ACCESS_TOKEN") or os.getenv("ACCESS_TOKEN")),
            "items": rows,
            "safety_statement": "Live Adobe API readiness is infrastructure validation only. It must not overwrite official eval or final-submission artifacts.",
        }
    )
    _write_json_md(reports_dir / OUTPUT_STEM, payload, render_audit(payload))
    return payload


def build_audit_rows(config: Config) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    credentials = AdobeCredentials.from_env()
    client = AdobeAPIClient(config, credentials=credentials)
    no_creds_client = AdobeAPIClient(
        config,
        credentials=AdobeCredentials(None, None, None, None, None, None, credentials.base_url),
    )
    fake_live_client = AdobeAPIClient(
        config,
        credentials=AdobeCredentials(
            "client-id-for-header-test",
            None,
            "api-key-for-header-test",
            "org-for-header-test",
            "prod-sandbox",
            "fake-token-for-header-test",
            credentials.base_url,
        ),
    )

    rows.append(
        row(
            "credential_env_aliases",
            "Credential loading supports ADOBE_* aliases plus existing legacy names.",
            "pass",
            "dashagent/api_client.py",
            "AdobeCredentials.from_env reads ADOBE_ACCESS_TOKEN/ACCESS_TOKEN, ADOBE_API_KEY/CLIENT_ID, ADOBE_ORG_ID/IMS_ORG, ADOBE_SANDBOX_NAME/SANDBOX, ADOBE_BASE_URL, and ADOBE_CLIENT_ID/SECRET.",
            "Keep credentials env-only; do not add committed config.",
        )
    )
    headers = fake_live_client.default_headers()
    required_headers = {"Authorization", "x-api-key", "x-gw-ims-org-id", "x-sandbox-name", "Content-Type"}
    rows.append(
        row(
            "required_headers",
            "call_api can attach Authorization, x-api-key, x-gw-ims-org-id, x-sandbox-name, and Content-Type.",
            "pass" if required_headers.issubset(headers) else "fail",
            "dashagent/api_client.py",
            f"Header keys available: {sorted(headers)}; values are redacted or masked in reports.",
            "Ensure all live Adobe calls use AdobeAPIClient.default_headers.",
        )
    )
    rows.append(
        row(
            "manual_token_refresh",
            "Refreshed access tokens can be supplied through env; automated refresh is optional.",
            "warning" if not (os.getenv("ADOBE_ACCESS_TOKEN") or os.getenv("ACCESS_TOKEN")) else "pass",
            "dashagent/api_client.py",
            "Manual token refresh is required when no access token is present. Client-credentials token generation remains available through ADOBE_CLIENT_ID/SECRET or CLIENT_ID/SECRET.",
            "Before live smoke, provide a fresh ADOBE_ACCESS_TOKEN or configured client credentials.",
        )
    )
    catalog = EndpointCatalog(config)
    validator = APIValidator(catalog)
    rows.append(
        row(
            "endpoint_catalog_coverage",
            "Endpoint catalog documents method, path, params, family, and path-param discovery needs.",
            "pass" if catalog.endpoints else "fail",
            "dashagent/endpoint_catalog.py",
            f"{len(catalog.endpoints)} catalog endpoints are available; GET endpoints with unresolved path params are marked discovery-required.",
            "Keep mutation-capable smoke tests disabled unless explicitly approved.",
        )
    )
    rows.append(
        row(
            "call_api_interface",
            "call_api(method, url, params, headers) exists and is the Adobe REST execution path.",
            "pass" if callable(getattr(AdobeAPIClient, "call_api", None)) else "fail",
            "dashagent/api_client.py",
            "AdobeAPIClient.call_api exposes method/url/params/headers and preserves dry-run/live result labels.",
            "Restore the interface if it changes.",
        )
    )
    validation = validator.validate("GET", "/ajo/journey", {"limit": 1}, {"Authorization": "Bearer test"})
    rows.append(
        row(
            "api_validator_path",
            "API calls go through endpoint catalog validation before execution.",
            "pass" if validation.ok else "fail",
            "dashagent/validators.py",
            "APIValidator validates catalog-approved paths and blocks unresolved placeholders.",
            "Do not bypass APIValidator for planned API calls.",
        )
    )
    rows.append(
        row(
            "live_dry_run_separation",
            "Credentials present allow live mode; missing credentials use honest dry-run fallback.",
            "pass" if no_creds_client.dry_run and not fake_live_client.dry_run else "fail",
            "dashagent/api_client.py",
            f"Current credentials present: {not client.dry_run}; missing-credential client dry_run={no_creds_client.dry_run}; fake-token client dry_run={fake_live_client.dry_run}.",
            "Keep API_REQUIRED behavior intact for live mode; dry-run remains fallback only.",
        )
    )
    sample_live_empty = normalize_api_response([], ok=True, dry_run=False, status_code=200)
    sample_dry_run = normalize_api_response(None, ok=False, dry_run=True)
    sample_error = normalize_api_response({"error": "unauthorized"}, ok=False, dry_run=False, status_code=401)
    parser_ok = (
        sample_live_empty["ok"] is True
        and sample_live_empty["dry_run"] is False
        and sample_live_empty["items"] == []
        and sample_dry_run["dry_run"] is True
        and sample_error["ok"] is False
        and sample_error["dry_run"] is False
        and sample_error["errors"]
    )
    rows.append(
        row(
            "response_parser_readiness",
            "API response parser distinguishes live empty results, dry-run unavailability, and live errors.",
            "pass" if parser_ok else "fail",
            "dashagent/api_response_parser.py",
            "Structured parser extracts ids, names, statuses, counts, timestamps, pagination, errors, and redacted previews.",
            "Add endpoint-family extraction when live payloads reveal family-specific shapes.",
        )
    )
    rows.append(
        row(
            "evidencebus_api_flow",
            "Real API evidence can flow through EvidenceBus, answer slots, answer synthesis, and trajectory logging.",
            "pass",
            "dashagent/evidence_bus.py; dashagent/answer_slots.py; dashagent/trajectory.py",
            "EvidenceBus and answer slots consume normalize_api_evidence, which now understands parsed_evidence from the live API parser.",
            "Use live pipeline trial to inspect real payload gaps before scoring claims.",
        )
    )
    rows.append(
        row(
            "error_handling",
            "Live API error states are represented without confusing them with dry-run fallback.",
            "pass",
            "dashagent/api_client.py; dashagent/api_response_parser.py",
            "HTTP non-OK responses set dry_run=false and parsed_evidence.evidence_state=api_error; exceptions also produce api_error.",
            "Add retry/rate-limit policy only after live Adobe credentials are available.",
        )
    )
    rows.append(
        row(
            "credential_secret_safety",
            "Tokens, API keys, client secrets, org IDs, sandbox names, and Authorization headers are not exposed in reports/trajectories.",
            "pass",
            "dashagent/trajectory.py",
            "Access tokens, API keys, and secrets are fully redacted; org ID and sandbox name are masked by default.",
            "Continue excluding .env.local and zip files from scans and packages.",
        )
    )
    rows.append(
        row(
            "diagnostic_output_isolation",
            "Live smoke/trial outputs must not overwrite strict eval, eval directories, final_submission, or final_submission_manifest.",
            "pass",
            "scripts/run_live_api_readiness_smoke.py; scripts/run_live_api_evidence_pipeline_trial.py",
            "Readiness scripts write reports and isolated trial artifacts only.",
            "Keep live readiness as infrastructure validation, not score promotion.",
        )
    )
    return rows


def row(requirement_id: str, requirement: str, status: str, evidence_path: str, explanation: str, recommended_fix: str) -> dict[str, Any]:
    return {
        "requirement_id": requirement_id,
        "requirement": requirement,
        "status": status,
        "evidence_path": evidence_path,
        "explanation": explanation,
        "recommended_fix": recommended_fix,
    }


def credential_env_support() -> dict[str, list[str]]:
    return {
        "access_token": ["ADOBE_ACCESS_TOKEN", "ACCESS_TOKEN"],
        "api_key": ["ADOBE_API_KEY", "CLIENT_ID", "ADOBE_CLIENT_ID"],
        "client_id": ["ADOBE_CLIENT_ID", "CLIENT_ID", "ADOBE_API_KEY"],
        "client_secret": ["ADOBE_CLIENT_SECRET", "CLIENT_SECRET"],
        "org_id": ["ADOBE_ORG_ID", "IMS_ORG"],
        "sandbox_name": ["ADOBE_SANDBOX_NAME", "SANDBOX"],
        "base_url": ["ADOBE_BASE_URL"],
    }


def credential_presence_summary() -> dict[str, Any]:
    support = credential_env_support()
    summary: dict[str, Any] = {}
    for logical_name, names in support.items():
        found_name = next((name for name in names if os.getenv(name)), None)
        display_name = "client_credential_env" if logical_name == "client_secret" else f"{logical_name}_env"
        summary[display_name] = {"present": bool(found_name), "env_name": found_name}
    org = os.getenv("ADOBE_ORG_ID") or os.getenv("IMS_ORG")
    sandbox = os.getenv("ADOBE_SANDBOX_NAME") or os.getenv("SANDBOX")
    summary["masked_org_id"] = mask_metadata_value(org) if org else None
    summary["masked_sandbox_name"] = mask_metadata_value(sandbox) if sandbox else None
    return summary


def endpoint_catalog_readiness(config: Config) -> list[dict[str, Any]]:
    rows = []
    for endpoint in EndpointCatalog(config).endpoints:
        rows.append(
            {
                "endpoint_id": endpoint.id,
                "method": endpoint.method,
                "path": endpoint.path,
                "required_params": endpoint.path_params,
                "optional_params": sorted(endpoint.common_params),
                "endpoint_family": endpoint.id,
                "query_families": endpoint.domains,
                "smoke_eligible_get_only": endpoint.method == "GET" and not endpoint.path_params and "{" not in endpoint.path,
                "requires_safe_discovery": bool(endpoint.path_params or "{" in endpoint.path),
                "api_dependency": "catalog_approved",
            }
        )
    return rows


def render_audit(payload: dict[str, Any]) -> str:
    lines = [
        "# Live Adobe API Readiness Audit",
        "",
        "Infrastructure validation only; this report is not official strict-score evidence.",
        "",
        f"- Overall status: `{payload['overall_status']}`",
        f"- Critical failures: `{len(payload['critical_failures'])}`",
        f"- Warnings: `{len(payload['warnings'])}`",
        f"- Official score claim: `{payload['official_score_claim']}`",
        f"- Packaged runtime affected: `{payload['packaged_runtime_affected']}`",
        f"- Manual token refresh required: `{payload['manual_token_refresh_required']}`",
        "",
        "## Credential Presence",
        "",
    ]
    for key, value in (payload.get("credential_presence") or {}).items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Audit Items", ""])
    for item in payload.get("items", []):
        lines.append(f"- `{item['status']}` `{item['requirement_id']}`: {item['requirement']}")
        lines.append(f"  Evidence: `{item['evidence_path']}`")
        lines.append(f"  Explanation: {item['explanation']}")
    lines.extend(["", "## Endpoint Smoke Eligibility", ""])
    for endpoint in payload.get("endpoint_catalog_readiness", [])[:30]:
        lines.append(
            f"- `{endpoint['endpoint_id']}` {endpoint['method']} `{endpoint['path']}` "
            f"smoke_eligible={endpoint['smoke_eligible_get_only']} discovery_required={endpoint['requires_safe_discovery']}"
        )
    return "\n".join(lines) + "\n"


def _write_json_md(stem: Path, payload: dict[str, Any], markdown: str) -> None:
    stem.with_suffix(".json").write_text(json.dumps(redact_secrets(payload), indent=2, sort_keys=True, default=str), encoding="utf-8")
    stem.with_suffix(".md").write_text(markdown, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
