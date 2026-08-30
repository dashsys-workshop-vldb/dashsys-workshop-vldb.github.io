from __future__ import annotations

import json
import os
import signal
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Callable

from .config import Config
from .pioneer_model_sweep import (
    DEFAULT_PIONEER_MODEL_SWEEP,
    is_gpt4_family_model,
    parse_pioneer_model_id_map,
    parse_pioneer_model_sweep,
    run_pioneer_model_sweep,
    safe_model_name,
    _availability_probe,
    _reset_llm_client_for_model,
)
from .trajectory import SECRET_KEYS, SECRET_LIKE_RE


DEFAULT_SELECTED_MODEL_ID_MAP = {
    "Qwen3 4B Instruct 2507": "Qwen/Qwen3-4B-Instruct-2507",
    "Qwen3 4B Instruct": "Qwen/Qwen3-4B-Instruct-2507",
    "Qwen3 8B": "Qwen/Qwen3-8B",
    "Qwen3.5 9B": "Qwen/Qwen3.5-9B",
    "Qwen3.6 27B": "Qwen/Qwen3.6-27B",
    "Qwen3.6 Flash": "qwen3.6-flash",
    "Qwen3.6 Plus": "qwen3.6-plus",
    "Qwen3.6 35B A3B": "Qwen/Qwen3.6-35B-A3B",
    "Qwen3.7 Max": "qwen3.7-max",
    "Claude Haiku 4.5": "claude-haiku-4-5",
    "DeepSeek V4 Flash": "deepseek-ai/DeepSeek-V4-Flash",
    "DeepSeek V4 Pro": "deepseek-ai/DeepSeek-V4-Pro",
    "Llama 3.1 8B Instruct": "meta-llama/Llama-3.1-8B-Instruct",
    "Llama 3.2 3B Instruct": "meta-llama/Llama-3.2-3B-Instruct",
    "Llama 3.2 1B Instruct": "meta-llama/Llama-3.2-1B-Instruct",
    "Mistral Nemo Instruct 2407": "mistralai/Mistral-Nemo-Instruct-2407",
    "Mistral Nemo": "mistralai/Mistral-Nemo-Instruct-2407",
    "Gemma 4 E4B It": "google/gemma-4-E4B-it",
    "Gemma 4 E4B IT": "google/gemma-4-E4B-it",
    "Gemma 4 31B It": "google/gemma-4-31B-it",
    "Gemma 4 31B IT": "google/gemma-4-31B-it",
    "MiniMax M2.7": "MiniMaxAI/MiniMax-M2.7",
    "Minimax M2.7": "MiniMaxAI/MiniMax-M2.7",
    "Kimi K2.6": "moonshotai/Kimi-K2.6",
    "GLM 5.1": "zai-org/GLM-5.1",
    "GPT-OSS 20B": "openai/gpt-oss-20b",
    "Gpt Oss 20b": "openai/gpt-oss-20b",
    "GPT-OSS 120B": "openai/gpt-oss-120b",
    "Gpt Oss 120b": "openai/gpt-oss-120b",
}


CommandRunner = Callable[[dict[str, Any], dict[str, str], Path, int], dict[str, Any]]
AvailabilityProbe = Callable[[str], dict[str, Any]]
FocusedSmokeRunner = Callable[..., dict[str, Any]]


def default_full_benchmark_command_plan() -> list[dict[str, Any]]:
    return [
        {
            "name": "organizer35_strict_v2",
            "command": [
                "python3",
                "scripts/run_dev_eval.py",
                "--strict",
                "--strategies",
                "ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2",
            ],
            "timeout_sec": 1800,
            "description": "Organizer35 strict run for the V2 research candidate only.",
        },
        {
            "name": "internal50_v2",
            "command": [
                "python3",
                "scripts/run_dashagent_500_prompt_suite_eval.py",
                "--engine",
                "real_agent",
                "--mode",
                "robust_generalized_harness_candidate_v2_real",
                "--limit",
                "50",
                "--seed",
                "20260525",
                "--clean",
                "--output-dir",
                "{model_outputs_dir}/internal50_eval",
                "--report-dir",
                "{model_outputs_dir}/internal50_reports",
            ],
            "timeout_sec": 2400,
            "description": "Focused Internal50 real-agent benchmark for V2.",
        },
        {
            "name": "semantic_route_promotion_gate",
            "command": ["python3", "scripts/run_semantic_route_promotion_gate.py"],
            "timeout_sec": 900,
            "description": "Existing semantic routing promotion gate, recorded as diagnostic-only.",
        },
        {
            "name": "integrated_robustness_gate",
            "command": ["python3", "scripts/run_integrated_robustness_gate.py"],
            "timeout_sec": 900,
            "description": "Existing integrated robustness gate, recorded as diagnostic-only.",
        },
        {
            "name": "hidden_style_eval",
            "command": ["python3", "scripts/run_hidden_style_eval.py"],
            "timeout_sec": 900,
            "description": "Existing hidden-style evaluation.",
        },
    ]


