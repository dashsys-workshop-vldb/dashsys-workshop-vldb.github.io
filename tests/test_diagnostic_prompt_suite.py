from __future__ import annotations

import json
import re
from pathlib import Path

from dashagent.eval_harness import EvalHarness
from scripts.generate_diagnostic_prompt_suite import DOMAINS, INTENTS, GENERATION_TYPES, ROUTES, generate_prompt_suite
from scripts.package_query_outputs import NON_SUBMISSION_OUTPUT_DIRS
from scripts.analyze_generated_prompt_local_diagnostic_gaps import analyze_generated_prompt_local_diagnostic_gaps
from scripts.run_diagnostic_prompt_suite import DEFAULT_LIMIT, run_diagnostic_prompt_suite
from scripts.run_generated_prompt_suite_local_diagnostic import run_generated_prompt_suite_local_diagnostic
from scripts.review_local_diagnostic_gap_candidates import (
    build_fix_decision,
    review_local_diagnostic_gap_candidates,
)
from scripts.run_superpowers_next_steps_preflight import run_superpowers_next_steps_preflight


ROOT = Path(__file__).resolve().parents[1]


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text.lower())).strip()


def test_generated_prompt_suite_exists_and_has_required_shape():
    suite_path = ROOT / "data" / "generated_prompt_suite.json"
    summary_path = ROOT / "outputs" / "reports" / "generated_prompt_suite_summary.json"
    if not suite_path.exists() or not summary_path.exists():
        generate_prompt_suite()
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    assert len(suite) >= 200
    assert summary["source_id_mapping"][0]["source_query_id"] == "example_001"
    assert summary["source_id_mapping"][-1]["source_query_id"] == "example_035"
    assert summary["duplicate_count"] == 0
    assert summary["exact_copy_count_against_original_examples"] == 0

    prompt_ids = [item["prompt_id"] for item in suite]
    normalized_prompts = [_normalize(item["prompt"]) for item in suite]
    assert len(prompt_ids) == len(set(prompt_ids))
    assert len(normalized_prompts) == len(set(normalized_prompts))

    source_rows = json.loads((ROOT / "data" / "data.json").read_text(encoding="utf-8"))
    source_prompts = {_normalize(item["query"]) for item in source_rows}
    source_ids = {item["source_query_id"] for item in summary["source_id_mapping"]}
    for item in suite:
        assert item["prompt_id"]
        assert item["prompt"]
        assert item["generation_type"] in GENERATION_TYPES
        assert item["expected_route_diagnostic"] in ROUTES
        assert item["expected_answer_intent_diagnostic"] in INTENTS
        assert item["domain_family"] in DOMAINS
        assert item["diagnostic_only"] is True
        assert item["should_be_scored"] is False
        assert _normalize(item["prompt"]) not in source_prompts
        assert set(item.get("source_query_ids") or []).issubset(source_ids)


def test_generated_prompt_suite_does_not_embed_source_answers():
    suite_path = ROOT / "data" / "generated_prompt_suite.json"
    if not suite_path.exists():
        generate_prompt_suite()
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    source_rows = json.loads((ROOT / "data" / "data.json").read_text(encoding="utf-8"))
    full_generated_text = "\n".join(item["prompt"] for item in suite).lower()
    for index, row in enumerate(source_rows, start=1):
        answer = str(row.get("answer") or "").strip().lower()
        if len(answer) > 40:
            assert answer not in full_generated_text
        prompt_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", str(row.get("query") or "")))
        answer_only_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", answer)) - prompt_numbers
        source_id = f"example_{index:03d}"
        linked_prompt_text = "\n".join(
            item["prompt"] for item in suite if source_id in set(item.get("source_query_ids") or [])
        )
        for number in answer_only_numbers:
            assert not re.search(rf"\b{re.escape(number)}\b", linked_prompt_text)


