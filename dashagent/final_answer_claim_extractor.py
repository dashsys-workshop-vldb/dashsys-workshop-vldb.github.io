from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any


CLAIM_TYPES = {
    "COUNT",
    "ENTITY_NAME",
    "ID",
    "STATUS",
    "DATE",
    "RELATIONSHIP",
    "EXISTENCE",
    "NO_DATA",
    "LIVE_STATE",
    "CAVEAT",
    "SOFT_TEXT",
}
STATUS_WORDS = {
    "active",
    "inactive",
    "failed",
    "succeeded",
    "success",
    "queued",
    "published",
    "unpublished",
    "draft",
    "deployed",
}
GENERIC_ENTITY_TERMS = {
    "API",
    "SQL",
    "Live API",
    "Based",
    "Available",
    "Evidence",
    "Count",
    "Status",
    "ID",
}


@dataclass(frozen=True)
class FinalAnswerClaim:
    text: str
    type: str
    value: str
    span: str
    hardness: str = "HARD"

    def __post_init__(self) -> None:
        claim_type = str(self.type or "SOFT_TEXT").upper()
        object.__setattr__(self, "type", claim_type if claim_type in CLAIM_TYPES else "SOFT_TEXT")
        object.__setattr__(self, "hardness", "SOFT" if str(self.hardness).upper() == "SOFT" else "HARD")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def extract_final_answer_claims(answer: str) -> list[FinalAnswerClaim]:
    text = str(answer or "")
    claims: list[FinalAnswerClaim] = []
    occupied: list[tuple[int, int]] = []
    _extend(claims, occupied, _id_claims(text))
    _extend(claims, occupied, _date_claims(text))
    _extend(claims, occupied, _count_claims(text, occupied))
    _extend(claims, occupied, _status_claims(text, occupied))
    _extend(claims, occupied, _relationship_claims(text))
    _extend(claims, occupied, _no_data_claims(text))
    _extend(claims, occupied, _caveat_claims(text))
    _extend(claims, occupied, _existence_claims(text, occupied))
    _extend(claims, occupied, _entity_name_claims(text, occupied))
    if not claims and text.strip():
        claims.append(FinalAnswerClaim(text=text.strip()[:120], type="SOFT_TEXT", value="", span=text.strip()[:120], hardness="SOFT"))
    return claims


def _id_claims(text: str) -> list[tuple[FinalAnswerClaim, int, int]]:
    out: list[tuple[FinalAnswerClaim, int, int]] = []
    patterns = [
        r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
        r"\b01[A-Z0-9]{20,}\b",
        r"\b[a-z]+-\d+\b",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.I):
            out.append((_claim(text, "ID", match.group(0), match.start(), match.end()), match.start(), match.end()))
    return out


