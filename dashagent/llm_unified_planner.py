from __future__ import annotations

import json
import os
import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any

from .llm_client import get_llm_client
from .trajectory import compact_preview, redact_secrets


ALLOWED_ROUTES = {"LLM_DIRECT", "EVIDENCE_PIPELINE"}
ALLOWED_EVIDENCE_ORDERS = {
    "NO_EVIDENCE",
    "SQL_FIRST",
    "API_FIRST",
    "SQL_THEN_API",
    "API_THEN_SQL",
    "PARALLEL",
    "MULTI_PASS",
}
MAX_LLM_OWNED_PASSES = 6
ALLOWED_PASS_PATHS = {"SQL", "API", "SQL_AND_API", "DIRECT", "AGGREGATION_ONLY"}


@dataclass
class PlannerProviderCapabilities:
    supports_tool_calls: bool | None
    supports_json_content_fallback: bool
    requires_json_prompting: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LLMUnifiedSQLCandidate:
    query: str
    params: list[Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LLMUnifiedAPIRequest:
    method: str
    path: str
    params: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LLMUnifiedPass:
    pass_id: str
    subtask: str
    path: str
    can_run_parallel: bool
    depends_on: list[str]
    evidence_order: str
    sql: LLMUnifiedSQLCandidate | None
    api_request: LLMUnifiedAPIRequest | None
    expected_result: str = ""
    optional: bool = False
    fallback: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "pass_id": self.pass_id,
            "subtask": self.subtask,
            "path": self.path,
            "can_run_parallel": self.can_run_parallel,
            "depends_on": self.depends_on,
            "evidence_order": self.evidence_order,
            "sql": self.sql.to_dict() if self.sql else None,
            "api_request": self.api_request.to_dict() if self.api_request else None,
            "expected_result": self.expected_result,
            "optional": self.optional,
            "fallback": self.fallback,
        }


@dataclass
class LLMUnifiedPlan:
    route: str
    evidence_order: str
    direct_answer: str | None
    sql: LLMUnifiedSQLCandidate | None
    api_request: LLMUnifiedAPIRequest | None
    passes: list[LLMUnifiedPass]
    aggregation_instruction: str
    reason: str
    provider: str
    model: str
    parse_error: bool = False
    backend_unavailable: bool = False
    raw_preview: Any | None = None
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "route": self.route,
            "evidence_order": self.evidence_order,
            "direct_answer": self.direct_answer,
            "sql": self.sql.to_dict() if self.sql else None,
            "api_request": self.api_request.to_dict() if self.api_request else None,
            "passes": [item.to_dict() for item in self.passes],
            "aggregation_instruction": self.aggregation_instruction,
            "reason": self.reason,
            "provider": self.provider,
            "model": self.model,
            "parse_error": self.parse_error,
            "backend_unavailable": self.backend_unavailable,
            "raw_preview": self.raw_preview,
            "diagnostics": self.diagnostics,
        }


