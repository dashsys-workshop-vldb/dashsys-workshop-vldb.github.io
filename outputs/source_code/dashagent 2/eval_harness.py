from __future__ import annotations

import csv
import json
import re
import time
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlparse

from .api_templates import parse_api_call_string
from .config import Config, DEFAULT_CONFIG
from .db import DuckDBDatabase
from .endpoint_catalog import normalize_api_path
from .executor import AgentExecutor
from .planner import STRATEGIES


@dataclass
class EvalExample:
    query_id: str
    query: str
    gold_sql: str | None = None
    gold_api: Any = None
    gold_answer: str | None = None


class EvalHarness:
    def __init__(
        self,
        config: Config | None = None,
        executor: AgentExecutor | None = None,
    ) -> None:
        self.config = config or DEFAULT_CONFIG
        self.config.ensure_dirs()
        self.executor = executor or AgentExecutor(self.config)

    def load_examples(self, data_json_path: Path | None = None) -> list[EvalExample]:
        path = data_json_path or self.config.data_json_path
        if not path.exists():
            return []
        payload = json.loads(path.read_text(encoding="utf-8"))
        raw_examples = find_example_list(payload)
        examples: list[EvalExample] = []
        for index, item in enumerate(raw_examples):
            if not isinstance(item, dict):
                continue
            query = item.get("question") or item.get("query") or item.get("input") or item.get("nl_query")
            if not query:
                continue
            examples.append(
                EvalExample(
                    query_id=str(item.get("id") or item.get("query_id") or f"example_{index:03d}"),
                    query=str(query),
                    gold_sql=coerce_gold_sql(item),
                    gold_api=item.get("gold_api") or item.get("api") or item.get("api_calls") or item.get("tool_calls"),
                    gold_answer=item.get("answer") or item.get("gold_answer") or item.get("expected_answer"),
                )
            )
        return examples

    def run(
        self,
        *,
        strategies: list[str] | None = None,
        examples: list[EvalExample] | None = None,
        include_live_api_metrics: bool = False,
        strict: bool = False,
    ) -> dict[str, Any]:
        strategies = strategies or STRATEGIES
        examples = examples if examples is not None else self.load_examples()
        if not examples:
            return self._write_empty_results(strategies)

        rows: list[dict[str, Any]] = []
        for example in examples:
            for strategy in strategies:
                start = time.perf_counter()
                output_dir = self.config.outputs_dir / "eval" / example.query_id / strategy.lower()
                result = self.executor.run(
                    example.query,
                    strategy=strategy,
                    query_id=example.query_id,
                    output_dir=output_dir,
                )
                elapsed = time.perf_counter() - start
                trajectory = result["trajectory"]
                generated_sql = first_generated_sql(trajectory)
                generated_api = generated_api_calls(trajectory)
                metadata_tokens, prompt_tokens = metadata_prompt_tokens(trajectory)
                if strict:
                    sql_score, sql_reason = score_sql_strict(self.executor.db, generated_sql, example.gold_sql)
                    api_score, api_reason = score_api_strict(generated_api, example.gold_api)
                    answer_score, answer_reason = score_answer_strict(result["final_answer"], example.gold_answer)
                    correctness_score, unscored_dimension_count = aggregate_strict_correctness(
                        {"sql": sql_score, "api": api_score, "answer": answer_score}
                    )
                else:
                    sql_score, sql_reason = score_sql(
                        self.executor.db,
                        generated_sql,
                        example.gold_sql,
                    )
                    api_score, api_reason = score_api(generated_api, example.gold_api)
                    answer_score, answer_reason = score_answer(result["final_answer"], example.gold_answer)
                    correctness_score = 0.4 * sql_score + 0.3 * api_score + 0.3 * answer_score
                    unscored_dimension_count = 0
                efficiency_penalty = min(
                    1.0,
                    (trajectory.get("tool_call_count", 0) / 8)
                    + (trajectory.get("runtime", elapsed) / 30)
                    + (trajectory.get("estimated_tokens", 0) / 12000),
                )
                final_score = correctness_score - 0.1 * efficiency_penalty
                rows.append(
                    {
                        "query_id": example.query_id,
                        "strategy": strategy,
                        "query": example.query,
                        "sql_score": round(sql_score, 4) if sql_score is not None else None,
                        "api_score": round(api_score, 4) if api_score is not None else None,
                        "answer_score": round(answer_score, 4) if answer_score is not None else None,
                        "correctness_score": round(correctness_score, 4),
                        "efficiency_penalty": round(efficiency_penalty, 4),
                        "final_score": round(final_score, 4),
                        "tool_call_count": trajectory.get("tool_call_count", 0),
                        "sql_call_count": trajectory.get("sql_call_count", 0),
                        "api_call_count": trajectory.get("api_call_count", 0),
                        "runtime": round(trajectory.get("runtime", elapsed), 4),
                        "estimated_tokens": trajectory.get("estimated_tokens", 0),
                        "metadata_tokens": metadata_tokens,
                        "prompt_tokens": prompt_tokens,
                        "preprocessing_time": round(trajectory.get("preprocessing_time", 0.0), 6),
                        "planning_time": round(trajectory.get("planning_time", 0.0), 6),
                        "execution_time": round(trajectory.get("execution_time", 0.0), 6),
                        "answer_time": round(trajectory.get("answer_time", 0.0), 6),
                        "error_count": len(trajectory.get("errors", [])),
                        "validation_failures": count_validation_failures(trajectory),
                        "sql_reason": sql_reason,
                        "api_reason": api_reason,
                        "answer_reason": answer_reason,
                        "unscored_dimension_count": unscored_dimension_count,
                        "output_dir": result["output_dir"],
                    }
                )
        summary = summarize_rows(rows, strategies)
        payload = {"examples": len(examples), "strategies": strategies, "rows": rows, "summary": summary, "strict": strict}
        if include_live_api_metrics:
            payload["live_api_metrics"] = compute_live_api_metrics(rows)
        self._write_outputs(payload, strict=strict)
        return payload

    def _write_empty_results(self, strategies: list[str]) -> dict[str, Any]:
        payload = {
            "examples": 0,
            "strategies": strategies,
            "rows": [],
            "summary": {
                "message": "No public examples found. Place data/data.json to run the dev evaluation.",
                "best_correctness": None,
                "best_efficiency": None,
                "best_overall": None,
            },
        }
        if strategies:
            payload["live_api_metrics"] = {
                "planned_api_score": 0.0,
                "live_api_success_rate": 0.0,
                "live_api_empty_response_rate": 0.0,
                "live_api_error_rate": 0.0,
                "dry_run_vs_live_discrepancies": {"dry_run_calls": 0, "live_calls": 0},
                "note": "No examples were available.",
            }
        self._write_outputs(payload)
        return payload

    def _write_outputs(self, payload: dict[str, Any], *, strict: bool = False) -> None:
        self.config.outputs_dir.mkdir(parents=True, exist_ok=True)
        suffix = "_strict" if strict else ""
        (self.config.outputs_dir / f"eval_results{suffix}.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True, default=str),
            encoding="utf-8",
        )
        csv_path = self.config.outputs_dir / f"eval_results{suffix}.csv"
        rows = payload.get("rows", [])
        with csv_path.open("w", encoding="utf-8", newline="") as handle:
            if rows:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            else:
                writer = csv.DictWriter(handle, fieldnames=["message"])
                writer.writeheader()
                writer.writerow({"message": payload["summary"]["message"]})
        (self.config.outputs_dir / f"strategy_comparison{suffix}.md").write_text(
            render_strategy_comparison(payload),
            encoding="utf-8",
        )


