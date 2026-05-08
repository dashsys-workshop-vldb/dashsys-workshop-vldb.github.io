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
    how_to_read_page,
    md_escape,
    mermaid_block,
    metric_cards,
    prompt_callout,
    visual_card,
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
        "flowchart": flowchart(),
        "sequence_diagram": sequence_diagram(),
        "journey_diagram": journey_diagram(),
        "source_trajectory": context["trajectory_path"],
    }
    write_json(VIS_DIR / "sql_prompt_storyboard_primary.json", payload)
    write_md(VIS_DIR / "sql_prompt_storyboard_primary.md", build_markdown(payload))
    print({"json": str(VIS_DIR / "sql_prompt_storyboard_primary.json"), "markdown": str(VIS_DIR / "sql_prompt_storyboard_primary.md")})
    return 0


def flowchart() -> str:
    return """
flowchart LR
  A["Raw prompt"] --> B["Router/gate"]
  B --> C["Normalize + tokens"]
  C --> D["Query analysis"]
  D --> E["Context selection"]
  E --> F["SQL planning input"]
  F --> G["Generated SQL"]
  G --> H["SQL validation"]
  H --> I["SQL execution"]
  I --> J["Evidence extraction"]
  J --> K["Answer synthesis"]
  K --> L["Answer verification"]
  L --> M["Final answer"]
  M --> N["Trajectory output"]
  H -.-> O["Dry-run API verification"]
  O -.-> K
"""


def sequence_diagram() -> str:
    return """
sequenceDiagram
  participant User
  participant Router
  participant Normalizer
  participant Analyzer as Query Analysis
  participant Context as Context Selector
  participant Planner
  participant Validator
  participant DuckDB as SQL Executor
  participant API as API Dry-Run
  participant Evidence
  participant Answer
  participant Verifier
  participant Output
  User->>Router: How many schemas do I have?
  Router->>Normalizer: use data pipeline
  Normalizer->>Analyzer: normalized schema/count query
  Analyzer->>Context: schema_count intent
  Context->>Planner: dim_blueprint + schema API context
  Planner->>Validator: generated SQL + API verification
  Validator->>DuckDB: safe read-only SQL
  DuckDB->>Evidence: blueprint_count row
  Validator->>API: catalog-valid verification call
  API->>Evidence: dry-run unavailable label
  Evidence->>Answer: count evidence + dry-run status
  Answer->>Verifier: SQL-grounded answer
  Verifier->>Output: final answer + trajectory
"""


def journey_diagram() -> str:
    return """
journey
  title example_011 Prompt to SQL to Answer
  section Prompt understanding
    Raw prompt captured: 5: User
    Schema count intent detected: 5: Router
    Query normalized and tokenized: 4: Normalizer
  section SQL path
    Context selects dim_blueprint: 5: Metadata
    SQL count generated: 5: Planner
    SQL validated as read-only: 5: Validator
    DuckDB returns count: 5: Executor
  section Answer path
    Evidence bus forwards count: 5: Evidence
    Answer states schema count: 5: Answer
    Dry-run API note preserved: 4: Verifier
"""


