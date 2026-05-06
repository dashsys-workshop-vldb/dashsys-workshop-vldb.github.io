from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from .trajectory import compact_preview, redact_secrets


REQUIRED_CHECKPOINT_IDS = [
    "checkpoint_00_prompt_router",
    "checkpoint_01_raw_query",
    "checkpoint_02_query_normalization",
    "checkpoint_03_query_tokens",
    "checkpoint_04_relevance_scoring",
    "checkpoint_05_query_analysis",
    "checkpoint_06_lookup_path",
    "checkpoint_07_context_card",
    "checkpoint_08_candidate_plans",
    "checkpoint_09_plan_optimization",
    "checkpoint_10_evidence_policy",
    "checkpoint_11_call_budget",
    "checkpoint_12_validation",
    "checkpoint_13_tool_execution",
    "checkpoint_14_evidence_bus",
    "checkpoint_15_answer_slots",
    "checkpoint_16_answer_verification",
    "checkpoint_17_answer_reranking",
    "checkpoint_18_final_answer",
]


@dataclass
class Checkpoint:
    checkpoint_id: str
    stage: str
    technique: str
    input_summary: Any = None
    output_summary: Any = None
    output: Any = None
    effect: str = ""
    correctness_role: str = ""
    efficiency_role: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    duration_ms: float = 0.0
    warnings: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self, *, max_preview_chars: int = 1000) -> dict[str, Any]:
        payload = asdict(self)
        payload["input_summary"] = compact_preview(payload.get("input_summary"), max_preview_chars)
        payload["output_summary"] = compact_preview(payload.get("output_summary"), max_preview_chars)
        payload["output"] = compact_preview(payload.get("output"), max_preview_chars)
        return redact_secrets({key: value for key, value in payload.items() if value not in (None, {}, [], "")})


class CheckpointLogger:
    def __init__(self, *, max_preview_chars: int = 1000) -> None:
        self.max_preview_chars = max_preview_chars
        self._checkpoints: list[Checkpoint] = []
        self._starts: dict[str, float] = {}

    def start(self, checkpoint_id: str) -> None:
        self._starts[checkpoint_id] = time.perf_counter()

    def add_checkpoint(
        self,
        checkpoint_id: str,
        *,
        stage: str,
        technique: str,
        input_summary: Any = None,
        output_summary: Any = None,
        output: Any = None,
        effect: str = "",
        correctness_role: str = "",
        efficiency_role: str = "",
        duration_ms: float | None = None,
        warnings: list[str] | None = None,
        metrics: dict[str, Any] | None = None,
    ) -> Checkpoint:
        if duration_ms is None:
            started = self._starts.pop(checkpoint_id, None)
            duration_ms = (time.perf_counter() - started) * 1000 if started is not None else 0.0
        checkpoint = Checkpoint(
            checkpoint_id=checkpoint_id,
            stage=stage,
            technique=technique,
            input_summary=input_summary,
            output_summary=output_summary,
            output=output,
            effect=effect,
            correctness_role=correctness_role,
            efficiency_role=efficiency_role,
            duration_ms=round(float(duration_ms), 3),
            warnings=warnings or [],
            metrics=metrics or {},
        )
        self._checkpoints.append(checkpoint)
        return checkpoint

    def add_error_checkpoint(
        self,
        checkpoint_id: str,
        *,
        stage: str,
        technique: str,
        error: str,
        input_summary: Any = None,
        warnings: list[str] | None = None,
        metrics: dict[str, Any] | None = None,
    ) -> Checkpoint:
        return self.add_checkpoint(
            checkpoint_id,
            stage=stage,
            technique=technique,
            input_summary=input_summary,
            output_summary={"error": error},
            output={"error": error},
            effect="error checkpoint",
            correctness_role="captures failure instead of hiding it",
            efficiency_role="prevents repeated blind retries",
            warnings=warnings or [error],
            metrics=metrics,
        )

    def to_list(self) -> list[dict[str, Any]]:
        return [checkpoint.to_dict(max_preview_chars=self.max_preview_chars) for checkpoint in self._checkpoints]

    def summarize(self) -> dict[str, Any]:
        checkpoints = self.to_list()
        return {
            "count": len(checkpoints),
            "checkpoint_ids": [checkpoint.get("checkpoint_id") for checkpoint in checkpoints],
            "stages": [checkpoint.get("stage") for checkpoint in checkpoints],
            "total_duration_ms": round(sum(float(checkpoint.get("duration_ms", 0.0) or 0.0) for checkpoint in checkpoints), 3),
            "warnings": [warning for checkpoint in checkpoints for warning in checkpoint.get("warnings", [])][:12],
        }

    def clear(self) -> None:
        self._checkpoints.clear()
        self._starts.clear()
