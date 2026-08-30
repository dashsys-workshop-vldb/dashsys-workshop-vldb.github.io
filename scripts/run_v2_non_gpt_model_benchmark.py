#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.pioneer_model_full_benchmark import run_pioneer_model_full_benchmark
from dashagent.pioneer_model_sweep import safe_model_name
from dashagent.pioneer_non_gpt_model_candidates import (
    apply_run_results_to_candidates,
    build_non_gpt_model_candidates,
    candidate_model_id_map,
    candidate_model_names,
    write_non_gpt_candidate_reports,
)
from dashagent.trajectory import redact_secrets
from scripts.load_local_env import load_local_env


REPORT_DIR = ROOT / "outputs" / "reports" / "v2_non_gpt_model_benchmark"
CATALOG_PATH = ROOT / "outputs" / "reports" / "pioneer_model_sweep" / "pioneer_model_catalog.json"
FINAL_BENCHMARK_CANDIDATES = ROOT / "outputs" / "reports" / "v2_final_benchmark" / "non_gpt_model_candidates.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the V2 non-GPT-4 Pioneer model benchmark.")
    parser.add_argument("--models", default=None, help="Optional comma-separated display-name override.")
    parser.add_argument("--report-dir", default=str(REPORT_DIR))
    args = parser.parse_args()

    config = Config.from_env(ROOT)
    load_local_env(config.project_root)
    os.environ["PIONEER_TIMEOUT_SEC"] = os.getenv("PIONEER_BENCHMARK_TIMEOUT_SEC", "20")
    os.environ["PIONEER_GPT_FALLBACK_PROBE_TIMEOUT_SEC"] = os.getenv("PIONEER_AVAILABILITY_TIMEOUT_SEC", "25")
    os.environ["PIONEER_FOCUSED_SMOKE_TIMEOUT_SEC"] = os.getenv("PIONEER_FOCUSED_SMOKE_TIMEOUT_SEC", "60")
    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)

    catalog_payload = _load_catalog()
    candidate_payload = build_non_gpt_model_candidates(catalog_payload.get("records") or [])
    if args.models:
        allowed = {item.strip() for item in args.models.split(",") if item.strip()}
        candidate_payload["candidate_models"] = [
            row for row in candidate_payload.get("candidate_models") or [] if row.get("display_name") in allowed
        ]
    candidate_paths = write_non_gpt_candidate_reports(report_dir, candidate_payload, mirror_path=FINAL_BENCHMARK_CANDIDATES)
    models = candidate_model_names(candidate_payload)
    model_id_map = candidate_model_id_map(candidate_payload)

    command_manifest = _write_manifest(report_dir)
    baseline = _run_baseline_once(report_dir)

    previous_map = os.environ.get("PIONEER_MODEL_ID_MAP_JSON")
    os.environ["PIONEER_MODEL_ID_MAP_JSON"] = json.dumps(model_id_map, sort_keys=True)
    try:
        benchmark = run_pioneer_model_full_benchmark(
            config,
            models=models,
            report_dir=report_dir,
            commands=_per_model_command_plan(),
            focused_smoke_runner=_subprocess_focused_smoke_runner,
        )
    finally:
        if previous_map is None:
            os.environ.pop("PIONEER_MODEL_ID_MAP_JSON", None)
        else:
            os.environ["PIONEER_MODEL_ID_MAP_JSON"] = previous_map

    _copy_smoke_reports(report_dir, benchmark.get("models") or [])
    updated_candidates = apply_run_results_to_candidates(candidate_payload, benchmark.get("models") or [])
    write_non_gpt_candidate_reports(report_dir, updated_candidates, mirror_path=FINAL_BENCHMARK_CANDIDATES)
    gates = _run_gates_once(report_dir)

    summary = _summary_payload(
        candidate_payload=updated_candidates,
        benchmark=benchmark,
        baseline=baseline,
        gates=gates,
        command_manifest=command_manifest,
        candidate_paths=candidate_paths,
    )
    summary_json = report_dir / "v2_non_gpt_model_benchmark_summary.json"
    summary_md = report_dir / "v2_non_gpt_model_benchmark_summary.md"
    summary_json.write_text(json.dumps(redact_secrets(summary), indent=2, sort_keys=True, default=str), encoding="utf-8")
    summary_md.write_text(_summary_markdown(summary), encoding="utf-8")
    print(json.dumps({"summary_json": str(summary_json), "summary_md": str(summary_md)}, indent=2, sort_keys=True))
    return 0


