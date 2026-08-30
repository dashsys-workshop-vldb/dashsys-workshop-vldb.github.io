#!/usr/bin/env python
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.trajectory import redact_secrets


REPORT_STEM = "deterministic_prompt_type_audit"

INTENTS = {
    "count",
    "list/name/id",
    "status",
    "timestamp/date/when",
    "yes/no",
    "compare",
    "explain",
    "unknown/ambiguous",
}

DOMAIN_BUCKETS = {
    "journey_campaign",
    "segment_audience",
    "destination_dataflow",
    "dataset_schema",
    "property_field",
    "dataflow_run",
    "count_aggregation",
    "status_monitoring",
    "unknown",
}


def main() -> int:
    config = Config.from_env(ROOT)
    payload = run_deterministic_prompt_type_audit(config)
    print(
        json.dumps(
            {
                "json": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.json"),
                "markdown": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.md"),
                "official_rows": payload.get("official_row_count"),
                "generated_prompts": payload.get("generated_prompt_count"),
                "bucket_count": len(payload.get("buckets", [])),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def run_deterministic_prompt_type_audit(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    official_source = _load_json(reports_dir / "official_row_failure_table.json")
    generated_source = _load_json(reports_dir / "generated_prompt_failure_table.json")
    strict = _load_json(config.outputs_dir / "eval_results_strict.json")

    official_rows = [_official_taxonomy(row) for row in (official_source.get("rows") or []) if isinstance(row, dict)]
    generated_rows = [_generated_taxonomy(row) for row in (generated_source.get("rows") or []) if isinstance(row, dict)]
    buckets = _build_buckets(official_rows, generated_rows)
    payload = {
        "report_type": REPORT_STEM,
        "generated_at": _now(),
        "diagnostic_only": True,
        "official_score_claim": False,
        "runtime_change_applied": False,
        "packaged_strategy": "SQL_FIRST_API_VERIFY",
        "strict_score": _strict_score(strict, official_rows),
        "official_row_count": len(official_rows),
        "generated_prompt_count": len(generated_rows),
        "generated_prompts_used_for": "generality_and_speed_evidence_only",
        "taxonomy_dimensions": {
            "prompt_intents": sorted(INTENTS),
            "domains": sorted(DOMAIN_BUCKETS),
            "execution_needs": [
                "sql_only_possible",
                "sql_then_api_optional",
                "api_required",
                "live_api_required",
                "dry_run_only_currently",
                "no_local_evidence",
            ],
            "evidence_shapes": [
                "SQL count available",
                "SQL names/IDs available",
                "SQL status available",
                "SQL timestamp available",
                "SQL zero rows",
                "API dry-run only",
                "API error/caveat only",
            ],
        },
        "official_rows": official_rows,
        "generated_prompt_rows": generated_rows,
        "buckets": buckets,
        "summary": {
            "bucket_count": len(buckets),
            "fast_path_possible_buckets": sum(1 for bucket in buckets if bucket["deterministic_fast_path_possible"]),
            "api_unnecessary_candidate_buckets": sum(1 for bucket in buckets if bucket["api_unnecessary"]),
            "llm_unnecessary_buckets": sum(1 for bucket in buckets if bucket["llm_unnecessary"]),
        },
        "safety": {
            "generated_prompts_diagnostic_only": True,
            "runtime_change_allowed": False,
            "final_submission_changed": False,
            "env_local_accessed": False,
            "credentials_accessed": False,
        },
        "source_reports": [
            "outputs/eval_results_strict.json",
            "outputs/reports/official_row_failure_table.json",
            "outputs/reports/generated_prompt_failure_table.json",
            "outputs/reports/cross_dataset_failure_clusters.json",
            "outputs/reports/general_deterministic_rule_candidates.json",
            "outputs/reports/generated_prompt_suite_local_diagnostic.json",
        ],
    }
    payload = _redact(payload)
    _write_json(reports_dir / f"{REPORT_STEM}.json", payload)
    (reports_dir / f"{REPORT_STEM}.md").write_text(_render_audit(payload), encoding="utf-8")
    return payload


def _official_taxonomy(row: dict[str, Any]) -> dict[str, Any]:
    evidence_shape = _evidence_shape(
        fields=row.get("sql_evidence_fields") or [],
        row_count=row.get("sql_returned_row_count"),
        api_state=row.get("api_state"),
    )
    execution_need = _execution_need(
        route=row.get("predicted_route"),
        requires_live=bool(row.get("requires_live_api")),
        sql_calls=int(row.get("sql_calls") or 0),
        api_calls=int(row.get("api_calls") or 0),
        api_state=row.get("api_state"),
        evidence_shape=evidence_shape,
    )
    intent = _intent_bucket(row.get("answer_intent") or row.get("prompt"))
    domain = _domain_bucket(row.get("predicted_domain") or row.get("prompt"))
    return {
        "source_type": "official",
        "row_id": row.get("row_id") or row.get("example_id"),
        "prompt": row.get("prompt"),
        "prompt_intent": intent,
        "domain_bucket": domain,
        "execution_need": execution_need,
        "evidence_shape": evidence_shape,
        "current_route": row.get("predicted_route"),
        "current_answer_family": _answer_family(row),
        "strict_score": row.get("total_strict_score"),
        "answer_score": row.get("answer_score"),
        "sql_score": row.get("sql_score"),
        "api_score": row.get("api_score"),
        "tool_calls": int(row.get("sql_calls") or 0) + int(row.get("api_calls") or 0),
        "api_calls": int(row.get("api_calls") or 0),
        "common_failure_patterns": _failure_patterns(row),
        "llm_unnecessary": True,
        "api_unnecessary": _api_unnecessary(execution_need, row.get("api_state")),
        "deterministic_fast_path_possible": _fast_path_possible(intent, execution_need, evidence_shape, row),
        "risk_level": _risk_level(execution_need, row.get("total_strict_score"), row.get("failure_classification") or {}),
    }


def _generated_taxonomy(row: dict[str, Any]) -> dict[str, Any]:
    fields = (row.get("sql_result_shape") or {}).get("fields") or []
    evidence_shape = _evidence_shape(
        fields=fields,
        row_count=row.get("sql_row_count"),
        api_state=row.get("api_state"),
        zero_row=bool(row.get("zero_row_sql") or (row.get("sql_result_shape") or {}).get("zero_row")),
    )
    execution_need = _execution_need(
        route=row.get("actual_route"),
        requires_live=bool(row.get("requires_live_api")),
        sql_calls=int(row.get("sql_calls") or 0),
        api_calls=int(row.get("dry_run_api_calls") or 0),
        api_state=row.get("api_state"),
        evidence_shape=evidence_shape,
    )
    intent = _intent_bucket(row.get("actual_answer_intent") or row.get("expected_intent") or row.get("prompt"))
    domain = _domain_bucket(row.get("actual_domain") or row.get("expected_domain") or row.get("prompt"))
    return {
        "source_type": "generated_prompt",
        "prompt_id": row.get("prompt_id"),
        "prompt": row.get("prompt"),
        "prompt_intent": intent,
        "domain_bucket": domain,
        "execution_need": execution_need,
        "evidence_shape": evidence_shape,
        "current_route": row.get("actual_route"),
        "current_answer_family": row.get("answer_family"),
        "diagnostic_issue_type": row.get("likely_issue_type"),
        "route_mismatch": bool(row.get("route_mismatch")),
        "domain_mismatch": bool(row.get("domain_mismatch")),
        "answer_intent_mismatch": bool(row.get("answer_intent_mismatch")),
        "llm_unnecessary": True,
        "api_unnecessary": _api_unnecessary(execution_need, row.get("api_state")),
        "deterministic_fast_path_possible": _generated_fast_path_possible(row, intent, execution_need, evidence_shape),
        "risk_level": "medium" if row.get("route_mismatch") or row.get("domain_mismatch") else "low",
        "diagnostic_only": True,
        "generated_prompt_usage": "generality_and_speed_evidence_only",
    }


def _build_buckets(official_rows: list[dict[str, Any]], generated_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in official_rows + generated_rows:
        key = (row["prompt_intent"], row["domain_bucket"], row["execution_need"])
        bucket = grouped.setdefault(
            key,
            {
                "bucket_id": _bucket_id(*key),
                "prompt_intent": key[0],
                "domain_bucket": key[1],
                "execution_need": key[2],
                "official_rows": [],
                "generated_prompts": [],
                "official_scores": [],
                "route_distribution": Counter(),
                "answer_family_distribution": Counter(),
                "failure_distribution": Counter(),
                "evidence_shape_distribution": Counter(),
                "llm_unnecessary": True,
                "api_unnecessary": False,
                "deterministic_fast_path_possible": False,
                "risk_level": "low",
            },
        )
        bucket["route_distribution"][row.get("current_route") or "unknown"] += 1
        bucket["answer_family_distribution"][row.get("current_answer_family") or "unknown"] += 1
        for shape in row.get("evidence_shape") or []:
            bucket["evidence_shape_distribution"][shape] += 1
        bucket["api_unnecessary"] = bool(bucket["api_unnecessary"] or row.get("api_unnecessary"))
        bucket["deterministic_fast_path_possible"] = bool(bucket["deterministic_fast_path_possible"] or row.get("deterministic_fast_path_possible"))
        if row.get("risk_level") == "high":
            bucket["risk_level"] = "high"
        elif row.get("risk_level") == "medium" and bucket["risk_level"] != "high":
            bucket["risk_level"] = "medium"
        if row["source_type"] == "official":
            bucket["official_rows"].append(row.get("row_id"))
            if isinstance(row.get("strict_score"), (int, float)):
                bucket["official_scores"].append(float(row["strict_score"]))
            for pattern in row.get("common_failure_patterns") or []:
                bucket["failure_distribution"][pattern] += 1
        else:
            bucket["generated_prompts"].append(row.get("prompt_id"))
            if row.get("diagnostic_issue_type"):
                bucket["failure_distribution"][row["diagnostic_issue_type"]] += 1
    buckets = []
    for bucket in grouped.values():
        scores = bucket.pop("official_scores")
        bucket["official_row_count"] = len(bucket["official_rows"])
        bucket["generated_prompt_count"] = len(bucket["generated_prompts"])
        bucket["average_official_score"] = round(mean(scores), 4) if scores else None
        bucket["current_route_distribution"] = dict(bucket.pop("route_distribution"))
        bucket["current_answer_family_distribution"] = dict(bucket.pop("answer_family_distribution"))
        bucket["common_failure_patterns"] = dict(bucket.pop("failure_distribution"))
        bucket["evidence_shape_distribution"] = dict(bucket.pop("evidence_shape_distribution"))
        buckets.append(bucket)
    return sorted(buckets, key=lambda item: (-item["official_row_count"], -item["generated_prompt_count"], item["bucket_id"]))


def _intent_bucket(value: Any) -> str:
    text = str(value or "").lower()
    if any(token in text for token in ["count", "how many", "number", "total"]):
        return "count"
    if any(token in text for token in ["list", "show", "name", "id", "which"]):
        return "list/name/id"
    if "status" in text or "state" in text or "published" in text or "enabled" in text:
        return "status"
    if any(token in text for token in ["when", "date", "time", "timestamp"]):
        return "timestamp/date/when"
    if any(token in text for token in ["yes", "no", "whether", "is ", "are "]):
        return "yes/no"
    if any(token in text for token in ["compare", "difference", "more than", "less than"]):
        return "compare"
    if any(token in text for token in ["why", "explain", "describe"]):
        return "explain"
    if text.upper() in {"COUNT"}:
        return "count"
    if text.upper() in {"LIST", "NAME", "ID"}:
        return "list/name/id"
    if text.upper() in {"STATUS", "STATE"}:
        return "status"
    if text.upper() in {"WHEN", "DATE", "TIMESTAMP"}:
        return "timestamp/date/when"
    if text.upper() in {"YES_NO", "BOOLEAN"}:
        return "yes/no"
    return "unknown/ambiguous"


def _domain_bucket(value: Any) -> str:
    text = str(value or "").lower()
    if "journey" in text or "campaign" in text:
        return "journey_campaign"
    if "segment" in text or "audience" in text:
        return "segment_audience"
    if "destination" in text or "dataflow" in text or "flow" in text:
        return "destination_dataflow" if "destination" in text else "dataflow_run"
    if "schema" in text or "dataset" in text or "catalog" in text:
        return "dataset_schema"
    if "property" in text or "field" in text:
        return "property_field"
    if "count" in text or "aggregation" in text:
        return "count_aggregation"
    if "status" in text or "monitor" in text:
        return "status_monitoring"
    return "unknown"


def _evidence_shape(fields: list[Any], row_count: Any, api_state: Any, zero_row: bool | None = None) -> list[str]:
    field_text = " ".join(str(field).lower() for field in fields)
    shapes = []
    if "count" in field_text or "total" in field_text:
        shapes.append("SQL count available")
    if "name" in field_text or "_id" in field_text or field_text.endswith(" id") or " id " in f" {field_text} ":
        shapes.append("SQL names/IDs available")
    if "status" in field_text or "state" in field_text:
        shapes.append("SQL status available")
    if any(token in field_text for token in ["time", "date", "timestamp", "created", "updated", "published"]):
        shapes.append("SQL timestamp available")
    if zero_row is True or row_count == 0:
        shapes.append("SQL zero rows")
    api = str(api_state or "").lower()
    if "dry_run" in api:
        shapes.append("API dry-run only")
    if "error" in api or "caveat" in api:
        shapes.append("API error/caveat only")
    return shapes or ["no structured evidence"]


def _execution_need(route: Any, requires_live: bool, sql_calls: int, api_calls: int, api_state: Any, evidence_shape: list[str]) -> str:
    route_text = str(route or "").upper()
    api = str(api_state or "").lower()
    if requires_live:
        return "live_api_required"
    if route_text == "API_ONLY":
        return "api_required"
    if sql_calls and not api_calls and "no structured evidence" not in evidence_shape:
        return "sql_only_possible"
    if sql_calls and api_calls and "dry_run" in api:
        return "dry_run_only_currently"
    if sql_calls and api_calls:
        return "sql_then_api_optional"
    if not sql_calls and not api_calls:
        return "no_local_evidence"
    return "sql_only_possible" if sql_calls else "no_local_evidence"


def _api_unnecessary(execution_need: str, api_state: Any) -> bool:
    return execution_need in {"sql_only_possible", "dry_run_only_currently"} and "dry_run" in str(api_state or "").lower()


def _fast_path_possible(intent: str, execution_need: str, evidence_shape: list[str], row: dict[str, Any]) -> bool:
    if execution_need in {"api_required", "live_api_required", "no_local_evidence"}:
        return False
    if intent == "count" and "SQL count available" in evidence_shape:
        return True
    if intent == "list/name/id" and "SQL names/IDs available" in evidence_shape:
        return True
    if intent == "status" and "SQL status available" in evidence_shape:
        return True
    if intent == "timestamp/date/when" and "SQL timestamp available" in evidence_shape:
        return True
    if "SQL zero rows" in evidence_shape:
        return True
    return bool(row.get("locally_fixable_now") and row.get("general_rule_possible"))


def _generated_fast_path_possible(row: dict[str, Any], intent: str, execution_need: str, evidence_shape: list[str]) -> bool:
    if not row.get("diagnostic_only", True):
        return False
    if row.get("likely_issue_type") in {"answer_template_gap", "zero_row_clarity_gap", "dry_run_wording_gap"}:
        return True
    return _fast_path_possible(intent, execution_need, evidence_shape, row)


def _failure_patterns(row: dict[str, Any]) -> list[str]:
    flags = row.get("failure_classification") or {}
    return [key for key, value in flags.items() if value] or [row.get("likely_primary_cause") or "no_clear_failure"]


def _answer_family(row: dict[str, Any]) -> str:
    intent = _intent_bucket(row.get("answer_intent"))
    domain = _domain_bucket(row.get("predicted_domain"))
    return f"{domain}_{intent}".replace("/", "_")


def _risk_level(execution_need: str, score: Any, flags: dict[str, Any]) -> str:
    if execution_need in {"api_required", "live_api_required"}:
        return "high"
    if flags.get("unsupported_claim") or flags.get("route_domain_wrong"):
        return "high"
    if isinstance(score, (int, float)) and float(score) >= 0.75:
        return "medium"
    return "low"


def _bucket_id(intent: str, domain: str, execution: str) -> str:
    return f"{intent}__{domain}__{execution}".replace("/", "_").replace(" ", "_")


def _strict_score(strict: dict[str, Any], official_rows: list[dict[str, Any]]) -> float | None:
    metrics = strict.get("summary", {}).get("by_strategy", {}).get("SQL_FIRST_API_VERIFY", {})
    if isinstance(metrics.get("avg_final_score"), (int, float)):
        return round(float(metrics["avg_final_score"]), 4)
    scores = [row.get("strict_score") for row in official_rows if isinstance(row.get("strict_score"), (int, float))]
    return round(mean(scores), 4) if scores else None


def _render_audit(payload: dict[str, Any]) -> str:
    lines = [
        "# Deterministic Prompt-Type Audit",
        "",
        "This report groups official strict rows and diagnostic generated prompts by prompt intent, domain, execution need, and evidence shape.",
        "",
        f"- Official rows: `{payload.get('official_row_count')}`",
        f"- Generated prompts: `{payload.get('generated_prompt_count')}`",
        f"- Fast-path candidate buckets: `{payload.get('summary', {}).get('fast_path_possible_buckets')}`",
        f"- Runtime change applied: `{payload.get('runtime_change_applied')}`",
        "",
        "| Bucket | Official | Generated | Fast Path? | Risk |",
        "| --- | ---: | ---: | --- | --- |",
    ]
    for bucket in payload.get("buckets", []):
        lines.append(
            f"| `{bucket['bucket_id']}` | `{bucket['official_row_count']}` | `{bucket['generated_prompt_count']}` | "
            f"`{bucket['deterministic_fast_path_possible']}` | `{bucket['risk_level']}` |"
        )
    return "\n".join(lines) + "\n"


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(redact_secrets(json.dumps(payload, indent=2, sort_keys=True)), encoding="utf-8")


def _redact(payload: Any) -> Any:
    try:
        return json.loads(redact_secrets(json.dumps(payload)))
    except Exception:
        return payload


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
