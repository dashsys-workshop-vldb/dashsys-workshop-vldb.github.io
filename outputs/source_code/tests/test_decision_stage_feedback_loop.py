from __future__ import annotations

import json
from pathlib import Path

from dashagent.config import Config
from scripts.run_decision_feedback_loop import answer_only_invariants_preserved, run_decision_feedback_loop
from scripts.run_workflow_decision_audit import BOTTLENECK_CATEGORIES, build_workflow_decision_map, run_workflow_decision_audit


def _write_minimal_strict_eval(config: Config) -> None:
    output_dir = config.outputs_dir / "eval" / "tiny_001" / "sql_first_api_verify"
    output_dir.mkdir(parents=True, exist_ok=True)
    trajectory = {
        "query_id": "tiny_001",
        "original_query": "How many campaigns are there?",
        "strategy": "SQL_FIRST_API_VERIFY",
        "route_type": "SQL_ONLY",
        "domain_type": "JOURNEY_CAMPAIGN",
        "tool_call_count": 1,
        "estimated_tokens": 500,
        "runtime": 0.02,
        "final_answer": "There are 2 campaigns.",
        "steps": [
            {
                "kind": "route",
                "route_type": "SQL_ONLY",
                "domain_type": "JOURNEY_CAMPAIGN",
                "confidence": 0.82,
                "candidate_tables": ["dim_campaign"],
                "candidate_apis": [],
            },
            {
                "kind": "nlp",
                "relevance": {"tables": ["dim_campaign"], "apis": []},
                "tokens": {"domains": ["journey_campaign"]},
            },
            {
                "kind": "plan",
                "strategy": "SQL_FIRST_API_VERIFY",
                "rationale": "SQL-first evidence policy: API_SKIP.",
                "steps": [{"action": "sql", "family": "campaign_count", "sql": "SELECT COUNT(*) FROM dim_campaign"}],
            },
            {"kind": "optimizer", "plan_ensemble": {"candidate_scores": {"generic_sql_first": 1.0}, "selected": "generic_sql_first"}},
            {
                "kind": "sql_call",
                "sql": "SELECT COUNT(*) FROM dim_campaign",
                "validation": {"ok": True, "errors": [], "warnings": []},
                "result": {"ok": True, "row_count": 1, "rows": [{"count": 2}]},
            },
            {
                "kind": "answer_diagnostics",
                "answer_family": "count",
                "answer_intent": "COUNT",
                "slots_present": ["counts"],
                "unsupported_claims_count": 0,
                "verifier_passed": True,
            },
        ],
    }
    (output_dir / "trajectory.json").write_text(json.dumps(trajectory), encoding="utf-8")
    (config.outputs_dir / "eval_results_strict.json").write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "query_id": "tiny_001",
                        "query": "How many campaigns are there?",
                        "strategy": "SQL_FIRST_API_VERIFY",
                        "output_dir": str(output_dir),
                        "sql_score": 0.9,
                        "api_score": None,
                        "answer_score": 0.4,
                        "correctness_score": 0.65,
                        "final_score": 0.63,
                        "tool_call_count": 1,
                        "estimated_tokens": 500,
                        "runtime": 0.02,
                        "validation_failures": 0,
                    }
                ],
                "summary": {},
            }
        ),
        encoding="utf-8",
    )


def test_workflow_decision_map_has_all_twenty_stages():
    payload = build_workflow_decision_map()
    assert payload["stage_count"] == 20
    assert len(payload["decision_stages"]) == 20
    assert {stage["stage_id"] for stage in payload["decision_stages"]} == set(range(1, 21))


def test_workflow_decision_audit_reports_parseable_rows(tiny_project: Config):
    _write_minimal_strict_eval(tiny_project)
    payload = run_workflow_decision_audit(tiny_project)
    audit = payload["audit"]
    assert audit["total_queries"] == 1
    row = audit["rows"][0]
    assert row["query_id"] == "tiny_001"
    assert row["route_type"] == "SQL_ONLY"
    assert row["selected_tables"] == ["dim_campaign"]
    assert "strict_score_components" in row
    assert row["likely_decision_stage_bottleneck"] in BOTTLENECK_CATEGORIES
    assert (tiny_project.outputs_dir / "reports" / "workflow_decision_map.json").exists()
    assert (tiny_project.outputs_dir / "reports" / "workflow_decision_audit.md").exists()


def test_decision_feedback_loop_reports_variants(monkeypatch, tiny_project: Config):
    def fake_trial(config, **kwargs):
        policy = kwargs["trial_policy"]
        delta = 0.0 if policy == "priority_only" else -0.001
        return {
            "report_type": "llm_semantic_router_isolated_trial",
            "status": "complete",
            "trial_policy": policy,
            "output_root": f"outputs/llm_semantic_router_feedback_loop/{policy}",
            "strict_score_delta": delta,
            "answer_score_delta": 0.01 if policy == "priority_only" else 0.0,
            "sql_score_delta": 0.0,
            "api_score_delta": 0.0,
            "tool_count_delta_avg": 0.0,
            "estimated_token_delta_avg": 0.0,
            "runtime_delta_avg": 0.0,
            "route_changed_count": 0,
            "domain_changed_count": 0,
            "intent_changed_count": 0,
            "sql_changed_count": 0,
            "api_changed_count": 0,
            "answer_changed_count": 1 if policy == "priority_only" else 0,
            "failures_introduced_count": 0,
            "failures_fixed_count": 1 if policy == "priority_only" else 0,
            "safety_failures": [],
            "where_semantic_routing_helped": [{"query_id": "tiny_001", "strict_final_score_delta": delta, "answer_score_delta": 0.01}],
            "where_semantic_routing_hurt_or_was_risky": [],
        }

    monkeypatch.setattr("scripts.run_decision_feedback_loop.run_llm_semantic_router_isolated_trial", fake_trial)
    result = run_decision_feedback_loop(tiny_project, variants=["narrow_eligibility", "priority_only"], limit=1)
    assert result["final"]["iteration_count"] == 2
    assert result["iterations"][1]["outcome_classification"] == "candidate_partially_useful"
    assert result["iterations"][1]["recommendation"] == "locally_useful_but_not_promotable"
    assert (tiny_project.outputs_dir / "reports" / "improvement_feedback_loop_index.json").exists()
    assert (tiny_project.outputs_dir / "reports" / "feedback_loop_semantic_router_iteration_3.md").exists()
    assert (tiny_project.outputs_dir / "reports" / "decision_stage_improvement_summary.json").exists()


def test_answer_only_invariants_preserved_requires_all_hashes():
    baseline = {
        "sql_hash": "a",
        "api_hash": "b",
        "tool_count": 1,
        "selected_evidence_hash": "c",
        "dry_run_label": "dry_run",
    }
    trial = dict(baseline)
    assert answer_only_invariants_preserved(baseline, trial)["ok"] is True
    trial["tool_count"] = 2
    result = answer_only_invariants_preserved(baseline, trial)
    assert result["ok"] is False
    assert result["checks"]["tool_count_unchanged"] is False
