from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .answer_slots import AnswerSlots
from .concise_llm_answer_rewriter import ConciseRewriteResult
from .concise_rewrite_card import ConciseRewriteCard
from .evidence_grounded_final_answer_verifier import (
    EvidenceGroundedFinalAnswerVerification,
    verify_evidence_grounded_final_answer,
)


@dataclass(frozen=True)
class ConciseRewriteSelection:
    selected_answer: str
    selected_source: str
    selection_codes: list[str] = field(default_factory=list)
    unsupported_claims: int = 0
    rewrite_fact_coverage: float = 0.0
    legacy_fact_coverage: float = 0.0
    verifier: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "selected_answer": self.selected_answer,
            "selected_source": self.selected_source,
            "selection_codes": list(self.selection_codes),
            "unsupported_claims": self.unsupported_claims,
            "rewrite_fact_coverage": self.rewrite_fact_coverage,
            "legacy_fact_coverage": self.legacy_fact_coverage,
            "verifier": self.verifier,
        }


def select_concise_rewrite(
    *,
    prompt: str,
    legacy_answer: str,
    rewrite_result: ConciseRewriteResult | None,
    card: ConciseRewriteCard | None,
    slots: AnswerSlots,
    evidence_bus: Any | None = None,
    verification: EvidenceGroundedFinalAnswerVerification | None = None,
) -> ConciseRewriteSelection:
    if rewrite_result is None or card is None:
        return _legacy(legacy_answer, ["KEEP_LEGACY_NOT_ELIGIBLE"])
    if rewrite_result.category == "backend_unavailable":
        return _legacy(legacy_answer, ["KEEP_LEGACY_BACKEND_UNAVAILABLE"])
    if rewrite_result.category == "empty_rewrite" or not rewrite_result.rewritten_answer.strip():
        return _legacy(legacy_answer, ["KEEP_LEGACY_EMPTY_REWRITE"])

    rewrite = rewrite_result.rewritten_answer.strip()
    missing = _missing_exact_facts(rewrite, card)
    if missing:
        return _legacy(legacy_answer, ["KEEP_LEGACY_MISSING_EXACT_FACT"])

    if _drops_required_caveat(rewrite, card, legacy_answer):
        return _legacy(legacy_answer, ["KEEP_LEGACY_MISSING_EXACT_FACT"])

    if _scope_risk(rewrite, card):
        return _legacy(legacy_answer, ["KEEP_LEGACY_SCOPE_RISK"])

    if _extra_caveat(rewrite, card, legacy_answer):
        return _legacy(legacy_answer, ["KEEP_LEGACY_EXTRA_CAVEAT"])

    verifier = verification or verify_evidence_grounded_final_answer(
        rewrite,
        slots=slots,
        evidence_bus=evidence_bus,
        question=prompt,
        caveats=card.exact_facts.get("caveats") or [],
    )
    unsupported_claims = _effective_unsupported_claims(verifier, card)
    unsupported_count = len(unsupported_claims)
    if (not verifier.ok and unsupported_count) or unsupported_count:
        return _legacy(legacy_answer, ["KEEP_LEGACY_UNSUPPORTED_REWRITE"], unsupported_count, verifier)

    legacy_coverage = _coverage(legacy_answer, card)
    rewrite_coverage = _coverage(rewrite, card)
    if rewrite_coverage < legacy_coverage:
        return _legacy(legacy_answer, ["KEEP_LEGACY_MISSING_EXACT_FACT"], 0, verifier, rewrite_coverage, legacy_coverage)

    codes: list[str] = []
    if _object_phrase_better(prompt, rewrite, legacy_answer, card):
        codes.append("SELECT_REWRITE_BETTER_OBJECT_PHRASE")
    if card.answer_type == "CONCEPT":
        codes.append("SELECT_REWRITE_CONCEPT_CLEARER")
    if _more_direct(rewrite, legacy_answer):
        codes.append("SELECT_REWRITE_SHORTER_EQUAL_FACTS")
    if not codes:
        return _legacy(legacy_answer, ["KEEP_LEGACY_NO_CLEAR_IMPROVEMENT"], 0, verifier, rewrite_coverage, legacy_coverage)
    return ConciseRewriteSelection(
        selected_answer=rewrite,
        selected_source="CONCISE_LLM_REWRITE",
        selection_codes=codes,
        unsupported_claims=0,
        rewrite_fact_coverage=rewrite_coverage,
        legacy_fact_coverage=legacy_coverage,
        verifier=verifier.to_dict(),
    )


