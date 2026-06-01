from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any

from .trajectory import compact_preview, redact_secrets


ALLOWED_ROUTE_CARD_VALUES = {"DIRECT", "EVIDENCE"}
ALLOWED_TASK_PATHS = {"DIRECT", "SQL", "API", "SQL_AND_API", "AGGREGATE"}
ROUTE_CARD_MAX_TOKENS = 80
DIRECT_CHALLENGE_MAX_TOKENS = 40
TASK_LEDGER_MAX_TOKENS = 300
CANDIDATE_CARD_MAX_TOKENS = 220
CANDIDATE_REPAIR_MAX_TOKENS = 220


@dataclass
class RouteCard:
    route: str
    direct_answer: str | None = None
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DirectRouteChallenge:
    needs_evidence: bool
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TaskLedgerTask:
    task_id: str
    path: str
    depends_on: list[str]
    description: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TaskLedger:
    tasks: list[TaskLedgerTask] = field(default_factory=list)
    aggregation_instruction: str = ""
    shape_error: str | None = None
    shape_error_message: str | None = None
    legacy_plan_payload: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "tasks": [task.to_dict() for task in self.tasks],
            "aggregation_instruction": self.aggregation_instruction,
            "shape_error": self.shape_error,
            "shape_error_message": self.shape_error_message,
            "legacy_plan_payload": compact_preview(self.legacy_plan_payload, 1200) if self.legacy_plan_payload else None,
        }


@dataclass
class PassCandidateCard:
    path: str
    sql: str | None = None
    params: Any = None
    method: str | None = None
    api_path: str | None = None
    parse_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class WeakProtocolResult:
    plan_payload: dict[str, Any]
    diagnostics: dict[str, Any]
    raw_preview: Any | None = None
    parse_error: bool = False
    backend_unavailable: bool = False
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ProtocolParseError(ValueError):
    pass


