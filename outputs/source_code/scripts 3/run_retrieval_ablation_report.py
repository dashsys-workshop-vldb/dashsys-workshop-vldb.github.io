#!/usr/bin/env python
from __future__ import annotations

import json
import shutil
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.candidate_context_builder import build_candidate_context
from dashagent.config import Config
from dashagent.eval_harness import EvalHarness, extract_api_calls, score_api_strict
from dashagent.executor import AgentExecutor
from dashagent.report_run import DEFAULT_RUNTIME_NOISE_SECONDS, report_metadata, runtime_budget_for_row, runtime_budget_summary
from scripts.generate_candidate_context_report import extract_sql_tables, recall_at_k


MODES = [
    ("schema_linking_only", {"enable_value_retrieval": False, "enable_endpoint_family_ranking": False, "enable_value_to_api_ranking": False, "enable_hybrid_candidate_scoring": False, "enable_official_token_reduction": False}),
    ("schema_linking_value_retrieval", {"enable_value_retrieval": True, "enable_endpoint_family_ranking": False, "enable_value_to_api_ranking": False, "enable_hybrid_candidate_scoring": False, "enable_official_token_reduction": False}),
    ("schema_value_endpoint_ranking", {"enable_value_retrieval": True, "enable_endpoint_family_ranking": True, "enable_value_to_api_ranking": True, "enable_hybrid_candidate_scoring": True, "enable_official_token_reduction": False}),
    ("full_current_retrieval", {"enable_official_token_reduction": False}),
    ("full_current_retrieval_official_token_reduction", {"enable_official_token_reduction": True}),
]


def main() -> int:
    config = Config.from_env(ROOT)
    payload = run_retrieval_ablation_report(config)
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    json_path = config.outputs_dir / "retrieval_ablation_report.json"
    md_path = config.outputs_dir / "retrieval_ablation_report.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "modes": len(payload["modes"])}, indent=2, sort_keys=True))
    return 0


def run_retrieval_ablation_report(config: Config) -> dict[str, Any]:
    root = config.outputs_dir / "retrieval_ablation_report"
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    mode_results: list[tuple[str, Config, AgentExecutor, list[dict[str, Any]]]] = []
    baseline_rows: dict[str, dict[str, Any]] = {}
    for mode_name, overrides in MODES:
        mode_config = replace(config, outputs_dir=root / mode_name, **overrides)
        executor = AgentExecutor(mode_config)
        harness = EvalHarness(mode_config, executor)
        result = harness.run(strategies=["SQL_FIRST_API_VERIFY"], strict=True)
        rows = result.get("rows", [])
        if mode_name == "full_current_retrieval":
            baseline_rows = {row["query_id"]: row for row in rows}
        mode_results.append((mode_name, mode_config, executor, rows))
    mode_payloads = [
        _mode_summary(mode_name, mode_config, executor, rows, baseline_rows)
        for mode_name, mode_config, executor, rows in mode_results
    ]
    return {
        **report_metadata(config.outputs_dir),
        "mode": "retrieval_ablation_report",
        "report_only": True,
        "packaged_execution_changed": False,
        "modes": mode_payloads,
        "summary": {
            "best_final_score_mode": _best(mode_payloads, "strict_score"),
            "lowest_token_mode": _lowest(mode_payloads, "estimated_tokens"),
            "lowest_tool_call_mode": _lowest(mode_payloads, "tool_calls"),
        },
        "artifact_isolation": {
            "allowed_outputs": ["outputs/retrieval_ablation_report.json", "outputs/retrieval_ablation_report.md", "outputs/retrieval_ablation_report/"],
            "writes_eval_outputs": False,
            "writes_final_submission": False,
            "writes_packaged_query_outputs": False,
        },
    }


