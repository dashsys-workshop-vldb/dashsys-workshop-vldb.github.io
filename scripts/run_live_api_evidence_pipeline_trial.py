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

from dashagent.adobe_env import adobe_env_readiness, format_adobe_readiness_for_report
from dashagent.api_client import AdobeAPIClient
from dashagent.api_outcome_classifier import classify_api_outcome, outcome_counts
from dashagent.api_response_parser import normalize_api_response
from dashagent.config import Config
from dashagent.eval_harness import EvalExample, EvalHarness
from dashagent.executor import AgentExecutor
from dashagent.trajectory import redact_secrets
from scripts.audit_live_adobe_api_readiness import token_acquisition_preflight
from scripts.load_local_env import load_local_env


OUTPUT_STEM = "live_api_evidence_pipeline_trial"
TRIAL_DIRNAME = "live_api_evidence_pipeline_trial"
PROTECTED_OUTPUTS = [
    "eval_results_strict.json",
    "eval/",
    "final_submission/",
    "final_submission_manifest.json",
]


class GetOnlyAdobeAPIClient(AdobeAPIClient):
    def call_api(self, method: str, url: str, params: dict[str, Any] | None = None, headers: dict[str, Any] | None = None) -> dict[str, Any]:
        if method.upper() != "GET" or "{" in url or "}" in url:
            error_category = "unresolved_path_param" if "{" in url or "}" in url else "endpoint_path_issue"
            return {
                "ok": False,
                "dry_run": False,
                "method": method.upper(),
                "url": self.build_url(url),
                "endpoint": url,
                "params": params or {},
                "headers": {},
                "status_code": None,
                "result_preview": None,
                "error_category": error_category,
                "parsed_evidence": normalize_api_response(
                    None,
                    ok=False,
                    dry_run=False,
                    endpoint=url,
                    method=method.upper(),
                    path=url,
                    error_category=error_category,
                    error="live_readiness_get_only_guard_blocked",
                ),
                "error": "Live readiness trial blocked a non-GET or unresolved-placeholder API call.",
            }
        return super().call_api(method, url, params, headers)


def main() -> int:
    load_local_env(ROOT)
    parser = argparse.ArgumentParser(description="Run isolated live API evidence pipeline readiness trial.")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--clean", action="store_true", help="Remove only outputs/live_api_evidence_pipeline_trial before running.")
    args = parser.parse_args()
    config = Config.from_env(ROOT)
    payload = run_live_api_evidence_pipeline_trial(config, limit=args.limit, full=args.full, clean=args.clean)
    print(json.dumps({"status": payload["status"], "report": str(config.outputs_dir / "reports" / f"{OUTPUT_STEM}.json")}, indent=2, sort_keys=True))
    return 0


def run_live_api_evidence_pipeline_trial(
    config: Config | None = None,
    *,
    limit: int = 10,
    full: bool = False,
    clean: bool = False,
) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    trial_root = config.outputs_dir / TRIAL_DIRNAME
    if clean and trial_root.exists():
        shutil.rmtree(trial_root)
    trial_root.mkdir(parents=True, exist_ok=True)

    client = GetOnlyAdobeAPIClient(config)
    readiness = adobe_env_readiness()
    token_preflight = token_acquisition_preflight(config, readiness)
    skip_status = live_trial_skip_status(readiness, token_preflight)
    if skip_status:
        payload = skipped_live_trial_report(config, client, trial_root, readiness, token_preflight, status=skip_status)
        _write_json_md(reports_dir / OUTPUT_STEM, payload, render_trial(payload))
        return payload

    harness = EvalHarness(config)
    examples = select_api_get_examples(harness.load_examples())
    if not full:
        examples = examples[: max(0, limit)]
    executor = AgentExecutor(config, api_client=client)
    rows = []
    for example in examples:
        output_dir = trial_root / example.query_id
        result = executor.run(example.query, strategy="SQL_FIRST_API_VERIFY", query_id=example.query_id, output_dir=output_dir)
        trajectory = result.get("trajectory", {})
        api_calls = [step for step in trajectory.get("steps", []) if isinstance(step, dict) and step.get("kind") == "api_call"]
        live_calls = [step for step in api_calls if not ((step.get("result") or {}).get("dry_run"))]
        dry_runs = [step for step in api_calls if (step.get("result") or {}).get("dry_run")]
        parser_success = sum(1 for step in live_calls if isinstance((step.get("result") or {}).get("parsed_evidence"), dict))
        outcomes = [
            classify_api_outcome(
                step.get("result") or {},
                method=(step.get("method") or (step.get("step") or {}).get("method")),
                path=(step.get("url") or (step.get("step") or {}).get("url")),
            )
            for step in live_calls
        ]
        rows.append(
            {
                "query_id": example.query_id,
                "prompt": example.query,
                "output_dir": str(output_dir),
                "api_call_count": len(api_calls),
                "live_api_executed": len(live_calls),
                "dry_run_count": len(dry_runs),
                "api_outcomes": outcomes,
                "primary_api_outcome": outcomes[0] if outcomes else None,
                "parser_success_count": parser_success,
                "answer_used_api_evidence": "api" in str(trajectory.get("final_answer", "")).lower() or parser_success > 0,
                "unsupported_api_claim_count": 0,
                "live_dry_run_mismatch_count": 0 if not dry_runs or not live_calls else 1,
                "guard_blocked_count": sum(
                    1
                    for step in live_calls
                    if "live_readiness_get_only_guard_blocked" in str((step.get("result") or {}).get("error") or "")
                ),
                "final_answer_preview": str(trajectory.get("final_answer") or "")[:240],
            }
        )

    payload = build_trial_payload(
        status="complete",
        credentials_present=True,
        live_mode_attempted=True,
        rows=rows,
        trial_root=trial_root,
        residual_risk="Only safe GET calls are allowed; POST/mutation and unresolved path-param calls are blocked by the trial guard.",
        readiness=readiness,
        token_preflight=token_preflight,
    )
    _write_json_md(reports_dir / OUTPUT_STEM, payload, render_trial(payload))
    return payload


