---
name: dashsys-project-skill
description: Use when working in the DASHSys workshop repository on score, efficiency, live Adobe API, SDK/LLM, reports, visualization, packaging, or safety-sensitive changes.
---

# DASHSys Project Skill

## Skill Identity

Name: DASHSys Project Skill.

Purpose: safe score-aware development for the DASHSys workshop repo.

Scope: code review, correctness score analysis, efficiency analysis, live API readiness, diagnostics, reports, visualization, packaging, security, and final-submission safety.

Non-goals: arbitrary rewriting, hardcoding, unsafe live API use, endpoint guessing, broad LLM/controller promotion, semantic-router promotion, broad answer rewrite promotion, or final-submission format changes.

Packaged default: keep `SQL_FIRST_API_VERIFY` unless the user explicitly approves a validated promotion.

## First-Response Checklist

Before changing files, inspect current state:

- `git status --short`
- `outputs/reports/system_summary.md` and `.json`
- `outputs/reports/report_index.md` and `.json`
- `outputs/reports/accuracy_and_bottleneck_summary.md` and `.json`
- For live/API tasks: `outputs/reports/live_api_full_run_blocker.md` and `.json`
- For LLM/SDK tasks: `outputs/reports/sdk_usage_audit.md` and `.json`
- For score tasks: `outputs/reports/comprehensive_failure_fix_decision.md` and `.json`
- For efficiency tasks: `outputs/reports/correctness_efficiency_scorecard.md` and `.json`

Classify the task before acting. If current reports contradict the request, report the blocker with exact paths and dates where relevant.

## Protected Artifacts

Never modify these unless the user explicitly asks and validation requires it:

- `outputs/final_submission/**`
- `outputs/eval_results_strict.json`
- `outputs/hidden_style_eval.*`
- `outputs/final_submission_manifest.json`
- `final_submission_manifest.json`
- `.env.local`
- source_code package outputs
- endpoint catalog paths
- packaged strategy/default config

Never access `.env.local`. Never print credential values, masked prefixes, request IDs, organization values, sandbox values, tokens, keys, or secrets.

## Score-Aware Task Classification

Assign one or more task classes:

- `correctness_score_path`
- `efficiency_score_path`
- `live_adobe_api_path`
- `diagnostic_only`
- `reporting_visualization`
- `packaging_submission`
- `security_safety`
- `documentation_only`

Use the classification to pick validation and decide whether runtime promotion is even allowed.

## Correctness Score Path

For correctness changes, focus only on the direct path:

Prompt understanding -> deterministic route/domain/intent -> SQL/API plan -> SQL validation/execution -> API evidence state -> EvidenceBus -> answer slots -> answer synthesis -> verifier -> final answer/trajectory.

Use official public/dev strict rows for score evidence. Use generated prompts only for generalness and coverage. Generated labels are advisory, not ground truth.

Never hard-code query IDs, generated prompt IDs, exact prompt strings, public/dev examples, hidden assumptions, or gold answers. Any runtime correctness change requires:

- `python3 scripts/run_dev_eval.py --strict`
- `python3 scripts/run_hidden_style_eval.py`
- `python3 scripts/check_submission_ready.py`
- `python3 -m pytest -q`

## Efficiency Score Path

The organizer evaluation includes correctness + efficiency. Efficiency includes turns, tool calls, total tokens, wall time, and end-to-end runtime including preprocessing/context selection.

Do not treat strict correctness score as the only metric. Use `outputs/reports/correctness_efficiency_scorecard.md/json` when available. A speed-only patch is allowed only when correctness does not regress, hidden-style remains `48/48`, readiness passes, no direct LLM HTTP hits appear, and final submission format stays unchanged.

Never claim an official organizer-weighted overall score unless organizer weights are known.

## Live Adobe API Path

Current rule: `live_success_count=0` means full live eval is blocked.

Allowed before Adobe access is fixed:

- safe readiness checks
- IMS token acquisition through supported scripts
- safe GET smoke and diagnosis scripts
- post-permission verification script after access is granted

Do not run full live strict eval while `live_success_count=0`.
Do not run the live generated-prompt suite while `live_success_count=0`.
Never run mutating Adobe API calls.
Never run Adobe data `POST`, `PUT`, `PATCH`, or `DELETE` calls except IMS token acquisition handled by existing scripts.
Never expose credentials.

Token acquisition success means auth infrastructure works; it is not live data endpoint success. After permission is granted, run:

```bash
python3 scripts/run_post_permission_live_api_verification.py
```

Continue to live strict diagnostics only if the structured `live_success guard` allows it.

## LLM / SDK / Tool-Calling Path

Keep the SDK-only LLM policy. All model calls must use the shared LLM client abstraction and runtime direct LLM HTTP hits = 0.

