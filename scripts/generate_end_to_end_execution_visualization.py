#!/usr/bin/env python
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from supervisor_visualization_common import build_primary_context, checkpoint_timeline  # noqa: E402
from visualization_report_helpers import (  # noqa: E402
    VIS_DIR,
    checkpoint_output,
    how_to_read_page,
    md_escape,
    mermaid_block,
    metric_cards,
    prompt_callout,
    table,
    visual_summary,
    write_json,
    write_md,
)


def main() -> int:
    context = build_primary_context()
    timeline = checkpoint_timeline(context)
    payload = {
        "page": "end_to_end_execution_primary",
        "query_id": context["query_id"],
        "raw_prompt": context["raw_prompt"],
        "strategy": context["strategy"],
        "route_type": context["route_type"],
        "flowchart": flowchart(),
        "sequence_diagram": sequence_diagram(),
        "checkpoint_timeline": timeline,
        "evidence_flow": evidence_flow(context),
        "decision_flow": decision_flow(context),
    }
    write_json(VIS_DIR / "end_to_end_execution_primary.json", payload)
    write_md(VIS_DIR / "end_to_end_execution_primary.md", build_markdown(payload, context))
    print({"json": str(VIS_DIR / "end_to_end_execution_primary.json"), "markdown": str(VIS_DIR / "end_to_end_execution_primary.md")})
    return 0


def flowchart() -> str:
    return """
flowchart LR
  A["Raw prompt"] --> B["Routing"]
  B --> C["Normalize + tokens"]
  C --> D["Query analysis"]
  D --> E["Metadata/context"]
  E --> F["Planning"]
  F --> G["Validation + budget"]
  G --> H["Execution"]
  H --> I["Evidence bus"]
  I --> J["Answer synthesis"]
  J --> K["Verifier/reranker"]
  K --> L["Final answer"]
  L --> M["Trajectory + reports"]
"""


def sequence_diagram() -> str:
    return """
sequenceDiagram
  participant User
  participant Router
  participant Normalizer
  participant Analysis as Query Analysis
  participant Metadata as Metadata Selector
  participant Planner
  participant SQL as SQL Template
  participant API as API Template
  participant Validator
  participant Executor
  participant Evidence as Evidence Bus
  participant Answer as Answer Synthesizer
  participant Verify as Verifier/Reranker
  participant Output as Final Output
  User->>Router: raw prompt
  Router->>Normalizer: use data pipeline
  Normalizer->>Analysis: normalized text + tokens
  Analysis->>Metadata: route intent + answer family
  Metadata->>Planner: compact context
  Planner->>API: batch files endpoint plan
  Planner->>SQL: no SQL call for API-only route
  API->>Validator: method/path/params
  Validator->>Executor: safe API call
  Executor->>Evidence: dry-run API label
  Evidence->>Answer: evidence objects + missing payload
  Answer->>Verify: grounded final answer
  Verify->>Output: honest dry-run response
"""


def evidence_flow(context: dict) -> list[dict]:
    trajectory = context["trajectory"]
    execution = checkpoint_output(trajectory, "checkpoint_13_tool_execution")
    slots = checkpoint_output(trajectory, "checkpoint_15_answer_slots")
    return [
        {"name": "SQL evidence", "status": "not used", "detail": "API_ONLY route; sql_call_count=0"},
        {"name": "API evidence", "status": "dry-run", "detail": visual_summary(execution, 180)},
        {"name": "Local evidence", "status": "not in packaged final answer", "detail": "No promoted local-evidence answer path for this row."},
        {"name": "Unsupported claims", "status": "not fabricated", "detail": visual_summary(slots, 180)},
    ]


def decision_flow(context: dict) -> list[dict]:
    return [
        {"decision": "Route selected", "value": context["route_type"], "reason": "Batch/file prompt classified as API_ONLY batch family."},
        {"decision": "SQL used?", "value": "no", "reason": "No local SQL call in the packaged trajectory."},
        {"decision": "API used?", "value": "yes", "reason": "Endpoint catalog validates the batch files API call."},
        {"decision": "Dry-run happened?", "value": "yes", "reason": "Adobe credentials unavailable, so live payload was not executed."},
        {"decision": "Answer rewrite promoted?", "value": "no", "reason": "Supportable/LLM rewrites remain shadow or isolated; packaged answer stays honest."},
    ]


def build_markdown(payload: dict, context: dict) -> str:
    timeline_rows = [
        [
            row["order"],
            row["checkpoint_id"],
            row["stage"],
            row["technique"],
            row["input"],
            row["output"],
            row["what_changed"],
            row["impact"],
        ]
        for row in payload["checkpoint_timeline"]
    ]
    evidence_rows = [[row["name"], row["status"], row["detail"]] for row in payload["evidence_flow"]]
    decision_rows = [[row["decision"], row["value"], row["reason"]] for row in payload["decision_flow"]]
    return "\n".join(
        [
            "# End-to-End Execution Movie: example_031",
            "",
            how_to_read_page("raw prompt card"),
            "",
            prompt_callout(context["query_id"], context["raw_prompt"], context["why_chosen"]),
            "",
            "## Execution Flowchart",
            "",
            mermaid_block(payload["flowchart"]),
            "",
            "## System Sequence",
            "",
            mermaid_block(payload["sequence_diagram"]),
            "",
            "## Visual Checkpoint Timeline",
            "",
            table(["#", "Checkpoint", "Stage", "Technique", "Input", "Output", "What changed", "Effect"], timeline_rows),
            "",
            "## Evidence Flow Panel",
            "",
            metric_cards([(row["name"], row["status"], row["detail"]) for row in payload["evidence_flow"]]),
            "",
            "## Decision Flow Panel",
            "",
            table(["Decision", "Value", "Reason"], decision_rows),
            "",
            "## Final Answer",
            "",
            f"> {md_escape(context['final_answer'])}",
            "",
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())
