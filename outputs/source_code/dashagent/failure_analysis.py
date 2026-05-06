from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import Config, DEFAULT_CONFIG
from .eval_harness import coerce_gold_sql, extract_api_calls, find_example_list, first_generated_sql, generated_api_calls


FAILURE_CATEGORIES = [
    "SQL_JOIN_MISMATCH",
    "SQL_COLUMN_MISMATCH",
    "SQL_FILTER_MISMATCH",
    "API_PATH_MISMATCH",
    "API_PARAM_MISMATCH",
    "API_CALL_COUNT_MISMATCH",
    "ANSWER_TOO_GENERIC",
    "ANSWER_WRONG_FACT",
    "VALIDATION_BLOCKED",
    "DRY_RUN_ONLY",
    "UNKNOWN",
]


def generate_failure_analysis(config: Config | None = None) -> list[dict[str, Any]]:
    cfg = config or DEFAULT_CONFIG
    eval_path = cfg.outputs_dir / "eval_results.json"
    if not eval_path.exists():
        raise FileNotFoundError(f"Missing evaluation results: {eval_path}")
    eval_payload = json.loads(eval_path.read_text(encoding="utf-8"))
    examples = load_examples_by_id(cfg.data_json_path)
    rows = []
    for row in eval_payload.get("rows", []):
        output_dir = Path(row["output_dir"])
        trajectory = load_json(output_dir / "trajectory.json")
        example = examples.get(row["query_id"], {})
        generated_sql = first_generated_sql(trajectory)
        generated_api = generated_api_calls(trajectory)
        gold_api = example.get("gold_api")
        generated_answer = trajectory.get("final_answer", "")
        gold_answer = example.get("answer") or example.get("gold_answer") or ""
        category = categorize_failure(row, trajectory, generated_sql, generated_api, example)
        rows.append(
            {
                "query_id": row["query_id"],
                "query": row["query"],
                "strategy": row["strategy"],
                "sql_score": float(row["sql_score"]),
                "api_score": float(row["api_score"]),
                "answer_score": float(row["answer_score"]),
                "final_score": float(row["final_score"]),
                "generated_sql": generated_sql,
                "gold_sql": example.get("gold_sql") or "",
                "generated_api": generated_api,
                "gold_api": gold_api or [],
                "generated_answer": generated_answer,
                "gold_answer": gold_answer,
                "failure_category": category,
                "recommended_fix": recommended_fix(category, row["query"]),
            }
        )
    rows.sort(key=lambda item: (item["final_score"], item["strategy"], item["query_id"]))
    write_failure_outputs(cfg, rows)
    return rows


def load_examples_by_id(data_json_path: Path) -> dict[str, dict[str, Any]]:
    if not data_json_path.exists():
        return {}
    payload = json.loads(data_json_path.read_text(encoding="utf-8"))
    examples = find_example_list(payload)
    normalized: dict[str, dict[str, Any]] = {}
    for idx, item in enumerate(examples):
        if not isinstance(item, dict):
            continue
        query_id = str(item.get("id") or item.get("query_id") or f"example_{idx:03d}")
        copy = dict(item)
        copy["gold_sql"] = coerce_gold_sql(item) or ""
        copy["gold_api"] = item.get("gold_api") or item.get("api") or item.get("api_calls") or item.get("tool_calls") or []
        copy["gold_answer"] = item.get("answer") or item.get("gold_answer") or item.get("expected_answer") or ""
        normalized[query_id] = copy
    return normalized


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"_load_error": f"Malformed JSON in {path}"}


def categorize_failure(
    row: dict[str, Any],
    trajectory: dict[str, Any],
    generated_sql: str | None,
    generated_api: list[dict[str, Any]],
    example: dict[str, Any],
) -> str:
    if any(validation_failed(step) for step in trajectory.get("steps", [])):
        return "VALIDATION_BLOCKED"
    if float(row["sql_score"]) < 0.8 and example.get("gold_sql"):
        return sql_failure_category(generated_sql or "", example.get("gold_sql") or "")
    if float(row["api_score"]) < 0.8 and example.get("gold_api"):
        return api_failure_category(generated_api, extract_api_calls(example.get("gold_api")))
    if float(row["answer_score"]) < 0.5:
        if answer_has_contradictory_numbers(trajectory.get("final_answer", ""), example.get("answer", "")):
            return "ANSWER_WRONG_FACT"
        return "ANSWER_TOO_GENERIC"
    if any(step.get("kind") == "api_call" and step.get("result", {}).get("dry_run") for step in trajectory.get("steps", [])):
        return "DRY_RUN_ONLY"
    return "UNKNOWN"


def validation_failed(step: dict[str, Any]) -> bool:
    validation = step.get("validation")
    return isinstance(validation, dict) and validation.get("ok") is False


def sql_failure_category(generated_sql: str, gold_sql: str) -> str:
    generated_lower = generated_sql.lower()
    gold_lower = gold_sql.lower()
    if " join " in gold_lower and " join " not in generated_lower:
        return "SQL_JOIN_MISMATCH"
    if selected_columns(generated_lower) != selected_columns(gold_lower):
        return "SQL_COLUMN_MISMATCH"
    if where_clause(generated_lower) != where_clause(gold_lower):
        return "SQL_FILTER_MISMATCH"
    if " join " in gold_lower and " join " in generated_lower and generated_lower != gold_lower:
        return "SQL_JOIN_MISMATCH"
    return "SQL_FILTER_MISMATCH"


