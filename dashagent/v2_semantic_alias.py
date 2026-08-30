from __future__ import annotations

import copy
import json
from dataclasses import asdict, dataclass, field
from typing import Any

from .trajectory import redact_secrets


@dataclass
class SemanticAliasValidationResult:
    passed: bool
    error_type: str | None = None
    task_id: str | None = None
    reuse_result_from: str | None = None
    message: str = ""
    alias_contract: dict[str, Any] | None = None
    producer_contract: dict[str, Any] | None = None
    semantic_alias_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_semantic_ir_aliases(plan: Any) -> SemanticAliasValidationResult:
    return _validate_aliases(list(getattr(plan, "tasks", []) or []), id_attr="task_id", kind_attr="kind")


def validate_unified_plan_semantic_aliases(plan: Any) -> SemanticAliasValidationResult:
    return _validate_aliases(list(getattr(plan, "passes", []) or []), id_attr="pass_id", kind_attr="path")


def materialize_semantic_alias_pass(
    alias_pass: Any,
    runtime_passes: list[dict[str, Any]],
    *,
    run_id: str | None = None,
    plan_version: int = 1,
    stage_history: list[dict[str, Any]] | None = None,
    dependency_resolution: dict[str, Any] | None = None,
) -> dict[str, Any]:
    producer_id = str(getattr(alias_pass, "reuse_result_from", None) or "").strip()
    producer = _runtime_pass_by_id(runtime_passes, producer_id)
    started_at = stage_history[0]["timestamp"] if stage_history else None
    completed_at = stage_history[-1]["timestamp"] if stage_history else None
    base = {
        "run_id": run_id,
        "pass_id": str(getattr(alias_pass, "pass_id", "") or ""),
        "global_pass_id": f"{run_id}:{getattr(alias_pass, 'pass_id', '')}" if run_id else None,
        "attempt_id": 0,
        "plan_version": plan_version,
        "subtask": str(getattr(alias_pass, "subtask", "") or ""),
        "path": "CACHE_ALIAS",
        "source": "SEMANTIC_CACHE_ALIAS",
        "can_run_parallel": bool(getattr(alias_pass, "can_run_parallel", False)),
        "depends_on": list(getattr(alias_pass, "depends_on", []) or []),
        "expected_result": str(getattr(alias_pass, "expected_result", "") or ""),
        "reuse_result_from": producer_id or None,
        "semantic_cache_key": getattr(alias_pass, "semantic_cache_key", None),
        "result_contract": _contract_to_dict(getattr(alias_pass, "result_contract", None)),
        "started_at": started_at,
        "completed_at": completed_at,
        "stage_history": list(stage_history or []),
        "dependency_resolution": dependency_resolution or {"required": False, "resolved": True, "errors": []},
        "shared_execution_id": _shared_execution_id(producer, producer_id, run_id),
    }
    if producer is None or not _producer_successful(producer):
        producer_status = str((producer or {}).get("status") or "MISSING").upper()
        caveat = f"Alias source pass {producer_id or '<missing>'} was not successful; reused evidence is unavailable for this alias."
        return {
            **base,
            "status": "ALIAS_SOURCE_FAILED",
            "scope": str((producer or {}).get("scope") or _scope_from_contract(getattr(alias_pass, "result_contract", None)) or ""),
            "alias_materialized": False,
            "alias_source_status": producer_status,
            "source_results": [
                {
                    "source": "SEMANTIC_CACHE_ALIAS",
                    "status": "ALIAS_SOURCE_FAILED",
                    "scope": str((producer or {}).get("scope") or _scope_from_contract(getattr(alias_pass, "result_contract", None)) or ""),
                    "result": {
                        "producer_pass_id": producer_id,
                        "producer_status": producer_status,
                    },
                    "error": caveat,
                }
            ],
            "facts": [],
            "caveats": [caveat],
        }
    facts = copy.deepcopy(producer.get("facts") or [])
    caveats = copy.deepcopy(producer.get("caveats") or [])
    scope = str(producer.get("scope") or _scope_from_source_results(producer.get("source_results")) or _scope_from_contract(getattr(alias_pass, "result_contract", None)) or "")
    return {
        **base,
        "status": "SUCCESS",
        "scope": scope,
        "alias_materialized": True,
        "alias_source_status": str(producer.get("status") or "SUCCESS"),
        "source_results": [
            {
                "source": "SEMANTIC_CACHE_ALIAS",
                "status": "SUCCESS",
                "scope": scope,
                "result": redact_secrets(
                    {
                        "producer_pass_id": producer_id,
                        "producer_global_pass_id": producer.get("global_pass_id"),
                        "shared_execution_id": _shared_execution_id(producer, producer_id, run_id),
                        "semantic_cache_key": getattr(alias_pass, "semantic_cache_key", None),
                        "producer_source_results": copy.deepcopy(producer.get("source_results") or []),
                    }
                ),
                "error": None,
            }
        ],
        "facts": facts,
        "caveats": caveats,
    }


