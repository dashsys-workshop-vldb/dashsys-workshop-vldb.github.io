from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from .answer_slots import AnswerSlots
from .evidence_allowed_fact_index import build_allowed_fact_index
from .evidence_bus import EvidenceBus
from .evidence_grounded_final_answer_verifier import verify_evidence_grounded_final_answer
from .final_answer_claim_extractor import extract_final_answer_claims
from .llm_client import get_llm_client
from .llm_unified_planner import LLMUnifiedPlan, planner_provider_capabilities
from .result_bundle import ResultBundle
from .trajectory import compact_preview, redact_secrets


SENSITIVE_CONTEXT_KEYS = {
    "gold",
    "gold_answer",
    "category",
    "tags",
    "oracle",
    "expected_trace",
    "expected_observable_trace",
    "query_id",
    "example_id",
}
FINAL_ANSWER_MAX_TOKENS = 260


@dataclass
class LLMFinalAnswerCandidate:
    final_answer: str | None
    used_pass_ids: list[str] = field(default_factory=list)
    answered_subtasks: list[str] = field(default_factory=list)
    unanswered_subtasks: list[str] = field(default_factory=list)
    claimed_facts: list[dict[str, Any]] = field(default_factory=list)
    caveats_included: list[str] = field(default_factory=list)
    provider: str = "unknown"
    model: str = "unknown"
    raw_preview: Any | None = None
    parse_error: bool = False
    backend_unavailable: bool = False
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FinalAnswerSyntaxGateResult:
    passed: bool
    error_type: str | None = None
    error_message: str | None = None
    final_answer: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FinalAnswerSemanticGateResult:
    passed: bool
    error_type: str | None = None
    error_message: str | None = None
    unsupported_claims: list[dict[str, Any]] = field(default_factory=list)
    missing_required_fields: list[str] = field(default_factory=list)
    scope_errors: list[str] = field(default_factory=list)
    verifier: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_llm_final_answer_card(
    *,
    user_prompt: str,
    llm_plan: LLMUnifiedPlan,
    runtime_passes: list[dict[str, Any]],
    evidence_bus: EvidenceBus,
    answer_slots: AnswerSlots,
    evidence_quality: dict[str, Any] | None = None,
    result_bundle: ResultBundle | None = None,
    aggregation_instruction: str = "",
    repair_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    card = {
        "task": "LLM_OWNED_FINAL_ANSWER_COMPOSITION",
        "user_prompt": user_prompt,
        "llm_plan": {
            "route": llm_plan.route,
            "evidence_order": llm_plan.evidence_order,
            "reason": llm_plan.reason,
            "sql_present": llm_plan.sql is not None,
            "api_request_present": llm_plan.api_request is not None,
        },
        "task_checklist": _task_checklist(llm_plan),
        "required_task_ids": _required_task_ids(llm_plan),
        "runtime_passes": [_safe_pass_payload(item) for item in runtime_passes],
        "AVAILABLE_RUNTIME_FACTS": _available_runtime_facts(runtime_passes, answer_slots),
        "FAILED_OR_UNAVAILABLE_SOURCES": _failed_or_unavailable_sources(runtime_passes, evidence_bus),
        "pass_result_checklist": _pass_result_checklist(runtime_passes),
        "result_bundle": _compact_result_bundle(result_bundle) if result_bundle is not None else None,
        "evidence_bus": evidence_bus.compact(),
        "answer_slots": answer_slots.compact(),
        "evidence_quality": compact_preview(evidence_quality or {}, 1800),
        "aggregation_instruction": aggregation_instruction or llm_plan.aggregation_instruction,
        "repair_context": _final_answer_repair_context(repair_context) if repair_context else None,
        "required_caveats": _required_caveats(runtime_passes, evidence_bus),
        "scope_labels": ["LOCAL_SNAPSHOT", "LIVE_API", "API_ERROR", "LIVE_EMPTY"],
        "final_answer_max_tokens": FINAL_ANSWER_MAX_TOKENS,
        "constraints": [
            "Generate the final answer using only runtime evidence in this card.",
            "Treat AVAILABLE_RUNTIME_FACTS as the authoritative facts for the final answer.",
            "If AVAILABLE_RUNTIME_FACTS is non-empty, answer from those facts and do not say runtime evidence is globally unavailable.",
            "If AVAILABLE_RUNTIME_FACTS is non-empty and FAILED_OR_UNAVAILABLE_SOURCES is non-empty, answer the available scoped facts first, then add only the scoped failed-source caveat.",
            "Answer every required task ID with successful evidence.",
            "If a required task failed, state the scoped unavailable/error caveat for that task.",
            "If any required local evidence succeeded while live/API evidence failed, answer the successful local evidence first and include a scoped live/API caveat.",
            "Only use the global runtime-unavailable answer if all required evidence failed or no usable runtime evidence exists.",
            "Preserve local snapshot versus live/API scope exactly.",
            "Do not claim live/current/platform state unless LIVE_API evidence supports it.",
            "Do not turn API_ERROR into no-data.",
            "Do not turn LIVE_EMPTY into global absence.",
            "For count prompts, if AVAILABLE_RUNTIME_FACTS includes a count, state that exact count.",
            "For what/list prompts, list or summarize only the names/IDs provided in AVAILABLE_RUNTIME_FACTS.",
            "For date/when prompts, state the exact date/timestamp from AVAILABLE_RUNTIME_FACTS or say that field was not available in the relevant scope.",
            "For mixed concept plus data prompts, give one concise concept sentence plus the scoped data facts from AVAILABLE_RUNTIME_FACTS.",
            "Keep the final answer concise: usually one to four sentences, no markdown tables, and no long explanatory preamble.",
            "If no matching runtime evidence is available, use exactly: No matching runtime evidence was available for this query/scope.",
            "If all required runtime evidence is unavailable or errored, use exactly: Runtime evidence was unavailable; cannot provide a verified answer.",
            "When repairing unsupported claims, remove the unsupported span instead of restating it as a negative fact.",
            "Include required information from evidence when the user explicitly asked for it.",
            "Do not add list-size phrases such as 'first 10' unless that exact list-size fact is present in runtime evidence.",
            "For multi-pass plans, answer all requested parts using the relevant pass results.",
            "Extra context or explanation is allowed only when semantically correct and evidence-safe.",
            "Do not optimize for hidden eval, gold answer wording, or scorer-specific phrasing.",
        ],
        "hidden_eval_gold_used": False,
        "deterministic_answer_template_used": False,
        "weak_model_stable_protocol": True,
    }
    return _strip_sensitive_keys(card)


def compose_llm_final_answer(
    *,
    card: dict[str, Any],
    repair_context: dict[str, Any] | None = None,
    max_tokens: int = FINAL_ANSWER_MAX_TOKENS,
) -> LLMFinalAnswerCandidate:
    client = get_llm_client()
    provider = client.provider_name()
    model = client.model_name()
    if not client.available():
        return LLMFinalAnswerCandidate(
            final_answer=None,
            provider=provider,
            model=model,
            backend_unavailable=True,
            error_message="LLM backend unavailable for final answer composition.",
        )
    capabilities = planner_provider_capabilities(provider, model)
    prefer_plain_text = bool(card.get("weak_model_stable_protocol"))
    system_prompt = _final_answer_system_prompt(
        requires_json_prompting=capabilities.requires_json_prompting,
        prefer_plain_text=prefer_plain_text,
    )
    payload = dict(card)
    payload["final_answer_max_tokens"] = max_tokens
    if repair_context:
        payload["repair_context"] = _final_answer_repair_context(repair_context)
    toolcall_attempted = bool(capabilities.supports_tool_calls and not prefer_plain_text)
    result = _generate_final_answer_messages(
        client,
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": json.dumps(payload, sort_keys=True, default=str)}],
        tools=[_final_answer_tool_schema()] if toolcall_attempted else None,
        tool_choice={"type": "function", "function": {"name": "submit_final_answer"}} if toolcall_attempted else None,
        parallel_tool_calls=False if toolcall_attempted else None,
        max_tokens=max_tokens,
    )
    provider = str(result.get("provider") or provider)
    model = str(result.get("model") or model)
    if not result.get("ok", True) and not result.get("content"):
        return LLMFinalAnswerCandidate(
            final_answer=None,
            provider=provider,
            model=model,
            backend_unavailable=bool(result.get("skipped")),
            raw_preview=compact_preview(result, 1200),
            error_message=str(result.get("error") or result.get("reason") or "LLM final answer composition failed"),
        )
    try:
        structured = _structured_tool_arguments(result, "submit_final_answer")
        candidate = parse_llm_final_answer_response(json.dumps(structured, sort_keys=True, default=str))
    except Exception:
        candidate = parse_llm_final_answer_response(str(result.get("content") or ""), allow_plain_text=prefer_plain_text)
    candidate.provider = provider
    candidate.model = model
    return candidate


def _final_answer_system_prompt(*, requires_json_prompting: bool = False, prefer_plain_text: bool = False) -> str:
    if prefer_plain_text:
        return (
            "You are the final-answer writer for DASHSys V2. "
            "Return plain natural language final answer text only. No JSON wrapper, no markdown, no code fence. "
            "Use only runtime evidence provided in the card. "
            "AVAILABLE_RUNTIME_FACTS is authoritative; if it is non-empty, answer from it and do not say runtime evidence is globally unavailable. "
            "If API/live evidence failed but local evidence succeeded, answer the local evidence first and include only the scoped API/live caveat. "
            "Do not use hidden eval or gold-answer wording. "
            "Do not invent counts, dates, statuses, entity names, IDs, relationships, live state, or API success. "
            "If no matching runtime evidence is available, use exactly: No matching runtime evidence was available for this query/scope. "
            "If some local evidence succeeded but live/API evidence failed, answer the local evidence first and include the scoped live/API caveat. "
            "Use exactly 'Runtime evidence was unavailable; cannot provide a verified answer.' only when all required runtime evidence is unavailable or errored. "
            "When repairing unsupported claims, remove the unsupported span instead of restating it as a negative fact. "
            "Keep the answer concise: usually one to four sentences, no markdown tables, and no long preamble."
        )
    if requires_json_prompting:
        return (
            "You are the sole final-answer composer for DASHSys V2. "
            "Return ONLY one valid JSON object. No markdown, no code fence, no explanation outside JSON. "
            "Required keys: final_answer, used_pass_ids, claimed_facts, caveats_included. "
            "Use only runtime evidence provided in the card. "
            "AVAILABLE_RUNTIME_FACTS is authoritative; if it is non-empty, answer from it and do not say runtime evidence is globally unavailable. "
            "If API/live evidence failed but local evidence succeeded, answer the local evidence first and include only the scoped API/live caveat. "
            "Do not use hidden eval or gold-answer wording. "
            "Do not invent counts, dates, statuses, entity names, IDs, relationships, live state, or API success. "
            "If no matching runtime evidence is available, use exactly: No matching runtime evidence was available for this query/scope. "
            "If some local evidence succeeded but live/API evidence failed, answer the local evidence first and include the scoped live/API caveat. "
            "Use exactly 'Runtime evidence was unavailable; cannot provide a verified answer.' only when all required runtime evidence is unavailable or errored. "
            "When repairing unsupported claims, remove the unsupported span instead of restating it as a negative fact. "
            "Keep the answer concise: usually one to four sentences, no markdown tables, and no long preamble."
        )
    return (
        "You are the sole final-answer composer for DASHSys V2. "
        "Use the submit_final_answer tool when available; otherwise return ONLY valid JSON with keys final_answer, used_pass_ids, claimed_facts, caveats_included. "
        "Use only runtime evidence provided in the card. "
        "AVAILABLE_RUNTIME_FACTS is authoritative; if it is non-empty, answer from it and do not say runtime evidence is globally unavailable. "
        "Do not use hidden eval or gold-answer wording. "
        "Do not invent counts, dates, statuses, entity names, IDs, relationships, live state, or API success. "
        "Do not call tools. Do not include markdown."
    )


def parse_llm_final_answer_response(raw_content: str, *, allow_plain_text: bool = False) -> LLMFinalAnswerCandidate:
    text = str(raw_content or "").strip()
    try:
        parsed = json.loads(_strip_json_text(text))
    except Exception as exc:
        if allow_plain_text and text:
            return LLMFinalAnswerCandidate(
                final_answer=text,
                used_pass_ids=[],
                claimed_facts=[],
                caveats_included=[],
                raw_preview=compact_preview(text, 1200),
            )
        return LLMFinalAnswerCandidate(
            final_answer=None,
            raw_preview=compact_preview(text, 1200),
            parse_error=True,
            error_message=f"Final answer wrapper is not valid JSON: {str(exc)[:180]}",
        )
    if not isinstance(parsed, dict):
        return LLMFinalAnswerCandidate(
            final_answer=None,
            raw_preview=compact_preview(parsed, 1200),
            parse_error=True,
            error_message="Final answer wrapper must be a JSON object.",
        )
    return LLMFinalAnswerCandidate(
        final_answer=str(parsed.get("final_answer")).strip() if parsed.get("final_answer") is not None else None,
        used_pass_ids=[str(value) for value in parsed.get("used_pass_ids", []) if value] if isinstance(parsed.get("used_pass_ids"), list) else [],
        answered_subtasks=[str(value) for value in parsed.get("answered_subtasks", []) if value] if isinstance(parsed.get("answered_subtasks"), list) else [],
        unanswered_subtasks=[str(value) for value in parsed.get("unanswered_subtasks", []) if value] if isinstance(parsed.get("unanswered_subtasks"), list) else [],
        claimed_facts=[dict(value) for value in parsed.get("claimed_facts", []) if isinstance(value, dict)] if isinstance(parsed.get("claimed_facts"), list) else [],
        caveats_included=[str(value) for value in parsed.get("caveats_included", []) if value] if isinstance(parsed.get("caveats_included"), list) else [],
        raw_preview=compact_preview(parsed, 1200),
    )


def check_final_answer_syntax(candidate: LLMFinalAnswerCandidate) -> FinalAnswerSyntaxGateResult:
    if candidate.parse_error:
        return FinalAnswerSyntaxGateResult(False, "malformed_json", _safe_error(candidate.error_message), None)
    answer = candidate.final_answer
    if not isinstance(answer, str):
        return FinalAnswerSyntaxGateResult(False, "missing_final_answer", "final_answer must be a string.", None)
    answer = answer.strip()
    if not answer:
        return FinalAnswerSyntaxGateResult(False, "empty_answer", "final_answer must not be empty.", answer)
    if not isinstance(candidate.used_pass_ids, list) or not isinstance(candidate.claimed_facts, list) or not isinstance(candidate.caveats_included, list):
        return FinalAnswerSyntaxGateResult(False, "malformed_wrapper", "required wrapper list fields are malformed.", answer)
    return FinalAnswerSyntaxGateResult(True, None, None, answer)


def check_final_answer_semantic_grounding(
    final_answer: str,
    *,
    question: str,
    runtime_passes: list[dict[str, Any]],
    evidence_bus: EvidenceBus,
    slots: AnswerSlots,
) -> FinalAnswerSemanticGateResult:
    caveats = _caveats_from_passes(runtime_passes)
    index = build_allowed_fact_index(slots=slots, evidence_bus=evidence_bus, caveats=caveats)
    scope_errors = _scope_errors(final_answer, question=question, runtime_passes=runtime_passes, slots=slots)
    if scope_errors:
        return FinalAnswerSemanticGateResult(False, "scope_error", scope_errors[0], scope_errors=scope_errors)

    caveat_error = _caveat_error(final_answer, runtime_passes=runtime_passes, slots=slots)
    if caveat_error:
        return FinalAnswerSemanticGateResult(False, "caveat_error", caveat_error)

    contradiction = _contradiction(final_answer, index)
    if contradiction:
        return FinalAnswerSemanticGateResult(False, "contradiction", contradiction["message"], unsupported_claims=[contradiction])

    verification = verify_evidence_grounded_final_answer(
        final_answer,
        slots=slots,
        evidence_bus=evidence_bus,
        question=question,
        caveats=caveats,
        llm_judge_enabled=False,
    )
    blocked = verification.unsupported_claims + verification.over_specified_claims + verification.needs_caveat_claims
    if blocked:
        return FinalAnswerSemanticGateResult(
            False,
            _semantic_error_type(blocked),
            "Final answer contains a hard claim not supported by runtime evidence.",
            unsupported_claims=blocked,
            verifier=verification.to_dict(),
        )

    missing = _missing_required_fields(final_answer, question=question, index=index, slots=slots, runtime_passes=runtime_passes)
    missing.extend(_missing_required_pass_results(final_answer, runtime_passes=runtime_passes))
    if missing:
        return FinalAnswerSemanticGateResult(
            False,
            "missing_required_info",
            "Final answer omitted information explicitly requested and present in runtime evidence.",
            missing_required_fields=missing,
            verifier=verification.to_dict(),
        )

    return FinalAnswerSemanticGateResult(True, None, None, verifier=verification.to_dict())


def safe_llm_final_answer_fallback(
    runtime_passes: list[dict[str, Any]],
    *,
    syntax_gate: FinalAnswerSyntaxGateResult | None = None,
    semantic_gate: FinalAnswerSemanticGateResult | None = None,
    slots: AnswerSlots | None = None,
) -> str:
    available = _available_runtime_facts(runtime_passes, slots)
    if available:
        summary = _fallback_fact_summary(available)
        prefix = "Local snapshot evidence shows" if any(str(item.get("scope") or "").upper() == "LOCAL_SNAPSHOT" for item in available) else "Runtime evidence shows"
        answer = f"{prefix} {summary}."
        failed = _failed_or_unavailable_sources(runtime_passes, None)
        runtime_failed = [
            item
            for item in failed
            if str(item.get("source") or item.get("path") or "").upper() not in {"DIRECT", "CONCEPT", ""}
        ]
        if any(str(item.get("source") or item.get("status") or "").upper() in {"API", "LIVE_API", "API_ERROR"} for item in failed):
            answer += " Live API evidence was unavailable, so a live comparison cannot be completed."
        elif runtime_failed:
            answer += " Some requested runtime evidence was unavailable for this query/scope."
        return answer
    statuses = {str(item.get("status") or "").upper() for item in runtime_passes}
    has_success = "SUCCESS" in statuses or any(_pass_has_successful_evidence(item) for item in runtime_passes)
    if has_success:
        return "I could not compose a verified final answer from the available runtime evidence."
    if statuses & {"API_ERROR", "ERROR"}:
        return "Runtime evidence was unavailable; cannot provide a verified answer."
    if statuses & {"LIVE_EMPTY", "EMPTY"}:
        return "No matching runtime evidence was available for this query/scope."
    return "I could not compose a verified final answer from the available runtime evidence."


def _strip_json_text(text: str) -> str:
    stripped = str(text or "").strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?", "", stripped, flags=re.I).strip()
        stripped = re.sub(r"```$", "", stripped).strip()
    match = re.search(r"\{.*\}", stripped, flags=re.S)
    return match.group(0) if match else stripped


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


def _final_answer_tool_schema() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "submit_final_answer",
            "description": "Submit the LLM-owned final answer wrapper grounded in current run evidence.",
            "parameters": {
                "type": "object",
                "properties": {
                    "final_answer": {"type": "string"},
                    "used_pass_ids": {"type": "array", "items": {"type": "string"}},
                    "claimed_facts": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "claim": {"type": "string"},
                                "supporting_pass_ids": {"type": "array", "items": {"type": "string"}},
                            },
                        },
                    },
                    "caveats_included": {"type": "array", "items": {"type": "string"}},
                    "answered_subtasks": {"type": "array", "items": {"type": "string"}},
                    "unanswered_subtasks": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["final_answer", "used_pass_ids", "claimed_facts", "caveats_included"],
            },
        },
    }


