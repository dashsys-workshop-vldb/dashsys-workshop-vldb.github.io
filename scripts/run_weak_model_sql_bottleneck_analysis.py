#!/usr/bin/env python
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.nlp_generalization_layer import domain_to_table
from dashagent.trajectory import redact_secrets

REPORT_STEM = "weak_model_sql_bottleneck_analysis"
DEFAULT_VARIANT = "weak_scaffold_api_recovery_v1"


def main() -> int:
    config = Config.from_env(ROOT)
    payload = run_weak_model_sql_bottleneck_analysis(config)
    print(json.dumps({"json": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.json"), "summary": payload["summary"]}, indent=2, sort_keys=True))
    return 0


def run_weak_model_sql_bottleneck_analysis(config: Config | None = None, *, variant: str = DEFAULT_VARIANT) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports = config.outputs_dir / "reports"
    source = reports / "weak_model_lift_eval_public_dev_full.json"
    if not source.exists():
        source = reports / "weak_model_lift_eval.json"
    payload = json.loads(source.read_text(encoding="utf-8")) if source.exists() else {"rows": []}
    rows = [_analyze_row(row) for row in payload.get("rows", []) if row.get("mode") == variant and row.get("sql_score") is not None]
    summary = _summary(rows)
    report = redact_secrets(
        {
            "report_type": REPORT_STEM,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "diagnostic_only": True,
            "official_score_claim": False,
            "promotion_allowed": False,
            "packaged_runtime_changed": False,
            "variant": variant,
            "source_report": str(source),
            "summary": summary,
            "rows": rows,
        }
    )
    (reports / f"{REPORT_STEM}.json").write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    (reports / f"{REPORT_STEM}.md").write_text(_render_md(report), encoding="utf-8")
    return report


def _analyze_row(row: dict[str, Any]) -> dict[str, Any]:
    trajectory = row.get("trajectory") if isinstance(row.get("trajectory"), dict) else {}
    steps = trajectory.get("steps", []) if isinstance(trajectory.get("steps"), list) else []
    slot_step = next((step for step in steps if step.get("kind") == "semantic_slots"), {})
    compiler_step = next((step for step in steps if step.get("kind") == "slot_compiler"), {})
    sql_step = next((step for step in steps if step.get("kind") == "sql_call"), {})
    final_step = next((step for step in steps if step.get("kind") == "final_answer"), {})
    slots = slot_step.get("slots") if isinstance(slot_step.get("slots"), dict) else {}
    compiled = compiler_step.get("compiled") if isinstance(compiler_step.get("compiled"), dict) else {}
    sql_candidate = (compiled.get("sql_candidates") or [{}])[0] if isinstance(compiled.get("sql_candidates"), list) else {}
    plan = sql_candidate.get("structured_sql_plan") if isinstance(sql_candidate.get("structured_sql_plan"), dict) else {}
    grounding = final_step.get("grounding") if isinstance(final_step.get("grounding"), dict) else {}
    sql = sql_step.get("sql") or sql_candidate.get("sql")
    analyzed = {
        "query_id": row.get("query_id"),
        "prompt": row.get("prompt"),
        "semantic_slots": slots,
        "compiled_sql": sql,
        "selected_table": plan.get("primary_table"),
        "selected_columns": plan.get("columns_needed"),
        "filters": plan.get("filters"),
        "aggregation": plan.get("aggregation"),
        "join_path": (sql_candidate.get("compiled") or {}).get("join_path") if isinstance(sql_candidate.get("compiled"), dict) else None,
        "sql_validation_ok": _validation_ok(sql_step.get("validation") or sql_candidate.get("validation")),
        "sql_execution_ok": isinstance(sql_step.get("result"), dict) and not bool((sql_step.get("result") or {}).get("error")),
        "sql_score": row.get("sql_score"),
        "answer_score": row.get("answer_score"),
        "answer_used_sql_evidence": bool(grounding.get("answer_used_sql")),
        "final_answer": row.get("trajectory", {}).get("final_answer") if isinstance(row.get("trajectory"), dict) else None,
    }
    analyzed["failure_category"] = classify_sql_bottleneck(analyzed)
    return redact_secrets(analyzed)


def classify_sql_bottleneck(row: dict[str, Any]) -> str:
    score = _num(row.get("sql_score"))
    if score >= 0.8:
        if row.get("compiled_sql") and not row.get("answer_used_sql_evidence"):
            return "SQL_result_not_used"
        return "no_clear_sql_failure"
    slots = row.get("semantic_slots") if isinstance(row.get("semantic_slots"), dict) else {}
    intent = str(slots.get("intent") or "").upper()
    domain = str(slots.get("domain") or "").upper()
    if not row.get("compiled_sql"):
        return "no_sql_when_needed"
    if not row.get("sql_validation_ok"):
        return "SQL_valid_but_wrong_semantics"
    expected_table = domain_to_table(domain)
    if expected_table and row.get("selected_table") and row.get("selected_table") != expected_table:
        return "wrong_table"
    if intent == "COUNT" and "count(" not in str(row.get("compiled_sql") or "").lower():
        return "wrong_aggregation"
    if _quoted_entity(str(row.get("prompt") or "")) and not row.get("filters"):
        return "missing_filter"
    if intent == "RELATIONSHIP" and " join " not in str(row.get("compiled_sql") or "").lower():
        return "wrong_join"
    if _wrong_columns_for_intent(intent, row.get("selected_columns") or []):
        return "wrong_columns"
    if row.get("compiled_sql") and not row.get("answer_used_sql_evidence"):
        return "SQL_result_not_used"
    return "SQL_valid_but_wrong_semantics"


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    failures = Counter(str(row.get("failure_category") or "no_clear_sql_failure") for row in rows)
    low_score_rows = [row for row in rows if _num(row.get("sql_score")) < 0.8]
    dominant = failures.most_common(1)[0][0] if failures else "none"
    return {
        "rows": len(rows),
        "low_sql_score_rows": len(low_score_rows),
        "average_sql_score": round(sum(_num(row.get("sql_score")) for row in rows) / len(rows), 4) if rows else 0.0,
        "failure_distribution": dict(failures),
        "dominant_sql_bottleneck": dominant,
        "fix_layer_recommendation": _fix_layer(dominant),
        "safe_next_sql_improvement_candidate": _safe_next_candidate(dominant),
    }


def _render_md(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    failures = "\n".join(f"- `{name}`: `{count}`" for name, count in summary.get("failure_distribution", {}).items())
    examples = "\n".join(f"- `{row.get('query_id')}`: `{row.get('failure_category')}` SQL `{row.get('sql_score')}`" for row in payload.get("rows", [])[:12])
    return (
        "# Weak Model SQL Bottleneck Analysis\n\n"
        "Diagnostic-only analysis of weak scaffold SQL failures. No runtime promotion.\n\n"
        f"- Variant: `{payload.get('variant')}`\n"
        f"- Rows with SQL score: `{summary.get('rows')}`\n"
        f"- Average SQL score: `{summary.get('average_sql_score')}`\n"
        f"- Dominant SQL bottleneck: `{summary.get('dominant_sql_bottleneck')}`\n"
        f"- Fix layer: `{summary.get('fix_layer_recommendation')}`\n"
        f"- Safe next candidate: `{summary.get('safe_next_sql_improvement_candidate')}`\n\n"
        "## Failure Distribution\n\n"
        f"{failures}\n\n"
        "## Examples\n\n"
        f"{examples}\n"
    )


def _validation_ok(validation: Any) -> bool | None:
    if not isinstance(validation, dict):
        return None
    if "ok" in validation:
        return bool(validation.get("ok"))
    if "valid" in validation:
        return bool(validation.get("valid"))
    return None


def _quoted_entity(prompt: str) -> bool:
    return bool(re.search(r"['\"][^'\"]+['\"]", prompt))


def _wrong_columns_for_intent(intent: str, columns: list[Any]) -> bool:
    text = " ".join(str(column).lower() for column in columns)
    if intent == "DATE":
        return not any(marker in text for marker in ("time", "date", "created", "updated", "published", "deployed", "modified"))
    if intent == "STATUS":
        return not any(marker in text for marker in ("status", "state"))
    if intent == "LIST":
        return not any(marker in text for marker in ("id", "name", "title", "display"))
    return False


def _fix_layer(dominant: str) -> str:
    if dominant in {"wrong_table", "wrong_columns", "wrong_aggregation", "missing_filter", "wrong_join"}:
        return "slot_extraction_and_semantic_slot_compiler"
    if dominant == "no_sql_when_needed":
        return "evidence_need_planner_and_compiler_candidate_generation"
    if dominant == "SQL_result_not_used":
        return "answer_grounding"
    return "semantic_sql_ranking_or_schema_retrieval"


def _safe_next_candidate(dominant: str) -> str:
    mapping = {
        "wrong_table": "strengthen domain-to-table ranking using schema aliases",
        "wrong_columns": "add role-aware column ranking for weak slots",
        "wrong_aggregation": "tighten COUNT/count_distinct slot normalization",
        "missing_filter": "link quoted entities to name/title/display filters before compilation",
        "wrong_join": "add join-path slot support using known schema hints",
        "no_sql_when_needed": "repair evidence_need classification for local SQL-answerable prompts",
        "SQL_result_not_used": "tighten SQL evidence answer fallback",
    }
    return mapping.get(dominant, "add semantic SQL candidate ranking before execution")


def _num(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


if __name__ == "__main__":
    raise SystemExit(main())
