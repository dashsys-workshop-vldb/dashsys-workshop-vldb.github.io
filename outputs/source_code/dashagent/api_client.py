from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

import requests

from .api_response_parser import normalize_api_response
from .config import Config, DEFAULT_CONFIG
from .endpoint_catalog import normalize_api_path
from .trajectory import compact_preview, redact_secrets


def _env_first(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


@dataclass
class AdobeCredentials:
    client_id: str | None
    client_secret: str | None
    api_key: str | None
    ims_org: str | None
    sandbox: str | None
    access_token: str | None
    base_url: str

    @classmethod
    def from_env(cls) -> "AdobeCredentials":
        return cls(
            client_id=_env_first("ADOBE_CLIENT_ID", "CLIENT_ID", "ADOBE_API_KEY"),
            client_secret=_env_first("ADOBE_CLIENT_SECRET", "CLIENT_SECRET"),
            api_key=_env_first("ADOBE_API_KEY", "CLIENT_ID", "ADOBE_CLIENT_ID"),
            ims_org=_env_first("ADOBE_ORG_ID", "IMS_ORG"),
            sandbox=_env_first("ADOBE_SANDBOX_NAME", "SANDBOX"),
            access_token=_env_first("ADOBE_ACCESS_TOKEN", "ACCESS_TOKEN"),
            base_url=os.getenv("ADOBE_BASE_URL", "https://platform.adobe.io"),
        )


class AdobeAPIClient:
    def __init__(self, config: Config | None = None, credentials: AdobeCredentials | None = None) -> None:
        self.config = config or DEFAULT_CONFIG
        self.credentials = credentials or AdobeCredentials.from_env()
        self.session = requests.Session()

    @property
    def dry_run(self) -> bool:
        return not (
            self.credentials.access_token
            or (self.credentials.client_id and self.credentials.client_secret)
        )

    def get_access_token(self) -> str | None:
        if self.credentials.access_token:
            return self.credentials.access_token
        if not (self.credentials.client_id and self.credentials.client_secret):
            return None

        token_url = os.getenv("ADOBE_TOKEN_URL", "https://ims-na1.adobelogin.com/ims/token/v3")
        scopes = os.getenv("ADOBE_SCOPES", "openid,AdobeID,read_organizations,additional_info.projectedProductContext")
        response = self.session.post(
            token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": self.credentials.client_id,
                "client_secret": self.credentials.client_secret,
                "scope": scopes,
            },
            timeout=self.config.api_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        token = payload.get("access_token")
        if token:
            self.credentials.access_token = token
        return token

    def default_headers(self) -> dict[str, str]:
        token = self.get_access_token()
        headers = {
            "Content-Type": "application/json",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        api_key = self.credentials.api_key or self.credentials.client_id
        if api_key:
            headers["x-api-key"] = api_key
        if self.credentials.ims_org:
            headers["x-gw-ims-org-id"] = self.credentials.ims_org
        if self.credentials.sandbox:
            headers["x-sandbox-name"] = self.credentials.sandbox
        return headers

    def build_url(self, url_or_path: str) -> str:
        if url_or_path.startswith("http://") or url_or_path.startswith("https://"):
            return url_or_path
        return urljoin(self.credentials.base_url.rstrip("/") + "/", normalize_api_path(url_or_path).lstrip("/"))

    def call_api(
        self,
        method: str,
        url: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        method = method.upper()
        params = params or {}
        merged_headers = {**self.default_headers(), **(headers or {})} if not self.dry_run else headers or {}
        full_url = self.build_url(url)

        if self.dry_run:
            return {
                "ok": False,
                "dry_run": True,
                "method": method,
                "url": full_url,
                "endpoint": normalize_api_path(url),
                "params": params,
                "headers": redact_secrets(merged_headers),
                "status_code": None,
                "result_preview": None,
                "error": "Adobe credentials unavailable; API call not executed.",
            }

        try:
            request_kwargs: dict[str, Any] = {
                "method": method,
                "url": full_url,
                "headers": merged_headers,
                "timeout": self.config.api_timeout_seconds,
            }
            if method in {"POST", "PUT", "PATCH"}:
                request_kwargs["json"] = params
            else:
                request_kwargs["params"] = params
            response = self.session.request(**request_kwargs)
            content_type = response.headers.get("content-type", "")
            if "application/json" in content_type:
                body: Any = response.json()
            else:
                body = response.text
            return {
                "ok": response.ok,
                "dry_run": False,
                "method": method,
                "url": full_url,
                "endpoint": normalize_api_path(url),
                "params": params,
                "headers": redact_secrets(merged_headers),
                "status_code": response.status_code,
                "result_preview": compact_preview(body, self.config.max_preview_chars),
                "parsed_evidence": normalize_api_response(
                    body,
                    ok=response.ok,
                    dry_run=False,
                    status_code=response.status_code,
                    endpoint=normalize_api_path(url),
                    max_preview_chars=self.config.max_preview_chars,
                    error=None if response.ok else str(body)[:500],
                ),
                "error": None if response.ok else str(body)[:500],
            }
        except Exception as exc:
            return {
                "ok": False,
                "dry_run": False,
                "method": method,
                "url": full_url,
                "endpoint": normalize_api_path(url),
                "params": params,
                "headers": redact_secrets(merged_headers),
                "status_code": None,
                "result_preview": None,
                "parsed_evidence": normalize_api_response(
                    None,
                    ok=False,
                    dry_run=False,
                    status_code=None,
                    endpoint=normalize_api_path(url),
                    max_preview_chars=self.config.max_preview_chars,
                    error=str(exc)[:500],
                ),
                "error": str(exc)[:500],
            }
