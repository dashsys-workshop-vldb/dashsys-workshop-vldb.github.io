# DASHSys Project Skill

This repo-local Codex Skill captures the DASHSys workflow for safe, score-aware project work.

Use it before any serious Codex change that touches correctness, efficiency, live Adobe API readiness, SDK/LLM behavior, generated prompts, reports, visualizations, packaging, or security.

The Skill protects final submission artifacts, official eval artifacts, endpoint catalog paths, `.env.local`, packaged defaults, and source package outputs. It distinguishes correctness from efficiency, keeps generated prompts diagnostic-only, blocks unsafe live eval while `live_success_count=0`, and requires validation before promotion.

Primary file:

- `skills/dashsys_project_skill/SKILL.md`

Supporting references:

- `skills/dashsys_project_skill/checklists.md`
- `skills/dashsys_project_skill/commands.md`
- `skills/dashsys_project_skill/workflows.md`

How to ask Codex to use it:

```text
Use the DASHSys Project Skill for this repo task.
```

Manual installation, if your Codex environment supports local skills:

```bash
cp -R skills/dashsys_project_skill /path/to/codex/skills/
```

Do not auto-copy this Skill into a user home directory from repo scripts. If local skill loading is unavailable, paste or reference `SKILL.md` in the Codex task prompt or keep the link in `AGENTS.md`.