def find_example_list(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ["examples", "data", "queries", "dev", "public_examples"]:
            value = payload.get(key)
            if isinstance(value, list):
                return value
        dict_values = [value for value in payload.values() if isinstance(value, dict)]
        if dict_values and all(("query" in item or "question" in item) for item in dict_values):
            return dict_values
    return []


def coerce_gold_sql(item: dict[str, Any]) -> str | None:
    value = item.get("gold_sql") or item.get("sql") or item.get("expected_sql")
    if isinstance(value, list):
        return str(value[0]) if value else None
    return str(value) if value else None


def normalize_sql(sql: str | None) -> str:
    if not sql:
        return ""
    return " ".join(sql.strip().rstrip(";").replace('"', "").lower().split())


def first_generated_sql(trajectory: dict[str, Any]) -> str | None:
    for step in trajectory.get("steps", []):
        if step.get("kind") == "sql_call":
            return step.get("sql")
    return None


def generated_api_calls(trajectory: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "method": str(step.get("method", "")).upper(),
            "path": normalize_api_path(step.get("url", "")),
            "params": step.get("params", {}),
        }
        for step in trajectory.get("steps", [])
        if step.get("kind") == "api_call"
    ]


def score_sql(db: DuckDBDatabase, generated_sql: str | None, gold_sql: str | None) -> tuple[float, str]:
    if not gold_sql:
        return (1.0, "No gold SQL supplied; SQL dimension treated as unscored/pass.")
    if not generated_sql:
        return (0.0, "No generated SQL.")
    if normalize_sql(generated_sql) == normalize_sql(gold_sql):
        return (1.0, "Normalized exact SQL match.")
    generated_result = db.execute_sql(generated_sql)
    gold_result = db.execute_sql(gold_sql)
    if generated_result.get("ok") and gold_result.get("ok") and generated_result.get("rows") == gold_result.get("rows"):
        return (0.9, "Semantic result match.")
    return (0.0, "SQL mismatch.")


