from __future__ import annotations

import json
import re
from pathlib import Path

from scripts.generate_consolidated_reports import generate_consolidated_reports
from scripts.package_submission import REQUIRED_PATHS
from scripts.run_context7_code_alignment_audit import (
    ALLOWED_AUDIT_STATUSES,
    PROTECTED_ARTIFACTS,
    run_context7_code_alignment_audit,
)


def _write_minimal_audited_repo(root: Path) -> None:
    (root / "dashagent").mkdir(exist_ok=True)
    (root / "scripts").mkdir(exist_ok=True)
    (root / "tests").mkdir(exist_ok=True)
    (root / "dashagent" / "llm_client.py").write_text(
        "\n".join(
            [
                "from openai import OpenAI",
                "from anthropic import Anthropic",
                "client.chat.completions.create(**payload)",
                "client.messages.create(**payload)",
                "completion.model_dump()",
                "response.model_dump()",
                "completion.dict()",
                "_normalize_openai_tool_calls = True",
                "_normalize_anthropic_usage = True",
                "input_schema = {}",
            ]
        ),
        encoding="utf-8",
    )
    (root / "dashagent" / "api_client.py").write_text(
        "default_headers Authorization x-api-key x-gw-ims-org-id x-sandbox-name TokenAcquisitionError",
        encoding="utf-8",
    )
    (root / "dashagent" / "adobe_env.py").write_text(
        "format_adobe_readiness_for_report ADOBE_ACCESS_TOKEN ADOBE_API_KEY ADOBE_ORG_ID ADOBE_SANDBOX_NAME",
        encoding="utf-8",
    )
    (root / "dashagent" / "api_outcome_classifier.py").write_text("classify_api_outcome", encoding="utf-8")
    (root / "dashagent" / "db.py").write_text(
        "DESTRUCTIVE_SQL Multiple SQL statements execute_sql", encoding="utf-8"
    )
    (root / "dashagent" / "sql_ast_tools.py").write_text(
        "parse_one read=dialect DESTRUCTIVE_EXPRESSIONS", encoding="utf-8"
    )
    (root / "dashagent" / "validators.py").write_text("SQLValidator APIValidator", encoding="utf-8")
    (root / "scripts" / "run_live_api_readiness_smoke.py").write_text("GET only smoke", encoding="utf-8")
    (root / "scripts" / "run_post_permission_live_api_verification.py").write_text("post permission", encoding="utf-8")
    (root / "scripts" / "run_dev_eval.py").write_text(
        "allow-live-diagnostic-without-success evaluate_live_api_full_run_guard", encoding="utf-8"
    )
    (root / "tests" / "test_dummy.py").write_text("def test_x(tmp_path, monkeypatch): pass", encoding="utf-8")


def _fake_context7_runner(command: list[str], cwd: Path, timeout: int) -> dict:
    if command[:3] == ["git", "status", "--short"]:
        return {"command": command, "exit_code": 0, "stdout": "", "stderr": "", "timed_out": False}
    if command[:2] == ["ctx7", "--help"]:
        return {"command": command, "exit_code": 0, "stdout": "Usage: ctx7", "stderr": "", "timed_out": False}
    if "library" in command:
        return {
            "command": command,
            "exit_code": 0,
            "stdout": "Context7-compatible library ID: /fake/library\n",
            "stderr": "",
            "timed_out": False,
        }
    if "docs" in command:
        return {
            "command": command,
            "exit_code": 0,
            "stdout": (
                "chat.completions.create tools tool_choice usage messages.create tool_use input_schema "
                "Authorization" + ": " + "Bearer sample-token-value x-api-key sample-api-key-value "
                "x-gw-ims-org-id sample-org-value x-sandbox-name sample-sandbox-value "
                "execute fetchall parameters Multiple statements parse_one read dialect ParseError "
                "model_dump model_dump_json BaseModel validation Options required callback help "
                "monkeypatch tmp_path capsys fixture fake-key-value-without-sk-prefix"
            ),
            "stderr": "",
            "timed_out": False,
        }
    return {"command": command, "exit_code": 0, "stdout": "", "stderr": "", "timed_out": False}