def run_llm_unified_planner(
    *,
    user_prompt: str,
    schema_context: dict[str, Any],
    endpoint_context: list[dict[str, Any]],
    repair_context: dict[str, Any] | None = None,
    max_tokens: int = 900,
) -> LLMUnifiedPlan:
    started = time.perf_counter()
    client = get_llm_client()
    provider = client.provider_name()
    model = client.model_name()
    _apply_planner_timeout_if_supported(client)
    capabilities = planner_provider_capabilities(provider, model)
    base_diagnostics: dict[str, Any] = {
        "planner_toolcall_attempted": False,
        "planner_toolcall_supported": capabilities.supports_tool_calls,
        "planner_json_fallback_used": False,
        "planner_json_parse_error": None,
        "planner_repair_attempted": False,
        "planner_success": False,
        "planner_timeout": False,
        "planner_provider_latency_ms": None,
        "provider_capabilities": capabilities.to_dict(),
    }
    if not client.available():
        return _fallback_plan(
            provider=provider,
            model=model,
            reason="LLM backend unavailable; fail closed to EVIDENCE_PIPELINE without backend-generated SQL/API.",
            backend_unavailable=True,
            diagnostics={**base_diagnostics, "planner_provider_latency_ms": _elapsed_ms(started)},
        )

    system_prompt = _planner_system_prompt(capabilities)
    payload = _planner_payload(
        user_prompt=user_prompt,
        schema_context=schema_context,
        endpoint_context=endpoint_context,
        repair_context=repair_context,
    )
    toolcall_attempted = bool(capabilities.supports_tool_calls)
    tool = _planner_tool_schema()
    result, call_error = _call_planner_model(
        client,
        system_prompt=system_prompt,
        payload=payload,
        tool=tool if toolcall_attempted else None,
        toolcall_attempted=toolcall_attempted,
    )
    base_diagnostics["planner_toolcall_attempted"] = toolcall_attempted
    base_diagnostics["planner_provider_latency_ms"] = _elapsed_ms(started)
    if call_error:
        return _fallback_plan(
            provider=provider,
            model=model,
            reason=call_error,
            backend_unavailable=True,
            raw_preview=compact_preview(call_error, 1000),
            diagnostics={
                **base_diagnostics,
                "planner_timeout": "timeout" in call_error.lower(),
                "planner_provider_latency_ms": _elapsed_ms(started),
            },
        )
    provider = str(result.get("provider") or provider)
    model = str(result.get("model") or model)
    if not result.get("ok", True) and not result.get("content"):
        return _fallback_plan(
            provider=provider,
            model=model,
            reason=str(result.get("error") or result.get("reason") or "LLM unified planner failed"),
            backend_unavailable=bool(result.get("skipped")),
            raw_preview=compact_preview(result, 1000),
            diagnostics={**base_diagnostics, "planner_provider_latency_ms": _elapsed_ms(started)},
        )
    parsed, raw_content, parse_error, parse_source = _parse_planner_response(result, toolcall_attempted=toolcall_attempted)
    diagnostics = {
        **base_diagnostics,
        "planner_json_fallback_used": parse_source == "content_json",
        "planner_json_parse_error": parse_error,
        "planner_parse_source": parse_source,
        "planner_provider_latency_ms": _elapsed_ms(started),
    }
    if parsed is None:
        diagnostics["planner_repair_attempted"] = True
        repair_result, repair_call_error = _call_planner_model(
            client,
            system_prompt=_planner_repair_system_prompt(),
            payload=_planner_repair_payload(payload, raw_content=raw_content, parse_error=parse_error),
            tool=None,
            toolcall_attempted=False,
        )
        diagnostics["planner_provider_latency_ms"] = _elapsed_ms(started)
        if repair_call_error:
            return _fallback_plan(
                provider=provider,
                model=model,
                reason=repair_call_error,
                parse_error=True,
                backend_unavailable=True,
                raw_preview=compact_preview(raw_content, 1000),
                diagnostics={
                    **diagnostics,
                    "planner_timeout": "timeout" in repair_call_error.lower(),
                    "planner_provider_latency_ms": _elapsed_ms(started),
                },
            )
        provider = str(repair_result.get("provider") or provider)
        model = str(repair_result.get("model") or model)
        parsed, raw_content, repair_parse_error, parse_source = _parse_planner_response(repair_result, toolcall_attempted=False)
        diagnostics["planner_json_parse_error"] = repair_parse_error
        diagnostics["planner_json_fallback_used"] = True
        diagnostics["planner_parse_source"] = parse_source
        if parsed is None:
            return _fallback_plan(
                provider=provider,
                model=model,
                reason="Malformed LLM unified planner JSON after one repair attempt; fail closed to EVIDENCE_PIPELINE.",
                parse_error=True,
                raw_preview=compact_preview(raw_content, 1000),
                diagnostics={**diagnostics, "planner_provider_latency_ms": _elapsed_ms(started)},
            )
    diagnostics["planner_success"] = True
    diagnostics["planner_provider_latency_ms"] = _elapsed_ms(started)
    return normalize_llm_unified_plan(
        parsed,
        provider=provider,
        model=model,
        raw_preview=compact_preview(raw_content, 1000),
        diagnostics=diagnostics,
    )


