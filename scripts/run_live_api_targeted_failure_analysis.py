#!/usr/bin/env python
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.adobe_env import adobe_env_readiness, format_adobe_readiness_for_report
from dashagent.api_outcome_classifier import classify_api_outcome, diagnose_api_outcome
from dashagent.config import Config
from dashagent.live_api_guard import evaluate_live_api_full_run_guard, safe_rerun_commands
from dashagent.trajectory import redact_secrets
from scripts.load_local_env import load_local_env
from scripts.run_live_api_readiness_smoke import safe_error_excerpt


OUTPUT_STEM = "live_api_targeted_failure_analysis"
ALLOWED_NEXT_ACTIONS = {
    "verify_permission",
    "verify_scope",
    "verify_sandbox",
    "fix_endpoint_path",
    "add_required_param",
    "wait_external_service",
    "no_code_fix",
    "rerun_with_endpoint_filter",
    "inspect_redacted_error_shape",
}


def main() -> int:
    load_local_env(ROOT)
    config = Config.from_env(ROOT)
    payload = run_live_api_targeted_failure_analysis(config)
    print(json.dumps({"report": str(config.outputs_dir / "reports" / f"{OUTPUT_STEM}.json"), "failure_rows": len(payload.get("rows", []))}, indent=2, sort_keys=True))
    return 0


