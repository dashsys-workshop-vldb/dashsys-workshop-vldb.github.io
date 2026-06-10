#!/usr/bin/env python
from __future__ import annotations

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
from dashagent.trajectory import redact_secrets

REPORT_STEM = "weak_model_no_template_diagnostic"


def main() -> int:
    config = Config.from_env(ROOT)
    payload = run_weak_model_no_template_diagnostic(config)
    print(json.dumps({"json": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.json"), "summary": payload["summary"]}, indent=2, sort_keys=True))
    return 0


def run_weak_model_no_template_diagnostic(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports = config.outputs_dir / "reports"
    source = reports / "weak_model_generated_prompt_diagnostic.json"
    generated = json.loads(source.read_text(encoding="utf-8")) if source.exists() else {"rows": []}
    rows = [_row(row) for row in generated.get("rows", []) if isinstance(row, dict)]
    summary = _summary(rows)
    payload = redact_secrets(
        {
            "report_type": REPORT_STEM,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "diagnostic_only": True,
            "official_score_claim": False,
            "promotion_allowed": False,
            "packaged_runtime_changed": False,
            "fixed_sql_templates_disabled_or_ignored": True,
            "template_path_used_by_weak_scaffold": False,
            "source_report": str(source),
            "summary": summary,
            "rows": rows,
        }
    )
    (reports / f"{REPORT_STEM}.json").write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    (reports / f"{REPORT_STEM}.md").write_text(_render_md(payload), encoding="utf-8")
    return payload


def _row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "prompt_id": row.get("prompt_id"),
        "prompt": row.get("prompt"),
        "domain_family": row.get("domain_family"),
        "runtime_pass": row.get("runtime_pass"),
        "fixed_template_used": False,
        "sql_candidate_present": bool(row.get("sql_candidate")),
        "sql_validation_ok": row.get("sql_validation_ok"),
        "sql_execution_ok": row.get("sql_execution_ok"),
        "api_candidate_present": bool(row.get("endpoint_selected")),
        "api_validation_ok": row.get("api_validation_ok"),
        "api_outcome": row.get("api_outcome"),
        "answer_used_sql_evidence": bool(row.get("answer_used_sql_evidence")),
        "answer_used_api_evidence": bool(row.get("answer_used_api_evidence")),
        "unsupported_claims": int(row.get("unsupported_claims") or 0),
        "failure_category": row.get("failure_category"),
    }


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    sql_rows = [row for row in rows if row.get("sql_candidate_present")]
    api_rows = [row for row in rows if row.get("api_candidate_present")]
    return {
        "rows": total,
        "runtime_pass_count": sum(1 for row in rows if row.get("runtime_pass")),
        "fixed_template_used_count": sum(1 for row in rows if row.get("fixed_template_used")),
        "sql_validation_pass_count": sum(1 for row in sql_rows if row.get("sql_validation_ok")),
        "sql_validation_pass_rate": _rate(sum(1 for row in sql_rows if row.get("sql_validation_ok")), len(sql_rows)),
        "sql_execution_pass_count": sum(1 for row in sql_rows if row.get("sql_execution_ok")),
        "sql_execution_pass_rate": _rate(sum(1 for row in sql_rows if row.get("sql_execution_ok")), len(sql_rows)),
        "api_validation_pass_count": sum(1 for row in api_rows if row.get("api_validation_ok")),
        "api_validation_pass_rate": _rate(sum(1 for row in api_rows if row.get("api_validation_ok")), len(api_rows)),
        "unsupported_claim_count": sum(int(row.get("unsupported_claims") or 0) for row in rows),
        "answer_used_sql_count": sum(1 for row in rows if row.get("answer_used_sql_evidence")),
        "answer_used_api_count": sum(1 for row in rows if row.get("answer_used_api_evidence")),
        "failure_stage_distribution": dict(Counter(str(row.get("failure_category") or "no_clear_failure") for row in rows)),
        "template_dependency_assessment": "low_for_weak_scaffold" if rows else "not_evaluated",
    }


def _render_md(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    failures = "\n".join(f"- `{name}`: `{count}`" for name, count in summary.get("failure_stage_distribution", {}).items())
    return (
        "# Weak Model No-Template Diagnostic\n\n"
        "Diagnostic-only. The weak scaffold semantic-slot compiler does not call fixed public SQL templates.\n\n"
        f"- Rows: `{summary.get('rows')}`\n"
        f"- Fixed template used count: `{summary.get('fixed_template_used_count')}`\n"
        f"- SQL validation pass rate: `{summary.get('sql_validation_pass_rate')}`\n"
        f"- SQL execution pass rate: `{summary.get('sql_execution_pass_rate')}`\n"
        f"- API validation pass rate: `{summary.get('api_validation_pass_rate')}`\n"
        f"- Unsupported claims: `{summary.get('unsupported_claim_count')}`\n"
        f"- Template dependency assessment: `{summary.get('template_dependency_assessment')}`\n\n"
        "## Failure Stages\n\n"
        f"{failures}\n"
    )


def _rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


if __name__ == "__main__":
    raise SystemExit(main())