def minimal_test_command_plan() -> list[dict[str, Any]]:
    return [
        {
            "name": "organizer35_strict_v2",
            "command": ["python3", "scripts/run_dev_eval.py", "--strict", "--strategies", "ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2"],
            "timeout_sec": 30,
        },
        {
            "name": "internal50_v2",
            "command": ["python3", "scripts/run_dashagent_500_prompt_suite_eval.py", "--engine", "real_agent", "--mode", "robust_generalized_harness_candidate_v2_real"],
            "timeout_sec": 30,
        },
    ]


def resolve_pioneer_model_id(display_name: str) -> str:
    mapping = dict(DEFAULT_SELECTED_MODEL_ID_MAP)
    mapping.update(parse_pioneer_model_id_map())
    return mapping.get(display_name, display_name)


def run_pioneer_model_full_benchmark(
    config: Config,
    *,
    models: list[str] | None = None,
    report_dir: Path | None = None,
    commands: list[dict[str, Any]] | None = None,
    availability_probe: AvailabilityProbe | None = None,
    focused_smoke_runner: FocusedSmokeRunner | None = None,
    command_runner: CommandRunner | None = None,
) -> dict[str, Any]:
    selected_models = _exclude_gpt4_family(models or parse_pioneer_model_sweep())
    destination = report_dir or (config.outputs_dir / "reports" / "pioneer_model_full_benchmark")
    destination.mkdir(parents=True, exist_ok=True)
    command_plan = commands or default_full_benchmark_command_plan()
    probe = availability_probe or _availability_probe
    smoke_runner = focused_smoke_runner or run_pioneer_model_sweep
    runner = command_runner or _run_subprocess_command
    manifest = _write_command_manifest(destination, command_plan)
    exclusion_summary = _gpt4_exclusion_summary(models or parse_pioneer_model_sweep(), selected_models)

    results: list[dict[str, Any]] = []
    for model in selected_models:
        results.append(
            _run_one_model_full_benchmark(
                config,
                model,
                destination,
                command_plan,
                availability_probe=probe,
                focused_smoke_runner=smoke_runner,
                command_runner=runner,
            )
        )

    summary = _summary_payload(results, manifest, exclusion_summary)
    summary_json = destination / "pioneer_model_full_benchmark_summary.json"
    summary_md = destination / "pioneer_model_full_benchmark_summary.md"
    summary_json.write_text(json.dumps(_redact_benchmark(summary), indent=2, sort_keys=True, default=str), encoding="utf-8")
    summary_md.write_text(_summary_markdown(summary), encoding="utf-8")
    return {
        "models": results,
        "paths": {
            "summary_json": str(summary_json),
            "summary_md": str(summary_md),
            "command_manifest": str(manifest),
        },
    }


