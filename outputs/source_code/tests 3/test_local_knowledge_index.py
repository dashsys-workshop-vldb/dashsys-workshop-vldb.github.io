from __future__ import annotations

import json

from dashagent.local_knowledge_index import (
    build_local_knowledge_index,
    classify_evidence_hit,
    ensure_not_final_answer_payload,
)
from scripts.build_local_knowledge_index import build_local_knowledge_index_report
from scripts.run_local_index_candidate_eval import run_local_index_candidate_eval


def test_local_index_builds_from_parquet_only_and_not_data_json(tiny_project):
    tiny_project.data_json_path.write_text(
        json.dumps({"answer": "FORBIDDEN_GOLD_ANSWER", "gold_sql": "SELECT secret"}),
        encoding="utf-8",
    )

    index = build_local_knowledge_index(tiny_project)
    payload = index.to_dict()
    rendered = json.dumps(payload, sort_keys=True)

    assert payload["runtime_sources"]["parquet_only"] is True
    assert payload["runtime_sources"]["data_json_used_for_runtime"] is False
    assert "FORBIDDEN_GOLD_ANSWER" not in rendered
    assert "SELECT secret" not in rendered
    assert index.evidence_objects


def test_local_index_returns_evidence_objects_not_final_answers(tiny_project):
    index = build_local_knowledge_index(tiny_project)
    hits = index.lookup("What is the status of Welcome Journey?")

    assert hits
    for hit in hits:
        assert hit["is_final_answer"] is False
        assert hit["answer_cache"] is False
        assert "final_answer" not in hit
        assert "answer" not in hit
        assert hit["provenance"]["data_json_used"] is False
        assert hit["provenance"]["derived_from_gold"] is False
        assert classify_evidence_hit(hit) in {
            "reusable_entity_lookup",
            "reusable_value_grounding",
            "reusable_schema_relation_lookup",
            "reusable_endpoint_family_lookup",
            "reusable_materialized_view_lookup",
        }


def test_local_index_rejects_final_answer_like_payloads():
    try:
        ensure_not_final_answer_payload({"evidence": {"final_answer": "2"}})
    except ValueError as exc:
        assert "final" in str(exc)
    else:  # pragma: no cover - defensive assertion.
        raise AssertionError("final_answer payload was not rejected")


def test_local_knowledge_index_report_fields(tiny_project):
    payload = build_local_knowledge_index_report(tiny_project)

    assert payload["summary"]["packaged_execution_changed"] is False
    assert payload["summary"]["data_json_used_for_runtime"] is False
    assert payload["summary"]["local_index_returns_final_answers"] is False
    assert payload["sample_evidence_objects"]
    assert "table_summaries" in payload


def test_local_index_candidate_eval_is_report_only(tiny_project):
    output_dir = tiny_project.outputs_dir / "eval" / "tiny_001" / "sql_first_api_verify"
    output_dir.mkdir(parents=True, exist_ok=True)
    strict = {
        "rows": [
            {
                "query_id": "tiny_001",
                "query": "What is the status of Welcome Journey?",
                "strategy": "SQL_FIRST_API_VERIFY",
                "output_dir": str(output_dir),
                "final_score": 0.5,
                "correctness_score": 0.55,
            }
        ]
    }
    (tiny_project.outputs_dir / "eval_results_strict.json").write_text(json.dumps(strict), encoding="utf-8")

    payload = run_local_index_candidate_eval(tiny_project)

    assert payload["packaged_execution_changed"] is False
    assert payload["writes_eval_outputs"] is False
    assert payload["writes_final_submission"] is False
    assert payload["summary"]["total_rows"] == 1
    assert payload["summary"]["rows_with_hits"] == 1
    assert payload["summary"]["safe_for_packaged_trial_rows"] == 0
    assert payload["rows"][0]["safe_for_packaged_trial"] is False
