from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .endpoint_catalog import EndpointCatalog
from .post_sql_llm_advisor import PostSQLAPIAdvice


@dataclass(frozen=True)
class VerifiedPostSQLAPIAction:
    final_action: str
    source: str
    selected_api_families: list[str] = field(default_factory=list)
    blocked_families: list[str] = field(default_factory=list)
    codes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def verify_post_sql_api_advice(
    advice: PostSQLAPIAdvice | dict[str, Any],
    card: dict[str, Any],
    endpoint_catalog: EndpointCatalog,
    *,
    api_required: bool = False,
    budget_available: bool = True,
) -> VerifiedPostSQLAPIAction:
    payload = advice.to_dict() if isinstance(advice, PostSQLAPIAdvice) else dict(advice)
    mode = str(payload.get("mode") or "CAVEAT_ONLY").upper()
    endpoint_id = payload.get("endpoint_id")
    candidates = [item for item in card.get("api_candidates") or [] if isinstance(item, dict)]
    candidate_by_id = {str(item.get("endpoint_id")): item for item in candidates if item.get("endpoint_id")}
    prompt_features = set(str(item) for item in card.get("prompt_features") or [])
    sql_state = card.get("sql_state") if isinstance(card.get("sql_state"), dict) else {}
    codes: list[str] = []

    if mode == "CALL_API":
        selected = candidate_by_id.get(str(endpoint_id)) if endpoint_id else _first_safe_candidate(candidates)
        if selected is None:
            endpoint = endpoint_catalog.by_id(str(endpoint_id)) if endpoint_id else None
            if endpoint is None:
                return _blocked("SKIP_API", ["UNKNOWN_ENDPOINT"], endpoint_id, payload)
            selected = {
                "endpoint_id": endpoint.id,
                "family": endpoint.id,
                "method": endpoint.method,
                "safe_get": endpoint.method == "GET",
                "requires_path_param": bool(endpoint.path_params),
                "can_fill_roles": [],
            }
        if not budget_available:
            return _blocked("SKIP_API", ["API_BUDGET_UNAVAILABLE"], selected.get("family"), payload)
        if selected.get("method") != "GET" or not selected.get("safe_get"):
            return _blocked("SKIP_API", ["UNSAFE_METHOD"], selected.get("family"), payload)
        if selected.get("requires_path_param"):
            return _blocked("SKIP_API", ["UNRESOLVED_PATH_PARAM"], selected.get("family"), payload)
        needed_roles = set(str(item) for item in payload.get("needed_roles") or [])
        can_fill = set(str(item) for item in selected.get("can_fill_roles") or [])
        live_or_api_intent = bool(prompt_features & {"CURRENT", "LIVE", "PLATFORM", "API", "TAG", "AUDIT", "MERGE_POLICY"})
        if needed_roles and not (needed_roles & can_fill) and not live_or_api_intent:
            return _blocked("SKIP_API", ["ROLE_MISMATCH"], selected.get("family"), payload)
        return VerifiedPostSQLAPIAction("CALL_API", _source(payload), [str(selected.get("family") or selected.get("endpoint_id"))], [], ["VERIFIED_CALL_API"])

    if mode == "SKIP_API":
        safe_candidate = _first_safe_candidate(candidates)
        if api_required and safe_candidate:
            return VerifiedPostSQLAPIAction("CALL_API", _blocked_source(payload), [str(safe_candidate.get("family") or safe_candidate.get("endpoint_id"))], [], ["API_REQUIRED_SKIP_BLOCKED"])
        if _explicit_live_or_api(prompt_features) and safe_candidate:
            return VerifiedPostSQLAPIAction("CALL_API", _blocked_source(payload), [str(safe_candidate.get("family") or safe_candidate.get("endpoint_id"))], [], ["LIVE_API_SKIP_BLOCKED"])
        if sql_state.get("execution") == "ERROR" and safe_candidate:
            return VerifiedPostSQLAPIAction("CALL_API", _blocked_source(payload), [str(safe_candidate.get("family") or safe_candidate.get("endpoint_id"))], [], ["SQL_ERROR_SKIP_BLOCKED"])
        return VerifiedPostSQLAPIAction("SKIP_API", _source(payload), [], [], ["VERIFIED_SKIP_API"])

    codes.append("VERIFIED_CAVEAT_ONLY")
    return VerifiedPostSQLAPIAction("CAVEAT_ONLY", _source(payload), [], [], codes)


def _first_safe_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    for candidate in candidates:
        if candidate.get("safe_get") and not candidate.get("requires_path_param"):
            return candidate
    return None


def _explicit_live_or_api(prompt_features: set[str]) -> bool:
    return bool(prompt_features & {"CURRENT", "LIVE", "PLATFORM", "API", "TAG", "AUDIT", "MERGE_POLICY"})


def _blocked(action: str, codes: list[str], family: Any = None, payload: dict[str, Any] | None = None) -> VerifiedPostSQLAPIAction:
    blocked = [str(family)] if family else []
    return VerifiedPostSQLAPIAction(action, _blocked_source(payload or {}), [], blocked, codes)


def _source(payload: dict[str, Any]) -> str:
    source = str(payload.get("source") or "LLM_ADVISOR_VERIFIED")
    if source == "DETERMINISTIC_BYPASS":
        return "DETERMINISTIC_HIGH_CONF"
    if source == "DETERMINISTIC_FALLBACK":
        return "DETERMINISTIC_FALLBACK"
    if source in {"LLM_ADVISOR", "LLM_ADVISOR_VERIFIED"}:
        return "LLM_ADVISOR_VERIFIED"
    return source


def _blocked_source(payload: dict[str, Any]) -> str:
    return "LLM_ADVISOR_BLOCKED" if _is_actual_llm_advice(payload) else _source(payload)


def _is_actual_llm_advice(payload: dict[str, Any]) -> bool:
    source = str(payload.get("source") or "LLM_ADVISOR")
    return source in {"LLM_ADVISOR", "LLM_ADVISOR_VERIFIED", "LLM_ADVISOR_BLOCKED"}
