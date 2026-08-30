#!/usr/bin/env python
from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.answer_slots import extract_answer_slots
from dashagent.api_client import AdobeAPIClient
from dashagent.api_outcome_classifier import classify_api_outcome
from dashagent.config import Config
from dashagent.endpoint_catalog import Endpoint, EndpointCatalog
from dashagent.evidence_bus import EvidenceBus
from dashagent.trajectory import redact_secrets
from dashagent.validators import APIValidator
from scripts.load_local_env import load_local_env


OUTPUT_STEM = "guarded_dash_agent_live_e2e_trial"
PASS_PARSER_STATES = {
    "live_evidence",
    "live_empty",
    "live_empty_result",
    "api_error",
    "malformed_response",
    "token_acquisition_failed",
}


@dataclass(frozen=True)
class TrialCase:
    query_id: str
    prompt: str
    route: str
    endpoint_id: str


def build_trial_cases() -> list[TrialCase]:
    return [
        TrialCase(
            "audience_list",
            "List available audiences for this workspace using live Adobe evidence.",
            "audience_segment",
            "ups_audiences",
        ),
        TrialCase(
            "segment_definition_list",
            "List segment definitions available for this workspace.",
            "audience_segment",
            "segment_definitions",
        ),
        TrialCase(
            "merge_policy_list",
            "List merge policies for Real-Time Customer Profile.",
            "merge_policies",
            "merge_policies",
        ),
        TrialCase(
            "destination_flows",
            "Show destination or dataflow records from Flow Service.",
            "flows_runs",
            "flowservice_flows",
        ),
        TrialCase(
            "flow_runs",
            "Show recent Flow Service run records.",
            "flows_runs",
            "flowservice_runs",
        ),
        TrialCase(
            "dataset_list",
            "List datasets from Catalog Service.",
            "datasets_batches",
            "catalog_datasets",
        ),
        TrialCase(
            "batch_list",
            "List catalog batches from the workspace.",
            "datasets_batches",
            "catalog_batches",
        ),
        TrialCase(
            "tenant_schema_list",
            "List tenant schemas from Schema Registry.",
            "schemas",
            "schema_registry_schemas",
        ),
        TrialCase(
            "schema_short_alias",
            "Find schemas using the shorthand schema-list alias.",
            "schemas",
            "schemas_short",
        ),
        TrialCase(
            "audit_events",
            "List audit events using the resolved audit-events shorthand.",
            "audit_events",
            "audit_events_short",
        ),
        TrialCase(
            "unified_tags",
            "List unified tags using the documented Unified Tags API.",
            "tags",
            "unified_tags",
        ),
        TrialCase(
            "unified_tag_categories",
            "List unified tag categories using the documented Unified Tags API.",
            "tags",
            "unified_tag_categories",
        ),
    ]


def main() -> int:
    load_local_env(ROOT, override=True)
    config = Config.from_env(ROOT)
    payload = run_guarded_dash_agent_live_e2e_trial(config)
    report = config.outputs_dir / "reports" / f"{OUTPUT_STEM}.json"
    print(json.dumps({"status": payload["status"], "report": str(report)}, indent=2, sort_keys=True))
    return 0 if payload["status"] == "pass" else 2


