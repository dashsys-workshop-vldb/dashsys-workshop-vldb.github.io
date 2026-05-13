from __future__ import annotations

import json
from pathlib import Path

from dashagent.answer_slots import extract_answer_slots
from dashagent.answer_intent import AnswerIntent
from dashagent.answer_verifier import safe_rewrite
from dashagent.api_discovery import plan_discovery_for_endpoint, resolve_discovery_chain
from dashagent.api_client import AdobeAPIClient, AdobeCredentials, TokenAcquisitionError
from dashagent.api_outcome_classifier import classify_api_outcome
from dashagent.api_response_parser import normalize_api_response
from dashagent.config import Config
from dashagent.endpoint_catalog import Endpoint, EndpointCatalog
from dashagent.evidence_bus import EvidenceBus
from dashagent.trajectory import redact_secrets
from scripts.audit_live_adobe_api_readiness import audit_live_adobe_api_readiness, token_acquisition_preflight
from scripts.generate_live_api_strict_eval_delta import generate_live_api_strict_eval_delta, preserve_pre_live_baseline
from scripts.generate_api_required_readiness_matrix import generate_api_required_readiness_matrix
from scripts.package_query_outputs import NON_SUBMISSION_OUTPUT_DIRS
from scripts.run_live_api_evidence_pipeline_trial import run_live_api_evidence_pipeline_trial
from scripts.run_live_api_readiness_smoke import run_live_api_readiness_smoke
from scripts.run_mock_live_api_evidence_pipeline_trial import run_mock_live_api_evidence_pipeline_trial


ADOBE_ENV_NAMES = [
    "ADOBE_ACCESS_TOKEN",
    "ADOBE_API_KEY",
    "ADOBE_ORG_ID",
    "ADOBE_SANDBOX_NAME",
    "ADOBE_BASE_URL",
    "ADOBE_CLIENT_ID",
    "ADOBE_CLIENT_SECRET",
    "ADOBE_SCOPES",
    "ACCESS_TOKEN",
    "CLIENT_ID",
    "CLIENT_SECRET",
    "IMS_ORG",
    "SANDBOX",
]


def clear_adobe_env(monkeypatch) -> None:
    for name in ADOBE_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)


def test_adobe_env_aliases_and_header_redaction(monkeypatch):
    clear_adobe_env(monkeypatch)
    monkeypatch.setenv("ADOBE_ACCESS_TOKEN", "tok_live_header_test_value_123")
    monkeypatch.setenv("ADOBE_API_KEY", "api_key_header_test_value_123")
    monkeypatch.setenv("ADOBE_ORG_ID", "org_debug_value")
    monkeypatch.setenv("ADOBE_SANDBOX_NAME", "production-sandbox")

    credentials = AdobeCredentials.from_env()
    client = AdobeAPIClient(credentials=credentials)
    headers = client.default_headers()

    assert headers["Authorization"].startswith("Bearer ")
    assert headers["x-api-key"] == "api_key_header_test_value_123"
    assert headers["x-gw-ims-org-id"] == "org_debug_value"
    assert headers["x-sandbox-name"] == "production-sandbox"
    assert client.dry_run is False

    redacted = redact_secrets(headers)
    assert redacted["Authorization"] == "[REDACTED]"
    assert redacted["x-api-key"] == "[REDACTED]"
    assert redacted["x-gw-ims-org-id"] == "org***"
    assert redacted["x-sandbox-name"] == "pro***"


def test_live_and_dry_run_mode_separation(monkeypatch):
    clear_adobe_env(monkeypatch)
    assert AdobeAPIClient().dry_run is True
    monkeypatch.setenv("ADOBE_ACCESS_TOKEN", "tok_live_mode_test_value_123")
    monkeypatch.setenv("ADOBE_API_KEY", "api_key_live_mode_test_value_123")
    assert AdobeAPIClient().dry_run is False


def test_client_credentials_mode_is_live_ready(monkeypatch):
    clear_adobe_env(monkeypatch)
    monkeypatch.setenv("CLIENT_ID", "client-id-live-ready")
    monkeypatch.setenv("CLIENT_SECRET", "client-secret-live-ready")
    monkeypatch.setenv("IMS_ORG", "org-live-ready")
    monkeypatch.setenv("SANDBOX", "sandbox-live-ready")
    assert AdobeAPIClient().dry_run is False