def _run_one_model_full_benchmark(
    config: Config,
    model: str,
    report_dir: Path,
    commands: list[dict[str, Any]],
    *,
    availability_probe: AvailabilityProbe,
    focused_smoke_runner: FocusedSmokeRunner,
    command_runner: CommandRunner,
) -> dict[str, Any]:
    started = time.perf_counter()
    safe_name = safe_model_name(model)
    model_id = resolve_pioneer_model_id(model)
    model_root = report_dir / "runs" / safe_name
    model_outputs = model_root / "outputs"
    if model_root.exists():
        shutil.rmtree(model_root)
    model_outputs.mkdir(parents=True, exist_ok=True)
    (model_outputs / "reports").mkdir(parents=True, exist_ok=True)
    model_env = _model_env(model, model_id, model_outputs)
    log_lines: list[str] = [
        f"pioneer_model={model}",
        f"pioneer_model_id={model_id}",
        "model_major_semantics=true",
    ]
    commands_run: list[dict[str, Any]] = []

    with _temporary_environ(model_env):
        _reset_llm_client_for_model()
        availability = _contextualize(_call_availability_probe_with_timeout(availability_probe, model_id), model, model_id, safe_name)
        log_lines.append("availability=" + json.dumps(_redact_benchmark(availability), sort_keys=True))
        if not availability.get("available"):
            result = _base_result(model, model_id, safe_name, availability, started)
            result["model_usage"] = _model_usage_summary(model, model_id, {}, {})
            result["stability_verdict"] = "UNAVAILABLE"
            result["log"] = "\n".join(log_lines) + "\n"
            _write_per_model(report_dir, result)
            return result

        focused_smoke = _run_focused_smoke_safely(
            config,
            model,
            model_id,
            model_outputs,
            focused_smoke_runner,
            log_lines,
        )
        if not _smoke_minimum_passed(focused_smoke):
            metrics = _collect_model_metrics(model_outputs, focused_smoke, commands_run)
            result = {
                **_base_result(model, model_id, safe_name, availability, started),
                "focused_smoke": focused_smoke,
                "commands": commands_run,
                "command_failures": 0,
                "metrics": metrics,
                "model_usage": _model_usage_summary(model, model_id, focused_smoke, metrics),
                "stability_verdict": "SMOKE_FAILED",
                "benchmark_status": "skipped_smoke_failed",
                "outputs_dir": str(model_outputs),
                "trajectories_path": None,
                "log": "\n".join(log_lines + ["benchmark_skipped=smoke_minimum_failed"]) + "\n",
            }
            _write_per_model(report_dir, result)
            return result
        for command in commands:
            prepared = _prepare_command(command, model_outputs)
            command_started = time.perf_counter()
            try:
                cwd = Path(getattr(config, "project_root", Path.cwd()))
                command_result = command_runner(prepared, dict(os.environ), cwd, int(prepared.get("timeout_sec") or 1800))
            except Exception as exc:
                command_result = {
                    "returncode": 1,
                    "stdout": "",
                    "stderr": f"{type(exc).__name__}: {exc}",
                    "duration_sec": round(time.perf_counter() - command_started, 4),
                }
            command_record = _contextualize(
                {
                    "name": prepared["name"],
                    "command": prepared["command"],
                    **command_result,
                },
                model,
                model_id,
                safe_name,
            )
            commands_run.append(_redact_benchmark(command_record))
            log_lines.append("command_result=" + json.dumps(_redact_benchmark(command_record), sort_keys=True, default=str))

        trajectories_path = _write_trajectory_snapshot(report_dir, model_outputs, model, model_id, safe_name)
        metrics = _collect_model_metrics(model_outputs, focused_smoke, commands_run)
        result = {
            **_base_result(model, model_id, safe_name, availability, started),
            "focused_smoke": focused_smoke,
            "commands": commands_run,
            "command_failures": sum(1 for row in commands_run if int(row.get("returncode") or 0) != 0),
            "metrics": metrics,
            "model_usage": _model_usage_summary(model, model_id, focused_smoke, metrics),
            "stability_verdict": _stability_verdict(metrics, commands_run),
            "benchmark_status": "completed" if commands_run else "not_run",
            "outputs_dir": str(model_outputs),
            "trajectories_path": str(trajectories_path) if trajectories_path else None,
            "log": "\n".join(log_lines) + "\n",
        }
        _write_per_model(report_dir, result)
        return result


def _exclude_gpt4_family(models: list[str]) -> list[str]:
    return [model for model in models if not is_gpt4_family_model(model, resolve_pioneer_model_id(model))]


def _gpt4_exclusion_summary(original_models: list[str], selected_models: list[str]) -> dict[str, Any]:
    selected_set = set(selected_models)
    excluded = [
        {
            "display_name": model,
            "model_id": resolve_pioneer_model_id(model),
            "reason": "excluded_gpt4_family_or_unavailable",
        }
        for model in original_models
        if model not in selected_set and is_gpt4_family_model(model, resolve_pioneer_model_id(model))
    ]
    return {
        "enabled": True,
        "reason": "GPT-4/Gpt 4o family models are excluded from this non-GPT-4 stability benchmark.",
        "excluded_models": excluded,
    }


class _ProbeTimeout(RuntimeError):
    pass


def _call_availability_probe_with_timeout(availability_probe: AvailabilityProbe, model_id: str) -> dict[str, Any]:
    timeout_sec = int(os.getenv("PIONEER_GPT_FALLBACK_PROBE_TIMEOUT_SEC", "45"))
    if timeout_sec <= 0 or signal.getsignal(signal.SIGALRM) is None:
        return availability_probe(model_id)
    previous_handler = signal.getsignal(signal.SIGALRM)

    def _handle_timeout(signum, frame):  # noqa: ANN001 - signal handler signature.
        raise _ProbeTimeout(f"availability probe timed out after {timeout_sec}s")

    try:
        signal.signal(signal.SIGALRM, _handle_timeout)
        signal.alarm(timeout_sec)
        return availability_probe(model_id)
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous_handler)


def _model_env(model: str, model_id: str, model_outputs: Path) -> dict[str, str]:
    return {
        "DASHAGENT_LLM_PROVIDER": "pioneer_chat",
        "PIONEER_MODEL": model,
        "PIONEER_MODEL_ID": model_id,
        "PIONEER_MODEL_DISPLAY": model,
        "PIONEER_STORE": os.getenv("PIONEER_STORE", "false"),
        "DASHAGENT_OUTPUTS_DIR": str(model_outputs),
    }


