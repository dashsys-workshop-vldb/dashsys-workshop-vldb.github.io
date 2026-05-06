from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


SECRET_KEYS = {
    "authorization",
    "x-api-key",
    "client_secret",
    "access_token",
    "refresh_token",
    "api_key",
    "secret",
}


def redact_value(key: str, value: Any) -> Any:
    lowered = key.lower()
    if lowered.startswith("no_secret"):
        return value
    if (
        lowered in SECRET_KEYS
        or lowered.endswith("_token")
        or lowered.endswith("-token")
        or lowered in {"token", "bearer"}
        or "secret" in lowered
    ):
        return "[REDACTED]"
    return value


def redact_secrets(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {key: redact_value(str(key), redact_secrets(value)) for key, value in obj.items()}
    if isinstance(obj, list):
        return [redact_secrets(item) for item in obj]
    if isinstance(obj, str):
        redacted = obj
        for env_name, env_value in os.environ.items():
            if env_value and len(env_value) >= 12 and env_value in redacted:
                redacted = redacted.replace(env_value, "[REDACTED]")
        return redacted
    return obj


IMPORTANT_PREVIEW_KEYS = [
    "id",
    "name",
    "status",
    "state",
    "total",
    "count",
    "errors",
    "error",
    "result_preview",
]


def compact_preview(obj: Any, max_chars: int = 1000) -> Any:
    redacted = redact_secrets(obj)
    redacted = structural_preview(redacted)
    text = json.dumps(redacted, default=str, ensure_ascii=False)
    if len(text) <= max_chars:
        return redacted
    return {"preview": text[:max_chars] + "...", "truncated": True}


def structural_preview(obj: Any) -> Any:
    if isinstance(obj, list):
        return {
            "items": [structural_preview(item) for item in obj[:3]],
            "total_items": len(obj),
            "truncated_items": len(obj) > 3,
        }
    if isinstance(obj, dict):
        compact: dict[str, Any] = {}
        for key in IMPORTANT_PREVIEW_KEYS:
            if key in obj:
                compact[key] = structural_preview(obj[key])
        for key, value in obj.items():
            if key in compact:
                continue
            if key in {"original_sql", "sql"} and ("row_count" in obj or "rows" in obj):
                continue
            if value in ({}, [], None, ""):
                continue
            if len(compact) >= 8:
                compact["truncated_fields"] = max(0, len(obj) - len(compact))
                break
            compact[key] = structural_preview(value)
        return compact
    return obj


def estimate_tokens(text_or_obj: Any) -> int:
    text = text_or_obj if isinstance(text_or_obj, str) else json.dumps(text_or_obj, default=str)
    try:
        import tiktoken  # type: ignore

        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    except Exception:
        return max(1, len(text) // 4)


@dataclass
class TrajectoryLogger:
    query_id: str
    original_query: str
    strategy: str
    route_type: str
    domain_type: str
    max_preview_chars: int = 1000
    start_time: float = field(default_factory=time.perf_counter)
    steps: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    final_answer: str | None = None
    timings: dict[str, float] = field(default_factory=dict)
    checkpoints: list[dict[str, Any]] = field(default_factory=list)

    def add_step(self, kind: str, payload: dict[str, Any]) -> None:
        self.steps.append({"kind": kind, **redact_secrets(payload)})

    def add_validation(self, target: str, validation: Any) -> None:
        payload = validation.to_dict() if hasattr(validation, "to_dict") else validation
        self.add_step("validation", {"target": target, "result": payload})

    def add_sql_call(self, sql: str, validation: Any, result: dict[str, Any]) -> None:
        self.add_step(
            "sql_call",
            {
                "sql": sql,
                "validation": validation.to_dict() if hasattr(validation, "to_dict") else validation,
                "result": compact_preview(result, self.max_preview_chars),
            },
        )

    def add_api_call(
        self,
        method: str,
        url: str,
        params: dict[str, Any] | None,
        headers: dict[str, Any] | None,
        validation: Any,
        result: dict[str, Any],
    ) -> None:
        self.add_step(
            "api_call",
            {
                "method": method,
                "url": url,
                "params": params or {},
                "headers": redact_secrets(headers or {}),
                "validation": validation.to_dict() if hasattr(validation, "to_dict") else validation,
                "result": compact_preview(result, self.max_preview_chars),
            },
        )

    def add_error(self, error: str) -> None:
        self.errors.append(error)
        self.add_step("error", {"error": error})

    def set_timing(self, name: str, seconds: float) -> None:
        self.timings[name] = seconds

    def set_checkpoints(self, checkpoints: list[dict[str, Any]]) -> None:
        self.checkpoints = redact_secrets(checkpoints)

    def finish(self, final_answer: str) -> dict[str, Any]:
        self.final_answer = final_answer
        runtime = time.perf_counter() - self.start_time
        token_steps = [step for step in self.steps if step.get("kind") != "answer_diagnostics"]
        payload = {
            "query_id": self.query_id,
            "original_query": self.original_query,
            "strategy": self.strategy,
            "route_type": self.route_type,
            "domain_type": self.domain_type,
            "checkpoints": self.checkpoints,
            "steps": self.steps,
            "final_answer": final_answer,
            "runtime": runtime,
            "tool_call_count": sum(1 for step in self.steps if step["kind"] in {"sql_call", "api_call"}),
            "sql_call_count": sum(1 for step in self.steps if step["kind"] == "sql_call"),
            "api_call_count": sum(1 for step in self.steps if step["kind"] == "api_call"),
            "estimated_tokens": estimate_tokens({"query": self.original_query, "steps": token_steps, "answer": final_answer}),
            "timings": self.timings,
            "preprocessing_time": self.timings.get("preprocessing_time", 0.0),
            "planning_time": self.timings.get("planning_time", 0.0),
            "execution_time": self.timings.get("execution_time", 0.0),
            "answer_time": self.timings.get("answer_time", 0.0),
            "errors": self.errors,
        }
        return redact_secrets(payload)

    def save(self, path: Path, final_answer: str) -> dict[str, Any]:
        payload = self.finish(final_answer)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
        return payload
