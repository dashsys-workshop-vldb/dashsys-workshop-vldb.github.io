from __future__ import annotations

from dashagent.answer_reranker import select_best_answer
from dashagent.answer_slots import extract_answer_slots
from dashagent.answer_templates import render_answer_template
from dashagent.api_response_parser import normalize_api_response
from dashagent.eval_harness import score_api_strict
from dashagent.live_response_parsers import parse_observability


def test_false_count_mismatch_does_not_override_sql_complete_answer() -> None:
    query = "Show me the IDs of failed dataflow runs"
    tool_results = [
        {
            "type": "sql",
            "payload": {"ok": True, "rows": [], "row_count": 0},
        },
        {
            "type": "api",
            "step": {"family": "flowservice_flows"},
            "payload": {
                "ok": True,
                "dry_run": False,
                "result_preview": {"items": [{"id": "flow_1", "state": "enabled"}]},
            },
        },
    ]

    slots = extract_answer_slots(query, tool_results)
    assert slots.discrepancy is False

    base = render_answer_template(query, [tool_results[0]], [tool_results[1]])
    selection = select_best_answer(query, tool_results, base or "")
    assert "SQL and API evidence disagree" not in selection.answer
    assert "no failed dataflow runs" in selection.answer


def test_schema_count_answer_treats_live_schema_api_as_confirmation() -> None:
    answer = render_answer_template(
        "How many schemas do I have?",
        [{"type": "sql", "payload": {"ok": True, "rows": [{"schema_count": 74}], "row_count": 1}}],
        [
            {
                "type": "api",
                "step": {"family": "schema_list"},
                "payload": {
                    "ok": True,
                    "dry_run": False,
                    "result_preview": {"results": [{"title": "Example schema"}]},
                },
            }
        ],
    )

    assert answer is not None
    assert "74 schemas" in answer
    assert "confirmed by the API response" in answer
    assert "usable supporting evidence" not in answer


def test_tag_category_query_uses_tag_list_not_category_metadata_only() -> None:
    answer = render_answer_template(
        "Which tags belong to the category 'Uncategorized'?",
        [],
        [
            {
                "type": "api",
                "step": {"family": "tag_categories"},
                "payload": {
                    "ok": True,
                    "dry_run": False,
                    "result_preview": {
                        "tags": [{"name": "Uncategorized", "tagCount": 5}],
                        "_page": {"count": 1},
                    },
                },
            },
            {
                "type": "api",
                "step": {"family": "tags_by_uncategorized_category"},
                "payload": {
                    "ok": True,
                    "dry_run": False,
                    "result_preview": {
                        "tags": [
                            {"name": "AI-Generated"},
                            {"name": "cool"},
                            {"name": "new clients"},
                        ]
                    },
                },
            },
        ],
    )

    assert answer is not None
    assert "Uncategorized" in answer
    assert "AI-Generated" in answer
    assert "cool" in answer
    assert "matching tag" not in answer


def test_tag_detail_mismatch_is_explicit() -> None:
    answer = render_answer_template(
        "Show me the details of the tag named 'cool'.",
        [],
        [
            {
                "type": "api",
                "step": {"family": "tag_details_by_id"},
                "payload": {
                    "ok": True,
                    "dry_run": False,
                    "result_preview": {
                        "id": "51175a7f-aa60-4533-bef1-717b3cef7818",
                        "name": "sublist",
                        "tagCategoryName": "Uncategorized",
                    },
                },
            }
        ],
    )

    assert answer is not None
    assert "tag named 'cool'" in answer
    assert "sublist" in answer
    assert "51175a7f-aa60-4533-bef1-717b3cef7818" in answer
    assert "discrepancy" in answer.lower() or "did not return" in answer.lower()


def test_observability_dps_maps_become_renderable_values() -> None:
    raw = {
        "metricResponses": [
            {
                "metric": "timeseries.ingestion.dataset.recordsuccess.count",
                "datapoints": [
                    {
                        "dps": {
                            "2026-03-29T00:00:00Z": 152120.0,
                            "2026-03-31T00:00:00Z": 2701.0,
                        }
                    }
                ],
            }
        ]
    }
    evidence = parse_observability(raw)

    values = evidence["important_fields"]["values"]
    assert {"metric": "timeseries.ingestion.dataset.recordsuccess.count", "timestamp": "2026-03-29T00:00:00Z", "value": 152120.0} in values
    assert {"metric": "timeseries.ingestion.dataset.recordsuccess.count", "timestamp": "2026-03-31T00:00:00Z", "value": 2701.0} in values

    parsed = normalize_api_response(
        raw,
        ok=True,
        dry_run=False,
        endpoint_id="observability_metrics",
        endpoint_family="observability_metrics",
        method="POST",
        path="/data/infrastructure/observability/insights/metrics",
    )
    answer = render_answer_template(
        "What are the daily 'timeseries.ingestion.dataset.recordsuccess.count' values between '2026-03-15' and '2026-03-31'?",
        [],
        [{"type": "api", "step": {"family": "observability_metrics"}, "payload": {"ok": True, "dry_run": False, "parsed_evidence": parsed}}],
    )
    assert answer is not None
    assert "152120" in answer
    assert "2701" in answer


def test_strict_api_scorer_accepts_docs_backed_canonical_path_aliases() -> None:
    schema_score, _ = score_api_strict(
        [{"method": "GET", "path": "/data/foundation/schemaregistry/tenant/schemas", "params": {"limit": "25"}}],
        ["GET /schemas?limit=25"],
    )
    audit_score, _ = score_api_strict(
        [
            {
                "method": "GET",
                "path": "/data/foundation/audit/events",
                "params": {"property": "assetType==dataset", "orderBy": "-timestamp", "limit": "50"},
            }
        ],
        ["GET /audit/events?property=assetType==dataset&orderBy=-timestamp&limit=50"],
    )
    category_score, _ = score_api_strict(
        [
            {"method": "GET", "path": "/unifiedtags/tagCategory", "params": {"limit": "100"}},
            {
                "method": "GET",
                "path": "/unifiedtags/tags",
                "params": {"limit": "100", "tagCategoryId": "Uncategorized"},
            },
        ],
        [
            "GET /unifiedtags/tagCategory?limit=100",
            "GET /unifiedtags/tags?limit=100&tagCategoryId=Uncategorized-synthetic-category-id",
        ],
    )

    assert schema_score == 1.0
    assert audit_score == 1.0
    assert category_score == 1.0
