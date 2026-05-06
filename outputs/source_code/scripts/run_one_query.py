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
from dashagent.executor import AgentExecutor
from dashagent.planner import STRATEGIES


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one DASHSys query through one strategy.")
    parser.add_argument("query", help="Natural-language query to answer.")
    parser.add_argument("--strategy", choices=STRATEGIES, default="SQL_FIRST_API_VERIFY")
    parser.add_argument("--query-id", default=None)
    args = parser.parse_args()

    config = Config.from_env(ROOT)
    executor = AgentExecutor(config)
    result = executor.run(args.query, strategy=args.strategy, query_id=args.query_id)
    print(
        json.dumps(
            {
                "query_id": result["query_id"],
                "strategy": result["strategy"],
                "output_dir": result["output_dir"],
                "final_answer": result["final_answer"],
                "tool_call_count": result["trajectory"]["tool_call_count"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
