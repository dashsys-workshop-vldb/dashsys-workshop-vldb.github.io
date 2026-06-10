#!/usr/bin/env python
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.reporting import generate_family_score_report


def main() -> int:
    config = Config.from_env(ROOT)
    report = generate_family_score_report(config)
    print(json.dumps({"families": len(report["families"]), "markdown": str(config.outputs_dir / "family_score_report.md")}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
