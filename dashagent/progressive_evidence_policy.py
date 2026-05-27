from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .prompt_semantic_ir import ObjectivePromptFeatures
from .semantic_consistency_verifier import SemanticConsistencyResult
from .semantic_intent_classifier import SemanticIntentDecision
from .semantic_parse import SemanticParse


EARLY_ROUTE_ACTIONS = {"LLM_DIRECT", "LLM_SAFE_DIRECT", "SAFE_API_PROBE", "EVIDENCE_PIPELINE"}
NO_TOOL_GROUNDINGS = {"CONCEPTUAL_OBJECT", "META_LANGUAGE", "OUT_OF_DOMAIN"}
DATA_OPERATIONS = {"LIST", "COUNT", "LOOKUP", "STATUS", "DATE", "RELATIONSHIP"}
LIVE_API_CUES = {
    "LIVE",
    "CURRENT",
    "PLATFORM",
    "API",
    "LIVE_OR_CURRENT",
    "EXPLICIT_API_FAMILY",
    "SCHEMA_REGISTRY",
    "FLOW_SERVICE",
    "TAGS",
    "AUDIT_EVENTS",
    "MERGE_POLICIES",
    "SEGMENT_DEFINITIONS",
    "UPS_AUDIENCES",
    "CATALOG_DATASETS",
    "CATALOG_BATCHES",
}
API_FAMILY_TO_ENDPOINT = {
    "SCHEMA_REGISTRY": "schemas_short",
    "FLOW_SERVICE": "flowservice_flows",
    "TAGS": "unified_tags",
    "AUDIT_EVENTS": "audit_events",
    "MERGE_POLICIES": "merge_policies",
    "SEGMENT_DEFINITIONS": "segment_definitions",
    "UPS_AUDIENCES": "ups_audiences",
    "CATALOG_DATASETS": "catalog_datasets",
    "CATALOG_BATCHES": "catalog_batches",
}
ENDPOINT_TO_API_FAMILY = {endpoint: family for family, endpoint in API_FAMILY_TO_ENDPOINT.items()}
ENDPOINT_TO_API_FAMILY["schema_registry_schemas"] = "SCHEMA_REGISTRY"


@dataclass(frozen=True)
class ProgressiveEvidenceDecision:
    entry_action: str
    confidence: str
    reason_codes: list[str] = field(default_factory=list)
    risk_codes: list[str] = field(default_factory=list)
    allowed_early_exit: bool = False
    requires_evidence_pipeline: bool = True
    safe_api_probe: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if payload["entry_action"] not in EARLY_ROUTE_ACTIONS:
            payload["entry_action"] = "EVIDENCE_PIPELINE"
            payload["allowed_early_exit"] = False
            payload["requires_evidence_pipeline"] = True
        return payload


