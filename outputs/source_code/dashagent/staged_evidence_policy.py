from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .evidence_match_scorer import EvidenceMatchScore


@dataclass(frozen=True)
class InitialEvidenceBranch:
    first_branch: str
    second_branch_policy: str
    policy_codes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def decide_initial_evidence_branch(match_score: EvidenceMatchScore | dict[str, Any], query_analysis: Any | None = None) -> InitialEvidenceBranch:
    payload = match_score.to_dict() if isinstance(match_score, EvidenceMatchScore) else dict(match_score)
    sql_match = float(payload.get("sql_match") or 0.0)
    api_match = float(payload.get("api_match") or 0.0)
    concrete = bool(payload.get("concrete_data_signal"))
    codes: list[str] = []

    if sql_match >= 0.7 and api_match < 0.6:
        codes.append("SQL_HIGH_API_LOW")
        return InitialEvidenceBranch("SQL", "NONE", codes)
    if sql_match >= 0.7 and api_match >= 0.6:
        codes.append("SQL_HIGH_API_HIGH")
        return InitialEvidenceBranch("SQL", "API_AFTER_SQL_IF_NEEDED", codes)
    if sql_match < 0.5 and api_match >= 0.7:
        codes.append("SQL_LOW_API_HIGH")
        second = "SQL_AFTER_API_IF_NEEDED" if _local_context_may_help(query_analysis) else "NONE"
        return InitialEvidenceBranch("API", second, codes)
    if not concrete:
        codes.append("BOTH_LOW_NO_CONCRETE_SIGNAL")
        return InitialEvidenceBranch("NO_TOOL", "NONE", codes)
    codes.append("BOTH_LOW_CONCRETE_SIGNAL")
    return InitialEvidenceBranch("SQL", "API_AFTER_SQL_IF_NEEDED" if api_match >= 0.4 else "NONE", codes)


def _local_context_may_help(query_analysis: Any | None) -> bool:
    if query_analysis is None:
        return False
    route_type = str(getattr(query_analysis, "route_type", "") or "")
    domain_type = str(getattr(query_analysis, "domain_type", "") or "")
    return "SQL" in route_type or domain_type in {"DATASET_SCHEMA", "SEGMENT_AUDIENCE", "DESTINATION_DATAFLOW"}
