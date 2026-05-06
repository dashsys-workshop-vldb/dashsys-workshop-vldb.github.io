from __future__ import annotations

from pathlib import Path

from dashagent.dataflow_visualizer import (
    build_checkpoint_effect_table,
    build_dataflow_summary,
    build_html_report,
    build_markdown_report,
    build_mermaid_graph,
    count_mermaid_readability_issues,
    write_dataflow_artifacts,
)


def fake_trajectory():
    return {
        "query_id": "fake",
        "original_query": "Is the 'Birthday Message' journey published?",
        "strategy": "SQL_FIRST_API_VERIFY",
        "tool_call_count": 1,
        "runtime": 0.123,
        "estimated_tokens": 456,
        "final_answer": "Birthday Message has not been published.",
        "checkpoints": [
            {
                "checkpoint_id": "checkpoint_00_prompt_router",
                "stage": "routing",
                "technique": "routing",
                "output": {"mode": "SQL_PLUS_API", "api_policy": "API_OPTIONAL", "risk": "medium"},
                "effect": "routes status question to SQL plus API verification",
                "correctness_role": "prevents unsupported direct answers",
                "efficiency_role": "avoids unnecessary APIs for local-only prompts",
            },
            {
                "checkpoint_id": "checkpoint_02_query_normalization",
                "technique": "normalization",
                "output": {"normalized_query": "is birthday message journey published"},
            },
            {"checkpoint_id": "checkpoint_03_query_tokens", "technique": "tokens", "output": {"quoted_entities": ["Birthday Message"]}},
            {
                "checkpoint_id": "checkpoint_value_entity_retrieval",
                "stage": "query understanding",
                "technique": "CHESS-style value/entity retrieval",
                "output": {
                    "cache_hit": False,
                    "cache_key_algorithm": "sha256",
                    "cache_reproducible": True,
                    "retrieval_ms": 1.23,
                    "cold_cache_build_ms": 1.23,
                    "warm_cache_lookup_ms": None,
                    "value_retrieval_budget_exceeded": False,
                    "match_count": 1,
                },
            },
            {
                "checkpoint_id": "checkpoint_sql_ast_validation",
                "stage": "validation",
                "technique": "SQLGlot AST-based SQL validation and extraction",
                "output": {
                    "parsed_ok": True,
                    "parse_errors": [],
                    "selected_tables": ["dim_campaign"],
                    "selected_columns": ["name"],
                    "unknown_tables": [],
                    "unknown_columns": [],
                    "destructive_sql_detected": False,
                    "closest_table_suggestions": {},
                    "closest_column_suggestions": {},
                },
            },
            {"checkpoint_id": "checkpoint_16_answer_verification", "technique": "verification", "output": {"verifier_passed": True}},
        ],
        "steps": [
            {"kind": "sql_call", "sql": "SELECT * FROM dim_campaign", "validation": {"ok": True}, "result": {"row_count": 1, "rows": [{"name": "Birthday Message"}]}},
            {
                "kind": "api_call",
                "method": "GET",
                "url": "/ajo/journey",
                "params": {"access_token": "secret-token-123456789"},
                "validation": {"ok": True},
                "endpoint_repair": {"repaired": True, "original_url": "/journey", "repaired_url": "/ajo/journey"},
                "result": {"ok": True, "dry_run": True, "result_preview": {"dry_run": True}},
            },
        ],
        "_candidate_context_report_row": {
            "hybrid_candidate_scoring": {
                "active": True,
                "top_candidate_score": 1.2,
                "score_margin": 0.3,
                "ranking_changed": True,
                "top_components": {"name": "dim_campaign"},
            },
            "endpoint_family_ranking": {
                "active": True,
                "endpoint_family": "journey_list",
                "endpoint_family_confidence": 0.95,
                "ranking_changed": False,
                "endpoint_boost_reason": ["journey_list: journey vocabulary"],
            },
            "schema_linking": {
                "bridge_preserved": True,
                "structural_tables_added": ["br_campaign_segment"],
                "structural_reason": "schema-level campaign-segment bridge rule",
                "structural_confidence_delta": 0.1,
            },
            "value_to_api_ranking": {"active": True, "value_match_used_for_api_ranking": False},
            "gated_risk_cluster_repair": {"active": True, "diagnostic_only": True, "risk_cluster": "zero_score_margin"},
            "risk_efficiency_controller": {
                "active": True,
                "risk_level": "high",
                "accuracy_risk": "high - zero_score_margin",
                "module_skipped_by_risk": [],
                "token_saved_estimate": 0,
                "runtime_saved_estimate_ms": 0,
                "savings_are_estimates": True,
                "measured_efficiency_improvement_claimed": False,
                "behavior_changed": False,
            },
            "schema_context_vote": {
                "active": True,
                "schema_vote_agreement": True,
                "compact_context_safe": True,
                "fallback_reason": "compact and fallback top candidates agree",
                "compact_candidate_tables": ["dim_campaign"],
                "fallback_candidate_tables": ["dim_campaign"],
                "compact_candidate_apis": ["journey_list"],
                "fallback_candidate_apis": ["journey_list"],
                "token_delta": 42,
                "behavior_changed": False,
            },
        },
        "_shadow_repair_eval_row": {
            "risk_cluster": "zero_score_margin",
            "current_plan_sql": ["SELECT * FROM dim_campaign"],
            "current_plan_api": [{"method": "GET", "path": "/ajo/journey"}],
            "repaired_plan_sql": ["SELECT * FROM dim_campaign"],
            "repaired_plan_api": [{"method": "GET", "path": "/ajo/journey"}],
            "current_strict_score": 0.6,
            "repaired_strict_score": 0.6,
            "score_delta": 0.0,
            "tool_delta": 0,
            "token_delta": 0,
            "runtime_delta": 0.0,
            "repair_safe_to_enable": False,
            "safety_verdict": {"safe": False},
            "decision": "diagnostic_only_no_enablement",
            "decision_hash": "abc123",
            "execution_changed": False,
            "why_execution_not_changed": "offline shadow evaluation only",
            "risk_efficiency_controller": {
                "active": True,
                "risk_level": "high",
                "accuracy_risk": "high - zero_score_margin",
                "module_skipped_by_risk": [],
                "token_saved_estimate": 0,
                "runtime_saved_estimate_ms": 0,
                "savings_are_estimates": True,
                "measured_efficiency_improvement_claimed": False,
                "behavior_changed": False,
            },
            "schema_context_vote": {
                "active": True,
                "schema_vote_agreement": True,
                "compact_context_safe": True,
                "fallback_reason": "compact and fallback top candidates agree",
                "compact_candidate_tables": ["dim_campaign"],
                "fallback_candidate_tables": ["dim_campaign"],
                "compact_candidate_apis": ["journey_list"],
                "fallback_candidate_apis": ["journey_list"],
                "token_delta": 42,
                "behavior_changed": False,
            },
        },
        "_compact_context_shadow_eval_row": {
            "current_score": 0.6,
            "compact_context_score": 0.6,
            "score_delta": 0.0,
            "token_delta": -42,
            "runtime_delta": 0.0,
            "tool_call_delta": 0,
            "final_answer_difference": False,
            "packaged_execution_changed": False,
            "measured_accuracy_improvement_claimed": False,
            "measured_efficiency_improvement_claimed": False,
        },
        "_risk_efficiency_shadow_eval_row": {
            "risk_level": "medium",
            "module_skipped_by_risk": ["shadow_repair"],
            "current_score": 0.6,
            "risk_skipping_score": 0.6,
            "score_delta": 0.0,
            "token_delta": -12,
            "runtime_delta": -0.01,
            "tool_call_delta": 0,
            "final_answer_difference": False,
            "packaged_execution_changed": False,
            "measured_accuracy_improvement_claimed": False,
            "measured_efficiency_improvement_claimed": False,
        },
    }


