from __future__ import annotations

import json

from dashagent.api_client import AdobeAPIClient, AdobeCredentials
from scripts.test_organizer_adobe_ups_audiences import (
    classify_organizer_response,
    resolve_organizer_adobe_credentials,
    run_organizer_adobe_ups_audiences_smoke,
)


class FakeResponse:
    def __init__(self, status_code: int, body, *, json_ok: bool = True):
        self.status_code = status_code
        self._body = body
        self.ok = 200 <= status_code < 300
        self.text = body if isinstance(body, str) else json.dumps(body)
        self.headers = {"content-type": "application/json"}
        self._json_ok = json_ok

    def json(self):
        if not self._json_ok:
            raise ValueError("invalid json")
        return self._body


class FakeRepoClient(AdobeAPIClient):
    def __init__(self, *_args, result=None):
        self.result = result or {
            "ok": True,
            "status_code": 200,
            "parsed_evidence": {"evidence_state": "live_empty"},
        }

    def get_access_token(self):
        return "repo-token-secret"

    def call_api(self, method, url, params, headers):
        return self.result


def test_organizer_env_resolution_supports_aliases():
    env = {
        "CLIENT_ID": "client-id-value",
        "CLIENT_SECRET": "client-secret-value",
        "IMS_ORG": "org-value",
        "SANDBOX": "sandbox-value",
    }

    creds = resolve_organizer_adobe_credentials(env)

    assert creds.client_id == "client-id-value"
    assert creds.client_secret == "client-secret-value"
    assert creds.ims_org == "org-value"
    assert creds.sandbox == "sandbox-value"
    assert creds.missing_required_fields == []


def test_organizer_env_resolution_supports_primary_names():
    env = {
        "ADOBE_API_KEY": "api-key-value",
        "ADOBE_CLIENT_SECRET": "client-secret-value",
        "ADOBE_ORG_ID": "org-value",
        "ADOBE_SANDBOX_NAME": "sandbox-value",
    }

    creds = resolve_organizer_adobe_credentials(env)

    assert creds.client_id == "api-key-value"
    assert creds.client_secret == "client-secret-value"
    assert creds.ims_org == "org-value"
    assert creds.sandbox == "sandbox-value"
    assert creds.missing_required_fields == []


def test_organizer_missing_env_fails_safely_without_values(monkeypatch, tiny_project):
    _clear_adobe_env(monkeypatch)

    report = run_organizer_adobe_ups_audiences_smoke(tiny_project, allow_failure=True)
    rendered = json.dumps(report, sort_keys=True)

    assert report["token_acquisition_ok"] is False
    assert report["token_error_category"] == "missing_required_env"
    assert report["likely_issue"] == "bad_client_credentials"
    assert "client-secret" not in rendered


def test_organizer_smoke_redacts_token_and_credentials(monkeypatch, tiny_project):
    _set_alias_env(monkeypatch)

    def fake_post(*_args, **_kwargs):
        return FakeResponse(200, {"access_token": "token-secret-value-123456", "expires_in": 3600})

    def fake_get(*_args, **_kwargs):
        return FakeResponse(200, {"items": [{"id": "aud-1", "name": "Audience One"}]})

    report = run_organizer_adobe_ups_audiences_smoke(
        tiny_project,
        allow_failure=True,
        post_func=fake_post,
        get_func=fake_get,
        repo_client_factory=lambda cfg: FakeRepoClient(cfg),
    )
    rendered = json.dumps(report, sort_keys=True)

    assert report["credential_valid_for_token"] is True
    assert report["ups_audiences_access_valid"] is True
    assert report["audiences_outcome"] == "live_success"
    for secret in [
        "token-secret-value-123456",
        "client-id-secret-value-123456",
        "client-secret-value-123456",
        "org-secret-value-123456",
        "sandbox-secret-value-123456",
        "Bearer token-secret-value-123456",
    ]:
        assert secret not in rendered
    assert "Authorization" in rendered