def test_diagnostic_runner_limit_clean_and_isolated_outputs(tiny_project):
    suite_path = tiny_project.data_dir / "generated_prompt_suite.json"
    suite_path.write_text(
        json.dumps(
            [
                {
                    "prompt_id": "gen_test_0001",
                    "prompt": "List all journeys",
                    "generation_type": "domain_coverage",
                    "source_query_ids": ["tiny_001"],
                    "source_prompt": "How many campaigns are there?",
                    "expected_route_diagnostic": "SQL_ONLY",
                    "expected_answer_intent_diagnostic": "LIST",
                    "domain_family": "journey_campaign",
                    "target_tables_hint": ["dim_campaign"],
                    "target_api_hint": [],
                    "difficulty": "easy",
                    "should_be_scored": False,
                    "diagnostic_only": True,
                    "notes": "test",
                },
                {
                    "prompt_id": "gen_test_0002",
                    "prompt": "How many campaigns are there?",
                    "generation_type": "paraphrase",
                    "source_query_ids": ["tiny_001"],
                    "source_prompt": "How many campaigns are there?",
                    "expected_route_diagnostic": "SQL_ONLY",
                    "expected_answer_intent_diagnostic": "COUNT",
                    "domain_family": "journey_campaign",
                    "target_tables_hint": ["dim_campaign"],
                    "target_api_hint": [],
                    "difficulty": "easy",
                    "should_be_scored": False,
                    "diagnostic_only": True,
                    "notes": "test",
                },
            ]
        ),
        encoding="utf-8",
    )
    stale = tiny_project.outputs_dir / "diagnostic_prompt_suite" / "stale" / "old.txt"
    stale.parent.mkdir(parents=True, exist_ok=True)
    stale.write_text("old", encoding="utf-8")

    report = run_diagnostic_prompt_suite(tiny_project, suite_path=suite_path, limit=1, clean=True)

    assert report["executed_prompts"] == 1
    assert report["llm_runtime_used"] is False
    assert not stale.exists()
    assert (tiny_project.outputs_dir / "diagnostic_prompt_suite" / "gen_test_0001" / "trajectory.json").exists()
    assert (tiny_project.outputs_dir / "reports" / "diagnostic_prompt_suite_run.json").exists()


def test_diagnostic_runner_default_limit_constant():
    assert DEFAULT_LIMIT == 50


def test_official_eval_uses_data_json_not_generated_suite(tiny_project):
    (tiny_project.data_dir / "generated_prompt_suite.json").write_text(
        json.dumps([{"prompt_id": "gen_fake", "prompt": "This should not enter official eval."}]),
        encoding="utf-8",
    )
    examples = EvalHarness(tiny_project).load_examples()
    assert [example.query_id for example in examples] == ["tiny_001"]


def test_diagnostic_outputs_are_not_submission_outputs():
    assert "diagnostic_prompt_suite" in NON_SUBMISSION_OUTPUT_DIRS
    assert "generated_prompt_suite_local_diagnostic" in NON_SUBMISSION_OUTPUT_DIRS
    assert "llm_strict_eval" in NON_SUBMISSION_OUTPUT_DIRS
    assert "llm_controller_baseline_backend" in NON_SUBMISSION_OUTPUT_DIRS


def test_local_generated_prompt_diagnostic_is_dry_run_only(tiny_project):
    suite_path = tiny_project.data_dir / "generated_prompt_suite.json"
    suite_path.write_text(
        json.dumps(
            [
                {
                    "prompt_id": "local_gen_0001",
                    "prompt": "How many campaigns are there?",
                    "generation_type": "paraphrase",
                    "expected_route_diagnostic": "SQL_ONLY",
                    "expected_answer_intent_diagnostic": "COUNT",
                    "domain_family": "journey_campaign",
                    "diagnostic_only": True,
                    "should_be_scored": False,
                },
                {
                    "prompt_id": "local_gen_0002",
                    "prompt": "List all journeys",
                    "generation_type": "domain_coverage",
                    "expected_route_diagnostic": "SQL_ONLY",
                    "expected_answer_intent_diagnostic": "LIST",
                    "domain_family": "journey_campaign",
                    "diagnostic_only": True,
                    "should_be_scored": False,
                },
            ]
        ),
        encoding="utf-8",
    )

    report = run_generated_prompt_suite_local_diagnostic(tiny_project, suite_path=suite_path, clean=True)

    assert report["total_prompts"] == 2
    assert report["executed_prompts"] == 2
    assert report["diagnostic_only"] is True
    assert report["official_score_claim"] is False
    assert report["promotion_allowed"] is False
    assert report["dry_run_only"] is True
    assert report["live_api_calls"] == 0
    assert report["heuristics_are_advisory_only"] is True
    assert report["no_safe_deterministic_improvement_applied"] is True
    assert (tiny_project.outputs_dir / "generated_prompt_suite_local_diagnostic" / "local_gen_0001" / "trajectory.json").exists()
    assert (tiny_project.outputs_dir / "reports" / "generated_prompt_suite_local_diagnostic.json").exists()


