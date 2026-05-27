#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


RISK_TERMS = [
    "prompt_id",
    "query_id",
    "example_",
    "da500_",
    "category",
    "tags",
    "gold",
    "oracle",
    "expected_trace",
    "expected_tool_calls",
    "required_facts",
    "forbidden_claims",
    "simulated_trace",
    "synthetic_sql_result",
    "fake_score",
    "native_score",
    "score_override",
    "hardcoded score",
    "manually assigned pass/fail",
]
SKIP_DIRS = {
    ".git",
    ".pytest_cache",
    "__pycache__",
    ".mypy_cache",
    ".venv",
    "venv",
    "node_modules",
    "archives",
    "archive",
}
TEXT_SUFFIXES = {
    ".py",
    ".md",
    ".json",
    ".jsonl",
    ".txt",
    ".yaml",
    ".yml",
    ".toml",
    ".csv",
}


def classify_hit(*, path: Path, line: str, term: str, line_number: int) -> dict[str, Any]:
    path_text = path.as_posix()
    lower_path = path_text.lower()
    lower_line = line.lower()
    lower_term = term.lower()
    classification = "safe_report_only"
    promotion_blocker = False

    if lower_path.startswith("outputs/source_code/"):
        classification = "safe_report_only"
    elif "/tests/" in f"/{lower_path}" or lower_path.startswith("tests/"):
        classification = "safe_test_fixture"
    elif lower_path.startswith("outputs/") or "/reports/" in lower_path or lower_path.startswith("docs/"):
        classification = "safe_report_only"
    elif "simulated_trace" in lower_line or "synthetic_sql_result" in lower_line:
        classification = "legacy_simulated_diagnostic"
    elif lower_path.startswith("scripts/") and _is_eval_or_audit_script(lower_path):
        classification = "safe_eval_only_after_execution"
    elif lower_path in {"dashagent/score_provenance.py", "dashagent/eval_harness.py"}:
        classification = "safe_eval_only_after_execution"
    elif lower_path.startswith("dashagent/") and any(token in lower_path for token in ("failure_analysis.py", "dataflow_visualizer.py")):
        classification = "safe_eval_only_after_execution"
    elif lower_path.startswith("dashagent/") and lower_term in {"gold", "query_id"} and _looks_like_leakage_guard(lower_line):
        classification = "safe_runtime_guard"
    elif lower_path.startswith("dashagent/") and lower_term == "gold" and any(
        token in lower_path
        for token in (
            "answer_style_miner.py",
            "query_family_examples.py",
            "pattern_mining.py",
            "metadata_selector.py",
            "api_templates.py",
            "endpoint_catalog.py",
            "cache.py",
            "config.py",
            "risk_efficiency_controller.py",
            "sql_only_api_skip_guard.py",
            "evidence_policy.py",
        )
    ):
        classification = "needs_review_gold_pattern_runtime_risk"
    elif lower_path.startswith("dashagent/") and any(
        token in lower_path
        for token in (
            "endpoint_schema_rule_candidates.py",
            "execution_based_candidate_selector.py",
            "targeted_candidate_generator.py",
            "research_safety.py",
            "local_knowledge_index.py",
            "llm_candidate_generator.py",
            "llm_sql_context_builder.py",
            "llm_sql_semantic_verifier.py",
        )
    ):
        classification = "safe_runtime_guard"
    elif lower_path.startswith("dashagent/") and lower_term in {"gold", "oracle", "expected_trace", "expected_tool_calls", "required_facts", "forbidden_claims"}:
        classification = "unsafe_runtime_hardcode"
        promotion_blocker = True
    elif lower_path.startswith("dashagent/") and lower_term in {"prompt_id", "query_id", "example_", "da500_"}:
        if _looks_like_identifier_conditional(lower_line):
            classification = "unsafe_runtime_hardcode"
            promotion_blocker = True
        else:
            classification = "safe_runtime_identifier_io"
    elif any(token in lower_line for token in ("score_override", "fake_score", "hardcoded score", "manually assigned pass/fail")):
        classification = "unsafe_fake_score"
        promotion_blocker = True
    elif lower_path.startswith("scripts/"):
        classification = "safe_eval_only_after_execution"

    return {
        "path": path_text,
        "line_number": int(line_number),
        "term": term,
        "classification": classification,
        "promotion_blocker": promotion_blocker,
        "line_preview": _preview(line),
    }


