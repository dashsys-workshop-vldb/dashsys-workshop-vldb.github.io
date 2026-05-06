#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.eval_harness import EvalHarness
from dashagent.planner import ALL_STRATEGIES, STRATEGIES
from dashagent.answer_style_miner import write_answer_style_patterns


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
    args = parser.parse_args()

    config = Config.from_env(ROOT)
    write_answer_style_patterns(config)
    harness = EvalHarness(config)
    selected = parse_strategies(args.strategy, args.strategies)
    result = harness.run(strategies=selected or STRATEGIES, include_live_api_metrics=args.live_api, strict=args.strict)
    print(
        json.dumps(
            {
                "examples": result["examples"],
                "strategies": result["strategies"],
                "summary": result["summary"],
                "strict": result.get("strict", False),
                "live_api_metrics": result.get("live_api_metrics"),
                "strategy_comparison": str(config.outputs_dir / ("strategy_comparison_strict.md" if args.strict else "strategy_comparison.md")),
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


if __name__ == "__main__":
    raise SystemExit(main())
