from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .prompt_semantic_ir import ObjectivePromptFeatures, extract_objective_prompt_features


LIVE_WORDS = {"current", "live", "platform", "api", "adobe", "endpoint"}
API_PRIMARY_DOMAINS = {"TAG", "AUDIT", "MERGE_POLICY"}
API_FAMILY_DOMAINS = {"TAG", "AUDIT", "MERGE_POLICY", "DATAFLOW", "FLOW", "BATCH", "SEGMENT", "AUDIENCE", "DATASET", "SCHEMA"}
SQL_FAMILY_DOMAINS = {"SCHEMA", "SEGMENT", "AUDIENCE", "DATASET", "JOURNEY", "CAMPAIGN", "DATAFLOW", "FLOW", "DESTINATION", "CONNECTOR", "FIELD"}


@dataclass(frozen=True)
class EvidenceMatchScore:
    sql_match: float
    api_match: float
    sql_match_codes: list[str] = field(default_factory=list)
    api_match_codes: list[str] = field(default_factory=list)
    concrete_data_signal: bool = False
    live_api_signal: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["sql_match"] = round(float(self.sql_match), 4)
        payload["api_match"] = round(float(self.api_match), 4)
        return payload


def score_evidence_match(
    features_or_query: ObjectivePromptFeatures | dict[str, Any] | str,
    *,
    relevance_result: Any | None = None,
    sql_candidate_available: bool | None = None,
    api_candidate_available: bool | None = None,
    endpoint_health: dict[str, Any] | None = None,
) -> EvidenceMatchScore:
    features = _feature_payload(features_or_query)
    norm = str(features.get("norm") or features.get("p") or "").lower()
    domains = set(str(item) for item in features.get("domain") or features.get("domain_terms") or [])
    caps = set(str(item) for item in features.get("cap") or features.get("capability_matches") or [])
    retr = bool(features.get("retr") or features.get("retrieval_cues"))
    count = bool(features.get("count") or features.get("count_cues"))
    fields = bool(features.get("fields") or features.get("field_cues"))
    status = bool(features.get("status") or features.get("status_cues"))
    date = bool(features.get("date") or features.get("date_cues"))
    rel = bool(features.get("rel") or features.get("relationship_cues"))
    entity = bool(features.get("entity") or features.get("entities"))
    concrete = bool(retr or count or fields or rel or entity or status or date)
    live_signal = any(word in norm.split() for word in LIVE_WORDS) or "current adobe" in norm or "live api" in norm

    sql_score = 0.0
    api_score = 0.0
    sql_codes: list[str] = []
    api_codes: list[str] = []

    if domains & SQL_FAMILY_DOMAINS:
        sql_score += 0.35
        sql_codes.append("SQL_DOMAIN_MATCH")
    if any(code.startswith("SQL_") for code in caps):
        sql_score += 0.25
        sql_codes.append("SQL_CAPABILITY_MATCH")
    if retr or count or fields or status or date or rel:
        sql_score += 0.25
        sql_codes.append("CONCRETE_DATA_SIGNAL")
    if sql_candidate_available is True:
        sql_score += 0.15
        sql_codes.append("SQL_CANDIDATE_AVAILABLE")
    if getattr(relevance_result, "tables", None):
        sql_score += 0.1
        sql_codes.append("RELEVANT_TABLES")

    if domains & API_FAMILY_DOMAINS:
        api_score += 0.25
        api_codes.append("API_DOMAIN_MATCH")
    if domains & API_PRIMARY_DOMAINS:
        api_score += 0.25
        api_codes.append("API_PRIMARY_DOMAIN")
    if any(code.startswith("API_") for code in caps):
        api_score += 0.2
        api_codes.append("API_CAPABILITY_MATCH")
    if live_signal:
        api_score += 0.25
        api_codes.append("LIVE_API_SIGNAL")
    if status and domains & {"TAG", "AUDIT", "MERGE_POLICY", "DATAFLOW", "FLOW"}:
        api_score += 0.1
        api_codes.append("API_STATUS_FAMILY")
    if api_candidate_available is True:
        api_score += 0.15
        api_codes.append("API_CANDIDATE_AVAILABLE")
    if getattr(relevance_result, "apis", None):
        api_score += 0.1
        api_codes.append("RELEVANT_APIS")
    if endpoint_health and endpoint_health.get("live_success_count"):
        api_score += 0.05
        api_codes.append("ENDPOINT_HEALTH_LIVE_SUCCESS")

    if not concrete and not live_signal:
        sql_score = min(sql_score, 0.35)
        api_score = min(api_score, 0.35)

    return EvidenceMatchScore(
        sql_match=min(1.0, round(sql_score, 4)),
        api_match=min(1.0, round(api_score, 4)),
        sql_match_codes=_dedupe(sql_codes),
        api_match_codes=_dedupe(api_codes),
        concrete_data_signal=concrete,
        live_api_signal=live_signal,
    )


def _feature_payload(features_or_query: ObjectivePromptFeatures | dict[str, Any] | str) -> dict[str, Any]:
    if isinstance(features_or_query, ObjectivePromptFeatures):
        return features_or_query.to_dict()
    if isinstance(features_or_query, str):
        return extract_objective_prompt_features(features_or_query).to_dict()
    return dict(features_or_query)


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out
