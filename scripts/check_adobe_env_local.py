#!/usr/bin/env python
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.load_local_env import load_local_env

REQUIRED = [
    ("ADOBE_ACCESS_TOKEN", "ACCESS_TOKEN"),
    ("ADOBE_API_KEY", "CLIENT_ID"),
    ("ADOBE_ORG_ID", "IMS_ORG"),
    ("ADOBE_SANDBOX_NAME", "SANDBOX"),
    ("ADOBE_BASE_URL",),
]


def _present(*names: str) -> bool:
    return any(bool(os.getenv(name)) for name in names)


def main() -> int:
    load_meta = load_local_env(ROOT)
    status = {
        "report": "Adobe credential check",
        "env_source": load_meta.get("source") or "environment_or_missing",
        "vars": {
            "ADOBE_ACCESS_TOKEN": "present" if _present("ADOBE_ACCESS_TOKEN", "ACCESS_TOKEN") else "missing",
            "ADOBE_API_KEY": "present" if _present("ADOBE_API_KEY", "CLIENT_ID") else "missing",
            "ADOBE_ORG_ID": "present" if _present("ADOBE_ORG_ID", "IMS_ORG") else "missing",
            "ADOBE_SANDBOX_NAME": "present" if _present("ADOBE_SANDBOX_NAME", "SANDBOX") else "missing",
            "ADOBE_BASE_URL": "present" if _present("ADOBE_BASE_URL") else "missing",
        },
        "headers_constructible": {
            "Authorization": _present("ADOBE_ACCESS_TOKEN", "ACCESS_TOKEN"),
            "x-api-key": _present("ADOBE_API_KEY", "CLIENT_ID"),
            "x-gw-ims-org-id": _present("ADOBE_ORG_ID", "IMS_ORG"),
            "x-sandbox-name": _present("ADOBE_SANDBOX_NAME", "SANDBOX"),
        },
    }
    status["ready_for_live_adobe_api_smoke"] = all(_present(*group) for group in REQUIRED)
    print(json.dumps(status, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