def build_markdown(payload: dict[str, Any]) -> str:
    sql = payload["sql_artifacts"].get("generated_sql")
    result = payload["sql_artifacts"].get("sql_result")
    result_facts = payload["sql_artifacts"].get("sql_result_facts") or ["unavailable"]
    timeline_cards = [
        visual_card(
            f"{row['order']}. {row['checkpoint_id']}",
            "▣",
            "\n".join(
                [
                    f"**Stage:** {md_escape(row['stage'])}",
                    f"**Technique:** `{md_escape(row['technique'])}`",
                    f"**Input:** {md_escape(row['input'])}",
                    f"**Output:** {md_escape(row['output'])}",
                    f"**Effect:** {md_escape(row['impact'])}",
                ]
            ),
        )
        for row in payload["checkpoint_timeline"]
    ]
    step_cards = [
        visual_card(
            step["name"],
            "▶",
            "\n".join(
                [
                    f"**Payload:** {md_escape(step['short_payload'])}",
                    f"**Technique:** `{md_escape(step['technique'])}`",
                    f"**What changed:** {md_escape(step['what_changed'])}",
                    f"**Impact:** {md_escape(step['impact'])}",
                ]
            ),
        )
        for step in payload["storyboard_steps"]
    ]
    return "\n".join(
        [
            "# SQL-Backed Primary Prompt Storyboard",
            "",
            how_to_read_page("SQL-backed raw prompt card"),
            "",
            prompt_callout(payload["query_id"], payload["raw_prompt"], payload["why_chosen"]),
            "",
            "## Why This Example Was Chosen",
            "",
            "- It is SQL-backed in the packaged path: SQL is the answer source.",
            "- It still shows the real system nuance: API verification was attempted but only dry-run/unavailable.",
            "- It demonstrates prompt → SQL → SQL evidence → final answer without using an API-only row as the main walkthrough.",
            "",
            "## Full End-to-End Flow Diagram",
            "",
            mermaid_block(payload["flowchart"]),
            "",
            "## System Sequence Diagram",
            "",
            mermaid_block(payload["sequence_diagram"]),
            "",
            "## Prompt → SQL → Answer Journey",
            "",
            mermaid_block(payload["journey_diagram"]),
            "",
            "## Prompt Transformation Storyboard",
            "",
            "\n\n".join(step_cards),
            "",
            "## Prompt → SQL Derivation",
            "",
            visual_card(
                "Generated SQL",
                "🟢 SQL answer source",
                "\n".join(
                    [
                        f"**Prompt intent:** `{md_escape(payload['route_type'])}` schema count.",
                        f"**Generated SQL:**",
                        "",
                        "```sql",
                        str(sql),
                        "```",
                    ]
                ),
            ),
            "",
            "## SQL Validation / Execution",
            "",
            visual_card(
                "Validated SQL and DuckDB Result",
                "🟢 validated read-only SQL",
                "\n".join(
                    [
                        f"**SQL calls executed:** `{md_escape(payload['sql_artifacts'].get('sql_calls_executed'))}`",
                        f"**API calls executed:** `{md_escape(payload['sql_artifacts'].get('api_calls_executed'))}`",
                        f"**API verification:** {md_escape(payload['api_status'])}",
                        f"**SQL result:** `{md_escape('; '.join(str(item) for item in result_facts))}`",
                        f"**Raw result preview:** `{md_escape(visual_summary(result, 240))}`",
                    ]
                ),
            ),
            "",
            "## Evidence → Final Answer",
            "",
            visual_card(
                "Evidence Extraction",
                "🟢 SQL evidence",
                "\n".join(
                    [
                        f"**Evidence:** `{md_escape(visual_summary(payload['sql_artifacts'].get('evidence'), 240))}`",
                        f"**Extracted fact:** `{md_escape('; '.join(str(item) for item in result_facts))}`",
                        "**Meaning:** SQL returns the schema count; dry-run API status explains why live API verification is unavailable.",
                    ]
                ),
            ),
            "",
            "## Checkpoint Timeline Visualization",
            "",
            "\n\n".join(timeline_cards),
            "",
            "## Final Answer Card",
            "",
            visual_card(
                "Final Answer",
                "🟢 SQL-grounded answer",
                f"> {md_escape(payload['final_answer'])}",
            ),
            "",
            "## Key Takeaway",
            "",
            "SQL provides the answer. API verification is present in the packaged trace, but it is dry-run/unavailable, so the final answer includes the honest live-API disclaimer.",
            "",
            "## Supporting Metrics",
            "",
            metric_cards(
                [
                    ("Strict score", payload["metrics"]["strict_score"], "Row-level strict score."),
                    ("Correctness", payload["metrics"]["correctness_score"], "Row-level correctness score."),
                    ("SQL score", payload["metrics"]["sql_score"], "Strict SQL component."),
                    ("API score", payload["metrics"]["api_score"], "Dry-run verification call still scored."),
                    ("Answer score", payload["metrics"]["answer_score"], "Final-answer component."),
                    ("Tools/tokens/runtime", f"{payload['metrics']['tool_calls']} / {payload['metrics']['tokens']} / {payload['metrics']['runtime']}", "Packaged trajectory metrics."),
                ]
            ),
            "",
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())
