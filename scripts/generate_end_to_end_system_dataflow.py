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

try:  # noqa: E402
    from scripts.visualization_report_helpers import (
        VIS_DIR,
        ensure_visualization_path,
        load_json,
        mermaid_block,
        redact_text,
        write_json,
        write_md,
    )
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    from visualization_report_helpers import (
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
    x: int
    y: int
    width: int = 210
    height: int = 58


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    label: str = ""
    path_type: str = "packaged"


@dataclass(frozen=True)
class Cluster:
    cluster_id: str
    label: str
    section: str
    x: int
    y: int
    width: int
    height: int
    kind: str = "main"


MAJOR_SECTIONS = [
    "Input + Preflight",
    "Routing + Query Understanding",
    "Context + Planning",
    "SQL Evidence Path",
    "Adobe API Evidence Path",
    "EvidenceBus",
    "Answer Generation",
    "Trajectory + Packaging",
    "Evaluation + Reports",
    "Diagnostic / Trial Side Paths",
    "Mock Live API Readiness",
    "Evidence-Aware Answer Rewrite",
]


BASE_NODES = [
    Node("user_prompt", "User Prompt", "Input + Preflight", "input", 415, 64, 200, 52),
    Node("runtime_config", "Runtime Config", "Input + Preflight", "config", 415, 124, 200, 52),
    Node("preflight", "Validation Guard", "Input + Preflight", "config", 415, 184, 200, 52),
    Node("prompt_router", "Prompt Routing", "Routing + Query Understanding", "routing", 415, 318, 200, 52),
    Node("simple_gate", "Simple Prompt Gate", "Routing + Query Understanding", "routing", 415, 378, 200, 52),
    Node("normalization", "Query Normalization", "Routing + Query Understanding", "understanding", 415, 438, 200, 52),
    Node("tokens", "Query Token\nExtraction", "Routing + Query Understanding", "understanding", 415, 498, 200, 52),
    Node("query_router", "Deterministic\nQueryRouter", "Routing + Query Understanding", "understanding", 415, 558, 200, 52),
    Node("intent", "Answer Intent", "Routing + Query Understanding", "understanding", 415, 618, 200, 52),
    Node("analysis", "QueryAnalysis", "Routing + Query Understanding", "understanding", 415, 678, 200, 52),
    Node("schema_catalog", "SchemaIndex /\nEndpointCatalog", "Context + Planning", "context", 415, 838, 200, 52),
    Node("relevance", "Relevance Scoring", "Context + Planning", "context", 415, 898, 200, 52),
    Node("context_pack", "Context Packing", "Context + Planning", "context", 415, 958, 200, 52),
    Node("planner", "SQL_FIRST_API_VERIFY\nmain strategy", "Context + Planning", "planning", 415, 1018, 200, 52),
    Node("evidence_policy", "Evidence Policy", "Context + Planning", "decision", 415, 1078, 200, 52),
    Node("sql_api_plan", "SQL / API Plan", "Context + Planning", "planning", 415, 1138, 200, 52),
    Node("sql_template", "SQL Template /\nGeneric SQL", "SQL Evidence Path", "sql", 152, 1328, 196, 52),
    Node("sql_validation", "SQL validation\npassed?", "SQL Evidence Path", "decision", 152, 1388, 196, 52),
    Node("sqlglot", "SQLGlot AST", "SQL Evidence Path", "sql", 152, 1448, 196, 52),
    Node("duckdb", "execute_sql\nDuckDB", "SQL Evidence Path", "sql", 152, 1508, 196, 52),
    Node("sql_result", "SQL Result", "SQL Evidence Path", "sql", 152, 1568, 196, 52),
    Node("sql_evidence", "Local SQL\nEvidence", "SQL Evidence Path", "sql", 152, 1628, 196, 52),
    Node("api_plan", "API Plan", "Adobe API Evidence Path", "api", 690, 1328, 196, 52),
    Node("api_validation", "API validation\npassed?", "Adobe API Evidence Path", "decision", 690, 1388, 196, 52),
    Node("headers", "Credential Headers", "Adobe API Evidence Path", "api", 690, 1448, 196, 52),
    Node("credentials", "Adobe credentials\npresent?", "Adobe API Evidence Path", "decision", 690, 1508, 196, 52),
    Node("live_api", "Live API mode\n{live_status}", "Adobe API Evidence Path", "live", 580, 1590, 162, 48),
    Node("dry_run", "Dry-run fallback", "Adobe API Evidence Path", "live", 838, 1590, 162, 48),
    Node("api_parser", "API Response\nParser", "Adobe API Evidence Path", "live", 690, 1668, 196, 52),
    Node("evidence_state", "Evidence State\nsuccess / empty / error", "Adobe API Evidence Path", "live", 690, 1728, 196, 52),
    Node("parsed_api", "Adobe API\nEvidence", "Adobe API Evidence Path", "live", 690, 1788, 196, 52),
    Node("evidence_bus", "EvidenceBus", "EvidenceBus", "evidence", 415, 1976, 200, 52),
    Node("evidence_fields", "IDs / names /\ncounts / statuses", "EvidenceBus", "evidence", 415, 2036, 200, 52),
    Node("evidence_sources", "SQL / live API /\ndry-run state", "EvidenceBus", "evidence", 415, 2096, 200, 52),
    Node("answer_slots", "Answer Slots", "Answer Generation", "slots", 415, 2270, 200, 52),
    Node("answer_synthesis", "Answer Synthesis", "Answer Generation", "answer", 415, 2330, 200, 52),
    Node("claim_verification", "Claim Faithfulness", "Answer Generation", "decision", 415, 2390, 200, 52),
    Node("final_answer", "Final Answer", "Answer Generation", "answer", 415, 2468, 200, 52),
    Node("trajectory", "Trajectory Logging", "Trajectory + Packaging", "trajectory", 415, 2666, 200, 52),
    Node("deliverables", "trajectory.json /\nmetadata.json / prompt", "Trajectory + Packaging", "trajectory", 415, 2726, 200, 52),
    Node("final_submission", "Final Submission", "Trajectory + Packaging", "final", 415, 2786, 200, 52),
    Node("eval_hub", "Evaluation + Reports", "Evaluation + Reports", "eval", 415, 2956, 200, 52),
    Node("strict_eval", "Strict Eval\nscore: {strict_score}", "Evaluation + Reports", "eval", 120, 3050, 170, 48),
    Node("hidden_eval", "Hidden-style Eval\n{hidden_style}", "Evaluation + Reports", "eval", 330, 3050, 170, 48),
    Node("readiness", "Check Submission\nready: {ready}", "Evaluation + Reports", "eval", 540, 3050, 170, 48),
    Node("report_index", "Report Index", "Evaluation + Reports", "final", 750, 3050, 170, 48),
    Node("semantic_flag", "Semantic router\nenabled?", "Diagnostic / Trial Side Paths", "decision", 802, 334, 168, 42),
    Node("llm_client", "SDK LLMClient", "Diagnostic / Trial Side Paths", "muted", 802, 386, 168, 42),
    Node("semantic_helper", "LLM Semantic\nRouting Helper", "Diagnostic / Trial Side Paths", "muted", 802, 438, 168, 42),
    Node("semantic_validation", "Hint Validation", "Diagnostic / Trial Side Paths", "muted", 802, 490, 168, 42),
    Node("semantic_status", "shadow /\nnot promoted", "Diagnostic / Trial Side Paths", "muted", 802, 542, 168, 42),
    Node("llm_baseline", "SDK LLM Baseline\nDiagnostic only", "Diagnostic / Trial Side Paths", "muted", 802, 630, 168, 42),
    Node("fixtures", "Synthetic Fixtures", "Mock Live API Readiness", "muted", 1112, 1328, 168, 42),
    Node("mock_parser", "Mock Parser\nsuccess: {mock_parser}", "Mock Live API Readiness", "muted", 1112, 1380, 168, 42),
    Node("discovery", "Discovery-chain\nreadiness", "Mock Live API Readiness", "muted", 1112, 1432, 168, 42),
    Node("mock_forward", "EvidenceBus\nForwarding", "Mock Live API Readiness", "muted", 1112, 1484, 168, 42),
    Node("mock_slots", "Answer Slot\nVerification", "Mock Live API Readiness", "muted", 1112, 1536, 168, 42),
    Node("diagnostic_only", "Diagnostic only", "Mock Live API Readiness", "muted", 1112, 1588, 168, 42),
    Node("templates", "Evidence-Aware\nAnswer Synthesis", "Evidence-Aware Answer Rewrite", "muted", 802, 2270, 168, 42),
    Node("faithfulness_trial", "Claim Faithfulness", "Evidence-Aware Answer Rewrite", "muted", 802, 2322, 168, 42),
    Node("rewrite_trial", "Answer-only\nRewrite Trial", "Evidence-Aware Answer Rewrite", "muted", 802, 2374, 168, 42),
    Node("rewrite_status", "keep_trial_only\nnot promoted", "Evidence-Aware Answer Rewrite", "muted", 802, 2426, 168, 42),
]


CLUSTERS = [
    Cluster("cluster_input", "Input + Preflight", "Input + Preflight", 310, 30, 410, 226, "main"),
    Cluster("cluster_routing", "Routing + Query Understanding", "Routing + Query Understanding", 300, 288, 430, 462, "main"),
    Cluster("cluster_context", "Context + Planning", "Context + Planning", 300, 808, 430, 404, "main"),
    Cluster("cluster_sql", "SQL Evidence Path", "SQL Evidence Path", 92, 1288, 320, 410, "sql"),
    Cluster("cluster_api", "Adobe API Evidence Path", "Adobe API Evidence Path", 548, 1288, 480, 575, "api"),
    Cluster("cluster_evidence", "EvidenceBus", "EvidenceBus", 325, 1936, 380, 240, "evidence"),
    Cluster("cluster_answer", "Answer Generation", "Answer Generation", 325, 2232, 380, 310, "answer"),
    Cluster("cluster_package", "Trajectory + Packaging", "Trajectory + Packaging", 325, 2628, 380, 232, "final"),
    Cluster("cluster_eval", "Evaluation + Reports", "Evaluation + Reports", 60, 2918, 910, 214, "eval"),
    Cluster("cluster_diag", "Diagnostic / Trial Side Paths", "Diagnostic / Trial Side Paths", 760, 300, 260, 396, "diag"),
    Cluster("cluster_mock", "Mock Live API Readiness", "Mock Live API Readiness", 1070, 1288, 260, 362, "diag"),
    Cluster("cluster_rewrite", "Evidence-Aware Answer Rewrite", "Evidence-Aware Answer Rewrite", 760, 2232, 260, 276, "diag"),
]


EDGES = [
    Edge("user_prompt", "runtime_config"),
    Edge("runtime_config", "preflight"),
    Edge("preflight", "prompt_router"),
    Edge("prompt_router", "simple_gate"),
    Edge("simple_gate", "normalization"),
    Edge("normalization", "tokens"),
    Edge("tokens", "query_router"),
    Edge("query_router", "intent"),
    Edge("intent", "analysis"),
    Edge("analysis", "schema_catalog"),
    Edge("schema_catalog", "relevance"),
    Edge("relevance", "context_pack"),
    Edge("context_pack", "planner"),
    Edge("planner", "evidence_policy"),
    Edge("evidence_policy", "sql_api_plan"),
    Edge("sql_api_plan", "sql_template", "SQL branch"),
    Edge("sql_template", "sql_validation"),
    Edge("sql_validation", "sqlglot", "yes"),
    Edge("sqlglot", "duckdb"),
    Edge("duckdb", "sql_result"),
    Edge("sql_result", "sql_evidence"),
    Edge("sql_evidence", "evidence_bus"),
    Edge("sql_api_plan", "api_plan", "API branch"),
    Edge("api_plan", "api_validation"),
    Edge("api_validation", "headers", "yes"),
    Edge("headers", "credentials"),
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
    Edge("answer_slots", "answer_synthesis"),
    Edge("answer_synthesis", "claim_verification"),
    Edge("claim_verification", "final_answer", "supported"),
    Edge("final_answer", "trajectory"),
    Edge("trajectory", "deliverables"),
    Edge("deliverables", "final_submission"),
    Edge("final_submission", "eval_hub"),
    Edge("eval_hub", "strict_eval", "strict", "final"),
    Edge("eval_hub", "hidden_eval", "hidden", "final"),
    Edge("eval_hub", "readiness", "ready", "final"),
    Edge("eval_hub", "report_index", "reports", "final"),
    Edge("analysis", "semantic_flag", "low confidence", "diagnostic"),
    Edge("semantic_flag", "llm_client", "feature flag", "diagnostic"),
    Edge("llm_client", "semantic_helper", "SDK only", "diagnostic"),
    Edge("semantic_helper", "semantic_validation", "JSON hint", "diagnostic"),
    Edge("semantic_validation", "semantic_status", "valid", "diagnostic"),
    Edge("semantic_status", "relevance", "shadow only", "diagnostic"),
    Edge("trajectory", "llm_baseline", "baseline", "diagnostic"),
    Edge("api_plan", "fixtures", "mock live", "trial"),
    Edge("fixtures", "mock_parser", "fixture data", "trial"),
    Edge("mock_parser", "discovery", "mock", "trial"),
    Edge("discovery", "mock_forward", "GET-only", "trial"),
    Edge("mock_forward", "mock_slots", "parsed evidence", "trial"),
    Edge("mock_slots", "diagnostic_only", "verified", "trial"),
    Edge("answer_synthesis", "templates", "answer-only", "trial"),
    Edge("templates", "faithfulness_trial", "", "trial"),
    Edge("faithfulness_trial", "rewrite_trial", "", "trial"),
    Edge("rewrite_trial", "rewrite_status", "strict gate", "trial"),
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
        "layout_orientation": "vertical",
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
        Node(
            node.node_id,
            node.label.format(**values),
            node.section,
            node.kind,
            node.x,
            node.y,
            node.width,
            node.height,
        )
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
    lines = ["flowchart TB"]
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
      --bg: #ffffff;
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
      background: #ffffff;
      border-bottom: 1px solid #e5e7eb;
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
      background: #ffffff;
      padding: 16px;
    }}
    svg {{
      display: block;
      max-width: none;
      shape-rendering: geometricPrecision;
    }}
    .section-bg {{ fill: #fcfdff; stroke: #d1d5db; stroke-width: 1.05; }}
    .section-bg.sql-cluster {{ fill: #f0fdf4; stroke: #bbf7d0; }}
    .section-bg.api-cluster {{ fill: #fff7ed; stroke: #fed7aa; }}
    .section-bg.evidence-cluster {{ fill: #f0fdfa; stroke: #99f6e4; }}
    .section-bg.answer-cluster {{ fill: #fdf2f8; stroke: #fbcfe8; }}
    .section-bg.eval-cluster, .section-bg.final-cluster {{ fill: #f5f3ff; stroke: #ddd6fe; }}
    .section-bg.diag-cluster {{ fill: #f8fafc; stroke: #d1d5db; stroke-dasharray: 7 6; }}
    .section-label {{ font-size: 14px; font-weight: 800; fill: #0f172a; }}
    .node rect, .node polygon {{ stroke: #334155; stroke-width: 1.25; filter: url(#soft-shadow); }}
    .node.packaged rect, .node.packaged polygon {{ stroke-width: 2.45; }}
    .node text {{ font-size: 12px; fill: #0f172a; font-weight: 700; }}
    .node .small {{ font-size: 11px; fill: #475569; font-weight: 650; }}
    .node-muted rect, .node-muted polygon {{ stroke: #cbd5e1; stroke-width: .9; filter: none; }}
    .node-muted text {{ font-size: 10.5px; fill: #475569; font-weight: 650; }}
    .node-muted .small {{ font-size: 10px; fill: #64748b; }}
    .edge {{ fill: none; stroke: #166534; stroke-width: 2.8; marker-end: url(#arrow-packaged); }}
    .edge.final {{ stroke: #6d28d9; stroke-width: 2.0; marker-end: url(#arrow-final); }}
    .edge.diagnostic {{ stroke: #94a3b8; stroke-width: 1.55; stroke-dasharray: 7 6; marker-end: url(#arrow-muted); }}
    .edge.trial {{ stroke: #9ca3af; stroke-width: 1.55; stroke-dasharray: 7 6; marker-end: url(#arrow-trial); }}
    .edge-label {{ font-size: 11px; fill: #334155; paint-order: stroke; stroke: white; stroke-width: 4px; font-weight: 700; }}
    .input {{ fill: #dbeafe; }}
    .config {{ fill: #e0f2fe; }}
    .routing {{ fill: #e0f2fe; }}
    .understanding {{ fill: #e0f2fe; }}
    .context {{ fill: #dbeafe; }}
    .planning {{ fill: #dcfce7; }}
    .sql {{ fill: #dcfce7; }}
    .api {{ fill: #ffedd5; }}
    .live {{ fill: #fed7aa; }}
    .decision {{ fill: #fef3c7; }}
    .evidence {{ fill: #ccfbf1; }}
    .slots {{ fill: #cffafe; }}
    .answer {{ fill: #fce7f3; }}
    .trajectory {{ fill: #e0e7ff; }}
    .eval {{ fill: #ede9fe; }}
    .final {{ fill: #ddd6fe; }}
    .muted {{ fill: #f8fafc; stroke: #cbd5e1; }}
    footer {{
      height: 28px;
      padding: 5px 18px;
      color: var(--muted);
      font-size: 12px;
      background: #ffffff;
      border-top: 1px solid #e5e7eb;
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
    width = 1360
    height = 3180
    node_by_id = {node.node_id: node for node in nodes}
    positions = {node.node_id: (node.x, node.y) for node in nodes}
    required_keywords = [
        "Runtime Config",
        "Prompt Routing",
        "QueryAnalysis",
        "SQL_FIRST_API_VERIFY",
        "SQL Evidence",
        "Adobe API Evidence",
        "Adobe credentials present?",
        "Live API",
        "Dry-run fallback",
        "API Response Parser",
        "Discovery-chain readiness",
        "Mock Live API Readiness",
        "EvidenceBus",
        "Answer Slots",
        "Answer Synthesis",
        "Claim Faithfulness",
        "Final Answer",
        "Trajectory Logging",
        "Final Submission",
        "Strict Eval",
        "Hidden-style Eval",
        "LLM Semantic Routing Helper",
        "Evidence-Aware Answer Rewrite",
        "not promoted",
        "keep_trial_only",
        "packaged runtime path",
        "shadow diagnostic path",
        "isolated trial path",
    ]
    searchable = " | ".join([*MAJOR_SECTIONS, *required_keywords, *(node.label.replace("\n", " ") for node in nodes)])
    parts = [
        f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img" aria-labelledby="chart-title chart-desc">',
        '<title id="chart-title">DASHSys end-to-end system dataflow flowchart</title>',
        f'<desc id="chart-desc">{esc(searchable)}</desc>',
        "<defs>",
        '<filter id="soft-shadow" x="-10%" y="-10%" width="120%" height="125%"><feDropShadow dx="0" dy="1.2" stdDeviation="1.4" flood-color="#0f172a" flood-opacity=".12"/></filter>',
        '<marker id="arrow-packaged" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#14532d"/></marker>',
        '<marker id="arrow-final" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#6d28d9"/></marker>',
        '<marker id="arrow-muted" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#94a3b8"/></marker>',
        '<marker id="arrow-trial" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#9ca3af"/></marker>',
        "</defs>",
    ]
    for cluster in CLUSTERS:
        cluster_class = {
            "sql": "sql-cluster",
            "api": "api-cluster",
            "evidence": "evidence-cluster",
            "answer": "answer-cluster",
            "final": "final-cluster",
            "eval": "eval-cluster",
            "diag": "diag-cluster",
        }.get(cluster.kind, "main-cluster")
        parts.append(
            f'<rect id="{esc(cluster.cluster_id)}" class="section-bg {cluster_class}" x="{cluster.x}" y="{cluster.y}" '
            f'width="{cluster.width}" height="{cluster.height}" rx="16"/>'
        )
        parts.append(f'<text class="section-label" x="{cluster.x + 18}" y="{cluster.y + 28}">{esc(cluster.label)}</text>')
    for edge in edges:
        source = node_by_id[edge.source]
        target = node_by_id[edge.target]
        path = edge_path(source, target)
        parts.append(f'<path class="edge {esc(edge.path_type)}" d="{path}"/>')
        if edge.label:
            sx, sy = node_center(source)
            tx, ty = node_center(target)
            lx = (sx + tx) / 2
            ly = (sy + ty) / 2 - 8
            parts.append(f'<text class="edge-label" x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle">{esc(edge.label)}</text>')
    packaged_nodes = set()
    for edge in edges:
        if edge.path_type == "packaged":
            packaged_nodes.add(edge.source)
            packaged_nodes.add(edge.target)
    for node in nodes:
        x, y = positions[node.node_id]
        group_classes = " ".join(
            part
            for part in [
                "node",
                f"node-{node.kind}",
                "packaged" if node.node_id in packaged_nodes and node.kind != "muted" else "",
            ]
            if part
        )
        parts.append(f'<g class="{group_classes}" id="{esc(node.node_id)}">')
        if node.kind == "decision":
            cx = x + node.width / 2
            cy = y + node.height / 2
            points = f"{cx},{y} {x + node.width},{cy} {cx},{y + node.height} {x},{cy}"
            parts.append(f'<polygon class="{esc(node.kind)}" points="{points}"/>')
        else:
            parts.append(f'<rect class="{esc(node.kind)}" x="{x}" y="{y}" width="{node.width}" height="{node.height}" rx="10"/>')
        lines = compact_label_lines(node.label, 24, 4)
        y_start = y + 20 if len(lines) >= 4 else y + 24
        for i, line in enumerate(lines):
            css = ' class="small"' if i > 0 and len(lines) >= 3 else ""
            parts.append(f'<text{css} x="{x + node.width / 2}" y="{y_start + (i * 14)}" text-anchor="middle">{esc(line)}</text>')
        parts.append("</g>")
    parts.append("</svg>")
    return "\n".join(parts)


def node_center(node: Node) -> tuple[float, float]:
    return (node.x + node.width / 2, node.y + node.height / 2)


def edge_path(source: Node, target: Node) -> str:
    sx, sy = node_center(source)
    tx, ty = node_center(target)
    dx = tx - sx
    dy = ty - sy
    if abs(dx) < 95 and dy >= 0:
        start = (sx, source.y + source.height)
        end = (tx, target.y)
        mid_y = (start[1] + end[1]) / 2
        return (
            f"M {start[0]:.1f} {start[1]:.1f} "
            f"C {start[0]:.1f} {mid_y:.1f}, {end[0]:.1f} {mid_y:.1f}, {end[0]:.1f} {end[1]:.1f}"
        )
    if dx >= 0:
        start = (source.x + source.width, sy)
        end = (target.x, ty)
        bend = max(45.0, abs(dx) * 0.42)
        return (
            f"M {start[0]:.1f} {start[1]:.1f} "
            f"C {start[0] + bend:.1f} {start[1]:.1f}, {end[0] - bend:.1f} {end[1]:.1f}, "
            f"{end[0]:.1f} {end[1]:.1f}"
        )
    start = (source.x, sy)
    end = (target.x + target.width, ty)
    bend = max(45.0, abs(dx) * 0.42)
    return (
        f"M {start[0]:.1f} {start[1]:.1f} "
        f"C {start[0] - bend:.1f} {start[1]:.1f}, {end[0] + bend:.1f} {end[1]:.1f}, "
        f"{end[0]:.1f} {end[1]:.1f}"
    )


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