def planner_provider_capabilities(provider: str, model: str | None = None) -> PlannerProviderCapabilities:
    normalized_provider = str(provider or "").strip().lower()
    if normalized_provider == "pioneer_chat":
        return PlannerProviderCapabilities(
            supports_tool_calls=False,
            supports_json_content_fallback=True,
            requires_json_prompting=True,
        )
    if normalized_provider in {"none", ""}:
        return PlannerProviderCapabilities(
            supports_tool_calls=False,
            supports_json_content_fallback=False,
            requires_json_prompting=False,
        )
    return PlannerProviderCapabilities(
        supports_tool_calls=True,
        supports_json_content_fallback=True,
        requires_json_prompting=False,
    )


def _planner_system_prompt(capabilities: PlannerProviderCapabilities) -> str:
    if capabilities.requires_json_prompting:
        return (
            "You are the only semantic planner for this DASHSys V2 runtime. "
            "Return ONLY one valid JSON object. No markdown, no code fence, no explanation. "
            "Choose exactly one route string: LLM_DIRECT or EVIDENCE_PIPELINE. "
            "Choose exactly one evidence_order string. Never output enum choices joined by '|'. "
            "You may choose LLM_DIRECT only for pure general, concept, meta-language, or out-of-domain questions "
            "that need no user-specific, live, SQL, or API evidence. "
            "For data, mixed, ambiguous-data-like, SQL/API, live/current/status/date/count/list/show/my prompts, "
            "choose EVIDENCE_PIPELINE and provide LLM-owned SQL and/or one safe GET API request if useful. "
            "The backend only compile-checks SQL, request-checks API shape, executes, and grounds the answer. "
            "Do not include extra keys beyond the requested schema unless needed for pass fields."
        )
    return (
        "You are the only semantic planner for this DASHSys V2 runtime. "
        "Use the submit_v2_plan tool when available; otherwise return ONLY valid JSON matching the requested schema. "
        "You may choose LLM_DIRECT only for pure general, concept, meta-language, or out-of-domain questions "
        "that need no user-specific, live, SQL, or API evidence. "
        "For data, mixed, ambiguous-data-like, SQL/API, live/current/status/date/count/list/show/my prompts, "
        "choose EVIDENCE_PIPELINE and provide SQL and/or one safe GET API request if useful. "
        "The backend will only compile-check SQL, request-check API shape, execute, and ground the final answer. "
        "Do not include markdown."
    )


def _planner_repair_system_prompt() -> str:
    return (
        "Your previous V2 planner response was not valid planner JSON. "
        "Return ONLY one corrected JSON object matching the schema. "
        "Do not add markdown, commentary, or code fences. "
        "Do not let malformed JSON fail open into LLM_DIRECT; choose EVIDENCE_PIPELINE when uncertain."
    )


