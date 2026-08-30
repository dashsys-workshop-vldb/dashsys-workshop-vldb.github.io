from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .prompt_semantic_ir import ObjectivePromptFeatures
from .semantic_intent_classifier import SemanticIntentDecision


@dataclass(frozen=True)
class NoToolSafetyResult:
    allow_no_tool: bool
    block: list[str] = field(default_factory=list)
    evidence_need_score: float = 0.0
    no_tool_safety_score: float = 0.0
    capability_match_score: float = 0.0
    clear_safe_api_family: bool = False
    has_concrete_data_signal: bool = False
    action: str = "BLOCK_NO_TOOL"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in ("final_route", "api_policy", "sql_route", "route"):
            payload.pop(key, None)
        payload["evidence_need_score"] = round(float(self.evidence_need_score), 4)
        payload["no_tool_safety_score"] = round(float(self.no_tool_safety_score), 4)
        payload["capability_match_score"] = round(float(self.capability_match_score), 4)
        return payload


def verify_no_tool_safety(
    features: ObjectivePromptFeatures | dict[str, Any],
    decision: SemanticIntentDecision | dict[str, Any],
) -> NoToolSafetyResult:
    feature_payload = features.to_dict() if isinstance(features, ObjectivePromptFeatures) else dict(features)
    if isinstance(decision, SemanticIntentDecision):
        decision_payload = decision.to_dict()
    else:
        decision_payload = dict(decision)
    block: list[str] = []
    retr = list(feature_payload.get("retr") or [])
    count = list(feature_payload.get("count") or [])
    fields = list(feature_payload.get("fields") or [])
    status = list(feature_payload.get("status") or [])
    date = list(feature_payload.get("date") or [])
    rel = list(feature_payload.get("rel") or [])
    entity = list(feature_payload.get("entity") or [])
    cap = list(feature_payload.get("cap") or [])
    domain = list(feature_payload.get("domain") or [])
    conf = float(decision_payload.get("conf") or 0.0)

    if retr:
        block.append("RETR")
    if count:
        block.append("COUNT")
    if fields:
        block.append("FIELDS")
    concrete_entity = bool(entity)
    if status and (concrete_entity or retr):
        block.append("STATUS")
    if date and (concrete_entity or retr):
        block.append("DATE")
    if rel:
        block.append("REL")
    if concrete_entity and (retr or count or fields or status or date or rel or domain):
        block.append("ENTITY_LOOKUP")
    if conf < 0.75:
        block.append("LOW_CONF")

    block = _dedupe(block)
    has_concrete_data_signal = any(code in block for code in ("RETR", "COUNT", "FIELDS", "DATE", "STATUS", "REL", "ENTITY_LOOKUP"))
    evidence_need_score = min(
        1.0,
        (0.23 if retr else 0.0)
        + (0.27 if count else 0.0)
        + (0.18 if fields else 0.0)
        + (0.2 if rel else 0.0)
        + (0.17 if status and (concrete_entity or retr) else 0.0)
        + (0.17 if date and (concrete_entity or retr) else 0.0)
        + (0.2 if concrete_entity and domain else 0.0)
        + (0.1 if domain and not has_concrete_data_signal else 0.0),
    )
    clear_safe_api_family = bool(decision_payload.get("api") and not decision_payload.get("sql")) or bool(
        {"API_TAGS", "API_AUDIT_EVENTS", "API_MERGE_POLICIES"} & set(cap)
    )
    capability_match_score = min(1.0, len(cap) / 4.0)
    allow = bool(decision_payload.get("no_tool")) and not block
    no_tool_safety_score = max(0.0, 1.0 - evidence_need_score - (0.25 if conf < 0.75 else 0.0))
    return NoToolSafetyResult(
        allow_no_tool=allow,
        block=block,
        evidence_need_score=evidence_need_score,
        no_tool_safety_score=no_tool_safety_score,
        capability_match_score=capability_match_score,
        clear_safe_api_family=clear_safe_api_family,
        has_concrete_data_signal=has_concrete_data_signal,
        action="ALLOW_NO_TOOL" if allow else "BLOCK_NO_TOOL",
    )


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out
