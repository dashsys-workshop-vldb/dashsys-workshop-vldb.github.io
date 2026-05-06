from __future__ import annotations

import json
import os
import hashlib
import subprocess
import sys
from pathlib import Path

from dashagent.executor import AgentExecutor
from scripts.run_shadow_repair_eval import (
    _decision_label,
    build_paired_summary,
    build_schema_dataset_repair_analysis,
    decision_hash,
    run_shadow_repair_eval,
)


def test_shadow_repair_eval_rows_have_paired_summary_and_stable_hash(tiny_project):
    payload_one = run_shadow_repair_eval(tiny_project)
    payload_two = run_shadow_repair_eval(tiny_project)

    assert "paired_shadow_eval_summary" in payload_one
    assert "cluster_canary_recommendations" in payload_one
    assert "risk_efficiency_controller_summary" in payload_one
    assert "schema_context_voting_summary" in payload_one
    assert "schema_dataset_repair_analysis" in payload_one
    assert payload_one["packaged_execution_changed"] is False
    assert payload_one["measured_accuracy_improvement_claimed"] is False
    assert payload_one["measured_efficiency_improvement_claimed"] is False
    assert payload_one["behavior_changing_flags_note"] == "No behavior-changing flags were enabled in this pass."
    assert payload_one["rows"]
    assert payload_one["rows"][0]["decision_hash"] == decision_hash(payload_one["rows"][0])
    assert "risk_level" in payload_one["rows"][0]
    assert "schema_context_vote" in payload_one["rows"][0]
    assert payload_one["rows"][0]["savings_are_estimates"] is True
    assert payload_one["rows"][0]["packaged_execution_changed"] is False
    for field in [
        "safe_repaired_better_count",
        "safe_repaired_equal_count",
        "safe_repaired_worse_count",
        "safe_avg_score_delta",
        "safe_avg_tool_delta",
        "unsafe_avg_score_delta",
        "unsafe_failure_reason_counts",
    ]:
        assert field in payload_one["paired_shadow_eval_summary"]
    assert [row["decision_hash"] for row in payload_one["rows"]] == [row["decision_hash"] for row in payload_two["rows"]]


def test_no_op_shadow_tie_keeps_current_and_never_recommends_canary():
    decision = _decision_label(
        0.0,
        {"safe": True},
        0,
        0,
        0.0,
        False,
        {"no_op": True, "safe_to_select_repaired": False},
    )

    assert decision == "no_op_shadow_tie_keep_current"


def test_safe_only_aggregates_use_safety_verdict_and_count_failures():
    summary = build_paired_summary(
        [
            {"score_delta": 0.2, "tool_delta": 0, "runtime_delta": 0, "token_delta": 0, "safety_verdict": {"safe": True}},
            {"score_delta": -0.1, "tool_delta": 1, "runtime_delta": 0, "token_delta": 0, "safety_verdict": {"safe": False, "failed_checks": ["api_validation"]}},
            {"score_delta": 0.0, "tool_delta": 0, "runtime_delta": 0, "token_delta": 0, "safety_verdict": {"safe": False, "failed_checks": ["api_validation", "fusion_agreement"]}},
        ]
    )

    assert summary["safe_repaired_better_count"] == 1
    assert summary["safe_repaired_equal_count"] == 0
    assert summary["safe_repaired_worse_count"] == 0
    assert summary["unsafe_failure_reason_counts"] == {"api_validation": 2, "fusion_agreement": 1}


def test_schema_dataset_repair_analysis_marks_failure_type_and_signal():
    analysis = build_schema_dataset_repair_analysis(
        [
            {
                "query_id": "q1",
                "query": "Which datasets use a schema?",
                "risk_cluster": "schema_vs_dataset_confusion",
                "current_plan_sql": ["SELECT 1"],
                "current_plan_api": [{"path": "/schemas"}],
                "repaired_plan_sql": ["SELECT 1"],
                "repaired_plan_api": [{"path": "/data/foundation/catalog/dataSets"}],
                "score_delta": 0.1,
                "safety_verdict": {"failed_checks": ["endpoint_family_confidence"]},
                "repair_candidate_selector": {"recommendation": "keep_current"},
                "decision": "keep_current_repair_selector_rejected",
            }
        ]
    )

    assert analysis["row_count"] == 1
    row = analysis["rows"][0]
    assert row["failure_type"] == "verifier_strictness"
    assert "endpoint family confidence" in row["missing_signal"]


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


def test_shadow_eval_does_not_modify_packaged_output_folders(tiny_project):
    protected_submission = tiny_project.outputs_dir / "final_submission" / "metadata.json"
    protected_eval = tiny_project.outputs_dir / "eval" / "protected" / "sql_first_api_verify" / "trajectory.json"
    protected_submission.parent.mkdir(parents=True, exist_ok=True)
    protected_eval.parent.mkdir(parents=True, exist_ok=True)
    protected_submission.write_text('{"preferred_strategy":"SQL_FIRST_API_VERIFY"}', encoding="utf-8")
    protected_eval.write_text('{"strategy":"SQL_FIRST_API_VERIFY","tool_call_count":1}', encoding="utf-8")
    before = {
        "final_submission": _hash_tree(tiny_project.outputs_dir / "final_submission"),
        "eval": _hash_tree(tiny_project.outputs_dir / "eval"),
    }
    _ = run_shadow_repair_eval(tiny_project)
    after = {
        "final_submission": _hash_tree(tiny_project.outputs_dir / "final_submission"),
        "eval": _hash_tree(tiny_project.outputs_dir / "eval"),
    }
    assert before == after


def test_no_duplicate_shadow_repair_modules_exist():
    root = Path(__file__).resolve().parents[1]
    assert (root / "scripts" / "run_shadow_repair_eval.py").exists()
    assert (root / "dashagent" / "repair_safety_verifier.py").exists()
    assert [path for path in (root / "scripts").glob("run_shadow_repair_eval.py")] == [root / "scripts" / "run_shadow_repair_eval.py"]
    assert [path for path in (root / "dashagent").glob("repair_safety_verifier.py")] == [root / "dashagent" / "repair_safety_verifier.py"]
    for forbidden in [
        "shadow_repair_evaluator.py",
        "repair_verifier_v2.py",
        "risk_repair_eval.py",
    ]:
        assert not (root / "scripts" / forbidden).exists()
        assert not (root / "dashagent" / forbidden).exists()


def _executed_sql(trajectory: dict) -> list[str]:
    return [step.get("sql") for step in trajectory.get("steps", []) if step.get("kind") == "sql_call"]


def _executed_api(trajectory: dict) -> list[str]:
    return [
        f"{step.get('method')} {step.get('url')}"
        for step in trajectory.get("steps", [])
        if step.get("kind") == "api_call"
    ]


def _hash_tree(root: Path) -> dict[str, str]:
    if not root.exists():
        return {}
    hashes = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        hashes[str(path.relative_to(root))] = digest
    return hashes
