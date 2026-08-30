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
from dashagent.executor import AgentExecutor
from dashagent.repair_candidate_selector_v3 import select_repair_candidate_v3
from dashagent.report_run import report_metadata
from dashagent.sql_ast_candidate_ranker import rank_sql_candidate_ast
from scripts.run_official_token_reduction_eval import _avg, _load_json


def main() -> int:
    config = Config.from_env(ROOT)
    payload = run_repair_selector_v3_shadow_eval(config)
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    json_path = config.outputs_dir / "repair_selector_v3_shadow_eval.json"
    md_path = config.outputs_dir / "repair_selector_v3_shadow_eval.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "rows": len(payload["rows"])}, indent=2, sort_keys=True))
    return 0


def run_repair_selector_v3_shadow_eval(config: Config) -> dict[str, Any]:
    if config.enable_gated_risk_cluster_repair_execution:
        raise RuntimeError("Repair selector v3 shadow eval refuses to run with repair execution enabled.")
    shadow = _load_json(config.outputs_dir / "shadow_repair_eval.json")
    ast_canary = _load_json(config.outputs_dir / "ast_guided_sql_candidate_canary.json")
    ast_by_id = {str(row.get("query_id")): row for row in ast_canary.get("rows", []) or []}
    executor = AgentExecutor(config)
    rows = []
    for row in shadow.get("rows", []) or []:
        query_id = str(row.get("query_id") or "")
        current_sql = (row.get("current_plan_sql") or [""])[0] if row.get("current_plan_sql") else ""
        repaired_sql = (row.get("repaired_plan_sql") or [""])[0] if row.get("repaired_plan_sql") else current_sql
        current_plan = {
            "sql": row.get("current_plan_sql") or [],
            "api_calls": row.get("current_plan_api") or [],
            "tool_call_count": row.get("current_tool_calls"),
            "expected_answer_shape": "unknown",
            "final_answer": row.get("current_final_answer"),
        }
        repaired_plan = {
            "sql": row.get("repaired_plan_sql") or [],
            "api_calls": row.get("repaired_plan_api") or [],
            "tool_call_count": row.get("repaired_tool_calls"),
            "expected_answer_shape": "unknown",
            "final_answer": row.get("repaired_final_answer"),
            "fusion_agreement": not _has_failed(row, "fusion_agreement"),
            "endpoint_family_confidence": _endpoint_confidence(row),
            "schema_family_confidence": 1.0,
            "offline_score_delta": row.get("offline_score_delta", row.get("score_delta")),
            "dry_run_labels_preserved": True,
            "live_api_evidence_fabricated": False,
        }
        ast_row = ast_by_id.get(query_id, {})
        ast_guided_plan = {
            "sql": [ast_row.get("candidate_sql") or current_sql],
            "api_calls": row.get("current_plan_api") or [],
            "tool_call_count": row.get("current_tool_calls"),
            "expected_answer_shape": "unknown",
            "final_answer": row.get("current_final_answer"),
            "fusion_agreement": True,
            "endpoint_family_confidence": 1.0,
            "schema_family_confidence": 1.0,
            "offline_score_delta": 0.0,
            "dry_run_labels_preserved": True,
            "live_api_evidence_fabricated": False,
        } if ast_row else None
        ast_current = rank_sql_candidate_ast(current_sql, executor.schema_index, query=row.get("query") or "")
        ast_repaired = rank_sql_candidate_ast(repaired_sql, executor.schema_index, query=row.get("query") or "")
        ast_guided = rank_sql_candidate_ast((ast_guided_plan or {}).get("sql", [""])[0], executor.schema_index, query=row.get("query") or "") if ast_guided_plan else None
        selection = select_repair_candidate_v3(
            current_plan,
            repaired_plan,
            ast_guided_plan,
            row.get("safety_verdict") or {},
            ast_current=ast_current,
            ast_repaired=ast_repaired,
            ast_guided=ast_guided,
        )
        selected_delta = _selected_delta(selection)
        rows.append(
            {
                "query_id": query_id,
                "query": row.get("query"),
                "risk_cluster": row.get("risk_cluster"),
                "score_delta": row.get("score_delta"),
                "tool_delta": row.get("tool_delta"),
                "current_ast_quality_score": ast_current.get("ast_quality_score"),
                "repaired_ast_quality_score": ast_repaired.get("ast_quality_score"),
                "ast_guided_ast_quality_score": (ast_guided or {}).get("ast_quality_score"),
                "selector_v3": selection,
                "selected_plan": selection.get("selected_plan"),
                "decision_label": selection.get("decision_label"),
                "selected_score_delta": selected_delta,
                "repair_execution_enabled": False,
                "execution_changed": False,
            }
        )
    selected = [row for row in rows if row["selector_v3"].get("safe_to_select_alternative")]
    selected_worse = [row for row in selected if float(row.get("selected_score_delta") or 0.0) < 0]
    better = [row for row in selected if float(row.get("selected_score_delta") or 0.0) > 0]
    summary = {
        "total_rows": len(rows),
        "repaired_worse_count": sum(1 for row in rows if float(row.get("score_delta") or 0.0) < 0),
        "selected_repaired_worse_count": len(selected_worse),
        "safe_repaired_worse_count": len(selected_worse),
        "strictly_better_selected_count": len(better),
        "avg_safe_score_delta": _avg(row.get("selected_score_delta") for row in selected),
        "avg_tool_delta": _avg(row.get("tool_delta") for row in selected),
        "no_op_tie_keep_current_count": sum(1 for row in rows if row.get("decision_label") == "no_op_tie_keep_current"),
        "score_tie_keep_current_count": sum(1 for row in rows if row.get("decision_label") == "score_tie_keep_current"),
        "success": len(selected_worse) == 0 and len(better) > 0 and _avg(row.get("selected_score_delta") for row in selected) >= 0 and _avg(row.get("tool_delta") for row in selected) <= 0,
        "repair_execution_enabled": False,
    }
    return {
        **report_metadata(config.outputs_dir),
        "mode": "repair_selector_v3_shadow_eval",
        "report_only": True,
        "packaged_execution_changed": False,
        "summary": summary,
        "rows": rows,
        "notes": ["Selector v3 is shadow-only and is not wired into packaged execution."],
    }


