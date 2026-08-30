#!/usr/bin/env python
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.pioneer_model_catalog import discover_pioneer_model_catalog, write_pioneer_model_catalog_reports
from scripts.load_local_env import load_local_env


def main() -> int:
    config = Config.from_env(ROOT)
    load_local_env(config.project_root)
    report_dir = config.outputs_dir / "reports" / "pioneer_model_sweep"
    catalog = discover_pioneer_model_catalog(os.getenv("PIONEER_API_KEY"))
    paths = write_pioneer_model_catalog_reports(
        report_dir,
        catalog["endpoint_results"],
        catalog["records"],
        catalog["mapping_suggestion"],
    )
    print(
        json.dumps(
            {
                "catalog_json": str(paths["catalog_json"]),
                "catalog_md": str(paths["catalog_md"]),
                "mapping_json": str(paths["mapping_json"]),
                "decoder_or_inference_model_count": catalog["decoder_or_inference_model_count"],
                "mapped": sorted(catalog["mapping_suggestion"].get("mapping", {})),
                "unmapped": catalog["mapping_suggestion"].get("unmapped", []),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
