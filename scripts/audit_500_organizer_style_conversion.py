#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.robustness_diagnostics_common import read_json, read_jsonl, write_json_md


def run_audit() -> dict[str, Any]:
    dataset = read_json(ROOT / "data" / "benchmarks" / "dashagent_500_organizer_style.json")
    manifest = read_json(ROOT / "data" / "benchmarks" / "dashagent_500_organizer_style_manifest.json")
    gold_rows = read_jsonl(ROOT / "data" / "benchmarks" / "dashagent_500_prompt_suite_gold.jsonl")
    examples = dataset.get("examples") if isinstance(dataset, dict) else []
    lost = manifest.get("lost_or_sidecar_fields") or {}
    strict_report = read_json(ROOT / "outputs" / "reports" / "dashagent_500_organizer_style_strict_comparison.json")
    rows = strict_report.get("rows") or []
    low_score_examples = [row for row in rows if row.get("baseline_final_score", 1) < 0.1][:20]
    report = {
        "report_type": "500_organizer_style_conversion_diagnostic",
        "converted_row_count": len(examples or []),
        "source_gold_row_count": len(gold_rows),
        "organizer_equivalent": False,
        "agent_visible_fields": manifest.get("agent_visible_fields") or ["id", "query"],
        "runtime_query_object_contains_category_tags": False,
        "gold_hidden_from_runtime": True,
        "strict_evaluator_fields_available": manifest.get("gold_fields_used_by_evaluator") or ["gold_sql", "gold_api", "answer"],
        "fields_lost_to_sidecar": lost,
        "fields_unavailable_to_strict_evaluator": sorted(lost),
        "endpoint_mapping_failures": manifest.get("endpoint_mapping_failures") or [],
        "gold_sql_api_compatibility": {
            "endpoint_mapping_failure_count": len(manifest.get("endpoint_mapping_failures") or []),
            "gold_sql_present_rows": sum(1 for row in examples or [] if row.get("gold_sql")),
            "gold_api_present_rows": sum(1 for row in examples or [] if row.get("gold_api")),
        },
        "absolute_score_low_reason": (
            "The converted dataset exposes only organizer-style gold_sql/gold_api/answer fields; "
            "required facts, forbidden claims, rubric points, and expected observable traces remain sidecar-only."
        ),
        "relative_comparison_validity": "useful stress evidence only; not organizer-equivalent",
        "low_score_examples": low_score_examples,
    }
    return report


def main() -> int:
    report = run_audit()
    lines = [
        "# 500 Organizer-Style Conversion Diagnostic",
        "",
        f"- Converted rows: `{report['converted_row_count']}`",
        f"- Organizer equivalent: `{str(report['organizer_equivalent']).lower()}`",
        f"- Agent-visible fields: `{report['agent_visible_fields']}`",
        f"- Fields lost to sidecar: `{report['fields_lost_to_sidecar']}`",
        "",
        report["absolute_score_low_reason"],
    ]
    write_json_md("500_organizer_style_conversion_diagnostic", report, lines)
    print(json.dumps({k: report[k] for k in ["converted_row_count", "organizer_equivalent", "fields_lost_to_sidecar"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