def _run_focused_smoke_safely(
    config: Config,
    model: str,
    model_id: str,
    model_outputs: Path,
    focused_smoke_runner: FocusedSmokeRunner,
    log_lines: list[str],
) -> dict[str, Any]:
    try:
        timeout_sec = int(os.getenv("PIONEER_FOCUSED_SMOKE_TIMEOUT_SEC", "120"))
        if timeout_sec > 0:
            smoke = _call_focused_smoke_with_timeout(
                focused_smoke_runner,
                config,
                model,
                model_outputs,
                timeout_sec,
            )
        else:
            smoke = focused_smoke_runner(config, models=[model], report_dir=model_outputs / "focused_smoke")
        smoke_model = (smoke.get("models") or [{}])[0]
        return _contextualize(smoke_model, model, model_id, safe_model_name(model))
    except Exception as exc:
        payload = _contextualize(
            {
                "availability": {"available": True},
                "metrics": {
                    "json_parse_failures": 0,
                    "semantic_fallback_count": 0,
                    "llm_direct_count": 0,
                    "llm_safe_direct_count": 0,
                    "evidence_pipeline_count": 0,
                    "evidence_pipeline_bypassed_count": 0,
                    "evidence_bus_built_count": 0,
                    "post_evidence_answer_router_ran_count": 0,
                    "no_tool_fp": 0,
                    "api_required_underuse": 0,
                    "unsupported_claims": 0,
                    "focused_smoke_pass": False,
                },
                "error": f"{type(exc).__name__}: {exc}",
            },
            model,
            model_id,
            safe_model_name(model),
        )
        log_lines.append("focused_smoke_error=" + json.dumps(_redact_benchmark(payload), sort_keys=True))
        return payload


def _call_focused_smoke_with_timeout(
    focused_smoke_runner: FocusedSmokeRunner,
    config: Config,
    model: str,
    model_outputs: Path,
    timeout_sec: int,
) -> dict[str, Any]:
    previous_handler = signal.getsignal(signal.SIGALRM)

    def _handle_timeout(signum, frame):  # noqa: ANN001 - signal handler signature.
        raise _ProbeTimeout(f"focused smoke timed out after {timeout_sec}s")

    try:
        signal.signal(signal.SIGALRM, _handle_timeout)
        signal.alarm(timeout_sec)
        return focused_smoke_runner(config, models=[model], report_dir=model_outputs / "focused_smoke")
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous_handler)


def _smoke_minimum_passed(focused_smoke: dict[str, Any]) -> bool:
    availability = focused_smoke.get("availability") if isinstance(focused_smoke.get("availability"), dict) else {}
    metrics = focused_smoke.get("metrics") if isinstance(focused_smoke.get("metrics"), dict) else {}
    if availability and availability.get("available") is False:
        return False
    if int(metrics.get("planner_usable_count") or 0) <= 0:
        return False
    if int(metrics.get("declared_pass_count") or 0) <= 0:
        return False
    if int(metrics.get("no_tool_fp") or 0) > 0:
        return False
    if int(metrics.get("unsupported_claims") or 0) > 0:
        return False
    if bool(metrics.get("final_gates_all_failed")):
        return False
    prompt_results = focused_smoke.get("prompt_results") if isinstance(focused_smoke.get("prompt_results"), list) else []
    pure_rows = [row for row in prompt_results if row.get("expected_kind") == "PURE_DIRECT"]
    evidence_rows = [row for row in prompt_results if row.get("expected_kind") == "EVIDENCE"]
    if not pure_rows or not evidence_rows:
        return False
    if any(int(row.get("sql_calls") or 0) > 0 or int(row.get("api_calls") or 0) > 0 for row in pure_rows):
        return False
    if all(int(row.get("declared_pass_count") or 0) == 0 for row in evidence_rows):
        return False
    return True


def _prepare_command(command: dict[str, Any], model_outputs: Path) -> dict[str, Any]:
    prepared = dict(command)
    prepared["command"] = [str(part).format(model_outputs_dir=str(model_outputs)) for part in command.get("command", [])]
    return prepared


def _run_subprocess_command(command: dict[str, Any], env: dict[str, str], cwd: Path, timeout_sec: int) -> dict[str, Any]:
    started = time.perf_counter()
    proc = subprocess.run(
        command["command"],
        cwd=str(cwd),
        env=env,
        text=True,
        capture_output=True,
        timeout=timeout_sec,
        check=False,
    )
    return _redact_benchmark(
        {
            "returncode": proc.returncode,
            "stdout": proc.stdout[-12000:],
            "stderr": proc.stderr[-12000:],
            "duration_sec": round(time.perf_counter() - started, 4),
        }
    )


