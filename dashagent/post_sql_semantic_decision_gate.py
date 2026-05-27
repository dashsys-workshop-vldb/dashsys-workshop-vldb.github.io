from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .minimal_correction_feedback import MinimalCorrectionFeedback, build_minimal_correction_feedback


@dataclass(frozen=True)
class PostSQLSemanticDecisionGateResult:
    ok: bool
    revision_required: bool
    conflict_codes: list[str] = field(default_factory=list)
    feedback: MinimalCorrectionFeedback | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "revision_required": self.revision_required,
            "conflict_codes": self.conflict_codes,
            "feedback": self.feedback.to_dict() if self.feedback else None,
            "feedback_token_estimate": self.feedback.token_estimate if self.feedback else 0,
        }


@dataclass(frozen=True)
class PostSQLRiskFallback:
    mode: str
    endpoint_id: str | None
    fallback_source: str
    fallback_reason_codes: list[str] = field(default_factory=list)
    semantic_certainty_claimed: bool = False
    confidence: float = 0.0
    codes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["confidence"] = round(float(self.confidence), 4)
        return payload


@dataclass(frozen=True)
class PostSQLExecutionVerification:
    ok: bool
    final_action: str
    source: str
    endpoint_id: str | None = None
    selected_api_families: list[str] = field(default_factory=list)
    blocked_families: list[str] = field(default_factory=list)
    codes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def gate_post_sql_semantic_decision(decision: Any, card: dict[str, Any]) -> PostSQLSemanticDecisionGateResult:
    payload = decision.to_dict() if hasattr(decision, "to_dict") else dict(decision)
    mode = str(payload.get("mode") or "CAVEAT_ONLY").upper()
    endpoint_id = payload.get("endpoint_id")
    conflicts: list[dict[str, Any]] = []
    if mode == "SKIP_API":
        conflicts.extend(_skip_conflicts(card))
    elif mode == "CALL_API":
        conflicts.extend(_call_conflicts(card, endpoint_id))
    conflict_codes = _dedupe([str(item["code"]) for item in conflicts])
    if not conflict_codes:
        return PostSQLSemanticDecisionGateResult(True, False, [])
    feedback = build_minimal_correction_feedback(
        task="REVISE_POST_SQL_API_DECISION",
        previous_decision={key: payload.get(key) for key in ("mode", "endpoint_id", "confidence", "conf", "codes")},
        conflicts=conflicts,
        must_reconsider=_must_reconsider(conflict_codes),
        allowed_outputs=_allowed_outputs_for_conflicts(conflict_codes),
        forbidden_outputs=_forbidden_outputs_for_conflicts(conflict_codes),
        output_schema=_output_schema_for_conflicts(conflict_codes, card),
    )
    return PostSQLSemanticDecisionGateResult(False, True, conflict_codes, feedback)


def risk_minimizing_post_sql_fallback(card: dict[str, Any]) -> PostSQLRiskFallback:
    safe_candidate = _first_safe_candidate(card)
    high_risk_codes = _skip_conflicts(card)
    if high_risk_codes:
        if safe_candidate:
            return PostSQLRiskFallback(
                mode="CALL_API",
                endpoint_id=str(safe_candidate.get("endpoint_id")),
                fallback_source="RISK_MINIMIZING_FALLBACK",
                fallback_reason_codes=_dedupe([str(item["code"]) for item in high_risk_codes]),
                confidence=0.0,
                codes=["FALLBACK_PRESERVE_API"],
            )
        return PostSQLRiskFallback(
            mode="CAVEAT_ONLY",
            endpoint_id=None,
            fallback_source="CAVEAT_UNSAFE_API_FALLBACK",
            fallback_reason_codes=[*_dedupe([str(item["code"]) for item in high_risk_codes]), "NO_SAFE_EXECUTABLE_API"],
            confidence=0.0,
            codes=["FALLBACK_CAVEAT_UNSAFE_API"],
        )
    sql_state = _sql_state(card)
    if (
        sql_state.get("direct_answer")
        and card.get("user_requested_scope") == "LOCAL_SNAPSHOT"
        and card.get("sql_result_scope") == "LOCAL_SNAPSHOT"
        and str(card.get("api_need_prior") or "").upper() in {"API_SKIP", "API_OPTIONAL"}
        and not _explicit_live_or_api(card)
    ):
        return PostSQLRiskFallback(
            mode="SKIP_API",
            endpoint_id=None,
            fallback_source="LOW_RISK_LOCAL_SQL_FALLBACK",
            fallback_reason_codes=["SQL_DIRECT_LOCAL_COMPLETE_API_SKIP"],
            confidence=0.0,
            codes=["FALLBACK_SKIP_OPTIONAL_API"],
        )
    if safe_candidate:
        return PostSQLRiskFallback(
            mode="CALL_API",
            endpoint_id=str(safe_candidate.get("endpoint_id")),
            fallback_source="RISK_MINIMIZING_FALLBACK",
            fallback_reason_codes=["UNCERTAIN_PRESERVE_EVIDENCE"],
            confidence=0.0,
            codes=["FALLBACK_PRESERVE_API"],
        )
    return PostSQLRiskFallback(
        mode="CAVEAT_ONLY",
        endpoint_id=None,
        fallback_source="CAVEAT_UNSAFE_API_FALLBACK",
        fallback_reason_codes=["NO_SAFE_EXECUTABLE_API"],
        confidence=0.0,
        codes=["FALLBACK_CAVEAT_UNSAFE_API"],
    )


