from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

import requests

from .adobe_env import DEFAULT_ADOBE_BASE_URL, DEFAULT_ADOBE_SCOPES
from .api_response_parser import normalize_api_response
from .config import Config, DEFAULT_CONFIG
from .endpoint_catalog import EndpointCatalog, normalize_api_path
from .trajectory import compact_preview, redact_secrets


def _env_first(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


class TokenAcquisitionError(RuntimeError):
    def __init__(
        self,
        message: str = "token_acquisition_failed",
        *,
        status_code: int | None = None,
        error_category: str = "token_acquisition_failed",
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_category = error_category


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
            base_url=os.getenv("ADOBE_BASE_URL", DEFAULT_ADOBE_BASE_URL),
        )


class AdobeAPIClient:
    def __init__(self, config: Config | None = None, credentials: AdobeCredentials | None = None) -> None:
        self.config = config or DEFAULT_CONFIG
        self.credentials = credentials or AdobeCredentials.from_env()
        self.session = requests.Session()
        self.endpoint_catalog = EndpointCatalog(self.config)

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

        payload = self.fetch_access_token_payload()
        token = payload.get("access_token")
        if not token:
            raise TokenAcquisitionError("token_response_missing_access_token", error_category="token_acquisition_failed")
        self.credentials.access_token = str(token)
        return self.credentials.access_token

    def fetch_access_token_payload(self) -> dict[str, Any]:
        if not (self.credentials.client_id and self.credentials.client_secret):
            raise TokenAcquisitionError("client_credentials_missing", error_category="token_acquisition_failed")
        token_url = os.getenv("ADOBE_TOKEN_URL", "https://ims-na1.adobelogin.com/ims/token/v3")
        scopes = os.getenv("ADOBE_SCOPES", DEFAULT_ADOBE_SCOPES)
        try:
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
        except Exception as exc:
            raise TokenAcquisitionError(
                "token_acquisition_failed",
                error_category="token_acquisition_failed",
            ) from exc
        if not response.ok:
            raise TokenAcquisitionError(
                "token_acquisition_failed",
                status_code=response.status_code,
                error_category="token_acquisition_failed",
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise TokenAcquisitionError(
                "token_response_malformed",
                status_code=response.status_code,
                error_category="token_acquisition_failed",
            ) from exc
        if not isinstance(payload, dict):
            raise TokenAcquisitionError(
                "token_response_malformed",
                status_code=response.status_code,
                error_category="token_acquisition_failed",
            )
        return payload

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
        full_url = self.build_url(url)
        endpoint_path = normalize_api_path(url)

        if self.dry_run:
            return {
                "ok": False,
                "dry_run": True,
                "method": method,
                "url": full_url,
                "endpoint": endpoint_path,
                "params": params,
                "headers": _header_presence(headers or {}),
                "status_code": None,
                "result_preview": None,
                "error": "Adobe credentials unavailable; API call not executed.",
            }

        try:
            merged_headers = {**self.default_headers(), **(headers or {})}
        except TokenAcquisitionError as exc:
            return self._token_acquisition_failure_result(method, endpoint_path, full_url, params, headers or {}, exc)

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
            endpoint = self.endpoint_catalog.match(method, endpoint_path)
            content_type = response.headers.get("content-type", "")
            malformed_response = False
            if "application/json" in content_type:
                try:
                    body: Any = response.json()
                except ValueError:
                    body = response.text
                    malformed_response = True
            else:
                body = response.text
            return {
                "ok": response.ok,
                "dry_run": False,
                "method": method,
                "url": full_url,
                "endpoint": endpoint_path,
                "params": params,
                "headers": _header_presence(merged_headers),
                "status_code": response.status_code,
                "result_preview": compact_preview(body, self.config.max_preview_chars),
                "parsed_evidence": normalize_api_response(
                    body,
                    ok=response.ok and not malformed_response,
                    dry_run=False,
                    status_code=response.status_code,
                    endpoint=endpoint_path,
                    endpoint_id=endpoint.id if endpoint else None,
                    endpoint_family=endpoint.id if endpoint else None,
                    method=method,
                    path=endpoint_path,
                    max_preview_chars=self.config.max_preview_chars,
                    malformed_response=malformed_response,
                    error_category="malformed_response" if malformed_response else None,
                    error="Malformed JSON response." if malformed_response else (None if response.ok else str(body)[:500]),
                ),
                "error": "Malformed JSON response." if malformed_response else (None if response.ok else str(body)[:500]),
            }
        except Exception as exc:
            return {
                "ok": False,
                "dry_run": False,
                "method": method,
                "url": full_url,
                "endpoint": normalize_api_path(url),
                "params": params,
                "headers": _header_presence(merged_headers),
                "status_code": None,
                "result_preview": None,
                "parsed_evidence": normalize_api_response(
                    None,
                    ok=False,
                    dry_run=False,
                    status_code=None,
                    endpoint=normalize_api_path(url),
                    method=method,
                    path=normalize_api_path(url),
                    max_preview_chars=self.config.max_preview_chars,
                    error_category="api_error",
                    error=str(exc)[:500],
                ),
                "error": str(exc)[:500],
            }

    def _token_acquisition_failure_result(
        self,
        method: str,
        endpoint_path: str,
        full_url: str,
        params: dict[str, Any],
        headers: dict[str, Any],
        exc: TokenAcquisitionError,
    ) -> dict[str, Any]:
        return {
            "ok": False,
            "dry_run": False,
            "method": method,
            "url": full_url,
            "endpoint": endpoint_path,
            "params": params,
            "headers": _header_presence(headers),
            "status_code": exc.status_code,
            "result_preview": None,
            "error_category": "token_acquisition_failed",
            "parsed_evidence": normalize_api_response(
                None,
                ok=False,
                dry_run=False,
                status_code=exc.status_code,
                endpoint=endpoint_path,
                method=method,
                path=endpoint_path,
                max_preview_chars=self.config.max_preview_chars,
                error_category="token_acquisition_failed",
                error="token_acquisition_failed",
            ),
            "error": "token_acquisition_failed",
        }


def _header_presence(headers: dict[str, Any]) -> dict[str, bool]:
    return {str(key): bool(value) for key, value in sorted(headers.items())}