def extract_api_calls(gold_api: Any) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    def walk(obj: Any) -> None:
        if isinstance(obj, str):
            parsed = parse_api_call_string(obj)
            if parsed:
                calls.append(parsed)
        elif isinstance(obj, dict):
            method = obj.get("method") or obj.get("http_method")
            path = obj.get("path") or obj.get("url") or obj.get("endpoint")
            if method and path:
                params = dict(obj.get("params", {}) or {})
                parsed_url = urlparse(str(path))
                params.update(dict(parse_qsl(parsed_url.query, keep_blank_values=True)))
                body = obj.get("body")
                if isinstance(body, dict):
                    params.update(body)
                calls.append(
                    {
                        "method": str(method).upper(),
                        "path": normalize_api_path(parsed_url.path or str(path)),
                        "params": params,
                    }
                )
            for value in obj.values():
                walk(value)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(gold_api)
    return calls


def score_api(generated_calls: list[dict[str, Any]], gold_api: Any) -> tuple[float, str]:
    gold_calls = extract_api_calls(gold_api)
    if not gold_calls:
        return (1.0, "No gold API supplied; API dimension treated as unscored/pass.")
    if not generated_calls:
        return (0.0, "No generated API call.")

    pair_scores = []
    for index, gold in enumerate(gold_calls):
        candidates = []
        for generated_index, generated in enumerate(generated_calls):
            method_path = method_path_score(generated, gold)
            params = param_score(generated.get("params", {}), gold.get("params", {}))
            order_bonus = 1.0 if generated_index == index else 0.5
            candidates.append(0.4 * method_path + 0.4 * params + 0.2 * order_bonus)
        pair_scores.append(max(candidates) if candidates else 0.0)
    call_count_score = 1.0 if len(generated_calls) == len(gold_calls) else max(0.0, 1.0 - abs(len(generated_calls) - len(gold_calls)) / max(len(gold_calls), 1))
    score = 0.8 * (sum(pair_scores) / len(gold_calls)) + 0.2 * call_count_score
    return (round(score, 4), f"API method/path, params, and call-count score: {score:.4f}.")


def method_path_score(generated: dict[str, Any], gold: dict[str, Any]) -> float:
    method_match = str(generated.get("method", "")).upper() == str(gold.get("method", "")).upper()
    generated_path = normalize_api_path(str(generated.get("path", ""))).lower()
    gold_path = normalize_api_path(str(gold.get("path", ""))).lower()
    if generated_path == gold_path:
        path_match = 1.0
    elif path_shape(generated_path) == path_shape(gold_path):
        path_match = 0.75
    else:
        path_match = 0.0
    return (0.5 if method_match else 0.0) + 0.5 * path_match


