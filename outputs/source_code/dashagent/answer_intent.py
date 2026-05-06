from __future__ import annotations

from enum import StrEnum

from .answer_slots import AnswerSlots


class AnswerIntent(StrEnum):
    COUNT = "COUNT"
    LIST = "LIST"
    YES_NO = "YES_NO"
    WHEN = "WHEN"
    STATUS = "STATUS"
    DETAIL = "DETAIL"
    COMPARISON = "COMPARISON"
    NO_RESULT = "NO_RESULT"
    DISCREPANCY = "DISCREPANCY"


def classify_answer_intent(query: str, slots: AnswerSlots | None = None) -> AnswerIntent:
    lowered = query.lower()
    if slots and slots.discrepancy:
        return AnswerIntent.DISCREPANCY
    if any(token in lowered for token in ["compare", "difference", "disagree", "discrepancy", "mismatch"]):
        return AnswerIntent.COMPARISON
    if any(token in lowered for token in ["when", "what time", "date", "daily", "between", "most recent", "recently"]):
        return AnswerIntent.WHEN
    if any(token in lowered for token in ["how many", "count", "number of", "total"]):
        return AnswerIntent.COUNT
    if any(token in lowered for token in ["list", "show all", "give me all", "which ", "what are the"]):
        return AnswerIntent.LIST
    if any(token in lowered for token in ["status", "state", "failed", "succeeded", "success", "live", "inactive", "published"]):
        return AnswerIntent.STATUS
    if lowered.startswith(("is ", "are ", "does ", "do ", "did ", "has ", "have ", "was ", "were ", "can ")):
        return AnswerIntent.YES_NO
    if slots and slots.sql_row_count == 0 and not slots.api_items and not slots.dry_run:
        return AnswerIntent.NO_RESULT
    return AnswerIntent.DETAIL


def intent_matches_answer(answer: str, intent: AnswerIntent) -> bool:
    lowered = answer.lower().strip()
    if intent == AnswerIntent.COUNT:
        return lowered.startswith(("the count", "the database count", "there are", "there is", "count")) or (
            lowered.startswith("based on") and any(ch.isdigit() for ch in lowered[:120])
        )
    if intent == AnswerIntent.LIST:
        return any(
            lowered.startswith(prefix)
            for prefix in ["based on", "matching", "the matching", "the available", "there are", "the requested", "no "]
        ) or "requires live api" in lowered
    if intent == AnswerIntent.WHEN:
        return any(token in lowered[:120] for token in [" at ", " on ", "between", "updated", "created", "published", "date", "time", "require live"])
    if intent == AnswerIntent.STATUS:
        return any(token in lowered[:160] for token in ["status", "state", "failed", "succeeded", "success", "inactive", "published", "live"])
    if intent == AnswerIntent.YES_NO:
        return lowered.startswith(("yes", "no", "the "))
    if intent == AnswerIntent.DISCREPANCY:
        return any(token in lowered for token in ["disagree", "discrepancy", "does not match", "different"])
    if intent == AnswerIntent.NO_RESULT:
        return any(token in lowered for token in ["no ", "not found", "zero rows", "no matching"])
    return True
