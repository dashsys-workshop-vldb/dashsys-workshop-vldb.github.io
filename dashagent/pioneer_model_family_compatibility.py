from __future__ import annotations

import json
from pathlib import Path
from statistics import mean
from typing import Any

from .pioneer_non_gpt_model_candidates import classify_model_family
from .trajectory import redact_secrets


FAMILY_ORDER = ["qwen", "mistral", "llama", "claude", "deepseek", "gemma", "glm", "kimi", "minimax", "gpt_oss", "other"]


def build_model_family_compatibility_matrix(
    *,
    model_results: list[dict[str, Any]],
    probe_results: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    probes = _probe_index(probe_results or [])
    families: dict[str, dict[str, Any]] = {}
    for result in model_results:
        model = str(result.get("model") or result.get("pioneer_model") or "")
        model_id = str(result.get("pioneer_model_id") or result.get("model_id") or model)
        family = classify_model_family(model, model_id)
        metrics = result.get("metrics") if isinstance(result.get("metrics"), dict) else {}
        availability = result.get("availability") if isinstance(result.get("availability"), dict) else {}
        probe = probes.get(model) or probes.get(model_id) or {}
        row = families.setdefault(family, _empty_family_row(family))
        if availability.get("available"):
            row["available_model_count"] += 1
            if row["representative_model"] is None:
                row["representative_model"] = model
                row["representative_model_id"] = model_id
        row["models"].append(
            {
                "model": model,
                "model_id": model_id,
                "available": bool(availability.get("available")),
                "metrics": _compact_model_metrics(result),
                "toolcall_supported": _toolcall_supported(probe),
                "json_content_fallback_works": _json_fallback_works(probe),
            }
        )
        _accumulate_metric(row, "timeout_failures", 1 if _timed_out(result) else 0)
        _accumulate_metric(row, "malformed_output_failures", _metric(metrics, "json_parse_failures", "routing_evidence.json_parse_failure_count"))
        _accumulate_metric(row, "usable_planner_output_count", _metric(metrics, "planner_usable_count", "routing_evidence.planner_usable_count"))
        _accumulate_metric(row, "declared_pass_count", _metric(metrics, "declared_pass_count", "routing_evidence.declared_pass_count"))
        _accumulate_metric(row, "sql_calls", _sql_call_count(result))
        _accumulate_metric(row, "api_calls", _api_call_count(result))
        _accumulate_metric(row, "evidence_bus_non_empty_count", _metric(metrics, "evidence_bus_non_empty_count", "routing_evidence.evidence_bus_non_empty_count"))
        _accumulate_metric(row, "no_tool_fp", _metric(metrics, "no_tool_fp", "safety.no_tool_fp"))
        _accumulate_metric(row, "unsupported_claims", _metric(metrics, "unsupported_claims", "safety.unsupported_claims"))
        latency = metrics.get("latency_sec") or _nested(metrics, "availability.latency_sec")
        if isinstance(latency, (int, float)):
            row.setdefault("_latencies", []).append(float(latency))
        _merge_probe_flags(row, probe)

    for family in list(families):
        row = families[family]
        latencies = row.pop("_latencies", [])
        row["average_planner_latency_sec"] = round(mean(latencies), 4) if latencies else None
        row["toolcall_supported"] = _collapse_flag(row.pop("_toolcall_flags", []))
        row["json_content_fallback_works"] = _collapse_flag(row.pop("_json_flags", []))
    ordered = {family: families[family] for family in FAMILY_ORDER if family in families}
    return redact_secrets({"families": ordered, "family_count": len(ordered)})


def select_full_benchmark_models_after_family_smoke(
    smoke_results: list[dict[str, Any]],
    *,
    minimum_families: int = 3,
) -> dict[str, Any]:
    selected: list[str] = []
    passing_families: set[str] = set()
    for result in smoke_results:
        metrics = result.get("metrics") if isinstance(result.get("metrics"), dict) else {}
        if not metrics.get("focused_smoke_pass"):
            continue
        model = str(result.get("model") or result.get("pioneer_model") or "")
        model_id = str(result.get("pioneer_model_id") or result.get("model_id") or model)
        passing_families.add(classify_model_family(model, model_id))
        selected.append(model)
    ordered_families = sorted(passing_families)
    return {
        "run_full_benchmark": len(ordered_families) >= minimum_families,
        "minimum_families": minimum_families,
        "passing_family_count": len(ordered_families),
        "passing_families": ordered_families,
        "selected_models": selected if len(ordered_families) >= minimum_families else [],
    }


def write_model_family_compatibility_matrix(
    report_dir: Path,
    matrix: dict[str, Any],
) -> dict[str, str]:
    report_dir.mkdir(parents=True, exist_ok=True)
    json_path = report_dir / "model_family_compatibility_matrix.json"
    md_path = report_dir / "model_family_compatibility_matrix.md"
    json_path.write_text(json.dumps(redact_secrets(matrix), indent=2, sort_keys=True, default=str), encoding="utf-8")
    md_path.write_text(_matrix_markdown(matrix), encoding="utf-8")
    return {"json": str(json_path), "md": str(md_path)}


def _empty_family_row(family: str) -> dict[str, Any]:
    return {
        "family": family,
        "available_model_count": 0,
        "representative_model": None,
        "representative_model_id": None,
        "toolcall_supported": "unknown",
        "json_content_fallback_works": "unknown",
        "average_planner_latency_sec": None,
        "timeout_failures": 0,
        "malformed_output_failures": 0,
        "usable_planner_output_count": 0,
        "declared_pass_count": 0,
        "sql_calls": 0,
        "api_calls": 0,
        "evidence_bus_non_empty_count": 0,
        "no_tool_fp": 0,
        "unsupported_claims": 0,
        "models": [],
        "_toolcall_flags": [],
        "_json_flags": [],
        "_latencies": [],
    }


def _probe_index(probes: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for probe in probes:
        for key in (probe.get("display_name"), probe.get("model"), probe.get("model_id"), probe.get("pioneer_model_id")):
            if key:
                indexed[str(key)] = probe
    return indexed


def _toolcall_supported(probe: dict[str, Any]) -> bool | None:
    tool = probe.get("toolcall_probe") if isinstance(probe.get("toolcall_probe"), dict) else {}
    if "toolcall_supported" in tool:
        return bool(tool.get("toolcall_supported"))
    if "tool_calls_count" in tool:
        return int(tool.get("tool_calls_count") or 0) > 0
    return None


def _json_fallback_works(probe: dict[str, Any]) -> bool | None:
    json_probe = probe.get("json_content_probe") if isinstance(probe.get("json_content_probe"), dict) else {}
    if not json_probe:
        return None
    preview = str(json_probe.get("content_preview") or "")
    return bool(json_probe.get("ok")) and "{" in preview and "}" in preview


def _merge_probe_flags(row: dict[str, Any], probe: dict[str, Any]) -> None:
    tool = _toolcall_supported(probe)
    json_ok = _json_fallback_works(probe)
    if tool is not None:
        row.setdefault("_toolcall_flags", []).append(tool)
    if json_ok is not None:
        row.setdefault("_json_flags", []).append(json_ok)


def _collapse_flag(flags: list[bool]) -> bool | str:
    if not flags:
        return "unknown"
    return any(flags)


def _accumulate_metric(row: dict[str, Any], key: str, value: int) -> None:
    row[key] = int(row.get(key) or 0) + int(value or 0)


def _prompt_call_count(result: dict[str, Any], key: str) -> int:
    return sum(int(row.get(key) or 0) for row in result.get("prompt_results") or [] if isinstance(row, dict))


def _sql_call_count(result: dict[str, Any]) -> int:
    prompt_count = _prompt_call_count(result, "sql_calls")
    if prompt_count:
        return prompt_count
    return _metric(result.get("metrics") if isinstance(result.get("metrics"), dict) else {}, "focused_smoke_sql_calls", "execution.focused_smoke_sql_calls")


def _api_call_count(result: dict[str, Any]) -> int:
    prompt_count = _prompt_call_count(result, "api_calls")
    if prompt_count:
        return prompt_count
    return _metric(result.get("metrics") if isinstance(result.get("metrics"), dict) else {}, "focused_smoke_api_calls", "execution.focused_smoke_api_calls")


def _compact_model_metrics(result: dict[str, Any]) -> dict[str, Any]:
    metrics = result.get("metrics") if isinstance(result.get("metrics"), dict) else {}
    return {
        "focused_smoke_pass": bool(metrics.get("focused_smoke_pass")),
        "json_parse_failures": _metric(metrics, "json_parse_failures", "routing_evidence.json_parse_failure_count"),
        "planner_usable_count": _metric(metrics, "planner_usable_count", "routing_evidence.planner_usable_count"),
        "declared_pass_count": _metric(metrics, "declared_pass_count", "routing_evidence.declared_pass_count"),
        "sql_calls": _sql_call_count(result),
        "api_calls": _api_call_count(result),
        "evidence_bus_non_empty_count": _metric(metrics, "evidence_bus_non_empty_count", "routing_evidence.evidence_bus_non_empty_count"),
        "no_tool_fp": _metric(metrics, "no_tool_fp", "safety.no_tool_fp"),
        "unsupported_claims": _metric(metrics, "unsupported_claims", "safety.unsupported_claims"),
    }


def _metric(metrics: dict[str, Any], key: str, nested_path: str) -> int:
    value = metrics.get(key)
    if isinstance(value, (int, float)):
        return int(value)
    nested = _nested(metrics, nested_path)
    if isinstance(nested, (int, float)):
        return int(nested)
    return 0


def _nested(payload: dict[str, Any], dotted_path: str) -> Any:
    current: Any = payload
    for part in dotted_path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _timed_out(result: dict[str, Any]) -> bool:
    text = " ".join(str(result.get(key) or "") for key in ("error", "fast_fail_reason", "smoke_timeout"))
    return bool(result.get("smoke_timeout")) or "timeout" in text.lower()


def _matrix_markdown(matrix: dict[str, Any]) -> str:
    lines = [
        "# Pioneer Model Family Compatibility Matrix",
        "",
        "Status: diagnostic_only. This matrix groups existing focused-smoke and probe artifacts by model family.",
        "",
        "| Family | Available | Representative | Toolcalls | JSON fallback | Planner usable | Passes | SQL | API | EvidenceBus non-empty | no_tool_fp | Unsupported | Timeouts | Malformed |",
        "|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for family, row in (matrix.get("families") or {}).items():
        lines.append(
            f"| {family} | {row.get('available_model_count')} | {row.get('representative_model') or ''} | "
            f"{row.get('toolcall_supported')} | {row.get('json_content_fallback_works')} | "
            f"{row.get('usable_planner_output_count')} | {row.get('declared_pass_count')} | "
            f"{row.get('sql_calls')} | {row.get('api_calls')} | {row.get('evidence_bus_non_empty_count')} | "
            f"{row.get('no_tool_fp')} | {row.get('unsupported_claims')} | {row.get('timeout_failures')} | {row.get('malformed_output_failures')} |"
        )
    lines.append("")
    return "\n".join(lines)