def test_dataflow_outputs_mermaid_markdown_html_and_redacts():
    trajectory = fake_trajectory()
    graph = build_mermaid_graph(trajectory)
    md = build_markdown_report(trajectory)
    html = build_html_report(trajectory)
    table = build_checkpoint_effect_table(trajectory)
    assert "flowchart" in graph
    assert "Prompt Router" in graph
    assert "Query Tokens<br/>" in graph
    assert "entities=Birthday Message" in graph
    assert "SQL evidence: yes" in graph
    assert "Live API evidence: no" in graph
    assert "Dry-run API: yes" in graph
    assert "{&quot;" not in graph
    assert "truncated_items" not in graph
    assert count_mermaid_readability_issues(graph) == 0
    assert "checkpoint_00_prompt_router" in table
    assert "Checkpoint Effect Table" in md
    assert "Research Technique Status" in md
    assert "Candidate Ranking Diagnostics" in md
    assert "Shadow Repair / What-if Evaluation" in md
    assert "zero_score_margin" in md
    assert "abc123" in md
    assert "Risk-Based Efficiency Controller" in md
    assert "token/runtime savings in this section are estimates" in md.lower()
    assert "Schema Context Voting" in md
    assert "compact and fallback top candidates agree" in md
    assert "Compact Context Shadow Evaluation" in md
    assert "Risk-Efficiency Shadow Evaluation" in md
    assert "packaged_execution_changed" in md
    assert "measured_accuracy_improvement_claimed" in md
    assert "measured_efficiency_improvement_claimed" in md
    assert "Hybrid Candidate Scoring" in md
    assert "Endpoint Family Ranker" in md
    assert "SQLGlot AST validation" in md
    assert "Value Retrieval Cache" in md
    assert "cache_key_algorithm" in md
    assert "sha256" in md
    assert "SQL AST Validation" in md
    assert "selected_tables" in md
    assert "dim_campaign" in md
    assert "mermaid" in html
    assert "secret-token-123456789" not in md


