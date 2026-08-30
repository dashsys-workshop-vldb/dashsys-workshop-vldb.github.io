#!/usr/bin/env python
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from supervisor_visualization_common import bottleneck_summary, build_primary_context, current_state, step_mermaid  # noqa: E402
from visualization_report_helpers import (  # noqa: E402
    VIS_DIR,
    how_to_read_page,
    mermaid_block,
    metric_cards,
    prompt_callout,
    status_badge,
    write_json,
    write_md,
)


def main() -> int:
    context = build_primary_context()
    state = current_state()
    bottleneck = bottleneck_summary(context)
    payload = {
        "page": "executive_dashboard",
        "primary_example": {
            key: context[key]
            for key in [
                "query_id",
                "raw_prompt",
                "why_chosen",
                "strategy",
                "route_type",
                "final_answer",
                "strict_score",
                "correctness_score",
                "answer_score",
                "api_score",
                "tool_calls",
                "tokens",
                "runtime",
                "api_status",
                "main_bottleneck",
            ]
        },
        "current_state": state,
        "bottleneck": bottleneck,
        "journey_steps": context["steps"],
    }
    write_json(VIS_DIR / "executive_dashboard.json", payload)
    write_md(VIS_DIR / "executive_dashboard.md", build_markdown(payload))
    print({"json": str(VIS_DIR / "executive_dashboard.json"), "markdown": str(VIS_DIR / "executive_dashboard.md")})
    return 0


def build_markdown(payload: dict) -> str:
    example = payload["primary_example"]
    state = payload["current_state"]
    bottleneck = payload["bottleneck"]
    journey = payload["journey_steps"]
    state_graph = f"""
flowchart LR
  A["Packaged system"] --> B["{state['preferred_strategy']}"]
  B --> C["Strict {state['packaged_strict_score']}"]
  C --> D["Submit-ready: {state['final_submission_ready']}"]
  C --> E["Target 0.75"]
  F["Best isolated"] --> G["{state['best_isolated_score']}"]
  H["Primary walkthrough"] --> I["SQL-backed example_011"]
  I --> J["SQL count -> final answer"]
"""
    promotion_graph = """
flowchart LR
  P["Packaged"] --> A["🟢 promoted_default"]
  S["Candidate reports"] --> B["🟡 shadow_only"]
  O["Feature flags"] --> C["⚪ default_off"]
  D["Reports/checks"] --> E["🔵 diagnostic_only"]
  X["Not promoted"] --> R["🔴 blocked/not_promoted"]
"""
    return "\n".join(
        [
            "# DASHSys Executive Visualization Dashboard",
            "",
            how_to_read_page("raw prompt card"),
            "",
            prompt_callout(example["query_id"], example["raw_prompt"], example["why_chosen"]),
            "",
            "## System At A Glance",
            "",
            mermaid_block(state_graph),
            "",
            metric_cards(
                [
                    ("Packaged strict score", state["packaged_strict_score"], "Current submit-ready score."),
                    ("Best isolated score", state["best_isolated_score"], "Safe trial progress, not promoted as winner-ready."),
                    ("Correctness", state["correctness"], "Must not regress."),
                    ("Hidden-style", state["hidden_style"], "Current robustness gate."),
                    ("Final readiness", state["final_submission_ready"], "Submission package still valid."),
                    ("Secret scan", state["no_secret_scan_ok"], "Readiness secret scan result."),
                ]
            ),
            "",
            "## Primary Prompt Journey",
            "",
            mermaid_block(step_mermaid(journey)),
            "",
            "➡️ Open the flagship walkthrough: [sql_prompt_storyboard_primary.md](sql_prompt_storyboard_primary.md)",
            "",
            "## Bottleneck Card",
            "",
            f"### 🟢 SQL-backed primary walkthrough",
            "",
            metric_cards(
                [
                    ("SQL score", bottleneck["sql_score"], "Generated SQL is validated and scored."),
                    ("API score", bottleneck["api_score"], "API verification is attempted as dry-run/unavailable."),
                    ("Answer score", bottleneck["answer_score"], "Final answer is grounded by SQL count plus dry-run note."),
                    ("Strict score", bottleneck["strict_score"], "Row-level strict score for the packaged path."),
                    ("Main distinction", bottleneck["main_bottleneck"], "SQL is the answer source; API verification is not live."),
                ]
            ),
            "",
            "## Technique State Legend",
            "",
            mermaid_block(promotion_graph),
            "",
            metric_cards(
                [
                    ("Official-token reduction", status_badge(state["official_token_reduction"]["state"]), "Enabled in the packaged path."),
                    ("Answer-shape v2", status_badge(state["answer_shape_v2"]["state"]), "Evaluated, not promoted."),
                    ("Endpoint tie-break v2", status_badge(state["endpoint_tiebreak"]["state"]), "Shadow-only report."),
                    ("Live readiness", status_badge(state["live"]["state"]), "Diagnostic only; credentials not visible."),
                    ("Compact context", status_badge(state["compact_context"]["state"]), "Disabled/default-off."),
                    ("Repair execution", status_badge(state["repair"]["state"]), "Disabled/default-off."),
                ]
            ),
            "",
            "## Submit-Ready, Not Winner-Ready",
            "",
            "- Submit-ready because packaging, hidden-style, readiness, and secret checks pass.",
            "- Not winner-ready because packaged strict score remains below `0.75` and the best safe isolated score is still below target.",
            "- Secondary API-only bottleneck pages remain reference material; the main walkthrough is now SQL-backed.",
            "",
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())
