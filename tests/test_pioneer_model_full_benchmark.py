from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import dashagent.pioneer_model_full_benchmark as fullbench
from dashagent.pioneer_model_sweep import DEFAULT_PIONEER_MODEL_SWEEP, safe_model_name


def test_full_benchmark_runs_model_major_for_all_callable_models(tmp_path, monkeypatch) -> None:
    call_order: list[tuple[str, str]] = []

    def fake_probe(model_id: str) -> dict:
        return {"available": True, "model": model_id}

    def fake_smoke(config, *, models, report_dir):
        return {
            "models": [
                {
                    "model": models[0],
                    "pioneer_model": models[0],
                    "pioneer_model_id": fullbench.resolve_pioneer_model_id(models[0]),
                    "safe_model_name": safe_model_name(models[0]),
                    "availability": {"available": True},
                    "metrics": {
                        "json_parse_failures": 0,
                        "semantic_fallback_count": 0,
                        "llm_direct_count": 2,
                        "evidence_pipeline_count": 4,
                        "evidence_pipeline_bypassed_count": 2,
                        "evidence_bus_built_count": 4,
                        "post_evidence_answer_router_ran_count": 4,
                        "no_tool_fp": 0,
                        "api_required_underuse": 0,
                        "unsupported_claims": 0,
                        "focused_smoke_pass": True,
                    },
                }
            ]
        }

    def fake_runner(command, env, cwd, timeout_sec):
        call_order.append((env["PIONEER_MODEL"], env["PIONEER_MODEL_ID"], command["name"]))
        _write_fake_artifacts(Path(env["DASHAGENT_OUTPUTS_DIR"]), tmp_path / "reports", command["name"])
        return {"returncode": 0, "stdout": "ok", "stderr": "", "duration_sec": 0.01}

    monkeypatch.setenv("PIONEER_MODEL_ID_MAP_JSON", '{"ModelA":"id-a","ModelB":"id-b"}')
    result = fullbench.run_pioneer_model_full_benchmark(
        SimpleNamespace(outputs_dir=tmp_path),
        models=["ModelA", "ModelB"],
        report_dir=tmp_path,
        commands=fullbench.minimal_test_command_plan(),
        availability_probe=fake_probe,
        focused_smoke_runner=fake_smoke,
        command_runner=fake_runner,
    )

    assert call_order == [
        ("ModelA", "id-a", "organizer35_strict_v2"),
        ("ModelA", "id-a", "internal50_v2"),
        ("ModelB", "id-b", "organizer35_strict_v2"),
        ("ModelB", "id-b", "internal50_v2"),
    ]
    assert [row["model"] for row in result["models"]] == ["ModelA", "ModelB"]
    assert result["models"][0]["metrics"]["routing_evidence"]["post_evidence_answer_router_ran_count"] == 4


def test_full_benchmark_reports_all_seven_and_unavailable_is_not_fatal(tmp_path, monkeypatch) -> None:
    def fake_probe(model_id: str) -> dict:
        if model_id == "gpt-4o":
            return {"available": False, "model": model_id, "error_category": "auth_or_401", "error": "provider_auth_error"}
        return {"available": True, "model": model_id}

    def fake_runner(command, env, cwd, timeout_sec):
        _write_fake_artifacts(Path(env["DASHAGENT_OUTPUTS_DIR"]), tmp_path / "reports", command["name"])
        return {"returncode": 0, "stdout": "ok", "stderr": "", "duration_sec": 0.01}

    monkeypatch.setenv("PIONEER_MODEL_ID_MAP_JSON", json.dumps(fullbench.DEFAULT_SELECTED_MODEL_ID_MAP))
    result = fullbench.run_pioneer_model_full_benchmark(
        SimpleNamespace(outputs_dir=tmp_path),
        report_dir=tmp_path,
        commands=fullbench.minimal_test_command_plan(),
        availability_probe=fake_probe,
        focused_smoke_runner=_fake_smoke,
        command_runner=fake_runner,
    )

    assert [row["model"] for row in result["models"]] == DEFAULT_PIONEER_MODEL_SWEEP
    assert result["models"][0]["availability"]["available"] is False
    assert result["models"][0]["stability_verdict"] == "UNAVAILABLE"
    assert any(row["availability"]["available"] for row in result["models"][1:])
    summary = json.loads((tmp_path / "pioneer_model_full_benchmark_summary.json").read_text(encoding="utf-8"))
    assert len(summary["models"]) == 7


