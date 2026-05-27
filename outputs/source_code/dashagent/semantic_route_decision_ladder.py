from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Callable

from .no_tool_safety_verifier import verify_no_tool_safety
from .prompt_semantic_ir import ObjectivePromptFeatures, extract_objective_prompt_features
from .routing_anti_hallucination_gate import RoutingGateRunResult, run_routing_gate_with_revision
from .semantic_intent_classifier import SemanticIntentDecision, classify_semantic_intent
from .semantic_intent_context_builder import build_semantic_intent_context, estimate_context_tokens


ALLOWED_SEMANTIC_ROUTE_ACTIONS = {
    "LLM_DIRECT",
    "LLM_SAFE_DIRECT",
    "SAFE_API_PROBE",
    "EVIDENCE_PIPELINE",
}

API_PROBE_BY_DOMAIN = {
    "TAG": {"endpoint_id": "unified_tags", "method": "GET", "path": "/unifiedtags/tags"},
    "AUDIT": {"endpoint_id": "audit_events", "method": "GET", "path": "/data/foundation/audit/events"},
    "MERGE_POLICY": {"endpoint_id": "merge_policies", "method": "GET", "path": "/data/core/ups/config/mergePolicies"},
    "DATAFLOW": {"endpoint_id": "flowservice_flows", "method": "GET", "path": "/data/foundation/flowservice/flows"},
    "FLOW": {"endpoint_id": "flowservice_flows", "method": "GET", "path": "/data/foundation/flowservice/flows"},
    "BATCH": {"endpoint_id": "catalog_batches", "method": "GET", "path": "/data/foundation/catalog/batches"},
    "SEGMENT": {"endpoint_id": "segment_definitions", "method": "GET", "path": "/data/core/ups/segment/definitions"},
    "AUDIENCE": {"endpoint_id": "ups_audiences", "method": "GET", "path": "/data/core/ups/audiences"},
    "DATASET": {"endpoint_id": "catalog_datasets", "method": "GET", "path": "/data/foundation/catalog/dataSets"},
    "SCHEMA": {"endpoint_id": "schemas_short", "method": "GET", "path": "/data/foundation/schemaregistry/tenant/schemas"},
}


@dataclass(frozen=True)
class SemanticRouteDecision:
    action: str
    tier_used: int
    features: dict[str, Any]
    semantic_intent_decision: dict[str, Any]
    routing_anti_hallucination_gate: dict[str, Any]
    no_tool_safety: dict[str, Any]
    context_token_cost: int
    average_tier_used: float
    low_low_case: bool = False
    safe_api_probe: dict[str, Any] = field(default_factory=dict)
    shadow_only: bool = True
    promotion_allowed: bool = False
    checkpoints: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if payload["action"] not in ALLOWED_SEMANTIC_ROUTE_ACTIONS:
            payload["action"] = "EVIDENCE_PIPELINE"
        return payload


def run_semantic_route_decision_ladder(
    prompt: str,
    *,
    classifier: Callable[[dict[str, Any]], SemanticIntentDecision] | None = None,
    llm_client: Any | None = None,
    tier2_diagnostic: bool = False,
    shadow_only: bool = True,
) -> SemanticRouteDecision:
    features = extract_objective_prompt_features(prompt)
    tier0_context = build_semantic_intent_context(features, tier=0)
    decision0 = _classify(tier0_context, classifier, llm_client)
    gate0 = run_routing_gate_with_revision(features, decision0)
    if gate0.fallback_action:
        safety_fallback = verify_no_tool_safety(features, gate0.final_decision)
        return _decision(gate0.fallback_action, 0, features, gate0.final_decision, gate0, safety_fallback, estimate_context_tokens(tier0_context), shadow_only=shadow_only)
    decision0 = gate0.final_decision
    safety0 = verify_no_tool_safety(features, decision0)
    token_cost = estimate_context_tokens(tier0_context)

    if decision0.no_tool and safety0.allow_no_tool and decision0.conf >= 0.85:
        return _decision("LLM_DIRECT", 0, features, decision0, gate0, safety0, token_cost, shadow_only=shadow_only)
    if safety0.evidence_need_score >= 0.75:
        return _decision("EVIDENCE_PIPELINE", 0, features, decision0, gate0, safety0, token_cost, shadow_only=shadow_only)

    low_low = decision0.conf < 0.75 and safety0.evidence_need_score < 0.75
    if low_low:
        tier = 2 if tier2_diagnostic else 1
        tier_context = build_semantic_intent_context(features, tier=tier)
        decision1 = _classify(tier_context, classifier, llm_client)
        gate1 = run_routing_gate_with_revision(features, decision1)
        if gate1.fallback_action:
            safety_fallback = verify_no_tool_safety(features, gate1.final_decision)
            return _decision(gate1.fallback_action, tier, features, gate1.final_decision, gate1, safety_fallback, token_cost, low_low=True, shadow_only=shadow_only)
        decision1 = gate1.final_decision
        safety1 = verify_no_tool_safety(features, decision1)
        token_cost += estimate_context_tokens(tier_context)
        if decision1.no_tool and safety1.allow_no_tool and decision1.conf >= 0.80:
            return _decision("LLM_DIRECT", tier, features, decision1, gate1, safety1, token_cost, low_low=True, shadow_only=shadow_only)
        if safety1.clear_safe_api_family:
            return _decision(
                "SAFE_API_PROBE",
                tier,
                features,
                decision1,
                gate1,
                safety1,
                token_cost,
                low_low=True,
                safe_api_probe=_safe_api_probe(features),
                shadow_only=shadow_only,
            )
        if safety1.has_concrete_data_signal:
            return _decision("EVIDENCE_PIPELINE", tier, features, decision1, gate1, safety1, token_cost, low_low=True, shadow_only=shadow_only)
        return _decision("LLM_SAFE_DIRECT", tier, features, decision1, gate1, safety1, token_cost, low_low=True, shadow_only=shadow_only)

    if safety0.clear_safe_api_family and not safety0.has_concrete_data_signal:
        return _decision(
            "SAFE_API_PROBE",
            0,
            features,
            decision0,
            gate0,
            safety0,
            token_cost,
            safe_api_probe=_safe_api_probe(features),
            shadow_only=shadow_only,
        )
    if safety0.has_concrete_data_signal or decision0.sql:
        return _decision("EVIDENCE_PIPELINE", 0, features, decision0, gate0, safety0, token_cost, shadow_only=shadow_only)
    if decision0.no_tool and safety0.action == "ALLOW_NO_TOOL":
        return _decision("LLM_SAFE_DIRECT", 0, features, decision0, gate0, safety0, token_cost, shadow_only=shadow_only)
    return _decision("EVIDENCE_PIPELINE", 0, features, decision0, gate0, safety0, token_cost, shadow_only=shadow_only)


