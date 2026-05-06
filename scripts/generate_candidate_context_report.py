#!/usr/bin/env python
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.candidate_context_builder import build_candidate_context, build_full_schema_context, choose_context_mode
from dashagent.config import Config
from dashagent.endpoint_catalog import EndpointCatalog
from dashagent.eval_harness import EvalHarness, extract_api_calls
from dashagent.executor import AgentExecutor
from dashagent.risk_efficiency_controller import classify_candidate_risk
from dashagent.schema_context_voter import vote_schema_contexts
from dashagent.trajectory import estimate_tokens


def main() -> int:
    config = Config.from_env(ROOT)
    report = generate_candidate_context_report(config)
    json_path = config.outputs_dir / "candidate_context_report.json"
    md_path = config.outputs_dir / "candidate_context_report.md"
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "examples": report["examples"]}, indent=2, sort_keys=True))
    return 0


def generate_candidate_context_report(config: Config) -> dict[str, Any]:
    executor = AgentExecutor(config)
    harness = EvalHarness(config, executor)
    examples = harness.load_examples()
    full_context = build_full_schema_context(executor.schema_index, executor.endpoint_catalog)
    full_tokens = estimate_tokens(full_context)
    rows = []
    table_recall3 = []
    table_recall5 = []
    api_recall3 = []
    api_recall5 = []
    candidate_tokens = []
    miss_analysis = []
    context_modes = Counter()
    for example in examples:
        context = build_candidate_context(
            example.query,
            executor.schema_index,
            executor.endpoint_catalog,
            enable_hybrid_ranking=config.enable_hybrid_candidate_scoring,
            enable_endpoint_family_ranking=config.enable_endpoint_family_ranking,
            enable_structural_preservation=config.enable_structural_schema_preservation,
            enable_value_to_api_ranking=config.enable_value_to_api_ranking,
            enable_gated_risk_cluster_repair=config.enable_gated_risk_cluster_repair,
        )
        context_mode = choose_context_mode(context)
        context["context_mode"] = context_mode
        context_modes[context_mode] += 1
        candidate_tokens.append(context.get("estimated_tokens", 0))
        gold_tables = extract_sql_tables(example.gold_sql)
        gold_apis = [call.get("path") for call in extract_api_calls(example.gold_api)]
        tables = context.get("candidate_tables", [])
        apis = [api.get("path") for api in context.get("candidate_apis", [])]
        baseline_tables = context.get("ranking_diagnostics", {}).get("baseline_candidate_tables", tables)
        baseline_apis_payload = context.get("ranking_diagnostics", {}).get("baseline_candidate_apis", context.get("candidate_apis", []))
        baseline_apis = [api.get("path") for api in baseline_apis_payload]
        row = {
            "query_id": example.query_id,
            "query": example.query,
            "candidate_tables": tables,
            "candidate_join_hints": context.get("candidate_join_hints", []),
            "candidate_apis": context.get("candidate_apis", []),
            "baseline_candidate_tables": baseline_tables,
            "baseline_candidate_apis": baseline_apis_payload,
            "confidence": context.get("confidence"),
            "score_margin": context.get("score_margin"),
            "baseline_confidence": context.get("ranking_diagnostics", {}).get("baseline_confidence", context.get("confidence")),
            "baseline_score_margin": context.get("ranking_diagnostics", {}).get("baseline_score_margin", context.get("score_margin")),
            "context_mode": context_mode,
            "recommended_context_mode": context_mode,
            "used_gold_patterns": context.get("used_gold_patterns", False),
            "schema_linking": context.get("schema_linking", {}),
            "forward_link_count": context.get("schema_linking", {}).get("forward_link_count", 0),
            "backward_link_count": context.get("schema_linking", {}).get("backward_link_count", 0),
            "structural_join_preserved": context.get("schema_linking", {}).get("structural_join_preserved", False),
            "schema_link_confidence": context.get("schema_linking", {}).get("schema_link_confidence"),
            "schema_link_risk": context.get("schema_linking", {}).get("schema_link_risk"),
            "missing_bridge_warning": context.get("schema_linking", {}).get("missing_bridge_warning", False),
            "reason_for_context_mode": context.get("schema_linking", {}).get("reason_for_context_mode"),
            "structural_tables_added": context.get("schema_linking", {}).get("structural_tables_added", []),
            "structural_reason": context.get("schema_linking", {}).get("structural_reason"),
            "bridge_preserved": context.get("schema_linking", {}).get("bridge_preserved", False),
            "structural_confidence_delta": context.get("schema_linking", {}).get("structural_confidence_delta", 0.0),
            "hybrid_candidate_scoring": context.get("hybrid_candidate_scoring", {}),
            "endpoint_family_ranking": context.get("endpoint_family_ranking", {}),
            "value_to_api_ranking": context.get("value_to_api_ranking", {}),
            "gated_risk_cluster_repair": context.get("gated_risk_cluster_repair", {}),
            "ranking_diagnostics": context.get("ranking_diagnostics", {}),
            "candidate_context_tokens": context.get("estimated_tokens", 0),
            "full_schema_context_tokens": full_tokens,
            "gold_tables": sorted(gold_tables),
            "gold_api_paths": gold_apis,
        }
        if gold_tables:
            r3 = recall_at_k(tables, gold_tables, 3)
            r5 = recall_at_k(tables, gold_tables, 5)
            table_recall3.append(r3)
            table_recall5.append(r5)
            row["table_recall_at_3"] = r3
            row["table_recall_at_5"] = r5
        if gold_apis:
            r3 = recall_at_k(apis, set(gold_apis), 3, normalize=False)
            r5 = recall_at_k(apis, set(gold_apis), 5, normalize=False)
            api_recall3.append(r3)
            api_recall5.append(r5)
            row["api_recall_at_3"] = r3
            row["api_recall_at_5"] = r5
        missing_gold_tables = sorted(
            normalize_table_name(item)
            for item in gold_tables
            if normalize_table_name(item) not in {normalize_table_name(candidate) for candidate in tables}
        )
        missing_gold_apis = sorted(
            api for api in gold_apis
            if api not in set(apis)
        )
        missing_gold_tables_before = sorted(
            normalize_table_name(item)
            for item in gold_tables
            if normalize_table_name(item) not in {normalize_table_name(candidate) for candidate in baseline_tables}
        )
        missing_gold_apis_before = sorted(api for api in gold_apis if api not in set(baseline_apis))
        row["missing_gold_tables"] = missing_gold_tables
        row["missing_gold_apis"] = missing_gold_apis
        row["missing_gold_tables_before"] = missing_gold_tables_before
        row["missing_gold_apis_before"] = missing_gold_apis_before
        risk_policy = classify_candidate_risk(
            context,
            risk_cluster=(context.get("gated_risk_cluster_repair") or {}).get("risk_cluster"),
            missing_candidate_signals={
                "missing_tables": bool(missing_gold_tables),
                "missing_apis": bool(missing_gold_apis),
            },
        )
        schema_vote = vote_schema_contexts(
            query=example.query,
            compact_context=context,
            schema_index=executor.schema_index,
            endpoint_catalog=executor.endpoint_catalog,
            risk_level=risk_policy["risk_level"],
        )
        row.update(
            {
                "risk_efficiency_controller": risk_policy,
                "risk_level": risk_policy.get("risk_level"),
                "accuracy_risk": risk_policy.get("accuracy_risk"),
                "module_skipped_by_risk": risk_policy.get("module_skipped_by_risk", []),
                "token_saved_estimate": risk_policy.get("token_saved_estimate"),
                "runtime_saved_estimate_ms": risk_policy.get("runtime_saved_estimate_ms"),
                "savings_are_estimates": risk_policy.get("savings_are_estimates"),
                "measured_efficiency_improvement_claimed": risk_policy.get("measured_efficiency_improvement_claimed"),
                "schema_context_vote": schema_vote,
                "schema_vote_agreement": schema_vote.get("schema_vote_agreement"),
                "compact_context_safe": schema_vote.get("compact_context_safe"),
                "fallback_reason": schema_vote.get("fallback_reason") or schema_vote.get("reason"),
            }
        )
        risky = (
            row.get("table_recall_at_3", 1.0) < 1.0
            or row.get("table_recall_at_5", 1.0) < 1.0
            or row.get("api_recall_at_3", 1.0) < 1.0
            or (context.get("confidence") or 0) < 0.4
            or (context.get("score_margin") or 0) == 0
        )
        if risky:
            miss_analysis.append(
                {
                    "query_id": example.query_id,
                    "query": example.query,
                    "missing_gold_tables": missing_gold_tables,
                    "missing_gold_apis": missing_gold_apis,
                    "candidate_tables": tables,
                    "candidate_apis": apis,
                    "confidence": context.get("confidence"),
                    "score_margin": context.get("score_margin"),
                    "recommended_context_mode": context_mode,
                }
            )
        rows.append(row)
    avg_candidate = avg(candidate_tokens)
    shadow_report = _load_shadow_repair_report(config.outputs_dir)
    risk_distribution = Counter(row.get("risk_level") for row in rows)
    schema_votes = [row.get("schema_context_vote") for row in rows if isinstance(row.get("schema_context_vote"), dict)]
    return {
        "examples": len(examples),
        "used_gold_patterns": False,
        "summary": {
            "avg_candidate_context_tokens": avg_candidate,
            "avg_full_schema_context_tokens": full_tokens,
            "compression_ratio": round(avg_candidate / full_tokens, 4) if full_tokens else 0.0,
            "table_recall_at_3": avg(table_recall3),
            "table_recall_at_5": avg(table_recall5),
            "api_recall_at_3": avg(api_recall3),
            "api_recall_at_5": avg(api_recall5),
            "candidate_low_confidence_count": sum(1 for row in rows if (row.get("confidence") or 0) < 0.4),
            "candidate_zero_margin_count": sum(1 for row in rows if (row.get("score_margin") or 0) == 0),
            "percent_low_confidence": round(sum(1 for row in rows if (row.get("confidence") or 0) < 0.4) / len(rows), 4) if rows else 0.0,
            "percent_zero_margin": round(sum(1 for row in rows if (row.get("score_margin") or 0) == 0) / len(rows), 4) if rows else 0.0,
            "recommended_fallback_rate": round(sum(1 for row in rows if row.get("context_mode") in {"hybrid", "full_schema"}) / len(rows), 4) if rows else 0.0,
            "context_mode_distribution": dict(context_modes),
            "avg_forward_link_count": avg([row.get("forward_link_count", 0) for row in rows]),
            "avg_backward_link_count": avg([row.get("backward_link_count", 0) for row in rows]),
            "structural_join_preserved_count": sum(1 for row in rows if row.get("structural_join_preserved")),
            "schema_link_risk_distribution": dict(Counter(row.get("schema_link_risk") for row in rows)),
            "cluster_gate_status": build_cluster_gate(build_candidate_risk_clusters(rows))["status"],
            "risk_level_distribution": dict(risk_distribution),
            "estimated_token_savings_total": round(sum(float(row.get("token_saved_estimate") or 0.0) for row in rows), 2),
            "estimated_runtime_savings_ms_total": round(sum(float(row.get("runtime_saved_estimate_ms") or 0.0) for row in rows), 2),
            "estimated_savings_label": "estimated only - packaged execution did not skip modules",
            "schema_vote_active_count": sum(1 for vote in schema_votes if vote.get("active")),
            "schema_vote_agreement_count": sum(1 for vote in schema_votes if vote.get("schema_vote_agreement") is True),
            "compact_context_safe_count": sum(1 for vote in schema_votes if vote.get("compact_context_safe") is True),
        },
        "candidate_miss_analysis": miss_analysis,
        "candidate_risk_clusters": build_candidate_risk_clusters(rows),
        "cluster_gate": build_cluster_gate(build_candidate_risk_clusters(rows)),
        "shadow_repair_eval": {
            "available": bool(shadow_report.get("rows")),
            "paired_shadow_eval_summary": shadow_report.get("paired_shadow_eval_summary", {}),
            "cluster_canary_recommendations": shadow_report.get("cluster_canary_recommendations", {}),
            "repair_execution_enabled": shadow_report.get("repair_execution_enabled", False),
        },
        "curated_join_hint_audit": curated_join_hint_audit(executor.schema_index),
        "rows": rows,
    }


