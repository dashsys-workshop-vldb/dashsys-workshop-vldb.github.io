from __future__ import annotations

import inspect
import json

from dashagent.agent_tools import DEFAULT_AGENT_STRATEGY
from dashagent.executor import AgentExecutor
from dashagent.planner import PACKAGED_DEFAULT_STRATEGY
from scripts import check_submission_ready, package_query_outputs


def _write_packaging_source(root, query_id: str, strategy: str) -> None:
    directory = root / query_id / strategy.lower()
    directory.mkdir(parents=True)
    (directory / "metadata.json").write_text("{}", encoding="utf-8")
    (directory / "filled_system_prompt.txt").write_text("prompt", encoding="utf-8")
    (directory / "trajectory.json").write_text(
        json.dumps(
            {
                "query_id": query_id,
                "original_query": "List schemas",
                "strategy": strategy,
                "final_answer": "done",
                "tool_call_count": 1,
                "runtime": 0.01,
                "estimated_tokens": 10,
                "steps": [{"kind": "plan", "steps": []}],
            }
        ),
        encoding="utf-8",
    )


def test_packaged_default_strategy_constant_is_sql_first_after_failed_gate_revert() -> None:
    assert PACKAGED_DEFAULT_STRATEGY == "SQL_FIRST_API_VERIFY"
    assert DEFAULT_AGENT_STRATEGY == PACKAGED_DEFAULT_STRATEGY
    assert inspect.signature(AgentExecutor.run).parameters["strategy"].default == PACKAGED_DEFAULT_STRATEGY
    assert package_query_outputs.PACKAGED_DEFAULT_STRATEGY == PACKAGED_DEFAULT_STRATEGY
    assert check_submission_ready.EXPECTED_PACKAGED_STRATEGY == PACKAGED_DEFAULT_STRATEGY


def test_package_query_outputs_defaults_to_packaged_strategy(tiny_project, monkeypatch) -> None:
    monkeypatch.delenv("DASHAGENT_SUBMISSION_STRATEGY", raising=False)
    _write_packaging_source(tiny_project.outputs_dir, "tiny_001", "SQL_FIRST_API_VERIFY")

    manifest = package_query_outputs.package_query_outputs(tiny_project)

    assert manifest["preferred_strategy"] == PACKAGED_DEFAULT_STRATEGY
    assert manifest["total_number_of_queries"] == 1
    assert manifest["queries"][0]["strategy"] == PACKAGED_DEFAULT_STRATEGY


def test_package_query_outputs_excludes_internal_500_eval_rows(tiny_project, monkeypatch) -> None:
    monkeypatch.delenv("DASHAGENT_SUBMISSION_STRATEGY", raising=False)
    _write_packaging_source(tiny_project.outputs_dir, "official_001", PACKAGED_DEFAULT_STRATEGY)
    _write_packaging_source(tiny_project.outputs_dir / "eval", "da500_0001", PACKAGED_DEFAULT_STRATEGY)

    manifest = package_query_outputs.package_query_outputs(tiny_project)

    assert manifest["total_number_of_queries"] == 1
    assert manifest["queries"][0]["original_query"] == "List schemas"
    assert "da500_0001" not in manifest["queries"][0]["source_dir"]


def test_submission_readiness_accepts_candidate_packaged_outputs(tiny_project) -> None:
    tiny_project.outputs_dir.mkdir(parents=True, exist_ok=True)
    (tiny_project.outputs_dir / "source_code.zip").write_bytes(b"zip")
    final_dir = tiny_project.outputs_dir / "final_submission"
    qdir = final_dir / "query_001"
    qdir.mkdir(parents=True)
    (final_dir / "system_prompt_template.txt").write_text("prompt", encoding="utf-8")
    (final_dir / "source_code.zip").write_bytes(b"zip")
    (qdir / "metadata.json").write_text("{}", encoding="utf-8")
    (qdir / "filled_system_prompt.txt").write_text("filled", encoding="utf-8")
    (qdir / "trajectory.json").write_text(
        json.dumps(
            {
                "query_id": "tiny_001",
                "strategy": PACKAGED_DEFAULT_STRATEGY,
                "final_answer": "done",
                "tool_call_count": 0,
                "runtime": 0.01,
                "estimated_tokens": 10,
                "steps": [{"kind": "plan", "steps": []}],
            }
        ),
        encoding="utf-8",
    )
    (tiny_project.outputs_dir / "final_submission_manifest.json").write_text(
        json.dumps({"preferred_strategy": PACKAGED_DEFAULT_STRATEGY}),
        encoding="utf-8",
    )
    for name in [
        "failure_analysis.json",
        "family_score_report.json",
        "pareto_report.json",
        "threshold_tuning_report.json",
        "robustness_eval.json",
    ]:
        (tiny_project.outputs_dir / name).write_text("{}", encoding="utf-8")
    for name in [
        "failure_analysis.md",
        "family_score_report.md",
        "pareto_report.md",
        "threshold_tuning_report.md",
        "robustness_eval.md",
    ]:
        (tiny_project.outputs_dir / name).write_text("ok", encoding="utf-8")

    report = check_submission_ready.check_submission_ready(tiny_project)

    assert report["ok"] is True
    assert report["expected_packaged_strategy"] == PACKAGED_DEFAULT_STRATEGY
    assert report["default_strategy_is_expected_packaged_strategy"] is True