def test_full_benchmark_does_not_skip_deepseek_or_qwen_after_json_failures(tmp_path, monkeypatch) -> None:
    run_models: list[str] = []

    def fake_runner(command, env, cwd, timeout_sec):
        run_models.append(env["PIONEER_MODEL_DISPLAY"])
        _write_fake_artifacts(Path(env["DASHAGENT_OUTPUTS_DIR"]), tmp_path / "reports", command["name"])
        return {"returncode": 0, "stdout": "ok", "stderr": "", "duration_sec": 0.01}

    monkeypatch.setenv("PIONEER_MODEL_ID_MAP_JSON", json.dumps(fullbench.DEFAULT_SELECTED_MODEL_ID_MAP))
    result = fullbench.run_pioneer_model_full_benchmark(
        SimpleNamespace(outputs_dir=tmp_path),
        models=["DeepSeek V4 Flash", "Qwen3 4B Instruct 2507"],
        report_dir=tmp_path,
        commands=fullbench.minimal_test_command_plan(),
        availability_probe=lambda model_id: {"available": True, "model": model_id},
        focused_smoke_runner=_fake_smoke_with_json_failures,
        command_runner=fake_runner,
    )

    assert run_models == [
        "DeepSeek V4 Flash",
        "DeepSeek V4 Flash",
        "Qwen3 4B Instruct 2507",
        "Qwen3 4B Instruct 2507",
    ]
    assert {row["stability_verdict"] for row in result["models"]} == {"SAFE_BUT_DEGRADED"}


def test_one_model_command_failure_does_not_stop_full_sweep(tmp_path, monkeypatch) -> None:
    call_order: list[str] = []

    def fake_runner(command, env, cwd, timeout_sec):
        model = env["PIONEER_MODEL_DISPLAY"]
        call_order.append(model)
        _write_fake_artifacts(Path(env["DASHAGENT_OUTPUTS_DIR"]), tmp_path / "reports", command["name"])
        if model == "ModelA" and command["name"] == "organizer35_strict_v2":
            return {"returncode": 2, "stdout": "", "stderr": "failed", "duration_sec": 0.01}
        return {"returncode": 0, "stdout": "ok", "stderr": "", "duration_sec": 0.01}

    monkeypatch.setenv("PIONEER_MODEL_ID_MAP_JSON", '{"ModelA":"id-a","ModelB":"id-b"}')
    result = fullbench.run_pioneer_model_full_benchmark(
        SimpleNamespace(outputs_dir=tmp_path),
        models=["ModelA", "ModelB"],
        report_dir=tmp_path,
        commands=fullbench.minimal_test_command_plan(),
        availability_probe=lambda model_id: {"available": True, "model": model_id},
        focused_smoke_runner=_fake_smoke,
        command_runner=fake_runner,
    )

    assert call_order == ["ModelA", "ModelA", "ModelB", "ModelB"]
    assert result["models"][0]["command_failures"] == 1
    assert result["models"][1]["command_failures"] == 0


