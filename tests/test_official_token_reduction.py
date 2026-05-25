from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import replace
from hashlib import sha256
from pathlib import Path

from dashagent.config import Config
from dashagent.eval_harness import first_generated_sql, generated_api_calls
from dashagent.executor import AgentExecutor
from dashagent.token_reduction_policy import (
    apply_token_reduction_to_trajectory,
    compact_preview_rows,
    official_estimated_tokens,
)
from scripts.generate_official_token_accounting_report import generate_official_token_accounting_report
from scripts.package_query_outputs import NON_SUBMISSION_OUTPUT_DIRS, discover_query_output_dirs
from scripts.run_official_token_reduction_canary import (
    _canary_safe,
    _summary as _canary_summary,
    protected_output_hash_snapshot,
    run_official_token_reduction_canary,
)
from scripts.run_official_token_reduction_eval import (
    REQUIRED_ROW_FIELDS,
    _reduction_safe,
    run_official_token_reduction_eval,
)


def test_official_token_reduction_flag_defaults_and_env(monkeypatch, tiny_project):
    monkeypatch.delenv("ENABLE_OFFICIAL_TOKEN_REDUCTION", raising=False)
    monkeypatch.setenv("DASHAGENT_ROOT", str(tiny_project.project_root))
    assert Config.from_env(tiny_project.project_root).enable_official_token_reduction is True

    monkeypatch.setenv("ENABLE_OFFICIAL_TOKEN_REDUCTION", "0")
    assert Config.from_env(tiny_project.project_root).enable_official_token_reduction is False

    monkeypatch.setenv("ENABLE_OFFICIAL_TOKEN_REDUCTION", "1")
    assert Config.from_env(tiny_project.project_root).enable_official_token_reduction is True


def test_token_reduction_policy_preserves_required_and_score_critical_fields():
    trajectory = _sample_verbose_trajectory()

    reduced, summary = apply_token_reduction_to_trajectory(trajectory)

    assert reduced["final_answer"] == trajectory["final_answer"]
    assert first_generated_sql(reduced) == first_generated_sql(trajectory)
    assert generated_api_calls(reduced) == generated_api_calls(trajectory)
    assert reduced["steps"][2]["result"]["dry_run"] is True
    assert reduced["steps"][2]["validation"]["ok"] is True
    for field in ["final_answer", "tool_call_count", "runtime", "estimated_tokens"]:
        assert field in reduced
    assert summary["estimated_tokens_before"] >= summary["estimated_tokens_after"]
    assert summary["estimated_tokens_after"] == official_estimated_tokens(json.loads(json.dumps(reduced, sort_keys=True)))

    checkpoint = reduced["checkpoints"][-1]
    assert checkpoint["checkpoint_id"] == "checkpoint_official_token_reduction"
    assert set(checkpoint) == {
        "checkpoint_id",
        "active",
        "reduced_fields",
        "estimated_tokens_before",
        "estimated_tokens_after",
        "expected_savings",
        "packaged_execution_changed",
        "correctness_impact_expected",
    }
    assert _max_string_length(checkpoint) <= 120


def test_compact_preview_rows_is_deterministic():
    rows = [{"name": "x" * 300, "count": 1}, {"name": "second", "count": 2}]

    first = compact_preview_rows(rows, max_rows=1, max_cell_chars=40)
    second = compact_preview_rows(rows, max_rows=1, max_cell_chars=40)

    assert first == second
    assert len(first) == 1
    assert len(first[0]["name"]) <= 40


def test_official_token_accounting_report_rows_and_packaged_outputs(tiny_project):
    _write_official_token_inputs(tiny_project)
    final_submission = tiny_project.outputs_dir / "final_submission"
    final_submission.mkdir(parents=True)
    (final_submission / "trajectory.json").write_text(json.dumps({"strategy": "SQL_FIRST_API_VERIFY"}), encoding="utf-8")
    before_hash = _tree_hash(final_submission)

    payload = generate_official_token_accounting_report(tiny_project)

    assert payload["packaged_execution_changed"] is False
    assert payload["aggregate"]["top_global_token_contributors"]
    assert payload["aggregate"]["recommended_safe_reductions"]
    assert payload["rows"]
    row = payload["rows"][0]
    assert row["component_breakdown"]
    assert row["top_5_token_components"]
    assert _tree_hash(final_submission) == before_hash


