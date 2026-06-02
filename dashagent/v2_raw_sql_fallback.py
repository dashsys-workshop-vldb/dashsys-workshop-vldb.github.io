from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from typing import Any

from .raw_sql_safety_gate import RawSQLSafetyGate, RawSQLSafetyGateResult
from .trajectory import compact_preview, redact_secrets
from .v2_semantic_ir_support import IRSupportResult
from .v2_weak_model_protocol import _elapsed_ms


RAW_SQL_FALLBACK_TOOL_NAME = "submit_raw_sql_fallback"


@dataclass
class RawSQLFallbackResult:
    ok: bool
    task_id: str | None = None
    reason: str | None = None
    sql: str | None = None
    params: list[Any] = field(default_factory=list)
    safety_gate: RawSQLSafetyGateResult | None = None
    repair_attempted: bool = False
    repair_success: bool = False
    rejected_reason: str | None = None
    raw_preview: Any | None = None
    backend_generated_sql: bool = False
    latency_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def raw_sql_fallback_tool_schema() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": RAW_SQL_FALLBACK_TOOL_NAME,
            "description": "Submit one LLM-owned read-only raw SQL fallback for an unsupported local Semantic IR task.",
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "task_id": {"type": "string"},
                    "reason": {"type": "string"},
                    "sql": {"type": "string"},
                    "params": {"type": "array"},
                },
                "required": ["task_id", "reason", "sql", "params"],
            },
        },
    }


def extract_raw_sql_fallback_tool_arguments(result: dict[str, Any]) -> dict[str, Any] | None:
    for call in result.get("tool_calls") or []:
        if not isinstance(call, dict):
            continue
        name = call.get("name") or call.get("tool") or (call.get("function") or {}).get("name")
        if name != RAW_SQL_FALLBACK_TOOL_NAME:
            continue
        args = call.get("arguments")
        if isinstance(args, dict):
            return args
        raw_args = call.get("raw_arguments")
        if isinstance(raw_args, str):
            try:
                parsed = json.loads(raw_args)
            except Exception:
                return {"_raw": raw_args}
            return parsed if isinstance(parsed, dict) else {"_raw": raw_args}
    return None


def run_raw_sql_fallback_planner(
    *,
    client: Any,
    user_prompt: str,
    semantic_plan: dict[str, Any],
    support_result: IRSupportResult,
    allowed_schema_card: list[dict[str, Any]],
    safety_gate: RawSQLSafetyGate | None = None,
) -> RawSQLFallbackResult:
    started = time.perf_counter()
    safety_gate = safety_gate or RawSQLSafetyGate()
    task = _task_for_support(semantic_plan, support_result.task_id)
    if not isinstance(task, dict):
        return RawSQLFallbackResult(False, task_id=support_result.task_id, rejected_reason="raw_sql_fallback_unknown_task", latency_ms=_elapsed_ms(started))
    if str(task.get("source") or "").upper() != "LOCAL_SNAPSHOT":
        return RawSQLFallbackResult(False, task_id=support_result.task_id, rejected_reason="raw_sql_fallback_requires_local_snapshot_task", latency_ms=_elapsed_ms(started))

    first = _call_raw_sql_tool(
        client,
        system_prompt=_raw_sql_system_prompt(),
        user_prompt=_raw_sql_user_prompt(
            user_prompt=user_prompt,
            semantic_plan=semantic_plan,
            support_result=support_result,
            allowed_schema_card=allowed_schema_card,
            repair_context=None,
        ),
    )
    args, raw_preview, error = first
    if error or args is None:
        return RawSQLFallbackResult(False, task_id=support_result.task_id, rejected_reason=error or "missing_raw_sql_tool_call", raw_preview=raw_preview, latency_ms=_elapsed_ms(started))
    candidate = _result_from_args(args, safety_gate=safety_gate, started=started, raw_preview=raw_preview)
    if candidate.safety_gate and candidate.safety_gate.passed:
        return candidate

    repair = _call_raw_sql_tool(
        client,
        system_prompt=_raw_sql_repair_system_prompt(),
        user_prompt=_raw_sql_user_prompt(
            user_prompt=user_prompt,
            semantic_plan=semantic_plan,
            support_result=support_result,
            allowed_schema_card=allowed_schema_card,
            repair_context={
                "previous_raw_sql": args,
                "safety_gate": candidate.safety_gate.to_dict() if candidate.safety_gate else None,
            },
        ),
    )
    repair_args, repair_preview, repair_error = repair
    if repair_error or repair_args is None:
        candidate.repair_attempted = True
        candidate.repair_success = False
        candidate.rejected_reason = repair_error or "missing_raw_sql_repair_tool_call"
        candidate.raw_preview = {"initial": raw_preview, "repair": repair_preview}
        return candidate
    repaired = _result_from_args(repair_args, safety_gate=safety_gate, started=started, raw_preview={"initial": raw_preview, "repair": repair_preview})
    repaired.repair_attempted = True
    repaired.repair_success = bool(repaired.safety_gate and repaired.safety_gate.passed)
    return repaired