def test_local_generated_prompt_gap_sampler_and_candidate_report(tiny_project):
    reports = tiny_project.outputs_dir / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    rows = []
    for idx in range(3):
        rows.append(
            {
                "prompt_id": f"gen_gap_{idx}",
                "prompt": f"How many unknown campaign records {idx}?",
                "domain_family": "journey_campaign",
                "answer_intent": "COUNT",
                "expected_route_label": "SQL_ONLY",
                "actual_route": "API_ONLY",
                "domain_type": "JOURNEY_CAMPAIGN",
                "actual_answer_intent": "COUNT",
                "route_matches_diagnostic": False,
                "domain_matches_diagnostic": True,
                "answer_intent_matches_diagnostic": True,
                "missing_count_or_name_advisory": True,
                "zero_row_sql": False,
                "requires_live_api": True,
                "sql_calls": 0,
                "api_calls": 1,
                "dry_run_count": 1,
                "sql_template": "unavailable",
                "evidence_state": "dry_run_unavailable",
                "final_answer": "The live API was unavailable in dry-run mode.",
            }
        )
    (reports / "generated_prompt_suite_local_diagnostic.json").write_text(
        json.dumps(
            {
                "report_type": "generated_prompt_suite_local_diagnostic",
                "total_prompts": 3,
                "executed_prompts": 3,
                "diagnostic_only": True,
                "official_score_claim": False,
                "rows": rows,
            }
        ),
        encoding="utf-8",
    )

    gap_report, candidate_report = analyze_generated_prompt_local_diagnostic_gaps(tiny_project)

    assert gap_report["diagnostic_only"] is True
    assert gap_report["official_score_claim"] is False
    assert gap_report["gap_types"]["route_mismatch"]["total_count"] == 3
    example = gap_report["gap_types"]["requires_live_api"]["representative_examples"][0]
    assert example["likely_cause"] == "live_api_required"
    assert example["suggested_action"] == "wait_for_live_api"
    assert candidate_report["promotion_allowed"] is False
    assert candidate_report["runtime_change_applied"] is False
    assert candidate_report["no_safe_deterministic_improvement_applied"] is True
    assert (reports / "generated_prompt_local_gap_samples.md").exists()
    assert (reports / "local_deterministic_improvement_candidates.md").exists()
    assert gap_report["recommended_next_human_review"]["runtime_change_allowed_from_this_report"] is False


def test_superpowers_preflight_records_protected_artifacts_and_blocks_changes(tiny_project, monkeypatch):
    reports = tiny_project.outputs_dir / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "system_summary.json").write_text(
        json.dumps(
            {
                "preferred_strategy": "SQL_FIRST_API_VERIFY",
                "packaged_strict_score": 0.6553,
                "hidden_style": {"label": "48/48", "passed": 48, "total": 48},
                "final_submission_ready": True,
            }
        ),
        encoding="utf-8",
    )
    (reports / "generated_prompt_suite_local_diagnostic.json").write_text(
        json.dumps({"diagnostic_only": True, "executed_prompts": 250, "runtime_pass_count": 250, "runtime_fail_count": 0}),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "scripts.run_superpowers_next_steps_preflight.collect_git_status",
        lambda root: {
            "mode": "test",
            "timed_out": False,
            "exit_code": 0,
            "line_count": 1,
            "lines": ["D  outputs/eval_results_strict.json"],
        },
    )

    payload = run_superpowers_next_steps_preflight(tiny_project)

    assert payload["blocker"] is True
    assert payload["blocker_reason"] == "protected_artifact_change_detected"
    assert "outputs/eval_results_strict.json" in payload["protected_artifacts"]
    assert "outputs/final_submission/**" in payload["protected_artifacts"]
    assert payload["runtime_changes_allowed"] is False
    assert "no_change_safety_rule" in payload
    assert (reports / "superpowers_next_steps_preflight.md").exists()


