from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .config import Config
from .db import DuckDBDatabase, quote_ident


EXPECTED_V2_DBSNAPSHOT_TABLES = ["dim_blueprint", "dim_campaign", "dim_segment", "dim_collection"]


@dataclass
class V2DBSnapshotPreflightResult:
    passed: bool
    dbsnapshot_dir: str
    exists: bool
    parquet_count: int = 0
    expected_parquet_files_present: dict[str, bool] = field(default_factory=dict)
    expected_table_row_counts: dict[str, int] = field(default_factory=dict)
    skipped_invalid_tables: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def check_v2_dbsnapshot_preflight(config: Config) -> V2DBSnapshotPreflightResult:
    dbsnapshot_dir = Path(config.dbsnapshot_dir)
    result = V2DBSnapshotPreflightResult(
        passed=False,
        dbsnapshot_dir=str(dbsnapshot_dir),
        exists=dbsnapshot_dir.exists(),
    )
    if not dbsnapshot_dir.exists():
        result.errors.append(f"DBSnapshot directory does not exist: {dbsnapshot_dir}")
        return result
    parquet_files = sorted(dbsnapshot_dir.glob("*.parquet"))
    result.parquet_count = len(parquet_files)
    if not parquet_files:
        result.errors.append(f"DBSnapshot directory contains no parquet files: {dbsnapshot_dir}")
        return result
    for table in EXPECTED_V2_DBSNAPSHOT_TABLES:
        result.expected_parquet_files_present[f"{table}.parquet"] = (dbsnapshot_dir / f"{table}.parquet").exists()
        if not result.expected_parquet_files_present[f"{table}.parquet"]:
            result.errors.append(f"Expected DBSnapshot parquet missing: {table}.parquet")
    try:
        db = DuckDBDatabase(config)
    except Exception as exc:
        result.errors.append(f"DBSnapshot DuckDB load failed: {str(exc).splitlines()[0][:300]}")
        return result
    try:
        for table, registration in db.registrations.items():
            if registration.load_error:
                result.skipped_invalid_tables.append(table)
        for table in EXPECTED_V2_DBSNAPSHOT_TABLES:
            if not db.table_exists(table):
                result.errors.append(f"Expected DBSnapshot table not registered: {table}")
                continue
            try:
                count = db.conn.execute(f"SELECT COUNT(*) FROM {quote_ident(table)}").fetchone()[0]
            except Exception as exc:
                result.errors.append(f"Expected DBSnapshot table row count failed for {table}: {str(exc).splitlines()[0][:300]}")
                continue
            result.expected_table_row_counts[table] = int(count)
    finally:
        db.close()
    result.passed = not result.errors
    return result
