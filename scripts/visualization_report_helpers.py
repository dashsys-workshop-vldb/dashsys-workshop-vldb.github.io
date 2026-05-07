from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from dashagent.trajectory import compact_preview, redact_secrets


ROOT = Path(__file__).resolve().parents[1]
OUTPUTS_DIR = ROOT / "outputs"
VIS_DIR = OUTPUTS_DIR / "visualizations"
UNAVAILABLE = "unavailable"

_OPENROUTER_KEY_PREFIX = "sk" + "-or-"
_OPENAI_KEY_PREFIX = "sk" + "-"
_AUTH_HEADER_PREFIX = "Authorization:" + r"\s*" + "Bearer"

SECRET_PATTERNS = [
    re.compile(re.escape(_OPENROUTER_KEY_PREFIX) + r"[A-Za-z0-9_-]+"),
    re.compile(re.escape(_OPENAI_KEY_PREFIX) + r"[A-Za-z0-9_-]{20,}"),
    re.compile(_AUTH_HEADER_PREFIX + r"\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE),
    re.compile(r"(OPENROUTER_API_KEY|OPENAI_API_KEY|CLIENT_SECRET|ACCESS_TOKEN)=\S+"),
]


def load_json(relative_path: str, default: Any | None = None) -> Any:
    path = ROOT / relative_path
    if not path.exists():
        return {} if default is None else default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {} if default is None else default


def redacted(obj: Any) -> Any:
    return _redact_patterns(redact_secrets(obj))


def _redact_patterns(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {key: _redact_patterns(value) for key, value in obj.items()}
    if isinstance(obj, list):
        return [_redact_patterns(item) for item in obj]
    if isinstance(obj, str):
        value = obj
        for pattern in SECRET_PATTERNS:
            value = pattern.sub("[REDACTED]", value)
        return value
    return obj


def metric(value: Any) -> Any:
    if value is None or value == "":
        return UNAVAILABLE
    return value


def get_path(data: Any, *keys: str, default: Any = UNAVAILABLE) -> Any:
    current = data
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return metric(current)


def summary(relative_path: str) -> dict[str, Any]:
    data = load_json(relative_path, {})
    if isinstance(data, dict) and isinstance(data.get("summary"), dict):
        return data["summary"]
    return data if isinstance(data, dict) else {}


def strict_strategy_summary(strategy: str = "SQL_FIRST_API_VERIFY") -> dict[str, Any]:
    data = load_json("outputs/eval_results_strict.json", {})
    return (data.get("summary", {}).get("by_strategy", {}) or {}).get(strategy, {}) if isinstance(data, dict) else {}


def strict_rows(strategy: str = "SQL_FIRST_API_VERIFY") -> list[dict[str, Any]]:
    data = load_json("outputs/eval_results_strict.json", {})
    rows = data.get("rows", []) if isinstance(data, dict) else []
    return [row for row in rows if row.get("strategy") == strategy]


def strict_row_by_query(query_id: str, strategy: str = "SQL_FIRST_API_VERIFY") -> dict[str, Any]:
    for row in strict_rows(strategy):
        if row.get("query_id") == query_id:
            return row
    return {}


def write_json(path: Path, payload: Any) -> None:
    ensure_visualization_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(redacted(payload), indent=2, sort_keys=True, default=str), encoding="utf-8")


def write_md(path: Path, content: str) -> None:
    ensure_visualization_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(redact_text(content), encoding="utf-8")


def ensure_visualization_path(path: Path) -> None:
    resolved = path.resolve()
    viz = VIS_DIR.resolve()
    if "final_submission" in resolved.parts:
        raise RuntimeError(f"Refusing to write visualization under final_submission: {path}")
    try:
        resolved.relative_to(viz)
    except ValueError as exc:
        raise RuntimeError(f"Visualization output must be under {VIS_DIR}: {path}") from exc


def redact_text(content: str) -> str:
    text = content
    for pattern in SECRET_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text


def md_escape(value: Any) -> str:
    if value is None:
        return UNAVAILABLE
    text = str(value)
    text = text.replace("\n", "<br/>")
    text = text.replace("|", "\\|")
    return redact_text(text)


def table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(md_escape(cell) for cell in row) + " |")
    return "\n".join(lines)


def mermaid_block(graph: str) -> str:
    return "```mermaid\n" + graph.strip() + "\n```"


def mermaid_label(value: Any, max_chars: int = 48) -> str:
    text = str(value if value is not None else UNAVAILABLE)
    text = redact_text(text)
    text = re.sub(r"[\n\r\t{}<>|`]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_chars:
        text = text[: max_chars - 3].rstrip() + "..."
    return text.replace('"', "'")


def compact(value: Any, max_chars: int = 180) -> str:
    if value in (None, "", [], {}):
        return UNAVAILABLE
    preview = compact_preview(value, max_chars=max_chars)
    if isinstance(preview, str):
        text = preview
    else:
        text = json.dumps(preview, ensure_ascii=False, default=str)
    if len(text) > max_chars:
        text = text[: max_chars - 3].rstrip() + "..."
    return redact_text(text)


def score_delta(after: Any, before: Any) -> Any:
    try:
        return round(float(after) - float(before), 4)
    except Exception:
        return UNAVAILABLE


def bool_status(value: Any) -> str:
    if value is True:
        return "yes"
    if value is False:
        return "no"
    return UNAVAILABLE if value in (None, "") else str(value)


def source(path: str, field: str | None = None) -> dict[str, str]:
    payload = {"path": path}
    if field:
        payload["field"] = field
    return payload


def required_visualization_files() -> list[str]:
    query_ids = ["example_000", "example_003", "example_011", "example_021", "example_031", "example_033"]
    files = [
        "index.md",
        "index.json",
        "technique_catalog.md",
        "technique_catalog.json",
        "system_end_to_end.md",
        "system_end_to_end.json",
        "technique_impact_matrix.md",
        "technique_impact_matrix.json",
        "score_improvement_timeline.md",
        "score_improvement_timeline.json",
        "current_system_state.md",
        "current_system_state.json",
        "technique_dataflow_views.md",
        "technique_dataflow_views.json",
    ]
    for query_id in query_ids:
        files.append(f"query_{query_id}_dataflow.md")
        files.append(f"query_{query_id}_dataflow.json")
    return files
