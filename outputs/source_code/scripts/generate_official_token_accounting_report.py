#!/usr/bin/env python
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.token_reduction_policy import official_estimated_tokens
from dashagent.trajectory import estimate_tokens


COMPONENTS = [
    "query/original_query",
    "final_answer",
    "SQL text",
    "API call records",
    "SQL result previews",
    "API result previews",
    "evidence summaries",
    "answer diagnostics",
    "checkpoint summaries",
    "metadata notes",
    "validation results",
    "dry-run explanations",
    "other step/checkpoint payloads",
]
REDUCIBLE_COMPONENTS = {
    "SQL result previews",
    "API result previews",
    "metadata notes",
    "validation results",
    "dry-run explanations",
    "other step/checkpoint payloads",
}


def main() -> int:
    config = Config.from_env(ROOT)
    payload = generate_official_token_accounting_report(config)
    config.outputs_dir.mkdir(parents=True, exist_ok=True)
    json_path = config.outputs_dir / "official_token_accounting_report.json"
    md_path = config.outputs_dir / "official_token_accounting_report.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "rows": len(payload["rows"])}, indent=2, sort_keys=True))
    return 0


def generate_official_token_accounting_report(config: Config) -> dict[str, Any]:
    strict = _load_json(config.outputs_dir / "eval_results_strict.json")
    rows = []
    global_components: Counter[str] = Counter()
    reducible_fields: Counter[str] = Counter()
    for strict_row in strict.get("rows", []) or []:
        if strict_row.get("strategy") != "SQL_FIRST_API_VERIFY":
            continue
        trajectory = _load_trajectory(strict_row.get("output_dir"))
        if not trajectory:
            continue
        row = analyze_trajectory(strict_row, trajectory)
        rows.append(row)
        for name, value in row["component_breakdown"].items():
            global_components[name] += int(value.get("tokens", 0))
        largest = row.get("largest_reducible_component")
        if largest and largest != "none":
            reducible_fields[largest] += int(row.get("reducible_token_estimate") or 0)
    avg_official = _avg(row.get("official_estimated_tokens") for row in rows)
    expected_savings = sum(int(row.get("reducible_token_estimate") or 0) for row in rows)
    return {
        "mode": "official_token_accounting_report",
        "packaged_execution_changed": False,
        "rows": rows,
        "aggregate": {
            "row_count": len(rows),
            "average_official_estimated_tokens": avg_official,
            "total_estimated_component_tokens": sum(global_components.values()),
            "top_global_token_contributors": _top_counter(global_components, 8),
            "biggest_reducible_fields": _top_counter(reducible_fields, 8),
            "recommended_safe_reductions": [
                "compact SQL/API result preview payloads",
                "shorten metadata artifact paths in trajectory steps",
                "deduplicate repeated validation warnings",
                "keep dry-run/live labels while avoiding repeated explanatory text",
            ],
            "expected_token_savings_estimate": expected_savings,
            "packaged_execution_changed": False,
        },
    }


def analyze_trajectory(strict_row: dict[str, Any], trajectory: dict[str, Any]) -> dict[str, Any]:
    component_values: dict[str, list[Any]] = {name: [] for name in COMPONENTS}
    component_values["query/original_query"].append(trajectory.get("original_query"))
    component_values["final_answer"].append(trajectory.get("final_answer"))
    for index, step in enumerate(trajectory.get("steps", []) or []):
        _classify_step(step, component_values, f"steps[{index}]")
    for index, checkpoint in enumerate(trajectory.get("checkpoints", []) or []):
        component_values["checkpoint summaries"].append({f"checkpoints[{index}]": checkpoint})
    breakdown = {
        name: {
            "tokens": estimate_tokens(values),
            "official_counted": name not in {"answer diagnostics", "checkpoint summaries"},
            "reducible": name in REDUCIBLE_COMPONENTS,
        }
        for name, values in component_values.items()
        if values
    }
    top_components = sorted(
        ((name, value["tokens"]) for name, value in breakdown.items()),
        key=lambda item: (-item[1], item[0]),
    )
    reducible = [
        (name, value["tokens"])
        for name, value in breakdown.items()
        if value.get("reducible") and value.get("official_counted")
    ]
    largest_name, largest_tokens = max(reducible, key=lambda item: item[1], default=("none", 0))
    official = int(trajectory.get("estimated_tokens") or official_estimated_tokens(trajectory))
    formula_tokens = official_estimated_tokens(trajectory)
    return {
        "query_id": strict_row.get("query_id") or trajectory.get("query_id"),
        "query": strict_row.get("query") or trajectory.get("original_query"),
        "official_estimated_tokens": official,
        "official_formula_tokens": formula_tokens,
        "official_formula_matches": official == formula_tokens,
        "estimated_component_total": sum(value["tokens"] for value in breakdown.values()),
        "component_breakdown": breakdown,
        "top_5_token_components": [
            {"component": name, "tokens": tokens}
            for name, tokens in top_components[:5]
        ],
        "largest_reducible_component": largest_name,
        "reducible_token_estimate": int(largest_tokens * 0.35) if largest_tokens else 0,
        "non_reducible_reason": "" if largest_tokens else "largest contributors are score-critical or diagnostic-only",
    }