def _call_raw_sql_tool(client: Any, *, system_prompt: str, user_prompt: str) -> tuple[dict[str, Any] | None, Any, str | None]:
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
    tool_choice = {"type": "function", "function": {"name": RAW_SQL_FALLBACK_TOOL_NAME}}
    try:
        result = client.generate_messages(messages, tools=[raw_sql_fallback_tool_schema()], tool_choice=tool_choice, parallel_tool_calls=False)
    except TypeError:
        result = client.generate_messages(messages, tools=[raw_sql_fallback_tool_schema()], tool_choice=tool_choice)
    except Exception as exc:
        return None, compact_preview(str(exc), 1000), str(exc)
    if not isinstance(result, dict):
        return None, compact_preview(result, 1000), "LLM client returned non-dict raw SQL fallback response."
    if not result.get("ok", True):
        return None, compact_preview(result, 1000), str(result.get("error") or result.get("reason") or "LLM raw SQL fallback failed.")
    args = extract_raw_sql_fallback_tool_arguments(result)
    return args, compact_preview(result, 1200), None if args is not None else "Missing submit_raw_sql_fallback tool call."


def _result_from_args(args: dict[str, Any], *, safety_gate: RawSQLSafetyGate, started: float, raw_preview: Any) -> RawSQLFallbackResult:
    params = args.get("params") if isinstance(args.get("params"), list) else []
    sql = str(args.get("sql") or "").strip()
    safety = safety_gate.check(sql, params)
    return RawSQLFallbackResult(
        ok=safety.passed,
        task_id=str(args.get("task_id") or "").strip() or None,
        reason=str(args.get("reason") or "").strip() or None,
        sql=safety.sql or sql,
        params=list(params),
        safety_gate=safety,
        rejected_reason=None if safety.passed else safety.error_type,
        raw_preview=redact_secrets(raw_preview),
        backend_generated_sql=False,
        latency_ms=_elapsed_ms(started),
    )


def _task_for_support(plan: dict[str, Any], task_id: str | None) -> dict[str, Any] | None:
    for task in plan.get("tasks") or []:
        if isinstance(task, dict) and str(task.get("task_id") or "") == str(task_id or ""):
            return task
    return None


def _raw_sql_system_prompt() -> str:
    return (
        "You are the LLM-owned raw SQL fallback generator for DASHSys V2. "
        "Use submit_raw_sql_fallback exactly once. The backend will not generate or repair SQL. "
        "Return one read-only SELECT statement only. No mutations, PRAGMA, COPY, external file reads, comments, or multiple statements. "
        "Include LIMIT unless the query is aggregate/count."
    )


def _raw_sql_repair_system_prompt() -> str:
    return (
        "Your previous raw SQL fallback failed the safety gate. Submit exactly one corrected submit_raw_sql_fallback tool call. "
        "Do not ask the backend to repair SQL. Use SELECT only, one statement, and LIMIT unless aggregate/count."
    )


def _raw_sql_user_prompt(
    *,
    user_prompt: str,
    semantic_plan: dict[str, Any],
    support_result: IRSupportResult,
    allowed_schema_card: list[dict[str, Any]],
    repair_context: dict[str, Any] | None,
) -> str:
    payload = {
        "task": "LLM_OWNED_RAW_SQL_FALLBACK",
        "user_prompt": user_prompt,
        "semantic_plan": compact_preview(semantic_plan, 1600),
        "unsupported_ir": support_result.to_dict(),
        "allowed_schema_card": allowed_schema_card,
        "rules": [
            "Use raw SQL only for the unsupported LOCAL_SNAPSHOT task.",
            "Backend does not generate SQL, choose tables/columns/filters, add LIMIT, or repair SQL.",
            "SQL must be one read-only SELECT statement.",
            "SQL must include LIMIT unless aggregate/count.",
            "Use params as a JSON list.",
        ],
        "repair_context": repair_context,
    }
    return json.dumps(redact_secrets(payload), ensure_ascii=False, sort_keys=True)
