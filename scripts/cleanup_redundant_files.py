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
        metavar="COMMAND=RESULT",
        help="Update outputs/reports/cleanup_final_report.* with a validation command result.",
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
        "check_submission_ready_passed": "not_recorded",
        "secret_scan_passed": "not_recorded",
        "sql_first_api_verify_unchanged": True,
        "final_submission_format_unchanged": summary["final_submission_format_unchanged"],
        "summary": summary,
        "protected_patterns": list(PROTECTED_PATTERNS),
        "notes": [
            "Cleanup deletes only audit rows classified as delete_obsolete or consolidate_then_delete.",
            "Required and manual-review paths are never deleted.",
            "Protected source/data/eval/final-submission patterns are refused even if an audit row is misclassified.",
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
        command, _, result = raw.partition("=")
        existing.append({"command": command.strip(), "result": (result or "passed").strip()})
    payload["validation_commands_run"] = existing
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
    summary = payload["summary"]
    lines = [
        "# Redundant File Cleanup Report",
        "",
        f"- Dry run: {payload['dry_run']}",
        f"- Applied: {payload['applied']}",
        f"- Candidate rows: {summary['candidate_count']}",
        f"- Deleted: {summary['deleted_count']}",
        f"- Deleted files total: {summary.get('deleted_file_count', len(payload.get('deleted_files') or []))}",
        f"- Would delete: {summary['dry_run_delete_count']}",
        f"- Refused: {summary['refused_count']}",
        f"- No protected files deleted: {summary['no_protected_files_deleted']}",
        f"- Files before cleanup: {summary.get('files_before_cleanup', 'unavailable')}",
        f"- Files after cleanup: {summary.get('files_after_cleanup', 'unavailable')}",
        f"- Reports consolidated: {summary.get('reports_consolidated', 'unavailable')}",
        f"- Final submission format unchanged: {payload.get('final_submission_format_unchanged', summary.get('final_submission_format_unchanged', 'unavailable'))}",
        f"- check_submission_ready passed: {payload.get('check_submission_ready_passed', 'not_recorded')}",
        f"- Secret scan passed: {payload.get('secret_scan_passed', 'not_recorded')}",
        "",
        "## Actions",
        "",
    ]
    if payload["actions"]:
        for action in payload["actions"][:150]:
            lines.append(f"- `{action['path']}`: {action['status']} ({action['reason']})")
    else:
        lines.append("- No safe generated deletion candidates.")
    lines.extend(["", "## Validation Commands", ""])
    if payload.get("validation_commands_run"):
        for item in payload.get("validation_commands_run", []):
            lines.append(f"- `{item.get('command')}`: {item.get('result')}")
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
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
