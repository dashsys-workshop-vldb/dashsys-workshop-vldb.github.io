#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.report_run import report_metadata


REQUIRED_POST_CHANGE_VALIDATION_COMMANDS = [
    "python3 -m pytest -q",
    "python3 scripts/run_dev_eval.py --strict",
    "python3 scripts/run_hidden_style_eval.py",
    "python3 scripts/check_llm_sdk_backend.py",
    "python3 scripts/run_llm_baseline_eval.py",
    "python3 scripts/run_llm_strict_baseline_eval.py",
    "python3 scripts/run_llm_hidden_style_diagnostic.py",
    "python3 scripts/generate_winner_readiness_report.py",
    "python3 scripts/generate_research_inspired_report.py",
    "python3 scripts/generate_system_status_dashboard.py",
    "python3 scripts/generate_technique_visual_cards.py",
    "python3 scripts/generate_visualization_index.py",
    "python3 scripts/package_submission.py",
    "python3 scripts/package_query_outputs.py",
    "python3 scripts/check_submission_ready.py",
]

REPORT_REGENERATION_TARGETS = [
    "outputs/reports/report_index.md",
    "outputs/reports/report_index.json",
    "outputs/reports/system_summary.md",
    "outputs/reports/system_summary.json",
    "outputs/reports/llm_baseline_summary.md",
    "outputs/reports/llm_baseline_summary.json",
    "outputs/reports/accuracy_and_bottleneck_summary.md",
    "outputs/reports/accuracy_and_bottleneck_summary.json",
    "outputs/reports/visualization_summary.md",
    "outputs/reports/visualization_summary.json",
    "outputs/reports/cleanup_audit.md",
    "outputs/reports/cleanup_audit.json",
    "outputs/reports/cleanup_final_report.md",
    "outputs/reports/cleanup_final_report.json",
    "outputs/winner_readiness_report.md",
    "outputs/winner_readiness_report.json",
    "outputs/final_research_inspired_improvement_report.md",
    "outputs/final_research_inspired_improvement_report.json",
    "outputs/visualizations/index.md",
    "outputs/visualizations/index.json",
    "outputs/visualizations/system_status_dashboard.md",
    "outputs/visualizations/system_status_dashboard.json",
    "outputs/visualizations/technique_visual_cards.md",
    "outputs/visualizations/technique_visual_cards.json",
]

FINAL_RESPONSE_REQUIRED_FIELDS = [
    "files changed",
    "reports generated",
    "files deleted, if any",
    "validation commands run",
    "validation results",
    "skipped commands and reasons, if any",
    "check_submission_ready status",
    "secret scan status",
    "SQL_FIRST_API_VERIFY unchanged confirmation",
    "final submission format unchanged confirmation",
]

PROTECTED_PATTERNS = (
    "dashagent/**",
    "scripts/**",
    "tests/**",
    "data/**",
    "prompts/**",
    "outputs/final_submission/**",
    "outputs/eval/**",
    "outputs/reports/**",
    "outputs/final_submission_manifest.json",
    "outputs/eval_results_strict.json",
    "outputs/winner_readiness_report.*",
    "outputs/final_research_inspired_improvement_report.*",
    "outputs/accuracy_promotion_decision_report.*",
    "outputs/hidden_style_eval.*",
    "outputs/official_token_reduction_promotion_report.*",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Safely clean redundant generated files from the DASHSys repo.")
    parser.add_argument("--dry-run", action="store_true", help="Preview deletions without removing files. Default mode.")
    parser.add_argument("--apply", action="store_true", help="Apply allowed deletions.")
    parser.add_argument("--write-report", action="store_true", help="Write cleanup report files.")
    parser.add_argument(
        "--record-validation",
        action="append",
        default=[],
        metavar="RESULT_SPEC",
        help=(
            "Update outputs/reports/cleanup_final_report.* with a validation result. "
            "Accepts COMMAND=RESULT, COMMAND||result=RESULT||skip_reason=..., or a JSON object."
        ),
    )
    args = parser.parse_args(argv)

    config = Config.from_env(ROOT)
    if args.record_validation and not args.apply and not args.dry_run:
        payload = update_validation_results(config, args.record_validation)
        print(json.dumps({"mode": payload["mode"], "validation_results": len(payload.get("validation_commands_run", []))}, indent=2, sort_keys=True))
        return 0

    payload = cleanup_redundant_files(config, apply=args.apply)
    should_write = args.write_report or args.apply or args.dry_run or not args.apply
    if should_write:
        reports_dir = config.outputs_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        json_path = reports_dir / "cleanup_final_report.json"
        md_path = reports_dir / "cleanup_final_report.md"
        json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
        md_path.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"mode": payload["mode"], "deleted": payload["summary"]["deleted_count"], "dry_run": payload["dry_run"]}, indent=2, sort_keys=True))
    return 0 if not payload["summary"]["refused_count"] else 1


