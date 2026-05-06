from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class AnswerClaim:
    claim_type: str
    value: str
    start: int = 0
    end: int = 0


def extract_claims(answer: str) -> list[AnswerClaim]:
    claims: list[AnswerClaim] = []
    claims.extend(number_claims(answer))
    claims.extend(timestamp_claims(answer))
    claims.extend(entity_claims(answer))
    claims.extend(status_claims(answer))
    lowered = answer.lower()
    for match in re.finditer(r"\b(no matching|not found|zero rows|no data|returned no|no .* found)\b", lowered):
        claims.append(AnswerClaim("no_result", match.group(0), match.start(), match.end()))
    for match in re.finditer(r"\b(api (?:returned|confirmed|confirms|shows|evidence reports)|live .*api evidence|based on live .*api)\b", lowered):
        prefix = lowered[max(0, match.start() - 20) : match.start()]
        suffix = lowered[match.end() : match.end() + 32]
        if any(token in prefix for token in ["require", "requires", "needed", "need "]) or any(
            token in suffix for token in ["require", "requires", "needed", "not executed", "unavailable"]
        ):
            continue
        claims.append(AnswerClaim("api_confirmation", match.group(0), match.start(), match.end()))
    for match in re.finditer(r"\b(discrepancy|disagree|does not match|different from|conflict)\b", lowered):
        claims.append(AnswerClaim("discrepancy", match.group(0), match.start(), match.end()))
    return claims


def number_claims(answer: str) -> list[AnswerClaim]:
    claims = []
    for match in re.finditer(r"(?<![\w.-])\d+(?:,\d{3})*(?:\.\d+)?(?![\w.-])", answer):
        value = match.group(0)
        if is_date_component(answer, match.start(), match.end()):
            continue
        claims.append(AnswerClaim("number", value.replace(",", ""), match.start(), match.end()))
    return claims


def timestamp_claims(answer: str) -> list[AnswerClaim]:
    claims = []
    patterns = [
        r"\b20\d{2}-\d{2}-\d{2}(?:[T ][0-9:.+-]+Z?)?\b",
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+20\d{2}\b",
        r"\b\d{1,2}:\d{2}(?::\d{2})?\s*(?:UTC|Z)?\b",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, answer, flags=re.I):
            claims.append(AnswerClaim("timestamp", match.group(0), match.start(), match.end()))
    return claims


def entity_claims(answer: str) -> list[AnswerClaim]:
    claims = []
    for match in re.finditer(r"'([^']+)'|\"([^\"]+)\"", answer):
        value = (match.group(1) or match.group(2)).strip()
        if value:
            claims.append(AnswerClaim("entity", value, match.start(), match.end()))
    for match in re.finditer(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", answer, flags=re.I):
        claims.append(AnswerClaim("entity", match.group(0), match.start(), match.end()))
    for match in re.finditer(r"\b01[A-Z0-9]{20,}\b", answer):
        claims.append(AnswerClaim("entity", match.group(0), match.start(), match.end()))
    return claims


def status_claims(answer: str) -> list[AnswerClaim]:
    statuses = [
        "active",
        "inactive",
        "failed",
        "succeeded",
        "success",
        "queued",
        "published",
        "unpublished",
        "draft",
        "live",
        "deployed",
    ]
    claims = []
    for status in statuses:
        for match in re.finditer(rf"\b{re.escape(status)}\b", answer, flags=re.I):
            if status == "live" and "api" in answer[match.end() : match.end() + 32].lower():
                continue
            claims.append(AnswerClaim("status", match.group(0), match.start(), match.end()))
    return claims


def is_date_component(answer: str, start: int, end: int) -> bool:
    window = answer[max(0, start - 6) : min(len(answer), end + 6)]
    if re.search(r"20\d{2}-\d{2}-\d{2}", window):
        return True
    return ":" in window and bool(re.search(r"\d{1,2}:\d{2}(?::\d{2})?", window))
