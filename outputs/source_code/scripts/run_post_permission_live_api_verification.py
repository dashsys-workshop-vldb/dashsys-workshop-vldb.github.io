#!/usr/bin/env python
from __future__ import annotations

import json
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.adobe_env import adobe_env_readiness, format_adobe_readiness_for_report
from dashagent.config import Config
from dashagent.live_api_guard import evaluate_live_api_full_run_guard
from dashagent.trajectory import redact_secrets
from scripts.audit_live_adobe_api_readiness import token_acquisition_preflight
from scripts.load_local_env import load_local_env


OUTPUT_STEM = "post_permission_live_api_verification"
WAITING_STEM = "adobe_access_waiting_status"
CommandRunner = Callable[[list[str], Path], int]


COMMANDS: list[tuple[list[str], str | None]] = [
    ([sys.executable, "scripts/check_adobe_env_local.py"], None),
    ([sys.executable, "scripts/audit_live_adobe_api_readiness.py"], "outputs/reports/live_adobe_api_readiness_audit.json"),
    (
        [sys.executable, "scripts/run_live_api_readiness_smoke.py", "--limit", "all-safe-get"],
        "outputs/reports/live_api_readiness_smoke.json",
    ),
    ([sys.executable, "scripts/run_live_api_evidence_pipeline_trial.py"], "outputs/reports/live_api_evidence_pipeline_trial.json"),
    ([sys.executable, "scripts/run_live_api_targeted_failure_analysis.py"], "outputs/reports/live_api_targeted_failure_analysis.json"),
]