def verify_post_sql_execution_contract(
    decision: Any,
    card: dict[str, Any],
    *,
    budget_available: bool = True,
    source: str = "LLM_DECISION_VERIFIED",
) -> PostSQLExecutionVerification:
    payload = decision.to_dict() if hasattr(decision, "to_dict") else dict(decision)
    mode = str(payload.get("mode") or "CAVEAT_ONLY").upper()
    endpoint_id = payload.get("endpoint_id")
    if mode == "SKIP_API":
        return PostSQLExecutionVerification(True, "SKIP_API", source, codes=["VERIFIED_SKIP_API"])
    if mode == "CAVEAT_ONLY":
        return PostSQLExecutionVerification(True, "CAVEAT_ONLY", source, codes=["VERIFIED_CAVEAT_ONLY"])
    selected = _candidate_by_endpoint(card, endpoint_id) if endpoint_id else _first_safe_candidate(card)
    if selected is None:
        return PostSQLExecutionVerification(False, "CAVEAT_ONLY", "CONTRACT_VERIFIER_BLOCKED", str(endpoint_id) if endpoint_id else None, [], [str(endpoint_id)] if endpoint_id else [], ["CALL_API_ENDPOINT_NOT_EXECUTABLE"])
    family = str(selected.get("family") or selected.get("endpoint_id"))
    if not budget_available:
        return PostSQLExecutionVerification(False, "CAVEAT_ONLY", "CONTRACT_VERIFIER_BLOCKED", str(selected.get("endpoint_id")), [], [family], ["API_BUDGET_UNAVAILABLE"])
    if selected.get("method") != "GET" or not selected.get("safe_get"):
        return PostSQLExecutionVerification(False, "CAVEAT_ONLY", "CONTRACT_VERIFIER_BLOCKED", str(selected.get("endpoint_id")), [], [family], ["UNSAFE_METHOD"])
    if selected.get("requires_path_param"):
        return PostSQLExecutionVerification(False, "CAVEAT_ONLY", "CONTRACT_VERIFIER_BLOCKED", str(selected.get("endpoint_id")), [], [family], ["UNRESOLVED_PATH_PARAM"])
    requested_roles = _requested_roles(card)
    can_answer = set(str(role) for role in selected.get("can_answer_roles") or selected.get("can_fill_roles") or [])
    if requested_roles and not (requested_roles & can_answer) and not _explicit_live_or_api(card):
        return PostSQLExecutionVerification(False, "CAVEAT_ONLY", "CONTRACT_VERIFIER_BLOCKED", str(selected.get("endpoint_id")), [], [family], ["API_NO_EVIDENCE_GAIN"])
    return PostSQLExecutionVerification(True, "CALL_API", source, str(selected.get("endpoint_id")), [family], [], ["VERIFIED_CALL_API"])


