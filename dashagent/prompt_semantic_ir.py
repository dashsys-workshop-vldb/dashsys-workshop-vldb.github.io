from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field


FORBIDDEN_OBJECTIVE_FEATURE_FIELDS = {
    "final_route",
    "should_use_sql",
    "should_use_api",
    "should_skip_tools",
    "true_user_intent",
    "subjective_risk",
    "reason",
    "explanation",
    "route_confidence",
}


@dataclass(frozen=True)
class ObjectivePromptFeatures:
    p: str
    norm: str
    cue: list[str] = field(default_factory=list)
    retr: list[str] = field(default_factory=list)
    count: list[str] = field(default_factory=list)
    status: list[str] = field(default_factory=list)
    date: list[str] = field(default_factory=list)
    fields: list[str] = field(default_factory=list)
    rel: list[str] = field(default_factory=list)
    domain: list[str] = field(default_factory=list)
    entity: list[str] = field(default_factory=list)
    cap: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        for key in FORBIDDEN_OBJECTIVE_FEATURE_FIELDS:
            payload.pop(key, None)
        return payload


def normalize_prompt_text(prompt: str) -> str:
    text = " ".join(str(prompt or "").strip().lower().split())
    text = text.replace("_", " ").replace("-", " ")
    return re.sub(r"\s+", " ", text)


def extract_objective_prompt_features(prompt: str) -> ObjectivePromptFeatures:
    norm = normalize_prompt_text(prompt)
    cue: list[str] = []
    retr: list[str] = []
    count: list[str] = []
    status: list[str] = []
    date: list[str] = []
    fields: list[str] = []
    rel: list[str] = []
    domain: list[str] = []
    entity: list[str] = []
    flags: list[str] = []

    _add_if(cue, "DEF", _has_phrase(norm, ("what is", "what are", "define", "definition of")))
    _add_if(cue, "EXPLAIN", _has_phrase(norm, ("explain", "describe", "summarize")))
    _add_if(cue, "WHY", _has_phrase(norm, ("why",)))
    _add_if(cue, "HOW_WORKS", _has_phrase(norm, ("how does", "how do", "how works", "how is")))
    _add_if(cue, "COMPARE", _has_phrase(norm, ("compare", "difference between", "versus", " vs ")))

    _add_if(retr, "LIST", _has_phrase(norm, ("list", "all current", "current")))
    _add_if(retr, "SHOW", _has_phrase(norm, ("show",)))
    _add_if(retr, "FIND", _has_phrase(norm, ("find", "search", "lookup", "look up")))
    _add_if(retr, "EXPORT", _has_phrase(norm, ("export", "download")))
    _add_if(retr, "RETURN", _has_phrase(norm, ("return", "give me", "provide")))

    _add_if(count, "COUNT", _has_phrase(norm, ("count", "counts")))
    _add_if(count, "HOW_MANY", _has_phrase(norm, ("how many",)))
    _add_if(count, "TOTAL", _has_phrase(norm, ("total", "number of")))

    _add_if(status, "STATUS", _has_phrase(norm, ("status", "state")))
    _add_if(status, "ACTIVE", _has_word(norm, "active"))
    _add_if(status, "INACTIVE", _has_word(norm, "inactive"))
    _add_if(status, "FAILED", _has_word(norm, "failed"))
    _add_if(status, "SUCCEEDED", _has_phrase(norm, ("succeeded", "successful")))

    _add_if(date, "WHEN", _has_phrase(norm, ("when",)))
    _add_if(date, "CREATED", _has_phrase(norm, ("created", "new")))
    _add_if(date, "UPDATED", _has_phrase(norm, ("updated", "modified", "recent")))
    _add_if(date, "PUBLISHED", _has_phrase(norm, ("published", "launched", "released")))
    _add_if(date, "DEPLOYED", _has_phrase(norm, ("deployed",)))

    _add_if(fields, "ID", _has_phrase(norm, (" id", " ids", "identifier", "audience id", "schema id")))
    _add_if(fields, "NAME", _has_phrase(norm, ("name", "title", "display name")))
    _add_if(fields, "STATUS", "STATUS" in status or _has_phrase(norm, ("status", "state")))
    _add_if(fields, "CREATED_TIME", _has_phrase(norm, ("created time", "createdtime")))
    _add_if(fields, "UPDATED_TIME", _has_phrase(norm, ("updated time", "updatedtime")))
    _add_if(fields, "TOTAL_PROFILES", _has_phrase(norm, ("total profiles", "totalprofiles")))

    _add_if(rel, "CONNECTED", _has_phrase(norm, ("connected",)))
    _add_if(rel, "LINKED", _has_phrase(norm, ("linked",)))
    _add_if(rel, "MAPPED", _has_phrase(norm, ("mapped",)))
    _add_if(rel, "ASSOCIATED", _has_phrase(norm, ("associated", "related")))
    _add_if(rel, "USES", _has_phrase(norm, ("uses", "using", "used by", "use ")))

    domain.extend(_domain_codes(norm))

    if re.search(r"'[^']+'|\"[^\"]+\"", prompt or ""):
        entity.append("QUOTED")
    if re.search(r"\b[A-Za-z0-9][A-Za-z0-9_-]{7,}\b", prompt or ""):
        entity.append("ID_LIKE")
    if re.search(r"\b\d+\b", norm):
        entity.append("NUMBER")
    if re.search(r"\b\d{4}-\d{2}-\d{2}\b", norm):
        entity.append("DATE_LITERAL")

    cap = _capability_codes(domain)

    if domain and any(code in cue for code in ("DEF", "EXPLAIN", "HOW_WORKS")):
        flags.append("DOMAIN_WITH_DEF_CUE")
    if cue and (retr or count):
        flags.append("MIXED_CONCEPT_AND_RETRIEVAL")
    if entity:
        flags.append("CONCRETE_ENTITY")
    if domain and not cue and not (retr or count or status or date or fields or rel):
        flags.append("DOMAIN_ONLY")

    return ObjectivePromptFeatures(
        p=str(prompt or ""),
        norm=norm,
        cue=cue,
        retr=retr,
        count=count,
        status=status,
        date=date,
        fields=fields,
        rel=rel,
        domain=domain,
        entity=_dedupe(entity),
        cap=cap,
        flags=flags,
    )


