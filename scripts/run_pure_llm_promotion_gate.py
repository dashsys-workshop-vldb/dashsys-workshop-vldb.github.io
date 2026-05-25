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
from dashagent.trajectory import redact_secrets

REPORT_STEM = "pure_llm_promotion_gate"
FULL_SYSTEM_REFERENCE = 0.6567


def main() -> int:
    config = Config.from_env(ROOT)
    payload = run_pure_llm_promotion_gate(config)
    print(json.dumps({"json": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.json"), "recommendation": payload["recommendation"], "promotion_allowed": payload["promotion_allowed"]}, indent=2))
    return 0


def run_pure_llm_promotion_gate(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    eval_payload = _load_json(reports_dir / "pure_llm_tool_agent_eval.json")
    systems = (eval_payload.get("summary") or {}).get("systems", [])
    pure_systems = [
        item
        for item in systems
        if str(item.get("system")) != "LLM_CONTROLLER_OPTIMIZED_AGENT"
    ]
    best = max(
        [item for item in pure_systems if isinstance(item.get("strict_final_score"), (int, float))],
        key=lambda item: item.get("strict_final_score", 0),
        default={},
    )
    best_score = best.get("strict_final_score")
    sql_score = best.get("sql_score")
    unsupported = best.get("unsupported_claims", 0)
    beats_current_pure = isinstance(best_score, (int, float)) and best_score > 0.2244
    beats_controller = isinstance(best_score, (int, float)) and best_score > 0.6328
    beats_full = isinstance(best_score, (int, float)) and best_score > FULL_SYSTEM_REFERENCE
    recommendation = _recommendation(best_score, beats_current_pure, beats_controller, beats_full, unsupported, sql_score)
    payload = redact_secrets(
        {
            "report_type": REPORT_STEM,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "diagnostic_only": True,
            "promotion_allowed": False,
            "packaged_default_strategy": "SQL_FIRST_API_VERIFY",
            "best_variant": best.get("system"),
            "best_strict_score": best_score,
            "best_sql_score": sql_score,
            "unsupported_claim_count": unsupported,
            "beats_current_guided_pure_llm": beats_current_pure,
            "beats_controller": beats_controller,
            "beats_full_system": beats_full,
            "recommendation": recommendation,
            "gates": {
                "strict_improves_over_current_pure_llm": beats_current_pure,
                "sql_score_improves_from_near_zero": isinstance(sql_score, (int, float)) and sql_score > 0.12,
                "unsupported_claims_clean": unsupported == 0,
                "final_submission_format_unchanged": True,
                "packaged_runtime_unchanged": True,
            },
        }
    )
    (reports_dir / f"{REPORT_STEM}.json").write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    (reports_dir / f"{REPORT_STEM}.md").write_text(_render_md(payload), encoding="utf-8")
    return payload


def _recommendation(
    best_score: Any,
    beats_current_pure: bool,
    beats_controller: bool,
    beats_full: bool,
    unsupported: Any,
    sql_score: Any,
) -> str:
    if unsupported not in (0, None):
        return "blocked_by_unsupported_claims"
    if not isinstance(sql_score, (int, float)) or sql_score <= 0.12:
        return "blocked_by_sql_generation"
    if not beats_current_pure:
        return "pure_llm_still_too_weak"
    if not beats_controller:
        return "pure_llm_baseline_improved_keep_shadow"
    if not beats_full:
        return "controller_still_preferred"
    return "candidate_for_limited_promotion_review"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _render_md(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Pure LLM Promotion Gate",
            "",
            f"- Recommendation: `{payload.get('recommendation')}`",
            f"- Promotion allowed: `{payload.get('promotion_allowed')}`",
            f"- Best variant: `{payload.get('best_variant')}`",
            f"- Best strict score: `{payload.get('best_strict_score')}`",
            "",
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())
