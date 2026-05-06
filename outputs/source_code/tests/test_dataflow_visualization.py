from __future__ import annotations

from pathlib import Path

from dashagent.dataflow_visualizer import (
    build_checkpoint_effect_table,
    build_dataflow_summary,
    build_html_report,
    build_markdown_report,
    build_mermaid_graph,
    write_dataflow_artifacts,
)


def fake_trajectory():
    return {
        "query_id": "fake",
        "original_query": "Is the 'Birthday Message' journey published?",
        "strategy": "SQL_FIRST_API_VERIFY",
        "tool_call_count": 1,
        "runtime": 0.123,
        "estimated_tokens": 456,
        "final_answer": "Birthday Message has not been published.",
        "checkpoints": [
            {
                "checkpoint_id": "checkpoint_00_prompt_router",
                "stage": "routing",
                "technique": "routing",
                "output": {"mode": "SQL_PLUS_API", "api_policy": "API_OPTIONAL", "risk": "medium"},
                "effect": "routes status question to SQL plus API verification",
                "correctness_role": "prevents unsupported direct answers",
                "efficiency_role": "avoids unnecessary APIs for local-only prompts",
            },
            {
                "checkpoint_id": "checkpoint_02_query_normalization",
                "technique": "normalization",
                "output": {"normalized_query": "is birthday message journey published"},
            },
            {"checkpoint_id": "checkpoint_03_query_tokens", "technique": "tokens", "output": {"quoted_entities": ["Birthday Message"]}},
            {"checkpoint_id": "checkpoint_16_answer_verification", "technique": "verification", "output": {"verifier_passed": True}},
        ],
        "steps": [
            {"kind": "sql_call", "sql": "SELECT * FROM dim_campaign", "validation": {"ok": True}, "result": {"row_count": 1, "rows": [{"name": "Birthday Message"}]}},
            {
                "kind": "api_call",
                "method": "GET",
                "url": "/ajo/journey",
                "params": {"access_token": "secret-token-123456789"},
                "validation": {"ok": True},
                "endpoint_repair": {"repaired": True, "original_url": "/journey", "repaired_url": "/ajo/journey"},
                "result": {"ok": True, "dry_run": True, "result_preview": {"dry_run": True}},
            },
        ],
    }


def test_dataflow_outputs_mermaid_markdown_html_and_redacts():
    trajectory = fake_trajectory()
    graph = build_mermaid_graph(trajectory)
    md = build_markdown_report(trajectory)
    html = build_html_report(trajectory)
    table = build_checkpoint_effect_table(trajectory)
    assert "flowchart" in graph
    assert "Prompt Router" in graph
    assert "checkpoint_00_prompt_router" in table
    assert "Checkpoint Effect Table" in md
    assert "mermaid" in html
    assert "secret-token-123456789" not in md


def test_dataflow_artifacts_are_real_values_and_not_final_submission(tmp_path):
    trajectory = fake_trajectory()
    out_dir = tmp_path / "outputs" / "visualizations" / "fake" / "sql_first_api_verify"
    files = write_dataflow_artifacts(trajectory, out_dir)
    for path in files.values():
        assert Path(path).exists()
        assert "final_submission" not in Path(path).parts
    md = Path(files["md"]).read_text(encoding="utf-8")
    summary = build_dataflow_summary(trajectory)
    assert "Is the 'Birthday Message' journey published?" in md
    assert "SQL_FIRST_API_VERIFY" in md
    assert "Birthday Message has not been published." in md
    assert "| Tool call count | 1 |" in md
    assert "SELECT * FROM dim_campaign" in md
    assert "GET /ajo/journey" in md
    assert "API tool was invoked and validated, but live evidence was unavailable because Adobe credentials were missing." in md
    assert "/journey" in md
    assert "Checkpoint count" in md
    assert "prevents unsupported direct answers" in md
    assert summary["context"]["context_mode"].startswith("n/a -")


def test_dataflow_mermaid_required_subgraphs_and_missing_fields():
    minimal = {"query_id": "minimal", "original_query": "Explain checkpoints", "strategy": "SQL_FIRST_API_VERIFY", "steps": [], "checkpoints": []}
    graph = build_mermaid_graph(minimal)
    md = build_markdown_report(minimal)
    for label in [
        "subgraph Input",
        "subgraph Routing",
        "Query Understanding",
        "Context Selection",
        "Planning",
        "SQL Path",
        "API Path",
        "Tool Execution",
        "EvidenceBus",
        "Answer Verification",
        "Final Answer",
        "Metrics",
    ]:
        assert label in graph
    assert "n/a - no API call in trajectory" in md
    assert "n/a - no candidate context mode recorded" in md
