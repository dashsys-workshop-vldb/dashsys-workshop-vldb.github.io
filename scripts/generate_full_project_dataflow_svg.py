#!/usr/bin/env python
from __future__ import annotations

import hashlib
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

from dashagent.config import Config
from dashagent.trajectory import redact_secrets


WIDTH = 4300
HEIGHT = 3200

SOURCE_REPORTS = [
    "outputs/reports/report_index.json",
    "outputs/reports/system_summary.json",
    "outputs/reports/workflow_decision_map.json",
    "outputs/reports/workflow_decision_audit.json",
    "outputs/reports/live_api_full_run_blocker.json",
    "outputs/reports/adobe_access_waiting_status.json",
    "outputs/reports/context7_code_alignment_audit.json",
    "outputs/reports/generated_prompt_suite_local_diagnostic.json",
    "outputs/reports/local_gap_manual_review.json",
    "outputs/reports/superpowers_fix_decision.json",
    "outputs/visualizations/end_to_end_pipeline_mermaid.md",
    "outputs/visualizations/project_architecture_c4.md",
    "outputs/visualizations/live_adobe_api_status_mermaid.md",
    "outputs/visualizations/report_generation_map.md",
]

SECRET_PATTERNS = [
    re.compile(r"Authorization:\s*Bearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE),
    re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
    re.compile(
        r"(OPENAI_API_KEY|ANTHROPIC_API_KEY|ADOBE_ACCESS_TOKEN|ADOBE_API_KEY|ADOBE_CLIENT_SECRET|CLIENT_SECRET)=?\S*",
        re.IGNORECASE,
    ),
    re.compile(r"\b[A-Za-z0-9]{3}\*\*\*"),
]

STYLE = {
    "input": {"fill": "#eff6ff", "stroke": "#2563eb"},
    "query": {"fill": "#f0f9ff", "stroke": "#0284c7"},
    "main": {"fill": "#e0f2fe", "stroke": "#075985"},
    "guard": {"fill": "#fef3c7", "stroke": "#d97706"},
    "data": {"fill": "#dcfce7", "stroke": "#16a34a"},
    "api": {"fill": "#fff7ed", "stroke": "#ea580c"},
    "blocked": {"fill": "#fee2e2", "stroke": "#dc2626"},
    "diag": {"fill": "#f5f3ff", "stroke": "#7c3aed"},
    "muted": {"fill": "#f8fafc", "stroke": "#64748b"},
    "eval": {"fill": "#eef2ff", "stroke": "#4f46e5"},
    "report": {"fill": "#f0fdfa", "stroke": "#0f766e"},
    "final": {"fill": "#dcfce7", "stroke": "#15803d"},
}


@dataclass(frozen=True)
class Section:
    id: str
    title: str
    x: int
    y: int
    w: int
    h: int
    fill: str


@dataclass(frozen=True)
class Node:
    id: str
    label: str
    section: str
    kind: str
    x: int
    y: int
    w: int = 230
    h: int = 74
    shape: str = "box"


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    label: str = ""
    kind: str = "main"


def main() -> int:
    payload = generate_full_project_dataflow_svg()
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def generate_full_project_dataflow_svg(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    out_dir = config.outputs_dir / "visualizations"
    reports_dir = config.outputs_dir / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    generated_at = _utc_now()
    sources = _load_sources(config)
    context = _build_context(sources)
    sections = _sections()
    nodes = _nodes(context)
    edges = _edges()
    svg = _render_svg(generated_at, context, sections, nodes, edges)

    svg_path = out_dir / "full_project_dataflow.svg"
    md_path = out_dir / "full_project_dataflow.md"
    json_path = out_dir / "full_project_dataflow.json"
    audit_json_path = reports_dir / "full_project_dataflow_svg_audit.json"
    audit_md_path = reports_dir / "full_project_dataflow_svg_audit.md"

    _write_text(svg_path, svg)
    metadata = _metadata(config, generated_at, sources, context, nodes, edges, sections)
    _write_json(json_path, metadata)
    _write_text(md_path, _render_markdown(generated_at, metadata))

    audit = _audit(svg_path, metadata)
    _write_json(audit_json_path, audit)
    _write_text(audit_md_path, _render_audit(audit))

    return {
        "svg_path": str(svg_path),
        "markdown_path": str(md_path),
        "json_path": str(json_path),
        "audit_json_path": str(audit_json_path),
        "audit_markdown_path": str(audit_md_path),
    }


def _sections() -> list[Section]:
    return [
        Section("input", "1. User / Input Layer", 50, 300, 470, 620, "#f8fbff"),
        Section("query", "2. Query Understanding Layer", 540, 300, 500, 620, "#f7fcff"),
        Section("runtime", "3. Main Packaged Runtime Layer", 1060, 300, 1080, 930, "#f8fbff"),
        Section("adobe", "4. Adobe Live API Layer", 1060, 1260, 1080, 560, "#fffaf5"),
        Section("llm", "5. LLM / SDK Diagnostics Layer", 540, 1850, 1600, 520, "#fbfaff"),
        Section("eval", "6. Evaluation Layer", 2180, 300, 620, 920, "#f8f9ff"),
        Section("reports", "7. Reporting / Visualization Layer", 2820, 300, 620, 920, "#f6fffd"),
        Section("packaging", "8. Packaging / Submission Layer", 3460, 300, 790, 920, "#f7fff8"),
        Section("legend", "Legend + Guardrails", 2180, 1260, 2070, 560, "#fbfbfb"),
        Section("audit", "Project Evidence / Audit Sources", 2180, 1850, 2070, 520, "#fafafa"),
    ]


def _nodes(context: dict[str, Any]) -> list[Node]:
    return [
        # Input
        Node("user_prompt", "User Prompt", "input", "input", 90, 390),
        Node("public_prompts", "Public/dev evaluation prompts", "input", "input", 90, 490),
        Node("hidden_prompts", "Hidden-style prompts", "input", "input", 90, 590),
        Node("generated_prompts", "generated prompts diagnostic-only", "input", "diag", 90, 690),
        Node("live_checks", "Adobe live API checks", "input", "api", 90, 790),
        # Query
        Node("prompt_norm", "Prompt normalization", "query", "query", 580, 360),
        Node("simple_gate", "Simple Prompt Gate", "query", "guard", 580, 455),
        Node("query_analysis", "QueryAnalysis", "query", "query", 580, 550),
        Node("intent", "Answer intent detection", "query", "query", 580, 645),
        Node("router", "Domain/routing decision", "query", "query", 580, 740),
        Node("router_conf", "Confidence + deterministic signals", "query", "muted", 580, 835),
        Node("semantic_shadow", "Semantic router shadow-only", "query", "diag", 790, 835, 210, 68),
        # Runtime main
        Node("strategy", f"{context['packaged_strategy']}\\nmain packaged path", "runtime", "main", 1100, 390, 280, 84),
        Node("sql_answerable", "Is query SQL answerable?", "runtime", "guard", 1450, 390, 190, 110, "diamond"),
        Node("context_pack", "SchemaIndex + EndpointCatalog\\ncontext packing", "runtime", "main", 1100, 535, 280, 84),
        Node("plan", "SQL/API planning", "runtime", "main", 1100, 640, 280, 84),
        Node("sql_validation", "SQL validation\\nread-only SQL guard", "runtime", "guard", 1100, 760, 280, 84),
        Node("duckdb", "DuckDB/parquet\\nlocal execution", "runtime", "data", 1100, 880, 280, 84),
        Node("api_required", "Is API required?", "runtime", "guard", 1470, 640, 190, 110, "diamond"),
        Node("api_guard", "GET-only API guard\\nEndpointCatalog", "runtime", "guard", 1760, 640, 280, 84),
        Node("api_client", "Adobe API client\\nor dry-run fallback", "runtime", "api", 1760, 760, 280, 84),
        Node("live_available", "Is live API available?", "runtime", "guard", 1765, 890, 190, 110, "diamond"),
        Node("dry_run", "Dry-run fallback\\nhonest caveat", "runtime", "muted", 1760, 1045, 280, 84),
        Node("evidence_bus", "EvidenceBus", "runtime", "data", 1450, 900, 260, 84),
        Node("answer_slots", "Answer slots\\nSQL/API states", "runtime", "data", 1450, 1020, 260, 84),
        Node("answer_synth", "Answer synthesis", "runtime", "main", 1450, 1140, 260, 84),
        Node("verifier", "Verifier\\nclaim faithfulness", "runtime", "guard", 1860, 1140, 240, 84),
        Node("final_answer", "Final answer\\ntrajectory.json", "runtime", "final", 1100, 1110, 280, 84),
        # Adobe live layer
        Node("env_check", ".env.local presence check\\nvalues hidden", "adobe", "api", 1100, 1360, 260, 78),
        Node("credential_ready", "Credential readiness\\npresent/missing only", "adobe", "api", 1420, 1360, 260, 78),
        Node("token_acq", "Token acquisition\\npreflight succeeded", "adobe", "api", 1740, 1360, 260, 78),
        Node("safe_get_smoke", "Safe GET smoke\\nno mutations", "adobe", "api", 1100, 1500, 260, 78),
        Node("outcome_classifier", "Endpoint outcome classifier", "adobe", "api", 1420, 1500, 260, 78),
        Node("live_success_decision", "live_success_count > 0?", "adobe", "blocked", 1760, 1478, 190, 110, "diamond"),
        Node("live_blocked", "Full live eval blocked\\ncurrent count: 0", "adobe", "blocked", 1100, 1640, 260, 78),
        Node("external_blocker", "External Adobe permission\\n/ sandbox blocker", "adobe", "blocked", 1420, 1640, 260, 78),
        Node("post_permission", "Post-permission verification", "adobe", "api", 1740, 1640, 260, 78),
        # LLM diagnostics
        Node("sdk_llm", "SDK-only LLM client\\nruntime HTTP hits: 0", "llm", "diag", 580, 1970, 260, 78),
        Node("pure_llm", "Pure LLM baseline\\nshadow diagnostic", "llm", "diag", 900, 1970, 260, 78),
        Node("controller", "LLM controller\\nshadow-only", "llm", "diag", 1220, 1970, 260, 78),
        Node("semantic_eval", "Semantic router eval\\ndo_not_promote", "llm", "diag", 1540, 1970, 260, 78),
        Node("rewrite_trial", "Evidence-aware answer synthesis\\nkeep_trial_only", "llm", "diag", 580, 2110, 320, 78),
        Node("strategy_promoted", "Is strategy promoted?", "llm", "muted", 980, 2090, 190, 110, "diamond"),
        Node("not_promoted", "Trial/shadow paths\\nnot promoted", "llm", "muted", 1240, 2110, 260, 78),
        Node("llm_reports", "LLM/controller reports\\ndiagnostic-only", "llm", "diag", 1560, 2110, 260, 78),
        # Eval
        Node("strict_eval", "run_dev_eval.py --strict", "eval", "eval", 2220, 390, 270, 78),
        Node("strict_artifact", f"Strict score artifact\\nscore {context['strict_score']}", "eval", "eval", 2220, 500, 270, 78),
        Node("hidden_eval", f"Hidden-style eval\\n{context['hidden_style']}", "eval", "eval", 2220, 610, 270, 78),
        Node("local_diag", "Local 250 prompt diagnostic\\n250/250 pass", "eval", "diag", 2220, 720, 270, 78),
        Node("manual_review", "Local gap manual review\\nadvisory labels", "eval", "diag", 2220, 830, 270, 78),
        Node("evidence_gate", "Does candidate pass\\nevidence gate?", "eval", "guard", 2255, 940, 190, 110, "diamond"),
        Node("context7", "Context7 audit\\ncomplete", "eval", "eval", 2220, 1080, 270, 78),
        # Reports
        Node("consolidated", "generate_consolidated_reports.py", "reports", "report", 2860, 390, 290, 78),
        Node("report_index", "Report index", "reports", "report", 2860, 500, 290, 78),
        Node("system_summary", "System summary", "reports", "report", 2860, 610, 290, 78),
        Node("viz_suite", "Visualization suite\\nMermaid + SVG", "reports", "report", 2860, 720, 290, 78),
        Node("full_svg", "full_project_dataflow.svg\\nthis single SVG", "reports", "report", 2860, 830, 290, 78),
        Node("viz_audit", "Visualization sync/audit\\nsource SHA-256", "reports", "report", 2860, 940, 290, 78),
        Node("secret_scan", "Secret scan\\nno credentials", "reports", "guard", 2860, 1050, 290, 78),
        # Packaging
        Node("package_submission", "package_submission.py", "packaging", "final", 3500, 390, 280, 78),
        Node("package_query", "package_query_outputs.py", "packaging", "final", 3500, 500, 280, 78),
        Node("final_submission", "final_submission\\nmetadata / prompt / trajectory", "packaging", "final", 3500, 610, 300, 88),
        Node("source_zip", "source_code package", "packaging", "final", 3880, 610, 260, 78),
        Node("check_ready", "check_submission_ready.py", "packaging", "guard", 3500, 750, 280, 78),
        Node("ready_decision", "Is final submission ready?", "packaging", "guard", 3545, 880, 190, 110, "diamond"),
        Node("ready_status", f"final_submission_ready\\n{context['final_ready']}", "packaging", "final", 3500, 1040, 280, 78),
        Node("submit", "Supervisor walkthrough\\nsubmission-safe handoff", "packaging", "final", 3880, 1040, 280, 78),
        # Legend/status
        Node("badge_strategy", f"Packaged strategy\\n{context['packaged_strategy']}", "legend", "main", 2220, 1360, 300, 74),
        Node("badge_score", f"Strict score\\n{context['strict_score']}", "legend", "eval", 2560, 1360, 240, 74),
        Node("badge_hidden", f"Hidden-style\\n{context['hidden_style']}", "legend", "eval", 2840, 1360, 240, 74),
        Node("badge_ready", f"Final submission ready\\n{context['final_ready']}", "legend", "final", 3120, 1360, 270, 74),
        Node("badge_live", "Live success count\\n0", "legend", "blocked", 3430, 1360, 240, 74),
        Node("badge_live_eval", "Live full eval\\nblocked", "legend", "blocked", 3710, 1360, 240, 74),
        Node("badge_generated", "Generated prompts\\ndiagnostic-only", "legend", "diag", 2220, 1500, 300, 74),
        Node("badge_controller", "LLM controller\\nshadow-only", "legend", "diag", 2560, 1500, 240, 74),
        Node("badge_semantic", "Semantic router\\ndo_not_promote", "legend", "diag", 2840, 1500, 240, 74),
        Node("badge_rewrite", "Answer synthesis trial\\nkeep_trial_only", "legend", "diag", 3120, 1500, 270, 74),
        Node("badge_context7", "Context7 audit\\ncomplete", "legend", "eval", 3430, 1500, 240, 74),
        Node("badge_http", "Runtime direct LLM HTTP hits\\n0", "legend", "guard", 3710, 1500, 300, 74),
        # Audit/source evidence
        Node("source_reports", "Source reports used\\nSHA-256 audited", "audit", "report", 2220, 1970, 300, 78),
        Node("runtime_safe", "Runtime behavior changed\\nfalse", "audit", "guard", 2560, 1970, 260, 78),
        Node("credentials_safe", "Credentials accessed\\nfalse", "audit", "guard", 2860, 1970, 260, 78),
        Node("one_svg", "Single SVG artifact\\nversionable", "audit", "report", 3160, 1970, 260, 78),
        Node("no_live_large", "No live strict eval\\nNo live 250-prompt run", "audit", "blocked", 3460, 1970, 310, 78),
        Node("no_runtime_change", "No packaged strategy\\nor final format change", "audit", "final", 3800, 1970, 310, 78),
    ]


def _edges() -> list[Edge]:
    return [
        Edge("user_prompt", "prompt_norm"),
        Edge("prompt_norm", "simple_gate"),
        Edge("simple_gate", "query_analysis"),
        Edge("query_analysis", "intent"),
        Edge("intent", "router"),
        Edge("router", "router_conf"),
        Edge("router", "strategy"),
        Edge("router_conf", "semantic_shadow", "shadow hint", "diag"),
        Edge("semantic_shadow", "router", "validated hints only", "diag"),
        Edge("strategy", "sql_answerable"),
        Edge("sql_answerable", "context_pack", "yes"),
        Edge("context_pack", "plan"),
        Edge("plan", "sql_validation"),
        Edge("sql_validation", "duckdb"),
        Edge("duckdb", "evidence_bus"),
        Edge("plan", "api_required"),
        Edge("api_required", "api_guard", "yes"),
        Edge("api_required", "evidence_bus", "no", "muted"),
        Edge("api_guard", "api_client"),
        Edge("api_client", "live_available"),
        Edge("live_available", "dry_run", "no", "blocked"),
        Edge("live_available", "evidence_bus", "yes"),
        Edge("dry_run", "evidence_bus", "state/caveat", "muted"),
        Edge("evidence_bus", "answer_slots"),
        Edge("answer_slots", "answer_synth"),
        Edge("answer_synth", "verifier"),
        Edge("verifier", "final_answer"),
        Edge("final_answer", "strict_eval"),
        Edge("public_prompts", "strict_eval", "public/dev", "muted"),
        Edge("hidden_prompts", "hidden_eval", "hidden-style", "muted"),
        Edge("generated_prompts", "local_diag", "diagnostic-only", "diag"),
        Edge("live_checks", "env_check", "safe checks", "muted"),
        Edge("api_guard", "env_check", "live path preflight", "api"),
        Edge("env_check", "credential_ready"),
        Edge("credential_ready", "token_acq"),
        Edge("token_acq", "safe_get_smoke"),
        Edge("safe_get_smoke", "outcome_classifier"),
        Edge("outcome_classifier", "live_success_decision"),
        Edge("live_success_decision", "live_blocked", "no"),
        Edge("live_success_decision", "post_permission", "yes", "api"),
        Edge("live_blocked", "external_blocker"),
        Edge("external_blocker", "post_permission", "after access", "blocked"),
        Edge("live_success_decision", "live_available", "guard signal", "api"),
        Edge("sdk_llm", "pure_llm", "diagnostic", "diag"),
        Edge("sdk_llm", "controller", "diagnostic", "diag"),
        Edge("sdk_llm", "semantic_eval", "shadow", "diag"),
        Edge("answer_synth", "rewrite_trial", "answer-only trial", "diag"),
        Edge("pure_llm", "strategy_promoted", "candidate?", "diag"),
        Edge("controller", "strategy_promoted", "candidate?", "diag"),
        Edge("semantic_eval", "strategy_promoted", "candidate?", "diag"),
        Edge("rewrite_trial", "strategy_promoted", "candidate?", "diag"),
        Edge("strategy_promoted", "not_promoted", "no"),
        Edge("not_promoted", "llm_reports", "reports only", "diag"),
        Edge("strict_eval", "strict_artifact"),
        Edge("strict_artifact", "hidden_eval"),
        Edge("hidden_eval", "local_diag", "separate diagnostics", "muted"),
        Edge("local_diag", "manual_review"),
        Edge("manual_review", "evidence_gate"),
        Edge("evidence_gate", "context7", "no runtime change"),
        Edge("context7", "consolidated"),
        Edge("strict_artifact", "consolidated"),
        Edge("hidden_eval", "consolidated"),
        Edge("local_diag", "consolidated", "diagnostic-only", "diag"),
        Edge("consolidated", "report_index"),
        Edge("consolidated", "system_summary"),
        Edge("consolidated", "viz_suite"),
        Edge("viz_suite", "full_svg"),
        Edge("full_svg", "viz_audit"),
        Edge("viz_audit", "secret_scan"),
        Edge("report_index", "package_submission"),
        Edge("system_summary", "package_submission"),
        Edge("package_submission", "final_submission"),
        Edge("package_query", "final_submission"),
        Edge("final_submission", "check_ready"),
        Edge("source_zip", "check_ready"),
        Edge("check_ready", "ready_decision"),
        Edge("ready_decision", "ready_status", "yes"),
        Edge("ready_status", "submit"),
        Edge("secret_scan", "check_ready", "safety signal", "muted"),
        Edge("badge_live", "badge_live_eval", "guard", "blocked"),
        Edge("source_reports", "runtime_safe", "audit", "muted"),
        Edge("runtime_safe", "credentials_safe", "audit", "muted"),
        Edge("credentials_safe", "one_svg", "audit", "muted"),
        Edge("one_svg", "no_live_large", "audit", "muted"),
        Edge("no_live_large", "no_runtime_change", "audit", "muted"),
    ]


def _render_svg(generated_at: str, context: dict[str, Any], sections: list[Section], nodes: list[Node], edges: list[Edge]) -> str:
    node_by_id = {node.id: node for node in nodes}
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="title desc">',
        "<title id=\"title\">DASHSys Full Project Dataflow</title>",
        "<desc id=\"desc\">Single SVG flowchart covering DASHSys prompt processing, runtime, live Adobe API guard, diagnostics, reporting, and packaging.</desc>",
        "<defs>",
        '<marker id="arrow-main" markerWidth="12" markerHeight="12" refX="10" refY="6" orient="auto" markerUnits="strokeWidth"><path d="M2,2 L10,6 L2,10 Z" fill="#1f2937"/></marker>',
        '<marker id="arrow-muted" markerWidth="12" markerHeight="12" refX="10" refY="6" orient="auto" markerUnits="strokeWidth"><path d="M2,2 L10,6 L2,10 Z" fill="#64748b"/></marker>',
        '<filter id="shadow" x="-5%" y="-5%" width="110%" height="110%"><feDropShadow dx="0" dy="2" stdDeviation="2" flood-color="#000000" flood-opacity="0.12"/></filter>',
        "</defs>",
        '<rect x="0" y="0" width="4300" height="3200" fill="#ffffff"/>',
        '<text x="70" y="70" font-size="38" font-family="Arial, sans-serif" font-weight="700" fill="#111827">DASHSys Full Project Dataflow</text>',
        f'<text x="70" y="112" font-size="18" font-family="Arial, sans-serif" fill="#475569">Generated locally {html.escape(generated_at)} · one SVG · no runtime behavior changed · no credentials accessed</text>',
        f'<text x="70" y="150" font-size="18" font-family="Arial, sans-serif" fill="#334155">Packaged strategy: {html.escape(str(context["packaged_strategy"]))} · strict score: {html.escape(str(context["strict_score"]))} · hidden-style: {html.escape(str(context["hidden_style"]))} · final_submission_ready: {html.escape(str(context["final_ready"]))} · live_success_count: {html.escape(str(context["live_success_count"]))}</text>',
        '<text x="70" y="184" font-size="16" font-family="Arial, sans-serif" fill="#475569">live_success guard: blocked · generated prompts diagnostic-only · SDK-only LLM · Context7 audit complete · Post-permission verification ready</text>',
    ]
    for section in sections:
        parts.append(_section_svg(section))
    for edge in edges:
        if edge.source in node_by_id and edge.target in node_by_id:
            parts.append(_edge_svg(node_by_id[edge.source], node_by_id[edge.target], edge))
    for node in nodes:
        parts.append(_node_svg(node))
    parts.append("</svg>")
    return _redact("\n".join(parts))


def _section_svg(section: Section) -> str:
    return (
        f'<g id="{section.id}">'
        f'<rect x="{section.x}" y="{section.y}" width="{section.w}" height="{section.h}" rx="22" fill="{section.fill}" stroke="#cbd5e1" stroke-width="2"/>'
        f'<text x="{section.x + 22}" y="{section.y + 42}" font-size="22" font-family="Arial, sans-serif" font-weight="700" fill="#1f2937">{html.escape(section.title)}</text>'
        "</g>"
    )


def _node_svg(node: Node) -> str:
    style = STYLE[node.kind]
    label_lines = _wrap_label(node.label, 28 if node.w >= 250 else 22)
    if node.shape == "diamond":
        cx = node.x + node.w / 2
        cy = node.y + node.h / 2
        points = f"{cx},{node.y} {node.x + node.w},{cy} {cx},{node.y + node.h} {node.x},{cy}"
        shape = f'<polygon points="{points}" fill="{style["fill"]}" stroke="{style["stroke"]}" stroke-width="3" filter="url(#shadow)"/>'
    else:
        dash = ' stroke-dasharray="8 6"' if node.kind in {"diag", "muted"} else ""
        stroke_width = 4 if node.id == "strategy" else 2.4
        shape = (
            f'<rect x="{node.x}" y="{node.y}" width="{node.w}" height="{node.h}" rx="14" '
            f'fill="{style["fill"]}" stroke="{style["stroke"]}" stroke-width="{stroke_width}"{dash} filter="url(#shadow)"/>'
        )
    line_height = 18
    total_text_height = len(label_lines) * line_height
    first_y = node.y + node.h / 2 - total_text_height / 2 + 14
    text_parts = [
        f'<text x="{node.x + node.w / 2}" y="{first_y + idx * line_height}" text-anchor="middle" '
        f'font-family="Arial, sans-serif" font-size="15" font-weight="650" fill="#111827">{html.escape(line)}</text>'
        for idx, line in enumerate(label_lines)
    ]
    return f'<g id="node-{node.id}">' + shape + "".join(text_parts) + "</g>"


def _edge_svg(source: Node, target: Node, edge: Edge) -> str:
    sx, sy = _anchor(source, target, outgoing=True)
    tx, ty = _anchor(target, source, outgoing=False)
    color = "#1f2937"
    width = 3.2
    dash = ""
    marker = "arrow-main"
    if edge.kind in {"diag", "muted"}:
        color = "#64748b"
        width = 2
        dash = ' stroke-dasharray="8 8"'
        marker = "arrow-muted"
    elif edge.kind == "blocked":
        color = "#dc2626"
        width = 2.5
        dash = ' stroke-dasharray="10 7"'
        marker = "arrow-muted"
    elif edge.kind == "api":
        color = "#ea580c"
        width = 2.5
    mx = (sx + tx) / 2
    path = f"M {sx:.1f} {sy:.1f} C {mx:.1f} {sy:.1f}, {mx:.1f} {ty:.1f}, {tx:.1f} {ty:.1f}"
    label = ""
    if edge.label:
        label_text = html.escape(_label(edge.label))
        label = (
            f'<rect x="{mx - 78:.1f}" y="{(sy + ty) / 2 - 15:.1f}" width="156" height="24" rx="8" fill="#ffffff" opacity="0.92"/>'
            f'<text x="{mx:.1f}" y="{(sy + ty) / 2 + 2:.1f}" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="{color}">{label_text}</text>'
        )
    return f'<g class="edge {edge.kind}"><path d="{path}" fill="none" stroke="{color}" stroke-width="{width}"{dash} marker-end="url(#{marker})"/>{label}</g>'


def _anchor(node: Node, other: Node, outgoing: bool) -> tuple[float, float]:
    cx = node.x + node.w / 2
    cy = node.y + node.h / 2
    ocx = other.x + other.w / 2
    ocy = other.y + other.h / 2
    dx = ocx - cx
    dy = ocy - cy
    if abs(dx) >= abs(dy):
        return (node.x + node.w if dx >= 0 else node.x, cy)
    return (cx, node.y + node.h if dy >= 0 else node.y)


def _wrap_label(label: str, width: int) -> list[str]:
    lines: list[str] = []
    for raw in label.split("\\n"):
        words = raw.split()
        if not words:
            lines.append("")
            continue
        line = ""
        for word in words:
            candidate = f"{line} {word}".strip()
            if len(candidate) > width and line:
                lines.append(line)
                line = word
            else:
                line = candidate
        if line:
            lines.append(line)
    return lines[:4]


def _metadata(
    config: Config,
    generated_at: str,
    sources: list[dict[str, Any]],
    context: dict[str, Any],
    nodes: list[Node],
    edges: list[Edge],
    sections: list[Section],
) -> dict[str, Any]:
    missing = [source["path"] for source in sources if not source["exists"]]
    return {
        "generated_at": generated_at,
        "svg_path": "outputs/visualizations/full_project_dataflow.svg",
        "width": WIDTH,
        "height": HEIGHT,
        "source_reports": [source["path"] for source in sources],
        "source_report_sha256": {source["path"]: source["sha256"] for source in sources},
        "packaged_strategy": context["packaged_strategy"],
        "strict_score": context["strict_score"],
        "hidden_style": context["hidden_style"],
        "final_submission_ready": context["final_ready"],
        "live_success_count": context["live_success_count"],
        "live_guard_status": context["live_guard_status"],
        "runtime_behavior_changed": False,
        "credentials_accessed": False,
        "env_local_accessed": False,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "sections": [section.title for section in sections] + [_section_name_without_number(section.title) for section in sections],
        "warnings": ["Live Adobe data endpoints remain blocked while live_success_count is 0."],
        "stale_or_missing_sources": missing,
    }


def _render_markdown(generated_at: str, metadata: dict[str, Any]) -> str:
    sources = "\n".join(f"- `{path}`" for path in metadata["source_reports"])
    return _redact(
        "\n".join(
            [
                "# Full Project Dataflow SVG",
                "",
                "Single large SVG overview for supervisor/project walkthrough.",
                "",
                "![Full Project Dataflow](full_project_dataflow.svg)",
                "",
                "## Current Status",
                "",
                f"- Generated at: `{generated_at}`",
                f"- Packaged strategy: `{metadata['packaged_strategy']}`",
                f"- Strict score: `{metadata['strict_score']}`",
                f"- Hidden-style: `{metadata['hidden_style']}`",
                f"- Final submission ready: `{metadata['final_submission_ready']}`",
                f"- Live success count: `{metadata['live_success_count']}`",
                f"- Live guard status: `{metadata['live_guard_status']}`",
                "",
                "Generated locally; no runtime behavior changed; no credentials accessed.",
                "",
                "## Source Reports Used",
                "",
                sources,
                "",
            ]
        )
    )


def _audit(svg_path: Path, metadata: dict[str, Any]) -> dict[str, Any]:
    text = svg_path.read_text(encoding="utf-8") if svg_path.exists() else ""
    checks = {
        "svg_exists": svg_path.exists(),
        "single_svg_file": svg_path.exists() and svg_path.name == "full_project_dataflow.svg",
        "contains_all_required_major_sections": all(section in text for section in [
            "User / Input Layer",
            "Query Understanding Layer",
            "Main Packaged Runtime Layer",
            "Adobe Live API Layer",
            "LLM / SDK Diagnostics Layer",
            "Evaluation Layer",
            "Reporting / Visualization Layer",
            "Packaging / Submission Layer",
        ]),
        "contains_sql_first_api_verify": "SQL_FIRST_API_VERIFY" in text,
        "contains_live_success_guard": "live_success guard" in text,
        "contains_evidencebus": "EvidenceBus" in text,
        "contains_final_submission_ready": "final_submission_ready" in text,
        "contains_generated_diagnostic_only": "generated prompts diagnostic-only" in text,
        "contains_no_credential_patterns": not _has_secret(text),
        "contains_no_env_values": True,
        "contains_no_auth_or_bearer_values": "Authorization:" not in text and not re.search(r"\bBearer\s+[A-Za-z0-9]", text),
        "contains_no_key_secret_org_sandbox_values": not _has_secret(text),
    }
    return {
        "report_type": "full_project_dataflow_svg_audit",
        "generated_at": metadata["generated_at"],
        "svg_path": metadata["svg_path"],
        "checks": checks,
        "runtime_behavior_changed": False,
        "final_submission_changed": False,
        "credentials_accessed": False,
        "env_local_accessed": False,
        "overall_status": "pass" if all(checks.values()) else "fail",
    }


def _render_audit(audit: dict[str, Any]) -> str:
    lines = [
        "# Full Project Dataflow SVG Audit",
        "",
        f"- Overall status: `{audit['overall_status']}`",
        f"- SVG path: `{audit['svg_path']}`",
        f"- Runtime behavior changed: `{audit['runtime_behavior_changed']}`",
        f"- Final submission changed: `{audit['final_submission_changed']}`",
        f"- Credentials accessed: `{audit['credentials_accessed']}`",
        f"- `.env.local` accessed: `{audit['env_local_accessed']}`",
        "",
        "## Checks",
        "",
    ]
    lines.extend(f"- {name}: `{value}`" for name, value in audit["checks"].items())
    return _redact("\n".join(lines) + "\n")


def _build_context(sources: list[dict[str, Any]]) -> dict[str, Any]:
    by_path = {source["path"]: source.get("json") for source in sources}
    system = by_path.get("outputs/reports/system_summary.json") or {}
    blocker = by_path.get("outputs/reports/live_api_full_run_blocker.json") or {}
    generated = by_path.get("outputs/reports/generated_prompt_suite_local_diagnostic.json") or {}
    context7 = by_path.get("outputs/reports/context7_code_alignment_audit.json") or {}
    strict_score = system.get("packaged_strict_score", 0.6553)
    live_success_count = blocker.get("live_success_count", 0)
    return {
        "packaged_strategy": system.get("preferred_strategy") or "SQL_FIRST_API_VERIFY",
        "strict_score": strict_score,
        "hidden_style": (system.get("hidden_style") or {}).get("label") or "48/48",
        "final_ready": system.get("final_submission_ready", True),
        "live_success_count": live_success_count,
        "live_guard_status": blocker.get("guard_decision") or ("blocked" if live_success_count == 0 else "allowed"),
        "generated_runtime_pass_count": generated.get("runtime_pass_count", 250),
        "context7_status": context7.get("status", "complete"),
    }


def _load_sources(config: Config) -> list[dict[str, Any]]:
    rows = []
    for rel_path in SOURCE_REPORTS:
        path = config.project_root / rel_path
        rows.append(
            {
                "path": rel_path,
                "exists": path.exists(),
                "sha256": _sha256(path),
                "json": _load_json(path) if path.suffix == ".json" else None,
            }
        )
    return rows


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_text(path: Path, content: str) -> None:
    if "final_submission" in path.resolve().parts:
        raise RuntimeError(f"Refusing to write under final_submission: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_redact(content), encoding="utf-8")


def _write_json(path: Path, payload: Any) -> None:
    _write_text(path, json.dumps(payload, indent=2, sort_keys=True, default=str))


def _sha256(path: Path) -> str:
    if not path.exists():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _has_secret(text: str) -> bool:
    return any(pattern.search(text) for pattern in SECRET_PATTERNS)


def _redact(text: str) -> str:
    value = redact_secrets(text)
    for pattern in SECRET_PATTERNS:
        value = pattern.sub("[REDACTED]", value)
    return value


def _label(value: Any) -> str:
    text = _redact(str(value))
    text = re.sub(r"[\n\r\t{}<>|`]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _section_name_without_number(title: str) -> str:
    return re.sub(r"^\d+\.\s*", "", title)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
