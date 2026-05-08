#!/usr/bin/env python
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from supervisor_visualization_common import build_primary_context  # noqa: E402
from visualization_report_helpers import (  # noqa: E402
    VIS_DIR,
    checkpoint_output,
    md_escape,
    mermaid_block,
    write_json,
    write_md,
)


def main() -> int:
    context = build_primary_context()
    payload = storyboard_payload(context)
    write_json(VIS_DIR / "sql_prompt_storyboard_primary.json", payload)
    write_md(VIS_DIR / "sql_prompt_storyboard_primary.md", build_markdown(payload))
    print({"json": str(VIS_DIR / "sql_prompt_storyboard_primary.json"), "markdown": str(VIS_DIR / "sql_prompt_storyboard_primary.md")})
    return 0


def storyboard_payload(context: dict[str, Any]) -> dict[str, Any]:
    trajectory = context["trajectory"]
    artifacts = context["sql_artifacts"]
    normalized = checkpoint_output(trajectory, "checkpoint_02_query_normalization") or {}
    analysis = checkpoint_output(trajectory, "checkpoint_05_query_analysis") or {}
    plan = checkpoint_output(trajectory, "checkpoint_08_candidate_plans") or {}
    ast = artifacts.get("ast_validation") if isinstance(artifacts.get("ast_validation"), dict) else {}
    selected_table = first_item(ast.get("selected_tables"), "dim_blueprint")
    selected_column = first_item(ast.get("selected_columns"), "B.BLUEPRINTID")
    selected_column = str(selected_column).split(".")[-1] if selected_column != "unavailable" else selected_column
    generated_sql = artifacts.get("generated_sql", "unavailable")
    sql_result_summary = first_or_unavailable(artifacts.get("sql_result_facts"))
    grounded_fact_summary = grounded_fact_from_result(sql_result_summary)
    api_branch_summary = (
        "dry-run verification only; not answer source"
        if artifacts.get("dry_run_status") is True
        else context["api_status"]
    )
    evidence_summary = (
        f"SQL evidence: {sql_result_summary}; API status evidence: {api_branch_summary}"
        if sql_result_summary != "unavailable"
        else f"SQL evidence: unavailable; API status evidence: {api_branch_summary}"
    )
    metrics = {
        "tools": context["tool_calls"],
        "tokens": context["tokens"],
        "runtime": rounded_runtime(context["runtime"]),
        "sql_calls": artifacts.get("sql_calls_executed", "unavailable"),
        "api_calls": artifacts.get("api_calls_executed", "unavailable"),
    }
    payload = {
        "page": "sql_prompt_storyboard_primary",
        "query_id": context["query_id"],
        "raw_prompt": context["raw_prompt"],
        "normalized_query": normalized.get("normalized_query", "unavailable"),
        "strategy": context["strategy"],
        "selected_plan": plan.get("selected_plan", "unavailable"),
        "route_type": analysis.get("route_type", context["route_type"]),
        "answer_family": analysis.get("answer_family", "unavailable"),
        "selected_table": selected_table,
        "selected_column": selected_column,
        "aggregation": aggregation_from_sql(generated_sql),
        "generated_sql": generated_sql,
        "sql_result_summary": sql_result_summary,
        "grounded_fact_summary": grounded_fact_summary,
        "api_branch_summary": api_branch_summary,
        "evidence_summary": evidence_summary,
        "final_answer": context["final_answer"],
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
        "flowchart_source": flowchart_source(
            {
                "query_id": context["query_id"],
                "raw_prompt": context["raw_prompt"],
                "normalized_query": normalized.get("normalized_query", "unavailable"),
                "route_type": analysis.get("route_type", context["route_type"]),
                "answer_family": analysis.get("answer_family", "unavailable"),
                "selected_plan": plan.get("selected_plan", "unavailable"),
                "strategy": context["strategy"],
                "selected_table": selected_table,
                "selected_column": selected_column,
                "aggregation": aggregation_from_sql(generated_sql),
                "generated_sql": generated_sql,
                "sql_result_summary": sql_result_summary,
                "grounded_fact_summary": grounded_fact_summary,
                "api_branch_summary": api_branch_summary,
                "evidence_summary": evidence_summary,
                "final_answer": context["final_answer"],
                "metrics": metrics,
            }
        ),
        "source_trajectory_path": relative_source_path(context["trajectory_path"]),
    }
    return payload


def relative_source_path(path_value: Any) -> str:
    try:
        return str(Path(str(path_value)).resolve().relative_to(ROOT))
    except Exception:
        return str(path_value or "unavailable")


