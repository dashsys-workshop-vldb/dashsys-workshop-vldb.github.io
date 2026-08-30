from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from dashagent.answer_slots import extract_answer_slots
from dashagent.api_outcome_classifier import classify_api_outcome
from dashagent.db import DuckDBDatabase
from dashagent.endpoint_catalog import EndpointCatalog
from dashagent.evidence_bus import EvidenceBus
from dashagent.planner import PlanStep
from dashagent.schema_index import SchemaIndex
from dashagent.validators import APIValidator, SQLValidator
from scripts.generate_consolidated_reports import generate_consolidated_reports
from scripts.run_core_tool_correctness_audit import run_core_tool_correctness_audit
from scripts.run_core_tool_correctness_trials import run_core_tool_correctness_trials


SECRET_VALUE_RE = re.compile(
    r"sk-[A-Za-z0-9_-]{12,}"
    r"|Bearer\s+[A-Za-z0-9._-]{12,}"
    r"|Authorization:\s*Bearer\s+[A-Za-z0-9._-]+"
    r"|[A-Za-z0-9]{3}\*\*\*",
    re.IGNORECASE,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _seed_correctness_inputs(outputs: Path) -> None:
    reports = outputs / "reports"
    _write_json(
        outputs / "eval_results_strict.json",
        {
            "summary": {
                "by_strategy": {
                    "SQL_FIRST_API_VERIFY": {
                        "avg_final_score": 0.6553,
                        "avg_sql_score": 0.9333,
                        "avg_api_score": 0.9791,
                        "avg_answer_score": 0.3199,
                        "avg_correctness_score": 0.6805,
                    }
                }
            },
            "rows": [
                {
                    "example_id": "example_001",
                    "strategy": "SQL_FIRST_API_VERIFY",
                    "prompt": "How many campaigns are there?",
                    "sql_score": 0.9,
                    "api_score": 1.0,
                    "answer_score": 0.3,
                    "final_score": 0.65,
                }
            ],
        },
    )
    _write_json(
        reports / "system_summary.json",
        {
            "preferred_strategy": "SQL_FIRST_API_VERIFY",
            "packaged_strict_score": 0.6553,
            "strict_correctness": 0.6805,
            "hidden_style": {"label": "48/48", "passed": 48, "total": 48},
            "final_submission_ready": True,
        },
    )
    _write_json(reports / "sdk_usage_audit.json", {"summary": {"runtime_llm_direct_http_hits": 0}})
    _write_json(reports / "live_api_readiness_smoke.json", {"summary": {"live_success_count": 0}})
    _write_json(reports / "report_index.json", {"report_type": "report_index", "canonical_reports": []})
    _write_json(
        reports / "accuracy_and_bottleneck_summary.json",
        {
            "report_type": "accuracy_and_bottleneck_summary",
            "dry_run_api_limitation": True,
        },
    )
    _write_json(
        reports / "core_tool_optimization_audit.json",
        {"report_type": "core_tool_optimization_audit", "tools": {"execute_sql": {}, "call_api": {}}},
    )
    _write_json(
        reports / "core_tool_policy_promotion_decision.json",
        {"report_type": "core_tool_policy_promotion_decision", "strict_score_before": 0.6553},
    )
    _write_json(
        reports / "official_row_failure_table.json",
        {
            "report_type": "official_row_failure_table",
            "rows": [
                {
                    "row_id": "row_1",
                    "example_id": "example_001",
                    "prompt": "How many campaigns are there?",
                    "predicted_route": "SQL_ONLY",
                    "predicted_domain": "JOURNEY_CAMPAIGN",
                    "answer_intent": "COUNT",
                    "sql_calls": 1,
                    "sql_returned_row_count": 1,
                    "sql_evidence_fields": ["num_campaigns"],
                    "api_calls": 0,
                    "api_state": "not_called",
                    "sql_score": 0.9,
                    "api_score": 1.0,
                    "answer_score": 0.3,
                    "total_strict_score": 0.65,
                    "failure_classification": {"answer_missing_count": True, "sql_correct_but_answer_weak": True},
                    "requires_live_api": False,
                    "locally_fixable_now": True,
                    "final_answer": "There are campaigns.",
                },
                {
                    "row_id": "row_2",
                    "example_id": "example_002",
                    "prompt": "List all journeys",
                    "predicted_route": "SQL_THEN_API",
                    "predicted_domain": "JOURNEY_CAMPAIGN",
                    "answer_intent": "LIST",
                    "sql_calls": 1,
                    "sql_returned_row_count": 2,
                    "sql_evidence_fields": ["campaign_id", "campaign_name"],
                    "api_calls": 1,
                    "api_state": "dry_run_unavailable",
                    "sql_score": 0.9,
                    "api_score": 1.0,
                    "answer_score": 0.4,
                    "total_strict_score": 0.66,
                    "failure_classification": {"api_required_but_dry_run": True, "live_api_blocked": True},
                    "requires_live_api": True,
                    "locally_fixable_now": False,
                    "final_answer": "Live API unavailable.",
                },
            ],
        },
    )
    _write_json(
        reports / "generated_prompt_failure_table.json",
        {
            "report_type": "generated_prompt_failure_table",
            "diagnostic_only": True,
            "rows": [
                {
                    "prompt_id": "gen_1",
                    "prompt": "Count campaigns",
                    "actual_answer_intent": "COUNT",
                    "requires_live_api": False,
                    "likely_issue_type": "answer_template_gap",
                    "zero_row_sql": False,
                },
                {
                    "prompt_id": "gen_2",
                    "prompt": "Show live audience status",
                    "actual_answer_intent": "STATUS",
                    "requires_live_api": True,
                    "likely_issue_type": "live_api_required",
                },
            ],
        },
    )
    _write_json(reports / "cross_dataset_failure_clusters.json", {"report_type": "cross_dataset_failure_clusters", "clusters": []})
    _write_json(reports / "general_deterministic_rule_candidates.json", {"report_type": "general_deterministic_rule_candidates", "candidates": []})
    _write_json(reports / "comprehensive_failure_fix_decision.json", {"report_type": "comprehensive_failure_fix_decision", "decision": "wait_for_adobe_access"})


def test_core_tool_correctness_reports_and_trials_are_isolated(tiny_project):
    _seed_correctness_inputs(tiny_project.outputs_dir)
    strict_path = tiny_project.outputs_dir / "eval_results_strict.json"
    before_hash = hashlib.sha256(strict_path.read_bytes()).hexdigest()

    audit_payload = run_core_tool_correctness_audit(tiny_project)
    trials_payload = run_core_tool_correctness_trials(tiny_project)

    assert hashlib.sha256(strict_path.read_bytes()).hexdigest() == before_hash
    assert not (tiny_project.outputs_dir / "final_submission").exists()

    reports = tiny_project.outputs_dir / "reports"
    for stem in [
        "core_tool_correctness_preflight",
        "core_tool_correctness_audit",
        "execute_sql_correctness_candidates",
        "call_api_correctness_candidates",
        "core_tool_correctness_trials",
        "core_tool_correctness_fix_decision",
    ]:
        assert (reports / f"{stem}.json").exists(), stem
        assert (reports / f"{stem}.md").exists(), stem

    preflight = audit_payload["preflight"]
    assert preflight["correctness_focused"] is True
    assert preflight["packaged_strategy"] == "SQL_FIRST_API_VERIFY"
    assert preflight["strict_score"] == 0.6553
    assert preflight["sql_score"] == 0.9333
    assert preflight["api_score"] == 0.9791
    assert preflight["response_score"] == 0.3199
    assert preflight["hidden_style"] == "48/48"
    assert preflight["final_submission_ready"] is True
    assert preflight["live_success_count"] == 0
    assert preflight["adobe_live_api_blocked"] is True

    audit = audit_payload["audit"]
    assert audit["official_rows_analyzed"] == 2
    assert audit["generated_prompts_diagnostic_only"] is True
    assert all(row["likely_tool_level_root_cause"] for row in audit["rows"])
    assert all("query_id" not in row["proposed_deterministic_fix"].lower() for row in audit["rows"])

    sql_candidates = audit_payload["execute_sql_candidates"]["candidates"]
    api_candidates = audit_payload["call_api_candidates"]["candidates"]
    assert {row["candidate_id"] for row in sql_candidates} >= {"SQL-C1", "SQL-C2", "SQL-C3", "SQL-C4", "SQL-C5", "SQL-C6", "SQL-C7"}
    assert {row["candidate_id"] for row in api_candidates} >= {"API-C1", "API-C2", "API-C3", "API-C4", "API-C5", "API-C6", "API-C7"}
    assert all(not row["uses_query_ids"] for row in sql_candidates + api_candidates)
    assert all(not row["uses_prompt_ids"] for row in sql_candidates + api_candidates)
    assert all(not row["uses_exact_prompt_strings"] for row in sql_candidates + api_candidates)
    assert all(not row["uses_gold_answers"] for row in sql_candidates + api_candidates)

    trials = trials_payload["trials"]
    assert {row["variant_id"] for row in trials["variants"]} >= {
        "SQL_A",
        "SQL_B",
        "SQL_C",
        "SQL_D",
        "SQL_E",
        "API_A",
        "API_B",
        "API_C",
        "COMBINED_SAFE",
    }
    assert all("strict_score_delta" in row for row in trials["variants"])
    assert trials["writes_official_eval_artifacts"] is False
    assert trials["writes_final_submission"] is False

    decision = trials_payload["fix_decision"]
    assert decision["decision"] in {"no_runtime_change", "one_correctness_patch_ready", "small_batch_ready", "wait_for_adobe_access"}
    assert decision["runtime_change_applied"] is False
    assert decision["final_submission_format_changed"] is False
    assert decision["official_organizer_weighted_score_claim"] is False

    combined = "\n".join((reports / f"{stem}.json").read_text(encoding="utf-8") for stem in [
        "core_tool_correctness_preflight",
        "core_tool_correctness_audit",
        "execute_sql_correctness_candidates",
        "call_api_correctness_candidates",
        "core_tool_correctness_trials",
        "core_tool_correctness_fix_decision",
    ])
    assert not SECRET_VALUE_RE.search(combined)


def test_core_tool_correctness_reports_linked_from_index(tiny_project):
    _seed_correctness_inputs(tiny_project.outputs_dir)
    run_core_tool_correctness_audit(tiny_project)
    run_core_tool_correctness_trials(tiny_project)

    generate_consolidated_reports(tiny_project)

    index = json.loads((tiny_project.outputs_dir / "reports" / "report_index.json").read_text(encoding="utf-8"))
    rendered = json.dumps(index)
    assert "core_tool_correctness_audit.md" in rendered
    assert "core_tool_correctness_trials.md" in rendered
    assert "core_tool_correctness_fix_decision.md" in rendered


def test_execute_sql_correctness_guards_existing_behaviors(tiny_project):
    db = DuckDBDatabase(tiny_project)
    schema = SchemaIndex.build(db)
    validator = SQLValidator(schema)

    assert validator.validate("SELECT COUNT(*) AS num_campaigns FROM dim_campaign").ok is True
    assert validator.ast_summary("SELECT COUNT(*) AS num_campaigns FROM dim_campaign")["enabled"] is True
    assert validator.validate("DELETE FROM dim_campaign").ok is False

    slots = extract_answer_slots(
        "How many campaigns are there?",
        [
            {
                "type": "sql",
                "payload": {"ok": True, "row_count": 1, "rows": [{"num_campaigns": 2}]},
                "step": {"sql": "SELECT COUNT(*) AS num_campaigns FROM dim_campaign"},
            }
        ],
    )
    assert 2 in slots.counts
    assert slots.sql_row_count == 1

    status_slots = extract_answer_slots(
        "When was Birthday Message updated and what is its status?",
        [
            {
                "type": "sql",
                "payload": {"ok": True, "row_count": 1, "rows": [{"campaign_state": "inactive", "updated_time": "2026-03-31"}]},
                "step": {"sql": "SELECT campaign_state, updated_time FROM dim_campaign"},
            }
        ],
    )
    assert "inactive" in status_slots.statuses
    assert "2026-03-31" in status_slots.timestamps


def test_call_api_correctness_guards_existing_behaviors(tiny_project):
    catalog = EndpointCatalog(tiny_project)
    validator = APIValidator(catalog)

    missing_id = validator.validate("GET", "/data/foundation/schemaregistry/tenant/schemas/{schema_id}", {}, {})
    assert missing_id.ok is False
    assert any("unresolved path" in error.lower() for error in missing_id.errors)

    assert classify_api_outcome({"ok": False, "dry_run": True, "parsed_evidence": {"evidence_state": "dry_run_unavailable"}}) == "api_error"
    assert classify_api_outcome({"ok": False, "status_code": 404, "error": "not found"}) == "endpoint_path_issue"
    assert classify_api_outcome({"ok": True, "status_code": 204, "parsed_evidence": {"evidence_state": "live_empty"}}) == "live_empty"

    bus = EvidenceBus()
    bus.observe_sql(PlanStep(action="sql", purpose="unit"), {"ok": True, "rows": [{"schema_id": "schema-123"}], "row_count": 1})
    step = PlanStep(action="api", purpose="unit", method="GET", url="/data/foundation/schemaregistry/tenant/schemas/{schema_id}")
    actions = bus.forward_to_step(step)
    assert step.url.endswith("/schema-123")
    assert actions
