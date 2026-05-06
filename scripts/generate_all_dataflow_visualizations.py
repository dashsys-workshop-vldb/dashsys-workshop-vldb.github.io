#!/usr/bin/env python
from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.dataflow_visualizer import (
    attach_candidate_report_row,
    attach_compact_context_shadow_row,
    attach_risk_efficiency_shadow_row,
    attach_shadow_repair_row,
    build_dataflow_summary,
    default_visualization_dir,
    load_trajectory,
    trajectory_from_llm_row,
    write_dataflow_artifacts,
)

DEFAULT_QUERY_IDS = ["example_000", "example_004", "example_031", "list_all_journeys"]
DEFAULT_STRATEGIES = {
    "sql_first_api_verify",
    "raw_real_llm_two_tools_baseline",
    "guided_real_llm_two_tools_baseline",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a bounded set of DASHSys dataflow visualizations.")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of visualization folders to generate.")
    parser.add_argument("--query-id", action="append", default=None, help="Query id to include. May be repeated.")
    parser.add_argument("--strategy", action="append", default=None, help="Strategy/system slug or name to include. May be repeated.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing visualization files.")
    args = parser.parse_args()

    config = Config.from_env(ROOT)
    query_ids = args.query_id or DEFAULT_QUERY_IDS
    strategies = {_slug(item) for item in args.strategy} if args.strategy else set(DEFAULT_STRATEGIES)
    # The default set is intentionally bounded, so refresh it on each run to avoid
    # stale visualization files after readability/reporting changes.  The
    # --overwrite flag remains accepted for compatibility with earlier commands.
    entries = generate_all(config, query_ids=query_ids, strategies=strategies, limit=args.limit, overwrite=True)
    index_files = write_index(config.outputs_dir, entries)
    print(json.dumps({"generated": len(entries), "index": index_files, "entries": entries}, indent=2, sort_keys=True))
    return 0


