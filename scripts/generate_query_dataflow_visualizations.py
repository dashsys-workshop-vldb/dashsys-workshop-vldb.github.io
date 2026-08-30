#!/usr/bin/env python
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.dataflow_visualizer import (  # noqa: E402
    attach_candidate_report_row,
    attach_compact_context_shadow_row,
    attach_risk_efficiency_shadow_row,
    attach_shadow_repair_row,
    build_dataflow_summary,
)
from visualization_report_helpers import (  # noqa: E402
    OUTPUTS_DIR,
    UNAVAILABLE,
    VIS_DIR,
    bool_status,
    compact,
    load_json,
    mermaid_block,
    mermaid_label,
    strict_row_by_query,
    table,
    write_json,
    write_md,
)


QUERY_IDS = ["example_000", "example_003", "example_011", "example_021", "example_031", "example_033"]


def main() -> int:
    generated: list[dict[str, str]] = []
    for query_id in QUERY_IDS:
        payload = build_query_visualization(query_id)
        md = build_markdown(payload)
        json_path = VIS_DIR / f"query_{query_id}_dataflow.json"
        md_path = VIS_DIR / f"query_{query_id}_dataflow.md"
        write_json(json_path, payload)
        write_md(md_path, md)
        generated.append({"query_id": query_id, "json": str(json_path), "markdown": str(md_path)})
    print({"generated": generated})
    return 0


def build_query_visualization(query_id: str) -> dict[str, Any]:
    trajectory_path = OUTPUTS_DIR / "eval" / query_id / "sql_first_api_verify" / "trajectory.json"
    trajectory = json.loads(trajectory_path.read_text(encoding="utf-8"))
    trajectory = enrich_trajectory(trajectory)
    summary = build_dataflow_summary(trajectory)
    strict_row = strict_row_by_query(query_id)
    checkpoints = build_checkpoint_timeline(trajectory)
    evidence = build_evidence_table(summary, query_id)
    decisions = build_decision_table(summary, query_id, trajectory)
    graph = build_query_graph(summary)
    return {
        "query_summary": {
            "query_id": query_id,
            "query": trajectory.get("original_query"),
            "current_packaged_strategy_used": trajectory.get("strategy"),
            "final_answer": trajectory.get("final_answer"),
            "strict_score": strict_row.get("final_score", UNAVAILABLE),
            "correctness_score": strict_row.get("correctness_score", UNAVAILABLE),
            "answer_score": strict_row.get("answer_score", UNAVAILABLE),
            "sql_score": strict_row.get("sql_score", UNAVAILABLE),
            "api_score": strict_row.get("api_score", UNAVAILABLE),
            "tool_calls": trajectory.get("tool_call_count"),
            "tokens": trajectory.get("estimated_tokens"),
            "runtime": trajectory.get("runtime"),
        },
        "checkpoint_timeline": checkpoints,
        "mermaid_dataflow_graph": graph,
        "evidence_table": evidence,
        "decision_table": decisions,
        "source_trajectory": str(trajectory_path),
    }


def enrich_trajectory(trajectory: dict[str, Any]) -> dict[str, Any]:
    trajectory = attach_candidate_report_row(trajectory, OUTPUTS_DIR)
    trajectory = attach_shadow_repair_row(trajectory, OUTPUTS_DIR)
    trajectory = attach_compact_context_shadow_row(trajectory, OUTPUTS_DIR)
    trajectory = attach_risk_efficiency_shadow_row(trajectory, OUTPUTS_DIR)
    return trajectory


