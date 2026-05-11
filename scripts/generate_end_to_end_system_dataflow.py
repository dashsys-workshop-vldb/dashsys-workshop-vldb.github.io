#!/usr/bin/env python
from __future__ import annotations

import html
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from visualization_report_helpers import (  # noqa: E402
    VIS_DIR,
    ensure_visualization_path,
    load_json,
    mermaid_block,
    redact_text,
    write_json,
    write_md,
)


STALE_SOURCE_HOURS = 72
OUTPUT_STEM = "end_to_end_system_dataflow"
IMPORTANT_SOURCES = [
    "outputs/reports/report_index.json",
    "outputs/reports/live_adobe_api_readiness_audit.json",
    "outputs/reports/mock_live_api_evidence_pipeline_trial.json",
    "outputs/reports/evidence_aware_answer_rewrite_trial.json",
    "outputs/reports/feedback_loop_semantic_router_final.json",
    "outputs/reports/sdk_usage_audit.json",
    "outputs/reports/workshop_requirement_audit.json",
    "outputs/eval_results_strict.json",
    "outputs/hidden_style_eval.json",
    "outputs/winner_readiness_report.json",
]


@dataclass(frozen=True)
class Node:
    node_id: str
    label: str
    section: str
    kind: str
    col: int
    row: int


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    label: str = ""
    path_type: str = "packaged"


MAJOR_SECTIONS = [
    "User Prompt Input",
    "Runtime Config / Safety Preflight",
    "Prompt Routing",
    "Query Understanding",
    "Context Selection",
    "Planning",
    "SQL Evidence Path",
    "Adobe API Evidence Path",
    "Live API / Dry-run Split",
    "Mock Live API Readiness",
    "EvidenceBus",
    "Answer Slots",
    "Answer Synthesis",
    "Trajectory Logging",
    "Evaluation",
    "Final Submission / Reports",
]


