#!/usr/bin/env python
from __future__ import annotations

import json
import os
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.llm_client import get_llm_client
from dashagent.llm_tool_agent import GUIDED_REAL_LLM_TWO_TOOLS_BASELINE, run_real_llm_two_tools_baseline
from dashagent.trajectory import redact_secrets
from scripts.load_local_env import load_local_env
from scripts.run_hidden_style_eval import HIDDEN_STYLE_CASES


def main() -> int:
    config = Config.from_env(ROOT)
    load_local_env(config.project_root)
    payload = run_llm_hidden_style_diagnostic(config)
    write_report(config, payload)
    print(
        json.dumps(
            {
                "json": str(config.outputs_dir / "llm_hidden_style_diagnostic.json"),
                "markdown": str(config.outputs_dir / "llm_hidden_style_diagnostic.md"),
                "status": payload.get("status"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def run_llm_hidden_style_diagnostic(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    client = get_llm_client()
    provider_type = "anthropic" if client.provider_name() == "anthropic" else "openai_compatible"
    backend_type = "anthropic_sdk" if client.provider_name() == "anthropic" else "openai_sdk"
    if not client.available():
        probe = client.generate_messages([])
        payload = {
            "framework": "generic_sdk_llm_baseline",
            "provider_type": provider_type,
            "backend_type": backend_type,
            "backend_name": client.model_name(),
            "status": "skipped",
            "skipped_reason": probe.get("reason", "LLM provider API key is not set"),
            "recommendation": "keep_shadow_only",
            "rows": [],
            "summary": {
                "hidden_style_sample_count": 0,
                "malformed_tool_calls": 0,
                "unsupported_answers": 0,
                "missing_evidence": 0,
                "dry_run_hallucination_risk": 0,
            },
        }
        return _safe_report_payload(payload)

    limit = int(os.getenv("LLM_HIDDEN_STYLE_SAMPLE_LIMIT", "8") or "8")
    cases = HIDDEN_STYLE_CASES[: max(1, min(limit, len(HIDDEN_STYLE_CASES)))]
    rows = []
    for case in cases:
        start = time.perf_counter()
        query = _case_value(case, "query")
        try:
            result = run_real_llm_two_tools_baseline(
                query,
                config=config,
                guided=True,
                system_name=GUIDED_REAL_LLM_TWO_TOOLS_BASELINE,
                max_turns=3,
                max_tool_calls=3,
            )
            elapsed = time.perf_counter() - start
            rows.append(_diagnostic_row(case, result, elapsed))
        except Exception as exc:
            rows.append(
                {
                    "case_id": _case_value(case, "case_id"),
                    "query": query,
                    "status": "failed",
                    "failure_category": "provider_error",
                    "error": f"{type(exc).__name__}: {exc}",
                    "runtime": round(time.perf_counter() - start, 4),
                }
            )

    summary = {
        "hidden_style_sample_count": len(rows),
        "malformed_tool_calls": sum(int(row.get("malformed_tool_calls", 0)) for row in rows),
        "unsupported_answers": sum(int(row.get("unsupported_answer", False)) for row in rows),
        "missing_evidence": sum(int(row.get("missing_evidence", False)) for row in rows),
        "dry_run_hallucination_risk": sum(int(row.get("dry_run_hallucination_risk", False)) for row in rows),
        "failure_categories": dict(Counter(row.get("failure_category", "ok") for row in rows if row.get("failure_category"))),
    }
    payload = {
        "framework": "generic_sdk_llm_baseline",
        "provider_type": provider_type,
        "backend_type": backend_type,
        "sdk_client": "SDK-based LLM client",
        "backend_name": client.model_name(),
        "model": client.model_name(),
        "status": "diagnostic_complete",
        "diagnostic_only": True,
        "summary": summary,
        "rows": rows,
        "recommendation": "keep_shadow_only",
        "notes": [
            "This is a small generic SDK LLM diagnostic, not the official hidden-style eval.",
            "The deterministic packaged path remains unchanged.",
        ],
    }
    return _safe_report_payload(payload)


def _diagnostic_row(case: Any, result: dict[str, Any], runtime: float) -> dict[str, Any]:
    invalid = int(result.get("invalid_tool_call_count", result.get("trajectory", {}).get("invalid_tool_call_count", 0)) or 0)
    evidence_count = int(result.get("successful_evidence_count", result.get("trajectory", {}).get("successful_evidence_count", 0)) or 0)
    dry_run = int(result.get("dry_run_only_api_count", result.get("trajectory", {}).get("dry_run_only_api_count", 0)) or 0)
    answer = str(result.get("final_answer", ""))
    unsupported = not bool(answer.strip()) or bool(result.get("unsupported_negative_answer_count"))
    missing_evidence = evidence_count == 0 and result.get("tool_calls_executed", False)
    dry_run_hallucination_risk = dry_run > 0 and not any(token in answer.lower() for token in ["dry-run", "unavailable", "credentials"])
    failure_category = ""
    if result.get("skipped_or_failed") or not result.get("valid_agent_run", True):
        failure_category = "provider_error" if "request" in str(result.get("failure_reason", "")).lower() else "validation_failed"
    elif invalid:
        failure_category = "invalid_tool_call"
    elif missing_evidence:
        failure_category = "missing_evidence"
    elif dry_run_hallucination_risk:
        failure_category = "dry_run_hallucination_risk"
    return {
        "case_id": _case_value(case, "case_id"),
        "query": _case_value(case, "query"),
        "status": "ok" if not failure_category else "risk_observed",
        "failure_category": failure_category,
        "malformed_tool_calls": invalid,
        "unsupported_answer": unsupported,
        "missing_evidence": missing_evidence,
        "dry_run_hallucination_risk": dry_run_hallucination_risk,
        "tool_calls": result.get("tool_call_count", result.get("trajectory", {}).get("tool_call_count", 0)),
        "runtime": round(runtime, 4),
        "final_answer_preview": answer[:300],
    }


def _case_value(case: Any, key: str) -> str:
    if isinstance(case, dict):
        return str(case.get(key, ""))
    return str(getattr(case, key, ""))


def write_report(config: Config, payload: dict[str, Any]) -> None:
    json_path = config.outputs_dir / "llm_hidden_style_diagnostic.json"
    md_path = config.outputs_dir / "llm_hidden_style_diagnostic.md"
    json_path.write_text(json.dumps(_safe_report_payload(payload), indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload.get("summary", {})
    lines = [
        "# SDK LLM Hidden-Style Diagnostic",
        "",
        f"- Framework: `{payload.get('framework')}`",
        f"- Provider type: `{payload.get('provider_type')}`",
        f"- Backend type: `{payload.get('backend_type')}`",
        f"- Current LLM backend: `{payload.get('backend_name')}`",
        f"- Status: `{payload.get('status')}`",
        f"- Diagnostic only: `{payload.get('diagnostic_only', True)}`",
        f"- Recommendation: `{payload.get('recommendation')}`",
        "",
        "The LLM baseline framework is generic; the configured model/provider is backend metadata.",
        "",
        "## Summary",
        "",
        f"- Hidden-style sample count: `{summary.get('hidden_style_sample_count')}`",
        f"- Malformed tool calls: `{summary.get('malformed_tool_calls')}`",
        f"- Unsupported answers: `{summary.get('unsupported_answers')}`",
        f"- Missing evidence: `{summary.get('missing_evidence')}`",
        f"- Dry-run hallucination risk: `{summary.get('dry_run_hallucination_risk')}`",
        "",
        "This diagnostic does not claim official hidden-style robustness.",
        "",
    ]
    return "\n".join(lines)


def _safe_report_payload(payload: dict[str, Any]) -> dict[str, Any]:
    safe = redact_secrets(payload)
    for key in ["framework", "provider_type", "backend_type", "sdk_client", "backend_name", "model", "status", "diagnostic_only", "recommendation"]:
        if key in payload:
            safe[key] = payload.get(key)
    return safe


if __name__ == "__main__":
    raise SystemExit(main())
