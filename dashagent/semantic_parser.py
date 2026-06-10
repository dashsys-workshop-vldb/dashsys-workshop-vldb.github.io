from __future__ import annotations

import json
import re
from typing import Any

from .llm_client import get_llm_client
from .prompt_semantic_ir import ObjectivePromptFeatures, extract_objective_prompt_features
from .semantic_parse import SemanticCapability, SemanticFilters, SemanticParse, SemanticTarget


DATA_OPERATIONS = {"LIST", "COUNT", "LOOKUP", "STATUS", "DATE", "RELATIONSHIP"}
CONCEPTUAL_GROUNDINGS = {"CONCEPTUAL_OBJECT", "META_LANGUAGE", "OUT_OF_DOMAIN"}
API_FAMILY_BY_CAP = {
    "SCHEMA_REGISTRY",
    "FLOW_SERVICE",
    "TAGS",
    "AUDIT_EVENTS",
    "MERGE_POLICIES",
    "SEGMENT_DEFINITIONS",
    "UPS_AUDIENCES",
    "CATALOG_DATASETS",
    "CATALOG_BATCHES",
}
DOMAIN_TO_OBJECT = {
    "SCHEMA": "SCHEMA",
    "DATASET": "DATASET",
    "JOURNEY": "JOURNEY",
    "CAMPAIGN": "JOURNEY",
    "SEGMENT": "SEGMENT",
    "AUDIENCE": "AUDIENCE",
    "TAG": "TAG",
    "AUDIT": "AUDIT",
    "MERGE_POLICY": "MERGE_POLICY",
    "DATAFLOW": "FLOW",
    "FLOW": "FLOW",
    "BATCH": "BATCH",
}


def parse_prompt_semantics(
    prompt: str,
    features: ObjectivePromptFeatures | None = None,
    *,
    llm_client: Any | None = None,
    use_llm: bool | None = None,
) -> SemanticParse:
    features = features or extract_objective_prompt_features(prompt)
    if llm_client is None and not use_llm:
        return _fallback_parse(prompt, features)
    client = llm_client
    if client is None:
        try:
            client = get_llm_client()
        except Exception:
            return _fallback_parse(prompt, features)
    messages = _messages_for_parse(prompt, features)
    last_error: Exception | None = None
    for _attempt in range(2):
        try:
            raw = _call_client(client, messages)
            parsed = SemanticParse.from_dict(json.loads(raw) if isinstance(raw, str) else dict(raw))
            return SemanticParse.from_dict({**parsed.to_dict(), "source": "LLM"})
        except Exception as exc:
            last_error = exc
            messages = messages + [
                {
                    "role": "user",
                    "content": (
                        "Return corrected SemanticParse JSON only. "
                        "Use the fixed schema exactly and omit prose. "
                        f"Previous parse failed: {type(exc).__name__}."
                    ),
                }
            ]
    return _unknown_fallback_parse(prompt, features, "INVALID_JSON" if last_error else "LLM_FAILED")


def _messages_for_parse(prompt: str, features: ObjectivePromptFeatures) -> list[dict[str, str]]:
    schema = {
        "operation": "DEFINE|EXPLAIN|LIST|COUNT|LOOKUP|STATUS|DATE|RELATIONSHIP|COMPARE|FORMAT_REQUEST|META_LANGUAGE|UNKNOWN",
        "target": {
            "text": "short target text",
            "grounding": "SUPPORTED_DATA_OBJECT|CONCEPTUAL_OBJECT|META_LANGUAGE|OUT_OF_DOMAIN|UNKNOWN",
            "object_family": "SCHEMA|DATASET|JOURNEY|SEGMENT|AUDIENCE|TAG|AUDIT|MERGE_POLICY|FLOW|BATCH|null",
            "instance_level": "boolean",
        },
        "filters": {"status": "string|null", "date": "string|null", "entity": "string|null", "relationship": "string|null"},
        "requested_fields": "array of ID|NAME|STATUS|CREATED_TIME|UPDATED_TIME|COUNT",
        "capability": {"sql_match": "boolean", "api_match": "boolean", "api_families": "array"},
        "evidence_need": "NONE|SQL|API|SQL_API|UNKNOWN",
        "no_tool_safe": "boolean",
        "confidence": "0.0-1.0",
        "supporting_spans": "array of compact spans",
        "risk_codes": "array of short codes",
        "source": "LLM",
    }
    payload = {
        "prompt": prompt,
        "objective_features": features.to_dict(),
        "schema": schema,
        "task": (
            "Describe semantic roles only. Do not answer the user, write SQL, or produce API params. "
            "Distinguish list-as-format from data retrieval, concept terms from data objects, "
            "quoted/meta-language usage from actual requests, and instance-level lookup from concept-level explanation."
        ),
    }
    return [
        {"role": "system", "content": "Return SemanticParse JSON only. No prose."},
        {"role": "user", "content": json.dumps(payload, sort_keys=True)},
    ]


