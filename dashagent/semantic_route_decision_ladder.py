from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Callable

from .no_tool_safety_verifier import verify_no_tool_safety
from .minimal_correction_feedback import build_minimal_correction_feedback
from .progressive_evidence_policy import decide_progressive_evidence_entry
from .prompt_semantic_ir import ObjectivePromptFeatures, extract_objective_prompt_features
from .routing_anti_hallucination_gate import RoutingGateRunResult, run_routing_gate_with_revision
from .semantic_consistency_verifier import SemanticConsistencyResult, verify_semantic_consistency
from .semantic_intent_classifier import SemanticIntentDecision, classify_semantic_intent
from .semantic_intent_context_builder import build_semantic_intent_context, estimate_context_tokens
from .semantic_parse import SemanticParse
from .semantic_parser import parse_prompt_semantics


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
    semantic_parse: dict[str, Any]
    semantic_intent_decision: dict[str, Any]
    routing_anti_hallucination_gate: dict[str, Any]
    semantic_consistency: dict[str, Any]
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
    enable_semantic_parse: bool = True,
    tier2_diagnostic: bool = False,
    shadow_only: bool = True,
) -> SemanticRouteDecision:
    features = extract_objective_prompt_features(prompt)
    semantic_parse = (
        parse_prompt_semantics(prompt, features, llm_client=llm_client, use_llm=llm_client is not None)
        if enable_semantic_parse
        else SemanticParse(source="SEMANTIC_PARSE_DISABLED", no_tool_safe=False, evidence_need="UNKNOWN")
    )
    tier0_context = build_semantic_intent_context(features, tier=0)
    decision0 = _classify(tier0_context, classifier, llm_client)
    decision0 = _align_decision_to_semantic_parse(decision0, semantic_parse)
    gate0 = run_routing_gate_with_revision(features, decision0)
    decision0 = gate0.final_decision
    consistency0 = verify_semantic_consistency(features, semantic_parse, decision0)
    safety0 = verify_no_tool_safety(features, decision0)
    token_cost = estimate_context_tokens(tier0_context)

    if consistency0.allow_no_tool and decision0.conf >= 0.85:
        return _decision("LLM_DIRECT", 0, features, semantic_parse, decision0, gate0, consistency0, safety0, token_cost, shadow_only=shadow_only)
    if consistency0.allow_no_tool:
        return _decision("LLM_SAFE_DIRECT", 0, features, semantic_parse, decision0, gate0, consistency0, safety0, token_cost, shadow_only=shadow_only)
    if consistency0.fallback_action == "SAFE_API_PROBE":
        return _decision(
            "SAFE_API_PROBE",
            0,
            features,
            semantic_parse,
            decision0,
            gate0,
            consistency0,
            safety0,
            token_cost,
            safe_api_probe=_safe_api_probe(features),
            shadow_only=shadow_only,
        )
    low_low = decision0.conf < 0.75 and safety0.evidence_need_score < 0.75
    if low_low:
        tier = 2 if tier2_diagnostic else 1
        tier_context = build_semantic_intent_context(features, tier=tier)
        decision1 = _classify(tier_context, classifier, llm_client)
        decision1 = _align_decision_to_semantic_parse(decision1, semantic_parse)
        gate1 = run_routing_gate_with_revision(features, decision1)
        decision1 = gate1.final_decision
        consistency1 = verify_semantic_consistency(features, semantic_parse, decision1)
        safety1 = verify_no_tool_safety(features, decision1)
        token_cost += estimate_context_tokens(tier_context)
        if consistency1.allow_no_tool and decision1.conf >= 0.80:
            return _decision("LLM_DIRECT", tier, features, semantic_parse, decision1, gate1, consistency1, safety1, token_cost, low_low=True, shadow_only=shadow_only)
        if consistency1.allow_no_tool:
            return _decision("LLM_SAFE_DIRECT", tier, features, semantic_parse, decision1, gate1, consistency1, safety1, token_cost, low_low=True, shadow_only=shadow_only)
        if consistency1.fallback_action == "SAFE_API_PROBE" or safety1.clear_safe_api_family:
            return _decision(
                "SAFE_API_PROBE",
                tier,
                features,
                semantic_parse,
                decision1,
                gate1,
                consistency1,
                safety1,
                token_cost,
                low_low=True,
                safe_api_probe=_safe_api_probe(features),
                shadow_only=shadow_only,
            )
        if consistency1.fallback_action == "EVIDENCE_PIPELINE" or safety1.has_concrete_data_signal:
            return _decision("EVIDENCE_PIPELINE", tier, features, semantic_parse, decision1, gate1, consistency1, safety1, token_cost, low_low=True, shadow_only=shadow_only)
        return _decision("LLM_SAFE_DIRECT", tier, features, semantic_parse, decision1, gate1, consistency1, safety1, token_cost, low_low=True, shadow_only=shadow_only)

    if consistency0.fallback_action == "LLM_SAFE_DIRECT":
        return _decision("LLM_SAFE_DIRECT", 0, features, semantic_parse, decision0, gate0, consistency0, safety0, token_cost, shadow_only=shadow_only)
    if consistency0.fallback_action == "EVIDENCE_PIPELINE" or safety0.evidence_need_score >= 0.75:
        return _decision("EVIDENCE_PIPELINE", 0, features, semantic_parse, decision0, gate0, consistency0, safety0, token_cost, shadow_only=shadow_only)

    if safety0.clear_safe_api_family and not safety0.has_concrete_data_signal:
        return _decision(
            "SAFE_API_PROBE",
            0,
            features,
            semantic_parse,
            decision0,
            gate0,
            consistency0,
            safety0,
            token_cost,
            safe_api_probe=_safe_api_probe(features),
            shadow_only=shadow_only,
        )
    if safety0.has_concrete_data_signal or decision0.sql:
        return _decision("EVIDENCE_PIPELINE", 0, features, semantic_parse, decision0, gate0, consistency0, safety0, token_cost, shadow_only=shadow_only)
    if decision0.no_tool and safety0.action == "ALLOW_NO_TOOL":
        return _decision("LLM_SAFE_DIRECT", 0, features, semantic_parse, decision0, gate0, consistency0, safety0, token_cost, shadow_only=shadow_only)
    return _decision("EVIDENCE_PIPELINE", 0, features, semantic_parse, decision0, gate0, consistency0, safety0, token_cost, shadow_only=shadow_only)


