from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4


@dataclass
class RunBudget:
    max_passes: int = 6
    max_parallelism: int = 4
    max_sql_workers: int = 2
    max_api_workers: int = 2
    max_repair_attempts: int = 1
    max_answer_repair_attempts: int = 1
    run_timeout_ms: int = 30_000

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RunContext:
    run_id: str
    original_prompt: str
    prompt_id: str | None = None
    plan_version: int = 1
    status: str = "RUNNING"
    result_bundle_id: str = ""
    evidence_bus_id: str = ""
    created_at: str = ""
    deadline_at: str = ""
    budget: RunBudget = field(default_factory=RunBudget)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["budget"] = self.budget.to_dict()
        return payload


@dataclass
class ErrorEnvelope:
    error_id: str
    run_id: str
    pass_id: str | None
    stage: str
    error_type: str
    severity: str
    retryable: bool
    repairable_by_llm: bool
    message: str
    sanitized_message: str
    action: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class StageEvent:
    run_id: str
    pass_id: str
    global_pass_id: str
    attempt_id: int
    plan_version: int
    stage: str
    event: str
    timestamp: str
    status: str = "OK"
    error_type: str | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def create_run_context(
    original_prompt: str,
    *,
    prompt_id: str | None = None,
    budget: RunBudget | None = None,
    run_id: str | None = None,
) -> RunContext:
    selected_budget = budget or RunBudget()
    created = datetime.now(timezone.utc)
    selected_run_id = run_id or f"run_{uuid4().hex}"
    return RunContext(
        run_id=selected_run_id,
        prompt_id=prompt_id,
        original_prompt=str(original_prompt),
        plan_version=1,
        status="RUNNING",
        result_bundle_id=f"bundle_{selected_run_id}",
        evidence_bus_id=f"evidence_{selected_run_id}",
        created_at=created.isoformat(),
        deadline_at=(created + timedelta(milliseconds=selected_budget.run_timeout_ms)).isoformat(),
        budget=selected_budget,
    )


def error_envelope(
    *,
    run_id: str,
    pass_id: str | None,
    stage: str,
    error_type: str,
    message: str,
    severity: str = "RECOVERABLE",
    retryable: bool = False,
    repairable_by_llm: bool = False,
    action: str = "RECORD_CAVEAT",
) -> ErrorEnvelope:
    return ErrorEnvelope(
        error_id=f"err_{uuid4().hex}",
        run_id=run_id,
        pass_id=pass_id,
        stage=stage,
        error_type=error_type,
        severity=severity,
        retryable=retryable,
        repairable_by_llm=repairable_by_llm,
        message=str(message),
        sanitized_message=str(message)[:500],
        action=action,
    )