def _load_catalog() -> dict[str, Any]:
    if not CATALOG_PATH.exists():
        raise FileNotFoundError(f"Missing Pioneer catalog. Run python3 scripts/discover_pioneer_models.py first: {CATALOG_PATH}")
    payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid Pioneer catalog: {CATALOG_PATH}")
    return payload


def _per_model_command_plan() -> list[dict[str, Any]]:
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
    ]


def _run_baseline_once(report_dir: Path) -> dict[str, Any]:
    baseline_outputs = report_dir / "baseline_sql_first_outputs"
    baseline_outputs.mkdir(parents=True, exist_ok=True)
    command = ["python3", "scripts/run_dev_eval.py", "--strict", "--strategies", "SQL_FIRST_API_VERIFY"]
    env = dict(os.environ)
    env["DASHAGENT_OUTPUTS_DIR"] = str(baseline_outputs)
    result = _run_command(command, env=env, timeout_sec=1800)
    payload = {"name": "packaged_baseline_sql_first", "command": command, **result, "outputs_dir": str(baseline_outputs)}
    (report_dir / "baseline_sql_first.json").write_text(json.dumps(redact_secrets(payload), indent=2, sort_keys=True), encoding="utf-8")
    (report_dir / "baseline_sql_first.log").write_text(_log_text(payload), encoding="utf-8")
    return payload


def _run_gates_once(report_dir: Path) -> list[dict[str, Any]]:
    gate_dir = report_dir / "gates"
    gate_dir.mkdir(parents=True, exist_ok=True)
    gates = [
        {"name": "semantic_route_promotion_gate", "command": ["python3", "scripts/run_semantic_route_promotion_gate.py"], "timeout_sec": 900},
        {"name": "integrated_robustness_gate", "command": ["python3", "scripts/run_integrated_robustness_gate.py"], "timeout_sec": 900},
        {"name": "hidden_style_eval", "command": ["python3", "scripts/run_hidden_style_eval.py"], "timeout_sec": 900},
        {"name": "check_submission_ready", "command": ["python3", "scripts/check_submission_ready.py"], "timeout_sec": 900},
    ]
    results: list[dict[str, Any]] = []
    for gate in gates:
        result = {"name": gate["name"], "command": gate["command"], **_run_command(gate["command"], timeout_sec=int(gate["timeout_sec"]))}
        results.append(redact_secrets(result))
        (gate_dir / f"{gate['name']}.json").write_text(json.dumps(redact_secrets(result), indent=2, sort_keys=True), encoding="utf-8")
        (gate_dir / f"{gate['name']}.log").write_text(_log_text(result), encoding="utf-8")
    return results