def decide_progressive_evidence_entry(
    *,
    features: ObjectivePromptFeatures | dict[str, Any],
    semantic_parse: SemanticParse | dict[str, Any],
    semantic_decision: SemanticIntentDecision | dict[str, Any],
    semantic_consistency: SemanticConsistencyResult | dict[str, Any],
    no_tool_safety: Any | None = None,
    safe_api_probe: dict[str, Any] | None = None,
) -> ProgressiveEvidenceDecision:
    feature_payload = features.to_dict() if isinstance(features, ObjectivePromptFeatures) else dict(features)
    parsed = semantic_parse if isinstance(semantic_parse, SemanticParse) else SemanticParse.from_dict(dict(semantic_parse))
    decision_payload = semantic_decision.to_dict() if isinstance(semantic_decision, SemanticIntentDecision) else dict(semantic_decision)
    consistency_payload = semantic_consistency.to_dict() if isinstance(semantic_consistency, SemanticConsistencyResult) else dict(semantic_consistency)
    safety_payload = no_tool_safety.to_dict() if hasattr(no_tool_safety, "to_dict") else dict(no_tool_safety or {})
    probe = dict(safe_api_probe or {})

    metrics = _capability_metrics(feature_payload, parsed, probe)
    no_tool_risks = _no_tool_risk_codes(feature_payload, parsed, decision_payload, consistency_payload, safety_payload, metrics)
    if _safe_no_tool_exit(parsed, decision_payload, consistency_payload, safety_payload, no_tool_risks):
        action = "LLM_DIRECT" if float(decision_payload.get("conf") or 0.0) >= 0.85 else "LLM_SAFE_DIRECT"
        return ProgressiveEvidenceDecision(
            entry_action=action,
            confidence="HIGH" if action == "LLM_DIRECT" else "MEDIUM",
            reason_codes=["SAFE_CONCEPTUAL_NO_TOOL"],
            risk_codes=[],
            allowed_early_exit=True,
            requires_evidence_pipeline=False,
            metrics=metrics,
        )

    probe_risks = _safe_api_probe_risk_codes(feature_payload, parsed, decision_payload, safety_payload, probe, metrics)
    if not probe_risks and _safe_api_probe_exit(parsed, decision_payload, probe, metrics):
        return ProgressiveEvidenceDecision(
            entry_action="SAFE_API_PROBE",
            confidence="HIGH",
            reason_codes=["SAFE_API_PROBE_SINGLE_ENDPOINT", "API_ONLY_OR_LIVE_OBJECT"],
            risk_codes=[],
            allowed_early_exit=True,
            requires_evidence_pipeline=False,
            safe_api_probe=probe,
            metrics=metrics,
        )

    risks = _dedupe([*no_tool_risks, *probe_risks])
    if not risks:
        risks = ["UNCERTAIN_REQUIRES_EVIDENCE_PIPELINE"]
    return ProgressiveEvidenceDecision(
        entry_action="EVIDENCE_PIPELINE",
        confidence="LOW" if "UNKNOWN_PARSE_WITH_DATA_SIGNAL" in risks or "API_FAMILY_CONFIDENCE_NOT_HIGH" in risks else "MEDIUM",
        reason_codes=["PROGRESSIVE_EVIDENCE_REQUIRED"],
        risk_codes=risks,
        allowed_early_exit=False,
        requires_evidence_pipeline=True,
        metrics=metrics,
    )


def _safe_no_tool_exit(
    parsed: SemanticParse,
    decision: dict[str, Any],
    consistency: dict[str, Any],
    safety: dict[str, Any],
    risk_codes: list[str],
) -> bool:
    return bool(
        parsed.target.grounding in NO_TOOL_GROUNDINGS
        and not parsed.target.instance_level
        and parsed.evidence_need == "NONE"
        and parsed.no_tool_safe
        and bool(decision.get("no_tool"))
        and bool(consistency.get("allow_no_tool"))
        and bool(safety.get("allow_no_tool", consistency.get("allow_no_tool")))
        and float(decision.get("conf") or 0.0) >= 0.78
        and float(parsed.confidence or 0.0) >= 0.75
        and not risk_codes
    )


def _safe_api_probe_exit(
    parsed: SemanticParse,
    decision: dict[str, Any],
    probe: dict[str, Any],
    metrics: dict[str, Any],
) -> bool:
    return bool(
        parsed.target.grounding == "SUPPORTED_DATA_OBJECT"
        and parsed.evidence_need in {"API", "SQL_API"}
        and bool(parsed.capability.api_match or decision.get("api"))
        and not bool(parsed.capability.sql_match)
        and metrics.get("api_family_confidence") == "HIGH"
        and metrics.get("api_family_count") == 1
        and probe.get("endpoint_id")
        and str(probe.get("method") or "").upper() == "GET"
        and not probe.get("unresolved_path_params")
    )