def run_weak_model_stable_protocol(
    *,
    client: Any,
    user_prompt: str,
    schema_context: dict[str, Any],
    endpoint_context: list[dict[str, Any]],
    repair_context: dict[str, Any] | None = None,
) -> WeakProtocolResult:
    started = time.perf_counter()
    diagnostics: dict[str, Any] = {
        "weak_model_stable_protocol_used": True,
        "weak_protocol_route_card_used": repair_context is None,
        "weak_protocol_task_ledger_used": False,
        "llm_route_gate_used": repair_context is None,
        "route_card_success": False,
        "route_card_route": None,
        "route_card_repair_attempted": False,
        "route_gate_success": False,
        "route_gate_route": None,
        "route_gate_repair_attempted": False,
        "task_ledger_success": False,
        "task_ledger_repair_attempted": False,
        "candidate_card_success": 0,
        "pass_candidate_cards": 0,
        "sql_candidate_cards": 0,
        "api_candidate_cards": 0,
        "candidate_repair_attempts": 0,
        "direct_route_challenge_used": False,
        "direct_route_challenge_needs_evidence": None,
        "direct_route_challenge_repair_attempted": False,
        "backend_route_inference_used": False,
        "backend_semantic_planning_used": False,
        "backend_semantic_decomposition_used": False,
        "route_card_max_tokens": ROUTE_CARD_MAX_TOKENS,
        "direct_route_challenge_max_tokens": DIRECT_CHALLENGE_MAX_TOKENS,
        "task_ledger_max_tokens": TASK_LEDGER_MAX_TOKENS,
        "candidate_card_max_tokens": CANDIDATE_CARD_MAX_TOKENS,
        "candidate_repair_max_tokens": CANDIDATE_REPAIR_MAX_TOKENS,
    }
    if repair_context:
        return _run_repair_context_protocol(
            client=client,
            user_prompt=user_prompt,
            schema_context=schema_context,
            endpoint_context=endpoint_context,
            repair_context=repair_context,
            diagnostics=diagnostics,
            started=started,
        )

    route_raw, route_error, route_latency_ms = _call_text(
        client,
        system_prompt=_route_card_system_prompt(),
        user_prompt=_route_card_user_prompt(user_prompt),
        max_tokens=ROUTE_CARD_MAX_TOKENS,
    )
    diagnostics["route_card_latency_ms"] = route_latency_ms
    raw_previews: dict[str, Any] = {"route_card": compact_preview(route_raw or route_error, 1000)}
    route_card: RouteCard | None = None
    legacy_payload = _legacy_full_plan_payload(route_raw)
    if legacy_payload is not None:
        route_card = _route_card_from_legacy_payload(legacy_payload)
        diagnostics.update(
            {
                "route_card_success": True,
                "route_card_route": route_card.route,
                "route_gate_success": True,
                "route_gate_route": _planner_route_from_route_card(route_card.route),
                "weak_protocol_legacy_monolithic_response_accepted": True,
                "planner_success": True,
                "planner_json_fallback_used": True,
                "planner_provider_latency_ms": _elapsed_ms(started),
            }
        )
        if route_card.route == "DIRECT":
            challenge, challenge_raw_preview = _run_direct_route_challenge(
                client=client,
                user_prompt=user_prompt,
                route_card=route_card,
                diagnostics=diagnostics,
            )
            raw_previews.update(challenge_raw_preview)
            if not challenge.needs_evidence:
                return WeakProtocolResult(plan_payload=legacy_payload, diagnostics=diagnostics, raw_preview=raw_previews)
            diagnostics["weak_protocol_legacy_direct_challenge_forced_evidence"] = True
            diagnostics["planner_success"] = False
            route_card = RouteCard(route="EVIDENCE", direct_answer=None, reason=challenge.reason)
        else:
            return WeakProtocolResult(plan_payload=legacy_payload, diagnostics=diagnostics, raw_preview=raw_previews)
    route_parse_error = route_error
    if route_card is None and not route_error:
        try:
            route_card = parse_route_card(route_raw)
            route_parse_error = None
        except Exception as exc:
            route_parse_error = str(exc)
    if route_card is None:
        diagnostics["route_card_repair_attempted"] = True
        diagnostics["route_gate_repair_attempted"] = True
        repair_raw, repair_error, repair_latency_ms = _call_text(
            client,
            system_prompt=_route_card_repair_system_prompt(),
            user_prompt=_route_card_repair_user_prompt(user_prompt, route_raw, route_parse_error),
            max_tokens=ROUTE_CARD_MAX_TOKENS,
        )
        diagnostics["route_card_repair_latency_ms"] = repair_latency_ms
        raw_previews["route_card_repair"] = compact_preview(repair_raw or repair_error, 1000)
        legacy_payload = _legacy_full_plan_payload(repair_raw)
        if legacy_payload is not None:
            route_card = _route_card_from_legacy_payload(legacy_payload)
            diagnostics.update(
                {
                    "route_card_success": True,
                    "route_card_route": route_card.route,
                    "route_gate_success": True,
                    "route_gate_route": _planner_route_from_route_card(route_card.route),
                    "weak_protocol_legacy_monolithic_response_accepted": True,
                    "planner_success": True,
                    "planner_json_fallback_used": True,
                    "planner_provider_latency_ms": _elapsed_ms(started),
                }
            )
            if route_card.route == "DIRECT":
                challenge, challenge_raw_preview = _run_direct_route_challenge(
                    client=client,
                    user_prompt=user_prompt,
                    route_card=route_card,
                    diagnostics=diagnostics,
                )
                raw_previews.update(challenge_raw_preview)
                if not challenge.needs_evidence:
                    return WeakProtocolResult(plan_payload=legacy_payload, diagnostics=diagnostics, raw_preview=raw_previews)
                diagnostics["weak_protocol_legacy_direct_challenge_forced_evidence"] = True
                diagnostics["planner_success"] = False
                route_card = RouteCard(route="EVIDENCE", direct_answer=None, reason=challenge.reason)
            else:
                return WeakProtocolResult(plan_payload=legacy_payload, diagnostics=diagnostics, raw_preview=raw_previews)
        if not repair_error:
            try:
                route_card = parse_route_card(repair_raw)
                route_parse_error = None
            except Exception as exc:
                route_parse_error = str(exc)
        else:
            route_parse_error = repair_error
        if route_card is None and route_error and repair_error:
            diagnostics.update(
                {
                    "route_card_success": False,
                    "route_gate_success": False,
                    "route_card_parse_error": route_parse_error,
                    "route_card_route": "EVIDENCE",
                    "route_gate_route": "EVIDENCE_PIPELINE",
                    "planner_success": False,
                    "planner_timeout": "timeout" in str(route_parse_error or "").lower(),
                    "planner_provider_latency_ms": _elapsed_ms(started),
                }
            )
            return WeakProtocolResult(
                plan_payload={
                    "route": "EVIDENCE_PIPELINE",
                    "evidence_order": "SQL_FIRST",
                    "direct_answer": None,
                    "passes": [],
                    "aggregation_instruction": "",
                    "reason": "Route Card LLM call failed twice; fail closed to evidence without backend SQL/API.",
                },
                diagnostics=diagnostics,
                raw_preview=raw_previews,
                parse_error=True,
                backend_unavailable=True,
                error_message=route_parse_error,
            )
    if route_card is None:
        route_card = RouteCard(route="EVIDENCE", direct_answer=None, reason="Malformed Route Card after one repair; fail closed to evidence.")
        diagnostics["route_card_success"] = False
        diagnostics["route_gate_success"] = False
        diagnostics["route_card_parse_error"] = route_parse_error
    else:
        diagnostics["route_card_success"] = True
        diagnostics["route_gate_success"] = True
    diagnostics["route_card_route"] = route_card.route
    diagnostics["route_gate_route"] = _planner_route_from_route_card(route_card.route)

    if route_card.route == "DIRECT":
        challenge, challenge_raw_preview = _run_direct_route_challenge(
            client=client,
            user_prompt=user_prompt,
            route_card=route_card,
            diagnostics=diagnostics,
        )
        raw_previews.update(challenge_raw_preview)
        if challenge.needs_evidence:
            route_card = RouteCard(
                route="EVIDENCE",
                direct_answer=None,
                reason=challenge.reason or "Direct Route Challenge required runtime evidence.",
            )
            diagnostics["route_card_effective_route"] = "EVIDENCE"
            diagnostics["route_gate_route"] = "EVIDENCE_PIPELINE"
        else:
            diagnostics["route_card_effective_route"] = "DIRECT"
    if route_card.route == "DIRECT":
        diagnostics.update(
            {
                "weak_protocol_task_ledger_used": False,
                "evidence_planner_called": False,
                "planner_success": diagnostics["route_card_success"],
                "planner_provider_latency_ms": _elapsed_ms(started),
            }
        )
        return WeakProtocolResult(
            plan_payload={
                "route": "LLM_DIRECT",
                "evidence_order": "NO_EVIDENCE",
                "direct_answer": route_card.direct_answer,
                "passes": [],
                "aggregation_instruction": "",
                "reason": route_card.reason,
            },
            diagnostics=diagnostics,
            raw_preview=raw_previews,
            parse_error=not bool(diagnostics["route_card_success"]),
        )

    ledger_raw, ledger_error, ledger_latency_ms = _call_text(
        client,
        system_prompt=_task_ledger_system_prompt(),
        user_prompt=_task_ledger_user_prompt(user_prompt, schema_context, endpoint_context),
        max_tokens=TASK_LEDGER_MAX_TOKENS,
    )
    diagnostics["weak_protocol_task_ledger_used"] = True
    diagnostics["task_ledger_latency_ms"] = ledger_latency_ms
    diagnostics["evidence_planner_called"] = True
    raw_previews["task_ledger"] = compact_preview(ledger_raw or ledger_error, 1400)
    legacy_payload = _legacy_full_plan_payload(ledger_raw)
    if legacy_payload is not None:
        diagnostics.update(
            {
                "task_ledger_success": True,
                "weak_protocol_legacy_monolithic_response_accepted": True,
                "planner_success": True,
                "planner_json_fallback_used": True,
                "planner_provider_latency_ms": _elapsed_ms(started),
            }
        )
        return WeakProtocolResult(plan_payload=legacy_payload, diagnostics=diagnostics, raw_preview=raw_previews)

    ledger: TaskLedger | None = None
    ledger_parse_error = ledger_error
    if not ledger_error:
        try:
            ledger = parse_task_ledger_card(ledger_raw)
            ledger_parse_error = ledger.shape_error
        except Exception as exc:
            ledger_parse_error = str(exc)
    if ledger is None or ledger.shape_error:
        diagnostics["task_ledger_repair_attempted"] = True
        diagnostics["planner_repair_attempted"] = True
        repair_raw, repair_error, repair_latency_ms = _call_text(
            client,
            system_prompt=_task_ledger_repair_system_prompt(),
            user_prompt=_task_ledger_repair_user_prompt(user_prompt, ledger_raw, ledger_parse_error),
            max_tokens=TASK_LEDGER_MAX_TOKENS,
        )
        diagnostics["task_ledger_repair_latency_ms"] = repair_latency_ms
        raw_previews["task_ledger_repair"] = compact_preview(repair_raw or repair_error, 1400)
        legacy_payload = _legacy_full_plan_payload(repair_raw)
        if legacy_payload is not None:
            diagnostics.update(
                {
                    "task_ledger_success": True,
                    "weak_protocol_legacy_monolithic_response_accepted": True,
                    "planner_success": True,
                    "planner_json_fallback_used": True,
                    "planner_provider_latency_ms": _elapsed_ms(started),
                }
            )
            return WeakProtocolResult(plan_payload=legacy_payload, diagnostics=diagnostics, raw_preview=raw_previews)
        if not repair_error:
            try:
                ledger = parse_task_ledger_card(repair_raw)
                ledger_parse_error = ledger.shape_error
            except Exception as exc:
                ledger_parse_error = str(exc)
        else:
            ledger_parse_error = repair_error
    if ledger is None or ledger.shape_error:
        diagnostics.update(
            {
                "task_ledger_success": False,
                "task_ledger_error": ledger_parse_error,
                "planner_success": False,
                "planner_provider_latency_ms": _elapsed_ms(started),
            }
        )
        return WeakProtocolResult(
            plan_payload={
                "route": "EVIDENCE_PIPELINE",
                "evidence_order": "SQL_FIRST",
                "direct_answer": None,
                "passes": [],
                "aggregation_instruction": "",
                "reason": f"Task Ledger failed shape gate: {ledger_parse_error}",
            },
            diagnostics=diagnostics,
            raw_preview=raw_previews,
            parse_error=True,
        )

    diagnostics["task_ledger_success"] = True
    diagnostics["task_count"] = len(ledger.tasks)
    diagnostics["task_paths"] = [task.path for task in ledger.tasks]
    diagnostics["dependency_edges"] = [[dep, task.task_id] for task in ledger.tasks for dep in task.depends_on]
    passes: list[dict[str, Any]] = []
    for task in ledger.tasks:
        passes.append(
            _pass_payload_for_task(
                client=client,
                task=task,
                user_prompt=user_prompt,
                schema_context=schema_context,
                endpoint_context=endpoint_context,
                diagnostics=diagnostics,
                raw_previews=raw_previews,
            )
        )
    diagnostics.update({"planner_success": True, "planner_provider_latency_ms": _elapsed_ms(started)})
    return WeakProtocolResult(
        plan_payload={
            "route": "EVIDENCE_PIPELINE",
            "evidence_order": "MULTI_PASS" if len(passes) > 1 else _evidence_order_for_passes(passes),
            "direct_answer": None,
            "passes": passes,
            "aggregation_instruction": ledger.aggregation_instruction,
            "reason": route_card.reason or "Route Card selected evidence; Task Ledger supplied executable tasks.",
        },
        diagnostics=diagnostics,
        raw_preview=raw_previews,
    )


