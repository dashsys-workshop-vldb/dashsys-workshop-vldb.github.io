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
    "Journey Optimizer",
    "Adobe Experience Platform",
}
GENERIC_ENTITY_PHRASES = {
    "the api",
    "the sql",
    "sql query",
    "the sql query",
    "api evidence",
    "the api evidence",
    "the evidence",
    "evidence provided",
    "the field",
    "the fields",
    "journey optimizer",
    "adobe experience platform",
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
    quoted = _quoted_spans(text)
    for match in re.finditer(r"(?<![\w.-])\d+(?:,\d{3})*(?:\.\d+)?(?![\w-])", text):
        if _overlaps(match.start(), match.end(), occupied):
            continue
        if _inside_span(match.start(), match.end(), quoted):
            continue
        value = match.group(0).replace(",", "")
        if _looks_like_url_port(text, match.start(), match.end()):
            continue
        if _looks_like_numbered_list_marker(text, match.start(), match.end()):
            continue
        if _looks_like_percentage(text, match.end()):
            continue
        if _looks_like_entity_code_number(value):
            continue
        if _looks_like_prompt_time_window(text, match.start(), match.end()):
            continue
        if _looks_like_interval_value(text, match.start(), match.end()):
            continue
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
            if status == "active" and "not currently" in text[max(0, match.start() - 24) : match.start()].lower():
                continue
            if status == "live" and "api" in text[match.end() : match.end() + 16].lower():
                continue
            if _looks_like_conceptual_status_example(text, match.start(), match.end(), status):
                continue
            if _looks_like_api_caveat_status(text, match.start(), match.end(), status):
                continue
            if _looks_like_negative_unavailable_status_context(text, match.start(), match.end()):
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
    for match in re.finditer(r"\b[A-Z][A-Za-z0-9_-]*_[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", text, flags=re.I):
        if _overlaps(match.start(), match.end(), occupied):
            continue
        out.append((_claim(text, "ENTITY_NAME", match.group(0).strip(), match.start(), match.end()), match.start(), match.end()))
    for match in re.finditer(r"\b[A-Z][A-Za-z0-9_-]+(?:[ \t]+[A-Z][A-Za-z0-9_-]+){1,5}\b", text):
        if _overlaps(match.start(), match.end(), occupied):
            continue
        value = match.group(0).strip()
        normalized = re.sub(r"\s+", " ", value).strip().lower()
        if value in GENERIC_ENTITY_TERMS or normalized in GENERIC_ENTITY_PHRASES or value.startswith(("Based on", "Available evidence", "Live API")):
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


def _quoted_spans(text: str) -> list[tuple[int, int]]:
    return [(match.start(), match.end()) for match in re.finditer(r"'[^']*'|\"[^\"]*\"", text)]


def _inside_span(start: int, end: int, spans: list[tuple[int, int]]) -> bool:
    return any(start >= span_start and end <= span_end for span_start, span_end in spans)


def _looks_like_url_port(text: str, start: int, end: int) -> bool:
    if start <= 0 or text[start - 1] != ":":
        return False
    prefix = text[max(0, start - 160) : start]
    suffix = text[end : min(len(text), end + 16)]
    return bool(re.search(r"https?://\S*$", prefix, flags=re.I) and (not suffix or suffix[0] in "/?#.:;, )]"))


def _looks_like_numbered_list_marker(text: str, start: int, end: int) -> bool:
    prefix = text[max(0, start - 8) : start]
    suffix = text[end : min(len(text), end + 2)]
    if not suffix or suffix[0] not in {".", ")"}:
        return False
    return bool(re.search(r"(?:^|\n)\s*$", prefix))


def _looks_like_percentage(text: str, end: int) -> bool:
    suffix = text[end : min(len(text), end + 2)]
    return suffix.startswith("%")


def _looks_like_entity_code_number(value: str) -> bool:
    normalized = str(value or "").replace(",", "")
    return len(normalized) > 1 and normalized.startswith("0") and normalized.isdigit()


def _looks_like_prompt_time_window(text: str, start: int, end: int) -> bool:
    prefix = text[max(0, start - 32) : start].lower()
    suffix = text[end : min(len(text), end + 16)].lower()
    if not re.match(r"\s*(?:days?|weeks?|months?|hours?|minutes?)\b", suffix):
        return False
    return bool(re.search(r"\b(last|past|previous|next|prior)\s+$", prefix))


def _looks_like_interval_value(text: str, start: int, end: int) -> bool:
    prefix = text[max(0, start - 32) : start].lower()
    return bool(re.search(r"\binterval\s+of\s+$", prefix))


def _looks_like_negative_unavailable_status_context(text: str, start: int, end: int) -> bool:
    prefix = text[max(0, start - 48) : start].lower()
    suffix = text[end : min(len(text), end + 48)].lower()
    if prefix.endswith("non-") or prefix.endswith("non "):
        return True
    if re.search(r"\b(no|not|without)\s+[\w\s-]{0,32}$", prefix) and re.search(r"\b(explicitly\s+)?(identified|available|found|returned|present)\b", suffix):
        return True
    return False


def _looks_like_api_caveat_status(text: str, start: int, end: int, status: str) -> bool:
    if str(status).lower() not in {"failed", "success", "succeeded", "deployed"}:
        return False
    context = text[max(0, start - 100) : min(len(text), end + 100)].lower()
    if str(status).lower() == "deployed" and re.search(r"\b(last\s+deployed|deployed\s+time|deployment\s+time|timestamp)\b", context):
        return True
    has_api_subject = bool(re.search(r"\b(api|live api|api call|api request|endpoint|credentials?|verification|tool call|request)\b", context))
    has_caveat_signal = bool(re.search(r"\b(unavailable|error|errored|failed|not executed|could not|unable|credentials?)\b", context))
    return has_api_subject and has_caveat_signal


def _looks_like_conceptual_status_example(text: str, start: int, end: int, status: str) -> bool:
    if str(status).lower() not in {"active", "inactive", "draft", "deployed", "published", "unpublished"}:
        return False
    context = text[max(0, start - 120) : min(len(text), end + 120)].lower()
    status_text = re.escape(str(status).lower())
    conceptual_signal = bool(
        re.search(r"\b(refers to|typically|can mean|can include|includes|such as|e\\.g\\.|for example|concept|state encompasses|is considered|unlike|differs? from|not currently|not running)\b", context)
        or re.search(rf"\b{status_text}\s+[a-z][\w-]*\s+(?:is|means|refers to)\s+(?:a|an|the|that)\b", context)
    )
    data_signal = bool(re.search(r"\b(status|state)\s*[:=]\s*$", context[: max(0, start - max(0, start - 120))]))
    return conceptual_signal and not data_signal
