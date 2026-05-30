from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
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
    can_run_parallel: bool
    depends_on: list[str]
    evidence_order: str
    sql: LLMUnifiedSQLCandidate | None
    api_request: LLMUnifiedAPIRequest | None
    expected_result: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "pass_id": self.pass_id,
            "subtask": self.subtask,
            "can_run_parallel": self.can_run_parallel,
            "depends_on": self.depends_on,
            "evidence_order": self.evidence_order,
            "sql": self.sql.to_dict() if self.sql else None,
            "api_request": self.api_request.to_dict() if self.api_request else None,
            "expected_result": self.expected_result,
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
        }


def run_llm_unified_planner(
    *,
    user_prompt: str,
    schema_context: dict[str, Any],
    endpoint_context: list[dict[str, Any]],
    repair_context: dict[str, Any] | None = None,
    max_tokens: int = 900,
) -> LLMUnifiedPlan:
    client = get_llm_client()
    provider = client.provider_name()
    model = client.model_name()
    if not client.available():
        return _fallback_plan(
            provider=provider,
            model=model,
            reason="LLM backend unavailable; fail closed to EVIDENCE_PIPELINE without backend-generated SQL/API.",
            backend_unavailable=True,
        )

    system_prompt = (
        "You are the only semantic planner for this DASHSys V2 runtime. "
        "Return ONLY valid JSON matching the requested schema. "
        "You may choose LLM_DIRECT only for pure general, concept, meta-language, or out-of-domain questions "
        "that need no user-specific, live, SQL, or API evidence. "
        "For data, mixed, ambiguous-data-like, SQL/API, live/current/status/date/count/list/show/my prompts, "
        "choose EVIDENCE_PIPELINE and provide SQL and/or one safe GET API request if useful. "
        "The backend will only compile-check SQL, request-check API shape, execute, and ground the final answer. "
        "Do not rely on tool calling. Do not include markdown."
    )
    payload = {
        "output_schema": {
            "route": "LLM_DIRECT | EVIDENCE_PIPELINE",
            "evidence_order": "NO_EVIDENCE | SQL_FIRST | API_FIRST | SQL_THEN_API | API_THEN_SQL | PARALLEL",
            "direct_answer": "string or null",
            "sql": {"query": "string", "params": []},
            "api_request": {"method": "GET", "path": "/path", "params": {}},
            "passes": [
                {
                    "pass_id": "pass_1",
                    "subtask": "short description",
                    "can_run_parallel": True,
                    "depends_on": [],
                    "evidence_order": "SQL_FIRST | API_FIRST | SQL_THEN_API | API_THEN_SQL | PARALLEL | NO_EVIDENCE",
                    "sql": {"query": "string", "params": []},
                    "api_request": {"method": "GET", "path": "/path", "params": {}},
                    "expected_result": "short result description",
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
            "LLM owns decomposition for long prompts. Use passes for independent or dependent evidence needs.",
            "Do not output deterministic templates or explanations outside JSON.",
            "Use route LLM_DIRECT only when no runtime evidence is required.",
            "Use route EVIDENCE_PIPELINE when uncertain.",
            "API requests must be safe GET requests from the endpoint context.",
        ],
    }
    result = client.generate(system_prompt, json.dumps(payload, sort_keys=True, default=str))
    provider = str(result.get("provider") or provider)
    model = str(result.get("model") or model)
    if not result.get("ok", True) and not result.get("content"):
        return _fallback_plan(
            provider=provider,
            model=model,
            reason=str(result.get("error") or result.get("reason") or "LLM unified planner failed"),
            backend_unavailable=bool(result.get("skipped")),
            raw_preview=compact_preview(result, 1000),
        )
    raw_content = str(result.get("content") or "")
    try:
        parsed = _parse_json_object(raw_content)
    except Exception:
        return _fallback_plan(
            provider=provider,
            model=model,
            reason="Malformed LLM unified planner JSON; fail closed to EVIDENCE_PIPELINE.",
            parse_error=True,
            raw_preview=compact_preview(raw_content, 1000),
        )
    return normalize_llm_unified_plan(parsed, provider=provider, model=model, raw_preview=compact_preview(raw_content, 1000))


def normalize_llm_unified_plan(payload: dict[str, Any], *, provider: str = "unknown", model: str = "unknown", raw_preview: Any | None = None) -> LLMUnifiedPlan:
    route = str(payload.get("route") or "").strip().upper()
    evidence_order = str(payload.get("evidence_order") or "").strip().upper()
    if route not in ALLOWED_ROUTES:
        return _fallback_plan(provider=provider, model=model, reason="Invalid LLM route; fail closed to EVIDENCE_PIPELINE.", parse_error=True, raw_preview=raw_preview)
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
        return _dedupe_pass_ids(passes)
    if fallback_sql is None and fallback_api_request is None:
        return []
    return [
        LLMUnifiedPass(
            pass_id="pass_1",
            subtask="Primary evidence pass.",
            can_run_parallel=True,
            depends_on=[],
            evidence_order=fallback_evidence_order if fallback_evidence_order in ALLOWED_EVIDENCE_ORDERS else "SQL_FIRST",
            sql=fallback_sql,
            api_request=fallback_api_request,
            expected_result="Primary runtime evidence.",
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
    if sql is None and api_request is None and evidence_order != "NO_EVIDENCE":
        evidence_order = "NO_EVIDENCE"
    depends_on = value.get("depends_on")
    if not isinstance(depends_on, list):
        depends_on = []
    pass_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value.get("pass_id") or f"pass_{index}").strip())[:80] or f"pass_{index}"
    return LLMUnifiedPass(
        pass_id=pass_id,
        subtask=str(value.get("subtask") or f"Evidence pass {index}.").strip(),
        can_run_parallel=bool(value.get("can_run_parallel", False)),
        depends_on=[str(item).strip() for item in depends_on if str(item).strip()],
        evidence_order=evidence_order,
        sql=sql,
        api_request=api_request,
        expected_result=str(value.get("expected_result") or "").strip(),
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
                    can_run_parallel=item.can_run_parallel,
                    depends_on=item.depends_on,
                    evidence_order=item.evidence_order,
                    sql=item.sql,
                    api_request=item.api_request,
                    expected_result=item.expected_result,
                )
            )
    return out


def _parse_json_object(text: str) -> dict[str, Any]:
    stripped = _strip_json_text(text)
    parsed = json.loads(stripped)
    if not isinstance(parsed, dict):
        raise ValueError("Planner response must be a JSON object")
    return parsed


def _strip_json_text(text: str) -> str:
    stripped = str(text or "").strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?", "", stripped, flags=re.I).strip()
        stripped = re.sub(r"```$", "", stripped).strip()
    match = re.search(r"\{.*\}", stripped, flags=re.S)
    return match.group(0) if match else stripped


def _fallback_plan(
    *,
    provider: str,
    model: str,
    reason: str,
    parse_error: bool = False,
    backend_unavailable: bool = False,
    raw_preview: Any | None = None,
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
    )
