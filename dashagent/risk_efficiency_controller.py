from __future__ import annotations

from typing import Any


MODULE_COST_ESTIMATES = {
    "hybrid_candidate_scoring": {"tokens": 24, "runtime_ms": 1.5},
    "endpoint_family_ranking": {"tokens": 18, "runtime_ms": 1.0},
    "value_retrieval": {"tokens": 64, "runtime_ms": 12.0},
    "shadow_repair": {"tokens": 80, "runtime_ms": 8.0},
    "repair_safety_verifier": {"tokens": 24, "runtime_ms": 2.0},
    "schema_context_voting": {"tokens": 96, "runtime_ms": 3.0},
}

LOW_RISK_MODULES = (
    "value_retrieval",
    "shadow_repair",
    "repair_safety_verifier",
    "schema_context_voting",
)

MEDIUM_RISK_MODULES = (
    "value_retrieval",
    "shadow_repair",
    "repair_safety_verifier",
    "schema_context_voting",
)

HIGH_RISK_MODULES: tuple[str, ...] = ()


def classify_candidate_risk(
    candidate_context: dict[str, Any],
    *,
    risk_cluster: str | None = None,
    missing_candidate_signals: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Classify retrieval risk and estimate diagnostic-module savings.

    This helper is intentionally report-only. It describes which expensive
    diagnostics *could* be skipped by a risk-aware path, but it does not change
    packaged SQL_FIRST_API_VERIFY execution.
    """

    missing_candidate_signals = missing_candidate_signals or {}
    confidence = _float(candidate_context.get("confidence"), 0.0)
    score_margin = _float(candidate_context.get("score_margin"), 0.0)
    schema_linking = candidate_context.get("schema_linking") or {}
    schema_link_risk = str(schema_linking.get("schema_link_risk") or "unknown")
    endpoint_ranking = candidate_context.get("endpoint_family_ranking") or {}
    endpoint_confidence = _float(endpoint_ranking.get("endpoint_family_confidence"), 0.0)
    cluster = risk_cluster or _risk_cluster_from_context(candidate_context)

    reasons: list[str] = []
    if schema_link_risk == "high":
        reasons.append("high_schema_link_risk")
    if confidence < 0.4:
        reasons.append("low_confidence")
    if score_margin == 0:
        reasons.append("zero_score_margin")
    if endpoint_confidence and endpoint_confidence < 0.5:
        reasons.append("low_endpoint_family_confidence")
    if cluster in {
        "zero_score_margin",
        "missing_gold_api_in_top_k",
        "batch_endpoint_confusion",
        "tag_api_confusion",
        "schema_vs_dataset_confusion",
        "broad_domain_api_confusion",
    }:
        reasons.append(f"risk_cluster:{cluster}")
    if missing_candidate_signals.get("missing_tables"):
        reasons.append("missing_candidate_tables")
    if missing_candidate_signals.get("missing_apis"):
        reasons.append("missing_candidate_apis")

    if reasons:
        level = "high"
        skipped = list(HIGH_RISK_MODULES)
        policy = "high risk: value retrieval + shadow repair + verifier diagnostics"
    elif confidence < 0.75 or score_margin < 0.15 or endpoint_confidence < 0.75:
        level = "medium"
        skipped = list(MEDIUM_RISK_MODULES)
        policy = "medium risk: hybrid ranking + endpoint ranking diagnostics"
        if confidence < 0.75:
            reasons.append("medium_confidence")
        if score_margin < 0.15:
            reasons.append("small_score_margin")
        if endpoint_confidence < 0.75:
            reasons.append("medium_endpoint_family_confidence")
    else:
        level = "low"
        skipped = list(LOW_RISK_MODULES)
        policy = "low risk: skip expensive diagnostics"
        reasons.append("strong_candidate_separation")

    token_saved = sum(MODULE_COST_ESTIMATES[module]["tokens"] for module in skipped)
    runtime_saved = sum(MODULE_COST_ESTIMATES[module]["runtime_ms"] for module in skipped)
    return {
        "active": True,
        "diagnostic_only": True,
        "behavior_changed": False,
        "risk_level": level,
        "accuracy_risk": _accuracy_risk(level, reasons),
        "risk_reasons": reasons,
        "module_policy": policy,
        "module_skipped_by_risk": skipped,
        "modules_run_by_policy": _modules_run_for_level(level),
        "token_saved_estimate": round(token_saved, 2),
        "runtime_saved_estimate_ms": round(runtime_saved, 2),
        "savings_are_estimates": True,
        "measured_efficiency_improvement_claimed": False,
        "estimate_basis": "static diagnostic-module cost estimates; packaged execution did not skip modules",
        "inputs": {
            "confidence": confidence,
            "score_margin": score_margin,
            "schema_link_risk": schema_link_risk,
            "endpoint_family_confidence": endpoint_confidence,
            "risk_cluster": cluster,
            "missing_candidate_signals": missing_candidate_signals,
        },
    }


def _modules_run_for_level(level: str) -> list[str]:
    if level == "low":
        return ["hybrid_candidate_scoring", "endpoint_family_ranking"]
    if level == "medium":
        return ["hybrid_candidate_scoring", "endpoint_family_ranking"]
    return [
        "hybrid_candidate_scoring",
        "endpoint_family_ranking",
        "value_retrieval",
        "shadow_repair",
        "repair_safety_verifier",
        "schema_context_voting",
    ]


def _accuracy_risk(level: str, reasons: list[str]) -> str:
    if level == "high":
        return "high - " + ", ".join(reasons[:4])
    if level == "medium":
        return "medium - candidate confidence or endpoint confidence is not strong enough for compact-only diagnostics"
    return "low - candidates are separated and schema/API signals are consistent"


def _risk_cluster_from_context(candidate_context: dict[str, Any]) -> str:
    repair = candidate_context.get("gated_risk_cluster_repair") or {}
    if repair.get("risk_cluster"):
        return str(repair["risk_cluster"])
    if (candidate_context.get("score_margin") or 0) == 0:
        return "zero_score_margin"
    endpoint = candidate_context.get("endpoint_family_ranking") or {}
    if endpoint.get("ranking_changed"):
        return "missing_gold_api_in_top_k"
    return "not_targeted"


def _float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
