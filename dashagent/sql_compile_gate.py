from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from .db import DuckDBDatabase, translate_sql_for_duckdb
from .trajectory import redact_secrets


@dataclass
class SQLCompileGateResult:
    passed: bool
    error_type: str | None
    error_message: str | None
    sql: str
    params: list[Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SQLCompileGate:
    """Compile-check LLM-generated SQL against the live DuckDB schema without rewriting it."""

    def __init__(self, db: DuckDBDatabase) -> None:
        self.db = db

    def check(self, sql: str, params: list[Any] | None = None) -> SQLCompileGateResult:
        original_sql = sql
        original_params = list(params) if params is not None else None
        try:
            translated_sql = translate_sql_for_duckdb(sql)
            compile_sql = f"EXPLAIN {translated_sql.strip().rstrip(';')}"
            if original_params is None:
                self.db.conn.execute(compile_sql)
            else:
                self.db.conn.execute(compile_sql, original_params)
            return SQLCompileGateResult(
                passed=True,
                error_type=None,
                error_message=None,
                sql=original_sql,
                params=original_params,
            )
        except Exception as exc:
            error_message = _sanitize_error_message(str(exc))
            return SQLCompileGateResult(
                passed=False,
                error_type=_classify_compile_error(error_message),
                error_message=error_message,
                sql=original_sql,
                params=original_params,
            )


def _sanitize_error_message(message: str) -> str:
    redacted = redact_secrets(message)
    text = str(redacted).splitlines()[0] if str(redacted).splitlines() else str(redacted)
    return text[:500]


def _classify_compile_error(message: str) -> str:
    lowered = message.lower()
    if "parser error" in lowered or "syntax error" in lowered:
        return "syntax_error"
    if re.search(
        r"binder error|catalog error|ambiguous|does not exist|not found|no such|unknown|referenced "
        r"(?:column|table)|column|table|alias|function|type mismatch|cannot compare|conversion error",
        lowered,
    ):
        return "semantic_error"
    if message:
        return "compile_error"
    return "unknown"