def generate_all(
    config: Config,
    *,
    query_ids: list[str],
    strategies: set[str],
    limit: int | None,
    overwrite: bool,
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for trajectory_path in discover_trajectory_paths(config.outputs_dir, query_ids, strategies):
        trajectory = enrich_trajectory(load_trajectory(trajectory_path), config.outputs_dir)
        out_dir = default_visualization_dir(config.outputs_dir, trajectory)
        if "final_submission" in out_dir.parts:
            raise RuntimeError(f"Refusing to write visualization under final_submission: {out_dir}")
        files = write_dataflow_artifacts(trajectory, out_dir, overwrite=overwrite)
        entries.append(entry_from_summary(build_dataflow_summary(trajectory), files))
        if limit is not None and len(entries) >= limit:
            return entries

    for row in discover_llm_rows(config.outputs_dir, query_ids, strategies):
        trajectory = enrich_trajectory(trajectory_from_llm_row(row), config.outputs_dir)
        out_dir = default_visualization_dir(config.outputs_dir, trajectory)
        if "final_submission" in out_dir.parts:
            raise RuntimeError(f"Refusing to write visualization under final_submission: {out_dir}")
        files = write_dataflow_artifacts(trajectory, out_dir, overwrite=overwrite)
        entries.append(entry_from_summary(build_dataflow_summary(trajectory), files))
        if limit is not None and len(entries) >= limit:
            return entries
    return entries


def enrich_trajectory(trajectory: dict[str, Any], outputs_dir: Path) -> dict[str, Any]:
    trajectory = attach_candidate_report_row(trajectory, outputs_dir)
    trajectory = attach_shadow_repair_row(trajectory, outputs_dir)
    trajectory = attach_compact_context_shadow_row(trajectory, outputs_dir)
    trajectory = attach_risk_efficiency_shadow_row(trajectory, outputs_dir)
    return trajectory


def discover_trajectory_paths(outputs_dir: Path, query_ids: list[str], strategies: set[str]) -> list[Path]:
    paths: list[Path] = []
    for query_id in query_ids:
        candidates = [
            outputs_dir / "eval" / query_id,
            outputs_dir / query_id,
        ]
        for base in candidates:
            if not base.exists():
                continue
            for trajectory in sorted(base.glob("*/trajectory.json")):
                if strategies and _slug(trajectory.parent.name) not in strategies:
                    continue
                paths.append(trajectory)
    return paths


def discover_llm_rows(outputs_dir: Path, query_ids: list[str], strategies: set[str]) -> list[dict[str, Any]]:
    path = outputs_dir / "llm_baseline_eval.json"
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("skipped"):
        return []
    rows = payload.get("rows", [])
    selected: list[dict[str, Any]] = []
    wanted = set(query_ids)
    for row in rows:
        if row.get("query_id") not in wanted:
            continue
        system_slug = _slug(str(row.get("system") or ""))
        variant_slug = _slug(str(row.get("baseline_variant") or ""))
        if strategies and system_slug not in strategies and variant_slug not in strategies:
            continue
        selected.append(row)
    return selected


def entry_from_summary(summary: dict[str, Any], files: dict[str, str]) -> dict[str, Any]:
    return {
        "query_id": summary.get("query_id"),
        "query": summary.get("user_query"),
        "strategy": summary.get("strategy"),
        "variant": summary.get("variant"),
        "tool_call_count": summary.get("execution", {}).get("tool_call_count"),
        "valid_run": summary.get("execution", {}).get("valid_agent_run"),
        "evidence_status": evidence_status(summary),
        "valid_trajectory": True,
        "dry_run_api": summary.get("evidence", {}).get("dry_run_only"),
        "endpoint_repaired": summary.get("api", {}).get("endpoint_repair") not in (None, "", [], {}, "n/a - no endpoint repair recorded"),
        "zero_row_uncertain": summary.get("evidence", {}).get("zero_row_uncertain"),
        "invalid_tool_calls": summary.get("execution", {}).get("invalid_tool_calls"),
        "successful_evidence": summary.get("evidence", {}).get("successful_evidence_count"),
        "dataflow_md": files.get("md"),
        "dataflow_html": files.get("html"),
        "strategy_comparison_md": None,
    }


def write_index(outputs_dir: Path, entries: list[dict[str, Any]]) -> dict[str, str]:
    out_dir = outputs_dir / "visualizations"
    out_dir.mkdir(parents=True, exist_ok=True)
    index_md = out_dir / "index.md"
    index_html = out_dir / "index.html"
    lines = [
        "# DASHSys Dataflow Visualization Index",
        "",
        "| Query ID | Query | Strategy | Variant | Tool calls | Valid run | Evidence status | Status badges | Links |",
        "| --- | --- | --- | --- | ---: | --- | --- | --- | --- |",
    ]
    for entry in entries:
        badges = ", ".join(
            badge
            for badge, active in [
                ("valid trajectory", entry.get("valid_trajectory")),
                ("dry-run API", entry.get("dry_run_api") is True),
                ("endpoint repaired", entry.get("endpoint_repaired") is True),
                ("zero-row uncertainty", entry.get("zero_row_uncertain") is True),
                ("invalid tool calls", _has_positive(entry.get("invalid_tool_calls"))),
                ("successful evidence", _has_positive(entry.get("successful_evidence"))),
            ]
            if active
        ) or "n/a"
        md_link = _rel(out_dir, entry.get("dataflow_md"))
        html_link = _rel(out_dir, entry.get("dataflow_html"))
        comparison_path = out_dir / str(entry.get("query_id")) / "strategy_comparison.md"
        comparison_link = _rel(out_dir, comparison_path) if comparison_path.exists() else None
        links = f"[dataflow.md]({md_link}) / [dataflow.html]({html_link})"
        if comparison_link:
            links += f" / [strategy_comparison.md]({comparison_link})"
        lines.append(
            f"| `{entry.get('query_id')}` | {entry.get('query')} | `{entry.get('strategy')}` | {entry.get('variant')} | {entry.get('tool_call_count')} | {entry.get('valid_run')} | {entry.get('evidence_status')} | {badges} | {links} |"
        )
    index_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    index_html.write_text(
        "<!doctype html><html><body><pre>{}</pre></body></html>\n".format(html.escape(index_md.read_text(encoding="utf-8"))),
        encoding="utf-8",
    )
    return {"md": str(index_md), "html": str(index_html)}


def _has_positive(value: Any) -> bool:
    try:
        return float(value) > 0
    except Exception:
        return False


def evidence_status(summary: dict[str, Any]) -> str:
    evidence = summary.get("evidence", {})
    sql = evidence.get("sql_evidence_available")
    live_api = evidence.get("live_api_evidence_available")
    overall = evidence.get("overall_evidence_available")
    dry_run = evidence.get("dry_run_only")
    return f"sql={_yn(sql)}, live_api={_yn(live_api)}, overall={_yn(overall)}, dry_run={_yn(dry_run)}"


def _yn(value: Any) -> str:
    if value is True:
        return "yes"
    if value is False:
        return "no"
    if isinstance(value, str) and value.startswith("n/a -"):
        return "n/a"
    return str(value)


def _rel(base: Path, value: Any) -> str:
    if not value:
        return "#"
    try:
        return str(Path(value).resolve().relative_to(base.resolve()))
    except Exception:
        return str(value)


def _slug(text: str) -> str:
    import re

    return re.sub(r"[^a-zA-Z0-9]+", "_", text.lower()).strip("_")


if __name__ == "__main__":
    raise SystemExit(main())
