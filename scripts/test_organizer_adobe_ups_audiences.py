#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urljoin, urlparse

import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.adobe_env import DEFAULT_ADOBE_BASE_URL
from dashagent.api_client import AdobeAPIClient, TokenAcquisitionError
from dashagent.api_outcome_classifier import classify_api_outcome
from dashagent.api_response_parser import normalize_api_response
from dashagent.config import Config
from dashagent.endpoint_catalog import normalize_api_path
from dashagent.trajectory import compact_preview, redact_secrets
from scripts.load_local_env import load_local_env


REPORT_STEM = "organizer_adobe_ups_audiences_smoke"
EVIDENCE_REPORT_STEM = "organizer_adobe_ups_audiences_evidence_package"
UPS_AUDIENCES_PATH = "/data/core/ups/audiences"
DEFAULT_IMS_TOKEN_URL = "https://ims-na1.adobelogin.com/ims/token/v3"
ORGANIZER_DEFAULT_SCOPES = "openid,AdobeID,read_organizations,additional_info.projectedProductContext,session"
MAX_EXCERPT_CHARS = 300
EVIDENCE_MAX_EXCERPT_CHARS = 1000
REQUIRED_HEADER_NAMES = ["Authorization", "x-api-key", "x-gw-ims-org-id", "x-sandbox-name", "Content-Type"]


@dataclass(frozen=True)
class OrganizerAdobeCredentials:
    client_id: str | None
    client_secret: str | None
    ims_org: str | None
    sandbox: str | None
    base_url: str
    token_url: str
    scopes: str

    @property
    def missing_required_fields(self) -> list[str]:
        missing = []
        if not self.client_id:
            missing.append("client_id")
        if not self.client_secret:
            missing.append("client_secret")
        if not self.ims_org:
            missing.append("ims_org")
        if not self.sandbox:
            missing.append("sandbox")
        return missing

    @property
    def secret_values(self) -> list[str]:
        return [value for value in [self.client_id, self.client_secret, self.ims_org, self.sandbox] if value]