def _run_direct_route_challenge(
    *,
    client: Any,
    user_prompt: str,
    route_card: RouteCard,
    diagnostics: dict[str, Any],
) -> tuple[DirectRouteChallenge, dict[str, Any]]:
    diagnostics["direct_route_challenge_used"] = True
    raw_previews: dict[str, Any] = {}
    challenge_raw, challenge_error, challenge_latency_ms = _call_text(
        client,
        system_prompt=_direct_route_challenge_system_prompt(),
        user_prompt=_direct_route_challenge_user_prompt(user_prompt, route_card),
        max_tokens=DIRECT_CHALLENGE_MAX_TOKENS,
    )
    diagnostics["direct_route_challenge_latency_ms"] = challenge_latency_ms
    raw_previews["direct_route_challenge"] = compact_preview(challenge_raw or challenge_error, 800)
    challenge: DirectRouteChallenge | None = None
    parse_error = challenge_error
    if not challenge_error:
        try:
            challenge = parse_direct_route_challenge(challenge_raw)
            parse_error = None
        except Exception as exc:
            parse_error = str(exc)
    if challenge is None:
        diagnostics["direct_route_challenge_repair_attempted"] = True
        repair_raw, repair_error, repair_latency_ms = _call_text(
            client,
            system_prompt=_direct_route_challenge_repair_system_prompt(),
            user_prompt=_direct_route_challenge_repair_user_prompt(user_prompt, route_card, challenge_raw, parse_error),
            max_tokens=DIRECT_CHALLENGE_MAX_TOKENS,
        )
        diagnostics["direct_route_challenge_repair_latency_ms"] = repair_latency_ms
        raw_previews["direct_route_challenge_repair"] = compact_preview(repair_raw or repair_error, 800)
        if not repair_error:
            try:
                challenge = parse_direct_route_challenge(repair_raw)
                parse_error = None
            except Exception as exc:
                parse_error = str(exc)
        else:
            parse_error = repair_error
    if challenge is None:
        challenge = DirectRouteChallenge(
            needs_evidence=True,
            reason=f"Malformed Direct Route Challenge after one repair: {parse_error or 'unknown'}",
        )
        diagnostics["direct_route_challenge_parse_error"] = parse_error
    diagnostics["direct_route_challenge_needs_evidence"] = challenge.needs_evidence
    diagnostics["direct_route_challenge_reason"] = challenge.reason
    return challenge, raw_previews


def parse_route_card(raw_content: str) -> RouteCard:
    parsed_json = _try_protocol_json_object(raw_content)
    if parsed_json is not None:
        return _route_card_from_json(parsed_json)
    fields = _parse_key_value_lines(raw_content)
    route = str(fields.get("ROUTE") or "").strip().upper()
    if route in {"LLM_DIRECT", "LLM_SAFE_DIRECT"}:
        route = "DIRECT"
    if route == "EVIDENCE_PIPELINE":
        route = "EVIDENCE"
    if route not in ALLOWED_ROUTE_CARD_VALUES:
        raise ProtocolParseError("ROUTE must be DIRECT or EVIDENCE.")
    answer = str(fields.get("DIRECT_ANSWER") or "").strip() or None
    if route == "EVIDENCE":
        answer = None
    return RouteCard(route=route, direct_answer=answer, reason=str(fields.get("REASON") or "").strip())


def parse_direct_route_challenge(raw_content: str) -> DirectRouteChallenge:
    parsed_json = _try_protocol_json_object(raw_content)
    if parsed_json is not None:
        value = parsed_json.get("needs_evidence")
        if value is None:
            value = parsed_json.get("NEEDS_EVIDENCE")
        if value is None:
            raise ProtocolParseError("NEEDS_EVIDENCE is required.")
        return DirectRouteChallenge(needs_evidence=_parse_yes_no(value), reason=str(parsed_json.get("reason") or parsed_json.get("REASON") or "").strip())
    fields = _parse_key_value_lines(raw_content)
    if "NEEDS_EVIDENCE" not in fields:
        raise ProtocolParseError("NEEDS_EVIDENCE is required.")
    return DirectRouteChallenge(
        needs_evidence=_parse_yes_no(fields.get("NEEDS_EVIDENCE")),
        reason=str(fields.get("REASON") or "").strip(),
    )


def parse_task_ledger_card(raw_content: str) -> TaskLedger:
    legacy = _legacy_full_plan_payload(raw_content)
    if legacy is not None:
        return TaskLedger(legacy_plan_payload=legacy)
    parsed_json = _try_protocol_json_object(raw_content)
    if parsed_json is not None and isinstance(parsed_json.get("tasks"), list):
        tasks: list[TaskLedgerTask] = []
        for item in parsed_json.get("tasks") or []:
            if not isinstance(item, dict):
                continue
            task_id = _normalize_task_id(item.get("task_id") or item.get("id") or item.get("pass_id"))
            path = str(item.get("path") or "").strip().upper()
            description = str(item.get("description") or item.get("subtask") or item.get("task") or "").strip()
            if path not in ALLOWED_TASK_PATHS:
                raise ProtocolParseError(f"Invalid task path: {path}")
            depends_on = item.get("depends_on") if isinstance(item.get("depends_on"), list) else []
            tasks.append(TaskLedgerTask(task_id=task_id, path=path, depends_on=[str(dep) for dep in depends_on if dep], description=description))
        ledger = TaskLedger(tasks=tasks, aggregation_instruction=str(parsed_json.get("aggregation_instruction") or parsed_json.get("aggregate") or "").strip())
        error = _task_ledger_shape_error(tasks)
        if error:
            ledger.shape_error, ledger.shape_error_message = error
        return ledger
    tasks: list[TaskLedgerTask] = []
    aggregation = ""
    for raw_line in str(raw_content or "").splitlines():
        line = _strip_protocol_prefix(raw_line)
        if not line:
            continue
        upper = line.upper()
        if upper.startswith("TASK ") or upper.startswith("TASK:"):
            tasks.append(_parse_task_line(line))
        elif upper.startswith("AGGREGATE=") or upper.startswith("AGGREGATE:"):
            aggregation = re.split(r"[:=]", line, maxsplit=1)[1].strip()
    ledger = TaskLedger(tasks=tasks, aggregation_instruction=aggregation)
    error = _task_ledger_shape_error(tasks)
    if error:
        ledger.shape_error, ledger.shape_error_message = error
    return ledger


