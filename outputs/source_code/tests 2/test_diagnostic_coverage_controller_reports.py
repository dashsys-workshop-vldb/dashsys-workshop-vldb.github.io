from __future__ import annotations

import json
from pathlib import Path


ALLOWED_LOSS_CATEGORIES = {
    "router_loss",
    "backend_evidence_loss",
    "llm_rewrite_loss",
    "verifier_loss",
    "answer_scorer_mismatch",
    "dry_run_caveat_loss",
    "no_clear_loss",
    "controller_helped",
}

ABLATION_VARIANTS = {
    "backend_answer_only",
    "llm_rewrite_current",
    "verifier_forced_backend_safe",
    "minimal_llm_style_edit",
    "no_rewrite_when_backend_answer_complete",
}


def _load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def test_full_generated_prompt_diagnostic_report_is_diagnostic_only():
    assert Path("scripts/run_full_generated_prompt_suite_diagnostic.py").exists()
    report_path = Path("outputs/reports/full_generated_prompt_suite_diagnostic.json")
    md_path = Path("outputs/reports/full_generated_prompt_suite_diagnostic.md")
    assert report_path.exists()
    assert md_path.exists()
    report = _load(str(report_path))
    assert report["report_type"] == "full_generated_prompt_suite_diagnostic"
    assert report["total_prompts"] == 250
    assert report["executed_prompts"] == 250
    assert report["diagnostic_only"] is True
    assert report["official_strict_score_computed"] is False
    assert report["generated_prompt_score_claim"] is False
    assert report["rows"]
    assert all(row.get("diagnostic_only") is True for row in report["rows"][:10])
    assert "official strict-score evidence" in md_path.read_text(encoding="utf-8")


def test_generated_prompt_coverage_gap_report_has_required_sections():
    report = _load("outputs/reports/generated_prompt_coverage_gap_analysis.json")
    for key in [
        "domain_gaps",
        "route_gaps",
        "answer_intent_gaps",
        "dry_run_gaps",
        "live_api_gaps",
        "unknown_gaps",
        "schema_synonym_gaps",
        "sql_template_gaps",
        "answer_template_gaps",
    ]:
        assert key in report
    assert report["diagnostic_only"] is True
    assert report["generated_prompt_score_claim"] is False


def test_controller_failure_decomposition_sections_and_categories():
    assert Path("scripts/run_llm_controller_failure_decomposition.py").exists()
    report = _load("outputs/reports/llm_controller_failure_decomposition.json")
    assert report["report_type"] == "llm_controller_failure_decomposition"
    assert report["automatic_promotion"] is False
    assert report["summary"]["total_controller_rows"] == 35
    for row in report["rows"]:
        assert row["loss_category"] in ALLOWED_LOSS_CATEGORIES
        assert {"router_decision", "backend_tool_result", "llm_rewrite_result", "verifier_behavior", "score_breakdown"}.issubset(row)
        assert "delta_vs_sql_first_api_verify" in row["score_breakdown"]
        assert "proposed_llm_final_answer" in row["llm_rewrite_result"]


def test_controller_rewrite_ablation_preserves_backend_behavior():
    assert Path("scripts/run_controller_rewrite_ablation.py").exists()
    report = _load("outputs/reports/controller_rewrite_ablation.json")
    assert report["report_type"] == "controller_rewrite_ablation"
    assert set(report["variants"]) == ABLATION_VARIANTS
    assert report["automatic_promotion"] is False
    assert report["new_llm_calls"] is False
    assert report["summary"]["recommendation"] in {
        "keep_shadow_only",
        "controller_no_rewrite_better",
        "verifier_adjustment_candidate",
        "minimal_style_edit_candidate",
        "not_viable_after_ablation",
    }
    for variant in report["variants"].values():
        assert variant["backend_sql_api_behavior_preserved"] is True
        assert variant["backend_evidence_preserved"] is True
        assert variant["sql_score_delta"] == 0
        assert variant["api_score_delta"] == 0


def test_consolidated_report_index_links_controller_and_generated_diagnostics():
    index = _load("outputs/reports/report_index.json")
    diagnostic_paths = {item["path"] for item in index.get("diagnostic_prompt_coverage", [])}
    assert "outputs/reports/full_generated_prompt_suite_diagnostic.md" in diagnostic_paths
    assert "outputs/reports/generated_prompt_coverage_gap_analysis.md" in diagnostic_paths
    controller = index.get("llm_controller_diagnostics", {})
    assert controller.get("failure_decomposition_path") == "outputs/reports/llm_controller_failure_decomposition.md"
    assert controller.get("rewrite_ablation_path") == "outputs/reports/controller_rewrite_ablation.md"
    assert controller.get("automatic_promotion") is False
