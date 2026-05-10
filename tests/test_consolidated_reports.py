from __future__ import annotations

import json
import re
from pathlib import Path

from scripts.generate_consolidated_reports import generate_consolidated_reports


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_consolidated_reports_are_parseable_and_match_sources(tiny_project):
    outputs = tiny_project.outputs_dir
    _write_json(
        outputs / "eval_results_strict.json",
        {
            "summary": {
                "by_strategy": {
                    "SQL_FIRST_API_VERIFY": {
                        "avg_final_score": 0.6491,
                        "avg_correctness_score": 0.6743,
                        "avg_estimated_tokens": 831.4571,
                        "avg_runtime": 0.0092,
                        "avg_tool_call_count": 1.4571,
                    }
                }
            }
        },
    )
    _write_json(
        outputs / "winner_readiness_report.json",
        {
            "packaged": {
                "preferred_strategy": "SQL_FIRST_API_VERIFY",
                "strict_final_score": 0.6491,
                "strict_correctness": 0.6743,
                "final_submission_ready": True,
            },
            "final_recommendation": "ready_to_submit_with_official_token_reduction",
        },
    )
    _write_json(outputs / "hidden_style_eval.json", {"summary": {"passed_cases": 48, "total_cases": 48}, "repair_execution_enabled": False, "compact_context_enabled": False})
    _write_json(outputs / "official_token_reduction_promotion_report.json", {"summary": {"promotion_kept": True}})
    _write_json(outputs / "autonomous_packaged_trial.json", {"summary": {"strict_final_score": 0.6558}})
    _write_json(outputs / "autonomous_score_push_report.json", {"summary": {"best_achieved_score": 0.6558, "target_0_70_reached": False, "target_0_75_reached": False}})
    _write_json(outputs / "score075_blocker_analysis.json", {"best_achieved_score": 0.6558})
    _write_json(
        outputs / "llm_baseline_eval_report.json",
        {
            "framework": "generic_sdk_llm_baseline",
            "backend_name": "qwen2.5-32b-instruct",
            "provider_type": "openai_compatible",
            "backend_type": "openai_sdk",
            "tool_calling_supported": True,
            "smoke_test_passed": True,
            "strict_scoring_status": "available",
            "recommendation": "keep_shadow_only",
            "deterministic_sql_first_api_verify": {"avg_final_score": 0.6491},
            "per_strategy": [{"system": "LLM_CONTROLLER_OPTIMIZED_AGENT", "strict_score": 0.6338, "strict_correctness": 0.6641}],
        },
    )
    _write_json(outputs / "llm_strict_baseline_eval.json", {"summary": {"recommendation": "keep_shadow_only", "strict_scoring_status": "available"}})
    _write_json(outputs / "llm_sdk_backend_check.json", {"ok": True, "backend_name": "qwen2.5-32b-instruct", "backend_type": "openai_sdk", "provider_type": "openai_compatible"})
    _write_json(
        outputs / "visualizations" / "sql_prompt_storyboard_primary.json",
        {
            "query_id": "example_011",
            "raw_prompt": "How many schemas do I have?",
            "selected_table": "dim_blueprint",
            "selected_column": "BLUEPRINTID",
            "aggregation": "COUNT DISTINCT",
            "sql_result_summary": "blueprint_count = 74",
        },
    )
    _write_json(outputs / "visualizations" / "index.json", {"entries": []})

    generate_consolidated_reports(tiny_project)

    reports = outputs / "reports"
    required = [
        "system_summary",
        "llm_baseline_summary",
        "accuracy_and_bottleneck_summary",
        "visualization_summary",
        "report_index",
    ]
    for stem in required:
        assert (reports / f"{stem}.json").exists()
        assert (reports / f"{stem}.md").exists()
        json.loads((reports / f"{stem}.json").read_text(encoding="utf-8"))

    system = json.loads((reports / "system_summary.json").read_text(encoding="utf-8"))
    llm = json.loads((reports / "llm_baseline_summary.json").read_text(encoding="utf-8"))
    visualization = json.loads((reports / "visualization_summary.json").read_text(encoding="utf-8"))
    assert system["preferred_strategy"] == "SQL_FIRST_API_VERIFY"
    assert system["packaged_strict_score"] == 0.6491
    assert system["hidden_style"]["label"] == "48/48"
    assert llm["framework"] == "generic_sdk_llm_baseline"
    assert llm["current_backend_model"] == "qwen2.5-32b-instruct"
    assert llm["recommendation"] == "keep_shadow_only"
    assert visualization["primary_example"] == "example_011"
    assert visualization["prompt_to_sql_mapping"]["schemas"] == "dim_blueprint"


def test_consolidated_report_links_and_secret_scan_on_current_outputs():
    reports_dir = Path("outputs/reports")
    index = reports_dir / "report_index.md"
    if not index.exists():
        return
    text = index.read_text(encoding="utf-8")
    for link in re.findall(r"\]\(([^)]+)\)", text):
        if link.startswith("http"):
            continue
        assert (reports_dir / link).exists(), link
    combined = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in reports_dir.glob("*") if path.is_file())
    assert "Authorization" + ": " + "Bearer" not in combined
    assert not re.search(r"sk-[A-Za-z0-9_-]{12,}", combined)