def _no_tool_risk_codes(
    features: dict[str, Any],
    parsed: SemanticParse,
    decision: dict[str, Any],
    consistency: dict[str, Any],
    safety: dict[str, Any],
    metrics: dict[str, Any],
) -> list[str]:
    risks: list[str] = []
    if parsed.filters.status or parsed.filters.date or parsed.filters.entity or parsed.filters.relationship:
        risks.append("STATUS_OR_FILTER_REQUIRES_EVIDENCE")
    if parsed.target.grounding == "SUPPORTED_DATA_OBJECT":
        risks.append("SUPPORTED_DATA_OBJECT_REQUIRES_EVIDENCE")
    if parsed.target.instance_level:
        risks.append("INSTANCE_LEVEL_REQUIRES_EVIDENCE")
    if parsed.operation in DATA_OPERATIONS and (parsed.target.grounding == "SUPPORTED_DATA_OBJECT" or parsed.evidence_need in {"SQL", "API", "SQL_API"}):
        risks.append("DATA_OPERATION_REQUIRES_EVIDENCE")
    if parsed.evidence_need in {"SQL", "API", "SQL_API"}:
        risks.append("EVIDENCE_NEED_REQUIRES_PIPELINE")
    if parsed.requested_fields:
        risks.append("REQUESTED_FIELDS_REQUIRES_EVIDENCE")
    if _has_live_api_cue(features, parsed):
        risks.append("LIVE_API_CUE_REQUIRES_EVIDENCE")
    if _has_explicit_api_family(features, parsed):
        risks.append("EXPLICIT_API_FAMILY_REQUIRES_EVIDENCE")
    if _mixed_conceptual_data(features, parsed):
        risks.append("MIXED_CONCEPTUAL_DATA_REQUIRES_EVIDENCE")
    if parsed.target.grounding == "UNKNOWN" and metrics.get("concrete_data_signal"):
        risks.append("UNKNOWN_PARSE_WITH_DATA_SIGNAL")
    if decision.get("no_tool") and not consistency.get("allow_no_tool"):
        risks.append("SEMANTIC_CONSISTENCY_BLOCKED_NO_TOOL")
    if safety.get("block"):
        risks.append("NO_TOOL_SAFETY_BLOCKED")
    return _dedupe(risks)


def _safe_api_probe_risk_codes(
    features: dict[str, Any],
    parsed: SemanticParse,
    decision: dict[str, Any],
    safety: dict[str, Any],
    probe: dict[str, Any],
    metrics: dict[str, Any],
) -> list[str]:
    risks: list[str] = []
    if parsed.target.grounding != "SUPPORTED_DATA_OBJECT":
        risks.append("API_PROBE_TARGET_NOT_SUPPORTED_DATA_OBJECT")
    if parsed.evidence_need not in {"API", "SQL_API"} and not decision.get("api"):
        risks.append("API_PROBE_EVIDENCE_NEED_NOT_API")
    if parsed.capability.sql_match:
        risks.append("SQL_MATCH_NOT_LOW_FOR_API_PROBE")
    if metrics.get("api_family_confidence") != "HIGH":
        risks.append("API_FAMILY_CONFIDENCE_NOT_HIGH")
    if int(metrics.get("api_family_count") or 0) != 1:
        risks.append("API_FAMILY_NOT_UNIQUE")
    if not probe.get("endpoint_id"):
        risks.append("NO_SAFE_API_PROBE_ENDPOINT")
    if str(probe.get("method") or "").upper() != "GET":
        risks.append("API_PROBE_METHOD_NOT_SAFE_GET")
    if probe.get("unresolved_path_params") or "{" in str(probe.get("path") or ""):
        risks.append("API_PROBE_UNRESOLVED_PATH_PARAM")
    if _conceptual_or_meta(features, parsed):
        risks.append("API_PROBE_CONCEPTUAL_OR_META_PROMPT")
    if not (_has_live_api_cue(features, parsed) or _has_explicit_api_family(features, parsed) or parsed.evidence_need == "API" or safety.get("clear_safe_api_family")):
        risks.append("API_PROBE_NOT_STRONGLY_SUPPORTED")
    if probe.get("endpoint_id") and metrics.get("matched_endpoint_family") and metrics.get("selected_api_family") != metrics.get("matched_endpoint_family"):
        risks.append("API_PROBE_ENDPOINT_FAMILY_MISMATCH")
    return _dedupe(risks)