def _subprocess_focused_smoke_runner(config: Config, *, models: list[str], report_dir: Path) -> dict[str, Any]:
    model = models[0]
    safe = safe_model_name(model)
    timeout_sec = int(os.getenv("PIONEER_FOCUSED_SMOKE_TIMEOUT_SEC", "120"))
    code = (
        "import json, sys;"
        "from pathlib import Path;"
        "from dashagent.config import Config;"
        "from dashagent.pioneer_model_sweep import run_pioneer_model_sweep;"
        "from scripts.load_local_env import load_local_env;"
        f"root=Path({str(ROOT)!r});"
        "config=Config.from_env(root);"
        "load_local_env(config.project_root);"
        "result=run_pioneer_model_sweep(config, models=[sys.argv[1]], report_dir=Path(sys.argv[2]));"
        "print(json.dumps(result['paths'], sort_keys=True))"
    )
    command = ["python3", "-c", code, model, str(report_dir)]
    try:
        proc = subprocess.run(
            command,
            cwd=str(ROOT),
            env=dict(os.environ),
            text=True,
            capture_output=True,
            timeout=timeout_sec,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "models": [
                {
                    "model": model,
                    "pioneer_model": model,
                    "pioneer_model_id": _model_id_for_display(model),
                    "safe_model_name": safe,
                    "availability": {"available": True},
                    "metrics": {
                        "json_parse_failures": 0,
                        "semantic_fallback_count": 0,
                        "llm_direct_count": 0,
                        "llm_safe_direct_count": 0,
                        "evidence_pipeline_count": 0,
                        "evidence_pipeline_bypassed_count": 0,
                        "evidence_bus_built_count": 0,
                        "evidence_bus_non_empty_count": 0,
                        "result_bundle_built_count": 0,
                        "declared_pass_count": 0,
                        "planner_usable_count": 0,
                        "post_evidence_answer_router_ran_count": 0,
                        "no_tool_fp": 0,
                        "api_required_underuse": 0,
                        "unsupported_claims": 0,
                        "final_syntax_gate_failures": 0,
                        "final_semantic_gate_failures": 0,
                        "final_gates_all_failed": False,
                        "focused_smoke_pass": False,
                    },
                    "prompt_results": [],
                    "semantic_probe_results": [],
                    "smoke_timeout": True,
                    "error": f"focused_smoke_timeout_after_{timeout_sec}s",
                }
            ]
        }
    if proc.returncode != 0:
        return {
            "models": [
                {
                    "model": model,
                    "pioneer_model": model,
                    "pioneer_model_id": _model_id_for_display(model),
                    "safe_model_name": safe,
                    "availability": {"available": True},
                    "metrics": {"focused_smoke_pass": False, "planner_usable_count": 0, "declared_pass_count": 0},
                    "prompt_results": [],
                    "semantic_probe_results": [],
                    "error": redact_secrets((proc.stderr or proc.stdout)[-1200:]),
                }
            ]
        }
    per_model = report_dir / f"per_model_{safe}.json"
    if not per_model.exists():
        return {
            "models": [
                {
                    "model": model,
                    "pioneer_model": model,
                    "pioneer_model_id": _model_id_for_display(model),
                    "safe_model_name": safe,
                    "availability": {"available": True},
                    "metrics": {"focused_smoke_pass": False, "planner_usable_count": 0, "declared_pass_count": 0},
                    "prompt_results": [],
                    "semantic_probe_results": [],
                    "error": "focused_smoke_report_missing",
                }
            ]
        }
    return {"models": [json.loads(per_model.read_text(encoding="utf-8"))]}


def _model_id_for_display(model: str) -> str:
    raw = os.getenv("PIONEER_MODEL_ID_MAP_JSON") or "{}"
    try:
        mapping = json.loads(raw)
        if isinstance(mapping, dict):
            return str(mapping.get(model) or model)
    except Exception:
        pass
    return model


def _run_command(command: list[str], *, env: dict[str, str] | None = None, timeout_sec: int) -> dict[str, Any]:
    started = time.perf_counter()
    proc = subprocess.run(
        command,
        cwd=str(ROOT),
        env=env or dict(os.environ),
        text=True,
        capture_output=True,
        timeout=timeout_sec,
        check=False,
    )
    return redact_secrets(
        {
            "returncode": proc.returncode,
            "stdout": proc.stdout[-12000:],
            "stderr": proc.stderr[-12000:],
            "duration_sec": round(time.perf_counter() - started, 4),
        }
    )


def _copy_smoke_reports(report_dir: Path, model_results: list[dict[str, Any]]) -> None:
    for row in model_results:
        safe = str(row.get("safe_model_name") or safe_model_name(str(row.get("model") or "model")))
        source = report_dir / "runs" / safe / "outputs" / "focused_smoke" / f"per_model_{safe}.json"
        destination = report_dir / f"per_model_{safe}_smoke.json"
        if source.exists():
            shutil.copyfile(source, destination)
        else:
            payload = row.get("focused_smoke") or {}
            destination.write_text(json.dumps(redact_secrets(payload), indent=2, sort_keys=True, default=str), encoding="utf-8")


