from __future__ import annotations

import json

from scripts.audit_redundant_files import audit_redundant_files
from scripts.check_submission_ready import check_submission_ready
from scripts.cleanup_redundant_files import cleanup_redundant_files, update_validation_results


def _write_cleanup_baseline(config):
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    (config.outputs_dir / "eval_results_strict.json").write_text(json.dumps({"summary": {}}), encoding="utf-8")
    (config.outputs_dir / "winner_readiness_report.json").write_text(json.dumps({"summary": {}}), encoding="utf-8")
    (config.outputs_dir / "final_submission_manifest.json").write_text(json.dumps({"preferred_strategy": "SQL_FIRST_API_VERIFY"}), encoding="utf-8")


def test_redundant_file_audit_classifies_required_and_safe_paths(tiny_project):
    (tiny_project.project_root / "dashagent").mkdir()
    (tiny_project.project_root / "scripts").mkdir()
    (tiny_project.project_root / "tests").mkdir()
    (tiny_project.outputs_dir / "cache").mkdir(parents=True)
    (tiny_project.outputs_dir / "cache" / "value.json").write_text("{}", encoding="utf-8")
    (tiny_project.project_root / ".pytest_cache").mkdir()
    (tiny_project.project_root / ".venv").mkdir()
    final_dir = tiny_project.outputs_dir / "final_submission"
    final_dir.mkdir(parents=True)
    (final_dir / "keep.txt").write_text("keep", encoding="utf-8")

    payload = audit_redundant_files(tiny_project)
    rows = {row["path"]: row for row in payload["rows"]}

    assert rows["dashagent"]["classification"] == "keep_source_of_truth"
    assert rows["scripts"]["classification"] == "keep_source_of_truth"
    assert rows["outputs/final_submission"]["classification"] == "keep_required_by_packaging"
    assert rows["outputs/cache"]["classification"] == "delete_obsolete"
    assert rows[".pytest_cache"]["classification"] == "delete_obsolete"
    assert rows[".venv"]["classification"] == "unsure_do_not_delete"


def test_cleanup_dry_run_and_apply_delete_only_safe_generated(tiny_project):
    _write_cleanup_baseline(tiny_project)
    cache_dir = tiny_project.outputs_dir / "cache"
    cache_dir.mkdir(parents=True)
    (cache_dir / "value.json").write_text("{}", encoding="utf-8")
    final_dir = tiny_project.outputs_dir / "final_submission"
    final_dir.mkdir(parents=True)
    (final_dir / "keep.txt").write_text("keep", encoding="utf-8")

    audit = audit_redundant_files(tiny_project)
    reports_dir = tiny_project.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "cleanup_audit.json").write_text(json.dumps(audit), encoding="utf-8")
    dry = cleanup_redundant_files(tiny_project, apply=False)

    assert dry["summary"]["dry_run_delete_count"] >= 1
    assert cache_dir.exists()
    applied = cleanup_redundant_files(tiny_project, apply=True)

    assert applied["summary"]["deleted_count"] >= 1
    assert not cache_dir.exists()
    assert (final_dir / "keep.txt").exists()
    assert applied["summary"]["no_protected_files_deleted"] is True


def test_cleanup_refuses_misclassified_protected_path(tiny_project):
    _write_cleanup_baseline(tiny_project)
    protected_file = tiny_project.project_root / "scripts" / "fake.tmp"
    protected_file.parent.mkdir(exist_ok=True)
    protected_file.write_text("tmp", encoding="utf-8")
    audit = {
        "rows": [
            {
                "path": "scripts/fake.tmp",
                "classification": "delete_obsolete",
                "reason": "malicious or stale audit row",
                "referenced_by": [],
                "proposed_action": "delete",
            }
        ]
    }
    reports_dir = tiny_project.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "cleanup_audit.json").write_text(json.dumps(audit), encoding="utf-8")

    payload = cleanup_redundant_files(tiny_project, apply=True)

    assert payload["summary"]["refused_count"] == 1
    assert protected_file.exists()


def test_cleanup_final_report_records_skipped_validation_metadata(tiny_project):
    reports_dir = tiny_project.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    payload = update_validation_results(
        tiny_project,
        [
            "python3 -m pytest -q=passed",
            json.dumps(
                {
                    "command": "python3 scripts/run_llm_hidden_style_diagnostic.py",
                    "result": "skipped",
                    "skip_reason": "endpoint unavailable in test fixture",
                    "substitute_validation": "python3 scripts/check_llm_sdk_backend.py",
                    "residual_risk": "hidden-style LLM diagnostics not exercised in fixture",
                }
            ),
            "python3 scripts/check_submission_ready.py||result=passed",
            "rg -n secret-pattern .||result=passed",
        ],
    )

    skipped = payload["skipped_validation_commands"]
    assert skipped[0]["command"] == "python3 scripts/run_llm_hidden_style_diagnostic.py"
    assert skipped[0]["skip_reason"] == "endpoint unavailable in test fixture"
    assert skipped[0]["substitute_validation"] == "python3 scripts/check_llm_sdk_backend.py"
    assert skipped[0]["residual_risk"] == "hidden-style LLM diagnostics not exercised in fixture"
    assert payload["check_submission_ready_passed"] is True
    assert payload["secret_scan_passed"] is True
    assert payload["validation_summary"]["skipped"] == 1
    assert payload["final_response_required_fields"]
    assert payload["generated_reports"]
    assert (reports_dir / "cleanup_final_report.json").exists()
    md = (reports_dir / "cleanup_final_report.md").read_text(encoding="utf-8")
    assert "Skipped Validation Commands" in md
    assert "endpoint unavailable in test fixture" in md


def test_readiness_ignores_duplicate_query_copy_dirs(tiny_project):
    tiny_project.outputs_dir.mkdir(parents=True, exist_ok=True)
    for report in [
        "failure_analysis",
        "family_score_report",
        "pareto_report",
        "threshold_tuning_report",
        "robustness_eval",
    ]:
        (tiny_project.outputs_dir / f"{report}.json").write_text("{}", encoding="utf-8")
        (tiny_project.outputs_dir / f"{report}.md").write_text("ok", encoding="utf-8")
    (tiny_project.outputs_dir / "source_code.zip").write_bytes(b"zip")
    (tiny_project.outputs_dir / "final_submission_manifest.json").write_text(
        json.dumps({"preferred_strategy": "SQL_FIRST_API_VERIFY"}),
        encoding="utf-8",
    )
    final_dir = tiny_project.outputs_dir / "final_submission"
    for dirname in ["query_001", "query_001 2"]:
        query_dir = final_dir / dirname
        query_dir.mkdir(parents=True)
        (query_dir / "metadata.json").write_text("{}", encoding="utf-8")
        (query_dir / "filled_system_prompt.txt").write_text("prompt", encoding="utf-8")
        (query_dir / "trajectory.json").write_text(
            json.dumps(
                {
                    "strategy": "SQL_FIRST_API_VERIFY",
                    "final_answer": "x",
                    "tool_call_count": 1,
                    "runtime": 0.0,
                    "estimated_tokens": 1,
                }
            ),
            encoding="utf-8",
        )
    (final_dir / "system_prompt_template 2.txt").write_text("ACCESS_TOKEN=duplicate_not_submission", encoding="utf-8")

    report = check_submission_ready(tiny_project)

    assert report["query_output_count"] == 1
    assert report["query_outputs"][0]["query_id"] == "query_001"
    assert report["secret_scan"]["ok"] is True