def test_dataflow_artifacts_are_real_values_and_not_final_submission(tmp_path):
    trajectory = fake_trajectory()
    out_dir = tmp_path / "outputs" / "visualizations" / "fake" / "sql_first_api_verify"
    files = write_dataflow_artifacts(trajectory, out_dir)
    for path in files.values():
        assert Path(path).exists()
        assert "final_submission" not in Path(path).parts
    assert Path(files["spans"]).name == "spans.json"
    md = Path(files["md"]).read_text(encoding="utf-8")
    summary = build_dataflow_summary(trajectory)
    assert "Is the 'Birthday Message' journey published?" in md
    assert "SQL_FIRST_API_VERIFY" in md
    assert "Birthday Message has not been published." in md
    assert "| Tool call count | 1 |" in md
    assert "SELECT * FROM dim_campaign" in md
    assert "GET /ajo/journey" in md
    assert "API tool was invoked and validated" in md
    assert "live API evidence was unavailable because Adobe credentials were missing" in md
    assert "/journey" in md
    assert "Checkpoint count" in md
    assert "prevents unsupported direct answers" in md
    assert summary["evidence"]["sql_evidence_available"] is True
    assert summary["evidence"]["live_api_evidence_available"] is False
    assert summary["evidence"]["overall_evidence_available"] is True
    json_summary = Path(files["json"]).read_text(encoding="utf-8")
    assert "sql_evidence_available" in json_summary
    assert "live_api_evidence_available" in json_summary
    assert "overall_evidence_available" in json_summary
    spans = Path(files["spans"]).read_text(encoding="utf-8")
    assert "span_count" in spans
    assert "sql_ast_validation_span" in spans
    assert "checkpoint_hybrid_candidate_scoring" in spans
    assert "checkpoint_risk_efficiency_controller" in spans
    assert "checkpoint_schema_context_voting" in spans
    assert "checkpoint_compact_context_shadow_eval" in spans
    assert "checkpoint_risk_efficiency_shadow_eval" in spans


def test_dataflow_mermaid_required_subgraphs_and_missing_fields():
    minimal = {"query_id": "minimal", "original_query": "Explain checkpoints", "strategy": "SQL_FIRST_API_VERIFY", "steps": [], "checkpoints": []}
    graph = build_mermaid_graph(minimal)
    md = build_markdown_report(minimal)
    for label in [
        "subgraph Input",
        "subgraph Routing",
        "Query Understanding",
        "Context Selection",
        "Planning",
        "SQL Path",
        "API Path",
        "Tool Execution",
        "EvidenceBus",
        "Answer Verification",
        "Final Answer",
        "Metrics",
    ]:
        assert label in graph
    assert "n/a - no API call in trajectory" in md
    assert "not_recorded" in md


def test_context_mode_is_inferred_when_candidates_exist():
    trajectory = {
        "query_id": "ctx",
        "original_query": "List journeys",
        "strategy": "SQL_FIRST_API_VERIFY",
        "steps": [
            {
                "kind": "nlp",
                "tokens": {"domains": ["journey_campaign"]},
                "relevance": {"tables": ["dim_campaign"], "apis": ["journey_list"]},
            },
            {"kind": "metadata", "estimated_tokens": 300},
        ],
        "checkpoints": [],
    }
    summary = build_dataflow_summary(trajectory)
    assert summary["context"]["context_mode"] == "candidate_like_context_inferred"
    assert "display-only inferred" in summary["context"]["context_mode_note"]
    graph = build_mermaid_graph(trajectory)
    assert "candidate_like_context_inferred" in graph