def _collect_model_metrics(model_outputs: Path, focused_smoke: dict[str, Any], commands_run: list[dict[str, Any]]) -> dict[str, Any]:
    strict = _read_json(model_outputs / "eval_results_strict.json")
    strict_summary = ((strict.get("summary") or {}).get("by_strategy") or {}).get("ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2", {})
    internal50 = _read_json(model_outputs / "internal50_reports" / "dashagent_500_prompt_suite_eval_real.json")
    internal_summary = ((internal50.get("mode_summary") or {}).get("robust_generalized_harness_candidate_v2_real") or {})
    smoke_metrics = focused_smoke.get("metrics") if isinstance(focused_smoke.get("metrics"), dict) else {}
    smoke_prompt_results = focused_smoke.get("prompt_results") if isinstance(focused_smoke.get("prompt_results"), list) else []
    smoke_sql_calls = sum(int(row.get("sql_calls") or 0) for row in smoke_prompt_results)
    smoke_api_calls = sum(int(row.get("api_calls") or 0) for row in smoke_prompt_results)
    command_failures = sum(1 for row in commands_run if int(row.get("returncode") or 0) != 0)
    post_router_count = smoke_metrics.get("post_evidence_answer_router_ran_count")
    if post_router_count is None:
        post_router_count = sum(1 for row in smoke_prompt_results if bool(row.get("post_evidence_answer_router_ran")))
    return {
        "organizer35": {
            "final_score": strict_summary.get("avg_final_score"),
            "correctness_score": strict_summary.get("avg_correctness_score"),
            "answer_score": strict_summary.get("avg_answer_score"),
            "sql_score": strict_summary.get("avg_sql_score"),
            "api_score": strict_summary.get("avg_api_score"),
            "tool_call_count": strict_summary.get("avg_tool_call_count"),
        },
        "internal50": {
            "combined_score": internal_summary.get("overall_score") or internal_summary.get("combined_diagnostic_score"),
            "behavior_score": internal_summary.get("behavior_score"),
            "sql_calls": internal_summary.get("sql_calls"),
            "api_calls": internal_summary.get("api_calls"),
            "no_tool_fp": internal_summary.get("no_tool_false_positive"),
            "api_required_underuse": internal_summary.get("api_required_underuse"),
            "unsupported_claims": internal_summary.get("unsupported_claims"),
        },
        "safety": {
            "no_tool_fp": int(smoke_metrics.get("no_tool_fp") or internal_summary.get("no_tool_false_positive") or 0),
            "api_required_underuse": int(smoke_metrics.get("api_required_underuse") or internal_summary.get("api_required_underuse") or 0),
            "unsupported_claims": int(smoke_metrics.get("unsupported_claims") or internal_summary.get("unsupported_claims") or 0),
            "concrete_data_prompt_incorrectly_routed_to_llm_direct": int(smoke_metrics.get("no_tool_fp") or 0),
            "api_error_treated_as_no_data": None,
            "live_empty_treated_as_global_absence": None,
            "live_local_scope_confusion": None,
        },
        "execution": {
            "focused_smoke_sql_calls": smoke_sql_calls,
            "focused_smoke_api_calls": smoke_api_calls,
            "focused_smoke_tool_calls": smoke_sql_calls + smoke_api_calls,
            "sql_gate_failures": 0,
            "api_gate_failures": 0,
            "sql_repair_attempts": 0,
            "api_repair_attempts": 0,
            "exact_pass_cache_hits": 0,
            "exact_pass_cache_misses": 0,
            "result_bundle_built_count": int(smoke_metrics.get("result_bundle_built_count") or 0),
        },
        "routing_evidence": {
            "llm_direct_count": int(smoke_metrics.get("llm_direct_count") or 0),
            "llm_safe_direct_count": int(smoke_metrics.get("llm_safe_direct_count") or 0),
            "evidence_pipeline_count": int(smoke_metrics.get("evidence_pipeline_count") or 0),
            "evidence_pipeline_bypassed_count": int(smoke_metrics.get("evidence_pipeline_bypassed_count") or 0),
            "evidence_bus_built_count": int(smoke_metrics.get("evidence_bus_built_count") or 0),
            "evidence_bus_non_empty_count": int(smoke_metrics.get("evidence_bus_non_empty_count") or 0),
            "result_bundle_built_count": int(smoke_metrics.get("result_bundle_built_count") or 0),
            "declared_pass_count": int(smoke_metrics.get("declared_pass_count") or 0),
            "planner_usable_count": int(smoke_metrics.get("planner_usable_count") or 0),
            "post_evidence_answer_router_ran_count": int(post_router_count or 0),
            "semantic_fallback_count": int(smoke_metrics.get("semantic_fallback_count") or 0),
            "json_parse_failure_count": int(smoke_metrics.get("json_parse_failures") or 0),
            "malformed_model_response_count": int(smoke_metrics.get("json_parse_failures") or 0),
            "final_syntax_gate_failures": int(smoke_metrics.get("final_syntax_gate_failures") or 0),
            "final_semantic_gate_failures": int(smoke_metrics.get("final_semantic_gate_failures") or 0),
        },
        "availability": {
            "latency_sec": (focused_smoke.get("availability") or {}).get("latency_sec"),
            "retry_or_fallback_count": int(smoke_metrics.get("semantic_fallback_count") or 0),
        },
        "command_failures": command_failures,
    }


