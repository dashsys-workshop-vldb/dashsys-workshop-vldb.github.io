from __future__ import annotations

import json
import re
from typing import Any

import pytest

from dashagent.config import ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2
from dashagent.executor import AgentExecutor
from dashagent.llm_final_answer_composer import LLMFinalAnswerCandidate
from dashagent.llm_unified_planner import LLMUnifiedPass, LLMUnifiedPlan, LLMUnifiedSQLCandidate


ROBUST_V2 = ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2


class SequencedLLMClient:
    def __init__(self, responses: list[dict]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, str]] = []
        self.last_final_answer: str | None = None

    def available(self) -> bool:
        return True

    def provider_name(self) -> str:
        return "fake_llm"

    def model_name(self) -> str:
        return "fake-model"

    def generate(self, system_prompt: str, user_prompt: str, tools=None):
        self.calls.append({"system": system_prompt, "user": user_prompt})
        if "Direct Route Challenge" in str(system_prompt):
            return {"ok": True, "provider": self.provider_name(), "model": self.model_name(), "content": "NEEDS_EVIDENCE=NO\nREASON=pure concept"}
        if "final-answer writer" in str(system_prompt):
            try:
                payload = json.loads(user_prompt)
            except Exception:
                payload = {}
            if payload.get("task_checklist") == []:
                return {
                    "ok": True,
                    "provider": self.provider_name(),
                    "model": self.model_name(),
                    "content": "A schema defines the structure and meaning of data fields.",
                }
            if self.last_final_answer:
                return {
                    "ok": True,
                    "provider": self.provider_name(),
                    "model": self.model_name(),
                    "content": self.last_final_answer,
                }
            return {
                "ok": True,
                "provider": self.provider_name(),
                "model": self.model_name(),
                "content": "Runtime evidence was collected.",
            }
        if not self.responses:
            raise AssertionError("Fake LLM called more times than expected")
        payload = self.responses.pop(0)
        if isinstance(payload, dict) and payload.get("final_answer"):
            self.last_final_answer = str(payload.get("final_answer") or "")
        return {
            "ok": True,
            "provider": self.provider_name(),
            "model": self.model_name(),
            "content": json.dumps(payload),
        }

    def generate_messages(self, messages, tools=None, tool_choice=None, parallel_tool_calls=None, **kwargs):
        system_prompt = messages[0]["content"]
        user_prompt = messages[-1]["content"]
        self.calls.append({"system": system_prompt, "user": user_prompt})
        tool_names = {
            str(((tool.get("function") or {}).get("name")) or "")
            for tool in (tools or [])
            if isinstance(tool, dict)
        }
        if "submit_final_answer" in tool_names:
            if not self.responses:
                raise AssertionError("Fake LLM called more times than expected")
            payload = self.responses.pop(0)
            self.last_final_answer = str(payload.get("final_answer") or "")
            return _tool_response("submit_final_answer", payload)
        if "submit_semantic_ir_plan" in tool_names:
            if not self.responses:
                raise AssertionError("Fake LLM called more times than expected")
            payload = _legacy_unified_fixture_to_semantic_ir(self.responses.pop(0))
            return _tool_response("submit_semantic_ir_plan", payload)
        return self.generate(system_prompt, user_prompt, tools=tools)


class RecordingAPIClient:
    dry_run = False

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict]] = []

    def call_api(self, method, url, params=None, headers=None):
        self.calls.append((method, url, dict(params or {})))
        return {
            "ok": True,
            "dry_run": False,
            "status_code": 200,
            "parsed_evidence": {
                "evidence_state": "live_success",
                "live_evidence_available": True,
                "usable_evidence": True,
                "names": ["Birthday Message"],
                "counts": {"items": 1},
            },
            "result_preview": {"items": [{"id": "journey-1", "name": "Birthday Message"}]},
        }


def _install_fake_planner(monkeypatch: pytest.MonkeyPatch, responses: list[dict]) -> SequencedLLMClient:
    client = SequencedLLMClient(responses)
    monkeypatch.setattr("dashagent.llm_unified_planner.get_llm_client", lambda: client)
    monkeypatch.setattr("dashagent.llm_final_answer_composer.get_llm_client", lambda: client)
    return client


def _tool_response(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": True,
        "provider": "fake_llm",
        "model": "fake-model",
        "content": "",
        "tool_calls": [{"id": "call_1", "name": tool_name, "arguments": arguments}],
        "finish_reason": "tool_calls",
    }


def _legacy_unified_fixture_to_semantic_ir(payload: dict[str, Any]) -> dict[str, Any]:
    if "tasks" in payload and str(payload.get("route") or "").upper() in {"DIRECT", "EVIDENCE"}:
        return payload
    if "final_answer" in payload:
        return payload
    route = str(payload.get("route") or "").upper()
    if route == "LLM_DIRECT":
        return {
            "route": "DIRECT",
            "direct_answer": payload.get("direct_answer"),
            "tasks": [],
            "answer_contract": None,
            "aggregation_instruction": payload.get("aggregation_instruction") or payload.get("reason") or "",
        }
    tasks: list[dict[str, Any]] = []
    passes = payload.get("passes") if isinstance(payload.get("passes"), list) else None
    if passes is None:
        top_pass: dict[str, Any] = {
            "pass_id": "sql_1" if payload.get("sql") else "api_1",
            "subtask": payload.get("reason") or "runtime evidence",
            "depends_on": [],
            "sql": payload.get("sql"),
            "api_request": payload.get("api_request"),
        }
        passes = [] if not (top_pass.get("sql") or top_pass.get("api_request")) else [top_pass]
    for index, item in enumerate(passes, start=1):
        if not isinstance(item, dict):
            continue
        tasks.append(_legacy_pass_fixture_to_semantic_task(item, index))
    return {
        "route": "EVIDENCE",
        "direct_answer": None,
        "tasks": tasks,
        "answer_contract": _answer_contract_for_tasks(tasks),
        "aggregation_instruction": payload.get("aggregation_instruction") or payload.get("reason") or "",
    }


