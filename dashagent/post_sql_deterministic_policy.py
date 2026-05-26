from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


LIVE_CODES = {"CURRENT", "LIVE", "PLATFORM", "API"}
LIVE_DOMAINS = {"TAG", "AUDIT", "MERGE_POLICY"}


@dataclass(frozen=True)
class PostSQLDeterministicPolicy:
    suggestion: str
    confidence: str
    api_evidence_signal: float
    codes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["api_evidence_signal"] = round(float(self.api_evidence_signal), 4)
        return payload


def decide_post_sql_api_policy(card: dict[str, Any]) -> PostSQLDeterministicPolicy:
    sql_state = card.get("sql_state") if isinstance(card.get("sql_state"), dict) else {}
    features = set(str(item) for item in card.get("prompt_features") or [])
    candidates = [item for item in card.get("api_candidates") or [] if isinstance(item, dict)]
    valid_candidates = [item for item in candidates if item.get("safe_get") and not item.get("requires_path_param")]
    missing_roles = set(str(item) for item in sql_state.get("missing_roles") or [])
    live_intent = bool(features & LIVE_CODES or features & LIVE_DOMAINS)
    api_signal = _api_signal(features, valid_candidates)
    codes: list[str] = []

    if not valid_candidates:
        codes.append("NO_SAFE_API_CANDIDATE")
        if sql_state.get("direct_answer"):
            return PostSQLDeterministicPolicy("SKIP_API", "HIGH", 0.0, ["SQL_DIRECT_ANSWER", *codes])
        return PostSQLDeterministicPolicy("CAVEAT_ONLY", "LOW", 0.0, codes)

    if live_intent:
        codes.append("EXPLICIT_LIVE_OR_API_INTENT")
        return PostSQLDeterministicPolicy("CALL_API", "HIGH", max(api_signal, 0.85), codes)
    if sql_state.get("execution") == "ERROR":
        codes.append("SQL_ERROR_API_CAN_ANSWER")
        return PostSQLDeterministicPolicy("CALL_API", "HIGH", max(api_signal, 0.8), codes)
    if sql_state.get("zero_rows") and live_intent:
        codes.append("SQL_ZERO_ROWS_LIVE_INTENT")
        return PostSQLDeterministicPolicy("CALL_API", "HIGH", max(api_signal, 0.8), codes)
    if missing_roles and _candidate_can_fill(valid_candidates, missing_roles):
        critical_missing = missing_roles & {"status", "timestamp"}
        if critical_missing and _candidate_can_fill(valid_candidates, critical_missing):
            codes.append("SQL_MISSING_REQUESTED_FIELDS")
            return PostSQLDeterministicPolicy("CALL_API", "HIGH", max(api_signal, 0.76), codes)
        codes.append("SQL_PARTIAL_API_MAY_FILL")
        return PostSQLDeterministicPolicy("AMBIGUOUS", "MEDIUM", max(api_signal, 0.55), codes)
    if sql_state.get("direct_answer"):
        codes.append("SQL_DIRECT_ANSWER")
        return PostSQLDeterministicPolicy("SKIP_API", "HIGH", min(api_signal, 0.35), codes)
    if sql_state.get("partial_answer"):
        codes.append("SQL_PARTIAL_ANSWER")
        return PostSQLDeterministicPolicy("AMBIGUOUS", "MEDIUM", max(api_signal, 0.5), codes)
    if sql_state.get("zero_rows"):
        codes.append("SQL_ZERO_ROWS_NO_LIVE_INTENT")
        return PostSQLDeterministicPolicy("AMBIGUOUS", "MEDIUM", max(api_signal, 0.45), codes)
    codes.append("SQL_RESULT_QUALITY_UNCLEAR")
    return PostSQLDeterministicPolicy("AMBIGUOUS", "LOW", api_signal, codes)


def _candidate_can_fill(candidates: list[dict[str, Any]], roles: set[str]) -> bool:
    for candidate in candidates:
        candidate_roles = set(str(item) for item in candidate.get("can_fill_roles") or [])
        if roles & candidate_roles:
            return True
    return False


def _api_signal(features: set[str], candidates: list[dict[str, Any]]) -> float:
    score = 0.0
    if candidates:
        score += 0.35
    if features & LIVE_CODES or features & LIVE_DOMAINS:
        score += 0.4
    if features & {"RETR", "LIST", "SHOW", "STATUS", "FAILED", "SUCCEEDED"}:
        score += 0.15
    return min(1.0, score)