def _skip_conflicts(card: dict[str, Any]) -> list[dict[str, Any]]:
    conflicts: list[dict[str, Any]] = []
    sql_state = _sql_state(card)
    candidates = _candidates(card)
    safe_candidate = _first_safe_candidate(card)
    api_required = str(card.get("api_need_prior") or "").upper() == "API_REQUIRED" or bool((card.get("constraints") or {}).get("api_required_cannot_skip"))
    if api_required:
        conflicts.append({"code": "API_REQUIRED_CANNOT_SKIP", "given": "mode=SKIP_API", "required": "api_need_prior=API_REQUIRED"})
    if card.get("user_requested_scope") == "LIVE_PLATFORM" and card.get("sql_result_scope") == "LOCAL_SNAPSHOT":
        conflicts.append({"code": "SQL_SCOPE_MISMATCH", "given": "sql_scope=LOCAL_SNAPSHOT", "required": "user_scope=LIVE_PLATFORM"})
    if _explicit_api_family(card):
        conflicts.append({"code": "EXPLICIT_API_FAMILY_CANNOT_SKIP", "given": "mode=SKIP_API", "required": "explicit API family requested"})
    if _explicit_live_or_api(card):
        conflicts.append({"code": "LIVE_OR_STATUS_API_CUE_CANNOT_SKIP", "given": "mode=SKIP_API", "required": "live/current/platform/status/API cue present"})
    missing_roles = set(str(role) for role in sql_state.get("missing_roles") or [])
    if missing_roles and _candidate_can_fill(candidates, missing_roles):
        for candidate in candidates:
            roles = missing_roles & set(str(role) for role in candidate.get("can_fill_roles") or [])
            if roles:
                conflicts.append({"code": "MISSING_ROLES_CAN_BE_FILLED_BY_API", "role": sorted(roles)[0], "endpoint_id": str(candidate.get("endpoint_id"))})
                break
    if sql_state.get("execution") == "ERROR" and safe_candidate:
        conflicts.append({"code": "SQL_ERROR_API_CAN_ANSWER", "given": "sql_execution=ERROR", "endpoint_id": str(safe_candidate.get("endpoint_id"))})
    if sql_state.get("zero_rows") and (_explicit_live_or_api(card) or str(card.get("api_need_prior") or "").upper() == "API_REQUIRED") and safe_candidate:
        conflicts.append({"code": "SQL_ZERO_ROWS_LIVE_API_NEEDED", "given": "sql_zero_rows=true", "endpoint_id": str(safe_candidate.get("endpoint_id"))})
    scope_mismatch = card.get("user_requested_scope") == "LIVE_PLATFORM" and card.get("sql_result_scope") == "LOCAL_SNAPSHOT"
    api_required = str(card.get("api_need_prior") or "").upper() == "API_REQUIRED" or bool((card.get("constraints") or {}).get("api_required_cannot_skip"))
    if (api_required or scope_mismatch or _explicit_live_or_api(card)) and safe_candidate and _requested_roles(card) & set(str(role) for role in safe_candidate.get("can_answer_roles") or safe_candidate.get("can_fill_roles") or []):
        conflicts.append({"code": "API_CAN_ANSWER_REQUESTED_ROLE", "endpoint_id": str(safe_candidate.get("endpoint_id")), "role": sorted(_requested_roles(card))[0] if _requested_roles(card) else None})
    return _dedupe_conflicts(conflicts)


def _call_conflicts(card: dict[str, Any], endpoint_id: Any) -> list[dict[str, Any]]:
    conflicts: list[dict[str, Any]] = []
    selected = _candidate_by_endpoint(card, endpoint_id) if endpoint_id else _first_safe_candidate(card)
    if selected is None or selected.get("method") != "GET" or not selected.get("safe_get") or selected.get("requires_path_param"):
        conflicts.append({"code": "CALL_API_ENDPOINT_NOT_EXECUTABLE", "endpoint_id": str(endpoint_id) if endpoint_id else None})
        return conflicts
    requested = _requested_roles(card)
    can_answer = set(str(role) for role in selected.get("can_answer_roles") or selected.get("can_fill_roles") or [])
    if requested and not (requested & can_answer) and not _explicit_live_or_api(card):
        conflicts.append({"code": "API_NO_EVIDENCE_GAIN", "endpoint_id": str(selected.get("endpoint_id"))})
    return conflicts


def _must_reconsider(codes: list[str]) -> list[str]:
    mapping = {
        "API_REQUIRED_CANNOT_SKIP": "api_required",
        "SQL_SCOPE_MISMATCH": "scope_match",
        "EXPLICIT_API_FAMILY_CANNOT_SKIP": "api_family_request",
        "LIVE_OR_STATUS_API_CUE_CANNOT_SKIP": "live_status_scope",
        "MISSING_ROLES_CAN_BE_FILLED_BY_API": "missing_roles",
        "SQL_ERROR_API_CAN_ANSWER": "sql_error",
        "SQL_ZERO_ROWS_LIVE_API_NEEDED": "sql_zero_rows_live_scope",
        "API_CAN_ANSWER_REQUESTED_ROLE": "api_can_answer_requested_role",
        "CALL_API_ENDPOINT_NOT_EXECUTABLE": "endpoint_executability",
        "API_NO_EVIDENCE_GAIN": "api_evidence_gain",
    }
    return _dedupe([mapping.get(code, code.lower()) for code in codes])