def _planner_payload(
    *,
    user_prompt: str,
    schema_context: dict[str, Any],
    endpoint_context: list[dict[str, Any]],
    repair_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "output_schema": {
            "route": "LLM_DIRECT | EVIDENCE_PIPELINE",
            "evidence_order": "NO_EVIDENCE | SQL_FIRST | API_FIRST | SQL_THEN_API | API_THEN_SQL | PARALLEL | MULTI_PASS",
            "direct_answer": "string or null",
            "sql": {"query": "string", "params": []},
            "api_request": {"method": "GET", "path": "/path", "params": {}},
            "passes": [
                {
                    "pass_id": "pass_1",
                    "subtask": "short description",
                    "path": "SQL | API | SQL_AND_API | DIRECT | AGGREGATION_ONLY",
                    "can_run_parallel": True,
                    "depends_on": [],
                    "evidence_order": "SQL_FIRST | API_FIRST | SQL_THEN_API | API_THEN_SQL | PARALLEL | NO_EVIDENCE",
                    "sql": {"query": "string", "params": []},
                    "api_request": {"method": "GET", "path": "/path", "params": {}},
                    "expected_result": "short result description",
                    "optional": False,
                    "fallback": False,
                }
            ],
            "aggregation_instruction": "How to combine pass results into one final answer",
            "reason": "short string",
        },
        "user_prompt": user_prompt,
        "database_schema": compact_preview(schema_context, 7000),
        "allowed_api_endpoints": compact_preview(endpoint_context, 6000),
        "repair_context": repair_context or None,
        "constraints": [
            "LLM owns semantic route, evidence order, SQL/API candidate generation, and optional repair.",
            "LLM owns decomposition and dependency planning. Use passes for independent or dependent evidence needs.",
            "Use depends_on only when a pass needs earlier pass results. Use placeholders like {{pass_1.result.id}} only when needed.",
            "Do not output deterministic templates or explanations outside JSON.",
            "Use route LLM_DIRECT only when no runtime evidence is required.",
            "Use route EVIDENCE_PIPELINE when uncertain.",
            "API requests must be safe GET requests from the endpoint context.",
        ],
        "examples": [
            {
                "user_prompt": "What is a schema?",
                "response": {
                    "route": "LLM_DIRECT",
                    "evidence_order": "NO_EVIDENCE",
                    "direct_answer": "A schema defines the structure and meaning of data fields.",
                    "sql": None,
                    "api_request": None,
                    "passes": [],
                    "aggregation_instruction": "",
                    "reason": "pure concept question; no runtime evidence required",
                },
            },
            {
                "user_prompt": "How many schema records are in the local snapshot?",
                "response": {
                    "route": "EVIDENCE_PIPELINE",
                    "evidence_order": "SQL_FIRST",
                    "direct_answer": None,
                    "passes": [
                        {
                            "pass_id": "pass_1",
                            "subtask": "Count schema records in the local snapshot.",
                            "path": "SQL",
                            "can_run_parallel": True,
                            "depends_on": [],
                            "evidence_order": "SQL_FIRST",
                            "sql": {"query": "SELECT COUNT(*) AS count FROM <schema_table>", "params": []},
                            "api_request": None,
                            "expected_result": "local schema count",
                            "optional": False,
                            "fallback": False,
                        }
                    ],
                    "aggregation_instruction": "Answer with the count from pass_1.",
                    "reason": "count request requires runtime data evidence",
                },
            },
        ],
    }


def _planner_repair_payload(payload: dict[str, Any], *, raw_content: str, parse_error: str | None) -> dict[str, Any]:
    return {
        "task": "REPAIR_V2_PLANNER_JSON",
        "original_planner_request": compact_preview(payload, 6500),
        "previous_response": compact_preview(raw_content, 1800),
        "parse_error": str(parse_error or "unknown parse error")[:600],
        "required_output": payload.get("output_schema"),
    }


def _call_planner_model(
    client: Any,
    *,
    system_prompt: str,
    payload: dict[str, Any],
    tool: dict[str, Any] | None,
    toolcall_attempted: bool,
) -> tuple[dict[str, Any], str | None]:
    try:
        result = client.generate_messages(
            [{"role": "system", "content": system_prompt}, {"role": "user", "content": json.dumps(payload, sort_keys=True, default=str)}],
            tools=[tool] if tool is not None else None,
            tool_choice={"type": "function", "function": {"name": "submit_v2_plan"}} if toolcall_attempted else None,
            parallel_tool_calls=False if toolcall_attempted else None,
        )
        return result if isinstance(result, dict) else {"ok": False, "content": "", "error": f"Planner returned {type(result).__name__}"}, None
    except TimeoutError as exc:
        return {}, f"Planner provider timeout: {exc}"
    except Exception as exc:
        return {}, f"Planner provider error: {redact_secrets(str(exc))[:500]}"


def _parse_planner_response(result: dict[str, Any], *, toolcall_attempted: bool) -> tuple[dict[str, Any] | None, str, str | None, str | None]:
    if toolcall_attempted:
        try:
            parsed = _structured_tool_arguments(result, "submit_v2_plan")
            return parsed, json.dumps(parsed, sort_keys=True, default=str), None, "tool_call"
        except Exception:
            pass
    raw_content = str(result.get("content") or "")
    try:
        return _parse_json_object(raw_content), raw_content, None, "content_json"
    except Exception as exc:
        return None, raw_content, str(exc), None


