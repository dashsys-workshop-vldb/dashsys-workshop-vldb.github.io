from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .answer_intent import AnswerIntent, classify_answer_intent
from .answer_templates import classify_answer_family, human_date, human_datetime, join_human
from .live_response_parsers import normalize_api_evidence


SECRET_PARAM_KEYS = {
    "access_token",
    "authorization",
    "client_id",
    "client_secret",
    "ims_org",
    "imsorg",
    "key",
    "password",
    "secret",
    "token",
}


@dataclass(frozen=True)
class AnswerShapeCandidate:
    answer_shape: str
    text: str
    supported: bool
    unavailable_fields: tuple[str, ...]
    source_evidence: tuple[str, ...]
    diagnostic_only: bool = True
    packaged_execution_changed: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "answer_shape": self.answer_shape,
            "text": self.text,
            "supported": self.supported,
            "unavailable_fields": list(self.unavailable_fields),
            "source_evidence": list(self.source_evidence),
            "diagnostic_only": self.diagnostic_only,
            "packaged_execution_changed": self.packaged_execution_changed,
        }


def propose_answer_shape_candidate(query: str, tool_results: list[dict[str, Any]]) -> AnswerShapeCandidate:
    """Build a diagnostic answer-shape candidate from recorded evidence only.

    This helper is intentionally not wired into packaged answer generation. It is
    for score075 answer-shape experiments and refuses to treat dry-run API
    previews as payload evidence.
    """

    evidence = collect_shape_evidence(query, tool_results)
    intent = classify_shape_intent(query)
    family = classify_answer_family(query)
    noun = family_noun(family)
    live_note = "Live API verification was not executed because Adobe credentials are unavailable."

    if intent == AnswerIntent.COUNT:
        count = first_count(evidence)
        if count is not None:
            return _candidate("count", f"There are {count} {plural(noun, count)} in the recorded evidence.", True, [], evidence["sources"])
        return _unavailable("count", f"The {noun} count is unavailable in dry-run mode. {live_note}", ["count"], evidence["sources"])

    if intent == AnswerIntent.LIST:
        names = evidence["names"][:8] or evidence["ids"][:8]
        if names:
            label = plural(noun, len(names))
            return _candidate("list", f"The recorded evidence lists {len(names)} {label}: {join_human(names)}.", True, [], evidence["sources"])
        return _unavailable("list", f"The requested {noun} list is unavailable in dry-run mode. {live_note}", ["items"], evidence["sources"])

    if intent == AnswerIntent.STATUS:
        status = first_nonempty(evidence["statuses"])
        subject = status_subject(evidence, status) or f"the requested {noun}"
        if status:
            return _candidate("status", f"{subject} has status/state {status} in the recorded evidence.", True, [], evidence["sources"])
        return _unavailable("status", f"The requested {noun} status is unavailable in dry-run mode. {live_note}", ["status"], evidence["sources"])

    if intent == AnswerIntent.WHEN:
        timestamp = first_nonempty(evidence["timestamps"])
        subject = first_nonempty(evidence["names"]) or first_nonempty(evidence["ids"]) or f"the requested {noun}"
        if timestamp:
            return _candidate("date", f"{subject} has recorded timestamp {human_datetime(timestamp)}.", True, [], evidence["sources"])
        dates = evidence["query_dates"]
        if len(dates) >= 2:
            return _unavailable(
                "date",
                f"Values for the requested {noun} window between {dates[0]} and {dates[-1]} are unavailable in dry-run mode. {live_note}",
                ["values"],
                evidence["sources"],
            )
        return _unavailable("date", f"The requested {noun} timestamp is unavailable in dry-run mode. {live_note}", ["timestamp"], evidence["sources"])

    detail = detail_candidate_text(noun, evidence)
    if detail:
        return _candidate("detail", detail, True, [], evidence["sources"])
    return _unavailable("detail", f"The requested {noun} details are unavailable in dry-run mode. {live_note}", ["details"], evidence["sources"])


