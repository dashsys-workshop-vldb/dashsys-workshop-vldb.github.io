#!/usr/bin/env python
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from supervisor_visualization_common import bottleneck_summary, build_primary_context, current_state  # noqa: E402
from visualization_report_helpers import API_BOTTLENECK_QUERY_ID, VIS_DIR, how_to_read_page, mermaid_block, metric_cards, primary_example_context, prompt_callout, write_json, write_md  # noqa: E402


def main() -> int:
    context = build_primary_context()
    api_context = primary_example_context(API_BOTTLENECK_QUERY_ID)
    state = current_state()
    bottleneck = bottleneck_summary(context)
    api_bottleneck = bottleneck_summary(api_context)
    payload = {
        "page": "score_bottleneck_dashboard",
        "state": state,
        "primary_example": {
            "query_id": context["query_id"],
            "raw_prompt": context["raw_prompt"],
            "api_score": context["api_score"],
            "answer_score": context["answer_score"],
            "strict_score": context["strict_score"],
            "main_bottleneck": context["main_bottleneck"],
        },
        "secondary_api_bottleneck_example": {
            "query_id": api_context["query_id"],
            "raw_prompt": api_context["raw_prompt"],
            "api_score": api_context["api_score"],
            "answer_score": api_context["answer_score"],
            "strict_score": api_context["strict_score"],
            "main_bottleneck": "Dry-run API evidence lacks live payload, so files cannot be listed safely.",
        },
        "blockers": blockers(state, api_bottleneck),
        "score_graph": score_graph(state),
    }
    write_json(VIS_DIR / "score_bottleneck_dashboard.json", payload)
    write_md(VIS_DIR / "score_bottleneck_dashboard.md", build_markdown(payload, context))
    print({"json": str(VIS_DIR / "score_bottleneck_dashboard.json"), "markdown": str(VIS_DIR / "score_bottleneck_dashboard.md")})
    return 0


def score_graph(state: dict) -> str:
    return f"""
flowchart LR
  A["Packaged {state['packaged_strict_score']}"] --> B["Best isolated {state['best_isolated_score']}"]
  B --> C["Target 0.75"]
  A --> D["Submit-ready"]
  C --> E["Not winner-ready yet"]
  F["Main blockers"] --> G["Answer weakness"]
  F --> H["Dry-run payload missing"]
  F --> I["No accepted LLM candidates"]
  F --> J["Shadow/default-off not promotable"]
"""


def blockers(state: dict, bottleneck: dict) -> list[dict]:
    return [
        {
            "blocker": "Answer-score bottleneck",
            "evidence": f"example_031 API score={bottleneck['api_score']}, answer score={bottleneck['answer_score']}",
            "meaning": "Dry-run API evidence lacks live payload, so files cannot be listed safely.",
        },
        {
            "blocker": "Dry-run dependency",
            "evidence": f"live credentials visible={state['live']['credentials_visible']}; dry-run rows={state['live']['dry_run_dependent_rows']}",
            "meaning": "The packaged path must not fabricate live API payload values.",
        },
        {
            "blocker": "No accepted LLM candidates",
            "evidence": f"accepted={state['llm']['accepted']}; candidates={state['llm']['candidate_count']}",
            "meaning": "LLM rewrite search remains shadow-only and did not add a promoted candidate.",
        },
        {
            "blocker": "Endpoint tie-break not promotable",
            "evidence": f"trial eligible rows={state['endpoint_tiebreak']['trial_eligible_rows']}",
            "meaning": "Tie-break v2 did not produce a safe positive trial set.",
        },
        {
            "blocker": "Answer-shape v2 not promotable",
            "evidence": f"recommendation={state['answer_shape_v2']['recommendation']}; projected={state['answer_shape_v2']['projected_score']}",
            "meaning": "Answer-shape v2 remains default-off because gates did not justify promotion.",
        },
        {
            "blocker": "Live credentials missing",
            "evidence": f"credentials visible={state['live']['credentials_visible']}",
            "meaning": "Live-readiness is diagnostic only and cannot change dry-run answers by itself.",
        },
    ]


def build_markdown(payload: dict, context: dict) -> str:
    state = payload["state"]
    example = payload["primary_example"]
    secondary = payload["secondary_api_bottleneck_example"]
    blocker_rows = [(row["blocker"], row["evidence"], row["meaning"]) for row in payload["blockers"]]
    return "\n".join(
        [
            "# Score Bottleneck Dashboard",
            "",
            how_to_read_page("score gap card"),
            "",
            prompt_callout(context["query_id"], context["raw_prompt"], context["why_chosen"]),
            "",
            "## Score Gap Visual",
            "",
            mermaid_block(payload["score_graph"]),
            "",
            "## Current Score Cards",
            "",
            metric_cards(
                [
                    ("Packaged strict score", state["packaged_strict_score"], "Current submit-ready package."),
                    ("Best isolated score", state["best_isolated_score"], "Safe progress, below target."),
                    ("Target", state["target_score"], "Winner-readiness target in this score-push thread."),
                    ("Primary walkthrough", example["query_id"], "SQL-backed example used by the main visualization pages."),
                    ("Primary SQL/API distinction", example["main_bottleneck"], "SQL provides the answer; API verification is dry-run/unavailable."),
                    ("Secondary API bottleneck", secondary["query_id"], "Reference-only API/dry-run bottleneck example."),
                    ("Secondary API score", secondary["api_score"], "Endpoint selection is correct for the API bottleneck row."),
                    ("Secondary answer score", secondary["answer_score"], "Final answer is weak because live payload is unavailable."),
                ]
            ),
            "",
            "## Blocker Cards",
            "",
            metric_cards(blocker_rows),
            "",
            "## Bottom Line",
            "",
            "- The system is submit-ready because the packaged path is safe and readiness checks pass.",
            "- It is not winner-ready because the packaged score remains below `0.75` and the remaining high-value fixes are blocked by evidence availability or promotion gates.",
            "",
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())