def test_token_acquisition_failure_returns_structured_result_without_secret_leak(monkeypatch):
    clear_adobe_env(monkeypatch)
    credentials = AdobeCredentials(
        client_id="client-id-secret-value",
        client_secret="client-secret-value",
        api_key="api-key-secret-value",
        ims_org="org-secret-value",
        sandbox="sandbox-secret-value",
        access_token=None,
        base_url="https://platform.adobe.io",
    )

    class FailingTokenClient(AdobeAPIClient):
        def get_access_token(self):
            raise TokenAcquisitionError(status_code=None, error_category="token_acquisition_failed")

    result = FailingTokenClient(credentials=credentials).call_api("GET", "/ajo/journey", {"limit": 1}, {})
    rendered = json.dumps(result, sort_keys=True)
    assert result["ok"] is False
    assert result["dry_run"] is False
    assert result["error_category"] == "token_acquisition_failed"
    assert result["parsed_evidence"]["evidence_state"] == "token_acquisition_failed"
    assert classify_api_outcome(result, method="GET", path="/ajo/journey") == "token_acquisition_failed"
    for secret in ["client-id-secret-value", "client-secret-value", "api-key-secret-value", "org-secret-value", "sandbox-secret-value"]:
        assert secret not in rendered


def test_shared_api_outcome_classifier_covers_live_error_states():
    assert classify_api_outcome({"status_code": 401, "ok": False}) == "auth_error"
    assert classify_api_outcome({"status_code": 403, "ok": False, "error": "missing scope"}) == "scope_or_permission_issue"
    assert classify_api_outcome({"status_code": 403, "ok": False, "error": "sandbox not authorized"}) == "sandbox_scope_issue"
    assert classify_api_outcome({"status_code": 404, "ok": False}) == "endpoint_path_issue"
    assert classify_api_outcome({"status_code": 429, "ok": False}) == "rate_limited"
    assert classify_api_outcome({"status_code": 503, "ok": False}) == "external_api_unavailable"
    assert classify_api_outcome({"parsed_evidence": normalize_api_response("bad", ok=False, dry_run=False, malformed_response=True)}) == "malformed_response"
    assert classify_api_outcome({"status_code": 200, "ok": True, "parsed_evidence": normalize_api_response([], ok=True, dry_run=False, status_code=200)}) == "live_empty"
    assert classify_api_outcome({"status_code": 200, "ok": True, "parsed_evidence": normalize_api_response({"items": [{"id": "1"}]}, ok=True, dry_run=False, status_code=200)}) == "live_success"
    assert classify_api_outcome({}, path="/unifiedtags/tags/{tag_id}") == "unresolved_path_param"
    assert classify_api_outcome({}, discovery_status="discovery_blocked_missing_id") == "discovery_blocked_missing_id"


def test_api_response_parser_distinguishes_live_empty_dry_run_and_error():
    live_empty = normalize_api_response([], ok=True, dry_run=False, status_code=200)
    dry_run = normalize_api_response(None, ok=False, dry_run=True)
    api_error = normalize_api_response({"error": "unauthorized"}, ok=False, dry_run=False, status_code=401)

    assert live_empty["ok"] is True
    assert live_empty["dry_run"] is False
    assert live_empty["items"] == []
    assert live_empty["evidence_state"] == "live_empty"
    assert dry_run["dry_run"] is True
    assert dry_run["evidence_state"] == "dry_run_unavailable"
    assert dry_run["evidence_state"] != "malformed_response"
    assert dry_run["live_evidence_available"] is False
    assert api_error["ok"] is False
    assert api_error["dry_run"] is False
    assert api_error["evidence_state"] == "api_error"
    assert api_error["errors"]


def test_token_acquisition_preflight_uses_client_helper(monkeypatch, tiny_project: Config):
    clear_adobe_env(monkeypatch)
    monkeypatch.setenv("CLIENT_ID", "client-id-preflight")
    monkeypatch.setenv("CLIENT_SECRET", "client-secret-preflight")
    monkeypatch.setenv("IMS_ORG", "org-preflight")
    monkeypatch.setenv("SANDBOX", "sandbox-preflight")

    def fake_payload(self):
        return {"access_token": "token-preflight-secret", "expires_in": 3600}

    monkeypatch.setattr(AdobeAPIClient, "fetch_access_token_payload", fake_payload)
    preflight = token_acquisition_preflight(tiny_project)
    rendered = json.dumps(preflight)
    assert preflight["token_acquisition_attempted"] is True
    assert preflight["token_acquisition_ok"] is True
    assert preflight["expires_in_present"] is True
    assert "token-preflight-secret" not in rendered


