from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ResultBundle:
    """Runtime evidence container for LLM-owned V2 pass execution."""

    runtime_passes: list[dict[str, Any]] = field(default_factory=list)
    tool_results: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def pass_results_count(self) -> int:
        return len(self.runtime_passes)

    @classmethod
    def from_pass_results(cls, runtime_passes: list[dict[str, Any]], tool_results: list[dict[str, Any]]) -> "ResultBundle":
        return cls(runtime_passes=list(runtime_passes), tool_results=list(tool_results))
