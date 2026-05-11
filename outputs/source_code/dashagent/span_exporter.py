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
                    "span_kind": _span_kind(checkpoint),
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
    candidate_row = trajectory.get("_candidate_context_report_row") or {}
    shadow_row = trajectory.get("_shadow_repair_eval_row") or {}
    compact_shadow_row = trajectory.get("_compact_context_shadow_eval_row") or {}
    risk_shadow_row = trajectory.get("_risk_efficiency_shadow_eval_row") or {}
    for technique, checkpoint_id, output_key in [
        ("Hybrid Candidate Scoring", "checkpoint_hybrid_candidate_scoring", "hybrid_candidate_scoring"),
        ("Endpoint Family Ranking", "checkpoint_endpoint_family_ranking", "endpoint_family_ranking"),
        ("Structural Schema Preservation", "checkpoint_structural_schema_preservation", "schema_linking"),
        ("Value-to-API Ranking", "checkpoint_value_to_api_ranking", "value_to_api_ranking"),
        ("Gated Risk Cluster Repair", "checkpoint_gated_risk_cluster_repair", "gated_risk_cluster_repair"),
        ("Risk-Based Efficiency Controller", "checkpoint_risk_efficiency_controller", "risk_efficiency_controller"),
        ("Schema Context Voting", "checkpoint_schema_context_voting", "schema_context_vote"),
    ]:
        payload = candidate_row.get(output_key) or shadow_row.get(output_key)
        if not payload:
            continue
        span_id = f"span_{len(spans):03d}_{checkpoint_id}"
        spans.append(
            redact_secrets(
                {
                    "span_id": span_id,
                    "parent_id": previous_id,
                    "stage": "candidate retrieval diagnostics",
                    "technique": technique,
                    "checkpoint_id": checkpoint_id,
                    "span_kind": checkpoint_id.removeprefix("checkpoint_") + "_span",
                    "started_at": None,
                    "ended_at": None,
                    "input_summary": "candidate_context_report row",
                    "output_summary": compact_preview(payload, 500),
                    "correctness_role": "improves retrieval diagnostics without changing SQL_FIRST execution",
                    "efficiency_role": "report-only ranking; no extra tool calls",
                    "visualization_label": technique,
                }
            )
        )
        previous_id = span_id
    for technique, checkpoint_id, payload in [
        ("Compact Context Shadow Eval", "checkpoint_compact_context_shadow_eval", compact_shadow_row),
        ("Risk-Efficiency Shadow Eval", "checkpoint_risk_efficiency_shadow_eval", risk_shadow_row),
    ]:
        if not payload:
            continue
        span_id = f"span_{len(spans):03d}_{checkpoint_id}"
        spans.append(
            redact_secrets(
                {
                    "span_id": span_id,
                    "parent_id": previous_id,
                    "stage": "shadow diagnostics",
                    "technique": technique,
                    "checkpoint_id": checkpoint_id,
                    "span_kind": checkpoint_id.removeprefix("checkpoint_") + "_span",
                    "started_at": None,
                    "ended_at": None,
                    "input_summary": "shadow replay report row",
                    "output_summary": compact_preview(payload, 500),
                    "correctness_role": "replays current SQL_FIRST outputs without claiming accuracy improvement",
                    "efficiency_role": "reports estimated deltas only; packaged execution unchanged",
                    "visualization_label": technique,
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
        ("Hybrid candidate scoring", "Blended RAG / rank fusion", "checkpoint_hybrid_candidate_scoring", "Report-only candidate separation scoring"),
        ("Endpoint family ranking", "Domain-aware retrieval", "checkpoint_endpoint_family_ranking", "Report-only endpoint family reranking"),
        ("Structural schema preservation", "RSL-SQL", "checkpoint_structural_schema_preservation", "Report-only bridge/relationship preservation diagnostics"),
        ("Value-to-API ranking", "CHESS", "checkpoint_value_to_api_ranking", "High-confidence entity matches can boost API-family ranking in reports"),
        ("Gated risk-cluster repair", "CHASE-SQL-style repair", "checkpoint_gated_risk_cluster_repair", "Diagnostic repaired candidate comparison without execution change"),
        ("Risk-based efficiency controller", "adaptive retrieval control", "checkpoint_risk_efficiency_controller", "Diagnostic policy that estimates skipped module cost by risk level"),
        ("Schema context voting", "full-vs-compact context voting", "checkpoint_schema_context_voting", "High-risk diagnostic comparison of compact and broader context"),
        ("Compact context shadow eval", "shadow replay", "checkpoint_compact_context_shadow_eval", "Replay-only compact-context cost comparison"),
        ("Risk-efficiency shadow eval", "shadow replay", "checkpoint_risk_efficiency_shadow_eval", "Replay-only diagnostic module-skipping cost comparison"),
    ]
    candidate_row = trajectory.get("_candidate_context_report_row") or {}
    candidate_active = {
        "checkpoint_hybrid_candidate_scoring": bool(candidate_row.get("hybrid_candidate_scoring", {}).get("active")),
        "checkpoint_endpoint_family_ranking": bool(candidate_row.get("endpoint_family_ranking", {}).get("active")),
        "checkpoint_structural_schema_preservation": bool(candidate_row.get("schema_linking", {}).get("bridge_preserved")),
        "checkpoint_value_to_api_ranking": bool(candidate_row.get("value_to_api_ranking", {}).get("active")),
        "checkpoint_gated_risk_cluster_repair": bool(candidate_row.get("gated_risk_cluster_repair", {}).get("active")),
        "checkpoint_risk_efficiency_controller": bool(candidate_row.get("risk_efficiency_controller", {}).get("active")),
        "checkpoint_schema_context_voting": bool(candidate_row.get("schema_context_vote", {}).get("active")),
    }
    shadow_row = trajectory.get("_shadow_repair_eval_row") or {}
    if shadow_row:
        candidate_active["checkpoint_risk_efficiency_controller"] = bool((shadow_row.get("risk_efficiency_controller") or {}).get("active"))
        candidate_active["checkpoint_schema_context_voting"] = bool((shadow_row.get("schema_context_vote") or {}).get("active"))
    if trajectory.get("_compact_context_shadow_eval_row"):
        candidate_active["checkpoint_compact_context_shadow_eval"] = True
    if trajectory.get("_risk_efficiency_shadow_eval_row"):
        candidate_active["checkpoint_risk_efficiency_shadow_eval"] = True
    return [
        {
            "technique": name,
            "source_inspiration": source,
            "active": checkpoint_id in checkpoint_ids or checkpoint_id == "spans.json" or candidate_active.get(checkpoint_id, False),
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


def _span_kind(checkpoint: dict[str, Any]) -> str:
    if checkpoint.get("checkpoint_id") == "checkpoint_sql_ast_validation":
        return "sql_ast_validation_span"
    checkpoint_id = str(checkpoint.get("checkpoint_id") or "checkpoint")
    return checkpoint_id.removeprefix("checkpoint_") + "_span"


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
