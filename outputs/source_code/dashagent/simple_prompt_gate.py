from __future__ import annotations

from dataclasses import asdict, dataclass

from .prompt_router import LLM_DIRECT, route_prompt


@dataclass(frozen=True)
class SimplePromptDecision:
    is_simple: bool
    reason: str
    suggested_action: str
    confidence: float

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["confidence"] = round(float(self.confidence), 4)
        return payload


def decide_simple_prompt(query: str) -> SimplePromptDecision:
    route = route_prompt(query)
    if route.mode == LLM_DIRECT:
        return SimplePromptDecision(
            is_simple=True,
            reason=route.reason,
            suggested_action="LLM_DIRECT",
            confidence=route.confidence,
        )
    return SimplePromptDecision(
        is_simple=False,
        reason=route.reason,
        suggested_action="USE_DATA_PIPELINE",
        confidence=route.confidence,
    )
