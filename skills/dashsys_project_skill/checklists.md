# DASHSys Project Skill Checklists

## Score improvement checklist

- Read `outputs/eval_results_strict.json` and score reports first.
- Classify affected path: router, planner, SQL, API, EvidenceBus, answer synthesis, verifier, or trajectory.
- Use official public/dev rows for score evidence.
- Use generated prompts only for generalness and coverage.
- Confirm no query ID, prompt ID, exact prompt, public example, hidden assumption, or gold-answer hardcoding.
- Run strict eval, hidden-style eval, readiness, and pytest before promotion.

## Efficiency improvement checklist

- Read `outputs/reports/correctness_efficiency_scorecard.md/json`.
- Measure turns, tool calls, tokens, wall time, and end-to-end runtime where available.
- Keep correctness stable or better.
- Prefer small independent speed patches before combined policy changes.
- Do not claim official overall score while organizer weights are unknown.

## Adobe live API checklist

- Read `outputs/reports/live_api_full_run_blocker.md/json`.
- Confirm current `live_success_count`.
- Use safe GET smoke and readiness only before access is granted.
- Never access `.env.local`.
- Never print credentials, request IDs, org values, sandbox values, or masked prefixes.
- After permission is granted, run `python3 scripts/run_post_permission_live_api_verification.py`.
- Do not run full live eval until the live_success guard allows it.

## SDK tool-calling checklist

- Read `outputs/reports/sdk_usage_audit.md/json`.
- Confirm runtime direct LLM HTTP hits remain `0`.
- Keep SDK-only LLM policy.
- Treat controller, semantic router, and rewrite paths as shadow-only unless promotion gates pass.
- Use Context7 docs before changing external SDK/API behavior when available.
- Validate compact schemas, tool result summaries, allowed tools, and provider compatibility with focused tests.

## Generated prompt diagnostic checklist

- Confirm generated prompts are diagnostic-only.
- Treat generated labels as advisory, not ground truth.
- Do not create exact prompt or generated prompt ID rules.
- Use generated prompts for coverage/generalness only.
- Rerun `python3 scripts/run_generated_prompt_suite_local_diagnostic.py` only in local dry-run-safe mode.

## Report/visualization checklist

- Generate `.md` and `.json` reports.
- Link reports from `outputs/reports/report_index.md/json`.
- Update `outputs/reports/system_summary.md/json` when the report changes project status.
- Do not claim score improvement from report wording or visualization changes.
- Keep diagrams and reports free of credentials and masked prefixes.

## Packaging/submission checklist

- Protect `outputs/final_submission/**`.
- Protect `outputs/eval_results_strict.json` unless intentionally running strict eval.
- Protect final submission manifests.
- Run `python3 scripts/check_submission_ready.py`.
- Preserve `SQL_FIRST_API_VERIFY` as packaged default unless explicitly approved after validation.
- Preserve final submission format.

## Secret safety checklist

- Exclude `.git`, `.env.local`, and zip files.
- Scan for credential values, Authorization/Bearer values, access tokens, API keys, client secrets, organization values, sandbox values, request IDs, and masked prefixes.
- Redact before writing reports.
- Do not print environment variable values.

## Rollback checklist

- If strict score regresses, rollback runtime changes.
- If hidden-style drops below `48/48`, rollback runtime changes.
- If readiness or pytest fails after runtime change, rollback or write a blocker.
- Keep diagnostic reports when useful.
- Record command, reason, substitute validation, and residual risk for skipped or failed validation.
