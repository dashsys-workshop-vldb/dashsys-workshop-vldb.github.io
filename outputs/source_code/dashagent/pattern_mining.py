from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .api_templates import parse_api_call_string
from .config import Config, DEFAULT_CONFIG


def mine_gold_patterns(config: Config | None = None) -> dict[str, list[dict[str, Any]]]:
    cfg = config or DEFAULT_CONFIG
    if not cfg.data_json_path.exists():
        return {"sql": [], "api": [], "answer": []}
    payload = json.loads(cfg.data_json_path.read_text(encoding="utf-8"))
    examples = payload if isinstance(payload, list) else payload.get("examples", [])
    sql_patterns = mine_sql_patterns(examples)
    api_patterns = mine_api_patterns(examples)
    answer_patterns = mine_answer_patterns(examples)
    cfg.outputs_dir.mkdir(parents=True, exist_ok=True)
    (cfg.outputs_dir / "gold_sql_patterns.json").write_text(
        json.dumps(sql_patterns, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (cfg.outputs_dir / "gold_api_patterns.json").write_text(
        json.dumps(api_patterns, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (cfg.outputs_dir / "gold_answer_patterns.json").write_text(
        json.dumps(answer_patterns, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return {"sql": sql_patterns, "api": api_patterns, "answer": answer_patterns}


def mine_sql_patterns(examples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()
    details: dict[str, dict[str, Any]] = {}
    for example in examples:
        sql = example.get("gold_sql") or ""
        if not sql.strip():
            continue
        tables = sorted(set(re.findall(r"\b(?:FROM|JOIN)\s+([a-zA-Z_][\w$]*)", sql, flags=re.IGNORECASE)))
        joins = re.findall(r"\bJOIN\s+([a-zA-Z_][\w$]*)\s+(?:AS\s+)?([a-zA-Z_][\w$]*)?.*?\bON\b(.*?)(?=\bJOIN\b|\bWHERE\b|\bGROUP\b|\bORDER\b|\bLIMIT\b|$)", sql, flags=re.IGNORECASE | re.DOTALL)
        template = normalize_sql_template(sql)
        counter[template] += 1
        entry = details.setdefault(
            template,
            {
                "template": template,
                "tables": tables,
                "joins": [],
                "query_keywords": Counter(),
                "examples": [],
            },
        )
        entry["joins"].extend(" ".join(join).strip() for join in joins)
        entry["query_keywords"].update(keywords(example.get("query", "")))
        if len(entry["examples"]) < 3:
            entry["examples"].append({"query": example.get("query"), "sql": sql})
    return [
        {
            "template": template,
            "count": count,
            "tables": details[template]["tables"],
            "joins": sorted(set(details[template]["joins"]))[:10],
            "query_keywords": [word for word, _ in details[template]["query_keywords"].most_common(12)],
            "examples": details[template]["examples"],
        }
        for template, count in counter.most_common()
    ]


def mine_api_patterns(examples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for example in examples:
        for call in extract_api_calls(example.get("gold_api")):
            key = (call["method"], call["path"])
            entry = grouped.setdefault(
                key,
                {
                    "method": call["method"],
                    "path": call["path"],
                    "count": 0,
                    "params_counter": defaultdict(Counter),
                    "query_keywords": Counter(),
                    "examples": [],
                },
            )
            entry["count"] += 1
            for param_key, param_value in call.get("params", {}).items():
                entry["params_counter"][param_key][str(param_value)] += 1
            entry["query_keywords"].update(keywords(example.get("query", "")))
            if len(entry["examples"]) < 4:
                entry["examples"].append({"question": example.get("query"), "params": call.get("params", {})})
    patterns = []
    for entry in sorted(grouped.values(), key=lambda item: item["count"], reverse=True):
        patterns.append(
            {
                "method": entry["method"],
                "path": entry["path"],
                "count": entry["count"],
                "params": {
                    key: counter.most_common(1)[0][0]
                    for key, counter in entry["params_counter"].items()
                    if counter
                },
                "param_values": {
                    key: [{"value": value, "count": count} for value, count in counter.most_common(5)]
                    for key, counter in entry["params_counter"].items()
                },
                "query_keywords": [word for word, _ in entry["query_keywords"].most_common(15)],
                "examples": entry["examples"],
            }
        )
    return patterns


def mine_answer_patterns(examples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {}
    for example in examples:
        answer = example.get("answer") or ""
        if not answer:
            continue
        style = answer_style(answer)
        entry = buckets.setdefault(style, {"style": style, "count": 0, "query_keywords": Counter(), "examples": []})
        entry["count"] += 1
        entry["query_keywords"].update(keywords(example.get("query", "")))
        if len(entry["examples"]) < 4:
            entry["examples"].append({"query": example.get("query"), "answer_preview": answer[:300]})
    return [
        {
            "style": entry["style"],
            "count": entry["count"],
            "query_keywords": [word for word, _ in entry["query_keywords"].most_common(12)],
            "examples": entry["examples"],
        }
        for entry in sorted(buckets.values(), key=lambda item: item["count"], reverse=True)
    ]


def extract_api_calls(gold_api: Any) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    if isinstance(gold_api, str):
        parsed = parse_api_call_string(gold_api)
        return [parsed] if parsed else []
    if isinstance(gold_api, list):
        for item in gold_api:
            calls.extend(extract_api_calls(item))
    elif isinstance(gold_api, dict):
        method = gold_api.get("method")
        path = gold_api.get("path") or gold_api.get("url")
        if method and path:
            parsed = parse_api_call_string(f"{method} {path}")
            if parsed:
                calls.append(parsed)
    return calls


def normalize_sql_template(sql: str) -> str:
    text = re.sub(r"'[^']*'", "'<literal>'", sql)
    text = re.sub(r"\b[0-9a-f]{8,}(?:-[0-9a-f]{4,})*\b", "<id>", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:500]


def keywords(text: str) -> list[str]:
    stop = {"the", "all", "and", "for", "with", "that", "this", "have", "been", "show", "list", "give", "what"}
    return [word for word in re.findall(r"[a-z0-9_]+", text.lower()) if len(word) > 2 and word not in stop]


def answer_style(answer: str) -> str:
    lowered = answer.lower()
    if "no " in lowered or "not " in lowered or "zero" in lowered:
        return "no_result_or_negative"
    if any(token in lowered for token in ["count", "number", "there are", "total"]):
        return "count_summary"
    if ":" in answer or "\n" in answer or "," in answer:
        return "list_summary"
    return "direct_statement"
