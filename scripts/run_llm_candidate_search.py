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
from dashagent.llm_candidate_generator import llm_candidate_search_status
from dashagent.report_run import report_metadata
from scripts.run_official_token_reduction_eval import _load_json


def main() -> int:
    config = Config.from_env(ROOT)
    payload = run_llm_candidate_search(config)
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    json_path = config.outputs_dir / "llm_candidate_search.json"
    md_path = config.outputs_dir / "llm_candidate_search.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "status": payload["summary"]["status"]}, indent=2, sort_keys=True))
    return 0


def run_llm_candidate_search(config: Config) -> dict[str, Any]:
    status = llm_candidate_search_status()
    mining = _load_json(config.outputs_dir / "low_score_failure_mining_report.json")
    if not status.available:
        return {
            **report_metadata(config.outputs_dir),
            "mode": "llm_candidate_search",
            "skipped": True,
            "skip_reason": status.reason,
            "provider": status.provider,
            "packaged_execution_changed": False,
            "writes_eval_outputs": False,
            "writes_final_submission": False,
            "rows": [],
            "summary": {
                "status": "skipped_no_llm_key",
                "safe_rows": 0,
                "unsafe_rows": 0,
                "recommendation": "keep_shadow_only",
            },
            "notes": [
                "No LLM key is available, so optional LLM candidate search was skipped.",
                "Validation passes because LLM search is optional and isolated.",
            ],
        }
    return {
        **report_metadata(config.outputs_dir),
        "mode": "llm_candidate_search",
        "skipped": True,
        "skip_reason": "llm_key_present_but_live_generation_requires_explicit_operator_review",
        "provider": status.provider,
        "packaged_execution_changed": False,
        "writes_eval_outputs": False,
        "writes_final_submission": False,
        "candidate_prompt_constraints": [
            "no gold SQL/API/answers",
            "no public-query answers",
            "all outputs require deterministic validators and offline strict scoring",
        ],
        "target_rows_available": (mining.get("summary") or {}).get("top_10_target_rows", []),
        "rows": [],
        "summary": {
            "status": "skipped_operator_review_required",
            "safe_rows": 0,
            "unsafe_rows": 0,
            "recommendation": "keep_shadow_only",
        },
        "notes": [
            "A key is present, but this script does not trust or package LLM output directly.",
            "Run a later explicit operator-reviewed LLM search task to invoke a provider.",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# LLM Candidate Search",
        "",
        f"- Status: `{summary['status']}`",
        f"- Provider: `{payload.get('provider')}`",
        f"- Skipped: {payload.get('skipped')}",
        f"- Recommendation: `{summary['recommendation']}`",
        f"- Packaged execution changed: {payload.get('packaged_execution_changed')}",
    ]
    if payload.get("skip_reason"):
        lines.append(f"- Skip reason: {payload['skip_reason']}")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
