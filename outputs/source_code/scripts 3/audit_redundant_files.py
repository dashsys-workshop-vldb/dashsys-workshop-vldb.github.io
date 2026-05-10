#!/usr/bin/env python
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, asdict
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.report_run import report_metadata


REQUIRED_REPORT_BASENAMES = {
    "winner_readiness_report",
    "final_research_inspired_improvement_report",
    "accuracy_promotion_decision_report",
    "hidden_style_eval",
    "official_token_reduction_promotion_report",
    "official_token_reduction_packaged_trial",
    "official_token_reduction_eval",
    "official_token_reduction_canary",
    "official_token_accounting_report",
    "candidate_context_report",
    "shadow_repair_eval",
    "compact_context_shadow_eval",
    "compact_context_measured_eval",
    "risk_efficiency_shadow_eval",
    "endpoint_family_failure_report",
    "endpoint_schema_rule_candidate_eval",
    "endpoint_schema_rule_canary",
    "endpoint_schema_rule_packaged_trial",
    "schema_dataset_positive_repair_analysis",
    "sql_ast_candidate_ranking_report",
    "ast_guided_sql_candidate_canary",
    "retrieval_ablation_report",
    "repair_selector_v2_shadow_eval",
    "repair_selector_v3_shadow_eval",
    "low_score_failure_mining_report",
    "execution_candidate_search",
    "llm_candidate_search",
    "targeted_accuracy_packaged_trial",
    "score_0_7_push_report",
    "research_safety_audit",
}

REQUIRED_OUTPUT_FILES = {
    "outputs/final_submission_manifest.json",
    "outputs/eval_results_strict.json",
    "outputs/eval_results_strict.csv",
    "outputs/source_code.zip",
    "outputs/strategy_comparison_strict.md",
}

PROTECTED_PREFIXES = (
    "dashagent/",
    "scripts/",
    "tests/",
    "data/",
    "prompts/",
    "outputs/final_submission/",
    "outputs/eval/",
)

SAFE_DELETE_DIR_NAMES = {
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "__pycache__",
    "cache",
    "tmp",
}

SAFE_GITIGNORE_ONLY = {
    ".venv",
    "venv",
    ".env",
}


@dataclass(frozen=True)
class AuditEntry:
    path: str
    classification: str
    reason: str
    referenced_by: list[str]
    proposed_action: str


def main() -> int:
    config = Config.from_env(ROOT)
    payload = audit_redundant_files(config)
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    json_path = config.outputs_dir / "redundant_file_audit.json"
    md_path = config.outputs_dir / "redundant_file_audit.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "safe_to_delete": payload["summary"]["safe_to_delete_generated_count"]}, indent=2, sort_keys=True))
    return 0


def audit_redundant_files(config: Config) -> dict[str, Any]:
    root = config.project_root.resolve()
    entries: dict[str, AuditEntry] = {}

    _add(entries, root, root / "dashagent", "required_runtime", "runtime package source", ["package_submission.py", "runtime imports"], "keep")
    _add(entries, root, root / "scripts", "required_validation", "validation and report scripts", ["package_submission.py", "validation command sequence"], "keep")
    _add(entries, root, root / "tests", "required_validation", "test suite", ["pytest"], "keep")
    _add(entries, root, root / "data", "required_runtime", "local data/config inputs for execution", ["Config", "DuckDBDatabase"], "keep")
    _add(entries, root, root / "prompts", "required_runtime", "system prompt templates", ["AgentExecutor", "package_query_outputs.py"], "keep")
    _add(entries, root, config.outputs_dir / "final_submission", "required_submission", "current packaged final submission artifacts", ["check_submission_ready.py"], "keep")

    for relative in sorted(REQUIRED_OUTPUT_FILES):
        _add(entries, root, root / relative, "required_submission", "current eval/submission artifact", ["validation/readiness"], "keep")

    for basename in sorted(REQUIRED_REPORT_BASENAMES):
        for suffix in (".json", ".md"):
            path = config.outputs_dir / f"{basename}{suffix}"
            if path.exists():
                _add(entries, root, path, "required_reports", "current diagnostic/final report", ["winner/research reports"], "keep")

    for path in _iter_cleanup_candidates(root):
        rel = _relative(root, path)
        if rel in entries:
            continue
        if _is_protected(rel):
            _add(entries, root, path, "needs_manual_review", "inside protected source/data/eval/final-submission path", ["protected pattern"], "manual_review")
        elif _is_safe_delete_generated(rel, path):
            _add(entries, root, path, "safe_to_delete_generated", _safe_delete_reason(rel, path), ["regenerable local/generated artifact"], "delete")
        elif _is_safe_gitignore_only(rel, path):
            _add(entries, root, path, "safe_to_gitignore_only", "local environment/cache should be ignored, not removed by cleanup", [".gitignore"], "gitignore")
        else:
            _add(entries, root, path, "needs_manual_review", "ambiguous generated or local artifact", ["manual review"], "manual_review")

    rows = sorted((asdict(entry) for entry in entries.values()), key=lambda row: row["path"])
    summary = _summary(rows)
    return {
        **report_metadata(config.outputs_dir),
        "mode": "redundant_file_audit",
        "project_root": str(root),
        "rows": rows,
        "summary": summary,
        "protected_patterns": list(PROTECTED_PREFIXES),
        "notes": [
            "This audit is conservative: cleanup may delete only safe_to_delete_generated rows.",
            "Source, data, prompts, official eval, and final submission paths are protected.",
            "safe_to_gitignore_only rows are local artifacts to ignore, not delete automatically.",
        ],
    }


