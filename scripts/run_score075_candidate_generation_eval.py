#!/usr/bin/env python
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.db import DuckDBDatabase
from dashagent.endpoint_catalog import EndpointCatalog
from dashagent.report_run import report_metadata
from dashagent.schema_index import SchemaIndex
from dashagent.targeted_candidate_generator import DEPENDENCY_NAMES, generate_targeted_candidates

OUTPUT_STEM = "score075_candidate_generation_eval"
HANDOFF_NAME = "score075_candidate_generation_handoff.md"


def main() -> int:
    config = Config.from_env(ROOT)
    payload = run_score075_candidate_generation_eval(config)
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    json_path = config.outputs_dir / f"{OUTPUT_STEM}.json"
    md_path = config.outputs_dir / f"{OUTPUT_STEM}.md"
    handoff_path = config.outputs_dir / HANDOFF_NAME
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    handoff_path.write_text(render_handoff(payload), encoding="utf-8")
    print(
        json.dumps(
            {
                "json": str(json_path),
                "markdown": str(md_path),
                "handoff": str(handoff_path),
                "total_candidates": payload["summary"]["total_candidates"],
                "leakage_failures": payload["summary"]["leakage_failure_count"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def run_score075_candidate_generation_eval(config: Config) -> dict[str, Any]:
    strict = _load_json(config.outputs_dir / "eval_results_strict.json")
    mining = _load_json(config.outputs_dir / "low_score_failure_mining_report.json")
    db = DuckDBDatabase(config)
    schema_index = SchemaIndex.build(db)
    endpoint_catalog = EndpointCatalog(config)
    examples = _load_examples(config)
    strict_rows = {
        str(row.get("query_id")): row
        for row in strict.get("rows", [])
        if row.get("strategy") == "SQL_FIRST_API_VERIFY"
    }
    mining_rows = {str(row.get("query_id")): row for row in mining.get("rows", [])}
    target_ids = list((mining.get("summary") or {}).get("top_10_target_rows") or [])
    if not target_ids:
        target_ids = list(strict_rows)[:10]

    rows = []
    family_counts: Counter[str] = Counter()
    leakage_failures = 0
    for query_id in target_ids:
        strict_row = strict_rows.get(str(query_id))
        query_text = examples.get(str(query_id))
        if not strict_row or not query_text:
            rows.append({"query_id": str(query_id), "status": "skipped", "skip_reason": "missing_strict_row_or_example"})
            continue
        trajectory = _load_trajectory(strict_row.get("output_dir"))
        candidates = generate_targeted_candidates(
            query_id=str(query_id),
            query=str(strict_row.get("query") or query_text),
            baseline_trajectory=trajectory,
            schema_index=schema_index,
            endpoint_catalog=endpoint_catalog,
            failure_row=mining_rows.get(str(query_id), {}),
            max_candidates=12,
        )
        for candidate in candidates:
            family_counts[str(candidate.get("candidate_family") or "unknown")] += 1
            if candidate.get("leakage_check_passed") is not True:
                leakage_failures += 1
        rows.append(
            {
                "query_id": str(query_id),
                "query": strict_row.get("query"),
                "current_score": strict_row.get("final_score"),
                "likely_failure_type": (mining_rows.get(str(query_id), {}) or {}).get("likely_failure_type"),
                "candidate_count": len(candidates),
                "candidate_families": sorted({str(candidate.get("candidate_family")) for candidate in candidates}),
                "candidates": candidates,
            }
        )

    dependency_status = _dependency_status(config.project_root)
    summary = {
        "branch": "codex/score075-candidate-generation",
        "baseline_commit": _git_value("rev-parse HEAD"),
        "declared_dependencies": DEPENDENCY_NAMES,
        "dependency_status": dependency_status,
        "target_rows": len(target_ids),
        "evaluated_rows": len([row for row in rows if row.get("status") != "skipped"]),
        "total_candidates": sum(int(row.get("candidate_count") or 0) for row in rows),
        "candidate_family_counts": dict(sorted(family_counts.items())),
        "leakage_failure_count": leakage_failures,
        "packaged_execution_changed": False,
        "writes_eval_outputs": False,
        "writes_final_submission": False,
        "merge_recommendation": "candidate_generation_ready_for_selector" if leakage_failures == 0 else "blocked_leakage_failures",
    }
    return {
        **report_metadata(config.outputs_dir),
        "mode": OUTPUT_STEM,
        "worker": "candidate-generation",
        "allowed_files": [
            "dashagent/targeted_candidate_generator.py",
            "scripts/run_score075_candidate_generation_eval.py",
            "tests/test_score075_candidate_generation.py",
            "outputs/score075_candidate_generation_eval.json",
            "outputs/score075_candidate_generation_eval.md",
            "outputs/score075_candidate_generation_handoff.md",
        ],
        "summary": summary,
        "rows": rows,
        "notes": [
            "This worker produces isolated/default-off candidate descriptions only.",
            "No executor, scorer, official eval, or final-submission code is modified by this report.",
            "Gold labels may score candidates later, but they are not used for candidate construction.",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# score075 Candidate Generation Eval",
        "",
        f"- Branch: `{summary['branch']}`",
        f"- Baseline commit: `{summary['baseline_commit']}`",
        f"- Target rows: {summary['target_rows']}",
        f"- Total candidates: {summary['total_candidates']}",
        f"- Leakage failures: {summary['leakage_failure_count']}",
        f"- Packaged execution changed: {summary['packaged_execution_changed']}",
        f"- Merge recommendation: `{summary['merge_recommendation']}`",
        "",
        "## Candidate Family Counts",
        "",
    ]
    if summary["candidate_family_counts"]:
        lines.extend(f"- {family}: {count}" for family, count in summary["candidate_family_counts"].items())
    else:
        lines.append("- None")
    lines.extend(["", "## Dependency Status", ""])
    for name, status in summary["dependency_status"].items():
        lines.append(f"- {name}: {status['status']} ({status['branch']})")
    lines.extend(["", "## Rows", ""])
    for row in payload["rows"]:
        if row.get("status") == "skipped":
            lines.append(f"- {row['query_id']}: skipped ({row['skip_reason']})")
        else:
            lines.append(
                f"- {row['query_id']}: {row['candidate_count']} candidates; "
                f"families={', '.join(row['candidate_families'])}"
            )
    return "\n".join(lines) + "\n"


def render_handoff(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# score075 Candidate Generation Handoff",
        "",
        "This worker stayed within candidate-generation ownership and did not edit runtime execution, scoring, or final submission paths.",
        "",
        "## Declared Dependencies",
        "",
    ]
    for name, status in summary["dependency_status"].items():
        lines.append(f"- {name}: {status['status']} via `{status['branch']}`")
    lines.extend(
        [
            "",
            "## Requested Dependency APIs",
            "",
            "- local-index: provide Parquet-derived evidence objects as `local_index_evidence` for `generate_targeted_candidates`.",
            "- endpoint-routing: provide leakage-safe rule dictionaries as `endpoint_rule_candidates`.",
            "- answer-shape: provide shape hints as `answer_shape_hints`; candidates will not change answers directly.",
            "",
            "## Safety Notes",
            "",
            "- Candidate triggers must remain reusable and cannot depend on query_id or exact full public query strings.",
            "- Local index evidence must be provenance-tagged and must not contain final answers.",
            "- This branch recommends selector/integration evaluation only; it does not promote behavior.",
        ]
    )
    return "\n".join(lines) + "\n"


def _dependency_status(project_root: Path) -> dict[str, dict[str, str]]:
    return {
        "local_index": {
            "branch": DEPENDENCY_NAMES["local_index"],
            "status": "api_missing_blocked" if not (project_root / "dashagent" / "local_knowledge_index.py").exists() else "api_available_declared_dependency",
        },
        "endpoint_routing": {
            "branch": DEPENDENCY_NAMES["endpoint_routing"],
            "status": "api_available_declared_dependency"
            if (project_root / "dashagent" / "endpoint_schema_rule_candidates.py").exists()
            else "api_missing_blocked",
        },
        "answer_shape": {
            "branch": DEPENDENCY_NAMES["answer_shape"],
            "status": "api_missing_blocked" if not (project_root / "dashagent" / "answer_shape_optimizer.py").exists() else "api_available_declared_dependency",
        },
    }


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _load_trajectory(output_dir: Any) -> dict[str, Any]:
    if not output_dir:
        return {}
    path = Path(str(output_dir)) / "trajectory.json"
    if not path.exists():
        return {}
    return _load_json(path)


def _load_examples(config: Config) -> dict[str, str]:
    payload = _load_json(config.data_json_path)
    raw = _find_example_list(payload)
    examples: dict[str, str] = {}
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        query = item.get("question") or item.get("query") or item.get("input") or item.get("nl_query")
        if not query:
            continue
        query_id = str(item.get("id") or item.get("query_id") or f"example_{index:03d}")
        examples[query_id] = str(query)
    return examples


def _find_example_list(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ["examples", "data", "queries", "dev", "public_examples"]:
            value = payload.get(key)
            if isinstance(value, list):
                return value
        dict_values = [value for value in payload.values() if isinstance(value, dict)]
        if dict_values and all(("query" in item or "question" in item) for item in dict_values):
            return dict_values
    return []


def _git_value(args: str) -> str:
    import subprocess

    try:
        return subprocess.check_output(["git", *args.split()], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


if __name__ == "__main__":
    raise SystemExit(main())
