#!/usr/bin/env python
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.dataflow_visualizer import build_dataflow_summary, load_trajectory, trajectory_from_llm_row

PREFERRED_ORDER = [
    "SQL_FIRST_API_VERIFY",
    "RAW_REAL_LLM_TWO_TOOLS_BASELINE",
    "GUIDED_REAL_LLM_TWO_TOOLS_BASELINE",
    "LLM_CONTROLLER_OPTIMIZED_AGENT",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate side-by-side strategy dataflow comparison for one query.")
    parser.add_argument("--query-id", required=True)
    parser.add_argument("--out-dir", default=None)
    args = parser.parse_args()
    config = Config.from_env(ROOT)
    summaries = collect_strategy_summaries(config.outputs_dir, args.query_id)
    out_dir = Path(args.out_dir) if args.out_dir else config.outputs_dir / "visualizations" / args.query_id
    if "final_submission" in out_dir.parts:
        raise SystemExit("Refusing to write visualization artifacts under outputs/final_submission")
    out_dir.mkdir(parents=True, exist_ok=True)
    written = write_strategy_comparison(args.query_id, summaries, out_dir)
    print(json.dumps({"query_id": args.query_id, "strategies": len(summaries), "written": written}, indent=2, sort_keys=True))
    return 0


def collect_strategy_summaries(outputs_dir: Path, query_id: str) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    deterministic_bases = [outputs_dir / "eval" / query_id, outputs_dir / query_id]
    for base in deterministic_bases:
        if not base.exists():
            continue
        for path in sorted(base.glob("*/trajectory.json")):
            trajectory = load_trajectory(path)
            summary = build_dataflow_summary(trajectory)
            summary["source_path"] = str(path)
            summaries.append(summary)
    llm_path = outputs_dir / "llm_baseline_eval.json"
    if llm_path.exists():
        payload = json.loads(llm_path.read_text(encoding="utf-8"))
        if not payload.get("skipped"):
            for row in payload.get("rows", []):
                if row.get("query_id") == query_id:
                    summary = build_dataflow_summary(trajectory_from_llm_row(row))
                    summary["source_path"] = str(llm_path)
                    summaries.append(summary)
    return sorted(summaries, key=lambda item: _order_key(str(item.get("strategy"))))


def write_strategy_comparison(query_id: str, summaries: list[dict[str, Any]], out_dir: Path) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    mmd = build_strategy_mermaid(query_id, summaries)
    md = build_strategy_markdown(query_id, summaries, mmd)
    html_doc = """<!doctype html>
<html><head><meta charset="utf-8"><title>DASHSys Strategy Comparison</title>
<script type="module">import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs'; mermaid.initialize({startOnLoad:true});</script>
<style>body{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;margin:32px;line-height:1.45} pre{background:#f6f8fa;padding:12px;overflow:auto;white-space:pre-wrap} table{border-collapse:collapse;width:100%;margin:12px 0} td,th{border:1px solid #d0d7de;padding:6px;vertical-align:top}</style>
</head><body><div class="mermaid">""" + html.escape(mmd) + "</div><pre>" + html.escape(md) + "</pre></body></html>\n"
    files = {
        "mmd": out_dir / "strategy_comparison.mmd",
        "md": out_dir / "strategy_comparison.md",
        "html": out_dir / "strategy_comparison.html",
    }
    files["mmd"].write_text(mmd, encoding="utf-8")
    files["md"].write_text(md, encoding="utf-8")
    files["html"].write_text(html_doc, encoding="utf-8")
    return {key: str(path) for key, path in files.items()}


def build_strategy_markdown(query_id: str, summaries: list[dict[str, Any]], mmd: str) -> str:
    lines = [
        f"# Strategy Comparison: {query_id}",
        "",
        "This view compares deterministic, Raw real LLM, Guided real LLM, and optimized-controller paths when those artifacts exist.",
        "",
        "```mermaid",
        mmd.strip(),
        "```",
        "",
        "| Variant | Strategy | Route | Context mode | SQL preview | API endpoint | Tool calls | Invalid calls | Endpoint repairs | SQL evidence | Live API evidence | Overall evidence | Dry-run only | Runtime | Tokens | Final answer preview |",
        "| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | --- | --- | --- | --- | ---: | ---: | --- |",
    ]
    if not summaries:
        lines.append("| n/a | n/a | n/a | n/a | n/a | n/a | 0 | 0 | 0 | n/a | n/a | n/a | n/a | 0 | 0 | n/a |")
    for summary in summaries:
        lines.append(
            "| {} | `{}` | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
                _md(_display_variant(summary)),
                _md(summary.get("strategy")),
                _md(summary.get("route", {}).get("mode")),
                _md(summary.get("context", {}).get("context_mode")),
                _md(summary.get("sql", {}).get("preview")),
                _md(summary.get("api", {}).get("endpoint")),
                _md(summary.get("execution", {}).get("tool_call_count")),
                _md(summary.get("execution", {}).get("invalid_tool_calls")),
                _md(summary.get("execution", {}).get("endpoint_repairs")),
                _md(summary.get("evidence", {}).get("sql_evidence_available")),
                _md(summary.get("evidence", {}).get("live_api_evidence_available")),
                _md(summary.get("evidence", {}).get("overall_evidence_available")),
                _md(summary.get("evidence", {}).get("dry_run_only")),
                _md(summary.get("metrics", {}).get("runtime")),
                _md(summary.get("metrics", {}).get("estimated_tokens") or summary.get("metrics", {}).get("prompt_context_tokens")),
                _md(summary.get("answer", {}).get("final_answer_preview")),
            )
        )
    return "\n".join(lines) + "\n"


