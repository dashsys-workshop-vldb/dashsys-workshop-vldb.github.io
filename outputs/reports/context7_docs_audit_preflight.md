# Context7 Docs Audit Preflight

- Created at: `2026-05-17T02:58:38+00:00`
- Git status mode: `git_status_short`
- Git status timed out: `False`
- Direct `ctx7` available: `False`
- Selected Context7 command: `npx -y ctx7@latest`
- Packaged strategy: `SQL_FIRST_API_VERIFY`
- Strict score: `0.6553`
- Hidden-style: `{'label': '48/48', 'passed': 48, 'total': 48}`
- Final submission ready: `True`
- Live success count: `0`
- Runtime changes allowed by default: `False`

## Protected Artifacts

- `outputs/final_submission/**`
- `outputs/eval_results_strict.json`
- `outputs/hidden_style_eval.*`
- `outputs/final_submission_manifest.json`
- `final_submission_manifest.json`
- `.env.local`
- `dashagent/endpoint_catalog.py`
- `dashagent/config.py`
- `scripts/package_query_outputs.py`
- `scripts/run_dev_eval.py`

## Rule

Do not alter packaged runtime behavior unless Context7 docs prove a small deterministic issue, focused tests are added, and mandatory validation passes.
