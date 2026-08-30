#!/usr/bin/env python
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:  # noqa: E402
    from scripts.visualization_report_helpers import (
        VIS_DIR,
        how_to_read_page,
        load_json,
        required_visualization_files,
        table,
        write_json,
        write_md,
    )
    from scripts.generate_end_to_end_system_dataflow import generate_end_to_end_system_dataflow
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    from visualization_report_helpers import (
        VIS_DIR,
        how_to_read_page,
        load_json,
        required_visualization_files,
        table,
        write_json,
        write_md,
    )
    from generate_end_to_end_system_dataflow import generate_end_to_end_system_dataflow


def main() -> int:
    generate_end_to_end_system_dataflow()
    entries = build_entries()
    state = load_json("outputs/visualizations/current_system_state.json", {})
    catalog = load_json("outputs/visualizations/technique_catalog.json", {})
    llm_baseline = load_json("outputs/llm_baseline_eval_report.json", {})
    payload = {
        "summary": {
            "visualization_root": str(VIS_DIR),
            "required_files_total": len(entries),
            "required_files_existing": sum(1 for entry in entries if entry["exists"]),
            "technique_count": catalog.get("total"),
            "packaged_strict_final_score": state.get("packaged_strict_final_score"),
            "best_isolated_score": state.get("best_isolated_score"),
            "final_recommendation": state.get("final_recommendation"),
            "llm_baseline_framework": llm_baseline.get("framework", "generic_sdk_llm_baseline"),
            "llm_baseline_backend": llm_baseline.get("backend_name", "unavailable"),
            "llm_baseline_recommendation": llm_baseline.get("recommendation", "unavailable"),
        },
        "entries": entries,
    }
    write_json(VIS_DIR / "index.json", payload)
    write_md(VIS_DIR / "index.md", build_markdown(payload))
    print({"json": str(VIS_DIR / "index.json"), "markdown": str(VIS_DIR / "index.md"), "entries": len(entries)})
    return 0


def build_entries() -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for filename in required_visualization_files():
        path = VIS_DIR / filename
        will_be_written_by_this_script = filename in {"index.md", "index.json"}
        suffix = path.suffix.lower()
        kind = (
            "markdown"
            if suffix == ".md"
            else "html"
            if suffix == ".html"
            else "svg"
            if suffix == ".svg"
            else "json"
        )
        entries.append(
            {
                "file": filename,
                "path": str(path),
                "exists": path.exists() or will_be_written_by_this_script,
                "kind": kind,
                "link": filename if suffix in {".md", ".html", ".svg"} else None,
            }
        )
    return entries


def build_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    supervisor_files = {
        "executive_dashboard.md",
        "end_to_end_system_dataflow.html",
        "full_project_dataflow.svg",
        "full_project_dataflow.md",
        "project_architecture_c4.md",
        "end_to_end_pipeline_mermaid.md",
        "live_adobe_api_status_mermaid.md",
        "report_generation_map.md",
        "sql_prompt_storyboard_primary.md",
        "prompt_storyboard_primary.md",
        "prompt_transformation_primary.md",
        "end_to_end_execution_primary.md",
        "technique_pipeline_map.md",
        "technique_visual_cards.md",
        "system_status_dashboard.md",
        "score_bottleneck_dashboard.md",
    }
    supervisor_order = [
        "executive_dashboard.md",
        "end_to_end_system_dataflow.html",
        "sql_prompt_storyboard_primary.md",
        "system_status_dashboard.md",
        "technique_visual_cards.md",
        "prompt_transformation_primary.md",
        "end_to_end_execution_primary.md",
        "full_project_dataflow.svg",
        "full_project_dataflow.md",
        "project_architecture_c4.md",
        "end_to_end_pipeline_mermaid.md",
        "live_adobe_api_status_mermaid.md",
        "report_generation_map.md",
        "technique_pipeline_map.md",
        "score_bottleneck_dashboard.md",
    ]
    supervisor_rows = []
    detail_rows = []
    supervisor_row_by_file = {}
    for entry in payload["entries"]:
        link = f"[{entry['file']}]({entry['link']})" if entry.get("link") else entry["file"]
        row = [link, entry["kind"], entry["exists"]]
        if entry["file"] in supervisor_files:
            supervisor_row_by_file[entry["file"]] = row
        else:
            detail_rows.append(row)
    supervisor_rows = [supervisor_row_by_file[name] for name in supervisor_order if name in supervisor_row_by_file]
    supervisor_rows.extend(
        row
        for filename, row in supervisor_row_by_file.items()
        if filename not in set(supervisor_order)
    )
    return "\n".join(
        [
            "# DASHSys Visualization Index",
            "",
            "This index links the supervisor-facing visualization suite. Every artifact is generated under `outputs/visualizations/` and is based on current repo reports/trajectories.",
            "",
            how_to_read_page("Supervisor-Facing Pages list"),
            "",
            "## At a Glance",
            "",
            table(
                ["Field", "Value"],
                [
                    ["Required files", f"{summary['required_files_existing']}/{summary['required_files_total']}"],
                    ["Technique count", summary.get("technique_count")],
                    ["Packaged strict final score", summary.get("packaged_strict_final_score")],
                    ["Best isolated score", summary.get("best_isolated_score")],
                    ["Final recommendation", summary.get("final_recommendation")],
                    ["LLM baseline framework", summary.get("llm_baseline_framework")],
                    ["Current LLM backend", summary.get("llm_baseline_backend")],
                    ["LLM baseline recommendation", summary.get("llm_baseline_recommendation")],
                ],
                ),
            "",
            "## Supervisor-Facing Pages",
            "",
            "Start here. These pages are diagram/card-first and designed for a quick walkthrough with a supervisor.",
            "",
            table(["Artifact", "Kind", "Exists"], supervisor_rows),
            "",
            "## Detailed Reference Views",
            "",
            table(["Artifact", "Kind", "Exists"], detail_rows),
            "",
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())