def validate_llm_safe_direct_answer(answer: str) -> dict[str, Any]:
    text = str(answer or "")
    blocked: list[str] = []
    if re.search(r"\b(there (?:are|is)|count|total)\s+\d+\b", text, re.I):
        blocked.append("CONCRETE_COUNT")
    if re.search(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", text, re.I):
        blocked.append("CONCRETE_ID")
    if re.search(r"\b\d{4}-\d{2}-\d{2}(?:[T ][0-9:.Z+-]+)?\b", text):
        blocked.append("CONCRETE_TIMESTAMP")
    for match in re.finditer(r"\b(active|inactive|failed|succeeded|published|deployed)\b", text, re.I):
        if not _looks_like_conceptual_status_word(text, match.start(), match.end()):
            blocked.append("CONCRETE_STATUS")
            break
    if re.search(r"\b(live|current)\s+(?:platform|sandbox|api|adobe)\b", text, re.I):
        blocked.append("LIVE_PLATFORM_STATE")
    blocked = _dedupe(blocked)
    return {"ok": not blocked, "blocked_claims": blocked}


def _looks_like_conceptual_status_word(text: str, start: int, end: int) -> bool:
    context = str(text or "")[max(0, start - 90) : min(len(str(text or "")), end + 90)].lower()
    conceptual_signal = bool(
        re.search(
            r"\b(is a|means|refers to|defined as|concept|typically|can mean|can include|not currently|not running|status indicator|such as|for example|e\.g\.)\b",
            context,
        )
    )
    concrete_signal = bool(
        re.search(
            r"\b(birthday message|gold tier|you have|your|local snapshot|live api|current platform|records?|schemas?|journeys?:|campaigns?:|there (?:is|are)|count|total)\b",
            context,
        )
        or re.search(r"\b\d{4}-\d{2}-\d{2}\b", context)
        or re.search(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", context)
    )
    return conceptual_signal and not concrete_signal


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


def _align_decision_to_semantic_parse(decision: SemanticIntentDecision, semantic_parse: SemanticParse) -> SemanticIntentDecision:
    if not _decision_is_low_authority(decision):
        return decision
    if semantic_parse.no_tool_safe and semantic_parse.evidence_need == "NONE":
        intent = "UNSUPPORTED" if semantic_parse.target.grounding == "OUT_OF_DOMAIN" else "CONCEPT"
        return SemanticIntentDecision(
            intent=intent,
            need="NONE",
            no_tool=True,
            sql=False,
            api=False,
            conf=max(float(decision.conf), float(semantic_parse.confidence), 0.78),
            codes=_dedupe([*decision.codes, "SEMANTIC_PARSE_NO_TOOL"]),
        )
    if semantic_parse.evidence_need in {"SQL", "API", "SQL_API"}:
        return SemanticIntentDecision(
            intent="LIVE_API" if semantic_parse.evidence_need == "API" else ("MIXED" if semantic_parse.evidence_need == "SQL_API" else "DATA"),
            need=semantic_parse.evidence_need,
            no_tool=False,
            sql=semantic_parse.evidence_need in {"SQL", "SQL_API"},
            api=semantic_parse.evidence_need in {"API", "SQL_API"},
            conf=max(float(decision.conf), float(semantic_parse.confidence), 0.76),
            codes=_dedupe([*decision.codes, "SEMANTIC_PARSE_EVIDENCE"]),
        )
    return decision


def _decision_is_low_authority(decision: SemanticIntentDecision) -> bool:
    return bool(
        decision.conf < 0.55
        or decision.intent == "AMBIG"
        or decision.need == "UNKNOWN"
        or set(decision.codes) & {"FALLBACK", "INVALID_JSON"}
    )


def _decision(
    action: str,
    tier: int,
    features: ObjectivePromptFeatures,
    semantic_parse: SemanticParse,
    decision: SemanticIntentDecision,
    gate: RoutingGateRunResult,
    semantic_consistency: SemanticConsistencyResult,
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
    consistency_payload = semantic_consistency.to_dict()
    semantic_feedback = _semantic_minimal_feedback(decision, semantic_parse, consistency_payload)
    safety_payload["allow_no_tool"] = bool(consistency_payload.get("allow_no_tool"))
    safety_payload["block"] = list(consistency_payload.get("block_codes") or [])
    safety_payload["semantic_consistency_codes"] = list(consistency_payload.get("consistency_codes") or [])
    safety_payload["action"] = "ALLOW_NO_TOOL" if consistency_payload.get("allow_no_tool") else "BLOCK_NO_TOOL"
    candidate_probe = safe_api_probe or (_safe_api_probe(features) if action == "SAFE_API_PROBE" else {})
    progressive = decide_progressive_evidence_entry(
        features=features,
        semantic_parse=semantic_parse,
        semantic_decision=decision,
        semantic_consistency=semantic_consistency,
        no_tool_safety=safety_payload,
        safe_api_probe=candidate_probe,
    )
    progressive_payload = progressive.to_dict()
    action = progressive.entry_action
    safe_api_probe_payload = progressive.safe_api_probe if action == "SAFE_API_PROBE" else {}
    parse_payload = semantic_parse.to_dict()
    return SemanticRouteDecision(
        action=action,
        tier_used=tier,
        features=feature_payload,
        semantic_parse=parse_payload,
        semantic_intent_decision=decision.to_dict(),
        routing_anti_hallucination_gate=gate.to_dict(),
        semantic_consistency=consistency_payload,
        no_tool_safety=safety_payload,
        context_token_cost=token_cost,
        average_tier_used=float(tier),
        low_low_case=low_low,
        safe_api_probe=safe_api_probe_payload,
        shadow_only=shadow_only,
        promotion_allowed=False,
        checkpoints={
            "checkpoint_objective_prompt_features": feature_payload,
            "checkpoint_semantic_parse": parse_payload,
            "checkpoint_semantic_intent_decision": decision.to_dict(),
            "checkpoint_routing_anti_hallucination_gate": gate.to_dict(),
            "checkpoint_minimal_correction_feedback_semantic": semantic_feedback,
            "checkpoint_semantic_revision_result": {
                "revision_attempted": bool(gate.revision_attempted),
                "revision_success": bool(gate.revision_success),
                "final_decision": decision.to_dict(),
                "source": "LLM_DECISION" if not _decision_is_low_authority(decision) else "LOW_AUTHORITY_OR_FALLBACK_DECISION",
            },
            "checkpoint_semantic_fallback_if_any": {
                "fallback_action": consistency_payload.get("fallback_action") if not consistency_payload.get("ok") else None,
                "semantic_certainty_claimed": False,
            },
            "checkpoint_semantic_consistency_verifier": consistency_payload,
            "checkpoint_no_tool_safety_verifier": safety_payload,
            "checkpoint_progressive_evidence_policy": progressive_payload,
            "checkpoint_semantic_route_decision_ladder": {"action": action, "tier_used": tier, "shadow_only": shadow_only},
        },
    )


def _semantic_minimal_feedback(
    decision: SemanticIntentDecision,
    semantic_parse: SemanticParse,
    consistency_payload: dict[str, Any],
) -> dict[str, Any]:
    block_codes = list(consistency_payload.get("block_codes") or [])
    if not block_codes:
        return {
            "task": "REVISE_SEMANTIC_DECISION",
            "revision_required": False,
            "conflicts": [],
            "feedback_token_estimate": 0,
        }
    target = semantic_parse.target
    conflicts: list[dict[str, Any]] = []
    for code in block_codes:
        if code in {"SUPPORTED_DATA_OBJECT", "INSTANCE_LEVEL", "DATA_OPERATION", "EVIDENCE_NEEDED"}:
            conflicts.append(
                {
                    "code": "NO_TOOL_CONFLICTS_WITH_INSTANCE_REQUEST",
                    "given": f"no_tool={str(decision.no_tool).lower()}",
                    "required": f"target.grounding={target.grounding}, instance_level={str(target.instance_level).lower()}, evidence_need={semantic_parse.evidence_need}",
                }
            )
        elif code == "LIVE_OR_API_STATE":
            conflicts.append({"code": "NO_TOOL_CONFLICTS_WITH_LIVE_OR_API_STATE", "given": "no_tool=true", "required": "live/current/API/platform evidence"})
        elif code == "EXPLICIT_API_FAMILY":
            conflicts.append({"code": "NO_TOOL_CONFLICTS_WITH_EXPLICIT_API_FAMILY", "given": "no_tool=true", "required": "API family evidence"})
        else:
            conflicts.append({"code": code, "given": "semantic decision", "required": "consistent SemanticParse"})
    feedback = build_minimal_correction_feedback(
        task="REVISE_SEMANTIC_DECISION",
        previous_decision=decision.to_dict(),
        conflicts=conflicts,
        must_reconsider=["target_grounding", "instance_level", "evidence_need"],
        allowed_outputs=["EVIDENCE_NEEDED", "SQL", "API", "SQL_API"],
        forbidden_outputs=["NO_TOOL"],
        output_schema={
            "intent": "CONCEPT|DATA|LIVE_API|MIXED|AMBIG|UNSUPPORTED",
            "need": "NONE|SQL|API|SQL_API|UNKNOWN",
            "no_tool": "boolean",
            "sql": "boolean",
            "api": "boolean",
            "conf": "0.0-1.0",
            "codes": ["short codes"],
        },
    )
    payload = feedback.to_dict()
    payload["revision_required"] = True
    payload["feedback_token_estimate"] = feedback.token_estimate
    return payload


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
