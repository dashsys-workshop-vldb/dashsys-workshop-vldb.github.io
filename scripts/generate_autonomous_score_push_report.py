#!/usr/bin/env python
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.report_run import report_metadata
from scripts.check_submission_ready import check_submission_ready
from scripts.run_official_token_reduction_eval import _load_json


BASELINE_COMMIT = "b583624c1977d7bf7a4403ba3a77779f602d2f79"
BASELINE_STRICT_SCORE = 0.6491
BASELINE_CORRECTNESS = 0.6743
BASELINE_TOKENS = 831.4571
BASELINE_RUNTIME = 0.0115
BASELINE_TOOL_CALLS = 1.4571
TARGET_SCORE = 0.7500


WORKERS = [
    {
        "branch": "codex/score075-coordinator-baseline",
        "owner": "coordinator/baseline",
        "scope": "baseline snapshots, shared gates, research notes, workplan, status table",
        "dependencies": [],
        "reported_commit": None,
        "status": "reported_complete_not_merged",
        "tests_run": [
            "python3 -m py_compile scripts/generate_improvement_backlog.py scripts/autonomous_improvement_loop.py scripts/generate_autonomous_score_push_report.py",
            "python3 scripts/autonomous_improvement_loop.py --initialize-coordinator",
        ],
        "merge_recommendation": "pending_integration_validation",
    },
    {
        "branch": "codex/score075-dryrun-answer",
        "owner": "evidence-aware dry-run answers",
        "scope": "default-off evidence-aware dry-run answer candidate",
        "dependencies": ["codex/score075-local-index"],
        "reported_commit": "667e1515",
        "status": "reported_complete_not_merged",
        "tests_run": ["python3 -m pytest tests/test_answer_correctness_layer.py", "python3 -m pytest"],
        "merge_recommendation": "pending_dependency_validation",
    },
    {
        "branch": "codex/score075-local-index",
        "owner": "local Parquet knowledge index",
        "scope": "Parquet-derived evidence-object index and isolated eval",
        "dependencies": ["codex/score075-robustness-leakage"],
        "reported_commit": None,
        "status": "reported_complete_not_merged",
        "tests_run": [
            "python3 -m pytest tests/test_local_knowledge_index.py",
            "python3 -m pytest",
            "python3 scripts/build_local_knowledge_index.py",
            "python3 scripts/run_local_index_candidate_eval.py",
        ],
        "merge_recommendation": "pending_dependency_validation",
    },
    {
        "branch": "codex/score075-endpoint-routing",
        "owner": "endpoint/schema routing",
        "scope": "leakage-safe endpoint/schema rule candidates",
        "dependencies": ["codex/score075-robustness-leakage"],
        "reported_commit": None,
        "status": "reported_complete_not_merged",
        "tests_run": ["python3 -m pytest tests/test_endpoint_schema_rule_candidates.py tests/test_candidate_ranker.py::test_tag_and_schema_dataset_family_separation tests/test_gated_improvement_batch.py::test_endpoint_and_ast_reports_are_report_only"],
        "merge_recommendation": "pending_dependency_validation",
    },
    {
        "branch": "codex/score075-candidate-generation",
        "owner": "candidate generation",
        "scope": "deterministic candidate families and isolated candidate eval",
        "dependencies": [
            "codex/score075-local-index",
            "codex/score075-answer-shape",
            "codex/score075-endpoint-routing",
        ],
        "reported_commit": None,
        "status": "reported_complete_not_merged",
        "tests_run": ["python3 -m pytest tests/test_score075_candidate_generation.py tests/test_score_push_pipeline.py", "python3 scripts/run_score075_candidate_generation_eval.py"],
        "merge_recommendation": "pending_dependency_validation",
    },
    {
        "branch": "codex/score075-execution-selector",
        "owner": "execution-based selector",
        "scope": "selector hardening and execution search rejection reporting",
        "dependencies": ["codex/score075-candidate-generation", "codex/score075-robustness-leakage"],
        "reported_commit": None,
        "status": "reported_complete_not_merged",
        "tests_run": ["python3 -m pytest tests/test_execution_based_candidate_selector.py tests/test_score_push_pipeline.py -q", "python3 scripts/run_execution_candidate_search.py"],
        "merge_recommendation": "keep_shadow_only_until_dependencies_merged",
    },
    {
        "branch": "codex/score075-llm-search",
        "owner": "LLM-assisted candidate search",
        "scope": "optional LLM candidates with skipped report when no key exists",
        "dependencies": ["codex/score075-robustness-leakage"],
        "reported_commit": None,
        "status": "not_reported_to_integration",
        "tests_run": [],
        "merge_recommendation": "blocked_missing_worker_result",
    },
    {
        "branch": "codex/score075-answer-shape",
        "owner": "answer-shape optimization",
        "scope": "answer-shape normalization candidates",
        "dependencies": ["codex/score075-robustness-leakage"],
        "reported_commit": None,
        "status": "not_reported_to_integration",
        "tests_run": [],
        "merge_recommendation": "blocked_missing_worker_result",
    },
    {
        "branch": "codex/score075-robustness-leakage",
        "owner": "robustness/leakage tests",
        "scope": "leakage, hidden-style, evidence-boundary, and diversity tests",
        "dependencies": [],
        "reported_commit": None,
        "status": "not_reported_to_integration",
        "tests_run": [],
        "merge_recommendation": "blocked_missing_worker_result",
    },
    {
        "branch": "codex/score075-integration",
        "owner": "integration/validation",
        "scope": "packaged trial scaffolding, score-push report, integration diff report",
        "dependencies": ["all accepted worker branches"],
        "reported_commit": None,
        "status": "in_progress",
        "tests_run": [],
        "merge_recommendation": "not_applicable_current_branch",
    },
]


