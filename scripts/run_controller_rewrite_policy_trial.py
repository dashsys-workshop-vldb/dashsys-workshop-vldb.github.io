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
from scripts.run_controller_rewrite_ablation import run_controller_rewrite_ablation


REPORT_STEM = "controller_rewrite_policy_trial"


def main() -> int:
    config = Config.from_env(ROOT)
    report = run_controller_rewrite_policy_trial(config)
    print(
        json.dumps(
            {
                "json": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.json"),
                "markdown": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.md"),
                "recommendation": report.get("recommendation"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def run_controller_rewrite_policy_trial(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    ablation = run_controller_rewrite_ablation(config)
    variants = {
        "current_controller": _variant(ablation, "llm_rewrite_current"),
        "backend_answer_only": _variant(ablation, "backend_answer_only"),
        "verifier_forced_backend_safe": _variant(ablation, "verifier_forced_backend_safe"),
        "minimal_style_edit_only": _variant(ablation, "minimal_llm_style_edit"),
        "no_rewrite_when_backend_complete": _variant(ablation, "no_rewrite_when_backend_answer_complete"),
        "evidence_locked_rewrite": _variant(ablation, "verifier_forced_backend_safe"),
        "answer_shape_template_after_backend": _variant(ablation, "minimal_llm_style_edit"),
    }
    recommendation = _recommendation(variants)
    report = redact_secrets(
        {
            "report_type": REPORT_STEM,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "diagnostic_only": True,
            "new_llm_calls": False,
            "official_score_claim": False,
            "automatic_promotion": False,
            "source_report": "outputs/reports/controller_rewrite_ablation.json",
            "variants": variants,
            "recommendation": recommendation,
            "promotion_allowed": False,
            "reason": "Controller rewrite remains diagnostic-only; deterministic SQL_FIRST_API_VERIFY remains packaged default.",
        }
    )
    (reports_dir / f"{REPORT_STEM}.json").write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    (reports_dir / f"{REPORT_STEM}.md").write_text(_render_md(report), encoding="utf-8")
    return report


def _variant(ablation: dict[str, Any], source_name: str) -> dict[str, Any]:
    item = (ablation.get("variants") or {}).get(source_name) or {}
    return {
        "source_variant": source_name,
        "strict_score_delta": item.get("avg_strict_final_score_delta_vs_current"),
        "answer_score_delta": item.get("avg_answer_score_delta_vs_current"),
        "sql_score_delta": item.get("sql_score_delta", 0),
        "api_score_delta": item.get("api_score_delta", 0),
        "unsupported_claim_delta": item.get("unsupported_claim_delta", 0),
        "rows_helped": item.get("helped_count"),
        "rows_hurt": item.get("hurt_count"),
        "token_delta": item.get("avg_token_delta"),
        "runtime_delta": item.get("avg_runtime_delta"),
        "backend_sql_api_behavior_preserved": item.get("backend_sql_api_behavior_preserved"),
        "backend_evidence_preserved": item.get("backend_evidence_preserved"),
        "recommendation": "candidate" if float(item.get("avg_strict_final_score_delta_vs_current") or 0) > 0 else "keep_trial_only",
    }


def _recommendation(variants: dict[str, dict[str, Any]]) -> str:
    candidates = [name for name, item in variants.items() if item.get("recommendation") == "candidate"]
    if "backend_answer_only" in candidates:
        return "backend_answer_only_shadow_candidate"
    if candidates:
        return "controller_rewrite_shadow_candidate"
    return "keep_current_controller_shadow_only"


def _render_md(report: dict[str, Any]) -> str:
    lines = [
        "# Controller Rewrite Policy Trial",
        "",
        "Diagnostic-only artifact replay. No controller rewrite policy is promoted.",
        "",
        f"- Recommendation: `{report.get('recommendation')}`",
        "",
        "## Variants",
        "",
    ]
    for name, item in report.get("variants", {}).items():
        lines.append(
            f"- `{name}`: strict delta `{item.get('strict_score_delta')}`, answer delta `{item.get('answer_score_delta')}`, "
            f"helped `{item.get('rows_helped')}`, hurt `{item.get('rows_hurt')}`"
        )
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
