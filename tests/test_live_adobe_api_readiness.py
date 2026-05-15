from __future__ import annotations

import json
import zipfile
from pathlib import Path

from dashagent.answer_slots import extract_answer_slots
from dashagent.answer_intent import AnswerIntent
from dashagent.answer_verifier import safe_rewrite
from dashagent.adobe_env import format_adobe_readiness_for_report
from dashagent.api_discovery import plan_discovery_for_endpoint, resolve_discovery_chain
from dashagent.api_client import AdobeAPIClient, AdobeCredentials, TokenAcquisitionError
from dashagent.api_outcome_classifier import classify_api_outcome, diagnose_api_outcome
from dashagent.api_response_parser import normalize_api_response
from dashagent.config import Config
from dashagent.endpoint_catalog import Endpoint, EndpointCatalog
from dashagent.evidence_bus import EvidenceBus
from dashagent.live_api_guard import OVERRIDE_FLAG, evaluate_live_api_full_run_guard
from dashagent.trajectory import redact_secrets
from scripts.audit_live_adobe_api_readiness import audit_live_adobe_api_readiness, token_acquisition_preflight
from scripts.generate_live_api_strict_eval_delta import generate_live_api_strict_eval_delta, preserve_pre_live_baseline
from scripts.generate_api_required_readiness_matrix import generate_api_required_readiness_matrix
from scripts.package_query_outputs import NON_SUBMISSION_OUTPUT_DIRS
from scripts.package_submission import REQUIRED_PATHS
from scripts.run_live_api_evidence_pipeline_trial import run_live_api_evidence_pipeline_trial
from scripts.run_live_api_endpoint_path_diagnosis import run_live_api_endpoint_path_diagnosis
from scripts.run_live_api_readiness_smoke import (
    filter_safe_smoke_endpoints,
    run_live_api_readiness_smoke,
    safe_error_excerpt,
)
from scripts.run_live_api_targeted_failure_analysis import run_live_api_targeted_failure_analysis
from scripts.run_full_generated_prompt_suite_diagnostic import run_full_generated_prompt_suite_diagnostic
from scripts.run_post_permission_live_api_verification import (
    run_post_permission_live_api_verification,
    write_adobe_access_waiting_status,
)
from scripts.run_mock_live_api_evidence_pipeline_trial import run_mock_live_api_evidence_pipeline_trial
from scripts import run_dev_eval


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
    assert classify_api_outcome({"status_code": 500, "ok": False, "error": "route not found"}) == "endpoint_path_issue"
    assert classify_api_outcome({"status_code": 500, "ok": False, "error": "tenant sandbox mismatch"}) == "sandbox_scope_issue"
    assert classify_api_outcome({"status_code": 400, "ok": False, "error": "missing required query parameter"}) == "api_error"
    required = diagnose_api_outcome({"status_code": 400, "ok": False, "error": "missing required query parameter"})
    assert required["likely_failure_area"] == "required_param"
    assert required["next_action"] == "add_required_param"
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


def test_smoke_default_order_filters_and_safe_excerpt(monkeypatch):
    catalog = EndpointCatalog()
    safe = [
        endpoint
        for endpoint in catalog.endpoints
        if endpoint.method == "GET" and not endpoint.path_params and "{" not in endpoint.path
    ]
    selected = filter_safe_smoke_endpoints(safe, limit=12)
    selected_ids = [endpoint.id for endpoint in selected]
    for endpoint_id in [
        "catalog_datasets",
        "schema_registry_schemas",
        "unified_tags",
        "merge_policies",
        "catalog_batches",
        "audit_events",
    ]:
        assert endpoint_id in selected_ids
    assert len(filter_safe_smoke_endpoints(safe, limit="all-safe-get")) == len(safe)
    assert [endpoint.id for endpoint in filter_safe_smoke_endpoints(safe, limit="all-safe-get", endpoint_id="merge_policies")] == ["merge_policies"]
    assert all(
        "DATASET_SCHEMA" in endpoint.domains or "dataset" in endpoint.id
        for endpoint in filter_safe_smoke_endpoints(safe, limit="all-safe-get", endpoint_family="DATASET_SCHEMA")
    )

    monkeypatch.setenv("ADOBE_ACCESS_TOKEN", "tok_secret_excerpt_value")
    monkeypatch.setenv("ADOBE_API_KEY", "api_secret_excerpt_value")
    monkeypatch.setenv("ADOBE_ORG_ID", "alias-org-secret")
    monkeypatch.setenv("ADOBE_SANDBOX_NAME", "alias-sandbox-secret")
    excerpt = safe_error_excerpt(
        {
            "error": "Authorization" + ": " + "Bearer tok_secret_excerpt_value x-api-key=api_secret_excerpt_value ali***",
            "result_preview": "alias-org-secret alias-sandbox-secret route not found",
            "headers": {"Authorization": "Bearer should-not-appear"},
        },
        max_chars=300,
    )
    assert len(excerpt) <= 300
    for forbidden in [
        "tok_secret_excerpt_value",
        "api_secret_excerpt_value",
        "alias-org-secret",
        "alias-sandbox-secret",
        "Bearer tok",
        "ali***",
    ]:
        assert forbidden not in excerpt


