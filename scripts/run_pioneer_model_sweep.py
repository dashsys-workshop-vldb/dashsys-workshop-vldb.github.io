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
from dashagent.pioneer_model_sweep import parse_pioneer_model_sweep, run_pioneer_model_sweep
from scripts.load_local_env import load_local_env


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the focused Pioneer model safety sweep for V2.")
    parser.add_argument(
        "--models",
        default=None,
        help="Comma-separated Pioneer model display names. Defaults to PIONEER_MODEL_SWEEP or the curated non-GPT-4 model set.",
    )
    args = parser.parse_args()

    config = Config.from_env(ROOT)
    load_local_env(config.project_root)
    models = parse_pioneer_model_sweep(args.models) if args.models else parse_pioneer_model_sweep()
    result = run_pioneer_model_sweep(config, models=models)
    print(json.dumps(result["paths"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
