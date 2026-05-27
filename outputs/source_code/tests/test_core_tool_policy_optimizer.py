from __future__ import annotations

import json
import re
from pathlib import Path

from scripts.generate_consolidated_reports import generate_consolidated_reports
from scripts.run_core_tool_optimization_audit import run_core_tool_optimization_audit
from scripts.run_core_tool_policy_optimizer import run_core_tool_policy_optimizer


SECRET_VALUE_RE = re.compile(
    r"sk-[A-Za-z0-9_-]{12,}"
    r"|Bearer\s+[A-Za-z0-9._-]{12,}"
    r"|Authorization:\s*Bearer\s+[A-Za-z0-9._-]+"
    r"|[A-Za-z0-9]{3}\*\*\*",
    re.IGNORECASE,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _seed_inputs(outputs: Path) -> None:
    reports = outputs / "reports"
    _write_json(
        outputs / "eval_results_strict.json",
        {
            "summary": {
                "by_strategy": {
                    "SQL_FIRST_API_VERIFY": {
                        "avg_final_score": 0.6553,
                        "avg_correctness_score": 0.6805,
                        "avg_sql_score": 0.9333,
                        "avg_api_score": 0.9791,
                        "avg_answer_score": 0.3199,
                        "avg_tool_call_count": 1.4571,
                        "avg_estimated_tokens": 834.6,
                        "avg_runtime": 0.0123,
                    }
                }
            }
        },
    )
    _write_json(
        reports / "system_summary.json",
        {
            "preferred_strategy": "SQL_FIRST_API_VERIFY",
            "packaged_strict_score": 0.6553,
            "hidden_style": {"label": "48/48", "passed": 48, "total": 48},
            "final_submission_ready": True,
        },
    )
    _write_json(reports / "sdk_usage_audit.json", {"summary": {"runtime_llm_direct_http_hits": 0}})
    _write_json(reports / "live_api_readiness_smoke.json", {"summary": {"live_success_count": 0}})
    _write_json(
        reports / "generated_prompt_suite_local_diagnostic.json",
        {"diagnostic_only": True, "total_prompts": 250, "runtime_pass_count": 250, "dry_run_api_call_count": 212},
    )


def test_core_tool_optimizer_generates_tool_specific_reports(tiny_project):
    _seed_inputs(tiny_project.outputs_dir)

    audit = run_core_tool_optimization_audit(tiny_project)
    optimizer = run_core_tool_policy_optimizer(tiny_project)

    reports = tiny_project.outputs_dir / "reports"
    for stem in [
        "core_tool_optimization_audit",
        "core_tool_optimization_search_space",
        "core_tool_policy_optimizer",
        "core_tool_policy_search_results",
        "execute_sql_optimization_candidates",
        "call_api_optimization_candidates",
        "core_tool_compiled_policy_candidate",
        "core_tool_policy_promotion_decision",
    ]:
        assert (reports / f"{stem}.json").exists(), stem
        assert (reports / f"{stem}.md").exists(), stem

    assert audit["diagnostic_only"] is True
    assert audit["official_organizer_weighted_score_claim"] is False
    assert {"execute_sql", "call_api"} <= set(audit["tools"])
    assert audit["tools"]["execute_sql"]["read_only_guard"] is True
    assert audit["tools"]["call_api"]["get_only_data_guard"] is True

    search_space = optimizer["search_space"]
    assert {"execute_sql", "call_api", "joint_sql_api"} <= set(search_space["dimensions"])
    assert search_space["policy_count"] > 100
    assert "correctness_dominant" in optimizer["optimizer"]["composite_scenarios"]
    assert "no_regression_efficiency" in optimizer["optimizer"]["composite_scenarios"]

    sql_candidates = optimizer["execute_sql_candidates"]["candidates"]
    api_candidates = optimizer["call_api_candidates"]["candidates"]
    assert {row["rule_id"] for row in sql_candidates} >= {"SQL-1", "SQL-2", "SQL-3", "SQL-4", "SQL-5"}
    assert {row["rule_id"] for row in api_candidates} >= {"API-1", "API-2", "API-3", "API-4", "API-5", "API-6"}
    assert all(not row["uses_query_ids"] for row in sql_candidates + api_candidates)
    assert all(not row["uses_prompt_ids"] for row in sql_candidates + api_candidates)
    assert all(not row["uses_exact_prompt_strings"] for row in sql_candidates + api_candidates)
    assert all(not row["uses_gold_answers"] for row in sql_candidates + api_candidates)

    compiled = optimizer["compiled_candidate"]
    assert compiled["recommendation"] in {"promote_candidate", "shadow_only", "needs_manual_review", "reject", "wait_for_adobe_access"}
    assert compiled["sql_first_api_verify_remains_default"] is True
    assert compiled["endpoint_catalog_changed"] is False
    assert compiled["official_organizer_weighted_score_claim"] is False

    decision = optimizer["promotion_decision"]
    assert decision["strict_score_before"] == decision["strict_score_after_projected"]
    assert decision["final_submission_format_changed"] is False
    assert decision["direct_http_hits"] == 0
    assert decision["runtime_change_applied_by_script"] is False
    assert not (tiny_project.outputs_dir / "final_submission").exists()

    combined = "\n".join((reports / f"{stem}.json").read_text(encoding="utf-8") for stem in [
        "core_tool_optimization_audit",
        "core_tool_optimization_search_space",
        "core_tool_policy_optimizer",
        "core_tool_policy_search_results",
        "execute_sql_optimization_candidates",
        "call_api_optimization_candidates",
        "core_tool_compiled_policy_candidate",
        "core_tool_policy_promotion_decision",
    ])
    assert not SECRET_VALUE_RE.search(combined)


def test_core_tool_reports_linked_from_consolidated_index(tiny_project):
    _seed_inputs(tiny_project.outputs_dir)
    run_core_tool_optimization_audit(tiny_project)
    run_core_tool_policy_optimizer(tiny_project)

    generate_consolidated_reports(tiny_project)
    index = json.loads((tiny_project.outputs_dir / "reports" / "report_index.json").read_text(encoding="utf-8"))
    linked = "\n".join(index.get("canonical_reports", []) + index.get("additional_reports", []))
    assert "core_tool_optimization_audit.md" in linked
    assert "core_tool_policy_optimizer.md" in linked
    assert "core_tool_compiled_policy_candidate.md" in linked
