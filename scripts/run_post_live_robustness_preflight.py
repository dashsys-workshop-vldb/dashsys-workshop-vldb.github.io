#!/usr/bin/env python
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.trajectory import redact_secrets
from scripts.check_submission_ready import check_submission_ready


REPORT_STEM = "post_live_robustness_preflight"


def main() -> int:
    config = Config.from_env(ROOT)
    report = run_post_live_robustness_preflight(config)
    print(
        json.dumps(
            {
                "json": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.json"),
                "markdown": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.md"),
                "current_score": report.get("current_score"),
                "endpoint_matrix": report.get("endpoint_matrix_summary"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def run_post_live_robustness_preflight(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    strict = _load_json(config.outputs_dir / "eval_results_strict.json")
    hidden = _load_json(config.outputs_dir / "hidden_style_eval.json")
    smoke = _load_json(reports_dir / "live_api_readiness_smoke.json")
    baseline = _load_json(reports_dir / "live_api_score_regression_baseline.json")
    arbitration = _load_json(reports_dir / "live_api_evidence_arbitration_trial.json")
    coverage = _load_json(reports_dir / "sql_template_coverage_audit.json")
    llm_baseline = _load_json(reports_dir / "llm_baseline_summary.json")
    controller = _load_json(reports_dir / "controller_rewrite_ablation.json")
    check = _safe_submission_check(config)

    current_score = _strict_score(strict)
    previous_baseline = (baseline.get("baseline") or {}).get("strict_score")
    initial_live = (baseline.get("live") or {}).get("strict_score")
    report = redact_secrets(
        {
            "report_type": REPORT_STEM,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "git_status_short": _git(["status", "--short"]),
            "current_branch": _git(["branch", "--show-current"]).strip() or "unavailable",
            "current_score": current_score,
            "previous_baseline_score": previous_baseline,
            "initial_live_regression_score": initial_live,
            "baseline_delta": baseline.get("delta"),
            "hidden_style_result": _hidden_summary(hidden),
            "check_submission_ready": {
                "ok": check.get("ok"),
                "query_output_count": check.get("query_output_count"),
                "default_strategy_is_sql_first_api_verify": check.get("default_strategy_is_sql_first_api_verify"),
            },
            "endpoint_matrix_summary": smoke.get("outcome_counts") or {},
            "active_arbitration_policy": arbitration.get("recommended_variant") or "unavailable",
            "arbitration_promotion_decision": arbitration.get("promotion_decision"),
            "nl_to_sql_template_coverage": {
                "row_count": coverage.get("row_count"),
                "template_hit_count": coverage.get("template_hit_count"),
                "template_miss_count": coverage.get("template_miss_count"),
                "template_hit_rate": coverage.get("template_hit_rate"),
                "template_miss_rate": coverage.get("template_miss_rate"),
            },
            "llm_baseline_controller_status": {
                "llm_baseline_summary_available": bool(llm_baseline),
                "controller_rewrite_ablation_available": bool(controller),
                "controller_recommendation": (controller.get("summary") or {}).get("recommendation"),
            },
            "known_risks": [
                "template dependency remains the main NL-to-SQL generalization risk",
                "schema-aware fallback previously regressed strict score and remains keep_trial_only",
                "pure LLM tool-grounding is weaker than deterministic SQL_FIRST_API_VERIFY",
                "generated prompts need post-live diagnostic rerun",
                "multi-LLM robustness is diagnostic-only and not a packaged promotion gate yet",
            ],
            "missing_source_reports": _missing_reports(config),
        }
    )
    (reports_dir / f"{REPORT_STEM}.json").write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    (reports_dir / f"{REPORT_STEM}.md").write_text(_render_md(report), encoding="utf-8")
    return report


def _safe_submission_check(config: Config) -> dict[str, Any]:
    try:
        return check_submission_ready(config)
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def _strict_score(payload: dict[str, Any]) -> Any:
    return (
        payload.get("summary", {})
        .get("by_strategy", {})
        .get("SQL_FIRST_API_VERIFY", {})
        .get("avg_final_score")
    )


def _hidden_summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    return {
        "passed_cases": summary.get("passed_cases") or payload.get("passed"),
        "total_cases": summary.get("total_cases") or payload.get("total"),
        "failed_cases": summary.get("failed_cases") or payload.get("failures"),
    }


def _missing_reports(config: Config) -> list[str]:
    reports = config.outputs_dir / "reports"
    required = [
        config.outputs_dir / "eval_results_strict.json",
        config.outputs_dir / "hidden_style_eval.json",
        reports / "live_api_readiness_smoke.json",
        reports / "live_api_score_regression_baseline.json",
        reports / "live_api_evidence_arbitration_trial.json",
        reports / "sql_template_coverage_audit.json",
    ]
    return [_rel(config, path) for path in required if not path.exists()]


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "unavailable"


def _rel(config: Config, path: Path) -> str:
    try:
        return path.resolve().relative_to(config.project_root.resolve()).as_posix()
    except Exception:
        return str(path)


def _render_md(report: dict[str, Any]) -> str:
    lines = [
        "# Post-Live Robustness Preflight",
        "",
        f"- Current branch: `{report.get('current_branch')}`",
        f"- Current strict score: `{report.get('current_score')}`",
        f"- Previous pre-live baseline: `{report.get('previous_baseline_score')}`",
        f"- Initial live regression score: `{report.get('initial_live_regression_score')}`",
        f"- Endpoint matrix: `{report.get('endpoint_matrix_summary')}`",
        f"- Active arbitration policy: `{report.get('active_arbitration_policy')}`",
        f"- check_submission_ready ok: `{report.get('check_submission_ready', {}).get('ok')}`",
        "",
        "## Known Risks",
        "",
    ]
    lines.extend(f"- {item}" for item in report.get("known_risks", []))
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
