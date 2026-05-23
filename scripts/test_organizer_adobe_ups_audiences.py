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
from urllib.parse import urljoin

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
UPS_AUDIENCES_PATH = "/data/core/ups/audiences"
DEFAULT_IMS_TOKEN_URL = "https://ims-na1.adobelogin.com/ims/token/v3"
ORGANIZER_DEFAULT_SCOPES = "openid,AdobeID,read_organizations,additional_info.projectedProductContext,session"
MAX_EXCERPT_CHARS = 300


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
) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    load_local_env(config.project_root)
    credentials = resolve_organizer_adobe_credentials(os.environ)
    _mirror_token_url_for_repo_client(credentials.token_url)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    post_func = post_func or session.post
    get_func = get_func or session.get
    repo_client_factory = repo_client_factory or (lambda cfg: AdobeAPIClient(cfg))

    report: dict[str, Any] = {
        "report_type": REPORT_STEM,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "diagnostic_only": True,
        "official_score_claim": False,
        "promotion_allowed": False,
        "auth_mode": "client_credentials",
        "env_present_missing": env_present_missing(credentials),
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
        return _finalize_report(config, report, write_reports=write_reports)

    token_result = _request_access_token(credentials, config, post_func)
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
        return _finalize_report(config, report, write_reports=write_reports)

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
        }
    )

    repo_result = _run_repo_client_comparison(config, repo_client_factory)
    report["repo_client_result"] = repo_result
    report["comparison"] = {
        "direct_requests_result": report["direct_requests_result"],
        "repo_client_result": repo_result,
        "conclusion": _comparison_conclusion(report["direct_requests_result"], repo_result),
    }
    if report["comparison"]["conclusion"] == "direct_success_repo_failure":
        report["next_action"] = "Investigate AdobeAPIClient header construction, endpoint path, and query params for this endpoint."
    return _finalize_report(config, report, write_reports=write_reports)


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
            data={
                "grant_type": "client_credentials",
                "client_id": credentials.client_id,
                "client_secret": credentials.client_secret,
                "scope": credentials.scopes,
            },
            timeout=config.api_timeout_seconds,
        )
    except Exception as exc:
        return {
            "ok": False,
            "status_code": None,
            "error_category": "token_request_exception",
            "safe_excerpt": _safe_excerpt(str(exc), credentials.secret_values),
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
        return {
            "status_code": None,
            "outcome": "external_api_unavailable",
            "json_parse_succeeded": False,
            "audience_items_present": False,
            "safe_excerpt": _safe_excerpt(str(exc), secrets),
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
        }
    except Exception:
        return {
            "token_ok": False,
            "status_code": None,
            "outcome": "token_acquisition_failed",
        }
    result = client.call_api("GET", UPS_AUDIENCES_PATH, {"limit": 5}, {})
    outcome = classify_api_outcome(result, method="GET", path=UPS_AUDIENCES_PATH)
    return {
        "token_ok": token_ok,
        "status_code": result.get("status_code"),
        "outcome": outcome,
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


def _finalize_report(config: Config, report: dict[str, Any], *, write_reports: bool) -> dict[str, Any]:
    reports_dir = config.outputs_dir / "reports"
    credential_valid_for_token = bool(report.get("credential_valid_for_token"))
    report = redact_secrets(report)
    # Generic key-based redaction treats any key ending in "_token" as secret.
    # This report field is a boolean readiness result, not a token value.
    report["credential_valid_for_token"] = credential_valid_for_token
    report["output_paths"] = {
        "json": str(reports_dir / f"{REPORT_STEM}.json"),
        "markdown": str(reports_dir / f"{REPORT_STEM}.md"),
    }
    if write_reports:
        reports_dir.mkdir(parents=True, exist_ok=True)
        (reports_dir / f"{REPORT_STEM}.json").write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
        (reports_dir / f"{REPORT_STEM}.md").write_text(_render_markdown(report), encoding="utf-8")
    return report


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


def _safe_excerpt(value: Any, secrets: list[str]) -> str:
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
    return text[:MAX_EXCERPT_CHARS]


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


def _present_missing(value: Any) -> str:
    return "present" if bool(value) else "missing"


def _mirror_token_url_for_repo_client(token_url: str) -> None:
    if token_url and not os.environ.get("ADOBE_TOKEN_URL"):
        os.environ["ADOBE_TOKEN_URL"] = token_url


if __name__ == "__main__":
    raise SystemExit(main())