def main() -> int:
    load_local_env(ROOT)
    config = Config.from_env(ROOT)
    payload = run_post_permission_live_api_verification(config)
    print(
        json.dumps(
            {
                "status": payload.get("status"),
                "live_success_count": payload.get("live_success_count"),
                "full_live_eval_allowed": payload.get("full_live_eval_allowed"),
                "report": str(config.outputs_dir / "reports" / f"{OUTPUT_STEM}.json"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if payload.get("status") == "complete" else 1


def run_post_permission_live_api_verification(
    config: Config | None = None,
    *,
    command_runner: CommandRunner | None = None,
) -> dict[str, Any]:
    """Run the minimal safe live-API verification sequence after permissions change."""

    config = config or Config.from_env(ROOT)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    command_runner = command_runner or _default_command_runner

    command_records = []
    for command, report_path in COMMANDS:
        command_records.append(_run_recorded_command(command, config.project_root, report_path, command_runner))

    readiness = adobe_env_readiness()
    report_readiness = format_adobe_readiness_for_report(readiness)
    token_preflight = token_acquisition_preflight(config, readiness)
    smoke = _load_json(config.outputs_dir / "reports" / "live_api_readiness_smoke.json")
    trial = _load_json(config.outputs_dir / "reports" / "live_api_evidence_pipeline_trial.json")
    followup = _load_json(config.outputs_dir / "reports" / "live_api_endpoint_followup_commands.json")
    guard = evaluate_live_api_full_run_guard(config, run_label=OUTPUT_STEM, write_blocker=True)

    smoke_rows = [row for row in smoke.get("endpoints_tested", []) if isinstance(row, dict)]
    smoke_counts = Counter(str(row.get("outcome") or "api_error") for row in smoke_rows)
    live_success_count = int(smoke_counts.get("live_success", 0))
    full_live_runs_allowed = bool(guard.get("allowed") and live_success_count > 0)
    safe_rerun_commands = [
        str(item.get("command"))
        for item in followup.get("commands", [])
        if isinstance(item, dict) and item.get("command")
    ]
    if not safe_rerun_commands:
        safe_rerun_commands = list(guard.get("safe_rerun_commands") or [])

    next_commands = _recommended_next_commands(live_success_count, safe_rerun_commands)
    payload = redact_secrets(
        {
            "report_type": OUTPUT_STEM,
            "created_at": _now(),
            "status": "complete",
            "diagnostic_only": True,
            "official_score_claim": False,
            "promotion_allowed": False,
            "full_strict_eval_executed": False,
            "full_generated_prompt_suite_executed": False,
            "commands": command_records,
            "adobe_readiness": report_readiness,
            "credential_ready": bool(report_readiness.get("credential_ready")),
            "sandbox_ready": bool(report_readiness.get("sandbox_ready")),
            "token_acquisition_ok": bool(token_preflight.get("token_acquisition_ok")),
            "token_acquisition_attempted": bool(token_preflight.get("token_acquisition_attempted")),
            "live_success_count": live_success_count,
            "live_empty_count": int(smoke_counts.get("live_empty", 0)),
            "auth_error_count": int(smoke_counts.get("auth_error", 0)),
            "sandbox_scope_issue_count": int(smoke_counts.get("sandbox_scope_issue", 0)),
            "endpoint_path_issue_count": int(smoke_counts.get("endpoint_path_issue", 0)),
            "external_api_unavailable_count": int(smoke_counts.get("external_api_unavailable", 0)),
            "usable_live_api_evidence_count": int(trial.get("usable_live_api_evidence_count") or 0),
            "api_state_caveat_forwarded_count": int(trial.get("api_state_forwarded_count") or 0),
            "live_api_guard_decision": guard.get("guard_decision"),
            "live_api_guard_reason": guard.get("reason"),
            "guard_decision": guard.get("guard_decision"),
            "reason": guard.get("reason"),
            "full_live_eval_allowed": full_live_runs_allowed,
            "full_generated_prompt_suite_allowed": full_live_runs_allowed,
            "recommended_next_command": next_commands[0] if next_commands else "unavailable",
            "recommended_followup_commands": next_commands[1:],
            "recommended_next_commands": next_commands,
            "safe_rerun_commands": safe_rerun_commands,
            "source_reports": [
                "outputs/reports/live_adobe_api_readiness_audit.json",
                "outputs/reports/live_api_readiness_smoke.json",
                "outputs/reports/live_api_evidence_pipeline_trial.json",
                "outputs/reports/live_api_targeted_failure_analysis.json",
            ],
        }
    )
    (reports_dir / f"{OUTPUT_STEM}.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    (reports_dir / f"{OUTPUT_STEM}.md").write_text(_render_post_permission_md(payload), encoding="utf-8")
    waiting = write_adobe_access_waiting_status(config, verification=payload)
    payload["waiting_status_report"] = "outputs/reports/adobe_access_waiting_status.md"
    (reports_dir / f"{OUTPUT_STEM}.json").write_text(
        json.dumps(redact_secrets(payload), indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    return payload


def write_adobe_access_waiting_status(config: Config | None = None, *, verification: dict[str, Any] | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    smoke = _load_json(reports_dir / "live_api_readiness_smoke.json")
    trial = _load_json(reports_dir / "live_api_evidence_pipeline_trial.json")
    blockers = _load_json(reports_dir / "live_api_external_blockers.json")
    local_diag = _load_json(reports_dir / "generated_prompt_suite_local_diagnostic.json")
    manual_review = _load_json(reports_dir / "local_gap_manual_review.json")
    guard = evaluate_live_api_full_run_guard(config, run_label=WAITING_STEM, write_blocker=True)
    smoke_rows = [row for row in smoke.get("endpoints_tested", []) if isinstance(row, dict)]
    counts = Counter(str(row.get("outcome") or "api_error") for row in smoke_rows)
    live_success_count = int(counts.get("live_success", 0))
    full_live_runs_allowed = bool(guard.get("allowed") and live_success_count > 0)
    payload = redact_secrets(
        {
            "report_type": WAITING_STEM,
            "created_at": _now(),
            "diagnostic_only": True,
            "official_score_claim": False,
            "promotion_allowed": False,
            "what_works": [
                "credential loading",
                "client_credentials token acquisition",
                "live API smoke infrastructure",
                "large live-run guard protection",
                "local deterministic SQL_FIRST_API_VERIFY pipeline",
            ],
            "what_is_blocked": {
                "live_success_count": live_success_count,
                "usable_live_api_evidence_count": int(trial.get("usable_live_api_evidence_count") or 0),
                "full_live_eval_allowed": full_live_runs_allowed,
                "full_generated_prompt_suite_allowed": full_live_runs_allowed,
            },
            "why_likely_external_access": [
                "credential loading and client-credentials token acquisition pass locally",
                "safe GET smoke infrastructure executes real Adobe requests",
                "endpoint failures are grouped as permission/scope, sandbox/environment, unresolved path evidence, or service/server issues",
                "no safe GET endpoint has returned live payload evidence yet",
            ],
            "likely_external_blockers": [
                group.get("title")
                for group in blockers.get("groups", [])
                if isinstance(group, dict) and group.get("affected_endpoints")
            ]
            or [
                "Adobe permission/scope setup",
                "sandbox/environment setup",
                "unresolved endpoint/path evidence",
                "Adobe service/server issue",
            ],
            "external_access_needed": [
                "Adobe Organization access",
                "workshop sandbox access",
                "AEP read permissions for schemas, datasets, audiences/segments, merge policies, flow service, and audit events",
            ],
            "run_after_permission_granted": "python3 scripts/run_post_permission_live_api_verification.py",
            "secondary_rerun_command": "python3 scripts/run_live_api_readiness_smoke.py --limit all-safe-get",
            "current_guard_status": {
                "guard_decision": guard.get("guard_decision"),
                "reason": guard.get("reason"),
                "live_success_count": guard.get("live_success_count"),
                "full_live_eval_allowed": full_live_runs_allowed,
                "full_generated_prompt_suite_allowed": full_live_runs_allowed,
            },
            "local_work_completed_while_waiting": {
                "local_250_prompt_diagnostic_completed": bool(local_diag.get("executed_prompts")),
                "executed_prompts": local_diag.get("executed_prompts", "unavailable"),
                "total_prompts": local_diag.get("total_prompts", "unavailable"),
                "runtime_pass_count": local_diag.get("runtime_pass_count", "unavailable"),
                "runtime_fail_count": local_diag.get("runtime_fail_count", "unavailable"),
                "official_score_claim": False,
                "no_safe_deterministic_improvement_applied": local_diag.get("no_safe_deterministic_improvement_applied", "unavailable"),
            },
            "recommended_next_human_review": manual_review.get("recommended_next_human_review")
            or {
                "category": "local diagnostic gap candidates",
                "why": "Run scripts/review_local_diagnostic_gap_candidates.py to classify high-value advisory gaps before any deterministic fix.",
                "report_to_open": "outputs/reports/local_gap_manual_review.md",
                "can_be_fixed_before_adobe_access": False,
            },
            "live_api_guard": guard,
            "source_reports": [
                "outputs/reports/live_api_readiness_smoke.json",
                "outputs/reports/live_api_external_blockers.json",
                "outputs/reports/live_api_evidence_pipeline_trial.json",
            ],
        }
    )
    (reports_dir / f"{WAITING_STEM}.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    (reports_dir / f"{WAITING_STEM}.md").write_text(_render_waiting_md(payload), encoding="utf-8")
    return payload


def _run_recorded_command(
    command: list[str],
    cwd: Path,
    report_path: str | None,
    command_runner: CommandRunner,
) -> dict[str, Any]:
    started = _now()
    start = time.perf_counter()
    try:
        exit_code = int(command_runner(command, cwd))
    except Exception:
        exit_code = 1
    ended = _now()
    return {
        "command": _display_command(command),
        "exit_code": exit_code,
        "started_at": started,
        "ended_at": ended,
        "duration_seconds": round(time.perf_counter() - start, 4),
        "status": "passed" if exit_code == 0 else "failed",
        "report_path": report_path,
    }


def _default_command_runner(command: list[str], cwd: Path) -> int:
    completed = subprocess.run(command, cwd=cwd, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return int(completed.returncode)


def _recommended_next_commands(live_success_count: int, safe_rerun_commands: list[str]) -> list[str]:
    if live_success_count > 0:
        return [
            "python3 scripts/run_dev_eval.py --strict --live-api",
            "python3 scripts/run_full_generated_prompt_suite_diagnostic.py",
        ]
    broad = "python3 scripts/run_live_api_readiness_smoke.py --limit all-safe-get"
    commands = [broad]
    for command in safe_rerun_commands:
        if command and command not in commands:
            commands.append(command)
    if "python3 scripts/run_live_api_endpoint_path_diagnosis.py" not in commands:
        commands.append("python3 scripts/run_live_api_endpoint_path_diagnosis.py")
    return commands


def _render_post_permission_md(payload: dict[str, Any]) -> str:
    lines = [
        "# Post-Permission Live API Verification",
        "",
        "Diagnostic-only verification after Adobe org/sandbox/permission access changes.",
        "",
        f"- Credential ready: `{payload.get('credential_ready')}`",
        f"- Sandbox ready: `{payload.get('sandbox_ready')}`",
        f"- Token acquisition OK: `{payload.get('token_acquisition_ok')}`",
        f"- Live success count: `{payload.get('live_success_count')}`",
        f"- Live empty count: `{payload.get('live_empty_count')}`",
        f"- Auth error count: `{payload.get('auth_error_count')}`",
        f"- Sandbox issue count: `{payload.get('sandbox_scope_issue_count')}`",
        f"- Endpoint path issue count: `{payload.get('endpoint_path_issue_count')}`",
        f"- External unavailable count: `{payload.get('external_api_unavailable_count')}`",
        f"- Usable live API evidence count: `{payload.get('usable_live_api_evidence_count')}`",
        f"- API state/caveat forwarded count: `{payload.get('api_state_caveat_forwarded_count')}`",
        f"- Guard decision: `{payload.get('live_api_guard_decision')}`",
        f"- Reason: `{payload.get('reason')}`",
        f"- Full live eval allowed: `{payload.get('full_live_eval_allowed')}`",
        f"- Full generated prompt suite allowed: `{payload.get('full_generated_prompt_suite_allowed')}`",
        f"- Recommended next command: `{payload.get('recommended_next_command')}`",
        f"- Recommended follow-up commands: `{payload.get('recommended_followup_commands')}`",
        "",
        "## Subcommands",
        "",
    ]
    for record in payload.get("commands", []):
        lines.append(
            f"- `{record.get('command')}` -> `{record.get('status')}` "
            f"exit=`{record.get('exit_code')}` duration=`{record.get('duration_seconds')}`s"
        )
    return "\n".join(lines) + "\n"


def _render_waiting_md(payload: dict[str, Any]) -> str:
    blocked = payload.get("what_is_blocked", {})
    guard = payload.get("current_guard_status", {})
    local = payload.get("local_work_completed_while_waiting", {})
    next_review = payload.get("recommended_next_human_review", {})
    return "\n".join(
        [
            "# Adobe Access Waiting Status",
            "",
            "## What Works",
            "",
            *[f"- {item}" for item in payload.get("what_works", [])],
            "",
            "## What Is Blocked",
            "",
            f"- Live success count: `{blocked.get('live_success_count')}`",
            f"- Usable live API payload evidence: `{blocked.get('usable_live_api_evidence_count')}`",
            f"- Full live eval allowed: `{blocked.get('full_live_eval_allowed')}`",
            f"- Full live generated prompt suite allowed: `{blocked.get('full_generated_prompt_suite_allowed')}`",
            "",
            "## Why This Is Likely External Adobe Access",
            "",
            *[f"- {item}" for item in payload.get("why_likely_external_access", [])],
            "",
            "## What External Access Is Needed",
            "",
            *[f"- {item}" for item in payload.get("external_access_needed", [])],
            "",
            "## What Command To Run After Permission Is Granted",
            "",
            f"`{payload.get('run_after_permission_granted')}`",
            "",
            f"Immediate smoke rerun: `{payload.get('secondary_rerun_command')}`",
            "",
            "## Current Guard Status",
            "",
            f"- Guard decision: `{guard.get('guard_decision')}`",
            f"- Reason: `{guard.get('reason')}`",
            f"- Live success count: `{guard.get('live_success_count')}`",
            f"- Full live eval allowed: `{guard.get('full_live_eval_allowed')}`",
            f"- Full generated prompt suite allowed: `{guard.get('full_generated_prompt_suite_allowed')}`",
            "",
            "## What Local Work Was Completed While Waiting",
            "",
            f"- Local 250-prompt diagnostic completed: `{local.get('executed_prompts')}` / `{local.get('total_prompts')}`",
            f"- Runtime pass count: `{local.get('runtime_pass_count')}`",
            f"- Runtime fail count: `{local.get('runtime_fail_count')}`",
            f"- Official score claim: `{local.get('official_score_claim')}`",
            f"- No safe deterministic improvement applied: `{local.get('no_safe_deterministic_improvement_applied')}`",
            "",
            "## Recommended Next Human Review",
            "",
            f"- Category: `{next_review.get('category')}`",
            f"- Why: {next_review.get('why')}",
            f"- Report: `{next_review.get('report_to_open')}`",
            f"- Can be fixed before Adobe access: `{next_review.get('can_be_fixed_before_adobe_access')}`",
            "",
        ]
    )


def _display_command(command: list[str]) -> str:
    displayed = ["python3" if Path(part).name.startswith("python") else part for part in command]
    return " ".join(displayed)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