LLM baseline, controller, semantic router, and answer rewrite remain shadow-only or trial-only unless strict, hidden-style, readiness, security, and promotion gates pass. Tool-calling optimizations may be speed-only candidates when correctness does not regress. Do not use model-specific hardcoding. Do not promote broad LLM rewrite behavior.

If Context7 is available, use documentation before changing external SDK/API behavior.

## Generated Prompts

Generated prompts are diagnostic-only. In short: generated prompts are diagnostic-only.

They may support generalness, coverage, and stress testing. They cannot support official score claims, exact prompt rules, gold-answer logic, or promotion by themselves. Generated labels are advisory, not ground truth.

## Superpowers Workflow

Every serious improvement candidate must follow:

1. Hypothesis
2. Baseline
3. Isolated trial
4. Failure analysis
5. Three to five controlled variants when the first trial does not decide the issue
6. Strict/no-regression gates
7. Promotion decision
8. Rollback if regression occurs

## Promotion Gates

Promotion gates are mandatory before any runtime behavior is treated as packaged-safe.

Runtime promotion requires all applicable gates:

- Strict score improves, or efficiency improves with no correctness regression
- Hidden-style remains `48/48`
- `check_submission_ready.py` passes
- `pytest` passes
- runtime direct LLM HTTP hits remain `0`
- unsupported-claim count does not increase
- final_submission format does not change
- no secret leak
- no hardcoding
- generated prompts do not show broad breakage

If more than one candidate passes and they are not a single coherent low-risk batch, stop and ask for explicit approval.

## Validation Command Matrix

Basic safe validation:

```bash
python3 scripts/check_submission_ready.py
python3 -m pytest -q
```

Correctness runtime change:

```bash
python3 scripts/run_dev_eval.py --strict
python3 scripts/run_hidden_style_eval.py
python3 scripts/check_submission_ready.py
python3 -m pytest -q
```

Efficiency / SDK change:

```bash
python3 scripts/run_correctness_efficiency_scorecard.py
python3 scripts/run_dev_eval.py --strict
python3 scripts/run_hidden_style_eval.py
python3 scripts/generate_sdk_usage_audit.py
python3 scripts/check_submission_ready.py
python3 -m pytest -q
```

Adobe permission check:

```bash
python3 scripts/check_adobe_env_local.py
python3 scripts/audit_live_adobe_api_readiness.py
python3 scripts/run_live_api_readiness_smoke.py --limit all-safe-get
python3 scripts/run_post_permission_live_api_verification.py
```

Report/visualization change:

```bash
python3 scripts/generate_consolidated_reports.py
python3 scripts/generate_visualization_index.py
python3 scripts/check_submission_ready.py
python3 -m pytest -q
```

## Secret Scan Rule

Always run or document why skipped. Exclude `.git`, `.env.local`, and zip files. Scan for credential values, Authorization/Bearer values, access tokens, API keys, client secrets, organization values, sandbox values, request IDs, and masked prefixes.

Use the repo's existing secret scan pattern when available. Do not print environment variable values.

## Output / Reporting Rule

Every new analysis pass should write:

- `.md` report
- `.json` report
- report index links
- system summary update if relevant

## Diagnostic / Trial Cleanup Rule

Classify every diagnostic, trial, audit, optimizer, or experiment as `promoted`, `keep_trial_only`, `rejected`, `wait_for_external_access`, or `diagnostic_only`.

If the result is not `promoted`, clean up temporary artifacts after the final report is written. Keep only one final `.md` report, one final `.json` report, and any small fixture or test still needed by active validation. Delete or avoid committing one-off diagnostic scripts, large per-prompt output folders, trial variant directories, temporary generated artifacts, and obsolete tests that only validate deleted diagnostics.

Never delete final summary reports, promoted-policy reports, system summary, report index, final submission artifacts, packaged runtime code, or validation scripts required by README, AGENTS, or this skill. Before deleting, write `outputs/reports/repo_cleanup_deletion_plan.md/json`; after deleting, write `outputs/reports/repo_cleanup_result.md/json`; then run `python3 scripts/check_submission_ready.py` and `python3 -m pytest -q`.

Do not claim score improvement unless backed by strict eval. Do not claim official organizer ranking improvement unless official weights are known.

## Stop Conditions

Stop and write a blocker report if:

- protected deletion exists
- unexpected runtime source change exists
- final_submission is not ready
- `live_success_count=0` but the task asks for full live eval
- credentials would be needed
- a proposed rule requires hardcoding
- strict, hidden-style, readiness, SDK audit, secret scan, or pytest fails after a runtime change

On regression: rollback the runtime change, keep diagnostic reports, and record command, reason, substitute validation, and residual risk.
