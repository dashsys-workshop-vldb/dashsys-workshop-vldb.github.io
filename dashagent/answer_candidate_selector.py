from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from .answer_slots import AnswerSlots, normalize_text
from .answer_verifier import verify_answer


@dataclass(frozen=True)
class AnswerCandidateSelection:
    selected_answer: str
    selected_source: str
    coverage_score: float
    unsupported_claims: int = 0
    selection_codes: list[str] = field(default_factory=list)
    candidates: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["coverage_score"] = round(float(self.coverage_score), 4)
        return payload


def select_answer_candidate(
    *,
    prompt: str,
    slots: AnswerSlots,
    evidence_bus: Any | None = None,
    llm_answer: str | None = None,
    llm_verification: Any | None = None,
    legacy_answer: str | None = None,
    grounded_answer: str | None = None,
    deterministic_answer: str | None = None,
) -> AnswerCandidateSelection:
    """Select the safest fact-complete answer using only runtime evidence.

    This selector deliberately does not inspect gold, benchmark category, tags,
    oracle SQL, or expected traces. It ranks same-evidence answers by claim
    safety and coverage of requested roles already present in AnswerSlots.
    """

    roles = _requested_roles(prompt, slots)
    candidates = [
        _candidate("LLM_EVIDENCE_GROUNDED", llm_answer, slots, roles, llm_verification),
        _candidate("LEGACY_SAFE_RENDERER", legacy_answer, slots, roles, None),
        _candidate("DETERMINISTIC_FALLBACK", grounded_answer or deterministic_answer, slots, roles, None),
    ]
    usable = [candidate for candidate in candidates if candidate["answer"] and candidate["unsupported_claims"] == 0]
    if not usable:
        fallback = _candidate("DETERMINISTIC_FALLBACK", deterministic_answer or grounded_answer or legacy_answer or "", slots, roles, None)
        return AnswerCandidateSelection(
            selected_answer=str(fallback["answer"]),
            selected_source="DETERMINISTIC_FALLBACK",
            coverage_score=float(fallback["coverage_score"]),
            unsupported_claims=int(fallback["unsupported_claims"]),
            selection_codes=["NO_VERIFIED_CANDIDATE", *fallback["coverage_codes"]],
            candidates=candidates,
        )

    best = max(usable, key=lambda item: (float(item["coverage_score"]), _source_preference(str(item["source"]))))
    llm = next((item for item in candidates if item["source"] == "LLM_EVIDENCE_GROUNDED"), None)
    legacy = next((item for item in candidates if item["source"] == "LEGACY_SAFE_RENDERER"), None)
    codes: list[str] = []
    if llm and int(llm["unsupported_claims"]) > 0:
        codes.append("REJECTED_UNSUPPORTED_LLM")
    if llm and legacy and legacy["source"] == best["source"] and float(legacy["coverage_score"]) > float(llm["coverage_score"]):
        codes.extend(_coverage_advantage_codes(llm, legacy))
    codes.extend(str(code) for code in best.get("coverage_codes", []))
    if not codes:
        codes.append("SELECTED_VERIFIED_HIGHEST_COVERAGE")

    return AnswerCandidateSelection(
        selected_answer=str(best["answer"]),
        selected_source=str(best["source"]),
        coverage_score=float(best["coverage_score"]),
        unsupported_claims=int(best["unsupported_claims"]),
        selection_codes=_dedupe(codes),
        candidates=candidates,
    )


def _candidate(
    source: str,
    answer: str | None,
    slots: AnswerSlots,
    roles: list[str],
    external_verification: Any | None,
) -> dict[str, Any]:
    text = str(answer or "").strip()
    verification = _external_verification(external_verification)
    if verification is None and text:
        checked = verify_answer(text, slots)
        verification = {"ok": checked.ok, "unsupported_claims_count": checked.unsupported_count, "errors": checked.errors[:5]}
    unsupported = int((verification or {}).get("unsupported_claims_count", 0) or 0)
    if verification is not None and not bool(verification.get("ok", True)):
        unsupported = max(unsupported, 1)
    coverage = _coverage(text, slots, roles)
    return {
        "source": source,
        "answer": text,
        "verification": verification or {"ok": not text, "unsupported_claims_count": 0},
        "unsupported_claims": unsupported,
        "coverage_score": coverage["score"],
        "covered_roles": coverage["covered_roles"],
        "missing_roles": coverage["missing_roles"],
        "coverage_codes": coverage["codes"],
    }


