from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .adobe_env import adobe_env_readiness
from .config import Config, DEFAULT_CONFIG
from .trajectory import redact_secrets


OVERRIDE_FLAG = "--allow-live-diagnostic-without-success"
BLOCKER_STEM = "live_api_full_run_blocker"


def evaluate_live_api_full_run_guard(
    config: Config | None = None,
    *,
    override: bool = False,
    live_mode_active: bool | None = None,
    run_label: str = "large_live_api_run",
    write_blocker: bool = True,
) -> dict[str, Any]:
    """Guard large live API diagnostics using structured smoke JSON only."""

    config = config or DEFAULT_CONFIG
    if live_mode_active is None:
        readiness = adobe_env_readiness()
        live_mode_active = bool(readiness.get("credential_ready"))

    smoke_path = config.outputs_dir / "reports" / "live_api_readiness_smoke.json"
    smoke_sha = _sha256_or_none(smoke_path)
    failure_counts: dict[str, int] = {}
    live_success_count = 0
    reason = "not_live_mode"
    smoke_rows: list[dict[str, Any]] = []

    if not live_mode_active:
        decision = _decision(
            allowed=True,
            guard_decision="allowed_not_live_mode",
            reason=reason,
            run_label=run_label,
            source_smoke_report=smoke_path,
            source_smoke_report_sha256=smoke_sha,
            live_success_count=0,
            failure_counts={},
            override=override,
        )
        return redact_secrets(decision)

    smoke_payload, load_error = _load_smoke_payload(smoke_path)
    if load_error:
        reason = "smoke_report_missing_or_stale"
    else:
        smoke_rows = [row for row in smoke_payload.get("endpoints_tested", []) if isinstance(row, dict)]
        if not smoke_rows:
            reason = "smoke_report_missing_or_stale"
        else:
            live_success_count = sum(1 for row in smoke_rows if row.get("outcome") == "live_success")
            failure_counts = dict(
                Counter(
                    str(row.get("outcome") or "api_error")
                    for row in smoke_rows
                    if row.get("outcome") != "live_success"
                )
            )
            reason = "live_success_available" if live_success_count > 0 else "no_live_success"

    allowed = live_success_count > 0 or bool(override)
    if reason == "smoke_report_missing_or_stale" and not override:
        allowed = False
    guard_decision = (
        "allowed_live_success"
        if live_success_count > 0
        else "allowed_diagnostic_override"
        if allowed and override
        else "blocked"
    )
    decision = _decision(
        allowed=allowed,
        guard_decision=guard_decision,
        reason="explicit_user_diagnostic_run_without_live_success" if allowed and override and live_success_count == 0 else reason,
        run_label=run_label,
        source_smoke_report=smoke_path,
        source_smoke_report_sha256=smoke_sha,
        live_success_count=live_success_count,
        failure_counts=failure_counts,
        override=override,
        smoke_rows=smoke_rows,
    )
    decision["diagnostic_only"] = bool(allowed and override and live_success_count == 0)
    decision["official_score_claim"] = False
    decision["promotion_allowed"] = False if decision["diagnostic_only"] else live_success_count > 0
    decision = redact_secrets(decision)
    if not allowed and write_blocker:
        write_live_api_full_run_blocker(config, decision)
    return decision