def main() -> int:
    parser = argparse.ArgumentParser(description="Safely run the organizer Adobe UPS audiences smoke snippet.")
    parser.add_argument(
        "--allow-failure",
        action="store_true",
        help="Write reports and exit 0 even when token acquisition or UPS audiences access fails.",
    )
    args = parser.parse_args()
    payload = run_organizer_adobe_ups_audiences_smoke(allow_failure=args.allow_failure)
    print(
        json.dumps(
            {
                "json": payload["output_paths"]["json"],
                "markdown": payload["output_paths"]["markdown"],
                "credential_valid_for_token": payload.get("credential_valid_for_token"),
                "ups_audiences_access_valid": payload.get("ups_audiences_access_valid"),
                "audiences_status_code": payload.get("audiences_status_code"),
                "audiences_outcome": payload.get("audiences_outcome"),
                "likely_issue": payload.get("likely_issue"),
                "comparison_conclusion": payload.get("comparison", {}).get("conclusion"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    if args.allow_failure:
        return 0
    if not payload.get("credential_valid_for_token"):
        return 1
    if not payload.get("ups_audiences_access_valid"):
        return 1
    return 0


def run_organizer_adobe_ups_audiences_smoke(
    config: Config | None = None,
    *,
    allow_failure: bool = False,
    post_func: Callable[..., Any] | None = None,
    get_func: Callable[..., Any] | None = None,
    repo_client_factory: Callable[[Config], AdobeAPIClient] | None = None,
    write_reports: bool = True,
    report_stem: str = REPORT_STEM,
    evidence_report_stem: str = EVIDENCE_REPORT_STEM,
    test_template: str = "organizer_adobe_ups_audiences_smoke",
) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    load_meta = load_local_env(config.project_root)
    credentials = resolve_organizer_adobe_credentials(os.environ)
    _mirror_token_url_for_repo_client(credentials.token_url)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    post_func = post_func or session.post
    get_func = get_func or session.get
    repo_client_factory = repo_client_factory or (lambda cfg: AdobeAPIClient(cfg))

    report: dict[str, Any] = {
        "report_type": report_stem,
        "test_template": test_template,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "diagnostic_only": True,
        "official_score_claim": False,
        "promotion_allowed": False,
        "auth_mode": "client_credentials",
        "request_template_shape": {
            "token_request_method": "POST",
            "token_request_url_host": urlparse(credentials.token_url).hostname or "",
            "token_request_path": urlparse(credentials.token_url).path or "",
            "token_request_content_type": "application/x-www-form-urlencoded",
            "grant_type": "client_credentials",
            "scopes_source": env_source_labels(os.environ).get("scopes_source", "missing"),
            "base_url_host": urlparse(credentials.base_url).hostname or "",
            "data_endpoint_method": "GET",
            "data_endpoint_path": UPS_AUDIENCES_PATH,
            "data_endpoint_params": {"limit": 5},
            "required_header_names": REQUIRED_HEADER_NAMES,
            "org_placeholder_name": "IMS_ORG",
            "sandbox_placeholder_name": "SANDBOX",
        },
        "env_present_missing": env_present_missing(credentials),
        "env_source_labels": env_source_labels(os.environ),
        "env_file_loaded": bool(load_meta.get("loaded")),
        "headers_constructible": {
            "Authorization": bool(credentials.client_id and credentials.client_secret),
            "Content-Type": True,
            "x-api-key": bool(credentials.client_id),
            "x-gw-ims-org-id": bool(credentials.ims_org),
            "x-sandbox-name": bool(credentials.sandbox),
        },
        "token_status_code": None,
        "token_acquisition_ok": False,
        "token_error_category": None,
        "audiences_status_code": None,
        "audiences_outcome": None,
        "credential_valid_for_token": False,
        "ups_audiences_access_valid": False,
        "likely_issue": "unknown",
        "json_parse_succeeded": False,
        "audience_items_present": False,
        "redacted_response_excerpt": None,
        "next_action": None,
        "direct_requests_result": {
            "token_ok": False,
            "status_code": None,
            "outcome": None,
        },
        "repo_client_result": {
            "token_ok": False,
            "status_code": None,
            "outcome": None,
        },
    }

    if credentials.missing_required_fields:
        report.update(
            {
                "token_error_category": "missing_required_env",
                "likely_issue": "bad_client_credentials",
                "next_action": "Populate .env.local with CLIENT_ID/CLIENT_SECRET/IMS_ORG/SANDBOX or the supported ADOBE_* aliases.",
            }
        )
        return _finalize_report(
            config,
            report,
            write_reports=write_reports,
            report_stem=report_stem,
            evidence_report_stem=evidence_report_stem,
        )

    token_result = _request_access_token(credentials, config, post_func)
    report["token_request_evidence"] = token_result.get("evidence", {})
    report.update(
        {
            "token_status_code": token_result["status_code"],
            "token_acquisition_ok": token_result["ok"],
            "credential_valid_for_token": token_result["ok"],
            "token_error_category": token_result.get("error_category"),
            "direct_requests_result": {
                "token_ok": token_result["ok"],
                "status_code": None,
                "outcome": None,
            },
        }
    )

    access_token = token_result.get("access_token")
    if not token_result["ok"] or not access_token:
        report.update(
            {
                "likely_issue": _likely_issue_for_token(token_result),
                "redacted_response_excerpt": token_result.get("safe_excerpt"),
                "next_action": "Verify client credentials, project API key, and IMS token scopes with the organizer.",
            }
        )
        return _finalize_report(
            config,
            report,
            write_reports=write_reports,
            report_stem=report_stem,
            evidence_report_stem=evidence_report_stem,
        )

    direct_result = _request_ups_audiences(credentials, config, str(access_token), get_func)
    outcome = direct_result["outcome"]
    access_valid = outcome in {"live_success", "live_empty"}
    report.update(
        {
            "audiences_status_code": direct_result["status_code"],
            "audiences_outcome": outcome,
            "ups_audiences_access_valid": access_valid,
            "json_parse_succeeded": direct_result["json_parse_succeeded"],
            "audience_items_present": direct_result["audience_items_present"],
            "redacted_response_excerpt": direct_result.get("safe_excerpt"),
            "likely_issue": "none" if access_valid else _likely_issue_for_outcome(outcome),
            "next_action": _next_action_for_outcome(outcome),
            "direct_requests_result": {
                "token_ok": True,
                "status_code": direct_result["status_code"],
                "outcome": outcome,
            },
            "direct_request_evidence": direct_result.get("evidence", {}),
        }
    )

    repo_result = _run_repo_client_comparison(config, repo_client_factory)
    report["repo_client_result"] = repo_result
    report["repo_request_evidence"] = repo_result.get("evidence", {})
    report["comparison"] = {
        "direct_requests_result": report["direct_requests_result"],
        "repo_client_result": repo_result,
        "conclusion": _comparison_conclusion(report["direct_requests_result"], repo_result),
    }
    report["evidence_equivalence"] = _evidence_equivalence(
        report.get("direct_request_evidence", {}),
        report.get("repo_request_evidence", {}),
        report.get("env_source_labels", {}),
        report["comparison"]["conclusion"],
    )
    if report["comparison"]["conclusion"] == "direct_success_repo_failure":
        report["next_action"] = "Investigate AdobeAPIClient header construction, endpoint path, and query params for this endpoint."
    return _finalize_report(
        config,
        report,
        write_reports=write_reports,
        report_stem=report_stem,
        evidence_report_stem=evidence_report_stem,
    )


def resolve_organizer_adobe_credentials(env: dict[str, str] | os._Environ[str]) -> OrganizerAdobeCredentials:
    return OrganizerAdobeCredentials(
        client_id=_env_first(env, "CLIENT_ID", "ADOBE_CLIENT_ID", "ADOBE_API_KEY"),
        client_secret=_env_first(env, "CLIENT_SECRET", "ADOBE_CLIENT_SECRET"),
        ims_org=_env_first(env, "IMS_ORG", "ADOBE_ORG_ID"),
        sandbox=_env_first(env, "SANDBOX", "ADOBE_SANDBOX_NAME"),
        base_url=_env_first(env, "ADOBE_BASE_URL") or DEFAULT_ADOBE_BASE_URL,
        token_url=_env_first(env, "ADOBE_IMS_TOKEN_URL") or DEFAULT_IMS_TOKEN_URL,
        scopes=_env_first(env, "ADOBE_SCOPES") or ORGANIZER_DEFAULT_SCOPES,
    )


def env_present_missing(credentials: OrganizerAdobeCredentials) -> dict[str, str]:
    return {
        "client_id": _present_missing(credentials.client_id),
        "client_secret": _present_missing(credentials.client_secret),
        "ims_org": _present_missing(credentials.ims_org),
        "sandbox": _present_missing(credentials.sandbox),
        "base_url": "present" if credentials.base_url else "missing",
        "token_url": "present" if credentials.token_url else "missing",
        "scopes": "present" if credentials.scopes else "missing",
    }


def env_source_labels(env: dict[str, str] | os._Environ[str]) -> dict[str, str]:
    return {
        "client_id_source": _source_label(env, primary=("ADOBE_CLIENT_ID", "ADOBE_API_KEY"), alias=("CLIENT_ID",)),
        "client_secret_source": _source_label(env, primary=("ADOBE_CLIENT_SECRET",), alias=("CLIENT_SECRET",)),
        "org_id_source": _source_label(env, primary=("ADOBE_ORG_ID",), alias=("IMS_ORG",)),
        "sandbox_source": _source_label(env, primary=("ADOBE_SANDBOX_NAME",), alias=("SANDBOX",)),
        "base_url_source": "primary" if env.get("ADOBE_BASE_URL") else "default",
        "scopes_source": "primary" if env.get("ADOBE_SCOPES") else "default",
    }


def classify_organizer_response(
    *,
    status_code: int | None,
    ok: bool,
    body: Any,
    json_parse_succeeded: bool,
    malformed_response: bool = False,
) -> str:
    parsed = normalize_api_response(
        body,
        ok=ok and not malformed_response,
        dry_run=False,
        status_code=status_code,
        endpoint=UPS_AUDIENCES_PATH,
        endpoint_id="ups_audiences",
        endpoint_family="ups_audiences",
        method="GET",
        path=UPS_AUDIENCES_PATH,
        max_preview_chars=MAX_EXCERPT_CHARS,
        malformed_response=malformed_response,
        error_category="malformed_response" if malformed_response else None,
        error=None if ok and not malformed_response else _body_to_text(body)[:MAX_EXCERPT_CHARS],
    )
    result = {
        "ok": ok and not malformed_response,
        "status_code": status_code,
        "parsed_evidence": parsed,
        "error": None if ok and json_parse_succeeded else _body_to_text(body)[:MAX_EXCERPT_CHARS],
        "result_preview": compact_preview(body, MAX_EXCERPT_CHARS),
    }
    return classify_api_outcome(result, method="GET", path=UPS_AUDIENCES_PATH)


def _request_access_token(
    credentials: OrganizerAdobeCredentials,
    config: Config,
    post_func: Callable[..., Any],
) -> dict[str, Any]:
    try:
        response = post_func(
            credentials.token_url,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "client_credentials",
                "client_id": credentials.client_id,
                "client_secret": credentials.client_secret,
                "scope": credentials.scopes,
            },
            timeout=config.api_timeout_seconds,
        )
    except Exception as exc:
        evidence = _token_request_evidence(
            credentials,
            status_code=None,
            json_parse_ok=False,
            access_token_field_present=False,
            token_acquisition_ok=False,
            expires_in_present=False,
            error_category="token_request_exception",
            failure_excerpt=_safe_excerpt(str(exc), credentials.secret_values),
        )
        return {
            "ok": False,
            "status_code": None,
            "error_category": "token_request_exception",
            "safe_excerpt": _safe_excerpt(str(exc), credentials.secret_values),
            "evidence": evidence,
        }
    status_code = getattr(response, "status_code", None)
    text = getattr(response, "text", "")
    try:
        body = response.json()
        json_ok = isinstance(body, dict)
    except ValueError:
        body = text
        json_ok = False
    token = body.get("access_token") if isinstance(body, dict) else None
    ok = bool(getattr(response, "ok", False) and token)
    error_category = None
    if not getattr(response, "ok", False):
        error_category = "token_http_error"
    elif not json_ok:
        error_category = "token_response_malformed"
    elif not token:
        error_category = "token_response_missing_access_token"
    return {
        "ok": ok,
        "status_code": status_code,
        "access_token": token if ok else None,
        "error_category": error_category,
        "safe_excerpt": None if ok else _safe_excerpt(body, credentials.secret_values),
        "evidence": _token_request_evidence(
            credentials,
            status_code=status_code,
            json_parse_ok=json_ok,
            access_token_field_present=bool(token),
            token_acquisition_ok=ok,
            expires_in_present=bool(isinstance(body, dict) and body.get("expires_in")),
            error_category=error_category,
            failure_excerpt=None if ok else _safe_excerpt(body, credentials.secret_values),
        ),
    }


def _request_ups_audiences(
    credentials: OrganizerAdobeCredentials,
    config: Config,
    access_token: str,
    get_func: Callable[..., Any],
) -> dict[str, Any]:
    url = urljoin(credentials.base_url.rstrip("/") + "/", UPS_AUDIENCES_PATH.lstrip("/"))
    secrets = [*credentials.secret_values, access_token]
    headers = {
        "Authorization": f"Bearer {access_token}",
        "x-api-key": credentials.client_id,
        "x-gw-ims-org-id": credentials.ims_org,
        "x-sandbox-name": credentials.sandbox,
        "Content-Type": "application/json",
    }
    try:
        response = get_func(url, headers=headers, params={"limit": 5}, timeout=config.api_timeout_seconds)
    except Exception as exc:
        evidence = _data_request_evidence(
            prefix="direct",
            method="GET",
            base_url=credentials.base_url,
            path=UPS_AUDIENCES_PATH,
            params={"limit": 5},
            header_names_sent=REQUIRED_HEADER_NAMES,
            status_code=None,
            json_parse_ok=False,
            outcome="external_api_unavailable",
            response_content_type=None,
            body=str(exc),
            secrets=secrets,
        )
        return {
            "status_code": None,
            "outcome": "external_api_unavailable",
            "json_parse_succeeded": False,
            "audience_items_present": False,
            "safe_excerpt": _safe_excerpt(str(exc), secrets),
            "evidence": evidence,
        }
    status_code = getattr(response, "status_code", None)
    text = getattr(response, "text", "")
    try:
        body = response.json()
        json_parse_succeeded = True
        malformed = False
    except ValueError:
        body = text
        json_parse_succeeded = False
        malformed = bool(getattr(response, "ok", False))
    ok = bool(getattr(response, "ok", False))
    outcome = classify_organizer_response(
        status_code=status_code,
        ok=ok,
        body=body,
        json_parse_succeeded=json_parse_succeeded,
        malformed_response=malformed,
    )
    return {
        "status_code": status_code,
        "outcome": outcome,
        "json_parse_succeeded": json_parse_succeeded,
        "audience_items_present": _audience_items_present(body),
        "safe_excerpt": _safe_excerpt(body, secrets),
        "evidence": _data_request_evidence(
            prefix="direct",
            method="GET",
            base_url=credentials.base_url,
            path=UPS_AUDIENCES_PATH,
            params={"limit": 5},
            header_names_sent=list(headers),
            status_code=status_code,
            json_parse_ok=json_parse_succeeded,
            outcome=outcome,
            response_content_type=_header_value(getattr(response, "headers", {}), "content-type"),
            body=body,
            secrets=secrets,
            response_headers=getattr(response, "headers", {}),
        ),
    }


def _run_repo_client_comparison(
    config: Config,
    repo_client_factory: Callable[[Config], AdobeAPIClient],
) -> dict[str, Any]:
    client = repo_client_factory(config)
    token_ok = False
    try:
        token_ok = bool(client.get_access_token())
    except TokenAcquisitionError as exc:
        return {
            "token_ok": False,
            "status_code": exc.status_code,
            "outcome": "token_acquisition_failed",
            "evidence": _repo_failure_evidence(status_code=exc.status_code, outcome="token_acquisition_failed"),
        }
    except Exception:
        return {
            "token_ok": False,
            "status_code": None,
            "outcome": "token_acquisition_failed",
            "evidence": _repo_failure_evidence(status_code=None, outcome="token_acquisition_failed"),
        }
    result = client.call_api("GET", UPS_AUDIENCES_PATH, {"limit": 5}, {})
    outcome = classify_api_outcome(result, method="GET", path=UPS_AUDIENCES_PATH)
    evidence = _repo_request_evidence(result, outcome)
    return {
        "token_ok": token_ok,
        "status_code": result.get("status_code"),
        "outcome": outcome,
        "evidence": evidence,
    }


def _comparison_conclusion(direct: dict[str, Any], repo: dict[str, Any]) -> str:
    direct_valid = direct.get("outcome") in {"live_success", "live_empty"}
    repo_valid = repo.get("outcome") in {"live_success", "live_empty"}
    if direct_valid and repo_valid:
        return "both_success"
    if direct_valid and not repo_valid:
        return "direct_success_repo_failure"
    if not direct_valid and repo_valid:
        return "direct_failure_repo_success"
    if direct.get("outcome") == repo.get("outcome"):
        return "both_same_failure"
    return "mismatch_needs_client_fix"


def _likely_issue_for_token(token_result: dict[str, Any]) -> str:
    status_code = token_result.get("status_code")
    if status_code in {400, 401, 403}:
        return "bad_client_credentials"
    return "unknown"


def _likely_issue_for_outcome(outcome: str | None) -> str:
    if outcome in {"live_success", "live_empty"}:
        return "none"
    if outcome in {"auth_error", "token_acquisition_failed"}:
        return "auth_header_or_api_key_issue"
    if outcome == "scope_or_permission_issue":
        return "permission_or_scope_issue"
    if outcome == "sandbox_scope_issue":
        return "sandbox_issue"
    if outcome == "endpoint_path_issue":
        return "endpoint_path_issue"
    if outcome in {"rate_limited", "external_api_unavailable"}:
        return "adobe_service_issue"
    if outcome == "malformed_response":
        return "malformed_response"
    return "unknown"


def _next_action_for_outcome(outcome: str | None) -> str:
    issue = _likely_issue_for_outcome(outcome)
    return {
        "none": "UPS audiences endpoint is reachable with the current credentials; continue live smoke and evidence pipeline checks.",
        "auth_header_or_api_key_issue": "Verify the API key/client ID and Authorization header expectations with Adobe project settings.",
        "permission_or_scope_issue": "Request or verify AEP/UPS audience read permissions and scopes for the Adobe project.",
        "sandbox_issue": "Verify the sandbox name/environment and IMS org access with the organizer.",
        "endpoint_path_issue": "Confirm the organizer endpoint path and API family/version before changing runtime paths.",
        "adobe_service_issue": "Rerun later or ask organizer whether Adobe service availability/rate limits are active.",
        "malformed_response": "Inspect the redacted response shape and add parser handling only if the endpoint is otherwise accessible.",
        "unknown": "Inspect the redacted status and response excerpt, then rerun the focused smoke.",
    }[issue]


def _finalize_report(
    config: Config,
    report: dict[str, Any],
    *,
    write_reports: bool,
    report_stem: str = REPORT_STEM,
    evidence_report_stem: str = EVIDENCE_REPORT_STEM,
) -> dict[str, Any]:
    reports_dir = config.outputs_dir / "reports"
    credential_valid_for_token = bool(report.get("credential_valid_for_token"))
    safe_env_present_missing = report.get("env_present_missing")
    safe_env_source_labels = report.get("env_source_labels")
    safe_request_template_shape = report.get("request_template_shape")
    report = redact_secrets(report)
    # Generic key-based redaction treats any key ending in "_token" as secret.
    # This report field is a boolean readiness result, not a token value.
    report["credential_valid_for_token"] = credential_valid_for_token
    if isinstance(safe_env_present_missing, dict):
        report["env_present_missing"] = safe_env_present_missing
    if isinstance(safe_env_source_labels, dict):
        report["env_source_labels"] = safe_env_source_labels
    if isinstance(safe_request_template_shape, dict):
        report["request_template_shape"] = safe_request_template_shape
    report["output_paths"] = {
        "json": str(reports_dir / f"{report_stem}.json"),
        "markdown": str(reports_dir / f"{report_stem}.md"),
    }
    if write_reports:
        reports_dir.mkdir(parents=True, exist_ok=True)
        evidence_package = _build_evidence_package(report, evidence_report_stem=evidence_report_stem)
        _assert_report_safe(report)
        _assert_report_safe(evidence_package)
        (reports_dir / f"{report_stem}.json").write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
        (reports_dir / f"{report_stem}.md").write_text(_render_markdown(report), encoding="utf-8")
        (reports_dir / f"{evidence_report_stem}.json").write_text(
            json.dumps(evidence_package, indent=2, sort_keys=True, default=str),
            encoding="utf-8",
        )
        evidence_markdown = _render_evidence_markdown(evidence_package)
        _assert_report_safe(evidence_markdown)
        (reports_dir / f"{evidence_report_stem}.md").write_text(evidence_markdown, encoding="utf-8")
    return report


def _build_evidence_package(report: dict[str, Any], *, evidence_report_stem: str = EVIDENCE_REPORT_STEM) -> dict[str, Any]:
    env_sources = report.get("env_source_labels") or {}
    token = report.get("token_request_evidence") or {}
    direct = report.get("direct_request_evidence") or {}
    repo = report.get("repo_request_evidence") or {}
    equivalence = report.get("evidence_equivalence") or _evidence_equivalence(
        direct,
        repo,
        env_sources,
        (report.get("comparison") or {}).get("conclusion"),
    )
    conclusion = _evidence_based_conclusion(equivalence.get("comparison_result"))
    package = {
        "test_identity": {
            "test_name": report.get("test_template") or "organizer_adobe_ups_audiences_smoke",
            "endpoint_purpose": "UPS audiences read-only validation",
            "data_endpoint_method": "GET",
            "data_endpoint_path": UPS_AUDIENCES_PATH,
            "data_endpoint_params": {"limit": 5},
            "data_endpoint_mutating": False,
            "direct_path_tested": bool(direct.get("direct_request_attempted")),
            "repo_client_path_tested": bool(repo.get("repo_request_attempted")),
            "generated_at": report.get("generated_at"),
        },
        "credential_loading_status": {
            "env_file_loaded": bool(report.get("env_file_loaded")),
            "auth_mode": report.get("auth_mode"),
            "client_id_source": env_sources.get("client_id_source", "missing"),
            "client_secret_source": env_sources.get("client_secret_source", "missing"),
            "org_id_source": env_sources.get("org_id_source", "missing"),
            "sandbox_source": env_sources.get("sandbox_source", "missing"),
            "base_url_source": env_sources.get("base_url_source", "missing"),
            "scopes_source": env_sources.get("scopes_source", "missing"),
            "same_resolved_config_used_for_direct_and_repo_paths": bool(equivalence.get("same_credential_sources")),
        },
        "token_acquisition_evidence": token,
        "direct_organizer_requests_path": direct,
        "repo_adobe_api_client_path": repo,
        "equivalence_verification": equivalence,
        "evidence_based_conclusion": {
            "conclusion": conclusion,
            "summary": _conclusion_summary(conclusion),
        },
        "output_paths": {
            "json": f"outputs/reports/{evidence_report_stem}.json",
            "markdown": f"outputs/reports/{evidence_report_stem}.md",
        },
    }
    _assert_report_safe(package)
    return package


def _render_markdown(report: dict[str, Any]) -> str:
    comparison = report.get("comparison", {})
    lines = [
        "# Organizer Adobe UPS Audiences Smoke",
        "",
        "Safe diagnostic implementation of the organizer token plus `/data/core/ups/audiences` smoke snippet.",
        "",
        f"- Auth mode: `{report.get('auth_mode')}`",
        f"- Token status code: `{report.get('token_status_code')}`",
        f"- Token acquisition ok: `{report.get('token_acquisition_ok')}`",
        f"- Audiences status code: `{report.get('audiences_status_code')}`",
        f"- Audiences outcome: `{report.get('audiences_outcome')}`",
        f"- Credential valid for token: `{report.get('credential_valid_for_token')}`",
        f"- UPS audiences access valid: `{report.get('ups_audiences_access_valid')}`",
        f"- Likely issue: `{report.get('likely_issue')}`",
        f"- Comparison conclusion: `{comparison.get('conclusion')}`",
        f"- Next action: {report.get('next_action')}",
        "",
        "## Environment Presence",
        "",
    ]
    for name, status in (report.get("env_present_missing") or {}).items():
        lines.append(f"- `{name}`: `{status}`")
    lines.extend(["", "## Side-by-Side Result", ""])
    direct = report.get("direct_requests_result") or {}
    repo = report.get("repo_client_result") or {}
    lines.extend(
        [
            f"- Direct requests: token `{direct.get('token_ok')}`, status `{direct.get('status_code')}`, outcome `{direct.get('outcome')}`",
            f"- Repo client: token `{repo.get('token_ok')}`, status `{repo.get('status_code')}`, outcome `{repo.get('outcome')}`",
            "",
            "Response excerpts are redacted and truncated. Raw credentials, tokens, header values, org values, and sandbox values are intentionally omitted.",
            "",
        ]
    )
    return "\n".join(lines)


def _render_evidence_markdown(package: dict[str, Any]) -> str:
    identity = package.get("test_identity", {})
    credentials = package.get("credential_loading_status", {})
    token = package.get("token_acquisition_evidence", {})
    direct = package.get("direct_organizer_requests_path", {})
    repo = package.get("repo_adobe_api_client_path", {})
    equivalence = package.get("equivalence_verification", {})
    conclusion = package.get("evidence_based_conclusion", {})
    lines = [
        "# Organizer Adobe UPS Audiences Evidence Package",
        "",
        "Fully redacted evidence package for the organizer-provided UPS audiences smoke test.",
        "",
        "## A. Test Identity",
        "",
        f"- test_name: `{identity.get('test_name')}`",
        f"- endpoint_purpose: `{identity.get('endpoint_purpose')}`",
        f"- data_endpoint_method: `{identity.get('data_endpoint_method')}`",
        f"- data_endpoint_path: `{identity.get('data_endpoint_path')}`",
        f"- data_endpoint_params: `{identity.get('data_endpoint_params')}`",
        f"- data_endpoint_mutating: `{identity.get('data_endpoint_mutating')}`",
        f"- direct_path_tested: `{identity.get('direct_path_tested')}`",
        f"- repo_client_path_tested: `{identity.get('repo_client_path_tested')}`",
        f"- generated_at: `{identity.get('generated_at')}`",
        "",
        "## B. Credential Loading Status",
        "",
    ]
    for key in [
        "env_file_loaded",
        "auth_mode",
        "client_id_source",
        "client_secret_source",
        "org_id_source",
        "sandbox_source",
        "base_url_source",
        "scopes_source",
        "same_resolved_config_used_for_direct_and_repo_paths",
    ]:
        lines.append(f"- {key}: `{credentials.get(key)}`")
    lines.extend(
        [
            "",
            "## C. Token Acquisition Evidence",
            "",
        ]
    )
    for key in [
        "token_request_attempted",
        "token_request_method",
        "token_request_url_host",
        "grant_type",
        "token_status_code",
        "token_json_parse_ok",
        "access_token_field_present",
        "token_acquisition_ok",
        "expires_in_present",
        "token_error_category",
        "token_redacted_response_excerpt",
    ]:
        if key in token:
            lines.append(f"- {key}: `{token.get(key)}`")
    lines.extend(["", "## D. Direct Organizer-Style Requests Path", ""])
    lines.extend(_request_markdown_lines(direct))
    lines.extend(["", "## E. Repo AdobeAPIClient Path", ""])
    lines.extend(_request_markdown_lines(repo))
    lines.extend(["", "## F. Equivalence Verification", ""])
    for key in [
        "same_method",
        "same_path",
        "same_params",
        "same_required_header_names",
        "same_credential_sources",
        "same_status_code",
        "same_outcome",
        "same_safe_error_shape",
        "comparison_result",
    ]:
        lines.append(f"- {key}: `{equivalence.get(key)}`")
    mismatch = equivalence.get("mismatch_explanation")
    if mismatch:
        lines.append(f"- mismatch_explanation: {mismatch}")
    lines.extend(
        [
            "",
            "## G. Evidence-Based Conclusion",
            "",
            f"- conclusion: `{conclusion.get('conclusion')}`",
            "",
            str(conclusion.get("summary") or ""),
            "",
        ]
    )
    return "\n".join(lines)


def _request_markdown_lines(section: dict[str, Any]) -> list[str]:
    return [
        f"- request_attempted: `{section.get('direct_request_attempted', section.get('repo_request_attempted'))}`",
        f"- method: `{section.get('method')}`",
        f"- base_url_host: `{section.get('base_url_host')}`",
        f"- path: `{section.get('path')}`",
        f"- params: `{section.get('params')}`",
        f"- header_names_sent: `{section.get('header_names_sent')}`",
        f"- header_values_redacted: `{section.get('header_values_redacted')}`",
        f"- status_code: `{section.get('status_code')}`",
        f"- json_parse_ok: `{section.get('json_parse_ok')}`",
        f"- outcome: `{section.get('outcome')}`",
        f"- response_content_type: `{section.get('response_content_type')}`",
        f"- safe_response_error_fields: `{section.get('safe_response_error_fields')}`",
        f"- adobe_diagnostic_ids: `{section.get('adobe_diagnostic_ids')}`",
        f"- redacted_response_excerpt: `{section.get('redacted_response_excerpt')}`",
    ]


def _token_request_evidence(
    credentials: OrganizerAdobeCredentials,
    *,
    status_code: int | None,
    json_parse_ok: bool,
    access_token_field_present: bool,
    token_acquisition_ok: bool,
    expires_in_present: bool,
    error_category: str | None,
    failure_excerpt: str | None,
) -> dict[str, Any]:
    evidence = {
        "token_request_attempted": True,
        "token_request_method": "POST",
        "token_request_url_host": urlparse(credentials.token_url).hostname or "",
        "grant_type": "client_credentials",
        "token_status_code": status_code,
        "token_json_parse_ok": json_parse_ok,
        "access_token_field_present": access_token_field_present,
        "token_acquisition_ok": token_acquisition_ok,
        "expires_in_present": expires_in_present,
        "token_error_category": error_category,
    }
    if not token_acquisition_ok:
        evidence["token_redacted_response_excerpt"] = failure_excerpt
    return evidence


def _data_request_evidence(
    *,
    prefix: str,
    method: str,
    base_url: str,
    path: str,
    params: dict[str, Any],
    header_names_sent: list[str],
    status_code: int | None,
    json_parse_ok: bool,
    outcome: str,
    response_content_type: str | None,
    body: Any,
    secrets: list[str],
    response_headers: Any | None = None,
) -> dict[str, Any]:
    excerpt = _safe_excerpt(body, secrets, max_chars=EVIDENCE_MAX_EXCERPT_CHARS)
    safe_error_fields = _safe_error_fields(body, secrets)
    return {
        f"{prefix}_request_attempted": True,
        "method": method,
        "base_url_host": urlparse(base_url).hostname or "",
        "path": normalize_api_path(path),
        "params": params,
        "header_names_sent": sorted(_dedupe(header_names_sent)),
        "header_values_redacted": True,
        "headers": _redacted_headers(header_names_sent),
        "status_code": status_code,
        "json_parse_ok": json_parse_ok,
        "outcome": outcome,
        "response_content_type": response_content_type,
        "redacted_response_excerpt": excerpt,
        "safe_response_error_fields": safe_error_fields,
        "adobe_diagnostic_ids": _diagnostic_ids(response_headers or {}, body),
    }


def _repo_request_evidence(result: dict[str, Any], outcome: str) -> dict[str, Any]:
    headers = result.get("headers") if isinstance(result.get("headers"), dict) else {}
    header_names = list(headers) if headers else REQUIRED_HEADER_NAMES
    parsed = result.get("parsed_evidence") if isinstance(result.get("parsed_evidence"), dict) else {}
    body = result.get("result_preview") or parsed.get("raw_preview") or result.get("error") or parsed.get("errors")
    return _data_request_evidence(
        prefix="repo",
        method=str(result.get("method") or "GET"),
        base_url=str(result.get("url") or DEFAULT_ADOBE_BASE_URL),
        path=str(result.get("endpoint") or UPS_AUDIENCES_PATH),
        params=result.get("params") if isinstance(result.get("params"), dict) else {"limit": 5},
        header_names_sent=header_names,
        status_code=result.get("status_code"),
        json_parse_ok=bool(parsed),
        outcome=outcome,
        response_content_type=result.get("response_content_type"),
        body=body,
        secrets=[],
    )


def _repo_failure_evidence(*, status_code: int | None, outcome: str) -> dict[str, Any]:
    return _data_request_evidence(
        prefix="repo",
        method="GET",
        base_url=DEFAULT_ADOBE_BASE_URL,
        path=UPS_AUDIENCES_PATH,
        params={"limit": 5},
        header_names_sent=REQUIRED_HEADER_NAMES,
        status_code=status_code,
        json_parse_ok=False,
        outcome=outcome,
        response_content_type=None,
        body={"error": outcome},
        secrets=[],
    )


def _evidence_equivalence(
    direct: dict[str, Any],
    repo: dict[str, Any],
    env_sources: dict[str, Any],
    comparison_result: str | None,
) -> dict[str, Any]:
    required = set(REQUIRED_HEADER_NAMES)
    direct_headers = set(direct.get("header_names_sent") or [])
    repo_headers = set(repo.get("header_names_sent") or [])
    same_error_shape = _error_shape(direct.get("safe_response_error_fields")) == _error_shape(repo.get("safe_response_error_fields"))
    if not direct.get("direct_request_attempted") or not repo.get("repo_request_attempted"):
        comparison_result = "not_comparable"
    comparison_result = comparison_result or "not_comparable"
    if comparison_result == "mismatch_needs_client_fix":
        comparison_result = _comparison_result_from_booleans(direct, repo)
    booleans = {
        "same_method": direct.get("method") == repo.get("method"),
        "same_path": direct.get("path") == repo.get("path"),
        "same_params": direct.get("params") == repo.get("params"),
        "same_required_header_names": required <= direct_headers and required <= repo_headers,
        "same_credential_sources": all(
            env_sources.get(key) in {"primary", "alias", "default"}
            for key in ["client_id_source", "client_secret_source", "org_id_source", "sandbox_source", "base_url_source", "scopes_source"]
        ),
        "same_status_code": direct.get("status_code") == repo.get("status_code"),
        "same_outcome": direct.get("outcome") == repo.get("outcome"),
        "same_safe_error_shape": same_error_shape,
    }
    return {
        **booleans,
        "comparison_result": comparison_result,
        "mismatch_explanation": _mismatch_explanation(booleans),
    }


def _comparison_result_from_booleans(direct: dict[str, Any], repo: dict[str, Any]) -> str:
    direct_success = direct.get("outcome") in {"live_success", "live_empty"}
    repo_success = repo.get("outcome") in {"live_success", "live_empty"}
    if direct_success and repo_success:
        return "both_success"
    if direct_success and not repo_success:
        return "direct_success_repo_failure"
    if not direct_success and repo_success:
        return "direct_failure_repo_success"
    if direct.get("status_code") == repo.get("status_code") and direct.get("outcome") == repo.get("outcome"):
        return "both_same_failure"
    return "not_comparable"


def _evidence_based_conclusion(comparison_result: str | None) -> str:
    if comparison_result == "both_success":
        return "repo_client_path_validated_against_direct_success"
    if comparison_result in {"direct_success_repo_failure", "direct_failure_repo_success"}:
        return "repo_client_mismatch_detected"
    if comparison_result == "both_same_failure":
        return "both_paths_failed_equivalently_no_repo_specific_mismatch_shown"
    return "test_not_comparable_due_to_missing_evidence"


def _conclusion_summary(conclusion: str) -> str:
    if conclusion == "both_paths_failed_equivalently_no_repo_specific_mismatch_shown":
        return (
            "Both the organizer-style direct request and the repo AdobeAPIClient request failed with the same HTTP "
            "status/outcome. This does not show a repo-specific header/client mismatch. Root cause may still be Adobe "
            "endpoint availability, sandbox, organization context, or product-profile permission."
        )
    if conclusion == "repo_client_path_validated_against_direct_success":
        return "Both paths reached UPS audiences successfully with equivalent redacted request shape."
    if conclusion == "repo_client_mismatch_detected":
        return "The direct and repo client paths diverged; inspect the redacted equivalence fields before changing runtime code."
    return "The evidence package is incomplete or the two requests were not comparable."


def _mismatch_explanation(booleans: dict[str, bool]) -> str | None:
    mismatched = [name for name, value in booleans.items() if not value]
    if not mismatched:
        return None
    return "Mismatched redacted comparison fields: " + ", ".join(mismatched)


def _redacted_headers(header_names: list[str]) -> dict[str, str]:
    headers = {}
    for name in sorted(_dedupe(header_names)):
        headers[name] = "application/json" if name.lower() == "content-type" else "<redacted>"
    return headers


def _safe_error_fields(body: Any, secrets: list[str]) -> dict[str, Any]:
    if not isinstance(body, dict):
        return {}
    candidates = {
        "error_code": _first_present(body, ["error_code", "errorCode", "code", "error"]),
        "error_message": _first_present(body, ["error_message", "errorMessage", "message", "detail", "description"]),
        "title": body.get("title"),
        "status": body.get("status"),
    }
    return {
        key: _safe_excerpt(value, secrets, max_chars=240)
        for key, value in candidates.items()
        if value not in (None, "", [], {})
    }


def _first_present(body: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        if key in body and body[key] not in (None, "", [], {}):
            return body[key]
    nested = body.get("error")
    if isinstance(nested, dict):
        return _first_present(nested, keys)
    return None


def _diagnostic_ids(headers: Any, body: Any) -> dict[str, str]:
    result: dict[str, str] = {}
    if isinstance(headers, dict):
        for key, value in headers.items():
            lowered = str(key).lower()
            if lowered in {"x-request-id", "request-id", "x-correlation-id", "x-trace-id", "x-adobe-request-id"}:
                result[str(key)] = _safe_diagnostic_id(value)
    if isinstance(body, dict):
        for key in ["requestId", "request-id", "registryRequestId", "correlationId", "traceId"]:
            value = body.get(key)
            if value:
                result[key] = _safe_diagnostic_id(value)
    return result


def _safe_diagnostic_id(value: Any) -> str:
    text = str(value or "")
    if not text:
        return ""
    if len(text) > 120:
        return "[REDACTED_DIAGNOSTIC_ID]"
    return text


def _error_shape(fields: Any) -> list[str]:
    if not isinstance(fields, dict):
        return []
    return sorted(fields)


def _safe_excerpt(value: Any, secrets: list[str], *, max_chars: int = MAX_EXCERPT_CHARS) -> str:
    redacted = redact_secrets(value)
    text = _body_to_text(redacted)
    for secret in secrets:
        if secret:
            text = text.replace(secret, "[REDACTED]")
    text = re.sub(r"Authorization\s*:\s*Bearer\s+[^\s,'\"}]+", "Authorization: Bearer [REDACTED]", text, flags=re.IGNORECASE)
    text = re.sub(r"Bearer\s+[A-Za-z0-9._-]{8,}", "Bearer [REDACTED]", text, flags=re.IGNORECASE)
    text = re.sub(r"sk-[A-Za-z0-9_-]{8,}", "[REDACTED]", text)
    text = re.sub(r"\b(request-id|registryRequestId|x-request-id|trace[-_ ]?id)\b[\"':= ]+[A-Za-z0-9._:-]+", r"\1=[REDACTED]", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]


def _audience_items_present(body: Any) -> bool:
    if isinstance(body, list):
        return bool(body)
    if not isinstance(body, dict):
        return False
    for key in ("items", "results", "data", "audiences", "children"):
        value = body.get(key)
        if isinstance(value, list) and value:
            return True
        if isinstance(value, dict) and value:
            return True
    return False


def _body_to_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, sort_keys=True, default=str)
    except TypeError:
        return str(value)


def _env_first(env: dict[str, str] | os._Environ[str], *names: str) -> str | None:
    for name in names:
        value = env.get(name)
        if value:
            return value
    return None


def _source_label(env: dict[str, str] | os._Environ[str], *, primary: tuple[str, ...], alias: tuple[str, ...]) -> str:
    if any(env.get(name) for name in primary):
        return "primary"
    if any(env.get(name) for name in alias):
        return "alias"
    return "missing"


def _present_missing(value: Any) -> str:
    return "present" if bool(value) else "missing"


def _mirror_token_url_for_repo_client(token_url: str) -> None:
    if token_url and not os.environ.get("ADOBE_TOKEN_URL"):
        os.environ["ADOBE_TOKEN_URL"] = token_url


def _header_value(headers: Any, name: str) -> str | None:
    if not isinstance(headers, dict):
        return None
    for key, value in headers.items():
        if str(key).lower() == name.lower():
            text = str(value)
            return text[:120]
    return None


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        key = text.lower()
        if text and key not in seen:
            seen.add(key)
            result.append(text)
    return result


def _assert_report_safe(payload: Any) -> None:
    text = payload if isinstance(payload, str) else json.dumps(payload, sort_keys=True, default=str)
    secret_env_names = [
        "ADOBE_ACCESS_TOKEN",
        "ACCESS_TOKEN",
        "CLIENT_SECRET",
        "ADOBE_CLIENT_SECRET",
        "CLIENT_ID",
        "ADOBE_CLIENT_ID",
        "ADOBE_API_KEY",
        "IMS_ORG",
        "ADOBE_ORG_ID",
        "SANDBOX",
        "ADOBE_SANDBOX_NAME",
    ]
    leaked = []
    for name in secret_env_names:
        value = os.environ.get(name)
        if value and len(value) >= 3 and value in text:
            leaked.append(name)
    if leaked:
        raise RuntimeError(f"Refusing to write report with unredacted secret values: {', '.join(sorted(set(leaked)))}")
    if re.search(r"Authorization\s*:\s*Bearer\s+(?!\[REDACTED\])[^\s,'\"}]+", text, flags=re.IGNORECASE):
        raise RuntimeError("Refusing to write report with unredacted Authorization bearer value.")
    if re.search(r"\bBearer\s+(?!\[REDACTED\])[A-Za-z0-9._-]{8,}", text, flags=re.IGNORECASE):
        raise RuntimeError("Refusing to write report with unredacted bearer value.")
    if re.search(r"\b[A-Za-z0-9_-]{3,}\*\*\*", text):
        raise RuntimeError("Refusing to write report with masked credential prefix.")


if __name__ == "__main__":
    raise SystemExit(main())
