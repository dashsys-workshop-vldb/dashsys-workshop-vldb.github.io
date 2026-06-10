# DASHSys Project Skill Workflows

## Workflow: score-path improvement

1. Read git status and current score reports.
2. Identify direct score-path component: router, planner, SQL, API, EvidenceBus, answer synthesis, verifier, or trajectory.
3. Form a general hypothesis from official strict rows.
4. Use generated prompts only to test generalness and coverage.
5. Run an isolated trial that does not overwrite official artifacts.
6. Promote only if strict score improves or no-regression efficiency gates justify the change.
7. Run strict eval, hidden-style eval, readiness, pytest, and secret scan.
8. Rollback on regression.

## Workflow: efficiency-only patch

1. Read the correctness + efficiency scorecard.
2. Confirm correctness is stable.
3. Choose the smallest speed patch: schema compaction, compact summaries, allowed tools, or safe skip gate.
4. Measure tool calls, tokens, wall time, and end-to-end runtime.
5. Promote only with no correctness regression and hidden-style `48/48`.
6. Do not claim official organizer-weighted score without known weights.

## Workflow: post-permission Adobe verification

1. Confirm the task is a live Adobe API path task.
2. Do not read `.env.local`.
3. Run safe readiness and all-safe-get smoke only.
4. Run `python3 scripts/run_post_permission_live_api_verification.py`.
5. If `live_success_count=0`, keep full live eval blocked and use follow-up commands.
6. If the structured guard allows live runs, proceed only with explicit user intent.

## Workflow: SDK/tool-calling optimization

1. Read SDK audit, tool-call trial, and correctness + efficiency reports.
2. Confirm SDK-only LLM policy and direct HTTP hits `0`.
3. Use Context7 docs before external SDK/API behavior changes when available.
4. Trial compact schema, compact result summaries, allowed tools, tool choice, and rewrite gates in isolation.
5. Keep controller/semantic-router/rewrite behavior shadow-only unless gates pass.
6. Validate with strict eval, hidden-style, SDK audit, readiness, pytest, and secret scan.

## Workflow: generated prompt analysis

1. Confirm generated prompts are diagnostic-only.
2. Run local dry-run diagnostic only.
3. Treat generated labels as advisory.
4. Compare labels to actual route/domain/evidence behavior before marking a bug.
5. Propose general rules only when official rows or broad semantics support them.
6. Never implement exact prompt or prompt ID logic.

## Workflow: final submission packaging

1. Confirm runtime changes have passed validation.
2. Run `python3 scripts/package_submission.py` only when packaging is intended.
3. Run `python3 scripts/package_query_outputs.py` when query outputs must refresh.
4. Run `python3 scripts/check_submission_ready.py`.
5. Confirm final submission format and packaged default strategy are unchanged unless explicitly approved.

## Workflow: visualization update

1. Treat visualizations as reporting, not score improvement.
2. Read source reports first.
3. Regenerate visualizations with repo scripts.
4. Run visualization/report tests and readiness.
5. Do not include credentials, raw prompt answers, or sensitive values.

## Workflow: blocker handling

1. Stop when a protected deletion, unexpected runtime source change, missing readiness, credential need, hardcoding need, or failed validation appears.
2. Write a blocker report with command, reason, substitute validation, and residual risk.
3. Do not continue into promotion until the blocker is resolved.