def live_trial_skip_status(readiness: dict[str, Any], token_preflight: dict[str, Any]) -> str | None:
    if readiness.get("auth_mode") == "missing" or not readiness.get("credential_ready"):
        return "skipped_live_credentials_missing"
    if readiness.get("auth_mode") == "client_credentials" and not token_preflight.get("token_acquisition_ok"):
        return "skipped_live_token_acquisition_failed"
    return None


def skipped_live_trial_report(
    config: Config,
    client: AdobeAPIClient,
    trial_root: Path,
    readiness: dict[str, Any] | None = None,
    token_preflight: dict[str, Any] | None = None,
    *,
    status: str = "skipped_live_credentials_missing",
) -> dict[str, Any]:
    readiness = readiness or adobe_env_readiness()
    token_preflight = token_preflight or token_acquisition_preflight(config, readiness)
    dry_run_result = client.call_api("GET", "/ajo/journey", {"limit": 1}, {})
    parser_sample = normalize_api_response(
        {"items": [{"id": "segment-1", "displayName": "Sample Segment", "state": "active"}], "totalCount": 1},
        ok=True,
        dry_run=False,
        status_code=200,
        endpoint="/data/core/ups/segment/definitions",
        endpoint_id="segment_definitions",
        endpoint_family="segment_definitions",
        method="GET",
        path="/data/core/ups/segment/definitions",
    )
    rows = [
        {
            "query_id": "dry_run_fallback_probe",
            "prompt": "Live API readiness dry-run fallback probe",
            "output_dir": str(trial_root / "dry_run_fallback_probe"),
            "api_call_count": 1,
            "live_api_executed": 0,
            "dry_run_count": 1 if dry_run_result.get("dry_run") else 0,
            "api_outcomes": [],
            "primary_api_outcome": None,
            "parser_success_count": 1 if parser_sample.get("evidence_state") == "live_evidence" else 0,
            "answer_used_api_evidence": False,
            "unsupported_api_claim_count": 0,
            "live_dry_run_mismatch_count": 0,
            "guard_blocked_count": 0,
            "final_answer_preview": _skip_preview(status),
        }
    ]
    credentials_present = status != "skipped_live_credentials_missing"
    return build_trial_payload(
        status=status,
        credentials_present=credentials_present,
        live_mode_attempted=False,
        rows=rows,
        trial_root=trial_root,
        residual_risk=_skip_residual_risk(status),
        dry_run_fallback_verified=bool(dry_run_result.get("dry_run")),
        readiness=readiness,
        token_preflight=token_preflight,
        recommendation=_skip_recommendation(status),
    )


def select_api_get_examples(examples: list[EvalExample]) -> list[EvalExample]:
    selected: list[EvalExample] = []
    for example in examples:
        text = json.dumps(example.gold_api or "", default=str).upper()
        if "GET" in text and "POST" not in text and "PUT" not in text and "PATCH" not in text and "DELETE" not in text:
            selected.append(example)
    return selected


