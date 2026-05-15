from __future__ import annotations

import json
import re
from pathlib import Path

from dashagent.eval_harness import EvalHarness
from scripts.generate_diagnostic_prompt_suite import DOMAINS, INTENTS, GENERATION_TYPES, ROUTES, generate_prompt_suite
from scripts.package_query_outputs import NON_SUBMISSION_OUTPUT_DIRS
from scripts.run_diagnostic_prompt_suite import DEFAULT_LIMIT, run_diagnostic_prompt_suite
from scripts.run_generated_prompt_suite_local_diagnostic import run_generated_prompt_suite_local_diagnostic


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