def _mode_summary(
    mode_name: str,
    config: Config,
    executor: AgentExecutor,
    rows: list[dict[str, Any]],
    baseline_rows: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    examples = EvalHarness(config, executor).load_examples()
    candidate_rows = []
    table_hit = []
    api_hit = []
    clusters: dict[str, int] = {}
    for example in examples:
        context = build_candidate_context(
            example.query,
            executor.schema_index,
            executor.endpoint_catalog,
            enable_hybrid_ranking=config.enable_hybrid_candidate_scoring,
            enable_endpoint_family_ranking=config.enable_endpoint_family_ranking,
            enable_structural_preservation=config.enable_structural_schema_preservation,
            enable_value_to_api_ranking=config.enable_value_to_api_ranking,
        )
        gold_tables = extract_sql_tables(example.gold_sql)
        gold_apis = [call.get("path") for call in extract_api_calls(example.gold_api)]
        tables = context.get("candidate_tables", [])
        apis = [api.get("path") for api in context.get("candidate_apis", [])]
        if gold_tables:
            table_hit.append(recall_at_k(tables, gold_tables, 5))
        if gold_apis:
            api_hit.append(recall_at_k(apis, set(gold_apis), 5, normalize=False))
        cluster = _risk_cluster(context, gold_apis, apis)
        clusters[cluster] = clusters.get(cluster, 0) + 1
        candidate_rows.append({"query_id": example.query_id, "risk_cluster": cluster})
    runtime_rows = []
    for row in rows:
        baseline = baseline_rows.get(row["query_id"], row)
        runtime_rows.append(
            {
                "query_id": row["query_id"],
                **runtime_budget_for_row(
                    baseline_runtime=baseline.get("runtime"),
                    trial_runtime=row.get("runtime"),
                    acceptable_noise_seconds=DEFAULT_RUNTIME_NOISE_SECONDS,
                ),
            }
        )
    runtime_summary = runtime_budget_summary(runtime_rows, acceptable_noise_seconds=DEFAULT_RUNTIME_NOISE_SECONDS)
    summary = result_summary(rows)
    return {
        "mode": mode_name,
        "strict_score": summary["avg_final_score"],
        "correctness": summary["avg_correctness_score"],
        "estimated_tokens": summary["avg_estimated_tokens"],
        "runtime": summary["avg_runtime"],
        "tool_calls": summary["avg_tool_call_count"],
        "candidate_risk_clusters": clusters,
        "top_k_table_hit_rate": _avg(table_hit),
        "top_k_api_hit_rate": _avg(api_hit),
        "runtime_budget": runtime_summary,
        "rows": rows,
    }


def result_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "avg_final_score": _avg(row.get("final_score") for row in rows),
        "avg_correctness_score": _avg(row.get("correctness_score") for row in rows),
        "avg_estimated_tokens": _avg(row.get("estimated_tokens") for row in rows),
        "avg_runtime": _avg(row.get("runtime") for row in rows),
        "avg_tool_call_count": _avg(row.get("tool_call_count") for row in rows),
    }


def _risk_cluster(context: dict[str, Any], gold_apis: list[Any], candidate_apis: list[Any]) -> str:
    if gold_apis and any(api not in candidate_apis for api in gold_apis):
        return "missing_gold_api_in_top_k"
    if float(context.get("score_margin") or 0.0) == 0.0:
        return "zero_score_margin"
    if float(context.get("confidence") or 0.0) < 0.4:
        return "low_confidence"
    return "none"


def _best(modes: list[dict[str, Any]], key: str) -> str | None:
    return max(modes, key=lambda mode: float(mode.get(key) or 0.0)).get("mode") if modes else None


def _lowest(modes: list[dict[str, Any]], key: str) -> str | None:
    return min(modes, key=lambda mode: float(mode.get(key) or 999999.0)).get("mode") if modes else None


def _avg(values: Any) -> float:
    values = [float(value) for value in values if value is not None]
    return round(sum(values) / len(values), 4) if values else 0.0


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Retrieval Ablation Report",
        "",
        "| Mode | Strict score | Correctness | Tokens | Runtime | Tool calls | Table hit | API hit | Runtime budget OK |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for mode in payload["modes"]:
        lines.append(
            f"| `{mode['mode']}` | {mode['strict_score']} | {mode['correctness']} | {mode['estimated_tokens']} | "
            f"{mode['runtime']} | {mode['tool_calls']} | {mode['top_k_table_hit_rate']} | {mode['top_k_api_hit_rate']} | "
            f"{mode['runtime_budget']['runtime_budget_ok']} |"
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
