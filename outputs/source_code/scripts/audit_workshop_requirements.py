#!/usr/bin/env python
from __future__ import annotations

import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.api_client import AdobeAPIClient
from dashagent.config import Config
from dashagent.db import DuckDBDatabase, is_read_only_sql
from dashagent.trajectory import redact_secrets
from dashagent.validators import APIValidator, SQLValidator
from scripts.check_submission_ready import check_submission_ready
from scripts.generate_sdk_usage_audit import generate_sdk_usage_audit
from scripts.package_query_outputs import NON_SUBMISSION_OUTPUT_DIRS, REQUIRED_QUERY_FILES


OFFICIAL_REQUIREMENTS_URL = "https://dashsys-workshop-vldb.github.io/systems.html"
CRITICAL_FAILURE_IDS = {
    "required_tools.execute_sql",
    "required_tools.call_api",
    "final_submission.required_artifacts",
    "final_submission.per_query_outputs",
    "final_submission.trajectory_json",
    "final_submission.secret_scan",
    "final_submission.diagnostic_contamination",
    "final_submission.source_zip_safety",
    "submission.default_strategy",
    "llm_sdk.direct_runtime_http",
}
SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"Authorization\s*:\s*Bearer\s+[A-Za-z0-9._-]{12,}", re.I),
    re.compile(r"OPENAI_API_KEY\s*=\s*sk", re.I),
    re.compile(r"ANTHROPIC_API_KEY\s*=\s*sk", re.I),
]
ZIP_FORBIDDEN_PARTS = {
    ".env.local",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}
FINAL_SUBMISSION_FORBIDDEN_PATTERNS = [
    "generated_prompt_suite",
    "diagnostic_prompt_suite",
    "llm_strict_eval",
    "llm_candidate_search",
    "llm_answer_rewrite_search",
    "qwen_",
]


