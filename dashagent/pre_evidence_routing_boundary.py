from __future__ import annotations

import re
from typing import Any


DIRECT_LLM_ACTIONS = {"LLM_DIRECT", "LLM_SAFE_DIRECT"}
SQL_FIRST_FIXED_STRATEGIES = {
    "SQL_FIRST_API_VERIFY",
    "SQL_FIRST_API_VERIFY_LLM_ANSWER_VERIFIER",
    "SQL_FIRST_API_VERIFY_HYBRID_ANSWER",
    "SQL_FIRST_API_VERIFY_CONCISE_LLM_REWRITE",
}
NO_EVIDENCE_GROUNDINGS = {"CONCEPTUAL_OBJECT", "META_LANGUAGE", "OUT_OF_DOMAIN"}
DATA_OPERATIONS = {"LIST", "COUNT", "LOOKUP", "STATUS", "DATE", "RELATIONSHIP"}
CONCRETE_DATA_SIGNAL_RE = re.compile(
    r"\b("
    r"how many|count|number|total|show|give me|current|status|date|recent|live|api|platform|"
    r"do i have|my|active|inactive|failed|succeeded|published|created|updated"
    r")\b",
    re.I,
)


def should_bypass_evidence_for_llm_direct(
    route_decision: Any,
    strategy: str | None = None,
    prompt: str | None = None,
) -> bool:
    """
    Return True only when the pre-evidence router already made a high-confidence
    pure general/concept/meta decision and no runtime evidence is required.
    """

    if _is_fixed_sql_first_strategy(strategy):
        return False

    payload = _as_dict(route_decision)
    action = _route_action(payload)
    if action not in DIRECT_LLM_ACTIONS:
        return False
    if not _has_safe_confidence(payload):
        return False
    if _requires_evidence(payload):
        return False
    semantic_parse = _as_dict(payload.get("semantic_parse"))
    if not _is_pure_no_evidence_parse(semantic_parse):
        return False
    if _is_mixed(payload):
        return False
    if _is_ambiguous_data_like(payload):
        return False
    if _has_concrete_data_signal(payload, prompt):
        return False
    return True


def _as_dict(value: Any) -> dict[str, Any]:
    if hasattr(value, "to_dict"):
        value = value.to_dict()
    return dict(value) if isinstance(value, dict) else {}


def _route_action(payload: dict[str, Any]) -> str:
    return str(
        payload.get("action")
        or payload.get("entry_action")
        or payload.get("mode")
        or payload.get("route")
        or ""
    ).upper()


def _is_fixed_sql_first_strategy(strategy: str | None) -> bool:
    return str(strategy or "").upper() in SQL_FIRST_FIXED_STRATEGIES


def _has_safe_confidence(payload: dict[str, Any]) -> bool:
    semantic_decision = _as_dict(payload.get("semantic_intent_decision"))
    semantic_parse = _as_dict(payload.get("semantic_parse"))
    progressive = _progressive_policy(payload)
    numeric_candidates = [
        _float_or_none(payload.get("confidence")),
        _float_or_none(semantic_decision.get("conf")),
        _float_or_none(semantic_parse.get("confidence")),
    ]
    numeric_confidence = max([value for value in numeric_candidates if value is not None] or [0.0])
    progressive_confidence = str(progressive.get("confidence") or "").upper()
    if progressive_confidence == "HIGH":
        return numeric_confidence >= 0.75
    return numeric_confidence >= 0.8


def _requires_evidence(payload: dict[str, Any]) -> bool:
    semantic_decision = _as_dict(payload.get("semantic_intent_decision"))
    semantic_parse = _as_dict(payload.get("semantic_parse"))
    no_tool_safety = _as_dict(payload.get("no_tool_safety"))
    progressive = _progressive_policy(payload)
    if progressive.get("requires_evidence_pipeline") is True:
        return True
    if payload.get("requires_evidence") is True:
        return True
    if payload.get("requires_database") is True or payload.get("requires_api") is True:
        return True
    if str(semantic_decision.get("need") or "NONE").upper() not in {"NONE", ""}:
        return True
    if semantic_decision and not bool(semantic_decision.get("no_tool")):
        return True
    if str(semantic_parse.get("evidence_need") or "NONE").upper() not in {"NONE", ""}:
        return True
    if semantic_parse and not bool(semantic_parse.get("no_tool_safe")):
        return True
    if no_tool_safety and not bool(no_tool_safety.get("allow_no_tool")):
        return True
    return False


