#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.agents_sdk_adapter import export_checkpoints_to_spans


def main() -> int:
    parser = argparse.ArgumentParser(description="Export real trajectory checkpoints as optional OpenAI Agents SDK spans.")
    parser.add_argument("trajectory", help="Path to trajectory.json")
    parser.add_argument("--trace-name", default="dashsys-full-query-checkpoints")
    args = parser.parse_args()
    path = Path(args.trajectory)
    trajectory = json.loads(path.read_text(encoding="utf-8"))
    checkpoints = trajectory.get("checkpoints", []) or []
    if not os.getenv("OPENAI_API_KEY"):
        print("Warning: OPENAI_API_KEY is not set; trace export will no-op unless the SDK supports local/no-key spans.")
    print(f"Trace mode: full trajectory export. Smoke test would export one fake checkpoint; this run found {len(checkpoints)} real checkpoints.")
    result = export_checkpoints_to_spans(checkpoints)
    result.update({"trace_name": args.trace_name, "trajectory": str(path), "checkpoint_count": len(checkpoints)})
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
