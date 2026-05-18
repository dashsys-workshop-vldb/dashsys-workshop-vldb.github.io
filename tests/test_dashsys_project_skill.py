from __future__ import annotations

import json
import re
from pathlib import Path

from dashagent.config import Config
from scripts.audit_dashsys_project_skill import audit_dashsys_project_skill
from scripts.generate_consolidated_reports import POST_CHANGE_VALIDATION_COMMANDS, REPORT_REGENERATION_TARGETS


SKILL_DIR = Path("skills/dashsys_project_skill")
SKILL_FILES = [
    SKILL_DIR / "SKILL.md",
    SKILL_DIR / "checklists.md",
    SKILL_DIR / "commands.md",
    SKILL_DIR / "workflows.md",
    SKILL_DIR / "README.md",
]
SECRET_VALUE_RE = re.compile(
    r"sk-[A-Za-z0-9_-]{12,}"
    r"|Bearer\s+[A-Za-z0-9._-]{12,}"
    r"|Authorization:\s*Bearer\s+[A-Za-z0-9._-]+"
    r"|[A-Za-z0-9]{3}\*\*\*",
    re.IGNORECASE,
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_dashsys_project_skill_files_exist_and_contain_guardrails():
    for path in SKILL_FILES:
        assert path.exists(), path

    skill = _read(SKILL_DIR / "SKILL.md")
    required_phrases = [
        "DASHSys Project Skill",
        "SQL_FIRST_API_VERIFY",
        "correctness + efficiency",
        "live_success guard",
        "generated prompts are diagnostic-only",
        "Never hard-code",
        "outputs/final_submission/**",
        "SDK-only LLM policy",
        "runtime direct LLM HTTP hits = 0",
        "secret scan",
        "Promotion gates",
        "rollback",
    ]
    for phrase in required_phrases:
        assert phrase in skill

    assert "Never access `.env.local`" in skill
    assert "Do not run full live strict eval while `live_success_count=0`" in skill
    assert "Do not run the live generated-prompt suite while `live_success_count=0`" in skill
    assert "Never run mutating Adobe API calls" in skill
    assert "Generated labels are advisory, not ground truth" in skill


def test_dashsys_skill_supporting_docs_cover_commands_workflows_and_checklists():
    commands = _read(SKILL_DIR / "commands.md")
    workflows = _read(SKILL_DIR / "workflows.md")
    checklists = _read(SKILL_DIR / "checklists.md")

    for command in [
        "python3 scripts/check_submission_ready.py",
        "python3 -m pytest -q",
        "python3 scripts/run_dev_eval.py --strict",
        "python3 scripts/run_hidden_style_eval.py",
        "python3 scripts/run_correctness_efficiency_scorecard.py",
        "python3 scripts/run_post_permission_live_api_verification.py",
        "python3 scripts/generate_consolidated_reports.py",
    ]:
        assert command in commands

    for heading in [
        "Score improvement checklist",
        "Efficiency improvement checklist",
        "Adobe live API checklist",
        "SDK tool-calling checklist",
        "Secret safety checklist",
        "Rollback checklist",
    ]:
        assert heading in checklists

    for workflow in [
        "Workflow: score-path improvement",
        "Workflow: efficiency-only patch",
        "Workflow: post-permission Adobe verification",
        "Workflow: SDK/tool-calling optimization",
        "Workflow: generated prompt analysis",
        "Workflow: final submission packaging",
    ]:
        assert workflow in workflows


def test_dashsys_skill_readme_and_project_docs_link_skill():
    skill_readme = _read(SKILL_DIR / "README.md")
    readme = _read(Path("README.md"))
    agents = _read(Path("AGENTS.md"))

    assert "DASHSys Project Skill" in skill_readme
    assert "skills/dashsys_project_skill/SKILL.md" in readme
    assert "skills/dashsys_project_skill/SKILL.md" in agents
    assert "Use this skill before any serious Codex change" in readme
    assert "Use this skill before any serious Codex change" in agents


def test_dashsys_project_skill_audit_generates_reports(tiny_project):
    project = tmp_project_with_skill_docs(tiny_project)
    payload = audit_dashsys_project_skill(project)

    reports = project.outputs_dir / "reports"
    assert (reports / "dashsys_project_skill_audit.json").exists()
    assert (reports / "dashsys_project_skill_audit.md").exists()
    assert payload["overall_status"] == "pass"
    assert payload["checks"]["skill_md_exists"] is True
    assert payload["checks"]["commands_md_exists"] is True
    assert payload["checks"]["readme_links_skill"] is True
    assert payload["checks"]["agents_links_skill"] is True
    assert payload["checks"]["contains_no_secret_values"] is True
    assert payload["checks"]["no_unsafe_live_eval_instruction"] is True
    assert payload["checks"]["no_mutating_adobe_instruction"] is True

    saved = json.loads((reports / "dashsys_project_skill_audit.json").read_text(encoding="utf-8"))
    assert saved["overall_status"] == "pass"


def test_dashsys_skill_files_have_no_secret_values_or_unsafe_instructions():
    combined = "\n".join(_read(path) for path in SKILL_FILES)
    assert not SECRET_VALUE_RE.search(combined)
    assert "run full live strict eval while `live_success_count=0`" not in combined.replace(
        "Do not run full live strict eval while `live_success_count=0`",
        "",
    )
    assert "run the live generated-prompt suite while `live_success_count=0`" not in combined.replace(
        "Do not run the live generated-prompt suite while `live_success_count=0`",
        "",
    )
    assert "hard-code query IDs" not in combined.replace("Never hard-code query IDs", "")
    assert "hard-code gold answers" not in combined.replace("gold answers", "")


def test_consolidated_report_contract_includes_dashsys_skill_audit():
    assert "python3 scripts/audit_dashsys_project_skill.py" in POST_CHANGE_VALIDATION_COMMANDS
    assert "outputs/reports/dashsys_project_skill_audit.md/json" in REPORT_REGENERATION_TARGETS


def tmp_project_with_skill_docs(config: Config) -> Config:
    # The audit reads project docs from the repo root and writes reports under the supplied outputs dir.
    return config
