#!/usr/bin/env python
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.trajectory import redact_secrets
from scripts.check_llm_sdk_backend import render_markdown, run_llm_sdk_backend_check


def main() -> int:
    config = Config.from_env(ROOT)
    report = run_openai_compatible_llm_check(config)
    print(
        json.dumps(
            {
                "ok": report["ok"],
                "deprecated_wrapper": report["deprecated_wrapper"],
                "provider": report["provider"],
                "backend_type": report["backend_type"],
                "model": report["model"],
                "tool_calling_supported": report["tool_calling_supported"],
                "json": str(config.outputs_dir / "openai_compatible_llm_check.json"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def run_openai_compatible_llm_check(config: Config | None = None) -> dict[str, Any]:
    """Deprecated compatibility entry point.

    The system-wide LLM rule requires all provider tests to go through the shared
    SDK client abstraction. This wrapper preserves the old script/report name
    while delegating the actual smoke test to check_llm_sdk_backend.py.
    """

    config = config or Config.from_env(ROOT)
    report = dict(run_llm_sdk_backend_check(config))
    report.update(
        {
            "deprecated_wrapper": True,
            "delegates_to": "scripts/check_llm_sdk_backend.py",
            "compatibility_report": "openai_compatible_llm_check",
            "sdk_path_used": report.get("backend_type") in {"openai_sdk", "anthropic_sdk"},
            "notes": [
                "Deprecated compatibility wrapper; use scripts/check_llm_sdk_backend.py for new checks.",
                "The generic SDK-based LLM baseline framework is provider-agnostic.",
            ],
        }
    )
    return _write_compatibility_report(config, report)


def _write_compatibility_report(config: Config, report: dict[str, Any]) -> dict[str, Any]:
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    safe_report = redact_secrets(report)
    if not isinstance(safe_report, dict):
        safe_report = report
    json_path = config.outputs_dir / "openai_compatible_llm_check.json"
    md_path = config.outputs_dir / "openai_compatible_llm_check.md"
    json_path.write_text(json.dumps(safe_report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md = render_markdown(safe_report)
    md += "\nCompatibility note: this deprecated script delegates to `scripts/check_llm_sdk_backend.py`.\n"
    md_path.write_text(md, encoding="utf-8")
    return safe_report


if __name__ == "__main__":
    raise SystemExit(main())