def test_live_trial_client_credentials_success_does_not_emit_stale_skip(monkeypatch, tiny_project: Config):
    clear_adobe_env(monkeypatch)
    monkeypatch.setenv("CLIENT_ID", "client-id-live-trial")
    monkeypatch.setenv("CLIENT_SECRET", "client-secret-live-trial")
    monkeypatch.setenv("IMS_ORG", "org-live-trial")
    monkeypatch.setenv("SANDBOX", "sandbox-live-trial")

    monkeypatch.setattr(
        "scripts.run_live_api_evidence_pipeline_trial.token_acquisition_preflight",
        lambda config, readiness=None: {
            "token_acquisition_attempted": True,
            "token_acquisition_ok": True,
            "expires_in_present": True,
            "error_category": None,
        },
    )

    class FakeHarness:
        def __init__(self, config):
            pass

        def load_examples(self):
            return [
                type(
                    "Example",
                    (),
                    {
                        "query_id": "query_live_trial",
                        "query": "List journeys.",
                        "gold_api": [{"method": "GET", "url": "/ajo/journey"}],
                    },
                )()
            ]

    class FakeExecutor:
        def __init__(self, config, api_client=None):
            pass

        def run(self, query, strategy, query_id, output_dir):
            output_dir.mkdir(parents=True, exist_ok=True)
            return {
                "trajectory": {
                    "steps": [
                        {
                            "kind": "api_call",
                            "method": "GET",
                            "url": "/ajo/journey",
                            "result": {
                                "ok": False,
                                "dry_run": False,
                                "status_code": 403,
                                "error": "missing scope",
                                "parsed_evidence": normalize_api_response(
                                    {"error": "missing scope"},
                                    ok=False,
                                    dry_run=False,
                                    status_code=403,
                                ),
                            },
                        }
                    ],
                    "final_answer": "API evidence unavailable.",
                }
            }

    monkeypatch.setattr("scripts.run_live_api_evidence_pipeline_trial.EvalHarness", FakeHarness)
    monkeypatch.setattr("scripts.run_live_api_evidence_pipeline_trial.AgentExecutor", FakeExecutor)
    report = run_live_api_evidence_pipeline_trial(tiny_project, limit=1, clean=True)
    markdown = (tiny_project.outputs_dir / "reports" / "live_api_evidence_pipeline_trial.md").read_text(encoding="utf-8")
    assert report["status"] == "complete"
    assert report["credentials_present"] is True
    assert report["recommendation"] != "provide_live_credentials_then_rerun"
    assert report["usable_live_api_evidence_count"] == 0
    assert report["answer_used_usable_api_evidence_count"] == 0
    assert report["api_state_forwarded_count"] == 1
    assert report["answer_used_api_state_count"] == 1
    assert report["evidencebus_api_evidence_count"] == 0
    assert "skipped_live_credentials_missing" not in json.dumps(report)
    assert "Credentials present: `False`" not in markdown
    assert "provide_live_credentials_then_rerun" not in markdown
    assert "Answer used usable API evidence count" in markdown
    assert "Answer used API state/caveat count" in markdown


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
    assert "live_api_strict_eval_diagnostic_override" in NON_SUBMISSION_OUTPUT_DIRS
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
        "ADOBE_ORG_ID": "alias-org-actual-secret-value",
        "ADOBE_SANDBOX_NAME": "alias-sandbox-actual-secret-value",
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
        assert f"{value[:3]}***" not in combined
    assert '"org_id":' not in combined
    assert "`org_id`" not in combined
    assert '"sandbox_name":' not in combined
    assert "`sandbox_name`" not in combined
    assert "ali***" not in combined