def normalize_llm_unified_plan(
    payload: dict[str, Any],
    *,
    provider: str = "unknown",
    model: str = "unknown",
    raw_preview: Any | None = None,
    diagnostics: dict[str, Any] | None = None,
) -> LLMUnifiedPlan:
    route = str(payload.get("route") or "").strip().upper()
    evidence_order = str(payload.get("evidence_order") or "").strip().upper()
    if route not in ALLOWED_ROUTES:
        return _fallback_plan(
            provider=provider,
            model=model,
            reason="Invalid LLM route; fail closed to EVIDENCE_PIPELINE.",
            parse_error=True,
            raw_preview=raw_preview,
            diagnostics={**(diagnostics or {}), "planner_success": False},
        )
    if evidence_order not in ALLOWED_EVIDENCE_ORDERS:
        evidence_order = "NO_EVIDENCE" if route == "LLM_DIRECT" else "SQL_FIRST"
    if route == "LLM_DIRECT":
        evidence_order = "NO_EVIDENCE"
    elif evidence_order == "NO_EVIDENCE":
        evidence_order = "SQL_FIRST"

    sql = _normalize_sql_candidate(payload.get("sql"))
    api_request = _normalize_api_request(payload.get("api_request"))
    passes = _normalize_passes(payload.get("passes"), fallback_sql=sql, fallback_api_request=api_request, fallback_evidence_order=evidence_order)
    if route == "LLM_DIRECT":
        passes = []
        sql = None
        api_request = None
    elif passes and len(passes) > 1:
        evidence_order = "MULTI_PASS"
    elif evidence_order == "MULTI_PASS" and len(passes) <= 1:
        evidence_order = passes[0].evidence_order if passes else "SQL_FIRST"
    if passes:
        sql = passes[0].sql
        api_request = passes[0].api_request
    direct_answer = payload.get("direct_answer")
    if direct_answer is not None:
        direct_answer = str(direct_answer).strip() or None
    return LLMUnifiedPlan(
        route=route,
        evidence_order=evidence_order,
        direct_answer=direct_answer,
        sql=sql,
        api_request=api_request,
        passes=passes,
        aggregation_instruction=str(payload.get("aggregation_instruction") or "").strip(),
        reason=str(payload.get("reason") or ""),
        provider=provider,
        model=model,
        raw_preview=raw_preview,
        diagnostics=diagnostics or {},
    )


def _normalize_sql_candidate(value: Any) -> LLMUnifiedSQLCandidate | None:
    if not isinstance(value, dict):
        return None
    query = str(value.get("query") or value.get("sql") or "").strip()
    if not query:
        return None
    params = value.get("params")
    if params is None:
        normalized_params = None
    elif isinstance(params, list):
        normalized_params = list(params)
    else:
        normalized_params = [params]
    return LLMUnifiedSQLCandidate(query=query, params=normalized_params)


def _normalize_api_request(value: Any) -> LLMUnifiedAPIRequest | None:
    if not isinstance(value, dict):
        return None
    method = str(value.get("method") or "").strip().upper()
    path = str(value.get("path") or value.get("url") or "").strip()
    params = value.get("params")
    normalized_params = dict(params) if isinstance(params, dict) else ({} if params is None else None)
    if not method or not path or normalized_params is None:
        return LLMUnifiedAPIRequest(method=method, path=path, params=None)
    return LLMUnifiedAPIRequest(method=method, path=path, params=normalized_params)