BASE_NODES = [
    Node("user_prompt", "User Prompt", "User Prompt Input", "input", 0, 1),
    Node("config_env", "Config / env", "Runtime Config / Safety Preflight", "config", 1, 0),
    Node("preflight", "Safety preflight", "Runtime Config / Safety Preflight", "config", 1, 1),
    Node("tool_contract", "Tool contract\nexecute_sql / call_api", "Runtime Config / Safety Preflight", "config", 1, 2),
    Node("prompt_router", "Prompt Routing", "Prompt Routing", "routing", 2, 0),
    Node("simple_gate", "Simple Prompt Gate", "Prompt Routing", "routing", 2, 1),
    Node("pipeline_decision", "Use data pipeline?", "Prompt Routing", "decision", 2, 2),
    Node("normalization", "Query Normalization", "Query Understanding", "understanding", 3, 0),
    Node("tokens", "Query Token Extraction", "Query Understanding", "understanding", 3, 1),
    Node("query_router", "Deterministic\nQueryRouter", "Query Understanding", "understanding", 3, 2),
    Node("intent", "Answer Intent", "Query Understanding", "understanding", 3, 3),
    Node("analysis", "QueryAnalysis", "Query Understanding", "understanding", 3, 4),
    Node("semantic_enabled", "Semantic router\nenabled?", "Query Understanding", "decision", 3, 5),
    Node("llm_client", "SDK LLMClient", "Query Understanding", "muted", 3, 6),
    Node("semantic_helper", "LLM Semantic\nRouting Helper", "Query Understanding", "muted", 3, 7),
    Node("semantic_validation", "Hint validation", "Query Understanding", "decision", 3, 8),
    Node("semantic_status", "shadow / not promoted", "Query Understanding", "muted", 3, 9),
    Node("schema_index", "SchemaIndex", "Context Selection", "context", 4, 0),
    Node("endpoint_catalog", "EndpointCatalog", "Context Selection", "context", 4, 1),
    Node("relevance", "Relevance scoring", "Context Selection", "context", 4, 2),
    Node("context_pack", "Context packing", "Context Selection", "context", 4, 3),
    Node("planner", "SQL_FIRST_API_VERIFY\npackaged strategy", "Planning", "planning", 5, 0),
    Node("evidence_policy", "Evidence policy", "Planning", "decision", 5, 1),
    Node("call_budget", "Tool-call budget", "Planning", "planning", 5, 2),
    Node("plan_selection", "Selected plan", "Planning", "planning", 5, 3),
    Node("sql_template", "SQL template /\ngeneric SQL", "SQL Evidence Path", "sql", 6, 0),
    Node("sql_validation", "SQL validation\npassed?", "SQL Evidence Path", "decision", 6, 1),
    Node("sqlglot", "SQLGlot AST\nvalidation", "SQL Evidence Path", "sql", 6, 2),
    Node("duckdb", "execute_sql\nDuckDB snapshot", "SQL Evidence Path", "sql", 6, 3),
    Node("sql_result", "SQL result", "SQL Evidence Path", "sql", 6, 4),
    Node("sql_evidence", "SQL evidence", "SQL Evidence Path", "sql", 6, 5),
    Node("api_plan", "API plan", "Adobe API Evidence Path", "api", 7, 0),
    Node("api_catalog", "Endpoint catalog\nvalidation", "Adobe API Evidence Path", "api", 7, 1),
    Node("api_validation", "API validation\npassed?", "Adobe API Evidence Path", "decision", 7, 2),
    Node("headers", "Credential/header\nconstruction", "Adobe API Evidence Path", "api", 7, 3),
    Node("call_api", "call_api(method,\nurl, params, headers)", "Adobe API Evidence Path", "api", 7, 4),
    Node("credentials", "Adobe credentials\npresent?", "Live API / Dry-run Split", "decision", 8, 0),
    Node("live_api", "Live API mode\nlive readiness: {live_status}", "Live API / Dry-run Split", "live", 8, 1),
    Node("dry_run", "Dry-run fallback\nno credentials", "Live API / Dry-run Split", "live", 8, 2),
    Node("api_parser", "API response\nparser", "Live API / Dry-run Split", "live", 8, 3),
    Node("evidence_state", "evidence_state\nlive_success / live_empty\napi_error / malformed\ndry_run_unavailable", "Live API / Dry-run Split", "live", 8, 4),
    Node("parsed_api", "Parsed API\nevidence", "Live API / Dry-run Split", "live", 8, 5),
    Node("fixtures", "Synthetic fixtures", "Mock Live API Readiness", "muted", 9, 0),
    Node("mock_parser", "Mock live parser\nsuccess: {mock_parser}", "Mock Live API Readiness", "muted", 9, 1),
    Node("discovery", "Discovery-chain\nreadiness\nchains: {mock_discovery}", "Mock Live API Readiness", "muted", 9, 2),
    Node("mock_forward", "EvidenceBus\nforwarding", "Mock Live API Readiness", "muted", 9, 3),
    Node("mock_slots", "Answer slot\nverification", "Mock Live API Readiness", "muted", 9, 4),
    Node("diagnostic_only", "diagnostic only", "Mock Live API Readiness", "muted", 9, 5),
    Node("evidence_bus", "EvidenceBus", "EvidenceBus", "evidence", 10, 1),
    Node("evidence_fields", "ids / names / counts\nstatuses / timestamps", "EvidenceBus", "evidence", 10, 2),
    Node("evidence_sources", "SQL / live API /\ndry-run state", "EvidenceBus", "evidence", 10, 3),
    Node("answer_slots", "Answer Slots", "Answer Slots", "slots", 11, 1),
    Node("slot_shape", "COUNT / LIST\nSTATUS / WHEN\nYES_NO", "Answer Slots", "slots", 11, 2),
    Node("slot_sources", "source tracking", "Answer Slots", "slots", 11, 3),
    Node("answer_synthesis", "Evidence-Aware\nAnswer Synthesis", "Answer Synthesis", "answer", 12, 0),
    Node("templates", "Evidence-aware\ntemplates", "Answer Synthesis", "answer", 12, 1),
    Node("faithfulness", "Claim Faithfulness\nCheck", "Answer Synthesis", "decision", 12, 2),
    Node("rewrite_trial", "Answer-only\nrewrite trial\nkeep_trial_only", "Answer Synthesis", "muted", 12, 3),
    Node("rewrite_status", "not promoted", "Answer Synthesis", "muted", 12, 4),
    Node("final_answer", "Final Answer", "Answer Synthesis", "answer", 12, 5),
    Node("trajectory", "Trajectory Logging", "Trajectory Logging", "trajectory", 13, 1),
    Node("metadata_json", "metadata.json", "Trajectory Logging", "trajectory", 13, 2),
    Node("filled_prompt", "filled_system_prompt.txt", "Trajectory Logging", "trajectory", 13, 3),
    Node("trajectory_json", "trajectory.json", "Trajectory Logging", "trajectory", 13, 4),
    Node("strict_eval", "Strict Eval\nscore: {strict_score}", "Evaluation", "eval", 14, 0),
    Node("hidden_eval", "Hidden-style Eval\n{hidden_style}", "Evaluation", "eval", 14, 1),
    Node("llm_baseline", "LLM baseline eval\ndiagnostic only", "Evaluation", "muted", 14, 2),
    Node("readiness", "check_submission_ready\nready: {ready}", "Evaluation", "eval", 14, 3),
    Node("final_package", "final_submission\npackaging", "Final Submission / Reports", "final", 15, 0),
    Node("source_zip", "source_code.zip", "Final Submission / Reports", "final", 15, 1),
    Node("workshop_audit", "Workshop audit\n{workshop_status}", "Final Submission / Reports", "final", 15, 2),
    Node("report_index", "Consolidated\nreport index", "Final Submission / Reports", "final", 15, 3),
]