def parse_pass_candidate_card(raw_content: str) -> PassCandidateCard:
    parsed_json = _try_protocol_json_object(raw_content)
    if parsed_json is not None:
        return _pass_candidate_from_json(parsed_json)
    fields = _parse_key_value_lines(raw_content)
    path = str(fields.get("PATH") or "").strip().upper()
    if path not in {"SQL", "API"}:
        raise ProtocolParseError("PATH must be SQL or API.")
    if path == "SQL":
        sql = str(fields.get("SQL") or "").strip()
        if not sql:
            raise ProtocolParseError("SQL candidate is missing SQL=.")
        return PassCandidateCard(path="SQL", sql=sql, params=_parse_json_value(fields.get("PARAMS"), default=[]))
    method = str(fields.get("METHOD") or "GET").strip().upper()
    api_path = str(fields.get("API_PATH") or fields.get("PATH_URL") or "").strip()
    if not api_path:
        raise ProtocolParseError("API candidate is missing API_PATH=.")
    return PassCandidateCard(path="API", method=method, api_path=api_path, params=_parse_json_value(fields.get("PARAMS"), default={}))


def _pass_payload_for_task(
    *,
    client: Any,
    task: TaskLedgerTask,
    user_prompt: str,
    schema_context: dict[str, Any],
    endpoint_context: list[dict[str, Any]],
    diagnostics: dict[str, Any],
    raw_previews: dict[str, Any],
) -> dict[str, Any]:
    if task.path in {"DIRECT", "AGGREGATE"}:
        return {
            "pass_id": task.task_id,
            "subtask": task.description,
            "path": "DIRECT" if task.path == "DIRECT" else "AGGREGATION_ONLY",
            "can_run_parallel": not bool(task.depends_on),
            "depends_on": task.depends_on,
            "evidence_order": "NO_EVIDENCE",
            "sql": None,
            "api_request": None,
            "expected_result": task.description,
        }
    sql_payload: dict[str, Any] | None = None
    api_payload: dict[str, Any] | None = None
    if task.path in {"SQL", "SQL_AND_API"}:
        card = _candidate_card_for_task(
            client=client,
            task=task,
            user_prompt=user_prompt,
            requested_path="SQL",
            schema_context=schema_context,
            endpoint_context=endpoint_context,
            diagnostics=diagnostics,
            raw_previews=raw_previews,
        )
        if card and card.sql:
            sql_payload = {"query": card.sql, "params": card.params if isinstance(card.params, list) else []}
    if task.path in {"API", "SQL_AND_API"}:
        card = _candidate_card_for_task(
            client=client,
            task=task,
            user_prompt=user_prompt,
            requested_path="API",
            schema_context=schema_context,
            endpoint_context=endpoint_context,
            diagnostics=diagnostics,
            raw_previews=raw_previews,
        )
        if card and card.api_path:
            api_payload = {"method": card.method or "GET", "path": card.api_path, "params": card.params if isinstance(card.params, dict) else {}}
    return {
        "pass_id": task.task_id,
        "subtask": task.description,
        "path": task.path,
        "can_run_parallel": not bool(task.depends_on),
        "depends_on": task.depends_on,
        "evidence_order": _evidence_order_for_task(task.path),
        "sql": sql_payload,
        "api_request": api_payload,
        "expected_result": task.description,
    }


def _candidate_card_for_task(
    *,
    client: Any,
    task: TaskLedgerTask,
    user_prompt: str,
    requested_path: str,
    schema_context: dict[str, Any],
    endpoint_context: list[dict[str, Any]],
    diagnostics: dict[str, Any],
    raw_previews: dict[str, Any],
    repair_context: dict[str, Any] | None = None,
) -> PassCandidateCard | None:
    diagnostics["pass_candidate_cards"] = int(diagnostics.get("pass_candidate_cards", 0) or 0) + 1
    if requested_path == "SQL":
        diagnostics["sql_candidate_cards"] = int(diagnostics.get("sql_candidate_cards", 0) or 0) + 1
        system = _sql_candidate_system_prompt()
        user = _sql_candidate_user_prompt(user_prompt, task, schema_context)
    else:
        diagnostics["api_candidate_cards"] = int(diagnostics.get("api_candidate_cards", 0) or 0) + 1
        system = _api_candidate_system_prompt()
        user = _api_candidate_user_prompt(user_prompt, task, endpoint_context)
    raw, error, latency_ms = _call_text(client, system_prompt=system, user_prompt=user, max_tokens=CANDIDATE_CARD_MAX_TOKENS)
    diagnostics["candidate_card_latency_ms"] = int(diagnostics.get("candidate_card_latency_ms", 0) or 0) + latency_ms
    raw_previews[f"candidate_{task.task_id}_{requested_path.lower()}"] = compact_preview(raw or error, 1000)
    parse_error = error
    if not error:
        legacy_candidate = _candidate_from_legacy_plan(_legacy_full_plan_payload(raw), task.task_id, requested_path)
        if legacy_candidate is not None:
            diagnostics["candidate_card_success"] = int(diagnostics.get("candidate_card_success", 0) or 0) + 1
            diagnostics["weak_protocol_legacy_candidate_extracted"] = int(diagnostics.get("weak_protocol_legacy_candidate_extracted", 0) or 0) + 1
            return legacy_candidate
        try:
            candidate = parse_pass_candidate_card(raw)
            diagnostics["candidate_card_success"] = int(diagnostics.get("candidate_card_success", 0) or 0) + 1
            return candidate
        except Exception as exc:
            parse_error = str(exc)
    diagnostics["candidate_repair_attempts"] = int(diagnostics.get("candidate_repair_attempts", 0) or 0) + 1
    repair_raw, repair_error, repair_latency_ms = _call_text(
        client,
        system_prompt=_candidate_repair_system_prompt(requested_path),
        user_prompt=_candidate_repair_user_prompt(user_prompt, task, requested_path, raw, parse_error, schema_context, endpoint_context, repair_context),
        max_tokens=CANDIDATE_REPAIR_MAX_TOKENS,
    )
    diagnostics["candidate_card_latency_ms"] = int(diagnostics.get("candidate_card_latency_ms", 0) or 0) + repair_latency_ms
    raw_previews[f"candidate_repair_{task.task_id}_{requested_path.lower()}"] = compact_preview(repair_raw or repair_error, 1000)
    if repair_error:
        return PassCandidateCard(path=requested_path, parse_error=repair_error)
    legacy_candidate = _candidate_from_legacy_plan(_legacy_full_plan_payload(repair_raw), task.task_id, requested_path)
    if legacy_candidate is not None:
        diagnostics["candidate_card_success"] = int(diagnostics.get("candidate_card_success", 0) or 0) + 1
        diagnostics["weak_protocol_legacy_candidate_extracted"] = int(diagnostics.get("weak_protocol_legacy_candidate_extracted", 0) or 0) + 1
        return legacy_candidate
    try:
        candidate = parse_pass_candidate_card(repair_raw)
        diagnostics["candidate_card_success"] = int(diagnostics.get("candidate_card_success", 0) or 0) + 1
        return candidate
    except Exception as exc:
        return PassCandidateCard(path=requested_path, parse_error=str(exc))


