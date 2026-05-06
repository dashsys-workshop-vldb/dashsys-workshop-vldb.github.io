from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import replace
from hashlib import sha256
from pathlib import Path

from dashagent.eval_harness import first_generated_sql, generated_api_calls
from dashagent.executor import AgentExecutor
from scripts.run_compact_context_measured_eval import run_compact_context_measured_eval
from scripts.run_compact_context_shadow_eval import run_compact_context_shadow_eval
from scripts.run_risk_efficiency_shadow_eval import run_risk_efficiency_shadow_eval


def test_compact_and_risk_shadow_reports_replay_current_outputs(tiny_project):
    _write_shadow_inputs(tiny_project)

    compact_one = run_compact_context_shadow_eval(tiny_project)
    compact_two = run_compact_context_shadow_eval(tiny_project)
    risk_one = run_risk_efficiency_shadow_eval(tiny_project)
    risk_two = run_risk_efficiency_shadow_eval(tiny_project)

    assert compact_one == compact_two
    assert risk_one == risk_two
    assert compact_one["summary"]["row_count"] == 1
    assert risk_one["summary"]["row_count"] == 1
    compact_row = compact_one["rows"][0]
    risk_row = risk_one["rows"][0]
    assert compact_row["schema_vote_agreement"] is True
    assert compact_row["compact_context_safe"] is True
    assert compact_row["score_delta"] == 0.0
    assert compact_row["tool_call_delta"] == 0
    assert compact_row["final_answer_difference"] is False
    assert risk_row["score_delta"] == 0.0
    assert risk_row["tool_call_delta"] == 0
    assert risk_row["token_delta"] < 0
    for payload in [compact_one, risk_one]:
        summary = payload["summary"]
        assert summary["packaged_execution_changed"] is False
        assert summary["measured_accuracy_improvement_claimed"] is False
        assert summary["measured_efficiency_improvement_claimed"] is False
        assert summary["behavior_changing_flags_note"] == "No behavior-changing flags were enabled in this pass."


def test_shadow_efficiency_scripts_write_only_allowed_outputs(tiny_project):
    _write_shadow_inputs(tiny_project)
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
    for script_name in ["run_compact_context_shadow_eval.py", "run_risk_efficiency_shadow_eval.py"]:
        result = subprocess.run([sys.executable, str(root / "scripts" / script_name)], cwd=root, env=env, text=True, capture_output=True)
        assert result.returncode == 0, result.stderr

    outputs = tiny_project.outputs_dir
    assert (outputs / "compact_context_shadow_eval.json").exists()
    assert (outputs / "compact_context_shadow_eval.md").exists()
    assert (outputs / "risk_efficiency_shadow_eval.json").exists()
    assert (outputs / "risk_efficiency_shadow_eval.md").exists()
    assert not (outputs / "final_submission").exists()
    assert not any(path.name == "compact_context_shadow_eval.json" and "eval" in path.parts for path in outputs.rglob("*"))
    assert not any(path.name == "risk_efficiency_shadow_eval.json" and "eval" in path.parts for path in outputs.rglob("*"))


def test_compact_context_measured_eval_isolated_and_experimental(tiny_project):
    _write_measured_inputs(tiny_project)

    assert tiny_project.enable_compact_context_when_schema_vote_safe is False
    payload_one = run_compact_context_measured_eval(tiny_project)
    payload_two = run_compact_context_measured_eval(tiny_project)

    assert payload_one["shadow_safety_gate"]["ok"] is True
    assert payload_one["summary"]["row_count"] == 1
    assert payload_two["summary"]["row_count"] == 1
    assert payload_one["rows"][0]["query_id"] == payload_two["rows"][0]["query_id"]
    row = payload_one["rows"][0]
    assert row["schema_vote_agreement"] is True
    assert row["compact_context_safe"] is True
    assert "score_delta" in row
    assert "token_delta" in row
    assert "runtime_delta" in row
    assert "experiment_safe_to_enable" in row
    assert payload_one["packaged_execution_changed"] is False
    assert payload_one["official_submission_metrics_updated"] is False
    assert payload_one["summary"]["official_measured_efficiency_improvement_claimed"] is False
    assert (tiny_project.outputs_dir / "compact_context_measured_eval" / "tiny_001" / "compact_sql_first" / "trajectory.json").exists()
    assert not (tiny_project.outputs_dir / "eval").exists()
    assert not (tiny_project.outputs_dir / "final_submission").exists()