def path_shape(path: str) -> str:
    return re.sub(r"/[0-9a-f]{8,}(?:-[0-9a-f]{4,})*", "/{id}", path.lower())


def param_score(generated_params: Any, gold_params: Any) -> float:
    generated = normalize_params(generated_params)
    gold = normalize_params(gold_params)
    if not gold:
        return 1.0 if not generated else 0.8
    if not generated:
        return 0.0
    scores = []
    for key, gold_value in gold.items():
        generated_key = next((candidate for candidate in generated if normalize_param_key(candidate) == normalize_param_key(key)), None)
        if generated_key is None:
            scores.append(0.0)
            continue
        key_score = 0.4
        value_score = 0.6 * param_value_similarity(generated[generated_key], gold_value)
        scores.append(key_score + value_score)
    extra_penalty = max(0, len(generated) - len(gold)) * 0.03
    return max(0.0, min(1.0, sum(scores) / len(scores) - extra_penalty))


def normalize_params(params: Any) -> dict[str, Any]:
    if params is None:
        return {}
    if isinstance(params, str):
        parsed = parse_api_call_string("GET /x?" + params.lstrip("?"))
        return parsed["params"] if parsed else {}
    if isinstance(params, dict):
        return params
    return {}


def normalize_param_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(key).lower())


def normalize_param_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    text = str(value).strip().strip('"')
    text = re.sub(r"\s*(==|!=|=|eq|:)\s*", r"\1", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text)
    return text.lower()


def param_value_similarity(generated_value: Any, gold_value: Any) -> float:
    generated = normalize_param_value(generated_value)
    gold = normalize_param_value(gold_value)
    if generated == gold:
        return 1.0
    if generated in gold or gold in generated:
        return 0.75
    generated_tokens = set(re.findall(r"[a-z0-9_<>.-]+", generated))
    gold_tokens = set(re.findall(r"[a-z0-9_<>.-]+", gold))
    if generated_tokens and gold_tokens:
        overlap = len(generated_tokens & gold_tokens) / len(gold_tokens)
        if overlap:
            return min(0.7, overlap)
    return SequenceMatcher(None, generated, gold).ratio() * 0.6


def score_answer(generated_answer: str, gold_answer: str | None) -> tuple[float, str]:
    if not gold_answer:
        return (1.0, "No gold answer supplied; answer dimension treated as unscored/pass.")
    generated = generated_answer.lower().strip()
    gold = gold_answer.lower().strip()
    if generated == gold:
        return (1.0, "Exact answer match.")
    if gold in generated or generated in gold:
        return (0.85, "Substring answer match.")
    try:
        from rapidfuzz.fuzz import ratio  # type: ignore

        score = ratio(generated, gold) / 100
    except Exception:
        score = SequenceMatcher(None, generated, gold).ratio()
    return (score, "Fuzzy answer similarity.")


def score_sql_strict(db: DuckDBDatabase, generated_sql: str | None, gold_sql: str | None) -> tuple[float | None, str]:
    if not gold_sql:
        return (None, "No gold SQL supplied; SQL dimension unscored in strict mode.")
    if not generated_sql:
        return (0.0, "No generated SQL while gold SQL exists.")
    if normalize_sql(generated_sql) == normalize_sql(gold_sql):
        return (1.0, "Normalized exact SQL match.")
    generated_result = db.execute_sql(generated_sql)
    gold_result = db.execute_sql(gold_sql)
    if generated_result.get("ok") and gold_result.get("ok") and generated_result.get("rows") == gold_result.get("rows"):
        return (0.9, "Strict semantic result match.")
    return (0.0, "Strict SQL mismatch.")


