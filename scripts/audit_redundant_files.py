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

READINESS_REQUIRED_REPORT_BASENAMES = {
    "failure_analysis",
    "family_score_report",
    "pareto_report",
    "threshold_tuning_report",
    "robustness_eval",
}

CANONICAL_TOP_LEVEL_REPORT_BASENAMES = {
    "winner_readiness_report",
    "final_research_inspired_improvement_report",
    "accuracy_promotion_decision_report",
    "hidden_style_eval",
    "llm_sdk_backend_check",
    "llm_baseline_eval_report",
    "llm_strict_baseline_eval",
    "llm_hidden_style_diagnostic",
    "eval_results_strict",
}

CANONICAL_VISUALIZATION_FILES = {
    "outputs/visualizations/sql_prompt_storyboard_primary.md",
    "outputs/visualizations/sql_prompt_storyboard_primary.json",
    "outputs/visualizations/index.md",
    "outputs/visualizations/index.json",
    "outputs/visualizations/executive_dashboard.md",
    "outputs/visualizations/executive_dashboard.json",
    "outputs/visualizations/system_status_dashboard.md",
    "outputs/visualizations/system_status_dashboard.json",
    "outputs/visualizations/score_bottleneck_dashboard.md",
    "outputs/visualizations/score_bottleneck_dashboard.json",
}

LEGACY_REPORT_FILES_TO_CONSOLIDATE = {
    "outputs/baseline_before_architecture_optimization.md",
    "outputs/baseline_before_efficiency_pass.md",
    "outputs/baseline_before_final_polish.md",
    "outputs/baseline_before_nlp_optimization.md",
    "outputs/final_answer_correctness_report.md",
    "outputs/final_architecture_optimization_report.md",
    "outputs/final_checkpointed_agent_report.md",
    "outputs/final_efficiency_accuracy_improvement_report.md",
    "outputs/final_improvement_report.md",
    "outputs/final_llm_nl2sql_strict_candidate_report.md",
    "outputs/final_nlp_optimization_report.md",
    "outputs/final_polish_report.md",
    "outputs/final_real_llm_tool_baseline_fix_report.md",
    "outputs/final_report_and_visualization_polish_report.md",
    "outputs/redundant_file_audit.json",
    "outputs/redundant_file_audit.md",
    "outputs/redundant_file_cleanup_report.json",
    "outputs/redundant_file_cleanup_report.md",
}

