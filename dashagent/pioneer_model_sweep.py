from __future__ import annotations

import json
import os
import re
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .config import Config, ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2
from .executor import AgentExecutor
from .llm_client import PioneerChatLLMClient
from .trajectory import redact_secrets


DEFAULT_PIONEER_MODEL_SWEEP = [
    "Gpt 4o",
    "Claude Haiku 4.5",
    "DeepSeek V4 Flash",
    "Qwen3 4B Instruct 2507",
    "Llama 3.1 8B Instruct",
    "Mistral Nemo Instruct 2407",
    "Gemma 4 E4B It",
]

DEFAULT_PIONEER_MODEL_GROUPS = {
    "Gpt 4o": "gpt_baseline",
    "Claude Haiku 4.5": "anthropic_fast_small",
    "DeepSeek V4 Flash": "deepseek_cheap_fast",
    "Qwen3 4B Instruct 2507": "qwen_small_instruct",
    "Llama 3.1 8B Instruct": "llama_small_instruct",
    "Mistral Nemo Instruct 2407": "mistral_compact_instruct",
    "Gemma 4 E4B It": "gemma_small_instruct",
}

EXCLUDED_DEFAULT_PIONEER_MODELS = {
    "Gpt 4.1",
    "Gpt 4.1 Mini",
    "Gpt 4.1 Nano",
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
    "DeepSeek V4 Pro",
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
        "id": "mixed_inactive_journeys",
        "prompt": "Explain what inactive journey means and show inactive journeys.",
        "expected_kind": "EVIDENCE",
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
]


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
            "PIONEER_MODEL": model_id,
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
        executor = AgentExecutor(config)
        prompt_results: list[dict[str, Any]] = []
        semantic_probe_results: list[dict[str, Any]] = []
        for prompt_case in PIONEER_SWEEP_PROMPTS:
            semantic_probe = _with_model_context(_semantic_json_probe(model_id, prompt_case["prompt"]), model, safe_name, model_id)
            semantic_probe_results.append(semantic_probe)
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
    result = client.complete_json(
        (
            "Classify this prompt for DASHSys pre-evidence routing. "
            "Concrete user data, counts, lists, status, dates, live/current/platform/API prompts, "
            "and mixed concept+data prompts must route to EVIDENCE_PIPELINE."
        ),
        prompt,
        schema_hint=schema_hint,
        max_tokens=160,
    )
    result = dict(result)
    result.update(
        {
            "prompt": prompt,
            "model": model,
            "latency_sec": round(time.perf_counter() - started, 4),
        }
    )
    return redact_secrets(result)


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
    unsupported_claims = _unsupported_claim_count(checkpoints)
    expected_kind = prompt_case["expected_kind"]
    if expected_kind == "PURE_DIRECT":
        passed = (
            sql_calls == 0
            and api_calls == 0
            and evidence_pipeline_bypassed
            and not evidence_bus_built
            and not post_router_ran
            and unsupported_claims == 0
        )
    else:
        passed = (not evidence_pipeline_bypassed) and evidence_bus_built and post_router_ran and unsupported_claims == 0
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
            "post_evidence_answer_router_ran": post_router_ran,
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
    return {
        "json_parse_failures": sum(1 for row in semantic_probe_results if bool(row.get("parse_error"))),
        "semantic_fallback_count": sum(1 for row in semantic_probe_results if bool(row.get("parse_error"))),
        "llm_direct_count": sum(1 for row in prompt_results if bool(row.get("llm_direct"))),
        "evidence_pipeline_count": sum(1 for row in prompt_results if bool(row.get("evidence_pipeline"))),
        "evidence_pipeline_bypassed_count": sum(1 for row in prompt_results if bool(row.get("evidence_pipeline_bypassed"))),
        "evidence_bus_built_count": sum(1 for row in prompt_results if bool(row.get("evidence_bus_built"))),
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
