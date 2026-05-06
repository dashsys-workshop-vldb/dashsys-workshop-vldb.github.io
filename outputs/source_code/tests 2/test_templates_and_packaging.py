from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from dashagent.answer_synthesizer import synthesize_answer
from dashagent.api_templates import find_api_templates
from dashagent.config import Config
from dashagent.db import DuckDBDatabase
from dashagent.endpoint_catalog import EndpointCatalog
from dashagent.eval_harness import score_api
from dashagent.schema_index import SchemaIndex
from dashagent.sql_templates import find_sql_template
from dashagent.validators import APIValidator
from scripts.check_submission_ready import check_submission_ready
from scripts.package_query_outputs import discover_query_output_dirs, scan_for_output_secrets, select_submission_query_dirs


def add_relationship_snapshot(config: Config) -> None:
    pd.DataFrame(
        [{"SEGMENTID": "s1", "NAME": "Audience A", "TOTALMEMBERS": 10, "CREATEDTIME": "2026-01-01", "UPDATEDTIME": "2026-01-02"}]
    ).to_parquet(config.dbsnapshot_dir / "dim_segment.parquet", index=False)
    pd.DataFrame([{"SEGMENTID": "s1", "TARGETID": "t1"}]).to_parquet(
        config.dbsnapshot_dir / "hkg_br_segment_target.parquet", index=False
    )
    pd.DataFrame([{"TARGETID": "t1", "DATAFLOWNAME": "SMS Opt-In", "NAME": "sms-target"}]).to_parquet(
        config.dbsnapshot_dir / "dim_target.parquet", index=False
    )


def test_relationship_sql_generation_and_no_row_limit(tiny_project):
    add_relationship_snapshot(tiny_project)
    db = DuckDBDatabase(tiny_project)
    schema = SchemaIndex.build(db)
    query = "List all segment audiences connected to the destination named 'SMS Opt-In'. Remove any row limit from the results."
    template = find_sql_template(query, schema)
    assert template is not None
    assert "JOIN" in template.sql
    assert "hkg_br_segment_target" in template.sql
    assert "LIMIT" not in template.sql.upper()
    result = db.execute_sql(template.sql, allow_full_result=template.allow_full_result)
    assert result["ok"] is True
    assert result["row_count"] == 1


def test_api_templates_for_inactive_and_journey_name():
    inactive = find_api_templates("Give me inactive journeys")
    assert inactive[0].path == "/ajo/journey"
    assert inactive[0].params == {"filter": "status!=live"}

    named = find_api_templates("When was the journey 'Birthday Message' published?")
    assert named[0].params == {"filter": "name==Birthday Message"}


def test_api_param_scoring():
    generated = [{"method": "GET", "path": "/ajo/journey", "params": {"filter": "name==Birthday Message"}}]
    gold = ["GET https://platform.adobe.io/ajo/journey?filter=name==Birthday"]
    score, reason = score_api(generated, gold)
    assert score > 0.75
    assert "params" in reason


def test_every_api_template_validates_against_catalog(tiny_project):
    validator = APIValidator(EndpointCatalog(tiny_project))
    queries = [
        "When was the journey 'Birthday Message' published?",
        "Give me inactive journeys",
        "Which audiences are connected to destination SMS?",
        "List all audiences in the sandbox that have been mapped to new destinations in the last 3 months.",
        "How many datasets have been ingested using schema https://ns.adobe.com/example/schema?",
        "Provide more details for the schema 'weRetail: Customer Actions'",
        "Show the default merge policy for schema class '_xdm.context.profile'.",
        "What are the daily 'timeseries.ingestion.dataset.recordsuccess.count' values between '2026-03-15' and '2026-03-31'?",
        "List failed files for batch 01ABCDEF0123456789012345.",
        "List tags in the Uncategorized category.",
    ]
    for query in queries:
        for template in find_api_templates(query, tiny_project):
            result = validator.validate(template.method, template.path, template.params)
            assert result.ok, (query, template.to_dict(), result.errors)
            assert "{" not in template.path and "}" not in template.path


def test_answer_synthesis_for_unpublished_and_published_journey():
    unpublished = synthesize_answer(
        "When was the journey 'Birthday Message' published?",
        [
            {
                "type": "sql",
                "payload": {
                    "ok": True,
                    "rows": [{"campaign_name": "Birthday Message", "published_time": None}],
                    "row_count": 1,
                },
            },
            {"type": "api", "payload": {"ok": True, "result_preview": []}},
        ],
    )
    assert "has not been published" in unpublished

    published = synthesize_answer(
        "When was the journey 'Welcome' published?",
        [{"type": "sql", "payload": {"ok": True, "rows": [{"campaign_name": "Welcome", "published_time": "2026-01-01"}]}}],
    )
    assert "was published at 2026-01-01" in published


