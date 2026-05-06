from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

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
