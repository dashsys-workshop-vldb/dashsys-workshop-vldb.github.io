#!/usr/bin/env python
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.trajectory import redact_secrets


SOURCE_REPORT_STEMS = [
    "report_index",
    "system_summary",
    "workflow_decision_map",
    "workflow_decision_audit",
    "live_api_full_run_blocker",
    "adobe_access_waiting_status",
    "context7_code_alignment_audit",
]

VISUALIZATION_STEMS = [
    "project_architecture_c4",
    "end_to_end_pipeline_mermaid",
    "live_adobe_api_status_mermaid",
    "report_generation_map",
]

SECRET_PATTERNS = [
    re.compile(r"Authorization:\s*Bearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE),
    re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
    re.compile(
        r"(OPENAI_API_KEY|ANTHROPIC_API_KEY|ADOBE_ACCESS_TOKEN|ADOBE_API_KEY|ADOBE_CLIENT_SECRET|CLIENT_SECRET)=\S+",
        re.IGNORECASE,
    ),
]


def main() -> int:
    payload = generate_project_mermaid_visualizations()
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def generate_project_mermaid_visualizations(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports_dir = config.outputs_dir / "reports"
    vis_dir = config.outputs_dir / "visualizations"
    reports_dir.mkdir(parents=True, exist_ok=True)
    vis_dir.mkdir(parents=True, exist_ok=True)

    generated_at = _utc_now()
    sources = _load_sources(reports_dir)
    module_inventory = _module_inventory(config.project_root)
    context = _context_from_sources(sources, module_inventory)

    diagrams = {
        "project_architecture_c4": _project_architecture_c4(context),
        "end_to_end_pipeline_mermaid": _end_to_end_pipeline(context),
        "live_adobe_api_status_mermaid": _live_adobe_api_status(context),
        "report_generation_map": _report_generation_map(context),
    }

    written_files: list[str] = []
    for stem, diagram in diagrams.items():
        mmd_path = vis_dir / f"{stem}.mmd"
        md_path = vis_dir / f"{stem}.md"
        _write_text(mmd_path, diagram)
        _write_text(md_path, _markdown_for_diagram(stem, diagram, context, generated_at))
        written_files.extend([_rel(config, mmd_path), _rel(config, md_path)])

    audit = _build_sync_audit(config, generated_at, sources, context, written_files)
    audit_json = reports_dir / "visualization_sync_audit.json"
    audit_md = reports_dir / "visualization_sync_audit.md"
    _write_json(audit_json, audit)
    _write_text(audit_md, _render_sync_audit(audit))
    written_files.extend([_rel(config, audit_json), _rel(config, audit_md)])

    return {
        "written_files": written_files,
        "audit_path": str(audit_json),
        "visualization_root": str(vis_dir),
    }


def _load_sources(reports_dir: Path) -> dict[str, Any]:
    sources: dict[str, Any] = {}
    for stem in SOURCE_REPORT_STEMS:
        json_path = reports_dir / f"{stem}.json"
        md_path = reports_dir / f"{stem}.md"
        sources[stem] = {
            "json_path": json_path,
            "md_path": md_path,
            "json": _load_json(json_path),
            "json_exists": json_path.exists(),
            "md_exists": md_path.exists(),
            "json_sha256": _sha256(json_path),
            "md_sha256": _sha256(md_path),
        }
    return sources


def _context_from_sources(sources: dict[str, Any], module_inventory: dict[str, list[str]]) -> dict[str, Any]:
    system = _source_json(sources, "system_summary")
    blocker = _source_json(sources, "live_api_full_run_blocker")
    waiting = _source_json(sources, "adobe_access_waiting_status")
    context7 = _source_json(sources, "context7_code_alignment_audit")
    decision_map = _source_json(sources, "workflow_decision_map")
    audit = _source_json(sources, "workflow_decision_audit")
    live_success_count = _first_number(blocker.get("live_success_count"), waiting.get("live_success_count"), 0)
    final_ready = system.get("final_submission_ready")
    if final_ready is None:
        final_ready = "unavailable"
    return {
        "packaged_strategy": system.get("preferred_strategy") or "SQL_FIRST_API_VERIFY",
        "packaged_strict_score": system.get("packaged_strict_score", "unavailable"),
        "hidden_style": (system.get("hidden_style") or {}).get("label", "unavailable"),
        "final_submission_ready": final_ready,
        "live_success_count": live_success_count,
        "live_guard_decision": blocker.get("guard_decision", "blocked" if live_success_count == 0 else "allowed"),
        "live_failure_counts": blocker.get("failure_counts", {}),
        "waiting_live_evidence_count": waiting.get("usable_live_api_evidence_count", "unavailable"),
        "context7_status": context7.get("status", "unavailable"),
        "workflow_stage_count": decision_map.get("stage_count", "unavailable"),
        "workflow_audited_queries": audit.get("total_queries", "unavailable"),
        "dashagent_modules": module_inventory["dashagent_modules"],
        "script_modules": module_inventory["script_modules"],
    }


def _project_architecture_c4(context: dict[str, Any]) -> str:
    strategy = _label(context["packaged_strategy"])
    return f"""
C4Context
title DASHSys Project Architecture - {strategy}
Person(user, "User", "Submits natural-language DASHSys questions")
System_Boundary(dashsys, "DASHSys local project") {{
  Container(cli, "CLI scripts", "Python", "Run evals, package outputs, and regenerate reports/visualizations")
  Container(core, "dashagent core", "Python modules", "Query analysis, routing, planning, validators, EvidenceBus, answer synthesis")
  ContainerDb(db, "Local DuckDB/parquet", "Read-only data", "Local DBSnapshot evidence")
  Container(reports, "Reports + Mermaid visualizations", "Markdown/JSON/Mermaid", "Versionable generated diagnostics")
  Container(finals, "Final submission", "metadata/prompt/trajectory", "Packaged DASHSys deliverables")
}}
System_Ext(adobe, "Adobe API", "GET-only live evidence when credentials and live_success guard allow")
System_Ext(llm, "SDK LLM", "SDK-only diagnostics and shadow helpers")
Rel(user, cli, "runs safe commands")
Rel(cli, core, "invokes {strategy}")
Rel(core, db, "execute_sql read-only")
Rel(core, adobe, "call_api GET via API guard")
Rel(core, llm, "SDK-only shadow diagnostics")
Rel(core, reports, "writes trajectories and reports")
Rel(reports, finals, "documents packaging readiness")
Rel(core, finals, "writes final submission artifacts")
UpdateRelStyle(core, adobe, $textColor="#6b7280", $lineColor="#9ca3af", $offsetY="-10")
"""


def _end_to_end_pipeline(context: dict[str, Any]) -> str:
    strategy = _label(context["packaged_strategy"])
    return f"""
flowchart TD
  user["User Prompt"] --> analysis["Query Analysis"]
  analysis --> router["Deterministic Router"]
  router --> strategy["{strategy}<br/>packaged default"]
  strategy --> plan["SQL/API Plan"]
  plan --> sqlv["SQL Validation<br/>read-only guard"]
  plan --> apig["API Guard<br/>GET-only catalog"]
  sqlv --> sql["execute_sql<br/>DuckDB/parquet"]
  apig --> api["call_api<br/>Adobe API or dry-run"]
  sql --> bus["EvidenceBus"]
  api --> bus
  bus --> slots["Answer Slots"]
  slots --> synth["Answer Synthesis"]
  synth --> verifier["Verifier"]
  verifier --> eval["Eval"]
  eval --> package["Packaging"]
  guard["live_success guard"] -. blocks large live runs when 0 .-> apig
  reports["Reports + Mermaid sync audit"] -. generated locally .-> eval
  classDef main fill:#eaf3ff,stroke:#2563eb,color:#111827
  classDef evidence fill:#ecfdf5,stroke:#16a34a,color:#111827
  classDef guard fill:#f5f5f5,stroke:#6b7280,stroke-dasharray: 5 5,color:#111827
  class user,analysis,router,strategy,plan,synth,verifier,eval,package main
  class sqlv,sql,apig,api,bus,slots evidence
  class guard,reports guard
"""


def _live_adobe_api_status(context: dict[str, Any]) -> str:
    count = _label(context["live_success_count"])
    decision = _label(context["live_guard_decision"])
    evidence = _label(context["waiting_live_evidence_count"])
    return f"""
flowchart TD
  env[".env.local readiness<br/>presence only"] --> token["Token acquisition<br/>client_credentials or access_token"]
  token --> smoke["Safe GET smoke"]
  smoke --> outcomes["Endpoint outcomes<br/>auth / sandbox / path / service"]
  outcomes --> success{{"live_success_count > 0?"}}
  success -->|yes| allowed["live_success guard<br/>full live eval allowed"]
  success -->|no| blocked["live_success guard<br/>full live eval blocked"]
  blocked --> follow["Follow-up commands<br/>all-safe-get + endpoint filters"]
  allowed --> trial["Live evidence pipeline trial"]
  trial --> prompts["Live generated prompts<br/>diagnostic-only"]
  meta["Current status<br/>live_success_count: {count}<br/>guard: {decision}<br/>usable evidence: {evidence}"] -.-> success
  classDef ready fill:#ecfdf5,stroke:#16a34a,color:#111827
  classDef blocked fill:#fff7ed,stroke:#ea580c,color:#111827
  classDef neutral fill:#f8fafc,stroke:#64748b,color:#111827
  class env,token,smoke,outcomes,trial,prompts neutral
  class allowed ready
  class blocked,follow blocked
"""


def _report_generation_map(context: dict[str, Any]) -> str:
    return """
flowchart LR
  dev["scripts/run_dev_eval.py"] --> strict["outputs/eval_results_strict.json"]
  hidden["scripts/run_hidden_style_eval.py"] --> hidden_report["outputs/hidden_style_eval.json"]
  workflow["scripts/run_workflow_decision_audit.py"] --> decision_map["workflow_decision_map.md/json"]
  workflow --> decision_audit["workflow_decision_audit.md/json"]
  live_smoke["scripts/run_live_api_readiness_smoke.py"] --> smoke_report["live_api_readiness_smoke.md/json"]
  live_guard["dashagent/live_api_guard.py"] --> blocker["live_api_full_run_blocker.md/json"]
  waiting["scripts/run_post_permission_live_api_verification.py"] --> waiting_report["adobe_access_waiting_status.md/json"]
  context7["scripts/run_context7_code_alignment_audit.py"] --> context7_report["context7_code_alignment_audit.md/json"]
  mermaid["scripts/generate_project_mermaid_visualizations.py"] --> c4["project_architecture_c4.md/mmd"]
  mermaid --> pipeline["end_to_end_pipeline_mermaid.md/mmd"]
  mermaid --> live_viz["live_adobe_api_status_mermaid.md/mmd"]
  mermaid --> report_map["report_generation_map.md/mmd"]
  mermaid --> sync["visualization_sync_audit.md/json"]
  consolidated["scripts/generate_consolidated_reports.py"] --> index["report_index.md/json"]
  consolidated --> system["system_summary.md/json"]
  consolidated --> viz_summary["visualization_summary.md/json"]
  c4 --> index
  pipeline --> index
  live_viz --> index
  report_map --> index
  sync --> index
  guard_label["live_success guard"] -. protects .-> dev
  strategy["SQL_FIRST_API_VERIFY"] -. packaged default .-> strict
  classDef script fill:#eaf3ff,stroke:#2563eb,color:#111827
  classDef report fill:#f0fdf4,stroke:#16a34a,color:#111827
  classDef guard fill:#f5f5f5,stroke:#6b7280,stroke-dasharray: 5 5,color:#111827
  class dev,hidden,workflow,live_smoke,waiting,context7,mermaid,consolidated script
  class strict,hidden_report,decision_map,decision_audit,smoke_report,blocker,waiting_report,context7_report,c4,pipeline,live_viz,report_map,sync,index,system,viz_summary report
  class guard_label,strategy guard
"""


def _markdown_for_diagram(stem: str, diagram: str, context: dict[str, Any], generated_at: str) -> str:
    titles = {
        "project_architecture_c4": "Project Architecture C4",
        "end_to_end_pipeline_mermaid": "End-To-End Pipeline Mermaid",
        "live_adobe_api_status_mermaid": "Live Adobe API Status Mermaid",
        "report_generation_map": "Report Generation Map",
    }
    return "\n".join(
        [
            f"# {titles[stem]}",
            "",
            f"Generated: {generated_at}",
            "",
            "This generated Mermaid diagram is synchronized from current local reports and code/module names only. It does not change runtime behavior.",
            "",
            f"- Packaged strategy: `{_label(context['packaged_strategy'])}`",
            f"- live_success guard: `{_label(context['live_guard_decision'])}`",
            "",
            "```mermaid",
            diagram.strip(),
            "```",
            "",
        ]
    )


def _build_sync_audit(
    config: Config,
    generated_at: str,
    sources: dict[str, Any],
    context: dict[str, Any],
    written_files: list[str],
) -> dict[str, Any]:
    source_reports = []
    missing = []
    for stem, source in sources.items():
        for kind in ("json", "md"):
            exists_key = f"{kind}_exists"
            sha_key = f"{kind}_sha256"
            path = source[f"{kind}_path"]
            rel_path = _rel(config, path)
            if not source[exists_key]:
                missing.append(rel_path)
            source_reports.append(
                {
                    "name": stem,
                    "kind": kind,
                    "path": rel_path,
                    "exists": bool(source[exists_key]),
                    "sha256": source[sha_key],
                }
            )
    return {
        "report_type": "visualization_sync_audit",
        "generated_at": generated_at,
        "diagram_files": written_files[: len(VISUALIZATION_STEMS) * 2],
        "source_reports_used": source_reports,
        "missing_source_reports": missing,
        "stale_source_reports": [],
        "live_success_count": context["live_success_count"],
        "packaged_strategy": context["packaged_strategy"],
        "final_submission_ready": context["final_submission_ready"],
        "module_inventory": context,
        "runtime_behavior_changed": False,
        "credentials_accessed": False,
        "local_env_accessed": False,
    }


def _render_sync_audit(audit: dict[str, Any]) -> str:
    lines = [
        "# Visualization Sync Audit",
        "",
        f"- Generated at: `{audit['generated_at']}`",
        f"- Packaged strategy: `{audit['packaged_strategy']}`",
        f"- Final submission ready: `{audit['final_submission_ready']}`",
        f"- live_success_count: `{audit['live_success_count']}`",
        f"- Runtime behavior changed: `{audit['runtime_behavior_changed']}`",
        f"- Credentials accessed: `{audit['credentials_accessed']}`",
        f"- `.env.local` accessed: `{audit['local_env_accessed']}`",
        "",
        "## Diagram Files",
        "",
        *[f"- `{path}`" for path in audit["diagram_files"]],
        "",
        "## Source Reports",
        "",
    ]
    for source in audit["source_reports_used"]:
        lines.append(f"- `{source['path']}` exists=`{source['exists']}` sha256=`{source['sha256']}`")
    if audit["missing_source_reports"]:
        lines.extend(["", "## Missing Sources", ""])
        lines.extend(f"- `{path}`" for path in audit["missing_source_reports"])
    return "\n".join(lines) + "\n"


def _module_inventory(project_root: Path) -> dict[str, list[str]]:
    dashagent_dir = project_root / "dashagent"
    scripts_dir = project_root / "scripts"
    dashagent_modules = sorted(path.stem for path in dashagent_dir.glob("*.py") if path.name != "__init__.py") if dashagent_dir.exists() else []
    script_modules = sorted(path.name for path in scripts_dir.glob("*.py")) if scripts_dir.exists() else []
    return {
        "dashagent_modules": dashagent_modules[:80],
        "script_modules": script_modules[:120],
    }


def _source_json(sources: dict[str, Any], stem: str) -> dict[str, Any]:
    value = sources.get(stem, {}).get("json", {})
    return value if isinstance(value, dict) else {}


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_redact(json.dumps(payload, indent=2, sort_keys=True, default=str)), encoding="utf-8")


def _write_text(path: Path, content: str) -> None:
    if "final_submission" in path.resolve().parts:
        raise RuntimeError(f"Refusing to write under final_submission: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_redact(content), encoding="utf-8")


def _sha256(path: Path) -> str:
    if not path.exists():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _redact(content: str) -> str:
    value = redact_secrets(content)
    for pattern in SECRET_PATTERNS:
        value = pattern.sub("[REDACTED]", value)
    return value


def _label(value: Any) -> str:
    text = str(value)
    text = _redact(text)
    text = re.sub(r"[\n\r\t{}<>|`]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text.replace('"', "'")


def _first_number(*values: Any) -> int | float | Any:
    for value in values:
        if isinstance(value, (int, float)):
            return value
    return values[-1] if values else "unavailable"


def _rel(config: Config, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(config.project_root.resolve()))
    except ValueError:
        return str(path)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