def _external_verification(value: Any | None) -> dict[str, Any] | None:
    if value is None:
        return None
    payload = value.to_dict() if hasattr(value, "to_dict") else dict(value)
    unsupported = payload.get("unsupported_claims")
    count = payload.get("unsupported_claims_count")
    if count is None and isinstance(unsupported, list):
        count = len(unsupported)
    return {
        "ok": bool(payload.get("ok", count in (None, 0))),
        "unsupported_claims_count": int(count or 0),
        "action": payload.get("action"),
    }


def _requested_roles(prompt: str, slots: AnswerSlots) -> list[str]:
    norm = normalize_text(prompt)
    roles: list[str] = []
    if re.search(r"\b(how many|count|counts|total|number of)\b", norm):
        roles.append("count")
    if slots.answer_family == "observability_metrics" and slots.metrics:
        roles.append("metric_values")
    if slots.sql_row_count == 0 or any(str(value) in {"0", "0.0"} for value in slots.counts):
        roles.append("no_result")
    if "default" in norm and slots.answer_family == "merge_policy":
        roles.append("default_detail")
    if (
        re.search(r"\b(list|show|return)\b", norm)
        and "all" in norm
        and slots.api_item_count is not None
        and slots.api_item_count > 10
        and slots.api_item_count > len(slots.api_items or slots.important_items or [])
    ):
        roles.append("result_count_context")
    if re.search(r"\b(status|state|active|inactive|failed|succeeded|published|deployed)\b", norm):
        roles.append("status")
    if re.search(r"\b(active|inactive|failed|succeeded|published|deployed)\b", norm):
        roles.append("status_filter")
    if re.search(r"\b(when|created|updated|modified|published|deployed|timestamp|date|recent|latest)\b", norm):
        roles.append("date")
    if re.search(r"\b(list|show|return|provide|available|records?|which|what)\b", norm) and slots.entity_names:
        roles.append("name")
    if re.search(r"\b(id|ids|identifier)\b", norm) and slots.entity_ids:
        roles.append("id")
    if "local snapshot" in norm:
        roles.append("local_scope")
    if re.search(r"\b(current|live|platform|adobe experience platform)\b", norm) and slots.sql_row_count is not None and (slots.dry_run or slots.api_error):
        roles.append("live_scope_caveat")
    if (slots.api_error and not slots.live_api_evidence_available) or slots.dry_run:
        roles.append("caveat")
    return _dedupe(roles)


def _coverage(answer: str, slots: AnswerSlots, roles: list[str]) -> dict[str, Any]:
    if not answer:
        return {"score": -1.0, "covered_roles": [], "missing_roles": roles, "codes": ["EMPTY_ANSWER"]}
    norm = normalize_text(answer)
    covered: list[str] = []
    missing: list[str] = []
    codes: list[str] = []
    for role in roles:
        ok = _role_covered(role, norm, slots)
        if ok:
            covered.append(role)
            codes.append(f"{role.upper()}_COVERED")
        else:
            missing.append(role)
    covered_weight = sum(_role_weight(role) for role in covered)
    total_weight = sum(_role_weight(role) for role in roles) or 1.0
    score = float(covered_weight)
    if roles:
        score += covered_weight / total_weight
    score += min(1.0, _value_density(norm, slots))
    score += _answer_shape_quality(answer)
    if missing:
        score -= sum(_role_weight(role) * 0.35 for role in missing)
    return {"score": score, "covered_roles": covered, "missing_roles": missing, "codes": codes}


