from __future__ import annotations

import json
from typing import Any

from .evidence_allowed_fact_index import AllowedFactIndex
from .final_answer_claim_extractor import FinalAnswerClaim
from .llm_client import get_llm_client


LLM_JUDGE_LABELS = {"SUPPORTED", "UNSUPPORTED", "NEEDS_CAVEAT"}


def judge_ambiguous_claim(
    claim: FinalAnswerClaim,
    *,
    question: str = "",
    allowed_fact_index: AllowedFactIndex,
    llm_client: Any | None = None,
    enabled: bool = False,
) -> str:
    if not enabled:
        return "NEEDS_CAVEAT"
    client = llm_client
    if client is None:
        try:
            client = get_llm_client()
        except Exception:
            return "NEEDS_CAVEAT"
    payload = {
        "claim": claim.to_dict(),
        "question": str(question or ""),
        "allowed_facts": allowed_fact_index.compact_allowed_facts(),
        "allowed_caveats": allowed_fact_index.allowed_caveats,
        "task": "Return SUPPORTED|UNSUPPORTED|NEEDS_CAVEAT only.",
    }
    messages = [
        {"role": "system", "content": "Classify claim support only. Do not answer the user or add facts."},
        {"role": "user", "content": json.dumps(payload, sort_keys=True)},
    ]
    try:
        raw = _call_client(client, messages)
    except Exception:
        return "NEEDS_CAVEAT"
    label = str(raw or "").strip().upper()
    for candidate in LLM_JUDGE_LABELS:
        if candidate in label:
            return candidate
    return "NEEDS_CAVEAT"


def _call_client(client: Any, messages: list[dict[str, str]]) -> str:
    if hasattr(client, "complete"):
        return str(client.complete(messages))
    if hasattr(client, "chat"):
        return str(client.chat(messages))
    if hasattr(client, "complete_json"):
        return json.dumps(client.complete_json(messages), sort_keys=True)
    if hasattr(client, "generate_messages"):
        result = client.generate_messages(messages)
        if isinstance(result, dict):
            return str(result.get("content") or "")
    raise TypeError("unsupported ambiguous-claim judge client")