def build_strategy_mermaid(query_id: str, summaries: list[dict[str, Any]]) -> str:
    lines = ["flowchart LR", f"  prompt[\"Query<br/>{_m(query_id)}\"]"]
    for index, summary in enumerate(summaries or []):
        name = _display_variant(summary)
        node_prefix = f"s{index}"
        lines.extend(
            [
                f"  prompt --> {node_prefix}_route[\"{_m(name)}<br/>route={_m(summary.get('route', {}).get('mode'))}\"]",
                f"  {node_prefix}_route --> {node_prefix}_tools[\"tools={_m(summary.get('execution', {}).get('tool_call_count'))}<br/>invalid={_m(summary.get('execution', {}).get('invalid_tool_calls'))}\"]",
                f"  {node_prefix}_tools --> {node_prefix}_evidence[\"sql={_m(_yn(summary.get('evidence', {}).get('sql_evidence_available')))}<br/>live_api={_m(_yn(summary.get('evidence', {}).get('live_api_evidence_available')))}<br/>dry_run={_m(_yn(summary.get('evidence', {}).get('dry_run_only')))}\"]",
                f"  {node_prefix}_evidence --> {node_prefix}_answer[\"answer<br/>{_m(summary.get('answer', {}).get('final_answer_preview'))}\"]",
            ]
        )
    if not summaries:
        lines.append('  prompt --> missing["n/a - no strategy artifacts found"]')
    return "\n".join(lines) + "\n"


def _display_variant(summary: dict[str, Any]) -> str:
    variant = str(summary.get("variant") or "")
    strategy = str(summary.get("strategy") or "")
    if variant == "Raw" or "RAW_REAL_LLM" in strategy:
        return "Raw"
    if variant == "Guided" or "GUIDED_REAL_LLM" in strategy:
        return "Guided"
    if "LLM_CONTROLLER_OPTIMIZED_AGENT" in strategy:
        return "Optimized Controller"
    if "SQL_FIRST_API_VERIFY" in strategy:
        return "SQL_FIRST_API_VERIFY"
    return strategy or "n/a"


def _order_key(strategy: str) -> tuple[int, str]:
    for index, preferred in enumerate(PREFERRED_ORDER):
        if preferred in strategy:
            return (index, strategy)
    return (len(PREFERRED_ORDER), strategy)


def _md(value: Any) -> str:
    text = "n/a" if value in (None, "") else str(value)
    return text.replace("|", "\\|").replace("\n", " ")[:600]


def _m(value: Any) -> str:
    text = "n/a" if value in (None, "") else str(value)
    return html.escape(re.sub(r"\s+", " ", text))[:100]


def _yn(value: Any) -> str:
    if value is True:
        return "yes"
    if value is False:
        return "no"
    if isinstance(value, str) and value.startswith("n/a -"):
        return "n/a"
    return str(value)


if __name__ == "__main__":
    raise SystemExit(main())
