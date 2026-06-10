from __future__ import annotations

import json
import zipfile
from pathlib import Path

from dashagent.config import Config
from scripts.audit_workshop_requirements import audit_workshop_requirements
from scripts.generate_consolidated_reports import generate_consolidated_reports


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_zip(path: Path, entries: dict[str, str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, text in (entries or {"README.md": "safe source"}).items():
            archive.writestr(name, text)


def _make_workshop_project(tmp_path: Path) -> Config:
    data_dir = tmp_path / "data"
    outputs = tmp_path / "outputs"
    prompts = tmp_path / "prompts"
    data_dir.mkdir()
    prompts.mkdir()
    (data_dir / "data.json").write_text("[]", encoding="utf-8")
    (data_dir / "generated_prompt_suite.json").write_text(
        json.dumps(
            [
                {
                    "prompt_id": "gen_0001",
                    "prompt": "Count schemas",
                    "diagnostic_only": True,
                    "should_be_scored": False,
                }
            ]
        ),
        encoding="utf-8",
    )
    prompt_text = "Use execute_sql(sql) and call_api(method, url, params, headers). Keep answers grounded."
    (prompts / "system_prompt_template.txt").write_text(prompt_text, encoding="utf-8")
    (tmp_path / "README.md").write_text(
        "execute_sql call_api metadata.json filled_system_prompt trajectory.json SQL_FIRST_API_VERIFY "
        "diagnostic-only should_be_scored=false get_llm_client validation",
        encoding="utf-8",
    )
    (tmp_path / "AGENTS.md").write_text(
        "execute_sql call_api metadata.json filled_system_prompt trajectory.json SQL_FIRST_API_VERIFY "
        "diagnostic-only should_be_scored=false get_llm_client validation",
        encoding="utf-8",
    )

    final_dir = outputs / "final_submission"
    query_dir = final_dir / "query_001"
    query_dir.mkdir(parents=True)
    (final_dir / "system_prompt_template.txt").write_text(prompt_text, encoding="utf-8")
    _write_zip(final_dir / "source_code.zip")
    _write_zip(outputs / "source_code.zip")
    (query_dir / "metadata.json").write_text("{}", encoding="utf-8")
    (query_dir / "filled_system_prompt.txt").write_text("filled", encoding="utf-8")
    _write_json(
        query_dir / "trajectory.json",
        {
            "query_id": "tiny_001",
            "original_query": "How many campaigns are there?",
            "strategy": "SQL_FIRST_API_VERIFY",
            "final_answer": "There are 2 campaigns.",
            "tool_call_count": 1,
            "estimated_tokens": 100,
            "runtime": 0.01,
            "sql_call_count": 1,
            "api_call_count": 0,
            "steps": [
                {
                    "kind": "sql_call",
                    "sql": "SELECT COUNT(*) AS count FROM dim_campaign",
                    "validation": {"ok": True, "errors": []},
                    "result": {"ok": True, "rows": [{"count": 2}], "row_count": 1},
                }
            ],
        },
    )
    _write_json(
        outputs / "final_submission_manifest.json",
        {"preferred_strategy": "SQL_FIRST_API_VERIFY", "total_number_of_queries": 1},
    )
    for stem in ["failure_analysis", "family_score_report", "pareto_report", "threshold_tuning_report", "robustness_eval"]:
        _write_json(outputs / f"{stem}.json", {})
        (outputs / f"{stem}.md").write_text("ok", encoding="utf-8")
    _write_json(
        outputs / "eval_results_strict.json",
        {
            "summary": {
                "by_strategy": {
                    "SQL_FIRST_API_VERIFY": {
                        "avg_sql_score": 1.0,
                        "avg_api_score": 1.0,
                        "avg_answer_score": 1.0,
                        "avg_final_score": 1.0,
                        "avg_correctness_score": 1.0,
                        "avg_tool_call_count": 1,
                        "avg_estimated_tokens": 100,
                        "avg_runtime": 0.01,
                    }
                }
            }
        },
    )
    _write_json(outputs / "hidden_style_eval.json", {"summary": {"passed_cases": 1, "total_cases": 1}})
    _write_json(
        outputs / "winner_readiness_report.json",
        {
            "packaged": {
                "preferred_strategy": "SQL_FIRST_API_VERIFY",
                "strict_final_score": 1.0,
                "final_submission_ready": True,
            }
        },
    )
    _write_json(outputs / "visualizations" / "sql_prompt_storyboard_primary.json", {"query_id": "example_011"})
    _write_json(outputs / "visualizations" / "index.json", {"entries": []})
    return Config(
        project_root=tmp_path,
        data_dir=data_dir,
        dbsnapshot_dir=data_dir / "DBSnapshot",
        data_json_path=data_dir / "data.json",
        outputs_dir=outputs,
        prompts_dir=prompts,
    )


def test_workshop_audit_report_schema_and_mapping(tmp_path: Path):
    config = _make_workshop_project(tmp_path)

    report = audit_workshop_requirements(config)

    assert report["overall_status"] in {"pass", "warning"}
    assert report["critical_failures"] == []
    assert "execute_sql(sql)" in report["official_requirement_mapping"]
    assert "call_api(method, url, params, headers)" in report["official_requirement_mapping"]
    assert "per_query_deliverables" in report["official_requirement_mapping"]
    assert any(item["id"] == "final_submission.trajectory_json" for item in report["items"])
    assert (config.outputs_dir / "reports" / "workshop_requirement_audit.json").exists()
    assert (config.outputs_dir / "reports" / "workshop_requirement_audit.md").exists()


def test_workshop_audit_critical_failure_for_invalid_trajectory_and_diagnostic_contamination(tmp_path: Path):
    config = _make_workshop_project(tmp_path)
    (config.outputs_dir / "final_submission" / "query_001" / "trajectory.json").write_text("{not json", encoding="utf-8")
    (config.outputs_dir / "final_submission" / "generated_prompt_suite.json").write_text("[]", encoding="utf-8")

    report = audit_workshop_requirements(config)
    failure_ids = {item["id"] for item in report["critical_failures"]}

    assert report["overall_status"] == "fail"
    assert "final_submission.trajectory_json" in failure_ids
    assert "final_submission.diagnostic_contamination" in failure_ids


def test_workshop_audit_critical_failure_for_direct_llm_http_runtime_hit(tmp_path: Path):
    config = _make_workshop_project(tmp_path)
    scripts_dir = config.project_root / "scripts"
    scripts_dir.mkdir()
    (scripts_dir / "bad_llm.py").write_text(
        "import requests\nrequests.post('https://api.openai.com/v1/chat/completions')\n",
        encoding="utf-8",
    )

    report = audit_workshop_requirements(config)
    failure_ids = {item["id"] for item in report["critical_failures"]}

    assert report["overall_status"] == "fail"
    assert "llm_sdk.direct_runtime_http" in failure_ids


def test_report_index_links_workshop_requirement_audit(tmp_path: Path):
    config = _make_workshop_project(tmp_path)
    audit_workshop_requirements(config)
    generate_consolidated_reports(config)

    index_md = (config.outputs_dir / "reports" / "report_index.md").read_text(encoding="utf-8")
    index_json = json.loads((config.outputs_dir / "reports" / "report_index.json").read_text(encoding="utf-8"))

    assert "## Workshop Requirement Alignment" in index_md
    assert "workshop_requirement_audit.md" in index_md
    assert index_json["workshop_requirement_alignment"]["path"] == "outputs/reports/workshop_requirement_audit.md"