def _model_usage_summary(model: str, model_id: str, focused_smoke: dict[str, Any], metrics: dict[str, Any]) -> dict[str, Any]:
    smoke_prompt_results = focused_smoke.get("prompt_results") if isinstance(focused_smoke.get("prompt_results"), list) else []
    semantic_probe_results = (
        focused_smoke.get("semantic_probe_results") if isinstance(focused_smoke.get("semantic_probe_results"), list) else []
    )
    routing = metrics.get("routing_evidence") if isinstance(metrics.get("routing_evidence"), dict) else {}
    direct_answer_count = sum(1 for row in smoke_prompt_results if bool(row.get("llm_direct")))
    semantic_count = len(semantic_probe_results)
    json_failures = int(routing.get("json_parse_failure_count") or 0)
    fallback_count = int(routing.get("semantic_fallback_count") or 0)
    return {
        "active_llm_provider": "pioneer_chat",
        "pioneer_model": model,
        "pioneer_model_id": model_id,
        "llm_call_count": semantic_count + direct_answer_count,
        "semantic_llm_call_count": semantic_count,
        "direct_answer_llm_call_count": direct_answer_count,
        "json_parse_failures": json_failures,
        "fallback_to_evidence_pipeline_count": fallback_count,
        "scope": "focused_smoke_model_usage_plus_per_model_benchmark_env",
    }


def _stability_verdict(metrics: dict[str, Any], commands_run: list[dict[str, Any]]) -> str:
    safety = metrics.get("safety") or {}
    routing = metrics.get("routing_evidence") or {}
    if (
        int(safety.get("unsupported_claims") or 0) > 0
        or int(safety.get("no_tool_fp") or 0) > 0
        or int(safety.get("concrete_data_prompt_incorrectly_routed_to_llm_direct") or 0) > 0
    ):
        return "UNSAFE"
    if int(metrics.get("command_failures") or 0) > 0 or int(routing.get("json_parse_failure_count") or 0) > 0:
        return "SAFE_BUT_DEGRADED"
    return "STABLE"


def _base_result(model: str, model_id: str, safe_name: str, availability: dict[str, Any], started: float) -> dict[str, Any]:
    return {
        "model": model,
        "pioneer_model": model,
        "pioneer_model_id": model_id,
        "safe_model_name": safe_name,
        "model_sweep_run_id": safe_name,
        "availability": _redact_benchmark(availability),
        "duration_sec": round(time.perf_counter() - started, 4),
    }


def _contextualize(payload: dict[str, Any], model: str, model_id: str, safe_name: str) -> dict[str, Any]:
    row = dict(payload)
    row["model"] = model
    row["pioneer_model"] = model
    row["pioneer_model_id"] = model_id
    row["model_sweep_run_id"] = safe_name
    return _redact_benchmark(row)