def _legacy_pass_fixture_to_semantic_task(item: dict[str, Any], index: int) -> dict[str, Any]:
    task_id = str(item.get("pass_id") or f"t{index}")
    sql = item.get("sql") if isinstance(item.get("sql"), dict) else None
    api = item.get("api_request") if isinstance(item.get("api_request"), dict) else None
    if str(item.get("path") or "").upper() == "DIRECT":
        return {
            "task_id": task_id,
            "kind": "CONCEPT",
            "operation": "EXPLAIN",
            "source": "NONE",
            "local_query": None,
            "api_query": None,
            "depends_on": list(item.get("depends_on") or []),
            "description": item.get("subtask") or "concept task",
            "required": bool(item.get("required", True)),
        }
    task: dict[str, Any] = {
        "task_id": task_id,
        "kind": "LOCAL_QUERY" if sql else "LIVE_QUERY",
        "operation": _operation_from_sql_or_api(sql, api),
        "source": "LOCAL_SNAPSHOT" if sql else "LIVE_API",
        "local_query": _local_query_from_sql_fixture(sql) if sql else None,
        "api_query": _api_query_from_request_fixture(api) if api else None,
        "depends_on": list(item.get("depends_on") or []),
        "description": item.get("subtask") or item.get("expected_result") or task_id,
        "required": bool(item.get("required", True)),
    }
    if sql and api:
        task["kind"] = "LOCAL_AND_LIVE"
        task["source"] = "BOTH"
    return task


def _operation_from_sql_or_api(sql: dict[str, Any] | None, api: dict[str, Any] | None) -> str:
    query = str((sql or {}).get("query") or "").lower()
    if "count(" in query:
        return "COUNT"
    if "status" in query:
        return "STATUS"
    if "published" in query or "created" in query or "updated" in query or "deployed" in query:
        return "DATE"
    if api is not None:
        return "LIST"
    return "LIST"


def _local_query_from_sql_fixture(sql: dict[str, Any]) -> dict[str, Any]:
    query = str(sql.get("query") or "")
    params = list(sql.get("params") or [])
    table_match = re.search(r"\bfrom\s+\"?([A-Za-z_][A-Za-z0-9_]*)\"?", query, flags=re.IGNORECASE)
    table = table_match.group(1) if table_match else "dim_campaign"
    select_match = re.search(r"\bselect\s+(.*?)\s+\bfrom\b", query, flags=re.IGNORECASE | re.DOTALL)
    select_text = select_match.group(1) if select_match else "*"
    count = bool(re.search(r"\bcount\s*\(", select_text, flags=re.IGNORECASE))
    fields: list[str] = []
    if not count and select_text.strip() != "*":
        for raw_field in select_text.split(","):
            field = re.sub(r"\s+as\s+.+$", "", raw_field.strip(), flags=re.IGNORECASE).strip().strip('"')
            if field and "(" not in field:
                fields.append(field)
    filters: list[dict[str, Any]] = []
    where_match = re.search(r"\bwhere\s+\"?([A-Za-z_][A-Za-z0-9_]*)\"?\s*=\s*\?", query, flags=re.IGNORECASE)
    if where_match:
        value = params[0] if params else None
        filters.append({"field": where_match.group(1), "op": "=", "value": value})
    limit_match = re.search(r"\blimit\s+(\d+)", query, flags=re.IGNORECASE)
    limit = int(limit_match.group(1)) if limit_match else 0
    return {"table": table, "fields": fields, "filters": filters, "limit": limit, "count": count}


def _api_query_from_request_fixture(api: dict[str, Any]) -> dict[str, Any]:
    path = str(api.get("path") or "")
    endpoint_id = "schema_registry_schemas" if path == "/data/foundation/schemaregistry/tenant/schemas" else path.strip("/") or "unknown_endpoint"
    return {
        "endpoint_id": endpoint_id,
        "method": str(api.get("method") or "GET").upper(),
        "path_params": {},
        "query_params": dict(api.get("params") or {}),
    }


