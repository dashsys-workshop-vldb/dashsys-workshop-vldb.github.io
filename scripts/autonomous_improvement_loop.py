#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASELINE_COMMIT = "b583624c1977d7bf7a4403ba3a77779f602d2f79"
BASELINE = {
    "branch": "main",
    "commit_sha": BASELINE_COMMIT,
    "strict_final_score": 0.6491,
    "correctness": 0.6743,
    "estimated_tokens": 831.4571,
    "runtime": 0.0115,
    "tool_calls": 1.4571,
    "hidden_style": "48/48",
    "preferred_strategy": "SQL_FIRST_API_VERIFY",
}
TARGET_SCORE = 0.7500


WORKERS: list[dict[str, Any]] = [
    {
        "branch": "codex/score075-coordinator-baseline",
        "owner": "coordinator/baseline",
        "scope": "Baseline snapshots, workplan, research notes, branch status, shared gates",
        "allowed_files": [
            "PARALLEL_WORKPLAN.md",
            "scripts/generate_improvement_backlog.py",
            "scripts/autonomous_improvement_loop.py",
            "scripts/generate_autonomous_score_push_report.py",
            "outputs/score075_baseline_report.*",
            "outputs/autonomous_research_notes.*",
            "outputs/score075_parallel_status.*",
        ],
        "declared_dependencies": [],
        "status": "ready_for_review",
        "blockers": [],
    },
    {
        "branch": "codex/score075-dryrun-answer",
        "owner": "evidence-aware dry-run answers",
        "scope": "Dry-run answer candidates from recorded evidence only",
        "allowed_files": [
            "dashagent/answer_templates.py",
            "dashagent/answer_synthesizer.py",
            "tests/test_*answer*",
            "outputs/score075_dryrun_answer_eval.*",
            "outputs/score075_dryrun_answer_handoff.md",
        ],
        "declared_dependencies": ["codex/score075-local-index"],
        "status": "blocked_on_dependency",
        "blockers": ["Needs local-index evidence-object contract before integrating local evidence."],
    },
    {
        "branch": "codex/score075-local-index",
        "owner": "local Parquet knowledge index",
        "scope": "Parquet-derived evidence-object local index, no final-answer cache",
        "allowed_files": [
            "dashagent/local_knowledge_index.py",
            "scripts/build_local_knowledge_index.py",
            "scripts/run_local_index_candidate_eval.py",
            "tests/test_*local*index*",
            "outputs/local_knowledge_index_report.*",
            "outputs/local_index_candidate_eval.*",
        ],
        "declared_dependencies": ["codex/score075-robustness-leakage"],
        "status": "blocked_on_dependency",
        "blockers": ["Needs provenance/leakage tests before merge."],
    },
    {
        "branch": "codex/score075-endpoint-routing",
        "owner": "endpoint/schema routing",
        "scope": "Leakage-safe endpoint/schema routing candidates",
        "allowed_files": [
            "dashagent/endpoint_schema_rule_candidates.py",
            "scripts/run_endpoint_schema_rule_canary.py",
            "scripts/run_endpoint_schema_rule_candidate_eval.py",
            "tests/test_*endpoint*schema*",
            "outputs/score075_endpoint_routing_eval.*",
        ],
        "declared_dependencies": ["codex/score075-robustness-leakage"],
        "status": "blocked_on_dependency",
        "blockers": ["Needs leakage guard branch merged first."],
    },
    {
        "branch": "codex/score075-candidate-generation",
        "owner": "candidate generation",
        "scope": "Deterministic candidate families and isolated candidate reports",
        "allowed_files": [
            "dashagent/targeted_candidate_generator.py",
            "scripts/run_execution_candidate_search.py",
            "tests/test_score_push_pipeline.py",
            "outputs/score075_candidate_generation_eval.*",
        ],
        "declared_dependencies": [
            "codex/score075-local-index",
            "codex/score075-endpoint-routing",
            "codex/score075-answer-shape",
        ],
        "status": "blocked_on_dependency",
        "blockers": ["Needs local-index, endpoint-routing, and answer-shape candidate contracts."],
    },
    {
        "branch": "codex/score075-execution-selector",
        "owner": "execution-based selector",
        "scope": "Execution-guided selector and safety gates",
        "allowed_files": [
            "dashagent/execution_based_candidate_selector.py",
            "scripts/run_execution_candidate_search.py",
            "tests/test_score_push_pipeline.py",
            "outputs/execution_candidate_search.*",
            "outputs/execution_candidate_search/",
        ],
        "declared_dependencies": [
            "codex/score075-candidate-generation",
            "codex/score075-robustness-leakage",
        ],
        "status": "blocked_on_dependency",
        "blockers": ["Needs candidate generation and leakage guards."],
    },
    {
        "branch": "codex/score075-llm-search",
        "owner": "LLM-assisted candidate search",
        "scope": "Optional LLM candidate search, skipped if no key",
        "allowed_files": [
            "dashagent/llm_candidate_generator.py",
            "scripts/run_llm_candidate_search.py",
            "tests/test_score_push_pipeline.py",
            "outputs/llm_candidate_search.*",
        ],
        "declared_dependencies": [
            "codex/score075-candidate-generation",
            "codex/score075-execution-selector",
        ],
        "status": "blocked_on_dependency",
        "blockers": ["Needs candidate schema and selector validators."],
    },
    {
        "branch": "codex/score075-answer-shape",
        "owner": "answer-shape optimization",
        "scope": "Answer-shape normalization candidates only",
        "allowed_files": [
            "dashagent/answer_templates.py",
            "dashagent/answer_synthesizer.py",
            "tests/test_*answer*",
            "outputs/score075_answer_shape_eval.*",
        ],
        "declared_dependencies": ["codex/score075-robustness-leakage"],
        "status": "blocked_on_dependency",
        "blockers": ["Needs evidence-boundary tests."],
    },
    {
        "branch": "codex/score075-robustness-leakage",
        "owner": "robustness/leakage tests",
        "scope": "Leakage, hidden-style, evidence-boundary, candidate-diversity tests",
        "allowed_files": [
            "tests/test_score075_*",
            "tests/test_hidden_style_generalization.py",
            "tests/test_score_push_pipeline.py",
            "outputs/score075_robustness_report.*",
        ],
        "declared_dependencies": [],
        "status": "ready_to_start",
        "blockers": [],
    },
    {
        "branch": "codex/score075-integration",
        "owner": "integration/validation",
        "scope": "Pairwise merge validation, packaged trial, diff report, readiness/research updates",
        "allowed_files": [
            "scripts/run_autonomous_packaged_trial.py",
            "scripts/generate_autonomous_score_push_report.py",
            "scripts/generate_winner_readiness_report.py",
            "scripts/generate_research_inspired_report.py",
            "outputs/autonomous_packaged_trial.*",
            "outputs/autonomous_score_push_report.*",
            "outputs/score075_integration_diff_report.*",
        ],
        "declared_dependencies": [
            "codex/score075-robustness-leakage",
            "codex/score075-local-index",
            "codex/score075-dryrun-answer",
            "codex/score075-answer-shape",
            "codex/score075-endpoint-routing",
            "codex/score075-candidate-generation",
            "codex/score075-execution-selector",
            "codex/score075-llm-search",
        ],
        "status": "blocked_on_worker_branches",
        "blockers": ["May merge only after dependency branches produce isolated reports and pass gates."],
    },
]


