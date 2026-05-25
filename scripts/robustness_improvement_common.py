from __future__ import annotations

import json
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Iterable

from dashagent.config import Config
from dashagent.trajectory import redact_secrets


ROOT = Path(__file__).resolve().parents[1]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def reports_dir(config: Config) -> Path:
    path = config.outputs_dir / "reports"
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def load_rows(config: Config) -> list[dict[str, Any]]:
    payload = load_json(reports_dir(config) / "full_generated_prompt_suite_diagnostic.json")
    rows = payload.get("rows")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def write_report(config: Config, stem: str, payload: dict[str, Any], markdown: str) -> dict[str, Any]:
    safe_payload = redact_secrets(payload)
    directory = reports_dir(config)
    json_path = directory / f"{stem}.json"
    md_path = directory / f"{stem}.md"
    json_path.write_text(json.dumps(safe_payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(redact_secrets(markdown), encoding="utf-8")
    return safe_payload


def counter_dict(values: Iterable[Any]) -> dict[str, int]:
    return dict(Counter(str(value) for value in values if value not in (None, "", [], {})).most_common())


def top_examples(rows: list[dict[str, Any]], *, limit: int = 10) -> list[dict[str, Any]]:
    examples: list[dict[str, Any]] = []
    for row in rows[:limit]:
        examples.append(
            {
                "prompt_id": row.get("prompt_id"),
                "prompt": row.get("prompt"),
                "generation_type": row.get("generation_type"),
                "domain_family": row.get("domain_family"),
                "route_type": row.get("route_type"),
                "domain_type": row.get("domain_type"),
                "answer_intent": row.get("answer_intent"),
                "actual_answer_intent": row.get("actual_answer_intent"),
                "template_hit": row.get("template_hit"),
                "sql_calls": row.get("sql_calls"),
                "api_calls": row.get("api_calls"),
                "endpoint_selected": row.get("endpoint_selected"),
                "api_outcomes": row.get("api_outcomes"),
                "final_answer_excerpt": excerpt(row.get("final_answer")),
                "unsupported_claim_count": row.get("unsupported_claim_count"),
            }
        )
    return examples


def excerpt(value: Any, limit: int = 240) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)] + "..."


def generated_summary(config: Config) -> dict[str, Any]:
    payload = load_json(reports_dir(config) / "full_generated_prompt_suite_diagnostic.json")
    return {
        "total_prompts": payload.get("total_prompts"),
        "executed_prompts": payload.get("executed_prompts"),
        "runtime_pass_count": payload.get("runtime_pass_count"),
        "runtime_fail_count": payload.get("runtime_fail_count"),
        "validation_fail_count": payload.get("validation_fail_count"),
        "unsupported_claim_count": payload.get("unsupported_claim_count"),
        "live_api_calls": payload.get("live_api_calls"),
        "live_success_count": payload.get("live_success_count"),
        "live_empty_count": payload.get("live_empty_count"),
        "api_error_count": payload.get("api_error_count"),
        "top_failure_categories": payload.get("top_failure_categories"),
    }


def strict_score(config: Config) -> float | None:
    strict = load_json(config.outputs_dir / "eval_results_strict.json")
    value = (
        strict.get("summary", {})
        .get("by_strategy", {})
        .get("SQL_FIRST_API_VERIFY", {})
        .get("avg_final_score")
    )
    return float(value) if isinstance(value, (int, float)) else None


def strict_metrics(config: Config) -> dict[str, Any]:
    strict = load_json(config.outputs_dir / "eval_results_strict.json")
    return (
        strict.get("summary", {})
        .get("by_strategy", {})
        .get("SQL_FIRST_API_VERIFY", {})
    )


def hidden_summary(config: Config) -> dict[str, Any]:
    hidden = load_json(config.outputs_dir / "hidden_style_eval.json")
    summary = hidden.get("summary") if isinstance(hidden.get("summary"), dict) else {}
    return {
        "passed_cases": summary.get("passed_cases"),
        "total_cases": summary.get("total_cases"),
        "failed_cases": summary.get("failed_cases"),
        "family_stability_rate": summary.get("family_stability_rate"),
        "schema_stability_rate": summary.get("schema_stability_rate"),
    }


def endpoint_matrix(config: Config) -> dict[str, Any]:
    smoke = load_json(reports_dir(config) / "live_api_readiness_smoke.json")
    return {
        "attempted": smoke.get("endpoints_attempted") or smoke.get("endpoints_tested"),
        "success_count": smoke.get("success_count") or smoke.get("endpoints_success"),
        "live_empty_count": smoke.get("endpoints_empty"),
        "failure_count": smoke.get("failure_count"),
        "outcome_counts": smoke.get("outcome_counts") or {},
        "status": smoke.get("status"),
    }


def robustness_metrics(config: Config) -> dict[str, Any]:
    payload = load_json(reports_dir(config) / "nl_sql_robustness_audit.json")
    return payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {}


def git_status_short() -> str:
    try:
        return subprocess.check_output(["git", "status", "--short"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "unavailable"


def git_branch() -> str:
    try:
        return subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "unavailable"


def mean_number(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [row.get(key) for row in rows if isinstance(row.get(key), (int, float))]
    return round(float(mean(values)), 4) if values else None


def group_by(rows: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(key) or "unknown")].append(row)
    return dict(grouped)


def render_key_values(title: str, mapping: dict[str, Any]) -> list[str]:
    lines = [f"## {title}", ""]
    for key, value in mapping.items():
        lines.append(f"- `{key}`: `{value}`")
    lines.append("")
    return lines
