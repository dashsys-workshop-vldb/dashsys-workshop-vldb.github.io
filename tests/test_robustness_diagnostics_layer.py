from __future__ import annotations

import json
from pathlib import Path

from scripts.run_dashagent_500_prompt_suite_eval import _runtime_input


def test_score_provenance_blocks_simulated_trace_from_promotion() -> None:
    from dashagent.score_provenance import build_score_provenance

    provenance = build_score_provenance(
        score_source="simulated_trace",
        real_agent_execution=False,
        synthetic_trace=True,
        grading_type="diagnostic_simulated_trace",
        evaluator_script="scripts/run_dashagent_500_prompt_suite_eval.py",
        dataset_path="data/benchmarks/dashagent_500_prompt_suite.jsonl",
    )

    payload = provenance.to_dict()
    assert payload["promotion_eligible"] is False
    assert payload["organizer_equivalent"] is False
    assert payload["runtime_gold_visible"] is False


def test_score_provenance_marks_organizer_strict_as_promotion_eligible() -> None:
    from dashagent.score_provenance import build_score_provenance

    provenance = build_score_provenance(
        score_source="organizer_strict",
        real_agent_execution=True,
        synthetic_trace=False,
        grading_type="organizer_style_strict",
        evaluator_script="scripts/run_dev_eval.py",
        dataset_path="data/data.json",
    )

    payload = provenance.to_dict()
    assert payload["promotion_eligible"] is True
    assert payload["organizer_equivalent"] is True


def test_real_benchmark_runtime_input_keeps_only_prompt_id_and_prompt() -> None:
    row = {
        "prompt_id": "da500_0001",
        "prompt": "List schemas.",
        "category": "sql_only",
        "tags": ["forbidden_runtime_metadata"],
        "domain_family": "SCHEMA",
    }

    assert _runtime_input(row) == {"prompt_id": "da500_0001", "prompt": "List schemas."}


def test_hardcode_audit_classifies_eval_gold_after_execution_as_safe() -> None:
    from scripts.audit_hardcoded_runtime_and_score_paths import classify_hit

    hit = classify_hit(
        path=Path("scripts/run_dashagent_500_prompt_suite_eval.py"),
        line='gold_row = gold_by_id[prompt_id]',
        term="gold",
        line_number=10,
    )

    assert hit["classification"] == "safe_eval_only_after_execution"
    assert hit["promotion_blocker"] is False


def test_hardcode_audit_flags_prompt_id_runtime_conditionals() -> None:
    from scripts.audit_hardcoded_runtime_and_score_paths import classify_hit

    hit = classify_hit(
        path=Path("dashagent/executor.py"),
        line='if query_id == "example_001": return "special answer"',
        term="query_id",
        line_number=42,
    )

    assert hit["classification"] == "unsafe_runtime_hardcode"
    assert hit["promotion_blocker"] is True


def test_diagnostics_gate_rejects_simulated_trace_promotion(tmp_path: Path) -> None:
    from scripts.run_diagnostics_only_gate import build_diagnostics_only_gate

    reports = tmp_path / "outputs" / "reports"
    reports.mkdir(parents=True)
    (reports / "score_provenance_audit.json").write_text(
        json.dumps(
            {
                "summary": {
                    "promotion_ineligible_simulated_reports": 1,
                    "unsafe_runtime_hardcode_count": 0,
                    "unsafe_fake_score_count": 0,
                }
            }
        ),
        encoding="utf-8",
    )

    gate = build_diagnostics_only_gate(
        reports_dir=reports,
        packaged_default_strategy="SQL_FIRST_API_VERIFY",
        check_submission_ready_ok=True,
        hidden_style_ok=True,
        pytest_ok=True,
        secret_scan_ok=True,
    )

    assert gate["packaged_default_strategy"] == "SQL_FIRST_API_VERIFY"
    assert gate["simulated_trace_promotion_eligible"] is False