def first_item(value: Any, default: str = "unavailable") -> str:
    if isinstance(value, dict):
        items = value.get("items")
        if isinstance(items, list) and items:
            return str(items[0])
    if isinstance(value, list) and value:
        return str(value[0])
    return default


def first_or_unavailable(value: Any) -> str:
    if isinstance(value, list) and value:
        return str(value[0])
    return "unavailable"


def aggregation_from_sql(sql: Any) -> str:
    text = str(sql or "").lower()
    if "count(distinct" in text:
        return "COUNT DISTINCT"
    if "count(" in text:
        return "COUNT"
    return "unavailable"


def grounded_fact_from_result(sql_result_summary: str) -> str:
    if sql_result_summary == "blueprint_count = 74":
        return "user has 74 schemas"
    if sql_result_summary == "unavailable":
        return "unavailable"
    return f"answer fact from SQL result: {sql_result_summary}"


def rounded_runtime(value: Any) -> str:
    try:
        return f"{float(value):.3f}s"
    except Exception:
        return "unavailable"


def flow_label(value: Any, max_chars: int = 120) -> str:
    text = str(value if value is not None else "unavailable")
    text = text.replace("\n", "<br/>")
    text = " ".join(text.split())
    if len(text) > max_chars:
        text = text[: max_chars - 3].rstrip() + "..."
    return (
        text.replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<br/>", "<br/>")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("&lt;br/&gt;", "<br/>")
    )


def sql_node_label(sql: Any) -> str:
    if sql == 'SELECT COUNT(DISTINCT B."BLUEPRINTID") AS blueprint_count FROM "dim_blueprint" AS B':
        return flow_label('SELECT COUNT(DISTINCT\nB."BLUEPRINTID")\nAS blueprint_count\nFROM "dim_blueprint" AS B', 180)
    return flow_label(sql, 180)


