#!/usr/bin/env python
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.llm_client import get_llm_client
from dashagent.trajectory import redact_secrets
from scripts.nl_sql_robustness_common import analyze_prompt_groups


REPORT_STEM = "multi_llm_backend_robustness"
BACKENDS = ["deterministic_only", "no_llm_fallback", "openai", "openrouter", "anthropic"]


def main() -> int:
    config = Config.from_env(ROOT)
    payload = run_multi_llm_backend_robustness(config)
    print(
        json.dumps(
            {
                "json": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.json"),
                "markdown": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.md"),
                "llm_calls_executed": payload.get("llm_calls_executed"),
                "available_backend_count": sum(1 for item in payload.get("backends", []) if item.get("available")),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def run_multi_llm_backend_robustness(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    _rows, _groups, deterministic_metrics = analyze_prompt_groups(
        config,
        include_generated=False,
        max_groups=None,
        enable_schema_aware=False,
    )
    backends = [_backend_status(name) for name in BACKENDS]
    payload = redact_secrets(
        {
            "report_type": REPORT_STEM,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "diagnostic_only": True,
            "official_score_claim": False,
            "promotion_allowed": False,
            "llm_calls_executed": 0,
            "sdk_only_policy": True,
            "note": (
                "This pass records backend availability and deterministic/no-LLM behavior only. "
                "It does not call hosted LLM APIs or optimize for a specific model."
            ),
            "deterministic_only_metrics": deterministic_metrics,
            "backends": backends,
            "variance": _variance_summary(backends, deterministic_metrics),
            "output_paths": {
                "json": str(reports_dir / f"{REPORT_STEM}.json"),
                "markdown": str(reports_dir / f"{REPORT_STEM}.md"),
            },
        }
    )
    (reports_dir / f"{REPORT_STEM}.json").write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    (reports_dir / f"{REPORT_STEM}.md").write_text(_render_markdown(payload), encoding="utf-8")
    return payload


def _backend_status(name: str) -> dict[str, Any]:
    if name == "deterministic_only":
        return {
            "backend": name,
            "available": True,
            "executed": True,
            "llm_calls_executed": 0,
            "status": "baseline_deterministic_path",
        }
    if name == "no_llm_fallback":
        return {
            "backend": name,
            "available": True,
            "executed": True,
            "llm_calls_executed": 0,
            "status": "fallback_path_no_model_required",
        }
    client = get_llm_client(name)
    available = bool(client.available())
    env_names = {
        "openai": ["OPENAI_API_KEY"],
        "openrouter": ["OPENROUTER_API_KEY", "OPENAI_BASE_URL"],
        "anthropic": ["ANTHROPIC_API_KEY"],
    }.get(name, [])
    return {
        "backend": name,
        "available": available,
        "executed": False,
        "llm_calls_executed": 0,
        "provider": client.provider_name(),
        "model": client.model_name(),
        "status": "available_not_executed_diagnostic_only" if available else "unavailable",
        "env_names_checked": [env for env in env_names if os.getenv(env)],
        "reason": None if available else "backend credentials not present or provider unavailable",
    }


def _variance_summary(backends: list[dict[str, Any]], deterministic_metrics: dict[str, Any]) -> dict[str, Any]:
    executable = [item for item in backends if item.get("executed")]
    unavailable = [item for item in backends if not item.get("available")]
    return {
        "correctness_variance": "not_measured_without_executing_hosted_llm_calls",
        "tool_call_variance": 0,
        "token_runtime_variance": "not_measured_without_executing_hosted_llm_calls",
        "answer_drift": "not_measured_without_executing_hosted_llm_calls",
        "unsupported_claim_drift": "not_measured_without_executing_hosted_llm_calls",
        "executed_backend_count": len(executable),
        "unavailable_backend_count": len(unavailable),
        "no_llm_template_dependency_score": deterministic_metrics.get("template_dependency_score"),
    }


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Multi-LLM Backend Robustness",
        "",
        "Diagnostic-only backend sensitivity report. No hosted LLM calls are executed by this script.",
        "",
        f"- LLM calls executed: `{report.get('llm_calls_executed')}`",
        f"- No-LLM template dependency score: `{report.get('variance', {}).get('no_llm_template_dependency_score')}`",
        "",
        "## Backends",
        "",
    ]
    for item in report.get("backends", []):
        lines.append(
            f"- `{item.get('backend')}`: status `{item.get('status')}`, available `{item.get('available')}`, executed `{item.get('executed')}`"
        )
    lines.extend(
        [
            "",
            "Variance across hosted model backends is recorded as unavailable in this pass because executing hosted LLM calls is outside the current local-first diagnostic scope.",
            "",
        ]
    )
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
