#!/usr/bin/env python
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.trajectory import redact_secrets


REPORT_STEM = "live_tool_efficiency_audit"


def main() -> int:
    config = Config.from_env(ROOT)
    report = run_live_tool_efficiency_audit(config)
    print(
        json.dumps(
            {
                "json": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.json"),
                "markdown": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.md"),
                "avg_tool_call_count": report.get("live_mode", {}).get("avg_tool_call_count"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def run_live_tool_efficiency_audit(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    strict = _load_json(config.outputs_dir / "eval_results_strict.json")
    baseline = _load_json(reports_dir / "baselines" / "pre_live_api_eval_results_strict.json")
    generated = _load_json(reports_dir / "full_generated_prompt_suite_diagnostic.json")
    live = _strategy_summary(strict)
    pre_live = _strategy_summary(baseline)
    gen_rows = generated.get("rows") or []
    report = redact_secrets(
        {
            "report_type": REPORT_STEM,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "diagnostic_only": True,
            "promotion_allowed": False,
            "live_mode": live,
            "pre_live_or_dry_run_mode": pre_live,
            "before_after_delta": {
                "tool_call_count": _delta(live.get("avg_tool_call_count"), pre_live.get("avg_tool_call_count")),
                "runtime": _delta(live.get("avg_runtime"), pre_live.get("avg_runtime")),
                "tokens": _delta(live.get("avg_estimated_tokens"), pre_live.get("avg_estimated_tokens")),
                "final_score": _delta(live.get("avg_final_score"), pre_live.get("avg_final_score")),
            },
            "generated_prompt_diagnostic_mode": {
                "prompt_count": len(gen_rows),
                "api_call_count": sum(int(row.get("api_calls") or 0) for row in gen_rows),
                "sql_call_count": sum(int(row.get("sql_calls") or 0) for row in gen_rows),
                "live_empty_count": sum(int(row.get("live_empty_count") or 0) for row in gen_rows),
                "failure_distribution": dict(Counter(row.get("failure_category") or "unknown" for row in gen_rows)),
            },
            "efficiency_candidates": _candidates(live, pre_live, gen_rows),
            "recommendation": "keep_correctness_first; consider only guarded optional API suppression candidates",
        }
    )
    (reports_dir / f"{REPORT_STEM}.json").write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    (reports_dir / f"{REPORT_STEM}.md").write_text(_render_md(report), encoding="utf-8")
    return report


def _strategy_summary(payload: dict[str, Any]) -> dict[str, Any]:
    return (
        payload.get("summary", {})
        .get("by_strategy", {})
        .get("SQL_FIRST_API_VERIFY", {})
    )


def _delta(new: Any, old: Any) -> float | None:
    if not isinstance(new, (int, float)) or not isinstance(old, (int, float)):
        return None
    return round(float(new) - float(old), 4)


def _candidates(live: dict[str, Any], pre_live: dict[str, Any], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates = []
    if _delta(live.get("avg_runtime"), pre_live.get("avg_runtime")) not in (None, 0):
        candidates.append(
            {
                "candidate": "cache_or_suppress_low_value_optional_api_verification",
                "expected_correctness_impact": "must_be_neutral",
                "risk": "can reintroduce live API score regression if API evidence is hidden incorrectly",
            }
        )
    noisy = [row for row in rows if row.get("failure_category") == "unnecessary_api_call_noise"]
    if noisy:
        candidates.append(
            {
                "candidate": "generated_prompt_optional_api_noise_audit",
                "affected_prompts": len(noisy),
                "expected_correctness_impact": "diagnostic_only_until_strict_guard_passes",
                "risk": "generated prompts are not official score evidence",
            }
        )
    return candidates


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _render_md(report: dict[str, Any]) -> str:
    live = report.get("live_mode", {})
    delta = report.get("before_after_delta", {})
    lines = [
        "# Live Tool Efficiency Audit",
        "",
        f"- Live avg tool calls: `{live.get('avg_tool_call_count')}`",
        f"- Live avg runtime: `{live.get('avg_runtime')}`",
        f"- Live avg estimated tokens: `{live.get('avg_estimated_tokens')}`",
        f"- Tool-call delta vs pre-live: `{delta.get('tool_call_count')}`",
        f"- Runtime delta vs pre-live: `{delta.get('runtime')}`",
        "",
        "Do not sacrifice correctness for efficiency.",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