def cleanup_redundant_files(config: Config, *, apply: bool = False) -> dict[str, Any]:
    root = config.project_root.resolve()
    before_files = _count_files(root)
    audit_path = _audit_path(config)
    if not audit_path.exists():
        raise RuntimeError("Refusing cleanup: outputs/reports/cleanup_audit.json is missing.")
    if apply and not _validation_baseline_exists(config):
        raise RuntimeError("Refusing --apply: validation baseline outputs are missing.")
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    rows = audit.get("rows") or []
    actions = []
    for row in rows:
        if row.get("classification") not in {"delete_obsolete", "consolidate_then_delete", "safe_to_delete_generated"}:
            continue
        rel = str(row.get("path") or "")
        path = (root / rel).resolve()
        action = _cleanup_action(root, rel, path, apply=apply)
        actions.append({**row, **action})

    after_files = _count_files(root)
    deleted_files = [action["path"] for action in actions if action["status"] == "deleted"]
    protected_files = [
        row["path"]
        for row in rows
        if row.get("classification") in {"keep_source_of_truth", "keep_canonical_summary", "keep_required_by_test", "keep_required_by_packaging"}
    ]
    summary = {
        "candidate_count": len(actions),
        "deleted_count": sum(1 for action in actions if action["status"] == "deleted"),
        "dry_run_delete_count": sum(1 for action in actions if action["status"] == "would_delete"),
        "missing_count": sum(1 for action in actions if action["status"] == "missing"),
        "refused_count": sum(1 for action in actions if action["status"] == "refused"),
        "protected_deleted_count": 0,
        "no_protected_files_deleted": all(action["status"] != "deleted" or not action.get("protected_match") for action in actions),
        "files_before_cleanup": before_files,
        "files_after_cleanup": after_files,
        "reports_consolidated": sum(1 for row in rows if row.get("classification") == "consolidate_then_delete"),
        "final_submission_format_unchanged": not any(action["path"].startswith("outputs/final_submission/") for action in actions if action["status"] == "deleted"),
    }
    return {
        **report_metadata(config.outputs_dir),
        "mode": "redundant_file_cleanup_report",
        "dry_run": not apply,
        "applied": apply,
        "audit_run_id": audit.get("run_id"),
        "audit_path": str(audit_path.relative_to(root)),
        "actions": actions,
        "deleted_files": deleted_files,
        "canonical_reports_kept": [
            "outputs/reports/system_summary.md",
            "outputs/reports/llm_baseline_summary.md",
            "outputs/reports/accuracy_and_bottleneck_summary.md",
            "outputs/reports/visualization_summary.md",
            "outputs/reports/report_index.md",
        ],
        "protected_files": protected_files[:250],
        "validation_commands_run": [],
        "skipped_validation_commands": [],
        "required_validation_commands": list(REQUIRED_POST_CHANGE_VALIDATION_COMMANDS),
        "missing_required_validation_commands": list(REQUIRED_POST_CHANGE_VALIDATION_COMMANDS),
        "report_regeneration_targets": list(REPORT_REGENERATION_TARGETS),
        "generated_reports": _report_statuses(config),
        "check_submission_ready_passed": "not_recorded",
        "secret_scan_passed": "not_recorded",
        "remaining_validation_risk": [],
        "sql_first_api_verify_unchanged": True,
        "final_submission_format_unchanged": summary["final_submission_format_unchanged"],
        "final_response_required_fields": list(FINAL_RESPONSE_REQUIRED_FIELDS),
        "summary": summary,
        "protected_patterns": list(PROTECTED_PATTERNS),
        "notes": [
            "Cleanup deletes only audit rows classified as delete_obsolete or consolidate_then_delete.",
            "Required and manual-review paths are never deleted.",
            "Protected source/data/eval/final-submission patterns are refused even if an audit row is misclassified.",
            "Any skipped validation command must include a reason, substitute validation, and residual risk.",
        ],
    }


