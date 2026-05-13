#!/usr/bin/env python
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.adobe_env import adobe_env_readiness, format_adobe_readiness_for_report
from scripts.load_local_env import load_local_env


def main() -> int:
    load_local_env(ROOT)
    print(json.dumps(format_adobe_readiness_for_report(adobe_env_readiness()), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
