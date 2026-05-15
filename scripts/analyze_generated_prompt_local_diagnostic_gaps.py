#!/usr/bin/env python
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.trajectory import redact_secrets


GAP_REPORT_STEM = "generated_prompt_local_gap_samples"
CANDIDATE_REPORT_STEM = "local_deterministic_improvement_candidates"
GAP_TYPES = [
    "route_mismatch",
    "domain_mismatch",
    "answer_intent_mismatch",
    "missing_count_or_name_advisory",
    "zero_row_sql",
    "requires_live_api",
]
ALLOWED_MODULES = {
    "deterministic router synonyms",
    "query token extraction",
    "answer intent classifier",
    "deterministic answer templates",
    "zero-row answer wording",
}


def main() -> int:
    config = Config.from_env(ROOT)
    gap_report, candidate_report = analyze_generated_prompt_local_diagnostic_gaps(config)
    print(
        json.dumps(
            {
                "gap_report": str(config.outputs_dir / "reports" / f"{GAP_REPORT_STEM}.json"),
                "candidate_report": str(config.outputs_dir / "reports" / f"{CANDIDATE_REPORT_STEM}.json"),
                "gap_types": len(gap_report.get("gap_types", {})),
                "implementation_ready_count": candidate_report.get("implementation_ready_count"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def analyze_generated_prompt_local_diagnostic_gaps(config: Config | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    config = config or Config.from_env(ROOT)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    source_path = reports_dir / "generated_prompt_suite_local_diagnostic.json"
    source = _load_json(source_path)
    rows = [row for row in source.get("rows", []) if isinstance(row, dict)]
    gap_report = redact_secrets(_build_gap_report(config, source_path, source, rows))
    candidate_report = redact_secrets(_build_candidate_report(gap_report))
    (reports_dir / f"{GAP_REPORT_STEM}.json").write_text(
        json.dumps(gap_report, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    (reports_dir / f"{GAP_REPORT_STEM}.md").write_text(_render_gap_md(gap_report), encoding="utf-8")
    (reports_dir / f"{CANDIDATE_REPORT_STEM}.json").write_text(
        json.dumps(candidate_report, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    (reports_dir / f"{CANDIDATE_REPORT_STEM}.md").write_text(_render_candidate_md(candidate_report), encoding="utf-8")
    return gap_report, candidate_report


def _build_gap_report(config: Config, source_path: Path, source: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    gap_sections: dict[str, Any] = {}
    for gap_type in GAP_TYPES:
        selected = [row for row in rows if _row_has_gap(row, gap_type)]
        gap_sections[gap_type] = {
            "total_count": len(selected),
            "top_domain_families": dict(Counter(str(row.get("domain_family") or "unknown") for row in selected).most_common(10)),
            "representative_examples": [_example(row, gap_type) for row in selected[:10]],
        }
    return {
        "report_type": GAP_REPORT_STEM,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "diagnostic_only": True,
        "official_score_claim": False,
        "promotion_allowed": False,
        "generated_prompt_score_claim": False,
        "heuristics_are_advisory_only": True,
        "source_report": _rel(config, source_path),
        "source_total_prompts": source.get("total_prompts"),
        "source_executed_prompts": source.get("executed_prompts"),
        "gap_types": gap_sections,
        "rules": [
            "Generated prompt labels are diagnostic-only and may contain label noise.",
            "Representative examples must not be converted into exact prompt-specific runtime rules.",
            "No runtime behavior is changed by this sampler.",
        ],
    }


def _example(row: dict[str, Any], gap_type: str) -> dict[str, Any]:
    cause = _likely_cause(row, gap_type)
    return {
        "prompt_id": row.get("prompt_id"),
        "prompt": row.get("prompt"),
        "expected_route_label": row.get("expected_route_label"),
        "expected_domain_family": row.get("domain_family"),
        "expected_answer_intent": row.get("answer_intent"),
        "actual_route": row.get("actual_route"),
        "actual_domain": row.get("domain_type"),
        "actual_answer_intent": row.get("actual_answer_intent"),
        "sql_api_behavior_summary": {
            "sql_calls": row.get("sql_calls"),
            "api_calls": row.get("api_calls"),
            "dry_run_count": row.get("dry_run_count"),
            "sql_template": row.get("sql_template"),
            "evidence_state": row.get("evidence_state"),
            "zero_row_sql": row.get("zero_row_sql"),
        },
        "final_answer_excerpt": _excerpt(row.get("final_answer")),
        "likely_cause": cause,
        "suggested_action": _suggested_action(cause),
        "confidence": _confidence(row, gap_type, cause),
    }


def _build_candidate_report(gap_report: dict[str, Any]) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for gap_type, section in (gap_report.get("gap_types") or {}).items():
        examples = section.get("representative_examples") or []
        by_domain = section.get("top_domain_families") or {}
        for domain, count in by_domain.items():
            domain_examples = [ex for ex in examples if ex.get("expected_domain_family") == domain]
            likely_causes = Counter(str(ex.get("likely_cause") or "no_action") for ex in domain_examples)
            dominant_cause = likely_causes.most_common(1)[0][0] if likely_causes else "no_action"
            suggested_action = _suggested_action(dominant_cause)
            implementation_ready = _implementation_ready(gap_type, int(count), dominant_cause, suggested_action)
            candidates.append(
                {
                    "candidate_id": f"{gap_type}:{domain}",
                    "gap_type": gap_type,
                    "affected_domain_family": domain,
                    "evidence_count": int(count),
                    "representative_prompt_ids": [ex.get("prompt_id") for ex in domain_examples[:5]],
                    "proposed_fix": _proposed_fix(gap_type, dominant_cause),
                    "allowed_module": _allowed_module(gap_type, dominant_cause),
                    "required_tests": _required_tests(gap_type, dominant_cause),
                    "risk_level": "low" if implementation_ready else "medium",
                    "implementation_ready": implementation_ready,
                    "reason": _candidate_reason(gap_type, int(count), dominant_cause, implementation_ready),
                }
            )
    ready = [candidate for candidate in candidates if candidate["implementation_ready"]]
    return {
        "report_type": CANDIDATE_REPORT_STEM,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "diagnostic_only": True,
        "official_score_claim": False,
        "promotion_allowed": False,
        "generated_prompt_score_claim": False,
        "source_report": "outputs/reports/generated_prompt_local_gap_samples.json",
        "allowed_modules": sorted(ALLOWED_MODULES),
        "implementation_gate": {
            "minimum_repeated_gap_count": 3,
            "reject_generated_label_noise": True,
            "requires_schema_or_evidence_support": True,
            "requires_general_deterministic_rule": True,
            "requires_low_regression_risk": True,
            "requires_focused_tests": True,
            "must_not_depend_on_live_api_success": True,
        },
        "implementation_ready_count": len(ready),
        "no_safe_deterministic_improvement_applied": len(ready) == 0,
        "runtime_change_applied": False,
        "candidates": candidates[:50],
    }


def _row_has_gap(row: dict[str, Any], gap_type: str) -> bool:
    if gap_type == "route_mismatch":
        return row.get("route_matches_diagnostic") is False
    if gap_type == "domain_mismatch":
        return row.get("domain_matches_diagnostic") is False
    if gap_type == "answer_intent_mismatch":
        return row.get("answer_intent_matches_diagnostic") is False
    if gap_type == "missing_count_or_name_advisory":
        return bool(row.get("missing_count_or_name_advisory"))
    if gap_type == "zero_row_sql":
        return bool(row.get("zero_row_sql"))
    if gap_type == "requires_live_api":
        return bool(row.get("requires_live_api"))
    return False


def _likely_cause(row: dict[str, Any], gap_type: str) -> str:
    if gap_type == "requires_live_api":
        return "live_api_required"
    if gap_type == "zero_row_sql":
        return "schema_or_sql_gap"
    if gap_type == "missing_count_or_name_advisory":
        if row.get("evidence_state") == "dry_run_unavailable":
            return "live_api_required"
        return "answer_template_gap"
    if gap_type == "answer_intent_mismatch":
        expected = str(row.get("answer_intent") or "").upper()
        actual = str(row.get("actual_answer_intent") or "").upper()
        if {expected, actual} <= {"DATE", "WHEN", "STATUS"}:
            return "generated_label_noise"
        return "answer_intent_gap"
    if gap_type == "route_mismatch":
        if int(row.get("dry_run_count") or 0) > 0:
            return "live_api_required"
        return "deterministic_router_gap"
    if gap_type == "domain_mismatch":
        return "synonym_gap"
    return "no_action"


def _suggested_action(cause: str) -> str:
    return {
        "generated_label_noise": "no_code_change",
        "synonym_gap": "add_synonym_candidate",
        "deterministic_router_gap": "add_synonym_candidate",
        "answer_intent_gap": "add_intent_rule_candidate",
        "answer_template_gap": "add_answer_template_candidate",
        "schema_or_sql_gap": "review_schema_mapping",
        "live_api_required": "wait_for_live_api",
        "no_action": "no_code_change",
    }.get(cause, "no_code_change")


def _confidence(row: dict[str, Any], gap_type: str, cause: str) -> str:
    if cause in {"live_api_required", "generated_label_noise"}:
        return "high"
    if gap_type in {"missing_count_or_name_advisory", "answer_intent_mismatch"}:
        return "medium"
    return "low"


def _implementation_ready(gap_type: str, count: int, cause: str, suggested_action: str) -> bool:
    if count < 3:
        return False
    if cause in {"generated_label_noise", "live_api_required", "no_action", "schema_or_sql_gap"}:
        return False
    if suggested_action in {"wait_for_live_api", "review_schema_mapping", "no_code_change"}:
        return False
    # This pass proposes only. Runtime implementation still requires manual evidence review.
    return False


def _allowed_module(gap_type: str, cause: str) -> str:
    if gap_type == "zero_row_sql":
        return "zero-row answer wording"
    if gap_type == "missing_count_or_name_advisory":
        return "deterministic answer templates"
    if gap_type == "answer_intent_mismatch":
        return "answer intent classifier"
    if gap_type in {"route_mismatch", "domain_mismatch"}:
        return "deterministic router synonyms"
    return "query token extraction"


def _proposed_fix(gap_type: str, cause: str) -> str:
    if cause == "live_api_required":
        return "Wait for at least one safe GET live_success before API-dependent changes."
    if cause == "generated_label_noise":
        return "No code change; review generated diagnostic labels before treating mismatch as a system gap."
    if gap_type == "zero_row_sql":
        return "Review schema mapping and improve zero-row wording only if local evidence supports a general rule."
    if gap_type == "missing_count_or_name_advisory":
        return "Consider deterministic answer wording that surfaces available counts/names when evidence exists."
    if gap_type == "answer_intent_mismatch":
        return "Consider a general answer-intent rule after confirming labels are not noisy."
    return "Consider a general synonym/token rule after confirming repeated non-label-noise failures."


def _required_tests(gap_type: str, cause: str) -> list[str]:
    if cause in {"live_api_required", "generated_label_noise"}:
        return ["No runtime test required unless a future code change is proposed."]
    if gap_type == "zero_row_sql":
        return ["zero-row SQL wording does not fabricate data", "dry_run_unavailable remains distinct from zero-row SQL"]
    if gap_type == "missing_count_or_name_advisory":
        return ["answer includes available counts/names", "answer does not fabricate unavailable API values"]
    if gap_type == "answer_intent_mismatch":
        return ["answer intent classifier maps representative paraphrases", "hidden-style remains 48/48"]
    return ["router synonym maps general paraphrase", "public/dev strict eval does not regress"]


def _candidate_reason(gap_type: str, count: int, cause: str, implementation_ready: bool) -> str:
    if implementation_ready:
        return "passes diagnostic threshold and is eligible for a separate tested implementation pass"
    if count < 3:
        return "fewer than 3 repeated examples"
    if cause == "generated_label_noise":
        return "representative examples look like generated-label noise"
    if cause == "live_api_required":
        return "depends on live Adobe API success, which is currently blocked"
    if cause == "schema_or_sql_gap":
        return "needs schema review before code changes"
    return "diagnostic-only proposal; requires manual evidence review before implementation"


def _excerpt(value: Any, max_chars: int = 240) -> str:
    text = str(value or "")
    return text[:max_chars]


def _render_gap_md(report: dict[str, Any]) -> str:
    lines = [
        "# Generated Prompt Local Gap Samples",
        "",
        "Diagnostic-only sampler for local dry-run generated prompts. Generated labels may be noisy and are not official score evidence.",
        "",
        f"- Source prompts: `{report.get('source_executed_prompts')}` / `{report.get('source_total_prompts')}`",
        f"- Official score claim: `{report.get('official_score_claim')}`",
        "",
    ]
    for gap_type, section in (report.get("gap_types") or {}).items():
        lines.extend(
            [
                f"## {gap_type}",
                "",
                f"- Total count: `{section.get('total_count')}`",
                f"- Top domains: `{section.get('top_domain_families')}`",
                "",
            ]
        )
        for example in (section.get("representative_examples") or [])[:5]:
            lines.append(
                f"- `{example.get('prompt_id')}` cause=`{example.get('likely_cause')}` "
                f"action=`{example.get('suggested_action')}` prompt={_excerpt(example.get('prompt'), 120)!r}"
            )
        lines.append("")
    return "\n".join(lines)


def _render_candidate_md(report: dict[str, Any]) -> str:
    lines = [
        "# Local Deterministic Improvement Candidates",
        "",
        "Diagnostic-only candidate report. No runtime changes are applied by this report.",
        "",
        f"- Implementation-ready count: `{report.get('implementation_ready_count')}`",
        f"- No safe deterministic improvement applied: `{report.get('no_safe_deterministic_improvement_applied')}`",
        f"- Runtime change applied: `{report.get('runtime_change_applied')}`",
        "",
        "## Candidates",
        "",
    ]
    candidates = report.get("candidates") or []
    if not candidates:
        lines.append("- No candidates were produced.")
    for candidate in candidates[:20]:
        lines.append(
            f"- `{candidate.get('candidate_id')}` ready=`{candidate.get('implementation_ready')}` "
            f"count=`{candidate.get('evidence_count')}` reason={candidate.get('reason')}"
        )
    return "\n".join(lines) + "\n"


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _rel(config: Config, path: Path) -> str:
    try:
        return path.resolve().relative_to(config.project_root.resolve()).as_posix()
    except Exception:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
