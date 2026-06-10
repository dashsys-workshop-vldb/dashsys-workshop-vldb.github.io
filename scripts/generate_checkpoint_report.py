#!/usr/bin/env python
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.checkpoints import REQUIRED_CHECKPOINT_IDS
from dashagent.config import Config


CHECKPOINT_TECHNIQUES = {
    "checkpoint_00_prompt_router": ("prompt routing policy", "chooses direct vs SQL/API evidence path", "skips tools for safe conceptual prompts"),
    "checkpoint_01_raw_query": ("raw user query capture", "preserves the original query", "starts a reproducible trace"),
    "checkpoint_02_query_normalization": ("data cleaning / query normalization", "improves matching robustness", "reduces reparsing"),
    "checkpoint_03_query_tokens": ("domain-aware tokenization/entity extraction", "extracts names/IDs/dates/metrics", "shares token structure"),
    "checkpoint_04_relevance_scoring": ("attention-style relevance scoring", "keeps useful schema/API context", "reduces metadata tokens"),
    "checkpoint_05_query_analysis": ("branch prediction / QueryAnalysis", "aligns route/domain/family/template decisions", "avoids repeated analysis"),
    "checkpoint_06_lookup_path": ("TLB-style lookup path prediction", "guides joins and API families", "filters irrelevant paths"),
    "checkpoint_07_context_card": ("huge-page-style compact context card", "packs required context", "reduces prompt size"),
    "checkpoint_08_candidate_plans": ("pre-execution plan ensemble", "chooses validated plan before execution", "executes only one candidate"),
    "checkpoint_09_plan_optimization": ("compiler-style plan optimization", "drops duplicates/placeholders", "enforces compact plan"),
    "checkpoint_10_evidence_policy": ("API_REQUIRED/API_OPTIONAL/API_SKIP policy", "keeps required API evidence", "skips unnecessary API calls"),
    "checkpoint_11_call_budget": ("tool-call budgeting", "bounds SQL/API plan", "controls calls/tokens/runtime"),
    "checkpoint_12_validation": ("SQL/API safety validation", "blocks unsafe calls", "avoids wasted invalid execution"),
    "checkpoint_13_tool_execution": ("SQL/API tool execution", "records SQL/API evidence", "makes tool cost explicit"),
    "checkpoint_14_evidence_bus": ("operand forwarding / EvidenceBus", "forwards exact evidence", "avoids repeated lookup"),
    "checkpoint_15_answer_slots": ("structured answer slot extraction", "builds factual answer fields", "keeps evidence compact"),
    "checkpoint_16_answer_verification": ("claim verification / groundedness checking", "blocks unsupported claims", "rewrites without extra calls"),
    "checkpoint_17_answer_reranking": ("deterministic answer reranking", "selects safest candidate", "uses same evidence only"),
    "checkpoint_18_final_answer": ("concise grounded final response", "returns evidence-grounded answer", "keeps final response short"),
}


def main() -> int:
    config = Config.from_env(ROOT)
    report = generate_checkpoint_report(config)
    json_path = config.outputs_dir / "checkpoint_report.json"
    md_path = config.outputs_dir / "checkpoint_report.md"
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "trajectories": report["trajectory_count"]}, indent=2, sort_keys=True))
    return 0


