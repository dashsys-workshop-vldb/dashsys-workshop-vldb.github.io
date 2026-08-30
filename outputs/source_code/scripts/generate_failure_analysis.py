#!/usr/bin/env python
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.failure_analysis import generate_failure_analysis


def main() -> int:
    config = Config.from_env(ROOT)
    rows = generate_failure_analysis(config)
    print(
        json.dumps(
            {
                "rows": len(rows),
                "json": str(config.outputs_dir / "failure_analysis.json"),
                "markdown": str(config.outputs_dir / "failure_analysis.md"),
                "lowest": rows[:10],
            },
            indent=2,
            sort_keys=True,
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