def _domain_codes(norm: str) -> list[str]:
    domain: list[str] = []
    domain_patterns = [
        ("SCHEMA", ("schema", "schemas", "blueprint", "blueprints")),
        ("SEGMENT", ("segment", "segments")),
        ("AUDIENCE", ("audience", "audiences")),
        ("DATASET", ("dataset", "datasets", "data set", "data sets", "collection", "collections")),
        ("JOURNEY", ("journey", "journeys")),
        ("CAMPAIGN", ("campaign", "campaigns")),
        ("TAG", ("tag", "tags", "category", "categories")),
        ("AUDIT", ("audit", "event", "events")),
        ("MERGE_POLICY", ("merge policy", "merge policies")),
        ("DATAFLOW", ("dataflow", "data flow", "flow", "flows", "run", "runs")),
        ("FLOW", ("dataflow", "data flow", "flow", "flows")),
        ("BATCH", ("batch", "batches")),
        ("DESTINATION", ("destination", "destinations", "target", "targets")),
        ("CONNECTOR", ("connector", "connectors", "source", "sources")),
        ("FIELD", ("field", "fields", "property", "properties")),
    ]
    for code, phrases in domain_patterns:
        if _has_phrase(norm, phrases):
            domain.append(code)
    return domain


def _capability_codes(domain: list[str]) -> list[str]:
    mapping = {
        "SCHEMA": ("SQL_SCHEMA", "API_SCHEMA_REGISTRY"),
        "SEGMENT": ("SQL_SEGMENT", "API_UPS_AUDIENCES", "API_SEGMENT_DEFINITIONS"),
        "AUDIENCE": ("SQL_SEGMENT", "API_UPS_AUDIENCES"),
        "DATASET": ("SQL_DATASET", "API_CATALOG_DATASETS"),
        "JOURNEY": ("SQL_CAMPAIGN", "API_JOURNEY"),
        "CAMPAIGN": ("SQL_CAMPAIGN", "API_JOURNEY"),
        "TAG": ("API_TAGS",),
        "AUDIT": ("API_AUDIT_EVENTS",),
        "MERGE_POLICY": ("API_MERGE_POLICIES",),
        "DATAFLOW": ("SQL_FLOW", "API_FLOW_SERVICE"),
        "FLOW": ("SQL_FLOW", "API_FLOW_SERVICE"),
        "BATCH": ("API_CATALOG_BATCHES",),
        "DESTINATION": ("SQL_TARGET", "API_FLOW_SERVICE"),
        "CONNECTOR": ("SQL_CONNECTOR", "API_FLOW_SERVICE"),
        "FIELD": ("SQL_FIELD",),
    }
    caps: list[str] = []
    for code in domain:
        caps.extend(mapping.get(code, ()))
    return _dedupe(caps)


def _has_phrase(text: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in text for phrase in phrases)


def _has_word(text: str, word: str) -> bool:
    return bool(re.search(rf"\b{re.escape(word)}\b", text))


def _add_if(values: list[str], code: str, condition: bool) -> None:
    if condition and code not in values:
        values.append(code)


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out
