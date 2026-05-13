from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any


DEFAULT_ADOBE_BASE_URL = "https://platform.adobe.io"
DEFAULT_ADOBE_SCOPES = "openid,AdobeID,read_organizations,additional_info.projectedProductContext"
SOURCE_LABELS = {"primary", "alias", "default", "missing"}
AUTH_MODES = {"access_token", "client_credentials", "missing"}


def adobe_env_readiness(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Return Adobe credential readiness without exposing credential values."""

    env = env or os.environ
    access_token = _detected(env, primary=("ADOBE_ACCESS_TOKEN",), alias=("ACCESS_TOKEN",))
    api_key = _detected(env, primary=("ADOBE_API_KEY",), alias=("CLIENT_ID", "ADOBE_CLIENT_ID"))
    client_id = _detected(env, primary=("ADOBE_CLIENT_ID", "ADOBE_API_KEY"), alias=("CLIENT_ID",))
    client_secret = _detected(env, primary=("ADOBE_CLIENT_SECRET",), alias=("CLIENT_SECRET",))
    org_id = _detected(env, primary=("ADOBE_ORG_ID",), alias=("IMS_ORG",))
    sandbox = _detected(env, primary=("ADOBE_SANDBOX_NAME",), alias=("SANDBOX",))
    base_url = "primary" if _has(env, "ADOBE_BASE_URL") else "default"
    scopes = "primary" if _has(env, "ADOBE_SCOPES") else "default"

    if access_token != "missing":
        auth_mode = "access_token"
    elif client_id != "missing" and client_secret != "missing":
        auth_mode = "client_credentials"
    else:
        auth_mode = "missing"

    authorization_constructible = auth_mode != "missing"
    headers_constructible = {
        "Authorization": authorization_constructible,
        "x-api-key": api_key != "missing",
        "x-gw-ims-org-id": org_id != "missing",
        "x-sandbox-name": sandbox != "missing",
        "Content-Type": True,
    }
    credential_ready = headers_constructible["Authorization"] and headers_constructible["x-api-key"]
    sandbox_ready = headers_constructible["x-gw-ims-org-id"] and headers_constructible["x-sandbox-name"]
    base_url_ready = base_url in {"primary", "default"}
    return {
        "auth_mode": auth_mode,
        "authorization_constructible": authorization_constructible,
        "env_names_detected": {
            "access_token": access_token,
            "api_key": api_key,
            "client_id": client_id,
            "client_secret": client_secret,
            "org_id": org_id,
            "sandbox_name": sandbox,
            "base_url": base_url,
            "scopes": scopes,
        },
        "headers_constructible": headers_constructible,
        "credential_ready": credential_ready,
        "sandbox_ready": sandbox_ready,
        "ready_for_live_adobe_api_smoke": credential_ready and base_url_ready,
        "ready_for_sandbox_endpoints": credential_ready and sandbox_ready and base_url_ready,
    }


def format_adobe_readiness_for_report(readiness: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Format Adobe readiness for reports without exposing or masking credential values.

    The returned shape deliberately avoids value-bearing keys such as org_id or
    sandbox_name, because generic report redaction treats those keys as metadata
    values and can create misleading masked prefixes. This formatter only emits
    source labels, header names, and booleans.
    """

    readiness = readiness or adobe_env_readiness()
    env_sources = readiness.get("env_names_detected") if isinstance(readiness.get("env_names_detected"), Mapping) else {}
    header_sources = readiness.get("headers_constructible") if isinstance(readiness.get("headers_constructible"), Mapping) else {}
    env_order = [
        ("access_token", "access_token"),
        ("api_key", "api_key"),
        ("client_id", "client_id"),
        ("client_secret", "client_secret"),
        ("organization", "org_id"),
        ("sandbox", "sandbox_name"),
        ("base_url", "base_url"),
        ("scopes", "scopes"),
    ]
    header_order = [
        "Authorization",
        "Content-Type",
        "x-api-key",
        "x-gw-ims-org-id",
        "x-sandbox-name",
    ]
    return {
        "auth_mode": _auth_mode_label(readiness.get("auth_mode")),
        "authorization_constructible": bool(readiness.get("authorization_constructible")),
        "credential_ready": bool(readiness.get("credential_ready")),
        "sandbox_ready": bool(readiness.get("sandbox_ready")),
        "ready_for_live_adobe_api_smoke": bool(readiness.get("ready_for_live_adobe_api_smoke")),
        "ready_for_sandbox_endpoints": bool(readiness.get("ready_for_sandbox_endpoints")),
        "detected_env_sources": [
            {"name": public_name, "source": _source_label(env_sources.get(internal_name))}
            for public_name, internal_name in env_order
        ],
        "header_constructibility": [
            {"header_name": header_name, "constructible": bool(header_sources.get(header_name))}
            for header_name in header_order
        ],
    }


def _detected(env: Mapping[str, str], *, primary: tuple[str, ...], alias: tuple[str, ...]) -> str:
    if any(_has(env, name) for name in primary):
        return "primary"
    if any(_has(env, name) for name in alias):
        return "alias"
    return "missing"


def _has(env: Mapping[str, str], name: str) -> bool:
    return bool(env.get(name))


def _source_label(value: Any) -> str:
    return str(value) if str(value) in SOURCE_LABELS else "missing"


def _auth_mode_label(value: Any) -> str:
    return str(value) if str(value) in AUTH_MODES else "missing"
