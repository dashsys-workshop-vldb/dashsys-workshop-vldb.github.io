from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from .trajectory import compact_preview, redact_secrets


def checkpoints_to_spans(trajectory: dict[str, Any]) -> dict[str, Any]:
    spans = []
    previous_id = None
    for index, checkpoint in enumerate(trajectory.get("checkpoints", []) or []):
        span_id = f"span_{index:03d}_{checkpoint.get('checkpoint_id', 'checkpoint')}"
        timestamp = checkpoint.get("timestamp")
        duration_ms = float(checkpoint.get("duration_ms", 0.0) or 0.0)
        ended_at = _ended_at(timestamp, duration_ms)
        spans.append(
            redact_secrets(
                {
                    "span_id": span_id,
                    "parent_id": previous_id,
                    "stage": checkpoint.get("stage"),
                    "technique": checkpoint.get("technique"),
                    "checkpoint_id": checkpoint.get("checkpoint_id"),
                    "started_at": timestamp,
                    "ended_at": ended_at,
                    "input_summary": compact_preview(checkpoint.get("input_summary"), 500),
                    "output_summary": compact_preview(checkpoint.get("output_summary") or checkpoint.get("output"), 500),
                    "correctness_role": checkpoint.get("correctness_role"),
                    "efficiency_role": checkpoint.get("efficiency_role"),
                    "visualization_label": _label(checkpoint),
                }
            )
        )
        previous_id = span_id
    return {
        "query_id": trajectory.get("query_id"),
        "strategy": trajectory.get("strategy") or trajectory.get("system"),
        "span_count": len(spans),
        "spans": spans,
    }


def research_technique_status(trajectory: dict[str, Any]) -> list[dict[str, Any]]:
    checkpoint_ids = {checkpoint.get("checkpoint_id") for checkpoint in trajectory.get("checkpoints", []) or []}
    rows = [
        ("SQLGlot AST validation", "SQLGlot", "checkpoint_sql_ast_validation", "AST SQL validation and table/column extraction"),
        ("Robust schema linking", "RSL-SQL", "checkpoint_schema_linking", "Bidirectional schema linking and bridge preservation"),
        ("Value/entity retrieval", "CHESS", "checkpoint_value_entity_retrieval", "Entity-value grounding from local DB samples"),
        ("Query decomposition", "DIN-SQL", "checkpoint_query_decomposition", "Complex-query decomposition into constraints"),
        ("Gated SQL candidates", "DIN-SQL / self-correction", "checkpoint_gated_sql_candidate_selection", "Hard-case candidate validation before one execution"),
        ("Query-family examples", "DAIL-SQL", "checkpoint_query_family_examples", "Optional family hints for LLM SQL"),
        ("Span export", "OpenAI Agents SDK tracing", "spans.json", "Local span-style checkpoint export"),
    ]
    return [
        {
            "technique": name,
            "source_inspiration": source,
            "active": checkpoint_id in checkpoint_ids or checkpoint_id == "spans.json",
            "visualization_checkpoint": checkpoint_id,
            "effect_on_dataflow": effect,
            "correctness_impact": _correctness_impact(name),
            "efficiency_impact": _efficiency_impact(name),
        }
        for name, source, checkpoint_id, effect in rows
    ]


def _ended_at(timestamp: str | None, duration_ms: float) -> str | None:
    if not timestamp:
        return None
    try:
        started = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        return (started + timedelta(milliseconds=duration_ms)).isoformat()
    except Exception:
        return None


def _label(checkpoint: dict[str, Any]) -> str:
    stage = checkpoint.get("stage") or "checkpoint"
    technique = checkpoint.get("technique") or checkpoint.get("checkpoint_id") or ""
    return f"{stage}: {technique}"[:120]


def _correctness_impact(name: str) -> str:
    if "SQLGlot" in name:
        return "detects schema/safety mismatches structurally"
    if "schema" in name:
        return "keeps relevant tables, columns, and bridges visible"
    if "Value" in name:
        return "grounds named entities and IDs before planning"
    if "decomposition" in name:
        return "preserves complex constraints"
    if "candidates" in name:
        return "prevents invalid hard-case SQL from being selected"
    return "makes technique visibility auditable"


def _efficiency_impact(name: str) -> str:
    if "Value" in name:
        return "bounded cached retrieval budget"
    if "candidates" in name:
        return "validates only; executes one selected plan"
    if "examples" in name:
        return "optional LLM-only token cost"
    return "diagnostic overhead only"
