from __future__ import annotations

import json

from dashagent.api_client import AdobeAPIClient, AdobeCredentials
from scripts.compare_organizer_adobe_request_templates import build_template_diff_report, write_template_diff_report
from scripts.test_organizer_adobe_ups_audiences import (
    classify_organizer_response,
    resolve_organizer_adobe_credentials,
    run_organizer_adobe_ups_audiences_smoke,
)
from scripts.test_organizer_latest_working_adobe_template import (
    EQUIVALENCE_REPORT_STEM,
    REPORT_STEM,
    EXACT,
    INCOMPLETE,
    resolve_latest_template_for_path_b,
    run_organizer_latest_working_adobe_template,
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
    captured_posts = []

    def fake_post(*args, **kwargs):
        captured_posts.append((args, kwargs))
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
    assert report["env_present_missing"]["client_id"] == "present"
    assert report["env_source_labels"]["client_id_source"] == "alias"
    assert captured_posts[0][1]["headers"] == {"Content-Type": "application/x-www-form-urlencoded"}
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


def test_latest_working_template_writes_separate_reports(monkeypatch, tiny_project):
    _set_alias_env(monkeypatch)

    def fake_post(*_args, **_kwargs):
        return FakeResponse(200, {"access_token": "token-secret-value-123456", "expires_in": 3600})

    def fake_get(*_args, **_kwargs):
        return FakeResponse(200, {"items": [{"id": "aud-1"}]})

    report = run_organizer_adobe_ups_audiences_smoke(
        tiny_project,
        allow_failure=True,
        post_func=fake_post,
        get_func=fake_get,
        repo_client_factory=lambda cfg: FakeRepoClient(cfg),
        report_stem=REPORT_STEM,
        evidence_report_stem=EQUIVALENCE_REPORT_STEM,
        test_template="organizer_latest_working_template",
    )

    assert report["test_template"] == "organizer_latest_working_template"
    assert (tiny_project.outputs_dir / "reports" / f"{REPORT_STEM}.json").exists()
    assert (tiny_project.outputs_dir / "reports" / f"{EQUIVALENCE_REPORT_STEM}.json").exists()
    evidence = json.loads((tiny_project.outputs_dir / "reports" / f"{EQUIVALENCE_REPORT_STEM}.json").read_text(encoding="utf-8"))
    assert evidence["test_identity"]["test_name"] == "organizer_latest_working_template"


def test_latest_template_resolver_requires_isolated_env_file(tiny_project):
    resolved = resolve_latest_template_for_path_b(tiny_project.project_root)

    assert resolved.exact_reproduction_status == INCOMPLETE
    assert resolved.credentials is None
    assert "ims_org" in resolved.missing_fields


def test_latest_template_resolver_uses_only_organizer_latest_file(monkeypatch, tiny_project):
    _set_alias_env(monkeypatch)
    (tiny_project.project_root / ".env.local").write_text(
        "\n".join(
            [
                "CLIENT_ID=old-client-fixture",
                "CLIENT_SECRET=old-secret-fixture",
                "IMS_ORG=old-org-fixture",
                "SANDBOX=old-sandbox-fixture",
            ]
        ),
        encoding="utf-8",
    )
    (tiny_project.project_root / ".env.organizer_latest.local").write_text(
        "\n".join(
            [
                "CLIENT_ID=new-client-fixture",
                "CLIENT_SECRET=new-secret-fixture",
                "IMS_ORG=new-org-fixture",
                "SANDBOX=new-sandbox-fixture",
                "ADOBE_SCOPES=openid,AdobeID,read_organizations,additional_info.projectedProductContext,session",
                "ADOBE_BASE_URL=https://platform.adobe.io",
                "ADOBE_IMS_TOKEN_URL=https://ims-na1.adobelogin.com/ims/token/v3",
            ]
        ),
        encoding="utf-8",
    )

    resolved = resolve_latest_template_for_path_b(tiny_project.project_root)

    assert resolved.exact_reproduction_status == EXACT
    assert resolved.credentials is not None
    assert resolved.credentials.ims_org == "new-org-fixture"
    assert resolved.credentials.sandbox == "new-sandbox-fixture"
    assert resolved.field_sources["ims_org"] == "organizer_latest_file:IMS_ORG"
    assert resolved.field_sources["sandbox"] == "organizer_latest_file:SANDBOX"
    assert resolved.field_sources["scopes"] == "organizer_latest_file:ADOBE_SCOPES"
    assert resolved.fallback_flags["old_env_fallback_used_for_ims_org"] is False
    assert resolved.fallback_flags["old_env_fallback_used_for_sandbox"] is False
    assert resolved.fallback_flags["old_env_fallback_used_for_scopes"] is False
    assert resolved.fallback_flags["repo_default_fallback_used"] is False
    assert resolved.safe_booleans["org_same_old_vs_latest"] is False
    assert resolved.safe_booleans["sandbox_same_old_vs_latest"] is False


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
    evidence_json_path = tiny_project.outputs_dir / "reports" / "organizer_adobe_ups_audiences_evidence_package.json"
    evidence_md_path = tiny_project.outputs_dir / "reports" / "organizer_adobe_ups_audiences_evidence_package.md"
    rendered = (
        json_path.read_text(encoding="utf-8")
        + md_path.read_text(encoding="utf-8")
        + evidence_json_path.read_text(encoding="utf-8")
        + evidence_md_path.read_text(encoding="utf-8")
    )
    assert json_path.exists()
    assert md_path.exists()
    assert evidence_json_path.exists()
    assert evidence_md_path.exists()
    assert report["credential_valid_for_token"] is True
    assert report["ups_audiences_access_valid"] is False
    assert report["likely_issue"] == "permission_or_scope_issue"
    evidence = json.loads(evidence_json_path.read_text(encoding="utf-8"))
    assert {
        "test_identity",
        "credential_loading_status",
        "token_acquisition_evidence",
        "direct_organizer_requests_path",
        "repo_adobe_api_client_path",
        "equivalence_verification",
        "evidence_based_conclusion",
    } <= set(evidence)
    assert evidence["equivalence_verification"]["comparison_result"] == "both_same_failure"
    assert evidence["evidence_based_conclusion"]["conclusion"] == "both_paths_failed_equivalently_no_repo_specific_mismatch_shown"
    assert len(evidence["direct_organizer_requests_path"]["redacted_response_excerpt"]) <= 1000
    for secret in [
        "token-secret-value-123456",
        "client-id-secret-value-123456",
        "client-secret-value-123456",
        "org-secret-value-123456",
        "sandbox-secret-value-123456",
    ]:
        assert secret not in rendered
    assert "abc***" not in rendered


def test_evidence_package_marks_direct_success_repo_failure_as_mismatch(monkeypatch, tiny_project):
    _set_alias_env(monkeypatch)

    def fake_post(*_args, **_kwargs):
        return FakeResponse(200, {"access_token": "token-secret-value-123456", "expires_in": 3600})

    def fake_get(*_args, **_kwargs):
        return FakeResponse(200, {"items": [{"id": "aud-1"}]})

    run_organizer_adobe_ups_audiences_smoke(
        tiny_project,
        allow_failure=True,
        post_func=fake_post,
        get_func=fake_get,
        repo_client_factory=lambda cfg: FakeRepoClient(
            cfg,
            result={
                "ok": False,
                "status_code": 403,
                "endpoint": "/data/core/ups/audiences",
                "method": "GET",
                "url": "https://platform.adobe.io/data/core/ups/audiences",
                "params": {"limit": 5},
                "headers": {
                    "Authorization": True,
                    "Content-Type": True,
                    "x-api-key": True,
                    "x-gw-ims-org-id": True,
                    "x-sandbox-name": True,
                },
                "parsed_evidence": {"evidence_state": "api_error", "errors": ["missing scope"]},
            },
        ),
    )
    evidence = json.loads(
        (tiny_project.outputs_dir / "reports" / "organizer_adobe_ups_audiences_evidence_package.json").read_text(encoding="utf-8")
    )

    assert evidence["equivalence_verification"]["comparison_result"] == "direct_success_repo_failure"
    assert evidence["evidence_based_conclusion"]["conclusion"] == "repo_client_mismatch_detected"


def test_evidence_package_records_get_only_ups_audiences_request(monkeypatch, tiny_project):
    _set_alias_env(monkeypatch)
    captured_gets = []
    captured_repo_calls = []

    def fake_post(*_args, **_kwargs):
        return FakeResponse(200, {"access_token": "token-secret-value-123456", "expires_in": 3600})

    def fake_get(url, **kwargs):
        captured_gets.append((url, kwargs))
        return FakeResponse(500, {"error": "server unavailable"})

    class RecordingRepoClient(FakeRepoClient):
        def call_api(self, method, url, params, headers):
            captured_repo_calls.append((method, url, params, headers))
            return {
                "ok": False,
                "status_code": 500,
                "endpoint": "/data/core/ups/audiences",
                "method": "GET",
                "url": "https://platform.adobe.io/data/core/ups/audiences",
                "params": {"limit": 5},
                "headers": {
                    "Authorization": True,
                    "Content-Type": True,
                    "x-api-key": True,
                    "x-gw-ims-org-id": True,
                    "x-sandbox-name": True,
                },
                "parsed_evidence": {"evidence_state": "api_error", "errors": ["server unavailable"]},
            }

    run_organizer_adobe_ups_audiences_smoke(
        tiny_project,
        allow_failure=True,
        post_func=fake_post,
        get_func=fake_get,
        repo_client_factory=lambda cfg: RecordingRepoClient(cfg),
    )
    evidence = json.loads(
        (tiny_project.outputs_dir / "reports" / "organizer_adobe_ups_audiences_evidence_package.json").read_text(encoding="utf-8")
    )

    assert len(captured_gets) == 1
    assert captured_gets[0][0].endswith("/data/core/ups/audiences")
    assert captured_gets[0][1]["params"] == {"limit": 5}
    assert captured_repo_calls == [("GET", "/data/core/ups/audiences", {"limit": 5}, {})]
    assert evidence["test_identity"]["data_endpoint_mutating"] is False
    assert evidence["direct_organizer_requests_path"]["method"] == "GET"
    assert evidence["repo_adobe_api_client_path"]["method"] == "GET"
    assert evidence["direct_organizer_requests_path"]["path"] == "/data/core/ups/audiences"
    assert evidence["repo_adobe_api_client_path"]["path"] == "/data/core/ups/audiences"
    assert evidence["equivalence_verification"]["same_method"] is True
    assert evidence["equivalence_verification"]["same_path"] is True
    assert evidence["equivalence_verification"]["same_params"] is True


def test_template_diff_records_structural_mismatch_without_values(monkeypatch, tiny_project):
    _set_alias_env(monkeypatch)
    monkeypatch.setenv("ADOBE_API_KEY", "different-api-key-secret-123456")
    monkeypatch.setenv("ADOBE_ORG_ID", "different-org-secret-123456")
    monkeypatch.setenv("ADOBE_SANDBOX_NAME", "different-sandbox-secret-123456")

    reports = tiny_project.outputs_dir / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "organizer_latest_working_template_smoke.json").write_text(
        json.dumps(
            {
                "token_status_code": 200,
                "token_acquisition_ok": True,
                "audiences_status_code": 200,
                "audiences_outcome": "live_success",
                "repo_client_result": {"status_code": 500, "outcome": "external_api_unavailable"},
                "comparison": {"conclusion": "direct_success_repo_failure"},
            }
        ),
        encoding="utf-8",
    )
    (reports / "baselines").mkdir(exist_ok=True)
    (reports / "baselines" / "organizer_adobe_ups_audiences_old_template_500.json").write_text(
        json.dumps(
            {
                "token_status_code": 200,
                "token_acquisition_ok": True,
                "audiences_status_code": 500,
                "audiences_outcome": "external_api_unavailable",
                "comparison": {"conclusion": "both_same_failure"},
            }
        ),
        encoding="utf-8",
    )

    payload = build_template_diff_report(tiny_project)
    write_template_diff_report(tiny_project, payload)
    rendered = (reports / "organizer_adobe_template_diff.json").read_text(encoding="utf-8")

    assert payload["code_change_required"] is True
    assert payload["env_local_manual_update_required"] is True
    assert "resolved_config.direct_client_id_same_as_repo_api_key" in payload["mismatch_fields"]
    for secret in [
        "client-id-secret-value-123456",
        "different-api-key-secret-123456",
        "different-org-secret-123456",
        "different-sandbox-secret-123456",
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