def render_markdown(payload: dict[str, Any]) -> str:
    aggregate = payload.get("aggregate", {})
    lines = [
        "# Official Token Accounting Report",
        "",
        f"- Packaged execution changed: {payload.get('packaged_execution_changed')}",
        f"- Rows: {aggregate.get('row_count')}",
        f"- Average official estimated tokens: {aggregate.get('average_official_estimated_tokens')}",
        f"- Expected safe savings estimate: {aggregate.get('expected_token_savings_estimate')}",
        "",
        "## Top Global Contributors",
        "",
        "| Component | Tokens |",
        "| --- | ---: |",
    ]
    for item in aggregate.get("top_global_token_contributors", []):
        lines.append(f"| {item['name']} | {item['tokens']} |")
    lines.extend(
        [
            "",
            "## Biggest Reducible Fields",
            "",
            "| Component | Estimated reducible tokens |",
            "| --- | ---: |",
        ]
    )
    for item in aggregate.get("biggest_reducible_fields", []):
        lines.append(f"| {item['name']} | {item['tokens']} |")
    lines.extend(
        [
            "",
            "## Rows",
            "",
            "| Query ID | Official tokens | Formula matches? | Largest reducible component | Reducible estimate | Top components |",
            "| --- | ---: | --- | --- | ---: | --- |",
        ]
    )
    for row in payload.get("rows", []):
        top = ", ".join(f"{item['component']}={item['tokens']}" for item in row.get("top_5_token_components", []))
        lines.append(
            f"| `{row.get('query_id')}` | {row.get('official_estimated_tokens')} | "
            f"{row.get('official_formula_matches')} | {row.get('largest_reducible_component')} | "
            f"{row.get('reducible_token_estimate')} | {top} |"
        )
    return "\n".join(lines) + "\n"


def _classify_step(step: dict[str, Any], components: dict[str, list[Any]], path: str) -> None:
    kind = step.get("kind")
    if kind == "answer_diagnostics":
        components["answer diagnostics"].append({path: step})
        return
    if kind == "metadata":
        components["metadata notes"].append({path: step})
        return
    if kind == "sql_call":
        if step.get("sql"):
            components["SQL text"].append(step.get("sql"))
        if step.get("result"):
            components["SQL result previews"].append(step.get("result"))
        if step.get("validation"):
            components["validation results"].append(step.get("validation"))
        return
    if kind == "api_call":
        components["API call records"].append({key: step.get(key) for key in ["method", "url", "params", "headers"]})
        if step.get("result"):
            components["API result previews"].append(step.get("result"))
            if (step.get("result") or {}).get("dry_run"):
                components["dry-run explanations"].append(step.get("result"))
        if step.get("validation"):
            components["validation results"].append(step.get("validation"))
        return
    if kind == "plan":
        for planned in step.get("steps", []) or []:
            if isinstance(planned, dict) and planned.get("sql"):
                components["SQL text"].append(planned.get("sql"))
            elif isinstance(planned, dict) and (planned.get("method") or planned.get("url")):
                components["API call records"].append(planned)
        other = {key: value for key, value in step.items() if key not in {"steps", "kind"}}
        if other:
            components["other step/checkpoint payloads"].append({path: other})
        return
    if kind in {"optimizer", "route", "nlp"}:
        if kind == "nlp" and step.get("value_retrieval"):
            components["evidence summaries"].append(step.get("value_retrieval"))
        components["other step/checkpoint payloads"].append({path: step})
        return
    components["other step/checkpoint payloads"].append({path: step})


def _load_trajectory(output_dir: Any) -> dict[str, Any]:
    if not output_dir:
        return {}
    path = Path(str(output_dir)) / "trajectory.json"
    return _load_json(path)


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _avg(values: Any) -> float:
    numbers = [float(value) for value in values if value is not None]
    return round(sum(numbers) / len(numbers), 4) if numbers else 0.0


def _top_counter(counter: Counter[str], limit: int) -> list[dict[str, Any]]:
    return [
        {"name": name, "tokens": tokens}
        for name, tokens in sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:limit]
    ]


if __name__ == "__main__":
    raise SystemExit(main())
