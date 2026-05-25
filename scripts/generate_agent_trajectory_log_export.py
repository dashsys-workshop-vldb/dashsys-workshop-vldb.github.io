#!/usr/bin/env python
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.trajectory import redact_secrets


REPORT_STEM = "agent_trajectory_log_export"
SQL_ONLY_LABEL = "sql_only_path"
LIVE_API_LABEL = "sql_plus_live_api_path"
MAX_EXCERPT_CHARS = 700
SENSITIVE_KEYS = {
    "authorization",
    "access_token",
    "refresh_token",
    "client_secret",
    "client_id",
    "api_key",
    "x-api-key",
    "x-gw-ims-org-id",
    "x-sandbox-name",
    "ims_org",
    "org_id",
    "sandbox",
    "secret",
    "token",
    "request-id",
    "request_id",
    "requestid",
    "registryrequestid",
    "correlationid",
    "traceid",
    "x-request-id",
    "x-correlation-id",
    "x-trace-id",
    "createdby",
    "updatedby",
    "createdclient",
    "updatedclient",
}
SENSITIVE_KEY_PARTS = {
    "authorization",
    "access_token",
    "refresh_token",
    "client_secret",
    "api_key",
    "x-api-key",
    "x-gw-ims-org-id",
    "x-sandbox-name",
}