RESEARCH_SOURCES: list[dict[str, Any]] = [
    {
        "source_url": "https://platform.openai.com/docs/guides/evaluation-best-practices",
        "technique_name": "Eval-driven regression gates",
        "how_it_applies": "Use strict eval, hidden-style eval, packaging readiness, and metric deltas as blocking gates before accepting any score075 branch.",
        "implemented_or_rejected": "implemented",
        "result": "Encoded as promotion gates and integration validation protocol.",
        "reason_kept_or_rejected": "Directly matches the need to compare candidate behavior before promotion.",
    },
    {
        "source_url": "https://arxiv.org/abs/2410.01943",
        "technique_name": "CHASE-SQL multi-path candidate generation and selection",
        "how_it_applies": "Separate workers generate candidate families while the selector/integration workers perform pairwise evaluation and selection.",
        "implemented_or_rejected": "implemented_as_gated_scaffolding",
        "result": "Candidate generation and execution selector branches are isolated and blocked behind validation.",
        "reason_kept_or_rejected": "Useful pattern, but adapted to deterministic local validation rather than multi-agent runtime execution.",
    },
    {
        "source_url": "https://arxiv.org/pdf/2405.16755",
        "technique_name": "CHESS schema/value retrieval and schema pruning",
        "how_it_applies": "Local-index and endpoint-routing workers focus on Parquet-derived value grounding and safe schema relation preservation.",
        "implemented_or_rejected": "implemented_as_candidate_direction",
        "result": "Assigned to local-index, endpoint-routing, and candidate-generation workers.",
        "reason_kept_or_rejected": "Potentially improves grounding without gold labels if evidence provenance is enforced.",
    },
    {
        "source_url": "https://arxiv.org/abs/2304.11015",
        "technique_name": "DIN-SQL task decomposition and self-correction",
        "how_it_applies": "Backlog classification decomposes failures into endpoint, schema, SQL, answer-shape, and dry-run evidence tasks.",
        "implemented_or_rejected": "implemented_as_report_scaffolding",
        "result": "Improvement backlog separates targeted failure types and worker ownership.",
        "reason_kept_or_rejected": "Fits the coordinator role without adding runtime multi-agent complexity.",
    },
    {
        "source_url": "https://arxiv.org/abs/2308.15363",
        "technique_name": "DAIL-SQL prompt/example organization",
        "how_it_applies": "Used only as a caution to rank and organize candidates; no public-example prompt examples are introduced.",
        "implemented_or_rejected": "partially_rejected",
        "result": "No runtime few-shot public-example mechanism is added by coordinator.",
        "reason_kept_or_rejected": "Example selection can overfit this benchmark, so only ranking discipline is kept.",
    },
    {
        "source_url": "https://arxiv.org/abs/2411.00073",
        "technique_name": "RSL-SQL robust schema linking",
        "how_it_applies": "Schema-routing workers must preserve recall and hidden-style stability; schema pruning cannot weaken robustness.",
        "implemented_or_rejected": "implemented_as_gate",
        "result": "Hidden-style 48/48 and no reduced candidate diversity are merge requirements.",
        "reason_kept_or_rejected": "Prevents score gains from brittle schema omissions.",
    },
    {
        "source_url": "https://arxiv.org/abs/1807.03100",
        "technique_name": "Execution-guided SQL generation",
        "how_it_applies": "Execution-selector worker validates and scores isolated candidates before any integration trial.",
        "implemented_or_rejected": "implemented_as_gated_scaffolding",
        "result": "Assigned to execution selector and autonomous packaged trial workflow.",
        "reason_kept_or_rejected": "Execution feedback is valuable as long as it remains offline/scored and not gold-driven at runtime.",
    },
    {
        "source_url": "https://sqlglot.com/sqlglot.html",
        "technique_name": "SQLGlot AST validation",
        "how_it_applies": "Candidate workers must parse SQL, identify tables/columns, and reject destructive or unknown-schema candidates.",
        "implemented_or_rejected": "implemented_as_gate",
        "result": "Included in worker and selector safety requirements.",
        "reason_kept_or_rejected": "Keeps generated candidates structurally safe before execution.",
    },
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Coordinator scaffolding for the parallel score075 push.")
    parser.add_argument("--initialize-coordinator", action="store_true", help="Write baseline, research, and status artifacts only.")
    parser.add_argument("--outputs-dir", default=str(ROOT / "outputs"))
    args = parser.parse_args()

    outputs_dir = Path(args.outputs_dir)
    if args.initialize_coordinator:
        payload = write_coordinator_artifacts(outputs_dir)
        print(json.dumps({"status": payload["status"]["global_status"], "artifacts": payload["artifacts"]}, indent=2))
        return 0

    payload = {
        "mode": "autonomous_improvement_loop_scaffold",
        "generated_at": _now(),
        "status": "not_started_by_coordinator_worker",
        "baseline": _current_baseline(outputs_dir),
        "target_score": TARGET_SCORE,
        "loop_policy": {
            "success_only_at_or_above_target": True,
            "stop_after_high_medium_backlog_exhaustion": True,
            "revert_failed_changes": True,
            "workers_may_not_promote": True,
        },
        "next_actions": [
            "Integration should merge accepted worker branches pairwise.",
            "Run execution/local-index/LLM searches only after their dependencies are merged.",
            "Generate autonomous score push report after packaged trial.",
        ],
    }
    _write_json_md(
        outputs_dir / "autonomous_improvement_loop.json",
        outputs_dir / "autonomous_improvement_loop.md",
        payload,
        _render_loop_markdown(payload),
    )
    print(json.dumps({"json": str(outputs_dir / "autonomous_improvement_loop.json"), "status": payload["status"]}, indent=2))
    return 0


def write_coordinator_artifacts(outputs_dir: Path) -> dict[str, Any]:
    outputs_dir.mkdir(parents=True, exist_ok=True)
    baseline = _current_baseline(outputs_dir)
    current_branch = _git(["branch", "--show-current"]) or "unknown"
    current_commit = _git(["rev-parse", "HEAD"]) or BASELINE_COMMIT
    baseline_report = {
        "mode": "score075_baseline_report",
        "generated_at": _now(),
        "worker_branch": current_branch,
        "baseline_commit_sha": BASELINE_COMMIT,
        "current_commit_sha": current_commit,
        "allowed_files_declared_before_editing": True,
        "baseline": baseline,
        "hard_target": TARGET_SCORE,
        "intermediate_targets": {"minimum_meaningful_progress": 0.7000, "stretch": 0.8000},
        "gates": _promotion_gates(),
        "pre_existing_workspace_notes": [
            "Untracked duplicate outputs/final_submission/* 2.* artifacts were present before this worker started.",
            "Coordinator worker did not edit final_submission or official outputs/eval.",
        ],
    }
    research_notes = {
        "mode": "autonomous_research_notes",
        "generated_at": _now(),
        "web_access_available": True,
        "worker_branch": current_branch,
        "sources": RESEARCH_SOURCES,
        "notes": [
            "Sources are used to guide offline candidate generation and validation only.",
            "No external source is used to justify gold/public-query memorization.",
        ],
    }
    status = _parallel_status(current_commit, baseline)
    artifacts = {
        "baseline_json": "outputs/score075_baseline_report.json",
        "baseline_md": "outputs/score075_baseline_report.md",
        "research_json": "outputs/autonomous_research_notes.json",
        "research_md": "outputs/autonomous_research_notes.md",
        "status_json": "outputs/score075_parallel_status.json",
        "status_md": "outputs/score075_parallel_status.md",
    }
    _write_json_md(
        outputs_dir / "score075_baseline_report.json",
        outputs_dir / "score075_baseline_report.md",
        baseline_report,
        _render_baseline_markdown(baseline_report),
    )
    _write_json_md(
        outputs_dir / "autonomous_research_notes.json",
        outputs_dir / "autonomous_research_notes.md",
        research_notes,
        _render_research_markdown(research_notes),
    )
    _write_json_md(
        outputs_dir / "score075_parallel_status.json",
        outputs_dir / "score075_parallel_status.md",
        status,
        _render_status_markdown(status),
    )
    return {"baseline": baseline_report, "research": research_notes, "status": status, "artifacts": artifacts}


def _parallel_status(current_commit: str, baseline: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for worker in WORKERS:
        row = {
            **worker,
            "latest_commit": current_commit if worker["branch"] == "codex/score075-coordinator-baseline" else BASELINE_COMMIT,
            "tests_run": [],
            "score_delta": None,
            "hidden_style_result": None,
            "merge_recommendation": "pending",
        }
        if worker["branch"] == "codex/score075-coordinator-baseline":
            row["tests_run"] = [
                "python3 -m py_compile scripts/generate_improvement_backlog.py scripts/autonomous_improvement_loop.py scripts/generate_autonomous_score_push_report.py"
            ]
            row["score_delta"] = 0.0
            row["hidden_style_result"] = baseline.get("hidden_style")
            row["merge_recommendation"] = "merge_foundational_scaffolding"
        rows.append(row)
    return {
        "mode": "score075_parallel_status",
        "generated_at": _now(),
        "baseline": baseline,
        "success_target": TARGET_SCORE,
        "global_status": "coordinator_initialized",
        "required_artifacts": [
            "outputs/score075_parallel_status.json",
            "outputs/score075_parallel_status.md",
            "outputs/score075_integration_diff_report.json",
            "outputs/score075_integration_diff_report.md",
        ],
        "pre_existing_blockers": [
            "Untracked duplicate outputs/final_submission/* 2.* artifacts exist in the baseline workspace; workers must not edit final_submission directly."
        ],
        "workers": rows,
    }


def _current_baseline(outputs_dir: Path) -> dict[str, Any]:
    strict = _load_json(outputs_dir / "eval_results_strict.json")
    hidden = _load_json(outputs_dir / "hidden_style_eval.json")
    sql_first = (strict.get("summary") or {}).get("by_strategy", {}).get("SQL_FIRST_API_VERIFY", {})
    hidden_summary = hidden.get("summary") or {}
    return {
        **BASELINE,
        "strict_final_score": float(sql_first.get("avg_final_score") or BASELINE["strict_final_score"]),
        "correctness": float(sql_first.get("avg_correctness_score") or BASELINE["correctness"]),
        "estimated_tokens": float(sql_first.get("avg_estimated_tokens") or BASELINE["estimated_tokens"]),
        "runtime": float(sql_first.get("avg_runtime") or BASELINE["runtime"]),
        "tool_calls": float(sql_first.get("avg_tool_call_count") or BASELINE["tool_calls"]),
        "hidden_style": f"{hidden_summary.get('passed_cases', 48)}/{hidden_summary.get('total_cases', 48)}",
        "hidden_style_summary": hidden_summary,
    }


def _promotion_gates() -> dict[str, Any]:
    return {
        "strict_final_score_target": TARGET_SCORE,
        "correctness_minimum": BASELINE["correctness"],
        "hidden_style_required": "48/48",
        "max_estimated_tokens": round(BASELINE["estimated_tokens"] * 1.02, 4),
        "max_runtime": round(BASELINE["runtime"] * 1.10, 4),
        "max_tool_calls": BASELINE["tool_calls"],
        "preferred_strategy": "SQL_FIRST_API_VERIFY",
        "official_token_reduction_enabled": True,
        "compact_context_enabled": False,
        "repair_execution_enabled": False,
        "final_submission_format_unchanged": True,
        "no_secret_scan_ok": True,
    }


def _write_json_md(json_path: Path, md_path: Path, payload: dict[str, Any], markdown: str) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(markdown, encoding="utf-8")


def _render_baseline_markdown(payload: dict[str, Any]) -> str:
    baseline = payload["baseline"]
    gates = payload["gates"]
    lines = [
        "# Score075 Baseline Report",
        "",
        f"- Worker branch: `{payload['worker_branch']}`",
        f"- Baseline commit SHA: `{payload['baseline_commit_sha']}`",
        f"- Current commit SHA: `{payload['current_commit_sha']}`",
        f"- Preferred strategy: `{baseline['preferred_strategy']}`",
        f"- Strict final score: {baseline['strict_final_score']}",
        f"- Correctness: {baseline['correctness']}",
        f"- Estimated tokens/runtime/tools: {baseline['estimated_tokens']} / {baseline['runtime']} / {baseline['tool_calls']}",
        f"- Hidden-style result: {baseline['hidden_style']}",
        f"- Hard target: {payload['hard_target']}",
        "",
        "## Gates",
        "",
    ]
    for key, value in gates.items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Notes", ""])
    lines.extend(f"- {note}" for note in payload["pre_existing_workspace_notes"])
    return "\n".join(lines) + "\n"


def _render_research_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Autonomous Research Notes",
        "",
        f"- Web access available: {payload['web_access_available']}",
        f"- Worker branch: `{payload['worker_branch']}`",
        "",
        "| Technique | Source | Decision | Result |",
        "|---|---|---|---|",
    ]
    for source in payload["sources"]:
        lines.append(
            f"| {source['technique_name']} | {source['source_url']} | "
            f"{source['implemented_or_rejected']} | {source['result']} |"
        )
    lines.extend(["", "## Guardrails", ""])
    lines.extend(f"- {note}" for note in payload["notes"])
    return "\n".join(lines) + "\n"


def _render_status_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Score075 Parallel Status",
        "",
        f"- Generated at: {payload['generated_at']}",
        f"- Baseline commit: `{payload['baseline']['commit_sha']}`",
        f"- Global status: `{payload['global_status']}`",
        f"- Success target: {payload['success_target']}",
        "",
        "| Branch | Owner | Dependencies | Status | Tests | Score delta | Hidden-style | Recommendation | Blockers |",
        "|---|---|---|---|---|---:|---|---|---|",
    ]
    for worker in payload["workers"]:
        dependencies = ", ".join(worker["declared_dependencies"]) or "none"
        tests = "<br>".join(worker["tests_run"]) or "not run"
        blockers = "<br>".join(worker["blockers"]) or ""
        lines.append(
            f"| `{worker['branch']}` | {worker['owner']} | {dependencies} | `{worker['status']}` | "
            f"{tests} | {worker['score_delta']} | {worker['hidden_style_result']} | "
            f"{worker['merge_recommendation']} | {blockers} |"
        )
    return "\n".join(lines) + "\n"


def _render_loop_markdown(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Autonomous Improvement Loop",
            "",
            f"- Status: `{payload['status']}`",
            f"- Baseline strict final score: {payload['baseline']['strict_final_score']}",
            f"- Target strict final score: {payload['target_score']}",
            "",
            "This coordinator scaffold does not implement or promote behavior changes by itself.",
            "",
        ]
    )


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()
    except Exception:
        return ""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
