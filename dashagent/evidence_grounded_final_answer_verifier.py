from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

from .ambiguous_claim_llm_judge import judge_ambiguous_claim
from .answer_slots import AnswerSlots
from .evidence_allowed_fact_index import AllowedFactIndex, build_allowed_fact_index
from .evidence_bus import EvidenceBus
from .final_answer_claim_extractor import FinalAnswerClaim, extract_final_answer_claims
from .final_answer_claim_matcher import ClaimMatch, match_final_answer_claims
from .minimal_correction_feedback import build_minimal_correction_feedback


@dataclass(frozen=True)
class EvidenceGroundedFinalAnswerVerification:
    ok: bool
    unsupported_claims: list[dict[str, Any]] = field(default_factory=list)
    over_specified_claims: list[dict[str, Any]] = field(default_factory=list)
    needs_caveat_claims: list[dict[str, Any]] = field(default_factory=list)
    supported_claims: list[dict[str, Any]] = field(default_factory=list)
    ambiguous_claims: list[dict[str, Any]] = field(default_factory=list)
    action: str = "ACCEPT"
    claim_extractor: dict[str, Any] = field(default_factory=dict)
    claim_matcher: dict[str, Any] = field(default_factory=dict)
    allowed_fact_index: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FinalAnswerRewriteResult:
    final_answer: str
    verification: EvidenceGroundedFinalAnswerVerification
    first_pass_ok: bool
    rewrite_attempted: bool
    rewrite_success: bool
    fallback_used: bool
    feedback: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "final_answer": self.final_answer,
            "verification": self.verification.to_dict(),
            "first_pass_ok": self.first_pass_ok,
            "rewrite_attempted": self.rewrite_attempted,
            "rewrite_success": self.rewrite_success,
            "fallback_used": self.fallback_used,
            "feedback": self.feedback,
        }


def verify_evidence_grounded_final_answer(
    final_answer: str,
    *,
    answer_card: Any | None = None,
    slots: AnswerSlots | None = None,
    evidence_bus: EvidenceBus | dict[str, Any] | None = None,
    question: str = "",
    caveats: list[str] | None = None,
    missing_roles: list[str] | None = None,
    llm_judge_enabled: bool = False,
    llm_client: Any | None = None,
) -> EvidenceGroundedFinalAnswerVerification:
    index = build_allowed_fact_index(answer_card=answer_card, slots=slots, evidence_bus=evidence_bus, caveats=caveats, missing_roles=missing_roles)
    claims = extract_final_answer_claims(final_answer)
    matches = match_final_answer_claims(claims, index)
    matches = _judge_ambiguous(matches, index, question=question or getattr(slots, "query", ""), llm_judge_enabled=llm_judge_enabled, llm_client=llm_client)

    supported = [match.claim.to_dict() for match in matches if match.status == "SUPPORTED"]
    unsupported = [match.claim.to_dict() for match in matches if match.status == "UNSUPPORTED"]
    over = [match.claim.to_dict() for match in matches if match.status == "OVER_SPECIFIED"]
    needs_caveat = [match.claim.to_dict() for match in matches if match.status == "NEEDS_CAVEAT"]
    ambiguous = [match.claim.to_dict() for match in matches if match.status == "AMBIGUOUS"]
    ok = not unsupported and not over and not needs_caveat and not ambiguous
    action = "ACCEPT" if ok else ("FALLBACK_DETERMINISTIC" if _high_risk_failure(unsupported, over) else "REWRITE_WITH_FEEDBACK")
    return EvidenceGroundedFinalAnswerVerification(
        ok=ok,
        unsupported_claims=unsupported,
        over_specified_claims=over,
        needs_caveat_claims=needs_caveat,
        supported_claims=supported,
        ambiguous_claims=ambiguous,
        action=action,
        claim_extractor={"claim_count": len(claims), "claims": [claim.to_dict() for claim in claims]},
        claim_matcher={"matches": [match.to_dict() for match in matches]},
        allowed_fact_index=index.to_dict(),
    )


