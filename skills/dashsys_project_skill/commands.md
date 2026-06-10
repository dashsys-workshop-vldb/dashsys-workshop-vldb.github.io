# DASHSys Project Skill Commands

## Safe Commands

```bash
git status --short
python3 scripts/check_submission_ready.py
python3 -m pytest -q
python3 scripts/generate_consolidated_reports.py
python3 scripts/audit_dashsys_project_skill.py
```

## Strict Validation Commands

```bash
python3 scripts/run_dev_eval.py --strict
python3 scripts/run_hidden_style_eval.py
python3 scripts/check_submission_ready.py
python3 -m pytest -q
```

## Efficiency / SDK Commands

```bash
python3 scripts/run_correctness_efficiency_scorecard.py
python3 scripts/run_sdk_tool_calling_optimization_audit.py
python3 scripts/run_sdk_tool_calling_optimization_trials.py
python3 scripts/run_sdk_tool_calling_efficiency_promotion.py --validation-complete
python3 scripts/generate_sdk_usage_audit.py
```

## Live API Commands

Use only safe readiness and GET smoke before Adobe access is fixed:

```bash
python3 scripts/check_adobe_env_local.py
python3 scripts/audit_live_adobe_api_readiness.py
python3 scripts/run_live_api_readiness_smoke.py --limit all-safe-get
python3 scripts/run_live_api_endpoint_path_diagnosis.py
python3 scripts/run_live_api_evidence_pipeline_trial.py
python3 scripts/run_post_permission_live_api_verification.py
```

## Report Regeneration Commands

```bash
python3 scripts/generate_consolidated_reports.py
python3 scripts/generate_visualization_index.py
python3 scripts/audit_dashsys_project_skill.py
```

## Gated Commands

Run only when the relevant guard allows or when explicitly validating a runtime change:

```bash
python3 scripts/run_dev_eval.py --strict
python3 scripts/run_hidden_style_eval.py
python3 scripts/package_submission.py
python3 scripts/package_query_outputs.py
```

## Forbidden Commands

- Mutating Adobe data API calls.
- Full live strict eval while `live_success_count=0`.
- Live generated-prompt suite while `live_success_count=0`.
- Commands that read `.env.local`.
- Commands that print environment variables or credentials.
- Git reset/checkout commands that revert user changes without explicit approval.

## Secret Scan Template

Exclude `.git`, `.env.local`, and zip files:

```bash
SECRET_SCAN_PATTERN='sk-[A-Za-z0-9_-]{12,}|Bearer[[:space:]]+[A-Za-z0-9._-]{12,}|Authorization:[[:space:]]*Bearer[[:space:]]+[A-Za-z0-9._-]+|[A-Za-z0-9]{3}\*\*\*'
rg -n "$SECRET_SCAN_PATTERN" . --glob '!.git/**' --glob '!.env.local' --glob '!*.zip' || true
```