def run_audit(root: Path = ROOT) -> dict[str, Any]:
    hits: list[dict[str, Any]] = []
    scanned_files = 0
    for path in _iter_text_files(root):
        rel = path.relative_to(root)
        scanned_files += 1
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for line_number, line in enumerate(lines, start=1):
            lower = line.lower()
            for term in RISK_TERMS:
                if term.lower() in lower:
                    hits.append(classify_hit(path=rel, line=line, term=term, line_number=line_number))
    counts = Counter(hit["classification"] for hit in hits)
    unsafe_runtime = [hit for hit in hits if hit["classification"] == "unsafe_runtime_hardcode"]
    unsafe_fake = [hit for hit in hits if hit["classification"] == "unsafe_fake_score"]
    needs_review = [hit for hit in hits if hit["classification"].startswith("needs_review")]
    simulated_hits = [hit for hit in hits if hit["classification"] == "legacy_simulated_diagnostic"]
    report = {
        "report_type": "hardcoded_runtime_and_score_path_audit",
        "scanned_file_count": scanned_files,
        "hit_count": len(hits),
        "classification_counts": dict(sorted(counts.items())),
        "unsafe_runtime_hardcode_count": len(unsafe_runtime),
        "unsafe_fake_score_count": len(unsafe_fake),
        "legacy_simulated_diagnostic_count": len(simulated_hits),
        "needs_review_count": len(needs_review),
        "needs_review_hits": needs_review[:100],
        "promotion_eligible_simulated_trace": False,
        "runtime_leakage_detected": bool(unsafe_runtime),
        "fake_score_risk_detected": bool(unsafe_fake),
        "hits": hits[:1000],
        "unsafe_runtime_hardcode": unsafe_runtime[:100],
        "unsafe_fake_score": unsafe_fake[:100],
    }
    return report


def write_report(report: dict[str, Any], reports_dir: Path) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "hardcoded_runtime_and_score_path_audit.json").write_text(
        json.dumps(report, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    lines = [
        "# Hardcoded Runtime And Score Path Audit",
        "",
        f"- Scanned files: `{report['scanned_file_count']}`",
        f"- Hits: `{report['hit_count']}`",
        f"- Unsafe runtime hardcodes: `{report['unsafe_runtime_hardcode_count']}`",
        f"- Unsafe fake score hits: `{report['unsafe_fake_score_count']}`",
        f"- Legacy simulated diagnostic hits: `{report['legacy_simulated_diagnostic_count']}`",
        f"- Needs-review runtime pattern risks: `{report['needs_review_count']}`",
        f"- Simulated trace promotion eligible: `{str(report['promotion_eligible_simulated_trace']).lower()}`",
        "",
        "## Classification Counts",
    ]
    for key, value in report["classification_counts"].items():
        lines.append(f"- `{key}`: `{value}`")
    if report["unsafe_runtime_hardcode"]:
        lines.extend(["", "## Unsafe Runtime Hardcode Hits"])
        for hit in report["unsafe_runtime_hardcode"][:20]:
            lines.append(f"- `{hit['path']}:{hit['line_number']}` term=`{hit['term']}`")
    (reports_dir / "hardcoded_runtime_and_score_path_audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--reports-dir", type=Path, default=ROOT / "outputs" / "reports")
    args = parser.parse_args()
    report = run_audit(args.root)
    write_report(report, args.reports_dir)
    print(json.dumps({k: report[k] for k in ["scanned_file_count", "unsafe_runtime_hardcode_count", "unsafe_fake_score_count"]}, indent=2, sort_keys=True))
    return 0


def _iter_text_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if path.is_dir():
            continue
        rel_parts = set(path.relative_to(root).parts)
        if rel_parts & SKIP_DIRS:
            continue
        if ".env" in path.name or path.suffix.lower() in {".zip", ".parquet", ".duckdb", ".png", ".jpg", ".jpeg", ".gif", ".pdf"}:
            continue
        rel = path.relative_to(root).as_posix()
        if rel.startswith(("outputs/eval/", "outputs/source_code/", "outputs/dashagent_500_prompt_suite_eval_real/")):
            continue
        if path.suffix.lower() in TEXT_SUFFIXES:
            files.append(path)
    return files


def _is_eval_or_audit_script(path: str) -> bool:
    name = Path(path).name
    return any(token in name for token in ("eval", "audit", "diagnostic", "benchmark", "suite", "gate", "report", "convert"))


def _looks_like_leakage_guard(line: str) -> bool:
    return any(
        token in line
        for token in (
            "do not",
            "forbidden",
            "reject",
            "rejected",
            "non-gold",
            "no_gold",
            "leakage",
            "cannot contain",
            "used_gold_patterns",
            "derived_from_gold",
            "gold_signal_used",
            "gold label",
            "mentions_query_id_or_gold",
            "runtime_gold_signal_patterns",
            "gold-derived",
            "gold-derived",
            "does not use",
            "omits",
            "manual_gold",
            "memorized_gold",
            "gold_sql_path",
            "gold_api_path",
        )
    )


def _looks_like_identifier_conditional(line: str) -> bool:
    has_branch = any(token in line for token in ("if ", "elif ", "case "))
    has_identifier = any(token in line for token in ("query_id", "prompt_id", "example_", "da500_"))
    has_specific_match = any(token in line for token in ("==", "!=", " in {", " in [", " in (", ".startswith"))
    return has_branch and has_identifier and has_specific_match


def _preview(line: str) -> str:
    text = " ".join(str(line).strip().split())
    return text[:220]


if __name__ == "__main__":
    raise SystemExit(main())