def verify_or_rewrite_final_answer(
    generated_answer: str,
    *,
    deterministic_answer: str,
    answer_card: Any | None = None,
    slots: AnswerSlots | None = None,
    evidence_bus: EvidenceBus | dict[str, Any] | None = None,
    question: str = "",
    caveats: list[str] | None = None,
    missing_roles: list[str] | None = None,
    rewrite_client: Any | None = None,
    llm_judge_enabled: bool = False,
    llm_client: Any | None = None,
) -> FinalAnswerRewriteResult:
    first = verify_evidence_grounded_final_answer(
        generated_answer,
        answer_card=answer_card,
        slots=slots,
        evidence_bus=evidence_bus,
        question=question,
        caveats=caveats,
        missing_roles=missing_roles,
        llm_judge_enabled=llm_judge_enabled,
        llm_client=llm_client,
    )
    if first.ok:
        return FinalAnswerRewriteResult(generated_answer, first, True, False, False, False)

    feedback = build_rewrite_feedback(first)
    if rewrite_client is not None:
        try:
            rewritten = _call_rewrite_client(rewrite_client, generated_answer, feedback)
            second = verify_evidence_grounded_final_answer(
                rewritten,
                answer_card=answer_card,
                slots=slots,
                evidence_bus=evidence_bus,
                question=question,
                caveats=caveats,
                missing_roles=missing_roles,
                llm_judge_enabled=llm_judge_enabled,
                llm_client=llm_client,
            )
            if second.ok:
                return FinalAnswerRewriteResult(rewritten, second, False, True, True, False, feedback)
            fallback = verify_evidence_grounded_final_answer(
                deterministic_answer,
                answer_card=answer_card,
                slots=slots,
                evidence_bus=evidence_bus,
                question=question,
                caveats=caveats,
                missing_roles=missing_roles,
                llm_judge_enabled=False,
            )
            return FinalAnswerRewriteResult(deterministic_answer, fallback, False, True, False, True, feedback)
        except Exception:
            pass
    fallback = verify_evidence_grounded_final_answer(
        deterministic_answer,
        answer_card=answer_card,
        slots=slots,
        evidence_bus=evidence_bus,
        question=question,
        caveats=caveats,
        missing_roles=missing_roles,
        llm_judge_enabled=False,
    )
    return FinalAnswerRewriteResult(deterministic_answer, fallback, False, rewrite_client is not None, False, True, feedback)


def build_rewrite_feedback(verification: EvidenceGroundedFinalAnswerVerification) -> dict[str, Any]:
    blocked = verification.unsupported_claims + verification.over_specified_claims + verification.needs_caveat_claims + verification.ambiguous_claims
    blocked_claims = [_blocked_claim_payload(claim) for claim in blocked[:8]]
    allowed_facts = _allowed_facts_for_blocked_claims(blocked_claims, verification.allowed_fact_index)
    forbidden = _forbidden_claim_types(blocked_claims, verification.allowed_fact_index)
    minimal = build_minimal_correction_feedback(
        task="REWRITE_FINAL_ANSWER",
        previous_decision={"answer_action": verification.action},
        conflicts=[
            {
                "code": claim.get("issue") or "UNSUPPORTED_FINAL_ANSWER_CLAIM",
                "claim": claim.get("claim") or claim.get("text"),
                "given": claim.get("value") or claim.get("span") or claim.get("text"),
                "required": "use only relevant allowed facts/caveats",
            }
            for claim in blocked_claims
        ],
        must_reconsider=["unsupported_claims", "claim_scope", "missing_roles"],
        allowed_outputs=["REWRITE_WITH_ALLOWED_FACTS"],
        forbidden_outputs=forbidden,
        output_schema={"answer": "string"},
    )
    return {
        "task": "REWRITE_FINAL_ANSWER",
        "blocked_claims": blocked_claims,
        "allowed_facts": allowed_facts,
        "allowed_rewrite": _allowed_rewrite_shape(allowed_facts, verification.allowed_fact_index),
        "forbidden_claim_types": forbidden,
        "minimal_correction_feedback": minimal.to_dict(),
        "feedback_token_estimate": minimal.token_estimate,
    }


def _judge_ambiguous(
    matches: list[ClaimMatch],
    index: AllowedFactIndex,
    *,
    question: str,
    llm_judge_enabled: bool,
    llm_client: Any | None,
) -> list[ClaimMatch]:
    judged: list[ClaimMatch] = []
    for match in matches:
        if match.status != "AMBIGUOUS":
            judged.append(match)
            continue
        label = judge_ambiguous_claim(match.claim, question=question, allowed_fact_index=index, llm_client=llm_client, enabled=llm_judge_enabled)
        judged.append(ClaimMatch(match.claim, label, "llm_ambiguous_claim_judge"))
    return judged


def _high_risk_failure(unsupported: list[dict[str, Any]], over: list[dict[str, Any]]) -> bool:
    return bool(over or any(claim.get("type") in {"COUNT", "ID", "STATUS", "DATE", "RELATIONSHIP"} for claim in unsupported))


def _call_rewrite_client(client: Any, generated_answer: str, feedback: dict[str, Any]) -> str:
    messages = [
        {"role": "system", "content": "Rewrite the answer using only allowed facts. Return answer text only."},
        {"role": "user", "content": json.dumps({"answer": generated_answer, "feedback": feedback}, sort_keys=True)},
    ]
    if hasattr(client, "complete"):
        return str(client.complete(messages)).strip()
    if hasattr(client, "chat"):
        return str(client.chat(messages)).strip()
    if hasattr(client, "complete_json"):
        return str(client.complete_json(messages).get("answer", "")).strip()
    if hasattr(client, "generate_messages"):
        result = client.generate_messages(messages)
        if isinstance(result, dict):
            return str(result.get("content") or "").strip()
    raise TypeError("unsupported answer rewrite client")


