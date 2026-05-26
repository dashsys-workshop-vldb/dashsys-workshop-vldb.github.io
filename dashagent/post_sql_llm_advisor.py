from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

from .llm_client import get_llm_client
from .post_sql_deterministic_policy import PostSQLDeterministicPolicy


MODES = {"CALL_API", "SKIP_API", "CAVEAT_ONLY"}


@dataclass(frozen=True)
class PostSQLAPIAdvice:
    mode: str
    endpoint_id: str | None = None
    conf: float = 0.0
    needed_roles: list[str] = field(default_factory=list)
    codes: list[str] = field(default_factory=list)
    source: str = "LLM_ADVISOR"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["conf"] = round(float(self.conf), 4)
        return payload


def advise_post_sql_api(
    card: dict[str, Any],
    deterministic_policy: PostSQLDeterministicPolicy | dict[str, Any],
    *,
    llm_client: Any | None = None,
    enabled: bool = True,
) -> PostSQLAPIAdvice:
    policy = deterministic_policy.to_dict() if isinstance(deterministic_policy, PostSQLDeterministicPolicy) else dict(deterministic_policy)
    suggestion = str(policy.get("suggestion") or "CAVEAT_ONLY").upper()
    confidence = str(policy.get("confidence") or "LOW").upper()
    if confidence == "HIGH" and suggestion in MODES:
        return _from_policy(policy, source="DETERMINISTIC_BYPASS")
    if not enabled:
        return _from_policy(policy, source="DETERMINISTIC_FALLBACK")
    client = llm_client
    if client is None:
        try:
            client = get_llm_client()
        except Exception:
            return _from_policy(policy, source="DETERMINISTIC_FALLBACK", codes=["LLM_BACKEND_UNAVAILABLE"])
    messages = _messages_for_card(card)
    for attempt in range(2):
        try:
            raw = _call_client(client, messages)
            return parse_post_sql_api_advice(raw)
        except Exception as exc:
            messages = messages + [
                {
                    "role": "user",
                    "content": f"Return corrected JSON only. Previous parse failed: {type(exc).__name__}.",
                }
            ]
    return _from_policy(policy, source="DETERMINISTIC_FALLBACK", codes=["INVALID_JSON"])


def parse_post_sql_api_advice(raw: str | dict[str, Any]) -> PostSQLAPIAdvice:
    payload = json.loads(raw) if isinstance(raw, str) else dict(raw)
    mode = str(payload.get("mode") or "CAVEAT_ONLY").upper()
    if mode not in MODES:
        mode = "CAVEAT_ONLY"
    endpoint_id = payload.get("endpoint_id")
    needed_roles = payload.get("needed_roles") if isinstance(payload.get("needed_roles"), list) else []
    codes = payload.get("codes") if isinstance(payload.get("codes"), list) else []
    return PostSQLAPIAdvice(
        mode=mode,
        endpoint_id=str(endpoint_id) if endpoint_id else None,
        conf=max(0.0, min(1.0, float(payload.get("conf") or 0.0))),
        needed_roles=[str(item) for item in needed_roles][:8],
        codes=[str(item) for item in codes][:8],
    )


def _messages_for_card(card: dict[str, Any]) -> list[dict[str, str]]:
    schema = {"mode": "CALL_API|SKIP_API|CAVEAT_ONLY", "endpoint_id": "allowed endpoint id or null", "conf": "0.0-1.0", "needed_roles": "array", "codes": "array"}
    return [
        {
            "role": "system",
            "content": "Decide whether a planned safe GET API call is needed after SQL. Return JSON only. Do not answer the user or create params.",
        },
        {"role": "user", "content": json.dumps({"card": card, "schema": schema}, sort_keys=True)},
    ]


def _call_client(client: Any, messages: list[dict[str, str]]) -> str:
    if hasattr(client, "complete"):
        return str(client.complete(messages))
    if hasattr(client, "chat"):
        return str(client.chat(messages))
    if hasattr(client, "complete_json"):
        return json.dumps(client.complete_json(messages), sort_keys=True)
    raise TypeError("unsupported post-sql advisor client")


def _from_policy(policy: dict[str, Any], *, source: str, codes: list[str] | None = None) -> PostSQLAPIAdvice:
    mode = str(policy.get("suggestion") or "CAVEAT_ONLY").upper()
    if mode == "AMBIGUOUS":
        mode = "CAVEAT_ONLY"
    if mode not in MODES:
        mode = "CAVEAT_ONLY"
    return PostSQLAPIAdvice(
        mode=mode,
        endpoint_id=None,
        conf=1.0 if str(policy.get("confidence")).upper() == "HIGH" else 0.0,
        needed_roles=[],
        codes=[*(policy.get("codes") or []), *(codes or [])],
        source=source,
    )
