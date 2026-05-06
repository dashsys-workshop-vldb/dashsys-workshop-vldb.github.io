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
        context = build_candidate_context(example.query, executor.schema_index, executor.endpoint_catalog)
        context_mode = choose_context_mode(context)
        context["context_mode"] = context_mode
        context_modes[context_mode] += 1
        candidate_tokens.append(context.get("estimated_tokens", 0))
        gold_tables = extract_sql_tables(example.gold_sql)
        gold_apis = [call.get("path") for call in extract_api_calls(example.gold_api)]
        tables = context.get("candidate_tables", [])
        apis = [api.get("path") for api in context.get("candidate_apis", [])]
        row = {
            "query_id": example.query_id,
            "query": example.query,
            "candidate_tables": tables,
            "candidate_join_hints": context.get("candidate_join_hints", []),
            "candidate_apis": context.get("candidate_apis", []),
            "confidence": context.get("confidence"),
            "score_margin": context.get("score_margin"),
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
        row["missing_gold_tables"] = missing_gold_tables
        row["missing_gold_apis"] = missing_gold_apis
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
        },
        "candidate_miss_analysis": miss_analysis,
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
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