SAFE_DELETE_OUTPUT_DIRS = {
    "outputs/cache",
    "outputs/tmp",
    "outputs/source_code",
    "outputs/probe",
    "outputs/probe_eff",
    "outputs/probe_eff2",
    "outputs/debug_example_005",
    "outputs/debug_example_005b",
    "outputs/llm_strict_eval",
    "outputs/llm_controller_baseline_backend",
    "outputs/threshold_runs",
    "outputs/robustness_runs",
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
    replacement: str | None = None


def main() -> int:
    config = Config.from_env(ROOT)
    payload = audit_redundant_files(config)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    json_path = reports_dir / "cleanup_audit.json"
    md_path = reports_dir / "cleanup_audit.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "safe_to_delete": payload["summary"]["safe_to_delete_generated_count"]}, indent=2, sort_keys=True))
    return 0


def audit_redundant_files(config: Config) -> dict[str, Any]:
    root = config.project_root.resolve()
    entries: dict[str, AuditEntry] = {}

    _add(entries, root, root / "dashagent", "keep_source_of_truth", "runtime package source", ["package_submission.py", "runtime imports"], "keep")
    _add(entries, root, root / "scripts", "keep_source_of_truth", "validation and report scripts", ["package_submission.py", "validation command sequence"], "keep")
    _add(entries, root, root / "tests", "keep_required_by_test", "test suite", ["pytest"], "keep")
    _add(entries, root, root / "data", "keep_source_of_truth", "local data/config inputs for execution", ["Config", "DuckDBDatabase"], "keep")
    _add(entries, root, root / "prompts", "keep_source_of_truth", "system prompt templates", ["AgentExecutor", "package_query_outputs.py"], "keep")
    _add(entries, root, config.outputs_dir / "final_submission", "keep_required_by_packaging", "current packaged final submission artifacts", ["check_submission_ready.py"], "keep")

    for relative in sorted(REQUIRED_OUTPUT_FILES):
        _add(entries, root, root / relative, "keep_required_by_packaging", "current eval/submission artifact", ["validation/readiness"], "keep")

    for basename in sorted(REQUIRED_REPORT_BASENAMES):
        for suffix in (".json", ".md"):
            path = config.outputs_dir / f"{basename}{suffix}"
            if path.exists():
                _add(entries, root, path, "keep_source_of_truth", "current diagnostic/final report", ["winner/research reports"], "keep")

    for basename in sorted(READINESS_REQUIRED_REPORT_BASENAMES):
        for suffix in (".json", ".md"):
            path = config.outputs_dir / f"{basename}{suffix}"
            if path.exists():
                _add(entries, root, path, "keep_required_by_packaging", "required by check_submission_ready.py", ["check_submission_ready.py"], "keep")

    for basename in sorted(CANONICAL_TOP_LEVEL_REPORT_BASENAMES):
        for suffix in (".json", ".md", ".csv"):
            path = config.outputs_dir / f"{basename}{suffix}"
            if path.exists():
                _add(entries, root, path, "keep_source_of_truth", "current canonical status/evaluation report", ["outputs/reports/report_index.md"], "keep")

    for relative in sorted(CANONICAL_VISUALIZATION_FILES):
        _add(entries, root, root / relative, "keep_source_of_truth", "current supervisor visualization artifact", ["outputs/reports/visualization_summary.md"], "keep")

    reports_dir = config.outputs_dir / "reports"
    if reports_dir.exists():
        for path in sorted(reports_dir.glob("*")):
            if path.is_file():
                _add(entries, root, path, "keep_canonical_summary", "canonical consolidated report", ["outputs/reports/report_index.md"], "keep")

    for relative in sorted(LEGACY_REPORT_FILES_TO_CONSOLIDATE):
        path = root / relative
        if path.exists():
            _add(entries, root, path, "consolidate_then_delete", "legacy narrative report superseded by outputs/reports summaries", ["outputs/reports/report_index.md"], "delete", "outputs/reports/report_index.md")

    for relative in sorted(SAFE_DELETE_OUTPUT_DIRS):
        path = root / relative
        if path.exists():
            replacement = "outputs/reports/llm_baseline_summary.md" if "llm_" in relative else "regenerable generated artifact"
            _add(entries, root, path, "delete_obsolete", _safe_delete_reason(relative, path), [replacement], "delete", replacement if replacement.startswith("outputs/") else None)

    for path in _iter_cleanup_candidates(root):
        rel = _relative(root, path)
        if rel in entries:
            continue
        if _is_protected(rel):
            _add(entries, root, path, "unsure_do_not_delete", "inside protected source/data/eval/final-submission path", ["protected pattern"], "keep")
        elif _is_safe_delete_generated(rel, path):
            _add(entries, root, path, "delete_obsolete", _safe_delete_reason(rel, path), ["regenerable local/generated artifact"], "delete")
        elif _is_safe_gitignore_only(rel, path):
            _add(entries, root, path, "unsure_do_not_delete", "local environment/cache should be ignored, not removed by cleanup", [".gitignore"], "keep")
        else:
            _add(entries, root, path, "unsure_do_not_delete", "ambiguous generated or local artifact", ["manual review"], "keep")

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
            "This audit is conservative: cleanup may delete only delete_obsolete or consolidate_then_delete rows.",
            "Source, data, prompts, official eval, and final submission paths are protected.",
            "unsure_do_not_delete rows are kept.",
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
    if rel in SAFE_DELETE_OUTPUT_DIRS and path.is_dir():
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
    if rel in {"outputs/llm_strict_eval", "outputs/llm_controller_baseline_backend"}:
        return "isolated LLM baseline raw artifacts summarized by generic LLM reports"
    if rel in {"outputs/probe", "outputs/probe_eff", "outputs/probe_eff2", "outputs/debug_example_005", "outputs/debug_example_005b"}:
        return "debug/probe output not used by packaging or readiness"
    if rel in {"outputs/threshold_runs", "outputs/robustness_runs"}:
        return "intermediate run directory summarized by required reports"
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
    replacement: str | None = None,
) -> None:
    if not path.exists():
        return
    rel = _relative(root, path)
    entries[rel] = AuditEntry(rel, classification, reason, referenced_by, action, replacement)


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
        "safe_to_delete_generated_count": counts.get("delete_obsolete", 0) + counts.get("consolidate_then_delete", 0),
        "safe_to_gitignore_only_count": 0,
        "needs_manual_review_count": counts.get("unsure_do_not_delete", 0),
        "required_count": sum(counts.get(key, 0) for key in ["keep_source_of_truth", "keep_required_by_test", "keep_required_by_packaging", "keep_canonical_summary"]),
        "delete_obsolete_count": counts.get("delete_obsolete", 0),
        "consolidate_then_delete_count": counts.get("consolidate_then_delete", 0),
        "canonical_summary_count": counts.get("keep_canonical_summary", 0),
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Redundant File Audit",
        "",
        f"- Total rows: {summary['total_rows']}",
        f"- Required rows: {summary['required_count']}",
        f"- Delete obsolete rows: {summary['delete_obsolete_count']}",
        f"- Consolidate then delete rows: {summary['consolidate_then_delete_count']}",
        f"- Unsure / kept rows: {summary['needs_manual_review_count']}",
        "",
        "## Safe To Delete Generated",
        "",
    ]
    safe_rows = [row for row in payload["rows"] if row["classification"] in {"delete_obsolete", "consolidate_then_delete"}]
    if safe_rows:
        lines.extend(f"- `{row['path']}`: {row['reason']}" for row in safe_rows[:100])
    else:
        lines.append("- None")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