def test_official_token_reduction_eval_isolated_and_formula_exact(tiny_project):
    _write_official_token_inputs(tiny_project)

    payload = run_official_token_reduction_eval(tiny_project)

    assert payload["feature_flag_default"] is True
    assert payload["feature_flag_enabled_for_experiment"] is True
    assert payload["packaged_execution_changed"] is False
    assert payload["summary"]["total_rows"] == 1
    row = payload["rows"][0]
    for field in REQUIRED_ROW_FIELDS:
        assert field in row
    assert row["baseline_formula_matches"] is True
    assert row["reduced_formula_matches"] is True
    assert row["reduced_estimated_tokens"] == row["reduced_formula_tokens"]
    assert row["required_fields_preserved"] is True
    assert row["live_api_evidence_fabricated"] is False
    assert (tiny_project.outputs_dir / "official_token_reduction_eval" / "tiny_001" / "reduced_sql_first" / "trajectory.json").exists()
    assert not (tiny_project.outputs_dir / "eval").exists()
    assert not (tiny_project.outputs_dir / "final_submission").exists()


def test_official_token_reduction_script_writes_only_allowed_outputs(tiny_project):
    _write_official_token_inputs(tiny_project)
    env = os.environ.copy()
    env.update(
        {
            "DASHAGENT_ROOT": str(tiny_project.project_root),
            "DASHAGENT_DATA_DIR": str(tiny_project.data_dir),
            "DASHAGENT_DBSNAPSHOT_DIR": str(tiny_project.dbsnapshot_dir),
            "DASHAGENT_DATA_JSON": str(tiny_project.data_json_path),
            "DASHAGENT_OUTPUTS_DIR": str(tiny_project.outputs_dir),
            "DASHAGENT_PROMPTS_DIR": str(tiny_project.prompts_dir),
        }
    )
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(root / "scripts" / "run_official_token_reduction_eval.py")],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    outputs = tiny_project.outputs_dir
    assert (outputs / "official_token_reduction_eval.json").exists()
    assert (outputs / "official_token_reduction_eval.md").exists()
    assert (outputs / "official_token_reduction_eval" / "tiny_001" / "reduced_sql_first" / "trajectory.json").exists()
    assert not (outputs / "eval").exists()
    assert not (outputs / "final_submission").exists()


def test_official_token_reduction_canary_isolated_and_hash_protected(tiny_project):
    _write_official_token_inputs(tiny_project)
    final_submission = tiny_project.outputs_dir / "final_submission"
    final_submission.mkdir(parents=True)
    (final_submission / "manifest.json").write_text(json.dumps({"preferred_strategy": "SQL_FIRST_API_VERIFY"}), encoding="utf-8")
    before_final_submission_hash = _tree_hash(final_submission)
    before_hashes = protected_output_hash_snapshot(tiny_project)

    payload = run_official_token_reduction_canary(tiny_project)

    assert payload["feature_flag_default"] is True
    assert payload["feature_flag_enabled_for_canary"] is True
    assert payload["packaged_execution_changed"] is False
    assert payload["protected_output_hashes_unchanged"] is True
    assert payload["protected_output_hashes_before"] == before_hashes
    assert payload["protected_output_hashes_after"] == protected_output_hash_snapshot(tiny_project)
    assert payload["summary"]["total_rows"] == 1
    row = payload["rows"][0]
    assert row["canary_formula_matches"] is True
    assert row["strict_scorer_check_passed"] is True
    assert row["required_fields_preserved"] is True
    assert row["live_api_evidence_fabricated"] is False
    assert (tiny_project.outputs_dir / "official_token_reduction_canary" / "tiny_001" / "sql_first_api_verify" / "trajectory.json").exists()
    assert not (tiny_project.outputs_dir / "eval").exists()
    assert _tree_hash(final_submission) == before_final_submission_hash


def test_official_token_reduction_canary_script_writes_only_allowed_outputs(tiny_project):
    _write_official_token_inputs(tiny_project)
    env = os.environ.copy()
    env.update(
        {
            "DASHAGENT_ROOT": str(tiny_project.project_root),
            "DASHAGENT_DATA_DIR": str(tiny_project.data_dir),
            "DASHAGENT_DBSNAPSHOT_DIR": str(tiny_project.dbsnapshot_dir),
            "DASHAGENT_DATA_JSON": str(tiny_project.data_json_path),
            "DASHAGENT_OUTPUTS_DIR": str(tiny_project.outputs_dir),
            "DASHAGENT_PROMPTS_DIR": str(tiny_project.prompts_dir),
        }
    )
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(root / "scripts" / "run_official_token_reduction_canary.py")],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    outputs = tiny_project.outputs_dir
    assert (outputs / "official_token_reduction_canary.json").exists()
    assert (outputs / "official_token_reduction_canary.md").exists()
    assert (outputs / "official_token_reduction_canary" / "tiny_001" / "sql_first_api_verify" / "trajectory.json").exists()
    assert not (outputs / "eval").exists()
    assert not (outputs / "final_submission").exists()


