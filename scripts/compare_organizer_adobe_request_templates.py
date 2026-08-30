#!/usr/bin/env python
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.adobe_env import DEFAULT_ADOBE_BASE_URL, DEFAULT_ADOBE_SCOPES
from dashagent.api_client import AdobeCredentials
from dashagent.config import Config
from dashagent.trajectory import redact_secrets
from scripts.load_local_env import load_local_env
from scripts.test_organizer_adobe_ups_audiences import (
    DEFAULT_IMS_TOKEN_URL,
    ORGANIZER_DEFAULT_SCOPES,
    REQUIRED_HEADER_NAMES,
    UPS_AUDIENCES_PATH,
    env_source_labels,
    resolve_organizer_adobe_credentials,
)


REPORT_STEM = "organizer_adobe_template_diff"


def main() -> int:
    config = Config.from_env(ROOT)
    payload = build_template_diff_report(config)
    write_template_diff_report(config, payload)
    print(
        json.dumps(
            {
                "json": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.json"),
                "markdown": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.md"),
                "mismatch_fields": payload.get("mismatch_fields", []),
                "likely_root_cause": payload.get("likely_root_cause"),
                "code_change_required": payload.get("code_change_required"),
                "env_local_manual_update_required": payload.get("env_local_manual_update_required"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def build_template_diff_report(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    load_meta = load_local_env(config.project_root)
    direct = resolve_organizer_adobe_credentials(os.environ)
    repo = AdobeCredentials.from_env()
    repo_scopes = os.getenv("ADOBE_SCOPES", DEFAULT_ADOBE_SCOPES)
    latest = _latest_template_shape(direct)
    previous = _previous_template_shape()
    repo_shape = _repo_client_shape(repo, repo_scopes)
    old_report = _load_json(config.outputs_dir / "reports" / "baselines" / "organizer_adobe_ups_audiences_old_template_500.json")
    latest_report = _load_json(config.outputs_dir / "reports" / "organizer_latest_working_template_smoke.json")
    latest_comparison = _load_json(config.outputs_dir / "reports" / "organizer_latest_template_repo_client_equivalence.json")

    old_vs_latest = _compare_shapes(previous, latest)
    latest_vs_repo = _compare_shapes(latest, repo_shape)
    resolved_config = {
        "direct_client_id_same_as_repo_client_id": _same(direct.client_id, repo.client_id),
        "direct_client_id_same_as_repo_api_key": _same(direct.client_id, repo.api_key),
        "direct_org_same_as_repo_org": _same(direct.ims_org, repo.ims_org),
        "direct_sandbox_same_as_repo_sandbox": _same(direct.sandbox, repo.sandbox),
        "direct_base_url_same_as_repo_base_url": _same(direct.base_url, repo.base_url),
        "direct_scopes_same_as_repo_scopes": _same(direct.scopes, repo_scopes),
    }
    mismatch_fields = [
        *[f"previous_vs_latest.{name}" for name, value in old_vs_latest.items() if value is False],
        *[f"latest_vs_repo.{name}" for name, value in latest_vs_repo.items() if value is False],
        *[f"resolved_config.{name}" for name, value in resolved_config.items() if value is False],
    ]
    direct_outcome = latest_report.get("audiences_outcome")
    repo_outcome = (latest_report.get("repo_client_result") or {}).get("outcome")
    direct_status = latest_report.get("audiences_status_code")
    repo_status = (latest_report.get("repo_client_result") or {}).get("status_code")
    comparison_result = (latest_report.get("comparison") or {}).get("conclusion") or (
        latest_comparison.get("equivalence_verification") or {}
    ).get("comparison_result")
    direct_success = direct_outcome in {"live_success", "live_empty"}
    repo_success = repo_outcome in {"live_success", "live_empty"}

    code_change_required = bool(direct_success and not repo_success)
    env_update_required = bool(
        not resolved_config["direct_org_same_as_repo_org"]
        or not resolved_config["direct_sandbox_same_as_repo_sandbox"]
        or not resolved_config["direct_client_id_same_as_repo_api_key"]
        or not resolved_config["direct_scopes_same_as_repo_scopes"]
    )
    likely_root_cause = _likely_root_cause(
        direct_success=direct_success,
        repo_success=repo_success,
        comparison_result=comparison_result,
        resolved_config=resolved_config,
        latest_report_exists=bool(latest_report),
    )
    payload = {
        "report_type": REPORT_STEM,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "diagnostic_only": True,
        "official_score_claim": False,
        "promotion_allowed": False,
        "env_file_loaded": bool(load_meta.get("loaded")),
        "previous_template": previous,
        "latest_organizer_template": latest,
        "current_repo_client_template": repo_shape,
        "old_vs_latest_safe_structure": old_vs_latest,
        "latest_vs_repo_safe_structure": latest_vs_repo,
        "resolved_config_equivalence": resolved_config,
        "env_source_labels": env_source_labels(os.environ),
        "previous_baseline_result": {
            "token_status_code": old_report.get("token_status_code"),
            "token_acquisition_ok": old_report.get("token_acquisition_ok"),
            "status_code": old_report.get("audiences_status_code"),
            "outcome": old_report.get("audiences_outcome"),
            "comparison_result": (old_report.get("comparison") or {}).get("conclusion"),
        },
        "latest_local_result": {
            "token_status_code": latest_report.get("token_status_code"),
            "token_acquisition_ok": latest_report.get("token_acquisition_ok"),
            "direct_status_code": direct_status,
            "direct_outcome": direct_outcome,
            "repo_status_code": repo_status,
            "repo_outcome": repo_outcome,
            "comparison_result": comparison_result,
        },
        "mismatch_fields": mismatch_fields,
        "likely_root_cause": likely_root_cause,
        "code_change_required": code_change_required,
        "env_local_manual_update_required": env_update_required,
        "exact_next_action": _next_action(
            latest_report_exists=bool(latest_report),
            direct_success=direct_success,
            repo_success=repo_success,
            code_change_required=code_change_required,
            env_update_required=env_update_required,
        ),
    }
    _assert_safe(payload)
    return payload


def write_template_diff_report(config: Config, payload: dict[str, Any]) -> None:
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    payload = redact_secrets(payload)
    _assert_safe(payload)
    (reports_dir / f"{REPORT_STEM}.json").write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    markdown = _render_md(payload)
    _assert_safe(markdown)
    (reports_dir / f"{REPORT_STEM}.md").write_text(markdown, encoding="utf-8")


def _latest_template_shape(direct: Any) -> dict[str, Any]:
    return {
        "token_url_host": _host(direct.token_url),
        "token_path": _path(direct.token_url),
        "token_request_content_type": "application/x-www-form-urlencoded",
        "grant_type": "client_credentials",
        "scopes": _scope_labels(direct.scopes),
        "base_url_host": _host(direct.base_url),
        "data_endpoint_method": "GET",
        "data_endpoint_path": UPS_AUDIENCES_PATH,
        "data_endpoint_params": {"limit": 5},
        "required_header_names": sorted(REQUIRED_HEADER_NAMES),
        "org_context_source": "env_local_alias_or_fallback",
        "sandbox_source": "env_local_alias_or_fallback",
    }


def _previous_template_shape() -> dict[str, Any]:
    return {
        "token_url_host": _host(DEFAULT_IMS_TOKEN_URL),
        "token_path": _path(DEFAULT_IMS_TOKEN_URL),
        "token_request_content_type": "requests_default_form_encoding",
        "grant_type": "client_credentials",
        "scopes": _scope_labels(ORGANIZER_DEFAULT_SCOPES),
        "base_url_host": _host(DEFAULT_ADOBE_BASE_URL),
        "data_endpoint_method": "GET",
        "data_endpoint_path": UPS_AUDIENCES_PATH,
        "data_endpoint_params": {"limit": 5},
        "required_header_names": sorted(REQUIRED_HEADER_NAMES),
        "org_context_source": "env_local_alias_or_fallback",
        "sandbox_source": "env_local_alias_or_fallback",
    }


def _repo_client_shape(repo: AdobeCredentials, scopes: str) -> dict[str, Any]:
    return {
        "token_url_host": _host(os.getenv("ADOBE_TOKEN_URL", DEFAULT_IMS_TOKEN_URL)),
        "token_path": _path(os.getenv("ADOBE_TOKEN_URL", DEFAULT_IMS_TOKEN_URL)),
        "token_request_content_type": "requests_default_form_encoding",
        "grant_type": "client_credentials",
        "scopes": _scope_labels(scopes),
        "base_url_host": _host(repo.base_url),
        "data_endpoint_method": "GET",
        "data_endpoint_path": UPS_AUDIENCES_PATH,
        "data_endpoint_params": {"limit": 5},
        "required_header_names": sorted(REQUIRED_HEADER_NAMES),
        "org_context_source": "repo_env_resolution",
        "sandbox_source": "repo_env_resolution",
    }


def _compare_shapes(left: dict[str, Any], right: dict[str, Any]) -> dict[str, bool]:
    keys = [
        "token_url_host",
        "token_path",
        "token_request_content_type",
        "grant_type",
        "scopes",
        "base_url_host",
        "data_endpoint_method",
        "data_endpoint_path",
        "data_endpoint_params",
        "required_header_names",
    ]
    return {key: left.get(key) == right.get(key) for key in keys}


def _likely_root_cause(
    *,
    direct_success: bool,
    repo_success: bool,
    comparison_result: str | None,
    resolved_config: dict[str, bool],
    latest_report_exists: bool,
) -> str:
    if not latest_report_exists:
        return "latest_template_not_yet_run"
    if direct_success and repo_success:
        return "no_repo_specific_mismatch_detected"
    if direct_success and not repo_success:
        if not resolved_config.get("direct_scopes_same_as_repo_scopes", True):
            return "repo_scope_mismatch"
        if not resolved_config.get("direct_client_id_same_as_repo_api_key", True):
            return "repo_api_key_mapping_mismatch"
        if not resolved_config.get("direct_org_same_as_repo_org", True) or not resolved_config.get("direct_sandbox_same_as_repo_sandbox", True):
            return "repo_org_or_sandbox_mapping_mismatch"
        return "repo_client_request_mismatch"
    if comparison_result == "both_same_failure":
        return "latest_template_local_failure_not_repo_specific"
    return "unresolved"


def _next_action(
    *,
    latest_report_exists: bool,
    direct_success: bool,
    repo_success: bool,
    code_change_required: bool,
    env_update_required: bool,
) -> str:
    if not latest_report_exists:
        return "Run python3 scripts/test_organizer_latest_working_adobe_template.py --allow-failure."
    if direct_success and repo_success:
        return "Rerun focused live smoke for ups_audiences and update live API go/no-go."
    if direct_success and code_change_required:
        return "Align AdobeAPIClient with the proven latest template request shape, then rerun direct and repo equivalence."
    if env_update_required:
        return "Align local Adobe env aliases and primary variables with the organizer template values without changing source code."
    return "Ask organizer/senior to confirm non-secret request shape and local Adobe project/sandbox access."


def _scope_labels(scopes: str | None) -> list[str]:
    return sorted(part.strip() for part in str(scopes or "").split(",") if part.strip())


def _host(url: str) -> str:
    from urllib.parse import urlparse

    return urlparse(url).hostname or ""


def _path(url: str) -> str:
    from urllib.parse import urlparse

    return urlparse(url).path or ""


def _same(left: Any, right: Any) -> bool:
    return bool(left) and bool(right) and left == right


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _render_md(payload: dict[str, Any]) -> str:
    lines = [
        "# Organizer Adobe Request Template Diff",
        "",
        f"Generated at: `{payload.get('generated_at')}`",
        "",
        "This report compares only safe request structure and same/different booleans. Credential values, organization values, sandbox values, access tokens, and header values are intentionally omitted.",
        "",
        "## Latest Local Result",
        "",
    ]
    for key, value in (payload.get("latest_local_result") or {}).items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Mismatch Fields", ""])
    mismatches = payload.get("mismatch_fields") or []
    if mismatches:
        lines.extend(f"- `{field}`" for field in mismatches)
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Decision",
            "",
            f"- likely_root_cause: `{payload.get('likely_root_cause')}`",
            f"- code_change_required: `{payload.get('code_change_required')}`",
            f"- env_local_manual_update_required: `{payload.get('env_local_manual_update_required')}`",
            f"- exact_next_action: {payload.get('exact_next_action')}",
            "",
        ]
    )
    return "\n".join(lines)


def _assert_safe(payload: Any) -> None:
    text = payload if isinstance(payload, str) else json.dumps(payload, sort_keys=True, default=str)
    for name in [
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
    ]:
        value = os.environ.get(name)
        if value and len(value) >= 3 and value in text:
            raise RuntimeError(f"Refusing to write template diff with unredacted value from {name}.")
    import re

    if re.search(r"\b[A-Za-z0-9_-]{3,}\*\*\*", text):
        raise RuntimeError("Refusing to write template diff with masked credential prefix.")
    if re.search(r"\bBearer\s+(?!\[REDACTED\])[A-Za-z0-9._-]{8,}", text, flags=re.IGNORECASE):
        raise RuntimeError("Refusing to write template diff with unredacted bearer value.")


if __name__ == "__main__":
    raise SystemExit(main())
