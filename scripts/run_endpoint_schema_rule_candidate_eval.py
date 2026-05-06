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
from dashagent.endpoint_catalog import EndpointCatalog
from dashagent.endpoint_schema_rule_candidates import candidate_rules, rerank_api_ids_for_family
from dashagent.report_run import report_metadata
from scripts.generate_endpoint_family_failure_report import generate_endpoint_family_failure_report
from scripts.run_hidden_style_eval import run_hidden_style_eval
from scripts.run_official_token_reduction_eval import _load_json


def main() -> int:
    config = Config.from_env(ROOT)
    payload = run_endpoint_schema_rule_candidate_eval(config)
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    json_path = config.outputs_dir / "endpoint_schema_rule_candidate_eval.json"
    md_path = config.outputs_dir / "endpoint_schema_rule_candidate_eval.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "rules": payload["summary"]["candidate_rules"]}, indent=2, sort_keys=True))
    return 0


def run_endpoint_schema_rule_candidate_eval(config: Config) -> dict[str, Any]:
    failure_report = _load_json(config.outputs_dir / "endpoint_family_failure_report.json") or generate_endpoint_family_failure_report(config)
    hidden_report = _load_json(config.outputs_dir / "hidden_style_eval.json")
    if int((hidden_report.get("summary") or {}).get("total_cases") or 0) < 40:
        hidden_report = run_hidden_style_eval(config)
    catalog = EndpointCatalog(config)
    rows = []
    for rule in candidate_rules():
        affected = [
            row
            for row in failure_report.get("rows", []) or []
            if rule.matches(str(row.get("query") or ""), str(row.get("risk_cluster") or ""), str(row.get("failure_type") or ""))
        ]
        before_by_query: dict[str, list[str]] = {}
        after_by_query: dict[str, list[str]] = {}
        before_hits = 0
        after_hits = 0
        for row in affected:
            query_id = str(row.get("query_id") or "")
            before_ids = _api_ids(row.get("top_ranked_apis") or [])
            after_ids = rerank_api_ids_for_family(before_ids, catalog.endpoints, rule.target_family)
            before_by_query[query_id] = before_ids[:5]
            after_by_query[query_id] = after_ids[:5]
            gold_api = row.get("gold_api")
            before_hits += int(_gold_in_top_k(gold_api, before_ids))
            after_hits += int(_gold_in_top_k(gold_api, after_ids))
        leakage_ok = _leakage_check(rule.to_dict())
        hidden_ok = _hidden_ok(hidden_report)
        hit_delta = after_hits - before_hits
        safe_for_future = leakage_ok and hidden_ok and hit_delta >= 0
        rows.append(
            {
                "rule_id": rule.rule_id,
                "description": rule.description,
                "targeted_failure_type": rule.targeted_failure_type,
                "affected_query_ids": sorted(before_by_query),
                "endpoint_family_before": _families_for_rows(affected),
                "endpoint_family_after": rule.target_family,
                "top_ranked_apis_before": before_by_query,
                "top_ranked_apis_after": after_by_query,
                "top_k_api_hit_delta": hit_delta,
                "strict_score_shadow_delta": 0.0,
                "token_delta": 0.0,
                "tool_delta": 0.0,
                "runtime_delta": 0.0,
                "leakage_check_passed": leakage_ok,
                "safe_for_future_canary": safe_for_future,
                "report_only": True,
                "packaged_execution_changed": False,
                "source": rule.source,
            }
        )
    safe = [row for row in rows if row["safe_for_future_canary"]]
    return {
        **report_metadata(config.outputs_dir),
        "mode": "endpoint_schema_rule_candidate_eval",
        "report_only": True,
        "packaged_execution_changed": False,
        "gold_used_for_generation": False,
        "public_query_strings_used_for_generation": False,
        "summary": {
            "candidate_rules": len(rows),
            "safe_for_future_canary_rules": len(safe),
            "affected_query_count": len({qid for row in rows for qid in row["affected_query_ids"]}),
            "total_top_k_api_hit_delta": sum(int(row["top_k_api_hit_delta"]) for row in rows),
            "hidden_style_gate_passed": _hidden_ok(hidden_report),
            "repair_execution_enabled": config.enable_gated_risk_cluster_repair_execution,
            "compact_context_enabled": config.enable_compact_context_when_schema_vote_safe,
        },
        "rows": rows,
        "notes": [
            "Rule candidates are shadow-only and are not wired into packaged execution.",
            "Gold API is used only for offline top-k hit delta measurement.",
        ],
    }


def _api_ids(items: list[Any]) -> list[str]:
    ids = []
    for item in items:
        if isinstance(item, dict):
            ids.append(str(item.get("id") or item.get("path") or item.get("url") or ""))
        else:
            ids.append(str(item))
    return [item for item in ids if item]


def _gold_in_top_k(gold_api: Any, api_ids: list[str]) -> bool:
    if not gold_api:
        return False
    text = json.dumps(gold_api, sort_keys=True).lower()
    return any(api_id.lower() in text for api_id in api_ids)


def _families_for_rows(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        family = str(row.get("predicted_endpoint_family") or "unknown")
        counts[family] = counts.get(family, 0) + 1
    return dict(sorted(counts.items()))


def _leakage_check(rule: dict[str, Any]) -> bool:
    forbidden = ["gold_sql", "gold_api", "public answer", "public query"]
    text = json.dumps(rule, sort_keys=True).lower()
    return not any(item in text for item in forbidden)


def _hidden_ok(hidden_report: dict[str, Any]) -> bool:
    summary = hidden_report.get("summary") or {}
    total = int(summary.get("total_cases") or 0)
    passed = int(summary.get("passed_cases") or 0)
    pass_rate = passed / total if total else 0.0
    return total >= 48 and pass_rate >= 0.98 and float(summary.get("family_stability_rate") or 0.0) >= 0.98 and float(summary.get("schema_stability_rate") or 0.0) >= 0.98


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Endpoint/Schema Rule Candidate Eval",
        "",
        "This is a shadow-only rule candidate report. No packaged execution behavior changed.",
        "",
        f"- Candidate rules: {summary['candidate_rules']}",
        f"- Safe for future canary rules: {summary['safe_for_future_canary_rules']}",
        f"- Affected query count: {summary['affected_query_count']}",
        f"- Total top-k API hit delta: {summary['total_top_k_api_hit_delta']}",
        f"- Hidden-style gate passed: {summary['hidden_style_gate_passed']}",
        "",
        "| Rule | Target | Affected | Top-k hit delta | Leakage OK? | Future canary? |",
        "| --- | --- | ---: | ---: | --- | --- |",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['rule_id']}` | {row['targeted_failure_type']} | {len(row['affected_query_ids'])} | "
            f"{row['top_k_api_hit_delta']} | {row['leakage_check_passed']} | {row['safe_for_future_canary']} |"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
