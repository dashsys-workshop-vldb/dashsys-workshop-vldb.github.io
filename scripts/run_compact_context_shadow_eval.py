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
    payload = run_compact_context_shadow_eval(config)
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    json_path = config.outputs_dir / "compact_context_shadow_eval.json"
    md_path = config.outputs_dir / "compact_context_shadow_eval.md"
    _assert_allowed_output(config.outputs_dir, json_path)
    _assert_allowed_output(config.outputs_dir, md_path)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "rows": len(payload.get("rows", []))}, indent=2, sort_keys=True))
    return 0


def run_compact_context_shadow_eval(config: Config) -> dict[str, Any]:
    candidate_report = _load_json(config.outputs_dir / "candidate_context_report.json")
    strict_rows = _strict_sql_first_rows(config.outputs_dir)
    rows: list[dict[str, Any]] = []
    for candidate in candidate_report.get("rows", []) or []:
        vote = candidate.get("schema_context_vote") or {}
        if vote.get("schema_vote_agreement") is not True or vote.get("compact_context_safe") is not True:
            continue
        strict = strict_rows.get(str(candidate.get("query_id") or ""), {})
        trajectory = _load_trajectory(strict.get("output_dir"))
        final_answer = trajectory.get("final_answer") or ""
        token_delta = int(vote.get("compact_context_tokens") or 0) - int(vote.get("fallback_context_tokens") or 0)
        rows.append(
            {
                "query_id": candidate.get("query_id"),
                "query": candidate.get("query"),
                "current_score": strict.get("final_score"),
                "compact_context_score": strict.get("final_score"),
                "score_delta": 0.0,
                "current_tool_calls": strict.get("tool_call_count"),
                "compact_context_tool_calls": strict.get("tool_call_count"),
                "tool_call_delta": 0,
                "current_tokens": strict.get("estimated_tokens"),
                "compact_context_tokens": vote.get("compact_context_tokens"),
                "fallback_context_tokens": vote.get("fallback_context_tokens"),
                "token_delta": token_delta,
                "token_delta_source": "schema_context_vote compact_context_tokens - fallback_context_tokens",
                "current_runtime": strict.get("runtime"),
                "compact_context_runtime": strict.get("runtime"),
                "runtime_delta": 0.0,
                "runtime_delta_source": "replayed current trajectory; no measured execution change",
                "current_final_answer_preview": _preview(final_answer),
                "compact_context_final_answer_preview": _preview(final_answer),
                "final_answer_difference": False,
                "schema_vote_agreement": vote.get("schema_vote_agreement"),
                "compact_context_safe": vote.get("compact_context_safe"),
                "fallback_reason": vote.get("fallback_reason"),
                "packaged_execution_changed": False,
                "measured_accuracy_improvement_claimed": False,
                "measured_efficiency_improvement_claimed": False,
                "diagnostic_only": True,
            }
        )
    return {
        "mode": "compact_context_shadow_eval",
        "rows": rows,
        "summary": {
            "row_count": len(rows),
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
                "outputs/compact_context_shadow_eval.json",
                "outputs/compact_context_shadow_eval.md",
            ],
            "writes_eval_outputs": False,
            "writes_final_submission": False,
            "writes_packaged_query_outputs": False,
        },
        "notes": [
            "This is a replay-only compact-context shadow evaluation.",
            "Scores, tool calls, runtime, and answers are copied from current SQL_FIRST_API_VERIFY outputs.",
            "Token deltas come from schema context vote estimates, not measured packaged execution.",
            "No behavior-changing flags were enabled in this pass.",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload.get("summary", {})
    lines = [
        "# Compact Context Shadow Evaluation",
        "",
        "This report is replay-only and does not change packaged SQL_FIRST_API_VERIFY execution.",
        "",
        f"- Packaged execution changed: {summary.get('packaged_execution_changed')}",
        f"- Measured accuracy improvement claimed: {summary.get('measured_accuracy_improvement_claimed')}",
        f"- Measured efficiency improvement claimed: {summary.get('measured_efficiency_improvement_claimed')}",
        f"- {summary.get('behavior_changing_flags_note')}",
        f"- Rows: {summary.get('row_count')}",
        f"- Avg token delta: {summary.get('avg_token_delta')}",
        "",
        "| Query ID | Current score | Compact score | Token delta | Runtime delta | Tool delta | Answer changed? |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in payload.get("rows", []):
        lines.append(
            f"| `{row.get('query_id')}` | {row.get('current_score')} | {row.get('compact_context_score')} | "
            f"{row.get('token_delta')} | {row.get('runtime_delta')} | {row.get('tool_call_delta')} | {row.get('final_answer_difference')} |"
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
        (outputs_dir / "compact_context_shadow_eval.json").resolve(),
        (outputs_dir / "compact_context_shadow_eval.md").resolve(),
    }
    if path.resolve() not in allowed:
        raise RuntimeError(f"Refusing to write compact-context shadow artifact outside isolated paths: {path}")


def _preview(text: Any, limit: int = 160) -> str:
    value = str(text or "").replace("\n", " ")
    return value[:limit] + ("..." if len(value) > limit else "")


def _avg(values: Any) -> float:
    numbers = [float(value or 0.0) for value in values]
    return round(sum(numbers) / len(numbers), 4) if numbers else 0.0


if __name__ == "__main__":
    raise SystemExit(main())
