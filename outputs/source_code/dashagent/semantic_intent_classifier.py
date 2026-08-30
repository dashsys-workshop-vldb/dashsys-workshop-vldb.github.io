from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

from .llm_client import get_llm_client


INTENTS = {"CONCEPT", "DATA", "LIVE_API", "MIXED", "AMBIG", "UNSUPPORTED"}
NEEDS = {"NONE", "SQL", "API", "SQL_API", "UNKNOWN"}


@dataclass(frozen=True)
class SemanticIntentDecision:
    intent: str
    need: str
    no_tool: bool
    sql: bool
    api: bool
    conf: float
    codes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["conf"] = round(float(self.conf), 4)
        return payload


def parse_semantic_intent_decision(raw: str | dict[str, Any]) -> SemanticIntentDecision:
    payload = json.loads(raw) if isinstance(raw, str) else dict(raw)
    allowed = {"intent", "need", "no_tool", "sql", "api", "conf", "codes", "flags"}
    payload = {key: payload.get(key) for key in allowed}
    intent = str(payload.get("intent") or "AMBIG").upper()
    need = str(payload.get("need") or "UNKNOWN").upper()
    if intent not in INTENTS:
        intent = "AMBIG"
    if need not in NEEDS:
        need = "UNKNOWN"
    codes = payload.get("codes") if isinstance(payload.get("codes"), list) else payload.get("flags")
    if not isinstance(codes, list):
        codes = []
    return SemanticIntentDecision(
        intent=intent,
        need=need,
        no_tool=bool(payload.get("no_tool")),
        sql=bool(payload.get("sql")),
        api=bool(payload.get("api")),
        conf=max(0.0, min(1.0, float(payload.get("conf") or 0.0))),
        codes=[str(code) for code in codes][:8],
    )


def classify_semantic_intent(
    context: dict[str, Any],
    *,
    llm_client: Any | None = None,
    use_llm: bool | None = None,
) -> SemanticIntentDecision:
    if llm_client is None and not use_llm:
        return _fallback_decision(context)
    client = llm_client
    if client is None:
        try:
            client = get_llm_client()
        except Exception:
            return _fallback_decision(context)
    messages = _messages_for_context(context)
    last_error = None
    for attempt in range(2):
        try:
            raw = _call_client(client, messages)
            return parse_semantic_intent_decision(raw)
        except Exception as exc:
            last_error = exc
            messages = messages + [
                {
                    "role": "user",
                    "content": (
                        "Return corrected JSON only with keys: intent, need, no_tool, sql, api, conf, codes. "
                        f"Previous parse failed: {type(exc).__name__}."
                    ),
                }
            ]
            continue
    _ = last_error
    return SemanticIntentDecision("AMBIG", "UNKNOWN", False, False, False, 0.0, ["INVALID_JSON"])


def _messages_for_context(context: dict[str, Any]) -> list[dict[str, str]]:
    schema = {
        "intent": "CONCEPT|DATA|LIVE_API|MIXED|AMBIG|UNSUPPORTED",
        "need": "NONE|SQL|API|SQL_API|UNKNOWN",
        "no_tool": "boolean",
        "sql": "boolean",
        "api": "boolean",
        "conf": "0.0-1.0",
        "codes": "array of short codes",
    }
    return [
        {
            "role": "system",
            "content": (
                "Classify semantic intent for routing only. Return JSON only. "
                "Do not write SQL, API parameters, final answers, reasons, or explanations."
            ),
        },
        {"role": "user", "content": json.dumps({"ctx": context, "schema": schema}, sort_keys=True)},
    ]


def _call_client(client: Any, messages: list[dict[str, str]]) -> str:
    if hasattr(client, "complete"):
        return str(client.complete(messages))
    if hasattr(client, "chat"):
        return str(client.chat(messages))
    if hasattr(client, "complete_json"):
        return json.dumps(client.complete_json(messages), sort_keys=True)
    raise TypeError("unsupported semantic intent client")


def _fallback_decision(context: dict[str, Any]) -> SemanticIntentDecision:
    features = context.get("features") if isinstance(context.get("features"), dict) else context.get("f")
    features = features if isinstance(features, dict) else {}
    cue = set(features.get("conceptual_cues") or features.get("cue") or [])
    retr = set(features.get("retrieval_cues") or features.get("retr") or [])
    count = set(features.get("count_cues") or features.get("count") or [])
    status = set(features.get("status_cues") or features.get("status") or [])
    date = set(features.get("date_cues") or features.get("date") or [])
    fields = set(features.get("field_cues") or features.get("fields") or [])
    rel = set(features.get("relationship_cues") or features.get("rel") or [])
    entity = set(features.get("entities") or features.get("entity") or [])
    caps = set(features.get("capability_matches") or features.get("cap") or [])
    domains = set(features.get("domain_terms") or features.get("domain") or [])
    concrete = bool(retr or count or fields or rel or (entity and (status or date)))
    conceptual = bool(cue and not concrete)
    api_only_domain = bool(domains & {"TAG", "AUDIT", "MERGE_POLICY"}) and not any(cap.startswith("SQL_") for cap in caps)
    if conceptual:
        return SemanticIntentDecision("CONCEPT", "NONE", True, False, False, 0.9, ["FALLBACK"])
    if concrete and api_only_domain:
        return SemanticIntentDecision("LIVE_API", "API", False, False, True, 0.82, ["FALLBACK"])
    if concrete and any(cap.startswith("API_") for cap in caps) and any(cap.startswith("SQL_") for cap in caps):
        return SemanticIntentDecision("MIXED", "SQL_API", False, True, True, 0.82, ["FALLBACK"])
    if concrete:
        return SemanticIntentDecision("DATA", "SQL", False, True, False, 0.84, ["FALLBACK"])
    if api_only_domain:
        return SemanticIntentDecision("LIVE_API", "API", False, False, True, 0.65, ["FALLBACK"])
    return SemanticIntentDecision("AMBIG", "UNKNOWN", False, False, False, 0.5, ["FALLBACK"])
