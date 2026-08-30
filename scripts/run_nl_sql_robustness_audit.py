#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from scripts.nl_sql_robustness_common import analyze_prompt_groups, safe_report_payload


REPORT_STEM = "nl_sql_robustness_audit"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run diagnostic-only NL-to-SQL robustness audit.")
    parser.add_argument("--no-generated", action="store_true", help="Exclude generated diagnostic prompts.")
    parser.add_argument("--max-groups", type=int, default=None, help="Limit semantic prompt groups for quick local checks.")
    parser.add_argument("--max-generated", type=int, default=None, help="Limit generated prompt groups.")
    args = parser.parse_args()
    config = Config.from_env(ROOT)
    payload = run_nl_sql_robustness_audit(
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
                "template_dependency_score": payload.get("metrics", {}).get("template_dependency_score"),
                "paraphrase_consistency_score": payload.get("metrics", {}).get("paraphrase_consistency_score"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def run_nl_sql_robustness_audit(
    config: Config | None = None,
    *,
    include_generated: bool = True,
    max_groups: int | None = None,
    max_generated: int | None = None,
) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    rows, groups, metrics = analyze_prompt_groups(
        config,
        include_generated=include_generated,
        max_groups=max_groups,
        max_generated=max_generated,
        enable_schema_aware=False,
    )
    payload = safe_report_payload(
        {
            "report_type": REPORT_STEM,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "diagnostic_only": True,
            "official_score_claim": False,
            "promotion_allowed": False,
            "strategy": "SQL_FIRST_API_VERIFY",
            "schema_aware_fallback_packaged_default": False,
            "variant_kinds": sorted({row.get("variant_kind") for row in rows}),
            "metrics": metrics,
            "rows": rows,
            "groups": groups,
            "methodology": {
                "description": "Deterministic paraphrase/synonym/order variants are used to stress SQL routing, table selection, and SQL shape stability without LLM-as-judge.",
                "answer_correctness_proxy": "Local proxy only: SQL validation/execution success, not official answer score.",
                "template_dependency_score": "Higher means more risk from template dependence, fallback weakness, paraphrase-induced template miss, and SQL-shape instability.",
            },
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
    metrics = report.get("metrics", {})
    lines = [
        "# NL-to-SQL Robustness Audit",
        "",
        "Diagnostic-only robustness audit for `SQL_FIRST_API_VERIFY` SQL planning. No packaged runtime promotion is made.",
        "",
        "Higher score is not considered meaningful unless robustness and generalization gates pass.",
        "",
        "## Metrics",
        "",
        f"- Template hit rate: `{metrics.get('template_hit_rate')}`",
        f"- Template miss rate: `{metrics.get('template_miss_rate')}`",
        f"- Fallback success rate: `{metrics.get('fallback_success_rate')}`",
        f"- SQL validation pass rate: `{metrics.get('sql_validation_pass_rate')}`",
        f"- SQL execution pass rate: `{metrics.get('sql_execution_pass_rate')}`",
        f"- Answer correctness proxy: `{metrics.get('answer_correctness_proxy')}`",
        f"- Route stability: `{metrics.get('route_stability')}`",
        f"- Table selection stability: `{metrics.get('table_selection_stability')}`",
        f"- Join selection stability: `{metrics.get('join_selection_stability')}`",
        f"- Count/count-distinct stability: `{metrics.get('count_count_distinct_stability')}`",
        f"- Paraphrase consistency score: `{metrics.get('paraphrase_consistency_score')}`",
        f"- Template dependency score: `{metrics.get('template_dependency_score')}`",
        "",
        "## Failure Distribution",
        "",
    ]
    for name, count in sorted((metrics.get("failure_distribution") or {}).items()):
        lines.append(f"- `{name}`: {count}")
    lines.extend(["", "## Most Unstable Groups", ""])
    groups = sorted(
        report.get("groups", []),
        key=lambda item: float(item.get("paraphrase_consistency_score") or 0.0),
    )[:20]
    for group in groups:
        unstable = [name for name, value in (group.get("instabilities") or {}).items() if value]
        lines.append(
            f"- `{group.get('prompt_id')}` [{group.get('source')}]: consistency `{group.get('paraphrase_consistency_score')}`, "
            f"instability={', '.join(unstable) if unstable else 'none'}"
        )
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