def _fallback_parse(prompt: str, features: ObjectivePromptFeatures) -> SemanticParse:
    norm = features.norm
    domains = list(features.domain)
    object_family = _object_family(domains)
    api_families = _api_families(features.cap)
    sql_match = any(str(cap).startswith("SQL_") for cap in features.cap)
    api_match = bool(api_families or any(str(cap).startswith("API_") for cap in features.cap))
    operation = _operation(features)
    supporting_spans = _supporting_spans(features)
    risk_codes: list[str] = ["DETERMINISTIC_FALLBACK"]

    meta_language = bool(features.meta_language_indicators) or _meta_language_prompt(norm, features.quoted_spans)
    explicit_do_not_query = _has_phrase(norm, ("do not query", "don't query", "without querying", "no query", "do not call"))
    conceptual_format = bool(features.format_request_terms) or _conceptual_format_request(norm)
    conceptual = bool(features.conceptual_object_terms) and not _actual_data_retrieval(norm, features)
    out_of_domain = _out_of_domain(norm, object_family)

    if meta_language:
        grounding = "META_LANGUAGE"
        evidence_need = "NONE"
        instance_level = False
        no_tool_safe = True
        risk_codes.extend(["META_LANGUAGE", "KEYWORD_DECOY_SAFE"])
        operation = "META_LANGUAGE" if _has_phrase(norm, ("in the phrase", "the word")) else "DEFINE"
    elif out_of_domain:
        grounding = "OUT_OF_DOMAIN"
        evidence_need = "NONE"
        instance_level = False
        no_tool_safe = True
        risk_codes.append("OUT_OF_DOMAIN")
        sql_match = False
        api_match = False
        api_families = []
    elif explicit_do_not_query or conceptual_format or conceptual:
        grounding = "CONCEPTUAL_OBJECT"
        evidence_need = "NONE"
        instance_level = False
        no_tool_safe = True
        if conceptual_format:
            operation = "FORMAT_REQUEST" if "LIST" in features.retr or operation == "LIST" else operation
            risk_codes.append("FORMAT_REQUEST")
        if explicit_do_not_query:
            risk_codes.append("EXPLICIT_NO_QUERY")
        risk_codes.append("CONCEPTUAL_OBJECT")
    elif object_family and _supported_data_request(features):
        grounding = "SUPPORTED_DATA_OBJECT"
        instance_level = True
        no_tool_safe = False
        evidence_need = _evidence_need(features, sql_match, api_match, object_family)
        risk_codes.append("DATA_RETRIEVAL")
    elif object_family and _api_only_safe_probe(features, api_match, sql_match):
        grounding = "SUPPORTED_DATA_OBJECT"
        instance_level = True
        no_tool_safe = False
        evidence_need = "API"
        risk_codes.append("API_ONLY_OBJECT")
    elif object_family and features.cue:
        grounding = "CONCEPTUAL_OBJECT"
        instance_level = False
        evidence_need = "NONE"
        no_tool_safe = True
        risk_codes.append("CONCEPTUAL_OBJECT")
    else:
        return _unknown_fallback_parse(prompt, features, "UNKNOWN_SEMANTIC_ROLE")

    requested_fields = _requested_fields(features, operation, conceptual_grounding=grounding in CONCEPTUAL_GROUNDINGS)
    filters = SemanticFilters(
        status=_first(features.status),
        date=_first(features.date),
        entity=_entity_filter(features),
        relationship=_first(features.rel),
    )
    if grounding in CONCEPTUAL_GROUNDINGS:
        requested_fields = []
        filters = SemanticFilters()
    target_text = _target_text(prompt, features, object_family, grounding)
    confidence = _confidence(grounding, operation, features, risk_codes)
    return SemanticParse(
        operation=operation,
        target=SemanticTarget(target_text, grounding, object_family, instance_level),
        filters=filters,
        requested_fields=requested_fields,
        capability=SemanticCapability(sql_match=sql_match, api_match=api_match, api_families=api_families),
        evidence_need=evidence_need,
        no_tool_safe=no_tool_safe,
        confidence=confidence,
        supporting_spans=supporting_spans,
        risk_codes=risk_codes,
        source="DETERMINISTIC_FALLBACK",
    )


