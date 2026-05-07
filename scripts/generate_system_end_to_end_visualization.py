#!/usr/bin/env python
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from visualization_report_helpers import VIS_DIR, mermaid_block, table, write_json, write_md  # noqa: E402


def main() -> int:
    stages = build_stages()
    overview = build_overview_graph()
    detailed = build_detailed_graph()
    payload = {"overview_mermaid": overview, "detailed_mermaid": detailed, "stages": stages}
    write_json(VIS_DIR / "system_end_to_end.json", payload)
    write_md(VIS_DIR / "system_end_to_end.md", build_markdown(overview, detailed, stages))
    print({"json": str(VIS_DIR / "system_end_to_end.json"), "markdown": str(VIS_DIR / "system_end_to_end.md")})
    return 0


def build_stages() -> list[dict[str, str]]:
    return [
        {
            "stage": "User prompt",
            "goal": "Capture original natural-language question unchanged.",
            "key_inputs": "User query",
            "key_outputs": "original_query in trajectory",
            "representative_files": "dashagent/executor.py",
            "representative_checkpoints": "trajectory root",
            "status": "promoted_default",
        },
        {
            "stage": "Prompt router",
            "goal": "Choose SQL-only, SQL-first/API-verify, or API-oriented path.",
            "key_inputs": "original query",
            "key_outputs": "route_type, requires_api, risk/API policy",
            "representative_files": "dashagent/prompt_router.py, dashagent/router.py",
            "representative_checkpoints": "checkpoint_00_prompt_router",
            "status": "promoted_default",
        },
        {
            "stage": "Query normalization and tokens",
            "goal": "Normalize text and extract quoted entities/tokens.",
            "key_inputs": "original query",
            "key_outputs": "normalized query, tokens, quoted entities",
            "representative_files": "dashagent/query_normalizer.py, dashagent/query_tokens.py",
            "representative_checkpoints": "checkpoint_02_query_normalization, checkpoint_03_query_tokens",
            "status": "promoted_default",
        },
        {
            "stage": "Query analysis",
            "goal": "Classify domain, answer shape, and route intent.",
            "key_inputs": "tokens, route policy, schema/API hints",
            "key_outputs": "domain_type, answer shape, route_type",
            "representative_files": "dashagent/query_analysis.py, dashagent/answer_intent.py",
            "representative_checkpoints": "checkpoint_query_analysis",
            "status": "promoted_default",
        },
        {
            "stage": "Metadata/context selection",
            "goal": "Select compact schema/API context for planning.",
            "key_inputs": "schema index, endpoint catalog, relevance scores",
            "key_outputs": "metadata.json, filled_system_prompt.txt",
            "representative_files": "dashagent/metadata_selector.py, dashagent/context_cards.py",
            "representative_checkpoints": "checkpoint_metadata_selection",
            "status": "promoted_default",
        },
        {
            "stage": "SQL planning",
            "goal": "Create read-only SQL when local data can ground facts.",
            "key_inputs": "metadata, SQL templates, query analysis",
            "key_outputs": "validated SQL step or no SQL step",
            "representative_files": "dashagent/sql_templates.py, dashagent/planner.py",
            "representative_checkpoints": "checkpoint_sql_ast_validation",
            "status": "promoted_default",
        },
        {
            "stage": "API planning",
            "goal": "Create endpoint-catalog-valid API calls when required.",
            "key_inputs": "endpoint catalog, API templates, grounded params",
            "key_outputs": "method/path/params or API_SKIP",
            "representative_files": "dashagent/api_templates.py, dashagent/endpoint_catalog.py",
            "representative_checkpoints": "checkpoint_api_validation",
            "status": "promoted_default",
        },
        {
            "stage": "Optimization and budget",
            "goal": "Dedupe plan steps and enforce call/token budgets.",
            "key_inputs": "candidate plan",
            "key_outputs": "one selected optimized plan",
            "representative_files": "dashagent/plan_optimizer.py, dashagent/plan_ensemble.py, dashagent/call_budget.py",
            "representative_checkpoints": "checkpoint_plan_optimizer, checkpoint_11_call_budget",
            "status": "promoted_default",
        },
        {
            "stage": "Execution",
            "goal": "Execute exactly one selected plan through SQL/API tools.",
            "key_inputs": "validated SQL/API steps",
            "key_outputs": "SQL rows, API result or dry-run label",
            "representative_files": "dashagent/executor.py, dashagent/db.py",
            "representative_checkpoints": "checkpoint_execution",
            "status": "promoted_default",
        },
        {
            "stage": "Evidence collection",
            "goal": "Record SQL, API, local evidence, and dry-run/live status.",
            "key_inputs": "tool outputs and local evidence",
            "key_outputs": "evidence objects for synthesis and audit",
            "representative_files": "dashagent/evidence_bus.py, dashagent/evidence_policy.py",
            "representative_checkpoints": "checkpoint_evidence_policy",
            "status": "promoted_default",
        },
        {
            "stage": "Answer synthesis",
            "goal": "Compose concise evidence-supported final answer.",
            "key_inputs": "evidence, answer templates, answer shape",
            "key_outputs": "final answer candidate",
            "representative_files": "dashagent/answer_synthesizer.py, dashagent/answer_templates.py",
            "representative_checkpoints": "checkpoint_answer_synthesis",
            "status": "promoted_default",
        },
        {
            "stage": "Answer verification/reranking",
            "goal": "Validate answer support and choose safer wording.",
            "key_inputs": "answer candidates and evidence",
            "key_outputs": "verified final answer",
            "representative_files": "dashagent/answer_verifier.py, dashagent/answer_reranker.py",
            "representative_checkpoints": "checkpoint_16_answer_verification",
            "status": "promoted_default",
        },
        {
            "stage": "Trajectory and reports",
            "goal": "Persist audit trail and metrics for evaluation/visualization.",
            "key_inputs": "checkpoints, steps, metrics",
            "key_outputs": "trajectory.json, reports, visualization summaries",
            "representative_files": "dashagent/trajectory.py, dashagent/span_exporter.py",
            "representative_checkpoints": "checkpoints list",
            "status": "promoted_default",
        },
        {
            "stage": "Shadow/canary branches",
            "goal": "Evaluate answer-shape v2, supportable rewrites, endpoint rules, AST, LLM, and local-index candidates without changing packaged output.",
            "key_inputs": "baseline trajectories and reports",
            "key_outputs": "isolated reports and candidate bundles",
            "representative_files": "scripts/run_*_eval.py, scripts/run_*_canary.py",
            "representative_checkpoints": "report-specific rows",
            "status": "shadow_only / diagnostic_only / default_off",
        },
    ]