def _run_repair_context_protocol(
    *,
    client: Any,
    user_prompt: str,
    schema_context: dict[str, Any],
    endpoint_context: list[dict[str, Any]],
    repair_context: dict[str, Any],
    diagnostics: dict[str, Any],
    started: float,
) -> WeakProtocolResult:
    previous = repair_context.get("previous_plan") if isinstance(repair_context.get("previous_plan"), dict) else {}
    failed_component = str(repair_context.get("failed_component") or "")
    pass_id = str(repair_context.get("pass_id") or "")
    repair_raw, repair_error, repair_latency_ms = _call_text(
        client,
        system_prompt=_generic_repair_system_prompt(),
        user_prompt=_generic_repair_user_prompt(user_prompt, repair_context),
        max_tokens=CANDIDATE_REPAIR_MAX_TOKENS,
    )
    diagnostics["planner_repair_attempted"] = True
    diagnostics["weak_protocol_generic_repair_attempted"] = True
    diagnostics["weak_protocol_generic_repair_latency_ms"] = repair_latency_ms
    raw_repair_preview = {"generic_repair": compact_preview(repair_raw or repair_error, 1400)}
    repaired_payload = _legacy_full_plan_payload(repair_raw)
    if repaired_payload is not None:
        if previous and pass_id and failed_component in {"sql", "api_request", "dependency_resolution"}:
            repaired_payload = _merge_repaired_pass_payload(previous, repaired_payload, pass_id)
        diagnostics.update(
            {
                "planner_success": True,
                "planner_provider_latency_ms": _elapsed_ms(started),
                "weak_protocol_generic_repair_accepted": True,
                "planner_json_fallback_used": True,
            }
        )
        return WeakProtocolResult(plan_payload=repaired_payload, diagnostics=diagnostics, raw_preview=raw_repair_preview)
    if failed_component not in {"sql", "api_request"} or not previous:
        diagnostics.update({"weak_protocol_repair_fallback": True, "planner_success": False, "planner_provider_latency_ms": _elapsed_ms(started)})
        return WeakProtocolResult(
            plan_payload={
                "route": "EVIDENCE_PIPELINE",
                "evidence_order": "SQL_FIRST",
                "direct_answer": None,
                "passes": [],
                "aggregation_instruction": "",
                "reason": "Unsupported repair context for weak protocol.",
            },
            diagnostics=diagnostics,
            parse_error=True,
            raw_preview={"repair_context": compact_preview(repair_context, 1000), **raw_repair_preview},
        )
    passes = [dict(item) for item in previous.get("passes", []) if isinstance(item, dict)]
    target = next((item for item in passes if str(item.get("pass_id")) == pass_id), None)
    if target is None:
        diagnostics.update({"weak_protocol_repair_target_missing": True, "planner_success": False, "planner_provider_latency_ms": _elapsed_ms(started)})
        return WeakProtocolResult(plan_payload={**previous, "passes": passes}, diagnostics=diagnostics, parse_error=True)
    task = TaskLedgerTask(
        task_id=pass_id,
        path="SQL" if failed_component == "sql" else "API",
        depends_on=[str(item) for item in target.get("depends_on", [])] if isinstance(target.get("depends_on"), list) else [],
        description=str(repair_context.get("subtask") or target.get("subtask") or "Repair candidate"),
    )
    raw_previews: dict[str, Any] = {}
    card = _candidate_card_for_task(
        client=client,
        task=task,
        user_prompt=user_prompt,
        requested_path="SQL" if failed_component == "sql" else "API",
        schema_context=schema_context,
        endpoint_context=endpoint_context,
        diagnostics=diagnostics,
        raw_previews=raw_previews,
        repair_context=repair_context,
    )
    if card and card.sql:
        target["sql"] = {"query": card.sql, "params": card.params if isinstance(card.params, list) else []}
        target["api_request"] = None if target.get("path") == "SQL" else target.get("api_request")
    elif card and card.api_path:
        target["api_request"] = {"method": card.method or "GET", "path": card.api_path, "params": card.params if isinstance(card.params, dict) else {}}
        target["sql"] = None if target.get("path") == "API" else target.get("sql")
    else:
        diagnostics["planner_success"] = False
        diagnostics["planner_provider_latency_ms"] = _elapsed_ms(started)
        return WeakProtocolResult(plan_payload={**previous, "passes": passes}, diagnostics=diagnostics, raw_preview=raw_previews, parse_error=True)
    diagnostics.update(
        {
            "weak_protocol_candidate_repair_card_used": True,
            "planner_success": True,
            "planner_provider_latency_ms": _elapsed_ms(started),
        }
    )
    return WeakProtocolResult(plan_payload={**previous, "passes": passes}, diagnostics=diagnostics, raw_preview=raw_previews)


def _parse_task_line(line: str) -> TaskLedgerTask:
    line = _strip_protocol_prefix(line)
    body = re.sub(r"^TASK\s*:?", "", line, flags=re.I).strip()
    parts = [part.strip() for part in body.split("|", 3)]
    if len(parts) != 4:
        raise ProtocolParseError("TASK line must have four pipe-separated fields.")
    task_id, path, deps, description = parts
    task_id = _normalize_task_id(task_id)
    path = path.upper()
    if path not in ALLOWED_TASK_PATHS:
        raise ProtocolParseError(f"Invalid task path: {path}")
    return TaskLedgerTask(task_id=task_id, path=path, depends_on=_parse_dep_list(deps), description=description)


def _task_ledger_shape_error(tasks: list[TaskLedgerTask]) -> tuple[str, str] | None:
    if not tasks:
        return "empty_task_ledger", "Task Ledger must include at least one task."
    ids = [task.task_id for task in tasks]
    if any(not task_id for task_id in ids):
        return "missing_task_id", "Task IDs are required."
    if len(set(ids)) != len(ids):
        return "duplicate_task_id", "Task IDs must be unique."
    known = set(ids)
    for task in tasks:
        for dep in task.depends_on:
            if dep not in known:
                return "unknown_dependency", f"Task {task.task_id} depends on unknown task {dep}."
        if task.path == "AGGREGATE" and not task.depends_on:
            return "aggregation_without_dependencies", f"Task {task.task_id} is AGGREGATE but has no dependencies."
    if len(tasks) == 1 and tasks[0].path == "AGGREGATE":
        return "aggregate_only", "AGGREGATE cannot be the only task."
    if not any(task.path in {"SQL", "API", "SQL_AND_API"} for task in tasks):
        return "missing_executable_evidence_task", "EVIDENCE route requires at least one SQL/API task."
    if _task_has_cycle(tasks):
        return "dependency_cycle", "Task Ledger dependencies contain a cycle."
    return None


def _task_has_cycle(tasks: list[TaskLedgerTask]) -> bool:
    deps = {task.task_id: set(task.depends_on) for task in tasks}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(task_id: str) -> bool:
        if task_id in visiting:
            return True
        if task_id in visited:
            return False
        visiting.add(task_id)
        for dep in deps.get(task_id, set()):
            if dep in deps and visit(dep):
                return True
        visiting.remove(task_id)
        visited.add(task_id)
        return False

    return any(visit(task.task_id) for task in tasks)


def _parse_key_value_lines(raw_content: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for raw_line in str(raw_content or "").splitlines():
        line = _strip_protocol_prefix(raw_line)
        if not line:
            continue
        equal_at = line.find("=")
        colon_at = line.find(":")
        split_at = -1
        if equal_at >= 0 and colon_at >= 0:
            split_at = min(equal_at, colon_at)
        elif equal_at >= 0:
            split_at = equal_at
        elif colon_at >= 0:
            split_at = colon_at
        if split_at < 0:
            continue
        key, value = line[:split_at], line[split_at + 1 :]
        fields[key.strip().upper()] = value.strip()
    return fields


def _strip_protocol_prefix(raw_line: Any) -> str:
    line = str(raw_line or "").strip()
    line = re.sub(r"^\s*[-*]\s+", "", line)
    line = re.sub(r"^\s*\d+[\.)]\s+", "", line)
    return line.strip()


def _normalize_task_id(value: Any) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "").strip())[:80]


def _parse_yes_no(value: Any) -> bool:
    text = str(value or "").strip().upper()
    if text in {"YES", "Y", "TRUE", "1"}:
        return True
    if text in {"NO", "N", "FALSE", "0"}:
        return False
    raise ProtocolParseError("NEEDS_EVIDENCE must be YES or NO.")


