from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

from .trajectory import redact_secrets


@dataclass
class RawSQLSafetyGateResult:
    passed: bool
    error_type: str | None = None
    error_message: str | None = None
    sql: str = ""
    params: list[Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RawSQLSafetyGate:
    def __init__(self, *, max_sql_length: int = 4000) -> None:
        self.max_sql_length = int(max_sql_length)

    def check(self, sql: str, params: list[Any] | None = None) -> RawSQLSafetyGateResult:
        text = str(sql or "").strip()
        if not isinstance(params, list) and params is not None:
            return self._fail("invalid_params", "Raw SQL fallback params must be a list.", text, params=None)
        safe_params = list(params or [])
        if not text:
            return self._fail("unknown", "Raw SQL fallback SQL is empty.", text, safe_params)
        if "--" in text or "/*" in text or "*/" in text:
            return self._fail("forbidden_keyword", "Raw SQL fallback must not contain SQL comments.", text, safe_params)
        if len(text) > self.max_sql_length:
            return self._fail("sql_too_long", f"Raw SQL fallback exceeds max_sql_length={self.max_sql_length}.", text, safe_params)
        if _statement_count(text) != 1:
            return self._fail("multiple_statements", "Raw SQL fallback must contain exactly one statement.", text, safe_params)
        normalized = text.rstrip(";").strip()
        if not re.match(r"(?is)^select\b", normalized):
            return self._fail("non_select", "Raw SQL fallback must be a SELECT statement.", text, safe_params)
        forbidden = _forbidden_keyword(normalized)
        if forbidden:
            return self._fail("forbidden_keyword", f"Raw SQL fallback contains forbidden keyword or function: {forbidden}.", text, safe_params)
        if not _is_aggregate_select(normalized) and not re.search(r"(?is)\blimit\s+\d+\b", normalized):
            return self._fail("missing_limit", "Raw SQL fallback SELECT must include LIMIT unless it is an aggregate/count query.", text, safe_params)
        return RawSQLSafetyGateResult(True, None, None, normalized, safe_params)

    def _fail(self, error_type: str, message: str, sql: str, params: list[Any] | None) -> RawSQLSafetyGateResult:
        return RawSQLSafetyGateResult(False, error_type, str(redact_secrets(message))[:500], sql, params)


def _statement_count(sql: str) -> int:
    statements: list[str] = []
    current: list[str] = []
    in_single = False
    in_double = False
    escaped = False
    for char in sql:
        current.append(char)
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == "'" and not in_double:
            in_single = not in_single
            continue
        if char == '"' and not in_single:
            in_double = not in_double
            continue
        if char == ";" and not in_single and not in_double:
            statement = "".join(current).strip().rstrip(";").strip()
            if statement:
                statements.append(statement)
            current = []
    tail = "".join(current).strip().rstrip(";").strip()
    if tail:
        statements.append(tail)
    return len(statements)


FORBIDDEN_PATTERNS = [
    r"\binsert\b",
    r"\bupdate\b",
    r"\bdelete\b",
    r"\bmerge\b",
    r"\bupsert\b",
    r"\bcreate\b",
    r"\balter\b",
    r"\bdrop\b",
    r"\btruncate\b",
    r"\bcopy\b",
    r"\bexport\b",
    r"\bimport\b",
    r"\battach\b",
    r"\bdetach\b",
    r"\bpragma\b",
    r"\bset\b",
    r"\bcall\b",
    r"\bexecute\b",
    r"\bread_csv\b",
    r"\bread_parquet\b",
    r"\bhttpfs\b",
]


def _forbidden_keyword(sql: str) -> str | None:
    for pattern in FORBIDDEN_PATTERNS:
        match = re.search(pattern, sql, flags=re.IGNORECASE)
        if match:
            return match.group(0).upper()
    return None


def _is_aggregate_select(sql: str) -> bool:
    select_part = re.split(r"(?is)\bfrom\b", sql, maxsplit=1)[0]
    return bool(re.search(r"(?is)\b(count|sum|avg|min|max)\s*\(", select_part))