def generate_checkpoint_report(config: Config) -> dict[str, Any]:
    trajectories = load_trajectories(config.outputs_dir)
    coverage: dict[str, dict[str, Any]] = {}
    durations: dict[str, list[float]] = defaultdict(list)
    missing_by_query: list[dict[str, Any]] = []
    for trajectory in trajectories:
        checkpoints = trajectory.get("checkpoints", []) or []
        ids = {checkpoint.get("checkpoint_id") for checkpoint in checkpoints}
        missing = [checkpoint_id for checkpoint_id in REQUIRED_CHECKPOINT_IDS if checkpoint_id not in ids]
        if missing:
            missing_by_query.append({"query_id": trajectory.get("query_id"), "missing": missing})
        for checkpoint in checkpoints:
            checkpoint_id = checkpoint.get("checkpoint_id")
            if checkpoint_id:
                durations[checkpoint_id].append(float(checkpoint.get("duration_ms", 0.0) or 0.0))

    for checkpoint_id in REQUIRED_CHECKPOINT_IDS:
        technique, correctness_role, efficiency_role = CHECKPOINT_TECHNIQUES[checkpoint_id]
        coverage[checkpoint_id] = {
            "technique": technique,
            "correctness_role": correctness_role,
            "efficiency_role": efficiency_role,
            "present_in": sum(
                1 for trajectory in trajectories if checkpoint_id in {cp.get("checkpoint_id") for cp in trajectory.get("checkpoints", []) or []}
            ),
            "avg_duration_ms": round(mean(durations[checkpoint_id]), 3) if durations[checkpoint_id] else 0.0,
        }

    return {
        "trajectory_count": len(trajectories),
        "required_checkpoints": REQUIRED_CHECKPOINT_IDS,
        "coverage": coverage,
        "missing_by_query": missing_by_query[:25],
        "representative_queries": representative_queries(trajectories),
    }


def load_trajectories(outputs_dir: Path) -> list[dict[str, Any]]:
    trajectories = []
    for path in outputs_dir.rglob("trajectory.json"):
        if any(
            part in {"final_submission", "source_code", "robustness_runs", "threshold_runs"} or part.startswith("probe")
            for part in path.parts
        ):
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(payload, dict):
            trajectories.append(payload)
    return sorted(trajectories, key=lambda item: (str(item.get("query_id", "")), str(item.get("strategy", ""))))


def representative_queries(trajectories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets = {
        "simple_local_sql_query": lambda t: t.get("sql_call_count", 0) > 0 and t.get("api_call_count", 0) == 0,
        "sql_plus_api_verification_query": lambda t: t.get("sql_call_count", 0) > 0 and t.get("api_call_count", 0) > 0,
        "api_only_or_dry_run_query": lambda t: t.get("api_call_count", 0) > 0 and t.get("sql_call_count", 0) == 0,
    }
    examples = []
    for label, predicate in buckets.items():
        match = next((trajectory for trajectory in trajectories if predicate(trajectory)), None)
        if not match:
            continue
        checkpoints = match.get("checkpoints", []) or []
        examples.append(
            {
                "kind": label,
                "query_id": match.get("query_id"),
                "query": match.get("original_query"),
                "strategy": match.get("strategy"),
                "checkpoint_ids": [checkpoint.get("checkpoint_id") for checkpoint in checkpoints[:6]],
                "tool_call_count": match.get("tool_call_count"),
                "final_answer_preview": str(match.get("final_answer", ""))[:240],
            }
        )
    return examples


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Checkpoint Report",
        "",
        f"Trajectory files inspected: {report['trajectory_count']}",
        "",
        "## Required Checkpoints",
        "",
        "| Checkpoint | Technique | Correctness role | Efficiency role | Present in | Avg duration ms |",
        "| --- | --- | --- | --- | ---: | ---: |",
    ]
    for checkpoint_id, row in report["coverage"].items():
        lines.append(
            f"| `{checkpoint_id}` | {row['technique']} | {row['correctness_role']} | {row['efficiency_role']} | {row['present_in']} | {row['avg_duration_ms']} |"
        )
    lines.extend(["", "## Representative Data Flow Examples", ""])
    if not report["representative_queries"]:
        lines.append("No trajectory examples were available yet.")
    for example in report["representative_queries"]:
        lines.extend(
            [
                f"### {example['kind']}",
                "",
                f"- Query ID: `{example.get('query_id')}`",
                f"- Query: {example.get('query')}",
                f"- Tool calls: {example.get('tool_call_count')}",
                f"- First checkpoints: {', '.join(example.get('checkpoint_ids') or [])}",
                f"- Final answer preview: {example.get('final_answer_preview')}",
                "",
            ]
        )
    if report["missing_by_query"]:
        lines.extend(["## Missing Checkpoints", ""])
        for item in report["missing_by_query"][:10]:
            lines.append(f"- `{item.get('query_id')}` missing: {', '.join(item.get('missing', []))}")
    else:
        lines.extend(["## Missing Checkpoints", "", "All inspected trajectories contain the required checkpoints."])
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