def test_compact_context_measured_script_writes_only_allowed_outputs(tiny_project):
    _write_measured_inputs(tiny_project)
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
        [sys.executable, str(root / "scripts" / "run_compact_context_measured_eval.py")],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr

    outputs = tiny_project.outputs_dir
    assert (outputs / "compact_context_measured_eval.json").exists()
    assert (outputs / "compact_context_measured_eval.md").exists()
    assert (outputs / "compact_context_measured_eval" / "tiny_001" / "compact_sql_first" / "trajectory.json").exists()
    assert not (outputs / "eval").exists()
    assert not (outputs / "final_submission").exists()


def test_compact_context_flag_off_preserves_sql_first_outputs_and_submission_hash(tiny_project):
    final_submission = tiny_project.outputs_dir / "final_submission"
    final_submission.mkdir(parents=True)
    (final_submission / "trajectory.json").write_text(json.dumps({"strategy": "SQL_FIRST_API_VERIFY"}), encoding="utf-8")
    before_hash = _tree_hash(final_submission)
    config = replace(tiny_project, enable_compact_context_when_schema_vote_safe=False)
    executor = AgentExecutor(config)

    first = executor.run("How many campaigns are there?", strategy="SQL_FIRST_API_VERIFY", query_id="tiny_001", output_dir=tiny_project.outputs_dir / "flag_off_a")
    second = executor.run("How many campaigns are there?", strategy="SQL_FIRST_API_VERIFY", query_id="tiny_001", output_dir=tiny_project.outputs_dir / "flag_off_b")

    assert first_generated_sql(first["trajectory"]) == first_generated_sql(second["trajectory"])
    assert generated_api_calls(first["trajectory"]) == generated_api_calls(second["trajectory"])
    assert first["final_answer"] == second["final_answer"]
    assert first["trajectory"]["tool_call_count"] == second["trajectory"]["tool_call_count"]
    for field in ["query_id", "original_query", "strategy", "steps", "final_answer", "tool_call_count"]:
        assert field in first["trajectory"]
        assert field in second["trajectory"]
    assert _tree_hash(final_submission) == before_hash


def _write_shadow_inputs(config) -> None:
    outputs = config.outputs_dir
    trajectory_dir = outputs / "current" / "sql_first_api_verify"
    trajectory_dir.mkdir(parents=True, exist_ok=True)
    (trajectory_dir / "trajectory.json").write_text(
        json.dumps(
            {
                "query_id": "tiny_001",
                "strategy": "SQL_FIRST_API_VERIFY",
                "final_answer": "There are 2 campaigns.",
                "tool_call_count": 1,
                "steps": [],
                "checkpoints": [],
            }
        ),
        encoding="utf-8",
    )
    outputs.mkdir(parents=True, exist_ok=True)
    (outputs / "eval_results_strict.json").write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "query_id": "tiny_001",
                        "strategy": "SQL_FIRST_API_VERIFY",
                        "final_score": 0.9,
                        "tool_call_count": 1,
                        "estimated_tokens": 100,
                        "runtime": 0.01,
                        "output_dir": str(trajectory_dir),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (outputs / "candidate_context_report.json").write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "query_id": "tiny_001",
                        "query": "How many campaigns are configured?",
                        "schema_context_vote": {
                            "schema_vote_agreement": True,
                            "compact_context_safe": True,
                            "compact_context_tokens": 40,
                            "fallback_context_tokens": 100,
                            "fallback_reason": "compact and broader context agree",
                        },
                        "risk_efficiency_controller": {
                            "risk_level": "low",
                            "module_skipped_by_risk": ["value_retrieval", "shadow_repair"],
                            "token_saved_estimate": 25,
                            "runtime_saved_estimate_ms": 10,
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )


def _write_measured_inputs(config) -> None:
    _write_shadow_inputs(config)
    outputs = config.outputs_dir
    (outputs / "shadow_repair_eval.json").write_text(
        json.dumps(
            {
                "paired_shadow_eval_summary": {
                    "safe_repaired_worse_count": 0,
                    "safe_avg_score_delta": 0.0,
                },
                "rows": [],
                "cluster_canary_recommendations": {
                    "zero_score_margin": {"safe_to_enable_canary": False}
                },
            }
        ),
        encoding="utf-8",
    )
    report = json.loads((outputs / "candidate_context_report.json").read_text(encoding="utf-8"))
    report["rows"][0]["risk_level"] = "high"
    report["rows"][0]["schema_context_vote"].update(
        {
            "compact_candidate_tables": ["dim_campaign"],
            "fallback_candidate_tables": ["dim_campaign", "dim_segment"],
            "compact_candidate_apis": [],
            "fallback_candidate_apis": [],
        }
    )
    (outputs / "candidate_context_report.json").write_text(json.dumps(report), encoding="utf-8")


def _tree_hash(root: Path) -> str:
    digest = sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file():
            digest.update(str(path.relative_to(root)).encode("utf-8"))
            digest.update(path.read_bytes())
    return digest.hexdigest()