def build_overview_graph() -> str:
    return """
flowchart LR
  A["User prompt"] --> B["Normalize + route"]
  B --> C["Select metadata/context"]
  C --> D["Plan SQL/API"]
  D --> E["Validate + optimize"]
  E --> F["Execute tools"]
  F --> G["Collect evidence"]
  G --> H["Synthesize answer"]
  H --> I["Verify + rerank"]
  I --> J["Final answer + trajectory"]
  E -. "shadow/canary only" .-> K["Candidate trials"]
  H -. "answer-only trials" .-> L["Rewrite search"]
"""


def build_detailed_graph() -> str:
    return """
flowchart TD
  Q["Raw query"] --> R["Prompt router"]
  R --> N["Normalization + tokens"]
  N --> A["Query analysis"]
  A --> M["Metadata selector"]
  M --> P["Planner"]
  P --> S["Route decision"]
  S -->|"SQL_ONLY"| SQL["SQL template + validator"]
  S -->|"SQL_FIRST_API_VERIFY"| SQL
  S -->|"API needed"| API["API template + catalog validator"]
  SQL --> BUD["Plan optimizer + call budget"]
  API --> BUD
  BUD --> SKIP["API skip safety check"]
  SKIP -->|"yes, default-off guard"| SQLONLY["SQL evidence only"]
  SKIP -->|"no / API score may matter"| EXEC["Execute selected plan"]
  SQLONLY --> EV["Evidence bus"]
  EXEC --> DRY["API mode decision"]
  DRY -->|"live credentials"| LIVE["Live API evidence"]
  DRY -->|"missing credentials"| DRYR["Dry-run label"]
  LIVE --> EV
  DRYR --> EV
  EV --> ANS["Answer templates + synthesizer"]
  ANS --> VER["Verifier + reranker"]
  VER --> FINAL["Final answer"]
  FINAL --> TRAJ["Trajectory + reports"]
  M -. "shadow only" .-> ES["Endpoint/schema rules"]
  P -. "shadow only" .-> AST["AST candidate canary"]
  ANS -. "shadow only" .-> RW["Supportable rewrites / LLM search"]
  TRAJ -. "diagnostic" .-> HIDDEN["Hidden-style + readiness checks"]
"""


def build_markdown(overview: str, detailed: str, stages: list[dict[str, str]]) -> str:
    rows = [
        [
            stage["stage"],
            stage["goal"],
            stage["key_inputs"],
            stage["key_outputs"],
            stage["representative_files"],
            stage["representative_checkpoints"],
            stage["status"],
        ]
        for stage in stages
    ]
    return "\n".join(
        [
            "# DASHSys End-to-End System Workflow",
            "",
            "This view shows the promoted packaged path and where default-off, shadow-only, and diagnostic-only branches split from it.",
            "",
            "## High-Level Workflow",
            "",
            mermaid_block(overview),
            "",
            "## Detailed Workflow",
            "",
            mermaid_block(detailed),
            "",
            "## Stage Table",
            "",
            table(["Stage", "Goal", "Inputs", "Outputs", "Files", "Checkpoints", "Status"], rows),
            "",
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())
