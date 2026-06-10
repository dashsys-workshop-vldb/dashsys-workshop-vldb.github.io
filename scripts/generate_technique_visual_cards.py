#!/usr/bin/env python
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from supervisor_visualization_common import technique_cards  # noqa: E402
from visualization_report_helpers import VIS_DIR, UNAVAILABLE, how_to_read_page, md_escape, metric_cards, visual_summary, write_json, write_md  # noqa: E402


def main() -> int:
    cards = technique_cards()
    payload = {
        "page": "technique_visual_cards",
        "total": len(cards),
        "cards": cards,
    }
    write_json(VIS_DIR / "technique_visual_cards.json", payload)
    write_md(VIS_DIR / "technique_visual_cards.md", build_markdown(payload))
    print({"json": str(VIS_DIR / "technique_visual_cards.json"), "markdown": str(VIS_DIR / "technique_visual_cards.md"), "cards": len(cards)})
    return 0


def build_markdown(payload: dict) -> str:
    sections = [
        "# Technique Visual Cards",
        "",
        how_to_read_page("technique status badges"),
        "",
        "Each card separates **status** from **runtime path** so experimental work is not confused with the packaged system.",
        "",
    ]
    for card in payload["cards"]:
        effect = card.get("measured_effect") or {}
        effect_summary = ", ".join(
            f"{key}={value}" for key, value in effect.items() if value not in (None, "", UNAVAILABLE)
        ) or UNAVAILABLE
        sections.extend(
            [
                f"## {card['status_badge']} {card['technique_name']}",
                "",
                metric_cards(
                    [
                        ("Runtime path", card["runtime_badge"], "Where this technique actually runs today."),
                        ("Input", card["input"], "Data consumed by the technique."),
                        ("Changed artifact", card["changed_artifact"], "Intermediate representation it changes."),
                        ("Output", card["output"], "Data emitted downstream."),
                        ("Downstream effect", card["downstream_effect"], "Why the technique exists."),
                        ("Affects", ", ".join(card["affects"]), "Accuracy, efficiency, safety, or observability."),
                        ("Measured impact", visual_summary(effect_summary, 180), "Unavailable means no source report measured a delta."),
                    ]
                ),
                "",
                f"**Why this status:** {md_escape(card.get('why'))}",
                "",
            ]
        )
    return "\n".join(sections)


if __name__ == "__main__":
    raise SystemExit(main())