def selected_columns(sql: str) -> str:
    before_from = sql.split(" from ", 1)[0]
    return " ".join(before_from.replace('"', "").split())


def where_clause(sql: str) -> str:
    if " where " not in sql:
        return ""
    tail = sql.split(" where ", 1)[1]
    for marker in [" group by ", " order by ", " limit "]:
        if marker in tail:
            tail = tail.split(marker, 1)[0]
    return " ".join(tail.replace('"', "").split())


def api_failure_category(generated_api: list[dict[str, Any]], gold_api: list[dict[str, Any]]) -> str:
    if len(generated_api) != len(gold_api):
        return "API_CALL_COUNT_MISMATCH"
    generated_paths = {(call.get("method"), call.get("path")) for call in generated_api}
    gold_paths = {(call.get("method"), call.get("path")) for call in gold_api}
    if generated_paths != gold_paths:
        return "API_PATH_MISMATCH"
    return "API_PARAM_MISMATCH"


def answer_has_contradictory_numbers(generated: str, gold: str) -> bool:
    import re

    generated_numbers = set(re.findall(r"\b\d+\b", generated))
    gold_numbers = set(re.findall(r"\b\d+\b", gold))
    return bool(generated_numbers and gold_numbers and generated_numbers.isdisjoint(gold_numbers))


def recommended_fix(category: str, query: str) -> str:
    mapping = {
        "SQL_JOIN_MISMATCH": "Add or adjust a schema-validated SQL join template for this relationship pattern.",
        "SQL_COLUMN_MISMATCH": "Align the selected projection/aliases with the requested fields and known gold-style columns.",
        "SQL_FILTER_MISMATCH": "Improve deterministic filter extraction for quoted names, statuses, time windows, and sandbox/domain phrases.",
        "API_PATH_MISMATCH": "Add endpoint selection rules or endpoint catalog coverage for this query family.",
        "API_PARAM_MISMATCH": "Add endpoint-specific parameter templates using reusable gold API parameter patterns.",
        "API_CALL_COUNT_MISMATCH": "Emit the expected sequence of API calls or intentionally document why a call is skipped.",
        "ANSWER_TOO_GENERIC": "Add a query-family answer template that names concrete SQL/API evidence.",
        "ANSWER_WRONG_FACT": "Audit answer template field selection and avoid summarizing the wrong row/value.",
        "VALIDATION_BLOCKED": "Fix template validation by using actual schema/catalog names and resolving placeholders before execution.",
        "DRY_RUN_ONLY": "Run with Adobe credentials for live evidence, or make the answer explicitly describe dry-run limitations.",
        "UNKNOWN": "Inspect trajectory manually and add a targeted deterministic rule only if it generalizes.",
    }
    return mapping.get(category, mapping["UNKNOWN"])


def write_failure_outputs(config: Config, rows: list[dict[str, Any]]) -> None:
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    json_path = config.outputs_dir / "failure_analysis.json"
    md_path = config.outputs_dir / "failure_analysis.md"
    json_path.write_text(json.dumps(rows, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(rows), encoding="utf-8")


def render_markdown(rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Failure Analysis",
        "",
        "Rows are sorted from lowest final score to highest.",
        "",
        "| Rank | Query ID | Strategy | Final | SQL | API | Answer | Category | Recommended Fix |",
        "|---:|---|---|---:|---:|---:|---:|---|---|",
    ]
    for index, row in enumerate(rows, start=1):
        lines.append(
            "| {rank} | {query_id} | {strategy} | {final:.4f} | {sql:.4f} | {api:.4f} | {answer:.4f} | {category} | {fix} |".format(
                rank=index,
                query_id=row["query_id"],
                strategy=row["strategy"],
                final=row["final_score"],
                sql=row["sql_score"],
                api=row["api_score"],
                answer=row["answer_score"],
                category=row["failure_category"],
                fix=row["recommended_fix"].replace("|", "/"),
            )
        )
    lines.append("")
    lines.append("## Details")
    for row in rows:
        lines.extend(
            [
                "",
                f"### {row['query_id']} / {row['strategy']} / {row['final_score']:.4f}",
                "",
                f"Query: {row['query']}",
                "",
                f"Failure category: `{row['failure_category']}`",
                "",
                f"Recommended fix: {row['recommended_fix']}",
                "",
                "Generated SQL:",
                "```sql",
                row["generated_sql"] or "",
                "```",
                "",
                "Gold SQL:",
                "```sql",
                row["gold_sql"] or "",
                "```",
                "",
                "Generated API:",
                "```json",
                json.dumps(row["generated_api"], indent=2, default=str),
                "```",
                "",
                "Gold API:",
                "```json",
                json.dumps(row["gold_api"], indent=2, default=str),
                "```",
                "",
                f"Generated answer: {row['generated_answer']}",
                "",
                f"Gold answer: {row['gold_answer']}",
            ]
        )
    lines.append("")
    return "\n".join(lines)
