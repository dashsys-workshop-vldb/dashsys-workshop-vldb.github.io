#!/usr/bin/env python
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.db import DuckDBDatabase
from dashagent.endpoint_catalog import EndpointCatalog
from dashagent.pattern_mining import mine_gold_patterns
from dashagent.schema_index import SchemaIndex


def main() -> int:
    config = Config.from_env(ROOT)
    config.ensure_dirs()
    db = DuckDBDatabase(config)
    schema_index = SchemaIndex.build(db)
    schema_path, graph_path = schema_index.save(config)
    catalog = EndpointCatalog(config)
    catalog_path = catalog.save()
    patterns = mine_gold_patterns(config)

    status = {
        "dbsnapshot_dir": str(config.dbsnapshot_dir),
        "data_json_path": str(config.data_json_path),
        "parquet_files_found": len(list(config.dbsnapshot_dir.rglob("*.parquet"))) if config.dbsnapshot_dir.exists() else 0,
        "tables_loaded": len(db.list_tables()),
        "schema_summary": str(schema_path),
        "join_graph": str(graph_path),
        "endpoint_catalog": str(catalog_path),
        "gold_sql_patterns": len(patterns["sql"]),
        "gold_api_patterns": len(patterns["api"]),
        "gold_answer_patterns": len(patterns["answer"]),
    }
    print(json.dumps(status, indent=2, sort_keys=True))
    if status["parquet_files_found"] == 0:
        print("No parquet files found. Place DBSnapshot files under data/DBSnapshot/.", file=sys.stderr)
    if not config.data_json_path.exists():
        print("No data.json found. Place public examples at data/data.json.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