EDGES = [
    Edge("user_prompt", "config_env"),
    Edge("config_env", "preflight"),
    Edge("preflight", "tool_contract"),
    Edge("tool_contract", "prompt_router"),
    Edge("prompt_router", "simple_gate"),
    Edge("simple_gate", "pipeline_decision"),
    Edge("pipeline_decision", "normalization", "yes"),
    Edge("normalization", "tokens"),
    Edge("tokens", "query_router"),
    Edge("query_router", "intent"),
    Edge("intent", "analysis"),
    Edge("analysis", "schema_index"),
    Edge("analysis", "endpoint_catalog"),
    Edge("schema_index", "relevance"),
    Edge("endpoint_catalog", "relevance"),
    Edge("relevance", "context_pack"),
    Edge("context_pack", "planner"),
    Edge("planner", "evidence_policy"),
    Edge("evidence_policy", "call_budget"),
    Edge("call_budget", "plan_selection"),
    Edge("plan_selection", "sql_template", "SQL branch"),
    Edge("sql_template", "sql_validation"),
    Edge("sql_validation", "sqlglot", "yes"),
    Edge("sqlglot", "duckdb"),
    Edge("duckdb", "sql_result"),
    Edge("sql_result", "sql_evidence"),
    Edge("sql_evidence", "evidence_bus"),
    Edge("plan_selection", "api_plan", "API branch"),
    Edge("api_plan", "api_catalog"),
    Edge("api_catalog", "api_validation"),
    Edge("api_validation", "headers", "yes"),
    Edge("headers", "call_api"),
    Edge("call_api", "credentials"),
    Edge("credentials", "live_api", "yes"),
    Edge("credentials", "dry_run", "no"),
    Edge("live_api", "api_parser"),
    Edge("dry_run", "api_parser"),
    Edge("api_parser", "evidence_state"),
    Edge("evidence_state", "parsed_api"),
    Edge("parsed_api", "evidence_bus"),
    Edge("evidence_bus", "evidence_fields"),
    Edge("evidence_fields", "evidence_sources"),
    Edge("evidence_sources", "answer_slots"),
    Edge("answer_slots", "slot_shape"),
    Edge("slot_shape", "slot_sources"),
    Edge("slot_sources", "answer_synthesis"),
    Edge("answer_synthesis", "templates"),
    Edge("templates", "faithfulness"),
    Edge("faithfulness", "final_answer", "supported"),
    Edge("final_answer", "trajectory"),
    Edge("trajectory", "metadata_json"),
    Edge("trajectory", "filled_prompt"),
    Edge("trajectory", "trajectory_json"),
    Edge("trajectory_json", "final_package"),
    Edge("final_package", "source_zip"),
    Edge("final_package", "strict_eval"),
    Edge("final_package", "hidden_eval"),
    Edge("final_package", "readiness"),
    Edge("strict_eval", "report_index", "metrics", "final"),
    Edge("hidden_eval", "report_index", "robustness", "final"),
    Edge("readiness", "report_index", "ready", "final"),
    Edge("workshop_audit", "report_index", "compliance", "final"),
    Edge("analysis", "semantic_enabled", "low confidence", "diagnostic"),
    Edge("semantic_enabled", "llm_client", "feature flag", "diagnostic"),
    Edge("llm_client", "semantic_helper", "SDK only", "diagnostic"),
    Edge("semantic_helper", "semantic_validation", "JSON hint", "diagnostic"),
    Edge("semantic_validation", "semantic_status", "valid", "diagnostic"),
    Edge("semantic_status", "relevance", "shadow only", "diagnostic"),
    Edge("fixtures", "mock_parser", "fixture data", "trial"),
    Edge("mock_parser", "discovery", "mock", "trial"),
    Edge("discovery", "mock_forward", "GET-only", "trial"),
    Edge("mock_forward", "mock_slots", "parsed evidence", "trial"),
    Edge("mock_slots", "diagnostic_only", "verified", "trial"),
    Edge("diagnostic_only", "report_index", "readiness report", "trial"),
    Edge("faithfulness", "rewrite_trial", "answer-only", "trial"),
    Edge("rewrite_trial", "rewrite_status", "strict gate", "trial"),
    Edge("rewrite_status", "report_index", "trial report", "trial"),
    Edge("trajectory", "llm_baseline", "baseline", "diagnostic"),
    Edge("llm_baseline", "report_index", "diagnostic", "diagnostic"),
]