def test_malformed_response_is_live_only():
    malformed = normalize_api_response(
        '{"bad":',
        ok=False,
        dry_run=False,
        endpoint_id="journey_list",
        endpoint_family="journey_list",
        method="GET",
        path="/ajo/journey",
        malformed_response=True,
        error="Malformed JSON response.",
    )
    dry_run = normalize_api_response(
        None,
        ok=False,
        dry_run=True,
        endpoint_id="journey_list",
        endpoint_family="journey_list",
        method="GET",
        path="/ajo/journey",
    )

    assert malformed["evidence_state"] == "malformed_response"
    assert malformed["dry_run"] is False
    assert dry_run["evidence_state"] == "dry_run_unavailable"
    assert dry_run["evidence_state"] != "malformed_response"


def test_api_response_parser_extracts_common_fields():
    payload = {
        "results": [
            {
                "_id": "item-1",
                "displayName": "Audience One",
                "state": "active",
                "updatedAt": "2026-03-31T00:00:00Z",
                "totalProfiles": 7,
            }
        ],
        "page": {"limit": 1, "total": 1},
    }
    parsed = normalize_api_response(
        payload,
        ok=True,
        dry_run=False,
        status_code=200,
        endpoint_id="ups_audiences",
        endpoint_family="ups_audiences",
        method="GET",
        path="/data/core/ups/audiences",
    )
    assert parsed["items"][0]["_id"] == "item-1"
    assert parsed["endpoint_id"] == "ups_audiences"
    assert parsed["endpoint_family"] == "ups_audiences"
    assert parsed["method"] == "GET"
    assert parsed["path"] == "/data/core/ups/audiences"
    assert "item-1" in parsed["ids"]
    assert "Audience One" in parsed["names"]
    assert "active" in parsed["statuses"]
    assert parsed["counts"]["totalProfiles"] == 7
    assert parsed["timestamps"]["updatedAt"] == "2026-03-31T00:00:00Z"
    assert parsed["pagination"]["page"]["limit"] == 1
    assert parsed["parser_mode"] in {"endpoint_family", "generic"}


def test_endpoint_family_fixture_cases_are_case_addressable():
    fixture_root = Path("tests/fixtures/adobe_api_responses/journey_list")
    for case_name in ["normal", "empty", "error", "pagination", "nested", "malformed"]:
        assert (fixture_root / f"{case_name}.json").exists()

    normal = json.loads((fixture_root / "normal.json").read_text(encoding="utf-8"))
    parsed = normalize_api_response(
        normal,
        ok=True,
        dry_run=False,
        endpoint_id="journey_list",
        endpoint_family="journey_list",
        method="GET",
        path="/ajo/journey",
    )
    assert parsed["parser_mode"] == "endpoint_family"
    assert parsed["live_evidence_available"] is True
    assert parsed["endpoint_id"] == "journey_list"


def test_structured_api_evidence_flows_to_evidencebus_and_answer_slots():
    parsed = normalize_api_response(
        {"items": [{"id": "flow-1", "name": "Flow One", "status": "enabled"}], "total": 1},
        ok=True,
        dry_run=False,
        status_code=200,
    )
    payload = {"ok": True, "dry_run": False, "parsed_evidence": parsed}
    step = type("Step", (), {"family": "flowservice_flows"})()
    bus = EvidenceBus()
    bus.observe_api(step, payload)
    slots = extract_answer_slots("list flows", [{"type": "api", "step": {"family": "flowservice_flows"}, "payload": payload}])

    assert "Flow One" in bus.names
    assert bus.ids["id"] == "flow-1"
    assert "enabled" in bus.statuses
    assert "flow-1" in bus.api_ids
    assert bus.api_evidence_states == ["live_evidence"]
    assert slots.api_item_count == 1
    assert "Flow One" in slots.entity_names
    assert slots.answer_slot_source == "live_api"
    assert slots.live_api_evidence_available is True


