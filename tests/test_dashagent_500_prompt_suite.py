from __future__ import annotations

import json
from pathlib import Path

from scripts.generate_dashagent_500_prompt_suite import CATEGORY_TARGETS, generate_suite
from scripts.run_dashagent_500_prompt_suite_eval import RECOGNIZED_MODES, run_suite_eval
from scripts.validate_dashagent_500_prompt_suite import validate_suite


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_generate_suite_writes_500_runtime_and_gold_rows(tmp_path: Path) -> None:
    out = tmp_path / "benchmarks"
    report_dir = tmp_path / "reports"

    manifest = generate_suite(out_dir=out, report_dir=report_dir, seed=20260525)

    runtime_rows = _read_jsonl(out / "dashagent_500_prompt_suite.jsonl")
    gold_rows = _read_jsonl(out / "dashagent_500_prompt_suite_gold.jsonl")
    assert manifest["total_prompts"] == 500
    assert len(runtime_rows) == 500
    assert len(gold_rows) == 500
    assert manifest["category_distribution"] == CATEGORY_TARGETS
    assert {row["prompt_id"] for row in runtime_rows} == {row["prompt_id"] for row in gold_rows}
    assert not ({"gold_answer", "oracle_evidence", "expected_observable_trace"} & runtime_rows[0].keys())
    assert {"gold_answer", "oracle_evidence", "expected_observable_trace", "grading_rubric"} <= gold_rows[0].keys()


def test_validation_rejects_gold_leakage_and_accepts_generated_suite(tmp_path: Path) -> None:
    out = tmp_path / "benchmarks"
    report_dir = tmp_path / "reports"
    generate_suite(out_dir=out, report_dir=report_dir, seed=20260525)

    ok = validate_suite(suite_path=out / "dashagent_500_prompt_suite.jsonl", gold_path=out / "dashagent_500_prompt_suite_gold.jsonl", manifest_path=out / "dashagent_500_prompt_suite_manifest.json", report_dir=report_dir)
    assert ok["ok"] is True
    assert ok["total_prompts"] == 500
    assert ok["runtime_gold_field_leak_count"] == 0
    assert ok["private_chain_of_thought_count"] == 0

    leaked = _read_jsonl(out / "dashagent_500_prompt_suite.jsonl")
    leaked[0]["gold_answer"] = "leak"
    (out / "dashagent_500_prompt_suite.jsonl").write_text("\n".join(json.dumps(row) for row in leaked) + "\n", encoding="utf-8")
    bad = validate_suite(suite_path=out / "dashagent_500_prompt_suite.jsonl", gold_path=out / "dashagent_500_prompt_suite_gold.jsonl", manifest_path=out / "dashagent_500_prompt_suite_manifest.json", report_dir=report_dir)
    assert bad["ok"] is False
    assert bad["runtime_gold_field_leak_count"] == 1


def test_suite_contains_required_semantic_and_post_sql_stress_cases(tmp_path: Path) -> None:
    out = tmp_path / "benchmarks"
    report_dir = tmp_path / "reports"
    generate_suite(out_dir=out, report_dir=report_dir, seed=20260525)
    gold = _read_jsonl(out / "dashagent_500_prompt_suite_gold.jsonl")
    tags = {tag for row in _read_jsonl(out / "dashagent_500_prompt_suite.jsonl") for tag in row.get("tags", [])}

    assert {"anti_hallucination_no_tool_conflict", "anti_hallucination_unknown_capability", "mixed_no_tool_block", "low_low_safe_direct", "low_low_safe_api_probe", "post_sql_advisor_accept", "post_sql_advisor_block", "invalid_json_fallback"} <= tags
    assert any(step["stage"] == "objective_features" for row in gold for step in row["expected_observable_trace"])
    assert any((row["oracle_evidence"] or {}).get("oracle_sql") for row in gold)
    assert any((row["oracle_evidence"] or {}).get("oracle_api_endpoint") for row in gold)


def test_eval_runner_recognizes_latest_modes_and_isolates_outputs(tmp_path: Path) -> None:
    out = tmp_path / "benchmarks"
    report_dir = tmp_path / "reports"
    eval_dir = tmp_path / "eval"
    generate_suite(out_dir=out, report_dir=report_dir, seed=20260525)

    assert {
        "packaged_baseline",
        "semantic_routing_shadow",
        "staged_evidence_shadow",
        "post_sql_api_decision_shadow",
        "latest_applied_trial",
        "latest_full_trial",
    } <= RECOGNIZED_MODES

    result = run_suite_eval(
        suite_path=out / "dashagent_500_prompt_suite.jsonl",
        gold_path=out / "dashagent_500_prompt_suite_gold.jsonl",
        output_dir=eval_dir,
        report_dir=report_dir,
        modes=["packaged_baseline", "latest_applied_trial"],
        limit=8,
        seed=20260525,
        clean=True,
    )

    assert result["prompt_count"] == 8
    assert set(result["modes"]) == {"packaged_baseline", "latest_applied_trial"}
    assert result["mode_summary"]["latest_applied_trial"]["latest_code_paths_enabled"]["semantic_route_decision_ladder"] is True
    assert result["mode_summary"]["latest_applied_trial"]["old_generated_diagnostic_path_used"] is False
    assert (eval_dir / "packaged_baseline").is_dir()
    assert (eval_dir / "latest_applied_trial").is_dir()
    assert len(list((eval_dir / "latest_applied_trial").glob("*/trajectory.json"))) == 8
