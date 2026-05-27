from __future__ import annotations

from typing import Any

from .endpoint_catalog import EndpointCatalog
from .planner import PlanStep
from .post_sql_decision_card import ROLE_KEYWORDS
from .prompt_semantic_ir import ObjectivePromptFeatures
from .semantic_parse import SemanticParse


def build_post_sql_semantic_decision_card(
    *,
    user_prompt: str,
    semantic_parse: SemanticParse | dict[str, Any] | None,
    features: ObjectivePromptFeatures | dict[str, Any],
    answer_intent: str,
    sql_result: dict[str, Any] | None,
    api_steps: list[PlanStep | dict[str, Any]],
    endpoint_catalog: EndpointCatalog | None,
    api_need_prior: str = "API_OPTIONAL",
) -> dict[str, Any]:
    feature_payload = features.to_dict() if isinstance(features, ObjectivePromptFeatures) else dict(features)
    parse_payload = semantic_parse.to_dict() if isinstance(semantic_parse, SemanticParse) else dict(semantic_parse or {})
    explicit_cues = _explicit_cues(feature_payload)
    sql_state = _sql_state(feature_payload, answer_intent, sql_result or {})
    candidates = [_api_candidate(step, endpoint_catalog) for step in api_steps if _is_api_step(step)]
    user_scope = "LIVE_PLATFORM" if _live_or_api_cue(explicit_cues) else "LOCAL_SNAPSHOT"
    return {
        "task": "POST_SQL_SEMANTIC_DECISION",
        "user_prompt": str(user_prompt)[:300],
        "semantic_parse": _compact_semantic_parse(parse_payload),
        "user_requested_scope": user_scope,
        "sql_result_scope": "LOCAL_SNAPSHOT",
        "sql_state": sql_state,
        "returned_roles": sql_state.get("returned_roles", []),
        "missing_roles": sql_state.get("missing_roles", []),
        "sql_facts_summary": {
            "execution": sql_state.get("execution"),
            "row_count_bucket": sql_state.get("row_count_bucket"),
            "returned_roles": sql_state.get("returned_roles", []),
            "missing_roles": sql_state.get("missing_roles", []),
            "direct_answer": sql_state.get("direct_answer"),
            "partial_answer": sql_state.get("partial_answer"),
            "zero_rows": sql_state.get("zero_rows"),
        },
        "api_candidates": candidates[:3],
        "api_need_prior": str(api_need_prior or "API_OPTIONAL").upper(),
        "explicit_cues": explicit_cues[:32],
        "constraints": {
            "api_required_cannot_skip": str(api_need_prior or "").upper() == "API_REQUIRED",
            "local_sql_does_not_imply_live_scope": True,
            "api_error_is_not_no_data": True,
            "live_empty_is_scoped_only": True,
            "do_not_invent_missing_fields": True,
        },
        "allowed_outputs": ["CALL_API", "SKIP_API", "CAVEAT_ONLY"],
        "output_schema": {
            "mode": "CALL_API|SKIP_API|CAVEAT_ONLY",
            "endpoint_id": "allowed endpoint id or null",
            "confidence": "0.0-1.0",
            "codes": ["short codes"],
        },
    }


def _compact_semantic_parse(payload: dict[str, Any]) -> dict[str, Any]:
    target = payload.get("target") if isinstance(payload.get("target"), dict) else {}
    capability = payload.get("capability") if isinstance(payload.get("capability"), dict) else {}
    return {
        "operation": payload.get("operation"),
        "target": {
            "grounding": target.get("grounding"),
            "object_family": target.get("object_family"),
            "instance_level": target.get("instance_level"),
        },
        "requested_fields": list(payload.get("requested_fields") or [])[:8],
        "capability": {
            "sql_match": bool(capability.get("sql_match")),
            "api_match": bool(capability.get("api_match")),
            "api_families": list(capability.get("api_families") or [])[:5],
        },
        "evidence_need": payload.get("evidence_need"),
        "no_tool_safe": bool(payload.get("no_tool_safe")),
        "source": payload.get("source"),
    }


def _sql_state(features: dict[str, Any], answer_intent: str, result: dict[str, Any]) -> dict[str, Any]:
    ok = bool(result.get("ok", True)) and not result.get("error")
    row_count = _row_count(result)
    returned_roles = _returned_roles(result)
    required_roles = _required_roles(features, answer_intent)
    missing_roles = [role for role in required_roles if role not in returned_roles]
    return {
        "validation": "PASS" if ok else "FAIL",
        "execution": "SUCCESS" if ok else "ERROR",
        "row_count_bucket": _row_count_bucket(row_count),
        "returned_roles": returned_roles,
        "missing_roles": missing_roles,
        "direct_answer": bool(ok and row_count > 0 and not missing_roles),
        "partial_answer": bool(ok and row_count > 0 and missing_roles),
        "zero_rows": bool(ok and row_count == 0),
    }


