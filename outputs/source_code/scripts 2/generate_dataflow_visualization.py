#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.dataflow_visualizer import (
    attach_candidate_report_row,
    build_dataflow_summary,
    build_html_report,
    build_markdown_report,
    build_mermaid_graph,
    default_visualization_dir,
    load_trajectory,
    write_dataflow_artifacts,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Mermaid/Markdown/HTML/JSON dataflow visualization from a trajectory.")
    parser.add_argument("trajectory", help="Path to trajectory.json")
    parser.add_argument("--out-dir", default=None, help="Output directory. Defaults to outputs/visualizations/<query_id>/<strategy>.")
    parser.add_argument("--format", choices=["mmd", "md", "html", "json", "all"], default="all")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing visualization files.")
    args = parser.parse_args()
    config = Config.from_env(ROOT)
    trajectory = attach_candidate_report_row(load_trajectory(args.trajectory), config.outputs_dir)
    out_dir = Path(args.out_dir) if args.out_dir else default_visualization_dir(config.outputs_dir, trajectory)
    out_dir.mkdir(parents=True, exist_ok=True)
    if "final_submission" in out_dir.parts:
        raise SystemExit("Refusing to write visualization artifacts under outputs/final_submission")
    if args.format == "all":
        files = write_dataflow_artifacts(trajectory, out_dir, overwrite=True)
    else:
        files = {}
        writers = {
            "mmd": ("dataflow.mmd", build_mermaid_graph(trajectory)),
            "md": ("dataflow.md", build_markdown_report(trajectory)),
            "html": ("dataflow.html", build_html_report(trajectory)),
            "json": ("dataflow_summary.json", json.dumps(build_dataflow_summary(trajectory), indent=2, sort_keys=True, default=str)),
        }
        filename, content = writers[args.format]
        path = out_dir / filename
        if args.overwrite or not path.exists():
            path.write_text(content, encoding="utf-8")
        files[args.format] = str(path)
    print(json.dumps({"trajectory": args.trajectory, "out_dir": str(out_dir), "written": files}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