def test_reduction_safe_to_enable_requires_all_gates():
    safe_row = {
        "score_delta": 0.0,
        "token_delta": -5,
        "tool_delta": 0,
        "final_answer_changed": False,
        "sql_changed": False,
        "api_changed": False,
        "required_fields_preserved": True,
        "dry_run_labels_preserved": True,
        "live_api_evidence_fabricated": False,
        "baseline_formula_matches": True,
        "reduced_formula_matches": True,
    }
    assert _reduction_safe(safe_row)[0] is True

    for key, value in [
        ("score_delta", -0.1),
        ("token_delta", 0),
        ("tool_delta", 1),
        ("final_answer_changed", True),
        ("sql_changed", True),
        ("api_changed", True),
        ("required_fields_preserved", False),
        ("dry_run_labels_preserved", False),
        ("live_api_evidence_fabricated", True),
        ("reduced_formula_matches", False),
    ]:
        row = dict(safe_row)
        row[key] = value
        assert _reduction_safe(row)[0] is False


def test_canary_safe_to_promote_requires_all_gates():
    safe_row = {
        "score_delta": 0.0,
        "token_delta": -5,
        "tool_delta": 0,
        "final_answer_changed": False,
        "sql_changed": False,
        "api_changed": False,
        "required_fields_preserved": True,
        "dry_run_labels_preserved": True,
        "live_api_evidence_fabricated": False,
        "canary_formula_matches": True,
        "strict_scorer_check_passed": True,
        "protected_hashes_unchanged": True,
    }
    assert _canary_safe(safe_row)[0] is True

    for key, value in [
        ("score_delta", -0.1),
        ("token_delta", 0),
        ("tool_delta", 1),
        ("final_answer_changed", True),
        ("sql_changed", True),
        ("api_changed", True),
        ("required_fields_preserved", False),
        ("dry_run_labels_preserved", False),
        ("live_api_evidence_fabricated", True),
        ("canary_formula_matches", False),
        ("strict_scorer_check_passed", False),
        ("protected_hashes_unchanged", False),
    ]:
        row = dict(safe_row)
        row[key] = value
        assert _canary_safe(row)[0] is False


def test_canary_summary_recommends_trial_only_when_all_gates_pass():
    safe_row = {
        "canary_safe_to_promote": True,
        "score_delta": 0.0,
        "token_delta": -5,
        "runtime_delta": 0.0,
        "tool_delta": 0,
        "final_answer_changed": False,
        "sql_changed": False,
        "api_changed": False,
        "required_fields_preserved": True,
        "dry_run_labels_preserved": True,
        "live_api_evidence_fabricated": False,
        "canary_formula_matches": True,
        "strict_scorer_check_passed": True,
    }

    assert _canary_summary([safe_row], protected_unchanged=True)["recommendation"] == "safe_for_packaged_flag_trial"
    row = dict(safe_row)
    row["canary_safe_to_promote"] = False
    row["token_delta"] = 0
    assert _canary_summary([row], protected_unchanged=True)["recommendation"] == "unsafe_do_not_enable"
    assert _canary_summary([safe_row], protected_unchanged=False)["recommendation"] == "unsafe_do_not_enable"
    assert _canary_summary([], protected_unchanged=True)["recommendation"] == "keep_default_off"


def test_official_token_canary_is_excluded_from_query_packaging(tiny_project):
    canary_dir = tiny_project.outputs_dir / "official_token_reduction_canary" / "tiny_001" / "sql_first_api_verify"
    canary_dir.mkdir(parents=True)
    (canary_dir / "metadata.json").write_text("{}", encoding="utf-8")
    (canary_dir / "filled_system_prompt.txt").write_text("prompt", encoding="utf-8")
    (canary_dir / "trajectory.json").write_text(
        json.dumps({"query_id": "tiny_001", "strategy": "SQL_FIRST_API_VERIFY", "final_answer": "x", "tool_call_count": 1, "runtime": 0.0, "estimated_tokens": 1}),
        encoding="utf-8",
    )

    assert "official_token_reduction_canary" in NON_SUBMISSION_OUTPUT_DIRS
    assert canary_dir not in discover_query_output_dirs(tiny_project.outputs_dir)


