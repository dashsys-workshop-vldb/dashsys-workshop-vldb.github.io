#!/usr/bin/env python
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from visualization_report_helpers import (  # noqa: E402
    VIS_DIR,
    load_json,
    required_visualization_files,
    table,
    write_json,
    write_md,
)


def main() -> int:
    entries = build_entries()
    state = load_json("outputs/visualizations/current_system_state.json", {})
    catalog = load_json("outputs/visualizations/technique_catalog.json", {})
    payload = {
        "summary": {
            "visualization_root": str(VIS_DIR),
            "required_files_total": len(entries),
            "required_files_existing": sum(1 for entry in entries if entry["exists"]),
            "technique_count": catalog.get("total"),
            "packaged_strict_final_score": state.get("packaged_strict_final_score"),
            "best_isolated_score": state.get("best_isolated_score"),
            "final_recommendation": state.get("final_recommendation"),
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
        entries.append(
            {
                "file": filename,
                "path": str(path),
                "exists": path.exists() or will_be_written_by_this_script,
                "kind": "markdown" if filename.endswith(".md") else "json",
                "link": filename if filename.endswith(".md") else None,
            }
        )
    return entries


def build_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    rows = []
    for entry in payload["entries"]:
        link = f"[{entry['file']}]({entry['link']})" if entry.get("link") else entry["file"]
        rows.append([link, entry["kind"], entry["exists"]])
    return "\n".join(
        [
            "# DASHSys Visualization Index",
            "",
            "This index links the supervisor-facing visualization suite. Every artifact is generated under `outputs/visualizations/` and is based on current repo reports/trajectories.",
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
                ],
            ),
            "",
            "## Core Views",
            "",
            table(["Artifact", "Kind", "Exists"], rows),
            "",
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())
