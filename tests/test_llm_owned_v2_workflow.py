from __future__ import annotations

import json

import pytest

from dashagent.config import ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2
from dashagent.executor import AgentExecutor


ROBUST_V2 = ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2


class SequencedLLMClient:
    def __init__(self, responses: list[dict]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, str]] = []

    def available(self) -> bool:
        return True

    def provider_name(self) -> str:
        return "fake_llm"

    def model_name(self) -> str:
        return "fake-model"

    def generate(self, system_prompt: str, user_prompt: str, tools=None):
        self.calls.append({"system": system_prompt, "user": user_prompt})
        if not self.responses:
            raise AssertionError("Fake LLM called more times than expected")
        return {
            "ok": True,
            "provider": self.provider_name(),
            "model": self.model_name(),
            "content": json.dumps(self.responses.pop(0)),
        }

    def generate_messages(self, messages, tools=None, tool_choice=None, parallel_tool_calls=None):
        return self.generate(messages[0]["content"], messages[-1]["content"], tools=tools)


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


def _checkpoint_names(result: dict) -> set[str]:
    return {checkpoint["checkpoint_id"] for checkpoint in result["checkpoints"]}


def _checkpoint_output(result: dict, checkpoint_id: str) -> dict:
    return next(
        checkpoint["output"]
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
    assert result["final_answer"] == "There are 2 campaigns."
    sql_gate = _checkpoint_output(result, "checkpoint_llm_owned_sql_compile_gate")
    assert sql_gate["passed"] is True
    answer_gate = _checkpoint_output(result, "checkpoint_llm_final_answer_semantic_gate")
    assert answer_gate["passed"] is True
    boundary = _checkpoint_output(result, "checkpoint_evidence_pipeline_boundary")
    assert boundary["evidence_pipeline_bypassed"] is False
    assert boundary["evidence_bus_built"] is True


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
    assert first_gate["passed"] is False
    assert first_gate["error_type"] == "semantic_error"
    assert "campaign_name" in first_gate["error_message"]
    repaired_gate = _checkpoint_output(result, "checkpoint_llm_owned_sql_compile_gate_repair")
    assert repaired_gate["passed"] is True
    summary = _checkpoint_output(result, "checkpoint_llm_owned_generation_boundary")
    assert summary["sql_gate_passed"] is True
    assert summary["sql_repair_attempts"] == 1


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
                        "can_run_parallel": True,
                        "depends_on": [],
                        "evidence_order": "SQL_FIRST",
                        "sql": {"query": "SELECT COUNT(*) AS count FROM dim_campaign", "params": []},
                        "api_request": None,
                    },
                    {
                        "pass_id": "live_schema_probe",
                        "subtask": "Probe live schemas.",
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

    assert [row["type"] for row in result["tool_results"]] == ["sql", "api"]
    assert result["final_answer"] == "There are 2 campaigns, and Birthday Message was returned by the live API."
    assert "checkpoint_llm_final_answer_composer" in _checkpoint_names(result)
    final = _checkpoint_output(result, "checkpoint_18_final_answer")
    assert final["llm_owned_final_answer"] is True
    assert final["used_pass_ids"]["items"] == ["local_count", "live_schema_probe"]
    boundary = _checkpoint_output(result, "checkpoint_llm_owned_generation_boundary")
    assert boundary["multi_pass_enabled"] is True
    assert boundary["llm_pass_count"] == 2
    assert boundary["parallel_pass_count"] == 2
    assert boundary["backend_semantic_decomposition_used"] is False
    composer_payload = next(payload for payload in _client_call_payloads(client) if payload.get("task") == "LLM_OWNED_FINAL_ANSWER_COMPOSITION")
    assert [item["pass_id"] for item in composer_payload["runtime_passes"]] == ["local_count", "live_schema_probe"]
    assert composer_payload["aggregation_instruction"] == "Report both local count and live API evidence."


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
                        "can_run_parallel": False,
                        "depends_on": [],
                        "evidence_order": "SQL_FIRST",
                        "sql": {"query": "SELECT name FROM dim_campaign ORDER BY campaign_id", "params": []},
                    },
                    {
                        "pass_id": "second",
                        "subtask": "Fetch statuses after names.",
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
    assert boundary["sequential_pass_count"] == 2


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
    assert summary["sql_repair_attempts"] == 1
    repair_payload = next(payload for payload in _client_call_payloads(client) if isinstance(payload.get("repair_context"), dict))
    assert repair_payload["repair_context"]["pass_id"] == "broken_sql"


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
    assert first_gate["passed"] is False
    assert "GET" in first_gate["error_message"]
    repair_gate = _checkpoint_output(result, "checkpoint_llm_owned_api_request_gate_repair")
    assert repair_gate["passed"] is True
    assert api_client.calls == [("GET", "/data/foundation/schemaregistry/tenant/schemas", {})]
    summary = _checkpoint_output(result, "checkpoint_llm_owned_generation_boundary")
    assert summary["api_gate_passed"] is True
    assert summary["api_repair_attempts"] == 1


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