def write_live_api_full_run_blocker(config: Config, decision: dict[str, Any]) -> None:
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    payload = redact_secrets(
        {
            "report_type": BLOCKER_STEM,
            "created_at": decision.get("created_at"),
            "guard_decision": decision.get("guard_decision"),
            "reason": decision.get("reason"),
            "run_label": decision.get("run_label"),
            "source_smoke_report": decision.get("source_smoke_report"),
            "source_smoke_report_sha256": decision.get("source_smoke_report_sha256"),
            "live_success_count": decision.get("live_success_count"),
            "failure_counts": decision.get("failure_counts", {}),
            "override_available_flag": decision.get("override_available_flag", OVERRIDE_FLAG),
            "safe_rerun_commands": decision.get("safe_rerun_commands", []),
            "official_score_claim": False,
            "promotion_allowed": False,
        }
    )
    (reports_dir / f"{BLOCKER_STEM}.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    (reports_dir / f"{BLOCKER_STEM}.md").write_text(_render_blocker_md(payload), encoding="utf-8")


def guard_override_metadata(decision: dict[str, Any]) -> dict[str, Any]:
    return {
        "diagnostic_only": True,
        "official_score_claim": False,
        "promotion_allowed": False,
        "override_used": True,
        "override_method": "cli_flag",
        "reason": "explicit_user_diagnostic_run_without_live_success",
        "live_api_guard": decision,
    }


def _decision(
    *,
    allowed: bool,
    guard_decision: str,
    reason: str,
    run_label: str,
    source_smoke_report: Path,
    source_smoke_report_sha256: str | None,
    live_success_count: int,
    failure_counts: dict[str, int],
    override: bool,
    smoke_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "allowed": allowed,
        "guard_decision": guard_decision,
        "reason": reason,
        "run_label": run_label,
        "source_smoke_report": str(source_smoke_report),
        "source_smoke_report_sha256": source_smoke_report_sha256,
        "live_success_count": live_success_count,
        "failure_counts": failure_counts,
        "override_used": bool(override and allowed),
        "override_method": "cli_flag" if override and allowed else None,
        "override_available_flag": OVERRIDE_FLAG,
        "safe_rerun_commands": safe_rerun_commands(smoke_rows or []),
    }


def safe_rerun_commands(smoke_rows: list[dict[str, Any]]) -> list[str]:
    commands = ["python3 scripts/run_live_api_readiness_smoke.py --limit all-safe-get"]
    endpoint_ids = sorted({str(row.get("endpoint_id")) for row in smoke_rows if row.get("endpoint_id")})
    for endpoint_id in endpoint_ids[:20]:
        commands.append(f"python3 scripts/run_live_api_readiness_smoke.py --endpoint-id {endpoint_id}")
    families = sorted(_family_for_endpoint(str(endpoint_id)) for endpoint_id in endpoint_ids)
    for family in [family for family in families if family][:8]:
        command = f"python3 scripts/run_live_api_readiness_smoke.py --endpoint-family {family}"
        if command not in commands:
            commands.append(command)
    commands.append("python3 scripts/run_live_api_endpoint_path_diagnosis.py")
    return commands


def _family_for_endpoint(endpoint_id: str) -> str:
    if endpoint_id.startswith("flowservice"):
        return "flowservice"
    if endpoint_id.startswith("catalog"):
        return "catalog"
    if endpoint_id.startswith("schema") or endpoint_id == "schemas_short":
        return "schema"
    if endpoint_id.startswith("unified"):
        return "unified_tags"
    if "audience" in endpoint_id or "segment" in endpoint_id or "merge" in endpoint_id:
        return "ups"
    if endpoint_id.startswith("audit"):
        return "audit"
    if endpoint_id.startswith("journey"):
        return "journey"
    return endpoint_id


def _load_smoke_payload(path: Path) -> tuple[dict[str, Any], str | None]:
    if not path.exists():
        return {}, "missing"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}, "malformed"
    if not isinstance(payload, dict):
        return {}, "malformed"
    return payload, None


def _sha256_or_none(path: Path) -> str | None:
    if not path.exists():
        return None
    h = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                h.update(chunk)
    except OSError:
        return None
    return h.hexdigest()


def _render_blocker_md(payload: dict[str, Any]) -> str:
    lines = [
        "# Live API Full Run Blocker",
        "",
        "Large live API diagnostics are blocked until smoke evidence is trustworthy or an explicit diagnostic override is used.",
        "",
        f"- Created at: `{payload.get('created_at')}`",
        f"- Guard decision: `{payload.get('guard_decision')}`",
        f"- Reason: `{payload.get('reason')}`",
        f"- Live success count: `{payload.get('live_success_count')}`",
        f"- Failure counts: `{payload.get('failure_counts')}`",
        f"- Override flag: `{payload.get('override_available_flag')}`",
        "",
        "## Safe Rerun Commands",
        "",
    ]
    lines.extend(f"- `{command}`" for command in payload.get("safe_rerun_commands", []))
    return "\n".join(lines) + "\n"