def test_live_api_full_run_guard_blocks_missing_or_zero_success_smoke(tiny_project: Config):
    missing = evaluate_live_api_full_run_guard(tiny_project, live_mode_active=True)
    assert missing["allowed"] is False
    assert missing["reason"] == "smoke_report_missing_or_stale"
    blocker = json.loads((tiny_project.outputs_dir / "reports" / "live_api_full_run_blocker.json").read_text(encoding="utf-8"))
    for key in [
        "created_at",
        "guard_decision",
        "source_smoke_report",
        "source_smoke_report_sha256",
        "live_success_count",
        "failure_counts",
        "override_available_flag",
        "safe_rerun_commands",
    ]:
        assert key in blocker

    reports = tiny_project.outputs_dir / "reports"
    (reports / "live_api_readiness_smoke.json").write_text(
        json.dumps({"endpoints_tested": [{"endpoint_id": "journey_list", "outcome": "external_api_unavailable"}]}),
        encoding="utf-8",
    )
    blocked = evaluate_live_api_full_run_guard(tiny_project, live_mode_active=True)
    assert blocked["allowed"] is False
    assert blocked["reason"] == "no_live_success"
    assert blocked["failure_counts"]["external_api_unavailable"] == 1
    assert blocked["source_smoke_report_sha256"]


def test_live_api_full_run_guard_allows_success_and_cli_override(tiny_project: Config):
    reports = tiny_project.outputs_dir / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "live_api_readiness_smoke.json").write_text(
        json.dumps({"endpoints_tested": [{"endpoint_id": "journey_list", "outcome": "live_success"}]}),
        encoding="utf-8",
    )
    allowed = evaluate_live_api_full_run_guard(tiny_project, live_mode_active=True)
    assert allowed["allowed"] is True
    assert allowed["guard_decision"] == "allowed_live_success"

    (reports / "live_api_readiness_smoke.json").write_text(
        json.dumps({"endpoints_tested": [{"endpoint_id": "journey_list", "outcome": "external_api_unavailable"}]}),
        encoding="utf-8",
    )
    override = evaluate_live_api_full_run_guard(tiny_project, live_mode_active=True, override=True)
    assert override["allowed"] is True
    assert override["guard_decision"] == "allowed_diagnostic_override"
    assert override["override_available_flag"] == OVERRIDE_FLAG
    assert override["diagnostic_only"] is True
    assert override["promotion_allowed"] is False


def test_full_generated_prompt_diagnostic_obeys_live_api_guard(monkeypatch, tiny_project: Config):
    clear_adobe_env(monkeypatch)
    monkeypatch.setenv("CLIENT_ID", "client-id-guard-test")
    monkeypatch.setenv("CLIENT_SECRET", "client-secret-guard-test")
    reports = tiny_project.outputs_dir / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "live_api_readiness_smoke.json").write_text(
        json.dumps({"endpoints_tested": [{"endpoint_id": "journey_list", "outcome": "external_api_unavailable"}]}),
        encoding="utf-8",
    )
    report = run_full_generated_prompt_suite_diagnostic(tiny_project)
    assert report["status"] == "blocked_by_live_api_guard"
    assert report["live_api_guard"]["reason"] == "no_live_success"
    assert report["executed_prompts"] == 0