def validate_llm_safe_direct_answer(answer: str) -> dict[str, Any]:
    text = str(answer or "")
    blocked: list[str] = []
    if re.search(r"\b(there (?:are|is)|count|total)\s+\d+\b", text, re.I):
        blocked.append("CONCRETE_COUNT")
    if re.search(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", text, re.I):
        blocked.append("CONCRETE_ID")
    if re.search(r"\b\d{4}-\d{2}-\d{2}(?:[T ][0-9:.Z+-]+)?\b", text):
        blocked.append("CONCRETE_TIMESTAMP")
    if re.search(r"\b(active|inactive|failed|succeeded|published|deployed)\b", text, re.I):
        blocked.append("CONCRETE_STATUS")
    if re.search(r"\b(live|current)\s+(?:platform|sandbox|api|adobe)\b", text, re.I):
        blocked.append("LIVE_PLATFORM_STATE")
    blocked = _dedupe(blocked)
    return {"ok": not blocked, "blocked_claims": blocked}


def _classify(
    context: dict[str, Any],
    classifier: Callable[[dict[str, Any]], SemanticIntentDecision] | None,
    llm_client: Any | None,
) -> SemanticIntentDecision:
    if classifier is not None:
        result = classifier(context)
        if isinstance(result, SemanticIntentDecision):
            return result
        return SemanticIntentDecision(**result)  # type: ignore[arg-type]
    return classify_semantic_intent(context, llm_client=llm_client)


def _decision(
    action: str,
    tier: int,
    features: ObjectivePromptFeatures,
    decision: SemanticIntentDecision,
    gate: RoutingGateRunResult,
    safety: Any,
    token_cost: int,
    *,
    low_low: bool = False,
    safe_api_probe: dict[str, Any] | None = None,
    shadow_only: bool = True,
) -> SemanticRouteDecision:
    if action not in ALLOWED_SEMANTIC_ROUTE_ACTIONS:
        action = "EVIDENCE_PIPELINE"
    feature_payload = features.to_dict()
    safety_payload = safety.to_dict()
    return SemanticRouteDecision(
        action=action,
        tier_used=tier,
        features=feature_payload,
        semantic_intent_decision=decision.to_dict(),
        routing_anti_hallucination_gate=gate.to_dict(),
        no_tool_safety=safety_payload,
        context_token_cost=token_cost,
        average_tier_used=float(tier),
        low_low_case=low_low,
        safe_api_probe=safe_api_probe or {},
        shadow_only=shadow_only,
        promotion_allowed=False,
        checkpoints={
            "checkpoint_objective_prompt_features": feature_payload,
            "checkpoint_semantic_intent_decision": decision.to_dict(),
            "checkpoint_routing_anti_hallucination_gate": gate.to_dict(),
            "checkpoint_no_tool_safety_verifier": safety_payload,
            "checkpoint_semantic_route_decision_ladder": {"action": action, "tier_used": tier, "shadow_only": shadow_only},
        },
    )


def _safe_api_probe(features: ObjectivePromptFeatures) -> dict[str, Any]:
    for domain in features.domain:
        candidate = API_PROBE_BY_DOMAIN.get(domain)
        if candidate and candidate["method"] == "GET" and "{" not in candidate["path"]:
            return {**candidate, "max_endpoints": 1, "mutating": False, "unresolved_path_params": False}
    return {"endpoint_id": None, "method": "GET", "path": "", "max_endpoints": 0, "mutating": False, "unresolved_path_params": False}


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out
