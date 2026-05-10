from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field


LLM_DIRECT = "LLM_DIRECT"
LOCAL_DB_ONLY = "LOCAL_DB_ONLY"
SQL_PLUS_API = "SQL_PLUS_API"
API_ONLY = "API_ONLY"

API_REQUIRED = "API_REQUIRED"
API_OPTIONAL = "API_OPTIONAL"
API_SKIP = "API_SKIP"


DATA_KEYWORDS = {
    "activation",
    "api",
    "audit",
    "audience",
    "batch",
    "batches",
    "campaign",
    "collection",
    "count",
    "current",
    "data flow",
    "dataflow",
    "dataset",
    "destination",
    "failed",
    "field",
    "file",
    "files",
    "find",
    "how many",
    "id",
    "journey",
    "list",
    "live",
    "merge policy",
    "metric",
    "observability",
    "platform",
    "profile",
    "property",
    "published",
    "sandbox",
    "schema",
    "segment",
    "show",
    "status",
    "tag",
    "tags",
    "timestamp",
}

CONCEPTUAL_PREFIXES = (
    "explain ",
    "what is ",
    "what are ",
    "define ",
    "describe ",
    "why ",
    "how does ",
    "summarize ",
    "give a fun ",
)

API_ONLY_KEYWORDS = {
    "audit",
    "batch",
    "batches",
    "file",
    "files",
    "merge policy",
    "merge policies",
    "observability",
    "platform",
    "sandbox",
    "tag",
    "tags",
}

LIVE_STATUS_KEYWORDS = {
    "api",
    "current",
    "failed",
    "live",
    "platform",
    "published",
    "sandbox",
    "status",
    "succeeded",
    "validate",
}

LOCAL_DB_KEYWORDS = {
    "audience",
    "campaign",
    "collection",
    "count",
    "dataset",
    "field",
    "find",
    "how many",
    "journey",
    "list",
    "local snapshot",
    "property",
    "schema",
    "segment",
    "show",
}


@dataclass(frozen=True)
class PromptRouteDecision:
    mode: str
    reason: str
    confidence: float
    matched_rules: list[str] = field(default_factory=list)
    risk: str = "medium"
    recommended_strategy: str = "SQL_FIRST_API_VERIFY"
    requires_database: bool = True
    requires_api: bool = False
    api_policy: str = API_OPTIONAL

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["confidence"] = round(float(self.confidence), 4)
        return payload


def route_prompt(query: str) -> PromptRouteDecision:
    lowered = normalize_prompt(query)
    matched_data = sorted(keyword for keyword in DATA_KEYWORDS if keyword in lowered)
    matched_api_only = sorted(keyword for keyword in API_ONLY_KEYWORDS if keyword in lowered)
    matched_live = sorted(keyword for keyword in LIVE_STATUS_KEYWORDS if keyword in lowered)
    matched_local = sorted(keyword for keyword in LOCAL_DB_KEYWORDS if keyword in lowered)
    conceptual = lowered.startswith(CONCEPTUAL_PREFIXES)

    if conceptual and not matched_data:
        return PromptRouteDecision(
            mode=LLM_DIRECT,
            reason="Conceptual prompt with no local DB/API evidence request.",
            confidence=0.9,
            matched_rules=["conceptual_prefix", "no_data_keywords"],
            risk="low",
            recommended_strategy=LLM_DIRECT,
            requires_database=False,
            requires_api=False,
            api_policy=API_SKIP,
        )

    if matched_api_only:
        return PromptRouteDecision(
            mode=API_ONLY,
            reason=f"API/platform family keyword(s): {', '.join(matched_api_only[:5])}.",
            confidence=0.9,
            matched_rules=[f"api_only:{keyword}" for keyword in matched_api_only[:8]],
            risk="medium",
            recommended_strategy="SQL_FIRST_API_VERIFY",
            requires_database=False,
            requires_api=True,
            api_policy=API_REQUIRED,
        )

    if matched_live:
        return PromptRouteDecision(
            mode=SQL_PLUS_API,
            reason=f"Live/status keyword(s) require SQL grounding plus API verification: {', '.join(matched_live[:5])}.",
            confidence=0.88,
            matched_rules=[f"sql_plus_api:{keyword}" for keyword in matched_live[:8]],
            risk="medium",
            recommended_strategy="SQL_FIRST_API_VERIFY",
            requires_database=True,
            requires_api=True,
            api_policy=API_OPTIONAL,
        )

    if matched_local:
        return PromptRouteDecision(
            mode=LOCAL_DB_ONLY,
            reason=f"Local snapshot keyword(s) can be answered from DuckDB/parquet: {', '.join(matched_local[:5])}.",
            confidence=0.84,
            matched_rules=[f"local_db:{keyword}" for keyword in matched_local[:8]],
            risk="low",
            recommended_strategy="SQL_FIRST_API_VERIFY",
            requires_database=True,
            requires_api=False,
            api_policy=API_SKIP,
        )

    if matched_data:
        return PromptRouteDecision(
            mode=SQL_PLUS_API,
            reason=f"Data/evidence keyword(s) found; route to evidence pipeline: {', '.join(matched_data[:5])}.",
            confidence=0.75,
            matched_rules=[f"data:{keyword}" for keyword in matched_data[:8]],
            risk="medium",
            recommended_strategy="SQL_FIRST_API_VERIFY",
            requires_database=True,
            requires_api=True,
            api_policy=API_OPTIONAL,
        )

    return PromptRouteDecision(
        mode=SQL_PLUS_API,
        reason="Ambiguous prompt; use the data pipeline to avoid unsupported facts.",
        confidence=0.6,
        matched_rules=["ambiguous_default_to_data_pipeline"],
        risk="high",
        recommended_strategy="SQL_FIRST_API_VERIFY",
        requires_database=True,
        requires_api=True,
        api_policy=API_OPTIONAL,
    )


def normalize_prompt(query: str) -> str:
    text = " ".join(query.lower().split())
    text = re.sub(r"[-_]+", " ", text)
    return text