def test_dry_run_empty_and_api_error_stay_distinct_in_answer_slots():
    dry_run = {"ok": False, "dry_run": True, "parsed_evidence": normalize_api_response(None, ok=False, dry_run=True)}
    empty = {
        "ok": True,
        "dry_run": False,
        "parsed_evidence": normalize_api_response([], ok=True, dry_run=False, endpoint_id="journey_list", method="GET", path="/ajo/journey"),
    }
    error = {
        "ok": False,
        "dry_run": False,
        "parsed_evidence": normalize_api_response({"error": "unauthorized"}, ok=False, dry_run=False, status_code=401),
    }

    dry_slots = extract_answer_slots("list journeys", [{"type": "api", "step": {"family": "journey_list"}, "payload": dry_run}])
    empty_slots = extract_answer_slots("list journeys", [{"type": "api", "step": {"family": "journey_list"}, "payload": empty}])
    error_slots = extract_answer_slots("list journeys", [{"type": "api", "step": {"family": "journey_list"}, "payload": error}])

    assert dry_slots.dry_run is True
    assert dry_slots.answer_slot_source == "dry_run_unavailable"
    assert empty_slots.dry_run is False
    assert empty_slots.api_item_count == 0
    assert empty_slots.answer_slot_source == "live_api"
    answer = safe_rewrite("list journeys", empty_slots, AnswerIntent.LIST, "journey_list")
    assert answer == "Live API returned no matching journeys."
    assert "credentials are unavailable" not in answer.lower()
    assert error_slots.api_error is True
    assert error_slots.answer_slot_source == "api_error"


def test_discovery_chain_records_provenance_and_blocks_unsafe_paths():
    catalog = EndpointCatalog()
    detail = catalog.by_id("unified_tag_detail")
    assert detail is not None
    planned = plan_discovery_for_endpoint(detail, catalog)
    assert planned.discovery_status == "needs_discovery_chain"

    parsed = normalize_api_response(
        {"tags": [{"tag_id": "tag-001", "name": "VIP"}]},
        ok=True,
        dry_run=False,
        endpoint_id="unified_tags",
        endpoint_family="unified_tags",
        method="GET",
        path="/unifiedtags/tags",
    )
    resolved = resolve_discovery_chain(
        detail,
        parsed_evidence=parsed,
        source_query_id_or_fixture="tests/fixtures/adobe_api_responses/unified_tags/normal.json",
        catalog=catalog,
    )
    assert resolved.discovery_status == "ready_with_discovered_id"
    assert resolved.filled_path == "/unifiedtags/tags/tag-001"
    assert resolved.id_source == "live_api"
    assert resolved.source_endpoint == "unified_tags"
    assert resolved.source_field in {"tag_id", "ids[0]", "id"}
    assert resolved.source_query_id_or_fixture

    missing = resolve_discovery_chain(detail, catalog=catalog)
    assert missing.discovery_status == "discovery_blocked_missing_id"

    unsafe = Endpoint(id="unsafe_post_detail", method="POST", path="/unsafe/{id}", use_when="test", path_params=["id"])
    assert plan_discovery_for_endpoint(unsafe, catalog).discovery_status == "discovery_blocked_non_get"


def test_live_readiness_audit_and_skipped_reports_are_infrastructure_only(tiny_project: Config, monkeypatch):
    clear_adobe_env(monkeypatch)
    audit = audit_live_adobe_api_readiness(tiny_project)
    smoke = run_live_api_readiness_smoke(tiny_project, limit=1)
    trial = run_live_api_evidence_pipeline_trial(tiny_project, limit=1)

    assert audit["infrastructure_validation_only"] is True
    assert audit["official_score_claim"] is False
    assert "live_adobe_api_readiness_audit.md" in {path.name for path in (tiny_project.outputs_dir / "reports").glob("*.md")}
    assert smoke["status"] == "skipped_live_credentials_missing"
    assert smoke["dry_run_fallback_verified"] is True
    assert trial["status"] == "skipped_live_credentials_missing"
    assert trial["official_score_claim"] is False
    assert not (tiny_project.outputs_dir / "eval").exists()
    assert not (tiny_project.outputs_dir / "final_submission").exists()
    assert not (tiny_project.outputs_dir / "eval_results_strict.json").exists()
    assert not (tiny_project.outputs_dir / "final_submission_manifest.json").exists()


def test_live_readiness_outputs_excluded_from_final_submission():
    assert "live_api_readiness_smoke" in NON_SUBMISSION_OUTPUT_DIRS
    assert "live_api_evidence_pipeline_trial" in NON_SUBMISSION_OUTPUT_DIRS
    assert "mock_live_api_evidence_pipeline_trial" in NON_SUBMISSION_OUTPUT_DIRS


def test_live_reports_are_parseable_after_skipped_run(tiny_project: Config, monkeypatch):
    clear_adobe_env(monkeypatch)
    run_live_api_readiness_smoke(tiny_project, limit=1)
    run_live_api_evidence_pipeline_trial(tiny_project, limit=1)
    for name in ["live_api_readiness_smoke.json", "live_api_evidence_pipeline_trial.json"]:
        data = json.loads((tiny_project.outputs_dir / "reports" / name).read_text(encoding="utf-8"))
        assert data["infrastructure_validation_only"] is True
        assert data["official_score_claim"] is False
        assert "outputs/final_submission/" in data["protected_outputs_not_written"]


