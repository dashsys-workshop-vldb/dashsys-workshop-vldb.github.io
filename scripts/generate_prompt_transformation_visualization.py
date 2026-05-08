#!/usr/bin/env python
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from supervisor_visualization_common import build_primary_context, step_mermaid  # noqa: E402
from visualization_report_helpers import (  # noqa: E402
    VIS_DIR,
    before_after_panel,
    checkpoint_output,
    how_to_read_page,
    mermaid_block,
    prompt_callout,
    visual_summary,
    write_json,
    write_md,
)


def main() -> int:
    context = build_primary_context()
    panels = build_panels(context)
    payload = {
        "page": "prompt_transformation_primary",
        "query_id": context["query_id"],
        "raw_prompt": context["raw_prompt"],
        "strategy": context["strategy"],
        "panels": panels,
        "steps": context["steps"],
    }
    write_json(VIS_DIR / "prompt_transformation_primary.json", payload)
    write_md(VIS_DIR / "prompt_transformation_primary.md", build_markdown(payload, context))
    print({"json": str(VIS_DIR / "prompt_transformation_primary.json"), "markdown": str(VIS_DIR / "prompt_transformation_primary.md")})
    return 0


def build_panels(context: dict) -> list[dict]:
    trajectory = context["trajectory"]
    normalized = checkpoint_output(trajectory, "checkpoint_02_query_normalization")
    tokens = checkpoint_output(trajectory, "checkpoint_03_query_tokens")
    analysis = checkpoint_output(trajectory, "checkpoint_05_query_analysis")
    lookup = checkpoint_output(trajectory, "checkpoint_06_lookup_path")
    context_card = checkpoint_output(trajectory, "checkpoint_07_context_card")
    plan = checkpoint_output(trajectory, "checkpoint_08_candidate_plans")
    execution = checkpoint_output(trajectory, "checkpoint_13_tool_execution")
    slots = checkpoint_output(trajectory, "checkpoint_15_answer_slots")
    final_answer = checkpoint_output(trajectory, "checkpoint_18_final_answer")
    return [
        panel("Raw → normalized", context["raw_prompt"], normalized, "query_normalizer", "accuracy + observability"),
        panel("Normalized → tokens/entities", normalized, tokens, "query_tokens", "accuracy"),
        panel("Tokens/entities → query analysis", tokens, analysis, "query_analysis", "accuracy"),
        panel("Analysis → context card", {"analysis": visual_summary(analysis), "lookup": visual_summary(lookup)}, context_card, "metadata_selector + context cards", "accuracy + efficiency"),
        panel("Context → selected plan", context_card, plan, "planner + plan_ensemble", "efficiency + safety"),
        panel("Plan → evidence", plan, execution, "executor + API validator", "safety"),
        panel("Evidence → final answer", {"evidence": visual_summary(execution), "slots": visual_summary(slots)}, final_answer or context["final_answer"], "answer slots + verifier", "accuracy + safety"),
    ]


def panel(title: str, before, after, technique: str, impact: str) -> dict:
    return {
        "title": title,
        "before": before,
        "after": after,
        "technique": technique,
        "impact": impact,
    }


def build_markdown(payload: dict, context: dict) -> str:
    panel_md = [
        before_after_panel(item["title"], item["before"], item["after"], item["technique"], item["impact"])
        for item in payload["panels"]
    ]
    return "\n".join(
        [
            "# Prompt Transformation: example_011",
            "",
            how_to_read_page("raw prompt card"),
            "",
            prompt_callout(context["query_id"], context["raw_prompt"], context["why_chosen"]),
            "",
            "## Transformation Lineage",
            "",
            mermaid_block(step_mermaid(context["steps"])),
            "",
            "## Before → After Panels",
            "",
            "\n\n".join(panel_md),
            "",
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())
