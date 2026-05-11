#!/usr/bin/env python
from __future__ import annotations

import json
import re
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config


REQUIRED_PATHS = [
    "dashagent",
    "eval/implementation_notes.md",
    "prompts/system_prompt_template.txt",
    "scripts/inspect_schema.py",
    "scripts/run_one_query.py",
    "scripts/run_dev_eval.py",
    "scripts/package_submission.py",
    "scripts/package_query_outputs.py",
    "scripts/run_llm_query.py",
    "scripts/run_llm_baseline_eval.py",
    "scripts/run_llm_strict_baseline_eval.py",
    "scripts/run_llm_hidden_style_diagnostic.py",
    "scripts/check_llm_sdk_backend.py",
    "scripts/check_openai_compatible_llm.py",
    "scripts/load_local_env.py",
    "scripts/check_llm_env.py",
    "scripts/audit_workshop_requirements.py",
    "scripts/generate_sdk_usage_audit.py",
    "scripts/generate_diagnostic_prompt_suite.py",
    "scripts/run_diagnostic_prompt_suite.py",
    "scripts/run_llm_semantic_router_shadow_eval.py",
    "scripts/run_llm_semantic_router_isolated_trial.py",
    "scripts/run_workflow_decision_audit.py",
    "scripts/run_decision_feedback_loop.py",
    "scripts/generate_failure_analysis.py",
    "scripts/generate_family_score_report.py",
    "scripts/generate_pareto_report.py",
    "scripts/generate_template_generalization_report.py",
    "scripts/generate_candidate_context_report.py",
    "scripts/generate_baseline_comparison_report.py",
    "scripts/generate_dataflow_visualization.py",
    "scripts/generate_all_dataflow_visualizations.py",
    "scripts/generate_strategy_comparison_visualization.py",
    "scripts/generate_research_inspired_report.py",
    "scripts/audit_redundant_files.py",
    "scripts/cleanup_redundant_files.py",
    "scripts/generate_official_token_accounting_report.py",
    "scripts/generate_official_token_reduction_promotion_report.py",
    "scripts/run_official_token_reduction_packaged_trial.py",
    "scripts/run_endpoint_schema_rule_candidate_eval.py",
    "scripts/run_endpoint_schema_rule_canary.py",
    "scripts/run_endpoint_schema_rule_packaged_trial.py",
    "scripts/run_ast_guided_sql_candidate_canary.py",
    "scripts/run_hidden_style_eval.py",
    "scripts/generate_endpoint_family_failure_report.py",
    "scripts/analyze_schema_dataset_positive_repair.py",
    "scripts/generate_sql_ast_candidate_ranking_report.py",
    "scripts/run_retrieval_ablation_report.py",
    "scripts/run_repair_selector_v2_shadow_eval.py",
    "scripts/run_repair_selector_v3_shadow_eval.py",
    "scripts/generate_low_score_failure_mining_report.py",
    "scripts/run_execution_candidate_search.py",
    "scripts/run_llm_candidate_search.py",
    "scripts/analyze_unsafe_answer_candidates.py",
    "scripts/run_answer_shape_v2_ab_eval.py",
    "scripts/run_supportable_answer_rewrite_eval.py",
    "scripts/run_llm_answer_rewrite_search.py",
    "scripts/run_endpoint_family_tiebreak_v2_shadow.py",
    "scripts/run_live_mode_readiness_check.py",
    "scripts/audit_live_adobe_api_readiness.py",
    "scripts/generate_api_required_readiness_matrix.py",
    "scripts/run_live_api_readiness_smoke.py",
    "scripts/run_live_api_evidence_pipeline_trial.py",
    "scripts/run_mock_live_api_evidence_pipeline_trial.py",
    "scripts/run_targeted_accuracy_packaged_trial.py",
    "scripts/generate_0_7_score_push_report.py",
    "scripts/run_autonomous_packaged_trial.py",
    "scripts/generate_autonomous_score_push_report.py",
    "scripts/generate_accuracy_promotion_decision_report.py",
    "scripts/generate_winner_readiness_report.py",
    "scripts/generate_consolidated_reports.py",
    "scripts/run_shadow_repair_eval.py",
    "scripts/run_compact_context_shadow_eval.py",
    "scripts/run_compact_context_measured_eval.py",
    "scripts/run_official_token_reduction_eval.py",
    "scripts/run_official_token_reduction_canary.py",
    "scripts/run_risk_efficiency_shadow_eval.py",
    "scripts/tune_thresholds.py",
    "scripts/run_robustness_eval.py",
    "scripts/export_trajectory_to_openai_trace.py",
    "scripts/check_submission_ready.py",
    "scripts/warm_cache.py",
    "tests",
    "pyproject.toml",
    "requirements.txt",
    "README.md",
    ".env.example",
]

SECRET_PATTERNS = [
    re.compile(r"client_secret\s*[:=]\s*['\"][^'\"]+", re.IGNORECASE),
    re.compile(r"access_token\s*[:=]\s*['\"][^'\"]+", re.IGNORECASE),
    re.compile(r"authorization\s*:\s*bearer\s+[a-z0-9._-]+", re.IGNORECASE),
]


def main() -> int:
    config = Config.from_env(ROOT)
    missing = [path for path in REQUIRED_PATHS if not (config.project_root / path).exists()]
    secret_hits = scan_for_secrets(config.project_root)
    package_dir = config.outputs_dir / "source_code"
    zip_path = config.outputs_dir / "source_code.zip"

    if missing or secret_hits:
        print(
            json.dumps(
                {"ok": False, "missing": missing, "secret_hits": secret_hits},
                indent=2,
                sort_keys=True,
            )
        )
        return 1

    if package_dir.exists():
        shutil.rmtree(package_dir)
    package_dir.mkdir(parents=True)
    for path in REQUIRED_PATHS:
        src = config.project_root / path
        dst = package_dir / path
        if src.is_dir():
            shutil.copytree(src, dst, ignore=ignore_package_paths)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in package_dir.rglob("*"):
            if file_path.is_file():
                archive.write(file_path, file_path.relative_to(package_dir))

    print(
        json.dumps(
            {"ok": True, "package_dir": str(package_dir), "zip_path": str(zip_path)},
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def ignore_package_paths(directory: str, names: list[str]) -> set[str]:
    ignored = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".ipynb_checkpoints", ".DS_Store"}
    return {name for name in names if name in ignored or name.endswith(".pyc") or name == "answer_synthesizer 2.py"}


def scan_for_secrets(root: Path) -> list[str]:
    hits: list[str] = []
    for path in list(root.glob("*.txt")) + list(root.glob("*.md")) + list(root.glob("*.py")) + list((root / "dashagent").rglob("*.py")):
        if path.is_relative_to(root / "outputs") or path.is_relative_to(root / "data"):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                hits.append(str(path.relative_to(root)))
                break
    return sorted(set(hits))


if __name__ == "__main__":
    raise SystemExit(main())