def _pass_candidate_from_json(payload: dict[str, Any]) -> PassCandidateCard:
    path = str(payload.get("path") or payload.get("PATH") or "").strip().upper()
    if path not in {"SQL", "API"}:
        raise ProtocolParseError("JSON candidate path must be SQL or API.")
    if path == "SQL":
        sql_value = payload.get("sql")
        params = payload.get("params")
        if isinstance(sql_value, dict):
            params = sql_value.get("params", params)
            sql_value = sql_value.get("query")
        sql = str(sql_value or "").strip()
        if not sql:
            raise ProtocolParseError("SQL candidate is missing sql.")
        return PassCandidateCard(path="SQL", sql=sql, params=params if isinstance(params, list) else [])
    api_value = payload.get("api_request") if isinstance(payload.get("api_request"), dict) else payload
    method = str(api_value.get("method") or payload.get("method") or "GET").strip().upper()
    api_path = str(api_value.get("path") or api_value.get("api_path") or payload.get("api_path") or payload.get("API_PATH") or "").strip()
    if not api_path:
        raise ProtocolParseError("API candidate is missing path.")
    params = api_value.get("params") if isinstance(api_value.get("params"), dict) else payload.get("params")
    return PassCandidateCard(path="API", method=method, api_path=api_path, params=params if isinstance(params, dict) else {})


def _parse_dep_list(value: str) -> list[str]:
    text = value.strip()
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1]
    return [item.strip() for item in text.split(",") if item.strip()]


def _parse_json_value(value: Any, *, default: Any) -> Any:
    if value is None or str(value).strip() == "":
        return default
    try:
        return json.loads(str(value))
    except Exception:
        return default


def _try_json_object(raw_content: str) -> dict[str, Any] | None:
    text = str(raw_content or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I).strip()
        text = re.sub(r"\s*```$", "", text).strip()
    if not text.startswith("{"):
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return None
        text = text[start : end + 1].strip()
    text = re.sub(r",(\s*[}\]])", r"\1", text)
    try:
        payload = json.loads(text)
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _try_protocol_json_object(raw_content: str) -> dict[str, Any] | None:
    text = str(raw_content or "").strip()
    if not text:
        return None
    if text.startswith("```"):
        return _try_json_object(text)
    if text.startswith("{"):
        return _try_json_object(text)
    return None


def _route_card_from_json(payload: dict[str, Any]) -> RouteCard:
    route = str(payload.get("route") or "").strip().upper()
    if route in {"LLM_DIRECT", "DIRECT"}:
        return RouteCard("DIRECT", str(payload.get("direct_answer") or "").strip() or None, str(payload.get("reason") or "").strip())
    if route in {"EVIDENCE_PIPELINE", "EVIDENCE"}:
        return RouteCard("EVIDENCE", None, str(payload.get("reason") or "").strip())
    raise ProtocolParseError("JSON Route Card route must be DIRECT or EVIDENCE.")


def _route_card_from_legacy_payload(payload: dict[str, Any]) -> RouteCard:
    return _route_card_from_json(payload)


def _planner_route_from_route_card(route: str) -> str:
    return "LLM_DIRECT" if str(route).upper() == "DIRECT" else "EVIDENCE_PIPELINE"


def _legacy_full_plan_payload(raw_content: str | None) -> dict[str, Any] | None:
    payload = _try_json_object(raw_content or "")
    if not isinstance(payload, dict):
        return None
    if not any(key in payload for key in ("passes", "sql", "api_request")):
        return None
    return payload


def _candidate_from_legacy_plan(payload: dict[str, Any] | None, task_id: str, requested_path: str) -> PassCandidateCard | None:
    if not isinstance(payload, dict):
        return None
    requested_path = requested_path.upper()
    pass_payload: dict[str, Any] | None = None
    passes = payload.get("passes")
    if isinstance(passes, list):
        for item in passes:
            if not isinstance(item, dict):
                continue
            if str(item.get("pass_id") or "") == task_id:
                pass_payload = item
                break
        if pass_payload is None and len(passes) == 1 and isinstance(passes[0], dict):
            pass_payload = passes[0]
    if pass_payload is None:
        pass_payload = payload
    if requested_path == "SQL":
        sql = pass_payload.get("sql")
        if isinstance(sql, dict) and str(sql.get("query") or "").strip():
            return PassCandidateCard(path="SQL", sql=str(sql.get("query")).strip(), params=sql.get("params") if isinstance(sql.get("params"), list) else [])
        sql = payload.get("sql")
        if isinstance(sql, dict) and str(sql.get("query") or "").strip():
            return PassCandidateCard(path="SQL", sql=str(sql.get("query")).strip(), params=sql.get("params") if isinstance(sql.get("params"), list) else [])
        return None
    api = pass_payload.get("api_request")
    if isinstance(api, dict) and str(api.get("path") or "").strip():
        return PassCandidateCard(
            path="API",
            method=str(api.get("method") or "GET").upper(),
            api_path=str(api.get("path")).strip(),
            params=api.get("params") if isinstance(api.get("params"), dict) else {},
        )
    api = payload.get("api_request")
    if isinstance(api, dict) and str(api.get("path") or "").strip():
        return PassCandidateCard(
            path="API",
            method=str(api.get("method") or "GET").upper(),
            api_path=str(api.get("path")).strip(),
            params=api.get("params") if isinstance(api.get("params"), dict) else {},
        )
    return None


def _evidence_order_for_task(path: str) -> str:
    if path == "API":
        return "API_FIRST"
    if path == "SQL_AND_API":
        return "PARALLEL"
    if path in {"DIRECT", "AGGREGATE"}:
        return "NO_EVIDENCE"
    return "SQL_FIRST"


def _evidence_order_for_passes(passes: list[dict[str, Any]]) -> str:
    if not passes:
        return "SQL_FIRST"
    orders = {str(item.get("evidence_order") or "") for item in passes}
    if "PARALLEL" in orders:
        return "PARALLEL"
    if "API_FIRST" in orders and "SQL_FIRST" not in orders:
        return "API_FIRST"
    return "SQL_FIRST"


