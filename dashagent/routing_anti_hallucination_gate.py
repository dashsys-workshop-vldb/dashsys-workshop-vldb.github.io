from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable

from .prompt_semantic_ir import ObjectivePromptFeatures
from .semantic_intent_classifier import SemanticIntentDecision


@dataclass(frozen=True)
class RoutingGateResult:
    ok: bool
    block: list[str] = field(default_factory=list)
    unsupported_codes: list[str] = field(default_factory=list)
    support: dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in ("final_route", "api_policy", "sql_route", "route"):
            payload.pop(key, None)
        return payload


@dataclass(frozen=True)
class RoutingGateRunResult:
    initial_gate: RoutingGateResult
    final_gate: RoutingGateResult
    initial_decision: SemanticIntentDecision
    final_decision: SemanticIntentDecision
    revision_attempted: bool = False
    revision_success: bool = False
    fallback_action: str | None = None
    feedback: dict[str, Any] = field(default_factory=dict)
    revision_token_estimate: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "initial_gate": self.initial_gate.to_dict(),
            "final_gate": self.final_gate.to_dict(),
            "initial_decision": self.initial_decision.to_dict(),
            "final_decision": self.final_decision.to_dict(),
            "revision_attempted": self.revision_attempted,
            "revision_success": self.revision_success,
            "fallback_action": self.fallback_action,
            "feedback": self.feedback,
            "revision_token_estimate": self.revision_token_estimate,
        }


def validate_routing_decision_support(
    features: ObjectivePromptFeatures | dict[str, Any],
    decision: SemanticIntentDecision | dict[str, Any],
) -> RoutingGateResult:
    feature_payload = features.to_dict() if isinstance(features, ObjectivePromptFeatures) else dict(features)
    decision_payload = decision.to_dict() if isinstance(decision, SemanticIntentDecision) else dict(decision)
    allowed_codes = set(feature_payload.get("cap") or [])
    decision_codes = [str(code) for code in decision_payload.get("codes") or decision_payload.get("flags") or []]
    unsupported_codes = [code for code in decision_codes if code.startswith(("SQL_", "API_")) and code not in allowed_codes]
    block: list[str] = []
    concrete = _has_concrete_signal(feature_payload)
    evidence_support = _has_evidence_support(feature_payload)
    mixed = bool(feature_payload.get("cue") and (feature_payload.get("retr") or feature_payload.get("count")))
    no_tool = bool(decision_payload.get("no_tool") or decision_payload.get("need") == "NONE")
    evidence_need = str(decision_payload.get("need") or "UNKNOWN") in {"SQL", "API", "SQL_API"}

    if no_tool and concrete:
        block.append("UNSUPPORTED_NO_TOOL")
    if mixed and no_tool:
        block.append("MIXED_REQUIRES_EVIDENCE")
    if evidence_need and not evidence_support:
        block.append("UNSUPPORTED_EVIDENCE_NEED")
    if unsupported_codes:
        block.append("UNKNOWN_CAPABILITY_CODE")

    support = {
        "intent": not ("UNSUPPORTED_NO_TOOL" in block or "MIXED_REQUIRES_EVIDENCE" in block),
        "need": not ("UNSUPPORTED_NO_TOOL" in block or "UNSUPPORTED_EVIDENCE_NEED" in block or "MIXED_REQUIRES_EVIDENCE" in block),
        "caps": not unsupported_codes,
    }
    ok = not block
    return RoutingGateResult(ok=ok, block=_dedupe(block), unsupported_codes=unsupported_codes, support=support)


def build_routing_gate_feedback(
    previous: SemanticIntentDecision,
    gate: RoutingGateResult,
    features: ObjectivePromptFeatures | dict[str, Any],
) -> dict[str, Any]:
    feature_payload = features.to_dict() if isinstance(features, ObjectivePromptFeatures) else dict(features)
    allowed_fix = ["set no_tool=false when data cues exist", "use only supported capability codes"]
    if feature_payload.get("retr") or feature_payload.get("count") or feature_payload.get("fields"):
        allowed_fix.append("choose DATA with SQL/API need if evidence is requested")
    if feature_payload.get("cue") and not _has_concrete_signal(feature_payload):
        allowed_fix.append("choose CONCEPT/NONE only when no concrete data cues exist")
    feedback = {
        "prev": previous.to_dict(),
        "gate": {
            "block": gate.block,
            "unsupported_codes": gate.unsupported_codes,
            "feature_conflicts": _feature_conflicts(feature_payload, gate),
            "allowed_fix": allowed_fix,
            "must_not": ["do not write SQL", "do not create API params", "do not answer user", "do not include prose"],
        },
        "task": "Return corrected SemanticIntentDecision JSON only.",
    }
    return feedback


def run_routing_gate_with_revision(
    features: ObjectivePromptFeatures | dict[str, Any],
    decision: SemanticIntentDecision,
    *,
    reviser: Callable[[dict[str, Any]], SemanticIntentDecision | dict[str, Any]] | None = None,
) -> RoutingGateRunResult:
    initial = validate_routing_decision_support(features, decision)
    if initial.ok:
        return RoutingGateRunResult(initial, initial, decision, decision)
    feedback = build_routing_gate_feedback(decision, initial, features)
    if reviser is None:
        fallback = _fallback_action(features)
        return RoutingGateRunResult(initial, initial, decision, decision, False, False, fallback, feedback, _estimate_tokens(feedback))
    revised_raw = reviser(feedback)
    revised = revised_raw if isinstance(revised_raw, SemanticIntentDecision) else SemanticIntentDecision(**revised_raw)
    final = validate_routing_decision_support(features, revised)
    if final.ok:
        return RoutingGateRunResult(initial, final, decision, revised, True, True, None, feedback, _estimate_tokens(feedback))
    return RoutingGateRunResult(initial, final, decision, revised, True, False, _fallback_action(features), feedback, _estimate_tokens(feedback))


def _has_concrete_signal(features: dict[str, Any]) -> bool:
    return bool(
        features.get("retr")
        or features.get("count")
        or features.get("fields")
        or features.get("rel")
        or (features.get("status") and features.get("entity"))
        or (features.get("date") and features.get("entity"))
        or (features.get("entity") and not features.get("cue"))
    )


def _has_evidence_support(features: dict[str, Any]) -> bool:
    return bool(features.get("retr") or features.get("fields") or features.get("entity") or features.get("domain") or features.get("cap") or features.get("count"))


def _feature_conflicts(features: dict[str, Any], gate: RoutingGateResult) -> list[str]:
    conflicts: list[str] = []
    if "UNSUPPORTED_NO_TOOL" in gate.block:
        for key, code in [("retr", "RETR"), ("count", "COUNT"), ("fields", "FIELDS"), ("status", "STATUS"), ("date", "DATE"), ("rel", "REL"), ("entity", "ENTITY_LOOKUP")]:
            if features.get(key):
                conflicts.append(code)
    if "MIXED_REQUIRES_EVIDENCE" in gate.block:
        conflicts.append("MIXED_CONCEPT_AND_RETRIEVAL")
    return _dedupe(conflicts)


def _fallback_action(features: ObjectivePromptFeatures | dict[str, Any]) -> str:
    payload = features.to_dict() if isinstance(features, ObjectivePromptFeatures) else dict(features)
    return "EVIDENCE_PIPELINE" if _has_concrete_signal(payload) else "LLM_SAFE_DIRECT"


def _estimate_tokens(obj: Any) -> int:
    return max(1, len(str(obj)) // 4)


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out