def _allowed_outputs_for_conflicts(codes: list[str]) -> list[str]:
    if any(code.endswith("CANNOT_SKIP") or code in {"SQL_SCOPE_MISMATCH", "MISSING_ROLES_CAN_BE_FILLED_BY_API", "SQL_ERROR_API_CAN_ANSWER", "SQL_ZERO_ROWS_LIVE_API_NEEDED", "API_CAN_ANSWER_REQUESTED_ROLE"} for code in codes):
        return ["CALL_API", "CAVEAT_ONLY"]
    if "CALL_API_ENDPOINT_NOT_EXECUTABLE" in codes:
        return ["CAVEAT_ONLY", "SKIP_API"]
    return ["CALL_API", "SKIP_API", "CAVEAT_ONLY"]


def _forbidden_outputs_for_conflicts(codes: list[str]) -> list[str]:
    forbidden: list[str] = []
    if any(code.endswith("CANNOT_SKIP") or code in {"SQL_SCOPE_MISMATCH", "MISSING_ROLES_CAN_BE_FILLED_BY_API", "SQL_ERROR_API_CAN_ANSWER", "SQL_ZERO_ROWS_LIVE_API_NEEDED", "API_CAN_ANSWER_REQUESTED_ROLE"} for code in codes):
        forbidden.append("SKIP_API")
    if "CALL_API_ENDPOINT_NOT_EXECUTABLE" in codes:
        forbidden.append("CALL_API")
    return forbidden


def _output_schema_for_conflicts(codes: list[str], card: dict[str, Any]) -> dict[str, Any]:
    allowed = _allowed_outputs_for_conflicts(codes)
    endpoint_ids = [str(candidate.get("endpoint_id")) for candidate in _candidates(card)[:3] if candidate.get("endpoint_id")]
    return {
        "mode": "|".join(allowed),
        "endpoint_id": "|".join([*endpoint_ids, "null"]) if endpoint_ids else "null",
        "confidence": "0.0-1.0",
        "codes": ["short codes"],
    }


def _candidate_by_endpoint(card: dict[str, Any], endpoint_id: Any) -> dict[str, Any] | None:
    endpoint_text = str(endpoint_id or "")
    for candidate in _candidates(card):
        if endpoint_text and endpoint_text == str(candidate.get("endpoint_id")):
            return candidate
    return None


def _first_safe_candidate(card: dict[str, Any]) -> dict[str, Any] | None:
    for candidate in _candidates(card):
        if candidate.get("safe_get") and candidate.get("method") == "GET" and not candidate.get("requires_path_param"):
            return candidate
    return None


def _candidate_can_fill(candidates: list[dict[str, Any]], roles: set[str]) -> bool:
    return any(roles & set(str(role) for role in candidate.get("can_fill_roles") or []) for candidate in candidates)


def _requested_roles(card: dict[str, Any]) -> set[str]:
    sql_state = _sql_state(card)
    roles = set(str(role) for role in sql_state.get("missing_roles") or [])
    semantic_parse = card.get("semantic_parse") if isinstance(card.get("semantic_parse"), dict) else {}
    for field in semantic_parse.get("requested_fields") or []:
        mapping = {"COUNT": "count", "STATUS": "status", "CREATED_TIME": "timestamp", "UPDATED_TIME": "timestamp", "ID": "id", "NAME": "name"}
        roles.add(mapping.get(str(field).upper(), str(field).lower()))
    return {role for role in roles if role}


def _explicit_live_or_api(card: dict[str, Any]) -> bool:
    return bool(set(str(cue) for cue in card.get("explicit_cues") or []) & {"LIVE", "CURRENT", "PLATFORM", "API", "STATUS", "ACTIVE", "INACTIVE", "FAILED", "SUCCEEDED", "SCHEMA_REGISTRY", "FLOW_SERVICE", "TAGS", "AUDIT_EVENTS", "MERGE_POLICIES"})


def _explicit_api_family(card: dict[str, Any]) -> bool:
    cues = set(str(cue) for cue in card.get("explicit_cues") or [])
    return bool(cues & {"EXPLICIT_API_FAMILY", "SCHEMA_REGISTRY", "FLOW_SERVICE", "TAGS", "AUDIT_EVENTS", "MERGE_POLICIES"})


def _sql_state(card: dict[str, Any]) -> dict[str, Any]:
    return card.get("sql_state") if isinstance(card.get("sql_state"), dict) else {}


def _candidates(card: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in card.get("api_candidates") or [] if isinstance(item, dict)]


def _dedupe(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return out


def _dedupe_conflicts(conflicts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for conflict in conflicts:
        code = str(conflict.get("code") or "")
        if code and code not in seen:
            seen.add(code)
            out.append(conflict)
    return out
