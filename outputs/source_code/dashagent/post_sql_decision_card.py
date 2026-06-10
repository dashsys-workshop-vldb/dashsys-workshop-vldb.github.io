from __future__ import annotations

from typing import Any

from .endpoint_catalog import EndpointCatalog
from .planner import PlanStep
from .prompt_semantic_ir import ObjectivePromptFeatures


ROLE_KEYWORDS = {
    "id": ("id", "identifier", "audienceid", "campaignid", "schemaid"),
    "name": ("name", "title", "display"),
    "status": ("status", "state"),
    "timestamp": ("time", "date", "created", "updated", "published", "deployed"),
    "count": ("count", "total", "profiles", "member"),
    "detail": ("description", "type", "class", "version"),
}


def build_post_sql_decision_card(
    features: ObjectivePromptFeatures | dict[str, Any],
    answer_intent: str,
    sql_result: dict[str, Any] | None,
    api_steps: list[PlanStep | dict[str, Any]],
    endpoint_catalog: EndpointCatalog,
) -> dict[str, Any]:
    feature_payload = features.to_dict() if isinstance(features, ObjectivePromptFeatures) else dict(features)
    sql_state = _sql_state(feature_payload, answer_intent, sql_result or {})
    return {
        "task": "POST_SQL_API_DECISION",
        "prompt_features": _compact_feature_codes(feature_payload),
        "answer_intent": str(answer_intent or "UNKNOWN").upper(),
        "sql_state": sql_state,
        "api_candidates": [_api_candidate(step, endpoint_catalog) for step in api_steps if _is_api_step(step)][:3],
        "allowed_outputs": {"mode": ["CALL_API", "SKIP_API", "CAVEAT_ONLY"]},
    }


def _sql_state(features: dict[str, Any], answer_intent: str, result: dict[str, Any]) -> dict[str, Any]:
    ok = bool(result.get("ok", True)) and not result.get("error")
    row_count = _row_count(result)
    returned_roles = _returned_roles(result)
    required_roles = _required_roles(features, answer_intent)
    missing_roles = [role for role in required_roles if role not in returned_roles]
    direct_answer = bool(ok and row_count > 0 and not missing_roles)
    partial_answer = bool(ok and row_count > 0 and missing_roles)
    return {
        "validation": "PASS" if ok else "FAIL",
        "execution": "SUCCESS" if ok else "ERROR",
        "row_count_bucket": _row_count_bucket(row_count),
        "returned_roles": returned_roles,
        "missing_roles": missing_roles,
        "direct_answer": direct_answer,
        "partial_answer": partial_answer,
        "zero_rows": bool(ok and row_count == 0),
    }


def _api_candidate(step: PlanStep | dict[str, Any], endpoint_catalog: EndpointCatalog) -> dict[str, Any]:
    payload = step.to_dict() if isinstance(step, PlanStep) else dict(step)
    method = str(payload.get("method") or "GET").upper()
    url = str(payload.get("url") or payload.get("path") or "")
    endpoint = endpoint_catalog.match(method, url)
    endpoint_id = str(payload.get("family") or (endpoint.id if endpoint else "unknown"))
    if endpoint is not None:
        endpoint_id = endpoint.id
    path_params = list(getattr(endpoint, "path_params", []) if endpoint else [])
    requires_param = bool(path_params or "{" in url)
    return {
        "endpoint_id": endpoint_id,
        "family": str(payload.get("family") or endpoint_id),
        "method": method,
        "safe_get": method == "GET",
        "requires_path_param": requires_param,
        "live_health": "UNKNOWN",
        "can_fill_roles": _endpoint_roles(endpoint_id, url),
    }


def _compact_feature_codes(features: dict[str, Any]) -> list[str]:
    codes: list[str] = []
    for key in ("cue", "retr", "count", "fields", "status", "date", "rel", "domain", "entity", "cap", "flags"):
        values = features.get(key) or []
        if isinstance(values, list):
            codes.extend(str(value) for value in values)
    return _dedupe(codes)[:32]


def _row_count(result: dict[str, Any]) -> int:
    if isinstance(result.get("row_count"), int):
        return int(result["row_count"])
    if isinstance(result.get("rows"), list):
        return len(result["rows"])
    if isinstance(result.get("result"), list):
        return len(result["result"])
    return 0


def _returned_roles(result: dict[str, Any]) -> list[str]:
    keys: set[str] = set()
    rows = result.get("rows")
    if isinstance(rows, list) and rows and isinstance(rows[0], dict):
        keys.update(str(key).lower() for key in rows[0].keys())
    if isinstance(rows, dict) and isinstance(rows.get("items"), list) and rows.get("items") and isinstance(rows["items"][0], dict):
        keys.update(str(key).lower() for key in rows["items"][0].keys())
    if isinstance(result.get("columns"), list):
        keys.update(str(key).lower() for key in result.get("columns") or [])
    roles: list[str] = []
    for role, needles in ROLE_KEYWORDS.items():
        if any(any(needle in key for needle in needles) for key in keys):
            roles.append(role)
    if _row_count(result) == 1 and not roles:
        roles.append("detail")
    return _dedupe(roles)


def _required_roles(features: dict[str, Any], answer_intent: str) -> list[str]:
    intent = str(answer_intent or "").upper()
    fields = set(features.get("fields") or [])
    roles: list[str] = []
    if intent == "COUNT" or features.get("count"):
        roles.append("count")
    if intent in {"LIST", "DETAIL"} or features.get("retr"):
        roles.extend(["id", "name"])
    if intent == "STATUS" or fields & {"STATUS"} or features.get("status"):
        roles.append("status")
    if intent == "DATE" or features.get("date") or fields & {"CREATED_TIME", "UPDATED_TIME"}:
        roles.append("timestamp")
    if fields & {"ID"}:
        roles.append("id")
    if fields & {"NAME"}:
        roles.append("name")
    return _dedupe(roles)


def _endpoint_roles(endpoint_id: str, url: str) -> list[str]:
    text = f"{endpoint_id} {url}".lower()
    roles = ["id", "name"]
    if any(word in text for word in ("status", "run", "flow", "audit")):
        roles.append("status")
        roles.append("timestamp")
    if any(word in text for word in ("schema", "merge", "tag", "audience", "segment", "dataset", "batch")):
        roles.append("detail")
    return _dedupe(roles)


def _row_count_bucket(row_count: int) -> str:
    if row_count == 0:
        return "ZERO"
    if row_count == 1:
        return "ONE"
    if row_count > 1:
        return "MANY"
    return "UNKNOWN"


def _is_api_step(step: PlanStep | dict[str, Any]) -> bool:
    payload = step.to_dict() if isinstance(step, PlanStep) else dict(step)
    return str(payload.get("action") or "api").lower() == "api" and bool(payload.get("url") or payload.get("path"))


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out
