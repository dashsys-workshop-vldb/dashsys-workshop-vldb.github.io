#!/usr/bin/env python
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from supervisor_visualization_common import bottleneck_summary, build_primary_context, step_mermaid  # noqa: E402
from visualization_report_helpers import (  # noqa: E402
    VIS_DIR,
    how_to_read_page,
    md_escape,
    mermaid_block,
    metric_cards,
    prompt_callout,
    visual_card,
    write_json,
    write_md,
)


def main() -> int:
    context = build_primary_context()
    payload = {
        "page": "prompt_storyboard_primary",
        "primary_example": {
            "query_id": context["query_id"],
            "raw_prompt": context["raw_prompt"],
            "strategy": context["strategy"],
            "route_type": context["route_type"],
            "final_answer": context["final_answer"],
            "strict_score": context["strict_score"],
            "correctness_score": context["correctness_score"],
            "api_score": context["api_score"],
            "answer_score": context["answer_score"],
            "tool_calls": context["tool_calls"],
            "tokens": context["tokens"],
            "runtime": context["runtime"],
            "dry_run_status": context["api_status"],
            "main_bottleneck": context["main_bottleneck"],
        },
        "bottleneck": bottleneck_summary(context),
        "storyboard_steps": context["steps"],
    }
    write_json(VIS_DIR / "prompt_storyboard_primary.json", payload)
    write_md(VIS_DIR / "prompt_storyboard_primary.md", build_markdown(payload))
    print({"json": str(VIS_DIR / "prompt_storyboard_primary.json"), "markdown": str(VIS_DIR / "prompt_storyboard_primary.md")})
    return 0


def build_markdown(payload: dict) -> str:
    example = payload["primary_example"]
    bottleneck = payload["bottleneck"]
    steps = payload["storyboard_steps"]
    cards = []
    for idx, step in enumerate(steps, start=1):
        cards.append(
            visual_card(
                f"{idx}. {step['name']}",
                "▣",
                "\n".join(
                    [
                        f"**Payload:** {md_escape(step['short_payload'])}",
                        f"**Technique:** `{md_escape(step['technique'])}`",
                        f"**What changed:** {md_escape(step['what_changed'])}",
                        f"**Primary impact:** {md_escape(step['impact'])}",
                    ]
                ),
            )
        )
    return "\n".join(
        [
            "# Primary Prompt Storyboard: example_031",
            "",
            how_to_read_page("raw prompt card"),
            "",
            prompt_callout(example["query_id"], example["raw_prompt"], "Chosen because it shows the real submit-ready/not-winner-ready gap: API selection is correct, but dry-run answer evidence is incomplete."),
            "",
            "## Bottleneck Snapshot",
            "",
            metric_cards(
                [
                    ("API score", bottleneck["api_score"], "The selected API call is scored as correct."),
                    ("Answer score", bottleneck["answer_score"], "The final answer is weak because live file payload is unavailable."),
                    ("Main bottleneck", bottleneck["main_bottleneck"], "No file list can be safely stated from dry-run evidence."),
                    ("Dry-run status", bottleneck["dry_run_status"], "Credentials were not available for live API payloads."),
                ]
            ),
            "",
            "## Storyboard Flow",
            "",
            mermaid_block(step_mermaid(steps)),
            "",
            "## Visual Step Cards",
            "",
            "\n\n".join(cards),
            "",
            "## Final Answer",
            "",
            f"> {md_escape(example['final_answer'])}",
            "",
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())