def test_manual_gap_review_compares_generated_labels_to_behavior_and_makes_no_change(tiny_project):
    reports = tiny_project.outputs_dir / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    rows = []
    for idx in range(3):
        prompt_id = f"gen_review_{idx}"
        out_dir = tiny_project.outputs_dir / "generated_prompt_suite_local_diagnostic" / prompt_id
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "trajectory.json").write_text(
            json.dumps(
                {
                    "steps": [
                        {
                            "kind": "sql_call",
                            "sql": "SELECT id FROM dim_target WHERE state = 'failed'",
                            "result": {"ok": True, "row_count": 0, "limited": False},
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        rows.append(
            {
                "prompt_id": prompt_id,
                "prompt": "Show failed dataflow runs",
                "domain_family": "dataflow_run",
                "answer_intent": "STATUS",
                "expected_route_label": "SQL_PLUS_API",
                "actual_route": "SQL_THEN_API",
                "domain_type": "DESTINATION_DATAFLOW",
                "actual_answer_intent": "STATUS",
                "route_matches_diagnostic": True,
                "domain_matches_diagnostic": False,
                "answer_intent_matches_diagnostic": True,
                "missing_count_or_name_advisory": False,
                "zero_row_sql": True,
                "requires_live_api": True,
                "sql_calls": 1,
                "api_calls": 1,
                "dry_run_count": 1,
                "sql_template": "generic_sql",
                "evidence_state": "dry_run_unavailable",
                "final_answer": "No matching local records; API verification was unavailable.",
                "output_dir": f"outputs/generated_prompt_suite_local_diagnostic/{prompt_id}",
            }
        )
    (reports / "generated_prompt_suite_local_diagnostic.json").write_text(
        json.dumps(
            {
                "report_type": "generated_prompt_suite_local_diagnostic",
                "total_prompts": 3,
                "executed_prompts": 3,
                "diagnostic_only": True,
                "official_score_claim": False,
                "rows": rows,
            }
        ),
        encoding="utf-8",
    )

    review, decision = review_local_diagnostic_gap_candidates(tiny_project)

    assert review["generated_labels_are_ground_truth"] is False
    category = next(item for item in review["reviewed_categories"] if item["category"] == "zero_row_sql / dataflow_run")
    assert category["reviewed_count"] == 3
    assert category["examples"][0]["generated_label_advisory_only"] is True
    assert "label_behavior_comparison" in category["examples"][0]
    assert category["examples"][0]["likely_cause"] == "live_api_required"
    assert decision["runtime_change_applied"] is False
    assert decision["no_safe_fix_after_manual_review"] is True
    assert (reports / "local_gap_manual_review.md").exists()
    assert (reports / "superpowers_fix_decision.md").exists()


def test_superpowers_fix_decision_blocks_multiple_ready_candidates():
    review = {
        "reviewed_categories": [
            {
                "category": "answer_intent_mismatch / segment_audience",
                "gap_type": "answer_intent_mismatch",
                "total_count": 4,
                "true_bug_count": 4,
                "implementation_candidate": True,
                "proposed_minimal_fix": "Add focused intent rule.",
                "risk_level": "low",
                "required_tests": ["intent test"],
            },
            {
                "category": "route_mismatch / destination_flow",
                "gap_type": "route_mismatch",
                "total_count": 3,
                "true_bug_count": 3,
                "implementation_candidate": True,
                "proposed_minimal_fix": "Add focused route synonym.",
                "risk_level": "low",
                "required_tests": ["route test"],
            },
        ]
    }

    decision = build_fix_decision(review)

    assert decision["implementation_ready_count"] == 2
    assert decision["runtime_change_applied"] is False
    assert decision["decision"] == "multiple_candidates_require_explicit_approval"
    assert len(decision["ranked_shortlist"]) == 2
