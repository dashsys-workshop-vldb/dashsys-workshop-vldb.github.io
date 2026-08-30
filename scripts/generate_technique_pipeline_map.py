#!/usr/bin/env python
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from supervisor_visualization_common import TECHNIQUE_GROUPS, technique_cards  # noqa: E402
from visualization_report_helpers import VIS_DIR, how_to_read_page, md_escape, mermaid_block, status_badge, table, write_json, write_md  # noqa: E402


def main() -> int:
    cards = technique_cards()
    payload = {
        "page": "technique_pipeline_map",
        "groups": group_cards(cards),
        "pipeline_mermaid": pipeline_mermaid(cards),
    }
    write_json(VIS_DIR / "technique_pipeline_map.json", payload)
    write_md(VIS_DIR / "technique_pipeline_map.md", build_markdown(payload))
    print({"json": str(VIS_DIR / "technique_pipeline_map.json"), "markdown": str(VIS_DIR / "technique_pipeline_map.md")})
    return 0


def group_cards(cards: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for card in cards:
        grouped[card["group"]].append(card)
    ordered = {}
    for group in TECHNIQUE_GROUPS:
        ordered[group] = sorted(grouped.get(group, []), key=lambda item: item["technique_name"])
    for group, rows in grouped.items():
        if group not in ordered:
            ordered[group] = sorted(rows, key=lambda item: item["technique_name"])
    return ordered


def pipeline_mermaid(cards: list[dict]) -> str:
    by_name = {card["technique_name"]: card for card in cards}
    def label(name: str) -> str:
        status = by_name.get(name, {}).get("status", "")
        prefix = {"promoted_default": "🟢", "shadow_only": "🟡", "default_off": "⚪", "diagnostic_only": "🔵"}.get(status, "▣")
        return f'{prefix} {name}'
    return f"""
flowchart LR
  A["Raw prompt"] --> B["{label('prompt_router')}"]
  B --> C["{label('simple_prompt_gate')}"]
  C --> D["{label('query_normalizer')}"]
  D --> E["{label('query_tokens')}"]
  E --> F["{label('query_analysis')}"]
  F --> G["{label('metadata_selector')}"]
  G --> H["{label('SQL_FIRST_API_VERIFY')}"]
  H --> I["{label('SQL templates')}"]
  H --> J["{label('API templates')}"]
  I --> K["{label('executor')}"]
  J --> K
  K --> L["{label('evidence_bus')}"]
  L --> M["{label('answer verifier')}"]
  M --> N["Final answer"]
  G -.shadow.-> O["{label('endpoint-family tie-break v2')}"]
  L -.shadow.-> P["{label('supportable answer rewriter')}"]
  P -.isolated.-> Q["{label('OpenRouter LLM rewrite search')}"]
  N -.diagnostic.-> R["{label('hidden-style eval')}"]
  N -.diagnostic.-> S["{label('package readiness checks')}"]
"""


def build_markdown(payload: dict) -> str:
    sections = []
    for group, rows in payload["groups"].items():
        sections.append(f"## {group}")
        sections.append("")
        chunks = []
        for row in rows:
            chunks.append(
                "\n".join(
                    [
                        f"### {row['status_badge']} `{md_escape(row['technique_name'])}`",
                        "",
                        f"**Runtime path:** {md_escape(row['runtime_badge'])}",
                        "",
                        f"**Input → output:** {md_escape(row['input'])} → {md_escape(row['output'])}",
                        "",
                        f"**Changed artifact:** {md_escape(row['changed_artifact'])}",
                        "",
                        f"**Downstream effect:** {md_escape(row['downstream_effect'])}",
                        "",
                        f"**Affects:** {', '.join(row['affects'])}",
                    ]
                )
            )
        sections.append("\n\n".join(chunks))
        sections.append("")
    return "\n".join(
        [
            "# Technique Pipeline Map",
            "",
            how_to_read_page("pipeline diagram"),
            "",
            "## Pipeline Placement",
            "",
            mermaid_block(payload["pipeline_mermaid"]),
            "",
            "## Badge Legend",
            "",
            table(
                ["Status", "Meaning"],
                [
                    [status_badge("promoted_default"), "Runs in the packaged path."],
                    [status_badge("shadow_only"), "Evaluated in shadow reports; not packaged."],
                    [status_badge("default_off"), "Feature-flagged or isolated only."],
                    [status_badge("diagnostic_only"), "Reports/checks only."],
                    [status_badge("not_promoted"), "Blocked or not promoted."],
                ],
            ),
            "",
            "\n".join(sections),
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())
