from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .prompt_semantic_ir import ObjectivePromptFeatures
from .semantic_intent_classifier import SemanticIntentDecision
from .semantic_parse import SemanticParse


DATA_OPERATIONS = {"LIST", "COUNT", "LOOKUP", "STATUS", "DATE", "RELATIONSHIP"}
NO_TOOL_GROUNDINGS = {"CONCEPTUAL_OBJECT", "META_LANGUAGE", "OUT_OF_DOMAIN"}


@dataclass(frozen=True)
class SemanticConsistencyResult:
    ok: bool
    allow_no_tool: bool
    block_codes: list[str] = field(default_factory=list)
    consistency_codes: list[str] = field(default_factory=list)
    fallback_action: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def verify_semantic_consistency(
    features: ObjectivePromptFeatures | dict[str, Any],
    semantic_parse: SemanticParse | dict[str, Any],
    decision: SemanticIntentDecision | dict[str, Any],
) -> SemanticConsistencyResult:
    feature_payload = features.to_dict() if isinstance(features, ObjectivePromptFeatures) else dict(features)
    parsed = semantic_parse if isinstance(semantic_parse, SemanticParse) else SemanticParse.from_dict(dict(semantic_parse))
    decision_payload = decision.to_dict() if isinstance(decision, SemanticIntentDecision) else dict(decision)
    wants_no_tool = bool(decision_payload.get("no_tool") or decision_payload.get("need") == "NONE")
    block: list[str] = []
    codes: list[str] = []

    semantic_no_tool_role = (
        parsed.target.grounding in NO_TOOL_GROUNDINGS
        and not parsed.target.instance_level
        and parsed.evidence_need == "NONE"
        and parsed.no_tool_safe
    )
    hard_data_role = (
        parsed.target.grounding == "SUPPORTED_DATA_OBJECT"
        or parsed.target.instance_level
        or parsed.operation in DATA_OPERATIONS and parsed.evidence_need in {"SQL", "API", "SQL_API"}
    )

    if wants_no_tool:
        if parsed.target.grounding == "SUPPORTED_DATA_OBJECT":
            block.append("SUPPORTED_DATA_OBJECT")
        if parsed.target.instance_level:
            block.append("INSTANCE_LEVEL")
        if parsed.operation in DATA_OPERATIONS and parsed.evidence_need != "NONE":
            block.append("DATA_OPERATION")
        if parsed.evidence_need in {"SQL", "API", "SQL_API"}:
            block.append("EVIDENCE_NEEDED")
        if parsed.requested_fields:
            block.append("REQUESTED_DATA_FIELDS")
        if _semantic_live_or_api_state_request(feature_payload, parsed):
            block.append("LIVE_OR_API_STATE")
        if _explicit_api_family_request(feature_payload, parsed):
            block.append("EXPLICIT_API_FAMILY")
        if _contradicts_objective_features(feature_payload, parsed):
            block.append("OBJECTIVE_SEMANTIC_CONFLICT")
    elif semantic_no_tool_role:
        block.append("INTENT_NO_TOOL_FALSE_FOR_SAFE_PARSE")

    if semantic_no_tool_role and _has_surface_evidence_cues(feature_payload):
        codes.append("KEYWORD_ONLY_BLOCK_AVOIDED")
    if hard_data_role:
        codes.append("SEMANTIC_DATA_ROLE_REQUIRES_EVIDENCE")
    if parsed.target.grounding == "META_LANGUAGE":
        codes.append("META_LANGUAGE_CONTEXT")
    if parsed.target.grounding == "OUT_OF_DOMAIN":
        codes.append("OUT_OF_DOMAIN_SAFE_DIRECT")
    if semantic_no_tool_role and wants_no_tool and not block:
        codes.append("SEMANTIC_NO_TOOL_CONSISTENT")

    block = _dedupe(block)
    allow = wants_no_tool and semantic_no_tool_role and not block and float(decision_payload.get("conf") or 0.0) >= 0.6
    fallback_action = None if allow else _fallback_action(feature_payload, parsed)
    ok = allow or (not wants_no_tool and not block)
    return SemanticConsistencyResult(
        ok=ok,
        allow_no_tool=allow,
        block_codes=block,
        consistency_codes=_dedupe(codes),
        fallback_action=fallback_action,
    )


def _semantic_live_or_api_state_request(features: dict[str, Any], parsed: SemanticParse) -> bool:
    if parsed.target.grounding != "SUPPORTED_DATA_OBJECT":
        return False
    return bool(set(features.get("flags") or []) & {"LIVE", "CURRENT", "PLATFORM", "API"})


def _explicit_api_family_request(features: dict[str, Any], parsed: SemanticParse) -> bool:
    if parsed.target.grounding != "SUPPORTED_DATA_OBJECT":
        return False
    flags = set(features.get("flags") or [])
    caps = set(features.get("cap") or [])
    return "EXPLICIT_API_FAMILY" in flags or bool(caps & {"SCHEMA_REGISTRY", "FLOW_SERVICE", "TAGS", "AUDIT_EVENTS", "MERGE_POLICIES"})


def _contradicts_objective_features(features: dict[str, Any], parsed: SemanticParse) -> bool:
    if parsed.target.grounding in NO_TOOL_GROUNDINGS:
        return False
    has_data_surface = bool(features.get("retr") or features.get("count") or features.get("status") or features.get("date") or features.get("rel"))
    return bool(has_data_surface and parsed.evidence_need == "NONE")


def _has_surface_evidence_cues(features: dict[str, Any]) -> bool:
    return bool(features.get("retr") or features.get("count") or features.get("status") or features.get("date") or features.get("fields") or features.get("domain") or features.get("cap"))


def _fallback_action(features: dict[str, Any], parsed: SemanticParse) -> str:
    if parsed.target.grounding in {"CONCEPTUAL_OBJECT", "META_LANGUAGE", "OUT_OF_DOMAIN"}:
        return "LLM_SAFE_DIRECT"
    if parsed.capability.api_match and not parsed.capability.sql_match and parsed.target.grounding == "SUPPORTED_DATA_OBJECT":
        return "SAFE_API_PROBE"
    if parsed.target.grounding == "SUPPORTED_DATA_OBJECT" or parsed.evidence_need in {"SQL", "API", "SQL_API"}:
        return "EVIDENCE_PIPELINE"
    if features.get("domain") and features.get("cap") and not features.get("cue"):
        return "SAFE_API_PROBE"
    return "LLM_SAFE_DIRECT"


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return out
