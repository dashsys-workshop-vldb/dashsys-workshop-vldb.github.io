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
from dashagent.report_run import report_metadata
from scripts.run_official_token_reduction_eval import _load_json


def main() -> int:
    config = Config.from_env(ROOT)
    payload = analyze_schema_dataset_positive_repair(config)
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    json_path = config.outputs_dir / "schema_dataset_positive_repair_analysis.json"
    md_path = config.outputs_dir / "schema_dataset_positive_repair_analysis.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "rows": len(payload["rows"])}, indent=2, sort_keys=True))
    return 0


def analyze_schema_dataset_positive_repair(config: Config) -> dict[str, Any]:
    shadow = _load_json(config.outputs_dir / "shadow_repair_eval.json")
    rows = []
    for row in shadow.get("rows", []) or []:
        if row.get("risk_cluster") != "schema_vs_dataset_confusion":
            continue
        if float(row.get("score_delta") or 0.0) <= 0:
            continue
        safety = row.get("safety_verdict") or {}
        failed = list(safety.get("failed_checks") or [])
        rows.append(
            {
                "query_id": row.get("query_id"),
                "query": row.get("query"),
                "current_plan": {"sql": row.get("current_plan_sql"), "api": row.get("current_plan_api")},
                "repaired_plan": {"sql": row.get("repaired_plan_sql"), "api": row.get("repaired_plan_api")},
                "score_delta": row.get("score_delta"),
                "failed_safety_checks": failed,
                "why_repaired_plan_improved_score": _improvement_reason(row),
                "why_api_validation_rejected": _validation_reason(failed, safety),
                "failure_classification": _failure_classification(failed),
                "catalog_alias_gap_possible": "api_validation" in failed,
                "generalizable_rule_candidate": _generalizable_rule(failed),
                "enable_schema_dataset_repair": False,
                "behavior_changed": False,
            }
        )
    return {
        **report_metadata(config.outputs_dir),
        "mode": "schema_dataset_positive_repair_analysis",
        "report_only": True,
        "repair_execution_enabled": config.enable_gated_risk_cluster_repair_execution,
        "summary": {
            "positive_schema_dataset_rows": len(rows),
            "catalog_alias_gap_candidate_count": sum(1 for row in rows if row["catalog_alias_gap_possible"]),
            "repair_enabled": False,
        },
        "rows": rows,
        "notes": [
            "This analysis does not enable schema/dataset repair.",
            "Any endpoint alias expansion must be catalog-backed and evaluated in a later explicit task.",
        ],
    }


def _improvement_reason(row: dict[str, Any]) -> str:
    current_api = row.get("current_plan_api") or []
    repaired_api = row.get("repaired_plan_api") or []
    if current_api != repaired_api:
        return "Repaired endpoint candidate better matched the offline strict API expectation."
    return "Positive delta came from efficiency or scorer tie behavior, not a visible plan change."


def _validation_reason(failed: list[str], safety: dict[str, Any]) -> str:
    if "api_validation" in failed:
        return "; ".join((safety.get("api_validation") or {}).get("errors") or ["API validator rejected the repaired endpoint."])
    if failed:
        return f"Safety verifier rejected checks: {', '.join(failed)}."
    return "Safety verifier did not reject; selector/canary gates kept repair disabled."


def _failure_classification(failed: list[str]) -> str:
    if "api_validation" in failed and len(failed) == 1:
        return "catalog_alias_gap_or_real_endpoint_risk"
    if "api_validation" in failed:
        return "real_risk_with_catalog_validation_failure"
    if failed:
        return "verifier_strictness"
    return "no_safety_failure_but_not_enabled"


def _generalizable_rule(failed: list[str]) -> str:
    if "api_validation" in failed:
        return "Only consider schema/dataset endpoint alias repair when the target path is already present in endpoint catalog or explicit alias map."
    return "No runtime rule should be added until a catalog-backed repair passes shadow and canary gates."


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Schema/Dataset Positive Repair Analysis",
        "",
        f"- Positive schema/dataset rows: {payload['summary']['positive_schema_dataset_rows']}",
        f"- Catalog alias gap candidates: {payload['summary']['catalog_alias_gap_candidate_count']}",
        f"- Repair enabled: {payload['summary']['repair_enabled']}",
        "",
        "| Query ID | Score delta | Failed checks | Failure classification | Generalizable rule candidate |",
        "| --- | ---: | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['query_id']}` | {row['score_delta']} | {', '.join(row['failed_safety_checks'])} | "
            f"{row['failure_classification']} | {row['generalizable_rule_candidate']} |"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