def extract_sql_tables(sql: str | None) -> set[str]:
    if not sql:
        return set()
    identifier = r"(?:\"[^\"]+\"|`[^`]+`|[A-Za-z_][\w$]*)(?:\s*\.\s*(?:\"[^\"]+\"|`[^`]+`|[A-Za-z_][\w$]*))*"
    matches = re.findall(rf"\b(?:FROM|JOIN)\s+({identifier})", sql, flags=re.IGNORECASE)
    return {match for match in matches}


def normalize_table_name(name: str) -> str:
    value = str(name or "").strip().rstrip(";")
    parts = [part.strip().strip('"').strip("`").strip("'") for part in re.split(r"\s*\.\s*", value) if part.strip()]
    return (parts[-1] if parts else value.strip('"').strip("`").strip("'")).lower()


def recall_at_k(candidates: list[str], gold: set[str], k: int, *, normalize: bool = True) -> float:
    normalized_gold = {normalize_table_name(item) for item in gold if normalize_table_name(item)} if normalize else set(gold)
    if not normalized_gold:
        return 0.0
    if normalize:
        top = {normalize_table_name(item) for item in candidates[:k] if normalize_table_name(item)}
    else:
        top = set(candidates[:k])
    return round(len(top & normalized_gold) / len(normalized_gold), 4)