def test_answer_templates_for_weak_domains():
    schema_answer = synthesize_answer(
        "How many datasets have been ingested using the same schema in the prod sandbox?",
        [
            {
                "type": "sql",
                "payload": {
                    "ok": True,
                    "rows": [{"blueprint_name": "Journey Inbound External Segment Profile Schema", "collection_count": 2}],
                    "row_count": 1,
                },
            },
            {"type": "api", "payload": {"ok": False, "dry_run": True}},
        ],
    )
    assert "2 datasets" in schema_answer
    assert "Journey Inbound External Segment Profile Schema" in schema_answer

    audit_answer = synthesize_answer(
        "List all audiences in the sandbox that have been mapped to new destinations in the last 3 months.",
        [
            {
                "type": "sql",
                "payload": {
                    "ok": True,
                    "rows": [{"segment_name": "Gender: Male", "target_name": "Amazon S3", "created_time": "2026-03-29"}],
                    "row_count": 1,
                },
            },
            {"type": "api", "payload": {"ok": False, "dry_run": True}},
        ],
    )
    assert "Gender: Male" in audit_answer
    assert "Amazon S3" in audit_answer

    merge_answer = synthesize_answer(
        "Show the default merge policy for schema class '_xdm.context.profile'.",
        [{"type": "api", "payload": {"ok": False, "dry_run": True}}],
    )
    assert "default merge policy" in merge_answer
    assert "live api verification was not executed" in merge_answer.lower()

    segment_destination_answer = synthesize_answer(
        "List all segment audiences connected to the destination named 'SMS Opt-In'.",
        [
            {"type": "sql", "payload": {"ok": True, "rows": [], "row_count": 0}},
            {
                "type": "api",
                "step": {"family": "audience_by_destination_id"},
                "payload": {"ok": False, "dry_run": True},
            },
        ],
    )
    assert "no data available" in segment_destination_answer
    assert "SQL query returned zero rows" in segment_destination_answer

    observability_answer = synthesize_answer(
        "What are the daily 'timeseries.ingestion.dataset.recordsuccess.count' values between '2026-03-15' and '2026-03-31'?",
        [
            {
                "type": "api",
                "step": {"family": "observability_metrics"},
                "payload": {"ok": False, "dry_run": True},
            }
        ],
    )
    assert "timeseries.ingestion.dataset.recordsuccess.count" in observability_answer
    assert "2026-03-15" in observability_answer

    live_observability_answer = synthesize_answer(
        "What are the daily 'timeseries.ingestion.dataset.recordsuccess.count' values between '2026-03-15' and '2026-03-31'?",
        [
            {
                "type": "api",
                "step": {"family": "observability_metrics"},
                "payload": {
                    "ok": True,
                    "result_preview": {
                        "series": [
                            {
                                "name": "timeseries.ingestion.dataset.recordsuccess.count",
                                "points": [{"timestamp": "2026-03-31T00:00:00Z", "value": 2701}],
                            }
                        ]
                    },
                },
            }
        ],
    )
    assert "2026-03-31" in live_observability_answer
    assert "2701" in live_observability_answer


def test_hidden_output_packager_helpers_and_no_secret_scan(tmp_path: Path):
    outputs = tmp_path / "outputs"
    qdir = outputs / "eval" / "example_001" / "template_first"
    qdir.mkdir(parents=True)
    (qdir / "metadata.json").write_text("{}", encoding="utf-8")
    (qdir / "filled_system_prompt.txt").write_text("prompt", encoding="utf-8")
    (qdir / "trajectory.json").write_text(
        json.dumps({"strategy": "TEMPLATE_FIRST", "original_query": "q"}),
        encoding="utf-8",
    )
    found = discover_query_output_dirs(outputs)
    assert found == [qdir]
    assert select_submission_query_dirs(found, "TEMPLATE_FIRST") == [qdir]

    final_dir = outputs / "final_submission"
    final_dir.mkdir()
    (final_dir / "safe.txt").write_text("Authorization: [REDACTED]", encoding="utf-8")
    assert scan_for_output_secrets(final_dir)["ok"] is True


def test_submission_readiness_checker_accepts_valid_packaged_outputs(tiny_project):
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
                "strategy": "SQL_FIRST_API_VERIFY",
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
        json.dumps({"preferred_strategy": "SQL_FIRST_API_VERIFY"}),
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
    report = check_submission_ready(tiny_project)
    assert report["ok"] is True