def _api_candidate(step: PlanStep | dict[str, Any], endpoint_catalog: EndpointCatalog | None) -> dict[str, Any]:
    payload = step.to_dict() if isinstance(step, PlanStep) else dict(step)
    method = str(payload.get("method") or "GET").upper()
    url = str(payload.get("url") or payload.get("path") or "")
    endpoint = endpoint_catalog.match(method, url) if endpoint_catalog is not None else None
    endpoint_id = str(payload.get("family") or (endpoint.id if endpoint else _infer_endpoint_id(url)))
    if endpoint is not None:
        endpoint_id = endpoint.id
    requires_path_param = bool(getattr(endpoint, "path_params", []) if endpoint else "{" in url)
    roles = _endpoint_roles(endpoint_id, url)
    return {
        "endpoint_id": endpoint_id,
        "family": endpoint_id,
        "method": method,
        "safe_get": method == "GET",
        "requires_path_param": requires_path_param,
        "can_answer_roles": roles,
        "can_fill_roles": roles,
    }


def _explicit_cues(features: dict[str, Any]) -> list[str]:
    codes: list[str] = []
    for key in ("flags", "cap", "status", "domain", "retr", "count", "fields"):
        values = features.get(key) or []
        if isinstance(values, list):
            codes.extend(str(value) for value in values)
    return _dedupe(codes)


def _live_or_api_cue(cues: list[str]) -> bool:
    return bool(set(cues) & {"LIVE", "CURRENT", "PLATFORM", "API", "EXPLICIT_API_FAMILY", "SCHEMA_REGISTRY", "FLOW_SERVICE", "TAGS", "AUDIT_EVENTS", "MERGE_POLICIES"})


def _row_count(result: dict[str, Any]) -> int:
    if isinstance(result.get("row_count"), int):
        return int(result["row_count"])
    rows = result.get("rows") if isinstance(result.get("rows"), list) else result.get("result")
    return len(rows) if isinstance(rows, list) else 0


def _returned_roles(result: dict[str, Any]) -> list[str]:
    keys: set[str] = set()
    rows = result.get("rows") if isinstance(result.get("rows"), list) else result.get("result")
    if isinstance(rows, list) and rows and isinstance(rows[0], dict):
        keys.update(str(key).lower() for key in rows[0].keys())
    if isinstance(result.get("columns"), list):
        keys.update(str(key).lower() for key in result.get("columns") or [])
    roles: list[str] = []
    for role, needles in ROLE_KEYWORDS.items():
        if any(any(needle in key for needle in needles) for key in keys):
            roles.append(role)
    return _dedupe(roles)


def _required_roles(features: dict[str, Any], answer_intent: str) -> list[str]:
    intent = str(answer_intent or "").upper()
    roles: list[str] = []
    fields = set(features.get("fields") or [])
    if intent == "COUNT" or features.get("count"):
        roles.append("count")
    if intent in {"LIST", "DETAIL"} or features.get("retr"):
        roles.extend(["id", "name"])
    if intent == "STATUS" or features.get("status") or "STATUS" in fields:
        roles.append("status")
    if intent == "DATE" or features.get("date") or fields & {"CREATED_TIME", "UPDATED_TIME"}:
        roles.append("timestamp")
    return _dedupe(roles)


def _endpoint_roles(endpoint_id: str, url: str) -> list[str]:
    text = f"{endpoint_id} {url}".lower()
    roles = ["id", "name"]
    if "count" in text or "schema" in text or "audience" in text or "segment" in text:
        roles.append("count")
    if any(word in text for word in ("status", "run", "flow", "audit")):
        roles.extend(["status", "timestamp"])
    if any(word in text for word in ("schema", "merge", "tag", "audience", "segment", "dataset", "batch")):
        roles.append("detail")
    return _dedupe(roles)


def _infer_endpoint_id(url: str) -> str:
    text = url.lower()
    if "schemaregistry" in text or "schema" in text:
        return "schema_registry_schemas"
    if "merge" in text:
        return "merge_policies"
    if "unifiedtags" in text or "tag" in text:
        return "unified_tags"
    if "audit" in text:
        return "audit_events"
    if "flowservice" in text:
        return "flowservice_flows"
    if "segment" in text:
        return "segment_definitions"
    if "audience" in text:
        return "ups_audiences"
    if "dataset" in text:
        return "catalog_datasets"
    if "batch" in text:
        return "catalog_batches"
    return "unknown"


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
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            seen.add(value)
            out.append(value)
    return out
