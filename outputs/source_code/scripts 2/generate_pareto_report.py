#!/usr/bin/env python
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.reporting import generate_pareto_report


def main() -> int:
    config = Config.from_env(ROOT)
    report = generate_pareto_report(config)
    print(json.dumps({"best_final": report["best_final_score_strategy"], "markdown": str(config.outputs_dir / "pareto_report.md")}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