def _is_mixed(payload: dict[str, Any]) -> bool:
    semantic_decision = _as_dict(payload.get("semantic_intent_decision"))
    semantic_parse = _as_dict(payload.get("semantic_parse"))
    features = _as_dict(payload.get("features"))
    if _is_pure_no_evidence_parse(semantic_parse):
        return False
    flags = {str(value).upper() for value in _list(features.get("flags"))}
    intent = str(semantic_decision.get("intent") or "").upper()
    evidence_need = str(semantic_parse.get("evidence_need") or "").upper()
    return bool(intent == "MIXED" or evidence_need == "SQL_API" or "MIXED_CONCEPT_AND_RETRIEVAL" in flags)


def _is_ambiguous_data_like(payload: dict[str, Any]) -> bool:
    semantic_decision = _as_dict(payload.get("semantic_intent_decision"))
    progressive = _progressive_policy(payload)
    metrics = _as_dict(progressive.get("metrics"))
    intent = str(semantic_decision.get("intent") or "").upper()
    risk_codes = {str(value).upper() for value in _list(progressive.get("risk_codes"))}
    return bool(
        intent == "AMBIG"
        and (
            metrics.get("concrete_data_signal") is True
            or "UNKNOWN_TARGET_WITH_DATA_SIGNAL" in risk_codes
            or "AMBIGUITY_REQUIRES_EVIDENCE" in risk_codes
        )
    )


def _has_concrete_data_signal(payload: dict[str, Any], prompt: str | None) -> bool:
    semantic_parse = _as_dict(payload.get("semantic_parse"))
    no_tool_safety = _as_dict(payload.get("no_tool_safety"))
    target = _as_dict(semantic_parse.get("target"))
    filters = _as_dict(semantic_parse.get("filters"))
    capability = _as_dict(semantic_parse.get("capability"))
    grounding = str(target.get("grounding") or "").upper()
    operation = str(semantic_parse.get("operation") or "").upper()
    pure_no_evidence = _is_pure_no_evidence_parse(semantic_parse)
    if grounding == "SUPPORTED_DATA_OBJECT":
        return True
    if bool(target.get("instance_level")):
        return True
    if semantic_parse.get("requested_fields"):
        return True
    if any(filters.get(key) for key in ("status", "date", "entity", "relationship")):
        return True
    if (capability.get("api_match") is True or capability.get("api_families")) and not pure_no_evidence:
        return True
    if no_tool_safety.get("has_concrete_data_signal") is True and not pure_no_evidence:
        return True
    if operation in DATA_OPERATIONS and grounding not in NO_EVIDENCE_GROUNDINGS:
        return True
    if _prompt_has_concrete_data_signal(prompt) and not _is_pure_no_evidence_parse(semantic_parse):
        return True
    return False


def _is_pure_no_evidence_parse(semantic_parse: dict[str, Any]) -> bool:
    target = _as_dict(semantic_parse.get("target"))
    grounding = str(target.get("grounding") or "").upper()
    evidence_need = str(semantic_parse.get("evidence_need") or "").upper()
    operation = str(semantic_parse.get("operation") or "").upper()
    return bool(
        grounding in NO_EVIDENCE_GROUNDINGS
        and evidence_need == "NONE"
        and operation in {"DEFINE", "EXPLAIN", "COMPARE", "FORMAT_REQUEST", "META_LANGUAGE", "UNKNOWN"}
    )


def _prompt_has_concrete_data_signal(prompt: str | None) -> bool:
    return bool(prompt and CONCRETE_DATA_SIGNAL_RE.search(prompt))


def _progressive_policy(payload: dict[str, Any]) -> dict[str, Any]:
    checkpoints = _as_dict(payload.get("checkpoints"))
    progressive = _as_dict(checkpoints.get("checkpoint_progressive_evidence_policy"))
    if progressive:
        return progressive
    return _as_dict(payload.get("progressive_evidence_policy"))


def _list(value: Any) -> list[Any]:
    if isinstance(value, dict) and isinstance(value.get("items"), list):
        return list(value.get("items") or [])
    return value if isinstance(value, list) else []


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
