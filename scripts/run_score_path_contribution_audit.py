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


REPORT_STEM = "score_path_contribution_audit"


DIRECT_SCORE_COMPONENTS = [
    "router",
    "intent/domain detection",
    "SQL_FIRST_API_VERIFY",
    "SQL/API plan",
    "SQL validation/execution",
    "API evidence state",
    "EvidenceBus",
    "answer slots",
    "answer synthesis",
    "verifier",
    "eval output",
    "final submission trajectory",
]

SCORE_PROTECTION_COMPONENTS = [
    "validators",
    "check_submission_ready",
    "hidden-style eval",
    "live_success guard",
    "no hardcoding checks",
    "secret scan",
    "SDK-only LLM audit",
]

EXTERNAL_BLOCKERS = [
    "Adobe sandbox permission",
    "live API credential access",
    "live endpoint success",
]

DIAGNOSTIC_ONLY_COMPONENTS = [
    "generated prompts",
    "Context7 audit",
    "Playwright setup",
    "Superpowers review",
    "visualization/reporting",
]


def main() -> int:
    config = Config.from_env(ROOT)
    payload = run_score_path_contribution_audit(config)
    print(
        json.dumps(
            {
                "json": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.json"),
                "markdown": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.md"),
                "primary_score_focus": payload["conclusions"]["primary_score_focus"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def run_score_path_contribution_audit(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports = config.outputs_dir / "reports"
    reports.mkdir(parents=True, exist_ok=True)

    sources = _load_sources(config)
    strict_score = _strict_score(sources)
    live_success_count = _live_success_count(sources)
    packaged_strategy = _packaged_strategy(sources)
    bottlenecks = _bottleneck_distribution(sources)
    evidence_issues = _evidence_issue_distribution(sources)

    payload = {
        "report_type": REPORT_STEM,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "diagnostic_only": True,
        "official_score_claim": False,
        "packaged_strategy": packaged_strategy,
        "strict_score": strict_score,
        "live_success_count": live_success_count,
        "source_reports": _source_report_status(config),
        "bottleneck_distribution": bottlenecks,
        "evidence_issue_distribution": evidence_issues,
        "classifications": {
            "direct_score_path": _direct_score_path(bottlenecks, evidence_issues),
            "score_protection_guard": _fixed_classification(SCORE_PROTECTION_COMPONENTS, "protects_score_integrity"),
            "external_blocker": _fixed_classification(EXTERNAL_BLOCKERS, "blocked_by_adobe_access"),
            "diagnostic_only": _fixed_classification(DIAGNOSTIC_ONLY_COMPONENTS, "do_not_optimize_for_score_now"),
        },
        "conclusions": {
            "can_realistically_improve_score_now": [
                "answer synthesis",
                "SQL evidence usage",
                "dry-run wording",
                "answer slots",
                "verifier output wording",
            ],
            "blocked_by_adobe_access": [
                "live Adobe API evidence",
                "API-only rows that need sandbox/permission access",
                "full live strict eval and live generated-prompt diagnostics",
            ],
            "primary_score_focus": [
                "answer synthesis",
                "SQL evidence usage",
                "dry-run wording",
            ],
            "do_not_touch_for_score_now": [
                "visualization/reporting aesthetics",
                "Context7 reports",
                "Playwright reports",
                "generated prompt labels as promotion evidence",
                "LLM controller / semantic router / broad answer rewrite promotion",
            ],
            "expected_conclusion": (
                "Use the SVG as a map, but keep score work on the direct runtime path. "
                "Before Adobe access is fixed, the realistic score trial surface is answer synthesis, "
                "SQL evidence usage, and dry-run wording. Live API score gains remain externally blocked."
            ),
        },
        "runtime_behavior_changed": False,
        "final_submission_changed": False,
        "credentials_accessed": False,
        "env_local_accessed": False,
    }
    payload = redact_secrets(payload)
    _write_json(reports / f"{REPORT_STEM}.json", payload)
    (reports / f"{REPORT_STEM}.md").write_text(_render_markdown(payload), encoding="utf-8")
    return payload


def _load_sources(config: Config) -> dict[str, Any]:
    outputs = config.outputs_dir
    reports = outputs / "reports"
    visualizations = outputs / "visualizations"
    return {
        "full_project_dataflow": _load_json(visualizations / "full_project_dataflow.json"),
        "workflow_decision_audit": _load_json(reports / "workflow_decision_audit.json"),
        "accuracy_and_bottleneck_summary": _load_json(reports / "accuracy_and_bottleneck_summary.json"),
        "evidence_usage_audit": _load_json(reports / "evidence_usage_audit.json"),
        "sql_evidence_usage_audit": _load_json(reports / "sql_evidence_usage_audit.json"),
        "evidence_aware_answer_rewrite_trial": _load_json(reports / "evidence_aware_answer_rewrite_trial.json"),
        "eval_results_strict": _load_json(outputs / "eval_results_strict.json"),
    }


def _source_report_status(config: Config) -> list[dict[str, Any]]:
    paths = [
        "outputs/visualizations/full_project_dataflow.svg",
        "outputs/reports/workflow_decision_audit.json",
        "outputs/reports/accuracy_and_bottleneck_summary.json",
        "outputs/reports/evidence_usage_audit.json",
        "outputs/reports/sql_evidence_usage_audit.json",
        "outputs/reports/evidence_aware_answer_rewrite_trial.json",
        "outputs/eval_results_strict.json",
    ]
    rows = []
    for rel in paths:
        path = config.project_root / rel
        rows.append({"path": rel, "exists": path.exists()})
    return rows


def _strict_score(sources: dict[str, Any]) -> float | None:
    svg = sources.get("full_project_dataflow") or {}
    if svg.get("strict_score") is not None:
        return round(float(svg["strict_score"]), 4)
    strict = sources.get("eval_results_strict") or {}
    return _baseline_score(strict)


def _baseline_score(strict: dict[str, Any]) -> float | None:
    try:
        return round(
            float(((strict.get("summary") or {}).get("by_strategy") or {}).get("SQL_FIRST_API_VERIFY", {}).get("avg_final_score")),
            4,
        )
    except Exception:
        return None


def _live_success_count(sources: dict[str, Any]) -> int:
    svg = sources.get("full_project_dataflow") or {}
    try:
        return int(svg.get("live_success_count") or 0)
    except Exception:
        return 0


def _packaged_strategy(sources: dict[str, Any]) -> str:
    svg = sources.get("full_project_dataflow") or {}
    return str(svg.get("packaged_strategy") or "SQL_FIRST_API_VERIFY")


def _bottleneck_distribution(sources: dict[str, Any]) -> dict[str, int]:
    workflow = sources.get("workflow_decision_audit") or {}
    raw = workflow.get("bottleneck_distribution") or {}
    return {str(key): int(value or 0) for key, value in raw.items()}


def _evidence_issue_distribution(sources: dict[str, Any]) -> dict[str, int]:
    evidence = sources.get("evidence_usage_audit") or {}
    sql = sources.get("sql_evidence_usage_audit") or {}
    merged: dict[str, int] = {}
    for raw in [
        evidence.get("category_distribution") or {},
        ((sql.get("summary") or {}).get("issue_distribution") or {}),
    ]:
        for key, value in raw.items():
            merged[str(key)] = merged.get(str(key), 0) + int(value or 0)
    return merged


def _direct_score_path(bottlenecks: dict[str, int], evidence_issues: dict[str, int]) -> dict[str, dict[str, Any]]:
    components: dict[str, dict[str, Any]] = {}
    for component in DIRECT_SCORE_COMPONENTS:
        component_id = component.replace("/", "_").replace("-", "_").replace(" ", "_")
        relevance = "protect_do_not_weaken"
        reason = "This component affects strict score or final submission artifacts."
        if component in {"answer slots", "answer synthesis", "verifier", "EvidenceBus"}:
            relevance = "can_improve_now"
            reason = "Reports show answer/evidence usage gaps that can be tested without live Adobe API access."
        elif component == "API evidence state":
            relevance = "partly_blocked_by_adobe_access"
            reason = "Dry-run wording is testable now, but usable live API evidence waits for external access."
        elif component in {"SQL validation/execution", "SQL/API plan", "router", "intent/domain detection"}:
            relevance = "only_change_with_strict_evidence"
            reason = "These can change score but carry regression risk; generated-prompt labels alone are not enough."
        components[component_id] = {
            "label": component,
            "classification": "direct_score_path",
            "score_relevance": relevance,
            "reason": reason,
            "related_bottlenecks": _related_bottlenecks(component, bottlenecks, evidence_issues),
        }
    return components


def _related_bottlenecks(component: str, bottlenecks: dict[str, int], evidence_issues: dict[str, int]) -> dict[str, int]:
    if component in {"answer slots", "answer synthesis", "verifier", "EvidenceBus"}:
        keys = [
            "answer_uses_dry_run_poorly",
            "answer_shape_weak",
            "answer_missing_count",
            "answer_missing_names",
            "answer_missing_status",
            "answer_missing_timestamp",
            "zero_row_answer_unclear",
            "answer_missed_count",
            "answer_missed_status",
        ]
        source = {**bottlenecks, **evidence_issues}
        return {key: int(source.get(key, 0)) for key in keys if int(source.get(key, 0))}
    if component == "API evidence state":
        return {
            key: int(bottlenecks.get(key, 0))
            for key in ["api_only_needs_live_credentials", "api_required_but_credentials_missing"]
            if int(bottlenecks.get(key, 0))
        }
    return {}


def _fixed_classification(components: list[str], relevance: str) -> dict[str, dict[str, Any]]:
    return {
        component: {
            "classification": relevance,
            "score_relevance": relevance,
            "reason": _fixed_reason(component, relevance),
        }
        for component in components
    }


def _fixed_reason(component: str, relevance: str) -> str:
    if relevance == "blocked_by_adobe_access":
        return f"{component} cannot be improved by code while live_success_count is zero and access is externally blocked."
    if relevance == "protects_score_integrity":
        return f"{component} protects score validity and must not be weakened for score chasing."
    return f"{component} is diagnostic/reporting support, not a direct strict-score path."


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"malformed": True, "path": str(path)}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")


def _render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Score Path Contribution Audit",
        "",
        "Diagnostic-only map from the full project dataflow and current score reports to the code paths that can affect strict score.",
        "",
        f"- Packaged strategy: `{payload.get('packaged_strategy')}`",
        f"- Strict score: `{payload.get('strict_score')}`",
        f"- Live success count: `{payload.get('live_success_count')}`",
        f"- Official score claim: `{payload.get('official_score_claim')}`",
        f"- Runtime behavior changed: `{payload.get('runtime_behavior_changed')}`",
        "",
        "## Practical Conclusion",
        "",
        payload["conclusions"]["expected_conclusion"],
        "",
        "## Score Focus Now",
        "",
    ]
    lines.extend(f"- {item}" for item in payload["conclusions"]["primary_score_focus"])
    lines.extend(["", "## Blocked By Adobe Access", ""])
    lines.extend(f"- {item}" for item in payload["conclusions"]["blocked_by_adobe_access"])
    lines.extend(["", "## Do Not Touch For Score Now", ""])
    lines.extend(f"- {item}" for item in payload["conclusions"]["do_not_touch_for_score_now"])
    lines.extend(["", "## Direct Score Path Components", ""])
    lines.append("| Component | Score relevance | Reason |")
    lines.append("| --- | --- | --- |")
    for name, item in payload["classifications"]["direct_score_path"].items():
        label = item.get("label") or name
        lines.append(f"| `{label}` | `{item['score_relevance']}` | {item['reason']} |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