def _safe_pass_payload(item: dict[str, Any]) -> dict[str, Any]:
    return _strip_sensitive_keys(compact_preview(_truncate_long_strings(item), 1600))


def _compact_result_bundle(result_bundle: ResultBundle | None) -> dict[str, Any] | None:
    if result_bundle is None:
        return None
    data = result_bundle.to_dict()
    runtime_passes = data.get("runtime_passes") if isinstance(data.get("runtime_passes"), list) else []
    tool_results = data.get("tool_results") if isinstance(data.get("tool_results"), list) else []
    append_events = data.get("append_events") if isinstance(data.get("append_events"), list) else []
    return _strip_sensitive_keys(
        {
            "run_id": data.get("run_id"),
            "pass_results_count": len(runtime_passes),
            "tool_result_count": len(tool_results),
            "runtime_passes": [_safe_pass_payload(item) for item in runtime_passes[:12] if isinstance(item, dict)],
            "append_events": append_events[:20],
        }
    )


def _available_runtime_facts(runtime_passes: list[dict[str, Any]], answer_slots: AnswerSlots | None) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for item in runtime_passes:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or item.get("source") or "")
        if path.upper() in {"DIRECT", "AGGREGATION_ONLY"}:
            continue
        has_zero_row_evidence = _pass_has_zero_row_evidence(item)
        if not (_pass_has_successful_evidence(item) or has_zero_row_evidence):
            continue
        entry = {
            "task_id": str(item.get("pass_id") or ""),
            "source": path,
            "scope": str(item.get("scope") or _scope_from_sources(item.get("source_results")) or ""),
            "status": str(item.get("status") or ""),
            "facts": [str(value) for value in item.get("facts", [])[:20] if value] if isinstance(item.get("facts"), list) else [],
            "row_previews": [],
            "counts": [],
            "names": [],
            "ids": [],
            "statuses": [],
            "dates": [],
        }
        for source in item.get("source_results", []) if isinstance(item.get("source_results"), list) else []:
            if not isinstance(source, dict):
                continue
            source_status = str(source.get("status") or "").upper()
            if source_status != "SUCCESS" and not _source_has_zero_row_evidence(source, item):
                continue
            result = source.get("result") if isinstance(source.get("result"), dict) else {}
            rows = _rows_from_result_payload(result)
            if rows:
                entry["row_previews"].extend(_strip_sensitive_keys(_compact_rows(rows[:10])))
                _collect_row_values(entry, rows[:10])
            row_count = result.get("row_count")
            if row_count not in (None, "", [], {}) and row_count not in entry["counts"]:
                entry["counts"].append(row_count)
            parsed = result.get("parsed_evidence") if isinstance(result.get("parsed_evidence"), dict) else {}
            _collect_parsed_values(entry, parsed)
        if answer_slots is not None and entry["scope"] == "LOCAL_SNAPSHOT":
            _merge_slot_values(entry, answer_slots)
        for key in ["row_previews", "counts", "names", "ids", "statuses", "dates", "facts"]:
            entry[key] = _dedupe_preserve_order(entry[key])
        if any(entry[key] for key in ["facts", "row_previews", "counts", "names", "ids", "statuses", "dates"]):
            facts.append(_strip_sensitive_keys(entry))
    return facts


