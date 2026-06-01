from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .config import Config, ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2
from .executor import AgentExecutor
from .llm_client import PioneerChatLLMClient
from .llm_unified_planner import _route_gate_payload
from .trajectory import redact_secrets


DEFAULT_PIONEER_MODEL_SWEEP = [
    "Qwen3 4B Instruct 2507",
    "Qwen3 8B",
    "Qwen3.5 9B",
    "Qwen3.6 27B",
    "Qwen3.6 Flash",
    "Qwen3.6 Plus",
    "Qwen3.6 35B A3B",
    "Qwen3.7 Max",
    "Claude Haiku 4.5",
    "DeepSeek V4 Flash",
    "DeepSeek V4 Pro",
    "Llama 3.1 8B Instruct",
    "Llama 3.2 3B Instruct",
    "Mistral Nemo Instruct 2407",
    "Gemma 4 E4B It",
    "Gemma 4 31B It",
    "MiniMax M2.7",
    "Kimi K2.6",
    "GLM 5.1",
    "GPT-OSS 20B",
    "GPT-OSS 120B",
]

DEFAULT_PIONEER_MODEL_GROUPS = {
    "Qwen3 4B Instruct 2507": "qwen",
    "Qwen3 8B": "qwen",
    "Qwen3.5 9B": "qwen",
    "Qwen3.6 27B": "qwen",
    "Qwen3.6 Flash": "qwen",
    "Qwen3.6 Plus": "qwen",
    "Qwen3.6 35B A3B": "qwen",
    "Qwen3.7 Max": "qwen",
    "Claude Haiku 4.5": "anthropic_fast_small",
    "DeepSeek V4 Flash": "deepseek_cheap_fast",
    "DeepSeek V4 Pro": "deepseek",
    "Qwen3 4B Instruct 2507": "qwen_small_instruct",
    "Llama 3.1 8B Instruct": "llama_small_instruct",
    "Llama 3.2 3B Instruct": "llama_small_instruct",
    "Mistral Nemo Instruct 2407": "mistral_compact_instruct",
    "Gemma 4 E4B It": "gemma_small_instruct",
    "Gemma 4 31B It": "gemma",
    "MiniMax M2.7": "minimax",
    "Kimi K2.6": "kimi",
    "GLM 5.1": "glm",
    "GPT-OSS 20B": "gpt_oss",
    "GPT-OSS 120B": "gpt_oss",
}

GPT4_FAMILY_EXCLUDED_MODELS = {
    "Gpt 4o",
    "gpt-4o",
    "Gpt 4o Mini",
    "gpt-4o-mini",
    "Gpt 4.1",
    "Gpt 4.1 Mini",
    "Gpt 4.1 Nano",
    "gpt-4.1",
    "gpt-4.1-mini",
    "gpt-4.1-nano",
}

EXCLUDED_DEFAULT_PIONEER_MODELS = {
    *GPT4_FAMILY_EXCLUDED_MODELS,
    "Gpt 5 Mini",
    "Gpt 5 Nano",
    "Gpt 5.1",
    "Gpt 5.4",
    "Gpt 5.5",
    "Claude Opus",
    "Claude Opus 4",
    "Claude Opus 4.5",
    "Claude Sonnet",
    "Claude Sonnet 4",
    "Claude Sonnet 4.5",
    "Qwen Max",
    "Qwen Plus",
    "Gemini 3.5 Flash",
}

PIONEER_SWEEP_PROMPTS = [
    {
        "id": "pure_concept_schema",
        "prompt": "What is a schema?",
        "expected_kind": "PURE_DIRECT",
    },
    {
        "id": "pure_meta_list_schemas",
        "prompt": 'In the phrase "list schemas", what does "list" mean?',
        "expected_kind": "PURE_DIRECT",
    },
    {
        "id": "ambiguous_user_schemas",
        "prompt": "What schemas do I have?",
        "expected_kind": "EVIDENCE",
    },
    {
        "id": "local_schema_count",
        "prompt": "How many schema records are in the local snapshot?",
        "expected_kind": "EVIDENCE",
    },
    {
        "id": "birthday_message_published",
        "prompt": 'When was the journey "Birthday Message" published?',
        "expected_kind": "EVIDENCE",
    },
    {
        "id": "mixed_inactive_journeys",
        "prompt": "Explain what inactive journey means and show inactive journeys.",
        "expected_kind": "EVIDENCE",
    },
    {
        "id": "compare_local_live_birthday_status",
        "prompt": "Compare local and live status of Birthday Message if both are available.",
        "expected_kind": "EVIDENCE",
    },
]

SLOW_ROUTE_PROBE_MODELS = {"DeepSeek V4 Flash", "GLM 5.1"}
ROUTE_GATE_PROBE_PROMPTS = [
    {"id": "probe_concept", "prompt": "What is a schema?", "expected_route": "LLM_DIRECT"},
    {"id": "probe_data", "prompt": "What schemas do I have?", "expected_route": "EVIDENCE_PIPELINE"},
]


def is_gpt4_family_model(*values: str | None) -> bool:
    """Return True for GPT-4/Gpt 4 display names or model IDs only."""
    for value in values:
        normalized = _normalize_model_family_text(value)
        if not normalized:
            continue
        if normalized.startswith(("gpt4", "gpt4o", "gpt41")):
            return True
    return False


def parse_pioneer_model_sweep(env_value: str | None = None) -> list[str]:
    raw = os.getenv("PIONEER_MODEL_SWEEP") if env_value is None else env_value
    if raw:
        return [item.strip() for item in raw.split(",") if item.strip()]
    return list(DEFAULT_PIONEER_MODEL_SWEEP)