def test_organizer_response_classification_cases():
    assert classify_organizer_response(status_code=200, ok=True, body={"items": [{"id": "a1"}]}, json_parse_succeeded=True) == "live_success"
    assert classify_organizer_response(status_code=200, ok=True, body={"items": []}, json_parse_succeeded=True) == "live_empty"
    assert classify_organizer_response(status_code=401, ok=False, body={"error": "unauthorized"}, json_parse_succeeded=True) == "auth_error"
    assert classify_organizer_response(status_code=403, ok=False, body={"error": "missing scope"}, json_parse_succeeded=True) == "scope_or_permission_issue"
    assert classify_organizer_response(status_code=400, ok=False, body={"error": "invalid sandbox"}, json_parse_succeeded=True) == "sandbox_scope_issue"
    assert classify_organizer_response(status_code=404, ok=False, body={"error": "not found"}, json_parse_succeeded=True) == "endpoint_path_issue"
    assert classify_organizer_response(status_code=503, ok=False, body={"error": "service unavailable"}, json_parse_succeeded=True) == "external_api_unavailable"
    assert classify_organizer_response(status_code=200, ok=True, body="not-json", json_parse_succeeded=False, malformed_response=True) == "malformed_response"


def test_organizer_report_files_are_generated_and_safe(monkeypatch, tiny_project):
    _set_alias_env(monkeypatch)

    def fake_post(*_args, **_kwargs):
        return FakeResponse(200, {"access_token": "token-secret-value-123456"})

    def fake_get(*_args, **_kwargs):
        return FakeResponse(403, {"error": "missing scope"})

    report = run_organizer_adobe_ups_audiences_smoke(
        tiny_project,
        allow_failure=True,
        post_func=fake_post,
        get_func=fake_get,
        repo_client_factory=lambda cfg: FakeRepoClient(
            cfg,
            result={
                "ok": False,
                "status_code": 403,
                "parsed_evidence": {"evidence_state": "api_error", "errors": ["missing scope"]},
            },
        ),
    )

    json_path = tiny_project.outputs_dir / "reports" / "organizer_adobe_ups_audiences_smoke.json"
    md_path = tiny_project.outputs_dir / "reports" / "organizer_adobe_ups_audiences_smoke.md"
    rendered = json_path.read_text(encoding="utf-8") + md_path.read_text(encoding="utf-8")
    assert json_path.exists()
    assert md_path.exists()
    assert report["credential_valid_for_token"] is True
    assert report["ups_audiences_access_valid"] is False
    assert report["likely_issue"] == "permission_or_scope_issue"
    for secret in [
        "token-secret-value-123456",
        "client-id-secret-value-123456",
        "client-secret-value-123456",
        "org-secret-value-123456",
        "sandbox-secret-value-123456",
    ]:
        assert secret not in rendered


def _set_alias_env(monkeypatch) -> None:
    _clear_adobe_env(monkeypatch)
    monkeypatch.setenv("CLIENT_ID", "client-id-secret-value-123456")
    monkeypatch.setenv("CLIENT_SECRET", "client-secret-value-123456")
    monkeypatch.setenv("IMS_ORG", "org-secret-value-123456")
    monkeypatch.setenv("SANDBOX", "sandbox-secret-value-123456")


def _clear_adobe_env(monkeypatch) -> None:
    for name in [
        "ADOBE_ACCESS_TOKEN",
        "ADOBE_API_KEY",
        "ADOBE_ORG_ID",
        "ADOBE_SANDBOX_NAME",
        "ADOBE_CLIENT_ID",
        "ADOBE_CLIENT_SECRET",
        "ADOBE_SCOPES",
        "ADOBE_BASE_URL",
        "ADOBE_IMS_TOKEN_URL",
        "ADOBE_TOKEN_URL",
        "ACCESS_TOKEN",
        "CLIENT_ID",
        "CLIENT_SECRET",
        "IMS_ORG",
        "SANDBOX",
    ]:
        monkeypatch.delenv(name, raising=False)
