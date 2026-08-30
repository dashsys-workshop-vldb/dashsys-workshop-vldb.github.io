#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from scripts.nl_sql_robustness_common import analyze_prompt_groups, safe_report_payload


REPORT_STEM = "nl_sql_paraphrase_consistency"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic paraphrase consistency diagnostics for NL-to-SQL.")
    parser.add_argument("--no-generated", action="store_true", help="Exclude generated diagnostic prompts.")
    parser.add_argument("--max-groups", type=int, default=None, help="Limit semantic groups for quick checks.")
    parser.add_argument("--max-generated", type=int, default=None, help="Limit generated prompt groups.")
    args = parser.parse_args()
    config = Config.from_env(ROOT)
    payload = run_nl_sql_paraphrase_consistency(
        config,
        include_generated=not args.no_generated,
        max_groups=args.max_groups,
        max_generated=args.max_generated,
    )
    print(
        json.dumps(
            {
                "json": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.json"),
                "markdown": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.md"),
                "group_count": payload.get("group_count"),
                "paraphrase_consistency_score": payload.get("summary", {}).get("paraphrase_consistency_score"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def run_nl_sql_paraphrase_consistency(
    config: Config | None = None,
    *,
    include_generated: bool = True,
    max_groups: int | None = None,
    max_generated: int | None = None,
) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    _rows, groups, metrics = analyze_prompt_groups(
        config,
        include_generated=include_generated,
        max_groups=max_groups,
        max_generated=max_generated,
        enable_schema_aware=False,
    )
    instability_counts = Counter()
    for group in groups:
        for name, value in (group.get("instabilities") or {}).items():
            if value:
                instability_counts[name] += 1
    payload = safe_report_payload(
        {
            "report_type": REPORT_STEM,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "diagnostic_only": True,
            "official_score_claim": False,
            "promotion_allowed": False,
            "group_count": len(groups),
            "summary": {
                "paraphrase_consistency_score": metrics.get("paraphrase_consistency_score"),
                "route_stability": metrics.get("route_stability"),
                "table_selection_stability": metrics.get("table_selection_stability"),
                "join_selection_stability": metrics.get("join_selection_stability"),
                "count_count_distinct_stability": metrics.get("count_count_distinct_stability"),
                "answer_intent_stability": metrics.get("answer_intent_stability"),
                "template_dependency_score": metrics.get("template_dependency_score"),
                "instability_counts": dict(instability_counts),
            },
            "instability_definitions": {
                "route_changed": "Route type differs from the original prompt in the same semantic group.",
                "table_changed": "Selected SQL tables differ from the original prompt.",
                "join_changed": "Join count differs from the original prompt.",
                "count_changed": "COUNT/non-COUNT shape differs from the original prompt.",
                "answer_intent_changed": "Answer family differs from the original prompt.",
                "sql_shape_changed": "Normalized SQL shape differs from the original prompt.",
            },
            "groups": groups,
            "output_paths": {
                "json": str(reports_dir / f"{REPORT_STEM}.json"),
                "markdown": str(reports_dir / f"{REPORT_STEM}.md"),
            },
        }
    )
    (reports_dir / f"{REPORT_STEM}.json").write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    (reports_dir / f"{REPORT_STEM}.md").write_text(_render_markdown(payload), encoding="utf-8")
    return payload


def _render_markdown(report: dict[str, Any]) -> str:
    summary = report.get("summary", {})
    lines = [
        "# NL-to-SQL Paraphrase Consistency",
        "",
        "Diagnostic-only report. Generated prompt variants are coverage stress tests, not official score evidence.",
        "",
        f"- Semantic groups: `{report.get('group_count')}`",
        f"- Paraphrase consistency score: `{summary.get('paraphrase_consistency_score')}`",
        f"- Route stability: `{summary.get('route_stability')}`",
        f"- Table selection stability: `{summary.get('table_selection_stability')}`",
        f"- Join selection stability: `{summary.get('join_selection_stability')}`",
        f"- Count/count-distinct stability: `{summary.get('count_count_distinct_stability')}`",
        f"- Answer intent stability: `{summary.get('answer_intent_stability')}`",
        "",
        "## Instability Counts",
        "",
    ]
    for name, count in sorted((summary.get("instability_counts") or {}).items()):
        lines.append(f"- `{name}`: {count}")
    lines.extend(["", "## Representative Unstable Groups", ""])
    groups = [
        group
        for group in sorted(report.get("groups", []), key=lambda item: float(item.get("paraphrase_consistency_score") or 0.0))
        if any((group.get("instabilities") or {}).values())
    ][:20]
    for group in groups:
        flags = [name for name, value in (group.get("instabilities") or {}).items() if value]
        lines.append(f"- `{group.get('prompt_id')}`: `{group.get('paraphrase_consistency_score')}` ({', '.join(flags)})")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
