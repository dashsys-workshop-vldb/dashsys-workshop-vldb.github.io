#!/usr/bin/env python
from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.eval_harness import EvalHarness
from dashagent.reporting import query_family


GRID = [
    {"max_join_hints": 4, "max_gold_patterns": 1, "max_preview_chars": 600, "fast_path_confidence_threshold": 0.0, "api_skip_confidence_threshold": 0.0, "relevance_top_k_tables": 6, "relevance_top_k_apis": 3},
    {"max_join_hints": 4, "max_gold_patterns": 2, "max_preview_chars": 800, "fast_path_confidence_threshold": 0.2, "api_skip_confidence_threshold": 0.1, "relevance_top_k_tables": 6, "relevance_top_k_apis": 4},
    {"max_join_hints": 6, "max_gold_patterns": 1, "max_preview_chars": 800, "fast_path_confidence_threshold": 0.0, "api_skip_confidence_threshold": 0.1, "relevance_top_k_tables": 8, "relevance_top_k_apis": 3},
    {"max_join_hints": 6, "max_gold_patterns": 2, "max_preview_chars": 1000, "fast_path_confidence_threshold": 0.2, "api_skip_confidence_threshold": 0.2, "relevance_top_k_tables": 8, "relevance_top_k_apis": 4},
    {"max_join_hints": 8, "max_gold_patterns": 1, "max_preview_chars": 600, "fast_path_confidence_threshold": 0.4, "api_skip_confidence_threshold": 0.2, "relevance_top_k_tables": 10, "relevance_top_k_apis": 3},
    {"max_join_hints": 8, "max_gold_patterns": 2, "max_preview_chars": 1000, "fast_path_confidence_threshold": 0.0, "api_skip_confidence_threshold": 0.0, "relevance_top_k_tables": 8, "relevance_top_k_apis": 4},
]


def main() -> int:
    base = Config.from_env(ROOT)
    base.outputs_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for index, params in enumerate(GRID, start=1):
        run_dir = base.outputs_dir / "threshold_runs" / f"run_{index:02d}"
        cfg = replace(base, outputs_dir=run_dir, **params)
        payload = EvalHarness(cfg).run(strategies=["SQL_FIRST_API_VERIFY"])
        summary = payload["summary"]["by_strategy"]["SQL_FIRST_API_VERIFY"]
        family_summary = summarize_families(payload)
        results.append(
            {
                "run_id": f"run_{index:02d}",
                "params": params,
                "summary": summary,
                "families": family_summary,
                "leave_one_family_out": leave_one_family_out(payload),
            }
        )
    best = sorted(results, key=lambda item: (item["summary"]["avg_final_score"], item["summary"]["avg_correctness_score"], -item["summary"]["avg_estimated_tokens"]), reverse=True)[0]
    default_like = next((item for item in results if is_default_like(item["params"], base)), None)
    report = {
        "strategy": "SQL_FIRST_API_VERIFY",
        "grid_size": len(results),
        "best_run_id": best["run_id"],
        "best_params": best["params"],
        "best_summary": best["summary"],
        "default_like_run_id": default_like["run_id"] if default_like else None,
        "default_like_summary": default_like["summary"] if default_like else None,
        "recommendation": recommendation(best, default_like),
        "runs": results,
    }
    write_outputs(base, report)
    print(json.dumps({"grid_size": len(results), "best_run_id": best["run_id"], "markdown": str(base.outputs_dir / "threshold_tuning_report.md")}, indent=2, sort_keys=True))
    return 0


def summarize_families(payload: dict[str, Any]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in payload.get("rows", []):
        grouped.setdefault(query_family(row.get("query", "")), []).append(row)
    return {
        family: {
            "examples": len(rows),
            "avg_final_score": avg(row.get("final_score", 0) for row in rows),
            "avg_correctness": avg(row.get("correctness_score", 0) for row in rows),
            "avg_tokens": avg(row.get("estimated_tokens", 0) for row in rows),
        }
        for family, rows in sorted(grouped.items())
    }


def leave_one_family_out(payload: dict[str, Any]) -> dict[str, float]:
    rows = payload.get("rows", [])
    families = sorted({query_family(row.get("query", "")) for row in rows})
    summary = {}
    for family in families:
        kept = [row for row in rows if query_family(row.get("query", "")) != family]
        summary[family] = avg(row.get("final_score", 0) for row in kept)
    return summary


def avg(values: Any) -> float:
    values = [float(value) for value in values]
    return round(sum(values) / len(values), 4) if values else 0.0


def is_default_like(params: dict[str, Any], base: Config) -> bool:
    return (
        params["max_join_hints"] == base.max_join_hints
        and params["max_gold_patterns"] == base.max_gold_patterns
        and params["max_preview_chars"] == base.max_preview_chars
        and params["relevance_top_k_tables"] == base.relevance_top_k_tables
        and params["relevance_top_k_apis"] == base.relevance_top_k_apis
    )


def recommendation(best: dict[str, Any], default_like: dict[str, Any] | None) -> str:
    if default_like is None:
        return "No default-like grid point was included; keep current defaults until a stable comparison is available."
    best_summary = best["summary"]
    default_summary = default_like["summary"]
    if (
        best_summary["avg_correctness_score"] >= default_summary["avg_correctness_score"]
        and best_summary["avg_tool_call_count"] <= default_summary["avg_tool_call_count"]
        and best_summary["avg_estimated_tokens"] <= default_summary["avg_estimated_tokens"]
        and best_summary["avg_final_score"] > default_summary["avg_final_score"]
    ):
        return "Best grid point is a stable candidate, but defaults were not changed automatically."
    return "Keep current defaults; tuning did not show a stable all-metric improvement."


def write_outputs(config: Config, report: dict[str, Any]) -> None:
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    json_path = config.outputs_dir / "threshold_tuning_report.json"
    md_path = config.outputs_dir / "threshold_tuning_report.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    lines = [
        "# Threshold Tuning Report",
        "",
        f"- Strategy: `{report['strategy']}`",
        f"- Grid size: {report['grid_size']}",
        f"- Best run: `{report['best_run_id']}`",
        f"- Recommendation: {report['recommendation']}",
        "",
        "| Run | Correctness | Final | Tools | Tokens | Runtime | Params |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for run in report["runs"]:
        summary = run["summary"]
        params = run["params"]
        lines.append(
            f"| {run['run_id']} | {summary['avg_correctness_score']:.4f} | {summary['avg_final_score']:.4f} | {summary['avg_tool_call_count']:.2f} | {summary['avg_estimated_tokens']:.1f} | {summary['avg_runtime']:.4f} | {json.dumps(params, sort_keys=True)} |"
        )
    lines.extend(["", "## Leave-One-Family-Out Final Scores"])
    for family, score in report["runs"][0]["leave_one_family_out"].items():
        lines.append(f"- {family}: {score:.4f}")
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