def score_api_strict(generated_calls: list[dict[str, Any]], gold_api: Any) -> tuple[float | None, str]:
    gold_calls = extract_api_calls(gold_api)
    if not gold_calls:
        return (None, "No gold API supplied; API dimension unscored in strict mode.")
    if not generated_calls:
        return (0.0, "No generated API call while gold API exists.")
    pair_scores = []
    used_generated: set[int] = set()
    for gold in gold_calls:
        best_score = 0.0
        best_index = -1
        for index, generated in enumerate(generated_calls):
            method_match = str(generated.get("method", "")).upper() == str(gold.get("method", "")).upper()
            path_match = normalize_api_path(str(generated.get("path", ""))).lower() == normalize_api_path(str(gold.get("path", ""))).lower()
            params = strict_param_score(generated.get("params", {}), gold.get("params", {}))
            score = (0.35 if method_match else 0.0) + (0.45 if path_match else 0.0) + (0.2 * params)
            if score > best_score:
                best_score = score
                best_index = index
        pair_scores.append(best_score)
        if best_index >= 0:
            used_generated.add(best_index)
    call_count_penalty = max(0.0, 1.0 - abs(len(generated_calls) - len(gold_calls)) / max(len(gold_calls), 1))
    score = 0.85 * (sum(pair_scores) / len(gold_calls)) + 0.15 * call_count_penalty
    return (round(score, 4), f"Strict API method/path/required-param/call-count score: {score:.4f}.")


def strict_param_score(generated_params: Any, gold_params: Any) -> float:
    generated = normalize_params(generated_params)
    gold = normalize_params(gold_params)
    if not gold:
        return 1.0
    if not generated:
        return 0.0
    matches = 0
    for key, gold_value in gold.items():
        generated_key = next((candidate for candidate in generated if normalize_param_key(candidate) == normalize_param_key(key)), None)
        if generated_key is None:
            continue
        if param_value_similarity(generated[generated_key], gold_value) >= 0.9:
            matches += 1
    return matches / len(gold)


def score_answer_strict(generated_answer: str, gold_answer: str | None) -> tuple[float | None, str]:
    if not gold_answer:
        return (None, "No gold answer supplied; answer dimension unscored in strict mode.")
    generated = generated_answer.lower().strip()
    gold = gold_answer.lower().strip()
    if generated == gold:
        return (1.0, "Exact answer match.")
    if gold in generated or generated in gold:
        return (0.85, "Substring answer match capped at 0.85.")
    score = 0.0
    generated_numbers = set(re.findall(r"-?\d+(?:\.\d+)?", generated))
    gold_numbers = set(re.findall(r"-?\d+(?:\.\d+)?", gold))
    if gold_numbers:
        score += 0.25 * (len(generated_numbers & gold_numbers) / len(gold_numbers))
    generated_dates = set(re.findall(r"\b20\d{2}-\d{2}-\d{2}\b", generated))
    gold_dates = set(re.findall(r"\b20\d{2}-\d{2}-\d{2}\b", gold))
    if gold_dates:
        score += 0.2 * (len(generated_dates & gold_dates) / len(gold_dates))
    status_words = {"published", "draft", "active", "inactive", "failed", "succeeded", "not", "no", "yes", "null", "unavailable"}
    gold_status = {word for word in status_words if word in gold}
    generated_status = {word for word in status_words if word in generated}
    if gold_status:
        score += 0.25 * (len(generated_status & gold_status) / len(gold_status))
    generated_tokens = set(re.findall(r"[a-z0-9_]+", generated)) - status_words
    gold_tokens = set(re.findall(r"[a-z0-9_]+", gold)) - status_words
    if gold_tokens:
        score += 0.05 * (len(generated_tokens & gold_tokens) / len(gold_tokens))
    try:
        from rapidfuzz.fuzz import ratio  # type: ignore

        fuzzy = ratio(generated, gold) / 100
    except Exception:
        fuzzy = SequenceMatcher(None, generated, gold).ratio()
    score += min(0.25, 0.25 * fuzzy)
    return (round(min(score, 0.85), 4), "Strict answer score from required facts plus capped fuzzy similarity.")