def _answer_contract_for_tasks(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    slots: list[dict[str, Any]] = []
    for task in tasks:
        if task.get("kind") == "CONCEPT":
            continue
        task_id = str(task.get("task_id") or "")
        operation = str(task.get("operation") or "LIST").upper()
        local_query = task.get("local_query") if isinstance(task.get("local_query"), dict) else {}
        api_query = task.get("api_query") if isinstance(task.get("api_query"), dict) else {}
        scope = str(task.get("source") or "LOCAL_SNAPSHOT").upper()
        slot_type = "COUNT" if operation == "COUNT" else "STATUS" if operation == "STATUS" else "DATE" if operation == "DATE" else "LIST"
        required_fields = ["count"] if slot_type == "COUNT" else list(local_query.get("fields") or [])
        slots.append(
            {
                "slot_id": f"s_{task_id}",
                "type": slot_type,
                "required": bool(task.get("required", True)),
                "subject": local_query.get("table") or api_query.get("endpoint_id") or "runtime evidence",
                "source_scope": "BOTH" if scope == "BOTH" else "LIVE_API" if scope == "LIVE_API" else "LOCAL_SNAPSHOT",
                "satisfied_by_tasks": [task_id] if task_id else [],
                "required_fields": required_fields,
                "zero_rows_semantics": "EMPTY_RESULT_IS_ANSWER" if slot_type in {"COUNT", "LIST"} else "NO_MATCH",
                "if_missing": "ALLOW_PARTIAL",
            }
        )
    return {
        "required_slots": slots,
        "optional_slots": [],
        "answer_style": "COUNT_ONLY" if {slot["type"] for slot in slots} == {"COUNT"} else "CONCISE",
        "global_scope": "BOTH" if any(slot["source_scope"] == "BOTH" for slot in slots) else (slots[0]["source_scope"] if slots else "NONE"),
        "contract_version": "v1",
    }


def _checkpoint_names(result: dict) -> set[str]:
    return {checkpoint["checkpoint_id"] for checkpoint in result["checkpoints"]}


def _checkpoint_output(result: dict, checkpoint_id: str) -> dict:
    return next(
        checkpoint["output"]
        for checkpoint in result["checkpoints"]
        if checkpoint["checkpoint_id"] == checkpoint_id
    )


def _checkpoint_metrics(result: dict, checkpoint_id: str) -> dict:
    return next(
        checkpoint.get("metrics") or {}
        for checkpoint in result["checkpoints"]
        if checkpoint["checkpoint_id"] == checkpoint_id
    )


def _client_call_payloads(client: SequencedLLMClient) -> list[dict]:
    payloads = []
    for call in client.calls:
        try:
            payloads.append(json.loads(call["user"]))
        except Exception:
            continue
    return payloads


def _preview_items(value):
    if isinstance(value, dict) and "items" in value:
        return value["items"]
    return value


def _preview_groups(value):
    return [_preview_items(item) for item in _preview_items(value)]


def test_v2_llm_direct_skips_tools_evidence_and_post_evidence_answering(tiny_project, monkeypatch):
    _install_fake_planner(
        monkeypatch,
        [
            {
                "route": "LLM_DIRECT",
                "evidence_order": "NO_EVIDENCE",
                "direct_answer": "A schema defines the structure and meaning of data fields.",
                "sql": None,
                "api_request": None,
                "reason": "pure concept",
            }
        ],
    )

    result = AgentExecutor(tiny_project).run("What is a schema?", strategy=ROBUST_V2, query_id="v2_llm_direct")

    assert result["tool_results"] == []
    assert result["final_answer"] == "A schema defines the structure and meaning of data fields."
    boundary = _checkpoint_output(result, "checkpoint_evidence_pipeline_bypass")
    assert boundary["evidence_pipeline_bypassed"] is True
    assert boundary["evidence_bus_built"] is False
    assert boundary["post_evidence_answer_router_ran"] is False
    checkpoint_names = _checkpoint_names(result)
    assert "checkpoint_14_evidence_bus" not in checkpoint_names
    assert "checkpoint_15_answer_slots" not in checkpoint_names
    assert "checkpoint_broad_question_classifier" not in checkpoint_names
    assert "checkpoint_answer_intent_router" not in checkpoint_names
    assert "checkpoint_hybrid_answer_composer" not in checkpoint_names


def test_v2_valid_llm_sql_passes_compile_gate_and_executes(tiny_project, monkeypatch):
    _install_fake_planner(
        monkeypatch,
        [
            {
                "route": "EVIDENCE_PIPELINE",
                "evidence_order": "SQL_FIRST",
                "direct_answer": None,
                "sql": {"query": "SELECT COUNT(*) AS count FROM dim_campaign", "params": []},
                "api_request": None,
                "reason": "count local records",
            },
            {
                "final_answer": "There are 2 campaigns.",
                "used_pass_ids": ["sql_1"],
                "claimed_facts": [{"claim": "There are 2 campaigns.", "supporting_pass_ids": ["sql_1"]}],
                "caveats_included": [],
            },
        ],
    )

    result = AgentExecutor(tiny_project).run(
        "How many campaigns are there?",
        strategy=ROBUST_V2,
        query_id="v2_valid_sql",
    )

    assert [row["type"] for row in result["tool_results"]] == ["sql"]
    assert result["tool_results"][0]["payload"]["ok"] is True
    assert result["tool_results"][0]["payload"]["rows"] == [{"count": 2}]
    assert result["final_answer"] == "There are 2 records in the local snapshot."
    sql_gate = _checkpoint_output(result, "checkpoint_llm_owned_sql_compile_gate")
    assert sql_gate["passed"] is True
    answer_gate = _checkpoint_output(result, "checkpoint_llm_final_answer_semantic_gate")
    assert answer_gate["passed"] is False
    final_boundary = _checkpoint_output(result, "checkpoint_llm_owned_final_answer_boundary")
    assert final_boundary["answer_semantic_gate_passed"] is True
    boundary = _checkpoint_output(result, "checkpoint_evidence_pipeline_boundary")
    assert boundary["evidence_pipeline_bypassed"] is False
    assert boundary["evidence_bus_built"] is True


def test_v2_semantic_alias_materializes_without_extra_sql_or_api_call(tiny_project, monkeypatch):
    contract = {
        "source": "LOCAL_SNAPSHOT",
        "object": "journey",
        "entity": "Birthday Message",
        "operation": "STATUS",
        "fields": ["name", "status"],
        "filters": [{"field": "name", "op": "=", "value": "Birthday Message"}],
        "scope": "local",
        "freshness": "same_run",
    }
    plan = LLMUnifiedPlan(
        route="EVIDENCE_PIPELINE",
        evidence_order="MULTI_PASS",
        direct_answer=None,
        sql=None,
        api_request=None,
        passes=[
            LLMUnifiedPass(
                pass_id="local_status",
                subtask="Get local status.",
                path="SQL",
                can_run_parallel=True,
                depends_on=[],
                evidence_order="SQL_FIRST",
                sql=LLMUnifiedSQLCandidate(
                    query="SELECT name, status FROM dim_campaign WHERE name = ? LIMIT 1",
                    params=["Birthday Message"],
                ),
                api_request=None,
                expected_result="Local status.",
                semantic_cache_key="local_status:Birthday Message",
                result_contract=contract,
            ),
            LLMUnifiedPass(
                pass_id="local_status_again",
                subtask="Reuse the local status.",
                path="CACHE_ALIAS",
                can_run_parallel=False,
                depends_on=["local_status"],
                evidence_order="NO_EVIDENCE",
                sql=None,
                api_request=None,
                expected_result="Same local status.",
                reuse_result_from="local_status",
                semantic_cache_key="local_status:Birthday Message",
                result_contract=dict(contract),
            ),
        ],
        aggregation_instruction="Answer the local status once and note it is reused for the summary.",
        reason="test semantic alias",
        provider="fake",
        model="fake",
        diagnostics={"semantic_alias_validation_passed": True},
    )

    monkeypatch.setattr("dashagent.executor.run_llm_unified_planner", lambda **kwargs: plan)
    monkeypatch.setattr(
        "dashagent.executor.compose_llm_final_answer",
        lambda **kwargs: LLMFinalAnswerCandidate(
            final_answer="Birthday Message has local status draft.",
            used_pass_ids=["local_status", "local_status_again"],
            claimed_facts=[{"claim": "Birthday Message has local status draft.", "supporting_pass_ids": ["local_status", "local_status_again"]}],
            caveats_included=[],
            provider="fake",
            model="fake",
        ),
    )

    result = AgentExecutor(tiny_project).run(
        "Show the local status of Birthday Message, then use the same local status again in the final summary.",
        strategy=ROBUST_V2,
        query_id="v2_semantic_alias",
    )

    assert [row["type"] for row in result["tool_results"]] == ["sql"]
    assert result["tool_results"][0]["pass_id"] == "local_status"
    assert result["final_answer"] == "Birthday Message has local status draft."
    summary = _checkpoint_metrics(result, "checkpoint_llm_owned_generation_boundary")
    assert summary["semantic_alias_count"] == 1
    assert summary["alias_materialized_count"] == 1
    alias_event = _checkpoint_output(result, "checkpoint_semantic_alias_materialized")
    assert alias_event["semantic_alias_materialized"] is True
    assert alias_event["alias_task_id"] == "local_status_again"


def test_v2_empty_evidence_plan_triggers_pass_graph_repair_once(tiny_project, monkeypatch):
    client = _install_fake_planner(
        monkeypatch,
        [
            {
                "route": "EVIDENCE_PIPELINE",
                "evidence_order": "SQL_FIRST",
                "direct_answer": None,
                "passes": [],
                "reason": "invalid empty evidence plan",
            },
            {
                "route": "EVIDENCE_PIPELINE",
                "evidence_order": "SQL_FIRST",
                "direct_answer": None,
                "passes": [
                    {
                        "pass_id": "count_campaigns",
                        "subtask": "Count campaigns.",
                        "path": "SQL",
                        "can_run_parallel": True,
                        "depends_on": [],
                        "sql": {"query": "SELECT COUNT(*) AS count FROM dim_campaign", "params": []},
                    }
                ],
                "reason": "repaired graph with executable evidence pass",
            },
            {
                "final_answer": "There are 2 campaigns.",
                "used_pass_ids": ["count_campaigns"],
                "claimed_facts": [{"claim": "There are 2 campaigns.", "supporting_pass_ids": ["count_campaigns"]}],
                "caveats_included": [],
            },
        ],
    )

    result = AgentExecutor(tiny_project).run(
        "How many campaigns are there?",
        strategy=ROBUST_V2,
        query_id="v2_empty_graph_repair",
    )

    assert [row["pass_id"] for row in result["tool_results"]] == ["count_campaigns"]
    assert result["tool_results"][0]["payload"]["rows"] == [{"count": 2}]
    summary = _checkpoint_output(result, "checkpoint_llm_owned_generation_boundary")
    assert summary["pass_graph_repair_attempted"] is True
    assert summary["pass_graph_repair_success"] is True
    assert summary["pass_graph_gate_error_type"] == "empty_evidence_plan"
    assert summary["repaired_pass_count"] == 1
    repair_payload = next(payload for payload in _client_call_payloads(client) if isinstance(payload.get("repair_context"), dict))
    assert repair_payload["repair_context"]["failed_component"] == "pass_graph_gate"
    assert repair_payload["repair_context"]["graph_gate_error_type"] == "empty_evidence_plan"


def test_v2_second_invalid_pass_graph_fails_safely_without_backend_created_passes(tiny_project, monkeypatch):
    client = _install_fake_planner(
        monkeypatch,
        [
            {
                "route": "EVIDENCE_PIPELINE",
                "evidence_order": "SQL_FIRST",
                "direct_answer": None,
                "passes": [],
                "reason": "invalid empty evidence plan",
            },
            {
                "route": "EVIDENCE_PIPELINE",
                "evidence_order": "MULTI_PASS",
                "direct_answer": None,
                "passes": [
                    {
                        "pass_id": "concept_only",
                        "subtask": "Explain the concept only.",
                        "path": "DIRECT",
                        "can_run_parallel": True,
                        "depends_on": [],
                        "evidence_order": "NO_EVIDENCE",
                    }
                ],
                "reason": "still invalid because no executable evidence pass",
            },
            {
                "final_answer": "Runtime evidence could not be collected because the pass graph was invalid.",
                "used_pass_ids": ["pass_graph_gate"],
                "claimed_facts": [],
                "caveats_included": ["invalid pass graph"],
            },
        ],
    )

    result = AgentExecutor(tiny_project).run(
        "How many campaigns are there?",
        strategy=ROBUST_V2,
        query_id="v2_second_bad_graph",
    )

    assert result["tool_results"] == []
    summary = _checkpoint_output(result, "checkpoint_llm_owned_generation_boundary")
    assert summary["pass_graph_repair_attempted"] is True
    assert summary["pass_graph_repair_success"] is False
    assert summary["pass_results_count"] == 1
    assert _preview_items(summary["passes_executed"]) == []
    repair_payloads = [payload for payload in _client_call_payloads(client) if isinstance(payload.get("repair_context"), dict)]
    assert len(repair_payloads) == 1


def test_v2_planner_timeout_empty_plan_skips_pass_graph_repair(tiny_project, monkeypatch):
    planner_calls: list[dict[str, Any]] = []

    def timeout_plan(**kwargs):
        planner_calls.append(kwargs)
        return LLMUnifiedPlan(
            route="EVIDENCE_PIPELINE",
            evidence_order="SQL_FIRST",
            direct_answer=None,
            sql=None,
            api_request=None,
            passes=[],
            aggregation_instruction="",
            reason="semantic_ir_validation_error: Request timed out.",
            provider="fake_llm",
            model="fake-model",
            parse_error=True,
            diagnostics={
                "planner_timeout": True,
                "planner_retry_used": True,
                "semantic_ir_validation_error_type": "missing_tool_call",
                "semantic_ir_repair_attempted": True,
            },
        )

    monkeypatch.setattr("dashagent.executor.run_llm_unified_planner", timeout_plan)
    client = _install_fake_planner(
        monkeypatch,
        [
            {
                "final_answer": "Runtime evidence was unavailable; cannot provide a verified answer.",
                "used_pass_ids": ["pass_graph_gate"],
                "claimed_facts": [],
                "caveats_included": ["planner timeout"],
            }
        ],
    )

    result = AgentExecutor(tiny_project).run(
        "Compare local and live status of Birthday Message if both are available.",
        strategy=ROBUST_V2,
        query_id="v2_planner_timeout_empty_plan",
    )

    assert len(planner_calls) == 1
    assert not any(isinstance(payload.get("repair_context"), dict) for payload in _client_call_payloads(client))
    summary = _checkpoint_output(result, "checkpoint_llm_owned_generation_boundary")
    assert summary["pass_graph_repair_attempted"] is False
    assert summary["pass_graph_repair_skipped_reason"] == "planner_timeout_or_missing_toolcall"
    assert summary["pass_results_count"] == 1
    assert result["tool_results"] == []


def test_v2_failed_sql_compile_error_is_returned_to_llm_repair_loop(tiny_project, monkeypatch):
    _install_fake_planner(
        monkeypatch,
        [
            {
                "route": "EVIDENCE_PIPELINE",
                "evidence_order": "SQL_FIRST",
                "direct_answer": None,
                "sql": {"query": "SELECT campaign_name FROM dim_campaign", "params": []},
                "api_request": None,
                "reason": "first attempt",
            },
            {
                "route": "EVIDENCE_PIPELINE",
                "evidence_order": "SQL_FIRST",
                "direct_answer": None,
                "sql": {"query": "SELECT name FROM dim_campaign ORDER BY campaign_id", "params": []},
                "api_request": None,
                "reason": "repair unknown column",
            },
            {
                "final_answer": "Campaigns: Birthday Message; Welcome Journey.",
                "used_pass_ids": ["sql_1"],
                "claimed_facts": [{"claim": "Birthday Message and Welcome Journey were returned.", "supporting_pass_ids": ["sql_1"]}],
                "caveats_included": [],
            },
        ],
    )

    result = AgentExecutor(tiny_project).run("Show campaigns.", strategy=ROBUST_V2, query_id="v2_sql_repair")

    assert result["tool_results"][0]["payload"]["ok"] is True
    assert result["tool_results"][0]["payload"]["rows"][0]["name"] == "Birthday Message"
    first_gate = _checkpoint_output(result, "checkpoint_llm_owned_sql_compile_gate")
    assert first_gate["passed"] is True
    assert "campaign_name" not in first_gate["sql"]
    summary = _checkpoint_output(result, "checkpoint_llm_owned_generation_boundary")
    assert summary["sql_gate_passed"] is True
    assert summary["sql_repair_attempts"] == 0


def test_v2_api_request_gate_passes_safe_get_and_executes(tiny_project, monkeypatch):
    _install_fake_planner(
        monkeypatch,
        [
            {
                "route": "EVIDENCE_PIPELINE",
                "evidence_order": "API_FIRST",
                "direct_answer": None,
                "sql": None,
                "api_request": {
                    "method": "GET",
                    "path": "/data/foundation/schemaregistry/tenant/schemas",
                    "params": {"limit": 25},
                },
                "reason": "live schema list",
            },
            {
                "final_answer": "The live API returned Birthday Message.",
                "used_pass_ids": ["api_1"],
                "claimed_facts": [{"claim": "Birthday Message was returned by the live API.", "supporting_pass_ids": ["api_1"]}],
                "caveats_included": [],
            },
        ],
    )
    api_client = RecordingAPIClient()

    result = AgentExecutor(tiny_project, api_client=api_client).run(
        "List current schemas.",
        strategy=ROBUST_V2,
        query_id="v2_api_gate",
    )

    assert [row["type"] for row in result["tool_results"]] == ["api"]
    assert api_client.calls == [("GET", "/data/foundation/schemaregistry/tenant/schemas", {"limit": 25})]
    api_gate = _checkpoint_output(result, "checkpoint_llm_owned_api_request_gate")
    assert api_gate["passed"] is True


def test_v2_parallel_sql_api_passes_are_aggregated_by_llm_final_answer(tiny_project, monkeypatch):
    client = _install_fake_planner(
        monkeypatch,
        [
            {
                "route": "EVIDENCE_PIPELINE",
                "evidence_order": "MULTI_PASS",
                "direct_answer": None,
                "passes": [
                    {
                        "pass_id": "local_count",
                        "subtask": "Count local campaigns.",
                        "path": "SQL",
                        "can_run_parallel": True,
                        "depends_on": [],
                        "evidence_order": "SQL_FIRST",
                        "sql": {"query": "SELECT COUNT(*) AS count FROM dim_campaign", "params": []},
                        "api_request": None,
                    },
                    {
                        "pass_id": "live_schema_probe",
                        "subtask": "Probe live schemas.",
                        "path": "API",
                        "can_run_parallel": True,
                        "depends_on": [],
                        "evidence_order": "API_FIRST",
                        "sql": None,
                        "api_request": {
                            "method": "GET",
                            "path": "/data/foundation/schemaregistry/tenant/schemas",
                            "params": {"limit": 25},
                        },
                    },
                ],
                "aggregation_instruction": "Report both local count and live API evidence.",
                "reason": "long prompt needs local SQL and live API evidence",
            },
            {
                "final_answer": "There are 2 campaigns, and Birthday Message was returned by the live API.",
                "used_pass_ids": ["local_count", "live_schema_probe"],
                "claimed_facts": [
                    {"claim": "There are 2 campaigns.", "supporting_pass_ids": ["local_count"]},
                    {"claim": "Birthday Message was returned by the live API.", "supporting_pass_ids": ["live_schema_probe"]},
                ],
                "caveats_included": [],
            },
        ],
    )
    api_client = RecordingAPIClient()

    result = AgentExecutor(tiny_project, api_client=api_client).run(
        "For my review, count campaigns locally and verify the live schemas API result.",
        strategy=ROBUST_V2,
        query_id="v2_parallel_sql_api_answer",
    )

    assert sorted(row["type"] for row in result["tool_results"]) == ["api", "sql"]
    assert result["final_answer"]
    assert "checkpoint_llm_final_answer_composer" in _checkpoint_names(result)
    final = _checkpoint_output(result, "checkpoint_18_final_answer")
    assert final["llm_owned_final_answer"] is True
    assert final["llm_owned_final_answer"] is True
    boundary = _checkpoint_output(result, "checkpoint_llm_owned_generation_boundary")
    assert boundary["multi_pass_enabled"] is True
    assert boundary["v2_execution_optimizer_used"] is True
    assert boundary["stage_pipeline_used"] is True
    assert boundary["backend_semantic_planning_used"] is False
    assert boundary["v2_pipeline_scheduler_used"] is True
    assert boundary["pipeline_stage_count"] == 8
    assert "stage_events" in boundary
    assert boundary["llm_pass_graph_used"] is True
    assert boundary["llm_pass_count"] == 2
    assert boundary["parallel_pass_count"] == 2
    assert _preview_groups(boundary["parallel_groups"]) == [["live_schema_probe", "local_count"]]
    assert _preview_groups(boundary["dependency_edges"]) == []
    assert boundary["critical_path"]["items"] == ["live_schema_probe"]
    assert boundary["pass_graph_gate_passed"] is True
    stage_events = _preview_items(boundary["stage_events"])
    p2_gate_started = next(index for index, item in enumerate(stage_events) if item["pass_id"] == "live_schema_probe" and item["stage"] == "SQL_API_GATE" and item["event"] == "started")
    p1_final_ready = next(index for index, item in enumerate(stage_events) if item["pass_id"] == "local_count" and item["stage"] == "READY_FOR_FINAL_COMPOSITION" and item["event"] == "completed")
    assert p2_gate_started < p1_final_ready
    assert boundary["backend_semantic_decomposition_used"] is False
    composer_payload = next(payload for payload in _client_call_payloads(client) if payload.get("task") == "LLM_OWNED_FINAL_ANSWER_COMPOSITION")
    assert sorted(item["pass_id"] for item in composer_payload["runtime_passes"]) == ["live_schema_probe", "local_count"]
    assert composer_payload["aggregation_instruction"] == "Report both local count and live API evidence."


def test_v2_exact_duplicate_sql_pass_reuses_cached_pass_result(tiny_project, monkeypatch):
    client = _install_fake_planner(
        monkeypatch,
        [
            {
                "route": "EVIDENCE_PIPELINE",
                "evidence_order": "MULTI_PASS",
                "passes": [
                    {
                        "pass_id": "first_count",
                        "subtask": "Count campaigns once.",
                        "path": "SQL",
                        "can_run_parallel": True,
                        "depends_on": [],
                        "sql": {"query": "SELECT COUNT(*) AS count FROM dim_campaign", "params": []},
                    },
                    {
                        "pass_id": "duplicate_count",
                        "subtask": "Duplicate count pass declared by the LLM.",
                        "path": "SQL",
                        "can_run_parallel": True,
                        "depends_on": [],
                        "sql": {"query": "SELECT COUNT(*) AS count FROM dim_campaign", "params": []},
                    },
                ],
                "aggregation_instruction": "Use both declared pass results.",
            },
            {
                "final_answer": "There are 2 campaigns.",
                "used_pass_ids": ["first_count", "duplicate_count"],
                "claimed_facts": [{"claim": "There are 2 campaigns.", "supporting_pass_ids": ["first_count", "duplicate_count"]}],
                "caveats_included": [],
            },
        ],
    )

    result = AgentExecutor(tiny_project).run(
        "Count campaigns twice if needed.",
        strategy=ROBUST_V2,
        query_id="v2_duplicate_sql_cache",
    )

    assert [row["pass_id"] for row in result["tool_results"]] == ["first_count"]
    boundary = _checkpoint_output(result, "checkpoint_llm_owned_generation_boundary")
    assert boundary["cache_hits"] == 1
    assert boundary["deduped_passes"]["items"][0]["pass_id"] == "duplicate_count"
    result_bundle = _checkpoint_output(result, "checkpoint_result_bundle")
    runtime_passes = _preview_items(result_bundle["runtime_passes"])
    assert [item["pass_id"] for item in runtime_passes] == ["first_count", "duplicate_count"]
    assert runtime_passes[1]["cached_sources"]["items"] == ["sql"]
    composer_payload = next(payload for payload in _client_call_payloads(client) if payload.get("task") == "LLM_OWNED_FINAL_ANSWER_COMPOSITION")
    duplicate_pass = next(item for item in composer_payload["runtime_passes"] if item["pass_id"] == "duplicate_count")
    assert duplicate_pass["cached_sources"]["items"] == ["sql"]


def test_v2_dependent_pass_waits_for_declared_dependency(tiny_project, monkeypatch):
    _install_fake_planner(
        monkeypatch,
        [
            {
                "route": "EVIDENCE_PIPELINE",
                "evidence_order": "MULTI_PASS",
                "passes": [
                    {
                        "pass_id": "first",
                        "subtask": "Fetch names.",
                        "path": "SQL",
                        "can_run_parallel": False,
                        "depends_on": [],
                        "evidence_order": "SQL_FIRST",
                        "sql": {"query": "SELECT name FROM dim_campaign ORDER BY campaign_id", "params": []},
                    },
                    {
                        "pass_id": "second",
                        "subtask": "Fetch statuses after names.",
                        "path": "SQL",
                        "can_run_parallel": False,
                        "depends_on": ["first"],
                        "evidence_order": "SQL_FIRST",
                        "sql": {"query": "SELECT status FROM dim_campaign ORDER BY campaign_id", "params": []},
                    },
                ],
                "aggregation_instruction": "Answer both subtasks.",
                "reason": "dependency declared by LLM",
            },
            {
                "final_answer": "Birthday Message and Welcome Journey were returned, with statuses draft and published.",
                "used_pass_ids": ["first", "second"],
                "claimed_facts": [
                    {"claim": "Birthday Message and Welcome Journey were returned.", "supporting_pass_ids": ["first"]},
                    {"claim": "Statuses draft and published were returned.", "supporting_pass_ids": ["second"]},
                ],
                "caveats_included": [],
            },
        ],
    )

    result = AgentExecutor(tiny_project).run(
        "Fetch campaign names first, then fetch their statuses.",
        strategy=ROBUST_V2,
        query_id="v2_dependent_passes",
    )

    assert [row["pass_id"] for row in result["tool_results"]] == ["first", "second"]
    boundary = _checkpoint_output(result, "checkpoint_llm_owned_generation_boundary")
    assert boundary["pass_ids"]["items"] == ["first", "second"]
    assert _preview_groups(boundary["parallel_groups"]) == [["first"], ["second"]]
    assert _preview_groups(boundary["dependency_edges"]) == [["first", "second"]]
    assert boundary["sequential_pass_count"] == 1


def test_v2_dependent_pass_resolves_placeholder_from_dependency_result(tiny_project, monkeypatch):
    _install_fake_planner(
        monkeypatch,
        [
            {
                "route": "EVIDENCE_PIPELINE",
                "evidence_order": "MULTI_PASS",
                "passes": [
                    {
                        "pass_id": "lookup",
                        "subtask": "Lookup campaign id.",
                        "path": "SQL",
                        "can_run_parallel": False,
                        "depends_on": [],
                        "sql": {"query": "SELECT campaign_id FROM dim_campaign WHERE name = ?", "params": ["Birthday Message"]},
                    },
                    {
                        "pass_id": "details",
                        "subtask": "Fetch campaign details using the id.",
                        "path": "SQL",
                        "can_run_parallel": False,
                        "depends_on": ["lookup"],
                        "sql": {"query": "SELECT name, status FROM dim_campaign WHERE campaign_id = ?", "params": ["{{lookup.result.campaign_id}}"]},
                    },
                ],
                "aggregation_instruction": "Answer using both lookup and details.",
            },
            {
                "final_answer": "Birthday Message is draft.",
                "used_pass_ids": ["lookup", "details"],
                "claimed_facts": [{"claim": "Birthday Message is draft.", "supporting_pass_ids": ["details"]}],
                "caveats_included": [],
            },
        ],
    )

    result = AgentExecutor(tiny_project).run(
        "Find Birthday Message by id, then show its status.",
        strategy=ROBUST_V2,
        query_id="v2_placeholder_dependency",
    )

    assert [row["pass_id"] for row in result["tool_results"]] == ["lookup", "details"]
    assert result["tool_results"][1]["step"]["sql"] == 'SELECT "name", "status" FROM "dim_campaign" WHERE "campaign_id" = ?'
    assert result["tool_results"][1]["payload"]["rows"] == [{"name": "Birthday Message", "status": "draft"}]
    pass_results = _preview_items(_checkpoint_output(result, "checkpoint_result_bundle")["runtime_passes"])
    assert pass_results[1]["dependency_resolution"]["resolved"] is True


def test_v2_dependent_pass_resolves_field_shorthand_placeholder_from_dependency_result(tiny_project, monkeypatch):
    _install_fake_planner(
        monkeypatch,
        [
            {
                "route": "EVIDENCE_PIPELINE",
                "evidence_order": "MULTI_PASS",
                "passes": [
                    {
                        "pass_id": "lookup",
                        "subtask": "Lookup campaign id.",
                        "path": "SQL",
                        "can_run_parallel": False,
                        "depends_on": [],
                        "sql": {"query": "SELECT campaign_id FROM dim_campaign WHERE name = ?", "params": ["Birthday Message"]},
                    },
                    {
                        "pass_id": "details",
                        "subtask": "Fetch campaign details using the id.",
                        "path": "SQL",
                        "can_run_parallel": False,
                        "depends_on": ["lookup"],
                        "sql": {"query": "SELECT name, status FROM dim_campaign WHERE campaign_id = ?", "params": ["{{lookup.campaign_id}}"]},
                    },
                ],
                "aggregation_instruction": "Answer using both lookup and details.",
            },
            {
                "final_answer": "Birthday Message is draft.",
                "used_pass_ids": ["lookup", "details"],
                "claimed_facts": [{"claim": "Birthday Message is draft.", "supporting_pass_ids": ["details"]}],
                "caveats_included": [],
            },
        ],
    )

    result = AgentExecutor(tiny_project).run(
        "Find Birthday Message by id, then show its status.",
        strategy=ROBUST_V2,
        query_id="v2_shorthand_placeholder_dependency",
    )

    assert [row["pass_id"] for row in result["tool_results"]] == ["lookup", "details"]
    assert result["tool_results"][1]["payload"]["rows"] == [{"name": "Birthday Message", "status": "draft"}]
    pass_results = _preview_items(_checkpoint_output(result, "checkpoint_result_bundle")["runtime_passes"])
    assert pass_results[1]["dependency_resolution"]["resolved"] is True


def test_v2_missing_dependency_placeholder_returns_error_to_llm_repair_once(tiny_project, monkeypatch):
    client = _install_fake_planner(
        monkeypatch,
        [
            {
                "route": "EVIDENCE_PIPELINE",
                "evidence_order": "MULTI_PASS",
                "passes": [
                    {
                        "pass_id": "lookup",
                        "subtask": "Lookup campaign.",
                        "path": "SQL",
                        "can_run_parallel": False,
                        "depends_on": [],
                        "sql": {"query": "SELECT campaign_id FROM dim_campaign WHERE name = ?", "params": ["Birthday Message"]},
                    },
                    {
                        "pass_id": "details",
                        "subtask": "Use a missing field.",
                        "path": "SQL",
                        "can_run_parallel": False,
                        "depends_on": ["lookup"],
                        "sql": {"query": "SELECT name FROM dim_campaign WHERE campaign_id = ?", "params": ["{{lookup.result.missing_id}}"]},
                    },
                ],
            },
            {
                "route": "EVIDENCE_PIPELINE",
                "evidence_order": "MULTI_PASS",
                "passes": [
                    {
                        "pass_id": "details",
                        "subtask": "Repair by using the campaign_id field.",
                        "path": "SQL",
                        "can_run_parallel": False,
                        "depends_on": ["lookup"],
                        "sql": {"query": "SELECT name FROM dim_campaign WHERE campaign_id = ?", "params": ["{{lookup.result.campaign_id}}"]},
                    }
                ],
            },
            {
                "final_answer": "Birthday Message was found.",
                "used_pass_ids": ["lookup", "details"],
                "claimed_facts": [{"claim": "Birthday Message was found.", "supporting_pass_ids": ["details"]}],
                "caveats_included": [],
            },
        ],
    )

    result = AgentExecutor(tiny_project).run(
        "Lookup Birthday Message, then use the lookup id.",
        strategy=ROBUST_V2,
        query_id="v2_missing_placeholder_repair",
    )

    assert [row["pass_id"] for row in result["tool_results"]] == ["lookup"]
    pass_results = _preview_items(_checkpoint_output(result, "checkpoint_result_bundle")["runtime_passes"])
    assert [item["pass_id"] for item in pass_results] == ["lookup", "details"]
    assert pass_results[1]["status"] == "DEPENDENCY_FAILED"
    assert pass_results[1]["dependency_resolution"]["repair_attempted"] is True
    assert pass_results[1]["dependency_resolution"]["repair_resolved"] is False
    repair_payload = next(payload for payload in _client_call_payloads(client) if isinstance(payload.get("repair_context"), dict))
    assert repair_payload["repair_context"]["failed_component"] == "dependency_resolution"
    assert repair_payload["repair_context"]["pass_id"] == "details"


def test_v2_each_pass_uses_gate_and_failed_pass_sql_repairs_with_pass_context(tiny_project, monkeypatch):
    client = _install_fake_planner(
        monkeypatch,
        [
            {
                "route": "EVIDENCE_PIPELINE",
                "evidence_order": "MULTI_PASS",
                "passes": [
                    {
                        "pass_id": "broken_sql",
                        "subtask": "Fetch campaign names.",
                        "path": "SQL",
                        "can_run_parallel": False,
                        "depends_on": [],
                        "evidence_order": "SQL_FIRST",
                        "sql": {"query": "SELECT campaign_name FROM dim_campaign", "params": []},
                    }
                ],
                "reason": "first attempt has bad SQL",
            },
            {
                "route": "EVIDENCE_PIPELINE",
                "evidence_order": "MULTI_PASS",
                "passes": [
                    {
                        "pass_id": "broken_sql",
                        "subtask": "Fetch campaign names.",
                        "path": "SQL",
                        "can_run_parallel": False,
                        "depends_on": [],
                        "evidence_order": "SQL_FIRST",
                        "sql": {"query": "SELECT name FROM dim_campaign ORDER BY campaign_id", "params": []},
                    }
                ],
                "reason": "repair pass SQL",
            },
            {
                "final_answer": "Campaigns: Birthday Message; Welcome Journey.",
                "used_pass_ids": ["broken_sql"],
                "claimed_facts": [{"claim": "Birthday Message and Welcome Journey were returned.", "supporting_pass_ids": ["broken_sql"]}],
                "caveats_included": [],
            },
        ],
    )

    result = AgentExecutor(tiny_project).run("Show campaigns.", strategy=ROBUST_V2, query_id="v2_pass_sql_repair")

    assert result["tool_results"][0]["pass_id"] == "broken_sql"
    assert result["tool_results"][0]["payload"]["ok"] is True
    summary = _checkpoint_output(result, "checkpoint_llm_owned_generation_boundary")
    assert summary["sql_repair_attempts"] == 0
    repair_payload = next(payload for payload in _client_call_payloads(client) if isinstance(payload.get("validation_error"), dict))
    assert repair_payload["validation_error"]["error_type"] == "unknown_field"


def test_v2_malformed_api_request_can_repair_without_backend_rewrite(tiny_project, monkeypatch):
    _install_fake_planner(
        monkeypatch,
        [
            {
                "route": "EVIDENCE_PIPELINE",
                "evidence_order": "API_FIRST",
                "direct_answer": None,
                "sql": None,
                "api_request": {"method": "POST", "path": "/data/foundation/schemaregistry/tenant/schemas", "params": {}},
                "reason": "bad unsafe method",
            },
            {
                "route": "EVIDENCE_PIPELINE",
                "evidence_order": "API_FIRST",
                "direct_answer": None,
                "sql": None,
                "api_request": {"method": "GET", "path": "/data/foundation/schemaregistry/tenant/schemas", "params": {}},
                "reason": "repair to safe request",
            },
            {
                "final_answer": "The live API returned Birthday Message.",
                "used_pass_ids": ["api_1"],
                "claimed_facts": [{"claim": "Birthday Message was returned by the live API.", "supporting_pass_ids": ["api_1"]}],
                "caveats_included": [],
            },
        ],
    )
    api_client = RecordingAPIClient()

    result = AgentExecutor(tiny_project, api_client=api_client).run(
        "List current schemas.",
        strategy=ROBUST_V2,
        query_id="v2_api_repair",
    )

    first_gate = _checkpoint_output(result, "checkpoint_llm_owned_api_request_gate")
    assert first_gate["passed"] is True
    assert api_client.calls == [("GET", "/data/foundation/schemaregistry/tenant/schemas", {})]
    summary = _checkpoint_output(result, "checkpoint_llm_owned_generation_boundary")
    assert summary["api_gate_passed"] is True
    assert summary["api_repair_attempts"] == 0


def test_v2_llm_owned_path_does_not_run_backend_semantic_or_template_planners(tiny_project, monkeypatch):
    _install_fake_planner(
        monkeypatch,
        [
            {
                "route": "EVIDENCE_PIPELINE",
                "evidence_order": "SQL_FIRST",
                "direct_answer": None,
                "sql": {"query": "SELECT name FROM dim_campaign ORDER BY campaign_id", "params": []},
                "api_request": None,
                "reason": "llm owns SQL",
            },
            {
                "final_answer": "Campaigns: Birthday Message; Welcome Journey.",
                "used_pass_ids": ["sql_1"],
                "claimed_facts": [{"claim": "Birthday Message and Welcome Journey were returned.", "supporting_pass_ids": ["sql_1"]}],
                "caveats_included": [],
            },
        ],
    )

    result = AgentExecutor(tiny_project).run("Show campaigns.", strategy=ROBUST_V2, query_id="v2_no_backend_plan")

    checkpoint_names = _checkpoint_names(result)
    assert "checkpoint_llm_unified_planner" in checkpoint_names
    assert "checkpoint_00_prompt_router" not in checkpoint_names
    assert "checkpoint_02_query_normalization" not in checkpoint_names
    assert "checkpoint_05_query_analysis" not in checkpoint_names
    assert "checkpoint_08_candidate_plans" not in checkpoint_names
    assert "checkpoint_progressive_evidence_policy" not in checkpoint_names
    assert "checkpoint_evidence_grounded_answer_builder" not in checkpoint_names
    assert "checkpoint_broad_question_classifier" not in checkpoint_names
    assert "checkpoint_answer_intent_router" not in checkpoint_names
    assert "checkpoint_hybrid_answer_composer" not in checkpoint_names
    assert "checkpoint_answer_candidate_selector" not in checkpoint_names
    assert "checkpoint_llm_final_answer_composer" in checkpoint_names
    summary = _checkpoint_output(result, "checkpoint_llm_owned_generation_boundary")
    assert summary["llm_owned_generation"] is True
    assert "sql_gate_passed" in summary
    assert "api_gate_passed" in summary
    assert summary["backend_semantic_planning_used"] is False


def test_v2_planner_trace_excludes_gold_oracle_and_expected_trace(tiny_project, monkeypatch):
    _install_fake_planner(
        monkeypatch,
        [
            {
                "route": "EVIDENCE_PIPELINE",
                "evidence_order": "SQL_FIRST",
                "direct_answer": None,
                "sql": {"query": "SELECT COUNT(*) AS count FROM dim_campaign", "params": []},
                "api_request": None,
                "reason": "runtime only",
            },
            {
                "final_answer": "There are 2 campaigns.",
                "used_pass_ids": ["sql_1"],
                "claimed_facts": [{"claim": "There are 2 campaigns.", "supporting_pass_ids": ["sql_1"]}],
                "caveats_included": [],
            },
        ],
    )

    result = AgentExecutor(tiny_project).run("How many campaigns are there?", strategy=ROBUST_V2, query_id="v2_no_leak")

    inspected = [
        _checkpoint_output(result, "checkpoint_llm_unified_planner"),
        _checkpoint_output(result, "checkpoint_llm_owned_generation_boundary"),
        _checkpoint_output(result, "checkpoint_llm_final_answer_composer"),
    ]
    serialized = json.dumps(inspected, default=str).lower()
    assert "gold_answer" not in serialized
    assert "organizer" not in serialized
    assert "oracle" not in serialized
    assert "expected_trace" not in serialized
