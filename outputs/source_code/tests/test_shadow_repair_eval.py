from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from dashagent.executor import AgentExecutor
from scripts.run_shadow_repair_eval import decision_hash, run_shadow_repair_eval


def test_shadow_repair_eval_rows_have_paired_summary_and_stable_hash(tiny_project):
    payload_one = run_shadow_repair_eval(tiny_project)
    payload_two = run_shadow_repair_eval(tiny_project)

    assert "paired_shadow_eval_summary" in payload_one
    assert "cluster_canary_recommendations" in payload_one
    assert payload_one["rows"]
    assert payload_one["rows"][0]["decision_hash"] == decision_hash(payload_one["rows"][0])
    assert [row["decision_hash"] for row in payload_one["rows"]] == [row["decision_hash"] for row in payload_two["rows"]]


def test_shadow_eval_does_not_change_packaged_sql_first_execution(tiny_project):
    before = AgentExecutor(tiny_project).run("How many campaigns are there?", strategy="SQL_FIRST_API_VERIFY", query_id="stable")
    _ = run_shadow_repair_eval(tiny_project)
    after = AgentExecutor(tiny_project).run("How many campaigns are there?", strategy="SQL_FIRST_API_VERIFY", query_id="stable_after")

    assert _executed_sql(before["trajectory"]) == _executed_sql(after["trajectory"])
    assert _executed_api(after["trajectory"]) == _executed_api(before["trajectory"])
    assert before["trajectory"]["tool_call_count"] == after["trajectory"]["tool_call_count"]
    assert before["final_answer"] == after["final_answer"]
    assert before["trajectory"].keys() == after["trajectory"].keys()


def test_shadow_script_artifact_isolation_exact_paths(tiny_project):
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
    script = Path(__file__).resolve().parents[1] / "scripts" / "run_shadow_repair_eval.py"
    result = subprocess.run([sys.executable, str(script)], cwd=Path(__file__).resolve().parents[1], env=env, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr

    outputs = tiny_project.outputs_dir
    assert (outputs / "shadow_repair_eval.json").exists()
    assert (outputs / "shadow_repair_eval.md").exists()
    assert (outputs / "shadow_repair_eval").is_dir()
    assert not (outputs / "eval").exists()
    assert not (outputs / "final_submission").exists()
    assert not any("final_submission" in path.parts for path in outputs.rglob("*"))
    unexpected_top_level = {
        path.name
        for path in outputs.iterdir()
        if path.name not in {"cache", "shadow_repair_eval", "shadow_repair_eval.json", "shadow_repair_eval.md"}
    }
    assert unexpected_top_level == set()

    payload = json.loads((outputs / "shadow_repair_eval.json").read_text(encoding="utf-8"))
    assert payload["artifact_isolation"]["writes_eval_outputs"] is False
    assert payload["artifact_isolation"]["writes_final_submission"] is False


def _executed_sql(trajectory: dict) -> list[str]:
    return [step.get("sql") for step in trajectory.get("steps", []) if step.get("kind") == "sql_call"]


def _executed_api(trajectory: dict) -> list[str]:
    return [
        f"{step.get('method')} {step.get('url')}"
        for step in trajectory.get("steps", [])
        if step.get("kind") == "api_call"
    ]