def _role_covered(role: str, answer_norm: str, slots: AnswerSlots) -> bool:
    if role == "count":
        allowed = {re.sub(r"[^\d.]", "", str(value)) for value in slots.counts}
        if not allowed and slots.sql_row_count is not None:
            allowed.add(str(slots.sql_row_count))
        if not allowed and slots.api_item_count is not None:
            allowed.add(str(slots.api_item_count))
        return any(value and re.search(rf"(?<!\d){re.escape(value)}(?!\d)", answer_norm) for value in allowed)
    if role == "metric_values":
        metric_ok = all(normalize_text(metric) in answer_norm for metric in slots.metrics[:2])
        evidence_numbers = [
            value
            for value in sorted(str(item) for item in slots.evidence_numbers)
            if value and value not in {str(count) for count in slots.counts}
        ]
        number_ok = any(normalize_text(value) in answer_norm for value in evidence_numbers[:8])
        timestamp_ok = not slots.timestamps or any(normalize_text(value)[:10] in answer_norm for value in slots.timestamps[:5])
        return metric_ok and number_ok and timestamp_ok
    if role == "result_count_context":
        if slots.api_item_count is None:
            return False
        value = str(slots.api_item_count)
        return bool(re.search(rf"(?<!\d){re.escape(value)}(?!\d)", answer_norm))
    if role == "no_result":
        return any(
            phrase in answer_norm
            for phrase in (
                "no data",
                "no matching",
                "zero rows",
                "0 matching",
                "no entities",
                "none were",
                "not found",
            )
        )
    if role == "default_detail":
        return "default merge polic" in answer_norm
    if role in {"status", "status_filter"}:
        valid_statuses = _status_terms(slots)
        return any(status in answer_norm for status in valid_statuses) or bool(
            re.search(r"\b(active|inactive|failed|succeeded|published|unpublished|draft|deployed)\b", answer_norm)
        )
    if role == "date":
        return any(normalize_text(value)[:10] and normalize_text(value)[:10] in answer_norm for value in slots.timestamps)
    if role == "name":
        return any(normalize_text(name) in answer_norm for name in slots.entity_names[:5])
    if role == "id":
        return any(str(value).lower() in answer_norm for value in slots.entity_ids[:5])
    if role == "local_scope":
        return "local" in answer_norm and "snapshot" in answer_norm
    if role == "live_scope_caveat":
        return ("local" in answer_norm and "snapshot" in answer_norm) and (
            "cannot verify" in answer_norm or "not executed" in answer_norm or "unavailable" in answer_norm
        )
    if role == "caveat":
        if slots.api_error:
            return any(token in answer_norm for token in ("api unavailable", "api error", "could not verify", "did not provide usable data"))
        if slots.dry_run:
            return "credentials" in answer_norm or "dry run" in answer_norm or "not executed" in answer_norm
        if str(slots.api_evidence_state or "").lower() in {"live_empty", "live_empty_result"}:
            return "no matching" in answer_norm or "returned no" in answer_norm
    return False


def _value_density(answer_norm: str, slots: AnswerSlots) -> float:
    values: list[str] = []
    values.extend(str(value) for value in slots.counts[:3])
    values.extend(slots.entity_names[:5])
    values.extend(slots.entity_ids[:5])
    values.extend(slots.statuses[:3])
    values.extend(slots.timestamps[:3])
    values.extend(slots.metrics[:2])
    values.extend(sorted(str(value) for value in slots.evidence_numbers)[:8])
    present = sum(1 for value in values if value and normalize_text(value) in answer_norm)
    return present / max(1, min(len(values), 6))


def _answer_shape_quality(answer: str) -> float:
    text = str(answer or "").strip()
    lowered = text.lower()
    score = 0.0
    if re.fullmatch(r"count:\s*[-+]?\d+(?:\.\d+)?\.", text, flags=re.I):
        score -= 0.75
    if lowered.startswith("results: {"):
        score -= 0.85
    if "api returned no matching records for this query/scope" in lowered:
        score -= 0.5
    if re.search(r"\b1[0-9]{12}\b", lowered) and lowered.startswith("date/time:"):
        score -= 4.0
    return score


def _coverage_advantage_codes(llm: dict[str, Any], legacy: dict[str, Any]) -> list[str]:
    missing_llm = set(str(role) for role in llm.get("missing_roles") or [])
    covered_legacy = set(str(role) for role in legacy.get("covered_roles") or [])
    return [f"{role.upper()}_COVERAGE_ADVANTAGE" for role in sorted(missing_llm & covered_legacy)]


def _source_preference(source: str) -> int:
    return {"LLM_EVIDENCE_GROUNDED": 3, "LEGACY_SAFE_RENDERER": 2, "DETERMINISTIC_FALLBACK": 1}.get(source, 0)


def _role_weight(role: str) -> float:
    if role == "status_filter":
        return 5.0
    if role == "metric_values":
        return 4.0
    if role == "result_count_context":
        return 3.0
    if role in {"no_result", "default_detail"}:
        return 3.0
    if role in {"count", "status", "date", "name", "id", "live_scope_caveat"}:
        return 2.0
    if role == "local_scope":
        return 1.25
    if role == "caveat":
        return 0.5
    return 1.0


def _status_terms(slots: AnswerSlots) -> list[str]:
    known = {"active", "inactive", "failed", "succeeded", "published", "unpublished", "draft", "deployed", "queued"}
    terms = [normalize_text(value) for value in slots.statuses if normalize_text(value) in known]
    query_norm = normalize_text(slots.query)
    terms.extend(status for status in known if re.search(rf"\b{re.escape(status)}\b", query_norm))
    return _dedupe(terms)


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return out
