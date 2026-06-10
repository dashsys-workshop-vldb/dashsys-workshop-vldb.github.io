from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from .answer_slots import AnswerSlots
from .evidence_grounded_final_answer_verifier import EvidenceGroundedFinalAnswerVerification, verify_evidence_grounded_final_answer
from .llm_client import get_llm_client
from .trajectory import estimate_tokens


@dataclass(frozen=True)
class LLMConceptAnswerResult:
    answer: str
    verification: EvidenceGroundedFinalAnswerVerification
    llm_backend_used: bool
    fallback_used: bool = False
    debug: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "answer": self.answer,
            "verification": self.verification.to_dict(),
            "llm_backend_used": self.llm_backend_used,
            "fallback_used": self.fallback_used,
            "debug": self.debug,
        }


def generate_llm_concept_answer(
    prompt: str,
    *,
    slots: AnswerSlots,
    llm_client: Any | None = None,
    evidence_bus: Any | None = None,
) -> LLMConceptAnswerResult:
    client = llm_client
    if client is None:
        try:
            client = get_llm_client()
        except Exception:
            client = None
    messages = _messages(prompt, slots)
    answer = ""
    debug = _debug(client, messages)
    backend_used = False
    if client is not None and (not hasattr(client, "available") or bool(client.available())):
        try:
            raw = _call_client(client, messages)
            answer = _extract_content(raw)
            backend_used = bool(answer)
            debug.update({"raw_response_present": raw is not None, "extracted_content_length": len(answer)})
        except Exception as exc:
            debug.update({"exception_class": type(exc).__name__, "extracted_content_length": 0})
    if not answer:
        answer = _deterministic_concept_answer(prompt)
    verification = verify_evidence_grounded_final_answer(answer, slots=slots, evidence_bus=evidence_bus, question=prompt)
    return LLMConceptAnswerResult(answer, verification, backend_used, fallback_used=not backend_used, debug=debug)


def _messages(prompt: str, slots: AnswerSlots) -> list[dict[str, Any]]:
    payload = {
        "question": prompt,
        "conceptual_terms": _conceptual_terms(prompt),
        "allowed_domain_terms": _allowed_domain_terms(prompt),
        "constraints": [
            "Answer directly and concisely.",
            "Explain the concept in general terms.",
            "Do not claim live platform state.",
            "Do not mention exact records unless provided as evidence.",
            "Do not invent counts, IDs, statuses, dates, or relationships.",
            "Return final answer text only.",
        ],
        "available_evidence_slots": slots.compact(),
    }
    return [
        {"role": "system", "content": "Generate a concise conceptual answer. Return final answer text only."},
        {"role": "user", "content": json.dumps(payload, sort_keys=True)},
    ]


def _call_client(client: Any, messages: list[dict[str, Any]]) -> Any:
    if hasattr(client, "complete"):
        return client.complete(messages)
    if hasattr(client, "chat"):
        return client.chat(messages)
    if hasattr(client, "generate_messages"):
        return client.generate_messages(messages)
    if hasattr(client, "complete_json"):
        return client.complete_json(messages)
    raise TypeError("unsupported concept answer client")


def _extract_content(raw: Any) -> str:
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw.strip()
    if not isinstance(raw, dict):
        return ""
    candidates: list[str] = []
    for key in ("content", "output_text", "answer"):
        value = raw.get(key)
        if isinstance(value, str):
            candidates.append(value)
    choices = raw.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict):
            message = first.get("message")
            if isinstance(message, dict) and isinstance(message.get("content"), str):
                candidates.append(message["content"])
            if isinstance(first.get("text"), str):
                candidates.append(first["text"])
    return "\n".join(value.strip() for value in candidates if value and value.strip()).strip()


def _deterministic_concept_answer(prompt: str) -> str:
    text = _norm(prompt)
    if (" in the phrase " in text or "what does" in text) and "list" in text:
        return "In this phrase, list means to enumerate or show the requested items."
    if "list" in text and any(token in text for token in ("reasons", "reason", "benefits", "examples")):
        if "schema" in text:
            return "Schemas matter because they make data structure explicit, keep records consistent, and help systems validate and interpret data."
        return "It matters because it clarifies structure, improves consistency, and supports reliable interpretation."
    if "schema" in text:
        return "A schema defines the structure, fields, and expected shape of data."
    if "inactive journey" in text or ("journey" in text and "inactive" in text):
        return "An inactive journey is a journey that is not currently active or running."
    if "journey" in text:
        return "A journey describes an orchestrated customer path or campaign flow."
    if "dataset" in text:
        return "A dataset is a collection of records organized for storage and analysis."
    return "This is a conceptual question and does not require SQL or API records."


def _conceptual_terms(prompt: str) -> list[str]:
    terms: list[str] = []
    text = _norm(prompt)
    for term in ("schema", "dataset", "journey", "segment", "audience", "status", "field", "api", "list"):
        if term in text:
            terms.append(term)
    return terms


def _allowed_domain_terms(prompt: str) -> list[str]:
    return _conceptual_terms(prompt)


def _debug(client: Any | None, messages: list[dict[str, Any]]) -> dict[str, Any]:
    prompt_text = "\n".join(str(message.get("content") or "") for message in messages)
    return {
        "llm_client_class": type(client).__name__ if client is not None else None,
        "backend_available": bool(client.available()) if client is not None and hasattr(client, "available") else client is not None,
        "request_message_count": len(messages),
        "estimated_prompt_tokens": estimate_tokens(prompt_text),
        "raw_response_present": False,
        "extracted_content_length": 0,
    }


def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())