def run_live_api_targeted_failure_analysis(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    path_diagnosis = _path_diagnosis_by_endpoint(config)
    rows = _smoke_rows(config, path_diagnosis) + _trial_rows(config)
    counts = Counter(row.get("failure_type", "no_clear_failure") for row in rows)
    gate = _full_diagnostics_gate(config)
    payload = redact_secrets(
        {
            "report_type": OUTPUT_STEM,
            "diagnostic_only": True,
            "official_score_claim": False,
            "uses_shared_api_outcome_classifier": True,
            "adobe_readiness": format_adobe_readiness_for_report(adobe_env_readiness()),
            "failure_type_counts": dict(counts),
            "full_diagnostics_gate": gate,
            "rows": rows,
            "recommendation": "fix_high_count_runtime_safe_failures_before_score_claims",
        }
    )
    (reports_dir / f"{OUTPUT_STEM}.json").write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    (reports_dir / f"{OUTPUT_STEM}.md").write_text(_render_md(payload), encoding="utf-8")
    _write_followup_reports(config, payload)
    return payload


def _smoke_rows(config: Config, path_diagnosis: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    payload = _load_json(config.outputs_dir / "reports" / "live_api_readiness_smoke.json")
    rows = []
    for row in payload.get("endpoints_tested", []) or []:
        outcome = row.get("outcome") or classify_api_outcome(row, method=row.get("method"), path=row.get("path"))
        if outcome == "live_success":
            continue
        diagnosis = diagnose_api_outcome(row, method=row.get("method"), path=row.get("path"), outcome=outcome)
        policy = _row_policy(outcome, diagnosis, path_diagnosis.get(str(row.get("endpoint_id") or "")))
        next_action = policy["next_action"]
        rows.append(
            {
                "source_report": "live_api_readiness_smoke",
                "evidence_source": policy["evidence_source"] or "smoke",
                "failure_type": outcome,
                "outcome": outcome,
                "likely_failure_area": diagnosis["likely_failure_area"],
                "next_action": next_action,
                "confidence": diagnosis["confidence"],
                "code_fix_allowed": policy["code_fix_allowed"],
                "reason_code": policy["reason_code"],
                "human_explanation": policy["human_explanation"],
                "endpoint_id": row.get("endpoint_id"),
                "method": row.get("method"),
                "path": row.get("path"),
                "status_code": row.get("status_code"),
                "safe_error_excerpt": row.get("safe_error_excerpt") or safe_error_excerpt(row),
                "root_cause": _root_cause(outcome, diagnosis["likely_failure_area"]),
                "runtime_safe_fix_candidate": _fix_candidate(outcome, diagnosis["likely_failure_area"]),
            }
        )
    return rows


def _trial_rows(config: Config) -> list[dict[str, Any]]:
    payload = _load_json(config.outputs_dir / "reports" / "live_api_evidence_pipeline_trial.json")
    rows = []
    for row in payload.get("rows", []) or []:
        outcomes = row.get("api_outcomes") or []
        for outcome in outcomes:
            if outcome == "live_success":
                continue
            diagnosis = diagnose_api_outcome({"error": row.get("final_answer_preview")}, outcome=outcome)
            policy = _row_policy(outcome, diagnosis, None, source="evidence_pipeline_trial")
            rows.append(
                {
                    "source_report": "live_api_evidence_pipeline_trial",
                    "evidence_source": "evidence_pipeline_trial",
                    "failure_type": outcome,
                    "outcome": outcome,
                    "likely_failure_area": diagnosis["likely_failure_area"],
                    "next_action": policy["next_action"],
                    "confidence": diagnosis["confidence"],
                    "code_fix_allowed": policy["code_fix_allowed"],
                    "reason_code": policy["reason_code"],
                    "human_explanation": policy["human_explanation"],
                    "query_id": row.get("query_id"),
                    "method": row.get("method"),
                    "path": row.get("path"),
                    "status_code": row.get("status_code"),
                    "safe_error_excerpt": safe_error_excerpt({"error": row.get("final_answer_preview")}),
                    "root_cause": _root_cause(outcome, diagnosis["likely_failure_area"]),
                    "runtime_safe_fix_candidate": _fix_candidate(outcome, diagnosis["likely_failure_area"]),
                }
            )
    return rows


def _full_diagnostics_gate(config: Config) -> dict[str, Any]:
    smoke = _load_json(config.outputs_dir / "reports" / "live_api_readiness_smoke.json")
    rows = smoke.get("endpoints_tested") or []
    outcomes = [row.get("outcome") or classify_api_outcome(row, method=row.get("method"), path=row.get("path")) for row in rows]
    has_live_success = any(outcome == "live_success" for outcome in outcomes)
    blocking = {"auth_error", "token_acquisition_failed", "scope_or_permission_issue", "sandbox_scope_issue", "external_api_unavailable"}
    all_blocked = bool(outcomes) and all(outcome in blocking for outcome in outcomes)
    guard = evaluate_live_api_full_run_guard(config, write_blocker=True, run_label="large_live_api_diagnostics")
    return {
        "live_success_seen": has_live_success,
        "all_attempted_safe_gets_blocked_by_auth_scope_sandbox_or_service": all_blocked,
        "full_generated_prompt_suite_allowed": bool(guard.get("allowed")),
        "live_strict_eval_allowed": bool(guard.get("allowed")),
        "guard_decision": guard.get("guard_decision"),
        "guard_reason": guard.get("reason"),
        "override_available_flag": guard.get("override_available_flag"),
    }


def _path_diagnosis_by_endpoint(config: Config) -> dict[str, dict[str, Any]]:
    payload = _load_json(config.outputs_dir / "reports" / "live_api_endpoint_path_diagnosis.json")
    return {
        str(row.get("endpoint_id")): row
        for row in payload.get("rows", []) or []
        if isinstance(row, dict) and row.get("endpoint_id")
    }


def _row_policy(
    outcome: str,
    diagnosis: dict[str, str],
    path_diagnosis: dict[str, Any] | None,
    *,
    source: str = "smoke",
) -> dict[str, Any]:
    likely = diagnosis.get("likely_failure_area", "no_code_fix")
    next_action = _allowed_next_action(diagnosis.get("next_action", "no_code_fix"))
    code_fix_allowed = False
    reason_code = "no_code_fix_supported"
    explanation = "The live API response does not currently support a safe code-side fix."
    evidence_source = source

    if outcome == "auth_error":
        reason_code = "adobe_permission_or_scope_setup"
        next_action = "verify_permission"
        explanation = "Adobe accepted token acquisition, but this endpoint returned an authorization failure. Verify product access, API key entitlement, and scopes outside the codebase."
    elif outcome == "scope_or_permission_issue":
        reason_code = "adobe_permission_or_scope_setup"
        next_action = "verify_scope"
        explanation = "The endpoint appears blocked by Adobe permission or scope setup. Do not change runtime behavior until access is verified externally."
    elif outcome == "sandbox_scope_issue":
        reason_code = "adobe_sandbox_or_environment_setup"
        next_action = "verify_sandbox"
        explanation = "The response points to sandbox, tenant, org, or environment scope. Verify the configured sandbox and Adobe project access externally."
    elif outcome == "endpoint_path_issue":
        evidence_source = "endpoint_path_diagnosis" if path_diagnosis else source
        if path_diagnosis and path_diagnosis.get("code_change_recommended"):
            code_fix_allowed = True
            reason_code = "safe_get_candidate_supports_path_fix"
            next_action = "fix_endpoint_path"
            explanation = "Endpoint path diagnosis found a safe GET candidate that supports a catalog path change."
        elif path_diagnosis:
            reason_code = "no_successful_safe_get_candidate"
            next_action = _allowed_next_action(path_diagnosis.get("recommended_action") or "no_code_fix")
            explanation = "Endpoint path diagnosis did not find a successful safe GET candidate, so the endpoint catalog should remain unchanged."
        else:
            reason_code = "endpoint_path_unverified"
            next_action = "rerun_with_endpoint_filter"
            explanation = "Run endpoint path diagnosis before considering an endpoint catalog change."
    elif outcome == "external_api_unavailable":
        reason_code = "adobe_service_or_server_issue"
        next_action = "wait_external_service"
        explanation = "The response looks like an Adobe service/server issue. Rerun later before changing code."
    elif likely == "required_param":
        code_fix_allowed = True
        reason_code = "safe_required_param_candidate"
        next_action = "add_required_param"
        explanation = "The redacted error shape indicates a missing required parameter; add one only if it is safe and general."
    elif likely == "parser_gap" or outcome == "malformed_response":
        code_fix_allowed = True
        reason_code = "parser_or_error_shape_gap"
        next_action = "inspect_redacted_error_shape"
        explanation = "The response shape may require parser hardening, but use only redacted payload evidence."
    elif outcome == "api_error":
        reason_code = "api_error_state_only"
        next_action = "inspect_redacted_error_shape"
        explanation = "The trial forwarded API error state only; no live payload evidence is available to support a runtime or catalog change."
    elif outcome in {"unresolved_path_param", "discovery_blocked_missing_id"}:
        reason_code = "discovery_needed_before_detail_call"
        next_action = "rerun_with_endpoint_filter"
        explanation = "Detail endpoints need safe GET discovery before they can be called."

    return {
        "code_fix_allowed": code_fix_allowed,
        "reason_code": reason_code,
        "next_action": _allowed_next_action(next_action),
        "human_explanation": explanation,
        "evidence_source": evidence_source,
    }


def _allowed_next_action(value: Any) -> str:
    text = str(value or "no_code_fix")
    return text if text in ALLOWED_NEXT_ACTIONS else "no_code_fix"


def _root_cause(outcome: str, likely_failure_area: str = "") -> str:
    if likely_failure_area == "required_param":
        return "endpoint_path_issue"
    if likely_failure_area == "parser_gap":
        return "parser_gap"
    mapping = {
        "auth_error": "credential_header_issue",
        "token_acquisition_failed": "credential_header_issue",
        "scope_or_permission_issue": "sandbox_scope_issue",
        "sandbox_scope_issue": "sandbox_scope_issue",
        "endpoint_path_issue": "endpoint_path_issue",
        "unresolved_path_param": "unresolved_path_param",
        "discovery_blocked_missing_id": "discovery_chain_gap",
        "rate_limited": "rate_limit_or_timeout",
        "malformed_response": "parser_gap",
        "external_api_unavailable": "external_api_unavailable",
        "live_empty": "no_clear_failure",
    }
    return mapping.get(outcome, "no_clear_failure")


def _fix_candidate(outcome: str, likely_failure_area: str = "") -> str:
    if likely_failure_area == "required_param":
        return "add safe required query parameter only if the API explicitly requires it"
    mapping = {
        "auth_error": "verify token scopes and credential freshness; no code promotion",
        "token_acquisition_failed": "fix token acquisition inputs before live endpoint smoke",
        "scope_or_permission_issue": "inspect Adobe product permissions and endpoint scopes",
        "sandbox_scope_issue": "verify sandbox header and org access",
        "endpoint_path_issue": "validate endpoint catalog path against live Adobe API",
        "unresolved_path_param": "add safe GET discovery chain before detail endpoint",
        "discovery_blocked_missing_id": "add discovery source or block detail endpoint",
        "rate_limited": "add conservative retry/backoff only after evidence",
        "malformed_response": "harden parser for real response content type/body",
        "external_api_unavailable": "record external outage; avoid runtime behavior changes",
        "live_empty": "ensure answer synthesis treats live empty as no matching records",
    }
    return mapping.get(outcome, "inspect evidence before changing runtime")


def _write_followup_reports(config: Config, analysis: dict[str, Any]) -> None:
    reports_dir = config.outputs_dir / "reports"
    rows = analysis.get("rows", []) or []
    followup = redact_secrets(_build_followup_commands_report(rows, analysis.get("full_diagnostics_gate", {})))
    blockers = redact_secrets(_build_external_blockers_report(rows, analysis.get("full_diagnostics_gate", {})))
    (reports_dir / "live_api_endpoint_followup_commands.json").write_text(
        json.dumps(followup, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    (reports_dir / "live_api_endpoint_followup_commands.md").write_text(_render_followup_md(followup), encoding="utf-8")
    (reports_dir / "live_api_external_blockers.json").write_text(
        json.dumps(blockers, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    (reports_dir / "live_api_external_blockers.md").write_text(_render_external_blockers_md(blockers), encoding="utf-8")


def _build_followup_commands_report(rows: list[dict[str, Any]], gate: dict[str, Any]) -> dict[str, Any]:
    endpoint_rows = [row for row in rows if row.get("endpoint_id")]
    grouped = {
        "auth_error": [row for row in endpoint_rows if row.get("outcome") in {"auth_error", "scope_or_permission_issue"}],
        "sandbox_scope_issue": [row for row in endpoint_rows if row.get("outcome") == "sandbox_scope_issue"],
        "endpoint_path_issue": [row for row in endpoint_rows if row.get("outcome") == "endpoint_path_issue"],
        "external_api_unavailable": [row for row in endpoint_rows if row.get("outcome") == "external_api_unavailable"],
    }
    commands: list[dict[str, Any]] = []
    for outcome, outcome_rows in grouped.items():
        for row in outcome_rows:
            endpoint_id = row.get("endpoint_id")
            commands.append(
                {
                    "endpoint_id": endpoint_id,
                    "outcome": outcome,
                    "command": f"python3 scripts/run_live_api_readiness_smoke.py --endpoint-id {endpoint_id}",
                    "action": row.get("next_action"),
                }
            )
    family_commands = [
        {
            "family": "flowservice",
            "command": "python3 scripts/run_live_api_readiness_smoke.py --endpoint-family flowservice",
            "action": "verify_sandbox",
        },
        {
            "family": "catalog",
            "command": "python3 scripts/run_live_api_readiness_smoke.py --endpoint-family catalog",
            "action": "no_code_fix",
        },
        {
            "family": "all_safe_get",
            "command": "python3 scripts/run_live_api_readiness_smoke.py --limit all-safe-get",
            "action": "rerun_with_endpoint_filter",
        },
        {
            "family": "endpoint_path_diagnosis",
            "command": "python3 scripts/run_live_api_endpoint_path_diagnosis.py",
            "action": "no_code_fix",
        },
    ]
    return {
        "report_type": "live_api_endpoint_followup_commands",
        "diagnostic_only": True,
        "official_score_claim": False,
        "full_live_run_guard": gate,
        "commands": commands,
        "family_commands": family_commands,
        "safe_rerun_commands": safe_rerun_commands(endpoint_rows),
    }


def _build_external_blockers_report(rows: list[dict[str, Any]], gate: dict[str, Any]) -> dict[str, Any]:
    endpoint_rows = [row for row in rows if row.get("endpoint_id")]
    groups = [
        _blocker_group(
            key="permission_scope",
            title="Likely Adobe permission/scope setup",
            rows=[row for row in endpoint_rows if row.get("outcome") in {"auth_error", "scope_or_permission_issue"}],
            verify="Verify Adobe product access, API key entitlement, and OAuth scopes for these endpoint families.",
            why="Token acquisition works, but the data endpoint rejects access. Changing runtime code would hide an Adobe access problem.",
        ),
        _blocker_group(
            key="sandbox_environment",
            title="Likely sandbox/environment setup",
            rows=[row for row in endpoint_rows if row.get("outcome") == "sandbox_scope_issue"],
            verify="Verify the sandbox name, org/project access, and whether the selected sandbox has these services enabled.",
            why="Responses point to sandbox, tenant, org, or environment scope. Runtime should not guess a different sandbox or org.",
        ),
        _blocker_group(
            key="unresolved_endpoint_path",
            title="Unresolved endpoint/path evidence with no proven code fix",
            rows=[row for row in endpoint_rows if row.get("outcome") == "endpoint_path_issue"],
            verify="Review endpoint path diagnosis and rerun focused smoke after external checks; do not change catalog paths without a successful safe GET candidate.",
            why="Endpoint path probes did not return a successful safe GET candidate, so a blind catalog edit would be speculative.",
        ),
        _blocker_group(
            key="service_server",
            title="Likely Adobe service/server issue",
            rows=[row for row in endpoint_rows if row.get("outcome") == "external_api_unavailable"],
            verify="Rerun later and check Adobe service status or request logs for the endpoint.",
            why="The response shape looks like a server/service failure rather than actionable local code evidence.",
        ),
    ]
    return {
        "report_type": "live_api_external_blockers",
        "diagnostic_only": True,
        "official_score_claim": False,
        "plain_language_summary": "Adobe credentials and token acquisition work, but live data endpoints have not returned usable payload evidence. Treat current blockers as external setup or unresolved endpoint evidence until at least one safe GET endpoint returns live_success.",
        "full_live_eval_blocked": not bool(gate.get("live_strict_eval_allowed")),
        "full_generated_prompt_suite_blocked": not bool(gate.get("full_generated_prompt_suite_allowed")),
        "full_live_run_guard": gate,
        "groups": groups,
    }


def _blocker_group(*, key: str, title: str, rows: list[dict[str, Any]], verify: str, why: str) -> dict[str, Any]:
    endpoints = [str(row.get("endpoint_id")) for row in rows if row.get("endpoint_id")]
    return {
        "key": key,
        "title": title,
        "affected_endpoints": endpoints,
        "why_code_should_not_blindly_change_runtime": why,
        "what_to_verify": verify,
        "rerun_commands": [f"python3 scripts/run_live_api_readiness_smoke.py --endpoint-id {endpoint}" for endpoint in endpoints],
        "blocked_full_live_runs": bool(endpoints),
    }


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _render_md(payload: dict[str, Any]) -> str:
    lines = [
        "# Live API Targeted Failure Analysis",
        "",
        "Diagnostic-only analysis using the shared API outcome classifier.",
        "",
        "## Failure Counts",
        "",
    ]
    for key, value in sorted((payload.get("failure_type_counts") or {}).items()):
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Next Actions", ""])
    for row in payload.get("rows", [])[:30]:
        label = row.get("endpoint_id") or row.get("query_id") or "unknown"
        lines.append(
            f"- `{label}` failure=`{row.get('failure_type')}` next_action=`{row.get('next_action')}` "
            f"code_fix_allowed=`{row.get('code_fix_allowed')}` reason=`{row.get('reason_code')}`"
        )
    return "\n".join(lines) + "\n"


def _render_followup_md(payload: dict[str, Any]) -> str:
    lines = [
        "# Live API Endpoint Follow-Up Commands",
        "",
        "Diagnostic-only safe rerun commands. No credentials are included.",
        "",
        "## Endpoint Commands",
        "",
    ]
    for item in payload.get("commands", []):
        lines.append(f"- `{item.get('command')}` - action: `{item.get('action')}`")
    lines.extend(["", "## Family Commands", ""])
    for item in payload.get("family_commands", []):
        lines.append(f"- `{item.get('command')}` - action: `{item.get('action')}`")
    return "\n".join(lines) + "\n"


def _render_external_blockers_md(payload: dict[str, Any]) -> str:
    lines = [
        "# Live API External Blockers",
        "",
        str(payload.get("plain_language_summary")),
        "",
        f"- Full live strict eval blocked: `{payload.get('full_live_eval_blocked')}`",
        f"- Full generated prompt suite blocked: `{payload.get('full_generated_prompt_suite_blocked')}`",
        "",
    ]
    for group in payload.get("groups", []):
        lines.extend(
            [
                f"## {group.get('title')}",
                "",
                f"- Affected endpoints: `{group.get('affected_endpoints')}`",
                f"- Why code should not blindly change runtime: {group.get('why_code_should_not_blindly_change_runtime')}",
                f"- What to verify: {group.get('what_to_verify')}",
                "",
                "Rerun commands:",
            ]
        )
        lines.extend(f"- `{command}`" for command in group.get("rerun_commands", []))
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