def _blocked_claim_payload(claim: dict[str, Any]) -> dict[str, Any]:
    claim_type = str(claim.get("type") or "UNKNOWN")
    text = str(claim.get("text") or claim.get("span") or claim.get("value") or "")
    return {
        "claim": text[:180],
        "type": claim_type,
        "value": str(claim.get("value") or "")[:120],
        "issue": _issue_for_claim(claim),
    }


def _issue_for_claim(claim: dict[str, Any]) -> str:
    claim_type = str(claim.get("type") or "")
    text = f"{claim.get('text') or ''} {claim.get('value') or ''}".lower()
    if claim_type == "NO_DATA" and any(word in text for word in ("anywhere", "aep", "platform", "globally")):
        return "LIVE_EMPTY_AS_GLOBAL_ABSENCE"
    if claim_type == "NO_DATA":
        return "NO_DATA_REQUIRES_SCOPED_EMPTY_EVIDENCE"
    if claim_type in {"COUNT", "ID", "STATUS", "DATE", "RELATIONSHIP"}:
        return f"UNSUPPORTED_{claim_type}"
    if claim_type == "AMBIGUOUS":
        return "AMBIGUOUS_FACTUAL_CLAIM"
    return "UNSUPPORTED_FINAL_ANSWER_CLAIM"


def _allowed_facts_for_blocked_claims(blocked_claims: list[dict[str, Any]], index: dict[str, Any]) -> list[dict[str, str]]:
    facts: list[dict[str, str]] = []
    blocked_types = {str(claim.get("type")) for claim in blocked_claims}
    if "COUNT" in blocked_types:
        facts.extend({"role": "COUNT", "value": str(value)} for value in (index.get("counts") or [])[:5])
    if "ID" in blocked_types:
        facts.extend({"role": "ID", "value": str(value)} for value in (index.get("ids") or [])[:5])
    if "STATUS" in blocked_types:
        facts.extend({"role": "STATUS", "value": str(value)} for value in (index.get("statuses") or [])[:5])
    if "DATE" in blocked_types:
        facts.extend({"role": "DATE", "value": str(value)} for value in (index.get("dates") or [])[:5])
    if "RELATIONSHIP" in blocked_types:
        facts.extend({"role": "RELATIONSHIP", "value": str(value)} for value in (index.get("relationships") or [])[:5])
    caveats = set(index.get("allowed_caveats") or [])
    if "API_ERROR" in caveats:
        facts.append({"role": "CAVEAT", "value": "API_ERROR", "scope": _first(index.get("api_error_scopes"), "live api verification")})
    if "API_LIVE_EMPTY" in caveats:
        facts.append({"role": "CAVEAT", "value": "LIVE_EMPTY_SCOPED", "scope": _first(index.get("live_empty_scopes"), "query/scope")})
    if "SQL_EMPTY" in caveats:
        facts.append({"role": "CAVEAT", "value": "SQL_EMPTY_SCOPED", "scope": _first(index.get("live_empty_scopes"), "local snapshot")})
    if not facts:
        facts.extend({"role": "NAME", "value": str(value)} for value in (index.get("names") or [])[:5])
    return facts[:12]


def _forbidden_claim_types(blocked_claims: list[dict[str, Any]], index: dict[str, Any]) -> list[str]:
    forbidden: list[str] = []
    if any(claim.get("issue") == "LIVE_EMPTY_AS_GLOBAL_ABSENCE" for claim in blocked_claims):
        forbidden.append("GLOBAL_NO_DATA")
    if "API_ERROR" in set(index.get("allowed_caveats") or []):
        forbidden.append("NO_DATA_FROM_API_ERROR")
    for claim in blocked_claims:
        claim_type = str(claim.get("type") or "")
        if claim_type in {"COUNT", "ID", "STATUS", "DATE", "RELATIONSHIP"}:
            forbidden.append(f"INVENTED_{claim_type}")
    return _dedupe(forbidden)


def _allowed_rewrite_shape(allowed_facts: list[dict[str, str]], index: dict[str, Any]) -> str:
    if any(fact.get("value") == "LIVE_EMPTY_SCOPED" for fact in allowed_facts):
        return "No matching records were returned for this API query/scope."
    if any(fact.get("value") == "API_ERROR" for fact in allowed_facts):
        return "API unavailable/error; live state could not be verified."
    if index.get("counts"):
        return f"Use supported count: {index['counts'][0]}."
    return "Rewrite using only the listed allowed facts."


def _first(values: Any, default: str) -> str:
    if isinstance(values, list) and values:
        return str(values[0])
    return default


def _dedupe(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return out