def _write_manifest(report_dir: Path) -> str:
    path = report_dir / "benchmark_command_manifest.json"
    payload = {
        "purpose": "V2 stability benchmark across catalog-confirmed non-GPT-4 Pioneer models.",
        "model_major_semantics": True,
        "pioneer_timeout_sec": os.getenv("PIONEER_TIMEOUT_SEC"),
        "focused_smoke_timeout_sec": os.getenv("PIONEER_FOCUSED_SMOKE_TIMEOUT_SEC"),
        "baseline_command": ["python3", "scripts/run_dev_eval.py", "--strict", "--strategies", "SQL_FIRST_API_VERIFY"],
        "per_model_commands": _per_model_command_plan(),
        "gates_once_after_models": [
            ["python3", "scripts/run_semantic_route_promotion_gate.py"],
            ["python3", "scripts/run_integrated_robustness_gate.py"],
            ["python3", "scripts/run_hidden_style_eval.py"],
            ["python3", "scripts/check_submission_ready.py"],
        ],
    }
    path.write_text(json.dumps(redact_secrets(payload), indent=2, sort_keys=True), encoding="utf-8")
    return str(path)


def _summary_payload(
    *,
    candidate_payload: dict[str, Any],
    benchmark: dict[str, Any],
    baseline: dict[str, Any],
    gates: list[dict[str, Any]],
    command_manifest: str,
    candidate_paths: dict[str, str],
) -> dict[str, Any]:
    models = benchmark.get("models") or []
    return {
        "purpose": "This benchmark tests V2 stability across callable non-GPT-4 Pioneer/API models. GPT-4 family was intentionally excluded.",
        "model_major_semantics": True,
        "packaged_default_expected": "SQL_FIRST_API_VERIFY",
        "v2_strategy": "ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2",
        "candidate_paths": candidate_paths,
        "benchmark_command_manifest": command_manifest,
        "excluded_models": candidate_payload.get("excluded_models") or [],
        "candidate_models": candidate_payload.get("candidate_models") or [],
        "baseline_sql_first": baseline,
        "models": models,
        "gates": gates,
        "objective_totals": {
            "models_attempted": len(models),
            "models_available": sum(1 for row in models if bool((row.get("availability") or {}).get("available"))),
            "models_smoke_passed": sum(1 for row in models if bool(((row.get("focused_smoke") or {}).get("metrics") or {}).get("focused_smoke_pass"))),
            "models_benchmarked": sum(1 for row in models if row.get("benchmark_status") == "completed"),
            "unsupported_claims": sum(int(((row.get("metrics") or {}).get("safety") or {}).get("unsupported_claims") or 0) for row in models),
            "no_tool_fp": sum(int(((row.get("metrics") or {}).get("safety") or {}).get("no_tool_fp") or 0) for row in models),
        },
        "recommendation": {
            "safe_to_keep": True,
            "safe_to_commit_reports": True,
            "safe_to_promote_v2": False,
            "reason": "V2 remains explicit/shadow-only; promotion requires an explicit passing promotion gate and manual review.",
        },
    }


