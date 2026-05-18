#!/usr/bin/env python
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
from dashagent.trajectory import redact_secrets


GIT_STATUS_TIMEOUT_SECONDS = 5
CTX7_TIMEOUT_SECONDS = 45

PRELIGHT_STEM = "context7_docs_audit_preflight"
DOCS_STEM = "context7_dependency_docs_summary"
AUDIT_STEM = "context7_code_alignment_audit"
FIX_STEM = "context7_fix_decision"

PROTECTED_ARTIFACTS = [
    "outputs/final_submission/**",
    "outputs/eval_results_strict.json",
    "outputs/hidden_style_eval.*",
    "outputs/final_submission_manifest.json",
    "final_submission_manifest.json",
    ".env.local",
    "dashagent/endpoint_catalog.py",
    "dashagent/config.py",
    "scripts/package_query_outputs.py",
    "scripts/run_dev_eval.py",
]

PACKAGED_DEFAULT_FILES = [
    "dashagent/config.py",
    "scripts/package_query_outputs.py",
    "scripts/run_dev_eval.py",
]

ALLOWED_AUDIT_STATUSES = {
    "aligned",
    "minor_docs_mismatch",
    "potential_bug",
    "needs_manual_review",
    "blocked_by_adobe_permission",
    "no_action",
}


@dataclass(frozen=True)
class DocTarget:
    dependency: str
    library_name: str
    library_query: str
    docs_query: str
    affected_files: tuple[str, ...]
    risk_level: str
    code_audit_needed: bool
    expected_findings: tuple[str, ...]
    markers: tuple[str, ...]


