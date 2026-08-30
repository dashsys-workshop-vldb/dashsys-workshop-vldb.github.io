#!/usr/bin/env python
from __future__ import annotations

import json
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
from scripts.load_local_env import load_local_env

REPORT_STEM = "pure_llm_multi_backend_eval"
BACKENDS = ["openai", "openrouter", "anthropic", "deterministic_no_llm"]


def main() -> int:
    config = Config.from_env(ROOT)
    load_local_env(config.project_root)
    payload = run_pure_llm_multi_backend_eval(config)
    print(json.dumps({"json": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.json"), "executed_backend_count": payload["summary"]["executed_backend_count"]}, indent=2))
    return 0


def run_pure_llm_multi_backend_eval(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    base_eval = _load_json(reports_dir / "pure_llm_tool_agent_eval.json")
    backends = []
    for backend in BACKENDS:
        if backend == "deterministic_no_llm":
            backends.append({"backend": backend, "available": True, "executed": True, "llm_calls_executed": 0, "status": "no_llm_reference"})
            continue
        client = get_llm_client(backend)
        available = bool(client.available())
        probe = _probe(client) if available else {"ok": False, "reason": "credentials_or_provider_unavailable"}
        backends.append(
            {
                "backend": backend,
                "available": available,
                "request_ok": probe.get("ok"),
                "executed": bool(probe.get("ok")),
                "llm_calls_executed": 1 if probe.get("ok") else 0,
                "provider": client.provider_name(),
                "model": client.model_name(),
                "status": "smoke_ok_not_full_eval" if probe.get("ok") else "unavailable_or_request_failed",
                "reason": probe.get("reason"),
            }
        )
    payload = redact_secrets(
        {
            "report_type": REPORT_STEM,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "diagnostic_only": True,
            "promotion_allowed": False,
            "sdk_only_policy": True,
            "best_variant_from_primary_eval": (base_eval.get("summary") or {}).get("best_variant"),
            "summary": {
                "executed_backend_count": sum(1 for item in backends if item.get("executed")),
                "available_backend_count": sum(1 for item in backends if item.get("available")),
                "answer_drift": "not_measured_without_explicit_cross_backend_execution",
                "tool_call_variance": "not_measured_without_explicit_cross_backend_execution",
            },
            "backends": backends,
        }
    )
    (reports_dir / f"{REPORT_STEM}.json").write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    (reports_dir / f"{REPORT_STEM}.md").write_text(_render_md(payload), encoding="utf-8")
    return payload


def _probe(client: Any) -> dict[str, Any]:
    response = client.generate("Return JSON only.", '{"ok": true}')
    if response.get("ok"):
        return {"ok": True, "reason": None}
    return {"ok": False, "reason": response.get("error") or response.get("reason") or "request_failed"}


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _render_md(payload: dict[str, Any]) -> str:
    lines = ["# Pure LLM Multi-Backend Eval", "", "No cross-backend hosted LLM calls are executed by default.", ""]
    for item in payload.get("backends", []):
        lines.append(f"- `{item.get('backend')}`: `{item.get('status')}`")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