def _compact_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compacted: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        out: dict[str, Any] = {}
        for index, (key, value) in enumerate(row.items()):
            if index >= 12:
                out["truncated_fields"] = max(0, len(row) - index)
                break
            out[str(key)] = _truncate_long_strings(value)
        compacted.append(out)
    return compacted


def _truncate_long_strings(value: Any, *, limit: int = 60) -> Any:
    if isinstance(value, str):
        return value if len(value) <= limit else value[:limit] + "...[truncated]"
    if isinstance(value, list):
        return [_truncate_long_strings(item, limit=limit) for item in value[:20]]
    if isinstance(value, dict):
        return {str(key): _truncate_long_strings(item, limit=limit) for key, item in list(value.items())[:30]}
    return value


def _failed_or_unavailable_sources(runtime_passes: list[dict[str, Any]], evidence_bus: EvidenceBus | None) -> list[dict[str, Any]]:
    failed: list[dict[str, Any]] = []
    for item in runtime_passes:
        if not isinstance(item, dict):
            continue
        pass_id = str(item.get("pass_id") or "")
        for source in item.get("source_results", []) if isinstance(item.get("source_results"), list) else []:
            if not isinstance(source, dict):
                continue
            status = str(source.get("status") or "").upper()
            if status in {"SUCCESS", "SKIPPED"}:
                continue
            failed.append(
                _strip_sensitive_keys(
                    {
                        "task_id": pass_id,
                        "source": str(source.get("source") or item.get("source") or item.get("path") or ""),
                        "scope": str(source.get("scope") or item.get("scope") or ""),
                        "status": status,
                        "error": _safe_error(source.get("error")),
                        "caveat": _source_caveat(source, item),
                    }
                )
            )
        item_status = str(item.get("status") or "").upper()
        if item_status in {"API_ERROR", "ERROR", "LIVE_EMPTY", "EMPTY", "COMPILE_ERROR", "REQUEST_ERROR", "DEPENDENCY_BLOCKED", "BUDGET_EXCEEDED"} and not any(entry.get("task_id") == pass_id for entry in failed):
            failed.append(
                _strip_sensitive_keys(
                    {
                        "task_id": pass_id,
                        "source": str(item.get("source") or item.get("path") or ""),
                        "scope": str(item.get("scope") or ""),
                        "status": item_status,
                        "error": _safe_error("; ".join(str(value) for value in item.get("caveats", []) if value) if isinstance(item.get("caveats"), list) else None),
                        "caveat": _item_caveat(item),
                    }
                )
            )
    if evidence_bus is not None:
        for error in getattr(evidence_bus, "api_errors", [])[:5]:
            failed.append({"task_id": "", "source": "API", "scope": "LIVE_API", "status": "API_ERROR", "error": _safe_error(error), "caveat": "Live API evidence was unavailable or errored for this source."})
    return _dedupe_dicts(failed)