def _validate_aliases(items: list[Any], *, id_attr: str, kind_attr: str) -> SemanticAliasValidationResult:
    aliases = [item for item in items if _kind(item, kind_attr) == "CACHE_ALIAS"]
    by_id = {_item_id(item, id_attr): item for item in items if _item_id(item, id_attr)}
    for alias in aliases:
        alias_id = _item_id(alias, id_attr)
        producer_id = str(getattr(alias, "reuse_result_from", None) or "").strip()
        alias_contract = _canonical_contract(getattr(alias, "result_contract", None))
        producer = by_id.get(producer_id)
        if not producer_id:
            return _alias_fail(alias, None, id_attr, "CACHE_ALIAS task must declare reuse_result_from.")
        if producer_id == alias_id:
            return _alias_fail(alias, alias, id_attr, "CACHE_ALIAS task cannot reference itself.")
        if producer is None:
            return _alias_fail(alias, None, id_attr, f"CACHE_ALIAS references unknown producer {producer_id}.")
        if producer_id not in set(str(dep) for dep in getattr(alias, "depends_on", []) or []):
            return _alias_fail(alias, producer, id_attr, "CACHE_ALIAS depends_on must include reuse_result_from so scheduling waits for the producer.")
        if getattr(alias, "local_query", None) is not None or getattr(alias, "api_query", None) is not None:
            return _alias_fail(alias, producer, id_attr, "CACHE_ALIAS must not contain local_query or api_query.")
        if getattr(alias, "sql", None) is not None or getattr(alias, "api_request", None) is not None:
            return _alias_fail(alias, producer, id_attr, "CACHE_ALIAS must not contain sql or api_request.")
        if alias_contract is None:
            return _alias_fail(alias, producer, id_attr, "CACHE_ALIAS must declare result_contract.")
        producer_contract = _resolve_producer_contract(producer, by_id, id_attr, kind_attr, seen={alias_id})
        if producer_contract is None:
            return _alias_fail(alias, producer, id_attr, "Producer must declare result_contract before it can be aliased.")
        if alias_contract != producer_contract:
            return _alias_fail(alias, producer, id_attr, "CACHE_ALIAS result_contract must exactly match producer result_contract after canonicalization.")
        alias_key = str(getattr(alias, "semantic_cache_key", None) or "").strip()
        producer_key = str(getattr(producer, "semantic_cache_key", None) or "").strip()
        if alias_key and producer_key and alias_key != producer_key:
            return _alias_fail(alias, producer, id_attr, "CACHE_ALIAS semantic_cache_key must match producer semantic_cache_key when both are present.")
        alias_source = _source_for_item(alias)
        producer_source = _source_for_item(producer)
        if alias_source and producer_source and alias_source != producer_source:
            return _alias_fail(alias, producer, id_attr, "CACHE_ALIAS source must match producer source.")
        alias_operation = _operation_for_item(alias)
        producer_operation = _operation_for_item(producer)
        if alias_operation and producer_operation and alias_operation != producer_operation:
            return _alias_fail(alias, producer, id_attr, "CACHE_ALIAS operation must match producer operation.")
    return SemanticAliasValidationResult(True, semantic_alias_count=len(aliases))


def _alias_fail(alias: Any, producer: Any | None, id_attr: str, message: str) -> SemanticAliasValidationResult:
    return SemanticAliasValidationResult(
        passed=False,
        error_type="invalid_semantic_alias",
        task_id=_item_id(alias, id_attr),
        reuse_result_from=str(getattr(alias, "reuse_result_from", None) or "").strip() or None,
        message=str(redact_secrets(message)),
        alias_contract=_canonical_contract(getattr(alias, "result_contract", None)),
        producer_contract=_canonical_contract(getattr(producer, "result_contract", None)) if producer is not None else None,
        semantic_alias_count=1,
    )