def avg(values: list[float | int]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0


def _load_shadow_repair_report(outputs_dir: Path) -> dict[str, Any]:
    path = outputs_dir / "shadow_repair_eval.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def curated_join_hint_audit(schema_index: Any) -> dict[str, Any]:
    rows = []
    for hint in schema_index.join_hints:
        reason = hint.reason
        if reason.startswith("Curated:"):
            source = "manual general rule"
        elif "Matching ID-like" in reason:
            source = "schema-level relationship"
        elif "Foreign-key-looking" in reason:
            source = "naming convention"
        elif hint.left_table in schema_index.bridge_tables or hint.right_table in schema_index.bridge_tables:
            source = "bridge-table heuristic"
        else:
            source = "schema-level relationship"
        rows.append(
            {
                **hint.to_dict(),
                "source": source,
                "used_gold_patterns": False,
            }
        )
    return {
        "used_gold_patterns": False,
        "count": len(rows),
        "rows": rows,
    }


def build_candidate_risk_clusters(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    definitions = {
        "zero_score_margin": {
            "predicate": lambda row: (row.get("score_margin") or 0) == 0,
            "before_predicate": lambda row: (row.get("baseline_score_margin") or 0) == 0,
            "likely_safe_improvement": "Improve tie-break diagnostics or fall back to hybrid/full schema context; do not force a table choice from a tied score.",
        },
        "low_confidence": {
            "predicate": lambda row: (row.get("confidence") or 0) < 0.4,
            "before_predicate": lambda row: (row.get("baseline_confidence") or 0) < 0.4,
            "likely_safe_improvement": "Use broader context and surface the uncertainty to LLM/controller paths instead of narrowing aggressively.",
        },
        "missing_gold_table_in_top_k": {
            "predicate": lambda row: bool(row.get("missing_gold_tables")),
            "before_predicate": lambda row: bool(row.get("missing_gold_tables_before")),
            "likely_safe_improvement": "Audit schema aliases and structural bridge coverage using schema-level signals only.",
        },
        "missing_gold_api_in_top_k": {
            "predicate": lambda row: bool(row.get("missing_gold_apis")),
            "before_predicate": lambda row: bool(row.get("missing_gold_apis_before")),
            "likely_safe_improvement": "Improve endpoint catalog descriptions and API-family aliases without using public answer patterns.",
        },
        "broad_domain_api_confusion": {
            "predicate": lambda row: _query_has(row, ("sandbox", "platform", "current", "live", "status", "observability")) and bool(row.get("missing_gold_apis")),
            "before_predicate": lambda row: _query_has(row, ("sandbox", "platform", "current", "live", "status", "observability")) and bool(row.get("missing_gold_apis_before")),
            "likely_safe_improvement": "Add endpoint-family labels and confidence diagnostics for broad platform/API intents.",
        },
        "schema_vs_dataset_confusion": {
            "predicate": lambda row: _query_has(row, ("schema", "schemas", "dataset", "datasets")) and bool(row.get("missing_gold_apis")),
            "before_predicate": lambda row: _query_has(row, ("schema", "schemas", "dataset", "datasets")) and bool(row.get("missing_gold_apis_before")),
            "likely_safe_improvement": "Clarify schema-vs-dataset table/API affordances in retrieval-only metadata.",
        },
        "tag_api_confusion": {
            "predicate": lambda row: _query_has(row, ("tag", "tags", "category")) and bool(row.get("missing_gold_apis")),
            "before_predicate": lambda row: _query_has(row, ("tag", "tags", "category")) and bool(row.get("missing_gold_apis_before")),
            "likely_safe_improvement": "Strengthen tag endpoint summaries and keep dry-run API evidence labeled separately.",
        },
        "batch_endpoint_confusion": {
            "predicate": lambda row: _query_has(row, ("batch", "batches", "file", "files", "download")) and bool(row.get("missing_gold_apis")),
            "before_predicate": lambda row: _query_has(row, ("batch", "batches", "file", "files", "download")) and bool(row.get("missing_gold_apis_before")),
            "likely_safe_improvement": "Audit batch endpoint family labels and alias repair diagnostics.",
        },
    }
    clusters: dict[str, dict[str, Any]] = {}
    for name, spec in definitions.items():
        matched = [row for row in rows if spec["predicate"](row)]
        before_matched = [row for row in rows if spec.get("before_predicate", spec["predicate"])(row)]
        clusters[name] = {
            "count": len(matched),
            "before_count": len(before_matched),
            "after_count": len(matched),
            "delta": len(matched) - len(before_matched),
            "improved": len(matched) < len(before_matched),
            "example_query_ids": [row.get("query_id") for row in matched[:8]],
            "before_example_query_ids": [row.get("query_id") for row in before_matched[:8]],
            "likely_safe_improvement": spec["likely_safe_improvement"],
            "diagnostic_only": True,
            "behavior_changing": False,
        }
    return clusters


def build_cluster_gate(clusters: dict[str, dict[str, Any]]) -> dict[str, Any]:
    target_clusters = [
        "zero_score_margin",
        "missing_gold_api_in_top_k",
        "batch_endpoint_confusion",
        "tag_api_confusion",
        "schema_vs_dataset_confusion",
    ]
    improved = [
        name
        for name in target_clusters
        if clusters.get(name, {}).get("after_count", 0) < clusters.get(name, {}).get("before_count", 0)
    ]
    return {
        "target_clusters": target_clusters,
        "passed": bool(improved),
        "improved_clusters": improved,
        "status": "retrieval-cluster improvement measured" if improved else "no retrieval-cluster improvement",
        "diagnostic_only": True,
    }


def _query_has(row: dict[str, Any], terms: tuple[str, ...]) -> bool:
    text = str(row.get("query") or "").lower()
    return any(term in text for term in terms)


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Candidate Context Report",
        "",
        "Candidate context is schema/API retrieval only. It does not use public gold patterns or decide final SQL.",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
    ]
    for key, value in report.get("summary", {}).items():
        lines.append(f"| {key} | {value} |")
    lines.extend(
        [
            "",
            "## Candidate Miss Analysis",
            "",
            "| Query ID | Missing tables | Missing APIs | Confidence | Margin | Recommended mode |",
            "| --- | --- | --- | ---: | ---: | --- |",
        ]
    )
    for row in report.get("candidate_miss_analysis", [])[:50]:
        lines.append(
            f"| `{row.get('query_id')}` | {', '.join(row.get('missing_gold_tables', []))} | "
            f"{', '.join(row.get('missing_gold_apis', []))} | {row.get('confidence')} | {row.get('score_margin')} | {row.get('recommended_context_mode')} |"
        )
    lines.extend(
        [
            "",
            "## Candidate Risk Clusters",
            "",
            "These clusters compare baseline retrieval ordering with the ranking/report-only ordering. They do not change executed SQL/API plans or answer behavior.",
            "",
            "| Cluster | Before | After | Delta | Improved? | Example query IDs | Diagnostic only | Behavior changing? | Likely safe improvement |",
            "| --- | ---: | ---: | ---: | --- | --- | --- | --- | --- |",
        ]
    )
    for name, cluster in report.get("candidate_risk_clusters", {}).items():
        lines.append(
            f"| `{name}` | {cluster.get('before_count')} | {cluster.get('after_count')} | {cluster.get('delta')} | {cluster.get('improved')} | "
            f"{', '.join(map(str, cluster.get('example_query_ids', [])))} | "
            f"{cluster.get('diagnostic_only')} | {cluster.get('behavior_changing')} | {cluster.get('likely_safe_improvement')} |"
        )
    gate = report.get("cluster_gate", {})
    lines.extend(
        [
            "",
            "## Cluster Gate",
            "",
            f"- Status: {gate.get('status')}",
            f"- Passed: {gate.get('passed')}",
            f"- Improved target clusters: {', '.join(gate.get('improved_clusters', [])) or 'none'}",
            "- No score claim: ranking-only changes are reported as retrieval diagnostics unless strict-score improvement is measured.",
        ]
    )
    shadow = report.get("shadow_repair_eval", {})
    lines.extend(
        [
            "",
            "## Shadow Repair Evaluation Linkage",
            "",
            f"- Shadow repair eval available: {shadow.get('available')}",
            f"- Repair execution enabled: {shadow.get('repair_execution_enabled')}",
            "- Canary recommendations are offline what-if diagnostics and do not change SQL_FIRST_API_VERIFY execution.",
            "",
            "| Cluster | Rows | Better | Equal | Worse | Safe to enable? | Recommended flag |",
            "| --- | ---: | ---: | ---: | ---: | --- | --- |",
        ]
    )
    for name, cluster in shadow.get("cluster_canary_recommendations", {}).items():
        lines.append(
            f"| `{name}` | {cluster.get('shadow_eval_rows')} | {cluster.get('repaired_better_count')} | "
            f"{cluster.get('repaired_equal_count')} | {cluster.get('repaired_worse_count')} | "
            f"{cluster.get('safe_to_enable_canary')} | `{cluster.get('recommended_flag')}` |"
        )
    lines.extend(
        [
            "",
            "## Risk-Based Efficiency Controller",
            "",
            "This section is diagnostic only. Token/runtime savings are estimates from module policy and are not measured efficiency gains because packaged execution is unchanged.",
            "",
            "| Query ID | Risk level | Accuracy risk | Skipped modules | Token saved estimate | Runtime saved estimate ms | Estimated only? |",
            "| --- | --- | --- | --- | ---: | ---: | --- |",
        ]
    )
    for row in report.get("rows", [])[:50]:
        lines.append(
            f"| `{row.get('query_id')}` | {row.get('risk_level')} | {row.get('accuracy_risk')} | "
            f"{', '.join(row.get('module_skipped_by_risk', [])) or 'none'} | "
            f"{row.get('token_saved_estimate')} | {row.get('runtime_saved_estimate_ms')} | {row.get('savings_are_estimates')} |"
        )
    lines.extend(
        [
            "",
            "## Schema Context Voting",
            "",
            "Schema voting compares compact candidate context against broader hybrid/full context for high-risk diagnostics only; it does not change executed SQL/API plans.",
            "",
            "| Query ID | Active | Agreement | Compact safe? | Fallback reason | Token delta | Compact tables | Fallback tables |",
            "| --- | --- | --- | --- | --- | ---: | --- | --- |",
        ]
    )
    for row in report.get("rows", [])[:50]:
        vote = row.get("schema_context_vote") or {}
        lines.append(
            f"| `{row.get('query_id')}` | {vote.get('active')} | {vote.get('schema_vote_agreement')} | "
            f"{vote.get('compact_context_safe')} | {vote.get('fallback_reason') or vote.get('reason')} | {vote.get('token_delta')} | "
            f"{', '.join(vote.get('compact_candidate_tables', [])[:4])} | {', '.join(vote.get('fallback_candidate_tables', [])[:4])} |"
        )
    lines.extend(
        [
            "",
            "## Curated Join Hint Audit",
            "",
            f"Used gold patterns: {report.get('curated_join_hint_audit', {}).get('used_gold_patterns')}",
            "",
            "| Left | Right | Source | Reason |",
            "| --- | --- | --- | --- |",
        ]
    )
    for row in report.get("curated_join_hint_audit", {}).get("rows", [])[:80]:
        lines.append(
            f"| {row.get('left_table')}.{row.get('left_column')} | {row.get('right_table')}.{row.get('right_column')} | {row.get('source')} | {row.get('reason')} |"
        )
    lines.extend(
        [
            "",
            "## Per Example",
            "",
            "| Query ID | Tables | APIs | Confidence | Context mode | Used gold patterns |",
            "| --- | --- | --- | ---: | --- | --- |",
        ]
    )
    for row in report.get("rows", [])[:50]:
        tables = ", ".join(row.get("candidate_tables", [])[:5])
        apis = ", ".join(api.get("id", "") for api in row.get("candidate_apis", [])[:5])
        lines.append(f"| `{row.get('query_id')}` | {tables} | {apis} | {row.get('confidence')} | {row.get('context_mode')} | {row.get('used_gold_patterns')} |")
    lines.extend(
        [
            "",
            "## Robust Schema Linking Metrics",
            "",
            "| Query ID | Forward links | Backward links | Structural join preserved | Link confidence | Risk | Context reason |",
            "| --- | ---: | ---: | --- | ---: | --- | --- |",
        ]
    )
    for row in report.get("rows", [])[:50]:
        lines.append(
            f"| `{row.get('query_id')}` | {row.get('forward_link_count')} | {row.get('backward_link_count')} | "
            f"{row.get('structural_join_preserved')} | {row.get('schema_link_confidence')} | {row.get('schema_link_risk')} | {row.get('reason_for_context_mode')} |"
        )
    lines.extend(
        [
            "",
            "## Hybrid Ranking Diagnostics",
            "",
            "| Query ID | Ranking changed? | Top table score | Table margin | Endpoint family | Endpoint confidence | Endpoint ranking changed? |",
            "| --- | --- | ---: | ---: | --- | ---: | --- |",
        ]
    )
    for row in report.get("rows", [])[:50]:
        hybrid = row.get("hybrid_candidate_scoring", {})
        endpoint = row.get("endpoint_family_ranking", {})
        lines.append(
            f"| `{row.get('query_id')}` | {hybrid.get('ranking_changed')} | {hybrid.get('top_candidate_score')} | {hybrid.get('score_margin')} | "
            f"{endpoint.get('endpoint_family')} | {endpoint.get('endpoint_family_confidence')} | {endpoint.get('ranking_changed')} |"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
