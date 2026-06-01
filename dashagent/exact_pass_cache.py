from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from .llm_unified_planner import LLMUnifiedPass


CACHEABLE_STATUSES = {"SUCCESS", "EMPTY", "LIVE_EMPTY"}


@dataclass
class ExactPassCacheEntry:
    key: str
    run_id: str
    pass_id: str
    source: str
    pass_result: dict[str, Any]
    shared_execution_id: str


class ExactPassCache:
    """Single-run exact SQL/API work cache for LLM-owned V2 passes."""

    def __init__(
        self,
        *,
        run_id: str,
        db_snapshot_version: str | None = None,
        api_context_version: str | None = None,
    ) -> None:
        self.run_id = run_id
        self.db_snapshot_version = db_snapshot_version or "unknown_db_snapshot"
        self.api_context_version = api_context_version or "unknown_api_context"
        self._entries: dict[str, ExactPassCacheEntry] = {}

    def key_for(self, pass_spec: LLMUnifiedPass, source: str) -> str | None:
        normalized_source = source.lower()
        if normalized_source == "sql" and pass_spec.sql is not None:
            return _stable_json(
                {
                    "path": "SQL",
                    "scope": "LOCAL_SNAPSHOT",
                    "sql": _normalize_sql(pass_spec.sql.query),
                    "params": pass_spec.sql.params or [],
                    "db_snapshot_version": self.db_snapshot_version,
                }
            )
        if normalized_source == "api" and pass_spec.api_request is not None:
            return _stable_json(
                {
                    "path": "API",
                    "scope": "LIVE_API",
                    "method": str(pass_spec.api_request.method or "").upper(),
                    "path_value": pass_spec.api_request.path,
                    "params": pass_spec.api_request.params or {},
                    "api_context_version": self.api_context_version,
                }
            )
        return None

    def store(self, pass_spec: LLMUnifiedPass, *, source: str, pass_result: dict[str, Any]) -> None:
        if not _cacheable(pass_result):
            return
        key = self.key_for(pass_spec, source)
        if key is None:
            return
        self._entries[key] = ExactPassCacheEntry(
            key=key,
            run_id=self.run_id,
            pass_id=pass_spec.pass_id,
            source=source.upper(),
            pass_result=copy.deepcopy(pass_result),
            shared_execution_id=str(pass_result.get("shared_execution_id") or f"shared_{uuid4().hex}"),
        )

    def lookup(self, pass_spec: LLMUnifiedPass, *, source: str, target_pass_id: str) -> dict[str, Any] | None:
        key = self.key_for(pass_spec, source)
        if key is None:
            return None
        entry = self._entries.get(key)
        if entry is None or entry.run_id != self.run_id:
            return None
        original = copy.deepcopy(entry.pass_result)
        status = str(original.get("status") or "SUCCESS").upper()
        source_results = original.get("source_results") if isinstance(original.get("source_results"), list) else []
        cached = {
            **original,
            "run_id": self.run_id,
            "pass_id": target_pass_id,
            "global_pass_id": f"{self.run_id}:{target_pass_id}",
            "attempt_id": int(original.get("attempt_id") or 0),
            "plan_version": int(original.get("plan_version") or 1),
            "status": status,
            "cache_hit": True,
            "deduped_from_pass_id": entry.pass_id,
            "shared_execution_id": entry.shared_execution_id,
            "source_results": [
                {
                    "source": "EXACT_PASS_CACHE",
                    "status": status,
                    "scope": _scope_for_source(entry.source),
                    "result": {"deduped_from_pass_id": entry.pass_id, "source_results": source_results},
                    "error": None,
                    "gate_passed": True,
                    "repair_attempts": 0,
                }
            ],
        }
        return cached


def _cacheable(pass_result: dict[str, Any]) -> bool:
    status = str(pass_result.get("status") or "").upper()
    if status not in CACHEABLE_STATUSES:
        return False
    source_results = pass_result.get("source_results")
    if isinstance(source_results, list):
        for item in source_results:
            if isinstance(item, dict) and str(item.get("status") or "").upper() in {"API_ERROR", "COMPILE_ERROR", "REQUEST_ERROR", "ERROR", "TIMEOUT"}:
                return False
    return True


def _normalize_sql(sql: str) -> str:
    return re.sub(r"\s+", " ", str(sql or "").strip())


def _scope_for_source(source: str) -> str:
    return "LIVE_API" if source.upper() == "API" else "LOCAL_SNAPSHOT"


def _stable_json(value: dict[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