def main() -> int:
    config = Config.from_env(ROOT)
    report = audit_workshop_requirements(config)
    print(
        json.dumps(
            {
                "overall_status": report["overall_status"],
                "critical_failure_count": len(report["critical_failures"]),
                "warning_count": len(report["warnings"]),
                "json": str(config.outputs_dir / "reports" / "workshop_requirement_audit.json"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report["overall_status"] != "fail" else 1


def audit_workshop_requirements(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    items: list[dict[str, Any]] = []
    mapping: dict[str, dict[str, Any]] = {}

    def add_item(
        item_id: str,
        requirement: str,
        status: str,
        evidence_path: str | list[str],
        explanation: str,
        recommended_fix: str = "No action needed.",
    ) -> None:
        item = {
            "id": item_id,
            "requirement": requirement,
            "status": status,
            "evidence_path": evidence_path,
            "explanation": explanation,
            "recommended_fix": recommended_fix,
            "critical": item_id in CRITICAL_FAILURE_IDS,
        }
        items.append(item)

    _audit_required_tools(config, add_item, mapping)
    _audit_final_submission(config, add_item, mapping)
    _audit_evaluation_alignment(config, add_item, mapping)
    _audit_model_generality(config, add_item, mapping)
    _audit_diagnostic_suite(config, add_item, mapping)
    _audit_documentation(config, add_item, mapping)

    critical_failures = [
        _failure_record(item)
        for item in items
        if item["status"] == "fail" and item.get("critical")
    ]
    warnings = [_failure_record(item) for item in items if item["status"] == "warning"]
    if critical_failures:
        overall = "fail"
    elif warnings:
        overall = "warning"
    else:
        overall = "pass"

    report = {
        "report_type": "workshop_requirement_audit",
        "official_source": OFFICIAL_REQUIREMENTS_URL,
        "overall_status": overall,
        "critical_failures": critical_failures,
        "warnings": warnings,
        "official_requirement_mapping": mapping,
        "items": items,
        "assumptions": [
            "`original_query` satisfies the official user-query trace requirement when `query` is absent.",
            "Diagnostic prompt labels are coverage hints only and are not official gold labels.",
            "The SDK-only rule applies to LLM/model provider calls; Adobe REST API execution stays on the existing API client path.",
        ],
    }
    safe = redact_secrets(report)
    if not isinstance(safe, dict):
        safe = report
    (reports_dir / "workshop_requirement_audit.json").write_text(
        json.dumps(safe, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    (reports_dir / "workshop_requirement_audit.md").write_text(_render_markdown(safe), encoding="utf-8")
    return safe


def _audit_required_tools(config: Config, add_item: Any, mapping: dict[str, dict[str, Any]]) -> None:
    sql_exists = hasattr(DuckDBDatabase, "execute_sql") and callable(getattr(DuckDBDatabase, "execute_sql"))
    select_ok, _ = is_read_only_sql('SELECT COUNT(*) FROM "dim_campaign"')
    drop_ok, drop_error = is_read_only_sql('DROP TABLE "dim_campaign"')
    sql_validator_exists = callable(getattr(SQLValidator, "validate", None))
    sql_status = "pass" if sql_exists and sql_validator_exists and select_ok and not drop_ok else "fail"
    add_item(
        "required_tools.execute_sql",
        "Implement execute_sql(sql) and keep SQL read-only.",
        sql_status,
        [_rel_or_abs(config, Path(DuckDBDatabase.execute_sql.__code__.co_filename)), "dashagent/validators.py"],
        (
            "execute_sql exists and read-only checks block destructive SQL."
            if sql_status == "pass"
            else f"execute_sql/read-only enforcement missing or incomplete: {drop_error or 'unknown'}"
        ),
        "Restore DuckDBDatabase.execute_sql, SQLValidator, and destructive SQL blocking.",
    )
    mapping["execute_sql(sql)"] = {
        "official_requirement": "Tool execute_sql(sql) must execute database SQL.",
        "repo_artifacts": [_rel_or_abs(config, Path(DuckDBDatabase.execute_sql.__code__.co_filename)), "dashagent/validators.py", "tests/test_db.py"],
        "status": sql_status,
    }

    api_exists = hasattr(AdobeAPIClient, "call_api") and callable(getattr(AdobeAPIClient, "call_api"))
    api_validator_exists = callable(getattr(APIValidator, "validate", None))
    api_status = "pass" if api_exists and api_validator_exists else "fail"
    add_item(
        "required_tools.call_api",
        "Implement call_api(method, url, params, headers) with endpoint/API validation.",
        api_status,
        [_rel_or_abs(config, Path(AdobeAPIClient.call_api.__code__.co_filename)), "dashagent/validators.py", "dashagent/endpoint_catalog.py"],
        "call_api exists and APIValidator/endpoint catalog are present." if api_status == "pass" else "call_api or APIValidator is missing.",
        "Restore AdobeAPIClient.call_api and route all planned API calls through APIValidator.",
    )
    mapping["call_api(method, url, params, headers)"] = {
        "official_requirement": "Tool call_api(method, url, params, headers) must make sandbox REST API calls.",
        "repo_artifacts": [_rel_or_abs(config, Path(AdobeAPIClient.call_api.__code__.co_filename)), "dashagent/validators.py", "dashagent/endpoint_catalog.py"],
        "status": api_status,
    }


def _audit_final_submission(config: Config, add_item: Any, mapping: dict[str, dict[str, Any]]) -> None:
    outputs = config.outputs_dir
    final_dir = outputs / "final_submission"
    manifest_path = outputs / "final_submission_manifest.json"
    required_top = [
        final_dir,
        final_dir / "system_prompt_template.txt",
        final_dir / "source_code.zip",
        manifest_path,
    ]
    missing_top = [_rel_or_abs(config, path) for path in required_top if not path.exists()]
    add_item(
        "final_submission.required_artifacts",
        "Submit system_prompt_template.txt, source_code.zip, final_submission_manifest.json, and final_submission query outputs.",
        "fail" if missing_top else "pass",
        [_rel_or_abs(config, path) for path in required_top],
        "All top-level final submission deliverables exist." if not missing_top else f"Missing: {', '.join(missing_top)}",
        "Run package_submission.py and package_query_outputs.py to regenerate required final-submission artifacts.",
    )
    mapping["additional_deliverables"] = {
        "official_requirement": "Submit a system prompt template and source-code archive.",
        "repo_artifacts": ["outputs/final_submission/system_prompt_template.txt", "outputs/final_submission/source_code.zip", "outputs/final_submission_manifest.json"],
        "status": "fail" if missing_top else "pass",
    }

    manifest = _load_json(manifest_path)
    strategy_ok = manifest.get("preferred_strategy") == "SQL_FIRST_API_VERIFY"
    add_item(
        "submission.default_strategy",
        "Keep packaged default strategy unchanged as SQL_FIRST_API_VERIFY.",
        "pass" if strategy_ok else "fail",
        _rel_or_abs(config, manifest_path),
        f"preferred_strategy={manifest.get('preferred_strategy', 'unavailable')}",
        "Regenerate package outputs with SQL_FIRST_API_VERIFY as the preferred strategy.",
    )

    query_dirs = sorted(path for path in final_dir.glob("query_*") if path.is_dir()) if final_dir.exists() else []
    missing_files: list[dict[str, Any]] = []
    invalid_trajectories: list[dict[str, Any]] = []
    missing_fields: list[dict[str, Any]] = []
    missing_action_records: list[dict[str, Any]] = []
    for query_dir in query_dirs:
        for filename in REQUIRED_QUERY_FILES:
            if not (query_dir / filename).exists():
                missing_files.append({"query_dir": _rel_or_abs(config, query_dir), "missing": filename})
        trajectory_path = query_dir / "trajectory.json"
        if not trajectory_path.exists():
            invalid_trajectories.append({"query_dir": _rel_or_abs(config, query_dir), "error": "trajectory.json missing"})
            continue
        trajectory = _load_json(trajectory_path)
        if not trajectory:
            invalid_trajectories.append({"query_dir": _rel_or_abs(config, query_dir), "error": "trajectory.json invalid or empty"})
            continue
        required_fields = ["final_answer", "tool_call_count", "estimated_tokens", "runtime"]
        missing = [field for field in required_fields if field not in trajectory]
        if not (trajectory.get("original_query") or trajectory.get("query")):
            missing.append("original_query_or_query")
        if missing:
            missing_fields.append({"query_dir": _rel_or_abs(config, query_dir), "missing": missing})
        steps = trajectory.get("steps") or []
        if int(trajectory.get("sql_call_count") or 0) > 0 and not any(step.get("kind") == "sql_call" for step in steps):
            missing_action_records.append({"query_dir": _rel_or_abs(config, query_dir), "missing": "sql_call step"})
        if int(trajectory.get("api_call_count") or 0) > 0 and not any(step.get("kind") == "api_call" for step in steps):
            missing_action_records.append({"query_dir": _rel_or_abs(config, query_dir), "missing": "api_call step"})

    per_query_ok = bool(query_dirs) and not missing_files
    add_item(
        "final_submission.per_query_outputs",
        "Each packaged query directory contains metadata.json, filled_system_prompt.txt, and trajectory.json.",
        "pass" if per_query_ok else "fail",
        _rel_or_abs(config, final_dir),
        f"Checked {len(query_dirs)} query directories; missing file records={len(missing_files)}.",
        "Regenerate query outputs with package_query_outputs.py and inspect missing query directories.",
    )
    trajectory_ok = bool(query_dirs) and not invalid_trajectories and not missing_fields and not missing_action_records
    add_item(
        "final_submission.trajectory_json",
        "Trajectory JSON is parseable, reproducible, and records query, answer, tool count, tokens, runtime, and SQL/API actions.",
        "pass" if trajectory_ok else "fail",
        _rel_or_abs(config, final_dir),
        (
            f"Checked {len(query_dirs)} trajectories; invalid={len(invalid_trajectories)}, "
            f"missing_fields={len(missing_fields)}, missing_action_records={len(missing_action_records)}."
        ),
        "Regenerate affected trajectories and preserve original_query, final_answer, tool_call_count, estimated_tokens, runtime, and tool-call steps.",
    )
    mapping["per_query_deliverables"] = {
        "official_requirement": "For each query submit metadata.json, filled_system_prompt.txt, and trajectory.json.",
        "repo_artifacts": ["outputs/final_submission/query_###/metadata.json", "outputs/final_submission/query_###/filled_system_prompt.txt", "outputs/final_submission/query_###/trajectory.json"],
        "status": "pass" if per_query_ok and trajectory_ok else "fail",
        "query_directory_count": len(query_dirs),
    }

    readiness = check_submission_ready(config)
    secret_ok = bool(readiness.get("secret_scan", {}).get("ok", False))
    add_item(
        "final_submission.secret_scan",
        "Final submission and trajectory artifacts must not leak secrets.",
        "pass" if secret_ok else "fail",
        _rel_or_abs(config, final_dir),
        "check_submission_ready secret scan passed." if secret_ok else f"Secret hits: {readiness.get('secret_scan', {}).get('hits')}",
        "Remove or redact secrets and regenerate affected artifacts.",
    )

    zip_report = _inspect_source_zip(config, final_dir / "source_code.zip")
    add_item(
        "final_submission.source_zip_safety",
        "source_code.zip must include source code without .env.local, caches, outputs, generated diagnostic data, or secrets.",
        "pass" if zip_report["ok"] else "fail",
        _rel_or_abs(config, final_dir / "source_code.zip"),
        zip_report["summary"],
        "Rebuild source_code.zip with package_submission.py after excluding unsafe files.",
    )

    contamination = _find_final_submission_contamination(config, final_dir)
    add_item(
        "final_submission.diagnostic_contamination",
        "Diagnostic prompts, diagnostic outputs, LLM raw artifacts, caches, and stale duplicate files must not be packaged into final_submission.",
        "pass" if not contamination else "fail",
        _rel_or_abs(config, final_dir),
        "No diagnostic or stale output contamination found." if not contamination else f"Contamination paths: {contamination[:20]}",
        "Remove contaminated artifacts from final_submission and update packaging exclusions.",
    )


def _audit_evaluation_alignment(config: Config, add_item: Any, mapping: dict[str, dict[str, Any]]) -> None:
    outputs = config.outputs_dir
    strict = _load_json(outputs / "eval_results_strict.json")
    sql_first = strict.get("summary", {}).get("by_strategy", {}).get("SQL_FIRST_API_VERIFY", {})
    component_keys = {"avg_sql_score", "avg_api_score", "avg_answer_score", "avg_tool_call_count", "avg_estimated_tokens", "avg_runtime"}
    strict_ok = bool(sql_first) and component_keys.issubset(sql_first)
    hidden_ok = (outputs / "hidden_style_eval.json").exists()
    readiness_ok = check_submission_ready(config).get("ok", False)
    add_item(
        "evaluation.strict_component_metrics",
        "Reports cover SQL correctness, API correctness, response correctness, tool calls, tokens, wall time, hidden-style robustness, and readiness.",
        "pass" if strict_ok and hidden_ok and readiness_ok else "warning",
        ["outputs/eval_results_strict.json", "outputs/hidden_style_eval.json", "outputs/winner_readiness_report.json", "outputs/final_submission_manifest.json"],
        (
            "Strict/component metrics, hidden-style report, and readiness checks are available."
            if strict_ok and hidden_ok and readiness_ok
            else f"strict_ok={strict_ok}, hidden_ok={hidden_ok}, readiness_ok={readiness_ok}"
        ),
        "Regenerate strict eval, hidden-style eval, winner readiness, and readiness reports.",
    )
    mapping["evaluation_dimensions"] = {
        "official_requirement": "Evaluation covers SQL/API/response correctness plus turns/tool calls/tokens/wall time and trajectory reproducibility.",
        "repo_artifacts": ["outputs/eval_results_strict.json", "outputs/hidden_style_eval.json", "scripts/check_submission_ready.py"],
        "status": "pass" if strict_ok and hidden_ok and readiness_ok else "warning",
    }


def _audit_model_generality(config: Config, add_item: Any, mapping: dict[str, dict[str, Any]]) -> None:
    prompt_paths = [config.prompts_dir / "system_prompt_template.txt", config.outputs_dir / "final_submission" / "system_prompt_template.txt"]
    prompt_text = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in prompt_paths if path.exists()).lower()
    bad_terms = ["qwen", "openrouter-only", "gpt-4", "claude-only", "public example", "gold answer"]
    vendor_issue_terms = [term for term in bad_terms if term in prompt_text]
    prompt_ok = bool(prompt_text) and not vendor_issue_terms and "execute_sql" in prompt_text and "call_api" in prompt_text
    add_item(
        "model_generality.system_prompt",
        "System prompt should generalize across Claude/OpenAI-style harnesses and avoid public/gold/model-specific runtime assumptions.",
        "pass" if prompt_ok else "warning",
        [_rel_or_abs(config, path) for path in prompt_paths],
        "Prompt is tool-grounded and model-generic." if prompt_ok else f"Prompt may need review; terms={vendor_issue_terms or 'missing tool wording'}",
        "Remove model-specific/public-example wording and ensure prompt requires grounded SQL/API evidence.",
    )
    sdk = generate_sdk_usage_audit(config)
    direct_hits = sdk.get("summary", {}).get("runtime_llm_direct_http_hits")
    add_item(
        "llm_sdk.direct_runtime_http",
        "All LLM/model provider calls must use get_llm_client() or LLMClient SDK paths; direct runtime HTTP hits must be zero.",
        "pass" if direct_hits == 0 else "fail",
        "outputs/reports/sdk_usage_audit.json",
        f"runtime_llm_direct_http_hits={direct_hits}",
        "Refactor direct LLM HTTP runtime calls to dashagent.llm_client.get_llm_client().",
    )
    mapping["harness_model_generality"] = {
        "official_requirement": "Organizer may run the system prompt with Claude Agent SDK or OpenAI Agents SDK and any model.",
        "repo_artifacts": ["prompts/system_prompt_template.txt", "dashagent/llm_client.py", "outputs/reports/sdk_usage_audit.json"],
        "status": "pass" if prompt_ok and direct_hits == 0 else ("fail" if direct_hits else "warning"),
    }


def _audit_diagnostic_suite(config: Config, add_item: Any, mapping: dict[str, dict[str, Any]]) -> None:
    suite_path = config.data_dir / "generated_prompt_suite.json"
    suite = _load_json_list(suite_path)
    diag_ok = bool(suite) and all(item.get("diagnostic_only") is True and item.get("should_be_scored") is False for item in suite)
    strict_source = "data/generated_prompt_suite" not in Path("scripts/run_dev_eval.py").read_text(encoding="utf-8", errors="ignore")
    excluded = "diagnostic_prompt_suite" in NON_SUBMISSION_OUTPUT_DIRS
    add_item(
        "diagnostic_suite.separation",
        "Generated prompt suite is diagnostic-only, not official scoring data, and excluded from final submission.",
        "pass" if diag_ok and strict_source and excluded else "warning",
        ["data/generated_prompt_suite.json", "scripts/run_dev_eval.py", "scripts/package_query_outputs.py"],
        f"prompts={len(suite)}, diagnostic_flags_ok={diag_ok}, official_eval_separate={strict_source}, packaging_excluded={excluded}",
        "Regenerate the diagnostic suite, preserve diagnostic_only/should_be_scored flags, and keep package exclusions.",
    )
    mapping["diagnostic_prompt_suite_separation"] = {
        "official_requirement": "Public examples are illustration/validation only; broader diagnostic prompts must not become official scoring data.",
        "repo_artifacts": ["data/generated_prompt_suite.json", "outputs/reports/generated_prompt_suite_summary.json", "scripts/package_query_outputs.py"],
        "status": "pass" if diag_ok and strict_source and excluded else "warning",
    }


def _audit_documentation(config: Config, add_item: Any, mapping: dict[str, dict[str, Any]]) -> None:
    readme = config.project_root / "README.md"
    agents = config.project_root / "AGENTS.md"
    doc_text = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in [readme, agents] if path.exists()).lower()
    required_terms = [
        "execute_sql",
        "call_api",
        "metadata.json",
        "filled_system_prompt",
        "trajectory.json",
        "sql_first_api_verify",
        "diagnostic-only",
        "should_be_scored=false",
        "get_llm_client",
        "validation",
    ]
    missing = [term for term in required_terms if term not in doc_text]
    add_item(
        "documentation.alignment",
        "README.md and AGENTS.md explain official tools, deliverables, default strategy, validation, diagnostic separation, SDK LLM rule, and no hardcoding/gold-label rules.",
        "pass" if not missing else "warning",
        [_rel_or_abs(config, readme), _rel_or_abs(config, agents)],
        "Documentation contains required alignment guidance." if not missing else f"Missing terms: {missing}",
        "Update README.md and AGENTS.md with workshop-alignment and post-change validation guidance.",
    )
    mapping["documentation_alignment"] = {
        "official_requirement": "Submission should be easy to verify and describe architecture, prompting strategy, evaluation, and safe operation.",
        "repo_artifacts": ["README.md", "AGENTS.md", "outputs/reports/report_index.md"],
        "status": "pass" if not missing else "warning",
    }

    report_index = config.outputs_dir / "reports" / "report_index.md"
    index_json = config.outputs_dir / "reports" / "report_index.json"
    md_has_link = report_index.exists() and "workshop_requirement_audit.md" in report_index.read_text(encoding="utf-8", errors="ignore")
    json_has_link = index_json.exists() and "workshop_requirement_audit.md" in json.dumps(_load_json(index_json))
    add_item(
        "reports.workshop_audit_indexed",
        "report_index.md/json links workshop_requirement_audit.md under Workshop Requirement Alignment.",
        "pass" if md_has_link and json_has_link else "warning",
        [_rel_or_abs(config, report_index), _rel_or_abs(config, index_json)],
        f"markdown_link={md_has_link}, json_link={json_has_link}",
        "Regenerate consolidated reports after adding the Workshop Requirement Alignment section.",
    )


def _inspect_source_zip(config: Config, path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"ok": False, "summary": "source_code.zip is missing."}
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            forbidden_names = [
                name
                for name in names
                if any(part in name for part in ZIP_FORBIDDEN_PARTS)
                or name.startswith("outputs/")
                or name in {"data/generated_prompt_suite.json", "data/generated_prompt_suite.md"}
            ]
            secret_hits = []
            for name in names:
                if not _zip_member_is_text(name):
                    continue
                try:
                    data = archive.read(name)
                except Exception:
                    continue
                if len(data) > 750_000:
                    continue
                text = data.decode("utf-8", errors="ignore")
                if any(pattern.search(text) for pattern in SECRET_PATTERNS):
                    secret_hits.append(name)
            ok = not forbidden_names and not secret_hits
            return {
                "ok": ok,
                "summary": (
                    f"zip_entries={len(names)}, forbidden_entries={len(forbidden_names)}, secret_hits={len(secret_hits)}"
                ),
            }
    except zipfile.BadZipFile:
        return {"ok": False, "summary": "source_code.zip is not a valid zip file."}


def _find_final_submission_contamination(config: Config, final_dir: Path) -> list[str]:
    if not final_dir.exists():
        return []
    contaminated = []
    for path in final_dir.rglob("*"):
        rel = path.relative_to(final_dir).as_posix()
        lower = rel.lower()
        if " 2." in rel or " 3." in rel or " 4." in rel:
            contaminated.append(_rel_or_abs(config, path))
            continue
        if any(pattern in lower for pattern in FINAL_SUBMISSION_FORBIDDEN_PATTERNS):
            contaminated.append(_rel_or_abs(config, path))
            continue
        if any(part in path.parts for part in [".pytest_cache", "__pycache__", ".mypy_cache", ".ruff_cache"]):
            contaminated.append(_rel_or_abs(config, path))
    return contaminated


def _zip_member_is_text(name: str) -> bool:
    suffix = Path(name).suffix.lower()
    return suffix in {"", ".py", ".txt", ".md", ".json", ".toml", ".yaml", ".yml", ".example"}


def _load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _load_json_list(path: Path) -> list[dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _failure_record(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item["id"],
        "requirement": item["requirement"],
        "evidence_path": item["evidence_path"],
        "explanation": item["explanation"],
        "recommended_fix": item["recommended_fix"],
    }


def _rel_or_abs(config: Config, path: Path) -> str:
    try:
        return path.resolve().relative_to(config.project_root.resolve()).as_posix()
    except Exception:
        return path.as_posix()


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Workshop Requirement Audit",
        "",
        f"- Official source: {report.get('official_source')}",
        f"- Overall status: `{report.get('overall_status')}`",
        f"- Critical failures: `{len(report.get('critical_failures', []))}`",
        f"- Warnings: `{len(report.get('warnings', []))}`",
        "",
        "## Critical Failures",
        "",
    ]
    critical = report.get("critical_failures") or []
    if critical:
        for item in critical:
            lines.append(f"- `{item['id']}`: {item['explanation']} Fix: {item['recommended_fix']}")
    else:
        lines.append("- None.")
    lines.extend(["", "## Warnings", ""])
    warnings = report.get("warnings") or []
    if warnings:
        for item in warnings:
            lines.append(f"- `{item['id']}`: {item['explanation']} Fix: {item['recommended_fix']}")
    else:
        lines.append("- None.")
    lines.extend(["", "## Official Requirement Mapping", ""])
    for name, mapping in (report.get("official_requirement_mapping") or {}).items():
        status = mapping.get("status")
        artifacts = ", ".join(f"`{path}`" for path in mapping.get("repo_artifacts", []))
        lines.append(f"- **{name}** `{status}` - {mapping.get('official_requirement')} Evidence: {artifacts}")
    lines.extend(["", "## Audit Items", ""])
    lines.append("| Requirement | Status | Evidence | Explanation |")
    lines.append("|---|---:|---|---|")
    for item in report.get("items", []):
        evidence = item.get("evidence_path")
        if isinstance(evidence, list):
            evidence_text = "<br/>".join(f"`{value}`" for value in evidence)
        else:
            evidence_text = f"`{evidence}`"
        lines.append(
            f"| {item.get('requirement')} | `{item.get('status')}` | {evidence_text} | {item.get('explanation')} |"
        )
    lines.extend(["", "## Assumptions", ""])
    for assumption in report.get("assumptions", []):
        lines.append(f"- {assumption}")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