def collect_shape_evidence(query: str, tool_results: list[dict[str, Any]]) -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "counts": [],
        "names": [],
        "ids": [],
        "statuses": [],
        "timestamps": [],
        "query_dates": re.findall(r"\b20\d{2}-\d{2}-\d{2}\b", query),
        "safe_params": {},
        "rows": [],
        "items": [],
        "sources": ["query_text"],
    }
    add_query_visible_values(query, evidence)

    for result in tool_results:
        kind = result.get("type")
        payload = result.get("payload", {})
        if kind == "sql" and payload.get("ok"):
            rows = coerce_rows(payload.get("rows"))
            evidence["sources"].append("sql_result")
            evidence["rows"].extend(rows[:5])
            for row in rows[:10]:
                collect_mapping_values(row, evidence)
            row_count = payload.get("row_count")
            if row_count is not None:
                evidence["counts"].append(row_count)
        elif kind == "api":
            step = result.get("step") or {}
            safe_params = safe_request_params(step.get("params") or payload.get("params") or {})
            if safe_params:
                evidence["safe_params"].update(safe_params)
                evidence["sources"].append("selected_endpoint_params")
                collect_mapping_values(safe_params, evidence)
            if payload.get("dry_run"):
                evidence["sources"].append("dry_run_api_no_payload")
                continue
            if payload.get("ok"):
                family = str(step.get("family") or classify_answer_family(query))
                normalized = normalize_api_evidence(family, payload)
                items = [item for item in normalized.get("items", []) if isinstance(item, dict)]
                evidence["items"].extend(items[:5])
                evidence["sources"].append("live_api_payload")
                count = normalized.get("count")
                if count is not None:
                    evidence["counts"].append(count)
                important = normalized.get("important_fields") or {}
                if isinstance(important, dict):
                    collect_mapping_values(important, evidence)
                for item in items[:10]:
                    collect_mapping_values(item, evidence)

    for key in ["counts", "names", "ids", "statuses", "timestamps", "sources"]:
        evidence[key] = dedupe_values(evidence[key])
    return evidence


def detail_candidate_text(noun: str, evidence: dict[str, Any]) -> str | None:
    subject = first_nonempty(evidence["names"]) or first_nonempty(evidence["ids"])
    parts = []
    status = first_nonempty(evidence["statuses"])
    timestamp = first_nonempty(evidence["timestamps"])
    if status:
        parts.append(f"status/state {status}")
    if timestamp:
        parts.append(f"timestamp {human_date(timestamp)}")
    if subject and parts:
        return f"The recorded evidence identifies {subject} with {', '.join(parts)}."
    if subject:
        return f"The recorded evidence identifies {subject}; additional payload fields are unavailable without live API evidence."
    return None


def status_subject(evidence: dict[str, Any], status: str | None) -> str | None:
    for name in evidence["names"]:
        if status and str(name).strip().lower() == str(status).strip().lower():
            continue
        return str(name)
    return first_nonempty(evidence["ids"])


def classify_shape_intent(query: str) -> AnswerIntent:
    lowered = query.lower()
    if any(token in lowered for token in ["when", "what time", "date", "daily", "between", "most recent", "recently", "updated"]):
        return AnswerIntent.WHEN
    if any(token in lowered for token in ["how many", "count", "number of", "total"]):
        return AnswerIntent.COUNT
    if any(token in lowered for token in ["status", "state"]):
        return AnswerIntent.STATUS
    return classify_answer_intent(query, None)