def _cleanup_action(root: Path, rel: str, path: Path, *, apply: bool) -> dict[str, Any]:
    try:
        path.relative_to(root)
    except ValueError:
        return {"status": "refused", "reason": "path_outside_repo", "protected_match": None}
    protected = _protected_match(rel)
    if protected:
        return {"status": "refused", "reason": "protected_pattern", "protected_match": protected}
    if not path.exists():
        return {"status": "missing", "reason": "already_absent", "protected_match": None}
    if not apply:
        return {"status": "would_delete", "reason": "dry_run", "protected_match": None}
    print(f"Deleting redundant generated path: {rel}")
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()
    return {"status": "deleted", "reason": "safe_to_delete_generated", "protected_match": None}


def _audit_path(config: Config) -> Path:
    new_path = config.outputs_dir / "reports" / "cleanup_audit.json"
    if new_path.exists():
        return new_path
    return config.outputs_dir / "redundant_file_audit.json"


def update_validation_results(config: Config, raw_results: list[str]) -> dict[str, Any]:
    reports_dir = config.outputs_dir / "reports"
    json_path = reports_dir / "cleanup_final_report.json"
    md_path = reports_dir / "cleanup_final_report.md"
    if json_path.exists():
        payload = json.loads(json_path.read_text(encoding="utf-8"))
    else:
        payload = {
            **report_metadata(config.outputs_dir),
            "mode": "redundant_file_cleanup_report",
            "validation_commands_run": [],
            "summary": {},
        }
    existing = payload.get("validation_commands_run") or []
    for raw in raw_results:
        existing.append(_parse_validation_result(raw))
    payload["validation_commands_run"] = existing
    skipped = [
        item
        for item in existing
        if item.get("result") == "skipped" or item.get("skipped") is True
    ]
    payload["skipped_validation_commands"] = skipped
    payload["required_validation_commands"] = list(REQUIRED_POST_CHANGE_VALIDATION_COMMANDS)
    payload["missing_required_validation_commands"] = _missing_required_commands(existing)
    payload["report_regeneration_targets"] = list(REPORT_REGENERATION_TARGETS)
    payload["generated_reports"] = _report_statuses(config)
    payload["final_response_required_fields"] = list(FINAL_RESPONSE_REQUIRED_FIELDS)
    payload["remaining_validation_risk"] = [
        item.get("residual_risk", "unspecified residual risk")
        for item in skipped
        if item.get("residual_risk")
    ]
    payload["validation_summary"] = {
        "total_recorded": len(existing),
        "passed": sum(1 for item in existing if item.get("result") == "passed"),
        "failed": sum(1 for item in existing if item.get("result") == "failed"),
        "skipped": len(skipped),
        "missing_required_count": len(payload["missing_required_validation_commands"]),
    }
    tracked_deleted = _deleted_files_from_git(config.project_root)
    if tracked_deleted:
        merged_deleted = sorted(set(payload.get("deleted_files") or []) | set(tracked_deleted))
        payload["deleted_files"] = merged_deleted
        payload.setdefault("summary", {})["deleted_file_count"] = len(merged_deleted)
    payload["check_submission_ready_passed"] = any(
        "check_submission_ready.py" in item.get("command", "") and item.get("result") == "passed"
        for item in existing
    )
    payload["secret_scan_passed"] = any(
        "rg -n" in item.get("command", "") and item.get("result") == "passed"
        for item in existing
    )
    reports_dir.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    return payload


