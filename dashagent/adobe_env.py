from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any


DEFAULT_ADOBE_BASE_URL = "https://platform.adobe.io"
DEFAULT_ADOBE_SCOPES = "openid,AdobeID,read_organizations,additional_info.projectedProductContext"


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


def _detected(env: Mapping[str, str], *, primary: tuple[str, ...], alias: tuple[str, ...]) -> str:
    if any(_has(env, name) for name in primary):
        return "primary"
    if any(_has(env, name) for name in alias):
        return "alias"
    return "missing"


def _has(env: Mapping[str, str], name: str) -> bool:
    return bool(env.get(name))