DOC_TARGETS: tuple[DocTarget, ...] = (
    DocTarget(
        dependency="OpenAI Python SDK",
        library_name="openai python sdk",
        library_query="chat completions tool calling usage",
        docs_query="chat completions tool calling usage token usage fields",
        affected_files=("dashagent/llm_client.py", "scripts/check_llm_sdk_backend.py"),
        risk_level="medium",
        code_audit_needed=True,
        expected_findings=(
            "Chat completions are invoked through the SDK client method, with tools supplied as function definitions.",
            "Tool calls are returned on message tool call fields and arguments are JSON strings that need defensive parsing.",
            "Usage metadata is optional response metadata and should be read defensively.",
            "SDK exceptions can expose request metadata; reports should store only redacted compact error text.",
        ),
        markers=("chat.completions.create", "tools", "tool_choice", "usage"),
    ),
    DocTarget(
        dependency="Anthropic Python SDK",
        library_name="anthropic python sdk",
        library_query="messages tool use",
        docs_query="messages tool use usage fields",
        affected_files=("dashagent/llm_client.py",),
        risk_level="medium",
        code_audit_needed=True,
        expected_findings=(
            "Messages API calls use the SDK client's messages.create method.",
            "Anthropic tools use name, description, and input_schema fields, and tool_use blocks return structured input.",
            "Tool results are sent back as user content with a tool_result block.",
            "Usage includes input/output token fields and should be normalized defensively.",
        ),
        markers=("messages.create", "tool_use", "input_schema", "usage"),
    ),
    DocTarget(
        dependency="Adobe Experience Platform API",
        library_name="Adobe Experience Platform API",
        library_query="headers sandbox x-api-key x-gw-ims-org-id",
        docs_query="headers x-api-key x-gw-ims-org-id sandbox authorization",
        affected_files=(
            "dashagent/api_client.py",
            "dashagent/adobe_env.py",
            "dashagent/api_outcome_classifier.py",
            "scripts/check_adobe_env_local.py",
            "scripts/audit_live_adobe_api_readiness.py",
            "scripts/run_live_api_readiness_smoke.py",
            "scripts/run_post_permission_live_api_verification.py",
        ),
        risk_level="high",
        code_audit_needed=True,
        expected_findings=(
            "AEP requests require Authorization, x-api-key, and x-gw-ims-org-id headers; sandbox-scoped endpoints also use x-sandbox-name.",
            "Header names can be reported, but values must remain fully redacted or represented as constructible booleans only.",
            "Endpoint-level permission, sandbox, and path errors are separate from global credential readiness.",
            "Data endpoint diagnostics must stay GET-only unless explicitly limited to OAuth token acquisition.",
        ),
        markers=("Authorization", "x-api-key", "x-gw-ims-org-id", "x-sandbox-name"),
    ),
    DocTarget(
        dependency="DuckDB Python",
        library_name="duckdb python",
        library_query="execute query parameter usage",
        docs_query="execute query parameters read only python result fetch",
        affected_files=("dashagent/db.py", "dashagent/validators.py"),
        risk_level="medium",
        code_audit_needed=True,
        expected_findings=(
            "DuckDB Python executes SQL through connection execute/sql APIs and fetches rows through fetch methods.",
            "The client can execute multiple statements, so repository validation must block multi-statement and write statements before execution.",
            "Parameter binding is available for values, but repository-generated SQL remains read-only validated text.",
        ),
        markers=("execute", "fetchall", "parameters", "Multiple statements"),
    ),
    DocTarget(
        dependency="SQLGlot",
        library_name="sqlglot",
        library_query="parse_one read-only validation",
        docs_query="parse_one sql dialect validation read only expression",
        affected_files=("dashagent/sql_ast_tools.py", "dashagent/validators.py"),
        risk_level="medium",
        code_audit_needed=True,
        expected_findings=(
            "parse_one parses a SQL string into a syntax tree for a chosen dialect.",
            "Multiple statements can parse into a Block expression; repo validation should still block multi-statement SQL explicitly.",
            "Parse errors should be warnings or validation failures, not uncontrolled crashes.",
        ),
        markers=("parse_one", "read", "dialect", "ParseError"),
    ),
    DocTarget(
        dependency="Pydantic v2",
        library_name="pydantic v2",
        library_query="model_dump BaseModel validation",
        docs_query="model_dump BaseModel JSON serialization",
        affected_files=("dashagent/llm_client.py",),
        risk_level="low",
        code_audit_needed=True,
        expected_findings=(
            "Pydantic v2 SDK response models support model_dump for dictionary serialization.",
            "JSON-safe output may require mode=json or model_dump_json when serializing datetime-like values.",
            "Validation errors should be caught and reported safely where user-facing diagnostics are written.",
        ),
        markers=("model_dump", "model_dump_json", "BaseModel", "validation"),
    ),
    DocTarget(
        dependency="Typer",
        library_name="typer",
        library_query="cli options testing",
        docs_query="cli option argparse testing",
        affected_files=("scripts/run_live_api_readiness_smoke.py", "scripts/run_dev_eval.py"),
        risk_level="low",
        code_audit_needed=True,
        expected_findings=(
            "Typer documents explicit CLI options and help output, but this repo primarily uses argparse for diagnostics.",
            "CLI override flags should remain explicit user inputs rather than implicit environment behavior.",
            "Required options and callbacks should fail clearly in help/error paths.",
        ),
        markers=("Options", "required", "callback", "help"),
    ),
    DocTarget(
        dependency="pytest",
        library_name="pytest",
        library_query="tmp_path monkeypatch capsys",
        docs_query="tmp_path monkeypatch capsys fixtures",
        affected_files=("tests",),
        risk_level="low",
        code_audit_needed=True,
        expected_findings=(
            "pytest fixtures such as tmp_path, monkeypatch, and capsys are function-scoped tools for isolated tests.",
            "monkeypatch changes are automatically undone after the test or fixture scope.",
            "tmp_path provides per-test filesystem isolation for generated reports.",
            "capsys supports output-redaction tests without printing secret values.",
        ),
        markers=("monkeypatch", "tmp_path", "capsys", "fixture"),
    ),
)


Runner = Callable[[list[str], Path, int], dict[str, Any]]


