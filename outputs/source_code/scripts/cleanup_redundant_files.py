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
    args = parser.parse_args(argv)

    config = Config.from_env(ROOT)
    payload = cleanup_redundant_files(config, apply=args.apply)
    should_write = args.write_report or args.apply or args.dry_run or not args.apply
    if should_write:
        config.outputs_dir.mkdir(parents=True, exist_ok=True)
        json_path = config.outputs_dir / "redundant_file_cleanup_report.json"
        md_path = config.outputs_dir / "redundant_file_cleanup_report.md"
        json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
        md_path.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"mode": payload["mode"], "deleted": payload["summary"]["deleted_count"], "dry_run": payload["dry_run"]}, indent=2, sort_keys=True))
    return 0 if not payload["summary"]["refused_count"] else 1


def cleanup_redundant_files(config: Config, *, apply: bool = False) -> dict[str, Any]:
    root = config.project_root.resolve()
    audit_path = config.outputs_dir / "redundant_file_audit.json"
    if not audit_path.exists():
        raise RuntimeError("Refusing cleanup: outputs/redundant_file_audit.json is missing.")
    if apply and not _validation_baseline_exists(config):
        raise RuntimeError("Refusing --apply: validation baseline outputs are missing.")
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    rows = audit.get("rows") or []
    actions = []
    for row in rows:
        if row.get("classification") != "safe_to_delete_generated":
            continue
        rel = str(row.get("path") or "")
        path = (root / rel).resolve()
        action = _cleanup_action(root, rel, path, apply=apply)
        actions.append({**row, **action})

    summary = {
        "candidate_count": len(actions),
        "deleted_count": sum(1 for action in actions if action["status"] == "deleted"),
        "dry_run_delete_count": sum(1 for action in actions if action["status"] == "would_delete"),
        "missing_count": sum(1 for action in actions if action["status"] == "missing"),
        "refused_count": sum(1 for action in actions if action["status"] == "refused"),
        "protected_deleted_count": 0,
        "no_protected_files_deleted": all(action["status"] != "deleted" or not action.get("protected_match") for action in actions),
    }
    return {
        **report_metadata(config.outputs_dir),
        "mode": "redundant_file_cleanup_report",
        "dry_run": not apply,
        "applied": apply,
        "audit_run_id": audit.get("run_id"),
        "actions": actions,
        "summary": summary,
        "protected_patterns": list(PROTECTED_PATTERNS),
        "notes": [
            "Cleanup deletes only audit rows classified as safe_to_delete_generated.",
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
        f"- Would delete: {summary['dry_run_delete_count']}",
        f"- Refused: {summary['refused_count']}",
        f"- No protected files deleted: {summary['no_protected_files_deleted']}",
        "",
        "## Actions",
        "",
    ]
    if payload["actions"]:
        for action in payload["actions"][:150]:
            lines.append(f"- `{action['path']}`: {action['status']} ({action['reason']})")
    else:
        lines.append("- No safe generated deletion candidates.")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
