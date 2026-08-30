#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dashagent.config import DEFAULT_CONFIG
from dashagent.prompt_semantic_ir import extract_objective_prompt_features, normalize_prompt_text


ARTIFACT_PATTERNS = [
    re.compile(r"\s*Use general terms for concept case \d+\.", re.IGNORECASE),
    re.compile(r"\s*Return only evidence from the local database for SQL case \d+\.", re.IGNORECASE),
    re.compile(r"\s*SQL/API policy case \d+\.", re.IGNORECASE),
    re.compile(r"\s*SQL case \d+\.", re.IGNORECASE),
    re.compile(r"\s*API case \d+\.", re.IGNORECASE),
    re.compile(r"\s*Mixed case \d+\.", re.IGNORECASE),
    re.compile(r"\s*Ambiguous case \d+\.", re.IGNORECASE),
    re.compile(r"\s*Stress case \d+\.", re.IGNORECASE),
    re.compile(r"\s*Stress trigger \d+\.", re.IGNORECASE),
]

ADJECTIVES = [
    "activation",
    "governance",
    "schema",
    "audience",
    "dataset",
    "quality",
    "operations",
    "delivery",
    "profile",
    "catalog",
    "lifecycle",
    "readiness",
    "review",
    "platform",
    "integration",
    "validation",
    "stewardship",
    "monitoring",
    "workflow",
    "release",
]
NOUNS = [
    "handoff",
    "audit",
    "brief",
    "review",
    "checkpoint",
    "summary",
    "triage",
    "inventory",
    "runbook",
    "planning",
    "sync",
    "assessment",
    "note",
    "snapshot",
    "overview",
    "readout",
    "worksheet",
    "dashboard",
    "inspection",
    "memo",
    "packet",
    "log",
    "digest",
    "walkthrough",
    "reviewal",
]