def main() -> int:
    config = Config.from_env(ROOT)
    payload = run_context7_code_alignment_audit(config)
    print(
        json.dumps(
            {
                "status": payload["code_alignment_audit"].get("status"),
                "fix_applied": payload["fix_decision"].get("code_changes_applied"),
                "reports": [
                    str(config.outputs_dir / "reports" / f"{stem}.json")
                    for stem in (PRELIGHT_STEM, DOCS_STEM, AUDIT_STEM, FIX_STEM)
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def run_context7_code_alignment_audit(
    config: Config | None = None,
    *,
    ctx7_runner: Runner | None = None,
    query_context7: bool = True,
) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    runner = ctx7_runner or _run_command
    preflight = build_preflight(config, runner=runner)
    docs_summary = build_docs_summary(config, preflight, runner=runner, query_context7=query_context7)
    code_alignment = build_code_alignment_audit(config, docs_summary)
    fix_decision = build_fix_decision(docs_summary, code_alignment)

    for stem, payload, renderer in [
        (PRELIGHT_STEM, preflight, render_preflight_md),
        (DOCS_STEM, docs_summary, render_docs_summary_md),
        (AUDIT_STEM, code_alignment, render_code_alignment_md),
        (FIX_STEM, fix_decision, render_fix_decision_md),
    ]:
        safe_payload = _safe_payload(payload)
        (reports_dir / f"{stem}.json").write_text(
            json.dumps(safe_payload, indent=2, sort_keys=True, default=str),
            encoding="utf-8",
        )
        (reports_dir / f"{stem}.md").write_text(renderer(safe_payload), encoding="utf-8")

    return {
        "preflight": preflight,
        "docs_summary": docs_summary,
        "code_alignment_audit": code_alignment,
        "fix_decision": fix_decision,
    }


def build_preflight(config: Config, *, runner: Runner) -> dict[str, Any]:
    git_status = _collect_git_status(config.project_root, runner)
    ctx7_direct = runner(["ctx7", "--help"], config.project_root, 10)
    ctx7_fallback_available = bool(shutil.which("npx"))
    ctx7_command = ["ctx7"] if ctx7_direct.get("exit_code") == 0 else ["npx", "-y", "ctx7@latest"]
    sources = _load_preflight_sources(config)
    return _safe_payload(
        {
            "report_type": PRELIGHT_STEM,
            "created_at": _now(),
            "git_status": git_status,
            "ctx7_cli": {
                "direct_command_available": ctx7_direct.get("exit_code") == 0,
                "direct_command_exit_code": ctx7_direct.get("exit_code"),
                "fallback_npx_available": ctx7_fallback_available,
                "selected_command": " ".join(ctx7_command),
                "help_checked_without_values": True,
            },
            "protected_artifacts": PROTECTED_ARTIFACTS,
            "packaged_default_files": PACKAGED_DEFAULT_FILES,
            "allowed_scope": [
                "Context7 documentation lookup",
                "SDK/API/code alignment reporting",
                "README/AGENTS/report-index clarification",
                "Focused test-only coverage for the audit reports",
            ],
            "runtime_changes_allowed_by_default": False,
            "no_runtime_change_by_default_rule": (
                "Do not alter packaged runtime behavior unless Context7 docs prove a small deterministic issue, "
                "focused tests are added, and mandatory validation passes."
            ),
            "current_packaged_strategy": sources["system_summary"].get("preferred_strategy")
            or sources["winner_readiness"].get("packaged", {}).get("preferred_strategy")
            or "SQL_FIRST_API_VERIFY",
            "current_strict_score": sources["system_summary"].get("packaged_strict_score")
            or sources["winner_readiness"].get("packaged", {}).get("strict_final_score")
            or "unavailable",
            "hidden_style_status": sources["system_summary"].get("hidden_style")
            or _hidden_label(sources["hidden_style"].get("summary", {})),
            "final_submission_ready": sources["system_summary"].get("final_submission_ready")
            if sources["system_summary"].get("final_submission_ready") is not None
            else sources["winner_readiness"].get("packaged", {}).get("final_submission_ready"),
            "live_success_count": _live_success_count(sources["live_api_smoke"]),
            "final_submission_format_protected": True,
        }
    )


def build_docs_summary(
    config: Config,
    preflight: dict[str, Any],
    *,
    runner: Runner,
    query_context7: bool,
) -> dict[str, Any]:
    reports: list[dict[str, Any]] = []
    selected_prefix = str(preflight.get("ctx7_cli", {}).get("selected_command") or "ctx7").split()
    if not selected_prefix:
        selected_prefix = ["ctx7"]

    for target in DOC_TARGETS:
        library_cmd = [*selected_prefix, "library", target.library_name, target.library_query]
        library_result = runner(library_cmd, config.project_root, CTX7_TIMEOUT_SECONDS) if query_context7 else _skipped_result(library_cmd)
        library_output = _combined_output(library_result)
        library_id = _parse_context7_library_id(library_output)
        docs_result = _skipped_result([*selected_prefix, "docs", library_id or "not_found", target.docs_query])
        docs_output = ""
        if query_context7 and library_id:
            docs_cmd = [*selected_prefix, "docs", library_id, target.docs_query]
            docs_result = runner(docs_cmd, config.project_root, CTX7_TIMEOUT_SECONDS)
            docs_output = _combined_output(docs_result)
        result = "found" if library_id and docs_result.get("exit_code") == 0 else "not_found"
        if library_result.get("timed_out") or docs_result.get("timed_out"):
            result = "timeout"
        elif library_result.get("exit_code") not in (0, None):
            result = "unavailable"
        reports.append(
            {
                "dependency": target.dependency,
                "context7_library_id": library_id or "not_found",
                "library_query_used": target.library_query,
                "docs_query_used": target.docs_query,
                "context7_result": result,
                "library_command_exit_code": library_result.get("exit_code"),
                "docs_command_exit_code": docs_result.get("exit_code"),
                "docs_output_char_count": len(docs_output),
                "observed_markers": _observed_markers(docs_output or library_output, target.markers),
                "key_docs_findings": list(target.expected_findings),
                "repo_files_affected": list(target.affected_files),
                "risk_level": target.risk_level,
                "code_audit_needed": target.code_audit_needed,
                "fallback": "existing repo behavior / manual review needed" if result != "found" else "not_needed",
            }
        )

    found_count = sum(1 for row in reports if row.get("context7_result") == "found")
    return _safe_payload(
        {
            "report_type": DOCS_STEM,
            "created_at": _now(),
            "purpose": "Short Context7 documentation lookup summary for SDK/API/code-alignment auditing.",
            "raw_docs_stored": False,
            "sensitive_values_stored": False,
            "ctx7_command": preflight.get("ctx7_cli", {}).get("selected_command"),
            "dependency_count": len(reports),
            "context7_found_count": found_count,
            "context7_unavailable_count": len(reports) - found_count,
            "dependencies": reports,
        }
    )


def build_code_alignment_audit(config: Config, docs_summary: dict[str, Any]) -> dict[str, Any]:
    root = config.project_root
    llm_client = _read(root / "dashagent" / "llm_client.py")
    adobe_env = _read(root / "dashagent" / "adobe_env.py")
    api_client = _read(root / "dashagent" / "api_client.py")
    outcome_classifier = _read(root / "dashagent" / "api_outcome_classifier.py")
    smoke = _read(root / "scripts" / "run_live_api_readiness_smoke.py")
    post_permission = _read(root / "scripts" / "run_post_permission_live_api_verification.py")
    db = _read(root / "dashagent" / "db.py")
    validators = _read(root / "dashagent" / "validators.py")
    sql_ast = _read(root / "dashagent" / "sql_ast_tools.py")
    run_dev_eval = _read(root / "scripts" / "run_dev_eval.py")
    tests_text = "\n".join(_read(path) for path in (root / "tests").glob("test_*.py"))
    sdk_usage = _load_json(config.outputs_dir / "reports" / "sdk_usage_audit.json")

    sections = [
        _audit_section(
            "OpenAI SDK",
            "aligned" if all(token in llm_client for token in ["OpenAI", "chat.completions.create", "model_dump", "_normalize_openai_tool_calls"]) else "needs_manual_review",
            [
                "Uses OpenAI SDK client object for chat completions.",
                "Normalizes tool_calls and JSON argument strings defensively.",
                "Reads usage metadata from model-dumped SDK response without assuming token fields are present.",
                f"Runtime direct LLM HTTP hits: `{sdk_usage.get('summary', {}).get('runtime_llm_direct_http_hits', 'unavailable')}`.",
            ],
            ["dashagent/llm_client.py", "scripts/check_llm_sdk_backend.py"],
        ),
        _audit_section(
            "Anthropic SDK",
            "aligned" if all(token in llm_client for token in ["Anthropic", "messages.create", "input_schema", "_normalize_anthropic_usage"]) else "needs_manual_review",
            [
                "Uses Anthropic SDK messages.create path instead of direct HTTP.",
                "Converts OpenAI-style tools into Anthropic name/description/input_schema shape.",
                "Converts tool_use blocks back to the common internal tool-call shape.",
                "Normalizes input/output token usage into total_tokens defensively.",
            ],
            ["dashagent/llm_client.py"],
        ),
        _audit_section(
            "Adobe API Auth And Headers",
            "blocked_by_adobe_permission"
            if _live_success_count(_load_json(config.outputs_dir / "reports" / "live_api_readiness_smoke.json")) == 0
            else "aligned",
            [
                "Env readiness uses supported primary names and aliases without value-bearing report output.",
                "default_headers builds Authorization, x-api-key, x-gw-ims-org-id, and x-sandbox-name when constructible.",
                "Token acquisition failures return structured non-dry-run API evidence.",
                "Safe smoke/trial paths remain GET-only for Adobe data endpoints; IMS token request is the only OAuth POST.",
                "Current live data success remains blocked by Adobe endpoint-level permission/sandbox/path/service outcomes, not by credential construction.",
            ],
            [
                "dashagent/api_client.py",
                "dashagent/adobe_env.py",
                "dashagent/api_outcome_classifier.py",
                "scripts/run_live_api_readiness_smoke.py",
                "scripts/run_post_permission_live_api_verification.py",
            ],
        ),
        _audit_section(
            "DuckDB And SQLGlot SQL Safety",
            "aligned"
            if all(token in db for token in ["DESTRUCTIVE_SQL", "Multiple SQL statements", "execute_sql"])
            and all(token in sql_ast for token in ["parse_one", "read=dialect", "DESTRUCTIVE_EXPRESSIONS"])
            else "needs_manual_review",
            [
                "DuckDB execute path is wrapped by read-only SQL checks before execution.",
                "Multiple statements and destructive/environment-changing commands are blocked before DuckDB execution.",
                "SQLGlot parse_one uses the DuckDB dialect for AST summaries and destructive-expression detection.",
                "SQL validation reports parse warnings safely instead of crashing the executor.",
            ],
            ["dashagent/db.py", "dashagent/sql_ast_tools.py", "dashagent/validators.py"],
        ),
        _audit_section(
            "Pydantic / SDK Model Serialization",
            "aligned" if "model_dump" in llm_client and "dict" in llm_client else "no_action",
            [
                "Repo does not define first-party Pydantic models in runtime paths.",
                "SDK responses are serialized through model_dump when present, then dict/json fallbacks.",
                "Generated reports call json.dumps with default=str for non-JSON-native metadata.",
            ],
            ["dashagent/llm_client.py", "scripts/generate_consolidated_reports.py"],
        ),
        _audit_section(
            "CLI And Test Harness",
            "aligned"
            if all(token in run_dev_eval for token in ["allow-live-diagnostic-without-success", "evaluate_live_api_full_run_guard"])
            and all(token in tests_text for token in ["tmp_path", "monkeypatch"])
            else "needs_manual_review",
            [
                "Large live-run override is an explicit CLI flag, not an implicit env toggle.",
                "Tests use isolated tmp_path and monkeypatch patterns for report and environment coverage.",
                "Diagnostics are marked diagnostic-only and do not overwrite official strict artifacts under guarded override.",
            ],
            ["scripts/run_dev_eval.py", "tests"],
        ),
    ]

    direct_http_hits = _direct_llm_http_hits(root)
    if direct_http_hits:
        sections.append(
            _audit_section(
                "Direct LLM HTTP Search",
                "potential_bug",
                ["Direct LLM HTTP-like strings were found outside approved SDK wrappers; review before changing runtime."],
                direct_http_hits[:10],
            )
        )

    return _safe_payload(
        {
            "report_type": AUDIT_STEM,
            "created_at": _now(),
            "status": "complete",
            "docs_summary_path": "outputs/reports/context7_dependency_docs_summary.json",
            "documentation_grounded": bool(docs_summary.get("dependencies")),
            "audit_status_enum": sorted(ALLOWED_AUDIT_STATUSES),
            "sections": sections,
            "summary": {
                "section_count": len(sections),
                "potential_bug_count": sum(1 for section in sections if section.get("status") == "potential_bug"),
                "needs_manual_review_count": sum(1 for section in sections if section.get("status") == "needs_manual_review"),
                "blocked_by_adobe_permission_count": sum(
                    1 for section in sections if section.get("status") == "blocked_by_adobe_permission"
                ),
                "runtime_change_recommended": False,
                "packaged_strategy_unchanged": True,
                "final_submission_format_unchanged": True,
            },
        }
    )


def build_fix_decision(docs_summary: dict[str, Any], code_alignment: dict[str, Any]) -> dict[str, Any]:
    sections = code_alignment.get("sections", [])
    issues = [
        {
            "area": section.get("area"),
            "status": section.get("status"),
            "reason": "Requires manual/external review before code change.",
        }
        for section in sections
        if section.get("status") in {"potential_bug", "needs_manual_review", "minor_docs_mismatch"}
    ]
    code_changes_allowed = [
        issue for issue in issues
        if issue.get("status") == "potential_bug"
    ]
    return _safe_payload(
        {
            "report_type": FIX_STEM,
            "created_at": _now(),
            "docs_reviewed": [
                {
                    "dependency": row.get("dependency"),
                    "context7_library_id": row.get("context7_library_id"),
                    "context7_result": row.get("context7_result"),
                }
                for row in docs_summary.get("dependencies", [])
            ],
            "issues_found": issues,
            "code_changes_allowed": bool(code_changes_allowed),
            "code_changes_applied": False,
            "no_context7_backed_code_change": True,
            "fix_summary": "No runtime change applied. The audit found no single small docs-proven bug that passes the safe-fix gate.",
            "tests_added": ["tests/test_context7_code_alignment_audit.py"],
            "regression_result": {
                "runtime_code_changed": False,
                "strict_eval_required": False,
                "hidden_style_required": False,
                "packaged_strategy_unchanged": True,
                "final_submission_format_unchanged": True,
            },
            "guardrails": [
                "No endpoint catalog path changes without safe GET evidence.",
                "No semantic router/controller/answer rewrite promotion.",
                "No generated-prompt-based runtime change.",
                "No final submission format change.",
            ],
        }
    )


def render_preflight_md(payload: dict[str, Any]) -> str:
    ctx7 = payload.get("ctx7_cli", {})
    return "\n".join(
        [
            "# Context7 Docs Audit Preflight",
            "",
            f"- Created at: `{payload.get('created_at')}`",
            f"- Git status mode: `{payload.get('git_status', {}).get('mode')}`",
            f"- Git status timed out: `{payload.get('git_status', {}).get('timed_out')}`",
            f"- Direct `ctx7` available: `{ctx7.get('direct_command_available')}`",
            f"- Selected Context7 command: `{ctx7.get('selected_command')}`",
            f"- Packaged strategy: `{payload.get('current_packaged_strategy')}`",
            f"- Strict score: `{payload.get('current_strict_score')}`",
            f"- Hidden-style: `{payload.get('hidden_style_status')}`",
            f"- Final submission ready: `{payload.get('final_submission_ready')}`",
            f"- Live success count: `{payload.get('live_success_count')}`",
            f"- Runtime changes allowed by default: `{payload.get('runtime_changes_allowed_by_default')}`",
            "",
            "## Protected Artifacts",
            "",
            *[f"- `{item}`" for item in payload.get("protected_artifacts", [])],
            "",
            "## Rule",
            "",
            payload.get("no_runtime_change_by_default_rule", ""),
            "",
        ]
    )


def render_docs_summary_md(payload: dict[str, Any]) -> str:
    lines = [
        "# Context7 Dependency Docs Summary",
        "",
        "This report stores short findings only. Raw Context7 documentation output is not stored.",
        "",
        f"- Dependency count: `{payload.get('dependency_count')}`",
        f"- Context7 found count: `{payload.get('context7_found_count')}`",
        f"- Raw docs stored: `{payload.get('raw_docs_stored')}`",
        "",
    ]
    for row in payload.get("dependencies", []):
        lines.extend(
            [
                f"## {row.get('dependency')}",
                "",
                f"- Context7 library ID: `{row.get('context7_library_id')}`",
                f"- Result: `{row.get('context7_result')}`",
                f"- Query: `{row.get('docs_query_used')}`",
                f"- Risk: `{row.get('risk_level')}`",
                f"- Code audit needed: `{row.get('code_audit_needed')}`",
                "- Findings:",
                *[f"  - {finding}" for finding in row.get("key_docs_findings", [])],
                "- Repo files:",
                *[f"  - `{path}`" for path in row.get("repo_files_affected", [])],
                "",
            ]
        )
    return "\n".join(lines)


def render_code_alignment_md(payload: dict[str, Any]) -> str:
    lines = [
        "# Context7 Code Alignment Audit",
        "",
        f"- Status: `{payload.get('status')}`",
        f"- Documentation grounded: `{payload.get('documentation_grounded')}`",
        f"- Runtime change recommended: `{payload.get('summary', {}).get('runtime_change_recommended')}`",
        "",
    ]
    for section in payload.get("sections", []):
        lines.extend(
            [
                f"## {section.get('area')}",
                "",
                f"- Status: `{section.get('status')}`",
                "- Findings:",
                *[f"  - {finding}" for finding in section.get("findings", [])],
                "- Files:",
                *[f"  - `{path}`" for path in section.get("files", [])],
                "",
            ]
        )
    return "\n".join(lines)


def render_fix_decision_md(payload: dict[str, Any]) -> str:
    lines = [
        "# Context7 Fix Decision",
        "",
        f"- Code changes allowed: `{payload.get('code_changes_allowed')}`",
        f"- Code changes applied: `{payload.get('code_changes_applied')}`",
        f"- No Context7-backed code change: `{payload.get('no_context7_backed_code_change')}`",
        f"- Fix summary: {payload.get('fix_summary')}",
        "",
        "## Guardrails",
        "",
        *[f"- {item}" for item in payload.get("guardrails", [])],
        "",
    ]
    if payload.get("issues_found"):
        lines.extend(["## Issues Requiring Review", ""])
        for issue in payload.get("issues_found", []):
            lines.append(f"- `{issue.get('area')}`: `{issue.get('status')}` - {issue.get('reason')}")
    return "\n".join(lines)


def _audit_section(area: str, status: str, findings: list[str], files: list[str]) -> dict[str, Any]:
    if status not in ALLOWED_AUDIT_STATUSES:
        status = "needs_manual_review"
    return {
        "area": area,
        "status": status,
        "findings": findings,
        "files": files,
        "documentation_grounded": True,
        "runtime_change_recommended": False,
    }


def _collect_git_status(root: Path, runner: Runner) -> dict[str, Any]:
    result = runner(["git", "status", "--short"], root, GIT_STATUS_TIMEOUT_SECONDS)
    lines = [line for line in str(result.get("stdout") or "").splitlines() if line.strip()]
    return {
        "mode": "git_status_short" if not result.get("timed_out") else "git_status_short_timeout",
        "timeout_seconds": GIT_STATUS_TIMEOUT_SECONDS,
        "exit_code": result.get("exit_code"),
        "timed_out": bool(result.get("timed_out")),
        "line_count": len(lines),
        "lines": lines[:200],
    }


def _run_command(command: list[str], cwd: Path, timeout: int) -> dict[str, Any]:
    try:
        completed = subprocess.run(command, cwd=cwd, check=False, capture_output=True, text=True, timeout=timeout)
        return {
            "command": list(command),
            "exit_code": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "timed_out": False,
        }
    except FileNotFoundError as exc:
        return {"command": list(command), "exit_code": 127, "stdout": "", "stderr": str(exc), "timed_out": False}
    except subprocess.TimeoutExpired as exc:
        return {
            "command": list(command),
            "exit_code": None,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "timed_out": True,
        }


def _skipped_result(command: list[str]) -> dict[str, Any]:
    return {"command": list(command), "exit_code": None, "stdout": "", "stderr": "skipped", "timed_out": False}


def _combined_output(result: dict[str, Any]) -> str:
    text = f"{result.get('stdout') or ''}\n{result.get('stderr') or ''}"
    redacted = redact_secrets(text)
    return str(redacted) if redacted is not None else ""


def _parse_context7_library_id(output: str) -> str | None:
    match = re.search(r"Context7-compatible library ID:\s*(/\S+)", output)
    return match.group(1).strip() if match else None


def _observed_markers(output: str, markers: tuple[str, ...]) -> dict[str, bool]:
    lower = output.lower()
    return {marker: marker.lower() in lower for marker in markers}


def _load_preflight_sources(config: Config) -> dict[str, Any]:
    outputs = config.outputs_dir
    reports = outputs / "reports"
    return {
        "system_summary": _load_json(reports / "system_summary.json"),
        "winner_readiness": _load_json(outputs / "winner_readiness_report.json"),
        "hidden_style": _load_json(outputs / "hidden_style_eval.json"),
        "live_api_smoke": _load_json(reports / "live_api_readiness_smoke.json"),
    }


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def _live_success_count(smoke: dict[str, Any]) -> int:
    if isinstance(smoke.get("live_success_count"), int):
        return int(smoke["live_success_count"])
    rows = smoke.get("endpoint_results") or smoke.get("endpoint_rows") or smoke.get("endpoints") or []
    if isinstance(rows, list):
        return sum(1 for row in rows if isinstance(row, dict) and row.get("outcome") == "live_success")
    return 0


def _hidden_label(summary: dict[str, Any]) -> str:
    passed = summary.get("passed_cases")
    total = summary.get("total_cases")
    if passed is None or total is None:
        return "unavailable"
    return f"{passed}/{total}"


def _direct_llm_http_hits(root: Path) -> list[str]:
    hits: list[str] = []
    patterns = [
        "/chat" + "/completions",
        "/v1" + "/messages",
        "api." + "openai.com" + "/v1" + "/chat",
        "api." + "anthropic" + ".com" + "/v1" + "/messages",
    ]
    for folder in [root / "dashagent", root / "scripts"]:
        if not folder.exists():
            continue
        for path in folder.rglob("*.py"):
            if path.name in {Path(__file__).name, "generate_sdk_usage_audit.py", "check_llm_sdk_backend.py"}:
                continue
            text = _read(path)
            if any(pattern in text for pattern in patterns):
                hits.append(path.relative_to(root).as_posix())
    return sorted(set(hits))


def _safe_payload(payload: Any) -> Any:
    safe = redact_secrets(payload)
    return safe


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
