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
    table,
    write_json,
    write_md,
)


STALE_SOURCE_HOURS = 72
OUTPUT_STEM = "end_to_end_system_dataflow"
IMPORTANT_SOURCES = [
    "outputs/reports/report_index.json",
    "outputs/reports/workflow_decision_map.json",
    "outputs/reports/workflow_decision_audit.json",
    "outputs/reports/live_adobe_api_readiness_audit.json",
    "outputs/reports/api_required_readiness_matrix.json",
    "outputs/reports/mock_live_api_evidence_pipeline_trial.json",
    "outputs/reports/evidence_usage_audit.json",
    "outputs/reports/evidence_aware_answer_rewrite_trial.json",
    "outputs/reports/feedback_loop_answer_synthesis_final.json",
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
    "Input and Guards",
    "Routing and Analysis",
    "Planning Context",
    "SQL Evidence Path",
    "Adobe REST API Evidence Path",
    "Evidence and Answer",
    "Packaging and Evaluation",
    "Diagnostics and Reports",
]


NODES = [
    Node("user_prompt", "User Prompt input", "Input and Guards", "input", 0, 0),
    Node("runtime_config", "Runtime config and preflight guards", "Input and Guards", "config", 0, 1),
    Node("prompt_router", "Prompt Routing", "Routing and Analysis", "routing", 1, 0),
    Node("simple_gate", "Simple prompt gate", "Routing and Analysis", "routing", 1, 1),
    Node("normalization", "Query normalization", "Routing and Analysis", "routing", 1, 2),
    Node("tokens", "Query token extraction", "Routing and Analysis", "routing", 1, 3),
    Node("query_router", "Deterministic QueryRouter", "Routing and Analysis", "routing", 1, 4),
    Node("intent", "Answer intent detection", "Routing and Analysis", "routing", 1, 5),
    Node("analysis", "QueryAnalysis", "Routing and Analysis", "analysis", 1, 6),
    Node("semantic_enabled", "semantic router feature enabled?", "Diagnostics and Reports", "decision", 2, 0),
    Node("llm_client", "SDK LLMClient", "Diagnostics and Reports", "llm", 2, 1),
    Node("semantic_helper", "LLM Semantic Routing Helper", "Diagnostics and Reports", "llm", 2, 2),
    Node("semantic_validate", "Validate routing hint", "Diagnostics and Reports", "decision", 2, 3),
    Node("semantic_promoted", "promoted or diagnostic-only?", "Diagnostics and Reports", "decision", 2, 4),
    Node("metadata_context", "Metadata/context selection", "Planning Context", "planning", 3, 0),
    Node("schema_index", "Endpoint catalog and schema index", "Planning Context", "planning", 3, 1),
    Node("plan_generation", "SQL_FIRST_API_VERIFY plan generation", "Planning Context", "planning", 3, 2),
    Node("evidence_policy", "Evidence policy", "Planning Context", "decision", 3, 3),
    Node("sql_derivation", "SQL derivation", "SQL Evidence Path", "sql", 4, 0),
    Node("sql_validation", "SQL validation passed?", "SQL Evidence Path", "decision", 4, 1),
    Node("sqlglot_ast", "SQLGlot AST validation", "SQL Evidence Path", "sql", 4, 2),
    Node("execute_sql", "execute_sql / DuckDB local snapshot", "SQL Evidence Path", "sql", 4, 3),
    Node("sql_result", "SQL result", "SQL Evidence Path", "sql", 4, 4),
    Node("sql_evidence", "SQL evidence normalization", "SQL Evidence Path", "sql", 4, 5),
    Node("api_plan", "Adobe API plan", "Adobe REST API Evidence Path", "api", 5, 0),
    Node("api_validation", "API validation passed?", "Adobe REST API Evidence Path", "decision", 5, 1),
    Node("headers", "Credential/header construction", "Adobe REST API Evidence Path", "api", 5, 2),
    Node("credentials", "Adobe credentials present?", "Adobe REST API Evidence Path", "decision", 5, 3),
    Node("live_api", "Live API mode", "Adobe REST API Evidence Path", "api", 5, 4),
    Node("dry_run_decision", "dry_run fallback?", "Adobe REST API Evidence Path", "decision", 5, 5),
    Node("dry_run", "Dry-run fallback mode", "Adobe REST API Evidence Path", "api", 5, 6),
    Node("api_parser", "API response parser", "Adobe REST API Evidence Path", "api", 5, 7),
    Node("discovery", "Discovery-chain readiness", "Adobe REST API Evidence Path", "api", 5, 8),
    Node("parsed_api", "Parsed API evidence", "Adobe REST API Evidence Path", "api", 5, 9),
    Node("evidence_bus", "EvidenceBus", "Evidence and Answer", "evidence", 6, 2),
    Node("answer_slots", "Answer Slots", "Evidence and Answer", "answer", 6, 3),
    Node("answer_synthesis", "Answer Synthesis", "Evidence and Answer", "answer", 6, 4),
    Node("answer_verify", "Answer verification / reranking", "Evidence and Answer", "answer", 6, 5),
    Node("final_answer", "Final answer", "Evidence and Answer", "answer", 6, 6),
    Node("trajectory", "Trajectory Logging", "Packaging and Evaluation", "packaging", 7, 2),
    Node("final_submission", "Final Submission packaging", "Packaging and Evaluation", "packaging", 7, 3),
    Node("strict_eval", "Strict Eval", "Packaging and Evaluation", "eval", 7, 4),
    Node("hidden_eval", "Hidden-style eval", "Packaging and Evaluation", "eval", 7, 5),
    Node("llm_baseline", "LLM baseline eval", "Packaging and Evaluation", "eval", 7, 6),
    Node("workflow_audit", "Workflow decision audit", "Diagnostics and Reports", "report", 8, 0),
    Node("live_readiness", "Live Adobe API Readiness", "Diagnostics and Reports", "report", 8, 1),
    Node("mock_fixtures", "Mock live API readiness diagnostics", "Diagnostics and Reports", "trial", 8, 2),
    Node("mock_parser", "Mock live parser + discovery simulation", "Diagnostics and Reports", "trial", 8, 3),
    Node("evidence_reports", "Evidence-Aware Answer Synthesis reports", "Diagnostics and Reports", "trial", 8, 4),
    Node("rewrite_promoted", "answer-only rewrite promoted or keep_trial_only?", "Diagnostics and Reports", "decision", 8, 5),
    Node("consolidated_index", "Consolidated report index", "Diagnostics and Reports", "report", 8, 6),
]