def _legacy(
    answer: str,
    codes: list[str],
    unsupported_claims: int = 0,
    verification: EvidenceGroundedFinalAnswerVerification | None = None,
    rewrite_coverage: float = 0.0,
    legacy_coverage: float = 0.0,
) -> ConciseRewriteSelection:
    return ConciseRewriteSelection(
        selected_answer=answer,
        selected_source="LEGACY_SAFE_RENDERER",
        selection_codes=codes,
        unsupported_claims=unsupported_claims,
        rewrite_fact_coverage=rewrite_coverage,
        legacy_fact_coverage=legacy_coverage,
        verifier=verification.to_dict() if verification is not None else {},
    )


def _missing_exact_facts(answer: str, card: ConciseRewriteCard) -> list[str]:
    text = _norm(answer)
    missing: list[str] = []
    facts = card.exact_facts
    for key in ("count", "date", "status", "entity"):
        value = facts.get(key)
        if value and _norm(str(value)) not in text:
            missing.append(key)
    for value in facts.get("items", []) or []:
        if value and _norm(str(value)) not in text:
            missing.append("item")
    return missing


def _effective_unsupported_claims(
    verifier: EvidenceGroundedFinalAnswerVerification,
    card: ConciseRewriteCard,
) -> list[dict[str, Any]]:
    unsupported = list(verifier.unsupported_claims or [])
    if card.answer_type != "DATE":
        return unsupported
    benign_date_labels = {"published", "created", "updated", "modified"}
    return [
        claim
        for claim in unsupported
        if not (
            claim.get("type") == "STATUS"
            and str(claim.get("value") or "").lower() in benign_date_labels
            and bool(card.exact_facts.get("date"))
        )
    ]


def _coverage(answer: str, card: ConciseRewriteCard) -> float:
    total = 0
    hit = 0
    text = _norm(answer)
    facts = card.exact_facts
    for key in ("count", "date", "status", "entity"):
        value = facts.get(key)
        if value:
            total += 1
            hit += int(_norm(str(value)) in text)
    for value in facts.get("items", []) or []:
        if value:
            total += 1
            hit += int(_norm(str(value)) in text)
    return hit / total if total else 1.0


def _scope_risk(answer: str, card: ConciseRewriteCard) -> bool:
    text = _norm(answer)
    scope = str(card.exact_facts.get("scope") or "UNKNOWN").upper()
    live_tokens = ("adobe experience platform", "platform", "live", "current")
    local_tokens = ("local snapshot", "snapshot")
    if scope == "LOCAL_SNAPSHOT" and any(token in text for token in live_tokens):
        return True
    if scope == "LIVE" and any(token in text for token in local_tokens) and "live" not in text:
        return True
    return False


def _extra_caveat(answer: str, card: ConciseRewriteCard, legacy_answer: str) -> bool:
    text = _norm(answer)
    legacy = _norm(legacy_answer)
    allowed = {str(value).lower() for value in card.exact_facts.get("caveats", []) or []}
    caveat_markers = (
        "api unavailable",
        "api error",
        "cannot verify",
        "unable to verify",
        "no data",
        "no matching records",
        "not available",
    )
    for marker in caveat_markers:
        if marker in text and marker not in legacy:
            if not any(caveat in allowed for caveat in ("api_error", "live_empty", "sql_empty")):
                return True
    return False


def _drops_required_caveat(answer: str, card: ConciseRewriteCard, legacy_answer: str) -> bool:
    required = {str(value).upper() for value in card.exact_facts.get("caveats", []) or []}
    if not required.intersection({"API_ERROR", "DRY_RUN_API_UNAVAILABLE"}):
        return False
    legacy = _norm(legacy_answer)
    if not any(marker in legacy for marker in ("api", "verification", "credential", "unavailable", "cannot verify")):
        return False
    text = _norm(answer)
    return not any(marker in text for marker in ("api", "verification", "credential", "unavailable", "cannot verify"))


def _object_phrase_better(prompt: str, rewrite: str, legacy_answer: str, card: ConciseRewriteCard) -> bool:
    phrase = str(card.allowed_terms.get("object_phrase_from_prompt") or "").strip().lower()
    if not phrase:
        return False
    return phrase in rewrite.lower() and phrase not in legacy_answer.lower()


def _more_direct(rewrite: str, legacy_answer: str) -> bool:
    rewrite_words = len(re.findall(r"\w+", rewrite))
    legacy_words = len(re.findall(r"\w+", legacy_answer))
    if rewrite_words < legacy_words:
        return True
    if "_" in legacy_answer and "_" not in rewrite:
        return True
    weak_starts = ("based on", "the sql evidence", "the local snapshot contains", "the database shows")
    return any(_norm(legacy_answer).startswith(prefix) for prefix in weak_starts) and rewrite_words <= legacy_words + 4


def _norm(value: str) -> str:
    return re.sub(r"\s+", " ", value.lower()).strip()