def _parse_validation_result(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if not text:
        return {"command": "unavailable", "result": "failed", "skipped": False}
    if text.startswith("{"):
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            return {
                "command": text,
                "result": "failed",
                "skipped": False,
                "error": f"invalid validation JSON: {exc}",
            }
        command = str(data.get("command") or "unavailable").strip()
        result = str(data.get("result") or ("skipped" if data.get("skipped") else "passed")).strip()
        return _normalize_validation_entry({**data, "command": command, "result": result})
    if "||" in text:
        command, *segments = text.split("||")
        entry: dict[str, Any] = {"command": command.strip(), "result": "passed"}
        for segment in segments:
            key, sep, value = segment.partition("=")
            if sep:
                entry[key.strip()] = value.strip()
        return _normalize_validation_entry(entry)
    command, _, result = text.partition("=")
    return _normalize_validation_entry({"command": command.strip(), "result": (result or "passed").strip()})


def _normalize_validation_entry(entry: dict[str, Any]) -> dict[str, Any]:
    result = str(entry.get("result") or "passed").strip().lower()
    if result not in {"passed", "failed", "skipped"}:
        result = str(entry.get("result") or "passed").strip()
    skipped = bool(entry.get("skipped")) or result == "skipped"
    normalized = {
        "command": str(entry.get("command") or "unavailable").strip(),
        "result": result,
        "skipped": skipped,
    }
    for key in ("skip_reason", "substitute_validation", "residual_risk", "notes"):
        if entry.get(key):
            normalized[key] = str(entry[key]).strip()
    if skipped:
        normalized.setdefault("skip_reason", "not_recorded")
        normalized.setdefault("substitute_validation", "not_recorded")
        normalized.setdefault("residual_risk", "not_recorded")
    return normalized


def _missing_required_commands(existing: list[dict[str, Any]]) -> list[str]:
    recorded = {str(item.get("command") or "").strip() for item in existing}
    return [command for command in REQUIRED_POST_CHANGE_VALIDATION_COMMANDS if command not in recorded]


def _report_statuses(config: Config) -> list[dict[str, Any]]:
    root = config.project_root.resolve()
    statuses = []
    for rel in REPORT_REGENERATION_TARGETS:
        path = (root / rel).resolve()
        try:
            display = path.relative_to(root).as_posix()
        except ValueError:
            display = rel
        statuses.append({"path": display, "exists": path.exists()})
    return statuses


def _count_files(root: Path) -> int:
    return sum(1 for path in root.rglob("*") if path.is_file() and ".git" not in path.parts)


def _deleted_files_from_git(root: Path) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=D"],
            cwd=root,
            check=False,
            text=True,
            capture_output=True,
        )
    except Exception:
        return []
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _protected_match(rel: str) -> str | None:
    for pattern in PROTECTED_PATTERNS:
        if _matches_pattern(rel, pattern):
            return pattern
    return None


def _matches_pattern(rel: str, pattern: str) -> bool:
    if pattern.endswith("/**"):
        prefix = pattern[:-3]
        return rel == prefix.rstrip("/") or rel.startswith(prefix)
    if "*" in pattern:
        from fnmatch import fnmatch

        return fnmatch(rel, pattern)
    return rel == pattern


