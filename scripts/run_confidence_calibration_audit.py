#!/usr/bin/env python
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.report_run import report_metadata
from dashagent.trajectory import redact_secrets
from scripts.run_official_token_reduction_eval import _load_json, _load_trajectory


BINS = [(0.0, 0.35), (0.35, 0.55), (0.55, 0.75), (0.75, 0.9), (0.9, 1.01)]


def main() -> int:
    config = Config.from_env(ROOT)
    payload = run_confidence_calibration_audit(config)
    print(json.dumps({"status": payload["status"], "rows": payload["total_rows"]}, indent=2, sort_keys=True))
    return 0


def run_confidence_calibration_audit(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    strict = _load_json(config.outputs_dir / "eval_results_strict.json")
    rows = [_audit_row(row) for row in strict.get("rows", []) if row.get("strategy") == "SQL_FIRST_API_VERIFY"]
    bins = _bin_rows(rows)
    payload = {
        **report_metadata(config.outputs_dir),
        "report_type": "confidence_calibration_audit",
        "status": "complete" if rows else "skipped",
        "official_score_claim": False,
        "total_rows": len(rows),
        "bins": bins,
        "expected_calibration_error_approx": _ece(bins, len(rows)),
        "high_confidence_failures": [
            _row_preview(row)
            for row in rows
            if row["router_confidence"] >= 0.75 and float(row.get("strict_score") or 0.0) < 0.6
        ][:10],
        "low_confidence_successes": [
            _row_preview(row)
            for row in rows
            if row["router_confidence"] < 0.55 and float(row.get("strict_score") or 0.0) >= 0.7
        ][:10],
        "candidate_predictors": {
            "sql_template_match_available": "reported_when_plan_contains_sql_call",
            "api_template_match_available": "reported_when_plan_contains_api_call",
            "answer_family_match_proxy": "strict answer score",
            "relevance_margin_available": "not consistently logged; report-only gap",
        },
        "rows": rows,
    }
    _write_report(reports_dir / "confidence_calibration_audit", payload, _render(payload))
    return payload


def _audit_row(row: dict[str, Any]) -> dict[str, Any]:
    trajectory = _load_trajectory(row.get("output_dir"))
    route = next((step for step in trajectory.get("steps", []) if step.get("kind") == "route"), {})
    confidence = float(route.get("confidence") or 0.0)
    strict_score = float(row.get("final_score") or 0.0)
    return redact_secrets(
        {
            "query_id": row.get("query_id"),
            "prompt": row.get("query") or trajectory.get("original_query"),
            "route_type": route.get("route_type") or trajectory.get("route_type"),
            "domain_type": route.get("domain_type") or trajectory.get("domain_type"),
            "router_confidence": round(confidence, 4),
            "strict_score": round(strict_score, 4),
            "strict_answer_score": row.get("answer_score"),
            "strict_sql_score": row.get("sql_score"),
            "strict_api_score": row.get("api_score"),
            "confidence_error_gap": round(abs(confidence - strict_score), 4),
            "sql_template_match_proxy": any(step.get("kind") == "sql_call" for step in trajectory.get("steps", [])),
            "api_template_match_proxy": any(step.get("kind") == "api_call" for step in trajectory.get("steps", [])),
        }
    )


def _bin_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        confidence = float(row.get("router_confidence") or 0.0)
        for start, end in BINS:
            if start <= confidence < end:
                grouped[f"{start:.2f}-{min(end, 1.0):.2f}"].append(row)
                break
    output = []
    for start, end in BINS:
        label = f"{start:.2f}-{min(end, 1.0):.2f}"
        members = grouped.get(label, [])
        output.append(
            {
                "bin": label,
                "row_count": len(members),
                "mean_confidence": _avg(row.get("router_confidence") for row in members),
                "average_strict_score": _avg(row.get("strict_score") for row in members),
                "average_answer_score": _avg(row.get("strict_answer_score") for row in members),
                "confidence_error_gap": round(
                    abs(_avg(row.get("router_confidence") for row in members) - _avg(row.get("strict_score") for row in members)),
                    4,
                )
                if members
                else 0.0,
            }
        )
    return output


def _ece(bins: list[dict[str, Any]], total: int) -> float:
    if not total:
        return 0.0
    return round(
        sum((item["row_count"] / total) * abs(float(item["mean_confidence"]) - float(item["average_strict_score"])) for item in bins),
        4,
    )


def _avg(values: Any) -> float:
    nums = [float(value) for value in values if isinstance(value, (int, float))]
    return round(sum(nums) / len(nums), 4) if nums else 0.0


def _row_preview(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "query_id": row.get("query_id"),
        "router_confidence": row.get("router_confidence"),
        "strict_score": row.get("strict_score"),
        "route_type": row.get("route_type"),
        "domain_type": row.get("domain_type"),
    }


def _write_report(stem: Path, payload: dict[str, Any], markdown: str) -> None:
    stem.with_suffix(".json").write_text(json.dumps(redact_secrets(payload), indent=2, sort_keys=True, default=str), encoding="utf-8")
    stem.with_suffix(".md").write_text(markdown, encoding="utf-8")


def _render(payload: dict[str, Any]) -> str:
    lines = [
        "# Confidence Calibration Audit",
        "",
        "Report-only audit of deterministic router confidence against strict outcomes. Routing is unchanged.",
        "",
        f"- Status: `{payload['status']}`",
        f"- Rows: `{payload['total_rows']}`",
        f"- Approx ECE: `{payload['expected_calibration_error_approx']}`",
        "",
        "## Confidence Bins",
        "",
    ]
    for item in payload["bins"]:
        lines.append(
            f"- `{item['bin']}` rows `{item['row_count']}`, mean confidence `{item['mean_confidence']}`, "
            f"avg strict `{item['average_strict_score']}`"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
