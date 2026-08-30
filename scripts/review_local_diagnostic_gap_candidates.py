#!/usr/bin/env python
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.trajectory import redact_secrets


REVIEW_STEM = "local_gap_manual_review"
DECISION_STEM = "superpowers_fix_decision"
SAMPLE_LIMIT = 10

LIKELY_CAUSES = {
    "generated_label_noise",
    "live_api_required",
    "synonym_gap",
    "answer_intent_gap",
    "answer_template_gap",
    "SQL_template_gap",
    "schema_mapping_gap",
    "no_action",
}

SUGGESTED_ACTIONS = {
    "generated_label_noise": "no_code_change",
    "live_api_required": "wait_for_live_api",
    "synonym_gap": "add_synonym_candidate",
    "answer_intent_gap": "add_intent_rule_candidate",
    "answer_template_gap": "add_answer_template_candidate",
    "SQL_template_gap": "review_schema_mapping",
    "schema_mapping_gap": "review_schema_mapping",
    "no_action": "no_code_change",
}


def main() -> int:
    config = Config.from_env(ROOT)
    review, decision = review_local_diagnostic_gap_candidates(config)
    print(
        json.dumps(
            {
                "review_report": str(config.outputs_dir / "reports" / f"{REVIEW_STEM}.json"),
                "decision_report": str(config.outputs_dir / "reports" / f"{DECISION_STEM}.json"),
                "implementation_ready_count": decision.get("implementation_ready_count"),
                "runtime_change_applied": decision.get("runtime_change_applied"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def review_local_diagnostic_gap_candidates(config: Config | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    config = config or Config.from_env(ROOT)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    source_path = reports_dir / "generated_prompt_suite_local_diagnostic.json"
    source = load_json(source_path)
    rows = [row for row in source.get("rows", []) if isinstance(row, dict)]

    categories = build_category_reviews(config, rows)
    review = redact_secrets(
        {
            "report_type": REVIEW_STEM,
            "created_at": now(),
            "diagnostic_only": True,
            "official_score_claim": False,
            "promotion_allowed": False,
            "generated_labels_are_ground_truth": False,
            "advisory_only": True,
            "source_report": "outputs/reports/generated_prompt_suite_local_diagnostic.json",
            "source_total_prompts": source.get("total_prompts"),
            "source_executed_prompts": source.get("executed_prompts"),
            "reviewed_categories": categories,
            "rules": [
                "Generated labels are diagnostic hints, not ground truth.",
                "Each mismatch is compared against actual route/domain/intent and SQL/API evidence behavior.",
                "No runtime code is changed by this review.",
            ],
            "recommended_next_human_review": recommended_next_human_review(categories),
        }
    )
    decision = redact_secrets(build_fix_decision(review))

    (reports_dir / f"{REVIEW_STEM}.json").write_text(
        json.dumps(review, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    (reports_dir / f"{REVIEW_STEM}.md").write_text(render_review_md(review), encoding="utf-8")
    (reports_dir / f"{DECISION_STEM}.json").write_text(
        json.dumps(decision, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    (reports_dir / f"{DECISION_STEM}.md").write_text(render_decision_md(decision), encoding="utf-8")
    return review, decision


def build_category_reviews(config: Config, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    specs: list[tuple[str, str, Callable[[dict[str, Any]], bool]]] = [
        (
            "zero_row_sql / dataflow_run",
            "zero_row_sql",
            lambda row: bool(row.get("zero_row_sql")) and row.get("domain_family") == "dataflow_run",
        ),
        (
            "missing_count_or_name_advisory / segment_audience",
            "missing_count_or_name_advisory",
            lambda row: bool(row.get("missing_count_or_name_advisory")) and row.get("domain_family") == "segment_audience",
        ),
        (
            "answer_intent_mismatch / segment_audience",
            "answer_intent_mismatch",
            lambda row: row.get("answer_intent_matches_diagnostic") is False and row.get("domain_family") == "segment_audience",
        ),
        (
            "domain_mismatch / dataflow_run",
            "domain_mismatch",
            lambda row: row.get("domain_matches_diagnostic") is False and row.get("domain_family") == "dataflow_run",
        ),
        (
            "route_mismatch / destination_flow",
            "route_mismatch",
            lambda row: row.get("route_matches_diagnostic") is False and row.get("domain_family") == "destination_flow",
        ),
    ]
    reviews: list[dict[str, Any]] = []
    for name, gap_type, predicate in specs:
        selected = [row for row in rows if predicate(row)]
        examples = [review_example(config, row, gap_type) for row in selected[:SAMPLE_LIMIT]]
        cause_counts = Counter(str(example.get("likely_cause") or "no_action") for example in examples)
        true_bug_count = sum(1 for example in examples if example.get("true_bug") is True)
        live_api_count = sum(1 for example in examples if example.get("likely_cause") == "live_api_required")
        label_noise_count = sum(1 for example in examples if example.get("likely_cause") == "generated_label_noise")
        implementation_candidate = is_category_candidate(selected, examples)
        reviews.append(
            {
                "category": name,
                "gap_type": gap_type,
                "total_count": len(selected),
                "reviewed_count": len(examples),
                "true_bug_count": true_bug_count,
                "generated_label_noise_count": label_noise_count,
                "live_api_required_count": live_api_count,
                "likely_cause_distribution": dict(cause_counts),
                "implementation_candidate": implementation_candidate,
                "proposed_minimal_fix": proposed_minimal_fix(gap_type, examples, implementation_candidate),
                "risk_level": "low" if implementation_candidate else "medium",
                "required_tests": required_tests(gap_type, examples, implementation_candidate),
                "examples": examples,
            }
        )
    return reviews


def review_example(config: Config, row: dict[str, Any], gap_type: str) -> dict[str, Any]:
    trajectory = load_trajectory(config, row)
    sql_shape = sql_result_shape(row, trajectory)
    comparison = label_behavior_comparison(row, sql_shape)
    cause = likely_cause(row, gap_type, comparison, sql_shape)
    deterministic_possible = deterministic_fix_possible(row, gap_type, cause, sql_shape)
    true_bug = deterministic_possible and cause not in {"generated_label_noise", "live_api_required", "no_action"}
    return {
        "prompt_id": row.get("prompt_id"),
        "prompt": row.get("prompt"),
        "gap_type": gap_type,
        "generated_label_advisory_only": True,
        "label_behavior_comparison": comparison,
        "expected_label": {
            "route": row.get("expected_route_label"),
            "domain_family": row.get("domain_family"),
            "answer_intent": row.get("answer_intent"),
        },
        "actual_behavior": {
            "route": row.get("actual_route"),
            "domain": row.get("domain_type"),
            "answer_intent": row.get("actual_answer_intent"),
            "sql_calls": row.get("sql_calls"),
            "api_calls": row.get("api_calls"),
            "dry_run_count": row.get("dry_run_count"),
            "sql_template": row.get("sql_template"),
            "evidence_state": row.get("evidence_state"),
            "requires_live_api": row.get("requires_live_api"),
            "zero_row_sql": row.get("zero_row_sql"),
            "sql_result_shape": sql_shape,
        },
        "final_answer_excerpt": excerpt(row.get("final_answer")),
        "likely_cause": cause,
        "suggested_action": SUGGESTED_ACTIONS.get(cause, "no_code_change"),
        "deterministic_fix_possible_without_live_api": deterministic_possible,
        "true_bug": true_bug,
        "confidence": confidence(row, gap_type, cause, deterministic_possible),
    }


def label_behavior_comparison(row: dict[str, Any], sql_shape: dict[str, Any]) -> dict[str, Any]:
    expected_route = str(row.get("expected_route_label") or "UNKNOWN")
    actual_route = str(row.get("actual_route") or "UNKNOWN")
    api_calls = int(row.get("api_calls") or 0)
    dry_run_count = int(row.get("dry_run_count") or 0)
    expected_api = "API" in expected_route
    actual_api_behavior = api_calls > 0 or dry_run_count > 0
    return {
        "route_label_matches": row.get("route_matches_diagnostic"),
        "domain_label_matches": row.get("domain_matches_diagnostic"),
        "answer_intent_label_matches": row.get("answer_intent_matches_diagnostic"),
        "expected_route": expected_route,
        "actual_route": actual_route,
        "expected_route_requires_api": expected_api,
        "actual_behavior_used_api_branch": actual_api_behavior,
        "actual_behavior_used_sql_branch": int(row.get("sql_calls") or 0) > 0,
        "generated_route_label_supported_by_behavior": (expected_api == actual_api_behavior)
        or (expected_route in {"SQL_PLUS_API", "SQL_FIRST_API_VERIFY"} and actual_api_behavior),
        "generated_domain_label_supported_by_behavior": row.get("domain_matches_diagnostic") is not False,
        "generated_answer_intent_supported_by_behavior": row.get("answer_intent_matches_diagnostic") is not False,
        "sql_row_count": sql_shape.get("row_count"),
        "sql_returned_zero_rows": sql_shape.get("row_count") == 0,
    }


def likely_cause(row: dict[str, Any], gap_type: str, comparison: dict[str, Any], sql_shape: dict[str, Any]) -> str:
    requires_live = bool(row.get("requires_live_api")) or str(row.get("evidence_state")) == "dry_run_unavailable"
    if requires_live and gap_type in {"route_mismatch", "missing_count_or_name_advisory", "zero_row_sql"}:
        return "live_api_required"
    if gap_type == "answer_intent_mismatch":
        expected = str(row.get("answer_intent") or "").upper()
        actual = str(row.get("actual_answer_intent") or "").upper()
        prompt = str(row.get("prompt") or "").lower()
        if {expected, actual} <= {"DATE", "WHEN", "STATUS"}:
            return "generated_label_noise"
        if expected == "BOOLEAN" and any(token in prompt for token in ("list", "show", "which", "what")):
            return "generated_label_noise"
        if requires_live:
            return "live_api_required"
        return "answer_intent_gap"
    if gap_type == "domain_mismatch":
        if requires_live:
            return "live_api_required"
        return "synonym_gap"
    if gap_type == "zero_row_sql":
        if sql_shape.get("row_count") == 0:
            return "schema_mapping_gap"
    if gap_type == "missing_count_or_name_advisory":
        answer = str(row.get("final_answer") or "")
        if any(ch.isdigit() for ch in answer) and requires_live:
            return "live_api_required"
        return "answer_template_gap"
    if gap_type == "route_mismatch":
        if comparison.get("generated_route_label_supported_by_behavior"):
            return "generated_label_noise"
        return "synonym_gap"
    return "no_action"


def deterministic_fix_possible(row: dict[str, Any], gap_type: str, cause: str, sql_shape: dict[str, Any]) -> bool:
    if cause in {"generated_label_noise", "live_api_required", "no_action"}:
        return False
    if cause in {"SQL_template_gap", "schema_mapping_gap"}:
        # Schema/SQL changes need deeper evidence than the generated prompt review alone.
        return False
    if gap_type == "missing_count_or_name_advisory":
        return bool(sql_shape.get("has_rows"))
    return cause in {"synonym_gap", "answer_intent_gap", "answer_template_gap"}


def is_category_candidate(selected: list[dict[str, Any]], examples: list[dict[str, Any]]) -> bool:
    true_bugs = [example for example in examples if example.get("true_bug")]
    live_api_required = [example for example in examples if example.get("likely_cause") == "live_api_required"]
    label_noise = [example for example in examples if example.get("likely_cause") == "generated_label_noise"]
    if len(selected) < 3 or len(true_bugs) < 3:
        return False
    if len(true_bugs) <= len(live_api_required) or len(true_bugs) <= len(label_noise):
        return False
    causes = Counter(str(example.get("likely_cause")) for example in true_bugs)
    if len(causes) != 1:
        return False
    if causes.most_common(1)[0][0] in {"generated_label_noise", "live_api_required", "schema_mapping_gap", "SQL_template_gap"}:
        return False
    return all(example.get("deterministic_fix_possible_without_live_api") is True for example in true_bugs)


def proposed_minimal_fix(gap_type: str, examples: list[dict[str, Any]], implementation_candidate: bool) -> str:
    if not examples:
        return "No examples available."
    if not implementation_candidate:
        dominant = Counter(str(example.get("likely_cause") or "no_action") for example in examples).most_common(1)[0][0]
        if dominant == "live_api_required":
            return "No runtime change; wait for live API access or review after live_success."
        if dominant == "generated_label_noise":
            return "No runtime change; generated label appears noisy for reviewed examples."
        if dominant in {"schema_mapping_gap", "SQL_template_gap"}:
            return "No runtime change; schema/SQL evidence review is required before edits."
        return "No runtime change in this pass."
    if gap_type == "answer_intent_mismatch":
        return "Add one focused deterministic answer-intent rule for the reviewed general pattern."
    if gap_type in {"route_mismatch", "domain_mismatch"}:
        return "Add one focused deterministic synonym/token rule for the reviewed general pattern."
    if gap_type == "missing_count_or_name_advisory":
        return "Tighten deterministic answer wording to surface already-available counts/names."
    return "Tighten zero-row wording without fabricating unavailable evidence."


def required_tests(gap_type: str, examples: list[dict[str, Any]], implementation_candidate: bool) -> list[str]:
    if not implementation_candidate:
        return ["No runtime test required unless a later pass applies a code change."]
    if gap_type == "answer_intent_mismatch":
        return ["answer intent classifier maps the reviewed paraphrase family", "hidden-style remains 48/48"]
    if gap_type in {"route_mismatch", "domain_mismatch"}:
        return ["deterministic router handles representative synonym", "strict eval does not regress"]
    if gap_type == "missing_count_or_name_advisory":
        return ["answer includes available count/name evidence", "answer does not fabricate API-only values"]
    return ["zero-row answer says no matching local records", "API unavailable remains distinct from zero-row SQL"]


def build_fix_decision(review: dict[str, Any]) -> dict[str, Any]:
    categories = review.get("reviewed_categories") or []
    candidates = []
    for category in categories:
        if category.get("implementation_candidate"):
            candidates.append(
                {
                    "category": category.get("category"),
                    "gap_type": category.get("gap_type"),
                    "evidence_count": category.get("total_count"),
                    "reviewed_true_bug_count": category.get("true_bug_count"),
                    "proposed_fix": category.get("proposed_minimal_fix"),
                    "risk_level": category.get("risk_level"),
                    "required_tests": category.get("required_tests"),
                    "implementation_ready": True,
                }
            )
    ranked = sorted(candidates, key=lambda item: (-int(item.get("reviewed_true_bug_count") or 0), str(item.get("category"))))
    if len(ranked) == 0:
        decision = "no_runtime_change"
        reason = "No reviewed category passed the strict evidence gate."
    elif len(ranked) == 1:
        decision = "one_candidate_ready_requires_separate_implementation"
        reason = "Exactly one candidate passed review, but this script only records the decision; implementation requires a separate edit/validation step."
    else:
        decision = "multiple_candidates_require_explicit_approval"
        reason = "Multiple candidates passed; no fix is applied in this pass without separate explicit approval."
    return {
        "report_type": DECISION_STEM,
        "created_at": now(),
        "diagnostic_only": True,
        "official_score_claim": False,
        "promotion_allowed": False,
        "runtime_change_applied": False,
        "implementation_ready_count": len(ranked),
        "at_most_one_fix_allowed": True,
        "decision": decision,
        "reason": reason,
        "no_safe_fix_after_manual_review": len(ranked) == 0,
        "ranked_shortlist": ranked,
        "implementation_gate": {
            "minimum_repeated_gap_count": 3,
            "generated_labels_not_ground_truth": True,
            "reject_mostly_generated_label_noise": True,
            "reject_mostly_live_api_required": True,
            "must_not_require_live_api_success": True,
            "requires_general_deterministic_rule": True,
            "requires_schema_or_evidence_support": True,
            "requires_focused_tests": True,
            "requires_low_regression_risk": True,
            "preserves_final_submission_format": True,
            "preserves_validators": True,
            "no_llm_controller_or_semantic_router_promotion": True,
        },
        "mandatory_validation_if_runtime_change_applied": [
            "python3 scripts/run_dev_eval.py --strict",
            "python3 scripts/run_hidden_style_eval.py",
            "python3 scripts/check_submission_ready.py",
            "python3 -m pytest -q",
        ],
        "source_report": "outputs/reports/local_gap_manual_review.json",
    }


def load_trajectory(config: Config, row: dict[str, Any]) -> dict[str, Any]:
    output_dir = row.get("output_dir")
    if not output_dir:
        return {}
    path = config.project_root / str(output_dir) / "trajectory.json"
    return load_json(path)


def sql_result_shape(row: dict[str, Any], trajectory: dict[str, Any]) -> dict[str, Any]:
    sql_steps = [step for step in trajectory.get("steps", []) if isinstance(step, dict) and step.get("kind") == "sql_call"]
    if not sql_steps:
        return {"available": False, "row_count": None, "has_rows": False, "sql": row.get("sql_template")}
    step = sql_steps[-1]
    result = step.get("result") if isinstance(step.get("result"), dict) else {}
    row_count = result.get("row_count")
    return {
        "available": True,
        "row_count": row_count,
        "has_rows": bool(row_count and int(row_count) > 0),
        "ok": result.get("ok"),
        "limited": result.get("limited"),
        "sql_excerpt": excerpt(step.get("sql"), 200),
    }


def confidence(row: dict[str, Any], gap_type: str, cause: str, deterministic_possible: bool) -> str:
    if cause in {"live_api_required", "generated_label_noise"}:
        return "high"
    if deterministic_possible:
        return "medium"
    if gap_type in {"domain_mismatch", "route_mismatch"}:
        return "low"
    return "medium"


def recommended_next_human_review(categories: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(categories, key=lambda item: (-int(item.get("total_count") or 0), str(item.get("category"))))
    target = ordered[0] if ordered else {}
    return {
        "category": target.get("category", "unavailable"),
        "why": "Largest reviewed high-value category; inspect examples before any runtime change.",
        "report_to_open": "outputs/reports/local_gap_manual_review.md",
        "can_be_fixed_before_adobe_access": bool(target.get("implementation_candidate")),
    }


def render_review_md(report: dict[str, Any]) -> str:
    lines = [
        "# Local Gap Manual Review",
        "",
        "Diagnostic-only manual review. Generated labels are advisory and are not treated as ground truth.",
        "",
        f"- Source prompts: `{report.get('source_executed_prompts')}` / `{report.get('source_total_prompts')}`",
        f"- Official score claim: `{report.get('official_score_claim')}`",
        f"- Promotion allowed: `{report.get('promotion_allowed')}`",
        "",
    ]
    for category in report.get("reviewed_categories", []):
        lines.extend(
            [
                f"## {category.get('category')}",
                "",
                f"- Total count: `{category.get('total_count')}`",
                f"- Reviewed count: `{category.get('reviewed_count')}`",
                f"- True bug count: `{category.get('true_bug_count')}`",
                f"- Generated-label noise count: `{category.get('generated_label_noise_count')}`",
                f"- Live API required count: `{category.get('live_api_required_count')}`",
                f"- Implementation candidate: `{category.get('implementation_candidate')}`",
                f"- Proposed minimal fix: {category.get('proposed_minimal_fix')}",
                "",
            ]
        )
        for example in (category.get("examples") or [])[:5]:
            lines.append(
                f"- `{example.get('prompt_id')}` cause=`{example.get('likely_cause')}` "
                f"true_bug=`{example.get('true_bug')}` action=`{example.get('suggested_action')}` "
                f"prompt={excerpt(example.get('prompt'), 100)!r}"
            )
        lines.append("")
    next_review = report.get("recommended_next_human_review") or {}
    lines.extend(
        [
            "## Recommended Next Human Review",
            "",
            f"- Category: `{next_review.get('category')}`",
            f"- Why: {next_review.get('why')}",
            f"- Can be fixed before Adobe access: `{next_review.get('can_be_fixed_before_adobe_access')}`",
            "",
        ]
    )
    return "\n".join(lines)


def render_decision_md(report: dict[str, Any]) -> str:
    lines = [
        "# Superpowers Fix Decision",
        "",
        "Diagnostic-only decision report. No runtime change is applied by this report.",
        "",
        f"- Decision: `{report.get('decision')}`",
        f"- Reason: {report.get('reason')}",
        f"- Implementation-ready count: `{report.get('implementation_ready_count')}`",
        f"- Runtime change applied: `{report.get('runtime_change_applied')}`",
        f"- No safe fix after manual review: `{report.get('no_safe_fix_after_manual_review')}`",
        "",
    ]
    shortlist = report.get("ranked_shortlist") or []
    if shortlist:
        lines.extend(["## Ranked Shortlist", ""])
        for item in shortlist:
            lines.append(
                f"- `{item.get('category')}` ready=`{item.get('implementation_ready')}` "
                f"true_bugs=`{item.get('reviewed_true_bug_count')}` fix={item.get('proposed_fix')}"
            )
    else:
        lines.append("No candidate passed the strict evidence gate, so no runtime change was applied.")
    lines.extend(["", "## Mandatory Validation If A Runtime Change Is Applied", ""])
    lines.extend(f"- `{command}`" for command in report.get("mandatory_validation_if_runtime_change_applied", []))
    lines.append("")
    return "\n".join(lines)


def excerpt(value: Any, max_chars: int = 240) -> str:
    return str(value or "")[:max_chars]


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
