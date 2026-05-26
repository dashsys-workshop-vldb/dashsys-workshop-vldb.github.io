from __future__ import annotations

import re
from typing import Any

from .answer_claims import extract_claims
from .llm_client import LLMClient, get_llm_client
from .llm_tool_agent_prompts import build_final_answer_prompt, parse_json_object
from .trajectory import redact_secrets


def evidence_locked_answer(
    prompt: str,
    observations: list[dict[str, Any]],
    *,
    llm_client: LLMClient | None = None,
    answer_intent: str | None = None,
) -> dict[str, Any]:
    client = llm_client or get_llm_client()
    supported_values = _supported_values(observations)
    if not client.available():
        answer = _fallback_answer(prompt, observations, answer_intent)
        return {
            "answer": answer,
            "claims": [],
            "unsupported_claim_count": 0,
            "unsupported_claims": [],
            "fallback_used": True,
            "skipped": True,
        }
    bundle = build_final_answer_prompt(prompt, observations, answer_intent=answer_intent)
    response = client.generate(bundle.system_prompt, bundle.user_prompt)
    parsed = parse_json_object(response.get("content", ""))
    proposed = str(parsed.get("answer") or response.get("content") or "").strip()
    proposed_unsupported = _unsupported_claims(proposed, supported_values)
    fallback_used = bool(proposed_unsupported) or not proposed
    answer = _fallback_answer(prompt, observations, answer_intent) if fallback_used else proposed
    final_unsupported = _unsupported_claims(answer, supported_values)
    return redact_secrets(
        {
            "answer": answer,
            "claims": parsed.get("claims", []),
            "unsupported_claim_count": len(final_unsupported),
            "unsupported_claims": final_unsupported,
            "rejected_unsupported_claim_count": len(proposed_unsupported),
            "rejected_unsupported_claims": proposed_unsupported,
            "fallback_used": fallback_used,
            "skipped": False,
            "llm_usage": response.get("usage", {}),
            "supported_values": sorted(supported_values)[:40],
            "tool_result_used": bool(observations and answer and "does not contain enough supported data" not in answer),
        }
    )


def _unsupported_claims(answer: str, supported_values: set[str]) -> list[dict[str, str]]:
    unsupported = []
    for claim in extract_claims(answer):
        value = str(claim.value).strip()
        if not value:
            continue
        if value.lower() in {"api returned", "api confirmed", "api confirms", "api evidence reports"}:
            continue
        if value.lower() not in supported_values:
            unsupported.append({"claim_type": claim.claim_type, "value": value})
    return unsupported


def _supported_values(observations: list[dict[str, Any]]) -> set[str]:
    values: set[str] = set()

    def walk(value: Any) -> None:
        if value is None:
            return
        if isinstance(value, (str, int, float, bool)):
            text = str(value)
            if text:
                values.add(text)
                values.add(text.lower())
                for match in re.finditer(r"\b\d{1,2}:\d{2}(?::\d{2})?\b", text):
                    time_value = match.group(0)
                    values.add(time_value)
                    values.add(time_value.lower())
            return
        if isinstance(value, dict):
            if value.get("state") == "live_empty":
                for phrase in ("returned no", "no records", "no matching records", "live_empty"):
                    values.add(phrase)
                    values.add(phrase.lower())
            for key, nested in value.items():
                key_text = str(key)
                if key_text:
                    values.add(key_text)
                    values.add(key_text.lower())
                walk(nested)
        elif isinstance(value, list):
            for nested in value:
                walk(nested)

    walk(observations)
    return values


def _fallback_answer(prompt: str, observations: list[dict[str, Any]], answer_intent: str | None) -> str:
    rows = []
    api_states = []
    for observation in observations:
        if isinstance(observation.get("rows"), list):
            rows.extend(row for row in observation["rows"] if isinstance(row, dict))
        result = observation.get("execution_result")
        if isinstance(result, dict) and isinstance(result.get("rows"), list):
            rows.extend(row for row in result["rows"] if isinstance(row, dict))
        if observation.get("source") == "api":
            api_states.append(
                {
                    "state": observation.get("state"),
                    "status_code": observation.get("status_code"),
                    "endpoint": observation.get("endpoint"),
                }
            )
    if answer_intent == "COUNT":
        for row in rows:
            for key in ("count", "COUNT(*)", "cnt", "total"):
                if key in row:
                    return f"The evidence reports {row[key]}."
    if rows:
        compact = []
        for row in rows[:3]:
            selected = {key.lower(): row[key] for key in row if key.lower() in {"count", "name", "id", "status", "state"}}
            compact.append(selected or row)
        return f"The available evidence is: {compact}."
    if api_states:
        first = api_states[0]
        state = first.get("state") or "api_result"
        status = first.get("status_code")
        if state == "live_empty":
            return "The validated API call returned no records for this request context; this does not establish broader absence."
        if state == "live_success":
            return "The validated API call succeeded, but the compact observation does not expose specific fields needed for a more detailed answer."
        if status:
            return f"The API evidence state is {state} with HTTP status {status}; no payload facts are available for a stronger answer."
        return f"The API evidence state is {state}; no payload facts are available for a stronger answer."
    return "The available tool evidence does not contain enough supported data to answer."