def _call_text(client: Any, *, system_prompt: str, user_prompt: str, max_tokens: int | None = None) -> tuple[str, str | None, int]:
    started = time.perf_counter()
    kwargs: dict[str, Any] = {
        "tools": None,
        "tool_choice": None,
        "parallel_tool_calls": None,
    }
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
        kwargs["temperature"] = 0
    try:
        result = client.generate_messages(
            [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            **kwargs,
        )
    except TypeError as exc:
        if "max_tokens" not in str(exc) and "temperature" not in str(exc):
            return "", str(redact_secrets(str(exc)))[:500], _elapsed_ms(started)
        kwargs.pop("max_tokens", None)
        kwargs.pop("temperature", None)
        try:
            result = client.generate_messages(
                [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                **kwargs,
            )
        except Exception as retry_exc:
            return "", str(redact_secrets(str(retry_exc)))[:500], _elapsed_ms(started)
    except Exception as exc:
        return "", str(redact_secrets(str(exc)))[:500], _elapsed_ms(started)
    if not isinstance(result, dict):
        return "", "LLM client returned a non-object result.", _elapsed_ms(started)
    if not result.get("ok", True) and not result.get("content"):
        return "", str(redact_secrets(result.get("error") or result.get("reason") or "LLM call failed"))[:500], _elapsed_ms(started)
    content = str(result.get("content") or "")
    if not content:
        tool_calls = result.get("tool_calls")
        if isinstance(tool_calls, list) and tool_calls:
            first = tool_calls[0]
            if isinstance(first, dict):
                arguments = first.get("arguments")
                if isinstance(arguments, dict):
                    content = json.dumps(arguments)
                elif isinstance(first.get("raw_arguments"), str):
                    content = str(first.get("raw_arguments") or "")
    return content, None, _elapsed_ms(started)


def _elapsed_ms(started: float) -> int:
    return int(round((time.perf_counter() - started) * 1000))


def _route_card_system_prompt() -> str:
    return (
        "You are the V2 Route Card writer. Output exactly three lines. "
        "Allowed ROUTE values are DIRECT and EVIDENCE. "
        "DIRECT is only for pure concept/meta/general questions with no runtime data. "
        "EVIDENCE is for user data, list, count, status, date, local snapshot, live/API/SQL, mixed, or ambiguous data-like prompts. "
        "Safety rule: if the prompt asks about records the user has, counts, lists, status, dates, published/created/updated times, local snapshots, current/live/platform state, or asks to show/give actual items, use EVIDENCE. "
        "Do not treat a data question that starts with 'what' as conceptual. "
        "Do not output JSON. Do not output SQL or API."
    )


def _route_card_user_prompt(user_prompt: str) -> str:
    return "\n".join(
        [
            f"USER_PROMPT={user_prompt}",
            "DIRECT means pure concept/meta/general only, no runtime data needed.",
            "EVIDENCE means any user-specific data/list/count/status/date/local/live/API/SQL/mixed/ambiguous-data-like prompt.",
            "Use EVIDENCE for: 'What schemas do I have?', 'How many schema records are in the local snapshot?', 'When was Birthday Message published?', 'Show inactive journeys', and compare local/live prompts.",
            "Use DIRECT for: 'What is a schema?' and 'In the phrase list schemas, what does list mean?'.",
            "Return exactly:",
            "ROUTE=DIRECT",
            "DIRECT_ANSWER=<short answer or empty>",
            "REASON=<short reason>",
            "or:",
            "ROUTE=EVIDENCE",
            "DIRECT_ANSWER=",
            "REASON=<short reason>",
        ]
    )


def _route_card_repair_system_prompt() -> str:
    return "Repair the Route Card. Output exactly ROUTE=, DIRECT_ANSWER=, and REASON= lines. If uncertain use ROUTE=EVIDENCE."


def _route_card_repair_user_prompt(user_prompt: str, raw_content: str, parse_error: str | None) -> str:
    return "\n".join(
        [
            f"USER_PROMPT={user_prompt}",
            f"PREVIOUS_RESPONSE={compact_preview(raw_content, 600)}",
            f"PARSE_ERROR={parse_error or 'unknown'}",
            "Allowed ROUTE values: DIRECT, EVIDENCE.",
        ]
    )


def _direct_route_challenge_system_prompt() -> str:
    return (
        "You are the Direct Route Challenge checker. Output exactly NEEDS_EVIDENCE=YES or NEEDS_EVIDENCE=NO and REASON=. "
        "YES means the prompt needs runtime SQL/API/local/live/user-specific evidence. NO means pure concept/meta/general with no runtime evidence."
    )


def _direct_route_challenge_user_prompt(user_prompt: str, route_card: RouteCard) -> str:
    return "\n".join(
        [
            f"USER_PROMPT={user_prompt}",
            f"PROPOSED_DIRECT_ANSWER={route_card.direct_answer or ''}",
            f"ROUTE_REASON={route_card.reason}",
            "Use NEEDS_EVIDENCE=YES for records the user has, counts, lists, status, dates, local snapshots, live/current/platform/API, mixed prompts, or ambiguous data-like prompts.",
            "Use NEEDS_EVIDENCE=NO only for pure concept/meta/general prompts.",
            "Return exactly:",
            "NEEDS_EVIDENCE=NO",
            "REASON=<short reason>",
        ]
    )


def _direct_route_challenge_repair_system_prompt() -> str:
    return "Repair the Direct Route Challenge. Output only NEEDS_EVIDENCE=YES|NO and REASON=. If uncertain use NEEDS_EVIDENCE=YES."


def _direct_route_challenge_repair_user_prompt(
    user_prompt: str,
    route_card: RouteCard,
    raw_content: str,
    parse_error: str | None,
) -> str:
    return "\n".join(
        [
            f"USER_PROMPT={user_prompt}",
            f"PROPOSED_DIRECT_ANSWER={route_card.direct_answer or ''}",
            f"PREVIOUS_RESPONSE={compact_preview(raw_content, 500)}",
            f"PARSE_ERROR={parse_error or 'unknown'}",
            "Allowed values: NEEDS_EVIDENCE=YES or NEEDS_EVIDENCE=NO.",
        ]
    )


def _task_ledger_system_prompt() -> str:
    return (
        "You are the V2 Task Ledger writer. Output only TASK lines and one AGGREGATE line. "
        "Do not output SQL or API requests. Backend will not add or remove semantic tasks."
    )


def _task_ledger_user_prompt(user_prompt: str, schema_context: dict[str, Any], endpoint_context: list[dict[str, Any]]) -> str:
    return "\n".join(
        [
            f"USER_PROMPT={user_prompt}",
            "Allowed paths: DIRECT, SQL, API, SQL_AND_API, AGGREGATE.",
            "DIRECT = concept explanation only. SQL = local snapshot evidence. API = live/API/platform evidence. AGGREGATE = combine earlier task results.",
            "For mixed prompts include DIRECT plus SQL/API evidence tasks.",
            "For local snapshot/list/count/date/status data use SQL. For live/current/platform/API data use API if needed.",
            "Do not output SQL/API in this stage.",
            "Compact DB schema context:",
            _compact_schema_lines(schema_context),
            "Compact safe GET endpoint context:",
            _compact_endpoint_lines(endpoint_context),
            "Output format:",
            "TASK t1 | SQL | [] | short task description",
            "TASK t2 | AGGREGATE | [t1] | combine results",
            "AGGREGATE=How to combine task results.",
        ]
    )


def _task_ledger_repair_system_prompt() -> str:
    return "Repair the Task Ledger line protocol. Output only TASK lines and one AGGREGATE line. Do not output SQL/API."


def _task_ledger_repair_user_prompt(user_prompt: str, raw_content: str, parse_error: str | None) -> str:
    return "\n".join([f"USER_PROMPT={user_prompt}", f"PREVIOUS_RESPONSE={compact_preview(raw_content, 900)}", f"SHAPE_ERROR={parse_error or 'unknown'}"])


def _sql_candidate_system_prompt() -> str:
    return "You are the SQL candidate card writer. Output one SQL card only. Use only tables/columns in schema context."


def _sql_candidate_user_prompt(user_prompt: str, task: TaskLedgerTask, schema_context: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"USER_PROMPT={user_prompt}",
            f"TASK_ID={task.task_id}",
            f"TASK_DESCRIPTION={task.description}",
            "Schema context:",
            _compact_schema_lines(schema_context, max_tables=12),
            "Output exactly:",
            "PATH=SQL",
            "SQL=SELECT ...",
            "PARAMS=[]",
        ]
    )


def _api_candidate_system_prompt() -> str:
    return "You are the API candidate card writer. Output one safe GET API card only. Use only endpoint context."


def _api_candidate_user_prompt(user_prompt: str, task: TaskLedgerTask, endpoint_context: list[dict[str, Any]]) -> str:
    return "\n".join(
        [
            f"USER_PROMPT={user_prompt}",
            f"TASK_ID={task.task_id}",
            f"TASK_DESCRIPTION={task.description}",
            "Safe GET endpoint context:",
            _compact_endpoint_lines(endpoint_context, max_endpoints=10),
            "Output exactly:",
            "PATH=API",
            "METHOD=GET",
            "API_PATH=/...",
            "PARAMS={}",
        ]
    )


def _candidate_repair_system_prompt(requested_path: str) -> str:
    return f"Repair the {requested_path} candidate card. Output only PATH={requested_path} card lines."


def _candidate_repair_user_prompt(
    user_prompt: str,
    task: TaskLedgerTask,
    requested_path: str,
    raw_content: str,
    parse_error: str | None,
    schema_context: dict[str, Any],
    endpoint_context: list[dict[str, Any]],
    repair_context: dict[str, Any] | None,
) -> str:
    gate_error = _candidate_gate_error(repair_context, requested_path)
    lines = [
        f"USER_PROMPT={user_prompt}",
        f"TASK_ID={task.task_id}",
        f"TASK_DESCRIPTION={task.description}",
        f"REQUESTED_PATH={requested_path}",
        f"PREVIOUS_RESPONSE={compact_preview(raw_content, 900)}",
        f"PARSE_OR_GATE_ERROR={parse_error or gate_error or 'unknown'}",
    ]
    if requested_path == "SQL":
        lines.extend(
            [
                "Previous SQL:",
                _previous_sql_from_repair_context(repair_context),
                "SQLCompileGate sanitized error:",
                gate_error or "unknown",
                "Schema context:",
                _compact_schema_lines(schema_context, max_tables=12),
                "Use only tables and columns in Schema context. Do not invent missing columns.",
            ]
        )
    else:
        lines.extend(
            [
                "Previous API request:",
                _previous_api_from_repair_context(repair_context),
                "APIRequestGate sanitized error:",
                gate_error or "unknown",
                "Safe GET endpoint context:",
                _compact_endpoint_lines(endpoint_context, max_endpoints=10),
                "Use only endpoints in Safe GET endpoint context. Do not invent paths.",
            ]
        )
    return "\n".join(lines)


def _candidate_gate_error(repair_context: dict[str, Any] | None, requested_path: str) -> str:
    if not isinstance(repair_context, dict):
        return ""
    keys = ["sql_compile_gate", "compile_gate", "sql_gate"] if requested_path == "SQL" else ["api_request_gate", "api_gate"]
    for key in keys:
        value = repair_context.get(key)
        if isinstance(value, dict):
            return str(redact_secrets(value.get("error_message") or value.get("message") or value.get("error") or ""))[:500]
    return str(redact_secrets(repair_context.get("error_message") or repair_context.get("gate_error") or ""))[:500]


def _previous_sql_from_repair_context(repair_context: dict[str, Any] | None) -> str:
    if not isinstance(repair_context, dict):
        return ""
    previous_plan = repair_context.get("previous_plan")
    pass_id = str(repair_context.get("pass_id") or "")
    target = _target_previous_pass(previous_plan, pass_id)
    sql = target.get("sql") if isinstance(target, dict) else None
    if isinstance(sql, dict):
        return str(sql.get("query") or "")
    return ""


def _previous_api_from_repair_context(repair_context: dict[str, Any] | None) -> str:
    if not isinstance(repair_context, dict):
        return ""
    previous_plan = repair_context.get("previous_plan")
    pass_id = str(repair_context.get("pass_id") or "")
    target = _target_previous_pass(previous_plan, pass_id)
    api = target.get("api_request") if isinstance(target, dict) else None
    return json.dumps(redact_secrets(api or {}), sort_keys=True) if isinstance(api, dict) else ""


def _target_previous_pass(previous_plan: Any, pass_id: str) -> dict[str, Any]:
    if not isinstance(previous_plan, dict):
        return {}
    passes = previous_plan.get("passes")
    if isinstance(passes, list):
        for item in passes:
            if isinstance(item, dict) and str(item.get("pass_id") or "") == pass_id:
                return item
        if len(passes) == 1 and isinstance(passes[0], dict):
            return passes[0]
    return {}


def _generic_repair_system_prompt() -> str:
    return (
        "Repair the V2 LLM-owned plan using only the provided failure context. "
        "Return either the weak line protocol card requested by the context or a complete V2 plan JSON object. "
        "Do not add backend-selected semantic tasks."
    )


def _generic_repair_user_prompt(user_prompt: str, repair_context: dict[str, Any]) -> str:
    return json.dumps(
        {
            "task": "V2_LLM_OWNED_PLAN_REPAIR",
            "user_prompt": user_prompt,
            "repair_context": repair_context,
            "constraints": [
                "LLM owns pass repair.",
                "Backend will not add semantic tasks.",
                "Return a repaired plan or repaired candidate only.",
            ],
        },
        sort_keys=True,
    )


def _merge_repaired_pass_payload(previous: dict[str, Any], repaired: dict[str, Any], pass_id: str) -> dict[str, Any]:
    previous_passes = [dict(item) for item in previous.get("passes", []) if isinstance(item, dict)]
    repaired_passes = [dict(item) for item in repaired.get("passes", []) if isinstance(item, dict)]
    if not previous_passes or not repaired_passes:
        return repaired
    replacement = next((item for item in repaired_passes if str(item.get("pass_id") or "") == pass_id), None)
    if replacement is None and len(repaired_passes) == 1:
        replacement = repaired_passes[0]
        replacement["pass_id"] = pass_id
    if replacement is None:
        return repaired
    merged_passes = []
    replaced = False
    for item in previous_passes:
        if str(item.get("pass_id") or "") == pass_id:
            merged = {**item, **replacement}
            merged["pass_id"] = pass_id
            merged_passes.append(merged)
            replaced = True
        else:
            merged_passes.append(item)
    if not replaced:
        merged_passes.append(replacement)
    return {**previous, **repaired, "passes": merged_passes}


def _compact_schema_lines(schema_context: dict[str, Any], *, max_tables: int = 8) -> str:
    tables = schema_context.get("tables") if isinstance(schema_context, dict) else None
    if isinstance(tables, dict):
        items = [{"name": name, **(value if isinstance(value, dict) else {})} for name, value in tables.items()]
    elif isinstance(tables, list):
        items = [item for item in tables if isinstance(item, dict)]
    else:
        items = []
    lines: list[str] = []
    for item in items[:max_tables]:
        name = str(item.get("name") or item.get("table") or "").strip()
        columns = item.get("columns")
        if isinstance(columns, dict):
            col_names = list(columns)[:16]
        elif isinstance(columns, list):
            col_names = [str(col.get("name") if isinstance(col, dict) else col) for col in columns[:16]]
        else:
            col_names = []
        lines.append(f"- {name}: {', '.join(col_names)}" if col_names else f"- {name}")
    return "\n".join(lines) if lines else "- no schema summary available"


def _compact_endpoint_lines(endpoint_context: list[dict[str, Any]], *, max_endpoints: int = 8) -> str:
    lines: list[str] = []
    for endpoint in endpoint_context[:max_endpoints]:
        if not isinstance(endpoint, dict):
            continue
        method = str(endpoint.get("method") or "").upper()
        path = str(endpoint.get("path") or "")
        if method != "GET" or not path:
            continue
        desc = str(endpoint.get("use_when") or endpoint.get("description") or endpoint.get("id") or "")[:120]
        lines.append(f"- GET {path}: {desc}")
    return "\n".join(lines) if lines else "- no safe GET endpoints available"