def _summary_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# V2 Non-GPT-4 Pioneer Model Benchmark",
        "",
        "## Purpose",
        "",
        "This benchmark tests V2 stability across callable non-GPT-4 Pioneer/API models. GPT-4 family was intentionally excluded.",
        "",
        "## Excluded GPT-4 Models",
        "",
        "| Display Name | Model ID | Reason |",
        "| --- | --- | --- |",
    ]
    for row in summary.get("excluded_models") or []:
        lines.append(f"| {row.get('display_name')} | `{row.get('model_id')}` | {row.get('reason')} |")
    lines.extend(
        [
            "",
            "## Candidate Models",
            "",
            "| Display Name | Model ID | Family | Available | Smoke | Benchmark |",
            "| --- | --- | --- | ---: | --- | --- |",
        ]
    )
    for row in summary.get("candidate_models") or []:
        lines.append(
            f"| {row.get('display_name')} | `{row.get('model_id')}` | {row.get('family')} | {row.get('callable')} | {row.get('smoke_status')} | {row.get('benchmark_status')} |"
        )
    lines.extend(
        [
            "",
            "## Per-Model Objective Results",
            "",
            "| Model | Available | Smoke | Benchmark | SQL Calls | API Calls | EvidenceBus Non-Empty | Unsupported | no_tool_fp | Final Syntax Gate Failures | Final Semantic Gate Failures |",
            "| --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in summary.get("models") or []:
        metrics = row.get("metrics") or {}
        routing = metrics.get("routing_evidence") or {}
        safety = metrics.get("safety") or {}
        execution = metrics.get("execution") or {}
        smoke_metrics = ((row.get("focused_smoke") or {}).get("metrics") or {})
        lines.append(
            f"| {row.get('model')} | {bool((row.get('availability') or {}).get('available'))} | {bool(smoke_metrics.get('focused_smoke_pass'))} | {row.get('benchmark_status')} | {execution.get('focused_smoke_sql_calls')} | {execution.get('focused_smoke_api_calls')} | {routing.get('evidence_bus_non_empty_count')} | {safety.get('unsupported_claims')} | {safety.get('no_tool_fp')} | {routing.get('final_syntax_gate_failures')} | {routing.get('final_semantic_gate_failures')} |"
        )
    lines.extend(
        [
            "",
            "## Failure Analysis By Objective Error Type",
            "",
        ]
    )
    for row in summary.get("models") or []:
        metrics = row.get("metrics") or {}
        routing = metrics.get("routing_evidence") or {}
        safety = metrics.get("safety") or {}
        availability = row.get("availability") or {}
        failures = []
        if not availability.get("available"):
            failures.append("provider_error")
        if int(routing.get("json_parse_failure_count") or 0) > 0:
            failures.append("planner_malformed_output")
        if int(routing.get("declared_pass_count") or 0) == 0 and availability.get("available"):
            failures.append("planner_toolcall_failure")
        if int(routing.get("evidence_bus_non_empty_count") or 0) == 0 and availability.get("available"):
            failures.append("empty EvidenceBus")
        if int(routing.get("final_syntax_gate_failures") or 0) > 0:
            failures.append("final syntax gate failure")
        if int(routing.get("final_semantic_gate_failures") or 0) > 0:
            failures.append("final semantic grounding failure")
        if int(safety.get("unsupported_claims") or 0) > 0:
            failures.append("unsupported claim")
        if int(safety.get("no_tool_fp") or 0) > 0:
            failures.append("no_tool_fp")
        lines.append(f"- {row.get('model')}: {', '.join(failures) if failures else 'none recorded'}")
    totals = summary.get("objective_totals") or {}
    lines.extend(
        [
            "",
            "## Objective Totals",
            "",
            f"- Models attempted: {totals.get('models_attempted')}",
            f"- Models available: {totals.get('models_available')}",
            f"- Models smoke-passed: {totals.get('models_smoke_passed')}",
            f"- Models benchmarked: {totals.get('models_benchmarked')}",
            f"- Unsupported claims: {totals.get('unsupported_claims')}",
            f"- no_tool_fp: {totals.get('no_tool_fp')}",
            "",
            "## Correctness Standard",
            "",
            "Answer grounding correctness means semantic correctness, required information present, no false or unsupported claims, and correct scope/caveats. Hidden-eval or gold-wording similarity is not treated as real correctness in this report.",
            "",
            "## Recommendation",
            "",
            f"- Safe to keep: {summary['recommendation']['safe_to_keep']}",
            f"- Safe to commit reports: {summary['recommendation']['safe_to_commit_reports']}",
            f"- Safe to promote V2: {summary['recommendation']['safe_to_promote_v2']}",
            f"- Reason: {summary['recommendation']['reason']}",
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


def _log_text(payload: dict[str, Any]) -> str:
    return json.dumps(redact_secrets(payload), indent=2, sort_keys=True, default=str)


if __name__ == "__main__":
    raise SystemExit(main())
