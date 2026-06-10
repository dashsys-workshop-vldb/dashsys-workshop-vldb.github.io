#!/usr/bin/env python
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from scripts.robustness_improvement_common import counter_dict, load_json, now_iso, top_examples, write_report


REPORT_STEM = "no_template_sql_mode_diagnostic"


def main() -> int:
    config = Config.from_env(ROOT)
    report = run_no_template_sql_mode_diagnostic(config)
    print(json.dumps({"report": REPORT_STEM, "no_template_rows": report["no_template_rows"]}, indent=2))
    return 0


def run_no_template_sql_mode_diagnostic(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    robustness = load_json(config.outputs_dir / "reports" / "nl_sql_robustness_audit.json")
    rows = [row for row in robustness.get("rows", []) if isinstance(row, dict) and not row.get("template_hit")]
    sql_rows = [row for row in rows if row.get("generated_sql")]
    executed = [row for row in sql_rows if row.get("sql_execution_ok")]
    valid = [row for row in sql_rows if row.get("sql_validation_ok")]
    payload: dict[str, Any] = {
        "report_type": REPORT_STEM,
        "generated_at": now_iso(),
        "classification": "diagnostic_only",
        "official_score_claim": False,
        "promotion_allowed": False,
        "runtime_change_applied": False,
        "methodology": "Uses rows from nl_sql_robustness_audit where fixed template_hit=false. This is a no-template fallback diagnostic, not a packaged no-template runtime mode.",
        "no_template_rows": len(rows),
        "no_template_sql_rows": len(sql_rows),
        "sql_validation_pass_count": len(valid),
        "sql_validation_pass_rate": round(len(valid) / len(sql_rows), 4) if sql_rows else None,
        "sql_execution_pass_count": len(executed),
        "sql_execution_pass_rate": round(len(executed) / len(sql_rows), 4) if sql_rows else None,
        "fallback_success_rate": round(len(executed) / len(rows), 4) if rows else None,
        "failure_distribution": counter_dict(row.get("likely_failure") for row in rows),
        "route_distribution": counter_dict(row.get("route_type") for row in rows),
        "table_selection_distribution": counter_dict(",".join(row.get("selected_tables") or []) for row in rows),
        "join_count_distribution": counter_dict(row.get("join_count") for row in rows),
        "count_distinct_rows": sum(1 for row in rows if row.get("count_distinct")),
        "representative_examples": top_examples(rows),
        "promotion_gate": {
            "promotable": False,
            "reason": "Template-disabled behavior is not evaluated as packaged runtime; schema-aware fallback must pass separate strict and robustness gates before any promotion.",
        },
        "rows": rows,
    }
    write_report(config, REPORT_STEM, payload, _render_md(payload))
    return payload


def _render_md(report: dict[str, Any]) -> str:
    lines = [
        "# No-Template SQL Mode Diagnostic",
        "",
        "This report isolates robustness-audit rows where fixed SQL templates did not hit. It does not disable templates in packaged runtime.",
        "",
        f"- No-template rows: `{report.get('no_template_rows')}`",
        f"- SQL validation pass rate: `{report.get('sql_validation_pass_rate')}`",
        f"- SQL execution pass rate: `{report.get('sql_execution_pass_rate')}`",
        f"- Failure distribution: `{report.get('failure_distribution')}`",
        f"- Promotable: `{report.get('promotion_gate', {}).get('promotable')}`",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