def run_guarded_dash_agent_live_e2e_trial(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    catalog = EndpointCatalog(config)
    validator = APIValidator(catalog)
    client = AdobeAPIClient(config)
    rows = [
        run_case(case, catalog=catalog, validator=validator, client=client)
        for case in build_trial_cases()
    ]
    payload = build_report(rows)
    write_report(reports_dir / OUTPUT_STEM, payload)
    return payload


def run_case(
    case: TrialCase,
    *,
    catalog: EndpointCatalog,
    validator: APIValidator,
    client: AdobeAPIClient,
) -> dict[str, Any]:
    started = time.perf_counter()
    endpoint = catalog.by_id(case.endpoint_id)
    if endpoint is None:
        return {
            "query_id": case.query_id,
            "prompt": case.prompt,
            "route": case.route,
            "api_endpoint_selected": case.endpoint_id,
            "api_outcome": "endpoint_path_issue",
            "parser_result": "not_available",
            "evidencebus_usable_evidence": False,
            "answer_evidence_usage": "not_available",
            "unsupported_claims": [],
            "tool_count": 0,
            "runtime_ms": elapsed_ms(started),
            "validation_ok": False,
            "selected_endpoint_unresolved_path_failure": True,
        }

    headers = dict(endpoint.common_headers or {})
    validation = validator.validate(endpoint.method, endpoint.path, endpoint.common_params, headers)
    if not validation.ok:
        return case_failure_row(case, endpoint, validation.to_dict(), started)

    result = client.call_api(endpoint.method, endpoint.path, endpoint.common_params, headers)
    outcome = classify_api_outcome(result, method=endpoint.method, path=endpoint.path)
    parsed = result.get("parsed_evidence") if isinstance(result, dict) else None
    parser_result = parser_status(parsed, result)
    bus = EvidenceBus()
    step = type("Step", (), {"family": endpoint.id, "url": endpoint.path})()
    bus.observe_api(step, result)
    slots = extract_answer_slots(
        case.prompt,
        [{"type": "api", "step": {"family": endpoint.id, "url": endpoint.path}, "payload": result}],
    )
    usable_evidence = bool(isinstance(parsed, dict) and parsed.get("live_evidence_available") is True)
    api_state_forwarded = bool(
        bus.api_items
        or bus.api_ids
        or bus.api_errors
        or bus.api_evidence_states
        or bus.names
        or bus.ids
        or bus.statuses
    )
    answer_used_evidence = bool(usable_evidence and (slots.api_items or slots.api_item_count is not None or slots.answer_slot_source))
    answer_usage = "used_usable_api_evidence" if answer_used_evidence else "used_api_state_caveat"
    selected_path_failure = outcome == "endpoint_path_issue"
    return redact_secrets(
        {
            "query_id": case.query_id,
            "prompt": case.prompt,
            "route": case.route,
            "api_endpoint_selected": endpoint.id,
            "method": endpoint.method,
            "safe_path": endpoint.path,
            "safe_params": endpoint.common_params,
            "safe_header_names": sorted(headers),
            "api_status_code": result.get("status_code"),
            "api_outcome": outcome,
            "parser_result": parser_result,
            "parser_evidence_state": parsed.get("evidence_state") if isinstance(parsed, dict) else None,
            "evidencebus_usable_evidence": usable_evidence,
            "api_state_forwarded": api_state_forwarded,
            "answer_evidence_usage": answer_usage,
            "answer_used_usable_api_evidence": answer_used_evidence,
            "answer_used_api_state": bool(api_state_forwarded and not answer_used_evidence),
            "unsupported_claims": [],
            "tool_count": 1,
            "runtime_ms": elapsed_ms(started),
            "validation_ok": validation.ok,
            "selected_endpoint_unresolved_path_failure": selected_path_failure,
        }
    )


def case_failure_row(
    case: TrialCase,
    endpoint: Endpoint,
    validation: dict[str, Any],
    started: float,
) -> dict[str, Any]:
    return {
        "query_id": case.query_id,
        "prompt": case.prompt,
        "route": case.route,
        "api_endpoint_selected": endpoint.id,
        "method": endpoint.method,
        "safe_path": endpoint.path,
        "safe_params": endpoint.common_params,
        "safe_header_names": sorted(endpoint.common_headers or {}),
        "api_status_code": None,
        "api_outcome": "endpoint_path_issue",
        "parser_result": "not_available",
        "parser_evidence_state": None,
        "evidencebus_usable_evidence": False,
        "api_state_forwarded": False,
        "answer_evidence_usage": "not_available",
        "answer_used_usable_api_evidence": False,
        "answer_used_api_state": False,
        "unsupported_claims": [],
        "tool_count": 0,
        "runtime_ms": elapsed_ms(started),
        "validation_ok": False,
        "validation": validation,
        "selected_endpoint_unresolved_path_failure": True,
    }


def parser_status(parsed: Any, result: dict[str, Any]) -> str:
    if result.get("dry_run"):
        return "dry_run_fallback"
    if isinstance(parsed, dict) and parsed.get("evidence_state") in PASS_PARSER_STATES:
        return "pass"
    return "not_available"


def elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def build_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    live_success_count = sum(1 for row in rows if row.get("api_outcome") == "live_success")
    live_empty_count = sum(1 for row in rows if row.get("api_outcome") == "live_empty")
    parser_success_count = sum(1 for row in rows if row.get("parser_result") == "pass")
    unsupported_count = sum(len(row.get("unsupported_claims") or []) for row in rows)
    unresolved_path_count = sum(1 for row in rows if row.get("selected_endpoint_unresolved_path_failure"))
    parser_evidencebus_failure_count = sum(
        1
        for row in rows
        if row.get("parser_result") != "pass" or row.get("selected_endpoint_unresolved_path_failure")
    )
    payload = {
        "report_type": OUTPUT_STEM,
        "diagnostic_only": True,
        "official_score_claim": False,
        "mutating_calls_executed": False,
        "status": "pass"
        if parser_evidencebus_failure_count == 0 and unsupported_count == 0 and unresolved_path_count == 0
        else "fail",
        "rows": rows,
        "summary": {
            "trial_query_count": len(rows),
            "live_api_calls_attempted": sum(1 for row in rows if row.get("tool_count")),
            "live_success_count": live_success_count,
            "live_empty_count": live_empty_count,
            "api_failure_count": len(rows) - live_success_count - live_empty_count,
            "parser_success_count": parser_success_count,
            "usable_live_api_evidence_count": sum(1 for row in rows if row.get("evidencebus_usable_evidence")),
            "api_state_forwarded_count": sum(1 for row in rows if row.get("api_state_forwarded")),
            "answer_used_usable_api_evidence_count": sum(1 for row in rows if row.get("answer_used_usable_api_evidence")),
            "answer_used_api_state_count": sum(1 for row in rows if row.get("answer_used_api_state")),
            "unsupported_api_claim_count": unsupported_count,
            "parser_evidencebus_failure_count": parser_evidencebus_failure_count,
            "unresolved_path_failure_count": unresolved_path_count,
        },
        "families_tested": sorted({str(row.get("route")) for row in rows}),
        "endpoint_ids_tested": [row.get("api_endpoint_selected") for row in rows],
        "requirements": {
            "parser_evidencebus_failures_zero": parser_evidencebus_failure_count == 0,
            "unsupported_api_claims_zero": unsupported_count == 0,
            "no_selected_endpoint_unresolved_path_failure": unresolved_path_count == 0,
        },
    }
    return redact_secrets(payload)


def write_report(stem: Path, payload: dict[str, Any]) -> None:
    stem.with_suffix(".json").write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    stem.with_suffix(".md").write_text(render_report(payload), encoding="utf-8")


def render_report(payload: dict[str, Any]) -> str:
    summary = payload.get("summary", {})
    lines = [
        "# Guarded Dash Agent Live E2E Trial",
        "",
        "Diagnostic-only live Adobe trial over supported GET endpoint families. No mutating calls were executed.",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Trial queries: `{summary.get('trial_query_count')}`",
        f"- Live API calls attempted: `{summary.get('live_api_calls_attempted')}`",
        f"- Live success: `{summary.get('live_success_count')}`",
        f"- Live empty: `{summary.get('live_empty_count')}`",
        f"- API failures: `{summary.get('api_failure_count')}`",
        f"- Parser successes: `{summary.get('parser_success_count')}`",
        f"- Usable live API evidence: `{summary.get('usable_live_api_evidence_count')}`",
        f"- API state forwarded: `{summary.get('api_state_forwarded_count')}`",
        f"- Answers used usable API evidence: `{summary.get('answer_used_usable_api_evidence_count')}`",
        f"- Unsupported API claims: `{summary.get('unsupported_api_claim_count')}`",
        f"- Parser/EvidenceBus failures: `{summary.get('parser_evidencebus_failure_count')}`",
        f"- Unresolved path failures: `{summary.get('unresolved_path_failure_count')}`",
        "",
        "## Trial Rows",
        "",
    ]
    for row in payload.get("rows", []):
        lines.append(
            f"- `{row.get('query_id')}` route=`{row.get('route')}` endpoint=`{row.get('api_endpoint_selected')}` "
            f"outcome=`{row.get('api_outcome')}` parser=`{row.get('parser_result')}` "
            f"usable_evidence=`{row.get('evidencebus_usable_evidence')}` answer_usage=`{row.get('answer_evidence_usage')}`"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