def _selected_delta(selection: dict[str, Any]) -> float:
    selected = selection.get("selected_plan")
    for item in selection.get("alternative_decisions") or []:
        if item.get("name") == selected:
            return float(item.get("score_delta") or 0.0)
    return 0.0


def _has_failed(row: dict[str, Any], check: str) -> bool:
    return check in (row.get("safety_verdict") or {}).get("failed_checks", []) or check in (row.get("repair_candidate_selector") or {}).get("failed_checks", [])


def _endpoint_confidence(row: dict[str, Any]) -> float:
    selector_reason = " ".join((row.get("repair_candidate_selector") or {}).get("reasons", []))
    return 0.0 if "Endpoint family confidence" in selector_reason else 1.0


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Repair Selector V3 Shadow Eval",
        "",
        f"- Success: {summary['success']}",
        f"- Strictly better selected count: {summary['strictly_better_selected_count']}",
        f"- Selected repaired worse count: {summary['selected_repaired_worse_count']}",
        f"- Safe repaired worse count: {summary['safe_repaired_worse_count']}",
        "",
        "| Query ID | Cluster | Score delta | Selected | Decision | Failed checks |",
        "| --- | --- | ---: | --- | --- | --- |",
    ]
    for row in payload["rows"]:
        selector = row["selector_v3"]
        lines.append(
            f"| `{row['query_id']}` | {row['risk_cluster']} | {row['score_delta']} | "
            f"{selector.get('selected_plan')} | {selector.get('decision_label')} | {', '.join(selector.get('failed_checks') or [])} |"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
