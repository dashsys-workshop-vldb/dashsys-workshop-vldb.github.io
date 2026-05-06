from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any

from .trajectory import compact_preview, redact_secrets


def load_trajectory(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def extract_checkpoint_map(trajectory: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(checkpoint.get("checkpoint_id")): checkpoint
        for checkpoint in trajectory.get("checkpoints", []) or []
        if checkpoint.get("checkpoint_id")
    }


def extract_prompt_router_decision(trajectory: dict[str, Any]) -> dict[str, Any]:
    checkpoints = extract_checkpoint_map(trajectory)
    checkpoint = checkpoints.get("checkpoint_00_prompt_router") or {}
    output = checkpoint.get("output") or {}
    if isinstance(output, dict) and output:
        return output
    for step in trajectory.get("steps", []) or []:
        if step.get("kind") in {"prompt_router", "route"}:
            return step.get("decision") if isinstance(step.get("decision"), dict) else step
    route = {}
    if trajectory.get("route_type"):
        route["mode"] = trajectory.get("route_type")
    if trajectory.get("domain_type"):
        route["domain_type"] = trajectory.get("domain_type")
    return route


def extract_sql_api_steps(trajectory: dict[str, Any]) -> dict[str, Any]:
    steps = trajectory.get("steps", []) or []
    sql_calls = [step for step in steps if step.get("kind") == "sql_call"]
    api_calls = [step for step in steps if step.get("kind") == "api_call"]
    if not sql_calls and trajectory.get("llm_tool_calls"):
        sql_calls = [
            _llm_tool_call_to_step(call)
            for call in trajectory.get("llm_tool_calls", [])
            if call.get("tool_name") == "execute_sql" or call.get("tool") == "execute_sql"
        ]
        api_calls = [
            _llm_tool_call_to_step(call)
            for call in trajectory.get("llm_tool_calls", [])
            if call.get("tool_name") == "call_api" or call.get("tool") == "call_api"
        ]
    return {"sql_calls": sql_calls, "api_calls": api_calls}


def extract_prompt_to_sql_api_mapping(trajectory: dict[str, Any]) -> dict[str, Any]:
    summary = build_dataflow_summary(trajectory)
    return redact_secrets(
        {
            "prompt": summary["user_query"],
            "route": summary["route"],
            "normalization": summary["normalization"],
            "tokens": summary["tokens"],
            "context": summary["context"],
            "sql": summary["sql"],
            "api": summary["api"],
            "evidence": summary["evidence"],
            "answer": summary["answer"],
        }
    )


def build_dataflow_summary(trajectory: dict[str, Any]) -> dict[str, Any]:
    checkpoints = extract_checkpoint_map(trajectory)
    sql_api = extract_sql_api_steps(trajectory)
    sql_calls = sql_api["sql_calls"]
    api_calls = sql_api["api_calls"]
    nlp_step = _first_step(trajectory, "nlp")
    plan_step = _first_step(trajectory, "plan")
    optimizer_step = _first_step(trajectory, "optimizer")
    route = extract_prompt_router_decision(trajectory)
    first_sql = sql_calls[0] if sql_calls else {}
    first_api = api_calls[0] if api_calls else {}
    candidate_mode = _find_context_mode(trajectory, checkpoints)
    dry_run = _api_dry_run(api_calls)
    evidence_available = _evidence_available(trajectory, sql_calls, api_calls)
    checkpoint_effect = _first_checkpoint_effect(trajectory)
    query_id = _value(trajectory.get("query_id") or trajectory.get("query"), "missing query_id")
    strategy = _value(trajectory.get("strategy") or trajectory.get("system"), "missing strategy")
    user_query = _value(trajectory.get("original_query") or trajectory.get("query"), "missing original query")
    return redact_secrets(
        {
            "query_id": query_id,
            "strategy": strategy,
            "variant": _variant_label(trajectory),
            "user_query": user_query,
            "route": {
                "mode": _value(route.get("mode") or route.get("route_type"), "no prompt router decision"),
                "confidence": _value(route.get("confidence"), "no route confidence recorded"),
                "risk": _value(route.get("risk"), "no route risk recorded"),
                "api_policy": _value(route.get("api_policy"), "no API policy recorded"),
            },
            "normalization": _normalization_summary(checkpoints),
            "tokens": _tokens_summary(checkpoints, nlp_step),
            "context": {
                "context_mode": candidate_mode,
                "candidate_tables": _value(_candidate_tables(checkpoints, nlp_step), "no candidate tables recorded"),
                "candidate_apis": _value(_candidate_apis(checkpoints, nlp_step), "no candidate APIs recorded"),
                "confidence": _value(_find_nested(trajectory, "confidence"), "no candidate confidence recorded"),
                "score_margin": _value(_find_nested(trajectory, "score_margin"), "no candidate score margin recorded"),
                "estimated_context_tokens": _value(_estimated_context_tokens(trajectory), "no context token estimate recorded"),
            },
            "planning": {
                "selected_strategy": strategy,
                "rationale": _value(plan_step.get("rationale"), "no plan rationale recorded"),
                "optimizer_decision": _value(_brief(optimizer_step.get("plan_ensemble") or plan_step.get("optimizer_actions")), "no optimizer decision recorded"),
                "call_budget": _value(_checkpoint_output(checkpoints, "checkpoint_11_call_budget"), "no call budget checkpoint recorded"),
            },
            "sql": {
                "preview": _value(first_sql.get("sql"), "no SQL call in trajectory"),
                "validation": _validation_status(first_sql),
                "row_count": _value(_nested(first_sql, ["result", "row_count"]), "no SQL row count recorded"),
                "result_preview": _value(_brief(_nested(first_sql, ["result", "rows"])), "no SQL rows preview recorded"),
            },
            "api": {
                "endpoint": _api_endpoint(first_api),
                "validation": _validation_status(first_api),
                "dry_run": dry_run,
                "live_evidence_available": _api_live_evidence(api_calls),
                "endpoint_repair": _value(_endpoint_repair(api_calls), "no endpoint repair recorded"),
                "result_preview": _value(_brief(_nested(first_api, ["result", "result_preview"])), "no API result preview recorded"),
            },
            "execution": {
                "execute_sql_calls": len(sql_calls),
                "call_api_calls": len(api_calls),
                "tool_call_count": _value(trajectory.get("tool_call_count"), "tool_call_count missing"),
                "valid_tool_calls": _valid_tool_calls(trajectory, sql_calls, api_calls),
                "invalid_tool_calls": _value(trajectory.get("invalid_tool_call_count"), "no invalid-call metric recorded"),
                "duplicate_invalid_calls": _value(trajectory.get("duplicate_invalid_call_count"), "no duplicate-invalid metric recorded"),
                "endpoint_repairs": _value(trajectory.get("repaired_endpoint_count"), "no endpoint-repair metric recorded"),
                "schema_hint_injections": _value(trajectory.get("schema_hint_injected"), "no schema-hint metric recorded"),
            },
            "evidence": {
                "evidence_available": evidence_available,
                "dry_run_only": dry_run,
                "zero_row_uncertain": _zero_row_uncertain(sql_calls),
                "successful_evidence_count": _successful_evidence_count(trajectory, sql_calls, api_calls),
                "explanation": _evidence_explanation(dry_run, evidence_available),
            },
            "answer": {
                "final_answer_preview": _value(_preview(trajectory.get("final_answer")), "missing final answer"),
                "answer_verification": _value(_checkpoint_output(checkpoints, "checkpoint_16_answer_verification"), "no answer verification checkpoint recorded"),
                "empty_result_uncertainty": _value(_empty_result_uncertainty(trajectory), "no empty-result uncertainty wording detected"),
            },
            "metrics": {
                "runtime": _value(trajectory.get("runtime"), "runtime missing"),
                "estimated_tokens": _value(trajectory.get("estimated_tokens"), "estimated_tokens missing"),
                "prompt_context_tokens": _value(trajectory.get("prompt_context_tokens"), "prompt_context_tokens missing"),
                "preprocessing_time": _value(trajectory.get("preprocessing_time"), "preprocessing_time missing"),
                "planning_time": _value(trajectory.get("planning_time"), "planning_time missing"),
                "execution_time": _value(trajectory.get("execution_time"), "execution_time missing"),
                "answer_time": _value(trajectory.get("answer_time"), "answer_time missing"),
                "checkpoint_count": len(trajectory.get("checkpoints", []) or []),
            },
            "checkpoint_effect": checkpoint_effect,
            "checkpoint_count": len(trajectory.get("checkpoints", []) or []),
        }
    )


def build_mermaid_graph(trajectory: dict[str, Any]) -> str:
    summary = build_dataflow_summary(trajectory)
    route = summary["route"]
    context = summary["context"]
    sql = summary["sql"]
    api = summary["api"]
    evidence = summary["evidence"]
    metrics = summary["metrics"]
    lines = [
        "flowchart TD",
        "  subgraph Input",
        f"    input_prompt[\"User Prompt<br/>{_m(summary['user_query'])}\"]",
        "  end",
        "  subgraph Routing",
        f"    router[\"Prompt Router<br/>mode={_m(route['mode'])}<br/>api={_m(route['api_policy'])}\"]",
        "    input_prompt -->|route_prompt| router",
        "  end",
        "  subgraph QueryUnderstanding[\"Query Understanding\"]",
        f"    normalizer[\"Query Normalizer<br/>{_m(summary['normalization'].get('normalized_query', 'n/a'))}\"]",
        f"    tokens[\"Query Tokens<br/>{_m(_brief(summary['tokens']))}\"]",
        "    router -->|clean + extract| normalizer --> tokens",
        "  end",
        "  subgraph ContextSelection[\"Context Selection\"]",
        f"    context[\"Context Mode<br/>{_m(context['context_mode'])}\"]",
        f"    candidates[\"Tables/APIs<br/>{_m(_brief({'tables': context['candidate_tables'], 'apis': context['candidate_apis']}))}\"]",
        "    tokens -->|score relevance| context --> candidates",
        "  end",
        "  subgraph Planning",
        f"    planner[\"Planner<br/>{_m(summary['planning']['selected_strategy'])}\"]",
        f"    optimizer[\"Plan Optimizer<br/>{_m(summary['planning']['optimizer_decision'])}\"]",
        "    candidates -->|metadata + policy| planner --> optimizer",
        "  end",
        "  subgraph SQLPath[\"SQL Path\"]",
        f"    sqlgen[\"SQL Generator<br/>{_m(_preview(sql['preview'], 90))}\"]",
        f"    sqlval[\"SQL Validator<br/>{_m(sql['validation'])}\"]",
        "    optimizer -->|SQL step if needed| sqlgen --> sqlval",
        "  end",
        "  subgraph APIPath[\"API Path\"]",
        f"    apisel[\"API Selector<br/>{_m(api['endpoint'])}\"]",
        f"    apival[\"API Validator<br/>{_m(api['validation'])}<br/>dry_run={_m(str(api['dry_run']))}\"]",
        "    optimizer -->|API policy| apisel --> apival",
        "  end",
        "  subgraph ToolExecution[\"Tool Execution\"]",
        f"    tools[\"Tool Calls<br/>sql={summary['execution']['execute_sql_calls']} api={summary['execution']['call_api_calls']}<br/>invalid={_m(str(summary['execution']['invalid_tool_calls']))}\"]",
        "    sqlval -->|execute_sql| tools",
        "    apival -->|call_api / dry-run| tools",
        "  end",
        "  subgraph EvidenceBus",
        f"    evidence[\"Evidence Quality<br/>overall={_m(str(evidence['evidence_available']))}<br/>api_dry_run={_m(str(evidence['dry_run_only']))}\"]",
        "    tools -->|extract facts| evidence",
        "  end",
        "  subgraph AnswerVerification[\"Answer Verification\"]",
        f"    verifier[\"Verifier<br/>{_m(_brief(summary['answer']['answer_verification']))}\"]",
        "    evidence -->|answer slots + claims| verifier",
        "  end",
        "  subgraph FinalAnswer[\"Final Answer\"]",
        f"    answer[\"Final Answer<br/>{_m(summary['answer']['final_answer_preview'])}\"]",
        "    verifier -->|safe answer| answer",
        "  end",
        "  subgraph Metrics",
        f"    metrics[\"Metrics<br/>tools={_m(str(metrics['tool_call_count'] if 'tool_call_count' in metrics else summary['execution']['tool_call_count']))}<br/>tokens={_m(str(metrics['estimated_tokens']))}<br/>runtime={_m(str(metrics['runtime']))}\"]",
        "    answer -->|record trajectory| metrics",
        "  end",
    ]
    return "\n".join(lines) + "\n"


def build_checkpoint_effect_table(trajectory: dict[str, Any]) -> str:
    lines = [
        "| Checkpoint | Stage | Technique | Input | Output | Effect on data flow | Correctness role | Efficiency role |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    checkpoints = trajectory.get("checkpoints", []) or []
    if not checkpoints:
        lines.append("| `n/a` | n/a | n/a | n/a | n/a | n/a - no checkpoints recorded | n/a | n/a |")
    for checkpoint in checkpoints:
        lines.append(
            "| `{}` | {} | {} | {} | {} | {} | {} | {} |".format(
                _md(checkpoint.get("checkpoint_id")),
                _md(checkpoint.get("stage")),
                _md(checkpoint.get("technique")),
                _md(_brief(checkpoint.get("input_summary"))),
                _md(_brief(checkpoint.get("output") or checkpoint.get("output_summary"))),
                _md(checkpoint.get("effect")),
                _md(checkpoint.get("correctness_role")),
                _md(checkpoint.get("efficiency_role")),
            )
        )
    return "\n".join(lines) + "\n"


def build_markdown_report(trajectory: dict[str, Any]) -> str:
    summary = build_dataflow_summary(trajectory)
    lines = [
        "# DASHSys Prompt-To-Answer Dataflow",
        "",
        "## Quality Gate Facts",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| Query ID | `{_md(summary['query_id'])}` |",
        f"| User query | {_md(summary['user_query'])} |",
        f"| Strategy | `{_md(summary['strategy'])}` |",
        f"| Variant | {_md(summary['variant'])} |",
        f"| Final answer preview | {_md(summary['answer']['final_answer_preview'])} |",
        f"| Tool call count | {_md(summary['execution']['tool_call_count'])} |",
        f"| Runtime | {_md(summary['metrics']['runtime'])} |",
        f"| Estimated tokens | {_md(summary['metrics']['estimated_tokens'])} |",
        f"| Checkpoint count | {_md(summary['checkpoint_count'])} |",
        f"| Candidate context mode | {_md(summary['context']['context_mode'])} |",
        "",
        "```mermaid",
        build_mermaid_graph(trajectory).strip(),
        "```",
        "",
        "## SQL And API Preview",
        "",
        "| Path | Preview | Validation | Result / Status |",
        "| --- | --- | --- | --- |",
        f"| SQL | {_md(summary['sql']['preview'])} | {_md(summary['sql']['validation'])} | row_count={_md(summary['sql']['row_count'])}; rows={_md(summary['sql']['result_preview'])} |",
        f"| API | {_md(summary['api']['endpoint'])} | {_md(summary['api']['validation'])} | dry_run={_md(summary['api']['dry_run'])}; live_api_evidence={_md(summary['api']['live_evidence_available'])}; overall_evidence={_md(summary['evidence']['evidence_available'])}; preview={_md(summary['api']['result_preview'])} |",
        "",
        "## Tool Execution vs Evidence Availability",
        "",
        summary["evidence"]["explanation"],
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| execute_sql calls | {_md(summary['execution']['execute_sql_calls'])} |",
        f"| call_api calls | {_md(summary['execution']['call_api_calls'])} |",
        f"| valid tool calls | {_md(summary['execution']['valid_tool_calls'])} |",
        f"| invalid tool calls | {_md(summary['execution']['invalid_tool_calls'])} |",
        f"| endpoint repairs | {_md(summary['execution']['endpoint_repairs'])} |",
        f"| schema hint injections | {_md(summary['execution']['schema_hint_injections'])} |",
        f"| dry-run only | {_md(summary['evidence']['dry_run_only'])} |",
        f"| successful evidence count | {_md(summary['evidence']['successful_evidence_count'])} |",
        f"| zero-row uncertain | {_md(summary['evidence']['zero_row_uncertain'])} |",
        "",
        "## Technique Impact Highlight",
        "",
        f"- Correctness: {_md(summary['checkpoint_effect']['correctness_role'])}",
        f"- Efficiency: {_md(summary['checkpoint_effect']['efficiency_role'])}",
        f"- Dataflow effect: {_md(summary['checkpoint_effect']['effect'])}",
        "",
        "## Prompt To SQL/API Mapping",
        "",
        "```json",
        json.dumps(redact_secrets(compact_preview(extract_prompt_to_sql_api_mapping(trajectory), 5000)), indent=2, sort_keys=True, default=str),
        "```",
        "",
        "## Checkpoint Effect Table",
        "",
        build_checkpoint_effect_table(trajectory).strip(),
        "",
    ]
    return "\n".join(lines)


def build_html_report(trajectory: dict[str, Any]) -> str:
    markdown = build_markdown_report(trajectory)
    graph = build_mermaid_graph(trajectory)
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>DASHSys Dataflow</title>
  <script type="module">import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs'; mermaid.initialize({{startOnLoad:true}});</script>
  <style>body{{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;margin:32px;line-height:1.45}} pre{{background:#f6f8fa;padding:12px;overflow:auto;white-space:pre-wrap}} table{{border-collapse:collapse;width:100%;margin:12px 0}} td,th{{border:1px solid #d0d7de;padding:6px;vertical-align:top}} code{{background:#f6f8fa;padding:1px 4px;border-radius:3px}}</style>
</head>
<body>
  <h1>DASHSys Prompt-To-Answer Dataflow</h1>
  <div class="mermaid">{html.escape(graph)}</div>
  <h2>Markdown Report</h2>
  <pre>{html.escape(markdown)}</pre>
</body>
</html>
"""


def write_dataflow_artifacts(trajectory: dict[str, Any], out_dir: Path, *, overwrite: bool = True) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "mmd": out_dir / "dataflow.mmd",
        "md": out_dir / "dataflow.md",
        "html": out_dir / "dataflow.html",
        "json": out_dir / "dataflow_summary.json",
    }
    if not overwrite and all(path.exists() for path in files.values()):
        return {key: str(path) for key, path in files.items()}
    files["mmd"].write_text(build_mermaid_graph(trajectory), encoding="utf-8")
    files["md"].write_text(build_markdown_report(trajectory), encoding="utf-8")
    files["html"].write_text(build_html_report(trajectory), encoding="utf-8")
    files["json"].write_text(json.dumps(build_dataflow_summary(trajectory), indent=2, sort_keys=True, default=str), encoding="utf-8")
    return {key: str(path) for key, path in files.items()}


def default_visualization_dir(outputs_dir: Path, trajectory: dict[str, Any]) -> Path:
    query_id = _slug(str(trajectory.get("query_id") or trajectory.get("query") or "query"))
    strategy = _slug(str(trajectory.get("strategy") or trajectory.get("system") or "unknown_strategy"))
    return outputs_dir / "visualizations" / query_id / strategy


def trajectory_from_llm_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "query_id": row.get("query_id"),
        "original_query": row.get("query"),
        "strategy": row.get("system"),
        "system": row.get("system"),
        "baseline_variant": row.get("baseline_variant"),
        "final_answer": row.get("final_answer"),
        "tool_call_count": row.get("tool_call_count"),
        "runtime": row.get("runtime"),
        "prompt_context_tokens": row.get("prompt_context_tokens"),
        "invalid_tool_call_count": row.get("invalid_tool_call_count"),
        "duplicate_invalid_call_count": row.get("duplicate_invalid_call_count"),
        "repaired_endpoint_count": row.get("repaired_endpoint_count"),
        "schema_hint_injected": row.get("schema_hint_injected"),
        "successful_evidence_count": row.get("successful_evidence_count"),
        "llm_tool_calls": row.get("llm_tool_calls", []),
        "steps": [],
        "checkpoints": [],
    }


def _llm_tool_call_to_step(call: dict[str, Any]) -> dict[str, Any]:
    args = call.get("arguments") or {}
    if call.get("tool_name") == "execute_sql" or call.get("tool") == "execute_sql":
        return {
            "kind": "sql_call",
            "sql": args.get("sql"),
            "validation": call.get("validation"),
            "result": call.get("result_preview"),
        }
    return {
        "kind": "api_call",
        "method": args.get("method"),
        "url": args.get("url"),
        "params": args.get("params"),
        "validation": call.get("validation"),
        "result": call.get("result_preview"),
        "endpoint_repair": call.get("endpoint_repair"),
    }


def _first_step(trajectory: dict[str, Any], kind: str) -> dict[str, Any]:
    for step in trajectory.get("steps", []) or []:
        if step.get("kind") == kind:
            return step
    return {}


def _normalization_summary(checkpoints: dict[str, dict[str, Any]]) -> dict[str, Any]:
    output = _checkpoint_output(checkpoints, "checkpoint_02_query_normalization")
    if isinstance(output, dict) and output:
        return output
    return {"normalized_query": _value(None, "no normalization checkpoint recorded")}


def _tokens_summary(checkpoints: dict[str, dict[str, Any]], nlp_step: dict[str, Any]) -> dict[str, Any]:
    output = _checkpoint_output(checkpoints, "checkpoint_03_query_tokens")
    if isinstance(output, dict) and output:
        return output
    if isinstance(nlp_step.get("tokens"), dict):
        return nlp_step["tokens"]
    return {"tokens": _value(None, "no tokens recorded")}


def _candidate_tables(checkpoints: dict[str, dict[str, Any]], nlp_step: dict[str, Any]) -> Any:
    output = _checkpoint_output(checkpoints, "checkpoint_04_relevance_scoring")
    if isinstance(output, dict):
        return output.get("top_tables") or output.get("tables")
    context_output = _checkpoint_output(checkpoints, "checkpoint_07_context_card")
    if isinstance(context_output, dict):
        return context_output.get("selected_tables") or context_output.get("tables")
    return (nlp_step.get("relevance") or {}).get("tables")


def _candidate_apis(checkpoints: dict[str, dict[str, Any]], nlp_step: dict[str, Any]) -> Any:
    output = _checkpoint_output(checkpoints, "checkpoint_04_relevance_scoring")
    if isinstance(output, dict):
        return output.get("top_apis") or output.get("apis")
    context_output = _checkpoint_output(checkpoints, "checkpoint_07_context_card")
    if isinstance(context_output, dict):
        return context_output.get("selected_apis") or context_output.get("apis")
    return (nlp_step.get("relevance") or {}).get("apis")


def _find_context_mode(trajectory: dict[str, Any], checkpoints: dict[str, dict[str, Any]]) -> str:
    for checkpoint in checkpoints.values():
        for key in ("output", "input_summary", "metrics"):
            found = _find_nested(checkpoint.get(key), "context_mode")
            if found not in (None, "", [], {}):
                return str(found)
    found = _find_nested(trajectory, "context_mode")
    if found not in (None, "", [], {}):
        return str(found)
    return _value(None, "no candidate context mode recorded")


def _estimated_context_tokens(trajectory: dict[str, Any]) -> Any:
    for key in ("metadata_tokens", "prompt_context_tokens"):
        if trajectory.get(key) is not None:
            return trajectory.get(key)
    metadata_step = _first_step(trajectory, "metadata")
    return metadata_step.get("estimated_tokens")


def _api_endpoint(api_call: dict[str, Any]) -> str:
    if not api_call:
        return _value(None, "no API call in trajectory")
    method = api_call.get("method") or _nested(api_call, ["result", "method"]) or "GET"
    url = api_call.get("url") or _nested(api_call, ["result", "endpoint"]) or _nested(api_call, ["result", "url"])
    return f"{method} {url}" if url else _value(None, "API endpoint missing")


def _validation_status(step: dict[str, Any]) -> str:
    if not step:
        return _value(None, "no validation step recorded")
    validation = step.get("validation") or {}
    if validation.get("ok") is True:
        return "ok"
    if validation.get("ok") is False:
        return "failed: " + "; ".join(validation.get("errors") or [])
    return _value(None, "validation status missing")


def _api_dry_run(api_calls: list[dict[str, Any]]) -> Any:
    if not api_calls:
        return _value(None, "no API call in trajectory")
    return any(bool(_nested(call, ["result", "dry_run"]) or call.get("dry_run_only")) for call in api_calls)


def _api_live_evidence(api_calls: list[dict[str, Any]]) -> Any:
    if not api_calls:
        return _value(None, "no API call in trajectory")
    return any(bool(_nested(call, ["result", "ok"]) and not _nested(call, ["result", "dry_run"])) for call in api_calls)


def _endpoint_repair(api_calls: list[dict[str, Any]]) -> Any:
    repairs = []
    for call in api_calls:
        repair = call.get("endpoint_repair") or _nested(call, ["result", "endpoint_repair"])
        if repair:
            repairs.append(repair)
    return repairs


def _evidence_available(trajectory: dict[str, Any], sql_calls: list[dict[str, Any]], api_calls: list[dict[str, Any]]) -> Any:
    if trajectory.get("successful_evidence_count") is not None:
        return trajectory.get("successful_evidence_count", 0) > 0
    for call in sql_calls:
        if (_nested(call, ["result", "row_count"]) or 0) > 0:
            return True
    for call in api_calls:
        result = call.get("result") or {}
        if result.get("ok") and not result.get("dry_run"):
            return True
    if not sql_calls and not api_calls:
        return _value(None, "no tool calls in trajectory")
    return False


def _successful_evidence_count(trajectory: dict[str, Any], sql_calls: list[dict[str, Any]], api_calls: list[dict[str, Any]]) -> Any:
    if trajectory.get("successful_evidence_count") is not None:
        return trajectory.get("successful_evidence_count")
    count = 0
    count += sum(1 for call in sql_calls if (_nested(call, ["result", "row_count"]) or 0) > 0)
    count += sum(1 for call in api_calls if _nested(call, ["result", "ok"]) and not _nested(call, ["result", "dry_run"]))
    return count


def _valid_tool_calls(trajectory: dict[str, Any], sql_calls: list[dict[str, Any]], api_calls: list[dict[str, Any]]) -> Any:
    if trajectory.get("llm_tool_calls"):
        return sum(1 for call in trajectory.get("llm_tool_calls", []) if call.get("tool_validation_ok") or call.get("validation_ok"))
    return sum(1 for call in sql_calls + api_calls if (call.get("validation") or {}).get("ok") is True)


def _zero_row_uncertain(sql_calls: list[dict[str, Any]]) -> Any:
    if not sql_calls:
        return _value(None, "no SQL call in trajectory")
    return any((_nested(call, ["result", "row_count"]) == 0) for call in sql_calls)


def _empty_result_uncertainty(trajectory: dict[str, Any]) -> Any:
    answer = str(trajectory.get("final_answer") or "")
    if "executed query did not find evidence" in answer.lower():
        return "present"
    return None


def _evidence_explanation(dry_run: Any, evidence_available: Any) -> str:
    if dry_run is True:
        return "API tool was invoked and validated, but live evidence was unavailable because Adobe credentials were missing."
    if evidence_available is True:
        return "At least one SQL/API result provided evidence for answer construction."
    if evidence_available is False:
        return "No successful evidence was available from executed tools."
    return str(evidence_available)


def _first_checkpoint_effect(trajectory: dict[str, Any]) -> dict[str, str]:
    for checkpoint in trajectory.get("checkpoints", []) or []:
        correctness = checkpoint.get("correctness_role")
        efficiency = checkpoint.get("efficiency_role")
        effect = checkpoint.get("effect")
        if correctness or efficiency or effect:
            return {
                "checkpoint_id": str(checkpoint.get("checkpoint_id") or "n/a"),
                "correctness_role": _value(correctness, "no correctness role recorded"),
                "efficiency_role": _value(efficiency, "no efficiency role recorded"),
                "effect": _value(effect, "no dataflow effect recorded"),
            }
    return {
        "checkpoint_id": "n/a",
        "correctness_role": "n/a - no checkpoint correctness role recorded",
        "efficiency_role": "n/a - no checkpoint efficiency role recorded",
        "effect": "n/a - no checkpoint effect recorded",
    }


def _checkpoint_output(checkpoints: dict[str, dict[str, Any]], checkpoint_id: str) -> Any:
    checkpoint = checkpoints.get(checkpoint_id) or {}
    return checkpoint.get("output") or checkpoint.get("output_summary")


def _find_nested(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        if key in value:
            return value[key]
        for item in value.values():
            found = _find_nested(item, key)
            if found not in (None, "", [], {}):
                return found
    if isinstance(value, list):
        for item in value:
            found = _find_nested(item, key)
            if found not in (None, "", [], {}):
                return found
    return None


def _nested(value: Any, keys: list[str]) -> Any:
    current = value
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _value(value: Any, reason: str) -> Any:
    if value in (None, "", [], {}):
        return f"n/a - {reason}"
    return value


def _brief(value: Any, limit: int = 260) -> str:
    if value in (None, "", {}, []):
        return ""
    compact = compact_preview(value, limit)
    if isinstance(compact, (dict, list)):
        return json.dumps(compact, sort_keys=True, default=str)
    return str(compact)


def _preview(value: Any, limit: int = 220) -> str:
    if value in (None, ""):
        return ""
    text = str(value).replace("\n", " ")
    return text[:limit] + ("..." if len(text) > limit else "")


def _variant_label(trajectory: dict[str, Any]) -> str:
    variant = trajectory.get("baseline_variant")
    if variant == "raw":
        return "Raw"
    if variant == "guided":
        return "Guided"
    system = trajectory.get("system") or trajectory.get("strategy")
    if system == "LLM_CONTROLLER_OPTIMIZED_AGENT":
        return "Optimized Controller"
    return _value(variant, "not a baseline variant")


def _m(text: str) -> str:
    return html.escape(str(text).replace("\n", " "))[:180]


def _md(value: Any) -> str:
    text = "" if value is None else str(value)
    return text.replace("|", "\\|").replace("\n", " ")[:800]


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", text.lower()).strip("_")
    return slug or "unknown"