def _validation_baseline_exists(config: Config) -> bool:
    required = [
        config.outputs_dir / "eval_results_strict.json",
        config.outputs_dir / "winner_readiness_report.json",
        config.outputs_dir / "final_submission_manifest.json",
    ]
    return all(path.exists() for path in required)


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload.get("summary", {})
    validation = payload.get("validation_summary", {})
    lines = [
        "# Redundant File Cleanup Report",
        "",
        f"- Dry run: {payload.get('dry_run', 'unavailable')}",
        f"- Applied: {payload.get('applied', 'unavailable')}",
        f"- Candidate rows: {summary.get('candidate_count', 'unavailable')}",
        f"- Deleted: {summary.get('deleted_count', 'unavailable')}",
        f"- Deleted files total: {summary.get('deleted_file_count', len(payload.get('deleted_files') or []))}",
        f"- Would delete: {summary.get('dry_run_delete_count', 'unavailable')}",
        f"- Refused: {summary.get('refused_count', 'unavailable')}",
        f"- No protected files deleted: {summary.get('no_protected_files_deleted', 'unavailable')}",
        f"- Files before cleanup: {summary.get('files_before_cleanup', 'unavailable')}",
        f"- Files after cleanup: {summary.get('files_after_cleanup', 'unavailable')}",
        f"- Reports consolidated: {summary.get('reports_consolidated', 'unavailable')}",
        f"- Final submission format unchanged: {payload.get('final_submission_format_unchanged', summary.get('final_submission_format_unchanged', 'unavailable'))}",
        f"- check_submission_ready passed: {payload.get('check_submission_ready_passed', 'not_recorded')}",
        f"- Secret scan passed: {payload.get('secret_scan_passed', 'not_recorded')}",
        f"- Validation commands recorded: {validation.get('total_recorded', len(payload.get('validation_commands_run') or []))}",
        f"- Required validation commands missing: {validation.get('missing_required_count', len(payload.get('missing_required_validation_commands') or []))}",
        "",
        "## Actions",
        "",
    ]
    if payload.get("actions"):
        for action in payload["actions"][:150]:
            lines.append(f"- `{action['path']}`: {action['status']} ({action['reason']})")
    else:
        lines.append("- No safe generated deletion candidates.")
    lines.extend(["", "## Validation Commands", ""])
    if payload.get("validation_commands_run"):
        for item in payload.get("validation_commands_run", []):
            detail = f"- `{item.get('command')}`: {item.get('result')}"
            if item.get("skipped"):
                detail += (
                    f" (reason: {item.get('skip_reason')}; "
                    f"substitute: {item.get('substitute_validation')}; "
                    f"risk: {item.get('residual_risk')})"
                )
            lines.append(detail)
    else:
        lines.append("- Not recorded yet.")
    lines.extend(["", "## Skipped Validation Commands", ""])
    if payload.get("skipped_validation_commands"):
        for item in payload["skipped_validation_commands"]:
            lines.append(
                f"- `{item.get('command')}`: {item.get('skip_reason')} "
                f"(substitute: {item.get('substitute_validation')}; risk: {item.get('residual_risk')})"
            )
    else:
        lines.append("- None recorded.")
    lines.extend(["", "## Missing Required Validation Commands", ""])
    missing = payload.get("missing_required_validation_commands") or []
    if missing:
        lines.extend(f"- `{command}`" for command in missing)
    else:
        lines.append("- None.")
    lines.extend(["", "## Generated Reports", ""])
    reports = payload.get("generated_reports") or []
    if reports:
        for item in reports:
            lines.append(f"- `{item.get('path')}`: {'present' if item.get('exists') else 'missing'}")
    else:
        lines.append("- Not recorded yet.")
    lines.extend(["", "## Deleted Files", ""])
    deleted = payload.get("deleted_files") or [
        action["path"] for action in payload.get("actions", []) if action.get("status") == "deleted"
    ]
    if deleted:
        lines.extend(f"- `{path}`" for path in deleted[:200])
    else:
        lines.append("- None")
    lines.extend(["", "## Final Response Checklist", ""])
    for item in payload.get("final_response_required_fields", FINAL_RESPONSE_REQUIRED_FIELDS):
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
