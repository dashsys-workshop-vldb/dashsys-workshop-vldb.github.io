#!/usr/bin/env python
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.report_run import report_metadata
from dashagent.trajectory import estimate_tokens, redact_secrets
from scripts.run_official_token_reduction_eval import _load_json, _load_trajectory


REPRODUCIBILITY_REQUIRED_FIELDS = {
    "original_query",
    "final_answer",
    "steps",
    "checkpoints",
    "tool_call_count",
    "runtime",
    "estimated_tokens",
    "sql_call_count",
    "api_call_count",
}


def main() -> int:
    config = Config.from_env(ROOT)
    payload = run_token_efficiency_audit(config)
    print(json.dumps({"status": payload["status"], "rows": payload["total_rows"]}, indent=2, sort_keys=True))
    return 0


def run_token_efficiency_audit(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    strict = _load_json(config.outputs_dir / "eval_results_strict.json")
    rows = [_audit_row(row) for row in strict.get("rows", []) if row.get("strategy") == "SQL_FIRST_API_VERIFY"]
    stage_totals = Counter()
    for row in rows:
        stage_totals.update(row["token_estimate_by_stage"])
    payload = {
        **report_metadata(config.outputs_dir),
        "report_type": "token_efficiency_audit",
        "status": "complete" if rows else "skipped",
        "official_score_claim": False,
        "total_rows": len(rows),
        "summary": {
            "average_estimated_tokens": _avg(row.get("estimated_tokens") for row in rows),
            "max_estimated_tokens": max((int(row.get("estimated_tokens") or 0) for row in rows), default=0),
            "dominant_stage_tokens": dict(stage_totals.most_common(8)),
            "safe_to_compress_fields": [
                "large metadata previews after compact hashes are present",
                "repeated candidate lists after selected plan is recorded",
                "debug-only timing internals outside required runtime fields",
            ],
            "reproducibility_required_fields": sorted(REPRODUCIBILITY_REQUIRED_FIELDS),
            "reproducibility_required_fields_marked_safe_to_delete": [],
        },
        "rows": rows,
    }
    _write_report(reports_dir / "token_efficiency_audit", payload, _render(payload))
    return payload


def _audit_row(row: dict[str, Any]) -> dict[str, Any]:
    trajectory = _load_trajectory(row.get("output_dir"))
    stage_tokens = {
        "route": 0,
        "metadata": 0,
        "plan": 0,
        "tool_results": 0,
        "checkpoints": 0,
        "final_answer": estimate_tokens(str(trajectory.get("final_answer") or "")),
    }
    for step in trajectory.get("steps", []):
        kind = str(step.get("kind") or "other")
        size = estimate_tokens(json.dumps(step, sort_keys=True, default=str))
        if kind in {"route", "nlp"}:
            stage_tokens["route"] += size
        elif kind == "metadata":
            stage_tokens["metadata"] += size
        elif kind in {"plan", "optimizer"}:
            stage_tokens["plan"] += size
        elif kind in {"sql_call", "api_call"}:
            stage_tokens["tool_results"] += size
    stage_tokens["checkpoints"] = sum(
        estimate_tokens(json.dumps(checkpoint, sort_keys=True, default=str))
        for checkpoint in trajectory.get("checkpoints", [])
    )
    dominant = max(stage_tokens, key=lambda key: stage_tokens[key]) if stage_tokens else "unknown"
    return redact_secrets(
        {
            "query_id": row.get("query_id"),
            "prompt": row.get("query") or trajectory.get("original_query"),
            "estimated_tokens": int(row.get("estimated_tokens") or trajectory.get("estimated_tokens") or 0),
            "prompt_tokens": row.get("prompt_tokens"),
            "metadata_tokens": row.get("metadata_tokens"),
            "tool_call_count": row.get("tool_call_count") or trajectory.get("tool_call_count"),
            "runtime": row.get("runtime") or trajectory.get("runtime"),
            "token_estimate_by_stage": stage_tokens,
            "dominant_token_stage": dominant,
            "fields_required_for_reproducibility": sorted(field for field in REPRODUCIBILITY_REQUIRED_FIELDS if field in trajectory),
            "fields_safe_to_compress": [
                "debug-only timing internals",
                "candidate alternatives after selected candidate and validation outcome are recorded",
            ],
            "estimated_score_impact_if_compressed": "unmeasured; requires isolated token-reduction trial before promotion",
        }
    )


def _avg(values: Any) -> float:
    nums = [float(value) for value in values if isinstance(value, (int, float))]
    return round(sum(nums) / len(nums), 4) if nums else 0.0


def _write_report(stem: Path, payload: dict[str, Any], markdown: str) -> None:
    stem.with_suffix(".json").write_text(json.dumps(redact_secrets(payload), indent=2, sort_keys=True, default=str), encoding="utf-8")
    stem.with_suffix(".md").write_text(markdown, encoding="utf-8")


def _render(payload: dict[str, Any]) -> str:
    lines = [
        "# Token Efficiency Audit",
        "",
        "Report-only token audit. It does not delete reproducibility-required trajectory fields.",
        "",
        f"- Status: `{payload['status']}`",
        f"- Rows: `{payload['total_rows']}`",
        f"- Average estimated tokens: `{payload['summary']['average_estimated_tokens']}`",
        "",
        "## Dominant Stage Tokens",
        "",
    ]
    lines.extend(f"- `{key}`: `{value}`" for key, value in payload["summary"]["dominant_stage_tokens"].items())
    lines.extend(["", "## Reproducibility Fields", ""])
    lines.extend(f"- `{field}`" for field in payload["summary"]["reproducibility_required_fields"])
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
