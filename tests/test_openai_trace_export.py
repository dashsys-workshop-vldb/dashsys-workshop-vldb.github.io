from __future__ import annotations

from dashagent.agents_sdk_adapter import export_checkpoints_to_spans


def test_openai_trace_export_noops_without_required_sdk():
    result = export_checkpoints_to_spans([{"checkpoint_id": "checkpoint_00_prompt_router", "stage": "routing"}])
    assert "sdk_available" in result
    assert "exported_spans" in result