def _date_claims(text: str) -> list[tuple[FinalAnswerClaim, int, int]]:
    out: list[tuple[FinalAnswerClaim, int, int]] = []
    patterns = [
        r"\b20\d{2}-\d{2}-\d{2}(?:[T ][0-9:.+-]+Z?)?\b",
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+20\d{2}\b",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.I):
            out.append((_claim(text, "DATE", match.group(0), match.start(), match.end()), match.start(), match.end()))
    return out


def _count_claims(text: str, occupied: list[tuple[int, int]]) -> list[tuple[FinalAnswerClaim, int, int]]:
    out: list[tuple[FinalAnswerClaim, int, int]] = []
    for match in re.finditer(r"(?<![\w.-])\d+(?:,\d{3})*(?:\.\d+)?(?![\w.-])", text):
        if _overlaps(match.start(), match.end(), occupied):
            continue
        value = match.group(0).replace(",", "")
        out.append((_claim(text, "COUNT", value, match.start(), match.end()), match.start(), match.end()))
    return out


def _status_claims(text: str, occupied: list[tuple[int, int]]) -> list[tuple[FinalAnswerClaim, int, int]]:
    out: list[tuple[FinalAnswerClaim, int, int]] = []
    for status in STATUS_WORDS:
        for match in re.finditer(rf"\b{re.escape(status)}\b", text, flags=re.I):
            if _overlaps(match.start(), match.end(), occupied):
                continue
            if status == "active" and text[max(0, match.start() - 2) : match.start()].lower().endswith("in"):
                continue
            if status == "live" and "api" in text[match.end() : match.end() + 16].lower():
                continue
            out.append((_claim(text, "STATUS", match.group(0), match.start(), match.end()), match.start(), match.end()))
    return out


def _relationship_claims(text: str) -> list[tuple[FinalAnswerClaim, int, int]]:
    out: list[tuple[FinalAnswerClaim, int, int]] = []
    for match in re.finditer(r"\b([A-Z][\w-]*(?:\s+[A-Z][\w-]*){0,4})\s+(uses|is connected to|is linked to|maps to|belongs to)\s+([A-Z][\w-]*(?:\s+[A-Z][\w-]*){0,4})\b", text):
        out.append((_claim(text, "RELATIONSHIP", match.group(0), match.start(), match.end()), match.start(), match.end()))
    for match in re.finditer(r"\b([A-Z][\w-]*(?:\s+[A-Z][\w-]*){0,4})\s+(uses|is connected to|is linked to|maps to|belongs to)\s+(?:dataset|schema|journey|campaign|segment|audience)\s+([A-Z][\w-]*(?:\s+[A-Z][\w-]*){0,4})\b", text):
        out.append((_claim(text, "RELATIONSHIP", match.group(0), match.start(), match.end()), match.start(), match.end()))
    return out


def _no_data_claims(text: str) -> list[tuple[FinalAnswerClaim, int, int]]:
    lowered = text.lower()
    out: list[tuple[FinalAnswerClaim, int, int]] = []
    patterns = [
        r"\bno matching records? (?:were )?returned(?: for this query(?:/scope| scope)?)?(?: (?:globally|anywhere))?\b",
        r"\bthere are no [^.]+",
        r"\bno [a-z ]+ anywhere\b",
        r"\bno data\b",
        r"\breturned no [^.]+",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, lowered, flags=re.I):
            out.append((_claim(text, "NO_DATA", match.group(0), match.start(), match.end()), match.start(), match.end()))
    return out


def _caveat_claims(text: str) -> list[tuple[FinalAnswerClaim, int, int]]:
    lowered = text.lower()
    out: list[tuple[FinalAnswerClaim, int, int]] = []
    patterns = [
        r"\bapi unavailable\b",
        r"\bapi unavailable/error\b",
        r"\bcould not be verified\b",
        r"\bcannot verify live state\b",
        r"\blive api verification was not executed\b",
        r"\bapi error\b",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, lowered, flags=re.I):
            out.append((_claim(text, "CAVEAT", match.group(0), match.start(), match.end()), match.start(), match.end()))
    return out


def _existence_claims(text: str, occupied: list[tuple[int, int]]) -> list[tuple[FinalAnswerClaim, int, int]]:
    out: list[tuple[FinalAnswerClaim, int, int]] = []
    for match in re.finditer(r"\bthe matching ([a-z ]+) is ([A-Z][\w-]*(?:\s+[A-Z][\w-]*){0,4})\b", text, flags=re.I):
        if _overlaps(match.start(), match.end(), occupied):
            continue
        out.append((_claim(text, "EXISTENCE", match.group(2), match.start(), match.end()), match.start(), match.end()))
    for match in re.finditer(r"\bthe matching ([a-z ]+) looks ready\b", text, flags=re.I):
        if _overlaps(match.start(), match.end(), occupied):
            continue
        out.append((_claim(text, "EXISTENCE", match.group(0), match.start(), match.end()), match.start(), match.end()))
    for match in re.finditer(r"\b([A-Z][\w-]*(?:\s+[A-Z][\w-]*){0,4})\s+(?:is|was|are|were)\s+(?:available|present|returned|found)\b", text):
        if _overlaps(match.start(), match.end(), occupied):
            continue
        out.append((_claim(text, "EXISTENCE", match.group(1), match.start(), match.end()), match.start(), match.end()))
    return out


def _entity_name_claims(text: str, occupied: list[tuple[int, int]]) -> list[tuple[FinalAnswerClaim, int, int]]:
    out: list[tuple[FinalAnswerClaim, int, int]] = []
    for match in re.finditer(r"'([^']+)'|\"([^\"]+)\"", text):
        value = (match.group(1) or match.group(2)).strip()
        if value:
            out.append((_claim(text, "ENTITY_NAME", value, match.start(), match.end()), match.start(), match.end()))
    for match in re.finditer(r"\b[A-Z][A-Za-z0-9_-]+(?:\s+[A-Z][A-Za-z0-9_-]+){1,5}\b", text):
        if _overlaps(match.start(), match.end(), occupied):
            continue
        value = match.group(0).strip()
        if value in GENERIC_ENTITY_TERMS or value.startswith(("Based on", "Available evidence", "Live API")):
            continue
        if any(part in STATUS_WORDS for part in value.lower().split()):
            continue
        out.append((_claim(text, "ENTITY_NAME", value, match.start(), match.end()), match.start(), match.end()))
    return out


def _claim(text: str, claim_type: str, value: str, start: int, end: int) -> FinalAnswerClaim:
    return FinalAnswerClaim(text=text[start:end], type=claim_type, value=str(value), span=text[start:end], hardness="HARD")


def _extend(target: list[FinalAnswerClaim], occupied: list[tuple[int, int]], items: list[tuple[FinalAnswerClaim, int, int]]) -> None:
    for claim, start, end in items:
        target.append(claim)
        occupied.append((start, end))


def _overlaps(start: int, end: int, occupied: list[tuple[int, int]]) -> bool:
    return any(start < other_end and end > other_start for other_start, other_end in occupied)