def test_per_model_benchmark_report_contains_one_active_model(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PIONEER_MODEL_ID_MAP_JSON", '{"ModelA":"id-a"}')
    fullbench.run_pioneer_model_full_benchmark(
        SimpleNamespace(outputs_dir=tmp_path),
        models=["ModelA"],
        report_dir=tmp_path,
        commands=fullbench.minimal_test_command_plan(),
        availability_probe=lambda model_id: {"available": True, "model": model_id},
        focused_smoke_runner=_fake_smoke,
        command_runner=lambda command, env, cwd, timeout_sec: _runner_with_fake_artifacts(command, env, tmp_path),
    )

    payload = json.loads((tmp_path / "per_model_modela_benchmark.json").read_text(encoding="utf-8"))
    active_models = {payload["pioneer_model"], payload["model"]}
    active_models.update(row["pioneer_model"] for row in payload["commands"])
    assert active_models == {"ModelA"}
    assert payload["pioneer_model_id"] == "id-a"


def test_full_benchmark_redacts_api_key_from_logs(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("PIONEER_API_KEY", "sk-test-secret-value-123456")
    monkeypatch.setenv("PIONEER_MODEL_ID_MAP_JSON", '{"ModelA":"id-a"}')

    def leaking_runner(command, env, cwd, timeout_sec):
        _write_fake_artifacts(Path(env["DASHAGENT_OUTPUTS_DIR"]), tmp_path / "reports", command["name"])
        return {"returncode": 0, "stdout": "using sk-test-secret-value-123456", "stderr": "", "duration_sec": 0.01}

    fullbench.run_pioneer_model_full_benchmark(
        SimpleNamespace(outputs_dir=tmp_path),
        models=["ModelA"],
        report_dir=tmp_path,
        commands=fullbench.minimal_test_command_plan(),
        availability_probe=lambda model_id: {"available": True, "model": model_id},
        focused_smoke_runner=_fake_smoke,
        command_runner=leaking_runner,
    )

    text = (tmp_path / "per_model_modela_benchmark.log").read_text(encoding="utf-8")
    assert "sk-test-secret-value-123456" not in text
    assert "[REDACTED]" in text


def _fake_smoke(config, *, models, report_dir):
    model = models[0]
    return {
        "models": [
            {
                "model": model,
                "pioneer_model": model,
                "pioneer_model_id": fullbench.resolve_pioneer_model_id(model),
                "safe_model_name": safe_model_name(model),
                "availability": {"available": True},
                "metrics": {
                    "json_parse_failures": 0,
                    "semantic_fallback_count": 0,
                    "llm_direct_count": 2,
                    "llm_safe_direct_count": 0,
                    "evidence_pipeline_count": 4,
                    "evidence_pipeline_bypassed_count": 2,
                    "evidence_bus_built_count": 4,
                    "post_evidence_answer_router_ran_count": 4,
                    "no_tool_fp": 0,
                    "api_required_underuse": 0,
                    "unsupported_claims": 0,
                    "focused_smoke_pass": True,
                },
            }
        ]
    }


def _fake_smoke_with_json_failures(config, *, models, report_dir):
    payload = _fake_smoke(config, models=models, report_dir=report_dir)
    payload["models"][0]["metrics"]["json_parse_failures"] = 6
    payload["models"][0]["metrics"]["semantic_fallback_count"] = 6
    return payload


def _runner_with_fake_artifacts(command, env, tmp_path):
    _write_fake_artifacts(Path(env["DASHAGENT_OUTPUTS_DIR"]), tmp_path / "reports", command["name"])
    return {"returncode": 0, "stdout": "ok", "stderr": "", "duration_sec": 0.01}


def _write_fake_artifacts(outputs_dir: Path, report_dir: Path, command_name: str) -> None:
    outputs_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    if command_name == "organizer35_strict_v2":
        (outputs_dir / "eval_results_strict.json").write_text(
            json.dumps(
                {
                    "summary": {
                        "by_strategy": {
                            "ROBUST_GENERALIZED_HARNESS_CANDIDATE_V2": {
                                "avg_final_score": 0.7,
                                "avg_correctness_score": 0.72,
                                "avg_answer_score": 0.4,
                                "avg_sql_score": 0.9,
                                "avg_api_score": 0.95,
                                "avg_tool_call_count": 1.2,
                            }
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
    if command_name == "internal50_v2":
        internal_report = outputs_dir / "internal50_reports"
        internal_report.mkdir(parents=True, exist_ok=True)
        (internal_report / "dashagent_500_prompt_suite_eval_real.json").write_text(
            json.dumps(
                {
                    "mode_summary": {
                        "robust_generalized_harness_candidate_v2_real": {
                            "overall_score": 0.81,
                            "behavior_score": 0.82,
                            "sql_calls": 10,
                            "api_calls": 4,
                            "no_tool_false_positive": 0,
                            "api_required_underuse": 0,
                            "unsupported_claims": 0,
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