def _unknown_fallback_parse(prompt: str, features: ObjectivePromptFeatures, code: str) -> SemanticParse:
    hard_signal = _supported_data_request(features)
    family = _object_family(features.domain)
    sql_match = any(str(cap).startswith("SQL_") for cap in features.cap)
    api_families = _api_families(features.cap)
    api_match = bool(api_families or any(str(cap).startswith("API_") for cap in features.cap))
    return SemanticParse(
        operation=_operation(features),
        target=SemanticTarget(_target_text(prompt, features, family, "UNKNOWN"), "UNKNOWN", family, hard_signal),
        filters=SemanticFilters(status=_first(features.status), date=_first(features.date), entity=_entity_filter(features), relationship=_first(features.rel)),
        requested_fields=_requested_fields(features, _operation(features), conceptual_grounding=False),
        capability=SemanticCapability(sql_match=sql_match, api_match=api_match, api_families=api_families),
        evidence_need="UNKNOWN" if not hard_signal else _evidence_need(features, sql_match, api_match, family),
        no_tool_safe=not hard_signal,
        confidence=0.45,
        supporting_spans=_supporting_spans(features),
        risk_codes=["DETERMINISTIC_FALLBACK", code],
        source="DETERMINISTIC_FALLBACK",
    )


def _operation(features: ObjectivePromptFeatures) -> str:
    if features.meta_language_indicators:
        return "META_LANGUAGE"
    if "DEF" in features.cue:
        return "DEFINE"
    if "EXPLAIN" in features.cue or "WHY" in features.cue or "HOW_WORKS" in features.cue:
        return "EXPLAIN"
    if "COMPARE" in features.cue:
        return "COMPARE"
    if features.count:
        return "COUNT"
    if features.rel:
        return "RELATIONSHIP"
    if features.date:
        return "DATE"
    if features.status and features.retr:
        return "STATUS"
    if "LIST" in features.retr:
        return "LIST"
    if features.retr:
        return "LOOKUP"
    return "UNKNOWN"


def _object_family(domains: list[str]) -> str | None:
    for domain in domains:
        mapped = DOMAIN_TO_OBJECT.get(str(domain))
        if mapped:
            return mapped
    return None


def _api_families(caps: list[str]) -> list[str]:
    out: list[str] = []
    for cap in caps:
        cap = str(cap).upper()
        if cap in API_FAMILY_BY_CAP:
            out.append(cap)
        elif cap.startswith("API_"):
            out.append(cap[4:])
    return _dedupe(out)


def _supported_data_request(features: ObjectivePromptFeatures) -> bool:
    if not features.domain:
        return False
    if features.meta_language_indicators or features.format_request_terms:
        return False
    if _has_phrase(features.norm, ("do not query", "don't query", "without querying", "no query")):
        return False
    if features.count or features.retr or features.status or features.date or features.rel:
        return True
    if features.fields and not features.cue:
        return True
    if any(flag in features.flags for flag in ("LIVE", "CURRENT", "PLATFORM", "API", "EXPLICIT_API_FAMILY")) and not features.cue:
        return True
    return False


def _actual_data_retrieval(norm: str, features: ObjectivePromptFeatures) -> bool:
    if _has_phrase(norm, ("do not query", "don't query", "without querying")):
        return False
    if features.format_request_terms or features.meta_language_indicators:
        return False
    if features.count:
        return True
    if features.retr and not features.conceptual_object_terms:
        return True
    if features.status and ("SHOW" in features.retr or "LIST" in features.retr):
        return True
    return False