def aggregate_strict_correctness(scores: dict[str, float | None]) -> tuple[float, int]:
    weights = {"sql": 0.4, "api": 0.3, "answer": 0.3}
    scored = {key: value for key, value in scores.items() if value is not None}
    if not scored:
        return 0.0, len(scores)
    weight_sum = sum(weights[key] for key in scored)
    correctness = sum((scores[key] or 0.0) * weights[key] for key in scored) / weight_sum
    return correctness, len(scores) - len(scored)


def count_validation_failures(trajectory: dict[str, Any]) -> int:
    failures = 0
    for step in trajectory.get("steps", []):
        validation = step.get("validation") or step.get("result")
        if isinstance(validation, dict) and validation.get("ok") is False:
            failures += 1
    return failures


def metadata_prompt_tokens(trajectory: dict[str, Any]) -> tuple[int, int]:
    for step in trajectory.get("steps", []):
        if step.get("kind") == "metadata":
            return int(step.get("estimated_tokens", 0)), int(step.get("prompt_tokens", 0))
    return 0, 0


def compute_live_api_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    api_rows = [row for row in rows if int(row.get("api_call_count", 0)) > 0]
    planned_api_score = avg(float(row.get("api_score", 0)) for row in api_rows) if api_rows else 0.0
    api_calls = []
    for row in rows:
        output_dir = row.get("output_dir")
        if not output_dir:
            continue
        path = Path(output_dir) / "trajectory.json"
        if not path.exists():
            continue
        try:
            trajectory = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        for step in trajectory.get("steps", []):
            if step.get("kind") == "api_call":
                result = step.get("result", {})
                api_calls.append(result)
    live_calls = [result for result in api_calls if not result.get("dry_run")]
    dry_run_calls = [result for result in api_calls if result.get("dry_run")]
    success = [result for result in live_calls if result.get("ok")]
    empty = [
        result
        for result in success
        if result.get("result_preview") in (None, "", [], {})
    ]
    error = [result for result in live_calls if not result.get("ok")]
    denom = len(live_calls) or 1
    return {
        "planned_api_score": planned_api_score,
        "live_api_success_rate": round(len(success) / denom, 4) if live_calls else 0.0,
        "live_api_empty_response_rate": round(len(empty) / denom, 4) if live_calls else 0.0,
        "live_api_error_rate": round(len(error) / denom, 4) if live_calls else 0.0,
        "dry_run_vs_live_discrepancies": {
            "dry_run_calls": len(dry_run_calls),
            "live_calls": len(live_calls),
            "total_api_calls": len(api_calls),
        },
        "note": "No live API calls were executed; credentials are missing or dry-run mode was used." if not live_calls else "",
    }


def summarize_rows(rows: list[dict[str, Any]], strategies: list[str]) -> dict[str, Any]:
    by_strategy: dict[str, dict[str, Any]] = {}
    for strategy in strategies:
        strategy_rows = [row for row in rows if row["strategy"] == strategy]
        if not strategy_rows:
            continue
        by_strategy[strategy] = {
            "avg_sql_score": avg(row["sql_score"] for row in strategy_rows),
            "avg_api_score": avg(row["api_score"] for row in strategy_rows),
            "avg_answer_score": avg(row["answer_score"] for row in strategy_rows),
            "avg_correctness_score": avg(row["correctness_score"] for row in strategy_rows),
            "avg_tool_call_count": avg(row["tool_call_count"] for row in strategy_rows),
            "avg_runtime": avg(row["runtime"] for row in strategy_rows),
            "avg_estimated_tokens": avg(row["estimated_tokens"] for row in strategy_rows),
            "avg_metadata_tokens": avg(row.get("metadata_tokens", 0) for row in strategy_rows),
            "avg_prompt_tokens": avg(row.get("prompt_tokens", 0) for row in strategy_rows),
            "avg_preprocessing_time": avg(row.get("preprocessing_time", 0) for row in strategy_rows),
            "avg_planning_time": avg(row.get("planning_time", 0) for row in strategy_rows),
            "avg_execution_time": avg(row.get("execution_time", 0) for row in strategy_rows),
            "avg_answer_time": avg(row.get("answer_time", 0) for row in strategy_rows),
            "avg_final_score": avg(row["final_score"] for row in strategy_rows),
        }
    if not by_strategy:
        return {}
    best_correctness = max(by_strategy, key=lambda strategy: by_strategy[strategy]["avg_correctness_score"])
    best_efficiency = min(
        by_strategy,
        key=lambda strategy: (
            by_strategy[strategy]["avg_tool_call_count"],
            by_strategy[strategy]["avg_runtime"],
            by_strategy[strategy]["avg_estimated_tokens"],
        ),
    )
    best_overall = max(by_strategy, key=lambda strategy: by_strategy[strategy]["avg_final_score"])
    return {
        "by_strategy": by_strategy,
        "best_correctness": best_correctness,
        "best_efficiency": best_efficiency,
        "best_overall": best_overall,
        "recommended_next_focus": recommend_next_focus(best_overall),
    }