def main() -> int:
    payload = generate_end_to_end_system_dataflow()
    print(
        json.dumps(
            {
                "html": payload["output_html_path"],
                "markdown": payload["output_md_path"],
                "json": str(VIS_DIR / f"{OUTPUT_STEM}.json"),
                "nodes": payload["node_count"],
                "edges": payload["edge_count"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def generate_end_to_end_system_dataflow() -> dict[str, Any]:
    VIS_DIR.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc)
    sources = source_metadata(generated_at)
    status = current_status()
    nodes = build_nodes(status)
    mermaid = build_mermaid(nodes, EDGES)
    svg = render_svg(nodes, EDGES)
    payload = {
        "generated_at": generated_at.isoformat(),
        "source_files": sources["source_files"],
        "missing_source_files": sources["missing_source_files"],
        "stale_source_warnings": sources["stale_source_warnings"],
        "node_count": len(nodes),
        "edge_count": len(EDGES),
        "major_sections": list(MAJOR_SECTIONS),
        "mermaid_source": mermaid,
        "svg_source": svg,
        "output_html_path": str(VIS_DIR / f"{OUTPUT_STEM}.html"),
        "output_md_path": str(VIS_DIR / f"{OUTPUT_STEM}.md"),
        "warnings": sources["warnings"],
    }
    write_html(VIS_DIR / f"{OUTPUT_STEM}.html", render_html(payload, svg))
    write_md(VIS_DIR / f"{OUTPUT_STEM}.md", render_markdown(payload))
    write_json(VIS_DIR / f"{OUTPUT_STEM}.json", payload)
    return payload


def build_nodes(status: dict[str, Any]) -> list[Node]:
    values = {
        "live_status": status.get("live_adobe_api_readiness", "unavailable"),
        "mock_parser": status.get("mock_parser_success_count", "unavailable"),
        "mock_discovery": status.get("mock_discovery_chains_simulated", "unavailable"),
        "strict_score": status.get("packaged_strict_score", "unavailable"),
        "hidden_style": status.get("hidden_style", "unavailable"),
        "ready": status.get("final_submission_ready", "unavailable"),
        "workshop_status": status.get("workshop_audit_status", "unavailable"),
    }
    return [
        Node(node.node_id, node.label.format(**values), node.section, node.kind, node.col, node.row)
        for node in BASE_NODES
    ]


def source_metadata(generated_at: datetime) -> dict[str, Any]:
    source_files = []
    missing = []
    stale = []
    warnings = []
    for rel in IMPORTANT_SOURCES:
        path = ROOT / rel
        if not path.exists():
            missing.append(rel)
            warnings.append(f"missing_source:{rel}")
            continue
        generated = report_generated_at(path)
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        source_time = generated or mtime
        age_hours = max(0.0, (generated_at - source_time).total_seconds() / 3600)
        source_files.append(
            {
                "path": rel,
                "exists": True,
                "source_timestamp": source_time.isoformat(),
                "timestamp_source": "generated_at" if generated else "file_mtime",
                "age_hours": round(age_hours, 3),
            }
        )
        if age_hours > STALE_SOURCE_HOURS:
            message = f"stale_source_warning:{rel}:age_hours={round(age_hours, 1)}"
            stale.append(message)
            warnings.append(message)
    return {
        "source_files": source_files,
        "missing_source_files": missing,
        "stale_source_warnings": stale,
        "warnings": warnings,
    }


def report_generated_at(path: Path) -> datetime | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    value = payload.get("generated_at")
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def current_status() -> dict[str, Any]:
    system = load_json("outputs/reports/system_summary.json", {})
    index = load_json("outputs/reports/report_index.json", {})
    mock = load_json("outputs/reports/mock_live_api_evidence_pipeline_trial.json", {})
    workshop = load_json("outputs/reports/workshop_requirement_audit.json", {})
    strict = load_json("outputs/eval_results_strict.json", {})
    hidden = load_json("outputs/hidden_style_eval.json", {})
    readiness = load_json("outputs/winner_readiness_report.json", {})
    index_status = index.get("current_status", {}) if isinstance(index, dict) else {}
    strict_summary = strict.get("summary", {}).get("by_strategy", {}).get("SQL_FIRST_API_VERIFY", {})
    hidden_summary = hidden.get("summary", {}) if isinstance(hidden, dict) else {}
    packaged = readiness.get("packaged", {}) if isinstance(readiness, dict) else {}
    live = system.get("live_adobe_api_readiness", {}) if isinstance(system, dict) else {}
    return clean_status(
        {
            "packaged_strict_score": first_value(
                system.get("packaged_strict_score"),
                packaged.get("strict_final_score"),
                strict_summary.get("avg_final_score"),
                index_status.get("packaged_strict_score"),
            ),
            "hidden_style": first_value(
                (system.get("hidden_style") or {}).get("label") if isinstance(system.get("hidden_style"), dict) else None,
                f"{hidden_summary.get('passed_cases')}/{hidden_summary.get('total_cases')}"
                if hidden_summary.get("passed_cases") is not None and hidden_summary.get("total_cases") is not None
                else None,
                index_status.get("hidden_style"),
            ),
            "final_submission_ready": first_value(
                system.get("final_submission_ready"),
                packaged.get("final_submission_ready"),
                index_status.get("final_submission_ready"),
            ),
            "live_adobe_api_readiness": first_value(
                live.get("overall_status"),
                index_status.get("live_adobe_api_readiness"),
            ),
            "mock_parser_success_count": first_value(
                live.get("mock_parser_success_count"),
                mock.get("parser_success_count"),
            ),
            "mock_discovery_chains_simulated": first_value(
                live.get("mock_discovery_chain_simulated_count"),
                mock.get("discovery_chain_simulated_count"),
            ),
            "workshop_audit_status": first_value(workshop.get("overall_status")),
        }
    )


def clean_status(status: dict[str, Any]) -> dict[str, Any]:
    return {key: "unavailable" if value in (None, "", [], {}) else value for key, value in status.items()}


def first_value(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return "unavailable"


def build_mermaid(nodes: list[Node], edges: list[Edge]) -> str:
    lines = ["flowchart LR"]
    by_section: dict[str, list[Node]] = {section: [] for section in MAJOR_SECTIONS}
    for node in nodes:
        by_section.setdefault(node.section, []).append(node)
    for index, section in enumerate(MAJOR_SECTIONS):
        lines.append(f"  subgraph S{index}[\"{section}\"]")
        for node in by_section.get(section, []):
            label = mermaid_label(node.label)
            if node.kind == "decision":
                lines.append(f"    {node.node_id}{{\"{label}\"}}")
            else:
                lines.append(f"    {node.node_id}[\"{label}\"]")
        lines.append("  end")
    for edge in edges:
        connector = "-.->" if edge.path_type in {"diagnostic", "trial"} else "-->"
        label = f"|{mermaid_label(edge.label, 36)}|" if edge.label else ""
        lines.append(f"  {edge.source} {connector}{label} {edge.target}")
    for kind in sorted({node.kind for node in nodes}):
        lines.append(f"  classDef {kind} fill:{color_for_kind(kind)},stroke:#243044,color:#111827,stroke-width:1px;")
    for node in nodes:
        lines.append(f"  class {node.node_id} {node.kind};")
    return "\n".join(lines)


def render_html(payload: dict[str, Any], svg: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>DASHSys End-to-End System Data Flow</title>
  <style>
    :root {{
      --bg: #eef2f7;
      --ink: #111827;
      --muted: #64748b;
    }}
    * {{ box-sizing: border-box; }}
    html, body {{ height: 100%; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    header {{
      padding: 14px 18px 8px;
      background: #f8fafc;
      border-bottom: 1px solid #dbe3ef;
    }}
    h1 {{
      margin: 0;
      font-size: 20px;
      line-height: 1.2;
      letter-spacing: 0;
    }}
    .flowchart-canvas {{
      width: 100vw;
      height: calc(100vh - 74px);
      overflow: auto;
      background:
        linear-gradient(90deg, rgba(148, 163, 184, .12) 1px, transparent 1px),
        linear-gradient(180deg, rgba(148, 163, 184, .12) 1px, transparent 1px),
        #f8fafc;
      background-size: 24px 24px;
      padding: 18px;
    }}
    svg {{
      display: block;
      min-width: 3440px;
      min-height: 1030px;
      shape-rendering: geometricPrecision;
    }}
    .section-bg {{ fill: rgba(255, 255, 255, .78); stroke: #cbd5e1; stroke-width: 1.2; }}
    .section-label {{ font-size: 15px; font-weight: 800; fill: #0f172a; }}
    .node rect, .node polygon {{ stroke: #243044; stroke-width: 1.4; filter: url(#soft-shadow); }}
    .node.packaged rect, .node.packaged polygon {{ stroke-width: 2.8; }}
    .node text {{ font-size: 12px; fill: #0f172a; font-weight: 700; }}
    .node .small {{ font-size: 11px; fill: #475569; font-weight: 650; }}
    .edge {{ fill: none; stroke: #14532d; stroke-width: 3.3; marker-end: url(#arrow-packaged); }}
    .edge.final {{ stroke: #1d4ed8; stroke-width: 2.8; marker-end: url(#arrow-final); }}
    .edge.diagnostic {{ stroke: #64748b; stroke-width: 2.2; stroke-dasharray: 8 7; marker-end: url(#arrow-muted); }}
    .edge.trial {{ stroke: #a16207; stroke-width: 2.2; stroke-dasharray: 7 6; marker-end: url(#arrow-trial); }}
    .edge-label {{ font-size: 11px; fill: #334155; paint-order: stroke; stroke: white; stroke-width: 4px; font-weight: 700; }}
    .input {{ fill: #dbeafe; }}
    .config {{ fill: #e0f2fe; }}
    .routing {{ fill: #ede9fe; }}
    .understanding {{ fill: #f5e8ff; }}
    .context {{ fill: #fef3c7; }}
    .planning {{ fill: #fde68a; }}
    .sql {{ fill: #dcfce7; }}
    .api {{ fill: #ffedd5; }}
    .live {{ fill: #fed7aa; }}
    .decision {{ fill: #fee2e2; }}
    .evidence {{ fill: #ccfbf1; }}
    .slots {{ fill: #cffafe; }}
    .answer {{ fill: #d1fae5; }}
    .trajectory {{ fill: #e0e7ff; }}
    .eval {{ fill: #dbeafe; }}
    .final {{ fill: #ddd6fe; }}
    .muted {{ fill: #f1f5f9; stroke: #94a3b8; }}
    footer {{
      height: 28px;
      padding: 5px 18px;
      color: var(--muted);
      font-size: 12px;
      background: #f8fafc;
      border-top: 1px solid #dbe3ef;
    }}
  </style>
</head>
<body>
  <header><h1>DASHSys End-to-End System Data Flow</h1></header>
  <main class="flowchart-canvas" aria-label="DASHSys end-to-end system workflow flowchart">
    {svg}
  </main>
  <footer>Generated {esc(payload['generated_at'])}</footer>
</body>
</html>
"""


def render_svg(nodes: list[Node], edges: list[Edge]) -> str:
    node_w = 172
    node_h = 66
    col_gap = 214
    row_gap = 87
    margin_x = 30
    margin_y = 72
    max_col = max(node.col for node in nodes)
    max_row = max(node.row for node in nodes)
    width = margin_x * 2 + max_col * col_gap + node_w + 44
    height = margin_y * 2 + max_row * row_gap + node_h + 64
    positions = {node.node_id: (margin_x + node.col * col_gap, margin_y + node.row * row_gap) for node in nodes}
    section_col = {section: index for index, section in enumerate(MAJOR_SECTIONS)}
    searchable = " | ".join([*MAJOR_SECTIONS, *(node.label.replace("\n", " ") for node in nodes)])
    parts = [
        f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img" aria-labelledby="chart-title chart-desc">',
        '<title id="chart-title">DASHSys end-to-end system dataflow flowchart</title>',
        f'<desc id="chart-desc">{esc(searchable)}</desc>',
        "<defs>",
        '<filter id="soft-shadow" x="-10%" y="-10%" width="120%" height="125%"><feDropShadow dx="0" dy="1.2" stdDeviation="1.4" flood-color="#0f172a" flood-opacity=".12"/></filter>',
        '<marker id="arrow-packaged" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#14532d"/></marker>',
        '<marker id="arrow-final" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#1d4ed8"/></marker>',
        '<marker id="arrow-muted" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#64748b"/></marker>',
        '<marker id="arrow-trial" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#a16207"/></marker>',
        "</defs>",
    ]
    for section in MAJOR_SECTIONS:
        col = section_col[section]
        x = margin_x + col * col_gap - 14
        parts.append(f'<rect class="section-bg" x="{x}" y="18" width="{node_w + 28}" height="{height - 42}" rx="12"/>')
        parts.append(f'<text class="section-label" x="{x + 14}" y="42">{esc(section)}</text>')
    for edge in edges:
        x1, y1 = positions[edge.source]
        x2, y2 = positions[edge.target]
        start = (x1 + node_w, y1 + node_h / 2)
        end = (x2, y2 + node_h / 2)
        if x2 <= x1:
            start = (x1 + node_w / 2, y1 + node_h)
            end = (x2 + node_w / 2, y2)
        distance = abs(end[0] - start[0])
        cx1 = start[0] + max(36, distance * 0.34)
        cx2 = end[0] - max(36, distance * 0.34)
        if x2 <= x1:
            cx1 = start[0]
            cx2 = end[0]
        path = f"M {start[0]:.1f} {start[1]:.1f} C {cx1:.1f} {start[1]:.1f}, {cx2:.1f} {end[1]:.1f}, {end[0]:.1f} {end[1]:.1f}"
        parts.append(f'<path class="edge {esc(edge.path_type)}" d="{path}"/>')
        if edge.label:
            lx = (start[0] + end[0]) / 2
            ly = (start[1] + end[1]) / 2 - 7
            parts.append(f'<text class="edge-label" x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle">{esc(edge.label)}</text>')
    packaged_nodes = set()
    for edge in edges:
        if edge.path_type == "packaged":
            packaged_nodes.add(edge.source)
            packaged_nodes.add(edge.target)
    for node in nodes:
        x, y = positions[node.node_id]
        group_classes = f"node {'packaged' if node.node_id in packaged_nodes and node.kind != 'muted' else ''}"
        parts.append(f'<g class="{group_classes}" id="{esc(node.node_id)}">')
        if node.kind == "decision":
            cx = x + node_w / 2
            cy = y + node_h / 2
            points = f"{cx},{y} {x + node_w},{cy} {cx},{y + node_h} {x},{cy}"
            parts.append(f'<polygon class="{esc(node.kind)}" points="{points}"/>')
        else:
            parts.append(f'<rect class="{esc(node.kind)}" x="{x}" y="{y}" width="{node_w}" height="{node_h}" rx="9"/>')
        lines = compact_label_lines(node.label, 22, 4)
        y_start = y + 20 if len(lines) >= 4 else y + 24
        for i, line in enumerate(lines):
            css = ' class="small"' if i > 0 and len(lines) >= 3 else ""
            parts.append(f'<text{css} x="{x + node_w / 2}" y="{y_start + (i * 14)}" text-anchor="middle">{esc(line)}</text>')
        parts.append("</g>")
    parts.append("</svg>")
    return "\n".join(parts)


def render_markdown(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# DASHSys End-to-End System Data Flow",
            "",
            mermaid_block(payload["mermaid_source"]),
            "",
            "HTML artifact: `outputs/visualizations/end_to_end_system_dataflow.html`",
            "",
        ]
    )


def write_html(path: Path, content: str) -> None:
    ensure_visualization_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(redact_text(content), encoding="utf-8")


def mermaid_label(value: Any, max_chars: int = 120) -> str:
    text = str(value if value is not None else "unavailable")
    text = redact_text(text).replace("\n", "<br/>")
    text = re.sub(r"[\r\t{}|`]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_chars:
        text = text[: max_chars - 3].rstrip() + "..."
    return text.replace('"', "'")


def compact_label_lines(label: str, width: int, max_lines: int) -> list[str]:
    lines: list[str] = []
    for raw_line in str(label).splitlines():
        words = raw_line.split()
        current = ""
        for word in words:
            if not current:
                current = word
            elif len(current) + len(word) + 1 <= width:
                current += " " + word
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)
    if len(lines) > max_lines:
        lines = lines[: max_lines - 1] + [lines[max_lines - 1].rstrip(" .") + "..."]
    return lines or ["unavailable"]


def color_for_kind(kind: str) -> str:
    return {
        "input": "#dbeafe",
        "config": "#e0f2fe",
        "routing": "#ede9fe",
        "understanding": "#f5e8ff",
        "context": "#fef3c7",
        "planning": "#fde68a",
        "sql": "#dcfce7",
        "api": "#ffedd5",
        "live": "#fed7aa",
        "decision": "#fee2e2",
        "evidence": "#ccfbf1",
        "slots": "#cffafe",
        "answer": "#d1fae5",
        "trajectory": "#e0e7ff",
        "eval": "#dbeafe",
        "final": "#ddd6fe",
        "muted": "#f1f5f9",
    }.get(kind, "#f8fafc")


def esc(value: Any) -> str:
    return html.escape(redact_text(str(value)), quote=True)


if __name__ == "__main__":
    raise SystemExit(main())