def add_query_visible_values(query: str, evidence: dict[str, Any]) -> None:
    for single, double in re.findall(r"'([^']+)'|\"([^\"]+)\"", query):
        value = (single or double).strip()
        if value:
            evidence["names"].append(value)
    for value in re.findall(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", query, flags=re.I):
        evidence["ids"].append(value)
    for value in re.findall(r"\b01[A-Z0-9]{20,}\b", query):
        evidence["ids"].append(value)
    for value in evidence["query_dates"]:
        evidence["timestamps"].append(value)


def collect_mapping_values(mapping: dict[str, Any], evidence: dict[str, Any]) -> None:
    for key, value in mapping.items():
        if value in (None, "", [], {}):
            continue
        key_norm = normalize_key(str(key))
        if isinstance(value, dict):
            collect_mapping_values(value, evidence)
            continue
        if isinstance(value, list):
            for item in value[:5]:
                if isinstance(item, dict):
                    collect_mapping_values(item, evidence)
            continue
        text = str(value)
        if key_norm in {"name", "title", "campaignname", "segmentname", "audiencename", "targetname", "collectionname", "datasetname", "blueprintname", "filename", "fileName".lower()}:
            evidence["names"].append(text)
        if key_norm.endswith("id") or key_norm in {"id", "_id", "batchid", "schemaid", "tagid", "runid", "flowid"} or looks_like_id(text):
            evidence["ids"].append(text)
        if key_norm in {"status", "state", "lifecyclestatus", "campaignstate", "processingstatus"}:
            evidence["statuses"].append(text)
        if key_norm in {"timestamp", "date", "time", "created", "createdtime", "createdat", "updated", "updatedtime", "publishedtime", "modified"} or re.match(r"20\d{2}-\d{2}-\d{2}", text):
            evidence["timestamps"].append(text)
        if (key_norm in {"count", "total", "totalcount", "rowcount", "collectioncount", "propertycount", "totalprofiles", "totalmembers"} or "count" in key_norm) and re.search(r"\d", text):
            evidence["counts"].append(value)


def safe_request_params(params: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    if not isinstance(params, dict):
        return safe
    for key, value in params.items():
        key_norm = normalize_key(str(key))
        if any(secret in key_norm for secret in SECRET_PARAM_KEYS):
            continue
        if isinstance(value, (dict, list)):
            continue
        if value in (None, ""):
            continue
        safe[str(key)] = value
    return safe


def coerce_rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [row for row in value if isinstance(row, dict)]
    if isinstance(value, dict) and isinstance(value.get("items"), list):
        return [row for row in value["items"] if isinstance(row, dict)]
    return []


def first_count(evidence: dict[str, Any]) -> Any | None:
    for count in evidence["counts"]:
        if count not in (None, ""):
            return count
    return None


def first_nonempty(values: list[Any]) -> str | None:
    for value in values:
        if value not in (None, ""):
            return str(value)
    return None


def family_noun(family: str) -> str:
    mapping = {
        "batch": "batch",
        "tags": "tag",
        "segment_jobs": "segment evaluation job",
        "segment_definitions": "segment definition",
        "merge_policy": "merge policy",
        "schema_dataset": "schema/dataset",
        "observability_metrics": "observability metric",
        "list_journeys": "journey",
        "inactive_journeys": "journey",
        "journey_published": "journey",
    }
    return mapping.get(family, family.replace("_", " "))


def plural(noun: str, count: Any) -> str:
    try:
        numeric = float(str(count).replace(",", ""))
    except ValueError:
        numeric = 2
    if numeric == 1:
        return noun
    if noun.endswith("y"):
        return noun[:-1] + "ies"
    return noun + "s"


def _candidate(shape: str, text: str, supported: bool, unavailable: list[str], sources: list[str]) -> AnswerShapeCandidate:
    return AnswerShapeCandidate(
        answer_shape=shape,
        text=text,
        supported=supported,
        unavailable_fields=tuple(unavailable),
        source_evidence=tuple(dedupe_values(sources)),
    )


def _unavailable(shape: str, text: str, unavailable: list[str], sources: list[str]) -> AnswerShapeCandidate:
    return _candidate(shape, text, False, unavailable, sources)


def normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def looks_like_id(text: str) -> bool:
    return bool(
        re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", text, flags=re.I)
        or re.fullmatch(r"01[A-Z0-9]{20,}", text)
    )


def dedupe_values(values: list[Any]) -> list[Any]:
    seen: set[str] = set()
    output: list[Any] = []
    for value in values:
        key = str(value).strip().lower()
        if key and key not in seen:
            seen.add(key)
            output.append(value)
    return output