def build_checkpoint_timeline(trajectory: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, checkpoint in enumerate(trajectory.get("checkpoints", []) or [], start=1):
        technique = checkpoint.get("technique") or UNAVAILABLE
        stage = checkpoint.get("stage") or infer_stage(str(checkpoint.get("checkpoint_id") or ""), str(technique))
        correctness_role = checkpoint.get("correctness_role")
        efficiency_role = checkpoint.get("efficiency_role")
        safety_role = checkpoint.get("safety_role") or ("validation" if "validation" in str(technique).lower() else None)
        rows.append(
            {
                "checkpoint_order": index,
                "checkpoint_id": checkpoint.get("checkpoint_id") or f"checkpoint_{index:02d}",
                "stage": stage,
                "technique": technique,
                "short_input_summary": concise_value(checkpoint.get("input_summary") or checkpoint.get("input")),
                "short_output_summary": concise_value(checkpoint.get("output")),
                "what_changed": checkpoint.get("effect") or infer_change(stage, technique, checkpoint),
                "affects_accuracy": bool_status(bool(correctness_role)),
                "affects_efficiency": bool_status(bool(efficiency_role)),
                "affects_safety": bool_status(bool(safety_role)),
            }
        )
    return rows


def concise_value(value: Any, max_chars: int = 180) -> str:
    """Summarize nested checkpoint payloads without dropping raw JSON blobs into Markdown."""
    if value in (None, "", [], {}):
        return UNAVAILABLE
    if isinstance(value, str):
        parsed = try_parse_jsonish(value)
        if parsed is not None:
            return concise_value(parsed, max_chars=max_chars)
        return value[: max_chars - 3].rstrip() + "..." if len(value) > max_chars else value
    if isinstance(value, list):
        if not value:
            return UNAVAILABLE
        head = ", ".join(concise_value(item, 60) for item in value[:3])
        suffix = f"; +{len(value) - 3} more" if len(value) > 3 else ""
        return f"{len(value)} item(s): {head}{suffix}"
    if isinstance(value, dict):
        if set(value.keys()) == {"preview"} and isinstance(value.get("preview"), str):
            parsed = try_parse_jsonish(value["preview"])
            return concise_value(parsed if parsed is not None else value["preview"], max_chars=max_chars)
        priority_keys = [
            "query",
            "query_id",
            "strategy",
            "route_type",
            "domain_type",
            "answer_family",
            "lookup_path",
            "confidence",
            "is_simple",
            "suggested_action",
            "reason",
            "base_step_count",
            "optimized_step_count",
            "planned_sql_calls",
            "planned_api_calls",
            "final_planned_calls",
            "max_total_tool_calls",
            "sql_calls_executed",
            "api_calls_executed",
            "verifier_passed",
            "rewrite_applied",
            "candidate_count",
            "selected_candidate_type",
            "answer_length",
            "final_answer",
        ]
        parts: list[str] = []
        for key in priority_keys:
            if key in value and value[key] not in (None, "", [], {}):
                parts.append(f"{key}={scalar_summary(value[key])}")
            if len(parts) >= 4:
                break
        if not parts:
            for key, item in value.items():
                if item in (None, "", [], {}):
                    continue
                parts.append(f"{key}={scalar_summary(item)}")
                if len(parts) >= 4:
                    break
        text = "; ".join(parts) if parts else compact(value, max_chars)
        return text[: max_chars - 3].rstrip() + "..." if len(text) > max_chars else text
    text = str(value)
    return text[: max_chars - 3].rstrip() + "..." if len(text) > max_chars else text


def scalar_summary(value: Any) -> str:
    if isinstance(value, dict):
        if "items" in value and "total_items" in value:
            return f"{value.get('total_items')} item(s)"
        if "preview" in value:
            return concise_value(value.get("preview"), 60)
        return f"{len(value)} field(s)"
    if isinstance(value, list):
        preview = ", ".join(str(item) for item in value[:2])
        return f"{len(value)} item(s)" + (f" [{preview}]" if preview else "")
    text = str(value)
    return text[:57].rstrip() + "..." if len(text) > 60 else text


def try_parse_jsonish(value: str) -> Any | None:
    text = value.strip()
    if not ((text.startswith("{") and text.endswith("}")) or (text.startswith("[") and text.endswith("]"))):
        return None
    try:
        return json.loads(text)
    except Exception:
        return None


def infer_stage(checkpoint_id: str, technique: str) -> str:
    text = f"{checkpoint_id} {technique}".lower()
    if "route" in text:
        return "routing"
    if "token" in text or "normal" in text:
        return "query understanding"
    if "metadata" in text or "context" in text or "candidate" in text:
        return "context selection"
    if "sql" in text:
        return "SQL planning/execution"
    if "api" in text or "endpoint" in text:
        return "API planning/execution"
    if "answer" in text:
        return "answer synthesis"
    if "validation" in text or "verif" in text:
        return "validation"
    return "pipeline"


def infer_change(stage: str, technique: Any, checkpoint: dict[str, Any]) -> str:
    output = checkpoint.get("output")
    if output not in (None, {}, []):
        return f"Recorded {stage} output for {technique}."
    return f"Checkpoint recorded {stage} progress."


def build_evidence_table(summary: dict[str, Any], query_id: str) -> list[dict[str, Any]]:
    local_row = find_report_row("outputs/local_index_fact_coverage_report.json", query_id)
    supportable_row = find_report_row("outputs/supportable_answer_rewrite_eval.json", query_id)
    evidence = summary.get("evidence", {})
    return [
        {
            "evidence_type": "SQL evidence",
            "used_or_status": bool_status(evidence.get("sql_evidence_available")),
            "source": summary.get("sql", {}).get("preview", UNAVAILABLE),
            "preview": summary.get("sql", {}).get("result_preview", UNAVAILABLE),
        },
        {
            "evidence_type": "API evidence",
            "used_or_status": "dry-run" if evidence.get("dry_run_only") else bool_status(evidence.get("live_api_evidence_available")),
            "source": summary.get("api", {}).get("endpoint", UNAVAILABLE),
            "preview": summary.get("api", {}).get("result_preview", UNAVAILABLE),
        },
        {
            "evidence_type": "Local Parquet evidence",
            "used_or_status": bool_status(local_row.get("local_evidence_used_in_final_answer") or local_row.get("local_evidence_used_in_final_answer_row")),
            "source": local_row.get("source_table", UNAVAILABLE) if local_row else UNAVAILABLE,
            "preview": concise_value(local_row) if local_row else UNAVAILABLE,
        },
        {
            "evidence_type": "Dry-run label",
            "used_or_status": bool_status(evidence.get("dry_run_only")),
            "source": "API dry-run result label",
            "preview": evidence.get("explanation", UNAVAILABLE),
        },
        {
            "evidence_type": "Unsupported claims replaced",
            "used_or_status": bool_status(bool(supportable_row.get("unsupported_claims_replaced"))),
            "source": "supportable_answer_rewrite_eval",
            "preview": supportable_row.get("unsupported_claims_replaced", UNAVAILABLE) if supportable_row else UNAVAILABLE,
        },
    ]


def build_decision_table(summary: dict[str, Any], query_id: str, trajectory: dict[str, Any]) -> list[dict[str, Any]]:
    endpoint_tie = find_report_row("outputs/endpoint_family_tiebreak_v2_shadow.json", query_id)
    answer_shape = find_report_row("outputs/answer_shape_v2_ab_eval.json", query_id)
    supportable = find_report_row("outputs/supportable_answer_rewrite_eval.json", query_id)
    auto_trial = find_report_row("outputs/autonomous_packaged_trial.json", query_id)
    execution = summary.get("execution", {})
    route = summary.get("route", {})
    return [
        {
            "decision": "Why SQL was used",
            "selected_value": f"SQL calls={execution.get('execute_sql_calls', UNAVAILABLE)}",
            "reason": route.get("mode", trajectory.get("route_type", UNAVAILABLE)),
            "promotion_status": "promoted_default",
        },
        {
            "decision": "Why API was used or skipped",
            "selected_value": f"API calls={execution.get('call_api_calls', UNAVAILABLE)}; dry_run={summary.get('api', {}).get('dry_run', UNAVAILABLE)}",
            "reason": route.get("api_policy", UNAVAILABLE),
            "promotion_status": "promoted_default",
        },
        {
            "decision": "Answer template / rewriter",
            "selected_value": "packaged answer synthesizer",
            "reason": supportable.get("selection_reason") or answer_shape.get("selection_reason") or "No default-on answer rewrite promoted.",
            "promotion_status": "promoted_default + shadow_only diagnostics",
        },
        {
            "decision": "Endpoint family changed?",
            "selected_value": endpoint_tie.get("changed_endpoint_decision", endpoint_tie.get("selected_family_after", UNAVAILABLE)) if endpoint_tie else UNAVAILABLE,
            "reason": endpoint_tie.get("rejection_reason", "No endpoint-family tie-break v2 promotion.") if endpoint_tie else "No shadow row for this query.",
            "promotion_status": "shadow_only",
        },
        {
            "decision": "Candidate promoted?",
            "selected_value": auto_trial.get("selected_candidate_id", answer_shape.get("candidate_id", UNAVAILABLE)) if (auto_trial or answer_shape) else UNAVAILABLE,
            "reason": auto_trial.get("selection_reason", "Packaged system remains current safe default.") if auto_trial else "No promoted candidate for packaged path.",
            "promotion_status": "shadow_only / isolated_trial",
        },
    ]


def find_report_row(relative_path: str, query_id: str) -> dict[str, Any]:
    report = load_json(relative_path, {})
    for row in report.get("rows", []) if isinstance(report, dict) else []:
        if row.get("query_id") == query_id:
            return row
    return {}


def build_query_graph(summary: dict[str, Any]) -> str:
    query = mermaid_label(summary.get("user_query"), 44)
    route = mermaid_label(summary.get("route", {}).get("mode"), 28)
    tables = mermaid_label(summary.get("context", {}).get("candidate_tables"), 42)
    apis = mermaid_label(summary.get("context", {}).get("candidate_apis"), 42)
    sql = "SQL rows" if summary.get("evidence", {}).get("sql_evidence_available") else "No SQL evidence"
    api = "Dry-run API" if summary.get("evidence", {}).get("dry_run_only") else "Live/API evidence"
    answer = mermaid_label(summary.get("answer", {}).get("final_answer_preview"), 42)
    return f"""
flowchart LR
  Q["Raw query: {query}"] --> N["Normalize + tokens"]
  N --> R["Route: {route}"]
  R --> C["Context tables: {tables}"]
  C --> P["Plan SQL/API"]
  P --> S["{sql}"]
  P --> A["API candidates: {apis}"]
  A --> E["{api}"]
  S --> V["Evidence bus"]
  E --> V
  V --> H["Answer synthesis"]
  H --> F["Final: {answer}"]
"""


def build_markdown(payload: dict[str, Any]) -> str:
    summary = payload["query_summary"]
    checkpoint_rows = [
        [
            row["checkpoint_order"],
            row["checkpoint_id"],
            row["stage"],
            row["technique"],
            row["short_input_summary"],
            row["short_output_summary"],
            row["what_changed"],
            row["affects_accuracy"],
            row["affects_efficiency"],
            row["affects_safety"],
        ]
        for row in payload["checkpoint_timeline"]
    ]
    evidence_rows = [
        [row["evidence_type"], row["used_or_status"], row["source"], row["preview"]]
        for row in payload["evidence_table"]
    ]
    decision_rows = [
        [row["decision"], row["selected_value"], row["reason"], row["promotion_status"]]
        for row in payload["decision_table"]
    ]
    return "\n".join(
        [
            f"# Query Dataflow: {summary['query_id']}",
            "",
            "## Query Summary",
            "",
            table(
                ["Field", "Value"],
                [
                    ["Query", summary["query"]],
                    ["Current packaged strategy", summary["current_packaged_strategy_used"]],
                    ["Final answer", summary["final_answer"]],
                    ["Strict score", summary["strict_score"]],
                    ["Correctness score", summary["correctness_score"]],
                    ["Answer / SQL / API score", f"{summary['answer_score']} / {summary['sql_score']} / {summary['api_score']}"],
                    ["Tools / tokens / runtime", f"{summary['tool_calls']} / {summary['tokens']} / {summary['runtime']}"],
                ],
            ),
            "",
            "## Dataflow Graph",
            "",
            mermaid_block(payload["mermaid_dataflow_graph"]),
            "",
            "## Checkpoint Timeline",
            "",
            table(["#", "Checkpoint", "Stage", "Technique", "Input", "Output", "What changed", "Accuracy", "Efficiency", "Safety"], checkpoint_rows),
            "",
            "## Evidence Table",
            "",
            table(["Evidence", "Used/status", "Source", "Preview"], evidence_rows),
            "",
            "## Decision Table",
            "",
            table(["Decision", "Selected value", "Reason", "Promotion status"], decision_rows),
            "",
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())