def _normalize_passes(
    value: Any,
    *,
    fallback_sql: LLMUnifiedSQLCandidate | None,
    fallback_api_request: LLMUnifiedAPIRequest | None,
    fallback_evidence_order: str,
) -> list[LLMUnifiedPass]:
    passes: list[LLMUnifiedPass] = []
    if isinstance(value, list):
        for index, item in enumerate(value[:MAX_LLM_OWNED_PASSES], start=1):
            normalized = _normalize_pass(item, index=index)
            if normalized is not None:
                passes.append(normalized)
    if passes:
        return passes
    if fallback_sql is None and fallback_api_request is None:
        return []
    return [
        LLMUnifiedPass(
            pass_id="pass_1",
            subtask="Primary evidence pass.",
            path="SQL_AND_API" if fallback_sql is not None and fallback_api_request is not None else ("SQL" if fallback_sql is not None else "API"),
            can_run_parallel=True,
            depends_on=[],
            evidence_order=fallback_evidence_order if fallback_evidence_order in ALLOWED_EVIDENCE_ORDERS else "SQL_FIRST",
            sql=fallback_sql,
            api_request=fallback_api_request,
            expected_result="Primary runtime evidence.",
            optional=False,
            fallback=False,
        )
    ]


def _normalize_pass(value: Any, *, index: int) -> LLMUnifiedPass | None:
    if not isinstance(value, dict):
        return None
    evidence_order = str(value.get("evidence_order") or "").strip().upper()
    if evidence_order not in ALLOWED_EVIDENCE_ORDERS:
        evidence_order = "SQL_FIRST"
    sql = _normalize_sql_candidate(value.get("sql"))
    api_request = _normalize_api_request(value.get("api_request"))
    path = _normalize_pass_path(value.get("path"), sql=sql, api_request=api_request, evidence_order=evidence_order)
    if sql is None and api_request is None and evidence_order != "NO_EVIDENCE":
        evidence_order = "NO_EVIDENCE"
    depends_on = value.get("depends_on")
    if not isinstance(depends_on, list):
        depends_on = []
    pass_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value.get("pass_id") or f"pass_{index}").strip())[:80] or f"pass_{index}"
    return LLMUnifiedPass(
        pass_id=pass_id,
        subtask=str(value.get("subtask") or f"Evidence pass {index}.").strip(),
        path=path,
        can_run_parallel=bool(value.get("can_run_parallel", False)),
        depends_on=[str(item).strip() for item in depends_on if str(item).strip()],
        evidence_order=evidence_order,
        sql=sql,
        api_request=api_request,
        expected_result=str(value.get("expected_result") or "").strip(),
        optional=bool(value.get("optional", False)),
        fallback=bool(value.get("fallback", False)),
    )


def _dedupe_pass_ids(passes: list[LLMUnifiedPass]) -> list[LLMUnifiedPass]:
    seen: dict[str, int] = {}
    out: list[LLMUnifiedPass] = []
    for item in passes:
        base = item.pass_id
        seen[base] = seen.get(base, 0) + 1
        if seen[base] == 1:
            out.append(item)
        else:
            out.append(
                LLMUnifiedPass(
                    pass_id=f"{base}_{seen[base]}",
                    subtask=item.subtask,
                    path=item.path,
                    can_run_parallel=item.can_run_parallel,
                    depends_on=item.depends_on,
                    evidence_order=item.evidence_order,
                    sql=item.sql,
                    api_request=item.api_request,
                    expected_result=item.expected_result,
                    optional=item.optional,
                    fallback=item.fallback,
                )
            )
    return out


def _normalize_pass_path(
    value: Any,
    *,
    sql: LLMUnifiedSQLCandidate | None,
    api_request: LLMUnifiedAPIRequest | None,
    evidence_order: str,
) -> str:
    path = str(value or "").strip().upper()
    if path:
        return path
    if sql is not None and api_request is not None:
        return "SQL_AND_API"
    if sql is not None:
        return "SQL"
    if api_request is not None:
        return "API"
    if evidence_order == "NO_EVIDENCE":
        return "DIRECT"
    return "AGGREGATION_ONLY"


def _parse_json_object(text: str) -> dict[str, Any]:
    stripped = _extract_json_object_text(text)
    parsed = json.loads(stripped)
    if not isinstance(parsed, dict):
        raise ValueError("Planner response must be a JSON object")
    return parsed


def _structured_tool_arguments(result: dict[str, Any], tool_name: str) -> dict[str, Any]:
    for call in result.get("tool_calls") or []:
        if not isinstance(call, dict):
            continue
        name = call.get("name") or call.get("tool")
        if name != tool_name:
            continue
        arguments = call.get("arguments")
        if isinstance(arguments, dict):
            return arguments
        raw = call.get("raw_arguments")
        if isinstance(raw, str):
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
    raise ValueError(f"Missing structured tool output: {tool_name}")


