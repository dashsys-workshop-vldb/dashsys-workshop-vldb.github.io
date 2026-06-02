#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.eval_harness import EvalHarness
from dashagent.live_api_guard import evaluate_live_api_full_run_guard, guard_override_metadata
from dashagent.planner import ALL_STRATEGIES, STRATEGIES
from dashagent.answer_style_miner import write_answer_style_patterns
from scripts.load_local_env import load_local_env


def main() -> int:
    parser = argparse.ArgumentParser(description="Run public-example evaluation for all strategies.")
    parser.add_argument("--strategy", action="append", choices=ALL_STRATEGIES, help="Limit to one or more strategies.")
    parser.add_argument(
        "--strategies",
        action="append",
        help="Comma-separated or repeated strategy list. Includes optional LLM strategies.",
    )
    parser.add_argument("--strict", action="store_true", help="Use strict scorer and write *_strict outputs.")
    parser.add_argument(
        "--live-api",
        action="store_true",
        help="Include live API success/empty/error metrics when Adobe credentials are available.",
    )
    parser.add_argument(
        "--allow-live-diagnostic-without-success",
        action="store_true",
        help="Explicitly allow diagnostic-only live strict eval when smoke has no live_success.",
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        help="Optional organizer-style dataset JSON to evaluate instead of the default data/data.json.",
    )
    parser.add_argument(
        "--per-query-timeout-sec",
        type=float,
        default=None,
        help="Run each example/strategy row in a child process with this hard timeout.",
    )
    parser.add_argument(
        "--partial-report-dir",
        type=Path,
        default=None,
        help="Directory for timeout-aware partial eval reports.",
    )
    args = parser.parse_args()

    load_local_env(ROOT)
    original_config = Config.from_env(ROOT)
    config = original_config
    guard: dict | None = None
    if args.strict:
        guard = evaluate_live_api_full_run_guard(
            original_config,
            override=args.allow_live_diagnostic_without_success,
            run_label="live_strict_eval",
        )
        if not guard.get("allowed"):
            print(
                json.dumps(
                    {
                        "status": "blocked_by_live_api_guard",
                        "live_api_guard": guard,
                        "blocker_report": str(original_config.outputs_dir / "reports" / "live_api_full_run_blocker.json"),
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 2
        if guard.get("override_used"):
            config = replace(original_config, outputs_dir=original_config.outputs_dir / "live_api_strict_eval_diagnostic_override")
    write_answer_style_patterns(config)
    harness = EvalHarness(config)
    selected = parse_strategies(args.strategy, args.strategies)
    examples = harness.load_examples(args.dataset) if args.dataset else None
    per_query_timeout_sec = args.per_query_timeout_sec or _float_env("DASHAGENT_DEV_EVAL_QUERY_TIMEOUT_SEC")
    partial_report_dir = args.partial_report_dir or _path_env("DASHAGENT_DEV_EVAL_PARTIAL_REPORT_DIR")
    result = harness.run(
        strategies=selected or STRATEGIES,
        examples=examples,
        include_live_api_metrics=args.live_api,
        strict=args.strict,
        per_query_timeout_sec=per_query_timeout_sec,
        partial_report_dir=partial_report_dir,
    )
    if args.dataset:
        result["dataset_path"] = str(args.dataset)
        suffix = "_strict" if args.strict else ""
        (config.outputs_dir / f"eval_results{suffix}.json").write_text(
            json.dumps(result, indent=2, sort_keys=True, default=str),
            encoding="utf-8",
        )
    if guard and guard.get("override_used"):
        _record_override_outputs(original_config, config, result, guard, strict=args.strict)
    print(
        json.dumps(
            {
                "examples": result["examples"],
                "strategies": result["strategies"],
                "summary": result["summary"],
                "strict": result.get("strict", False),
                "dataset_path": str(args.dataset) if args.dataset else None,
                "live_api_metrics": result.get("live_api_metrics"),
                "per_query_timeout_sec": per_query_timeout_sec,
                "partial_report_dir": str(partial_report_dir) if partial_report_dir else None,
                "timeout_query_ids": result.get("timeout_query_ids"),
                "failed_query_ids": result.get("failed_query_ids"),
                "strategy_comparison": str(config.outputs_dir / ("strategy_comparison_strict.md" if args.strict else "strategy_comparison.md")),
                "live_api_guard": guard,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def parse_strategies(strategy_args: list[str] | None, strategies_args: list[str] | None) -> list[str] | None:
    values: list[str] = []
    for item in strategy_args or []:
        values.append(item)
    for item in strategies_args or []:
        values.extend(part.strip() for part in item.split(",") if part.strip())
    unknown = [item for item in values if item not in ALL_STRATEGIES]
    if unknown:
        raise SystemExit(f"Unknown strategy {unknown[0]}. Expected one of {ALL_STRATEGIES}.")
    return values or None


def _float_env(name: str) -> float | None:
    raw = os.getenv(name)
    if not raw:
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    return value if value > 0 else None


def _path_env(name: str) -> Path | None:
    raw = os.getenv(name)
    return Path(raw).expanduser() if raw else None


def _record_override_outputs(original_config: Config, effective_config: Config, result: dict, guard: dict, *, strict: bool) -> None:
    metadata = guard_override_metadata(guard)
    result.update(metadata)
    suffix = "_strict" if strict else ""
    json_path = effective_config.outputs_dir / f"eval_results{suffix}.json"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True, default=str), encoding="utf-8")
    reports_dir = original_config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "report_type": "live_api_strict_eval_diagnostic_override",
        **metadata,
        "output_root": str(effective_config.outputs_dir),
        "eval_results_path": str(json_path),
        "strategy_comparison_path": str(effective_config.outputs_dir / f"strategy_comparison{suffix}.md"),
        "official_outputs_not_written": [
            str(original_config.outputs_dir / "eval_results_strict.json"),
            str(original_config.outputs_dir / "eval"),
            str(original_config.outputs_dir / "final_submission"),
            str(original_config.outputs_dir / "final_submission_manifest.json"),
        ],
    }
    (reports_dir / "live_api_strict_eval_diagnostic_override.json").write_text(
        json.dumps(report, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    (reports_dir / "live_api_strict_eval_diagnostic_override.md").write_text(
        "\n".join(
            [
                "# Live API Strict Eval Diagnostic Override",
                "",
                "This run used an explicit diagnostic-only override and did not write official strict artifacts.",
                "",
                f"- Output root: `{report['output_root']}`",
                f"- Override used: `{report['override_used']}`",
                f"- Official score claim: `{report['official_score_claim']}`",
                f"- Promotion allowed: `{report['promotion_allowed']}`",
                "",
            ]
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