def test_official_token_defaults_keep_repair_and_compact_disabled(tiny_project):
    config = Config.from_env(tiny_project.project_root)

    assert config.enable_official_token_reduction is True
    assert config.enable_gated_risk_cluster_repair_execution is False
    assert config.enable_compact_context_when_schema_vote_safe is False


def test_official_token_flag_off_preserves_sql_first_outputs_and_submission_hash(tiny_project):
    final_submission = tiny_project.outputs_dir / "final_submission"
    final_submission.mkdir(parents=True)
    (final_submission / "trajectory.json").write_text(json.dumps({"strategy": "SQL_FIRST_API_VERIFY"}), encoding="utf-8")
    before_hash = _tree_hash(final_submission)
    config = replace(tiny_project, enable_official_token_reduction=False)
    executor = AgentExecutor(config)

    first = executor.run("How many campaigns are there?", strategy="SQL_FIRST_API_VERIFY", query_id="tiny_001", output_dir=tiny_project.outputs_dir / "flag_off_a")
    second = executor.run("How many campaigns are there?", strategy="SQL_FIRST_API_VERIFY", query_id="tiny_001", output_dir=tiny_project.outputs_dir / "flag_off_b")

    assert first_generated_sql(first["trajectory"]) == first_generated_sql(second["trajectory"])
    assert generated_api_calls(first["trajectory"]) == generated_api_calls(second["trajectory"])
    assert first["final_answer"] == second["final_answer"]
    assert first["trajectory"]["tool_call_count"] == second["trajectory"]["tool_call_count"]
    assert "checkpoint_official_token_reduction" not in json.dumps(first["trajectory"])
    assert _tree_hash(final_submission) == before_hash


def _write_official_token_inputs(config: Config) -> None:
    executor = AgentExecutor(config)
    trajectory_dir = config.outputs_dir / "current" / "sql_first_api_verify"
    result = executor.run(
        "How many campaigns are there?",
        strategy="SQL_FIRST_API_VERIFY",
        query_id="tiny_001",
        output_dir=trajectory_dir,
    )
    trajectory = result["trajectory"]
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    (config.outputs_dir / "eval_results_strict.json").write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "query_id": "tiny_001",
                        "strategy": "SQL_FIRST_API_VERIFY",
                        "query": "How many campaigns are there?",
                        "final_score": 0.0,
                        "tool_call_count": trajectory.get("tool_call_count"),
                        "estimated_tokens": trajectory.get("estimated_tokens"),
                        "runtime": trajectory.get("runtime"),
                        "output_dir": str(trajectory_dir),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )


def _sample_verbose_trajectory() -> dict:
    long_cell = "A" * 500
    return {
        "query_id": "sample",
        "original_query": "Which rows should be listed?",
        "strategy": "SQL_FIRST_API_VERIFY",
        "route_type": "SQL_ONLY",
        "domain_type": "CAMPAIGN",
        "steps": [
            {
                "kind": "sql_call",
                "sql": "SELECT name FROM dim_campaign",
                "validation": {"ok": True, "errors": [], "warnings": ["same", "same"]},
                "result": {"ok": True, "row_count": 2, "rows": [{"name": long_cell}, {"name": "second"}]},
            },
            {
                "kind": "plan",
                "strategy": "SQL_FIRST_API_VERIFY",
                "rationale": "r" * 500,
                "steps": [{"action": "sql", "sql": "SELECT name FROM dim_campaign"}],
            },
            {
                "kind": "api_call",
                "method": "GET",
                "url": "/data/test",
                "params": {"x": "y"},
                "headers": {},
                "validation": {"ok": True, "errors": [], "warnings": []},
                "result": {
                    "ok": False,
                    "dry_run": True,
                    "error": "Adobe credentials unavailable; API call not executed.",
                    "preview": "P" * 500,
                    "result_preview": [{"value": long_cell}],
                },
            },
        ],
        "checkpoints": [{"checkpoint_id": "verbose", "output": "c" * 500}],
        "final_answer": "Rows are listed from SQL evidence.",
        "runtime": 0.01,
        "tool_call_count": 2,
        "sql_call_count": 1,
        "api_call_count": 1,
        "timings": {},
        "errors": [],
    }


def _max_string_length(value) -> int:
    if isinstance(value, str):
        return len(value)
    if isinstance(value, list):
        return max([0, *(_max_string_length(item) for item in value)])
    if isinstance(value, dict):
        return max([0, *(_max_string_length(item) for item in value.values())])
    return 0


def _tree_hash(root: Path) -> str:
    digest = sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file():
            digest.update(str(path.relative_to(root)).encode("utf-8"))
            digest.update(path.read_bytes())
    return digest.hexdigest()