def main() -> int:
    config = Config.from_env(ROOT)
    payload = build_export(config)
    write_export(config, payload)
    print(
        json.dumps(
            {
                "json": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.json"),
                "markdown": str(config.outputs_dir / "reports" / f"{REPORT_STEM}.md"),
                "examples": [example["label"] for example in payload["examples"]],
                "warnings": payload.get("warnings", []),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def build_export(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    warnings: list[str] = []
    sql_path = choose_sql_only_trajectory(config)
    live_path = choose_live_api_trajectory(config)
    examples: list[dict[str, Any]] = []
    source_files: list[str] = []

    if sql_path:
        examples.append(build_example(sql_path, label=SQL_ONLY_LABEL))
        source_files.extend(source_bundle(sql_path))
    else:
        warnings.append("No SQL-only final-submission trajectory was found.")

    if live_path:
        live_example = build_example(live_path, label=LIVE_API_LABEL)
        if not any(result.get("outcome") == "live_success" for result in live_example.get("tool_results", [])):
            warnings.append("No existing live API trajectory with live_success was found; included the best available dry_run=false API trajectory.")
        examples.append(live_example)
        source_files.extend(source_bundle(live_path))
    else:
        warnings.append("No existing SQL plus live API trajectory artifact was found.")

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "diagnostic_only": True,
        "official_score_claim": False,
        "promotion_allowed": False,
        "source_trajectory_files": sorted(_dedupe(source_files)),
        "available_trajectory_index": trajectory_index(config),
        "examples": examples,
        "warnings": warnings,
        "redaction_applied": True,
    }
    safe_payload = sanitize(payload)
    assert_safe_to_write(safe_payload)
    return safe_payload


def choose_sql_only_trajectory(config: Config) -> Path | None:
    candidates = sorted((config.outputs_dir / "final_submission").glob("query_*/trajectory.json"))
    best: tuple[int, Path] | None = None
    for path in candidates:
        try:
            data = load_json(path)
        except Exception:
            continue
        if data.get("route_type") != "SQL_ONLY" or int(data.get("sql_call_count") or 0) < 1:
            continue
        api_count = int(data.get("api_call_count") or 0)
        score = api_count
        if best is None or score < best[0]:
            best = (score, path)
    return best[1] if best else None


def choose_live_api_trajectory(config: Config) -> Path | None:
    candidates = sorted((config.outputs_dir / "live_api_evidence_pipeline_trial").glob("*/trajectory.json"))
    best: tuple[int, Path] | None = None
    for path in candidates:
        try:
            data = load_json(path)
        except Exception:
            continue
        api_steps = [step for step in data.get("steps", []) if step.get("kind") == "api_call"]
        if not api_steps:
            continue
        has_live_success = any(classify_api_result(step.get("result") or {}) == "live_success" for step in api_steps)
        has_live_empty = any(classify_api_result(step.get("result") or {}) == "live_empty" for step in api_steps)
        has_dry_run_false = any((step.get("result") or {}).get("dry_run") is False for step in api_steps)
        score = 0 if has_live_success else 1 if has_live_empty else 2 if has_dry_run_false else 3
        if best is None or score < best[0]:
            best = (score, path)
    return best[1] if best else None


def build_example(path: Path, *, label: str) -> dict[str, Any]:
    trajectory = load_json(path)
    metadata = load_json(path.with_name("metadata.json")) if path.with_name("metadata.json").exists() else {}
    checkpoints = trajectory.get("checkpoints") if isinstance(trajectory.get("checkpoints"), list) else []
    steps = trajectory.get("steps") if isinstance(trajectory.get("steps"), list) else []
    route_step = first_step(steps, "route")
    nlp_step = first_step(steps, "nlp")
    plan_step = first_step(steps, "plan")
    answer_diag = first_step(steps, "answer_diagnostics")
    sql_steps = [step for step in steps if step.get("kind") == "sql_call"]
    api_steps = [step for step in steps if step.get("kind") == "api_call"]
    tool_calls = [tool_call_from_sql(step) for step in sql_steps] + [tool_call_from_api(step) for step in api_steps]
    tool_results = [tool_result_from_sql(step) for step in sql_steps] + [tool_result_from_api(step) for step in api_steps]
    evidence_bus = evidence_bus_summary(sql_steps, api_steps, answer_diag)
    answer_slots = answer_slot_summary(answer_diag, tool_results)
    return sanitize(
        {
            "label": label,
            "source_trajectory_file": str(path),
            "source_metadata_file": str(path.with_name("metadata.json")) if path.with_name("metadata.json").exists() else None,
            "query_id": trajectory.get("query_id") or metadata.get("query_id"),
            "prompt": trajectory.get("original_query") or metadata.get("query"),
            "strategy": trajectory.get("strategy") or metadata.get("strategy"),
            "route_type": trajectory.get("route_type") or metadata.get("route_type"),
            "domain_type": trajectory.get("domain_type") or metadata.get("domain_type"),
            "answer_intent": answer_diag.get("answer_intent") or metadata.get("answer_intent") or "unavailable",
            "answer_family": answer_diag.get("answer_family") or metadata.get("context_card", {}).get("family") or "unavailable",
            "confidence": route_step.get("confidence") or query_analysis_confidence(checkpoints),
            "routing": {
                "route_step": route_step or "unavailable",
                "nlp_step": nlp_step or "unavailable",
                "selected_tables": metadata.get("selected_tables") or "unavailable",
                "selected_apis": metadata.get("selected_apis") or "unavailable",
            },
            "planning": {
                "selected_strategy": trajectory.get("strategy"),
                "evidence_policy": plan_step.get("rationale") if plan_step else "unavailable",
                "plan_steps": plan_step.get("steps") if plan_step else [],
                "optimizer_actions": plan_step.get("optimizer_actions") if plan_step else [],
            },
            "plan_steps": plan_step.get("steps") if plan_step else [],
            "tool_calls": tool_calls,
            "tool_results": tool_results,
            "evidence_bus": evidence_bus,
            "answer_slots": answer_slots,
            "final_answer": trajectory.get("final_answer") or "unavailable",
            "verification": {
                "verifier_passed": answer_diag.get("verifier_passed"),
                "unsupported_claims_count": answer_diag.get("unsupported_claims_count"),
                "completeness_missing_fields": answer_diag.get("completeness_missing_fields", []),
            },
            "metrics": {
                "tool_count": trajectory.get("tool_call_count"),
                "sql_calls": trajectory.get("sql_call_count"),
                "api_calls": trajectory.get("api_call_count"),
                "estimated_tokens": trajectory.get("estimated_tokens"),
                "runtime": trajectory.get("runtime"),
                "preprocessing_time": trajectory.get("preprocessing_time"),
                "planning_time": trajectory.get("planning_time"),
                "execution_time": trajectory.get("execution_time"),
                "answer_time": trajectory.get("answer_time"),
                "timings": trajectory.get("timings", {}),
            },
            "redaction_applied": True,
        }
    )


def tool_call_from_sql(step: dict[str, Any]) -> dict[str, Any]:
    return {
        "tool_name": "execute_sql",
        "purpose": "validated local DuckDB/parquet evidence query",
        "sql": step.get("sql"),
        "validation_result": step.get("validation", {}).get("ok"),
        "status": "ok" if step.get("result", {}).get("ok") else "error",
    }


def tool_call_from_api(step: dict[str, Any]) -> dict[str, Any]:
    headers = step.get("headers")
    header_names = sorted(headers) if isinstance(headers, dict) else []
    return {
        "tool_name": "call_api",
        "purpose": "validated Adobe API evidence call",
        "method": step.get("method"),
        "path": step.get("url"),
        "params": step.get("params"),
        "header_names": header_names,
        "header_values_redacted": True,
        "validation_result": step.get("validation", {}).get("ok"),
        "status": classify_api_result(step.get("result") or {}),
    }


def tool_result_from_sql(step: dict[str, Any]) -> dict[str, Any]:
    result = step.get("result") or {}
    rows = result.get("rows")
    return {
        "tool_name": "execute_sql",
        "ok": result.get("ok"),
        "row_count": result.get("row_count"),
        "limited": result.get("limited"),
        "error": result.get("error"),
        "result_summary": trim(rows),
        "outcome": "sql_success" if result.get("ok") else "sql_error",
    }


def tool_result_from_api(step: dict[str, Any]) -> dict[str, Any]:
    result = step.get("result") or {}
    return {
        "tool_name": "call_api",
        "ok": result.get("ok"),
        "dry_run": result.get("dry_run"),
        "status_code": result.get("status_code"),
        "endpoint": result.get("endpoint") or step.get("url"),
        "params": result.get("params") or step.get("params"),
        "outcome": classify_api_result(result),
        "result_summary": trim(result.get("result_preview") or result.get("error")),
    }


def classify_api_result(result: dict[str, Any]) -> str:
    if result.get("dry_run"):
        return "dry_run"
    if result.get("ok"):
        preview = result.get("result_preview")
        text = json.dumps(preview, default=str).lower() if preview is not None else ""
        if '"totalcount": 0' in text or '"items": []' in text or '"results": []' in text:
            return "live_empty"
        return "live_success"
    if result.get("status_code") is not None:
        return "api_error"
    return "unavailable"


def evidence_bus_summary(sql_steps: list[dict[str, Any]], api_steps: list[dict[str, Any]], answer_diag: dict[str, Any]) -> dict[str, Any]:
    sql_evidence = [tool_result_from_sql(step) for step in sql_steps]
    api_evidence = [tool_result_from_api(step) for step in api_steps]
    return {
        "evidence_sources": ["SQL" for _ in sql_evidence] + ["API" for _ in api_evidence],
        "evidence_state": {
            "sql": [item["outcome"] for item in sql_evidence],
            "api": [item["outcome"] for item in api_evidence],
        },
        "selected_evidence": {
            "sql_row_counts": [item.get("row_count") for item in sql_evidence],
            "api_outcomes": [item.get("outcome") for item in api_evidence],
            "slots_present": answer_diag.get("slots_present", []),
        },
    }


def answer_slot_summary(answer_diag: dict[str, Any], tool_results: list[dict[str, Any]]) -> dict[str, Any]:
    api_outcomes = [item.get("outcome") for item in tool_results if item.get("tool_name") == "call_api"]
    sql_rows = [item.get("row_count") for item in tool_results if item.get("tool_name") == "execute_sql"]
    return {
        "answer_intent": answer_diag.get("answer_intent"),
        "slot_values": {
            "slots_present": answer_diag.get("slots_present", []),
            "sql_row_counts": sql_rows,
            "api_outcomes": api_outcomes,
        },
        "source_tracking": {
            "uses_sql": bool(sql_rows),
            "uses_live_api": any(outcome in {"live_success", "live_empty"} for outcome in api_outcomes),
            "uses_dry_run": "dry_run" in api_outcomes,
            "uses_api_error_state": "api_error" in api_outcomes,
        },
    }


def trajectory_index(config: Config) -> dict[str, Any]:
    final = sorted((config.outputs_dir / "final_submission").glob("query_*/trajectory.json"))
    live = sorted((config.outputs_dir / "live_api_evidence_pipeline_trial").glob("*/trajectory.json"))
    return {
        "final_submission_trajectory_count": len(final),
        "live_api_evidence_pipeline_trajectory_count": len(live),
        "sql_only_candidates": [
            str(path)
            for path in final
            if safe_get(load_json(path), "route_type") == "SQL_ONLY"
        ][:20],
        "live_api_candidates": [str(path) for path in live[:20]],
    }


def write_export(config: Config, payload: dict[str, Any]) -> None:
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    assert_safe_to_write(payload)
    json_path = reports_dir / f"{REPORT_STEM}.json"
    md_path = reports_dir / f"{REPORT_STEM}.md"
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    markdown = render_markdown(payload)
    assert_safe_to_write(markdown)
    md_path.write_text(markdown, encoding="utf-8")


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Agent Trajectory Log",
        "",
        "This sanitized trajectory shows how the agent transforms a user prompt into a grounded answer through routing, SQL/API planning, validated tool calls, EvidenceBus, answer slots, and final answer generation. Sensitive credentials and environment values have been redacted.",
        "",
        f"Generated at: `{payload.get('generated_at')}`",
        "",
    ]
    warnings = payload.get("warnings") or []
    if warnings:
        lines.extend(["## Warnings", ""])
        lines.extend(f"- {warning}" for warning in warnings)
        lines.append("")
    for idx, example in enumerate(payload.get("examples", []), start=1):
        title = "SQL-only path" if example.get("label") == SQL_ONLY_LABEL else "SQL + Live API path"
        lines.extend(render_example(idx, title, example))
    return "\n".join(lines)


def render_example(idx: int, title: str, example: dict[str, Any]) -> list[str]:
    lines = [
        f"## Example {idx}: {title}",
        "",
        "### 1. Input",
        "",
        f"- user prompt: {fmt(example.get('prompt'))}",
        f"- query_id: `{example.get('query_id')}`",
        f"- strategy: `{example.get('strategy')}`",
        "",
        "### 2. Routing / Query Understanding",
        "",
        f"- route_type: `{example.get('route_type')}`",
        f"- domain_type: `{example.get('domain_type')}`",
        f"- answer_intent: `{example.get('answer_intent')}`",
        f"- answer_family: `{example.get('answer_family')}`",
        f"- confidence: `{example.get('confidence')}`",
        f"- selected tables: `{compact(example.get('routing', {}).get('selected_tables'))}`",
        f"- selected APIs: `{compact(example.get('routing', {}).get('selected_apis'))}`",
        "",
        "### 3. Planning",
        "",
        f"- selected strategy: `{example.get('planning', {}).get('selected_strategy')}`",
        f"- evidence policy: {fmt(example.get('planning', {}).get('evidence_policy'))}",
        "",
    ]
    for plan in example.get("plan_steps", []):
        lines.append(f"- `{plan.get('action')}`: {fmt(plan.get('purpose'))}")
    lines.extend(["", "### 4. Tool Calls", ""])
    for call in example.get("tool_calls", []):
        if call.get("tool_name") == "execute_sql":
            lines.extend(
                [
                    "- tool name: `execute_sql`",
                    f"  - purpose: {fmt(call.get('purpose'))}",
                    f"  - sanitized SQL: `{call.get('sql')}`",
                    f"  - validation result: `{call.get('validation_result')}`",
                    f"  - status/outcome: `{call.get('status')}`",
                ]
            )
        else:
            lines.extend(
                [
                    "- tool name: `call_api`",
                    f"  - method/path: `{call.get('method')} {call.get('path')}`",
                    f"  - params: `{compact(call.get('params'))}`",
                    f"  - header names: `{compact(call.get('header_names'))}`",
                    f"  - header values redacted: `{call.get('header_values_redacted')}`",
                    f"  - validation result: `{call.get('validation_result')}`",
                    f"  - status/outcome: `{call.get('status')}`",
                ]
            )
    lines.extend(["", "### 5. Tool Results", ""])
    for result in example.get("tool_results", []):
        lines.extend(
            [
                f"- `{result.get('tool_name')}` outcome: `{result.get('outcome')}`",
                f"  - summary: `{compact(result.get('result_summary'))}`",
            ]
        )
    lines.extend(
        [
            "",
            "### 6. EvidenceBus",
            "",
            f"- evidence sources: `{compact(example.get('evidence_bus', {}).get('evidence_sources'))}`",
            f"- evidence_state: `{compact(example.get('evidence_bus', {}).get('evidence_state'))}`",
            f"- selected evidence: `{compact(example.get('evidence_bus', {}).get('selected_evidence'))}`",
            "",
            "### 7. Answer Slots",
            "",
            f"- answer intent: `{example.get('answer_slots', {}).get('answer_intent')}`",
            f"- slot values: `{compact(example.get('answer_slots', {}).get('slot_values'))}`",
            f"- source tracking: `{compact(example.get('answer_slots', {}).get('source_tracking'))}`",
            "",
            "### 8. Final Answer",
            "",
            f"- final answer: {fmt(example.get('final_answer'))}",
            f"- verification result: `{compact(example.get('verification'))}`",
            "",
            "### 9. Efficiency",
            "",
            f"- tool count: `{example.get('metrics', {}).get('tool_count')}`",
            f"- token count: `{example.get('metrics', {}).get('estimated_tokens')}`",
            f"- runtime: `{example.get('metrics', {}).get('runtime')}`",
            f"- SQL calls: `{example.get('metrics', {}).get('sql_calls')}`",
            f"- API calls: `{example.get('metrics', {}).get('api_calls')}`",
            "",
        ]
    )
    return lines


def sanitize(value: Any) -> Any:
    redacted = redact_secrets(value)
    return sanitize_strings(redacted)


def sanitize_strings(value: Any) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            lowered = str(key).lower()
            if lowered in SENSITIVE_KEYS or any(part in lowered for part in SENSITIVE_KEY_PARTS):
                if lowered in {"header_names", "required_header_names", "tool_name"}:
                    result[key] = sanitize_strings(item)
                else:
                    result[key] = "[REDACTED]" if item not in (None, "", [], {}) else item
            else:
                result[key] = sanitize_strings(item)
        return result
    if isinstance(value, list):
        return [sanitize_strings(item) for item in value]
    if isinstance(value, str):
        text = value
        text = text.replace(".env.local", "[REDACTED_ENV_FILE]")
        text = text.replace(".env.organizer_latest.local", "[REDACTED_ENV_FILE]")
        text = re.sub(r"Authorization\s*[:=]\s*Bearer\s+[^\s,'\"}]+", "Authorization: Bearer [REDACTED]", text, flags=re.I)
        text = re.sub(r"\bBearer\s+[A-Za-z0-9._-]{8,}", "Bearer [REDACTED]", text, flags=re.I)
        text = re.sub(r"sk-[A-Za-z0-9_-]{8,}", "[REDACTED]", text)
        text = re.sub(r"\b[A-Za-z0-9_-]{3,}\*\*\*", "[REDACTED]", text)
        for env_value in os.environ.values():
            if env_value and len(env_value) >= 8 and env_value in text:
                text = text.replace(env_value, "[REDACTED]")
        return text[:MAX_EXCERPT_CHARS] if len(text) > MAX_EXCERPT_CHARS else text
    return value


def assert_safe_to_write(payload: Any) -> None:
    text = payload if isinstance(payload, str) else json.dumps(payload, sort_keys=True, default=str)
    forbidden_literals = [".env.local", ".env.organizer_latest.local"]
    for literal in forbidden_literals:
        if literal in text:
            raise RuntimeError(f"Refusing to write trajectory export with forbidden literal {literal}.")
    patterns = [
        r"Authorization\s*[:=]\s*Bearer\s+(?!\[REDACTED\])[^\s,'\"}]+",
        r"\bBearer\s+(?!\[REDACTED\])[A-Za-z0-9._-]{8,}",
        r"sk-[A-Za-z0-9_-]{12,}",
        r"\b[A-Za-z0-9_-]{3,}\*\*\*",
        r"\b(request-id|request_id|requestId|registryRequestId|traceId|correlationId)\b[\"':= ]+(?!\[REDACTED\])[A-Za-z0-9._:-]{8,}",
    ]
    for pattern in patterns:
        if re.search(pattern, text, flags=re.I):
            raise RuntimeError(f"Refusing to write trajectory export with unsafe pattern: {pattern}")


def trim(value: Any) -> Any:
    return sanitize(value)


def compact(value: Any) -> str:
    return json.dumps(sanitize(value), sort_keys=True, default=str)[:MAX_EXCERPT_CHARS]


def fmt(value: Any) -> str:
    if value is None:
        return "`unavailable`"
    return str(sanitize(value))


def first_step(steps: list[dict[str, Any]], kind: str) -> dict[str, Any]:
    for step in steps:
        if step.get("kind") == kind:
            return step
    return {}


def query_analysis_confidence(checkpoints: list[dict[str, Any]]) -> Any:
    for checkpoint in checkpoints:
        output = checkpoint.get("output")
        if isinstance(output, dict) and output.get("confidence") is not None:
            return output.get("confidence")
    return "unavailable"


def source_bundle(path: Path) -> list[str]:
    files = [str(path)]
    for sibling in ["metadata.json", "filled_system_prompt.txt"]:
        candidate = path.with_name(sibling)
        if candidate.exists():
            files.append(str(candidate))
    return files


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def safe_get(payload: dict[str, Any], key: str) -> Any:
    return payload.get(key) if isinstance(payload, dict) else None


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