def _iter_cleanup_candidates(root: Path) -> list[Path]:
    candidates: set[Path] = set()
    for dirpath, dirnames, filenames in os.walk(root):
        directory = Path(dirpath)
        rel_dir = _relative(root, directory) if directory != root else ""
        pruned: list[str] = []
        for dirname in list(dirnames):
            path = directory / dirname
            rel = _relative(root, path)
            if dirname == ".git":
                pruned.append(dirname)
                continue
            if rel in {"dashagent", "scripts", "tests", "data", "prompts"} or rel in {"outputs/eval", "outputs/final_submission"}:
                pruned.append(dirname)
                continue
            if dirname in SAFE_DELETE_DIR_NAMES or dirname in SAFE_GITIGNORE_ONLY or rel == "outputs/source_code":
                candidates.add(path)
                pruned.append(dirname)
                continue
            if rel.startswith("outputs/") and (dirname.endswith(" 4") or dirname.endswith(" 2")):
                candidates.add(path)
                pruned.append(dirname)
        for dirname in pruned:
            if dirname in dirnames:
                dirnames.remove(dirname)
        for filename in filenames:
            path = directory / filename
            rel = _relative(root, path)
            if filename == ".DS_Store" or filename.endswith((".pyc", ".pyo", ".log", ".tmp")):
                candidates.add(path)
            elif rel.startswith("outputs/") and (" 2." in filename or filename.endswith((" 2.json", " 2.csv", " 2.md"))):
                candidates.add(path)
    return sorted(candidates, key=lambda item: (len(item.parts), str(item)))


def _is_safe_delete_generated(rel: str, path: Path) -> bool:
    if rel == "outputs/source_code" and path.is_dir():
        return True
    if path.name in {".pytest_cache", ".mypy_cache", ".ruff_cache"}:
        return True
    if rel.startswith("outputs/") and path.name in {"cache", "tmp", "__pycache__"}:
        return True
    if rel.startswith("outputs/") and (path.name.endswith((".pyc", ".pyo", ".log", ".tmp")) or path.name == ".DS_Store"):
        return True
    if rel.startswith("outputs/") and (" 2." in path.name or path.name.endswith((" 2.json", " 2.csv", " 2.md"))):
        return True
    if rel.startswith("outputs/") and any(part.endswith(" 4") or part.endswith(" 2") for part in path.parts):
        return True
    return False


def _safe_delete_reason(rel: str, path: Path) -> str:
    if rel == "outputs/source_code":
        return "regenerated by package_submission.py; source_code.zip is protected separately"
    if path.name in {".pytest_cache", ".mypy_cache", ".ruff_cache"}:
        return "local test/type/lint cache"
    if path.name == "cache" and rel.startswith("outputs/"):
        return "regenerable output cache"
    if " 2" in path.name or any(part.endswith(" 4") or part.endswith(" 2") for part in path.parts):
        return "duplicate stale copied run artifact under isolated outputs"
    return "generated temporary/cache artifact"


def _is_safe_gitignore_only(rel: str, path: Path) -> bool:
    if path.name in SAFE_GITIGNORE_ONLY:
        return True
    if path.name.startswith(".env."):
        return True
    return False


def _is_protected(rel: str) -> bool:
    return any(rel == prefix.rstrip("/") or rel.startswith(prefix) for prefix in PROTECTED_PREFIXES) or rel in REQUIRED_OUTPUT_FILES


def _add(
    entries: dict[str, AuditEntry],
    root: Path,
    path: Path,
    classification: str,
    reason: str,
    referenced_by: list[str],
    action: str,
) -> None:
    if not path.exists():
        return
    rel = _relative(root, path)
    entries[rel] = AuditEntry(rel, classification, reason, referenced_by, action)


def _relative(root: Path, path: Path) -> str:
    # Do not resolve symlink targets here: virtualenv bin links can point
    # outside the repo, but the audit should classify the local symlink path.
    return path.absolute().relative_to(root).as_posix()


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["classification"]] = counts.get(row["classification"], 0) + 1
    return {
        "total_rows": len(rows),
        "classification_counts": counts,
        "safe_to_delete_generated_count": counts.get("safe_to_delete_generated", 0),
        "safe_to_gitignore_only_count": counts.get("safe_to_gitignore_only", 0),
        "needs_manual_review_count": counts.get("needs_manual_review", 0),
        "required_count": sum(counts.get(key, 0) for key in ["required_runtime", "required_validation", "required_submission", "required_reports"]),
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Redundant File Audit",
        "",
        f"- Total rows: {summary['total_rows']}",
        f"- Required rows: {summary['required_count']}",
        f"- Safe generated deletions: {summary['safe_to_delete_generated_count']}",
        f"- Gitignore-only rows: {summary['safe_to_gitignore_only_count']}",
        f"- Manual review rows: {summary['needs_manual_review_count']}",
        "",
        "## Safe To Delete Generated",
        "",
    ]
    safe_rows = [row for row in payload["rows"] if row["classification"] == "safe_to_delete_generated"]
    if safe_rows:
        lines.extend(f"- `{row['path']}`: {row['reason']}" for row in safe_rows[:100])
    else:
        lines.append("- None")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
