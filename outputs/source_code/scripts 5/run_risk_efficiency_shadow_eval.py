#!/usr/bin/env python
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config


def main() -> int:
    config = Config.from_env(ROOT)
    payload = run_risk_efficiency_shadow_eval(config)
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    json_path = config.outputs_dir / "risk_efficiency_shadow_eval.json"
    md_path = config.outputs_dir / "risk_efficiency_shadow_eval.md"
    _assert_allowed_output(config.outputs_dir, json_path)
    _assert_allowed_output(config.outputs_dir, md_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "rows": len(payload.get("rows", []))}, indent=2, sort_keys=True))
    return 0


def run_risk_efficiency_shadow_eval(config: Config) -> dict[str, Any]:
    candidate_report = _load_json(config.outputs_dir / "candidate_context_report.json")
    strict_rows = _strict_sql_first_rows(config.outputs_dir)
    rows: list[dict[str, Any]] = []
    for candidate in candidate_report.get("rows", []) or []:
        risk = candidate.get("risk_efficiency_controller") or {}
        if risk.get("risk_level") not in {"low", "medium"}:
            continue
        strict = strict_rows.get(str(candidate.get("query_id") or ""), {})
        trajectory = _load_trajectory(strict.get("output_dir"))
        final_answer = trajectory.get("final_answer") or ""
        token_delta = -int(float(risk.get("token_saved_estimate") or 0))
        runtime_delta = -round(float(risk.get("runtime_saved_estimate_ms") or 0.0) / 1000.0, 6)
        rows.append(
            {
                "query_id": candidate.get("query_id"),
                "query": candidate.get("query"),
                "risk_level": risk.get("risk_level"),
                "module_skipped_by_risk": risk.get("module_skipped_by_risk", []),
                "current_score": strict.get("final_score"),
                "risk_skipping_score": strict.get("final_score"),
                "score_delta": 0.0,
                "current_tool_calls": strict.get("tool_call_count"),
                "risk_skipping_tool_calls": strict.get("tool_call_count"),
                "tool_call_delta": 0,
                "current_tokens": strict.get("estimated_tokens"),
                "token_saved_estimate": risk.get("token_saved_estimate"),
                "token_delta": token_delta,
                "current_runtime": strict.get("runtime"),
                "runtime_saved_estimate_ms": risk.get("runtime_saved_estimate_ms"),
                "runtime_delta": runtime_delta,
                "current_final_answer_preview": _preview(final_answer),
                "risk_skipping_final_answer_preview": _preview(final_answer),
                "final_answer_difference": False,
                "packaged_execution_changed": False,
                "measured_accuracy_improvement_claimed": False,
                "measured_efficiency_improvement_claimed": False,
                "estimated_savings_only": True,
                "diagnostic_only": True,
            }
        )
    return {
        "mode": "risk_efficiency_shadow_eval",
        "rows": rows,
        "summary": {
            "row_count": len(rows),
            "risk_levels": _risk_level_counts(rows),
            "avg_score_delta": _avg(row.get("score_delta") for row in rows),
            "avg_tool_call_delta": _avg(row.get("tool_call_delta") for row in rows),
            "avg_token_delta": _avg(row.get("token_delta") for row in rows),
            "avg_runtime_delta": _avg(row.get("runtime_delta") for row in rows),
            "final_answer_difference_count": sum(1 for row in rows if row.get("final_answer_difference")),
            "packaged_execution_changed": False,
            "measured_accuracy_improvement_claimed": False,
            "measured_efficiency_improvement_claimed": False,
            "behavior_changing_flags_enabled": False,
            "behavior_changing_flags_note": "No behavior-changing flags were enabled in this pass.",
        },
        "artifact_isolation": {
            "allowed_outputs": [
                "outputs/risk_efficiency_shadow_eval.json",
                "outputs/risk_efficiency_shadow_eval.md",
            ],
            "writes_eval_outputs": False,
            "writes_final_submission": False,
            "writes_packaged_query_outputs": False,
        },
        "notes": [
            "This is a replay-only risk-efficiency shadow evaluation.",
            "Token/runtime deltas are estimates from the diagnostic risk policy.",
            "Scores, tool calls, runtime, and answers are copied from current SQL_FIRST_API_VERIFY outputs.",
            "No behavior-changing flags were enabled in this pass.",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload.get("summary", {})
    lines = [
        "# Risk-Efficiency Shadow Evaluation",
        "",
        "This report simulates diagnostic-module skipping for low/medium risk rows only. It does not change packaged execution.",
        "",
        f"- Packaged execution changed: {summary.get('packaged_execution_changed')}",
        f"- Measured accuracy improvement claimed: {summary.get('measured_accuracy_improvement_claimed')}",
        f"- Measured efficiency improvement claimed: {summary.get('measured_efficiency_improvement_claimed')}",
        f"- {summary.get('behavior_changing_flags_note')}",
        f"- Rows: {summary.get('row_count')}",
        f"- Avg token delta: {summary.get('avg_token_delta')}",
        f"- Avg runtime delta: {summary.get('avg_runtime_delta')}",
        "",
        "| Query ID | Risk | Skipped modules | Current score | Replay score | Token delta | Runtime delta | Answer changed? |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in payload.get("rows", []):
        lines.append(
            f"| `{row.get('query_id')}` | {row.get('risk_level')} | {', '.join(row.get('module_skipped_by_risk', [])) or 'none'} | "
            f"{row.get('current_score')} | {row.get('risk_skipping_score')} | {row.get('token_delta')} | "
            f"{row.get('runtime_delta')} | {row.get('final_answer_difference')} |"
        )
    return "\n".join(lines) + "\n"


def _strict_sql_first_rows(outputs_dir: Path) -> dict[str, dict[str, Any]]:
    payload = _load_json(outputs_dir / "eval_results_strict.json")
    return {
        str(row.get("query_id")): row
        for row in payload.get("rows", []) or []
        if row.get("strategy") == "SQL_FIRST_API_VERIFY"
    }


def _load_trajectory(output_dir: Any) -> dict[str, Any]:
    if not output_dir:
        return {}
    path = Path(str(output_dir)) / "trajectory.json"
    if not path.exists():
        return {}
    return _load_json(path)


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _assert_allowed_output(outputs_dir: Path, path: Path) -> None:
    allowed = {
        (outputs_dir / "risk_efficiency_shadow_eval.json").resolve(),
        (outputs_dir / "risk_efficiency_shadow_eval.md").resolve(),
    }
    if path.resolve() not in allowed:
        raise RuntimeError(f"Refusing to write risk-efficiency shadow artifact outside isolated paths: {path}")


def _risk_level_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        level = str(row.get("risk_level") or "unknown")
        counts[level] = counts.get(level, 0) + 1
    return dict(sorted(counts.items()))


def _preview(text: Any, limit: int = 160) -> str:
    value = str(text or "").replace("\n", " ")
    return value[:limit] + ("..." if len(value) > limit else "")


def _avg(values: Any) -> float:
    numbers = [float(value or 0.0) for value in values]
    return round(sum(numbers) / len(numbers), 4) if numbers else 0.0


if __name__ == "__main__":
    raise SystemExit(main())