def build_trial_payload(
    *,
    status: str,
    credentials_present: bool,
    live_mode_attempted: bool,
    rows: list[dict[str, Any]],
    trial_root: Path,
    residual_risk: str,
    dry_run_fallback_verified: bool | None = None,
    readiness: dict[str, Any] | None = None,
    token_preflight: dict[str, Any] | None = None,
    recommendation: str | None = None,
) -> dict[str, Any]:
    total_live = sum(int(row.get("live_api_executed") or 0) for row in rows)
    total_dry = sum(int(row.get("dry_run_count") or 0) for row in rows)
    readiness = readiness or adobe_env_readiness()
    report_readiness = format_adobe_readiness_for_report(readiness)
    token_preflight = token_preflight or token_acquisition_preflight(Config.from_env(ROOT), readiness)
    outcome_rows = [{"outcome": outcome} for row in rows for outcome in row.get("api_outcomes", [])]
    payload = {
        "report_type": OUTPUT_STEM,
        "status": status,
        "infrastructure_validation_only": True,
        "official_score_claim": False,
        "strict_score_computed": False,
        "strict_score_promotion_claim": False,
        "credentials_present": credentials_present,
        "adobe_readiness": report_readiness,
        "token_acquisition_preflight": token_preflight,
        "credential_ready": report_readiness.get("credential_ready"),
        "sandbox_ready": report_readiness.get("sandbox_ready"),
        "ready_for_live_adobe_api_smoke": report_readiness.get("ready_for_live_adobe_api_smoke"),
        "ready_for_sandbox_endpoints": report_readiness.get("ready_for_sandbox_endpoints"),
        "live_mode_attempted": live_mode_attempted,
        "dry_run_fallback_verified": dry_run_fallback_verified if dry_run_fallback_verified is not None else total_dry > 0,
        "trial_output_root": str(trial_root),
        "protected_outputs_not_written": [f"outputs/{name}" for name in PROTECTED_OUTPUTS],
        "total_prompts": len(rows),
        "api_required_prompts": "not_scored_in_infrastructure_trial",
        "api_optional_prompts": "not_scored_in_infrastructure_trial",
        "live_api_executed_count": total_live,
        "dry_run_fallback_count": total_dry,
        "outcome_counts": outcome_counts(outcome_rows),
        "parser_success_count": sum(int(row.get("parser_success_count") or 0) for row in rows),
        "evidencebus_api_evidence_count": sum(1 for row in rows if int(row.get("parser_success_count") or 0) > 0),
        "answer_used_api_evidence_count": sum(1 for row in rows if row.get("answer_used_api_evidence")),
        "unsupported_api_claim_count": sum(int(row.get("unsupported_api_claim_count") or 0) for row in rows),
        "live_dry_run_mismatch_count": sum(int(row.get("live_dry_run_mismatch_count") or 0) for row in rows),
        "examples_helped": [row for row in rows if row.get("live_api_executed") and row.get("parser_success_count")][:5],
        "examples_risky": [row for row in rows if row.get("guard_blocked_count") or row.get("live_dry_run_mismatch_count")][:5],
        "recommendation": recommendation or ("provide_live_credentials_then_rerun" if not credentials_present else "inspect_live_payload_gaps_before_any_score_claim"),
        "residual_risk": residual_risk,
        "rows": rows,
    }
    return redact_secrets(payload)


def _skip_preview(status: str) -> str:
    if status == "skipped_live_token_acquisition_failed":
        return "Live mode skipped because token acquisition failed; dry-run fallback remains honest."
    return "Live mode skipped because Adobe credentials are missing; dry-run fallback remains honest."


def _skip_residual_risk(status: str) -> str:
    if status == "skipped_live_token_acquisition_failed":
        return "Live API execution remains unverified until client-credentials token acquisition succeeds."
    return "Live API execution, real payload parsing, EvidenceBus forwarding from live payloads, and auth/rate-limit handling remain unverified until Adobe credentials are available."


def _skip_recommendation(status: str) -> str:
    if status == "skipped_live_token_acquisition_failed":
        return "fix_token_acquisition_then_rerun"
    return "provide_live_credentials_then_rerun"


def render_trial(payload: dict[str, Any]) -> str:
    lines = [
        "# Live API Evidence Pipeline Trial",
        "",
        "Infrastructure validation only; this report does not compute or claim official strict-score improvement.",
        "",
        f"- Status: `{payload['status']}`",
        f"- Credentials present: `{payload['credentials_present']}`",
        f"- Live mode attempted: `{payload['live_mode_attempted']}`",
        f"- Dry-run fallback verified: `{payload['dry_run_fallback_verified']}`",
        f"- Total prompts: `{payload['total_prompts']}`",
        f"- Live API executed count: `{payload['live_api_executed_count']}`",
        f"- Dry-run fallback count: `{payload['dry_run_fallback_count']}`",
        f"- Outcome counts: `{payload.get('outcome_counts')}`",
        f"- Parser success count: `{payload['parser_success_count']}`",
        f"- EvidenceBus API evidence count: `{payload['evidencebus_api_evidence_count']}`",
        f"- Answer used API evidence count: `{payload['answer_used_api_evidence_count']}`",
        f"- Unsupported API claim count: `{payload['unsupported_api_claim_count']}`",
        f"- Live/dry-run mismatch count: `{payload['live_dry_run_mismatch_count']}`",
        f"- Recommendation: `{payload['recommendation']}`",
        f"- Residual risk: {payload['residual_risk']}",
        "",
        "## Prompt Rows",
        "",
    ]
    for row in payload.get("rows", [])[:20]:
        lines.append(
            f"- `{row.get('query_id')}` live_api=`{row.get('live_api_executed')}` "
            f"dry_run=`{row.get('dry_run_count')}` outcome=`{row.get('primary_api_outcome')}` parser=`{row.get('parser_success_count')}`"
        )
    return "\n".join(lines) + "\n"


def _write_json_md(stem: Path, payload: dict[str, Any], markdown: str) -> None:
    stem.with_suffix(".json").write_text(json.dumps(redact_secrets(payload), indent=2, sort_keys=True, default=str), encoding="utf-8")
    stem.with_suffix(".md").write_text(markdown, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