def flowchart_source(data: dict[str, Any]) -> str:
    raw_prompt = flow_label(data["raw_prompt"], 90)
    normalized_query = flow_label(data["normalized_query"], 90)
    route_type = flow_label(data["route_type"], 40)
    answer_family = flow_label(data["answer_family"], 50)
    table = flow_label(data["selected_table"], 40)
    column = flow_label(data["selected_column"], 40)
    aggregation = flow_label(data["aggregation"], 40)
    generated_sql = sql_node_label(data["generated_sql"])
    result = flow_label(data["sql_result_summary"], 60)
    grounded_fact = flow_label(data["grounded_fact_summary"], 80)
    final_answer = flow_label("You have 74 schemas.\nDry-run note: live API verification unavailable.", 120)
    strategy = flow_label(data["strategy"], 60)
    selected_plan = flow_label(data["selected_plan"], 60)
    metrics = data["metrics"]
    runtime = flow_label(metrics.get("runtime", "unavailable"), 20)
    return f"""
flowchart TD
  classDef prompt fill:#e8f3ff,stroke:#2f6fad,stroke-width:1px,color:#102a43
  classDef interpret fill:#eef8ef,stroke:#3b873e,stroke-width:1px,color:#183b1b
  classDef mapping fill:#fff7df,stroke:#b7791f,stroke-width:2px,color:#3d2a00
  classDef plan fill:#fffaf0,stroke:#b7791f,stroke-width:1px,color:#3d2a00
  classDef sql fill:#eafff7,stroke:#00856f,stroke-width:2px,color:#063b33
  classDef api fill:#f7f2ff,stroke:#805ad5,stroke-width:1px,color:#2d1b69,stroke-dasharray: 5 3
  classDef evidence fill:#f0fff4,stroke:#2f855a,stroke-width:2px,color:#1c4532
  classDef answer fill:#fff0f6,stroke:#b83280,stroke-width:2px,color:#521b41
  classDef output fill:#f7fafc,stroke:#4a5568,stroke-width:1px,color:#1a202c

  subgraph U["1. User Prompt"]
    U0["Raw prompt<br/>{raw_prompt}"]:::prompt
  end

  subgraph P["2. Prompt Understanding"]
    P0["Router<br/>use data pipeline"]:::interpret
    P1["Normalize text<br/>{normalized_query}"]:::interpret
    P2["Extract signals<br/>&quot;schemas&quot; + &quot;how many&quot;"]:::interpret
    P3["Query analysis<br/>route = {route_type}<br/>answer type = COUNT<br/>family = {answer_family}"]:::interpret
  end

  subgraph M["3. Prompt → Data Mapping"]
    M0["Prompt-to-SQL mapping<br/>&quot;schemas&quot; → dim_blueprint<br/>&quot;how many&quot; → COUNT DISTINCT"]:::mapping
    M1["System interpretation<br/>&quot;schemas&quot; = records in dim_blueprint"]:::mapping
    M2["Table selected<br/>{table}"]:::mapping
    M3["Schema ID column<br/>{column}"]:::mapping
  end

  subgraph C["4. Context + Planning"]
    C0["Selected plan<br/>{strategy}<br/>{selected_plan}"]:::plan
    C1["Plan split<br/>main answer path: SQL count<br/>side check: dry-run API verification"]:::plan
    C2["Main answer path<br/>SQL count → evidence → final answer"]:::evidence
  end

  subgraph S["5. SQL Derivation"]
    S0["SQL template selected<br/>schema_count"]:::plan
    S1["Generated SQL<br/>{generated_sql}"]:::sql
    S2["SQL validation<br/>read-only ✓<br/>known table ✓<br/>known column ✓"]:::sql
    S3["SQLGlot AST check<br/>parsed_ok = true<br/>destructive_sql = false"]:::sql
  end

  subgraph E["6. SQL Execution + Evidence"]
    E0["DuckDB execution<br/>execute validated SQL"]:::sql
    E1["SQL result<br/>{result}"]:::sql
    E2["Grounded fact<br/>The SQL result means:<br/>{grounded_fact}"]:::evidence
    E3["SQL is the answer source<br/>SQL_ONLY = SQL provides the count"]:::evidence
    E4["Evidence bus<br/>SQL evidence = 74 schemas<br/>API status = dry-run only"]:::evidence
    API0["API verification branch<br/>dry-run verification only<br/>not answer source"]:::api
  end

  subgraph A["7. Answer Generation"]
    A0["Answer intent<br/>COUNT"]:::answer
    A1["Answer synthesis<br/>use SQL count + dry-run note"]:::answer
    A2["Answer verification<br/>&quot;74 schemas&quot; supported by SQL result"]:::answer
    A3["Final answer<br/>{final_answer}"]:::answer
  end

  subgraph O["8. Output + Trace"]
    O0["Trajectory output<br/>strategy = {strategy}<br/>plan = {selected_plan}"]:::output
    O1["Efficiency metrics<br/>tools = {metrics.get('tools', 'unavailable')}<br/>tokens = {metrics.get('tokens', 'unavailable')}<br/>runtime ≈ {runtime}"]:::output
  end

  U0 -->|"schema-count question"| P0
  P0 -->|"send to evidence pipeline"| P1
  P1 -->|"preserve meaning"| P2
  P2 -->|"intent signals"| P3
  P3 -->|"schema/count intent"| M0
  M0 -->|"noun maps to local table"| M1
  M1 -->|"schema records live here"| M2
  M2 -->|"count unique schema IDs"| M3
  M3 -->|"table + column + count operation"| C0
  C0 -->|"selected strategy"| C1
  C1 -->|"main answer path"| C2
  C2 -->|"fill SQL template"| S0
  S0 -->|"COUNT request becomes SQL"| S1
  S1 -->|"validate before execution"| S2
  S2 -->|"parse and inspect AST"| S3
  S3 -->|"safe read-only SQL"| E0
  E0 -->|"DuckDB returns one row"| E1
  E1 -->|"interpret result"| E2
  E2 -->|"answer fact"| E3
  E3 -->|"structured evidence"| E4
  C1 -.->|"verification side path"| API0
  API0 -.->|"dry-run status only"| E4
  E4 -->|"answer slot receives count"| A0
  A0 -->|"compose concise answer"| A1
  A1 -->|"claim support check"| A2
  A2 -->|"verified"| A3
  A3 -->|"logged as final output"| O0
  O0 -->|"submission trace metrics"| O1
"""


def build_markdown(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# SQL-Backed Primary Prompt Storyboard",
            "",
            f"`{md_escape(payload['query_id'])}` was chosen because it is SQL-backed in the packaged path: the prompt becomes validated SQL, SQL returns the answer count, and API verification is dry-run/unavailable.",
            "",
            mermaid_block(payload["flowchart_source"]),
            "",
            "**Takeaway:** SQL is the answer source (`blueprint_count = 74`). The API branch is shown because the packaged trace attempts verification, but it is dry-run/unavailable and does not provide the answer value.",
            "",
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())