def _write_per_model(report_dir: Path, result: dict[str, Any]) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    safe_name = str(result.get("safe_model_name") or safe_model_name(str(result.get("model") or "model")))
    payload = dict(result)
    log = str(payload.pop("log", ""))
    (report_dir / f"per_model_{safe_name}_benchmark.json").write_text(
        json.dumps(_redact_benchmark(payload), indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    if not log:
        log = json.dumps(_redact_benchmark(payload), indent=2, sort_keys=True, default=str)
    (report_dir / f"per_model_{safe_name}_benchmark.log").write_text(_redact_benchmark(log), encoding="utf-8")


def _write_trajectory_snapshot(report_dir: Path, model_outputs: Path, model: str, model_id: str, safe_name: str) -> Path | None:
    trajectories: list[dict[str, Any]] = []
    for path in sorted(model_outputs.rglob("trajectory.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                payload["pioneer_model"] = model
                payload["pioneer_model_id"] = model_id
                payload["model_sweep_run_id"] = safe_name
                path.write_text(json.dumps(_redact_benchmark(payload), indent=2, sort_keys=True, default=str), encoding="utf-8")
                trajectories.append({"path": str(path), "trajectory": payload})
        except Exception as exc:
            trajectories.append({"path": str(path), "error": f"{type(exc).__name__}: {exc}"})
    if not trajectories:
        return None
    output_path = report_dir / f"per_model_{safe_name}_trajectories.json"
    output_path.write_text(json.dumps(_redact_benchmark(trajectories), indent=2, sort_keys=True, default=str), encoding="utf-8")
    return output_path


def _write_command_manifest(report_dir: Path, commands: list[dict[str, Any]]) -> Path:
    path = report_dir / "benchmark_command_manifest.json"
    payload = {
        "purpose": "Cross-model stability benchmark for ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2.",
        "model_major_semantics": True,
        "commands": commands,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _summary_payload(model_results: list[dict[str, Any]], manifest: Path, gpt4_exclusion: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "purpose": "This benchmark verifies V2 stability across callable non-GPT-4 Pioneer/API models.",
        "model_major_semantics_confirmed": True,
        "default_model_sweep": list(DEFAULT_PIONEER_MODEL_SWEEP),
        "gpt4_family_exclusion": gpt4_exclusion or {},
        "benchmark_command_manifest": str(manifest),
        "models": model_results,
        "cross_model_conclusion": _cross_model_conclusion(model_results),
    }


def _cross_model_conclusion(model_results: list[dict[str, Any]]) -> dict[str, Any]:
    callable_models = [row for row in model_results if row.get("availability", {}).get("available")]
    unsafe = [row.get("model") for row in callable_models if row.get("stability_verdict") == "UNSAFE"]
    completed = [
        row.get("model")
        for row in callable_models
        if row.get("commands") and all(int(command.get("returncode") or 0) == 0 for command in row.get("commands", []))
    ]
    return {
        "callable_model_count": len(callable_models),
        "completed_full_benchmark_models": completed,
        "unavailable_models": [row.get("model") for row in model_results if not row.get("availability", {}).get("available")],
        "unsafe_models": unsafe,
        "v2_stable_across_callable_models": bool(callable_models) and not unsafe,
        "weak_models_failed_closed_if_malformed": all(
            not (
                int(((row.get("metrics") or {}).get("routing_evidence") or {}).get("json_parse_failure_count") or 0) > 0
                and int(((row.get("metrics") or {}).get("safety") or {}).get("concrete_data_prompt_incorrectly_routed_to_llm_direct") or 0) > 0
            )
            for row in callable_models
        ),
    }


def _summary_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# V2 Non-GPT-4 Pioneer Model Benchmark Summary",
        "",
        "## Purpose",
        "",
        "This benchmark verifies V2 stability across callable non-GPT-4 Pioneer/API models. GPT-4/Gpt 4o family models are intentionally excluded.",
        "",
        "## Model-Major Semantics",
        "",
        "Each callable model runs the complete benchmark suite before the runner switches to the next model. No per-prompt model rotation is used.",
        "",
        "## Excluded GPT-4 Family Models",
        "",
    ]
    exclusion = summary.get("gpt4_family_exclusion") or {}
    lines.append(f"- Reason: {exclusion.get('reason') or 'excluded from this benchmark scope'}")
    lines.extend(["", "| Display Name | Model ID | Reason |", "| --- | --- | --- |"])
    for row in exclusion.get("excluded_models") or []:
        lines.append(f"| {row.get('display_name')} | `{row.get('model_id')}` | {row.get('reason')} |")
    lines.extend(
        [
            "",
            "## Model Availability",
            "",
            "| Display Name | Model ID | Available | Smoke | Benchmark | Error |",
            "| --- | --- | ---: | --- | --- | --- |",
        ]
    )
    for row in summary.get("models", []):
        availability = row.get("availability") or {}
        lines.append(
            f"| {row.get('model')} | `{row.get('pioneer_model_id')}` | {bool(availability.get('available'))} | {bool(((row.get('focused_smoke') or {}).get('metrics') or {}).get('focused_smoke_pass'))} | {row.get('benchmark_status') or 'not_run'} | {availability.get('error_category') or availability.get('error') or ''} |"
        )
    lines.extend(
        [
            "",
            "## Per-Model Benchmark Scores",
            "",
            "| Model | Verdict | Org35 Final | Org35 Correctness | Org35 Answer | Org35 SQL | Org35 API | Org35 Tool Calls | Internal50 Combined | Internal50 Behavior |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in summary.get("models", []):
        metrics = row.get("metrics") or {}
        org = metrics.get("organizer35") or {}
        internal = metrics.get("internal50") or {}
        lines.append(
            f"| {row.get('model')} | {row.get('stability_verdict')} | {_fmt(org.get('final_score'))} | {_fmt(org.get('correctness_score'))} | {_fmt(org.get('answer_score'))} | {_fmt(org.get('sql_score'))} | {_fmt(org.get('api_score'))} | {_fmt(org.get('tool_call_count'))} | {_fmt(internal.get('combined_score'))} | {_fmt(internal.get('behavior_score'))} |"
        )
    lines.extend(
        [
            "",
            "## Model Usage",
            "",
            "| Model | Active Provider | Model ID | LLM Calls | Semantic Calls | Direct Answer Calls | JSON Failures | Evidence Fallbacks |",
            "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in summary.get("models", []):
        usage = row.get("model_usage") or {}
        lines.append(
            f"| {row.get('model')} | {usage.get('active_llm_provider') or ''} | `{usage.get('pioneer_model_id') or row.get('pioneer_model_id')}` | {usage.get('llm_call_count')} | {usage.get('semantic_llm_call_count')} | {usage.get('direct_answer_llm_call_count')} | {usage.get('json_parse_failures')} | {usage.get('fallback_to_evidence_pipeline_count')} |"
        )
    lines.extend(
        [
            "",
            "## Safety",
            "",
            "| Model | no_tool_fp | api_required_underuse | unsupported_claims | concrete_data_llm_direct | JSON failures | Semantic fallbacks |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in summary.get("models", []):
        metrics = row.get("metrics") or {}
        safety = metrics.get("safety") or {}
        routing = metrics.get("routing_evidence") or {}
        lines.append(
            f"| {row.get('model')} | {safety.get('no_tool_fp')} | {safety.get('api_required_underuse')} | {safety.get('unsupported_claims')} | {safety.get('concrete_data_prompt_incorrectly_routed_to_llm_direct')} | {routing.get('json_parse_failure_count')} | {routing.get('semantic_fallback_count')} |"
        )
    lines.extend(
        [
            "",
            "## Routing / Evidence",
            "",
            "| Model | LLM_DIRECT | LLM_SAFE_DIRECT | Evidence Pipeline | Bypassed | EvidenceBus Built | Post-Evidence Router |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in summary.get("models", []):
        routing = ((row.get("metrics") or {}).get("routing_evidence") or {})
        lines.append(
            f"| {row.get('model')} | {routing.get('llm_direct_count')} | {routing.get('llm_safe_direct_count')} | {routing.get('evidence_pipeline_count')} | {routing.get('evidence_pipeline_bypassed_count')} | {routing.get('evidence_bus_built_count')} | {routing.get('post_evidence_answer_router_ran_count')} |"
        )
    conclusion = summary.get("cross_model_conclusion") or {}
    lines.extend(
        [
            "",
            "## Cross-Model Conclusion",
            "",
            f"- Callable models: {conclusion.get('callable_model_count')}",
            f"- Completed full benchmark models: {', '.join(conclusion.get('completed_full_benchmark_models') or []) or 'none'}",
            f"- Unavailable models: {', '.join(conclusion.get('unavailable_models') or []) or 'none'}",
            f"- Unsafe models: {', '.join(conclusion.get('unsafe_models') or []) or 'none'}",
            f"- V2 stable across callable models: {conclusion.get('v2_stable_across_callable_models')}",
            f"- Weak malformed responses failed closed: {conclusion.get('weak_models_failed_closed_if_malformed')}",
            "",
            "No recommendation is made to continue with only the best model; this report is about system robustness across model families.",
            "",
        ]
    )
    return "\n".join(lines)


def _fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}
    return {}


def _redact_benchmark(obj: Any) -> Any:
    if isinstance(obj, dict):
        redacted: dict[Any, Any] = {}
        for key, value in obj.items():
            lowered = str(key).lower()
            if (
                lowered in SECRET_KEYS
                or lowered.endswith("_token")
                or lowered.endswith("-token")
                or lowered in {"token", "bearer", "pioneer_api_key"}
                or "secret" in lowered
            ):
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = _redact_benchmark(value)
        return redacted
    if isinstance(obj, list):
        return [_redact_benchmark(item) for item in obj]
    if isinstance(obj, str):
        redacted = obj
        api_key = os.getenv("PIONEER_API_KEY")
        if api_key and len(api_key) >= 8:
            redacted = redacted.replace(api_key, "[REDACTED]")
        return SECRET_LIKE_RE.sub("[REDACTED]", redacted)
    return obj


class _temporary_environ:
    def __init__(self, updates: dict[str, str]) -> None:
        self.updates = updates
        self.previous: dict[str, str | None] = {}

    def __enter__(self) -> None:
        for key, value in self.updates.items():
            self.previous[key] = os.environ.get(key)
            os.environ[key] = value

    def __exit__(self, exc_type, exc, tb) -> None:
        for key, value in self.previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
