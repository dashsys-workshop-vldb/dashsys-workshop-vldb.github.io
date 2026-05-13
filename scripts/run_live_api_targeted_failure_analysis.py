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
from dashagent.trajectory import redact_secrets
from scripts.load_local_env import load_local_env
from scripts.run_live_api_readiness_smoke import safe_error_excerpt


OUTPUT_STEM = "live_api_targeted_failure_analysis"


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
    rows = _smoke_rows(config) + _trial_rows(config)
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
    return payload


def _smoke_rows(config: Config) -> list[dict[str, Any]]:
    payload = _load_json(config.outputs_dir / "reports" / "live_api_readiness_smoke.json")
    rows = []
    for row in payload.get("endpoints_tested", []) or []:
        outcome = row.get("outcome") or classify_api_outcome(row, method=row.get("method"), path=row.get("path"))
        if outcome == "live_success":
            continue
        diagnosis = diagnose_api_outcome(row, method=row.get("method"), path=row.get("path"), outcome=outcome)
        rows.append(
            {
                "source_report": "live_api_readiness_smoke",
                "failure_type": outcome,
                "likely_failure_area": diagnosis["likely_failure_area"],
                "next_action": diagnosis["next_action"],
                "confidence": diagnosis["confidence"],
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
            rows.append(
                {
                    "source_report": "live_api_evidence_pipeline_trial",
                    "failure_type": outcome,
                    "likely_failure_area": diagnosis["likely_failure_area"],
                    "next_action": diagnosis["next_action"],
                    "confidence": diagnosis["confidence"],
                    "query_id": row.get("query_id"),
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
    return {
        "live_success_seen": has_live_success,
        "all_attempted_safe_gets_blocked_by_auth_scope_sandbox_or_service": all_blocked,
        "full_generated_prompt_suite_allowed": has_live_success or all_blocked,
        "live_strict_eval_allowed": has_live_success or all_blocked,
    }


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
        lines.append(f"- `{label}` failure=`{row.get('failure_type')}` next_action=`{row.get('next_action')}`")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
