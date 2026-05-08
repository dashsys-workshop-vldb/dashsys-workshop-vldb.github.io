#!/usr/bin/env python
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from supervisor_visualization_common import build_primary_context, checkpoint_timeline  # noqa: E402
from visualization_report_helpers import (  # noqa: E402
    VIS_DIR,
    checkpoint_output,
    md_escape,
    mermaid_label,
    mermaid_block,
    visual_summary,
    write_json,
    write_md,
)


def main() -> int:
    context = build_primary_context()
    artifacts = context["sql_artifacts"]
    payload = {
        "page": "sql_prompt_storyboard_primary",
        "query_id": context["query_id"],
        "raw_prompt": context["raw_prompt"],
        "why_chosen": context["why_chosen"],
        "strategy": context["strategy"],
        "route_type": context["route_type"],
        "metrics": {
            "strict_score": context["strict_score"],
            "correctness_score": context["correctness_score"],
            "answer_score": context["answer_score"],
            "sql_score": context["sql_score"],
            "api_score": context["api_score"],
            "tool_calls": context["tool_calls"],
            "tokens": context["tokens"],
            "runtime": context["runtime"],
        },
        "sql_artifacts": artifacts,
        "final_answer": context["final_answer"],
        "api_status": context["api_status"],
        "storyboard_steps": context["steps"],
        "checkpoint_timeline": checkpoint_timeline(context),
        "flowchart": flowchart(context),
        "source_trajectory": context["trajectory_path"],
    }
    write_json(VIS_DIR / "sql_prompt_storyboard_primary.json", payload)
    write_md(VIS_DIR / "sql_prompt_storyboard_primary.md", build_markdown(payload))
    print({"json": str(VIS_DIR / "sql_prompt_storyboard_primary.json"), "markdown": str(VIS_DIR / "sql_prompt_storyboard_primary.md")})
    return 0


