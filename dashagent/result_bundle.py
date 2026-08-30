from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ResultBundle:
    """Runtime evidence container for LLM-owned V2 pass execution."""

    run_id: str | None = None
    runtime_passes: list[dict[str, Any]] = field(default_factory=list)
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    append_events: list[dict[str, Any]] = field(default_factory=list)
    _latest_attempts: dict[str, int] = field(default_factory=dict, repr=False)
    _committed: set[tuple[str, int]] = field(default_factory=set, repr=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "runtime_passes": self.runtime_passes,
            "tool_results": self.tool_results,
            "append_events": self.append_events,
        }

    @property
    def pass_results_count(self) -> int:
        return len(self.runtime_passes)

    @classmethod
    def from_pass_results(cls, runtime_passes: list[dict[str, Any]], tool_results: list[dict[str, Any]], *, run_id: str | None = None) -> "ResultBundle":
        bundle = cls(run_id=run_id, tool_results=list(tool_results))
        for item in runtime_passes:
            bundle.append_pass_result(item)
        return bundle

    def append_pass_result(self, pass_result: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(pass_result, dict):
            event = {"appended": False, "error_type": "malformed_pass_result"}
            self.append_events.append(event)
            return event
        result_run_id = pass_result.get("run_id")
        if self.run_id and result_run_id and result_run_id != self.run_id:
            event = {"appended": False, "error_type": "run_isolation_error", "run_id": result_run_id}
            self.append_events.append(event)
            return event
        pass_id = str(pass_result.get("pass_id") or "")
        attempt_id = int(pass_result.get("attempt_id") or 0)
        if not pass_id:
            event = {"appended": False, "error_type": "missing_pass_id"}
            self.append_events.append(event)
            return event
        latest = self._latest_attempts.get(pass_id)
        if latest is not None and attempt_id < latest:
            event = {"appended": False, "error_type": "stale_attempt", "pass_id": pass_id, "attempt_id": attempt_id}
            self.append_events.append(event)
            return event
        key = (pass_id, attempt_id)
        if key in self._committed:
            event = {"appended": False, "error_type": "duplicate_commit", "pass_id": pass_id, "attempt_id": attempt_id}
            self.append_events.append(event)
            return event
        normalized = dict(pass_result)
        if self.run_id and not normalized.get("run_id"):
            normalized["run_id"] = self.run_id
        self.runtime_passes.append(normalized)
        self._committed.add(key)
        self._latest_attempts[pass_id] = attempt_id
        event = {"appended": True, "pass_id": pass_id, "attempt_id": attempt_id}
        self.append_events.append(event)
        return event
