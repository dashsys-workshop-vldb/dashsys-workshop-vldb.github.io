from __future__ import annotations

import json
from pathlib import Path

from dashagent.answer_slots import extract_answer_slots
from dashagent.api_client import AdobeAPIClient, AdobeCredentials
from dashagent.api_response_parser import normalize_api_response
from dashagent.config import Config
from dashagent.evidence_bus import EvidenceBus
from dashagent.trajectory import redact_secrets
from scripts.audit_live_adobe_api_readiness import audit_live_adobe_api_readiness
from scripts.package_query_outputs import NON_SUBMISSION_OUTPUT_DIRS
from scripts.run_live_api_evidence_pipeline_trial import run_live_api_evidence_pipeline_trial
from scripts.run_live_api_readiness_smoke import run_live_api_readiness_smoke


ADOBE_ENV_NAMES = [
    "ADOBE_ACCESS_TOKEN",
    "ADOBE_API_KEY",
    "ADOBE_ORG_ID",
    "ADOBE_SANDBOX_NAME",
    "ADOBE_BASE_URL",
    "ADOBE_CLIENT_ID",
    "ADOBE_CLIENT_SECRET",
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


def test_api_response_parser_distinguishes_live_empty_dry_run_and_error():
    live_empty = normalize_api_response([], ok=True, dry_run=False, status_code=200)
    dry_run = normalize_api_response(None, ok=False, dry_run=True)
    api_error = normalize_api_response({"error": "unauthorized"}, ok=False, dry_run=False, status_code=401)

    assert live_empty["ok"] is True
    assert live_empty["dry_run"] is False
    assert live_empty["items"] == []
    assert live_empty["evidence_state"] == "live_empty_result"
    assert dry_run["dry_run"] is True
    assert dry_run["live_evidence_available"] is False
    assert api_error["ok"] is False
    assert api_error["dry_run"] is False
    assert api_error["errors"]


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
    parsed = normalize_api_response(payload, ok=True, dry_run=False, status_code=200)
    assert parsed["items"][0]["_id"] == "item-1"
    assert "item-1" in parsed["ids"]
    assert "Audience One" in parsed["names"]
    assert "active" in parsed["statuses"]
    assert parsed["counts"]["totalProfiles"] == 7
    assert parsed["timestamps"]["updatedAt"] == "2026-03-31T00:00:00Z"
    assert parsed["pagination"]["page"]["limit"] == 1


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
    assert slots.api_item_count == 1
    assert "Flow One" in slots.entity_names


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


def test_live_reports_are_parseable_after_skipped_run(tiny_project: Config, monkeypatch):
    clear_adobe_env(monkeypatch)
    run_live_api_readiness_smoke(tiny_project, limit=1)
    run_live_api_evidence_pipeline_trial(tiny_project, limit=1)
    for name in ["live_api_readiness_smoke.json", "live_api_evidence_pipeline_trial.json"]:
        data = json.loads((tiny_project.outputs_dir / "reports" / name).read_text(encoding="utf-8"))
        assert data["infrastructure_validation_only"] is True
        assert data["official_score_claim"] is False
        assert "outputs/final_submission/" in data["protected_outputs_not_written"]