def refine_suite(
    *,
    suite: Path | str | None = None,
    gold: Path | str | None = None,
    manifest: Path | str | None = None,
    report_dir: Path | str | None = None,
) -> dict[str, Any]:
    suite_path = Path(suite) if suite is not None else DEFAULT_CONFIG.data_dir / "benchmarks" / "dashagent_500_prompt_suite.jsonl"
    gold_path = Path(gold) if gold is not None else DEFAULT_CONFIG.data_dir / "benchmarks" / "dashagent_500_prompt_suite_gold.jsonl"
    manifest_path = Path(manifest) if manifest is not None else DEFAULT_CONFIG.data_dir / "benchmarks" / "dashagent_500_prompt_suite_manifest.json"
    reports_dir = Path(report_dir) if report_dir is not None else DEFAULT_CONFIG.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    runtime_rows = _read_jsonl(suite_path)
    gold_rows = _read_jsonl(gold_path)
    gold_by_id = {row["prompt_id"]: row for row in gold_rows}
    changes: list[dict[str, Any]] = []
    normalized_seen: set[str] = set()
    duplicate_after_refine: list[dict[str, Any]] = []

    for index, row in enumerate(runtime_rows):
        old_prompt = str(row["prompt"])
        new_prompt = _naturalize_prompt(old_prompt, row, index)
        if new_prompt != old_prompt:
            changes.append({"prompt_id": row["prompt_id"], "before": old_prompt, "after": new_prompt})
            row["prompt"] = new_prompt
            gold_row = gold_by_id.get(row["prompt_id"])
            if gold_row is not None:
                _refresh_objective_feature_expectation(gold_row, new_prompt)
        normalized = normalize_prompt_text(str(row["prompt"]))
        if normalized in normalized_seen:
            duplicate_after_refine.append({"prompt_id": row["prompt_id"], "normalized_prompt": normalized})
        normalized_seen.add(normalized)

    _write_jsonl(suite_path, runtime_rows)
    _write_jsonl(gold_path, gold_rows)
    manifest_payload: dict[str, Any] = {}
    if manifest_path.exists():
        manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_payload.update(
        {
            "naturalness_refined": True,
            "naturalness_refinement_report": str(reports_dir / "dashagent_500_prompt_suite_naturalness_refinement.json"),
            "synthetic_artifact_prompts_changed": len(changes),
            "normalized_unique_after_refine": len(normalized_seen),
        }
    )
    manifest_path.write_text(json.dumps(manifest_payload, indent=2, sort_keys=True), encoding="utf-8")

    summary = {
        "ok": not duplicate_after_refine,
        "suite": str(suite_path),
        "gold": str(gold_path),
        "manifest": str(manifest_path),
        "prompts_changed": len(changes),
        "category_counts": dict(Counter(row.get("category") for row in runtime_rows)),
        "duplicate_after_refine_count": len(duplicate_after_refine),
        "duplicate_after_refine": duplicate_after_refine[:20],
        "sample_changes": changes[:20],
    }
    (reports_dir / "dashagent_500_prompt_suite_naturalness_refinement.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (reports_dir / "dashagent_500_prompt_suite_naturalness_refinement.md").write_text(_report_md(summary), encoding="utf-8")
    return summary


def _naturalize_prompt(prompt: str, row: dict[str, Any], index: int) -> str:
    context = _context_phrase(index)
    category = str(row.get("category") or "")
    text = prompt.replace("without listing current objects", "without naming current objects")
    replacements = {
        "conceptual_no_tool": f" Keep the answer conceptual {context}.",
        "sql_only_local_snapshot": f" Use only local snapshot evidence {context}.",
        "api_only_live_platform": f" Use only safe read-only platform evidence {context}.",
        "sql_then_api_verification": f" Apply SQL first and verify only when needed {context}.",
        "mixed_conceptual_data": f" Include both the concept and requested evidence {context}.",
        "ambiguous_low_confidence": f" Resolve conservatively {context}.",
        "hard_stress": f" Keep the answer evidence-bound {context}.",
    }
    replacement = replacements.get(category, f" Keep the request evidence-bound {context}.")
    for pattern in ARTIFACT_PATTERNS:
        text = pattern.sub(replacement, text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _context_phrase(index: int) -> str:
    adjective = ADJECTIVES[index % len(ADJECTIVES)]
    noun = NOUNS[(index // len(ADJECTIVES)) % len(NOUNS)]
    return f"for the {adjective} {noun}"


def _refresh_objective_feature_expectation(gold_row: dict[str, Any], prompt: str) -> None:
    features = extract_objective_prompt_features(prompt).to_dict()
    codes: list[str] = []
    for value in features.values():
        if isinstance(value, list):
            codes.extend(str(item) for item in value)
    for step in gold_row.get("expected_observable_trace") or []:
        if step.get("stage") == "objective_features":
            step["expected_codes"] = sorted(set(codes))
            return


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")


def _report_md(summary: dict[str, Any]) -> str:
    lines = [
        "# DashAgent 500-Prompt Suite Naturalness Refinement",
        "",
        f"- ok: {str(summary['ok']).lower()}",
        f"- prompts_changed: {summary['prompts_changed']}",
        f"- duplicate_after_refine_count: {summary['duplicate_after_refine_count']}",
        "",
        "## Sample Changes",
    ]
    for item in summary["sample_changes"][:10]:
        lines.append(f"- {item['prompt_id']}: {item['after']}")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Remove benchmark self-labeling artifacts from the 500-prompt suite.")
    parser.add_argument("--suite", type=Path, default=DEFAULT_CONFIG.data_dir / "benchmarks" / "dashagent_500_prompt_suite.jsonl")
    parser.add_argument("--gold", type=Path, default=DEFAULT_CONFIG.data_dir / "benchmarks" / "dashagent_500_prompt_suite_gold.jsonl")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_CONFIG.data_dir / "benchmarks" / "dashagent_500_prompt_suite_manifest.json")
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_CONFIG.outputs_dir / "reports")
    args = parser.parse_args()
    summary = refine_suite(suite=args.suite, gold=args.gold, manifest=args.manifest, report_dir=args.report_dir)
    print(json.dumps({"ok": summary["ok"], "prompts_changed": summary["prompts_changed"]}, sort_keys=True))


if __name__ == "__main__":
    main()