def test_context7_audit_reports_exist_and_do_not_store_raw_secret_docs(tiny_project):
    _write_minimal_audited_repo(tiny_project.project_root)

    payload = run_context7_code_alignment_audit(tiny_project, ctx7_runner=_fake_context7_runner)
    reports = tiny_project.outputs_dir / "reports"

    for stem in [
        "context7_docs_audit_preflight",
        "context7_dependency_docs_summary",
        "context7_code_alignment_audit",
        "context7_fix_decision",
    ]:
        assert (reports / f"{stem}.json").exists()
        assert (reports / f"{stem}.md").exists()
        json.loads((reports / f"{stem}.json").read_text(encoding="utf-8"))

    assert payload["docs_summary"]["dependency_count"] == 8
    assert payload["docs_summary"]["raw_docs_stored"] is False
    assert payload["fix_decision"]["code_changes_applied"] is False
    assert payload["fix_decision"]["no_context7_backed_code_change"] is True

    combined = "\n".join(path.read_text(encoding="utf-8") for path in reports.glob("context7_*.json"))
    for forbidden in [
        "sample-token-value",
        "sample-api-key-value",
        "sample-org-value",
        "sample-sandbox-value",
        "fake-key-value-without-sk-prefix",
        "Authorization" + ": " + "Bearer secret",
    ]:
        assert forbidden not in combined


def test_context7_preflight_protects_artifacts_and_audit_schema(tiny_project):
    _write_minimal_audited_repo(tiny_project.project_root)
    run_context7_code_alignment_audit(tiny_project, ctx7_runner=_fake_context7_runner)

    reports = tiny_project.outputs_dir / "reports"
    preflight = json.loads((reports / "context7_docs_audit_preflight.json").read_text(encoding="utf-8"))
    audit = json.loads((reports / "context7_code_alignment_audit.json").read_text(encoding="utf-8"))
    decision = json.loads((reports / "context7_fix_decision.json").read_text(encoding="utf-8"))

    assert "outputs/final_submission/**" in preflight["protected_artifacts"]
    assert ".env.local" in preflight["protected_artifacts"]
    assert set(PROTECTED_ARTIFACTS).issubset(set(preflight["protected_artifacts"]))
    assert preflight["runtime_changes_allowed_by_default"] is False
    assert audit["documentation_grounded"] is True
    assert audit["summary"]["packaged_strategy_unchanged"] is True
    assert audit["summary"]["final_submission_format_unchanged"] is True
    for section in audit["sections"]:
        assert section["status"] in ALLOWED_AUDIT_STATUSES
    assert decision["regression_result"]["runtime_code_changed"] is False


def test_context7_reports_are_linked_from_consolidated_index(tiny_project):
    _write_minimal_audited_repo(tiny_project.project_root)
    run_context7_code_alignment_audit(tiny_project, ctx7_runner=_fake_context7_runner)

    generate_consolidated_reports(tiny_project)
    index = json.loads((tiny_project.outputs_dir / "reports" / "report_index.json").read_text(encoding="utf-8"))
    assert index["context7_documentation_grounded_audit"]["code_alignment_path"] == (
        "outputs/reports/context7_code_alignment_audit.md"
    )
    assert index["context7_documentation_grounded_audit"]["code_changes_applied"] is False
    md = (tiny_project.outputs_dir / "reports" / "report_index.md").read_text(encoding="utf-8")
    assert "Context7 Documentation-Grounded Audit" in md
    assert "context7_fix_decision.md" in md


def test_context7_script_is_packaged_and_docs_mention_it():
    assert "scripts/run_context7_code_alignment_audit.py" in REQUIRED_PATHS
    readme = Path("README.md").read_text(encoding="utf-8")
    agents = Path("AGENTS.md").read_text(encoding="utf-8")
    for text in [readme, agents]:
        assert "Context7 documentation" in text or "Context7 Documentation" in text
        assert "python3 scripts/run_context7_code_alignment_audit.py" in text
        assert "Context7 API key" in text
        assert "live_success" in text


def test_context7_report_secret_patterns_are_absent_from_current_outputs():
    reports = Path("outputs/reports")
    if not (reports / "context7_code_alignment_audit.json").exists():
        return
    combined = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in reports.glob("context7_*"))
    assert "Authorization" + ": " + "Bearer" not in combined
    assert not re.search(r"sk-[A-Za-z0-9_-]{12,}", combined)
    assert not re.search(r"\b[a-zA-Z0-9]{3}\*\*\*", combined)
