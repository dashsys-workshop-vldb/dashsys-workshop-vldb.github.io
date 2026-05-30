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
from .llm_unified_planner import LLMUnifiedPlan
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
        "runtime_passes": [_safe_pass_payload(item) for item in runtime_passes],
        "result_bundle": result_bundle.to_dict() if result_bundle is not None else None,
        "evidence_bus": evidence_bus.compact(),
        "answer_slots": answer_slots.compact(),
        "evidence_quality": compact_preview(evidence_quality or {}, 1800),
        "aggregation_instruction": aggregation_instruction or llm_plan.aggregation_instruction,
        "repair_context": compact_preview(repair_context, 1800) if repair_context else None,
        "scope_labels": ["LOCAL_SNAPSHOT", "LIVE_API", "API_ERROR", "LIVE_EMPTY"],
        "constraints": [
            "Generate the final answer using only runtime evidence in this card.",
            "Do not claim live/current/platform state unless LIVE_API evidence supports it.",
            "Do not turn API_ERROR into no-data.",
            "Do not turn LIVE_EMPTY into global absence.",
            "Include required information from evidence when the user explicitly asked for it.",
            "For multi-pass plans, answer all requested parts using the relevant pass results.",
            "Extra context or explanation is allowed only when semantically correct and evidence-safe.",
            "Do not optimize for hidden eval, gold answer wording, or scorer-specific phrasing.",
        ],
        "hidden_eval_gold_used": False,
        "deterministic_answer_template_used": False,
    }
    return _strip_sensitive_keys(card)


def compose_llm_final_answer(
    *,
    card: dict[str, Any],
    repair_context: dict[str, Any] | None = None,
    max_tokens: int = 700,
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
    system_prompt = (
        "You are the sole final-answer composer for DASHSys V2. "
        "Return ONLY valid JSON with keys final_answer, used_pass_ids, claimed_facts, caveats_included. "
        "Use only runtime evidence provided in the card. "
        "Do not use hidden eval or gold-answer wording. "
        "Do not invent counts, dates, statuses, entity names, IDs, relationships, live state, or API success. "
        "Do not call tools. Do not include markdown."
    )
    payload = dict(card)
    if repair_context:
        payload["repair_context"] = compact_preview(repair_context, 1800)
    result = client.generate(system_prompt, json.dumps(payload, sort_keys=True, default=str))
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
    candidate = parse_llm_final_answer_response(str(result.get("content") or ""))
    candidate.provider = provider
    candidate.model = model
    return candidate


def parse_llm_final_answer_response(raw_content: str) -> LLMFinalAnswerCandidate:
    text = str(raw_content or "").strip()
    try:
        parsed = json.loads(_strip_json_text(text))
    except Exception as exc:
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

    missing = _missing_required_fields(final_answer, question=question, index=index, slots=slots)
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


def safe_llm_final_answer_fallback(runtime_passes: list[dict[str, Any]], *, syntax_gate: FinalAnswerSyntaxGateResult | None = None, semantic_gate: FinalAnswerSemanticGateResult | None = None) -> str:
    statuses = {str(item.get("status") or "").upper() for item in runtime_passes}
    if statuses & {"API_ERROR", "ERROR"}:
        return "Runtime evidence was unavailable or failed; cannot provide a verified answer."
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


def _safe_pass_payload(item: dict[str, Any]) -> dict[str, Any]:
    return _strip_sensitive_keys(compact_preview(item, 2200))


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


def _missing_required_fields(final_answer: str, *, question: str, index: Any, slots: AnswerSlots) -> list[str]:
    answer = _norm(final_answer)
    prompt = _norm(question)
    missing: list[str] = []
    if _asks_count(prompt) and index.counts and not any(_value_in_answer(value, answer) for value in index.counts):
        missing.append("count")
    if _asks_date(prompt) and index.dates and not any(_date_value_in_answer(value, answer) for value in index.dates):
        missing.append("date")
    if _asks_status(prompt) and index.statuses and not any(_value_in_answer(value, answer) for value in index.statuses):
        missing.append("status")
    if _asks_list(prompt) and slots.entity_names:
        absent = [name for name in slots.entity_names[:10] if _norm(name) not in answer]
        if absent:
            missing.append("entity_names")
    return missing


def _missing_required_pass_results(final_answer: str, *, runtime_passes: list[dict[str, Any]]) -> list[str]:
    if len(runtime_passes) <= 1:
        return []
    answer = _norm(final_answer)
    missing: list[str] = []
    for item in runtime_passes:
        pass_id = str(item.get("pass_id") or "").strip()
        if not pass_id or not _pass_has_successful_evidence(item):
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


def _asks_count(prompt: str) -> bool:
    return bool(re.search(r"\b(how many|count|number of|total)\b", prompt))


def _asks_date(prompt: str) -> bool:
    return bool(re.search(r"\b(when|date|created|updated|published|modified)\b", prompt))


def _asks_status(prompt: str) -> bool:
    return bool(re.search(r"\b(status|state|active|inactive|failed|succeeded|published|draft)\b", prompt))


def _asks_list(prompt: str) -> bool:
    return bool(re.search(r"\b(list|show|give me|what .+ do i have|which)\b", prompt))


def _value_in_answer(value: Any, answer: str) -> bool:
    value_text = _norm(str(value))
    if not value_text:
        return False
    if re.fullmatch(r"\d+(?:\.\d+)?", value_text):
        return bool(re.search(rf"(?<![\w.]){re.escape(value_text)}(?![\w.])", answer))
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
