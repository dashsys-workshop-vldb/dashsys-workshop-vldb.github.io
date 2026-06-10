#!/usr/bin/env python
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashagent.config import Config
SKILL_DIR = ROOT / "skills" / "dashsys_project_skill"
REPORT_STEM = "dashsys_project_skill_audit"
REQUIRED_FILES = {
    "skill_md_exists": SKILL_DIR / "SKILL.md",
    "checklists_md_exists": SKILL_DIR / "checklists.md",
    "commands_md_exists": SKILL_DIR / "commands.md",
    "workflows_md_exists": SKILL_DIR / "workflows.md",
    "skill_readme_exists": SKILL_DIR / "README.md",
}
REQUIRED_SKILL_PHRASES = {
    "mentions_sql_first_api_verify": "SQL_FIRST_API_VERIFY",
    "mentions_correctness_efficiency": "correctness + efficiency",
    "mentions_live_success_guard": "live_success guard",
    "mentions_generated_prompts_diagnostic_only": "generated prompts are diagnostic-only",
    "mentions_no_hardcoding": "Never hard-code",
    "mentions_final_submission_protection": "outputs/final_submission/**",
    "mentions_sdk_only_llm_policy": "SDK-only LLM policy",
    "mentions_direct_http_zero": "runtime direct LLM HTTP hits = 0",
    "mentions_secret_scan": "secret scan",
    "mentions_promotion_gates": "Promotion gates",
    "mentions_rollback": "rollback",
}
SECRET_VALUE_RE = re.compile(
    r"sk-[A-Za-z0-9_-]{12,}"
    r"|Bearer\s+[A-Za-z0-9._-]{12,}"
    r"|Authorization:\s*Bearer\s+[A-Za-z0-9._-]+"
    r"|[A-Za-z0-9]{3}\*\*\*",
    re.IGNORECASE,
)


def main() -> int:
    config = Config.from_env(ROOT)
    payload = audit_dashsys_project_skill(config)
    print(json.dumps({"overall_status": payload["overall_status"], "report": payload["report_path_json"]}, indent=2, sort_keys=True))
    return 0 if payload["overall_status"] == "pass" else 1


def audit_dashsys_project_skill(config: Config | None = None) -> dict[str, Any]:
    config = config or Config.from_env(ROOT)
    reports_dir = config.outputs_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    skill_texts = {path.name: _read(path) for path in REQUIRED_FILES.values()}
    combined_skill = "\n".join(skill_texts.values())
    readme = _read(ROOT / "README.md")
    agents = _read(ROOT / "AGENTS.md")

    checks: dict[str, bool] = {}
    for name, path in REQUIRED_FILES.items():
        checks[name] = path.exists()
    for name, phrase in REQUIRED_SKILL_PHRASES.items():
        checks[name] = phrase in combined_skill

    checks.update(
        {
            "readme_links_skill": "skills/dashsys_project_skill/SKILL.md" in readme,
            "agents_links_skill": "skills/dashsys_project_skill/SKILL.md" in agents,
            "contains_no_secret_values": SECRET_VALUE_RE.search(combined_skill + "\n" + readme + "\n" + agents) is None,
            "no_unsafe_live_eval_instruction": _no_unapproved_instruction(
                combined_skill,
                "run full live strict eval while `live_success_count=0`",
                "Do not run full live strict eval while `live_success_count=0`",
            ),
            "no_live_prompt_suite_instruction": _no_unapproved_instruction(
                combined_skill,
                "run the live generated-prompt suite while `live_success_count=0`",
                "Do not run the live generated-prompt suite while `live_success_count=0`",
            ),
            "no_mutating_adobe_instruction": _no_unapproved_instruction(
                combined_skill,
                "run mutating Adobe API calls",
                "Never run mutating Adobe API calls",
            ),
            "does_not_instruct_env_local_access": "Never access `.env.local`" in combined_skill,
            "does_not_instruct_query_or_gold_hardcoding": "Never hard-code query IDs" in combined_skill
            and "gold answers" in combined_skill,
        }
    )

    payload = {
        "report_type": REPORT_STEM,
        "generated_at": _now(),
        "report_path_json": str(reports_dir / f"{REPORT_STEM}.json"),
        "report_path_md": str(reports_dir / f"{REPORT_STEM}.md"),
        "skill_dir": "skills/dashsys_project_skill",
        "files": {path.name: str(path.relative_to(ROOT)) for path in REQUIRED_FILES.values()},
        "checks": checks,
        "overall_status": "pass" if all(checks.values()) else "fail",
        "failed_checks": sorted(name for name, ok in checks.items() if not ok),
        "runtime_behavior_changed": False,
        "credentials_accessed": False,
        "env_local_accessed": False,
        "unsafe_live_eval_allowed": False,
        "mutating_adobe_calls_allowed": False,
    }
    _write_report_pair(reports_dir / REPORT_STEM, payload, _render_markdown(payload))
    return payload


def _no_unapproved_instruction(text: str, phrase: str, approved_phrase: str) -> bool:
    return phrase not in text.replace(approved_phrase, "")


def _read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def _write_report_pair(stem_path: Path, payload: dict[str, Any], markdown: str) -> None:
    stem_path.with_suffix(".json").write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    stem_path.with_suffix(".md").write_text(markdown, encoding="utf-8")


def _render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# DASHSys Project Skill Audit",
        "",
        f"- Overall status: `{payload['overall_status']}`",
        f"- Skill directory: `{payload['skill_dir']}`",
        f"- Runtime behavior changed: `{payload['runtime_behavior_changed']}`",
        f"- Credentials accessed: `{payload['credentials_accessed']}`",
        f"- Env local accessed: `{payload['env_local_accessed']}`",
        f"- Unsafe live eval allowed: `{payload['unsafe_live_eval_allowed']}`",
        f"- Mutating Adobe calls allowed: `{payload['mutating_adobe_calls_allowed']}`",
        "",
        "## Checks",
        "",
    ]
    for name, ok in sorted(payload["checks"].items()):
        lines.append(f"- `{name}`: `{ok}`")
    if payload["failed_checks"]:
        lines.extend(["", "## Failed Checks", ""])
        lines.extend(f"- `{name}`" for name in payload["failed_checks"])
    return "\n".join(lines) + "\n"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
