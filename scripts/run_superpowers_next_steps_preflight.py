#!/usr/bin/env python
from __future__ import annotations

import fnmatch
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.trajectory import redact_secrets


OUTPUT_STEM = "superpowers_next_steps_preflight"
GIT_STATUS_TIMEOUT_SECONDS = 5

PROTECTED_ARTIFACTS = [
    "outputs/final_submission/**",
    "outputs/eval_results_strict.json",
    "outputs/hidden_style_eval.*",
    "outputs/final_submission_manifest.json",
    "final_submission_manifest.json",
    "dashagent/endpoint_catalog.py",
    "dashagent/config.py",
    "scripts/package_query_outputs.py",
    "scripts/run_dev_eval.py",
]

PACKAGED_DEFAULT_FILES = [
    "dashagent/config.py",
    "scripts/package_query_outputs.py",
    "scripts/run_dev_eval.py",
]


def main() -> int:
    config = Config.from_env(ROOT)
    payload = run_superpowers_next_steps_preflight(config)
    print(
        json.dumps(
            {
                "status": payload.get("status"),
                "blocker": payload.get("blocker"),
                "report": str(config.outputs_dir / "reports" / f"{OUTPUT_STEM}.json"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 1 if payload.get("blocker") else 0


def run_superpowers_next_steps_preflight(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    git_status = collect_git_status(config.project_root)
    protected_findings = find_protected_findings(git_status)
    sources = load_sources(config)
    payload = redact_secrets(
        {
            "report_type": OUTPUT_STEM,
            "created_at": now(),
            "status": "blocked" if protected_findings else "complete",
            "blocker": bool(protected_findings),
            "blocker_reason": "protected_artifact_change_detected" if protected_findings else None,
            "git_status": git_status,
            "protected_artifacts": PROTECTED_ARTIFACTS,
            "packaged_default_files": PACKAGED_DEFAULT_FILES,
            "protected_findings": protected_findings,
            "current_packaged_strategy": sources["system_summary"].get("preferred_strategy")
            or sources["final_submission_manifest"].get("preferred_strategy")
            or "unavailable",
            "current_strict_score": sources["system_summary"].get("packaged_strict_score")
            or sources["eval_results_strict"].get("final_score")
            or sources["eval_results_strict"].get("score")
            or "unavailable",
            "hidden_style_status": sources["system_summary"].get("hidden_style")
            or _hidden_style_status(sources["hidden_style"]),
            "final_submission_ready": sources["system_summary"].get("final_submission_ready")
            if sources["system_summary"].get("final_submission_ready") is not None
            else bool(sources["final_submission_manifest"].get("no_secret_scan", {}).get("ok")),
            "live_success_count": _live_success_count(sources["live_api_smoke"], sources["live_api_full_run_blocker"]),
            "local_diagnostic_status": {
                "diagnostic_only": sources["generated_prompt_suite_local_diagnostic"].get("diagnostic_only"),
                "total_prompts": sources["generated_prompt_suite_local_diagnostic"].get("total_prompts"),
                "executed_prompts": sources["generated_prompt_suite_local_diagnostic"].get("executed_prompts"),
                "runtime_pass_count": sources["generated_prompt_suite_local_diagnostic"].get("runtime_pass_count"),
                "runtime_fail_count": sources["generated_prompt_suite_local_diagnostic"].get("runtime_fail_count"),
                "validation_fail_count": sources["generated_prompt_suite_local_diagnostic"].get("validation_fail_count"),
                "no_safe_deterministic_improvement_applied": sources[
                    "generated_prompt_suite_local_diagnostic"
                ].get("no_safe_deterministic_improvement_applied"),
            },
            "runtime_changes_allowed": False,
            "runtime_change_policy": (
                "Runtime changes are blocked by default. A later phase may apply at most one deterministic fix only "
                "after manual review finds exactly one low-risk implementation-ready candidate and mandatory validation passes."
            ),
            "candidate_categories_to_inspect": [
                "zero_row_sql / dataflow_run",
                "missing_count_or_name_advisory / segment_audience",
                "answer_intent_mismatch / segment_audience",
                "domain_mismatch / dataflow_run",
                "route_mismatch / destination_flow",
            ],
            "no_change_safety_rule": (
                "Do not modify packaged defaults, endpoint catalog paths, validators, strict/hidden artifacts, or final submission "
                "unless the gated fix decision explicitly allows it."
            ),
            "source_reports": [
                "outputs/reports/system_summary.json",
                "outputs/reports/generated_prompt_suite_local_diagnostic.json",
                "outputs/reports/generated_prompt_local_gap_samples.json",
                "outputs/reports/local_deterministic_improvement_candidates.json",
                "outputs/reports/adobe_access_waiting_status.json",
                "outputs/reports/post_permission_live_api_verification.json",
                "outputs/reports/live_api_full_run_blocker.json",
                "outputs/reports/report_index.json",
            ],
        }
    )

    (reports_dir / f"{OUTPUT_STEM}.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    (reports_dir / f"{OUTPUT_STEM}.md").write_text(render_md(payload), encoding="utf-8")
    return payload


def collect_git_status(root: Path) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            ["git", "status", "--short"],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            timeout=GIT_STATUS_TIMEOUT_SECONDS,
        )
        lines = [line for line in completed.stdout.splitlines() if line.strip()]
        return {
            "mode": "git_status_short",
            "timeout_seconds": GIT_STATUS_TIMEOUT_SECONDS,
            "exit_code": completed.returncode,
            "timed_out": False,
            "line_count": len(lines),
            "lines": lines[:200],
        }
    except subprocess.TimeoutExpired:
        fallback_lines = _git_status_fallback(root)
        return {
            "mode": "fallback_diff_and_untracked",
            "timeout_seconds": GIT_STATUS_TIMEOUT_SECONDS,
            "exit_code": None,
            "timed_out": True,
            "line_count": len(fallback_lines),
            "lines": fallback_lines[:200],
        }


def _git_status_fallback(root: Path) -> list[str]:
    commands = [
        ["git", "diff", "--name-status", "--", "README.md", "AGENTS.md", "scripts", "dashagent", "tests", "outputs/reports"],
        ["git", "ls-files", "--deleted", "--", *PROTECTED_ARTIFACTS],
        ["git", "ls-files", "--others", "--exclude-standard", "--", "scripts", "tests", "outputs/reports"],
    ]
    lines: list[str] = []
    for command in commands:
        try:
            completed = subprocess.run(command, cwd=root, check=False, capture_output=True, text=True, timeout=3)
            lines.extend(line for line in completed.stdout.splitlines() if line.strip())
        except subprocess.TimeoutExpired:
            lines.append(f"fallback_timeout: {' '.join(command)}")
    return lines


def find_protected_findings(git_status: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    for line in git_status.get("lines", []):
        status, path = parse_status_line(str(line))
        if not path:
            continue
        matched = protected_pattern(path)
        if not matched:
            continue
        deletion = "D" in status
        findings.append(
            {
                "status": status,
                "path": path,
                "matched_protection": matched,
                "reason": "protected_deletion" if deletion else "protected_artifact_or_default_change",
            }
        )
    return findings


def parse_status_line(line: str) -> tuple[str, str]:
    if "\t" in line:
        status, path = line.split("\t", 1)
        return status.strip(), path.strip()
    if len(line) >= 4:
        return line[:2].strip(), line[3:].strip()
    return "", line.strip()


def protected_pattern(path: str) -> str | None:
    normalized = path.strip()
    for pattern in PROTECTED_ARTIFACTS:
        if fnmatch.fnmatch(normalized, pattern):
            return pattern
    return None


def load_sources(config: Config) -> dict[str, Any]:
    outputs = config.outputs_dir
    reports = outputs / "reports"
    return {
        "system_summary": load_json(reports / "system_summary.json"),
        "eval_results_strict": load_json(outputs / "eval_results_strict.json"),
        "hidden_style": load_json(outputs / "hidden_style_eval.json"),
        "final_submission_manifest": load_json(outputs / "final_submission_manifest.json"),
        "live_api_smoke": load_json(reports / "live_api_readiness_smoke.json"),
        "live_api_full_run_blocker": load_json(reports / "live_api_full_run_blocker.json"),
        "generated_prompt_suite_local_diagnostic": load_json(reports / "generated_prompt_suite_local_diagnostic.json"),
    }


def _hidden_style_status(payload: dict[str, Any]) -> dict[str, Any] | str:
    if not payload:
        return "unavailable"
    passed = payload.get("passed") or payload.get("pass_count") or payload.get("passed_count")
    total = payload.get("total") or payload.get("total_count")
    if passed is not None and total is not None:
        return {"label": f"{passed}/{total}", "passed": passed, "total": total}
    return payload.get("status", "unavailable")


def _live_success_count(smoke: dict[str, Any], blocker: dict[str, Any]) -> int | str:
    if blocker.get("live_success_count") is not None:
        return int(blocker.get("live_success_count") or 0)
    rows = smoke.get("endpoints_tested") or smoke.get("rows") or []
    if isinstance(rows, list):
        return sum(1 for row in rows if isinstance(row, dict) and row.get("outcome") == "live_success")
    return "unavailable"


def render_md(payload: dict[str, Any]) -> str:
    local = payload.get("local_diagnostic_status", {})
    lines = [
        "# Superpowers Next Steps Preflight",
        "",
        "Disciplined preflight before manual local diagnostic review. This report does not change runtime behavior.",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Blocker: `{payload.get('blocker')}`",
        f"- Packaged strategy: `{payload.get('current_packaged_strategy')}`",
        f"- Strict score: `{payload.get('current_strict_score')}`",
        f"- Hidden-style: `{payload.get('hidden_style_status')}`",
        f"- Final submission ready: `{payload.get('final_submission_ready')}`",
        f"- Live success count: `{payload.get('live_success_count')}`",
        f"- Local diagnostic: `{local.get('runtime_pass_count')}` pass / `{local.get('runtime_fail_count')}` fail",
        f"- Runtime changes allowed now: `{payload.get('runtime_changes_allowed')}`",
        "",
        "## Protected Artifacts",
        "",
    ]
    lines.extend(f"- `{item}`" for item in payload.get("protected_artifacts", []))
    lines.extend(["", "## Candidate Categories To Inspect", ""])
    lines.extend(f"- {item}" for item in payload.get("candidate_categories_to_inspect", []))
    lines.extend(["", "## No-Change Safety Rule", "", str(payload.get("no_change_safety_rule")), ""])
    findings = payload.get("protected_findings") or []
    if findings:
        lines.extend(["## Blocker Findings", ""])
        for finding in findings:
            lines.append(f"- `{finding.get('status')}` `{finding.get('path')}`: {finding.get('reason')}")
        lines.append("")
    return "\n".join(lines)


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