def _task_checklist(llm_plan: LLMUnifiedPlan) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for item in llm_plan.passes:
        items.append(
            {
                "task_id": item.pass_id,
                "subtask": item.subtask,
                "path": item.path,
                "depends_on": list(item.depends_on),
                "reuse_result_from": getattr(item, "reuse_result_from", None),
                "semantic_cache_key": getattr(item, "semantic_cache_key", None),
                "result_contract": getattr(item, "result_contract", None),
                "expected_result": item.expected_result,
                "required": not bool(getattr(item, "optional", False) or getattr(item, "fallback", False)),
            }
        )
    return _strip_sensitive_keys(items)


def _required_task_ids(llm_plan: LLMUnifiedPlan) -> list[str]:
    task_ids: list[str] = []
    for item in llm_plan.passes:
        if bool(getattr(item, "optional", False) or getattr(item, "fallback", False)):
            continue
        if item.path in {"AGGREGATION_ONLY", "DIRECT"}:
            continue
        task_ids.append(str(item.pass_id))
    return task_ids


def _pass_result_checklist(runtime_passes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    checklist: list[dict[str, Any]] = []
    for item in runtime_passes:
        if not isinstance(item, dict):
            continue
        checklist.append(
            {
                "task_id": str(item.get("pass_id") or ""),
                "source": str(item.get("path") or item.get("source") or ""),
                "scope": str(item.get("scope") or ""),
                "status": str(item.get("status") or ""),
                "facts": [str(value) for value in item.get("facts", [])[:10] if value] if isinstance(item.get("facts"), list) else [],
                "caveats": [str(value) for value in item.get("caveats", [])[:8] if value] if isinstance(item.get("caveats"), list) else [],
                "depends_on": list(item.get("depends_on") or []) if isinstance(item.get("depends_on"), list) else [],
                "reuse_result_from": item.get("reuse_result_from"),
                "semantic_cache_key": item.get("semantic_cache_key"),
                "alias_materialized": item.get("alias_materialized"),
                "shared_execution_id": item.get("shared_execution_id"),
            }
        )
    return _strip_sensitive_keys(checklist)


def _required_caveats(runtime_passes: list[dict[str, Any]], evidence_bus: EvidenceBus) -> list[str]:
    caveats = _caveats_from_passes(runtime_passes)
    for error in getattr(evidence_bus, "api_errors", [])[:5]:
        caveats.append(str(error))
    return list(dict.fromkeys(str(item) for item in caveats if item))


def _final_answer_repair_context(repair_context: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(repair_context, dict):
        return None
    semantic_gate = repair_context.get("semantic_gate")
    if not isinstance(semantic_gate, dict):
        semantic_gate = repair_context.get("semantic_gate_result") if isinstance(repair_context.get("semantic_gate_result"), dict) else {}
    payload = {
        "previous_answer": repair_context.get("previous_answer") or repair_context.get("final_answer"),
        "semantic_gate_error_type": semantic_gate.get("error_type") or repair_context.get("error_type"),
        "missing_required_fields": semantic_gate.get("missing_required_fields") or repair_context.get("missing_required_fields") or [],
        "scope_errors": semantic_gate.get("scope_errors") or repair_context.get("scope_errors") or [],
        "unsupported_claims": semantic_gate.get("unsupported_claims") or repair_context.get("unsupported_claims") or [],
        "raw": compact_preview(repair_context, 1200),
    }
    return _strip_sensitive_keys(payload)


def _generate_final_answer_messages(
    client: Any,
    *,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None,
    tool_choice: dict[str, Any] | None,
    parallel_tool_calls: bool | None,
    max_tokens: int,
) -> dict[str, Any]:
    kwargs = {
        "tools": tools,
        "tool_choice": tool_choice,
        "parallel_tool_calls": parallel_tool_calls,
        "max_tokens": max_tokens,
        "temperature": 0,
    }
    try:
        return client.generate_messages(messages, **kwargs)
    except TypeError as exc:
        if "max_tokens" not in str(exc) and "temperature" not in str(exc):
            raise
        kwargs.pop("max_tokens", None)
        kwargs.pop("temperature", None)
        return client.generate_messages(messages, **kwargs)


def _strip_sensitive_keys(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _strip_sensitive_keys(item)
            for key, item in value.items()
            if str(key).lower() not in SENSITIVE_CONTEXT_KEYS
        }
    if isinstance(value, list):
        return [_strip_sensitive_keys(item) for item in value]
    return redact_secrets(value)


def _safe_error(message: str | None) -> str:
    return str(redact_secrets(message or ""))[:500]


def _caveats_from_passes(runtime_passes: list[dict[str, Any]]) -> list[str]:
    caveats: list[str] = []
    for item in runtime_passes:
        status = str(item.get("status") or "").upper()
        if status == "API_ERROR":
            caveats.append("API_ERROR")
        if status == "LIVE_EMPTY":
            caveats.append("API_LIVE_EMPTY")
        if status == "ERROR":
            caveats.append("API_ERROR" if str(item.get("source") or "").upper() == "API" else "SQL_ERROR")
        for caveat in item.get("caveats", []) if isinstance(item.get("caveats"), list) else []:
            caveats.append(str(caveat))
    return caveats


def _semantic_error_type(blocked: list[dict[str, Any]]) -> str:
    issues = " ".join(str(item.get("issue") or item.get("type") or "") for item in blocked).lower()
    if "scope" in issues or "global" in issues:
        return "scope_error"
    if "caveat" in issues or "no_data" in issues:
        return "caveat_error"
    return "unsupported_claim"


def _contradiction(final_answer: str, index: Any) -> dict[str, Any] | None:
    for claim in extract_final_answer_claims(final_answer):
        if claim.type == "STATUS" and index.statuses:
            value = _norm_status(claim.value)
            if value not in set(index.statuses):
                return {"claim": claim.to_dict(), "message": f"Status claim '{claim.value}' contradicts available status evidence."}
        if claim.type == "DATE" and index.dates:
            variants = _date_variants(claim.value)
            if not set(variants) & set(index.dates):
                return {"claim": claim.to_dict(), "message": f"Date claim '{claim.value}' contradicts available date evidence."}
    return None


def _missing_required_fields(final_answer: str, *, question: str, index: Any, slots: AnswerSlots, runtime_passes: list[dict[str, Any]] | None = None) -> list[str]:
    answer = _norm(final_answer)
    prompt = _norm(question)
    missing: list[str] = []
    runtime_passes = runtime_passes or []
    if _is_runtime_unavailable_answer(answer) and _all_required_runtime_evidence_failed(runtime_passes):
        return missing
    if _asks_count(prompt) and index.counts and not any(_value_in_answer(value, answer) for value in index.counts):
        missing.append("count")
    if _asks_date(prompt) and index.dates and not any(_date_value_in_answer(value, answer) for value in index.dates):
        missing.append("date")
    date_answer_satisfies_published_prompt = (
        _asks_date(prompt)
        and "published" in prompt
        and index.dates
        and any(_date_value_in_answer(value, answer) for value in index.dates)
    )
    if _asks_status(prompt) and not date_answer_satisfies_published_prompt and index.statuses and not any(_value_in_answer(value, answer) for value in index.statuses):
        missing.append("status")
    if _asks_list(prompt) and slots.entity_names:
        if _is_scoped_no_match_answer(answer) and _index_has_zero_count(index):
            return missing
        names = slots.entity_names[:10]
        present = [name for name in names if _norm(name) in answer]
        absent = [name for name in names if _norm(name) not in answer]
        if absent and not (
            _allows_broad_list_summary(prompt, answer, slots, present)
            or _allows_ranked_recent_summary(prompt, answer, slots, present)
        ):
            missing.append("entity_names")
    return missing


def _missing_required_pass_results(final_answer: str, *, runtime_passes: list[dict[str, Any]]) -> list[str]:
    if len(runtime_passes) <= 1:
        return []
    answer = _norm(final_answer)
    missing: list[str] = []
    dependency_only_passes = {
        str(dep)
        for item in runtime_passes
        for dep in (item.get("depends_on") if isinstance(item.get("depends_on"), list) else [])
    }
    for item in runtime_passes:
        pass_id = str(item.get("pass_id") or "").strip()
        if str(item.get("path") or item.get("source") or "").upper() == "DIRECT":
            continue
        if not pass_id or not _pass_has_successful_evidence(item):
            continue
        if pass_id in dependency_only_passes:
            continue
        facts = [str(value) for value in item.get("facts", []) if value] if isinstance(item.get("facts"), list) else []
        if facts and not any(_fact_value_in_answer(fact, answer) for fact in facts):
            missing.append(f"pass:{pass_id}")
    return missing


def _pass_has_successful_evidence(item: dict[str, Any]) -> bool:
    source_results = item.get("source_results")
    if not isinstance(source_results, list):
        return False
    return any(str(source.get("status") or "").upper() == "SUCCESS" for source in source_results if isinstance(source, dict))


def _pass_has_zero_row_evidence(item: dict[str, Any]) -> bool:
    source_results = item.get("source_results")
    if not isinstance(source_results, list):
        return False
    return any(_source_has_zero_row_evidence(source, item) for source in source_results if isinstance(source, dict))


def _source_has_zero_row_evidence(source: dict[str, Any], item: dict[str, Any]) -> bool:
    status = str(source.get("status") or item.get("status") or "").upper()
    if status not in {"EMPTY", "LIVE_EMPTY", "SUCCESS"}:
        return False
    source_name = str(source.get("source") or item.get("source") or item.get("path") or "").upper()
    scope = str(source.get("scope") or item.get("scope") or "").upper()
    if source_name == "API" or scope == "LIVE_API":
        return False
    result = source.get("result") if isinstance(source.get("result"), dict) else {}
    return result.get("row_count") == 0


def _scope_from_sources(source_results: Any) -> str:
    if not isinstance(source_results, list):
        return ""
    for source in source_results:
        if isinstance(source, dict) and source.get("scope"):
            return str(source.get("scope"))
    return ""


def _rows_from_result_payload(result: dict[str, Any]) -> list[dict[str, Any]]:
    rows = result.get("rows")
    if isinstance(rows, list):
        return [row for row in rows if isinstance(row, dict)]
    if isinstance(rows, dict) and isinstance(rows.get("items"), list):
        return [row for row in rows["items"] if isinstance(row, dict)]
    preview = result.get("result_preview")
    if isinstance(preview, list):
        return [row for row in preview if isinstance(row, dict)]
    if isinstance(preview, dict) and isinstance(preview.get("items"), list):
        return [row for row in preview["items"] if isinstance(row, dict)]
    return []


def _collect_row_values(entry: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    for row in rows:
        for key, value in row.items():
            if value in (None, "", [], {}):
                continue
            normalized = re.sub(r"[^a-z0-9_]", "", str(key).lower())
            if "count" in normalized or normalized in {"total", "row_count"}:
                entry["counts"].append(value)
            if normalized in {"name", "title", "campaignname", "campaign_name", "blueprintname", "blueprint_name"}:
                entry["names"].append(str(value))
            if normalized == "name" or normalized.endswith("name"):
                entry["names"].append(str(value))
            if normalized == "id" or normalized.endswith("id"):
                entry["ids"].append(str(value))
            if normalized in {"status", "state", "lifecyclestatus", "lifecycle_status"}:
                entry["statuses"].append(str(value))
            if "time" in normalized or "date" in normalized or normalized in {"created", "updated", "modified", "published"}:
                entry["dates"].append(str(value))


def _collect_parsed_values(entry: dict[str, Any], parsed: dict[str, Any]) -> None:
    for key, target in [("names", "names"), ("ids", "ids"), ("statuses", "statuses")]:
        values = parsed.get(key)
        if isinstance(values, list):
            entry[target].extend(str(value) for value in values[:10] if value not in (None, "", [], {}))
    counts = parsed.get("counts")
    if isinstance(counts, dict):
        entry["counts"].extend(value for value in counts.values() if value not in (None, "", [], {}))
    timestamps = parsed.get("timestamps")
    if isinstance(timestamps, dict):
        entry["dates"].extend(str(value) for value in timestamps.values() if value not in (None, "", [], {}))


def _merge_slot_values(entry: dict[str, Any], slots: AnswerSlots) -> None:
    if slots.sql_row_count not in (None, "", [], {}):
        entry["counts"].append(slots.sql_row_count)
    entry["counts"].extend(slots.counts[:10])
    entry["names"].extend(slots.entity_names[:10])
    entry["ids"].extend(slots.entity_ids[:10])
    entry["statuses"].extend(slots.statuses[:10])
    entry["dates"].extend(slots.timestamps[:10])


def _source_caveat(source: dict[str, Any], item: dict[str, Any]) -> str:
    status = str(source.get("status") or item.get("status") or "").upper()
    if status == "LIVE_EMPTY":
        return "No matching live API records were returned for this query/scope."
    if status in {"API_ERROR", "REQUEST_ERROR", "ERROR"} and str(source.get("source") or item.get("source") or "").upper() == "API":
        return "Live API evidence was unavailable or errored for this source."
    if status in {"COMPILE_ERROR", "ERROR"}:
        return "This runtime evidence source errored."
    return "This runtime evidence source was unavailable for this query/scope."


def _item_caveat(item: dict[str, Any]) -> str:
    status = str(item.get("status") or "").upper()
    if status == "LIVE_EMPTY":
        return "No matching live API records were returned for this query/scope."
    if status == "API_ERROR" or str(item.get("source") or item.get("path") or "").upper() == "API":
        return "Live API evidence was unavailable or errored for this source."
    return "This runtime evidence source was unavailable for this query/scope."


def _fallback_fact_summary(available: list[dict[str, Any]]) -> str:
    pieces: list[str] = []
    labels = {"counts": "count", "names": "name", "ids": "id", "statuses": "status", "dates": "date"}
    for item in available[:4]:
        label = "/".join(part for part in [str(item.get("task_id") or ""), str(item.get("source") or ""), str(item.get("scope") or "")] if part)
        values: list[str] = []
        counts = [value for value in item.get("counts", [])[:1]]
        names = [str(value) for value in item.get("names", [])[:3] if value]
        if counts:
            values.append(f"count: {counts[0]}")
        if names:
            values.append("examples include " + "; ".join(names))
        for key in ["ids", "statuses", "dates"]:
            for value in item.get(key, [])[:3]:
                values.append(f"{labels[key]}: {value}")
        if len(values) < 4:
            for value in item.get("facts", [])[:6]:
                fact = str(value)
                if _looks_like_raw_or_oversized_fact(fact):
                    continue
                values.append(fact)
                if len(values) >= 6:
                    break
        if values:
            pieces.append(f"{label}: {'; '.join(values[:6])}")
    return " | ".join(pieces) if pieces else "scoped runtime evidence was present"


def _looks_like_raw_or_oversized_fact(fact: str) -> bool:
    text = str(fact or "")
    if len(text) > 180:
        return True
    lowered = text.lower()
    return any(marker in lowered for marker in ['{"', '"nodetype"', '"params"', "[{", "}]"])


def _dedupe_preserve_order(values: list[Any]) -> list[Any]:
    out: list[Any] = []
    seen: set[str] = set()
    for value in values:
        marker = json.dumps(value, sort_keys=True, default=str) if isinstance(value, (dict, list)) else str(value)
        if marker in seen:
            continue
        seen.add(marker)
        out.append(value)
    return out


def _dedupe_dicts(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for value in values:
        marker = json.dumps(value, sort_keys=True, default=str)
        if marker in seen:
            continue
        seen.add(marker)
        out.append(value)
    return out


def _fact_value_in_answer(fact: str, answer: str) -> bool:
    text = str(fact)
    value = text.split(":", 1)[1] if ":" in text else text
    return _value_in_answer(value, answer)


def _scope_errors(final_answer: str, *, question: str, runtime_passes: list[dict[str, Any]], slots: AnswerSlots) -> list[str]:
    answer = _norm(final_answer)
    prompt = _norm(question)
    has_live_success = any(str(item.get("scope") or "").upper() == "LIVE_API" and str(item.get("status") or "").upper() == "SUCCESS" for item in runtime_passes)
    has_local_success = any(str(item.get("scope") or "").upper() == "LOCAL_SNAPSHOT" and str(item.get("status") or "").upper() == "SUCCESS" for item in runtime_passes)
    live_prompt = any(term in prompt for term in ["current", "live", "platform", "adobe experience platform", "aep", "api"])
    current_data_claim = ("currently" in answer or "current " in answer) and bool(
        re.search(r"\b(has|have|returned|contains|shows|includes|there are|there is|found)\b", answer)
    )
    live_answer = any(term in answer for term in ["live", "platform", "adobe experience platform", "aep"]) or current_data_claim
    if live_prompt and live_answer and has_local_success and not has_live_success and "local" not in answer:
        return ["Answer presents local snapshot evidence as live/current platform evidence."]
    if live_answer and not has_live_success and getattr(slots, "live_api_evidence_available", False) is False and "local" not in answer:
        return ["Answer claims live/current evidence without live API support."]
    return []


def _caveat_error(final_answer: str, *, runtime_passes: list[dict[str, Any]], slots: AnswerSlots) -> str | None:
    answer = _norm(final_answer)
    statuses = {str(item.get("status") or "").upper() for item in runtime_passes}
    has_api_error = "API_ERROR" in statuses or bool(slots.api_error) or _norm(slots.answer_slot_source or "") == "api_error"
    has_live_empty = "LIVE_EMPTY" in statuses or "live_empty" in _norm(slots.api_evidence_state or "")
    if has_api_error and _is_no_data_answer(answer):
        return "Answer treats API_ERROR/unavailable evidence as no-data."
    if has_live_empty and _is_global_no_data_answer(answer):
        return "Answer treats scoped LIVE_EMPTY evidence as global absence."
    return None


def _is_no_data_answer(answer: str) -> bool:
    return bool(re.search(r"\b(no data|no [a-z ]+ returned|there are no|no matching|not found|none)\b", answer))


def _is_global_no_data_answer(answer: str) -> bool:
    if not _is_no_data_answer(answer):
        return False
    scoped_terms = ["matching", "query", "scope", "for this"]
    global_terms = ["adobe experience platform", "platform", "aep", "anywhere", "global", "there are no"]
    return any(term in answer for term in global_terms) and not any(term in answer for term in scoped_terms)


def _is_scoped_no_match_answer(answer: str) -> bool:
    return _is_no_data_answer(answer) and any(term in answer for term in ["matching", "query", "scope", "for this"])


def _is_runtime_unavailable_answer(answer: str) -> bool:
    return "runtime evidence was unavailable" in answer or "live api evidence was unavailable" in answer or "api evidence was unavailable" in answer


def _all_required_runtime_evidence_failed(runtime_passes: list[dict[str, Any]]) -> bool:
    saw_runtime = False
    for item in runtime_passes:
        if not isinstance(item, dict):
            continue
        path = str(item.get("path") or item.get("source") or "").upper()
        if path in {"DIRECT", "AGGREGATION_ONLY", ""}:
            continue
        saw_runtime = True
        if _pass_has_successful_evidence(item) or _pass_has_zero_row_evidence(item):
            return False
    return saw_runtime


def _index_has_zero_count(index: Any) -> bool:
    return any(str(value) in {"0", "0.0"} for value in getattr(index, "counts", []) or [])


def _asks_count(prompt: str) -> bool:
    return bool(re.search(r"\b(how many|count|number of|total)\b", prompt))


def _asks_date(prompt: str) -> bool:
    return bool(re.search(r"\b(when|date|created|updated|published|modified)\b", prompt))


def _asks_status(prompt: str) -> bool:
    return bool(re.search(r"\b(status|state|active|inactive|failed|succeeded|published|draft)\b", prompt))


def _asks_list(prompt: str) -> bool:
    return bool(re.search(r"\b(list|show|give me|what .+ do i have|which)\b", prompt))


def _allows_broad_list_summary(prompt: str, answer: str, slots: AnswerSlots, present_names: list[str]) -> bool:
    if not present_names:
        return False
    if not re.search(r"\bwhat .+ do i have\b", prompt):
        return False
    has_count = bool(slots.counts and any(_value_in_answer(value, answer) for value in slots.counts))
    if not has_count and slots.sql_row_count not in (None, 0, ""):
        has_count = _value_in_answer(slots.sql_row_count, answer)
    if not has_count:
        return False
    sample_signal = bool(re.search(r"\b(sample|examples?|includ(?:e|es|ed|ing)|first few|first \w+)\b", answer))
    return sample_signal and len(present_names) >= min(3, len(slots.entity_names))


def _allows_ranked_recent_summary(prompt: str, answer: str, slots: AnswerSlots, present_names: list[str]) -> bool:
    if not present_names:
        return False
    if not re.search(r"\b(most recent|most recently|latest|updated most recently|recently updated)\b", prompt):
        return False
    if not re.search(r"\b(most recent|most recently|latest|updated)\b", answer):
        return False
    return bool(slots.timestamps and any(_date_value_in_answer(value, answer) for value in slots.timestamps))


def _value_in_answer(value: Any, answer: str) -> bool:
    value_text = _norm(str(value))
    if not value_text:
        return False
    if re.fullmatch(r"\d+(?:\.\d+)?", value_text):
        return bool(re.search(rf"(?<![\w.]){re.escape(value_text)}(?!\.\d)(?!\w)", answer))
    return value_text in answer


def _date_value_in_answer(value: Any, answer: str) -> bool:
    return any(_value_in_answer(variant, answer) for variant in _date_variants(value))


def _date_variants(value: Any) -> list[str]:
    text = str(value)
    variants = [_norm(text)]
    match = re.search(r"\b20\d{2}-\d{2}-\d{2}\b", text)
    if match:
        variants.append(match.group(0).lower())
    return list(dict.fromkeys(value for value in variants if value))


def _norm_status(value: Any) -> str:
    text = _norm(value)
    return {"success": "succeeded", "successful": "succeeded", "failure": "failed", "running": "active"}.get(text, text)


def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())
