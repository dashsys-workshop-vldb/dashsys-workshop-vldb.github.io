from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


ALLOWED_CONFLICT_FIELDS = {"code", "given", "required", "field", "role", "endpoint_id", "issue", "claim", "value", "scope"}
SENSITIVE_FEEDBACK_KEYS = {
    "gold",
    "gold_answer",
    "gold_sql",
    "gold_api",
    "category",
    "tags",
    "oracle",
    "oracle_sql",
    "oracle_api",
    "expected_trace",
    "expected_observable_trace",
    "expected_tool_calls",
    "raw_sql_rows",
    "sql_rows",
    "full_api_catalog",
    "endpoint_catalog",
    "api_docs",
    "full_schema",
    "sample_rows",
}


@dataclass(frozen=True)
class CorrectionConflict:
    code: str
    given: str | None = None
    required: str | None = None
    field: str | None = None
    role: str | None = None
    endpoint_id: str | None = None
    issue: str | None = None
    claim: str | None = None
    value: str | None = None
    scope: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {key: value for key, value in asdict(self).items() if value not in (None, "", [], {})}


@dataclass(frozen=True)
class MinimalCorrectionFeedback:
    task: str
    previous_decision: dict[str, Any]
    conflicts: list[CorrectionConflict] = field(default_factory=list)
    must_reconsider: list[str] = field(default_factory=list)
    allowed_outputs: list[str] = field(default_factory=list)
    forbidden_outputs: list[str] = field(default_factory=list)
    output_schema: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task": self.task,
            "previous_decision": _compact_mapping(self.previous_decision, allowed_keys=None, max_items=12),
            "conflicts": [conflict.to_dict() for conflict in self.conflicts[:8]],
            "must_reconsider": _compact_list(self.must_reconsider, 12),
            "allowed_outputs": _compact_list(self.allowed_outputs, 12),
            "forbidden_outputs": _compact_list(self.forbidden_outputs, 12),
            "output_schema": _compact_mapping(self.output_schema, allowed_keys=None, max_items=12),
        }

    @property
    def token_estimate(self) -> int:
        return estimate_feedback_tokens(self.to_dict())


def build_minimal_correction_feedback(
    *,
    task: str,
    previous_decision: dict[str, Any],
    conflicts: list[dict[str, Any] | CorrectionConflict],
    must_reconsider: list[str] | None = None,
    allowed_outputs: list[str] | None = None,
    forbidden_outputs: list[str] | None = None,
    output_schema: dict[str, Any] | None = None,
) -> MinimalCorrectionFeedback:
    return MinimalCorrectionFeedback(
        task=str(task),
        previous_decision=_compact_mapping(previous_decision, allowed_keys=None, max_items=12),
        conflicts=[_conflict(item) for item in conflicts[:8]],
        must_reconsider=_compact_list(must_reconsider or [], 12),
        allowed_outputs=_compact_list(allowed_outputs or [], 12),
        forbidden_outputs=_compact_list(forbidden_outputs or [], 12),
        output_schema=_compact_mapping(output_schema or {}, allowed_keys=None, max_items=12),
    )


def estimate_feedback_tokens(feedback: dict[str, Any] | MinimalCorrectionFeedback) -> int:
    payload = feedback.to_dict() if isinstance(feedback, MinimalCorrectionFeedback) else feedback
    return max(1, len(str(payload)) // 4)


def _conflict(item: dict[str, Any] | CorrectionConflict) -> CorrectionConflict:
    if isinstance(item, CorrectionConflict):
        return item
    compact = _compact_mapping(item, allowed_keys=ALLOWED_CONFLICT_FIELDS, max_items=len(ALLOWED_CONFLICT_FIELDS))
    return CorrectionConflict(
        code=str(compact.get("code") or "CONFLICT"),
        given=_as_optional_string(compact.get("given")),
        required=_as_optional_string(compact.get("required")),
        field=_as_optional_string(compact.get("field")),
        role=_as_optional_string(compact.get("role")),
        endpoint_id=_as_optional_string(compact.get("endpoint_id")),
        issue=_as_optional_string(compact.get("issue")),
        claim=_as_optional_string(compact.get("claim")),
        value=_as_optional_string(compact.get("value")),
        scope=_as_optional_string(compact.get("scope")),
    )


def _compact_mapping(
    payload: dict[str, Any],
    *,
    allowed_keys: set[str] | None,
    max_items: int,
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in payload.items():
        key_text = str(key)
        lower = key_text.lower()
        if lower in SENSITIVE_FEEDBACK_KEYS or (allowed_keys is not None and key_text not in allowed_keys):
            continue
        if isinstance(value, (dict, list, tuple, set)):
            if key_text == "output_schema" and isinstance(value, dict):
                out[key_text] = {str(k): _short_scalar(v) for k, v in list(value.items())[:12]}
            elif allowed_keys is not None:
                out[key_text] = _short_scalar(value)
            else:
                out[key_text] = _compact_nested(value)
        else:
            out[key_text] = _short_scalar(value)
        if len(out) >= max_items:
            break
    return out


def _compact_nested(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(k): _short_scalar(v)
            for k, v in list(value.items())[:8]
            if str(k).lower() not in SENSITIVE_FEEDBACK_KEYS
        }
    if isinstance(value, (list, tuple, set)):
        return [_short_scalar(item) for item in list(value)[:8]]
    return _short_scalar(value)


def _compact_list(values: list[Any], limit: int) -> list[str]:
    return [str(item)[:120] for item in values[:limit] if item not in (None, "", [], {})]


def _short_scalar(value: Any) -> Any:
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float)):
        return value
    text = str(value)
    return text if len(text) <= 160 else text[:157] + "..."


def _as_optional_string(value: Any) -> str | None:
    if value in (None, "", [], {}):
        return None
    return str(value)[:160]
