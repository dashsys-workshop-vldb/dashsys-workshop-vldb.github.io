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
PRIMARY_QUERY_ID = "example_011"
API_BOTTLENECK_QUERY_ID = "example_031"

_OPENROUTER_KEY_PREFIX = "sk" + "-or-"
_OPENAI_KEY_PREFIX = "sk" + "-"
_AUTH_HEADER_PREFIX = "Authorization:" + r"\s*" + "Bearer"

SECRET_PATTERNS = [
    re.compile(re.escape(_OPENROUTER_KEY_PREFIX) + r"[A-Za-z0-9_-]+"),
    re.compile(re.escape(_OPENAI_KEY_PREFIX) + r"[A-Za-z0-9_-]{20,}"),
    re.compile(_AUTH_HEADER_PREFIX + r"\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE),
    re.compile(
        r"(OPENROUTER_API_KEY|OPENAI_API_KEY|ANTHROPIC_API_KEY|CLIENT_SECRET|ACCESS_TOKEN|ADOBE_ACCESS_TOKEN|ADOBE_API_KEY|ADOBE_CLIENT_SECRET)=\S+"
    ),
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
        "executive_dashboard.md",
        "executive_dashboard.json",
        "end_to_end_system_dataflow.html",
        "end_to_end_system_dataflow.md",
        "end_to_end_system_dataflow.json",
        "project_architecture_c4.md",
        "project_architecture_c4.mmd",
        "end_to_end_pipeline_mermaid.md",
        "end_to_end_pipeline_mermaid.mmd",
        "live_adobe_api_status_mermaid.md",
        "live_adobe_api_status_mermaid.mmd",
        "report_generation_map.md",
        "report_generation_map.mmd",
        "sql_prompt_storyboard_primary.md",
        "sql_prompt_storyboard_primary.json",
        "prompt_storyboard_primary.md",
        "prompt_storyboard_primary.json",
        "prompt_transformation_primary.md",
        "prompt_transformation_primary.json",
        "end_to_end_execution_primary.md",
        "end_to_end_execution_primary.json",
        "technique_pipeline_map.md",
        "technique_pipeline_map.json",
        "system_status_dashboard.md",
        "system_status_dashboard.json",
        "technique_visual_cards.md",
        "technique_visual_cards.json",
        "score_bottleneck_dashboard.md",
        "score_bottleneck_dashboard.json",
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


STATUS_BADGES = {
    "promoted_default": "🟢 promoted_default",
    "shadow_only": "🟡 shadow_only",
    "default_off": "⚪ default_off",
    "diagnostic_only": "🔵 diagnostic_only",
    "blocked": "🔴 blocked/not_promoted",
    "not_promoted": "🔴 blocked/not_promoted",
    "disabled": "🔴 blocked/not_promoted",
}

RUNTIME_BADGES = {
    "packaged": "🟢 packaged",
    "isolated_trial": "🟡 isolated_trial",
    "shadow_report": "🟡 shadow_report",
    "diagnostic_report": "🔵 diagnostic_report",
}


def status_badge(status: Any) -> str:
    text = str(status or UNAVAILABLE)
    return STATUS_BADGES.get(text, text)


def runtime_badge(runtime_path: Any) -> str:
    text = str(runtime_path or UNAVAILABLE)
    return RUNTIME_BADGES.get(text, text)


def runtime_path_for_status(status: str) -> str:
    if status == "promoted_default":
        return "packaged"
    if status == "shadow_only":
        return "shadow_report"
    if status == "default_off":
        return "isolated_trial"
    if status == "diagnostic_only":
        return "diagnostic_report"
    return "diagnostic_report"


def how_to_read_page(start: str = "raw prompt card") -> str:
    return "\n".join(
        [
            "## How To Read This Page",
            "",
            f"1. Start from the {start}.",
            "2. Follow the arrows/cards to see how DASHSys transforms prompt, data, and evidence.",
            "3. Use badges to distinguish packaged, shadow, default-off, diagnostic, and blocked techniques.",
        ]
    )


def metric_cards(rows: list[tuple[str, Any, str | None]]) -> str:
    lines = ["| Metric | Value | Note |", "| --- | --- | --- |"]
    for label, value, note in rows:
        lines.append(f"| **{md_escape(label)}** | `{md_escape(value)}` | {md_escape(note or '')} |")
    return "\n".join(lines)


def prompt_callout(query_id: str, prompt: str, why: str) -> str:
    return "\n".join(
        [
            "## Primary Testing Prompt",
            "",
            f"> **{md_escape(query_id)}**",
            ">",
            f"> # {md_escape(prompt)}",
            ">",
            f"> {md_escape(why)}",
        ]
    )


def visual_card(title: str, badge: str, body: str, footer: str | None = None) -> str:
    parts = [
        f"### {badge} {title}",
        "",
        body,
    ]
    if footer:
        parts.extend(["", f"_Source/impact: {md_escape(footer)}_"])
    return "\n".join(parts)


def before_after_panel(title: str, before: Any, after: Any, technique: str, impact: str) -> str:
    return "\n".join(
        [
            f"### {title}",
            "",
            "| Before | After | Technique | Impact |",
            "| --- | --- | --- | --- |",
            f"| {md_escape(visual_summary(before, 220))} | {md_escape(visual_summary(after, 220))} | {md_escape(technique)} | {md_escape(impact)} |",
        ]
    )


def visual_summary(value: Any, max_chars: int = 160) -> str:
    if value in (None, "", [], {}):
        return UNAVAILABLE
    if isinstance(value, str):
        parsed = parse_jsonish(value)
        if parsed is not None:
            return visual_summary(parsed, max_chars=max_chars)
        text = value
    elif isinstance(value, list):
        head = ", ".join(visual_summary(item, 50) for item in value[:3])
        text = f"{len(value)} item(s)" + (f": {head}" if head else "")
        if len(value) > 3:
            text += f"; +{len(value) - 3} more"
    elif isinstance(value, dict):
        if set(value.keys()) == {"preview"} and isinstance(value.get("preview"), str):
            return visual_summary(value["preview"], max_chars=max_chars)
        keys = [
            "query",
            "query_id",
            "strategy",
            "route_type",
            "domain_type",
            "answer_family",
            "lookup_path",
            "confidence",
            "is_simple",
            "suggested_action",
            "reason",
            "normalized_query",
            "matching_text",
            "ids",
            "domains",
            "api_mode",
            "selected_plan",
            "planned_sql_calls",
            "planned_api_calls",
            "sql_calls_executed",
            "api_calls_executed",
            "answer_intent",
            "verifier_passed",
            "answer_length",
            "final_answer",
        ]
        parts: list[str] = []
        for key in keys:
            if key in value and value[key] not in (None, "", [], {}):
                parts.append(f"{key}={scalar_visual(value[key])}")
            if len(parts) >= 4:
                break
        if not parts:
            for key, item in value.items():
                if item in (None, "", [], {}):
                    continue
                parts.append(f"{key}={scalar_visual(item)}")
                if len(parts) >= 4:
                    break
        text = "; ".join(parts) if parts else compact(value, max_chars)
    else:
        text = str(value)
    text = redact_text(str(text))
    return text[: max_chars - 3].rstrip() + "..." if len(text) > max_chars else text


def scalar_visual(value: Any) -> str:
    if isinstance(value, dict):
        if "items" in value and "total_items" in value:
            return f"{value.get('total_items')} item(s)"
        if "preview" in value:
            return visual_summary(value.get("preview"), 60)
        return f"{len(value)} field(s)"
    if isinstance(value, list):
        return f"{len(value)} item(s)"
    text = str(value)
    return text[:57].rstrip() + "..." if len(text) > 60 else text


def parse_jsonish(value: str) -> Any | None:
    text = value.strip()
    if not ((text.startswith("{") and text.endswith("}")) or (text.startswith("[") and text.endswith("]"))):
        return None
    try:
        return json.loads(text)
    except Exception:
        return None


def checkpoint_by_id(trajectory: dict[str, Any], checkpoint_id: str) -> dict[str, Any]:
    for checkpoint in trajectory.get("checkpoints", []) or []:
        if checkpoint.get("checkpoint_id") == checkpoint_id:
            return checkpoint
    return {}


def checkpoint_output(trajectory: dict[str, Any], checkpoint_id: str) -> Any:
    return checkpoint_by_id(trajectory, checkpoint_id).get("output")


def checkpoint_input(trajectory: dict[str, Any], checkpoint_id: str) -> Any:
    checkpoint = checkpoint_by_id(trajectory, checkpoint_id)
    return checkpoint.get("input_summary") or checkpoint.get("input")


def primary_example_context(query_id: str = PRIMARY_QUERY_ID) -> dict[str, Any]:
    trajectory_path = OUTPUTS_DIR / "eval" / query_id / "sql_first_api_verify" / "trajectory.json"
    trajectory = json.loads(trajectory_path.read_text(encoding="utf-8"))
    strict_row = strict_row_by_query(query_id)
    winner = load_json("outputs/winner_readiness_report.json", {})
    packaged = winner.get("packaged", {})
    hidden = winner.get("hidden_style_eval", {})
    auto_trial = winner.get("autonomous_packaged_trial", {})
    return {
        "query_id": query_id,
        "trajectory": trajectory,
        "trajectory_path": str(trajectory_path),
        "strict_row": strict_row,
        "raw_prompt": trajectory.get("original_query"),
        "why_chosen": "Primary SQL-backed packaged walkthrough: the prompt becomes validated SQL, SQL returns the answer count, and API verification remains dry-run/unavailable.",
        "strategy": trajectory.get("strategy"),
        "route_type": trajectory.get("route_type") or get_path(checkpoint_output(trajectory, "checkpoint_05_query_analysis"), "route_type"),
        "final_answer": trajectory.get("final_answer"),
        "tool_calls": trajectory.get("tool_call_count"),
        "tokens": trajectory.get("estimated_tokens"),
        "runtime": trajectory.get("runtime"),
        "strict_score": strict_row.get("final_score", UNAVAILABLE),
        "correctness_score": strict_row.get("correctness_score", UNAVAILABLE),
        "answer_score": strict_row.get("answer_score", UNAVAILABLE),
        "sql_score": strict_row.get("sql_score", UNAVAILABLE),
        "api_score": strict_row.get("api_score", UNAVAILABLE),
        "api_status": api_status_for_trajectory(trajectory),
        "main_bottleneck": "SQL provides the answer source; API verification is dry-run/unavailable in the packaged trace.",
        "sql_artifacts": sql_artifacts(trajectory),
        "packaged": packaged,
        "hidden_style": hidden,
        "best_isolated": auto_trial,
    }


def primary_prompt_steps(context: dict[str, Any]) -> list[dict[str, Any]]:
    trajectory = context["trajectory"]
    raw = context["raw_prompt"]
    router = checkpoint_output(trajectory, "checkpoint_00_prompt_router")
    gate = checkpoint_output(trajectory, "checkpoint_simple_prompt_gate")
    normalized = checkpoint_output(trajectory, "checkpoint_02_query_normalization")
    tokens = checkpoint_output(trajectory, "checkpoint_03_query_tokens")
    analysis = checkpoint_output(trajectory, "checkpoint_05_query_analysis")
    lookup = checkpoint_output(trajectory, "checkpoint_06_lookup_path")
    context_card = checkpoint_output(trajectory, "checkpoint_07_context_card")
    plan = checkpoint_output(trajectory, "checkpoint_08_candidate_plans")
    execution = checkpoint_output(trajectory, "checkpoint_13_tool_execution")
    slots = checkpoint_output(trajectory, "checkpoint_15_answer_slots")
    verification = checkpoint_output(trajectory, "checkpoint_16_answer_verification")
    final_answer = checkpoint_output(trajectory, "checkpoint_18_final_answer")
    return [
        step("Raw prompt", "raw user query capture", raw, "Original test prompt enters the packaged SQL_FIRST_API_VERIFY path.", "observability"),
        step("Prompt router view", "prompt_router", router, "Recognizes the prompt as a schema count/data question.", "accuracy"),
        step("Simple-prompt gate", "simple_prompt_gate", gate, "Sends the prompt into the evidence pipeline rather than a direct answer.", "safety"),
        step("Normalized query", "query_normalizer", normalized, "Creates matching-friendly text while preserving original wording.", "accuracy"),
        step("Tokens/entities/domains", "query_tokens", tokens, "Extracts schema/count intent for routing and SQL generation.", "accuracy"),
        step("Query analysis", "query_analysis", analysis, "Classifies the route and answer family for schema counting.", "accuracy"),
        step("Lookup path / route intent", "lookup_path", lookup, "Narrows to schema tables and schema API verification options.", "accuracy"),
        step("Context card", "metadata_selector + context_cards", context_card, "Packs the endpoint catalog/context into metadata and prompt budget.", "efficiency"),
        step("Selected plan", "planner + plan_ensemble", plan, "Selects a SQL-first plan with dry-run API verification.", "efficiency"),
        step("Evidence objects", "executor + evidence_bus", execution, "Executes SQL for the answer count and records dry-run API verification.", "safety"),
        step("Answer slots / intent", "answer_slots", slots, "Maps SQL count evidence into COUNT answer intent.", "accuracy"),
        step("Verified final answer", "answer_verifier + answer_reranker", verification or final_answer, "Verifies the SQL-grounded count and preserves dry-run honesty.", "safety"),
    ]


def step(name: str, technique: str, payload: Any, changed: str, impact: str) -> dict[str, Any]:
    return {
        "name": name,
        "technique": technique,
        "short_payload": visual_summary(payload, 180),
        "what_changed": changed,
        "impact": impact,
    }


def api_status_for_trajectory(trajectory: dict[str, Any]) -> str:
    execution = checkpoint_output(trajectory, "checkpoint_13_tool_execution") or {}
    if execution.get("dry_run_status") is True:
        return "API verification attempted as dry-run; live API payload unavailable."
    if execution.get("api_calls_executed", 0):
        return "Live/API evidence available."
    return "API not executed in this trajectory."


def sql_artifacts(trajectory: dict[str, Any]) -> dict[str, Any]:
    validation = checkpoint_input(trajectory, "checkpoint_12_validation") or {}
    execution = checkpoint_output(trajectory, "checkpoint_13_tool_execution") or {}
    ast_validation = checkpoint_output(trajectory, "checkpoint_sql_ast_validation") or {}
    evidence_bus = checkpoint_output(trajectory, "checkpoint_14_evidence_bus") or {}
    sql = first_sql(validation)
    result_preview = first_sql_result(execution)
    result_facts = sql_result_facts(result_preview)
    return {
        "generated_sql": sql,
        "validated_sql": sql,
        "sql_validation": checkpoint_output(trajectory, "checkpoint_12_validation"),
        "ast_validation": ast_validation,
        "sql_result": result_preview,
        "sql_result_facts": result_facts,
        "evidence": evidence_bus,
        "sql_calls_executed": execution.get("sql_calls_executed", UNAVAILABLE),
        "api_calls_executed": execution.get("api_calls_executed", UNAVAILABLE),
        "dry_run_status": execution.get("dry_run_status", UNAVAILABLE),
    }


def first_sql(validation_input: Any) -> Any:
    steps = get_path(validation_input, "optimized_steps", "items", default=[])
    if isinstance(steps, list):
        for step_item in steps:
            if isinstance(step_item, dict) and step_item.get("action") == "sql":
                return step_item.get("sql", UNAVAILABLE)
    return UNAVAILABLE


def first_sql_result(execution_output: Any) -> Any:
    items = get_path(execution_output, "sql_results", "items", default=[])
    if isinstance(items, list) and items:
        return items[0].get("result_preview", UNAVAILABLE) if isinstance(items[0], dict) else items[0]
    return UNAVAILABLE


def sql_result_facts(result_preview: Any) -> list[str]:
    rows = get_path(result_preview, "items", default=[])
    facts: list[str] = []
    if isinstance(rows, list):
        for row in rows:
            if isinstance(row, dict):
                for key, value in row.items():
                    facts.append(f"{key} = {value}")
    return facts
