#!/usr/bin/env python
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from supervisor_visualization_common import current_state  # noqa: E402
from visualization_report_helpers import VIS_DIR, how_to_read_page, mermaid_block, metric_cards, status_badge, write_json, write_md  # noqa: E402


def main() -> int:
    state = current_state()
    payload = {"page": "system_status_dashboard", "state": state, "status_graph": status_graph(state)}
    write_json(VIS_DIR / "system_status_dashboard.json", payload)
    write_md(VIS_DIR / "system_status_dashboard.md", build_markdown(payload))
    print({"json": str(VIS_DIR / "system_status_dashboard.json"), "markdown": str(VIS_DIR / "system_status_dashboard.md")})
    return 0


def status_graph(state: dict) -> str:
    return f"""
flowchart LR
  A["Packaged path"] --> B["{state['preferred_strategy']}"]
  B --> C["Strict {state['packaged_strict_score']}"]
  B --> D["Correctness {state['correctness']}"]
  B --> E["Hidden {state['hidden_style']}"]
  B --> F["Ready {state['final_submission_ready']}"]
  G["Promoted"] --> H["Official-token reduction"]
  I["Shadow/default-off"] --> J["Answer-shape v2"]
  I --> K["Endpoint tie-break v2"]
  L["Diagnostic"] --> M["Live readiness"]
  L --> N["Secret/readiness"]
  O["Disabled"] --> P["Compact context"]
  O --> Q["Repair"]
"""


def build_markdown(payload: dict) -> str:
    state = payload["state"]
    return "\n".join(
        [
            "# System Status Dashboard",
            "",
            how_to_read_page("status cards"),
            "",
            "## Status Map",
            "",
            mermaid_block(payload["status_graph"]),
            "",
            "## Packaged Metrics",
            "",
            metric_cards(
                [
                    ("Preferred strategy", state["preferred_strategy"], "Must remain SQL_FIRST_API_VERIFY."),
                    ("Packaged strict score", state["packaged_strict_score"], "Submit-ready packaged score."),
                    ("Best isolated score", state["best_isolated_score"], "Best safe trial score; below winner target."),
                    ("Correctness", state["correctness"], "Current strict correctness."),
                    ("Tokens/runtime/tools", f"{state['tokens']} / {state['runtime']} / {state['tool_calls']}", "Efficiency metrics."),
                    ("Hidden-style", state["hidden_style"], "Current hidden-style pass result."),
                    ("Readiness", state["final_submission_ready"], "Final submission package status."),
                    ("Secret scan", state["no_secret_scan_ok"], "Readiness secret scan status."),
                ]
            ),
            "",
            "## Technique Status Cards",
            "",
            metric_cards(
                [
                    ("Official-token reduction", status_badge(state["official_token_reduction"]["state"]), "Promoted in the packaged path."),
                    ("LLM rewrite search", status_badge(state["llm"]["state"]), f"Candidates={state['llm']['candidate_count']}; accepted={state['llm']['accepted']}."),
                    ("Live-mode readiness", status_badge(state["live"]["state"]), f"Credentials visible={state['live']['credentials_visible']}; dry-run rows={state['live']['dry_run_dependent_rows']}."),
                    ("Answer-shape v2", status_badge(state["answer_shape_v2"]["state"]), f"Recommendation={state['answer_shape_v2']['recommendation']}."),
                    ("SQL-only API-skip", status_badge(state["sql_only_api_skip"]["state"]), f"Rows={state['sql_only_api_skip']['rows']}."),
                    ("Endpoint-family tie-break", status_badge(state["endpoint_tiebreak"]["state"]), f"Trial eligible rows={state['endpoint_tiebreak']['trial_eligible_rows']}."),
                    ("Compact context", status_badge(state["compact_context"]["state"]), f"Enabled={state['compact_context']['enabled']}."),
                    ("Repair execution", status_badge(state["repair"]["state"]), f"Enabled={state['repair']['enabled']}."),
                ]
            ),
            "",
            "## Readiness Interpretation",
            "",
            "- Submit-ready: final package, preferred strategy, hidden-style, and secret checks are valid.",
            "- Not winner-ready: packaged strict score is below `0.75`, and shadow/default-off ideas have not passed promotion gates.",
            "",
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())