EDGES = [
    Edge("user_prompt", "runtime_config"),
    Edge("runtime_config", "prompt_router"),
    Edge("prompt_router", "simple_gate"),
    Edge("simple_gate", "normalization", "USE_DATA_PIPELINE"),
    Edge("normalization", "tokens"),
    Edge("tokens", "query_router"),
    Edge("query_router", "intent"),
    Edge("intent", "analysis"),
    Edge("analysis", "metadata_context"),
    Edge("metadata_context", "schema_index"),
    Edge("schema_index", "plan_generation"),
    Edge("plan_generation", "evidence_policy"),
    Edge("evidence_policy", "sql_derivation", "SQL path"),
    Edge("sql_derivation", "sql_validation"),
    Edge("sql_validation", "sqlglot_ast", "yes"),
    Edge("sqlglot_ast", "execute_sql"),
    Edge("execute_sql", "sql_result"),
    Edge("sql_result", "sql_evidence"),
    Edge("sql_evidence", "evidence_bus"),
    Edge("evidence_policy", "api_plan", "API path"),
    Edge("api_plan", "api_validation"),
    Edge("api_validation", "headers", "yes"),
    Edge("headers", "credentials"),
    Edge("credentials", "live_api", "yes"),
    Edge("credentials", "dry_run_decision", "no"),
    Edge("dry_run_decision", "dry_run", "true"),
    Edge("live_api", "api_parser"),
    Edge("dry_run", "api_parser", "dry_run=true"),
    Edge("api_parser", "discovery"),
    Edge("discovery", "parsed_api"),
    Edge("parsed_api", "evidence_bus"),
    Edge("evidence_bus", "answer_slots"),
    Edge("answer_slots", "answer_synthesis"),
    Edge("answer_synthesis", "answer_verify"),
    Edge("answer_verify", "final_answer"),
    Edge("final_answer", "trajectory"),
    Edge("trajectory", "final_submission", "packaged"),
    Edge("trajectory", "strict_eval"),
    Edge("trajectory", "hidden_eval"),
    Edge("trajectory", "llm_baseline", "baseline"),
    Edge("analysis", "semantic_enabled", "low confidence?", "diagnostic"),
    Edge("semantic_enabled", "llm_client", "if enabled", "diagnostic"),
    Edge("llm_client", "semantic_helper", "SDK only", "diagnostic"),
    Edge("semantic_helper", "semantic_validate", "JSON hint", "diagnostic"),
    Edge("semantic_validate", "semantic_promoted", "valid?", "diagnostic"),
    Edge("semantic_promoted", "workflow_audit", "shadow/diagnostic only", "diagnostic"),
    Edge("trajectory", "workflow_audit", "report-only", "diagnostic"),
    Edge("api_plan", "live_readiness", "readiness audit", "diagnostic"),
    Edge("mock_fixtures", "mock_parser", "fixture responses", "trial"),
    Edge("mock_parser", "evidence_bus", "diagnostic forwarding", "trial"),
    Edge("mock_parser", "live_readiness", "readiness report", "trial"),
    Edge("answer_synthesis", "evidence_reports", "answer-only trial", "trial"),
    Edge("evidence_reports", "rewrite_promoted", "strict gate", "trial"),
    Edge("rewrite_promoted", "consolidated_index", "keep_trial_only", "trial"),
    Edge("strict_eval", "consolidated_index", "metrics", "final"),
    Edge("hidden_eval", "consolidated_index", "robustness", "final"),
    Edge("llm_baseline", "consolidated_index", "baseline", "diagnostic"),
    Edge("live_readiness", "consolidated_index", "reports", "diagnostic"),
    Edge("workflow_audit", "consolidated_index", "reports", "diagnostic"),
    Edge("final_submission", "consolidated_index", "readiness", "final"),
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
    mermaid = build_mermaid()
    warnings = list(sources["warnings"])
    payload = {
        "generated_at": generated_at.isoformat(),
        "source_files": sources["source_files"],
        "missing_source_files": sources["missing_source_files"],
        "stale_source_warnings": sources["stale_source_warnings"],
        "current_status": status,
        "node_count": len(NODES),
        "edge_count": len(EDGES),
        "major_sections": list(MAJOR_SECTIONS),
        "mermaid_source": mermaid,
        "output_html_path": str(VIS_DIR / f"{OUTPUT_STEM}.html"),
        "output_md_path": str(VIS_DIR / f"{OUTPUT_STEM}.md"),
        "warnings": warnings,
    }
    html_text = render_html(payload)
    md_text = render_markdown(payload)
    write_html(VIS_DIR / f"{OUTPUT_STEM}.html", html_text)
    write_md(VIS_DIR / f"{OUTPUT_STEM}.md", md_text)
    write_json(VIS_DIR / f"{OUTPUT_STEM}.json", payload)
    return payload


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
        info = {
            "path": rel,
            "exists": True,
            "source_timestamp": source_time.isoformat(),
            "timestamp_source": "generated_at" if generated else "file_mtime",
            "age_hours": round(age_hours, 3),
        }
        source_files.append(info)
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
    sdk = load_json("outputs/reports/sdk_usage_audit.json", {})
    workshop = load_json("outputs/reports/workshop_requirement_audit.json", {})
    strict = load_json("outputs/eval_results_strict.json", {})
    hidden = load_json("outputs/hidden_style_eval.json", {})
    readiness = load_json("outputs/winner_readiness_report.json", {})

    index_status = index.get("current_status", {}) if isinstance(index, dict) else {}
    strict_summary = strict.get("summary", {}).get("by_strategy", {}).get("SQL_FIRST_API_VERIFY", {})
    hidden_summary = hidden.get("summary", {}) if isinstance(hidden, dict) else {}
    packaged = readiness.get("packaged", {}) if isinstance(readiness, dict) else {}
    live = system.get("live_adobe_api_readiness", {}) if isinstance(system, dict) else {}
    semantic = system.get("llm_semantic_routing_helper", {}) if isinstance(system, dict) else {}
    evidence = system.get("evidence_aware_answer_synthesis", {}) if isinstance(system, dict) else {}
    return clean_status(
        {
            "preferred_strategy": first_value(system.get("preferred_strategy"), packaged.get("preferred_strategy"), "SQL_FIRST_API_VERIFY"),
            "packaged_strict_score": first_value(
                system.get("packaged_strict_score"),
                packaged.get("strict_final_score"),
                strict_summary.get("avg_final_score"),
                index_status.get("packaged_strict_score"),
            ),
            "best_isolated_score": first_value(system.get("best_isolated_score"), index_status.get("best_isolated_score")),
            "hidden_style": first_value(
                (system.get("hidden_style") or {}).get("label") if isinstance(system.get("hidden_style"), dict) else None,
                f"{hidden_summary.get('passed_cases')}/{hidden_summary.get('total_cases')}"
                if hidden_summary.get("passed_cases") is not None and hidden_summary.get("total_cases") is not None
                else None,
                index_status.get("hidden_style"),
            ),
            "final_submission_ready": first_value(system.get("final_submission_ready"), packaged.get("final_submission_ready"), index_status.get("final_submission_ready")),
            "live_adobe_api_readiness": first_value(live.get("overall_status"), index_status.get("live_adobe_api_readiness")),
            "mock_parser_success_count": first_value(live.get("mock_parser_success_count"), mock.get("parser_success_count")),
            "mock_discovery_chains_simulated": first_value(live.get("mock_discovery_chain_simulated_count"), mock.get("discovery_chain_simulated_count")),
            "evidence_aware_answer_synthesis_recommendation": first_value(evidence.get("recommendation"), index_status.get("evidence_aware_answer_synthesis")),
            "semantic_router_recommendation": first_value(semantic.get("recommendation"), index_status.get("llm_recommendation")),
            "runtime_llm_direct_http_hits": first_value(sdk.get("summary", {}).get("runtime_llm_direct_http_hits")),
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


def build_mermaid() -> str:
    lines = ["flowchart LR"]
    by_section: dict[str, list[Node]] = {section: [] for section in MAJOR_SECTIONS}
    for node in NODES:
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
    for edge in EDGES:
        connector = "-.->" if edge.path_type in {"diagnostic", "trial"} else "-->"
        label = f"|{mermaid_label(edge.label, 36)}|" if edge.label else ""
        lines.append(f"  {edge.source} {connector}{label} {edge.target}")
    for kind in sorted({node.kind for node in NODES}):
        lines.append(f"  classDef {kind} fill:{color_for_kind(kind)},stroke:#243044,color:#111827,stroke-width:1px;")
    for node in NODES:
        lines.append(f"  class {node.node_id} {node.kind};")
    return "\n".join(lines)


def mermaid_label(value: Any, max_chars: int = 64) -> str:
    text = str(value if value is not None else "unavailable")
    text = redact_text(text)
    text = re.sub(r"[\n\r\t{}<>|`]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_chars:
        text = text[: max_chars - 3].rstrip() + "..."
    return text.replace('"', "'")


def render_html(payload: dict[str, Any]) -> str:
    status_rows = "".join(
        f"<tr><th>{esc(key.replace('_', ' ').title())}</th><td>{esc(value)}</td></tr>"
        for key, value in payload["current_status"].items()
    )
    source_rows = "".join(
        f"<tr><td>{esc(item['path'])}</td><td>{esc(item['timestamp_source'])}</td><td>{esc(item['age_hours'])}</td></tr>"
        for item in payload["source_files"]
    )
    warning_items = "".join(f"<li>{esc(item)}</li>" for item in payload["warnings"]) or "<li>none</li>"
    report_links = [
        ("Report index", "../reports/report_index.md"),
        ("Workflow decision audit", "../reports/workflow_decision_audit.md"),
        ("Live Adobe API readiness", "../reports/live_adobe_api_readiness_audit.md"),
        ("API_REQUIRED readiness matrix", "../reports/api_required_readiness_matrix.md"),
        ("Mock live API pipeline", "../reports/mock_live_api_evidence_pipeline_trial.md"),
        ("Evidence usage audit", "../reports/evidence_usage_audit.md"),
        ("Evidence-aware answer trial", "../reports/evidence_aware_answer_rewrite_trial.md"),
        ("SDK usage audit", "../reports/sdk_usage_audit.md"),
        ("Workshop audit", "../reports/workshop_requirement_audit.md"),
    ]
    links = "".join(f'<li><a href="{esc(href)}">{esc(label)}</a></li>' for label, href in report_links)
    svg = render_svg()
    workflow_keywords = " | ".join(
        [
            *MAJOR_SECTIONS,
            *(node.label for node in NODES),
            "packaged runtime path",
            "shadow/diagnostic path",
            "isolated trial path",
            "final submission/evaluation path",
            "Evidence-Aware Answer Synthesis",
            "Mock live API readiness diagnostics",
        ]
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>DASHSys End-to-End System Data Flow</title>
  <style>
    :root {{
      --bg: #f8fafc;
      --ink: #111827;
      --muted: #4b5563;
      --panel: #ffffff;
      --line: #334155;
      --packaged: #14532d;
      --diagnostic: #6d28d9;
      --trial: #a16207;
      --final: #1d4ed8;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: var(--bg); color: var(--ink); font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    header {{ padding: 28px 32px 12px; }}
    h1 {{ margin: 0 0 8px; font-size: 30px; letter-spacing: 0; }}
    p {{ color: var(--muted); line-height: 1.5; }}
    .grid {{ display: grid; grid-template-columns: minmax(320px, 1.2fr) minmax(320px, .8fr); gap: 16px; padding: 0 32px 18px; }}
    .panel {{ background: var(--panel); border: 1px solid #dbe3ef; border-radius: 8px; padding: 16px; box-shadow: 0 1px 2px rgba(15,23,42,.04); }}
    .panel h2 {{ margin: 0 0 12px; font-size: 18px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th, td {{ border-top: 1px solid #e5e7eb; padding: 7px 8px; text-align: left; vertical-align: top; }}
    th {{ width: 44%; color: #334155; font-weight: 650; }}
    a {{ color: #1d4ed8; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .legend {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }}
    .chip {{ display: inline-flex; align-items: center; gap: 6px; border: 1px solid #dbe3ef; border-radius: 999px; padding: 5px 9px; font-size: 12px; background: #fff; }}
    .dot {{ width: 12px; height: 12px; border-radius: 50%; display: inline-block; }}
    .chart-wrap {{ margin: 0 32px 32px; background: white; border: 1px solid #dbe3ef; border-radius: 8px; overflow: auto; }}
    .chart-title {{ padding: 14px 16px 0; font-weight: 700; }}
    .sr-only {{ position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; border: 0; }}
    svg {{ display: block; min-width: 2140px; }}
    .section-label {{ font-size: 14px; font-weight: 750; fill: #0f172a; }}
    .section-bg {{ fill: #f8fafc; stroke: #cbd5e1; stroke-width: 1; }}
    .node rect, .node polygon {{ stroke: #243044; stroke-width: 1.2; }}
    .node text {{ font-size: 12px; fill: #111827; font-weight: 650; }}
    .node small {{ color: #475569; }}
    .edge {{ fill: none; stroke: var(--line); stroke-width: 2.4; marker-end: url(#arrow); }}
    .edge.diagnostic {{ stroke: var(--diagnostic); stroke-dasharray: 7 6; marker-end: url(#arrow-diagnostic); }}
    .edge.trial {{ stroke: var(--trial); stroke-dasharray: 6 5; marker-end: url(#arrow-trial); }}
    .edge.final {{ stroke: var(--final); stroke-width: 2.2; marker-end: url(#arrow-final); }}
    .edge-label {{ font-size: 11px; fill: #334155; paint-order: stroke; stroke: white; stroke-width: 3px; }}
    .input {{ fill: #dbeafe; }}
    .config {{ fill: #e0f2fe; }}
    .routing {{ fill: #ede9fe; }}
    .analysis {{ fill: #f5e8ff; }}
    .planning {{ fill: #fef3c7; }}
    .sql {{ fill: #dcfce7; }}
    .api {{ fill: #ffedd5; }}
    .decision {{ fill: #fee2e2; }}
    .evidence {{ fill: #ccfbf1; }}
    .answer {{ fill: #d1fae5; }}
    .packaging {{ fill: #e0e7ff; }}
    .eval {{ fill: #dbeafe; }}
    .llm {{ fill: #f3e8ff; }}
    .report {{ fill: #f1f5f9; }}
    .trial {{ fill: #fef9c3; }}
    footer {{ padding: 0 32px 32px; color: var(--muted); font-size: 12px; }}
  </style>
</head>
<body>
  <header>
    <h1>DASHSys End-to-End System Data Flow</h1>
    <p>Auto-generated from current DASHSys reports and configuration artifacts. The dominant solid path is packaged <code>SQL_FIRST_API_VERIFY</code>; dashed paths are diagnostic, shadow, or isolated trial only.</p>
  </header>
  <section class="grid">
    <div class="panel">
      <h2>Current System Status</h2>
      <table>{status_rows}</table>
    </div>
    <div class="panel">
      <h2>Legend</h2>
      <div class="legend">
        <span class="chip"><span class="dot" style="background:#14532d"></span>packaged runtime path</span>
        <span class="chip"><span class="dot" style="background:#6d28d9"></span>shadow/diagnostic path</span>
        <span class="chip"><span class="dot" style="background:#a16207"></span>isolated trial path</span>
        <span class="chip"><span class="dot" style="background:#1d4ed8"></span>packaging/evaluation path</span>
        <span class="chip"><span class="dot" style="background:#fee2e2"></span>decision node</span>
      </div>
      <h2 style="margin-top:18px">Report Links</h2>
      <ul>{links}</ul>
    </div>
  </section>
  <section class="chart-wrap">
    <div class="chart-title">Complete Runtime, Diagnostic, Evaluation, and Reporting Flowchart</div>
    <p class="sr-only">{esc(workflow_keywords)}</p>
    {svg}
  </section>
  <section class="grid">
    <div class="panel">
      <h2>Source Artifacts Used</h2>
      <table><tr><th>Path</th><th>Timestamp Source</th><th>Age Hours</th></tr>{source_rows}</table>
    </div>
    <div class="panel">
      <h2>Warnings</h2>
      <ul>{warning_items}</ul>
    </div>
  </section>
  <footer>
    Generated at {esc(payload['generated_at'])}. Fully self-contained; no CDN, network access, or build tools required.
  </footer>
</body>
</html>
"""


def render_svg() -> str:
    node_w = 190
    node_h = 58
    col_gap = 232
    row_gap = 84
    margin_x = 28
    margin_y = 62
    max_col = max(node.col for node in NODES)
    max_row = max(node.row for node in NODES)
    width = margin_x * 2 + max_col * col_gap + node_w + 40
    height = margin_y * 2 + max_row * row_gap + node_h + 80
    positions = {
        node.node_id: (
            margin_x + node.col * col_gap,
            margin_y + node.row * row_gap,
        )
        for node in NODES
    }
    section_col: dict[str, int] = {}
    for node in NODES:
        section_col.setdefault(node.section, node.col)
    parts = [
        f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img" aria-labelledby="chart-title">',
        '<title id="chart-title">DASHSys end-to-end system dataflow flowchart</title>',
        "<defs>",
        '<marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#334155"/></marker>',
        '<marker id="arrow-diagnostic" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#6d28d9"/></marker>',
        '<marker id="arrow-trial" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#a16207"/></marker>',
        '<marker id="arrow-final" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#1d4ed8"/></marker>',
        "</defs>",
    ]
    for section in MAJOR_SECTIONS:
        col = section_col.get(section)
        if col is None:
            continue
        x = margin_x + col * col_gap - 12
        parts.append(f'<rect class="section-bg" x="{x}" y="18" width="{node_w + 24}" height="{height - 42}" rx="8"/>')
        parts.append(f'<text class="section-label" x="{x + 12}" y="42">{esc(section)}</text>')
    for edge in EDGES:
        x1, y1 = positions[edge.source]
        x2, y2 = positions[edge.target]
        start = (x1 + node_w, y1 + node_h / 2)
        end = (x2, y2 + node_h / 2)
        if x2 <= x1:
            start = (x1 + node_w / 2, y1 + node_h)
            end = (x2 + node_w / 2, y2)
        cx1 = start[0] + max(34, abs(end[0] - start[0]) * 0.35)
        cx2 = end[0] - max(34, abs(end[0] - start[0]) * 0.35)
        if x2 <= x1:
            cx1 = start[0]
            cx2 = end[0]
        path = f"M {start[0]:.1f} {start[1]:.1f} C {cx1:.1f} {start[1]:.1f}, {cx2:.1f} {end[1]:.1f}, {end[0]:.1f} {end[1]:.1f}"
        parts.append(f'<path class="edge {esc(edge.path_type)}" d="{path}"/>')
        if edge.label:
            lx = (start[0] + end[0]) / 2
            ly = (start[1] + end[1]) / 2 - 8
            parts.append(f'<text class="edge-label" x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle">{esc(edge.label)}</text>')
    for node in NODES:
        x, y = positions[node.node_id]
        parts.append(f'<g class="node" id="{esc(node.node_id)}">')
        if node.kind == "decision":
            cx = x + node_w / 2
            cy = y + node_h / 2
            points = f"{cx},{y} {x + node_w},{cy} {cx},{y + node_h} {x},{cy}"
            parts.append(f'<polygon class="{esc(node.kind)}" points="{points}" rx="8"/>')
        else:
            parts.append(f'<rect class="{esc(node.kind)}" x="{x}" y="{y}" width="{node_w}" height="{node_h}" rx="8"/>')
        for i, line in enumerate(wrap_label(node.label, 24)[:3]):
            parts.append(f'<text x="{x + node_w / 2}" y="{y + 21 + (i * 15)}" text-anchor="middle">{esc(line)}</text>')
        parts.append("</g>")
    parts.append("</svg>")
    return "\n".join(parts)


def render_markdown(payload: dict[str, Any]) -> str:
    status_rows = [[key.replace("_", " "), value] for key, value in payload["current_status"].items()]
    links = [
        ["HTML artifact", "outputs/visualizations/end_to_end_system_dataflow.html"],
        ["JSON metadata", "outputs/visualizations/end_to_end_system_dataflow.json"],
        ["Report index", "outputs/reports/report_index.md"],
    ]
    return "\n".join(
        [
            "# DASHSys End-to-End System Data Flow",
            "",
            "Auto-generated system documentation. The HTML artifact is fully self-contained and is the primary browser view.",
            "",
            "## Flowchart",
            "",
            mermaid_block(payload["mermaid_source"]),
            "",
            "## Current Status",
            "",
            table(["Field", "Value"], status_rows),
            "",
            "## Artifact Links",
            "",
            table(["Artifact", "Path"], links),
            "",
            "## Source Warnings",
            "",
            *(f"- `{warning}`" for warning in payload["warnings"]),
            "",
        ]
    )


def write_html(path: Path, content: str) -> None:
    ensure_visualization_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(redact_text(content), encoding="utf-8")


def color_for_kind(kind: str) -> str:
    return {
        "input": "#dbeafe",
        "config": "#e0f2fe",
        "routing": "#ede9fe",
        "analysis": "#f5e8ff",
        "planning": "#fef3c7",
        "sql": "#dcfce7",
        "api": "#ffedd5",
        "decision": "#fee2e2",
        "evidence": "#ccfbf1",
        "answer": "#d1fae5",
        "packaging": "#e0e7ff",
        "eval": "#dbeafe",
        "llm": "#f3e8ff",
        "report": "#f1f5f9",
        "trial": "#fef9c3",
    }.get(kind, "#f8fafc")


def wrap_label(label: str, width: int) -> list[str]:
    words = str(label).split()
    lines: list[str] = []
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
    return lines or [str(label)]


def esc(value: Any) -> str:
    return html.escape(redact_text(str(value)), quote=True)


if __name__ == "__main__":
    raise SystemExit(main())