def main() -> int:
    config = Config.from_env(ROOT)
    score_payload = generate_autonomous_score_push_report(config)
    diff_payload = generate_integration_diff_report(config, score_payload)
    config.outputs_dir.mkdir(parents=True, exist_ok=True)

    score_json = config.outputs_dir / "autonomous_score_push_report.json"
    score_md = config.outputs_dir / "autonomous_score_push_report.md"
    diff_json = config.outputs_dir / "score075_integration_diff_report.json"
    diff_md = config.outputs_dir / "score075_integration_diff_report.md"
    blocker_json = config.outputs_dir / "score075_blocker_analysis.json"
    blocker_md = config.outputs_dir / "score075_blocker_analysis.md"
    score_json.write_text(json.dumps(score_payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    score_md.write_text(render_score_markdown(score_payload), encoding="utf-8")
    diff_json.write_text(json.dumps(diff_payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    diff_md.write_text(render_diff_markdown(diff_payload), encoding="utf-8")
    if not score_payload["summary"].get("target_0_75_reached"):
        blocker = generate_score075_blocker_analysis(config, score_payload)
        blocker_json.write_text(json.dumps(blocker, indent=2, sort_keys=True, default=str), encoding="utf-8")
        blocker_md.write_text(render_blocker_markdown(blocker), encoding="utf-8")
    print(
        json.dumps(
            {
                "json": str(score_json),
                "markdown": str(score_md),
                "integration_diff_json": str(diff_json),
                "integration_diff_markdown": str(diff_md),
                "recommendation": score_payload["summary"]["final_recommendation"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def generate_autonomous_score_push_report(config: Config) -> dict[str, Any]:
    strict = _load_json(config.outputs_dir / "eval_results_strict.json")
    hidden = _load_json(config.outputs_dir / "hidden_style_eval.json")
    backlog = _load_json(config.outputs_dir / "improvement_backlog.json")
    local_index = _load_json(config.outputs_dir / "local_index_candidate_eval.json")
    execution = _load_json(config.outputs_dir / "execution_candidate_search.json")
    evidence_answer = _load_json(config.outputs_dir / "evidence_answer_candidate_eval.json")
    score_components = _load_json(config.outputs_dir / "score_component_error_report.json")
    local_fact_coverage = _load_json(config.outputs_dir / "local_index_fact_coverage_report.json")
    llm = _load_json(config.outputs_dir / "llm_candidate_search.json")
    trial = _load_json(config.outputs_dir / "autonomous_packaged_trial.json")
    research = _load_json(config.outputs_dir / "autonomous_research_notes.json")
    readiness = check_submission_ready(config)
    baseline = _baseline(strict)
    trial_summary = trial.get("summary") or {}
    best_score = float(trial_summary.get("strict_final_score") or baseline["strict_final_score"])
    reached_075 = bool(trial_summary.get("target_0_75_reached")) and best_score >= TARGET_SCORE
    if reached_075:
        recommendation = "promote_safe_autonomous_improvements"
    elif best_score > baseline["strict_final_score"]:
        recommendation = "continue_iteration_target_not_reached"
    else:
        recommendation = "submit_current_official_token_reduction_version"
    if not readiness.get("ok"):
        recommendation = "do_not_submit_until_regression_fixed"
    return {
        **report_metadata(config.outputs_dir),
        "mode": "autonomous_score_push_report",
        "baseline_commit": BASELINE_COMMIT,
        "baseline": baseline,
        "target_score": TARGET_SCORE,
        "intermediate_targets": {"minimum_meaningful_progress": 0.7000, "stretch_target": 0.8000},
        "research_notes": research.get("summary", {}),
        "improvement_backlog": backlog.get("summary", {}),
        "local_index_candidate_eval": local_index.get("summary", {}),
        "local_index_fact_coverage_report": local_fact_coverage.get("summary", {}),
        "score_component_error_report": score_components.get("summary", {}),
        "evidence_answer_candidate_eval": evidence_answer.get("summary", {}),
        "execution_candidate_search": execution.get("summary", {}),
        "llm_candidate_search": llm.get("summary", {}),
        "autonomous_packaged_trial": trial_summary,
        "hidden_style_eval": hidden.get("summary", {}),
        "readiness": {"ok": readiness.get("ok"), "no_secret_scan_ok": readiness.get("secret_scan", {}).get("ok")},
        "summary": {
            "starting_score": baseline["strict_final_score"],
            "best_achieved_score": round(best_score, 4),
            "score_delta": round(best_score - baseline["strict_final_score"], 4),
            "target_0_70_reached": best_score >= 0.7000,
            "target_0_75_reached": reached_075,
            "target_0_80_reached": best_score >= 0.8000 and reached_075,
            "hard_target_success": reached_075,
            "final_recommendation": recommendation,
        },
        "blockers": _blockers(best_score, reached_075, execution, trial),
        "notes": [
            "This report cannot mark success below strict_final_score >= 0.7500.",
            "No worker branch is promoted by this report.",
            "If 0.75 is not reached, preserve the current submit-ready official-token-reduction version.",
        ],
    }


def generate_score075_blocker_analysis(config: Config, score_payload: dict[str, Any]) -> dict[str, Any]:
    strict = _load_json(config.outputs_dir / "eval_results_strict.json")
    score_components = _load_json(config.outputs_dir / "score_component_error_report.json")
    evidence_answer = _load_json(config.outputs_dir / "evidence_answer_candidate_eval.json")
    local_fact = _load_json(config.outputs_dir / "local_index_fact_coverage_report.json")
    execution = _load_json(config.outputs_dir / "execution_candidate_search.json")
    llm = _load_json(config.outputs_dir / "llm_candidate_search.json")
    trial = _load_json(config.outputs_dir / "autonomous_packaged_trial.json")
    baseline = score_payload.get("baseline", {})
    best = score_payload.get("summary", {}).get("best_achieved_score", baseline.get("strict_final_score", 0.6491))
    low_rows = [
        {
            "query_id": row.get("query_id"),
            "query": row.get("query"),
            "final_score": row.get("final_score"),
            "answer_score": row.get("answer_score"),
            "sql_score": row.get("sql_score"),
            "api_score": row.get("api_score"),
        }
        for row in strict.get("rows", [])
        if row.get("strategy") == "SQL_FIRST_API_VERIFY" and float(row.get("final_score") or 0.0) < 0.75
    ]
    return {
        **report_metadata(config.outputs_dir),
        "mode": "score075_blocker_analysis",
        "best_achieved_score": best,
        "score_gap_remaining": round(max(0.0, TARGET_SCORE - float(best or 0.0)), 4),
        "low_score_rows": low_rows,
        "tried_strategies": {
            "score_component_error_report": score_components.get("summary", {}),
            "evidence_answer_candidate_eval": evidence_answer.get("summary", {}),
            "local_index_fact_coverage_report": local_fact.get("summary", {}),
            "execution_candidate_search": execution.get("summary", {}),
            "llm_candidate_search": llm.get("summary", {}),
            "autonomous_packaged_trial": trial.get("summary", {}),
        },
        "why_not_reached": score_payload.get("blockers", []),
        "current_version_should_remain_submit_ready": True,
        "recommendation": "submit_current_official_token_reduction_version",
    }


def generate_integration_diff_report(config: Config, score_payload: dict[str, Any]) -> dict[str, Any]:
    strict = _load_json(config.outputs_dir / "eval_results_strict.json")
    hidden = _load_json(config.outputs_dir / "hidden_style_eval.json")
    readiness = check_submission_ready(config)
    baseline = score_payload["baseline"]
    current = _baseline(strict)
    hidden_summary = hidden.get("summary") or {}
    branch_rows = []
    for worker in WORKERS:
        latest_commit = _branch_commit(worker["branch"]) or worker.get("reported_commit")
        branch_rows.append(
            {
                **worker,
                "latest_commit": latest_commit,
                "merged_or_rejected": "pending",
                "rejection_reason": "not_merged_by_integration_worker",
                "files_changed": [],
                "flags_added": [],
                "flags_enabled": [],
                "strict_score_delta": 0.0,
                "correctness_delta": 0.0,
                "hidden_style_delta": 0.0,
                "token_delta": 0.0,
                "runtime_delta": 0.0,
                "tool_call_delta": 0.0,
                "final_submission_diff": "not_run_for_unmerged_branch",
                "no_secret_result": readiness.get("secret_scan", {}).get("ok"),
            }
        )
    return {
        **report_metadata(config.outputs_dir),
        "mode": "score075_integration_diff_report",
        "baseline_commit": BASELINE_COMMIT,
        "current_branch": _current_branch(),
        "merged_branches": [],
        "rejected_branches": [],
        "pending_branches": [row["branch"] for row in branch_rows],
        "branch_decisions": branch_rows,
        "files_changed": [],
        "flags_added": [],
        "flags_enabled": ["ENABLE_OFFICIAL_TOKEN_REDUCTION"],
        "metrics": {
            "strict_score_before": baseline["strict_final_score"],
            "strict_score_after": current["strict_final_score"],
            "strict_score_delta": round(current["strict_final_score"] - baseline["strict_final_score"], 4),
            "correctness_before": baseline["correctness"],
            "correctness_after": current["correctness"],
            "correctness_delta": round(current["correctness"] - baseline["correctness"], 4),
            "hidden_style_before": "48/48",
            "hidden_style_after": f"{hidden_summary.get('passed_cases')}/{hidden_summary.get('total_cases')}",
            "estimated_tokens_before": baseline["estimated_tokens"],
            "estimated_tokens_after": current["estimated_tokens"],
            "token_delta": round(current["estimated_tokens"] - baseline["estimated_tokens"], 4),
            "runtime_before": baseline["runtime"],
            "runtime_after": current["runtime"],
            "runtime_delta": round(current["runtime"] - baseline["runtime"], 4),
            "tool_calls_before": baseline["tool_calls"],
            "tool_calls_after": current["tool_calls"],
            "tool_call_delta": round(current["tool_calls"] - baseline["tool_calls"], 4),
        },
        "final_submission_diff": {
            "checked": False,
            "reason": "no worker branch merged by integration yet",
            "format_unchanged": readiness.get("ok"),
        },
        "no_secret_result": readiness.get("secret_scan", {}),
        "recommendation": "no_merge_performed_pending_worker_dependencies",
        "notes": [
            "This integration branch prepared diff-report scaffolding only.",
            "Every worker branch remains pending until pairwise merge validation is run.",
        ],
    }


def _baseline(strict: dict[str, Any]) -> dict[str, float]:
    sql_first = (strict.get("summary") or {}).get("by_strategy", {}).get("SQL_FIRST_API_VERIFY", {})
    return {
        "strict_final_score": float(sql_first.get("avg_final_score") or BASELINE_STRICT_SCORE),
        "correctness": float(sql_first.get("avg_correctness_score") or BASELINE_CORRECTNESS),
        "estimated_tokens": float(sql_first.get("avg_estimated_tokens") or BASELINE_TOKENS),
        "runtime": float(sql_first.get("avg_runtime") or BASELINE_RUNTIME),
        "tool_calls": float(sql_first.get("avg_tool_call_count") or BASELINE_TOOL_CALLS),
    }


def _blockers(best_score: float, reached_075: bool, execution: dict[str, Any], trial: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if not reached_075:
        blockers.append("strict_final_score_0_75_not_reached")
    if best_score <= BASELINE_STRICT_SCORE:
        blockers.append("no_safe_score_improvement_over_baseline")
    if not (execution.get("summary") or {}).get("safe_rows"):
        blockers.append("execution_candidate_search_found_no_safe_rows")
    if (trial.get("summary") or {}).get("recommendation") in {None, "submit_current_official_token_reduction_version"}:
        blockers.append("autonomous_packaged_trial_has_no_promotable_bundle")
    return blockers


def _current_branch() -> str | None:
    return _git(["branch", "--show-current"])


def _branch_commit(branch: str) -> str | None:
    return _git(["rev-parse", "--short", branch])


def _git(args: list[str]) -> str | None:
    try:
        result = subprocess.run(["git", *args], cwd=ROOT, check=True, text=True, capture_output=True)
    except Exception:
        return None
    value = result.stdout.strip()
    return value or None


def render_score_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Autonomous 0.75 Score-Push Report",
        "",
        f"- Baseline commit: `{payload['baseline_commit']}`",
        f"- Starting strict score: {summary['starting_score']}",
        f"- Best achieved strict score: {summary['best_achieved_score']}",
        f"- Score delta: {summary['score_delta']}",
        f"- 0.70 reached: {summary['target_0_70_reached']}",
        f"- 0.75 reached: {summary['target_0_75_reached']}",
        f"- 0.80 reached: {summary['target_0_80_reached']}",
        f"- Hard target success: {summary['hard_target_success']}",
        f"- Final recommendation: `{summary['final_recommendation']}`",
        "",
    ]
    if payload["blockers"]:
        lines.append("## Blockers")
        lines.append("")
        lines.extend(f"- {item}" for item in payload["blockers"])
    return "\n".join(lines) + "\n"


def render_diff_markdown(payload: dict[str, Any]) -> str:
    metrics = payload["metrics"]
    lines = [
        "# score075 Integration Diff Report",
        "",
        f"- Baseline commit: `{payload['baseline_commit']}`",
        f"- Current branch: `{payload['current_branch']}`",
        f"- Merged branches: {len(payload['merged_branches'])}",
        f"- Rejected branches: {len(payload['rejected_branches'])}",
        f"- Pending branches: {len(payload['pending_branches'])}",
        f"- Strict score before/after/delta: {metrics['strict_score_before']} / {metrics['strict_score_after']} / {metrics['strict_score_delta']}",
        f"- Hidden-style before/after: {metrics['hidden_style_before']} / {metrics['hidden_style_after']}",
        f"- Token/runtime/tool deltas: {metrics['token_delta']} / {metrics['runtime_delta']} / {metrics['tool_call_delta']}",
        f"- Final submission format unchanged: {payload['final_submission_diff'].get('format_unchanged')}",
        f"- No-secret result: {payload['no_secret_result'].get('ok')}",
        f"- Recommendation: `{payload['recommendation']}`",
        "",
        "## Branch Decisions",
        "",
        "| Branch | Status | Dependencies | Merge recommendation | Score delta | Hidden delta |",
        "|---|---:|---|---|---:|---:|",
    ]
    for row in payload["branch_decisions"]:
        deps = ", ".join(row.get("dependencies") or [])
        lines.append(
            f"| `{row['branch']}` | {row['status']} | {deps or '-'} | {row['merge_recommendation']} | "
            f"{row['strict_score_delta']} | {row['hidden_style_delta']} |"
        )
    return "\n".join(lines) + "\n"


def render_blocker_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Score 0.75 Blocker Analysis",
        "",
        f"- Best achieved score: {payload.get('best_achieved_score')}",
        f"- Score gap remaining: {payload.get('score_gap_remaining')}",
        f"- Recommendation: `{payload.get('recommendation')}`",
        f"- Current version should remain submit-ready: {payload.get('current_version_should_remain_submit_ready')}",
        "",
        "## Why 0.75 Was Not Reached",
        "",
    ]
    blockers = payload.get("why_not_reached") or []
    lines.extend(f"- {item}" for item in blockers) if blockers else lines.append("- No blocker details were available.")
    lines.extend(["", "## Tried Strategies", ""])
    for name, summary in (payload.get("tried_strategies") or {}).items():
        if summary:
            lines.append(f"- `{name}`: {summary}")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