def test_api_required_matrix_and_mock_live_trial_reports(tiny_project: Config):
    matrix = generate_api_required_readiness_matrix(tiny_project)
    mock = run_mock_live_api_evidence_pipeline_trial(tiny_project, limit=3, clean=True)

    assert matrix["infrastructure_validation_only"] is True
    assert matrix["official_score_claim"] is False
    assert "rows" in matrix
    assert mock["infrastructure_validation_only"] is True
    assert mock["official_score_claim"] is False
    assert mock["parser_success_count"] > 0
    assert mock["evidencebus_forwarding_count"] == mock["total_mocked_live_cases"]
    assert mock["evidencebus_state_only_forwarding_count"] > 0
    assert mock["answer_slot_success_count"] > 0
    assert mock["unsupported_api_claim_count"] == 0
    assert mock["discovery_chain_simulated_count"] >= 0
    empty = next(row for row in mock["rows"] if row["query_id"] == "journey_list_empty")
    assert empty["final_answer"] == "Live API returned no matching journeys."
    assert empty["evidencebus_state_only_forwarded"] is True
    assert not (tiny_project.outputs_dir / "eval_results_strict.json").exists()
    assert not (tiny_project.outputs_dir / "final_submission").exists()


def test_pre_live_strict_baseline_and_meta_are_preserved_once(tiny_project: Config):
    strict = {
        "summary": {"by_strategy": {"SQL_FIRST_API_VERIFY": {"avg_final_score": 0.5}}},
        "rows": [{"query_id": "q1", "strategy": "SQL_FIRST_API_VERIFY", "final_score": 0.5}],
    }
    strict_path = tiny_project.outputs_dir / "eval_results_strict.json"
    tiny_project.outputs_dir.mkdir(parents=True, exist_ok=True)
    strict_path.write_text(json.dumps(strict), encoding="utf-8")

    first = preserve_pre_live_baseline(tiny_project, reason="test-baseline")
    meta_path = tiny_project.outputs_dir / "reports" / "baselines" / "pre_live_api_eval_results_strict.meta.json"
    baseline_path = tiny_project.outputs_dir / "reports" / "baselines" / "pre_live_api_eval_results_strict.json"
    assert first["created"] is True
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["reason"] == "test-baseline"
    assert meta["source_path"] == str(strict_path)
    assert len(meta["source_sha256"]) == 64

    strict_path.write_text(json.dumps({"summary": {}, "rows": []}), encoding="utf-8")
    second = preserve_pre_live_baseline(tiny_project, reason="should-not-overwrite")
    assert second["created"] is False
    assert json.loads(baseline_path.read_text(encoding="utf-8")) == strict


def test_live_api_strict_delta_report_is_diagnostic_only(tiny_project: Config):
    strict = {
        "summary": {"by_strategy": {"SQL_FIRST_API_VERIFY": {"avg_final_score": 0.5, "avg_sql_score": 1.0}}},
        "rows": [{"query_id": "q1", "strategy": "SQL_FIRST_API_VERIFY", "final_score": 0.5, "answer_score": 0.4, "sql_score": 1.0, "api_score": None}],
    }
    tiny_project.outputs_dir.mkdir(parents=True, exist_ok=True)
    (tiny_project.outputs_dir / "eval_results_strict.json").write_text(json.dumps(strict), encoding="utf-8")
    report = generate_live_api_strict_eval_delta(tiny_project, reason="test-delta")
    assert report["official_score_claim"] is False
    assert report["automatic_promotion"] is False
    assert report["baseline_preserved"]["created"] is True
    assert (tiny_project.outputs_dir / "reports" / "live_api_strict_eval_delta.json").exists()


def test_live_audit_reports_do_not_include_actual_credential_values(tiny_project: Config, monkeypatch):
    clear_adobe_env(monkeypatch)
    fake_values = {
        "ADOBE_ACCESS_TOKEN": "tok_actual_secret_value_123456",
        "ADOBE_API_KEY": "api_actual_secret_value_123456",
        "ADOBE_ORG_ID": "org_actual_secret_value_123456",
        "ADOBE_SANDBOX_NAME": "sandbox_actual_secret_value_123456",
    }
    for key, value in fake_values.items():
        monkeypatch.setenv(key, value)
    audit_live_adobe_api_readiness(tiny_project)
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (tiny_project.outputs_dir / "reports").glob("live_adobe_api_readiness_audit.*")
    )
    for value in fake_values.values():
        assert value not in combined
