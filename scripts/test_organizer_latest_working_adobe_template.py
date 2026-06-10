#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import requests

from dashagent.adobe_env import DEFAULT_ADOBE_SCOPES
from dashagent.config import Config
from dashagent.trajectory import redact_secrets
from scripts.test_organizer_adobe_ups_audiences import (
    DEFAULT_IMS_TOKEN_URL,
    ORGANIZER_DEFAULT_SCOPES,
    REQUIRED_HEADER_NAMES,
    UPS_AUDIENCES_PATH,
    OrganizerAdobeCredentials,
    _request_access_token,
    _request_ups_audiences,
)


REPORT_STEM = "organizer_latest_working_template_smoke"
EQUIVALENCE_REPORT_STEM = "organizer_latest_template_repo_client_equivalence"
ORGANIZER_ENV_FILENAME = ".env.organizer_latest.local"

EXACT = "exact"
INCOMPLETE = "incomplete_template_fields"
OLD_ENV_CONTAMINATED = "contaminated_by_old_env_fallback"
REPO_DEFAULT_CONTAMINATED = "contaminated_by_repo_default_fallback"


@dataclass(frozen=True)
class ResolvedLatestTemplate:
    credentials: OrganizerAdobeCredentials | None
    parsed_latest_env: dict[str, str]
    parsed_old_env: dict[str, str]
    latest_env_path: Path
    exact_reproduction_status: str
    missing_fields: list[str]
    field_sources: dict[str, str]
    fallback_flags: dict[str, bool]
    safe_booleans: dict[str, bool | None]


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Safely reproduce PATH B, the organizer latest exact Adobe UPS audiences template. "
            "This script reads .env.organizer_latest.local directly and refuses old-env/repo-default fallback."
        )
    )
    parser.add_argument(
        "--allow-failure",
        action="store_true",
        help="Write redacted reports and exit 0 even when PATH B does not return live_success.",
    )
    args = parser.parse_args()
    payload = run_organizer_latest_working_adobe_template(allow_failure=args.allow_failure)
    path_b = payload.get("paths", {}).get("PATH_B_organizer_latest_exact_direct", {})
    print(
        json.dumps(
            {
                "json": payload["output_paths"]["json"],
                "markdown": payload["output_paths"]["markdown"],
                "exact_reproduction_status": payload.get("exact_reproduction_status"),
                "latest_env_file_loaded": payload.get("latest_env_file_loaded"),
                "old_env_fallback_used_for_ims_org": payload.get("fallback_flags", {}).get("old_env_fallback_used_for_ims_org"),
                "old_env_fallback_used_for_sandbox": payload.get("fallback_flags", {}).get("old_env_fallback_used_for_sandbox"),
                "old_env_fallback_used_for_scopes": payload.get("fallback_flags", {}).get("old_env_fallback_used_for_scopes"),
                "repo_default_fallback_used": payload.get("fallback_flags", {}).get("repo_default_fallback_used"),
                "path_b_status_code": path_b.get("status_code"),
                "path_b_outcome": path_b.get("outcome"),
                "path_b_live_success": path_b.get("live_success"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    if payload.get("exact_reproduction_status") != EXACT:
        return 1
    if args.allow_failure:
        return 0
    return 0 if path_b.get("outcome") in {"live_success", "live_empty"} else 1


def run_organizer_latest_working_adobe_template(
    config: Config | None = None,
    *,
    allow_failure: bool = False,
) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    resolved = resolve_latest_template_for_path_b(config.project_root)
    report = _base_report(config, resolved)
    if resolved.exact_reproduction_status != EXACT or not resolved.credentials:
        _write_reports(config, report)
        return report

    session = requests.Session()
    token_result = _request_access_token(resolved.credentials, config, session.post)
    report["token_request_evidence"] = _strip_token_evidence(token_result.get("evidence") or {})
    report["token_status_code"] = token_result.get("status_code")
    report["token_acquisition_ok"] = bool(token_result.get("ok"))
    report["credential_valid_for_token"] = bool(token_result.get("ok"))
    report["token_error_category"] = token_result.get("error_category")
    access_token = token_result.get("access_token")

    if not token_result.get("ok") or not access_token:
        report["paths"]["PATH_B_organizer_latest_exact_direct"].update(
            {
                "attempted": False,
                "blocked_reason": "token_acquisition_failed",
                "status_code": None,
                "outcome": "token_acquisition_failed",
                "live_success": False,
            }
        )
        report["next_action"] = "Verify client credentials in .env.organizer_latest.local without changing source code."
        _write_reports(config, report, resolved.credentials.secret_values)
        return report

    direct_result = _request_ups_audiences(resolved.credentials, config, str(access_token), session.get)
    outcome = direct_result.get("outcome")
    report["paths"]["PATH_B_organizer_latest_exact_direct"].update(
        {
            "attempted": True,
            "method": "GET",
            "path": UPS_AUDIENCES_PATH,
            "params": {"limit": 5},
            "header_names_sent": REQUIRED_HEADER_NAMES,
            "header_values_redacted": True,
            "status_code": direct_result.get("status_code"),
            "json_parse_ok": direct_result.get("json_parse_succeeded"),
            "outcome": outcome,
            "live_success": outcome == "live_success",
            "live_empty": outcome == "live_empty",
            "audience_items_present": direct_result.get("audience_items_present"),
            "redacted_response_excerpt": (direct_result.get("evidence") or {}).get("redacted_response_excerpt"),
            "safe_response_error_fields": (direct_result.get("evidence") or {}).get("safe_response_error_fields"),
        }
    )
    report["audiences_status_code"] = direct_result.get("status_code")
    report["audiences_outcome"] = outcome
    report["ups_audiences_access_valid"] = outcome in {"live_success", "live_empty"}
    report["next_action"] = _next_action_for_path_b(report)
    _write_reports(config, report, [*resolved.credentials.secret_values, str(access_token)])
    return report


def resolve_latest_template_for_path_b(project_root: Path) -> ResolvedLatestTemplate:
    latest_path = project_root / ORGANIZER_ENV_FILENAME
    latest = _parse_env_file(latest_path)
    old = _parse_env_file(project_root / ".env.local")
    field_sources: dict[str, str] = {}
    missing: list[str] = []

    client_id, client_id_key = _required(latest, "client_id", ("CLIENT_ID",))
    client_secret, client_secret_key = _required(latest, "client_secret", ("CLIENT_SECRET",))
    ims_org, ims_org_key = _required(latest, "ims_org", ("IMS_ORG",))
    sandbox, sandbox_key = _required(latest, "sandbox", ("SANDBOX",))
    scopes, scopes_key = _required(latest, "scopes", ("ADOBE_SCOPES", "SCOPES"))
    base_url, base_url_key = _required(latest, "base_url", ("ADOBE_BASE_URL", "BASE_URL"))
    token_url, token_url_key = _required(latest, "token_url", ("ADOBE_IMS_TOKEN_URL", "IMS_TOKEN_URL"))

    values = {
        "client_id": (client_id, client_id_key),
        "client_secret": (client_secret, client_secret_key),
        "ims_org": (ims_org, ims_org_key),
        "sandbox": (sandbox, sandbox_key),
        "scopes": (scopes, scopes_key),
        "base_url": (base_url, base_url_key),
        "token_url": (token_url, token_url_key),
    }
    for field, (value, key) in values.items():
        if value:
            field_sources[field] = f"organizer_latest_file:{key}"
        else:
            missing.append(field)
            field_sources[field] = "missing"

    fallback_flags = {
        "old_env_fallback_used_for_ims_org": False,
        "old_env_fallback_used_for_sandbox": False,
        "old_env_fallback_used_for_scopes": False,
        "old_env_fallback_used_for_base_url": False,
        "old_env_fallback_used_for_token_url": False,
        "repo_default_fallback_used": False,
    }
    if not latest_path.exists() or missing:
        status = INCOMPLETE
    else:
        status = EXACT

    credentials = None
    if status == EXACT:
        credentials = OrganizerAdobeCredentials(
            client_id=client_id,
            client_secret=client_secret,
            ims_org=ims_org,
            sandbox=sandbox,
            base_url=base_url or "",
            token_url=token_url or "",
            scopes=scopes or "",
        )
    safe_booleans = _safe_comparison_booleans(latest, old)
    return ResolvedLatestTemplate(
        credentials=credentials,
        parsed_latest_env=latest,
        parsed_old_env=old,
        latest_env_path=latest_path,
        exact_reproduction_status=status,
        missing_fields=missing,
        field_sources=field_sources,
        fallback_flags=fallback_flags,
        safe_booleans=safe_booleans,
    )


def _base_report(config: Config, resolved: ResolvedLatestTemplate) -> dict[str, Any]:
    path_a = _path_a_result(config)
    return {
        "report_type": REPORT_STEM,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "diagnostic_only": True,
        "official_score_claim": False,
        "promotion_allowed": False,
        "test_template": "organizer_latest_working_template",
        "auth_mode": "client_credentials",
        "latest_env_file": ORGANIZER_ENV_FILENAME,
        "latest_env_file_loaded": resolved.latest_env_path.exists(),
        "exact_reproduction_status": resolved.exact_reproduction_status,
        "missing_required_template_fields": resolved.missing_fields,
        "field_sources": resolved.field_sources,
        "fallback_flags": resolved.fallback_flags,
        "safe_boolean_comparison": resolved.safe_booleans,
        "request_template_shape": {
            "token_request_method": "POST",
            "token_request_url_source": resolved.field_sources.get("token_url"),
            "token_request_content_type": "application/x-www-form-urlencoded",
            "grant_type": "client_credentials",
            "scopes_source": resolved.field_sources.get("scopes"),
            "base_url_source": resolved.field_sources.get("base_url"),
            "data_endpoint_method": "GET",
            "data_endpoint_path": UPS_AUDIENCES_PATH,
            "data_endpoint_params": {"limit": 5},
            "required_header_names": REQUIRED_HEADER_NAMES,
            "org_source": resolved.field_sources.get("ims_org"),
            "sandbox_source": resolved.field_sources.get("sandbox"),
        },
        "token_status_code": None,
        "token_acquisition_ok": False,
        "credential_valid_for_token": False,
        "token_error_category": None,
        "audiences_status_code": None,
        "audiences_outcome": None,
        "ups_audiences_access_valid": False,
        "paths": {
            "PATH_A_old_local_configuration": path_a,
            "PATH_B_organizer_latest_exact_direct": {
                "attempted": False,
                "method": "GET",
                "path": UPS_AUDIENCES_PATH,
                "params": {"limit": 5},
                "header_names_sent": REQUIRED_HEADER_NAMES,
                "header_values_redacted": True,
                "status_code": None,
                "outcome": None,
                "live_success": False,
            },
            "PATH_C_repo_client_current": {
                "attempted": False,
                "status": "not_run_in_path_b_isolation_pass",
                "reason": "PATH B exact reproduction must be established before repo-client correction testing.",
            },
        },
        "next_action": None,
        "output_paths": {
            "json": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.json"),
            "markdown": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.md"),
        },
    }


def _path_a_result(config: Config) -> dict[str, Any]:
    baseline = _load_json(config.outputs_dir / "reports" / "baselines" / "organizer_adobe_ups_audiences_old_template_500.json")
    if not baseline:
        baseline = _load_json(config.outputs_dir / "reports" / "organizer_adobe_ups_audiences_smoke.json")
    return {
        "attempted": bool(baseline),
        "source": "historical_report",
        "token_status_code": baseline.get("token_status_code"),
        "token_acquisition_ok": baseline.get("token_acquisition_ok"),
        "method": "GET",
        "path": UPS_AUDIENCES_PATH,
        "params": {"limit": 5},
        "status_code": baseline.get("audiences_status_code"),
        "outcome": baseline.get("audiences_outcome"),
        "comparison_result": (baseline.get("comparison") or {}).get("conclusion"),
    }


def _safe_comparison_booleans(latest: dict[str, str], old: dict[str, str]) -> dict[str, bool | None]:
    latest_org = latest.get("IMS_ORG")
    latest_sandbox = latest.get("SANDBOX")
    latest_scopes = _first(latest, "ADOBE_SCOPES", "SCOPES")
    old_org = _first(old, "IMS_ORG", "ADOBE_ORG_ID")
    old_sandbox = _first(old, "SANDBOX", "ADOBE_SANDBOX_NAME")
    old_direct_scopes = _first(old, "ADOBE_SCOPES", "SCOPES") or ORGANIZER_DEFAULT_SCOPES
    repo_org = _first(old, "ADOBE_ORG_ID", "IMS_ORG")
    repo_sandbox = _first(old, "ADOBE_SANDBOX_NAME", "SANDBOX")
    repo_scopes = _first(old, "ADOBE_SCOPES", "SCOPES") or DEFAULT_ADOBE_SCOPES
    return {
        "org_same_old_vs_latest": _same_or_none(old_org, latest_org),
        "sandbox_same_old_vs_latest": _same_or_none(old_sandbox, latest_sandbox),
        "scopes_same_old_vs_latest": _same_or_none(old_direct_scopes, latest_scopes),
        "token_content_type_same_old_vs_latest": False,
        "latest_matches_repo_client_org": _same_or_none(repo_org, latest_org),
        "latest_matches_repo_client_sandbox": _same_or_none(repo_sandbox, latest_sandbox),
        "latest_matches_repo_client_scopes": _same_or_none(repo_scopes, latest_scopes),
    }


def _write_reports(config: Config, report: dict[str, Any], secrets: list[str] | None = None) -> None:
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    safe_report = redact_secrets(report)
    for key in ["field_sources", "fallback_flags", "safe_boolean_comparison", "request_template_shape", "paths"]:
        safe_report[key] = report[key]
    _assert_safe(safe_report, secrets or [])
    (reports_dir / f"{REPORT_STEM}.json").write_text(json.dumps(safe_report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    markdown = _render_markdown(safe_report)
    _assert_safe(markdown, secrets or [])
    (reports_dir / f"{REPORT_STEM}.md").write_text(markdown, encoding="utf-8")


def _render_markdown(report: dict[str, Any]) -> str:
    path_b = report.get("paths", {}).get("PATH_B_organizer_latest_exact_direct", {})
    lines = [
        "# Organizer Latest Working Template Smoke",
        "",
        f"Generated at: `{report.get('generated_at')}`",
        "",
        "This is the isolated PATH B exact reproduction report. It reads `.env.organizer_latest.local` directly and does not fall back to old `.env.local` values or repo defaults for request-context fields.",
        "",
        f"- exact_reproduction_status: `{report.get('exact_reproduction_status')}`",
        f"- latest_env_file_loaded: `{report.get('latest_env_file_loaded')}`",
        f"- token_status_code: `{report.get('token_status_code')}`",
        f"- token_acquisition_ok: `{report.get('token_acquisition_ok')}`",
        f"- PATH B status/outcome: `{path_b.get('status_code')}` / `{path_b.get('outcome')}`",
        f"- PATH B live_success: `{path_b.get('live_success')}`",
        "",
        "## Fallback Flags",
        "",
    ]
    for key, value in (report.get("fallback_flags") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Safe Boolean Comparison", ""])
    for key, value in (report.get("safe_boolean_comparison") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## PATH Results", ""])
    for name, payload in (report.get("paths") or {}).items():
        lines.append(f"### {name}")
        lines.append("")
        for key in ["attempted", "status", "reason", "method", "path", "params", "status_code", "outcome", "live_success"]:
            if key in payload:
                lines.append(f"- {key}: `{payload.get(key)}`")
        excerpt = payload.get("redacted_response_excerpt")
        if excerpt:
            lines.append(f"- redacted_response_excerpt: `{excerpt}`")
        lines.append("")
    if report.get("next_action"):
        lines.extend(["## Next Action", "", str(report.get("next_action")), ""])
    return "\n".join(lines)


def _parse_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    result: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key):
            continue
        result[key] = _strip_quotes(value.strip())
    return result


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _required(env: dict[str, str], public_name: str, keys: tuple[str, ...]) -> tuple[str | None, str]:
    value = _first(env, *keys)
    if not value:
        return None, "missing"
    for key in keys:
        if env.get(key):
            return env[key], key
    return None, "missing"


def _first(env: dict[str, str], *keys: str) -> str | None:
    for key in keys:
        value = env.get(key)
        if value:
            return value
    return None


def _same_or_none(left: str | None, right: str | None) -> bool | None:
    if not left or not right:
        return None
    return left == right


def _strip_token_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in evidence.items()
        if key
        in {
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
        }
    }


def _next_action_for_path_b(report: dict[str, Any]) -> str:
    path_b = report.get("paths", {}).get("PATH_B_organizer_latest_exact_direct", {})
    if path_b.get("live_success"):
        return "PATH B exact reproduction succeeded. Next compare repo AdobeAPIClient against this exact request shape."
    return "PATH B exact reproduction did not return live_success. Do not modify AdobeAPIClient or endpoint catalog; verify organizer-latest local values and Adobe access externally."


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _assert_safe(payload: Any, secrets: list[str]) -> None:
    text = payload if isinstance(payload, str) else json.dumps(payload, sort_keys=True, default=str)
    for secret in secrets:
        if secret and len(secret) >= 3 and secret in text:
            raise RuntimeError("Refusing to write report with unredacted organizer-latest value.")
    if re.search(r"\b[A-Za-z0-9_-]{3,}\*\*\*", text):
        raise RuntimeError("Refusing to write report with masked credential prefix.")
    if re.search(r"\bBearer\s+(?!\[REDACTED\])[A-Za-z0-9._-]{8,}", text, flags=re.IGNORECASE):
        raise RuntimeError("Refusing to write report with unredacted bearer value.")


if __name__ == "__main__":
    raise SystemExit(main())