def _resolve_producer_contract(producer: Any, by_id: dict[str, Any], id_attr: str, kind_attr: str, *, seen: set[str]) -> dict[str, Any] | None:
    contract = _canonical_contract(getattr(producer, "result_contract", None))
    if _kind(producer, kind_attr) != "CACHE_ALIAS":
        return contract
    producer_id = _item_id(producer, id_attr)
    if producer_id in seen:
        return None
    seen.add(producer_id)
    target_id = str(getattr(producer, "reuse_result_from", None) or "").strip()
    target = by_id.get(target_id)
    if target is None:
        return None
    target_contract = _resolve_producer_contract(target, by_id, id_attr, kind_attr, seen=seen)
    if contract is not None and target_contract is not None and contract != target_contract:
        return None
    return target_contract if target_contract is not None else contract


def _canonical_contract(raw: Any) -> dict[str, Any] | None:
    contract = _contract_to_dict(raw)
    if not isinstance(contract, dict):
        return None
    filters = contract.get("filters") if isinstance(contract.get("filters"), list) else []
    return {
        "source": str(contract.get("source") or "").strip().upper(),
        "object": _nullable_text(contract.get("object")),
        "entity": _nullable_text(contract.get("entity")),
        "operation": str(contract.get("operation") or "").strip().upper(),
        "fields": sorted(str(field).strip() for field in (contract.get("fields") or []) if str(field).strip()),
        "filters": sorted((_canonical_filter(item) for item in filters), key=lambda item: json.dumps(item, sort_keys=True, default=str)),
        "scope": str(contract.get("scope") or "").strip().lower(),
        "freshness": str(contract.get("freshness") or "").strip().lower(),
    }


def _canonical_filter(raw: Any) -> dict[str, Any]:
    item = _filter_to_dict(raw)
    return {
        "field": str(item.get("field") or "").strip(),
        "op": str(item.get("op") or "").strip(),
        "value": item.get("value"),
    }


def _contract_to_dict(raw: Any) -> dict[str, Any] | None:
    if raw is None:
        return None
    if isinstance(raw, dict):
        return copy.deepcopy(raw)
    if hasattr(raw, "to_dict"):
        value = raw.to_dict()
        return copy.deepcopy(value) if isinstance(value, dict) else None
    return None


def _filter_to_dict(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return copy.deepcopy(raw)
    if hasattr(raw, "to_dict"):
        value = raw.to_dict()
        return copy.deepcopy(value) if isinstance(value, dict) else {}
    return {}


def _nullable_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _kind(item: Any, attr: str) -> str:
    return str(getattr(item, attr, "") or "").strip().upper()


def _item_id(item: Any, attr: str) -> str:
    return str(getattr(item, attr, "") or "").strip()


def _source_for_item(item: Any) -> str:
    source = str(getattr(item, "source", "") or "").strip().upper()
    if source:
        return source
    contract = _canonical_contract(getattr(item, "result_contract", None))
    return str((contract or {}).get("source") or "").strip().upper()


def _operation_for_item(item: Any) -> str:
    operation = str(getattr(item, "operation", "") or "").strip().upper()
    if operation:
        return operation
    contract = _canonical_contract(getattr(item, "result_contract", None))
    return str((contract or {}).get("operation") or "").strip().upper()


def _runtime_pass_by_id(runtime_passes: list[dict[str, Any]], pass_id: str) -> dict[str, Any] | None:
    for item in runtime_passes:
        if isinstance(item, dict) and str(item.get("pass_id") or "") == pass_id:
            return item
    return None


def _producer_successful(producer: dict[str, Any]) -> bool:
    if str(producer.get("status") or "").upper() == "SUCCESS":
        return True
    source_results = producer.get("source_results")
    if isinstance(source_results, list):
        return any(isinstance(source, dict) and str(source.get("status") or "").upper() == "SUCCESS" for source in source_results)
    return False


def _shared_execution_id(producer: dict[str, Any] | None, producer_id: str, run_id: str | None) -> str | None:
    if producer and producer.get("shared_execution_id"):
        return str(producer["shared_execution_id"])
    if producer and producer.get("global_pass_id"):
        return str(producer["global_pass_id"])
    if run_id and producer_id:
        return f"{run_id}:{producer_id}"
    return producer_id or None


def _scope_from_source_results(source_results: Any) -> str:
    if not isinstance(source_results, list):
        return ""
    for source in source_results:
        if isinstance(source, dict) and source.get("scope"):
            return str(source["scope"])
    return ""


def _scope_from_contract(contract: Any) -> str:
    canonical = _canonical_contract(contract)
    scope = str((canonical or {}).get("scope") or "")
    if scope == "local":
        return "LOCAL_SNAPSHOT"
    if scope == "live":
        return "LIVE_API"
    if scope == "both":
        return "BOTH"
    if scope == "concept":
        return "NO_EVIDENCE"
    return ""