def _conceptual_format_request(norm: str) -> bool:
    return bool(
        re.search(r"\blist\s+(?:\d+|one|two|three|four|five|six|several)\s+(?:reason|reasons|example|examples)\b", norm)
        or _has_phrase(norm, ("give examples", "provide examples", "explain why", "why the word", "what does"))
    )


def _meta_language_prompt(norm: str, quoted_spans: list[str]) -> bool:
    return bool(quoted_spans and _has_phrase(norm, ("what does", "what is meant", "in the phrase", "the phrase", "the word", "mean")))


def _out_of_domain(norm: str, object_family: str | None) -> bool:
    if _has_phrase(norm, ("stock price", "share price", "market cap", "price trends", "weather", "sports score")):
        return True
    return False if object_family else bool(_has_phrase(norm, ("adobe stock", "stock trends")))


def _api_only_safe_probe(features: ObjectivePromptFeatures, api_match: bool, sql_match: bool) -> bool:
    return bool(features.domain and api_match and not sql_match and not features.cue)


def _evidence_need(features: ObjectivePromptFeatures, sql_match: bool, api_match: bool, object_family: str | None) -> str:
    if "local snapshot" in features.norm:
        return "SQL" if sql_match else "UNKNOWN"
    if any(flag in features.flags for flag in ("LIVE", "CURRENT", "PLATFORM", "API", "EXPLICIT_API_FAMILY")):
        if sql_match and api_match:
            return "SQL_API"
        return "API" if api_match else "SQL"
    if object_family in {"TAG", "AUDIT", "MERGE_POLICY", "BATCH"} and api_match and not sql_match:
        return "API"
    if features.count and sql_match:
        return "SQL"
    if sql_match and api_match:
        return "SQL_API"
    if sql_match:
        return "SQL"
    if api_match:
        return "API"
    return "UNKNOWN"


def _requested_fields(features: ObjectivePromptFeatures, operation: str, *, conceptual_grounding: bool) -> list[str]:
    if conceptual_grounding:
        return []
    fields = list(features.fields)
    if operation == "COUNT":
        fields.append("COUNT")
    return _dedupe(fields)


def _supporting_spans(features: ObjectivePromptFeatures) -> list[str]:
    spans: list[str] = []
    spans.extend(features.quoted_spans)
    spans.extend(features.operation_candidate_spans[:4])
    spans.extend(features.target_candidate_spans[:4])
    return _dedupe(spans)[:10]


def _target_text(prompt: str, features: ObjectivePromptFeatures, family: str | None, grounding: str) -> str:
    if grounding == "META_LANGUAGE" and features.quoted_spans:
        return features.quoted_spans[0]
    if family:
        return family.lower().replace("_", " ")
    if features.target_candidate_spans:
        return features.target_candidate_spans[0]
    return str(prompt or "")[:80]


def _entity_filter(features: ObjectivePromptFeatures) -> str | None:
    for span in features.quoted_spans:
        return span
    return "ID_LIKE" if "ID_LIKE" in features.entity else None


def _confidence(grounding: str, operation: str, features: ObjectivePromptFeatures, risk_codes: list[str]) -> float:
    if grounding == "META_LANGUAGE":
        return 0.92
    if grounding == "CONCEPTUAL_OBJECT" and ("FORMAT_REQUEST" in risk_codes or features.cue):
        return 0.88
    if grounding == "SUPPORTED_DATA_OBJECT" and operation in DATA_OPERATIONS:
        return 0.87
    if grounding == "OUT_OF_DOMAIN":
        return 0.8
    return 0.65


def _call_client(client: Any, messages: list[dict[str, str]]) -> str:
    if hasattr(client, "complete"):
        return str(client.complete(messages))
    if hasattr(client, "chat"):
        return str(client.chat(messages))
    if hasattr(client, "complete_json"):
        return json.dumps(client.complete_json(messages), sort_keys=True)
    raise TypeError("unsupported semantic parser client")


def _first(values: list[str]) -> str | None:
    return str(values[0]).upper() if values else None


def _has_phrase(text: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in text for phrase in phrases)


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return out
