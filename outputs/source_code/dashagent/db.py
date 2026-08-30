from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb

from .config import Config, DEFAULT_CONFIG


DESTRUCTIVE_SQL = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|COPY|ATTACH|DETACH|MERGE|TRUNCATE|"
    r"VACUUM|EXPORT|IMPORT|INSTALL|LOAD|PRAGMA\s+.*=|SET)\b",
    re.IGNORECASE | re.DOTALL,
)


def sanitize_table_name(path: Path) -> str:
    name = re.sub(r"[^0-9a-zA-Z_]+", "_", path.stem).strip("_").lower()
    if not name:
        name = "table"
    if name[0].isdigit():
        name = f"t_{name}"
    return name


def quote_ident(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def strip_sql_comments(sql: str) -> str:
    sql = re.sub(r"--.*?(?=\n|$)", " ", sql)
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    return sql.strip()


def translate_sql_for_duckdb(sql: str) -> str:
    def replace_dateadd(match: re.Match[str]) -> str:
        unit = match.group("unit").lower()
        amount = match.group("amount")
        base = match.group("base").strip()
        interval_unit = "month" if unit.startswith("month") else "day"
        return f"({base} + ({amount}) * INTERVAL '1 {interval_unit}')"

    translated = re.sub(
        r"DATEADD\s*\(\s*(?P<unit>MONTH|DAY)\s*,\s*(?P<amount>[-+]?\d+)\s*,\s*(?P<base>[^)]+?)\s*\)",
        replace_dateadd,
        sql,
        flags=re.IGNORECASE,
    )
    translated = re.sub(
        r'(?P<lhs>(?:[A-Za-z_][\w$]*\.)?(?:"(?:CREATEDTIME|UPDATEDTIME)"|[A-Za-z_]*(?:created|updated)time))\s*(?P<op>>=|<=|>|<)\s*(?P<rhs>\(CURRENT_DATE\s+\+\s+\([-+]?\d+\)\s*\*\s*INTERVAL\s+\'[^\']+\'\))',
        lambda match: f"TRY_CAST({match.group('lhs')} AS TIMESTAMP) {match.group('op')} {match.group('rhs')}",
        translated,
        flags=re.IGNORECASE,
    )
    return translated


def is_read_only_sql(sql: str) -> tuple[bool, str | None]:
    cleaned = strip_sql_comments(sql).strip().rstrip(";")
    if not cleaned:
        return False, "SQL is empty."
    if ";" in cleaned:
        return False, "Multiple SQL statements are not allowed."
    if DESTRUCTIVE_SQL.search(cleaned):
        return False, "SQL contains a blocked write or environment-changing command."
    if not re.match(r"^(SELECT|WITH|DESCRIBE|EXPLAIN)\b", cleaned, re.IGNORECASE):
        return False, "Only read-only SELECT/WITH/DESCRIBE/EXPLAIN statements are allowed."
    return True, None


@dataclass
class TableRegistration:
    table_name: str
    parquet_path: Path
    load_error: str | None = None


class DuckDBDatabase:
    """Read-only DuckDB facade over every parquet file in data/DBSnapshot."""

    def __init__(self, config: Config | None = None, dbsnapshot_dir: Path | None = None) -> None:
        self.config = config or DEFAULT_CONFIG
        self.dbsnapshot_dir = Path(dbsnapshot_dir or self.config.dbsnapshot_dir)
        self.conn = duckdb.connect(database=":memory:")
        self.registrations: dict[str, TableRegistration] = {}
        self.load_parquet_views()

    def close(self) -> None:
        self.conn.close()

    def load_parquet_views(self) -> None:
        if not self.dbsnapshot_dir.exists():
            return

        used: set[str] = set()
        for parquet_path in sorted(self.dbsnapshot_dir.rglob("*.parquet")):
            base = sanitize_table_name(parquet_path)
            table_name = base
            suffix = 2
            while table_name in used:
                table_name = f"{base}_{suffix}"
                suffix += 1
            used.add(table_name)
            path_literal = str(parquet_path.resolve()).replace("'", "''")
            load_error = None
            try:
                self.conn.execute(
                    f"CREATE OR REPLACE VIEW {quote_ident(table_name)} AS "
                    f"SELECT * FROM read_parquet('{path_literal}')"
                )
            except Exception as exc:
                load_error = str(exc).splitlines()[0][:500]
                if not is_zero_column_parquet(parquet_path):
                    raise
                self.conn.execute(
                    f"CREATE OR REPLACE VIEW {quote_ident(table_name)} AS "
                    'SELECT NULL::VARCHAR AS "__empty_parquet_placeholder" WHERE FALSE'
                )
            self.registrations[table_name] = TableRegistration(table_name, parquet_path, load_error)

    def list_tables(self) -> list[str]:
        return sorted(self.registrations)

    def table_exists(self, table: str) -> bool:
        return table in self.registrations

    def describe_table(self, table: str) -> list[dict[str, Any]]:
        if table not in self.registrations:
            raise KeyError(f"Unknown table: {table}")
        rows = self.conn.execute(f"DESCRIBE {quote_ident(table)}").fetchall()
        columns = [desc[0] for desc in self.conn.description]
        return [dict(zip(columns, row, strict=False)) for row in rows]

    def get_table_columns(self, table: str) -> list[str]:
        return [row["column_name"] for row in self.describe_table(table)]

    def get_schema_summary(self) -> dict[str, Any]:
        tables: dict[str, Any] = {}
        for table in self.list_tables():
            columns = []
            for row in self.describe_table(table):
                columns.append(
                    {
                        "name": row.get("column_name"),
                        "type": row.get("column_type"),
                        "nullable": row.get("null") != "NO",
                    }
                )
            tables[table] = {
                "parquet_file": str(self.registrations[table].parquet_path.relative_to(self.config.project_root))
                if self.registrations[table].parquet_path.is_relative_to(self.config.project_root)
                else self.registrations[table].parquet_path.name,
                "columns": columns,
                "load_error": self.registrations[table].load_error,
            }
        return {"table_count": len(tables), "tables": tables}

    def _apply_limit_protection(self, sql: str, max_rows: int, allow_full_result: bool) -> tuple[str, bool]:
        cleaned = strip_sql_comments(sql).strip().rstrip(";")
        if allow_full_result:
            return cleaned, False
        if re.search(r"\bLIMIT\s+\d+\b", cleaned, re.IGNORECASE):
            return cleaned, False
        if not re.match(r"^(SELECT|WITH)\b", cleaned, re.IGNORECASE):
            return cleaned, False
        return f"SELECT * FROM ({cleaned}) AS _dashagent_limited_result LIMIT {max_rows}", True

    def execute_sql(
        self,
        sql: str,
        *,
        max_rows: int | None = None,
        allow_full_result: bool = False,
    ) -> dict[str, Any]:
        valid, error = is_read_only_sql(sql)
        if not valid:
            return {
                "ok": False,
                "sql": sql,
                "rows": [],
                "row_count": 0,
                "limited": False,
                "error": error,
            }
        executable_sql = translate_sql_for_duckdb(sql)
        effective_sql, limited = self._apply_limit_protection(
            executable_sql, max_rows or self.config.max_result_rows, allow_full_result
        )
        try:
            result = self.conn.execute(effective_sql)
            columns = [desc[0] for desc in result.description] if result.description else []
            rows = [dict(zip(columns, row, strict=False)) for row in result.fetchall()]
            return {
                "ok": True,
                "sql": effective_sql,
                "original_sql": sql,
                "rows": rows,
                "row_count": len(rows),
                "limited": limited,
                "error": None,
            }
        except Exception as exc:  # DuckDB exceptions include query text; keep output compact.
            return {
                "ok": False,
                "sql": effective_sql,
                "original_sql": sql,
                "rows": [],
                "row_count": 0,
                "limited": limited,
                "error": str(exc).splitlines()[0][:500],
            }


def is_zero_column_parquet(path: Path) -> bool:
    try:
        import pyarrow.parquet as pq  # type: ignore

        metadata = pq.ParquetFile(path).metadata
        return metadata.num_columns == 0
    except Exception:
        return False
