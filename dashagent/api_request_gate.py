from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .trajectory import redact_secrets
from .validators import APIValidator


@dataclass
class APIRequestGateResult:
    passed: bool
    error_type: str | None
    error_message: str | None
    method: str | None
    path: str | None
    params: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class APIRequestGate:
    """Shape/catalog gate for LLM-generated API requests without endpoint planning or repair."""

    def __init__(self, api_validator: APIValidator) -> None:
        self.api_validator = api_validator

    def check(self, request: Any) -> APIRequestGateResult:
        if request is None:
            return APIRequestGateResult(False, "shape_error", "API request is missing.", None, None, None)
        if hasattr(request, "to_dict"):
            request = request.to_dict()
        if not isinstance(request, dict):
            return APIRequestGateResult(False, "shape_error", "API request must be an object.", None, None, None)

        raw_method = request.get("method")
        raw_path = request.get("path") or request.get("url")
        raw_params = request.get("params")
        method = str(raw_method or "").strip().upper()
        path = str(raw_path or "").strip()
        params = dict(raw_params) if isinstance(raw_params, dict) else ({} if raw_params is None else None)

        if not method:
            return APIRequestGateResult(False, "shape_error", "API request method is missing.", method or None, path or None, params)
        if method != "GET":
            return APIRequestGateResult(False, "request_error", "Only safe GET API requests may execute.", method, path or None, params)
        if not path:
            return APIRequestGateResult(False, "shape_error", "API request path is missing.", method, None, params)
        if params is None:
            return APIRequestGateResult(False, "shape_error", "API request params must be a JSON object.", method, path, None)

        validation = self.api_validator.validate(method, path, params, {})
        if not validation.ok:
            return APIRequestGateResult(
                False,
                "request_error",
                _sanitize_error_message("; ".join(validation.errors)),
                method,
                path,
                params,
            )
        return APIRequestGateResult(True, None, None, method, path, params)


def _sanitize_error_message(message: str) -> str:
    redacted = redact_secrets(message)
    text = str(redacted).splitlines()[0] if str(redacted).splitlines() else str(redacted)
    return text[:500]