def _planner_tool_schema() -> dict[str, Any]:
    pass_schema = {
        "type": "object",
        "properties": {
            "pass_id": {"type": "string"},
            "subtask": {"type": "string"},
            "path": {"type": "string", "enum": sorted(ALLOWED_PASS_PATHS)},
            "depends_on": {"type": "array", "items": {"type": "string"}},
            "can_run_parallel": {"type": "boolean"},
            "sql": {
                "type": ["object", "null"],
                "properties": {"query": {"type": "string"}, "params": {"type": "array"}},
                "required": ["query"],
            },
            "api_request": {
                "type": ["object", "null"],
                "properties": {"method": {"type": "string"}, "path": {"type": "string"}, "params": {"type": "object"}},
                "required": ["method", "path"],
            },
            "expected_result": {"type": "string"},
            "optional": {"type": "boolean"},
            "fallback": {"type": "boolean"},
        },
        "required": ["pass_id", "subtask", "path", "depends_on", "can_run_parallel"],
    }
    return {
        "type": "function",
        "function": {
            "name": "submit_v2_plan",
            "description": "Submit the LLM-owned V2 route, evidence order, pass DAG, SQL/API candidates, and aggregation instruction.",
            "parameters": {
                "type": "object",
                "properties": {
                    "route": {"type": "string", "enum": sorted(ALLOWED_ROUTES)},
                    "evidence_order": {"type": "string", "enum": sorted(ALLOWED_EVIDENCE_ORDERS)},
                    "direct_answer": {"type": ["string", "null"]},
                    "passes": {"type": "array", "items": pass_schema},
                    "aggregation_instruction": {"type": ["string", "null"]},
                    "reason": {"type": ["string", "null"]},
                },
                "required": ["route", "evidence_order", "passes"],
            },
        },
    }


def _strip_json_text(text: str) -> str:
    stripped = str(text or "").strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?", "", stripped, flags=re.I).strip()
        stripped = re.sub(r"```$", "", stripped).strip()
    match = re.search(r"\{.*\}", stripped, flags=re.S)
    return match.group(0) if match else stripped


def _extract_json_object_text(text: str) -> str:
    stripped = _strip_json_text(text)
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped
    start = stripped.find("{")
    if start < 0:
        return stripped
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(stripped)):
        char = stripped[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return stripped[start : index + 1]
    return stripped[start:]


def _apply_planner_timeout_if_supported(client: Any) -> None:
    raw_timeout = os.getenv("PIONEER_PLANNER_TIMEOUT_SEC")
    if not raw_timeout:
        return
    try:
        timeout_seconds = int(raw_timeout)
    except Exception:
        return
    if timeout_seconds <= 0:
        return
    if getattr(client, "provider_name", lambda: "")() != "pioneer_chat":
        return
    if hasattr(client, "timeout_seconds"):
        try:
            setattr(client, "timeout_seconds", timeout_seconds)
            if hasattr(client, "_sdk_client"):
                setattr(client, "_sdk_client", None)
        except Exception:
            return


def _elapsed_ms(started: float) -> int:
    return int(round((time.perf_counter() - started) * 1000))


def _fallback_plan(
    *,
    provider: str,
    model: str,
    reason: str,
    parse_error: bool = False,
    backend_unavailable: bool = False,
    raw_preview: Any | None = None,
    diagnostics: dict[str, Any] | None = None,
) -> LLMUnifiedPlan:
    return LLMUnifiedPlan(
        route="EVIDENCE_PIPELINE",
        evidence_order="SQL_FIRST",
        direct_answer=None,
        sql=None,
        api_request=None,
        passes=[],
        aggregation_instruction="",
        reason=redact_secrets(reason),
        provider=provider,
        model=model,
        parse_error=parse_error,
        backend_unavailable=backend_unavailable,
        raw_preview=raw_preview,
        diagnostics=diagnostics or {},
    )