def avg(values: Any) -> float:
    values = [value for value in values if value is not None]
    return round(sum(values) / len(values), 4) if values else 0.0


def fmt_score(value: Any, digits: int = 4) -> str:
    if value is None:
        return "unscored"
    try:
        return f"{float(value):.{digits}f}"
    except Exception:
        return str(value)


def recommend_next_focus(best_overall: str) -> list[str]:
    if best_overall == "TEMPLATE_FIRST":
        return [
            "Keep template coverage but add guardrails to avoid overfitting public examples.",
            "Back every template with schema-derived column/table checks.",
        ]
    if best_overall == "SQL_FIRST_API_VERIFY":
        return [
            "Improve entity extraction and join-template coverage.",
            "Add endpoint-specific param selection from observed gold API patterns.",
        ]
    return [
        "Inspect failed examples and add deterministic routing/schema selection rules before adding agent complexity.",
    ]


def render_strategy_comparison(payload: dict[str, Any]) -> str:
    if payload.get("examples", 0) == 0:
        return (
            "# Strategy Comparison\n\n"
            "No public examples were evaluated because `data/data.json` is missing.\n\n"
            "Place the official public examples at `data/data.json` and rerun:\n\n"
            "```bash\npython scripts/run_dev_eval.py\n```\n"
        )
    summary = payload["summary"]
    lines = [
        "# Strategy Comparison",
        "",
        "| Strategy | Correctness | Final score | Tool calls | Runtime (s) | Tokens |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for strategy, metrics in summary.get("by_strategy", {}).items():
        lines.append(
            "| {strategy} | {correctness} | {final} | {tools:.2f} | {runtime:.4f} | {tokens:.0f} |".format(
                strategy=strategy,
                correctness=fmt_score(metrics["avg_correctness_score"]),
                final=fmt_score(metrics["avg_final_score"]),
                tools=metrics["avg_tool_call_count"],
                runtime=metrics["avg_runtime"],
                tokens=metrics["avg_estimated_tokens"],
            )
        )
    lines.extend(
        [
            "",
            f"- Best correctness: `{summary.get('best_correctness')}`",
            f"- Best efficiency: `{summary.get('best_efficiency')}`",
            f"- Best overall: `{summary.get('best_overall')}`",
            "",
            "## Token Context",
            "",
            "| Strategy | Metadata tokens | Prompt tokens | Preprocess (s) | Planning (s) | Execution (s) | Answer (s) |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for strategy, metrics in summary.get("by_strategy", {}).items():
        lines.append(
            "| {strategy} | {metadata:.0f} | {prompt:.0f} | {pre:.5f} | {planning:.5f} | {execution:.5f} | {answer:.5f} |".format(
                strategy=strategy,
                metadata=metrics.get("avg_metadata_tokens", 0),
                prompt=metrics.get("avg_prompt_tokens", 0),
                pre=metrics.get("avg_preprocessing_time", 0),
                planning=metrics.get("avg_planning_time", 0),
                execution=metrics.get("avg_execution_time", 0),
                answer=metrics.get("avg_answer_time", 0),
            )
        )
    lines.extend(
        [
            "",
            "## Recommended Next Focus",
        ]
    )
    for item in summary.get("recommended_next_focus", []):
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)
