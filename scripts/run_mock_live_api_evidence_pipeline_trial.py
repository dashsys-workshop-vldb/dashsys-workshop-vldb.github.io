#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.answer_intent import AnswerIntent
from dashagent.answer_slots import extract_answer_slots
from dashagent.answer_verifier import safe_rewrite, verify_answer
from dashagent.api_discovery import resolve_discovery_chain
from dashagent.api_response_parser import normalize_api_response
from dashagent.config import Config
from dashagent.endpoint_catalog import Endpoint, EndpointCatalog
from dashagent.evidence_bus import EvidenceBus
from dashagent.trajectory import redact_secrets


OUTPUT_STEM = "mock_live_api_evidence_pipeline_trial"
TRIAL_DIRNAME = "mock_live_api_evidence_pipeline_trial"
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "adobe_api_responses"
PROTECTED_OUTPUTS = [
    "eval_results_strict.json",
    "eval/",
    "final_submission/",
    "final_submission_manifest.json",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run mocked live Adobe API parser/EvidenceBus/answer-slot trial.")
    parser.add_argument("--limit", type=int, default=0, help="Optional endpoint limit; 0 means all endpoint fixture families.")
    parser.add_argument("--clean", action="store_true", help="Remove only outputs/mock_live_api_evidence_pipeline_trial before running.")
    args = parser.parse_args()
    config = Config.from_env(ROOT)
    payload = run_mock_live_api_evidence_pipeline_trial(config, limit=args.limit, clean=args.clean)
    print(json.dumps({"status": payload["status"], "report": str(config.outputs_dir / "reports" / f"{OUTPUT_STEM}.json")}, indent=2, sort_keys=True))
    return 0


def run_mock_live_api_evidence_pipeline_trial(
    config: Config | None = None,
    *,
    limit: int = 0,
    clean: bool = False,
) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    trial_root = config.outputs_dir / TRIAL_DIRNAME
    if clean and trial_root.exists():
        shutil.rmtree(trial_root)
    trial_root.mkdir(parents=True, exist_ok=True)

    catalog = EndpointCatalog(config)
    endpoints = [endpoint for endpoint in catalog.endpoints if (FIXTURE_ROOT / endpoint.id).exists()]
    if limit and limit > 0:
        endpoints = endpoints[:limit]

    rows: list[dict[str, Any]] = []
    discovery_rows: list[dict[str, Any]] = []
    for endpoint in endpoints:
        for case_name in ["normal", "empty", "error", "pagination", "nested", "malformed"]:
            fixture = FIXTURE_ROOT / endpoint.id / f"{case_name}.json"
            if not fixture.exists():
                continue
            row = _run_fixture_case(endpoint, case_name, fixture, trial_root)
            rows.append(row)
        discovery = _simulate_discovery(endpoint, catalog)
        if discovery:
            discovery_rows.append(discovery)

    payload = _build_payload(trial_root, rows, discovery_rows)
    _write_json_md(reports_dir / OUTPUT_STEM, payload, _render(payload))
    return payload


def _run_fixture_case(endpoint: Endpoint, case_name: str, fixture: Path, trial_root: Path) -> dict[str, Any]:
    fixture_text = fixture.read_text(encoding="utf-8")
    malformed = case_name == "malformed"
    if malformed:
        raw: Any = fixture_text
        ok = False
        error = "Synthetic malformed JSON fixture."
    else:
        raw = json.loads(fixture_text)
        ok = case_name != "error"
        error = "Synthetic API error fixture." if case_name == "error" else None
    parsed = normalize_api_response(
        raw,
        ok=ok,
        dry_run=False,
        status_code=200 if ok else 500,
        endpoint=endpoint.path,
        endpoint_id=endpoint.id,
        endpoint_family=endpoint.id,
        method=endpoint.method,
        path=endpoint.path,
        malformed_response=malformed,
        error=error,
    )
    payload = {
        "ok": parsed["ok"],
        "dry_run": False,
        "method": endpoint.method,
        "endpoint": endpoint.path,
        "parsed_evidence": parsed,
        "result_preview": parsed.get("raw_preview"),
        "error": "; ".join(parsed.get("errors", [])) if parsed.get("errors") else None,
    }
    tool_result = {"type": "api", "step": {"family": endpoint.id, "url": endpoint.path}, "payload": payload}
    bus = EvidenceBus()
    step = type("Step", (), {"family": endpoint.id})()
    bus.observe_api(step, payload)
    slots = extract_answer_slots(f"List live API evidence for {endpoint.id}.", [tool_result])
    answer = safe_rewrite(slots.query, slots, AnswerIntent.LIST, endpoint.id)
    verification = verify_answer(answer, slots)

    api_evidence_present = bool(parsed.get("live_evidence_available"))
    answer_slot_source = slots.answer_slot_source
    supported_field = _answer_contains_supported_field(answer, slots)
    unsupported_count = verification.unsupported_count
    if case_name == "normal":
        assert api_evidence_present is True
        assert answer_slot_source == "live_api"
        assert supported_field is True
        assert unsupported_count == 0
    if case_name == "empty":
        assert answer_slot_source == "live_api"
        assert parsed.get("evidence_state") == "live_empty"
        assert "credentials are unavailable" not in answer.lower()
        assert "no matching" in answer.lower()

    output_dir = trial_root / endpoint.id / case_name
    output_dir.mkdir(parents=True, exist_ok=True)
    row = redact_secrets(
        {
            "query_id": f"{endpoint.id}_{case_name}",
            "endpoint_id": endpoint.id,
            "endpoint_family": endpoint.id,
            "case": case_name,
            "fixture": str(fixture),
            "method": endpoint.method,
            "path": endpoint.path,
            "parser_success": bool(parsed.get("evidence_state")),
            "parser_mode": parsed.get("parser_mode"),
            "evidence_state": parsed.get("evidence_state"),
            "api_evidence_present": api_evidence_present,
            "evidencebus_forwarded": bool(
                bus.api_items
                or bus.api_ids
                or bus.api_names
                or bus.api_statuses
                or bus.api_errors
                or bus.api_evidence_states
            ),
            "evidencebus_payload_forwarded": bool(bus.api_items or bus.api_ids or bus.api_names or bus.api_statuses or bus.api_errors),
            "evidencebus_state_only_forwarded": bool(bus.api_evidence_states)
            and not bool(bus.api_items or bus.api_ids or bus.api_names or bus.api_statuses or bus.api_errors),
            "answer_slot_success": bool(slots.answer_slot_source),
            "answer_slot_source": answer_slot_source,
            "final_answer_contains_api_supported_field": supported_field,
            "unsupported_api_claim_count": unsupported_count,
            "empty_live_result_handled": case_name == "empty" and parsed.get("evidence_state") == "live_empty",
            "api_error_handled": case_name == "error" and parsed.get("evidence_state") == "api_error",
            "malformed_response_handled": case_name == "malformed" and parsed.get("evidence_state") == "malformed_response",
            "final_answer": answer,
            "parsed_evidence": parsed,
            "evidence_bus": bus.compact(),
            "answer_slots": slots.compact(),
            "verification": verification.compact(),
        }
    )
    (output_dir / "result.json").write_text(json.dumps(row, indent=2, sort_keys=True, default=str), encoding="utf-8")
    return row


def _simulate_discovery(endpoint: Endpoint, catalog: EndpointCatalog) -> dict[str, Any] | None:
    if not endpoint.path_params:
        return None
    source_decision = resolve_discovery_chain(endpoint, catalog=catalog)
    source_id = source_decision.discovery_source_endpoint
    if not source_id:
        return source_decision.to_dict()
    source_endpoint = catalog.by_id(source_id)
    if source_endpoint is None:
        return source_decision.to_dict()
    fixture = FIXTURE_ROOT / source_endpoint.id / "normal.json"
    if not fixture.exists():
        return source_decision.to_dict()
    raw = json.loads(fixture.read_text(encoding="utf-8"))
    parsed = normalize_api_response(
        raw,
        ok=True,
        dry_run=False,
        status_code=200,
        endpoint=source_endpoint.path,
        endpoint_id=source_endpoint.id,
        endpoint_family=source_endpoint.id,
        method=source_endpoint.method,
        path=source_endpoint.path,
    )
    return resolve_discovery_chain(
        endpoint,
        parsed_evidence=parsed,
        source_query_id_or_fixture=str(fixture),
        catalog=catalog,
    ).to_dict()


def _answer_contains_supported_field(answer: str, slots: Any) -> bool:
    answer_norm = answer.lower()
    for value in list(slots.entity_names) + list(slots.entity_ids) + list(slots.statuses):
        if str(value).lower() in answer_norm:
            return True
    if slots.api_item_count is not None and str(slots.api_item_count) in answer_norm:
        return True
    return not slots.live_api_evidence_available


def _build_payload(trial_root: Path, rows: list[dict[str, Any]], discovery_rows: list[dict[str, Any]]) -> dict[str, Any]:
    payload = {
        "report_type": OUTPUT_STEM,
        "status": "complete",
        "infrastructure_validation_only": True,
        "official_score_claim": False,
        "strict_score_computed": False,
        "protected_outputs_not_written": [f"outputs/{name}" for name in PROTECTED_OUTPUTS],
        "trial_output_root": str(trial_root),
        "total_mocked_live_cases": len(rows),
        "total_mocked_live_prompts": len(rows),
        "endpoint_families_covered": sorted({row["endpoint_family"] for row in rows}),
        "parser_success_count": sum(1 for row in rows if row.get("parser_success")),
        "evidencebus_forwarding_count": sum(1 for row in rows if row.get("evidencebus_forwarded")),
        "evidencebus_payload_forwarding_count": sum(1 for row in rows if row.get("evidencebus_payload_forwarded")),
        "evidencebus_state_only_forwarding_count": sum(1 for row in rows if row.get("evidencebus_state_only_forwarded")),
        "evidencebus_non_payload_forwarding_explanation": "State-only forwarding is expected for live-empty cases: EvidenceBus records evidence_state/count/pagination but has no item/name/id payload to forward.",
        "evidencebus_state_only_examples": [
            {
                "query_id": row["query_id"],
                "case": row.get("case"),
                "evidence_state": row.get("evidence_state"),
                "evidence_bus": row.get("evidence_bus"),
            }
            for row in rows
            if row.get("evidencebus_state_only_forwarded")
        ][:5],
        "answer_slot_success_count": sum(1 for row in rows if row.get("answer_slot_success")),
        "answer_used_api_evidence_count": sum(1 for row in rows if row.get("final_answer_contains_api_supported_field")),
        "unsupported_api_claim_count": sum(int(row.get("unsupported_api_claim_count") or 0) for row in rows),
        "empty_live_result_handling_count": sum(1 for row in rows if row.get("empty_live_result_handled")),
        "api_error_handling_count": sum(1 for row in rows if row.get("api_error_handled")),
        "malformed_response_handling_count": sum(1 for row in rows if row.get("malformed_response_handled")),
        "discovery_chain_simulated_count": sum(1 for row in discovery_rows if row.get("discovery_status") == "ready_with_discovered_id"),
        "discovery_rows": discovery_rows,
        "examples_of_parsed_evidence": [row for row in rows if row.get("api_evidence_present")][:5],
        "examples_of_final_answer_evidence_usage": [
            {
                "query_id": row["query_id"],
                "answer_slot_source": row.get("answer_slot_source"),
                "final_answer": row.get("final_answer"),
            }
            for row in rows
            if row.get("final_answer_contains_api_supported_field")
        ][:5],
        "remaining_gaps": _remaining_gaps(rows, discovery_rows),
        "recommendation": "mock_live_pipeline_ready_for_future_credentialed_smoke",
        "rows": rows,
    }
    return redact_secrets(payload)


def _remaining_gaps(rows: list[dict[str, Any]], discovery_rows: list[dict[str, Any]]) -> list[str]:
    gaps = []
    if any(not row.get("parser_success") for row in rows):
        gaps.append("parser_case_failure")
    if any(row.get("unsupported_api_claim_count") for row in rows):
        gaps.append("unsupported_api_claim")
    if any(row.get("discovery_status") not in {"ready_with_discovered_id", "not_required"} for row in discovery_rows):
        gaps.append("some_discovery_chains_blocked")
    return gaps


def _render(payload: dict[str, Any]) -> str:
    lines = [
        "# Mock Live API Evidence Pipeline Trial",
        "",
        "Infrastructure validation only; this report does not compute or claim official strict-score improvement.",
        "",
        f"- Status: `{payload['status']}`",
        f"- Mocked live cases: `{payload['total_mocked_live_cases']}`",
        f"- Endpoint families covered: `{len(payload['endpoint_families_covered'])}`",
        f"- Parser success count: `{payload['parser_success_count']}`",
        f"- EvidenceBus forwarding count: `{payload['evidencebus_forwarding_count']}`",
        f"- EvidenceBus payload forwarding count: `{payload['evidencebus_payload_forwarding_count']}`",
        f"- EvidenceBus state-only forwarding count: `{payload['evidencebus_state_only_forwarding_count']}`",
        f"- Answer slot success count: `{payload['answer_slot_success_count']}`",
        f"- Answer used API evidence count: `{payload['answer_used_api_evidence_count']}`",
        f"- Unsupported API claim count: `{payload['unsupported_api_claim_count']}`",
        f"- Empty live result handling count: `{payload['empty_live_result_handling_count']}`",
        f"- API error handling count: `{payload['api_error_handling_count']}`",
        f"- Malformed response handling count: `{payload['malformed_response_handling_count']}`",
        f"- Discovery-chain simulated count: `{payload['discovery_chain_simulated_count']}`",
        f"- Recommendation: `{payload['recommendation']}`",
        f"- EvidenceBus note: {payload['evidencebus_non_payload_forwarding_explanation']}",
        "",
        "## Endpoint Families Covered",
        "",
    ]
    lines.extend(f"- `{family}`" for family in payload["endpoint_families_covered"])
    lines.extend(["", "## Example Evidence Usage", ""])
    for example in payload.get("examples_of_final_answer_evidence_usage", []):
        lines.append(f"- `{example['query_id']}` source=`{example['answer_slot_source']}` answer={example['final_answer']}")
    return "\n".join(lines) + "\n"


def _write_json_md(stem: Path, payload: dict[str, Any], markdown: str) -> None:
    stem.with_suffix(".json").write_text(json.dumps(redact_secrets(payload), indent=2, sort_keys=True, default=str), encoding="utf-8")
    stem.with_suffix(".md").write_text(markdown, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
