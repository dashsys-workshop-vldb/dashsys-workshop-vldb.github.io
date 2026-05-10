from __future__ import annotations

from typing import Any

from .trajectory import compact_preview, redact_secrets


def export_checkpoints_to_spans(checkpoints: list[dict[str, Any]]) -> dict[str, Any]:
    """Export checkpoint metadata as optional OpenAI Agents SDK custom spans.

    The repository must keep working without the SDK, so missing imports are a
    successful no-op. The adapter is intentionally tiny and side-effect-free
    unless the optional SDK is present.
    """
    try:
        from agents import custom_span  # type: ignore
    except Exception:
        return {"ok": True, "sdk_available": False, "exported_spans": 0}

    exported = 0
    try:
        for checkpoint in checkpoints:
            payload = redact_secrets(compact_preview(checkpoint, 1000))
            name = f"{checkpoint.get('checkpoint_id', 'checkpoint')}:{checkpoint.get('stage', 'stage')}"
            with custom_span(name, data=payload):
                exported += 1
    except Exception as exc:
        return {
            "ok": False,
            "sdk_available": True,
            "exported_spans": exported,
            "error": str(exc),
        }
    return {"ok": True, "sdk_available": True, "exported_spans": exported}


def export_validation_to_span(name: str, validation: Any) -> dict[str, Any]:
    try:
        from agents import custom_span  # type: ignore
    except Exception:
        return {"ok": True, "sdk_available": False, "exported_spans": 0}
    payload = validation.to_dict() if hasattr(validation, "to_dict") else validation
    with custom_span(name, data=redact_secrets(compact_preview(payload, 1000))):
        return {"ok": True, "sdk_available": True, "exported_spans": 1}


def export_tool_execution_to_span(name: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        from agents import custom_span  # type: ignore
    except Exception:
        return {"ok": True, "sdk_available": False, "exported_spans": 0}
    with custom_span(name, data=redact_secrets(compact_preview(payload, 1000))):
        return {"ok": True, "sdk_available": True, "exported_spans": 1}
