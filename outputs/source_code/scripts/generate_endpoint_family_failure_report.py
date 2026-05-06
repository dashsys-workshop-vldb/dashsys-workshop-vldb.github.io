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
from dashagent.endpoint_family_ranker import endpoint_family_for_endpoint
from dashagent.eval_harness import EvalHarness, generated_api_calls
from dashagent.report_run import report_metadata
from scripts.generate_candidate_context_report import generate_candidate_context_report
from scripts.run_official_token_reduction_eval import _load_json, _load_trajectory


RISK_CLUSTERS = {
    "missing_gold_api_in_top_k",
    "zero_score_margin",
    "batch_endpoint_confusion",
    "tag_api_confusion",
    "broad_domain_api_confusion",
    "schema_vs_dataset_confusion",
}


def main() -> int:
    config = Config.from_env(ROOT)
    payload = generate_endpoint_family_failure_report(config)
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    json_path = config.outputs_dir / "endpoint_family_failure_report.json"
    md_path = config.outputs_dir / "endpoint_family_failure_report.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "rows": len(payload["rows"])}, indent=2, sort_keys=True))
    return 0


def generate_endpoint_family_failure_report(config: Config) -> dict[str, Any]:
    candidate_report = _load_json(config.outputs_dir / "candidate_context_report.json") or generate_candidate_context_report(config)
    strict_rows = {
        str(row.get("query_id")): row
        for row in (_load_json(config.outputs_dir / "eval_results_strict.json").get("rows") or [])
        if row.get("strategy") == "SQL_FIRST_API_VERIFY"
    }
    examples = {example.query_id: example for example in EvalHarness(config).load_examples()}
    rows = []
    for row in candidate_report.get("rows", []) or []:
        risk_cluster = _risk_cluster(row)
        if risk_cluster not in RISK_CLUSTERS and not _is_risky(row):
            continue
        query_id = str(row.get("query_id") or "")
        strict = strict_rows.get(query_id, {})
        trajectory = _load_trajectory(strict.get("output_dir"))
        current_api = generated_api_calls(trajectory)
        endpoint = row.get("endpoint_family_ranking") or {}
        top_ranked = endpoint.get("top_ranked_apis") or []
        family_confidence = endpoint.get("endpoint_family_confidence")
        weighted_agreement = bool((row.get("hybrid_candidate_scoring") or {}).get("active"))
        rrf_scores = (row.get("hybrid_candidate_scoring") or {}).get("reciprocal_rank_fusion_scores") or {}
        rows.append(
            {
                "query_id": query_id,
                "query": row.get("query"),
                "risk_cluster": risk_cluster,
                "predicted_endpoint_family": endpoint.get("endpoint_family"),
                "top_ranked_apis": top_ranked[:5],
                "current_api": current_api,
                "gold_api": examples.get(query_id).gold_api if examples.get(query_id) else None,
                "gold_api_report_only": True,
                "endpoint_family_confidence": family_confidence,
                "weighted_rrf_agreement": weighted_agreement and bool(rrf_scores or top_ranked),
                "value_match_used": (row.get("value_to_api_ranking") or {}).get("value_match_used_for_api_ranking", False),
                "schema_vote_agreement": row.get("schema_vote_agreement"),
                "failure_type": _failure_type(row, current_api, top_ranked),
                "suggested_non_gold_rule_improvement": _suggestion(risk_cluster, endpoint.get("endpoint_family")),
                "generation_logic_changed": False,
            }
        )
    failure_counts: dict[str, int] = {}
    for row in rows:
        failure_counts[row["failure_type"]] = failure_counts.get(row["failure_type"], 0) + 1
    return {
        **report_metadata(config.outputs_dir),
        "mode": "endpoint_family_failure_report",
        "report_only": True,
        "gold_used_for_generation": False,
        "summary": {
            "risky_rows": len(rows),
            "failure_type_counts": failure_counts,
            "risk_cluster_counts": _counts(row.get("risk_cluster") for row in rows),
        },
        "rows": rows,
        "notes": [
            "Gold API appears only as eval-report context and is never used to generate endpoint rules.",
            "Suggested improvements are phrased as reusable domain/path-pattern rules.",
        ],
    }


def _risk_cluster(row: dict[str, Any]) -> str:
    repair = row.get("gated_risk_cluster_repair") or {}
    if repair.get("risk_cluster"):
        return str(repair["risk_cluster"])
    if row.get("missing_gold_apis"):
        return "missing_gold_api_in_top_k"
    if float(row.get("score_margin") or 0.0) == 0.0:
        return "zero_score_margin"
    query = str(row.get("query") or "").lower()
    if "batch" in query and ("file" in query or "download" in query):
        return "batch_endpoint_confusion"
    if "tag" in query or "category" in query:
        return "tag_api_confusion"
    if "schema" in query and "dataset" in query:
        return "schema_vs_dataset_confusion"
    return "broad_domain_api_confusion"


def _is_risky(row: dict[str, Any]) -> bool:
    return bool(row.get("missing_gold_apis") or row.get("missing_gold_tables") or float(row.get("confidence") or 0.0) < 0.4)


def _failure_type(row: dict[str, Any], current_api: list[dict[str, Any]], top_ranked: list[dict[str, Any]]) -> str:
    if row.get("missing_gold_apis"):
        return "gold_api_missing_from_top_k"
    if not top_ranked:
        return "no_endpoint_ranked"
    if current_api:
        current_family = endpoint_family_for_endpoint(current_api[0].get("path") or current_api[0].get("url") or "")
        top_family = top_ranked[0].get("endpoint_family")
        if current_family != top_family:
            return "executed_endpoint_family_differs_from_ranked_family"
    if float(row.get("score_margin") or 0.0) == 0.0:
        return "zero_candidate_score_margin"
    return "low_confidence_or_broad_domain"


def _suggestion(cluster: str, family: Any) -> str:
    suggestions = {
        "batch_endpoint_confusion": "Strengthen reusable batch ID + file/failure path-pattern rules.",
        "tag_api_confusion": "Separate tag list/detail/category vocabulary using endpoint catalog path shapes.",
        "schema_vs_dataset_confusion": "Clarify schema detail versus dataset list intent using schema-dataset relation vocabulary.",
        "missing_gold_api_in_top_k": "Add endpoint-family coverage diagnostics for catalog-backed families with low top-k recall.",
        "zero_score_margin": "Improve deterministic tie-breaks using endpoint family confidence and schema-link confidence.",
        "broad_domain_api_confusion": "Route broad platform questions through domain vocabulary before endpoint-specific boosts.",
    }
    return suggestions.get(cluster, f"Review reusable endpoint-family signals for {family or 'unknown'} without gold-derived rules.")


def _counts(values: Any) -> dict[str, int]:
    result: dict[str, int] = {}
    for value in values:
        key = str(value)
        result[key] = result.get(key, 0) + 1
    return dict(sorted(result.items()))


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Endpoint-Family Failure Report",
        "",
        f"- Risky rows: {payload['summary']['risky_rows']}",
        f"- Failure types: {payload['summary']['failure_type_counts']}",
        "",
        "| Query ID | Cluster | Family | Confidence | Failure type | Suggested non-gold improvement |",
        "| --- | --- | --- | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['query_id']}` | {row['risk_cluster']} | {row['predicted_endpoint_family']} | "
            f"{row['endpoint_family_confidence']} | {row['failure_type']} | {row['suggested_non_gold_rule_improvement']} |"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