def test_run_dev_eval_strict_guard_blocks_live_mode_without_overwriting(monkeypatch, tiny_project: Config):
    clear_adobe_env(monkeypatch)
    monkeypatch.setenv("CLIENT_ID", "client-id-guard-test")
    monkeypatch.setenv("CLIENT_SECRET", "client-secret-guard-test")
    monkeypatch.setenv("DASHAGENT_DATA_DIR", str(tiny_project.data_dir))
    monkeypatch.setenv("DASHAGENT_DBSNAPSHOT_DIR", str(tiny_project.dbsnapshot_dir))
    monkeypatch.setenv("DASHAGENT_DATA_JSON", str(tiny_project.data_json_path))
    monkeypatch.setenv("DASHAGENT_OUTPUTS_DIR", str(tiny_project.outputs_dir))
    monkeypatch.setenv("DASHAGENT_PROMPTS_DIR", str(tiny_project.prompts_dir))
    reports = tiny_project.outputs_dir / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "live_api_readiness_smoke.json").write_text(
        json.dumps({"endpoints_tested": [{"endpoint_id": "journey_list", "outcome": "external_api_unavailable"}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(run_dev_eval, "load_local_env", lambda root: {})
    monkeypatch.setattr(run_dev_eval.sys, "argv", ["run_dev_eval.py", "--strict"])
    assert run_dev_eval.main() == 2
    assert (reports / "live_api_full_run_blocker.json").exists()
    assert not (tiny_project.outputs_dir / "eval_results_strict.json").exists()
    assert not (tiny_project.outputs_dir / "eval").exists()


def test_targeted_failure_analysis_rows_include_next_action(tiny_project: Config):
    reports = tiny_project.outputs_dir / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "live_api_readiness_smoke.json").write_text(
        json.dumps(
            {
                "endpoints_tested": [
                    {
                        "endpoint_id": "merge_policies",
                        "method": "GET",
                        "path": "/data/core/ups/config/mergePolicies",
                        "status_code": 403,
                        "outcome": "scope_or_permission_issue",
                    },
                    {
                        "endpoint_id": "schema_registry_schemas",
                        "method": "GET",
                        "path": "/data/foundation/schemaregistry/tenant/schemas",
                        "status_code": 500,
                        "outcome": "external_api_unavailable",
                    },
                ],
                "selection_filters": {"limit": "all-safe-get"},
            }
        ),
        encoding="utf-8",
    )
    (reports / "live_api_evidence_pipeline_trial.json").write_text(json.dumps({"rows": []}), encoding="utf-8")
    report = run_live_api_targeted_failure_analysis(tiny_project)
    actions = {row["next_action"] for row in report["rows"]}
    assert "verify_scope" in actions
    assert "wait_external_service" in actions
    assert all(row["likely_failure_area"] for row in report["rows"])
    assert all(row["confidence"] in {"high", "medium", "low"} for row in report["rows"])
    assert all("safe_error_excerpt" in row for row in report["rows"])
    for row in report["rows"]:
        for key in [
            "outcome",
            "code_fix_allowed",
            "reason_code",
            "human_explanation",
            "evidence_source",
        ]:
            assert key in row
    assert report["uses_shared_api_outcome_classifier"] is True
    followup = json.loads((reports / "live_api_endpoint_followup_commands.json").read_text(encoding="utf-8"))
    blockers = json.loads((reports / "live_api_external_blockers.json").read_text(encoding="utf-8"))
    assert followup["report_type"] == "live_api_endpoint_followup_commands"
    assert any("--endpoint-id merge_policies" in item["command"] for item in followup["commands"])
    assert blockers["report_type"] == "live_api_external_blockers"
    titles = {group["title"] for group in blockers["groups"]}
    assert "Likely Adobe permission/scope setup" in titles
    assert "Likely sandbox/environment setup" in titles
    assert "Unresolved endpoint/path evidence with no proven code fix" in titles
    assert "Likely Adobe service/server issue" in titles


def test_live_endpoint_path_diagnosis_reports_safe_candidates(monkeypatch, tiny_project: Config):
    reports = tiny_project.outputs_dir / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "live_api_readiness_smoke.json").write_text(
        json.dumps(
            {
                "endpoints_tested": [
                    {
                        "endpoint_id": "unified_tags",
                        "method": "GET",
                        "path": "/unifiedtags/tags",
                        "status_code": 404,
                        "outcome": "endpoint_path_issue",
                    },
                    {
                        "endpoint_id": "merge_policies",
                        "method": "GET",
                        "path": "/data/core/ups/config/mergePolicies",
                        "status_code": 403,
                        "outcome": "scope_or_permission_issue",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    class FakeClient:
        dry_run = False

        def __init__(self, config):
            pass

        def call_api(self, method, url, params, headers):
            assert method == "GET"
            assert "{" not in url and "}" not in url
            return {"ok": False, "dry_run": False, "status_code": 404, "error": "route not found"}

    monkeypatch.setattr("scripts.run_live_api_endpoint_path_diagnosis.AdobeAPIClient", FakeClient)
    report = run_live_api_endpoint_path_diagnosis(tiny_project)
    assert report["diagnostic_only"] is True
    assert report["mutating_calls_executed"] is False
    assert len(report["rows"]) == 1
    row = report["rows"][0]
    assert row["endpoint_id"] == "unified_tags"
    assert row["recommended_action"] == "no_code_fix"
    assert row["code_change_recommended"] is False
    assert row["candidate_safe_get_paths_attempted"]
    assert all(path.startswith("/") for path in row["candidate_safe_get_paths_attempted"])


def test_targeted_failure_analysis_uses_path_diagnosis_to_block_catalog_fix(tiny_project: Config):
    reports = tiny_project.outputs_dir / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "live_api_readiness_smoke.json").write_text(
        json.dumps(
            {
                "endpoints_tested": [
                    {
                        "endpoint_id": "unified_tags",
                        "method": "GET",
                        "path": "/unifiedtags/tags",
                        "status_code": 404,
                        "outcome": "endpoint_path_issue",
                        "safe_error_excerpt": "route not found",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (reports / "live_api_endpoint_path_diagnosis.json").write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "endpoint_id": "unified_tags",
                        "recommended_action": "no_code_fix",
                        "code_change_recommended": False,
                        "evidence": "best candidate outcome remained endpoint_path_issue",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (reports / "live_api_evidence_pipeline_trial.json").write_text(json.dumps({"rows": []}), encoding="utf-8")
    report = run_live_api_targeted_failure_analysis(tiny_project)
    row = report["rows"][0]
    assert row["outcome"] == "endpoint_path_issue"
    assert row["code_fix_allowed"] is False
    assert row["next_action"] == "no_code_fix"
    assert row["reason_code"] == "no_successful_safe_get_candidate"
    assert row["evidence_source"] == "endpoint_path_diagnosis"


def test_post_permission_runner_records_subcommands_and_waiting_status(tiny_project: Config, monkeypatch):
    clear_adobe_env(monkeypatch)
    monkeypatch.setenv("CLIENT_ID", "client-id-test")
    monkeypatch.setenv("CLIENT_SECRET", "client-secret-test")
    monkeypatch.setenv("ADOBE_API_KEY", "api-key-test")
    monkeypatch.setattr(
        "scripts.run_post_permission_live_api_verification.token_acquisition_preflight",
        lambda config, readiness: {"token_acquisition_attempted": True, "token_acquisition_ok": True},
    )
    reports = tiny_project.outputs_dir / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "live_api_readiness_smoke.json").write_text(
        json.dumps(
            {
                "status": "complete",
                "endpoints_tested": [
                    {"endpoint_id": "merge_policies", "outcome": "auth_error"},
                    {"endpoint_id": "journey_list", "outcome": "external_api_unavailable"},
                ],
            }
        ),
        encoding="utf-8",
    )
    (reports / "live_api_evidence_pipeline_trial.json").write_text(
        json.dumps({"usable_live_api_evidence_count": 0, "api_state_forwarded_count": 2}),
        encoding="utf-8",
    )
    (reports / "live_api_endpoint_followup_commands.json").write_text(
        json.dumps({"commands": [{"command": "python3 scripts/run_live_api_readiness_smoke.py --endpoint-id merge_policies"}]}),
        encoding="utf-8",
    )
    (reports / "live_api_external_blockers.json").write_text(
        json.dumps({"groups": [{"title": "Likely Adobe permission/scope setup", "affected_endpoints": ["merge_policies"]}]}),
        encoding="utf-8",
    )

    commands_seen: list[str] = []

    def fake_runner(command: list[str], cwd: Path) -> int:
        commands_seen.append(" ".join(command))
        return 0

    report = run_post_permission_live_api_verification(tiny_project, command_runner=fake_runner)

    assert report["diagnostic_only"] is True
    assert report["full_strict_eval_executed"] is False
    assert report["full_generated_prompt_suite_executed"] is False
    assert len(report["commands"]) == 5
    assert all({"command", "exit_code", "started_at", "ended_at", "duration_seconds", "status", "report_path"} <= set(row) for row in report["commands"])
    assert not any("run_dev_eval.py" in command for command in commands_seen)
    assert not any("run_full_generated_prompt_suite_diagnostic.py" in command for command in commands_seen)
    assert report["live_success_count"] == 0
    assert report["recommended_next_command"] == "python3 scripts/run_live_api_readiness_smoke.py --limit all-safe-get"
    assert any(command.endswith("--endpoint-id merge_policies") for command in report["recommended_followup_commands"])
    assert report["guard_decision"] == "blocked"
    assert report["reason"] == "no_live_success"
    waiting = json.loads((reports / "adobe_access_waiting_status.json").read_text(encoding="utf-8"))
    waiting_md = (reports / "adobe_access_waiting_status.md").read_text(encoding="utf-8")
    assert waiting["report_type"] == "adobe_access_waiting_status"
    assert "## What Works" in waiting_md
    assert "## What Is Blocked" in waiting_md
    assert "## Why This Is Likely External Adobe Access" in waiting_md
    assert "## What External Access Is Needed" in waiting_md
    assert "## What Command To Run After Permission Is Granted" in waiting_md
    assert "## Current Guard Status" in waiting_md
    assert "## What Local Work Was Completed While Waiting" in waiting_md


def test_adobe_access_waiting_status_is_short_and_redacted(tiny_project: Config, monkeypatch):
    clear_adobe_env(monkeypatch)
    reports = tiny_project.outputs_dir / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "live_api_readiness_smoke.json").write_text(json.dumps({"endpoints_tested": []}), encoding="utf-8")
    payload = write_adobe_access_waiting_status(tiny_project)
    markdown = (reports / "adobe_access_waiting_status.md").read_text(encoding="utf-8")
    assert payload["official_score_claim"] is False
    assert "Authorization" not in markdown
    assert "ADOBE_ACCESS_TOKEN" not in markdown
    assert "ali***" not in markdown
    assert markdown.count("## ") == 7


def test_redacted_live_api_error_fixtures_classify_expected_outcomes():
    fixture_dir = Path(__file__).parent / "fixtures" / "live_api_errors"
    expected = {
        "auth_error_401.json": "auth_error",
        "invalid_sandbox_400.json": "sandbox_scope_issue",
        "endpoint_path_404.json": "endpoint_path_issue",
        "sandbox_internal_500.json": "sandbox_scope_issue",
        "service_unavailable_500.json": "external_api_unavailable",
    }
    forbidden = [
        "Bearer ",
        "ADOBE_ACCESS_TOKEN",
        "ADOBE_API_KEY",
        "ADOBE_CLIENT_SECRET",
        "IMS_ORG",
        "ali***",
    ]
    for name, outcome in expected.items():
        payload = json.loads((fixture_dir / name).read_text(encoding="utf-8"))
        text = json.dumps(payload)
        assert all(token not in text for token in forbidden)
        result = {
            "ok": False,
            "dry_run": False,
            "status_code": payload["status_code"],
            "error": json.dumps(payload["body"]),
        }
        assert classify_api_outcome(result, method="GET", path="/synthetic/path") == outcome


def test_safe_error_excerpt_redacts_ids_and_token_like_values():
    fake_key = "sk-" + "1234567890abcdef"
    fake_auth = "Authorization: " + "Bearer secret-token-value"
    excerpt = safe_error_excerpt(
        {
            "error": {
                "message": "failed for org ali-prod sandbox abc-prod",
                "requestId": "real-request-id-123",
                "registryRequestId": "real-registry-request-id-123",
                "traceId": "real-trace-id-123",
                "timestamp": "2026-05-16T00:00:00Z",
                "token": fake_key,
            },
            "result_preview": f"{fake_auth} x-api-key=secret-api-key abc***",
        },
        max_chars=300,
    )
    assert len(excerpt) <= 300
    assert "real-request-id" not in excerpt
    assert "real-registry-request-id" not in excerpt
    assert "real-trace-id" not in excerpt
    assert "2026-05-16" not in excerpt
    assert "ali-prod" not in excerpt
    assert "abc-prod" not in excerpt
    assert fake_key not in excerpt
    assert "Bearer secret-token-value" not in excerpt
    assert "secret-api-key" not in excerpt
    assert "abc***" not in excerpt
    assert "synthetic-request-id" in excerpt
    assert "synthetic-timestamp" in excerpt


def test_generated_local_diagnostic_is_excluded_from_packages(tmp_path: Path):
    assert "generated_prompt_suite_local_diagnostic" in NON_SUBMISSION_OUTPUT_DIRS
    assert "outputs" not in REQUIRED_PATHS
    assert ".env.local" not in REQUIRED_PATHS
    package_dir = tmp_path / "source_code"
    local_output = package_dir / "outputs" / "generated_prompt_suite_local_diagnostic" / "prompt_001"
    local_output.mkdir(parents=True)
    (local_output / "trajectory.json").write_text("{}", encoding="utf-8")
    zip_path = tmp_path / "source_code.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        for file_path in package_dir.rglob("*"):
            if "generated_prompt_suite_local_diagnostic" not in file_path.parts:
                archive.write(file_path, file_path.relative_to(package_dir))
    with zipfile.ZipFile(zip_path) as archive:
        assert not any("generated_prompt_suite_local_diagnostic" in name for name in archive.namelist())