def flowchart(context: dict[str, Any]) -> str:
    trajectory = context["trajectory"]
    artifacts = context["sql_artifacts"]
    raw_prompt = mermaid_label(context["raw_prompt"], 70)
    router = mermaid_label(visual_summary(checkpoint_output(trajectory, "checkpoint_00_prompt_router"), 90), 90)
    gate = mermaid_label(visual_summary(checkpoint_output(trajectory, "checkpoint_simple_prompt_gate"), 90), 90)
    normalized = checkpoint_output(trajectory, "checkpoint_02_query_normalization") or {}
    normalized_query = mermaid_label(normalized.get("normalized_query", "unavailable"), 70)
    matching_text = mermaid_label(normalized.get("matching_text", "unavailable"), 70)
    tokens = mermaid_label(visual_summary(checkpoint_output(trajectory, "checkpoint_03_query_tokens"), 90), 90)
    analysis = checkpoint_output(trajectory, "checkpoint_05_query_analysis") or {}
    route_type = mermaid_label(analysis.get("route_type", context["route_type"]), 36)
    answer_family = mermaid_label(analysis.get("answer_family", "unavailable"), 46)
    lookup = mermaid_label(visual_summary(checkpoint_output(trajectory, "checkpoint_06_lookup_path"), 90), 90)
    context_card = mermaid_label(visual_summary(checkpoint_output(trajectory, "checkpoint_07_context_card"), 100), 100)
    plan = checkpoint_output(trajectory, "checkpoint_08_candidate_plans") or {}
    selected_plan = mermaid_label(plan.get("selected_plan", "unavailable"), 50)
    plan_input = mermaid_label(visual_summary(checkpoint_output(trajectory, "checkpoint_08_candidate_plans"), 80), 80)
    sql_summary = mermaid_label("COUNT DISTINCT BLUEPRINTID FROM dim_blueprint", 70)
    generated_sql = mermaid_label(artifacts.get("generated_sql", "unavailable"), 160)
    validation = mermaid_label(visual_summary(artifacts.get("sql_validation"), 90), 90)
    ast_validation = mermaid_label(visual_summary(artifacts.get("ast_validation"), 90), 90)
    execution = mermaid_label(
        f"SQL calls={artifacts.get('sql_calls_executed', 'unavailable')}; API calls={artifacts.get('api_calls_executed', 'unavailable')}",
        80,
    )
    result_facts = "; ".join(str(item) for item in (artifacts.get("sql_result_facts") or ["unavailable"]))
    sql_result = mermaid_label(result_facts, 70)
    api_status = mermaid_label(context["api_status"], 80)
    evidence = mermaid_label(visual_summary(artifacts.get("evidence"), 90), 90)
    slots = mermaid_label(visual_summary(checkpoint_output(trajectory, "checkpoint_15_answer_slots"), 90), 90)
    verifier = mermaid_label(visual_summary(checkpoint_output(trajectory, "checkpoint_16_answer_verification"), 90), 90)
    answer = mermaid_label(context["final_answer"], 160)
    metrics = mermaid_label(
        f"strategy={context['strategy']}; tools={context['tool_calls']}; tokens={context['tokens']}; runtime={context['runtime']}",
        100,
    )
    return f"""
flowchart TD
  classDef prompt fill:#e8f3ff,stroke:#2f6fad,stroke-width:1px,color:#102a43
  classDef interpret fill:#eef8ef,stroke:#3b873e,stroke-width:1px,color:#183b1b
  classDef plan fill:#fff7df,stroke:#b7791f,stroke-width:1px,color:#3d2a00
  classDef sql fill:#eafff7,stroke:#00856f,stroke-width:2px,color:#063b33
  classDef api fill:#f7f2ff,stroke:#805ad5,stroke-width:1px,color:#2d1b69,stroke-dasharray: 5 3
  classDef evidence fill:#f0fff4,stroke:#2f855a,stroke-width:1px,color:#1c4532
  classDef answer fill:#fff0f6,stroke:#b83280,stroke-width:2px,color:#521b41
  classDef output fill:#f7fafc,stroke:#4a5568,stroke-width:1px,color:#1a202c

  subgraph P["Input / Prompt Understanding"]
    P0["Raw user prompt<br/>{raw_prompt}"]:::prompt
    P1["Prompt router interpretation<br/>{router}"]:::prompt
    P2["Simple-prompt gate decision<br/>{gate}"]:::prompt
    P3["Query normalization<br/>normalized: {normalized_query}<br/>matching text: {matching_text}"]:::prompt
    P4["Token/entity extraction<br/>{tokens}"]:::prompt
  end

  subgraph I["Query Interpretation"]
    I0["Query analysis<br/>route type: {route_type}<br/>answer family: {answer_family}"]:::interpret
    I1["Lookup path / route intent<br/>{lookup}"]:::interpret
  end

  subgraph C["Context + Planning"]
    C0["Context selection / metadata card<br/>{context_card}"]:::plan
    C1["SQL planning input<br/>{plan_input}"]:::plan
    C2["Selected plan / strategy<br/>{selected_plan}<br/>{context['strategy']}"]:::plan
  end

  subgraph S["SQL Derivation"]
    S0["Prompt becomes SQL<br/>{sql_summary}"]:::sql
    S1["Generated SQL artifact<br/>{generated_sql}"]:::sql
    S2["SQL validation<br/>{validation}"]:::sql
    S3["SQLGlot AST validation<br/>{ast_validation}"]:::sql
    S4["SQL is the answer source<br/>API branch is dry-run verification only"]:::sql
  end

  subgraph X["Execution + Evidence"]
    X0["Tool execution<br/>{execution}"]:::output
    X1["SQL execution result<br/>{sql_result}"]:::sql
    X2["Dry-run API verification branch<br/>{api_status}"]:::api
    X3["Evidence extraction / evidence bus<br/>{evidence}"]:::evidence
  end

  subgraph A["Final Answer + Output"]
    A0["Answer slots / answer intent<br/>{slots}"]:::answer
    A1["Answer synthesis<br/>SQL count + dry-run verification note"]:::answer
    A2["Answer verification / reranking<br/>{verifier}"]:::answer
    A3["Final answer<br/>{answer}"]:::answer
    A4["Trajectory / checkpoint output<br/>{metrics}"]:::output
  end

  P0 -->|"raw text captured"| P1
  P1 -->|"route policy applied"| P2
  P2 -->|"data pipeline selected"| P3
  P3 -->|"matching text derived"| P4
  P4 -->|"schema/count signals"| I0
  I0 -->|"route + family"| I1
  I1 -->|"schema path selected"| C0
  C0 -->|"compact metadata"| C1
  C1 -->|"planner chooses plan"| C2
  C2 -->|"SQL-first planning"| S0
  S0 -->|"SQL template filled"| S1
  S1 -->|"safety validation"| S2
  S2 -->|"AST extraction"| S3
  S3 -->|"safe to execute"| X0
  S4 -.->|"interpretation guard"| X1
  X0 -->|"DuckDB read-only query"| X1
  X0 -.->|"catalog-valid API verification"| X2
  X1 -->|"count evidence"| X3
  X2 -.->|"dry-run status"| X3
  X3 -->|"structured evidence"| A0
  A0 -->|"count intent"| A1
  A1 -->|"grounded claim check"| A2
  A2 -->|"verifier passed"| A3
  A3 -->|"logged outputs"| A4
"""


def build_markdown(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# SQL-Backed Primary Prompt Storyboard",
            "",
            f"`{md_escape(payload['query_id'])}` was chosen because it is SQL-backed in the packaged path: the prompt becomes validated SQL, SQL returns the answer count, and API verification is dry-run/unavailable.",
            "",
            "## One Giant End-to-End Flowchart",
            "",
            mermaid_block(payload["flowchart"]),
            "",
            "**Takeaway:** SQL is the answer source (`blueprint_count = 74`). The API branch is shown because the packaged trace attempts verification, but it is dry-run/unavailable and does not provide the answer value.",
            "",
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())