def _capability_metrics(features: dict[str, Any], parsed: SemanticParse, probe: dict[str, Any]) -> dict[str, Any]:
    families = _api_families(features, parsed)
    selected_family = families[0] if len(families) == 1 else None
    endpoint_id = str(probe.get("endpoint_id") or "")
    matched_endpoint_family = ENDPOINT_TO_API_FAMILY.get(endpoint_id)
    concrete_signal = bool(
        parsed.target.grounding == "SUPPORTED_DATA_OBJECT"
        and (
            features.get("retr")
            or features.get("count")
            or features.get("status")
            or features.get("date")
            or features.get("rel")
            or parsed.target.instance_level
            or parsed.evidence_need in {"SQL", "API", "SQL_API"}
        )
    )
    return {
        "sql_match": float(1.0 if parsed.capability.sql_match else 0.0),
        "api_match": float(1.0 if parsed.capability.api_match else 0.0),
        "concrete_data_signal": concrete_signal,
        "live_api_signal": _has_live_api_cue(features, parsed),
        "api_required_signal": _has_explicit_api_family(features, parsed) or parsed.evidence_need == "API",
        "api_family_count": len(families),
        "api_families": families,
        "api_family_confidence": "HIGH" if len(families) == 1 and (selected_family in API_FAMILY_TO_ENDPOINT or matched_endpoint_family == selected_family) else ("LOW" if not families else "MEDIUM"),
        "selected_api_family": selected_family,
        "matched_endpoint_family": matched_endpoint_family,
        "safe_api_candidates": [probe] if probe.get("endpoint_id") else [],
    }


def _api_families(features: dict[str, Any], parsed: SemanticParse) -> list[str]:
    families: list[str] = []
    for family in parsed.capability.api_families:
        families.append(_normalize_family(family))
    for code in features.get("cap") or []:
        text = str(code).upper()
        if text.startswith("API_"):
            families.append(_normalize_family(text[4:]))
        elif text in API_FAMILY_TO_ENDPOINT:
            families.append(text)
    return _dedupe([family for family in families if family in API_FAMILY_TO_ENDPOINT])


def _normalize_family(value: str) -> str:
    text = str(value or "").upper()
    aliases = {
        "API_SCHEMA_REGISTRY": "SCHEMA_REGISTRY",
        "SCHEMA_REGISTRY": "SCHEMA_REGISTRY",
        "API_FLOW_SERVICE": "FLOW_SERVICE",
        "FLOW_SERVICE": "FLOW_SERVICE",
        "API_TAGS": "TAGS",
        "TAGS": "TAGS",
        "API_AUDIT_EVENTS": "AUDIT_EVENTS",
        "AUDIT_EVENTS": "AUDIT_EVENTS",
        "API_MERGE_POLICIES": "MERGE_POLICIES",
        "MERGE_POLICIES": "MERGE_POLICIES",
        "API_SEGMENT_DEFINITIONS": "SEGMENT_DEFINITIONS",
        "SEGMENT_DEFINITIONS": "SEGMENT_DEFINITIONS",
        "API_UPS_AUDIENCES": "UPS_AUDIENCES",
        "UPS_AUDIENCES": "UPS_AUDIENCES",
        "API_CATALOG_DATASETS": "CATALOG_DATASETS",
        "CATALOG_DATASETS": "CATALOG_DATASETS",
        "API_CATALOG_BATCHES": "CATALOG_BATCHES",
        "CATALOG_BATCHES": "CATALOG_BATCHES",
    }
    return aliases.get(text, text)


def _has_live_api_cue(features: dict[str, Any], parsed: SemanticParse) -> bool:
    if parsed.target.grounding in NO_TOOL_GROUNDINGS and parsed.evidence_need == "NONE":
        return False
    flags = set(str(value) for value in features.get("flags") or [])
    caps = set(_normalize_family(str(value)) for value in features.get("cap") or [])
    return bool(flags & LIVE_API_CUES or caps & LIVE_API_CUES or parsed.evidence_need == "API")


def _has_explicit_api_family(features: dict[str, Any], parsed: SemanticParse) -> bool:
    flags = set(str(value) for value in features.get("flags") or [])
    return bool("EXPLICIT_API_FAMILY" in flags or parsed.capability.api_families and parsed.evidence_need == "API")


def _mixed_conceptual_data(features: dict[str, Any], parsed: SemanticParse) -> bool:
    if parsed.target.grounding in NO_TOOL_GROUNDINGS and parsed.evidence_need == "NONE":
        return False
    return bool("MIXED_CONCEPT_AND_RETRIEVAL" in set(features.get("flags") or []))


def _conceptual_or_meta(features: dict[str, Any], parsed: SemanticParse) -> bool:
    return bool(parsed.target.grounding in {"CONCEPTUAL_OBJECT", "META_LANGUAGE"} or features.get("conceptual_object_terms") or features.get("meta_language_indicators"))


def _dedupe(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return out
