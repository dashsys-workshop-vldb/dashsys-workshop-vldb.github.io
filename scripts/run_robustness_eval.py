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


MODES = [
    ("baseline", {}),
    ("drop_fast_paths", {"disable_fast_paths": True}),
    ("drop_gold_patterns", {"disable_gold_patterns": True}),
    ("drop_one_join_hint", {"drop_one_join_hint": True}),
    ("drop_context_cards", {"disable_context_cards": True}),
    ("drop_api_fallback_templates", {"disable_api_fallback_templates": True}),
]


def main() -> int:
    base = Config.from_env(ROOT)
    base.outputs_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for mode, overrides in MODES:
        run_dir = base.outputs_dir / "robustness_runs" / mode
        cfg = replace(base, outputs_dir=run_dir, **overrides)
        payload = EvalHarness(cfg).run(strategies=["SQL_FIRST_API_VERIFY"])
        summary = payload["summary"]["by_strategy"]["SQL_FIRST_API_VERIFY"]
        results.append({"mode": mode, "overrides": overrides, "summary": summary})
    baseline = results[0]["summary"]
    for item in results:
        item["delta_vs_baseline"] = {
            "correctness": round(item["summary"]["avg_correctness_score"] - baseline["avg_correctness_score"], 4),
            "final": round(item["summary"]["avg_final_score"] - baseline["avg_final_score"], 4),
            "tokens": round(item["summary"]["avg_estimated_tokens"] - baseline["avg_estimated_tokens"], 4),
            "tool_calls": round(item["summary"]["avg_tool_call_count"] - baseline["avg_tool_call_count"], 4),
        }
        item["risk"] = classify_risk(item["delta_vs_baseline"])
    report = {"strategy": "SQL_FIRST_API_VERIFY", "modes": results, "summary": summarize_risks(results)}
    write_outputs(base, report)
    print(json.dumps({"modes": len(results), "markdown": str(base.outputs_dir / "robustness_eval.md")}, indent=2, sort_keys=True))
    return 0


def classify_risk(delta: dict[str, float]) -> str:
    if delta["correctness"] <= -0.03 or delta["final"] <= -0.03:
        return "high"
    if delta["correctness"] < 0 or delta["final"] < 0:
        return "medium"
    return "low"


def summarize_risks(results: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "high_risk_modes": [item["mode"] for item in results if item["risk"] == "high"],
        "medium_risk_modes": [item["mode"] for item in results if item["risk"] == "medium"],
        "low_risk_modes": [item["mode"] for item in results if item["risk"] == "low"],
    }


def write_outputs(config: Config, report: dict[str, Any]) -> None:
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    json_path = config.outputs_dir / "robustness_eval.json"
    md_path = config.outputs_dir / "robustness_eval.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    lines = [
        "# Robustness Dropout Evaluation",
        "",
        f"- Strategy: `{report['strategy']}`",
        f"- High-risk modes: {', '.join(report['summary']['high_risk_modes']) or 'none'}",
        f"- Medium-risk modes: {', '.join(report['summary']['medium_risk_modes']) or 'none'}",
        "",
        "| Mode | Correctness | Final | Tools | Tokens | Delta Correctness | Delta Final | Risk |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for item in report["modes"]:
        summary = item["summary"]
        delta = item["delta_vs_baseline"]
        lines.append(
            f"| {item['mode']} | {summary['avg_correctness_score']:.4f} | {summary['avg_final_score']:.4f} | {summary['avg_tool_call_count']:.2f} | {summary['avg_estimated_tokens']:.1f} | {delta['correctness']:.4f} | {delta['final']:.4f} | {item['risk']} |"
        )
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
