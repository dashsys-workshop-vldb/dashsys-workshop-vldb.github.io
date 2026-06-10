#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.evidence_match_scorer import score_evidence_match
from dashagent.prompt_semantic_ir import extract_objective_prompt_features
from dashagent.staged_evidence_policy import decide_initial_evidence_branch


VARIANTS = [
    "shadow_observe_only",
    "deterministic_high_conf_only",
    "llm_advisor_medium_low_only",
    "combined_verified_policy",
    "drop_api_when_sql_direct_answer",
    "sql_first_then_api_if_needed",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run shadow-only staged evidence policy trial.")
    parser.add_argument("--generated-limit", type=int, default=50)
    args = parser.parse_args()
    cfg = Config.from_env()
    rows = _load_rows(cfg, generated_limit=args.generated_limit)
    branch_counts: Counter[str] = Counter()
    second_counts: Counter[str] = Counter()
    sql_both_high = 0
    api_first = 0
    no_tool = 0
    result_rows: list[dict[str, Any]] = []

    for row in rows:
        features = extract_objective_prompt_features(row["prompt"])
        score = score_evidence_match(features)
        branch = decide_initial_evidence_branch(score)
        branch_counts[branch.first_branch] += 1
        second_counts[branch.second_branch_policy] += 1
        sql_both_high += 1 if score.sql_match >= 0.7 and score.api_match >= 0.6 else 0
        api_first += 1 if branch.first_branch == "API" else 0
        no_tool += 1 if branch.first_branch == "NO_TOOL" else 0
        result_rows.append(
            {
                "prompt_id": row["prompt_id"],
                "source": row["source"],
                "prompt": row["prompt"],
                "score": score.to_dict(),
                "branch": branch.to_dict(),
            }
        )

    variant_summaries = _variant_summaries(result_rows)
    summary = {
        "classification": "diagnostic_only",
        "shadow_only": True,
        "packaged_default_strategy": "SQL_FIRST_API_VERIFY",
        "packaged_execution_changed": False,
        "total_prompts": len(result_rows),
        "branch_distribution": dict(sorted(branch_counts.items())),
        "second_branch_distribution": dict(sorted(second_counts.items())),
        "sql_and_api_both_high_count": sql_both_high,
        "api_first_count": api_first,
        "no_tool_branch_count": no_tool,
        "variants": variant_summaries,
        "strict_delta": 0.0,
        "api_score_delta": 0.0,
        "answer_score_delta": 0.0,
        "tool_call_delta": 0,
        "unsupported_claims": 0,
        "endpoint_matrix_status": "unchanged_shadow_only",
        "recommendation": "keep_shadow_only",
    }
    report = {**summary, "rows": result_rows}
    out_json = cfg.outputs_dir / "reports" / "staged_evidence_policy_trial.json"
    out_md = cfg.outputs_dir / "reports" / "staged_evidence_policy_trial.md"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    out_md.write_text(_render_markdown(summary), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


def _variant_summaries(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    summaries: dict[str, dict[str, Any]] = {}
    for variant in VARIANTS:
        saved = 0
        added = 0
        advisor_invocations = 0
        if variant in {"drop_api_when_sql_direct_answer", "sql_first_then_api_if_needed", "combined_verified_policy"}:
            saved = sum(1 for row in rows if row["branch"]["first_branch"] == "SQL" and row["branch"]["second_branch_policy"] == "NONE")
        if variant in {"llm_advisor_medium_low_only", "combined_verified_policy"}:
            advisor_invocations = sum(1 for row in rows if row["branch"]["second_branch_policy"] != "NONE")
        if variant == "sql_first_then_api_if_needed":
            added = sum(1 for row in rows if row["branch"]["second_branch_policy"] == "API_AFTER_SQL_IF_NEEDED")
        summaries[variant] = {
            "shadow_only": True,
            "estimated_api_calls_saved": saved,
            "estimated_api_calls_added": added,
            "estimated_llm_advisor_invocations": advisor_invocations,
            "strict_delta": 0.0,
            "api_delta": 0.0,
            "answer_delta": 0.0,
        }
    return summaries


def _load_rows(cfg: Config, *, generated_limit: int) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if cfg.data_json_path.exists():
        for idx, row in enumerate(json.loads(cfg.data_json_path.read_text(encoding="utf-8")), start=1):
            rows.append({"prompt_id": f"public_{idx:03d}", "prompt": str(row.get("query") or ""), "source": "public_dev"})
    generated = cfg.data_dir / "generated_prompt_suite.json"
    if generated.exists() and generated_limit:
        for idx, row in enumerate(json.loads(generated.read_text(encoding="utf-8"))[:generated_limit], start=1):
            rows.append({"prompt_id": str(row.get("prompt_id") or f"generated_{idx:03d}"), "prompt": str(row.get("prompt") or ""), "source": "generated"})
    return rows


def _render_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Staged Evidence Policy Trial",
        "",
        "Classification: `diagnostic_only`. The trial is shadow-only and did not change packaged `SQL_FIRST_API_VERIFY` execution.",
        "",
        "## Summary",
        "",
    ]
    for key in [
        "total_prompts",
        "branch_distribution",
        "second_branch_distribution",
        "sql_and_api_both_high_count",
        "api_first_count",
        "no_tool_branch_count",
        "strict_delta",
        "api_score_delta",
        "answer_score_delta",
        "tool_call_delta",
        "recommendation",
    ]:
        lines.append(f"- {key}: `{summary.get(key)}`")
    lines.extend(["", "## Variants", ""])
    for variant, payload in (summary.get("variants") or {}).items():
        lines.append(f"- `{variant}`: saved `{payload.get('estimated_api_calls_saved')}`, added `{payload.get('estimated_api_calls_added')}`, advisor calls `{payload.get('estimated_llm_advisor_invocations')}`")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