def parse_pioneer_model_id_map(env_value: str | None = None) -> dict[str, str]:
    raw = env_value
    if raw is None:
        raw = os.getenv("PIONEER_MODEL_ID_MAP_JSON") or os.getenv("PIONEER_MODEL_ID_MAP")
    if raw is None:
        suggested = Path("outputs/reports/pioneer_model_sweep/pioneer_model_id_map_suggested.json")
        if suggested.exists():
            try:
                payload = json.loads(suggested.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    mapping = payload.get("mapping") if isinstance(payload.get("mapping"), dict) else payload
                    return {
                        str(key).strip(): str(value).strip()
                        for key, value in mapping.items()
                        if isinstance(value, str) and str(key).strip() and value.strip()
                    }
            except Exception:
                return {}
    if not raw:
        return {}
    raw = raw.strip()
    if not raw:
        return {}
    if raw.startswith("{"):
        try:
            payload = json.loads(raw)
            if isinstance(payload, dict):
                if isinstance(payload.get("mapping"), dict):
                    payload = payload["mapping"]
                return {str(key).strip(): str(value).strip() for key, value in payload.items() if str(key).strip() and str(value).strip()}
        except Exception:
            return {}
    mapping: dict[str, str] = {}
    for item in raw.split(","):
        if "=" not in item:
            continue
        label, model_id = item.split("=", 1)
        label = label.strip()
        model_id = model_id.strip()
        if label and model_id:
            mapping[label] = model_id
    return mapping


def _normalize_model_family_text(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def safe_model_name(model: str) -> str:
    safe = re.sub(r"[^a-z0-9]+", "_", model.lower()).strip("_")
    return safe or "model"


def run_pioneer_model_sweep(
    config: Config,
    *,
    models: list[str] | None = None,
    report_dir: Path | None = None,
) -> dict[str, Any]:
    selected_models = models or parse_pioneer_model_sweep()
    destination = report_dir or (config.outputs_dir / "reports" / "pioneer_model_sweep")
    results = [_run_one_model(config, model, destination) for model in selected_models]
    paths = write_pioneer_model_sweep_reports(destination, results)
    return {
        "models": results,
        "paths": {key: str(value) for key, value in paths.items()},
    }


def _run_one_model(config: Config, model: str, report_dir: Path) -> dict[str, Any]:
    started = time.perf_counter()
    safe_name = safe_model_name(model)
    model_id = parse_pioneer_model_id_map().get(model, model)
    log_lines: list[str] = [f"model={model}", f"group={DEFAULT_PIONEER_MODEL_GROUPS.get(model, 'custom')}"]
    with _temporary_env(
        {
            "DASHAGENT_LLM_PROVIDER": "pioneer_chat",
            "PIONEER_MODEL": model,
            "PIONEER_MODEL_ID": model_id,
            "PIONEER_MODEL_DISPLAY": model,
            "PIONEER_STORE": os.getenv("PIONEER_STORE", "false"),
        }
    ):
        _reset_llm_client_for_model()
        availability = _with_model_context(_availability_probe(model_id), model, safe_name, model_id)
        log_lines.append("availability=" + json.dumps(redact_secrets(availability), sort_keys=True))
        if not availability.get("available"):
            result = _empty_model_result(model, availability, started, model_id=model_id)
            result["log"] = "\n".join(log_lines) + "\n"
            _write_per_model(report_dir, result)
            return result
        route_gate_probe: dict[str, Any] | None = None
        if model in SLOW_ROUTE_PROBE_MODELS:
            route_gate_probe = _route_gate_short_probe(model_id)
            route_gate_probe = _with_model_context(route_gate_probe, model, safe_name, model_id)
            log_lines.append("route_gate_probe=" + json.dumps(redact_secrets(route_gate_probe), sort_keys=True))
            if not route_gate_probe.get("usable"):
                result = _empty_model_result(model, availability, started, model_id=model_id)
                result["route_gate_probe"] = route_gate_probe
                result["metrics"]["route_gate_probe_usable"] = False
                result["metrics"]["route_gate_probe_failures"] = len(route_gate_probe.get("prompt_results") or [])
                result["log"] = "\n".join(log_lines) + "\n"
                _write_per_model(report_dir, result)
                return result
        executor = AgentExecutor(config)
        prompt_results: list[dict[str, Any]] = []
        semantic_probe_results: list[dict[str, Any]] = [
            _with_model_context(_semantic_json_probe(model_id, prompt_case["prompt"]), model, safe_name, model_id)
            for prompt_case in PIONEER_SWEEP_PROMPTS
        ]
        if semantic_probe_results and all(bool(row.get("parse_error")) for row in semantic_probe_results):
            for semantic_probe in semantic_probe_results:
                log_lines.append("semantic_probe=" + json.dumps(redact_secrets(semantic_probe), sort_keys=True))
            log_lines.append("semantic_probe_all_failed_closed=true")
        for prompt_case in PIONEER_SWEEP_PROMPTS:
            prompt_start = time.perf_counter()
            try:
                run_result = executor.run(
                    prompt_case["prompt"],
                    strategy=ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2,
                    query_id=f"pioneer_sweep_{safe_name}_{prompt_case['id']}",
                    output_dir=report_dir / "runs" / safe_name / prompt_case["id"],
                )
                trajectory_annotated = _annotate_sweep_trajectory(run_result.get("output_dir"), model, safe_name, model_id)
                prompt_result = _summarize_prompt_result(prompt_case, run_result, time.perf_counter() - prompt_start)
                prompt_result["trajectory_annotated"] = trajectory_annotated
            except Exception as exc:
                prompt_result = {
                    "prompt_id": prompt_case["id"],
                    "prompt": prompt_case["prompt"],
                    "expected_kind": prompt_case["expected_kind"],
                    "pass": False,
                    "error": redact_secrets(f"{type(exc).__name__}: {exc}"),
                    "latency_sec": round(time.perf_counter() - prompt_start, 4),
                }
            prompt_result = _with_model_context(prompt_result, model, safe_name, model_id)
            log_lines.append("prompt_result=" + json.dumps(redact_secrets(prompt_result), sort_keys=True))
            prompt_results.append(prompt_result)
        metrics = _aggregate_metrics(prompt_results, semantic_probe_results, started)
        result = {
            "model": model,
            "pioneer_model": model,
            "pioneer_model_id": model_id,
            "safe_model_name": safe_name,
            "model_sweep_run_id": safe_name,
            "group": DEFAULT_PIONEER_MODEL_GROUPS.get(model, "custom"),
            "availability": availability,
            "route_gate_probe": route_gate_probe,
            "metrics": metrics,
            "semantic_probe_results": semantic_probe_results,
            "prompt_results": prompt_results,
            "log": "\n".join(log_lines) + "\n",
        }
        _write_per_model(report_dir, result)
        return result


def _availability_probe(model: str) -> dict[str, Any]:
    client = PioneerChatLLMClient(model=model, timeout_seconds=int(os.getenv("PIONEER_TIMEOUT_SEC", "30")))
    if not client.available():
        return {
            "available": False,
            "attempted": False,
            "reason": "PIONEER_API_KEY is not set",
            "model": model,
        }
    started = time.perf_counter()
    response = client.generate_messages(
        [
            {"role": "system", "content": "You are a concise availability probe."},
            {"role": "user", "content": "Reply exactly: ok"},
        ],
        max_tokens=8,
    )
    return redact_secrets(
        {
            "available": bool(response.get("ok")),
            "attempted": True,
            "model": model,
            "provider": response.get("provider"),
            "transport": response.get("transport"),
            "finish_reason": response.get("finish_reason"),
            "error_category": response.get("error_category"),
            "error": response.get("error"),
            "latency_sec": round(time.perf_counter() - started, 4),
        }
    )


def _semantic_json_probe(model: str, prompt: str) -> dict[str, Any]:
    started = time.perf_counter()
    client = PioneerChatLLMClient(model=model, timeout_seconds=int(os.getenv("PIONEER_TIMEOUT_SEC", "30")))
    if not client.available():
        return {
            "prompt": prompt,
            "parse_error": True,
            "route": "EVIDENCE_PIPELINE",
            "requires_evidence": True,
            "available": False,
            "latency_sec": 0.0,
        }
    schema_hint = {
        "intent": "CONCEPT | COUNT | LIST | STATUS | DATE | RELATIONSHIP | MIXED | UNKNOWN",
        "route": "LLM_DIRECT | LLM_SAFE_DIRECT | EVIDENCE_PIPELINE",
        "requires_evidence": True,
        "pure_no_evidence": True,
        "confidence": 0.0,
        "reason": "short string",
    }
    raw_result = client.complete_json(
        (
            "Classify this prompt for DASHSys pre-evidence routing. "
            "Concrete user data, counts, lists, status, dates, live/current/platform/API prompts, "
            "and mixed concept+data prompts must route to EVIDENCE_PIPELINE."
        ),
        prompt,
        schema_hint=schema_hint,
        max_tokens=160,
    )
    if isinstance(raw_result, dict):
        result = dict(raw_result)
    else:
        result = {
            "parse_error": True,
            "route": "EVIDENCE_PIPELINE",
            "requires_evidence": True,
            "pure_no_evidence": False,
            "confidence": 0.0,
            "raw_type": type(raw_result).__name__,
        }
    result.update(
        {
            "prompt": prompt,
            "model": model,
            "latency_sec": round(time.perf_counter() - started, 4),
        }
    )
    return redact_secrets(result)


def _route_gate_short_probe(model: str) -> dict[str, Any]:
    if os.getenv("PIONEER_ROUTE_GATE_PROBE_SUBPROCESS", "true").strip().lower() not in {"0", "false", "no", "off"}:
        return _route_gate_short_probe_subprocess(model)
    return _route_gate_short_probe_inline(model)


def _route_gate_short_probe_subprocess(model: str) -> dict[str, Any]:
    timeout_seconds = int(os.getenv("PIONEER_ROUTE_GATE_PROBE_TOTAL_TIMEOUT_SEC", "35"))
    code = (
        "import json, os, sys\n"
        "from dashagent.pioneer_model_sweep import _route_gate_short_probe_inline\n"
        "os.environ['PIONEER_ROUTE_GATE_PROBE_SUBPROCESS']='false'\n"
        "print(json.dumps(_route_gate_short_probe_inline(sys.argv[1]), sort_keys=True))\n"
    )
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            [sys.executable, "-c", code, model],
            cwd=str(Path.cwd()),
            env=dict(os.environ),
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "usable": False,
            "error_category": "route_gate_timeout",
            "prompt_results": [],
            "latency_sec": round(time.perf_counter() - started, 4),
        }
    if completed.returncode != 0:
        return redact_secrets(
            {
                "usable": False,
                "error_category": "route_gate_error",
                "prompt_results": [],
                "stderr_tail": completed.stderr[-600:],
                "latency_sec": round(time.perf_counter() - started, 4),
            }
        )
    try:
        parsed = json.loads(completed.stdout.strip().splitlines()[-1])
        if isinstance(parsed, dict):
            return redact_secrets(parsed)
    except Exception as exc:
        return redact_secrets(
            {
                "usable": False,
                "error_category": "route_gate_parse_failure",
                "prompt_results": [],
                "error": str(exc),
                "latency_sec": round(time.perf_counter() - started, 4),
            }
        )
    return {
        "usable": False,
        "error_category": "route_gate_parse_failure",
        "prompt_results": [],
        "latency_sec": round(time.perf_counter() - started, 4),
    }


def _route_gate_short_probe_inline(model: str) -> dict[str, Any]:
    started = time.perf_counter()
    timeout_seconds = int(os.getenv("PIONEER_ROUTE_GATE_PROBE_TIMEOUT_SEC", "10"))
    client = PioneerChatLLMClient(model=model, timeout_seconds=timeout_seconds)
    if not client.available():
        return {
            "usable": False,
            "error_category": "provider_unavailable",
            "prompt_results": [],
            "latency_sec": 0.0,
        }
    prompt_results: list[dict[str, Any]] = []
    for case in ROUTE_GATE_PROBE_PROMPTS:
        prompt_started = time.perf_counter()
        try:
            result = client.complete_json(
                "Return ONLY valid JSON for DASHSys V2 RouteGate. Do not generate SQL or API.",
                json.dumps(_route_gate_payload(case["prompt"], repair_context=None), sort_keys=True),
                schema_hint={
                    "route_allowed_values": ["LLM_DIRECT", "EVIDENCE_PIPELINE"],
                    "evidence_order_allowed_values": ["NO_EVIDENCE", "NEED_EVIDENCE"],
                    "direct_answer": "string or null",
                    "reason": "short string",
                },
                max_tokens=160,
            )
            if not isinstance(result, dict):
                result = {"parse_error": True, "route": "EVIDENCE_PIPELINE", "error": f"non_object:{type(result).__name__}"}
        except TimeoutError as exc:
            result = {"parse_error": True, "route": "EVIDENCE_PIPELINE", "error_category": "route_gate_timeout", "error": str(exc)}
        except Exception as exc:
            result = {"parse_error": True, "route": "EVIDENCE_PIPELINE", "error_category": "route_gate_error", "error": redact_secrets(str(exc))}
        route = str(result.get("route") or "").strip().upper()
        parse_error = bool(result.get("parse_error")) or route not in {"LLM_DIRECT", "EVIDENCE_PIPELINE"}
        prompt_results.append(
            redact_secrets(
                {
                    "prompt_id": case["id"],
                    "prompt": case["prompt"],
                    "expected_route": case["expected_route"],
                    "route": route or "EVIDENCE_PIPELINE",
                    "parse_error": parse_error,
                    "pass": (not parse_error) and route == case["expected_route"],
                    "error_category": result.get("error_category"),
                    "latency_sec": round(time.perf_counter() - prompt_started, 4),
                }
            )
        )
    usable = bool(prompt_results) and all((not row.get("parse_error")) for row in prompt_results)
    return redact_secrets(
        {
            "usable": usable,
            "error_category": None if usable else "route_gate_parse_failure",
            "prompt_results": prompt_results,
            "latency_sec": round(time.perf_counter() - started, 4),
        }
    )


def _summarize_prompt_result(prompt_case: dict[str, str], run_result: dict[str, Any], latency_sec: float) -> dict[str, Any]:
    checkpoints = run_result.get("checkpoints") or []
    checkpoint_names = {str(item.get("checkpoint_id")) for item in checkpoints if isinstance(item, dict)}
    boundary = _checkpoint_output(checkpoints, "checkpoint_evidence_pipeline_bypass") or _checkpoint_output(
        checkpoints, "checkpoint_evidence_pipeline_boundary"
    )
    sql_calls = sum(1 for row in run_result.get("tool_results") or [] if row.get("type") == "sql")
    api_calls = sum(1 for row in run_result.get("tool_results") or [] if row.get("type") == "api")
    evidence_pipeline_bypassed = bool(boundary.get("evidence_pipeline_bypassed"))
    evidence_bus_built = bool(boundary.get("evidence_bus_built")) or "checkpoint_14_evidence_bus" in checkpoint_names
    post_router_ran = bool(boundary.get("post_evidence_answer_router_ran")) or bool(
        {"checkpoint_broad_question_classifier", "checkpoint_answer_intent_router", "checkpoint_hybrid_answer_composer"}
        & checkpoint_names
    )
    declared_pass_count = _declared_pass_count(checkpoints)
    pass_results_count = _pass_results_count(checkpoints)
    result_bundle_built = bool("checkpoint_result_bundle" in checkpoint_names)
    answer_gate_metrics = _answer_gate_metrics(checkpoints)
    planner_metrics = _weak_protocol_planner_metrics(checkpoints)
    tool_gate_metrics = _tool_gate_metrics(checkpoints)
    final_syntax_gate_failures = answer_gate_metrics["answer_syntax_gate_final_failures"]
    final_semantic_gate_failures = answer_gate_metrics["answer_semantic_gate_final_failures"]
    unsupported_claims = _unsupported_claim_count(checkpoints)
    expected_kind = prompt_case["expected_kind"]
    if expected_kind == "PURE_DIRECT":
        passed = (
            sql_calls == 0
            and api_calls == 0
            and evidence_pipeline_bypassed
            and not evidence_bus_built
            and not post_router_ran
            and final_syntax_gate_failures == 0
            and final_semantic_gate_failures == 0
            and unsupported_claims == 0
        )
    else:
        evidence_path_exercised = evidence_bus_built or result_bundle_built or declared_pass_count > 0 or sql_calls > 0 or api_calls > 0
        passed = (
            (not evidence_pipeline_bypassed)
            and evidence_path_exercised
            and declared_pass_count > 0
            and final_syntax_gate_failures == 0
            and final_semantic_gate_failures == 0
            and unsupported_claims == 0
        )
    return redact_secrets(
        {
            "prompt_id": prompt_case["id"],
            "prompt": prompt_case["prompt"],
            "expected_kind": expected_kind,
            "pass": bool(passed),
            "final_answer": run_result.get("final_answer"),
            "sql_calls": sql_calls,
            "api_calls": api_calls,
            "evidence_pipeline_bypassed": evidence_pipeline_bypassed,
            "evidence_bus_built": evidence_bus_built,
            "result_bundle_built": result_bundle_built,
            "post_evidence_answer_router_ran": post_router_ran,
            "declared_pass_count": declared_pass_count,
            "pass_results_count": pass_results_count,
            **planner_metrics,
            **tool_gate_metrics,
            **answer_gate_metrics,
            "final_syntax_gate_failures": final_syntax_gate_failures,
            "final_semantic_gate_failures": final_semantic_gate_failures,
            "unsupported_claims": unsupported_claims,
            "llm_direct": evidence_pipeline_bypassed,
            "evidence_pipeline": not evidence_pipeline_bypassed,
            "latency_sec": round(latency_sec, 4),
            "output_dir": str(run_result.get("output_dir") or ""),
        }
    )


def _aggregate_metrics(
    prompt_results: list[dict[str, Any]],
    semantic_probe_results: list[dict[str, Any]],
    started: float,
) -> dict[str, Any]:
    data_prompt_fail_open = [
        row
        for row in prompt_results
        if row.get("expected_kind") == "EVIDENCE" and bool(row.get("evidence_pipeline_bypassed"))
    ]
    evidence_rows = [row for row in prompt_results if row.get("expected_kind") == "EVIDENCE"]
    planner_usable_rows = [row for row in evidence_rows if int(row.get("declared_pass_count") or 0) > 0]
    all_final_gates_failed = bool(prompt_results) and all(
        int(row.get("final_syntax_gate_failures") or 0) > 0 or int(row.get("final_semantic_gate_failures") or 0) > 0
        for row in prompt_results
    )
    return {
        "json_parse_failures": sum(1 for row in semantic_probe_results if bool(row.get("parse_error"))),
        "semantic_fallback_count": sum(1 for row in semantic_probe_results if bool(row.get("parse_error"))),
        "llm_direct_count": sum(1 for row in prompt_results if bool(row.get("llm_direct"))),
        "evidence_pipeline_count": sum(1 for row in prompt_results if bool(row.get("evidence_pipeline"))),
        "evidence_pipeline_bypassed_count": sum(1 for row in prompt_results if bool(row.get("evidence_pipeline_bypassed"))),
        "evidence_bus_built_count": sum(1 for row in prompt_results if bool(row.get("evidence_bus_built"))),
        "evidence_bus_non_empty_count": sum(1 for row in prompt_results if int(row.get("pass_results_count") or 0) > 0),
        "result_bundle_built_count": sum(1 for row in prompt_results if bool(row.get("result_bundle_built"))),
        "declared_pass_count": sum(int(row.get("declared_pass_count") or 0) for row in prompt_results),
        "route_card_success_count": sum(1 for row in prompt_results if bool(row.get("route_card_success"))),
        "task_ledger_success_count": sum(1 for row in prompt_results if bool(row.get("task_ledger_success"))),
        "candidate_card_success_count": sum(int(row.get("candidate_card_success") or 0) for row in prompt_results),
        "sql_gate_failures": sum(int(row.get("sql_gate_failures") or 0) for row in prompt_results),
        "api_gate_failures": sum(int(row.get("api_gate_failures") or 0) for row in prompt_results),
        "planner_usable_count": len(planner_usable_rows),
        "answer_syntax_gate_initial_failures": sum(int(row.get("answer_syntax_gate_initial_failures") or 0) for row in prompt_results),
        "answer_semantic_gate_initial_failures": sum(int(row.get("answer_semantic_gate_initial_failures") or 0) for row in prompt_results),
        "answer_repair_attempts": sum(int(row.get("answer_repair_attempts") or 0) for row in prompt_results),
        "answer_syntax_gate_final_failures": sum(int(row.get("answer_syntax_gate_final_failures") or 0) for row in prompt_results),
        "answer_semantic_gate_final_failures": sum(int(row.get("answer_semantic_gate_final_failures") or 0) for row in prompt_results),
        "answer_repaired_successes": sum(int(row.get("answer_repaired_successes") or 0) for row in prompt_results),
        "final_syntax_gate_failures": sum(int(row.get("final_syntax_gate_failures") or 0) for row in prompt_results),
        "final_semantic_gate_failures": sum(int(row.get("final_semantic_gate_failures") or 0) for row in prompt_results),
        "final_gates_all_failed": all_final_gates_failed,
        "post_evidence_answer_router_ran_count": sum(
            1 for row in prompt_results if bool(row.get("post_evidence_answer_router_ran"))
        ),
        "no_tool_fp": len(data_prompt_fail_open),
        "api_required_underuse": 0,
        "unsupported_claims": sum(int(row.get("unsupported_claims") or 0) for row in prompt_results),
        "focused_smoke_pass": all(bool(row.get("pass")) for row in prompt_results) if prompt_results else False,
        "latency_sec": round(time.perf_counter() - started, 4),
    }


def _empty_model_result(model: str, availability: dict[str, Any], started: float, *, model_id: str | None = None) -> dict[str, Any]:
    safe_name = safe_model_name(model)
    active_model_id = model_id or model
    return {
        "model": model,
        "pioneer_model": model,
        "pioneer_model_id": active_model_id,
        "safe_model_name": safe_name,
        "model_sweep_run_id": safe_name,
        "group": DEFAULT_PIONEER_MODEL_GROUPS.get(model, "custom"),
        "availability": availability,
        "metrics": {
            "json_parse_failures": 0,
            "semantic_fallback_count": 0,
            "llm_direct_count": 0,
            "evidence_pipeline_count": 0,
            "evidence_pipeline_bypassed_count": 0,
            "evidence_bus_built_count": 0,
            "evidence_bus_non_empty_count": 0,
            "result_bundle_built_count": 0,
            "declared_pass_count": 0,
            "planner_usable_count": 0,
            "answer_syntax_gate_initial_failures": 0,
            "answer_semantic_gate_initial_failures": 0,
            "answer_repair_attempts": 0,
            "answer_syntax_gate_final_failures": 0,
            "answer_semantic_gate_final_failures": 0,
            "answer_repaired_successes": 0,
            "final_syntax_gate_failures": 0,
            "final_semantic_gate_failures": 0,
            "final_gates_all_failed": False,
            "no_tool_fp": 0,
            "api_required_underuse": 0,
            "unsupported_claims": 0,
            "focused_smoke_pass": False,
            "latency_sec": round(time.perf_counter() - started, 4),
        },
        "semantic_probe_results": [],
        "prompt_results": [],
    }


def _with_model_context(payload: dict[str, Any], model: str, safe_name: str, model_id: str | None = None) -> dict[str, Any]:
    contextualized = dict(payload)
    contextualized["model"] = model
    contextualized["pioneer_model"] = model
    contextualized["pioneer_model_id"] = model_id or model
    contextualized["model_sweep_run_id"] = safe_name
    return contextualized


def _reset_llm_client_for_model() -> None:
    # get_llm_client() is currently uncached; this hook keeps the sweep safe if a
    # future shared cache is added to the provider module.
    try:
        from . import llm_client as llm_client_module
    except Exception:
        return
    for name in ("reset_llm_client_cache", "clear_llm_client_cache"):
        reset = getattr(llm_client_module, name, None)
        if callable(reset):
            try:
                reset()
            except Exception:
                return


def _annotate_sweep_trajectory(output_dir: Any, model: str, safe_name: str, model_id: str | None = None) -> bool:
    if not output_dir:
        return False
    try:
        trajectory_path = Path(output_dir) / "trajectory.json"
        if not trajectory_path.exists():
            return False
        payload = json.loads(trajectory_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return False
        payload["pioneer_model"] = model
        payload["pioneer_model_id"] = model_id or model
        payload["model_sweep_run_id"] = safe_name
        diagnostics = payload.get("diagnostics") if isinstance(payload.get("diagnostics"), dict) else {}
        diagnostics["pioneer_model"] = model
        diagnostics["pioneer_model_id"] = model_id or model
        diagnostics["model_sweep_run_id"] = safe_name
        diagnostics["pioneer_model_sweep"] = True
        payload["diagnostics"] = diagnostics
        trajectory_path.write_text(json.dumps(redact_secrets(payload), indent=2, sort_keys=True), encoding="utf-8")
        return True
    except Exception:
        return False


def write_pioneer_model_sweep_reports(report_dir: Path, model_results: list[dict[str, Any]]) -> dict[str, Path]:
    report_dir.mkdir(parents=True, exist_ok=True)
    for result in model_results:
        _write_per_model(report_dir, result)
    summary = _summary_payload(model_results)
    summary_json = report_dir / "pioneer_model_sweep_summary.json"
    summary_md = report_dir / "pioneer_model_sweep_summary.md"
    summary_json.write_text(json.dumps(redact_secrets(summary), indent=2, sort_keys=True), encoding="utf-8")
    summary_md.write_text(_summary_markdown(summary), encoding="utf-8")
    return {"summary_json": summary_json, "summary_md": summary_md}


def _write_per_model(report_dir: Path, result: dict[str, Any]) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    safe_name = result.get("safe_model_name") or safe_model_name(str(result.get("model") or "model"))
    payload = dict(result)
    log = str(payload.pop("log", ""))
    (report_dir / f"per_model_{safe_name}.json").write_text(
        json.dumps(redact_secrets(payload), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    if not log:
        log = json.dumps(redact_secrets(payload), indent=2, sort_keys=True)
    (report_dir / f"per_model_{safe_name}.log").write_text(log, encoding="utf-8")


def _summary_payload(model_results: list[dict[str, Any]]) -> dict[str, Any]:
    evaluated = [row for row in model_results if row.get("availability", {}).get("available")]
    safe_non_gpt = [
        row
        for row in evaluated
        if not str(row.get("model", "")).lower().startswith("gpt")
        and row.get("metrics", {}).get("focused_smoke_pass")
        and int(row.get("metrics", {}).get("no_tool_fp") or 0) == 0
        and int(row.get("metrics", {}).get("unsupported_claims") or 0) == 0
    ]
    safest_non_gpt = sorted(
        safe_non_gpt,
        key=lambda row: (
            int(row.get("metrics", {}).get("json_parse_failures") or 0),
            float(row.get("metrics", {}).get("latency_sec") or 999999),
        ),
    )
    fewest_json_failures = sorted(
        evaluated,
        key=lambda row: (
            int(row.get("metrics", {}).get("json_parse_failures") or 0),
            float(row.get("metrics", {}).get("latency_sec") or 999999),
        ),
    )
    incorrect_bypass = [
        row.get("model")
        for row in evaluated
        if int(row.get("metrics", {}).get("no_tool_fp") or 0) > 0
    ]
    viable_small = [row.get("model") for row in safest_non_gpt]
    return {
        "status": "diagnostic_only",
        "model_count": len(model_results),
        "default_model_sweep": list(DEFAULT_PIONEER_MODEL_SWEEP),
        "model_groups": dict(DEFAULT_PIONEER_MODEL_GROUPS),
        "models": model_results,
        "answers": {
            "safest_non_gpt_model": safest_non_gpt[0].get("model") if safest_non_gpt else None,
            "fewest_json_failures_model": fewest_json_failures[0].get("model") if fewest_json_failures else None,
            "incorrect_evidence_bypass_models": incorrect_bypass,
            "viable_cross_family_small_models": viable_small,
            "gpt_4o_necessary": None if not evaluated else not bool(viable_small),
        },
    }


def _summary_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Pioneer Model Sweep Summary",
        "",
        "Status: diagnostic_only. This sweep changes only the configured Pioneer LLM model for V2 semantic/concept paths.",
        "",
        "## Default Model Set",
        "",
    ]
    for model in summary["default_model_sweep"]:
        lines.append(f"- {model}: {summary['model_groups'].get(model, 'custom')}")
    lines.extend(
        [
            "",
            "## Results",
            "",
            "| Model | Group | Available | Pass | JSON Failures | LLM Direct | Evidence Pipeline | Bypassed | EvidenceBus | no_tool_fp | Unsupported | Latency Sec |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in summary["models"]:
        metrics = row.get("metrics", {})
        availability = row.get("availability", {})
        lines.append(
            "| {model} | {group} | {available} | {passed} | {json_fail} | {direct} | {pipeline} | {bypassed} | {bus} | {fp} | {unsupported} | {latency} |".format(
                model=row.get("model"),
                group=row.get("group"),
                available=bool(availability.get("available")),
                passed=bool(metrics.get("focused_smoke_pass")),
                json_fail=metrics.get("json_parse_failures"),
                direct=metrics.get("llm_direct_count"),
                pipeline=metrics.get("evidence_pipeline_count"),
                bypassed=metrics.get("evidence_pipeline_bypassed_count"),
                bus=metrics.get("evidence_bus_built_count"),
                fp=metrics.get("no_tool_fp"),
                unsupported=metrics.get("unsupported_claims"),
                latency=metrics.get("latency_sec"),
            )
        )
    answers = summary.get("answers", {})
    lines.extend(
        [
            "",
            "## Summary Answers",
            "",
            f"1. Safest non-GPT model: {answers.get('safest_non_gpt_model') or 'none evaluated as safe'}.",
            f"2. Fewest JSON failures: {answers.get('fewest_json_failures_model') or 'none available'}.",
            f"3. Incorrect EvidenceBus bypass models: {answers.get('incorrect_evidence_bypass_models') or []}.",
            f"4. Viable cross-family small models: {answers.get('viable_cross_family_small_models') or []}.",
            "5. Per-family safety is determined by focused smoke pass, no_tool_fp=0, and unsupported_claims=0.",
            f"6. GPT-4o necessary based on this focused run: {answers.get('gpt_4o_necessary')}.",
            "",
        ]
    )
    return "\n".join(lines)


def _checkpoint_output(checkpoints: list[dict[str, Any]], checkpoint_id: str) -> dict[str, Any]:
    for checkpoint in checkpoints:
        if checkpoint.get("checkpoint_id") == checkpoint_id:
            output = checkpoint.get("output")
            return output if isinstance(output, dict) else {}
    return {}


def _declared_pass_count(checkpoints: list[dict[str, Any]]) -> int:
    counts: list[int] = []
    for checkpoint in checkpoints:
        output = checkpoint.get("output")
        counts.extend(_find_numeric_fields(output, {"llm_pass_count", "declared_pass_count", "pass_count"}))
        if checkpoint.get("checkpoint_id") == "checkpoint_llm_owned_pass_graph_gate":
            nested = checkpoint.get("input_summary")
            counts.extend(_find_numeric_fields(nested, {"llm_pass_count", "declared_pass_count", "pass_count"}))
    return max(counts) if counts else 0


def _pass_results_count(checkpoints: list[dict[str, Any]]) -> int:
    counts: list[int] = []
    for checkpoint in checkpoints:
        output = checkpoint.get("output")
        counts.extend(_find_numeric_fields(output, {"pass_results_count", "result_bundle_pass_results_count"}))
        nested = checkpoint.get("input_summary")
        counts.extend(_find_numeric_fields(nested, {"pass_results_count", "result_bundle_pass_results_count"}))
    return max(counts) if counts else 0


def _weak_protocol_planner_metrics(checkpoints: list[dict[str, Any]]) -> dict[str, Any]:
    planner_checkpoint = next(
        (checkpoint for checkpoint in checkpoints if checkpoint.get("checkpoint_id") == "checkpoint_llm_unified_planner"),
        {},
    )
    planner = planner_checkpoint.get("output") if isinstance(planner_checkpoint.get("output"), dict) else {}
    metrics = planner_checkpoint.get("metrics") if isinstance(planner_checkpoint.get("metrics"), dict) else {}
    diagnostics = planner.get("diagnostics") if isinstance(planner.get("diagnostics"), dict) else {}
    source = metrics or diagnostics or planner
    return {
        "route_card_success": source.get("route_card_success"),
        "route_card_route": source.get("route_card_route"),
        "route_card_repair_attempted": source.get("route_card_repair_attempted"),
        "task_ledger_success": source.get("task_ledger_success"),
        "task_ledger_repair_attempted": source.get("task_ledger_repair_attempted"),
        "candidate_card_success": int(source.get("candidate_card_success") or 0),
        "pass_candidate_cards": int(source.get("pass_candidate_cards") or 0),
        "sql_candidate_cards": int(source.get("sql_candidate_cards") or 0),
        "api_candidate_cards": int(source.get("api_candidate_cards") or 0),
        "candidate_repair_attempts": int(source.get("candidate_repair_attempts") or 0),
        "route_card_latency_ms": source.get("route_card_latency_ms"),
        "task_ledger_latency_ms": source.get("task_ledger_latency_ms"),
        "candidate_card_latency_ms": source.get("candidate_card_latency_ms"),
    }


def _tool_gate_metrics(checkpoints: list[dict[str, Any]]) -> dict[str, int]:
    sql_gate_failures = 0
    api_gate_failures = 0
    for checkpoint in checkpoints:
        checkpoint_id = str(checkpoint.get("checkpoint_id") or "")
        output = checkpoint.get("output")
        if not isinstance(output, dict) or output.get("passed") is not False:
            continue
        if "sql_compile_gate" in checkpoint_id:
            sql_gate_failures += 1
        if "api_request_gate" in checkpoint_id:
            api_gate_failures += 1
    return {"sql_gate_failures": sql_gate_failures, "api_gate_failures": api_gate_failures}


def _answer_gate_metrics(checkpoints: list[dict[str, Any]]) -> dict[str, int]:
    initial_syntax = _gate_failure_count(checkpoints, "checkpoint_llm_final_answer_syntax_gate")
    initial_semantic = _gate_failure_count(checkpoints, "checkpoint_llm_final_answer_semantic_gate")
    boundary = _checkpoint_output(checkpoints, "checkpoint_llm_owned_final_answer_boundary")
    repair_attempts = int(boundary.get("answer_repair_attempts") or 0) if boundary else 0
    if boundary:
        final_syntax = 0 if bool(boundary.get("answer_syntax_gate_passed")) else 1
        final_semantic = 0 if bool(boundary.get("answer_semantic_gate_passed")) else 1
    else:
        final_syntax = initial_syntax
        final_semantic = initial_semantic
    repaired_successes = 1 if repair_attempts > 0 and final_syntax == 0 and final_semantic == 0 else 0
    return {
        "answer_syntax_gate_initial_failures": initial_syntax,
        "answer_semantic_gate_initial_failures": initial_semantic,
        "answer_repair_attempts": repair_attempts,
        "answer_syntax_gate_final_failures": final_syntax,
        "answer_semantic_gate_final_failures": final_semantic,
        "answer_repaired_successes": repaired_successes,
    }


def _gate_failure_count(checkpoints: list[dict[str, Any]], checkpoint_id: str) -> int:
    failures = 0
    for checkpoint in checkpoints:
        if checkpoint.get("checkpoint_id") != checkpoint_id:
            continue
        output = checkpoint.get("output")
        if isinstance(output, dict) and output.get("passed") is False:
            failures += 1
    return failures


def _unsupported_claim_count(checkpoints: list[dict[str, Any]]) -> int:
    counts: list[int] = []
    for checkpoint in checkpoints:
        output = checkpoint.get("output")
        counts.extend(_find_unsupported_counts(output))
    return max(counts) if counts else 0


def _find_unsupported_counts(value: Any) -> list[int]:
    if isinstance(value, dict):
        counts: list[int] = []
        for key, nested in value.items():
            lowered = str(key).lower()
            if lowered in {"unsupported_claim_count", "unsupported_claims_count"} and isinstance(nested, (int, float)):
                counts.append(int(nested))
            elif lowered == "unsupported_claims" and isinstance(nested, list):
                counts.append(len(nested))
            counts.extend(_find_unsupported_counts(nested))
        return counts
    if isinstance(value, list):
        counts: list[int] = []
        for item in value:
            counts.extend(_find_unsupported_counts(item))
        return counts
    return []


def _find_numeric_fields(value: Any, field_names: set[str]) -> list[int]:
    if isinstance(value, dict):
        counts: list[int] = []
        for key, nested in value.items():
            if str(key) in field_names and isinstance(nested, (int, float)):
                counts.append(int(nested))
            else:
                counts.extend(_find_numeric_fields(nested, field_names))
        return counts
    if isinstance(value, list):
        counts: list[int] = []
        for item in value:
            counts.extend(_find_numeric_fields(item, field_names))
        return counts
    return []


@contextmanager
def _temporary_env(updates: dict[str, str]) -> Iterator[None]:
    old_values = {key: os.environ.get(key) for key in updates}
    try:
        for key, value in updates.items():
            os.environ[key] = value
        yield
    finally:
        for key, old_value in old_values.items():
            if old_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old_value
